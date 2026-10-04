# Padua UX: schlanke Kopfzeile, CoThinker lesbar, Rehearsal-Link raus — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five concrete Birk UX complaints on the unified group page
(`web_vereint.seite`) — unreadable CoThinker panel, an overlapping/duplicated
header, a dead rehearsal-view link in the Workbench tab — and add a Padua-only
phase stepper with prev/next arrows and a bottom sheet, replacing the
two-click "arm and confirm" phase-switch UI for that profile only.

**Architecture:** All changes live in the three existing web-layer modules
(`interview_theater/web.py`, `interview_theater/web_vereint.py`,
`interview_theater/web_gestalt.py`) plus one new `[web]` profile switch
(`workshop/padua-2026/profil.toml`) and one new field on the existing roadmap
data (`interview_theater/roadmap.py`). No new modules, no new routes (the
existing `/g/<token>/chat/phase` endpoint and `befehle.wechsle_phase` stay
unchanged — only the client that calls it changes for Padua).

**Tech Stack:** Python 3.11 stdlib `http.server`, hand-rolled vanilla JS (no
build step, no framework — CSP forbids inline `style=`/`on...=`, CSSOM only),
Playwright for e2e tests (`pytest.importorskip`, `pytest.mark.e2e`), pytest
for unit tests.

## Global Constraints

- Branch stays `wt/t_cc4306db`. No merge to main, no `git push`.
- Commit after every completed task — do not batch commits across tasks.
- CSP forbids `style="..."` attributes and `on...=` handlers in any HTML this
  plan emits — dynamic values go through CSSOM (`el.style.setProperty`) or
  class/attribute toggles only. No webfont, no `@font-face`, no external
  origin in any CSS added.
- `web_gestalt.py` imports nothing from the project except `sprache` — it
  must stay that way. It touches no SQL and calls no model.
- Every new `_TEXT_*` string constant added to `web_vereint.py` or
  `web_gestalt.py` **must** get a matching English entry in
  `interview_theater/sprachen/en/texte.toml` under the matching
  `["<module>"]` table (bracket-quoted table name = bare module name, key =
  exact constant name) — `tests/test_sprache_texte.py`'s `UMGESTELLT` set
  already includes both modules and asserts every `T.NAME`/`_TEXT_*` access
  has an English counterpart; this is a hard pytest failure, not a soft
  runtime fallback.
- `tests/test_profil_bitgleich.py` only covers LLM prompt text — it is
  unaffected by this plan and must stay green throughout, but it does not
  substitute for the web-output bitgleich check each task must add/keep
  green on its own (see Task 5, Task 6).
- Dortmund (`workshop/dortmund-2026/`, and the built-in default profile with
  no `IT_WORKSHOP` set) must render **byte-identical** `web_vereint.seite()`
  output for the Padua-only stepper/bottom-sheet feature (Task 6) — gated
  behind the new `[web] phasennav_stepper` switch, default `False`, set
  `True` only in `workshop/padua-2026/profil.toml`. The CSS/contrast/header
  fixes in Tasks 2–4 are **not** gated — they apply to every profile (the
  existing `web_gestalt` CSS already applies unconditionally to every
  profile on the unified page, per `web_vereint.seite()`; only the Team
  Dashboard `/` is gated behind `dashboard_gestaltet`).
- Playwright viewport convention already used across `tests/e2e/`:
  `HANDY = {"width": 390, "height": 844}` (iPhone-13-ish, no device
  emulation needed) and `LAPTOP = {"width": 1366, "height": 900}` (see
  `tests/e2e/test_web_gestalt_e2e.py`). Reuse these exact dicts/names where a
  new test file needs them; do not invent new numbers.
- Full verification command for pytest is plain `pytest` from the repo root
  (per `AGENTS.md`, "Starten und testen"). Playwright e2e tests are skipped
  automatically in a normal `pytest` run via `pytest.importorskip` and only
  run when explicitly targeted; still run the relevant e2e files for each
  task's own changes, and the full e2e suite once at the very end (Task 7).
- `scripts/pruefe_profil.py` must pass for **both** `dortmund-2026` and
  `padua-2026` (`IT_WORKSHOP=<name> python -m scripts.pruefe_profil`).

---

## Context for every implementer (read once, applies to all tasks)

The unified group page is assembled in `interview_theater/web_vereint.py`,
function `seite()` (around line 1224). It renders, in this DOM order, inside
`<body>` (a CSS flex column from `_css_schale()`, no literal `<header>` tag
exists anywhere in the current markup):

1. `_leiste_html(roadmapdaten, klickbar=...)` — a `<details class="roadmap"
   id="roadmap" data-aktive-phase="N">` element (flex item, `order: 0`,
   `flex: 0 0 auto` — a fixed, non-scrolling, non-growing header row). Its
   `<summary>` is one line closed: `"Phase N/7 · Name — x/y"` (constant
   `_TEXT_ROADMAP_KOPF`, `web_vereint.py:1084`). Opened, it shows an
   `<ol class="phasen">` list of all 7 phases with their task checklists and
   (for a clickable/Telegram-web group) a `.phase-knopf` per phase that arms
   itself (`data-sicher="1"`) on first click and sends the real
   `POST /g/<token>/chat/phase` on the second (JS in `web_vereint.py`
   `_VEREINT_JS`, functions `bewaffne`/`entwaffneAlle`/`springe`, lines
   ~744–856). `ladeRoadmap()` (lines ~897–951) polls `/teil/roadmap` and
   replaces the **entire** `<details>` subtree via `outerHTML` whenever the
   server content differs — any JS-added decoration inside it (the progress
   bar, in `web_gestalt.py`) must be **re-applied after every swap**, which
   is why `_JS_FORTSCHRITT`'s `schmuecke()` re-runs via a `MutationObserver`
   on the parent (`eltern` = `<body>`) rather than running once.
2. `_tabs_html(...)` — the tab bar (`<nav class="tabs">`), another fixed,
   non-scrolling flex item (`order` depends on `IT_UX_ENTWURF`: `0`/`1` for
   entwurf B, `5` for entwurf A — see `_css_schale()` in `web_vereint.py`
   around line 281).
3. One `<section class="panel panel-<tab>" ...>` per tab (`chat`, `stand`,
   `textbuch`, `buehne`) — the single flex item with `flex: 1 1 auto` that
   grows and scrolls internally (`overflow-y: auto`); all others are
   `hidden` except the active one.

`web_gestalt.py` is the **only** place that styles/decorates any of this with
the dark "Terminal/Bühne" theme — it is appended **unconditionally**, for
every workshop profile, via `css_rahmen()` + `scope_css(css_stand(), ...)` +
`scope_css(css_buehne(), ...)` (the last one does not exist yet — Task 2
creates it) + `_css_schale(...)`, always in that order, always last (highest
cascade priority). `web.py`'s `_CSS_GRUPPE`/`_CSS_BUEHNE` and
`web_vereint.py`'s `_CSS_VEREINT` are the **older, hardcoded-light-color**
base styles that `web_gestalt.py` overrides selector-by-selector — the
established pattern (see `web_gestalt._STAND`, already overriding dozens of
`_CSS_GRUPPE` selectors with `var(--...)` tokens) is: **never edit the
hardcoded light-color rule in `web.py`/`web_vereint.py` itself** (it must stay
byte-identical — other tests and a future "no dark theme" fallback depend on
it); instead add an **overriding** rule in `web_gestalt.py`, scoped the same
way, appended later in the cascade.

Theme tokens (`:root { --grund; --grund-2; --grund-3; --linie; --rand; --text;
--text-leise; --signal; --signal-tief; --auf-signal; --warn; --auf-warn;
--rec; --auf-rec; --radius; --radius-gross; --tippflaeche; ...}`) are defined
in `web_gestalt.TOKENS["a"]`/`TOKENS["b"]` and must never be hardcoded as hex
literals in new CSS — always `var(--name)`. `web_gestalt.KONTRAST` is the
tuple of foreground/background token pairs that
`tests/test_web_gestalt_tokens.py` recomputes a WCAG ratio for on every run;
reusing an existing pair (e.g. `("text", "grund-2")`, already ≥ 4.5) needs no
new entry there — only add a new `Paar` if you introduce a token combination
not already covered.

---

## Task 1: Baseline "before" screenshots

No code changes. This task captures the *current* (unmodified) rendering so
later tasks have a real "vorher" to diff against, as the card requires
("Screenshots vorher/nachher je Tab ... 'Vorher' kann aus dem Stand vor
deinem ersten Commit stammen").

**Files:**
- Create: `scripts/_kopfzeile_screenshots.py` (throwaway helper, **delete it
  again at the end of this task** after the screenshots are committed — it
  is not part of the product and should not linger; if you prefer, write it
  under `/tmp/` instead and skip creating it in the repo at all — either way,
  only the screenshots themselves are committed)
- Create: `docs/ux-padua/kopfzeile/vorher/` — PNG screenshots (see below)

**Interfaces:**
- Produces: a committed directory `docs/ux-padua/kopfzeile/vorher/` with 8
  PNGs (4 tabs × 2 viewports) that Task 7 will diff against visually when
  producing the "nachher" set. No code interface — this is a pure artifact
  task.

- [ ] **Step 1: Build a throwaway fixture + server + screenshot script**

  Follow the exact pattern in `tests/e2e/test_web_app_shell_e2e.py` (fixture
  `_baue_datenbank`/`server`/`browser`, `CHAT = 7_000_000_000_501`, phase 4 so
  all four tabs — `chat`, `stand`, `textbuch`, `buehne` — are reachable, kanal
  `"web"`). You do not need pytest for this — a standalone script using
  `subprocess.Popen([sys.executable, "-m", "interview_theater.web"], ...)`
  plus `playwright.sync_api.sync_playwright()` is enough. Reuse viewport
  dicts `HANDY = {"width": 390, "height": 844}` and
  `LAPTOP = {"width": 1366, "height": 900}`.

  For each of the 4 tabs (`chat`, `stand`, `textbuch`, `buehne` — force the
  `buehne` tab visible for the screenshot even though the fixture group may
  not be in phase 4 by the time you navigate, via
  `page.eval_on_selector("#tab-buehne", "el => el.hidden = false")` and a
  matching click/visibility toggle on its tab button if needed) and each of
  the 2 viewports (HANDY, LAPTOP), navigate to `/g/<token>#<tab>`, wait for
  `#tab-<tab>:not([hidden])`, and save a full-page screenshot to
  `docs/ux-padua/kopfzeile/vorher/<tab>-<viewport>.png` (e.g.
  `stand-handy.png`, `buehne-laptop.png`).

- [ ] **Step 2: Run it, inspect the 8 PNGs land under
  `docs/ux-padua/kopfzeile/vorher/`**

  Confirm with `ls -la docs/ux-padua/kopfzeile/vorher/` that all 8 files
  exist and are non-trivial in size (not blank/white — open at least the
  `buehne-handy.png` one to eyeball the current CoThinker readability
  problem described in the card, and `stand-handy.png` to see the "Next
  up"/negative-margin overlap — this is your empirical confirmation of the
  befund before you touch any code in later tasks).

- [ ] **Step 3: Commit**

  ```bash
  git add docs/ux-padua/kopfzeile/vorher/
  git commit -m "Capture baseline 'before' screenshots for Padua UX header card"
  ```

  If you created `scripts/_kopfzeile_screenshots.py` in the repo, delete it
  before this commit (`git rm` it, or just never `git add` it) — only the
  PNGs are a deliverable of this task.

**Report:** write `.superpowers/sdd/task-1-report.md` with: whether the
`buehne`/CoThinker tab's `#buehne-panel .karte` elements visibly rendered
white/light in your screenshot (confirms the premise of Task 2), and whether
you could visually see the "Next up" text overlapping the tab bar or panel
content in `stand-handy.png` / `chat-handy.png` (confirms the premise of Task
3). State DONE with these two observations; do not editorialize beyond them.

---

## Task 2: CoThinker/Workbench panel contrast fix

**Files:**
- Modify: `interview_theater/web_gestalt.py` (add a new `css_buehne()`
  function + its `_BUEHNE` constant; extend the existing `_STAND` constant;
  wire the new function into `web_vereint.py`)
- Modify: `interview_theater/web_vereint.py` (one new line in `seite()`)
- Create: `tests/e2e/test_web_gestalt_buehne_e2e.py` (new contrast test for
  the CoThinker/Workbench panel and the `.begriff`/`.fassung` chips in the
  Arbeitsstand panel)
- Test: `tests/test_web_gestalt_tokens.py` (run, should stay green — no
  change needed unless you introduce a genuinely new token pair)

**Interfaces:**
- Consumes: `web_gestalt.TOKENS`, the existing `--grund-2`/`--text`/`--linie`/
  `--rand`/`--text-leise` tokens (already proven ≥4.5:1 / ≥3:1 by the
  existing `KONTRAST` tuple — no new `Paar` entries needed if you stick to
  these). The existing `scope_css()` helper in `web_vereint.py` (signature:
  `scope_css(css_text: str, praefix: str) -> str`, prefixes every selector).
  The existing `_HELLIGKEIT` JS snippet in
  `tests/e2e/test_web_gestalt_e2e.py:378-401` (contrast-via-computed-style —
  copy it verbatim into your new test file; it is a plain string constant,
  not an import).
- Produces: `web_gestalt.css_buehne(name: str | None = None) -> str` (same
  signature shape as `css_stand`/`css_textbuch`), hooked into
  `web_vereint.seite()` right after the existing
  `css += scope_css(web_gestalt.css_stand(), ".panel-stand")` line.

**What is actually wrong (verified against the live code, not the card's
raw hypothesis — the card explicitly says "Hypothese, bitte pruefen"):**

1. `interview_theater/web.py:674-697`, constant `_CSS_BUEHNE`, defines
   `#buehne-panel .karte { background: #fff; ...}`, `.stueckkarte { ...
   background: #f2ede1; ...}`, `.hoert-zu { opacity: .55; ...}` — all
   hardcoded light colors, rendered inside `.panel-buehne` (the CoThinker
   tab). **Do not edit this constant** — it must stay byte-identical (it is
   the pre-theme fallback). Instead, add overriding rules scoped to
   `.panel-buehne`, following exactly the pattern `_STAND` already uses for
   `.panel-stand`.
2. `interview_theater/web.py:568-571` (`_CSS_GRUPPE`) defines
   `.begriff { ... background: #f2ede1; color: #4a4032; }` and
   `interview_theater/web.py:641-645` defines
   `.fassung { ... background: #f2ede1; color: #4a4032; }` /
   `.fassung.aktiv { background: #4a4032; ...}`. These render **inside the
   Arbeitsstand (stand) panel**, not CoThinker — `.begriff` via
   `web._begriffe_html()` (called from `_interview_html()`, itself part of
   `gruppe_koerper()`), `.fassung` via `web._fassungen_html()` (also called
   from `gruppe_koerper()`). `web_gestalt._STAND` (web_gestalt.py:1193-1272)
   already overrides dozens of other `_CSS_GRUPPE` hardcoded colors
   (`.feld select`, `.szene .volltext`, `.art`, `.feld button`, ...) but has
   **no** override for `.begriff` or `.fassung` — this is the real,
   confirmed gap (not a hypothesis — `grep -n "begriff\|fassung"
   interview_theater/web_gestalt.py` returns nothing in `_STAND`). Add both.

- [ ] **Step 1: Add `css_buehne()` to `web_gestalt.py`**

  Add a new module constant `_BUEHNE` right after `_STAND` (web_gestalt.py,
  after line 1272), and a `css_buehne()` function next to `css_stand()`
  (web_gestalt.py:417-421), same shape:

  ```python
  def css_buehne(name: str | None = None) -> str:
      """Was IM CoThinker/Workbench-Panel liegt. Fuer beide Entwuerfe
      gleich: eine Leseflaeche wie das Stand-Panel, die Tokens tragen den
      Unterschied."""
      return _BUEHNE
  ```

  ```python
  #: Das CoThinker-Panel (Birk, Live-Feedback 03.10.2026 23:10: "CoThinker
  #: ist kaum lesbar. Weisser Hintergrund."). ``web._CSS_BUEHNE`` setzt
  #: ``#buehne-panel .karte``/``.stueckkarte`` fest hell -- dieselbe Luecke
  #: wie bei ``_STAND`` oben, nur nie geschlossen. Scoped auf
  #: ``.panel-buehne`` durch den Aufrufer, wie ``css_stand()``.
  _BUEHNE = """
  #buehne-panel .karte { background: var(--grund-2); color: var(--text);
                         border-color: var(--linie); }
  #buehne-panel .karte.alt { color: var(--text-leise); opacity: 1; }
  #buehne-panel .hoert-zu { color: var(--text-leise); opacity: 1; }
  #buehne-panel .leer { color: var(--text-leise); opacity: 1; }
  .stueckkarte { background: var(--grund-3); }
  .sk-haken { color: var(--text-leise); opacity: 1; }
  .sk-frei { color: var(--text-leise); opacity: 1; }
  """
  ```

  Note `.karte.alt`/`.hoert-zu`/`.leer`/`.sk-haken`/`.sk-frei` in the base
  CSS (`web.py`) use `opacity: .6`/`.55`/`.75` to dampen *on top of* an
  already-dark-enough color — since the base text color inherits from `body`
  (which `_BASIS` already sets to `var(--text)` on a dark `var(--grund)`),
  the real bug is only the explicit hardcoded `background: #fff` /
  `background: #f2ede1` lines; everything else inherits correctly once the
  background is fixed. Verify this with the contrast test in Step 3 rather
  than guessing — if the test shows a text/background pair still under
  4.5:1, add the missing override rather than assuming the above list is
  exhaustive.

- [ ] **Step 2: Extend `_STAND` with `.begriff`/`.fassung` overrides**

  Add at the end of the `_STAND` constant (web_gestalt.py, just before the
  closing `"""` at line 1272):

  ```python
  /* CoThinker-Befund, derselbe Fehler eine Panel-Ebene hoeher: die
     Begriffs-Chips und die Fassungsleiste sind helle Sandflaechen aus
     ``_CSS_GRUPPE`` -- wie die Speichern-Knoepfe oben, nur bisher nicht
     mitgefasst. */
  .begriff { background: var(--grund-3); color: var(--text); }
  .fassung { background: var(--grund-2); color: var(--text);
             border-color: var(--rand); }
  .fassung.aktiv { background: var(--signal); border-color: var(--signal);
                   color: var(--auf-signal); }
  ```

- [ ] **Step 3: Wire `css_buehne()` into `web_vereint.seite()`**

  In `web_vereint.py`, `seite()` function, find:

  ```python
      css += scope_css(web_gestalt.css_stand(), ".panel-stand")
      css += scope_css(web_gestalt.css_textbuch(), ".panel-textbuch")
  ```

  and insert a new line between them:

  ```python
      css += scope_css(web_gestalt.css_stand(), ".panel-stand")
      css += scope_css(web_gestalt.css_buehne(), ".panel-buehne")
      css += scope_css(web_gestalt.css_textbuch(), ".panel-textbuch")
  ```

- [ ] **Step 4: Write the contrast e2e test**

  Create `tests/e2e/test_web_gestalt_buehne_e2e.py`. Follow the exact
  fixture/server/browser pattern of `tests/e2e/test_web_gestalt_e2e.py`
  (`_baue_datenbank`, `dienst` fixture, `MIKROFON` args, `HANDY` viewport) —
  you can import nothing from that file (it is a test file, not a library);
  copy the `_HELLIGKEIT` JS string constant verbatim and the `_ALLE_TEXTE`
  JS string constant verbatim (web_gestalt_e2e.py:378-424) into your new
  file, plus a minimal `_baue_datenbank`/`dienst` fixture building a group in
  **phase 4** (so the `buehne` tab is not `hidden` — reuse
  `repo.setze_phase(conn, CHAT, 4)` plus the figure/scene setup already shown
  in `tests/e2e/test_web_app_shell_e2e.py:70-113`, which is exactly a
  phase-4 fixture with all four tabs reachable — you may copy that
  `_baue_datenbank` function near-verbatim with your own `DB_PFAD`/`CHAT`
  constants to avoid port/db clashes with other e2e files).

  Write two tests:

  ```python
  def test_cothinker_panel_hat_kontrast(dienst):
      """Birk, Live-Feedback 03.10.2026 23:10: 'CoThinker ist kaum lesbar.
      Weisser Hintergrund.' -- jeder sichtbare Text im Buehne-Panel gegen
      seinen tatsaechlichen, gerenderten Grund."""
      basis, token = dienst
      with sync_playwright() as p:
          browser = p.chromium.launch(args=MIKROFON)
          seite = browser.new_page(viewport=HANDY)
          seite.goto(f"{basis}/g/{token}#buehne")
          seite.wait_for_timeout(500)
          seite.eval_on_selector("#tab-buehne", "el => el.hidden = false")
          schlecht = seite.eval_on_selector(
              "#buehne-panel",
              """(wurzel, miss) => {
                const f = eval(miss), out = [];
                for (const el of wurzel.querySelectorAll('*')) {
                  if (!el.getClientRects().length) { continue; }
                  const eigen = [...el.childNodes].some(
                    n => n.nodeType === 3 && n.textContent.trim());
                  if (!eigen) { continue; }
                  const w = f(el);
                  if (w.kontrast < 4.5) {
                    out.push([el.tagName + '.' + el.className,
                              el.textContent.trim().slice(0, 30),
                              Math.round(w.kontrast * 100) / 100]);
                  }
                }
                return out;
              }""",
              _HELLIGKEIT,
          )
          assert not schlecht, schlecht
          browser.close()


  def test_begriff_und_fassung_chips_haben_kontrast(dienst):
      """Derselbe Fehler eine Panel-Ebene hoeher: die Begriffs-Chips und die
      Fassungsleiste im Arbeitsstand-Panel."""
      basis, token = dienst
      with sync_playwright() as p:
          browser = p.chromium.launch(args=MIKROFON)
          seite = browser.new_page(viewport=HANDY)
          seite.goto(f"{basis}/g/{token}#stand")
          seite.wait_for_timeout(500)
          for sel in (".begriff", ".fassung"):
              if seite.locator(sel).count() == 0:
                  continue
              wert = seite.eval_on_selector(sel, _HELLIGKEIT)
              assert wert["kontrast"] >= 4.5, (sel, wert)
          browser.close()
  ```

  Your fixture data must include at least one interview with
  `verdichtung_thema`/`begriffe` so `.begriff` chips actually render (see
  `web._begriffe_html` — it needs a non-empty `begriffe` list on the
  interview dict), and at least one scene with ≥2 `szenenfassung` rows so the
  `.fassung` nav renders (see `web._fassungen_html` — it only renders a
  `<nav class="fassungen">` with ≥2 fassungen; look at how
  `tests/test_web.py` or `tests/e2e/test_web_vereint_e2e.py` seeds
  `szenenfassung` rows via `repo` for the exact function name/signature to
  call, e.g. `repo.haenge_szenenfassung_an` or similar — grep `repo.py` for
  `fassung` to find the real name before using it).

  **Mutation check (do this manually, then revert — do not commit the
  mutation):** temporarily change `background: var(--grund-2)` back to
  `background: #fff` in your new `_BUEHNE` constant, rerun
  `test_cothinker_panel_hat_kontrast`, confirm it goes **red**, then revert
  the change before committing.

- [ ] **Step 5: Run the tests**

  ```bash
  pytest tests/test_web_gestalt_tokens.py -q
  pytest tests/test_web_vereint.py tests/test_web.py -q
  /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest tests/e2e/test_web_gestalt_buehne_e2e.py tests/e2e/test_web_gestalt_e2e.py -q
  ```

  (If that venv path does not exist in your environment, use whichever
  Python has `playwright` installed — check `tests/e2e/README.md` for the
  current convention; if none is installed, state that clearly in your
  report as `DONE_WITH_CONCERNS` rather than skipping the e2e test
  unverified.)

- [ ] **Step 6: Commit**

  ```bash
  git add interview_theater/web_gestalt.py interview_theater/web_vereint.py tests/e2e/test_web_gestalt_buehne_e2e.py
  git commit -m "Fix CoThinker/Workbench panel contrast: theme the buehne cards, begriff chips, fassung nav"
  ```

**Report:** `.superpowers/sdd/task-2-report.md` — confirm the mutation test
went red and the real test is green, and the exact `repo.*` function name you
used to seed `szenenfassung` rows.

---

## Task 3: Slim single-line header (merge "Next up" into the Phase line, drop "Act" duplication, remove the overlap)

**Files:**
- Modify: `interview_theater/web_vereint.py` (wrap the roadmap kopf text in
  a span, one line in `_leiste_html()`)
- Modify: `interview_theater/web_gestalt.py` (merge `_JS_FORTSCHRITT` +
  `_JS_NAECHSTES` into one decoration function; rewrite `_ROADMAP`'s
  `#ux-naechstes` CSS without the negative margin; remove the `.ux-akt`
  "Akt N/gesamt" text injection; remove the now-dead `_TEXT_AKT_KOPF`
  constant + its `_mikrotexte()` entry + its English translation entry)
- Modify: `interview_theater/sprachen/en/texte.toml` (remove the
  `_TEXT_AKT_KOPF` line under `["web_gestalt"]` — it becomes dead)
- Create: `tests/e2e/test_web_kopfzeile_e2e.py` (overlap test, header-height
  test, no-"Act"-text test — all three with their required mutation checks)

**Interfaces:**
- Consumes: the existing `summary` flex layout (`.roadmap > summary {
  display: flex; align-items: center; gap: .5rem; ...}`,
  web_gestalt.py:685-689), the existing `#ux-balken` progress-bar JS/CSS
  (unchanged by this task), `TEXTE.naechstes`/`TEXTE.naechste_phase` already
  populated by `_mikrotexte()` (unchanged — only `TEXTE.akt_kopf` is removed).
- Produces: nothing new is consumed by a later task — this is a leaf UI fix.
  Task 6 (Padua stepper) **replaces** this entire roadmap/summary rendering
  path for Padua only, so it does not depend on this task's merged
  `schmuecke()` function; it builds its own header markup from scratch.
  Still do this task first and keep it correct for Dortmund (and for Padua
  before/without the Task 6 switch), since the plan executes in order and
  Dortmund must never regress.

**Why the current code overlaps, in order of actual cause (verified, not
guessed):**

`web_gestalt.py:743-744` (constant `_ROADMAP`) sets
`#ux-naechstes { max-width: 44rem; margin: -.35rem auto .45rem; ...}` — a
negative top margin on a flex child (`#ux-naechstes` is inserted as a
**sibling** of `#roadmap`, both direct children of `<body>`, per
`_JS_NAECHSTES` at web_gestalt.py:1492-1541,
`eltern.insertBefore(zeile, erste.nextSibling)`). In the app-shell flex
column (`_css_schale()`, `web_vereint.py:281-400`), `.roadmap` has an
explicit `order: 0`/`flex: 0 0 auto`, but the `#ux-naechstes` paragraph has
**no** explicit `order` override in `_css_schale()` — it only avoids
visually floating away because it is the next sibling in DOM order with the
same default `order: 0`. The negative margin then pulls it upward,
overlapping whatever sits directly above it in the stacking/flow (the bottom
edge of the closed `<details>`, and — once opened — the top of the task
list). Separately, `web_gestalt.py:1462-1470` (`_JS_FORTSCHRITT`'s
`schmuecke()`) prepends a `<b class="ux-akt">Akt N/gesamt</b>` marker as the
**first child of `<summary>`**, immediately **before** the server-rendered
`"Phase N/7 · Name — x/y"` text — the literal doubling Birk saw ("Act and
Phase doppeln sich").

The fix below removes the standalone `#ux-naechstes` sibling-insertion
entirely and instead renders the "next up" text **as a flex child inside the
same `<summary>`** that already shows the Phase line, re-created on every
roadmap decoration pass (the existing code already has to tolerate the whole
`<details>` subtree being replaced via `outerHTML` on every `/teil/roadmap`
poll — `ladeRoadmap()`, web_vereint.py:897-951 — which is exactly why
`_JS_FORTSCHRITT`'s own comment at web_gestalt.py:1418-1423 explains it
re-decorates via a `MutationObserver` on the **parent**, not by caching a
node reference across swaps; the current separate `_JS_NAECHSTES`
implementation instead creates its `<p id="ux-naechstes">` **once** and
mutates it in place — explicitly documented at web_gestalt.py:1487-1489 as
living **outside** `#roadmap` *because* a child of it would be destroyed on
swap. Merging the two into one re-run-on-every-swap function, like
`schmuecke()` already is, resolves that constraint instead of working around
it, and lets "next up" live inside `<summary>` safely).

- [ ] **Step 1: Wrap the kopf text in a span (server-side, one line)**

  In `interview_theater/web_vereint.py`, `_leiste_html()` function
  (around line 1212-1221), change:

  ```python
      return (
          f'<details class="roadmap" id="roadmap" data-aktive-phase="{aktiv["nummer"]}">'
          f'<summary>{html.escape(kopf)}</summary>'
          f'<ol class="phasen">{"".join(zeilen)}</ol>'
          f'</details>\n'
      )
  ```

  to:

  ```python
      return (
          f'<details class="roadmap" id="roadmap" data-aktive-phase="{aktiv["nummer"]}">'
          f'<summary><span class="roadmap-kopf">{html.escape(kopf)}</span></summary>'
          f'<ol class="phasen">{"".join(zeilen)}</ol>'
          f'</details>\n'
      )
  ```

  This gives CSS/JS a stable anchor for "the fixed-width part of the summary
  line" distinct from the progress bar and the new next-up text, so flex
  shrink/grow and `text-overflow: ellipsis` behave predictably. Before this
  change, grep the test suite for any test asserting the exact raw
  `<summary>...</summary>` string (`grep -rn 'summary>{html.escape(kopf)' tests/
  ; grep -rn "_TEXT_ROADMAP_KOPF\|<summary>Phase" tests/`) and update any
  that assert the old unwrapped form.

- [ ] **Step 2: Add `.roadmap-kopf` + rewrite `#ux-naechstes` CSS in
  `_ROADMAP`**

  In `web_gestalt.py`, inside the `_ROADMAP` constant, add right after the
  existing `.roadmap > summary { ... }` rule (web_gestalt.py:685-689):

  ```
  .roadmap-kopf { flex: 0 0 auto; }
  ```

  Then **delete** the existing block (web_gestalt.py:743-748):

  ```
  #ux-naechstes { max-width: 44rem; margin: -.35rem auto .45rem;
                  padding: 0 .3rem; font-size: .9rem; line-height: 1.35;
                  color: var(--text-leise); white-space: nowrap;
                  overflow: hidden; text-overflow: ellipsis; }
  #ux-naechstes[hidden] { display: none; }
  #ux-naechstes b { color: var(--text); font-weight: 600; }
  ```

  and replace it with:

  ```
  /* P2/Padua-Kopfzeile-Karte: "Next up" ist jetzt ein Flex-Kind INNERHALB
     derselben Zeile wie "Phase N/7 · Name" -- kein eigener Flex-Zeilen-
     Teilnehmer mehr, kein negatives Margin, kein Ueberlappen. */
  #ux-naechstes { flex: 1 1 auto; min-width: 0; margin-left: auto;
                  padding: 0 0 0 .4rem; font-size: .9rem; line-height: 1.35;
                  color: var(--text-leise); white-space: nowrap;
                  overflow: hidden; text-overflow: ellipsis; text-align: right; }
  #ux-naechstes[hidden] { display: none; }
  #ux-naechstes b { color: var(--text); font-weight: 600; }
  ```

- [ ] **Step 3: Merge the two decoration functions in `web_gestalt.py`**

  Replace the whole `_JS_FORTSCHRITT` constant body (web_gestalt.py:1414-1473)
  **and** delete the whole `_JS_NAECHSTES` constant (web_gestalt.py:1476-1541)
  with one merged constant (keep the name `_JS_FORTSCHRITT` — it is the one
  referenced by `skript()`; grep `skript(` in web_gestalt.py to confirm
  `_JS_NAECHSTES` is concatenated there too and remove that reference):

  ```python
  _JS_FORTSCHRITT = """
    (function fortschritt() {
      var erste = el('roadmap');
      if (!erste) { return; }
      var eltern = erste.parentNode;
      var dekoriere = function () {
        var roadmap = el('roadmap');
        if (!roadmap || roadmap.querySelector('#ux-balken')) { return; }
        schmuecke(roadmap);
      };
      if (eltern) {
        new MutationObserver(dekoriere).observe(eltern, { childList: true });
      }
      dekoriere();

      var naechstesText = function (roadmap) {
        var aktiv = roadmap.querySelector('.phase.aktiv');
        if (!aktiv) { return ''; }
        var offen = aktiv.querySelector('.aufgabe:not(.erledigt)');
        if (offen) {
          return (offen.textContent || '').trim().replace(/^\\S+\\s+/, '');
        }
        var folgende = aktiv.nextElementSibling;
        while (folgende && !folgende.classList.contains('phase')) {
          folgende = folgende.nextElementSibling;
        }
        var name = function (phase) {
          var k = phase.querySelector('.phase-knopf, .phase-name');
          return k ? (k.dataset.bezeichnung || k.textContent || '').trim() : '';
        };
        var bez = folgende ? name(folgende) : '';
        return bez ? (TEXTE.naechste_phase || '{bezeichnung}')
          .replace('{bezeichnung}', bez) : '';
      };

      function schmuecke(roadmap) {
      var summary = roadmap.querySelector('summary');
      var phasen = roadmap.querySelectorAll('.phase');
      if (!summary || !phasen.length) { return; }

      var balken = document.createElement('span');
      balken.id = 'ux-balken';
      if (MOMENT === 'vorhang') {           // Entwurf B: ein Licht je Akt
        for (var i = 0; i < phasen.length; i++) {
          var licht = document.createElement('i');
          var knoten = phasen[i];
          licht.dataset.stand = knoten.classList.contains('aktiv') ? 'aktiv'
            : (knoten.querySelector('.aufgabe:not(.erledigt)') ? 'offen' : 'fertig');
          balken.appendChild(licht);
        }
      } else {                              // Entwurf A: ein Balken
        balken.appendChild(document.createElement('i'));
        var alle = roadmap.querySelectorAll('.aufgabe').length;
        var fertig = roadmap.querySelectorAll('.aufgabe.erledigt').length;
        balken.style.setProperty('--fortschritt',
          (alle ? Math.round(fertig * 100 / alle) : 0) + '%');
      }
      summary.appendChild(balken);

      if (TEXTE.naechstes) {
        var sache = naechstesText(roadmap);
        var zeile = document.createElement('p');
        zeile.id = 'ux-naechstes';
        zeile.hidden = !sache;
        if (sache) {
          var teile = TEXTE.naechstes.split('{was}');
          zeile.appendChild(document.createTextNode(teile[0] || ''));
          var b = document.createElement('b');
          b.textContent = sache;
          zeile.appendChild(b);
          zeile.appendChild(document.createTextNode(teile.slice(1).join('')));
          zeile.title = zeile.textContent;
        }
        summary.appendChild(zeile);
      }
      }
    })();
  """
  ```

  Then find the `skript()` function (web_gestalt.py:1873 area) and remove
  the `_JS_NAECHSTES` concatenation (grep `_JS_NAECHSTES` to find its one
  remaining use site and delete that line only — leave every other
  constituent of `skript()` untouched).

- [ ] **Step 4: Delete the dead `_TEXT_AKT_KOPF` constant and its wiring**

  After Step 3, `TEXTE.akt_kopf` has no reader left in JS. Confirm with
  `grep -n "akt_kopf\|_TEXT_AKT_KOPF" interview_theater/web_gestalt.py` that
  the only remaining hits are the constant definition
  (web_gestalt.py:266, `_TEXT_AKT_KOPF = "Akt {nummer}/{gesamt}"`) and its
  entry in `_mikrotexte()` (`"akt_kopf": T._TEXT_AKT_KOPF,` — grep
  `_mikrotexte` to find the exact line). Delete both. Then delete the
  `_TEXT_AKT_KOPF = "Act {nummer}/{gesamt}"` line under `["web_gestalt"]` in
  `interview_theater/sprachen/en/texte.toml` (grep `_TEXT_AKT_KOPF` there to
  find it — around line ~1876 per the earlier research, but confirm by
  grep, do not trust the line number blindly).

  Run `grep -rn "TEXT_AKT_KOPF\|akt_kopf" interview_theater/ tests/` after
  deleting — it must return **zero** hits.

- [ ] **Step 5: Write the three required e2e tests**

  Create `tests/e2e/test_web_kopfzeile_e2e.py`, following the same
  fixture/server pattern as `tests/e2e/test_web_app_shell_e2e.py` (reuse its
  `_baue_datenbank`/`token`/`server`/`browser` fixtures near-verbatim with
  your own `DB_PFAD`/`BIND`/`CHAT` to avoid clashing with other e2e test
  files run in the same process/session).

  ```python
  HANDY = {"width": 390, "height": 844}
  LAPTOP = {"width": 1366, "height": 900}
  TABS = ("chat", "stand", "textbuch", "buehne")


  @pytest.mark.parametrize("viewport,name", [(HANDY, "handy"), (LAPTOP, "laptop")])
  def test_kopfzeile_ueberlappt_keinen_panelinhalt(server, browser, token, viewport, name):
      """Birk: 'Workbench und Chat werden von Next up ueberdeckt.' Kein
      Bounding-Rect des Kopfbereichs (roadmap + tabs) darf das erste
      sichtbare Inhaltselement eines Panels schneiden."""
      kontext = browser.new_context(viewport=viewport)
      seite = kontext.new_page()
      seite.set_default_timeout(8000)
      seite.goto(f"{BASIS}/g/{token}")
      seite.wait_for_selector("#tab-chat:not([hidden])")
      for tab in TABS:
          seite.click(f'.tabs button[data-tab="{tab}"]')
          seite.wait_for_selector(f"#tab-{tab}:not([hidden])")
          kopf = seite.locator("#roadmap").bounding_box()
          tabs_kasten = seite.locator(".tabs").bounding_box()
          panel = seite.locator(f"#tab-{tab}")
          erstes = panel.locator(":scope > *").first
          if erstes.count() == 0:
              continue
          inhalt = erstes.bounding_box()
          if inhalt is None:
              continue
          # Kein Schnitt: der Kopf (roadmap + tabs) endet, bevor der Inhalt beginnt.
          kopf_unten = max(kopf["y"] + kopf["height"], tabs_kasten["y"] + tabs_kasten["height"])
          assert inhalt["y"] >= kopf_unten - 1, (name, tab, kopf, tabs_kasten, inhalt)
      kontext.close()


  def test_kopfzeilenhoehe_passt_aufs_handy(server, browser, token):
      """Karte, Punkt E: Kopf + Tableiste zusammen <= 96px am Handy."""
      kontext = browser.new_context(viewport=HANDY)
      seite = kontext.new_page()
      seite.goto(f"{BASIS}/g/{token}")
      seite.wait_for_selector("#tab-chat:not([hidden])")
      kopf = seite.locator("#roadmap").bounding_box()
      tabs_kasten = seite.locator(".tabs").bounding_box()
      hoehe = kopf["height"] + tabs_kasten["height"]
      assert hoehe <= 96, (kopf, tabs_kasten, hoehe)
      kontext.close()


  def test_kein_akt_wort_im_kopf(server, browser, token):
      """Birk: 'Act and Phase doppeln sich.' Kein sichtbares 'Act'/'Akt' im
      Kopfbereich -- nur noch 'Phase N/7 · Name' + 'Next up'."""
      kontext = browser.new_context(viewport=HANDY)
      seite = kontext.new_page()
      seite.goto(f"{BASIS}/g/{token}")
      seite.wait_for_selector("#roadmap")
      text = seite.locator("#roadmap > summary").inner_text()
      assert "Act" not in text and "Akt" not in text, text
      kontext.close()
  ```

  (Use whatever `BASIS`/`server`/`browser`/`token` fixture names and
  module-level constants your copied boilerplate from
  `test_web_app_shell_e2e.py` actually defines — the snippets above assume
  you kept the same names; adapt if you renamed anything.)

  **Mutation checks (do manually, then revert, do not commit the mutated
  state):**
  - Temporarily restore the old negative-margin `#ux-naechstes` rule →
    `test_kopfzeile_ueberlappt_keinen_panelinhalt` must go **red**.
  - Temporarily re-add the `.ux-akt`/`akt_kopf` prepend block from Step 3 →
    `test_kein_akt_wort_im_kopf` must go **red**.
  - Revert both before committing.

- [ ] **Step 6: Run the tests**

  ```bash
  pytest tests/test_web_vereint.py tests/test_sprache_texte.py -q
  /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest tests/e2e/test_web_kopfzeile_e2e.py tests/e2e/test_web_vereint_e2e.py tests/e2e/test_web_gestalt_e2e.py tests/e2e/test_web_app_shell_e2e.py -q
  ```

  If any existing e2e test asserts the exact old `<summary>` HTML or the
  presence of `.ux-akt`/`akt_kopf`, fix that assertion to match the new
  structure rather than reverting your change — grep first
  (`grep -rln "ux-akt\|akt_kopf\|roadmap-kopf" tests/`).

- [ ] **Step 7: Commit**

  ```bash
  git add interview_theater/web_vereint.py interview_theater/web_gestalt.py \
          interview_theater/sprachen/en/texte.toml tests/e2e/test_web_kopfzeile_e2e.py
  git commit -m "Slim the header: merge Next-up into the Phase line, drop duplicate Act marker, remove overlap"
  ```

**Report:** `.superpowers/sdd/task-3-report.md` — confirm both mutation
checks went red, list any pre-existing test you had to update and why.

---

## Task 4: Remove the rehearsal-view link from the Workbench tab

**Files:**
- Modify: `interview_theater/web.py` (remove ~6 lines from
  `gruppe_koerper()`)
- Test: add one assertion to an existing test file (see below) rather than a
  new file — this is a small, surgical removal.

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new. `_TEXT_PROBENANSICHT_LINK` becomes **dead** after
  this change (confirmed: it has exactly one other reference in the whole
  repo besides its own definition, and this task removes that one
  reference) — delete the constant too, in the same commit, after
  confirming with a fresh grep that it has zero remaining references.

**What to change (verified: the link lives in the "stand"/Arbeitsstand
panel's body, built by `gruppe_koerper()`, not in the "buehne"/Workbench
panel — but it is embedded on the unified page's Workbench... re-check this
yourself before editing, see the note below):**

The card's befund says the link appears in "the Workbench tab" — but the
actual code places it inside `web.gruppe_koerper()` (`web.py:2797` onward),
which backs the **`stand`** (Arbeitsstand) tab, not the `buehne`
(Workbench/CoThinker) tab (`_buehne_html()` is a separate function and does
not reference `_TEXT_PROBENANSICHT_LINK` at all). **Before editing, open
`interview_theater/web.py` around line 2849-2863 yourself and confirm which
panel this renders into on the live page** (cross-check against your Task 1
screenshot of the `stand` tab — the link should be visible there, with the
📖 emoji, since `web_vereint.py` wires `panels["stand"] =
web.gruppe_koerper(...)`). If your reading of the live screenshot disagrees
with this plan's claim, stop and flag the discrepancy in your report rather
than guessing which tab the card meant — do not silently "fix" the wrong
tab's content. Proceed with the removal below only once you've confirmed
it's the same link the card is pointing at (same 📖 wording, same
`/textbuch` destination) regardless of which tab label the card used for it.

- [ ] **Step 1: Remove the embed**

  In `interview_theater/web.py`, inside `gruppe_koerper()`, find (around
  line 2849-2863):

  ```python
      probenansicht = (
          f'<p class="probenansicht"><a href="{_t(praefix, "")}/g/{_t(token)}/textbuch">'
          f"{_t(T._TEXT_PROBENANSICHT_LINK)}</a></p>"
          if token
          else ""
      )
  ```

  and its use further down (`f"{probenansicht}"` spliced into the returned
  body). Delete the assignment and remove `probenansicht` from the returned
  f-string/concatenation. Run
  `grep -n "probenansicht" interview_theater/web.py` afterward to confirm no
  dangling reference remains in `gruppe_koerper()`.

- [ ] **Step 2: Delete the now-dead constant**

  `grep -rn "_TEXT_PROBENANSICHT_LINK" interview_theater/ tests/` — confirm
  it now has **zero** hits besides its own `_TEXT_PROBENANSICHT_LINK = (...)`
  definition (web.py:910-912). Delete that definition. Also check
  `interview_theater/sprachen/en/texte.toml` for a
  `_TEXT_PROBENANSICHT_LINK` entry under `["web"]` and delete it if present
  (grep first, do not assume).

  **Do not touch** `web.textbuch_koerper()`, `web.textbuch_html()`, the
  `/g/<token>/textbuch` route dispatch in `_beantworte_gruppenseite()`, or
  the `panels["textbuch"] = web.textbuch_koerper(...)` wiring in
  `web_vereint.py` — these are the Script tab itself and stay exactly as
  they are; only the duplicate link pointing at the same destination from
  inside the Arbeitsstand/Workbench content is removed.

- [ ] **Step 3: Add the regression assertion**

  Open `tests/test_web_vereint.py` (or `tests/test_web.py` — whichever
  already has a test asserting something about `gruppe_koerper()`'s or
  `seite()`'s HTML output for a token-bearing group; grep
  `def test_.*gruppe_koerper\|def test_.*stand.*panel` to find the closest
  existing test to extend) and add one assertion near it:

  ```python
  def test_kein_rehearsal_link_im_workbench_panel(...):
      """Birk: 'der Link zur Rehearsal view ist unsinnig, da identisch mit
      Script-Tab.' Die Script/Textbuch-Route bleibt erreichbar -- nur die
      zweite Verlinkung aus dem Arbeitsstand-Panel entfaellt."""
      ...
      html_ausgabe = web_vereint.seite(...)  # oder web.gruppe_koerper(...), je nach vorhandenem Testaufbau
      assert "/textbuch" not in html_ausgabe.split('id="tab-textbuch"')[0].rsplit('<section', 1)[0], \
          "kein Probenansicht-Link mehr vor dem Textbuch-Tab"
  ```

  Adapt the exact assertion to whatever fixture/helper the file you're
  extending already provides (it likely already builds a `daten` dict and
  calls `web.gruppe_koerper(daten, ...)` directly — in that case assert
  `"textbuch" not in ...` / `"Probenansicht" not in resultat` directly on
  that function's return value, which is simpler and more precise than
  string-slicing the whole page). Prefer the simplest correct assertion over
  the illustrative one above.

- [ ] **Step 4: Run the tests**

  ```bash
  pytest tests/test_web.py tests/test_web_vereint.py tests/test_sprache_texte.py -q
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add interview_theater/web.py tests/test_web_vereint.py  # or test_web.py, whichever you edited
  git commit -m "Remove the redundant rehearsal-view link from the Workbench/Arbeitsstand panel"
  ```

**Report:** `.superpowers/sdd/task-4-report.md` — state explicitly which
tab you confirmed the link rendered into (cross-checked against the Task 1
screenshot) and the exact test file/function you extended.

---

## Task 5: Padua profile switch + one-sentence phase description (foundation for Task 6)

This task lays the data/config groundwork so Task 6 can focus purely on the
stepper UI. It makes **no visible change** to any rendered page — it is pure
plumbing plus the safety net that proves Dortmund is unaffected.

**Files:**
- Modify: `interview_theater/workshop.py` (add `"phasennav_stepper": False`
  to the `[web]` table inside `VORGABE_WERTE`)
- Modify: `workshop/padua-2026/profil.toml` (add `phasennav_stepper = true`
  to the existing `[web]` section)
- Modify: `interview_theater/roadmap.py` (add a `"satz"` key to the per-phase
  dict in `aus_daten()`)
- Modify: `tests/test_roadmap.py` (if it enumerates exact dict keys, add
  `"satz"` to the expected set — check first, it may already iterate loosely)
- Create: `tests/fixtures/web_vereint_dortmund_vorher.html` (a committed
  snapshot of today's `web_vereint.seite()` output for Dortmund, generated
  with the **unmodified** code — generate this file in Step 1, **before**
  you touch any other file in this task)
- Create: `tests/test_web_vereint_bitgleich.py` (the Dortmund byte-identity
  test, modeled exactly on `tests/test_web_dashboard_en.py`)

**Interfaces:**
- Consumes: `workshop.aktiv().wert("web.<key>", <default>)` (the existing
  dotted-path profile lookup, `interview_theater/workshop.py:489-528` class
  `Profil`, method `wert`), `workshop.VARIABLE` (env var name),
  `workshop.vergiss()` / `sprache.vergiss()` (cache-busters, used in test
  setup — see `tests/test_web_dashboard_en.py:127-140` for the exact
  `_profil()`/`_frisch()` helper pattern to copy), `phasen.satz(nummer:
  int) -> str` (interview_theater/phasen.py:121-126, already public).
- Produces: `workshop.aktiv().wert("web.phasennav_stepper", False)` — the
  switch Task 6 reads to decide which roadmap markup to render.
  `roadmapdaten[i]["satz"]` — the one-sentence phase description (English
  text in Padua, German elsewhere, since `phasen.PHASEN`/`phasen.satz`
  already routes through the profile's own phase list — no new translation
  work needed here, it reuses existing per-profile phase data).

- [ ] **Step 1: Capture the Dortmund "before" fixture FIRST**

  Before changing any code, write a small script (or a throwaway pytest
  test you delete after use) that calls `web_vereint.seite(...)` with a
  realistic `daten`/`chatdaten`/`roadmapdaten` fixture (copy the fixture
  construction from `tests/test_web_vereint.py` — it already has one; grep
  for `def test_` + `seite(` there to find the exact call and its argument
  values) under the **default profile** (no `IT_WORKSHOP` set) and save the
  output to `tests/fixtures/web_vereint_dortmund_vorher.html`. This is your
  bitgleich baseline — generated from the code as it stands *right now*,
  before Steps 2-4 touch `roadmap.py`/`workshop.py`.

  Add a one-line module docstring note at the top of the new fixture file's
  companion test (not the HTML file itself) explaining it was generated
  before this task's changes, matching the convention in
  `tests/test_web_dashboard_en.py`'s own docstring.

- [ ] **Step 2: Add the profile switch**

  In `interview_theater/workshop.py`, find `VORGABE_WERTE["web"]` (around
  line 235-238):

  ```python
      "web": {
          "dashboard_log_einklappen": False,
          "dashboard_gestaltet": False,
      },
  ```

  change to:

  ```python
      "web": {
          "dashboard_log_einklappen": False,
          "dashboard_gestaltet": False,
          "phasennav_stepper": False,
      },
  ```

  In `workshop/padua-2026/profil.toml`, find the existing `[web]` section
  (around line 158-163):

  ```toml
  [web]
  dashboard_log_einklappen = true
  dashboard_gestaltet = true
  ```

  change to:

  ```toml
  [web]
  dashboard_log_einklappen = true
  dashboard_gestaltet = true
  phasennav_stepper = true
  ```

  **Do not touch `workshop/dortmund-2026/profil.toml`** — it has no `[web]`
  section at all today and must keep getting `False` purely from the new
  `VORGABE_WERTE` default.

- [ ] **Step 3: Add the one-sentence phase description to roadmap data**

  In `interview_theater/roadmap.py`, `aus_daten()` (around line 249-272),
  change the loop variable from `_satz` to `satz` and add it to the dict:

  ```python
      for nummer, name, satz in phasen.PHASEN:
          ...
          ergebnis.append({
              "nummer": nummer,
              "name": name,
              "satz": satz,
              "bezeichnung": phasen.bezeichnung(nummer),
              ...
          })
  ```

  Check `tests/test_roadmap.py` for any test that asserts the **exact** set
  of dict keys (e.g. `assert set(phase.keys()) == {...}` or
  `assert sorted(phase) == [...]`) — if one exists, add `"satz"` to the
  expected set. If tests only check individual keys (`phase["nummer"] ==
  ...`), no change is needed there.

- [ ] **Step 4: Write the bitgleich test**

  Create `tests/test_web_vereint_bitgleich.py`, copying the structure of
  `tests/test_web_dashboard_en.py` almost exactly:

  ```python
  """``web_vereint.seite()`` fuer Dortmund: byte-gleich wie vor der
  Padua-Stepper-Karte (Task 5/6, 2026-10-03).

  Die Vergleichsdatei ``tests/fixtures/web_vereint_dortmund_vorher.html`` ist
  mit dem Code VOR dieser Karte erzeugt worden (ohne Profil). Sie ist die
  Beweisgrundlage dafuer, dass Dortmund kein Zeichen anders sieht, nachdem
  Task 6 den Padua-Stepper hinter ``[web] phasennav_stepper`` einhaengt.
  """

  from pathlib import Path

  import pytest

  from interview_theater import sprache, web_vereint, workshop

  WURZEL = Path(__file__).resolve().parent.parent
  VORHER = WURZEL / "tests" / "fixtures" / "web_vereint_dortmund_vorher.html"


  def _profil(monkeypatch, name: str | None) -> None:
      if name is None:
          monkeypatch.delenv(workshop.VARIABLE, raising=False)
      else:
          monkeypatch.setenv(workshop.VARIABLE, name)
      workshop.vergiss()
      sprache.vergiss()


  @pytest.fixture(autouse=True)
  def _frisch():
      yield
      workshop.vergiss()
      sprache.vergiss()


  @pytest.mark.parametrize("profil", [None, "dortmund-2026"])
  def test_vereinte_seite_bleibt_byte_gleich(monkeypatch, profil):
      _profil(monkeypatch, profil)
      # <<< rufe web_vereint.seite(...) MIT DENSELBEN ARGUMENTEN wie beim
      # Erzeugen der Fixture in Schritt 1 auf >>>
      ausgabe = web_vereint.seite(...)
      assert ausgabe == VORHER.read_text(encoding="utf-8")


  @pytest.mark.parametrize("profil,erwartet", [
      (None, False), ("dortmund-2026", False), ("padua-2026", True),
  ])
  def test_phasennav_stepper_nur_im_padua_profil(monkeypatch, profil, erwartet):
      _profil(monkeypatch, profil)
      assert workshop.aktiv().wert("web.phasennav_stepper") is erwartet
  ```

  Fill in the `web_vereint.seite(...)` call with the **exact same
  arguments** you used in Step 1 to generate the fixture — copy them
  verbatim from the fixture-generation script/test so the comparison is
  apples-to-apples. If `seite()` embeds anything non-deterministic (a
  timestamp, a random nonce), check `web.nonce()`'s signature — it is
  deterministic given the same `schluessel`/`token`/hour window per
  `AGENTS.md` ("CSRF: ... ein Formular-Nonce aus Token und Stundenfenster"),
  so this should already be stable across runs within the same clock hour;
  if your fixture generation and your test run happen to straddle an hour
  boundary and the nonce differs, either freeze time in the test
  (`monkeypatch` the relevant clock read) or regenerate the fixture
  immediately before running the test — do not weaken the test by stripping
  the nonce out of the comparison.

- [ ] **Step 5: Run the tests**

  ```bash
  pytest tests/test_web_vereint_bitgleich.py tests/test_roadmap.py tests/test_web_vereint.py -q
  IT_WORKSHOP=dortmund-2026 python -m scripts.pruefe_profil
  IT_WORKSHOP=padua-2026 python -m scripts.pruefe_profil
  ```

- [ ] **Step 6: Commit**

  ```bash
  git add interview_theater/workshop.py interview_theater/roadmap.py \
          workshop/padua-2026/profil.toml tests/test_web_vereint_bitgleich.py \
          tests/fixtures/web_vereint_dortmund_vorher.html tests/test_roadmap.py
  git commit -m "Add phasennav_stepper profile switch (Padua only) and per-phase one-sentence description to roadmap data"
  ```

**Report:** `.superpowers/sdd/task-5-report.md` — state the exact
`web_vereint.seite(...)` call signature/arguments used for the fixture, so
Task 6's reviewer can verify the bitgleich test still calls it identically
after Task 6 lands.

---

## Task 6: Padua phase stepper, prev/next arrows, and bottom sheet (replaces the two-click arm/confirm UI, Padua only)

This is the largest task. It implements the "BINDING ADDITION" from Birk's
23:10 follow-up comment, entirely gated behind
`workshop.aktiv().wert("web.phasennav_stepper", False)` (added in Task 5).
Dortmund's rendering path through `_leiste_html()` must stay **completely
untouched** — add a new branch, never modify the existing one in place.

**Files:**
- Modify: `interview_theater/web_vereint.py` (branch `_leiste_html()` on the
  new switch; add the stepper/sheet HTML-building function; add the
  stepper/sheet JS; add new `_TEXT_*` constants)
- Modify: `interview_theater/web_gestalt.py` (add stepper/sheet CSS,
  theme-token-based, in `_ROADMAP` or a new constant — your call, keep
  `css_rahmen()`'s assembly order documented)
- Modify: `interview_theater/sprachen/en/texte.toml` (English entries for
  every new `_TEXT_*` constant added to `web_vereint.py`)
- Create: `tests/e2e/test_web_phasenstepper_e2e.py`

**Interfaces:**
- Consumes: `workshop.aktiv().wert("web.phasennav_stepper", False)`,
  `roadmapdaten[i]["satz"]`/`["bezeichnung"]`/`["bereit"]`/`["fehlt"]`/
  `["aktiv"]`/`["nummer"]`/`["name"]` (all from Task 5 + the pre-existing
  roadmap dict), the existing `POST /g/<token>/chat/phase` endpoint
  (`phase_post()`, `web_vereint.py:1087-1118` — unchanged, body shape
  `{"nonce": ..., "nummer": <int>, "bestaetigt": 1}`), the existing
  `sendePhase`/`friskeNonce`/`zeigeFehler` JS functions in `_VEREINT_JS`
  (reuse them as-is for the sheet's "Go to" button — do not duplicate the
  nonce-retry logic).
- Produces: nothing consumed by a later task in this plan — Task 7 only
  screenshots and verifies this task's output.

**Known, explicitly-flagged ambiguity (do not silently resolve, carry it into
your report as the plan does here):** Birk's comment says the sheet's status
indicator should use "🟢/🔴 wie Workbench, Karte t_49e7354c, gleiche
Datenquelle" — card `t_49e7354c` is **not present in this codebase/branch**
(confirmed: zero occurrences of 🟢/🔴 as a status glyph anywhere in
`interview_theater/*.py` on this branch, and no file/commit reference to that
card id). Implement the status using the **existing** `bereit`/`fehlt` data
already driving the current two-click arm logic (`🟢` when `phase["bereit"]`
is true or the phase is `erledigt`/`aktiv` with nothing missing, `🔴` plus a
`"Still open: {fehlt}"` line when not) as the closest available equivalent
"same data source" reading, since that is the actual, only readiness signal
this roadmap data carries. State this substitution explicitly in your task
report — it is a plan-level assumption, not a silent judgment call.

- [ ] **Step 1: Define the phase-status helper and new `_TEXT_*` constants**

  In `web_vereint.py`, near the existing `_TEXT_PHASE_*` constants
  (web_vereint.py:1063-1084), add:

  ```python
  _TEXT_SHEET_STATUS_OFFEN = "Still open: {was}"
  _TEXT_SHEET_STATUS_BEREIT = "Ready"
  _TEXT_SHEET_GEHE_ZU = "Go to {bezeichnung}"
  _TEXT_SHEET_BLEIBE = "Stay here"
  _TEXT_STEPPER_HINWEIS = "Tap a phase to move between steps."
  ```

  (These are English-first because `padua-2026` is the only profile this
  code path ever renders for — but the constant still needs a German
  default value per `sprache.Texte`'s contract, since `code()` falls back to
  the module constant verbatim when the active language is German; since
  this whole branch only ever renders under the Padua/English profile in
  practice, write the German value as a literal, sensible German
  translation anyway — do not leave it in English, `tests/test_anweisungen.py`-style
  conventions in this repo do not special-case "this will never actually be
  read in German". Example:
  `_TEXT_SHEET_BLEIBE = "Hier bleiben"`, then the **English** entry in
  `texte.toml` carries `"Stay here"`.)

  Add the English counterparts to `interview_theater/sprachen/en/texte.toml`
  under `["web_vereint"]` (grep the file for `["web_vereint"]` to find the
  existing table and append inside it, matching the bracket-quoted-table
  TOML format already used there).

- [ ] **Step 2: Build the stepper + sheet HTML**

  Add a new function in `web_vereint.py`, parallel to `_leiste_html()`:

  ```python
  def _stepper_html(roadmapdaten: list[dict], klickbar: bool = True) -> str:
      """Padua-Stepper (Birk 03.10.2026 23:10): sieben nummerierte Segmente
      statt eines zugeklappten ``<details>``, Pfeile links/rechts der
      aktiven Phase, ein Tap oeffnet das Bottom-Sheet statt der
      Zwei-Klick-Bewaffnung. Nur gerendert, wenn
      ``workshop.aktiv().wert("web.phasennav_stepper")`` wahr ist -- der
      Aufrufer entscheidet, ``_leiste_html`` bleibt fuer Dortmund
      unangetastet."""
      if not roadmapdaten:
          return ""
      aktiv = next((p for p in roadmapdaten if p["aktiv"]), roadmapdaten[0])
      idx = roadmapdaten.index(aktiv)
      vorherige = roadmapdaten[idx - 1] if idx > 0 else None
      naechste = roadmapdaten[idx + 1] if idx + 1 < len(roadmapdaten) else None

      segmente = []
      for phase in roadmapdaten:
          zustand = (
              "erledigt" if phase["nummer"] < aktiv["nummer"]
              else "aktiv" if phase["nummer"] == aktiv["nummer"]
              else "kommend"
          )
          marke = "✓" if zustand == "erledigt" else str(phase["nummer"])
          fehlt_text = ", ".join(phase.get("fehlt") or ())
          segmente.append(
              f'<li class="stepper-segment {zustand}" data-phase="{phase["nummer"]}" '
              f'data-bezeichnung="{html.escape(phase["bezeichnung"], quote=True)}" '
              f'data-satz="{html.escape(phase.get("satz") or "", quote=True)}" '
              f'data-bereit="{"0" if phase.get("bereit") is False else "1"}" '
              f'data-fehlt="{html.escape(fehlt_text, quote=True)}" '
              f'role="button" tabindex="0" aria-label="{html.escape(phase["bezeichnung"], quote=True)}">'
              f'<span class="stepper-marke">{marke}</span></li>'
          ) if klickbar else (
              f'<li class="stepper-segment {zustand}">'
              f'<span class="stepper-marke">{marke}</span></li>'
          )

      def pfeil(ziel, richtung, css_klasse):
          if ziel is None:
              return f'<span class="{css_klasse}" aria-hidden="true"></span>'
          pfeilzeichen = "‹ " if richtung == -1 else " ›"
          text = f"{pfeilzeichen}{html.escape(ziel['name'])}" if richtung == -1 \
              else f"{html.escape(ziel['name'])}{pfeilzeichen}"
          if not klickbar:
              return f'<span class="{css_klasse}">{text}</span>'
          return (
              f'<button type="button" class="{css_klasse}" '
              f'data-phase="{ziel["nummer"]}" '
              f'data-bezeichnung="{html.escape(ziel["bezeichnung"], quote=True)}" '
              f'data-satz="{html.escape(ziel.get("satz") or "", quote=True)}" '
              f'data-bereit="{"0" if ziel.get("bereit") is False else "1"}" '
              f'data-fehlt="{html.escape(", ".join(ziel.get("fehlt") or ()), quote=True)}">'
              f'{text}</button>'
          )

      sheet = (
          '<div class="sheet" id="phasensheet" hidden role="dialog" aria-modal="true" '
          'aria-labelledby="phasensheet-titel">'
          '<div class="sheet-hintergrund"></div>'
          '<div class="sheet-inhalt">'
          '<h3 id="phasensheet-titel"></h3>'
          '<p id="phasensheet-satz"></p>'
          '<p id="phasensheet-status"></p>'
          '<div class="sheet-knoepfe">'
          '<button type="button" id="phasensheet-los"></button>'
          f'<button type="button" id="phasensheet-bleib">{html.escape(T._TEXT_SHEET_BLEIBE)}</button>'
          '</div></div></div>'
      ) if klickbar else ""

      hinweis = (
          f'<p class="stepper-hinweis" id="stepper-hinweis" hidden>'
          f'{html.escape(T._TEXT_STEPPER_HINWEIS)}</p>'
      ) if klickbar else ""

      return (
          f'<header class="phasenav" id="roadmap" data-stepper="1" '
          f'data-aktive-phase="{aktiv["nummer"]}">'
          f'<ol class="stepper" role="list">{"".join(segmente)}</ol>'
          f'<div class="phasenav-zeile">'
          f'{pfeil(vorherige, -1, "phasenav-zurueck")}'
          f'<span class="phasenav-aktuell">{html.escape(aktiv["bezeichnung"])}</span>'
          f'{pfeil(naechste, 1, "phasenav-vor")}'
          f'</div>'
          f'<p id="ux-naechstes" hidden></p>'
          f'{hinweis}'
          f'</header>\n{sheet}'
      )
  ```

  (`id="roadmap"` and `data-aktive-phase` are kept on the new `<header>` on
  purpose — `web_vereint._VEREINT_JS`'s `istPhase4()` and the CoThinker-tab
  visibility logic read `document.getElementById('roadmap').dataset
  .aktivePhase`, and `_roadmap_html()`/`ladeRoadmap()`'s `/teil/roadmap`
  polling swap targets `#roadmap` by id too — reusing the id means the
  existing polling/swap machinery keeps working for Padua without
  modification. Verify this by reading `_roadmap_html()` and `ladeRoadmap()`
  yourself before assuming it; if the swap logic assumes `#roadmap` is
  specifically a `<details>` element — e.g. reads `.open` — adjust
  `ladeRoadmap()` to skip that `.open`-preserving step when
  `roadmap.dataset.stepper === '1'`.)

  In `seite()`, change the line that currently always calls
  `_leiste_html(...)`:

  ```python
      koerper = [_leiste_html(roadmapdaten, klickbar=chat_vorhanden),
                _tabs_html(vorgabe, tabs, phase4=phase4)]
  ```

  to:

  ```python
      from interview_theater import workshop
      kopf_html = (
          _stepper_html(roadmapdaten, klickbar=chat_vorhanden)
          if workshop.aktiv().wert("web.phasennav_stepper", False)
          else _leiste_html(roadmapdaten, klickbar=chat_vorhanden)
      )
      koerper = [kopf_html, _tabs_html(vorgabe, tabs, phase4=phase4)]
  ```

  Also update `_roadmap_html()` (the `/teil/roadmap` endpoint body,
  web_vereint.py:1365 area) with the same branch, so the polling endpoint
  returns stepper markup for Padua and details markup for Dortmund,
  consistently.

- [ ] **Step 3: Write the stepper/sheet CSS**

  Add a new constant in `web_gestalt.py` (e.g. `_STEPPER`, appended inside
  `css_rahmen()`'s tuple **only when the switch is on** — but
  `css_rahmen()` has no DB/profile access per its "importiert nichts ausser
  sprache" constraint; instead always include `_STEPPER`'s CSS
  unconditionally in `css_rahmen()`'s output — it only ever matches markup
  that Padua renders, so on Dortmund it is simply dead/unmatched CSS, which
  does **not** violate the bitgleich test because that test compares
  `web_vereint.seite()`'s full output including the `<style>` block... **this
  means the Task 5 bitgleich fixture will break the moment you add any CSS
  text to `css_rahmen()`, even unmatched CSS, because the `<style>` block's
  text changes.** Resolve this by **not** adding the new CSS to
  `css_rahmen()` at all — instead add a new `css_stepper()` function
  (parallel to `css_buehne()`/`css_stand()`) and append its output in
  `web_vereint.seite()` **only when the switch is on**:

  ```python
      if workshop.aktiv().wert("web.phasennav_stepper", False):
          css += web_gestalt.css_stepper()
  ```

  right after the `_css_schale(...)` line. This keeps Dortmund's `<style>`
  block (and therefore the Task 5 bitgleich fixture) untouched.

  Write `css_stepper()` using only `var(--...)` tokens, minimum 44px
  (`var(--tippflaeche)` is already `2.75rem` ≈ 44px — reuse it, do not
  invent a new size) tap targets for every `.stepper-segment`,
  `.phasenav-zurueck`/`.phasenav-vor`, and the two sheet buttons:

  ```python
  def css_stepper(name: str | None = None) -> str:
      """Der Padua-Stepper (BINDING ADDITION, 03.10.2026 23:10) -- nur
      angehaengt, wenn ``[web] phasennav_stepper`` an ist (siehe
      ``web_vereint.seite()``). Deshalb UNGESCOPT wie ``css_rahmen()``, aber
      eine eigene Funktion: ``css_rahmen()`` selbst muss fuer Dortmund
      byte-gleich bleiben."""
      return _STEPPER


  _STEPPER = """
  header.phasenav { position: sticky; top: 0; z-index: 4;
                     background: var(--grund); border-bottom: 1px solid var(--linie);
                     padding: .5rem .75rem; display: flex; flex-direction: column;
                     gap: .35rem; max-width: 44rem; margin: 0 auto; }
  .stepper { display: flex; gap: .3rem; list-style: none; margin: 0; padding: 0;
             justify-content: space-between; }
  .stepper-segment { flex: 1 1 0; min-height: var(--tippflaeche);
                      min-width: var(--tippflaeche); display: flex;
                      align-items: center; justify-content: center;
                      border-radius: var(--radius); border: 1px solid var(--rand);
                      background: var(--grund-2); color: var(--text-leise);
                      cursor: pointer; font-family: var(--schrift-tech); }
  .stepper-segment.erledigt { color: var(--signal); border-color: var(--signal); }
  .stepper-segment.aktiv { color: var(--auf-warn); background: var(--warn);
                            border-color: var(--warn); font-weight: 700; }
  .stepper-segment.kommend { opacity: .6; }
  .phasenav-zeile { display: flex; align-items: center; justify-content: space-between;
                     gap: .4rem; }
  .phasenav-zurueck, .phasenav-vor {
      min-height: var(--tippflaeche); font: inherit; background: transparent;
      color: var(--signal); border: 0; padding: 0 .3rem; cursor: pointer;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 40%; }
  .phasenav-aktuell { color: var(--text); font-weight: 600; text-align: center;
                       flex: 1 1 auto; min-width: 0; overflow: hidden;
                       text-overflow: ellipsis; white-space: nowrap; }
  .stepper-hinweis { font-size: .82rem; color: var(--text-leise); margin: 0; }
  .sheet { position: fixed; inset: 0; z-index: 11; display: flex;
           align-items: flex-end; }
  .sheet[hidden] { display: none; }
  .sheet-hintergrund { position: absolute; inset: 0; background: rgba(0,0,0,.5); }
  .sheet-inhalt { position: relative; z-index: 1; width: 100%; max-width: 44rem;
                  margin: 0 auto; background: var(--grund-2); color: var(--text);
                  border-radius: var(--radius-gross) var(--radius-gross) 0 0;
                  padding: 1rem 1.1rem calc(1.2rem + env(safe-area-inset-bottom));
                  border: 1px solid var(--linie); }
  .sheet-inhalt h3 { margin: 0 0 .3rem; font-family: var(--schrift-skript); }
  .sheet-inhalt p { margin: 0 0 .5rem; color: var(--text-leise); }
  .sheet-knoepfe { display: flex; gap: .5rem; margin-top: .6rem; }
  .sheet-knoepfe button { flex: 1 1 0; min-height: var(--tippflaeche); font: inherit;
                           border-radius: var(--radius); border: 1px solid var(--rand);
                           background: var(--grund-3); color: var(--text); }
  #phasensheet-los { background: var(--signal); color: var(--auf-signal);
                      border-color: var(--signal); font-weight: 600; }
  """
  ```

  Add the three new token-pairs this introduces to `KONTRAST` in
  `web_gestalt.py` if they are not already covered by an existing `Paar`
  (check: `("auf-warn", "warn")` already exists; `("text", "grund-2")`
  already exists; `("signal", "grund-2")` already exists;
  `("auf-signal", "signal")` already exists — likely **no new `Paar`
  needed**, confirm by reading `KONTRAST` yourself rather than trusting this
  claim blindly).

- [ ] **Step 4: Write the stepper/sheet JS**

  Add a new JS block in `web_gestalt.py`'s `skript()` assembly (or as a new
  constant appended the same conditional way as `css_stepper()` — in
  `web_vereint.py`, inside the `if workshop.aktiv().wert(...)` branch from
  Step 2/3, also append a new JS string). Put the JS in `web_vereint.py`
  this time (not `web_gestalt.py`) since it needs to call the existing
  `sendePhase`/`friskeNonce` functions that live inside `_VEREINT_JS`'s own
  closure — the simplest correct placement is **inside `_VEREINT_JS`
  itself**, guarded by a runtime check for the stepper markup's presence
  (`document.querySelector('.phasenav')`), so it is a no-op on Dortmund
  (where that selector never matches) without needing a second script
  string or a second IIFE:

  Inside `_VEREINT_JS`, after the existing `document.addEventListener('click', ...)` block that already
  handles `.phase-knopf`/`.phase-abbrechen`/`.tabs button`/`[data-ziel-tab]`
  (web_vereint.py:814-856), add a **second**, independent click listener
  (do not interleave it with the existing one — keep the existing listener
  byte-for-byte unchanged, since it is Dortmund's code path):

  ```javascript
    // Padua-Stepper (nur wirksam, wenn das Markup da ist -- auf Dortmund
    // trifft keiner dieser Selektoren je zu).
    var sheetOffenFuer = null;
    function zeigeHinweisEinmal() {
      var hinweis = document.getElementById('stepper-hinweis');
      if (!hinweis) { return; }
      try {
        if (localStorage.getItem('it_stepper_hinweis_gesehen')) { return; }
      } catch (e) { return; }
      hinweis.hidden = false;
    }
    zeigeHinweisEinmal();
    function verbergeHinweis() {
      var hinweis = document.getElementById('stepper-hinweis');
      if (hinweis) { hinweis.hidden = true; }
      try { localStorage.setItem('it_stepper_hinweis_gesehen', '1'); } catch (e) {}
    }
    function oeffneSheet(quelle) {
      var sheet = document.getElementById('phasensheet');
      if (!sheet || !quelle) { return; }
      sheetOffenFuer = quelle;
      document.getElementById('phasensheet-titel').textContent = quelle.dataset.bezeichnung || '';
      document.getElementById('phasensheet-satz').textContent = quelle.dataset.satz || '';
      var bereit = quelle.dataset.bereit !== '0';
      var status = document.getElementById('phasensheet-status');
      status.textContent = bereit ? __SHEET_STATUS_BEREIT__
        : __SHEET_STATUS_OFFEN__.replace('{was}', quelle.dataset.fehlt || '');
      document.getElementById('phasensheet-los').textContent =
        __SHEET_GEHE_ZU__.replace('{bezeichnung}', quelle.dataset.bezeichnung || '');
      sheet.hidden = false;
      verbergeHinweis();
    }
    function schliesseSheet() {
      var sheet = document.getElementById('phasensheet');
      if (sheet) { sheet.hidden = true; }
      sheetOffenFuer = null;
    }
    document.addEventListener('click', function (ev) {
      var segment = ev.target.closest ? ev.target.closest('.stepper-segment') : null;
      if (segment && segment.dataset.phase) { oeffneSheet(segment); return; }
      var pfeilKnopf = ev.target.closest ? ev.target.closest('.phasenav-zurueck, .phasenav-vor') : null;
      if (pfeilKnopf && pfeilKnopf.tagName === 'BUTTON') { oeffneSheet(pfeilKnopf); return; }
      if (ev.target.closest && ev.target.closest('#phasensheet-bleib')) { schliesseSheet(); return; }
      if (ev.target.closest && ev.target.closest('.sheet-hintergrund')) { schliesseSheet(); return; }
      var los = ev.target.closest ? ev.target.closest('#phasensheet-los') : null;
      if (los && sheetOffenFuer) {
        var phase = sheetOffenFuer;
        los.disabled = true;
        sendePhase(phase).then(function (r) {
          los.disabled = false;
          if (r && r.ok) {
            schliesseSheet();
            ladeRoadmap();
            setze('chat');
            return;
          }
          if (r) {
            r.text().then(function (satz) { zeigeFehler((satz || '').trim()); },
                         function () { zeigeFehler(''); });
          } else {
            zeigeFehler('');
          }
        }).catch(function () { los.disabled = false; zeigeFehler(''); });
      }
    });
  """
  ```

  Replace the three `__SHEET_*__` placeholders the same way the existing
  code replaces `__FEHLT__`/`__FEHLER_NETZ__` (`.replace('__FEHLT__',
  _js_text(T._TEXT_PHASE_FEHLT_HINWEIS))` pattern,
  `web_vereint.py:1328-1333` area) — add three more `.replace(...)` calls in
  `seite()`'s existing `_VEREINT_JS.replace(...)` chain, using `_js_text()`
  on `T._TEXT_SHEET_STATUS_BEREIT`, `T._TEXT_SHEET_STATUS_OFFEN`,
  `T._TEXT_SHEET_GEHE_ZU`.

  `sendePhase`, `zeigeFehler`, `ladeRoadmap`, `setze` are all already
  defined earlier in the same `_VEREINT_JS` function scope (verify this by
  reading the full function before you add code — they must be in scope at
  the point you call them; if `_VEREINT_JS`'s structure makes that not true,
  adjust by moving your new code to after their definitions within the same
  IIFE, not by redefining them).

- [ ] **Step 5: Write the e2e tests**

  Create `tests/e2e/test_web_phasenstepper_e2e.py`. Server/fixture pattern:
  same as other e2e files, but start the server with
  `IT_WORKSHOP=padua-2026` in its environment (see `server` fixture pattern
  in `tests/e2e/test_web_vereint_e2e.py` — add
  `umgebung["IT_WORKSHOP"] = "padua-2026"` to its `umgebung` dict). Build a
  fixture group with at least 3 distinct phase-readiness states (one past
  phase fully done, the active phase, one future phase not ready) so the
  sheet's two status branches are both exercised.

  Required tests (per the card's own acceptance bullet 6):

  ```python
  def test_tap_auf_segment_oeffnet_sheet_mit_name_und_status(...):
      ...
      seite.click('.stepper-segment[data-phase="4"]')
      seite.wait_for_selector("#phasensheet:not([hidden])")
      assert seite.locator("#phasensheet-titel").inner_text()
      assert seite.locator("#phasensheet-status").inner_text()

  def test_gehe_zu_wechselt_die_phase_per_post(...):
      ...
      # Abhoeren auf den POST, wie es test_web_vereint_e2e.py schon tut
      # (``seite.on("request", ...)`` oder direkter DB-Blick nach dem Klick)
      seite.click('.stepper-segment[data-phase="4"]')
      seite.click("#phasensheet-los")
      # assert: POST /g/<token>/chat/phase gesendet; roadmap zeigt neue Phase

  def test_hier_bleiben_schliesst_ohne_post(...):
      ...
      seite.click('.stepper-segment[data-phase="4"]')
      seite.click("#phasensheet-bleib")
      assert seite.locator("#phasensheet").is_hidden()
      # assert: kein POST gesendet (Phase im DB-Zustand unveraendert)

  def test_pfeile_oeffnen_dasselbe_sheet(...):
      ...
      seite.click(".phasenav-vor")
      seite.wait_for_selector("#phasensheet:not([hidden])")

  @pytest.mark.parametrize("breite_px,soll_gruen", [(44, True), (24, False)])
  def test_tapflaeche_mindestens_44px(server, browser, token, breite_px, soll_gruen):
      """Mutationstest eingebaut: mit 24px simulierter Mindestgroesse muss
      das hier false liefern -- bewiesen ueber eine direkte Messung der
      tatsaechlich gerenderten Groesse, nicht ueber den Quelltext."""
      ...
      kasten = seite.locator(".stepper-segment").first.bounding_box()
      ist_gross_genug = kasten["width"] >= 44 and kasten["height"] >= 44
      if breite_px == 44:
          assert ist_gross_genug
      # fuer den 24px-Fall: setze per CSSOM-Override (nicht Quelltextaenderung)
      # eine kleinere min-width/min-height auf .stepper-segment im Browser und
      # pruefe, dass DANN ist_gross_genug false ist -- das ist der
      # Mutationsbeweis, nicht eine zweite Quelldatei.

  def test_kein_zwei_klick_data_sicher_im_padua_markup(...):
      ...
      html_ausgabe = seite.content()
      assert 'data-sicher' not in html_ausgabe
  ```

  For the `44px`/`24px` parametrized mutation test, the cleanest real
  mutation is: load the page normally, assert ≥44px; then use
  `seite.evaluate("document.querySelectorAll('.stepper-segment').forEach(el => el.style.setProperty('min-width', '24px'))")`
  followed by `.style.setProperty('min-height', '24px')` and re-measure,
  asserting the measurement now correctly reports "too small" — this proves
  the **test's own measurement logic** is sensitive to the regression it's
  meant to catch, which is what "Mutant: 24px → rot" means (do not literally
  edit `_STEPPER`'s source CSS to 24px as your mutation check — that would
  require reverting a committed change; a live CSSOM override in the test
  itself is the correct, repeatable way to prove sensitivity without ever
  committing broken CSS).

  Write the `test_gehe_zu_wechselt_die_phase_per_post`/
  `test_hier_bleiben_schliesst_ohne_post` POST-observation using whichever
  mechanism `tests/e2e/test_web_vereint_e2e.py` already uses to detect a
  phase change (it has its own existing tests clicking `.phase-knopf` twice
  and asserting on `repo`-read DB state afterward — follow that exact
  pattern, reading the chat_id's current phase via `repo.lese_arbeitsstand`
  or similar from a direct `conn` fixture, rather than inventing a new
  detection mechanism).

- [ ] **Step 6: Run the tests**

  ```bash
  pytest tests/test_web_vereint.py tests/test_web_vereint_bitgleich.py tests/test_sprache_texte.py tests/test_web_gestalt_tokens.py -q
  IT_WORKSHOP=padua-2026 python -m scripts.pruefe_profil
  IT_WORKSHOP=dortmund-2026 python -m scripts.pruefe_profil
  /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest tests/e2e/test_web_phasenstepper_e2e.py tests/e2e/test_web_vereint_e2e.py -q
  ```

  `tests/test_web_vereint_bitgleich.py` (from Task 5) must **still pass**
  after this task — if it fails, you have leaked something Padua-only into
  Dortmund's unconditional code path (most likely: CSS added to
  `css_rahmen()` instead of the new conditional `css_stepper()`, or a
  changed `_leiste_html()` instead of a new `_stepper_html()`). Fix the
  leak, do not weaken the bitgleich test.

- [ ] **Step 7: Commit**

  ```bash
  git add interview_theater/web_vereint.py interview_theater/web_gestalt.py \
          interview_theater/sprachen/en/texte.toml tests/e2e/test_web_phasenstepper_e2e.py
  git commit -m "Add Padua phase stepper with prev/next arrows and bottom sheet, gated behind [web] phasennav_stepper"
  ```

**Report:** `.superpowers/sdd/task-6-report.md` — explicitly restate the
🟢/🔴 data-source substitution ambiguity and your resolution; confirm the
Task 5 bitgleich test is still green after this task; list the exact
mutation-check method you used for the 44px test.

---

## Task 7: "After" screenshots + full verification sweep

**Files:** none modified (verification only), plus
`docs/ux-padua/kopfzeile/nachher/` (new screenshots).

**Interfaces:** none — this task consumes the finished state of Tasks 1-6
and produces the final evidence the card's "Abnahme" section requires.

- [ ] **Step 1: "After" screenshots, Dortmund profile**

  Reuse (or rewrite, same approach as Task 1) a throwaway screenshot script.
  Capture the same 4 tabs × 2 viewports as Task 1, this time against the
  **current** code (no `IT_WORKSHOP` set, or `IT_WORKSHOP=dortmund-2026` —
  either is fine since they must render identically per Task 5/6's
  bitgleich tests), saved to
  `docs/ux-padua/kopfzeile/nachher/<tab>-<viewport>.png`.

- [ ] **Step 2: "After" screenshots, Padua stepper**

  With `IT_WORKSHOP=padua-2026` in the server's environment, capture three
  additional screenshots per the card's explicit request ("Screenshots
  Handy: Stepper geschlossen, Sheet offen, nach dem Wechsel"), at the HANDY
  viewport:
  - `docs/ux-padua/kopfzeile/nachher/padua-stepper-geschlossen.png` (stepper
    visible, sheet closed)
  - `docs/ux-padua/kopfzeile/nachher/padua-sheet-offen.png` (tap a segment,
    sheet open)
  - `docs/ux-padua/kopfzeile/nachher/padua-nach-wechsel.png` (after clicking
    "Go to ...", wait for the roadmap to reflect the new active phase)

- [ ] **Step 3: Visual self-check against Task 1's report**

  Open both the `vorher/buehne-handy.png` and `nachher/buehne-handy.png`
  side by side (describe what you see in your report — e.g. "vorher: white
  cards, unreadable; nachher: dark cards matching the theme, readable") and
  the same for `stand-handy.png`/`chat-handy.png` (overlap gone). This is a
  manual visual sanity check, not an automated assertion — the automated
  proof already lives in Tasks 2-6's e2e tests; this step is the human-facing
  evidence the card's "Abnahme" section asks for ("nicht per Behauptung").

- [ ] **Step 4: Full verification sweep**

  Run, in order, and capture the **last line + exit code** of each:

  ```bash
  pytest
  IT_WORKSHOP=dortmund-2026 python -m scripts.pruefe_profil
  IT_WORKSHOP=padua-2026 python -m scripts.pruefe_profil
  pytest tests/test_profil_bitgleich.py -q
  /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest tests/e2e/ -q -m e2e
  ```

  (If the dedicated Playwright venv path is unavailable in your execution
  environment, state that explicitly and run whatever interpreter has
  `playwright` installed, or state that the e2e suite could not be executed
  in this environment — do not claim a green e2e run you did not actually
  execute.)

  If any of these is not green, do **not** proceed to commit — go back to
  the task that caused the regression, fix it there (re-open that task's own
  work, do not patch around it from here), re-run that task's own tests,
  then re-run this full sweep from the top.

- [ ] **Step 5: Commit**

  ```bash
  git add docs/ux-padua/kopfzeile/nachher/
  git commit -m "Capture after-screenshots and record full verification sweep for Padua UX header card"
  ```

**Report:** `.superpowers/sdd/task-7-report.md` — the last line + exit code
of every command in Step 4, verbatim, plus the visual self-check from Step
3.
