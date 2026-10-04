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
import logging
import os
import re
import threading

from interview_theater import anweisungen, brainstorm, modellwahl, repo, workshop
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


_FELDER = ("begriff", "nennungen", "zustimmung", "begruendung", "zitat",
           "doppelbedeutung", "status")

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften, sonst lehnt der Anbieter den erzwungenen Modus ab
#: (Kommentar an ``diskussion.SCHEMA``). Die Wurzel ist ein Objekt, weil der
#: Schema-Modus keine Liste als Wurzel nimmt; ``board`` statt ``begriffe``,
#: weil ``scripts/pruefe_sprache.py`` "begriffe" als deutsches Wort fuehrt.
#: ``status`` ist bewusst ein freier String: ``validiere`` macht aus jedem
#: unbekannten Wert "kandidat".
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
                },
            },
        },
    },
}

ART = "begriffsboard"

VORGABE_TRANSKRIPT_ZEICHEN = 200_000

#: Eigene, niedrigere Schwelle als der Brainstorm (Phase 4): ein Testgespraech
#: in Phase 1 ist kuerzer als eine echte Brainstorm-Sitzung (Birk Live-Test
#: 04.10.2026: 1200 Zeichen liess das Board zu lange leer stehen).
VORGABE_MIN_ZEICHEN = 600


def min_zeichen() -> int:
    """``IT_BEGRIFFSBOARD_MIN_ZEICHEN`` -- dasselbe Muster wie
    ``transkript_zeichen_grenze``/``brainstorm.min_zeichen``."""
    roh = (os.environ.get("IT_BEGRIFFSBOARD_MIN_ZEICHEN") or "").strip()
    if roh.isdigit() and int(roh) > 0:
        return int(roh)
    return VORGABE_MIN_ZEICHEN


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


def soll_laufen(conn, chat_id: int, *, ist_abschluss: bool) -> bool:
    """D1: ``brainstorm.soll_reagieren`` unveraendert, mit den eigenen Zahlen
    der Phase 1 (``repo.begriffsboard_stand``) UND der eigenen, niedrigeren
    Zeichenschwelle (``min_zeichen`` oben). Kein Modellaufruf."""
    stand = repo.begriffsboard_stand(conn, chat_id)
    sekunden = stand["sekunden_seit_letztem_lauf"]
    return brainstorm.soll_reagieren(
        unreagierte_zeichen=stand["unreagierte_zeichen"],
        sekunden_seit_letzter_reaktion=sekunden if sekunden is not None else float("inf"),
        letzter_schnittgrund=stand["letzter_schnittgrund"],
        ist_abschluss=ist_abschluss,
        min_zeichen_override=min_zeichen(),
    )


#: Ein Sperren-Register je Nebenlaeufigkeit (AGENTS.md: "Gleicher Code,
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
    neu = validiere(ergebnis.get("board") if isinstance(ergebnis, dict) else None, transkript)
    if not neu and bisher:
        # Ein leeres Ergebnis ersetzt nie ein volles Board. Keine Zeile, also
        # keine Markierung: die Zeichen laufen weiter auf.
        log.info("Begriffsboard-Lauf ohne Ergebnis, altes Board bleibt, chat_id=%s", chat_id)
        return
    repo.lege_begriffsboard_an(
        conn, chat_id, json.dumps(neu, ensure_ascii=False),
        "claude" if ueber_claude else "sovereign", bis_id,
    )


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
    # Segment bleibt unreagiert und zaehlt beim naechsten Mal.
    bis_id = repo.hoechste_diskussion_aufnahme_id(conn, chat_id)

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


def sende_vorschlag(conn, tg, chat_id: int, rueckfall_text: str | None) -> None:
    """Nach "Discussion done" (D6): stehen nicht verworfene Begriffe auf dem
    Board, ALLE in der Liste und die Top 5 markiert, dazu EIN Knopf
    "Take these" fuer die Top 5 -- sonst der bisherige Satz unveraendert.
    Liest das Board, wie es JETZT ist (nach einem etwaigen Schlusslauf, auch
    wenn der scheiterte).

    Birk Live-Test 04.10.2026: vorher bekam die Gruppe NUR die Top 5 zu
    sehen -- neu genannte Begriffe mit noch niedriger Zustimmung/Nennungen
    fielen dadurch komplett aus der Anzeige, auch wenn sie frisch gesagt
    wurden. Jetzt zeigt die Liste alle, markiert nur die Auswahl."""
    board = [e for e in sortiert(aktuelles(conn, chat_id)) if e.get("status") != "verworfen"]
    if not board:
        if rueckfall_text:
            tg.sende(chat_id, rueckfall_text)
        return
    alle = [e["begriff"] for e in board]
    oben = [e["begriff"] for e in board[:TOP]]
    from interview_theater.knoepfe import basis  # Aufruf nach oben: lokal, wie im ganzen Repo

    basis.biete_begriffsvorschlag(conn, tg, chat_id, alle, oben)


def schreibe_detail(conn, chat_id: int, begriffe_text: str | None) -> None:
    """D7: je gespeichertem Begriff die Boardzeile nach
    ``arbeitsstand.begriffe_detail``. Gerufen auf JEDEM Weg, der
    ``arbeitsstand.begriffe`` schreibt (festgenagelt in
    ``tests/test_begriffe_detail_wege.py``). Leere Begriffe leeren das
    Detail. Ohne Board (Dortmund, oder nie mitgehoert) bleibt die Spalte,
    wie sie ist -- dort entsteht kein Detail."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    bisher = stand["begriffe_detail"] if stand is not None else None
    zeile = repo.letztes_begriffsboard(conn, chat_id)
    if not (begriffe_text or "").strip() or zeile is None:
        if bisher:
            repo.setze_arbeitsstand(conn, chat_id, "begriffe_detail", None)
        return
    detail = detail_fuer(lies(zeile["json"]), begriffe_text)
    repo.setze_arbeitsstand(
        conn, chat_id, "begriffe_detail", json.dumps(detail, ensure_ascii=False),
    )


def nach_segment(conn, tg, klm, e, chat_id: int, *, ist_abschluss: bool,
                 rueckfall_text: str | None = None) -> None:
    """Der Einhaengepunkt in ``aufnahme._diskussion_abschliessen``, je
    Segment. Entscheidet per Code (D1), ob ein Boardlauf faellig ist, und
    stoesst ihn im Thread an. Beim Abschluss-Segment (``ist_abschluss``)
    kommt danach der Vorschlag (D6): nach dem Schlusslauf, oder sofort,
    wenn keiner noetig ist. Ohne Profil, ohne Modell: nur der Satz, wie
    bisher."""
    danach = None
    if ist_abschluss:
        def danach() -> None:
            sende_vorschlag(conn, tg, chat_id, rueckfall_text)

    if (klm is None or not workshop.diskussion_aktiv()
            or not soll_laufen(conn, chat_id, ist_abschluss=ist_abschluss)):
        if danach is not None:
            danach()
        return
    starte(conn, klm, e, chat_id, danach=danach)


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
