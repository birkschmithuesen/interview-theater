"""Die Auswahlliste im CoThinker (Padua Phase 2, 05.10.2026) im echten
Browser auf Handygroesse (390x844): ein Tipp auf ✗ setzt die Zeile sofort,
der Zaehler zieht mit, die Entscheidung steht danach in der Datenbank; ein
zweiter Tipp nimmt sie zurueck; "Fertig sortiert" legt ``/sortiert`` in den
Eingang und schaltet auf den Chat. Ohne Playwright uebersprungen. Der
Handy-Schuss landet unter /tmp. Nur erfundenes Material."""

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

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo  # noqa: E402

DB_PFAD = "/tmp/it-auswahl-e2e.db"
AUDIO = "/tmp/it-auswahl-e2e-audio"
SERVERLOG = "/tmp/it-auswahl-e2e-server.log"
CHAT = 7_000_000_000_141
HANDY = {"width": 390, "height": 844}
SCHUSS_TMP = Path("/tmp/it-auswahl-e2e/auswahl.png")
GEDULD_MS = 30_000
FRAGEN = [
    "Casa: Che cosa vuol dire per te tornare a casa dopo un lungo viaggio?",
    "Casa: Chi abita con te?",
    "Mare: Che cosa porta il mare?",
    "Una domanda senza termine",
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
    repo.sichere_gruppe(conn, CHAT, "auswahlbot", "Auswahlgruppe")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 2)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Casa\nMare")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_auswahl", "\n".join(FRAGEN))
    repo.setze_arbeitsstand(conn, CHAT, "fragen_herkunft", "eigen,ki,ki,eigen")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_entschieden", "ja,,,")
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


def _stand():
    conn = db.verbinde(DB_PFAD)
    try:
        zeile = repo.hole_arbeitsstand(conn, CHAT)
        eingang = [(z["typ"], z["text"]) for z in repo.web_eingang(conn, CHAT, 0)]
        return zeile["fragen_entschieden"], eingang
    finally:
        conn.close()


def test_ein_tipp_sortiert_und_fertig_geht_zum_chat(server):
    basis, token = server
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            kontext = chromium.new_context(viewport=HANDY, is_mobile=True, has_touch=True)
            seite = kontext.new_page()
            seite.set_default_timeout(GEDULD_MS)
            seite.goto(f"{basis}/g/{token}#buehne")
            zeile = seite.locator('#tab-buehne li[data-nummer="2"]')
            zeile.wait_for(state="visible")
            zaehler = seite.locator("#tab-buehne .auswahl-zaehler")
            vorher = zaehler.inner_text()

            # Handytauglich: kein waagerechtes Scrollen, Knoepfe >= 44px.
            breite = seite.evaluate("document.documentElement.scrollWidth")
            assert breite <= HANDY["width"], breite
            for knopf in zeile.locator(".auswahl-knopf").all():
                kasten = knopf.bounding_box()
                assert kasten["height"] >= 44 and kasten["width"] >= 44, kasten

            zeile.locator('.auswahl-knopf[data-wert="nein"]').click()
            assert zeile.get_attribute("data-zustand") == "nein"
            assert zeile.locator('.auswahl-knopf[data-wert="nein"]').get_attribute(
                "aria-pressed") == "true"
            assert zaehler.inner_text() != vorher
            ende = time.time() + 10
            while _stand()[0] != "ja,nein,," and time.time() < ende:
                time.sleep(0.1)
            assert _stand()[0] == "ja,nein,,"
            stil = zeile.locator(".auswahl-text").evaluate(
                "el => getComputedStyle(el).textDecorationLine")
            assert "line-through" in stil

            SCHUSS_TMP.parent.mkdir(parents=True, exist_ok=True)
            seite.screenshot(path=str(SCHUSS_TMP), full_page=True)

            # Rueckgaengig: derselbe Knopf noch einmal.
            zeile.locator('.auswahl-knopf[data-wert="nein"]').click()
            ende = time.time() + 10
            while _stand()[0] != "ja,,," and time.time() < ende:
                time.sleep(0.1)
            assert _stand()[0] == "ja,,,"
            seite.wait_for_function(
                "() => document.querySelector('#tab-buehne li[data-nummer=\"2\"]')"
                ".getAttribute('data-zustand') === 'offen'")
            assert zaehler.inner_text() == vorher

            seite.locator("#tab-buehne .auswahl-fertig").click()
            seite.wait_for_function("() => location.hash.indexOf('chat') >= 0")
            assert seite.locator("#tab-chat").is_visible()
            ende = time.time() + 10
            sortiert = (repo.WEB_TYP_BEFEHL, "/sortiert")
            while sortiert not in _stand()[1] and time.time() < ende:
                time.sleep(0.1)
            # ``/start`` legt der erste Seitenaufruf selbst an (start_post).
            assert [e for e in _stand()[1] if e[1] != "/start"] == [sortiert]
            kontext.close()
        finally:
            chromium.close()
