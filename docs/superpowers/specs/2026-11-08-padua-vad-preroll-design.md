# Padua VAD: pre-roll buffer for the pause cut — premise check and design

Task `t_4fc47520`, written 2026-11-08 against `origin/main` a4485ce.
Card written 2026-10-04 (Birk live test). This spec replaces the card's
proposed solution: it checks the card's premise against the current code,
finds the mechanism it describes is gone, and plans for the narrow residual
that is left.

## 1. The card's claim

> Each new segment starts exactly at the moment of the cut — `MediaRecorder`
> starts at `neuesSegment()` without earlier audio. Between real speech onset
> and the RMS threshold being crossed a few measurement ticks pass, so the
> recognition loses the start of the first word after a pause. Fix: a real
> pre-roll buffer, the last ~300–500 ms before the detected cut go into the
> NEW segment.

The claim needs two things to be true at once: (1) the new recorder starts
when speech is *detected*, and (2) the audio between onset and detection
belongs to no segment that is kept. Two later commits matter:
36ab78b (2026-10-05, "Nachtfix Schnittluecke": successor first, old recorder
stops `UEBERLAPP_MS` later) and db6969c (soft cut `'weich'`).

## 2. Premise check (verified against the code on 2026-11-08)

All line numbers are `interview_theater/web_chat.py` at a4485ce.

### 2.1 Facts

| # | Fact | Evidence |
|---|---|---|
| F1 | The VAD tick runs every 60 ms and reads the RMS of one `fftSize = 256` window (≈5.3 ms at 48 kHz) | `:2375`, `:2392`, `:2407–2413` |
| F2 | A tick above the threshold sets `vadLetzteRede = jetzt` **before** the cut decision is taken in the same tick | `:2459–2462` precedes `:2464–2467` |
| F3 | `entscheideSchnitt` returns `'cap'` at `MAX_MS` (default 90 s) regardless of speech; `'pause'` only if `jetzt - vadLetzteRede >= PAUSE_MS` (2500); `'weich'` only if the segment is ≥ `WEICH_AB_MS` (30 s) old and `jetzt - vadLetzteRede >= WEICH_PAUSE_MS` (700) | `:2205–2220`, defaults `:2378–2387` |
| F4 | From F2+F3: a `'pause'`/`'weich'` cut can only fire on a tick whose own RMS window is **below** the threshold, after ≥ 700 ms / 2500 ms of below-threshold ticks. Speech onset never starts a recorder; it only updates `vadLetzteRede` | F2, F3 |
| F5 | `schneideSegment` starts the successor B first (`neuesSegment`), then A keeps recording `UEBERLAPP_MS = 200` ms (`stoppeNachUeberlappung`) | `:2177–2195` |
| F6 | Measured (Chromium headless, 6 runs/24 `'cap'` cuts in continuous synthetic sound): boundary gap −150 to −190 ms (i.e. 150–190 ms overlap), not one cut with lost audio | docstring `tests/e2e/test_web_chat_schnittluecke_e2e.py:10–24` |
| F7 | Pinned by non-e2e tests: successor-before-stop in all four keep-cuts (grep test + Node runs) | `tests/test_web_chat_js.py:285–443` |

Derived (inference, not a separate measurement): with A stopping 200 ms after
`B.start()` and an overlap of 150–190 ms, B's first kept sample lies about
10–50 ms after `B.start()` on Chromium (start latency + 60 ms Opus frame
alignment). This document calls that latency **λ**.

### 2.2 Verdict per cut type

"Lost" means: audio before the next speech onset is present in **no** kept
segment.

| Cut type / call site | Fires during | Audio before next onset lost? | Evidence |
|---|---|---|---|
| `'pause'` — `schneideSegment` from the tick | silence ≥ 2500 ms | **No.** B runs from the cut onward in silence, so an onset later than λ after the cut is inside B. Even an onset in the window from just before the cut to λ after it is inside A's 200 ms tail, so no audio is lost (see R1 for the word split) | F2–F6, `:2477` |
| `'weich'` — `schneideSegment` from the tick | silence ≥ 700 ms, segment ≥ 30 s | **No.** Same mechanism as `'pause'`. R1 is more likely here (shorter pause) | F2–F6, `:2472` |
| `'cap'` — `schneideSegment` from the tick | anywhere, usually mid-speech | **No.** Measured overlap 150–190 ms, 0 of 24 cuts with a gap. The cut splits a word **by design**; a pre-roll would only move the split point | F6, `:2477` |
| Fixed `SEGMENT_MS` fallback (no AnalyserNode) | anywhere | **No.** Same successor-first pattern as `'cap'` | `:3170–3177`, F7 |
| `kalSchneideOhneMarkierung` / `kalSchneideAlsKalibrierung` | calibration boundaries | **No.** Successor-first + overlap (the `kalVorStart` branches start the probe clip with nothing before it, by design) | `:2794–2824`, F7 |
| `kalSchneideUndVerwerfen`, `kalStarteEchteSchnitte` (kalVorStart), `beendeDiskussion` during the room check | discard of a clip that is never sent | **Not applicable.** The old clip is `_kalVerworfen` by design; no kept audio exists before the new start | `:2826–2832`, `:3150–3156`, `:3532–3539` |
| Session start `beginneAufnahme` | button press | **Not applicable.** No audio before the start is meant to be recorded | `:3418–3419` |
| Pause/end (`pausiereInterview`, `beendeInterview`) | user action | **Not applicable.** Intended stop, `_grund = 'ende'` | `:3675`, `:3730` |

**Result: the premise is refuted on current main.** No cut type drops audio
before the next speech onset. The card's mechanism ("the recorder starts when
speech is detected") does not exist: since the VAD (02.10.2026) the recorder
runs continuously, and cuts happen in silence or with overlap.

### 2.3 What is actually left

- **R1 — word split at a pause/weich cut (plausible, unmeasured).** The tick
  sees only ≈5 ms out of every 60 ms (F1), and a soft onset (/h/, /f/, a
  breathy vowel) can stay below the threshold. So speech can begin in the
  window `(T − δ, T + λ)` around a cut at tick `T`, with δ up to about one
  tick (60 ms) plus the quiet part of the onset. That onset is then inside
  **A's tail** (A runs until `T + 200 ms`), and **B starts mid-word**. No
  audio is lost, but the first word is split across two Whisper calls.
  How often this happens depends on how often a pause ends within ~δ+λ of the
  700/2500 ms mark. ANNAHME: rare for `'pause'`, possibly a few percent of
  `'weich'` cuts. Unmeasured; Task 3 of the plan measures it.
- **R2 — `'cap'` and fixed-interval cuts split a word by design.** No audio
  is lost (F6). A pre-roll in B is no remedy: it shifts the split, it does
  not remove it. Not addressed here. ANNAHME: after `'weich'` (db6969c), a
  `'cap'` needs 60 s without a single 700 ms pause, so it should be rare.
  Check with the query in §5.
- **R3 — other browsers.** F6 is Chromium only. Safari iOS (AAC/MP4) and
  Firefox Android (Opus/Ogg or WebM) have other frame sizes and start
  latencies. ANNAHME: both have λ < 200 ms, so the overlap still covers the
  boundary. To check: run Task 3's measurement on a real iPhone/Android, or
  in Playwright WebKit/Firefox if a fake microphone works there. Not
  verifiable from this repo; no web access in this run.
- **R4 — Whisper drops a word at t ≈ 0 of a clip.** An STT behaviour, not a
  recording gap. Measuring it costs money (real Whisper calls), so it never
  runs automatically. Out of scope; listed so a later card can pick it up.
- **Observation:** `tests/e2e/test_web_chat_schnittluecke_e2e.py:234` sets
  `IT_WEB_VAD_CAP_NACHLAUF_MS`, which nothing in `interview_theater/` reads
  any more (grep, 2026-11-08). The variable is dead config. Harmless and not
  touched here.

## 3. Approaches

1. **Measure, pin, decide (chosen).** Pin the premise with non-e2e Node tests
   so a future change cannot quietly bring back "recorder starts on speech"
   or "stop before successor". Measure R1 in the browser with a controlled
   onset sweep around a `'pause'` and a `'weich'` cut. Record the result.
   Build a fix only if the measurement passes the decision gate (§4).
   No recording code changes.
2. **Early successor (narrow form of the card's way 1), only if the gate
   trips.** While the segment is cut-eligible, start B speculatively once
   `ruhigSeit >= WEICH_PAUSE_MS - PREROLL_MS` (and the same for `PAUSE_MS`).
   If the cut fires, B already holds `PREROLL_MS` of pre-roll. If speech
   resumes first, B is discarded the way `_kalVerworfen` clips already are
   (onstop with `auftrag = null`, which keeps numbering intact,
   `:1980`, `:2009–2018`). It reuses `neuesSegment`, needs no new encoder,
   and leaves `entscheideSchnitt` and calibration untouched. Cost: up to two
   recorders on one `MediaStream` for ≤ `PREROLL_MS`. That pattern already
   runs in production for 200 ms at every cut (F5). So browser support for
   two recorders on one stream is not a new requirement — it is what the
   Nachtfix already does on all three Padua phones.
3. **PCM pre-buffer with its own encoder (the card's way 2). Rejected.**
   It needs an AudioWorklet (or the deprecated ScriptProcessor), a WAV/Opus
   encoder in the page, a second upload format, and Safari-specific testing.
   It solves R1 no better than approach 2, at many times the code.
   ANNAHME (unverified, no web access): AudioWorklet is available on Safari
   iOS ≥ 14.5 and Firefox Android; to check:
   <https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet>,
   <https://caniuse.com/mdn-api_audioworklet>.

Browser sources for approach 2, to check before it is built (ANNAHME — not
fetched in this run): MediaRecorder on Safari iOS ≥ 14.3
(<https://webkit.org/blog/11353/mediarecorder-api/>,
<https://caniuse.com/mediarecorder>); several recorders on one stream
(<https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/MediaRecorder>).
The strongest evidence in hand is the production fact in F5: every cut
already runs two recorders on one stream for 200 ms.

## 4. Design (approach 1)

### 4.1 Unit level (non-e2e, Node, in `tests/test_web_chat_js.py`)

- **P1 — a speech tick never cuts pause/weich.** Run the verbatim
  `pegelTakt` body (same extraction as
  `test_pegeltakt_zeichnet_breite_marke_und_farbzustand_live_in_node`) with
  the verbatim `entscheideSchnitt` and a recording `schneideSegment` stub.
  Feed a long below-threshold run, then one tick above the threshold at the
  exact moment `ruhigSeit` would reach `WEICH_PAUSE_MS` / `PAUSE_MS`.
  Expect: no cut on that tick. Control: the same sequence without the
  speech tick cuts `'weich'` / `'pause'`. This pins F2+F4 at runtime, not
  only by text order.
- **P2 — every `neuesSegment(sitzung)` call site is classified.** A grep
  test lists every call of `neuesSegment(sitzung)` in `_CHAT_JS` (not the
  `function neuesSegment(sitzung)` definition) with its enclosing function
  and compares it with the table in §2.2 (nine call sites at a4485ce). A new call site turns the test red until someone
  classifies it as "successor-first + overlap" or "discard/start, nothing
  kept before". This guards the verdict table against drift.

Both tests are characterization tests: they pass on today's code. Each must
be shown to catch its mutant (named in the plan) before it is committed.

### 4.2 Browser level (e2e, Playwright, Chromium)

New file `tests/e2e/test_web_chat_schnitt_einsatz_e2e.py` ("onset at the
cut"). It reuses the measurement idea of the Schnittluecke test (reference
recorder on a clone of the same stream, decode, locate) and adds a gated
source:

- The fake microphone is low-pass noise behind a `GainNode`, gain 0 =
  digital silence, gain 1 = "speech". The VAD's view (`__t.setzeRms`) is
  driven **separately**, so the test can model a quiet onset: the audio is
  on while the VAD still sees silence.
- Each run: sound for 1 s (enough `vadSpeechMs`), silence, then the sound
  comes back at an offset `Δ` from the expected cut moment, with the VAD
  level held at 0 until the cut has happened (or until `Δ + 60 ms` if that
  is later). Offsets `Δ ∈ {−100, −50, 0, +50, +100, +300}` ms, at least
  two runs each, for a `'pause'` run (`IT_WEB_VAD_PAUSE_MS=700`) and a
  `'weich'` run (`IT_WEB_VAD_WEICH_MS=1500`, `IT_WEB_VAD_WEICH_PAUSE_MS=700`,
  `IT_WEB_VAD_PAUSE_MS=60000`).
- Measured per run: actual `O − T` (onset time in the reference minus
  `B.start()` time, mapped to reference samples), `missing_in_B_ms` (onset
  in the reference minus the position of B's first sample when B starts
  inside sound, else 0), `onset_in_A_ms` (how much of the onset A's tail
  holds), and the boundary gap as in the Schnittluecke test.
- Asserts only what the premise claims: (a) gap ≤ 0 at every boundary
  (no lost audio), (b) `missing_in_B_ms == 0` for every run with
  `O − T ≥ 250 ms`. Runs inside the R1 window are **reported, not
  asserted**: one `SCHNITTEINSATZ {json}` line per run, like the existing
  `SCHNITTLUECKE` line.

### 4.3 Decision gate (written down, applied by Birk)

The measurement goes into `docs/handoffs/2026-11-08-padua-vad-preroll.md`
together with the §5 query result. A follow-up card for approach 2 is
justified only if **both** hold:

1. the e2e shows `missing_in_B_ms > 0` for some `Δ` in the R1 window, and
2. live data shows `'weich'` + `'pause'` cuts are a material share of all
   cuts (Birk sets the threshold; the handoff states the numbers).

If the gate does not trip, the card is closed with the measurement as its
answer. In both cases nothing in `entscheideSchnitt`, the calibration, the
noise-floor logic, `UEBERLAPP_MS` or `neuesSegment` changes in this task.

## 5. Live-data query (read-only, for Birk; not part of the coder's run)

The coder's worktree has no `betrieb/` database, so this is for Birk to run
on herkules against the Padua database:

```
sqlite3 -readonly <padua-db> "SELECT diskussion, brainstorm, schnittgrund, COUNT(*) FROM aufnahme WHERE empfangen_am >= '2026-10-06' GROUP BY diskussion, brainstorm, schnittgrund"
```

`aufnahme.schnittgrund` and `weich_ms` are stored per segment
(`interview_theater/db.py:152` table, `:196`, `:225`; `repo.py:525–568`).
Interviews, Phase-4 brainstorm and the Phase-1 discussion all use the same
cuts, hence the grouping. The cut-off date is after db6969c (committed
2026-10-05) went live (ANNAHME: deployed by 2026-10-06).

## 6. Scope and non-goals

- No production code change in this task: the measurement and the tests
  come first.
- No PCM path, no rolling recorder, no change to `entscheideSchnitt`
  semantics, calibration, noise floor, `UEBERLAPP_MS`.
- No real Whisper calls (R4) and no live service restarts.
- Padua only; Dortmund is frozen (AGENTS.md).

## 7. Acceptance

- `tests/test_web_chat_js.py` green including P1 and P2, inside the
  non-e2e suite
  (`uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2`).
- The new e2e file runs green in the e2e venv, and its `SCHNITTEINSATZ`
  lines are copied into the handoff.
- The handoff states the gate inputs; Birk decides about approach 2.
