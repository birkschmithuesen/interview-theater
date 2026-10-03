"""Der Padua-Stepper im echten Chromium (BINDING ADDITION, Birk 03.10.2026
23:10): sieben nummerierte Segmente statt des zugeklappten ``<details>``,
Pfeile links/rechts der aktiven Phase, ein Tap oeffnet ein Bottom-Sheet
statt der Zwei-Klick-Bewaffnung.

Nur unter ``IT_WORKSHOP=padua-2026`` gerendert (``[web] phasennav_stepper``,
siehe ``tests/test_web_vereint_bitgleich.py`` fuer den Dortmund-Gegenbeweis).

Birks Nachtrag beim Resume dieser Karte: das Sheet muss sich automatisch
schliessen -- nach einem erfolgreichen "Go to ...", nach "Stay here" und bei
einem Tap ausserhalb (auf den abgedunkelten Hintergrund). Alle drei Wege
haben hier eine eigene Pruefung.

Aufruf::

    python3.11 -m pytest tests/e2e/test_web_phasenstepper_e2e.py -q

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

from interview_theater import db, repo  # noqa: E402

DB_PFAD = "/tmp/it-phasenstepper.db"
AUDIO = "/tmp/it-phasenstepper-audio"
SERVERLOG = "/tmp/it-phasenstepper-server.log"
CHAT = 7_000_000_000_901
HANDY = {"width": 390, "height": 844}
GEDULD = 8000


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


BIND = f"127.0.0.1:{_freier_port()}"
BASIS = f"http://{BIND}"


def _baue_datenbank() -> str:
    """Phase 4 aktiv (Phase 1-3 damit 'erledigt', Phase 5-7 'kommend'), mit
    Begriffen/Fragen/Eroeffnung/Abschluss gesetzt (Phase 2/3 bereit), aber
    OHNE Figuren/Geschichte (Phase 4 selbst NICHT bereit) -- drei
    unterschiedliche Bereitschafts-Zustaende in einem Lauf, wie der Task-6-
    Auftrag es verlangt."""
    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Arriving, Work, Night, Suitcase")
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "What was in your suitcase?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_weich", "")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung", "We're from the theatre.")
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Thank you.")
    # Bewusst KEIN rahmen/figur/geschichte: Phase 4 bleibt "nicht bereit",
    # damit test_tap_auf_segment... den OFFEN-Zweig des Sheets ueben kann.
    repo.setze_phase(conn, CHAT, 4)
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
        "IT_DB": DB_PFAD, "IT_WEB_BIND": BIND, "IT_WEB_PREFIX": "",
        "IT_AUDIO": AUDIO, "PYTHONPATH": str(WURZEL),
        "IT_WORKSHOP": "padua-2026",
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
    yield verbindung
    verbindung.close()


@pytest.fixture
def seite(server, browser, token):
    kontext = browser.new_context(viewport=HANDY, is_mobile=True, has_touch=True)
    blatt = kontext.new_page()
    blatt.set_default_timeout(GEDULD)
    blatt.goto(f"{BASIS}/g/{token}")
    blatt.wait_for_selector("#tab-chat:not([hidden])")
    yield blatt
    kontext.close()


def test_stepper_ersetzt_die_zugeklappte_liste(seite):
    """Grundzustand: sieben Segmente, zwei Pfeile, kein zugeklapptes
    ``<details class="roadmap">`` mehr."""
    assert seite.locator(".phasenav").count() == 1
    assert seite.locator(".stepper-segment").count() == 7
    assert seite.locator(".phasenav-zurueck, .phasenav-vor").count() == 2
    assert seite.locator("details.roadmap").count() == 0


def test_tap_auf_segment_oeffnet_sheet_mit_name_und_status(seite):
    """Phase 4 ist in der Fixture absichtlich 'nicht bereit' -- der Sheet
    muss den OFFEN-Zweig zeigen ('Still open: ...'), nicht 'Ready'."""
    seite.click('.stepper-segment[data-phase="4"]')
    seite.wait_for_selector("#phasensheet:not([hidden])")
    assert seite.locator("#phasensheet-titel").inner_text().strip()
    status = seite.locator("#phasensheet-status").inner_text().strip()
    assert status
    assert "Still open" in status


def test_tap_auf_erledigte_phase_zeigt_bereit(seite):
    """Phase 1 (Terms) ist laut Fixture laengst erledigt -- 'Ready', nicht
    'Still open'."""
    seite.click('.stepper-segment[data-phase="1"]')
    seite.wait_for_selector("#phasensheet:not([hidden])")
    status = seite.locator("#phasensheet-status").inner_text().strip()
    assert status == "Ready"


def test_gehe_zu_wechselt_die_phase_per_post_und_schliesst_das_sheet(seite, conn):
    """Birks Nachtrag: nach einem erfolgreichen 'Go to ...' schliesst sich
    das Sheet von selbst -- und der Eingang zeigt den echten POST."""
    vor = len(repo.web_eingang(conn, CHAT, 0))
    seite.click('.stepper-segment[data-phase="1"]')
    seite.wait_for_selector("#phasensheet:not([hidden])")
    seite.click("#phasensheet-los")
    seite.wait_for_selector("#phasensheet", state="hidden")
    assert seite.locator("#phasensheet").is_hidden()
    eingaenge = repo.web_eingang(conn, CHAT, 0)
    assert len(eingaenge) == vor + 1
    assert eingaenge[-1]["text"] == "/phaseklick 1"


def test_hier_bleiben_schliesst_ohne_post(seite, conn):
    vor = len(repo.web_eingang(conn, CHAT, 0))
    seite.click('.stepper-segment[data-phase="4"]')
    seite.wait_for_selector("#phasensheet:not([hidden])")
    seite.click("#phasensheet-bleib")
    seite.wait_for_selector("#phasensheet", state="hidden")
    assert seite.locator("#phasensheet").is_hidden()
    seite.wait_for_timeout(500)
    assert len(repo.web_eingang(conn, CHAT, 0)) == vor


def test_tap_auf_hintergrund_schliesst_ohne_post(seite, conn):
    """Der dritte Schliessweg aus Birks Nachtrag: Tap ausserhalb des
    Sheets (der abgedunkelte Hintergrund)."""
    vor = len(repo.web_eingang(conn, CHAT, 0))
    seite.click('.stepper-segment[data-phase="4"]')
    seite.wait_for_selector("#phasensheet:not([hidden])")
    seite.click(".sheet-hintergrund")
    seite.wait_for_selector("#phasensheet", state="hidden")
    assert seite.locator("#phasensheet").is_hidden()
    seite.wait_for_timeout(500)
    assert len(repo.web_eingang(conn, CHAT, 0)) == vor


def test_pfeile_oeffnen_dasselbe_sheet(seite):
    seite.click(".phasenav-vor")
    seite.wait_for_selector("#phasensheet:not([hidden])")
    assert seite.locator("#phasensheet-titel").inner_text().strip()
    seite.click("#phasensheet-bleib")
    seite.wait_for_selector("#phasensheet", state="hidden")

    seite.click(".phasenav-zurueck")
    seite.wait_for_selector("#phasensheet:not([hidden])")
    assert seite.locator("#phasensheet-titel").inner_text().strip()


def test_tapflaeche_mindestens_44px(seite):
    """Mutationstest eingebaut: eine live per CSSOM verkleinerte Tippflaeche
    muss die Messung selbst als 'zu klein' erkennen -- Beweis, dass der Test
    wirklich die gerenderte Groesse prueft und nicht nur den Quelltext."""
    kasten = seite.locator(".stepper-segment").first.bounding_box()
    assert kasten["width"] >= 44 and kasten["height"] >= 44, kasten

    seite.evaluate(
        "document.querySelectorAll('.stepper-segment').forEach(function (el) {"
        "  el.style.setProperty('min-width', '24px');"
        "  el.style.setProperty('min-height', '24px');"
        "  el.style.setProperty('flex', '0 0 24px');"
        "})"
    )
    kasten_klein = seite.locator(".stepper-segment").first.bounding_box()
    ist_gross_genug = kasten_klein["width"] >= 44 and kasten_klein["height"] >= 44
    assert not ist_gross_genug, kasten_klein


def test_kein_zwei_klick_data_sicher_im_padua_markup(seite):
    """Die alte Zwei-Klick-Bewaffnung (``_leiste_html``s ``.phase-knopf
    [data-sicher]``) darf im Stepper gar nicht existieren -- geprueft ueber
    den spezifischen Selektor, nicht ueber eine blosse Textsuche: ein davon
    unabhaengiges Element (``#meldungen``) traegt ebenfalls ein Attribut
    namens ``data-sicher`` fuer eine andere Sache (Nachrichten-Sicherheit)
    und wuerde eine blosse ``'data-sicher' in html``-Suche falsch melden."""
    assert seite.locator(".phase-knopf").count() == 0
    assert seite.locator(".phase-knopf[data-sicher]").count() == 0


def test_stepper_hinweis_erscheint_einmalig(seite):
    """Erster Besuch: der Hinweis 'Tap a phase to move between steps.'
    erscheint. Nach einem Tap verschwindet er und bleibt (ueber localStorage)
    auch beim naechsten Laden weg."""
    hinweis = seite.locator("#stepper-hinweis")
    assert hinweis.count() == 1
    assert hinweis.is_visible()
    seite.click('.stepper-segment[data-phase="4"]')
    seite.wait_for_selector("#phasensheet:not([hidden])")
    assert hinweis.is_hidden()
    seite.click("#phasensheet-bleib")

    seite.reload()
    seite.wait_for_selector("#tab-chat:not([hidden])")
    assert seite.locator("#stepper-hinweis").is_hidden()
