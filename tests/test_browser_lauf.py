import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

# Versuche Playwright zu importieren; wenn das fehlschlägt, starte nur Tests
# die kein Playwright brauchen (z.B. _app_commit mit Timeout-Handling)
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except (ImportError, ModuleNotFoundError):
    HAS_PLAYWRIGHT = False
    # Fallback: Ein Dummy sync_playwright fuer Tests die Playwright nicht brauchen
    def sync_playwright(*args, **kwargs):
        raise pytest.skip("playwright ist hier nicht installiert")

# Tests die NICHT Playwright brauchen, koennen trotzdem laufen
if not HAS_PLAYWRIGHT:
    # Nur importorskip wenn wir WIRKLICH Playwright brauchen
    # (Das wird dynamisch pro Test entschieden, nicht statisch auf Dateiebene)
    pass

from interview_theater import bot, db, einstellungen, repo, web, web_kanal
from simulation import browser_lauf

CHAT = 7_000_000_000_555


class _ScriptedClient:
    """Liefert eine feste Folge von Aktionen -- eine je Aufruf, egal welches
    Bild/welche Elementliste gesehen wird. Nach dem letzten Eintrag:
    ``done_phase`` fuer immer (haelt den Lauf an, statt ihn zu ueberrennen)."""

    def __init__(self, folge: list[dict]):
        self._folge = list(folge)
        self.aufrufe = 0

    def json_objekt(self, system, nutzer, art="sim", bilder=None):
        self.aufrufe += 1
        if self._folge:
            return self._folge.pop(0)
        return {"type": "done_phase", "begruendung": "fertig"}


class _FakeJudge:
    modell = "fake-judge"

    def json_objekt(self, system, nutzer, art="sim", bilder=None):
        return {"note": 5, "befunde": []}


class _LLMAttrappe:
    """Minimal: der Gespraechszug antwortet einmal mit einem gespeicherten
    Begriffsvorschlag, danach immer mit einer Quittung -- genug, um
    ``/g/<token>`` echt bis zum Tab-Wechsel zu befahren. ``antwort`` ist
    per ``monkeypatch.setattr`` je Test austauschbar."""

    antwort = "Got it, thanks."

    def schema(self, chat_id, system, nutzer, schema, art, **kw):
        if art == "erkenner":
            return {"aenderungen": []}
        if art == "journal":
            return {"eintraege": []}
        return {"antwort": self.antwort}


@pytest.fixture()
def stack(tmp_path, monkeypatch):
    pfad = str(tmp_path / "t.db")
    audio = tmp_path / "audio"
    monkeypatch.setenv("IT_AUDIO", str(audio))
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")

    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    repo.sichere_gruppe(aufbau, CHAT, "gruppe1", "Testgruppe")
    repo.setze_gruppe_kanal(aufbau, CHAT, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT)
    aufbau.commit()
    aufbau.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "", schluessel=b"x" * 32)
    web_faden = threading.Thread(target=dienst.serve_forever, daemon=True)
    web_faden.start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"

    bot_conn = db.verbinde(pfad)
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe1", db_pfad=pfad, audio_verz=str(audio),
        llm_url="u", llm_key="k", llm_modell="m", stt_basis="https://stt.test",
        stt_produkt="P", kanal=einstellungen.KANAL_WEB, web_chat_id=CHAT,
    )
    klm = _LLMAttrappe()
    kanal = web_kanal.WebKanal(bot_conn, CHAT, str(audio), schritt_s=0.05)
    pool = ThreadPoolExecutor(max_workers=2)
    halt = threading.Event()

    class _Halt(Exception):
        pass

    orig_hole = kanal.hole_updates
    def hole_updates(offset, timeout=25):
        if halt.is_set():
            raise _Halt()
        return orig_hole(offset, timeout=min(timeout, 0.5))
    kanal.hole_updates = hole_updates

    def fahre():
        try:
            bot.schleife(bot_conn, e, kanal, klm, None, pool)
        except _Halt:
            pass

    bot_faden = threading.Thread(target=fahre, daemon=True)
    bot_faden.start()

    yield basis, token, pfad

    halt.set()
    bot_faden.join(timeout=10)
    pool.shutdown(wait=True, cancel_futures=True)
    dienst.shutdown()
    dienst.server_close()
    web_faden.join(timeout=10)
    bot_conn.close()


def test_eine_scriptete_persona_faehrt_phase_eins_durch(stack, tmp_path):
    basis, token, pfad = stack
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        seite = context.new_page()
        seite.goto(f"{basis}/g/{token}")
        seite.wait_for_selector("#verlauf")

        persona = _ScriptedClient([
            {"type": "type_send", "text": "Our terms: arrival, work, night",
             "begruendung": "typing the terms"},
            {"type": "wait", "duration_ms": 500, "begruendung": "waiting for the bot"},
            {"type": "done_phase", "begruendung": "that is phase 1 done"},
        ])
        ergebnis = browser_lauf.fuehre_lauf(
            seite, context, basis_url=basis, token=token, db_pfad=pfad,
            chat_id=CHAT, persona_client=persona, judge_client=_FakeJudge(),
            geraet="handy", persona_name="student", bis_phase=1,
            lauf_verzeichnis=tmp_path / "lauf",
        )
        browser.close()

    assert len(ergebnis["phasen_ergebnisse"]) == 1
    phase1 = ergebnis["phasen_ergebnisse"][0]
    assert phase1["note"] == 5
    assert persona.aufrufe >= 2
    zeilen = (tmp_path / "lauf" / "schritte.jsonl").read_text().splitlines()
    assert len(zeilen) >= 1
    for zeile in zeilen:
        eintrag = json.loads(zeile)
        assert Path(tmp_path / "lauf" / eintrag["screenshot_vorher"]).exists()


def test_ein_fehlgeschlagener_klick_reisst_nicht_die_ganze_phase_mit(stack, tmp_path):
    """Realer Betriebsbefund (Padua-Abnahme, 03.10.2026): ein Klick, der ins
    Leere trifft (eine veraltete ``element_id``, ein Tab-Name als Anzeigetext
    statt als ``data-tab``-Wert), warf bis hierhin eine Playwright-Ausnahme,
    die die GANZE Phase abstuerzen liess -- samt Richterurteil. Ein einzelner
    Fehlgriff darf nur diesen Schritt kosten, nicht die Phase."""
    basis, token, pfad = stack
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        seite = context.new_page()
        seite.goto(f"{basis}/g/{token}")
        seite.wait_for_selector("#verlauf")

        persona = _ScriptedClient([
            # Ein Text, den es auf der Seite garantiert nicht gibt -- das
            # erzwingt einen echten Playwright-Timeout (5 s) in
            # ``browser_aktionen.fuehre_aus``, denselben Fehlertyp wie beim
            # echten Fund.
            {"type": "click", "text": "Dieser Text steht nirgends auf der Seite",
             "begruendung": "ein Fehlgriff"},
            {"type": "done_phase", "begruendung": "trotzdem fertig"},
        ])
        ergebnis = browser_lauf.fuehre_lauf(
            seite, context, basis_url=basis, token=token, db_pfad=pfad,
            chat_id=CHAT, persona_client=persona, judge_client=_FakeJudge(),
            geraet="handy", persona_name="student", bis_phase=1,
            lauf_verzeichnis=tmp_path / "lauf",
        )
        browser.close()

    assert ergebnis["fehlgeschlagen_bei"] is None
    assert len(ergebnis["phasen_ergebnisse"]) == 1
    assert ergebnis["phasen_ergebnisse"][0]["note"] == 5


def test_eine_gescheiterte_phase_reisst_die_naechste_nicht_mit(stack, tmp_path, monkeypatch):
    """``fuehre_lauf`` darf einen kaputten Phasenschritt (Playwright-Timeout
    o.ae.) nicht mit dem ganzen Lauf bezahlen: Phase 1 scheitert, Phase 2
    bekommt trotzdem ihre Chance -- die ``_fuehre_phase_aus``-Schleife selbst
    wird hier nicht gebraucht, deshalb wird sie direkt ersetzt."""
    basis, token, pfad = stack

    def fake_fuehre_phase_aus(page, persona_client, mitschnitt, *, aktuelle_phase, **kw):
        if aktuelle_phase == 1:
            raise RuntimeError("Playwright-Timeout (simuliert)")
        return {"zaehler_summe": {}, "fallback_benutzt": False, "screenshots_nach": []}

    monkeypatch.setattr(browser_lauf, "_fuehre_phase_aus", fake_fuehre_phase_aus)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        seite = context.new_page()
        seite.goto(f"{basis}/g/{token}")
        seite.wait_for_selector("#verlauf")

        ergebnis = browser_lauf.fuehre_lauf(
            seite, context, basis_url=basis, token=token, db_pfad=pfad,
            chat_id=CHAT, persona_client=_ScriptedClient([]), judge_client=_FakeJudge(),
            geraet="handy", persona_name="student", bis_phase=2,
            lauf_verzeichnis=tmp_path / "lauf",
        )
        browser.close()

    assert ergebnis["fehlgeschlagen_bei"] == 1
    assert len(ergebnis["phasen_ergebnisse"]) == 2
    phase1, phase2 = ergebnis["phasen_ergebnisse"]
    assert phase1["nummer"] == 1
    assert phase1["note"] is None
    assert phase2["nummer"] == 2
    assert phase2["note"] == 5


def test_in_der_letzten_phase_wird_der_notweg_nicht_versucht(stack, tmp_path):
    """Realer Betriebsbefund (Padua-Abnahme, 03.10.2026): in der LETZTEN
    Phase gibt es keine naechste, in die der Operator-Notweg springen
    koennte -- ein Versuch dort lieferte HTTP 400 (die Zielphase existiert
    nicht) und riss eine sonst produktive letzte Phase als "gescheitert" in
    die Bilanz. Die Persona haelt hier absichtlich nie ``done_phase`` und
    loest nie einen natuerlichen Fortschritt aus, erschoepft also das
    Schritt-Budget -- das darf keine Ausnahme werfen und keinen HTTP-Aufruf
    ausloesen (eine erfundene, nicht aufloesende Basis-URL wuerde das sofort
    sichtbar machen)."""
    from interview_theater import phasen

    basis, token, pfad = stack
    letzte = phasen.LETZTE

    persona = _ScriptedClient([
        {"type": "wait", "duration_ms": 50, "begruendung": "warte"},
    ] * 20)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        seite = context.new_page()
        seite.goto(f"{basis}/g/{token}")
        seite.wait_for_selector("#verlauf")

        ergebnis = browser_lauf._fuehre_phase_aus(
            seite, persona, browser_lauf.browser_mitschnitt.Mitschnitt(
                tmp_path / "lauf", "handy-student", "handy"),
            aktuelle_phase=letzte, basis_url="http://127.0.0.1:1",
            token=token, db_pfad=pfad, chat_id=CHAT, persona_name="student",
            max_schritte=5, fallback_nach_schritten=2,
        )
        browser.close()

    assert ergebnis["fallback_benutzt"] is False


def test_notweg_springt_nicht_in_eine_schon_aktive_phase(stack, tmp_path):
    """Baseline 04.10.: /phaseklick hin und her erzeugte doppelte
    Phasentexte. Ist Phase 2 schon aktiv, darf der Notweg aus Phase 1 nichts
    ausloesen -- eine nicht aufloesende Basis-URL machte jeden Versuch sichtbar."""
    basis, token, pfad = stack
    conn = db.verbinde(pfad); repo.setze_phase(conn, CHAT, 2); conn.commit(); conn.close()
    with sync_playwright() as p:
        browser = p.chromium.launch(); context = browser.new_context()
        seite = context.new_page(); seite.goto(f"{basis}/g/{token}")
        seite.wait_for_selector("#verlauf")
        ergebnis = browser_lauf._fuehre_phase_aus(
            seite, _ScriptedClient([{"type": "wait", "duration_ms": 50,
                                     "begruendung": "w"}] * 5),
            browser_lauf.browser_mitschnitt.Mitschnitt(tmp_path / "l", "h", "handy"),
            aktuelle_phase=1, basis_url="http://127.0.0.1:1", token=token,
            db_pfad=pfad, chat_id=CHAT, persona_name="student",
            max_schritte=3, fallback_nach_schritten=1)
        browser.close()
    assert ergebnis["fallback_benutzt"] is False


def test_station_beantwortet_eine_rueckfrage_bevor_sie_endet(stack, tmp_path, monkeypatch):
    from simulation import browser_stationen
    basis, token, pfad = stack
    monkeypatch.setattr(browser_lauf, "_verlaufsblasen",
                        lambda page: [{"von": "bot", "typ": "text", "text": "Which terms?"}])
    station = browser_stationen.Station("t-eins", 1, "Say hello.", budget=4)
    persona = _ScriptedClient([
        {"type": "done_station", "begruendung": "fertig", "offene_fragen": ["What is this?"]},
        {"type": "type_send", "text": "home and border", "begruendung": "antworte"},
        {"type": "done_station", "begruendung": "jetzt fertig"},
    ])
    with sync_playwright() as p:
        browser = p.chromium.launch(); context = browser.new_context()
        seite = context.new_page()
        ergebnis = browser_lauf.fuehre_stationen(
            seite, context, basis_url=basis, token=token, db_pfad=pfad, chat_id=CHAT,
            persona_client=persona, judge_client=_FakeJudge(), geraet="handy",
            persona_name="priya", stationen=(station,), lauf_verzeichnis=tmp_path / "l")
        browser.close()
    st = ergebnis["stationen_ergebnisse"][0]
    assert st["nachfragen_beantwortet"] >= 1
    assert st["offene_fragen"] == ["What is this?"]
    assert persona.aufrufe >= 3
    assert (tmp_path / "l" / "ergebnis.json").exists()
    zeilen = (tmp_path / "l" / "schritte.jsonl").read_text().splitlines()
    assert json.loads(zeilen[0])["station"] == "t-eins"


def test_ohne_persona_station_wartet_und_erfasst_ohne_persona_aufruf(stack, tmp_path, monkeypatch):
    """p1-start (Pflichtpunkt 2): keine Persona, nur Warten + mechanische
    Erfassung. Patch die Wartezeit auf 0 fuer den Test."""
    from simulation import browser_stationen
    basis, token, pfad = stack
    station = browser_stationen.Station("p1-start", 1, "Observe.", ohne_persona=True,
                                        warte_s=0, leitbild_ende="start")
    persona = _ScriptedClient([{"type": "done_station", "begruendung": "sollte nie gerufen werden"}])
    with sync_playwright() as p:
        browser = p.chromium.launch(); context = browser.new_context()
        seite = context.new_page()
        ergebnis = browser_lauf.fuehre_stationen(
            seite, context, basis_url=basis, token=token, db_pfad=pfad, chat_id=CHAT,
            persona_client=persona, judge_client=_FakeJudge(), geraet="handy",
            persona_name="priya", stationen=(station,), lauf_verzeichnis=tmp_path / "l")
        browser.close()
    assert persona.aufrufe == 0
    st = ergebnis["stationen_ergebnisse"][0]
    for feld in ("bot_nachricht", "kalibrierung_sichtbar", "zuhoeren_laeuft", "leertext_sichtbar"):
        assert feld in st and isinstance(st[feld], bool)
    # Regressionsschutz: der ohne_persona-Schritt darf keinen Platzhalterpfad
    # ohne Datei dahinter in schritte.jsonl hinterlassen (sonst scheitert ein
    # spaeterer Leser wie der Berichtsbauer am Bild).
    zeilen = (tmp_path / "l" / "schritte.jsonl").read_text().splitlines()
    assert len(zeilen) >= 1
    for zeile in zeilen:
        eintrag = json.loads(zeile)
        assert Path(tmp_path / "l" / eintrag["screenshot_vorher"]).exists()
        assert Path(tmp_path / "l" / eintrag["screenshot_nachher"]).exists()


def test_fuehre_stationen_schreibt_meta_in_ergebnis_json(stack, tmp_path):
    """Task 1: ``app_wurzel``/``app_commit`` sollen im ergebnis.json landen,
    damit ein spaeterer Lauf gegen den alten Checkout (cb200e4) erkennbar
    bleibt."""
    from simulation import browser_stationen
    basis, token, pfad = stack
    station = browser_stationen.Station("p1-start", 1, "Observe.", ohne_persona=True, warte_s=0)
    with sync_playwright() as p:
        browser = p.chromium.launch(); context = browser.new_context()
        seite = context.new_page()
        browser_lauf.fuehre_stationen(
            seite, context, basis_url=basis, token=token, db_pfad=pfad, chat_id=CHAT,
            persona_client=_ScriptedClient([]), judge_client=_FakeJudge(), geraet="handy",
            persona_name="priya", stationen=(station,), lauf_verzeichnis=tmp_path / "l",
            meta={"app_wurzel": "/x/alt", "app_commit": "abc123"})
        browser.close()
    ergebnis = json.loads((tmp_path / "l" / "ergebnis.json").read_text())
    assert ergebnis["app_wurzel"] == "/x/alt"
    assert ergebnis["app_commit"] == "abc123"


_FIXTURE_DISKUSSION_LAEUFT = """
<button id="diskussion" data-laeuft="1">Start listening</button>
<button id="diskussion-beenden">Discussion done</button>
"""

_FIXTURE_INTERVIEW_LAEUFT = """
<button id="interview" data-laeuft="1">Recording</button>
<button id="interview-beenden">End interview</button>
"""


def test_beende_aufnahme_deterministisch_interview():
    with sync_playwright() as p:
        browser = p.chromium.launch(); seite = browser.new_page()
        seite.set_content(_FIXTURE_INTERVIEW_LAEUFT)
        assert browser_lauf._aufnahme_laeuft(seite, "interview") is True
        assert browser_lauf._beende_aufnahme_deterministisch(seite, "interview") is True
        browser.close()


def test_beende_aufnahme_deterministisch_brainstorm_nutzt_den_diskussion_knopf():
    """Billige, kostenlose Probe (kein Server, kein Modell) dafuer, dass der
    Stationstyp "brainstorm" seit 05.10.2026 22:00 wirklich ueber denselben
    ``#diskussion``/``#diskussion-beenden``-Knopf wie Phase 1 laeuft: dieselbe
    Fixture wie ``_FIXTURE_DISKUSSION_LAEUFT``, nur mit ``art="brainstorm"``
    angefragt -- ``browser_stationen.LAEUFT``/``ENDE`` muessen auf den
    echten Knopf auflaufen, kein eigenes ``#brainstorm`` mehr."""
    with sync_playwright() as p:
        browser = p.chromium.launch(); seite = browser.new_page()
        seite.set_content(_FIXTURE_DISKUSSION_LAEUFT)
        assert seite.locator("#brainstorm").count() == 0
        assert browser_lauf._aufnahme_laeuft(seite, "brainstorm") is True
        assert browser_lauf._beende_aufnahme_deterministisch(seite, "brainstorm") is True
        browser.close()


def test_aufnahme_diskussion_delegiert_an_die_alten_funktionen(monkeypatch):
    # bestehende Tests patchen _diskussion_laeuft/_beende_diskussion_deterministisch
    monkeypatch.setattr(browser_lauf, "_diskussion_laeuft", lambda page: True)
    monkeypatch.setattr(browser_lauf, "_beende_diskussion_deterministisch", lambda page: True)
    assert browser_lauf._aufnahme_laeuft(object(), "diskussion") is True
    assert browser_lauf._beende_aufnahme_deterministisch(object(), "diskussion") is True

_FIXTURE_DISKUSSION_OHNE_KNOPF = """
<button id="diskussion" data-laeuft="1">Start listening</button>
"""


def test_beende_diskussion_deterministisch_klickt_den_knopf():
    """Abnahme P1-2, Fortsetzung: Robo-Diagnose gegen eine echte sim.db-
    Kopie zeigte, dass in keinem der vier echten Laeufe 'Discussion done'
    gedrueckt wurde -- die Persona reagierte auf den Hinweis nicht
    zuverlaessig. Das Beenden eines stummen Mithoerens braucht keine
    LLM-Entscheidung und wird deshalb deterministisch geklickt."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page()
        seite.set_content(_FIXTURE_DISKUSSION_LAEUFT)
        geklickt = browser_lauf._beende_diskussion_deterministisch(seite)
        browser.close()
    assert geklickt is True


def test_beende_diskussion_deterministisch_ohne_knopf_liefert_false():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page()
        seite.set_content(_FIXTURE_DISKUSSION_OHNE_KNOPF)
        geklickt = browser_lauf._beende_diskussion_deterministisch(seite)
        browser.close()
    assert geklickt is False


_FIXTURE_PHASENSHEET_OFFEN = """
<div class="sheet" id="phasensheet" role="dialog" aria-modal="true">
  <div class="sheet-hintergrund"></div>
  <div class="sheet-inhalt">
    <h3 id="phasensheet-titel">1 Terms</h3>
    <div class="sheet-knoepfe">
      <button type="button" id="phasensheet-los">Go to 1 Terms</button>
      <button type="button" id="phasensheet-bleib">Stay here</button>
    </div>
  </div>
</div>
<button id="senden" type="button">Send</button>
"""

_FIXTURE_PHASENSHEET_ZU = """
<div class="sheet" id="phasensheet" hidden role="dialog" aria-modal="true">
  <div class="sheet-hintergrund"></div>
  <div class="sheet-inhalt">
    <div class="sheet-knoepfe">
      <button type="button" id="phasensheet-los">Go</button>
      <button type="button" id="phasensheet-bleib">Stay here</button>
    </div>
  </div>
</div>
<button id="senden" type="button">Send</button>
"""


def test_schliesse_offenes_phasensheet_klickt_stay_here():
    """Abnahme P1-2, Fortsetzung (05.10.2026, echter Lauf nach dem Merge):
    das Padua-Stepper-Bestaetigungsblatt oeffnete sich unbeabsichtigt und
    blockierte per unsichtbarem Hintergrund-Abdunkler jeden weiteren Klick
    30 Sekunden lang, bis der Lauf abbrach. Keine der elf Stationen
    navigiert ueber dieses Blatt absichtlich -- ein offenes Blatt wird
    deshalb deterministisch geschlossen, ohne LLM-Entscheidung."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page()
        seite.set_content(_FIXTURE_PHASENSHEET_OFFEN)
        geschlossen = browser_lauf._schliesse_offenes_phasensheet(seite)
        # Nach dem Klick auf "Stay here" wuerde die echte Seite das Blatt
        # per JS wieder verstecken -- hier pruefen wir nur den Rueckgabewert
        # und dass der Knopf wirklich erreichbar war (kein Timeout).
        browser.close()
    assert geschlossen is True


def test_schliesse_offenes_phasensheet_ohne_offenes_blatt_liefert_false():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page()
        seite.set_content(_FIXTURE_PHASENSHEET_ZU)
        geschlossen = browser_lauf._schliesse_offenes_phasensheet(seite)
        browser.close()
    assert geschlossen is False


_FIXTURE_DISKUSSION_TOGGLE = """
<div id="roadmap" data-aktive-phase="1"></div>
<button id="diskussion" data-laeuft="0" onclick="this.dataset.laeuft='1'">Start listening</button>
<button id="diskussion-beenden" onclick="document.getElementById('diskussion').dataset.laeuft='0'">Discussion done</button>
"""


def test_done_station_wartet_die_laufende_diskussion_zuerst_aus(
    tmp_path, monkeypatch
):
    """Abnahme P1-2, Fortsetzung (05.10.2026, echter Lauf): die Persona
    klickte 'Start listening' und sagte auf dem naechsten Schritt sofort
    'done_station' -- die Schleife brach VOR dem Zuhoer-Takt ab, die
    Diskussion blieb unbeendet. Jetzt wird der Zuhoer-Takt zuerst
    nachgeholt, bevor ein done_station/done_phase die Station beendet."""
    from simulation import browser_mitschnitt, browser_stationen

    pfad = str(tmp_path / "d.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "g", "G")
    conn.commit()
    conn.close()

    beendet_aufrufe = []
    monkeypatch.setattr(
        browser_lauf, "_beende_diskussion_deterministisch",
        lambda page: beendet_aufrufe.append(1) or True,
    )
    # Der 10s-Wartetakt selbst ist fuer den Test irrelevant -- nur, DASS er
    # laeuft, bevor "done_station" greift. ``time.monotonic``/``wait_for_timeout``
    # bleiben echt (ein ``zuhoeren_s`` von 1 braucht wegen der festen
    # 10s-Taktung trotzdem einmal 10s Realzeit; kurz genug fuer einen Test).
    station = browser_stationen.Station(
        "t-zuhoeren", 1, "Press Start listening, then say you are done.",
        budget=4, zuhoeren_s=1,
    )
    persona = _ScriptedClient([
        {"type": "click", "element_id": 0, "begruendung": "start listening"},
        {"type": "done_station", "begruendung": "fertig"},
    ])
    mitschnitt = browser_mitschnitt.Mitschnitt(tmp_path / "l", "h", "handy")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page()
        seite.set_content(_FIXTURE_DISKUSSION_TOGGLE)
        ergebnis = browser_lauf._fuehre_station_aus(
            seite, persona, mitschnitt, station, basis_url="http://127.0.0.1:1",
            token="t", db_pfad=pfad, chat_id=CHAT, persona_name="giulia",
            beobachter=None, leitbilder=None,
        )
        browser.close()
    assert beendet_aufrufe == [1]
    assert ergebnis["fertig"] is True


def test_app_commit_liefert_none_auch_bei_timeout(tmp_path, monkeypatch):
    """Task 1: _app_commit verspricht, None bei jedem Fehler einschließlich
    Timeout zu liefern, aber fing nur OSError. subprocess.TimeoutExpired ist
    eine SubprocessError, keine OSError -- ein unabgefangener Timeout fiel nach
    oben aus."""
    app_wurzel = tmp_path / "app"
    app_wurzel.mkdir()

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 10)

    monkeypatch.setattr(subprocess, "run", fake_run)
    ergebnis = browser_lauf._app_commit(app_wurzel)
    assert ergebnis is None


# --- Task 6: Pruef-Haken, Symptomregel, zweite Gruppe, Wissensfrage --------

from simulation import browser_invarianten as inv  # noqa: E402
from simulation import browser_stationen  # noqa: E402
from simulation.browser_umgebung import Gruppe  # noqa: E402

_UNGEKLAERT = "App oder Werkzeug – ungeklaert"


def _p1_stand(**kw) -> "inv.P1Stand":
    werte = dict(board_begriffe=(), board_zeilen=0, transkript_zeichen=0, ende_leer=False,
                 arbeitsstand_begriffe="", max_bot_id=0, bot_ids=())
    werte.update(kw)
    return inv.P1Stand(**werte)


def _lege_zweite_gruppe_an(pfad: str) -> Gruppe:
    conn = db.verbinde(pfad)
    chat2 = CHAT + 1
    repo.sichere_gruppe(conn, chat2, "gruppe2", "Testgruppe 2")
    repo.setze_gruppe_kanal(conn, chat2, "web")
    token2 = repo.stelle_web_token_sicher(conn, chat2)
    conn.commit()
    conn.close()
    return Gruppe(token=token2, chat_id=chat2)


def _stationen_lauf(basis, token, pfad, tmp_path, stationen, *, persona=None,
                    vorbereitung=None, **kw):
    with sync_playwright() as p:
        browser = p.chromium.launch(); context = browser.new_context()
        seite = context.new_page()
        if vorbereitung:
            vorbereitung(seite)
        ergebnis = browser_lauf.fuehre_stationen(
            seite, context, basis_url=basis, token=token, db_pfad=pfad, chat_id=CHAT,
            persona_client=persona or _ScriptedClient([]), judge_client=_FakeJudge(),
            geraet="handy", persona_name="priya", stationen=tuple(stationen),
            lauf_verzeichnis=tmp_path / "l", **kw)
        url = seite.url
        browser.close()
    return ergebnis, url


def test_invarianten_landen_in_ergebnis_json(stack, tmp_path):
    basis, token, pfad = stack
    aufrufe = []

    def warte(db_pfad, chat_id, vorher, station, **kw):
        aufrufe.append((chat_id, station))
        return [inv.Befund(inv.BOARD_LEER, station, "Board leer (Attrappe).")], _p1_stand()

    station = browser_stationen.Station("t-ende", 1, "Listen.", ohne_persona=True, warte_s=0,
                                        pruefung=("nach_ende",))
    _stationen_lauf(basis, token, pfad, tmp_path, [station], warte=warte)
    ergebnis = json.loads((tmp_path / "l" / "ergebnis.json").read_text())
    assert aufrufe == [(CHAT, "t-ende")]
    befund = ergebnis["invarianten"][0]
    assert befund["schluessel"] == "board_leer_nach_ende"
    assert befund["schwere"] == "hoch"
    assert befund["ursache"] == _UNGEKLAERT
    assert befund["station"] == "t-ende"
    assert "top_befunde" in ergebnis
    # Kein Harness-Klick auf "Discussion done" -> vermerkt (Review, Minor 6).
    assert any("t-ende" in n and "Discussion done" in n for n in ergebnis["pruef_notizen"])


def test_station_nicht_erreicht_wird_befund_hoch(stack, tmp_path):
    basis, token, pfad = stack
    station = browser_stationen.Station("t-ziel", 1, "Unreachable.", fertig=lambda s: False,
                                        budget=1)
    persona = _ScriptedClient([{"type": "wait", "duration_ms": 50, "begruendung": "w"}])
    ergebnis, _ = _stationen_lauf(basis, token, pfad, tmp_path, [station], persona=persona)
    schluessel = [b["schluessel"] for b in ergebnis["invarianten"]]
    assert "station_nicht_erreicht:t-ziel" in schluessel
    befund = ergebnis["invarianten"][schluessel.index("station_nicht_erreicht:t-ziel")]
    assert befund["schwere"] == "hoch" and befund["ursache"] == _UNGEKLAERT


def test_ausnahme_in_station_wird_befund_nicht_verschluckt(stack, tmp_path, monkeypatch):
    basis, token, pfad = stack

    def wirft(*a, **kw):
        raise RuntimeError("Persona kaputt XYZ")

    monkeypatch.setattr(browser_lauf.browser_persona, "naechste_aktion", wirft)
    station = browser_stationen.Station("t-kaputt", 1, "Anything.", budget=2)
    ergebnis, _ = _stationen_lauf(basis, token, pfad, tmp_path, [station])
    befunde = [b for b in ergebnis["invarianten"]
               if b["schluessel"] == "station_nicht_erreicht:t-kaputt"]
    assert len(befunde) == 1
    assert "Persona kaputt XYZ" in befunde[0]["text"]
    assert befunde[0]["schwere"] == "hoch"
    assert ergebnis["fehlgeschlagen_bei"] == "t-kaputt"


def test_aufruf_waehrend_gescheiterter_station_bleibt_fuer_modellwahl_sichtbar(
        stack, tmp_path, monkeypatch):
    """M1 (Review 05.10.2026, Fix round 1): ein Aufruf, der WAEHREND einer
    gescheiterten Station entsteht, darf nicht aus ``aufruf_bereiche``
    herausfallen -- vorher wurde der Bereich einer Station NUR nach einem
    ERFOLGREICHEN ``_fuehre_station_aus`` aktualisiert, bei einer Ausnahme
    blieb er auf (von, von) stehen und der Aufruf war fuer den
    ``modellwahl``-Haken der naechsten Phase unsichtbar -- egal, ob er in
    Phase 3 oder 4 fiel."""
    basis, token, pfad = stack

    def fake(page, persona_client, mitschnitt, station, **kw):
        if station.schluessel == "p3-kaputt":
            conn = db.verbinde(pfad)
            conn.execute(
                "INSERT INTO aufruf (chat_id, art, modus, erstellt_am) VALUES (?, 'gespraech', 'C', ?)",
                (CHAT, repo._jetzt()))
            conn.commit(); conn.close()
            raise RuntimeError("kaputt waehrend aufruf")
        return {"schritte": 0, "nachfragen_beantwortet": 0, "offene_fragen": [],
                "fertig": True, "fallback_benutzt": False, "zaehler_summe": {},
                "screenshots_nach": []}

    monkeypatch.setattr(browser_lauf, "_fuehre_station_aus", fake)
    station_a = browser_stationen.Station("p3-kaputt", 3, "x", budget=1)
    station_b = browser_stationen.Station("p4-check", 4, "x", pruefung=("modellwahl",))
    ergebnis, _ = _stationen_lauf(basis, token, pfad, tmp_path, [station_a, station_b])
    schluessel = [b["schluessel"] for b in ergebnis["invarianten"]]
    assert inv.P3_GESPRAECH_OPUS in schluessel


@pytest.mark.parametrize("schluessel_fuer, erwartet", [
    (lambda t2: "vad_schwelle", True),
    (lambda t2: f"vad_schwelle:{t2}:2026-10-05", False),
])
def test_zweite_gruppe_selber_kontext(stack, tmp_path, schluessel_fuer, erwartet):
    basis, token, pfad = stack
    gruppe2 = _lege_zweite_gruppe_an(pfad)
    gruppen = [Gruppe(token=token, chat_id=CHAT), gruppe2]
    besucht = []

    def vorbereitung(seite):
        seite.goto(f"{basis}/g/{token}")
        seite.wait_for_selector("#verlauf")
        seite.evaluate("k => localStorage.setItem(k, '0.1')", schluessel_fuer(gruppe2.token))
        seite.on("framenavigated", lambda f: besucht.append(f.url) if f == seite.main_frame else None)

    station = browser_stationen.Station("t-zweite", 1, "Observe.", gruppe=2, ohne_persona=True,
                                        warte_s=0, pruefung=("zweite_gruppe",))
    ergebnis, url = _stationen_lauf(basis, token, pfad, tmp_path, [station],
                                    vorbereitung=vorbereitung, gruppen=gruppen)
    schluessel = [b["schluessel"] for b in ergebnis["invarianten"]]
    assert ("raumcheck_domainweit" in schluessel) is erwartet
    assert any(f"/g/{gruppe2.token}" in u for u in besucht)
    assert url.rstrip("/").endswith(f"/g/{token}")
    assert (tmp_path / "l" / "zweite-gruppe-t-zweite.png").exists()


class _BeobachterAttrappe:
    def __init__(self, begriffe):
        self._begriffe = tuple(begriffe)
        self.verlauf: list[int] = []
        self.page = None

    def messe(self):
        self.verlauf.append(len(self._begriffe))
        return len(self._begriffe)

    def begriffe(self):
        return self._begriffe

    def ergebnis(self):
        return {"board_verlauf": list(self.verlauf), "beobachter_neu_geladen": False,
                "board_bestanden": bool(self.verlauf)}


@pytest.mark.parametrize("prompt, antwort, erwartet", [
    ("no board here", "I can't see it", {"chat_kennt_board_nicht", "chat_nennt_board_nicht"}),
    ("home border", "home and border", set()),
])
def test_wissen_vergleicht_prompt_und_antwort(stack, tmp_path, monkeypatch, prompt, antwort, erwartet):
    basis, token, pfad = stack
    monkeypatch.setattr(_LLMAttrappe, "antwort", antwort)
    eingang_beim_abzug = []

    def hole_prompt(chat_id, text):
        conn = db.verbinde(pfad)
        eingang_beim_abzug.append(conn.execute(
            "SELECT COUNT(*) FROM web_post WHERE chat_id = ? AND richtung = 'ein' AND text = ?",
            (chat_id, text)).fetchone()[0])
        conn.close()
        assert text == inv.WISSENSFRAGE
        return prompt

    station = browser_stationen.Station("t-wissen", 1, "Ask.", ohne_persona=True,
                                        sage=inv.WISSENSFRAGE, pruefung=("wissen",))
    ergebnis, _ = _stationen_lauf(basis, token, pfad, tmp_path, [station],
                                  beobachter=_BeobachterAttrappe(("home", "border")),
                                  hole_prompt=hole_prompt)
    assert eingang_beim_abzug == [0]        # Prompt VOR dem Senden geholt
    assert {b["schluessel"] for b in ergebnis["invarianten"]} == erwartet
    assert (tmp_path / "l" / "prompt-t-wissen.txt").read_text() == prompt


class _SeiteAttrappe:
    def __init__(self, schluessel, measure_again=False):
        self._schluessel = schluessel
        self._measure_again = measure_again

    def evaluate(self, js, *a):
        assert js == "Object.keys(localStorage)"
        return list(self._schluessel)

    def locator(self, selektor):
        anzahl = 1 if (self._measure_again and "kalibrierung-neu" in selektor) else 0
        return type("L", (), {"count": lambda self_: anzahl})()


def test_fuehre_pruefungen_ohne_browser(tmp_path):
    gruppen = [Gruppe(token="tok1", chat_id=1), Gruppe(token="tok2", chat_id=2)]
    kontext = browser_lauf.PruefKontext(
        db_pfad=str(tmp_path / "gibt-es-nicht.db"), gruppen=gruppen,
        page=_SeiteAttrappe(["vad_schwelle", "vad_boden:tok1:2026-10-05", "anderes"]),
        stand=_p1_stand(board_begriffe=("night shed", "language")))
    station = browser_stationen.Station("t-rv", 1, "x", diskussion="verhoerer",
                                        pruefung=("raumcheck", "verhoerer"))
    befunde = browser_lauf.fuehre_pruefungen(station, kontext)
    assert [b.schluessel for b in befunde] == ["raumcheck_domainweit", "verhoerer_nicht_korrigiert"]
    assert "vad_schwelle" in befunde[0].text and "vad_boden:tok1" not in befunde[0].text
    assert befunde[1].schwere == "mittel"

    kontext.stand = _p1_stand(board_begriffe=("night shift",))
    kontext.page = _SeiteAttrappe(["vad_boden:tok1:2026-10-05"])
    assert browser_lauf.fuehre_pruefungen(station, kontext) == []


def test_fuehre_pruefungen_p34_nach_interview_ohne_browser(tmp_path):
    """Wie ``test_fuehre_pruefungen_ohne_browser``, aber fuer den neuen
    ``nach_interview``-Haken (Padua live-reif Phase 3+4, Task 2c): ohne
    Browser, mit einer Attrappe fuer ``warte_p34``.

    I6 (Review 05.10.2026, Fix round 1): die alte Attrappe gab ``pruefe``
    NIE weiter (``return [], lese()``) -- die eigentliche Verdrahtung
    (``_nach_aufnahme_p34`` -> ``kontext.warte_p34`` -> ``pruefe``) war damit
    gar nicht getestet, nur dass irgendetwas Leeres zurueckkommt. Jetzt ruft
    die Attrappe ``pruefe(lese())`` wirklich auf, gegen eine leere DB, die
    einen echten Befund liefert (keine Transkript-Blase, keine Statuszeile)."""
    pfad = str(tmp_path / "p34.db")
    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    aufbau.close()
    gruppen = [Gruppe(token="tok1", chat_id=CHAT)]

    def warte_p34(lese, pruefe, *, frist_s, ende=None, grace_s=None):
        stand = lese()
        return pruefe(stand), stand

    kontext = browser_lauf.PruefKontext(
        db_pfad=pfad, gruppen=gruppen, page=None, warte_p34=warte_p34)
    station = browser_stationen.Station("p3-x", 3, "x", pruefung=("nach_interview",),
                                        aufnahme="interview")
    befunde = browser_lauf.fuehre_pruefungen(station, kontext)
    assert {b.schluessel for b in befunde} == {inv.INTERVIEW_OHNE_BLASE, inv.INTERVIEW_OHNE_STATUS}


def test_nach_interview_und_nach_brainstorm_reichen_die_passende_gnadenfrist_durch(tmp_path):
    """M3 (Review 05.10.2026, Fix round 2): ``_nach_interview`` muss die
    laengere ``inv.GRACE_NACH_INTERVIEW_S`` an ``kontext.warte_p34``
    weitergeben (kuerzer als der Nachhol-Takt liesse eine zweite, erst
    nachgeholte Statuszeile unbemerkt), ``_nach_brainstorm`` bleibt bei der
    kurzen Vorgabe ``inv.GRACE_NACH_SIGNAL_S``."""
    pfad = str(tmp_path / "p34.db")
    aufbau = db.verbinde(pfad); db.initialisiere(aufbau); aufbau.close()
    gruppen = [Gruppe(token="tok1", chat_id=CHAT)]
    gesehen = {}

    def warte_p34(lese, pruefe, *, frist_s, ende=None, grace_s=None):
        gesehen["grace_s"] = grace_s
        stand = lese()
        return pruefe(stand), stand

    kontext = browser_lauf.PruefKontext(
        db_pfad=pfad, gruppen=gruppen, page=None, warte_p34=warte_p34)
    station_interview = browser_stationen.Station(
        "p3-x", 3, "x", pruefung=("nach_interview",), aufnahme="interview")
    browser_lauf.fuehre_pruefungen(station_interview, kontext)
    assert gesehen["grace_s"] == inv.GRACE_NACH_INTERVIEW_S

    kontext2 = browser_lauf.PruefKontext(
        db_pfad=pfad, gruppen=gruppen, page=None, warte_p34=warte_p34)
    station_brainstorm = browser_stationen.Station(
        "p4-x", 4, "x", pruefung=("nach_brainstorm",), aufnahme="brainstorm")
    browser_lauf.fuehre_pruefungen(station_brainstorm, kontext2)
    assert gesehen["grace_s"] == inv.GRACE_NACH_SIGNAL_S


def test_nach_brainstorm_notiz_nennt_discussion_done_nicht_den_alten_toggle(tmp_path):
    """Birk 05.10.2026 22:00: kein eigener Brainstorm-Toggle mehr -- die
    Notiz, die laeuft, wenn der Harness den Ende-Knopf nie selbst geklickt
    hat (``kontext.ergebnis_p34 is None``), muss "Discussion done" nennen
    wie beim Diskussions-Haken, nicht mehr "Brainstorm-Toggle"."""
    pfad = str(tmp_path / "p34.db")
    aufbau = db.verbinde(pfad); db.initialisiere(aufbau); aufbau.close()
    gruppen = [Gruppe(token="tok1", chat_id=CHAT)]

    def warte_p34(lese, pruefe, *, frist_s, ende=None, grace_s=None):
        stand = lese()
        return pruefe(stand), stand

    kontext = browser_lauf.PruefKontext(
        db_pfad=pfad, gruppen=gruppen, page=None, warte_p34=warte_p34)
    station = browser_stationen.Station(
        "p4-x", 4, "x", pruefung=("nach_brainstorm",), aufnahme="brainstorm")
    browser_lauf.fuehre_pruefungen(station, kontext)
    assert any("p4-x" in n and "Discussion done" in n for n in kontext.notizen)
    assert not any("Toggle" in n for n in kontext.notizen)


def test_bereich_je_phase_vereinigt_alle_stationen_dieser_phase():
    """I6 (Review 05.10.2026, Fix round 1): reiner Test von
    ``browser_pruefhaken._bereich_je_phase`` mit vorbereiteten
    ``aufruf_bereiche``/``stationen_phase`` -- bisher nur indirekt ueber den
    Browser-Lauf gestreift."""
    from simulation import browser_pruefhaken as bph

    kontext = browser_lauf.PruefKontext(
        db_pfad="x", gruppen=[Gruppe("tok1", CHAT)], page=None,
        aufruf_bereiche={"p3-a": (0, 5), "p3-b": (5, 9), "p4-a": (9, 20)},
        stationen_phase={"p3-a": 3, "p3-b": 3, "p4-a": 4})
    assert bph._bereich_je_phase(kontext, 3) == (0, 9)
    assert bph._bereich_je_phase(kontext, 4) == (9, 20)
    # Keine Station dieser Phase gelaufen -- (0, 0), der "nichts da"-Fall.
    assert bph._bereich_je_phase(kontext, 5) == (0, 0)


def test_modellwahl_haken_nutzt_bereich_je_phase(tmp_path):
    """I6 (Review 05.10.2026, Fix round 1): reiner Test von
    ``browser_pruefhaken._modellwahl`` -- liest die aufbereiteten Bereiche
    aus dem Kontext und reicht sie an ``pruefe_modellwahl`` weiter."""
    from simulation import browser_pruefhaken as bph

    pfad = str(tmp_path / "p34.db")
    aufbau = db.verbinde(pfad); db.initialisiere(aufbau); aufbau.close()
    conn = db.verbinde(pfad)
    for i, (art, modus) in enumerate([("gespraech", "A"), ("gespraech", "A")], 1):
        conn.execute(
            "INSERT INTO aufruf (id, chat_id, art, modus, erstellt_am) VALUES (?, ?, ?, ?, ?)",
            (i, CHAT, art, modus, repo._jetzt()))
    conn.commit(); conn.close()
    kontext = browser_lauf.PruefKontext(
        db_pfad=pfad, gruppen=[Gruppe("tok1", CHAT)], page=None,
        aufruf_bereiche={"p3-uebergang": (0, 1), "p4-uebergang": (1, 2)},
        stationen_phase={"p3-uebergang": 3, "p4-uebergang": 4})
    station = browser_stationen.Station("p4-uebergang", 4, "x", pruefung=("modellwahl",))
    befunde = bph._modellwahl(station, kontext, CHAT)
    assert [b.schluessel for b in befunde] == [inv.P4_GESPRAECH_NICHT_OPUS]


def test_modellwahl_haken_meldet_p3_befund_nur_an_der_phase3_station(tmp_path):
    """M2 (Review 05.10.2026, Fix round 2): vor dem Fix prueft
    ``_modellwahl`` an JEDER Station IMMER beide Phasenteile. An
    ``p3-uebergang`` lieferte das IMMER
    ``nicht_pruefbar:p4_gespraech_nicht_opus`` (der Phase-4-Bereich ist dort
    noch leer, keine Phase-4-Station ist gelaufen), und ein echter
    ``P3_GESPRAECH_OPUS``-Befund kaeme an der spaeteren Station
    ``p4-uebergang`` ein zweites Mal (derselbe Phase-3-Bereich wird dort
    erneut geprueft). Mit ``nur_phase=station.phase`` meldet jede Station
    nur noch ihren eigenen Teil."""
    from simulation import browser_pruefhaken as bph

    pfad = str(tmp_path / "p34.db")
    aufbau = db.verbinde(pfad); db.initialisiere(aufbau); aufbau.close()
    conn = db.verbinde(pfad)
    # Ein Opus-Gespraechsaufruf WAEHREND Phase 3 (Datenschutzverstoss).
    conn.execute(
        "INSERT INTO aufruf (id, chat_id, art, modus, erstellt_am) VALUES (?, ?, ?, ?, ?)",
        (1, CHAT, "gespraech", "C", repo._jetzt()))
    conn.commit(); conn.close()
    kontext = browser_lauf.PruefKontext(
        db_pfad=pfad, gruppen=[Gruppe("tok1", CHAT)], page=None,
        aufruf_bereiche={"p3-uebergang": (0, 1)},
        stationen_phase={"p3-uebergang": 3})
    station3 = browser_stationen.Station("p3-uebergang", 3, "x", pruefung=("modellwahl",))
    befunde3 = bph._modellwahl(station3, kontext, CHAT)
    # Der P3-Befund kommt, aber KEIN Rauschen ueber den (noch leeren) Phase-4-Bereich.
    assert [b.schluessel for b in befunde3] == [inv.P3_GESPRAECH_OPUS]

    # Phase 4 ist jetzt (ohne eigenen Gespraechsaufruf) auch gelaufen --
    # derselbe Phase-3-Bereich bleibt im Kontext unveraendert stehen.
    kontext.aufruf_bereiche["p4-uebergang"] = (1, 1)
    kontext.stationen_phase["p4-uebergang"] = 4
    station4 = browser_stationen.Station("p4-uebergang", 4, "x", pruefung=("modellwahl",))
    befunde4 = bph._modellwahl(station4, kontext, CHAT)
    # Der P3-Befund darf an der Phase-4-Station nicht noch einmal kommen.
    assert inv.P3_GESPRAECH_OPUS not in {b.schluessel for b in befunde4}


def test_teile_bereich_am_phasenwechsel_splittet_nur_wenn_wechsel_dazwischen_liegt():
    """I4 (Review 05.10.2026, Fix round 1): reiner Test von
    ``browser_lauf._teile_bereich_am_phasenwechsel``."""
    bereiche, phasen_je_station = {}, {}
    browser_lauf._teile_bereich_am_phasenwechsel(
        bereiche, phasen_je_station, "p3-uebergang", 3, 5, 12, 8)
    assert bereiche == {"p3-uebergang": (5, 8), "p3-uebergang:nach_phasenwechsel": (8, 12)}
    assert phasen_je_station == {"p3-uebergang:nach_phasenwechsel": 4}

    bereiche2, phasen2 = {}, {}
    browser_lauf._teile_bereich_am_phasenwechsel(bereiche2, phasen2, "p4-eintritt", 4, 5, 12, None)
    assert bereiche2 == {"p4-eintritt": (5, 12)}
    assert phasen2 == {}

    # P34 Runde 2: Grenze == ``von`` (Wechsel, bevor die Station einen
    # Aufruf gebucht hat) -- jetzt Split mit leerem Vorher-Bereich, der
    # ganze Bereich zaehlt als naechste Phase.
    bereiche3, phasen3 = {}, {}
    browser_lauf._teile_bereich_am_phasenwechsel(bereiche3, phasen3, "p3-uebergang", 3, 5, 12, 5)
    assert bereiche3 == {"p3-uebergang": (5, 5), "p3-uebergang:nach_phasenwechsel": (5, 12)}
    assert phasen3 == {"p3-uebergang:nach_phasenwechsel": 4}

    # Grenze == ``bis``: nach dem Wechsel kam kein Aufruf -- kein Split.
    bereiche4, phasen4 = {}, {}
    browser_lauf._teile_bereich_am_phasenwechsel(bereiche4, phasen4, "p3-uebergang", 3, 5, 12, 12)
    assert bereiche4 == {"p3-uebergang": (5, 12)}
    assert phasen4 == {}


def _p34_db_mit_aufrufen(tmp_path, aufrufe, phase_gesetzt_am):
    pfad = str(tmp_path / "p34.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Testgruppe")
    if phase_gesetzt_am is not None:
        repo.setze_phase(conn, CHAT, 4)
        conn.execute("UPDATE arbeitsstand SET phase_gesetzt_am = ? WHERE chat_id = ?",
                     (phase_gesetzt_am, CHAT))
    for i, art, modus, zeit in aufrufe:
        conn.execute(
            "INSERT INTO aufruf (id, chat_id, art, modus, erstellt_am) VALUES (?, ?, ?, ?, ?)",
            (i, CHAT, art, modus, zeit))
    conn.commit()
    conn.close()
    return pfad


def test_phasenwechsel_grenze_kommt_aus_phase_gesetzt_am(tmp_path):
    """P34 Runde 1, C1 (Ursache Werkzeug, Lauf 205532): der Harness las die
    Grenze erst NACH ``warte_auf_antwort`` (``_max_aufruf_id``) -- da war der
    Phase-4-Einstieg (aufruf 16, Opus, 19:02:46) schon gebucht, die Phase
    aber um 19:02:42.93 gesetzt. ``von < 16 < bis`` griff nicht (16 == bis),
    der Aufruf zaehlte als Phase 3 -> falsches ``p3_gespraech_ueber_opus``.
    Die Grenze ist jetzt der letzte Aufruf bis ``phase_gesetzt_am``."""
    pfad = _p34_db_mit_aufrufen(tmp_path, [
        (14, "gespraech", "A", "2026-10-05T19:02:30+00:00"),
        (15, "extraktor", "A", "2026-10-05T19:02:42+00:00"),
        (16, "gespraech", "C", "2026-10-05T19:02:46+00:00"),
    ], "2026-10-05T19:02:42.930000+00:00")

    grenze = browser_lauf._aufruf_id_bei_phasenwechsel(pfad, CHAT)
    assert grenze == 15

    bereiche, phasen_je_station = {}, {}
    browser_lauf._teile_bereich_am_phasenwechsel(
        bereiche, phasen_je_station, "p3-uebergang", 3, 13, 16, grenze)
    assert bereiche == {"p3-uebergang": (13, 15), "p3-uebergang:nach_phasenwechsel": (15, 16)}
    assert phasen_je_station == {"p3-uebergang:nach_phasenwechsel": 4}

    with inv.oeffne_lesend(pfad) as conn:
        stand = inv.lese_p34_stand(conn, CHAT)
    befunde = inv.pruefe_modellwahl(stand, bereiche["p3-uebergang"], (0, 0), "p3-uebergang",
                                    nur_phase=3)
    assert inv.P3_GESPRAECH_OPUS not in {b.schluessel for b in befunde}


def test_phasenwechsel_vor_jedem_aufruf_der_station_zaehlt_ganz_als_phase_4(tmp_path):
    """P34 Runde 2 (C1 Rest): die Gruppe wechselt in Phase 4, BEVOR die
    Station (``von`` = 13) einen Aufruf gebucht hat. Die Grenze ist dann
    ``von`` selbst; vorher griff ``von < grenze < bis`` nicht, der ganze
    Bereich zaehlte als Phase 3 -> falsches ``p3_gespraech_ueber_opus``."""
    pfad = _p34_db_mit_aufrufen(tmp_path, [
        (13, "gespraech", "A", "2026-10-05T19:02:30+00:00"),
        (14, "gespraech", "C", "2026-10-05T19:02:46+00:00"),
        (15, "gespraech", "C", "2026-10-05T19:02:50+00:00"),
    ], "2026-10-05T19:02:40.000000+00:00")

    grenze = browser_lauf._aufruf_id_bei_phasenwechsel(pfad, CHAT)
    assert grenze == 13

    bereiche, phasen_je_station = {}, {}
    browser_lauf._teile_bereich_am_phasenwechsel(
        bereiche, phasen_je_station, "p3-uebergang", 3, 13, 15, grenze)
    assert bereiche == {"p3-uebergang": (13, 13), "p3-uebergang:nach_phasenwechsel": (13, 15)}
    assert phasen_je_station == {"p3-uebergang:nach_phasenwechsel": 4}

    with inv.oeffne_lesend(pfad) as conn:
        stand = inv.lese_p34_stand(conn, CHAT)
    befunde = inv.pruefe_modellwahl(stand, bereiche["p3-uebergang"], (0, 0), "p3-uebergang",
                                    nur_phase=3)
    assert inv.P3_GESPRAECH_OPUS not in {b.schluessel for b in befunde}


def test_phasenwechsel_grenze_ohne_zeitstempel_faellt_auf_max_id_zurueck(tmp_path):
    pfad = _p34_db_mit_aufrufen(tmp_path, [
        (1, "gespraech", "A", "2026-10-05T19:02:30+00:00"),
        (2, "gespraech", "C", "2026-10-05T19:02:46+00:00"),
    ], None)
    assert browser_lauf._aufruf_id_bei_phasenwechsel(pfad, CHAT) == 2


def test_fuehre_pruefungen_zweite_gruppe_mit_dom_hinweis():
    gruppen = [Gruppe(token="tok1", chat_id=1), Gruppe(token="tok2", chat_id=2)]
    kontext = browser_lauf.PruefKontext(
        db_pfad="x", gruppen=gruppen,
        page=_SeiteAttrappe(["vad_schwelle", "vad_boden:tok1:2026-10-05"], measure_again=True))
    station = browser_stationen.Station("t-z", 1, "x", gruppe=2, pruefung=("zweite_gruppe",))
    befunde = browser_lauf.fuehre_pruefungen(station, kontext)
    assert [b.schluessel for b in befunde] == ["raumcheck_domainweit"]
    assert "Measure again" in befunde[0].text
    assert "vad_schwelle" in befunde[0].text and "vad_boden:tok1" not in befunde[0].text


def test_fuehre_pruefungen_zweite_gruppe_gruppe_eins_schluessel_ist_kein_befund():
    """Review Task 6, Important 1: auf dem behobenen Stand liegt die korrekt
    gebundene Messung von Gruppe 1 (``vad_*:<tok1>:<datum>``) auf demselben
    Geraet -- auf der Seite von Gruppe 2 ist das KEIN domainweiter Schluessel."""
    gruppen = [Gruppe(token="tok1", chat_id=1), Gruppe(token="tok2", chat_id=2)]
    kontext = browser_lauf.PruefKontext(
        db_pfad="x", gruppen=gruppen,
        page=_SeiteAttrappe(["vad_schwelle:tok1:2026-10-05", "vad_boden:tok1:2026-10-05",
                             "vad_rede:tok1:2026-10-05"]))
    station = browser_stationen.Station("t-z", 1, "x", gruppe=2, pruefung=("zweite_gruppe",))
    assert browser_lauf.fuehre_pruefungen(station, kontext) == []


def test_raumcheck_haken_unbestaetigter_raumcheck(tmp_path):
    """Abnahmelauf 05.10.2026: p1-kalibrierung galt als erreicht, obwohl
    weder ``vad_*`` im localStorage noch ``kalibrierung_modus`` stand --
    das macht der Haken jetzt sichtbar (dazu: domainweit nicht pruefbar)."""
    pfad = _leere_db(tmp_path)
    kontext = browser_lauf.PruefKontext(db_pfad=pfad, gruppen=[Gruppe("tok1", CHAT)],
                                        page=_SeiteAttrappe(["theme"]))
    station = browser_stationen.Station("p1-kalibrierung", 1, "x", pruefung=("raumcheck",))
    befunde = browser_lauf.fuehre_pruefungen(station, kontext)
    assert [b.schluessel for b in befunde] == [
        "nicht_pruefbar:raumcheck_domainweit", "raumcheck_nicht_bestaetigt"]
    assert all(b.schwere == "hoch" for b in befunde)

    conn = db.verbinde(pfad)
    repo.setze_kalibrierung_modus_herumreichen(conn, CHAT); conn.commit(); conn.close()
    assert [b.schluessel for b in browser_lauf.fuehre_pruefungen(station, kontext)] == [
        "nicht_pruefbar:raumcheck_domainweit"]

    kontext.page = _SeiteAttrappe(["vad_schwelle:tok1:2026-10-05"])
    assert browser_lauf.fuehre_pruefungen(station, kontext) == []


def test_fuehre_pruefungen_verhoerer_leeres_board_nicht_pruefbar(tmp_path):
    kontext = browser_lauf.PruefKontext(db_pfad="x", gruppen=[Gruppe("tok1", 1)], page=None,
                                        stand=_p1_stand(board_begriffe=()))
    station = browser_stationen.Station("t-v", 1, "x", diskussion="verhoerer",
                                        pruefung=("verhoerer",))
    (b,) = browser_lauf.fuehre_pruefungen(station, kontext)
    assert b.schluessel == "nicht_pruefbar:verhoerer_nicht_korrigiert" and b.schwere == "hoch"


def test_fuehre_pruefungen_ausnahme_im_haken_wird_befund():
    def warte(*a, **kw):
        raise RuntimeError("DB weg")

    kontext = browser_lauf.PruefKontext(db_pfad="x", gruppen=[Gruppe("tok1", 1)], page=None,
                                        vorher=_p1_stand(), warte=warte)
    station = browser_stationen.Station("t-n", 1, "x", pruefung=("nach_ende",))
    befunde = browser_lauf.fuehre_pruefungen(station, kontext)
    assert len(befunde) == 1
    assert befunde[0].schluessel == "pruefung_gescheitert:nach_ende"
    assert "DB weg" in befunde[0].text and befunde[0].schwere == "hoch"


def test_vorher_stand_wird_direkt_vor_discussion_done_gelesen(tmp_path, monkeypatch):
    """Der Vorher-Stand fuer ``nach_ende`` entsteht unmittelbar vor dem Klick
    auf 'Discussion done' (``vor_ende``), nicht am Stationsanfang."""
    from simulation import browser_mitschnitt

    pfad = str(tmp_path / "d.db")
    conn = db.verbinde(pfad); db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "g", "G"); conn.commit(); conn.close()
    reihenfolge = []
    monkeypatch.setattr(browser_lauf, "_beende_diskussion_deterministisch",
                        lambda page: reihenfolge.append("beende") or True)
    station = browser_stationen.Station("t-zuhoeren", 1, "x", budget=3, zuhoeren_s=1)
    persona = _ScriptedClient([
        {"type": "click", "element_id": 0, "begruendung": "start listening"},
        {"type": "done_station", "begruendung": "fertig"},
    ])
    with sync_playwright() as p:
        browser = p.chromium.launch(); seite = browser.new_page()
        seite.set_content(_FIXTURE_DISKUSSION_TOGGLE)
        browser_lauf._fuehre_station_aus(
            seite, persona, browser_mitschnitt.Mitschnitt(tmp_path / "l", "h", "handy"),
            station, basis_url="http://127.0.0.1:1", token="t", db_pfad=pfad, chat_id=CHAT,
            persona_name="giulia", vor_ende=lambda: reihenfolge.append("vorher"))
        browser.close()
    assert reihenfolge == ["vorher", "beende"]


def _leere_db(tmp_path) -> str:
    pfad = str(tmp_path / "d.db")
    conn = db.verbinde(pfad); db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "g", "G"); conn.commit(); conn.close()
    return pfad


def test_diskussionsstation_endet_nach_dem_harness_klick(tmp_path, monkeypatch):
    """Abnahmelauf cb200e4 (05.10.2026): nach dem Klick auf 'Discussion
    done' startete die Persona neu und drueckte 'Take these' -- Phase 2,
    kein Board mehr im CoThinker. Eine Station mit ``diskussion`` endet
    deshalb mit dem Klick; die Persona wird danach nicht mehr gefragt."""
    from simulation import browser_mitschnitt

    pfad = _leere_db(tmp_path)
    monkeypatch.setattr(browser_lauf, "_beende_diskussion_deterministisch", lambda page: True)
    station = browser_stationen.Station("t-disk", 1, "x", budget=5, zuhoeren_s=1,
                                        diskussion="knapp")
    persona = _ScriptedClient([
        {"type": "click", "element_id": 0, "begruendung": "start listening"},
        {"type": "wait", "duration_ms": 10, "begruendung": "darf nie kommen"},
    ])
    with sync_playwright() as p:
        browser = p.chromium.launch(); seite = browser.new_page()
        seite.set_content(_FIXTURE_DISKUSSION_TOGGLE)
        ergebnis = browser_lauf._fuehre_station_aus(
            seite, persona, browser_mitschnitt.Mitschnitt(tmp_path / "l", "h", "handy"),
            station, basis_url="http://127.0.0.1:1", token="t", db_pfad=pfad, chat_id=CHAT,
            persona_name="student")
        browser.close()
    assert persona.aufrufe == 1 and ergebnis["schritte"] == 1


def test_diskussionsstation_endet_wenn_die_persona_selbst_beendet(tmp_path, monkeypatch):
    """Beendet die Persona die laufende Diskussion selbst (vor dem
    Harness), endet die Station ebenfalls nach diesem Schritt."""
    from simulation import browser_mitschnitt

    pfad = _leere_db(tmp_path)
    station = browser_stationen.Station("t-disk", 1, "x", budget=5, zuhoeren_s=0,
                                        diskussion="knapp")
    persona = _ScriptedClient([
        {"type": "click", "element_id": 0, "begruendung": "start listening"},
        {"type": "click", "element_id": 1, "begruendung": "discussion done"},
        {"type": "wait", "duration_ms": 10, "begruendung": "darf nie kommen"},
    ])
    with sync_playwright() as p:
        browser = p.chromium.launch(); seite = browser.new_page()
        seite.set_content(_FIXTURE_DISKUSSION_TOGGLE)
        ergebnis = browser_lauf._fuehre_station_aus(
            seite, persona, browser_mitschnitt.Mitschnitt(tmp_path / "l", "h", "handy"),
            station, basis_url="http://127.0.0.1:1", token="t", db_pfad=pfad, chat_id=CHAT,
            persona_name="student")
        browser.close()
    assert persona.aufrufe == 2 and ergebnis["schritte"] == 2


def test_diskussions_audio_zuhoerdauer_aus_wav(tmp_path, monkeypatch):
    from simulation import erzeuge_diskussion_audio as eda

    erzeugt = []
    monkeypatch.setattr(eda, "erzeuge", lambda skript, wav, *, ende_pause_s=0.0:
                        erzeugt.append((skript.name, wav.name, ende_pause_s)) or wav)
    monkeypatch.setattr(eda, "dauer_s", lambda wav: 41.2)
    station = browser_stationen.Station("t", 1, "x", zuhoeren_s=None, diskussion="knapp")
    wav, sekunden = browser_lauf._diskussions_audio(station, tmp_path)
    assert erzeugt == [("p1-knapp.txt", "diskussion-knapp.wav", 8.0)]
    assert wav == tmp_path / "diskussion-knapp.wav"
    assert sekunden == 47
    fest = browser_stationen.Station("t", 1, "x", zuhoeren_s=30, diskussion="knapp")
    assert browser_lauf._diskussions_audio(fest, tmp_path)[1] == 30


def test_station_mit_diskussion_startet_persona_browser_neu(stack, tmp_path, monkeypatch):
    """Vor einer Station mit ``diskussion`` ruft der Motor ``wechsle_audio``
    mit deren WAV und arbeitet danach auf der zurueckgegebenen Seite."""
    basis, token, pfad = stack
    monkeypatch.setattr(browser_lauf, "_diskussions_audio",
                        lambda st, lv: (Path(lv) / f"diskussion-{st.diskussion}.wav", 7))
    gewechselt = []
    with sync_playwright() as p:
        browser = p.chromium.launch(); context = browser.new_context()
        seite = context.new_page()
        neu_ctx = browser.new_context(); neu = neu_ctx.new_page()

        def wechsle_audio(wav):
            gewechselt.append(wav.name)
            neu.goto(f"{basis}/g/{token}")
            neu.wait_for_selector("#verlauf")
            return neu, neu_ctx

        station = browser_stationen.Station("t-disk", 1, "x", ohne_persona=True, warte_s=0,
                                            diskussion="verhoerer", zuhoeren_s=None)
        browser_lauf.fuehre_stationen(
            seite, context, basis_url=basis, token=token, db_pfad=pfad, chat_id=CHAT,
            persona_client=_ScriptedClient([]), judge_client=_FakeJudge(), geraet="handy",
            persona_name="priya", stationen=(station,), lauf_verzeichnis=tmp_path / "l",
            wechsle_audio=wechsle_audio)
        browser.close()
    assert gewechselt == ["diskussion-verhoerer.wav"]


def test_nach_ende_wartet_direkt_nach_dem_klick_persona_verdeckt_stille_nicht(
        stack, tmp_path, monkeypatch):
    """Review Task 6, Important 2: nach dem Harness-Klick auf 'Discussion
    done' schweigt der Bot; danach tippt die Persona noch etwas und der Bot
    antwortet NUR darauf. Diese spaetere Antwort darf die Stille nach dem
    Klick nicht verdecken -- ``nach_ende`` wartet deshalb direkt nach dem
    Klick, nicht am Stationsende."""
    basis, token, pfad = stack
    monkeypatch.setattr(browser_lauf, "_diskussion_laeuft", lambda page: True)
    klicks = []
    monkeypatch.setattr(browser_lauf, "_beende_diskussion_deterministisch",
                        lambda page: klicks.append(time.monotonic()) or True)
    gewartet = []

    def warte(db_pfad, chat_id, vorher, station, **kw):
        gewartet.append(time.monotonic())
        return inv.warte_nach_diskussion(db_pfad, chat_id, vorher, station,
                                         frist_s=0.5, takt_s=0.1)

    station = browser_stationen.Station("t-still", 1, "Listen, then chat.", budget=4,
                                        zuhoeren_s=1, pruefung=("nach_ende",))
    persona = _ScriptedClient([
        {"type": "wait", "duration_ms": 50, "begruendung": "liegt auf dem Tisch"},
        {"type": "type_send", "text": "Are you still there", "begruendung": "nach dem Klick"},
        {"type": "done_station", "begruendung": "fertig"},
    ])
    ergebnis, _ = _stationen_lauf(basis, token, pfad, tmp_path, [station], persona=persona,
                                  warte=warte)
    assert len(klicks) == 1 and len(gewartet) == 1
    assert gewartet[0] >= klicks[0]
    conn = db.verbinde(pfad)
    antworten = conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE chat_id = ? AND richtung = 'aus' AND text = ?",
        (CHAT, _LLMAttrappe.antwort)).fetchone()[0]
    conn.close()
    assert antworten >= 1            # der Bot HAT auf die spaetere Nachricht geantwortet
    schluessel = [b["schluessel"] for b in ergebnis["invarianten"]]
    assert any(s.startswith("stille_") for s in schluessel), schluessel
    assert not any("t-still" in n for n in ergebnis["pruef_notizen"])


def test_fehler_in_der_nachbereitung_kostet_ergebnis_json_nicht(stack, tmp_path, monkeypatch):
    """Review Task 6, Minor 7: ein Fehler im Richter/in der Blasenlese nach
    einer Station wird ein Befund, ergebnis.json entsteht trotzdem."""
    basis, token, pfad = stack

    def wirft(*a, **kw):
        raise RuntimeError("Richter kaputt")

    monkeypatch.setattr(browser_lauf.browser_judge, "bewerte_erklaerung", wirft)
    station = browser_stationen.Station("t-nach", 1, "Observe.", ohne_persona=True, warte_s=0)
    ergebnis, _ = _stationen_lauf(basis, token, pfad, tmp_path, [station])
    gespeichert = json.loads((tmp_path / "l" / "ergebnis.json").read_text())
    befunde = [b for b in gespeichert["invarianten"]
               if b["schluessel"] == "pruefung_gescheitert:nachbereitung"]
    assert len(befunde) == 1 and "Richter kaputt" in befunde[0]["text"]
    assert befunde[0]["schwere"] == "hoch"
    assert gespeichert["stationen_ergebnisse"][0]["schluessel"] == "t-nach"
    assert ergebnis["invarianten"] == gespeichert["invarianten"]


def test_ergebnis_json_auch_bei_durchschlagender_ausnahme(stack, tmp_path, monkeypatch):
    basis, token, pfad = stack

    class _Abbruch(BaseException):  # nicht von ``except Exception`` gefangen
        pass

    def wirft(*a, **kw):
        raise _Abbruch()

    monkeypatch.setattr(browser_lauf, "fuehre_pruefungen", wirft)
    station = browser_stationen.Station("t-x", 1, "Observe.", ohne_persona=True, warte_s=0)
    with pytest.raises(_Abbruch):
        _stationen_lauf(basis, token, pfad, tmp_path, [station])
    assert (tmp_path / "l" / "ergebnis.json").exists()
