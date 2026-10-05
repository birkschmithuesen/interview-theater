import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

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
    ``/g/<token>`` echt bis zum Tab-Wechsel zu befahren."""

    def schema(self, chat_id, system, nutzer, schema, art, **kw):
        if art == "erkenner":
            return {"aenderungen": []}
        if art == "journal":
            return {"eintraege": []}
        return {"antwort": "Got it, thanks."}


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


_FIXTURE_DISKUSSION_LAEUFT = """
<button id="diskussion" data-laeuft="1">Start listening</button>
<button id="diskussion-beenden">Discussion done</button>
"""

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
