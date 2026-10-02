# Padua Phasen TEIL 1: Namen + Phase 5 Prose Draft + Chat-Intents als Daten — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename Padua's phases 4–7 (Frame · Prose Draft · Rewrite · Stage Version),
add a declarative phase→intent gating table that `erkenner.wende_an` consults, and
build phase 5 ("Prose Draft") into a two-stage flow — a confirmable story overview,
then scene-by-scene prose with full-text continuity, ending in an automatic jump to
phase 6 — all scoped to the Padua profile only, without touching phase 6/7 behaviour
or Dortmund's byte-identical output.

**Architecture:** Phase naming lives entirely in `workshop/padua-2026/phasen.toml`
(data, not code) and the English prompt layer under `sprachen/en/`. The new
two-stage prose flow is a new module `interview_theater/entwurf.py` that reuses
existing machinery wherever it already does the job: `schaerfung.starte`'s
`nachbereitung` hook to kick off after the automatic quote-matching pass,
`szene.starte`/`szene.schreibe` to actually write per-scene prose (it already
writes into `szene.prosa` instead of `szene.volltext` whenever
`phasen.aktuelle(...) <= szene.PHASE_PROSA` — and `PHASE_PROSA = 6`, so phase 5
already qualifies, no change needed there), and the existing "Passt" scene-button
handler, extended with one phase-5-specific branch for auto-advance instead of
phase 7's button-offer. A new phase→art gating table in `erkenner.py` keeps the
one genuinely new erkenner art (`uebersicht_aendern`) silent outside phase 5,
without touching any of the 23 existing arts. The whole two-stage flow is gated
behind a new profile switch (`[prosa_entwurf] aktiv = true`, same pattern as
`[laengen] aktiv`) so Dortmund's *behaviour*, not just its prompt bytes, is
provably unaffected — the switch is absent/false everywhere except Padua.

**Tech Stack:** Python 3.11, SQLite (additive schema via `_migriere_fehlende_spalten`),
pytest, TOML workshop profiles, existing LLM schema/prosa call wrappers
(`modellwahl.aufruf_schema`, `szene_claude`/`llm.LLM.prosa`).

## Global Constraints

- Branch stays `padua-workshop/t_b87d075c-padua-phasen-4-7-neue-namen-frame-prose`. Never merge, never push, never touch `main`.
- Run `pytest` with `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider` after every task; commit only once it is green (baseline: 5928 passed, 4 skipped — compare against this, not zero).
- Dortmund's profile (`workshop/dortmund-2026/**`) is **never edited** by this plan. Any task touching shared code must re-run `tests/test_profil_bitgleich.py` and `python -m scripts.pruefe_profil dortmund-2026` and confirm they still pass.
- No new phase-specific behaviour may fire for Dortmund or the built-in default profile — gate all new runtime behaviour behind `workshop.prosa_entwurf_aktiv()` (new accessor, Task 7), which is `False` unless a profile sets `[prosa_entwurf] aktiv = true`.
- Phase **numbers** never change (SPEC/AGENTS.md: "Die Phase setzt allein die Gruppe"). Only `name`/`stichwoerter` of Padua's phases 4–7 change; old names/keywords remain recognised as aliases.
- No commit may contain `betrieb/*.env` content, `betrieb/soap.db`, or real transcript/interview text.
- Any new erkenner `art` needs ≥2 positive corpus cases (DE **and** EN, since both `korpus/erkenner.jsonl` and `korpus/en/erkenner.jsonl` exist) to satisfy `tests/test_korpus.py::test_erkenner_jede_art_mindestens_zweimal`, and the existing FP=0 regression rule applies if `scripts/pruefe_prompts` is actually run against the real model.
- No commit disables or weakens `tests/test_knoepfe_struktur.py`'s AST-level guarantees (every `ART_*` has a handler in `_WIRKUNGEN`, no model call inside a button handler).
- `repo.py` stays the only place with SQL for bot-side tables (aside from `db.py`); `entwurf.py` must not contain raw SQL — it calls `repo`/`szene`/`schaerfung`/`modellwahl` functions only, same discipline as `schaerfung.py`.

---

## Context the implementer needs before starting

**Phase mapping (numbers unchanged):**

| # | Old Padua name | New Padua name |
|---|---|---|
| 1 | Terms | Terms (unchanged) |
| 2 | Questions | Questions (unchanged) |
| 3 | Interviews | Interviews (unchanged) |
| 4 | Setting, Characters & Story | Frame |
| 5 | Sharpening | Prose Draft |
| 6 | Scenes as Story | Rewrite |
| 7 | Polish | Stage Version |

**What already exists and will be reused as-is (confirmed by reading the source, not guessed):**

- `interview_theater/szene.py:255` — `PHASE_PROSA = 6`; `schreibt_prosa(conn, chat_id)` returns `phasen.aktuelle(conn, chat_id) <= PHASE_PROSA`. Phase 5 already satisfies `<= 6`, so `szene.starte()`/`szene.schreibe()` called during phase 5 **already** write into `szene.prosa` (not `volltext`) and **already** skip the `form` Pflichtfeld. No change needed to this constant or this function.
- `interview_theater/szene.py:855` `ziel_fuer` / `repo.stelle_szene_sicher` (repo.py:2421) — resolves a scene number to a row, **creating a bare row on demand** if none exists yet. Safe to call `szene.starte(conn, tg, klm, e, chat_id, f"SZENE {n}: ...")` for a scene number that has no row yet.
- `interview_theater/repo.py:2778` `hole_letzte_szene` — "last changed" scene (`ORDER BY geaendert_am DESC, id DESC LIMIT 1`). This is what an empty `szene_schreiben`/`szene_kuerzen` `wert` resolves to (via `ziel_fuer`) — in a sequential Stage B flow this naturally means "the scene currently being drafted", with no new code needed.
- `interview_theater/knoepfe/szenen.py:932` `_naechste_offene(conn, chat_id, nach)` — lowest-numbered scene with `nummer > nach` that is not `szenenfolge.ist_fertig(s)` (i.e. `fertig_am` not set). Reused directly by the new Stage B auto-advance.
- `interview_theater/repo.py:2478` `setze_szene_figuren(conn, chat_id, szene_id, figur_ids: list[int])` — replaces a scene's cast assignment (the `szene_figur` junction table). `szene.PFLICHTFELDER`'s `"figuren"` check reads this junction via `repo.szene_figuren`, **not** a text column (there is no `szene.figuren` text column).
- `interview_theater/vorschlagssperre.py` — shared lock between `schaerfung` and `szenenfolge`; **not** reused for the new flow (a dedicated lock avoids coupling an unrelated workflow to that lock's semantics, matching "Ein Sperren-Register je Nebenläufigkeit").
- `interview_theater/schaerfung.starte(conn, tg, klm, e, chat_id, nachbereitung=None)` — the `nachbereitung` callable already exists precisely to chain work after the automatic matching pass finishes, released from the shared lock. The new Stage A kickoff becomes this callback at the phase-5 entry call site.

**Deliberate scope decisions (document these in the final report, not just here):**

1. **Stage A "Yes, save" is button-only**, matching the task spec's own wording ("Buttons under the overview") and Stage A's explicit two-button design. Stage B's **confirmation** ("Yes, save" on a scene) is likewise button-only in this plan — there is no existing erkenner art that means "approve this draft as final" without stretching `festlegung_setzen` past its catch-all purpose, and the task spec itself only requires the **revision** direction ("No, change it again") to resolve via chat, which reuses `szene_schreiben`/`szene_kuerzen` exactly as instructed. This is a deliberate, narrower reading — call it out in the final report as a question for the phase 6/7 follow-up card.
2. **Per-scene cast defaults to the full character list** for every auto-created Stage B scene. The overview schema returns `szenen_was_passiert: array[string]` (flat, one entry per scene) but not a per-scene cast breakdown — adding a nested `figuren_je_szene: array[array[string]]` would break the "flat schema" convention this codebase follows everywhere (`global-constraints.md 'Schema'`, cited throughout `erkenner.py`/`schaerfung.py`). Defaulting every scene's cast to the full character list satisfies `szene.PFLICHTFELDER`'s `figuren` check and is editable per-scene afterwards via the existing web `Besetzung` field (`web_schreiben.FELDER`). Call this out as a known simplification.
3. **`ort` per scene defaults to `arbeitsstand.rahmen`** (the group's Setting) when the scene's own `ort` is empty — consistent with the already-documented principle "The setting is the default for place, time and occasion of every scene" (`sprachen/en/prompts/phasen/4.md`).
4. The new behaviour is **entirely gated behind `workshop.prosa_entwurf_aktiv()`**, set only in `workshop/padua-2026/profil.toml`. Any code path added by this plan that isn't itself gated by this flag must be a no-op for every other profile.
5. **"Chat changes the scene count during Stage A" reuses the existing `szenenanzahl_setzen` art unchanged** — it already writes `arbeitsstand.szenen_anzahl` in any phase (confirmed: no phase gating exists on it today, and none is being added). The *consequence* (re-running Stage A generation) is wired as a side effect inside `erkenner.laufe`, not as a change to `szenenanzahl_setzen` itself.

---

## Task 1: Rename Padua's phases 4–7 and add legacy keyword aliases

**Files:**
- Modify: `workshop/padua-2026/phasen.toml`

**Interfaces:**
- Consumes: nothing new.
- Produces: `workshop.phasenliste("padua-2026")` returns `name` = `"Frame"`/`"Prose Draft"`/`"Rewrite"`/`"Stage Version"` for phases 4–7; `phasen.nummer_fuer(...)` still resolves every old keyword (`"Sharpening"`, `"Scenes as Story"`, `"Polish"`) to the same phase number as before.

- [ ] **Step 1: Edit the four phase blocks**

Replace lines 31–54 of `workshop/padua-2026/phasen.toml` (phases 4–7) with:

```toml
[[phase]]
nummer = 4
name = "Frame"
satz = "Invent freely: where it is set, who is in it, what happens."
stichwoerter = ["setting", "characters", "character", "frame", "core theme",
                "format", "conflict", "story", "plot", "outline"]

[[phase]]
nummer = 5
name = "Prose Draft"
satz = "Sharpen the invented story against the interview material, then write it scene by scene."
# "sharpening"/"sharpen"/"clustering"/"summaries" bleiben als Alt-Stichwoerter
# stehen: der englische Erkenner-Prompt (Punkt 19) nennt die Phase noch so,
# und eine Gruppe, die den alten Namen kennt, soll weiter treffen.
stichwoerter = ["prose draft", "prose", "draft", "overview", "story overview",
                "sharpening", "sharpen", "clustering", "summaries"]

[[phase]]
nummer = 6
name = "Rewrite"
satz = "Tell each scene as prose -- what happens, still without a form."
stichwoerter = ["rewrite", "rewriting", "revise", "revision",
                "scene texts", "scene text", "scenes", "scene"]

[[phase]]
nummer = 7
name = "Stage Version"
satz = "Choose the form of each scene, translate the story into it, check the play."
stichwoerter = ["stage version", "staging", "final version",
                "run-through", "polish", "play check", "review round"]
```

Note: the `satz` fields are left byte-identical to today's — only `name` and
`stichwoerter` change. Phase 5's `satz` gets ONE clause appended ("then write
it scene by scene") because the two-stage flow genuinely adds new behaviour
this sentence should describe; phases 4/6/7 keep their sentences verbatim
since their behaviour in this card is unchanged.

- [ ] **Step 2: Check for keyword collisions across all seven phases**

Run:
```
python3.11 -c "
import sys; sys.path.insert(0, '.')
from interview_theater import workshop
p = workshop.lade('padua-2026')
stich = workshop.phasen_stichwoerter(p)
seen = {}
for nummer, woerter in stich.items():
    for w in woerter:
        if w in seen and seen[w] != nummer:
            print('COLLISION', w, seen[w], nummer)
        seen[w] = nummer
print('ok, no collisions' if True else '')
"
```
Expected: no `COLLISION` lines printed (the new words — `"prose draft"`,
`"prose"`, `"draft"`, `"overview"`, `"story overview"`, `"rewrite"`,
`"rewriting"`, `"revise"`, `"revision"`, `"stage version"`, `"staging"`,
`"final version"` — do not appear in any other phase's existing keyword list;
verified against the full `phasen.toml` content read during planning).

- [ ] **Step 3: Run the existing Padua profile tests (expect two known failures, fixed in Task 2)**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest tests/test_profile_geruest.py -q -p no:cacheprovider`
Expected: `test_padua_phasen_und_formen_englisch` and the five
`test_padua_stichwoerter_finden_die_phase[...]` cases for `Sharpening`,
`Scenes as Story`, `polish` still PASS (old names are still keywords); no
NEW failures beyond what Task 2 will add assertions for. (At this point the
suite should still be fully green, since nothing yet asserts the *new* names.)

- [ ] **Step 4: Commit**

```bash
git add workshop/padua-2026/phasen.toml
git commit -m "$(cat <<'EOF'
Rename Padua phases 4-7 to Frame / Prose Draft / Rewrite / Stage Version

Old names (Sharpening, Scenes as Story, Polish) stay as recognised
keywords so phasen.nummer_fuer keeps resolving them. Dortmund is untouched.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Update `tests/test_profile_geruest.py` for the new names

**Files:**
- Modify: `tests/test_profile_geruest.py:129-146`

**Interfaces:**
- Consumes: `workshop.phasenliste`, `phasen.nummer_fuer` (unchanged signatures).
- Produces: nothing new; this task only updates test expectations.

- [ ] **Step 1: Update `test_padua_phasen_und_formen_englisch`**

```python
def test_padua_phasen_und_formen_englisch():
    profil = workshop.lade("padua-2026")
    assert [n for _, n, _ in workshop.phasenliste(profil)] == [
        "Terms", "Questions", "Interviews", "Frame",
        "Prose Draft", "Rewrite", "Stage Version"]
    assert workshop.form_anzeige(profil) == ("Dialogue", "Monologue", "Chorus", "Song", "Rap")
    assert workshop.formen(profil) == ("dialog", "monolog", "chor", "lied", "rap")
```

- [ ] **Step 2: Extend the stichwort parametrize list to cover both old and new names**

```python
@pytest.mark.parametrize("wort,nummer", [
    # "/phase Characters" steht im englischen _TEXT_PHASE_UMSCHALTEN; die
    # uebrigen nennt der englische Erkenner-Prompt noch aus der alten
    # Phasenliste -- phasen.STICHWOERTER macht die Zuordnung (Review A1).
    ("Characters", 4), ("core theme", 4), ("format", 4), ("setting", 4),
    ("story", 4), ("Frame", 4), ("Terms", 1), ("interview questions", 2),
    ("interviews", 3),
    # Alte Namen bleiben gueltig (Padua Phasen TEIL 1, 03.10.2026):
    ("Sharpening", 5), ("Scenes as Story", 6), ("polish", 7),
    # Neue Namen (Padua Phasen TEIL 1, 03.10.2026):
    ("Prose Draft", 5), ("prose", 5), ("Rewrite", 6), ("Stage Version", 7),
])
def test_padua_stichwoerter_finden_die_phase(wort, nummer, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert phasen.nummer_fuer(wort) == nummer
```

- [ ] **Step 3: Run the test file**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest tests/test_profile_geruest.py -q -p no:cacheprovider`
Expected: all PASS, including the new parametrized cases.

- [ ] **Step 4: Run the full suite**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: `5928 passed` (or more, if new cases got added by this task — parametrize adds test IDs, so the passed count rises by the number of new cases), `4 skipped`, no failures.

- [ ] **Step 5: Commit**

```bash
git add tests/test_profile_geruest.py
git commit -m "$(cat <<'EOF'
test: pin Padua's new phase names and keep old names as valid keywords

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Update the English prompts for the new phase names

**Files:**
- Modify: `interview_theater/sprachen/en/prompts/system.md:13-19`
- Modify: `interview_theater/sprachen/en/prompts/erkenner.md:133-137`
- Modify: `interview_theater/sprachen/en/prompts/phasen/4.md:1`
- Modify: `interview_theater/sprachen/en/prompts/phasen/6.md:1`
- Modify: `interview_theater/sprachen/en/prompts/phasen/7.md:1`

**Interfaces:**
- Consumes: nothing new.
- Produces: no displayed phase name in any Padua-facing prompt still says "Sharpening", "Scenes as Story" or "Polish" as the phase's own name (old words may remain as recognised keywords in `phasen.toml`, not as the header/list label here).

- [ ] **Step 1: Update the station list in `system.md`**

Current (lines 10–19):
```
1. Terms -- take in and sort the list of terms collected in the plenary session
2. Questions -- develop interview questions from the terms
3. Interviews -- carry out interviews, summarise the material
4. Setting, Characters & Story -- freely invent WHERE it is set (place,
   time, occasion), WHO appears and WHAT happens: the arc, the ending and the
   scene sequence (with a suggested form for each scene)
5. Sharpening -- sharpen the invented story against the interview material
6. Scenes as Story -- tell each scene as prose, still without a form
7. Polish -- choose the form for each scene, translate the story, check
   the play
```

Replace with:
```
1. Terms -- take in and sort the list of terms collected in the plenary session
2. Questions -- develop interview questions from the terms
3. Interviews -- carry out interviews, summarise the material
4. Frame -- freely invent WHERE it is set (place, time, occasion), WHO
   appears and WHAT happens: the arc, the ending and the scene sequence
   (with a suggested form for each scene)
5. Prose Draft -- sharpen the invented story against the interview
   material, then write it scene by scene as prose
6. Rewrite -- tell each scene as prose, still without a form
7. Stage Version -- choose the form for each scene, translate the story,
   check the play
```

- [ ] **Step 2: Update the phase list inside `erkenner.md`'s `phase_setzen` documentation**

Current (lines 133–137):
```
19. phase_setzen           -- wert: the number of the working phase the
    group is at now, as a numeral ("4"). The seven phases are:
    1 Terms, 2 Questions, 3 Interviews, 4 Setting, Characters & Story,
    5 Sharpening, 6 Scenes as Story, 7 Polish. The group commands a move
    to a phase ("let's do characters now", "back to the interviews", "next
```

Replace the phase-list sentence with:
```
19. phase_setzen           -- wert: the number of the working phase the
    group is at now, as a numeral ("4"). The seven phases are:
    1 Terms, 2 Questions, 3 Interviews, 4 Frame, 5 Prose Draft, 6 Rewrite,
    7 Stage Version. The group commands a move to a phase ("let's do
    characters now", "back to the interviews", "next
```
(Keep the rest of that paragraph, starting at "phase?") unchanged.)

- [ ] **Step 3: Update the phase-prompt headers**

`interview_theater/sprachen/en/prompts/phasen/4.md:1`:
```
## Current phase: 4 · Frame
```

`interview_theater/sprachen/en/prompts/phasen/6.md:1`:
```
## Current phase: 6 · Rewrite
```

`interview_theater/sprachen/en/prompts/phasen/7.md:1`:
```
## Current phase: 7 · Stage Version
```

Leave `phasen/5.md`'s header for Task 9 (it needs new body content describing
the two-stage flow, not just a header rename — doing both at once avoids a
throwaway intermediate edit).

Leave the body text of `phasen/4.md`, `6.md`, `7.md` otherwise untouched —
their described behaviour (free invention in 4, one-shot story writing in 6,
judge-loop polish in 7) is explicitly out of scope for this card.

- [ ] **Step 4: Grep-verify no stray old names remain as *labels***

Run:
```
grep -rn "Setting, Characters & Story\|Scenes as Story\b" interview_theater/sprachen/en/ interview_theater/prompts/ 2>/dev/null
```
Expected: no output (the EN prompt layer no longer uses the old compound
names as a header or station-list label; "Sharpening"/"Polish" as bare words
may still appear in body prose of `phasen/5.md`/`6.md`/`7.md` describing the
*activity*, which is fine — that's not a phase-name label and Task 9 handles
`5.md`'s rewrite).

- [ ] **Step 5: Run the Padua-specific prompt tests**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest tests/test_profile_geruest.py tests/test_anweisungen.py -q -p no:cacheprovider`
Expected: all PASS, including `test_padua_systemprompt_ohne_deutsche_reste`
(loops over `"phasen/4"` and `"phasen/6"`, unaffected by this rename) and
`tests/test_anweisungen.py`'s phase-prompt structural checks (e.g. the "what
you don't start on your own" closing-sentence test, which this task doesn't
touch).

- [ ] **Step 6: Run the full suite**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: green, same count as Task 2's end state.

- [ ] **Step 7: Commit**

```bash
git add interview_theater/sprachen/en/prompts/system.md \
        interview_theater/sprachen/en/prompts/erkenner.md \
        interview_theater/sprachen/en/prompts/phasen/4.md \
        interview_theater/sprachen/en/prompts/phasen/6.md \
        interview_theater/sprachen/en/prompts/phasen/7.md
git commit -m "$(cat <<'EOF'
Update English prompts to the new Padua phase names

phasen/5.md keeps its old header for now -- Task 9 rewrites its body for
the two-stage Prose Draft flow and updates the header in the same change.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Confirm the prompt-audit snapshot files need no regeneration, and Dortmund stays byte-identical

**Files:** none modified — this task is verification-only, documented as a task because the original spec explicitly asked for it and the answer ("no regeneration needed") must be demonstrated, not assumed.

**Interfaces:**
- Consumes: `tests/test_profil_bitgleich.py`, `scripts/pruefe_profil.py`.
- Produces: a written confirmation (in the commit message / final report) that `docs/prompt-audit/schnappschuss-vor-profilumbau.txt` and `docs/prompt-audit/texte-vor-sprache-a1.txt` contain **no Padua-keyed entries at all** (both files fingerprint only the Dortmund/default code path — confirmed during planning: zero hits for `grep -i padua` in either file, and `tests/test_profil_bitgleich.py` only ever loads `DORTMUND = "dortmund-2026"` or no env var at all).

- [ ] **Step 1: Grep both snapshot files for any Padua reference**

Run:
```
grep -ic padua docs/prompt-audit/schnappschuss-vor-profilumbau.txt docs/prompt-audit/texte-vor-sprache-a1.txt
```
Expected: `0` for both files — confirming they cannot regress from a Padua-only
rename, because they don't encode Padua content.

- [ ] **Step 2: Run the byte-identical test suite**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest tests/test_profil_bitgleich.py -q -p no:cacheprovider`
Expected: all PASS (unaffected — these tests never load `padua-2026`).

- [ ] **Step 3: Run the Dortmund profile checker**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m scripts.pruefe_profil dortmund-2026`
Expected: exits 0, prints "in Ordnung" (or equivalent success message per the
script's own wording) — confirming Dortmund is unaffected by any change so far.

- [ ] **Step 4: Run the Padua profile checker (structural sanity, not byte-identity)**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m scripts.pruefe_profil padua-2026`
Expected: exits 0 — the rename didn't break placeholder resolution, form-count
wording, or phase/intro consistency checks.

- [ ] **Step 5: No commit needed for this task (verification only)**

If any step above fails unexpectedly, stop and treat it as a bug introduced
by Tasks 1–3 — fix there, don't patch around it here.

---

## Task 5: Phase-aware intent gating table in `erkenner.py`

**Files:**
- Modify: `interview_theater/erkenner.py` (near `ARTEN_IN_AUFNAHME`, and inside `wende_an`)
- Test: `tests/test_erkenner.py` (add a new test function near existing `wende_an`/`ARTEN_IN_AUFNAHME` tests — check the file for the existing test naming convention and match it, e.g. `test_wende_an_...`)

**Interfaces:**
- Consumes: `phasen.aktuelle(conn, chat_id) -> int` (existing).
- Produces: `erkenner.PHASEN_SPEZIFISCHE_ARTEN: dict[str, tuple[int, ...]]` — a
  declarative table mapping an `art` string to the phase numbers in which it
  is honoured. An `art` absent from this dict is honoured in every phase
  (today's behaviour, unchanged for all 23 existing arts). Consumed by a new
  guard `erkenner._ist_phasenpassend(conn, chat_id, art) -> bool`, which
  `wende_an` calls before dispatching each change.

- [ ] **Step 1: Add the table and the guard function**

Insert directly after the `ARTEN_IN_AUFNAHME` tuple (after line 182) in
`interview_theater/erkenner.py`:

```python
#: Welche Phase eine ART tatsaechlich wirken laesst -- als Tabelle, nicht als
#: verstreute if/elif-Kette (Padua Phasen TEIL 1, 03.10.2026). Eine ART, die
#: hier NICHT auftaucht, gilt wie bisher in jeder Phase (alle 23 arts, die es
#: vor diesem Umbau schon gab, bleiben unveraendert phasenfrei). Dieser Platz
#: ist fuer kuenftige Karten gedacht -- z. B. eine Phase-7-spezifische
#: Revisions-art aus dem Flow-Audit (``git show feat/flow-audit:docs/
#: flow-audit/vorlagen.md``) wuerde hier einen weiteren Eintrag bekommen,
#: nicht einen weiteren Codepfad.
PHASEN_SPEZIFISCHE_ARTEN: dict[str, tuple[int, ...]] = {
    # Padua Phasen TEIL 1: die Uebersicht in Stufe A von Phase 5 (Prose
    # Draft) darf nur dort geaendert werden -- ausserhalb der Phase, oder
    # nachdem sie fixiert ist, ist ein "aendere die Uebersicht" etwas
    # anderes gemeint (siehe entwurf.py).
    "uebersicht_aendern": (5,),
}


def _ist_phasenpassend(conn, chat_id: int, art: str) -> bool:
    """True, wenn diese art in der aktuellen Phase ueberhaupt wirken darf.

    Reine Tabellen-Abfrage (``PHASEN_SPEZIFISCHE_ARTEN``), kein
    Modellaufruf, kein eigenes SQL -- wie jede andere Wache in diesem Modul
    (``waechter_filter``). Eine art, die nicht in der Tabelle steht, ist
    ueberall erlaubt: das ist der unveraenderte Normalfall."""
    phasen_liste = PHASEN_SPEZIFISCHE_ARTEN.get(art)
    if phasen_liste is None:
        return True
    return phasen.aktuelle(conn, chat_id) in phasen_liste
```

- [ ] **Step 2: Wire the guard into `wende_an`**

In `wende_an` (around line 1527, right before the `for aenderung in
aenderungen:` loop), filter out phase-mismatched changes **before** the loop
so they're silently dropped (same spirit as `waechter_filter`, which already
runs earlier in the pipeline via `_ohne_figur_festlegung_neben_figur_setzen`/
`_ohne_interview_starten_neben_ruecksprung`):

```python
    aenderungen = _ohne_figur_festlegung_neben_figur_setzen(
        _ohne_interview_starten_neben_ruecksprung(aenderungen)
    )
    aenderungen = [
        a for a in aenderungen
        if _ist_phasenpassend(conn, chat_id, a.get("art"))
    ]
    wirkliche = []
```

- [ ] **Step 3: Write a unit test proving the gate works and doesn't break generic arts**

Add to `tests/test_erkenner.py` (match the file's existing fixture style —
check how other `wende_an` tests build a `conn`/`chat_id`/arbeitsstand
fixture, e.g. `_conn()`/`repo.initialisiere` or an existing `db_conn`
fixture, and reuse that pattern instead of inventing a new one):

```python
def test_phasenspezifische_art_wirkt_nur_in_ihrer_phase(db_conn):
    chat_id = 1
    repo.sichere_gruppe(db_conn, chat_id, "testbot")
    phasen.setze(db_conn, chat_id, 4, "befehl")  # nicht Phase 5
    aenderungen = [{"art": "uebersicht_aendern", "wert": "make it sadder"}]
    e = type("E", (), {"bot_name": "testbot"})()
    ergebnis = erkenner.wende_an(db_conn, e, chat_id, aenderungen)
    assert ergebnis == []  # ausserhalb Phase 5: kein Effekt, kein Fehler


def test_phasenspezifische_art_wirkt_in_ihrer_phase(db_conn, monkeypatch):
    chat_id = 1
    repo.sichere_gruppe(db_conn, chat_id, "testbot")
    phasen.setze(db_conn, chat_id, 5, "befehl")
    # uebersicht_aendern hat (noch) keinen Schreibpfad in _wende_eine_an --
    # dieser Test haelt nur die Phasen-Durchlaessigkeit fest, nicht die
    # Wirkung selbst (die kommt mit Task 10's erkenner.laufe-Anbindung).
    monkeypatch.setattr(
        erkenner, "_wende_eine_an",
        lambda conn, cid, art, wert: {"art": art, "wert": wert}
        if art == "uebersicht_aendern" else None,
    )
    aenderungen = [{"art": "uebersicht_aendern", "wert": "make it sadder"}]
    e = type("E", (), {"bot_name": "testbot"})()
    ergebnis = erkenner.wende_an(db_conn, e, chat_id, aenderungen)
    assert ergebnis == [{"art": "uebersicht_aendern", "wert": "make it sadder"}]


def test_generische_art_wirkt_in_jeder_phase(db_conn):
    """festlegung_setzen steht nicht in PHASEN_SPEZIFISCHE_ARTEN und bleibt
    unveraendert phasenfrei (Padua Phasen TEIL 1, Vorgabe aus dem Auftrag)."""
    chat_id = 1
    repo.sichere_gruppe(db_conn, chat_id, "testbot")
    phasen.setze(db_conn, chat_id, 1, "befehl")
    aenderungen = [{"art": "festlegung_setzen", "wert": "MUSIC: everyone hums"}]
    e = type("E", (), {"bot_name": "testbot"})()
    ergebnis = erkenner.wende_an(db_conn, e, chat_id, aenderungen)
    assert len(ergebnis) == 1
    assert ergebnis[0]["art"] == "festlegung_setzen"
```

Before writing these, **open `tests/test_erkenner.py` and check**: (a) the
exact fixture name for a DB connection (`db_conn` is a guess — match
whatever the file actually uses, likely a `conn`-returning pytest fixture
already defined via `conftest.py`), (b) whether `repo.sichere_gruppe` is the
right setup call or whether existing tests use something simpler (e.g.
direct `INSERT` or a `gruppe_fixture`), and (c) how existing tests construct
the `e` (Einstellungen) stand-in. Match the established pattern exactly —
don't introduce a second fixture style in the same file.

- [ ] **Step 4: Run the new tests**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest tests/test_erkenner.py -q -p no:cacheprovider -k phasenspezifisch or generische_art`
Expected: 3 new tests PASS.

- [ ] **Step 5: Run the full suite**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add interview_theater/erkenner.py tests/test_erkenner.py
git commit -m "$(cat <<'EOF'
erkenner: phase-aware intent gating as a data table, not scattered ifs

PHASEN_SPEZIFISCHE_ARTEN maps an art to the phases it fires in; absence
means "every phase", preserving all 23 existing arts unchanged. Extensible
for the phase 6/7 follow-up card without touching control flow again.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: DB schema additions for the overview and per-scene draft confirmation

**Files:**
- Modify: `interview_theater/db.py` (the `arbeitsstand` and `szene` `CREATE TABLE` blocks inside `SCHEMA`)
- Modify: `interview_theater/repo.py` (`_ARBEITSSTAND_FELDER`, `SZENENFELDER` — check whether `entwurf_bestaetigt_am` belongs in a *separate* whitelist since it's a timestamp set by a dedicated function, not free text via `setze_szenenfeld`)
- Test: `tests/test_db.py` (add a migration/column-presence test — check existing patterns for other additive columns like `szenen_anzahl`)

**Interfaces:**
- Consumes: `db._migriere_fehlende_spalten` (existing, parses `SCHEMA` text automatically — no new migration function needed).
- Produces: `arbeitsstand.geschichte_uebersicht TEXT`, `arbeitsstand.geschichte_uebersicht_fixiert_am TEXT`, `szene.entwurf_bestaetigt_am TEXT`. New function `repo.setze_szene_entwurf_bestaetigt(conn, szene_id, wann=None) -> None`.

- [ ] **Step 1: Add the two `arbeitsstand` columns**

In `interview_theater/db.py`, inside the `arbeitsstand` `CREATE TABLE`
block, immediately after the `szenen_anzahl` column (after line 421, before
the `interviews_fertig_wunsch_seit` comment), add:

```sql
  -- Die Uebersicht aus Stufe A des zweistufigen Phase-5-Entwurfs (Padua
  -- Phasen TEIL 1, 03.10.2026, interview_theater/entwurf.py): Logline,
  -- Setting, Figuren, Spannungsbogen und je Szene ein Satz, als fertig
  -- zusammengesetzter Anzeigetext (~1200-1500 Zeichen). Wird bei jeder
  -- Neugenerierung ueberschrieben, solange sie nicht fixiert ist -- wie
  -- figuren_entwurf vor figuren_fixiert_am. Nur aktiv, wenn das
  -- Workshop-Profil [prosa_entwurf] aktiv = true setzt (workshop.py);
  -- Dortmund liest diese Spalte nie.
  geschichte_uebersicht           TEXT,
  -- Die Szenensaetze aus derselben Uebersicht, EINZELN (newline-getrennt,
  -- eine Zeile je Szene, in Szenenreihenfolge) -- getrennt von der
  -- zusammengesetzten Anzeige oben, weil Stufe B sie EINZELN braucht, um
  -- was_passiert je Szene zu befuellen (entwurf.uebernimm_szenenfelder).
  -- Reparsen der Anzeige waere fragil; dieses Feld ist die strukturierte
  -- Quelle dafuer.
  geschichte_uebersicht_szenen    TEXT,
  -- Wann die Gruppe die Uebersicht mit "Yes, save" abgenommen hat --
  -- derselbe Zeitstempel-Charakter wie figuren_fixiert_am. Erst danach
  -- beginnt Stufe B (Szene fuer Szene).
  geschichte_uebersicht_fixiert_am TEXT,
```

- [ ] **Step 2: Add the `szene.entwurf_bestaetigt_am` column**

In the `szene` `CREATE TABLE` block, immediately after `fertig_am` (after
line 542, before the `fruehere_fassungen` comment), add:

```sql
  -- Gesetzt = die Gruppe hat den PROSA-ENTWURF dieser Szene in Stufe B von
  -- Phase 5 (Prose Draft) mit "Yes, save" abgenommen (Padua Phasen TEIL 1,
  -- 03.10.2026, entwurf.py). Bewusst eine EIGENE Spalte und nicht
  -- fertig_am: fertig_am meint die Abnahme des THEATERTEXTS in Phase 7
  -- ("Passt"-Knopf unter einem geschriebenen Szenentext) -- zwei
  -- verschiedene Abnahmen in zwei verschiedenen Phasen, zwei Spalten.
  entwurf_bestaetigt_am TEXT,
```

- [ ] **Step 3: Whitelist the new arbeitsstand fields in `repo.py`**

In `interview_theater/repo.py`, append to `_ARBEITSSTAND_FELDER` (after
`"interviews_fertig_wunsch_seit"`, before the closing `)`  on line 1742):

```python
    # Die Uebersicht aus Stufe A des Phase-5-Entwurfs (Padua Phasen TEIL 1):
    # derselbe eine Schreibweg wie alles andere im Arbeitsstand.
    "geschichte_uebersicht", "geschichte_uebersicht_szenen",
    "geschichte_uebersicht_fixiert_am",
```

- [ ] **Step 4: Add a dedicated setter for the scene-level timestamp**

`repo.setze_szenenfeld` cannot be reused as-is for `entwurf_bestaetigt_am`:
its whitelist (`SZENENFELDER`) is for group-decided content fields and does
not stamp a timestamp automatically the way `fertig_am` handling elsewhere
does. Add a new function right after `szene_figuren` (after line 2513) in
`interview_theater/repo.py`:

```python
@_gesperrt
def setze_szene_entwurf_bestaetigt(
    conn: sqlite3.Connection, szene_id: int, wann: str | None = None
) -> None:
    """Markiert den Prosa-Entwurf einer Szene als abgenommen (Stufe B,
    Phase 5 Prose Draft, Padua Phasen TEIL 1) -- dieselbe Bauart wie
    ``merke_schaerfung_uebernommen``: ein Zeitstempel, kein Textfeld, also
    kein Platz in ``SZENENFELDER``."""
    conn.execute(
        "UPDATE szene SET entwurf_bestaetigt_am = ?, geaendert_am = ? WHERE id = ?",
        (wann or _jetzt_genau(), _jetzt_genau(), szene_id),
    )
    conn.commit()
```

Check the exact name of the "now" helper used elsewhere in this file for a
precise timestamp (`_jetzt_genau` was seen in `stelle_szene_sicher`/
`setze_szene_figuren` — confirm it exists and matches; if the file uses
`_jetzt()` for second-precision and `_jetzt_genau()` for sub-second, use
`_jetzt_genau()` to match the `szene` table's existing precision in
`geaendert_am`).

- [ ] **Step 5: Write a migration test**

Add to `tests/test_db.py` (match the file's existing fixture/style for a
fresh in-memory or temp-file DB):

```python
def test_geschichte_uebersicht_und_entwurf_bestaetigt_spalten_existieren(tmp_path):
    pfad = tmp_path / "test.db"
    conn = db.verbinde(str(pfad))
    db.initialisiere(conn)
    arbeitsstand_spalten = {z[1] for z in conn.execute("PRAGMA table_info(arbeitsstand)")}
    szene_spalten = {z[1] for z in conn.execute("PRAGMA table_info(szene)")}
    assert "geschichte_uebersicht" in arbeitsstand_spalten
    assert "geschichte_uebersicht_szenen" in arbeitsstand_spalten
    assert "geschichte_uebersicht_fixiert_am" in arbeitsstand_spalten
    assert "entwurf_bestaetigt_am" in szene_spalten
```

(Check `tests/test_db.py` for the actual `db.verbinde`/`db.initialisiere`
call convention used by neighbouring tests — e.g. whether a connection
fixture already exists — and match it instead of duplicating setup.)

- [ ] **Step 6: Run the new test and the full suite**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest tests/test_db.py -q -p no:cacheprovider`
Expected: PASS.

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: green. Also re-run `python -m scripts.pruefe_profil dortmund-2026`
to confirm the additive schema change didn't disturb Dortmund.

- [ ] **Step 7: Commit**

```bash
git add interview_theater/db.py interview_theater/repo.py tests/test_db.py
git commit -m "$(cat <<'EOF'
db: additive columns for the Phase 5 story overview and per-scene drafts

arbeitsstand.geschichte_uebersicht(_szenen)(_fixiert_am) and
szene.entwurf_bestaetigt_am -- all additive via _migriere_fehlende_spalten,
unused outside the Padua profile.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Profile switch `[prosa_entwurf] aktiv` and its `workshop.py` accessor

**Files:**
- Modify: `interview_theater/workshop.py` (add accessor + default, following the exact pattern of `[laengen] aktiv`/`laengen_aktiv()`)
- Modify: `workshop/padua-2026/profil.toml` (add `[prosa_entwurf]` table)
- Test: `tests/test_workshop.py` (or wherever `laengen_aktiv`/`sprachpass_aktiv` are tested — match that file)

**Interfaces:**
- Consumes: nothing new.
- Produces: `workshop.prosa_entwurf_aktiv(profil=None) -> bool`, `False` for
  the built-in default profile and for Dortmund, `True` for Padua.

- [ ] **Step 1: Find the exact `[laengen] aktiv` accessor pattern to copy**

Run: `grep -n "laengen_aktiv\|def laengen\|\[laengen\]" interview_theater/workshop.py`

Read the matched function in full before writing the new one — match its
exact style (likely something like `def laengen_aktiv(profil=None) -> bool:
return bool(wert(profil, "laengen.aktiv", False))` or similar, using
whatever internal `wert()`/`_tabelle()` helper the module already has for
reading a nested TOML key with a default). Do not invent a different
lookup mechanism.

- [ ] **Step 2: Add `prosa_entwurf_aktiv` right next to it**

Using the exact same helper call pattern discovered in Step 1, add (near
the `laengen_aktiv`/`sprachpass_aktiv` functions, to keep related toggles
together):

```python
def prosa_entwurf_aktiv(profil=None) -> bool:
    """Ob Phase 5 (Prose Draft) die zweistufige Uebersicht-dann-Szenen-
    Erzeugung faehrt (Padua Phasen TEIL 1, 03.10.2026, entwurf.py).

    Vorgabe false -- wie [laengen] aktiv: ohne diese Zeile im Profil bleibt
    Phase 5 genau das, was sie vorher war (die automatische Schaerfung,
    sonst nichts). Dortmund setzt die Zeile nicht und bleibt unberuehrt."""
    return bool(wert(profil, "prosa_entwurf.aktiv", False))
```

(Replace `wert(...)` with whatever the actual helper from Step 1 is called
if the name differs.)

- [ ] **Step 3: Add the TOML table to Padua's profile**

Append to `workshop/padua-2026/profil.toml` (after the `[web]` table at the
end of the file):

```toml
# Die zweistufige Phase 5 (Padua Phasen TEIL 1, 03.10.2026): erst eine
# Uebersicht abnehmen, dann Szene fuer Szene Prosa schreiben, am Ende
# automatisch weiter zu Phase 6. Ohne diese Zeile bliebe Phase 5 bei der
# automatischen Schaerfung allein -- wie vor diesem Umbau.
[prosa_entwurf]
aktiv = true
```

- [ ] **Step 4: Write tests for both profiles**

Add (matching whatever test file already covers `laengen_aktiv`):

```python
def test_prosa_entwurf_aktiv_nur_in_padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert workshop.prosa_entwurf_aktiv(workshop.lade("padua-2026")) is True
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    workshop.vergiss()
    assert workshop.prosa_entwurf_aktiv(workshop.lade("dortmund-2026")) is False
    assert workshop.prosa_entwurf_aktiv(None) is False  # eingebautes Vorgabeprofil
```

- [ ] **Step 5: Run the new test, the profile checkers, and the full suite**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -k prosa_entwurf -q -p no:cacheprovider`
Expected: PASS.

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m scripts.pruefe_profil --alle`
Expected: exits 0 for every profile (the new TOML table must not trip any
"unexpected key" validation — if `pruefe_profil.py` has an allow-list of
known top-level tables, check it and add `prosa_entwurf` there too).

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add interview_theater/workshop.py workshop/padua-2026/profil.toml tests/test_workshop.py
git commit -m "$(cat <<'EOF'
workshop: add [prosa_entwurf] aktiv switch, on only for Padua

Same pattern as [laengen] aktiv -- gates the new two-stage Phase 5 flow
so Dortmund's runtime behaviour, not just its prompt bytes, stays
unaffected by this card.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: New erkenner art `uebersicht_aendern` + corpus cases (DE + EN)

**Files:**
- Modify: `interview_theater/erkenner.py` (`ARTEN` tuple)
- Modify: `interview_theater/prompts/erkenner.md` (new numbered point, German)
- Modify: `interview_theater/sprachen/en/prompts/erkenner.md` (new numbered point, English)
- Modify: `korpus/erkenner.jsonl` (≥2 positive cases + ≥1 negative/boundary case documented in `notiz`)
- Modify: `korpus/en/erkenner.jsonl` (same, English)

**Interfaces:**
- Consumes: `erkenner.PHASEN_SPEZIFISCHE_ARTEN` (Task 5, already wired).
- Produces: `"uebersicht_aendern"` is a recognised `art` in `erkenner.ARTEN`,
  documented in both prompt languages, with corpus coverage in both corpora.
  `wert` = free-text direction for the regeneration, or `""` if the group
  just says "change it"/"try again" with no specific direction.

- [ ] **Step 1: Add the art to `ARTEN`**

In `interview_theater/erkenner.py`, append to the `ARTEN` tuple (after
`"szenenanzahl_setzen"`, before the closing `)` on line 161):

```python
    # Padua Phasen TEIL 1 (03.10.2026): Rueckmeldung zur generierten
    # Geschichts-Uebersicht in Stufe A von Phase 5 (Prose Draft,
    # entwurf.py) -- "mach das Ende trauriger", "nochmal, anders", "die
    # Spannungskurve ist mir zu flach". Gilt NUR in Phase 5
    # (PHASEN_SPEZIFISCHE_ARTEN) und nur, solange die Uebersicht noch nicht
    # fixiert ist -- das prueft entwurf.py selbst, nicht der Erkenner.
    # wert: die gewuenschte Richtung, oder leer ("") bei einem reinen
    # "nochmal"/"anders" ohne eigene Angabe.
    "uebersicht_aendern",
)
```

- [ ] **Step 2: Document it in the German prompt**

In `interview_theater/prompts/erkenner.md`, find the numbered list entry
for `szenenanzahl_setzen` (grep `grep -n "szenenanzahl_setzen" interview_theater/prompts/erkenner.md`)
and add a new point directly after it, matching that file's exact numbering
and formatting style (read the two surrounding points first to match
German wording conventions used elsewhere in that file):

```
25. uebersicht_aendern     -- wert: die gewuenschte Richtung als Text, oder
    leer (""), wenn die Gruppe nur "nochmal"/"anders" sagt. Gilt
    AUSSCHLIESSLICH, wenn im Verlauf direkt davor eine generierte
    Geschichts-Uebersicht steht (Logline, Setting, Figuren, Spannungsbogen,
    Szenen) und die Gruppe Rueckmeldung dazu gibt, OHNE "Ja, speichern" zu
    sagen oder zu druecken: "mach das Ende trauriger", "die Spannungskurve
    ist mir zu flach", "nochmal, anders". Ein einfaches "Ja" oder "passt"
    zu dieser Uebersicht ist KEIN uebersicht_aendern -- das laeuft nur ueber
    den Knopf "Yes, save". Eine Aenderung an Setting, Figuren oder
    Geschichte selbst bleibt rahmen_setzen/figur_setzen/geschichte_setzen;
    uebersicht_aendern ist nur fuer Rueckmeldung, die zu keinem bestehenden
    Feld passt (Tonfall, Tempo, Spannungskurve der Uebersicht selbst).
```

- [ ] **Step 3: Document it in the English prompt**

In `interview_theater/sprachen/en/prompts/erkenner.md`, add the matching
English point directly after point 24 (`szenenanzahl_setzen`):

```
25. uebersicht_aendern     -- wert: the wanted direction as text, or empty
    ("") if the group just says "again"/"different". Applies ONLY when a
    generated story overview (Logline, Setting, Characters, Tension arc,
    Scenes) is directly in the lead-up and the group gives feedback on it
    WITHOUT saying or pressing "Yes, save": "make the ending sadder", "the
    tension arc feels too flat", "try again, differently". A plain "yes"
    or "looks good" to this overview is NOT uebersicht_aendern -- that
    only goes through the "Yes, save" button. A change to the setting,
    characters or story itself stays rahmen_setzen/figur_setzen/
    geschichte_setzen; uebersicht_aendern is only for feedback that fits no
    existing field (tone, pace, the tension arc of the overview itself).
```

- [ ] **Step 4: Add German corpus cases**

Append to `korpus/erkenner.jsonl` (match the exact JSON schema confirmed
during planning: `id`, `arbeitsstand`, `nachrichten`, `erwartet`, `notiz`,
optional `zustimmung`):

```json
{"id": "ue01-uebersicht-ende-trauriger", "arbeitsstand": {"geschichte_uebersicht": "Logline: Zwei Schwestern treffen sich nach Jahren wieder.\nSetting: Ein Bahnhofscafe, spaet abends.\nFiguren:\n- Mira: die Aeltere, will Naehe, traut sich nicht zu fragen\n- Nora: die Juengere, will Distanz, ist laengst woanders angekommen\nSpannungsbogen: Beide wollen etwas Verschiedenes von diesem Treffen, und keine sagt es offen.\nSzenen:\n1. Mira wartet, Nora kommt spaet, erste Floskeln.\n2. Ein altes Foto bringt den eigentlichen Streit hoch.\n3. Nora will gehen, Mira haelt sie mit einem Gestaendnis.", "figuren": [{"name": "Mira", "beschreibung": ""}, {"name": "Nora", "beschreibung": ""}]}, "nachrichten": [{"absender": "Sara", "text": "das mit dem Gestaendnis am Ende ist mir zu versoehnlich"}, {"absender": "Sara", "text": "mach das Ende trauriger, die beiden sollen sich nicht wirklich finden"}], "erwartet": [{"art": "uebersicht_aendern", "wert": "Ende trauriger, die beiden finden nicht wirklich zueinander"}], "notiz": "Padua Phasen TEIL 1 (03.10.2026): Rueckmeldung zur generierten Uebersicht, die zu keinem bestehenden Feld passt (Tonfall des Endes), waehrend die Uebersicht noch nicht fixiert ist."}
{"id": "ue02-uebersicht-nochmal-ohne-richtung", "arbeitsstand": {"geschichte_uebersicht": "Logline: Ein Umzug trennt zwei Freunde.\nSetting: Ein Hausflur, Umzugskartons.\nFiguren:\n- Alex: zieht weg, fuehlt sich schuldig\n- Jo: bleibt, fuehlt sich verlassen\nSpannungsbogen: Keiner sagt, was er wirklich fuehlt, bis die Kartons weg sind.\nSzenen:\n1. Packen, Smalltalk ueber das Wetter.\n2. Ein Streit ueber eine Kleinigkeit, eigentlich ueber den Abschied.\n3. Der letzte Karton, ein ehrliches Wort."}, "nachrichten": [{"absender": "Jo", "text": "irgendwie trifft das noch nicht, was wir meinten"}, {"absender": "Jo", "text": "koenntest du das nochmal anders versuchen?"}], "erwartet": [{"art": "uebersicht_aendern", "wert": ""}], "notiz": "Padua Phasen TEIL 1 (03.10.2026): reines \"nochmal, anders\" ohne eigene Richtung -- wert bleibt leer, es wird nichts geraten."}
{"id": "n55-uebersicht-ja-ist-kein-aendern", "arbeitsstand": {"geschichte_uebersicht": "Logline: Ein Umzug trennt zwei Freunde.\nSetting: Ein Hausflur, Umzugskartons."}, "nachrichten": [{"absender": "Jo", "text": "ja, das passt genau so"}], "erwartet": [], "notiz": "Padua Phasen TEIL 1 (03.10.2026): Zustimmung zur Uebersicht laeuft ausschliesslich ueber den Knopf \"Yes, save\", nicht ueber uebersicht_aendern -- ein blosses Ja darf keinen neuen Lauf ausloesen.", "zustimmung": true}
```

- [ ] **Step 5: Add English corpus cases**

Append matching cases (same three ids with an `en` convention if the
English corpus uses a different id prefix — check
`korpus/en/erkenner.jsonl`'s existing id style first and match it, e.g. the
file may prefix English cases differently) to `korpus/en/erkenner.jsonl`:

```json
{"id": "ue01-overview-ending-sadder", "arbeitsstand": {"geschichte_uebersicht": "Logline: Two sisters meet again after years apart.\nSetting: A station cafe, late evening.\nCharacters:\n- Mira: the older one, wants closeness, doesn't dare ask\n- Nora: the younger one, wants distance, has long since moved on\nTension arc: both want something different from this meeting, and neither says so openly.\nScenes:\n1. Mira waits, Nora arrives late, first small talk.\n2. An old photo brings up the real argument.\n3. Nora wants to leave, Mira holds her back with a confession.", "figuren": [{"name": "Mira", "beschreibung": ""}, {"name": "Nora", "beschreibung": ""}]}, "nachrichten": [{"absender": "Member 1", "text": "the confession at the end feels too neat"}, {"absender": "Member 1", "text": "make the ending sadder, they shouldn't really find each other"}], "erwartet": [{"art": "uebersicht_aendern", "wert": "ending sadder, they don't really find each other"}], "notiz": "Padua Phasen TEIL 1 (03.10.2026): feedback on the generated overview that fits no existing field, overview not yet fixed."}
{"id": "ue02-overview-try-again-no-direction", "arbeitsstand": {"geschichte_uebersicht": "Logline: A move apart separates two friends.\nSetting: A hallway, moving boxes."}, "nachrichten": [{"absender": "Member 2", "text": "this doesn't quite hit what we meant"}, {"absender": "Member 2", "text": "could you try that again, differently?"}], "erwartet": [{"art": "uebersicht_aendern", "wert": ""}], "notiz": "Padua Phasen TEIL 1 (03.10.2026): plain \"try again\" with no direction -- wert stays empty, nothing guessed."}
{"id": "n55-overview-yes-is-not-aendern", "arbeitsstand": {"geschichte_uebersicht": "Logline: A move apart separates two friends."}, "nachrichten": [{"absender": "Member 2", "text": "yes, that's exactly it"}], "erwartet": [], "notiz": "Padua Phasen TEIL 1 (03.10.2026): agreement to the overview only goes through the \"Yes, save\" button, never uebersicht_aendern.", "zustimmung": true}
```

- [ ] **Step 6: Run the corpus structure tests**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest tests/test_korpus.py -q -p no:cacheprovider`
Expected: PASS, including
`test_erkenner_jede_art_mindestens_zweimal` (now satisfied for
`uebersicht_aendern` with 2 positive cases) and `test_jeder_fall_hat_id_und_notiz`.

- [ ] **Step 7: Run the full suite**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: green.

- [ ] **Step 8: Commit**

```bash
git add interview_theater/erkenner.py interview_theater/prompts/erkenner.md \
        interview_theater/sprachen/en/prompts/erkenner.md \
        korpus/erkenner.jsonl korpus/en/erkenner.jsonl
git commit -m "$(cat <<'EOF'
erkenner: new art uebersicht_aendern for Phase 5 overview feedback

Phase-gated to 5 via PHASEN_SPEZIFISCHE_ARTEN (Task 5). Corpus cases added
in both languages; a real scripts.pruefe_prompts run is Task 15.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `interview_theater/entwurf.py` — Stage A overview generation

**Files:**
- Create: `interview_theater/entwurf.py`
- Create: `interview_theater/prompts/entwurf.md`
- Create: `interview_theater/sprachen/en/prompts/entwurf.md`
- Modify: `interview_theater/sprachen/en/prompts/phasen/5.md` (header + body rewrite for the two-stage flow — see Step 5)
- Modify: `interview_theater/prompts/phasen/5.md` (German counterpart — check if Padua even reaches this file; since Dortmund never sets `prosa_entwurf.aktiv`, its `5.md` body describing the old schärfung-only flow stays accurate for Dortmund and should **not** be rewritten to describe Padua-only behaviour. Add a short paragraph instead, guarded conceptually by "wenn eure Uebersicht erscheint" wording that is harmless to read even when the feature is inactive — OR, simpler and safer: leave the German base `phasen/5.md` completely untouched, since the base prompt is shared and Dortmund must stay byte-identical; Padua already overrides this file via its own English translation in `sprachen/en/`. **Do not touch** `interview_theater/prompts/phasen/5.md` at all in this task — only the English translation needs the new body.)
- Test: `tests/test_entwurf.py` (new file)

**Interfaces:**
- Consumes: `modellwahl.aufruf_schema`, `szene_claude.ist_aktiv`, `repo.hole_arbeitsstand`, `repo.setze_arbeitsstand`, `repo.figuren`, `repo.hole_szenen`, `repo.stelle_szene_sicher`, `repo.setze_szenenfeld`, `repo.setze_szene_figuren`, `anweisungen.hole`/`anweisungen.fuelle` (check which one `schaerfung.prompt()` uses — it calls `anweisungen.hole("schaerfung")`; match that exact call shape for `entwurf.prompt()`).
- Produces: `entwurf.SCHEMA_UEBERSICHT`, `entwurf.baue_nutzertext_uebersicht(conn, chat_id, notiz=None) -> str`, `entwurf.baue_anzeige(ergebnis: dict) -> str`, `entwurf.generiere_uebersicht(klm, conn, e, chat_id, notiz=None) -> dict`, `entwurf.starte_uebersicht(conn, tg, klm, e, chat_id, notiz=None) -> threading.Thread | None`, `entwurf.ART_UEBERSICHT = "entwurf_uebersicht"` (the `aufruf.art` string for cost tracking — distinct from the erkenner art name `uebersicht_aendern`).

- [ ] **Step 1: Write the module docstring and imports**

```python
"""Phase 5 (Prose Draft), zweistufig: erst eine Geschichts-Uebersicht
abnehmen, dann Szene fuer Szene Prosa schreiben (Padua Phasen TEIL 1,
03.10.2026).

**Nur aktiv mit** ``workshop.prosa_entwurf_aktiv()`` (Dortmund und das
eingebaute Vorgabeprofil lassen das Feld unangetastet -- Phase 5 bleibt dort
die automatische Schaerfung allein, wie vor diesem Umbau).

**Stufe A -- Uebersicht.** Nach der automatischen Schaerfung
(``schaerfung.mappe``, unveraendert) laeuft EIN Schema-Aufruf, der aus
Setting, Figuren, Geschichte und der Szenenanzahl eine strukturierte
Uebersicht baut: Logline, Setting, Figuren (je eine Zeile), Spannungsbogen,
und je Szene ein bis zwei Saetze. Flach wie ueberall
(global-constraints.md 'Schema'): ``szenen_was_passiert`` ist eine Liste von
Strings, eine je Szene -- keine verschachtelte Struktur. Die Gruppe sieht die
zusammengesetzte Anzeige (``baue_anzeige``) mit zwei Knoepfen, "Yes, save"
und "No, change it again"; Freitext-Rueckmeldung laeuft ueber die
Erkenner-art ``uebersicht_aendern`` (phasengebunden, siehe erkenner.py).

**Stufe B -- Szene fuer Szene.** Sobald die Uebersicht fixiert ist
(``geschichte_uebersicht_fixiert_am``), bekommt jede Szene ihre Pflichtfelder
aus der Uebersicht (``was_passiert`` aus ``szenen_was_passiert[i]``, ``ort``
aus ``arbeitsstand.rahmen`` als Vorgabe, die volle Besetzung als Vorgabe-Cast)
und wird ueber das BESTEHENDE ``szene.starte()`` geschrieben -- das schreibt
bei Phase <= ``szene.PHASE_PROSA`` (6) ohnehin schon in ``szene.prosa`` statt
``volltext`` und verlangt dort kein ``form``. Jede Szene bekommt dabei
GARANTIERT den vollen Text jeder vorigen Szene (nicht nur eine
Zusammenfassung) -- das ist bereits ``szene.py``s Normalfall
(``_continuity_bloecke``, voller Wortlaut, solange das Tokenbudget reicht);
dieses Modul erzwingt keine zusaetzliche Kuerzung.

Ist eine Szene abgenommen (Knopf "Yes, save",
``repo.setze_szene_entwurf_bestaetigt``), geht es automatisch zur naechsten
offenen Szene weiter (wiederverwendet: ``knoepfe.szenen._naechste_offene``).
Ist keine mehr offen, springt die Phase automatisch auf 6 -- die EINE,
ausdruecklich von Birk gewuenschte Ausnahme vom sonst geltenden
"Datenstand ist nicht Absicht" (AGENTS.md); sie bleibt lokal auf diesen
Abschluss begrenzt und aendert nichts an ``phasen.moegliche_naechste``/
``offenes_angebot`` fuer jeden anderen Phasenuebergang.

**Eigenes Sperren-Register**, nicht ``vorschlagssperre`` (die koppelt
ausschliesslich Schaerfung und Szenenfolge) und nicht ``szene._sperren``
(das ist je Szene, dieses hier ist je Gruppe fuer den ganzen
Uebersicht-Lauf) -- "Ein Sperren-Register je Nebenlaeufigkeit" (AGENTS.md).
"""

from __future__ import annotations

import logging
import threading

from interview_theater import anweisungen, modellwahl, phasen, repo, szene_claude

log = logging.getLogger(__name__)

ART_UEBERSICHT = "entwurf_uebersicht"

#: Ein Sperren-Register je Gruppe -- eigenes Register, siehe Modul-Docstring.
_sperren: dict[int, threading.Lock] = {}


def _sperre_fuer(chat_id: int) -> threading.Lock:
    sperre = _sperren.get(chat_id)
    if sperre is None:
        sperre = threading.Lock()
        _sperren[chat_id] = sperre
    return sperre
```

- [ ] **Step 2: Write the schema and prompt-text builders**

```python
#: Flach (global-constraints.md 'Schema'): keine verschachtelte Struktur,
#: eine Liste von Strings je Szene -- dieselbe Bauart wie schaerfung.SCHEMA.
SCHEMA_UEBERSICHT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["logline", "setting", "figuren_zeilen", "spannungsbogen",
                 "szenen_was_passiert"],
    "properties": {
        "logline": {"type": "string"},
        "setting": {"type": "string"},
        "figuren_zeilen": {"type": "array", "items": {"type": "string"}},
        "spannungsbogen": {"type": "string"},
        "szenen_was_passiert": {"type": "array", "items": {"type": "string"}},
    },
}


def prompt() -> str:
    """Heiss nachgeladen (interview_theater.anweisungen)."""
    return anweisungen.hole("entwurf")


def baue_nutzertext_uebersicht(conn, chat_id: int, notiz: str | None = None) -> str:
    """Setting, Figuren, Geschichte, Szenenanzahl -- und bei einer
    Neugenerierung die vorige Uebersicht plus die Rueckmeldung der Gruppe,
    damit ``uebersicht_aendern`` wirklich etwas AENDERT statt zufaellig neu
    zu wuerfeln."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    zeilen: list[str] = []
    if stand and (stand["rahmen"] or "").strip():
        zeilen.append(f"Setting: {stand['rahmen'].strip()}")
    if stand and (stand["geschichte"] or "").strip():
        zeilen.append(f"Story (arc and ending):\n{stand['geschichte'].strip()}")
    figuren = repo.figuren(conn, chat_id)
    if figuren:
        zeilen.append("Characters:")
        for figur in figuren:
            beschreibung = (figur["beschreibung"] or "").strip()
            zeilen.append(f"- {figur['name']}" + (f" -- {beschreibung}" if beschreibung else ""))
    anzahl = (stand["szenen_anzahl"] or "").strip() if stand else ""
    if anzahl:
        zeilen.append(f"Number of scenes: {anzahl}")
    bisherige = (stand["geschichte_uebersicht"] or "").strip() if stand else ""
    if bisherige:
        zeilen.append("Previous overview (for reference, to be replaced):")
        zeilen.append(bisherige)
    if notiz:
        zeilen.append(f"Feedback from the group on the previous overview: {notiz}")
    return "\n\n".join(zeilen)


def baue_anzeige(ergebnis: dict) -> str:
    """Setzt die Schema-Antwort zur Chat-Anzeige zusammen -- deterministisch,
    kein zweiter Modellaufruf."""
    zeilen = [f"Logline: {ergebnis.get('logline', '').strip()}",
              "", f"Setting: {ergebnis.get('setting', '').strip()}",
              "", "Characters:"]
    for zeile in ergebnis.get("figuren_zeilen") or []:
        zeilen.append(f"- {zeile}")
    zeilen.append("")
    zeilen.append(f"Tension arc: {ergebnis.get('spannungsbogen', '').strip()}")
    zeilen.append("")
    zeilen.append("Scenes:")
    for i, satz in enumerate(ergebnis.get("szenen_was_passiert") or [], start=1):
        zeilen.append(f"{i}. {satz.strip()}")
    return "\n".join(zeilen)
```

- [ ] **Step 3: Write the generation + thread-start functions**

```python
def generiere_uebersicht(klm, conn, e, chat_id: int, notiz: str | None = None) -> dict:
    """Der eigentliche Modellaufruf: Nutzertext bauen, Schema-Aufruf, Ergebnis
    zurueckgeben (schreibt noch NICHTS in die Datenbank -- das macht der
    Aufrufer, der auch die Chat-Anzeige verschickt)."""
    ergebnis = modellwahl.aufruf_schema(
        conn, klm, e, chat_id, prompt(), baue_nutzertext_uebersicht(conn, chat_id, notiz),
        SCHEMA_UEBERSICHT, ART_UEBERSICHT,
        ueber_claude=szene_claude.ist_aktiv(e, conn, chat_id), modell=e.erkenner_modell,
    )
    return ergebnis


def _lauf(conn, tg, klm, e, chat_id: int, notiz: str | None) -> None:
    from interview_theater import arbeitszeilen, knoepfe

    try:
        zeilen = arbeitszeilen.sichtbar(tg, chat_id, "entwurf_uebersicht")
        try:
            ergebnis = generiere_uebersicht(klm, conn, e, chat_id, notiz)
            anzeige = baue_anzeige(ergebnis)
            repo.setze_arbeitsstand(conn, chat_id, "geschichte_uebersicht", anzeige)
            # Einzeln, newline-getrennt -- Stufe B liest das hieraus zurueck
            # (entwurf.uebernimm_szenenfelder), statt die zusammengesetzte
            # Anzeige wieder zu zerlegen.
            repo.setze_arbeitsstand(
                conn, chat_id, "geschichte_uebersicht_szenen",
                "\n".join(ergebnis.get("szenen_was_passiert") or []),
            )
            repo.schreibe_journal(
                conn, chat_id, "entschieden",
                f"Geschichts-Uebersicht erzeugt ({len(anzeige)} Zeichen)",
                quelle="entwurf",
            )
        except Exception:
            log.exception("Uebersicht-Erzeugung fehlgeschlagen, chat_id=%s", chat_id)
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "entwurf_uebersicht_fehlgeschlagen", "Uebersicht-Erzeugung fehlgeschlagen",
            )
            from interview_theater import kosten
            kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id)
            anzeige = None
        finally:
            zeilen.stoppe()
        if anzeige:
            knoepfe.biete_uebersicht(conn, tg, chat_id, anzeige)
    finally:
        sperre = _sperren.get(chat_id)
        if sperre is not None and sperre.locked():
            sperre.release()


def starte_uebersicht(conn, tg, klm, e, chat_id: int, notiz: str | None = None):
    """Gibt die Uebersicht-Erzeugung an einen eigenen Thread ab -- dasselbe
    Muster wie ``schaerfung.starte``/``kernzitate.starte`` (Zusage 2: kein
    Modellaufruf im Knopf-/Erkenner-Handler)."""
    if klm is None:
        log.error("Entwurf-Uebersicht ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    if not _sperre_fuer(chat_id).acquire(blocking=False):
        return None
    try:
        thread = threading.Thread(
            target=_lauf, args=(conn, tg, klm, e, chat_id, notiz), daemon=True,
        )
        thread.start()
    except BaseException:
        _sperre_fuer(chat_id).release()
        raise
    return thread
```

Note: `knoepfe.biete_uebersicht` is created in Task 10 — this task can be
committed with a `# noqa` or by writing a minimal stub in `knoepfe/szenen.py`
first if strict import-time correctness is required for the test in Step 6;
prefer building Task 9 and Task 10 together if `entwurf.py` cannot import
cleanly without it (check whether `knoepfe` is imported lazily inside the
function, which it is here — `from interview_theater import ... knoepfe`
inside `_lauf` — so this only needs to resolve at call time, not at module
import time, meaning Task 9's tests can run without Task 10's button code
existing yet, as long as the test doesn't call `_lauf`/`starte_uebersicht`
end-to-end).

- [ ] **Step 4: Write the prompt files**

`interview_theater/prompts/entwurf.md` (German base — read
`interview_theater/prompts/schaerfung.md` first for the house style of a
schema-call system prompt: short, states its one job, no persona framing):

```markdown
Du baust aus einer erfundenen Geschichte eine kurze, strukturierte
Uebersicht fuer eine Theatergruppe. Du erfindest NICHTS Neues hinzu -- du
verdichtest, was die Gruppe bereits festgelegt hat (Setting, Figuren,
Geschichte), zu: einer Logline (ein Satz), dem Setting (ein bis zwei
Saetze), je einer Zeile pro Figur (wer sie ist, was sie will), dem
Spannungsbogen (ein bis zwei Saetze: worum es im Kern geht, wer was will,
was auf dem Spiel steht) und je Szene ein bis zwei Saetzen (was passiert,
die Wendung oder das Schluesselereignis).

Steht eine vorherige Uebersicht und eine Rueckmeldung der Gruppe dazu im
Text, AENDERE genau in die genannte Richtung -- nicht zufaellig neu
wuerfeln, sondern die konkrete Kritik aufnehmen.

Die Anzahl der Eintraege in "szenen_was_passiert" muss genau der genannten
Szenenanzahl entsprechen, wenn eine genannt ist -- sonst waehle eine
plausible Zahl zwischen drei und sieben.

Schreib knapp: die ganze Uebersicht soll roughly 1200-1500 Zeichen ergeben,
wenn man sie zusammensetzt.
```

`interview_theater/sprachen/en/prompts/entwurf.md` (the EN translation —
Padua is the only profile with `prosa_entwurf.aktiv = true`, but
`anweisungen.hole` resolves the language layer independent of that switch,
so the EN file must exist for Padua regardless):

```markdown
You build a short, structured overview from an invented story for a
theatre group. You invent NOTHING new -- you condense what the group has
already decided (setting, characters, story) into: a logline (one
sentence), the setting (one to two sentences), one line per character (who
they are, what they want), the tension arc (one to two sentences: what it's
really about, who wants what, what's at stake), and one to two sentences
per scene (what happens, the turn or key event).

If a previous overview and the group's feedback on it are in the text,
CHANGE it in exactly the direction named -- don't reroll randomly, take the
concrete criticism on board.

The number of entries in "szenen_was_passiert" must match the named number
of scenes exactly, if one is given -- otherwise choose a plausible number
between three and seven.

Write tightly: the whole overview should come to roughly 1200-1500
characters once assembled.
```

- [ ] **Step 5: Rewrite `phasen/5.md` (English) for the two-stage flow**

Replace the full content of `interview_theater/sprachen/en/prompts/phasen/5.md`
with:

```markdown
## Current phase: 5 · Prose Draft

Now the interviews come back into play. The group has invented the setting, characters
and story itself -- **that stays as it is**. The material doesn't change the
story, it sharpens it: next to each scene and each character it places
the passages that fit, with their word-for-word quote. After that, the whole
story gets written out as prose, scene by scene.

**What you work from: the core package.** The setting, the characters with their
way of speaking, the story, the scenes -- and the assignments that were created
automatically on entering this station (for each scene and each character,
with interview number and checked quote). You don't see full transcripts.

{{rahmen_knapp}}

What you focus on:

- **The story belongs to the group.** An interview passage is an
  offer, not an objection. Never say something "doesn't fit the material" -- say
  what the material adds to it.
- **Quotes are word for word or not at all.** What you quote appears like that in
  an interview; invented sentences are worse here than none at all, because
  they go into every scene text as a model.
- Always name the interview number, never a name: the interviewees should
  not be recognisable in the chat.
- If the group says no to a passage, that is an answer. Don't bring it up
  a second time.
- One sentence, **one** question per message.
- **Don't name any slash command.**

**Ask first, then suggest -- and only ever ONE question per message.**
You don't make a suggestion out of nowhere here: you ask about the group's
idea, take their answer and flesh it out into two to three options
(title — description each). If nothing usable comes,
you ask more narrowly -- from their core terms -- instead of inventing; only
when they explicitly say "you suggest" do you lay out three options. And
exactly one field per message: first the one, then in the next message the
next.

What you don't start on your own:

- **No new story.** The material doesn't justify a different arc or
  a different ending. What the group has invented counts.
- No new characters, no new scenes. Both are settled.
- Don't retell full transcripts.

If the group explicitly asks for it, you do it anyway; the phase is your
focus, not its limit. The phase is set afterwards.

Result of the phase: for each scene and each character the passages from the interviews that
carry them -- taken on or turned down -- and the whole story written out as
prose, scene by scene. It is finished when every scene has a prose draft the
group has accepted.

**The bot handles the controls, not you.** On entry the
assignment runs automatically; after that, for each scene and each character, a
suggestion message comes with the reflection ("Yes, save" · "No,
change it again"). Once the group has gone through them (or says it's
enough), a story overview appears -- logline, setting, characters, tension
arc, and one line per scene -- with "Yes, save" and "No, change it again"
underneath. Feedback in words works too, as long as the overview is
still on screen. Once the overview is saved, the first scene is drafted
as prose automatically -- no button needed -- and each saved scene starts
the next one by itself. A free-text "make that shorter"/"change it" on a
scene still in draft works the same way it does everywhere else: no
command needed, no chain of follow-up questions. Once every scene has a
saved draft, the phase moves on to Rewrite by itself. Don't name these
buttons and don't explain them -- they are there anyway.
```

(This replaces the old body wholesale because the activity it describes
has genuinely changed — unlike `4.md`/`6.md`/`7.md`, where only the header
needed updating.)

- [ ] **Step 6: Write unit tests for the pure functions**

Create `tests/test_entwurf.py`:

```python
from interview_theater import entwurf


def test_baue_anzeige_enthaelt_alle_abschnitte():
    ergebnis = {
        "logline": "Two sisters meet again after years apart.",
        "setting": "A station cafe, late evening.",
        "figuren_zeilen": ["Mira -- wants closeness", "Nora -- wants distance"],
        "spannungsbogen": "Neither says what they want.",
        "szenen_was_passiert": ["They arrive.", "A photo surfaces.", "A confession."],
    }
    anzeige = entwurf.baue_anzeige(ergebnis)
    assert "Logline: Two sisters meet again after years apart." in anzeige
    assert "- Mira -- wants closeness" in anzeige
    assert "1. They arrive." in anzeige
    assert "3. A confession." in anzeige


def test_baue_nutzertext_uebersicht_traegt_vorige_fassung_und_notiz(db_conn):
    from interview_theater import repo

    chat_id = 1
    repo.sichere_gruppe(db_conn, chat_id, "testbot")
    repo.setze_arbeitsstand(db_conn, chat_id, "rahmen", "A hallway, moving boxes.")
    repo.setze_arbeitsstand(db_conn, chat_id, "geschichte_uebersicht", "Logline: old one")
    text = entwurf.baue_nutzertext_uebersicht(db_conn, chat_id, notiz="make it sadder")
    assert "A hallway, moving boxes." in text
    assert "Logline: old one" in text
    assert "make it sadder" in text
```

(Match `db_conn`/fixture conventions actually used elsewhere in the test
suite — check `tests/test_schaerfung.py` for the closest analogue, since
`entwurf.py` mirrors `schaerfung.py`'s structure closely, and copy its
fixture usage exactly.)

- [ ] **Step 7: Run the new tests and the full suite**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest tests/test_entwurf.py -q -p no:cacheprovider`
Expected: PASS.

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: green (note: `entwurf.py` references `knoepfe.biete_uebersicht`
lazily inside `_lauf`, which doesn't exist until Task 10 — this is fine as
long as no test in this task calls `_lauf`/`starte_uebersicht` end-to-end;
if the full-suite run discovers an import-time `AttributeError` anywhere,
that means something imports `knoepfe.biete_uebersicht` eagerly — fix by
confirming the import inside `_lauf` stays function-local).

Also run `python -m scripts.pruefe_profil --alle` to confirm the new
`entwurf.md` prompt file doesn't trip any placeholder-resolution check for
either profile (it has no `{{...}}` placeholders, so this should be a
no-op check).

- [ ] **Step 8: Commit**

```bash
git add interview_theater/entwurf.py interview_theater/prompts/entwurf.md \
        interview_theater/sprachen/en/prompts/entwurf.md \
        interview_theater/sprachen/en/prompts/phasen/5.md \
        tests/test_entwurf.py
git commit -m "$(cat <<'EOF'
entwurf: Stage A story overview generation for Phase 5 (Prose Draft)

Schema call, display assembly, thread-start with its own lock register.
Button wiring (knoepfe.biete_uebersicht) follows in the next task.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Stage A buttons + `uebersicht_aendern` wiring into `erkenner.laufe`

**Files:**
- Modify: `interview_theater/knoepfe/texte.py` (new `ART_*` constants)
- Modify: `interview_theater/knoepfe/szenen.py` (new `biete_uebersicht` function)
- Modify: `interview_theater/knoepfe/wirkung.py` (two new handlers + `_WIRKUNGEN` entries)
- Modify: `interview_theater/entwurf.py` (new `uebernimm_szenenfelder`, `erste_offene_szene` functions)
- Modify: `interview_theater/erkenner.py` (`laufe()` gains a call that resolves `uebersicht_aendern` into `entwurf.starte_uebersicht`, mirroring `_starte_szene`/`_starte_kuerzung`)
- Test: `tests/test_knoepfe_struktur.py` runs unchanged (AST check); `tests/test_entwurf.py` gains an integration-style test with a fake `tg`/`klm`

**Interfaces:**
- Consumes: `entwurf.starte_uebersicht`, `entwurf.generiere_uebersicht` (Task 9); `repo.lege_knopf_an`, `repo.beanspruche_knopf` (existing, used by every other handler — check `knoepfe/basis.py` for the exact helper names, e.g. `_daten`/`_starte_auftrag`).
- Produces: `knoepfe.biete_uebersicht(conn, tg, chat_id, anzeige_text) -> None`;
  pressing "Yes, save" fixes the overview and starts Stage B's first scene;
  pressing "No, change it again" re-runs Stage A; a chat message recognised
  as `uebersicht_aendern` (only in phase 5, per Task 5's gate) does the same
  as the button, via `erkenner.laufe`.

- [ ] **Step 1: Read the exact button-wiring pattern to copy**

Before writing anything, read `interview_theater/knoepfe/szenen.py`'s
`biete_nach_szenentext` function in full (quoted during planning — it
builds a `leiste` list of `(label, _daten(repo.lege_knopf_an(...)))` pairs)
and `interview_theater/knoepfe/wirkung.py`'s `_wirkung_szene_passt` and
`_wirkung_szene_anders` handlers in full. Match this exact shape — don't
invent a different calling convention.

- [ ] **Step 2: Add two `ART_*` constants**

In `interview_theater/knoepfe/texte.py`, next to the existing `ART_SZENE_*`
constants, add:

```python
# Padua Phasen TEIL 1 (03.10.2026): Stufe A von Phase 5 (Prose Draft).
ART_UEBERSICHT_PASST = "uebersicht_passt"
ART_UEBERSICHT_ANDERS = "uebersicht_anders"
```

Also add the two button labels next to the existing `TEXT_PASST_KNOPF`/
`TEXT_ANDERS_KNOPF` constants, matching their exact English wording used
elsewhere (`"Yes, save"` / `"No, change it again"` — these phrases are
already used verbatim in `sprachen/en/prompts/system.md` line 253 for the
single-value reflection pattern, so reuse the SAME button-label constants
if they already exist for that purpose rather than creating near-duplicate
strings — grep `grep -n "Yes, save\|No, change it again" interview_theater/knoepfe/texte.py interview_theater/sprachen/en/texte.toml` first).

- [ ] **Step 3: Add `knoepfe.biete_uebersicht`**

In `interview_theater/knoepfe/szenen.py`, add a new function near
`biete_nach_szenentext`:

```python
def biete_uebersicht(conn, tg, chat_id: int, anzeige: str) -> None:
    """Zeigt die generierte Geschichts-Uebersicht mit den zwei Knoepfen
    "Yes, save" / "No, change it again" (Padua Phasen TEIL 1, Stufe A)."""
    from interview_theater import repo

    leiste = [
        (T.TEXT_PASST_KNOPF, _daten(repo.lege_knopf_an(conn, chat_id, T.ART_UEBERSICHT_PASST, ""))),
        (T.TEXT_ANDERS_KNOPF, _daten(repo.lege_knopf_an(conn, chat_id, T.ART_UEBERSICHT_ANDERS, ""))),
    ]
    message_id = tg.sende_mit_knoepfen(chat_id, anzeige, leiste)
    repo.merke_bot_zeile(conn, chat_id, message_id, None, anzeige)
```

(Check the exact name of the "send with buttons" method on `tg` used by
`biete_nach_szenentext` — `tg.sende_mit_knoepfen` is the inferred name based
on the codebase's German naming convention; confirm against the actual
`telegram.py`/`web_kanal.py` method name and use that exact one. Also
confirm whether `repo.merke_bot_zeile` takes `e` or `None` for an
anonymous/system bot line elsewhere, matching existing call sites.)

- [ ] **Step 4: Add the two handlers in `knoepfe/wirkung.py`**

```python
def _wirkung_uebersicht_passt(conn, d: Druck) -> str:
    """"Yes, save": die Uebersicht ist fix, Stufe B beginnt (Padua Phasen
    TEIL 1). Kein Modellaufruf hier (Zusage 2) -- die erste Szene wird im
    naechsten Schritt dieser Funktion ueber ``szene.starte`` angestossen,
    das selbst einen Thread aufmacht."""
    from interview_theater import entwurf, repo, szene

    repo.setze_arbeitsstand(conn, d.chat_id, "geschichte_uebersicht_fixiert_am", repo.jetzt())
    entwurf.uebernimm_szenenfelder(conn, d.chat_id)
    erste = entwurf.erste_offene_szene(conn, d.chat_id)
    if erste is not None:
        auftrag = f"SZENE {erste}: write this scene as prose, following the overview."
        szene.starte(conn, d.tg, d.klm, d.e, d.chat_id, auftrag)
    return T.TEXT_UEBERSICHT_FIXIERT


def _wirkung_uebersicht_anders(conn, d: Druck) -> str:
    """"No, change it again": ein neuer Uebersicht-Lauf, kein Modellaufruf
    im Handler selbst (Zusage 2) -- ``entwurf.starte_uebersicht`` macht das
    im eigenen Thread."""
    from interview_theater import entwurf

    entwurf.starte_uebersicht(conn, d.tg, d.klm, d.e, d.chat_id)
    return T.TEXT_UEBERSICHT_WIRD_NEU_ERZEUGT
```

Add both to `_WIRKUNGEN`:
```python
    ART_UEBERSICHT_PASST: _wirkung_uebersicht_passt,
    ART_UEBERSICHT_ANDERS: _wirkung_uebersicht_anders,
```

Add the two new text constants (`TEXT_UEBERSICHT_FIXIERT`,
`TEXT_UEBERSICHT_WIRD_NEU_ERZEUGT`) to `knoepfe/texte.py`, matching the
short, factual tone of neighbouring confirmation strings (e.g.
`"Got it -- writing the first scene now."` / `"On it -- a new overview is
coming."`).

Write `_uebernimm_szenenfelder_aus_uebersicht` and
`_erste_offene_entwurfsszene` as new helper functions (either in
`knoepfe/szenen.py` or `entwurf.py` — prefer `entwurf.py` since they are
domain logic, not button plumbing, and `knoepfe/wirkung.py`'s handler then
just calls `entwurf.uebernimm_szenenfelder(conn, chat_id)` and
`entwurf.erste_offene_szene(conn, chat_id)`):

```python
# in interview_theater/entwurf.py

def uebernimm_szenenfelder(conn, chat_id: int) -> None:
    """Stufe A -> B: jede Szene bekommt ihre Pflichtfelder aus der
    Uebersicht, sofern sie noch leer sind. ``form`` bleibt aussen vor --
    das ist in Phase 5 kein Pflichtfeld (``szene.schreibt_prosa``).

    ``was_passiert`` kommt zeilenweise aus
    ``arbeitsstand.geschichte_uebersicht_szenen`` (Task 6/9 -- die
    EINZELNEN Szenensaetze, getrennt von der zusammengesetzten Anzeige, die
    Task 9's ``_lauf`` dort ablegt). Ort faellt auf das Setting zurueck
    (AGENTS.md, "The setting is the default for place, time and occasion of
    every scene"); die Besetzung faellt auf die volle Figurenliste zurueck
    (dokumentierte Vereinfachung, Padua Phasen TEIL 1 -- das Schema liefert
    keine Besetzung je Szene, um flach zu bleiben). Alle drei sind ueber die
    Gruppenseite danach aenderbar."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return
    rahmen = (stand["rahmen"] or "").strip()
    anzahl_text = (stand["szenen_anzahl"] or "").strip()
    anzahl = int(anzahl_text) if anzahl_text.isdigit() else 0
    was_passiert_zeilen = (stand["geschichte_uebersicht_szenen"] or "").splitlines()
    figuren_ids = [f["id"] for f in repo.figuren(conn, chat_id)]
    for nummer in range(1, anzahl + 1):
        szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
        zeile = repo.hole_szene(conn, szene_id)
        if not (zeile["was_passiert"] or "").strip() and nummer - 1 < len(was_passiert_zeilen):
            satz = was_passiert_zeilen[nummer - 1].strip()
            if satz:
                repo.setze_szenenfeld(conn, szene_id, "was_passiert", satz)
        if not (zeile["ort"] or "").strip() and rahmen:
            repo.setze_szenenfeld(conn, szene_id, "ort", rahmen)
        if not repo.szene_figuren(conn, szene_id) and figuren_ids:
            repo.setze_szene_figuren(conn, chat_id, szene_id, figuren_ids)


def erste_offene_szene(conn, chat_id: int) -> int | None:
    """Die niedrigste Szenennummer, deren Prosa-Entwurf noch nicht
    abgenommen ist (``szene.entwurf_bestaetigt_am``). Pflichtfelder
    (``was_passiert``, Besetzung) muessen schon dastehen --
    ``uebernimm_szenenfelder`` laeuft vorher."""
    for s in sorted(repo.hole_szenen(conn, chat_id), key=lambda z: z["nummer"] or 0):
        if s["nummer"] is not None and not (s["entwurf_bestaetigt_am"] or "").strip():
            return s["nummer"]
    return None
```

- [ ] **Step 5: Wire `uebersicht_aendern` into `erkenner.laufe`**

In `interview_theater/erkenner.py`, add a new function mirroring
`_starte_kuerzung`'s shape, and call it from `laufe()` right after
`_starte_kuerzung(...)`:

```python
def _starte_entwurf_uebersicht(klm, tg, conn, e, chat_id: int,
                                aenderungen: list[dict]) -> None:
    """Stoesst eine Neugenerierung der Stufe-A-Uebersicht an, wenn der
    Erkenner ``uebersicht_aendern`` gefunden hat (Padua Phasen TEIL 1).
    Phasengebunden ueber PHASEN_SPEZIFISCHE_ARTEN -- wende_an() hat eine
    fehlplatzierte Meldung schon herausgefiltert, bevor sie hier ankommt."""
    treffer = next(
        (a for a in aenderungen if a.get("art") == "uebersicht_aendern"), None
    )
    if treffer is None:
        return
    from interview_theater import entwurf

    entwurf.starte_uebersicht(conn, tg, klm, e, chat_id, treffer.get("wert") or None)
```

In `laufe()`, add `_starte_entwurf_uebersicht(klm, tg, conn, e, chat_id, aenderungen)`
right after the existing `_starte_kuerzung(klm, tg, conn, e, chat_id, aenderungen)` line.

Note this reads from `aenderungen` (the recognised list) not `wirkliche`
(the applied list) — same reasoning as `_starte_szene`/`_starte_kuerzung`:
`uebersicht_aendern` has no write path in `_wende_eine_an` (it never
appears in `wirkliche`), it only triggers an action. Confirm
`_wende_eine_an` has a no-op branch for it (add one, matching the
`szene_schreiben`/`szene_kuerzen` pattern):

```python
    if art == "uebersicht_aendern":
        # Kein Schreibpfad, wie szene_schreiben: diese art stoesst eine
        # Neugenerierung an (entwurf.py), die laufe() auswertet.
        return None
```

Add this branch to `_wende_eine_an` right after the `szene_kuerzen` branch.

- [ ] **Step 6: Run `tests/test_knoepfe_struktur.py`**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest tests/test_knoepfe_struktur.py -q -p no:cacheprovider`
Expected: PASS (the AST check confirms both new `ART_*` constants have a
handler in `_WIRKUNGEN`, no model call appears directly inside either
handler body — both call into `entwurf`/`szene` functions that spawn their
own threads, matching every other handler's shape).

- [ ] **Step 7: Run the full suite**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: green.

- [ ] **Step 8: Commit**

```bash
git add interview_theater/knoepfe/texte.py interview_theater/knoepfe/szenen.py \
        interview_theater/knoepfe/wirkung.py interview_theater/entwurf.py \
        interview_theater/erkenner.py
git commit -m "$(cat <<'EOF'
Stage A buttons (Yes, save / No, change it again) and chat-driven
overview feedback wired through erkenner.laufe

Stage A confirmation populates each scene's was_passiert/ort/cast
defaults from the overview and starts the first scene draft via the
existing szene.starte -- no new scene-writing machinery needed.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Wire Stage A auto-start after the automatic schärfung pass, on phase-5 entry

**Files:**
- Modify: `interview_theater/knoepfe/stationen.py` (the `PHASE_SCHAERFUNG`/phase-5 entry block that currently calls `schaerfung.starte(...)`)

**Interfaces:**
- Consumes: `workshop.prosa_entwurf_aktiv()` (Task 7), `entwurf.starte_uebersicht` (Task 9), `schaerfung.starte(..., nachbereitung=...)` (existing).
- Produces: when a group enters phase 5 under the Padua profile (with the
  switch on), the automatic schärfung run's `nachbereitung` callback starts
  the Stage A overview generation. For every other profile, the call site
  is unchanged (passes `nachbereitung=None` or whatever it does today).

- [ ] **Step 1: Find and read the exact current call site**

Run: `grep -n "schaerfung.starte\|PHASE_SCHAERFUNG" interview_theater/knoepfe/stationen.py`

Read the surrounding ~20 lines in full — this is inside `eintritt_in_phase`
(per the earlier research: "special-cased blocks for ... `PHASE_SCHAERFUNG`").
Confirm exactly what `nachbereitung` is today (likely `None`, or a
function that just logs — quote it exactly before changing it).

- [ ] **Step 2: Make the `nachbereitung` conditional on the profile switch**

Replace the existing call (shape inferred, **adjust to match exactly what
Step 1 found**):

```python
    if nummer == phasen.PHASE_SCHAERFUNG:  # or whatever the exact constant/condition is
        from interview_theater import entwurf, workshop

        nachbereitung = None
        if workshop.prosa_entwurf_aktiv():
            def nachbereitung():
                entwurf.starte_uebersicht(conn, tg, klm, e, chat_id)
        schaerfung.starte(conn, tg, klm, e, chat_id, nachbereitung=nachbereitung)
```

If the existing call already passes a non-`None` `nachbereitung` for some
other reason, **compose** both callbacks (call the existing one, then the
new one) rather than discarding the existing behaviour — read Step 1's
findings carefully before deciding which shape applies.

- [ ] **Step 3: Write a test confirming Dortmund is unaffected**

Add to whatever test file already covers phase-entry behaviour for
schärfung (check `tests/test_knoepfe*.py` or `tests/test_stationen.py` for
an existing test that asserts `schaerfung.starte` gets called on phase-5
entry, and extend it or add a sibling test):

```python
def test_entwurf_startet_nur_mit_aktivem_profilschalter(monkeypatch, db_conn):
    from interview_theater import entwurf, knoepfe, workshop

    aufgerufen = []
    monkeypatch.setattr(entwurf, "starte_uebersicht",
                         lambda *a, **k: aufgerufen.append(True))
    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: False)
    # ... trigger phase-5 entry exactly as the existing schaerfung-on-entry
    # test does (copy its setup) ...
    assert not aufgerufen
    monkeypatch.setattr(workshop, "prosa_entwurf_aktiv", lambda *a, **k: True)
    # ... trigger phase-5 entry again ...
    assert aufgerufen
```

Fill in the exact phase-5-entry trigger call by copying the setup of the
nearest existing test for `schaerfung.starte` being invoked on entry —
don't invent a new entry path.

- [ ] **Step 4: Run the relevant test file and the full suite**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest tests/ -k "schaerfung or stationen or entwurf" -q -p no:cacheprovider`
Expected: PASS.

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/knoepfe/stationen.py tests/
git commit -m "$(cat <<'EOF'
Start the Stage A overview generation after Phase 5's automatic
sharpening pass, gated behind [prosa_entwurf] aktiv

Dortmund's schaerfung-on-entry call is unchanged -- nachbereitung stays
None unless the profile switch is on.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Stage B auto-advance and automatic phase jump to 6

**Files:**
- Modify: `interview_theater/knoepfe/wirkung.py` (`_wirkung_szene_passt` gains a phase-5 branch)

**Interfaces:**
- Consumes: `entwurf.erste_offene_szene` (Task 10), `phasen.setze`, `knoepfe.eintritt_in_phase` (existing), `szene.starte` (existing).
- Produces: confirming a scene's draft in phase 5 (via the existing "Passt"
  button, `ART_SZENE_PASST`) stamps `entwurf_bestaetigt_am`, then either
  auto-starts the next open scene (no button, no wait) or — if none remain —
  calls `phasen.setze(conn, chat_id, 6, quelle="entwurf", notiz="all scenes drafted")`
  and sends phase 6's entry message. Phase 7's existing button-offer
  behaviour (`_biete_weiter_nach_szene`) is **unchanged** for every other
  phase.

- [ ] **Step 1: Read `_wirkung_szene_passt` in full**

Run: `grep -n "_wirkung_szene_passt" interview_theater/knoepfe/wirkung.py`

Read the full function body (confirmed during planning to call
`repo.setze_szene_fertig`, journal, then `_biete_weiter_nach_szene`). Note
exactly where the scene number and `chat_id` are available (`d.chat_id`,
and the scene number from `d.knopf["wert"]` or similar — confirm the exact
accessor from this read).

- [ ] **Step 2: Add the phase-5 branch**

Modify `_wirkung_szene_passt` to branch on the current phase **before**
calling the existing `fertig_am`/`_biete_weiter_nach_szene` path:

```python
def _wirkung_szene_passt(conn, d: Druck) -> str:
    nummer = int(d.knopf["wert"])  # match the exact existing extraction
    from interview_theater import phasen

    if phasen.aktuelle(conn, d.chat_id) == 5:
        return _wirkung_entwurf_szene_passt(conn, d, nummer)
    # ... existing body, unchanged, for every other phase (7 today) ...
```

Add the new phase-5-specific function right after it:

```python
def _wirkung_entwurf_szene_passt(conn, d: Druck, nummer: int) -> str:
    """"Yes, save" auf einem Prosa-Entwurf in Stufe B von Phase 5 (Padua
    Phasen TEIL 1): Szene abnehmen, automatisch weiter -- zur naechsten
    offenen Szene (kein Knopf, kein Warten) oder, wenn keine mehr offen
    ist, automatisch nach Phase 6. Das ist die EINE, ausdruecklich von
    Birk gewuenschte Ausnahme vom sonst geltenden "Datenstand ist nicht
    Absicht" (AGENTS.md) -- lokal auf diesen Abschluss begrenzt,
    ``phasen.moegliche_naechste``/``offenes_angebot`` bleiben fuer jeden
    anderen Uebergang unveraendert."""
    from interview_theater import entwurf, knoepfe, phasen, repo, szene

    szene_id = repo.stelle_szene_sicher(conn, d.chat_id, nummer)
    repo.setze_szene_entwurf_bestaetigt(conn, szene_id)
    naechste = entwurf.erste_offene_szene(conn, d.chat_id)
    if naechste is not None:
        auftrag = f"SZENE {naechste}: write this scene as prose, following the overview."
        szene.starte(conn, d.tg, d.klm, d.e, d.chat_id, auftrag)
        return T.TEXT_NAECHSTE_SZENE_WIRD_GESCHRIEBEN
    phasen.setze(conn, d.chat_id, 6, "entwurf", notiz="alle Szenen entworfen")
    knoepfe.eintritt_in_phase(conn, d.tg, d.klm, d.e, d.chat_id, 6)
    return T.TEXT_ALLE_SZENEN_ENTWORFEN
```

Add `T.TEXT_NAECHSTE_SZENE_WIRD_GESCHRIEBEN` and `T.TEXT_ALLE_SZENEN_ENTWORFEN`
to `knoepfe/texte.py`, short and factual (e.g. `"Got it -- writing the next
scene now."` / `"All scenes have a draft. On to Rewrite."`).

- [ ] **Step 3: Also handle chat-driven confirmation parity for revision**

Confirm (do not implement unless missing) that `szene_schreiben`/
`szene_kuerzen`'s existing resolution-to-`hole_letzte_szene` behaviour
(Task context notes) correctly targets the scene most recently drafted in
Stage B when the group says "no, change it, make it funnier" without a
scene number. Write one test proving this (see Step 4) rather than new
code — per the plan's scope decision, no new write path is needed here.

- [ ] **Step 4: Write tests**

Add to `tests/test_knoepfe_wirkung.py` (or the correct existing file —
check which file already tests `_wirkung_szene_passt`):

```python
def test_entwurf_szene_passt_startet_naechste_szene_automatisch(db_conn, monkeypatch):
    # Setup: phase 5, two scenes, scene 1 has a prose draft and gets "Yes, save".
    # Assert: entwurf_bestaetigt_am is set on scene 1, szene.starte is called
    # for scene 2, no phase change happens yet.
    ...


def test_entwurf_letzte_szene_passt_springt_automatisch_nach_phase_6(db_conn, monkeypatch):
    # Setup: phase 5, one scene, already drafted, "Yes, save" pressed.
    # Assert: entwurf_bestaetigt_am is set, phasen.aktuelle(...) == 6 afterwards,
    # knoepfe.eintritt_in_phase was called with nummer=6.
    ...


def test_phase_7_szene_passt_verhaelt_sich_unveraendert(db_conn, monkeypatch):
    # Setup: phase 7, one scene with a written theatre text, "Yes, save" pressed.
    # Assert: the EXISTING behaviour (fertig_am set, _biete_weiter_nach_szene
    # called) still happens -- this is the regression guard that Task 12
    # didn't change phase 7.
    ...
```

Fill in each test body by copying the setup pattern of whatever existing
test already exercises `_wirkung_szene_passt` for phase 7 (there should be
one — find it with `grep -rn "_wirkung_szene_passt\|ART_SZENE_PASST" tests/`)
and adapting the phase number / assertions. Use `monkeypatch.setattr` on
`szene.starte` and `knoepfe.eintritt_in_phase` to avoid real model/thread
calls, matching how neighbouring tests in that file already stub these.

- [ ] **Step 5: Run the new tests and the full suite**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -k "entwurf_szene or phase_7_szene_passt" -q -p no:cacheprovider`
Expected: PASS.

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: green. This is the regression-sensitive task in the whole plan —
if the phase-7 regression test fails, stop and fix before continuing;
do not weaken or delete that test to make the suite pass.

- [ ] **Step 6: Commit**

```bash
git add interview_theater/knoepfe/wirkung.py interview_theater/knoepfe/texte.py tests/
git commit -m "$(cat <<'EOF'
Stage B: auto-advance through scene drafts, automatic jump to Phase 6
once all scenes are drafted

Scoped to phase 5 only via a branch in the existing "Passt" handler;
phase 7's button-offer behaviour is proven unchanged by a regression test.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: End-to-end test of the full Phase 5 two-stage flow

**Files:**
- Create: `tests/test_entwurf_ablauf.py`

**Interfaces:**
- Consumes: everything from Tasks 5–12, plus whatever fake LLM client the
  test suite already uses for schema/prosa calls (check `tests/conftest.py`
  or the fakes used by `tests/test_schaerfung.py`/`tests/test_szene.py` —
  reuse the exact same fake, don't build a new one).

- [ ] **Step 1: Find and reuse the existing LLM fake**

Run: `grep -rln "class.*KLM\|KLMAttrappe\|FakeKLM" tests/` and read the one
used by `tests/test_schaerfung.py` in full. It needs to support both
`.schema(...)` (for Stage A's overview call and the erkenner call) and
`.prosa(...)`/whatever `szene.schreibe` actually calls (check `szene.py`'s
`hole_text`-equivalent — likely `klm.prosa` or a schema call, confirmed
during planning research: `szene.schreibe` dispatches based on
`schreibt_prosa`/form, calling a prosa-style generation). Extend the fake
if it doesn't yet support whatever `szene.starte` needs, in the test file
itself (a local subclass), not by changing the shared fake for every other
test.

- [ ] **Step 2: Write the scripted trace**

```python
def test_phase5_ueberblick_bis_automatischer_sprung_nach_6(db_conn, monkeypatch):
    """Demonstriert end-to-end (ohne echtes Modell): Phase 5 betreten ->
    Uebersicht generiert -> Rueckmeldung per Chat AENDERT die gespeicherte
    Uebersicht -> "Yes, save" -> Szene 1 Entwurf -> "Yes, save" -> Szene 2
    Entwurf (letzte) -> "Yes, save" -> automatisch Phase 6.

    Das ist der vom Auftrag geforderte Nachweis, dass Chat-Rueckmeldung in
    Phase 5 tatsaechlich den gespeicherten Stand aendert -- nicht nur
    Knopfdruecke."""
    import threading

    from interview_theater import (entwurf, erkenner, knoepfe, phasen, repo,
                                    szene, workshop)

    chat_id = 1
    repo.sichere_gruppe(db_conn, chat_id, "testbot")
    repo.setze_arbeitsstand(db_conn, chat_id, "rahmen", "A hallway, moving boxes.")
    repo.setze_arbeitsstand(db_conn, chat_id, "geschichte", "Two friends drift apart.\nEnde: they don't speak again.")
    repo.setze_arbeitsstand(db_conn, chat_id, "figuren_fixiert_am", repo.jetzt())
    repo.setze_arbeitsstand(db_conn, chat_id, "szenen_anzahl", "2")
    repo.setze_figur(db_conn, chat_id, "Alex", "")
    phasen.setze(db_conn, chat_id, 5, "befehl")

    klm = FakeKLMMitUebersichtUndProsa()  # built in Step 1, generates
                                           # deterministic, distinguishable
                                           # output per call so the test can
                                           # assert on its content
    tg = FakeTelegram()  # reuse the project's existing fake, e.g.
                          # simulation.attrappe.Telegram or a test-local one

    # Schritt 1: Uebersicht wird generiert und gespeichert.
    entwurf.generiere_uebersicht(klm, db_conn, _FakeE(), chat_id)
    stand = repo.hole_arbeitsstand(db_conn, chat_id)
    assert stand["geschichte_uebersicht"]
    erste_fassung = stand["geschichte_uebersicht"]

    # Schritt 2: Rueckmeldung per Chat (uebersicht_aendern) AENDERT den
    # gespeicherten Stand -- nicht nur ein Knopfdruck.
    e = _FakeE()
    aenderungen = [{"art": "uebersicht_aendern", "wert": "make the ending sadder"}]
    erkenner._starte_entwurf_uebersicht(klm, tg, db_conn, e, chat_id, aenderungen)
    # entwurf.starte_uebersicht laeuft in einem Thread -- im Test synchron
    # erzwingen (entweder generiere_uebersicht direkt aufrufen oder den
    # Thread joinen, je nachdem wie starte_uebersicht in Task 9 gebaut ist).
    _warte_auf_laufenden_entwurf(chat_id)
    zweite_fassung = repo.hole_arbeitsstand(db_conn, chat_id)["geschichte_uebersicht"]
    assert zweite_fassung != erste_fassung  # die Chat-Rueckmeldung hat gewirkt

    # Schritt 3: "Yes, save" -> Stufe B, Szene 1 wird entworfen.
    knoepfe.wirkung._wirkung_uebersicht_passt(db_conn, _FakeDruck(tg, klm, e, chat_id))
    _warte_auf_laufende_szene(chat_id)
    szene1 = next(s for s in repo.hole_szenen(db_conn, chat_id) if s["nummer"] == 1)
    assert (szene1["prosa"] or "").strip()

    # Schritt 4: Szene 1 "Yes, save" -> Szene 2 automatisch.
    knoepfe.wirkung._wirkung_szene_passt(db_conn, _FakeDruck(tg, klm, e, chat_id, wert="1"))
    _warte_auf_laufende_szene(chat_id)
    szene2 = next(s for s in repo.hole_szenen(db_conn, chat_id) if s["nummer"] == 2)
    assert (szene2["prosa"] or "").strip()
    assert phasen.aktuelle(db_conn, chat_id) == 5  # noch nicht gesprungen

    # Schritt 5: Szene 2 (letzte) "Yes, save" -> automatisch Phase 6.
    knoepfe.wirkung._wirkung_szene_passt(db_conn, _FakeDruck(tg, klm, e, chat_id, wert="2"))
    assert phasen.aktuelle(db_conn, chat_id) == 6
```

This test will need real supporting fakes (`_FakeE`, `_FakeDruck`,
`_warte_auf_laufenden_entwurf`/`_warte_auf_laufende_szene` — likely a
`threading.Event` the fake LLM sets, or simply calling the underlying
function directly instead of the thread-spawning wrapper where joining a
background thread would make the test flaky). **Prefer calling the
non-threaded inner functions directly** (`entwurf.generiere_uebersicht`
instead of `entwurf.starte_uebersicht`, and a non-threaded `szene.schreibe`
instead of `szene.starte` where the existing test suite already does this
for `szene.py` — check `tests/test_szene.py` for this exact pattern and
copy it) to keep the test deterministic and fast, reserving the threaded
wrappers for Task 10's button-handler tests that specifically assert the
thread gets started.

- [ ] **Step 2: Run the new test**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest tests/test_entwurf_ablauf.py -q -p no:cacheprovider -v`
Expected: PASS, with the four assertions above all holding — this is the
acceptance criterion from the original card ("a targeted pytest covering
the new intent paths... demonstrating phase 5 chat feedback actually
changes the stored overview / scene count / a scene's text").

- [ ] **Step 3: Run the full suite one more time**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add tests/test_entwurf_ablauf.py
git commit -m "$(cat <<'EOF'
test: end-to-end trace of Phase 5's two-stage flow, chat feedback included

Demonstrates: overview generated, chat feedback changes the stored
overview, confirming drafts advances automatically, last scene triggers
the automatic jump to Phase 6.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Run `scripts.pruefe_prompts` for the new erkenner art (best-effort, costs money)

**Files:** none modified — this task runs an external command and records
its outcome; if it edits anything, it's only `korpus/berichte/` (gitignored)
or a documentation line about the outcome.

**Interfaces:**
- Consumes: `scripts/pruefe_prompts.py` (existing CLI).

- [ ] **Step 1: Check for network/credentials availability first**

Run: `env | grep -i "IT_LLM\|IT_BOT_TOKEN" | sed 's/=.*/=<set>/'`
If no `IT_LLM_URL`/model credentials are configured in this environment,
**skip to Step 4** and record "not run: no credentials/network available in
this sandboxed worktree" in the final report — do not attempt to fabricate
or fake a result.

- [ ] **Step 2: If credentials exist, run the German corpus check**

```
set -a; . ./betrieb/<any-configured-group>.env; set +a
python -m scripts.pruefe_prompts erkenner --nur ue01-uebersicht-ende-trauriger,ue02-uebersicht-nochmal-ohne-richtung,n55-uebersicht-ja-ist-kein-aendern
```
Expected (if it runs): exit code 0, 0 false positives reported for these
cases plus the full existing negative set (the script always runs the full
negative set for FP counting unless `--nur` restricts positives only — check
`scripts/pruefe_prompts.py`'s `--nur` semantics before assuming a partial
run skips the FP gate).

- [ ] **Step 3: If credentials exist, run the English corpus check**

```
python -m scripts.pruefe_prompts erkenner --sprache en --workshop padua-2026 --nur ue01-overview-ending-sadder,ue02-overview-try-again-no-direction,n55-overview-yes-is-not-aendern
```

- [ ] **Step 4: Record the outcome**

Write one paragraph for the final report: whether the run happened, the
exact command(s), the exit code, the FP count, and — if it ran — the
approximate cost (the script logs token usage and cost per the existing
`kosten.py` pricing table; report the number it prints). If it did not run,
state clearly that this is an open item for whoever has API access before
merging.

- [ ] **Step 5: No code commit needed** unless the run surfaces a genuine
prompt wording problem — if so, fix `korpus/erkenner.jsonl`/
`sprachen/en/prompts/erkenner.md` and re-run, then commit with a message
describing exactly what the real-model run caught.

---

## Task 15: Rewrite `README.md`

**Files:**
- Modify: `README.md`

**Interfaces:** none — pure documentation.

- [ ] **Step 1: Verify every claim against the current code before writing**

Before touching the file, confirm (grep/read, don't assume from memory of
this plan):
- The exact current tab labels in `interview_theater/web_vereint.py`'s
  `_TEXT_TAB` dict (confirmed during planning: `"Chat"`, `"Arbeitsstand"`,
  `"Textbuch"`, conditional `"Bühne"` in phase 4 — **re-check this is still
  true after Tasks 1–14**, since Task 10/12 touch `knoepfe/` and `entwurf.py`
  but not `web_vereint.py`, so it should be unchanged; confirm with
  `grep -n "_TEXT_TAB" interview_theater/web_vereint.py`).
- The seven phase names are now Terms · Questions · Interviews · Frame ·
  Prose Draft · Rewrite · Stage Version (Task 1).
- `interview_theater/modellwahl.py` exists and documents the Kimi/Infomaniak
  vs. Claude Opus split (confirmed present on this branch during planning —
  re-confirm with `test -f interview_theater/modellwailwahl.py` — fix typo,
  `interview_theater/modellwahl.py`).
- `gruppe.szene_usa_bestaetigt_am` is the consent column, asked once on
  entry to the phase now named "Rewrite" (phase 6) per `szene_claude.py`/
  AGENTS.md's "Der Prosa-Lauf startet nur aus einem Knopf" section — note
  that Task 12's automatic phase-6 entry from Phase 5 means the consent
  question will now appear automatically once Stage B finishes, which is
  worth one sentence in the README under "model choice" (the consent ask
  itself is unchanged code, just reached automatically now instead of only
  via a button/command).
- Telegram remains fully supported (`telegram.py`/`web_kanal.py` docstrings,
  confirmed during planning — "Telegram bleibt Plan B").
- `workshop/dortmund-2026/` and `workshop/padua-2026/` are the two existing
  profiles (confirmed via `ls workshop/`).

- [ ] **Step 2: Write the new README**

Structure, modeled on `/mnt/HC_Volume_106183673/projekte/cothinker/README.md`'s
shape (bold one-liner → short naming/purpose paragraph → ASCII data-path
diagram → "what it does today, in short" paragraph → sectioned detail with
links out to `docs/`/`AGENTS.md` → status → license/contributing-equivalent
closing), in English, similar length to CoThinker's (~170 lines):

```markdown
# interview-theater

**A chat bot that helps an amateur theatre group turn its own interviews
into a play** — it transcribes, condenses, remembers what the group
decides, and drafts scene text on request. The group always decides; the
bot never writes a scene, sets a phase, or makes a choice on its own.

The group interviews people in their own community, talks through what a
play could look like, and gets scene drafts and a judged full read-through
back — all from a chat window, on a phone, in or around a rehearsal room.

```
 Group's phones / laptop              One bot process per group
 ┌──────────────────────┐             ┌──────────────────────────────────┐
 │ Telegram group chat   │◄──────────►│ bot.py: long-poll loop            │
 │   -- or --            │             │  ablauf.py: one reply per turn    │
 │ Web chat (web_chat.py)│◄──SSE/poll─►│  erkenner.py: what changed?       │
 │  same phone, no app   │             │  phasen.py: which station?        │
 └──────────────────────┘             │      │                            │
                                       │      ▼                            │
 Interview audio ──never leaves────►  │ stt.py (Whisper, Switzerland)      │
 the group's own recording             │ llm.py (Kimi, Switzerland)         │
                                       │  -- Phase 4+, with consent --      │
                                       │ szene_claude.py (Opus, USA)        │
                                       │      │                             │
                                       │      ▼  sqlite3, WAL               │
                                       │ one shared file, repo.py-only SQL  │
                                       └──────────────┬─────────────────────┘
                                                       ▼
                                   web.py: dashboard · group page · script ·
                                   rehearsal view -- read-only except the
                                   group's own editable work state
```

**What it does today, in short:** a group works through seven phases —
collecting terms, writing interview questions, running interviews, inventing
a setting/characters/story, sharpening that story against what people
actually said and drafting it scene by scene as prose, rewriting it, and
choosing a stage form for each scene before a final read-through. Every
decision the group states in plain language gets picked up automatically
("Notiert: ...") — no form to fill in, no command required. The same
conversation works over Telegram or a plain web chat page; a read-only
dashboard, an editable group page, a script view and a printable rehearsal
view sit next to it. What the group invents in phase 4 ("Frame") is
deliberately built **without** the interview material in view, so the
group recognises its own authorship; the material comes back one phase
later and sharpens, never replaces, what was invented. Detail on every one
of these decisions — and the live incidents that led to them — lives in
`AGENTS.md`.

## The seven phases

1. **Terms** — take in and sort the term list collected in the room
2. **Questions** — turn the terms into interview questions, down to the
   ones the group will actually ask
3. **Interviews** — record interviews, get them transcribed and condensed
   with word-for-word quotes
4. **Frame** — invent setting, characters and story freely, without the
   interview material
5. **Prose Draft** — sharpen the invented story against checked interview
   passages, then get it drafted scene by scene as prose
6. **Rewrite** — revise the draft against feedback and a dramaturgy check
7. **Stage Version** — choose a performance form per scene, translate the
   draft into it, and read the finished script once as a whole

The group can jump between phases at any time by saying so; the bot never
switches phases on its own, only asks once when the material would allow
moving on (`phasen.py`, `AGENTS.md` "Der automatische Sprung ist verworfen").

## Two channels, one conversation

**Telegram** is the original channel and stays fully supported — a bot
account in a group chat, voice messages transcribed and echoed back
immediately. **The web chat** (`web_chat.py`, `web_vereint.py`) is a plain
browser page under the group's own link, with the same recognizer, the same
buttons, the same phase flow — useful where installing Telegram isn't an
option. Both run through the identical `bot.py` loop; only the channel
object (`telegram.Telegram` vs. `web_kanal.WebKanal`) differs.

The web page has four tabs: **Chat** (the conversation), **Arbeitsstand**
(the group's editable work state — setting, characters, story, scenes),
**Textbuch** (the script, read-only, with a rehearsal-friendly print view
and a role filter), and, during phase 4 only, **Bühne** (a live
brainstorming surface). A separate rehearsal view and a printable interview
guide live at their own links for sharing outside the chat.

## Workshop profiles

Nothing in this repository is tied to one workshop. Everything specific —
language, phase names and keywords, scene forms, framing text, target
group — lives in `workshop/<name>/` and is selected per bot process with
`IT_WORKSHOP=<name>`. Without the variable, a built-in default profile
reproduces exactly what the first workshop (Dortmund, German, September
2026) ran on. `workshop/padua-2026/` is the English-language profile for a
three-week workshop at the National Theatre of the Veneto Region's academy
in Padua — same phases, same mechanics, its own wording, and (for now) the
only profile running the two-stage Phase 5 flow described above
(`[prosa_entwurf] aktiv = true`). See `docs/workshop-profil-umbau-2026-09-06.md`
for how a profile is built and proven not to change the default's output.

## Model choice and privacy

Interview audio, transcripts and every condensation always stay on a Swiss
provider (Infomaniak, open models, no training on user data) — the module
that condenses interviews never even has a code path to anything else
(`interview_theater/modellwahl.py`). From phase 4 onward, with the
operator's switch and the group's explicit, once-asked consent
(`gruppe.szene_usa_bestaetigt_am`), scene text can be written by Claude
Opus over a US proxy instead, because the resulting text is measurably
better — the group is told in plain language what that means before it is
ever asked, and the question is never implied, repeated or assumed by the
conversational bot itself. No real name of a participant or an interviewee
ever reaches a model or a scene: the chat sees "Member 1", "Member 2";
interviewees are "Interview 1", "Interview 2"; characters are always
invented. Every quote attributed to an interview is checked, word for word,
against the actual transcript before it is allowed into a scene or a
summary (`zitat.py`) — an unverifiable quote is dropped, not kept with a
warning flag.

## Operating it

One Python process per group (`systemd` user units, never a manual start —
two manual starts of the same bot collide over Telegram's update offset).
A single, separate web process serves every group's pages. Audio,
transcripts and condensations for a group can be deleted completely and
permanently with `scripts/loeschen.py`; there is deliberately no delete
command in the chat itself. Full operating instructions, environment
variables and the (many, individually measured) operational pitfalls are
in `AGENTS.md`.

## Testing

`pytest` runs the whole suite offline, with fakes standing in for the
speech and language models — including a regression corpus of real and
synthetic conversation snippets that pins down what the intent recognizer
must and must not catch (`korpus/`, in German and English). Two further,
explicitly non-automatic tools cost real API calls: `scripts/pruefe_prompts.py`
re-runs that corpus against the live model after a prompt change, and
`scripts/simulation.py` plays a complete, multi-phase workshop against the
real models with invented participants, judged by a separate model that
never wrote the text it's judging. Neither runs in CI; both are documented
in `AGENTS.md`.

---

For the technical reference — module map, every bindingly-settled design
decision and the measured incident behind it, and the known rough edges —
see [AGENTS.md](AGENTS.md).
```

- [ ] **Step 3: Sanity-check length and no invented claims**

Run `wc -l README.md` — expect roughly 150–190 lines (CoThinker is 169;
stay in that ballpark per the card's instruction). Re-read the drafted file
once against the grep/read results from Step 1 and strike anything not
directly verified against the current code.

- [ ] **Step 4: No automated test covers README prose** — this task has no
pytest step. Run the full suite once anyway to confirm nothing else broke:

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Expected: green (README changes cannot affect this, but keep the habit of
checking per-task).

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
README: rewrite for the current seven-phase, two-channel, two-model reality

Removes the Telegram-only framing and the old phase 5/6/7 names; adds the
web channel, workshop profiles and the Kimi/Opus consent split, all
verified against the current code before writing.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Update the Mermaid flow-diagram data (`ablauf.json`) for phases 4–7

**Files:**
- Modify: `~/.hermes/profiles/birk/var/padua-ablauf-web/ablauf.json` (outside
  this git repository — a separate operational tool's data file)

**Interfaces:** none — JSON data for an external viewer, not consumed by
any code in this repository.

- [ ] **Step 1: Back up the current file**

Run:
```
cp ~/.hermes/profiles/birk/var/padua-ablauf-web/ablauf.json \
   ~/.hermes/profiles/birk/var/padua-ablauf-web/ablauf.json.vor-t_b87d075c
```
Confirm it landed next to the existing `ablauf.json.vor-*` backups (list the
directory first if the Bash tool allows it here — if the same Bash
permission restriction encountered during planning research applies, ask
the user/operator to run this one command, since it's outside the
sandboxed repo and may be blocked the same way).

- [ ] **Step 2: Read the current file in full**

Read `~/.hermes/profiles/birk/var/padua-ablauf-web/ablauf.json` completely
(608 lines per planning research) before editing — do not edit blind from
this plan's summary of its shape.

- [ ] **Step 3: Update phase 4's `name_de`/`name_en`**

Set `name_en` to `"Frame"` for the phase-4 object (`nummer: 4`). Leave
`name_de`, `intents`, `knoepfe`, and `voraussetzung_naechste` unchanged —
phase 4's behaviour is unchanged by this card.

- [ ] **Step 4: Update phase 5's `name_en` and describe the new two-stage flow**

Set `name_en` to `"Prose Draft"`. Add the new intent `"uebersicht_aendern"`
to its `intents` array (today empty, per planning research — this directly
resolves the flow-audit's B1-adjacent finding that phase 5 had no chat
intent at all). Add the new buttons to its `knoepfe` array:
`"uebersicht_passt"`, `"uebersicht_anders"` (Stage A), and describe Stage B
either as existing scene buttons reused (`"szene_passt"`,
`"szene_anders"`/whatever Stage B's buttons are literally named in
`knoepfe/texte.py` after Task 10/12 — use the real constant values, not
placeholders). Update `voraussetzung_naechste`: it's no longer a manual
choice — note in the JSON (as a text field, matching whatever field the
file uses for prose notes, e.g. `voraussetzung_quelle` or
`unverified_notiz`) that phase 5→6 now happens automatically once every
scene has a confirmed draft (Task 12), not via a group decision — this is
worth flagging in the diagram precisely because it's the one deliberate
exception to the "ask, don't jump" rule documented elsewhere in this file's
`meta` block if it has a general-principle note.

- [ ] **Step 5: Update phase 6 and 7's `name_en` only**

Phase 6: `name_en` = `"Rewrite"`. Phase 7: `name_en` = `"Stage Version"`.
No other field changes for phases 6/7 (their behaviour is out of scope for
this card, matching `AGENTS.md`'s explicit boundary).

- [ ] **Step 6: Validate the JSON**

Run: `python3.11 -c "import json; json.load(open('/home/birk/.hermes/profiles/birk/var/padua-ablauf-web/ablauf.json'))" && echo OK`
Expected: `OK`, no `JSONDecodeError`.

- [ ] **Step 7: Do NOT touch `server.py`, `index.html`, or `aenderungen.json`**
in that directory — confirmed out of scope by the card.

- [ ] **Step 8: No git commit** — this file lives outside the repository
(`~/.hermes/...`), so there is nothing to commit here. Note the backup
filename and the exact diff made in the final report instead.

---

## Task 17: Final full-suite verification and report assembly

**Files:** none modified.

- [ ] **Step 1: Run the complete test suite one last time**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider`
Record the exact final summary line verbatim (e.g. `5928 passed, 4 skipped
in 123.45s`) — compare the passed count against the Task 2/8 expected
increases (new parametrized cases + new test files) and account for the
difference explicitly, don't just eyeball "green".

- [ ] **Step 2: Re-run the two profile checkers**

Run: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m scripts.pruefe_profil --alle`
Expected: exit 0 for both `dortmund-2026` and `padua-2026`.

- [ ] **Step 3: Grep-confirm the acceptance criterion about old phase names**

Run:
```
grep -rn "\"Sharpening\"\|\"Scenes as Story\"\|\"Polish\"" workshop/padua-2026/ interview_theater/sprachen/en/ interview_theater/prompts/ tests/
```
Expected: the only remaining hits are inside `stichwoerter = [...]` arrays
in `phasen.toml` (legacy keyword aliases, not display names) and inside
`test_padua_stichwoerter_finden_die_phase`'s parametrize list (testing that
those aliases still resolve) — no hit should be a phase **name**/label/
header anywhere else.

- [ ] **Step 4: Assemble the final report**

Per the card's "Acceptance" section, the report must state: every file
changed (list per task, or `git diff --stat main...HEAD`), the final
commit SHAs on this branch (`git log --oneline main..HEAD`), the exact
pytest command and its final summary line, whether `scripts.pruefe_prompts`
ran (Task 14) and its cost if so, and explicit TODOs/open questions left
for the phase 6/7 follow-up card — at minimum: (a) the scope decision that
Stage A/B "Yes, save" confirmation is button-only, not chat-driven (see
"Deliberate scope decisions" above); (b) the per-scene cast-default
simplification (full cast on every auto-created scene); (c) that old
phase-6 ("Rewrite")'s existing one-shot `kurzgeschichte.py` entry flow is
now functionally redundant once a group completes Phase 5's Stage B (every
scene already has a prose draft by then) but was deliberately left
untouched per the card's phase 6/7 boundary — flag this explicitly as a
likely cleanup target for the follow-up card, not something this plan
silently papered over.

No commit for this task — it is a verification and reporting pass.
