"""Phase 4, Brainstorm ueber die EINE Diskussionssteuerung -- der volle
Ablauf im echten Browser, gegen den echten Bot (Birk, 05.10.2026 22:00:
Phase 4 bekommt keinen eigenen Toggle mehr, sondern genau die Phase-1-
Bedienung "Start listening" / "Discussion done", mit CoThinker-Karten im
Hintergrund waehrend des Zuhoerens plus einer letzten Karte auf "Discussion
done").

Harness wie ``tests/e2e/test_web_diskussion_e2e.py`` (``bot.schleife`` und
``web.baue_server`` je in einem Thread desselben Prozesses, ``IT_WORKSHOP=
padua-2026``, ``LLMAttrappe``, gefaelschtes zweistufiges Whisper) -- hier auf
Phase 4 umgestellt: ``repo.setze_phase(aufbau, CHAT, 4)`` statt 1, und die
``LLMAttrappe`` bekommt zusaetzlich ``prosa()`` (``buehnenkarte.erzeuge``
ruft ``klm.prosa(...)``, nicht ``klm.schema(...)``) -- sie liefert einen
Kartentext, der Woerter aus ``TRANSKRIPT`` aufgreift (Belegzitat/Erdung ist
Sache der Simulation, nicht dieses Tests; hier geht es um die PLOMBIERUNG:
dieselbe Steuerung, derselbe Upload-Pfad, dieselbe Karte).

``szene_claude.ist_aktiv`` wird defensiv auf ``False`` gepatcht (Default ist
es ohnehin schon, ``e.szene_anbieter`` bleibt hier ungesetzt) -- sonst wuerde
``buehnenkarte.erzeuge`` versuchen, ueber den Anthropic-Pfad zu laufen, fuer
den dieser Test keine Gegenstelle hat.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_mithoeren_phase4_e2e.py -q
"""

import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

import httpx  # noqa: E402

from interview_theater import (  # noqa: E402
    bot, db, einstellungen, repo, szene_claude, web, web_chat, web_kanal, workshop,
)
from tests.e2e.test_web_chat_e2e import _MESSUNG  # noqa: E402

CHAT = 7_000_000_000_010  # eigene chat_id -- nie dieselbe wie ein anderer e2e-Lauf
SCHLUESSEL = b"p" * 32
GEDULD_S = 30.0
SCHRITT_S = 0.1

#: Wie in test_web_diskussion_e2e.py: Chromiums synthetischer Ton ist ein
#: DAUERTON -- Segmente ohne manuelle RMS-Manipulation entstehen nur ueber
#: den harten Zeitdeckel. Fuer die Pausen-Tests hier wird die RMS gezielt auf
#: 0.0 gesetzt (siehe Tests 2/3).
VAD_MAX_MS = 90_000

#: Der von der gefaelschten Whisper-Gegenstelle gelieferte Text -- erfunden,
#: kurz genug, dass die Standard-Abschlussschwelle (150 Zeichen) ohne
#: Env-Override NICHT reicht (Tests setzen sie bewusst herab, wo eine echte
#: Karte entstehen soll).
TRANSKRIPT = "Wir erzaehlen uns gerade, wie es war, als wir hier ankamen."

#: Der Kartentext unserer LLMAttrappe -- greift Woerter aus TRANSKRIPT auf.
KARTENTEXT = "The arrival at this place still echoes through the room."

HANDY = {"width": 390, "height": 844}
GEDULD_MS = 20000


class LLMAttrappe:
    """Wie ``test_web_diskussion_e2e.py::LLMAttrappe``, um ``prosa()``
    ergaenzt -- ``buehnenkarte.erzeuge`` ruft ``klm.prosa(...)``, nicht
    ``klm.schema(...)`` (siehe ``interview_theater/buehnenkarte.py``)."""

    def __init__(self):
        self.nutzertexte = []
        self.gespraechszuege = 0
        self.prosa_aufrufe = 0
        self._sperre = threading.Lock()

    def schema(self, chat_id, system, nutzer, schema, art, **kw):
        if art == "erkenner":
            return {"aenderungen": []}
        if art == "journal":
            return {"eintraege": []}
        if art == "begriffsboard":
            return {"board": []}
        # Jeder andere Aufruf ist ein normaler Gespraechszug (z. B. das
        # versteckte "/start" beim ersten Seitenaufruf) -- ein Diskussions-
        # /Brainstorm-SEGMENT loest das dagegen nie aus (aufnahme.
        # _brainstorm_abschliessen/_diskussion_abschliessen rufen weder
        # Erkenner noch Journal noch ``zug`` auf). Die Tests zaehlen
        # ``gespraechszuege`` deshalb VOR dem ersten Klick auf "Start
        # listening" ab -- der Zaehler darf danach nicht mehr wachsen.
        with self._sperre:
            self.nutzertexte.append(nutzer)
            self.gespraechszuege += 1
        return {"antwort": "Hello! Let's get started."}

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None, bei_teil=None):
        with self._sperre:
            self.prosa_aufrufe += 1
        return KARTENTEXT


def stt_attrappe(text: str) -> httpx.Client:
    """Wie ``test_web_diskussion_e2e.py::stt_attrappe``: Upload liefert eine
    batch_id, die erste Abfrage ist fertig. ``data`` ist ein JSON-STRING
    (Falle 2), genau wie beim echten Anbieter."""

    def handler(anfrage):
        if "audio/transcriptions" in anfrage.url.path:
            return httpx.Response(200, json={"batch_id": "B1"})
        return httpx.Response(200, json={
            "status": "success", "data": json.dumps({"text": text}),
        })

    return httpx.Client(transport=httpx.MockTransport(handler))


class _Halt(Exception):
    """Beendet ``bot.schleife`` von aussen (wie in test_web_diskussion_e2e.py)."""


class _HaltbarerKanal(web_kanal.WebKanal):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.halt = threading.Event()

    def hole_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        if self.halt.is_set():
            raise _Halt()
        return super().hole_updates(offset, timeout=min(timeout, 0.5))


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    """Webserver und Bot-Schleife im Thread, Gruppe gleich in Phase 4 (statt
    Phase 1 wie test_web_diskussion_e2e.py) -- derselbe Grundaufbau, kein
    eigener Brainstorm-Pfad mehr noetig: ``#diskussion`` bedient beide
    Phasen."""
    vorher = set(threading.enumerate())
    workshop.vergiss()
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")
    monkeypatch.setenv("IT_AUDIO", str(tmp_path / "audio"))
    monkeypatch.setenv("IT_WEB_VAD_MAX_MS", str(VAD_MAX_MS))
    monkeypatch.setenv("IT_WEB_SEGMENT_MS", str(VAD_MAX_MS))
    # Kalibrierung aus -- Tests 1-3 geht es um Steuerung/Karten, nicht um den
    # Raumcheck selbst (der hat eigene Tests 4/5 mit eingeschalteter
    # Kalibrierung).
    monkeypatch.setenv("IT_WEB_VAD_KALIBRIERUNG", "0")

    pfad = str(tmp_path / "t.db")
    audio = tmp_path / "audio"

    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    repo.sichere_gruppe(aufbau, CHAT, "gruppe-mithoeren-p4", "Die Denkenden")
    repo.setze_gruppe_kanal(aufbau, CHAT, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT)
    repo.setze_phase(aufbau, CHAT, 4)
    aufbau.commit()
    aufbau.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    web_faden = threading.Thread(target=dienst.serve_forever, daemon=True)
    web_faden.start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"

    bot_conn = db.verbinde(pfad)
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe-mithoeren-p4", db_pfad=pfad, audio_verz=str(audio),
        llm_url="u", llm_key="k", llm_modell="m", stt_basis="https://stt.test",
        stt_produkt="PRODUKT-ID", web_url="", kanal=einstellungen.KANAL_WEB,
        web_chat_id=CHAT,
    )
    klm = LLMAttrappe()
    kanal = _HaltbarerKanal(bot_conn, CHAT, str(audio), schritt_s=0.05)
    pool = ThreadPoolExecutor(max_workers=bot.POOL_GROESSE)
    stt = stt_attrappe(TRANSKRIPT)

    def fahre():
        try:
            bot.schleife(bot_conn, e, kanal, klm, stt, pool)
        except _Halt:
            pass

    bot_faden = threading.Thread(target=fahre, daemon=True)
    bot_faden.start()

    yield basis, token, pfad, klm

    kanal.halt.set()
    bot_faden.join(timeout=GEDULD_S)
    pool.shutdown(wait=True, cancel_futures=True)
    dienst.shutdown()
    dienst.server_close()
    web_faden.join(timeout=GEDULD_S)
    frist = time.monotonic() + GEDULD_S
    for faden in set(threading.enumerate()) - vorher:
        if faden is not threading.current_thread():
            faden.join(timeout=max(0.0, frist - time.monotonic()))
    stt.close()
    bot_conn.close()
    workshop.vergiss()
    assert not bot_faden.is_alive(), "bot.schleife ist nicht beendet"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch(args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
        ])
        yield chromium
        chromium.close()


@pytest.fixture
def seite(lauf, browser):
    basis, token, _pfad, _klm = lauf
    kontext = browser.new_context(
        viewport=HANDY, permissions=["microphone"],
        base_url=basis, is_mobile=True, has_touch=True,
    )
    kontext.add_init_script(_MESSUNG)
    blatt = kontext.new_page()
    blatt.set_default_timeout(GEDULD_MS)
    blatt.goto(f"{basis}/g/{token}/chat")
    yield blatt
    kontext.close()


def _anzahl_buehnenkarten(pfad: str, chat_id: int) -> int:
    conn = db.verbinde(pfad)
    try:
        zeile = conn.execute(
            "SELECT COUNT(*) AS n FROM buehnenkarte WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return zeile["n"]
    finally:
        conn.close()


# -- Test 1: dieselbe Bedienung wie Phase 1 ----------------------------------


def test_phase4_hat_dieselbe_bedienung_wie_phase1(lauf, seite):
    """Birk 05.10.2026 22:00: kein eigener Brainstorm-Knopf -- Phase 4
    benutzt ``#diskussion``/``#diskussion-beenden`` wie Phase 1, mit
    ``data-mithoeren-ziel="brainstorm"``."""
    text_an = web_chat.T._TEXT_DISKUSSION_AN

    assert seite.locator("#brainstorm").count() == 0, "kein eigener Brainstorm-Knopf mehr"
    knopf = seite.locator("#diskussion")
    expect(knopf).to_be_visible()
    expect(knopf).to_have_text(text_an)
    expect(knopf).to_have_attribute("data-mithoeren-ziel", "brainstorm")

    seite.click("#diskussion")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "1")
    # Birk 04.10.2026 (Phase 1): nur Start und Fertig, kein Pause-Knopf --
    # jetzt auch fuer Phase 4, da derselbe Knopfsatz.
    expect(seite.locator("#diskussion-aktionen button")).to_have_count(1)
    assert seite.locator("#diskussion-pause").count() == 0

    seite.click("#diskussion-beenden")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "0")


# -- Test 2: Pausenschnitt geht hoch, Ende bringt genau eine Reaktion -------


def test_pausenschnitt_geht_hoch_und_ende_bringt_genau_eine_reaktion(lauf, seite, monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    # TRANSKRIPT ist kuerzer als die Vorgabe-Abschlussschwelle (150 Zeichen) --
    # herabgesetzt, damit "Discussion done" zuverlaessig eine ECHTE Karte
    # anstoesst (keine Schweigen-Zeile, die im CoThinker-Tab nicht erscheint).
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")

    uploads = []
    seite.on("request", lambda r: uploads.append(r.url) if "chat/audio" in r.url else None)

    _basis, _token, pfad, klm = lauf
    vor_karten = _anzahl_buehnenkarten(pfad, CHAT)
    # Das versteckte "/start" beim ersten Seitenaufruf loest selbst einen
    # normalen Gespraechszug aus (Begruessung) -- abgewartet, BEVOR der
    # Zaehler fuer "kein Gespraechszug waehrend eines Segments" startet.
    expect(seite.locator(".blase.bot").first).to_be_visible(timeout=GEDULD_MS)
    vor_zuegen = klm.gespraechszuege

    seite.click("#diskussion")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "1")

    seite.evaluate("window.__t.setzeRms(0.6)")
    seite.wait_for_timeout(1500)
    seite.evaluate("window.__t.setzeRms(0.0)")
    seite.wait_for_timeout(4000)  # > PAUSE_MS (2500 ms Vorgabe)

    pause_uploads = [u for u in uploads if "grund=pause" in u and "brainstorm=1" in u]
    assert pause_uploads, uploads

    seite.click("#diskussion-beenden")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "0")
    seite.wait_for_timeout(1500)

    ende_uploads = [u for u in uploads if "grund=ende" in u and "brainstorm=1" in u]
    assert len(ende_uploads) == 1, uploads

    frist = time.monotonic() + GEDULD_S
    while time.monotonic() < frist and _anzahl_buehnenkarten(pfad, CHAT) <= vor_karten:
        time.sleep(SCHRITT_S)
    nach_karten = _anzahl_buehnenkarten(pfad, CHAT)
    assert nach_karten == vor_karten + 1, "genau eine neue Buehnenkarten-Zeile nach dem Ende"
    assert klm.gespraechszuege == vor_zuegen, (
        "kein Gespraechszug waehrend eines Brainstorm-Segments")

    karte = seite.locator('.tabs button[data-tab="buehne"]')
    expect(karte).to_be_visible(timeout=GEDULD_MS)
    karte.click()
    expect(seite.locator("#buehne-tafel")).to_contain_text("arrival", timeout=GEDULD_MS)
    assert klm.prosa_aufrufe >= 1


# -- Test 3: Zwischenkarte waehrend des Zuhoerens ----------------------------


def test_zwischenkarte_waehrend_des_zuhoerens(lauf, seite, monkeypatch):
    """Birk 05.10.2026 22:00: CoThinker-Karten laufen automatisch im
    Hintergrund, WAEHREND die Gruppe noch zuhoert -- nicht erst nach
    "Discussion done" (das war das alte Toggle-Verhalten)."""
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "10")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ABSTAND_S", "1")

    _basis, _token, pfad, _klm = lauf
    vor_karten = _anzahl_buehnenkarten(pfad, CHAT)

    seite.click("#diskussion")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "1")

    seite.evaluate("window.__t.setzeRms(0.6)")
    seite.wait_for_timeout(1500)
    seite.evaluate("window.__t.setzeRms(0.0)")
    seite.wait_for_timeout(4000)  # > PAUSE_MS -- erstes Segment hoch

    # Die Karte entsteht VOR "Discussion done" -- der Knopf laeuft noch.
    frist = time.monotonic() + GEDULD_S
    while time.monotonic() < frist and _anzahl_buehnenkarten(pfad, CHAT) <= vor_karten:
        time.sleep(SCHRITT_S)
    zwischen_karten = _anzahl_buehnenkarten(pfad, CHAT)
    assert zwischen_karten == vor_karten + 1, "die Zwischenkarte ist waehrend des Zuhoerens da"
    assert seite.locator("#diskussion").get_attribute("data-laeuft") == "1", (
        "die Karte kam, bevor 'Discussion done' gedrueckt wurde")

    seite.click("#diskussion-beenden")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "0")


# -- Tests 4/5: Raumcheck-Cache -----------------------------------------------


def _kal_init_skript(token: str) -> str:
    """Schreibt die drei Kalibrierungs-Schluessel unter dem Gruppentoken fuer
    HEUTE (lokale Zeit) -- dasselbe Format wie ``web_chat.py``s
    ``kalSchluessel(basis, gruppe, datum)`` (``'<basis>:<gruppe>:<JJJJ-MM-TT>'``)."""
    return f"""
    (function () {{
      function zwei(n) {{ return (n < 10 ? '0' : '') + n; }}
      var d = new Date();
      var datum = d.getFullYear() + '-' + zwei(d.getMonth() + 1) + '-' + zwei(d.getDate());
      var gruppe = {token!r};
      try {{
        localStorage.setItem('vad_boden_mess:' + gruppe + ':' + datum, '5');
        localStorage.setItem('vad_rede_mess:' + gruppe + ':' + datum, '40');
        localStorage.setItem('vad_schwelle:' + gruppe + ':' + datum, '20');
      }} catch (e) {{ /* localStorage kann fehlen */ }}
    }})();
    """


def test_raumcheck_cache_wird_in_phase_4_wiederverwendet(lauf, browser, monkeypatch):
    """Dieselbe Gruppe/derselbe Tag: ein Raumcheck-Cache (wie er aus Phase 1
    stammen koennte -- die Schluessel sind nicht phasengebunden) macht den
    Dialog in Phase 4 ueberfluessig, genauso wie in Phase 1."""
    monkeypatch.delenv("IT_WEB_VAD_KALIBRIERUNG", raising=False)  # Kalibrierung AN
    basis, token, _pfad, _klm = lauf
    kontext = browser.new_context(
        viewport=HANDY, permissions=["microphone"], base_url=basis,
        is_mobile=True, has_touch=True,
    )
    kontext.add_init_script(_MESSUNG)
    kontext.add_init_script(_kal_init_skript(token))
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD_MS)
    uploads = []
    seite.on("request", lambda r: uploads.append(r.url) if "chat/audio" in r.url else None)
    try:
        seite.goto(f"{basis}/g/{token}/chat")
        seite.click("#diskussion")
        expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "1")
        seite.wait_for_timeout(1500)
        assert seite.is_hidden("#kalibrierung"), "der Cache macht den Raumcheck ueberfluessig"
        assert [u for u in uploads if "kalibrierung=1" in u] == [], uploads
        seite.click("#diskussion-beenden")
        expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "0")
    finally:
        kontext.close()


def test_ohne_cache_kommt_der_raumcheck_wie_in_phase_1(lauf, browser, monkeypatch):
    """Ohne Cache (frischer ``localStorage``) erscheint der Raumcheck in
    Phase 4 genau wie in Phase 1 (``test_web_diskussion_raumcheck_e2e.py``)."""
    monkeypatch.delenv("IT_WEB_VAD_KALIBRIERUNG", raising=False)  # Kalibrierung AN
    basis, token, _pfad, _klm = lauf
    kontext = browser.new_context(
        viewport=HANDY, permissions=["microphone"], base_url=basis,
        is_mobile=True, has_touch=True,
    )
    kontext.add_init_script(_MESSUNG)
    kontext.add_init_script("try { localStorage.clear(); } catch (e) {}")
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD_MS)
    try:
        seite.goto(f"{basis}/g/{token}/chat")
        seite.evaluate("window.__t.setzeRms(0.0)")
        seite.click("#diskussion")
        expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "1")
        seite.wait_for_selector("#kalibrierung", state="visible")
        assert seite.is_hidden("#kalibrierung-start"), "kein zweiter Start-Knopf"

        seite.wait_for_selector("#kalibrierung-sprechen", state="visible", timeout=8000)
        seite.click("#kalibrierung-sprechen")
        seite.wait_for_timeout(500)
        seite.click("#kalibrierung-skip")
        assert seite.is_hidden("#kalibrierung")
        seite.wait_for_selector("#uhr", state="visible")
        assert re.search(r"0:0[01]$", seite.text_content("#uhr").strip())

        seite.click("#diskussion-beenden")
        expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "0")
    finally:
        kontext.close()
