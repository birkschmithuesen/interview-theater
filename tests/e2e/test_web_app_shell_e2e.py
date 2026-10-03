"""Die Mobile-App-Shell im echten Chromium (Nachbesserung 03.10.2026,
Birk-Befund 09:19, Handytest -- woertlich: "die website auf dem handy
rutscht hoch und runter, wenn sich unten tastatur oeffnet ... auch nach
rechts ist platz und es rutscht hin und her").

Was ``tests/test_web_vereint.py`` nicht pruefen kann: ob eine Seite auf dem
Telefon wirklich NICHT seitlich scrollt (``scrollWidth``/``innerWidth``,
das braucht echtes Layout), und ob das Fokussieren des Chat-Eingabefelds
das Dokument selbst verschiebt (``window.scrollY``). Beides ist der Kern
der Karte -- eine Behauptung ueber CSS-Text beweist noch kein Layout.

Zwei Telefon-Groessen, wie von der Karte verlangt: 390x844 (iPhone-13-ish,
dasselbe ``HANDY`` wie die anderen e2e-Laeufe) und 412x915
(Pixel-7-ish) -- reine Viewport-Masse, keine Geraete-Emulation noetig.

**Nur erfundenes Material**, nie ``betrieb/``. Keine Screenshots: diese
Datei ist eine reine Messung (Zahlen), kein Abnahme-Beleg zum Ansehen.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_app_shell_e2e.py -q

Im normalen ``pytest``-Lauf wird die Datei uebersprungen
(``importorskip``).
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

DB_PFAD = "/tmp/it-appschale.db"
AUDIO = "/tmp/it-appschale-audio"
SERVERLOG = "/tmp/it-appschale-server.log"
#: Eine einzige Gruppe in Phase 4 -- das gibt alle VIER Tabs auf einen Schlag
#: (Chat, Arbeitsstand, Textbuch, Buehne), ohne eine zweite Datenbank zu
#: brauchen.
CHAT = 7_000_000_000_501

#: Dieselben Masse wie die anderen e2e-Laeufe (``test_web_gestalt_e2e.py``,
#: ``test_web_vereint_e2e.py``): iPhone-13-aehnlich.
IPHONE_13 = {"width": 390, "height": 844}
#: Pixel-7-aehnlich (die Karte verlangt eine zweite, andere Telefongroesse
#: -- kein Geraeteprofil noetig, nur andere Pixelmasse).
PIXEL_7 = {"width": 412, "height": 915}


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
    # Ein paar Zeilen im Verlauf, darunter eine lange, am Stueck geschriebene
    # ohne Leerzeichen -- genau die Form, an der ein fehlendes
    # ``overflow-wrap`` ein horizontales Scrollen zeigen wuerde.
    kanal = web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01)
    kanal.sende(CHAT, "Eure Begriffe habe ich. Womit fangen wir an?")
    kanal.sende(
        CHAT,
        "Hier https://beispiel-einer-sehr-langen-ununterbrochenen-"
        "adresse-ohne-leerzeichen.example.org/pfad/noch/laenger steht mehr dazu.",
    )
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


#: Die vier Tabs, die diese eine Phase-4-Gruppe anbietet -- in der
#: Reihenfolge der Tableiste (``web_vereint.TABS`` + ``buehne``).
TABS = ("chat", "stand", "textbuch", "buehne")


@pytest.mark.parametrize("viewport,name", [(IPHONE_13, "iphone13"), (PIXEL_7, "pixel7")])
def test_kein_horizontales_scrollen_auf_jedem_tab(server, browser, token, viewport, name):
    """Der Kern des Befunds: ``scrollWidth`` darf auf KEINEM Tab breiter
    sein als der sichtbare Bereich -- auf keiner der beiden Telefongroessen.

    ``100vw`` und ein fehlendes ``overflow-x: hidden`` zeigen sich genau
    hier: eine Scrollbar-Kompensation oder ein ungebrochen langes Wort
    (die lange URL in der zweiten Nachricht oben) macht das Dokument sonst
    breiter als der Bildschirm, und die Seite wackelt seitlich."""
    kontext = browser.new_context(viewport=viewport)
    seite = kontext.new_page()
    seite.set_default_timeout(8000)
    seite.goto(f"{BASIS}/g/{token}")
    seite.wait_for_selector("#tab-chat:not([hidden])")

    # Die Sicherheitsnetz-Regel selbst, nicht nur ihr Ergebnis: ein
    # ``scrollWidth <= innerWidth`` koennte auch durch Zufall stimmen (wenn
    # nichts im Testmaterial zufaellig ueberlaeuft). Das pruefte nichts, wenn
    # ``overflow-x: hidden`` versehentlich entfernt wuerde, solange der
    # Inhalt gerade noch passt.
    assert seite.evaluate(
        "getComputedStyle(document.documentElement).overflowX"
    ) == "hidden"

    for tab in TABS:
        seite.click(f'.tabs button[data-tab="{tab}"]')
        seite.wait_for_selector(f"#tab-{tab}:not([hidden])")
        breite = seite.evaluate("document.documentElement.scrollWidth")
        sichtbar = seite.evaluate("window.innerWidth")
        assert breite <= sichtbar, (name, tab, breite, sichtbar)

    # Die Phasenuebersicht aufgeklappt ist der zweite bekannte Kandidat fuer
    # seitliches Wackeln (lange Phasenbezeichnungen, Aufgabenzeilen).
    seite.click(".roadmap summary")
    seite.wait_for_selector(".roadmap .phasen", state="visible")
    breite = seite.evaluate("document.documentElement.scrollWidth")
    sichtbar = seite.evaluate("window.innerWidth")
    assert breite <= sichtbar, (name, "roadmap-auf", breite, sichtbar)

    kontext.close()


@pytest.mark.parametrize("viewport,name", [(IPHONE_13, "iphone13"), (PIXEL_7, "pixel7")])
def test_eingabefeld_fokussieren_verschiebt_das_dokument_nicht(
    server, browser, token, viewport, name,
):
    """Birks zweiter Befund: das Fokussieren des Eingabefelds darf die
    Seite nicht hoch- oder runterrutschen lassen. Ohne echte Tastatur (kein
    Headless-Chromium hat eine) ist das vor allem die Kontrollfrage: zieht
    irgendein Skript ``window.scrollTo``/``scrollIntoView`` auf das
    Dokument, wenn ein Feld den Fokus bekommt? Mit der App-Shell (kein
    Dokument-Scroll, ``.fuss`` ein gewoehnliches Flex-Kind statt
    ``position: fixed``) bleibt die Eingabezeile einfach stehen, wo sie
    ist -- ohne dass irgendjemand etwas tun muss."""
    kontext = browser.new_context(viewport=viewport)
    seite = kontext.new_page()
    seite.set_default_timeout(8000)
    seite.goto(f"{BASIS}/g/{token}")
    seite.wait_for_selector("#eingabe")

    vorher = seite.evaluate("window.scrollY")
    assert vorher == 0

    # Die Shell selbst, nicht nur ihre Folge: ohne das wuerde ein
    # Headless-Chromium ohne echte Tastatur die untenstehenden Pruefungen
    # (``window.scrollY``, Bounding-Box des Fusses) ebenso erfuellen, WEIL
    # ``position: fixed`` ein Element sowieso im sichtbaren Bereich haelt,
    # unabhaengig davon, ob das Dokument scrollt. Diese zwei Zeilen pruefen
    # direkt den Umbau (``web_vereint._css_schale``): kein Dokument-Scroll,
    # und der Fuss ist ein gewoehnliches Flex-Kind, kein Overlay mehr.
    assert seite.evaluate(
        "getComputedStyle(document.body).overflowY"
    ) == "hidden"
    assert seite.evaluate(
        "getComputedStyle(document.getElementById('fuss')).position"
    ) != "fixed"

    seite.focus("#eingabe")
    seite.wait_for_timeout(300)

    nachher = seite.evaluate("window.scrollY")
    assert nachher == 0, (name, "window.scrollY nach Fokus")

    fuss = seite.locator("#fuss")
    assert fuss.is_visible()
    kasten = fuss.bounding_box()
    assert kasten is not None
    assert kasten["y"] >= 0, (name, kasten)
    assert kasten["y"] + kasten["height"] <= viewport["height"], (name, kasten, viewport)

    zeile = seite.locator(".zeile")
    assert zeile.is_visible()
    zeilenkasten = zeile.bounding_box()
    assert zeilenkasten is not None
    assert zeilenkasten["y"] >= 0, (name, zeilenkasten)
    assert zeilenkasten["y"] + zeilenkasten["height"] <= viewport["height"], (
        name, zeilenkasten, viewport,
    )

    kontext.close()


def test_kein_horizontales_scrollen_auf_der_probenansicht(server, browser, token):
    """Die Probenansicht (``/g/<token>/textbuch``) ist eine eigene Seite
    (kein sanftes Nachladen, kein Panel) -- derselbe globale
    ``overflow-x: hidden`` aus ``web._CSS_GEMEINSAM`` muss auch hier
    greifen."""
    kontext = browser.new_context(viewport=IPHONE_13)
    seite = kontext.new_page()
    # Grosszuegigere Frist als die uebrigen Tests dieser Datei (8000ms):
    # gegen Ende der vollen Suite (mehrere tausend Tests, viele Chromium-
    # Starts davor) ist der Rechner knapp an Arbeitsspeicher, und ein
    # einzelner Seitenaufbau kann dann laenger dauern als in Isolation.
    seite.set_default_timeout(20000)
    seite.goto(f"{BASIS}/g/{token}/textbuch")
    seite.wait_for_selector(".probe-szene")
    breite = seite.evaluate("document.documentElement.scrollWidth")
    sichtbar = seite.evaluate("window.innerWidth")
    assert breite <= sichtbar, (breite, sichtbar)
    kontext.close()
