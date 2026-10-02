# Phasen-Debrief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After every phase change, write a short automatic "debrief" (taste/tone/working-style, never content) for the phase just LEFT, store it, surface it in later prompts (incl. scene writing) and on the web Arbeitsstand page with a strike-out control; separately, fix the conversation journal block so rejections and the group's own proposals are never silently pushed out by scene-pipeline bookkeeping notes.

**Architecture:** One new module `interview_theater/phasen_debrief.py` owns the whole debrief pipeline (window → model call with existing modellwahl fallback → quote-check → storage) and is dispatched as a background thread from `phasen.setze` (the single place every phase transition already goes through). A new `phasen_debrief` table stores one row per (chat_id, phase). `kontext.py` grows one new block function reused by `szene.py`/`szenenfolge.py`/`kurzgeschichte.py`. `web_daten.py`/`web.py`/`web_schreiben.py` grow a read, a render, and a soft-delete POST handler, mirroring the existing `festlegung` pattern throughout. Part 2 is a separate, narrower change confined to `kontext._baue_journal` plus one new open-proposals block consumed by `szene.py`/`szenenfolge.py` only.

**Tech Stack:** Python 3.11, sqlite3, existing repo/kontext/web_* modules. No new dependencies.

**Python for all commands:** `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`

## Global Constraints

- Work happens on branch `feat/phasen-debrief`, worktree `/mnt/HC_Volume_106183673/projekte/interview-theater/.worktrees/phasen-debrief`. Never touch `/mnt/HC_Volume_106183673/projekte/interview-theater` (the main checkout) or its `betrieb/` files except as a read source copied via `VACUUM INTO` into `$TMPDIR` (Task 8 only).
- **Zusage 2 (no model call in a synchronous handler):** `phasen_debrief.starte(...)` must return almost immediately by spawning a daemon `threading.Thread` and returning — exactly the `kernzitate.starte` shape (`interview_theater/kernzitate.py:309-323`):
  ```python
  def starte(conn, klm, e, chat_id: int, phase: int):
      if klm is None:
          log.error("Phasen-Debrief ohne Sprachmodell, chat_id=%s, phase=%s", chat_id, phase)
          return None
      thread = threading.Thread(target=_lauf, args=(conn, klm, e, chat_id, phase), daemon=True)
      thread.start()
      return thread
  ```
  The message-count threshold and the on/off switch are checked **synchronously inside `starte()`** before the thread is spawned (cheap DB read, no model call) — if either fails, return `None` without spawning anything, same as `kernzitate.starte`'s `if klm is None` short-circuit.
- **No chat message is ever sent for a debrief.** No `tg` parameter anywhere in this feature's call chain.
- **No SQL outside `repo.py`/`db.py`** (except the pre-existing `web_daten.py` read-only exception). `phasen_debrief.py` calls only `repo.*` functions.
- Soft-delete for this one new table uses the brief's literal column name `geloescht INTEGER DEFAULT 0` — **not** the repo-wide `entfernt_am TEXT` convention used elsewhere (`schaerfung`, `festlegung`). This is an intentional, explicit deviation from house style because the brief specifies the column name; add a one-line comment at the `CREATE TABLE` noting the deviation so a future reader doesn't "fix" it to match the other tables.
- Prompt few-shot rule (Birk): **negative examples only**, never a positive example.
- Reasoning stays off for every call this feature makes (sovereign: don't pass `reasoning_effort`, defaults to `"none"`; Claude/Opus path: don't request extended thinking — this is a short classification/summarisation-shaped call, not the `szene.py` exception).
- Full test suite, whenever run (task self-check or final gate), runs in the **foreground**, clean env, never with a `betrieb/*.env` loaded:
  ```
  env -i HOME=$HOME PATH=/usr/bin:/bin /home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m pytest -q -p no:cacheprovider
  ```
  Per-task targeted tests may be run normally (`pytest tests/test_x.py -q`) without the clean-env wrapper.
- Do not edit `.gitignore`. Do not push. Commit at the end of every task.
- German identifiers/comments throughout, matching the repo (per AGENTS.md).

## File Map

- `interview_theater/db.py` — new `phasen_debrief` table, `TABELLEN_MIT_CHAT_ID` entry.
- `interview_theater/repo.py` — `merke_phasen_debrief`, `phasen_debriefs`, `entferne_phasen_debrief`, `nachrichten_zwischen`, `erste_nachricht_am`.
- `interview_theater/prompts/phasen_debrief.md` + `interview_theater/sprachen/en/prompts/phasen_debrief.md`.
- `interview_theater/phasen_debrief.py` — new module (the whole pipeline).
- `interview_theater/phasen.py` — `setze()` gains `klm=None, e=None` and dispatches the debrief job for the phase being left.
- Call sites passing `klm`/`e` into `phasen.setze`: `interview_theater/erkenner.py:1124`, `interview_theater/knoepfe/wirkung.py:1143`, `interview_theater/aufnahme.py:378`, `interview_theater/befehle.py:636`, `interview_theater/knoepfe/stationen.py:44`.
- `interview_theater/kontext.py` — `BUDGETS["debrief"]`, `baue_debrief_block()`, `_REIHENFOLGE` entry, `_bloecke()` entry, one `_kuerze_auf_budget` ladder step; Part 2: `_baue_journal` rewrite, `BUDGETS["journal"]`, new `offene_vorschlaege_block()`.
- `interview_theater/szene.py`, `interview_theater/kurzgeschichte.py`, `interview_theater/szenenfolge.py` — consume `kontext.baue_debrief_block`; `szene.py` and `szenenfolge.py` also consume `kontext.offene_vorschlaege_block` (Part 2).
- `interview_theater/web_daten.py` — `_phasen_debriefs` reader, included in the gruppe-page data and in `dashboard()`.
- `interview_theater/web.py` — `_phasen_debrief_html` render function, wired into the Arbeitsstand body.
- `interview_theater/web_schreiben.py` — `FELDER["phasen_debrief_streichen"]`, `_entferne_phasen_debrief`.
- `scripts/prompt_schnappschuss.py` output regenerated (`docs/prompt-audit/schnappschuss-vor-profilumbau.txt`).
- Tests: `tests/test_phasen_debrief.py` (new), `tests/test_kontext.py`, `tests/test_web.py`, `tests/test_web_daten.py` (or wherever the existing festlegung/web tests live — implementers must find the right file), `tests/test_db.py`/`tests/test_repo.py`, `tests/test_prompt_audit.py`, `tests/test_profil_bitgleich.py`.

---

## Task 1: Storage layer — `phasen_debrief` table and repo functions

**Files:**
- Modify: `interview_theater/db.py` (SCHEMA, `TABELLEN_MIT_CHAT_ID`)
- Modify: `interview_theater/repo.py`
- Test: new test module (find the convention — likely `tests/test_repo.py` or a feature-specific file like `tests/test_phasen_debrief.py`; create the latter if no obvious home exists, since later tasks add to it too)

**Interfaces produced (later tasks depend on these exact names):**
- `repo.merke_phasen_debrief(conn, chat_id: int, phase: int, text: str, modell: str) -> None` — upsert by `(chat_id, phase)`. On conflict, replace `text`, `erstellt_am` (fresh timestamp), `modell`, and reset `geloescht` to `0` (a fresh debrief is visible again even if a previous one for that phase had been struck — re-leaving a phase produces new, current content).
- `repo.phasen_debriefs(conn, chat_id: int) -> list[sqlite3.Row]` — `WHERE chat_id = ? AND geloescht = 0 ORDER BY phase ASC`.
- `repo.entferne_phasen_debrief(conn, chat_id: int, phase: int) -> None` — `UPDATE phasen_debrief SET geloescht = 1 WHERE chat_id = ? AND phase = ?`.
- `repo.nachrichten_zwischen(conn, chat_id: int, von: str, bis: str) -> list[sqlite3.Row]` — all messages (group AND bot) in `[von, bis]`, excluding transcript-typ rows, chronological. Reuse the existing `repo.TYP_TRANSKRIPT` constant / `_OHNE_TRANSKRIPT_ECHO` fragment (`repo.py:249-252`) for the exclusion, same as `repo.letzte_nachrichten`. Order by `message_id ASC`.
- `repo.erste_nachricht_am(conn, chat_id: int) -> str | None` — `SELECT MIN(gesendet_am) FROM nachricht WHERE chat_id = ?`.

All four new functions decorated `@_gesperrt` like every other `repo.py` function.

**Step 1 — schema.** Add to `interview_theater/db.py`'s `SCHEMA` string (model on the `schaerfung` table at `db.py:614-626`):
```sql
-- geloescht statt entfernt_am: Vorgabe aus der Spezifikation dieser Karte,
-- bewusste Abweichung von der sonstigen entfernt_am-Konvention.
CREATE TABLE IF NOT EXISTS phasen_debrief (
  id          INTEGER PRIMARY KEY,
  chat_id     INTEGER NOT NULL,
  phase       INTEGER NOT NULL,
  text        TEXT NOT NULL,
  erstellt_am TEXT NOT NULL,
  modell      TEXT,
  geloescht   INTEGER NOT NULL DEFAULT 0,
  UNIQUE (chat_id, phase)
);
CREATE INDEX IF NOT EXISTS idx_phasen_debrief_chat ON phasen_debrief(chat_id, phase);
```
Add `"phasen_debrief"` to the `TABELLEN_MIT_CHAT_ID` tuple (`db.py:1021-1049`) so `loesche_gruppe` purges it.

**Step 2 — repo functions.** Implement the four functions above in `repo.py`, following the `schaerfung`/`festlegung` CRUD style already in the file (`_gesperrt`, `conn.commit()`, no bare SQL outside this file). Use SQLite `INSERT ... ON CONFLICT(chat_id, phase) DO UPDATE SET ...` for the upsert (same pattern family as `repo.setze_phase`'s upsert-ish write).

**Step 3 — tests (write first, TDD):**
- Migration test: a fresh `db.initialisiere(conn)` creates the table (`PRAGMA table_info(phasen_debrief)` has the expected columns); `loesche_gruppe` removes rows for a given `chat_id` and leaves other chats' rows.
- `merke_phasen_debrief` + `phasen_debriefs` round-trip: insert, read back, fields match.
- Re-leaving replaces: call `merke_phasen_debrief` twice for the same `(chat_id, phase)` with different `text`; `phasen_debriefs` returns only the newest text, still one row.
- `entferne_phasen_debrief` then `phasen_debriefs` no longer returns it; `merke_phasen_debrief` again on the same phase makes it reappear with `geloescht = 0`.
- `nachrichten_zwischen` excludes a row with `typ = repo.TYP_TRANSKRIPT` and includes bot (`ist_bot = 1`) and group (`ist_bot = 0`) rows inside the window, excludes rows outside `[von, bis]`.
- `erste_nachricht_am` returns the earliest `gesendet_am` for the chat, `None` for an empty chat.

**Step 4 — run targeted tests, commit.**

---

## Task 2: Prompt files (DE + EN) and prompt-audit regeneration

**Files:**
- Create: `interview_theater/prompts/phasen_debrief.md`
- Create: `interview_theater/sprachen/en/prompts/phasen_debrief.md`
- Modify (regenerate): `docs/prompt-audit/schnappschuss-vor-profilumbau.txt` via `scripts/prompt_schnappschuss.py`
- Test: `tests/test_profil_bitgleich.py`, `tests/test_anweisungen.py` (if it asserts something generic about every prompt file, e.g. the "was du nicht von dir aus anfängst" check — this one does NOT apply, this prompt is not a `prompts/phasen/N.md` file, skip that specific assertion but verify no unrelated assertion breaks)

**Step 1 — write `interview_theater/prompts/phasen_debrief.md`** with exactly this content (the brief's German text, placeholders `{nummer}`/`{phasenname}` are plain Python string tokens filled by `.replace()` in Task 3's module — **not** the workshop `{{...}}` double-brace substitution, so leave them as single braces):

```
Du liest das vollstaendige Gespraech einer Gruppe aus Phase {nummer}
({phasenname}). Was sie festgelegt hat, ist schon gespeichert (unten). Schreib
NICHT das Ergebnis auf, sondern was jemand braeuchte, der mit dieser Gruppe
weiterarbeitet und ihren Geschmack treffen will.

Hoechstens vier kurze Abschnitte, jeder darf fehlen:
- Geschmack: was hat sie angezogen, was abgestossen? Abgelehntes zaehlt
  doppelt -- mit Grund, wenn einer genannt wurde.
- Ton: ernst, ironisch, wuetend, zart? Was hat Energie erzeugt, was hat
  gelangweilt?
- Arbeitsweise: schnell entschieden oder lange gerungen, Konsens oder Streit,
  eher Bilder oder eher Argumente?
- Offen: Spannungen, die nicht aufgeloest wurden.

Regeln: Jede Aussage hat ein woertliches Kurzzitat als Beleg, sonst faellt sie
weg. Beschreib die Gruppe, nie einzelne Personen -- keine Namen, keine
Psychologie, keine Bewertung. Nichts wiederholen, was in den Festlegungen
steht. Hoechstens 120 Woerter. Gibt die Phase nichts her: antworte NICHTS.

Beispiel fuer eine FALSCHE Antwort -- so nicht:
"Geschmack: Leyla wollte unbedingt ein trauriges Ende, waehrend der Rest eher
Richtung Komoedie wollte. Ton: Mira war die ganze Zeit sehr nervoes und hat
viel gezoegert. Arbeitsweise: Die Gruppe hat sich auf das Setting Schulhof
geeinigt."
Das ist falsch: Es nennt Namen und psychologisiert eine einzelne Person
("Mira war ... sehr nervoes" ist keine Gruppenbeobachtung). Es wiederholt eine
Festlegung (das Setting steht schon gespeichert). Und keine der drei Aussagen
traegt ein woertliches Zitat als Beleg.
```
(Use literal `{nummer}`/`{phasenname}` tokens, not f-string braces escaped — this is a plain `.md` file, no Python syntax inside it.)

**Step 2 — EN mirror** at `interview_theater/sprachen/en/prompts/phasen_debrief.md`: translate the prose, but **keep the literal sentinel word `NICHTS` unchanged** (it is a fixed protocol keyword the code checks for, like other cross-language fixed markers in this repo — not a word to localise), with a short English parenthetical next to it the first time it appears, e.g. "answer **NICHTS** (nothing)". Translate the rest (headings, the negative example, the names can stay — Leyla/Mira are fine as example names in English too).

**Step 3 — regenerate the prompt audit snapshot:**
```
/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3 -m scripts.prompt_schnappschuss
```
Confirm via `git diff docs/prompt-audit/schnappschuss-vor-profilumbau.txt` that the diff is **additive only** (new `prompt phasen_debrief` / `prompt en/phasen_debrief` section(s) appended) and no existing section's hash changed. Per `tests/test_profil_bitgleich.py`'s own documented rule ("Neue Abschnitte sind erlaubt"), no further justification entry is needed — just verify the diff is clean before committing.

**Step 4 — run `pytest tests/test_profil_bitgleich.py tests/test_prompt_audit.py -q`**, confirm green (a sanity check that loading `anweisungen.hole("phasen_debrief")` returns non-empty text is enough here; the full usage-in-context tests belong to Task 3).

**Step 5 — commit.**

---

## Task 3: `phasen_debrief.py` module, trigger wiring, model routing, quote-check

**Depends on:** Task 1 (repo functions), Task 2 (prompt file).

**Files:**
- Create: `interview_theater/phasen_debrief.py`
- Modify: `interview_theater/phasen.py` (`setze`)
- Modify call sites: `interview_theater/erkenner.py:1124`, `interview_theater/knoepfe/wirkung.py:1143`, `interview_theater/aufnahme.py:378`, `interview_theater/befehle.py:636`, `interview_theater/knoepfe/stationen.py:44`
- Test: `tests/test_phasen_debrief.py`

**Interfaces produced (Task 4 depends on these):**
- `phasen_debrief.starte(conn, klm, e, chat_id: int, phase: int) -> threading.Thread | None`
- Internally: window computation, model call via `modellwahl.aufruf_schema`, quote-filter, storage via `repo.merke_phasen_debrief`.

### Step 1 — env helpers (hot-read, no caching, model on `kontext._aus_umgebung`, `kontext.py:163-182`)

```python
import os

_ENV_AN = "IT_PHASEN_DEBRIEF"
_ENV_MINDEST = "IT_DEBRIEF_MIN_NACHRICHTEN"
_MINDEST_VORGABE = 6

def _aktiv() -> bool:
    wert = (os.environ.get(_ENV_AN) or "").strip().lower()
    return wert not in ("0", "aus", "off")

def _mindest_nachrichten() -> int:
    roh = os.environ.get(_ENV_MINDEST)
    try:
        n = int(roh) if roh else _MINDEST_VORGABE
    except ValueError:
        n = _MINDEST_VORGABE
    return max(n, 0)
```

### Step 2 — phase window

```python
import re
from interview_theater import repo

_PHASE_MUSTER = re.compile(r"^Phase (\d+)\b")

def _phasenfenster(conn, chat_id: int, phase: int) -> tuple[str, str]:
    """(von, bis) fuer die zuletzt verlassene Phase `phase`. `bis` ist jetzt."""
    bis = _jetzt()
    von = None
    for eintrag in repo.journal(conn, chat_id):
        treffer = _PHASE_MUSTER.match(eintrag["text"] or "")
        if treffer and int(treffer.group(1)) == phase:
            von = eintrag["erstellt_am"]  # letzter Treffer gewinnt: juengster Eintritt
    if von is None:
        von = repo.erste_nachricht_am(conn, chat_id) or bis
    return von, bis
```
(Use whatever "now, ISO, microsecond precision" helper the repo already has — check `repo.py` for `_jetzt`/`_jetzt_fein` and reuse the same one `setze_phase` uses, via a small local `_jetzt()` wrapper or direct import, so phase-boundary timestamps sort correctly against `erstellt_am`/`gesendet_am` strings.)

Verify `repo.journal(conn, chat_id)` rows expose `["text"]` and `["erstellt_am"]` keys (used already by `kontext._baue_journal`) before relying on them.

### Step 3 — build the input text (excludes transcripts/hidden/verdichtungen by construction, since `nachrichten_zwischen` already filters `typ='transkript'` and verdichtungen are never read from `nachricht`)

```python
def _gruppennachrichten_anzahl(zeilen) -> int:
    return sum(1 for z in zeilen if not z["ist_bot"])

def _korpus(zeilen) -> str:
    """Rohtext aller Zeilen, Basis fuer den Zitat-Check."""
    return "\n".join((z["text"] or "") for z in zeilen)

def _nachrichtentext(zeilen) -> str:
    """Formatierter Verlauf fuer den Prompt: 'Absender: Text' je Zeile."""
    return "\n".join(f"{z['absender'] or ('Bot' if z['ist_bot'] else 'Gruppe')}: {z['text'] or ''}" for z in zeilen)
```

Build the "already saved, don't repeat" block by reusing whatever existing functions already assemble festlegungen + arbeitsstand as human-readable text — **search for them** (`repo.festlegungen`, and the arbeitsstand-to-text function `kontext` or `fehlstellen`/`roadmap`/`vorspann` already use to render the structured state; do not invent a second rendering of the same data — reuse). If no single existing function renders "all of arbeitsstand as text", reuse `repo.festlegungen` plus the same per-field rendering `kontext._baue_festlegungen`/`roadmap` already does, or call `kontext._baue_festlegungen(conn, chat_id)` and `fehlstellen`'s underlying arbeitsstand read directly — pick whichever avoids duplicating logic, and note the choice in the report.

```python
def _nutzertext(conn, chat_id, zeilen, bereits_gespeichert: str) -> str:
    teile = []
    if bereits_gespeichert:
        teile.append("Schon gespeichert (nicht wiederholen):\n" + bereits_gespeichert)
    teile.append(_nachrichtentext(zeilen))
    return "\n\n".join(teile)
```

### Step 4 — model routing (reuse `modellwahl.aufruf_schema` verbatim — it already implements "try Opus, fall back to sovereign on failure")

```python
from interview_theater import modellwahl, phasen, szene_claude, zitat
from interview_theater.knoepfe.texte import PHASE_SETTING  # the existing phase>=4 constant used by modellwahl.konversation_ueber_claude

SCHEMA = {
    "type": "object",
    "properties": {"antwort": {"type": "string"}},
    "required": ["antwort"],
    "additionalProperties": False,
}
ART = "phasen_debrief"

def _ueber_claude(e, conn, chat_id: int, phase: int) -> bool:
    return phase >= PHASE_SETTING and szene_claude.ist_aktiv(e, conn, chat_id)
```

Important: do **not** reuse `modellwahl.konversation_ueber_claude` directly — it checks the group's **current** phase, but a debrief judges the phase just **left**, which can differ (e.g. the group already advanced past 4 while this runs). Gate on the `phase` parameter instead, as above.

```python
def _rufe_modell(conn, klm, e, chat_id: int, phase: int, phasenname: str, nutzertext: str) -> str | None:
    system = anweisungen.hole("phasen_debrief").replace("{nummer}", str(phase)).replace("{phasenname}", phasenname)
    try:
        antwort = modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system, nutzertext, SCHEMA, ART,
            ueber_claude=_ueber_claude(e, conn, chat_id, phase),
        )
    except Exception:
        log.exception("Phasen-Debrief: Modellaufruf fehlgeschlagen, chat_id=%s, phase=%s", chat_id, phase)
        return None
    return (antwort or {}).get("antwort")
```
Check `modellwahl.aufruf_schema`'s actual exception contract (`modellwahl.py:59-99`) — it already catches `(szene_claude.ClaudeFehler, LLMFehler)` internally and falls back; the `try/except Exception` above is the outer safety net for anything else (e.g. a schema/JSON error from the sovereign path itself), matching `kernzitate._lauf`'s broad-except style.

### Step 5 — quote check (per-line drop, reusing `zitat.pruefe`)

Rule (your interpretation, stated for the implementer to follow literally): split the model's `antwort` text on blank-line-separated paragraphs/lines. For each non-empty line: find all `„...“`-style quoted spans (use the same quote characters `zitat.normalisiere` already maps — don't hand-roll a second quote-character list); if the line contains **zero** quotes, drop it (the prompt demands every statement carry one); if it contains one or more quotes, keep the line only if **every** quote in it passes `zitat.pruefe(quote, korpus)` against the phase's message corpus (`_korpus(zeilen)`, the RAW, un-normalised message text — `zitat.pruefe` does its own normalisation). Join surviving lines back with the same separator. If the result is empty, or the original `antwort` (stripped, case-insensitive) equals `"nichts"`, return `""`.

```python
_ZITAT_MUSTER = re.compile(r"„([^„“]*)“")

def _gefiltert(antwort: str, korpus: str) -> str:
    if not antwort or antwort.strip().strip(".").lower() == "nichts":
        return ""
    zeilen = antwort.splitlines()
    behalten = []
    for zeile in zeilen:
        if not zeile.strip():
            behalten.append(zeile)
            continue
        zitate = _ZITAT_MUSTER.findall(zeile)
        if not zitate:
            continue
        if all(zitat.pruefe(z, korpus) for z in zitate):
            behalten.append(zeile)
    text = "\n".join(behalten).strip()
    return text
```
Adjust the quote regex to whatever quote glyphs actually appear in the prompt's instruction (`„…“`) — confirm against `zitat.normalisiere`'s `_ERSETZUNGEN` mapping so the same characters are recognised on both sides.

### Step 6 — the job itself

```python
import threading, logging
log = logging.getLogger(__name__)

def starte(conn, klm, e, chat_id: int, phase: int):
    if klm is None or not _aktiv():
        return None
    von, bis = _phasenfenster(conn, chat_id, phase)
    zeilen = repo.nachrichten_zwischen(conn, chat_id, von, bis)
    if _gruppennachrichten_anzahl(zeilen) < _mindest_nachrichten():
        return None
    thread = threading.Thread(target=_lauf, args=(conn, klm, e, chat_id, phase, zeilen), daemon=True)
    thread.start()
    return thread

def _lauf(conn, klm, e, chat_id: int, phase: int, zeilen) -> None:
    try:
        phasenname = phasen.bezeichnung(phase)  # or whatever the existing name-lookup is called — confirm exact function name
        bereits_gespeichert = ...  # Step 3
        nutzertext = _nutzertext(conn, chat_id, zeilen, bereits_gespeichert)
        antwort = _rufe_modell(conn, klm, e, chat_id, phase, phasenname, nutzertext)
        if not antwort:
            return
        text = _gefiltert(antwort, _korpus(zeilen))
        if not text:
            return
        modell = "claude" if _ueber_claude(e, conn, chat_id, phase) else "sovereign"  # best-effort label, not load-bearing
        repo.merke_phasen_debrief(conn, chat_id, phase, text, modell)
    except Exception:
        log.exception("Phasen-Debrief fehlgeschlagen, chat_id=%s, phase=%s", chat_id, phase)
        repo.merke_vorfall(conn, chat_id, "phasen_debrief_fehler")  # confirm exact merke_vorfall signature in repo.py before use
```
Check `phasen.py` for the exact function that turns a phase number into its display name (research found `bezeichnung(nummer)` used inside `phasen.setze` itself at `phasen.py:178`) and `repo.merke_vorfall`'s real signature before writing this.

### Step 7 — wire into `phasen.setze`

Current body (`phasen.py:176-199`):
```python
def setze(conn, chat_id: int, nummer: int, quelle: str, notiz: str | None = None) -> bool:
    if repo.hole_phase(conn, chat_id) == nummer:
        return False
    repo.setze_phase(conn, chat_id, nummer)
    text = f"Phase {bezeichnung(nummer)}"
    if notiz:
        text = f"{text} ({notiz})"
    repo.schreibe_journal(conn, chat_id, "entschieden", text, quelle=quelle)
    return True
```
Change to:
```python
def setze(conn, chat_id: int, nummer: int, quelle: str, notiz: str | None = None,
          klm=None, e=None) -> bool:
    vorherige = repo.hole_phase(conn, chat_id)
    if vorherige == nummer:
        return False
    repo.setze_phase(conn, chat_id, nummer)
    text = f"Phase {bezeichnung(nummer)}"
    if notiz:
        text = f"{text} ({notiz})"
    repo.schreibe_journal(conn, chat_id, "entschieden", text, quelle=quelle)
    from interview_theater import phasen_debrief  # lokaler Import: Zyklus vermeiden
    phasen_debrief.starte(conn, klm, e, chat_id, vorherige)
    return True
```
This fires for **every** call site uniformly ("both directions, any source"), including `aufnahme.stelle_phase_interviews_sicher` which never calls `eintritt_in_phase`.

### Step 8 — update the five call sites

At each of `erkenner.py:1124`, `knoepfe/wirkung.py:1143`, `aufnahme.py:378`, `befehle.py:636`, `knoepfe/stationen.py:44`: inspect the enclosing function's parameters/locals and pass `klm=klm, e=e` (or whatever the local variable names actually are at that call site — confirm each one individually, do not assume). If a site genuinely has no `e` or `klm` in scope, pass `None` for the missing one explicitly rather than silently omitting the keyword (so it's visible in a diff that a site is not wired up, and the report must name which site(s), if any, could not be wired and why).

### Step 9 — tests (`tests/test_phasen_debrief.py`)

- `starte` returns `None` and spawns nothing when `IT_PHASEN_DEBRIEF=0|aus|off` is set (monkeypatch `os.environ`).
- `starte` returns `None` when the phase window has fewer than `_mindest_nachrichten()` group messages; returns a `Thread` when it has exactly the threshold or more (monkeypatch `_lauf`/the model call so no real network call happens in the unit test — use a fake `klm`).
- `phasen.setze` dispatches `phasen_debrief.starte` with the **previous** phase number, not the new one (monkeypatch `phasen_debrief.starte`, assert call args); setting the same phase again does not call it (early `return False`).
- Input exclusion: seed a chat with a `typ=repo.TYP_TRANSKRIPT` row inside the phase window; assert the built `_nachrichtentext`/`_korpus` does not contain its text.
- Model routing, driven through `_lauf`/`_rufe_modell` with fakes: phase 2 → `ueber_claude=False` reaches the fake sovereign client; phase 4 with `szene_claude.ist_aktiv` patched to `False` → sovereign; phase 4 with it patched to `True` → the fake Claude path is used; Claude path raising → sovereign path's result is what gets stored (exercise this via `modellwahl.aufruf_schema`'s real fallback, with `szene_claude.schema`/`llm.LLM.schema` faked).
- Quote check: an `antwort` with one valid-quote line and one invented-quote line → only the valid line is stored; an `antwort` of `"NICHTS"` (and `"nichts"`, mixed case) → nothing is stored (`repo.phasen_debriefs` stays empty).
- Re-leaving replaces: call `_lauf` twice for the same `(chat_id, phase)` with different model outputs (fake), assert `repo.phasen_debriefs` shows only the latest text, one row.

### Step 10 — run `pytest tests/test_phasen_debrief.py -q`, then the touched modules' existing suites (`tests/test_phasen.py`, `tests/test_erkenner.py`, `tests/test_befehle.py`, `tests/test_aufnahme.py`, `tests/test_knoepfe*.py` — whichever exist and cover the five call sites), commit.

---

## Task 4: Context block — "So arbeitet diese Gruppe" in `kontext.py` + scene-writing paths

**Depends on:** Task 1 (repo), Task 3 (nothing structural, but conceptually this is what makes stored debriefs visible).

**Files:**
- Modify: `interview_theater/kontext.py`
- Modify: `interview_theater/szene.py`, `interview_theater/kurzgeschichte.py`, `interview_theater/szenenfolge.py`
- Test: `tests/test_kontext.py`, `tests/test_szene.py` (or wherever scene-prompt assembly is tested), `tests/test_szenenfolge.py`, `tests/test_kurzgeschichte.py`, `tests/test_erkenner.py`/`tests/test_journal.py` (negative check: block absent there)

### Step 1 — budget

In `kontext.py`'s `BUDGETS` dict (`kontext.py:76-96`), add:
```python
"debrief": 800,  # 800 Token * _ZEICHEN_JE_TOKEN(3) = 2400 Zeichen, wie "festlegungen"
```
(This mirrors `festlegungen`'s existing value exactly — 800 tokens × the module's `_ZEICHEN_JE_TOKEN` = 2400 chars, which is the number the brief states directly in chars. Do not set `BUDGETS["debrief"] = 2400` literally — that would be 3x too large once multiplied by `_ZEICHEN_JE_TOKEN` elsewhere.)

### Step 2 — the block function (public — reused outside `kontext.py`)

```python
def baue_debrief_block(conn, chat_id: int) -> str:
    """'So arbeitet diese Gruppe': gespeicherte Phasen-Debriefs, aelteste Phase zuerst."""
    zeilen = repo.phasen_debriefs(conn, chat_id)
    if not zeilen:
        return ""
    abschnitte = [f"### {phasen.bezeichnung(z['phase'])}\n{z['text']}" for z in zeilen]
    grenze = BUDGETS["debrief"] * _ZEICHEN_JE_TOKEN
    # Ueber dem Budget: aelteste Phasen zuerst verwerfen (am wenigsten aktuell).
    while abschnitte and sum(len(a) for a in abschnitte) + 2 * (len(abschnitte) - 1) > grenze:
        abschnitte.pop(0)
    if not abschnitte:
        return ""
    return "So arbeitet diese Gruppe:\n\n" + "\n\n".join(abschnitte)
```
Confirm the exact heading text/format convention other blocks use (look at `_baue_festlegungen`'s header line) and match it rather than inventing new formatting. Confirm `phasen.bezeichnung` is importable from `kontext.py` without a cycle (it already imports `phasen` elsewhere, per `_baue_phasenhinweis` likely doing so — verify).

### Step 3 — wire into `_bloecke()` / `_REIHENFOLGE`

In `_REIHENFOLGE` (`kontext.py:224-228`), insert `"debrief"` right after `"festlegungen"`:
```python
_REIHENFOLGE = (
    "verdichtungen", "transkripte", "kernpaket", "arbeitsstand", "festlegungen",
    "debrief",
    "phasenhinweis", "figurenhinweis", "szene", "journal", "fenster",
    "ausloeser", "erstkontakt",
)
```
In `_bloecke()` (`kontext.py:1535-1569`), add `"debrief": baue_debrief_block(conn, chat_id)` to the returned dict (no phase gating needed — a debrief for phase N only exists once the group has left phase N, so it naturally never appears while the group is still in N).

### Step 4 — add one `_kuerze_auf_budget` ladder step

In `_kuerze_auf_budget` (`kontext.py:1572-1715`), after the existing `festlegungen`-trim stage, add an analogous stage for `"debrief"`: if the prompt is still over `ZIEL` after trimming festlegungen, drop whole phase-sections from the **front** (oldest) of the `"debrief"` block's text (re-derive by calling `baue_debrief_block` is wasteful — instead, if `bloecke["debrief"]` is non-empty and the overall length is still too high, pop oldest `###`-separated sections from `bloecke["debrief"]` the same way `baue_debrief_block` does, or simply clear it to `""` as a blunt last resort if the codebase's existing ladder style prefers whole-block-wipe steps over partial section drops at this stage — check how `verdichtungen` is handled (research says "verdichtungen (wiped)") and prefer the simpler wipe if partial-drop would duplicate too much logic). Write a `vorfall` the same way the existing stages do, reusing the same constant (`"kontext_gekuerzt"`).

### Step 5 — scene-writing paths

- `szene.py`: in `baue_nutzertext`'s inner `_bloecke(...)` (`szene.py:1987`), add `"debrief": kontext.baue_debrief_block(conn, chat_id)`; add `"debrief"` to `_REIHENFOLGE` (`szene.py:1910-1916`) right after `"continuity"`/`"verworfen"`, before `"chat"`. Import `kontext` if not already imported (check for a cycle — `kontext.py` must not import `szene.py` at module level; if it does, use a local import inside `baue_nutzertext` instead).
- `kurzgeschichte.py`: in `baue_nutzertext` (`kurzgeschichte.py:363-413`), insert `kontext.baue_debrief_block(conn, chat_id)` into `teile` between the `regie` append and the final `teile.append(auftrag)` (~line 411-412), only if non-empty (follow the existing `if t` filtering already used by the final join).
- `szenenfolge.py`: in both `baue_nutzertext_geschichte` (`szenenfolge.py:1092-1099`) and `baue_nutzertext` (`szenenfolge.py:1102-1110`), insert the debrief block into `teile` between `_erfundenes(...)`/`_material(...)` and `auftrag`, same non-empty filtering.

### Step 6 — verify exclusion from erkenner/journal/verdichter

Confirm (grep) that `erkenner.py`, `journal.py`, `verdichter.py` do **not** call `kontext.baue`/`kontext._bloecke`/`kontext.baue_debrief_block` anywhere (they build their own prompts independently). If any of them DOES reuse a `kontext` block-building helper, explicitly exclude `"debrief"` there and say so in the report.

### Step 7 — tests

- `tests/test_kontext.py`: a stored debrief for phase 3 appears in `kontext.baue(...)` for a chat currently in phase 4+ (later phase); budget-trim test with debrief text exceeding `BUDGETS["debrief"]` worth of chars drops the **oldest** phase section first; no debriefs → block absent (not even the heading).
- Scene-writing tests: `szene.baue_nutzertext(...)` output contains the debrief heading/text when one exists for the chat; same for `kurzgeschichte.baue_nutzertext` and both `szenenfolge.baue_nutzertext*` functions.
- Negative test: build whatever erkenner/journal/verdichter use to assemble their prompt for a chat that HAS a stored debrief, and assert the debrief text does not appear there.

### Step 8 — run targeted tests, commit.

---

## Task 5: Web UI — Arbeitsstand section "So arbeitet ihr" + streichen control

**Depends on:** Task 1 (repo).

**Files:**
- Modify: `interview_theater/web_daten.py`
- Modify: `interview_theater/web.py`
- Modify: `interview_theater/web_schreiben.py`
- Test: whatever existing test files cover these three modules (likely `tests/test_web.py`, `tests/test_web_daten.py`, `tests/test_web_schreiben.py` — confirm exact names first)

**Note (from the user):** Karte W is already on this branch — `web_vereint`'s `"stand"` tab already renders the Arbeitsstand body via whatever `web.py` function it calls (research found `web.gruppe_koerper(...)`, confirm the exact name in this branch's `web_vereint.py`). No tab-wiring work is needed here — adding the section to that body function is sufficient.

### Step 1 — `web_daten.py` read

Add, modeled on `_festlegungen` (`web_daten.py:921-944`):
```python
def _phasen_debriefs(conn, chat_id: int) -> list[dict]:
    try:
        zeilen = conn.execute(
            "SELECT phase, text, erstellt_am FROM phasen_debrief "
            "WHERE chat_id = ? AND geloescht = 0 ORDER BY phase ASC",
            (chat_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(z) for z in zeilen]
```
Include it under a `"phasen_debriefs"` key in whatever function assembles the full gruppe-page data dict (find it — the same function that already includes `_festlegungen(...)`).

### Step 2 — `web.py` render

Add a function modeled on `_festlegungen_html` (`web.py:1517-1549`):
```python
def _phasen_debrief_html(daten: dict, nonce_wert: str | None) -> str:
    zeilen = daten.get("phasen_debriefs") or []
    if not zeilen:
        return ""
    karten = []
    for z in zeilen:
        knopf = _rahmen("", "phasen_debrief_streichen", z["phase"], knopf="streichen") if nonce_wert else ""
        karten.append(f"<div class='debrief'><h3>Phase {z['phase']}</h3><p>{escape(z['text'])}</p>{knopf}</div>")
    return "<section class='so-arbeitet-ihr'><h2>So arbeitet ihr</h2>" + "".join(karten) + "</section>"
```
Confirm the actual HTML-escaping helper used elsewhere in `web.py` (likely `html.escape` or a local wrapper) and reuse it — do not introduce raw unescaped text. Confirm the exact `_rahmen(...)` signature and the convention for the button label string (may need a `T.`-style text constant rather than a bare `"streichen"` literal — check how `T.TEXT_ENTFERNEN` is defined/used and add a sibling constant if that's the house convention). Wire the returned HTML into whatever function builds the full Arbeitsstand body (next to where `_festlegungen_html(...)` is called), positioned near the festlegungen section.

### Step 3 — `web_schreiben.py` POST handler

Add to `FELDER` (`web_schreiben.py:523+`): `"phasen_debrief_streichen": _entferne_phasen_debrief`.
```python
def _entferne_phasen_debrief(conn, chat_id: int, wert: str, ziel) -> str:
    try:
        phase = int(wert)
    except (TypeError, ValueError):
        raise Fehler("Ungueltige Phase.")
    repo.entferne_phasen_debrief(conn, chat_id, phase)
    repo.schreibe_journal(conn, chat_id, "entschieden", f"Debrief Phase {phase} gestrichen", quelle=QUELLE)
    return "Debrief gestrichen."
```
Match the existing `_entferne_festlegung` (`web_schreiben.py:444-468`) for exact return-string/exception conventions (the house pattern may require checking existence first and raising a specific `Fehler` message if nothing to strike — mirror that if so).

### Step 4 — tests

- `web_daten._phasen_debriefs` returns stored, non-struck rows only.
- `web.py`: the render function emits a "streichen" control only when `nonce_wert` is truthy (mirror whatever existing test does this for `_festlegungen_html`); renders nothing (no section at all) when there are no debriefs; escapes HTML in the debrief text.
- `web_schreiben.py`: POST `phasen_debrief_streichen` with a valid phase soft-deletes it (`repo.phasen_debriefs` no longer returns it) and writes a journal row with `quelle='web'`; the existing "no SQL in web_schreiben.py" / "no write path in web_daten.py" structural tests still pass unmodified.
- End-to-end-ish: after striking, `kontext.baue_debrief_block(conn, chat_id)` (Task 4) no longer includes that phase's text — this test may need to live in `tests/test_kontext.py` instead if that's cleaner; implementer's call, but it must exist somewhere.

### Step 5 — run targeted tests, commit.

---

## Task 6: Dashboard indicator

**Depends on:** Task 1 (repo).

**Files:**
- Modify: `interview_theater/web_daten.py` (`dashboard`)
- Test: `tests/test_web_daten.py` (dashboard tests)

### Step 1

In `web_daten.dashboard` (`web_daten.py:377-418`), add one more key to the per-group dict, following the existing `verdichtungen`/`szenen` count pattern (`web_daten.py:399-406`):
```python
"phasen_debriefs": conn.execute(
    "SELECT count(*) FROM phasen_debrief WHERE chat_id = ? AND geloescht = 0",
    (chat_id,),
).fetchone()[0],
```
Wrap in the same `try/except sqlite3.OperationalError: ... = 0` tolerance the rest of `dashboard` uses for a DB from before this table existed, if that's the established pattern there (confirm).

### Step 2 — test

`dashboard()` includes `"phasen_debriefs"` with the correct count for a seeded group; `0` for a group with none; doesn't crash against a DB missing the table (if that fallback is in scope for this function — confirm against how other counts in the same function handle a missing table, since the whole DB is normally migrated together so this may not be reachable in practice; don't over-engineer if the rest of `dashboard` doesn't bother).

### Step 3 — commit.

---

## Task 7 (Part 2a): `kontext._baue_journal` — budget, system-note filtering, rejections sub-block

**Depends on:** none of the above (independent of Tasks 1-6; touches a different function). Can run any time, but is sequenced last among the "core kontext" work to keep `kontext.py` diffs reviewable one at a time.

**Files:**
- Modify: `interview_theater/kontext.py` (`_baue_journal`, `BUDGETS`)
- Test: `tests/test_kontext.py`
- Report: must document the full `quelle=` investigation (see Step 1) in the shared task report file — this becomes part of the final `.phasen-debrief-report.md` too.

### Step 0 — read this measurement from the brief before starting

On the only real group (`betrieb/soap.db`, chat `-5143986099`, 339 messages): conversation prompt (`aufruf.art='gespraech'`, 85 calls) median 9.5k tokens, max 16k, `ZIEL` 20k. The whole journal: 69 entries, 8237 chars (~2.7k tokens), avg 113 chars/entry, 20 `vorgeschlagen`, 0 `verworfen`. The last 8 entries were ALL scene-pipeline system notes (`quelle` `'szene'`/`'skript'`), pushing every group proposal/decision entirely out of the then-8-entry window.

### Step 1 — investigate every `schreibe_journal` caller, list `quelle` values, classify

Grep the **whole repo** for every call to `repo.schreibe_journal(` (not just the ones already found during planning — re-verify, since some call sites may pass `quelle` via a module-level constant like `web_schreiben.QUELLE`/`laengen.JOURNAL_QUELLE` rather than a literal string). For each distinct `quelle` value, read a few of the actual `text=` values passed at its call sites and decide:
- **Pure bookkeeping** (hide from the conversation journal block — the Arbeitsstand already shows the same fact): e.g. progress notes like `"Szene 2 geschrieben"`, `"Szenenfolge: 3 Abschnitte"`.
- **Carries a group decision that lives nowhere else** (keep visible even if the `quelle` is otherwise bookkeeping-flavoured): the brief's own example is `"Szene 2: auf Wunsch der Gruppe stark verdichtet"` — a `laengen`/`szene`-sourced note that records a *group wish*, not just a progress report.

Do this classification **per call site / per text-pattern**, not blindly per `quelle` string, if a single `quelle` mixes both kinds (the brief explicitly warns against assuming a whole `quelle` is safe to hide). Write the findings as a short table in the report: `quelle` → example text → hide/keep → why.

Implement the filter as a predicate function, e.g. `_ist_systemnotiz(eintrag) -> bool`, consulted inside `_baue_journal` before an entry enters the budgeted/visible set — but entries it excludes must still be readable from `repo.journal(conn, chat_id)` directly (the DB row is untouched; only the conversation-prompt rendering hides it).

### Step 2 — budget instead of count

In `BUDGETS`, raise `"journal"` from `1500` to `3000` (tokens; ≈9000 chars at `_ZEICHEN_JE_TOKEN=3` — the brief's own math, confirm the constant's actual value in this codebase rather than assuming 3, since Task 4 also depends on it).

Rewrite `_baue_journal` (`kontext.py:1008-1033`) so that, after the existing dedupe-by-`(art, text)`-keep-newest step:
1. Entries classified as system notes (Step 1) are removed from the candidate list for the **general** (budgeted) listing.
2. `'verworfen'` entries are pulled out into their own list and are **never** subject to the character budget or the count cap — ALL of them render, always, in their own small sub-block (see Step 3).
3. The remaining (non-`verworfen`, non-system-note) entries are kept **newest-first** until the running character total would exceed `BUDGETS["journal"] * _ZEICHEN_JE_TOKEN`, with a hard safety cap of **80** entries regardless of the char budget (so a budget mis-set to something huge can't pull in an unbounded number of iterations/text). Then restore chronological order for display (whatever the existing display order convention is — check, don't assume).

### Step 3 — rejections sub-block

Render `verworfen` entries as a clearly separate sub-section within the journal block, e.g.:
```
Abgelehnt (gilt weiterhin):
- {text}
- {text}
```
placed consistently relative to the rest of the journal block (implementer's call on exact position — above or below the general entries — but it must be visually/structurally separated, not interleaved).

### Step 4 — tests

- Budget trims **oldest first**: seed enough journal entries to exceed `BUDGETS["journal"]`, assert the oldest non-verworfen, non-system-note entries are the ones missing from the built block, newest survive.
- System notes absent from the conversation block but present via `repo.journal(conn, chat_id)` directly: seed a `quelle='szene'` pure-bookkeeping entry, assert it's in the DB read but not in `_baue_journal`'s output.
- A `quelle`/text identified in Step 1 as "carries a group decision" is **not** hidden, even though its `quelle` is otherwise filtered.
- `verworfen` entries survive even when far more than 80 other entries exist (budget/count cap must not touch them): seed 100 non-verworfen entries plus a handful of `verworfen` ones, assert all `verworfen` entries are present in the output.
- `tests/test_prompt_audit.py`/`tests/test_profil_bitgleich.py`: rerun after this change (journal formatting changed) and update the committed snapshot if an existing section's hash legitimately changes because of this edit — this IS a case needing justification (an **existing** prompt's assembled text changed shape), not a "new section" case like Task 2. Document why in the commit message and in the report.

### Step 5 — re-measurement against the real group

```
mkdir -p "$TMPDIR"
sqlite3 /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/soap.db \
  "VACUUM INTO '$TMPDIR/soap-messkopie.db'"
```
(If `betrieb/soap.db` is not reachable from this environment, say so plainly in the report and skip this step rather than fabricating numbers — do not read or write the live file under any circumstance.)

Using the copy, build `kontext.baue(...)`'s conversation prompt for chat `-5143986099` at `HEAD~N` (before this task's commit, e.g. via `git stash`/a throwaway checkout of `kontext.py` — or simpler: capture the char count by running the OLD `_baue_journal` logic against the copy before editing, then the NEW logic after) and record both character counts in the report, plus a one-line sanity check that the new total stays comfortably under the ~19k-token `ZIEL` ceiling mentioned in the brief.

### Step 6 — run targeted tests + `tests/test_profil_bitgleich.py tests/test_prompt_audit.py`, commit.

---

## Task 8 (Part 2b): Open proposals into scene writing

**Depends on:** Task 7 (shares `kontext.py`'s journal-reading/classification logic — specifically needs "open vs. settled" `vorgeschlagen` entries, which Task 7's investigation will have already characterized).

**Files:**
- Modify: `interview_theater/kontext.py` (new function)
- Modify: `interview_theater/szene.py`, `interview_theater/szenenfolge.py` — **not** `kurzgeschichte.py` (the brief names only "szene / szenenfolge" for this block, unlike Task 4's debrief block which goes everywhere scenes are written — follow the brief literally here)
- Test: `tests/test_kontext.py`, scene/szenenfolge prompt tests

### Step 1 — find (or confirm absence of) an existing open-vs-settled marker

Search for any existing mechanism distinguishing a `'vorgeschlagen'` journal entry that was later acted on (decided/rejected) from one that's still open — e.g. a later `'entschieden'`/`'verworfen'` entry referencing the same text/topic, or a dedicated `art='offen'` value (the `schreibe_journal` docstring lists `vorgeschlagen|verworfen|entschieden|offen` as the known `art` values — check whether `'offen'` is actually used anywhere as a *distinct* art, or if it's aspirational/legacy). If nothing usable exists, implement the brief's explicit fallback: the newest 15 `'vorgeschlagen'` entries (deduped the same way `_baue_journal` already dedupes), with no settled/rejected filtering beyond that. State which path was taken in the report.

### Step 2 — the block function

```python
def offene_vorschlaege_block(conn, chat_id: int) -> str:
    vorschlaege = ...  # Step 1's result, newest first
    if not vorschlaege:
        return ""
    grenze = 1500  # eigenes, kleines Budget in Zeichen (siehe Brief)
    zeilen, laenge = [], 0
    for v in vorschlaege:
        zeile = f"- {v['text']}"
        if laenge + len(zeile) > grenze:
            break
        zeilen.append(zeile)
        laenge += len(zeile)
    if not zeilen:
        return ""
    return "Offen, nicht entschieden -- nur als Anregung:\n" + "\n".join(zeilen)
```
(1500 is a plain character budget per the brief's own wording — "own small budget (~1500 chars)" — unlike `BUDGETS["debrief"]`, do not run this one through the token→char multiplier; it's intentionally a simpler, standalone block not registered in the main `BUDGETS` dict or the `_kuerze_auf_budget` ladder, since the brief frames it as scene-writing-only context, not part of the conversation prompt's trim ladder.)

### Step 3 — wire into `szene.py` and `szenenfolge.py` only

- `szene.py`: add to the same `_bloecke()`/`_REIHENFOLGE` touched in Task 4, as a distinct key (e.g. `"offene_vorschlaege"`), positioned near `"debrief"` but clearly labelled as its own block (the label text itself is the distinguishing marker, per the prompt rule "Not as instructions" — i.e. phrase it as information, not a directive to the model).
- `szenenfolge.py`: same insertion point as Task 4's debrief block in both `baue_nutzertext_geschichte` and `baue_nutzertext`.
- Confirm `kurzgeschichte.py` is **untouched** by this task (Task 4 already added the debrief block there; this task does not touch that file at all).

### Step 4 — tests

- `kontext.offene_vorschlaege_block` returns the label + newest-15-or-fewer `vorgeschlagen` entries (or the open-vs-settled result if Step 1 found a real mechanism), respects the 1500-char budget, empty when there are none.
- `szene.baue_nutzertext` and both `szenenfolge.baue_nutzertext*` outputs contain the "Offen, nicht entschieden" block when open proposals exist; `kurzgeschichte.baue_nutzertext` output does **not** contain it (negative test, since Task 4 made that file debrief-aware but this task deliberately does not extend it further).

### Step 5 — run targeted tests, commit.

---

## Final Gate

After Task 8's review is clean:
1. Dispatch the final whole-branch code reviewer (most capable available model) against the full diff from this branch's merge-base with `main` (or `feat/modellwahl-phase`, whichever this branch actually started from — confirm with `git merge-base`).
2. Resolve Critical/Important findings with one consolidated fix dispatch (not per-finding).
3. Write/finalize `.phasen-debrief-report.md` at the repo root (worktree root) covering: what was built, what's untested (e.g. any `szene_claude`/Opus path not exercised against a real API), decisions made where the brief was ambiguous (budget units, quote-check line rule, EN sentinel word, which `quelle` values got hidden and why, dashboard inclusion, any call site that couldn't be wired with `klm`/`e`), and anything explicitly left open (e.g. "Opus call fails → fallback" only tested with a fake, never against the real Claude proxy).
4. Run the full suite in the foreground with the clean-env command from Global Constraints. Confirm green (or report exact failures).
5. Use `superpowers:finishing-a-development-branch` to decide merge/PR/cleanup with the human partner — do not push, do not open a PR, without being asked.
