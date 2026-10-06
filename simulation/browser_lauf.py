"""Der CLI-Orchestrator des Browserlaufs (Padua-UX-Simulation, 2026-10-03):
bindet die Teile aus Task 1-10 zu EINEM Lauf zusammen -- eine Opus-Persona
bedient die echte Webseite in einem echten, headless Chromium, Phase fuer
Phase, bis ``bis_phase`` erreicht ist oder die Persona aufgibt.

``fuehre_lauf`` ist die Engine (von einem echten oder einem Attrappen-Stack
aufrufbar, siehe ``tests/test_browser_lauf.py``), ``main()`` ist der duenne
CLI-Wrapper, der einen echten Stack (``browser_umgebung.starte_stack``),
einen echten Opus-Klienten (``simulation.claude.Claude``) und einen echten
Browser (Playwright) baut und danach genau dieselbe Engine aufruft.

Kein Schritt darf den ganzen Lauf mitreissen -- dieselbe Haltung wie
``simulation/lauf.py``: ein fehlgeschlagener Richterlauf oder ein kaputter
Phasenschritt wird vermerkt (``fehlgeschlagen_bei``), der Lauf geht mit der
naechsten Phase weiter."""

from __future__ import annotations

import dataclasses
import json
import logging
import sqlite3
import subprocess
import time
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import Error as PlaywrightError
except (ImportError, ModuleNotFoundError):
    # Fallback bei Playwright-Import-Fehler (z.B. Greenlet-Kompatibilitätsproblem)
    # Dies erlaubt Tests ohne Playwright-Abhängigkeit, z.B. _app_commit
    PlaywrightError = Exception

from interview_theater import phasen
from simulation import (
    browser_aktionen,
    browser_elemente,
    browser_invarianten,
    browser_judge,
    browser_mitschnitt,
    browser_persona,
    browser_stationen,
    browser_zaehler,
)
from simulation.browser_pruefhaken import (  # noqa: F401 -- die Haken-API dieses Moduls
    PruefKontext,
    befund_ausnahme,
    fuehre_pruefungen,
    sichtbares,
    speicher_schluessel,
    warte_nach_klick,
)

log = logging.getLogger(__name__)

#: Wie viele "nach"-Screenshots je Phase an den Richter gehen und im Bericht
#: stehen -- mehr waere fuer beide kein Gewinn (der Richter liest sie als
#: Bildfolge, der Bericht zeigt sie nebeneinander).
SCREENSHOTS_JE_PHASE = 3


def _verlaufszeilen(page) -> list[str]:
    """Die sichtbaren Chat-Blasen als Zeilen ``"<von>: <text>"`` -- genug
    fuer ``browser_persona.naechste_aktion``, das ohnehin nur die letzten
    acht nimmt. Keine eigene Heuristik fuer Sichtbarkeit: eine entfernte
    oder ueberholte Blase bleibt im DOM stehen (``web_chat.py``), zaehlt hier
    also mit -- das ist dasselbe, was eine Gruppe beim Hochscrollen sieht."""
    roh = page.eval_on_selector_all(
        ".blase",
        "els => els.map(el => ({von: (el.classList[1] || '?'), "
        "text: (el.innerText || '').trim()}))",
    )
    return [f"{z['von']}: {z['text']}" for z in roh if z["text"]]


def _verlaufsblasen(page) -> list[dict]:
    """Wie ``_verlaufszeilen``, nur strukturiert statt als Zeile -- fuer
    ``browser_stationen.muss_antworten`` (braucht ``von``/``typ``/``text``
    getrennt) und fuer die Erklaernote (Pflichtpunkt 1: welche Bot-Blase
    gerade zu beurteilen ist). ``classList[1]`` ist ``von`` (bot/gruppe),
    ``classList[2]`` die Darstellungsklasse (``klasseVon`` in
    ``web_chat.py``: ``text``/``system``/``sprache``/``datei``/``transkript``) --
    eine Systemzeile (Quittung, Undo-Ergebnis) steht mit ``von=bot``."""
    return page.eval_on_selector_all(
        ".blase",
        "els => els.map(el => ({von: el.classList[1] || '?', "
        "typ: el.classList[2] || 'text', text: (el.innerText || '').trim()}))",
    )


def _aktion_ausfuehren(page, aktion: dict) -> dict:
    """Die try/except-Logik aus ``_fuehre_phase_aus``, herausgezogen: auch
    der Stationslauf braucht sie, und zwei Kopien wuerden irgendwann
    auseinanderlaufen."""
    try:
        return browser_aktionen.fuehre_aus(page, aktion)
    except browser_aktionen.UnbekannteAktion as fehler:
        log.warning("unbekannte Persona-Aktion: %s", fehler)
        return {"art": "unbekannt", "fehler": str(fehler)}
    except (browser_aktionen.PhasenwechselFehlt,
            browser_aktionen.PhasenwechselAbgelehnt) as fehler:
        log.warning("Phasenwechsel nicht moeglich (%s): %s", aktion, fehler)
        return {"art": "fehlgeschlagen", "fehler": str(fehler)}
    except PlaywrightError as fehler:
        log.warning("Aktion schlug fehl (%s): %s", aktion, fehler)
        return {"art": "fehlgeschlagen", "fehler": str(fehler)}


#: P57 Schleifenschutz: so oft darf DIESELBE Aktion (oder derselbe Fehler in
#: Folge) in einer Station scheitern, bevor die Station endet.
SCHLEIFE_MAX_FEHLER = 3
#: Hoechstens so lange darf eine Station dauern (Sekunden).
STATION_MAX_S = 20 * 60.0
#: Hoechstens so lange darf ein ganzer Lauf dauern (Minuten).
LAUF_MAX_MINUTEN = 120.0


def _aktionsschluessel(aktion: dict) -> str:
    """Identitaet einer Aktion fuer den Schleifenschutz: Typ + Ziel, ohne
    Begruendung/offene Fragen (die formuliert die Persona jedes Mal neu)."""
    ziel = next((aktion[k] for k in ("nummer", "element_id", "text", "selektor", "name")
                 if aktion.get(k) not in (None, "")), "")
    return f"{aktion.get('type')}:{ziel}"


class Schleifenwaechter:
    """Zaehlt fehlgeschlagene Aktionen einer Station. ``pruefe`` liefert beim
    Erreichen der Schwelle ``(befundschluessel, fehlertext)``, sonst ``None``."""

    def __init__(self, schwelle: int = SCHLEIFE_MAX_FEHLER):
        self.schwelle = schwelle
        self._je_aktion: dict[str, int] = {}
        self._letzter_fehler = None
        self._folge = 0

    def pruefe(self, aktion: dict, protokoll: dict):
        if protokoll.get("art") not in ("fehlgeschlagen", "unbekannt"):
            self._letzter_fehler, self._folge = None, 0
            return None
        schluessel = _aktionsschluessel(aktion)
        fehler = " ".join(str(protokoll.get("fehler", "")).split())
        self._je_aktion[schluessel] = self._je_aktion.get(schluessel, 0) + 1
        # Gleicher Fehler in Folge, unabhaengig von der Aktionsformulierung.
        norm = "".join(c for c in fehler.casefold() if c.isalpha())[:120]
        self._folge = self._folge + 1 if norm == self._letzter_fehler else 1
        self._letzter_fehler = norm
        if self._je_aktion[schluessel] >= self.schwelle or self._folge >= self.schwelle:
            return (f"aktion_wiederholt_fehlgeschlagen:{schluessel}", fehler)
        return None


def _diskussion_laeuft(page) -> bool:
    return page.locator('#diskussion[data-laeuft="1"]').count() > 0


def _aufnahme_laeuft(page, art: str = "diskussion") -> bool:
    """Wie ``_diskussion_laeuft``, aber je Aufnahmeart (Padua live-reif
    Phase 3+4, Task 2): ``diskussion`` delegiert unveraendert an die
    bestehende Funktion (Dortmund/P1-2-Verhalten bleibt gleich), Interview
    und Brainstorm lesen ``browser_stationen.LAEUFT[art]``."""
    if art == "diskussion":
        return _diskussion_laeuft(page)
    return page.locator(browser_stationen.LAEUFT[art]).count() > 0


def _beende_aufnahme_deterministisch(page, art: str = "diskussion") -> bool:
    """Wie ``_beende_diskussion_deterministisch``, je Aufnahmeart."""
    if art == "diskussion":
        return _beende_diskussion_deterministisch(page)
    knopf = browser_stationen.ENDE[art]
    if page.locator(f"{knopf}:visible").count() == 0:
        return False
    page.click(knopf)
    return True


def _beende_laufende_aufnahme(page) -> str | None:
    """H1 (Abnahme P3-4, Lauf 042439, 06.10.2026): eine Sitzung, die die
    Persona in einer FRUEHEREN Station OHNE eigenes ``diskussion`` schon
    gestartet hat (gemessen: ``p3-eintritt``, Priya tippte aus Neugier auf
    "Start interview"), wuerde der naechste Browser-Neustart
    (``wechsle_audio``, vor jeder Station MIT ``diskussion``) sonst killen,
    BEVOR ein einziges Segment hochgeladen ist -- Chromiums Fake-Mikrofon
    laeuft nur im alten Prozess. Vor einem solchen Wechsel wird deshalb erst
    eine auf DIESER Seite noch laufende Aufnahme (Interview oder
    Diskussion/Brainstorm -- dieselben Selektoren, ``browser_stationen.
    LAEUFT``/``ENDE``) sauber beendet.

    Der Klick laeuft auf GENAU DER Seite, die die Sitzung gestartet hat --
    dort ist ``zustand.aufnahme`` serverseitig dieser Seite zugeordnet,
    also kein Fremdgeraet-Fall (``web_chat.js`` ``fremdBestaetigt``,
    Doppel-Tipp-Bestaetigung). Liefert die beendete Art oder ``None``, wenn
    nichts lief (der weit haeufigere Fall -- dann aendert sich nichts am
    bisherigen Ablauf)."""
    for art in ("interview", "diskussion"):
        if _aufnahme_laeuft(page, art) and _beende_aufnahme_deterministisch(page, art):
            return art
    return None


#: H1: wie lange hoechstens auf das serverseitige Ende gewartet wird, bevor
#: der Browser trotzdem gewechselt wird -- ein Sicherheitsnetz, kein
#: Haengenbleiben des Harness bei einem echten Fehler. Grosszuegiger als
#: ``browser_invarianten.GRACE_NACH_SIGNAL_S`` (10 s), weil hier ein
#: vollstaendiger Interview-Abschluss (Whisper, Erkenner) abgewartet wird,
#: nicht nur eine Buehnenkarte.
FRIST_AUFNAHME_ENDE_VOR_WECHSEL_S = 20.0


def _warte_auf_aufnahme_ende(db_pfad: str, chat_id: int, art: str,
                             frist_s: float = FRIST_AUFNAHME_ENDE_VOR_WECHSEL_S) -> None:
    """Wartet, bis das von ``_beende_laufende_aufnahme`` ausgeloeste Ende
    serverseitig angekommen ist -- OHNE das stuerbe der naechste
    Browser-Neustart (``wechsle_audio``) mitten im letzten Flush (genau der
    H1-Fehlermodus, nur einen Schritt spaeter). Fuer ``interview`` ist das
    Signal ``P34Stand.koepfe[-1]['beendet']`` (``aufnahme.beendet_am``
    gesetzt oder Status fertig/transkribiert, siehe ``lese_p34_stand``).
    ``diskussion``/``brainstorm`` haben keinen eigenen Kopf-Status -- eine
    kurze feste Gnadenfrist reicht hier (nur der letzte Chunk-Upload fehlt
    noch, keine Verdichtung)."""
    if art != "interview":
        time.sleep(min(frist_s, 3.0))
        return
    ende_zeit = time.monotonic() + frist_s
    while True:
        stand = _lies_p34(db_pfad, chat_id)
        if stand.koepfe and stand.koepfe[-1]["beendet"]:
            return
        if time.monotonic() >= ende_zeit:
            return
        time.sleep(1.0)


def _pausiere_und_fortsetze_aufnahme(page, art: str) -> bool:
    """Pausiert eine laufende Aufnahme einmal und setzt sie gleich wieder
    fort -- ``#interview-pause``/``#diskussion-pause`` sind Umschalter
    (``web_chat.js``, ``interviewPauseKnopf``/``diskussionPauseKnopf``): der
    erste Klick pausiert, der zweite setzt fort. Deterministisch wie
    ``_beende_aufnahme_deterministisch`` -- schliesst die Coverage-Luecke
    "Pause/Resume" (``p34-abnahme-verfahren.md`` §3: keine P34-Station
    pruefte das bisher) unabhaengig davon, ob die Persona selbst daran
    denkt, derselbe Gedanke wie beim deterministischen Diskussions-Ende.
    Liefert True, wenn beide Klicks sassen UND die Aufnahme danach wieder
    laeuft."""
    knopf = browser_stationen.PAUSE.get(art)
    if not knopf or page.locator(f"{knopf}:visible").count() == 0:
        return False
    page.click(knopf)
    page.wait_for_timeout(2000)
    if page.locator(f"{knopf}:visible").count() == 0:
        return False
    page.click(knopf)
    page.wait_for_timeout(500)
    return _aufnahme_laeuft(page, art)


def _schliesse_offenes_phasensheet(page) -> bool:
    """Schliesst ein offenes Padua-Stepper-Bestaetigungsblatt
    (``#phasensheet``) deterministisch ueber "Stay here", BEVOR die Persona
    ihren naechsten Zug plant (Abnahme P1-2, Fortsetzung, 05.10.2026: ein
    echter Lauf oeffnete dieses Blatt unbeabsichtigt -- es blieb offen und
    blockierte jeden weiteren Klick per unsichtbarem Hintergrund-Abdunkler,
    bis ein 30s-Timeout die Station abbrechen liess). Keiner der elf
    Stationen dieses Abnahmelaufs navigiert ueber dieses Blatt absichtlich
    -- ein offenes Blatt ist hier immer ein Unfall, das Schliessen braucht
    keine LLM-Entscheidung, derselbe Gedanke wie beim deterministischen
    Diskussions-Ende. Liefert True, wenn geschlossen wurde."""
    bleib = page.locator("#phasensheet-bleib:visible")
    if bleib.count() == 0:
        return False
    bleib.first.click()
    return True


def _beende_diskussion_deterministisch(page) -> bool:
    """Druecke ``#diskussion-beenden`` direkt, statt der Persona per Hinweis
    zu ueberlassen, ob sie es tut (Abnahme P1-2, Fortsetzung: Robo-Diagnose
    zeigte, dass ``ist_abschluss=True`` -- der einzige verlaessliche Ausloeser
    fuer eine Begriffsboard-Reaktion ohne Pausen-Schnitt -- in keinem der
    vier echten Laeufe erreicht wurde, weil die Persona den Knopf nie
    anfasste). Ein stummes Mithoeren ohne Chat-Feedback braucht keine
    LLM-Entscheidung zum Beenden -- derselbe Gedanke wie bei der
    ``ohne_persona``-Station ``p1-start``. Liefert True, wenn geklickt
    wurde."""
    if page.locator("#diskussion-beenden:visible").count() == 0:
        return False
    page.click("#diskussion-beenden")
    return True


def _entwickler_meta(page) -> list[str]:
    # ``browser_zaehler.entwickler_meta_seite`` landet erst in Paket F -- der
    # getattr-Rueckfall haelt dieses Paket eigenstaendig lauffaehig und gibt
    # Paket F eine Stelle zum Einhaengen, ohne hier noch einmal etwas
    # anzufassen.
    zaehler = getattr(browser_zaehler, "entwickler_meta_seite", None)
    return zaehler(page) if zaehler else []


def _erfasse_ohne_persona(page) -> dict:
    """p1-start: mechanische Erfassung ohne Persona-Aufruf (Pflichtpunkt 2).
    Liest ``.blase.bot``, ``#kalibrierung*``, ``#diskussion*`` und ``.leer``
    direkt aus dem DOM."""
    return {
        "bot_nachricht": page.locator(".blase.bot").count() > 0,
        "kalibrierung_sichtbar": page.locator("#kalibrierung:visible").count() > 0,
        "zuhoeren_laeuft": _diskussion_laeuft(page),
        "leertext_sichtbar": page.locator(".leer").count() > 0,
    }


def _aktive_phase_nummer(page) -> int | None:
    """Liest ``#roadmap``s ``data-aktive-phase`` -- die einzige Stelle, an
    der die Seite den serverseitig geltenden Phasenstand trägt
    (``web_vereint.py``)."""
    wert = page.get_attribute("#roadmap", "data-aktive-phase")
    if wert is None:
        return None
    try:
        return int(wert)
    except ValueError:
        return None


def _nonce(basis_url: str, token: str) -> str:
    with urllib.request.urlopen(
        f"{basis_url}/g/{token}/chat/zustand?nach=0", timeout=5
    ) as antwort:
        return json.loads(antwort.read().decode("utf-8"))["nonce"]


def _loese_phasenwechsel_aus(basis_url: str, token: str, nummer: int) -> None:
    """Der dokumentierte Operator-Notweg: derselbe Endpunkt, den ein Klick auf
    die Phasenleiste im Browser ansteuert (``web_vereint.phase_post``), hier
    direkt per HTTP -- ohne auf einen zweiten Klick fuer die Rueckfrage zu
    warten, ``bestaetigt: 1`` ersetzt ihn."""
    koerper = json.dumps({
        "nonce": _nonce(basis_url, token), "nummer": nummer, "bestaetigt": 1,
    }).encode("utf-8")
    anfrage = urllib.request.Request(
        f"{basis_url}/g/{token}/chat/phase", data=koerper,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=10):
        pass


def _zaehler_addieren(summe: dict, zaehler: dict) -> None:
    """Haeuft einen Schritt-Zaehler (``browser_zaehler.alle``) additiv auf
    die laufende Phasen-Tally -- ein ``bool`` zaehlt als 0/1 Treffer, eine
    Fundliste nach ihrer Laenge."""
    for schluessel, wert in zaehler.items():
        zuwachs = (1 if wert else 0) if isinstance(wert, bool) else len(wert)
        summe[schluessel] = summe.get(schluessel, 0) + zuwachs


def _repraesentativ(pfade: list[Path], anzahl: int = SCREENSHOTS_JE_PHASE) -> list[Path]:
    """Bis zu ``anzahl`` gleichmaessig verteilte Eintraege aus ``pfade`` --
    immer mit dem ersten und dem letzten, dazwischen gleich verteilt. Eine
    Phase mit 20 Schritten bekaeme sonst 20 Bilder an den Richter, wo drei
    genuegen."""
    if len(pfade) <= anzahl:
        return list(pfade)
    if anzahl <= 1:
        return [pfade[-1]]
    schritt = (len(pfade) - 1) / (anzahl - 1)
    indizes = sorted({round(i * schritt) for i in range(anzahl)})
    return [pfade[i] for i in indizes]


def _modell_lesen(db_pfad: str) -> dict[str, str]:
    """``DISTINCT art, modell`` aus der Tabelle ``aufruf`` -- read-only, wie
    ``browser_mitschnitt._oeffne_lesend``. Fehlt die Tabelle (eine ganz
    frische Datenbank ohne einen einzigen Aufruf) oder ist die Datei noch
    nicht da, ist das Ergebnis leer statt ein Fehler."""
    modelle: dict[str, str] = {}
    try:
        conn = sqlite3.connect(f"file:{db_pfad}?mode=ro", uri=True, timeout=5.0)
    except sqlite3.OperationalError:
        return modelle
    try:
        zeilen = conn.execute(
            "SELECT DISTINCT art, modell FROM aufruf WHERE modell IS NOT NULL"
        ).fetchall()
        for art, modell in zeilen:
            modelle[art] = modell
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
    return modelle


def _fuehre_phase_aus(
    page, persona_client, mitschnitt: browser_mitschnitt.Mitschnitt,
    *, aktuelle_phase: int, basis_url: str, token: str, db_pfad: str,
    chat_id: int, persona_name: str, max_schritte: int,
    fallback_nach_schritten: int,
) -> dict:
    """Ein Phasendurchlauf: bis zu ``max_schritte`` Aktionen der Persona,
    jede mit Mitschnitt. Liefert die Zaehler-Tally, ob der Operator-Notweg
    gezogen wurde, und die "nach"-Screenshots dieser Phase."""
    phasenziel = phasen.satz(aktuelle_phase) or phasen.kurzname(aktuelle_phase) or str(aktuelle_phase)
    zaehler_summe: dict[str, int] = {}
    screenshots_nach: list[Path] = []
    fallback_benutzt = False
    vorher_stand = browser_mitschnitt.datenstand(db_pfad, chat_id)

    schritt = 0
    while schritt < max_schritte:
        schritt += 1
        vor_pfad = mitschnitt.screenshot_pfad(aktuelle_phase, "vor")
        vor_pfad.write_bytes(browser_elemente.bildschirmfoto(page))
        elemente = browser_elemente.extrahiere(page)
        verlauf = _verlaufszeilen(page)

        aktion = browser_persona.naechste_aktion(
            persona_client, persona_name, vor_pfad.read_bytes(), elemente,
            phasenziel, verlauf,
        )
        if aktion.get("type") == "done_phase":
            break

        # Ein einzelner Fehlgriff der Persona (unbekannte Aktion, ins Leere
        # treffender Klick) soll nur diesen Schritt kosten, nicht die ganze
        # Phase -- ausgelagert nach ``_aktion_ausfuehren``, das der
        # Stationslauf ebenfalls braucht.
        protokoll = _aktion_ausfuehren(page, aktion)

        warte = browser_aktionen.warte_auf_antwort(page)

        nach_pfad = mitschnitt.screenshot_pfad(aktuelle_phase, "nach")
        nach_pfad.write_bytes(browser_elemente.bildschirmfoto(page))
        screenshots_nach.append(nach_pfad)

        nachher_stand = browser_mitschnitt.datenstand(db_pfad, chat_id)
        db_diff = browser_mitschnitt.unterschied(vorher_stand, nachher_stand)
        vorher_stand = nachher_stand

        _zaehler_addieren(zaehler_summe, browser_zaehler.alle(page))

        mitschnitt.schritt(
            phase=aktuelle_phase, screenshot_vorher=vor_pfad,
            screenshot_nachher=nach_pfad, elemente=elemente,
            aktion=protokoll, begruendung=aktion.get("begruendung", ""),
            antwort=warte, db_diff=db_diff,
        )

        aktive_nummer = _aktive_phase_nummer(page)
        if aktive_nummer is not None and aktive_nummer > aktuelle_phase:
            # Natuerlicher Fortschritt -- die Gruppe (hier: die Persona) hat
            # die Phase selbst weitergeschaltet. Kein Notweg noetig.
            break

        if schritt >= fallback_nach_schritten:
            # Realer Betriebsbefund (Padua-Abnahme, 03.10.2026): in der
            # LETZTEN Phase gibt es keine naechste, in die der Notweg
            # springen koennte -- ein Versuch dort liefert HTTP 400 (die
            # Phasennummer existiert nicht, ``web_vereint.phase_post``
            # prueft sie gegen ``phasen.PHASEN``) und reisst die Phase als
            # "gescheitert" in die Bilanz, obwohl die Persona bis dahin
            # produktiv gearbeitet haben kann. Dort einfach das
            # Schritt-Budget enden lassen, ohne Notweg.
            ziel = browser_stationen.notweg_ziel(aktuelle_phase, _aktive_phase_nummer(page))
            if ziel is not None and ziel <= phasen.LETZTE:
                _loese_phasenwechsel_aus(basis_url, token, ziel)
                fallback_benutzt = True
            break

    # Erst JETZT, auf dem Bildschirm, auf dem die Phasenschleife endete --
    # ein Knopf-Scan waehrend der Schleife wuerde den Bildschirm fuer den
    # naechsten Persona-Schritt veraendern (er mutiert die Seite).
    knopf_befunde = []
    try:
        knopf_befunde = browser_zaehler.knoepfe_ohne_wirkung(page)
    except Exception:
        log.exception("knoepfe_ohne_wirkung ist in Phase %s gescheitert", aktuelle_phase)
    if knopf_befunde:
        zaehler_summe["knoepfe_ohne_wirkung"] = (
            zaehler_summe.get("knoepfe_ohne_wirkung", 0) + len(knopf_befunde)
        )

    return {
        "zaehler_summe": zaehler_summe,
        "fallback_benutzt": fallback_benutzt,
        "screenshots_nach": screenshots_nach,
    }


#: Wie oft ``_warte_bis`` zwischen zwei Pruefungen des Praedikats pausiert.
_WARTE_BIS_INTERVALL_MS = 2000


#: H2 (P57): so lange darf der Datenstand ruhen, nachdem der Bot geantwortet
#: hat, bevor ``_warte_bis`` aufgibt (statt die volle ``geduld_s`` von 600 s
#: je Schritt zu verbrennen). Ein sehr langer stiller Hintergrundlauf ohne
#: Zwischenschreibung koennte so zu frueh abgeschnitten werden -- dann zeigt
#: die Station "nicht erreicht" statt eines 10-Minuten-Wartens.
WARTE_RUHE_S = 20.0


def _warte_bis(page, pruefe, lese_stand, geduld_s: float, *,
               ruhe_s: float | None = None, bot_antwort_da=None) -> dict:
    """Pollt ``lese_stand()`` (``browser_mitschnitt.datenstand``), bis
    ``pruefe(stand)`` wahr wird oder ``geduld_s`` verstrichen ist (Task 2,
    BRIEF p57, ``Station.warte_bis``).

    Fuer Stationen, deren Hintergrund-Thread (Szene mit Reasoning, Prueflauf)
    ``#tippt``/``.blase.vorlaeufig`` nie zeigt (Fakt 5, Begruendung am Feld
    ``Station.geduld_s``) -- ohne ``warte_bis`` haette der Harness KEINEN
    Weg, das Ende so eines Laufs zu bemerken, und wuerde sofort mit einem
    unfertigen Stand weiterlaufen.

    ``page.wait_for_timeout`` statt ``time.sleep``: dieselbe Uhr wie der Rest
    dieser Datei, und in Tests durch eine Attrappe ersetzbar, ohne wirklich
    zu warten (``test_warte_bis_...`` in ``tests/test_browser_lauf.py``)."""
    start = time.monotonic()
    stand = lese_stand()
    letzte_aenderung = start
    while not pruefe(stand) and time.monotonic() - start < geduld_s:
        page.wait_for_timeout(_WARTE_BIS_INTERVALL_MS)
        neu = lese_stand()
        jetzt = time.monotonic()
        if neu != stand:
            letzte_aenderung = jetzt
        stand = neu
        if (ruhe_s is not None and jetzt - letzte_aenderung >= ruhe_s
                and bot_antwort_da is not None and bot_antwort_da()):
            break
    return stand


def _hat_sich_veraendert(vorher: dict, nachher: dict) -> bool:
    """Ob sich der Datenstand gegenueber ``vorher`` IRGENDWO veraendert hat
    (Review-Fix 06.10.2026, ``docs/handoffs`` P57-Harness): die generische
    Rueckfallbedingung, mit der ``_fuehre_station_aus`` ``Station.warte_bis``
    ergaenzt.

    Grund: bei einer mehrschrittigen Bestaetigungsschleife (``p5-szenen``,
    ``p6-szenen``, ``p7-szenen`` -- ``Station.budget`` bis zu 14) feuert das
    stationseigene Ziel-Praedikat erst auf dem LETZTEN Schritt ("alle Szenen
    fertig"/Phasensprung). Ohne diese Rueckfallbedingung wuerde ``_warte_bis``
    auf JEDEM Zwischenschritt die volle ``geduld_s`` (600s) verbrauchen,
    obwohl der angestossene Hintergrund-Thread (Prueflauf vor jeder Anzeige,
    dann die naechste Szene) laengst fertig ist und etwas anderes im
    Datenstand veraendert hat (ein neuer Prueflauf, eine neu geschriebene
    Szene, ein neues Zitat). ``browser_mitschnitt.unterschied`` liefert den
    Vergleich bereits strukturiert -- hier zaehlt jede Abweichung, nicht nur
    eine bestimmte."""
    diff = browser_mitschnitt.unterschied(vorher, nachher)
    return bool(diff["arbeitsstand_geaendert"]) or bool(diff["zahlen_geaendert"])


def _fuehre_station_aus(page, persona_client, mitschnitt: browser_mitschnitt.Mitschnitt,
                        station: browser_stationen.Station, *, basis_url: str,
                        token: str, db_pfad: str, chat_id: int, persona_name: str,
                        beobachter=None, leitbilder=None, vor_ende=None,
                        nach_klick=None, max_station_s: float = STATION_MAX_S,
                        frist: float | None = None) -> dict:
    """Ein Stationsdurchlauf (Abnahmelauf Phase 1-2, 04.10.2026): wie
    ``_fuehre_phase_aus``, aber gegen ein Stationsziel statt eine Phase, mit
    Nachfragen-Schutz (``browser_stationen.muss_antworten``), optionalem
    Zuhoeren (``station.zuhoeren_s``) und Leitbild-Aufnahmen.

    ``station.ohne_persona`` ist die eine Ausnahme (p1-start, Pflichtpunkt
    2): keine Persona, nur Warten und eine mechanische Lese-Erfassung.

    ``vor_ende`` (Task 6) laeuft unmittelbar vor dem deterministischen Klick
    auf "Discussion done" -- dort liest ``fuehre_stationen`` den
    Vorher-Stand fuer die ``nach_ende``-Pruefung. ``nach_klick`` laeuft
    direkt nach einem erfolgreichen Klick (dort wartet ``nach_ende`` bis zu
    60 s auf Board und Bot -- bevor die Persona weitertippen kann)."""
    if station.ohne_persona:
        page.wait_for_timeout(station.warte_s * 1000)
        erfassung = _erfasse_ohne_persona(page)
        if leitbilder and station.leitbild_ende:
            leitbilder.nimm(page, station.phase, station.leitbild_ende)
        # Reiner Beobachtungsschritt, kein Vorher/Nachher -- ein einziges
        # echtes Bild dient fuer beide Felder (Abweichung von der woertlichen
        # Vorlage mit ``screenshot_vorher=None``: ``Path(None)`` wirft
        # ``TypeError``, siehe Paket-E-Bericht). ``schritte.jsonl`` darf keinen
        # Pfad ohne Datei dahinter enthalten (Invariante, siehe
        # ``test_browser_lauf.py``).
        bild_pfad = mitschnitt.screenshot_pfad(station.phase, f"{station.schluessel}-ohne-persona")
        bild_pfad.write_bytes(browser_elemente.bildschirmfoto(page))
        mitschnitt.schritt(
            phase=station.phase, screenshot_vorher=bild_pfad, screenshot_nachher=bild_pfad,
            elemente=[], aktion={"type": "ohne_persona_warten"}, begruendung="",
            antwort={}, db_diff={}, station=station.schluessel)
        return {"schritte": 0, "nachfragen_beantwortet": 0, "offene_fragen": [],
                "fertig": True, "fallback_benutzt": False, "zaehler_summe": {},
                "screenshots_nach": [], **erfassung}

    zaehler_summe: dict[str, int] = {}
    screenshots: list[Path] = []
    offene: list[str] = []
    beantwortet = 0
    hinweis = None
    gewartet = mitte_genommen = fallback = False
    #: Coverage-Luecke Pause/Resume (p34-abnahme-verfahren.md §3): ob
    #: ``_pausiere_und_fortsetze_aufnahme`` mittendrin lief UND bestaetigt
    #: hat, dass die Aufnahme danach weiterlief -- nur fuer
    #: ``station.pause_resume`` ueberhaupt versucht (siehe unten).
    pause_resume_ok = False
    #: Hoechste ``aufruf.id`` im Moment des erkannten Phasenwechsels (I4,
    #: Fix round 1) -- None, solange keiner erkannt wurde. Grundlage von
    #: ``_teile_bereich_am_phasenwechsel``: ohne sie zaehlte eine Antwort,
    #: die faktisch schon in der naechsten Phase lief, noch als diese.
    phasenwechsel_aufruf_id: int | None = None
    # Station mit gesprochenem Skript (``station.diskussion``): sie endet,
    # sobald die Diskussion vorbei ist -- Harness-Klick auf "Discussion
    # done" oder eine laufende Diskussion, die nach einer Aktion nicht mehr
    # laeuft. Abnahmelauf cb200e4 (05.10.2026): die Persona startete danach
    # neu, drueckte "Take these" und landete in Phase 2 -- der CoThinker
    # zeigte kein Board mehr, Wissensfrage und Nachtrag liefen ins Leere.
    diskussion_lief = diskussion_vorbei = False
    vorher = browser_mitschnitt.datenstand(db_pfad, chat_id)
    if leitbilder and station.leitbild_anfang:
        leitbilder.nimm(page, station.phase, station.leitbild_anfang)

    def _warte_und_beende_diskussion_falls_noetig() -> bool:
        """Kapselt den Zuhoer-Takt (Warten bis ``zuhoeren_s`` um ist, dann
        deterministisch beenden) -- aufgerufen an ZWEI Stellen (siehe unten):
        nach einer normalen Aktion UND bevor ein ``done_station``/
        ``done_phase`` die Station vorzeitig beenden darf. Ohne die zweite
        Stelle (Abnahme P1-2, Fortsetzung, 05.10.2026, echter Lauf) konnte
        die Persona die Diskussion starten und dann sofort "done_station"
        sagen -- die Schleife brach VOR diesem Block ab, die Diskussion
        blieb unbeendet, und das Begriffsboard sah nie ein
        ``ist_abschluss=True``. ``nonlocal``, weil ``gewartet``/
        ``mitte_genommen`` Schleifenzustand sind, der ueber beide
        Aufrufstellen hinweg gilt."""
        nonlocal gewartet, mitte_genommen, hinweis, diskussion_vorbei, diskussion_lief, pause_resume_ok
        if not (station.zuhoeren_s and not gewartet and _aufnahme_laeuft(page, station.aufnahme)):
            return False
        gewartet = diskussion_lief = True
        ende = time.monotonic() + station.zuhoeren_s
        pause_versucht = False
        while time.monotonic() < ende:
            page.wait_for_timeout(10_000)
            # Coverage-Luecke Pause/Resume: einmal mittendrin pausieren und
            # sofort wieder fortsetzen (deterministisch, siehe
            # ``_pausiere_und_fortsetze_aufnahme``) -- nicht in den letzten
            # 5s (sonst ueberlappt es mit dem Ende-Klick unten) und nur fuer
            # Stationen, die das ausdruecklich anfordern
            # (``station.pause_resume``, z. B. ``p3-interview-gemischt``).
            if (station.pause_resume and not pause_versucht
                    and time.monotonic() < ende - 5):
                pause_versucht = True
                pause_resume_ok = _pausiere_und_fortsetze_aufnahme(page, station.aufnahme)
            if beobachter:
                beobachter.messe()
            if leitbilder and station.leitbild_mitte and not mitte_genommen:
                mitte_genommen = bool(leitbilder.nimm(page, station.phase, station.leitbild_mitte))
        if vor_ende is not None:
            vor_ende()
        if _beende_aufnahme_deterministisch(page, station.aufnahme):
            diskussion_vorbei = True
            if nach_klick is not None:
                nach_klick()
            if beobachter:
                beobachter.messe()
        else:
            hinweis = browser_stationen.HINWEIS_DISKUSSION_ENDE
        return True

    schritte = 0
    waechter = Schleifenwaechter()
    schleifenbefunde: list[dict] = []
    # Zeitdeckel (P57): Station hoechstens ``max_station_s``, Lauf-Frist
    # (monotonic) darf nie ueberschritten werden.
    ende_zeit = time.monotonic() + max_station_s
    if frist is not None:
        ende_zeit = min(ende_zeit, frist)
    while schritte < station.budget:
        if time.monotonic() >= ende_zeit:
            schleifenbefunde.append({
                "schluessel": f"station_zeitdeckel:{station.schluessel}",
                "text": f"Station {station.schluessel} nach {schritte} Schritten wegen "
                        f"Zeitdeckel beendet (max {max_station_s:.0f} s / Lauffrist)."})
            break
        schritte += 1
        _schliesse_offenes_phasensheet(page)
        vor = mitschnitt.screenshot_pfad(station.phase, f"{station.schluessel}-vor")
        vor.write_bytes(browser_elemente.bildschirmfoto(page))
        elemente = browser_elemente.extrahiere(page)
        aktion = browser_persona.naechste_aktion(
            persona_client, persona_name, vor.read_bytes(), elemente,
            station.ziel, _verlaufszeilen(page), hinweis=hinweis)
        hinweis = None
        offene.extend(browser_persona.offene_fragen(aktion))
        if aktion.get("type") in ("done_phase", "done_station"):
            # Die Diskussion zuerst sauber beenden, falls sie noch laeuft --
            # sonst wuerde die Station enden, waehrend im Hintergrund weiter
            # aufgezeichnet wird und nie jemand "Discussion done" drueckt.
            if _warte_und_beende_diskussion_falls_noetig():
                break
            if browser_stationen.muss_antworten(_verlaufsblasen(page), beantwortet):
                beantwortet += 1
                hinweis = browser_stationen.HINWEIS_NACHFRAGE
                continue
            break

        bot_vorher = sum(1 for b in _verlaufsblasen(page) if b.get("von") == "bot")
        protokoll = _aktion_ausfuehren(page, aktion)
        aktion_gescheitert = protokoll.get("art") in ("fehlgeschlagen", "unbekannt")
        if aktion_gescheitert:
            # Nichts hat sich getan -- keine Antwort- und keine warte_bis-
            # Wartezeit (sonst 600 s je Fehlgriff, Lauf 2 vom 06.10.).
            warte = {"fertig": True, "sekunden": 0.0, "ohne_hinweis": False}
        else:
            warte = browser_aktionen.warte_auf_antwort(
                page, geduld_s=min(station.geduld_s, max(1.0, ende_zeit - time.monotonic())))

        _warte_und_beende_diskussion_falls_noetig()
        if station.diskussion:
            if _aufnahme_laeuft(page, station.aufnahme):
                diskussion_lief = True
            elif diskussion_lief:
                diskussion_vorbei = True

        if (leitbilder and station.leitbild_mitte and not mitte_genommen
                and not station.zuhoeren_s
                and page.locator(".leiste button:visible, #kalibrierung-start:visible").count()):
            mitte_genommen = bool(leitbilder.nimm(page, station.phase, station.leitbild_mitte))

        nach = mitschnitt.screenshot_pfad(station.phase, f"{station.schluessel}-nach")
        nach.write_bytes(browser_elemente.bildschirmfoto(page))
        screenshots.append(nach)
        nachher = browser_mitschnitt.datenstand(db_pfad, chat_id)
        if station.warte_bis is not None and not aktion_gescheitert:
            # Task 2 (BRIEF p57): erst NACH der normalen Wartung
            # (``warte_auf_antwort`` oben) -- die deckt den sichtbaren Teil
            # ab (``#tippt``), ``warte_bis`` den unsichtbaren Hintergrund-
            # Thread (Fakt 5).
            #
            # Review-Fix (06.10.2026): ODER-verknuepft mit
            # ``_hat_sich_veraendert(vorher, ...)`` -- ``vorher`` ist hier
            # noch der Stand VOR dieser Aktion (die Zuweisung ``vorher =
            # nachher`` unten kommt erst danach). Ohne diese Ergaenzung
            # wartet eine mehrschrittige Bestaetigungsschleife
            # (``p5-szenen``/``p6-szenen``/``p7-szenen``) auf JEDEM
            # Zwischenschritt die volle ``geduld_s``, weil deren
            # ``warte_bis`` erst auf dem LETZTEN Schritt wahr wird --
            # obwohl der Hintergrund-Thread dieses Schritts laengst
            # irgendetwas im Datenstand veraendert hat (neuer Prueflauf,
            # neu geschriebene Szene).
            station_praedikat = station.warte_bis
            vorher_fuer_warte_bis = vorher
            nachher = _warte_bis(
                page,
                lambda s: station_praedikat(s)
                or _hat_sich_veraendert(vorher_fuer_warte_bis, s),
                lambda: browser_mitschnitt.datenstand(db_pfad, chat_id),
                min(station.geduld_s, max(1.0, ende_zeit - time.monotonic())),
                ruhe_s=WARTE_RUHE_S,
                bot_antwort_da=lambda bv=bot_vorher: sum(
                    1 for b in _verlaufsblasen(page) if b.get("von") == "bot") > bv)
        db_diff = browser_mitschnitt.unterschied(vorher, nachher)
        vorher = nachher
        _zaehler_addieren(zaehler_summe, browser_zaehler.alle(page))
        if beobachter:
            beobachter.messe()
        mitschnitt.schritt(
            phase=station.phase, screenshot_vorher=vor, screenshot_nachher=nach,
            elemente=elemente, aktion=protokoll, begruendung=aktion.get("begruendung", ""),
            antwort=warte, db_diff=db_diff, station=station.schluessel)

        schleife = waechter.pruefe(aktion, protokoll)
        if schleife is not None:
            schleifenbefunde.append({
                "schluessel": schleife[0],
                "text": f"Station {station.schluessel} beendet: {schleife[0]} "
                        f"({waechter.schwelle}x gescheitert). Fehler: {schleife[1]}"})
            break

        aktiv = _aktive_phase_nummer(page)
        if station.endet_bei_phasenwechsel and aktiv is not None and aktiv > station.phase:
            # I4 (Fix round 1): GENAU der Moment, in dem der Wechsel in die
            # naechste Phase sichtbar wird -- Grundlage fuer
            # ``_teile_bereich_am_phasenwechsel``, damit eine Antwort NACH
            # dem Wechsel nicht noch als diese (die alte) Phase zaehlt.
            # P34 Runde 1, C1: die Grenze ist der Zeitpunkt des Wechsels
            # (``phase_gesetzt_am``), nicht "jetzt" -- sonst zaehlte der
            # schon gebuchte Phase-4-Einstieg noch als Phase 3.
            phasenwechsel_aufruf_id = _aufruf_id_bei_phasenwechsel(db_pfad, chat_id)
            break
        if station.diskussion and diskussion_vorbei:
            break

    stand = browser_mitschnitt.datenstand(db_pfad, chat_id)
    fertig = station.fertig(stand) if station.fertig else True
    if not fertig and station.endet_bei_phasenwechsel:
        ziel = browser_stationen.notweg_ziel(station.phase, _aktive_phase_nummer(page))
        if ziel is not None and ziel <= phasen.LETZTE:
            _loese_phasenwechsel_aus(basis_url, token, ziel)
            fallback = True
            schleifenbefunde.append({
                "schluessel": f"phase_erzwungen:{station.phase}->{ziel}",
                "text": f"Harness hat Phase {ziel} per Endpunkt erzwungen, weil Station "
                        f"{station.schluessel} ihr Ziel nicht erreichte -- Folgezustand "
                        f"(fehlende Szenen/Daten) ist Harness-Artefakt, kein Produktbefund.",
                "schwere": "mittel"})
    if leitbilder and station.leitbild_ende:
        if station.leitbild_tab:
            browser_aktionen.fuehre_aus(page, {"type": "tab", "name": station.leitbild_tab})
        leitbilder.nimm(page, station.phase, station.leitbild_ende)
        if station.leitbild_tab:
            browser_aktionen.fuehre_aus(page, {"type": "tab", "name": "chat"})
    if leitbilder and beobachter and station.leitbild_beobachter:
        leitbilder.nimm(beobachter.page, station.phase, station.leitbild_beobachter,
                        geraet="handy")
    return {"schritte": schritte, "nachfragen_beantwortet": beantwortet,
            "offene_fragen": offene, "fertig": fertig, "fallback_benutzt": fallback,
            "zaehler_summe": zaehler_summe, "screenshots_nach": screenshots,
            "phasenwechsel_aufruf_id": phasenwechsel_aufruf_id,
            "pause_resume_ok": pause_resume_ok, "schleifenbefunde": schleifenbefunde}


#: Wie lange nach dem Senden von ``station.sage`` hoechstens auf eine neue
#: Bot-Blase gewartet wird (dieselbe Geduld wie fuer jede Persona-Aktion).
SAGE_GEDULD_S = browser_aktionen.ANTWORT_GEDULD_S


def _bot_texte(page) -> list[str]:
    return [b["text"] for b in _verlaufsblasen(page) if b.get("von") == "bot"]


def _sende_und_lies_antwort(page, text: str, geduld_s: float = SAGE_GEDULD_S) -> str:
    """Schickt ``text`` so, wie die Persona tippt (``type_send`` aus
    ``browser_aktionen``), und liefert die neuen Bot-Blasen (ohne
    Systemzeilen) als Text -- leer, wenn binnen ``geduld_s`` nichts kommt."""
    vorher = len(_bot_texte(page))
    browser_aktionen.fuehre_aus(page, {"type": "type_send", "text": text})
    browser_aktionen.warte_auf_antwort(page)
    ende = time.monotonic() + geduld_s
    while True:
        neu = [b for b in _verlaufsblasen(page) if b.get("von") == "bot"][vorher:]
        texte = [b["text"] for b in neu if b.get("typ") != "system" and b["text"]]
        if (texte and not browser_aktionen.laeuft_sichtbar(page)) or time.monotonic() >= ende:
            return "\n".join(texte)
        page.wait_for_timeout(500)


def _diskussions_audio(station, lauf_verzeichnis: Path) -> tuple[Path, int]:
    """WAV fuer ``station.diskussion`` (``diskussionen.DISKUSSIONEN``) und
    die Zuhoerdauer: ``station.zuhoeren_s`` oder WAV-Dauer + 5 s."""
    import math

    from simulation.diskussionen import DISKUSSIONEN
    from simulation.erzeuge_diskussion_audio import dauer_s, erzeuge

    disk = DISKUSSIONEN[station.diskussion]
    wav = Path(lauf_verzeichnis) / f"diskussion-{disk.name}.wav"
    erzeuge(disk.datei, wav, ende_pause_s=disk.ende_pause_s)
    return wav, station.zuhoeren_s or int(math.ceil(dauer_s(wav))) + 5


def _lies_p1(db_pfad: str, chat_id: int) -> browser_invarianten.P1Stand:
    with browser_invarianten.oeffne_lesend(db_pfad) as conn:
        return browser_invarianten.lese_p1_stand(conn, chat_id)


def _lies_p34(db_pfad: str, chat_id: int) -> browser_invarianten.P34Stand:
    with browser_invarianten.oeffne_lesend(db_pfad) as conn:
        return browser_invarianten.lese_p34_stand(conn, chat_id)


def _max_aufruf_id(db_pfad: str) -> int:
    """Hoechste ``aufruf.id`` -- read-only, wie ``_modell_lesen``: fehlt die
    Tabelle (eine ganz frische Datenbank), ist das Ergebnis 0 statt ein
    Fehler. Grundlage von ``aufruf_bereiche`` (``_modellwahl``-Haken,
    Task 2c): welche Aufrufe in welche Station/Phase fielen."""
    try:
        with browser_invarianten.oeffne_lesend(db_pfad) as conn:
            return conn.execute("SELECT COALESCE(MAX(id), 0) FROM aufruf").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def _kosten_bisher(db_pfad: str) -> float:
    """Summe ueber ALLE Laeufe, die je ``aufruf.kosten_chf`` in diese
    ``sim.db`` geschrieben haben (Task 2, BRIEF p57) -- read-only, wie
    ``_max_aufruf_id``: fehlt die Tabelle, ist das Ergebnis 0.0 statt ein
    Fehler. Grundlage von ``--kosten-stopp`` (Plan-Vorgabe: hoechstens drei
    bezahlte Laeufe, Stopp sobald die Summe UEBER ALLE Laeufe > 1,50 CHF)."""
    try:
        with browser_invarianten.oeffne_lesend(db_pfad) as conn:
            zeile = conn.execute("SELECT COALESCE(SUM(kosten_chf), 0) FROM aufruf").fetchone()
            return float(zeile[0] or 0.0)
    except sqlite3.OperationalError:
        return 0.0


def _kostenstopp_erreicht(db_pfad: str, kosten_stopp: float | None) -> bool:
    """Ob die bisherige Kostensumme ueber ``kosten_stopp`` liegt --
    ``kosten_stopp=None`` (Vorgabe) heisst: kein Deckel, nie ein Abbruch.
    ``>``, nicht ``>=``: ein Lauf, der GENAU den Deckel erreicht, darf noch
    zu Ende laufen -- erst ein Ueberschreiten stoppt den naechsten Schritt."""
    if kosten_stopp is None:
        return False
    return _kosten_bisher(db_pfad) > kosten_stopp


def _aufruf_id_bei_phasenwechsel(db_pfad: str, chat_id: int) -> int:
    """Hoechste ``aufruf.id``, die spaetestens beim Setzen der aktuellen
    Phase (``arbeitsstand.phase_gesetzt_am``) gebucht war -- die Grenze fuer
    ``_teile_bereich_am_phasenwechsel``.

    P34 Runde 1, C1 (Ursache Werkzeug, Lauf 205532): vorher stand hier
    ``_max_aufruf_id`` NACH ``warte_auf_antwort`` -- da war der
    Phase-4-Einstieg (Opus) schon gebucht und zaehlte als Phase 3
    (falsches ``p3_gespraech_ueber_opus``). Verglichen wird als Zeitpunkt,
    nicht als String: ``aufruf.erstellt_am`` ist sekundengenau,
    ``phase_gesetzt_am`` mikrosekundengenau. Ohne Zeitstempel (alte Gruppe)
    oder bei einem Lesefehler bleibt es beim bisherigen ``_max_aufruf_id``.

    Grenze des Verfahrens (P34 Runde 2): ``arbeitsstand`` haelt nur den
    LETZTEN ``phase_gesetzt_am``, es gibt keinen Phasenverlauf in der
    Datenbank. Springt die Gruppe innerhalb eines Schritts ueber Phase 4
    hinaus (3 -> 4 -> 5), ist die Grenze der Wechsel in die spaetere Phase,
    nicht der in Phase 4 -- Aufrufe aus dem kurzen Phase-4-Stueck zaehlen
    dann als Phase 3. Der Split nimmt ausserdem immer ``station.phase + 1``
    als Folgephase."""
    from datetime import datetime

    try:
        with browser_invarianten.oeffne_lesend(db_pfad) as conn:
            zeile = conn.execute(
                "SELECT phase_gesetzt_am FROM arbeitsstand WHERE chat_id = ?", (chat_id,),
            ).fetchone()
            gesetzt = zeile[0] if zeile else None
            if not gesetzt:
                return _max_aufruf_id(db_pfad)
            grenze = datetime.fromisoformat(gesetzt)
            ergebnis = 0
            for aufruf_id, erstellt_am in conn.execute(
                    "SELECT id, erstellt_am FROM aufruf ORDER BY id"):
                if datetime.fromisoformat(erstellt_am) <= grenze:
                    ergebnis = max(ergebnis, aufruf_id)
            return ergebnis
    except (sqlite3.OperationalError, ValueError, TypeError):
        return _max_aufruf_id(db_pfad)


def _teile_bereich_am_phasenwechsel(aufruf_bereiche: dict, stationen_phase: dict,
                                    schluessel: str, phase: int, von: int, bis: int,
                                    wechsel_aufruf_id: int | None) -> None:
    """Schreibt ``(von, bis)`` in ``aufruf_bereiche[schluessel]`` -- AUSSER
    der Aufruf-Bereich dieser Station reicht ueber den tatsaechlichen
    Phasenwechsel hinweg (``wechsel_aufruf_id`` zwischen ``von`` und ``bis``,
    siehe ``_fuehre_station_aus``, ``station.endet_bei_phasenwechsel``):
    dann wird die Station in zwei Buckets gesplittet -- der Teil VOR dem
    Wechsel bleibt bei ``phase``, der Teil DANACH wandert unter einem
    eigenen Schluessel (``<schluessel>:nach_phasenwechsel``) in die naechste
    Phase. Ohne diesen Split zaehlte eine Antwort, die faktisch schon in
    Phase 4 lief, noch als Phase 3 -- genau die Station, die den Wechsel
    selbst ausloest (``p3-uebergang``), ist dafuer anfaellig (I4, Review
    05.10.2026, Fix round 1).

    P34 Runde 2 (C1 Rest): die Bedingung ist ``von <= wechsel < bis``.
    Wechselt die Gruppe, bevor die Station einen Aufruf gebucht hat, ist die
    Grenze genau ``von``; der Vorher-Bereich ``(von, von)`` ist dann leer und
    der ganze Bereich zaehlt als naechste Phase (vorher: alles Phase 3 ->
    falsches ``p3_gespraech_ueber_opus``). ``wechsel == bis`` (kein Aufruf
    nach dem Wechsel) und ``wechsel < von`` splitten nicht."""
    if wechsel_aufruf_id is not None and von <= wechsel_aufruf_id < bis:
        aufruf_bereiche[schluessel] = (von, wechsel_aufruf_id)
        nach_schluessel = f"{schluessel}:nach_phasenwechsel"
        aufruf_bereiche[nach_schluessel] = (wechsel_aufruf_id, bis)
        stationen_phase[nach_schluessel] = phase + 1
    else:
        aufruf_bereiche[schluessel] = (von, bis)


def _oeffne_gruppe(page, basis_url: str, token: str) -> None:
    page.goto(f"{basis_url}/g/{token}")
    page.wait_for_selector("#verlauf")


def fuehre_stationen(page, context, *, basis_url: str, token: str, db_pfad: str,
                     chat_id: int, persona_client, judge_client, geraet: str,
                     persona_name: str, stationen: tuple, lauf_verzeichnis: Path,
                     beobachter=None, leitbilder=None, meta: dict | None = None,
                     gruppen: list | None = None,
                     warte=browser_invarianten.warte_nach_diskussion,
                     hole_prompt=None, wechsle_audio=None,
                     kosten_stopp: float | None = None,
                     max_minuten: float = LAUF_MAX_MINUTEN,
                     max_station_s: float = STATION_MAX_S) -> dict:
    """Die Stationsmotor-Engine des Abnahmelaufs Phase 1-2 (04.10.2026):
    Station fuer Station aus ``browser_stationen.STATIONEN``, mit einer
    eigenen Erklaernote je Station (Pflichtpunkt 1). Schreibt
    ``lauf_verzeichnis / "ergebnis.json"`` und liefert dasselbe Dict.

    ``meta`` (z. B. ``{"app_wurzel": ..., "app_commit": ...}``, Task 1) wird
    unveraendert in dieses Dict gemischt -- so bleibt im Ergebnis erkennbar,
    aus welchem Checkout die App dieses Laufs gestartet wurde.

    Task 6 (Karte t_fc2c1bfa): nach jeder Station laufen die Pruef-Haken aus
    ``station.pruefung`` (``browser_pruefhaken``), dazu IMMER die
    Symptomregel -- eine nicht erreichte oder mit Ausnahme abgebrochene
    Station wird ein Befund "hoch". Alle Befunde landen in Reihenfolge in
    ``ergebnis["invarianten"]``, neben dem Richter (``top_befunde``).

    - ``gruppen``: alle Gruppen des Stacks (``browser_umgebung.Gruppe``),
      Vorgabe nur die eine aus ``token``/``chat_id``. Eine Station mit
      ``gruppe > 1`` oeffnet DIESELBE ``page`` auf deren URL und kehrt danach
      auf Gruppe 1 zurueck (ein Geraet, zwei Gruppen).
    - ``warte``/``hole_prompt``: Einhaengepunkte fuer ``nach_ende`` und
      ``wissen`` (Tests geben Attrappen).
    - ``wechsle_audio(wav) -> (page, context)``: startet den Persona-Browser
      mit ``wav`` als Mikrofon neu (Chromium liest die Fake-Audio-Datei nur
      beim Start), vor jeder Station mit ``diskussion``; er installiert
      ``browser_zaehler.installiere_messung`` auf dem neuen Kontext selbst,
      vor ``new_page``. Ohne ihn bleibt die bisherige Audioquelle.
    - ``nach_ende`` wartet direkt nach dem Harness-Klick auf "Discussion
      done" (``nach_klick``); ``ergebnis.json`` wird in jedem Fall
      geschrieben (``finally``).
    - ``kosten_stopp`` (Task 2, BRIEF p57): zwischen zwei Stationen wird
      Σ ``aufruf.kosten_chf`` dieser ``sim.db`` gelesen (``_kosten_bisher``);
      liegt sie darueber, endet der Lauf VOR der naechsten Station sauber
      (``ergebnis["abbruch"] = "kostenstopp"``, kein Absturz) -- die schon
      gelaufenen Stationen bleiben im Ergebnis stehen. ``None`` (Vorgabe):
      kein Deckel."""
    from simulation.browser_umgebung import Gruppe

    lauf_verzeichnis = Path(lauf_verzeichnis)
    mitschnitt = browser_mitschnitt.Mitschnitt(
        lauf_verzeichnis, f"{geraet}-{persona_name}", geraet)
    gruppen = list(gruppen or [Gruppe(token=token, chat_id=chat_id)])
    browser_zaehler.installiere_messung(context)
    _oeffne_gruppe(page, basis_url, token)
    ergebnisse: list[dict] = []
    invarianten: list[dict] = []
    notizen: list[str] = []
    fehlgeschlagen_bei = None
    entwickler_merkmale: set[str] = set()
    # Wie viele Bot-Blasen schon da waren, BEVOR diese Station lief -- die
    # Erklaernote (Pflichtpunkt 1) soll nur die wirklich NEUEN Bot-Blasen
    # dieser Station beurteilen, nicht noch einmal die der vorigen (sonst
    # waechst die Zitatbasis mit jeder Station und eine fruehe Erklaerung
    # wird mehrfach bewertet).
    bot_anzahl_vorher = 0
    ergebnis: dict = {}
    # Task 2c: welche ``aufruf``-Zeilen in welche Station/Phase fielen --
    # Grundlage des ``modellwahl``-Hakens (Phase-3/4-Bereich = Vereinigung
    # der Bereiche aller Stationen dieser Phase). Dieselben Dicts wandern in
    # JEDE ``PruefKontext`` dieses Laufs (Referenz, nicht Kopie), damit ein
    # spaeterer Haken den vollen bisherigen Stand sieht.
    aufruf_bereiche: dict[str, tuple[int, int]] = {}
    stationen_phase: dict[str, int] = {}
    #: M2 (Review 05.10.2026, Fix round 2): wie ``aufruf_bereiche`` --
    #: dasselbe ``set``-Objekt wandert per Referenz in jede ``PruefKontext``
    #: dieses Laufs, siehe ``browser_pruefhaken._modellwahl``.
    modellwahl_phasen_geprueft: set[int] = set()
    #: P57 Task 3: id -> Hash(``szenenfassung.volltext``) -- dasselbe
    #: Dict-Objekt wandert per Referenz in jede ``PruefKontext`` dieses
    #: Laufs (wie ``aufruf_bereiche`` oben), siehe
    #: ``browser_pruefhaken._sprung``/``PruefKontext.szenenfassung_hashes_p57``.
    szenenfassung_hashes_p57: dict = {}
    #: Task 2 (BRIEF p57): None, solange kein Kostendeckel gegriffen hat --
    #: landet unveraendert in ``ergebnis["abbruch"]``.
    abbruch: str | None = None
    lauf_frist = time.monotonic() + max_minuten * 60.0
    try:
        for index, station in enumerate(stationen):
            if index > 0 and time.monotonic() >= lauf_frist:
                abbruch = "zeitdeckel"
                break
            # Nur ZWISCHEN zwei Stationen pruefen (nicht vor der ersten): ein
            # frischer Lauf darf immer mindestens einen Schritt versuchen,
            # auch wenn der Deckel sehr knapp gesetzt ist.
            if index > 0 and _kostenstopp_erreicht(db_pfad, kosten_stopp):
                abbruch = "kostenstopp"
                break
            befunde: list[browser_invarianten.Befund] = []
            stationen_phase[station.schluessel] = station.phase
            kontext = PruefKontext(
                db_pfad=db_pfad, gruppen=gruppen, page=page, beobachter=beobachter,
                hole_prompt=hole_prompt, warte=warte, lauf_verzeichnis=lauf_verzeichnis,
                beobachter_start=len(beobachter.verlauf) if beobachter else 0, notizen=notizen,
                aufruf_bereiche=aufruf_bereiche, stationen_phase=stationen_phase,
                modellwahl_phasen_geprueft=modellwahl_phasen_geprueft,
                szenenfassung_hashes_p57=szenenfassung_hashes_p57)
            kontext.sende = lambda text, k=kontext: _sende_und_lies_antwort(k.page, text)
            lauf = None
            von_aufruf = _max_aufruf_id(db_pfad)
            aufruf_bereiche[station.schluessel] = (von_aufruf, von_aufruf)
            try:
                gruppe = gruppen[station.gruppe - 1]
                if station.diskussion:
                    wav, zuhoeren_s = _diskussions_audio(station, lauf_verzeichnis)
                    station = dataclasses.replace(station, zuhoeren_s=zuhoeren_s)
                    if wechsle_audio is not None:
                        # H1 (Abnahme P3-4, 06.10.2026): eine Sitzung, die
                        # die Persona in einer FRUEHEREN Station ohne
                        # eigenes ``diskussion`` schon gestartet hat (z. B.
                        # ``p3-eintritt``, "Start interview" aus Neugier),
                        # erst sauber beenden und auf dem Server ankommen
                        # lassen -- SONST killt der folgende Browser-
                        # Neustart sie, bevor ein einziges Segment
                        # hochgeladen ist (Lauf 042439: 0x POST /chat/audio
                        # im ganzen Interviewfenster).
                        beendete_art = _beende_laufende_aufnahme(page)
                        if beendete_art is not None:
                            _warte_auf_aufnahme_ende(db_pfad, gruppe.chat_id, beendete_art)
                        # ``wechsle_audio`` installiert die Messung selbst
                        # (vor ``new_page``), siehe ``main``.
                        page, context = wechsle_audio(wav)
                        kontext.page = page
                if station.gruppe != 1:
                    _oeffne_gruppe(page, basis_url, gruppe.token)
                nach_klick = None
                if "nach_ende" in station.pruefung:
                    # Rueckfall, falls der Harness "Discussion done" nicht
                    # selbst drueckt; ``vor_ende`` ersetzt ihn direkt vor dem
                    # Klick, ``nach_klick`` wartet direkt danach.
                    kontext.vorher = _lies_p1(db_pfad, gruppe.chat_id)

                    def nach_klick(k=kontext, st=station, cid=gruppe.chat_id):
                        warte_nach_klick(st, k, cid)
                elif "nach_interview" in station.pruefung or "nach_brainstorm" in station.pruefung:
                    # Dasselbe Muster fuer Interview/Brainstorm (Padua live-
                    # reif Phase 3+4, Task 2c): ``vor_ende`` liest zusaetzlich
                    # ``vor_ende_p34``, ``nach_klick`` wartet mit
                    # ``browser_invarianten.warte_auf``.
                    kontext.vorher_p34 = _lies_p34(db_pfad, gruppe.chat_id)
                    ist_brainstorm = "nach_brainstorm" in station.pruefung
                    frist_s = (browser_invarianten.FRIST_NACH_BRAINSTORM_S if ist_brainstorm
                              else browser_invarianten.FRIST_NACH_INTERVIEW_S)
                    # M3 (Review 05.10.2026, Fix round 2): der Interview-Pfad
                    # braucht laenger als die kurze Vorgabe
                    # (GRACE_NACH_SIGNAL_S < aufnahme.NACHHOL_INTERVALL_S) --
                    # siehe browser_invarianten.GRACE_NACH_INTERVIEW_S.
                    grace_s = (browser_invarianten.GRACE_NACH_SIGNAL_S if ist_brainstorm
                              else browser_invarianten.GRACE_NACH_INTERVIEW_S)

                    def _pruefe_p34(stand, k=kontext, st=station, brainstorm=ist_brainstorm):
                        if brainstorm:
                            return browser_invarianten.pruefe_nach_brainstorm(
                                k.vorher_p34, k.vor_ende_p34 or k.vorher_p34, stand, st.schluessel)
                        return browser_invarianten.pruefe_nach_interview(k.vorher_p34, stand, st.schluessel)

                    def _ende_p34(stand, k=kontext, brainstorm=ist_brainstorm):
                        # I2 (Fix round 1): das Positiv-Signal, hinter dem
                        # ``warte_auf`` erst noch die Gnadenfrist abwartet,
                        # bevor es final prueft -- sonst verdeckt eine fruehe
                        # "saubere" Zwischenmessung ein spaeteres Duplikat.
                        if brainstorm:
                            return browser_invarianten.hat_neue_karte(
                                k.vor_ende_p34 or k.vorher_p34, stand)
                        return browser_invarianten.hat_neue_statuszeile(k.vorher_p34, stand)

                    def nach_klick(k=kontext, cid=gruppe.chat_id, frist_s=frist_s, pruefe=_pruefe_p34,
                                   ende=_ende_p34, grace_s=grace_s):
                        k.ergebnis_p34 = k.warte_p34(
                            lambda: _lies_p34(db_pfad, cid), pruefe, frist_s=frist_s, ende=ende,
                            grace_s=grace_s)

                def vor_ende(k=kontext, cid=gruppe.chat_id):
                    k.vorher = _lies_p1(db_pfad, cid)
                    k.vor_ende_p34 = _lies_p34(db_pfad, cid)

                lauf = _fuehre_station_aus(
                    page, persona_client, mitschnitt, station, basis_url=basis_url,
                    token=gruppe.token, db_pfad=db_pfad, chat_id=gruppe.chat_id,
                    persona_name=persona_name, beobachter=beobachter,
                    leitbilder=leitbilder, vor_ende=vor_ende, nach_klick=nach_klick,
                    max_station_s=max_station_s, frist=lauf_frist)
                for sb in lauf.get("schleifenbefunde", []):
                    befunde.append(browser_invarianten.Befund(
                        sb["schluessel"], station.schluessel, sb["text"],
                        sb.get("schwere", "hoch")))
            except Exception as fehler:
                log.exception("Station %s ist gescheitert", station.schluessel)
                fehlgeschlagen_bei = fehlgeschlagen_bei or station.schluessel
                befunde.append(befund_ausnahme(station, fehler))
            finally:
                # M1 (Review 05.10.2026, Fix round 1): vorher stand diese
                # Zeile NUR im try-Block, direkt nach einem erfolgreichen
                # ``_fuehre_station_aus`` -- ein Aufruf, der WAEHREND einer
                # gescheiterten Station entstand, blieb dann fuer immer
                # ausserhalb jedes Bereichs (der ``modellwahl``-Haken einer
                # spaeteren Phase sah ihn nie). ``finally`` deckt beide Faelle.
                _teile_bereich_am_phasenwechsel(
                    aufruf_bereiche, stationen_phase, station.schluessel, station.phase,
                    von_aufruf, _max_aufruf_id(db_pfad),
                    lauf.get("phasenwechsel_aufruf_id") if lauf else None)
            # Die Haken laufen auch nach einer Ausnahme: ein Harness-Fehler
            # darf ein App-Symptom nicht verdecken (Symptomregel).
            # Coverage-Luecke Pause/Resume (p34-abnahme-verfahren.md §3):
            # ``kontext.lauf`` traegt ``_fuehre_station_aus``s Rueckgabe
            # (u. a. ``pause_resume_ok``) in den ``pause_resume``-Haken.
            kontext.lauf = lauf
            befunde += fuehre_pruefungen(station, kontext)
            if lauf is not None and station.sage and "wissen" not in station.pruefung:
                try:
                    _sende_und_lies_antwort(page, station.sage)
                except Exception as fehler:
                    befunde.append(befund_ausnahme(station, fehler))
            if station.gruppe != 1:
                try:
                    (lauf_verzeichnis / f"zweite-gruppe-{station.schluessel}.png").write_bytes(
                        browser_elemente.bildschirmfoto(page))
                    _oeffne_gruppe(page, basis_url, gruppen[0].token)
                except Exception as fehler:
                    log.exception("Rueckweg auf Gruppe 1 nach %s gescheitert", station.schluessel)
                    befunde.append(befund_ausnahme(station, fehler))
            if lauf is not None:
                befunde += browser_invarianten.pruefe_station_erreicht(
                    station.schluessel, lauf["fertig"])
            invarianten.extend(b.als_dict() for b in befunde)
            leer = {"schluessel": station.schluessel, "phase": station.phase,
                    "schritte": 0, "nachfragen_beantwortet": 0,
                    "offene_fragen": [], "fertig": False,
                    "fallback_benutzt": False, "note": None, "befunde": [],
                    "zaehler_summe": {}, "screenshots_fuer_bericht": [],
                    "note_erklaerung": None, "schwaechstes_zitat": "",
                    "vorschlag": "", "invarianten": [b.schluessel for b in befunde]}
            if lauf is None:
                ergebnisse.append(leer)
                continue
            # Nachbereitung (Merkmale, Blasen, Richter): ein Fehler hier darf
            # weder den Lauf noch ergebnis.json kosten -- er wird ein Befund.
            try:
                entwickler_merkmale.update(_entwickler_meta(page))
                repraesentativ = _repraesentativ(lauf["screenshots_nach"])
                alle_bot_texte = _bot_texte(page)
                bot_texte = alle_bot_texte[bot_anzahl_vorher:]
                bot_anzahl_vorher = len(alle_bot_texte)
                bewertung = browser_judge.bewerte_phase(
                    judge_client, station.phase,
                    f"{phasen.kurzname(station.phase)} / {station.schluessel}",
                    [p.read_bytes() for p in repraesentativ], [p.name for p in repraesentativ],
                    lauf["zaehler_summe"]) if not station.ohne_persona else {}
                erklaerung = browser_judge.bewerte_erklaerung(
                    judge_client, station.schluessel, bot_texte)
                ergebnisse.append({
                    "schluessel": station.schluessel, "phase": station.phase,
                    **{k: lauf[k] for k in ("schritte", "nachfragen_beantwortet", "offene_fragen",
                                            "fertig", "fallback_benutzt", "zaehler_summe")},
                    "note": bewertung.get("note"), "befunde": bewertung.get("befunde") or [],
                    "screenshots_fuer_bericht": [p.name for p in repraesentativ],
                    "note_erklaerung": erklaerung.get("note_erklaerung"),
                    "schwaechstes_zitat": erklaerung.get("schwaechstes_zitat", ""),
                    "vorschlag": erklaerung.get("vorschlag", ""),
                    **({k: lauf[k] for k in ("bot_nachricht", "kalibrierung_sichtbar",
                                             "zuhoeren_laeuft", "leertext_sichtbar") if k in lauf}),
                    "invarianten": [b.schluessel for b in befunde],
                })
            except Exception as fehler:
                log.exception("Nachbereitung von Station %s gescheitert", station.schluessel)
                fehlgeschlagen_bei = fehlgeschlagen_bei or station.schluessel
                befund = browser_invarianten.Befund(
                    "pruefung_gescheitert:nachbereitung", station.schluessel,
                    f"Nachbereitung (Merkmale/Blasen/Richter) an Station {station.schluessel} "
                    f"warf {type(fehler).__name__}: {fehler}")
                invarianten.append(befund.als_dict())
                ergebnisse.append({**leer, "fertig": lauf["fertig"],
                                   "invarianten": leer["invarianten"] + [befund.schluessel]})
    finally:
        # Immer schreiben -- auch wenn oben etwas Unerwartetes durchschlaegt
        # (die Ausnahme laeuft danach weiter nach oben).
        ergebnis = _schreibe_stationsergebnis(
            lauf_verzeichnis, beobachter=beobachter, db_pfad=db_pfad,
            persona_client=persona_client, judge_client=judge_client, geraet=geraet,
            persona_name=persona_name, ergebnisse=ergebnisse, invarianten=invarianten,
            notizen=notizen, entwickler_merkmale=entwickler_merkmale,
            fehlgeschlagen_bei=fehlgeschlagen_bei, meta=meta, abbruch=abbruch)
    return ergebnis


def _schreibe_stationsergebnis(lauf_verzeichnis: Path, *, beobachter, db_pfad, persona_client,
                               judge_client, geraet, persona_name, ergebnisse, invarianten,
                               notizen, entwickler_merkmale, fehlgeschlagen_bei, meta,
                               abbruch: str | None = None) -> dict:
    """Baut und schreibt ``ergebnis.json`` -- jeder Teil mit eigenem
    Rueckfall, damit die Datei auch nach einem kaputten Beobachter oder einer
    unlesbaren DB entsteht."""
    try:
        beob = beobachter.ergebnis() if beobachter else {
            "board_verlauf": [], "beobachter_neu_geladen": False, "board_bestanden": False}
    except Exception as fehler:
        log.exception("Beobachter-Ergebnis nicht lesbar")
        beob = {"board_verlauf": list(getattr(beobachter, "verlauf", [])),
                "beobachter_neu_geladen": None, "board_bestanden": False}
        notizen.append(f"Beobachter-Ergebnis nicht lesbar: {type(fehler).__name__}: {fehler}")
    try:
        modelle = _modell_lesen(db_pfad)
    except Exception:
        log.exception("Modelle nicht lesbar")
        modelle = {}
    modelle["persona"] = getattr(persona_client, "modell", "?")
    modelle["judge"] = getattr(judge_client, "modell", "?")
    top = [{**b, "station": e["schluessel"]} for e in ergebnisse
           for b in e["befunde"] if b.get("schwere") == "hoch"]
    ergebnis = {"geraet": geraet, "persona": persona_name,
                "stationen_ergebnisse": ergebnisse, **beob,
                "entwickler_meta": sorted(entwickler_merkmale), "modelle": modelle,
                "top_befunde": top, "invarianten": invarianten,
                "pruef_notizen": notizen, "fehlgeschlagen_bei": fehlgeschlagen_bei,
                "db_pfad": db_pfad, "abbruch": abbruch, **(meta or {})}
    (lauf_verzeichnis / "ergebnis.json").write_text(
        json.dumps(ergebnis, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return ergebnis


def fuehre_lauf(
    page, context, *, basis_url: str, token: str, db_pfad: str, chat_id: int,
    persona_client, judge_client, geraet: str, persona_name: str,
    bis_phase: int, lauf_verzeichnis: Path, max_schritte_je_phase: int = 25,
    fallback_nach_schritten: int = 8,
) -> dict:
    """Die Browserlauf-Engine: Phase fuer Phase, bis ``bis_phase`` erreicht
    ist. Liest ``IT_WORKSHOP`` nirgends selbst -- der Aufrufer (``main()``
    oder ein Test) setzt die Umgebung, bevor diese Funktion laeuft.

    Liefert ein Dict mit ``phasen_ergebnisse`` (eine Zeile je Phase),
    ``top_befunde`` (die schwersten Befunde quer durch alle Phasen) und
    ``fehlgeschlagen_bei`` (die Nummer der ersten Phase, in der ein
    Richterlauf gescheitert ist -- oder ``None``, wenn alle glatt liefen).
    Eine gescheiterte Phase reisst die anderen nicht mit: der Lauf macht mit
    der naechsten weiter, wie ``simulation/lauf.py``s "ein Schritt darf
    scheitern"-Haltung."""
    mitschnitt = browser_mitschnitt.Mitschnitt(
        lauf_verzeichnis, f"{geraet}-{persona_name}", geraet,
    )
    browser_zaehler.installiere_messung(context)
    page.goto(f"{basis_url}/g/{token}")
    page.wait_for_selector("#verlauf")

    phasen_ergebnisse: list[dict] = []
    fehlgeschlagen_bei: int | None = None

    for aktuelle_phase in range(1, bis_phase + 1):
        zaehler_summe: dict[str, int] = {}
        fallback_benutzt = False
        screenshots_nach: list[Path] = []
        bewertung = {"note": None, "befunde": []}

        try:
            phase_ergebnis = _fuehre_phase_aus(
                page, persona_client, mitschnitt,
                aktuelle_phase=aktuelle_phase, basis_url=basis_url,
                token=token, db_pfad=db_pfad, chat_id=chat_id,
                persona_name=persona_name, max_schritte=max_schritte_je_phase,
                fallback_nach_schritten=fallback_nach_schritten,
            )
            zaehler_summe = phase_ergebnis["zaehler_summe"]
            fallback_benutzt = phase_ergebnis["fallback_benutzt"]
            screenshots_nach = phase_ergebnis["screenshots_nach"]
        except Exception:
            # Ein kaputter Schritt (Playwright-Timeout, geschlossene Seite,
            # ...) reisst nicht den ganzen Lauf mit -- die naechste Phase
            # bekommt trotzdem ihre Chance.
            log.exception("Phase %s ist gescheitert", aktuelle_phase)
            if fehlgeschlagen_bei is None:
                fehlgeschlagen_bei = aktuelle_phase
            phasen_ergebnisse.append({
                "nummer": aktuelle_phase, "name": phasen.kurzname(aktuelle_phase),
                "note": None, "befunde": [], "zaehler_summe": {},
                "fallback_benutzt": False, "screenshots_fuer_bericht": [],
            })
            continue

        repraesentativ = _repraesentativ(screenshots_nach)
        try:
            bewertung = browser_judge.bewerte_phase(
                judge_client, aktuelle_phase, phasen.kurzname(aktuelle_phase),
                [p.read_bytes() for p in repraesentativ],
                [p.name for p in repraesentativ], zaehler_summe,
            )
        except Exception:
            # ``browser_judge.bewerte_phase`` faengt Modellfehler bereits
            # selbst ab -- dieser Block ist zusaetzliche Vorsicht fuer alles,
            # was DAVOR scheitern koennte (z. B. eine kaputte Rubrik-Datei).
            log.exception("Richterlauf fuer Phase %s ist gescheitert", aktuelle_phase)
            if fehlgeschlagen_bei is None:
                fehlgeschlagen_bei = aktuelle_phase
            bewertung = {"note": None, "befunde": []}

        phasen_ergebnisse.append({
            "nummer": aktuelle_phase,
            "name": phasen.kurzname(aktuelle_phase),
            "note": bewertung.get("note"),
            "befunde": bewertung.get("befunde") or [],
            "zaehler_summe": zaehler_summe,
            "fallback_benutzt": fallback_benutzt,
            "screenshots_fuer_bericht": [p.name for p in repraesentativ],
        })

    modelle = _modell_lesen(db_pfad)
    modelle["persona"] = getattr(persona_client, "modell", "?")
    modelle["judge"] = getattr(judge_client, "modell", "?")

    top_befunde = []
    for phase in phasen_ergebnisse:
        for befund in phase.get("befunde") or []:
            if befund.get("schwere") == "hoch":
                top_befunde.append({**befund, "phase": phase["nummer"]})
    if len(top_befunde) < 5:
        for phase in phasen_ergebnisse:
            for befund in phase.get("befunde") or []:
                if befund.get("schwere") == "mittel":
                    top_befunde.append({**befund, "phase": phase["nummer"]})

    return {
        "phasen_ergebnisse": phasen_ergebnisse,
        "top_befunde": top_befunde,
        "fehlgeschlagen_bei": fehlgeschlagen_bei,
        "modelle": modelle,
    }


def lauf_verzeichnis_fuer(basis: Path, datum: str, geraet: str, persona: str,
                         stationen: str, jetzt: str) -> Path:
    """Der Laufordner-Name, eindeutig je Lauf (nicht nur je Tag/Geraet/
    Argumente) -- vorher wurde ``sim.db`` bei zwei Laeufen desselben Tages
    mit denselben Argumenten wiederverwendet. ``jetzt`` ist die Uhrzeit
    (``HHMMSS``), vom Aufrufer uebergeben, damit diese Funktion selbst keine
    Uhr braucht."""
    if stationen:
        name = f"{datum}-{geraet}-{persona}-{stationen}-{jetzt}"
    else:
        name = f"{datum}-{geraet}-{jetzt}"
    return basis / name


def _app_commit(app_wurzel: Path) -> str | None:
    """Der kurze Commit des App-Checkouts, aus dem der Stack gestartet
    wurde -- ``None`` bei jedem Fehler (kein Git-Repo, ``git`` fehlt, ...),
    nie eine Ausnahme nach oben."""
    try:
        lauf = subprocess.run(
            ["git", "-C", str(app_wurzel), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if lauf.returncode != 0:
        return None
    return lauf.stdout.strip() or None


def main() -> None:
    """Dünner CLI-Wrapper: baut den echten Stack, einen echten Opus-Klienten
    und einen echten Browser, ruft ``fuehre_lauf``, schreibt den Bericht.

    Liest NIE die Env-Datei selbst -- ``browser_umgebung.starte_bot`` gibt
    ihren Pfad nur an ein Bash-Skript weiter (siehe dort)."""
    import argparse
    import os
    import sys
    import time
    from datetime import datetime
    from pathlib import Path

    from playwright.sync_api import sync_playwright

    from interview_theater import db
    from simulation import browser_bericht, browser_umgebung
    from simulation.claude import Claude

    os.environ["IT_WORKSHOP"] = "padua-2026"

    zerleger = argparse.ArgumentParser(prog="python -m simulation.browser_lauf")
    zerleger.add_argument("--env-datei", default=os.environ.get("IT_SIM_ENV", ""))
    zerleger.add_argument("--geraet", choices=["handy", "laptop"], default="handy")
    zerleger.add_argument("--persona", choices=sorted(browser_persona.PERSONEN), default="student")
    zerleger.add_argument("--bis-phase", type=int, default=7)
    zerleger.add_argument("--bericht", action="store_true")
    zerleger.add_argument("--stationen", choices=sorted(browser_stationen.STATIONEN))
    zerleger.add_argument("--leitbilder", action="store_true",
                          help="nur Schlusslauf: Leitbilder nach docs/guide/bilder")
    zerleger.add_argument("--app-wurzel", type=Path, default=browser_umgebung.WURZEL,
                          help="Checkout, aus dem Web und Bot gestartet werden "
                               "(Vorgabe: dieser Harness-Checkout)")
    zerleger.add_argument("--kosten-stopp", type=float, default=None,
                          help="Bricht VOR der naechsten Station ab, sobald "
                               "Sigma aufruf.kosten_chf dieser sim.db diesen "
                               "Wert ueberschreitet (nur Stationsmodus)")
    zerleger.add_argument("--max-minuten", type=float, default=LAUF_MAX_MINUTEN,
                          help="Zeitdeckel fuer den ganzen Stationslauf (Minuten, "
                               "Vorgabe 120); danach endet er sauber mit Bericht")
    argumente = zerleger.parse_args()

    if not argumente.env_datei:
        print("Fehlende Env-Datei: --env-datei oder IT_SIM_ENV", file=sys.stderr)
        raise SystemExit(1)

    app_wurzel = argumente.app_wurzel
    if not (app_wurzel / "interview_theater").is_dir():
        print(f"--app-wurzel ohne interview_theater/: {app_wurzel}", file=sys.stderr)
        raise SystemExit(1)

    datum = time.strftime("%Y-%m-%d")
    jetzt = datetime.now().strftime("%H%M%S")
    lauf_verzeichnis = lauf_verzeichnis_fuer(
        Path("simulation/browser_laeufe"), datum, argumente.geraet, argumente.persona,
        argumente.stationen or "", jetzt)
    lauf_name = lauf_verzeichnis.name
    stationsliste = browser_stationen.STATIONEN[argumente.stationen] if argumente.stationen else ()
    # Padua live-reif Phase 3+4 (Task 2): die Stationsliste ``p34`` startet
    # in Phase 3 -- ``bereite_vor`` (in ``starte_stack``) fuellt nur den
    # Stand davor, den Phasenwechsel selbst loest dieser Block ueber den
    # echten Endpunkt aus (Eintrittsnachricht wie live).
    startphase = browser_stationen.STARTPHASE.get(argumente.stationen or "", 1)
    stack = browser_umgebung.starte_stack(
        argumente.env_datei, lauf_verzeichnis, app_wurzel=app_wurzel,
        gruppen=max((st.gruppe for st in stationsliste), default=1), startphase=startphase)
    try:
        if startphase > 1:
            _loese_phasenwechsel_aus(stack.web_basis, stack.token, startphase)
            ende = time.monotonic() + 30.0
            while True:
                stand = browser_mitschnitt.datenstand(stack.db_pfad, stack.chat_id)
                if (stand.get("arbeitsstand") or {}).get("phase") == startphase:
                    break
                if time.monotonic() >= ende:
                    raise RuntimeError(
                        f"Phasenwechsel nach Phase {startphase} nicht angekommen, siehe "
                        f"{lauf_verzeichnis / 'bot.log'}")
                time.sleep(1.0)
        if argumente.stationen:
            # Der Stationsmodus (Abnahmelauf Phase 1-2): erfundene
            # Diskussion als Audio ueber Chromiums Fake-Media-Flags, dazu
            # ein zweites, rein zuschauendes Geraet fuer das Begriffsboard
            # (``browser_beobachter``) -- beide VOR der Persona-Seite, damit
            # der Beobachter von der ersten Sekunde an mitmisst.
            #
            # Task 6: der Beobachter hat einen EIGENEN Browser -- der
            # Persona-Browser wird vor jeder Station mit ``diskussion`` mit
            # deren WAV neu gestartet (``wechsle_audio``; Chromium liest
            # ``--use-file-for-fake-audio-capture`` nur beim Start), der
            # Speicher (localStorage, Cookies) geht per ``storage_state`` mit.
            from simulation import browser_probe, browser_wissen
            from simulation.browser_beobachter import Beobachter
            from simulation.erzeuge_diskussion_audio import erzeuge as erzeuge_diskussion

            wav = lauf_verzeichnis / "diskussion.wav"
            skript_pfad = Path(__file__).parent / "diskussion" / "p1-diskussion.txt"
            erzeuge_diskussion(skript_pfad, wav)

            def hole_prompt(chat_id: int, text: str) -> str:
                return browser_wissen.hole_prompt(
                    app_wurzel=app_wurzel, env_datei=Path(argumente.env_datei),
                    db=Path(stack.db_pfad), chat_id=chat_id, text=text,
                    arbeitsordner=lauf_verzeichnis)

            with sync_playwright() as p:
                beobachter_browser = p.chromium.launch()
                beobachter = Beobachter.oeffne(beobachter_browser,
                                               f"{stack.web_basis}/g/{stack.token}")
                geraet_profil = (
                    {**p.devices["iPhone 13"]} if argumente.geraet == "handy"
                    else {"viewport": {"width": 1440, "height": 900}}
                )
                persona = {"browser": p.chromium.launch(args=browser_probe.chromium_argumente(wav))}
                persona["context"] = persona["browser"].new_context(**geraet_profil)
                seite = persona["context"].new_page()
                persona["seite"] = seite
                context = persona["context"]

                def wechsle_audio(neue_wav: Path):
                    speicher = persona["context"].storage_state()
                    persona["browser"].close()
                    persona["browser"] = p.chromium.launch(
                        args=browser_probe.chromium_argumente(neue_wav))
                    persona["context"] = persona["browser"].new_context(
                        **geraet_profil, storage_state=speicher)
                    # Messung VOR der ersten Seite -- ein Init-Skript wirkt
                    # nur auf Seiten, die danach entstehen.
                    browser_zaehler.installiere_messung(persona["context"])
                    persona["seite"] = persona["context"].new_page()
                    # Immer Gruppe 1 (nicht ``alt.url``): eine Station einer
                    # anderen Gruppe kehrt sonst evtl. nicht zurueck.
                    persona["seite"].goto(f"{stack.web_basis}/g/{stack.token}")
                    persona["seite"].wait_for_selector("#verlauf")
                    return persona["seite"], persona["context"]

                persona_klient = Claude()
                richter_klient = Claude()
                # Die echten Leitbilder (``browser_leitbilder.Sammler``,
                # Paket G) -- nur im Schlusslauf mit ``--leitbilder``.
                leitbilder = None
                if argumente.leitbilder:
                    from simulation import browser_leitbilder
                    leitbilder = browser_leitbilder.Sammler(
                        token=stack.token, geraet=argumente.geraet,
                        ziel=Path("docs/guide/bilder"))
                ergebnis = fuehre_stationen(
                    seite, context, basis_url=stack.web_basis, token=stack.token,
                    db_pfad=stack.db_pfad, chat_id=stack.chat_id,
                    persona_client=persona_klient, judge_client=richter_klient,
                    geraet=argumente.geraet, persona_name=argumente.persona,
                    stationen=stationsliste,
                    lauf_verzeichnis=lauf_verzeichnis, beobachter=beobachter,
                    leitbilder=leitbilder,
                    meta={"app_wurzel": str(app_wurzel), "app_commit": _app_commit(app_wurzel),
                          "phase_erzwungen_start": startphase if startphase > 1 else None},
                    gruppen=stack.gruppen, hole_prompt=hole_prompt,
                    wechsle_audio=wechsle_audio, kosten_stopp=argumente.kosten_stopp,
                    max_minuten=argumente.max_minuten,
                )
                if leitbilder is not None:
                    leitbilder.schreibe_index()
                beobachter.schliesse()
                persona["browser"].close()
                beobachter_browser.close()
        else:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                geraet_profil = (
                    {**p.devices["iPhone 13"]} if argumente.geraet == "handy"
                    else {"viewport": {"width": 1440, "height": 900}}
                )
                context = browser.new_context(**geraet_profil)
                seite = context.new_page()
                persona_klient = Claude()
                richter_klient = Claude()
                ergebnis = fuehre_lauf(
                    seite, context, basis_url=stack.web_basis, token=stack.token,
                    db_pfad=stack.db_pfad, chat_id=stack.chat_id,
                    persona_client=persona_klient, judge_client=richter_klient,
                    geraet=argumente.geraet, persona_name=argumente.persona,
                    bis_phase=argumente.bis_phase, lauf_verzeichnis=lauf_verzeichnis,
                )
                # Der Kontaktbogen braucht den noch offenen Context (er baut
                # eine eigene Seite darin) -- deshalb VOR browser.close(), und
                # nur mit --bericht: ohne das Flag soll ein Lauf (z. B. zum
                # Debuggen) keine zusaetzlichen Dateien hinterlassen.
                kontaktbogen_pfade: dict[int, str] = {}
                if argumente.bericht:
                    for phase in ergebnis["phasen_ergebnisse"]:
                        nummer = phase["nummer"]
                        bilder = sorted(lauf_verzeichnis.glob(f"*-phase{nummer}-nach.png"))
                        if not bilder:
                            continue
                        ziel = lauf_verzeichnis / f"kontaktbogen-phase{nummer}.png"
                        browser_bericht.kontaktbogen(context, bilder, ziel)
                        kontaktbogen_pfade[nummer] = ziel.name
                browser.close()
    finally:
        stack.beende()

    if not argumente.bericht:
        return

    if argumente.stationen:
        # Der eigentliche Markdown-Bericht ist ein spaeteres Paket (G) --
        # hier steht nur der Pfad, unter dem ``ergebnis.json`` liegt.
        print(f"Ergebnis: {lauf_verzeichnis / 'ergebnis.json'}")
        return

    markdown = browser_bericht.baue_markdown(
        f"Padua browser UX simulation ({lauf_name})", argumente.geraet,
        ergebnis["modelle"], ergebnis["phasen_ergebnisse"], ergebnis["top_befunde"],
    )
    if kontaktbogen_pfade:
        zeilen = ["", "## Kontaktboegen (alle Screenshots je Phase)", ""]
        for nummer, name in sorted(kontaktbogen_pfade.items()):
            zeilen.append(f"- Phase {nummer}: `{lauf_verzeichnis / name}`")
        markdown += "\n".join(zeilen) + "\n"
    berichte_verzeichnis = Path("simulation/browser_berichte")
    berichte_verzeichnis.mkdir(parents=True, exist_ok=True)
    (berichte_verzeichnis / f"{lauf_name}.md").write_text(markdown, encoding="utf-8")
    print(f"Bericht: simulation/browser_berichte/{lauf_name}.md")


if __name__ == "__main__":
    main()
