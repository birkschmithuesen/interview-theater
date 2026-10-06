"""Best-effort-Screenshot des Regie-Tickers im echten Browser (Addendum 3,
Karte t_a0d171ab, 06.10.2026).

Der eigentliche Nachweis des Markups steht schon ohne Browser in
``tests/test_web_ticker.py`` -- dies ist nur der im Addendum ausdruecklich
verlangte Bildschirmschuss: ein echter Webserver-Prozess (kein Bot-Thread),
eine Demo-``IT_WEB_TICKER_DATEI`` mit zwei Eintraegen -- dem neuesten MIT
einer ⚠-Zeile im Technik-Teil (Ampel gelb) und einem aelteren OHNE (Ampel
gruen, eingeklappt) -- und die Ticker-Route im Browser, 390x844-Viewport.

Im normalen ``pytest``-Lauf wird die Datei uebersprungen, wenn Playwright
fehlt (``importorskip``, wie beim Vorbild). Der Schuss selbst wird nur bei
``IT_SCHUSS_AKTUALISIEREN=1`` ins Repository kopiert -- sonst bleibt der
Arbeitsbaum nach einem normalen Lauf sauber (dasselbe Muster wie
``tests/e2e/test_web_cothinker_status_screenshot_e2e.py``)."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo  # noqa: E402

DB_PFAD = "/tmp/it-ticker-schuss.db"
AUDIO = "/tmp/it-ticker-schuss-audio"
SERVERLOG = "/tmp/it-ticker-schuss-server.log"
TICKER_DATEI = Path("/tmp/it-ticker-schuss-eintraege.jsonl")

SCHUSS = WURZEL / "docs" / "web-ticker-addendum3-2026-10-06.png"
SCHUSS_TMP = Path("/tmp/it-ticker-schuss/ticker.png")

HANDY = {"width": 390, "height": 844}
DASHBOARD_TOKEN = "schuss-dashboard-token-xyz"


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _iso(vor_minuten: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=vor_minuten)).isoformat()


def _baue_demo_jsonl() -> None:
    TICKER_DATEI.write_text(
        json.dumps({
            "zeit": _iso(12),
            "text": "G1: ruhig in Phase Fragen",
            "inhalt": "• G1: ruhig, sammelt weiter Fragen zu Zuhause\n"
                      "• G2: Konflikt um den Begriff »Freiheit«\n"
                      "• G3: entwickelt fiktive Schlagzeilen fuers Interview",
            "technik": "✓ Technik unauffällig\n• Autodeploy: live e5d55aef\n• Platz: 7.9 GB frei",
        }) + "\n"
        + json.dumps({
            "zeit": _iso(1),
            "text": "G2: haengende Aufnahme",
            "inhalt": "• G1: Eroeffnungs- und Schlusstext stehen\n"
                      "• G2: eine Stimme dominiert das Gespraech\n"
                      "• 🎬 Regie: G2 hat einen starken Begriff, aber noch keine Frage dazu",
            "technik": "⚠ Verdacht: G2 Aufnahme haengt seit 7 min (Status empfangen, Versuche 1)\n"
                       "• G1: P2 Fragen, aktiv vor 2 min, 1 Aufn. im Fenster\n"
                       "• G2: P3 Interviews, aktiv vor 1 min, 2 Aufn. im Fenster\n"
                       "• unklar, ob der Recorder haengt oder nur niemand spricht",
        }) + "\n",
        encoding="utf-8",
    )


def _baue_datenbank() -> None:
    Path(DB_PFAD).unlink(missing_ok=True)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 7_000_000_000_098, "schussbot", "Schussgruppe")
    conn.commit()
    conn.close()


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


def test_ticker_screenshot():
    """Best effort: schreibt den Schuss nur bei ``IT_SCHUSS_AKTUALISIEREN=1``
    ins Repository. Ein uebersprungener oder fehlender Schuss ist kein
    Grund, die Karte als blockiert zu melden."""
    _baue_datenbank()
    _baue_demo_jsonl()
    bind = f"127.0.0.1:{_freier_port()}"
    basis = f"http://{bind}"
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD, "IT_WEB_BIND": bind, "IT_WEB_PREFIX": "",
        "IT_AUDIO": AUDIO, "PYTHONPATH": str(WURZEL),
        "IT_WEB_DASHBOARD_TOKEN": DASHBOARD_TOKEN,
        "IT_WEB_TICKER_DATEI": str(TICKER_DATEI),
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
                seite.goto(f"{basis}/dashboard/{DASHBOARD_TOKEN}/ticker")
                seite.wait_for_selector(".ticker-liste", state="attached")
                seite.wait_for_timeout(300)
                SCHUSS_TMP.parent.mkdir(parents=True, exist_ok=True)
                seite.screenshot(path=str(SCHUSS_TMP), full_page=True)
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
