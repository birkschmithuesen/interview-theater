# Padua VAD pre-roll — measure-first Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin with tests that no VAD cut type drops audio before the next speech onset, measure the one plausible residual (a word split at a pause/weich cut, "R1"), and write the decision input for Birk. **No production code changes.**

**Architecture:** The spec `docs/superpowers/specs/2026-11-08-padua-vad-preroll-design.md` refutes the card's premise (§2.2): the recorder runs continuously, pause/weich cuts fire in silence, and every keep-cut starts the successor first and overlaps 200 ms. This plan therefore adds (1) two non-e2e Node/grep tests in `tests/test_web_chat_js.py` that pin that premise, (2) a Playwright measurement that sweeps a speech onset around a real pause and weich cut, and (3) a handoff document that records the numbers and the decision gate. The card's pre-roll (way 1 "early successor") is built **only** in a later card, and only if the gate in spec §4.3 trips.

**Tech Stack:** Python 3 + pytest, Node (runs JS extracted verbatim from `web_chat._CHAT_JS`), Playwright Chromium (e2e only, separate venv).

## Global Constraints

- No change to `interview_theater/` at all. In particular `entscheideSchnitt`, the calibration (`kal*`), the noise-floor logic, `UEBERLAPP_MS`, `neuesSegment`, `schneideSegment` stay byte-identical.
- No PCM/AudioWorklet path, no rolling or speculative recorder.
- English for code, identifiers, comments, commits and docs (`docs/refactoring-guidelines.md` §7).
- Padua only; Dortmund is frozen (AGENTS.md). No `@pytest.mark.dortmund` needed — nothing here depends on Dortmund.
- One command per Bash call, no `cd`, no `&&`/`;`, no `$VAR`, no `$( )`.
- Targeted test command (append the test path):
  `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2`
- Do not run the full suite yourself — cc-run.py runs it once afterwards.
- Never start, stop or restart a live service (`interview-theater*`). No real Whisper or LLM calls.
- Commit after each task on the current branch `wt/t_4fc47520`. No merge, no push.
- If something here is wrong or cannot be run: stop and end with one line `FRAGE: <question>`. Do not guess.

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `tests/test_web_chat_js.py` | Modify (append two blocks) | P1: a speech tick never cuts pause/weich (runs the real tick body). P2: every `neuesSegment(sitzung)` call site is classified |
| `tests/e2e/test_web_chat_schnitt_einsatz_e2e.py` | Create | Browser measurement: onset swept around a real pause/weich cut, `SCHNITTEINSATZ {json}` per run |
| `docs/handoffs/2026-11-08-padua-vad-preroll.md` | Create | Measured numbers, live-data query, gate inputs for Birk |

Both the P1 and P2 code below were dry-run against a4485ce while this plan was written (scratch file, 3 passed, including the P1 mutant check). The e2e file could not be run then: its venv is outside the planning worktree.

---

### Task 1: P1 — a speech tick never produces a pause/weich cut

**Files:**
- Modify: `tests/test_web_chat_js.py` — insert after `test_entscheideschnitt_kein_schnitt_unter_min_speech_ms_live_in_node` (ends near line 2965, just before `def test_herumreichen_erinnerung_zeigt_sich_nur_beim_ersten_mal_live_in_node`)
- Test: same file

**Interfaces:**
- Consumes (already in the file): `_node_oder_skip() -> str`, `_fuehre_js_aus(node: str, quelltext: str, tmp_path) -> str`, module import `web_chat` (and `json`).
- Consumes (JS, extracted verbatim): the body of `sitzung.pegelTakt = setInterval(function () { … }, VAD_TAKT_MS)` and `function entscheideSchnitt` (up to `function kalMedian`) from `web_chat._CHAT_JS`.
- Produces: helper `_pegeltakt_cuts(node, tmp_path, scenarios_js: str) -> dict` (used only in this task) and test `test_a_speech_tick_never_cuts_pause_or_weich_live_in_node`.

These are characterization tests: they pass on today's code. The red step is the **mutant** run in Step 3.

- [ ] **Step 1: Add the helper and the test**

Insert this block (with a two-line section comment) after `test_entscheideschnitt_kein_schnitt_unter_min_speech_ms_live_in_node`:

```python
# -- Pre-roll premise (t_4fc47520, spec 2026-11-08-padua-vad-preroll-design) --
# -- A 'pause'/'weich' cut can only fire on a tick that is itself below the  --
# -- threshold: the tick updates vadLetzteRede BEFORE entscheideSchnitt runs. --


def _pegeltakt_cuts(node, tmp_path, scenarios_js: str) -> dict:
    """Runs the verbatim pegelTakt body together with the verbatim
    ``entscheideSchnitt``; ``schneideSegment`` is a stub that records the
    cut reason, ``Date.now`` is driven by the scenario."""
    js = web_chat._CHAT_JS
    takt = js[js.index("sitzung.pegelTakt = setInterval(function () {"):]
    takt = takt[:takt.index("}, VAD_TAKT_MS)")]
    body = takt[takt.index("{") + 1:]
    decide = js[js.index("function entscheideSchnitt"):js.index("function kalMedian")]
    source = f"""
    var PEGEL_MAX_RMS = 0.3;
    var BODEN_FENSTER = 10;
    var RMS_SCHWELLE = 0.01, BODEN_FAKTOR = 2.5, BODEN_DECKEL_FAKTOR = 10;
    var MAX_MS = 90000, PAUSE_MS = 2500, MIN_SPEECH_MS = 500;
    var WEICH_AB_MS = 30000, WEICH_PAUSE_MS = 700;
    var VAD_TAKT_MS = 60;
    function kalBerechneBodenUndSchwelle() {{ return {{ boden: 0, schwelle: 0.1 }}; }}
    var cuts = [];
    function schneideSegment(s, grund) {{ cuts.push(grund); }}
    {decide}
    var __rms = 0;
    var __now = 0;
    Date.now = function () {{ return __now; }};
    var zeitWerte = {{ length: 1 }};
    var messer = {{ getFloatTimeDomainData: function (arr) {{ arr[0] = __rms; }} }};
    var pegelBalken = {{ style: {{}} }};
    var pegelSchwelle = {{ style: {{}} }};
    var pegelFeld = {{ classList: {{ toggle: function () {{}} }} }};
    var sitzung;
    function tick() {{
    {body}
    }}
    // Below-threshold ticks from `from` to `to` (inclusive, 60 ms apart),
    // then ONE tick at `critical` with level `criticalRms`.
    function run(start, from, to, critical, criticalRms) {{
      sitzung = {{ vadBoden: [], recorder: {{}}, vadSegmentStart: start.seg,
                  vadLetzteRede: start.speechAt, vadSpeechMs: start.speechMs }};
      cuts = [];
      __rms = 0;
      for (var t = from; t <= to; t += 60) {{ __now = t; tick(); }}
      var before = cuts.slice();
      __now = critical; __rms = criticalRms; tick();
      return {{ before: before, critical: cuts.slice(before.length),
               lastSpeech: sitzung.vadLetzteRede }};
    }}
    {scenarios_js}
    """
    return json.loads(_fuehre_js_aus(node, source, tmp_path).strip().splitlines()[-1])


def test_a_speech_tick_never_cuts_pause_or_weich_live_in_node(tmp_path):
    """Spec §2.1 F2/F4: on the exact tick where the silence would reach
    WEICH_PAUSE_MS (700) or PAUSE_MS (2500), one tick above the threshold
    must prevent the cut -- so a pause/weich cut always happens in silence
    and the next word starts inside the new recorder. Control runs without
    that tick do cut. 'cap' ignores speech by design (spec R2).
    Mutant: move the ``if (rms > schwelle) { ... }`` block below the
    ``entscheideSchnitt`` call -> weich_speech/pause_speech cut."""
    node = _node_oder_skip()
    e = _pegeltakt_cuts(node, tmp_path, """
    var weich = { seg: 0, speechAt: 35000, speechMs: 20000 };
    var pause = { seg: 0, speechAt: 20000, speechMs: 15000 };
    var cap = { seg: 0, speechAt: 89940, speechMs: 80000 };
    console.log(JSON.stringify({
      weich_silence: run(weich, 35060, 35660, 35720, 0.0),
      weich_speech: run(weich, 35060, 35660, 35720, 0.5),
      pause_silence: run(pause, 20060, 22460, 22520, 0.0),
      pause_speech: run(pause, 20060, 22460, 22520, 0.5),
      cap_speech: run(cap, 89940, 89940, 90000, 0.5)
    }));
    """)
    assert e["weich_silence"] == {"before": [], "critical": ["weich"], "lastSpeech": 35000}
    assert e["weich_speech"] == {"before": [], "critical": [], "lastSpeech": 35720}
    assert e["pause_silence"] == {"before": [], "critical": ["pause"], "lastSpeech": 20000}
    assert e["pause_speech"] == {"before": [], "critical": [], "lastSpeech": 22520}
    assert e["cap_speech"]["critical"] == ["cap"]
```

- [ ] **Step 2: Run it — it passes on current code**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_web_chat_js.py -k speech_tick_never_cuts`
Expected: `1 passed` (or `1 skipped` if `node` is missing — then stop with `FRAGE: node is not installed, P1 cannot run`).

- [ ] **Step 3: Prove it catches the mutant, then revert**

Temporarily edit `interview_theater/web_chat.py` inside the pegelTakt tick (around lines 2458–2483). Cut these four lines:

```js
        if (rms > schwelle) {
          sitzung.vadSpeechMs += VAD_TAKT_MS;
          sitzung.vadLetzteRede = jetzt;
        }
```

and paste them directly above the line `        // kein grund: die Stille wird Teil desselben, weiterlaufenden` (that is, after the `if (grund === 'weich') { … } else if (grund) { … }` block).

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_web_chat_js.py -k speech_tick_never_cuts`
Expected: `1 failed`, with the assertion on `weich_speech` showing `'critical': ['weich']`.

Revert: `git checkout -- interview_theater/web_chat.py`
Then: `git status --short`
Expected: only ` M tests/test_web_chat_js.py`.

- [ ] **Step 4: Commit**

```
git add tests/test_web_chat_js.py
```
```
git commit -m "test(web_chat): pin that a speech tick never triggers a pause/weich cut (t_4fc47520)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: P2 — every `neuesSegment(sitzung)` call site is classified

**Files:**
- Modify: `tests/test_web_chat_js.py` — insert after `test_kalschnitte_starten_nachfolger_vor_dem_stopp_live_in_node` (ends near line 443, before `def test_das_js_startet_weiterhin_einen_eigenen_recorder_je_segment`)
- Test: same file

**Interfaces:**
- Consumes: `web_chat._CHAT_JS`, module import `re` (already imported at the top of the file).
- Produces: constant `EXPECTED_NEUESSEGMENT_CALLS: dict[str, int]` and test `test_every_neuessegment_call_site_is_classified`.

- [ ] **Step 1: Add the constant and the test**

```python
#: Spec 2026-11-08-padua-vad-preroll-design §2.2: every place that starts a
#: recorder, by enclosing named function, with its verdict.
#: Successor-first + UEBERLAPP_MS overlap (no audio lost): schneideSegment
#: ('pause'/'weich'/'cap'), kalSchneideOhneMarkierung (2 sites, one is the
#: kalVorStart probe start), kalSchneideAlsKalibrierung, kalStarteEchteSchnitte
#: (the fixed SEGMENT_MS fallback; its other site is the discussion start).
#: Start or discard, nothing kept before it: kalSchneideUndVerwerfen,
#: beginneAufnahme, beendeDiskussion (empty end segment).
EXPECTED_NEUESSEGMENT_CALLS = {
    "schneideSegment": 1,
    "kalSchneideOhneMarkierung": 2,
    "kalSchneideAlsKalibrierung": 1,
    "kalSchneideUndVerwerfen": 1,
    "kalStarteEchteSchnitte": 2,
    "beginneAufnahme": 1,
    "beendeDiskussion": 1,
}


def test_every_neuessegment_call_site_is_classified():
    """A new place that starts a recorder must be classified in the spec's
    verdict table (and here) -- otherwise a cut could come back that starts
    the new recorder late or stops the old one first, without any test
    noticing. Mutant: add ``neuesSegment(sitzung)`` anywhere else."""
    js = web_chat._CHAT_JS
    named = [(m.start(), m.group(1))
             for m in re.finditer(r"\bfunction ([A-Za-z_]\w*)\s*\(", js)]
    found: dict[str, int] = {}
    for m in re.finditer(r"neuesSegment\(sitzung\)", js):
        if js[max(0, m.start() - 9):m.start()] == "function ":
            continue   # the definition itself
        enclosing = [name for pos, name in named if pos < m.start()][-1]
        found[enclosing] = found.get(enclosing, 0) + 1
    assert found == EXPECTED_NEUESSEGMENT_CALLS
```

- [ ] **Step 2: Run it — it passes on current code**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_web_chat_js.py -k neuessegment_call_site`
Expected: `1 passed`.

- [ ] **Step 3: Prove it catches the mutant, then revert**

Temporarily add the line `    var probe = neuesSegment(sitzung);` as the first line inside `function pausiereInterview(sitzungArg) {` in `interview_theater/web_chat.py` (around line 3695).

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_web_chat_js.py -k neuessegment_call_site`
Expected: `1 failed`, the diff shows an extra key `'pausiereInterview': 1`.

Revert: `git checkout -- interview_theater/web_chat.py`
Then: `git status --short`
Expected: only ` M tests/test_web_chat_js.py`.

- [ ] **Step 4: Run the whole JS test file once**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_web_chat_js.py`
Expected: all passed (the count printed by pytest, no failures).

- [ ] **Step 5: Commit**

```
git add tests/test_web_chat_js.py
```
```
git commit -m "test(web_chat): classify every neuesSegment call site against the pre-roll verdict table (t_4fc47520)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Browser measurement — onset swept around a real pause/weich cut

**Files:**
- Create: `tests/e2e/test_web_chat_schnitt_einsatz_e2e.py`
- Read for context (do not modify): `tests/e2e/test_web_chat_schnittluecke_e2e.py` (the gap measurement this extends), `tests/e2e/test_web_chat_e2e.py` (`_MESSUNG`: the recorder wrapper and the fake analyser level `window.__t.setzeRms`)

**Interfaces:**
- Consumes: `tests.e2e.test_web_chat_e2e._MESSUNG` (JS string). Repo calls as in the Schnittluecke test: `db.verbinde`, `db.initialisiere`, `repo.sichere_gruppe`, `repo.setze_gruppe_kanal`, `repo.setze_phase`, `web_kanal.WebKanal(...).sende`, `repo.stelle_web_token_sicher`, `repo.setze_interviewmodus`.
- Produces: one stdout line per run, `SCHNITTEINSATZ {json}` with keys `config, offset_ms, repeat, onset_minus_cut_wall_ms, cut_minus_predicted_ms, missing_in_b_ms, onset_in_a_tail_ms, gap_ms, onset_minus_b_start_ms, corr_min, segments`. Task 4 copies these lines.

How it works: the fake microphone is low-pass noise behind a `GainNode` (gain 0 = digital silence, 1 = "speech"). The VAD level (`__t.setzeRms`) is driven separately, so a run can model a quiet onset: the sound is on while the VAD still reads silence. Each run: 1 s of sound, silence, then sound again at `offset_ms` relative to the predicted cut (last speech tick + 720 ms, i.e. 12 ticks of 60 ms ≥ 700 ms). A reference recorder on a clone of the stream locates both segments by cross-correlation, as in the Schnittluecke test.

- [ ] **Step 1: Create the file**

```python
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


@pytest.fixture(scope="module", params=sorted(CONFIGS))
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
        browser = p.chromium.launch(args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--autoplay-policy=no-user-gesture-required",
        ])
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
```

- [ ] **Step 2: Check it is skipped in the normal suite**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" -p no:cacheprovider tests/e2e/test_web_chat_schnitt_einsatz_e2e.py`
Expected: `1 skipped` (playwright is not in the dev extra). If it reports `24 passed`/`failed` instead, playwright is installed in `.venv` — that is fine too; go on with Step 3.

- [ ] **Step 3: Run the measurement in the e2e venv**

Run (the e2e venv from the Schnittluecke docstring; ~3–5 min, Bash timeout 900000):
`/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest tests/e2e/test_web_chat_schnitt_einsatz_e2e.py -q -s -p no:cacheprovider`

Expected: `24 passed` (2 configs × 6 offsets × 2 repeats) and 24 `SCHNITTEINSATZ {…}` lines. Expected shape, from the spec's analysis (not yet measured):
- `gap_ms` between about −200 and −100 in every run;
- `offset_ms` 300: `missing_in_b_ms` 0;
- `offset_ms` −100/−50: `missing_in_b_ms` > 0 and `onset_in_a_tail_ms` > 0 — that is R1 (word split, no loss). It is reported, not asserted.

If the venv path does not exist or Chromium does not start: stop and end with `FRAGE: the e2e venv /mnt/HC_Volume_106183673/venvs/it-webtest is not usable here (<error line>) — run Task 3 Step 3 on herkules, or skip the measurement?`
If a run fails with `"error"` in the result, or `segments != 2`: use superpowers:systematic-debugging. Look at `cut_minus_predicted_ms` first (tick jitter), and do not loosen the premise asserts (`gap_ms <= 0`, `missing_in_b_ms == 0` at ≥ 250 ms). If the premise asserts fail, the spec's verdict is wrong for that cut type: stop and report it with the failing `SCHNITTEINSATZ` line as `FRAGE:`.

Save the 24 lines for Task 4. Copy them from the pytest output (`-s` prints them).

- [ ] **Step 4: Commit**

```
git add tests/e2e/test_web_chat_schnitt_einsatz_e2e.py
```
```
git commit -m "test(e2e): measure speech onset around pause/weich cuts (pre-roll premise, t_4fc47520)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Handoff with the numbers and the decision gate

**Files:**
- Create: `docs/handoffs/2026-11-08-padua-vad-preroll.md`

**Interfaces:**
- Consumes: the 24 `SCHNITTEINSATZ` lines from Task 3 Step 3, spec §2.3/§4.3/§5.
- Produces: the document Birk uses to decide on the follow-up card.

- [ ] **Step 1: Write the handoff**

Write the file with exactly these sections. Fill the tables from the Task 3 output: one row per run, numbers copied, not rounded further. Every placeholder in angle brackets must be replaced with a measured value or the literal text `not run`.

```markdown
# Handoff t_4fc47520 — Padua VAD pre-roll (measure-first)

Spec: `docs/superpowers/specs/2026-11-08-padua-vad-preroll-design.md`.
Plan: `docs/superpowers/plans/2026-11-08-padua-vad-preroll.md`.

## Result in one paragraph

The card's premise (audio before the detected onset is lost) is refuted on
main a4485ce for every cut type (spec §2.2). Pinned by
`test_a_speech_tick_never_cuts_pause_or_weich_live_in_node` and
`test_every_neuessegment_call_site_is_classified` (tests/test_web_chat_js.py).
The browser measurement below quantifies R1: an onset right at a pause/weich
cut is split between A's tail and B. Audio is never lost.

## Measurement (Chromium headless, <playwright version from `pip show playwright` in the e2e venv>, <date>)

Command: `/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest tests/e2e/test_web_chat_schnitt_einsatz_e2e.py -q -s -p no:cacheprovider`

| config | offset_ms | repeat | onset−cut (wall) ms | missing_in_b_ms | onset_in_a_tail_ms | gap_ms |
|---|---|---|---|---|---|---|
| <one row per SCHNITTEINSATZ line> |

Summary: R1 window measured as onset−cut from <lowest value with missing_in_b_ms > 0> to <highest value with missing_in_b_ms > 0> ms; largest missing_in_b_ms <value> ms; smallest onset_in_a_tail_ms in those runs <value> ms; gap_ms range <min>..<max> ms.

## Not measured (ANNAHME)

- Safari iOS, Firefox Android (spec R3): start latency and frame size unknown; check on a real phone.
- Whisper on a split word (spec R4): costs money, never automatic.

## Live data — for Birk to run on herkules (read-only)

    sqlite3 -readonly <padua-db> "SELECT diskussion, brainstorm, schnittgrund, COUNT(*) FROM aufnahme WHERE empfangen_am >= '2026-10-06' GROUP BY diskussion, brainstorm, schnittgrund"

## Decision gate (spec §4.3)

A follow-up card "early successor" (spec §3, approach 2) is justified only if
(1) the table above shows missing_in_b_ms > 0 (it does / does not: <state which>), and
(2) the live query shows that 'weich' + 'pause' cuts are a material share (Birk decides).
Otherwise the card closes with this measurement.
```

- [ ] **Step 2: Check no placeholder is left**

Run: `grep -n "<" docs/handoffs/2026-11-08-padua-vad-preroll.md`
Expected: only the line with `<padua-db>` in the sqlite3 command (that one stays, Birk fills it in). Any other hit is an unfilled placeholder: fill it.

- [ ] **Step 3: Commit**

```
git add docs/handoffs/2026-11-08-padua-vad-preroll.md
```
```
git commit -m "docs(handoff): Padua VAD pre-roll measurement and decision gate (t_4fc47520)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Done when

- `tests/test_web_chat_js.py` passes with both new tests (Task 2 Step 4), and both mutants were shown red, then reverted.
- `git diff a4485ce --stat -- interview_theater/` prints nothing (no production change).
- The e2e file exists and ran 24 passed in the e2e venv, or a `FRAGE:` explains why it could not run.
- The handoff holds the numbers and the gate.
- The full non-e2e suite runs once afterwards via cc-run.py:
  `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2`
