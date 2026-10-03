# Padua Mithören SICHER: nie verwerfen + Stille-Kalibrierung + Schwellenmarke — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the web VAD (pause-cut) pipeline from ever silently discarding
a segment that contains real speech (Scenario A: threshold too high, quiet
speech never counted as "Rede"), add an automatic, per-device noise/speech
calibration that replaces guessed threshold constants with measured ones
(Scenario B: a cut threshold set too high/too low for the actual room), add a
visible threshold mark on the level meter, and add a one-time "check the
transcript" hint — all for the web chat's Interview and Brainstorm
mithören modes (`interview_theater/web_chat.py`).

**Source:** Kanban card t_22a9c6fe (verbatim spec, reproduced task-by-task
below). There is no separate design doc — this plan IS the breakdown of that
card into independently reviewable tasks.

**Architecture:** All four tasks touch `interview_theater/web_chat.py`'s
`_CHAT_JS` (the single vanilla-JS blob served to the browser) plus its
Python-side HTML renderer (`_fuss_html`/`chat_html`), `_vad_werte()`, and
`_JS_TEXTE`. Task 1 additionally threads a new metadatum (`rede_ms`) through
the whole upload pipeline end-to-end: client query param → `_audio` handler
→ `repo.lege_web_post_an` → `web_post` table → `web_kanal.hole_updates` →
`telegram.lies_nachricht` → `aufnahme.empfange` → `repo.lege_aufnahme_an` →
`aufnahme` table — mirroring the existing `schnittgrund`/`brainstorm`
plumbing exactly (grep any of those names to see every stop). Task 1 also
touches `aufnahme._melde_transkriptionsfehler`, generalizing the existing
brainstorm-only silent-discard of an empty Whisper transcript (commit
`b30faa2`) to every recording class.

**Tech Stack:** Python 3.11 stdlib `http.server`, vanilla JS (no build
step), SQLite, pytest, optionally `node --check` / Playwright for JS tests
(both already used by `tests/test_web_chat_js.py` / `tests/e2e/`).

## Global Constraints

- Branch: `wt/t_22a9c6fe` (current worktree). **No merge, no push** to
  main/origin. Commit after each completed task (not just at the end) —
  a run can die mid-plan; a commit survives that.
- `git add` exact paths only, never `-A`/`.`/`-a`.
- No model call anywhere in this plan — all four tasks are pure
  client/server plumbing and UI, no `llm.py`/`stt.py` prompt changes.
- German stays the literal Python `_TEXT_*` constant (bitgleich); every new
  user-facing string gets an English mirror entry under `["web_chat"]` in
  `interview_theater/sprachen/en/texte.toml` (same key name as the Python
  constant), because the Padua workshop profile runs in English
  (`sprache.code()` → `'en'`) and these are exactly the texts `T._TEXT_*`
  already looks up for this module (see `_js()`'s `texte = dict(_JS_TEXTE,
  interview_an=T._TEXT_INTERVIEW_AN, ...)` pattern — any NEW text that must
  be localized needs the same explicit override entry there, not just a
  raw `_JS_TEXTE` key).
- **Approved, narrow exception to E6** (resolved with Birk before this plan
  was written): `tests/test_web_chat_js.py::
  test_das_js_setzt_kein_cookie_und_nichts_in_den_speicher` currently bans
  `localStorage`/`sessionStorage`/cookies/`WebSocket`/`EventSource` outright
  in `_CHAT_JS`. Task 2 is explicitly allowed to use `localStorage`, but
  **only** for the three keys `vad_boden_mess`, `vad_rede_mess`,
  `vad_schwelle` (VAD calibration, per-device acoustic data — never meant to
  be shared via the group link, so E6's "shareable link / two phones see the
  same state" rationale does not apply to it). Update the test to assert
  exactly those three keys are the only `localStorage` usage (e.g. collect
  every `localStorage.(setItem|getItem)\(['"]([a-zA-Z_]+)['"]` match and
  assert the set equals `{"vad_boden_mess", "vad_rede_mess", "vad_schwelle"}`)
  and add an inline comment next to the first `localStorage` use in
  `_CHAT_JS` explaining why this one case is exempt from E6. Do not use
  `localStorage` for anything else, and do not touch `sessionStorage`/
  cookies/`WebSocket`/`EventSource` — those three remain banned.
- Every new timing/threshold/env number must be env-overridable with a
  default, same convention as the existing `IT_WEB_VAD_*` family in
  `web_chat._vad_werte()` (around line 3045-3060).
- Baseline before any change here: run the full suite once (see Task 0
  below — actually run it as part of your own verification per task, not as
  a separate task) and treat any pre-existing failure as out of scope;
  do not fix it, do not let the failure list grow for reasons unrelated to
  this plan.
- Never touch `betrieb/` or any live/production database. Tests use
  `tmp_path`/in-memory or scratch DBs, same as the existing test suite.
- Full suite command (background only, this single run takes close to or
  over the 600s foreground timeout):
  `env -i HOME=$HOME PATH=/usr/bin:/bin $PY -m pytest -q -p no:cacheprovider`
  with
  `PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`.
  Also run `python -m scripts.pruefe_profil dortmund-2026` and
  `python -m scripts.pruefe_profil padua-2026` (check `--help` for exact
  invocation) at the very end, after all four tasks, not per-task.

---

## Task 1: Never discard a recorded segment again (client) + generalize silent-discard of empty transcripts (server)

**Context:** `interview_theater/web_chat.py`'s `_CHAT_JS`, function
`neuesSegment`'s `r.onstop` handler (search for `r.onstop = function`, around
line 1102). Today it computes `genug` from `r._redeMs`/`r._grund` and drops
the segment entirely (never uploads it) when the VAD decided there wasn't
"enough" detected speech — this is exactly Birk's Scenario A: a threshold set
too high means real, quiet speech gets measured as `redeMs < MIN_SPEECH_MS`
(or even `redeMs === 0` for an `'ende'`/manual-flush cut) and the whole
segment, including real words, is thrown away client-side before it ever
reaches the server.

### 1a. Client: always upload, send `redeMs` as metadata instead

In `r.onstop`, remove the `genug` gate entirely. The new rule: **any
segment with bytes, from a session that hasn't been discarded, gets
uploaded** — full stop, regardless of `redeMs`/`grund`. Keep `redeMs` on the
`auftrag` object (`auftrag.redeMs = redeMs`, where `redeMs` may be `null`
when VAD is inactive — the old fallback-takt path) purely as metadata for
the server to store, not as an upload gate.

```js
r.onstop = function () {
  sitzung.offen -= 1;
  var auftrag = null;
  var redeMs = r._redeMs;
  var grund = r._grund || null;
  // Frueher wurde hier ueber redeMs verworfen (Birk, Szenario A: eine zu
  // hoch eingestellte Schwelle liess leise, aber echte Rede als "nicht
  // genug" durchfallen und das ganze Segment -- samt Woertern -- ging
  // nie hoch). Jedes Segment mit Bytes geht jetzt IMMER raus; redeMs
  // faehrt nur noch als Metadatum mit (Kanban-Karte Mithoeren SICHER).
  if (teile.length && !sitzung.verworfen) {   // leere Stuecke nie
    auftrag = {
      art: 'audio', sitzung: sitzung,
      blob: new Blob(teile, { type: teile[0].type || r.mimeType || 'audio/webm' }),
      dauer: Math.max(1, Math.round((Date.now() - von) / 1000)),
      grund: grund, redeMs: redeMs
    };
  }
  ...
```

In `postAudio`, append `redeMs` to the query string when it is a number
(mirroring the existing `grund` pattern):

```js
if (auftrag.redeMs != null) { weg_ += `&rede=${Math.round(auftrag.redeMs)}`; }
```

### 1b. Server: parse `rede`, thread it through to `aufnahme.rede_ms`

In `_audio` (around line 2642), parse the new `rede` query param the same
defensive way `dauer` is parsed (ASCII digits only, bounded length, `None`
on anything else — reuse the same pattern, it does not need the same strict
error-on-invalid behavior as `dauer`: an invalid/missing `rede` is just
`None`, it must never cause a 400). Pass it to `repo.lege_web_post_an(...,
rede_ms=rede_ms)`.

Thread it end-to-end, mirroring `schnittgrund` at every one of these exact
stops (grep `schnittgrund` in each file to find the precise line):

1. `interview_theater/db.py` — SCHEMA: add a `rede_ms INTEGER` column (with
   a short comment, additive like `schnittgrund`/`brainstorm`) to **both**
   `web_post` and `aufnahme` table definitions. Do **not** add any new
   migration function — `_migriere_fehlende_spalten` picks up any new
   column in `CREATE TABLE IF NOT EXISTS` automatically (verify by reading
   `_tabellenspalten_aus_schema`, around line 1110). Nullable, no default
   needed (NULL means "VAD inactive" or "no metadata recorded", same
   meaning as `schnittgrund IS NULL` today).
2. `interview_theater/repo.py`:
   - `lege_web_post_an(...)` — add `rede_ms: int | None = None` keyword
     param, insert it as a column (one more `?` placeholder and one more
     value).
   - `lege_aufnahme_an(...)` — same: add `rede_ms: int | None = None`
     keyword param, insert it as a column.
3. `interview_theater/web_kanal.py` — in the `nachricht["voice"] = {...}`
   dict (around line 353), add `"rede_ms": zeile["rede_ms"]` next to
   `"schnittgrund"`.
4. `interview_theater/telegram.py` — in `lies_nachricht`'s returned dict
   (around line 502), add `"rede_ms": _sprachquelle(nachricht).get("rede_ms")`
   next to `"schnittgrund"`. (A real Telegram update never has this key —
   `_sprachquelle(...).get(...)` returns `None`, same as `schnittgrund`
   today.)
5. `interview_theater/aufnahme.py` — in `empfange()` (around line 489), pass
   `rede_ms=n.get("rede_ms")` to `repo.lege_aufnahme_an(...)` next to
   `schnittgrund=n.get("schnittgrund")`.

Nothing downstream needs to *read* `aufnahme.rede_ms` for this task — it is
stored for future diagnosis (so Birk can see, per segment, how much
detected speech there was even though the segment was uploaded anyway). Do
not add a dashboard/reporting feature for it; that is out of scope.

### 1c. Server: generalize the silent-discard of an empty transcript

`interview_theater/aufnahme.py::_melde_transkriptionsfehler` (around line
744) today only silently discards a `stt.LeeresTranskript` (empty/whitespace
Whisper result — `stt.abholen` already does `.strip()`, so this class
already covers whitespace-only) when `row["brainstorm"]` is true. Because
Task 1a now uploads every segment regardless of detected speech, **every**
recording mode (Interview parts included, not just Brainstorm) will
routinely produce real, silent segments whose Whisper transcript comes back
empty — and the existing general error path (retry counting, the
`transkription_fehlgeschlagen` incident, the "please say it again" message
on first Interview-part failure, the Whisper-outage alarm) is wrong for
plain silence: it's not a service failure, and there's nothing to "say
again" about a quiet VAD-triggered cut.

Change the condition from `if row["brainstorm"] and isinstance(fehler,
stt.LeeresTranskript):` to `if isinstance(fehler, stt.LeeresTranskript):` —
drop the `row["brainstorm"]` restriction entirely, keep everything else in
that branch unchanged (status straight to `'fehlgeschlagen'`, no chat line,
no `melde_ausfall`, one incident for the dashboard). Rename the incident
type from `"brainstorm_segment_verworfen"` to a class-agnostic name, e.g.
`"leeres_segment_verworfen"` (update the one `repo.merke_vorfall(...)` call
and its message text to not say "Brainstorm" specifically), and update the
docstring above the function (the paragraph starting "**Ein
Brainstorm-Segment...**") to describe this as applying to any recording
class, not a brainstorm-specific third case.

### Tests to update/add

- `tests/test_web_chat_js.py::test_onstop_laesst_zu_kurze_kappen_schnitte_weg`
  currently asserts the **old** discard behavior exists (`"genug" in
  onstop`, `"redeMs > 0" in onstop`). Replace it with a test proving the
  opposite invariant — e.g. assert `"genug"` no longer appears as a gating
  variable in the `onstop` body, and that the `if (teile.length &&
  !sitzung.verworfen)` condition (no `redeMs`/`grund` term) is what gates
  the upload. State explicitly in a comment that reverting to the old
  `genug`-based condition must turn this test red (that is the point of
  this test, per the card).
- Add a focused unit/JS-logic test (same file) asserting `redeMs` is
  attached to the `auftrag` and that `postAudio` appends `&rede=` to the
  query when `auftrag.redeMs` is a number — string-level assertions against
  `web_chat._CHAT_JS` are fine, consistent with the rest of that file.
- `tests/test_web_chat_audio.py` (or wherever `_audio`'s query parsing is
  covered) — add a case for the `rede` query param: valid, missing, and
  garbage input, asserting it never causes a 400 and that a valid value
  reaches `web_post.rede_ms`.
- `tests/test_aufnahme.py` — three changes:
  1. `test_normale_kurze_nachricht_mit_leerem_transkript_bleibt_unveraendert`
     (added in commit `b30faa2`) currently proves a non-brainstorm empty
     transcript still goes through the full `MAX_VERSUCHE` retry chain and
     ends with a "nochmal" message. That is exactly the behavior Task 1c
     removes. Replace it with a test proving a **non-brainstorm** (e.g. an
     ordinary `klasse='kurz'` or `klasse='teil'`) empty transcript is now
     *also* silently discarded (status straight to `fehlgeschlagen`, zero
     retries counted, no chat line sent) — same shape as the existing
     `test_brainstorm_segment_mit_leerem_transkript_wird_still_verworfen`.
  2. Keep (or add, if missing) a regression test that a **non-empty**
     Whisper failure (a plain `stt.STTFehler`, not `LeeresTranskript`) for a
     non-brainstorm recording still goes through the normal retry chain
     with the "please say it again" message — silence is special-cased,
     real STT failures are not.
  3. Add round-trip coverage for `rede_ms`: `aufnahme.empfange(...)` with a
     message dict carrying `"rede_ms": 42` results in
     `repo.hole_aufnahme(conn, id)["rede_ms"] == 42`.
- `tests/test_db.py` (or equivalent) — confirm `rede_ms` appears in both
  `PRAGMA table_info(web_post)` and `PRAGMA table_info(aufnahme)` on a fresh
  database, and that `_migriere_fehlende_spalten` adds it to an
  old-schema database that predates this column (there is almost certainly
  an existing parametrized test doing exactly this for `schnittgrund` —
  follow its pattern, do not invent a new one).

Run the files you touched (`pytest tests/test_web_chat_js.py
tests/test_web_chat_audio.py tests/test_aufnahme.py tests/test_db.py -q`,
or the closest equivalents you find) before committing; report the command
and its summary line.

---

## Task 2: Button-gated noise/speech calibration with an onboarding test-transcript

> **Supersedes an earlier, fully-automatic version of this task.** Birk
> corrected it (03.10.2026, verbatim reasoning): a countdown that just starts
> by itself does not guarantee the room is actually quiet — the group needs
> to be told what is about to happen and press a button when *they* are
> ready, and the same is true for the speech measurement (a self-starting
> transition risks measuring before anyone has actually spoken, or missing a
> slow starter). He also wants the phone's placement addressed explicitly
> (real discussion position, not spoken into), and the whole calibration to
> double as an onboarding/functional test: the group hears back what the
> bot understood and confirms it, with concrete, staged feedback when it was
> too quiet (including a "pass the phone around" fallback for a loud/big
> room, remembered for the rest of the workshop). Nothing in this flow ever
> starts itself — every step waits for an explicit button press, with one
> narrow exception (the automatic retry-prompt after a 30 s silence timeout,
> which is itself a button, just one the system puts in front of the group
> rather than the group asking for it).

**Context:** `interview_theater/web_chat.py`, function `pegelAn` (around
line 1298) computes the cut threshold from **guessed** env constants
(`RMS_SCHWELLE` default `0.01`, `BODEN_FAKTOR` default `2.5`,
`BODEN_DECKEL_FAKTOR` hardcoded `10`) — Birk's Scenario B: these numbers
were never measured against a real room. This task replaces the guess with
a per-device, button-gated measurement with a built-in onboarding test, run
at the start of a fresh Interview/Brainstorm session (not on
resume-from-pause, and **web channel only** — Telegram has no browser VAD
pipeline at all and must stay completely untouched by this task).

### 2a. The flow, step by step (each step waits for a click; nothing times out into the next step on its own except where stated)

All text below is the literal English wording to use (Padua profile is
English) — write the German `_TEXT_*` constant as a faithful German
translation of the same sentence, English goes into
`sprachen/en/texte.toml` under `["web_chat"]` exactly as quoted. Every text
constant follows the same `_JS_TEXTE` + `T._TEXT_*`-override-in-`_js()`
wiring as the rest of this plan.

1. **Announcement** (shown immediately when a fresh, uncalibrated session's
   `beginneAufnahme` runs and there is no valid `localStorage` cache —
   see 2g): placement instructions plus what is about to happen, one panel,
   one button:

   > "Put this phone in the middle of the table, where it will stay during
   > the discussion. Sit as you will sit while talking — don't lean in or
   > speak into the phone. We'll test it exactly like the real situation.
   > When you press the button below, please stay completely silent for 5
   > seconds — then one of you will say a sentence in a normal voice."

   Button: **"Start measuring"** (`#kalibrierung-start`).

2. Only the click on "Start measuring" starts the 5-second silence
   measurement (`KALIBRIERUNG_STILLE_MS = 5000`, literal constant, no env
   override requested): sample RMS every 120ms (same cadence as the
   existing `pegelTakt`), show a visible countdown ("Quiet for {s}
   seconds — measuring the room...", `{s}` ticking 5→1). `boden_mess` =
   median of the collected samples.

3. After the silence measurement finishes, **no automatic transition**.
   Show:

   > "Silence measured. Now one of you will say a sentence in your normal
   > voice — ideally the person sitting furthest from the phone. Speak from
   > where you sit, at normal volume, not into the phone. Press the button,
   > then start talking."

   Button: **"Start speaking"** (`#kalibrierung-sprechen`).

4. Only the click on "Start speaking" starts the speech measurement:
   - Show "Listening... start whenever you're ready." and wait for the
     first RMS sample `> 3 * boden_mess` (voice detected), up to
     `KALIBRIERUNG_WARTE_MAX_MS = 30000`.
   - If nothing crosses that threshold within 30 s: show "We didn't hear
     anything — try again?" with a button **"Measure again"**
     (`#kalibrierung-nochmal-hoeren` — name it distinctly from the
     always-visible panel-level "Measure again" button from 2g, they are
     different buttons with different scope, do not reuse one id for both).
     Clicking it restarts **only** this step (fresh 30 s wait); the
     already-measured `boden_mess` from step 2 is kept, step 2 is not
     repeated.
   - Once voice is detected: keep sampling, accumulate "voiced time" (every
     120ms sample `> 3 * boden_mess` adds 120ms to a counter — time at or
     below threshold, i.e. pauses, does not count). Stop collecting when
     either the voiced-time counter reaches `KALIBRIERUNG_SPRACH_MS = 4000`
     or `KALIBRIERUNG_SPRACH_FENSTER_MS = 15000` has elapsed since the first
     voice sample, whichever comes first.
   - `rede_mess` = 80th-percentile RMS (`sortiert[Math.floor(sortiert.length
     * 0.8)]`, same percentile-indexing style the existing `boden`
     computation in `pegelAn` uses) over **all** samples collected from the
     first voice sample to the end of collection (pauses included in the
     percentile input — the 80th percentile already biases toward the
     louder, voiced parts of that window without needing a second filter).
   - Audio for the test transcript (step 6): cut the currently-running
     `MediaRecorder` segment at the "Start speaking" click (reuse the
     existing `schneideSegment`-style stop-current/start-next mechanism —
     add a new orthogonal per-recorder flag, e.g. `r._kalibrierung = true`,
     set the same way `r._grund`/`r._redeMs` are set today; do **not**
     repurpose the `grund` field, which is validated server-side against a
     fixed set of values and means something else) and cut it again when
     voiced-collection ends. The resulting clip spans from the "Start
     speaking" click to collection-end — this is intentionally more than a
     literal ±1 s window around the detected words (it includes the
     pre-speech wait and the full 15 s cap headroom), which already
     satisfies the card's "±1 s buffer" intent without needing separate
     timestamp bookkeeping: the point is not to clip the sentence, and a
     generous natural segment boundary cannot clip it.
   - If the 30 s wait times out (no voice at all): the cut segment from
     "Start speaking" to timeout is **discarded**, nothing is uploaded —
     there is nothing to test-transcribe. Clicking the retry button cuts a
     fresh segment at that click and restarts the wait.

5. **"Too quiet" detection** (deterministic, no model call), evaluated
   immediately once voiced-collection ends, **before** the test transcript
   runs:

   ```
   zu_leise = (rede_mess < 3 * boden_mess) || (voiced_ms_collected < 2000)
   ```

   On `zu_leise`: show a small horizontal bar, "your voice vs. the room"
   (`#kalibrierung-balken`, see note below), with a mark at the level that
   would have been "enough" (same `3 * boden_mess` ratio, scaled onto the
   bar), plus plain text: "That was too quiet for the phone to follow
   reliably." Then, staggered by a **per-session** counter (reset to 0 on a
   fresh `sitzung`, incremented on every `zu_leise` outcome from this step
   *or* step 7's post-transcript check below — both feed the same counter):

   - **1st** `zu_leise` this session: "Move the phone closer to the middle,
     and speak a little louder — then try again." Button **"Try again"**
     restarts **only** step 4 (voiced-collection step; silence result
     stays valid).
   - **2nd (and any later) `zu_leise` in a row** this session: "The room is
     too big or too loud for one phone in the middle. Pass the phone
     around: whoever speaks holds it (or puts it next to them). Then try
     again." Buttons **"Try again"** (same as above) **and** "Continue
     anyway" (proceeds to step 6/7 with the current, too-quiet measurement
     anyway — nothing here ever permanently blocks the group). On this 2nd
     occurrence, also persist `kalibrierung_modus = 'herumreichen'` on the
     **group** (new additive column on `gruppe`, nullable TEXT, same
     migration convention as every other additive column in `db.py` — not
     `localStorage`, this is shared across the whole group/every device,
     not per-device acoustic data). See 2f for the reminder this produces
     at later session starts.
   - When `zu_leise` is false: skip straight to step 6.

   (The "your voice vs. the room" bar is a simple, separate visual element
   from Task 3's level-meter threshold mark — Task 3's mark lives on the
   always-visible `#pegel` bar during live recording, this one is a small,
   one-off comparison shown only inside the calibration panel. Do not merge
   the two or make Task 3 depend on this one; keep them visually/DOM
   independent, reuse styling only if convenient.)

6. **Test transcript** (skipped if the group clicked "Try again" above —
   only reached on a non-`zu_leise` result or an explicit "Continue
   anyway"): upload the cut clip from step 4 through the **same** `_audio`
   endpoint and pipeline every other web segment uses, but tagged as
   calibration audio (new orthogonal upload flag, see 2e) rather than a
   normal `grund`. It is transcribed by Whisper exactly like any other
   segment technically, but a calibration-tagged `aufnahme` row:
   - is **never** a `teil_von` any interview (bypasses
     `klasse_fuer`/`stelle_interview_sicher` entirely server-side — see 2e),
     so it structurally cannot be concatenated into
     `repo.zusammengefuegtes_transkript` or verdichtet;
   - **never** gets a `nachricht`-table row written for it (skip
     `repo.merke_nachricht` for this upload specifically), so it cannot
     appear in `kontext.baue`'s window, the Erkenner, or the Journal;
   - **never** triggers a Gesprächszug (find wherever a successful `kurz`
     transcription normally schedules a conversational reply — grep
     `_kurz_abschliessen`/the post-transcription dispatch in `aufnahme.py`
     — and add an early, explicit branch for the calibration flag that
     stores the transcript/status on the `aufnahme` row and returns,
     skipping that scheduling entirely);
   - is excluded from the **visible web chat history** too (add an
     explicit `AND (kalibrierung = 0 OR kalibrierung IS NULL)` — or
     equivalent — to whatever `web_post`-reading query backs
     `web_daten.web_chatverlauf`/`web_chatzustand`'s message list; this is
     the literal, mutation-testable filter the card's test (g) wants, test
     it by inserting a `kalibrierung=1` `web_post` row directly and
     asserting it's absent from the returned list, independent of the
     `aufnahme`-side guards above).

   The client needs to read the finished transcript back without it ever
   appearing as a normal chat bubble. Add one small, explicit channel for
   this — e.g. one more key in whatever dict `web_daten.web_chatzustand`
   already returns (the same poll the chat UI already runs every
   `POLL_MS`/`POLL_MS_HINTERGRUND`), reporting the status
   (`laufend`/`fertig`/`fehler`) and transcript text of the most recent
   calibration upload for this `chat_id` that the client is currently
   waiting on (keyed by the `message_id` the `_audio` upload's response
   already returns — reuse that, do not invent a second id scheme).
   Mirror the existing `schnittgrund`/`brainstorm` precedent (both
   duplicated on `web_post` *and* `aufnahme`, per Task 1's `rede_ms` work)
   rather than inventing a new plumbing shape.

   **Web channel only.** Telegram has no analogous flow and nothing here
   should touch `telegram.py`'s existing behavior — a calibration upload is
   impossible to produce from the Telegram client, so no Telegram-side
   guard is even needed; just don't let anything in this step assume a
   Telegram code path exists.

7. **Group confirmation**, once the transcript is back:

   > "We heard: '<transcript>'. Is that what was said?"

   Buttons **"Yes, correct"** / **"No, try again"** — these are pure
   client-side choices (no server knopf/callback needed, this is not a
   knopf-press in the `knoepfe/` sense, just local JS state):

   - **"Yes, correct"**: re-run the same `zu_leise` check, this time adding
     the transcript itself: `zu_leise_final = zu_leise || transcript is
     empty/whitespace || word count < 3` (feeds the **same** per-session
     counter and staggered messaging as step 5 if true — i.e. an empty/
     too-short test transcript is treated exactly like a quiet measurement,
     with the same 1st/2nd staged hints, and loops back to step 4 the same
     way). If not `zu_leise_final`: compute
     `schwelle = clamp(sqrt(boden_mess * rede_mess), 0.004, 0.08)`
     (geometric mean). **Separately**, regardless of the transcript
     outcome, if `rede_mess < 2 * boden_mess` (a *different*, looser ratio
     than step 5's `3 *` — both checks are intentional and both stay, one
     gates the retry loop, this one is a final defensive override): show
     "The room is loud or the phone is far away — move it closer to the
     speakers." and force `schwelle = 0.006` instead of the computed value
     (do not retry here — the group already confirmed the transcript was
     right, this is just a defensive floor on the final number). On
     success: show "Room measured ✓ — you're ready.", store the three
     `localStorage` keys (2g), mark `sitzung.kalibriert = true`, and start
     normal recording (`pegelAn(sitzung)`, per 2d's formula).
   - **"No, try again"**: same as an empty/too-short transcript above —
     back to step 4 (voiced-collection step only; the step 2 silence result
     stays valid), with the concrete tip from step 5's staged messaging.

8. **"Skip" shortcut** (`#kalibrierung-skip`): a small button, visible
   throughout steps 1-7 (not step-gated, always clickable while the
   calibration panel is open). Click: abort immediately, set
   `sitzung.vadSchwelleFix = 0.006` (the fallback, same literal value as
   everywhere else in this task), `sitzung.kalibriert = true`, hide the
   calibration panel, start normal recording. Does **not** write to
   `localStorage` — skipping is a one-off bypass for *this* session, not a
   measurement result worth caching for the next one.

### 2b. What "session" means here, and the `localStorage` cache (the approved E6 exception)

Hook calibration into `beginneAufnahme(sitzung)` (around line 1492) — the
one place both `starteInterview`/`fortsetzeInterview` and
`starteBrainstorm`/`fortsetzeBrainstorm` funnel through
(`test_beginneaufnahme_ist_der_einzige_ort_der_die_aufnahme_beginnt` already
locks this in; do not duplicate the hook into all four callers). Add a flag
on the `sitzung` object, e.g. `sitzung.kalibriert` (`false` on a fresh
`sitzung`, `true` once calibration finishes or is skipped). `beginneAufnahme`
must start the `MediaRecorder` (`neuesSegment`) **immediately**, same as
today ("sofort aufnehmen" — never delay the actual start of recording for
calibration UI, that would lose the opening words of the real discussion).
What calibration gates is only `pegelAn(sitzung)` (the per-120ms VAD
cut-decision loop) and the `segmentTakt` fallback — neither may start making
pause/cap cut decisions on the real recording until a threshold is known
(the step-4/6 calibration clip-cuts described above are a separate,
explicit cut path, not the normal VAD loop).

Before running the step-1..8 flow, check `localStorage` for `vad_boden_mess`,
`vad_rede_mess`, `vad_schwelle` (three separate keys — see Global
Constraints for the exact, narrow E6 exception these three keys have). All
three must be present and numeric to count as cached; if so, apply them
immediately (`sitzung.kalibriert = true`, go straight to `pegelAn`) and skip
the entire UI flow — this is what keeps calibration from being a fresh,
multi-step tax on every single Interview/Brainstorm start throughout a
workshop day once a device has measured its room once. On success at the
end of step 7, overwrite all three keys with the new result.

Add an always-available **panel-level** "Measure again" button
(`#kalibrierung-neu`, distinct id from step 4's in-flow
`#kalibrierung-nochmal-hoeren` — see note there), visible whenever
`#pegel`/`#uhr` are visible (wire it the same way `uhrAn`/`anzeigeAus`
toggle `pegelFeld.hidden`). Clicking it **always** restarts the **whole**
flow from step 1 (ignoring any cache), and on completion overwrites the
three `localStorage` keys and applies the new threshold to the
**currently running** session in place (no need to stop/restart the actual
recording to pick up a fresh calibration).

### 2c. Env kill-switch

`IT_WEB_VAD_KALIBRIERUNG` (default on/`"1"`, `"0"` disables), read in
`_vad_werte()` next to the other four `IT_WEB_VAD_*` reads, exposed as a new
`data-vad-kalibrierung` attribute on `#fuss`. When `"0"`: skip the entire
flow unconditionally (no UI, no `localStorage` check), go straight to
`pegelAn(sitzung)` with `sitzung.vadSchwelleFix` unset, and `pegelAn` must
fall back to **exactly today's** fixed-env algorithm
(`RMS_SCHWELLE`/`BODEN_FAKTOR`/`BODEN_DECKEL_FAKTOR=10`, byte-for-byte, not
an approximation) — this is the live rollback switch if the measured
approach misbehaves during the workshop.

### 2d. Threshold computation in `pegelAn` once calibrated

Unchanged from the original design (Birk's correction only changed *how*
`vadSchwelleFix`/`vadBodenMess` get set, not what happens with them
afterward): replace, **only when calibration is active and the session has
a `vadSchwelleFix`**, the current

```js
var boden = Math.min(sortiert[...0.1 percentile...], RMS_SCHWELLE * BODEN_DECKEL_FAKTOR);
var schwelle = Math.max(RMS_SCHWELLE, boden * BODEN_FAKTOR);
```

with a version where the fixed, calibrated threshold is the **ceiling**,
and the rolling floor can only pull it down (per the card: "Boden darf sich
nur noch NACH UNTEN anpassen ... nach oben höchstens bis 2x `boden_mess`"):

```js
var bodenDeckel = sitzung.vadBodenMess * 2;   // statt RMS_SCHWELLE * 10
var boden = Math.min(sortiert[...0.1 percentile...], bodenDeckel);
var schwelle = Math.min(sitzung.vadSchwelleFix, Math.max(RMS_SCHWELLE_ABS_MIN, boden * BODEN_FAKTOR));
```

(`RMS_SCHWELLE_ABS_MIN = 0.004`, the same clamp floor used in step 7's
`schwelle` computation, so the dynamic adjustment can never push the
threshold below the absolute floor the fixed calibration was already
clamped to.) When calibration is inactive (2c) or this session has no
`vadSchwelleFix` yet, keep today's exact fixed-env computation unchanged.

### 2e. Server: the `kalibrierung` flag, mirroring `brainstorm`/`rede_ms`

Add a new boolean flag, duplicated on both `web_post` and `aufnahme`
(additive columns, `kalibrierung INTEGER NOT NULL DEFAULT 0`), threaded
through the **exact same stops** Task 1 already used for `rede_ms` and that
`brainstorm` already uses — `_audio`'s query parsing (new `&kalibrierung=1`
param), `repo.lege_web_post_an`/`lege_aufnahme_an`, `web_kanal`'s voice
dict, `telegram.lies_nachricht` (always `False` for a real Telegram
update), and `aufnahme.empfange`. In `empfange()`, when the flag is set:
force `klasse = "kurz"` and `teil_von = None` **unconditionally** — do not
call `klasse_fuer`/`stelle_interview_sicher` for this upload at all,
regardless of whatever interview/brainstorm mode the group happens to be in
server-side at that moment (the client may have already sent `/interview`
before calibration runs, per the existing `starteInterview` ordering — that
must not pull a calibration clip into the interview).

Add the explicit exclusion filters described in step 6 above: (1) the
`web_post`-reading query behind the visible chat history excludes
`kalibrierung = 1` rows; (2) `repo.zusammengefuegtes_transkript`'s
`WHERE teil_von = ?` query gets a defensive `AND (kalibrierung = 0 OR
kalibrierung IS NULL)` even though `teil_von` is never set on a calibration
row by construction — this is the literal, mutation-testable guard the
card's test (g) asks for; prove it by inserting a row with `teil_von`
pointing at a real interview head **and** `kalibrierung = 1` directly via
`repo.lege_aufnahme_an` (bypassing `empfange()`'s own guard, simulating a
hypothetical future regression) and asserting its text is excluded from
the concatenation — removing the added `AND` must turn that test red; (3)
`empfange()` skips `repo.merke_nachricht` for a calibration upload, which
is what keeps it out of `kontext.baue`'s window/Erkenner/Journal — prove
this one with a test that calls `empfange()` with the flag set and asserts
no matching row exists afterward in whatever function `kontext.baue` reads
its message window from.

Add the small client-readback channel from step 6 (status + transcript of
the group's current in-flight calibration upload) to
`web_daten.web_chatzustand`'s returned dict.

Add the post-transcription dispatch guard from step 6 (skip the normal
Gesprächszug-scheduling path for a calibration row) — locate the existing
dispatch (grep `_kurz_abschliessen`/the function `aufnahme.verarbeite`'s
success path calls after a `kurz`-classed transcription succeeds) and add
an early, explicit branch keyed on the `kalibrierung` flag.

### 2f. `kalibrierung_modus` and its reminder

New additive column on `gruppe`: `kalibrierung_modus TEXT` (nullable,
only ever written with the literal value `'herumreichen'`, as described in
step 5 — no clearing logic, the card does not ask for one and none should
be invented). Thread it into whatever dict already feeds `chat_html`'s
initial `daten` (same place `interviewmodus`/`phase` already come from),
exposed as a `data-kalibrierung-modus` attribute on `#fuss`. At the start
of **every** fresh `sitzung` (new Interview/Brainstorm start — not resume,
same granularity as Task 4's one-per-session hint, and independent of
whether calibration itself ran or was skipped/cached on this device, since
this is a **group**-level setting, not a per-device one) show, once:

> "Remember: pass the phone to whoever speaks."

only when `data-kalibrierung-modus === 'herumreichen'`. Guard with a
per-`sitzung` flag the same way Task 4 guards its hint, so a second segment
in the same session does not repeat it.

### Tests to add (binding — items a-j from the card, mapped to what to test)

- **(a)** No click on "Start measuring" → no silence countdown starts.
  Mutant: auto-starting the countdown on `beginneAufnahme` without the
  click → this test goes red.
- **(b)** No click on "Start speaking" → no voice-wait/collection starts.
  Mutant: an automatic transition straight from silence-measured into
  voice-waiting → red.
- **(c)** Voice arriving at ~20s (well inside the 30s wait) still succeeds.
  Mutant: shortening the wait budget to 10s → red.
- **(d)** `zu_leise` triggers when `rede_mess / boden_mess < 3`. Mutant:
  changing the factor to `1` → a case that should be "too quiet" is no
  longer detected → red.
- **(e)** A second consecutive `zu_leise` outcome in one session shows the
  "pass the phone around" hint **and** writes `kalibrierung_modus =
  'herumreichen'` on the group. Mutant: removing the counter/the group
  write → red.
- **(f)** The "Remember: pass the phone to whoever speaks." reminder
  appears **exactly once** per later listening-session start when
  `kalibrierung_modus = 'herumreichen'` — not on every poll, not twice, not
  on a resume.
- **(g)** Calibration audio (`kalibrierung = 1`) never appears in the
  phase context window and never in the interview concatenation. Mutant:
  removing either added filter from 2e → an existing (or newly added)
  context/concatenation test goes red because the calibration text
  suddenly shows up.
- **(h)** "No, try again" (or an empty/short test transcript) restarts
  **only** the speech-measurement step (4), not the silence measurement.
- **(i)** Order of the flow — placement/announcement → "Start measuring" →
  silence countdown → "Start speaking" → voice wait/collection → test
  transcript → confirmation — is not skippable except via the explicit
  "Skip" button. Prefer a Playwright e2e case if the project's existing
  harness makes that cheap (check `tests/e2e/test_web_chat_vad_e2e.py`'s
  `_MESSUNG` fake-AnalyserNode fixture — it is directly reusable here for
  driving the simulated RMS level through each step); otherwise a thorough
  string/structure-level test against `_CHAT_JS` proving each step's
  trigger is gated behind the right `addEventListener`/flag and nothing
  else advances it. If Playwright is unavailable in this environment, say
  so explicitly in the report rather than silently skipping coverage.
- **(j)** The Telegram channel is untouched: whatever regression test
  already locks `telegram.lies_nachricht`'s fixed key set (Task 1 added one
  for `rede_ms` — find and extend it, or confirm it already covers this)
  stays green, and no calibration code path is reachable from
  `interview_theater/telegram.py`.

Run `pytest tests/test_web_chat_js.py tests/test_aufnahme.py
tests/test_web_chat_audio.py tests/test_db.py -q` (plus whatever
`kontext`/`verdichter`/`web_daten` test files end up touched by 2e/2f) and
the e2e file if Playwright is available, before committing.

---

## Task 3: Visible threshold mark on the level meter

**Context:** `interview_theater/web_chat.py`, the `#pegel` bar (CSS around
line 313-314: `.pegel { ... } .pegel span { ... width: 0 ... }`, JS in
`pegelAn`'s `pegelTakt` callback around line 1324-1330, which sets
`pegelBalken.style.width` from the **frequency-domain** average
(`getByteFrequencyData`, scaled `* 2.2`) — a different metric than the
**time-domain RMS** that actually drives the VAD cut decision
(`getFloatTimeDomainData`). Already approved by Birk (per the card, "von
Birk bereits bestätigt, Teil von t_cf87ee0a"). Keep this small — no layout
redesign, just a thin line and a two-color bar.

Because the visible bar and the VAD threshold are measured on two different
scales today, a literal "draw a line at the RMS threshold on the frequency-
based bar" would be meaningless. Resolve this by switching the **visible
bar's** width calculation to the same RMS value already computed one line
below it in the same callback (`rms = Math.sqrt(quadratsumme / ...)`) — one
metric driving both the display and the cut decision, instead of two
unrelated ones. Pick a display scale constant, e.g. `PEGEL_MAX_RMS = 0.3`
(cap for 100% bar width — document the choice with one short comment, no
`IT_WEB_VAD_*` override needed, this is purely cosmetic), and compute:

```js
pegelBalken.style.width = Math.min(100, (rms / PEGEL_MAX_RMS) * 100) + '%';
```

Add a thin marker element inside `#pegel` (HTML in `_fuss_html`, around line
2265):

```html
<div class="pegel" id="pegel" hidden><span></span><i class="pegel-schwelle"></i></div>
```

CSS (near line 313-314):

```css
.pegel { position: relative; height: .45rem; border-radius: .3rem; background: #e0ddd6; overflow: hidden; }
.pegel span { display: block; height: 100%; width: 0; background: #e0ddd6; }
.pegel i.pegel-schwelle { position: absolute; top: 0; bottom: 0; width: 2px; background: #555; }
```

(Adjust exact colors to taste/consistency with the existing palette — the
functional requirement is: bar is one color above the line, a visually
distinct second color/grey below it, line itself is a thin, clearly visible
mark. Simplest correct implementation: keep `span`'s own color **grey**
always, and set the marker `i`'s `left` from the same `PEGEL_MAX_RMS` scale
as the bar, then overlay a **second**, green-colored span clipped to the
bar's own current width via `width`/`background` — pick whichever approach
is fewer lines; "grün über, grau unter der Linie" just needs the part of
the bar above the threshold to read as a different color from the part
below it, by any correct CSS means.)

In the `pegelTakt` callback, after computing `rms` and `schwelle` (whichever
of the two formulas from Task 2d applies), set the marker position and the
bar's color state:

```js
var schwellePct = Math.min(100, (schwelle / PEGEL_MAX_RMS) * 100);
pegelSchwelle.style.left = schwellePct + '%';
pegelFeld.classList.toggle('ueber-schwelle', rms > schwelle);
```

with the two-color rule expressed in CSS keyed off `.pegel.ueber-schwelle
span { background: <green>; }` (default/else color stays whatever the
below-threshold grey is).

### Tests to add

- A test reading `web_chat._CHAT_JS` (string-level, same style as the rest
  of `tests/test_web_chat_js.py`) asserting the marker element exists
  (`'<i class="pegel-schwelle">' in <rendered HTML>` via the `seite`
  fixture) and that the JS sets its `style.left` from a computed percentage
  tied to `schwelle` (grep for `pegelSchwelle.style.left` and the formula
  that references the current session's threshold variable, whichever name
  Task 2 settled on — `sitzung.vadSchwelleFix` or the dynamically-adjusted
  `schwelle` local).
- A live-in-`node` test (same `_extrahiere`/`_fuehre_js_aus` helper pattern)
  computing the percentage-position function in isolation against a couple
  of `(schwelle, PEGEL_MAX_RMS)` pairs, if you factor it into a standalone
  function — otherwise a string-level assertion of the formula is
  sufficient; use judgment on which gives better signal for the size of
  this change.

---

## Task 4: One-time "check the transcript" hint after the first segment of a session

**Context:** per the card: *"Check the transcript in the chat — if words
are missing, move the phone closer."* Shown once per Interview/Brainstorm
session (not once per segment, not once per device/forever) — English text,
Padua profile, same `_TEXT_*`/`sprachen/en/texte.toml` convention as the
rest of this plan.

Add `_TEXT_MITLAUF_HINWEIS` (German literal e.g. `"Schaut den Mitschnitt im
Chat nach -- fehlen Worte, haltet das Handy näher ran."`; English mirror
**exactly** the card's wording: `"Check the transcript in the chat — if
words are missing, move the phone closer."`), wired through `_JS_TEXTE` and
the `T._TEXT_*` override dict in `_js()`, same pattern as every other text
in this plan.

Add one DOM element (`_fuss_html`, near the other transient-message
elements like `#fehler`): `<p class="mitlauf-hinweis" id="mitlauf-hinweis"
role="status" hidden></p>`.

Show it exactly once per `sitzung`: add a guard flag (e.g.
`sitzung.hinweisGezeigt`), and trigger it the first time a segment for that
`sitzung` is finalized in `onstop` (after the `if (teile.length && ...)`
block from Task 1a — the natural "first segment of this session just
finished" point) when `!sitzung.hinweisGezeigt`:

```js
if (!sitzung.hinweisGezeigt) {
  sitzung.hinweisGezeigt = true;
  if (mitlaufHinweisFeld) {
    mitlaufHinweisFeld.textContent = TEXT.mitlauf_hinweis;
    mitlaufHinweisFeld.hidden = false;
  }
}
```

Hide it alongside the other transient recording UI when the session ends
(wherever `anzeigeAus()`/`gibFrei()` already hide `#uhr`/`#pegel` — add one
more hidden-toggle line there) so it does not linger into a later screen
state. One hint per **session**, not per device forever: a brand-new
`sitzung` (new Interview/Brainstorm start) always gets its own
`hinweisGezeigt = false`, no `localStorage` involvement here at all (this is
UI guidance, not acoustic calibration data — do not conflate it with Task
2's narrow E6 exception).

### Tests to add

- A test asserting the element and text exist and are wired (string-level,
  same style as the rest of the file): the guard flag is checked before
  showing, the flag flips to `true` on first show, and a second `onstop` for
  the same `sitzung` does not re-show it (you can assert this from reading
  the JS structure — an actual runtime assertion via a live-in-node
  extraction of the small guard block is a reasonable alternative if it is
  cheap to isolate).
- `web_chat._JS_TEXTE["mitlauf_hinweis"] == web_chat._TEXT_MITLAUF_HINWEIS`
  (same shape as the existing `test_der_hinweis_mit_zwei_knoepfen_steht_in_der_seite`
  assertion for `modus_weg`).

---

## Final verification (after all four tasks, controller — not a subagent task)

1. Full suite in the background (see Global Constraints for the exact
   command), polled to completion, log read afterward. Quote the final
   summary line and exit code in the completion report.
2. `python -m scripts.pruefe_profil dortmund-2026` and
   `python -m scripts.pruefe_profil padua-2026` (check `--help` first for
   exact flags/invocation) — both must exit 0.
3. Dispatch the final whole-branch code review per
   superpowers:requesting-code-review against the merge-base, covering all
   four tasks together (cross-task consistency: the `localStorage` E6
   exception stays narrow, the `rede_ms` plumbing is complete end-to-end,
   no leftover references to the removed `genug` gate or the
   brainstorm-only empty-transcript branch).
