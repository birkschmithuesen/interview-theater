"""Karte t_cb2c4678, Design-Erweiterung (04.10.2026): der "Nachher"-Beleg
der visuellen Gestaltung -- ein Board mit allen drei neuen Zustaenden auf
einmal (Scheinwerfer-Marke 1-5, Trennlinie zum Rest, kursives
``verworfen``, Schaerfungs-Steg). Gegenstueck zum "Vorher"-Beleg
``docs/web-begriffsboard/ranking-2026-10-04.png`` (aus Aufgabe 6 der
Karte, VOR dieser Design-Erweiterung erzeugt -- siehe
``docs/superpowers/plans/2026-10-04-padua-begriffsboard-design.md``).

Ohne Playwright wird die Datei uebersprungen (``importorskip``). Der
Handy-Schuss landet immer unter /tmp und nur mit
``IT_SCHUSS_AKTUALISIEREN=1`` im Repository (Muster wie
``tests/e2e/test_web_begriffsboard_ranking_e2e.py``). Nur erfundenes
Material."""

import json
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

DB_PFAD = "/tmp/it-bb-design.db"
AUDIO = "/tmp/it-bb-design-audio"
SERVERLOG = "/tmp/it-bb-design-server.log"
CHAT = 7_000_000_000_102
HANDY = {"width": 390, "height": 844}
SCHUSS = WURZEL / "docs" / "web-begriffsboard" / "design-2026-10-04.png"
SCHUSS_TMP = Path("/tmp/it-bb-design/design-2026-10-04.png")
GEDULD_MS = 30_000


def _e(begriff, status, zustimmung, nennungen, begruendung, vorgaenger=None):
    eintrag = {"begriff": begriff, "nennungen": nennungen, "zustimmung": zustimmung,
               "begruendung": begruendung, "zitat": "", "doppelbedeutung": "",
               "status": status}
    if vorgaenger:
        eintrag["vorgaenger"] = vorgaenger
    return eintrag


BOARD = [
    _e("Heimat", "favorit", 2, 5, "Alle wollen ueber Zuhause reden."),
    _e("Grenze", "favorit", 2, 3, "Eine Grenze kann auch im Kopf sein."),
    _e("Familie", "kandidat", 1, 4, "Wer gehoert dazu, wer nicht."),
    _e("Streit", "kandidat", 1, 2, "Ein Streit, der nie ausgesprochen wurde."),
    _e("Musik", "kandidat", 0, 3,
       "Zuerst als 'Lieder' genannt, spaeter geschaerft auf 'Musik'.", ["Lieder"]),
    _e("Zukunft", "kandidat", 0, 1, "Noch unklar, ob das traegt."),
    _e("Partyszene", "verworfen", -1, 1, "Kam nur einmal vor, dann nie wieder."),
]


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _baue_datenbank() -> str:
    for endung in ("", "-wal", "-shm"):
        Path(DB_PFAD + endung).unlink(missing_ok=True)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "designbot", "Designgruppe")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 1)
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(BOARD), "sovereign", 0)
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


@pytest.fixture
def server():
    token = _baue_datenbank()
    bind = f"127.0.0.1:{_freier_port()}"
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD, "IT_WEB_BIND": bind, "IT_WEB_PREFIX": "", "IT_AUDIO": AUDIO,
        "IT_WORKSHOP": "padua-2026", "PYTHONPATH": str(WURZEL),
    })
    log = open(SERVERLOG, "w")
    prozess = subprocess.Popen(
        [sys.executable, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        basis = f"http://{bind}"
        _warte_auf_server(prozess, basis)
        yield basis, token
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=5)
        except subprocess.TimeoutExpired:
            prozess.kill()
        log.close()


def test_kuratiertes_board_zeigt_rang_trennlinie_verworfen_und_schaerfung(server):
    basis, token = server
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            kontext = chromium.new_context(viewport=HANDY, is_mobile=True)
            seite = kontext.new_page()
            seite.set_default_timeout(GEDULD_MS)
            seite.goto(f"{basis}/g/{token}#buehne")
            seite.wait_for_selector('#tab-buehne li[data-begriff="Partyszene"]', state="visible")

            reihenfolge = seite.eval_on_selector_all(
                "#tab-buehne ol.begriffsboard > li", "els => els.map(e => e.dataset.begriff)")
            assert reihenfolge == [
                "Heimat", "Grenze", "Familie", "Streit", "Musik", "Zukunft", "Partyszene",
            ]
            assert seite.locator('#tab-buehne li[data-top="1"]').count() == 5
            assert seite.locator('#tab-buehne li[data-status="verworfen"]').count() == 1
            assert seite.locator("#tab-buehne details").count() == 0
            assert seite.locator(
                '#tab-buehne li[data-begriff="Musik"] .vorgaenger del').inner_text() == "Lieder"

            # Die Trennlinie liegt an der Scheinwerfer-Grenze, nicht an
            # einer festen Position: Rang-Zeile ohne oberen Rand, erste
            # Rest-Zeile mit einem.
            musik_rand = seite.locator('#tab-buehne li[data-begriff="Musik"]').evaluate(
                "el => getComputedStyle(el).borderTopWidth")
            zukunft_rand = seite.locator('#tab-buehne li[data-begriff="Zukunft"]').evaluate(
                "el => getComputedStyle(el).borderTopWidth")
            assert musik_rand == "0px"
            assert zukunft_rand != "0px"

            # Verworfen ist kursiv, nicht durchgestrichen -- das Zeichen
            # bleibt der Schaerfungskette vorbehalten.
            verworfen_stil = seite.locator(
                '#tab-buehne li[data-status="verworfen"] .begriff').evaluate(
                "el => getComputedStyle(el).fontStyle")
            assert verworfen_stil == "italic"

            SCHUSS_TMP.parent.mkdir(parents=True, exist_ok=True)
            seite.screenshot(path=str(SCHUSS_TMP), full_page=False)
            assert SCHUSS_TMP.stat().st_size > 1000
            if os.environ.get("IT_SCHUSS_AKTUALISIEREN") == "1":
                SCHUSS.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(SCHUSS_TMP, SCHUSS)
            kontext.close()
        finally:
            chromium.close()
