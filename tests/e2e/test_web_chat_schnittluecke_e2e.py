"""Geht an einem Segmentschnitt Audio verloren? -- gemessen im echten Browser.

Birk, 05.10.2026: "Gehen an den Schnitten Audiodaten verloren?" -- JA, bis
zum Nachtfix. Gemessen wird ohne Chirp, aber sample-genau: das Mikrofon ist
tiefpassgefiltertes Rauschen, ein Referenz-Recorder nimmt denselben Strom
ohne Schnitt auf, und jedes Segment wird per Kreuzkorrelation (Anfang und
Ende, je 100 ms) in der Referenz wiedergefunden. Luecke an Grenze i =
Anfang(i+1) - Ende(i): positiv = verlorenes Audio, negativ = doppelt.

Messwerte (Chromium headless, Playwright 1.61, Dauerrede,
``IT_WEB_VAD_MAX_MS=2500`` -> 4 'cap'-Schnitte je Lauf, Korrelation >= 0.99,
Segmente in sich lueckenlos):

- VORHER (main: ``alt.stop()``, dann ``neuesSegment``), 6 Laeufe/24 Schnitte:
  Luecke 0/10/40/50/60 ms, Mittel 20 ms, Maximum 60 ms, 13 von 24 Schnitten
  verlieren Audio.
- NUR GETAUSCHT (``neuesSegment``, dann sofort ``alt.stop()``), 8 Laeufe:
  dieselbe Verteilung (0-60 ms) -- die Reihenfolge im JS ist es nicht.
  Ursache: Chromiums Opus-Encoder (60-ms-Rahmen) wirft bei ``stop()`` den
  angefangenen Rahmen weg; jedes Segment ist ein Vielfaches von 60 ms lang
  (2460/2520 ms), und genau diese Restspanne fehlt.
- NACHHER (``neuesSegment``, A stoppt ``UEBERLAPP_MS`` = 200 ms spaeter),
  6 Laeufe/24 Schnitte: Luecke -150 bis -190 ms (Ueberlappung), kein
  einziger Schnitt mit Verlust.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_chat_schnittluecke_e2e.py -q -s

Im normalen ``pytest``-Lauf wird die Datei uebersprungen (``importorskip``).
"""

import json
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
from tests.e2e.test_web_chat_e2e import _MESSUNG  # noqa: E402

DB_PFAD = "/tmp/it-webchat-luecke.db"
AUDIO = "/tmp/it-webchat-luecke-audio"
SERVERLOG = "/tmp/it-webchat-luecke-server.log"
CHAT = 7_000_000_000_003
HANDY = {"width": 390, "height": 844}

#: Kurzer Deckel, Dauerrede -> nur 'cap'-Schnitte (mitten in der Rede, genau
#: der Fall, in dem eine Luecke Woerter kostet). NACHLAUF klein, damit der
#: weiche Deckel (Teil B) ohne Einbruch bald hart schneidet.
MAX_MS = 2500
NACHLAUF_MS = 500
SCHNITTE = 4

#: Liegt VOR ``_MESSUNG``. Drei Dinge:
#:
#: 1. ``getUserMedia`` liefert statt des Fake-Mikrofons tiefpassgefiltertes
#:    Rauschen aus einem eigenen AudioContext (nicht periodisch -- jede Stelle
#:    ist per Kreuzkorrelation eindeutig wiederzufinden; Tiefpass, weil Opus
#:    die hohen Baender nur nachbildet statt die Wellenform zu behalten).
#: 2. Ein REFERENZ-Recorder nimmt denselben Strom (geklont) ohne jeden
#:    Schnitt durchgehend auf.
#: 3. Der Prototyp des ECHTEN MediaRecorder (den die Attrappe aus
#:    ``_MESSUNG`` intern benutzt) zeichnet je Segment ``performance.now()``
#:    bei start()/stop()/stop-Ereignis auf und behaelt den Blob.
#:
#: ``__m.auswerten()`` dekodiert alles (OfflineAudioContext, 48 kHz) und
#: sucht Anfang und Ende jedes Segments in der Referenz (normierte
#: Kreuzkorrelation, 100-ms-Proben, Suchfenster um die Wanduhr-Schaetzung).
#: Luecke an Grenze i = Anfang(i+1) - Ende(i) in der Referenz: positiv =
#: verlorenes Audio, negativ = doppelt aufgenommen.
_ZEITEN = r"""
(function () {
  var M = window.__m = { recs: [], ref: null };
  if (!window.MediaRecorder) { return; }
  var EchterRecorder = window.MediaRecorder;   // _MESSUNG ersetzt ihn spaeter
  var P = EchterRecorder.prototype;
  var echtStart = P.start, echtStop = P.stop;
  function beobachte(r, e) {
    r.addEventListener('dataavailable', function (ev) {
      if (ev.data && ev.data.size) { e.teile.push(ev.data); }
    });
    r.addEventListener('stop', function () {
      e.stopEvT = performance.now();
      e.blob = new Blob(e.teile, { type: r.mimeType || 'audio/webm' });
    });
  }
  function eintrag() {
    return { startT: performance.now(), stopT: null, stopEvT: null, teile: [], blob: null };
  }
  P.start = function () {
    var e = eintrag();
    M.recs.push(e);
    this.__m = e;
    beobachte(this, e);
    return echtStart.apply(this, arguments);
  };
  P.stop = function () {
    if (this.__m && this.__m.stopT === null) { this.__m.stopT = performance.now(); }
    return echtStop.apply(this, arguments);
  };

  var Kontext = window.AudioContext;
  var geraete = navigator.mediaDevices;
  geraete.getUserMedia = function () {
    var k = new Kontext({ sampleRate: 48000 });
    var n = 48000 * 60;
    var puffer = k.createBuffer(1, n, 48000);
    var d = puffer.getChannelData(0);
    for (var i = 0; i < n; i++) { d[i] = Math.random() * 2 - 1; }
    var quelle = k.createBufferSource();
    quelle.buffer = puffer;
    var filter = k.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 2000;
    var ziel = k.createMediaStreamDestination();
    quelle.connect(filter); filter.connect(ziel);
    quelle.start();
    return k.resume().then(function () {
      var ref = new EchterRecorder(ziel.stream.clone());
      var e = eintrag();
      M.ref = { r: ref, e: e };
      beobachte(ref, e);
      echtStart.call(ref);
      return ziel.stream;
    });
  };
  M.stoppeReferenz = function () { echtStop.call(M.ref.r); };

  function dekodiere(ctx, blob) {
    return blob.arrayBuffer().then(function (b) { return ctx.decodeAudioData(b); })
      .then(function (p) { return p.getChannelData(0); });
  }
  // Bester Versatz von probe in ref, gesucht in [von, bis).
  function finde(ref, probe, von, bis) {
    var N = probe.length, pe = 0, i;
    for (i = 0; i < N; i++) { pe += probe[i] * probe[i]; }
    var besterL = -1, besterW = -2;
    von = Math.max(0, von); bis = Math.min(ref.length - N, bis);
    for (var L = von; L < bis; L++) {
      var s = 0, re = 0;
      for (i = 0; i < N; i++) { var x = ref[L + i]; s += x * probe[i]; re += x * x; }
      var w = s / Math.sqrt(pe * re + 1e-12);
      if (w > besterW) { besterW = w; besterL = L; }
    }
    return { L: besterL, w: besterW };
  }
  M.auswerten = async function () {
    var ctx = new OfflineAudioContext(1, 48000, 48000);
    var ref = await dekodiere(ctx, M.ref.e.blob);
    var SR = 48, N = 4800, RAND = 1200, SUCHE = 400 * SR;
    var aus = [];
    for (var j = 0; j < M.recs.length; j++) {
      var e = M.recs[j];
      var seg = await dekodiere(ctx, e.blob);
      var erwartet = Math.round((e.startT - M.ref.e.startT) * SR);
      var kopf = finde(ref, seg.subarray(RAND, RAND + N), erwartet + RAND - SUCHE,
                       erwartet + RAND + SUCHE);
      var a = seg.length - RAND - N;
      var fuss = finde(ref, seg.subarray(a, a + N), kopf.L - RAND + a - SUCHE,
                       kopf.L - RAND + a + SUCHE);
      aus.push({
        startT: e.startT, stopT: e.stopT, stopEvT: e.stopEvT,
        dauerMs: seg.length / SR,
        anfangRef: kopf.L - RAND, endeRef: fuss.L - a + seg.length,
        wKopf: kopf.w, wFuss: fuss.w,
        // Innerer Versatz: 0, wenn das Segment in sich lueckenlos ist.
        innenMs: (fuss.L - kopf.L - (a - RAND)) / SR
      });
    }
    return { ref: { dauerMs: ref.length / SR, startT: M.ref.e.startT }, segmente: aus };
  };
})();
"""


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
    shutil.rmtree(AUDIO, ignore_errors=True)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 3)
    web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01).sende(CHAT, "Los geht's.")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return token


@pytest.fixture(scope="module")
def token() -> str:
    return _baue_datenbank()


@pytest.fixture(scope="module")
def server(token):
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD, "IT_WEB_BIND": BIND, "IT_WEB_PREFIX": "/theatersoap",
        "IT_AUDIO": AUDIO,
        "IT_WEB_VAD_PAUSE_MS": "700",
        "IT_WEB_VAD_MAX_MS": str(MAX_MS),
        "IT_WEB_VAD_CAP_NACHLAUF_MS": str(NACHLAUF_MS),
        "IT_WEB_VAD_MIN_SPEECH_MS": "200",
        "IT_WEB_VAD_KALIBRIERUNG": "0",
        "PYTHONPATH": str(WURZEL),
    })
    log = open(SERVERLOG, "w")
    prozess = subprocess.Popen(
        [sys.executable, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        ende = time.time() + 15
        while True:
            if prozess.poll() is not None:
                raise RuntimeError(f"Webserver abgestuerzt, siehe {SERVERLOG}.")
            try:
                with urllib.request.urlopen(f"{BASIS}/gesund", timeout=1) as a:
                    if a.read().decode().strip() == "ok":
                        break
            except (urllib.error.URLError, OSError):
                if time.time() > ende:
                    raise RuntimeError("Webserver nicht hochgekommen.")
                time.sleep(0.2)
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
    """/interview -> Modus an, /fertig -> aus (wie die Attrappe der
    VAD-Tests), damit die Segmente ganz normal hochgehen."""
    ende = threading.Event()

    def run():
        conn = db.verbinde(DB_PFAD)
        letzte = 0
        try:
            while not ende.is_set():
                for zeile in conn.execute(
                    "SELECT id, text FROM web_post WHERE chat_id = ? "
                    "AND typ = 'befehl' AND id > ? ORDER BY id", (CHAT, letzte),
                ).fetchall():
                    repo.setze_interviewmodus(
                        conn, CHAT,
                        time.strftime("%Y-%m-%dT%H:%M:%S")
                        if zeile["text"] == "/interview" else None,
                    )
                    conn.commit()
                    letzte = zeile["id"]
                time.sleep(0.05)
        finally:
            conn.close()

    faden = threading.Thread(target=run, daemon=True)
    faden.start()
    yield
    ende.set()
    faden.join(timeout=5)


@pytest.fixture
def seite(server, bot, token):
    with sync_playwright() as p:
        chromium = p.chromium.launch(args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--autoplay-policy=no-user-gesture-required",
        ])
        kontext = chromium.new_context(
            viewport=HANDY, permissions=["microphone"], base_url=BASIS,
            is_mobile=True, has_touch=True,
        )
        kontext.add_init_script(_ZEITEN)
        kontext.add_init_script(_MESSUNG)
        blatt = kontext.new_page()
        blatt.set_default_timeout(10_000)
        blatt.goto(f"{BASIS}/g/{token}/chat")
        yield blatt
        kontext.close()
        chromium.close()


def _warte(seite, bedingung, ms: int, schritt: int = 100) -> bool:
    ende = time.time() + ms / 1000
    while time.time() < ende:
        if bedingung():
            return True
        seite.wait_for_timeout(schritt)
    return bedingung()


def test_ein_schnitt_verliert_kein_audio(seite):
    seite.evaluate("window.__t.setzeRms(0.6)")   # Dauerrede: nur 'cap'
    seite.click("#interview")
    seite.wait_for_selector('#interview[data-laeuft="1"]')
    assert _warte(seite, lambda: seite.evaluate("window.__m.recs.length") >= SCHNITTE + 1,
                  ms=(SCHNITTE + 2) * (MAX_MS + NACHLAUF_MS) + 5000)
    seite.wait_for_timeout(1000)   # das letzte Segment bekommt etwas Laenge
    seite.click("#interview-beenden")
    assert _warte(seite, lambda: seite.evaluate(
        "window.__m.recs.every(function (e) { return e.stopEvT !== null; })"), ms=10_000)
    seite.wait_for_timeout(300)
    seite.evaluate("window.__m.stoppeReferenz()")
    assert _warte(seite, lambda: seite.evaluate("window.__m.ref.e.stopEvT !== null"), ms=5000)
    erg = seite.evaluate("window.__m.auswerten()")
    recs = erg["segmente"]
    assert len(recs) >= SCHNITTE + 1

    # Reihenfolge im Browser: B.start() vor A.stop() (negativ = vorher).
    start_minus_stop = [recs[i + 1]["startT"] - recs[i]["stopT"] for i in range(len(recs) - 1)]
    # Inhalt: Luecke an jeder Grenze, in der Referenz gemessen (ms).
    luecken = [(recs[i + 1]["anfangRef"] - recs[i]["endeRef"]) / 48
               for i in range(len(recs) - 1)]
    summe = sum(r["dauerMs"] for r in recs)
    wand_ev = recs[-1]["stopEvT"] - recs[0]["startT"]
    bericht = {
        "segmente": len(recs),
        "start_minus_stop_ms": [round(g, 2) for g in start_minus_stop],
        "luecke_in_referenz_ms": [round(g, 2) for g in luecken],
        "korrelation_min": round(min(min(r["wKopf"], r["wFuss"]) for r in recs), 3),
        "innen_versatz_ms": [round(r["innenMs"], 2) for r in recs],
        "dauern_ms": [round(r["dauerMs"], 1) for r in recs],
        "summe_dekodiert_ms": round(summe, 1),
        "wand_bis_stoppereignis_ms": round(wand_ev, 1),
        "summe_minus_wand_ms": round(summe - wand_ev, 1),
    }
    print("\nSCHNITTLUECKE " + json.dumps(bericht))
    # Die Messung selbst muss tragen: Proben eindeutig gefunden, Segmente in
    # sich lueckenlos.
    assert bericht["korrelation_min"] > 0.9, bericht
    assert all(abs(v) <= 1 for v in bericht["innen_versatz_ms"]), bericht
    for g in start_minus_stop:
        assert g <= 0, bericht
    for g in luecken:
        assert g <= 0, bericht   # kein einziges Sample verloren
    # Plausibilitaet ohne Referenz: Summe der Segmente minus die gemessene
    # Ueberlappung ~ Wanduhr (Rest: Anlaufzeit des ersten Recorders und
    # Verzoegerung des letzten stop-Ereignisses, gemessen -50 bis -90 ms).
    netto = summe + sum(min(0.0, g) for g in luecken)
    assert abs(netto - wand_ev) <= 150, bericht
