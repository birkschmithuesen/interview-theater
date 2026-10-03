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
