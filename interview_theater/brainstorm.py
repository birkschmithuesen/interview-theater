"""Die Reaktionsschwelle fuer den Brainstorm-Modus (Phase 4, nur Web).

Reine Funktionen, kein Modellaufruf, kein SQL -- die EINE Stelle, die
entscheidet, ob JETZT eine Buehnenkarte entstehen soll (Zusage 2 bleibt
unberuehrt: das hier entscheidet nur OB, nie WAS die Karte sagt).

Herkunft der Zahlen: Betreiber-Entscheidung 02.10.2026
(``.brainstorm-vad-brief.md``), CoThinker-Referenzannotationen (3 Sitzungen,
117 Gedanken, 53 Themen, gemessen 02.10.2026): ein Gedanke ist median 50 s /
614 Zeichen (p25-p75 250-1451), ein Thema median 154 s / 1868 Zeichen,
Sprechtempo ~16 Zeichen/s. 1200 Zeichen ~ zwei Gedanken ~ 75 s Sprechzeit ->
eine Karte etwa alle 1,5-2,5 min, ungefaehr einmal je Themenbogen. Die Daten
stammen aus Erwachsenen-Meetings, NICHT aus Schueler-Brainstorms -- deshalb
bleiben alle Schwellen ueber die Umgebung nachjustierbar.
"""

import os
import threading
from datetime import datetime, timezone

VORGABE_MIN_ZEICHEN = 1200
VORGABE_MIN_ABSTAND_S = 90
VORGABE_MIN_ZEICHEN_BEI_ABSCHLUSS = 150


def _umgebungszahl(name: str, vorgabe: int) -> int:
    roh = (os.environ.get(name) or "").strip()
    if not roh:
        return vorgabe
    try:
        wert = int(roh)
    except ValueError:
        return vorgabe
    return wert if wert > 0 else vorgabe


def min_zeichen() -> int:
    return _umgebungszahl("IT_BRAINSTORM_MIN_ZEICHEN", VORGABE_MIN_ZEICHEN)


def min_abstand_s() -> int:
    return _umgebungszahl("IT_BRAINSTORM_MIN_ABSTAND_S", VORGABE_MIN_ABSTAND_S)


def min_zeichen_bei_abschluss() -> int:
    return _umgebungszahl(
        "IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS",
        VORGABE_MIN_ZEICHEN_BEI_ABSCHLUSS,
    )


def soll_reagieren(
    *, unreagierte_zeichen: int, sekunden_seit_letzter_reaktion: float,
    letzter_schnittgrund: str | None, ist_abschluss: bool,
    min_zeichen_override: int | None = None,
    min_abstand_override: int | None = None,
) -> bool:
    """Code-Entscheidung, kein Modellaufruf.

    ``unreagierte_zeichen``: Zeichen im Brainstorm-Transkript seit der
    letzten Karte (oder seit Beginn, wenn es noch keine gab).
    ``letzter_schnittgrund``: der Schnittgrund (``'pause'``/``'cap'``/
    ``'ende'``/``'weich'``) des JUENGSTEN seitdem eingetroffenen Segments --
    nur ein Pausen- oder Weich-Schnitt zaehlt als "die Gruppe hat gerade
    abgeschlossen", ein harter Zeitdeckel (``'cap'``) ist ein Schnitt mitten
    im Sprechen. ``'weich'`` (Padua VAD: weicher Schnitt, 05.10.2026) ist
    dieselbe natuerliche Sprechpause wie ``'pause'``, nur an einer kuerzeren
    Stille erkannt.
    ``ist_abschluss``: Pause/Beenden-Knopf der Gruppe -- dort reicht eine
    niedrigere Schwelle (``min_zeichen_bei_abschluss``) ohne Wartezeit und
    ohne Pausenschnitt-Bedingung, weil die Gruppe selbst gerade aufgehoert
    hat zu sprechen.
    ``min_zeichen_override``: Birk Live-Test 04.10.2026 -- das Begriffsboard
    (Phase 1) braucht eine eigene, niedrigere Schwelle als der Brainstorm
    (Phase 4): beide teilen sich diese Funktion, aber ein Testgespraech in
    Phase 1 ist kuerzer als eine echte Brainstorm-Sitzung. ``None`` heisst
    unveraendert ``min_zeichen()``.
    ``min_abstand_override``: dasselbe fuer den Mindestabstand (Birk
    05.10.2026, Phase 1 wartet 20 s statt 90 s, ``begriffsboard.min_abstand_s``).
    ``None`` heisst unveraendert ``min_abstand_s()`` -- der Brainstorm bleibt,
    wie er war."""
    if ist_abschluss:
        return unreagierte_zeichen >= min_zeichen_bei_abschluss()
    return (
        unreagierte_zeichen >= (min_zeichen_override if min_zeichen_override is not None else min_zeichen())
        and sekunden_seit_letzter_reaktion >= (
            min_abstand_override if min_abstand_override is not None else min_abstand_s())
        and letzter_schnittgrund in ("pause", "weich")
    )


#: Ein Sperren-Register je Nebenlaeufigkeit (docs/agents/aufbau.md: "Gleicher Code,
#: verschiedene Sperren"): nie mehr als eine Buehnenkarte je Gruppe
#: gleichzeitig. Kein Merkplatz wie bei ``vorschlagssperre.py`` -- ein
#: abgewiesener Versuch verliert nichts, die unreagierten Zeichen bleiben in
#: der Datenbank stehen (repo.brainstorm_stand) und zaehlen beim naechsten
#: Segment einfach weiter mit ("pending text accumulates into the next
#: turn").
_LAEUFT_LOCK = threading.Lock()
_LAEUFT: dict[int, str] = {}


def versuche_start(chat_id: int) -> bool:
    """True und merkt sich den Lauf, wenn fuer diese Gruppe gerade KEINE
    Buehnenkarte entsteht -- sonst False, ohne etwas zu veraendern."""
    with _LAEUFT_LOCK:
        if chat_id in _LAEUFT:
            return False
        _LAEUFT[chat_id] = datetime.now(timezone.utc).isoformat()
        return True


def beende(chat_id: int) -> None:
    """Gibt die Sperre wieder frei -- immer in einem ``finally``, auch nach
    einem Fehlschlag."""
    with _LAEUFT_LOCK:
        _LAEUFT.pop(chat_id, None)


def laeuft(chat_id: int) -> bool:
    """Oeffentliche Lesefunktion: laeuft fuer diese Gruppe gerade ein
    Buehnenkarten-Versuch (innerhalb DIESES Prozesses)? Im echten Betrieb
    (Bot und Webserver als getrennte Prozesse) ist das NICHT der Kanal,
    ueber den der Webserver das erfaehrt -- siehe
    arbeitsstand.brainstorm_lauf_seit (db.py/repo.py) fuer den
    Prozess-uebergreifenden Weg."""
    with _LAEUFT_LOCK:
        return chat_id in _LAEUFT
