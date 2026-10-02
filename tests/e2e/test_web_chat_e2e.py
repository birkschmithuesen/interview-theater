"""Der Chat im echten Browser -- geklickt und gehalten, nicht simuliert.

Was dieser Lauf leistet, was ``tests/test_web_chat_*.py`` nicht leisten: den
MediaRecorder, die Segmente, die Warteschlange, ``setPointerCapture`` und die
Frage, ob ein zu kurzer Druck wirklich NICHTS sendet.

Kein Bot laeuft dabei mit: geprueft wird die Browserseite gegen den
Webserver. Was der Bot daraus macht, prueft ``tests/test_web_e2e_http.py``.
Eine Stelle braucht trotzdem einen Bot: ein Interviewsegment geht erst raus,
wenn der Poll den Interviewmodus meldet (Entscheidung I, ``bereit()`` in
``web_chat._CHAT_JS``). Den Modus setzt hier die ``BotAttrappe`` -- ein
Thread, der ``/interview`` und ``/fertig`` aus ``web_post`` liest und
``repo.setze_interviewmodus`` ruft, sonst nichts.

Die Mikrofonseite ist echt (Chromium mit ``--use-fake-device-for-media-stream``,
echter MediaRecorder). Ein Init-Skript (``_MESSUNG``) legt nur eine duenne
Schicht darum: es zaehlt Recorder-Starts und Blob-Groessen, kann das
``stop``-Ereignis eines Recorders verzoegern, ``getUserMedia`` bremsen und
einen Audio-Upload festhalten -- die Faelle, die mit echtem Timing nicht
zuverlaessig eintreten.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_chat_e2e.py -q

Im normalen ``pytest``-Lauf wird die Datei uebersprungen (``importorskip``).
"""

import json
import os
import re
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
from playwright.sync_api import expect, sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo, web_chat, web_kanal  # noqa: E402

DB_PFAD = "/tmp/it-webchat.db"
AUDIO = "/tmp/it-webchat-audio"
SERVERLOG = "/tmp/it-webchat-server.log"


def _freier_port() -> int:
    """Ein freier Port, vom Betriebssystem vergeben. Ein fester Port liesse
    einen Altserver aus einem abgebrochenen Lauf ``/gesund`` beantworten --
    der Test liefe dann gegen dessen Datenbank."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


BIND = f"127.0.0.1:{_freier_port()}"
BASIS = f"http://{BIND}"
PRAEFIX = "/theatersoap"
CHAT = 7_000_000_000_001

#: Kurz, damit ein Lauf nicht Minuten dauert -- im Betrieb sind es 45 s
#: (``einstellungen.VORGABE_SEGMENT_MS``).
SEGMENT_MS = 1200

#: Wohin der Handy-Screenshot geht. Committet, weil Birk ihn ansieht -- und
#: er zeigt ausschliesslich erfundene Fixture-Daten.
SCHUSS = WURZEL / "docs" / "web-chat" / "handy-2026-09-30.png"

#: Jeder Lauf schreibt den Schuss hierhin; ins Repository (``SCHUSS``) nur
#: mit ``IT_SCHUSS_AKTUALISIEREN=1`` -- sonst waere der Arbeitsbaum nach
#: jedem Lauf schmutzig.
SCHUSS_TMP = Path("/tmp/it-webchat-shots/handy-2026-09-30.png")

#: iPhone-13-Groesse. Mobile zuerst.
HANDY = {"width": 390, "height": 844}

GEDULD = 8000

#: Die message_ids der Fixture-Nachrichten (fuer die Aenderungsfaelle).
IDS: dict = {}


# -- Messschicht im Browser ----------------------------------------------

#: Liegt unter der Seite (``add_init_script``), bevor ``_CHAT_JS`` laeuft.
#: Ohne Eingriff verhaelt sich alles wie im echten Browser; die Tests
#: schalten ueber ``window.__t`` gezielt Verzoegerungen ein.
_MESSUNG = r"""
(function () {
  var T = window.__t = {
    starts: 0, groessen: {}, stroeme: [], kontexte: [],
    stopVerzoegerung: {},   // je Recorder-Index: Millisekunden
    stopVerzoegerungAlle: 0,
    gumVerzoegerung: 0,
    halteAudio: false, gehalten: [],
    posts: []
  };

  var EchterRecorder = window.MediaRecorder;
  if (EchterRecorder) {
    var Attrappe = function (strom, optionen) {
      var r = optionen ? new EchterRecorder(strom, optionen) : new EchterRecorder(strom);
      var selbst = this;
      var index = null;
      this.ondataavailable = null;
      this.onstop = null;
      r.addEventListener('dataavailable', function (ev) {
        if (index !== null) {
          T.groessen[index] = (T.groessen[index] || 0) + (ev.data ? ev.data.size : 0);
        }
        if (selbst.ondataavailable) { selbst.ondataavailable(ev); }
      });
      r.addEventListener('stop', function (ev) {
        var ms = T.stopVerzoegerung[index] || T.stopVerzoegerungAlle || 0;
        var feuere = function () { if (selbst.onstop) { selbst.onstop(ev); } };
        if (ms) { setTimeout(feuere, ms); } else { feuere(); }
      });
      this.start = function () { index = T.starts; T.starts += 1; return r.start(); };
      this.stop = function () { return r.stop(); };
      Object.defineProperty(this, 'state', { get: function () { return r.state; } });
      Object.defineProperty(this, 'mimeType', { get: function () { return r.mimeType; } });
    };
    window.MediaRecorder = Attrappe;
  }

  var geraete = navigator.mediaDevices;
  if (geraete && geraete.getUserMedia) {
    var echtGum = geraete.getUserMedia.bind(geraete);
    geraete.getUserMedia = function (vorgabe) {
      return echtGum(vorgabe).then(function (strom) {
        T.stroeme.push(strom);
        var ms = T.gumVerzoegerung;
        if (!ms) { return strom; }
        return new Promise(function (ja) { setTimeout(function () { ja(strom); }, ms); });
      });
    };
  }

  var EchterKontext = window.AudioContext;
  if (EchterKontext) {
    window.AudioContext = function () {
      var k = new EchterKontext();
      T.kontexte.push(k);
      return k;
    };
  }

  var echtFetch = window.fetch.bind(window);
  window.fetch = function (url, optionen) {
    var u = String(url);
    if (optionen && optionen.method === 'POST') {
      var pfad = u.split('?')[0];
      var eintrag = { pfad: pfad.slice(pfad.lastIndexOf('/chat/') + 6) };
      if (typeof optionen.body === 'string') {
        try { eintrag.an = JSON.parse(optionen.body).an; } catch (e) { /* egal */ }
      } else if (optionen.body && optionen.body.size !== undefined) {
        eintrag.groesse = optionen.body.size;
      }
      T.posts.push(eintrag);
      if (eintrag.pfad === 'audio' && T.halteAudio) {
        return new Promise(function (ja) {
          T.gehalten.push(function (status) {
            ja(new Response('festgehalten', { status: status }));
          });
        });
      }
    }
    return echtFetch(url, optionen);
  };
})();
"""


# -- Datenbank, Server, Bot-Attrappe ---------------------------------------

def _baue_datenbank() -> str:
    """Eine Web-Gruppe in Phase 3 mit einer Leiste im Chat.

    Aufgebaut ueber ``repo`` und ``WebKanal`` -- so steht am Ende genau das
    da, was im Betrieb entsteht. Alles Material ist frei erfunden."""
    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    shutil.rmtree(AUDIO, ignore_errors=True)

    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 3)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Ankommen, Arbeit, Nacht")
    repo.setze_arbeitsstand(
        conn, CHAT, "fragen",
        "Was war in deinem Koffer?\nWer hat auf dich gewartet?",
    )
    repo.setze_arbeitsstand(
        conn, CHAT, "interview_eroeffnung",
        "Hallo, wir machen ein Theaterstueck und sammeln Geschichten.",
    )
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Danke fuer die Zeit.")

    kanal = web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01)
    IDS["begriffe"] = kanal.sende(CHAT, "Eure Begriffe habe ich. Womit fangen wir an?")
    knopf_id = repo.lege_knopf_an(conn, CHAT, "stand", None)
    IDS["leitfaden"] = kanal.sende_mit_knoepfen(
        CHAT, "Der Leitfaden steht. Wollt ihr ihn sehen?",
        [("Stand zeigen", f"k:{knopf_id}")],
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


class BotAttrappe(threading.Thread):
    """Spielt vom Bot genau das, was der Umschalter braucht: ``/interview``
    setzt den Modus, ``/fertig`` nimmt ihn zurueck. Mit ``aktiv = False``
    bleibt der Eingang liegen (der Bot "haengt") und wird beim Wiederanlaufen
    der Reihe nach abgearbeitet."""

    def __init__(self):
        super().__init__(daemon=True)
        self.aktiv = True
        self.ende = threading.Event()
        self.letzte = 0

    def run(self):
        conn = db.verbinde(DB_PFAD)
        try:
            while not self.ende.is_set():
                if self.aktiv:
                    self.arbeite(conn)
                time.sleep(0.05)
        finally:
            conn.close()

    def arbeite(self, conn):
        zeilen = conn.execute(
            "SELECT id, text FROM web_post WHERE chat_id = ? AND typ = 'befehl' "
            "AND id > ? ORDER BY id",
            (CHAT, self.letzte),
        ).fetchall()
        for zeile in zeilen:
            an = zeile["text"] == web_chat.BEFEHL_INTERVIEW_AN
            setze_modus(an, conn)
            self.letzte = zeile["id"]

    def offen(self) -> int:
        conn = db.verbinde(DB_PFAD)
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM web_post WHERE chat_id = ? AND typ = 'befehl' "
                "AND id > ?", (CHAT, self.letzte),
            ).fetchone()[0]
        finally:
            conn.close()


def setze_modus(an: bool, conn=None) -> None:
    """Der Interviewmodus, wie ihn der Bot setzt (oder ein zweites Telefon
    beendet)."""
    eigene = conn is None
    if eigene:
        conn = db.verbinde(DB_PFAD)
    try:
        repo.setze_interviewmodus(
            conn, CHAT, time.strftime("%Y-%m-%dT%H:%M:%S") if an else None,
        )
    finally:
        if eigene:
            conn.close()


def _modus_an() -> bool:
    conn = db.verbinde(DB_PFAD)
    try:
        return repo.ist_interviewmodus_an(conn, CHAT)
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
        "IT_AUDIO": AUDIO, "IT_WEB_SEGMENT_MS": str(SEGMENT_MS),
        "PYTHONPATH": str(WURZEL),
    })
    # In eine Datei, nicht in eine Pipe: der Server schreibt je Anfrage eine
    # Logzeile, und eine Pipe, die niemand liest, ist nach 64 KiB voll --
    # danach haengt der Server mitten im Lauf.
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
    attrappe.start()
    yield attrappe
    attrappe.ende.set()
    attrappe.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch(args=[
            # Ein Mikrofon ohne Rueckfrage, und ein synthetischer Ton darin.
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
        ])
        yield chromium
        chromium.close()


@pytest.fixture
def oeffne(server, bot, browser, token):
    """Oeffnet die Chatseite in einem frischen Handy-Kontext. Vorher: der Bot
    laeuft, der Eingang ist abgearbeitet, der Modus ist aus."""
    bot.aktiv = True
    ende = time.time() + 5
    while bot.offen() and time.time() < ende:
        time.sleep(0.05)
    setze_modus(False)
    kontexte = []

    def _oeffne(pfad: str | None = None, vorher=None):
        kontext = browser.new_context(
            viewport=HANDY, permissions=["microphone"],
            base_url=BASIS, is_mobile=True, has_touch=True,
        )
        kontext.add_init_script(_MESSUNG)
        kontexte.append(kontext)
        blatt = kontext.new_page()
        blatt.set_default_timeout(GEDULD)
        if vorher:
            vorher(blatt)
        blatt.goto(f"{BASIS}{pfad or f'/g/{token}/chat'}")
        return blatt

    yield _oeffne
    for kontext in kontexte:
        kontext.close()
    bot.aktiv = True


@pytest.fixture
def seite(oeffne):
    return oeffne()


# -- Hilfen ------------------------------------------------------------------

def _zaehle(typ: str) -> int:
    conn = db.verbinde(DB_PFAD)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM web_post WHERE chat_id = ? AND typ = ?",
            (CHAT, typ),
        ).fetchone()[0]
    finally:
        conn.close()


def _zaehle_sprachnachrichten() -> int:
    return _zaehle("sprache")


def _warte(seite, bedingung, ms: int = GEDULD, schritt: int = 100) -> bool:
    """Wartet, bis ``bedingung()`` wahr ist -- ueber ``wait_for_timeout``,
    damit Playwright dazwischen seine Ereignisse (Routen) abarbeitet."""
    ende = time.time() + ms / 1000
    while time.time() < ende:
        if bedingung():
            return True
        seite.wait_for_timeout(schritt)
    return bedingung()


def _t(seite, ausdruck: str):
    return seite.evaluate(f"window.__t.{ausdruck}")


def _posts(seite) -> list:
    return seite.evaluate("window.__t.posts")


def _form(posts) -> list:
    """Die POSTs der Schlange als kurze Folge: ``an``, ``aus``, ``audio``."""
    folge = []
    for p in posts:
        if p["pfad"] == "interview":
            folge.append("an" if p.get("an") else "aus")
        elif p["pfad"] == "audio":
            folge.append("audio")
    return folge


def _halte_ptt(seite, ms: int) -> None:
    seite.locator("#ptt").hover()
    seite.mouse.down()
    seite.wait_for_timeout(ms)
    seite.mouse.up()


def _starte_interview(seite) -> None:
    seite.click("#interview")
    expect(seite.locator("#interview")).to_have_attribute("data-laeuft", "1")


# -- Verlauf, Text, Knoepfe ----------------------------------------------------

def test_der_verlauf_steht_da(seite):
    expect(seite.locator(".blase.bot").first).to_contain_text("Eure Begriffe")
    # Die vereinte Seite rendert das Textbuch-Panel mit, auch verborgen --
    # und das traegt seine eigene ".leiste" (Rollenfilter, Schriftgroesse).
    # Gemeint ist die Knopfleiste der Chat-Nachricht.
    expect(seite.locator("#tab-chat .leiste button")).to_have_count(1)


def test_text_senden_erscheint_im_verlauf(seite):
    seite.fill("#eingabe", "Wir fangen mit Ankommen an.")
    seite.click("#senden")
    expect(seite.locator(".blase.gruppe").last).to_contain_text("Ankommen")


def test_handy_screenshot(seite):
    """Der Artefakt-Schuss: die Handy-Ansicht mit Knopfleiste und
    Aufnahme-Knopf. Nur erfundene Fixture-Daten. Steht frueh in der Datei,
    damit der Verlauf noch nicht voller Testnachrichten ist."""
    seite.fill("#eingabe", "")
    expect(seite.locator(".leiste button").first).to_be_visible()
    expect(seite.locator("#interview")).to_be_visible()
    expect(seite.locator("#ptt")).to_be_visible()
    seite.wait_for_timeout(300)
    SCHUSS_TMP.parent.mkdir(parents=True, exist_ok=True)
    seite.screenshot(path=str(SCHUSS_TMP), full_page=False)
    assert SCHUSS_TMP.stat().st_size > 5000
    if os.environ.get("IT_SCHUSS_AKTUALISIEREN") == "1":
        SCHUSS.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SCHUSS_TMP, SCHUSS)


def test_knopf_klicken_legt_einen_druck_an(seite):
    vorher = _zaehle("knopf")
    seite.click(".leiste button")
    assert _warte(seite, lambda: _zaehle("knopf") > vorher)
    assert _zaehle("knopf") == vorher + 1
    # Der Knopf ist danach aus: ein benutzter Knopf, der weiter klickbar
    # dasteht, laedt zum zweiten Druck ein.
    expect(seite.locator(".leiste button").first).to_be_disabled()


def test_aenderungen_des_bots_kommen_ohne_neuladen_an(seite):
    """B10: Text getauscht, Leiste weg, Nachricht geloescht -- per Poll."""
    conn = db.verbinde(DB_PFAD)
    try:
        kanal = web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01)
        weg_id = kanal.sende(CHAT, "Diese Zeile verschwindet gleich.")
        expect(seite.locator(f'.blase[data-id="{weg_id}"]')).to_be_visible()
        repo.aendere_web_text(conn, CHAT, IDS["begriffe"], "Begriffe stehen: drei Stueck.")
        repo.setze_web_knoepfe(conn, CHAT, IDS["leitfaden"], None)
        repo.loesche_web_posts(conn, CHAT, [weg_id])
    finally:
        conn.close()
    expect(seite.locator(f'.blase[data-id="{IDS["begriffe"]}"]')).to_contain_text(
        "drei Stueck")
    expect(seite.locator(f'.leiste[data-message="{IDS["leitfaden"]}"]')).to_have_count(0)
    expect(seite.locator(f'.blase[data-id="{weg_id}"]')).to_have_count(0)


# -- Push-to-Talk ----------------------------------------------------------------

def test_ptt_unter_einer_halben_sekunde_sendet_nichts(seite):
    """Der Recorder laeuft wirklich, bevor losgelassen wird -- sonst griffe
    der Weg "losgelassen vor getUserMedia" (B5), und die Sperre
    ``druck.dauerMs < PTT_MIN_MS`` liefe nie."""
    vorher = _zaehle_sprachnachrichten()
    # Mikrofon aufwaermen: der erste getUserMedia eines Kontexts ist langsam.
    seite.evaluate("""navigator.mediaDevices.getUserMedia({audio: true}).then(
      function (s) { s.getTracks().forEach(function (t) { t.stop(); }); })""")
    seite.locator("#ptt").hover()
    beginn = time.time()
    seite.mouse.down()
    assert _warte(seite, lambda: _t(seite, "starts") == 1, ms=400, schritt=20)
    gehalten = time.time() - beginn
    seite.wait_for_timeout(max(0, int((0.3 - gehalten) * 1000)))
    seite.mouse.up()
    assert time.time() - beginn <= 0.45     # deutlich unter PTT_MIN_MS
    seite.wait_for_timeout(2500)
    assert _zaehle_sprachnachrichten() == vorher
    assert _form(_posts(seite)) == []


def test_ptt_mit_pointercancel_sendet_nichts(seite):
    """Wegziehen oder ein Systemdialog: der Druck gilt als abgebrochen."""
    vorher = _zaehle_sprachnachrichten()
    seite.locator("#ptt").hover()
    seite.mouse.down()
    seite.wait_for_timeout(1200)
    assert _t(seite, "starts") == 1      # es lief wirklich ein Recorder
    seite.evaluate("""
      document.getElementById('ptt').dispatchEvent(
        new PointerEvent('pointercancel', { bubbles: true, pointerId: 1 }));
    """)
    seite.mouse.up()
    seite.wait_for_timeout(2500)
    assert _zaehle_sprachnachrichten() == vorher
    assert _form(_posts(seite)) == []


def test_ptt_wegziehen_und_aussen_loslassen_sendet_nichts(seite):
    """B7: mit setPointerCapture kommt das Loslassen neben dem Knopf beim
    Knopf an -- und gilt als abgebrochen."""
    vorher = _zaehle_sprachnachrichten()
    knopf = seite.locator("#ptt")
    knopf.hover()
    seite.mouse.down()
    seite.wait_for_timeout(400)
    rahmen = knopf.bounding_box()
    seite.mouse.move(rahmen["x"] - 120, rahmen["y"] - 200, steps=5)
    expect(knopf).to_have_attribute("data-weg", "1")
    seite.wait_for_timeout(800)
    seite.mouse.up()
    seite.wait_for_timeout(2500)
    assert _zaehle_sprachnachrichten() == vorher
    assert _form(_posts(seite)) == []


def test_ptt_ueber_einer_halben_sekunde_sendet_genau_eines(seite):
    """B7, Gegenprobe: >= 500 ms innen gehalten -> genau ein Upload, und
    KEIN /interview (PTT schaltet den Modus nicht)."""
    vorher = _zaehle_sprachnachrichten()
    befehle = _zaehle("befehl")
    _halte_ptt(seite, 1500)
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher)
    seite.wait_for_timeout(1000)
    assert _zaehle_sprachnachrichten() == vorher + 1
    assert _zaehle("befehl") == befehle
    assert _form(_posts(seite)) == ["audio"]


def test_zwei_schnelle_druecke_senden_zwei(seite):
    """B6: der zweite Druck kommt, waehrend der erste noch abschliesst --
    jeder wird nach seiner eigenen Haltezeit bewertet."""
    vorher = _zaehle_sprachnachrichten()
    _halte_ptt(seite, 800)
    _halte_ptt(seite, 800)
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() >= vorher + 2)
    seite.wait_for_timeout(800)
    assert _zaehle_sprachnachrichten() == vorher + 2


def test_ptt_losgelassen_bevor_das_mikrofon_da_ist(seite):
    """B5: kein Recorder, das Mikrofon sofort wieder zu, nichts gesendet."""
    seite.evaluate("window.__t.gumVerzoegerung = 2000")
    _halte_ptt(seite, 800)
    seite.wait_for_timeout(3000)
    assert _t(seite, "starts") == 0
    assert _form(_posts(seite)) == []
    assert seite.evaluate(
        "window.__t.stroeme.length === 1 && window.__t.stroeme[0].getTracks()"
        ".every(function (t) { return t.readyState === 'ended'; })"
    )


# -- Upload-Fehler -------------------------------------------------------------

_AUDIO_ROUTE = re.compile(r".*/chat/audio\?.*")


def test_upload_503_wird_wiederholt_bis_er_ankommt(seite):
    """B3: zweimal 503 -> das Stueck bleibt in der Schlange, der Hinweis
    steht da, und danach kommt es an."""
    vorher = _zaehle_sprachnachrichten()
    versuche = []

    def route(r):
        versuche.append(1)
        if len(versuche) <= 2:
            r.fulfill(status=503, body="kaputt")
        else:
            r.continue_()

    seite.route(_AUDIO_ROUTE, route)
    _halte_ptt(seite, 900)
    expect(seite.locator("#warteschlange")).to_contain_text("Keine Verbindung")
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher, ms=15000)
    assert len(versuche) == 3
    assert _zaehle_sprachnachrichten() == vorher + 1
    expect(seite.locator("#warteschlange")).to_have_text("")


def test_upload_netzabbruch_wird_wiederholt(seite):
    vorher = _zaehle_sprachnachrichten()
    versuche = []

    def route(r):
        versuche.append(1)
        if len(versuche) <= 1:
            r.abort("connectionreset")
        else:
            r.continue_()

    seite.route(_AUDIO_ROUTE, route)
    _halte_ptt(seite, 900)
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher, ms=15000)
    assert _zaehle_sprachnachrichten() == vorher + 1


def test_upload_403_mehrfach_holt_den_nonce_und_kommt_an(seite):
    """B2/C: 403 -> Zustand holen, zweiter Versuch; scheitert auch der,
    zaehlt es wie ein Netzfehler und das Stueck bleibt."""
    vorher = _zaehle_sprachnachrichten()
    versuche = []
    polls = []
    seite.on("request", lambda a: polls.append(a.url) if "/chat/zustand" in a.url else None)

    def route(r):
        versuche.append(len(polls))
        if len(versuche) <= 3:
            r.fulfill(status=403, body=web_chat._TEXT_FEHLER_VERALTET)
        else:
            r.continue_()

    seite.route(_AUDIO_ROUTE, route)
    _halte_ptt(seite, 900)
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher, ms=15000)
    assert len(versuche) == 4
    assert _zaehle_sprachnachrichten() == vorher + 1
    # Zwischen dem ersten 403 und dem zweiten Versuch lag ein Zustands-Poll.
    assert versuche[1] > versuche[0]


def test_upload_400_wird_verworfen_und_gemeldet(seite):
    vorher = _zaehle_sprachnachrichten()
    versuche = []

    def route(r):
        versuche.append(1)
        r.fulfill(status=400, body=web_chat._TEXT_FEHLER_DAUER,
                  content_type="text/plain; charset=utf-8")

    seite.route(_AUDIO_ROUTE, route)
    _halte_ptt(seite, 900)
    expect(seite.locator("#fehler")).to_be_visible()
    expect(seite.locator("#fehler")).to_contain_text(web_chat._TEXT_FEHLER_DAUER)
    seite.wait_for_timeout(2500)
    assert len(versuche) == 1           # kein zweiter Versuch
    assert _zaehle_sprachnachrichten() == vorher
    expect(seite.locator("#warteschlange")).to_have_text("")


# -- Der Interview-Umschalter -----------------------------------------------------

def test_der_umschalter_erzeugt_mindestens_zwei_segmente(seite):
    """Birks Abnahme: Umschalter an/aus erzeugt ein Interview mit >= 2
    Segmenten. Die Segmentlaenge ist im Test auf SEGMENT_MS verkuerzt."""
    vorher = _zaehle_sprachnachrichten()
    befehle = _zaehle("befehl")
    _starte_interview(seite)
    expect(seite.locator("#uhr")).to_be_visible()
    # Zwei Segmentgrenzen ueberschreiten, plus Luft fuer den Upload.
    seite.wait_for_timeout(SEGMENT_MS * 2 + 1500)
    seite.click("#interview")
    assert _warte(seite, lambda: _zaehle("befehl") >= befehle + 2, ms=15000)
    assert _zaehle_sprachnachrichten() >= vorher + 2
    expect(seite.locator("#interview")).to_have_attribute("data-laeuft", "0")
    expect(seite.locator("#interview")).to_be_enabled()
    folge = _form(_posts(seite))
    assert folge[0] == "an" and folge[-1] == "aus"
    assert folge.count("audio") >= 2


def test_stopp_mitten_im_segment_fertig_kommt_zuletzt(seite):
    """B1 + B8: Stopp, waehrend ein Segment laeuft, und dessen stop-Ereignis
    kommt spaet -- trotzdem /interview, ALLE Segmente, dann /fertig. Danach
    sind Mikrofon und AudioContext zu."""
    _starte_interview(seite)
    assert _warte(seite, lambda: _t(seite, "starts") >= 2)
    seite.wait_for_timeout(300)
    seite.evaluate("window.__t.stopVerzoegerungAlle = 1500")
    seite.click("#interview")
    expect(seite.locator("#interview")).to_be_disabled()   # Stopp unterwegs
    assert _warte(seite, lambda: "aus" in _form(_posts(seite)), ms=15000)
    starts = _t(seite, "starts")
    groessen = seite.evaluate("window.__t.groessen")
    mit_daten = [i for i in range(starts) if groessen.get(str(i), 0) > 0]
    assert _form(_posts(seite)) == ["an"] + ["audio"] * len(mit_daten) + ["aus"]
    assert len(mit_daten) == starts      # das letzte Segment ist dabei
    expect(seite.locator("#interview")).to_be_enabled()
    assert _warte(seite, lambda: seite.evaluate(
        "window.__t.stroeme.every(function (s) { return s.getTracks().every("
        "function (t) { return t.readyState === 'ended'; }); })"))
    assert seite.evaluate(
        "window.__t.kontexte.every(function (k) { return k.state === 'closed'; })")


def test_segmente_bleiben_in_aufnahmereihenfolge(seite):
    """Re-Review B: das stop-Ereignis von Segment 0 kommt NACH dem von
    Segment 1 -- hochgeladen wird trotzdem 0, 1, dann /fertig."""
    seite.evaluate("window.__t.stopVerzoegerung[0] = 2500")
    _starte_interview(seite)
    assert _warte(seite, lambda: _t(seite, "starts") >= 2)
    seite.wait_for_timeout(400)
    seite.click("#interview")
    assert _warte(seite, lambda: "aus" in _form(_posts(seite)), ms=15000)
    groessen = seite.evaluate("window.__t.groessen")
    audio = [p["groesse"] for p in _posts(seite) if p["pfad"] == "audio"]
    assert audio == [groessen["0"], groessen["1"]]
    assert _form(_posts(seite)) == ["an", "audio", "audio", "aus"]


def test_segmente_warten_bis_der_bot_den_modus_meldet(seite, bot):
    """Entscheidung I / A' / B4: solange der Poll keinen Modus meldet, geht
    kein Segment raus, der Knopf bleibt auf 'Aufnahme beenden', es laeuft
    genau ein Recorder zur Zeit. Laeuft der Bot an, kommt alles nach."""
    bot.aktiv = False
    vorher = _zaehle_sprachnachrichten()
    _starte_interview(seite)
    seite.wait_for_timeout(SEGMENT_MS + 2500)   # mindestens ein Segment fertig, Polls mit "aus"
    expect(seite.locator("#interview")).to_have_attribute("data-laeuft", "1")
    expect(seite.locator("#interview")).to_have_text(web_chat._TEXT_INTERVIEW_AUS)
    expect(seite.locator("#warteschlange")).to_contain_text("warten, bis der Bot")
    assert _form(_posts(seite)) == ["an"]
    assert _zaehle_sprachnachrichten() == vorher
    bot.aktiv = True
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher, ms=10000)
    seite.click("#interview")
    assert _warte(seite, lambda: not _modus_an() and "aus" in _form(_posts(seite)),
                  ms=15000)
    expect(seite.locator("#interview")).to_have_attribute("data-laeuft", "0")


def test_waehrend_der_aufnahme_ist_ptt_weg(seite):
    """Zwei Mikrofone gleichzeitig sind keine Bedienung (Birk, Punkt 2)."""
    seite.click("#interview")
    expect(seite.locator("#ptt")).to_be_hidden()
    seite.wait_for_timeout(2500)
    seite.click("#interview")
    expect(seite.locator("#ptt")).to_be_visible()


def test_gehaltener_ptt_wird_beim_interviewstart_verworfen(seite):
    """Re-Review F: PTT gehalten, mit dem zweiten Finger Interview gestartet
    -> kein PTT-Upload, nur der Interview-Recorder."""
    seite.locator("#ptt").hover()
    seite.mouse.down()
    seite.wait_for_timeout(900)
    seite.evaluate("document.getElementById('interview').click()")
    seite.mouse.up()
    seite.wait_for_timeout(SEGMENT_MS + 2000)
    seite.click("#interview")
    assert _warte(seite, lambda: "aus" in _form(_posts(seite)), ms=15000)
    folge = _form(_posts(seite))
    assert folge[0] == "an", folge          # kein PTT-Audio vor dem Interview
    assert folge[-1] == "aus"


def test_seite_im_interviewmodus_geladen(oeffne):
    """B11: Modus beim Laden an -> Stopp-Knopf, kein PTT; der Stopp schickt
    nur /fertig (dieses Telefon nimmt nicht auf)."""
    setze_modus(True)
    seite = oeffne()
    expect(seite.locator("#interview")).to_have_attribute("data-laeuft", "1")
    expect(seite.locator("#ptt")).to_be_hidden()
    seite.click("#interview")
    assert _warte(seite, lambda: not _modus_an(), ms=10000)
    assert _form(_posts(seite)) == ["aus"]
    expect(seite.locator("#ptt")).to_be_visible()
    expect(seite.locator("#interview")).to_have_attribute("data-laeuft", "0")


# -- Modusende ohne dieses Telefon (Re-Review H) -----------------------------------

def _geparkt(seite) -> int:
    text = seite.locator("#angehalten-text").inner_text()
    treffer = re.search(r"(\d+) Stück", text)
    return int(treffer.group(1)) if treffer else 0


def test_modusende_waehrend_der_aufnahme_parkt_den_rest(seite):
    """A/H + H2: ein zweites Telefon beendet das Interview -> kein stiller
    Upload als 'kurz', der Rest ist geparkt, der Knopf wieder bedienbar.
    Nachreichen schickt /interview, die Segmente, /fertig."""
    vorher = _zaehle_sprachnachrichten()
    _starte_interview(seite)
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher, ms=10000)
    setze_modus(False)                       # das andere Telefon
    expect(seite.locator("#angehalten")).to_be_visible()
    expect(seite.locator("#angehalten-text")).to_contain_text("noch nicht angekommen")
    expect(seite.locator("#nachreichen")).to_be_visible()
    expect(seite.locator("#interview")).to_be_enabled()
    expect(seite.locator("#interview")).to_have_text(web_chat._TEXT_INTERVIEW_AN)
    expect(seite.locator("#ptt")).to_be_visible()
    expect(seite.locator("#uhr")).to_be_hidden()
    stand = len(_posts(seite))
    geparkt = _geparkt(seite)
    assert geparkt >= 1
    seite.wait_for_timeout(SEGMENT_MS + 2000)
    assert _posts(seite)[stand:] == []      # nichts still nachgeschickt, kein /fertig
    assert not _modus_an()

    seite.click("#nachreichen")
    assert _warte(seite, lambda: "aus" in _form(_posts(seite)[stand:]), ms=15000)
    assert _form(_posts(seite)[stand:]) == ["an"] + ["audio"] * geparkt + ["aus"]
    expect(seite.locator("#angehalten")).to_be_hidden()
    assert _warte(seite, lambda: not _modus_an())


def test_modusende_rest_verwerfen(seite):
    """H3: Verwerfen -> kein Upload der geparkten Segmente."""
    vorher = _zaehle_sprachnachrichten()
    _starte_interview(seite)
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher, ms=10000)
    setze_modus(False)
    expect(seite.locator("#verwerfen")).to_be_visible()
    stand = len(_posts(seite))
    seite.click("#verwerfen")
    expect(seite.locator("#angehalten")).to_be_hidden()
    seite.wait_for_timeout(2500)
    assert _posts(seite)[stand:] == []
    expect(seite.locator("#interview")).to_be_enabled()


def test_modusende_waehrend_upload_der_dann_scheitert(seite):
    """H1: beim Modusende ist ein Segment unterwegs und scheitert danach ->
    es wird geparkt (vorn), und die Schlange haengt nicht: ein PTT danach
    kommt an."""
    seite.evaluate("window.__t.halteAudio = true")
    _starte_interview(seite)
    assert _warte(seite, lambda: _t(seite, "gehalten.length") >= 1, ms=10000)
    setze_modus(False)
    expect(seite.locator("#angehalten")).to_be_visible()
    assert _warte(seite, lambda: _t(seite, "starts") >= 2 and not seite.evaluate(
        "document.getElementById('uhr').hidden === false"))
    seite.wait_for_timeout(500)
    vor_dem_scheitern = _geparkt(seite)
    # Der festgehaltene Upload scheitert jetzt.
    seite.evaluate("window.__t.halteAudio = false; window.__t.gehalten.shift()(503)")
    assert _warte(seite, lambda: _geparkt(seite) == vor_dem_scheitern + 1, ms=6000)
    expect(seite.locator("#nachreichen")).to_be_visible()

    vorher = _zaehle_sprachnachrichten()
    expect(seite.locator("#ptt")).to_be_visible()
    _halte_ptt(seite, 1000)
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher, ms=10000)
    assert _zaehle_sprachnachrichten() == vorher + 1
    assert _geparkt(seite) == vor_dem_scheitern + 1


def test_anderes_interview_laeuft_nachreichen_wartet(seite):
    """H4: geparkt, und ein anderes Telefon startet ein Interview -> kein
    Nachreichen-Knopf, kein /interview; nach dessen Ende kommt er wieder."""
    vorher = _zaehle_sprachnachrichten()
    _starte_interview(seite)
    assert _warte(seite, lambda: _zaehle_sprachnachrichten() > vorher, ms=10000)
    setze_modus(False)
    expect(seite.locator("#nachreichen")).to_be_visible()
    setze_modus(True)                        # das andere Telefon startet
    expect(seite.locator("#nachreichen")).to_be_hidden()
    expect(seite.locator("#angehalten-text")).to_contain_text("anderes Interview")
    stand = len(_posts(seite))
    seite.wait_for_timeout(2500)
    assert _posts(seite)[stand:] == []
    setze_modus(False)
    expect(seite.locator("#nachreichen")).to_be_visible()
    seite.click("#verwerfen")


# -- Praefix -----------------------------------------------------------------------

def test_unter_dem_praefix_pollt_die_seite_unter_dem_praefix(oeffne, token):
    """B12: alle Wege absolut aus dem Pfad, den der Browser sieht."""
    adressen = []

    def merke(anfrage):
        adressen.append(anfrage.url)

    seite = oeffne(f"{PRAEFIX}/g/{token}/chat",
                   vorher=lambda s: s.on("request", merke))
    assert _warte(seite, lambda: any("/chat/zustand" in a for a in adressen))
    zustand = [a for a in adressen if "/chat/zustand" in a]
    assert all(a.startswith(f"{BASIS}{PRAEFIX}/g/{token}/chat/zustand?") for a in zustand)
    seite.fill("#eingabe", "Unter dem Praefix geschickt.")
    seite.click("#senden")
    expect(seite.locator(".blase.gruppe").last).to_contain_text("Praefix")
    assert f"{BASIS}{PRAEFIX}/g/{token}/chat/senden" in adressen


def test_chat_mit_schraegstrich_ist_404(server, token):
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(f"{BASIS}{PRAEFIX}/g/{token}/chat/", timeout=5)
    assert fehler.value.code == 404


def test_segmentlaenge_kommt_beim_browser_an(seite):
    assert seite.locator("#fuss").get_attribute("data-segment-ms") == str(SEGMENT_MS)
    assert json.loads(seite.evaluate("JSON.stringify(!!navigator.mediaDevices)"))
