"""Is the first word after a 'pause'/'weich' cut inside the NEW segment?

Measured in a real browser (t_4fc47520, spec
docs/superpowers/specs/2026-11-08-padua-vad-preroll-design.md, R1). The fake
microphone is low-pass noise behind a GainNode: gain 0 is digital silence,
gain 1 is "speech". The VAD level (``window.__t.setzeRms``) is driven
separately, so a run can model a quiet onset that the VAD does not see yet.
Each run: 1 s of sound, silence, then sound again ``offset_ms`` around the
predicted cut. A reference recorder on a clone of the same stream locates
segment A (before the cut) and B (after it) sample-exactly.

Per run one line ``SCHNITTEINSATZ {json}``:

- ``onset_minus_cut_wall_ms``: onset time minus ``B.start()`` (wall clock)
- ``missing_in_b_ms``: onset audio that B does not hold (B started later)
- ``onset_in_a_tail_ms``: how much audio from the onset on A's tail holds
- ``gap_ms``: B start minus A end in the reference (<= 0 = overlap)

Asserted is only the premise: no gap at the boundary, and nothing missing in
B when the onset comes >= 250 ms after the cut. Runs inside the R1 window are
reported, not asserted.

Call::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_chat_schnitt_einsatz_e2e.py -q -s

Skipped in the normal ``pytest`` run (``importorskip``, ``--ignore=tests/e2e``).
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

pytest.importorskip("playwright.sync_api", reason="playwright is not installed here")
from playwright.sync_api import sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from interview_theater import db, repo, web_kanal  # noqa: E402
from tests.e2e.test_web_chat_e2e import _MESSUNG  # noqa: E402

CHAT = 7_000_000_000_004
PHONE = {"width": 390, "height": 844}
OFFSETS_MS = (-100, -50, 0, 50, 100, 300)
REPEATS = 2
#: 12 ticks of 60 ms: the first tick with >= 700 ms of silence.
CUT_AFTER_LAST_SPEECH_TICK_MS = 720
#: An onset this long after B.start() must be fully inside B.
SURE_AFTER_CUT_MS = 250

COMMON_ENV = {
    "IT_WEB_VAD_WEICH_PAUSE_MS": "700",
    "IT_WEB_VAD_MAX_MS": "60000",
    "IT_WEB_VAD_MIN_SPEECH_MS": "200",
    "IT_WEB_VAD_KALIBRIERUNG": "0",
}
#: 'pause': the 700 ms pause rule cuts. 'weich': the segment is old enough
#: (1.5 s) for the soft cut, the pause rule is out of reach.
CONFIGS = {
    "pause": {"IT_WEB_VAD_PAUSE_MS": "700", "IT_WEB_VAD_WEICH_MS": "60000"},
    "weich": {"IT_WEB_VAD_PAUSE_MS": "60000", "IT_WEB_VAD_WEICH_MS": "1500"},
}

#: Runs BEFORE ``_MESSUNG``: gated noise as the microphone, a reference
#: recorder, per-segment timestamps on the real MediaRecorder prototype.
_GATED = r"""
(function () {
  var M = window.__m = { recs: [], ref: null, ticks: [], gain: null, ctx: null };
  if (!window.MediaRecorder) { return; }
  var RealRecorder = window.MediaRecorder;   // _MESSUNG wraps it later
  var P = RealRecorder.prototype;
  var realStart = P.start, realStop = P.stop;
  var LEVEL = 0.02;
  function watch(r, e) {
    r.addEventListener('dataavailable', function (ev) {
      if (ev.data && ev.data.size) { e.parts.push(ev.data); }
    });
    r.addEventListener('stop', function () {
      e.stopEvT = performance.now();
      e.blob = new Blob(e.parts, { type: r.mimeType || 'audio/webm' });
    });
  }
  function entry() {
    return { startT: performance.now(), stopT: null, stopEvT: null, parts: [], blob: null };
  }
  P.start = function () {
    var e = entry();
    M.recs.push(e);
    this.__m = e;
    watch(this, e);
    return realStart.apply(this, arguments);
  };
  P.stop = function () {
    if (this.__m && this.__m.stopT === null) { this.__m.stopT = performance.now(); }
    return realStop.apply(this, arguments);
  };

  var RealContext = window.AudioContext;
  navigator.mediaDevices.getUserMedia = function () {
    var k = new RealContext({ sampleRate: 48000 });
    var n = 48000 * 60;
    var buf = k.createBuffer(1, n, 48000);
    var d = buf.getChannelData(0);
    for (var i = 0; i < n; i++) { d[i] = Math.random() * 2 - 1; }
    var src = k.createBufferSource();
    src.buffer = buf;
    src.loop = true;
    var filter = k.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 2000;
    var gain = k.createGain();
    gain.gain.value = 0;
    var dest = k.createMediaStreamDestination();
    src.connect(filter); filter.connect(gain); gain.connect(dest);
    src.start();
    M.gain = gain; M.ctx = k;
    return k.resume().then(function () {
      var ref = new RealRecorder(dest.stream.clone());
      var e = entry();
      M.ref = { r: ref, e: e };
      watch(ref, e);
      realStart.call(ref);
      return dest.stream;
    });
  };
  M.sound = function (on) { M.gain.gain.setValueAtTime(on ? 1 : 0, M.ctx.currentTime); };
  M.stopReference = function () { realStop.call(M.ref.r); };

  // One run: 1 s sound, silence, sound again `delta` ms around the
  // predicted cut. The VAD level stays 0 until the cut has happened and
  // the onset is >= 60 ms old (a quiet onset the VAD does not see).
  M.run = function (delta, cutAfterMs) {
    var T = window.__t;
    return new Promise(function (done) {
      T.setzeRms(0.6); M.sound(true);
      setTimeout(function () {
        T.setzeRms(0); M.sound(false);
        var pauseFrom = performance.now();
        var speech = M.ticks.filter(function (x) { return x.rms > 0 && x.t <= pauseFrom; });
        if (!speech.length) { done({ error: 'no speech tick before the pause' }); return; }
        var last = speech[speech.length - 1].t;
        var predicted = last + cutAfterMs;
        setTimeout(function () {
          M.sound(true);
          var onsetT = performance.now();
          var giveUp = onsetT + 5000;
          var wait = setInterval(function () {
            var now = performance.now();
            if (M.recs.length >= 2 && now >= onsetT + 60) {
              clearInterval(wait);
              T.setzeRms(0.6);
              setTimeout(function () {
                done({ lastSpeechT: last, predictedCutT: predicted,
                       onsetT: onsetT, cutT: M.recs[1].startT });
              }, 1000);
            } else if (now > giveUp) {
              clearInterval(wait);
              done({ error: 'no cut within 5 s after the onset' });
            }
          }, 10);
        }, Math.max(0, predicted + delta - performance.now()));
      }, 1000);
    });
  };

  function decode(ctx, blob) {
    return blob.arrayBuffer().then(function (b) { return ctx.decodeAudioData(b); })
      .then(function (p) { return p.getChannelData(0); });
  }
  function firstSound(x, from) {
    if (from < 0) { return -1; }
    for (var i = from; i < x.length; i++) { if (Math.abs(x[i]) > LEVEL) { return i; } }
    return -1;
  }
  function firstSilence(x, from, len) {
    if (from < 0) { return -1; }
    var run = 0;
    for (var i = from; i < x.length; i++) {
      if (Math.abs(x[i]) <= LEVEL) { run += 1; if (run >= len) { return i - len + 1; } }
      else { run = 0; }
    }
    return -1;
  }
  // Best offset of probe in ref, searched in [from, to).
  function find(ref, probe, from, to) {
    var N = probe.length, pe = 0, i;
    for (i = 0; i < N; i++) { pe += probe[i] * probe[i]; }
    var bestL = -1, bestW = -2;
    from = Math.max(0, from); to = Math.min(ref.length - N, to);
    for (var L = from; L < to; L++) {
      var s = 0, re = 0;
      for (i = 0; i < N; i++) { var x = ref[L + i]; s += x * probe[i]; re += x * x; }
      var w = s / Math.sqrt(pe * re + 1e-12);
      if (w > bestW) { bestW = w; bestL = L; }
    }
    return { L: bestL, w: bestW };
  }
  M.evaluate = async function () {
    var ctx = new OfflineAudioContext(1, 48000, 48000);
    var SR = 48, N = 4800, EDGE = 1200, SEARCH = 400 * SR;
    if (M.recs.length < 2) { return { error: 'fewer than two segments', segments: M.recs.length }; }
    var ref = await decode(ctx, M.ref.e.blob);
    var A = M.recs[0], B = M.recs[1];
    var a = await decode(ctx, A.blob), b = await decode(ctx, B.blob);
    var refOnset = firstSound(ref, firstSilence(ref, firstSound(ref, 0), 200 * SR));
    if (refOnset < 0) { return { error: 'no second onset in the reference' }; }
    function place(seg, rec) {
      var on = firstSound(seg, 0);
      if (on < 0) { return null; }
      var expected = Math.round((rec.startT - M.ref.e.startT) * SR) + on + EDGE;
      var hit = find(ref, seg.subarray(on + EDGE, on + EDGE + N),
                     expected - SEARCH, expected + SEARCH);
      return { startRef: hit.L - (on + EDGE), w: hit.w };
    }
    var pa = place(a, A), pb = place(b, B);
    if (!pa || !pb) { return { error: 'a segment holds no sound' }; }
    var aEnd = pa.startRef + a.length;
    return {
      missing_in_b_ms: Math.max(0, pb.startRef - refOnset) / SR,
      onset_in_a_tail_ms: Math.max(0, aEnd - refOnset) / SR,
      gap_ms: (pb.startRef - aEnd) / SR,
      onset_minus_b_start_ms: (refOnset - pb.startRef) / SR,
      corr_min: Math.min(pa.w, pb.w),
      segments: M.recs.length
    };
  };
})();
"""

#: Runs AFTER ``_MESSUNG``: logs every VAD tick (time and the fake level),
#: so a run can predict the cut from the last speech tick.
_TICKS = r"""
(function () {
  var M = window.__m, Wrapped = window.AudioContext;
  if (!M || !Wrapped) { return; }
  window.AudioContext = function () {
    var k = new Wrapped();
    var make = k.createAnalyser.bind(k);
    k.createAnalyser = function () {
      var a = make();
      var read = a.getFloatTimeDomainData;
      a.getFloatTimeDomainData = function (values) {
        read.call(a, values);
        M.ticks.push({ t: performance.now(), rms: window.__t.rms });
      };
      return a;
    };
    return k;
  };
})();
"""


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _build_database(db_path: str, audio: str) -> str:
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(db_path + suffix):
            os.remove(db_path + suffix)
    shutil.rmtree(audio, ignore_errors=True)
    conn = db.verbinde(db_path)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 3)
    web_kanal.WebKanal(conn, CHAT, audio, schritt_s=0.01).sende(CHAT, "Los geht's.")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return token


def _fake_bot(db_path: str, stop: threading.Event) -> None:
    """/interview -> mode on, /fertig -> off, so segments upload normally."""
    conn = db.verbinde(db_path)
    last = 0
    try:
        while not stop.is_set():
            for row in conn.execute(
                "SELECT id, text FROM web_post WHERE chat_id = ? "
                "AND typ = 'befehl' AND id > ? ORDER BY id", (CHAT, last),
            ).fetchall():
                repo.setze_interviewmodus(
                    conn, CHAT,
                    time.strftime("%Y-%m-%dT%H:%M:%S")
                    if row["text"] == "/interview" else None,
                )
                conn.commit()
                last = row["id"]
            time.sleep(0.05)
    finally:
        conn.close()


# Function scope: a fresh server per run also resets web_grenze's rate limit
# (20 interview toggles per minute per chat), which 12 runs in a row exhaust.
@pytest.fixture(params=sorted(CONFIGS))
def server(request):
    name = request.param
    db_path = f"/tmp/it-webchat-einsatz-{name}.db"
    audio = f"/tmp/it-webchat-einsatz-{name}-audio"
    log_path = f"/tmp/it-webchat-einsatz-{name}-server.log"
    token = _build_database(db_path, audio)
    bind = f"127.0.0.1:{_free_port()}"
    base = f"http://{bind}"
    env = dict(os.environ)
    env.update(COMMON_ENV)
    env.update(CONFIGS[name])
    env.update({
        "IT_DB": db_path, "IT_WEB_BIND": bind, "IT_WEB_PREFIX": "/theatersoap",
        "IT_AUDIO": audio, "PYTHONPATH": str(ROOT),
    })
    log = open(log_path, "w")
    process = subprocess.Popen(
        [sys.executable, "-u", "-m", "interview_theater.web"],
        cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    stop = threading.Event()
    bot = threading.Thread(target=_fake_bot, args=(db_path, stop), daemon=True)
    try:
        deadline = time.time() + 15
        while True:
            if process.poll() is not None:
                raise RuntimeError(f"web server crashed, see {log_path}.")
            try:
                with urllib.request.urlopen(f"{base}/gesund", timeout=1) as answer:
                    if answer.read().decode().strip() == "ok":
                        break
            except (urllib.error.URLError, OSError):
                if time.time() > deadline:
                    raise RuntimeError("web server did not come up.")
                time.sleep(0.2)
        bot.start()
        yield {"name": name, "base": base, "token": token}
    finally:
        stop.set()
        if bot.is_alive():
            bot.join(timeout=5)
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


def _wait(page, condition, ms: int, step: int = 100) -> bool:
    end = time.time() + ms / 1000
    while time.time() < end:
        if condition():
            return True
        page.wait_for_timeout(step)
    return condition()


@pytest.mark.parametrize("repeat", range(REPEATS))
@pytest.mark.parametrize("offset_ms", OFFSETS_MS)
def test_onset_around_a_cut(server, offset_ms, repeat):
    with sync_playwright() as p:
        # Optional override: Playwright's Python API does not read this env var
        # itself; unset keeps the bundled browser.
        browser = p.chromium.launch(
            executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH") or None,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        try:
            context = browser.new_context(
                viewport=PHONE, permissions=["microphone"], base_url=server["base"],
                is_mobile=True, has_touch=True,
            )
            context.add_init_script(_GATED)
            context.add_init_script(_MESSUNG)
            context.add_init_script(_TICKS)
            page = context.new_page()
            page.set_default_timeout(10_000)
            page.goto(f"{server['base']}/g/{server['token']}/chat")
            page.evaluate("window.__t.setzeRms(0)")   # no speech before the run
            page.click("#interview")
            page.wait_for_selector('#interview[data-laeuft="1"]')
            # the fake microphone may not exist yet when data-laeuft flips
            # (polled via evaluate: wait_for_function evals a string, the CSP forbids it)
            assert _wait(page, lambda: page.evaluate(
                "!!(window.__m.gain && window.__m.ref)"), 5000), "fake microphone never created"
            run = page.evaluate(
                f"window.__m.run({offset_ms}, {CUT_AFTER_LAST_SPEECH_TICK_MS})")
            assert "error" not in run, run
            page.click("#interview-beenden")
            assert _wait(page, lambda: page.evaluate(
                "window.__m.recs.every(function (e) { return e.stopEvT !== null; })"),
                ms=10_000)
            page.wait_for_timeout(300)
            page.evaluate("window.__m.stopReference()")
            assert _wait(page, lambda: page.evaluate(
                "window.__m.ref.e.stopEvT !== null"), ms=5000)
            result = page.evaluate("window.__m.evaluate()")
            context.close()
        finally:
            browser.close()
    assert "error" not in result, result
    report = {
        "config": server["name"], "offset_ms": offset_ms, "repeat": repeat,
        "onset_minus_cut_wall_ms": round(run["onsetT"] - run["cutT"], 1),
        "cut_minus_predicted_ms": round(run["cutT"] - run["predictedCutT"], 1),
    }
    report.update({k: round(v, 1) if isinstance(v, float) else v
                   for k, v in result.items()})
    print("\nSCHNITTEINSATZ " + json.dumps(report))
    # The measurement itself must hold: exactly the one cut, segments found.
    assert report["segments"] == 2, report
    assert report["corr_min"] > 0.9, report
    # Premise (spec §2.2): no audio lost at the boundary ...
    assert report["gap_ms"] <= 0, report
    # ... and an onset clearly after the cut is fully inside B.
    if report["onset_minus_cut_wall_ms"] >= SURE_AFTER_CUT_MS:
        assert report["missing_in_b_ms"] == 0, report
