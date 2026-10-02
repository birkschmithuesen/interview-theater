"""Die vereinte Seite im echten Browser: die vorlaeufige Blase (Karte W).

Was ``tests/test_web_vereint_strom_js.py`` am Quelltext festhaelt, prueft
dieser Lauf im Chromium: die Blase waechst ueber mehr als ein Stueck Text,
eine abgebrochene Antwort verschwindet ersatzlos, eine fertige weicht der
Nachricht mit ihrer ``post_id`` -- und zwei gleichzeitige Zeilen haben zwei
Blasen.

Kein Bot laeuft mit: der Test schreibt die ``web_strom``-Zeilen selbst ueber
``repo`` (``beginne_strom``/``schreibe_strom``/``beende_strom``), so wie es
die Strom-Senke im Bot taete. Alles Material ist frei erfunden.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_vereint_e2e.py -q

Im normalen ``pytest``-Lauf wird die Datei uebersprungen (``importorskip``).
"""

import os
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

pytestmark = pytest.mark.e2e

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo, web_kanal  # noqa: E402

DB_PFAD = "/tmp/it-webvereint.db"
AUDIO = "/tmp/it-webvereint-audio"
SERVERLOG = "/tmp/it-webvereint-server.log"
CHAT = 7_000_000_000_001
HANDY = {"width": 390, "height": 844}
GEDULD = 8000


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


BIND = f"127.0.0.1:{_freier_port()}"
BASIS = f"http://{BIND}"


def _baue_datenbank() -> str:
    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Ankommen, Arbeit, Nacht")
    kanal = web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01)
    kanal.sende(CHAT, "Eure Begriffe habe ich. Womit fangen wir an?")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return token


def _warte_auf_server(prozess, sekunden: float = 15.0) -> None:
    ende = time.time() + sekunden
    while time.time() < ende:
        if prozess.poll() is not None:
            raise RuntimeError(f"Der Webserver ist abgestuerzt, siehe {SERVERLOG}.")
        try:
            with urllib.request.urlopen(f"{BASIS}/gesund", timeout=1) as antwort:
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
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD, "IT_WEB_BIND": BIND, "IT_WEB_PREFIX": "/theatersoap",
        "IT_AUDIO": AUDIO, "PYTHONPATH": str(WURZEL),
    })
    log = open(SERVERLOG, "w")
    prozess = subprocess.Popen(
        [sys.executable, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        _warte_auf_server(prozess)
        yield prozess
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=5)
        except subprocess.TimeoutExpired:
            prozess.kill()
        log.close()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        yield chromium
        chromium.close()


@pytest.fixture
def conn():
    verbindung = db.verbinde(DB_PFAD)
    # Kein Rest aus dem vorigen Test laeuft weiter.
    for zeile in repo.laufende_stroeme(verbindung, CHAT):
        repo.beende_strom(verbindung, zeile["id"], repo.STROM_ABGEBROCHEN)
    yield verbindung
    verbindung.close()


@pytest.fixture
def seite(server, browser, token, conn):
    kontext = browser.new_context(viewport=HANDY, is_mobile=True, has_touch=True)
    blatt = kontext.new_page()
    blatt.set_default_timeout(GEDULD)
    blatt.goto(f"{BASIS}/g/{token}")
    blatt.wait_for_selector("#verlauf")
    yield blatt
    kontext.close()


def _warte(seite, bedingung, ms: int = GEDULD, schritt: int = 100) -> bool:
    ende = time.time() + ms / 1000
    while time.time() < ende:
        if bedingung():
            return True
        seite.wait_for_timeout(schritt)
    return bedingung()


def _blasen(seite) -> list[str]:
    return seite.eval_on_selector_all(
        ".blase.vorlaeufig", "els => els.map(e => e.textContent)")


def _beginne_und_wecke(seite, conn) -> int:
    """Eine laufende Zeile -- und die Tippanzeige, wie der Bot sie setzt:
    das ist der Anlass, bei dem die Ansicht den Strom oeffnet."""
    strom_id = repo.beginne_strom(conn, CHAT, "gespraech")
    web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01).tippt(CHAT)
    return strom_id


def test_die_blase_waechst_und_verschwindet_bei_abbruch(seite, conn):
    strom_id = _beginne_und_wecke(seite, conn)
    repo.schreibe_strom(conn, strom_id, "Das ist")
    assert _warte(seite, lambda: _blasen(seite) == ["Das ist"], ms=40000)
    repo.schreibe_strom(conn, strom_id, "Das ist ein Anfang")
    assert _warte(seite, lambda: _blasen(seite) == ["Das ist ein Anfang"])
    # Kein innerHTML: Markup im Teiltext bleibt Text.
    repo.schreibe_strom(conn, strom_id, "Das ist <b>fett</b>")
    assert _warte(seite, lambda: _blasen(seite) == ["Das ist <b>fett</b>"])
    assert seite.locator(".blase.vorlaeufig b").count() == 0
    repo.beende_strom(conn, strom_id, repo.STROM_ABGEBROCHEN)
    assert _warte(seite, lambda: _blasen(seite) == [])
    # Und sie kommt nicht wieder, auch wenn der Strom neu aufgeht.
    seite.wait_for_timeout(4000)
    assert _blasen(seite) == []


def test_die_fertige_blase_weicht_der_nachricht(seite, conn):
    strom_id = _beginne_und_wecke(seite, conn)
    repo.schreibe_strom(conn, strom_id, "Hier kommt die Antwort")
    assert _warte(seite, lambda: _blasen(seite) == ["Hier kommt die Antwort"], ms=40000)
    kanal = web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01)
    post_id = kanal.sende(CHAT, "Hier kommt die Antwort, fertig.")
    repo.beende_strom(conn, strom_id, repo.STROM_FERTIG, post_id)
    assert _warte(
        seite,
        lambda: seite.locator(f'.blase[data-id="{post_id}"]').count() == 1
        and _blasen(seite) == [],
        ms=15000,
    )


def test_zwei_zeilen_zwei_blasen(seite, conn):
    erste = _beginne_und_wecke(seite, conn)
    zweite = repo.beginne_strom(conn, CHAT, "szene")
    repo.schreibe_strom(conn, erste, "Gespraech")
    repo.schreibe_strom(conn, zweite, "Szene")
    assert _warte(seite, lambda: sorted(_blasen(seite)) == ["Gespraech", "Szene"],
                  ms=40000)
    repo.beende_strom(conn, erste, repo.STROM_ABGEBROCHEN)
    assert _warte(seite, lambda: _blasen(seite) == ["Szene"])
    repo.schreibe_strom(conn, zweite, "Szene waechst")
    assert _warte(seite, lambda: _blasen(seite) == ["Szene waechst"])
    repo.beende_strom(conn, zweite, repo.STROM_ABGEBROCHEN)
    assert _warte(seite, lambda: _blasen(seite) == [])
