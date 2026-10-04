"""Die Stationen des Abnahmelaufs Phase 1-2 als Daten (Padua-UX-Simulation,
2026-10-04): statt eines Skripts mit hartcodierten Schritten eine Liste von
Zielen, je mit ihrem eigenen Fertig-Praedikat ueber ``browser_mitschnitt.
datenstand``. Dazu die Mehrfachantwort-Regel (eine Persona bleibt im
Gespraech, solange der Bot zuletzt gefragt hat, hoechstens dreimal) und der
Notweg-Waechter (eine ausbleibende Phasenangebotszeile darf nachgeholt
werden, aber nie rueckwaerts und nie zweimal).

``p1-start`` ist seit Birks Entscheidung "Start ohne Tippen" die erste
Station: die Seite wird frisch geoeffnet, 60 Sekunden passiert nichts
(kein Tippen, kein Klick), danach liest die Ausfuehrung (ein spaeteres
Paket, hier noch nicht gebaut) vier Booleans mechanisch aus dem DOM. Diese
eine Station ruft deshalb nie die Persona -- ``ohne_persona`` und
``warte_s`` sind die zwei Felder, an denen eine Ausfuehrung das erkennt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

MAX_NACHFRAGEN = 3
HINWEIS_NACHFRAGE = "The bot just asked you something. Answer it in character."
HINWEIS_DISKUSSION_ENDE = "Your group has finished discussing. Press 'Discussion done' now."
_NICHT_GESPRAECH = ("system", "transkript")


@dataclass(frozen=True)
class Station:
    schluessel: str
    phase: int
    ziel: str                                   # englischer Zieltext fuer die Persona
    fertig: Callable[[dict], bool] | None = None   # ueber browser_mitschnitt.datenstand
    budget: int = 8
    zuhoeren_s: int = 0                         # >0: Harness wartet, solange #diskussion laeuft
    endet_bei_phasenwechsel: bool = False
    leitbild_anfang: str | None = None
    leitbild_mitte: str | None = None           # erster Bildschirm mit .leiste-Knopf bzw. waehrend des Zuhoerens
    leitbild_ende: str | None = None
    leitbild_tab: str | None = None             # Tab fuer leitbild_ende (z. B. "stand"), danach zurueck auf "chat"
    leitbild_beobachter: str | None = None      # Bild vom zweiten Geraet am Stationsende
    ohne_persona: bool = False                  # p1-start: Ausfuehrung ruft keine Persona
    warte_s: int = 0                            # p1-start: wie lange die Ausfuehrung wartet, bevor sie liest


def _feld(stand: dict, name: str):
    return (stand.get("arbeitsstand") or {}).get(name)


def muss_antworten(blasen: list[dict], beantwortet: int) -> bool:
    """Ob die Persona noch einmal auf den Bot reagieren muss, statt den
    naechsten Stationsschritt zu beginnen: nur, solange die letzte
    Gespraechsblase (System- und Transkriptzeilen zaehlen nicht) vom Bot
    kommt und mit einem Fragezeichen endet -- und hoechstens
    ``MAX_NACHFRAGEN`` Mal je Station."""
    if beantwortet >= MAX_NACHFRAGEN:
        return False
    for blase in reversed(blasen):
        if blase.get("typ") in _NICHT_GESPRAECH:
            continue
        if blase.get("von") != "bot":
            return False
        return (blase.get("text") or "").rstrip().endswith("?")
    return False


def notweg_ziel(station_phase: int, aktive_phase: int | None) -> int | None:
    """Welche Phasennummer der Notweg noch anbieten darf, wenn die Gruppe
    am Ende einer Station die naechste Phase nicht selbst angenommen hat --
    nie rueckwaerts (ist die aktive Phase schon weiter oder unbekannt, gibt
    es nichts zu tun) und nie ein zweites Mal fuer dieselbe Stufe."""
    ziel = station_phase + 1
    if aktive_phase is None or aktive_phase >= ziel:
        return None
    return ziel


STATIONEN_P12: tuple[Station, ...] = (
    Station("p1-start", 1,
            "Observe the freshly opened app for 60 seconds without typing or "
            "clicking anything, then record what is visible.",
            ohne_persona=True, warte_s=60, leitbild_ende="start"),
    Station("p1-eintritt", 1,
            "You just opened the app with your group for the first time. Read "
            "the screen, say hello, and find out what this first phase is about.",
            budget=4, leitbild_ende="eintritt"),
    Station("p1-kalibrierung", 1,
            "The app wants to check the microphone before you start. Follow the "
            "microphone check on screen: start it, let it listen, confirm. If it "
            "fails twice, skip it.",
            fertig=lambda s: s.get("kalibrierung_aufnahmen", 0) > 0
            or bool(s.get("kalibrierung_modus")),
            budget=6, leitbild_mitte="kalibrierung"),
    Station("p1-zuhoeren", 1,
            "Your group now discusses which terms matter for your play. Press "
            "'Start listening' and put the phone down in the middle of the table "
            "-- do not type the terms. When you are told the discussion is over, "
            "press 'Discussion done'.",
            fertig=lambda s: s.get("diskussion_aufnahmen", 0) > 0,
            budget=6, zuhoeren_s=180, leitbild_mitte="zuhoeren"),
    Station("p1-begriffe", 1,
            "The bot proposes terms from your discussion. Save them with the "
            "button, then undo that once with the Undo button, then save them again.",
            fertig=lambda s: bool(_feld(s, "begriffe")) and bool(_feld(s, "begriffe_detail")),
            budget=10, leitbild_beobachter="cothinker"),
    Station("p1-uebergang", 1,
            "Your terms are saved. Move on to the next phase the way the app offers it.",
            fertig=lambda s: (_feld(s, "phase") or 1) >= 2,
            budget=4, endet_bei_phasenwechsel=True, leitbild_ende="uebergang"),
    Station("p2-eigene-fragen", 2,
            "Write your own interview questions for your terms as a group, at "
            "least four, in the chat.",
            fertig=lambda s: bool(_feld(s, "fragen_eigene_vorschlag")),
            budget=10, leitbild_anfang="eintritt"),
    Station("p2-ab-vergleich", 2,
            "The app compares your questions with the AI's questions. Look at "
            "the comparison and react to it.",
            fertig=lambda s: bool(_feld(s, "fragen_ki_vorschlag")), budget=6),
    Station("p2-einzeldurchgang", 2,
            "Go through the questions one by one: accept some, drop one, rework one.",
            fertig=lambda s: bool(_feld(s, "fragen")),
            budget=14, leitbild_mitte="arbeit"),
    Station("p2-eroeffnung", 2,
            "Agree on how you open and how you close your interviews.",
            fertig=lambda s: bool(_feld(s, "interview_eroeffnung"))
            and bool(_feld(s, "interview_abschluss")),
            budget=8, leitbild_ende="ergebnis", leitbild_tab="stand"),
    Station("p2-uebergang", 2,
            "Check whether the app now offers you the next phase (interviews). "
            "Do not start an interview yet.",
            fertig=lambda s: (_feld(s, "phase_angeboten") or 0) >= 3
            or (_feld(s, "phase") or 2) >= 3,
            budget=3, leitbild_ende="uebergang"),
)

STATIONEN: dict[str, tuple[Station, ...]] = {"p12": STATIONEN_P12}
