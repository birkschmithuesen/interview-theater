# Padua Browser UX Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking. **Exception:** Task 10 is not a
> coding task — it spends real money against the live model chain and needs live
> supervision for the operator fallback. The controller (the agent running this
> plan, not a dispatched implementer subagent) executes Task 10 directly.

**Goal:** Build `python -m simulation.browser_lauf` — a tool that drives the real
Padua group web page in a real headless Chromium browser via an Opus-played
persona, screenshots every step, counts mechanical UX defects, has Opus judge each
phase against `participatory-bot-ux`, and writes a Markdown report + contact
sheets. Then actually run it (phone, phases 1–7; laptop, phases 1–4) against the
real model chain and commit the reports.

**Architecture:** A new `simulation/browser_*.py` module family, flat like the rest
of `simulation/`, split by concern: element extraction, mechanical counters,
persona decision-making, the real-stack process manager, the action executor,
per-step recording (screenshots + DB diff), the phase judge, and the Markdown/PNG
report. `browser_lauf.py` wires them into one `fuehre_lauf()` function that a thin
`main()` wraps for the real run, and that tests call directly with fakes/stubs —
exactly the split `tests/test_web_e2e_http.py` and `simulation/lauf.py` already use
(real `interview_theater` code, attrappe model, no subprocess) for their own
integration tests.

**Tech Stack:** Python 3.11 stdlib + `httpx` (already a dependency) + Playwright
1.61.0 (new, installed into the project's own interpreter — see Global Constraints).
No other new dependency (no Pillow: the contact sheet is a Playwright screenshot of
an HTML `<img>` grid, like `simulation/claude.py`'s proxy client plus a second,
image-capable request).

## Global Constraints

- **Python:** `PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`.
  No project `.venv`. This interpreter already has `httpx`. Playwright must be
  installed into it directly (`"$PY" -m pip install --break-system-packages
  "playwright==1.61.0"` — `pip install` without `--break-system-packages` fails
  with `externally-managed-environment` on this host; verified working this
  session). **Do not run `playwright install chromium`** — the browser revision
  this version expects (`chromium-1228`) is already cached under
  `~/.cache/ms-playwright/`; a fresh `playwright install` would try to redownload.
  Verified working this session: `chromium.launch()` succeeds with no sandbox
  flag needed, from inside this worktree, without any special permission.
- **Full test suite command (must stay green after every task):**
  `env -i HOME=$HOME PATH=/usr/bin:/bin $PY -m pytest -q -p no:cacheprovider`.
  Because Playwright is now installed in `$PY`, this command will actually
  **execute** `tests/e2e/*.py` too (they only `importorskip`-skip when Playwright
  is absent) — budget 5–15 minutes, do not reduce scope to dodge this.
- **Opus proxy (persona + judge):** `http://127.0.0.1:28764/v1/messages`, model
  `claude-opus-5`, Anthropic Messages format, **no** `Authorization` header (the
  proxy sets it). This is `simulation/claude.py`'s existing client — extend it,
  don't replace it. Verified working this session, including image input
  (`{"type": "image", "source": {"type": "base64", "media_type": "image/png",
  "data": ...}}` content blocks). This endpoint is a subscription and costs
  nothing per call — persona/judge tests and the real run may call it freely,
  but keep calls **sequential** (no parallel requests against it from one run).
- **Real bot model-chain credentials:** sourced **at runtime only**, via a bash
  `source` of `/mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-test.env`
  (path passed via a CLI option / `IT_SIM_ENV` env var). **No Python code in this
  repo ever reads that file's contents** — only a generated bash script does
  (`set -a; source "$ENV_FILE"; set +a; export <overrides>; exec $PY -m
  interview_theater.bot`), so nothing in this codebase can log, print, or commit
  a key. Overrides exported *after* the `source` line win: `IT_DB=<temp>`,
  `IT_AUDIO=<temp>`, `IT_KANAL=web`, `IT_WEB_CHAT_ID=<created id>`,
  `IT_WORKSHOP=padua-2026`, `IT_BOT_NAME=padua-browser-sim`, `IT_WEB_URL=""`.
  Do **not** override `IT_SZENE_ANBIETER`/`IT_SZENE_MODELL`/`IT_LLM_*`/`IT_STT_*`/
  `IT_KOSTEN_DECKEL_CHF` — whatever `padua-test.env` sets for those is the real
  configuration under test.
- **Never:** touch `betrieb/padua.db` or any file under `betrieb/` for writing;
  use ports 8010 or 8030; start/stop a systemd unit; open any database other than
  a temp one created by this run; print or commit a secret value.
- **Dortmund profile stays byte-identical** — do not touch `workshop/dortmund-2026/`
  or `workshop.VORGABE_*`.
- **Only invented material** (`simulation/interviews/*`) — never a live DB, never
  real transcripts.
- **No new pip dependency besides Playwright.** No Pillow.
- Commit after every task, on the current branch (`wt/t_cf84eaad`). Never merge,
  never push.
- Every new/changed Python module gets a short module docstring in the project's
  established German documentation style (see any existing `simulation/*.py` file)
  — match the codebase's convention, including inline comments that explain *why*,
  not what.

---

## File structure

| File | Responsibility |
|---|---|
| `simulation/claude.py` (extend) | `Claude.text`/`.json_objekt` gain an optional `bilder: list[bytes] \| None` kwarg (image content blocks) |
| `simulation/ux_rubrik.md` (new) | Copy of the `participatory-bot-ux` skill checklist, source noted |
| `simulation/browser_elemente.py` (new) | `extrahiere(page)`, `bildschirmfoto(page)` — what the persona sees |
| `simulation/browser_zaehler.py` (new) | Mechanical UX counters (pure functions over a `Page`), `installiere_messung(context)` |
| `simulation/browser_persona.py` (new) | Persona texts, action schema, `naechste_aktion(...)` |
| `simulation/browser_umgebung.py` (new) | Real-stack process manager: free ports, group creation, web+bot subprocess start/stop |
| `simulation/browser_aktionen.py` (new) | `fuehre_aus(page, aktion)`, `warte_auf_antwort(page)` |
| `simulation/browser_mitschnitt.py` (new) | `datenstand()`, `unterschied()`, `Mitschnitt` (screenshots + `schritte.jsonl`) |
| `simulation/browser_judge.py` (new) | `bewerte_phase(...)` — Opus + images + rubric → note + findings |
| `simulation/browser_bericht.py` (new) | `baue_markdown(...)`, `kontaktbogen(...)` |
| `simulation/browser_lauf.py` (new) | `fuehre_lauf(...)` orchestrator + thin `main()` CLI |
| `tests/test_simulation_claude.py` (extend) | Image-block tests |
| `tests/test_browser_elemente.py` (new) | Element extraction against a static fixture |
| `tests/test_browser_lauf_zaehler.py` (new) | Counters, with mutants (exact filename from the card) |
| `tests/test_browser_persona.py` (new) | Persona prompt + action parsing, fake client |
| `tests/test_browser_umgebung.py` (new) | Port picking, group creation, bash-script text, real `web` subprocess health (no secrets) |
| `tests/test_browser_aktionen.py` (new) | Action execution + settle-wait against a static fixture |
| `tests/test_browser_mitschnitt.py` (new) | DB diff + JSONL recording, no browser |
| `tests/test_browser_judge.py` (new) | Judge prompt/parsing, fake client |
| `tests/test_browser_bericht.py` (new) | Markdown assembly (pure) + contact sheet (Playwright) |
| `tests/test_browser_lauf.py` (new) | Offline end-to-end: real web+bot (attrappe LLM, in-thread like `test_web_e2e_http.py`) driven by a scripted fake persona through phase 1→2 |
| `simulation/README.md`, `AGENTS.md` (extend) | Pointer to the new tool |

All new test files begin with `pytest.importorskip("playwright.sync_api", ...)` —
they skip (not fail) wherever Playwright is absent, exactly like `tests/e2e/*.py`.

---

### Task 1: Image input for the simulation Claude client

**Files:**
- Modify: `simulation/claude.py`
- Test: `tests/test_simulation_claude.py`

**Interfaces:**
- Produces: `Claude.text(system, nutzer, art="sim", max_tokens=MAX_TOKENS,
  bilder: list[bytes] | None = None) -> str` and `Claude.json_objekt(...,
  bilder=None) -> dict` — both used by `browser_persona.naechste_aktion` and
  `browser_judge.bewerte_phase` (Tasks 4 and 7) via `client.json_objekt(system,
  nutzer, art=..., bilder=[...])`.

- [ ] **Step 1: Write the failing test** — add to `tests/test_simulation_claude.py`:

```python
import base64


def test_bilder_werden_als_inhaltsbloecke_gesendet():
    gesehen = {}

    def handler(anfrage: httpx.Request) -> httpx.Response:
        gesehen["koerper"] = json.loads(anfrage.content)
        return _antwort("gesehen")

    c = claude.Claude(_klient(handler))
    bild = b"\x89PNG\r\n\x1a\nfake"
    assert c.text("S", "Beschreib das Bild.", bilder=[bild]) == "gesehen"

    inhalt = gesehen["koerper"]["messages"][0]["content"]
    assert inhalt[0] == {
        "type": "image",
        "source": {
            "type": "base64", "media_type": "image/png",
            "data": base64.b64encode(bild).decode(),
        },
    }
    assert inhalt[1] == {"type": "text", "text": "Beschreib das Bild."}


def test_ohne_bilder_bleibt_der_inhalt_ein_reiner_string():
    """Regression: die bestehende Form (content = ein String) bleibt
    unveraendert, solange niemand ``bilder`` uebergibt."""
    gesehen = {}

    def handler(anfrage):
        gesehen["koerper"] = json.loads(anfrage.content)
        return _antwort("ok")

    claude.Claude(_klient(handler)).text("S", "N")
    assert gesehen["koerper"]["messages"] == [{"role": "user", "content": "N"}]
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `"$PY" -m pytest tests/test_simulation_claude.py -q`
Expected: the two new tests FAIL (`TypeError: text() got an unexpected keyword
argument 'bilder'`); all existing tests in the file still PASS.

- [ ] **Step 3: Implement**

In `simulation/claude.py`, add `import base64` at the top, then change:

```python
    def text(self, system: str, nutzer: str, art: str = "sim",
             max_tokens: int = MAX_TOKENS, bilder: list[bytes] | None = None) -> str:
        """Ein Aufruf, ein Text. Leere Antworten liefern einen leeren String
        -- der Aufrufer entscheidet, ob ihm das reicht.

        ``bilder`` haengt PNG-Bytes als ``image``-Inhaltsbloecke vor den
        Text (Anthropic-Messages-Format) -- fuer die Browser-UX-Simulation
        (Persona/Richter sehen Screenshots). Ohne ``bilder`` bleibt der
        Inhalt ein reiner String wie bisher (Regressionstest)."""
        koerper = self._sende(system, nutzer, art, max_tokens, bilder)
        return _inhalt_aus(koerper).strip()

    def json_objekt(self, system: str, nutzer: str, art: str = "sim",
                    max_tokens: int = MAX_TOKENS,
                    bilder: list[bytes] | None = None) -> dict:
        """Wie ``text``, aber die Antwort wird als JSON-Objekt gelesen
        (``lies_json``, ein Reparaturversuch)."""
        return lies_json(self.text(system, nutzer, art, max_tokens, bilder))
```

And change `_sende`'s signature and body:

```python
    def _sende(self, system: str, nutzer: str, art: str, max_tokens: int,
               bilder: list[bytes] | None = None) -> dict:
        inhalt: str | list = nutzer
        if bilder:
            inhalt = [
                {"type": "image", "source": {"type": "base64",
                 "media_type": "image/png",
                 "data": base64.b64encode(b).decode()}}
                for b in bilder
            ]
            inhalt.append({"type": "text", "text": nutzer})
        koerper = {
            "model": self.modell,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": inhalt}],
        }
        # ... (der Rest von _sende bleibt unveraendert: Retry-Schleife,
        # Statistik, Fehlerbehandlung)
```

(Keep the rest of `_sende`'s body — the retry loop, `self.statistik.buche(...)`,
exception handling — byte-identical; only the `koerper` construction at the top
changes as shown.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `"$PY" -m pytest tests/test_simulation_claude.py -q`
Expected: all tests PASS (the full existing file plus the two new ones).

- [ ] **Step 5: Commit**

```bash
git add simulation/claude.py tests/test_simulation_claude.py
git commit -m "Bildeingabe im Simulations-Claude-Klienten fuer die Browser-UX-Simulation"
```

---

### Task 2: UX rubric copy + docs pointer stub

**Files:**
- Create: `simulation/ux_rubrik.md`
- Test: none (plain data file; covered by Task 7's test reading it)

**Interfaces:**
- Produces: `simulation/ux_rubrik.md`, read by `browser_judge.lies_rubrik()`
  (Task 7).

- [ ] **Step 1: Write the file**

Write `simulation/ux_rubrik.md` with this exact content (the full checklist from
`/home/birk/.hermes/profiles/birk/skills/creative/participatory-bot-ux/SKILL.md`,
source noted at the top, copied verbatim as the card requires):

```markdown
<!--
Source: /home/birk/.hermes/profiles/birk/skills/creative/participatory-bot-ux/SKILL.md
(Birk's personal Hermes skill, "participatory-bot-ux", v1.0.0). Copied into the
repo on 2026-10-03 for the Padua browser UX simulation (card t_cf84eaad) so the
phase judge (simulation/browser_judge.py) can read it without reaching outside
the repository. If the source skill changes, re-copy it here by hand.
-->

# Participatory bot UX — Birk's design stance

Use for ANY design decision on a bot or web surface that a group uses together
(interview-theater/Padua, CoThinker, future workshop tools): buttons, phase
flow, when the bot speaks, what gets saved, which model, which screen. Core
idea: free over guided, quiet over chatty.

Every rule below is a correction Birk actually made (interview-theater rework,
02.10.2026, plus earlier bot-UX rules). Before proposing a design, run the
draft through the checklist at the end. If a rule seems to conflict with the
task, say so and ask; do not silently pick.

## 1. The group authors, the bot assists

- **Content comes from the participants.** Bot suggestions are the last
  resort, not the opener (Phase 1 terms: „die Begriffe sollen unbedingt von den
  Teilnehmenden kommen“).
- **Numbers and scope are the group's call.** The bot asks, never proposes a
  count (scene count: „muss von der Gruppe festgelegt werden“).
- **Bot proposals are never saved as decisions.** Only what the group said or
  confirmed is saved.
- **Don't decide things before the phase where they matter.** Scene styles
  (rap, dialogue) were removed from the scene-planning phase because they belong
  later. Tell: a field is filled with a guess because "we're asking anyway".

## 2. Free over guided („Fokus, kein Käfig“)

- **Creative work has no fixed order.** One question after another is
  „kontraintuitiv für kreative Arbeit“. Instead: one good introduction (what is
  set here, and why), all topics at once as a field („Fragenkonsortium“, not a
  question list), then free brainstorming with an overview of fixed vs. open.
- **Leave room for the unasked.** Allow unlimited free, self-titled definitions
  next to the fixed fields.
- **Buttons are shortcuts, never obligations.** Buttons make users feel they
  MUST press them, which makes everything „starrer als nötig“. Free text and
  voice must visibly stay possible: input always active, chips labelled as
  shortcuts, chips grey out once someone types.
- **Buttons only for a storable value**, never under an open question; one
  field per message.
- **Navigation is always open.** Back/forward through phases at any time (phase
  bar). Requirements are a one-line yes/no hint, not a lock. Natural
  transitions ("saved", "interviews done") may still advance automatically.
- **Re-entry is consistent.** Jumping back into a phase gives the same entry as
  the first time.

## 3. Save automatically, always undoable

- Decisions the group states are saved **automatically** (no yes/no ceremony),
  shown as one quiet system line (📌 …) with **↶ Rückgängig**.
- **Every save has an undo.** No exceptions.
- Tell the group once where everything is kept (the Arbeitsstand tab).

## 4. Quiet over chatty — the bot's voice is a maximum, not a duty

- **Less is more.** Feedback sections are optional; often one or two are
  enough. No mandatory question per thought: that is „wieder so 'n Zwang“ and
  feels „gekünstelt“. The bot may say nothing (`NICHTS`).
- **But not too thin either.** „Ich höre“ in 2–3 lines was too little.
  Useful is: current topic, what emerged (in the group's words), real links to
  earlier statements, 2–3 offers, at most one question, what is still open.
- **Don't flood the chat.** Running commentary belongs on a separate surface (a
  stage tab like CoThinker's), never in the chat („langer Wurstchat“). In
  listening/brainstorm mode the bot writes NOTHING in the chat, not even a
  pointer line; a new card shows as a quiet marker on the tab („der Bot sollte
  dann gar nicht im Chat antworten, sondern nur im Stage-Fenster“).
- **Echo what was heard.** Every transcribed voice segment appears in the chat
  as the group's own bubble, right after each segment cut: that is the feedback
  that the bot is listening („das Transcript im Chat anzeigen als Feedback ist
  wichtig“). Display only: it does not trigger a bot reply.
- **Name surfaces by function, not by metaphor.** „Stage“ was wrong for the
  bot's commentary tab; Birk suggested discussion helper / CoThinker /
  feedback / dashboard and chose CoThinker.
- **Chat per phase (planned).** The chat should start empty in each phase and
  switch along with the phase bar („der Chat soll pro Phase angezeigt werden
  und mit jeder Phase neu bei 0 anfangen“).
- **No wake word** for a bot that is already listening in a session.
- **Background listening is a mode of its own: record, no feedback.** When the
  recording only serves as context for later phases (Phase 1 term discussion),
  the phone lies in the middle and runs the whole time: no arc buttons, no
  cards, no comments, only pause/stop/resume; one condensation at the very
  end, extracting what later phases need („es gibt überhaupt gar kein
  Feedback. Das ist einfach nur ein Mitschneiden, damit die KI das
  Hintergrundwissen aus der Diskussion hat“, 03.10.2026). Tell: a
  CoThinker-style card or a bot line appears during a pure context recording.
- **Own ideas first, AI second, then compare openly.** In question
  development the group writes its own questions before the bot proposes any;
  both sets are offered side by side for choosing, and the share of AI vs.
  own questions kept is shown to the plenary (A/B comparison, 03.10.2026).

## 5. Economy of model calls (cost and distraction are the same problem)

- **The group marks the arc, not the machine.** In brainstorm mode there is
  no automatic pause detection as a trigger: the listen button is a toggle,
  one press = one thought arc (speak, hand over to the next person), the last
  person switches it off, and THAT stop triggers exactly one CoThinker card
  („somit ist alles bei manueller Kontrolle“, 03.10.2026). No cards while
  listening; a hard time cap may still cut segments technically for upload/STT,
  never as a trigger. Tell: a card appears mid-sentence or nobody knows why
  one appeared now.
- **Don't react to every pause.** Too many cuts lead to too many calls, and
  that „lenkt von der Diskussion ab“. Gate model calls in CODE, one call at a
  time; prefer an explicit group action (see above) over size/interval/pause
  heuristics.
- Measured anchors (CoThinker reference annotations, 3 sessions): a thought is
  ~50 s / ~600 chars (wide spread), a topic arc ~2.5 min / ~1 900 chars,
  speech ~16 chars/s. A ~1 200-char trigger gives about one card per topic arc.
- **Give the model enough context to be useful**: the full current phase plus
  a summary of earlier phases, not a tight window.

## 6. Reuse measured values, don't invent them

- When a sibling system already tuned a value, take that value (VAD pause
  0.8 s → CoThinker's 2.5 s / 90 s cap / 0.5 s min speech). Mark it as set vs.
  measured. Keep thresholds env-configurable so they can be retuned on the day.

## 7. Surfaces and devices

- **One page, several tabs**, not extra pages/URLs („ein Tab auf dieser
  Seite“).
- **Several phones per group.** Each phase may have a suggested phone layout
  (who holds which tab), shown as a small picture at the phase start.
- Web is primary; secondary channels (Telegram) follow where it is cheap and may
  lag.
- **On the phone the web page must feel like an app.** It fits the screen
  exactly, never scrolls sideways, and does not jump when the keyboard opens
  („die website soll sich immer optimal an die handy bildschirmgröße anpassen
  und sich dann wie eine app anfühlen“, 03.10.2026). Build it as an app shell:
  `100dvh` container, header | scrolling content | input, no `position:fixed`
  footer on a scrolling document, viewport `interactive-widget=resizes-content`
  (+ `visualViewport` fallback for iOS), `overflow-x` clipped, inputs ≥16px.
  Tell: page slides up/down on keyboard open, or wobbles left/right.
  Acceptance: mobile emulation, `scrollWidth <= innerWidth` on every tab, input
  stays visible with focus.

## 8. Model choice follows data sensitivity

Sensitive data (interviews, their condensation) → sovereign model (Kimi /
Infomaniak). Performance-heavy, non-sensitive work (brainstorm sparring,
writing) → frontier model (Opus via subscription), **after explicit consent,
asked BEFORE that phase starts**. Detail: `interview-theater-live-ops` §2a'.

## How Birk decides (process)

- Proposal with a recommendation, max 3 options, one question per turn.
- He decides layout on a clickable draft, not on a description.
- He collects feedback over several turns and says himself when it is done.
- New correction from him on UX → add it here as a rule with his quote, not
  only in the code.

## Checklist before proposing a design

1. Does any content or number come from the bot that the group should author?
2. Is there a fixed order or a mandatory step the group can't skip or leave?
3. Does every save have an undo, and is it automatic where the group already
   decided?
4. Can the user ignore every button and just talk or type?
5. How many model calls per minute does this cause, and what gates them?
6. Does the bot speak only when it adds something, and outside the chat if it
   is commentary?
7. Is a value invented where a measured one exists?
8. New page where a tab would do? On a phone: does it fit, no sideways
   scroll, no jump when the keyboard opens?
9. Does sensitive data reach a non-sovereign model, or does any model switch
   happen without consent beforehand?
```

- [ ] **Step 2: Commit**

```bash
git add simulation/ux_rubrik.md
git commit -m "UX-Rubrik aus participatory-bot-ux in den Browserlauf kopiert"
```

---

### Task 3: Element extraction (what the persona sees)

**Files:**
- Create: `simulation/browser_elemente.py`
- Test: `tests/test_browser_elemente.py`

**Interfaces:**
- Consumes: a Playwright `Page` (sync API).
- Produces: `extrahiere(page) -> list[dict]` — each dict has at least `id`
  (int, position in the returned list), `art` (str, one of the keys below),
  `text` (str). Optional keys present only when set: `tab`, `phase`, `message`,
  `daten`, `zielTab`, `zielFeld`, `sicher`, `bereit`, `fehlt`, `placeholder`,
  `value`, `haelt`. Also `bildschirmfoto(page) -> bytes` (PNG). Used by
  `browser_persona.naechste_aktion` (Task 4) and `browser_lauf.fuehre_lauf`
  (Task 9).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_browser_elemente.py
import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from simulation import browser_elemente  # noqa: E402

_FIXTURE = """
<nav class="tabs" role="tablist">
  <button type="button" data-tab="chat" aria-selected="true">Chat</button>
  <button type="button" data-tab="stand" aria-selected="false">Status</button>
</nav>
<details class="roadmap" id="roadmap" data-aktive-phase="1">
  <summary>Phase 1/7</summary>
  <ol class="phasen"><li class="phase aktiv">
    <div class="phase-kopfzeile">
      <button type="button" class="phase-knopf" data-phase="2"
              data-bereit="0" data-fehlt="terms">2 - Questions</button>
    </div>
  </li></ol>
</details>
<div class="verlauf" id="verlauf">
  <div class="blase bot" data-id="1">Hello, what terms did you collect?</div>
</div>
<div class="leiste" data-message="1">
  <button type="button" data-message="1" data-daten="k:7">Something else</button>
</div>
<input id="eingabe" placeholder="Type or speak...">
<button id="senden" type="button">Send</button>
<button id="interview" hidden>Start interview</button>
<div style="display:none"><button data-tab="hidden-tab">unsichtbar</button></div>
"""


@pytest.fixture(scope="module")
def seite():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(_FIXTURE)
        yield page
        browser.close()


def test_sichtbare_elemente_werden_gefunden(seite):
    elemente = browser_elemente.extrahiere(seite)
    arten = {(e["art"], e["text"]) for e in elemente}
    assert ("tab", "Chat") in arten
    assert ("tab", "Status") in arten
    assert ("phase", "2 - Questions") in arten
    assert ("chip", "Something else") in arten
    assert ("senden", "Send") in arten
    assert ("eingabe", "") in arten


def test_versteckte_elemente_fehlen(seite):
    elemente = browser_elemente.extrahiere(seite)
    texte = {e["text"] for e in elemente}
    assert "unsichtbar" not in texte
    assert not any(e["art"] == "interview" for e in elemente)  # hidden


def test_data_attribute_kommen_mit(seite):
    elemente = browser_elemente.extrahiere(seite)
    phase = next(e for e in elemente if e["art"] == "phase")
    assert phase["phase"] == "2"
    assert phase["bereit"] == "0"
    assert phase["fehlt"] == "terms"
    chip = next(e for e in elemente if e["art"] == "chip")
    assert chip["message"] == "1"
    assert chip["daten"] == "k:7"
    eingabe = next(e for e in elemente if e["art"] == "eingabe")
    assert eingabe["placeholder"] == "Type or speak..."


def test_bildschirmfoto_liefert_png_bytes(seite):
    bild = browser_elemente.bildschirmfoto(seite)
    assert bild[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$PY" -m pytest tests/test_browser_elemente.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'simulation.browser_elemente'`.

- [ ] **Step 3: Implement**

```python
# simulation/browser_elemente.py
"""Was die Persona auf einem Bildschirm sieht (Padua-Browser-UX-Simulation,
2026-10-03): ein Screenshot plus eine strukturierte Liste der sichtbaren
Bedienelemente -- ueber Rolle, Text und ``data-*`` identifiziert, nicht
ueber Gestaltungsklassen. Ein spaeteres Redesign darf die CSS-Klassen
tauschen, ohne dass die Persona blind wird (AGENTS.md-Auftrag der Karte:
"Elemente ueber Rolle/Text/data-* finden").
"""

from __future__ import annotations

#: Je Elementart ein Selektor -- eine Allowlist bekannter Stellen, wie
#: ``browser_zaehler.VERDRAHTETE_SELEKTOREN``. Ein neues UI-Stueck wird hier
#: eingetragen, nicht erraten.
_ARTEN = (
    ("chip", ".leiste button"),
    ("tab", ".tabs button"),
    ("phase", ".phase-knopf"),
    ("phase_abbrechen", ".phase-abbrechen"),
    ("aufgabe", ".roadmap li.aufgabe"),
    ("senden", "#senden"),
    ("eingabe", "#eingabe"),
    ("interview", "#interview"),
    ("interview_pause", "#interview-pause"),
    ("interview_beenden", "#interview-beenden"),
    ("brainstorm", "#brainstorm"),
    ("brainstorm_pause", "#brainstorm-pause"),
    ("brainstorm_beenden", "#brainstorm-beenden"),
    ("ptt", "#ptt"),
    ("nachreichen", "#nachreichen"),
    ("verwerfen", "#verwerfen"),
    ("link", "a[href]"),
)

_DATEN_JS = (
    "e => ({tab: e.dataset.tab, phase: e.dataset.phase, "
    "message: e.dataset.message, daten: e.dataset.daten, "
    "zielTab: e.dataset.zielTab, zielFeld: e.dataset.zielFeld, "
    "sicher: e.dataset.sicher, bereit: e.dataset.bereit, "
    "fehlt: e.dataset.fehlt, placeholder: e.placeholder || null, "
    "value: (e.value !== undefined ? e.value : null), "
    "haelt: e.dataset.haelt})"
)


def extrahiere(page) -> list[dict]:
    """Sichtbare Bedienelemente als Liste von Dicts.

    ``id`` ist die laufende Nummer innerhalb DIESES Aufrufs -- stabil genug,
    dass eine Persona-Antwort sie in derselben Antwort referenzieren kann,
    aber nicht ueber einen Schritt hinaus (bei jedem Schritt wird neu
    extrahiert, die DOM kann sich veraendert haben)."""
    elemente: list[dict] = []
    gesehen: set[int] = set()
    for art, selektor in _ARTEN:
        for handle in page.query_selector_all(selektor):
            if not handle.is_visible():
                continue
            schluessel = id(handle)
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            eintrag = {
                "id": len(elemente),
                "art": art,
                "text": (handle.text_content() or "").strip(),
            }
            daten = handle.evaluate(_DATEN_JS)
            eintrag.update({k: v for k, v in daten.items() if v not in (None, "")})
            elemente.append(eintrag)
    return elemente


def bildschirmfoto(page) -> bytes:
    return page.screenshot()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$PY" -m pytest tests/test_browser_elemente.py -q`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_elemente.py tests/test_browser_elemente.py
git commit -m "Elementextraktion fuer die Browser-UX-Simulation (Rolle/Text/data-*)"
```

---

### Task 4: Mechanical UX counters, with mutants

**Files:**
- Create: `simulation/browser_zaehler.py`
- Test: `tests/test_browser_lauf_zaehler.py` (exact filename per the card)

**Interfaces:**
- Consumes: a Playwright `Page`.
- Produces: `seitliches_rutschen(page) -> bool`,
  `tap_ziele_zu_klein(page, selektor=...) -> list[dict]`,
  `eingabefeld_schrift_zu_klein(page, selektor=...) -> list[dict]`,
  `mehrere_fragen_pro_nachricht(page, selektor=".blase.bot") -> list[dict]`,
  `knoepfe_ohne_wirkung(page, selektor="button") -> list[dict]`,
  `alle(page) -> dict` (aggregates the five above, keyed by function name),
  `installiere_messung(context) -> None`, and the pure function
  `bot_text_waehrend_zuhoermodus(modus: str, neue_bot_nachrichten: list[str]) ->
  bool`. `alle()` is used by `browser_lauf.fuehre_lauf` (Task 9) after every
  action.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_browser_lauf_zaehler.py
import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from simulation import browser_zaehler as z  # noqa: E402

#: Ein absichtlich kaputter Stand: alle fuenf Mutanten auf einmal, in einem
#: HTML-Dokument, das sonst wie eine Chip-Leiste/Tabs/Eingabe aussieht.
_KAPUTT = """
<style>
  body { width: 120vw; }               /* Mutant 1: seitliches Rutschen */
  .klein { width: 20px; height: 20px; }  /* Mutant 2: zu kleines Tippziel */
  #eingabe { font-size: 12px; }          /* Mutant 3: Zoom-Falle */
</style>
<div class="blase bot">Where does it happen, and when, and who is there?</div>
<div class="leiste"><button class="klein" type="button">x</button></div>
<input id="eingabe">
<button id="tot" type="button">Tot</button>
<script>
  document.addEventListener('click', function (ev) {
    var k = ev.target.closest('.leiste button');
    if (k) { document.body.appendChild(document.createElement('span')); }
  });
</script>
"""

#: Dieselbe Struktur, aber durchgehend sauber -- muss bei JEDEM Zaehler
#: leer/falsch bleiben.
_SAUBER = """
<style>
  body { width: 100%; max-width: 44rem; }
  .ok { min-width: 44px; min-height: 44px; }
  #eingabe { font-size: 16px; }
</style>
<div class="blase bot">Where does it happen?</div>
<div class="leiste"><button class="ok" type="button">x</button></div>
<input id="eingabe">
<button id="tot" type="button">Tot</button>
<script>
  document.addEventListener('click', function (ev) {
    var k = ev.target.closest('.leiste button, #tot');
    if (k) { document.body.appendChild(document.createElement('span')); }
  });
</script>
"""


@pytest.fixture()
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _seite(browser, html):
    page = browser.new_page()
    z.installiere_messung(page.context)
    page.set_content(html)
    return page


def test_seitliches_rutschen_wird_im_kaputten_stand_gemeldet(browser):
    assert z.seitliches_rutschen(_seite(browser, _KAPUTT)) is True


def test_seitliches_rutschen_bleibt_im_sauberen_stand_aus(browser):
    assert z.seitliches_rutschen(_seite(browser, _SAUBER)) is False


def test_zu_kleines_tippziel_wird_gemeldet(browser):
    treffer = z.tap_ziele_zu_klein(_seite(browser, _KAPUTT), selektor=".leiste button")
    assert len(treffer) == 1


def test_tippziel_im_sauberen_stand_ist_gross_genug(browser):
    assert z.tap_ziele_zu_klein(_seite(browser, _SAUBER), selektor=".leiste button") == []


def test_zu_kleine_eingabeschrift_wird_gemeldet(browser):
    treffer = z.eingabefeld_schrift_zu_klein(_seite(browser, _KAPUTT))
    assert len(treffer) == 1


def test_eingabeschrift_im_sauberen_stand_reicht(browser):
    assert z.eingabefeld_schrift_zu_klein(_seite(browser, _SAUBER)) == []


def test_mehrere_fragen_je_nachricht_wird_gemeldet(browser):
    treffer = z.mehrere_fragen_pro_nachricht(_seite(browser, _KAPUTT))
    assert len(treffer) == 1


def test_eine_frage_je_nachricht_ist_in_ordnung(browser):
    assert z.mehrere_fragen_pro_nachricht(_seite(browser, _SAUBER)) == []


def test_knopf_ohne_handler_wird_gemeldet(browser):
    treffer = z.knoepfe_ohne_wirkung(_seite(browser, _KAPUTT))
    assert any(t["text"] == "Tot" for t in treffer)


def test_verdrahteter_knopf_wird_nicht_gemeldet(browser):
    treffer = z.knoepfe_ohne_wirkung(_seite(browser, _SAUBER))
    assert treffer == []


def test_bot_text_waehrend_zuhoermodus_ist_ein_befund():
    assert z.bot_text_waehrend_zuhoermodus("brainstorm", ["Here's a thought..."]) is True
    assert z.bot_text_waehrend_zuhoermodus("brainstorm", []) is False
    assert z.bot_text_waehrend_zuhoermodus("chat", ["anything"]) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"$PY" -m pytest tests/test_browser_lauf_zaehler.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'simulation.browser_zaehler'`.

- [ ] **Step 3: Implement**

```python
# simulation/browser_zaehler.py
"""Mechanische UX-Zaehler fuer den Browserlauf (Padua-UX-Simulation,
2026-10-03): reine Funktionen ueber eine Playwright-``Page`` (oder, wo es
reicht, ueber reinen Text) -- kein Modellaufruf, kein Netz. Sie ergaenzen
den Opus-Richter (``browser_judge.py``): was sich zaehlen laesst, zaehlt
der Code; was Urteil braucht, liest der Richter.
"""

from __future__ import annotations

#: Telefon-Tastatur: unter diesem Wert gilt ein Eingabefeld als Zoom-Falle
#: (iOS zoomt beim Fokussieren eines Feldes mit kleinerer Schrift) --
#: dieselbe Zahl wie in ``participatory-bot-ux`` Abschnitt 7 ("inputs >=16px").
MIN_SCHRIFT_PX = 16.0

#: WCAG-Tastenmass: unter diesem Wert in Pixel gilt ein Tippziel als zu klein.
MIN_TAPZIEL_PX = 44.0

#: Bekannte, mit einem Klick-Handler verdrahtete Stellen -- ueber ID/Rolle/
#: data-* identifiziert, NICHT ueber eine Gestaltungsklasse. Diese Liste
#: darf wachsen, wenn ein neues UI-Stueck dazukommt.
VERDRAHTETE_SELEKTOREN = (
    "#senden", "#interview", "#interview-pause", "#interview-beenden",
    "#brainstorm", "#brainstorm-pause", "#brainstorm-beenden", "#ptt",
    "#nachreichen", "#verwerfen", ".leiste button", ".tabs button",
    ".phase-knopf", ".phase-abbrechen", ".roadmap li.aufgabe", "a[href]",
)


def seitliches_rutschen(page) -> bool:
    """Liegt der Inhalt breiter als der Viewport (horizontales Scrollen)?"""
    return bool(page.evaluate(
        "document.documentElement.scrollWidth > window.innerWidth + 1"
    ))


def tap_ziele_zu_klein(page, selektor: str = (
        ".leiste button, .tabs button, .phase-knopf, #senden, #interview, "
        "#ptt, #brainstorm")) -> list[dict]:
    """Sichtbare Tippziele unter ``MIN_TAPZIEL_PX``."""
    treffer = []
    for el in page.query_selector_all(selektor):
        if not el.is_visible():
            continue
        box = el.bounding_box()
        if box is None:
            continue
        if box["width"] < MIN_TAPZIEL_PX or box["height"] < MIN_TAPZIEL_PX:
            treffer.append({
                "text": (el.text_content() or "").strip(),
                "breite": box["width"], "hoehe": box["height"],
            })
    return treffer


def eingabefeld_schrift_zu_klein(page, selektor: str = "#eingabe, input, textarea") -> list[dict]:
    treffer = []
    for el in page.query_selector_all(selektor):
        if not el.is_visible():
            continue
        px = el.evaluate("e => parseFloat(getComputedStyle(e).fontSize)")
        if px and px < MIN_SCHRIFT_PX:
            treffer.append({"schrift_px": px})
    return treffer


def mehrere_fragen_pro_nachricht(page, selektor: str = ".blase.bot") -> list[dict]:
    treffer = []
    for el in page.query_selector_all(selektor):
        text = el.text_content() or ""
        anzahl = text.count("?")
        if anzahl > 1:
            treffer.append({"text": text.strip()[:200], "fragen": anzahl})
    return treffer


def knoepfe_ohne_wirkung(page, selektor: str = "button") -> list[dict]:
    """Ein sichtbarer, aktiver Knopf, der weder einen ``fetch``-Aufruf noch
    eine DOM-Aenderung ausloest -- ``installiere_messung`` muss vorher auf
    dem ``context`` gelaufen sein, sonst bleibt ``window.__fetchZaehler``
    undefiniert und der fetch-Teil des Vergleichs greift nicht."""
    treffer = []
    for el in page.query_selector_all(selektor):
        if not el.is_visible() or el.is_disabled():
            continue
        vorher_fetch = page.evaluate("window.__fetchZaehler || 0")
        vorher_html = page.evaluate("document.body.innerHTML.length")
        try:
            el.click(timeout=1000)
        except Exception:
            continue
        page.wait_for_timeout(300)
        nachher_fetch = page.evaluate("window.__fetchZaehler || 0")
        nachher_html = page.evaluate("document.body.innerHTML.length")
        if nachher_fetch == vorher_fetch and nachher_html == vorher_html:
            treffer.append({"text": (el.text_content() or "").strip()})
    return treffer


def installiere_messung(context) -> None:
    """Zaehlt ``fetch``-Aufrufe in ``window.__fetchZaehler`` -- fuer
    ``knoepfe_ohne_wirkung``. Muss auf dem ``context`` laufen, BEVOR eine
    Seite geladen wird (``context.add_init_script``), damit es auf jedem
    neuen Dokument steht."""
    context.add_init_script(
        "window.__fetchZaehler = 0; var __echtesFetch = window.fetch;"
        "window.fetch = function () { window.__fetchZaehler++; "
        "return __echtesFetch.apply(this, arguments); };"
    )


def alle(page) -> dict:
    """Alle Zaehler in einem Durchlauf -- fuer den Mitschnitt je Schritt."""
    return {
        "seitliches_rutschen": seitliches_rutschen(page),
        "tap_ziele_zu_klein": tap_ziele_zu_klein(page),
        "eingabefeld_schrift_zu_klein": eingabefeld_schrift_zu_klein(page),
        "mehrere_fragen_pro_nachricht": mehrere_fragen_pro_nachricht(page),
    }


# -- reine Funktionen ohne Browser -------------------------------------------


def bot_text_waehrend_zuhoermodus(modus: str, neue_bot_nachrichten: list[str]) -> bool:
    """Schreibt der Bot im Brainstorm-/Zuhoermodus trotzdem in den Chat?
    (``ux_rubrik.md`` Abschnitt 4: "the bot writes NOTHING in the chat")."""
    return modus == "brainstorm" and any(t.strip() for t in neue_bot_nachrichten)
```

Note for the implementer: `knoepfe_ohne_wirkung` is deliberately **not** called
from `alle()` — it mutates the page by clicking every button, which would corrupt
a live run's state. `browser_lauf.fuehre_lauf` (Task 9) must call it only once, on
page load, before the persona starts acting (a "dead button" audit of the current
screen), never after.

- [ ] **Step 4: Run tests to verify they pass**

Run: `"$PY" -m pytest tests/test_browser_lauf_zaehler.py -q`
Expected: all 11 tests PASS. If `knopf_ohne_handler_wird_gemeldet` or
`verdrahteter_knopf_wird_nicht_gemeldet` are flaky, check that
`context.add_init_script` really runs before `page.set_content` executes the
fixture's own `<script>` (it must — init scripts run on every new document,
before any other script) — fix by re-ordering `installiere_messung(page.context)`
before `page.set_content(...)` in `_seite()` if not already so.

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_zaehler.py tests/test_browser_lauf_zaehler.py
git commit -m "Mechanische UX-Zaehler fuer den Browserlauf, mit Mutanten belegt"
```

---

### Task 5: Persona decision-making

**Files:**
- Create: `simulation/browser_persona.py`
- Test: `tests/test_browser_persona.py`

**Interfaces:**
- Consumes: any object with `.json_objekt(system, nutzer, art=..., bilder=...) ->
  dict` (the Task 1 interface — real `claude.Claude` or a fake).
- Produces: `PERSONEN: dict[str, str]` (keys `"student"`, `"clicker"`),
  `naechste_aktion(client, persona_name, bild_png, elemente, phasenziel,
  verlaufszeilen) -> dict` returning an action dict with at least `"type"` in
  `{"click", "type_send", "tab", "phase", "ptt", "wait", "done_phase"}` and
  `"begruendung"`. Used by `browser_lauf.fuehre_lauf` (Task 9); executed by
  `browser_aktionen.fuehre_aus` (Task 6).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_browser_persona.py
import json

from simulation import browser_persona as p


class _FakeClient:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def json_objekt(self, system, nutzer, art="sim", bilder=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art,
                             "bilder": bilder})
        if isinstance(self.antwort, Exception):
            raise self.antwort
        return self.antwort


def test_aktion_geht_mit_bild_und_elementliste_hinaus():
    client = _FakeClient({"type": "click", "element_id": 2, "begruendung": "ok"})
    elemente = [{"id": 2, "art": "chip", "text": "Something else"}]
    aktion = p.naechste_aktion(client, "student", b"PNGDATEN", elemente,
                               "Collect terms.", ["Bot: hi"])
    assert aktion == {"type": "click", "element_id": 2, "begruendung": "ok"}
    aufruf = client.aufrufe[0]
    assert aufruf["bilder"] == [b"PNGDATEN"]
    assert "Something else" in aufruf["nutzer"]
    assert "Collect terms." in aufruf["nutzer"]
    assert p.PERSONEN["student"] in aufruf["system"]


def test_kaputtes_json_wird_zu_wait_statt_zu_werfen():
    aktion = p.naechste_aktion(_FakeClient(ValueError("boom")), "student",
                               b"x", [], "ziel", [])
    assert aktion["type"] == "wait"


def test_antwort_ohne_type_wird_zu_wait():
    aktion = p.naechste_aktion(_FakeClient({"begruendung": "nur das"}), "student",
                               b"x", [], "ziel", [])
    assert aktion["type"] == "wait"


def test_beide_personas_existieren_und_unterscheiden_sich():
    assert set(p.PERSONEN) == {"student", "clicker"}
    assert p.PERSONEN["student"] != p.PERSONEN["clicker"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$PY" -m pytest tests/test_browser_persona.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'simulation.browser_persona'`.

- [ ] **Step 3: Implement**

```python
# simulation/browser_persona.py
"""Die Persona, die den Browser bedient (Padua-UX-Simulation, 2026-10-03):
ein Opus-Aufruf je Schritt, Bild + Elementliste herein, genau eine Aktion
als JSON heraus. Zwei Personas, wie im Kartentext gefordert: eine
zurueckhaltende Schauspielstudentin, die lieber tippt als klickt, und eine
klickfreudige Gegenstimme.
"""

from __future__ import annotations

PERSONEN: dict[str, str] = {
    "student": (
        "You are a 23-year-old acting student in an English-language "
        "theatre workshop (your own English is B2). You are impatient "
        "with long forms and prefer typing full sentences over tapping "
        "buttons, but you will tap a button when it is clearly the "
        "fastest way forward or when free text would not be understood "
        "(choosing a phase, confirming a scene's form, agreeing to a "
        "consent question). You read the screen before acting, and you "
        "get mildly annoyed by a repeated or confusing prompt -- say so "
        "in your reasoning when it happens."
    ),
    "clicker": (
        "You are a 19-year-old acting student who taps everything in "
        "sight before reading it closely. You prefer a button over "
        "typing whenever one exists, even for an open question, and you "
        "are quick to tap 'something else' or the first suggestion "
        "rather than composing your own text."
    ),
}

_SYSTEM_RAHMEN = """\
{persona}

You are testing a web app for a theatre workshop by actually using it, one \
step at a time. You will be shown a screenshot and a list of the visible \
controls. Reply with EXACTLY ONE JSON object describing your next action, \
nothing else, no markdown fence. Schema:

{{"type": "click" | "type_send" | "tab" | "phase" | "ptt" | "wait" | "done_phase",
 "element_id": <id from the control list below, required for "click">,
 "text": <string, required for "type_send">,
 "name": <tab name, required for "tab">,
 "nummer": <phase number, required for "phase">,
 "duration_ms": <integer, optional for "wait">,
 "begruendung": <one sentence, your in-character reason, always required>}}

Use "done_phase" once you believe this phase's goal is complete and it is \
time to move to the next phase. Use "wait" only if the bot appears to still \
be working (a typing indicator or a growing message) and nothing else useful \
is visible yet.
"""


def _elemente_text(elemente: list[dict]) -> str:
    zeilen = []
    for e in elemente:
        teile = [f"id={e['id']}", e["art"], repr(e.get("text", ""))]
        for schluessel in ("tab", "phase", "placeholder", "value"):
            if e.get(schluessel):
                teile.append(f"{schluessel}={e[schluessel]}")
        zeilen.append(" ".join(teile))
    return "\n".join(zeilen) if zeilen else "(no visible controls)"


def baue_nutzertext(elemente: list[dict], phasenziel: str,
                    verlaufszeilen: list[str]) -> str:
    verlauf = "\n".join(verlaufszeilen[-8:]) or "(nothing said yet)"
    return (
        f"Current phase goal: {phasenziel}\n\n"
        f"Recent chat:\n{verlauf}\n\n"
        f"Visible controls:\n{_elemente_text(elemente)}"
    )


def naechste_aktion(client, persona_name: str, bild_png: bytes,
                    elemente: list[dict], phasenziel: str,
                    verlaufszeilen: list[str]) -> dict:
    """Ein Opus-Aufruf (``client.json_objekt``, mit Bild) -> eine Aktion.

    Liefert bei kaputtem JSON oder einem Modellfehler eine ``wait``-Aktion
    statt zu werfen -- ein Schritt, der nichts tut, kostet nur Zeit; ein
    abgebrochener Lauf kostet den ganzen Rest der Phase."""
    system = _SYSTEM_RAHMEN.format(persona=PERSONEN[persona_name])
    nutzer = baue_nutzertext(elemente, phasenziel, verlaufszeilen)
    try:
        aktion = client.json_objekt(system, nutzer, art="browser_persona",
                                    bilder=[bild_png])
    except Exception:
        return {"type": "wait", "duration_ms": 2000,
                "begruendung": "(model error, waiting)"}
    if not isinstance(aktion, dict) or "type" not in aktion:
        return {"type": "wait", "duration_ms": 2000,
                "begruendung": "(no valid action JSON)"}
    return aktion
```

- [ ] **Step 4: Run test to verify it passes**

Run: `"$PY" -m pytest tests/test_browser_persona.py -q`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_persona.py tests/test_browser_persona.py
git commit -m "Persona-Entscheidung je Schritt fuer den Browserlauf"
```

---

### Task 6: Real-stack process manager

**Files:**
- Create: `simulation/browser_umgebung.py`
- Test: `tests/test_browser_umgebung.py`

**Interfaces:**
- Produces: `freier_port() -> int`; `baue_gruppe(db_pfad: str, bot_name: str) ->
  tuple[int, str]` (chat_id, token); `bau_bot_skript(env_datei, db_pfad,
  audio_verz, chat_id, py=PY) -> str` (the bash script text, pure, no
  execution); `starte_web(db_pfad, audio_verz, log_pfad) -> tuple[Popen, file,
  str]` (process, log handle, base URL); `starte_bot(env_datei, db_pfad,
  audio_verz, chat_id, log_pfad) -> tuple[Popen, file]`; `@dataclass Stack`
  with a `.beende()` method; `starte_stack(env_datei, lauf_verzeichnis: Path)
  -> Stack`. Used by `browser_lauf.main()` (Task 9) for the real run only —
  Task 9's own offline test builds its stack directly with threads, bypassing
  this module.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_browser_umgebung.py
import json
import os
import socket
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from simulation import browser_umgebung as u
from interview_theater import db, repo


def test_freier_port_ist_wirklich_frei():
    port = u.freier_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))  # waere belegt, schluege das fehl


def test_baue_gruppe_legt_eine_web_gruppe_an(tmp_path):
    db_pfad = str(tmp_path / "sim.db")
    chat_id, token = u.baue_gruppe(db_pfad, "padua-browser-sim")
    conn = db.verbinde(db_pfad)
    try:
        zeile = conn.execute(
            "SELECT kanal, web_token FROM gruppe WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        assert zeile["kanal"] == "web"
        assert zeile["web_token"] == token
    finally:
        conn.close()


def test_bot_skript_sourcet_die_env_datei_und_ueberschreibt_danach():
    skript = u.bau_bot_skript("/geheim/padua-test.env", "/tmp/sim.db",
                              "/tmp/audio", 7_000_000_000_123, py="/usr/bin/python3")
    zeilen = skript.splitlines()
    source_zeile = next(i for i, z in enumerate(zeilen) if "source" in z)
    db_zeile = next(i for i, z in enumerate(zeilen) if "IT_DB=" in z)
    assert source_zeile < db_zeile  # Overrides stehen NACH dem source
    assert '/geheim/padua-test.env' in skript
    assert "IT_KANAL=web" in skript
    assert "IT_WEB_CHAT_ID=\"7000000000123\"" in skript
    assert "IT_WORKSHOP=padua-2026" in skript
    assert "IT_BOT_NAME=padua-browser-sim" in skript
    assert skript.strip().endswith("-m interview_theater.bot")


def test_starte_web_antwortet_gesund(tmp_path):
    """Kein Geheimnis noetig: der Webserver braucht keine Modell-Zugangsdaten."""
    db_pfad = str(tmp_path / "sim.db")
    u.baue_gruppe(db_pfad, "padua-browser-sim")
    prozess, log, basis = u.starte_web(
        db_pfad, str(tmp_path / "audio"), str(tmp_path / "web.log"))
    try:
        with urllib.request.urlopen(f"{basis}/gesund", timeout=5) as a:
            assert a.read().decode().strip() == "ok"
    finally:
        prozess.terminate()
        prozess.wait(timeout=5)
        log.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"$PY" -m pytest tests/test_browser_umgebung.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'simulation.browser_umgebung'`.

- [ ] **Step 3: Implement**

```python
# simulation/browser_umgebung.py
"""Der echte Stack fuer den Browserlauf: Web-Server + EIN Web-Bot-Prozess
gegen eine Wegwerf-Datenbank (Padua-UX-Simulation, 2026-10-03).

Betrieb (``betrieb/padua.db``, Units, Ports 8010/8030) wird nie beruehrt --
dieses Modul startet zwei eigene Prozesse auf freien Ports gegen eine
temporaere Datenbank und legt die eine Web-Gruppe darin selbst an (wie
``scripts/web_gruppe.py``, aber ohne eine Env-Datei zu lesen -- das macht
hier allein das generierte Bash-Skript, als Kindprozess).

Die echten Modell-Zugangsdaten (IT_LLM_*, IT_STT_*, IT_SZENE_*) werden NIE
von Python gelesen: ``bau_bot_skript`` erzeugt nur TEXT (eine ``source``-
Zeile mit dem Dateipfad, keine Werte), und erst die Bash-Shell des
Kindprozesses fuellt daraus ihre eigene Umgebung. Dieser Python-Prozess
sieht die Werte nie, kann sie also auch nie loggen oder committen.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from interview_theater import db, repo

WURZEL = Path(__file__).resolve().parent.parent
PY = sys.executable


def freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def baue_gruppe(db_pfad: str, bot_name: str) -> tuple[int, str]:
    """Legt die eine Web-Gruppe an -- derselbe Weg wie
    ``scripts/web_gruppe.lege_an``, hier direkt ueber ``repo``."""
    conn = db.verbinde(db_pfad)
    try:
        db.initialisiere(conn)
        chat_id = repo.naechste_web_chat_id(conn)
        repo.sichere_gruppe(conn, chat_id, bot_name, "Padua UX-Simulation")
        repo.setze_gruppe_kanal(conn, chat_id, "web")
        repo.setze_update_id(conn, bot_name, 0)
        token = repo.stelle_web_token_sicher(conn, chat_id)
        conn.commit()
    finally:
        conn.close()
    return chat_id, token


_BOT_SKRIPT = """\
set -euo pipefail
set -a
source "{env_datei}"
set +a
export IT_DB="{db_pfad}"
export IT_AUDIO="{audio_verz}"
export IT_KANAL=web
export IT_WEB_CHAT_ID="{chat_id}"
export IT_WORKSHOP=padua-2026
export IT_BOT_NAME=padua-browser-sim
export IT_WEB_URL=""
exec "{py}" -u -m interview_theater.bot
"""


def bau_bot_skript(env_datei: str, db_pfad: str, audio_verz: str,
                   chat_id: int, py: str = PY) -> str:
    """Nur Text -- keine Ausfuehrung, kein Secret wird hier gelesen."""
    return _BOT_SKRIPT.format(
        env_datei=env_datei, db_pfad=db_pfad, audio_verz=audio_verz,
        chat_id=chat_id, py=py,
    )


def _warte_gesund(prozess, basis: str, log_pfad: str, sekunden: float = 20.0) -> None:
    ende = time.time() + sekunden
    while time.time() < ende:
        if prozess.poll() is not None:
            raise RuntimeError(f"Webserver abgestuerzt, siehe {log_pfad}")
        try:
            with urllib.request.urlopen(f"{basis}/gesund", timeout=1) as a:
                if a.read().decode().strip() == "ok":
                    return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Webserver nicht erreichbar, siehe {log_pfad}")


def starte_web(db_pfad: str, audio_verz: str, log_pfad: str):
    bind = f"127.0.0.1:{freier_port()}"
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": db_pfad, "IT_WEB_BIND": bind, "IT_WEB_PREFIX": "",
        "IT_AUDIO": audio_verz, "IT_WORKSHOP": "padua-2026",
        "IT_WEB_SEGMENT_MS": "45000", "PYTHONPATH": str(WURZEL),
    })
    log = open(log_pfad, "w")
    prozess = subprocess.Popen(
        [PY, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung, stdout=log, stderr=subprocess.STDOUT,
    )
    basis = f"http://{bind}"
    try:
        _warte_gesund(prozess, basis, log_pfad)
    except Exception:
        prozess.terminate()
        log.close()
        raise
    return prozess, log, basis


def starte_bot(env_datei: str, db_pfad: str, audio_verz: str, chat_id: int,
              log_pfad: str):
    skript = bau_bot_skript(env_datei, db_pfad, audio_verz, chat_id)
    log = open(log_pfad, "w")
    prozess = subprocess.Popen(
        ["bash", "-c", skript], cwd=str(WURZEL),
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "HOME": os.environ.get("HOME", "")},
        stdout=log, stderr=subprocess.STDOUT,
    )
    time.sleep(2.0)
    if prozess.poll() is not None:
        log.close()
        raise RuntimeError(f"Bot-Prozess sofort beendet, siehe {log_pfad}")
    return prozess, log


@dataclass
class Stack:
    db_pfad: str
    audio_verz: str
    chat_id: int
    token: str
    web_basis: str
    web_prozess: subprocess.Popen
    bot_prozess: subprocess.Popen
    web_log: object
    bot_log: object

    def beende(self) -> None:
        for prozess in (self.bot_prozess, self.web_prozess):
            prozess.terminate()
        for prozess in (self.bot_prozess, self.web_prozess):
            try:
                prozess.wait(timeout=10)
            except subprocess.TimeoutExpired:
                prozess.kill()
        self.web_log.close()
        self.bot_log.close()


def starte_stack(env_datei: str, lauf_verzeichnis: Path) -> Stack:
    db_pfad = str(lauf_verzeichnis / "sim.db")
    audio_verz = str(lauf_verzeichnis / "audio")
    os.makedirs(audio_verz, exist_ok=True)
    chat_id, token = baue_gruppe(db_pfad, "padua-browser-sim")
    web_prozess, web_log, web_basis = starte_web(
        db_pfad, audio_verz, str(lauf_verzeichnis / "web.log"))
    bot_prozess, bot_log = starte_bot(
        env_datei, db_pfad, audio_verz, chat_id,
        str(lauf_verzeichnis / "bot.log"))
    return Stack(db_pfad, audio_verz, chat_id, token, web_basis,
                web_prozess, bot_prozess, web_log, bot_log)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"$PY" -m pytest tests/test_browser_umgebung.py -q`
Expected: all 4 tests PASS. Note: `test_starte_web_antwortet_gesund` starts a
real `interview_theater.web` subprocess on a free port — no secrets involved,
nothing outside `/tmp`/the worktree's temp dirs is touched.

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_umgebung.py tests/test_browser_umgebung.py
git commit -m "Echter Stack (Web+Bot-Subprozesse) fuer den Browserlauf"
```

---

### Task 7: Action executor

**Files:**
- Create: `simulation/browser_aktionen.py`
- Test: `tests/test_browser_aktionen.py`

**Interfaces:**
- Consumes: a Playwright `Page`, an action dict shaped like Task 5's output.
- Produces: `fuehre_aus(page, aktion: dict) -> dict` (a small log dict);
  `warte_auf_antwort(page, geduld_s=ANTWORT_GEDULD_S, anlauf_s=3.0) -> dict`
  with keys `fertig` (bool), `sekunden` (float), `ohne_hinweis` (bool); and the
  exception `UnbekannteAktion`. Used by `browser_lauf.fuehre_lauf` (Task 9).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_browser_aktionen.py
import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from simulation import browser_aktionen as a  # noqa: E402

_FIXTURE = """
<div id="verlauf"></div>
<div id="tippt"></div>
<input id="eingabe">
<button id="senden" type="button" onclick="
  document.getElementById('verlauf').innerHTML =
    '<div class=\\'blase gruppe\\'>' + document.getElementById('eingabe').value + '</div>';
  document.getElementById('eingabe').value = '';
"></button>
<nav class="tabs"><button data-tab="stand">Status</button></nav>
<div class="phase-kopfzeile">
  <button class="phase-knopf" data-phase="2" data-bereit="0">2 - Questions</button>
</div>
<script>
  var knopf = document.querySelector('.phase-knopf');
  knopf.addEventListener('click', function () {
    if (knopf.getAttribute('data-sicher') === '1') {
      knopf.dataset.gesprungen = '1';
      return;
    }
    knopf.setAttribute('data-sicher', '1');
  });
</script>
"""


@pytest.fixture()
def seite():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.set_content(_FIXTURE)
        yield page
        b.close()


def test_type_send_fuellt_und_sendet(seite):
    a.fuehre_aus(seite, {"type": "type_send", "text": "hello"})
    assert seite.locator(".blase.gruppe").text_content() == "hello"


def test_tab_klickt_den_passenden_tab(seite):
    protokoll = a.fuehre_aus(seite, {"type": "tab", "name": "stand"})
    assert protokoll["art"] == "tab"


def test_phase_klickt_zweimal_wenn_unbereit(seite):
    a.fuehre_aus(seite, {"type": "phase", "nummer": 2})
    assert seite.locator(".phase-knopf").get_attribute("data-gesprungen") == "1"


def test_unbekannte_aktion_wirft(seite):
    with pytest.raises(a.UnbekannteAktion):
        a.fuehre_aus(seite, {"type": "foo"})


def test_warte_auf_antwort_ohne_aktivitaet_kehrt_schnell_zurueck(seite):
    ergebnis = a.warte_auf_antwort(seite, geduld_s=10, anlauf_s=1)
    assert ergebnis["fertig"] is True
    assert ergebnis["sekunden"] < 5


def test_warte_auf_antwort_wartet_auf_das_ende_der_tippanzeige(seite):
    seite.evaluate(
        "document.getElementById('tippt').textContent = 'schreibt...';"
        "setTimeout(function () {"
        "  document.getElementById('tippt').textContent = '';"
        "}, 500);"
    )
    ergebnis = a.warte_auf_antwort(seite, geduld_s=10, anlauf_s=1)
    assert ergebnis["fertig"] is True
    assert ergebnis["ohne_hinweis"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"$PY" -m pytest tests/test_browser_aktionen.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'simulation.browser_aktionen'`.

- [ ] **Step 3: Implement**

```python
# simulation/browser_aktionen.py
"""Fuehrt eine Persona-Aktion auf der Seite aus und wartet, bis die
Bot-Antwort fertig ist (Padua-UX-Simulation, 2026-10-03)."""

from __future__ import annotations

import time

#: Wie lange hoechstens auf das Ende einer Bot-Antwort gewartet wird.
ANTWORT_GEDULD_S = 90.0

#: Ab wann eine Wartezeit ganz ohne sichtbare Aktivitaet (kein Tippen, keine
#: vorlaeufige Blase) als "nichts zu erwarten" gilt und der naechste Schritt
#: sofort weiterlaeuft -- die meisten Aktionen (Tab-Wechsel, Phasenklick)
#: loesen gar keinen Modellaufruf aus.
_ANLAUF_S = 3.0

#: Ab wann eine laufende Wartezeit ohne sichtbaren Hinweis als Befund zaehlt
#: (``ux_rubrik.md``-Checkliste, "Wartezeit > 20 s ohne sichtbaren Hinweis").
WARTEZEIT_OHNE_HINWEIS_S = 20.0


class UnbekannteAktion(Exception):
    pass


def fuehre_aus(page, aktion: dict) -> dict:
    """Fuehrt genau eine Aktion aus. Liefert ein Protokoll-Dict."""
    art = aktion.get("type")
    if art == "wait":
        page.wait_for_timeout(int(aktion.get("duration_ms") or 1000))
        return {"art": "wait"}
    if art == "click":
        el = _element(page, aktion)
        el.click(timeout=5000)
        return {"art": "click", "ziel": aktion.get("element_id")}
    if art == "type_send":
        page.fill("#eingabe", aktion.get("text", ""))
        page.click("#senden")
        return {"art": "type_send", "text": aktion.get("text", "")}
    if art == "tab":
        page.click(f'.tabs button[data-tab="{aktion["name"]}"]')
        return {"art": "tab", "ziel": aktion["name"]}
    if art == "phase":
        selektor = f'.phase-knopf[data-phase="{aktion["nummer"]}"]'
        page.click(selektor)
        page.wait_for_timeout(300)
        # Nach vorn mit fehlender Voraussetzung bewaffnet der erste Klick
        # nur die Rueckfrage (data-sicher=1) -- ein zweiter Klick bestaetigt,
        # genau wie bei einer echten Gruppe (web_vereint._VEREINT_JS,
        # "bewaffne"/"springe").
        if page.locator(selektor).get_attribute("data-sicher") == "1":
            page.click(selektor)
        return {"art": "phase", "ziel": aktion["nummer"]}
    if art == "ptt":
        # Ton ist in dieser Kartenversion ausgespart (siehe Bericht,
        # "Real-Test Birk") -- die Aktion wird protokolliert, aber nicht
        # ausgefuehrt.
        return {"art": "ptt", "ausgefuehrt": False}
    if art == "done_phase":
        return {"art": "done_phase"}
    raise UnbekannteAktion(f"unbekannte Aktion: {art!r}")


def _element(page, aktion: dict):
    text = aktion.get("text")
    if text:
        return page.get_by_text(text, exact=True).first
    return page.locator(aktion.get("selektor") or "button, a, input").first


def laeuft_sichtbar(page) -> bool:
    """Laeuft der Bot gerade sichtbar (Tippanzeige oder vorlaeufige Blase)?"""
    return bool(page.evaluate(
        "() => { var t = document.getElementById('tippt'); "
        "var vl = document.querySelector('.blase.vorlaeufig'); "
        "return !!(t && t.textContent) || !!vl; }"
    ))


def warte_auf_antwort(page, geduld_s: float = ANTWORT_GEDULD_S,
                      anlauf_s: float = _ANLAUF_S) -> dict:
    """Wartet, bis der Bot sichtbar fertig ist.

    Zeigt sich binnen ``anlauf_s`` nichts, war die letzte Aktion vermutlich
    eine, die keinen Modellaufruf ausloest (Tab-/Phasenwechsel) -- sofort
    weiter. Zeigt sich etwas, wird gewartet, bis es wieder verschwindet,
    hoechstens ``geduld_s``."""
    start = time.monotonic()
    sah_aktivitaet = False
    while time.monotonic() - start < geduld_s:
        aktiv = laeuft_sichtbar(page)
        if aktiv:
            sah_aktivitaet = True
        elif sah_aktivitaet:
            dauer = time.monotonic() - start
            return {"fertig": True, "sekunden": dauer,
                    "ohne_hinweis": False}
        elif time.monotonic() - start > anlauf_s:
            dauer = time.monotonic() - start
            return {"fertig": True, "sekunden": dauer, "ohne_hinweis": False}
        page.wait_for_timeout(300)
    dauer = time.monotonic() - start
    return {"fertig": sah_aktivitaet, "sekunden": dauer,
            "ohne_hinweis": dauer > WARTEZEIT_OHNE_HINWEIS_S and not sah_aktivitaet}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"$PY" -m pytest tests/test_browser_aktionen.py -q`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_aktionen.py tests/test_browser_aktionen.py
git commit -m "Aktionsausfuehrung und Antwort-Wartelogik fuer den Browserlauf"
```

---

### Task 8: Step recording (screenshots, DB diff, JSONL)

**Files:**
- Create: `simulation/browser_mitschnitt.py`
- Test: `tests/test_browser_mitschnitt.py`

**Interfaces:**
- Consumes: a DB path (temp sqlite, via `interview_theater.db`/`repo`).
- Produces: `datenstand(db_pfad: str, chat_id: int) -> dict`,
  `unterschied(vorher: dict, nachher: dict) -> dict`, `class Mitschnitt`
  with `.screenshot_pfad(phase, suffix) -> Path` and `.schritt(**kwargs) ->
  None` (appends one JSON line to `schritte.jsonl`). Used by
  `browser_lauf.fuehre_lauf` (Task 9).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_browser_mitschnitt.py
import json

from interview_theater import db, repo
from simulation import browser_mitschnitt as m

CHAT = 7_000_000_000_777


def _db(tmp_path):
    pfad = str(tmp_path / "sim.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "bot", "Testgruppe")
    conn.commit()
    conn.close()
    return pfad


def test_datenstand_liest_den_leeren_arbeitsstand(tmp_path):
    pfad = _db(tmp_path)
    stand = m.datenstand(pfad, CHAT)
    assert stand["journal_anzahl"] == 0
    assert stand["szenen_anzahl"] == 0


def test_unterschied_findet_ein_neu_gesetztes_feld(tmp_path):
    pfad = _db(tmp_path)
    vorher = m.datenstand(pfad, CHAT)
    conn = db.verbinde(pfad)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Ankommen, Arbeit")
    conn.commit()
    conn.close()
    nachher = m.datenstand(pfad, CHAT)
    diff = m.unterschied(vorher, nachher)
    assert diff["arbeitsstand_geaendert"]["begriffe"] == "Ankommen, Arbeit"


def test_mitschnitt_schreibt_eine_jsonl_zeile(tmp_path):
    aufzeichner = m.Mitschnitt(tmp_path / "lauf1", "lauf1", "handy")
    vor = aufzeichner.screenshot_pfad(1, "vor")
    nach = aufzeichner.screenshot_pfad(1, "nach")
    vor.write_bytes(b"x")
    nach.write_bytes(b"y")
    aufzeichner.schritt(
        phase=1, screenshot_vorher=vor, screenshot_nachher=nach,
        elemente=[{"id": 0}], aktion={"type": "wait"}, begruendung="warte",
        antwort={"sekunden": 1.2, "ohne_hinweis": False}, db_diff={},
    )
    zeilen = (tmp_path / "lauf1" / "schritte.jsonl").read_text().splitlines()
    assert len(zeilen) == 1
    zeile = json.loads(zeilen[0])
    assert zeile["phase"] == 1
    assert zeile["begruendung"] == "warte"
    assert zeile["antwort_sekunden"] == 1.2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"$PY" -m pytest tests/test_browser_mitschnitt.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# simulation/browser_mitschnitt.py
"""Der Mitschnitt je Schritt: Screenshots, eine Zeile in ``schritte.jsonl``,
der DB-Unterschied seit dem letzten Schritt (Padua-UX-Simulation,
2026-10-03)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from interview_theater import db, repo


def datenstand(db_pfad: str, chat_id: int) -> dict:
    """Ein Schnappschuss der Felder, die sich beim Fortschreiten aendern.

    Nur Zaehler und kurze Werte (auf 120 Zeichen gekappt) -- kein
    Belegzitat landet hier, damit ein Bericht diese Werte zeigen darf."""
    conn = db.verbinde(f"file:{db_pfad}?mode=ro", uri=True)
    try:
        stand = repo.hole_arbeitsstand(conn, chat_id)
        felder = {}
        if stand is not None:
            for name in stand.keys():
                wert = stand[name]
                if isinstance(wert, str) and len(wert) > 120:
                    wert = wert[:120] + "…"
                felder[name] = wert
        return {
            "arbeitsstand": felder,
            "journal_anzahl": len(repo.journal(conn, chat_id)),
            "figuren_anzahl": len(repo.figuren(conn, chat_id)),
            "szenen_anzahl": len(repo.hole_szenen(conn, chat_id)),
        }
    finally:
        conn.close()


def unterschied(vorher: dict, nachher: dict) -> dict:
    """Was sich zwischen zwei Datenstaenden geaendert hat."""
    geaendert = {}
    for schluessel, wert in nachher.get("arbeitsstand", {}).items():
        if wert and vorher.get("arbeitsstand", {}).get(schluessel) != wert:
            geaendert[schluessel] = wert
    zahlen = {}
    for name in ("journal_anzahl", "figuren_anzahl", "szenen_anzahl"):
        if nachher.get(name) != vorher.get(name):
            zahlen[name] = {"vorher": vorher.get(name), "nachher": nachher.get(name)}
    return {"arbeitsstand_geaendert": geaendert, "zahlen_geaendert": zahlen}


class Mitschnitt:
    """Schreibt Screenshots und eine ``schritte.jsonl``-Zeile je Schritt."""

    def __init__(self, verzeichnis, lauf: str, geraet: str):
        self.verzeichnis = Path(verzeichnis)
        self.verzeichnis.mkdir(parents=True, exist_ok=True)
        self.jsonl_pfad = self.verzeichnis / "schritte.jsonl"
        self.lauf = lauf
        self.geraet = geraet
        self._n = 0

    def screenshot_pfad(self, phase: int, suffix: str) -> Path:
        self._n += 1
        name = f"{self._n:03d}-phase{phase}-{suffix}.png"
        return self.verzeichnis / name

    def schritt(self, *, phase: int, screenshot_vorher: Path,
               screenshot_nachher: Path, elemente: list, aktion: dict,
               begruendung: str, antwort: dict, db_diff: dict) -> None:
        zeile = {
            "zeit": time.time(), "phase": phase,
            "screenshot_vorher": Path(screenshot_vorher).name,
            "screenshot_nachher": Path(screenshot_nachher).name,
            "elemente_anzahl": len(elemente),
            "aktion": aktion, "begruendung": begruendung,
            "antwort_sekunden": antwort.get("sekunden"),
            "ohne_hinweis": antwort.get("ohne_hinweis"),
            "db_diff": db_diff,
        }
        with open(self.jsonl_pfad, "a", encoding="utf-8") as f:
            f.write(json.dumps(zeile, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"$PY" -m pytest tests/test_browser_mitschnitt.py -q`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_mitschnitt.py tests/test_browser_mitschnitt.py
git commit -m "Mitschnitt je Schritt: Screenshots, DB-Unterschied, schritte.jsonl"
```

---

### Task 9: Phase judge

**Files:**
- Create: `simulation/browser_judge.py`
- Test: `tests/test_browser_judge.py`

**Interfaces:**
- Consumes: Task 1's client interface (`.json_objekt(system, nutzer, art=...,
  bilder=...)`), `simulation/ux_rubrik.md` (Task 2).
- Produces: `lies_rubrik() -> str`, `bewerte_phase(client, phase_nummer: int,
  phase_name: str, screenshots: list[bytes], screenshot_namen: list[str],
  zaehler: dict) -> dict` with keys `note` (int 1–5 or `None` on failure),
  `befunde` (list of `{"text", "schwere", "screenshot"}`, at most 5). Used by
  `browser_lauf.fuehre_lauf` (Task 9/10... i.e. the next task).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_browser_judge.py
from simulation import browser_judge as j


class _FakeClient:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def json_objekt(self, system, nutzer, art="sim", bilder=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "bilder": bilder})
        if isinstance(self.antwort, Exception):
            raise self.antwort
        return self.antwort


def test_rubrik_wird_gelesen_und_steht_im_system_prompt():
    client = _FakeClient({"note": 4, "befunde": []})
    j.bewerte_phase(client, 1, "Terms", [b"img"], ["001.png"], {"x": 1})
    system = client.aufrufe[0]["system"]
    assert "The group authors, the bot assists" in system  # aus ux_rubrik.md


def test_bild_und_zaehler_gehen_mit():
    client = _FakeClient({"note": 3, "befunde": [{"text": "zu viele Fragen",
                                                   "schwere": "mittel"}]})
    ergebnis = j.bewerte_phase(client, 2, "Questions", [b"a", b"b"],
                               ["001.png", "002.png"], {"mehrere_fragen": 1})
    assert ergebnis["note"] == 3
    assert ergebnis["befunde"][0]["text"] == "zu viele Fragen"
    assert client.aufrufe[0]["bilder"] == [b"a", b"b"]
    assert "mehrere_fragen" in client.aufrufe[0]["nutzer"]


def test_modellfehler_liefert_keine_note_statt_zu_werfen():
    ergebnis = j.bewerte_phase(_FakeClient(ValueError("boom")), 1, "Terms",
                               [], [], {})
    assert ergebnis["note"] is None
    assert ergebnis["befunde"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"$PY" -m pytest tests/test_browser_judge.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# simulation/browser_judge.py
"""Die Phasenbewertung durch Opus (Padua-UX-Simulation, 2026-10-03): je
Phase eine Note 1-5 und bis zu fuenf Befunde, gegen die Checkliste aus
``simulation/ux_rubrik.md``."""

from __future__ import annotations

from pathlib import Path

RUBRIK_PFAD = Path(__file__).resolve().parent / "ux_rubrik.md"


def lies_rubrik() -> str:
    return RUBRIK_PFAD.read_text(encoding="utf-8")


_SYSTEM = """\
You are a strict UX reviewer for a participatory group-bot interface, \
judging ONE phase of a workshop run from screenshots and mechanical \
counters. Use the checklist below as your rubric. Reply with EXACTLY ONE \
JSON object, no markdown fence:

{{"note": <integer 1-5, 5 = excellent>,
 "befunde": [{{"text": <one sentence>, "schwere": "niedrig" | "mittel" | "hoch", \
"screenshot": <a filename from the list below, or null>}}]}}

At most 5 entries in "befunde", most severe first. Empty list if nothing is wrong.

Checklist:
{rubrik}
"""


def bewerte_phase(client, phase_nummer: int, phase_name: str,
                  screenshots: list[bytes], screenshot_namen: list[str],
                  zaehler: dict) -> dict:
    system = _SYSTEM.format(rubrik=lies_rubrik())
    nutzer = (
        f"Phase {phase_nummer}: {phase_name}\n\n"
        f"Screenshots (in order): {', '.join(screenshot_namen) or '(none)'}\n\n"
        f"Mechanical counters for this phase:\n{zaehler}"
    )
    try:
        ergebnis = client.json_objekt(system, nutzer, art="browser_judge",
                                      bilder=screenshots or None)
    except Exception:
        return {"note": None, "befunde": []}
    if not isinstance(ergebnis, dict):
        return {"note": None, "befunde": []}
    ergebnis.setdefault("note", None)
    ergebnis.setdefault("befunde", [])
    return ergebnis
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"$PY" -m pytest tests/test_browser_judge.py -q`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_judge.py tests/test_browser_judge.py
git commit -m "Phasenbewertung durch Opus gegen die UX-Rubrik"
```

---

### Task 10: Report (Markdown + contact sheet)

**Files:**
- Create: `simulation/browser_bericht.py`
- Test: `tests/test_browser_bericht.py`

**Interfaces:**
- Produces: `baue_markdown(lauf_titel: str, geraet: str, modelle: dict,
  phasen_ergebnisse: list[dict], top_befunde: list[dict]) -> str` (pure);
  `kontaktbogen(context, bild_pfade: list[Path], ausgabe: Path, spalten: int =
  4) -> None` (needs a Playwright browser `context`). Used by
  `browser_lauf.fuehre_lauf`/`main()` (Task 11).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_browser_bericht.py
from simulation import browser_bericht as b


def test_markdown_zeigt_titel_modelle_und_top_befunde():
    text = b.baue_markdown(
        "Padua browser run", "handy",
        {"persona": "claude-opus-5", "bot_gespraech": "kimi-k2"},
        [{"nummer": 1, "name": "Terms", "note": 4, "befunde": [],
          "zaehler_summe": {"seitliches_rutschen": False}}],
        [{"phase": 1, "schwere": "hoch", "text": "Chips blockieren die Eingabe"}],
    )
    assert "# Padua browser run (handy)" in text
    assert "claude-opus-5" in text
    assert "kimi-k2" in text
    assert "Chips blockieren die Eingabe" in text
    assert "## Phase 1 · Terms — note 4/5" in text
    assert "seitliches_rutschen" in text


def test_markdown_markiert_operator_fallback():
    text = b.baue_markdown("t", "handy", {}, [
        {"nummer": 3, "name": "Interviews", "note": None, "befunde": [],
         "fallback_benutzt": True, "zaehler_summe": {}},
    ], [])
    assert "Operator fallback used" in text
```

```python
# tests/test_browser_bericht.py (fortgesetzt, Playwright-Teil)
import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402


def test_kontaktbogen_erzeugt_eine_png_datei(tmp_path):
    bild = tmp_path / "001-phase1-vor.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page()
        seite.set_content("<h1>fixture</h1>")
        seite.screenshot(path=str(bild))
        ausgabe = tmp_path / "kontaktbogen.png"
        b.kontaktbogen(seite.context, [bild, bild], ausgabe, spalten=2)
        browser.close()
    assert ausgabe.exists()
    assert ausgabe.stat().st_size > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"$PY" -m pytest tests/test_browser_bericht.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# simulation/browser_bericht.py
"""Der Markdown-Bericht und der Kontaktbogen (Padua-UX-Simulation,
2026-10-03). Kein Pillow: der Kontaktbogen ist ein Playwright-Screenshot
einer kleinen HTML-Bildergalerie -- derselbe Werkzeugkasten wie der Rest
dieses Browserlaufs."""

from __future__ import annotations

from pathlib import Path


def baue_markdown(lauf_titel: str, geraet: str, modelle: dict,
                  phasen_ergebnisse: list[dict],
                  top_befunde: list[dict]) -> str:
    zeilen = [f"# {lauf_titel} ({geraet})", "", "## Overall", ""]
    if top_befunde:
        for befund in top_befunde[:5]:
            zeilen.append(
                f"- **{befund.get('schwere', '?')}** "
                f"(Phase {befund.get('phase', '?')}): {befund['text']}"
            )
    else:
        zeilen.append("(no findings)")
    zeilen += ["", "## Models used"]
    for art, name in sorted(modelle.items()):
        zeilen.append(f"- {art}: {name}")
    zeilen.append("")
    for phase in phasen_ergebnisse:
        note = phase.get("note")
        zeilen.append(
            f"## Phase {phase['nummer']} · {phase['name']} — "
            f"note {note if note is not None else '?'}/5"
        )
        zeilen.append("")
        if phase.get("fallback_benutzt"):
            zeilen += [
                "**Operator fallback used** — the persona got stuck and the "
                "phase was advanced via the harness's phase-click path (the "
                "same endpoint a group's own click on the phase bar uses).",
                "",
            ]
        for befund in phase.get("befunde", []):
            zeilen.append(f"- ({befund.get('schwere', '?')}) {befund['text']}")
        if phase.get("befunde"):
            zeilen.append("")
        zeilen += ["| counter | value |", "|---|---|"]
        for schluessel, wert in (phase.get("zaehler_summe") or {}).items():
            zeilen.append(f"| {schluessel} | {wert} |")
        zeilen.append("")
        for bild in phase.get("screenshots_fuer_bericht") or []:
            zeilen.append(f"![{bild}]({bild})")
        zeilen.append("")
    return "\n".join(zeilen)


def kontaktbogen(context, bild_pfade: list[Path], ausgabe: Path,
                 spalten: int = 4) -> None:
    """Alle Screenshots einer Phase verkleinert auf einem Blatt -- ein
    Playwright-Screenshot einer Rasterseite, kein Pillow."""
    kacheln = "".join(
        f'<figure><img src="file://{Path(p).resolve()}">'
        f"<figcaption>{Path(p).name}</figcaption></figure>"
        for p in bild_pfade
    )
    html = (
        "<style>body{margin:0;background:#222;font-family:sans-serif} "
        f"figure{{display:inline-block;width:{100 // spalten}%;margin:0;"
        "box-sizing:border-box;vertical-align:top}} "
        "img{width:100%;display:block} "
        "figcaption{color:#fff;font:11px monospace;padding:2px}</style>"
        f"<body>{kacheln}</body>"
    )
    seite = context.new_page()
    try:
        seite.set_content(html)
        seite.wait_for_timeout(200)
        seite.screenshot(path=str(ausgabe), full_page=True)
    finally:
        seite.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"$PY" -m pytest tests/test_browser_bericht.py -q`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_bericht.py tests/test_browser_bericht.py
git commit -m "Markdown-Bericht und Kontaktbogen fuer den Browserlauf"
```

---

### Task 11: CLI orchestrator (`python -m simulation.browser_lauf`)

**Files:**
- Create: `simulation/browser_lauf.py`
- Test: `tests/test_browser_lauf.py`
- Modify: `simulation/README.md` (add a short "Browserlauf" section),
  `AGENTS.md` (one-line pointer in the Simulation section)

**Interfaces:**
- Consumes: everything from Tasks 1–10 (`browser_elemente.extrahiere`/
  `bildschirmfoto`, `browser_zaehler.alle`/`installiere_messung`/
  `knoepfe_ohne_wirkung`, `browser_persona.naechste_aktion`,
  `browser_aktionen.fuehre_aus`/`warte_auf_antwort`,
  `browser_mitschnitt.datenstand`/`unterschied`/`Mitschnitt`,
  `browser_judge.bewerte_phase`, `browser_bericht.baue_markdown`/
  `kontaktbogen`, `browser_umgebung.starte_stack`/`Stack`).
- Produces: `fuehre_lauf(page, context, *, basis_url: str, token: str,
  db_pfad: str, chat_id: int, persona_client, judge_client, geraet: str,
  persona_name: str, bis_phase: int, lauf_verzeichnis: Path,
  max_schritte_je_phase: int = 25, fallback_nach_schritten: int = 8) -> dict`
  (summary dict: `phasen_ergebnisse`, `top_befunde`, `fehlgeschlagen_bei`);
  `main()` (thin CLI wrapper building the real stack via `browser_umgebung`
  and a real `claude.Claude()`, then calling `fuehre_lauf`, then
  `baue_markdown`/`kontaktbogen`, writing the report file).

**Required behaviour of `fuehre_lauf`** (write this as code, driven by its own
test — the structure below is the contract, not a suggestion to weaken):

- Set `os.environ["IT_WORKSHOP"] = "padua-2026"` once, at module import or in
  `main()` (NOT inside `fuehre_lauf`, so the test controls it) — this lets the
  orchestrator read phase names/goals straight from `interview_theater.phasen`
  instead of hard-coding English text redundantly.
- `page.goto(f"{basis_url}/g/{token}")`, wait for `#verlauf`.
- `browser_zaehler.installiere_messung(context)` once, before `goto`.
- For `aktuelle_phase` from 1 to `bis_phase`: loop up to `max_schritte_je_phase`
  steps. Each step: screenshot "vor", `extrahiere(page)`, call
  `naechste_aktion`, and:
  - if the action is `"done_phase"`: stop this phase's loop (no execution).
  - otherwise: `fuehre_aus`, `warte_auf_antwort`, screenshot "nach", compute the
    DB diff (`datenstand`/`unterschied`), accumulate `browser_zaehler.alle(page)`
    into a running per-phase tally, call `Mitschnitt.schritt(...)`.
  - read the live phase number off the page (`#roadmap` has
    `data-aktive-phase="N"` — read it with
    `page.get_attribute("#roadmap", "data-aktive-phase")`); if it moved past
    `aktuelle_phase`, stop this phase's loop (natural advance, no fallback).
  - if `fallback_nach_schritten` is reached with no advance: do the **documented
    operator fallback** — `urllib.request.urlopen` a `POST
    {basis_url}/g/{token}/chat/phase` with a nonce (read it the same way
    `tests/test_web_e2e_http.py::_nonce` does, from `GET chat/zustand`) and
    `{"nummer": aktuelle_phase + 1, "bestaetigt": 1}`; mark
    `fallback_benutzt = True` for this phase's result; advance.
- Once this phase's loop ends (naturally, by budget, or by fallback): call
  `browser_zaehler.knoepfe_ohne_wirkung(page)` **once** on the current screen
  (documented in Task 4 as never part of `alle()`'s per-step tally — it mutates
  the page) and fold it into this phase's counters; call `bewerte_phase(...)`
  with up to 3 representative "nach" screenshots from this phase; append the
  phase's result dict (`nummer`, `name` from `phasen.kurzname`, `note`,
  `befunde`, `zaehler_summe`, `fallback_benutzt`, `screenshots_fuer_bericht`
  — a short, report-sized subset of filenames, not every single one).
- After the phase loop: read `aufruf.art`/`aufruf.modell` DISTINCT pairs from
  `db_pfad` for the bot's models actually used (read-only connection), fold in
  `"persona": persona_client's configured model` and `"judge": ...` (ask the
  client for its `.modell` attribute — `claude.Claude` already exposes one).
- Collect `top_befunde`: the `hoch`-severity findings across all phases (plus
  `mittel` if fewer than 5 total), sorted by phase.
- Return the summary dict; never raise for a single phase's judge/model
  failure — record it and continue (same "a step may fail" posture as
  `simulation/lauf.py`'s `einfaedig()`).

```python
def main() -> None:
    """Dünner CLI-Wrapper: baut den echten Stack, einen echten Opus-Klienten
    und einen echten Browser, ruft ``fuehre_lauf``, schreibt den Bericht.

    Liest NIE die Env-Datei selbst -- ``browser_umgebung.starte_bot`` gibt
    ihren Pfad nur an ein Bash-Skript weiter (siehe dort)."""
    import argparse
    import os
    import sys
    import time
    from pathlib import Path

    from playwright.sync_api import sync_playwright

    from interview_theater import db
    from simulation import browser_bericht, browser_umgebung
    from simulation.claude import Claude

    os.environ["IT_WORKSHOP"] = "padua-2026"

    zerleger = argparse.ArgumentParser(prog="python -m simulation.browser_lauf")
    zerleger.add_argument("--env-datei", default=os.environ.get("IT_SIM_ENV", ""))
    zerleger.add_argument("--geraet", choices=["handy", "laptop"], default="handy")
    zerleger.add_argument("--persona", choices=["student", "clicker"], default="student")
    zerleger.add_argument("--bis-phase", type=int, default=7)
    zerleger.add_argument("--bericht", action="store_true")
    argumente = zerleger.parse_args()

    if not argumente.env_datei:
        print("Fehlende Env-Datei: --env-datei oder IT_SIM_ENV", file=sys.stderr)
        raise SystemExit(1)

    datum = time.strftime("%Y-%m-%d")
    lauf_name = f"{datum}-{argumente.geraet}"
    lauf_verzeichnis = Path("simulation/browser_laeufe") / lauf_name
    stack = browser_umgebung.starte_stack(argumente.env_datei, lauf_verzeichnis)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            geraet_profil = (
                {**p.devices["iPhone 13"]} if argumente.geraet == "handy"
                else {"viewport": {"width": 1440, "height": 900}}
            )
            context = browser.new_context(**geraet_profil)
            seite = context.new_page()
            persona_klient = Claude()
            richter_klient = Claude()
            ergebnis = fuehre_lauf(
                seite, context, basis_url=stack.web_basis, token=stack.token,
                db_pfad=stack.db_pfad, chat_id=stack.chat_id,
                persona_client=persona_klient, judge_client=richter_klient,
                geraet=argumente.geraet, persona_name=argumente.persona,
                bis_phase=argumente.bis_phase, lauf_verzeichnis=lauf_verzeichnis,
            )
            browser.close()
    finally:
        stack.beende()

    markdown = browser_bericht.baue_markdown(
        f"Padua browser UX simulation ({lauf_name})", argumente.geraet,
        ergebnis["modelle"], ergebnis["phasen_ergebnisse"], ergebnis["top_befunde"],
    )
    berichte_verzeichnis = Path("simulation/browser_berichte")
    berichte_verzeichnis.mkdir(parents=True, exist_ok=True)
    (berichte_verzeichnis / f"{lauf_name}.md").write_text(markdown, encoding="utf-8")
    print(f"Bericht: simulation/browser_berichte/{lauf_name}.md")
```

(The implementer writes `fuehre_lauf` itself from the bullet-point contract
above, driven by the test below — this is the one place in the plan where the
exact control flow is deliberately left to TDD rather than dictated line by
line, because its correctness is defined by observable behaviour, not by a
specific loop shape.)

- [ ] **Step 1: Write the failing test** — an offline integration test, no
  subprocess, no real model call: a real bot+web stack like
  `tests/test_web_e2e_http.py`'s `lauf` fixture (in-thread, `LLMAttrappe`), and a
  **scripted** fake persona client that returns a fixed sequence of actions
  driving phase 1 ("Terms") to completion via a typed message + a button click,
  then `"done_phase"`.

```python
# tests/test_browser_lauf.py
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from interview_theater import bot, db, einstellungen, repo, web, web_kanal
from simulation import browser_lauf

CHAT = 7_000_000_000_555


class _ScriptedClient:
    """Liefert eine feste Folge von Aktionen -- eine je Aufruf, egal welches
    Bild/welche Elementliste gesehen wird. Nach dem letzten Eintrag:
    ``done_phase`` fuer immer (haelt den Lauf an, statt ihn zu ueberrennen)."""

    def __init__(self, folge: list[dict]):
        self._folge = list(folge)
        self.aufrufe = 0

    def json_objekt(self, system, nutzer, art="sim", bilder=None):
        self.aufrufe += 1
        if self._folge:
            return self._folge.pop(0)
        return {"type": "done_phase", "begruendung": "fertig"}


class _FakeJudge:
    modell = "fake-judge"

    def json_objekt(self, system, nutzer, art="sim", bilder=None):
        return {"note": 5, "befunde": []}


class _LLMAttrappe:
    """Minimal: der Gespraechszug antwortet einmal mit einem gespeicherten
    Begriffsvorschlag, danach immer mit einer Quittung -- genug, um
    ``/g/<token>`` echt bis zum Tab-Wechsel zu befahren."""

    def schema(self, chat_id, system, nutzer, schema, art, **kw):
        if art == "erkenner":
            return {"aenderungen": []}
        if art == "journal":
            return {"eintraege": []}
        return {"antwort": "Got it, thanks."}


@pytest.fixture()
def stack(tmp_path, monkeypatch):
    pfad = str(tmp_path / "t.db")
    audio = tmp_path / "audio"
    monkeypatch.setenv("IT_AUDIO", str(audio))
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")

    aufbau = db.verbinde(pfad)
    db.initialisiere(aufbau)
    repo.sichere_gruppe(aufbau, CHAT, "gruppe1", "Testgruppe")
    repo.setze_gruppe_kanal(aufbau, CHAT, "web")
    token = repo.stelle_web_token_sicher(aufbau, CHAT)
    aufbau.commit()
    aufbau.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "", schluessel=b"x" * 32)
    web_faden = threading.Thread(target=dienst.serve_forever, daemon=True)
    web_faden.start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"

    bot_conn = db.verbinde(pfad)
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe1", db_pfad=pfad, audio_verz=str(audio),
        llm_url="u", llm_key="k", llm_modell="m", stt_basis="https://stt.test",
        stt_produkt="P", kanal=einstellungen.KANAL_WEB, web_chat_id=CHAT,
    )
    klm = _LLMAttrappe()
    kanal = web_kanal.WebKanal(bot_conn, CHAT, str(audio), schritt_s=0.05)
    pool = ThreadPoolExecutor(max_workers=2)
    halt = threading.Event()

    class _Halt(Exception):
        pass

    orig_hole = kanal.hole_updates
    def hole_updates(offset, timeout=25):
        if halt.is_set():
            raise _Halt()
        return orig_hole(offset, timeout=min(timeout, 0.5))
    kanal.hole_updates = hole_updates

    def fahre():
        try:
            bot.schleife(bot_conn, e, kanal, klm, None, pool)
        except _Halt:
            pass

    bot_faden = threading.Thread(target=fahre, daemon=True)
    bot_faden.start()

    yield basis, token, pfad

    halt.set()
    bot_faden.join(timeout=10)
    pool.shutdown(wait=True, cancel_futures=True)
    dienst.shutdown()
    dienst.server_close()
    web_faden.join(timeout=10)
    bot_conn.close()


def test_eine_scriptete_persona_faehrt_phase_eins_durch(stack, tmp_path):
    basis, token, pfad = stack
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        seite = context.new_page()
        seite.goto(f"{basis}/g/{token}")
        seite.wait_for_selector("#verlauf")

        persona = _ScriptedClient([
            {"type": "type_send", "text": "Our terms: arrival, work, night",
             "begruendung": "typing the terms"},
            {"type": "wait", "duration_ms": 500, "begruendung": "waiting for the bot"},
            {"type": "done_phase", "begruendung": "that is phase 1 done"},
        ])
        ergebnis = browser_lauf.fuehre_lauf(
            seite, context, basis_url=basis, token=token, db_pfad=pfad,
            chat_id=CHAT, persona_client=persona, judge_client=_FakeJudge(),
            geraet="handy", persona_name="student", bis_phase=1,
            lauf_verzeichnis=tmp_path / "lauf",
        )
        browser.close()

    assert len(ergebnis["phasen_ergebnisse"]) == 1
    phase1 = ergebnis["phasen_ergebnisse"][0]
    assert phase1["note"] == 5
    assert persona.aufrufe >= 2
    zeilen = (tmp_path / "lauf" / "schritte.jsonl").read_text().splitlines()
    assert len(zeilen) >= 1
    for zeile in zeilen:
        eintrag = json.loads(zeile)
        assert Path(tmp_path / "lauf" / eintrag["screenshot_vorher"]).exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"$PY" -m pytest tests/test_browser_lauf.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'simulation.browser_lauf'`.

- [ ] **Step 3: Implement** `simulation/browser_lauf.py` per the contract above
  (`fuehre_lauf` + `main()`), driven by the test until it passes. Add a short
  module docstring matching the project's documentation style.

- [ ] **Step 4: Run test to verify it passes, then run the module's own
  `--help`**

Run: `"$PY" -m pytest tests/test_browser_lauf.py -q`
Expected: PASS.

Run: `"$PY" -m simulation.browser_lauf --help`
Expected: argparse help text, exit 0 (no stack is started for `--help`).

- [ ] **Step 5: Update docs**

In `simulation/README.md`, add a short section (after the "Gegenprüfung"
section, matching the file's existing heading level and tone):

```markdown
## Der Browserlauf: die UX im echten Chromium

`simulation/browser_*.py` + `scripts... siehe unten` fahren nicht den
Bot-Code direkt an, sondern **die echte Webseite in einem echten,
headless Chromium** (Playwright): eine Opus-Persona bekommt bei jedem
Schritt einen Screenshot und die Liste der sichtbaren Bedienelemente,
entscheidet sich fuer genau eine Aktion, der Harness fuehrt sie aus und
wartet auf die Bot-Antwort. Dazu mechanische UX-Zaehler (seitliches
Rutschen, zu kleine Tippziele, Zoom-Fallen, Knoepfe ohne Wirkung, mehrere
Fragen je Nachricht) und ein Opus-Richter je Phase gegen die Checkliste in
`simulation/ux_rubrik.md` (Kopie aus Birks `participatory-bot-ux`-Skill).

```
IT_SIM_ENV=/pfad/zu/betrieb/padua-test.env \
  $PY -m simulation.browser_lauf --geraet handy --bis-phase 7 --bericht
$PY -m simulation.browser_lauf --env-datei betrieb/padua-test.env \
  --geraet laptop --persona clicker --bis-phase 4 --bericht
```

Startet einen echten Web-Server und einen echten Web-Bot-Prozess gegen eine
Wegwerf-Datenbank (`simulation/browser_laeufe/<lauf>/sim.db`) -- Betrieb
(Ports 8010/8030, `betrieb/padua.db`) wird nie beruehrt. Die
Modell-Zugangsdaten kommen per `source` aus der angegebenen Env-Datei direkt
in den Bot-Kindprozess; dieses Werkzeug liest sie selbst nie.

**Kostet Geld (die echte Modellkette des Bots), laeuft nie automatisch.**
Bericht: `simulation/browser_berichte/<lauf>.md`; Screenshots und
`schritte.jsonl` unter `simulation/browser_laeufe/<lauf>/`.
```

In `AGENTS.md`, in the "Simulation" section (near the existing `scripts/simulation.py`
paragraph), add one sentence: a pointer that `python -m simulation.browser_lauf`
drives the real web page in a real headless browser via an Opus persona for UX
screenshots and judging, distinct from `scripts/simulation.py` (which never opens
a browser), with its own `simulation/browser_*.py` files and
`simulation/ux_rubrik.md`.

- [ ] **Step 6: Commit**

```bash
git add simulation/browser_lauf.py tests/test_browser_lauf.py \
  simulation/README.md AGENTS.md
git commit -m "CLI-Orchestrator python -m simulation.browser_lauf + Doku-Hinweise"
```

---

### Task 12: Add `.gitignore` entries for run artifacts

**Files:**
- Modify: `.gitignore`

**Interfaces:** none (repo hygiene only).

- [ ] **Step 1: Check current `.gitignore`** for existing patterns like
  `simulation/laeufe/` / `simulation/berichte/*.md` (the existing simulation
  tool already gitignores its own run output, keeping only `verlauf.jsonl`).
  Follow the same shape.

- [ ] **Step 2: Add**

```gitignore
# Padua-Browserlauf: Rohlaeufe sind gross (Screenshots je Schritt) und
# koennen Betriebsdetails zeigen -- nur Bericht + Kontaktbogen der Abnahme
# werden von Hand committet (Task 10/13 dieses Plans), nicht jeder Lauf.
simulation/browser_laeufe/
```

Do **not** ignore `simulation/browser_berichte/` — the acceptance run's report
there must be committed per the card ("Ein vollständiger Handy-Lauf ... liegt
mit Bericht + Screenshots vor"); representative screenshots for that run are
committed explicitly in Task 13 by copying a handful out of the (gitignored)
`browser_laeufe/` run directory into a small, explicitly-added subfolder (see
Task 13).

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "Rohlaeufe des Browserlaufs gitignored, Berichte bleiben committet"
```

---

### Task 13 (operational, controller-executed — not a dispatched implementer subagent): Run the acceptance browser_lauf for real

This task spends real money against the live Infomaniak/Opus model chain and
needs a human-equivalent operator watching for dead ends (the operator fallback
in Task 11 is a documented escape hatch, not a silent one — every use must be
visible in the final report). The **controller** (the agent orchestrating this
whole plan) runs this task directly, in the current session, not through a
freshly dispatched implementer subagent — there is no spec-compliance code
review to gate here, only "did it produce real artifacts, correctly."

**Preconditions (verify before spending money):**
- Tasks 1–12 committed, full test suite green (`env -i HOME=$HOME
  PATH=/usr/bin:/bin "$PY" -m pytest -q -p no:cacheprovider`).
- `test -f /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-test.env`
  succeeds (use `dangerouslyDisableSandbox: true` on this one check — the
  session sandbox otherwise restricts path checks outside the worktree; `test
  -f` and `os.listdir`/`os.path` checks were confirmed to work with it this
  session, plain `ls` was not and is not needed here).
- Confirm with `IT_SIM_URL`/default pointing at `http://127.0.0.1:28764/v1/messages`
  that the proxy answers (`curl`-equivalent `httpx.post` smoke check, as
  verified manually earlier this session) — do this check again right before
  the run, cheaply (small `max_tokens`).

**Steps:**

- [ ] **Step 1: Phone run, phases 1–7**

```bash
IT_SIM_ENV=/mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-test.env \
  "$PY" -m simulation.browser_lauf --geraet handy --persona student \
  --bis-phase 7 --bericht
```

Run this with a generous timeout (phase 6/7 scene writing with Opus/Infomaniak
can take minutes per scene) and **do not background it blindly** — if it stalls
in a phase for longer than a few operator-fallback cycles with no sign of
progress in `simulation/browser_laeufe/<lauf>/schritte.jsonl` (watch it with
`tail -f` in a second call, or re-`Read` the file), investigate the bot log
(`simulation/browser_laeufe/<lauf>/bot.log`) before deciding whether to let the
fallback handle it or abort and fix a bug.

- [ ] **Step 2: Laptop run, phases 1–4**

```bash
IT_SIM_ENV=/mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-test.env \
  "$PY" -m simulation.browser_lauf --geraet laptop --persona clicker \
  --bis-phase 4 --bericht
```

- [ ] **Step 3: Verify artifacts**

For each run: the Markdown report exists under `simulation/browser_berichte/`,
mentions a note per phase, lists the models actually used (cross-check against
`SELECT DISTINCT art, modell FROM aufruf` on that run's `sim.db`, read-only, and
against the Claude proxy's own responses — `model` field in each JSON reply),
and — if any phase needed the operator fallback — says so explicitly, naming
the phase.

- [ ] **Step 4: Build and commit a representative artifact set**

Run directories under `simulation/browser_laeufe/` are gitignored (Task 12) and
can be large. Copy a small, explicit, representative subset into a committed
location — create `simulation/browser_berichte/<lauf-name>-bilder/` (not
gitignored) and copy into it: 2–3 screenshots per phase that illustrate the
report's top findings, plus the contact sheet(s) the tool already generated.
Update the Markdown report's image references to point at this committed
subfolder (relative path) before the final commit, so the report renders from
the repository alone. Verify by eye (`Read` the PNGs) that nothing committed
shows anything beyond the invented `simulation/interviews/` material running
through the UI — it cannot, since the run uses a fresh throwaway DB seeded only
by the persona's own invented conversation, but confirm visually anyway before
committing.

- [ ] **Step 5: Commit**

```bash
git add simulation/browser_berichte/
git commit -m "Abnahme-Laeufe des Padua-Browserlaufs: Handy Phase 1-7, Laptop Phase 1-4"
```

- [ ] **Step 6: Final full-suite confirmation**

```bash
env -i HOME=$HOME PATH=/usr/bin:/bin "$PY" -m pytest -q -p no:cacheprovider
```

Expected: all green. Report the final summary line (`N passed` / any skipped)
in the end-of-work message to the user, along with the commit list, the report
paths, the models actually used, and any unresolved SDD final-review
Critical/Important findings verbatim.

---

## Self-review notes (for the controller, before dispatching Task 1)

- **Spec coverage:** card points 1–5 → Tasks 6, 5, 3+4, 8, 11. Point 6 (rubric
  from the Hermes skill) → Task 2 + 9. Point 7 (sound) → deliberately scoped out
  in Task 11/13 with "Real-Test Birk" in the report, per the hard rules'
  explicit permission. Point 8 (report + contact sheet) → Task 10 + 13.
  Acceptance bullets → Task 13 (full runs + report), Task 4 (mutant-tested
  counters), Task 13 Step 3 (models-used belied in report), Task 12/Global
  Constraints (only invented material), Task 13 Step 6 (full suite green).
- **Known, declared scope cut:** the card's longer counter wishlist (doppelte
  Bestätigung, doppelte Knopfreihe, Chips grau nach Tippen, Sackgassen-Erkennung
  beyond the operator-fallback trigger) is **not** separately automated beyond
  what Task 4/7 build; the Opus phase judge (Task 9) covers these qualitatively
  against the rubric instead. State this explicitly in the Task 13 report under
  a "bekannte Grenzen" heading, matching this codebase's own documentation
  habit (see `AGENTS.md`'s many "Bekannte Grenze" notes) — this is not something
  to silently ship as if it were full coverage.
