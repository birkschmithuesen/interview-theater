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

## Measurement (Chromium headless, Playwright 1.61.0, Chromium 120.0.6099.224, 2026-11-08)

Command: `env PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest tests/e2e/test_web_chat_schnitt_einsatz_e2e.py -q -s -p no:cacheprovider`

Result: 24 passed (12 per cut type), 24 `SCHNITTEINSATZ` lines, 142.7 s.

The measurement ran on the system Chromium (`/usr/bin/chromium`, Debian 11),
selected through the optional env var `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`,
because no Playwright browser may be downloaded (technical call by Robo,
08.11.2026). Unset, the test uses the bundled browser. Python Playwright does
not read that variable itself; the test passes it as `executable_path`.

Deviations of the committed test from the plan (test file only, no change in
`interview_theater/`):

1. Optional `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` override in `launch(...)`.
2. A 5 s poll (`_wait`) for `window.__m.gain && window.__m.ref` before `__m.run(...)`:
   `data-laeuft="1"` can flip before the fake `getUserMedia` resolved (first run failed
   with "Cannot read properties of null (reading 'gain')"). Polled via `page.evaluate`
   because `wait_for_function` with a string is refused by the page CSP.
3. `server` fixture is function-scoped instead of module-scoped: with a shared server
   web_grenze's rate limit (20 messages/minute/chat) returned 429 on the interview POST
   in the 12th run of each config, so the run never started. A fresh server per run
   resets the limiter (about 1-2 s per run).

| config | offset_ms | repeat | onset−cut (wall) ms | missing_in_b_ms | onset_in_a_tail_ms | gap_ms |
|---|---|---|---|---|---|---|
| pause | -100 | 0 | -100.7 | 95.9 | 275.9 | -180 |
| pause | -100 | 1 | -100.8 | 95.6 | 275.6 | -180 |
| pause | -50 | 0 | -50.7 | 33.0 | 223.0 | -190 |
| pause | -50 | 1 | -50.7 | 35.8 | 215.8 | -180 |
| pause | 0 | 0 | -0.5 | 0 | 173.5 | -180 |
| pause | 0 | 1 | -0.8 | 0 | 162.8 | -170 |
| pause | 50 | 0 | 49.6 | 0 | 125.5 | -180 |
| pause | 50 | 1 | 49.4 | 0 | 122.8 | -180 |
| pause | 100 | 0 | 99.1 | 0 | 74.8 | -180 |
| pause | 100 | 1 | 99.8 | 0 | 72.1 | -180 |
| pause | 300 | 0 | 299.0 | 0 | 0 | -180 |
| pause | 300 | 1 | 299.2 | 0 | 0 | -180 |
| weich | -100 | 0 | -100.8 | 102.2 | 272.2 | -170 |
| weich | -100 | 1 | -100.9 | 94.9 | 274.9 | -180 |
| weich | -50 | 0 | -50.7 | 46.8 | 226.8 | -180 |
| weich | -50 | 1 | -50.9 | 40.8 | 210.8 | -170 |
| weich | 0 | 0 | 0.2 | 0 | 175.0 | -180 |
| weich | 0 | 1 | 0.4 | 0 | 172.8 | -180 |
| weich | 50 | 0 | 49.3 | 0 | 112.2 | -170 |
| weich | 50 | 1 | 49.8 | 0 | 122.9 | -180 |
| weich | 100 | 0 | 99.0 | 0 | 64.2 | -180 |
| weich | 100 | 1 | 99.1 | 0 | 74.8 | -180 |
| weich | 300 | 0 | 298.8 | 0 | 0 | -170 |
| weich | 300 | 1 | 298.5 | 0 | 0 | -180 |

Summary: R1 window measured as onset−cut from -100.9 to -50.7 ms (the runs with
missing_in_b_ms > 0; negative = onset before the cut); largest missing_in_b_ms
102.2 ms; smallest onset_in_a_tail_ms in those runs 210.8 ms; gap_ms range
-190..-170 ms (negative = A and B overlap, so no gap at the boundary).

Reading: in every run A and B overlap by about 180 ms. The part of an onset that
B misses (33.0 to 102.2 ms) is still held in A's tail (at least 210.8 ms in those
runs), so the onset is split across A and B but not lost. From an onset at or
after the cut (offset 0 and later) nothing is missing in B. Pause and weich
behave the same. Two repeats per cell; no values are estimated.

## Not measured (ANNAHME)

- Safari iOS, Firefox Android (spec R3): start latency and frame size unknown; check on a real phone.
- Whisper on a split word (spec R4): costs money, never automatic.
- Other browsers or Chromium versions: only Chromium 120.0.6099.224 with a fake microphone was run.
- Real speech: the measurement uses a synthetic onset signal; how often real onsets fall into the -100..-50 ms window is unknown.
- Offsets between -50 and 0 ms and below -100 ms: only the offsets in the table were run.

## Live data — for Birk to run on herkules (read-only)

    sqlite3 -readonly <padua-db> "SELECT diskussion, brainstorm, schnittgrund, COUNT(*) FROM aufnahme WHERE empfangen_am >= '2026-10-06' GROUP BY diskussion, brainstorm, schnittgrund"

## Decision gate (spec §4.3)

A follow-up card "early successor" (spec §3, approach 2) is justified only if
(1) the table above shows missing_in_b_ms > 0 (it does: 8 of 24 runs, 33.0 to 102.2 ms, all with the onset 50 to 100 ms before the cut), and
(2) the live query shows that 'weich' + 'pause' cuts are a material share (Birk decides).
Otherwise the card closes with this measurement.

Gate applied literally: condition (1) is met; condition (2) is open and rests
with Birk. Note for the decision: in all 8 runs the missing part is still
present in A's tail, so condition (1) holds without any audio being lost.
