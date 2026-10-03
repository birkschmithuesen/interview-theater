# Task 13 Report: End-to-end test of the full Phase 5 two-stage flow

## Status: DONE

## What was built

Created `tests/test_entwurf_ablauf.py` with a single scripted test,
`test_phase5_ueberblick_bis_automatischer_sprung_nach_6`, that exercises the
whole Phase 5 (Prose Draft) two-stage flow from Tasks 5-12 end to end,
without any real network/model call.

## Step 1: finding and reusing the real fakes

Read `tests/test_schaerfung.py`'s `KLMAttrappe` (a `.schema(chat_id, system,
nutzer, schema, art, modell=None, temperature=None)` fake that records calls
and returns a fixed answer) and `tests/test_szene.py`'s `LLMAttrappe` (a
`.prosa(chat_id, system, nutzer, art, max_tokens=None, timeout=None,
bei_teil=None)` fake). Neither fake supports both interfaces, and this test
needs both: Stage A's overview call goes through `modellwahl.aufruf_schema`
-> `klm.schema(...)`, and Stage B's scene write goes through
`szene.schreibe` -> `klm.prosa(...)` (Phase 5 <= `szene.PHASE_PROSA` (6), so
`schreibt_prosa` is true and the prosa path is used, not the dialog/theatre
path).

Built a local `FakeKLM` in the new test file combining both interfaces,
matching the real signatures `modellwahl.aufruf_schema` and `szene.schreibe`
actually call (confirmed by reading `interview_theater/modellwahl.py` and
`interview_theater/szene.py` directly, not guessed). Each call returns a
version-numbered, distinguishable answer so the test can assert on real
content differences rather than just "something was returned."

Also discovered and reused the existing test-suite convention from
`tests/test_entwurf.py` (Task 9-12's own tests): call the real
production entry points (`knoepfe.behandle(...)` for button presses,
`erkenner._starte_entwurf_uebersicht(...)` for the chat-feedback intent) and
wait for their internally-spawned background threads to finish by
re-acquiring and releasing the module's own lock
(`entwurf._sperre_fuer(chat_id)` / `szene._sperre_fuer(chat_id)`,
`sperre.acquire(timeout=20)` then `.release()`) — this is the same pattern
already reviewed and committed in `tests/test_entwurf.py`, so the new test
reuses it rather than inventing a parallel monkeypatched-Thread mechanism or
a bespoke `Druck`/`_FakeDruck` object (the brief's sketch names were
placeholders; `knoepfe.behandle` + the existing `_druck` helper from
`tests/test_knoepfe.py` already build the real `Druck` via production code).

## Step 2: the five-step narrative, as actually implemented

1. **Overview generated (Stage A).** `entwurf.starte_uebersicht(conn, tg,
   klm, einst, chat_id)` is called directly (real thread), waited out via
   the lock. Asserts `arbeitsstand.geschichte_uebersicht` is non-empty and
   exactly one `.schema()` call happened.
2. **Chat feedback changes the stored overview — not a button.**
   `erkenner._starte_entwurf_uebersicht(klm, tg, conn, einst, chat_id,
   [{"art": "uebersicht_aendern", "wert": "make the ending sadder"}])` is
   called directly — this is the real function the erkenner's intent
   recognition dispatches to (phase- and profile-gated, confirmed by reading
   `interview_theater/erkenner.py`). `workshop.prosa_entwurf_aktiv` is
   monkeypatched to `True` since this is explicitly a Padua-only feature and
   the gate would otherwise make this a silent no-op (mirroring
   `tests/test_entwurf.py::test_erkenner_startet_die_uebersicht_in_phase_5`).
   Asserts: the new `geschichte_uebersicht` text differs from the first,
   that two `.schema()` calls happened total, that the feedback text
   ("make the ending sadder") and the first fassung both appear in the
   second call's user-text (proving it's a real regeneration-with-reference,
   not an unrelated fresh call).
3. **"Yes, save" starts Scene 1.** The two-button overview message sent by
   Stage A is read from the fake Telegram's recorded buttons, and
   `knoepfe.behandle(conn, tg, klm, einst, _druck(...))` is called — the real
   top-level button dispatch used in production (`bot.schleife` ->
   `knoepfe.behandle`). This runs `_wirkung_uebersicht_passt`, which calls
   `entwurf.uebernimm_szenenfelder` and `szene.starte` (real thread), waited
   via `szene._sperre_fuer`. Asserts scene 1's `prosa` field is non-empty,
   `volltext` stays empty (Phase 5 writes prosa, not theatre text), and
   exactly one `.prosa()` call happened.
4. **Scene 1 "Yes, save" auto-starts Scene 2.** Same button-click pattern on
   the scene-1 confirmation button that `szene.schreibe` sent after writing
   scene 1. Asserts scene 1 is marked `entwurf_bestaetigt_am`, scene 2 now
   has non-empty, distinct prosa, two `.prosa()` calls total, and the phase
   is still 5 (no premature jump).
5. **Scene 2 (last) "Yes, save" jumps to Phase 6 automatically.** Same
   pattern on scene 2's confirmation button. Asserts scene 2 is confirmed,
   the phase is now 6, and no third scene write happened.

## Verification

- `python3.11 -m pytest tests/test_entwurf_ablauf.py -q -p no:cacheprovider -v`
  → 1 passed.
- `python3.11 -m pytest -q -p no:cacheprovider` (full suite) → 5965 passed,
  4 skipped, exit code 0. (One unrelated traceback appears mid-run from a
  pre-existing web-server stress test closing a socket early — not from the
  new test file, and the suite still exits 0.)

## Commit

`de0b606` — "test: end-to-end trace of Phase 5's two-stage flow, chat
feedback included"

## Concerns / things worth flagging (not production bugs, just test-design
notes)

- The brief's literal sketch set up the test figure as `repo.setze_figur(db_conn,
  chat_id, "Alex", "")` (empty description, no sprachprofil). Against the
  real `szene.fehlendes()`/`szene.sperrtext()` logic, a figure with neither a
  sprachprofil nor a non-empty `beschreibung` blocks the scene write
  entirely (`szene.py`'s T5 sperre), which would have made the sketch's own
  assertions fail. I gave Alex a non-empty description
  ("quiet, used to notice things") instead — this is a test-fixture fix, not
  a production bug: the sperre behaved exactly as documented and tested
  elsewhere (`tests/test_szene.py::test_eine_figur_ohne_sprachprofil_haelt_die_szene_auf`
  and its sibling `test_eine_beschriebene_figur_ohne_interview_sperrt_nicht`).
- No production code was modified in this task.
