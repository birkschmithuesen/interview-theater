"""Brainstorm ohne VAD schickt trotzdem 'ende' (Muster ``5532c95``) -- und die
letzte Blase bleibt sichtbar -- im echten Browser.

Birk, 05.10.2026 22:00: Phase 4 hat seit dem Umbau auf die Phase-1-Steuerung
keinen eigenen Toggle-Knopf mehr (``#brainstorm``) -- sie bedient sich ueber
``#diskussion``/``#diskussion-beenden`` wie Phase 1
(``tests/e2e/test_web_diskussion_e2e.py``), nur mit ``brainstorm=1`` statt
``diskussion=1`` im Upload (``sitzung.ziel`` kommt aus
``zustand.mithoerenZiel``, server-seitig ``mithoeren_ziel`` in Phase 4).
Diese Datei ersetzt den fruehren Toggle-Test (``test_beenden_ohne_vad_
schickt_das_ende``, click auf denselben Knopf startet UND beendet) durch das
Phase-1-Muster (Start-/Ende-Knopf getrennt) und uebernimmt zusaetzlich die
"letzte Blase bleibt sichtbar"-Pruefung aus dem geloeschten
``test_web_brainstorm_toggle_e2e.py`` (``test_letzte_blase_bleibt_sichtbar_
waehrend_brainstorm``), ebenfalls auf ``#diskussion`` umgestellt.

Webserver im Thread (wie ``test_web_diskussion_raumcheck_e2e.py``), keine
Bot-Schleife -- gezaehlt werden die Uploads (``chat/audio``) direkt im
Browser.

Aufruf::

    env -i HOME=/home/birk PATH=/usr/bin:/bin \\
        /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest -q \\
        -p no:cacheprovider -m 'not dortmund' tests/e2e/test_web_brainstorm_ende_e2e.py
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

CHAT = 7_000_000_000_006   # eigene chat_id
CHAT_BLASE = 7_000_000_000_007   # eigene chat_id, fuer die Sichtbarkeits-Pruefung
SCHLUESSEL = b"z" * 32
HANDY = {"width": 390, "height": 844}
GEDULD_MS = 15000


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    workshop.vergiss()
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")
    monkeypatch.setenv("IT_AUDIO", str(tmp_path / "audio"))
    # Raumcheck aus -- hier geht es nur um das Ende, nicht um die Kalibrierung.
    monkeypatch.setenv("IT_WEB_VAD_KALIBRIERUNG", "0")
    pfad = str(tmp_path / "t.db")
    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    repo.sichere_gruppe(aufbau, CHAT, "gruppe-brainstorm-ende", "Die Denkenden")
    repo.setze_gruppe_kanal(aufbau, CHAT, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT)
    repo.setze_phase(aufbau, CHAT, 4)
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


@pytest.fixture
def lauf_mit_verlauf(tmp_path, monkeypatch):
    """Wie ``lauf``, aber mit 15 vorab ueber den WebKanal gesendeten
    Bot-Nachrichten (fuer die Sichtbarkeits-Pruefung: der Verlauf muss
    laenger als der Bildschirm sein) -- uebernommen aus dem geloeschten
    ``test_web_brainstorm_toggle_e2e.py``."""
    workshop.vergiss()
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")
    monkeypatch.setenv("IT_AUDIO", str(tmp_path / "audio"))
    monkeypatch.setenv("IT_WEB_VAD_KALIBRIERUNG", "0")
    pfad = str(tmp_path / "t.db")
    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    repo.sichere_gruppe(aufbau, CHAT_BLASE, "gruppe-brainstorm-blase", "Die Denkenden")
    repo.setze_gruppe_kanal(aufbau, CHAT_BLASE, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT_BLASE)
    repo.setze_phase(aufbau, CHAT_BLASE, 4)
    kanal = web_kanal.WebKanal(aufbau, CHAT_BLASE, str(tmp_path / "audio"), schritt_s=0.01)
    for i in range(15):
        kanal.sende(CHAT_BLASE, f"Nachricht {i + 1}: ein Gedanke, der etwas Platz braucht, "
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


def test_beenden_ohne_vad_schickt_das_ende(lauf, browser):
    basis, token = lauf[0], lauf[1]
    kontext = browser.new_context(viewport=HANDY, permissions=["microphone"],
                                  base_url=basis, is_mobile=True, has_touch=True)
    # Ohne AudioContext: pegelAn() kehrt frueh zurueck, sitzung.vadAktiv bleibt leer.
    kontext.add_init_script("delete window.AudioContext; delete window.webkitAudioContext;")
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD_MS)
    uploads = []
    seite.on("request", lambda r: uploads.append(r.url) if "chat/audio" in r.url else None)
    try:
        seite.goto(f"{basis}/g/{token}/chat")
        # Birk 05.10.2026 22:00: kein Toggle mehr -- Phase 4 bedient sich wie
        # Phase 1, Start- und Ende-Knopf sind getrennt.
        seite.click("#diskussion")
        seite.wait_for_selector('#diskussion[data-laeuft="1"]')
        seite.wait_for_timeout(2000)
        seite.click("#diskussion-beenden")
        seite.wait_for_selector('#diskussion[data-laeuft="0"]')
        seite.wait_for_timeout(1500)
        ende = [u for u in uploads if "grund=ende" in u]
        assert len(ende) == 1, uploads
        assert "brainstorm=1" in ende[0], uploads
    finally:
        kontext.close()


def test_letzte_blase_bleibt_sichtbar_waehrend_brainstorm(lauf_mit_verlauf, browser):
    """t_a8129d7f Punkt 1 (uebernommen aus dem geloeschten
    ``test_web_brainstorm_toggle_e2e.py``): die letzte Blase steht ganz ueber
    dem Fuss UND ganz im sichtbaren Teil des Verlaufs -- ohne Mithoeren und
    mit. Der ResizeObserver, der das sicherstellt, haengt nicht am Knopf
    selbst (``#diskussion`` statt des fruehreren ``#brainstorm``) und bleibt
    unveraendert."""
    basis, token, lauf_ordner = lauf_mit_verlauf
    kontext = browser.new_context(viewport=HANDY, permissions=["microphone"],
                                  base_url=basis, is_mobile=True, has_touch=True)
    kontext.add_init_script(_MESSUNG)
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD_MS)
    try:
        seite.goto(f"{basis}/g/{token}")
        seite.wait_for_selector("#verlauf > *")
        for an in (False, True):
            if an:
                seite.click("#diskussion")
                seite.wait_for_selector('#diskussion[data-laeuft="1"]')
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
        seite.click("#diskussion-beenden")
        seite.wait_for_selector('#diskussion[data-laeuft="0"]')
    finally:
        kontext.close()
