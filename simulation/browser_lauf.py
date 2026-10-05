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
    except PlaywrightError as fehler:
        log.warning("Aktion schlug fehl (%s): %s", aktion, fehler)
        return {"art": "fehlgeschlagen", "fehler": str(fehler)}


def _diskussion_laeuft(page) -> bool:
    return page.locator('#diskussion[data-laeuft="1"]').count() > 0


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


def _fuehre_station_aus(page, persona_client, mitschnitt: browser_mitschnitt.Mitschnitt,
                        station: browser_stationen.Station, *, basis_url: str,
                        token: str, db_pfad: str, chat_id: int, persona_name: str,
                        beobachter=None, leitbilder=None, vor_ende=None,
                        nach_klick=None) -> dict:
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
        nonlocal gewartet, mitte_genommen, hinweis
        if not (station.zuhoeren_s and not gewartet and _diskussion_laeuft(page)):
            return False
        gewartet = True
        ende = time.monotonic() + station.zuhoeren_s
        while time.monotonic() < ende:
            page.wait_for_timeout(10_000)
            if beobachter:
                beobachter.messe()
            if leitbilder and station.leitbild_mitte and not mitte_genommen:
                mitte_genommen = bool(leitbilder.nimm(page, station.phase, station.leitbild_mitte))
        if vor_ende is not None:
            vor_ende()
        if _beende_diskussion_deterministisch(page):
            if nach_klick is not None:
                nach_klick()
            if beobachter:
                beobachter.messe()
        else:
            hinweis = browser_stationen.HINWEIS_DISKUSSION_ENDE
        return True

    schritte = 0
    while schritte < station.budget:
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

        protokoll = _aktion_ausfuehren(page, aktion)
        warte = browser_aktionen.warte_auf_antwort(page)

        _warte_und_beende_diskussion_falls_noetig()

        if (leitbilder and station.leitbild_mitte and not mitte_genommen
                and not station.zuhoeren_s
                and page.locator(".leiste button:visible, #kalibrierung-start:visible").count()):
            mitte_genommen = bool(leitbilder.nimm(page, station.phase, station.leitbild_mitte))

        nach = mitschnitt.screenshot_pfad(station.phase, f"{station.schluessel}-nach")
        nach.write_bytes(browser_elemente.bildschirmfoto(page))
        screenshots.append(nach)
        nachher = browser_mitschnitt.datenstand(db_pfad, chat_id)
        db_diff = browser_mitschnitt.unterschied(vorher, nachher)
        vorher = nachher
        _zaehler_addieren(zaehler_summe, browser_zaehler.alle(page))
        if beobachter:
            beobachter.messe()
        mitschnitt.schritt(
            phase=station.phase, screenshot_vorher=vor, screenshot_nachher=nach,
            elemente=elemente, aktion=protokoll, begruendung=aktion.get("begruendung", ""),
            antwort=warte, db_diff=db_diff, station=station.schluessel)

        aktiv = _aktive_phase_nummer(page)
        if station.endet_bei_phasenwechsel and aktiv is not None and aktiv > station.phase:
            break

    stand = browser_mitschnitt.datenstand(db_pfad, chat_id)
    fertig = station.fertig(stand) if station.fertig else True
    if not fertig and station.endet_bei_phasenwechsel:
        ziel = browser_stationen.notweg_ziel(station.phase, _aktive_phase_nummer(page))
        if ziel is not None and ziel <= phasen.LETZTE:
            _loese_phasenwechsel_aus(basis_url, token, ziel)
            fallback = True
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
            "zaehler_summe": zaehler_summe, "screenshots_nach": screenshots}


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


def _oeffne_gruppe(page, basis_url: str, token: str) -> None:
    page.goto(f"{basis_url}/g/{token}")
    page.wait_for_selector("#verlauf")


def fuehre_stationen(page, context, *, basis_url: str, token: str, db_pfad: str,
                     chat_id: int, persona_client, judge_client, geraet: str,
                     persona_name: str, stationen: tuple, lauf_verzeichnis: Path,
                     beobachter=None, leitbilder=None, meta: dict | None = None,
                     gruppen: list | None = None,
                     warte=browser_invarianten.warte_nach_diskussion,
                     hole_prompt=None, wechsle_audio=None) -> dict:
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
      geschrieben (``finally``)."""
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
    try:
        for station in stationen:
            befunde: list[browser_invarianten.Befund] = []
            kontext = PruefKontext(
                db_pfad=db_pfad, gruppen=gruppen, page=page, beobachter=beobachter,
                hole_prompt=hole_prompt, warte=warte, lauf_verzeichnis=lauf_verzeichnis,
                beobachter_start=len(beobachter.verlauf) if beobachter else 0, notizen=notizen)
            kontext.sende = lambda text, k=kontext: _sende_und_lies_antwort(k.page, text)
            lauf = None
            try:
                gruppe = gruppen[station.gruppe - 1]
                if station.diskussion:
                    wav, zuhoeren_s = _diskussions_audio(station, lauf_verzeichnis)
                    station = dataclasses.replace(station, zuhoeren_s=zuhoeren_s)
                    if wechsle_audio is not None:
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

                def vor_ende(k=kontext, cid=gruppe.chat_id):
                    k.vorher = _lies_p1(db_pfad, cid)

                lauf = _fuehre_station_aus(
                    page, persona_client, mitschnitt, station, basis_url=basis_url,
                    token=gruppe.token, db_pfad=db_pfad, chat_id=gruppe.chat_id,
                    persona_name=persona_name, beobachter=beobachter,
                    leitbilder=leitbilder, vor_ende=vor_ende, nach_klick=nach_klick)
            except Exception as fehler:
                log.exception("Station %s ist gescheitert", station.schluessel)
                fehlgeschlagen_bei = fehlgeschlagen_bei or station.schluessel
                befunde.append(befund_ausnahme(station, fehler))
            # Die Haken laufen auch nach einer Ausnahme: ein Harness-Fehler
            # darf ein App-Symptom nicht verdecken (Symptomregel).
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
            fehlgeschlagen_bei=fehlgeschlagen_bei, meta=meta)
    return ergebnis


def _schreibe_stationsergebnis(lauf_verzeichnis: Path, *, beobachter, db_pfad, persona_client,
                               judge_client, geraet, persona_name, ergebnisse, invarianten,
                               notizen, entwickler_merkmale, fehlgeschlagen_bei, meta) -> dict:
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
                "db_pfad": db_pfad, **(meta or {})}
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
    stack = browser_umgebung.starte_stack(
        argumente.env_datei, lauf_verzeichnis, app_wurzel=app_wurzel,
        gruppen=max((st.gruppe for st in stationsliste), default=1))
    try:
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
                    meta={"app_wurzel": str(app_wurzel), "app_commit": _app_commit(app_wurzel)},
                    gruppen=stack.gruppen, hole_prompt=hole_prompt,
                    wechsle_audio=wechsle_audio,
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
