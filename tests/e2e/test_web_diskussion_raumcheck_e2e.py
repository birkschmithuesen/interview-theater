"""Erst der Raumcheck, dann die Diskussion (Padua Phase 1, Birk 05.10.2026
13:10) -- im echten Browser, mit eingeschalteter Kalibrierung.

Ein Tipp auf "Start listening": die Stillemessung laeuft ohne zweiten Knopf;
waehrend der Kalibrierung geht kein Diskussionssegment hoch und die Uhr der
Diskussion steht; nach Skip beginnt die Aufnahme, die Uhr bei 0.

Webserver im Thread (wie ``test_web_diskussion_e2e.py``), keine Bot-Schleife
-- gezaehlt werden die Uploads (``chat/audio``) direkt im Browser.
``_MESSUNG`` aus ``test_web_chat_e2e`` liefert den gefaelschten Pegel, wie in
``test_web_chat_kalibrierung_e2e.py``.

Aufruf::

    env -i HOME=/home/birk PATH=/usr/bin:/bin \\
        /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest -q \\
        -p no:cacheprovider -m 'not dortmund' tests/e2e/test_web_diskussion_raumcheck_e2e.py
"""

import re
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
from tests.e2e.test_web_chat_e2e import _MESSUNG  # noqa: E402

CHAT = 7_000_000_000_004   # eigene chat_id
SCHLUESSEL = b"z" * 32
HANDY = {"width": 390, "height": 844}
GEDULD_MS = 15000


@pytest.fixture
def lauf(tmp_path, monkeypatch):
    workshop.vergiss()
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")
    monkeypatch.setenv("IT_AUDIO", str(tmp_path / "audio"))
    # IT_WEB_VAD_KALIBRIERUNG bleibt auf der Vorgabe (an) -- darum geht es hier.
    monkeypatch.delenv("IT_WEB_VAD_KALIBRIERUNG", raising=False)
    pfad = str(tmp_path / "t.db")
    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    repo.sichere_gruppe(aufbau, CHAT, "gruppe-raumcheck", "Die Messenden")
    repo.setze_gruppe_kanal(aufbau, CHAT, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT)
    repo.setze_phase(aufbau, CHAT, 1)
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


def test_raumcheck_zuerst_dann_diskussion_ab_null(lauf, browser):
    basis, token = lauf
    kontext = browser.new_context(
        viewport=HANDY, permissions=["microphone"], base_url=basis,
        is_mobile=True, has_touch=True,
    )
    kontext.add_init_script(_MESSUNG)
    kontext.add_init_script("try { localStorage.clear(); } catch (e) {}")
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD_MS)
    uploads = []   # URL je chat/audio-Upload (Probe: "kalibrierung=1")
    seite.on("request", lambda r: uploads.append(r.url) if "chat/audio" in r.url else None)
    try:
        seite.goto(f"{basis}/g/{token}/chat")
        seite.evaluate("window.__t.setzeRms(0.0)")   # Stille fuer die Messung

        # Ein Tipp -- die Stillemessung laeuft ohne "Start measuring".
        seite.click("#diskussion")
        seite.wait_for_selector('#diskussion[data-laeuft="1"]')
        seite.wait_for_selector("#kalibrierung", state="visible")
        assert seite.is_hidden("#kalibrierung-start"), "kein zweiter Start-Knopf"
        assert seite.is_hidden("#kalibrierung-sprechen")
        stille_text = seite.text_content("#kalibrierung-text")

        # Die Uhr der Diskussion steht waehrend der Kalibrierung bei 0.
        seite.wait_for_timeout(2500)
        assert "(0:00)" in seite.text_content("#diskussion")
        assert seite.is_hidden("#uhr")
        assert seite.text_content("#kalibrierung-text") != stille_text, (
            "der Stille-Countdown laeuft von selbst"
        )

        # Weiter zur Sprechprobe: das Stueck davor geht NICHT als Diskussion hoch.
        seite.wait_for_selector("#kalibrierung-sprechen", state="visible", timeout=8000)
        seite.click("#kalibrierung-sprechen")
        seite.wait_for_timeout(1500)
        assert "(0:00)" in seite.text_content("#diskussion")
        assert [u for u in uploads if "kalibrierung=1" not in u] == [], uploads

        # Skip: jetzt erst beginnt die Diskussion, die Uhr bei 0.
        seite.click("#kalibrierung-skip")
        assert seite.is_hidden("#kalibrierung")
        seite.wait_for_selector("#uhr", state="visible")
        assert re.search(r"0:0[01]$", seite.text_content("#uhr").strip())
        seite.evaluate("window.__t.setzeRms(0.6)")
        seite.wait_for_timeout(2500)
        assert re.search(r"0:0[234]$", seite.text_content("#uhr").strip())
        # Der Rest der Sprechprobe ging nie hoch, auch nicht beim Skip.
        assert [u for u in uploads if "kalibrierung=1" not in u] == [], uploads

        # Die Diskussionsaufnahme laeuft: "Fertig" schickt ihr Segment.
        seite.click("#diskussion-beenden")
        seite.wait_for_selector('#diskussion[data-laeuft="0"]')
        seite.wait_for_timeout(1500)
        diskussion = [u for u in uploads if "kalibrierung=1" not in u]
        assert len(diskussion) == 1, uploads
        assert "grund=ende" in diskussion[0], uploads
    finally:
        kontext.close()


def test_fertig_mitten_im_raumcheck_schickt_das_ende(lauf, browser):
    """Simulation 05.10.2026 13:43: "Discussion done" waehrend der
    Kalibrierung schickte gar nichts -- der Server erfuhr nie vom Ende, kein
    Boardlauf, keine Bot-Nachricht. Jetzt geht ein Ende-Segment
    (``grund=ende``, ``diskussion=1``) hoch; ist es leer, laeuft serverseitig
    ``_abschluss_trotz_verworfenem_ende`` (a852d59)."""
    basis, token = lauf
    kontext = browser.new_context(
        viewport=HANDY, permissions=["microphone"], base_url=basis,
        is_mobile=True, has_touch=True,
    )
    kontext.add_init_script(_MESSUNG)
    kontext.add_init_script("try { localStorage.clear(); } catch (e) {}")
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD_MS)
    uploads = []
    antworten = []
    seite.on("request", lambda r: uploads.append(r.url) if "chat/audio" in r.url else None)
    seite.on("response", lambda r: antworten.append(r.status) if "chat/audio" in r.url else None)
    try:
        seite.goto(f"{basis}/g/{token}/chat")
        seite.evaluate("window.__t.setzeRms(0.0)")
        seite.click("#diskussion")
        seite.wait_for_selector("#kalibrierung", state="visible")
        seite.wait_for_timeout(1000)   # mitten in der Stillemessung

        seite.click("#diskussion-beenden")
        seite.wait_for_selector('#diskussion[data-laeuft="0"]')
        seite.wait_for_timeout(2000)
        assert seite.is_hidden("#kalibrierung")
        ende = [u for u in uploads if "grund=ende" in u]
        assert len(ende) == 1, uploads
        assert "diskussion=1" in ende[0] and "kalibrierung=1" not in ende[0], uploads
        assert antworten and all(s < 300 for s in antworten), antworten
    finally:
        kontext.close()
