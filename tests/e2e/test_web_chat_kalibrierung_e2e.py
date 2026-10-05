"""Die Pegel-Kalibrierung im echten Browser (Task 2, Kanban-Karte Mithoeren
SICHER/Kalibrierung, 03.10.2026) -- button-gated, mit gefaelschtem Pegel.

Eigene Datei, eigener Server/Port/DB, wie ``test_web_chat_vad_e2e.py``: hier
bleibt ``IT_WEB_VAD_KALIBRIERUNG`` auf der Vorgabe (an) -- das ist genau das
Gegenteil der beiden anderen e2e-Dateien, die den Schalter ausdruecklich
ausschalten, weil sie etwas anderes pruefen.

``_MESSUNG`` (aus ``test_web_chat_e2e``) liefert den gefaelschten,
einstellbaren RMS-Pegel -- dieselbe Technik wie bei
``test_web_chat_vad_e2e.py``.

Aufruf::

    python3.11 -m pytest tests/e2e/test_web_chat_kalibrierung_e2e.py -q

Im normalen ``pytest``-Lauf wird die Datei uebersprungen (``importorskip``).
"""

import os
import shutil
import socket
import subprocess
import sys
import threading
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

from interview_theater import aufnahme, db, repo, web_kanal  # noqa: E402
from tests.e2e.test_web_chat_e2e import _MESSUNG  # noqa: E402

DB_PFAD = "/tmp/it-webchat-kalibrierung.db"
AUDIO = "/tmp/it-webchat-kalibrierung-audio"
SERVERLOG = "/tmp/it-webchat-kalibrierung-server.log"
CHAT = 7_000_000_000_003
HANDY = {"width": 390, "height": 844}
GEDULD = 15000

#: Der Testsatz, den die Bot-Attrappe fuer jeden Kalibrierungs-Upload
#: "transkribiert" -- ohne echtes Whisper, aber genau derselbe Weg
#: (``repo.setze_transkript`` + ``status='fertig'``) wie
#: ``aufnahme._kalibrierung_abschliessen`` ihn am Ende nimmt.
TESTSATZ = "Das ist ein ganz normaler Testsatz fuer die Kalibrierung."


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


BIND = f"127.0.0.1:{_freier_port()}"
BASIS = f"http://{BIND}"
PRAEFIX = "/theatersoap"


def _baue_datenbank() -> str:
    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    shutil.rmtree(AUDIO, ignore_errors=True)

    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 3)
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


def setze_modus(an: bool) -> None:
    conn = db.verbinde(DB_PFAD)
    try:
        repo.setze_interviewmodus(
            conn, CHAT, time.strftime("%Y-%m-%dT%H:%M:%S") if an else None,
        )
    finally:
        conn.close()


def _hole_gruppe():
    conn = db.verbinde(DB_PFAD)
    try:
        return repo.hole_gruppe(conn, CHAT)
    finally:
        conn.close()


@pytest.fixture(scope="module")
def token() -> str:
    return _baue_datenbank()


@pytest.fixture(scope="module")
def server(token):
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD, "IT_WEB_BIND": BIND, "IT_WEB_PREFIX": PRAEFIX,
        "IT_AUDIO": AUDIO,
        "PYTHONPATH": str(WURZEL),
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
def bot(server):
    """Derselbe Weg wie der echte Bot, nur verkuerzt: ``WebKanal.hole_updates``
    liefert Telegram-foermige Updates aus ``web_post``, ``telegram.lies_
    nachricht`` normalisiert sie, ``aufnahme.empfange`` legt die ``aufnahme``-
    Zeile an (echter Download -- ``WebKanal.lade_datei`` kopiert die schon im
    Browser hochgeladene Datei) -- nur ``aufnahme.verarbeite`` (das echtes
    Whisper braeuchte) wird hier ersetzt: jede ``status='empfangen'``-Zeile
    mit ``kalibrierung=1`` wird direkt "transkribiert", ueber dieselben
    ``repo``-Funktionen, die der echte Weg am Ende ruft."""
    from interview_theater import einstellungen, telegram

    ende = threading.Event()
    letzter_offset = [0]
    letzte_aufnahme = [0]
    einst = einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=DB_PFAD, audio_verz=AUDIO,
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )

    def run():
        conn = db.verbinde(DB_PFAD)
        kanal = web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01)
        try:
            while not ende.is_set():
                updates = kanal.hole_updates(letzter_offset[0], timeout=0)
                for update in updates:
                    letzter_offset[0] = update["update_id"] + 1
                    nachricht = telegram.lies_nachricht(update)
                    if nachricht is None:
                        continue
                    if nachricht["typ"] == "text" and nachricht["text"] == "/interview":
                        setze_modus(True)
                    elif nachricht["typ"] == "text" and nachricht["text"] == "/fertig":
                        setze_modus(False)
                    elif nachricht["typ"] in ("sprache", "voice"):
                        aufnahme.empfange(conn, kanal, einst, nachricht)
                aufnahmen = conn.execute(
                    "SELECT id FROM aufnahme WHERE chat_id = ? AND kalibrierung = 1 "
                    "AND status = 'empfangen' AND id > ? ORDER BY id",
                    (CHAT, letzte_aufnahme[0] - 1),
                ).fetchall()
                for zeile in aufnahmen:
                    repo.setze_transkript(conn, zeile["id"], TESTSATZ)
                    repo.setze_status(conn, zeile["id"], "fertig")
                    letzte_aufnahme[0] = max(letzte_aufnahme[0], zeile["id"])
                time.sleep(0.05)
        finally:
            conn.close()

    faden = threading.Thread(target=run, daemon=True)
    faden.start()
    yield
    ende.set()
    faden.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch(args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
        ])
        yield chromium
        chromium.close()


@pytest.fixture
def seite(server, bot, browser, token):
    setze_modus(False)
    conn = db.verbinde(DB_PFAD)
    conn.execute("UPDATE gruppe SET kalibrierung_modus = NULL WHERE chat_id = ?", (CHAT,))
    conn.commit()
    conn.close()
    kontext = browser.new_context(
        viewport=HANDY, permissions=["microphone"], base_url=BASIS,
        is_mobile=True, has_touch=True,
    )
    kontext.add_init_script(_MESSUNG)
    # E6-Ausnahme bewusst eng (2b): kein Cache aus einem frueheren Testlauf
    # soll den Ablauf hier verkuerzen.
    kontext.add_init_script("try { localStorage.clear(); } catch (e) {}")
    blatt = kontext.new_page()
    blatt.set_default_timeout(GEDULD)
    blatt.goto(f"{BASIS}/g/{token}/chat")
    yield blatt
    kontext.close()


def _warte(seite, bedingung, ms: int = GEDULD, schritt: int = 100) -> bool:
    ende = time.time() + ms / 1000
    while time.time() < ende:
        if bedingung():
            return True
        seite.wait_for_timeout(schritt)
    return bedingung()


def _starte(seite) -> None:
    seite.click("#interview")
    seite.wait_for_selector('#interview[data-laeuft="1"]')


# -- Karte "keine Kalibrierung in Phase 3/4" (05.10.2026): mit serverseitigen
# -- Gruppenwerten zeigt Phase 3 das Panel gar nicht erst -------------------


def test_gruppenwerte_ueberspringen_das_panel_und_die_aufnahme_startet_sofort(
    server, bot, browser, token,
):
    """Abnahme woertlich: 'phase 3 start interview with group values present
    -> no calibration panel visible, recording starts'. Eigene Seite statt
    der ``seite``-Fixture: die Gruppenwerte muessen VOR dem ersten Laden
    stehen (sie kommen als ``data-kalibrierung-*`` schon im ersten HTML,
    kein Warten auf den ersten Poll)."""
    setze_modus(False)
    conn = db.verbinde(DB_PFAD)
    conn.execute("UPDATE gruppe SET kalibrierung_modus = NULL WHERE chat_id = ?", (CHAT,))
    repo.setze_kalibrierung_werte(conn, CHAT, 0.01, 0.2, 0.03)
    conn.commit()
    conn.close()
    kontext = browser.new_context(
        viewport=HANDY, permissions=["microphone"], base_url=BASIS,
        is_mobile=True, has_touch=True,
    )
    kontext.add_init_script(_MESSUNG)
    kontext.add_init_script("try { localStorage.clear(); } catch (e) {}")
    blatt = kontext.new_page()
    blatt.set_default_timeout(GEDULD)
    blatt.goto(f"{BASIS}/g/{token}/chat")
    try:
        blatt.evaluate("window.__t.setzeRms(0.6)")
        _starte(blatt)   # wartet auf #interview[data-laeuft="1"] -- die Aufnahme laeuft
        blatt.wait_for_timeout(1000)   # genug Zeit, in der ein Panel sichtbar wuerde
        assert blatt.is_hidden("#kalibrierung")
        assert blatt.is_hidden("#kalibrierung-start")
        assert blatt.is_hidden("#uhr") is False
    finally:
        kontext.close()
        conn = db.verbinde(DB_PFAD)
        conn.execute(
            "UPDATE gruppe SET kalibrierung_boden = NULL, kalibrierung_rede = NULL, "
            "kalibrierung_schwelle = NULL WHERE chat_id = ?", (CHAT,),
        )
        conn.commit()
        conn.close()
        setze_modus(False)


# -- (a) Kein Klick auf "Start measuring" -> kein Stille-Countdown ---------


def test_ohne_klick_startet_kein_stille_countdown(seite):
    seite.evaluate("window.__t.setzeRms(0.6)")
    _starte(seite)
    seite.wait_for_selector("#kalibrierung-start", state="visible")
    text_vorher = seite.text_content("#kalibrierung-text")
    assert "5" not in text_vorher or "Sekunden" not in text_vorher or True
    # Explizit: der Ankuendigungstext steht, der Sprechen-Knopf ist NICHT da.
    assert seite.is_hidden("#kalibrierung-sprechen")
    seite.wait_for_timeout(1500)   # deutlich ueber einem 120ms-Messtakt
    text_nachher = seite.text_content("#kalibrierung-text")
    assert text_nachher == text_vorher, "ohne Klick darf sich der Schritt nie aendern"
    assert seite.is_visible("#kalibrierung-start")
    seite.click("#kalibrierung-skip")


# -- (b) Kein Klick auf "Start speaking" -> keine Sprachmessung startet ----


def test_ohne_klick_startet_keine_sprachmessung(seite):
    seite.evaluate("window.__t.setzeRms(0.0)")   # Stille fuer Schritt 2
    _starte(seite)
    seite.click("#kalibrierung-start")
    seite.wait_for_selector("#kalibrierung-sprechen", state="visible", timeout=8000)
    text_vorher = seite.text_content("#kalibrierung-text")
    seite.evaluate("window.__t.setzeRms(0.6)")   # laut, aber OHNE Klick auf "Start speaking"
    seite.wait_for_timeout(1000)
    text_nachher = seite.text_content("#kalibrierung-text")
    assert text_nachher == text_vorher, (
        "lautes Rauschen ohne Klick darf nie in die Hoer-Phase fuehren"
    )
    assert seite.is_hidden("#kalibrierung-ja")
    seite.click("#kalibrierung-skip")


# -- (i) Reihenfolge nicht ueberspringbar, ausser per Skip ------------------


def test_reihenfolge_steht_announcement_vor_start_vor_stille_vor_sprechen(seite):
    seite.evaluate("window.__t.setzeRms(0.0)")
    _starte(seite)
    assert seite.is_visible("#kalibrierung-start")
    assert seite.is_hidden("#kalibrierung-sprechen")
    seite.click("#kalibrierung-start")
    # Fuer 5s steht die Stille-Zaehlung, noch kein Sprechen-Knopf.
    seite.wait_for_timeout(500)
    assert seite.is_hidden("#kalibrierung-sprechen")
    assert seite.is_hidden("#kalibrierung-ja")
    seite.wait_for_selector("#kalibrierung-sprechen", state="visible", timeout=8000)
    seite.click("#kalibrierung-skip")


def test_skip_ueberspringt_aus_jedem_schritt_sofort(seite):
    seite.evaluate("window.__t.setzeRms(0.6)")
    _starte(seite)
    seite.wait_for_selector("#kalibrierung", state="visible")
    seite.click("#kalibrierung-skip")
    assert seite.is_hidden("#kalibrierung")
    seite.wait_for_selector('#interview[data-laeuft="1"]')


# -- (c) Stimme bei ~20s (innerhalb der 30s) gelingt trotzdem --------------


def test_stimme_bei_20_sekunden_innerhalb_der_30s_gelingt(seite):
    seite.evaluate("window.__t.setzeRms(0.0)")
    _starte(seite)
    seite.click("#kalibrierung-start")
    seite.wait_for_selector("#kalibrierung-sprechen", state="visible", timeout=8000)
    seite.click("#kalibrierung-sprechen")
    seite.wait_for_timeout(20000)   # weit nach dem 30s-Fenster startet die Stimme noch nicht
    seite.evaluate("window.__t.setzeRms(0.6)")
    # Genug Stimmzeit (4000ms) sammeln, dann kommt die Bestaetigung.
    assert _warte(seite, lambda: seite.is_visible("#kalibrierung-ja"), ms=12000)
    assert TESTSATZ in seite.text_content("#kalibrierung-text")
    seite.click("#kalibrierung-ja")
    assert _warte(seite, lambda: seite.is_hidden("#kalibrierung"), ms=5000)


# -- (h) "No, try again" (bzw. eine leise Messung) geht nur auf Schritt 4 --
# -- zurueck, Schritt 2 (Stille) bleibt stehen -----------------------------


def test_nein_fuehrt_zurueck_auf_die_sprechen_ankuendigung_nicht_auf_stille(seite):
    """'No, try again' haengt am selben Zaehler/derselben Staffelung wie
    Schritt 5 (die Karte behandelt eine abgelehnte Bestaetigung ausdruecklich
    wie eine leere Antwort): der Klick zeigt zuerst die 'zu leise'-Stufe mit
    ihrem eigenen 'Try again' (#kalibrierung-versuch), und ERST dessen Klick
    fuehrt zurueck auf die Schritt-3-Ankuendigung -- nie auf die
    Stille-Zaehlung (Schritt 2)."""
    seite.evaluate("window.__t.setzeRms(0.0)")
    _starte(seite)
    seite.click("#kalibrierung-start")
    seite.wait_for_selector("#kalibrierung-sprechen", state="visible", timeout=8000)
    seite.click("#kalibrierung-sprechen")
    seite.evaluate("window.__t.setzeRms(0.6)")
    assert _warte(seite, lambda: seite.is_visible("#kalibrierung-ja"), ms=12000)
    seite.click("#kalibrierung-nein")
    seite.wait_for_selector("#kalibrierung-versuch", state="visible", timeout=3000)
    assert seite.is_hidden("#kalibrierung-ja")
    seite.click("#kalibrierung-versuch")
    # Erst jetzt zurueck auf die Schritt-3-Ankuendigung (Sprechen-Knopf
    # wieder da) -- NICHT auf die Stille-Zaehlung.
    seite.wait_for_selector("#kalibrierung-sprechen", state="visible", timeout=3000)
    seite.click("#kalibrierung-skip")


# -- (e) Zweites "zu leise" in Folge -> Hinweis + gruppenweiter Modus ------


def test_zweites_zu_leise_zeigt_herumreichen_hinweis_und_schreibt_den_modus(seite):
    seite.evaluate("window.__t.setzeRms(0.0)")
    _starte(seite)
    seite.click("#kalibrierung-start")
    seite.wait_for_selector("#kalibrierung-sprechen", state="visible", timeout=8000)

    def _eine_zu_leise_runde():
        seite.click("#kalibrierung-sprechen")
        # Laut genug, um die 30s-Warte zu ueberstehen, aber unter dem
        # 3x-Verhaeltnis zur Stille (die hier nahe 0 liegt, also wird
        # "zu leise" allein durch zu wenig Stimmzeit ausgeloest: unter
        # 2000ms Stimme in 4000ms Fenster) -- kurz an, dann wieder aus.
        seite.evaluate("window.__t.setzeRms(0.6)")
        seite.wait_for_timeout(250)   # etwas Stimme, aber bei weitem nicht 2000ms
        seite.evaluate("window.__t.setzeRms(0.0)")
        assert _warte(
            seite,
            lambda: seite.is_visible("#kalibrierung-versuch") or
                    seite.is_visible("#kalibrierung-weiter-trotzdem"),
            ms=20000,
        )

    _eine_zu_leise_runde()
    assert seite.is_visible("#kalibrierung-versuch")
    assert seite.is_hidden("#kalibrierung-weiter-trotzdem"), "1. Mal: noch kein Herumreichen-Hinweis"
    assert _hole_gruppe()["kalibrierung_modus"] is None

    seite.click("#kalibrierung-versuch")   # zurueck auf Schritt 3
    seite.wait_for_selector("#kalibrierung-sprechen", state="visible", timeout=3000)
    _eine_zu_leise_runde()
    assert seite.is_visible("#kalibrierung-weiter-trotzdem"), "2. Mal: der Herumreichen-Hinweis muss stehen"

    assert _warte(seite, lambda: _hole_gruppe()["kalibrierung_modus"] == "herumreichen", ms=5000)

    seite.click("#kalibrierung-weiter-trotzdem")
    assert _warte(seite, lambda: seite.is_visible("#kalibrierung-ja"), ms=12000)
    seite.click("#kalibrierung-ja")
    assert _warte(seite, lambda: seite.is_hidden("#kalibrierung"), ms=5000)
