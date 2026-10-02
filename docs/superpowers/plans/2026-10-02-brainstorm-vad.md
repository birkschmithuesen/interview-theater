# Pausen-Schnitt (VAD) + Brainstorm-Mithören — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed 45 s web-recording segment cut with a pause-based
(VAD) cut for ALL web audio recordings (Part A), and add a second, Phase-4-only
"🎙 Brainstorm mithören" recording mode whose VAD segments are stored silently
as plain group contributions and occasionally trigger one Claude-written
"stage card" shown in a new tab (Part B).

**Architecture:** Part A changes exactly one subsystem end-to-end: the client
recording-segmentation logic in `interview_theater/web_chat.py`'s `_CHAT_JS`
(replace the `setInterval(SEGMENT_MS)` timer with an `AnalyserNode`-driven
RMS/silence decision, reusing the existing `pegelAn` analyser), plus the two
server-side limits that were sized for 45 s segments. Part B reuses the same
VAD session machinery for a second recording "art" (generalized via
`sitzung.art`), adds one new `aufnahme` column to carry the VAD cut-reason
through to the bot process, a pure code-level trigger-threshold function
(no model call), a Claude Opus "stage card" call that reuses
`szene_claude.py`'s client mechanics, and a minimal CSS/JS tab switch on the
group page (no new route, no dependency on the not-yet-merged Karte-W tab
bar).

**Tech Stack:** Python 3.11 stdlib `http.server`, vanilla JS (no build step),
SQLite, httpx (Claude proxy client), pytest.

## Global Constraints

- Zusage 2 (AGENTS.md): no model call in a button/knopf handler — the
  brainstorm trigger decision itself is pure code; only the resulting stage
  card generation is a model call, and it runs in its own thread/call site,
  never inline in a request handler.
- `callback_data` under 64 bytes wherever a new inline button is added (not
  needed here — no new Telegram buttons, web-only).
- Each uploaded audio segment must remain a standalone decodable file
  (one `MediaRecorder` start/stop per segment — never a timeslice chunk).
- All new timing/threshold numbers are env-overridable with a default and a
  comment naming their source (CoThinker or the operator's reasoning).
- German stays the literal Python constant (bitgleich); new strings get an
  English mirror entry per the `sprache.Texte`/`sprachen/en/` convention —
  do not hand-edit `docs/prompt-audit/texte-vor-sprache-a1.txt`, the baseline
  test allows new constants.
- Git: commit per step, `git add <exact paths>` only, no `-A`/`.`/`-a`, no
  destructive git ops, no push/merge/service restart.
- Baseline (this branch, before any change here): `5229 passed, 2 skipped,
  2 failed` (`tests/test_profil_bitgleich.py` — pre-existing drift from
  commit `43ca537`, unrelated to this work). Do not fix those two; do not
  make the failure list grow beyond them for reasons unrelated to this plan.

---

## Part A — Pause-based segmentation (VAD)

### Task A1: Env vars and server-rendered `data-*` attributes

**Files:**
- Modify: `interview_theater/web_chat.py:2313-2319` (`_segment_ms`) and the
  `chat_html()` `#fuss` markup (~line 1648)
- Test: `tests/test_web_chat_js.py`

**Interfaces:**
- Produces: `_vad_werte() -> dict` with keys `pause_ms`, `max_ms`,
  `min_speech_ms`, `rms`, `floor_faktor` (floats/ints), read once per
  `chat_html()` call from `os.environ`.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing test** — add to `tests/test_web_chat_js.py`:

```python
def test_die_vad_werte_kommen_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("IT_WEB_VAD_PAUSE_MS", "3000")
    monkeypatch.setenv("IT_WEB_VAD_MAX_MS", "60000")
    monkeypatch.setenv("IT_WEB_VAD_MIN_SPEECH_MS", "400")
    monkeypatch.setenv("IT_WEB_VAD_RMS", "0.02")
    monkeypatch.setenv("IT_WEB_VAD_FLOOR_FACTOR", "3.0")
    html_text = web_chat.chat_html("tok", modus=False, basis_url="", praefix="")
    assert 'data-vad-pause-ms="3000"' in html_text
    assert 'data-vad-max-ms="60000"' in html_text
    assert 'data-vad-min-speech-ms="400"' in html_text
    assert 'data-vad-rms="0.02"' in html_text
    assert 'data-vad-floor-faktor="3.0"' in html_text


def test_die_vad_werte_haben_vorgaben_ohne_umgebung(monkeypatch):
    for name in ("IT_WEB_VAD_PAUSE_MS", "IT_WEB_VAD_MAX_MS",
                 "IT_WEB_VAD_MIN_SPEECH_MS", "IT_WEB_VAD_RMS",
                 "IT_WEB_VAD_FLOOR_FACTOR"):
        monkeypatch.delenv(name, raising=False)
    werte = web_chat._vad_werte()
    assert werte == {
        "pause_ms": 2500, "max_ms": 90_000, "min_speech_ms": 500,
        "rms": 0.01, "floor_faktor": 2.5,
    }
```
(Adjust the `chat_html` call signature to match the real one found by reading
the file — check the existing `test_die_segmentlaenge_kommt_aus_der_umgebung`
test for the exact call pattern used today, and mirror it exactly.)

- [ ] **Step 2: Run to verify it fails** (`AttributeError: no _vad_werte`).

- [ ] **Step 3: Implement** — in `web_chat.py` near `_segment_ms()`:

```python
def _umgebungszahl(name: str, vorgabe: float, *, ganzzahl: bool) -> float:
    roh = (os.environ.get(name) or "").strip()
    if not roh:
        return vorgabe
    try:
        wert = float(roh)
    except ValueError:
        return vorgabe
    if wert <= 0:
        return vorgabe
    return int(wert) if ganzzahl else wert


def _vad_werte() -> dict:
    """Die fuenf VAD-Zahlen fuer den Pausen-Schnitt, einzeln ueberschreibbar.

    Herkunft (Betreiber-Entscheidung 02.10.2026, siehe
    .brainstorm-vad-brief.md): PAUSE_MS und MAX_MS aus CoThinker
    (``gateway/consumer.py --pause 2.5 --max-block 90``), MIN_SPEECH_MS aus
    CoThinker (``stt_server/args.py --vad_min_speech_ms 500``, Infomaniak-
    Pfad), RMS aus CoThinker (``settings.BUILT_IN_DEFAULTS
    vad_energy_threshold 0.01``). FLOOR_FACTOR ist NICHT aus CoThinker
    gemessen -- gesetzt, nicht gemessen, als Schutz gegen laute Workshop-
    Raeume (siehe Kommentar an der RMS-Schwelle im JS).
    """
    return {
        "pause_ms": _umgebungszahl("IT_WEB_VAD_PAUSE_MS", 2500, ganzzahl=True),
        "max_ms": _umgebungszahl("IT_WEB_VAD_MAX_MS", 90_000, ganzzahl=True),
        "min_speech_ms": _umgebungszahl(
            "IT_WEB_VAD_MIN_SPEECH_MS", 500, ganzzahl=True),
        "rms": _umgebungszahl("IT_WEB_VAD_RMS", 0.01, ganzzahl=False),
        "floor_faktor": _umgebungszahl(
            "IT_WEB_VAD_FLOOR_FACTOR", 2.5, ganzzahl=False),
    }
```

Add to the `#fuss` markup in `chat_html()`, next to the existing
`data-segment-ms="{...}"` attribute:

```python
vad = _vad_werte()
...
f'data-vad-pause-ms="{vad["pause_ms"]}" '
f'data-vad-max-ms="{vad["max_ms"]}" '
f'data-vad-min-speech-ms="{vad["min_speech_ms"]}" '
f'data-vad-rms="{vad["rms"]}" '
f'data-vad-floor-faktor="{vad["floor_faktor"]}" '
```

- [ ] **Step 4: Run to verify it passes.**

- [ ] **Step 5: Commit** —
  `git add interview_theater/web_chat.py tests/test_web_chat_js.py`
  `git commit -m "Web-VAD: fuenf Schnittwerte aus der Umgebung, data-Attribute am Fuss"`

---

### Task A2: Client VAD state machine — replace the fixed-interval cut

**Files:**
- Modify: `interview_theater/web_chat.py` inside `_CHAT_JS` — the region
  from `pegelAn` (was lines 1053-1072) through `beginneAufnahme`
  (was lines 1175-1191), and `neuesSegment`'s `onstop` (was lines 875-916).
- Test: `tests/test_web_chat_js.py` (string/regex assertions against
  `web_chat._CHAT_JS`, following the file's existing style), plus a
  best-effort extension of `tests/e2e/test_web_chat_e2e.py`'s `_MESSUNG`
  instrumentation (Task A3).

**Interfaces:**
- Consumes: `data-vad-*` attributes from Task A1 (`fuss.dataset.vadPauseMs`
  etc. — camelCase per the DOM `dataset` API, mirroring how
  `fuss.dataset.segmentMs` already reads `data-segment-ms`).
- Produces: the recorder lifecycle keeps the exact same contract
  (`neuesSegment`, `pruefeEnde`, `reiheEin`, `postAudio`) — only the decision
  of *when* to call `alt.stop(); sitzung.recorder = neuesSegment(sitzung);`
  changes, plus two new fields on each finished segment's `auftrag`:
  `grund` (`'pause'|'cap'|'ende'|null`) and `redeMs` (number|null), read by
  `postAudio` to append `&grund=...` to the upload URL (Task A4) and by the
  new upload-decision check in `onstop` (below).

**Design (read this before writing code — it is the one subtle part of this
whole plan):**

1. VAD state lives on `sitzung` (reset every time a *new* recorder actually
   starts recording, i.e. at the top of `beginneAufnahme`, right after
   `sitzung.recorder = neuesSegment(sitzung)`):
   - `sitzung.vadSegmentStart` — `Date.now()` when the current recorder
     began.
   - `sitzung.vadSpeechMs` — accumulated milliseconds, within the *current*
     recorder's lifetime, where RMS was above the speech threshold.
   - `sitzung.vadLetzteRede` — timestamp of the most recent tick where RMS
     was above threshold (`sitzung.vadSegmentStart` initially, so a pause
     cannot fire before any speech has been seen).
   - `sitzung.vadBoden` — a small rolling array of recent RMS samples
     (capped to `~5000 / PEGEL_TAKT_MS` entries) used to compute the
     adaptive noise floor.
   - `sitzung.vadAktiv` — `true` once `pegelAn` successfully created an
     `AnalyserNode` for this session; stays `false`/`undefined` if the
     browser threw (no `AudioContext`), in which case `beginneAufnahme`
     falls back to the OLD fixed `SEGMENT_MS` timer so recording still
     produces segments.
2. Every `pegelAn` tick (same 120 ms interval as today, now doing double
   duty): compute `rms` from `getFloatTimeDomainData`, update the level bar
   from the *existing* `getByteFrequencyData` call (unchanged, so the visual
   meter is byte-for-byte identical to today), then call `vadTick(sitzung,
   rms, Date.now())`.
3. `vadTick` updates the rolling floor, computes
   `schwelle = Math.max(RMS, boden * FLOOR_FACTOR)`, updates
   `vadSpeechMs`/`vadLetzteRede` if `rms > schwelle`, then decides whether to
   cut:
   - `kappe = (jetzt - sitzung.vadSegmentStart) >= MAX_MS` — hard cap,
     unconditional.
   - `pause = (jetzt - sitzung.vadLetzteRede) >= PAUSE_MS` — only meaningful
     once speech has been seen at least once (`vadLetzteRede` starts at
     segment-start, so a silent segment never spontaneously "pauses" before
     `MAX_MS` — it only ever gets cut by the cap, which is correct: an
     entirely silent 90 s block should still be flushed, not grow forever).
   - If `kappe`: always cut, `grund = 'cap'`.
   - Else if `pause` AND `vadSpeechMs >= MIN_SPEECH_MS`: cut, `grund =
     'pause'`.
   - Else if `pause` AND `vadSpeechMs < MIN_SPEECH_MS`: **do not cut** — this
     is the "carried into the next segment" rule, implemented as "the
     recorder simply keeps running" rather than literal blob concatenation
     (MediaRecorder output from two separate instances cannot be safely
     byte-concatenated into one decodable file — see the report for why this
     is a deliberate, flagged deviation from a literal reading of "carried
     over"). The next tick re-evaluates from the same `vadLetzteRede`, so if
     speech resumes `pause` becomes false again until the *next* real
     silence; if it stays silent, `kappe` will eventually fire.
4. On an actual cut, call `schneideSegment(sitzung, grund)`:
   ```js
   function schneideSegment(sitzung, grund) {
     var alt = sitzung.recorder;
     if (!alt) { return; }
     alt._grund = grund;
     alt._redeMs = sitzung.vadSpeechMs;
     if (alt.state !== 'inactive') { alt.stop(); }
     sitzung.recorder = neuesSegment(sitzung);
     sitzung.vadSegmentStart = Date.now();
     sitzung.vadSpeechMs = 0;
     sitzung.vadLetzteRede = sitzung.vadSegmentStart;
   }
   ```
5. `neuesSegment`'s `onstop` reads `r._grund`/`r._redeMs` (set by whoever
   stopped it — `schneideSegment` for VAD cuts, or the existing
   `pausiereInterview`/`beendeInterview` code for a manual flush, which must
   now also set `alt._grund = 'ende'; alt._redeMs = sitzung.vadSpeechMs;`
   before calling `.stop()`) and decides whether to build the `auftrag` at
   all:
   ```js
   r.onstop = function () {
     sitzung.offen -= 1;
     var auftrag = null;
     var redeMs = r._redeMs;
     var grund = r._grund || null;
     var genug = redeMs == null ||                 // kein VAD -- wie bisher
       (grund === 'ende' ? redeMs > 0 :             // Pause/Beenden: jede Rede reicht
        redeMs >= (sitzung.vadMinSpeechMs || 0));   // Schnitt: Mindestmass
     if (teile.length && !sitzung.verworfen && genug) {
       auftrag = {
         art: 'audio', sitzung: sitzung,
         blob: new Blob(teile, { type: teile[0].type || r.mimeType || 'audio/webm' }),
         dauer: Math.max(1, Math.round((Date.now() - von) / 1000)),
         grund: grund
       };
     }
     ...
   ```
   (the rest of the function — the `fertige`/`einzureihen` reordering and
   `pruefeEnde(sitzung)` call — is unchanged). A `grund === 'cap'` segment
   with `redeMs < MIN_SPEECH_MS` is the rare, explicitly-accepted edge case
   that gets dropped rather than merged — document this with a code comment
   at the `genug` check pointing at the same reasoning as point 3 above.
6. `beginneAufnahme` becomes:
   ```js
   function beginneAufnahme(sitzung) {
     if (sitzung.pausiert) { gibFrei(sitzung); return; }
     sitzung.legStart = Date.now();
     sitzung.recorder = neuesSegment(sitzung);
     sitzung.vadSegmentStart = Date.now();
     sitzung.vadSpeechMs = 0;
     sitzung.vadLetzteRede = sitzung.vadSegmentStart;
     sitzung.vadBoden = [];
     sitzung.gestartet = true;
     uhrAn(sitzung);
     pegelAn(sitzung);
     if (!sitzung.vadAktiv) {
       // Rueckfall ohne AnalyserNode: wie vor dieser Karte, feste Laenge --
       // sonst gaebe es nie einen Schnitt und das Interview liefe bis
       // Beenden in einem Stueck.
       sitzung.segmentTakt = setInterval(function () {
         if (!sitzung.recorder) { return; }
         var alt = sitzung.recorder;
         alt.stop();
         sitzung.recorder = neuesSegment(sitzung);
       }, SEGMENT_MS);
     }
   }
   ```
7. `pegelAn` becomes (keeping its name; the `getByteFrequencyData` block for
   the visual bar is untouched, copied verbatim from today):
   ```js
   function pegelAn(sitzung) {
     var Kontext = window.AudioContext || window.webkitAudioContext;
     if (!Kontext) { return; }
     try {
       var kontext = new Kontext();
       sitzung.kontext = kontext;
       if (kontext.state === 'suspended' && kontext.resume) { kontext.resume(); }
       var messer = kontext.createAnalyser();
       messer.fftSize = 256;
       kontext.createMediaStreamSource(sitzung.strom).connect(messer);
       var frequenzWerte = new Uint8Array(messer.frequencyBinCount);
       var zeitWerte = new Float32Array(messer.fftSize);
       var fuss = document.getElementById('fuss');
       var PAUSE_MS = parseInt(fuss.dataset.vadPauseMs, 10) || 2500;
       var MAX_MS = parseInt(fuss.dataset.vadMaxMs, 10) || 90000;
       var MIN_SPEECH_MS = parseInt(fuss.dataset.vadMinSpeechMs, 10) || 500;
       var RMS_SCHWELLE = parseFloat(fuss.dataset.vadRms) || 0.01;
       var BODEN_FAKTOR = parseFloat(fuss.dataset.vadFloorFaktor) || 2.5;
       var BODEN_FENSTER = Math.ceil(5000 / 120);
       sitzung.vadMinSpeechMs = MIN_SPEECH_MS;
       sitzung.vadAktiv = true;
       sitzung.pegelTakt = setInterval(function () {
         messer.getByteFrequencyData(frequenzWerte);
         var summe = 0;
         for (var i = 0; i < frequenzWerte.length; i++) { summe += frequenzWerte[i]; }
         if (pegelBalken) {
           pegelBalken.style.width =
             Math.min(100, (summe / frequenzWerte.length) * 2.2) + '%';
         }
         messer.getFloatTimeDomainData(zeitWerte);
         var quadratsumme = 0;
         for (var j = 0; j < zeitWerte.length; j++) {
           quadratsumme += zeitWerte[j] * zeitWerte[j];
         }
         var rms = Math.sqrt(quadratsumme / zeitWerte.length);
         sitzung.vadBoden.push(rms);
         if (sitzung.vadBoden.length > BODEN_FENSTER) { sitzung.vadBoden.shift(); }
         var sortiert = sitzung.vadBoden.slice().sort(function (a, b) { return a - b; });
         // Niedriges Perzentil als Rauschboden -- NICHT gemessen, gesetzt:
         // schuetzt gegen laute Raeume, Faktor und Perzentil sind eine
         // begruendete Annahme (siehe .brainstorm-vad-brief.md), kein
         // kalibrierter Wert wie PAUSE_MS/MAX_MS/MIN_SPEECH_MS/RMS_SCHWELLE.
         var boden = sortiert[Math.floor(sortiert.length * 0.1)] || 0;
         var schwelle = Math.max(RMS_SCHWELLE, boden * BODEN_FAKTOR);
         var jetzt = Date.now();
         if (rms > schwelle) {
           sitzung.vadSpeechMs += 120;
           sitzung.vadLetzteRede = jetzt;
         }
         if (!sitzung.recorder) { return; }
         var kappe = (jetzt - sitzung.vadSegmentStart) >= MAX_MS;
         var pause = (jetzt - sitzung.vadLetzteRede) >= PAUSE_MS;
         if (kappe) {
           schneideSegment(sitzung, 'cap');
         } else if (pause && sitzung.vadSpeechMs >= MIN_SPEECH_MS) {
           schneideSegment(sitzung, 'pause');
         }
       }, 120);
     } catch (e) { /* ohne Pegel geht es auch -- dann der feste Takt */ }
   }
   ```
   Note `schneideSegment` resets `vadSpeechMs`/`vadSegmentStart`/
   `vadLetzteRede` itself (step 4 above), so no double-reset here.
8. `pausiereInterview` and `beendeInterview` each already do
   `var alt = sitzung.recorder; sitzung.recorder = null; ... alt.stop();` —
   add `alt._grund = 'ende'; alt._redeMs = sitzung.vadSpeechMs;` immediately
   before each `alt.stop()` call (two call sites).
9. `postAudio` must send the cut reason so the server can persist it
   (needed by Part B's trigger condition (c)): change
   `fetch(weg('chat/audio?dauer=' + auftrag.dauer), ...)` to
   `fetch(weg('chat/audio?dauer=' + auftrag.dauer +
   (auftrag.grund ? '&grund=' + auftrag.grund : '')), ...)`.

- [ ] **Step 1: Write the failing tests** (string-assertion style, matching
  the file's convention) in `tests/test_web_chat_js.py`:

```python
def test_vad_ersetzt_den_festen_takt():
    js = web_chat._CHAT_JS
    assert "sitzung.segmentTakt = setInterval" in js  # Rueckfall bleibt
    assert "if (!sitzung.vadAktiv)" in js             # ... aber nur ohne VAD
    assert "function schneideSegment" in js
    assert "getFloatTimeDomainData" in js


def test_vad_liest_alle_fuenf_werte_aus_dem_fuss():
    js = web_chat._CHAT_JS
    for attribut in ("vadPauseMs", "vadMaxMs", "vadMinSpeechMs", "vadRms",
                     "vadFloorFaktor"):
        assert f"fuss.dataset.{attribut}" in js


def test_kappe_schneidet_immer_pause_nur_mit_genug_rede():
    js = web_chat._CHAT_JS
    takt = js[js.index("sitzung.pegelTakt = setInterval"):]
    takt = takt[:takt.index("}, 120)")]
    assert "schneideSegment(sitzung, 'cap')" in takt
    assert "schneideSegment(sitzung, 'pause')" in takt
    assert "sitzung.vadSpeechMs >= MIN_SPEECH_MS" in takt


def test_manuelle_schnitte_tragen_den_grund_ende():
    js = web_chat._CHAT_JS
    assert js.count("_grund = 'ende'") == 2  # pausiereInterview + beendeInterview


def test_onstop_laesst_zu_kurze_kappen_schnitte_weg():
    js = web_chat._CHAT_JS
    onstop = js[js.index("r.onstop = function"):js.index("r.start();")]
    assert "genug" in onstop
    assert "redeMs > 0" in onstop


def test_postaudio_haengt_den_grund_an():
    js = web_chat._CHAT_JS
    postaudio = js[js.index("function postAudio"):js.index("function postAudio") + 600]
    assert "auftrag.grund" in postaudio
```

- [ ] **Step 2: Run, verify every new test fails** (functions/strings don't
  exist yet).

- [ ] **Step 3: Implement** the changes described in points 1-9 above,
  directly in `_CHAT_JS`.

- [ ] **Step 4: Run the full `tests/test_web_chat_js.py` file** — all 48
  pre-existing tests plus the new ones must pass. Pay special attention to:
  `test_das_js_startet_einen_eigenen_recorder_je_segment` (still true — VAD
  still uses stop+restart, never a timeslice), `test_pausieren_sendet_kein_fertig_und_keinen_befehl`,
  `test_beginneaufnahme_ist_der_einzige_ort_der_die_aufnahme_beginnt`,
  `test_das_js_ist_syntaktisch_gueltig` (run `node --check` yourself too if
  node is available, don't rely on the test auto-skipping).

- [ ] **Step 5: Commit** —
  `git add interview_theater/web_chat.py tests/test_web_chat_js.py`
  `git commit -m "Web-VAD: Pausen-Schnitt statt fester Segmentlaenge (Part A)"`

---

### Task A3: Extend the e2e harness with a controllable fake analyser

**Files:**
- Modify: `tests/e2e/test_web_chat_e2e.py` (`_MESSUNG` init script, ~lines
  101-184)

**Interfaces:**
- Produces: `window.__t.setzeRms(wert)` callable from Playwright
  (`page.evaluate("window.__t.setzeRms(0.5)")`) to drive the fake analyser's
  `getFloatTimeDomainData`/`getByteFrequencyData` output deterministically.

- [ ] **Step 1: Write the failing e2e test** (will be skipped without
  Playwright, that's expected and must be stated in the report):

```python
def test_vad_schneidet_nach_pause(seite_mit_segment_ms, context, ...):
    # Pseudocode shape -- follow the existing fixtures/helpers in this file
    # exactly (look at an existing interview-recording test for the real
    # page/context fixture names before writing this).
    page.evaluate("window.__t.setzeRms(0.5)")  # Rede
    page.wait_for_timeout(600)
    page.evaluate("window.__t.setzeRms(0.0)")  # Stille
    page.wait_for_timeout(2800)                # > PAUSE_MS (Testwert kleiner gesetzt per env)
    assert page.evaluate("window.__t.starts") >= 2
```

- [ ] **Step 2: Extend `_MESSUNG`** to intercept `AudioContext.prototype
  .createAnalyser` and return an object whose `getByteFrequencyData`/
  `getFloatTimeDomainData` fill the buffer from a controllable
  `window.__t.rms` value (sine-free — just fill every sample with that RMS
  value, since the implementation only takes the root-mean-square, a
  constant-value buffer has exactly that RMS).

- [ ] **Step 3: Run** `pytest tests/e2e/test_web_chat_e2e.py -k vad` in the
  dedicated e2e venv if available in this environment; if Playwright/the e2e
  venv is not available here, say so explicitly in the report rather than
  claiming it passed — do not mark this step done without having actually
  run it once.

- [ ] **Step 4: Commit** —
  `git add tests/e2e/test_web_chat_e2e.py`
  `git commit -m "e2e: fake Analyser-Knoten fuer VAD-Tests"`

---

### Task A4: Server-side limits sized for 90 s segments

**Files:**
- Modify: `interview_theater/aufnahme.py` (`BUDGET_KURZ_S`), comment at
  `web_chat.py:52` (`MAX_AUDIO_BYTES` rationale), comment at
  `web_chat.py` near line 275 (`HINWEIS_AB_S` comparison), `web_grenze.py`
  (`UPLOADS_JE_STUNDE` derivation comment)
- Modify: `interview_theater/web_chat.py` `_audio()` handler — persist the
  new `grund` query parameter (Task A2 step 9) into the `aufnahme` row.
- Modify: `interview_theater/db.py` — additive migration for
  `aufnahme.schnittgrund TEXT`.
- Modify: `interview_theater/repo.py` — `lege_aufnahme_an` gains an optional
  `schnittgrund` parameter; `web_kanal.hole_updates`/`aufnahme.empfange`
  thread it through from the web_post row (same pattern as `endung`).
- Test: `tests/test_db.py` or wherever migrations are tested, plus
  `tests/test_aufnahme.py`.

**Interfaces:**
- Produces: `aufnahme.schnittgrund` column (`'pause'|'cap'|'ende'|NULL`),
  readable via `repo.hole_aufnahme`/whatever existing row-read function
  exists (check `repo.py` for the actual accessor name before writing code —
  do not invent one).

- [ ] **Step 1: Check `BUDGET_KURZ_S`.** Since `klasse='kurz'` segments can
  now be up to 90 s (same as `klasse='teil'`/interview parts), and
  `BUDGET_KURZ_S = 45` is a transcription-time budget (not a duration cap),
  change it to reuse `BUDGET_LANG_S` for any segment whose reported `dauer`
  exceeds the old 45 s budget, OR simplest and safest: just set
  `BUDGET_KURZ_S = BUDGET_LANG_S` (both become 90) since a `kurz` segment is
  no longer guaranteed short. Write the failing test first:

```python
def test_budget_kurz_reicht_fuer_ein_90s_segment():
    assert aufnahme.BUDGET_KURZ_S >= 90
```

  Then: `BUDGET_KURZ_S = BUDGET_LANG_S` in `aufnahme.py` (keep
  `BUDGET_LANG_S` as the named source of truth; add a one-line comment
  explaining why they're now equal — VAD segments up to 90 s regardless of
  class).

- [ ] **Step 2: Update the two stale comments** (`web_chat.py:52` and the
  `HINWEIS_AB_S` comparison comment near line 275) to say "bis zu 90 s" and
  drop the "45 s" framing — these are comments only, no behavior change, no
  test needed, but include the new wording verbatim in the commit diff
  (check that the current comment text actually says "45 s" first — quote
  the real text with Read before editing, do not guess the surrounding
  lines).

- [ ] **Step 3: Re-derive `web_grenze.UPLOADS_JE_STUNDE`.** The current
  comment derives 150 from `3600/45 = 80` uploads/hour with ~2x headroom.
  With pause-based cutting, segment count per hour depends on how choppy the
  speech is, not a fixed interval — CoThinker's own measurement (quoted in
  the brief) is "2-5 cuts per minute" in a brainstorm-like setting, i.e. up
  to 300/hour in the choppiest case. Read the current value and comment with
  Read first, then raise `UPLOADS_JE_STUNDE` to `400` (comfortably above the
  measured CoThinker ceiling of 300, keeping the same "headroom" philosophy
  as the original 150-vs-80 ratio) and rewrite the comment to cite the
  CoThinker numbers instead of `3600/45`. Add/adjust a test if one already
  pins the old value (`grep -rn UPLOADS_JE_STUNDE tests/`).

- [ ] **Step 4: Add `aufnahme.schnittgrund` column** — write the failing
  migration test first (follow the exact pattern of an existing additive
  migration test, e.g. for `aufnahme.uebernommen_von` — grep `db.py` and its
  test file for that migration and copy its shape exactly, including the
  `CREATE TABLE`/`ALTER TABLE ... ADD COLUMN` idiom used), then add the
  column in `db._migriere_fehlende_spalten` (or wherever the additive
  migrations list lives — confirm the exact function/list name by reading
  `db.py` before writing).

- [ ] **Step 5: Thread `grund` from upload to the `aufnahme` row.** In
  `web_chat._audio()`, read `felder = urllib.parse.parse_qs(...)` (however
  the handler already parses `dauer` from the query string — mirror that
  exactly) to also read `grund`, and pass it into
  `repo.lege_web_post_an(..., grund=grund)` — check whether `web_post` needs
  its own column too (it probably does, since `hole_updates` builds the
  Telegram-shaped update dict from `web_post` columns, the same way it
  already does for `mime`/`dauer`) — add `web_post.schnittgrund` via the
  same additive-migration mechanism if so, and have `hole_updates` put it on
  `n["schnittgrund"]`, consumed by `aufnahme.empfange` into
  `repo.lege_aufnahme_an(..., schnittgrund=n.get("schnittgrund"))`.

- [ ] **Step 6: Run the targeted tests**, then the full suite once at the
  end of Part A (see the top-level Git-rules section).

- [ ] **Step 7: Commit** —
  `git add interview_theater/aufnahme.py interview_theater/web_chat.py interview_theater/web_grenze.py interview_theater/db.py interview_theater/repo.py interview_theater/web_kanal.py tests/...`
  `git commit -m "Server: Limits und Schnittgrund fuer bis zu 90s-Segmente (Part A Abschluss)"`

---

## Part B — "🎙 Brainstorm mithören" (Phase 4, web only)

### Task B1: Pure trigger-threshold function (no model, no I/O)

**Files:**
- Create: `interview_theater/brainstorm.py`
- Test: `tests/test_brainstorm.py`

**Interfaces:**
- Produces:
  - `MIN_ZEICHEN`, `MIN_ABSTAND_S`, `MIN_ZEICHEN_BEI_ENDE` module constants
    (env-overridable via `IT_BRAINSTORM_MIN_ZEICHEN` [1200],
    `IT_BRAINSTORM_MIN_ABSTAND_S` [90] — follow the exact `os.environ.get`
    pattern used by `kosten.deckel()`/`kontext.zeichengrenze()`, read at
    call time, not at import time).
  - `soll_reagieren(*, neue_zeichen: int, sekunden_seit_letzter_reaktion: float, letzter_schnittgrund: str | None, ist_abschluss: bool, unreagierte_zeichen: int) -> bool`
    — pure function, the single decision point for "fire one stage-card
    turn now."

- [ ] **Step 1: Write the failing tests:**

```python
import pytest
from interview_theater import brainstorm


def test_kein_trigger_unter_der_zeichengrenze():
    assert not brainstorm.soll_reagieren(
        neue_zeichen=1199, sekunden_seit_letzter_reaktion=200,
        letzter_schnittgrund="pause", ist_abschluss=False,
        unreagierte_zeichen=1199,
    )


def test_trigger_bei_genug_zeichen_abstand_und_pausenschnitt():
    assert brainstorm.soll_reagieren(
        neue_zeichen=1200, sekunden_seit_letzter_reaktion=90,
        letzter_schnittgrund="pause", ist_abschluss=False,
        unreagierte_zeichen=1200,
    )


def test_kein_trigger_bei_kappen_schnitt():
    assert not brainstorm.soll_reagieren(
        neue_zeichen=5000, sekunden_seit_letzter_reaktion=200,
        letzter_schnittgrund="cap", ist_abschluss=False,
        unreagierte_zeichen=5000,
    )


def test_kein_trigger_zu_kurz_nach_der_letzten_reaktion():
    assert not brainstorm.soll_reagieren(
        neue_zeichen=5000, sekunden_seit_letzter_reaktion=10,
        letzter_schnittgrund="pause", ist_abschluss=False,
        unreagierte_zeichen=5000,
    )


def test_abschluss_triggert_schon_ab_150_zeichen_ohne_pausenschnitt():
    assert brainstorm.soll_reagieren(
        neue_zeichen=150, sekunden_seit_letzter_reaktion=5,
        letzter_schnittgrund="cap", ist_abschluss=True,
        unreagierte_zeichen=150,
    )


def test_abschluss_ohne_trigger_unter_150():
    assert not brainstorm.soll_reagieren(
        neue_zeichen=149, sekunden_seit_letzter_reaktion=5,
        letzter_schnittgrund="cap", ist_abschluss=True,
        unreagierte_zeichen=149,
    )


def test_schwellen_kommen_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "500")
    assert brainstorm.min_zeichen() == 500
```

- [ ] **Step 2: Run, verify failure** (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `interview_theater/brainstorm.py`:

```python
"""Die Reaktionsschwelle fuer den Brainstorm-Modus (Phase 4, nur Web).

Reine Funktionen, kein Modellaufruf, kein SQL -- die EINE Stelle, die
entscheidet, ob JETZT eine Buehnenkarte entstehen soll. Herkunft der Zahlen:
.brainstorm-vad-brief.md, CoThinker-Referenzannotationen (3 Sitzungen, 117
Gedanken, 53 Themen, gemessen 02.10.2026): ein Gedanke ist median 50 s /
614 Zeichen (p25-p75 250-1451), ein Thema median 154 s / 1868 Zeichen,
Sprechtempo ~16 Zeichen/s. 1200 Zeichen ~ zwei Gedanken ~ 75 s Sprechzeit ->
eine Karte etwa alle 1,5-2,5 min, ungefaehr einmal je Themenbogen. Die Daten
stammen aus Erwachsenen-Meetings, NICHT aus Schueler-Brainstorms -- deshalb
bleiben alle Schwellen ueber die Umgebung nachjustierbar.
"""

import os

VORGABE_MIN_ZEICHEN = 1200
VORGABE_MIN_ABSTAND_S = 90
VORGABE_MIN_ZEICHEN_BEI_ABSCHLUSS = 150


def _umgebungszahl(name: str, vorgabe: int) -> int:
    roh = (os.environ.get(name) or "").strip()
    if not roh:
        return vorgabe
    try:
        wert = int(roh)
    except ValueError:
        return vorgabe
    return wert if wert > 0 else vorgabe


def min_zeichen() -> int:
    return _umgebungszahl("IT_BRAINSTORM_MIN_ZEICHEN", VORGABE_MIN_ZEICHEN)


def min_abstand_s() -> int:
    return _umgebungszahl("IT_BRAINSTORM_MIN_ABSTAND_S", VORGABE_MIN_ABSTAND_S)


def min_zeichen_bei_abschluss() -> int:
    return _umgebungszahl(
        "IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS",
        VORGABE_MIN_ZEICHEN_BEI_ABSCHLUSS,
    )


def soll_reagieren(
    *, neue_zeichen: int, sekunden_seit_letzter_reaktion: float,
    letzter_schnittgrund: str | None, ist_abschluss: bool,
    unreagierte_zeichen: int,
) -> bool:
    """Code-Entscheidung, kein Modellaufruf (Zusage 2 bleibt unberuehrt --
    das hier entscheidet nur OB, nicht WAS die Karte sagt)."""
    if ist_abschluss:
        return unreagierte_zeichen >= min_zeichen_bei_abschluss()
    return (
        unreagierte_zeichen >= min_zeichen()
        and sekunden_seit_letzter_reaktion >= min_abstand_s()
        and letzter_schnittgrund == "pause"
    )
```

- [ ] **Step 4: Run, verify all pass.**

- [ ] **Step 5: Commit** —
  `git add interview_theater/brainstorm.py tests/test_brainstorm.py`
  `git commit -m "Brainstorm: reine Reaktionsschwelle (code, kein Modellaufruf)"`

---

### Task B2: DB schema — silent brainstorm segments and stage cards

**Files:**
- Modify: `interview_theater/db.py` (additive migrations)
- Modify: `interview_theater/repo.py` (new functions)
- Test: wherever `db.py` migrations are tested + a new `tests/test_repo_brainstorm.py`

**Interfaces:**
- Produces:
  - `arbeitsstand.brainstorm_zeichen_seit_reaktion INTEGER DEFAULT 0`,
    `arbeitsstand.brainstorm_reaktion_am TEXT` (two new columns — a
    singleton per group, same shape as `laengen_faktor`/`phase_angeboten`).
  - New table `buehnenkarte` (append-only, same shape as `szenenfassung`):
    `id, chat_id, erstellt_am, text, modell`.
  - `repo.merke_brainstorm_segment(conn, chat_id, zeichen: int) -> None` —
    adds to `brainstorm_zeichen_seit_reaktion`.
  - `repo.markiere_brainstorm_reaktion(conn, chat_id, jetzt_iso: str) -> None`
    — resets the counter to 0 and sets `brainstorm_reaktion_am`.
  - `repo.brainstorm_stand(conn, chat_id) -> dict` — returns
    `{"zeichen_seit_reaktion": int, "reaktion_am": str | None}`.
  - `repo.lege_buehnenkarte_an(conn, chat_id, text: str, modell: str) -> int`
    (returns new id).
  - `repo.buehnenkarten(conn, chat_id, hoechstens: int = 20) -> list[dict]`
    — newest first.
  - `repo.brainstorm_transkript(conn, chat_id) -> str` — the full,
    append-only phase-4 brainstorm transcript text (concatenation of every
    silently-stored brainstorm segment's transcript in chronological order;
    confirm the exact `nachricht`/`aufnahme` query shape against how
    `repo.unextrahierte`/`repo.letzte_nachrichten` already filter by
    `typ`/`klasse` before writing this — do not duplicate a different
    filtering convention).

- [ ] **Step 1: Write failing tests** for each new `repo` function above,
  against an in-memory/temp DB fixture (copy the fixture pattern from an
  existing `tests/test_repo_*.py` file — do not invent a new DB setup
  helper).

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement** the migrations and functions. Keep
  `buehnenkarte` append-only (no `UPDATE`/`DELETE` function for it — same
  rule as `journal`/`szenenfassung`).

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** —
  `git add interview_theater/db.py interview_theater/repo.py tests/...`
  `git commit -m "Brainstorm: Schema fuer stille Segmente und Buehnenkarten"`

---

### Task B3: Silent segment storage — brainstorm class, no erkenner, no turn

**Files:**
- Modify: `interview_theater/aufnahme.py` — wherever `klasse_fuer`/
  `_kurz_abschliessen` route a finished `kurz` transcription into a normal
  conversational contribution (`_kurz_abschliessen`, confirmed by the
  research to live around lines 749-807).
- Test: `tests/test_aufnahme.py`

**Interfaces:**
- Consumes: `phasen.aktuelle(conn, chat_id)` to detect phase 4;
  `aufnahme.schnittgrund` (Task A4) on the `aufnahme` row.
- Produces: a new branch in the `kurz`-finalization path — when phase is 4
  AND the group's channel is web AND a (to-be-added, see Task B4) session
  flag says "this kurz segment came from the brainstorm button, not PTT or
  a stray voice message", the segment:
  - Still gets transcribed via the normal STT path (reuse everything up to
    the transcript being available — do not duplicate `stt.transkribiere`
    call sites).
  - Does NOT call `erkenner.erkenne_in_aufnahme` (skip the branch, same as
    `klm is None` already skips it today — just add this condition to the
    existing `if klm is not None` guard).
  - Does NOT update the `nachricht` row to `typ='text'` (which would make it
    a conversational turn trigger) — instead calls
    `repo.aktualisiere_transkribierte_nachricht(..., versteckt=True)` (the
    existing `TYP_TRANSKRIPT` path, already proven to keep a row out of all
    three windows) — OR, if that path's "hidden" semantics turn out to also
    suppress it from `repo.brainstorm_transkript` (Task B2), add a distinct
    marker instead; read `repo.TYP_TRANSKRIPT`'s existing consumers first
    (`_OHNE_TRANSKRIPT_ECHO`) and decide which is correct — the key
    requirement is: never visible as a chat bubble requiring reply, never
    read by the conversational/erkenner/journal windows, but IS readable by
    `repo.brainstorm_transkript`.
  - Calls `repo.merke_brainstorm_segment(conn, chat_id, len(transkript))`
    (Task B2).
  - Evaluates `brainstorm.soll_reagieren(...)` (Task B1) using
    `repo.brainstorm_stand` plus the segment's own `schnittgrund` and
    whether this call is happening because of a Pause/Beenden flush
    (`ist_abschluss`) — if true, hand off to Task B5's stage-card trigger
    (do not call it inline in this function if it's the first segment of a
    batch; the existing per-segment processing call site is the right hook
    per the research's §5 conclusion: "piggyback on the next incoming
    update").
  - Never triggers `_zug_und_erkenner`/the normal conversational reply.

- [ ] **Step 1: Write failing tests**, e.g.:

```python
def test_brainstorm_segment_wird_nicht_typ_text(conn_mit_gruppe_in_phase_4):
    ...
    aufnahme._kurz_abschliessen(conn, ..., brainstorm=True)
    zeile = conn.execute(
        "SELECT typ FROM nachricht WHERE chat_id=? AND message_id=?",
        (chat_id, message_id),
    ).fetchone()
    assert zeile["typ"] != "text"


def test_brainstorm_segment_ruft_erkenner_nicht(conn_mit_gruppe_in_phase_4, monkeypatch):
    aufgerufen = []
    monkeypatch.setattr(erkenner, "erkenne_in_aufnahme",
                         lambda *a, **k: aufgerufen.append(1))
    aufnahme._kurz_abschliessen(conn, ..., brainstorm=True)
    assert not aufgerufen


def test_brainstorm_segment_zaehlt_zeichen(conn_mit_gruppe_in_phase_4):
    aufnahme._kurz_abschliessen(conn, ..., brainstorm=True)
    stand = repo.brainstorm_stand(conn, chat_id)
    assert stand["zeichen_seit_reaktion"] > 0
```

  (Build the exact fixture/helper names by reading the top of
  `tests/test_aufnahme.py` first — do not invent a different DB-setup
  convention than what that file already uses.)

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run, verify pass** — also re-run the full
  `tests/test_aufnahme.py` and `tests/test_korpus.py` (the erkenner
  allow-list change must not affect any existing corpus case).

- [ ] **Step 5: Commit** —
  `git add interview_theater/aufnahme.py tests/test_aufnahme.py`
  `git commit -m "Brainstorm: Segmente still speichern, kein Erkenner, kein Zug"`

---

### Task B4: Client — "🎙 Brainstorm mithören" button and session

**Files:**
- Modify: `interview_theater/web_chat.py` — `_JS_TEXTE`/`_TEXT_*` constants,
  `chat_html()` markup, `_CHAT_JS` session machinery (generalize
  `sitzung.art`).
- Test: `tests/test_web_chat_js.py`

**Interfaces:**
- Produces: a second button rendered only when the page's phase is 4 (the
  handler needs the current phase — check how `chat_html()` currently
  learns `modus`/interview state from `web_daten`, and add a `phase: int`
  parameter the same way, sourced from `web_daten.gruppe_phase` or
  equivalent — confirm the real accessor name by reading `web_daten.py`
  before writing code; do not invent one).
- A new `zustand.brainstorm` session object, structurally identical to
  `zustand.aufnahme` (same `naechsteNr`/`fertige`/`einzureihen`/`offen`
  bookkeeping, same `neuesSegment`/VAD functions reused verbatim — these
  functions already take a generic `sitzung` parameter and must NOT be
  duplicated), but:
  - started/stopped WITHOUT sending `{art:'befehl', an:true/false}` (no
    server-side "mode" to toggle — classification is already `kurz` by
    default since brainstorm never touches `gruppe.interviewmodus_seit`).
  - segments upload immediately via the same `postAudio`/queue path, with
    an additional query flag `&brainstorm=1` so the server-side handler
    (Task B3) knows to route it silently instead of as a normal `kurz`
    contribution-with-turn.
  - no `bereit()` gate (nothing to wait for — see design note above).

- [ ] **Step 1: Write failing tests:**

```python
def test_brainstorm_knopf_nur_in_phase_4():
    html_ohne = web_chat.chat_html("tok", modus=False, basis_url="", praefix="", phase=3)
    html_mit = web_chat.chat_html("tok", modus=False, basis_url="", praefix="", phase=4)
    assert "brainstorm" not in html_ohne.lower()
    assert _TEXT_BRAINSTORM_AN.split()[-1] in html_mit  # "mithören" o.ae. im Markup


def test_brainstorm_segmente_tragen_das_flag():
    js = web_chat._CHAT_JS
    postaudio = js[js.index("function postAudio"):js.index("function postAudio") + 600]
    assert "brainstorm=1" in postaudio or "sitzung.art" in postaudio


def test_brainstorm_sendet_keinen_befehl():
    js = web_chat._CHAT_JS
    # the brainstorm start/stop path must not call reiheEin({art:'befehl', ...})
    # for art === 'brainstorm' -- assert the generalized check exists
    assert "sitzung.art === 'interview'" in js


def test_ui_texte_stehen_nicht_als_literal_im_js_bleibt_gruen():
    # re-run the EXISTING test by name to confirm new _TEXT_BRAINSTORM_* also
    # goes through _JS_TEXTE, not as a literal
    ...
```

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement:**
  - New Python constants: `_TEXT_BRAINSTORM_AN = "🎙 Brainstorm mithören"`,
    `_TEXT_BRAINSTORM_LAEUFT = "● Hört mit · {zeit}"` — add both to
    `_JS_TEXTE`.
  - `chat_html()` gains a `phase: int` parameter; when `phase == 4`, render
    the brainstorm button as the primary `#interview`-styled button and the
    existing interview button smaller/secondary (exact markup/CSS is your
    call per the brief — keep it to the existing `.leiste`/button CSS
    classes already in `_CSS_CHAT` rather than inventing a parallel style
    system).
  - Generalize `sitzung.art` (`'interview'|'brainstorm'`) through
    `beginneAufnahme`, `pausiereInterview`, `fortsetzeInterview`,
    `beendeInterview`: every place that currently does
    `reiheEin({ art: 'befehl', an: ..., ... })` must guard with
    `if (sitzung.art === 'interview') { ... }` — for `'brainstorm'`,
    `beendeInterview`'s equivalent (rename or branch, your call, report it)
    just stops the recorder and flushes the last segment via `pruefeEnde`
    without ever enqueuing a `'befehl'` job.
  - `postAudio` appends `&brainstorm=1` when `auftrag.sitzung.art ===
    'brainstorm'`.

- [ ] **Step 4: Run the FULL `tests/test_web_chat_js.py`** — this task has
  the highest risk of breaking one of the 48 existing interview-recording
  tests, because it changes shared functions. If any existing test's
  assumption (e.g. "the only thing that calls `reiheEin({art:'befehl'})` is
  the interview path") needs updating because it's now conditional on
  `sitzung.art`, update that test's assertion to be art-aware rather than
  weakening what it checks — i.e. keep it asserting "still true when
  `art==='interview'`."

- [ ] **Step 5: Commit** —
  `git add interview_theater/web_chat.py tests/test_web_chat_js.py`
  `git commit -m "Brainstorm: Knopf und Aufnahme-Sitzung (Phase 4, ohne Modus-Befehl)"`

---

### Task B5: Server — `chat/audio` handler honors `&brainstorm=1`

**Files:**
- Modify: `interview_theater/web_chat.py` `_audio()` handler.
- Test: `tests/test_web_chat_js.py` (HTTP-level, using the existing `seite`
  fixture pattern).

**Interfaces:**
- Consumes: query param `brainstorm` (`"1"` or absent).
- Produces: `web_post.herkunft` (or reuse an existing free-text column if
  one exists — check `web_post`'s schema before adding a column) set to
  `'brainstorm'`, read by `web_kanal.hole_updates` into `n["brainstorm"] =
  True`, consumed by `aufnahme.empfange`/`klasse_fuer` to force `klasse =
  'kurz'` AND tag the resulting `aufnahme` row so Task B3's branch
  recognizes it (reuse the `schnittgrund` column's presence plus this new
  flag, or add `aufnahme.brainstorm INTEGER DEFAULT 0` — prefer the explicit
  boolean column over overloading `schnittgrund`, since `schnittgrund`
  already has a real job (Task A4) orthogonal to this one).

- [ ] **Step 1: Write failing test** asserting a POST with `&brainstorm=1`
  results in a `web_post` row carrying the flag, and without it the row
  doesn't.

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement** (additive migration for the new column, handler
  change, `hole_updates`/`empfange` plumbing — mirror the `endung` plumbing
  pattern exactly).

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** —
  `git add interview_theater/web_chat.py interview_theater/web_kanal.py interview_theater/aufnahme.py interview_theater/db.py interview_theater/repo.py tests/...`
  `git commit -m "Brainstorm: Flag vom Upload bis zur aufnahme-Zeile durchreichen"`

---

### Task B6: Claude stage-card call

**Files:**
- Create: `interview_theater/buehnenkarte.py`
- Create: `interview_theater/prompts/buehnenkarte.md` (+ English mirror
  under `sprachen/en/prompts/buehnenkarte.md`)
- Test: `tests/test_buehnenkarte.py`

**Interfaces:**
- Consumes: `szene_claude.ist_aktiv(e, conn, chat_id)`,
  `szene_claude.prosa(conn, e, klient, chat_id, system, nutzer, art, timeout)`,
  `repo.brainstorm_transkript`, `repo.lege_buehnenkarte_an` (Task B2),
  `anweisungen` module's hot-reload pattern for the prompt file (read
  `anweisungen.py` for the exact loader function name — likely something
  like `anweisungen.lade(name)` — before writing code; do not invent a
  parallel prompt-loading mechanism).
- Produces: `erzeuge(conn, e, klient, chat_id, *, stueckkarte: dict,
  zusammenfassung_1_bis_3: str) -> str | None` — returns the card text, or
  `None` if the model answered literally `NICHTS` (per the brief: "may
  answer NICHTS -> nothing changes"). Without USA consent
  (`szene_claude.ist_aktiv` false), falls back to the normal Infomaniak
  `llm.LLM` chat-completion path (reuse `llm.LLM.schema`/whatever the
  existing non-Claude call signature is — read `llm.py` before writing;
  this function must work on BOTH paths, branching once at the top on
  `ist_aktiv`).
- Own budget per the brief: `IT_BRAINSTORM_TRANSKRIPT_ZEICHEN` (default
  `200_000`), NOT the normal `kontext.ZEICHEN_GRENZE_VORGABE` — if the
  transcript exceeds it, truncate (oldest first, matching the project's
  established cut order) and call
  `repo.merke_vorfall(conn, chat_id, e.bot_name, "brainstorm_transkript_gekuerzt", detail)`
  following the exact `vorfall` pattern already quoted from `kontext.py`.

- [ ] **Step 1: Write the prompt file** `interview_theater/prompts/buehnenkarte.md`
  (German, the literal content — this is prose, not code, write the actual
  instruction text per the brief's description: "a creative sparring
  partner writing stage cards ... sparse, concrete, no lecture, every
  section optional, never repeats long passages verbatim, never asks to
  record an interview, never uses interview material", listing the six
  possible sections by name (Thema gerade / Was entstanden ist / Bezüge /
  Vorschläge / Rückfrage / Als Nächstes) and the `NICHTS` escape hatch).
  Follow the existing `prompts/*.md` file-header convention (a
  `prompt_version` line, per AGENTS.md's note on `prompts/dramaturgie/`) —
  check one existing prompt file's header format first and match it.

- [ ] **Step 2: Write the failing tests:**

```python
def test_nichts_antwort_ergibt_keine_karte(monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(szene_claude, "prosa", lambda *a, **k: "NICHTS")
    ergebnis = buehnenkarte.erzeuge(conn, e, klient, chat_id,
                                     stueckkarte={}, zusammenfassung_1_bis_3="")
    assert ergebnis is None


def test_ohne_einwilligung_faellt_auf_infomaniak_zurueck(monkeypatch):
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: False)
    aufgerufen = {}
    monkeypatch.setattr(llm.LLM, "schema", lambda *a, **k: aufgerufen.setdefault("x", True) or {"text": "Thema gerade: Testthema"})
    buehnenkarte.erzeuge(conn, e, klient, chat_id, stueckkarte={}, zusammenfassung_1_bis_3="")
    assert aufgerufen.get("x")


def test_grosses_transkript_wird_ab_eigenem_budget_gekuerzt(monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_TRANSKRIPT_ZEICHEN", "100")
    monkeypatch.setattr(repo, "brainstorm_transkript", lambda *a, **k: "x" * 500)
    monkeypatch.setattr(szene_claude, "ist_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(szene_claude, "prosa", lambda *a, **k: "Thema gerade: Test")
    buehnenkarte.erzeuge(conn, e, klient, chat_id, stueckkarte={}, zusammenfassung_1_bis_3="")
    zeile = conn.execute(
        "SELECT art FROM vorfall WHERE chat_id=? ORDER BY id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()
    assert zeile["art"] == "brainstorm_transkript_gekuerzt"
```

  (Mock boundaries match exactly what the file under test imports — check
  whether `buehnenkarte.py` imports `szene_claude`/`llm`/`repo` as modules
  [`from interview_theater import szene_claude`] or via `from ... import
  name`, and monkeypatch accordingly; this matters for whether `monkeypatch
  .setattr(szene_claude, ...)` vs `monkeypatch.setattr(buehnenkarte,
  "ist_aktiv", ...)` is the correct target.)

- [ ] **Step 3: Run, verify failure.**

- [ ] **Step 4: Implement** `interview_theater/buehnenkarte.py`, reusing
  `szene_claude.prosa`'s call contract exactly (it already does
  `kosten.pruefe` internally, books an `aufruf` row, and raises
  `ClaudeFehler` on a truncated/failed response — catch `ClaudeFehler` at
  the call site here and treat it as "no card this time" with a `vorfall`,
  per the project's "a gescheiterter Nachpass ist unsichtbar" convention —
  the group never sees a half-written stage card).

- [ ] **Step 5: Run, verify pass.**

- [ ] **Step 6: English mirror.** Add
  `sprachen/en/prompts/buehnenkarte.md` with the same structure translated,
  following the exact convention described in AGENTS.md under "Sprache":
  read one existing `sprachen/en/prompts/*.md` file first to match its
  format precisely (front matter, section naming) before writing the
  English version.

- [ ] **Step 7: Confirm `tests/test_sprache_bitgleich.py` stays green** —
  run it; a new prompt file is a new section, allowed by the test's own
  rule ("eine neue Konstante ist keine Undichtigkeit"); if it fails, read
  the failure output before assuming it's this change.

- [ ] **Step 8: Commit** —
  `git add interview_theater/buehnenkarte.py interview_theater/prompts/buehnenkarte.md sprachen/en/prompts/buehnenkarte.md tests/test_buehnenkarte.py`
  `git commit -m "Brainstorm: Buehnenkarten-Prompt und Claude-Aufruf (mit Infomaniak-Rueckfall)"`

---

### Task B7: Wire the trigger into the silent-segment path + chat system line

**Files:**
- Modify: `interview_theater/aufnahme.py` (the branch added in Task B3)
- Modify: `interview_theater/bot.py` or wherever the brainstorm turn should
  run in its own thread (reuse the existing `pool.submit`/thread pattern
  already used for `_zug_und_erkenner` and `szene.starte` — do not invent a
  new threading primitive).
- Test: `tests/test_aufnahme.py` or a new `tests/test_brainstorm_turn.py`

**Interfaces:**
- Consumes: `brainstorm.soll_reagieren` (B1), `buehnenkarte.erzeuge` (B6),
  `repo.markiere_brainstorm_reaktion`/`repo.lege_buehnenkarte_an` (B2).
- Produces: after a successful card, send **at most one** short chat system
  line — per the brief: "Neue Karte im Tab Bühne" — but ONLY if the chat's
  newest message isn't already that same line (the brief's "no stacking"
  rule). Mirror the existing single-line-dedup pattern already used
  somewhere in this codebase for a similar "don't repeat the same notice
  twice in a row" rule (grep for an existing example — e.g. check how
  `gruppe.kostenpause_gemeldet_am` avoids repeat pause messages, and apply
  the same "check the last message text/time before sending" idea here,
  adapted to "check the single newest chat message's text").
- Hard ceiling: "never more than one turn in flight per group; pending text
  accumulates into the next turn" — use the SAME per-group lock mechanism
  pattern as `vorschlagssperre.py` (do not build a second lock registry;
  either reuse that module's `nimm_oder_merke`/`merke`/`gib_frei` trio for a
  new lock key scoped to brainstorm, or confirm with a comment why a new,
  separate `threading.Lock`-per-chat_id dict is justified instead — the
  project's own rule is "ein Sperren-Register je Nebenlaeufigkeit", so a
  fourth register for brainstorm is consistent with that rule, just name it
  clearly, e.g. `brainstorm._SPERREN`).

- [ ] **Step 1: Write failing tests** covering: (a) the trigger fires once
  and accumulates pending text if a turn is already in flight (simulate
  with the lock held), (b) a `NICHTS` result causes no DB row in
  `buehnenkarte` and no chat line, (c) the chat line is skipped if the
  newest message is already that exact line.

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run, verify pass**, then run `tests/test_korpus.py` and
  `tests/test_kosten.py` once more to confirm the new Claude call path
  books correctly against the existing cost cap (per the brief: "verify
  they do" — do not just assert it by reading code, add a test that drives
  `kosten.deckel_erreicht` to `True` and asserts `buehnenkarte.erzeuge`
  either raises/short-circuits the same way `szene_claude.prosa` already
  does via its internal `kosten.pruefe()` call — no separate check should
  be needed since `erzeuge` calls `szene_claude.prosa`/the Infomaniak
  fallback, both of which already gate on the cap; write the test to prove
  that inherited behavior, not to re-implement it).

- [ ] **Step 5: Commit** —
  `git add interview_theater/aufnahme.py interview_theater/bot.py interview_theater/brainstorm.py tests/...`
  `git commit -m "Brainstorm: Trigger verdrahtet, eine Karte je Lauf, keine zweite Zeile im Stau"`

---

### Task B8: Stage tab on the group page

**Files:**
- Modify: `interview_theater/web.py` (group page rendering) — add a minimal
  CSS/JS tab switch "Chat · Bühne", following the brief's explicit fallback
  instruction since Karte W's tab bar is not on this branch: "add a minimal
  tab switch ... CSS/JS only, same page, same token, no new route, and keep
  the stage in ONE render function + one panel element so it moves into W's
  tab bar on merge without rework."
- Test: `tests/test_web.py`

**Interfaces:**
- Produces: `buehne_panel_html(conn, chat_id) -> str` — ONE function
  rendering the stage panel (newest card on top, older ones
  smaller/greyed, the Stückkarte strip with ✓/offen fixed fields plus free
  `festlegung` rows), called from exactly one place in `gruppe_html()`.
  Visible only when `phasen.aktuelle(conn, chat_id) == 4`. Updates via the
  page's EXISTING poll/refresh mechanism (read how `gruppe_html`'s page
  already soft-reloads — the research found the group page does NOT have
  the chat's fetch-based poll; confirm this before implementation: if the
  group page only does `meta refresh`/full reload today, the "no meta
  refresh" instruction in the brief for the stage tab specifically may
  require adding the chat page's lighter poll pattern just for this panel —
  read `web_chat.py`'s poll JS and `web.py`'s existing refresh mechanism
  side by side before deciding; if reusing the chat's poll pattern isn't a
  small change, implement a plain full-page soft-reload identical to
  whatever the rest of the group page already does, and say in the report
  that the stage panel does not yet have independent live-update without a
  page reload — do not invent a third reload mechanism).

- [ ] **Step 1: Write failing tests:**

```python
def test_buehne_tab_nur_in_phase_4(...):
    ...


def test_buehne_zeigt_neueste_karte_zuerst(...):
    ...


def test_buehne_zeigt_stueckkarte_streifen(...):
    ...


def test_kein_material_in_der_buehne(...):
    # same spirit as test_kein_material_in_der_probenansicht
    ...
```

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Implement**, phone-portrait first (reuse `_CSS_CHAT`'s
  mobile-first conventions — check its breakpoints before adding new ones).

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** —
  `git add interview_theater/web.py tests/test_web.py`
  `git commit -m "Brainstorm: Buehne-Tab auf der Gruppenseite (Phase 4, kein neuer Pfad)"`

---

### Task B9: Final full-suite run, docs, and the two "Also" items

**Files:**
- Verify: `tests/test_sprache_bitgleich.py` green (already checked in B6,
  re-confirm after all of Part B).
- Modify (external, outside this repo):
  `/mnt/HC_Volume_106183673/hermes/profiles/birk/var/padua-ablauf-web/ablauf.json`
  — back up first (`cp ablauf.json ablauf.json.vor-brainstorm-<HHMM>`),
  then load/modify/save: add the brainstorm button to `phasen[3].knoepfe`
  and a `meta.aufnahme_schnitt` note describing the VAD cut, using Python's
  `json` module (load, mutate the dict, dump with the same formatting the
  file already uses — check `indent`/`ensure_ascii` by reading the existing
  file's style before writing it back) rather than hand-editing text.
- Update `AGENTS.md` if the module table needs a new row for
  `brainstorm.py`/`buehnenkarte.py` (it does — follow the existing one-line
  style of every other row in that table, matching the German register).

- [ ] **Step 1: Run the FULL suite**
  (`$(ls -d $HOME/.local/share/uv/python/cpython-3.11*/bin/python3 | head -1) -m pytest -q -p no:cacheprovider`)
  and diff the result against the baseline captured before Task A1 (5229
  passed / 2 skipped / 2 pre-existing failures in
  `tests/test_profil_bitgleich.py`) — the only acceptable new state is
  `5229 + N` passed (N = every new test written across A1-B8), same 2
  skipped, same 2 pre-existing failures, zero new failures.

- [ ] **Step 2: Back up and edit `ablauf.json`** as described above.

- [ ] **Step 3: Update `AGENTS.md`'s module table** with the two new
  modules, in the existing style (one row each, pipe-table).

- [ ] **Step 4: Commit** —
  `git add AGENTS.md`
  `git commit -m "Doku: brainstorm.py und buehnenkarte.py in der Modultabelle"`
  (the `ablauf.json` edit is OUTSIDE this repo and is not part of this
  commit — note its path and the backup filename in the report instead).

- [ ] **Step 5: Write `.brainstorm-vad-report.md`** per the brief's exact
  required contents: what was built, every default and its source, what is
  tested vs. untested (especially real-audio behavior — be explicit that
  the VAD algorithm's silence/speech threshold was never run against a real
  microphone in this session, only against the JS source and, if Task A3's
  e2e run succeeded, a synthetic constant-RMS fake analyser), batching
  mechanics (how segments accumulate into one stage-card trigger), every
  flagged decision (the "carried over" audio-merge deviation from Task A2,
  the `sitzung.art` generalization approach, the stage-tab reload mechanism
  chosen in B8, any scope cut made along the way), and explicitly confirm
  or deny each of the brief's listed test cases under "Tests:" in Part A
  and Part B.

