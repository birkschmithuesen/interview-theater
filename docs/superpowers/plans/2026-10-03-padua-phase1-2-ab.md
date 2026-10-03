# Plan: Padua Phase 1+2 — Diskussion mitschneiden + A/B Fragen (t_98928a4e)

No pre-approved spec doc existed for this card (`--no-plan`); this file is the
plan derived from the Kanban card text + `AB-AENDERUNG-PHASE2.md` + codebase
research, written so `subagent-driven-development` tooling (`task-brief`,
`review-package`) can run against it. It is NOT a request for sign-off before
execution — the card explicitly authorized deriving tasks and proceeding.

## Key design decision (not explicit in the card, made here, flag in final report)

**All new Phase 1/2 behavior is gated behind two new workshop-profile flags**,
`workshop.diskussion_aktiv()` and `workshop.fragen_ab_aktiv()`, mirroring the
existing `workshop.prosa_entwurf_aktiv()` pattern (`[prosa_entwurf] aktiv` in
`profil.toml`, vorgabe `False`). Reason: `tests/test_profil_bitgleich.py`
requires the built-in default profile (== `workshop/dortmund-2026/`) to keep
producing byte-identical prompts forever. This card's changes are a
fundamental rework of Phase 1+2 conversation flow — without a flag, every
profile (including Dortmund, which has live/former groups) would get new
behavior, silently breaking that guarantee or at best violating its spirit.
Padua's `profil.toml` sets both flags `true`; the shipped default profile and
`dortmund-2026/` do not set them, so `aktiv()` returns `False` and nothing
about Dortmund's behavior changes — same contract as `[laengen]`/`[prosa_entwurf]`.

The **model-routing change** (`modellwahl.konversation_ueber_claude`) and the
**consent-ask-moves-to-phase-1** change are left **ungated** (global): they
are explicit, general Birk decisions ("Phase 1 (Diskussionsverdichtung) +
Phase 2 ... Phase 3 Interviews ... bleibt UNBEDINGT Kimi" — stated without
workshop qualification), and moving *when* the consent question fires cannot
retroactively affect a group that already passed Phase 1 before this deploys.

The **Phase 2 prompt content differences** (own-questions-first instructions)
go into a **profile override file** `workshop/padua-2026/prompts/phasen/2.md`
(the documented override mechanism — a same-named file in the profile beats
the repo file) rather than editing the shared `interview_theater/prompts/phasen/2.md`.
Dortmund's prompt file is therefore untouched. The Python-side new mechanics
specific to the A/B flow (background KI-question job, the "Our questions
done" button) are still gated by `workshop.fragen_ab_aktiv()` in Python,
since they are behavioral/UI changes, not just text.

## Global Constraints

- Repo root for all tasks: `/mnt/HC_Volume_106183673/projekte/interview-theater/.worktrees/t_98928a4e`.
  Branch stays `wt/t_98928a4e`. Never touch `betrieb/`. Never `git push`.
- Do not change the content/behavior of Phases 3, 4, 5, 6, 7 (only additive,
  structurally-unreachable-for-them code is allowed, e.g. a new DB column or
  a new module nothing calls for those phases).
- Every DB schema change is additive: new columns via the existing
  `_migriere_fehlende_spalten` list (mirror how `brainstorm`/`schnittgrund`
  were added to `aufnahme`/`web_post`) and `CREATE TABLE IF NOT EXISTS` for
  new tables, added to `db.TABELLEN_MIT_CHAT_ID`. Never alter an existing
  column or rewrite an existing migration.
- All SQL lives only in `repo.py`/`db.py` (never in `aufnahme.py`,
  `web_chat.py`, `diskussion.py`, `fragen_ki.py`, etc. — those call `repo.*`).
- Every new user-facing text constant needs a German default (plain Python
  module constant, used via `T = sprache.Texte(__name__)` i.e. `T._TEXT_X`)
  **and** a matching entry in `interview_theater/sprachen/en/texte.toml`
  under that module's section key, with the same `{placeholder}` tokens as
  the German string (see `sprache.platzhalter`/the symmetry test for the
  module in question — usually `tests/test_sprache_bitgleich.py` or a
  per-module variant; check for it and keep it green).
- Every new prompt `.md` file needs a DE file under
  `interview_theater/prompts/...` (or, when it must ONLY exist for Padua, as
  a profile override under `workshop/padua-2026/prompts/...` with NO base
  file — that is a valid and used pattern, e.g. workshop-only prompt
  additions) and, when there IS a base file, an EN mirror at
  `interview_theater/sprachen/en/prompts/<same path>`.
- No model call inside a button/knopf handler (Zusage 2, binding convention
  in this repo) — anything needing a model call goes to
  `threading.Thread(target=..., daemon=True).start()`, same as every
  existing background job (`buehnenkarte`, `phasen_debrief`-style modules,
  `schaerfung`, etc.).
- New buttons: `callback_data` stays `k:<id>` via `repo.lege_knopf_an` /
  `knoepfe.basis._daten` — never put a value directly in `callback_data`.
- New web UI elements get a `data-*` marker for the parallel UX card:
  `data-discussion-done="1"` on the Phase-1 "Discussion done" button,
  `data-own-questions-done="1"` on the Phase-2 "Our questions are done"
  button. Per-question origin labels ("yours"/"AI") stay **plain chat text**
  — do not add `data-term-source` spans inside chat bubble HTML: bubble
  content passes through `web_chat.sichere_html`'s fixed tag allowlist
  (`b i u s code pre blockquote a`), and extending that allowlist is a
  security-relevant change out of scope here (flag it, don't do it).
- Run each task's own new/changed tests (`pytest tests/test_X.py -q
  tests/test_Y.py -q ...`) before calling a task done. The one full-suite run
  happens once, in the background, near the end (see Task 20).
- Never run `scripts/pruefe_prompts.py` or `scripts/simulation.py` reflexively
  — they cost real money. Only run the former if `prompts/erkenner.md` (DE or
  EN) ends up touched (this plan is designed so it should NOT need to be —
  flag it in the final report if a task discovers otherwise instead of
  silently running/skipping the check).
- Every commit message ends with:
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`
- Use `PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`
  for all test/python invocations (no `.venv` in this worktree).

---

## Task 0: Workshop profile flags `diskussion_aktiv()` / `fragen_ab_aktiv()`

Add two functions to `interview_theater/workshop.py`, directly modeled on the
existing `prosa_entwurf_aktiv()` (read it first — it's ~10 lines):

```python
def diskussion_aktiv(profil: Profil | None = None) -> bool:
    """Ob Phase 1 die Hintergrund-Diskussionsaufnahme faehrt (Padua Phase
    1+2 Umbau, 03.10.2026) [...]. Vorgabe false -- wie [laengen] aktiv:
    ohne diese Zeile im Profil bleibt Phase 1 genau das, was sie vorher war.
    Dortmund setzt die Zeile nicht und bleibt unberuehrt."""
    profil = profil or aktiv()
    return bool(profil.wert("diskussion.aktiv", False))


def fragen_ab_aktiv(profil: Profil | None = None) -> bool:
    """Ob Phase 2 den A/B-Vergleich eigene-vs-KI-Fragen faehrt [...].
    Vorgabe false [...]. Dortmund setzt die Zeile nicht und bleibt
    unberuehrt."""
    profil = profil or aktiv()
    return bool(profil.wert("fragen_ab.aktiv", False))
```

Add to `workshop/padua-2026/profil.toml` (append near `[prosa_entwurf]`):

```toml
[diskussion]
aktiv = true

[fragen_ab]
aktiv = true
```

Do NOT add these sections to any other profile file (default/Dortmund stay
without them — that's the point).

**Tests (TDD):** a test module (new or appended to an existing
`tests/test_workshop*.py`) asserting: default/Vorgabeprofil → both functions
`False`; a `Profil` built from a dict containing `diskussion.aktiv=true` /
`fragen_ab.aktiv=true` → `True`; `workshop/padua-2026/profil.toml` loaded for
real → both `True`; `workshop/dortmund-2026/profil.toml` loaded for real →
both `False`.

**Also run:** `pytest tests/test_profil_bitgleich.py -q` and
`python -m scripts.pruefe_profil dortmund-2026` /
`python -m scripts.pruefe_profil padua-2026` (both must stay green — this is
the whole point of Task 0, verify it before moving on).

---

## Task 1: Model consent moves to Phase 1 entry + routing rule update

Files: `interview_theater/knoepfe/stationen.py`, `interview_theater/modellwahl.py`,
`docs/entscheidung-modellwahl-2026-10-02.md`, plus whatever test files already
cover `modellwahl.konversation_ueber_claude` and `eintritt_in_phase`'s
Phase-4 consent block (search `tests/` for `konversation_ueber_claude` and
for `angebot_faellig`/`ART_SZENE_USA` inside a phase-entry test).

This task is **ungated** (applies to every profile) — see "Key design
decision" above for why that's safe.

1. In `interview_theater/knoepfe/stationen.py::eintritt_in_phase`: move the
   existing
   ```python
   if nummer == PHASE_SETTING:
       ...
       if szene_claude.angebot_faellig(e, conn, chat_id):
           repo.merke_szene_usa_angeboten(conn, chat_id)
           tg.sende(chat_id, T._TEXT_ANGEBOT_MODELLWAHL)
           biete_szene_usa(conn, tg, chat_id)
   ```
   block so it ALSO (new, not instead-of) fires on `nummer == PHASE_BEGRIFFE`,
   **before** the existing Begriffe-kickoff block
   (`if nummer == PHASE_BEGRIFFE and klm is not None: ... _starte_auftrag(...)
   return`). Keep the existing `PHASE_SETTING` block completely unchanged
   (it becomes a no-op safety net in practice once Phase 1 already asked,
   exactly like the existing `PHASE_SZENEN` block already is one) — do not
   delete it, do not restructure it, just make sure Phase 1 entry executes
   an equivalent check-and-ask first. Concretely: extract the
   check-and-ask into a small local helper (e.g.
   `_biete_modellwahl_wenn_faellig(conn, tg, e, chat_id)`) and call it from
   both the `PHASE_BEGRIFFE` and `PHASE_SETTING` branches, rather than
   duplicating the four lines verbatim — this file already favors small
   local helpers, follow that style.
2. In `interview_theater/modellwahl.py::konversation_ueber_claude`: change
   ```python
   return phasen.aktuelle(conn, chat_id) >= PHASE_SETTING
   ```
   to
   ```python
   return phasen.aktuelle(conn, chat_id) != PHASE_INTERVIEWS
   ```
   Import `PHASE_INTERVIEWS` alongside the existing `PHASE_SETTING` import
   from `interview_theater.knoepfe.texte` (check whether `PHASE_SETTING` is
   still referenced anywhere else in the file after this change — if not,
   remove the now-unused import rather than leaving dead code). Update the
   function's docstring and the module's top-of-file docstring to state the
   new rule plainly: Phase 1, 2, 4, 5, 6, 7 → Opus-after-consent; Phase 3
   (interviews) → always Kimi, regardless of consent, no exception. Do not
   change the Phase-3-interviews-and-every-interview-digestion-stays-Kimi
   guarantee itself (`verdichter.py` still never imports this module —
   don't change that).
3. Append (do not rewrite) a new dated section to
   `docs/entscheidung-modellwahl-2026-10-02.md`:
   `## Nachtrag 2026-10-03 (Padua Phase 1+2 Karte)` describing: the consent
   question now fires at Phase 1 entry instead of the 3→4 transition (same
   column `gruppe.szene_usa_bestaetigt_am`, same button `ART_SZENE_USA` /
   `biete_szene_usa`, no second question); `konversation_ueber_claude` now
   excludes only `PHASE_INTERVIEWS` instead of requiring `>= PHASE_SETTING`,
   so Phase 1's discussion-digest and Phase 2's question-formulation/KI-
   generation calls are eligible for Opus after consent; Phase 3 interviews
   and their digestion remain unconditionally Kimi (unchanged mechanism:
   `verdichter.py` never calls `modellwahl`).

**Tests (TDD):**
- `konversation_ueber_claude`: returns `True` for phase 1, 2, 4, 5, 6, 7 when
  `szene_claude.ist_aktiv` is `True`; `False` for phase 3 regardless; `False`
  everywhere when `ist_aktiv` is `False` (no consent / switch off).
- `eintritt_in_phase` phase-1 entry: with `angebot_faellig` True, the consent
  text + `biete_szene_usa` buttons are sent; with it already answered/offered
  (False), nothing extra is sent and the Begriffe-kickoff still runs. A
  follow-up entry into Phase 4 afterward does NOT ask again.

Run: `pytest tests/test_modellwahl.py -q` plus whichever stationen/knoepfe
test file covers `eintritt_in_phase`'s Phase-4 consent block today (find it
with `grep -rl angebot_faellig tests/`).

---

## Task 2: DB schema — `aufnahme.diskussion` / `web_post.diskussion` columns + repo plumbing

Mirror the existing `brainstorm` column *exactly* (same additive-migration
mechanics, same `INTEGER NOT NULL DEFAULT 0`), for both tables. This task is
pure plumbing and is safe to leave **unconditional** (no profile check): a
column nobody ever sets to 1 is inert.

Files: `interview_theater/db.py`, `interview_theater/repo.py`, plus whichever
test files cover `lege_aufnahme_an`/`lege_web_post_an` and the `aufnahme`
table schema (e.g. `tests/test_repo.py`, `tests/test_db.py`,
`tests/test_repo_brainstorm.py` as a pattern reference).

1. `db.py`: add `diskussion INTEGER NOT NULL DEFAULT 0` to the `aufnahme`
   `CREATE TABLE` (right after the existing `brainstorm` column, with a
   comment explaining it parallels `brainstorm` but for Phase 1's plain
   background-listening mode: no CoThinker, no reaction decision, no
   Gespraechszug — just an echo bubble, with a single one-shot digest
   triggered elsewhere on `schnittgrund='ende'`, see `diskussion.py` later).
   Add the same column to `web_post`'s `CREATE TABLE`, mirroring its
   `brainstorm` column and comment. Add `diskussion` to BOTH tables'
   entries in whatever structure lists columns for
   `_migriere_fehlende_spalten` (search for where `"brainstorm"` appears in
   that migration list/dict and add `"diskussion"` next to it, same type/
   default, for both `aufnahme` and `web_post`).
2. `repo.py`:
   - `lege_aufnahme_an(...)` gains `diskussion: bool = False`, included in
     the `INSERT` exactly like the existing `brainstorm` parameter (same
     `1 if diskussion else 0` idiom, same position convention — look at how
     `brainstorm` is threaded through the function signature, the INSERT
     column list, and the INSERT values tuple, and do the same for
     `diskussion`).
   - `lege_web_post_an(...)` gains `diskussion: bool = False`, same
     treatment mirroring its `brainstorm` parameter.
   - New function `diskussion_transkript(conn: sqlite3.Connection, chat_id: int) -> str`:
     concatenates (with blank-line separators, same style as
     `brainstorm_transkript`) the `transkript` of every `aufnahme` row where
     `chat_id = ?  AND diskussion = 1 AND entfernt_am IS NULL AND status = 'fertig'`,
     ordered by `id`. Unlike `brainstorm_transkript`, there is no
     "markierung" filter — Phase 1's digest wants the WHOLE discussion, not
     "since the last card" (there is no "last card" concept here).

**Tests (TDD):** round-trip tests for `lege_aufnahme_an(..., diskussion=True)`
and `lege_web_post_an(..., diskussion=True)` (assert the column reads back
as `1`/truthy); `diskussion_transkript` test with 3+ rows (some
`entfernt_am` set, one `status != 'fertig'`, one `diskussion=0`) asserting
only the right rows are included, in `id` order, joined with blank lines.

Run: the specific new/changed test file(s) plus `pytest tests/test_db.py -q`
if that file asserts on the full schema text.

---

## Task 3: aufnahme.py — diskussion dispatch branch (no CoThinker, no Gespraechszug)

Files: `interview_theater/aufnahme.py`, a new test file
`tests/test_aufnahme_diskussion.py` (model it directly on
`tests/test_brainstorm.py`/the brainstorm dispatch tests in
`tests/test_aufnahme.py`, whichever covers `_brainstorm_abschliessen`).

1. `empfange()`: pass `diskussion=bool(n.get("diskussion"))` to
   `repo.lege_aufnahme_an(...)`, same line/position as the existing
   `brainstorm=bool(n.get("brainstorm"))` argument.
2. In `_kurz_abschliessen`, add a new branch **before** the existing
   `if row["brainstorm"]:` check:
   ```python
   if row["diskussion"]:
       _diskussion_abschliessen(conn, tg, klm, e, row)
       return
   ```
3. New function `_diskussion_abschliessen(conn, tg, klm, e, row) -> None`:
   - `repo.setze_status(conn, row["id"], "fertig")`
   - `_web_sprachblase(conn, row["chat_id"], row["message_id"], row["transkript"] or None)`
     — the transcript echo bubble, same helper/call shape as
     `_brainstorm_abschliessen` uses.
   - **Nothing else in this task** — no `brainstorm.soll_reagieren` call, no
     `_starte_buehnenkarte`, no `zug(...)`, no Absichtserkenner run. Write a
     clear docstring stating this is Phase 1's "nur zuhoeren" mode: segments
     are pure material, never a conversational turn, and the one-shot digest
     + "now send me your five terms" message are triggered separately (by
     the `schnittgrund == 'ende'` case specifically — **that trigger is
     Task 6's job, not this task's**; this task's function stays a plain
     echo-only leaf so Task 6 can add exactly one more call to it without
     restructuring).

**Tests (TDD):** a `diskussion=1` row reaching `_kurz_abschliessen` does NOT
call `zug`, does NOT touch `brainstorm.soll_reagieren`/`_starte_buehnenkarte`
(use a spy/mock asserting zero calls), DOES call `_web_sprachblase` with the
transcript, and DOES set status to `fertig`. A `brainstorm=1` row's existing
behavior is unchanged (regression check — run the existing brainstorm tests
too). A plain `kurz` row (neither flag) still triggers `zug` as before.

Run: `pytest tests/test_aufnahme_diskussion.py tests/test_aufnahme.py tests/test_brainstorm.py -q`
(adjust filenames to what actually exists after Explore).

---

## Task 4: web_daten.py + repo/web_kanal plumbing for the `diskussion` flag (server side, no UI yet)

This task wires the **gated** surface: `diskussion_knopf` is only ever `True`
for a Padua-style profile. Files: `interview_theater/web_daten.py`,
`interview_theater/web_kanal.py` (the brainstorm-flag passthrough into the
Telegram-shaped update dict — mirror it exactly for `diskussion`), relevant
tests (`tests/test_web_daten*.py`, `tests/test_web_kanal*.py`).

1. `web_daten.web_chatzustand`: add
   ```python
   "diskussion_knopf": (
       _feld(stand, "phase") == 1 and workshop.diskussion_aktiv()
   ),
   ```
   (import `workshop` the same lazy/late way `phasen` is imported a few
   lines above in this function, to match the existing "repo-frei, pure"
   style of this read path — check how `phasen` is imported there and mirror
   it for `workshop`).
2. `web_kanal.py`: wherever the brainstorm boolean is copied from the
   `web_post` row into the synthesized Telegram-shaped update dict (same
   place `schnittgrund`/`mime` are copied, per the `brainstorm` comment in
   `db.py` around the `web_post` schema), add the identical copy for
   `diskussion`.

**Tests:** `web_chatzustand` returns `diskussion_knopf: True` only when
phase==1 **and** the active profile has `diskussion.aktiv=true` (use the
existing test fixture/monkeypatch pattern this test file already uses for
`workshop.aktiv()` or profile selection — check how other profile-gated
fields, e.g. anything touching `prosa_entwurf_aktiv`, are tested in this
suite, if any precedent exists; otherwise monkeypatch
`workshop.diskussion_aktiv` directly, which is simpler and is an accepted
pattern elsewhere in this codebase for profile-flag tests). `web_kanal`
passthrough test mirroring the existing brainstorm passthrough test.

Run: the specific test files above.

---

## Task 5: web_chat.py — server-side `#diskussion` button/markup + `_audio` passthrough + EN texts

Files: `interview_theater/web_chat.py`, `interview_theater/sprachen/en/texte.toml`.

1. New German text constants in `web_chat.py` (place near the existing
   `_TEXT_BRAINSTORM_*` constants):
   ```python
   _TEXT_DISKUSSION_AN = "Zuhoeren starten"
   _TEXT_DISKUSSION_LAEUFT = "Hoert zu ({zeit})"
   _TEXT_DISKUSSION_FERTIG_KNOPF = "Diskussion fertig"
   ```
   (Reuse the existing `_TEXT_INTERVIEW_PAUSE`/`_TEXT_INTERVIEW_WEITER` for
   the pause/resume labels inside the diskussion-aktionen block — don't
   invent new German strings for those two, minimal diff.)
2. In `chat_koerper()`: add a `diskussion_erlaubt = daten.get("diskussion_knopf", False)`
   (note: default `False`, unlike `brainstorm_erlaubt`'s default `True` —
   this feature must stay invisible unless the server explicitly says so,
   since most profiles never send this key at all... actually re-check: does
   `web_chatzustand` ALWAYS include the key now per Task 4? If yes, default
   value here is moot but keep it `False` defensively, matching "invisible
   unless explicitly enabled" rather than `True`-by-default like brainstorm).
   Render a new button block modeled 1:1 on the existing
   `#brainstorm`/`#brainstorm-aktionen` block (same structure: a toggle
   button `id="diskussion"` with `data-laeuft`/`data-pausiert`, hidden via
   the `hidden` attribute when not `diskussion_erlaubt`, plus
   `#diskussion-aktionen` containing `#diskussion-pause` and
   `#diskussion-beenden`). Put `data-discussion-done="1"` as a static
   attribute directly on the `#diskussion-beenden` button element (not on
   the toggle button) — it is literally the "Discussion done" action.
   Decide placement (before or after the `#brainstorm` block) by what reads
   cleanest; they will never both be visible for the same group in practice
   (one profile flag gates one phase, the other gates another phase) but
   nothing stops both existing in the markup.
3. `_audio()` POST handler: read
   `diskussion = (felder.get("diskussion") or [""])[0] == "1"`
   right next to the existing `brainstorm = ...` line, and pass
   `diskussion=diskussion` to `repo.lege_web_post_an(...)` alongside the
   existing `brainstorm=brainstorm` argument.
4. Add EN entries to `interview_theater/sprachen/en/texte.toml` under the
   `web_chat` module section for every new `_TEXT_*` constant from step 1
   (English wording, e.g. "Start listening", "Listening ({zeit})",
   "Discussion done" — keep the `{zeit}` placeholder identical).

**Tests:** extend whatever test currently renders `chat_koerper()` and
asserts on the brainstorm markup (e.g. `tests/test_web_chat_brainstorm_knopf.py`)
with an analogous test file/cases for `diskussion_knopf` — button hidden by
default, visible+rendered correctly when `diskussion_knopf=True`, carries
`data-discussion-done="1"` on the beenden button and not on the toggle
button. A test for `_audio()` forwarding `diskussion=1` to
`repo.lege_web_post_an` (mirror the existing brainstorm-forwarding test in
`tests/test_web_chat_audio.py`). An EN-table symmetry test run
(`pytest tests/test_sprache_bitgleich.py -q` or whatever enforces
placeholder/key symmetry — run it, must stay green).

---

## Task 6: web_chat.py — client-side JS for the diskussion session lifecycle

Files: `interview_theater/web_chat.py` (the `_CHAT_JS` template string
region only).

Add, mirroring `starteBrainstorm`/`pausiereBrainstorm`/`fortsetzeBrainstorm`/
`beendeBrainstorm` **1:1** (same session-object shape, same guard order, same
mic-acquire/release calls) but targeting new DOM ids `#diskussion`,
`#diskussion-pause`, `#diskussion-beenden`, a new state slot
`zustand.diskussion` (not reusing `zustand.brainstorm`), and function names
`starteDiskussion`/`pausiereDiskussion`/`fortsetzeDiskussion`/`beendeDiskussion`/
`zeigeDiskussionModus`. Specifically:

- `zustand.diskussionErlaubt` set from `daten.diskussion_knopf` in the same
  poll-merge spot where `zustand.brainstormErlaubt` is set from
  `daten.brainstorm_knopf`.
- `postAudio(auftrag, zweiter)`: add
  `if (auftrag.sitzung && auftrag.sitzung.art === 'diskussion') { weg_ += '&diskussion=1'; }`
  right next to the existing brainstorm line.
- `bereit(auftrag)`: add
  `if (sitzung.art === 'diskussion') { return true; }` right next to the
  existing brainstorm case (diskussion segments are always ready to upload,
  same reasoning as brainstorm: no server mode-handshake needed).
- Session object for `starteDiskussion()` uses `art: 'diskussion'` and
  `fertigEingereiht: true` (same as brainstorm — there's no mode command to
  wait for).
- Event listeners for `#diskussion`, `#diskussion-pause`,
  `#diskussion-beenden` wired the same way the brainstorm ones are, at the
  same place in the listener-registration block.
- `zeigeDiskussionModus()` updates button labels/visibility/hidden state the
  same way `zeigeBrainstormModus()` does, using `_TEXT_DISKUSSION_AN`/
  `_TEXT_DISKUSSION_LAEUFT`/`_TEXT_DISKUSSION_FERTIG_KNOPF` (passed into the
  JS template the same way the brainstorm texts are, via the `TEXT` object
  built in `chat_html`/wherever `brainstorm_an=T._TEXT_BRAINSTORM_AN` etc.
  are assembled).

**Tests:** mirror whatever `tests/test_web_chat_js.py` already asserts for
the brainstorm functions (existence of the new function names in the
rendered JS, any structural/regex invariants that file checks for
brainstorm — e.g. no slide-to-lock gesture, mutually-exclusive session
guards). The deeper functional check is the e2e test in Task 10 — this
task's unit test only needs to prove the JS text is well-formed and present,
not that a browser runs it correctly.

---

## Task 7: New module `diskussion.py` — the one-shot digest job + DB table

Files: `interview_theater/diskussion.py` (new), `interview_theater/db.py`
(new table), `interview_theater/repo.py` (two new functions), new prompt
pair `interview_theater/prompts/diskussion_verdichtung.md` (DE) +
`interview_theater/sprachen/en/prompts/diskussion_verdichtung.md` (EN),
`interview_theater/aufnahme.py` (one new call site inside
`_diskussion_abschliessen` from Task 3).

1. `db.py`: new table
   ```sql
   CREATE TABLE IF NOT EXISTS diskussion_verdichtung (
     id          INTEGER PRIMARY KEY,
     chat_id     INTEGER NOT NULL,
     text        TEXT NOT NULL,
     erstellt_am TEXT NOT NULL,
     modell      TEXT,
     UNIQUE (chat_id)
   );
   ```
   Add `"diskussion_verdichtung"` to `db.TABELLEN_MIT_CHAT_ID` (the delete-a-
   group list) — read that list first and add it in alphabetical/logical
   position matching the surrounding style.
2. `repo.py`:
   - `merke_diskussion_verdichtung(conn, chat_id: int, text: str, modell: str | None) -> None`:
     upsert via `ON CONFLICT(chat_id) DO UPDATE SET text=excluded.text,
     erstellt_am=excluded.erstellt_am, modell=excluded.modell` (same idiom as
     any existing single-row-per-chat upsert in this file, e.g.
     `markiere_brainstorm_reaktion`).
   - `diskussion_verdichtung_text(conn, chat_id: int) -> str | None`:
     `SELECT text FROM diskussion_verdichtung WHERE chat_id = ?` → the text
     or `None`.
3. `interview_theater/diskussion.py` (new module), structure:
   - `SCHEMA = {"type": "object", "additionalProperties": False, "required": ["antwort"], "properties": {"antwort": {"type": "string"}}}`
   - `ART = "diskussion_verdichtung"`
   - A one-run-per-group lock, copied verbatim in shape from
     `interview_theater/brainstorm.py`'s `_LAEUFT_LOCK`/`_LAEUFT`/
     `versuche_start(chat_id)`/`beende(chat_id)` (read that file first, it's
     ~100 lines — this is the mechanism that guarantees "genau einmal" even
     under a double-trigger race).
   - `_nutzertext(transkript: str) -> str`: builds the isolated user text —
     just the raw diskussion transcript plus whatever minimal framing the
     prompt needs (NOT `kontext.baue`, no DB reads beyond the transcript
     itself — this call must not see any other conversation state).
   - Reuse the existing quote-verification idiom: for each `"..."`-quoted
     span in the model's answer, verify with `zitat.pruefe(zitat, korpus)`
     where `korpus` is the raw transcript; drop any line whose quote(s)
     don't verify; treat a case/whitespace-insensitive `"nichts"`/`"none"`
     answer as empty. Write this filter function locally in `diskussion.py`
     (don't try to import a private helper from an unrelated module — there
     is no existing shared helper for this in the current codebase state of
     this worktree; keep it self-contained, it's ~15 lines).
   - `starte(conn, klm, e, chat_id: int) -> None`: no-op if `klm is None`; no-op
     if `not workshop.diskussion_aktiv()` (defensive — in practice this is
     only ever called from a code path that already implies the flag was
     on, but the module should not trust that and should check for itself,
     since a background thread outliving a profile/config change is a real
     possibility in long-running processes); acquire the lock
     (`versuche_start`, return if already running); read
     `transkript = repo.diskussion_transkript(conn, chat_id)`; if blank,
     release the lock and return (no model call on empty material — don't
     invent an arbitrary minimum-length threshold beyond "non-empty", that
     number isn't specified anywhere and shouldn't be guessed); else spawn
     a daemon thread that: builds the nutzertext, computes
     `ueber_claude = modellwahl.konversation_ueber_claude(e, conn, chat_id)`,
     calls
     `modellwahl.aufruf_schema(conn, klm, e, chat_id, system=anweisungen.hole("diskussion_verdichtung"), nutzer=nutzertext, schema=SCHEMA, art=ART, ueber_claude=ueber_claude)`,
     filters the answer, and on a non-empty filtered result calls
     `repo.merke_diskussion_verdichtung(conn, chat_id, text, "claude" if ueber_claude else "sovereign")`;
     wrap the whole thread body in `try/except Exception: log.exception(...)`
     plus a best-effort `repo.merke_vorfall(conn, chat_id,
     getattr(e, "bot_name", None), "diskussion_verdichtung_fehler", ...)` on
     failure (mirror the error-handling shape used elsewhere for background
     jobs, e.g. `_starte_buehnenkarte`'s `_lauf`); always `finally: beende(chat_id)`.
4. Prompt files (DE then EN mirror, identical structure/instructions,
   English wording in the EN one): read the full discussion transcript;
   extract what is useful for Phase 2 (question development) and Phase 4+
   (story development): themes, positions, conflicts, images, anecdotes,
   open questions; every statement needs a short verbatim quote from the
   transcript or it must be dropped — never invent; answer exactly `NICHTS`
   (DE) / `NOTHING` (EN) if the discussion yields nothing usable; cap the
   answer at roughly 150 words (an explicit, checkable budget, mirrored in
   both language files); never describe or name individual speakers, only
   the group's discussion as a whole (same privacy stance as the existing
   `phasen_debrief`-pattern prompts elsewhere in this repo's conventions —
   check `prompts/` for a comparable existing prompt, e.g. `verdichter.md`,
   for house style/tone before writing the new one).
5. In `interview_theater/aufnahme.py::_diskussion_abschliessen` (Task 3's
   function), add: if `row["schnittgrund"] == "ende"`:
   - send the deterministic "now write me your five terms" chat message
     (new `T._TEXT_DISKUSSION_FERTIG_BEGRIFFE` constant — German default +
     EN table entry; this message only needs to be gated by the fact that
     `diskussion=1, schnittgrund='ende'` rows only ever exist when the
     feature was active, so no extra `workshop.diskussion_aktiv()` check
     needed here, though `diskussion.starte` below checks it anyway) via
     `tg.sende(chat_id, ...)`, **then**
   - `from interview_theater import diskussion` (local import, same style as
     the rest of this module's cross-module calls) and
     `diskussion.starte(conn, klm, e, row["chat_id"])`.
   Order matters: the chat message goes out first (synchronously), the
   digest starts after (asynchronously, non-blocking) — matches the card
   text ("Mitschnitt endet -> danach fordert der Bot auf", with the
   digest explicitly "NICHT blockierend fuer den Chat").

**Tests (TDD — these map directly to the card's explicit acceptance
criteria, do not skip any):**
- "Verdichtung laeuft GENAU EINMAL am Ende, kein doppelter Lauf bei
  Doppelklick o.ae.": call `diskussion.starte` twice back-to-back (or from
  two threads) for the same `chat_id` with a `klm` double that counts calls
  to `.schema`; assert exactly one call happened (the lock does this — but
  write the test as a black-box behavioral assertion, not an assertion on
  the lock's internals).
- Quote filtering: a model answer containing one verifiable and one
  fabricated quote results in only the verifiable line surviving (reuse the
  exact test style of any existing quote-filter test in this repo, e.g.
  `tests/test_zitat.py` combined with however `verdichter`'s own filter is
  tested).
- `klm is None` → no-op, no exception, no DB write.
- Blank transcript → no model call, no DB write.
- `workshop.diskussion_aktiv() == False` → `starte` is a no-op even if
  called directly (defensive check from the module itself).
- `_diskussion_abschliessen` with `schnittgrund='ende'` sends the five-terms
  message AND calls `diskussion.starte` exactly once; with
  `schnittgrund` anything else, neither happens.

Run: `pytest tests/test_diskussion.py tests/test_aufnahme_diskussion.py -q`
(new test file name your call, follow existing naming conventions, e.g.
`tests/test_diskussion.py`).

---

## Task 8: kontext.py — diskussion context block + gated Phase-1 welcome text

Files: `interview_theater/kontext.py`, `interview_theater/sprachen/en/texte.toml`,
`tests/test_kontext.py` (or wherever the `_bloecke`/budget tests live).

1. New budget entry in `BUDGETS` (append, don't reorder existing keys):
   `"diskussion": 800,` with a short comment explaining it parallels
   `"festlegungen"`'s cap-and-drop-wholesale treatment. Add `"diskussion"`
   to `_REIHENFOLGE` (pick a sensible position — right after
   `"festlegungen"` reads naturally: diskussion-derived material is
   contextually similar in weight/role to a festlegung).
2. New German text constant `DISKUSSION_KOPF = "Aus eurer Begriffs-Diskussion:"`
   plus an EN entry in `sprachen/en/texte.toml` ("From your term
   discussion:").
3. New function, following the exact `_baue_figurenhinweis`/similar
   data-gated pattern already in this file (early-return `""` the moment
   any precondition is unmet):
   ```python
   def _baue_diskussion_block(conn, chat_id: int) -> str:
       text = repo.diskussion_verdichtung_text(conn, chat_id)
       if not text:
           return ""
       return f"{T.DISKUSSION_KOPF}\n\n{text}"
   ```
   Wire it into `_bloecke()`'s returned dict as `"diskussion": _baue_diskussion_block(conn, chat_id)`.
   Wire it into whatever the trim-ladder (`_kuerze_auf_budget`) does with
   similarly-sized auxiliary blocks today (check how `"festlegungen"` or
   `"figurenhinweis"` is dropped when over budget — likely "drop this block
   wholesale rather than partially" — and do the same for `"diskussion"`;
   read `_kuerze_auf_budget`'s current body first, don't guess its shape).
4. **Gated Phase-1 welcome-text fork** (the Dortmund-safety-critical part):
   in `kontext.py`, leave `ERSTKONTAKT`, `ERSTKONTAKT_ANLASS_ERSTE`,
   `ERSTKONTAKT_ANLASS_RUECKKEHR` **byte-for-byte untouched**. Add a new,
   separate instruction constant (German default) describing the
   discussion-listening Phase-1 flow instead of "ask for begriffe
   immediately" — content: explain roles/workflow same as today's opening,
   but close by explaining that the group should lay the phone in the
   middle and discuss which terms matter to them, that the bot only
   listens and says nothing until they press "Discussion done" below, and
   that a "Start listening" button appears under this message — do **not**
   ask for the five terms in this message (that happens after "Discussion
   done" is pressed, per Task 7). Name it clearly, e.g.
   `ERSTKONTAKT_DISKUSSION` / `ERSTKONTAKT_DISKUSSION_ANLASS_ERSTE` /
   `ERSTKONTAKT_DISKUSSION_ANLASS_RUECKKEHR` mirroring the existing three
   constants' shape (same `{anlass}`/`{link}` placeholders so
   `_baue_erstkontakt`-style formatting still works). Add EN entries for all
   three new constants in `sprachen/en/texte.toml`.
   In `_baue_erstkontakt(conn, chat_id, e, rueckkehr=False)` (or wherever
   is cleanest — read the function first), branch at the top:
   ```python
   if workshop.diskussion_aktiv():
       # use the new ERSTKONTAKT_DISKUSSION* constants
   else:
       # existing body, completely unchanged
   ```
   Import `workshop` the way other late/lazy imports are done in this file
   if there isn't already a top-level import of it (check first — kontext.py
   may already import `workshop` for other `__getattr__`-based reasons).

**Tests:**
- `_baue_diskussion_block`: empty when no digest row exists; returns the
  header+text when one does; dropped under budget pressure the same way a
  sibling block is (mirror whatever test exists for `"festlegungen"`'s
  budget-drop behavior).
- `_baue_erstkontakt`/`einstieg_begriffe`: with
  `workshop.diskussion_aktiv()` monkeypatched `False` (the default), the
  returned text is **identical** to what it was before this task (a literal
  string-equality assertion against the pre-existing `ERSTKONTAKT`-based
  output — this is the regression guard for Dortmund); monkeypatched `True`,
  the returned text uses the new constants and mentions "Start listening"
  (EN table) / "Zuhoeren starten" (DE default) content, and does NOT ask for
  the five terms.
- Re-run `pytest tests/test_profil_bitgleich.py -q` and
  `python -m scripts.pruefe_profil dortmund-2026` once more after this task
  — this is the task most likely to regress them, verify explicitly.

---

## Task 9: Padua profile content wiring

Files: `workshop/padua-2026/profil.toml` (the `[diskussion]`/`[fragen_ab]`
sections, if not already added in Task 0 — check first, this may already be
done), `workshop/padua-2026/LIESMICH.md` (a one-paragraph note describing
what's new, following that file's existing style — read it first).

This is a small wrap-up task; if Task 0 already added the profile TOML
sections, this task is mostly documentation plus a final
`python -m scripts.pruefe_profil padua-2026` check. Do not duplicate the
TOML sections if Task 0 already added them.

**Tests:** none beyond re-running `scripts/pruefe_profil.py` for both
profiles.

---

## Task 10: e2e Playwright test — Phase 1 full flow

Files: a new file under `tests/e2e/` (follow the exact structure of an
existing test in that directory that exercises recording — e.g. whatever
file covers brainstorm or interview PTT with faked `getUserMedia`/
`MediaRecorder` — copy its fixture/fake-media setup).

Scenario: a Padua-profile group (profile flags on) at Phase 1 opens the
chat page → sees the "Start listening" button (and NOT the five-terms
request yet) → clicks it (fake mic granted) → a fake segment is flushed
(fake `MediaRecorder` → fake transcription in the test's backend double,
same mechanism the existing e2e tests use to avoid a real Whisper call) →
asserts a new chat bubble appears showing the transcript, authored as the
group (not the bot) → clicks "Discussion done" → asserts the chat shows the
five-terms prompt message. Assert at no point does a CoThinker-style
suggestion card/bot message appear between the start click and the done
click.

If the existing e2e harness in this repo doesn't support Padua-profile
group fixtures out of the box, that is itself a finding — note exactly what
was missing in your task report rather than fabricating a profile fixture
ad hoc; a minimal, well-contained addition to the test harness (e.g. an
`IT_WORKSHOP=padua-2026` env fixture already used elsewhere for non-e2e
tests, check `tests/profile/test_dortmund.py` for the pattern and whether an
e2e equivalent already exists) is in scope, inventing a new e2e fixture
pattern from scratch is not — flag it instead.

**Run:** the new e2e file specifically (Playwright is likely already
installed in this repo; skip gracefully with a clear message if it's not
available in this environment, matching how `tests/e2e/test_web_chat_e2e.py`
already handles a missing Playwright per `AGENTS.md`'s own note on that).

---

## Task 11: `_ARBEITSSTAND_FELDER` — new Phase 2 A/B fields

Files: `interview_theater/repo.py` only (plus whatever test asserts the
whitelist's exact tuple contents, if one exists — check
`tests/test_repo.py`).

Add six new field names to `_ARBEITSSTAND_FELDER` (pure additive, safe
unconditionally — an unused whitelisted field is inert):

- `fragen_ki_vorschlag` — the hidden KI-generated question lines
  ("Begriff: Frage" format, same shape as `fragen_auswahl`), set once by the
  background job from Task 12, never shown until the reveal.
- `fragen_ki_erzeugt_am` — ISO timestamp string, set alongside the above.
- `fragen_eigene_vorschlag` — the group's own, cleaned-up question lines
  (same line format), set once the group's own-questions stage closes.
- `fragen_eigene_erstellt_am` — ISO timestamp string, set alongside the
  above.
- `fragen_herkunft` — comma-separated list aligned by index with
  `fragen_auswahl` (same alignment convention as the existing
  `fragen_entschieden` field), each entry `"eigen"` or `"ki"`.
- `fragen_bearbeitet` — comma-separated list aligned the same way, each
  entry `"1"` or `""`, marking whether a KI-origin question was edited via
  "Schaerfen" (an "eigen"-origin question is never marked edited — editing
  your own question doesn't change its origin).
- `fragen_herkunft_final` — the `fragen_herkunft` list filtered down to only
  the finally-accepted indices, in the same order as the final `fragen`
  field (so the evaluation in Task 14 doesn't need to re-derive it from the
  pre-filter lists).

Add each with a one-line comment following this file's existing style
(reference "Padua Phase 1+2 Karte, 03.10.2026" + a short reason), same as
how `fragen_weich`/`fragen_aktuell` etc. are documented just above in this
tuple.

**Tests:** a round-trip test per new field via
`repo.setze_arbeitsstand(conn, chat_id, "<feld>", "<wert>")` +
`repo.hole_arbeitsstand` read-back, and a test that an unlisted field name
still raises `ValueError` (regression guard that the whitelist mechanism
itself is untouched).

---

## Task 12: `fragen_ki.py` — isolated background KI-question generation

Files: `interview_theater/fragen_ki.py` (new), new prompt pair
`interview_theater/prompts/fragen_ki_vorschlag.md` (DE) +
`interview_theater/sprachen/en/prompts/fragen_ki_vorschlag.md` (EN),
`interview_theater/knoepfe/stationen.py` (one new call site).

This is the module implementing the binding change in
`AB-AENDERUNG-PHASE2.md`: KI questions must be generated **before** any own
question arrives, from an **isolated** context (code-level isolation, not
prompt-level), and must never be regenerated/amended afterward.

1. Prompt pair: given the group's `begriffe` (terms, comma list) and — if
   present — the Phase 1 discussion digest
   (`repo.diskussion_verdichtung_text`), produce **exactly 3** open,
   experience-oriented questions per term (same "the term itself must be
   addressed inside the question" style rule as the existing
   `prompts/phasen/2.md` — read that file first for the inhaltlich house
   style and carry the same quality bar, but do NOT copy its "5 questions"
   instruction; this prompt asks for 3), output as plain lines
   `Begriff: Frage` (same line format `vorschlag.zeilen`/`fragenliste`
   already parse), one block, no extra commentary. EN mirror identical in
   structure, English wording.
2. `interview_theater/fragen_ki.py`:
   - `SCHEMA = {"type": "object", "additionalProperties": False, "required": ["antwort"], "properties": {"antwort": {"type": "string"}}}`
   - `ART = "fragen_ki_vorschlag"`
   - `_nutzertext(begriffe: str, diskussion_text: str | None) -> str`: an
     **isolated** builder — explicitly NOT `kontext.baue`, no Phase-2 chat
     window, no `arbeitsstand.fragen*` fields read at all (the function
     signature should make it structurally impossible to accidentally read
     the group's own questions — it only takes `begriffe`/`diskussion_text`
     as plain strings, not `conn`/`chat_id`).
   - `starte(conn, klm, e, chat_id: int) -> None`: no-op if `klm is None`;
     no-op if `not workshop.fragen_ab_aktiv()`; no-op if
     `repo.hole_arbeitsstand(conn, chat_id)["fragen_ki_vorschlag"]` is
     already set (idempotent — "kein Nachbessern": once generated, never
     regenerated, even on phase re-entry; a retry after a failed run is the
     ONE exception, see below); reads `begriffe` from the arbeitsstand and
     `diskussion_text` via `repo.diskussion_verdichtung_text` (may be
     `None` if Phase 1's digest never ran/was empty — the prompt must
     handle a missing digest gracefully, don't make it required); spawns a
     daemon thread that computes `ueber_claude =
     modellwahl.konversation_ueber_claude(e, conn, chat_id)`, calls
     `modellwahl.aufruf_schema(...)` with the isolated nutzertext, and on
     success calls two writes:
     `repo.setze_arbeitsstand(conn, chat_id, "fragen_ki_vorschlag", antwort)`
     then `repo.setze_arbeitsstand(conn, chat_id, "fragen_ki_erzeugt_am", <iso timestamp>)`.
     On failure: log + `repo.merke_vorfall(..., "fragen_ki_fehler", ...)`,
     leave both fields unset so a later retry (if you choose to add one —
     see "known gaps" below, a retry-on-next-entry is explicitly allowed by
     the card: "Faellt der Hintergrundlauf aus, wird er wiederholt") is
     possible; a simple way to allow exactly that without over-building: the
     idempotency check above only skips when the field is **already
     populated**, so a failed run (field still `NULL`) naturally allows a
     later call to `starte` (e.g. a repeated Phase-2 entry) to retry — no
     extra retry machinery needed.
     After a successful write, call
     `from interview_theater.knoepfe import fragen as fragen_modul;
     fragen_modul.versuche_gegenueberstellung(conn, tg, chat_id)` (this
     function is built in Task 13 — it checks whether BOTH the KI list and
     the group's own list are now ready, and if so, reveals the comparison;
     if the group's own questions aren't done yet, this call is a no-op).
     `starte`'s signature therefore needs a `tg` parameter too (the reveal
     needs to send a message) — add it: `starte(conn, tg, klm, e, chat_id)`.
3. `interview_theater/knoepfe/stationen.py::eintritt_in_phase`: add a new
   branch for `nummer == PHASE_FRAGEN` (define `PHASE_FRAGEN = 2` as a local
   module constant, same placement/style as the existing local
   `PHASE_BEGRIFFE = 1`), calling
   `if workshop.fragen_ab_aktiv(): from interview_theater import fragen_ki; fragen_ki.starte(conn, tg, klm, e, chat_id)`
   **before** falling through to the existing generic `else` branch
   (`biete_proaktiv(...)`) that already handles phase 2 today — do not
   remove or change that existing fallthrough, this is purely additive (an
   `if` added before the existing unconditional tail of the function, not a
   replacement of it). When the flag is off, behavior is 100% unchanged
   (the new `if` body simply never executes).

**Tests:**
- Isolation: a test builds a nutzertext via `_nutzertext` and asserts a
  planted marker string standing in for "a group's own question" (passed
  only as a conversational-history fixture elsewhere, never into this
  function) literally cannot appear in the output, because the function
  signature never receives it — plus, per the card's explicit test
  requirement, a test on `starte` using a `klm` double that records the
  exact `nutzer` text passed to `.schema`, asserting it does NOT contain a
  planted "eigene Frage" string present elsewhere in a fixture
  conversation/arbeitsstand.
- Ordering: after `starte` succeeds, `fragen_ki_erzeugt_am` is set; a
  separate own-questions save sets `fragen_eigene_erstellt_am` strictly
  later; assert `ki_erzeugt_am < eigene_erstellt_am` in a scenario where
  `starte` runs first (the card's explicit `(b)` acceptance test).
- No-amend: calling `starte` twice (second call after
  `fragen_ki_vorschlag` is already populated) does not change the stored
  value or re-call `.schema` a second time.
- Flag off (`fragen_ab_aktiv() == False`): `starte` and the
  `eintritt_in_phase` branch are no-ops; today's Phase 2 entry behavior is
  byte-identical to before this task (regression guard, same spirit as
  Task 8's Dortmund guard).
- Mutant check mentioned generally in the card ("Mutant: Phase-2-Chat in
  den Kontext geben -> Test rot"): write the isolation test so that if
  someone were to change `_nutzertext`'s signature to also accept
  `conn, chat_id` and read the Phase-2 window, the planted-marker assertion
  above would fail — verify this by literally trying that mutation locally,
  confirming the test goes red, then reverting (do this as a verification
  step, not a permanent change — report the result).

---

> 🔴 **BINDING CORRECTION (Birk 03.10. 10:25, orchestrator, overrides every
> "Our questions are done" button below):** there is NO such button and NO
> `ART_FRAGEN_EIGENE_FERTIG`. The comparison starts AUTOMATICALLY as soon as
> EVERY term has >= 3 own questions stored (deterministic code check after each
> save, no model) — with ONE short transition line. Until then, after each save
> one short status line ("Still missing: <term> 1, <term> 2"), no pushing. If
> the group says/writes it wants to move on earlier, the recogniser/chat starts
> the comparison anyway (no lock). Tests: condition met -> comparison exactly
> once; mutant ">=2 instead of >=3" -> red. See AB-AENDERUNG-PHASE2.md.

## Task 13: `knoepfe/fragen.py` — own-questions capture, reveal/comparison, origin tracking

This is the largest and most judgment-dependent task in Part C. Read
`interview_theater/knoepfe/fragen.py` in full before starting (it already
implements the per-question Annehmen/Verwerfen/Schaerfen flow this task
must extend, not replace).

Files: `interview_theater/knoepfe/fragen.py`, `interview_theater/vorschlag.py`
(new marker `EIGENE FRAGEN`/art `eigene_fragen`), `interview_theater/knoepfe/basis.py`
(one new dispatch branch), `interview_theater/knoepfe/texte.py` (new
`ART_FRAGEN_EIGENE_FERTIG` button art + its texts), a new profile-only
prompt override `workshop/padua-2026/prompts/phasen/2.md` (NOT touching the
shared `interview_theater/prompts/phasen/2.md` — see "Key design decision"
at the top of this plan for why).

1. `vorschlag.py`: add `"eigene_fragen"` to `ARTEN`, add
   `EIGENE\s+FRAGEN` as a new alternative in the `_ZEILE` regex (positioned
   the same careful way `FRAGEN WEICH` is positioned before `FRAGEN` — make
   sure `EIGENE FRAGEN` is tried before the bare `FRAGEN` alternative so it
   isn't swallowed by it, same reasoning as the existing comment about
   `FRAGEN WEICH`). The marker text the prompt will emit is therefore
   `VORSCHLAG EIGENE FRAGEN:` (DE) — for the EN profile prompt, the model
   still emits the **same marker text** `VORSCHLAG EIGENE FRAGEN:` (markers
   in this codebase are not translated — check: are any existing markers
   translated for EN prompts, or does `prompts/phasen/2.md`'s EN mirror
   still say `VORSCHLAG FRAGENAUSWAHL:` verbatim? Verify this with a quick
   grep of the EN prompt files before assuming either way, and follow
   whatever the existing convention actually is).
2. `workshop/padua-2026/prompts/phasen/2.md` (new profile override file):
   rewrite the Phase 2 instruction for Padua only: the group thinks up and
   speaks/types 3 questions per term themselves first; the model's job
   during this stage is to listen, assign incoming free-text to the right
   term, and keep an internal running tally — it must NOT propose its own
   questions in this phase (explicit sentence, matching the binding change's
   required wording: "Don't suggest questions yourself in this phase — the
   group writes first; your suggestions are already prepared."); when the
   group says (or presses a button meaning) "our questions are done", the
   model should emit `VORSCHLAG EIGENE FRAGEN:` followed by one
   `Begriff: Frage` line per term that got a question, cleanly reformulated
   (sense must not change) — using whatever the group actually said, never
   inventing a question for a term nobody addressed (leave that term out of
   the block rather than fabricating). Carry over the sensitivity/house
   style guidance from the base `prompts/phasen/2.md` (reuse its wording
   for "open, experience-oriented, the term itself must appear in the
   question" — don't lower that bar for the Padua override).
3. New button: `ART_FRAGEN_EIGENE_FERTIG` in `knoepfe/texte.py` (+ button
   label text DE/EN, e.g. `_TEXT_FRAGEN_EIGENE_FERTIG_KNOPF = "Unsere Fragen
   sind fertig"` / EN "Our questions are done") with
   `data-own-questions-done="1"` wherever this button renders as an HTML
   element (web path only — the Telegram inline-keyboard path has no `data-*`
   concept, that's fine, the attribute is web-UI-specific per the global
   constraints section; check how an existing knopf's label makes it into
   the web chat's rendered button markup, if at all — inline keyboards in
   this codebase may render identically on both channels via the knopf
   table, in which case there may be no natural place to attach a `data-*`
   attribute at all for a Telegram-style inline button; if that's the case,
   note it plainly as a gap in your task report rather than inventing a
   web-only rendering special-case not requested elsewhere).
   This button should be offered (always visible, same "always available"
   UX as Phase 1's "Discussion done") for the duration of the own-questions
   stage — find the natural place to send it (likely alongside/attached to
   whatever message currently invites the group to state their own
   questions, which in Padua's overridden prompt is the model's own first
   Phase-2 reply — so this button probably needs to be attached via the
   existing `knoepfe.basis.sende_mit_speicherleiste`/grundleiste mechanism
   to every Phase-2 bot reply while the own-questions stage is active, NOT
   as a one-off message; read how the existing "always visible" buttons in
   this codebase are kept visible across multiple turns — e.g. how the
   interview module keeps "Aufnahme beenden" visible across every
   subsequent send — and follow that exact pattern rather than inventing a
   new one).
4. Handler for the new button (in `knoepfe/wirkung.py`, added to the
   `_WIRKUNGEN` dispatch table, same registration pattern as every other
   `ART_*`): no model call (Zusage 2) — it sends a forced auftrag via
   `_starte_auftrag`, reusing the existing pattern in `fragen.py` (look at
   `frage_fuer_andere_richtung`/`_starte_schaerfung` for the shape): a short
   instruction telling the model "the group says they're done; emit
   `VORSCHLAG EIGENE FRAGEN:` NOW for everything assigned so far; leave a
   term's line out if nothing was said for it; do not invent."
5. New dispatch branch in `knoepfe/basis.py::sende_mit_speicherleiste` for
   `"eigene_fragen" in bloecke`, calling a new function
   `fragen.uebernimm_eigene(conn, tg, chat_id, bloecke["eigene_fragen"])`
   (mirror exactly how `"fragenauswahl"` is dispatched a few lines above it
   in that same function).
6. `knoepfe/fragen.py` new functions:
   - `uebernimm_eigene(conn, tg, chat_id, wert: str) -> int`: parses `wert`
     via `vorschlag.zeilen`, stores it to `fragen_eigene_vorschlag` +
     `fragen_eigene_erstellt_am` (ISO now), and calls
     `versuche_gegenueberstellung(conn, tg, chat_id)`; returns whatever that
     call returns (a sent message id) or a simple acknowledgement send if
     nothing was ready to reveal yet (own questions saved, waiting on KI).
   - `versuche_gegenueberstellung(conn, tg, chat_id) -> int | None`: the
     join point between Task 12's background job and this flow. Reads
     `fragen_eigene_vorschlag` and `fragen_ki_vorschlag`; if either is
     still empty, do nothing (return `None`) — whichever of the two writers
     runs second is the one that actually triggers the reveal, by calling
     this same function (Task 12's `starte` already does this after its
     write; this function's own caller, `uebernimm_eigene`, does it from
     the other side — so the reveal fires from whichever finishes last, by
     construction, with no polling needed). If idempotency matters here too
     (don't reveal twice if both writers happen to call this in a tight
     race) — guard it the same way: check whether `fragen_auswahl` is
     already non-empty (meaning the reveal already ran) and skip if so,
     since this function is the one that populates `fragen_auswahl` for
     the combined list below. Builds the combined list: group questions by
     term from both sources, per term list own question(s) first then the
     3 KI questions, track `fragen_herkunft` aligned by index ("eigen" for
     every line from `fragen_eigene_vorschlag`, "ki" for every line from
     `fragen_ki_vorschlag`), writes `fragen_auswahl` (the combined lines,
     same format as today) + `fragen_herkunft`, resets
     `fragen_aktuell`/`fragen_entschieden`/`fragen_warte_auf` to `None`
     (same reset `biete_fragenauswahl` already does for a fresh round —
     reuse its reset lines rather than duplicating them, factor a tiny
     shared helper if that's cleaner), and sends the overview + starts the
     per-question flow (reuse `fragenliste`/`starte_durchgehen` — do not
     reimplement the overview/listing logic, this is the explicit "reuse
     the flow" instruction from the card).
   - `_zeige_frage` (existing function): extend to append a short origin
     tag to the displayed question text when `fragen_herkunft` has data for
     this index — e.g. append `" (yours)"` / `" (AI)"` (EN; German default
     `" (eure)"` / `" (KI)"`) to the kopf or frage_text line — **plain text
     only**, no HTML/data attributes (see global constraints on
     `sichere_html`'s allowlist). Only do this when `fragen_herkunft` is
     non-empty for the current round (a pre-A/B-flow question, i.e. the
     classic 5-at-once flow when `fragen_ab_aktiv()` is off, has no
     `fragen_herkunft` at all and must render exactly as it does today —
     verify this with a regression test).
   - `entscheide`/`frage_waehlt_schaerfen`: when a question with
     `herkunft == "ki"` is accepted after being changed via "Schaerfen",
     mark it edited in `fragen_bearbeitet` (index-aligned, same convention
     as `fragen_herkunft`) — find the exact point in the existing Schaerfen
     flow (`uebernimm_schaerfung`) where the line text is replaced and set
     the corresponding `fragen_bearbeitet` entry to `"1"` there, but only
     when the line's `fragen_herkunft` entry is `"ki"` (an "eigen"-origin
     question's edited-flag is irrelevant per the card and should stay
     unset).
   - `_schliesse_fragen_ab`: when building the final `fragen` field from
     accepted questions, also build `fragen_herkunft_final` in lockstep
     (same filtering-by-`entschieden=="ja"` loop, one more parallel list)
     and persist it via `setze_arbeitsstand` alongside `fragen` in the same
     `_schreibe()` inner function.
7. When `fragen_ab_aktiv()` is off, NONE of the new code in this task
   should ever execute for a real group, because: (a) the new button is
   never offered (gate the offering code with the flag, same as Task 5/12's
   gating), and (b) `fragen_herkunft`/`fragen_eigene_vorschlag`/
   `fragen_ki_vorschlag` are never populated by anything. Add an explicit
   regression test proving the classic flow (`biete_fragenauswahl` →
   `starte_durchgehen` → `entscheide` → `_schliesse_fragen_ab`) is
   byte-identical in its sent message text to before this task, when no
   `fragen_herkunft` data exists.

**Tests:** this task needs the most coverage of the whole plan — budget
accordingly, consider splitting into two sub-dispatches (13a: vorschlag.py +
basis.py + the new button/texte.py plumbing + the profile override prompt
file; 13b: the fragen.py functions themselves) if the implementer finds it
too large for one pass. At minimum: `uebernimm_eigene` stores correctly;
`versuche_gegenueberstellung` only reveals once both sides are ready, reveals
exactly once even if both call it concurrently, and correctly interleaves
per-term own-then-ki lines with an aligned `fragen_herkunft`; `_zeige_frage`
shows the origin tag only when herkunft data exists and the correct tag per
index; `fragen_bearbeitet` gets set only for an edited KI-origin question,
never for an eigen-origin one; `fragen_herkunft_final` matches `fragen` in
length and in index correspondence after `_schliesse_fragen_ab`; the
classic (flag-off) flow is unchanged (string-equality regression test on
the overview message, same spirit as Task 8's Dortmund guard).

---

## Task 14: Deterministic evaluation (own vs. KI counts) + dashboard/group-page/chat display

Files: `interview_theater/knoepfe/fragen.py` or a small new module
`interview_theater/fragen_auswertung.py` (controller's call — if the
counting logic is more than ~20 lines, a dedicated pure-function module
mirroring `fehlstellen.py`'s "reine Leseabfrage" shape is cleaner than
burying it in `fragen.py`), `interview_theater/web_daten.py` (dashboard +
group page read paths), `interview_theater/web.py` if the dashboard HTML
needs a new line, chat text in `fragen.py`'s `_schliesse_fragen_ab`.

1. Pure function `auswertung(conn, chat_id) -> dict`: reading
   `fragen` + `fragen_herkunft_final` (set by Task 13's
   `_schliesse_fragen_ab`), compute, per term and in total, counts of
   `eigen` vs `ki` among the finally-kept questions. Return shape is the
   implementer's call, but must be deterministic (no model call) and
   directly testable — document the exact dict shape in a docstring and
   keep it stable since both the chat text and the dashboard will read it.
2. Chat text: `_schliesse_fragen_ab`'s existing confirmation message gets
   one more line (gated — only when `fragen_herkunft_final` is non-empty,
   i.e. the A/B flow actually ran) summarizing "You kept X AI questions and
   Y of your own" overall, plus the per-term breakdown (new DE default text
   + EN table entry).
3. Dashboard (`web_daten.py`'s dashboard-read function — find it, likely
   near `fehlstellen`/`roadmap`'s read functions) and the group page
   (`web_daten.py`'s per-group read function) each get the same
   `auswertung()` result exposed as a new, purely-additive dict key —
   follow the exact "reine Leseabfrage ueber eine eigene read-only
   Verbindung" constraint already documented in AGENTS.md for
   `web_daten.py` (no new SQL connection pattern, reuse the existing `conn`
   passed into whichever function you're extending).

**Tests (TDD — card's explicit mutation-test requirement, do not skip):**
- `auswertung()` on a fixture with a known mix of `eigen`/`ki` entries in
  `fragen_herkunft_final` returns the exact expected counts, per term and
  total.
- **Mutation test, literally run and shown**: take the same fixture, swap
  every `"eigen"`/`"ki"` value in `fragen_herkunft_final` (a simple
  str.translate/replace), re-run `auswertung()`, and assert the counts
  **differ** from the original (i.e. the test that asserted the original
  counts would now fail against the swapped fixture — write this as an
  actual executed assertion in the test file, e.g.
  `assert auswertung(...) != auswertung_mit_vertauschter_herkunft(...)`,
  not just a comment saying "a mutation would be caught"). Also run this
  mutation by hand once against the real function (temporarily edit the
  test fixture, run pytest, observe red, revert) and quote the red output
  in your task report, exactly as the card demands ("als Beleg
  tatsaechlich ausfuehren und zeigen").
- Dashboard/group-page tests: the new key appears with the right value for
  a fixture group; absent/zeroed for a group that never ran the A/B flow.

---

## Task 15: Full regression sweep + suite run

No new production code (only test additions if gaps are found while
reviewing). Steps:

1. Grep for every place this plan touched a shared/global code path
   (`modellwahl.py`, `kontext.py`'s `BUDGETS`/`_REIHENFOLGE`,
   `_ARBEITSSTAND_FELDER`, `db.py`'s two tables, `aufnahme.py`'s
   `_kurz_abschliessen`, `vorschlag.py`'s `ARTEN`/regex) and confirm each
   has at least one test proving Dortmund/flag-off behavior is unchanged —
   fill any gap found.
2. `pytest tests/test_profil_bitgleich.py -q`,
   `python -m scripts.pruefe_profil dortmund-2026`,
   `python -m scripts.pruefe_profil padua-2026` — all green, one more time,
   as the final gate before the full suite.
3. Check whether any task ended up touching `interview_theater/prompts/erkenner.md`
   or `interview_theater/sprachen/en/prompts/erkenner.md` (it should not
   have, per this plan's design — confirm with `git diff main...HEAD --
   interview_theater/prompts/erkenner.md interview_theater/sprachen/en/prompts/erkenner.md`).
   If it's empty, no korpus run is needed — state that explicitly in the
   final report. If NOT empty (a task deviated from plan), run
   `python -m scripts.pruefe_prompts erkenner --sprache en` and require
   FP=0 (exit code 0) before proceeding, per the card's acceptance
   criterion.
4. Start the full suite **in the background** with a log file:
   ```
   PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
   env -i HOME=$HOME PATH=/usr/bin:/bin "$PY" -m pytest -q -p no:cacheprovider \
     > /tmp/padua-phase12-suite.log 2>&1 &
   ```
   Poll the log file periodically (don't block the session on it, don't
   re-run it, don't guess its outcome) until it finishes, then read and
   quote the final summary line (`N passed, M failed, ...`) in the
   completion report. If anything failed, triage: a failure in a test this
   plan's tasks touched is this plan's bug (fix it, re-run just that file,
   then re-run the full suite once more in the background); a failure in
   an unrelated, pre-existing test is out of scope — note it explicitly
   rather than fixing unrelated code.
5. `git fetch origin && git log origin/main -1` — if `origin/main` has moved
   since this worktree's base, merge it into `wt/t_98928a4e` (per the
   card's explicit instruction to do this before completion) and re-run the
   affected tests/full suite once more if the merge touched anything this
   plan's tasks also touched.

---

## Known scope boundaries (restate in the final report, do not silently drop)

- The Phase-1 discussion-listening mode is **web-only** (like the existing
  brainstorm mode it's modeled on) — no Telegram equivalent is built, since
  the existing CoThinker/brainstorm feature this plan mirrors is itself
  web-only and Telegram's bot API has no native long-press-to-record
  concept matching this UX.
- Ending discussion-listening via spoken/typed "we're done" (rather than
  the button) is **not built** — the card's own Phase-1 description treats
  the button as the primary and, for this specific flow, sufficient
  mechanism (unlike other flows in this codebase where free text must
  always work in parallel to a button); flagged here as a deliberate scope
  decision, not an oversight.
- Per-question origin tags in the web chat are plain text, not styled
  `data-term-source` HTML spans, because chat bubble content passes through
  a fixed HTML tag allowlist that this plan does not extend (a
  security-relevant change out of scope for this card).
- `prompts/erkenner.md` is not touched; the new "Our questions are done"
  completion and "Discussion done" completion are both deterministic
  button-driven paths, not new Absichtserkenner intents — so no paid
  korpus run should be needed (verified in Task 15).
