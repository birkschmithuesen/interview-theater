# Final-review fix report — two integration-level findings (03.10.2026)

Branch: `wt/t_98928a4e`
Base: HEAD at session start, commit `fb1fe18` ("Add fragen_auswertung.py:
own-vs-AI question counts for chat/dashboard (Task 14)")

Note: this file previously held a report for an unrelated branch/review
(different findings, different branch name). It has been overwritten here
per the task instruction to write this exact path.

## Finding 1: stale `fragen_herkunft`/`fragen_bearbeitet` leak into a fresh
classic question round after an A/B reveal

**File:** `interview_theater/knoepfe/fragen.py`

**Root cause confirmed.** `_reset_fragenrunde` (line 195) only cleared
`fragen_aktuell`/`fragen_entschieden`/`fragen_warte_auf`. It is called from
both `biete_fragenauswahl` (every classic fresh round, including the
"nothing accepted → new direction" fallback) and from
`versuche_gegenueberstellung` (the A/B reveal). When a group runs the A/B
reveal (which sets `fragen_herkunft`) and then rejects *every* question in
the one-by-one walkthrough, `_schliesse_fragen_ab`'s `if not angenommen:`
branch calls `frage_fuer_andere_richtung` → `_starte_auftrag`, which (in
production) comes back as a brand-new classic `VORSCHLAG FRAGENAUSWAHL:`
block dispatched through `biete_fragenauswahl` — not through
`uebernimm_eigene`/`versuche_gegenueberstellung`. The old `fragen_herkunft`
from the prior reveal round was never cleared, so `_zeige_frage` would apply
stale, misaligned `" (eure)"`/`" (KI)"` tags to the unrelated new questions,
and any later `_schliesse_fragen_ab` would build `fragen_herkunft_final`
from indices that no longer line up with the same questions — corrupting
Task 14's dashboard/chat evaluation counts for that group.

**Fix.**

1. `interview_theater/knoepfe/fragen.py:195-222` — `_reset_fragenrunde` now
   also sets `fragen_herkunft` and `fragen_bearbeitet` to `None`, with a
   docstring addition explaining the scenario and why this is the single
   correct place for the reset (every fresh-round path, including the
   fallback, already calls it).
2. `interview_theater/knoepfe/fragen.py:445-450` — **required companion
   change**: `versuche_gegenueberstellung` itself sets `fragen_herkunft` for
   *its own* reveal round and then called `_reset_fragenrunde` immediately
   afterwards. Adding the clear-on-reset to `_reset_fragenrunde` without
   reordering would have made the reveal immediately erase its own
   just-written `fragen_herkunft` on every single call — a regression I
   caught by reasoning through the call order before running anything.
   Fixed by swapping the order: `_reset_fragenrunde(conn, chat_id)` now runs
   **before** `repo.setze_arbeitsstand(conn, chat_id, "fragen_herkunft",
   ",".join(herkunft))`. A comment documents why the order matters.

No other call site sets `fragen_herkunft`/`fragen_bearbeitet` (confirmed via
grep across `interview_theater/`), so no further adjustments were needed.

**Regression test added:**
`tests/test_fragen_eigene_ki.py::test_reset_fragenrunde_entfernt_stale_herkunft_nach_abgelehnter_gegenueberstellung`

Reuses the existing fixtures/helpers from that file
(`_bereite_gegenueberstellung_vor`, the `auftraege` fixture that records
instead of executing `ablauf.starte_auftrag`, `knoepfe.entscheide`/
`knoepfe.starte_durchgehen`, the `_TG` pattern already used by
`test_herkunft_final_passt_zu_fragen_nach_abschluss`). It:

1. Runs `_bereite_gegenueberstellung_vor` + `fragen.versuche_gegenueberstellung`
   to produce an 8-question reveal round with `fragen_herkunft` populated.
2. Rejects every one of the 8 questions via `knoepfe.entscheide(..., "nein")`,
   confirming the "nothing accepted" fallback fired (`auftraege` got an
   entry, `T._TEXT_FRAGEN_KEINE_ANGENOMMEN` was sent).
3. Simulates the model's reply to that fallback arriving as a classic round
   by calling `fragen.biete_fragenauswahl(conn, tg, CHAT, "Neu: ...")`
   directly (since `_starte_auftrag` is faked, not executed, in this test
   environment — matching how the file's other tests isolate the LLM call).
4. Asserts `fragen_herkunft`/`fragen_bearbeitet` are empty/absent after that
   call, that `_zeige_frage` shows no stale `" (eure)"`/`" (KI)"` suffix on
   the new question, and that after accepting both new questions,
   `fragen_herkunft_final` is all-empty (no leaked indices from the old
   round).

**Confirmed it would have caught the bug**: I temporarily reverted just the
two added lines in `_reset_fragenrunde` (restored afterwards) and reran only
this test —

```
uv run python -m pytest tests/test_fragen_eigene_ki.py::test_reset_fragenrunde_entfernt_stale_herkunft_nach_abgelehnter_gegenueberstellung -q
```

→ failed with `AssertionError: assert not 'eigen,ki,ki,ki,eigen,ki,ki,ki'`
(the stale herkunft from the rejected reveal round). After restoring the fix,
the same test passes and the full file (28 tests) is green.

## Finding 2: asymmetric mutual exclusion between Diskussion (Phase 1) and
Brainstorm (Phase 4) recording in the chat JS

**File:** `interview_theater/web_chat.py` (`_CHAT_JS` template)

**Root cause confirmed.** Commit `095e6e9` added `|| zustand.brainstorm` to
`starteDiskussion()`'s guard (and `starteInterview()`/`startePtt()` already
guarded against `zustand.brainstorm`), but the reverse direction was never
applied: `starteBrainstorm()`'s guard, `brainstormKnopf.disabled`'s
computation, and `startePtt()`'s guard did not check `zustand.diskussion`.
The realistic scenario: a group starts "Zuhören"/Diskussion-Modus in Phase 1,
never explicitly ends it while progressing forward through phases (normal
flow direction), then in Phase 4 presses the Brainstorm button (now visible
since it's server-gated on `phase == 4`) — starting a second `MediaRecorder`
on the same microphone while the Diskussion recorder/segment-upload loop is
still live. Same risk for Push-to-Talk.

**Fix.** Three guard additions, symmetric to the existing
`starteDiskussion()` fix:

1. `interview_theater/web_chat.py` — `brainstormKnopf.disabled` computation
   (inside `zeigeBrainstormModus`): now
   `modusAn() || !!zustand.wechsel || !!zustand.diskussion`.
2. `interview_theater/web_chat.py` — `starteBrainstorm()`'s guard: now
   `if (zustand.brainstorm || modusAn() || zustand.wechsel ||
   zustand.diskussion) { return; }`.
3. `interview_theater/web_chat.py` — `startePtt()`'s guard: now
   `if (modusAn() || zustand.wechsel || zustand.brainstorm ||
   zustand.diskussion || zustand.ptt) { return; }`.

Each change has an inline comment explaining the symmetry with the existing
`095e6e9` fix and the concrete scenario it closes.

**The `zeigeModus()` question (explicitly asked to verify, not assume).** I
read `zeigeModus()`'s current body in full. It is the single place that
computes `interviewKnopf.disabled`/`pttKnopf.hidden`/the `nebenknopf` class
from the OR'd `nebenAn = !!zustand.brainstorm || !!zustand.diskussion`, and
it calls `zeigeBrainstormModus()` + `zeigeDiskussionModus()` at its end so
both side-channel buttons stay in sync on every poll tick. `starteDiskussion()`
itself, however, calls only `zeigeDiskussionModus()` after setting
`zustand.diskussion = sitzung` — not the merged `zeigeModus()` — so
`interviewKnopf.disabled`/`pttKnopf.hidden` are not updated until the next
poll, which is exactly the "narrower timing gap" the finding describes.

I checked whether this is unique to `starteDiskussion()` or a wider pattern:
it is the **same pattern everywhere** in this module.
`starteBrainstorm()`/`pausiereBrainstorm()`/`fortsetzeBrainstorm()`/
`beendeBrainstorm()` and `pausiereDiskussion()`/`fortsetzeDiskussion()`/
`beendeDiskussion()` all call only their own `zeige*Modus()`, never
`zeigeModus()` — including at the *end* of a session
(`beendeBrainstorm()` only calls `zeigeBrainstormModus()`), which has the
identical staleness window on the opposite transition. The explicit
Task-6-era comments ("Re-Review Fund 1") state this consolidation into
`zeigeModus()` was intentional, with the periodic poll (`zeigeModus()`
called from `hole()`) as the mechanism that resyncs `interviewKnopf`/`pttKnopf`
within one poll interval.

**Judgment call: left this part alone.** Swapping only `starteDiskussion()`'s
call to the merged `zeigeModus()` would fix that one start-transition but
leave the symmetric start-transition for `starteBrainstorm()` and all four
pause/resume/end transitions for both sessions with the identical gap —
an inconsistent, partial fix of a pattern that spans six functions, not one.
A complete fix would mean touching all of them, which is a materially larger
and more invasive change than the three guard additions the finding asked
for, and risks instructions explicitly warning against scope creep ("Keep
changes minimal and targeted"). Per the finding's own instruction ("if it's
ambiguous, leave this part alone... noting why"), I left `starteDiskussion()`
calling `zeigeDiskussionModus()` unchanged and did only the three guard
additions.

**Also noticed, left out of scope:** `starteInterview()`'s guard
(`if (zustand.aufnahme || zustand.wechsel || zustand.brainstorm) { return; }`)
is missing `zustand.diskussion` too, by the same reasoning as this finding.
The finding's "Fix" section explicitly lists only three locations
(`starteBrainstorm`, `brainstormKnopf.disabled`, `startePtt`), not
`starteInterview`, so I left it untouched to stay within the stated scope —
flagging it here for a possible follow-up finding.

**Regression tests added** (`tests/test_web_chat_js.py`), reusing the
project's existing Node-execution harness (`_node_oder_skip()`,
`_fuehre_js_aus()`, `_extrahiere()` — the same harness used by
`test_zeigemodus_fuehrt_brainstorm_und_diskussion_zusammen_in_node` and
`test_amunterenrand_entscheidet_live_in_node`):

1. **Updated** `test_brainstorm_und_interview_schliessen_sich_gegenseitig_aus`
   — it previously *positively asserted* the incomplete guard strings for
   `starteBrainstorm()` and `brainstormKnopf.disabled` (confirming the gap
   was locked in by an existing test, not just unnoticed). Updated both
   assertions to the corrected, complete guard strings.
2. **Added** `test_starteptt_lehnt_waehrend_diskussion_ab` — string-level
   assertion that `startePtt()`'s guard now includes `zustand.diskussion`
   (there was no prior test asserting its exact guard string at all).
3. **Added**
   `test_startebrainstorm_und_starteptt_lehnen_waehrend_diskussion_tatsaechlich_ab_in_node`
   — a **behavioral** Node test (not just string matching) that extracts
   `modusAn`, `starteBrainstorm`, and `startePtt` verbatim from `_CHAT_JS`,
   stubs only what's needed to exercise the synchronous guard path
   (`verwirfPtt`, `zeigeBrainstormModus`, `holeStrom` returning a
   never-resolving promise so the async `.then()`/`.catch()` branches never
   fire, and no-op timer functions so the Node process doesn't hang), and
   calls both functions with `zustand.diskussion` set vs. unset. Asserts
   that with `zustand.diskussion` truthy neither function starts a session
   (`zustand.brainstorm`/`zustand.ptt` stay falsy after the synchronous
   call), and — as a control — that without `zustand.diskussion` both
   *do* start normally (so the fix doesn't over-sperren the common case).
   This directly covers the realistic "forward flow through phases, Diskussion
   never ended" scenario the finding called out as more likely than the
   already-fixed direction.

Extraction-marker fix along the way: `js.index("function beendePtt")` matches
`function beendePttAnzeige` first (string prefix), which sits *before*
`startePtt` in the file — this made both the new string test and the new Node
test initially fail with an empty/garbled extraction. Fixed by using
`"function beendePtt() {"` (with the parenthesis) as the end marker in both
the existing-test-adjacent code I touched and the new tests.

Also reworded two inline comments (in `web_chat.py`) that initially quoted
the literal UI button label `"Zuhoeren starten"` — this exact string is
`_TEXT_DISKUSSION_AN`, and `test_ui_texte_stehen_nicht_als_literal_im_js`
correctly failed because it asserts every `_JS_TEXTE` value is absent from
`_CHAT_JS` as a literal (UI text must come from the `TEXT` object, never be
hardcoded twice). Reworded to describe the scenario without quoting the
label.

**Confirmed these tests would have caught the bug**: reverted the three
guard changes in `web_chat.py` (via Edit, restored afterwards — not a
literal git revert, since Bash access to `/tmp` and `cp` was denied by the
sandbox) and reran `tests/test_web_chat_js.py` —

```
uv run python -m pytest tests/test_web_chat_js.py -q
```

→ 3 failed (`test_brainstorm_und_interview_schliessen_sich_gegenseitig_aus`,
`test_starteptt_lehnt_waehrend_diskussion_ab`,
`test_startebrainstorm_und_starteptt_lehnen_waehrend_diskussion_tatsaechlich_ab_in_node`),
97 passed. The Node test failed with
`{'brainstormGestartet': True, 'pttGestartet': True}` for the
`waehrendDiskussion` case — i.e. both functions started a session despite
`zustand.diskussion` being set, exactly the bug. Restored the fix; full file
is green again (100 passed).

## Full regression run

Tooling: `uv run python -m pytest ...` (the `PY=
/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`
direct-invocation form was blocked by the sandbox's Bash permission layer;
`uv run python` uses the same interpreter and worked without issue).

Required subset:

```
uv run python -m pytest tests/test_fragen_eigene_ki.py tests/test_fragen_ki.py tests/test_diskussion.py tests/test_fragen_auswertung.py tests/test_web_chat_js.py tests/test_web_daten.py tests/test_sprache_bitgleich.py -q
```

```
........................................................................ [ 33%]
........................................................................ [ 66%]
........................................................................ [ 99%]
..                                                                       [100%]
218 passed in 22.70s
```

Full suite (not strictly required, run for extra confidence given these are
whole-branch-review findings):

```
uv run python -m pytest -q
```

```
6246 passed, 5 skipped in 589.95s (0:09:49)
```

Zero failures. A `ConnectionResetError`/"Exception occurred during
processing of request" traceback appears mid-run — this is pre-existing,
benign `socketserver` teardown noise from a web-server test closing a live
HTTP connection, not a test failure (exit code 0, no FAILED lines).

## Files changed

- `interview_theater/knoepfe/fragen.py` (Finding 1: `_reset_fragenrunde` +
  reordering in `versuche_gegenueberstellung`)
- `tests/test_fragen_eigene_ki.py` (Finding 1, regression test)
- `interview_theater/web_chat.py` (Finding 2: three guard additions in
  `_CHAT_JS`)
- `tests/test_web_chat_js.py` (Finding 2: one updated test, two new tests)

Nothing under `betrieb/` was touched. No push. All work stays on
`wt/t_98928a4e`. Phases 3/5/6/7 content and `prompts/erkenner.md` were not
touched — Finding 2's change to Phase 4's brainstorm button logic is
mutual-exclusion/guard logic, not a content change to Phase 4 itself.

## Concerns for the requester

1. **`starteInterview()`'s guard is missing `zustand.diskussion`** (see
   above) — same class of bug as Finding 2, but outside the finding's
   explicitly listed scope, so left untouched. Worth a follow-up look.
2. The `zeigeModus()`-vs-`zeigeDiskussionModus()` timing-gap question was
   investigated and deliberately **not** changed — see the judgment-call
   section above for the full reasoning (the gap is a module-wide pattern
   across six start/pause/resume/end functions, not specific to
   `starteDiskussion()`, so a one-call-site fix would be inconsistent and a
   complete fix is out of scope for a minimal, targeted bug fix).
3. For Finding 1, the companion reordering in `versuche_gegenueberstellung`
   (swapping `_reset_fragenrunde` and the `fragen_herkunft` write) was not
   explicitly spelled out in the brief but is logically required once the
   clear-on-reset lands in `_reset_fragenrunde` — without it, the fix would
   have broken the reveal round it was never supposed to touch. Flagging
   this clearly since it's an addition beyond the literal instruction,
   though it falls out directly from "this is the single, correct place to
   add it."
