"""Die EINE Verdichtung der Hintergrund-Diskussion (Phase 1, Padua Phase
1+2 Umbau, 03.10.2026).

Die Gruppe diskutiert frei im Hintergrund, waehrend das Mikrofon mitlaeuft
(``aufnahme._diskussion_abschliessen``); jedes Segment bleibt reines
Material, ohne Gespraechszug und ohne Absichtserkenner; laufend schreibt nur
das Begriffsboard mit (``begriffsboard.py``, Karte t_4517d4ad).
Erst wenn die Diskussion endet (``schnittgrund == 'ende'``), laeuft genau
EIN Schema-Aufruf ueber das ganze zusammengefuegte Transkript und destilliert
daraus, was Phase 2 (Fragenentwicklung) und Phase 4+ (Geschichte) spaeter
brauchen koennen -- siehe ``prompts/diskussion_verdichtung.md``.

**Genau einmal, auch bei einem Doppelklick oder einem Nachzuegler-Segment,
das denselben Abschlusspfad noch einmal ausloest** -- dieselbe Sperrenform
wie ``brainstorm.py`` (``versuche_start``/``beende``), hier bewusst noch
einmal geschrieben statt importiert: eine gemeinsame Sperre wuerde Diskussion
(Phase 1) und Brainstorm (Phase 4) aneinanderketten, obwohl die beiden nie
gleichzeitig eine Gruppe betreffen (AGENTS.md: "Gleicher Code, verschiedene
Sperren").

**Der Nutzertext ist bewusst isoliert** (``_nutzertext``): er nimmt nur das
Transkript entgegen, keine ``conn``, keine ``chat_id`` -- dieser Aufruf darf
nichts anderes aus der Datenbank sehen als das, was tatsaechlich im Raum
gesagt wurde, kein ``kontext.baue``, kein Arbeitsstand.

**Derselbe Zitatschutz wie ueberall sonst** (Verdichter, Kernzitate,
Schaerfung, Dramaturgie): ``zitat.pruefe`` gegen genau das Transkript, das
dem Modell vorlag. Ein nicht verifizierbares Zitat wird aus seiner Zeile
genommen (seit 05.10.2026; vorher fiel die ganze Zeile), nicht geglaettet
oder nachkorrigiert -- kein Retry, wie in ``zitat.py`` selbst begruendet.
Bleibt am Ende nichts, steht ein Vorfall ``diskussion_verdichtung_leer``."""

import logging
import re
import threading

from interview_theater import anweisungen, modellwahl, repo, workshop, zitat

log = logging.getLogger(__name__)

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften, sonst lehnt der Anbieter den erzwungenen Modus ab
#: (global-constraints.md).
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["antwort"],
    "properties": {
        "antwort": {"type": "string"},
    },
}

ART = "diskussion_verdichtung"

#: Obergrenze der Antwort in Woertern -- im Prompttext ("hoechstens 150
#: Woerter") UND hier, damit ``scripts/pruefe_prompts.py`` sie spaeter
#: mechanisch nachzaehlen kann (wie ``verdichter.KURZ_MAX_WOERTER``). Nicht
#: durchgesetzt: eine zu lange Antwort ist eine unschoene Notiz, kein Grund,
#: ein belegtes Ergebnis wegzuwerfen.
WORT_GRENZE = 150

#: Sentinel-Antworten fuer "nichts Brauchbares" -- deutsch (``NICHTS``) und
#: englisch (``NOTHING``); ``none`` zusaetzlich, falls ein Modell die
#: englische Few-Shot-Sprache der eigenen Trainingsdaten durchmischt. Case-
#: und whitespace-unempfindlich verglichen.
_LEER = {"nichts", "none", "nothing"}

#: Ein woertliches Zitat in Anfuehrungszeichen -- gerade (die Form, die die
#: Promptdatei verlangt) oder typografisch (Opus setzt sie gern selbst).
#: Ohne die typografischen Formen bliebe ein solches Zitat ungeprueft stehen.
_ZITAT_MUSTER = re.compile(r'"([^"]+)"|“([^”]+)”|„([^“”]+)[“”]')

#: Was nach dem Herausnehmen eines Zitats an Satzresten stehen bleibt: eine
#: leere Klammer, ein haengender Doppelpunkt vor dem Satzende, doppelter
#: Leerraum.
_REST_KLAMMER = re.compile(r"\(\s*[,;:]?\s*\)")
_REST_LEERRAUM = re.compile(r"[ \t]{2,}")
_REST_VOR_ZEICHEN = re.compile(r"\s+([,.;:!?)])")
#: Unter so vielen Buchstaben ist von einer Zeile nach dem Herausnehmen nur
#: ein Fragment uebrig ("as in", "--") -- dann faellt sie weg.
_REST_MINDEST_BUCHSTABEN = 12


def _zitate(treffer: re.Match) -> str:
    return next(g for g in treffer.groups() if g is not None)


def _ohne_zitat(zeile: str, treffer: re.Match) -> str:
    """Die Zeile ohne dieses eine Zitat samt seinen Anfuehrungszeichen."""
    rest = zeile[:treffer.start()] + zeile[treffer.end():]
    rest = _REST_KLAMMER.sub("", rest)
    rest = _REST_LEERRAUM.sub(" ", rest)
    rest = _REST_VOR_ZEICHEN.sub(r"\1", rest)
    rest = re.sub(r"[:,]\s*([.;!?])", r"\1", rest)
    return rest.strip()


def _filtere(antwort: str, transkript: str) -> tuple[str, dict]:
    """Die Zitatwache mit Zaehlung -- ``(text, zahlen)``.

    Eine blanke NICHTS/NOTHING-Antwort ist leer. Sonst wird jedes Zitat, das
    nicht woertlich im Transkript steht (``zitat.pruefe``), **aus der Zeile
    genommen** -- die Aussage daneben bleibt stehen (Birk, 05.10.2026: die
    Verdichtung ist ein Absatz, also EINE Zeile, und ein einziges verhoertes
    Zitat warf bis dahin die ganze Verdichtung weg; live: 0 gespeicherte
    Verdichtungen bei erfolgreichem Aufruf). Das Prinzip bleibt: kein
    unbestaetigtes Zitat wird je gespeichert, geglaettet oder nachkorrigiert.

    ``zahlen`` traegt nur Zahlen, nie Inhalt (Log und Vorfall)."""
    text = (antwort or "").strip()
    zahlen = {
        "zeichen": len(text), "zeilen": 0, "zitate": 0,
        "zitate_verworfen": 0, "zeilen_verworfen": 0, "nichts": False,
    }
    if text.casefold() in _LEER:
        zahlen["nichts"] = True
        return "", zahlen
    zeilen = []
    for zeile in text.splitlines():
        if not zeile.strip():
            continue
        zahlen["zeilen"] += 1
        treffer = list(_ZITAT_MUSTER.finditer(zeile))
        zahlen["zitate"] += len(treffer)
        geaendert = False
        # Von hinten nach vorn, damit die Positionen der vorderen Treffer
        # beim Herausschneiden gueltig bleiben.
        for t in reversed(treffer):
            if zitat.pruefe(_zitate(t), transkript):
                continue
            zeile = _ohne_zitat(zeile, t)
            zahlen["zitate_verworfen"] += 1
            geaendert = True
        if geaendert and len(re.findall(r"[^\W\d_]", zeile)) < _REST_MINDEST_BUCHSTABEN:
            zahlen["zeilen_verworfen"] += 1
            continue
        zeilen.append(zeile)
    return "\n".join(zeilen).strip(), zahlen


def _gefiltert(antwort: str, transkript: str) -> str:
    """Der gefilterte Text allein -- siehe ``_filtere``."""
    return _filtere(antwort, transkript)[0]


def _nutzertext(transkript: str) -> str:
    """Der isolierte Nutzertext -- NUR das Transkript. Kein ``conn``, keine
    ``chat_id`` in der Signatur: dieser Aufruf kann strukturell nichts
    anderes sehen."""
    return f"Das Transkript der Diskussion:\n{transkript}"


#: Ein Sperren-Register je Nebenlaeufigkeit (AGENTS.md: "Gleicher Code,
#: verschiedene Sperren"), in Form kopiert aus ``brainstorm.py``: nie mehr
#: als ein Verdichtungslauf je Gruppe gleichzeitig.
_LAEUFT_LOCK = threading.Lock()
_LAEUFT: set[int] = set()


def versuche_start(chat_id: int) -> bool:
    """True und merkt sich den Lauf, wenn fuer diese Gruppe gerade KEINE
    Diskussionsverdichtung laeuft -- sonst False, ohne etwas zu veraendern."""
    with _LAEUFT_LOCK:
        if chat_id in _LAEUFT:
            return False
        _LAEUFT.add(chat_id)
        return True


def beende(chat_id: int) -> None:
    """Gibt die Sperre wieder frei -- immer in einem ``finally``, auch nach
    einem Fehlschlag oder einem fruehen Abbruch vor dem Thread-Start."""
    with _LAEUFT_LOCK:
        _LAEUFT.discard(chat_id)


def starte(conn, tg, klm, e, chat_id: int) -> None:
    """Stoesst den einen Verdichtungslauf der Hintergrund-Diskussion an.

    ``tg`` wird hier (noch) nicht gebraucht -- die Signatur bleibt trotzdem
    gleichfoermig mit dem verwandten Modul fuer Phase 2 (eigene-vs-KI-Fragen),
    das die fertige Verdichtung spaeter per Chatnachricht ankuendigt.

    Kein Modellaufruf hier selbst (Zusage 2): der eigentliche Aufruf laeuft
    in einem eigenen Thread. Diese Funktion prueft nur, ob ueberhaupt etwas
    zu tun ist, und gibt die Sperre selbst zurueck, wenn sie es doch nicht
    ist -- sonst gaebe niemand sie je wieder frei."""
    if klm is None:
        return
    if not workshop.diskussion_aktiv():
        return
    if not versuche_start(chat_id):
        return

    transkript = repo.diskussion_transkript(conn, chat_id)
    if not transkript.strip():
        # Kein Modellaufruf auf leerem Material (N2-Grundsatz): die Sperre
        # muss trotzdem zurueck, sonst bleibt diese Gruppe fuer immer
        # "laeuft gerade" stehen.
        beende(chat_id)
        return

    def _lauf() -> None:
        try:
            nutzertext = _nutzertext(transkript)
            ueber_claude = modellwahl.konversation_ueber_claude(e, conn, chat_id)
            ergebnis = modellwahl.aufruf_schema(
                conn, klm, e, chat_id,
                system=anweisungen.hole("diskussion_verdichtung"),
                nutzer=nutzertext, schema=SCHEMA, art=ART,
                ueber_claude=ueber_claude,
            )
            text, zahlen = _filtere(ergebnis.get("antwort", ""), transkript)
            # Nur Zahlen ins Log, nie Inhalt: die Antwort zitiert die Gruppe.
            log.info(
                "Diskussionsverdichtung chat_id=%s: %s Zeichen, %s Zeilen, "
                "%s Zitate (%s verworfen), %s Zeilen verworfen, NOTHING=%s, "
                "gespeichert=%s", chat_id, zahlen["zeichen"], zahlen["zeilen"],
                zahlen["zitate"], zahlen["zitate_verworfen"],
                zahlen["zeilen_verworfen"], zahlen["nichts"], bool(text),
            )
            if text:
                repo.merke_diskussion_verdichtung(
                    conn, chat_id, text, "claude" if ueber_claude else "sovereign",
                )
            else:
                repo.merke_vorfall(
                    conn, chat_id, getattr(e, "bot_name", None),
                    "diskussion_verdichtung_leer",
                    "Diskussionsverdichtung ohne Ergebnis: "
                    f"{'NOTHING' if zahlen['nichts'] else 'alles verworfen'}, "
                    f"{zahlen['zeichen']} Zeichen, {zahlen['zeilen']} Zeilen, "
                    f"{zahlen['zitate_verworfen']}/{zahlen['zitate']} Zitate verworfen, "
                    f"Transkript {len(transkript)} Zeichen",
                )
        except Exception:
            log.exception("Diskussionsverdichtung fehlgeschlagen, chat_id=%s", chat_id)
            try:
                repo.merke_vorfall(
                    conn, chat_id, getattr(e, "bot_name", None),
                    "diskussion_verdichtung_fehler",
                    f"Diskussionsverdichtung fehlgeschlagen fuer chat_id={chat_id}",
                )
            except Exception:
                log.exception(
                    "Vorfall diskussion_verdichtung_fehler nicht geschrieben, chat_id=%s",
                    chat_id,
                )
        finally:
            beende(chat_id)

    threading.Thread(target=_lauf, daemon=True).start()
