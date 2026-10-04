"""Die CoThinker-Tafel im echten Browser (Task 2, Padua CoThinker-Tab clean).

Task 1 hat die Tafel auf eine einzige sichtbare Karte umgebaut, mit einer
Browser-seitigen Verlaufsnavigation (◀/▶, Pfeiltasten, Wischen) -- der
Zeiger (``buehnePos``) lebt dabei NUR im Client-JS, nie auf dem Server
(siehe ``interview_theater/web_vereint.py``, Abschnitt ab
``buehneVerlauf``/``buehnePos``). ``tests/test_buehne_tafel_struktur.py``
haelt den Server-Vertrag (``web._buehne_html``) am HTML fest -- was dort
strukturell nicht pruefbar ist, ist genau das Interaktive: ein Klick, eine
Pfeiltaste, ein Wisch, und vor allem DAS EINE VERHALTEN, fuer das die ganze
Karte gebaut wurde -- ein Poll waehrend des Zurueckblaetterns darf die
Tafel NICHT verschieben (nur der "neu:"-Hinweis in der Navigationsleiste
erscheint), waehrend ein Poll auf "aktuell" automatisch nachzieht.

Kein Bot laeuft mit: die Karten werden direkt ueber
``repo.lege_buehnenkarte_an`` angelegt, wie es ``tests/test_web.py``
ebenfalls tut. Alles Material ist frei erfunden.

Aufruf::

    python3 -m pytest -q tests/e2e/test_buehne_verlauf_e2e.py -v

Im normalen ``pytest``-Lauf wird die Datei uebersprungen
(``importorskip``). Die Screenshots gehen ins Repository
(``docs/ux-padua/cothinker/``) -- sie sind der Beleg der Abnahme und
duerfen deshalb nichts Echtes zeigen.
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
from playwright.sync_api import sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo, web_vereint  # noqa: E402

# Eigene DB/Audio/Log/Port -- unabhaengig von test_web_vereint_e2e.py, damit
# beide Dateien in derselben pytest-Sitzung nicht um dieselbe SQLite-Datei
# oder denselben Port konkurrieren.
DB_PFAD = "/tmp/it-buehneverlauf.db"
AUDIO = "/tmp/it-buehneverlauf-audio"
SERVERLOG = "/tmp/it-buehneverlauf-server.log"

# Eine chat_id je Zustand -- getrennte Gruppen, damit ein Test, der Karten
# nachlegt (5/6), die Ausgangslage eines anderen Tests nicht veraendert.
CHAT_NAV = 8_100_000_000_001          # 4 Karten, nur gelesen (Tests 1-4)
CHAT_PAGE_BACK = 8_100_000_000_002    # 4 Karten, Test 5 legt eine fuenfte an
CHAT_CURRENT = 8_100_000_000_003      # 4 Karten, Test 6 legt eine fuenfte an
CHAT_LEER = 8_100_000_000_004         # keine Karten, keine Aufnahme
CHAT_HOERT = 8_100_000_000_005        # keine Karten, Aufnahme "empfangen"
CHAT_EINE_KARTE = 8_100_000_000_006   # genau eine Karte (kein Nav)
CHAT_NAV_HANDY = 8_100_000_000_007    # 4 Karten, eigene Kopie fuer den
CHAT_NAV_LAPTOP = 8_100_000_000_008   # Screenshot-Lauf je Bildschirmgroesse
CHAT_HINTERGRUND = 8_100_000_000_009  # Karte entsteht, waehrend der Chat-Tab vorn ist

HANDY = {"width": 390, "height": 844}
GEDULD = 8000
#: Die Screenshots der Abnahme -- committet, nur erfundenes Material.
SCHUSS = WURZEL / "docs" / "ux-padua" / "cothinker"

#: Dieselben vier Texte in Erzeugungsreihenfolge, fuer jede "4 Karten"-Gruppe.
VIER_TEXTE = ("Erste.", "Zweite.", "Dritte.", "Vierte.")


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


BIND = f"127.0.0.1:{_freier_port()}"
BASIS = f"http://{BIND}"


def _lege_gruppe(conn, chat_id: int, bot_name: str, titel: str) -> str:
    """Eine Web-Gruppe in Phase 4 -- der CoThinker-Tab existiert nur dort."""
    repo.sichere_gruppe(conn, chat_id, bot_name, titel)
    repo.setze_gruppe_kanal(conn, chat_id, "web")
    repo.setze_phase(conn, chat_id, 4)
    return repo.stelle_web_token_sicher(conn, chat_id)


def _vier_karten(conn, chat_id: int) -> None:
    for text in VIER_TEXTE:
        repo.lege_buehnenkarte_an(conn, chat_id, text, "infomaniak")


def _baue_datenbank() -> dict:
    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)

    tokens = {}
    tokens["nav"] = _lege_gruppe(conn, CHAT_NAV, "gruppe-nav", "Die Blaetternden")
    _vier_karten(conn, CHAT_NAV)

    tokens["page_back"] = _lege_gruppe(conn, CHAT_PAGE_BACK, "gruppe-zurueck", "Die Zurueckgeblaetterten")
    _vier_karten(conn, CHAT_PAGE_BACK)

    tokens["current"] = _lege_gruppe(conn, CHAT_CURRENT, "gruppe-aktuell", "Die Aktuellen")
    _vier_karten(conn, CHAT_CURRENT)

    tokens["leer"] = _lege_gruppe(conn, CHAT_LEER, "gruppe-leer", "Die Leeren")

    tokens["hoert"] = _lege_gruppe(conn, CHAT_HOERT, "gruppe-hoert", "Die Lauschenden")
    repo.lege_aufnahme_an(conn, CHAT_HOERT, 1, "lang", "sprache", "/tmp/x.ogg", 5)

    tokens["eine_karte"] = _lege_gruppe(conn, CHAT_EINE_KARTE, "gruppe-eine-karte", "Die Einzelkarte")
    repo.lege_buehnenkarte_an(conn, CHAT_EINE_KARTE, "Ein erster Gedanke.", "infomaniak")

    tokens["nav_handy"] = _lege_gruppe(conn, CHAT_NAV_HANDY, "gruppe-nav-handy", "Die Handygruppe")
    _vier_karten(conn, CHAT_NAV_HANDY)

    tokens["nav_laptop"] = _lege_gruppe(conn, CHAT_NAV_LAPTOP, "gruppe-nav-laptop", "Die Laptopgruppe")
    _vier_karten(conn, CHAT_NAV_LAPTOP)

    tokens["hintergrund"] = _lege_gruppe(conn, CHAT_HINTERGRUND, "gruppe-hintergrund", "Die Abwesenden")
    repo.lege_buehnenkarte_an(conn, CHAT_HINTERGRUND, "Erste.", "infomaniak")

    conn.commit()
    conn.close()
    return tokens


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
def tokens() -> dict:
    return _baue_datenbank()


@pytest.fixture(scope="module")
def schuss_verzeichnis() -> Path:
    shutil.rmtree(SCHUSS, ignore_errors=True)
    SCHUSS.mkdir(parents=True, exist_ok=True)
    return SCHUSS


@pytest.fixture(scope="module")
def server(tokens):
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
    yield verbindung
    verbindung.close()


def _oeffne(browser, token: str):
    kontext = browser.new_context(viewport=HANDY, is_mobile=True, has_touch=True)
    blatt = kontext.new_page()
    blatt.set_default_timeout(GEDULD)
    blatt.goto(f"{BASIS}/g/{token}")
    blatt.wait_for_selector("#verlauf")
    return kontext, blatt


def _zur_buehne(seite) -> None:
    seite.click('.tabs button[data-tab="buehne"]')
    seite.wait_for_selector("#tab-buehne:not([hidden])")


@pytest.fixture
def seite(server, browser, tokens):
    kontext, blatt = _oeffne(browser, tokens["nav"])
    _zur_buehne(blatt)
    yield blatt
    kontext.close()


def _warte(seite, bedingung, ms: int = GEDULD, schritt: int = 100) -> bool:
    ende = time.time() + ms / 1000
    while time.time() < ende:
        if bedingung():
            return True
        seite.wait_for_timeout(schritt)
    return bedingung()


def _tafel(seite) -> str:
    return (seite.text_content("#buehne-tafel") or "").strip()


def _zaehler(seite) -> str:
    el = seite.locator("#buehne-nav .zaehler")
    return el.text_content() if el.count() else ""


def _swipe(seite, selector: str, x0: int, x1: int) -> None:
    """Simuliert ein Wischen ueber ``selector`` durch synthetische
    ``touchstart``/``touchend``-Ereignisse.

    Playwrights eingebaute Touch-API (``page.touchscreen``) bildet nur
    Taps nach, kein Wischen mit frei waehlbarer Distanz; ein echtes
    ``new TouchEvent(...)`` scheitert in manchen Chromium-Bauarten an
    fehlenden ``Touch``-Konstruktoren im Headless-Modus. Der robuste Weg
    (vom Brief selbst als Rueckfall genannt): ein gewoehnliches ``Event``
    desselben Typs, dem ``touches``/``changedTouches`` per
    ``Object.defineProperty`` aufgepraegt werden -- genau die zwei Felder,
    die der Code tatsaechlich liest (``ev.touches[0].clientX``,
    ``ev.changedTouches[0].clientX``). Da ``addEventListener`` nach dem
    Ereignistyp (String) sucht, nicht nach der Klasse des Objekts, loest das
    denselben Handler aus wie ein echter Touch -- geprueft wird damit das
    beobachtbare Ergebnis (welche Karte danach auf der Tafel steht), nicht
    die Simulationstechnik selbst."""
    seite.eval_on_selector(
        selector,
        """
        (el, arg) => {
          const [x0, x1] = arg;
          function fire(type, x) {
            const ev = new Event(type, { bubbles: true, cancelable: true });
            const touch = { clientX: x, clientY: 10 };
            Object.defineProperty(ev, 'touches', { value: [touch] });
            Object.defineProperty(ev, 'changedTouches', { value: [touch] });
            el.dispatchEvent(ev);
          }
          fire('touchstart', x0);
          fire('touchend', x1);
        }
        """,
        [x0, x1],
    )


# -- 1. Tab oeffnen, neueste Karte + Zaehler --------------------------------

def test_tab_zeigt_die_neueste_karte_und_den_zaehler(seite):
    assert _warte(seite, lambda: _tafel(seite) == "Vierte.")
    assert _zaehler(seite) == "4/4"


# -- 2. Zurueck zeigt die vorige Karte, vor kehrt zurueck -------------------

def test_zurueck_zeigt_die_vorige_karte_und_vor_kehrt_zurueck(seite):
    assert _warte(seite, lambda: _tafel(seite) == "Vierte.")

    seite.click('#buehne-nav [data-v="zurueck"]')
    assert _warte(seite, lambda: _tafel(seite) == "Dritte.")
    assert _zaehler(seite) == "3/4"
    assert seite.locator('#buehne-nav [data-v="live"]').count() == 1

    seite.click('#buehne-nav [data-v="vor"]')
    assert _warte(seite, lambda: _tafel(seite) == "Vierte.")
    assert _zaehler(seite) == "4/4"
    assert seite.locator('#buehne-nav [data-v="live"]').count() == 0


# -- 3. Pfeiltasten, nur solange der Buehne-Tab aktiv ist -------------------

def test_pfeiltasten_blaettern_nur_bei_aktivem_buehne_tab(seite):
    assert _warte(seite, lambda: _tafel(seite) == "Vierte.")
    # Fokus auf die Tafel, nicht auf ein Eingabefeld (#eingabe lebt im
    # Chat-Tab und ist hier gar nicht sichtbar, aber sicher ist sicher).
    seite.click("#buehne-tafel")

    seite.keyboard.press("ArrowLeft")
    assert _warte(seite, lambda: _tafel(seite) == "Dritte.")
    seite.keyboard.press("ArrowRight")
    assert _warte(seite, lambda: _tafel(seite) == "Vierte.")

    # Tab-Scoping (``buehneAktiv()``): auf "stand" wirkt die Pfeiltaste nicht.
    seite.click('.tabs button[data-tab="stand"]')
    seite.wait_for_selector("#tab-stand:not([hidden])")
    seite.keyboard.press("ArrowLeft")
    seite.click('.tabs button[data-tab="buehne"]')
    seite.wait_for_selector("#tab-buehne:not([hidden])")
    assert _tafel(seite) == "Vierte."
    assert _zaehler(seite) == "4/4"


# -- 4. Wischen: rechts = zurueck, links = vor ------------------------------

def test_wischen_blaettert_in_die_richtige_richtung(seite):
    assert _warte(seite, lambda: _tafel(seite) == "Vierte.")

    # Rechts-Wisch (delta > 0) = "zurueck" (per Code: delta < 0 ? 1 : -1).
    _swipe(seite, "#buehne-tafel", 200, 280)
    assert _warte(seite, lambda: _tafel(seite) == "Dritte.")
    assert _zaehler(seite) == "3/4"

    # Links-Wisch (delta < 0) = "vor".
    _swipe(seite, "#buehne-tafel", 280, 200)
    assert _warte(seite, lambda: _tafel(seite) == "Vierte.")
    assert _zaehler(seite) == "4/4"


# -- 5. Das tragende Verhalten: zurueckgeblaettert, ein Poll kommt an, -------
#       kein automatischer Sprung, "neu:"-Hinweis erscheint ----------------

def test_zurueckgeblaettert_kein_automatischer_sprung_sondern_neu_hinweis(server, browser, tokens, conn):
    kontext, seite = _oeffne(browser, tokens["page_back"])
    try:
        _zur_buehne(seite)
        assert _warte(seite, lambda: _tafel(seite) == "Vierte.")

        seite.click('#buehne-nav [data-v="zurueck"]')
        assert _warte(seite, lambda: _tafel(seite) == "Dritte.")
        assert _zaehler(seite) == "3/4"

        repo.lege_buehnenkarte_an(conn, CHAT_PAGE_BACK, "Fuenfte.", "infomaniak")
        conn.commit()

        # Mindestens ein Poll-Takt (``NACHLADEN_MS``) plus Spielraum.
        assert _warte(
            seite, lambda: seite.locator("#buehne-nav .neu").count() == 1,
            ms=web_vereint.NACHLADEN_MS + 6000,
        )
        # Das tragende Verhalten: die Tafel bleibt UNVERAENDERT stehen.
        assert _tafel(seite) == "Dritte."
        # n ist gewachsen (5 Karten insgesamt), die Position der "Dritte."
        # bleibt aber Index 2 -> Anzeige 3/5, nicht 3/4.
        assert _zaehler(seite) == "3/5"
        hinweis = seite.text_content("#buehne-nav .neu") or ""
        assert "Fuenfte" in hinweis

        seite.click('#buehne-nav [data-v="live"]')
        assert _warte(seite, lambda: _tafel(seite) == "Fuenfte.")
        assert _zaehler(seite) == "5/5"
        assert seite.locator('#buehne-nav [data-v="live"]').count() == 0
        assert seite.locator("#buehne-nav .neu").count() == 0
    finally:
        kontext.close()


# -- 6. Das Gegenstueck: auf "aktuell" sitzend zieht ein Poll automatisch ---
#       nach -------------------------------------------------------------

def test_auf_aktuell_zieht_ein_poll_automatisch_nach(server, browser, tokens, conn):
    kontext, seite = _oeffne(browser, tokens["current"])
    try:
        _zur_buehne(seite)
        assert _warte(seite, lambda: _tafel(seite) == "Vierte.")
        assert _zaehler(seite) == "4/4"
        # Bewusst NICHT zurueckgeblaettert -- pos bleibt null.

        repo.lege_buehnenkarte_an(conn, CHAT_CURRENT, "Fuenfte.", "infomaniak")
        conn.commit()

        assert _warte(
            seite, lambda: _tafel(seite) == "Fuenfte.",
            ms=web_vereint.NACHLADEN_MS + 6000,
        )
        assert _zaehler(seite) == "5/5"
        assert seite.locator('#buehne-nav [data-v="live"]').count() == 0
        assert seite.locator("#buehne-nav .neu").count() == 0
    finally:
        kontext.close()


# -- 6b. Karte entsteht bei verborgenem Panel (Birk Live-Test 04.10.2026) ---
#
# Frueher merkte sich ``ladeBuehne`` den Stand auch dann als "gezeigt", wenn
# das Panel verborgen war -- nach dem Oeffnen tauschte kein Takt mehr, das
# Panel blieb bis zum Reload auf dem alten (oft leeren) Stand.

def test_karte_im_hintergrund_erscheint_nach_dem_oeffnen_ohne_reload(server, browser, tokens, conn):
    kontext, seite = _oeffne(browser, tokens["hintergrund"])
    try:
        assert seite.evaluate("document.body.dataset.tab") != "buehne"
        repo.lege_buehnenkarte_an(conn, CHAT_HINTERGRUND, "Zweite.", "infomaniak")
        conn.commit()
        assert _warte(
            seite,
            lambda: seite.get_attribute('.tabs button[data-tab="buehne"]', "data-neu") == "1",
            ms=web_vereint.NACHLADEN_MS + 6000,
        )
        _zur_buehne(seite)
        # Sofort beim Oeffnen geholt -- deutlich unter einem Nachladetakt.
        assert _warte(seite, lambda: _tafel(seite) == "Zweite.", ms=4000)
    finally:
        kontext.close()


# -- 7. Leer und "hoert zu" rendern im echten Browser ohne Absturz ----------

def test_leer_und_hoert_zu_rendern_fehlerfrei(server, browser, tokens):
    kontext, seite = _oeffne(browser, tokens["leer"])
    try:
        _zur_buehne(seite)
        assert _warte(seite, lambda: seite.locator(".buehne-leer").count() == 1)
        assert (seite.text_content(".buehne-leer") or "").strip() != ""
        assert seite.locator("#buehne-tafel").count() == 0
        assert seite.locator("#buehne-nav").count() == 0
        assert seite.locator("#buehne-verlauf-daten").count() == 0
    finally:
        kontext.close()

    kontext, seite = _oeffne(browser, tokens["hoert"])
    try:
        _zur_buehne(seite)
        assert _warte(seite, lambda: seite.locator("#buehne-status").count() == 1)
        assert (seite.text_content("#buehne-status") or "").strip() != ""
    finally:
        kontext.close()


# -- Screenshots -------------------------------------------------------------

@pytest.mark.parametrize("breite,hoehe,name", [(390, 844, "handy"),
                                               (1366, 900, "laptop")])
def test_screenshots(server, browser, tokens, conn, schuss_verzeichnis,
                     breite, hoehe, name):
    """Die Abnahme der Karte: leer, hoert zu, eine Karte, vier Karten --
    und zuletzt, mittendrin im Ablauf aus Test 5, der "neu:"-Hinweis beim
    Zurueckblaettern (das am schwersten zu beschreibende Element dieser
    ganzen Funktion)."""
    kontext = browser.new_context(viewport={"width": breite, "height": hoehe})
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD)

    seite.goto(f"{BASIS}/g/{tokens['leer']}")
    seite.wait_for_selector("#verlauf")
    _zur_buehne(seite)
    seite.wait_for_selector(".buehne-leer")
    seite.screenshot(path=str(schuss_verzeichnis / f"{name}-leer.png"))

    seite.goto(f"{BASIS}/g/{tokens['hoert']}")
    seite.wait_for_selector("#verlauf")
    _zur_buehne(seite)
    seite.wait_for_selector("#buehne-status")
    seite.screenshot(path=str(schuss_verzeichnis / f"{name}-aufnahme-laeuft.png"))

    seite.goto(f"{BASIS}/g/{tokens['eine_karte']}")
    seite.wait_for_selector("#verlauf")
    _zur_buehne(seite)
    seite.wait_for_selector("#buehne-tafel")
    seite.screenshot(path=str(schuss_verzeichnis / f"{name}-eine-karte.png"))

    nav_token = tokens["nav_handy"] if name == "handy" else tokens["nav_laptop"]
    nav_chat_id = CHAT_NAV_HANDY if name == "handy" else CHAT_NAV_LAPTOP
    seite.goto(f"{BASIS}/g/{nav_token}")
    seite.wait_for_selector("#verlauf")
    _zur_buehne(seite)
    assert _warte(seite, lambda: _zaehler(seite) == "4/4")
    seite.screenshot(path=str(schuss_verzeichnis / f"{name}-vier-karten.png"))

    seite.click('#buehne-nav [data-v="zurueck"]')
    assert _warte(seite, lambda: _zaehler(seite) == "3/4")

    repo.lege_buehnenkarte_an(conn, nav_chat_id, "Fuenfte.", "infomaniak")
    conn.commit()
    assert _warte(
        seite, lambda: seite.locator("#buehne-nav .neu").count() == 1,
        ms=web_vereint.NACHLADEN_MS + 6000,
    )
    seite.screenshot(path=str(schuss_verzeichnis / f"{name}-zurueckgeblaettert-neu-hinweis.png"))

    kontext.close()
