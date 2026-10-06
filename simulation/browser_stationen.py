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

Seit Karte t_fc2c1bfa (05.10.2026) gibt es zwei Listen (``STATIONEN``):
``STATIONEN_P12`` (die Phasen-Abnahme) und ``STATIONEN_INVARIANTEN`` (das
kleinste Set, das jede deterministische Pruefung aus
``browser_invarianten`` einmal durchlaeuft). ``PRUEFUNGEN`` nennt die
erlaubten Namen der Pruef-Haken (``browser_pruefhaken.HAKEN``). Neue
``Station``-Felder dafuer: ``pruefung`` (welche Haken nach der Station
laufen), ``diskussion`` (gesprochenes Skript aus
``diskussionen.DISKUSSIONEN`` statt freier Rede; ``zuhoeren_s=None`` heisst
Zuhoerdauer aus der WAV), ``sage`` (Text, den der Harness selbst schickt)
und ``gruppe`` (welche Gruppe im Mehrgruppen-Lauf die Station spielt).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from simulation import browser_aktionen
from simulation import browser_invarianten as _inv

MAX_NACHFRAGEN = 3
HINWEIS_NACHFRAGE = "The bot just asked you something. Answer it in character."
HINWEIS_DISKUSSION_ENDE = "Your group has finished discussing. Press 'Discussion done' now."
_NICHT_GESPRAECH = ("system", "transkript")

#: Welche deterministischen Pruefungen (browser_invarianten) eine Station
#: nach ihrem Ende durchlaufen soll -- Werte stehen in ``Station.pruefung``.
#: Die P5-7-Namen (ab ``p5_schaerfung``) bekommen ihren Haken erst in Task 3
#: (``browser_pruefhaken.HAKEN``) bzw. Task 7 (``kuerzung``, ``formen``,
#: ``textbuch``, ``modellwahl57``, ``sprache57``) -- bis dahin meldet
#: ``browser_pruefhaken.fuehre_pruefungen`` fuer einen Namen ohne Haken einen
#: Befund (``pruefung_unbekannt:<name>``) statt abzustuerzen, kein stilles
#: Grün.
PRUEFUNGEN = ("nach_ende", "wissen", "raumcheck", "zweite_gruppe", "verhoerer", "p2_werkbank",
              "nach_interview", "nach_brainstorm", "modellwahl", "p5_angebot", "pause_resume",
              "p5_schaerfung", "p5_uebersicht", "prueflauf", "chat_volltext", "sprung",
              "kuerzung", "formen", "stueckpruefung", "textbuch", "modellwahl57", "sprache57")

#: Je Aufnahmeart: woran der Harness "laeuft" erkennt und was er zum Beenden
#: drueckt. Brainstorm war unter t_cf87ee0a (Task 5, bis 05.10.2026) ein
#: eigener Toggle-Knopf (``#brainstorm``, derselbe Knopf beendet) -- Birk hat
#: das 05.10.2026 22:00 verworfen: **kein Toggle seit 05.10. 22:00**. Phase 4
#: bedient sich seitdem ueber genau denselben Knopf wie die Diskussion der
#: Phase 1 (``#diskussion``/``#diskussion-beenden``, kontinuierliches
#: Zuhoeren mit VAD-Pausenschnitten statt eines einzigen Bogens) -- der
#: Stationstyp "brainstorm" bleibt eigenstaendig (``Station.aufnahme``, die
#: Pruef-Haken), nur die Selektoren sind jetzt identisch mit "diskussion".
LAEUFT = {"diskussion": '#diskussion[data-laeuft="1"]',
          "interview": '#interview[data-laeuft="1"]',
          "brainstorm": '#diskussion[data-laeuft="1"]'}
ENDE = {"diskussion": "#diskussion-beenden",
        "interview": "#interview-beenden",
        "brainstorm": "#diskussion-beenden"}
#: Derselbe Umschalter-Knopf je Aufnahmeart (erster Klick pausiert, zweiter
#: setzt fort) -- Grundlage von ``browser_lauf._pausiere_und_fortsetze_aufnahme``
#: (Coverage-Luecke Pause/Resume, p34-abnahme-verfahren.md §3).
PAUSE = {"diskussion": "#diskussion-pause",
         "interview": "#interview-pause",
         "brainstorm": "#diskussion-pause"}


@dataclass(frozen=True)
class Station:
    schluessel: str
    phase: int
    ziel: str                                   # englischer Zieltext fuer die Persona
    fertig: Callable[[dict], bool] | None = None   # ueber browser_mitschnitt.datenstand
    budget: int = 8
    zuhoeren_s: int | None = 0                  # >0: Harness wartet, solange #diskussion laeuft; None: aus der WAV-Dauer (Task 6)
    endet_bei_phasenwechsel: bool = False
    leitbild_anfang: str | None = None
    leitbild_mitte: str | None = None           # erster Bildschirm mit .leiste-Knopf bzw. waehrend des Zuhoerens
    leitbild_ende: str | None = None
    leitbild_tab: str | None = None             # Tab fuer leitbild_ende (z. B. "stand"), danach zurueck auf "chat"
    leitbild_beobachter: str | None = None      # Bild vom zweiten Geraet am Stationsende
    ohne_persona: bool = False                  # p1-start: Ausfuehrung ruft keine Persona
    warte_s: int = 0                            # p1-start: wie lange die Ausfuehrung wartet, bevor sie liest
    diskussion: str | None = None               # Schluessel in diskussionen.DISKUSSIONEN: gesprochenes Skript statt freier Rede
    pruefung: tuple[str, ...] = ()              # Werte aus PRUEFUNGEN, die nach dieser Station laufen
    sage: str | None = None                     # Text, den der Harness selbst schickt (Station ohne Persona)
    gruppe: int = 1                             # welches Geraet/welche Gruppe im Mehrgruppen-Lauf diese Station spielt
    aufnahme: str = "diskussion"                # welcher Rekorder das Skript aus `diskussion` abspielt (LAEUFT/ENDE)
    #: Coverage-Luecke Pause/Resume (p34-abnahme-verfahren.md §3): der
    #: Harness pausiert/setzt waehrend ``zuhoeren_s`` einmal deterministisch
    #: fort (``browser_lauf._pausiere_und_fortsetze_aufnahme``), unabhaengig
    #: davon, ob die Persona selbst daran denkt -- geprueft per
    #: ``pause_resume`` in ``Station.pruefung``.
    pause_resume: bool = False
    #: Task 2 (BRIEF p57): wie lange ``browser_aktionen.warte_auf_antwort``
    #: UND ``browser_lauf._warte_bis`` (unten) hoechstens je Aktion warten --
    #: Vorgabe ``ANTWORT_GEDULD_S`` (90s), P5-7-Stationen setzen 600s
    #: (Fakt 1/5, Plan): ein Szenenlauf mit Reasoning oder ein Prueflauf mit
    #: zwei Runden braucht laenger als die alte 90s-Geduld, und zeigt dabei
    #: unter Umstaenden gar kein ``#tippt``/``.blase.vorlaeufig`` (gemessen
    #: per Code-Audit, nicht per Playwright-Lauf gegen ein echtes Modell --
    #: ``grep -n tippt interview_theater/szene.py interview_theater/
    #: prueflauf.py interview_theater/ueberarbeitung.py interview_theater/
    #: nachpass.py`` zeigt KEINEN Aufruf von ``tg.tippt``/``kanal.tippt`` in
    #: einem dieser Module; einzige Aufrufstelle ist ``ablauf.py`` Zeile 614,
    #: im normalen Gespraechszug. ``#tippt`` kann also waehrend eines dieser
    #: Hintergrund-Threads gar nicht gesetzt sein -- ``warte_bis`` ist
    #: deshalb kein Komfort, sondern der einzige Weg, wie der Harness das
    #: Ende eines solchen Laufs ueberhaupt bemerkt).
    geduld_s: float = browser_aktionen.ANTWORT_GEDULD_S
    #: Task 2: nach JEDER Aktion pollt der Harness ``browser_mitschnitt.
    #: datenstand`` gegen dieses Praedikat, hoechstens ``geduld_s`` lang
    #: (``browser_lauf._warte_bis``) -- fuer Stationen, deren Fortschritt
    #: sich nicht ueber ``#tippt``/``.blase.vorlaeufig`` zeigt. ``None``
    #: (Vorgabe) heisst: kein zusaetzliches Warten, wie bisher.
    warte_bis: Callable[[dict], bool] | None = None


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
            "The app wants to check the room before you start. Get through the "
            "room check; if it fails twice, skip it.",
            fertig=lambda s: s.get("kalibrierung_aufnahmen", 0) > 0
            or bool(s.get("kalibrierung_modus")),
            budget=10, leitbild_mitte="kalibrierung"),
    Station("p1-zuhoeren", 1,
            "Your group now discusses which terms matter for your play. Press "
            "'Start listening' and put the phone down in the middle of the table "
            "-- do not type the terms. When you are told the discussion is over, "
            "press 'Discussion done'.",
            fertig=lambda s: s.get("diskussion_aufnahmen", 0) > 0,
            budget=6, zuhoeren_s=180, leitbild_mitte="zuhoeren", pruefung=("nach_ende",)),
    Station("p1-begriffe", 1,
            "Get the terms from your discussion into the workbench and move on "
            "to the next phase.",
            fertig=lambda s: bool(_feld(s, "begriffe")) and bool(_feld(s, "begriffe_detail")),
            budget=10, leitbild_beobachter="cothinker", pruefung=()),
    Station("p1-uebergang", 1,
            "Move on to the next phase once your terms are in place.",
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
            "Make sure the question list for your interviews is the one your "
            "group wants, then check it in the workbench.",
            fertig=lambda s: bool(_feld(s, "fragen")),
            budget=14, leitbild_mitte="arbeit", pruefung=("p2_werkbank",)),
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

#: Zweite Stationsliste (Karte t_fc2c1bfa): keine Phasen-Abnahme, sondern das
#: kleinste Set, das jede deterministische Pruefung aus ``browser_invarianten``
#: mindestens einmal durchlaeuft -- zwei Gruppen (Raumcheck/Beobachter), drei
#: Diskussionsrunden mit gesprochenem Skript statt freier Rede (knapp,
#: verhoerer, nachtrag) und die Wissensfrage ans Board.
STATIONEN_INVARIANTEN: tuple[Station, ...] = (
    Station("p1-eintritt", 1,
            "You just opened the app with your group for the first time. Read "
            "the screen, say hello, and find out what this first phase is about.",
            budget=3, leitbild_ende="eintritt"),
    # Abnahmelauf cb200e4 (05.10.2026): mit "Get through the room check"
    # uebersprang die Persona den Raumcheck ohne einen Fehlschlag ("Skip is
    # the fastest") -- ohne Messung kein Raumcheck-Cache, die Invariante
    # ``raumcheck_domainweit`` blieb ungeprueft. Weiter ein Ziel, kein Rezept.
    Station("p1-kalibrierung", 1,
            "The app wants to check the room before you start. Do the room "
            "check completely, until the app confirms it is done. Skip it only "
            "if it has failed twice.",
            fertig=lambda s: s.get("kalibrierung_aufnahmen", 0) > 0
            or bool(s.get("kalibrierung_modus")),
            # Budget 10 statt 6 (Abnahmelauf 05.10.2026: 6 Schritte reichten
            # mit verstuemmeltem Testsatz nicht). Das Fertig-Praedikat bleibt;
            # ein unbestaetigter Raumcheck wird im Haken ``raumcheck`` zum
            # Befund ``raumcheck_nicht_bestaetigt``.
            budget=10, leitbild_mitte="kalibrierung", pruefung=("raumcheck",)),
    Station("p1-zweite-gruppe", 1,
            "Observe the app of the second group for 20 seconds.",
            gruppe=2, ohne_persona=True, warte_s=20, pruefung=("zweite_gruppe",)),
    Station("p1-zuhoeren", 1,
            "Your group now discusses which terms matter for your play. Press "
            "'Start listening' and put the phone down in the middle of the table "
            "-- do not type the terms. When you are told the discussion is over, "
            "press 'Discussion done'.",
            fertig=lambda s: s.get("diskussion_aufnahmen", 0) > 0,
            zuhoeren_s=None, leitbild_mitte="zuhoeren",
            diskussion="knapp", pruefung=("nach_ende",)),
    Station("p1-zuhoeren-2", 1,
            "Your group discusses a second time. Start listening again, put "
            "the phone down; when told, end the discussion.",
            fertig=lambda s: s.get("diskussion_aufnahmen", 0) > 0,
            zuhoeren_s=None, leitbild_mitte="zuhoeren",
            diskussion="verhoerer", pruefung=("nach_ende", "verhoerer")),
    Station("p1-wissen", 1,
            "Ask the bot what is on the CoThinker.",
            ohne_persona=True, sage=_inv.WISSENSFRAGE, pruefung=("wissen",)),
    Station("p1-zuhoeren-3", 1,
            "One more short round: start listening, add one term, end the "
            "discussion.",
            fertig=lambda s: s.get("diskussion_aufnahmen", 0) > 0,
            zuhoeren_s=None, leitbild_mitte="zuhoeren",
            diskussion="nachtrag", pruefung=("nach_ende",)),
    Station("p1-begriffe", 1,
            "Get the terms from your discussion into the workbench and move on "
            "to the next phase.",
            fertig=lambda s: (_feld(s, "phase") or 1) >= 2,
            budget=6, endet_bei_phasenwechsel=True, leitbild_beobachter="cothinker"),
)

#: Padua live-reif, Phase 3+4 (Karte t_92f99911, Task 2, 05.10.2026): kein
#: Abnahme-Durchlauf von Phase 1, sondern Interviews, Uebergang 3->4,
#: Brainstorm, Rahmen/Figuren/Geschichte und das Angebot von Phase 5 --
#: startet deshalb in Phase 3 (siehe STARTPHASE, browser_umgebung.bereite_vor).
#:
#: Merge-Nachtrag (06.10.2026, Birk "kein Toggle" + Kill-Switch-Umbau): Phase
#: 4 bedient sich seit 05.10. 22:00 ueber ``#diskussion``, also ueber genau
#: das Gate in ``beginneAufnahme()``, das vor der ersten echten Aufnahme auf
#: ``kalEntscheideOderStarte()`` wartet. ``IT_WEB_VAD_KALIBRIERUNG`` (der
#: Kill-Switch) ist per Vorgabe AN ("1"), und dieser Lauf startet in Phase 3
#: -- es gibt keine vorherige Phase-1-Diskussion in DIESEM Lauf, die den
#: gruppen-/tagesweiten ``vad_*``-Cache schon gefuellt haette. Der
#: Kalibrierungsdialog kann also beim ersten ``#diskussion``-Start in Phase 4
#: tatsaechlich erscheinen, genau wie bei ``p1-kalibrierung`` -- deshalb eine
#: eigene Station davor (``p4-kalibrierung``), nicht nur ein Satz im Zieltext
#: von ``p4-brainstorm`` (so wie ``p1-zuhoeren`` den Raumcheck auch nicht
#: mehr erwaehnt, seit es ``p1-kalibrierung`` als eigene Station gibt).
STATIONEN_P34: tuple[Station, ...] = (
    Station("p3-eintritt", 3,
            "Your group is now in the interview phase. Read the screen and find "
            "out how you record an interview with someone.",
            budget=3, leitbild_ende="eintritt"),
    Station("p3-interview-kurz", 3,
            "Do a very short test interview with one passer-by: start an "
            "interview, let the person answer, then finish the interview.",
            fertig=lambda st: st.get("interview_koepfe", 0) >= 1,
            budget=6, zuhoeren_s=None, aufnahme="interview",
            diskussion="interview-kurz", pruefung=("nach_interview",)),
    Station("p3-interview-gemischt", 3,
            "Now do a real interview with a second person, who answers partly in "
            "Italian. Start the interview, let them talk. Partway through, you "
            "may be asked to pause the recording for a moment and then continue "
            "it -- do that if the app offers a pause button. Then finish the "
            "interview.",
            fertig=lambda st: st.get("interview_koepfe", 0) >= 2,
            budget=6, zuhoeren_s=None, aufnahme="interview", pause_resume=True,
            diskussion="interview-gemischt", pruefung=("nach_interview", "pause_resume")),
    Station("p3-uebergang", 3,
            "Your interviews are done. Move on to the next phase.",
            fertig=lambda st: (_feld(st, "phase") or 3) >= 4,
            budget=5, endet_bei_phasenwechsel=True, leitbild_ende="uebergang",
            pruefung=("modellwahl",)),
    Station("p4-eintritt", 4,
            "Read what the app says about this phase and find out how your "
            "group can brainstorm with it.",
            budget=3, leitbild_ende="eintritt"),
    # Mirrors "p1-kalibrierung" (siehe Kommentar vor STATIONEN_P34): Phase 4
    # teilt sich seit 05.10. 22:00 das Diskussions-Gate mit Phase 1, und
    # dieser Lauf startet in Phase 3 ohne vorherige Phase-1-Diskussion, die
    # den Cache schon gefuellt haette -- der Dialog kann hier zum ERSTEN Mal
    # erscheinen.
    Station("p4-kalibrierung", 4,
            "The app wants to check the room before you start the "
            "brainstorm. Get through the room check; if it fails twice, "
            "skip it.",
            fertig=lambda st: st.get("kalibrierung_aufnahmen", 0) > 0
            or bool(st.get("kalibrierung_modus")),
            budget=10, leitbild_mitte="kalibrierung"),
    Station("p4-brainstorm", 4,
            "Your group brainstorms about a character from the interviews. "
            "Press 'Start listening' and put the phone down in the middle of "
            "the table -- the same button as in phase 1. When you are told "
            "the discussion is over, press 'Discussion done'; then look at "
            "the CoThinker tab.",
            fertig=lambda st: st.get("brainstorm_aufnahmen", 0) > 0,
            budget=6, zuhoeren_s=None, aufnahme="brainstorm",
            diskussion="brainstorm-bogen", leitbild_beobachter="cothinker",
            pruefung=("nach_brainstorm",)),
    Station("p4-setting-figuren", 4,
            "Agree as a group where and when your play is set and who is in it, "
            "and settle the list of characters.",
            fertig=lambda st: bool(_feld(st, "rahmen")) and bool(_feld(st, "figuren_fixiert_am")),
            budget=12, leitbild_ende="ergebnis", leitbild_tab="stand"),
    Station("p4-geschichte", 4,
            "Agree on the story in outline and how many scenes the play has.",
            fertig=lambda st: bool(_feld(st, "geschichte"))
            and (bool(_feld(st, "szenen_anzahl")) or st.get("szenen_anzahl", 0) > 0),
            budget=10),
    Station("p4-uebergang", 4,
            "Check whether the app now offers you the next phase. Do not start "
            "it yet.",
            fertig=lambda st: (_feld(st, "phase_angeboten") or 0) >= 5
            or (_feld(st, "phase") or 4) >= 5,
            # I4 (Review 05.10.2026, Fix round 1): ``modellwahl`` lief
            # bisher NUR an ``p3-uebergang`` -- zu diesem Zeitpunkt ist noch
            # keine einzige Phase-4-Station gelaufen, der Phase-4-Bereich ist
            # also immer leer und ``P4_GESPRAECH_NICHT_OPUS`` kann nie
            # feuern. Hier, am Ende von Phase 4, hat der Bereich Inhalt.
            budget=3, leitbild_ende="uebergang", pruefung=("modellwahl", "p5_angebot")),
)

#: Padua live-reif, Phase 5-7 (Karte t_db7c6b2c, Task 2, 06.10.2026): Prose
#: Draft (Schaerfung -> Uebersicht -> Prosa Szene fuer Szene -> Auto-Sprung
#: 6), Rewrite (Pruefung Gesamttext -> Szene fuer Szene -> Auto-Sprung 7),
#: Stage Version (Formen -> Sprechweisen -> Buehnentext je Szene -> Schluss).
#: Startet in Phase 5 (``browser_umgebung.bereite_vor(..., startphase=5)``,
#: Task 1) -- die Gruppe steht dort noch in Phase 4, ``browser_lauf.main``
#: loest den Wechsel ueber den echten Endpunkt aus, wie bei ``p34``.
#:
#: Alle Stationen bekommen ``geduld_s=600`` AUSSER dem Eintritt (bleibt bei
#: der Vorgabe ``ANTWORT_GEDULD_S``, 90s) -- Begruendung am Feld
#: ``Station.geduld_s`` oben: ein Szenenlauf mit Reasoning oder ein
#: Prueflauf mit zwei Runden braucht laenger als 90s und zeigt dabei unter
#: Umstaenden kein ``#tippt``. Gesamtbudget 105 Schritte (Risiko-Vorgabe:
#: hoechstens 80).
STATIONEN_P57: tuple[Station, ...] = (
    Station("p5-eintritt", 5,
            "Your group has just moved into the Prose Draft phase. Read what "
            "the screen says about what happens here.",
            budget=3, leitbild_ende="eintritt",
            warte_bis=lambda s: s.get("schaerfung_zeilen", 0) >= 1
            or bool(_feld(s, "geschichte_uebersicht"))),
    # Review-Fix (06.10.2026, P57-Harness): die neun Stationen ab hier
    # bekommen jetzt ihr eigenes ``warte_bis`` -- vorher hatte nur
    # ``p5-eintritt`` eines, obwohl KEIN Hintergrund-Modul dieser Phasen
    # (``entwurf``/``ueberarbeitung``/``prueflauf``/``nachpass``/
    # ``kurzgeschichte``/``sprechweise``/``schaerfung``/``stueckpruefung``)
    # ``tg.tippt()`` ruft (dasselbe Code-Audit wie am Feld ``geduld_s``
    # oben). Ohne ``warte_bis`` liest der Harness den Nachher-Stand sofort
    # nach ``_ANLAUF_S`` (3s) -- veraltet, solange der Thread noch laeuft.
    #
    # Wo moeglich zaehlt das Praedikat FORTSCHRITT statt nur das Stations-
    # ENDE (``szenen_mit_prosa``/``szenen_mit_volltext`` je gegen den
    # zugehoerigen Abnahme-Zaehler): bei einer mehrschrittigen
    # Bestaetigungsschleife (``p5-szenen``, ``p7-szenen``) wird so JEDER
    # Schritt einzeln erkannt, nicht nur der letzte -- ``browser_lauf.
    # _fuehre_station_aus`` ergaenzt zusaetzlich generisch
    # ``_hat_sich_veraendert`` (irgendeine Abweichung vom Stand vor der
    # Aktion zaehlt auch), fuer die Faelle, in denen kein solcher
    # Fortschrittszaehler existiert (``p6-szenen``: ``prosa`` wird in Phase 5
    # UND 6 geschrieben, ein "fertig, aber noch nicht abgenommen"-Zaehler wie
    # bei den anderen beiden gibt es dafuer nicht).
    Station("p5-schaerfung", 5,
            "Look at the interview passages the app lays next to your scenes "
            "and characters; keep what fits.",
            fertig=lambda s: s.get("schaerfung_uebernommen", 0) >= 1
            or bool(_feld(s, "geschichte_uebersicht_fixiert_am")),
            budget=8, geduld_s=600, pruefung=("p5_schaerfung",),
            warte_bis=lambda s: s.get("schaerfung_uebernommen", 0) >= 1
            or bool(_feld(s, "geschichte_uebersicht_fixiert_am"))),
    Station("p5-uebersicht", 5,
            "Read the story overview the app proposes, ask for one change, "
            "then confirm it.",
            fertig=lambda s: bool(_feld(s, "geschichte_uebersicht_fixiert_am")),
            budget=6, geduld_s=600, pruefung=("p5_uebersicht",),
            warte_bis=lambda s: bool(_feld(s, "geschichte_uebersicht_fixiert_am"))),
    Station("p5-szenen", 5,
            "Read every scene draft in the Script tab, one by one, and "
            "confirm each one.",
            fertig=lambda s: (_feld(s, "phase") or 5) >= 6
            or s.get("szenen_entwurf_ok", 0) >= s.get("szenen_anzahl", 0) > 0,
            budget=24, geduld_s=900, endet_bei_phasenwechsel=True,
            pruefung=("prueflauf", "chat_volltext", "sprung"),
            # Fortschritt: eine frisch entworfene, noch nicht abgenommene
            # Szene (``szenen_mit_prosa`` > ``szenen_entwurf_ok``) ist bereit
            # zum Lesen -- ODER alle Szenen sind durch (Phasensprung).
            warte_bis=lambda s: s.get("szenen_mit_prosa", 0) > s.get("szenen_entwurf_ok", 0)
            or s.get("szenen_entwurf_ok", 0) >= s.get("szenen_anzahl", 0) > 0
            or (_feld(s, "phase") or 5) >= 6),
    Station("p6-gesamt", 6,
            "Ask once for the whole story to be shorter, then confirm it.",
            fertig=lambda s: bool(_feld(s, "gesamttext_fixiert_am")),
            budget=8, geduld_s=600, pruefung=("kuerzung", "prueflauf"),
            warte_bis=lambda s: bool(_feld(s, "gesamttext_fixiert_am"))),
    Station("p6-szenen", 6,
            "Give free feedback on one scene in the chat, then confirm every "
            "scene.",
            fertig=lambda s: (_feld(s, "phase") or 6) >= 7,
            budget=18, geduld_s=900, endet_bei_phasenwechsel=True,
            pruefung=("prueflauf", "chat_volltext", "sprung"),
            # Kein eigener "geschrieben, aber noch nicht abgenommen"-Zaehler
            # wie bei p5-szenen/p7-szenen (``prosa`` wird in Phase 5 UND 6
            # geschrieben, ``szenen_mit_prosa`` ist hier schon seit Phase 5
            # voll) -- deshalb nur das Stationsziel; die Zwischenschritte
            # faengt ``browser_lauf._hat_sich_veraendert`` generisch auf.
            warte_bis=lambda s: s.get("szenen_ueberarbeitung_ok", 0) >= s.get("szenen_anzahl", 0) > 0
            or (_feld(s, "phase") or 6) >= 7),
    Station("p7-formen", 7,
            "In a single chat message, state a form for every scene -- at "
            "least two different forms across the scenes.",
            fertig=lambda s: s.get("szenen_mit_form", 0) >= s.get("szenen_anzahl", 0) > 0,
            budget=6, geduld_s=600, pruefung=("formen",),
            warte_bis=lambda s: s.get("szenen_mit_form", 0) >= s.get("szenen_anzahl", 0) > 0),
    Station("p7-sprechweisen", 7,
            "Read the suggested way each character speaks, then confirm it.",
            fertig=lambda s: bool(_feld(s, "sprechweisen_fixiert_am")),
            budget=6, geduld_s=600,
            warte_bis=lambda s: bool(_feld(s, "sprechweisen_fixiert_am"))),
    Station("p7-szenen", 7,
            "Read every scene's stage text, one by one, and confirm each "
            "one.",
            fertig=lambda s: s.get("szenen_fertig", 0) >= s.get("szenen_anzahl", 0) > 0,
            budget=20, geduld_s=900,
            # Fortschritt: eine frisch uebertragene, noch nicht abgenommene
            # Szene (``szenen_mit_volltext`` > ``szenen_fertig``) ist bereit
            # zum Lesen -- ODER alle Szenen sind abgenommen.
            warte_bis=lambda s: s.get("szenen_mit_volltext", 0) > s.get("szenen_fertig", 0)
            or s.get("szenen_fertig", 0) >= s.get("szenen_anzahl", 0) > 0),
    Station("p7-schluss", 7,
            "Wait for the final check of the whole script, then read the "
            "Script tab.",
            fertig=lambda s: s.get("stueckpruefung_zeilen", 0) > 0,
            budget=6, geduld_s=600, leitbild_tab="textbuch",
            pruefung=("stueckpruefung", "textbuch", "modellwahl57", "sprache57"),
            warte_bis=lambda s: s.get("stueckpruefung_zeilen", 0) > 0),
)

STATIONEN: dict[str, tuple[Station, ...]] = {
    "p12": STATIONEN_P12, "invarianten": STATIONEN_INVARIANTEN, "p34": STATIONEN_P34,
    "p57": STATIONEN_P57}
#: Von welcher Phase ein Lauf startet -- >1 heisst: browser_umgebung.bereite_vor
#: fuellt die Phasen davor, browser_lauf.main schaltet ueber den echten
#: Phasenwechsel-Endpunkt in diese Phase.
STARTPHASE: dict[str, int] = {"p12": 1, "invarianten": 1, "p34": 3, "p57": 5}
