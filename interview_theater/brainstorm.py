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
) -> bool:
    """Code-Entscheidung, kein Modellaufruf.

    ``unreagierte_zeichen``: Zeichen im Brainstorm-Transkript seit der
    letzten Karte (oder seit Beginn, wenn es noch keine gab).
    ``letzter_schnittgrund``: der Schnittgrund (``'pause'``/``'cap'``/
    ``'ende'``) des JUENGSTEN seitdem eingetroffenen Segments -- nur ein
    Pausen-Schnitt zaehlt als "die Gruppe hat gerade abgeschlossen", ein
    harter Zeitdeckel (``'cap'``) ist ein Schnitt mitten im Sprechen.
    ``ist_abschluss``: Pause/Beenden-Knopf der Gruppe -- dort reicht eine
    niedrigere Schwelle (``min_zeichen_bei_abschluss``) ohne Wartezeit und
    ohne Pausenschnitt-Bedingung, weil die Gruppe selbst gerade aufgehoert
    hat zu sprechen."""
    if ist_abschluss:
        return unreagierte_zeichen >= min_zeichen_bei_abschluss()
    return (
        unreagierte_zeichen >= min_zeichen()
        and sekunden_seit_letzter_reaktion >= min_abstand_s()
        and letzter_schnittgrund == "pause"
    )


#: Ein Sperren-Register je Nebenlaeufigkeit (AGENTS.md: "Gleicher Code,
#: verschiedene Sperren"): nie mehr als eine Buehnenkarte je Gruppe
#: gleichzeitig. Kein Merkplatz wie bei ``vorschlagssperre.py`` -- ein
#: abgewiesener Versuch verliert nichts, die unreagierten Zeichen bleiben in
#: der Datenbank stehen (repo.brainstorm_stand) und zaehlen beim naechsten
#: Segment einfach weiter mit ("pending text accumulates into the next
#: turn").
_LAEUFT_LOCK = threading.Lock()
_LAEUFT: set[int] = set()


def versuche_start(chat_id: int) -> bool:
    """True und merkt sich den Lauf, wenn fuer diese Gruppe gerade KEINE
    Buehnenkarte entsteht -- sonst False, ohne etwas zu veraendern."""
    with _LAEUFT_LOCK:
        if chat_id in _LAEUFT:
            return False
        _LAEUFT.add(chat_id)
        return True


def beende(chat_id: int) -> None:
    """Gibt die Sperre wieder frei -- immer in einem ``finally``, auch nach
    einem Fehlschlag."""
    with _LAEUFT_LOCK:
        _LAEUFT.discard(chat_id)
