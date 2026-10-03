# Padua Phasen TEIL 2: 6 Rewrite / 7 Stage Version / Prüfung vor Anzeige — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put a judge-driven check loop (≤ 2 rounds, abort on deterioration, quote guard, language pass) in front of every text the Padua group sees. Rebuild Padua's phase 6 (whole story first, then scene by scene) and phase 7 (forms by chat, character voices, scene-by-scene stage version, final play check) on top of it. Make chat feedback work wherever buttons work, by extending TEIL 1's phase→intent table. Show texts only in the Script tab. Dortmund must stay byte-identical.

**Architecture:** Three new modules, each with one job:
- `prueflauf.py` — the check-before-display. It runs fanout subsets through `schleife.schliesse` (extended so it can keep the better version), then the quote guard, then `nachpass`, and logs one row into a new table `prueflauf`.
- `ueberarbeitung.py` — the Padua state machine for phases 6 and 7 (which step is next, what approval does).
- `sprechweise.py` — derives a way of speaking for each character in one schema call.

Two existing writers (`szene.schreibe`, `kurzgeschichte.schreibe`) get a `zeigen` flag, so the check runs *before* anything is posted. `szene._lauf` and `kurzgeschichte.starte._lauf` delegate to `prueflauf` when its switch is on. That makes every text-producing path pass through the check: buttons, erkenner, Stage B and shortening.

Everything new is behind two profile switches that only Padua turns on (`[prueflauf] aktiv`, `[ueberarbeitung] aktiv`), the same pattern as TEIL 1's `[prosa_entwurf] aktiv`. The five new erkenner arts appear in the schema enum only when `[ueberarbeitung]` is on, and they are described only in the English erkenner prompt. So Dortmund's prompt bytes *and* its erkenner schema stay unchanged.

**Tech Stack:** Python 3.11, SQLite (additive schema via `db._migriere_fehlende_spalten`), pytest, TOML workshop profiles, the existing `fanout`/`schleife`/`bilanz`/`nachpass`/`sprachpass` machinery.

## Global Constraints

- Branch `padua-workshop/t_acfc5d3e-padua-phasen-teil-2-6-rewrite-7-stage-ve`. Never merge, never push, never touch `main`. Commit once per completed task.
- Python: `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3` (do not fix the broken `.venv`). Below, `$PY` means this interpreter.
- Full suite: `$PY -m pytest -q -p no:cacheprovider`. Run it in the foreground after every task. **Baseline measured 03.10.2026: `5969 passed, 4 skipped in 520.37s`.** A task is green when nothing that passed before fails. Ignore stray `ConnectionResetError` lines from local test HTTP servers.
- Dortmund must stay byte-identical. `tests/test_profil_bitgleich.py`, `tests/test_sprache_bitgleich.py` and `$PY -m scripts.pruefe_profil dortmund-2026` must stay green **without** regenerating any Dortmund/German snapshot. **Do not edit any German prompt file** under `interview_theater/prompts/**`, any file under `workshop/dortmund-2026/**`, or the value of any existing module constant. New constants are allowed, since snapshot tests accept new sections.
- All new runtime behaviour is gated by `workshop.prueflauf_aktiv()` and/or `workshop.ueberarbeitung_aktiv()`. Both are `False` except in `workshop/padua-2026/profil.toml`.
- Zusage 1: `callback_data` stays under 64 bytes (`k:<id>`, value in table `knopf`).
- Zusage 2: no model call inside a button handler. Anything that needs a model runs in a thread.
- Zusage 3: idempotent via `repo.beanspruche_knopf`, which is unchanged.
- SQL only in `repo.py` / `db.py`. The exception is `web_daten.py`, which reads only. Additive migrations only.
- `RUNDEN_MAX = 2` (Birk). A falling score aborts the loop, and the better earlier version stays.
- A version that loses a verified interview quote (`zitat.pruefe` via `sprachpass.verlorene`) is discarded.
- The judge is a different model from the writer, and the USA-consent rule stays (`fanout.waehle_richter`, unchanged).
- No full text in the chat for Padua. The chat gets a hint, a short summary, ≤ 3 lines on what the check changed, and buttons. Telegram gets a link instead of the text.
- No paid scripts (`scripts.pruefe_prompts`, `scripts.simulation`).
- Never commit `betrieb/*`, databases, or real interview material.
- If a genuine design question comes up that is not answered here or in the "Birk's decisions" section of the task card (money, deletion, privacy, architecture), stop and write it into the final report verbatim. Do not guess.

---

## Context the implementer needs (verified by reading the code, 03.10.2026)

**Writers post their own text.**
- `szene.schreibe(conn, tg, klm, e, chat_id, auftrag, art=ART, bei_teil=None) -> int` (`szene.py:2274`) saves, appends a `szenenfassung` row, writes the journal, and then at `:2413` calls `_sende_szenentext(...)`, which posts the full text plus the button bar (`knoepfe.biete_nach_szenentext`).
- `szene._lauf` (`:2448`) calls `schreibe`. If `art == ART`, it then calls `nachpass.nach_szene`, which calls `schreibe` again and so posts again.
- `kurzgeschichte.schreibe(conn, tg, klm, e, chat_id, regie=None, vorlage=False, ...)` (`kurzgeschichte.py:457`) calls `knoepfe.zeige_kurzgeschichte` at `:504`, which posts every section in full. Its thread (`starte._lauf`, `:528`) then runs `nachpass.nach_geschichte`.
- `kurzgeschichte.hole_text(...)` (`:425`) only calls the model and never posts.

**Prose vs stage text.** `szene.PHASE_PROSA = 6` and `szene.schreibt_prosa(conn, chat_id)` is `phase <= 6`. In phases 5 and 6, `szene.schreibe` writes `szene.prosa`; in phase 7 it writes `szene.volltext`, with the prose as the template. A revision order is `szene.T.TEXT_AUFTRAG_NEU.format(nummer=n, notiz=...)` (`"Schreib Szene {nummer} neu. {notiz}"`). In prose mode the notiz must end with `" " + szene.BISHER_MARKER` (`"[BISHER]"`), otherwise the model never sees the existing prose. See `kuerzung.py:184` and `nachpass.py:169` for the existing pattern.

**fanout** (`dramaturgie/fanout.py`):
- `pruefe(conn, e, klm, chat_id, richter=None, runde=None) -> Ergebnis` (`:1220`) always runs mechanics plus all seven questions: B1/A9/A10 per scene, A2/A11/A6 over the whole play, and C1 per scene with speakers. It persists findings and scores under `runde`.
- `Ergebnis(runde, befunde, bewertungen, aufrufe, richter)`.
- `auftraege(befunde, figuren=()) -> list[dict]` (`:1352`) returns keys `szene, pruefung, schwere, anweisung, befund_id`.
- `parameterkorrektur(...)` (`:757`) turns an A10 finding with `richtung=parameter` into `(feld, wert)`. **Read its exact signature before using it.**
- `waehle_richter(e, conn=None, chat_id=None) -> Richter` raises `RichterFehler` (same model as the writer, or a Claude judge without USA consent).
- `material_szene` reads `volltext` first, then `prosa`.
- `A10_FORM_AB_PHASE = 7`, so A10 includes the form check only in phase 7. That is how "Formregeln" are checked per stage scene.
- Fake judge for tests: `tests/test_dramaturgie_fanout.py:85` (`RichterAttrappe`) and `tests/test_dramaturgie_schleife.py:48` (`Rundenrichter(plan={(schluessel, szene): [score_r1, score_r2, ...]})`).

**schleife** (`dramaturgie/schleife.py`):
- `schliesse(conn, tg, klm, e, chat_id, *, richter=None, runden_max=RUNDEN_MAX, schreiber=None) -> Schleifenergebnis` (`:289`). It checks, takes orders, writes, re-checks, and compares with `bilanz.baue`. It stops on: no orders / `bilanz.geschadet` (Vorfall `dramaturgie_verschlechterung`) / round limit / missing write path.
- **On deterioration it restores nothing today.**
- The built-in writers `_schreibe_je_szene` and `_schreibe_die_geschichte` take their own locks and post the text. `prueflauf` therefore brings its own writers.
- `Runde(nummer, ergebnis, auftraege, ueberarbeitet, bilanz)`, `Schleifenergebnis(runden, grund, meldung)` with `.geschadet`.
- `repo.letzte_dramaturgie_runde` takes `MAX(runde)` from `dramaturgie_befund` **only**. A check run with scores but no findings would therefore reuse the same round number. Task 2 fixes this.

**nachpass**:
- `nach_szene(conn, tg, klm, e, chat_id, nummer) -> str | None` (`:123`) is gated by `laengen.aktiv()` (true in Padua). It calls `szene.schreibe` once, and restores the old row if a quote is lost.
- `nach_geschichte(conn, tg, klm, e, chat_id) -> str | None` (`:289`) uses `hole_text` plus `lege_szenen_an` and never posts.
- `sprachpass.gepruefte_zitate(conn, chat_id) -> list[str]` and `sprachpass.verlorene(alt, neu, zitate) -> list[str]`.

**Phase 5 (TEIL 1):**
- Stage A is confirmed by `knoepfe/wirkung.py:_wirkung_uebersicht_passt` (`:396`).
- Stage B writes through `szene.starte(... f"SZENE {n}: write this scene as prose, following the overview.")`.
- A scene is approved in `_wirkung_szene_passt` → `_wirkung_entwurf_szene_passt` (`:357`), which sets `szene.entwurf_bestaetigt_am`, moves to the next scene, and after the last one calls `phasen.setze(...,6,"entwurf")` plus `eintritt_in_phase(...,6)`.
- Tests are in `tests/test_entwurf_ablauf.py`, which has the FakeKLM / `TelegramAttrappe` / `_druck` / `_warte(lock)` pattern.

**Phase 6 today** (`knoepfe/stationen.py:349`):
- Entry sends the intro, then the USA question (`biete_szene_usa`) if due, else `biete_kurzgeschichte` ("Write the story" → `ART_GESCHICHTE_SCHREIBEN`).
- Story buttons: `ART_GESCHICHTE_PASST/ANDERS/KUERZEN/NEU`.
- `_wirkung_szene_usa` (`wirkung.py:1362`) offers `biete_kurzgeschichte` in phase 6 (`:1394`).
- There is no Padua branch.

**Phase 7 today** (`stationen.py:324`):
- Entry sends the intro, `biete_durchlauf`, and **starts `stueckpruefung` automatically** (`stationen.py:332`).
- The scene buttons from `biete_nach_szenentext` are `ART_SZENE_PASST` ("Looks good"), `ART_SZENE_ANDERS` (EN "No, change it again", which waits for the next chat message as a stage note via `szenenfolge.erwarte_regienotiz`, consumed in `ablauf.py:1116`), `ART_SZENE_KUERZEN`, `ART_SZENE_NEU` and `ART_SZENE_NAECHSTE`.

**Erkenner** (`erkenner.py`):
- The TEIL-1 table is `PHASEN_SPEZIFISCHE_ARTEN: dict[str, tuple[int, ...]] = {"uebersicht_aendern": (5,)}` (`:204`), consulted by `_ist_phasenpassend(conn, chat_id, art)` (`:213`).
- `wende_an` filters with it (`:1580`).
- `laufe` passes the **unfiltered** list to `_starte_szene` / `_starte_kuerzung` / `_starte_entwurf_uebersicht` (`:2515-2523`).
- `ARTEN` (`:65`) has 27 entries, and the schema enum is `list(ARTEN)` (`:261`).
- Arts with no write path return `None` from `_wende_eine_an`.
- `baue_meldung` builds "Notiert:" / "Noted:" only from writes that actually happened.
- The erkenner sees no phase. It sees "Arbeitsstand" plus the message window plus `vorlauf` (the last bot message).
- The English prompt `sprachen/en/prompts/erkenner.md` says "exactly twenty-six kinds", numbered 1–26, and that count is pinned by `tests/test_sprache_prompts.py:323` (`test_erkenner_en_zaehlt_seine_arten_richtig`).
- Corpus: `korpus/erkenner.jsonl` (DE, exact count pinned at 156/55 in `tests/test_korpus.py:727`) and `korpus/en/erkenner.jsonl` (78 cases, ids `en-…`). The case schema is: `id`, `notiz`, `arbeitsstand` (allowlisted keys, `tests/test_korpus.py:203`), `nachrichten` or `aufnahme`, `erwartet[{art,wert}]`, and optional `zustimmung`, `vorlauf`. There is **no phase field**. `OHNE_KORPUSFAELLE = {"geschichte_setzen"}` (`test_korpus.py:230`).
- No erkenner art writes `figur.sprachstil` (only `repo.setze_figur_sprachstil(conn, figur_id, stil)`, `repo.py:2319`, via a button). `szene_planen` redirects `form` into `form_vorschlag`.

**Flow-audit findings to resolve here** (`git show feat/flow-audit:docs/flow-audit/vorlagen.md`):
1. **B1:** in phase 5, agreeing to or changing a sharpening proposal by chat writes nothing. Only the `ART_SCHAERFUNG_*` buttons work.
2. **B2:** in phase 7, "make the mother angrier" triggers no revision, and once "Noted: …" appeared without anything being written.
3. **B3:** the phase-6 prompts (DE+EN) still say "write us scene 3" next to the one-story description.

Plan of record: B1 and B2 are fixed for Padua through new arts. B3 is fixed in the English prompt. The **German** B3 wording stays open (Dortmund byte-identity), and that goes in the final report.

**"hook".** It occurs in rule 4 of **both** `prompts/phasen/7.md` (DE, `:77`) and `sprachen/en/prompts/phasen/7.md` (EN, `:77`). It also occurs in `formen/rap.md` and `formen/chor.md` (DE and EN). It does **not** occur in `lied.md` in either language. Plan of record:
- remove it from EN `phasen/7.md`;
- add it to EN `formen/lied.md` so the acceptance test "rap/chor/lied contain hook" holds;
- leave the German files alone, because the Dortmund snapshot hashes them. Report that.

**Web.**
- `web_vereint.TABS = ("chat","stand","textbuch")`. The Textbuch tab is labelled "Script" in EN. Its body is `web.textbuch_koerper(daten, token, praefix)` (`web.py:3051`), with each scene rendered by `_probe_szene_html` (`:2816`). Prose is shown under "Als Geschichte:" only when `volltext` is empty.
- `daten` comes from `web_daten.gruppe_nach_token` (it includes `fassungen` from `web_daten.szenenfassungen`).
- The standalone `/g/<token>/textbuch` page uses the same `textbuch_koerper`.
- CSP: no `style="` and no `onclick=` anywhere (AGENTS.md "Die Absicherung").
- Channel check: `aufnahme.ist_web_gruppe(conn, chat_id)`. Group page URL: `repo.gruppenseite_url(conn, chat_id, basis)` with `basis = e.web_url`.
- `knoepfe/szenen.py:459 probenansicht_zeile(conn, e, chat_id) -> str` is the existing textbook-link line.

**Simulation.**
- `simulation/skript.py:SCHRITTE_TAG2` steps are `Schritt(name, titel, auftrag, fertig, art=..., max_nachrichten=...)`, where `fertig(conn, chat_id, merker) -> bool`.
- The CLI is `scripts/simulation.py --skript {auto,schritte,tag2,birk}`. The profile comes only from the environment (`IT_WORKSHOP`).
- Coverage claims are checked by `scripts/simulation_abdeckung.py` / `tests/test_simulation_abdeckung.py`.

---

## File structure

| File | New/Mod | Responsibility |
|---|---|---|
| `interview_theater/workshop.py` | Mod | `prueflauf_aktiv()`, `ueberarbeitung_aktiv()` |
| `workshop/padua-2026/profil.toml` | Mod | `[prueflauf] aktiv = true`, `[ueberarbeitung] aktiv = true` |
| `interview_theater/db.py` | Mod | columns `szene.erstentwurf_fassung`, `szene.ueberarbeitung_bestaetigt_am`, `arbeitsstand.gesamttext_fixiert_am`, `arbeitsstand.sprechweisen_fixiert_am`; table `prueflauf` |
| `interview_theater/repo.py` | Mod | readers/writers for the above; `letzte_dramaturgie_runde` over both tables |
| `interview_theater/dramaturgie/fanout.py` | Mod | `pruefe(..., fragen=None, szenen=None, mechanik=True)` |
| `interview_theater/sprachen/en/prompts/dramaturgie/a9_fokus.md` | Mod | spell out the A9 non-findings, bump `prompt_version` |
| `interview_theater/dramaturgie/schleife.py` | Mod | pass-through of `fragen/szenen/mechanik`; `behalte_bessere` restore |
| `interview_theater/szene.py` | Mod | `schreibe(..., zeigen=True)`; `ueberarbeitungsauftrag()`; `_lauf` delegates to `prueflauf` |
| `interview_theater/kurzgeschichte.py` | Mod | `schreibe(..., zeigen=True)`; `_lauf` delegates to `prueflauf` |
| `interview_theater/nachpass.py` | Mod | `nach_szene(..., zeigen=True)` |
| `interview_theater/prueflauf.py` | **New** | check-before-display: subsets, loop, quote guard, nachpass, log row, display |
| `interview_theater/ueberarbeitung.py` | **New** | Padua phase 6/7 state machine |
| `interview_theater/sprechweise.py` | **New** | one schema call: a way of speaking for each character without one |
| `interview_theater/knoepfe/texte.py`, `szenen.py`, `wirkung.py`, `stationen.py`, `__init__.py` | Mod | Script-tab hint, new ARTs (`ART_ERSTENTWURF`, `ART_SPRECHWEISEN_PASST`, `ART_SPRECHWEISEN_ANDERS`), Padua branches |
| `interview_theater/erkenner.py` | Mod | five new arts, gating by profile switch, `laufe` side effects |
| `interview_theater/ablauf.py` | Mod | discard an invented "Noted" answer in Padua phases 6/7 |
| `interview_theater/sprachen/en/prompts/erkenner.md`, `phasen/6.md`, `phasen/7.md`, `formen/lied.md` | Mod | EN only |
| `interview_theater/sprachen/en/texte.toml` | Mod | EN for all new constants |
| `workshop/padua-2026/phasentexte.toml` | Mod | entry moderation for phases 6 and 7 |
| `korpus/en/erkenner.jsonl` | Mod | cases for the five arts |
| `interview_theater/web.py`, `web_daten.py` | Mod | Script tab: first draft, earlier versions |
| `simulation/skript.py`, `scripts/simulation.py`, `simulation/README.md` | Mod | `--skript padua` |
| `AGENTS.md`, `README.md` | Mod | docs |
| tests | New/Mod | per task |

---

## Task 1: Profile switches `[prueflauf]` and `[ueberarbeitung]`

**Files:**
- Modify: `interview_theater/workshop.py` (after `prosa_entwurf_aktiv`, `:928`)
- Modify: `workshop/padua-2026/profil.toml` (after `[prosa_entwurf]`)
- Test: `tests/test_workshop.py`

**Interfaces:**
- Produces: `workshop.prueflauf_aktiv(profil=None) -> bool`, `workshop.ueberarbeitung_aktiv(profil=None) -> bool`

- [ ] **Step 1: Write the failing test** (append to `tests/test_workshop.py`, next to `test_prosa_entwurf_aktiv_nur_in_padua`)

```python
def test_prueflauf_und_ueberarbeitung_nur_in_padua():
    """Padua Phasen TEIL 2: beide Schalter wie [prosa_entwurf] -- aus in der
    Vorgabe und in Dortmund, an nur in Padua."""
    for schalter in (workshop.prueflauf_aktiv, workshop.ueberarbeitung_aktiv):
        assert schalter(None) is False
        assert schalter(workshop.lade("dortmund-2026")) is False
        assert schalter(workshop.lade("padua-2026")) is True
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_workshop.py -k prueflauf_und_ueberarbeitung`
Expected: FAIL with `AttributeError: module 'interview_theater.workshop' has no attribute 'prueflauf_aktiv'`

- [ ] **Step 3: Implement.** In `workshop.py` directly after `prosa_entwurf_aktiv`:

```python
def prueflauf_aktiv(profil: Profil | None = None) -> bool:
    """Der Pruefllauf vor jeder Anzeige eines Textes (Padua Phasen TEIL 2,
    03.10.2026): Richterfragen -> Ueberarbeitung -> neu bewerten, hoechstens
    ``schleife.RUNDEN_MAX`` Runden, danach Sprachpass/Nachpass. Ohne den
    Schalter laeuft jeder Szenen- und Prosalauf wie vorher."""
    profil = profil or aktiv()
    return bool(profil.wert("prueflauf.aktiv", False))


def ueberarbeitung_aktiv(profil: Profil | None = None) -> bool:
    """Die Padua-Fassung der Phasen 6 (Rewrite) und 7 (Stage Version):
    erst das Ganze, dann Szene fuer Szene; Formwahl und Sprechweisen per
    Chat; Lesen im Script-Tab statt im Chat; die Chat-Arten dazu
    (erkenner.PROFILSCHALTER_DER_ARTEN). Ohne den Schalter bleiben 6 und 7
    wie vorher."""
    profil = profil or aktiv()
    return bool(profil.wert("ueberarbeitung.aktiv", False))
```

In `workshop/padua-2026/profil.toml`, append after the `[prosa_entwurf]` block:

```toml
# Padua Phasen TEIL 2 (03.10.2026): vor jeder Anzeige eines Textes ein
# Prueflauf (Richterfragen, <= 2 Ueberarbeitungsrunden, Sprachpass/Nachpass).
[prueflauf]
aktiv = true

# Padua Phasen TEIL 2: Phase 6 erst das Ganze, dann Szene fuer Szene;
# Phase 7 Formwahl und Sprechweisen per Chat, Szene fuer Szene, am Ende die
# Stueckpruefung; Texte im Script-Tab statt im Chat.
[ueberarbeitung]
aktiv = true
```

- [ ] **Step 4: Run the test and the profile check**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_workshop.py tests/test_pruefe_profil.py tests/test_profile_geruest.py` → PASS
Run: `$PY -m scripts.pruefe_profil padua-2026` and `$PY -m scripts.pruefe_profil dortmund-2026` → both exit 0

- [ ] **Step 5: Full suite, then commit**

```bash
$PY -m pytest -q -p no:cacheprovider
git add interview_theater/workshop.py workshop/padua-2026/profil.toml tests/test_workshop.py
git commit -m "workshop: [prueflauf] and [ueberarbeitung] switches, on only for Padua"
```

---

## Task 2: Schema and repo — first draft, approvals, check-run log

**Files:**
- Modify: `interview_theater/db.py` (`SCHEMA`: `szene` block around `:504-578`, `arbeitsstand` block around `:422-441`, a new table after `dramaturgie_bewertung` around `:760`; `TABELLEN_MIT_CHAT_ID`)
- Modify: `interview_theater/repo.py`
- Test: `tests/test_prueflauf_repo.py` (new)

**Interfaces:**
- Produces:
  - `repo.setze_szene_erstentwurf(conn, szene_id: int, fassung_nummer: int) -> None`
  - `repo.erstentwurf_text(conn, szene_id: int) -> str | None`
  - `repo.letzte_szenenfassung(conn, szene_id: int) -> sqlite3.Row | None`
  - `repo.setze_szene_ueberarbeitung_bestaetigt(conn, szene_id: int, wann: str | None = None) -> None`
  - `repo.lege_prueflauf_an(conn, chat_id: int, *, phase: int, ziel: str, szene_nummer: int | None, fragen: str, runden: int, ueberarbeitungen: int, auftraege_je_runde: str, zweite_runde_mit_auftraegen: bool, grund: str, verworfen: str | None, dauer_ms: int) -> int`
  - `repo.prueflaeufe(conn, chat_id: int) -> list[sqlite3.Row]` (oldest first)
  - The arbeitsstand fields `gesamttext_fixiert_am` and `sprechweisen_fixiert_am`, settable through the existing `repo.setze_arbeitsstand`.
  - `repo.letzte_dramaturgie_runde` now returns the max over `dramaturgie_befund` **and** `dramaturgie_bewertung`.

- [ ] **Step 1: Write the failing tests** — `tests/test_prueflauf_repo.py`:

```python
"""Padua Phasen TEIL 2: Speicher fuer Erstfassung, Abnahmen und das
Protokoll jedes Prueflaufs."""

from interview_theater import db, repo


def _szene(conn, chat_id=1, nummer=1):
    return repo.stelle_szene_sicher(conn, chat_id, nummer)


def test_erstentwurf_zeigt_auf_eine_fassung(conn):
    sid = _szene(conn)
    repo.haenge_szenenfassung_an(conn, 1, sid, "Erste Fassung.")
    repo.haenge_szenenfassung_an(conn, 1, sid, "Zweite Fassung.")
    erste = repo.szenenfassungen(conn, sid)[0]
    repo.setze_szene_erstentwurf(conn, sid, erste["nummer"])
    assert repo.erstentwurf_text(conn, sid) == "Erste Fassung."
    assert repo.letzte_szenenfassung(conn, sid)["volltext"] == "Zweite Fassung."


def test_ohne_erstentwurf_kein_text(conn):
    sid = _szene(conn)
    assert repo.erstentwurf_text(conn, sid) is None
    assert repo.letzte_szenenfassung(conn, sid) is None


def test_ueberarbeitung_bestaetigt_und_arbeitsstandfelder(conn):
    sid = _szene(conn)
    repo.setze_szene_ueberarbeitung_bestaetigt(conn, sid)
    assert repo.hole_szene(conn, sid)["ueberarbeitung_bestaetigt_am"]
    repo.setze_arbeitsstand(conn, 1, "gesamttext_fixiert_am", "2026-10-03T10:00:00")
    repo.setze_arbeitsstand(conn, 1, "sprechweisen_fixiert_am", "2026-10-03T10:00:00")
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["gesamttext_fixiert_am"] and stand["sprechweisen_fixiert_am"]


def test_prueflauf_protokoll(conn):
    rid = repo.lege_prueflauf_an(
        conn, 1, phase=6, ziel="szene", szene_nummer=2, fragen="b1,a10",
        runden=2, ueberarbeitungen=1, auftraege_je_runde="2,0",
        zweite_runde_mit_auftraegen=False, grund="keine_auftraege",
        verworfen=None, dauer_ms=1234,
    )
    zeilen = repo.prueflaeufe(conn, 1)
    assert [z["id"] for z in zeilen] == [rid]
    assert zeilen[0]["zweite_runde_mit_auftraegen"] == 0
    assert zeilen[0]["auftraege_je_runde"] == "2,0"


def test_prueflauf_gehoert_zum_loeschweg():
    assert "prueflauf" in db.TABELLEN_MIT_CHAT_ID


def test_letzte_runde_zaehlt_auch_bewertungen(conn):
    repo.lege_dramaturgie_bewertungen_an(
        conn, 1, [{"pruefung": "b1", "szene": 1, "score": 2}], runde=4)
    assert repo.letzte_dramaturgie_runde(conn, 1) == 4
```

Before running, check `repo.lege_dramaturgie_bewertungen_an`'s exact signature (`repo.py:1349`) and adapt the call if its keyword or dict shape differs.

- [ ] **Step 2: Run it and confirm it fails**

Run: `$PY -m pytest -q -p no:cacheprovider tests/test_prueflauf_repo.py`
Expected: FAIL (`AttributeError: ... setze_szene_erstentwurf` etc.)

- [ ] **Step 3: Implement the schema.**
  - In `SCHEMA`'s `szene` block, after `entwurf_bestaetigt_am TEXT`, add:
    ```sql
        -- Padua Phasen TEIL 2: Nummer der szenenfassung VOR dem letzten
        -- Prueflauf ("Show first draft"); und die Abnahme in Phase 6.2.
        erstentwurf_fassung INTEGER,
        ueberarbeitung_bestaetigt_am TEXT,
    ```
  - In the `arbeitsstand` block, after `geschichte_uebersicht_fixiert_am TEXT`, add:
    ```sql
        -- Padua Phasen TEIL 2: Phase 6.1 (Gesamttext) und 7.2 (Sprechweisen) abgenommen.
        gesamttext_fixiert_am TEXT,
        sprechweisen_fixiert_am TEXT,
    ```
    Keep comma placement valid (look at the neighbouring lines).
  - Add a new table after `dramaturgie_bewertung` and its index:
    ```sql
    -- Padua Phasen TEIL 2 (03.10.2026): eine Zeile je Prueflauf vor einer
    -- Anzeige -- Rundenzahl, Dauer, ob die zweite Pruefung noch Auftraege
    -- hatte. Die Messgrundlage fuer RUNDEN_MAX = 2.
    CREATE TABLE IF NOT EXISTS prueflauf (
        id INTEGER PRIMARY KEY,
        chat_id INTEGER NOT NULL,
        phase INTEGER,
        ziel TEXT NOT NULL,              -- 'szene' | 'geschichte'
        szene_nummer INTEGER,
        fragen TEXT,
        runden INTEGER NOT NULL,         -- Zahl der Bewertungsrunden (fanout.pruefe)
        ueberarbeitungen INTEGER NOT NULL,
        auftraege_je_runde TEXT,         -- z. B. "3,1,0"
        zweite_runde_mit_auftraegen INTEGER NOT NULL DEFAULT 0,
        grund TEXT,
        verworfen TEXT,                  -- NULL | 'verschlechterung' | 'zitat'
        dauer_ms INTEGER,
        erstellt_am TEXT NOT NULL
    );
    ```
    The CREATE must end exactly with `\n);` so that `_tabellenspalten_aus_schema` parses it.
  - Add `"prueflauf"` to `db.TABELLEN_MIT_CHAT_ID`.

- [ ] **Step 4: Implement the repo functions.** Add the two arbeitsstand fields to `_ARBEITSSTAND_FELDER`, the same way commit e41927f did for `geschichte_uebersicht_fixiert_am`. Every function gets the `@_gesperrt` decorator, like its neighbours. Place them next to `haenge_szenenfassung_an` (`:2734`), `setze_szene_entwurf_bestaetigt` (`:2521`) and the dramaturgy block (`:1337`).

```python
@_gesperrt
def letzte_szenenfassung(conn, szene_id: int):
    return conn.execute(
        "SELECT * FROM szenenfassung WHERE szene_id = ? ORDER BY nummer DESC, id DESC LIMIT 1",
        (szene_id,),
    ).fetchone()


@_gesperrt
def setze_szene_erstentwurf(conn, szene_id: int, fassung_nummer: int) -> None:
    with conn:
        conn.execute(
            "UPDATE szene SET erstentwurf_fassung = ? WHERE id = ?",
            (int(fassung_nummer), szene_id),
        )


@_gesperrt
def erstentwurf_text(conn, szene_id: int) -> str | None:
    zeile = conn.execute(
        "SELECT f.volltext FROM szene s JOIN szenenfassung f"
        " ON f.szene_id = s.id AND f.nummer = s.erstentwurf_fassung"
        " WHERE s.id = ? ORDER BY f.id DESC LIMIT 1",
        (szene_id,),
    ).fetchone()
    return zeile["volltext"] if zeile else None


@_gesperrt
def setze_szene_ueberarbeitung_bestaetigt(conn, szene_id: int, wann: str | None = None) -> None:
    with conn:
        conn.execute(
            "UPDATE szene SET ueberarbeitung_bestaetigt_am = ? WHERE id = ?",
            (wann or _jetzt(), szene_id),
        )


@_gesperrt
def lege_prueflauf_an(conn, chat_id: int, *, phase: int, ziel: str,
                      szene_nummer: int | None, fragen: str, runden: int,
                      ueberarbeitungen: int, auftraege_je_runde: str,
                      zweite_runde_mit_auftraegen: bool, grund: str,
                      verworfen: str | None, dauer_ms: int) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO prueflauf (chat_id, phase, ziel, szene_nummer, fragen, runden,"
            " ueberarbeitungen, auftraege_je_runde, zweite_runde_mit_auftraegen, grund,"
            " verworfen, dauer_ms, erstellt_am) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (chat_id, phase, ziel, szene_nummer, fragen, runden, ueberarbeitungen,
             auftraege_je_runde, 1 if zweite_runde_mit_auftraegen else 0, grund,
             verworfen, dauer_ms, _jetzt()),
        )
    return cur.lastrowid


@_gesperrt
def prueflaeufe(conn, chat_id: int):
    return conn.execute(
        "SELECT * FROM prueflauf WHERE chat_id = ? ORDER BY id", (chat_id,)
    ).fetchall()
```

Match the existing transaction idiom in `repo.py`: look at how `setze_szene_entwurf_bestaetigt` commits and copy that instead of `with conn:` if it differs.

Replace the body of `letzte_dramaturgie_runde` with:

```python
    zeile = conn.execute(
        "SELECT MAX(r) AS r FROM ("
        " SELECT MAX(runde) AS r FROM dramaturgie_befund WHERE chat_id = ?"
        " UNION ALL SELECT MAX(runde) AS r FROM dramaturgie_bewertung WHERE chat_id = ?)",
        (chat_id, chat_id),
    ).fetchone()
    return int(zeile["r"] or 0)
```

Keep the function's existing filters: if the current query filters `entfernt_am IS NULL`, keep that on the befund side.

- [ ] **Step 5: Run the tests** — `$PY -m pytest -q -p no:cacheprovider tests/test_prueflauf_repo.py tests/test_db.py tests/test_dramaturgie_persistenz.py tests/test_ruecknahme*.py` → PASS. The undo tests (`test_ruecknahme_rundreise.py`) derive tracked columns from the schema. If one demands that a new column be listed in `ruecknahme.AUSSEN_VOR`, add it there with a one-line reason: it is written by the check run or a button, never by `wende_an`.

- [ ] **Step 6: Full suite, then commit**

```bash
git add interview_theater/db.py interview_theater/repo.py interview_theater/ruecknahme.py tests/test_prueflauf_repo.py
git commit -m "db/repo: first-draft pointer, phase 6/7 approvals, prueflauf log table"
```

---

## Task 3: `fanout.pruefe` can run a subset of questions and scenes; A9 non-findings in EN

**Files:**
- Modify: `interview_theater/dramaturgie/fanout.py` (`pruefe`, `:1220-1305`)
- Modify: `interview_theater/sprachen/en/prompts/dramaturgie/a9_fokus.md`
- Test: `tests/test_dramaturgie_fanout.py` (append)

**Interfaces:**
- Produces: `fanout.pruefe(conn, e, klm, chat_id, richter=None, runde=None, *, fragen: tuple[str, ...] | None = None, szenen: tuple[int, ...] | None = None, mechanik: bool = True) -> Ergebnis`
  - `fragen` holds keys from `fanout.PROMPTS` (`"b1","a2","a6","a9","a10","a11","c1"`); `None` means all.
  - `szenen` restricts the **per-scene** questions (B1, A9, A10, C1) to those scene numbers; `None` means all. Whole-play questions (A2, A6, A11) ignore it.
  - `mechanik=False` skips `mechanik.pruefe_alles`. The default keeps today's behaviour exactly.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_dramaturgie_fanout.py`, reusing its fixtures `stueck`, `einst` and `RichterAttrappe`/`_voller_richter`:

```python
def test_pruefe_nur_teilmenge_der_fragen_und_szenen(stueck, einst):
    richter = _voller_richter()
    fanout.pruefe(stueck, einst, None, 1, richter=richter,
                  fragen=("b1", "a10"), szenen=(2,), mechanik=False)
    arten = {art for art, _system, _nutzer in richter.gesehen}
    assert arten <= {fanout.ARTEN["b1"], fanout.ARTEN["a10"]}
    # B1 lief genau einmal: nur fuer Szene 2
    assert sum(1 for a, *_ in richter.gesehen if a == fanout.ARTEN["b1"]) == 1


def test_pruefe_ohne_mechanik_schreibt_keine_mechanikbefunde(stueck, einst):
    erg = fanout.pruefe(stueck, einst, None, 1, richter=_voller_richter(),
                        fragen=("a2",), mechanik=False)
    assert all(b.get("quelle") != "mechanik" for b in erg.befunde)


def test_pruefe_ohne_auswahl_wie_bisher(stueck, einst):
    richter = _voller_richter()
    fanout.pruefe(stueck, einst, None, 1, richter=richter)
    arten = {art for art, *_ in richter.gesehen}
    assert fanout.ARTEN["b1"] in arten and fanout.ARTEN["a2"] in arten
```

If `RichterAttrappe.gesehen` stores tuples in a different order, adjust the unpacking. Check whether the `stueck` fixture has a scene 2; if it has only one scene, use `szenen=(1,)`, and in the first test assert that B1 ran once for a two-scene fixture you build inline with `repo.stelle_szene_sicher` plus `repo.aktualisiere_szene`.

- [ ] **Step 2: Run the tests and confirm they fail** (TypeError: unexpected keyword `fragen`).

- [ ] **Step 3: Implement.** In `pruefe`, add the keyword-only parameters and a local helper:

```python
def pruefe(conn, e, klm, chat_id: int, richter: Richter | None = None,
           runde: int | None = None, *, fragen=None, szenen=None,
           mechanik: bool = True) -> Ergebnis:
    ...
    def _an(schluessel: str) -> bool:
        return fragen is None or schluessel in fragen

    def _szene_an(nummer) -> bool:
        return szenen is None or nummer in szenen
```

Wrap each existing step:
- the mechanics call: `if mechanik:`;
- the per-scene loop body for B1/A9/A10: `if not _szene_an(nummer): continue`, plus each question in `if _an("b1"):` and so on;
- A2/A11/A6: `if _an("a2"):` and so on;
- the C1 loop: `_an("c1") and _szene_an(nummer)`.

Do not reorder anything. With all three defaults, the call sequence must be identical to today's (`test_pruefe_ohne_auswahl_wie_bisher` plus the whole existing fanout suite prove it). Document the three parameters in the docstring: Padua Phasen TEIL 2, used by `prueflauf`.

- [ ] **Step 4: Update the EN A9 prompt.** Open `sprachen/en/prompts/dramaturgie/a9_fokus.md`. Bump line 1 to `prompt_version: a9-2026-10-03-1-en`. In the section that defines what counts as a finding, add this paragraph (keep the file's tone):

```markdown
Not a finding (Birk, 03.10.2026): introducing a character, a side thread
that the play picks up again later, and a poetic description of the
setting. Only a passage that pulls the scene away from its main conflict
and never returns to it counts.
```

Read the file first and put this where the existing criteria are listed. If the file already says this in other words, only bump the version and note it in the commit message. The German file stays untouched.

- [ ] **Step 5: Run the tests.** `$PY -m pytest -q -p no:cacheprovider tests/test_dramaturgie_fanout.py tests/test_dramaturgie_schleife.py tests/test_dramaturgie_persistenz.py tests/test_sprache_prompts.py` → PASS. If a test pins EN dramaturgy prompt versions, update that pin.

- [ ] **Step 6: Full suite, then commit**

```bash
git commit -am "fanout: run a subset of questions/scenes, mechanics optional; EN A9 names its non-findings"
```

---

## Task 4: `schleife.schliesse` passes the subset through and keeps the better version

**Files:**
- Modify: `interview_theater/dramaturgie/schleife.py`
- Test: `tests/test_dramaturgie_schleife.py` (append)

**Interfaces:**
- Consumes: `fanout.pruefe(..., fragen, szenen, mechanik)` (Task 3)
- Produces:
  - `schleife.schliesse(conn, tg, klm, e, chat_id, *, richter=None, runden_max=RUNDEN_MAX, schreiber=None, fragen=None, szenen=None, mechanik=True, behalte_bessere=False) -> Schleifenergebnis`
  - `Schleifenergebnis.wiederhergestellt: bool` (default `False`)
  - With `behalte_bessere=True`: before each `schreiber(...)` call, snapshot every scene row of the group. If the re-check then shows `bilanz.geschadet`, restore every scene whose text changed during that rewrite (`repo.aktualisiere_szene(conn, id, titel, kurzbeschreibung, volltext, zusammenfassung, prosa=prosa)`), set `wiederhergestellt = True`, and keep the existing Vorfall.

- [ ] **Step 1: Write the failing test** ("abort on deterioration keeps the better version"). Append to `tests/test_dramaturgie_schleife.py`, using its `Rundenrichter`, `Schreibattrappe`, `stueck`, `einst` and `tg`:

```python
def test_verschlechterung_in_runde_zwei_behaelt_die_bessere_fassung(stueck, einst, tg):
    """Birk 03.10.2026: Abbruch, wenn eine Bewertung faellt -- dann bleibt
    die bessere (fruehere) Fassung stehen, nicht die schlechtere."""
    vorher = repo.hole_szenen(stueck, 1)
    text_r1 = {s["nummer"]: s["volltext"] for s in vorher}
    # B1 Szene 1: Runde 1 Score 1 (Befund -> Auftrag), nach der
    # Ueberarbeitung Score 0 -> geschadet.
    richter = Rundenrichter(plan={("b1", 1): [0, 0]}, ...)
    ...
```

Build the plan from the fixture's real conventions. Read `Rundenrichter` (`:48`) and the existing deterioration test in this file (search for `geschadet`) and copy its setup. The assertion part is fixed:

```python
    ergebnis = schleife.schliesse(
        stueck, tg, None, einst, 1, richter=richter,
        schreiber=Schreibattrappe(stueck), behalte_bessere=True)
    assert ergebnis.grund == schleife.GRUND_GESCHADET
    assert ergebnis.wiederhergestellt is True
    nachher = {s["nummer"]: s["volltext"] for s in repo.hole_szenen(stueck, 1)}
    assert nachher == text_r1          # die bessere, fruehere Fassung steht wieder
    assert "UEBERARBEITET" not in "".join(nachher.values())


def test_ohne_behalte_bessere_bleibt_es_wie_bisher(stueck, einst, tg):
    # same setup, behalte_bessere omitted -> worse text stays, wiederhergestellt False
    ...
    assert ergebnis.wiederhergestellt is False
    assert "UEBERARBEITET" in "".join(
        s["volltext"] or "" for s in repo.hole_szenen(stueck, 1))
```

Write the `...` setup lines by copying the existing deterioration test. The judge must give scene 1's B1 a score that produces an order in round 1 and a lower score in round 2. Use the scores that test uses.

Also add a pass-through test:

```python
def test_teilmenge_geht_an_fanout_durch(stueck, einst, tg, monkeypatch):
    gesehen = {}
    echt = fanout.pruefe
    def spion(*a, **k):
        gesehen.update(k)
        return echt(*a, **k)
    monkeypatch.setattr(fanout, "pruefe", spion)
    schleife.schliesse(stueck, tg, None, einst, 1, richter=Rundenrichter(plan={}),
                       schreiber=Schreibattrappe(stueck), fragen=("b1",),
                       szenen=(1,), mechanik=False)
    assert gesehen["fragen"] == ("b1",) and gesehen["szenen"] == (1,)
    assert gesehen["mechanik"] is False
```

- [ ] **Step 2: Run the tests and confirm they fail.**

- [ ] **Step 3: Implement.**
  - Add `wiederhergestellt: bool = False` to the `Schleifenergebnis` dataclass.
  - In `schliesse`, add the four keyword parameters and pass `fragen=fragen, szenen=szenen, mechanik=mechanik` to **both** `fanout.pruefe` calls.
  - Around the writer call:

```python
        stand = _schnappschuss(conn, chat_id) if behalte_bessere else None
        aktuell.ueberarbeitet = schreiber(conn, tg, klm, e, chat_id, aktuell.auftraege)
        ...
        if vergleich.geschadet:
            _merke_schaden(...)
            if stand is not None:
                ergebnis.wiederhergestellt = _stelle_wieder_her(conn, chat_id, stand)
            ergebnis.grund = GRUND_GESCHADET
            break
```

  - Add the helpers:

```python
_TEXTFELDER = ("titel", "kurzbeschreibung", "volltext", "zusammenfassung", "prosa")


def _schnappschuss(conn, chat_id: int) -> dict[int, dict]:
    """Die Szenen vor einer Ueberarbeitung -- fuer ``behalte_bessere``."""
    return {s["id"]: {f: s[f] for f in _TEXTFELDER} for s in repo.hole_szenen(conn, chat_id)}


def _stelle_wieder_her(conn, chat_id: int, stand: dict[int, dict]) -> bool:
    """Schreibt jede Szene zurueck, deren Text sich seit dem Schnappschuss
    geaendert hat. Die Fassungszeilen der verworfenen Runde bleiben in
    ``szenenfassung`` stehen (nur anhaengen, nie loeschen)."""
    geaendert = False
    for s in repo.hole_szenen(conn, chat_id):
        alt = stand.get(s["id"])
        if alt is None or all(s[f] == alt[f] for f in _TEXTFELDER):
            continue
        repo.aktualisiere_szene(conn, s["id"], alt["titel"], alt["kurzbeschreibung"],
                                alt["volltext"], alt["zusammenfassung"], prosa=alt["prosa"])
        geaendert = True
    return geaendert
```

Note that `aktualisiere_szene` only writes `volltext`/`prosa` when not `None`. If the old value was `None` and the new one is set, the restore cannot null it. That case does not occur: a revision never creates a stage text in prose phases. Say so in a comment.

- [ ] **Step 4: Run the tests** — `tests/test_dramaturgie_schleife.py` and `tests/test_dramaturgie_bilanz.py` → PASS.

- [ ] **Step 5: Full suite, then commit**

```bash
git commit -am "schleife: subset pass-through; behalte_bessere restores the better version on deterioration"
```

---

## Task 5: Writers can stay silent: `zeigen` flags and `szene.ueberarbeitungsauftrag`

**Files:**
- Modify: `interview_theater/szene.py` (`schreibe`, `:2274-2414`; new helper next to `TEXT_AUFTRAG_NEU`, `:1671`)
- Modify: `interview_theater/kurzgeschichte.py` (`schreibe`, `:457-505`)
- Modify: `interview_theater/nachpass.py` (`nach_szene`, `:123`)
- Test: `tests/test_zeigen_schalter.py` (new)

**Interfaces:**
- Produces:
  - `szene.schreibe(conn, tg, klm, e, chat_id, auftrag, art=ART, bei_teil=None, zeigen=True) -> int`. With `zeigen=False`, everything happens except `_sende_szenentext`.
  - `kurzgeschichte.schreibe(..., zeigen=True)`. With `zeigen=False` it skips `_TEXT_FERTIG` and `knoepfe.zeige_kurzgeschichte`. Read the function: skip **every** `tg.sende*` that carries text, but keep journal and storage.
  - `nachpass.nach_szene(conn, tg, klm, e, chat_id, nummer, zeigen=True)` passes `zeigen` through to its `szene.schreibe` call.
  - `szene.ueberarbeitungsauftrag(conn, chat_id: int, nummer: int, notiz: str) -> str` returns `T.TEXT_AUFTRAG_NEU.format(nummer=nummer, notiz=notiz + (" " + BISHER_MARKER if schreibt_prosa(conn, chat_id) else ""))`.

- [ ] **Step 1: Write the failing tests** — `tests/test_zeigen_schalter.py`:

```python
"""Padua Phasen TEIL 2: ein Lauf kann schreiben, ohne zu zeigen -- der
Prueflauf zeigt erst die gepruefte Fassung."""

from test_knoepfe import TelegramAttrappe

from interview_theater import kurzgeschichte, phasen, repo, szene


class ProsaKLM:
    def __init__(self, text):
        self.text = text
        self.aufrufe = 0

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None, bei_teil=None):
        self.aufrufe += 1
        return self.text


def _vorbereiten(conn):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Flur.")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei Freunde.")
    repo.setze_figur(conn, 1, "Alex", "leise")
    sid = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, sid, "was_passiert", "Alex packt.")
    repo.setze_szenenfeld(conn, sid, "ort", "Flur")
    repo.setze_szene_figuren(conn, 1, sid, [f["id"] for f in repo.figuren(conn, 1)])
    phasen.setze(conn, 1, 6, "befehl")
    return sid


def test_schreibe_ohne_zeigen_speichert_aber_sendet_nichts(conn, einst):
    sid = _vorbereiten(conn)
    tg = TelegramAttrappe()
    szene.schreibe(conn, tg, ProsaKLM("TITEL: Eins\n\nPROSA-KOERPER-XYZ"), einst, 1,
                   "SZENE 1: schreib", zeigen=False)
    assert "PROSA-KOERPER-XYZ" in (repo.hole_szene(conn, sid)["prosa"] or "")
    assert not any("PROSA-KOERPER-XYZ" in t for _c, t, *_ in tg.gesendet)


def test_ueberarbeitungsauftrag_haengt_im_prosalauf_bisher_an(conn):
    _vorbereiten(conn)  # Phase 6 -> Prosa
    auftrag = szene.ueberarbeitungsauftrag(conn, 1, 1, "wuetender")
    assert szene.BISHER_MARKER in auftrag and "wuetender" in auftrag
    phasen.setze(conn, 1, 7, "befehl")
    assert szene.BISHER_MARKER not in szene.ueberarbeitungsauftrag(conn, 1, 1, "x")
```

Check `TelegramAttrappe.gesendet`'s tuple layout in `tests/test_knoepfe.py:20-69` and `sende_mit_knoepfen`'s record (`.knoepfe`). Assert on **both** lists. Look at how existing szene tests answer the model (the `TITEL:` / `Zusammenfassung:` / `Anders gemacht:` lines that `schreibe` parses) and copy that answer format so `schreibe` does not reject it. Add a `kurzgeschichte.schreibe(..., zeigen=False)` test the same way, using the answer format from `tests/test_teil4_kurzgeschichte.py`.

- [ ] **Step 2: Run the tests and confirm they fail.**

- [ ] **Step 3: Implement.**
  - In `szene.schreibe`, add `zeigen: bool = True` and wrap the final call: `if zeigen: _sende_szenentext(...)`. Document it in the docstring.
  - In `kurzgeschichte.schreibe`, do the same for every text post.
  - In `nachpass.nach_szene`, add `zeigen: bool = True` and pass it to `szene_modul.schreibe(..., zeigen=zeigen)`.
  - Add `ueberarbeitungsauftrag` directly below `TEXT_AUFTRAG_NEU`, with a docstring pointing at `kuerzung.py:184`.

- [ ] **Step 4: Run the tests** — new file plus `tests/test_szene*.py tests/test_nachpass*.py tests/test_teil4_kurzgeschichte.py tests/test_kuerzung.py` → PASS.

- [ ] **Step 5: Full suite, then commit**

```bash
git commit -am "szene/kurzgeschichte/nachpass: write without showing (zeigen=False); ueberarbeitungsauftrag helper"
```

---

## Task 6: `prueflauf.py` — the check before every display

**Files:**
- Create: `interview_theater/prueflauf.py`
- Modify: `interview_theater/sprachen/en/texte.toml` (new section `["prueflauf"]`; check how other modules' sections are keyed and follow that)
- Test: `tests/test_prueflauf.py` (new)

**Interfaces:**
- Consumes:
  - `fanout.waehle_richter`, `fanout.RichterFehler`, `fanout.parameterkorrektur`
  - `schleife.schliesse(..., fragen, szenen, mechanik=False, behalte_bessere=True, schreiber=...)`
  - `szene.schreibe(..., zeigen=False)`, `szene.ueberarbeitungsauftrag`, `szene.sperrtext`, `szene.schreibt_prosa`
  - `kurzgeschichte.schreibe(..., zeigen=False)`
  - `nachpass.nach_szene(..., zeigen=False)`, `nachpass.nach_geschichte`
  - `sprachpass.gepruefte_zitate`, `sprachpass.verlorene`
  - the repo functions from Task 2
- Produces:
  - `prueflauf.aktiv() -> bool` (= `workshop.prueflauf_aktiv()`)
  - `FRAGEN_GESCHICHTE = ("a2", "a6", "a9", "a11")`, `FRAGEN_PROSASZENE = ("b1", "a10")`, `FRAGEN_BUEHNENSZENE = ("a10", "c1")`, `ART_UEBERARBEITUNG = "prueflauf_ueberarbeitung"`
  - `@dataclass Bericht(zeilen: list[str], runden: int, ueberarbeitungen: int, auftraege_je_runde: list[int], verworfen: str | None, grund: str, dauer_ms: int)`
  - `prueflauf.pruefe_szene(conn, tg, klm, e, chat_id, nummer) -> Bericht`. Synchronous; **the caller holds `szene._sperre_fuer(chat_id)`**. It checks the scene's *current* text, never posts, and returns the report.
  - `prueflauf.pruefe_geschichte(conn, tg, klm, e, chat_id, *, fragen=FRAGEN_GESCHICHTE) -> Bericht`. Synchronous; **the caller holds the matching lock**: the kurzgeschichte lock in prose phases, the szene lock in phase 7. It checks all scenes and never posts. In prose phases it runs `nachpass.nach_geschichte` at the end; in phase 7 there is no nachpass for the whole play (each scene already had one).
  - `prueflauf.starte_szene(conn, tg, klm, e, chat_id, nummer, danach) -> threading.Thread | None`. Takes the szene lock non-blocking (returns `None` if busy), runs `pruefe_szene`, then calls `danach(bericht)`.
  - `prueflauf.starte_geschichte(conn, tg, klm, e, chat_id, danach) -> threading.Thread | None`. Same, with the kurzgeschichte lock (prose) or the szene lock (phase 7).

Behaviour of `pruefe_szene` (write it exactly like this):

1. `t0 = time.monotonic()`.
2. Read the row (`repo.hole_szenen` filtered by `nummer`). The text field is `"prosa" if szene.schreibt_prosa(conn, chat_id) else "volltext"`. If the text is empty, return an empty `Bericht(grund="ohne_text")`.
3. **First draft:** let `letzte = repo.letzte_szenenfassung(conn, sid)`. If `letzte is None` or `letzte["volltext"] != text`, append the current text via `repo.haenge_szenenfassung_an(conn, chat_id, sid, text, zeile["zusammenfassung"], None)` and re-read `letzte`. Then `repo.setze_szene_erstentwurf(conn, sid, letzte["nummer"])`.
4. `zitate = sprachpass.gepruefte_zitate(conn, chat_id)`; `snapshot = schleife._schnappschuss(conn, chat_id)`. Make `_schnappschuss`/`_stelle_wieder_her` public in Task 4 if you prefer; then use `schleife.schnappschuss` here.
5. `fragen = FRAGEN_PROSASZENE if szene.schreibt_prosa(conn, chat_id) else FRAGEN_BUEHNENSZENE`.
6. In `try:`:
   - `richter = fanout.waehle_richter(e, conn, chat_id)`;
   - `erg = schleife.schliesse(conn, tg, klm, e, chat_id, richter=richter, fragen=fragen, szenen=(nummer,), mechanik=False, behalte_bessere=True, schreiber=_schreibe_szenen)`.
   - `except fanout.RichterFehler as f:` add `str(f)` as a report line, record Vorfall `prueflauf_ohne_richter`, and continue with `erg = None`.
   - `except kosten.KostendeckelErreicht:` call `kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id)` and continue with `erg = None`.
   - `except Exception:` call `log.exception`, record Vorfall `prueflauf_fehlgeschlagen`, and continue with `erg = None`. The group still sees its text.
7. **Parameter correction (A10, "in both directions"):** for each finding of the **last** round (`repo.dramaturgie_befunde(conn, chat_id, runde=erg.runden[-1].nummer)`) with `pruefung == "a10"` and `richtung == "parameter"` for this scene, call `fanout.parameterkorrektur(...)` (read its signature). If it returns `(feld, wert)` and `feld in repo.SZENENFELDER`, call `repo.setze_szenenfeld(conn, sid, feld, wert)`, write the journal entry `entschieden` (`quelle="prueflauf"`), and add the line `T._ZEILE_PARAMETER.format(nummer=nummer, feld=feld)`.
8. **Quote guard:** `neu = current text`. If `sprachpass.verlorene(text, neu, zitate)`, call `schleife._stelle_wieder_her(conn, chat_id, snapshot)`, set `verworfen = "zitat"`, and add `T._ZEILE_ZITAT_VERWORFEN`.
9. If `erg and erg.wiederhergestellt`, set `verworfen = "verschlechterung"` and add `T._ZEILE_VERSCHLECHTERT`.
10. Then `vor_nachpass = current text`; `nachpass.nach_szene(conn, tg, klm, e, chat_id, nummer, zeigen=False)` inside its own try/except (Vorfall `nachpass.VORFALL_FEHLER`, as in `szene._lauf`). If the text changed, add `T._ZEILE_SPRACHPASS`.
11. **Lines about what changed:** for each round with `ueberarbeitet`, and for each order of that round, add `T._ZEILE_AUFTRAG.format(pruefung=_name(a["pruefung"]), text=_kurz(a["anweisung"], 100))`. Keep the **first three** lines in total (`zeilen[:3]`). `_name(k)` reads `T._PRUEFUNG_NAMEN[k]`. `_kurz` cuts at the last space before 100 characters and appends "…".
12. Log: `repo.lege_prueflauf_an(conn, chat_id, phase=phasen.aktuelle(conn, chat_id), ziel="szene", szene_nummer=nummer, fragen=",".join(fragen), runden=len(erg.runden) if erg else 0, ueberarbeitungen=sum(1 for r in erg.runden if r.ueberarbeitet) if erg else 0, auftraege_je_runde=",".join(str(len(r.auftraege or [])) for r in erg.runden) if erg else "", zweite_runde_mit_auftraegen=bool(erg and len(erg.runden) > 1 and erg.runden[1].auftraege), grund=(erg.grund if erg else "ohne_pruefung"), verworfen=verworfen, dauer_ms=int((time.monotonic()-t0)*1000))`, plus `log.info` with the same numbers.

`_schreibe_szenen(conn, tg, klm, e, chat_id, auftraege) -> list[int]` (the writer for `schleife`, **no lock**):

```python
def _schreibe_szenen(conn, tg, klm, e, chat_id, auftraege):
    from interview_theater import szene
    je_szene: dict[int, list[str]] = {}
    for a in auftraege:
        if a.get("szene") is not None:
            je_szene.setdefault(int(a["szene"]), []).append(a["anweisung"])
    geschrieben = []
    for nummer, notizen in sorted(je_szene.items()):
        auftrag = szene.ueberarbeitungsauftrag(conn, chat_id, nummer, " ".join(notizen))
        ziel = szene.ziel_fuer(conn, chat_id, auftrag)
        if szene.sperrtext(conn, chat_id, ziel):  # read its signature, as schleife._schreibe_je_szene does
            continue
        szene.schreibe(conn, tg, klm, e, chat_id, auftrag, art=ART_UEBERARBEITUNG, zeigen=False)
        geschrieben.append(nummer)
    return geschrieben
```

Copy the exact `sperrtext`/`ziel_fuer` call shape from `schleife._schreibe_je_szene` (`:137-178`), without its lock.

`_schreibe_geschichte(conn, tg, klm, e, chat_id, auftraege) -> list[int]` (prose phases): `kurzgeschichte.schreibe(conn, tg, klm, e, chat_id, schleife._regie_fuer_die_geschichte(auftraege), vorlage=True, zeigen=False)`, then return the sorted scene numbers with prose. In phase 7, `pruefe_geschichte` uses `_schreibe_szenen` instead.

`pruefe_geschichte` follows the same steps for **every** scene:
- the first draft per scene (step 3, looping over scenes);
- the snapshot;
- `schliesse(..., fragen=fragen, szenen=None, mechanik=False, behalte_bessere=True, schreiber=_schreibe_geschichte if prose else _schreibe_szenen)`;
- the quote guard over the concatenated text of all scenes;
- `nachpass.nach_geschichte` (prose only);
- a log row with `ziel="geschichte"`, `szene_nummer=None`.

No parameter correction for A11 (not part of Birk's decision for 6.1).

Texts (German defaults in the module, EN in `texte.toml`; `T = sprache.Texte(__name__)`):

```python
_PRUEFUNG_NAMEN = {
    "b1": "Wendung", "a2": "Kausalkette", "a6": "Tschechow", "a9": "Fokus",
    "a10": "Materialtreue", "a11": "Stueckvorgaben", "c1": "Stimme",
}
_ZEILE_AUFTRAG = "Pruefung ({pruefung}): {text}"
_ZEILE_SPRACHPASS = "Sprachpass: Laenge und Sprachmuster nachgezogen."
_ZEILE_VERSCHLECHTERT = "Die Ueberarbeitung war schwaecher -- die bessere Fassung bleibt."
_ZEILE_ZITAT_VERWORFEN = "Eine Ueberarbeitung hat ein Interviewzitat verloren -- verworfen."
_ZEILE_PARAMETER = "Szene {nummer}: die Planung ({feld}) folgt jetzt dem Text."
```

EN:

```toml
_ZEILE_AUFTRAG = "Check ({pruefung}): {text}"
_ZEILE_SPRACHPASS = "Language pass: length and style tightened."
_ZEILE_VERSCHLECHTERT = "The revision was weaker -- the better version stays."
_ZEILE_ZITAT_VERWORFEN = "A revision lost an interview quote -- discarded."
_ZEILE_PARAMETER = "Scene {nummer}: the plan ({feld}) now follows the text."
[prueflauf._PRUEFUNG_NAMEN]  # or however dict constants are keyed (see ["web_vereint"._TEXT_TAB])
b1 = "Turning point"
a2 = "Causal chain"
a6 = "Chekhov"
a9 = "Focus"
a10 = "Faithful to material"
a11 = "Play requirements"
c1 = "Voice"
```

- [ ] **Step 1: Write the failing tests** — `tests/test_prueflauf.py`. Use the Padua profile (`monkeypatch.setenv(workshop.VARIABLE, "padua-2026")`, as in the `padua` fixture of `tests/test_nachpass.py`). Use a scene in phase 6 with prose, `Rundenrichter` imported from `test_dramaturgie_schleife`, and `monkeypatch.setattr(fanout, "waehle_richter", lambda *a, **k: richter)`. Fake KLM `prosa` returns a revised prose text in the answer format `szene.schreibe` accepts.

Required tests:
- `test_pruefe_szene_hoechstens_zwei_ueberarbeitungen_und_protokoll`: the judge always scores 0 → `bericht.ueberarbeitungen <= 2`; `repo.prueflaeufe` has one row with `ziel="szene"` and `fragen="b1,a10"`; `zweite_runde_mit_auftraegen` reflects the plan.
- `test_pruefe_szene_ohne_auftraege_schreibt_nicht`: the judge scores 2 → no prose call from the loop (`klm` counter counts only `art == ART_UEBERARBEITUNG`), `grund == schleife.GRUND_KEINE_AUFTRAEGE`.
- `test_verschlechterung_laesst_die_bessere_fassung_und_sagt_es`: plan `[1, 0]` (follow Task 4's test) → text equals the pre-check text, and `T._ZEILE_VERSCHLECHTERT` (EN wording) is in `bericht.zeilen`; the log row has `verworfen == "verschlechterung"`.
- `test_verlorenes_zitat_wird_verworfen`: the setup stores a verified quote (copy the setup of `tests/test_nachpass.py`'s quote-loss test); the fake revision drops it → text restored, `verworfen == "zitat"`.
- `test_erstentwurf_zeigt_auf_die_fassung_vor_der_pruefung`: after a run with one revision, `repo.erstentwurf_text(conn, sid)` equals the pre-check text and differs from the current prose.
- `test_hoechstens_drei_zeilen`: plan with orders for B1 and A10 over two rounds → `len(bericht.zeilen) <= 3`.
- `test_richterfehler_zeigt_trotzdem_und_protokolliert`: `waehle_richter` raises `RichterFehler("x")` → `bericht.zeilen == ["x"]`, log row with `grund == "ohne_pruefung"`.
- `test_pruefe_geschichte_nutzt_die_ganzstueck_fragen`: spy on `fanout.pruefe` kwargs → `fragen == FRAGEN_GESCHICHTE`, `szenen is None`, `mechanik is False`.
- `test_buehnenszene_fragt_a10_und_c1`: phase 7 with volltext → `fragen == ("a10", "c1")`.

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement `prueflauf.py`** as specified above. Module docstring: what it is, Birk's decisions quoted (≤ 2 rounds, abort keeps the better version, quote guard, ≤ 3 lines), the lock contract, and that it never posts.
- [ ] **Step 4: Run the tests** → PASS; also `tests/test_sprache_texte.py` (EN keys complete) and `tests/test_sprache_bitgleich.py` (new constants are new sections only).
- [ ] **Step 5: Full suite, then commit**

```bash
git add interview_theater/prueflauf.py interview_theater/sprachen/en/texte.toml tests/test_prueflauf.py interview_theater/dramaturgie/schleife.py
git commit -m "prueflauf: judge subset -> <=2 revision rounds -> quote guard -> language pass, logged per run"
```

---

## Task 7: Wire the check into every text display; Script-tab hint and "Show first draft" (also phase 5)

**Files:**
- Modify: `interview_theater/szene.py` (`_lauf`, `:2448-2521`)
- Modify: `interview_theater/kurzgeschichte.py` (`starte._lauf`, `:528-560`)
- Modify: `interview_theater/knoepfe/texte.py`, `knoepfe/szenen.py`, `knoepfe/wirkung.py`, `knoepfe/__init__.py`
- Modify: `interview_theater/sprachen/en/texte.toml`
- Test: `tests/test_prueflauf_anzeige.py` (new)

**Interfaces:**
- Consumes: `prueflauf.pruefe_szene`, `prueflauf.pruefe_geschichte`, `prueflauf.Bericht`
- Produces:
  - `knoepfe.skript_verweis(conn, e, chat_id) -> str`. Web group → `T._TEXT_SKRIPT_TAB` ("Read it in the Script tab."); Telegram → `T._TEXT_SKRIPT_LINK.format(url=f"{gruppenseite_url}#textbuch")`, or `T._TEXT_SKRIPT_TAB` if `e.web_url` is unset.
  - `knoepfe.zeige_geprueft_szene(conn, tg, e, chat_id, nummer, bericht) -> int`
  - `knoepfe.zeige_geprueft_geschichte(conn, tg, e, chat_id, bericht) -> int`
  - `knoepfe.ART_ERSTENTWURF = "erstentwurf"` with handler `_wirkung_erstentwurf`

**The display rule:**
- If `workshop.ueberarbeitung_aktiv()`: the hint message only (never the full text).
- Otherwise (prueflauf on without ueberarbeitung, a combination no shipped profile has): the full text as today via `szene._sende_szenentext` / `zeige_kurzgeschichte`, with the report lines appended as a separate message.

**Hint for one scene** (one message, `sende_mit_knoepfen`):

```
{kopf}            # T._TEXT_SZENE_BEREIT = "Szene {nummer} von {gesamt} ist fertig: {titel}."
{zusammenfassung} # szene.zusammenfassung, cut to 300 characters; omitted if empty
{zeilen...}       # bericht.zeilen (<= 3)
{verweis}         # skript_verweis(...)
```

The buttons depend on the phase:
- phase 5 → the existing `biete_nach_szenentext` buttons (keep their order: TEIL 1's e2e test taps the first one) plus `ART_ERSTENTWURF`;
- phase 6/7 with ueberarbeitung on → `[T.TEXT_WEITER_KNOPF → ART_SZENE_PASST, T.TEXT_ANDERS_KNOPF → ART_SZENE_ANDERS, kuerzen label → ART_SZENE_KUERZEN, T._TEXT_ERSTENTWURF_KNOPF → ART_ERSTENTWURF]`, wert `str(nummer)` like the existing scene buttons.

Read `biete_nach_szenentext` (`szenen.py:758-802`) and build the bar the same way (`_daten(repo.lege_knopf_an(...))`). Record the message with `repo.merke_bot_zeile(conn, chat_id, message_id, e, text)`. That way the hint (not the full text) is what the conversation bot sees.

**Hint for the whole story:** `T._TEXT_GESCHICHTE_BEREIT = "Die ganze Geschichte steht ({gesamt} Szenen)."`, then the vorspann logline if one exists (`entwurf` overview logline; else omit), the report lines, the link, and the buttons `[Yes, save → ART_GESCHICHTE_PASST, No, change it again → ART_GESCHICHTE_ANDERS, Shorter → ART_GESCHICHTE_KUERZEN, Show first draft → ART_ERSTENTWURF (wert "")]`.

**`_wirkung_erstentwurf` (no model):** wert `""` = whole story, else a scene number. Reply `T._TEXT_ERSTENTWURF = "Die Fassung vor der Pruefung steht im Script-Tab unter \"Erste Fassung\"."` plus `skript_verweis`. Send it with `d.tg.sende` and return it. If no first draft exists, send `T._TEXT_KEIN_ERSTENTWURF`.

**Hooks:**
- `szene._lauf`, inside `if art == ART:`. If `prueflauf.aktiv()`, call `schreibe(..., zeigen=False)` above (compute the flag before the `schreibe` call: `zeigen = not prueflauf.aktiv()`), then `bericht = prueflauf.pruefe_szene(conn, tg, klm, e, chat_id, nummer)`, then `knoepfe.zeige_geprueft_szene(conn, tg, e, chat_id, nummer, bericht)`, **instead of** the nachpass block (prueflauf runs nachpass itself). For `art != ART`, `zeigen` stays True (unchanged).
- `kurzgeschichte.starte._lauf`: the same with `schreibe(..., zeigen=not prueflauf.aktiv())`, then `pruefe_geschichte` + `zeige_geprueft_geschichte`, instead of `nachpass.nach_geschichte`.

- [ ] **Step 1: Write the failing tests** — `tests/test_prueflauf_anzeige.py`. Use the Padua profile, a fake judge (always score 2, so there are no orders and the test stays fast) and a fake KLM whose prose contains the marker `KOERPER-MARKER-`. Tests:
  - `test_phase5_stufe_b_zeigt_nur_hinweis` reproduces TEIL 1's Stage-B start (`szene.starte(... "SZENE 1: write this scene as prose, following the overview.")`, wait on `szene._sperre_fuer`). Assert: no message in `tg.gesendet`/`tg.knoepfe` contains `KOERPER-MARKER-`; the last bar has a button labelled "Show first draft"; `repo.prueflaeufe` has one row with `phase == 5` and `fragen == "b1,a10"`.
  - `test_telegram_bekommt_einen_link`: `einst` with `web_url="https://x/theatersoap"` (use `dataclasses.replace`) → the hint contains `"/g/"` and `"#textbuch"`.
  - `test_ohne_schalter_wie_bisher`: Dortmund (no env) → `szene.starte` posts the full text (`KOERPER-MARKER-` appears) and no `prueflauf` row exists.
  - `test_erstentwurf_knopf_ohne_modellaufruf`: tap it via `knoepfe.behandle` with a KLM whose methods raise → reply contains the Script-tab hint.
  - `test_geschichte_zeigt_nur_hinweis`: phase 6, `kurzgeschichte.starte` → no section text in the chat, one `prueflauf` row with `ziel == "geschichte"`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement** the hooks, the display functions, the new ART (constant in `texte.py`, imports in `wirkung.py`/`szenen.py`/`__init__.py`, the `_WIRKUNGEN` entry) and the EN texts:

```toml
_TEXT_SZENE_BEREIT = "Scene {nummer} of {gesamt} is ready: {titel}."
_TEXT_GESCHICHTE_BEREIT = "The whole story is there ({gesamt} scenes)."
_TEXT_SKRIPT_TAB = "Read it in the Script tab."
_TEXT_SKRIPT_LINK = "Read it in the Script tab: {url}"
_TEXT_ERSTENTWURF_KNOPF = "Show first draft"
_TEXT_ERSTENTWURF = "The version before the check is in the Script tab under \"First draft\"."
_TEXT_KEIN_ERSTENTWURF = "There is no earlier draft for this yet."
```

German defaults: "Szene {nummer} von {gesamt} ist fertig: {titel}.", "Die ganze Geschichte steht ({gesamt} Szenen).", "Lest sie im Script-Tab.", "Lest sie im Script-Tab: {url}", "Erste Fassung zeigen", the `_TEXT_ERSTENTWURF` above, and "Dazu gibt es noch keine fruehere Fassung."

- [ ] **Step 4: Run the tests** — the new file plus `tests/test_entwurf_ablauf.py tests/test_entwurf.py tests/test_knoepfe_struktur.py tests/test_knoepfe*.py tests/test_szene*.py tests/test_teil4_kurzgeschichte.py tests/test_nachpass*.py` → PASS. `test_entwurf_ablauf.py` monkeypatches only `prosa_entwurf_aktiv` (German default profile), so the check stays off there. That is intended: it guards the TEIL-1 flow unchanged.
- [ ] **Step 5: Full suite, then commit**

```bash
git commit -am "Check before every display: szene/kurzgeschichte runs go through prueflauf; Script-tab hint, Show first draft"
```

---

## Task 8: Phase 6 (Rewrite) for Padua — the whole story first, then scene by scene

**Files:**
- Create: `interview_theater/ueberarbeitung.py`
- Modify: `interview_theater/knoepfe/stationen.py` (phase-6 entry, `:349-372`), `knoepfe/wirkung.py` (`_wirkung_geschichte_passt` `:119`, `_wirkung_szene_passt` `:331`, `_wirkung_szene_usa` `:1394`), `knoepfe/texte.py`
- Modify: `interview_theater/sprachen/en/texte.toml`, `workshop/padua-2026/phasentexte.toml` (`[einleitung]` 6)
- Test: `tests/test_ueberarbeitung_phase6.py` (new)

**Interfaces:**
- Consumes: `prueflauf.starte_szene`, `prueflauf.starte_geschichte`, `knoepfe.zeige_geprueft_szene`, `knoepfe.zeige_geprueft_geschichte`, `szene.starte`, `kurzgeschichte.starte`, `phasen.setze`, `knoepfe.eintritt_in_phase`
- Produces (all in `ueberarbeitung.py`, no SQL):
  - `aktiv() -> bool` = `workshop.ueberarbeitung_aktiv()`
  - `szenennummern(conn, chat_id) -> list[int]` (sorted, without `None`)
  - `aktuelle_szene(conn, chat_id) -> int | None`:
    - phase 6: the first scene without `ueberarbeitung_bestaetigt_am`, but **only** once `gesamttext_fixiert_am` is set; before that, `None`, meaning "the whole story is the current object";
    - phase 7: the first scene without `fertig_am`, once `sprechweisen_fixiert_am` is set and every scene has a form; otherwise `None`.
  - `weiter_6(conn, tg, klm, e, chat_id) -> None`, the single step function of phase 6:
    - no scene has prose → `knoepfe.biete_kurzgeschichte(conn, tg, chat_id, T._TEXT_KURZGESCHICHTE_BEREIT)` (fallback: write the story first);
    - else `gesamttext_fixiert_am` empty → `prueflauf.starte_geschichte(..., danach=lambda b: knoepfe.zeige_geprueft_geschichte(conn, tg, e, chat_id, b))`;
    - else `n = aktuelle_szene(...)` is not None → `prueflauf.starte_szene(..., n, danach=lambda b: knoepfe.zeige_geprueft_szene(conn, tg, e, chat_id, n, b))`;
    - else → `schliesse_6_ab(...)`.
  - `bestaetige_gesamt(conn, tg, klm, e, chat_id) -> str`: set `gesamttext_fixiert_am`, send `T._TEXT_GESAMT_GESPEICHERT` ("Saved. Now we go scene by scene: scene 1 of {gesamt}."), then `weiter_6(...)`; return the toast text.
  - `bestaetige_szene_6(conn, tg, klm, e, chat_id, nummer) -> str`: set `repo.setze_szene_ueberarbeitung_bestaetigt`, then `weiter_6(...)`.
  - `schliesse_6_ab(conn, tg, klm, e, chat_id) -> None`: send **one** closing message `T._TEXT_6_FERTIG` ("Rewrite done: all {gesamt} scenes are saved. On to the Stage Version."), then `phasen.setze(conn, chat_id, 7, "ueberarbeitung", notiz="alle Szenen ueberarbeitet")`, then `knoepfe.eintritt_in_phase(conn, tg, klm, e, chat_id, 7)`.
  - `ueberarbeite(conn, tg, klm, e, chat_id, notiz: str, nummer: int | None = None) -> threading.Thread | None`: the **one** path for content feedback (button note, erkenner art, Task 10).
    - phase 6 and `gesamttext_fixiert_am` empty and `nummer is None` → `kurzgeschichte.starte(conn, tg, klm, e, chat_id, notiz, vorlage=True)`;
    - otherwise `n = nummer or aktuelle_szene(...)`; if `n` is None, return None; else `szene.starte(conn, tg, klm, e, chat_id, szene.ueberarbeitungsauftrag(conn, chat_id, n, notiz))`.
    - Both runs go through prueflauf (Task 7) and end in the hint plus buttons again.

**knoepfe branches (all gated by `ueberarbeitung.aktiv()`):**
- `stationen.eintritt_in_phase` phase 6: keep `biete_proaktiv(..., vorspann=kopf)` and the USA branch unchanged. Replace `biete_kurzgeschichte(...)` in the else-branch with `ueberarbeitung.weiter_6(...)`. In Padua, do not send `_TEXT_PROAKTIV`'s phase button here: the end of phase 6 jumps automatically. Read `biete_proaktiv` and, if it adds a phase button, call the intro-only variant instead (send `kopf` with `tg.sende` + `repo.merke_bot_zeile`).
- `_wirkung_szene_usa` in phase 6: `ueberarbeitung.weiter_6(...)` instead of `biete_kurzgeschichte`.
- `_wirkung_geschichte_passt`: phase 6 + aktiv → `return ueberarbeitung.bestaetige_gesamt(conn, d.tg, d.klm, d.e, d.chat_id)`.
- `_wirkung_szene_passt`: phase 6 + aktiv → `return ueberarbeitung.bestaetige_szene_6(..., nummer)` (`nummer` from `d.wert`, as the existing handler resolves it).
- `_wirkung_geschichte_anders` / `_wirkung_szene_anders` stay. They already wait for the next chat message as a note (`knoepfe.nimm_geschichte_notiz` / `szenenfolge.nimm_regienotiz` in `ablauf.py:1116-1137`). In Padua, `ablauf` must route those notes through `ueberarbeitung.ueberarbeite(...)` (scene note: `nummer` from `nimm_regienotiz`; story note: `nummer=None`) instead of calling `szene.starte`/`kurzgeschichte.starte` directly. That way the phase-6 prose rewrite gets the `BISHER_MARKER`. Gate it with `ueberarbeitung.aktiv()`; Dortmund keeps today's calls byte-identical.
- `_wirkung_geschichte_kuerzen`/`_wirkung_szene_kuerzen` stay. `kuerzung.starte` already goes through `szene.starte`/`kurzgeschichte.starte` and therefore through the check.

**Padua phase-6 entry moderation** (`workshop/padua-2026/phasentexte.toml`, `[einleitung]` key 6; read the file for its key format). Replace the "Now I write your story in one piece …" text with:

```
First you read the whole story in the Script tab and tell me where it should go. Then we go scene by scene into the fine-tuning.
```

- [ ] **Step 1: Write the failing tests** — `tests/test_ueberarbeitung_phase6.py`. Use the Padua profile, a fake judge with score 2 (no orders), a fake KLM, three scenes with prose and `entwurf_bestaetigt_am` set, and `phasen.setze(...,6,...)`. Tests:
  - entering phase 6 (`knoepfe.eintritt_in_phase(..., 6)`; set `gruppe` USA consent so the USA question is not due — see how `szene_claude.angebot_faellig` decides and set that state, e.g. `repo.setze_szene_usa(conn, 1, False)`) → after waiting on the kurzgeschichte lock, a `prueflauf` row with `ziel="geschichte"` and a hint with "Yes, save"; **no** prose model call (the story is not regenerated: `klm.prosa_aufrufe == []` when the judge returns score 2);
  - tapping "Yes, save" → `gesamttext_fixiert_am` set, a message containing "scene 1 of 3", and a `prueflauf` row `ziel="szene", szene_nummer=1`;
  - `ueberarbeitung.ueberarbeite(..., "make it sadder")` before fixing → one prose run with `vorlage=True` (spy on `kurzgeschichte.starte`), afterwards a new hint;
  - after fixing, `ueberarbeite(..., "angrier")` → a `szene.starte` call whose order contains `szene.BISHER_MARKER` and "SZENE 1" / scene 1;
  - tapping "Yes, save" three times on scenes → exactly one message with `T._TEXT_6_FERTIG`'s wording, `phasen.aktuelle == 7`;
  - Dortmund (no env): phase-6 entry still offers "Geschichte schreiben" (`ART_GESCHICHTE_SCHREIBEN` in the last bar).
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests** — the new file plus `tests/test_knoepfe*.py tests/test_phasentexte*.py tests/test_profile_geruest.py tests/test_ablauf*.py` → PASS.
- [ ] **Step 5: Full suite, then commit**

```bash
git commit -am "Padua phase 6 (Rewrite): check the existing story, approve the whole, then scene by scene, auto-jump to 7"
```

---

## Task 9: Phase 7 (Stage Version) for Padua — forms by chat, voices, scene by scene, play check at the end

**Files:**
- Create: `interview_theater/sprechweise.py`
- Modify: `interview_theater/ueberarbeitung.py`
- Modify: `interview_theater/knoepfe/stationen.py` (phase-7 entry, `:324-332`), `knoepfe/szenen.py`, `knoepfe/wirkung.py`, `knoepfe/texte.py`, `knoepfe/__init__.py`
- Modify: `interview_theater/sprachen/en/texte.toml`, `workshop/padua-2026/phasentexte.toml` (`[einleitung]` 7)
- Test: `tests/test_ueberarbeitung_phase7.py`, `tests/test_sprechweise.py` (new)

**Interfaces:**
- Produces, in `sprechweise.py`:
  - `ART = "sprechweise"`
  - `SCHEMA = {"type":"object","additionalProperties":False,"required":["sprechweisen"],"properties":{"sprechweisen":{"type":"array","items":{"type":"string"}}}}`. Each item is `"Name: one line"`, flat as everywhere else.
  - `ANWEISUNG`: a module constant (DE) with its EN translation in `texte.toml`. **Not** a new prompt file: a new German `.md` would need a Dortmund snapshot section.
  - `baue_nutzertext(conn, chat_id) -> str`: per character, name, description, existing `sprachstil`, `sprachprofil`, and verified quotes (`figur.zitate`). Only characters **without** `sprachstil` need an answer; the others are listed as given.
  - `fehlende(conn, chat_id) -> list` (characters without `sprachstil`)
  - `starte(conn, tg, klm, e, chat_id) -> threading.Thread | None`. In a thread: if `fehlende` is empty, call `knoepfe.biete_sprechweisen(conn, tg, e, chat_id)` directly with no model call. Otherwise call `modellwahl.aufruf_schema(conn, klm, e, chat_id, T.ANWEISUNG, baue_nutzertext(conn, chat_id), SCHEMA, ART, ueber_claude=szene_claude.ist_aktiv(e, conn, chat_id), modell=e.erkenner_modell)` (copy `entwurf.generiere_uebersicht`), parse each `"Name: text"`, and write **only** for characters that are still without a style (`repo.setze_figur_sprachstil(conn, figur_id, text)`). Then `knoepfe.biete_sprechweisen(...)`. On an error: Vorfall `sprechweise_fehlgeschlagen`, `kosten.melde_pause_wenn_deckel`. It has its own lock register with a meta-lock, like `entwurf._sperre_fuer`.
- Produces, in `ueberarbeitung.py`:
  - `formen_offen(conn, chat_id) -> list[int]` (scene numbers without `form`)
  - `sende_formwahl(conn, tg, e, chat_id) -> None`: **one** message, `T._TEXT_FORMWAHL_KOPF`, then per scene `"{n}. {titel} -- {satz}"` (`satz` = first sentence of `zusammenfassung`, else `was_passiert`; at most 160 characters), then `T._TEXT_FORMWAHL_FRAGE` ("Which form for each number? For example: 1 chorus, 2 dialogue, 3 rap. Forms: {formen}."). `{formen}` are the Padua display names (`workshop` forms). No buttons and no suggestion. Record it via `repo.merke_bot_zeile`.
  - `weiter_7(conn, tg, klm, e, chat_id) -> None`, the single step function:
    - `formen_offen` → `sende_formwahl`;
    - else `sprechweisen_fixiert_am` empty → `sprechweise.starte(...)`;
    - else `n = aktuelle_szene(...)`:
      - `n` with no `volltext` → `szene.starte(conn, tg, klm, e, chat_id, T._AUFTRAG_BUEHNE.format(nummer=n))` (through prueflauf; it ends in the hint);
      - `n` with `volltext` (re-entry) → `prueflauf.starte_szene(... n, danach=zeige_geprueft_szene)`;
    - else → `starte_schluss(...)`.
  - `bestaetige_sprechweisen(conn, tg, klm, e, chat_id) -> str`: set `sprechweisen_fixiert_am`, send `T._TEXT_SPRECHWEISEN_GESPEICHERT`, then `weiter_7`.
  - `bestaetige_szene_7(conn, tg, klm, e, chat_id, nummer) -> str`: `repo.setze_szene_fertig` (read its signature, `repo.py:2694`), then `weiter_7`.
  - `starte_schluss(conn, tg, klm, e, chat_id) -> threading.Thread | None`: takes the szene lock non-blocking. In a thread:
    1. `prueflauf.pruefe_geschichte(..., fragen=prueflauf.FRAGEN_GESCHICHTE)` (phase 7 → per-scene writer on `volltext`);
    2. send the report lines (≤ 3) as one message if not empty;
    3. `stueckpruefung.starte(conn, tg, klm, e, chat_id)`, whose display (`zeige_stueckpruefung`) lists findings, not the text;
    4. send `T._TEXT_TEXTBUCH_FERTIG` ("The script is complete. Read it in the Script tab.") plus `knoepfe.skript_verweis`.
    - `stueckpruefung.starte` runs its own thread. Call it after releasing the szene lock, from `danach`, or pass it `nachbereitung` (read its signature) so the closing line follows the play check.
- Produces, in knoepfe:
  - `knoepfe.biete_sprechweisen(conn, tg, e, chat_id) -> int`: **one** message, `T._TEXT_SPRECHWEISEN_KOPF` ("How each character speaks:"), then one line per character `"- {name}: {sprachstil}"`, then buttons `[T.TEXT_WEITER_KNOPF → ART_SPRECHWEISEN_PASST, T.TEXT_ANDERS_KNOPF → ART_SPRECHWEISEN_ANDERS]`.
  - `_wirkung_sprechweisen_passt` → `ueberarbeitung.bestaetige_sprechweisen(...)`.
  - `_wirkung_sprechweisen_anders` → send `T._TEXT_SPRECHWEISEN_AENDERN` ("Tell me who should speak differently, e.g. \"Mira: short sentences, lots of slang\".") and return it. No model call. The answer is handled by the erkenner art `sprechweise_setzen` (Task 10).
  - Branches in `_wirkung_szene_passt`: phase 7 + aktiv → `ueberarbeitung.bestaetige_szene_7(...)`.
  - `stationen.eintritt_in_phase` phase 7, Padua: send `kopf`, then `ueberarbeitung.weiter_7(...)`. **Skip** `biete_durchlauf` and the automatic `starte_stueckpruefung` (the play check comes at the end).

Texts (German defaults + EN):

```toml
_TEXT_FORMWAHL_KOPF = "Here are your scenes:"
_TEXT_FORMWAHL_FRAGE = "Which form for each number? For example: 1 chorus, 2 dialogue, 3 rap. Forms: {formen}."
_AUFTRAG_BUEHNE = "SZENE {nummer}: transfer this scene into its form."
_TEXT_SPRECHWEISEN_KOPF = "How each character speaks:"
_TEXT_SPRECHWEISEN_AENDERN = "Tell me who should speak differently, e.g. \"Mira: short sentences, lots of slang\"."
_TEXT_SPRECHWEISEN_GESPEICHERT = "Saved. Now scene by scene into the stage version: scene 1 of {gesamt}."
_TEXT_TEXTBUCH_FERTIG = "The script is complete. Read it in the Script tab."
```

**Padua phase-7 entry moderation** (`phasentexte.toml` `[einleitung]` 7):

```
Now the story becomes a play: first you choose a form for each scene, then how each character speaks, then we transfer scene by scene. At the end I check the whole script once.
```

If `{{formen_liste_oder}}` was used there, it is no longer needed. Check `scripts.pruefe_profil padua-2026` still passes.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_sprechweise.py`: the fake schema returns `["Mira: short sentences", "Jo: slow"]`, but Jo already has a style → only Mira is written; one message with both lines and the two buttons; with all styles present → no schema call.
  - `tests/test_ueberarbeitung_phase7.py` (Padua, fake judge score 2, fake KLM):
    - entering phase 7 → exactly one message containing "1." … "3." and "Which form for each number?", **no** button bar, **no** `stueckpruefung` call (spy on `stueckpruefung.starte`);
    - with forms set (via `repo.setze_szenenfeld(..., "form", "chor")` etc.), `weiter_7` → the voices message;
    - tapping "Yes, save" there → `sprechweisen_fixiert_am` set and a `szene.starte` order for scene 1 (spy);
    - after scene 1's hint, tapping "Yes, save" → scene 2 starts; after the last one → `stueckpruefung.starte` called once and the "script is complete" line sent; a `prueflauf` row with `ziel="geschichte"` and `phase=7`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests** — the new files plus `tests/test_knoepfe*.py tests/test_stueckpruefung.py tests/test_knoepfe_struktur.py tests/test_pruefe_profil.py` → PASS.
- [ ] **Step 5: Full suite, then commit**

```bash
git commit -am "Padua phase 7 (Stage Version): form list by chat, character voices, scene-by-scene transfer, play check at the end"
```

---

## Task 10: Chat works where buttons work — five new erkenner arts (EN, Padua-gated), B1/B2

**Files:**
- Modify: `interview_theater/erkenner.py`
- Modify: `interview_theater/ablauf.py` (invented "Noted" guard)
- Modify: `interview_theater/sprachen/en/prompts/erkenner.md`
- Modify: `korpus/en/erkenner.jsonl`
- Modify: `tests/test_korpus.py`, `tests/test_sprache_prompts.py`, `tests/test_erkenner.py`
- Test: `tests/test_erkenner_teil2.py` (new)

**The five arts:**

| art | phases | write path | side effect in `laufe` |
|---|---|---|---|
| `text_ueberarbeiten` | 6, 7 | none (like `szene_schreiben`) | `ueberarbeitung.ueberarbeite(conn, tg, klm, e, chat_id, notiz, nummer)`. `wert` is the note; an optional leading `"scene N:"` / `"Szene N:"` sets `nummer` (parse with `kuerzung.nummer_aus_wert`). At most one per run |
| `fassung_abnehmen` | 5, 6, 7 | none | the same function as the matching "Yes, save" button (see below) |
| `formen_setzen` | 7 | `szene.form` per number | when `ueberarbeitung.formen_offen` is empty after the write and the voices are not fixed → `ueberarbeitung.weiter_7` |
| `sprechweise_setzen` | 7 | `figur.sprachstil` | when `sprechweisen_fixiert_am` is empty → `knoepfe.biete_sprechweisen` (updated list, same buttons) |
| `schaerfung_entscheidung` | 5 | the same fields as the sharpening buttons (`schaerfung.uebernimm_szene` / `uebernimm_figur` / `verwirf_stellen`) | `knoepfe.biete_schaerfung(conn, tg, chat_id)` for the next proposal |

**Gating — extend TEIL 1's table, no second mechanism:**

```python
PHASEN_SPEZIFISCHE_ARTEN: dict[str, tuple[int, ...]] = {
    "uebersicht_aendern": (5,),
    # Padua Phasen TEIL 2 (03.10.2026)
    "text_ueberarbeiten": (6, 7),
    "fassung_abnehmen": (5, 6, 7),
    "formen_setzen": (7,),
    "sprechweise_setzen": (7,),
    "schaerfung_entscheidung": (5,),
}

#: Welcher Profilschalter eine ART ueberhaupt erst freischaltet -- dieselbe
#: Tabelle, eine zweite Spalte. Eine ART ohne Eintrag ist profilfrei. Ohne
#: Schalter steht die ART auch nicht im Schema (``arten_fuer_schema``):
#: Dortmund sieht dieselbe Enum-Liste wie vor TEIL 2.
PROFILSCHALTER_DER_ARTEN: dict[str, str] = {
    "text_ueberarbeiten": "ueberarbeitung",
    "fassung_abnehmen": "ueberarbeitung",
    "formen_setzen": "ueberarbeitung",
    "sprechweise_setzen": "ueberarbeitung",
    "schaerfung_entscheidung": "ueberarbeitung",
}

_SCHALTER = {"ueberarbeitung": lambda: workshop.ueberarbeitung_aktiv()}


def _schalter_an(art: str) -> bool:
    name = PROFILSCHALTER_DER_ARTEN.get(art)
    return name is None or _SCHALTER[name]()


def arten_fuer_schema() -> list[str]:
    return [a for a in ARTEN if _schalter_an(a)]
```

- `_ist_phasenpassend` additionally returns `False` when `not _schalter_an(art)`.
- The schema enum (`:261`) becomes `arten_fuer_schema()`. If the schema is a module-level dict, build it lazily in `erkenne` (read the code; keep Dortmund's resulting dict equal: a test asserts that).
- Append the five arts to `ARTEN` with a one-line comment each.
- `laufe` (`:2510-2560`): compute `freigegeben = [a for a in aenderungen if _ist_phasenpassend(conn, chat_id, a.get("art"))]` once, and pass `freigegeben` to `_starte_szene`, `_starte_kuerzung`, `_starte_entwurf_uebersicht` and the new `_starte_teil2(klm, tg, conn, e, chat_id, freigegeben, wirkliche)`. This also fixes the TEIL-1 inconsistency that `_starte_szene`/`_starte_kuerzung` received unfiltered entries. Check `tests/test_erkenner.py` still passes; existing arts are phase-free, so nothing changes for them.
- When `text_ueberarbeiten` is in `freigegeben`, skip `_starte_szene` in the same run, and drop `festlegung_setzen` entries from the list given to `wende_an`. This ensures B2 ("make the mother angrier") never ends as a "Noted:" agreement without a rewrite. Do this filtering before `wende_an`, gated by `ueberarbeitung.aktiv()`.
- `_starte_kuerzung`, Padua only: when `nummer is None` and phase in (6, 7) and `ueberarbeitung.aktuelle_szene(...)` is not None, use that number (the scene on display) instead of the whole story or the "which scene?" question.
- `_starte_teil2` skips silently (log only) when the relevant lock is held (`szene._sperre_fuer(chat_id).locked()`, the kurzgeschichte lock, `sprechweise` lock). That covers the case where `ablauf` already consumed the same message as a note after "No, change it again".

`fassung_abnehmen` dispatch (`ueberarbeitung.nimm_ab(conn, tg, klm, e, chat_id) -> str | None`, new; returns `None` when nothing awaits approval):
- phase 5: overview present and `geschichte_uebersicht_fixiert_am` empty → `entwurf.fixiere_uebersicht(conn, tg, klm, e, chat_id)`. **Refactor** the body of `_wirkung_uebersicht_passt` into this function; the handler calls it. Else the first scene with prose and without `entwurf_bestaetigt_am` → `entwurf.bestaetige_szene(conn, tg, klm, e, chat_id, nummer)`; **refactor** `_wirkung_entwurf_szene_passt`'s body into it in the same way.
- phase 6: `gesamttext_fixiert_am` empty and prose present → `bestaetige_gesamt`; else `aktuelle_szene` with prose → `bestaetige_szene_6`.
- phase 7: forms open → `None`; voices not fixed and every character has a style → `bestaetige_sprechweisen`; else `aktuelle_szene` with `volltext` → `bestaetige_szene_7`.

`formen_setzen` write path (`_wende_formen_setzen_an`, returns the usual result rows for the "Noted:" message):
- Parse `wert` with `re.split(r"[|,;]", ...)` into `(nummer, form)` pairs, `r"(\d{1,2})\s*[:.\-]?\s*(.+)"`.
- Map the form name with `szene.formdatei(form)` or the `szene.FORM_STICHWOERTER` lookup the code already uses for display names. Read `szene.formdatei` and `FORM_STICHWOERTER`; the result must be in `szene.FORMEN` (not `prosa`).
- Write `repo.setze_szenenfeld(conn, szene_id, "form", form)` for existing scenes only. This writes `form` (the group's own choice), not `form_vorschlag`. Say so in the comment, quoting AGENTS.md "Eine Menüzeile ist keine Geschichte" ("die Regel hält den Vorschlag eines Modells aus dem Feld heraus, nicht die Wahl der Gruppe").

`sprechweise_setzen` write path: `wert` `"Name: text"` → `repo.hole_figur(conn, chat_id, name)` → `repo.setze_figur_sprachstil(conn, figur["id"], text)`, with a result row for the message.

`schaerfung_entscheidung` (side effect, no write path; mirrors the button handlers `wirkung.py:164-230`; **refactor** their bodies into `knoepfe.szenen.uebernimm_schaerfung_szene(conn, tg, chat_id, nummer, anders=False)`, `uebernimm_schaerfung_figur(conn, tg, chat_id, name, anders=False)` and `verwirf_schaerfung(conn, tg, chat_id)` so both paths share one function). `wert` forms:
- `"scene N"` / `"Szene N"` → `uebernimm_schaerfung_szene`;
- `"character NAME"` / `"Figur NAME"` → `uebernimm_schaerfung_figur`;
- `"none"` / `"keine"` → `verwirf_schaerfung`, applied to the ids of the currently open passage proposals (read `biete_schaerfung` to find where those ids come from; if they are not reconstructible without the button, then `"none"` only re-offers via `biete_schaerfung`, and this is noted in the final report).

**English erkenner prompt.** Add points 27–31 in the same style as point 26 (`uebersicht_aendern`, lines 219–229). Change "exactly twenty-six kinds" to "exactly thirty-one kinds". Each point has: when it applies (the bot just showed X / asked Y in the lead-up), `wert` format, and when NOT (a question about the text is not feedback; a plain "ok" with nothing awaiting approval is nothing; feedback on the displayed text is `text_ueberarbeiten`, never `festlegung_setzen`). Keep `szene_kuerzen` for "shorter". Update `tests/test_sprache_prompts.py::test_erkenner_en_zaehlt_seine_arten_richtig` to `range(1, 32)` and "thirty-one". **The German prompt is not touched.**

**Corpus.** English cases (ids `en-…`), each with `notiz`; the bot's hint as an `ist_bot` message or `vorlauf`:
- `text_ueberarbeiten`: 3 positives ("make the mother angrier" with wert containing "angrier"; "scene 2: less talking, more silence" with wert containing "scene 2"; "the ending is too soft, make it hurt more"); 2 negatives ("why is the mother so angry?", which is a question; "we'll read it later").
- `fassung_abnehmen`: 2 positives (`zustimmung: true`): "yes, save it" after the hint; "perfect, keep it like that". 1 negative: "yes" after a bot *question* unrelated to a text ("Do you want a break?").
- `formen_setzen`: 2 positives: "1 chorus, 2 dialogue, 3 rap" → wert containing "1" and "chorus"; "scene 1 should be a song and 2 a monologue". 1 negative: "what is a chorus?".
- `sprechweise_setzen`: 2 positives: "Mira: short sentences, lots of slang"; "make Jo talk slower, like he's tired" → wert containing "Jo". 1 negative: "Mira is the oldest" (a character fact, not a way of speaking; expected `figur_setzen` or nothing; use whatever the existing corpus does for similar facts).
- `schaerfung_entscheidung`: 2 positives: "yes, take the line for scene 1"; "no, nothing of that for Mira". 1 negative: "what does that quote mean?".

Keep `wert` minimal: a core substring, not the wording (AGENTS.md "Beim Erweitern"). Respect the allowed `arbeitsstand` keys (`test_korpus.py:203`); add none.

**`tests/test_korpus.py`:**
- Add `NUR_ENGLISCH = {"text_ueberarbeiten", "fassung_abnehmen", "formen_setzen", "sprechweise_setzen", "schaerfung_entscheidung"}` with a comment: Padua-only arts, described only in the English prompt, so the German corpus cannot carry them without a German prompt change (Dortmund byte-identity).
- `test_erkenner_jede_art_mindestens_zweimal` exempts them for DE.
- A new test requires ≥ 2 positive EN cases for each, and ≥ 1 negative EN case whose `notiz` names the art.
- The DE count pin (156/55) is unchanged.
- Bump EN minimums only if a test pins an exact EN count.

**Invented-"Noted" guard (B2, `ablauf.py`).** Add next to `ist_erfundene_systemzeile`:

```python
#: Padua Phasen TEIL 2 / Flow-Audit B2: der Gespraechs-Bot schrieb "Noted:"
#: ohne dass etwas geschrieben war. "Noted:" ist der Kopf der
#: Erkenner-Meldung (erkenner._NOTIERT_KOPF, englisch) -- im Gespraechszug
#: ist er immer erfunden.
_NOTIERT_ERFUNDEN_EN = re.compile(r"^\s*noted\b", re.IGNORECASE)


def ist_erfundenes_notiert(text: str | None) -> bool:
    return _NOTIERT_ERFUNDEN_EN.search((text or "")) is not None
```

Use it where `ist_erfundene_systemzeile` is checked in `antworte`, **only** when `ueberarbeitung.aktiv()` and `phasen.aktuelle in (6, 7)`: discard the answer, record Vorfall `gespraech_notiert_erfunden`, send nothing. Mirror the existing discard branch exactly.

- [ ] **Step 1: Write the failing tests** — `tests/test_erkenner_teil2.py`:
  - schema enum: Dortmund (no env) has no new arts; Padua has all five;
  - gating: in phase 5, `text_ueberarbeiten` is not phasenpassend; in Dortmund phase 7 it is not either;
  - `laufe` with a fake KLM whose `schema` returns `{"aenderungen": [{"art": "text_ueberarbeiten", "wert": "make the mother angrier"}]}` (copy the exact erkenner answer shape from `tests/test_erkenner.py`) in Padua phase 7 with `aktuelle_szene == 1` → `szene.starte` spied with an order containing "angrier" and scene 1; **no** message starting with "Noted";
  - the same with `festlegung_setzen` plus `text_ueberarbeiten` → no festlegung row is written;
  - `formen_setzen` `"1:chorus|2:dialogue"` → `szene.form` = `chor`/`dialog` (the internal keys); the message starts with "Noted";
  - `sprechweise_setzen` `"Mira: short sentences"` → `figur.sprachstil`;
  - `fassung_abnehmen` in phase 6 with an unfixed story → `gesamttext_fixiert_am` set;
  - `schaerfung_entscheidung` `"scene 1"` → `schaerfung.uebernimm_szene` spied for scene 1;
  - `ist_erfundenes_notiert("Noted: the mother is angrier")` is True; in Dortmund the guard does not fire.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement** everything above (erkenner, the refactors in `entwurf.py`/`knoepfe`, `ueberarbeitung.nimm_ab`, ablauf, prompt, corpus, test adjustments).
- [ ] **Step 4: Run the tests** — the new file plus `tests/test_erkenner*.py tests/test_korpus.py tests/test_sprache_prompts.py tests/test_ruecknahme*.py tests/test_entwurf*.py tests/test_ablauf*.py tests/test_profil_bitgleich.py tests/test_sprache_bitgleich.py` → PASS. The undo round-trip test runs every undo-capable art; `formen_setzen`/`sprechweise_setzen` must round-trip (they write tracked columns). If it needs fixture data (scenes/characters), add it there.
- [ ] **Step 5: Full suite, then commit**

```bash
git commit -am "erkenner: five Padua-gated arts (revise, approve, forms, voices, sharpening) via the phase table; EN prompt + corpus; Noted guard"
```

---

## Task 11: English phase prompts 6 and 7, "hook", B3

**Files:**
- Modify: `interview_theater/sprachen/en/prompts/phasen/6.md`, `phasen/7.md`, `formen/lied.md`
- Test: `tests/test_phasen_prompts_teil2.py` (new)

- [ ] **Step 1: Write the failing tests:**

```python
"""Padua Phasen TEIL 2: Gattungsspezifisches nur in formen/<form>.md."""
from pathlib import Path

EN = Path(__file__).resolve().parent.parent / "interview_theater" / "sprachen" / "en" / "prompts"


def test_phase7_en_ohne_hook():
    assert "hook" not in (EN / "phasen" / "7.md").read_text(encoding="utf-8").lower()


def test_rap_chor_lied_en_mit_hook():
    for form in ("rap", "chor", "lied"):
        assert "hook" in (EN / "formen" / f"{form}.md").read_text(encoding="utf-8").lower(), form


def test_phase6_en_ohne_alten_einzelszenen_ausloeser():
    """Flow-Audit B3: kein 'write us scene 3' mehr neben dem Ablauf."""
    text = (EN / "phasen" / "6.md").read_text(encoding="utf-8").lower()
    assert "write us scene" not in text
    assert "script tab" in text


def test_phase7_en_nennt_formwahl_sprechweisen_und_script_tab():
    text = (EN / "phasen" / "7.md").read_text(encoding="utf-8").lower()
    assert "which form for each number" in text
    assert "script tab" in text
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Rewrite the two EN phase files** for the new reality. Keep the heading lines (`## Current phase: 6 · Rewrite`, `## Current phase: 7 · Stage Version`), the "What you don't start on your own:" section and its fixed closing sentence (compare with the other EN phase files and keep the same wording pattern).

  **6.md says:**
  - the story already exists from the Prose Draft;
  - the group first reads the whole story in the Script tab and says where it should go (you never paste the story into the chat);
  - feedback on the whole is turned into a rewrite of the whole;
  - after "Yes, save" you go scene by scene, and you always say where the group stands ("scene 2 of 4");
  - feedback on a scene is a rewrite of that scene, and when the text is better than the plan, the plan follows the text;
  - no forms in this phase;
  - you never announce runs, never write "Noted";
  - remove every "write us scene 3" trigger and every per-scene-write button list that no longer exists. Name only the buttons that exist now: "Yes, save", "No, change it again", "Shorter (25 %)", "Show first draft".

  **7.md says:**
  - the group first chooses the form for every scene in one answer to "Which form for each number?" — you never suggest forms unless the group explicitly asks, and then they confirm;
  - then you show how each character speaks, and the group confirms or changes it;
  - then scene by scene, read in the Script tab;
  - content feedback ("make the mother angrier") is a rewrite of the current scene, never a "Noted";
  - at the end the whole script is checked once;
  - keep the text-work rules 1–6, but rule 4 loses its last sentence ("This applies especially to the hook, the last line and the title."). Rewrite rule 4 so it holds for any form. Remove any other form-specific statement from 7.md (forms live in `formen/*.md`).

  **lied.md**, in its existing refrain/structure section, add one sentence:

```
The refrain is the song's hook: the line the audience can sing back after one hearing. Keep it short and give it the clearest image of the song.
```

  The German files stay unchanged. Do not touch `interview_theater/prompts/phasen/6.md`, `7.md` or `prompts/formen/lied.md`.

- [ ] **Step 4: Run the tests** — the new file plus `tests/test_anweisungen*.py tests/test_sprache_prompts.py tests/test_profil_bitgleich.py tests/test_sprache_bitgleich.py tests/test_prompt_audit*.py`. If a Padua prompt-audit fixture (e.g. `docs/prompt-audit/2026-10-02-padua-p2/02-gespraech-phase6.txt`) is compared by a test and now differs **only** because of these intended EN changes, regenerate exactly that fixture with the same generator its test names. Mention it in the commit message. Never regenerate a Dortmund/German fixture.
- [ ] **Step 5: Full suite, `$PY -m scripts.pruefe_profil padua-2026`, then commit**

```bash
git commit -am "EN phase prompts 6/7 for the new flow; hook moves from phase 7 into formen (lied gains it); Flow-Audit B3 (EN)"
```

---

## Task 12: Script tab — whole text, versions, first draft

**Files:**
- Modify: `interview_theater/web_daten.py` (`_szenen`, `:547`: read `erstentwurf_fassung`; a new reader for the first-draft text)
- Modify: `interview_theater/web.py` (`textbuch_koerper`, `:3051`; `_probe_szene_html`, `:2816`)
- Modify: `interview_theater/sprachen/en/texte.toml`
- Test: `tests/test_web_skript_tab.py` (new)

**Interfaces:**
- Produces:
  - `web_daten.erstentwuerfe(conn, chat_id) -> dict[int, str]` (`szene_id → text`, only where `erstentwurf_fassung` is set **and** the text differs from the current text; SQL join as in `repo.erstentwurf_text`, `mode=ro` connection)
  - `gruppe_nach_token(...)["erstentwuerfe"]`
  - The textbook loader of the standalone `/g/<token>/textbuch` gets it too: find the loader that `textbuch_html`'s route uses and add the key there.
- Rendering in `_probe_szene_html` (all read-only, **no `style=`, no `onclick=`**):
  - the prose stays as it is ("Als Geschichte:" label when there is no volltext);
  - when `daten["fassungen"][szene_id]` has ≥ 2 entries, add `<details class="fruehere"><summary>{T._TEXT_FRUEHERE.format(anzahl=n-1)}</summary>` with each earlier version (not the current one) as `<div class="text"><p class="prosa">…</p></div>`, escaped like the existing prose;
  - when the scene id is in `daten["erstentwuerfe"]`, add `<details class="erstentwurf"><summary>{T._TEXT_ERSTE_FASSUNG}</summary>…</details>`.
  - `T._TEXT_ERSTE_FASSUNG` is "Erste Fassung (vor der Pruefung)" / EN "First draft (before the check)". `T._TEXT_FRUEHERE` is "Fruehere Fassungen ({anzahl})" / EN "Earlier versions ({anzahl})".
  - If `web.py` has no `T` yet for these constants, follow how `web._TEXT_GEPLANT`/`TEXT_UNGESCHRIEBEN` are translated.

`_probe_szene_html(s, bekannte)` currently gets only the scene dict. Pass the two extra values in through the scene dict instead of changing the signature: in `textbuch_koerper`, set `s = {**s, "_fassungen": ..., "_erstentwurf": ...}`. This keeps every other caller unchanged.

- [ ] **Step 1: Write the failing tests** — `tests/test_web_skript_tab.py`. Build a DB with a group, scene 1 with prose, two `szenenfassung` rows and `erstentwurf_fassung = 1`. Render via `web_vereint.seite(...)` (copy the setup of `tests/test_web_vereint.py::test_die_drei_panels_stehen_in_einem_dokument`) and via `web.textbuch_html`. Assert:
  - the first-draft text appears inside `panel-textbuch`;
  - "Earlier versions" appears under the EN profile;
  - `' style="'` and `'onclick='` do not appear in the HTML;
  - nothing renders when `erstentwurf_fassung` is NULL;
  - `test_kein_material_in_der_probenansicht` still passes (the run below).
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.** Add minimal CSS for `details.erstentwurf, details.fruehere` to `_CSS_TEXTBUCH` (it is scoped by `scope_css`). Changing an existing CSS constant changes a text-snapshot section. If `tests/test_sprache_bitgleich.py` hashes `_CSS_TEXTBUCH`, put the rules in a **new** constant `_CSS_TEXTBUCH_FASSUNGEN` and append it where `_CSS_TEXTBUCH` is used (both in `textbuch_html` and in `web_vereint.seite`'s `scope_css(...)` call).
- [ ] **Step 4: Run the tests** — the new file plus `tests/test_web*.py tests/test_sprache_bitgleich.py` → PASS.
- [ ] **Step 5: Full suite, then commit**

```bash
git commit -am "Script tab: earlier versions and the pre-check first draft per scene, read-only, CSP-clean"
```

---

## Task 13: Deterministic end-to-end trace, Phase 5 → 7

**Files:**
- Test: `tests/test_teil2_ablauf.py` (new)

This is the acceptance trace Birk will read. No network: a fake KLM, a fake judge and `TelegramAttrappe`, with the real `knoepfe.behandle` and real `erkenner.laufe`.

**Setup:**
- `monkeypatch.setenv(workshop.VARIABLE, "padua-2026")` (as in `tests/test_nachpass.py`'s `padua` fixture);
- `conn`/`einst` from conftest, with `einst = dataclasses.replace(einst, web_url="https://x/theatersoap")`;
- arbeitsstand as in `tests/test_entwurf_ablauf.py:98-108` with `szenen_anzahl = "2"` and two characters (Mother, Mira);
- `phasen.setze(conn, 1, 5, "befehl")`; USA consent state set so it is not due (see Task 8);
- `fanout.waehle_richter` monkeypatched to a `Rundenrichter`.

**`FakeKLM`:**
- `schema(chat_id, system, nutzer, schema, art, modell=None, bei_teil=None)` dispatches on `art`:
  - `"entwurf_uebersicht"` → the TEIL-1 overview dict;
  - `"sprechweise"` → `{"sprechweisen": ["Mother: clipped, impatient", "Mira: short sentences"]}`;
  - the erkenner's art (read `erkenner.erkenne` for the `art` it passes) → pop the next item from `self.erkenner_antworten` (a list of `aenderungen` lists), defaulting to `{"aenderungen": []}` in the exact shape `erkenne` expects.
- `prosa(...)` returns, per `art`:
  - scene-shaped text in the format `szene.schreibe` parses, with a body containing `KOERPER-<n>` (count-based);
  - for `kurzgeschichte` art, two sections in the format `kurzgeschichte.zerlege` parses, bodies `KOERPER-G<n>`;
  - for `stueckpruefung`, a valid six-question answer (copy one from `tests/test_stueckpruefung.py`).
- It records every `(art, nutzer)`.

**Helper `_chat(text)`:** `repo.speichere_nachricht(...)` (use the function `tests/test_erkenner.py` uses to put a group message into `nachricht`), then `erkenner.laufe(klm, tg, conn, einst, 1)` after setting `klm.erkenner_antworten`. Then wait on every lock that may have been taken (`szene._sperre_fuer(1)`, `kurzgeschichte._sperre_fuer(1)` — read the lock accessor's real name — `entwurf._sperre_fuer(1)`, `sprechweise._sperre_fuer(1)`).

**Judge plan:**
- Phase 5 scene 1: `B1` score `[1, 2]` → one revision, then good. This demonstrates "check loop per display, ≤ 2 rounds, logged".
- Everything else: 2.

**The trace, in order, with assertions:**
1. Stage A: `entwurf.starte_uebersicht` → wait → tap "Yes, save". Stage B scene 1 runs through prueflauf → `repo.prueflaeufe` row 1: `phase 5, ziel szene, szene_nummer 1, ueberarbeitungen 1, runden 2`.
2. Tap "Yes, save" (scene 1) → scene 2 → tap "Yes, save" → automatic phase 6.
   - `phasen.aktuelle == 6`.
   - The phase-6 entry ran the whole-story check (a `prueflauf` row with `ziel="geschichte"`, `phase=6`, `fragen="a2,a6,a9,a11"`).
3. Whole-text feedback via chat: `_chat("make the whole story darker")` with erkenner answer `[{"art": "text_ueberarbeiten", "wert": "make the whole story darker"}]`.
   - A `kurzgeschichte` prose call whose `nutzer` contains "darker".
   - A new hint whose text has no `KOERPER-`.
4. `_chat("yes, save it")` with `[{"art": "fassung_abnehmen", "wert": ""}]` → `gesamttext_fixiert_am` set, and the scene-1 check row.
5. Scene 1 changed via chat: `_chat("scene 1: make the mother angrier")` → `text_ueberarbeiten` → a scene prose call with "angrier" and `szene.BISHER_MARKER` in `nutzer`; a newer `szenenfassung` for scene 1.
6. Tap "Yes, save" twice (scenes 1, 2) → exactly one message containing the phase-6 closing wording; `phasen.aktuelle == 7`.
7. Phase 7 entry → one message with "Which form for each number?" and no buttons.
   - `_chat("1 chorus, 2 dialogue")` with `[{"art": "formen_setzen", "wert": "1:chorus|2:dialogue"}]` → `szene.form` = `chor`, `dialog`.
   - The voices message (one message, one line per character) follows automatically.
8. Voices confirmed: tap "Yes, save" → `sprechweisen_fixiert_am` set; scene 1's stage transfer runs (`volltext` set) and its hint arrives.
9. `_chat("make the mother angrier")` with `[{"art": "text_ueberarbeiten", "wert": "make the mother angrier"}]`.
   - A rewrite run: a scene prose call with "angrier"; the scene 1 `szenenfassung` count increases.
   - **No** message in the whole trace starts with "Noted" unless a write happened in the same step. Assert: every message starting with "Noted" in `tg.gesendet` corresponds to step 7 (forms) only.
10. Tap "Yes, save" (scene 1), then again (scene 2) → final check (`prueflauf` row `ziel=geschichte`, `phase=7`), a stueckpruefung prose call (`art == stueckpruefung.ART`), and the "script is complete" message.

**Global assertions at the end:**
- No full text in chat: no `tg.gesendet`/`tg.knoepfe` message contains `KOERPER-`.
- Every `prueflauf` row has `ueberarbeitungen <= 2`.
- Every row has `dauer_ms` not None.

- [ ] **Step 1: Write the test** as specified. It fails until Tasks 6–10 are in, so it should be green right away if they are. If it fails, the failure is a real integration bug: fix it in the module concerned, not in the test.
- [ ] **Step 2: Run** `$PY -m pytest -q -p no:cacheprovider tests/test_teil2_ablauf.py -x -vv` → PASS.
- [ ] **Step 3: Full suite, then commit**

```bash
git add tests/test_teil2_ablauf.py
git commit -m "test: deterministic Phase 5->7 trace (check loop per display, chat feedback, forms, voices, play check, no full text in chat)"
```

---

## Task 14: Simulation can drive phases 5 → 7 in the new flow

**Files:**
- Modify: `simulation/skript.py` (new list `SCHRITTE_PADUA`)
- Modify: `scripts/simulation.py` (`--skript` choices gain `padua`)
- Modify: `simulation/README.md`, and the coverage document that `scripts/simulation_abdeckung.py` checks
- Test: `tests/test_simulation_skript.py` (append), `tests/test_simulation_abdeckung.py`

**Steps of `SCHRITTE_PADUA`:** the `SCHRITTE_TAG2` steps up to and including `"geschichte"` (phase 4), then:

| name | Auftrag for the persona (German, as the existing steps) | `fertig` |
|---|---|---|
| `phase5` | the existing `_phasenschritt(5)` | phase ≥ 5 |
| `entwurf` | "Lest die Uebersicht und sagt 'Yes, save'. Danach kommt Szene fuer Szene -- lest sie im Script-Tab und drueckt jeweils 'Yes, save'." | `phasen.aktuelle >= 6`, `max_nachrichten=12` |
| `gesamt6` | "Die ganze Geschichte steht im Script-Tab. Sagt in einem Satz, wohin sie gehen soll (z. B. 'make it darker'), dann 'Yes, save'." | `arbeitsstand.gesamttext_fixiert_am` set |
| `szenen6` | "Geht Szene fuer Szene durch: bei Szene 1 sagt ihr eine Aenderung, danach jeweils 'Yes, save'." | phase ≥ 7, `max_nachrichten=12` |
| `formen7` | "Antwortet auf 'Which form for each number?' in einer Nachricht, z. B. '1 chorus, 2 dialogue'." | every scene has `form` |
| `sprechweisen7` | "Ihr seht, wie jede Figur spricht. Aendert eine Figur per Chat, dann 'Yes, save'." | `sprechweisen_fixiert_am` set |
| `buehne7` | "Szene fuer Szene: bei Szene 1 sagt 'make the mother angrier' (oder eine passende Figur), danach jeweils 'Yes, save'." | every scene has `fertig_am`, `max_nachrichten=14` |
| `pruefung7` | "Wartet die Stueckpruefung ab." | `repo.letzte_pruefrunde(conn, chat_id) >= 1` (read the real reader name) |
| `stand` | the existing `/stand` step | as existing |

- `--skript padua` selects `SCHRITTE_PADUA`. `auto` stays as it is.
- Add `skript.py` helpers for the `fertig` checks as module functions with names (the coverage script reads `schritt.fertig.__name__`).

- [ ] **Step 1: Write the failing tests:** `SCHRITTE_PADUA` names are unique; it contains `gesamt6`, `formen7`, `buehne7`; `scripts.simulation` parses `--skript padua`; the coverage script accepts the new list (follow how `SCHRITTE_TAG2` is registered there).
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement**, and document in `simulation/README.md` how to run it.
- [ ] **Step 4: Run** `$PY -m pytest -q -p no:cacheprovider tests/test_simulation*.py` → PASS, and `$PY -m scripts.simulation_abdeckung` (free, no model) → exit 0.
- [ ] **Step 5: Full suite, then commit**

```bash
git commit -am "simulation: --skript padua drives phases 5->7 in the new flow (no paid run)"
```

The command for Birk (paid, not run here):

```
set -a; . ./betrieb/gruppe1.env; set +a
IT_WORKSHOP=padua-2026 $PY -m scripts.simulation --set 1 --seed 7 --skript padua --bericht
```

---

## Task 15: Documentation — AGENTS.md, README.md

**Files:** `AGENTS.md`, `README.md`, `docs/superpowers/plans/2026-10-03-padua-phasen-teil2.md` (record in-execution corrections at the end, as TEIL 1 did)

- [ ] **Step 1: AGENTS.md.**
  - Module table: three rows (`prueflauf.py`, `ueberarbeitung.py`, `sprechweise.py`) in the existing style.
  - Modulkarte, "Fachlogik": add the three.
  - "Wo man anfängt": two rows: "Warum hat sich der Text vor der Anzeige geändert?" → `prueflauf.pruefe_szene` → `schleife.schliesse` → Tabelle `prueflauf`; "Wo steht Phase 6/7 gerade?" → `ueberarbeitung.weiter_6`/`weiter_7` → `aktuelle_szene`.
  - New bullet in "Bindende Entwurfsentscheidungen" (≤ 40 lines): **"Prüflauf vor jeder Anzeige, Phasen 6/7 für Padua (03.10.2026, Padua Phasen TEIL 2)"**. It covers:
    - Birk's decisions in one sentence each (≤ 2 rounds, abort keeps the better version via `behalte_bessere`, quote guard, language pass, ≤ 3 lines, "Show first draft" via `szene.erstentwurf_fassung`);
    - why the writers got `zeigen=False` (both used to post before any check could run);
    - the question subsets per object;
    - "Formregeln" = A10 from phase 7 (`A10_FORM_AB_PHASE`);
    - the A10 parameter correction "in both directions";
    - the five arts in `PHASEN_SPEZIFISCHE_ARTEN` with `PROFILSCHALTER_DER_ARTEN` (EN prompt only; Dortmund's schema unchanged);
    - the Noted guard;
    - known limits (below);
    - the measurement: table `prueflauf`, columns `runden`, `auftraege_je_runde`, `zweite_runde_mit_auftraegen`, `dauer_ms` — the basis for revisiting `RUNDEN_MAX`.
  - "Was bewusst fehlt": the German phase prompts 6/7 still carry B3 and "hook" (Dortmund byte-identity; needs Birk's wording); `PARAMETER` (checklist) for phases 6/7 is not profile-overridable and still counts stage texts in phase 6; `schaerfung_entscheidung "none"` limits if any (Task 10).
- [ ] **Step 2: README.md.** Replace the phase 6/7 bullets (`README.md:64-71`) and anything outdated around them (e.g. "the bot writes the whole story again in one pass … redoing that work"). Keep the cothinker tone. New text:
  - phase 6: the existing story is checked and read in the Script tab, approved as a whole, then scene by scene;
  - phase 7: forms by number in one answer, ways of speaking per character, scene-by-scene transfer, the play check at the end;
  - one paragraph "Checked before you read it" (the loop, ≤ 2 rounds, better version stays, quotes protected, "Show first draft");
  - one sentence that this is Padua's profile (`[prueflauf]`, `[ueberarbeitung]`).
- [ ] **Step 3: Run** the full suite (docs tests such as `tests/test_simulation_abdeckung.py` check doc claims), then commit:

```bash
git commit -am "docs: AGENTS.md check loop + phases 6/7 for Padua; README for the new phase 6/7 reality"
```

---

## Task 16: Final verification and whole-branch review

- [ ] `$PY -m pytest -q -p no:cacheprovider` → record the summary line; compare it with the baseline (5969 passed, 4 skipped).
- [ ] `$PY -m pytest -q -p no:cacheprovider tests/test_profil_bitgleich.py tests/test_sprache_bitgleich.py` → green; `git diff 8019f8e^ -- interview_theater/prompts workshop/dortmund-2026 docs/prompt-audit/schnappschuss-vor-profilumbau.txt docs/prompt-audit/schnappschuss-vor-sprache-a1.txt docs/prompt-audit/texte-vor-sprache-a1.txt` shows **no TEIL-2 commit** touching them (`git log b8650f5..HEAD -- <those paths>` is empty).
- [ ] `$PY -m scripts.pruefe_profil dortmund-2026` and `padua-2026` → exit 0.
- [ ] A whole-branch review (`b8650f5..HEAD`) against this plan and Birk's decisions. List every Critical/Important finding with fixed/open status.
- [ ] Final report: changed files, SHAs, the pytest command and summary line, the baseline, the simulation command, the review findings, and the open questions verbatim (German B3/hook, plus anything that came up).
