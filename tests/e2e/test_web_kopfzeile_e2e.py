"""Die schlanke Kopfzeile im echten Chromium (Padua-UX-Kopfzeilen-Karte,
03.10.2026, Birk-Befund live am Handy: "Workbench und Chat werden von Next
up ueberdeckt", "Act and Phase doppeln sich").

Baseline-Screenshot vor dieser Karte: ``docs/ux-padua/kopfzeile/vorher/
stand-handy.png`` -- zeigt "Akt 4/7" direkt neben "Phase 4/7 · ..." in
einer Zeile und einen Streifen verstuemmelten/abgeschnittenen Texts knapp
ueber der Tableiste (das negative Margin von ``#ux-naechstes``, als es noch
ein eigenstaendiges Flex-Geschwister von ``#roadmap`` war).

Drei Pruefungen, ohne Browser nicht messbar (echtes Layout, echte
Bounding-Boxen):

1. Der Kopfbereich (Roadmap-Zusammenfassung + Tableiste) ueberlappt auf
   KEINEM Tab und KEINER der beiden Groessen (Handy, Laptop) das erste
   sichtbare Inhaltselement des Panels darunter.
2. Kopf + Tableiste zusammen passen am Handy in <= 96px -- derselbe
   Massstab wie die uebrige App-Shell.
3. Im Kopfbereich steht kein sichtbares "Act"/"Akt" mehr -- nur noch
   "Phase N/7 · Name" und "Next up: ...".

**Nur erfundenes Material**, nie ``betrieb/``. Eigene ``DB_PFAD``/``BIND``/
``CHAT``, um mit anderen e2e-Dateien im selben Lauf nicht zu kollidieren.

Aufruf::

    python3.11 -m pytest tests/e2e/test_web_kopfzeile_e2e.py -q

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

DB_PFAD = "/tmp/it-kopfzeile.db"
AUDIO = "/tmp/it-kopfzeile-audio"
SERVERLOG = "/tmp/it-kopfzeile-server.log"
#: Eigene chat_id, damit dieser Lauf keiner anderen e2e-Datei in die Quere
#: kommt, falls mehrere Dateien im selben Prozess/derselben Session laufen.
CHAT = 7_000_000_000_601

HANDY = {"width": 390, "height": 844}
LAPTOP = {"width": 1366, "height": 900}
#: Die vier Tabs einer Phase-4-Gruppe -- in der Reihenfolge der Tableiste
#: (``web_vereint.TABS`` + ``buehne``).
TABS = ("chat", "stand", "textbuch", "buehne")


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
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Ankommen, Arbeit, Nacht, Koffer")
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "Was war in deinem Koffer?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_weich", "")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung", "Wir sind vom Theater.")
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Vielen Dank.")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhofshalle, spaet nachts, Winter")
    repo.setze_arbeitsstand(
        conn, CHAT, "geschichte",
        "Zwei kommen nachts am selben Bahnhof an und bleiben laenger als geplant, "
        "weil der letzte Zug schon weg ist und der naechste erst morgens faehrt.",
    )
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998 mit einem Koffer")
    repo.setze_figur(conn, CHAT, "Erhan", "holte sie am Bahnhof ab")
    repo.setze_phase(conn, CHAT, 4)
    szene_id = repo.lege_szene_an(conn, CHAT, 1, "Ankunft am Gleis", None, None)
    repo.aktualisiere_szene(
        conn, szene_id, "Ankunft am Gleis", None,
        "MERYEM: Drei Jahre. Unter dem Bett. Gepackt.\nERHAN: Du kannst ihn jetzt auspacken.",
    )
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
        "IT_DB": DB_PFAD, "IT_WEB_BIND": BIND, "IT_WEB_PREFIX": "",
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


@pytest.mark.parametrize("viewport,name", [(HANDY, "handy"), (LAPTOP, "laptop")])
def test_kopfzeile_ueberlappt_keinen_panelinhalt(server, browser, token, viewport, name):
    """Birk: 'Workbench und Chat werden von Next up ueberdeckt.' Kein
    Bounding-Rect des Kopfbereichs (roadmap + tabs) darf das erste
    sichtbare Inhaltselement eines Panels schneiden."""
    kontext = browser.new_context(viewport=viewport)
    seite = kontext.new_page()
    seite.set_default_timeout(8000)
    seite.goto(f"{BASIS}/g/{token}")
    seite.wait_for_selector("#tab-chat:not([hidden])")
    for tab in TABS:
        seite.click(f'.tabs button[data-tab="{tab}"]')
        seite.wait_for_selector(f"#tab-{tab}:not([hidden])")
        kopf = seite.locator("#roadmap").bounding_box()
        tabs_kasten = seite.locator(".tabs").bounding_box()
        # "Next up" kann -- je nach Fassung -- IN #roadmap verschachtelt oder
        # ein eigenes Geschwisterelement sein; #roadmap allein zeigt eine
        # Ueberlappung nicht, wenn "Next up" ausserhalb seiner eigenen Box
        # liegt (genau das war Birks Befund: ein negatives Margin zog ein
        # separates #ux-naechstes ueber die Tableiste). Pruefe sein eigenes
        # Bounding-Rect unabhaengig von #roadmap gegen die OBERE Kante der
        # Tableiste -- nicht gegen deren untere Kante (``kopf_unten`` unten
        # ist fuer die PANEL-Inhaltspruefung gedacht und waere hier immer
        # erfuellt, weil sie bereits die Tableiste selbst mit einschliesst).
        naechstes = seite.locator("#ux-naechstes")
        if naechstes.count() and naechstes.is_visible():
            kasten = naechstes.bounding_box()
            if kasten is not None:
                assert kasten["y"] + kasten["height"] <= tabs_kasten["y"] + 1, (
                    name, tab, "ux-naechstes ueberlappt die Tableiste",
                    kasten, tabs_kasten,
                )
        # Kein Schnitt: der Kopf (roadmap + tabs) endet, bevor der Inhalt beginnt.
        kopf_unten = max(kopf["y"] + kopf["height"], tabs_kasten["y"] + tabs_kasten["height"])
        panel = seite.locator(f"#tab-{tab}")
        erstes = panel.locator(":scope > *").first
        if erstes.count() == 0:
            continue
        inhalt = erstes.bounding_box()
        if inhalt is None:
            continue
        assert inhalt["y"] >= kopf_unten - 1, (name, tab, kopf, tabs_kasten, inhalt)
    kontext.close()


def test_kopfzeilenhoehe_passt_aufs_handy(server, browser, token):
    """Karte, Punkt E: Kopf + Tableiste zusammen <= 96px am Handy."""
    kontext = browser.new_context(viewport=HANDY)
    seite = kontext.new_page()
    seite.goto(f"{BASIS}/g/{token}")
    seite.wait_for_selector("#tab-chat:not([hidden])")
    kopf = seite.locator("#roadmap").bounding_box()
    tabs_kasten = seite.locator(".tabs").bounding_box()
    hoehe = kopf["height"] + tabs_kasten["height"]
    assert hoehe <= 96, (kopf, tabs_kasten, hoehe)
    kontext.close()


def test_kein_akt_wort_im_kopf(server, browser, token):
    """Birk: 'Act and Phase doppeln sich.' Kein sichtbares 'Act'/'Akt' im
    Kopfbereich -- nur noch 'Phase N/7 · Name' + 'Next up'."""
    kontext = browser.new_context(viewport=HANDY)
    seite = kontext.new_page()
    seite.goto(f"{BASIS}/g/{token}")
    seite.wait_for_selector("#roadmap")
    text = seite.locator("#roadmap > summary").inner_text()
    assert "Act" not in text and "Akt" not in text, text
    kontext.close()
