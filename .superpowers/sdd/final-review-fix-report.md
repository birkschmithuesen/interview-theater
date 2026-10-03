# Final-review fix report — three findings (03.10.2026)

Branch: `padua-workshop/t_b87d075c-padua-phasen-4-7-neue-namen-frame-prose`
Base: HEAD `3a20b3e`

## Finding 1 (Important): "story overview" unreachable as a Phase-5 keyword

**Root cause confirmed**: `phasen.nummer_fuer` checks phases in ascending
order with a bidirectional substring test. Phase 4's pre-existing keyword
`"story"` is a substring of Phase 5's `"story overview"`, and Phase 4 is
checked first — so `"story overview"` (and anything containing it) always
resolved to Phase 4, even though `sprachen/en/prompts/phasen/5.md` actively
tells the group "a story overview appears".

**Fix**: removed `"story overview"` from Phase 5's `stichwoerter` list in
`workshop/padua-2026/phasen.toml`. Kept `"overview"`, which I confirmed does
**not** collide with any other phase's keywords (checked both substring
directions against every keyword in phases 1, 2, 3, 4, 6, 7 — no match).
`workshop/dortmund-2026/` was not touched (its phase list uses different
keywords entirely).

**Test**: extended the `@pytest.mark.parametrize` list in
`tests/test_profile_geruest.py::test_padua_stichwoerter_finden_die_phase`
with two cases, following the existing "Scenes as Story" precedent in the
same test:
- `("story overview", 4)` — documents that the phrase still (correctly, by
  design) resolves to Phase 4 via Phase 4's pre-existing "story" keyword,
  matching the already-documented collision class.
- `("overview", 5)` — locks in that Phase 5 is still reachable via its own
  keyword after the removal.

## Finding 2 (Important): false safety claim in `erkenner.ARTEN` comment

**Root cause confirmed**: the comment for `uebersicht_aendern` claimed
`entwurf.py` checks that the overview isn't yet fixed before acting. Neither
`entwurf.starte_uebersicht` nor its caller
`erkenner._starte_entwurf_uebersicht` read
`arbeitsstand.geschichte_uebersicht_fixiert_am` anywhere — so a recognizer
hit on `uebersicht_aendern` after the overview was already confirmed (e.g.
generic feedback on an in-progress Stage-B scene draft, misread as overview
criticism) would fire a second, paid Stage-A regeneration with its own
confirmation buttons stacking on top of the scene draft's pending ones.

**Fix**: added the missing guard directly in
`erkenner._starte_entwurf_uebersicht`, in the same early-return style as the
two existing guards (`workshop.prosa_entwurf_aktiv()` and
`_ist_phasenpassend(...)`): it now reads
`repo.hole_arbeitsstand(conn, chat_id)` and no-ops if
`geschichte_uebersicht_fixiert_am` is already set (guarding against the row
not existing yet, too). Updated the `ARTEN` comment and the function's
docstring to describe the check accurately and point at
`erkenner._starte_entwurf_uebersicht` as the actual enforcement point.

**Test**: added
`tests/test_entwurf.py::test_erkenner_uebersicht_aendern_ist_no_op_wenn_schon_fixiert`,
modeled on the sibling guard tests in the same file
(`test_erkenner_uebersicht_aendern_ist_stiller_no_op_ohne_padua_profil`,
`test_erkenner_uebersicht_aendern_wirkt_nur_in_phase_5`): sets
`geschichte_uebersicht_fixiert_am` via `repo.setze_arbeitsstand`, monkeypatches
`entwurf.starte_uebersicht` to record any call, and asserts it is never
called when `_starte_entwurf_uebersicht` runs with a recognized
`uebersicht_aendern` change.

## Finding 3 (Minor): stale comment in `tests/test_erkenner.py`

The comment above the `PHASEN_SPEZIFISCHE_ARTEN` test block said
`"uebersicht_aendern" existiert noch nicht als echte art` — false since a
later task added it to `erkenner.ARTEN` (confirmed via
`test_arten_enthaelt_alle_werte`, which asserts it's a member). Rewrote the
comment to state that it is a real `art` since Task 10, point at
`test_arten_enthaelt_alle_werte` for proof, and clarify that this block only
tests the `PHASEN_SPEZIFISCHE_ARTEN` table's gating, not the Stage-A start
itself (which is covered by the `_starte_entwurf_uebersicht` tests in
`tests/test_entwurf.py`).

## Commands run and results

```
python3.11 -m pytest tests/test_profile_geruest.py tests/test_erkenner.py -q -p no:cacheprovider -v
```
→ `148 passed in 7.57s`

```
python3.11 -m pytest tests/test_profile_geruest.py tests/test_erkenner.py tests/test_entwurf.py -q -p no:cacheprovider
```
→ `165 passed in 9.86s` (includes the new `test_entwurf.py` case)

```
python3.11 -m pytest -q -p no:cacheprovider
```
→ `5968 passed, 4 skipped in 524.18s (0:08:44)` — baseline was `5965 passed,
4 skipped`; the +3 are exactly the new test IDs added (two new parametrize
cases in `test_profile_geruest.py`, one new test function in
`test_entwurf.py`). Zero failures. The "Exception occurred during processing
of request" tracebacks mid-run are pre-existing, benign `socketserver`
noise from web-server tests (unrelated to this change, exit code 0).

```
python3.11 -m scripts.pruefe_profil --alle
```
→
```
Workshop-Profil dortmund-2026
dortmund-2026: in Ordnung
Workshop-Profil padua-2026
padua-2026: in Ordnung
```

## Files changed

- `workshop/padua-2026/phasen.toml` (Finding 1)
- `tests/test_profile_geruest.py` (Finding 1, regression test)
- `interview_theater/erkenner.py` (Finding 2: guard + comment/docstring)
- `tests/test_entwurf.py` (Finding 2, regression test)
- `tests/test_erkenner.py` (Finding 3)

`workshop/dortmund-2026/` was not touched. No merge, no push; all work stays
on the current branch.
