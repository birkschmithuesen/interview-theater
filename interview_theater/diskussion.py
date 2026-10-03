"""Die EINE Verdichtung der Hintergrund-Diskussion (Phase 1, Padua Phase
1+2 Umbau, 03.10.2026).

Die Gruppe diskutiert frei im Hintergrund, waehrend das Mikrofon mitlaeuft
(``aufnahme._diskussion_abschliessen``); jedes Segment bleibt reines
Material, ohne Gespraechszug, ohne Absichtserkenner, ohne CoThinker-Karte.
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
dem Modell vorlag. Eine Zeile mit einem nicht verifizierbaren Zitat wird
verworfen, nicht geglaettet oder nachkorrigiert -- kein Retry, wie in
``zitat.py`` selbst begruendet."""

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

#: Ein woertliches Zitat in doppelten Anfuehrungszeichen -- dieselbe einfache
#: Form, die die Promptdatei verlangt (kein Markdown, kein Aufzaehlungszeichen
#: als Voraussetzung).
_ZITAT_MUSTER = re.compile(r'"([^"]+)"')


def _gefiltert(antwort: str, transkript: str) -> str:
    """Wirft jede Zeile weg, deren Zitat(e) nicht woertlich im Transkript
    stehen (``zitat.pruefe``), und behandelt eine blanke NICHTS/NOTHING-
    Antwort als leer. Eine Zeile ohne jedes Zitat bleibt unangetastet stehen
    -- es gibt hier nichts zu verifizieren, und nichts, was dagegen spraeche."""
    text = (antwort or "").strip()
    if text.strip().casefold() in _LEER:
        return ""
    zeilen = []
    for zeile in text.splitlines():
        if not zeile.strip():
            continue
        zitate = _ZITAT_MUSTER.findall(zeile)
        if zitate and not all(zitat.pruefe(z, transkript) for z in zitate):
            continue
        zeilen.append(zeile)
    return "\n".join(zeilen).strip()


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
            text = _gefiltert(ergebnis.get("antwort", ""), transkript)
            if text:
                repo.merke_diskussion_verdichtung(
                    conn, chat_id, text, "claude" if ueber_claude else "sovereign",
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
