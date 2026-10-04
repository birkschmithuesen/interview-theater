"""Best-effort-Screenshot der CoThinker-Statuszeile im echten Browser
(Task 5, Karte 2026-10-03-cothinker-statuszeile).

Der eigentliche Nachweis der Zustandswechsel steht bereits ohne Browser in
``tests/test_web_vereint_cothinker_status.py`` (siehe Begruendung dort).
Diese Datei ist nur der optionale, im Taskbrief ausdruecklich als
"best effort" erlaubte Bildschirmschuss: eine Gruppe in Phase 4 mit einem
laufenden Buehnenkarten-Lauf ("denkt"), ein echter Webserver-Prozess (ohne
Bot-Thread -- es wird nichts geklickt, nur eine Statuszeile betrachtet,
anders als ``tests/e2e/test_web_chat_e2e.py``), die vereinte Gruppenseite
im CoThinker-Tab, 390x844-Viewport.

Im normalen ``pytest``-Lauf wird die Datei uebersprungen, wenn Playwright
fehlt (``importorskip``, wie beim Vorbild). Der Schuss selbst wird nur bei
``IT_SCHUSS_AKTUALISIEREN=1`` ins Repository kopiert -- sonst bleibt der
Arbeitsbaum nach einem normalen Lauf sauber (exakt das Muster aus
``tests/e2e/test_web_chat_e2e.py::test_handy_screenshot``)."""

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
from playwright.sync_api import sync_playwright  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo  # noqa: E402

DB_PFAD = "/tmp/it-cothinker-schuss.db"
AUDIO = "/tmp/it-cothinker-schuss-audio"
SERVERLOG = "/tmp/it-cothinker-schuss-server.log"
CHAT = 7_000_000_000_099

SCHUSS = WURZEL / "docs" / "web-cothinker-status-2026-10-03.png"
SCHUSS_TMP = Path("/tmp/it-cothinker-schuss/co-status.png")

HANDY = {"width": 390, "height": 844}


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _baue_datenbank() -> str:
    Path(DB_PFAD).unlink(missing_ok=True)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "schussbot", "Schussgruppe")
    repo.setze_phase(conn, CHAT, 4)
    repo.markiere_buehnenkarten_lauf(conn, CHAT, repo._jetzt())
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


def test_cothinker_statuszeile_screenshot():
    """Best effort: schreibt den Schuss nur bei ``IT_SCHUSS_AKTUALISIEREN=1``
    ins Repository. Ein uebersprungener oder fehlender Schuss ist laut
    Taskbrief ausdruecklich kein Grund, die Karte als blockiert zu melden."""
    token = _baue_datenbank()
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
        with sync_playwright() as p:
            chromium = p.chromium.launch()
            try:
                kontext = chromium.new_context(viewport=HANDY, is_mobile=True)
                seite = kontext.new_page()
                seite.set_default_timeout(8000)
                seite.goto(f"{basis}/g/{token}#buehne")
                seite.wait_for_selector("#cothinker-status", state="attached")
                seite.wait_for_timeout(300)
                SCHUSS_TMP.parent.mkdir(parents=True, exist_ok=True)
                seite.screenshot(path=str(SCHUSS_TMP), full_page=False)
                assert SCHUSS_TMP.stat().st_size > 1000
                if os.environ.get("IT_SCHUSS_AKTUALISIEREN") == "1":
                    SCHUSS.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(SCHUSS_TMP, SCHUSS)
                kontext.close()
            finally:
                chromium.close()
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=5)
        except subprocess.TimeoutExpired:
            prozess.kill()
        log.close()
