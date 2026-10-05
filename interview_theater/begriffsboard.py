"""Das Begriffsboard der Phase 1 (Padua, Karte t_4517d4ad, 04.10.2026).

Birk 15:15: Phase 1 und Phase 4 laufen beim Mithoeren EINHEITLICH
automatisch. Die Hintergrund-Diskussion der Phase 1 bleibt Material -- kein
Gespraechszug, kein Erkenner, keine Chatzeile --, aber nach jedem
qualifizierenden Segment (``brainstorm.soll_reagieren``, unveraendert)
laeuft ein Schema-Aufruf, der ein Board der genannten Begriffe fortschreibt.
Das Board steht im CoThinker-Tab; bei "Discussion done" schlaegt der Bot
seine Top 5 vor — nach Birks Entscheidung vom 04.10.2026 ohne eigenen
Schlusslauf: der Ende-Schnitt ist ein gewöhnlicher Schnitt (``soll_laufen``),
der Vorschlag zeigt das Board, wie es ist. Beim Speichern der Begriffe geht
je Begriff die Boardzeile nach ``arbeitsstand.begriffe_detail``.

**Validiert wird im Code, nicht im Prompt** (``validiere``): ein Begriff,
der nicht im Transkript steht oder nur ein Ansage-/Mikrofonwort ist
(``ist_metabegriff``), fliegt raus; ein Zitat, das ``zitat.pruefe`` nicht
besteht, wird leer. **Belegpflicht (Karte t_2b9d2cbe):** eine Begruendung
bleibt nur, wenn ein geprueftes Zitat sie traegt, das mehr enthaelt als
Begriff und Ansage (``traegt_beleg``), und wenn sie kein Fuellsatz ist
("wird genannt/gesammelt", ``ist_fuellsatz``); sonst wird sie leer.

**Schaerfung (Karte t_cb2c4678):** das Modell nennt je Eintrag
``vorheriger_begriff`` (den ersetzten Begriff oder ""), der Code prueft es
gegen das bisherige Board und fuehrt daraus ``vorgaenger`` (aelteste
zuerst, nur am Eintrag, wenn nicht leer). Die Kette ist nie Modelltext:
jedes Element ist der Wortlaut eines frueheren ``begriff`` dieses Boards.

**Der Boardlauf kennt kein ``tg``** (``starte``/``_lauf_einmal``): er kann
strukturell keine Chatzeile schreiben (D5). Der einzige Chatweg dieses
Moduls ist der Vorschlag nach "Discussion done" (``sende_vorschlag``) und
der Einstiegssatz (``sende_einstieg``).

Diese Fassung (Aufgabe 2) traegt nur den reinen Kern: Validierung,
Sortierung, Top 5, Detail-Abgleich. Keine Datenbank, kein Thread, kein
Modellaufruf -- das kommt mit den Aufgaben 3-6."""

import json
import logging
import os
import re
import threading

from interview_theater import anweisungen, brainstorm, modellwahl, phasen, repo, workshop
from interview_theater import begriffe as begriffe_modul
from interview_theater import sprache, zitat

log = logging.getLogger(__name__)

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

_TRANSKRIPT_KOPF = "Das Transkript der Diskussion bisher:"
_BOARD_KOPF = "Das bisherige Begriffsboard (JSON):"

#: Der Einstiegssatz (D10) -- deterministisch, nur mit ``diskussion.aktiv``.
_TEXT_EINSTIEG = (
    "Legt ein Handy in die Mitte -- es hoert zu. Oeffnet auf einem zweiten "
    "Handy den Tab CoThinker: dort erscheinen die Begriffe, die ihr nennt."
)

T = sprache.Texte(__name__)


def schluessel(text: str | None) -> str:
    """Der Vergleichsschluessel eines Begriffs: ``zitat.normalisiere`` plus
    casefold -- dieselbe Normalisierung wie beim Zitatschutz, keine zweite."""
    return zitat.normalisiere(text or "").casefold()


def _steht_im_transkript(begriff: str, transkript: str) -> bool:
    k = schluessel(begriff)
    return bool(k) and k in schluessel(transkript)


# -- Belegpflicht (Karte t_2b9d2cbe, D1/D2) -----------------------------------
#
# Eine Begruendung gilt nur, wenn ein woertlich geprueftes Zitat sie traegt,
# das mehr enthaelt als den Begriff und die Ansage ("der erste Begriff ist
# X"). Die Woerter werden ueber ``schluessel`` (zitat.normalisiere +
# casefold) gewonnen -- keine zweite Normalisierung. Alle Listen gelten fuer
# DE und EN zugleich: gemessen schrieb Kimi unter dem EN-Profil deutsche
# Begruendungen (Live-Board 04.10.2026), eine Liste nur der Profilsprache
# liesse genau diesen Fall durch. Eintraege in casefold-Form (Test).

#: Mindestzahl Inhaltswoerter im Zitat. Ein einzelnes Restwort ist in den
#: beobachteten Fehlbildern ein Adjektiv oder ein STT-Rest aus der Ansage
#: ("als besten Gepaeck vor" -> "besten"); ein Grund braucht Gegenstand und
#: Aussage ("wo meine Oma kocht" -> "oma", "kocht").
BELEG_MIN_INHALTSWOERTER = 2

_STOPPWOERTER = frozenset("""
aber alle alles als also am an auch auf aus bei bin bis bist da dann das dass
dem den der des dich die dir doch dort du ein eine einem einen einer eines er
es etwa euch für fuer gar hab habe haben hat hier ich ihm ihn ihr ihre im in
ist ja jetzt kann kein keine man mal mein meine meinem meinen meiner mich mir
mit muss nach nee nein nicht nichts noch nur ob oder schon sehr sein seine
sich sie sind so soll sollte uns und unser vom von war waren was weil wenn wer
wie wir wird wo zu zum zur äh ähm hm genau eben halt einfach eigentlich
a about all also am an and any are as at be because been but by can could d
did do does for from had has have he her here him his how i if in into is it
its just ll like m me my no not now of oh ok okay on or our re s she so some
that the their them then there they this to too uh um us ve very we well were
what when where which who will with would yeah yes you your
eins zwei drei vier fünf fuenf one two three four five
""".split())

#: Woerter einer Ansage-Formel ("der erste Begriff ist X", "I'd suggest X")
#: samt der beobachteten STT-Varianten von "Begriff".
_ANSAGEWOERTER = frozenset("""
begriff begriffe term terms wort wörter woerter word words gepäck gepaeck
betreff vorschlag vorschlagen schlage schlägt schlaegt schlagen vor suggest
suggests suggestion propose proposes pick nehmen nehme take nenne nennen name
erste erster ersten erstes zweite zweiter zweiten dritte dritter dritten
vierte fünfte fuenfte nächste naechste nächster naechster letzte letzter
weitere weiterer first second third fourth fifth next last another nummer
number
""".split())

#: Woerter, die nie ein Begriff der Gruppe sind (D2) -- Ansage- und
#: Mikrofon-Gerede. Klein und geschlossen.
_METAWOERTER = frozenset("""
begriff begriffe term terms wort word gepäck gepaeck betreff test tests
testing mikrofon mikro microphone mic aufnahme recording hallo hello check
""".split())

#: Fuell-Begruendungen: sagen nur, DASS der Begriff fiel. Gesucht im
#: casefold-Text (``schluessel``).
_FUELL_MUSTER = (
    re.compile(r"\b(wird|wurde|werden|wurden|ist|sind)\b.{0,80}?\b(genannt|erwähnt|erwaehnt"
               r"|aufgeführt|aufgefuehrt|gesammelt|vorgeschlagen|aufgelistet|notiert"
               r"|festgehalten)\b"),
    re.compile(r"\bkam(en)?\b.{0,40}?\bvor\b"),
    re.compile(r"\bschl(ä|ae)gt\b.{0,80}?\bvor\b"),
    re.compile(r"\b(nennt|nennen)\b"),
    re.compile(r"\b(is|was|are|were|gets|got)\b.{0,80}?\b(named|mentioned|listed|collected"
               r"|suggested|proposed|noted|brought up|put forward)\b"),
    re.compile(r"\bcame up\b"),
    re.compile(r"\b(suggests|proposes|names|mentions)\b"),
)

#: Ein Grund-Marker macht aus einem Fuellsatz-Treffer einen Satz mit Grund
#: ("wird genannt, weil ...") -- ob er bleibt, entscheidet dann der Beleg.
_GRUND_MARKER = re.compile(r"\b(weil|denn|damit|deshalb|darum|because|since|so that|therefore)\b")


def _woerter(text: str | None) -> list[str]:
    return re.findall(r"\w+", schluessel(text))


def inhaltswoerter(text: str | None, begriff: str | None) -> list[str]:
    """Die Woerter von ``text`` ohne Begriff, Ansage-, Meta- und
    Stoppwoerter und ohne reine Ziffern -- in Reihenfolge, mit Doppelten."""
    weg = set(_woerter(begriff)) | _STOPPWOERTER | _ANSAGEWOERTER | _METAWOERTER
    return [w for w in _woerter(text) if w not in weg and not w.isdigit()]


def traegt_beleg(eintrag: dict, transkript: str) -> bool:
    """D1: das Zitat steht woertlich im Transkript (``zitat.pruefe``) UND
    traegt mindestens ``BELEG_MIN_INHALTSWOERTER`` Inhaltswoerter."""
    z = str(eintrag.get("zitat") or "").strip()
    return (bool(z) and zitat.pruefe(z, transkript)
            and len(inhaltswoerter(z, eintrag.get("begriff"))) >= BELEG_MIN_INHALTSWOERTER)


def ist_fuellsatz(text: str | None) -> bool:
    """D1: eine Begruendung, die nur sagt, dass der Begriff genannt/
    gesammelt/vorgeschlagen wurde -- ohne Grund-Marker."""
    k = schluessel(text)
    return (bool(k) and any(m.search(k) for m in _FUELL_MUSTER)
            and not _GRUND_MARKER.search(k))


def ist_metabegriff(begriff: str | None) -> bool:
    """D2: der Begriff besteht nur aus Meta-, Stoppwoertern und Ziffern und
    traegt mindestens ein Meta-Wort ("Test 1 2 3", "Gepaeck")."""
    woerter = _woerter(begriff)
    return (any(w in _METAWOERTER for w in woerter)
            and all(w in _METAWOERTER or w in _STOPPWOERTER or w.isdigit() for w in woerter))


def _belege(eintrag: dict, transkript: str) -> None:
    """D1: eine Begruendung, die ein Fuellsatz ist oder kein tragendes Zitat
    hat, wird leer. Leere Begruendung ist ein gueltiger Zustand --
    ``detail_zeilen`` laesst solche Eintraege ohnehin weg. Der Eintrag
    selbst bleibt."""
    if eintrag["begruendung"] and (ist_fuellsatz(eintrag["begruendung"])
                                   or not traegt_beleg(eintrag, transkript)):
        eintrag["begruendung"] = ""


def _ganzzahl(wert) -> int:
    try:
        return int(wert)
    except (TypeError, ValueError):
        return 0


def _ein_begriff(roh) -> str | None:
    """EIN Begriff in fester Form (Whitespace zusammengezogen), oder None,
    wenn ``roh`` leer ist oder einen Listentrenner traegt -- er zerfiele beim
    Speichern (``begriffe.zerlege``) in zwei. Dieselbe Regel fuer ``begriff``
    und fuer jedes Element von ``vorgaenger``."""
    teile = begriffe_modul.zerlege(" ".join(str(roh or "").split()))
    return teile[0] if len(teile) == 1 else None


def _vorgaenger(roh, eigener: str) -> list[str]:
    """Eine Vorgaengerkette defensiv gelesen (Karte t_cb2c4678, D1): nur
    Zeichenketten, die als EIN Begriff durchgehen, ohne den eigenen Begriff,
    ohne Doppelte (erste Nennung gilt), aelteste zuerst. Fehlt sie oder ist
    sie keine Liste: keine Kette."""
    if not isinstance(roh, list):
        return []
    kette: list[str] = []
    gesehen = {schluessel(eigener)}
    for element in roh:
        begriff = _ein_begriff(element) if isinstance(element, str) else None
        if begriff is None or schluessel(begriff) in gesehen:
            continue
        gesehen.add(schluessel(begriff))
        kette.append(begriff)
    return kette


def _eintrag(zeile) -> dict | None:
    """Eine Zeile in die feste Form -- ohne Transkriptpruefung (die macht
    ``validiere``). None, wenn sie keinen brauchbaren Begriff traegt.
    ``vorgaenger`` steht nur da, wenn die Kette nicht leer ist: ein Board
    ohne Schaerfung bleibt Zeichen fuer Zeichen, wie es war."""
    if not isinstance(zeile, dict):
        return None
    begriff = _ein_begriff(zeile.get("begriff"))
    if begriff is None:
        return None
    status = str(zeile.get("status") or "").strip().casefold()
    eintrag = {
        "begriff": begriff,
        "nennungen": max(0, _ganzzahl(zeile.get("nennungen"))),
        "zustimmung": min(ZUSTIMMUNG_MAX, max(ZUSTIMMUNG_MIN, _ganzzahl(zeile.get("zustimmung")))),
        "begruendung": str(zeile.get("begruendung") or "").strip(),
        "zitat": str(zeile.get("zitat") or "").strip(),
        "doppelbedeutung": str(zeile.get("doppelbedeutung") or "").strip(),
        "status": status if status in STATUS else "kandidat",
    }
    kette = _vorgaenger(zeile.get("vorgaenger"), begriff)
    if kette:
        eintrag["vorgaenger"] = kette
    return eintrag


def _verkette(neu: list[dict], links: list, bisher: list[dict]) -> None:
    """Fuehrt ``vorgaenger`` (D1, Karte t_cb2c4678) -- allein der Code.

    Ein Eintrag mit einem Schluessel aus ``bisher`` erbt dessen Kette. Ein
    ``vorheriger_begriff`` des Modells zaehlt NUR, wenn er auf einen Eintrag
    aus ``bisher`` zeigt, der im neuen Board nicht mehr als eigene Zeile
    steht und nicht der Eintrag selbst ist; dann wird dessen Kette plus
    dessen Begriff angehaengt -- im Wortlaut des BISHERIGEN Boards, nie im
    Wortlaut des Modells. Alles andere ist kein Link: ein vergessenes Feld
    heisst "kein Strich", nie "ein falscher". Zuletzt faellt aus jeder Kette,
    was als eigene Zeile im neuen Board steht (sonst stuende es zweimal da)."""
    alt = {schluessel(e["begriff"]): e for e in bisher}
    eigene = {schluessel(e["begriff"]) for e in neu}
    for eintrag, link in zip(neu, links):
        k = schluessel(eintrag["begriff"])
        kette = list(alt[k].get("vorgaenger") or []) if k in alt else []
        lk = schluessel(link) if isinstance(link, str) else ""
        if lk and lk != k and lk in alt and lk not in eigene:
            kette += list(alt[lk].get("vorgaenger") or []) + [alt[lk]["begriff"]]
        kette = [v for v in _vorgaenger(kette, eintrag["begriff"]) if schluessel(v) not in eigene]
        if kette:
            eintrag["vorgaenger"] = kette


def validiere(roh, transkript: str, bisher: list[dict] | None = None) -> list[dict]:
    """Die Modellantwort gegen das Transkript (D3). Nichts erfinden: nur
    Begriffe, die im Transkript stehen; Zitate nur woertlich. Mit ``bisher``
    (dem geltenden Board vor diesem Lauf) zusaetzlich die Schaerfungskette
    (``_verkette``); ohne ``bisher`` genau das Verhalten von vorher."""
    if not isinstance(roh, list):
        return []
    ergebnis: list[dict] = []
    links: list = []
    gesehen: set[str] = set()
    for zeile in roh:
        eintrag = _eintrag(zeile)
        if eintrag is None or not _steht_im_transkript(eintrag["begriff"], transkript):
            continue
        if ist_metabegriff(eintrag["begriff"]):
            continue
        k = schluessel(eintrag["begriff"])
        if k in gesehen:
            continue
        gesehen.add(k)
        if eintrag["zitat"] and not zitat.pruefe(eintrag["zitat"], transkript):
            eintrag["zitat"] = ""
        _belege(eintrag, transkript)
        # Die Kette schreibt allein der Code -- eine mitgeschickte faellt weg.
        eintrag.pop("vorgaenger", None)
        links.append(zeile.get("vorheriger_begriff"))
        ergebnis.append(eintrag)
        if len(ergebnis) >= HOECHSTENS:
            break
    _verkette(ergebnis, links, bisher or [])
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


def verlauf_merge(conn, chat_id: int) -> list[dict]:
    """Der GANZE Begriffsboard-Verlauf zu einem Stand zusammengefuehrt, nicht
    nur die juengste Zeile (AGG-2/R-1, Birk 05.10.2026: "Der Chat muss immer
    alles wissen"). Je Begriffsschluessel gilt der Eintrag aus der Zeile, in
    der er zuletzt (also zuerst in ``repo.begriffsboard_verlauf``, juengste
    zuerst) vorkam -- ein Begriff, den ein spaeterer Lauf nicht mehr nennt
    (zum Beispiel, weil das Modell einen verworfenen Begriff nicht
    wiederholt), behaelt so seine Begruendung statt sie zu verlieren."""
    gesehen: dict[str, dict] = {}
    for zeile in repo.begriffsboard_verlauf(conn, chat_id):
        for eintrag in lies(zeile["json"]):
            k = schluessel(eintrag["begriff"])
            if k not in gesehen:
                gesehen[k] = eintrag
    return list(gesehen.values())


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


_FELDER = ("begriff", "nennungen", "zustimmung", "begruendung", "zitat",
           "doppelbedeutung", "status", "vorheriger_begriff")

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften, sonst lehnt der Anbieter den erzwungenen Modus ab
#: (Kommentar an ``diskussion.SCHEMA``). Die Wurzel ist ein Objekt, weil der
#: Schema-Modus keine Liste als Wurzel nimmt; ``board`` statt ``begriffe``,
#: weil ``scripts/pruefe_sprache.py`` "begriffe" als deutsches Wort fuehrt.
#: ``status`` ist bewusst ein freier String: ``validiere`` macht aus jedem
#: unbekannten Wert "kandidat".
#: ``vorheriger_begriff`` (Karte t_cb2c4678) ist Pflicht und darf "" sein;
#: ``validiere`` prueft es gegen das bisherige Board. ``vorgaenger`` steht
#: bewusst NICHT hier: die Kette fuehrt allein der Code. Beide Namen sind
#: fuer ``scripts/pruefe_sprache.py`` unkritisch (snake_case faellt dort
#: heraus, "vorgaenger" steht in keiner Liste).
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["board"],
    "properties": {
        "board": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": list(_FELDER),
                "properties": {
                    "begriff": {"type": "string"},
                    "nennungen": {"type": "integer"},
                    "zustimmung": {"type": "integer"},
                    "begruendung": {"type": "string"},
                    "zitat": {"type": "string"},
                    "doppelbedeutung": {"type": "string"},
                    "status": {"type": "string"},
                    "vorheriger_begriff": {"type": "string"},
                },
            },
        },
    },
}

ART = "begriffsboard"

VORGABE_TRANSKRIPT_ZEICHEN = 200_000

#: Eigene, niedrigere Werte als der Brainstorm (Phase 4) fuer die
#: ZWISCHENlaeufe des Boards. Ein Begriff mit einem Satz Begruendung ist
#: kurz -- in Phase 1 sammelt die Gruppe einzelne Begriffe, sie entwickelt
#: keine Buehnenidee ueber Minuten. Birk Live-Test 04.10.2026: 1200 Zeichen
#: liessen das Board zu lange leer (-> 600). Birk Live-Test 05.10.2026
#: (Gruppe 2, Segmente mit 83/20/11/42/31/38 Zeichen): nach dem ersten Lauf
#: blockierte der Brainstorm-Mindestabstand von 90 s jeden weiteren, der
#: letzte Begriff kam nie aufs Board -- seitdem 100 Zeichen und 20 s. Kurze
#: Laeufe kosten wenig (Modellwahl wie bisher, Birk: ok). Der Schlusslauf
#: nach "Discussion done" haengt an keinem der beiden (``soll_laufen``).
VORGABE_MIN_ZEICHEN = 100
VORGABE_MIN_ABSTAND_S = 20


def _umgebungszahl(name: str, vorgabe: int) -> int:
    roh = (os.environ.get(name) or "").strip()
    if roh.isdigit() and int(roh) > 0:
        return int(roh)
    return vorgabe


def min_zeichen() -> int:
    """``IT_BEGRIFFSBOARD_MIN_ZEICHEN`` -- dasselbe Muster wie
    ``transkript_zeichen_grenze``/``brainstorm.min_zeichen``."""
    return _umgebungszahl("IT_BEGRIFFSBOARD_MIN_ZEICHEN", VORGABE_MIN_ZEICHEN)


def min_abstand_s() -> int:
    """``IT_BEGRIFFSBOARD_MIN_ABSTAND_S`` -- der Mindestabstand zwischen zwei
    Zwischenlaeufen in Phase 1, unabhaengig von
    ``IT_BRAINSTORM_MIN_ABSTAND_S`` (Phase 4)."""
    return _umgebungszahl("IT_BEGRIFFSBOARD_MIN_ABSTAND_S", VORGABE_MIN_ABSTAND_S)


def transkript_zeichen_grenze() -> int:
    """``IT_BEGRIFFSBOARD_TRANSKRIPT_ZEICHEN`` -- dasselbe Muster wie
    ``buehnenkarte.transkript_zeichen_grenze``."""
    roh = (os.environ.get("IT_BEGRIFFSBOARD_TRANSKRIPT_ZEICHEN") or "").strip()
    if roh.isdigit() and int(roh) > 0:
        return int(roh)
    return VORGABE_TRANSKRIPT_ZEICHEN


def _nutzertext(transkript: str, board: list[dict]) -> str:
    """Der isolierte Nutzertext -- NUR das (schon gekuerzte) Transkript und
    das bisherige Board. Kein ``conn``, keine ``chat_id``: dieser Aufruf sieht
    nichts anderes, was im Raum gesagt wurde. Das Transkript steht vorn (es
    waechst nur hinten an, der Prompt-Praefix bleibt cache-stabil)."""
    return (
        f"{T._TRANSKRIPT_KOPF}\n{transkript}\n\n"
        f"{T._BOARD_KOPF}\n{json.dumps(sortiert(board), ensure_ascii=False)}"
    )


def aktuelles(conn, chat_id: int) -> list[dict]:
    """Der geltende Stand des Boards (letzte Zeile), oder eine leere Liste."""
    zeile = repo.letztes_begriffsboard(conn, chat_id)
    return lies(zeile["json"]) if zeile else []


def soll_laufen(conn, chat_id: int) -> bool:
    """Zwei Regeln, je nach Schnitt. Kein Modellaufruf.

    **Zwischenlauf** (D1): ``brainstorm.soll_reagieren`` unveraendert, mit
    den eigenen Zahlen der Phase 1 (``repo.begriffsboard_stand``) und seit
    05.10.2026 eigener Schwelle UND eigenem Mindestabstand
    (``min_zeichen`` 100, ``min_abstand_s`` 20 s statt der 90 s des
    Brainstorms -- Begruendung an ``VORGABE_MIN_ZEICHEN``).

    **Nach "Discussion done"** (``'ende'``, Birk 05.10.2026): der Lauf kommt
    IMMER, sobald es ueberhaupt ungelesenes Transkript gibt (mehr als null
    nutzbare Zeichen) -- ohne Schwelle, ohne Mindestabstand. Das ersetzt
    bewusst die Regel vom 04.10.2026 14:50 ("Zwischenstand und Endstand
    muessen nicht anders behandelt werden"), unter der der Ende-Schnitt wie
    ein Pausenschnitt an ``min_zeichen`` (600) hing. Gemessen live am
    05.10.2026 (Gruppe 2): 8 Segmente mit zusammen 298 Zeichen, kein einziger
    Lauf, und die Gruppe bekam statt eines Boards die Aufforderung, ihre
    fuenf Begriffe zu schicken -- eine kurze Diskussion ist am Ende kein
    Grund, sie ungelesen zu lassen, denn nach dem Ende kommt kein Schnitt
    mehr, der den Rest nachholt. Ist alles schon gelesen (null ungelesene
    Zeichen), laeuft nichts: der letzte Lauf hat das komplette Transkript
    gesehen."""
    stand = repo.begriffsboard_stand(conn, chat_id)
    grund = stand["letzter_schnittgrund"]
    if grund == "ende":
        return stand["unreagierte_zeichen"] > 0
    sekunden = stand["sekunden_seit_letztem_lauf"]
    return brainstorm.soll_reagieren(
        unreagierte_zeichen=stand["unreagierte_zeichen"],
        sekunden_seit_letzter_reaktion=float("inf") if sekunden is None else sekunden,
        # Live Padua 05.10.2026 16:40: Gruppen, die durchreden, erzeugen nur
        # 90-s-Deckelschnitte ('cap') -- mit der Brainstorm-Regel "nur nach
        # Pausenschnitt" fror das Board fuer Minuten ein (G2 seit 16:32 bei 2
        # Begriffen, G3 leer, 4-5 volle Segmente). In Phase 1 zaehlt deshalb
        # auch ein Deckelschnitt; der Brainstorm (Phase 4) bleibt unveraendert.
        letzter_schnittgrund="pause" if grund == "cap" else grund,
        ist_abschluss=False,
        min_zeichen_override=min_zeichen(),
        min_abstand_override=min_abstand_s(),
    )


#: Ein Sperren-Register je Nebenlaeufigkeit (docs/agents/aufbau.md: "Gleicher Code,
#: verschiedene Sperren"), in Form aus ``brainstorm.py``: nie mehr als ein
#: Boardlauf je Gruppe. Dazu ein Merkplatz fuer Rueckrufe (der Vorschlag nach
#: "Discussion done"), die NACH dem gerade laufenden Lauf faellig sind --
#: Nehmen und Merken unter EINEM Schutz, wie ``vorschlagssperre.nimm_oder_merke``.
#: Grenze: der Merkplatz lebt im Prozess, ein Neustart verliert ihn.
_LAEUFT_LOCK = threading.Lock()
_LAEUFT: set[int] = set()
_DANACH: dict[int, list] = {}


def nimm_oder_merke(chat_id: int, danach) -> bool:
    """True und die Sperre gehoert dem Aufrufer -- oder False, und ``danach``
    (falls nicht None) laeuft, sobald der laufende Lauf endet."""
    with _LAEUFT_LOCK:
        if chat_id not in _LAEUFT:
            _LAEUFT.add(chat_id)
            return True
        if danach is not None:
            _DANACH.setdefault(chat_id, []).append(danach)
        return False


def versuche_start(chat_id: int) -> bool:
    return nimm_oder_merke(chat_id, None)


def beende(chat_id: int) -> list:
    """Gibt die Sperre frei und liefert die gemerkten Rueckrufe (der
    Aufrufer ruft sie, ausserhalb der Sperre)."""
    with _LAEUFT_LOCK:
        _LAEUFT.discard(chat_id)
        return _DANACH.pop(chat_id, [])


def laeuft(chat_id: int) -> bool:
    with _LAEUFT_LOCK:
        return chat_id in _LAEUFT


def merke_falls_laeuft(chat_id: int, danach) -> bool:
    """True, wenn gerade ein Boardlauf dieser Gruppe laeuft -- dann laeuft
    ``danach`` nach seinem Ende (``beende`` liefert es). False: es laeuft
    keiner, nichts gemerkt. Unter derselben Sperre wie ``nimm_oder_merke``:
    zwischen "laeuft" und "gemerkt" kann kein ``beende`` den Merkplatz leeren."""
    with _LAEUFT_LOCK:
        if chat_id in _LAEUFT:
            _DANACH.setdefault(chat_id, []).append(danach)
            return True
        return False


def _rufe(rueckrufe) -> None:
    for rueckruf in rueckrufe:
        try:
            rueckruf()
        except Exception:
            log.exception("Rueckruf nach dem Begriffsboard-Lauf fehlgeschlagen")


def _vorfall(conn, e, chat_id: int, art: str, detail: str) -> None:
    try:
        repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None), art, detail)
    except Exception:
        log.exception("Vorfall %s nicht geschrieben, chat_id=%s", art, chat_id)


def _lauf_einmal(conn, klm, e, chat_id: int, bis_id: int) -> None:
    """EIN Boardlauf. Kennt kein ``tg`` -- er schreibt nie in den Chat (D5)."""
    transkript = repo.diskussion_transkript(conn, chat_id)
    if not transkript.strip():
        return
    gesehen = transkript
    grenze = transkript_zeichen_grenze()
    if len(gesehen) > grenze:
        gesehen = gesehen[-grenze:]
        _vorfall(conn, e, chat_id, "begriffsboard_transkript_gekuerzt",
                 f"Diskussions-Transkript von {len(transkript)} auf {grenze} Zeichen gekuerzt")
    bisher = aktuelles(conn, chat_id)
    ueber_claude = modellwahl.konversation_ueber_claude(e, conn, chat_id)
    ergebnis = modellwahl.aufruf_schema(
        conn, klm, e, chat_id,
        system=anweisungen.hole("begriffsboard"),
        nutzer=_nutzertext(gesehen, bisher), schema=SCHEMA, art=ART,
        ueber_claude=ueber_claude,
    )
    # Geprueft wird gegen das GANZE Transkript: ein Begriff aus dem
    # weggekuerzten Anfang ist trotzdem woertlich gesagt worden.
    neu = validiere(ergebnis.get("board") if isinstance(ergebnis, dict) else None, transkript,
                    bisher=bisher)
    if not neu and bisher:
        # Ein leeres Ergebnis ersetzt nie ein volles Board. Keine Zeile, also
        # keine Markierung: die Zeichen laufen weiter auf.
        log.info("Begriffsboard-Lauf ohne Ergebnis, altes Board bleibt, chat_id=%s", chat_id)
        return
    repo.lege_begriffsboard_an(
        conn, chat_id, json.dumps(neu, ensure_ascii=False),
        "claude" if ueber_claude else "sovereign", bis_id,
    )
    try:
        speichere_automatisch(conn, e, chat_id, neu)
    except Exception:
        log.exception("Auto-Speichern der Begriffe fehlgeschlagen, chat_id=%s", chat_id)
        _vorfall(conn, e, chat_id, "begriffsboard_autosave_fehler",
                 f"Auto-Speichern der Begriffe fehlgeschlagen fuer chat_id={chat_id}")


def starte(conn, klm, e, chat_id: int, *, danach=None) -> bool:
    """Stoesst einen Boardlauf im eigenen Thread an (Zusage 2). Liefert
    True, wenn ein Lauf startete. ``danach`` laeuft nach DIESEM Lauf -- oder,
    wenn gerade schon einer laeuft, nach jenem (``nimm_oder_merke``). Ohne
    ``klm`` oder ohne Profil passiert nichts, auch ``danach`` nicht: das
    entscheidet der Aufrufer (``nach_segment``)."""
    if klm is None or not workshop.diskussion_aktiv():
        return False
    if not nimm_oder_merke(chat_id, danach):
        return False
    # VOR dem Lauf gelesen (D1): ein waehrend des Laufs neu eingetroffenes
    # Segment bleibt unreagiert und zaehlt beim naechsten Mal. Seit
    # 05.10.2026 nur bis vor das erste noch offene Segment
    # (``repo.diskussion_gelesen_bis``): was noch transkribiert wird, liest
    # dieser Lauf nicht und darf deshalb nicht als gelesen gelten.
    bis_id = repo.diskussion_gelesen_bis(conn, chat_id)

    def _lauf() -> None:
        try:
            _lauf_einmal(conn, klm, e, chat_id, bis_id)
        except Exception:
            log.exception("Begriffsboard-Lauf fehlgeschlagen, chat_id=%s", chat_id)
            _vorfall(conn, e, chat_id, "begriffsboard_fehler",
                     f"Begriffsboard-Lauf fehlgeschlagen fuer chat_id={chat_id}")
        finally:
            _rufe(([danach] if danach is not None else []) + beende(chat_id))

    try:
        threading.Thread(target=_lauf, daemon=True).start()
    except Exception:
        _rufe(([danach] if danach is not None else []) + beende(chat_id))
        raise
    return True


def oben(board: list[dict]) -> list[str]:
    """Die Top 5 nach Rang (``sortiert``), ohne verworfene -- genau die
    Begriffe, die gespeichert werden."""
    return [e["begriff"] for e in sortiert(board) if e.get("status") != "verworfen"][:TOP]


#: Der juengste Auto-Speicher-Lauf je Gruppe (``erkenner_lauf.id``) -- fuer
#: den Undo-Knopf der Abschlussnachricht. Lebt im Prozess wie der
#: Merkplatz oben; nach einem Neustart fehlt nur der Undo-Knopf.
_LETZTER_AUTOLAUF: dict[int, int] = {}


def speichere_automatisch(conn, e, chat_id: int, board: list[dict]) -> bool:
    """Auto-Speichern (Birk 05.10.2026, Live-Test Gruppe 2: vier Begriffe auf
    dem Board, aber keine ``arbeitsstand``-Zeile -- der Wechsel zu Phase 2
    war gesperrt, weil die Begriffe nur ueber "Take these" gespeichert
    wurden und der nach einem stillen Abschluss nie kam). Seitdem gilt: was
    im CoThinker steht, IST gespeichert -- die Top 5 nach Rang gehen nach
    JEDEM Boardlauf in Phase 1 nach ``arbeitsstand.begriffe``, ueber
    denselben Weg wie ein Knopf-Speichern (``erkenner.lauf_fuer_knopf``:
    Schnappschuss, Undo-faehig) samt ``schreibe_detail`` und einer
    Journalzeile. **Ohne Chatzeile** -- waehrend der Aufnahme schweigt der
    Bot; die eine sichtbare Zeile mit Undo-Knopf ist die Abschlussnachricht
    (``sende_vorschlag``).

    Nie ueber einen Wert der Gruppe hinweg: geschrieben wird nur, wenn
    ``begriffe`` leer ist oder noch genau das enthaelt, was das Board
    zuletzt selbst geschrieben hat (``begriffe_board_wert``). Hat die
    Gruppe per Chat, Knopf oder Web etwas anderes gesetzt, bleibt es stehen.
    Liefert True, wenn die Top 5 jetzt in ``begriffe`` stehen."""
    from interview_theater import erkenner, phasen  # lokal: erkenner haengt an knoepfe

    liste = oben(board)
    if not liste or phasen.aktuelle(conn, chat_id) != 1:
        return False
    wert = ", ".join(liste)
    stand = repo.hole_arbeitsstand(conn, chat_id)
    bisher = (stand["begriffe"] if stand is not None else None) or None
    vom_board = (stand["begriffe_board_wert"] if stand is not None else None) or None
    if bisher is not None and bisher != vom_board:
        return False
    if bisher == wert:
        return True

    def _schreibe() -> None:
        repo.setze_arbeitsstand(conn, chat_id, "begriffe", wert)
        repo.setze_arbeitsstand(conn, chat_id, "begriffe_board_wert", wert)
        schreibe_detail(conn, chat_id, wert)

    titel = erkenner.T._FELD_BESCHRIFTUNG["begriffe"]
    text = erkenner.T._ZEILE_FESTGELEGT.format(titel=titel, text=wert)
    lauf_id = erkenner.lauf_fuer_knopf(conn, e, chat_id, text, _schreibe)
    if lauf_id is not None:
        _LETZTER_AUTOLAUF[chat_id] = lauf_id
    repo.schreibe_journal(conn, chat_id, "entschieden", f"{titel}: {wert}", quelle="board")
    return True


def sende_vorschlag(conn, tg, chat_id: int, rueckfall_text: str | None, e=None) -> None:
    """Nach "Discussion done" (D6), bei JEDEM Diskussionsende -- es gibt
    keinen Einmal-Merker (Birk 05.10.2026: "der Bot soll weiter proaktiv
    durchfuehren", nie Stille). Liest das Board, wie es JETZT ist (nach
    einem etwaigen Schlusslauf, auch wenn der scheiterte).

    Seit dem Auto-Speichern (05.10.2026, ``speichere_automatisch``): stehen
    die Top 5 in ``begriffe``, kommt ``biete_board_gespeichert`` -- die Liste
    nach Rang, "gespeichert", EINE Frage mit zwei Knoepfen (weiter zu den
    Fragen · etwas aendern) und Undo. Hat die Gruppe selbst andere Begriffe
    gesetzt, bleibt es beim Vorschlag mit "Take these" (Birk Live-Test
    04.10.2026: dort ALLE nicht verworfenen Begriffe, die Top 5 markiert).
    Leeres Board: der Rueckfallsatz."""
    board = [e_ for e_ in sortiert(aktuelles(conn, chat_id)) if e_.get("status") != "verworfen"]
    if not board:
        if rueckfall_text:
            tg.sende(chat_id, rueckfall_text)
        return
    from interview_theater.knoepfe import basis  # Aufruf nach oben: lokal, wie im ganzen Repo

    top = oben(board)
    gespeichert = False
    try:
        gespeichert = speichere_automatisch(conn, e, chat_id, board)
    except Exception:
        log.exception("Auto-Speichern beim Diskussionsende fehlgeschlagen, chat_id=%s", chat_id)
    if gespeichert:
        basis.biete_board_gespeichert(conn, tg, chat_id, top, _LETZTER_AUTOLAUF.get(chat_id))
        # Review T3, IMPORTANT 1: diese Nachricht TRAEGT schon den
        # "Weiter zu Phase 2"-Knopf (``ART_PHASE`` mit Wert "2"), setzt aber
        # selbst keinen Merkposten -- ohne ``merke_angebot`` haette der
        # naechste Gespraechszug (``knoepfe.biete_phase_proaktiv``, derselbe
        # Merkposten wie ``kontext._baue_phasenhinweis``) denselben Wechsel
        # ein zweites Mal angeboten. Nur dieser Zweig (Auto-Speichern
        # erfolgreich): die andere Marke (``basis.biete_begriffsvorschlag``,
        # "Take these") bietet keinen Phasenwechsel an, dort entscheidet erst
        # der naechste Knopfdruck.
        phasen.merke_angebot(conn, chat_id, 2)
        return
    alle = [e_["begriff"] for e_ in board]
    basis.biete_begriffsvorschlag(conn, tg, chat_id, alle, top)


def schreibe_detail(conn, chat_id: int, begriffe_text: str | None) -> None:
    """D7: je gespeichertem Begriff die Boardzeile nach
    ``arbeitsstand.begriffe_detail``. Gerufen auf JEDEM Weg, der
    ``arbeitsstand.begriffe`` schreibt (festgenagelt in
    ``tests/test_begriffe_detail_wege.py``). Leere Begriffe leeren das
    Detail. Ohne Board (Dortmund, oder nie mitgehoert) bleibt die Spalte,
    wie sie ist -- dort entsteht kein Detail.

    **Liest den ganzen Verlauf** (``verlauf_merge``), nicht nur die juengste
    Zeile (AGG-2/R-1): sonst verliert ein gespeicherter Begriff seine
    Begruendung, sobald ein spaeterer Boardlauf ihn nicht mehr nennt."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    bisher = stand["begriffe_detail"] if stand is not None else None
    if not (begriffe_text or "").strip() or repo.letztes_begriffsboard(conn, chat_id) is None:
        if bisher:
            repo.setze_arbeitsstand(conn, chat_id, "begriffe_detail", None)
        return
    detail = detail_fuer(verlauf_merge(conn, chat_id), begriffe_text)
    repo.setze_arbeitsstand(
        conn, chat_id, "begriffe_detail", json.dumps(detail, ensure_ascii=False),
    )


def nach_segment(conn, tg, klm, e, chat_id: int, *, ist_abschluss: bool,
                 rueckfall_text: str | None = None) -> None:
    """Der Einhaengepunkt in ``aufnahme._diskussion_abschliessen``, je
    Segment. Entscheidet per Code (``soll_laufen``, EINE Regel fuer jeden
    Schnitt), ob ein Boardlauf faellig ist, und stoesst ihn im Thread an.

    ``ist_abschluss`` heisst "die Sitzung ist zu Ende": es haengt den
    Vorschlag (``sende_vorschlag``) an -- nach dem Lauf, den dieser Schnitt
    ausloest, sonst sofort, mit dem Board, wie es ist. Die Schwelle dafuer
    waehlt ``soll_laufen`` am Ende-Schnitt selbst (seit 05.10.2026: jeder
    ungelesene Rest). Laeuft beim Ende gerade ein Lauf, wird nach ihm NEU
    entschieden (derselbe Aufruf, nur spaeter): so liest am Ende immer ein
    Lauf das komplette Transkript, und der Vorschlag zeigt dessen Board.
    Ohne Profil, ohne Modell: nur der Satz."""
    if ist_abschluss and merke_falls_laeuft(chat_id, lambda: nach_segment(
            conn, tg, klm, e, chat_id, ist_abschluss=True, rueckfall_text=rueckfall_text)):
        return
    danach = None
    if ist_abschluss:
        def danach() -> None:
            sende_vorschlag(conn, tg, chat_id, rueckfall_text, e=e)

    if klm is not None and workshop.diskussion_aktiv() and soll_laufen(conn, chat_id):
        starte(conn, klm, e, chat_id, danach=danach)
        return
    if danach is not None:
        danach()


def sende_einstieg(conn, tg, e, chat_id: int) -> bool:
    """Der Einstiegssatz zum Mithoeren (D10), dort, wo der Bot den Knopf
    "Start listening" ankuendigt: beim Eintritt in Phase 1
    (``knoepfe/stationen.eintritt_in_phase``) und hinter der ersten Antwort
    einer neuen Gruppe (``ablauf.antworte``). Als Bot-Zeile mitgeschrieben,
    damit der naechste Gespraechszug ihn im Fenster sieht. Ohne Profil:
    nichts."""
    if not workshop.diskussion_aktiv():
        return False
    text = T._TEXT_EINSTIEG
    message_id = tg.sende(chat_id, text)
    repo.merke_nachricht(
        conn, chat_id, message_id, e.bot_name, 1, "text", text, repo._jetzt(),
    )
    return True
