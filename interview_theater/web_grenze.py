"""Das Rate-Limit der Weboberflaeche: wie oft eine Gruppe etwas schicken darf.

**Warum es das braucht** (Uebergabe 3 der Karte A2): wer den Gruppenlink hat,
kann beliebig viele Nachrichten und Uploads schicken. Jede Nachricht loest
einen bezahlten Modellaufruf aus, jeder Upload bis zu 8 MiB Platte und einen
bezahlten Whisper-Aufruf. Bis hier begrenzte nur ``MAX_TEXT_ZEICHEN`` und
``MAX_AUDIO_BYTES`` das EINZELNE Ereignis, nichts die Rate.

**Schluessel ist die chat_id, nicht das Token.** Eine Token-Rotation
(``scripts/web_token_neu.py``) darf das Limit nicht zuruecksetzen -- gezaehlt
wird die Gruppe, nicht die URL.

**Gleitendes Fenster, keine festen Eimer.** Ein fester Minuteneimer liesse 40
Anfragen in zwei Sekunden durch, wenn sie auf der Minutengrenze liegen. Ein
``deque`` mit Zeitstempeln kostet bei diesen Zahlen nichts: hoechstens
UPLOADS_JE_STUNDE Eintraege je Gruppe und Topf.

**Im Prozessspeicher, und ein Neustart vergisst die Zaehler.** Benannt und
akzeptiert: nginx auf herkules ist die zweite Schicht (``limit_req``, siehe
AGENTS.md), und eine Zaehltabelle in SQLite waere ein Schreibvorgang je
Anfrage in eine Datei, an der vier Bot-Prozesse haengen.

**Kein Projektimport** -- reine Standardbibliothek, wie
``vorschlagssperre.py``. Damit ist das Modul von jeder Seite importierbar und
baut nie einen Zyklus. ``tests/test_web_grenze.py`` haelt das per AST fest.
"""

import threading
import time
from collections import deque

#: Nachrichten und Knopfdruecke je Minute und Gruppe.
#:
#: Ein Topf fuer beide (Entscheidung 30.09.2026): beide loesen einen Bot-Zug
#: mit einem bezahlten Modellaufruf aus, und zwei Toepfe liessen jemanden
#: abwechseln und die Rate verdoppeln. Zwanzig in einer Minute sind fuer
#: drei bis fuenf Leute an Telefonen schon dicht getippt.
NACHRICHTEN_JE_MINUTE = 20
NACHRICHTEN_FENSTER_S = 60

#: Aufnahmesegmente je Stunde und Gruppe. War 150 (3600/45 = 80 Uploads bei
#: fester Segmentlaenge, mit Luft fuer Push-to-talk nebenher) bis zum
#: Pausen-Schnitt (VAD, 02.10.2026): die Segmentzahl haengt seitdem von der
#: Gespraechsdynamik ab, nicht von einem festen Takt. CoThinkers eigene
#: Messung (.brainstorm-vad-brief.md) zaehlt 2-5 Schnitte je MINUTE in einem
#: Brainstorm-aehnlichen Gespraech, also bis zu 300 je Stunde im
#: unruhigsten Fall. 400 haelt dieselbe Grosszuegigkeit (Luft fuer
#: Push-to-talk nebenher, weit unter dem, was ein Skript in einer Stunde
#: schafft) bei der neuen, hoeheren Messlatte.
UPLOADS_JE_STUNDE = 400
UPLOADS_FENSTER_S = 3600

TOPF_NACHRICHT = "nachricht"
TOPF_UPLOAD = "upload"

#: Nur fuer die Vorfall-Drosselung: ein Eintrag je Fenster. Steht hier und
#: nicht als zweite Buchhaltung in web_chat -- es ist genau dieselbe Frage
#: ("wie oft in einem Zeitraum"), und eine zweite Antwort darauf waere eine
#: zweite Wahrheit.
TOPF_VORFALL = "vorfall"

#: Der Start-POST beim ersten Seitenaufruf (05.10.2026, Robo): eigener Topf,
#: NICHT TOPF_NACHRICHT -- jeder Seitenaufruf/Reload schickt ihn, und im
#: geteilten 20/min-Topf frass er die Plaetze fuer Senden und Aufnahme-Start
#: (gemessen: 6 rote E2E-Tests mit 429). Er ist wirkungslos, sobald der Chat
#: eine Bot-Nachricht hat, ein grosszuegiger eigener Deckel reicht.
TOPF_START = "start"

GRENZEN = {
    TOPF_NACHRICHT: (NACHRICHTEN_JE_MINUTE, NACHRICHTEN_FENSTER_S),
    TOPF_UPLOAD: (UPLOADS_JE_STUNDE, UPLOADS_FENSTER_S),
    TOPF_VORFALL: (1, NACHRICHTEN_FENSTER_S),
    TOPF_START: (60, NACHRICHTEN_FENSTER_S),
}

_SPERRE = threading.Lock()
_ZEITEN: dict[tuple[str, int], deque] = {}


def pruefe(topf: str, schluessel: int, jetzt: float | None = None) -> int:
    """Darf diese Anfrage durch? ``0`` heisst ja (und zaehlt sie mit), sonst
    die Sekunden bis zum naechsten freien Platz (fuer ``Retry-After``).

    **Eine abgewiesene Anfrage zaehlt nicht mit.** Sonst schoebe eine Flut
    das Fenster vor sich her, und die Gruppe kaeme auch nach einer Minute
    nicht wieder hinein -- aus einem Rate-Limit waere eine Dauersperre
    geworden.

    Die Sperre umfasst Lesen, Aufraeumen und Anhaengen: ``ThreadingHTTPServer``
    bindet je Verbindung einen Thread, und ohne sie liessen 40 gleichzeitige
    Anfragen mehr als ``NACHRICHTEN_JE_MINUTE`` durch."""
    anzahl, fenster = GRENZEN[topf]
    jetzt = time.monotonic() if jetzt is None else jetzt
    with _SPERRE:
        zeiten = _ZEITEN.setdefault((topf, schluessel), deque())
        while zeiten and zeiten[0] < jetzt - fenster:
            zeiten.popleft()
        if len(zeiten) < anzahl:
            zeiten.append(jetzt)
            return 0
        return max(1, int(zeiten[0] + fenster - jetzt))


def vergiss() -> None:
    """Alle Zaehler leeren. Nur fuer Tests."""
    with _SPERRE:
        _ZEITEN.clear()
