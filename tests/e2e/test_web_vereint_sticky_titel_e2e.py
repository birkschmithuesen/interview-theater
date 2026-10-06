"""Feedbackloop S8 (Browserlauf ``2026-10-05-handy-giulia-p12``, Befunde
``100-…``/``015-…png``): "Gruppentitel (sticky) schneidet die oberste Blase
an" -- auf dem Handy (390x844) landete das automatische Scrollen ans Ende
des Verlaufs (``web_chat._CHAT_JS``, ``nachUnten()``:
``verlauf.scrollTop = verlauf.scrollHeight``, nicht angefasst -- parallele
Karte) oft mitten in einer Blase: ihr oberer Rand erschien direkt unter dem
Gruppentitel abgeschnitten, ohne Luft -- liest sich wie ein ueberlappender/
"sticky" Titel, ist aber die eigene, polsterlose obere Kante des Scrollbereichs
(gemessen: der Titel ist ``position: static`` und ueberlappt nichts).

Drei Kandidaten wurden am echten Chromium gemessen, bevor der Fix entstand
(Einzelheiten: Docstring von ``web_vereint._css_schale``):
``scroll-padding-top`` wirkt nicht auf eine direkte ``scrollTop``-Zuweisung,
``scroll-snap-type``/``-align`` rastet dabei ebenfalls nicht ein, und ein
festes ``padding-bottom`` verschiebt die Schnittkante nur um sich selbst --
bei anderer Blasenlaenge/Gesamthoehe trifft sie wieder irgendeine Blase
(content-abhaengig, kein allgemeiner Beweis). Der tragende Fix ist deshalb
eine Maske (``-webkit-mask-image``/``mask-image``, ``web_vereint.
_css_schale``, reiner CSS-Gradient, kein ``url()``): sie faerbt den obersten
Streifen von ``.verlauf`` IMMER weich zum Hintergrund aus, unabhaengig davon,
welche Blase dort gerade steht oder wie lang sie ist -- keine harte
Schnittkante mehr.

Dieser Test misst das am echten gerenderten Bild (Pixelfarbe an der oberen
Kante vs. Hintergrundfarbe), mit ABSICHTLICH langem Fuelltext, der garantiert
mitten in einer Blase endet (dieselbe Textlaenge liess die geometrische
Pruefung -- s. u. -- zuverlaessig fehlschlagen, auch mit ``padding-bottom``
allein). Server-/Browser-Fixtures hier bewusst eigenstaendig nachgebaut, wie
in ``tests/e2e/test_web_chat_e2e.py``, statt jene Datei zu importieren oder
zu aendern -- ``interview_theater/web_chat.py`` bleibt fuer diese Karte
unberuehrt.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_vereint_sticky_titel_e2e.py -q

Im normalen ``pytest``-Lauf wird die Datei uebersprungen (``importorskip``).
"""

import base64
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

from interview_theater import db, repo, web_gestalt, web_kanal  # noqa: E402

DB_PFAD = "/tmp/it-sticky-titel.db"
AUDIO = "/tmp/it-sticky-titel-audio"
SERVERLOG = "/tmp/it-sticky-titel-server.log"
CHAT = 7_000_000_000_777

HANDY = {"width": 390, "height": 844}

#: Der ``--grund``-Tonwert des zurzeit gewaehlten Entwurfs -- die Maske
#: faerbt dorthin aus, nicht in ein beliebiges Dunkel.
_GRUND = web_gestalt.TOKENS[web_gestalt.entwurf()]["grund"]


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


BIND = f"127.0.0.1:{_freier_port()}"
BASIS = f"http://{BIND}"
PRAEFIX = "/theatersoap"


def _baue_datenbank() -> str:
    """Eine Web-Gruppe mit genug UND absichtlich ungleich langem Verlauf,
    dass das Scroll-Ende (``nachUnten()``) garantiert mitten in einer Blase
    liegt -- die geometrische Gegenprobe unten zeigt das ohne den Fix
    zuverlaessig. Alle Inhalte frei erfunden, angelehnt an die
    Padua-Simulation (Titel, Phase 1, eine Korrektur-Quittung mit Leiste --
    derselbe Markup-Mix wie in ``100-…``/``015-…png``)."""
    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    shutil.rmtree(AUDIO, ignore_errors=True)

    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Padua UX-Simulation")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 1)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Ankommen, Arbeit, Nacht")

    kanal = web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01)
    for i in range(6):
        kanal.sende(
            CHAT,
            f"Nachricht Nummer {i} — etwas Text, der den Verlauf fuellt, "
            "damit auf dem Handy ueberhaupt gescrollt werden muss.",
        )
    knopf_aendern = repo.lege_knopf_an(conn, CHAT, "aendern", None)
    knopf_undo = repo.lege_knopf_an(conn, CHAT, "undo", None)
    kanal.sende_mit_knoepfen(
        CHAT, "Was moechtet ihr aendern?",
        [("Change something", f"k:{knopf_aendern}"), ("Undo", f"k:{knopf_undo}")],
    )
    kanal.sende(CHAT, "Noted:\nCorrected: foam -> home, wading -> waiting")
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
        "IT_DB": DB_PFAD, "IT_WEB_BIND": BIND, "IT_WEB_PREFIX": PRAEFIX,
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
def seite(server, browser, token):
    kontext = browser.new_context(viewport=HANDY, is_mobile=True, has_touch=True)
    blatt = kontext.new_page()
    blatt.set_default_timeout(8000)
    blatt.goto(f"{BASIS}/g/{token}/chat")
    blatt.wait_for_selector(".panel-chat .verlauf")
    # ``nachUnten()`` laeuft beim Laden und bei jedem Poll -- eine kurze
    # Wartezeit genuegt, das Layout ist beim ``wait_for_selector`` schon da.
    blatt.wait_for_timeout(400)
    yield blatt
    kontext.close()


def _verlaufskante(seite) -> dict:
    return seite.evaluate("""() => {
        const v = document.querySelector('.panel-chat .verlauf');
        const r = v.getBoundingClientRect();
        return {top: r.top, left: r.left, width: r.width};
    }""")


def _rgb(hilfsseite, png_bytes: bytes, x: float, y: float) -> tuple[int, int, int]:
    """Liest eine Pixelfarbe aus einem Screenshot -- ueber ein Canvas in
    einer unbeteiligten, CSP-freien Hilfsseite (nicht die App-Seite: deren
    CSP hat kein ``img-src`` fuer ``data:``). ``hilfsseite`` ist eine
    frische ``Page`` ohne eigene Navigation zur App."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    hilfsseite.set_content("<canvas id='c'></canvas>")
    wert = hilfsseite.evaluate(
        """([b64, x, y]) => new Promise((ok) => {
            const bild = new Image();
            bild.onload = () => {
                const c = document.getElementById('c');
                c.width = bild.width; c.height = bild.height;
                const ctx = c.getContext('2d');
                ctx.drawImage(bild, 0, 0);
                const d = ctx.getImageData(Math.round(x), Math.round(y), 1, 1).data;
                ok([d[0], d[1], d[2]]);
            };
            bild.src = 'data:image/png;base64,' + b64;
        })""",
        [b64, x, y],
    )
    return tuple(wert)


def _hex_zu_rgb(hex_farbe: str) -> tuple[int, int, int]:
    h = hex_farbe.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def test_die_obere_kante_des_verlaufs_faerbt_zum_hintergrund_aus(seite, browser):
    """Der tragende Beweis: unabhaengig davon, welche (ggf. mitten
    angeschnittene) Blase am Scroll-Ende an der oberen Kante von
    ``.verlauf`` steht, ist die PIXELFARBE direkt an dieser Kante nah am
    Seitenhintergrund (``--grund``) -- die Maske hat sie ausgeblendet. Ein
    zweiter Punkt deutlich darunter (ausserhalb des Maskenstreifens) zeigt
    dagegen sichtbaren Blaseninhalt (keine triviale "ist ueberall dunkel"-
    Bestaetigung)."""
    kante = _verlaufskante(seite)
    mitte_x = kante["left"] + kante["width"] / 2
    png = seite.screenshot()

    hilfe = browser.new_page()
    try:
        oben = _rgb(hilfe, png, mitte_x, kante["top"] + 1)
        tiefer = _rgb(hilfe, png, mitte_x, kante["top"] + 40)
    finally:
        hilfe.close()

    grund = _hex_zu_rgb(_GRUND)
    abstand_oben = sum(abs(a - b) for a, b in zip(oben, grund))
    abstand_tiefer = sum(abs(a - b) for a, b in zip(tiefer, grund))
    assert abstand_oben <= 18, (oben, grund, abstand_oben)
    assert abstand_tiefer > abstand_oben, (oben, tiefer, grund)


def test_verlauf_traegt_die_maske_als_computed_style(seite):
    """Ergaenzend zum Pixelbeweis: die Eigenschaft kommt im echten Browser
    an (keine CSP-Blockade, keine spaetere Regel ueberschreibt sie mit
    ``none``) -- gemessen per ``getComputedStyle``, nicht nur am CSS-Text
    (das deckt ``tests/test_web_gestalt_css.py`` ab)."""
    wert = seite.evaluate("""() => {
        const v = document.querySelector('.panel-chat .verlauf');
        const s = getComputedStyle(v);
        return s.maskImage || s.webkitMaskImage || s.getPropertyValue('-webkit-mask-image');
    }""")
    assert wert and wert != "none", wert


def test_keine_blase_wird_an_der_oberen_verlaufskante_hart_angeschnitten(seite):
    """Gegenprobe/Dokumentation: GEOMETRISCH endet die Liste weiterhin oft
    mitten in einer Blase (das zu verhindern braucht die Scroll-Logik in
    ``web_chat._CHAT_JS``, ausserhalb dieser Karte) -- genau deshalb traegt
    die Maske oben den eigentlichen Beweis. Dieser Test ist bewusst xfail:
    er haelt fest, WARUM ein reiner Geometrie-Beweis hier nicht reicht,
    statt es stillschweigend offen zu lassen."""
    masse = seite.evaluate("""() => {
        const verlauf = document.querySelector('.panel-chat .verlauf');
        const kante = verlauf.getBoundingClientRect().top;
        const kinder = Array.from(verlauf.children).map(k => {
            const r = k.getBoundingClientRect();
            return {top: r.top, bottom: r.bottom};
        });
        return {kante, kinder};
    }""")
    kante = masse["kante"]
    angeschnitten = [
        k for k in masse["kinder"]
        if k["top"] < kante - 0.5 and k["bottom"] > kante + 0.5
    ]
    if not angeschnitten:
        pytest.skip("diesmal zufaellig keine Blase mitten angeschnitten")
    pytest.xfail(
        "geometrisch weiterhin angeschnitten (erwartet) -- die Maske loest "
        "das visuell, nicht die Geometrie; siehe Moduldocstring"
    )
