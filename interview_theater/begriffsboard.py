"""Das Begriffsboard der Phase 1 (Padua, Karte t_4517d4ad, 04.10.2026).

Birk 15:15: Phase 1 und Phase 4 laufen beim Mithoeren EINHEITLICH
automatisch. Die Hintergrund-Diskussion der Phase 1 bleibt Material -- kein
Gespraechszug, kein Erkenner, keine Chatzeile --, aber nach jedem
qualifizierenden Segment (``brainstorm.soll_reagieren``, unveraendert)
laeuft ein Schema-Aufruf, der ein Board der genannten Begriffe fortschreibt.
Das Board steht im CoThinker-Tab; bei "Discussion done" schlaegt der Bot
seine Top 5 vor, und beim Speichern der Begriffe geht je Begriff die
Boardzeile nach ``arbeitsstand.begriffe_detail``.

**Validiert wird im Code, nicht im Prompt** (``validiere``): ein Begriff,
der nicht im Transkript steht, fliegt raus; ein Zitat, das ``zitat.pruefe``
nicht besteht, wird leer, die Begruendung bleibt.

**Der Boardlauf kennt kein ``tg``** (``starte``/``_lauf_einmal``): er kann
strukturell keine Chatzeile schreiben (D5). Der einzige Chatweg dieses
Moduls ist der Vorschlag nach "Discussion done" (``sende_vorschlag``) und
der Einstiegssatz (``sende_einstieg``).

Diese Fassung (Aufgabe 2) traegt nur den reinen Kern: Validierung,
Sortierung, Top 5, Detail-Abgleich. Keine Datenbank, kein Thread, kein
Modellaufruf -- das kommt mit den Aufgaben 3-6."""

import json

from interview_theater import begriffe as begriffe_modul
from interview_theater import sprache, zitat

STATUS = ("favorit", "kandidat", "verworfen")
_RANG = {"favorit": 0, "kandidat": 1, "verworfen": 2}
#: Obergrenze der Boardzeilen -- ein Board mit mehr Begriffen ist keine
#: Auswahl mehr, sondern ein Protokoll.
HOECHSTENS = 30
TOP = 5
ZUSTIMMUNG_MIN = -2
ZUSTIMMUNG_MAX = 2

#: Die Zeilen fuer Prompts (``kontext``, ``fragen_ki``) -- nie mit Zitat.
_ZEILE_DETAIL = "- {begriff}: {begruendung}"
_ZEILE_DETAIL_OHNE_GRUND = "- {begriff}"
_ZUSATZ_DOPPELBEDEUTUNG = " (Doppelbedeutung: {doppelbedeutung})"

T = sprache.Texte(__name__)


def schluessel(text: str | None) -> str:
    """Der Vergleichsschluessel eines Begriffs: ``zitat.normalisiere`` plus
    casefold -- dieselbe Normalisierung wie beim Zitatschutz, keine zweite."""
    return zitat.normalisiere(text or "").casefold()


def _steht_im_transkript(begriff: str, transkript: str) -> bool:
    k = schluessel(begriff)
    return bool(k) and k in schluessel(transkript)


def _ganzzahl(wert) -> int:
    try:
        return int(wert)
    except (TypeError, ValueError):
        return 0


def _eintrag(zeile) -> dict | None:
    """Eine Zeile in die feste Form -- ohne Transkriptpruefung (die macht
    ``validiere``). None, wenn sie keinen brauchbaren Begriff traegt."""
    if not isinstance(zeile, dict):
        return None
    teile = begriffe_modul.zerlege(" ".join(str(zeile.get("begriff") or "").split()))
    if len(teile) != 1:
        # Leer, oder ein Listentrenner im Begriff: er zerfiele beim
        # Speichern (``begriffe.zerlege``) in zwei.
        return None
    status = str(zeile.get("status") or "").strip().casefold()
    return {
        "begriff": teile[0],
        "nennungen": max(0, _ganzzahl(zeile.get("nennungen"))),
        "zustimmung": min(ZUSTIMMUNG_MAX, max(ZUSTIMMUNG_MIN, _ganzzahl(zeile.get("zustimmung")))),
        "begruendung": str(zeile.get("begruendung") or "").strip(),
        "zitat": str(zeile.get("zitat") or "").strip(),
        "doppelbedeutung": str(zeile.get("doppelbedeutung") or "").strip(),
        "status": status if status in STATUS else "kandidat",
    }


def validiere(roh, transkript: str) -> list[dict]:
    """Die Modellantwort gegen das Transkript (D3). Nichts erfinden: nur
    Begriffe, die im Transkript stehen; Zitate nur woertlich."""
    if not isinstance(roh, list):
        return []
    ergebnis: list[dict] = []
    gesehen: set[str] = set()
    for zeile in roh:
        eintrag = _eintrag(zeile)
        if eintrag is None or not _steht_im_transkript(eintrag["begriff"], transkript):
            continue
        k = schluessel(eintrag["begriff"])
        if k in gesehen:
            continue
        gesehen.add(k)
        if eintrag["zitat"] and not zitat.pruefe(eintrag["zitat"], transkript):
            eintrag["zitat"] = ""
        ergebnis.append(eintrag)
        if len(ergebnis) >= HOECHSTENS:
            break
    return ergebnis


def lies(roh_json: str | None) -> list[dict]:
    """Eine gespeicherte Boardzeile -> Eintraege. Defensiv wie
    ``roadmap.begriffe_detail``: kaputt oder leer ist eine leere Liste."""
    try:
        roh = json.loads(roh_json) if roh_json else []
    except (ValueError, TypeError):
        return []
    if not isinstance(roh, list):
        return []
    return [e for e in (_eintrag(z) for z in roh) if e is not None]


def sortiert(eintraege: list[dict]) -> list[dict]:
    """DIE Sortierung (D4) -- fuer die Webansicht UND den Top-5-Vorschlag."""
    return sorted(eintraege, key=lambda e: (
        _RANG.get(e.get("status"), _RANG["kandidat"]),
        -_ganzzahl(e.get("zustimmung")),
        -_ganzzahl(e.get("nennungen")),
        schluessel(e.get("begriff")),
    ))


def top(eintraege: list[dict], n: int = TOP) -> list[dict]:
    """Die ersten ``n`` nicht verworfenen Eintraege in ``sortiert``-Ordnung."""
    return [e for e in sortiert(eintraege) if e.get("status") != "verworfen"][:n]


def detail_fuer(board: list[dict], begriffe_text: str | None) -> list[dict]:
    """Je gespeichertem Begriff (Reihenfolge und Wortlaut der Gruppe) die
    Boardzeile -- Begriffe ohne Boardzeile mit leeren Feldern (D7)."""
    nach = {schluessel(e["begriff"]): e for e in board}
    ergebnis = []
    for begriff in begriffe_modul.zerlege(begriffe_text):
        zeile = nach.get(schluessel(begriff)) or {}
        ergebnis.append({
            "begriff": begriff,
            "begruendung": zeile.get("begruendung", ""),
            "zitat": zeile.get("zitat", ""),
            "doppelbedeutung": zeile.get("doppelbedeutung", ""),
        })
    return ergebnis


def detail_zeilen(detail: list[dict]) -> list[str]:
    """Die Prompt-Zeilen zu ``begriffe_detail`` (``kontext``, ``fragen_ki``)
    -- NIE mit Zitat. Ein Begriff ohne Begruendung und ohne Doppelbedeutung
    traegt nichts bei und faellt weg; seine Nennung steht ohnehin im
    Arbeitsstand."""
    zeilen = []
    for eintrag in detail:
        grund = (eintrag.get("begruendung") or "").strip()
        doppel = (eintrag.get("doppelbedeutung") or "").strip()
        if not grund and not doppel:
            continue
        zeile = (T._ZEILE_DETAIL.format(begriff=eintrag["begriff"], begruendung=grund)
                 if grund else T._ZEILE_DETAIL_OHNE_GRUND.format(begriff=eintrag["begriff"]))
        if doppel:
            zeile += T._ZUSATZ_DOPPELBEDEUTUNG.format(doppelbedeutung=doppel)
        zeilen.append(zeile)
    return zeilen
