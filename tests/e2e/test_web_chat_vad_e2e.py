"""Der Pausen-Schnitt (VAD) im echten Browser, mit gefaelschtem Pegel.

Eigene Datei statt ein paar Tests in ``test_web_chat_e2e.py``: dort braucht
jeder bestehende Test ``IT_WEB_VAD_MAX_MS`` auf derselben kurzen Zahl wie
``IT_WEB_SEGMENT_MS`` (Chromiums synthetischer Ton ist ein Dauerton und
schneidet sonst gar nicht innerhalb der dortigen 8-10 s Testgeduld, siehe
Kommentar an der ``server``-Fixture dort) -- das verdeckt genau den Pausen-
gegen-Zeitdeckel-Unterschied, den dieser Lauf braucht. Hier steht deshalb
``IT_WEB_VAD_PAUSE_MS`` klein und ``IT_WEB_VAD_MAX_MS`` gross, mit eigenem
Server/Port/DB.

``_MESSUNG`` (aus ``test_web_chat_e2e``) ueberschreibt
``getFloatTimeDomainData``/``getByteFrequencyData`` auf dem echten
AnalyserNode mit einem konstanten, per ``window.__t.setzeRms(x)`` steuerbaren
Pegel -- Chromiums eigener synthetischer Ton bleibt unberuehrt (die Spur
laeuft weiter in den echten MediaRecorder), nur die VAD-Messung liest den
gefaelschten Wert.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_chat_vad_e2e.py -q

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

from interview_theater import db, repo, web_kanal  # noqa: E402
from tests.e2e.test_web_chat_e2e import BotAttrappe, _MESSUNG  # noqa: E402

DB_PFAD = "/tmp/it-webchat-vad.db"
AUDIO = "/tmp/it-webchat-vad-audio"
SERVERLOG = "/tmp/it-webchat-vad-server.log"
CHAT = 7_000_000_000_002
HANDY = {"width": 390, "height": 844}
GEDULD = 8000

#: Klein, damit ein Test nicht minutenlang laeuft -- im Betrieb 2500/90000
#: (``einstellungen``-freie Vorgaben in ``web_chat._vad_werte``).
PAUSE_MS = 700
MAX_MS = 6000
MIN_SPEECH_MS = 200


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


def _zaehle_sprachnachrichten() -> int:
    conn = db.verbinde(DB_PFAD)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM web_post WHERE chat_id = ? AND typ = 'sprache'",
            (CHAT,),
        ).fetchone()[0]
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
        "IT_WEB_VAD_PAUSE_MS": str(PAUSE_MS),
        "IT_WEB_VAD_MAX_MS": str(MAX_MS),
        "IT_WEB_VAD_MIN_SPEECH_MS": str(MIN_SPEECH_MS),
        # Task 2 (Kanban-Karte Mithoeren SICHER/Kalibrierung, 03.10.2026):
        # dieser Lauf prueft die Pausen-Schnitt-Entscheidung selbst, nicht
        # die Kalibrierung davor -- ohne den Schalter wuerde jeder
        # _starte() hier auf einen nie gedrueckten Kalibrierungs-Knopf
        # warten und pegelAn() nie anlaufen.
        "IT_WEB_VAD_KALIBRIERUNG": "0",
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
    attrappe = BotAttrappe()
    # Die Attrappe liest aus einer eigenen Verbindung gegen DB_PFAD -- sie
    # ist in test_web_chat_e2e.py an das dortige Modul-DB_PFAD gebunden, hier
    # wird sie deshalb NICHT importiert fuer den Thread, sondern nachgebaut:
    # gleiches Verhalten (/interview -> an, /fertig -> aus), eigene DB.
    attrappe.ende = threading.Event()
    attrappe.aktiv = True
    attrappe.letzte = 0

    def run():
        conn = db.verbinde(DB_PFAD)
        try:
            while not attrappe.ende.is_set():
                if attrappe.aktiv:
                    zeilen = conn.execute(
                        "SELECT id, text FROM web_post WHERE chat_id = ? "
                        "AND typ = 'befehl' AND id > ? ORDER BY id",
                        (CHAT, attrappe.letzte),
                    ).fetchall()
                    for zeile in zeilen:
                        setze_modus(zeile["text"] == "/interview")
                        attrappe.letzte = zeile["id"]
                time.sleep(0.05)
        finally:
            conn.close()

    faden = threading.Thread(target=run, daemon=True)
    faden.start()
    yield attrappe
    attrappe.ende.set()
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
    kontext = browser.new_context(
        viewport=HANDY, permissions=["microphone"], base_url=BASIS,
        is_mobile=True, has_touch=True,
    )
    kontext.add_init_script(_MESSUNG)
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


def test_pause_schneidet_nach_der_pausenschwelle(seite):
    """Rede, dann Stille laenger als PAUSE_MS -> ein Segment geht raus, auch
    ohne dass der harte Zeitdeckel (MAX_MS, hier viel groesser) je erreicht
    wird."""
    seite.evaluate("window.__t.setzeRms(0.6)")
    vorher = _zaehle_sprachnachrichten()
    _starte(seite)
    seite.wait_for_timeout(MIN_SPEECH_MS + 300)   # genug Rede fuer MIN_SPEECH_MS
    seite.evaluate("window.__t.setzeRms(0.0)")
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher,
                  ms=PAUSE_MS + 3000)


def test_keine_pause_unter_der_schwelle_schneidet_noch_nicht(seite):
    """Eine Stille knapp UNTER PAUSE_MS schneidet noch nicht."""
    seite.evaluate("window.__t.setzeRms(0.6)")
    vorher = _zaehle_sprachnachrichten()
    _starte(seite)
    seite.wait_for_timeout(MIN_SPEECH_MS + 300)
    seite.evaluate("window.__t.setzeRms(0.0)")
    seite.wait_for_timeout(PAUSE_MS - 300)
    assert _zaehle_sprachnachrichten() == vorher
    seite.click("#interview-beenden")   # raeumt auf, zaehlt hier nicht mit


def test_harter_zeitdeckel_schneidet_auch_ohne_pause(seite):
    """Durchgehende Rede ohne jede Pause -> der Zeitdeckel MAX_MS schneidet
    trotzdem."""
    seite.evaluate("window.__t.setzeRms(0.6)")
    vorher = _zaehle_sprachnachrichten()
    _starte(seite)
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher,
                  ms=MAX_MS + 3000)
    seite.click("#interview-beenden")


def test_zu_kurze_rede_wird_nicht_einzeln_gesendet(seite):
    """Unter MIN_SPEECH_MS Rede vor einer Pause wird NICHT als eigenes
    Segment gesendet -- der Recorder laeuft weiter, bis genug Rede da war
    (Aufzeichnung ueber die erste Pause hinweg, kein zweites
    MediaRecorder-Segment)."""
    vorher = _zaehle_sprachnachrichten()
    starts_vorher = None
    seite.evaluate("window.__t.setzeRms(0.6)")
    _starte(seite)
    starts_vorher = seite.evaluate("window.__t.starts")
    seite.wait_for_timeout(100)   # deutlich unter MIN_SPEECH_MS
    seite.evaluate("window.__t.setzeRms(0.0)")
    seite.wait_for_timeout(PAUSE_MS + 300)
    # Keine Pause-Entscheidung hat geschnitten: kein zweiter Recorder-Start.
    assert seite.evaluate("window.__t.starts") == starts_vorher
    assert _zaehle_sprachnachrichten() == vorher
    # Jetzt genug Rede -> die naechste echte Pause schneidet doch.
    seite.evaluate("window.__t.setzeRms(0.6)")
    seite.wait_for_timeout(MIN_SPEECH_MS + 300)
    seite.evaluate("window.__t.setzeRms(0.0)")
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher,
                  ms=PAUSE_MS + 3000)
    seite.click("#interview-beenden")


def test_adaptiver_boden_erkennt_pause_bei_erhoehtem_rauschen(seite):
    """Eine Pause bei erhoehtem, aber konstantem Umgebungsrauschen (0.03
    statt echter Stille) schneidet trotzdem -- der Rauschboden ist das
    niedrige Perzentil ALLER Werte im Fenster (keine Vorbedingung), nur mit
    einem Deckel (``BODEN_DECKEL_FAKTOR``) gegen eine durchgehend laute
    Aufnahme, die sonst die Schwelle auf ihre eigene Lautstaerke zieht (siehe
    Kommentar an ``pegelAn`` in web_chat.py). Eine kurze Rauschphase vor der
    Rede lässt den Boden zuerst auf das Rauschen und nicht auf eine leere
    Anfangsschaetzung absinken."""
    RAUSCHEN = 0.03
    seite.evaluate(f"window.__t.setzeRms({RAUSCHEN})")
    vorher = _zaehle_sprachnachrichten()
    _starte(seite)
    seite.wait_for_timeout(600)   # Boden sieht das Rauschen vor der Rede
    seite.evaluate("window.__t.setzeRms(0.6)")
    seite.wait_for_timeout(MIN_SPEECH_MS + 300)
    seite.evaluate(f"window.__t.setzeRms({RAUSCHEN})")   # "Pause": Rauschen, nicht Stille
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher,
                  ms=PAUSE_MS + 3000)
    seite.click("#interview-beenden")
