"""Brainstorm ohne VAD schickt trotzdem 'ende' (Padua P34 Task 1, Muster
``5532c95``) -- im echten Browser.

Ohne Pegelmesser (kein AudioContext, z. B. ein altes Mobilgeraet oder ein
Browser ohne WebAudio) blieb ``sitzung.vadAktiv`` leer; ``beendeBrainstorm``/
``pausiereBrainstorm`` setzten ``grund 'ende'`` bisher nur mit aktiver VAD --
das letzte Segment ging dann ohne 'ende' hoch, der Server lief nie mit
``ist_abschluss`` (keine CoThinker-Karte). Jetzt immer.

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

from interview_theater import db, repo, web, workshop  # noqa: E402

CHAT = 7_000_000_000_006   # eigene chat_id
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
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token
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
    basis, token = lauf
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
        seite.click("#brainstorm")
        seite.wait_for_selector('#brainstorm[data-laeuft="1"]')
        seite.wait_for_timeout(2000)
        seite.click("#brainstorm-beenden")        # ab Task 5: seite.click("#brainstorm")
        seite.wait_for_selector('#brainstorm[data-laeuft="0"]')
        seite.wait_for_timeout(1500)
        ende = [u for u in uploads if "grund=ende" in u]
        assert len(ende) == 1, uploads
        assert "brainstorm=1" in ende[0], uploads
    finally:
        kontext.close()
