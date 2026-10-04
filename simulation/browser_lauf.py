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

import json
import logging
import sqlite3
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError

from interview_theater import phasen
from simulation import (
    browser_aktionen,
    browser_elemente,
    browser_judge,
    browser_mitschnitt,
    browser_persona,
    browser_stationen,
    browser_zaehler,
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
                        beobachter=None, leitbilder=None) -> dict:
    """Ein Stationsdurchlauf (Abnahmelauf Phase 1-2, 04.10.2026): wie
    ``_fuehre_phase_aus``, aber gegen ein Stationsziel statt eine Phase, mit
    Nachfragen-Schutz (``browser_stationen.muss_antworten``), optionalem
    Zuhoeren (``station.zuhoeren_s``) und Leitbild-Aufnahmen.

    ``station.ohne_persona`` ist die eine Ausnahme (p1-start, Pflichtpunkt
    2): keine Persona, nur Warten und eine mechanische Lese-Erfassung."""
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

    schritte = 0
    while schritte < station.budget:
        schritte += 1
        vor = mitschnitt.screenshot_pfad(station.phase, f"{station.schluessel}-vor")
        vor.write_bytes(browser_elemente.bildschirmfoto(page))
        elemente = browser_elemente.extrahiere(page)
        aktion = browser_persona.naechste_aktion(
            persona_client, persona_name, vor.read_bytes(), elemente,
            station.ziel, _verlaufszeilen(page), hinweis=hinweis)
        hinweis = None
        offene.extend(browser_persona.offene_fragen(aktion))
        if aktion.get("type") in ("done_phase", "done_station"):
            if browser_stationen.muss_antworten(_verlaufsblasen(page), beantwortet):
                beantwortet += 1
                hinweis = browser_stationen.HINWEIS_NACHFRAGE
                continue
            break

        protokoll = _aktion_ausfuehren(page, aktion)
        warte = browser_aktionen.warte_auf_antwort(page)

        if station.zuhoeren_s and not gewartet and _diskussion_laeuft(page):
            gewartet = True
            ende = time.monotonic() + station.zuhoeren_s
            while time.monotonic() < ende:
                page.wait_for_timeout(10_000)
                if beobachter:
                    beobachter.messe()
                if leitbilder and station.leitbild_mitte and not mitte_genommen:
                    mitte_genommen = bool(leitbilder.nimm(page, station.phase, station.leitbild_mitte))
            if _beende_diskussion_deterministisch(page):
                if beobachter:
                    beobachter.messe()
            else:
                hinweis = browser_stationen.HINWEIS_DISKUSSION_ENDE

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


def fuehre_stationen(page, context, *, basis_url: str, token: str, db_pfad: str,
                     chat_id: int, persona_client, judge_client, geraet: str,
                     persona_name: str, stationen: tuple, lauf_verzeichnis: Path,
                     beobachter=None, leitbilder=None) -> dict:
    """Die Stationsmotor-Engine des Abnahmelaufs Phase 1-2 (04.10.2026):
    Station fuer Station aus ``browser_stationen.STATIONEN``, mit einer
    eigenen Erklaernote je Station (Pflichtpunkt 1). Schreibt
    ``lauf_verzeichnis / "ergebnis.json"`` und liefert dasselbe Dict."""
    lauf_verzeichnis = Path(lauf_verzeichnis)
    mitschnitt = browser_mitschnitt.Mitschnitt(
        lauf_verzeichnis, f"{geraet}-{persona_name}", geraet)
    browser_zaehler.installiere_messung(context)
    page.goto(f"{basis_url}/g/{token}")
    page.wait_for_selector("#verlauf")
    ergebnisse: list[dict] = []
    fehlgeschlagen_bei = None
    meta: set[str] = set()
    # Wie viele Bot-Blasen schon da waren, BEVOR diese Station lief -- die
    # Erklaernote (Pflichtpunkt 1) soll nur die wirklich NEUEN Bot-Blasen
    # dieser Station beurteilen, nicht noch einmal die der vorigen (sonst
    # waechst die Zitatbasis mit jeder Station und eine fruehe Erklaerung
    # wird mehrfach bewertet).
    bot_anzahl_vorher = 0
    for station in stationen:
        try:
            lauf = _fuehre_station_aus(
                page, persona_client, mitschnitt, station, basis_url=basis_url,
                token=token, db_pfad=db_pfad, chat_id=chat_id,
                persona_name=persona_name, beobachter=beobachter,
                leitbilder=leitbilder)
        except Exception:
            log.exception("Station %s ist gescheitert", station.schluessel)
            fehlgeschlagen_bei = fehlgeschlagen_bei or station.schluessel
            ergebnisse.append({"schluessel": station.schluessel, "phase": station.phase,
                               "schritte": 0, "nachfragen_beantwortet": 0,
                               "offene_fragen": [], "fertig": False,
                               "fallback_benutzt": False, "note": None, "befunde": [],
                               "zaehler_summe": {}, "screenshots_fuer_bericht": [],
                               "note_erklaerung": None, "schwaechstes_zitat": "",
                               "vorschlag": ""})
            continue
        meta.update(_entwickler_meta(page))
        repraesentativ = _repraesentativ(lauf["screenshots_nach"])
        alle_bot_texte = [b["text"] for b in _verlaufsblasen(page) if b.get("von") == "bot"]
        bot_texte = alle_bot_texte[bot_anzahl_vorher:]
        bot_anzahl_vorher = len(alle_bot_texte)
        bewertung = browser_judge.bewerte_phase(
            judge_client, station.phase, f"{phasen.kurzname(station.phase)} / {station.schluessel}",
            [p.read_bytes() for p in repraesentativ], [p.name for p in repraesentativ],
            lauf["zaehler_summe"]) if not station.ohne_persona else {}
        erklaerung = browser_judge.bewerte_erklaerung(judge_client, station.schluessel, bot_texte)
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
        })

    beob = beobachter.ergebnis() if beobachter else {
        "board_verlauf": [], "beobachter_neu_geladen": False, "board_bestanden": False}
    modelle = _modell_lesen(db_pfad)
    modelle["persona"] = getattr(persona_client, "modell", "?")
    modelle["judge"] = getattr(judge_client, "modell", "?")
    top = [{**b, "station": e["schluessel"]} for e in ergebnisse
           for b in e["befunde"] if b.get("schwere") == "hoch"]
    ergebnis = {"geraet": geraet, "persona": persona_name,
                "stationen_ergebnisse": ergebnisse, **beob,
                "entwickler_meta": sorted(meta), "modelle": modelle,
                "top_befunde": top, "fehlgeschlagen_bei": fehlgeschlagen_bei,
                "db_pfad": db_pfad}
    (lauf_verzeichnis / "ergebnis.json").write_text(
        json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding="utf-8")
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


def main() -> None:
    """Dünner CLI-Wrapper: baut den echten Stack, einen echten Opus-Klienten
    und einen echten Browser, ruft ``fuehre_lauf``, schreibt den Bericht.

    Liest NIE die Env-Datei selbst -- ``browser_umgebung.starte_bot`` gibt
    ihren Pfad nur an ein Bash-Skript weiter (siehe dort)."""
    import argparse
    import os
    import sys
    import time
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
    argumente = zerleger.parse_args()

    if not argumente.env_datei:
        print("Fehlende Env-Datei: --env-datei oder IT_SIM_ENV", file=sys.stderr)
        raise SystemExit(1)

    datum = time.strftime("%Y-%m-%d")
    if argumente.stationen:
        lauf_name = f"{datum}-{argumente.geraet}-{argumente.persona}-{argumente.stationen}"
    else:
        lauf_name = f"{datum}-{argumente.geraet}"
    lauf_verzeichnis = Path("simulation/browser_laeufe") / lauf_name
    stack = browser_umgebung.starte_stack(argumente.env_datei, lauf_verzeichnis)
    try:
        if argumente.stationen:
            # Der Stationsmodus (Abnahmelauf Phase 1-2): erfundene
            # Diskussion als Audio ueber Chromiums Fake-Media-Flags, dazu
            # ein zweites, rein zuschauendes Geraet fuer das Begriffsboard
            # (``browser_beobachter``) -- beide VOR der Persona-Seite, damit
            # der Beobachter von der ersten Sekunde an mitmisst.
            from simulation import browser_probe
            from simulation.browser_beobachter import Beobachter
            from simulation.erzeuge_diskussion_audio import erzeuge as erzeuge_diskussion

            wav = lauf_verzeichnis / "diskussion.wav"
            skript_pfad = Path(__file__).parent / "diskussion" / "p1-diskussion.txt"
            erzeuge_diskussion(skript_pfad, wav)
            with sync_playwright() as p:
                browser = p.chromium.launch(args=browser_probe.chromium_argumente(wav))
                beobachter = Beobachter.oeffne(browser, f"{stack.web_basis}/g/{stack.token}")
                geraet_profil = (
                    {**p.devices["iPhone 13"]} if argumente.geraet == "handy"
                    else {"viewport": {"width": 1440, "height": 900}}
                )
                context = browser.new_context(**geraet_profil)
                seite = context.new_page()
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
                    stationen=browser_stationen.STATIONEN[argumente.stationen],
                    lauf_verzeichnis=lauf_verzeichnis, beobachter=beobachter,
                    leitbilder=leitbilder,
                )
                if leitbilder is not None:
                    leitbilder.schreibe_index()
                beobachter.schliesse()
                browser.close()
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
