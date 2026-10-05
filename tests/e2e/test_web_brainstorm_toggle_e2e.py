"""Brainstorm als Toggle im echten Browser (Padua P34 Task 5, t_cf87ee0a,
t_a8129d7f).

- Ein Tippen startet den Gedankenbogen, ein zweites schliesst ihn; dazwischen
  schneidet eine Sprechpause KEIN Segment (kein ``grund=pause``), nur das Ende
  geht mit ``grund=ende`` hoch -- genau einmal.
- Waehrend der Bogen laeuft, belegt der Knopf den Platz der Eingabezeile
  (``.fuss .zeile`` verborgen) -- und die neueste Nachricht bleibt trotzdem
  sichtbar ueber dem Fuss.

Webserver im Thread (wie ``test_web_brainstorm_ende_e2e.py``), keine
Bot-Schleife -- gezaehlt werden die Uploads (``chat/audio``) im Browser. Der
Pegel kommt aus ``_MESSUNG`` (``window.__t.setzeRms``).

Aufruf::

    env -i HOME=/home/birk PATH=/usr/bin:/bin \\
        /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest -q \\
        -p no:cacheprovider -m 'not dortmund' tests/e2e/test_web_brainstorm_toggle_e2e.py
"""

import sys
import threading
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo, web, web_kanal, workshop  # noqa: E402
from tests.e2e.test_web_chat_e2e import _MESSUNG  # noqa: E402

CHAT = 7_000_000_000_007   # eigene chat_id
SCHLUESSEL = b"z" * 32
HANDY = {"width": 390, "height": 844}
GEDULD_MS = 15000


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    workshop.vergiss()
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")
    monkeypatch.setenv("IT_AUDIO", str(tmp_path / "audio"))
    # Raumcheck aus -- hier geht es um Toggle und Fuss, nicht um die Kalibrierung.
    monkeypatch.setenv("IT_WEB_VAD_KALIBRIERUNG", "0")
    pfad = str(tmp_path / "t.db")
    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    repo.sichere_gruppe(aufbau, CHAT, "gruppe-brainstorm-toggle", "Die Denkenden")
    repo.setze_gruppe_kanal(aufbau, CHAT, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT)
    repo.setze_phase(aufbau, CHAT, 4)
    # 15 Bot-Nachrichten, damit der Verlauf scrollt und die letzte Blase
    # unten am Fuss steht. Ueber den WebKanal, wie im Betrieb.
    kanal = web_kanal.WebKanal(aufbau, CHAT, str(tmp_path / "audio"), schritt_s=0.01)
    for i in range(15):
        kanal.sende(CHAT, f"Nachricht {i + 1}: ein Gedanke, der etwas Platz braucht, "
                          f"damit der Verlauf wirklich laenger als der Bildschirm wird.")
    aufbau.commit()
    aufbau.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    faden = threading.Thread(target=dienst.serve_forever, daemon=True)
    faden.start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, tmp_path
    dienst.shutdown()
    dienst.server_close()
    faden.join(timeout=10)
    workshop.vergiss()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch(args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
        ])
        yield chromium
        chromium.close()


def _seite(browser, basis):
    kontext = browser.new_context(viewport=HANDY, permissions=["microphone"],
                                  base_url=basis, is_mobile=True, has_touch=True)
    kontext.add_init_script(_MESSUNG)
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD_MS)
    return kontext, seite


def test_toggle_pause_schneidet_nicht_und_ende_geht_hoch(lauf, browser):
    basis, token, _ = lauf
    kontext, seite = _seite(browser, basis)
    uploads = []
    seite.on("request", lambda r: uploads.append(r.url) if "chat/audio" in r.url else None)
    try:
        seite.goto(f"{basis}/g/{token}")
        seite.click("#brainstorm")
        seite.wait_for_selector('#brainstorm[data-laeuft="1"]')
        assert seite.is_hidden(".fuss .zeile")                # Modus belegt den Platz
        seite.evaluate("window.__t.setzeRms(0.6)")
        seite.wait_for_timeout(1500)
        seite.evaluate("window.__t.setzeRms(0.0)")
        seite.wait_for_timeout(4000)                           # > PAUSE_MS (2500)
        assert [u for u in uploads if "grund=pause" in u] == [], uploads
        seite.click("#brainstorm")                             # Bogen zu
        seite.wait_for_selector('#brainstorm[data-laeuft="0"]')
        seite.wait_for_timeout(1500)
        ende = [u for u in uploads if "grund=ende" in u and "brainstorm=1" in u]
        assert len(ende) == 1, uploads
        assert seite.is_visible(".fuss .zeile")
    finally:
        kontext.close()


def test_letzte_blase_bleibt_sichtbar_waehrend_brainstorm(lauf, browser):
    """t_a8129d7f Punkt 1: die letzte Blase steht ganz ueber dem Fuss UND
    ganz im sichtbaren Teil des Verlaufs -- ohne Brainstorm und mit. Gemessen
    rot vor dem ResizeObserver: beim Laden lag sie 60px unter dem sichtbaren
    Ende des Verlaufs (scrollTop 1503 statt 1563)."""
    basis, token, lauf_ordner = lauf
    kontext, seite = _seite(browser, basis)
    try:
        seite.goto(f"{basis}/g/{token}")
        seite.wait_for_selector("#verlauf > *")
        for an in (False, True):
            if an:
                seite.click("#brainstorm")
                seite.wait_for_selector('#brainstorm[data-laeuft="1"]')
            seite.wait_for_timeout(500)
            unten = seite.evaluate(
                "document.querySelector('#verlauf').lastElementChild"
                ".getBoundingClientRect().bottom")
            fuss = seite.evaluate(
                "document.querySelector('.fuss').getBoundingClientRect().top")
            sichtbar_bis = seite.evaluate(
                "document.querySelector('#verlauf').getBoundingClientRect().bottom")
            assert unten <= fuss + 1, (an, unten, fuss)
            assert unten <= sichtbar_bis + 1, (an, unten, sichtbar_bis)
            bild = Path(lauf_ordner) / f"p4-brainstorm-{'an' if an else 'aus'}.png"
            seite.screenshot(path=str(bild))
            print("SCREENSHOT", bild)
        seite.click("#brainstorm")
        seite.wait_for_selector('#brainstorm[data-laeuft="0"]')
    finally:
        kontext.close()
