"""Bild-Overlay-Karte (04.10.2026, t_abc12cf7, Task 2): die Telefon-
Organisationskarte (``.karte``) laesst sich im echten Browser antippen und
oeffnet sich vollbildig; der Record-Knopf (``#interview``) bleibt in
CSS-Pixeln gleich gross, unabhaengig vom Device-Pixel-Ratio.

Was ``tests/test_web_chat_bildoverlay.py`` nicht leistet: ob ein echtes
``<img>`` im Overlay wirklich laedt (``naturalWidth``/``naturalHeight``)
und ob Antippen/Schliessen im DOM tatsaechlich wirken.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo  # noqa: E402

DB_PFAD = "/tmp/it-bildzoom.db"
AUDIO = "/tmp/it-bildzoom-audio"
SERVERLOG = "/tmp/it-bildzoom-server.log"
CHAT = 7_000_000_000_051

HANDY = {"width": 390, "height": 844}

SCHUSS_VERZEICHNIS = WURZEL / "docs" / "ux-padua" / "chat-zoom"


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _baue_datenbank() -> str:
    for endung in ("", "-wal", "-shm"):
        pfad = DB_PFAD + endung
        if os.path.exists(pfad):
            os.remove(pfad)
    shutil.rmtree(AUDIO, ignore_errors=True)

    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "schussbot", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 3)
    repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_SYSTEM,
        text="Eins hoert zu, eins steht aufgestellt.", bild="phase-3.png",
    )
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.close()
    return token


def _warte_auf_server(prozess, basis: str, sekunden: float = 15.0) -> None:
    ende = time.time() + sekunden
    while time.time() < ende:
        if prozess.poll() is not None:
            raise RuntimeError(f"Der Webserver ist abgestuerzt, siehe {SERVERLOG}.")
        try:
            with urllib.request.urlopen(f"{basis}/gesund", timeout=1) as antwort:
                if antwort.read().decode().strip() == "ok":
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError("Der Webserver ist nicht hochgekommen.")


@pytest.fixture(scope="module")
def token() -> str:
    return _baue_datenbank()


@pytest.fixture(scope="module")
def server(token):
    bind = f"127.0.0.1:{_freier_port()}"
    basis = f"http://{bind}"
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD, "IT_WEB_BIND": bind, "IT_WEB_PREFIX": "",
        "IT_AUDIO": AUDIO, "PYTHONPATH": str(WURZEL),
    })
    log = open(SERVERLOG, "w")
    prozess = subprocess.Popen(
        [sys.executable, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        _warte_auf_server(prozess, basis)
        yield basis
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=5)
        except subprocess.TimeoutExpired:
            prozess.kill()
        log.close()


def test_bild_antippen_oeffnet_das_overlay_in_natuerlicher_aufloesung(server, token):
    basis = server
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            kontext = chromium.new_context(viewport=HANDY, is_mobile=True)
            seite = kontext.new_page()
            seite.set_default_timeout(8000)
            seite.goto(f"{basis}/g/{token}")
            karte = seite.locator("img.karte").first
            expect(karte).to_be_visible()

            SCHUSS_VERZEICHNIS.mkdir(parents=True, exist_ok=True)
            seite.screenshot(
                path=str(SCHUSS_VERZEICHNIS / "bild-vorher.png"), full_page=False,
            )

            overlay = seite.locator("#bild-overlay")
            assert overlay.is_hidden()
            karte.click()
            expect(overlay).to_be_visible()

            overlay_bild = seite.locator("#bild-overlay-img")
            expect(overlay_bild).to_have_js_property("complete", True)
            natuerliche_breite = overlay_bild.evaluate("el => el.naturalWidth")
            natuerliche_hoehe = overlay_bild.evaluate("el => el.naturalHeight")
            assert natuerliche_breite > 0
            assert natuerliche_hoehe > 0
            karten_quelle = karte.evaluate("el => el.src")
            overlay_quelle = overlay_bild.evaluate("el => el.src")
            assert overlay_quelle == karten_quelle

            seite.screenshot(
                path=str(SCHUSS_VERZEICHNIS / "bild-overlay-offen.png"),
                full_page=False,
            )

            # Schliessen per Knopf.
            seite.click("#bild-overlay-schliessen")
            expect(overlay).to_be_hidden()

            # Erneut oeffnen, diesmal per Klick auf den Hintergrund schliessen.
            karte.click()
            expect(overlay).to_be_visible()
            overlay.click(position={"x": 5, "y": 5})
            expect(overlay).to_be_hidden()

            kontext.close()
        finally:
            chromium.close()


def test_der_record_knopf_bleibt_in_css_pixeln_gleich_gross_ueber_dpr(server, token):
    basis = server
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            groessen = {}
            for dpr in (2, 3):
                kontext = chromium.new_context(
                    viewport=HANDY, is_mobile=True, device_scale_factor=dpr,
                )
                seite = kontext.new_page()
                seite.set_default_timeout(8000)
                seite.goto(f"{basis}/g/{token}")
                knopf = seite.locator("#interview")
                expect(knopf).to_be_visible()
                box = knopf.bounding_box()
                groessen[dpr] = (round(box["width"], 1), round(box["height"], 1))
                kontext.close()

            assert groessen[2] == groessen[3], (
                f"Record-Knopf aendert seine CSS-Pixel-Groesse mit dem "
                f"Device-Pixel-Ratio: {groessen}"
            )
        finally:
            chromium.close()
