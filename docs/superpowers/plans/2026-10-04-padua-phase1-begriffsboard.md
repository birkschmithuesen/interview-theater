# Padua Phase 1: laufend mithören + Begriffsboard im CoThinker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Kanban: Plan-Karte t_508887d6, Ausführung auf Karte t_4517d4ad, Branch `wt/t_4517d4ad`, **in diesem Worktree**.

**Goal:** Im Padua-Profil speist die Hintergrund-Diskussion der Phase 1 („Start listening" … „Discussion done") nach qualifizierenden Segmenten ein laufendes Begriffsboard (dieselbe Auslöser-Mechanik wie der Brainstorm in Phase 4), das live im CoThinker-Tab steht; bei „Discussion done" schlägt der Bot die Top 5 als Abkürzung vor, und beim Speichern der Begriffe wandern Begründung/Doppelbedeutung je Begriff nach `arbeitsstand.begriffe_detail` und von dort in Phase 2 (inkl. des isolierten `fragen_ki`-Aufrufs) und Phase 4+.

**Architecture:** Ein neues Fachmodul `interview_theater/begriffsboard.py` trägt alles: reine Funktionen (Validierung, Sortierung, Top 5, Detail-Abgleich, Prompt-Zeilen), ein eigenes Sperren-Register, die Auslöser-Entscheidung (`brainstorm.soll_reagieren` unverändert, eigene Zähler über `aufnahme.diskussion = 1`) und den Modelllauf im eigenen Thread, der **kein `tg` kennt** und deshalb strukturell keine Chatzeile schreiben kann. `aufnahme._diskussion_abschliessen` ruft je Segment `begriffsboard.nach_segment`; auf `schnittgrund == 'ende'` läuft ggf. ein Schlusslauf und danach der Top-5-Vorschlag mit EINEM Knopf. Speicherung in einer neuen, nur anhängenden Tabelle `begriffsboard` (SQL nur in `repo.py`/`db.py`, read-only in `web_daten.py`).

**Tech Stack:** Python 3.11, Standardbibliothek, SQLite, pytest, Playwright (nur `tests/e2e`, eigenes venv).

## Global Constraints

Bindende Entscheidungen (Birk 15:15 + Architekt) — **nicht neu verhandeln**:

- **Einheitlich automatisch:** Phase 1 und Phase 4 laufen beim Mithören gleich (Pausenschnitt, min/max wie Brainstorm, Start / Pause / Fortsetzen / „Discussion done"). Kein manueller Bogen-Modus.
- **D1 Auslöser:** `brainstorm.soll_reagieren` **unverändert** (dieselben Schwellen, dieselben Env-Variablen `IT_BRAINSTORM_MIN_ZEICHEN`, `IT_BRAINSTORM_MIN_ABSTAND_S`, `IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS`). Eigene Zähler (unreagierte Zeichen seit dem letzten Boardlauf, Sekunden seit dem letzten Boardlauf, Schnittgrund des jüngsten Diskussionssegments) **nur über `aufnahme`-Zeilen mit `diskussion = 1`**. Eigenes Sperren-Register in `begriffsboard.py` (Form `versuche_start`/`beende`/`laeuft` wie `brainstorm.py`). Markierung „was das Board gesehen hat" = höchste Diskussions-`aufnahme.id`, gelesen **vor** dem Lauf, gespeichert in der Boardzeile (`bis_aufnahme_id`). Ein abgewiesener/gescheiterter Lauf verliert nichts, die Zeichen laufen weiter auf. Einhängepunkt `aufnahme._diskussion_abschliessen`, dessen Docstring („ruft nie `soll_reagieren`") neu geschrieben wird.
- **D2 Modellaufruf** im eigenen Thread (Zusage 2) über `modellwahl.aufruf_schema(..., ueber_claude=modellwahl.konversation_ueber_claude(e, conn, chat_id))`, sonst Kimi. Schema-JSON mit `additionalProperties: false` und vollständigen `required`-Listen; `doppelbedeutung`/`zitat` sind Pflicht-Strings, die leer sein dürfen. Neue Prompt-Datei `interview_theater/prompts/begriffsboard.md` + `interview_theater/sprachen/en/prompts/begriffsboard.md`. **Nur Negativbeispiele, keine Positivbeispiele.** Transkriptbudget wie `buehnenkarte` (Env-überschreibbare Zeichengrenze `IT_BEGRIFFSBOARD_TRANSKRIPT_ZEICHEN`, Vorgabe 200 000, Ältestes zuerst weg, Vorfall).
- **D3 Validierung im Code, nicht im Prompt:** jede Zeile raus, deren `begriff` nach `zitat.normalisiere` + `casefold` nicht als Teilstring im zusammengefügten Phase-1-Transkript steht; `zitat` bleibt nur, wenn `zitat.pruefe(zitat, transkript)`, sonst `""` (Begründung bleibt); `zustimmung` auf −2..2 geklemmt, `nennungen` ganzzahlig ≥ 0, unbekannter `status` → `"kandidat"`; Dubletten nach normalisiertem Begriff raus; Liste gedeckelt (30). **Mutant:** ohne Transkriptprüfung muss ein Test fehlschlagen.
- **D4 Sortierung = EINE reine Funktion** (Web-Rendering UND Top-5-Vorschlag): favorit > kandidat > verworfen, dann `zustimmung` absteigend, dann `nennungen` absteigend, dann Begriff. Top 5 = die ersten fünf nicht-`verworfen`.
- **D5 Keine Chatzeile während des Mithörens:** der Boardlauf ruft nie `tg.sende`/`sende_mit_knoepfen`; das bestehende `_web_sprachblase`-Update bleibt. **Mutant:** ein `sende` im Boardlauf muss einen Test rot machen.
- **D6 „Discussion done"** (`schnittgrund == 'ende'`): Schlusslauf, wenn `soll_reagieren(..., ist_abschluss=True)`; der Vorschlag kommt **nach** dessen Ende (Erfolg, leer oder Fehler → dann das jeweils aktuelle Board); ist kein Schlusslauf nötig, sofort. Die Gesamtverdichtung (`diskussion.starte`) startet auf `'ende'` wie heute, unabhängig vom Board. Der Vorschlag ersetzt `aufnahme._TEXT_DISKUSSION_FERTIG_BEGRIFFE`, sobald das Board ≥ 1 nicht verworfenen Begriff hat: nummerierte Liste (≤ 5), EIN Knopf „Take these" (neue Knopf-ART, Wert = Begriffsliste in der Tabelle `knopf`, `callback_data` `k:<id>` < 64 Bytes, idempotent über `repo.beanspruche_knopf`, kein Modellaufruf im Handler) und der Satz, dass sie auch eigene fünf tippen können. Leeres Board → heutiger Text unverändert. Keine Toggle-Knöpfe.
- **D7 `begriffe_detail`:** neue additive Spalte `arbeitsstand.begriffe_detail` (TEXT, JSON `[{begriff, begruendung, zitat, doppelbedeutung}]`). Geschrieben von EINEM Helfer `begriffsboard.schreibe_detail(conn, chat_id, begriffe_text)`, gerufen auf JEDEM Weg, der `arbeitsstand.begriffe` schreibt (per AST-Test festgenagelt, Aufgabe 5); Abgleich über normalisierten casefold-Begriff; Begriffe ohne Boardzeile → leere Felder. Wird `begriffe` geleert, wird auch `begriffe_detail` geleert. Die Leseseite existiert und muss grün bleiben (`roadmap.begriffe_detail`, `tests/test_roadmap_werkbank.py`, `tests/test_web_daten_werkbank.py`, `tests/test_werkbank_web.py`; das Zitat geht nie auf die Webseite). Ruecknahme verfolgt die neue Spalte automatisch (`ruecknahme.spalten` liest `db.SCHEMA`); `begriffsboard` kommt in `db.TABELLEN_MIT_CHAT_ID` und bleibt **außerhalb** von `ruecknahme.VERFOLGT` (von `wende_an` nie geschrieben).
- **D8 Weitergabe:** `kontext.baue` bekommt einen datengetriebenen Block (weg, solange `begriffe_detail` leer ist) in Phase 2 und Phasen ≥ 4 (nicht 3): Begriff + Begründung + Doppelbedeutung, **kein Zitat**. `fragen_ki._nutzertext` bekommt `begriffe_detail` als zusätzliches Argument (weiterhin kein `conn`/`chat_id`, nie die eigenen Fragen der Gruppe); `starte()` liest es aus dem Arbeitsstand. Dortmund/Vorgabe bleibt byte-gleich (`tests/test_profil_bitgleich.py`).
- **D9 CoThinker-Tab in Phase 1:** der Early-Return `if (!istPhase4())` in `ladeBuehne` (und die drei anderen Phase-4-Weichen) erlaubt auch Phase 1; `teil/buehne` rendert in Phase 1 das Board, in Phase 4 die bestehenden Karten. Lesen über eine neue read-only `web_daten`-Funktion. Nur funktionales Markup mit `data-*`, `<details>` für Begründung/Doppelbedeutung, kein `style=`, kein `on…=` (CSP), keine Gestaltung. Nur hinter `workshop.diskussion_aktiv()`.
- **D10 Onboarding:** „Lay one phone in the middle -- it listens. Open the CoThinker tab on a second phone: the terms you mention appear there." als deterministischer Bot-Text (deutsche Python-Konstante + englischer Eintrag in `sprachen/en/texte.toml`, gleiche Modultabelle), nur bei aktiver Diskussion.
- **D11 AGENTS.md:** Modultabelle, „Wo man anfängt", Phase-1-Beschreibung, Ungemessen-Liste.
- AGENTS.md-Zusagen: SQL nur in `repo.py`/`db.py` (Ausnahme `web_daten.py` read-only); Migration nur additiv (`db._migriere_fehlende_spalten` liest `db.SCHEMA`, nichts von Hand); drei Knopf-Zusagen; Prompts nur Negativbeispiele; Platzhalter in Deutsch und Englisch identisch (`sprache.platzhalter`, K3).
- Code-Bezeichner deutsch wie im Repo, Kommentardichte wie im umgebenden Code. Nur erfundenes Material in Tests. Nie `.env`/`betrieb/` lesen.
- Branch `wt/t_4517d4ad`, **kein Merge, kein Push** (ein Push auf origin/main ist ≤ 5 min später LIVE). Ein Commit je Aufgabe, nur die genannten Dateien `git add`-en (nie `git add -A`; `.cc-*`/`.superpowers-*` bleiben ungetrackt). Commit-Nachrichten enden mit
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Testbefehle immer abwarten (nicht in den Hintergrund schicken).

**Abkürzungen in diesem Plan:**

```bash
PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
E2E=/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python   # Playwright-venv (tests/e2e/README.md)
```

**Bewusste, belegte Abweichungen von der Kartenformulierung:**

1. *Ausgabe JSON ist eine Liste* → das Schema hat ein Objekt mit dem Schlüssel `board` als Wurzel (`{"board": [...]}`). Der erzwungene Schema-Modus verlangt ein Objekt (Kommentar an `diskussion.SCHEMA`). Der Schlüssel heißt bewusst nicht `begriffe`: `scripts/pruefe_sprache.py` führt „begriffe" in `UI_WOERTER`, der englische Prompt würde damit `test_padua_ist_frei_von_deutsch` reißen. Die Zeilenschlüssel bleiben exakt die der Karte (`begriff`, `nennungen`, `zustimmung`, `begruendung`, `zitat`, `doppelbedeutung`, `status`) — keiner davon steht in den Prüferlisten.
2. *e2e „Segment → Board-Eintrag im CoThinker-Panel → Discussion done"*: im Browser **nicht** in dieser Reihenfolge herstellbar. Chromiums `--use-fake-device-for-media-stream` liefert einen Dauerton, der Pausenschnitt feuert nie, alle Segmente tragen `schnittgrund = 'cap'` (Dateikopf `tests/e2e/test_web_diskussion_e2e.py`, Konstante `VAD_MAX_MS`), und D1 lässt laufend nur nach `'pause'` aus. Der e2e-Lauf zeigt deshalb: Segment → „Discussion done" → Schlusslauf → Board-Eintrag im CoThinker-Panel → Top-5-Vorschlag mit Knopf. Der Zwischenlauf nach einem Pausenschnitt wird in Aufgabe 4 über den echten `aufnahme`-Pfad unit-getestet.
3. *Onboarding „beim Start"*: der Knopf „Start listening" ist rein clientseitig (`web_daten`: `diskussion_knopf = phase == 1 and diskussion_aktiv()`), der Bot erfährt vom Start erst mit dem ersten Segment. Der Text geht deshalb dorthin, wo der Bot den Knopf ankündigt: an den **Eintritt in Phase 1** (`knoepfe/stationen.eintritt_in_phase`) **und** direkt hinter die **erste Antwort einer neuen Gruppe** (`ablauf.antworte`) — der Erstkontakt läuft nicht über `eintritt_in_phase` (Aufrufer gegrept: `entwurf`, `erkenner`, `ueberarbeitung`, `befehle`, `stationen`, `wirkung`, `scripts/pruefe_sprache`), und eine frische Padua-Gruppe sähe den Satz sonst nie. Zwei Aufrufstellen, EINE Funktion `begriffsboard.sende_einstieg`.

---

## Dateiübersicht

| Datei | Aufgabe | Was |
|---|---|---|
| `interview_theater/db.py` | 1 | Tabelle `begriffsboard`, Spalte `arbeitsstand.begriffe_detail`, `TABELLEN_MIT_CHAT_ID` |
| `interview_theater/repo.py` | 1 | `lege_begriffsboard_an`, `letztes_begriffsboard`, `begriffsboard_stand`, `hoechste_diskussion_aufnahme_id`, `_ARBEITSSTAND_FELDER += begriffe_detail` |
| `interview_theater/begriffsboard.py` (neu) | 2, 3, 4, 5, 6, 9 | das ganze Board |
| `interview_theater/prompts/begriffsboard.md` (neu), `interview_theater/sprachen/en/prompts/begriffsboard.md` (neu) | 3 | Prompt DE/EN |
| `interview_theater/sprachen/en/texte.toml` | 2, 6, 7, 8 | Tabellen `["begriffsboard"]` (neu), Einträge in `["knoepfe.texte"]`, `["kontext"]`, `["fragen_ki"]`, `["web"]` |
| `interview_theater/aufnahme.py` | 4 | `_diskussion_abschliessen`, Docstrings |
| `interview_theater/diskussion.py` | 4 | Moduldocstring (nicht mehr „ohne CoThinker-Karte") |
| `interview_theater/erkenner.py`, `interview_theater/knoepfe/basis.py` | 5 | Haken `schreibe_detail` |
| `interview_theater/knoepfe/texte.py`, `knoepfe/basis.py`, `knoepfe/wirkung.py` | 6 | ART, Vorschlag, Handler |
| `interview_theater/kontext.py`, `interview_theater/fragen_ki.py` | 7 | Weitergabe |
| `interview_theater/web_daten.py`, `web.py`, `web_vereint.py` | 8 | CoThinker in Phase 1 |
| `interview_theater/knoepfe/stationen.py`, `interview_theater/ablauf.py` | 9 | Onboarding |
| `tests/e2e/test_web_diskussion_e2e.py` | 10 | Browserlauf |
| `AGENTS.md` | 11 | Doku |

Neue Testdateien: `tests/test_repo_begriffsboard.py`, `tests/test_begriffsboard.py`, `tests/test_begriffsboard_lauf.py`, `tests/test_begriffsboard_mithoeren.py`, `tests/test_begriffe_detail_wege.py`, `tests/test_begriffsboard_vorschlag.py`, `tests/test_begriffe_detail_weitergabe.py`, `tests/test_begriffsboard_web.py`, `tests/test_begriffsboard_einstieg.py`.

**Import-Regel für `begriffsboard`:** `begriffsboard.py` importiert oben `anweisungen, begriffe, brainstorm, modellwahl, repo, sprache, workshop, zitat` (wie `diskussion.py`). `modellwahl` zieht `knoepfe.texte` und damit das Paket `knoepfe` nach — deshalb importieren **alle** Aufrufer (`aufnahme`, `erkenner`, `knoepfe/*`, `kontext`, `web_daten`, `web`, `ablauf`) `begriffsboard` **lokal in der Funktion** (`from interview_theater import begriffsboard`), die Bauart des Repos gegen Zyklen. Einzige Ausnahme: `fragen_ki.py` (hat dieselben Abhängigkeiten schon oben).

---

### Task 1: Ablage — Tabelle `begriffsboard`, Spalte `begriffe_detail`, Repo-Funktionen

**Files:**
- Modify: `interview_theater/db.py` (SCHEMA: Spalte in `arbeitsstand` vor `geaendert_am` ~Z. 524; neue Tabelle direkt hinter `diskussion_verdichtung` ~Z. 733; `TABELLEN_MIT_CHAT_ID` ~Z. 1210)
- Modify: `interview_theater/repo.py` (`_ARBEITSSTAND_FELDER` ~Z. 1786–1848; neue Funktionen direkt hinter `diskussion_verdichtung_text` ~Z. 2172)
- Test: `tests/test_repo_begriffsboard.py` (neu)

**Interfaces:**
- Produces:
  - `repo.lege_begriffsboard_an(conn, chat_id: int, eintraege_json: str, modell: str | None, bis_aufnahme_id: int) -> int`
  - `repo.letztes_begriffsboard(conn, chat_id: int) -> sqlite3.Row | None` (Spalten `id, chat_id, json, erstellt_am, modell, bis_aufnahme_id`)
  - `repo.begriffsboard_stand(conn, chat_id: int) -> dict` mit `unreagierte_zeichen: int`, `sekunden_seit_letztem_lauf: float | None`, `letzter_schnittgrund: str | None`
  - `repo.hoechste_diskussion_aufnahme_id(conn, chat_id: int) -> int`
  - `repo.setze_arbeitsstand(conn, chat_id, "begriffe_detail", wert)` ist erlaubt

- [ ] **Step 1: Failing tests schreiben** — `tests/test_repo_begriffsboard.py`:

```python
"""Karte t_4517d4ad, Aufgabe 1: die Ablage des Begriffsboards."""

import json

import pytest

from interview_theater import db, repo

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def _segment(conn, message_id, text, schnittgrund=None, diskussion=True, status="fertig"):
    aid = repo.lege_aufnahme_an(
        conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
        diskussion=diskussion, schnittgrund=schnittgrund,
    )
    repo.setze_transkript(conn, aid, text)
    repo.setze_status(conn, aid, status)
    return aid


def test_tabelle_und_spalte_existieren(conn):
    spalten = {z[1] for z in conn.execute("PRAGMA table_info(begriffsboard)")}
    assert spalten == {"id", "chat_id", "json", "erstellt_am", "modell", "bis_aufnahme_id"}
    stand = {z[1] for z in conn.execute("PRAGMA table_info(arbeitsstand)")}
    assert "begriffe_detail" in stand


def test_loeschzusage_kennt_die_tabelle():
    assert "begriffsboard" in db.TABELLEN_MIT_CHAT_ID


def test_migration_ergaenzt_die_spalte_additiv(conn):
    """Eine bestehende Datenbank ohne die Spalte bekommt sie ueber
    ``db._migriere_fehlende_spalten`` (liest ``db.SCHEMA``) -- nachgestellt,
    indem die Spaltenliste vor der Migration geprueft wird."""
    soll = dict(db._tabellenspalten_aus_schema()["arbeitsstand"])
    assert soll["begriffe_detail"] == "TEXT"
    assert "begriffsboard" in db._tabellenspalten_aus_schema()


def test_letzter_stand_gilt_historie_bleibt(conn):
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps([{"begriff": "A"}]), "sovereign", 3)
    zweite = repo.lege_begriffsboard_an(conn, CHAT, json.dumps([{"begriff": "B"}]), "claude", 5)
    zeile = repo.letztes_begriffsboard(conn, CHAT)
    assert zeile["id"] == zweite
    assert json.loads(zeile["json"]) == [{"begriff": "B"}]
    assert zeile["bis_aufnahme_id"] == 5
    assert conn.execute("SELECT COUNT(*) FROM begriffsboard").fetchone()[0] == 2


def test_ohne_board_kein_letzter_stand(conn):
    assert repo.letztes_begriffsboard(conn, CHAT) is None


def test_stand_zaehlt_nur_diskussionssegmente_nach_der_markierung(conn):
    a = _segment(conn, 10, "x" * 100, "pause")
    _segment(conn, 11, "y" * 40, "cap", diskussion=False)   # Brainstorm/kurz zaehlt nie
    repo.lege_begriffsboard_an(conn, CHAT, "[]", "sovereign", a)
    _segment(conn, 12, "z" * 30, "pause")
    stand = repo.begriffsboard_stand(conn, CHAT)
    assert stand["unreagierte_zeichen"] == 30
    assert stand["letzter_schnittgrund"] == "pause"
    assert stand["sekunden_seit_letztem_lauf"] is not None
    assert stand["sekunden_seit_letztem_lauf"] >= 0


def test_stand_vor_dem_ersten_lauf(conn):
    _segment(conn, 10, "x" * 100, "cap")
    stand = repo.begriffsboard_stand(conn, CHAT)
    assert stand == {
        "unreagierte_zeichen": 100,
        "sekunden_seit_letztem_lauf": None,
        "letzter_schnittgrund": "cap",
    }


def test_hoechste_diskussion_aufnahme_id(conn):
    assert repo.hoechste_diskussion_aufnahme_id(conn, CHAT) == 0
    _segment(conn, 10, "a")
    b = _segment(conn, 11, "b")
    _segment(conn, 12, "c", diskussion=False)
    assert repo.hoechste_diskussion_aufnahme_id(conn, CHAT) == b


def test_begriffe_detail_ist_ein_erlaubtes_feld(conn):
    repo.setze_arbeitsstand(conn, CHAT, "begriffe_detail", "[]")
    assert repo.hole_arbeitsstand(conn, CHAT)["begriffe_detail"] == "[]"
```

- [ ] **Step 2: Rot laufen lassen**

Run: `$PY -m pytest tests/test_repo_begriffsboard.py -q`
Expected: FAIL (`no such table: begriffsboard`, `AttributeError: ... lege_begriffsboard_an`).

- [ ] **Step 3: Schema** — in `db.SCHEMA`, Tabelle `arbeitsstand`, direkt vor `geaendert_am           TEXT`:

```sql
  -- Je Begriff aus ``begriffe`` die Zeile des Begriffsboards (Karte
  -- t_4517d4ad, 04.10.2026): JSON ``[{begriff, begruendung, zitat,
  -- doppelbedeutung}]``. Geschrieben allein von
  -- ``begriffsboard.schreibe_detail``, auf jedem Weg, der ``begriffe``
  -- schreibt; geleert, wenn ``begriffe`` geleert wird. Das Zitat geht nie
  -- auf die Webseite (``roadmap.begriffe_detail``).
  begriffe_detail             TEXT,
```

Hinter dem `CREATE TABLE IF NOT EXISTS diskussion_verdichtung (...);`-Block:

```sql
-- Das Begriffsboard der Phase 1 (Padua, Karte t_4517d4ad, 04.10.2026,
-- ``interview_theater/begriffsboard.py``).
--
-- Nur anhaengen (wie ``buehnenkarte``): jeder Lauf legt eine neue Zeile an,
-- der LETZTE Stand gilt, die Historie bleibt. ``json`` ist die validierte
-- Liste ``[{begriff, nennungen, zustimmung, begruendung, zitat,
-- doppelbedeutung, status}]``. ``bis_aufnahme_id`` ist die hoechste
-- Diskussions-``aufnahme.id``, die VOR dem Lauf bekannt war -- die Markierung
-- fuer ``repo.begriffsboard_stand``. Kein Chattext steht hier.
CREATE TABLE IF NOT EXISTS begriffsboard (
  id               INTEGER PRIMARY KEY,
  chat_id          INTEGER NOT NULL,
  json             TEXT NOT NULL,
  erstellt_am      TEXT NOT NULL,
  -- 'claude' oder 'sovereign', wie ``diskussion_verdichtung.modell``.
  modell           TEXT,
  bis_aufnahme_id  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_begriffsboard_chat ON begriffsboard(chat_id, id);
```

In `TABELLEN_MIT_CHAT_ID` hinter `"diskussion_verdichtung",`: `"begriffsboard",`.

- [ ] **Step 4: Repo** — in `_ARBEITSSTAND_FELDER` am Ende (nach `"gesamttext_fixiert_am", "sprechweisen_fixiert_am",`):

```python
    # Das Begriffsboard je gespeichertem Begriff (Karte t_4517d4ad):
    # derselbe eine Schreibweg, gesetzt allein von
    # ``begriffsboard.schreibe_detail``.
    "begriffe_detail",
```

Hinter `diskussion_verdichtung_text`:

```python
@_gesperrt
def lege_begriffsboard_an(
    conn: sqlite3.Connection, chat_id: int, eintraege_json: str,
    modell: str | None, bis_aufnahme_id: int,
) -> int:
    """Haengt einen Stand des Begriffsboards an (nur anhaengen, der letzte
    gilt -- Tabellenkommentar in db.py)."""
    cur = conn.execute(
        "INSERT INTO begriffsboard (chat_id, json, erstellt_am, modell, bis_aufnahme_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (chat_id, eintraege_json, _jetzt(), modell, bis_aufnahme_id),
    )
    conn.commit()
    return int(cur.lastrowid)


@_gesperrt
def letztes_begriffsboard(conn: sqlite3.Connection, chat_id: int) -> sqlite3.Row | None:
    """Der geltende (juengste) Stand des Begriffsboards, oder None."""
    return conn.execute(
        "SELECT * FROM begriffsboard WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()


@_gesperrt
def hoechste_diskussion_aufnahme_id(conn: sqlite3.Connection, chat_id: int) -> int:
    """Die hoechste ``aufnahme.id`` eines Diskussionssegments, oder 0 --
    das Gegenstueck zu ``hoechste_brainstorm_aufnahme_id``."""
    zeile = conn.execute(
        "SELECT MAX(id) FROM aufnahme WHERE chat_id = ? AND diskussion = 1 "
        "AND entfernt_am IS NULL", (chat_id,),
    ).fetchone()
    return int(zeile[0]) if zeile and zeile[0] is not None else 0


@_gesperrt
def begriffsboard_stand(conn: sqlite3.Connection, chat_id: int) -> dict:
    """Die drei Zahlen fuer ``brainstorm.soll_reagieren`` -- wie
    ``brainstorm_stand``, aber ueber Diskussionssegmente (Phase 1) und mit
    der Markierung aus der juengsten Boardzeile statt aus ``arbeitsstand``
    (Karte t_4517d4ad, D1)."""
    board = conn.execute(
        "SELECT erstellt_am, bis_aufnahme_id FROM begriffsboard "
        "WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (chat_id,),
    ).fetchone()
    markierung = (board["bis_aufnahme_id"] or 0) if board else 0
    zeichen = conn.execute(
        "SELECT COALESCE(SUM(LENGTH(transkript)), 0) FROM aufnahme "
        "WHERE chat_id = ? AND diskussion = 1 AND entfernt_am IS NULL "
        "AND transkript IS NOT NULL AND id > ?",
        (chat_id, markierung),
    ).fetchone()[0]
    letzter = conn.execute(
        "SELECT schnittgrund FROM aufnahme WHERE chat_id = ? AND diskussion = 1 "
        "AND entfernt_am IS NULL ORDER BY id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()
    sekunden = None
    if board and board["erstellt_am"]:
        sekunden = max(
            0.0,
            (datetime.now(timezone.utc) - datetime.fromisoformat(board["erstellt_am"]))
            .total_seconds(),
        )
    return {
        "unreagierte_zeichen": int(zeichen),
        "sekunden_seit_letztem_lauf": sekunden,
        "letzter_schnittgrund": letzter["schnittgrund"] if letzter else None,
    }
```

ANNAHME: `repo._jetzt()` liefert ein ISO-Format, das `datetime.fromisoformat` mit Zeitzone liest (so nutzt es `brainstorm_stand` heute mit `brainstorm_reaktion_am`). Prüfen: `test_stand_zaehlt_nur_...` wird grün.

- [ ] **Step 5: Grün + Nachbarn**

Run: `$PY -m pytest tests/test_repo_begriffsboard.py tests/test_db.py tests/test_ruecknahme.py tests/test_ruecknahme_rundreise.py tests/test_roadmap_werkbank.py tests/test_web_daten_werkbank.py tests/test_werkbank_web.py -q`
Expected: alle PASS. (`tests/test_db.py:32` vergleicht alle Tabellen mit `TABELLEN_MIT_CHAT_ID`; `test_web_daten_werkbank.py::test_begriffe_detail_mit_spalte` legt die Spalte nur an, wenn sie fehlt — jetzt existiert sie.)

- [ ] **Step 6: Commit**

```bash
git add interview_theater/db.py interview_theater/repo.py tests/test_repo_begriffsboard.py
git commit -m "Begriffsboard: Tabelle, Spalte begriffe_detail und Repo-Zugriffe (Karte t_4517d4ad, Aufgabe 1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Der reine Kern — Validierung, Sortierung, Top 5, Detail-Abgleich

**Files:**
- Create: `interview_theater/begriffsboard.py`
- Modify: `interview_theater/sprachen/en/texte.toml` (neue Tabelle `["begriffsboard"]`, alphabetisch egal — hinter `["fragen_ki"]`)
- Test: `tests/test_begriffsboard.py` (neu)

**Interfaces:**
- Consumes: `zitat.normalisiere`, `zitat.pruefe`, `begriffe.zerlege`
- Produces (alles rein, keine DB):
  - `begriffsboard.STATUS = ("favorit", "kandidat", "verworfen")`, `HOECHSTENS = 30`, `TOP = 5`
  - `schluessel(text: str | None) -> str`
  - `_steht_im_transkript(begriff: str, transkript: str) -> bool` (die Mutationsstelle)
  - `validiere(roh: object, transkript: str) -> list[dict]`
  - `lies(roh_json: str | None) -> list[dict]` (gespeicherte Zeile → Einträge, defensiv, ohne Transkriptprüfung)
  - `sortiert(eintraege: list[dict]) -> list[dict]`
  - `top(eintraege: list[dict], n: int = TOP) -> list[dict]`
  - `detail_fuer(board: list[dict], begriffe_text: str | None) -> list[dict]` → `[{begriff, begruendung, zitat, doppelbedeutung}]` in der Reihenfolge der Gruppe
  - `detail_zeilen(detail: list[dict]) -> list[str]` (Prompt-Zeilen ohne Zitat; Einträge ohne Begründung UND ohne Doppelbedeutung fallen weg)
  - `T = sprache.Texte(__name__)` mit `_ZEILE_DETAIL`, `_ZEILE_DETAIL_OHNE_GRUND`, `_ZUSATZ_DOPPELBEDEUTUNG`

- [ ] **Step 1: Failing tests** — `tests/test_begriffsboard.py`:

```python
"""Karte t_4517d4ad, Aufgabe 2: der reine Kern des Begriffsboards (D3, D4)."""

import pytest

from interview_theater import begriffsboard

TRANSKRIPT = (
    "Wir reden ueber Heimat. Heimat ist fuer mich, wo meine Oma kocht. "
    "Und Grenze, eine Grenze kann auch im Kopf sein. Mut fehlt uns manchmal."
)


def _zeile(**kw):
    basis = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 1,
             "begruendung": "Kam zweimal vor.", "zitat": "wo meine Oma kocht",
             "doppelbedeutung": "", "status": "kandidat"}
    basis.update(kw)
    return basis


# -- D3: Validierung ---------------------------------------------------------

def _pruefe_erfundener_begriff_fliegt_raus():
    ergebnis = begriffsboard.validiere(
        [_zeile(), _zeile(begriff="Freiheit", zitat="")], TRANSKRIPT,
    )
    assert [e["begriff"] for e in ergebnis] == ["Heimat"]


def test_erfundener_begriff_fliegt_raus():
    _pruefe_erfundener_begriff_fliegt_raus()


def test_mutant_ohne_transkriptpruefung_faellt_durch(monkeypatch):
    """D3-Mutant: wer die Transkriptpruefung entfernt, muss den Test oben rot
    machen -- sonst prueft er nichts."""
    monkeypatch.setattr(begriffsboard, "_steht_im_transkript", lambda begriff, transkript: True)
    with pytest.raises(AssertionError):
        _pruefe_erfundener_begriff_fliegt_raus()


def test_begriff_wird_normalisiert_und_casefold_gefunden():
    ergebnis = begriffsboard.validiere([_zeile(begriff="  heimat ")], TRANSKRIPT)
    assert ergebnis[0]["begriff"] == "heimat"


def test_unbelegtes_zitat_wird_leer_begruendung_bleibt():
    ergebnis = begriffsboard.validiere(
        [_zeile(zitat="Heimat ist alles fuer uns")], TRANSKRIPT,
    )
    assert ergebnis[0]["zitat"] == ""
    assert ergebnis[0]["begruendung"] == "Kam zweimal vor."


def test_belegtes_zitat_bleibt():
    assert begriffsboard.validiere([_zeile()], TRANSKRIPT)[0]["zitat"] == "wo meine Oma kocht"


@pytest.mark.parametrize("roh, erwartet", [(7, 2), (-9, -2), ("1", 1), ("viel", 0), (None, 0)])
def test_zustimmung_wird_geklemmt(roh, erwartet):
    assert begriffsboard.validiere([_zeile(zustimmung=roh)], TRANSKRIPT)[0]["zustimmung"] == erwartet


@pytest.mark.parametrize("roh, erwartet", [(-3, 0), ("4", 4), (2.9, 2), ("x", 0)])
def test_nennungen_ganzzahlig_nicht_negativ(roh, erwartet):
    assert begriffsboard.validiere([_zeile(nennungen=roh)], TRANSKRIPT)[0]["nennungen"] == erwartet


@pytest.mark.parametrize("status, erwartet", [
    ("favorit", "favorit"), ("VERWORFEN", "verworfen"), ("top", "kandidat"), (None, "kandidat"),
])
def test_status(status, erwartet):
    assert begriffsboard.validiere([_zeile(status=status)], TRANSKRIPT)[0]["status"] == erwartet


def test_dubletten_nach_normalisiertem_begriff():
    ergebnis = begriffsboard.validiere(
        [_zeile(), _zeile(begriff="HEIMAT", nennungen=9)], TRANSKRIPT,
    )
    assert len(ergebnis) == 1
    assert ergebnis[0]["nennungen"] == 2


def test_liste_ist_gedeckelt():
    roh = [_zeile(begriff=w) for w in TRANSKRIPT.replace(".", "").replace(",", "").split()]
    assert len(begriffsboard.validiere(roh * 3, TRANSKRIPT)) <= begriffsboard.HOECHSTENS


@pytest.mark.parametrize("roh", [None, "kaputt", {"board": []}, [1, "x", None]])
def test_kaputte_eingaben_geben_leere_liste(roh):
    assert begriffsboard.validiere(roh, TRANSKRIPT) == []


def test_begriff_mit_listentrenner_fliegt_raus():
    """Ein Begriff mit Komma wuerde beim Speichern (``begriffe.zerlege``) in
    zwei zerfallen."""
    assert begriffsboard.validiere([_zeile(begriff="Heimat, Grenze")], TRANSKRIPT) == []


def test_fehlende_felder_werden_aufgefuellt():
    ergebnis = begriffsboard.validiere([{"begriff": "Mut"}], TRANSKRIPT)
    assert ergebnis == [{"begriff": "Mut", "nennungen": 0, "zustimmung": 0,
                         "begruendung": "", "zitat": "", "doppelbedeutung": "",
                         "status": "kandidat"}]


# -- D4: Sortierung und Top 5 -----------------------------------------------

def _e(begriff, status="kandidat", zustimmung=0, nennungen=0):
    return {"begriff": begriff, "status": status, "zustimmung": zustimmung,
            "nennungen": nennungen, "begruendung": "", "zitat": "", "doppelbedeutung": ""}


def test_sortierung_status_dann_zustimmung_dann_nennungen_dann_begriff():
    eintraege = [
        _e("Zebra", "kandidat", 2, 1),
        _e("Apfel", "verworfen", 2, 9),
        _e("Mut", "favorit", -1, 0),
        _e("Birne", "kandidat", 2, 1),
        _e("Kiwi", "kandidat", 2, 5),
        _e("Dorf", "kandidat", 1, 9),
    ]
    assert [e["begriff"] for e in begriffsboard.sortiert(eintraege)] == [
        "Mut", "Kiwi", "Birne", "Zebra", "Dorf", "Apfel",
    ]


def test_top_fuenf_ohne_verworfene():
    eintraege = [_e(f"B{i}", "kandidat", 0, i) for i in range(7)] + [_e("X", "verworfen", 2, 99)]
    oben = begriffsboard.top(eintraege)
    assert len(oben) == 5
    assert all(e["status"] != "verworfen" for e in oben)
    assert [e["begriff"] for e in oben] == ["B6", "B5", "B4", "B3", "B2"]


def test_lies_ist_defensiv():
    assert begriffsboard.lies(None) == []
    assert begriffsboard.lies("{kaputt") == []
    assert begriffsboard.lies('{"a": 1}') == []
    assert begriffsboard.lies('[{"begriff": "Mut", "status": "favorit"}, {"x": 1}]') == [
        {"begriff": "Mut", "nennungen": 0, "zustimmung": 0, "begruendung": "",
         "zitat": "", "doppelbedeutung": "", "status": "favorit"},
    ]


# -- D7: Detail-Abgleich -----------------------------------------------------

def test_detail_fuer_gleicht_casefold_ab_und_haelt_die_reihenfolge_der_gruppe():
    board = [_zeile(begriff="Heimat", doppelbedeutung="Ort und Gefuehl"), _zeile(begriff="Mut")]
    detail = begriffsboard.detail_fuer(board, "mut, HEIMAT, Schule")
    assert [d["begriff"] for d in detail] == ["mut", "HEIMAT", "Schule"]
    assert detail[1] == {"begriff": "HEIMAT", "begruendung": "Kam zweimal vor.",
                         "zitat": "wo meine Oma kocht", "doppelbedeutung": "Ort und Gefuehl"}
    assert detail[2] == {"begriff": "Schule", "begruendung": "", "zitat": "", "doppelbedeutung": ""}


def test_detail_zeilen_ohne_zitat_und_nur_mit_inhalt():
    detail = [
        {"begriff": "Heimat", "begruendung": "Wo die Oma kocht.", "zitat": "ZITAT", "doppelbedeutung": "Ort"},
        {"begriff": "Schule", "begruendung": "", "zitat": "", "doppelbedeutung": ""},
        {"begriff": "Grenze", "begruendung": "", "zitat": "", "doppelbedeutung": "im Kopf"},
    ]
    zeilen = begriffsboard.detail_zeilen(detail)
    assert len(zeilen) == 2
    assert "Heimat" in zeilen[0] and "Wo die Oma kocht." in zeilen[0] and "Ort" in zeilen[0]
    assert "Grenze" in zeilen[1] and "im Kopf" in zeilen[1]
    assert not any("ZITAT" in z for z in zeilen)
    assert not any("Schule" in z for z in zeilen)
```

- [ ] **Step 2: Rot**

Run: `$PY -m pytest tests/test_begriffsboard.py -q`
Expected: FAIL (`ModuleNotFoundError: interview_theater.begriffsboard`).

- [ ] **Step 3: Implementierung** — `interview_theater/begriffsboard.py` (Kopf + reiner Kern; Aufgaben 3–6, 9 hängen später unten an):

```python
"""Das Begriffsboard der Phase 1 (Padua, Karte t_4517d4ad, 04.10.2026).

Birk 15:15: Phase 1 und Phase 4 laufen beim Mithoeren EINHEITLICH
automatisch. Die Hintergrund-Diskussion der Phase 1 bleibt Material -- kein
Gespraechszug, kein Erkenner, keine Chatzeile --, aber nach jedem
qualifizierenden Segment (``brainstorm.soll_reagieren``, unveraendert)
laeuft ein Schema-Aufruf, der ein Board der genannten Begriffe fortschreibt.
Das Board steht im CoThinker-Tab; bei "Discussion done" schlaegt der Bot
seine Top 5 vor, und beim Speichern der Begriffe geht je Begriff die
Boardzeile nach ``arbeitsstand.begriffe_detail``.

**Validiert wird im Code, nicht im Prompt** (``validiere``): ein Begriff,
der nicht im Transkript steht, fliegt raus; ein Zitat, das ``zitat.pruefe``
nicht besteht, wird leer, die Begruendung bleibt.

**Der Boardlauf kennt kein ``tg``** (``starte``/``_lauf_einmal``): er kann
strukturell keine Chatzeile schreiben (D5). Der einzige Chatweg dieses
Moduls ist der Vorschlag nach "Discussion done" (``sende_vorschlag``) und
der Einstiegssatz (``sende_einstieg``)."""

import json
import logging
import os
import threading

from interview_theater import (
    anweisungen, brainstorm, modellwahl, repo, sprache, workshop, zitat,
)
from interview_theater import begriffe as begriffe_modul

log = logging.getLogger(__name__)

ART = "begriffsboard"
STATUS = ("favorit", "kandidat", "verworfen")
_RANG = {"favorit": 0, "kandidat": 1, "verworfen": 2}
#: Obergrenze der Boardzeilen -- ein Board mit mehr Begriffen ist keine
#: Auswahl mehr, sondern ein Protokoll.
HOECHSTENS = 30
TOP = 5
ZUSTIMMUNG_MIN = -2
ZUSTIMMUNG_MAX = 2

#: Die Zeilen fuer Prompts (``kontext``, ``fragen_ki``) -- nie mit Zitat.
_ZEILE_DETAIL = "- {begriff}: {begruendung}"
_ZEILE_DETAIL_OHNE_GRUND = "- {begriff}"
_ZUSATZ_DOPPELBEDEUTUNG = " (Doppelbedeutung: {doppelbedeutung})"

T = sprache.Texte(__name__)


def schluessel(text: str | None) -> str:
    """Der Vergleichsschluessel eines Begriffs: ``zitat.normalisiere`` plus
    casefold -- dieselbe Normalisierung wie beim Zitatschutz, keine zweite."""
    return zitat.normalisiere(text or "").casefold()


def _steht_im_transkript(begriff: str, transkript: str) -> bool:
    k = schluessel(begriff)
    return bool(k) and k in schluessel(transkript)


def _ganzzahl(wert) -> int:
    try:
        return int(wert)
    except (TypeError, ValueError):
        return 0


def _eintrag(zeile) -> dict | None:
    """Eine Zeile in die feste Form -- ohne Transkriptpruefung (die macht
    ``validiere``). None, wenn sie keinen brauchbaren Begriff traegt."""
    if not isinstance(zeile, dict):
        return None
    teile = begriffe_modul.zerlege(" ".join(str(zeile.get("begriff") or "").split()))
    if len(teile) != 1:
        # Leer, oder ein Listentrenner im Begriff: er zerfiele beim
        # Speichern (``begriffe.zerlege``) in zwei.
        return None
    status = str(zeile.get("status") or "").strip().casefold()
    return {
        "begriff": teile[0],
        "nennungen": max(0, _ganzzahl(zeile.get("nennungen"))),
        "zustimmung": min(ZUSTIMMUNG_MAX, max(ZUSTIMMUNG_MIN, _ganzzahl(zeile.get("zustimmung")))),
        "begruendung": str(zeile.get("begruendung") or "").strip(),
        "zitat": str(zeile.get("zitat") or "").strip(),
        "doppelbedeutung": str(zeile.get("doppelbedeutung") or "").strip(),
        "status": status if status in STATUS else "kandidat",
    }


def validiere(roh, transkript: str) -> list[dict]:
    """Die Modellantwort gegen das Transkript (D3). Nichts erfinden: nur
    Begriffe, die im Transkript stehen; Zitate nur woertlich."""
    if not isinstance(roh, list):
        return []
    ergebnis: list[dict] = []
    gesehen: set[str] = set()
    for zeile in roh:
        eintrag = _eintrag(zeile)
        if eintrag is None or not _steht_im_transkript(eintrag["begriff"], transkript):
            continue
        k = schluessel(eintrag["begriff"])
        if k in gesehen:
            continue
        gesehen.add(k)
        if eintrag["zitat"] and not zitat.pruefe(eintrag["zitat"], transkript):
            eintrag["zitat"] = ""
        ergebnis.append(eintrag)
        if len(ergebnis) >= HOECHSTENS:
            break
    return ergebnis


def lies(roh_json: str | None) -> list[dict]:
    """Eine gespeicherte Boardzeile -> Eintraege. Defensiv wie
    ``roadmap.begriffe_detail``: kaputt oder leer ist eine leere Liste."""
    try:
        roh = json.loads(roh_json) if roh_json else []
    except (ValueError, TypeError):
        return []
    if not isinstance(roh, list):
        return []
    return [e for e in (_eintrag(z) for z in roh) if e is not None]


def sortiert(eintraege: list[dict]) -> list[dict]:
    """DIE Sortierung (D4) -- fuer die Webansicht UND den Top-5-Vorschlag."""
    return sorted(eintraege, key=lambda e: (
        _RANG.get(e.get("status"), _RANG["kandidat"]),
        -_ganzzahl(e.get("zustimmung")),
        -_ganzzahl(e.get("nennungen")),
        schluessel(e.get("begriff")),
    ))


def top(eintraege: list[dict], n: int = TOP) -> list[dict]:
    """Die ersten ``n`` nicht verworfenen Eintraege in ``sortiert``-Ordnung."""
    return [e for e in sortiert(eintraege) if e.get("status") != "verworfen"][:n]


def detail_fuer(board: list[dict], begriffe_text: str | None) -> list[dict]:
    """Je gespeichertem Begriff (Reihenfolge und Wortlaut der Gruppe) die
    Boardzeile -- Begriffe ohne Boardzeile mit leeren Feldern (D7)."""
    nach = {schluessel(e["begriff"]): e for e in board}
    ergebnis = []
    for begriff in begriffe_modul.zerlege(begriffe_text):
        zeile = nach.get(schluessel(begriff)) or {}
        ergebnis.append({
            "begriff": begriff,
            "begruendung": zeile.get("begruendung", ""),
            "zitat": zeile.get("zitat", ""),
            "doppelbedeutung": zeile.get("doppelbedeutung", ""),
        })
    return ergebnis


def detail_zeilen(detail: list[dict]) -> list[str]:
    """Die Prompt-Zeilen zu ``begriffe_detail`` (``kontext``, ``fragen_ki``)
    -- NIE mit Zitat. Ein Begriff ohne Begruendung und ohne Doppelbedeutung
    traegt nichts bei und faellt weg; seine Nennung steht ohnehin im
    Arbeitsstand."""
    zeilen = []
    for eintrag in detail:
        grund = (eintrag.get("begruendung") or "").strip()
        doppel = (eintrag.get("doppelbedeutung") or "").strip()
        if not grund and not doppel:
            continue
        zeile = (T._ZEILE_DETAIL.format(begriff=eintrag["begriff"], begruendung=grund)
                 if grund else T._ZEILE_DETAIL_OHNE_GRUND.format(begriff=eintrag["begriff"]))
        if doppel:
            zeile += T._ZUSATZ_DOPPELBEDEUTUNG.format(doppelbedeutung=doppel)
        zeilen.append(zeile)
    return zeilen
```

(Die oberen Imports `anweisungen`, `brainstorm`, `modellwahl`, `repo`, `workshop`, `os`, `threading` werden erst ab Aufgabe 3 benutzt — ein Linter-Hinweis bis dahin ist hinzunehmen; alternativ in Aufgabe 3 nachtragen. Entscheidung der Ausführenden, solange `$PY -m pytest` grün ist.)

`sprachen/en/texte.toml`, neue Tabelle hinter `["fragen_ki"]`:

```toml
["begriffsboard"]
_ZEILE_DETAIL = "- {begriff}: {begruendung}"
_ZEILE_DETAIL_OHNE_GRUND = "- {begriff}"
_ZUSATZ_DOPPELBEDEUTUNG = " (double meaning: {doppelbedeutung})"
```

- [ ] **Step 4: Grün**

Run: `$PY -m pytest tests/test_begriffsboard.py tests/test_sprache.py -q`
Expected: PASS. ANNAHME: `tests/test_sprache.py` ist die Datei, die Tabellen/Platzhalter von `texte.toml` gegen die Python-Konstanten prüft (K3). Falls sie anders heißt: `grep -ln "platzhalter" tests/*.py` und diese Datei laufen lassen.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/begriffsboard.py interview_theater/sprachen/en/texte.toml tests/test_begriffsboard.py
git commit -m "Begriffsboard: reiner Kern -- Validierung gegen das Transkript, Sortierung, Top 5, Detail-Abgleich (Aufgabe 2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Der Boardlauf — Sperre, Auslöser, Prompt, Thread

**Files:**
- Modify: `interview_theater/begriffsboard.py` (anhängen)
- Create: `interview_theater/prompts/begriffsboard.md`, `interview_theater/sprachen/en/prompts/begriffsboard.md`
- Modify: `interview_theater/sprachen/en/texte.toml` (`["begriffsboard"]`: `_TRANSKRIPT_KOPF`, `_BOARD_KOPF`)
- Test: `tests/test_begriffsboard_lauf.py` (neu)

**Interfaces:**
- Consumes: Aufgabe 1 (`repo.begriffsboard_stand`, `repo.lege_begriffsboard_an`, `repo.letztes_begriffsboard`, `repo.hoechste_diskussion_aufnahme_id`, `repo.diskussion_transkript`), Aufgabe 2 (`validiere`, `lies`, `sortiert`)
- Produces:
  - `SCHEMA: dict`, `VORGABE_TRANSKRIPT_ZEICHEN = 200_000`, `transkript_zeichen_grenze() -> int`
  - `_nutzertext(transkript: str, board: list[dict]) -> str` (isoliert: kein `conn`, keine `chat_id`)
  - `aktuelles(conn, chat_id) -> list[dict]`
  - `soll_laufen(conn, chat_id, *, ist_abschluss: bool) -> bool`
  - Sperre: `versuche_start(chat_id) -> bool`, `nimm_oder_merke(chat_id, danach) -> bool`, `beende(chat_id) -> list`, `laeuft(chat_id) -> bool`
  - `_lauf_einmal(conn, klm, e, chat_id: int, bis_id: int) -> None` (kein `tg`!)
  - `starte(conn, klm, e, chat_id: int, *, danach=None) -> bool`

- [ ] **Step 1: Failing tests** — `tests/test_begriffsboard_lauf.py`:

```python
"""Karte t_4517d4ad, Aufgabe 3: Sperre, Ausloeser und Boardlauf (D1, D2)."""

import inspect
import json
import threading
import time

import pytest

from interview_theater import begriffsboard, db, einstellungen, repo, workshop

CHAT = 1
TEXT = "Wir reden ueber Heimat und Grenze. Heimat ist, wo meine Oma kocht."


@pytest.fixture(autouse=True)
def aktiv(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def _segment(conn, message_id, text=TEXT, schnittgrund="pause"):
    aid = repo.lege_aufnahme_an(
        conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
        diskussion=True, schnittgrund=schnittgrund,
    )
    repo.setze_transkript(conn, aid, text)
    repo.setze_status(conn, aid, "fertig")
    return aid


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


class _KLM:
    def __init__(self, board=None, fehler=None, sperre=None):
        self.aufrufe = 0
        self.nutzer = []
        self.system = []
        self.arten = []
        self._board = board if board is not None else []
        self._fehler = fehler
        self._sperre = sperre

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        self.nutzer.append(nutzer)
        self.system.append(system)
        self.arten.append(art)
        if self._sperre is not None:
            self._sperre.wait(5)
        if self._fehler:
            raise self._fehler
        return {"board": self._board}


HEIMAT = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 1, "begruendung": "Oma.",
          "zitat": "wo meine Oma kocht", "doppelbedeutung": "", "status": "favorit"}


# -- Schema -------------------------------------------------------------------

def test_schema_ist_streng():
    s = begriffsboard.SCHEMA
    assert s["additionalProperties"] is False and s["required"] == ["board"]
    zeile = s["properties"]["board"]["items"]
    assert zeile["additionalProperties"] is False
    assert set(zeile["required"]) == set(zeile["properties"]) == {
        "begriff", "nennungen", "zustimmung", "begruendung", "zitat", "doppelbedeutung", "status",
    }


# -- Isolierter Nutzertext ---------------------------------------------------

def test_nutzertext_kennt_weder_conn_noch_chat_id():
    assert list(inspect.signature(begriffsboard._nutzertext).parameters) == ["transkript", "board"]


def test_nutzertext_traegt_transkript_und_board():
    text = begriffsboard._nutzertext("Hallo Heimat", [HEIMAT])
    assert "Hallo Heimat" in text
    assert '"Heimat"' in text


# -- Ausloeser (D1) -----------------------------------------------------------

def test_unter_der_zeichenschwelle_kein_lauf(conn, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "1000")
    _segment(conn, 10, "kurz")
    assert begriffsboard.soll_laufen(conn, CHAT, ist_abschluss=False) is False


def test_ueber_der_schwelle_nach_pause_laeuft(conn, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "10")
    _segment(conn, 10)
    assert begriffsboard.soll_laufen(conn, CHAT, ist_abschluss=False) is True


def test_cap_schnitt_loest_nicht_aus(conn, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "10")
    _segment(conn, 10, schnittgrund="cap")
    assert begriffsboard.soll_laufen(conn, CHAT, ist_abschluss=False) is False


def test_mindestabstand_nach_einem_lauf(conn, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "10")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ABSTAND_S", "3600")
    a = _segment(conn, 10)
    repo.lege_begriffsboard_an(conn, CHAT, "[]", "sovereign", a)
    _segment(conn, 11, "x" * 200)
    assert begriffsboard.soll_laufen(conn, CHAT, ist_abschluss=False) is False


def test_abschluss_mit_niedriger_schwelle(conn, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    _segment(conn, 10, schnittgrund="ende")
    assert begriffsboard.soll_laufen(conn, CHAT, ist_abschluss=True) is True


def test_soll_laufen_ruft_brainstorm_soll_reagieren_unveraendert(conn, monkeypatch):
    gesehen = []
    monkeypatch.setattr(begriffsboard.brainstorm, "soll_reagieren",
                        lambda **kw: gesehen.append(kw) or True)
    _segment(conn, 10, "abc", schnittgrund="pause")
    assert begriffsboard.soll_laufen(conn, CHAT, ist_abschluss=False) is True
    assert gesehen == [{
        "unreagierte_zeichen": 3, "sekunden_seit_letzter_reaktion": float("inf"),
        "letzter_schnittgrund": "pause", "ist_abschluss": False,
    }]


# -- Lauf ---------------------------------------------------------------------

def test_lauf_speichert_das_validierte_board_mit_markierung(conn, einst):
    a = _segment(conn, 10)
    erfunden = dict(HEIMAT, begriff="Freiheit")
    klm = _KLM(board=[HEIMAT, erfunden])
    assert begriffsboard.starte(conn, klm, einst, CHAT) is True
    _warte_bis(lambda: repo.letztes_begriffsboard(conn, CHAT) is not None)
    zeile = repo.letztes_begriffsboard(conn, CHAT)
    assert [e["begriff"] for e in json.loads(zeile["json"])] == ["Heimat"]
    assert zeile["bis_aufnahme_id"] == a
    assert zeile["modell"] == "sovereign"
    assert klm.arten == ["begriffsboard"]
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))


def test_markierung_wird_vor_dem_lauf_gelesen(conn, einst):
    """Ein waehrend des Laufs eintreffendes Segment bleibt unreagiert."""
    a = _segment(conn, 10)
    halt = threading.Event()
    klm = _KLM(board=[HEIMAT], sperre=halt)
    begriffsboard.starte(conn, klm, einst, CHAT)
    _warte_bis(lambda: klm.aufrufe == 1)
    _segment(conn, 11, "spaeter dazu")
    halt.set()
    _warte_bis(lambda: repo.letztes_begriffsboard(conn, CHAT) is not None)
    assert repo.letztes_begriffsboard(conn, CHAT)["bis_aufnahme_id"] == a
    assert repo.begriffsboard_stand(conn, CHAT)["unreagierte_zeichen"] == len("spaeter dazu")
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))


def test_nur_ein_lauf_je_gruppe_gleichzeitig(conn, einst):
    _segment(conn, 10)
    halt = threading.Event()
    klm = _KLM(board=[HEIMAT], sperre=halt)
    assert begriffsboard.starte(conn, klm, einst, CHAT) is True
    _warte_bis(lambda: klm.aufrufe == 1)
    assert begriffsboard.starte(conn, klm, einst, CHAT) is False
    halt.set()
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    assert klm.aufrufe == 1


def test_gemerkter_rueckruf_laeuft_nach_dem_laufenden_lauf(conn, einst):
    _segment(conn, 10)
    halt = threading.Event()
    klm = _KLM(board=[HEIMAT], sperre=halt)
    begriffsboard.starte(conn, klm, einst, CHAT)
    _warte_bis(lambda: klm.aufrufe == 1)
    gerufen = []
    assert begriffsboard.starte(conn, klm, einst, CHAT, danach=lambda: gerufen.append(1)) is False
    assert gerufen == []
    halt.set()
    _warte_bis(lambda: gerufen == [1])


def test_gescheiterter_lauf_verliert_nichts(conn, einst):
    _segment(conn, 10)
    vorher = repo.begriffsboard_stand(conn, CHAT)["unreagierte_zeichen"]
    gerufen = []
    klm = _KLM(fehler=RuntimeError("weg"))
    begriffsboard.starte(conn, klm, einst, CHAT, danach=lambda: gerufen.append(1))
    _warte_bis(lambda: gerufen == [1])
    assert repo.letztes_begriffsboard(conn, CHAT) is None
    assert repo.begriffsboard_stand(conn, CHAT)["unreagierte_zeichen"] == vorher
    vorfaelle = conn.execute("SELECT art FROM vorfall WHERE chat_id = ?", (CHAT,)).fetchall()
    assert "begriffsboard_fehler" in [v["art"] for v in vorfaelle]
    assert not begriffsboard.laeuft(CHAT)


def test_leeres_ergebnis_ersetzt_kein_volles_board(conn, einst):
    a = _segment(conn, 10)
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps([HEIMAT]), "sovereign", a)
    _segment(conn, 11)
    begriffsboard.starte(conn, _KLM(board=[]), einst, CHAT)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    assert [e["begriff"] for e in begriffsboard.aktuelles(conn, CHAT)] == ["Heimat"]
    assert conn.execute("SELECT COUNT(*) FROM begriffsboard").fetchone()[0] == 1


def test_ohne_klm_oder_profil_kein_lauf(conn, einst, monkeypatch):
    _segment(conn, 10)
    assert begriffsboard.starte(conn, None, einst, CHAT) is False
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    assert begriffsboard.starte(conn, _KLM(board=[HEIMAT]), einst, CHAT) is False


def test_transkript_ueber_der_grenze_wird_vorn_gekuerzt(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_TRANSKRIPT_ZEICHEN", "20")
    _segment(conn, 10, "ANFANG " + "x" * 50 + " Heimat ENDE")
    klm = _KLM(board=[])
    begriffsboard.starte(conn, klm, einst, CHAT)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    assert "ANFANG" not in klm.nutzer[0] and "ENDE" in klm.nutzer[0]
    arten = [v["art"] for v in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "begriffsboard_transkript_gekuerzt" in arten


def test_der_lauf_kennt_kein_tg():
    """D5 strukturell: weder ``starte`` noch ``_lauf_einmal`` bekommen ein
    Telegram-Objekt."""
    for fn in (begriffsboard.starte, begriffsboard._lauf_einmal):
        assert "tg" not in inspect.signature(fn).parameters
```

- [ ] **Step 2: Rot**

Run: `$PY -m pytest tests/test_begriffsboard_lauf.py -q`
Expected: FAIL (`AttributeError: module ... has no attribute 'SCHEMA'` u. a.).

- [ ] **Step 3: Implementierung** — an `begriffsboard.py` anhängen (Konstanten `_TRANSKRIPT_KOPF`/`_BOARD_KOPF` zu den anderen Textkonstanten oben vor `T = ...` stellen):

```python
_TRANSKRIPT_KOPF = "Das Transkript der Diskussion bisher:"
_BOARD_KOPF = "Das bisherige Begriffsboard (JSON):"
```

```python
_FELDER = ("begriff", "nennungen", "zustimmung", "begruendung", "zitat",
           "doppelbedeutung", "status")

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften, sonst lehnt der Anbieter den erzwungenen Modus ab
#: (Kommentar an ``diskussion.SCHEMA``). Die Wurzel ist ein Objekt, weil der
#: Schema-Modus keine Liste als Wurzel nimmt; ``board`` statt ``begriffe``,
#: weil ``scripts/pruefe_sprache.py`` "begriffe" als deutsches Wort fuehrt.
#: ``status`` ist bewusst ein freier String: ``validiere`` macht aus jedem
#: unbekannten Wert "kandidat".
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["board"],
    "properties": {
        "board": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": list(_FELDER),
                "properties": {
                    "begriff": {"type": "string"},
                    "nennungen": {"type": "integer"},
                    "zustimmung": {"type": "integer"},
                    "begruendung": {"type": "string"},
                    "zitat": {"type": "string"},
                    "doppelbedeutung": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
        },
    },
}

VORGABE_TRANSKRIPT_ZEICHEN = 200_000


def transkript_zeichen_grenze() -> int:
    """``IT_BEGRIFFSBOARD_TRANSKRIPT_ZEICHEN`` -- dasselbe Muster wie
    ``buehnenkarte.transkript_zeichen_grenze``."""
    roh = (os.environ.get("IT_BEGRIFFSBOARD_TRANSKRIPT_ZEICHEN") or "").strip()
    if roh.isdigit() and int(roh) > 0:
        return int(roh)
    return VORGABE_TRANSKRIPT_ZEICHEN


def _nutzertext(transkript: str, board: list[dict]) -> str:
    """Der isolierte Nutzertext -- NUR das (schon gekuerzte) Transkript und
    das bisherige Board. Kein ``conn``, keine ``chat_id``: dieser Aufruf sieht
    nichts anderes, was im Raum gesagt wurde. Das Transkript steht vorn (es
    waechst nur hinten an, der Prompt-Praefix bleibt cache-stabil)."""
    return (
        f"{T._TRANSKRIPT_KOPF}\n{transkript}\n\n"
        f"{T._BOARD_KOPF}\n{json.dumps(sortiert(board), ensure_ascii=False)}"
    )


def aktuelles(conn, chat_id: int) -> list[dict]:
    """Der geltende Stand des Boards (letzte Zeile), oder eine leere Liste."""
    zeile = repo.letztes_begriffsboard(conn, chat_id)
    return lies(zeile["json"]) if zeile else []


def soll_laufen(conn, chat_id: int, *, ist_abschluss: bool) -> bool:
    """D1: ``brainstorm.soll_reagieren`` unveraendert, mit den eigenen Zahlen
    der Phase 1 (``repo.begriffsboard_stand``). Kein Modellaufruf."""
    stand = repo.begriffsboard_stand(conn, chat_id)
    sekunden = stand["sekunden_seit_letztem_lauf"]
    return brainstorm.soll_reagieren(
        unreagierte_zeichen=stand["unreagierte_zeichen"],
        sekunden_seit_letzter_reaktion=sekunden if sekunden is not None else float("inf"),
        letzter_schnittgrund=stand["letzter_schnittgrund"],
        ist_abschluss=ist_abschluss,
    )


#: Ein Sperren-Register je Nebenlaeufigkeit (AGENTS.md: "Gleicher Code,
#: verschiedene Sperren"), in Form aus ``brainstorm.py``: nie mehr als ein
#: Boardlauf je Gruppe. Dazu ein Merkplatz fuer Rueckrufe (der Vorschlag nach
#: "Discussion done"), die NACH dem gerade laufenden Lauf faellig sind --
#: Nehmen und Merken unter EINEM Schutz, wie ``vorschlagssperre.nimm_oder_merke``.
#: Grenze: der Merkplatz lebt im Prozess, ein Neustart verliert ihn.
_LAEUFT_LOCK = threading.Lock()
_LAEUFT: set[int] = set()
_DANACH: dict[int, list] = {}


def nimm_oder_merke(chat_id: int, danach) -> bool:
    """True und die Sperre gehoert dem Aufrufer -- oder False, und ``danach``
    (falls nicht None) laeuft, sobald der laufende Lauf endet."""
    with _LAEUFT_LOCK:
        if chat_id not in _LAEUFT:
            _LAEUFT.add(chat_id)
            return True
        if danach is not None:
            _DANACH.setdefault(chat_id, []).append(danach)
        return False


def versuche_start(chat_id: int) -> bool:
    return nimm_oder_merke(chat_id, None)


def beende(chat_id: int) -> list:
    """Gibt die Sperre frei und liefert die gemerkten Rueckrufe (der
    Aufrufer ruft sie, ausserhalb der Sperre)."""
    with _LAEUFT_LOCK:
        _LAEUFT.discard(chat_id)
        return _DANACH.pop(chat_id, [])


def laeuft(chat_id: int) -> bool:
    with _LAEUFT_LOCK:
        return chat_id in _LAEUFT


def _rufe(rueckrufe) -> None:
    for rueckruf in rueckrufe:
        try:
            rueckruf()
        except Exception:
            log.exception("Rueckruf nach dem Begriffsboard-Lauf fehlgeschlagen")


def _vorfall(conn, e, chat_id: int, art: str, detail: str) -> None:
    try:
        repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None), art, detail)
    except Exception:
        log.exception("Vorfall %s nicht geschrieben, chat_id=%s", art, chat_id)


def _lauf_einmal(conn, klm, e, chat_id: int, bis_id: int) -> None:
    """EIN Boardlauf. Kennt kein ``tg`` -- er schreibt nie in den Chat (D5)."""
    transkript = repo.diskussion_transkript(conn, chat_id)
    if not transkript.strip():
        return
    gesehen = transkript
    grenze = transkript_zeichen_grenze()
    if len(gesehen) > grenze:
        gesehen = gesehen[-grenze:]
        _vorfall(conn, e, chat_id, "begriffsboard_transkript_gekuerzt",
                 f"Diskussions-Transkript von {len(transkript)} auf {grenze} Zeichen gekuerzt")
    bisher = aktuelles(conn, chat_id)
    ueber_claude = modellwahl.konversation_ueber_claude(e, conn, chat_id)
    ergebnis = modellwahl.aufruf_schema(
        conn, klm, e, chat_id,
        system=anweisungen.hole("begriffsboard"),
        nutzer=_nutzertext(gesehen, bisher), schema=SCHEMA, art=ART,
        ueber_claude=ueber_claude,
    )
    # Geprueft wird gegen das GANZE Transkript: ein Begriff aus dem
    # weggekuerzten Anfang ist trotzdem woertlich gesagt worden.
    neu = validiere(ergebnis.get("board") if isinstance(ergebnis, dict) else None, transkript)
    if not neu and bisher:
        # Ein leeres Ergebnis ersetzt nie ein volles Board. Keine Zeile, also
        # keine Markierung: die Zeichen laufen weiter auf.
        log.info("Begriffsboard-Lauf ohne Ergebnis, altes Board bleibt, chat_id=%s", chat_id)
        return
    repo.lege_begriffsboard_an(
        conn, chat_id, json.dumps(neu, ensure_ascii=False),
        "claude" if ueber_claude else "sovereign", bis_id,
    )


def starte(conn, klm, e, chat_id: int, *, danach=None) -> bool:
    """Stoesst einen Boardlauf im eigenen Thread an (Zusage 2). Liefert
    True, wenn ein Lauf startete. ``danach`` laeuft nach DIESEM Lauf -- oder,
    wenn gerade schon einer laeuft, nach jenem (``nimm_oder_merke``). Ohne
    ``klm`` oder ohne Profil passiert nichts, auch ``danach`` nicht: das
    entscheidet der Aufrufer (``nach_segment``)."""
    if klm is None or not workshop.diskussion_aktiv():
        return False
    if not nimm_oder_merke(chat_id, danach):
        return False
    # VOR dem Lauf gelesen (D1): ein waehrend des Laufs neu eingetroffenes
    # Segment bleibt unreagiert und zaehlt beim naechsten Mal.
    bis_id = repo.hoechste_diskussion_aufnahme_id(conn, chat_id)

    def _lauf() -> None:
        try:
            _lauf_einmal(conn, klm, e, chat_id, bis_id)
        except Exception:
            log.exception("Begriffsboard-Lauf fehlgeschlagen, chat_id=%s", chat_id)
            _vorfall(conn, e, chat_id, "begriffsboard_fehler",
                     f"Begriffsboard-Lauf fehlgeschlagen fuer chat_id={chat_id}")
        finally:
            _rufe(([danach] if danach is not None else []) + beende(chat_id))

    try:
        threading.Thread(target=_lauf, daemon=True).start()
    except Exception:
        _rufe(([danach] if danach is not None else []) + beende(chat_id))
        raise
    return True
```

`sprachen/en/texte.toml`, Tabelle `["begriffsboard"]` ergänzen:

```toml
_TRANSKRIPT_KOPF = "The transcript of the discussion so far:"
_BOARD_KOPF = "The term board so far (JSON):"
```

`interview_theater/prompts/begriffsboard.md` (deutsch, nur Negativbeispiele):

```markdown
Du fuehrst das Begriffsboard einer Theaterworkshop-Gruppe. Die Gruppe
bespricht gerade frei, welche Begriffe ihr fuer ihr Stueck wichtig sind;
das Mikrofon laeuft im Hintergrund mit. Du bekommst das Transkript der
Diskussion bisher und das bisherige Board als JSON -- sonst nichts: keinen
Chat, keinen Arbeitsstand, keine Namen.

Gib das fortgeschriebene Board zurueck. Je Begriff, den die Gruppe im
Transkript selbst nennt:

- begriff: der Begriff im Wortlaut des Transkripts, ein bis drei Woerter,
  ohne Komma.
- nennungen: wie oft die Gruppe ihn nennt oder darueber spricht.
- zustimmung: -2 (klar abgelehnt) bis 2 (klar einig).
- begruendung: ein oder zwei Saetze, warum die Gruppe diesen Begriff will --
  in ihrer eigenen Argumentation.
- zitat: eine kurze Stelle, buchstabengetreu aus dem Transkript kopiert,
  oder "" wenn es keine gibt.
- doppelbedeutung: eine zweite Bedeutung, die die Gruppe selbst anspricht,
  sonst "".
- status: "favorit", wenn die Gruppe sich einig ist; "verworfen", wenn sie
  ihn fallen laesst; sonst "kandidat".

Begriffe aus dem bisherigen Board, die im Transkript stehen, behaeltst du
und schreibst ihre Zahlen fort.

Nicht so:

- Kein Begriff, den niemand gesagt hat -- auch keine Ueberschrift, die du der
  Diskussion geben wuerdest ("Identitaet", wenn nur "wo ich herkomme"
  fiel).
- Kein Zitat, das umformuliert ist ("sie sagten, Heimat sei wichtig" ist
  kein Zitat).
- Keine Begruendung, die die Gruppe nicht gegeben hat.
- Keine Beschreibung einzelner Sprecherinnen oder Sprecher ("eine meinte
  ...").
- Kein Text ausserhalb des JSON.

Eine Diskussion ohne Begriffe ergibt {"board": []}.
```

`interview_theater/sprachen/en/prompts/begriffsboard.md`:

```markdown
You keep the term board for a theatre workshop group. The group is talking
freely about which terms matter to them for their play; the microphone is
running in the background. You receive the transcript of the discussion so
far and the board so far as JSON -- nothing else: no chat, no work state,
no names.

Return the updated board. For every term that the group itself names in the
transcript:

- begriff: the term as worded in the transcript, one to three words, no
  comma.
- nennungen: how often the group names it or talks about it.
- zustimmung: -2 (clearly rejected) to 2 (clearly agreed).
- begruendung: one or two sentences on why the group wants this term -- in
  the group's own line of argument.
- zitat: a short passage copied letter for letter from the transcript, or
  "" if there is none.
- doppelbedeutung: a second meaning the group itself brings up, otherwise
  "".
- status: "favorit" when the group agrees on it; "verworfen" when it drops
  it; otherwise "kandidat".

Keep the terms from the board so far that appear in the transcript and
update their numbers.

Not like this:

- No term that nobody said -- not even a heading you would give the
  discussion ("identity" when only "where I come from" was said).
- No quote that is reworded ("they said home matters" is not a quote).
- No reason the group did not give.
- No description of individual speakers ("one of them thought ...").
- No text outside the JSON.

A discussion without terms gives {"board": []}.
```

ANNAHME: Die englische Prompt-Datei enthält die deutschen Feldnamen `begriff`, `nennungen`, `zustimmung`, `begruendung`, `zitat`, `doppelbedeutung` und die Statuswerte `favorit`, `kandidat`, `verworfen` — keines steht in `scripts/pruefe_sprache.py` `STOPPWOERTER`/`UI_WOERTER`, keines hat einen Umlaut. Geprüft wird das in Aufgabe 11 durch `tests/test_pruefe_sprache.py::test_padua_ist_frei_von_deutsch`; schlägt er an, die betroffenen Namen im englischen Prompt in Backticks setzen und `scripts/pruefe_sprache.py` prüfen, ob Backtick-Feldnamen ausgenommen sind (`FELDNAMEN_IN_BACKTICKS`), sonst die Namen in `ERLAUBT` ergänzen — mit Kommentar „Schema-Schlüssel des Begriffsboards".

- [ ] **Step 4: Grün + Prompt-Schnappschuss**

Run: `$PY -m pytest tests/test_begriffsboard_lauf.py tests/test_begriffsboard.py tests/test_profil_bitgleich.py tests/test_anweisungen.py -q`
Expected: PASS. (`test_der_schnappschuss_deckt_die_prompt_dateien_ab` findet die neue Datei über `rglob`; neue Abschnitte sind erlaubt.)

- [ ] **Step 5: Commit**

```bash
git add interview_theater/begriffsboard.py interview_theater/prompts/begriffsboard.md interview_theater/sprachen/en/prompts/begriffsboard.md interview_theater/sprachen/en/texte.toml tests/test_begriffsboard_lauf.py
git commit -m "Begriffsboard: Sperre, Ausloeser ueber brainstorm.soll_reagieren, Boardlauf im eigenen Thread (Aufgabe 3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Mithören — Einhängen in `aufnahme._diskussion_abschliessen`

**Files:**
- Modify: `interview_theater/begriffsboard.py` (anhängen: `nach_segment`, `sende_vorschlag` als Rückfall-Stub)
- Modify: `interview_theater/aufnahme.py:954-989` (`_diskussion_abschliessen`), Docstring `_kurz_abschliessen` (Z. 876–882)
- Modify: `interview_theater/diskussion.py` (Moduldocstring Z. 4–6)
- Modify: `tests/test_aufnahme_diskussion.py` (den einen veralteten Test ersetzen)
- Test: `tests/test_begriffsboard_mithoeren.py` (neu)

**Interfaces:**
- Consumes: `begriffsboard.starte`, `soll_laufen`, `laeuft`
- Produces:
  - `begriffsboard.nach_segment(conn, tg, klm, e, chat_id: int, *, ist_abschluss: bool, rueckfall_text: str | None = None) -> None`
  - `begriffsboard.sende_vorschlag(conn, tg, chat_id: int, rueckfall_text: str | None) -> None` — in dieser Aufgabe nur der Rückfall (`tg.sende(chat_id, rueckfall_text)`), den Vorschlag mit Knopf baut Aufgabe 6 ein.

- [ ] **Step 1: Failing tests** — `tests/test_begriffsboard_mithoeren.py`:

```python
"""Karte t_4517d4ad, Aufgabe 4: das Board haengt am echten Mithoer-Pfad
(``aufnahme._kurz_abschliessen`` -> ``_diskussion_abschliessen``), und es
entsteht dabei keine Chatzeile (D5, mit Mutant)."""

import threading
import time

import pytest

from interview_theater import aufnahme, begriffsboard, db, diskussion, einstellungen, repo, workshop

CHAT = 1
TEXT = "Wir reden ueber Heimat und Grenze. Heimat ist, wo meine Oma kocht."
HEIMAT = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 1, "begruendung": "Oma.",
          "zitat": "wo meine Oma kocht", "doppelbedeutung": "", "status": "favorit"}


@pytest.fixture(autouse=True)
def aktiv(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "10")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ABSTAND_S", "1")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    # Die Gesamtverdichtung ist nicht Gegenstand dieser Datei.
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: None)


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


class _TG:
    def __init__(self):
        self.gesendet = []
        self.mit_knoepfen = []
        self._id = 500

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._id += 1
        return self._id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        mid = self.sende(chat_id, text)
        self.mit_knoepfen.append((chat_id, text, list(knoepfe_)))
        return mid


class _KLM:
    def __init__(self, board):
        self.aufrufe = 0
        self._board = board

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        return {"board": self._board}


def _zeile(conn, message_id, schnittgrund, text=TEXT):
    aid = repo.lege_aufnahme_an(
        conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
        diskussion=True, schnittgrund=schnittgrund,
    )
    repo.setze_transkript(conn, aid, text)
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "sprache", None, repo._jetzt(), 1)
    return repo.hole_aufnahme(conn, aid)


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


def _segment_mit_board(conn, tg, einst, klm, message_id=700):
    row = _zeile(conn, message_id, "pause")
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, row, aufnahme._kein_zug, False)
    _warte_bis(lambda: repo.letztes_begriffsboard(conn, CHAT) is not None)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))


def _keine_chatzeile(tg):
    assert tg.gesendet == [] and tg.mit_knoepfen == []


def test_pausensegment_fuellt_das_board(conn, einst):
    tg, klm = _TG(), _KLM([HEIMAT])
    _segment_mit_board(conn, tg, einst, klm)
    assert [e["begriff"] for e in begriffsboard.aktuelles(conn, CHAT)] == ["Heimat"]
    assert klm.aufrufe == 1


def test_waehrend_des_mithoerens_keine_chatzeile(conn, einst):
    tg = _TG()
    _segment_mit_board(conn, tg, einst, _KLM([HEIMAT]))
    _keine_chatzeile(tg)


def test_mutant_sende_im_boardlauf_faellt_auf(conn, einst, monkeypatch):
    """D5-Mutant: schreibt der Boardlauf doch eine Chatzeile, muss
    ``_keine_chatzeile`` es merken."""
    tg = _TG()
    echt = begriffsboard._lauf_einmal

    def mutant(conn_, klm_, e_, chat_id, bis_id):
        echt(conn_, klm_, e_, chat_id, bis_id)
        tg.sende(chat_id, "Neuer Begriff auf dem Board!")

    monkeypatch.setattr(begriffsboard, "_lauf_einmal", mutant)
    _segment_mit_board(conn, tg, einst, _KLM([HEIMAT]))
    with pytest.raises(AssertionError):
        _keine_chatzeile(tg)


def test_kein_gespraechszug_und_keine_buehnenkarte(conn, einst, monkeypatch):
    karten = []
    monkeypatch.setattr(aufnahme, "_starte_buehnenkarte", lambda *a, **k: karten.append(1))
    zuege = []
    row = _zeile(conn, 701, "pause")
    aufnahme._kurz_abschliessen(conn, _TG(), _KLM([HEIMAT]), einst, row,
                                lambda *a, **k: zuege.append(1), False)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    assert karten == [] and zuege == []


def test_cap_segment_startet_keinen_lauf(conn, einst):
    klm = _KLM([HEIMAT])
    row = _zeile(conn, 702, "cap")
    aufnahme._kurz_abschliessen(conn, _TG(), klm, einst, row, aufnahme._kein_zug, False)
    time.sleep(0.1)
    assert klm.aufrufe == 0


def test_ohne_profil_bleibt_alles_wie_vorher(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    klm, tg = _KLM([HEIMAT]), _TG()
    row = _zeile(conn, 703, "ende")
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, row, aufnahme._kein_zug, False)
    time.sleep(0.1)
    assert klm.aufrufe == 0
    assert tg.gesendet == [(CHAT, aufnahme.T._TEXT_DISKUSSION_FERTIG_BEGRIFFE)]
```

In `tests/test_aufnahme_diskussion.py` den Test `test_diskussion_segment_ruft_weder_soll_reagieren_noch_buehnenkarte_auf` **ersetzen** durch (Begründung im Docstring — die Karte dreht genau diese Aussage):

```python
def test_diskussion_segment_startet_nie_eine_buehnenkarte(conn, einst, monkeypatch):
    """Ein Diskussions-Segment startet nie einen Buehnenkarten-Lauf (Phase
    4). Seit Karte t_4517d4ad prueft es aber ``soll_reagieren`` -- fuer das
    Begriffsboard (``begriffsboard.nach_segment``), siehe
    ``tests/test_begriffsboard_mithoeren.py``."""
    buehnenkarte_aufgerufen = []
    monkeypatch.setattr(
        aufnahme, "_starte_buehnenkarte",
        lambda *a, **k: buehnenkarte_aufgerufen.append(1),
    )
    row = _diskussion_zeile(conn, 1, 703, "x" * 200)
    aufnahme._kurz_abschliessen(conn, None, None, einst, row, aufnahme._kein_zug, False)
    assert not buehnenkarte_aufgerufen
```

(Vorher den kompletten bisherigen Testkörper lesen; behaltene Assertions zu `_starte_buehnenkarte` bleiben, nur die `soll_reagieren`-Assertion fällt weg.)

- [ ] **Step 2: Rot**

Run: `$PY -m pytest tests/test_begriffsboard_mithoeren.py -q`
Expected: FAIL (`test_pausensegment_fuellt_das_board` läuft in den Timeout „Bedingung nie eingetreten").

- [ ] **Step 3: Implementierung** — an `begriffsboard.py` anhängen:

```python
def sende_vorschlag(conn, tg, chat_id: int, rueckfall_text: str | None) -> None:
    """Nach "Discussion done": der Vorschlag aus dem Board -- oder, solange
    das Board leer ist, der bisherige Satz (D6). Aufgabe 6 baut den Knopf ein."""
    if rueckfall_text:
        tg.sende(chat_id, rueckfall_text)


def nach_segment(conn, tg, klm, e, chat_id: int, *, ist_abschluss: bool,
                 rueckfall_text: str | None = None) -> None:
    """Der Einhaengepunkt in ``aufnahme._diskussion_abschliessen``, je
    Segment. Entscheidet per Code (D1), ob ein Boardlauf faellig ist, und
    stoesst ihn im Thread an. Beim Abschluss-Segment (``ist_abschluss``)
    kommt danach der Vorschlag (D6): nach dem Schlusslauf, oder sofort,
    wenn keiner noetig ist. Ohne Profil, ohne Modell: nur der Satz, wie
    bisher."""
    danach = None
    if ist_abschluss:
        def danach() -> None:
            sende_vorschlag(conn, tg, chat_id, rueckfall_text)

    if (klm is None or not workshop.diskussion_aktiv()
            or not soll_laufen(conn, chat_id, ist_abschluss=ist_abschluss)):
        if danach is not None:
            danach()
        return
    starte(conn, klm, e, chat_id, danach=danach)
```

Hinweis zu `starte` → `False` mit belegter Sperre: `danach` ist dann gemerkt und kommt nach dem laufenden Lauf (Aufgabe 3, `test_gemerkter_rueckruf_...`). Kein zweiter Aufruf von `danach` hier.

`aufnahme._diskussion_abschliessen` (Z. 954–989) **Körper ersetzen**:

```python
    repo.setze_status(conn, row["id"], "fertig")
    _web_sprachblase(conn, row["chat_id"], row["message_id"], row["transkript"] or None)

    from interview_theater import begriffsboard  # lokaler Import, wie diskussion unten

    ende = row["schnittgrund"] == "ende"
    begriffsboard.nach_segment(
        conn, tg, klm, e, row["chat_id"], ist_abschluss=ende,
        rueckfall_text=T._TEXT_DISKUSSION_FERTIG_BEGRIFFE,
    )
    if ende:
        from interview_theater import diskussion  # lokaler Import, wie an anderen Cross-Modul-Stellen dieser Datei (z. B. bot)

        diskussion.starte(conn, tg, klm, e, row["chat_id"])
```

Docstring von `_diskussion_abschliessen` neu (ersetzt Z. 955–981):

```python
    """Ein Segment des Hintergrund-Mithoerens (Phase 1, Padua 03.10.2026):
    die Gruppe diskutiert im Raum, das Mikrofon laeuft mit -- reines
    Material, nie ein Gespraechsbeitrag an den Bot. Die ``nachricht``-Zeile
    bleibt, wie ``empfange()`` sie anlegte (``unterdrueckt=1``); das
    Transkript in ``aufnahme.transkript`` ist das Material.

    Auf JEDEM Segment: Status ``fertig``, das Transkript als Sprechblase
    (B7) -- und seit Karte t_4517d4ad (04.10.2026, Birk: Phase 1 und 4
    laufen EINHEITLICH automatisch) die Code-Entscheidung, ob das
    Begriffsboard fortgeschrieben wird: ``begriffsboard.nach_segment`` ruft
    ``brainstorm.soll_reagieren`` mit den eigenen Zahlen der Phase 1 und
    stoesst den Lauf im eigenen Thread an. Kein Gespraechszug, kein
    Absichtserkenner, keine Buehnenkarte und KEINE Chatzeile -- das Board
    steht nur im CoThinker-Tab.

    Beim Abschluss-Segment (``schnittgrund == 'ende'``) kommt danach der
    Vorschlag der Top 5 (oder, bei leerem Board, die bisherige Aufforderung
    "jetzt eure fuenf Begriffe") -- nach einem etwaigen Schlusslauf -- und,
    unabhaengig davon, der EINE Verdichtungslauf (``diskussion.starte``)."""
```

`_kurz_abschliessen`-Docstring, Absatz „Ein Diskussions-Segment …" (Z. 876–882): „kein Erkenner, keine CoThinker-Vorschlagskarte" → „kein Erkenner, keine Buehnenkarte; laufend wird nur das Begriffsboard fortgeschrieben (``begriffsboard.nach_segment``)".

`diskussion.py`-Moduldocstring Z. 4–6: „jedes Segment bleibt reines Material, ohne Gespraechszug, ohne Absichtserkenner, ohne CoThinker-Karte" → „jedes Segment bleibt reines Material, ohne Gespraechszug und ohne Absichtserkenner; laufend schreibt nur das Begriffsboard mit (``begriffsboard.py``, Karte t_4517d4ad)".

- [ ] **Step 4: Grün**

Run: `$PY -m pytest tests/test_begriffsboard_mithoeren.py tests/test_aufnahme_diskussion.py tests/test_aufnahme.py tests/test_diskussion.py tests/test_begriffsboard_lauf.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/begriffsboard.py interview_theater/aufnahme.py interview_theater/diskussion.py tests/test_begriffsboard_mithoeren.py tests/test_aufnahme_diskussion.py
git commit -m "Begriffsboard: laufend mithoeren -- Phase 1 nutzt die Brainstorm-Ausloesung, ohne Chatzeile (Aufgabe 4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `begriffe_detail` auf jedem Schreibweg von `begriffe`

**Files:**
- Modify: `interview_theater/begriffsboard.py` (anhängen: `schreibe_detail`)
- Modify: `interview_theater/erkenner.py` (`_wende_arbeitsstand_an` ~Z. 655, `_entferne_arbeitsstandfeld` ~Z. 1407)
- Modify: `interview_theater/knoepfe/basis.py` (`_speichere._schreibe` ~Z. 840)
- Test: `tests/test_begriffe_detail_wege.py` (neu)

**Interfaces:**
- Consumes: `repo.letztes_begriffsboard`, `lies`, `detail_fuer`
- Produces: `begriffsboard.schreibe_detail(conn, chat_id: int, begriffe_text: str | None) -> None`

Die Schreibwege von `arbeitsstand.begriffe` (gegrept am 04.10.2026, `setze_arbeitsstand(` in `interview_theater/`):

| Stelle | Feld | Haken |
|---|---|---|
| `erkenner._wende_arbeitsstand_an` | `feld` (u. a. `begriffe_setzen`) | ja |
| `erkenner._entferne_arbeitsstandfeld` | `feld` (u. a. „begriffe"/„terms") | ja (leeren) |
| `knoepfe/basis._speichere` → `_schreibe` | `_FELD_FUER.get(art, art)` („Ja, speichern", „Nein, nochmal ändern", ab Aufgabe 6 „Take these") | ja |
| `befehle._befehl_stueck` | nur `T._STUECK_FELDER` = rahmen/format | nein, kann `begriffe` nicht |
| `web_schreiben._setze_arbeitsstand.handler` | nur `ARBEITSSTANDFELDER` = rahmen/geschichte (`begriffe` steht in `FUEHRT_DER_CHAT`) | nein |
| `laengen.setze_faktor` | `FELD_FAKTOR` | nein |
| Ruecknahme (`repo.nimm_erkenner_lauf_zurueck`) | stellt `begriffe` UND `begriffe_detail` aus dem Schnappschuss her (Spalte wird automatisch verfolgt) | — |

`scripts/*.py` setzen `begriffe` für Prüf-/Vergleichsläufe ohne Board — bewusst nicht angefasst.

- [ ] **Step 1: Failing tests** — `tests/test_begriffe_detail_wege.py`:

```python
"""Karte t_4517d4ad, Aufgabe 5: begriffe_detail auf jedem Weg, der
``arbeitsstand.begriffe`` schreibt (D7)."""

import ast
import json
from pathlib import Path

import pytest

from interview_theater import begriffsboard, db, einstellungen, erkenner, repo, ruecknahme
from interview_theater.knoepfe import basis

CHAT = 1
WURZEL = Path(__file__).resolve().parent.parent / "interview_theater"
BOARD = [
    {"begriff": "Heimat", "nennungen": 2, "zustimmung": 2, "begruendung": "Wo die Oma kocht.",
     "zitat": "wo meine Oma kocht", "doppelbedeutung": "Ort und Gefuehl", "status": "favorit"},
    {"begriff": "Grenze", "nennungen": 1, "zustimmung": 1, "begruendung": "Im Kopf.",
     "zitat": "", "doppelbedeutung": "", "status": "kandidat"},
]


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def _board(conn):
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(BOARD), "sovereign", 1)


def _detail(conn):
    roh = repo.hole_arbeitsstand(conn, CHAT)["begriffe_detail"]
    return json.loads(roh) if roh else None


class _TG:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append(text)
        return 900 + len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return self.sende(chat_id, text)


# -- der Helfer ---------------------------------------------------------------

def test_schreibe_detail_mit_board(conn):
    _board(conn)
    begriffsboard.schreibe_detail(conn, CHAT, "heimat, Schule")
    assert _detail(conn) == [
        {"begriff": "heimat", "begruendung": "Wo die Oma kocht.", "zitat": "wo meine Oma kocht",
         "doppelbedeutung": "Ort und Gefuehl"},
        {"begriff": "Schule", "begruendung": "", "zitat": "", "doppelbedeutung": ""},
    ]


def test_ohne_board_bleibt_die_spalte_unberuehrt(conn):
    """Dortmund hat nie ein Board -- dort entsteht kein begriffe_detail."""
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "A, B")
    begriffsboard.schreibe_detail(conn, CHAT, "A, B")
    assert repo.hole_arbeitsstand(conn, CHAT)["begriffe_detail"] is None


def test_leere_begriffe_leeren_das_detail(conn):
    _board(conn)
    begriffsboard.schreibe_detail(conn, CHAT, "Heimat")
    begriffsboard.schreibe_detail(conn, CHAT, None)
    assert repo.hole_arbeitsstand(conn, CHAT)["begriffe_detail"] is None


# -- die Wege -----------------------------------------------------------------

def test_erkenner_weg_schreibt_detail(conn, einst):
    _board(conn)
    erkenner.wende_an(conn, einst, CHAT, [{"art": "begriffe_setzen", "wert": "Heimat, Grenze"}])
    assert [d["begruendung"] for d in _detail(conn)] == ["Wo die Oma kocht.", "Im Kopf."]


def test_erkenner_entfernen_leert_detail(conn, einst):
    _board(conn)
    erkenner.wende_an(conn, einst, CHAT, [{"art": "begriffe_setzen", "wert": "Heimat"}])
    erkenner.entferne(conn, CHAT, "begriffe")
    stand = repo.hole_arbeitsstand(conn, CHAT)
    assert stand["begriffe"] is None and stand["begriffe_detail"] is None


def test_knopf_weg_schreibt_detail(conn, einst):
    _board(conn)
    basis._speichere(conn, _TG(), CHAT, "begriffe|Grenze, Heimat", e=einst)
    assert [d["begriff"] for d in _detail(conn)] == ["Grenze", "Heimat"]
    assert _detail(conn)[1]["doppelbedeutung"] == "Ort und Gefuehl"


# -- Ruecknahme ---------------------------------------------------------------

def test_ruecknahme_verfolgt_die_neue_spalte():
    assert "begriffe_detail" in ruecknahme.spalten("arbeitsstand")
    assert "begriffsboard" not in ruecknahme.VERFOLGT


# -- Struktur: kein neuer Schreibweg ohne Haken -------------------------------

#: Jede Stelle in ``interview_theater/``, die ``setze_arbeitsstand`` mit einem
#: NICHT-literalen Feldnamen ruft -- (Datei, innerste Funktion). Kommt eine
#: dazu, schlaegt der Test an: dann pruefen, ob sie ``begriffe`` schreiben
#: kann, und ggf. ``begriffsboard.schreibe_detail`` einhaengen.
VARIABLE_FELDER = {
    ("erkenner.py", "_wende_arbeitsstand_an"),     # Haken
    ("erkenner.py", "_entferne_arbeitsstandfeld"),  # Haken
    ("knoepfe/basis.py", "_schreibe"),             # Haken
    ("befehle.py", "_befehl_stueck"),              # nur rahmen/format
    ("web_schreiben.py", "handler"),               # nur rahmen/geschichte
    ("laengen.py", "setze_faktor"),                # nur laengen_faktor
}
MIT_HAKEN = {
    ("erkenner.py", "_wende_arbeitsstand_an"),
    ("erkenner.py", "_entferne_arbeitsstandfeld"),
    ("knoepfe/basis.py", "_schreibe"),
}


def _aufrufe():
    literal, variabel = [], set()
    for pfad in WURZEL.rglob("*.py"):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        rel = str(pfad.relative_to(WURZEL))

        def besuche(knoten, funktion):
            for kind in ast.iter_child_nodes(knoten):
                name = kind.name if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef)) else funktion
                if (isinstance(kind, ast.Call) and isinstance(kind.func, ast.Attribute)
                        and kind.func.attr == "setze_arbeitsstand" and len(kind.args) >= 3):
                    feld = kind.args[2]
                    if isinstance(feld, ast.Constant):
                        literal.append((rel, feld.value))
                    else:
                        variabel.add((rel, funktion))
                besuche(kind, name)

        besuche(baum, None)
    return literal, variabel


def test_kein_literaler_schreibweg_fuer_begriffe():
    literal, _ = _aufrufe()
    assert [s for s in literal if s[1] == "begriffe"] == []


def test_jeder_variable_schreibweg_ist_geprueft():
    _, variabel = _aufrufe()
    assert variabel == VARIABLE_FELDER


def test_die_haken_stehen_an_den_drei_stellen():
    for datei, funktion in MIT_HAKEN:
        quelle = (WURZEL / datei).read_text(encoding="utf-8")
        baum = ast.parse(quelle)
        treffer = [k for k in ast.walk(baum)
                   if isinstance(k, ast.FunctionDef) and k.name == funktion]
        assert treffer, (datei, funktion)
        assert "schreibe_detail" in ast.unparse(treffer[0]), (datei, funktion)
```

ANNAHME: `erkenner.entferne(conn, chat_id, "begriffe")` trifft `_entferne_arbeitsstandfeld` (Schlüssel `"begriffe"` in `_ENTFERNEN_ARBEITSSTAND`, erkenner.py ~Z. 1391). ANNAHME: `basis._speichere(conn, tg, chat_id, "begriffe|…", e=einst)` läuft ohne `klm` durch (Default `weiterfrage=True`, `uebergang=False` → nur `_phasenknopf`/Weiterfrage); falls `_phasenknopf` mehr von `tg` braucht, `_TG` um die fehlende Methode ergänzen. ANNAHME: `VARIABLE_FELDER` stimmt beim ersten Lauf exakt (aus dem Grep vom 04.10.2026); weicht die Menge ab, jede abweichende Stelle lesen und mit Begründung in die Menge aufnehmen — nie blind.

- [ ] **Step 2: Rot**

Run: `$PY -m pytest tests/test_begriffe_detail_wege.py -q`
Expected: FAIL (`schreibe_detail` fehlt; Haken fehlen).

- [ ] **Step 3: Implementierung** — `begriffsboard.py` anhängen:

```python
def schreibe_detail(conn, chat_id: int, begriffe_text: str | None) -> None:
    """D7: je gespeichertem Begriff die Boardzeile nach
    ``arbeitsstand.begriffe_detail``. Gerufen auf JEDEM Weg, der
    ``arbeitsstand.begriffe`` schreibt (festgenagelt in
    ``tests/test_begriffe_detail_wege.py``). Leere Begriffe leeren das
    Detail. Ohne Board (Dortmund, oder nie mitgehoert) bleibt die Spalte,
    wie sie ist -- dort entsteht kein Detail."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    bisher = stand["begriffe_detail"] if stand is not None else None
    zeile = repo.letztes_begriffsboard(conn, chat_id)
    if not (begriffe_text or "").strip() or zeile is None:
        if bisher:
            repo.setze_arbeitsstand(conn, chat_id, "begriffe_detail", None)
        return
    detail = detail_fuer(lies(zeile["json"]), begriffe_text)
    repo.setze_arbeitsstand(
        conn, chat_id, "begriffe_detail", json.dumps(detail, ensure_ascii=False),
    )
```

`erkenner._wende_arbeitsstand_an`, direkt nach `repo.setze_arbeitsstand(conn, chat_id, feld, wert)`:

```python
    if feld == "begriffe":
        # Karte t_4517d4ad (D7): je Begriff die Zeile des Begriffsboards.
        from interview_theater import begriffsboard

        begriffsboard.schreibe_detail(conn, chat_id, wert)
```

`erkenner._entferne_arbeitsstandfeld`, direkt nach `repo.setze_arbeitsstand(conn, chat_id, feld, None)`:

```python
    if feld == "begriffe":
        from interview_theater import begriffsboard

        begriffsboard.schreibe_detail(conn, chat_id, None)
```

`knoepfe/basis._speichere._schreibe`:

```python
    def _schreibe():
        feld = _FELD_FUER.get(art, art)
        repo.setze_arbeitsstand(conn, chat_id, feld, wert)
        if feld == "begriffe":
            # Karte t_4517d4ad (D7) -- innerhalb von ``lauf_fuer_knopf``, damit
            # die Ruecknahme das Detail mit zuruecknimmt.
            from interview_theater import begriffsboard

            begriffsboard.schreibe_detail(conn, chat_id, wert)
        if weiterfrage:
            # Abgenommen: die offene Aenderungsbitte ist erledigt, die Leiste
            # verschwindet wieder (``offene_art``).
            repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)
```

- [ ] **Step 4: Grün + Ruecknahme-/Knopf-Nachbarn**

Run: `$PY -m pytest tests/test_begriffe_detail_wege.py tests/test_ruecknahme.py tests/test_ruecknahme_rundreise.py tests/test_ruecknahme_repo.py tests/test_undo_knopf.py tests/test_knoepfe_struktur.py tests/test_erkenner.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/begriffsboard.py interview_theater/erkenner.py interview_theater/knoepfe/basis.py tests/test_begriffe_detail_wege.py
git commit -m "Begriffsboard: begriffe_detail auf jedem Schreibweg von begriffe, per AST festgenagelt (Aufgabe 5)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: „Discussion done" — Top-5-Vorschlag mit EINEM Knopf „Take these"

**Files:**
- Modify: `interview_theater/knoepfe/texte.py` (ART neben `ART_SPEICHERN` ~Z. 79; Texte neben `_TEXT_SPEICHERN_KNOPF` ~Z. 307)
- Modify: `interview_theater/knoepfe/basis.py` (neue Funktion `biete_begriffsvorschlag`)
- Modify: `interview_theater/knoepfe/wirkung.py` (Import, Handler, Eintrag in `_WIRKUNGEN` ~Z. 1551)
- Modify: `interview_theater/begriffsboard.py` (`sende_vorschlag` vervollständigen)
- Modify: `interview_theater/sprachen/en/texte.toml` (`["knoepfe.texte"]`)
- Test: `tests/test_begriffsboard_vorschlag.py` (neu)

**Interfaces:**
- Consumes: `begriffsboard.aktuelles`, `top`, `nach_segment` (Aufgabe 4), `schreibe_detail` (Aufgabe 5 — „Take these" geht durch `_speichere`)
- Produces:
  - `knoepfe.texte.ART_BOARD_UEBERNEHMEN = "board_uebernehmen"`, `_TEXT_BOARD_VORSCHLAG` (Platzhalter `{liste}`), `_TEXT_BOARD_UEBERNEHMEN_KNOPF`
  - `knoepfe.basis.biete_begriffsvorschlag(conn, tg, chat_id: int, begriffe: list[str]) -> int`
  - `knoepfe.wirkung._wirkung_board_uebernehmen(conn, d: Druck) -> str`

- [ ] **Step 1: Failing tests** — `tests/test_begriffsboard_vorschlag.py`:

```python
"""Karte t_4517d4ad, Aufgabe 6: "Discussion done" -> Top-5-Vorschlag (D6)."""

import json
import threading
import time

import pytest

from interview_theater import (
    aufnahme, begriffsboard, db, diskussion, einstellungen, knoepfe, repo, workshop,
)
from interview_theater.knoepfe import texte

CHAT = 1
TEXT = "Heimat und Grenze und Mut und Schule und Freunde und Angst und Musik."


@pytest.fixture(autouse=True)
def aktiv(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: None)


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


class _TG:
    def __init__(self):
        self.gesendet = []
        self.mit_knoepfen = []
        self.beantwortet = []
        self._id = 800

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._id += 1
        return self._id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        mid = self.sende(chat_id, text)
        self.mit_knoepfen.append((chat_id, text, list(knoepfe_)))
        return mid

    def beantworte_knopf(self, callback_query_id, text=""):
        self.beantwortet.append(text)

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    def tippt(self, chat_id):
        pass


def _e(begriff, status="kandidat", zustimmung=0, nennungen=1):
    return {"begriff": begriff, "nennungen": nennungen, "zustimmung": zustimmung,
            "begruendung": f"Weil {begriff}.", "zitat": "", "doppelbedeutung": "", "status": status}


def _ende(conn, message_id=900):
    aid = repo.lege_aufnahme_an(conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
                                diskussion=True, schnittgrund="ende")
    repo.setze_transkript(conn, aid, TEXT)
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "sprache", None, repo._jetzt(), 1)
    return repo.hole_aufnahme(conn, aid)


def _druecke(conn, tg, einst, daten, klm=None):
    return knoepfe.behandle(conn, tg, klm, einst, {
        "callback_query_id": "q1", "data": daten, "chat_id": CHAT,
        "chat_titel": "Testgruppe", "message_id": 777,
    })


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


def test_leeres_board_heutiger_text(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "100000")
    tg = _TG()
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, _ende(conn), aufnahme._kein_zug, False)
    assert tg.gesendet == [(CHAT, aufnahme.T._TEXT_DISKUSSION_FERTIG_BEGRIFFE)]
    assert tg.mit_knoepfen == []


def test_ohne_schlusslauf_sofort_die_top_fuenf_mit_einem_knopf(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "100000")
    board = [_e("Heimat", "favorit"), _e("Grenze", zustimmung=2), _e("Mut", zustimmung=1),
             _e("Schule"), _e("Freunde"), _e("Angst"), _e("Musik", "verworfen", 2, 9)]
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(board), "sovereign", 0)
    tg = _TG()
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, _ende(conn), aufnahme._kein_zug, False)
    assert len(tg.mit_knoepfen) == 1
    _chat, text, leiste = tg.mit_knoepfen[0]
    assert len(leiste) == 1
    beschriftung, daten = leiste[0]
    assert beschriftung == texte.T._TEXT_BOARD_UEBERNEHMEN_KNOPF
    assert daten.startswith("k:") and len(daten.encode()) < 64
    for nr, begriff in enumerate(["Heimat", "Grenze", "Mut", "Angst", "Freunde"], 1):
        assert f"{nr}. {begriff}" in text
    assert "Musik" not in text and "Schule" not in text
    knopf = repo.hole_knopf(conn, int(daten[2:]))
    assert knopf["art"] == texte.ART_BOARD_UEBERNEHMEN
    assert knopf["wert"] == "Heimat, Grenze, Mut, Angst, Freunde"
    assert aufnahme.T._TEXT_DISKUSSION_FERTIG_BEGRIFFE not in [t for _c, t in tg.gesendet]


def test_mit_schlusslauf_kommt_der_vorschlag_erst_danach(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    halt = threading.Event()

    class KLM:
        def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
            halt.wait(5)
            return {"board": [_e("Heimat", "favorit")]}

    tg = _TG()
    aufnahme._kurz_abschliessen(conn, tg, KLM(), einst, _ende(conn), aufnahme._kein_zug, False)
    time.sleep(0.1)
    assert tg.mit_knoepfen == [] and tg.gesendet == []
    halt.set()
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    assert "1. Heimat" in tg.mit_knoepfen[0][1]


def test_gescheiterter_schlusslauf_nimmt_das_aktuelle_board(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "10")
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps([_e("Grenze")]), "sovereign", 0)

    class KLM:
        def schema(self, *a, **k):
            raise RuntimeError("weg")

    tg = _TG()
    aufnahme._kurz_abschliessen(conn, tg, KLM(), einst, _ende(conn), aufnahme._kein_zug, False)
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    assert "1. Grenze" in tg.mit_knoepfen[0][1]


def test_gesamtverdichtung_startet_unabhaengig(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "100000")
    gestartet = []
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: gestartet.append(1))
    aufnahme._kurz_abschliessen(conn, _TG(), object(), einst, _ende(conn), aufnahme._kein_zug, False)
    assert gestartet == [1]


def test_take_these_speichert_begriffe_und_detail_einmal(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "100000")
    board = [_e("Heimat", "favorit"), _e("Grenze")]
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(board), "sovereign", 0)
    tg = _TG()
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, _ende(conn), aufnahme._kein_zug, False)
    daten = tg.mit_knoepfen[0][2][0][1]

    assert _druecke(conn, tg, einst, daten) is True
    stand = repo.hole_arbeitsstand(conn, CHAT)
    assert stand["begriffe"] == "Heimat, Grenze"
    assert [d["begruendung"] for d in json.loads(stand["begriffe_detail"])] == [
        "Weil Heimat.", "Weil Grenze.",
    ]

    vorher = len(tg.gesendet)
    _druecke(conn, tg, einst, daten)   # zweiter Druck: beantwortet, wirkt nicht (Zusage 3)
    assert repo.hole_arbeitsstand(conn, CHAT)["begriffe"] == "Heimat, Grenze"
    assert len(tg.gesendet) == vorher
```

ANNAHME: `knoepfe.behandle(...)` liefert bei einem bekannten Knopf `True` und beantwortet einen zweiten Druck ohne Wirkung und ohne neue Chatzeile (so in `tests/test_interview_ohne_knopf.py`, `_druecke`). Falls der zweite Druck eine Antwortzeile über `tg.beantworte_knopf` erzeugt, ist das keine Chatzeile — die Assertion zählt nur `gesendet`.

- [ ] **Step 2: Rot**

Run: `$PY -m pytest tests/test_begriffsboard_vorschlag.py -q`
Expected: FAIL (`AttributeError: ... _TEXT_BOARD_UEBERNEHMEN_KNOPF`, Vorschlag fehlt).

- [ ] **Step 3: Implementierung**

`knoepfe/texte.py`, neben `ART_SPEICHERN`:

```python
#: "Take these" unter dem Top-5-Vorschlag des Begriffsboards (Karte
#: t_4517d4ad, D6): EIN Knopf, der Wert ist die Begriffsliste.
ART_BOARD_UEBERNEHMEN = "board_uebernehmen"
```

neben `_TEXT_SPEICHERN_KNOPF`:

```python
_TEXT_BOARD_UEBERNEHMEN_KNOPF = "Diese nehmen"
_TEXT_BOARD_VORSCHLAG = (
    "Die Diskussion ist zu Ende. Oben auf eurem Begriffsboard stehen:\n"
    "{liste}\n\n"
    "Nehmt ihr diese? Ihr koennt mir auch eure eigenen fuenf Begriffe "
    "schicken - getippt oder als Sprachnachricht."
)
```

`sprachen/en/texte.toml`, Tabelle `["knoepfe.texte"]`:

```toml
_TEXT_BOARD_UEBERNEHMEN_KNOPF = "Take these"
_TEXT_BOARD_VORSCHLAG = "The discussion is over. At the top of your term board:\n{liste}\n\nTake these? You can also send me your own five terms - typed or as a voice message."
```

`knoepfe/basis.py` — Import `ART_BOARD_UEBERNEHMEN` in den `knoepfe.texte`-Import aufnehmen; neue Funktion hinter `_sende_knoepfe`:

```python
def biete_begriffsvorschlag(conn, tg, chat_id: int, begriffe: list[str]) -> int:
    """Der Top-5-Vorschlag nach "Discussion done" (Karte t_4517d4ad, D6):
    die Begriffe als nummerierte Liste und EIN Knopf "Take these". Eine
    Abkuerzung, nie ein Zwang -- der Text sagt, dass die Gruppe ihre fuenf
    auch selbst schicken kann. Der Wert steht in der Tabelle ``knopf``
    (Zusage 1), gespeichert wird beim Druck ueber ``_speichere`` (Zusage 2:
    kein Modellaufruf)."""
    liste = "\n".join(f"{nr}. {begriff}" for nr, begriff in enumerate(begriffe, 1))
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_BOARD_UEBERNEHMEN, ", ".join(begriffe))
    message_id = _sende_knoepfe(
        conn, tg, chat_id, T._TEXT_BOARD_VORSCHLAG.format(liste=liste),
        [(T._TEXT_BOARD_UEBERNEHMEN_KNOPF, _daten(knopf_id))],
    )
    repo.merke_knopf_nachricht(conn, [knopf_id], message_id)
    return message_id
```

ANNAHME: `_daten` ist in `basis.py` vor `_sende_knoepfe` definiert (Z. 26 laut Grep) — ja.

`knoepfe/wirkung.py` — `ART_BOARD_UEBERNEHMEN` in den `knoepfe.texte`-Import; Handler neben `_wirkung_speichern`:

```python
def _wirkung_board_uebernehmen(conn, d: Druck) -> str:
    """"Take these" unter dem Top-5-Vorschlag (Karte t_4517d4ad): derselbe
    Speicherweg wie "Ja, speichern" -- also auch ``begriffe_detail``
    (``_speichere`` -> ``begriffsboard.schreibe_detail``), dieselbe
    Ruecknahme, derselbe Uebergang in Phase 2. Ueberschreibt nie still einen
    schon gesetzten Wert (``nur_bestaetigen``)."""
    return _speichere(
        conn, d.tg, d.chat_id, f"begriffe{TRENNER}{d.wert}",
        nur_bestaetigen=True, uebergang=True, klm=d.klm, e=d.e,
    )
```

In `_WIRKUNGEN`: `ART_BOARD_UEBERNEHMEN: _wirkung_board_uebernehmen,`.

`begriffsboard.sende_vorschlag` ersetzen:

```python
def sende_vorschlag(conn, tg, chat_id: int, rueckfall_text: str | None) -> None:
    """Nach "Discussion done" (D6): steht mindestens ein nicht verworfener
    Begriff auf dem Board, die Top 5 mit EINEM Knopf "Take these" -- sonst
    der bisherige Satz unveraendert. Liest das Board, wie es JETZT ist (nach
    einem etwaigen Schlusslauf, auch wenn der scheiterte)."""
    oben = [e["begriff"] for e in top(aktuelles(conn, chat_id))]
    if not oben:
        if rueckfall_text:
            tg.sende(chat_id, rueckfall_text)
        return
    from interview_theater.knoepfe import basis  # Aufruf nach oben: lokal, wie im ganzen Repo

    basis.biete_begriffsvorschlag(conn, tg, chat_id, oben)
```

- [ ] **Step 4: Grün + Knopf-Struktur**

Run: `$PY -m pytest tests/test_begriffsboard_vorschlag.py tests/test_knoepfe_struktur.py tests/test_begriffsboard_mithoeren.py tests/test_aufnahme_diskussion.py -q`
Expected: PASS (`test_jede_knopfart_hat_genau_einen_handler` findet `ART_BOARD_UEBERNEHMEN` in `_WIRKUNGEN`; `test_kein_handler_ruft_das_sprachmodell` grün, weil der Handler nur `_speichere` ruft).

- [ ] **Step 5: Commit**

```bash
git add interview_theater/knoepfe/texte.py interview_theater/knoepfe/basis.py interview_theater/knoepfe/wirkung.py interview_theater/begriffsboard.py interview_theater/sprachen/en/texte.toml tests/test_begriffsboard_vorschlag.py
git commit -m "Begriffsboard: Discussion done schlaegt die Top 5 mit einem Knopf vor, Take these speichert mit Detail (Aufgabe 6)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Weitergabe — Kontextblock (Phase 2, ≥ 4) und isolierter KI-Fragen-Aufruf

**Files:**
- Modify: `interview_theater/kontext.py` (`BUDGETS` ~Z. 97, `_REIHENFOLGE` ~Z. 232, neue Konstante + Funktion hinter `_baue_diskussion_block` ~Z. 851, `_bloecke` ~Z. 1664, Kürzungsleiter ~Z. 1779)
- Modify: `interview_theater/fragen_ki.py` (`_nutzertext`, `starte`, Konstante)
- Modify: `interview_theater/sprachen/en/texte.toml` (`["kontext"]`, `["fragen_ki"]`)
- Modify: `tests/test_fragen_ki.py:87-92` (Signaturtest), `tests/test_sprache_bitgleich.py` (Grund bei `"kontext._REIHENFOLGE"`)
- Test: `tests/test_begriffe_detail_weitergabe.py` (neu)

**Interfaces:**
- Consumes: `roadmap.begriffe_detail(stand)` (liest die Spalte, wirft das Zitat weg), `begriffsboard.detail_zeilen`
- Produces:
  - `kontext.BEGRIFFE_DETAIL_KOPF`, `kontext._baue_begriffe_detail(conn, chat_id) -> str`, Blockname `"begriffe_detail"` direkt hinter `"diskussion"`
  - `fragen_ki._nutzertext(begriffe: str, diskussion_text: str | None, begriffe_detail: list[dict] | None = None) -> str`

- [ ] **Step 1: Failing tests** — `tests/test_begriffe_detail_weitergabe.py`:

```python
"""Karte t_4517d4ad, Aufgabe 7: begriffe_detail geht in Phase 2 und ab
Phase 4 in den Gespraechs-Prompt, und in den ISOLIERTEN KI-Fragen-Aufruf (D8)."""

import json
import time

import pytest

from interview_theater import db, einstellungen, fragen_ki, kontext, repo, workshop

CHAT = 1
GRUND = "Weil Heimat fuer uns der Ort ist, wo die Oma kocht."
ZITAT = "ZITAT-DARF-NIE-IN-DEN-PROMPT"
EIGENE_FRAGE = "EIGENE-FRAGE-DER-GRUPPE?"


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    repo.setze_arbeitsstand(c, CHAT, "begriffe", "Heimat, Schule")
    repo.setze_arbeitsstand(c, CHAT, "begriffe_detail", json.dumps([
        {"begriff": "Heimat", "begruendung": GRUND, "zitat": ZITAT, "doppelbedeutung": "Ort und Gefuehl"},
        {"begriff": "Schule", "begruendung": "", "zitat": "", "doppelbedeutung": ""},
    ]))
    return c


@pytest.mark.parametrize("phase, erwartet", [(1, False), (2, True), (3, False), (4, True), (6, True)])
def test_block_nur_in_phase_2_und_ab_4(conn, phase, erwartet):
    repo.setze_phase(conn, CHAT, phase)
    block = kontext._baue_begriffe_detail(conn, CHAT)
    assert (GRUND in block) is erwartet
    assert ZITAT not in block


def test_block_traegt_kopf_und_doppelbedeutung(conn):
    repo.setze_phase(conn, CHAT, 2)
    block = kontext._baue_begriffe_detail(conn, CHAT)
    assert block.startswith(kontext.T.BEGRIFFE_DETAIL_KOPF)
    assert "Ort und Gefuehl" in block
    assert "Schule" not in block


def test_ohne_detail_kein_block(conn):
    repo.setze_phase(conn, CHAT, 2)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe_detail", None)
    assert kontext._baue_begriffe_detail(conn, CHAT) == ""


def test_block_steht_direkt_hinter_der_diskussion():
    reihenfolge = list(kontext._REIHENFOLGE)
    assert reihenfolge[reihenfolge.index("diskussion") + 1] == "begriffe_detail"


def test_block_erscheint_im_fertigen_prompt_phase_2(conn, einst):
    repo.setze_phase(conn, CHAT, 2)
    repo.merke_nachricht(conn, CHAT, 1, "Ada", 0, "text", "los", repo._jetzt())
    ausloeser = list(repo.unbeantwortete(conn, CHAT))
    prompt = kontext.baue(conn, CHAT, ausloeser, einst)
    assert GRUND in prompt and ZITAT not in prompt


# -- fragen_ki ---------------------------------------------------------------

def test_nutzertext_nimmt_das_detail_auf():
    text = fragen_ki._nutzertext("Heimat", None, [
        {"begriff": "Heimat", "begruendung": GRUND, "doppelbedeutung": ""},
    ])
    assert GRUND in text


def test_isolierter_ki_fragen_aufruf_sieht_detail_aber_keine_eigene_frage(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "fragen_ab_aktiv", lambda *a, **k: True)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_vorschlag", EIGENE_FRAGE)

    class KLM:
        nutzer = None

        def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
            KLM.nutzer = nutzer
            return {"antwort": "Heimat: Was vermisst du?"}

    class TG:
        def sende(self, *a, **k):
            return 1

        def sende_mit_knoepfen(self, *a, **k):
            return 1

    fragen_ki.starte(conn, TG(), KLM(), einst, CHAT)
    ende = time.monotonic() + 5
    while KLM.nutzer is None and time.monotonic() < ende:
        time.sleep(0.01)
    assert GRUND in KLM.nutzer
    assert EIGENE_FRAGE not in KLM.nutzer
    assert ZITAT not in KLM.nutzer
```

ANNAHME: `repo.merke_nachricht(conn, chat_id, message_id, absender, ist_bot, typ, text, gesendet_am)` und `repo.unbeantwortete(conn, chat_id)` passen so (Signatur in `repo.py:200`/`:289` vor dem Schreiben lesen; `tests/test_kontext.py` hat einen Helfer `_sende`, den man stattdessen nachbauen kann).

`tests/test_fragen_ki.py::test_nutzertext_signatur_kennt_weder_conn_noch_chat_id` ändern:

```python
    assert parameter == ["begriffe", "diskussion_text", "begriffe_detail"]
```

- [ ] **Step 2: Rot**

Run: `$PY -m pytest tests/test_begriffe_detail_weitergabe.py tests/test_fragen_ki.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementierung**

`kontext.py` — `BUDGETS` hinter `"diskussion": 800,`:

```python
    # Die Begruendungen je Begriff aus dem Begriffsboard (Karte t_4517d4ad):
    # klein wie die Diskussion, und wie sie bei Platznot im Ganzen weg.
    "begriffe_detail": 400,
```

`_REIHENFOLGE`: `"diskussion", "begriffe_detail", "phasenhinweis", ...`.

Hinter `_baue_diskussion_block`:

```python
#: Die Kopfzeile des Begriffs-Blocks (Karte t_4517d4ad, 04.10.2026).
BEGRIFFE_DETAIL_KOPF = "Warum ihr diese Begriffe gewaehlt habt:"


def _baue_begriffe_detail(conn, chat_id: int) -> str:
    """Begruendung und Doppelbedeutung je gespeichertem Begriff, aus dem
    Begriffsboard der Phase 1 (``arbeitsstand.begriffe_detail``) -- in Phase
    2 (die Fragen entstehen aus den Begriffen) und ab Phase 4 (Setting,
    Figuren, Geschichte). Nicht in Phase 3: dort wird interviewt. Nie das
    Zitat (``roadmap.begriffe_detail`` wirft es weg). Datengetrieben: ohne
    Detail (Dortmund) kein Block."""
    phase = phasen.aktuelle(conn, chat_id)
    if phase != 2 and phase < 4:
        return ""
    from interview_theater import begriffsboard, roadmap

    zeilen = begriffsboard.detail_zeilen(
        roadmap.begriffe_detail(repo.hole_arbeitsstand(conn, chat_id))
    )
    if not zeilen:
        return ""
    return T.BEGRIFFE_DETAIL_KOPF + "\n" + "\n".join(zeilen)
```

`_bloecke`, hinter `"diskussion": ...`:

```python
        # Direkt dahinter: warum die Gruppe ihre Begriffe gewaehlt hat
        # (Begriffsboard, Phase 2 und ab 4).
        "begriffe_detail": _baue_begriffe_detail(conn, chat_id),
```

Kürzungsleiter, direkt hinter dem `if _zu_lang() and bloecke["diskussion"]: ...`:

```python
    if _zu_lang() and bloecke["begriffe_detail"]:
        bloecke["begriffe_detail"] = ""
```

ANNAHME: `kontext._kuerze_auf_budget` greift auf `bloecke["begriffe_detail"]` zu, also muss der Schlüssel in `_bloecke` immer gesetzt sein (ist er, ggf. `""`). Außerdem prüfen, ob `umriss()`/`umrisszeile()` die Blöcke aus `_REIHENFOLGE` nimmt (`kontext.py:1604` ja) — dann ist nichts weiter nötig.

`sprachen/en/texte.toml`, `["kontext"]`: `BEGRIFFE_DETAIL_KOPF = "Why you chose these terms:"`.

`fragen_ki.py` — Konstante hinter `_DISKUSSION_KOPF`:

```python
_BEGRUENDUNG_KOPF = "Warum die Gruppe diese Begriffe gewaehlt hat:"
```

`_nutzertext` ersetzen:

```python
def _nutzertext(begriffe: str, diskussion_text: str | None,
                begriffe_detail: list[dict] | None = None) -> str:
    """Der isolierte Nutzertext -- NUR die Begriffe, ihre Begruendungen aus
    dem Begriffsboard (Karte t_4517d4ad, ohne Zitat) und, falls vorhanden,
    die Verdichtung einer vorangegangenen Diskussion. Kein ``conn``, keine
    ``chat_id`` in der Signatur: dieser Aufruf kann strukturell nichts
    anderes sehen, insbesondere keine eigene Frage der Gruppe."""
    from interview_theater import begriffsboard

    liste = begriffe_modul.zerlege(begriffe)
    text = T._BEGRIFFE_KOPF + "\n" + "\n".join(f"- {b}" for b in liste)
    zeilen = begriffsboard.detail_zeilen(begriffe_detail or [])
    if zeilen:
        text += "\n\n" + T._BEGRUENDUNG_KOPF + "\n" + "\n".join(zeilen)
    if diskussion_text and diskussion_text.strip():
        text += "\n\n" + T._DISKUSSION_KOPF + "\n" + diskussion_text.strip()
    return text
```

In `starte`, neben `begriffe_feld = ...`:

```python
    from interview_theater import roadmap

    begriffe_detail = roadmap.begriffe_detail(stand)
```

und im Thread `nutzertext = _nutzertext(begriffe_feld or "", diskussion_text, begriffe_detail)`.

`sprachen/en/texte.toml`, `["fragen_ki"]`: `_BEGRUENDUNG_KOPF = "Why the group chose these terms:"`.

`tests/test_sprache_bitgleich.py`, Grund zu `"kontext._REIHENFOLGE"` um einen Satz ergänzen (nicht ersetzen):

```python
        " Karte t_4517d4ad (04.10.2026): \"begriffe_detail\" steht direkt "
        "hinter \"diskussion\" -- fuer Dortmund ebenfalls leer (keine Spalte "
        "begriffe_detail ohne Begriffsboard) und ersatzlos weg."
```

- [ ] **Step 4: Grün + Bitgleichheit**

Run: `$PY -m pytest tests/test_begriffe_detail_weitergabe.py tests/test_fragen_ki.py tests/test_kontext.py tests/test_festlegung_kontext.py tests/test_profil_bitgleich.py tests/test_sprache_bitgleich.py tests/test_simulation_hintergrund.py tests/test_prompt_audit.py -q`
Expected: PASS. Dortmund/Vorgabe byte-gleich: der Block ist dort leer.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/kontext.py interview_theater/fragen_ki.py interview_theater/sprachen/en/texte.toml tests/test_begriffe_detail_weitergabe.py tests/test_fragen_ki.py tests/test_sprache_bitgleich.py
git commit -m "Begriffsboard: Begruendungen je Begriff in Phase 2, ab Phase 4 und im isolierten KI-Fragen-Aufruf (Aufgabe 7)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: CoThinker-Tab zeigt das Board in Phase 1

**Files:**
- Modify: `interview_theater/web_daten.py` (neue Funktion neben `buehnenkarten` ~Z. 1356; zwei Schlüssel im Gruppen-Dict neben `"buehnenkarten"` ~Z. 1332)
- Modify: `interview_theater/web.py` (Konstanten neben `_TEXT_BUEHNE_LEER` ~Z. 1038; `_begriffsboard_html` vor `_buehne_html`; Weiche am Anfang von `_buehne_html` ~Z. 2912)
- Modify: `interview_theater/web_vereint.py` (`_VEREINT_JS`: neue Funktion + vier Aufrufstellen Z. 657–665, 987, 1165, 1245; `seite` Z. 1539; `_leiste_html` Z. 1492)
- Modify: `interview_theater/sprachen/en/texte.toml` (`["web"]`)
- Test: `tests/test_begriffsboard_web.py` (neu)

**Interfaces:**
- Consumes: `begriffsboard.lies`, `sortiert`, `top`, `schluessel`
- Produces:
  - `web_daten.begriffsboard(conn, chat_id) -> list[dict]` (sortiert, **ohne** `zitat`)
  - Gruppen-Daten-Schlüssel `"begriffsboard_zeigen": bool`, `"begriffsboard": list[dict]`
  - `web._begriffsboard_html(eintraege: list[dict]) -> str`
  - JS `istCoThinkerPhase()`; `#roadmap` trägt `data-begriffsboard="1"` **hinter** `data-aktive-phase` nur bei `workshop.diskussion_aktiv()`

- [ ] **Step 1: Failing tests** — `tests/test_begriffsboard_web.py`:

```python
"""Karte t_4517d4ad, Aufgabe 8: das Board im CoThinker-Tab (D9)."""

import json
import re
import sqlite3

import pytest

from interview_theater import db, repo, web, web_daten, web_vereint, workshop

CHAT = 1
BOARD = [
    {"begriff": "Musik", "nennungen": 9, "zustimmung": 2, "begruendung": "", "zitat": "",
     "doppelbedeutung": "", "status": "verworfen"},
    {"begriff": "Heimat", "nennungen": 2, "zustimmung": 2, "begruendung": "Wo die <Oma> kocht.",
     "zitat": "ZITAT-NIE-IM-WEB", "doppelbedeutung": "Ort und Gefuehl", "status": "favorit"},
    {"begriff": "Grenze", "nennungen": 1, "zustimmung": 0, "begruendung": "", "zitat": "",
     "doppelbedeutung": "", "status": "kandidat"},
]


@pytest.fixture
def pfad(tmp_path):
    p = str(tmp_path / "t.db")
    c = db.verbinde(p)
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    repo.lege_begriffsboard_an(c, CHAT, json.dumps(BOARD), "sovereign", 0)
    c.close()
    return p


def _ro(pfad):
    c = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def test_web_daten_liest_sortiert_und_ohne_zitat(pfad):
    eintraege = web_daten.begriffsboard(_ro(pfad), CHAT)
    assert [e["begriff"] for e in eintraege] == ["Heimat", "Grenze", "Musik"]
    assert all("zitat" not in e for e in eintraege)


def test_web_daten_ohne_tabelle_ist_leer(tmp_path):
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    assert web_daten.begriffsboard(c, CHAT) == []


def test_html_ist_funktional_mit_data_attributen(pfad):
    html = web._begriffsboard_html(web_daten.begriffsboard(_ro(pfad), CHAT))
    assert 'data-ansicht="begriffsboard"' in html
    assert re.search(r'<li data-begriff="Heimat" data-status="favorit"[^>]*data-top="1"', html)
    assert re.search(r'<li data-begriff="Musik" data-status="verworfen"(?![^>]*data-top)[^>]*>', html)
    assert "<details>" in html and "Ort und Gefuehl" in html
    assert "&lt;Oma&gt;" in html and "<Oma>" not in html
    assert "ZITAT-NIE-IM-WEB" not in html
    assert "style=" not in html
    assert re.search(r"\son\w+=", html) is None


def test_leeres_board_hat_den_leertext():
    html = web._begriffsboard_html([])
    assert 'data-ansicht="begriffsboard"' in html and "<li" not in html


def test_buehne_html_weicht_in_phase_1_aufs_board_aus():
    html = web._buehne_html({"begriffsboard_zeigen": True, "begriffsboard": [
        {"begriff": "Mut", "nennungen": 1, "zustimmung": 0, "begruendung": "",
         "doppelbedeutung": "", "status": "kandidat"},
    ]})
    assert 'data-begriff="Mut"' in html


def test_buehne_html_ohne_schalter_wie_bisher():
    html = web._buehne_html({"buehnenkarten": []})
    assert "data-ansicht" not in html


def test_js_laesst_den_cothinker_in_phase_1_mit_board_zu():
    js = web_vereint._VEREINT_JS
    assert "function istCoThinkerPhase()" in js
    assert "rm.dataset.begriffsboard === '1'" in js
    lade = js[js.index("function ladeBuehne()"):]
    assert lade.index("if (!istCoThinkerPhase()) { return; }") < lade.index("fetch(")
    assert "istPhase4()" not in js


def test_roadmap_traegt_das_board_merkmal_nur_mit_profil(monkeypatch):
    daten = [{"nummer": 1, "bezeichnung": "Terms", "aktiv": True, "aufgaben": []}]
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    ohne = web_vereint._leiste_html(daten)
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    mit = web_vereint._leiste_html(daten)
    assert "data-begriffsboard" not in ohne
    assert re.search(r'id="roadmap" data-aktive-phase="1" data-begriffsboard="1"', mit)
```

ANNAHME: `web_vereint._leiste_html(roadmapdaten)` verkraftet diese Minimal-Daten. Vor dem Schreiben die tatsächlich gelesenen Schlüssel in `_leiste_html` (Z. 1396–1496) nachsehen und das Test-Dict auf genau diese Schlüssel anpassen (z. B. `erledigt`, `gesamt`, `aufgaben[*].zustand`).

Zusätzlich einen Seiten-Test in derselben Datei, der über den vorhandenen HTTP-Aufbau aus `tests/test_web_vereint.py` (Fixture `aufbau`, Helfer `_hole`) läuft — beide Helfer in die neue Datei kopieren, nicht importieren:

```python
def test_teil_buehne_liefert_das_board_in_phase_1(aufbau, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    basis, token, pfad_ = aufbau
    c = db.verbinde(pfad_)
    repo.setze_phase(c, CHAT_AUFBAU, 1)
    repo.lege_begriffsboard_an(c, CHAT_AUFBAU, json.dumps(BOARD), "sovereign", 0)
    _status, teil, _kopf = _hole(f"{basis}/g/{token}/teil/buehne")
    assert 'data-begriff="Heimat"' in teil
    _status, seite, _kopf = _hole(f"{basis}/g/{token}")
    assert re.search(r'<button[^>]*data-tab="buehne"(?![^>]*hidden)', seite)


def test_teil_buehne_ohne_profil_in_phase_1_zeigt_kein_board(aufbau, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    basis, token, pfad_ = aufbau
    c = db.verbinde(pfad_)
    repo.setze_phase(c, CHAT_AUFBAU, 1)
    repo.lege_begriffsboard_an(c, CHAT_AUFBAU, json.dumps(BOARD), "sovereign", 0)
    _status, teil, _kopf = _hole(f"{basis}/g/{token}/teil/buehne")
    assert "data-begriff" not in teil
```

ANNAHME: Der Webserver im `aufbau`-Fixture läuft im selben Prozess (Thread), sodass `monkeypatch.setattr(workshop, ...)` greift; `CHAT_AUFBAU` = die `CHAT`-Konstante aus `tests/test_web_vereint.py`. Läuft er als Subprozess, stattdessen `monkeypatch.setenv("IT_WORKSHOP", "padua-2026")` vor dem Fixture-Start nutzen (Muster: `tests/e2e/test_web_diskussion_e2e.py`, Fixture `lauf`).

- [ ] **Step 2: Rot**

Run: `$PY -m pytest tests/test_begriffsboard_web.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementierung**

`web_daten.py`, neben `buehnenkarten`:

```python
def begriffsboard(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """Das read-only Gegenstueck zu ``begriffsboard.aktuelles`` (CoThinker in
    Phase 1, Karte t_4517d4ad) -- sortiert wie der Top-5-Vorschlag
    (``begriffsboard.sortiert``) und OHNE ``zitat``: auf der Seite steht kein
    Zitat aus dem Mitschnitt (AGENTS.md, "Drei Grenzen"). Fehlt die Tabelle
    (Deploy vor Bot-Neustart), eine leere Liste."""
    try:
        zeile = conn.execute(
            "SELECT json FROM begriffsboard WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return []
    from interview_theater import begriffsboard as _begriffsboard

    return [
        {k: v for k, v in eintrag.items() if k != "zitat"}
        for eintrag in _begriffsboard.sortiert(_begriffsboard.lies(zeile["json"] if zeile else None))
    ]
```

Im Gruppen-Dict hinter `"buehnenkarten": buehnenkarten(conn, chat_id),`:

```python
        # Das Begriffsboard (CoThinker in Phase 1, Karte t_4517d4ad) -- nur
        # in Phase 1 und nur mit Profil ``diskussion.aktiv``; Dortmund liest
        # es nie.
        "begriffsboard_zeigen": stand.get("phase") == 1 and _workshop.diskussion_aktiv(),
        "begriffsboard": (
            begriffsboard(conn, chat_id)
            if stand.get("phase") == 1 and _workshop.diskussion_aktiv() else []
        ),
```

ANNAHME: In dieser Funktion heißen der Arbeitsstand `stand` (ein Dict mit `.get`) und das Workshop-Modul `_workshop` (beides in den Nachbarzeilen benutzt: `stand.get("fragen")`, `_workshop.workbench_bearbeitbar()`). Vor dem Einfügen lesen.

`web.py`, neben `_TEXT_BUEHNE_LEER`:

```python
#: Das Begriffsboard im CoThinker-Tab (Phase 1, Karte t_4517d4ad).
_TEXT_BOARD_LEER = "Hier erscheinen die Begriffe, die ihr in der Diskussion nennt."
_TEXT_BOARD_WARUM = "Warum"
_TEXT_BOARD_DOPPEL = "Doppelbedeutung: {doppelbedeutung}"
```

`sprachen/en/texte.toml`, `["web"]`:

```toml
_TEXT_BOARD_LEER = "The terms you mention in the discussion will appear here."
_TEXT_BOARD_WARUM = "Why"
_TEXT_BOARD_DOPPEL = "Double meaning: {doppelbedeutung}"
```

`web.py`, vor `_buehne_html`:

```python
def _begriffsboard_html(eintraege: list[dict]) -> str:
    """Das Begriffsboard im CoThinker-Tab (Phase 1, Karte t_4517d4ad, D9):
    eine Liste in ``begriffsboard.sortiert``-Ordnung, die Top 5 mit
    ``data-top="1"``, Begruendung und Doppelbedeutung aufklappbar. Nur
    funktionales Markup mit ``data-*`` -- die Gestaltung macht die UX-Karte.
    Kein Zitat (``web_daten.begriffsboard`` laesst es weg), kein
    ``style=``, kein ``on…=`` (CSP)."""
    from interview_theater import begriffsboard as _begriffsboard

    if not eintraege:
        return (
            '<div id="buehne-panel" data-ansicht="begriffsboard">'
            f'<p class="buehne-leer">{_t(T._TEXT_BOARD_LEER)}</p></div>'
        )
    oben = {_begriffsboard.schluessel(e["begriff"]) for e in _begriffsboard.top(eintraege)}
    zeilen = []
    for eintrag in _begriffsboard.sortiert(eintraege):
        begriff = html.escape(eintrag["begriff"], quote=True)
        top_merkmal = (' data-top="1"'
                       if _begriffsboard.schluessel(eintrag["begriff"]) in oben else "")
        teile = []
        if eintrag.get("begruendung"):
            teile.append(
                f'<p data-feld="begruendung">{html.escape(eintrag["begruendung"])}</p>'
            )
        if eintrag.get("doppelbedeutung"):
            teile.append(
                '<p data-feld="doppelbedeutung">'
                f'{_t(T._TEXT_BOARD_DOPPEL.format(doppelbedeutung=eintrag["doppelbedeutung"]))}</p>'
            )
        mehr = (f'<details><summary>{_t(T._TEXT_BOARD_WARUM)}</summary>{"".join(teile)}</details>'
                if teile else "")
        zeilen.append(
            f'<li data-begriff="{begriff}" data-status="{html.escape(eintrag["status"])}" '
            f'data-zustimmung="{int(eintrag["zustimmung"])}" '
            f'data-nennungen="{int(eintrag["nennungen"])}"{top_merkmal}>'
            f'<span class="begriff">{html.escape(eintrag["begriff"])}</span>{mehr}</li>'
        )
    return (
        '<div id="buehne-panel" data-ansicht="begriffsboard">'
        f'<ol class="begriffsboard">{"".join(zeilen)}</ol></div>'
    )
```

ANNAHME: `_t(text)` HTML-escaped den Text (Kommentar `web.py:2968`); falls nicht, `html.escape` verwenden.

Am Anfang von `_buehne_html` (vor `karten = ...`):

```python
    if daten.get("begriffsboard_zeigen"):
        # Phase 1 (Karte t_4517d4ad): der CoThinker zeigt das Begriffsboard
        # statt der Buehnenkarten -- eine Renderfunktion fuer Seite UND Poll.
        return _begriffsboard_html(daten.get("begriffsboard") or [])
```

`web_vereint._VEREINT_JS`: `function istPhase4() {...}` (Z. 657–660) **ersetzen** durch

```javascript
  // Karte t_4517d4ad: der CoThinker steht in Phase 4 (Buehnenkarten) UND in
  // Phase 1, wenn das Profil das Begriffsboard faehrt (``#roadmap`` traegt
  // dann ``data-begriffsboard="1"``, gesetzt von ``_leiste_html``).
  function istCoThinkerPhase() {
    var rm = document.getElementById('roadmap');
    if (!rm) { return false; }
    var p = rm.dataset.aktivePhase;
    return p === '4' || (p === '1' && rm.dataset.begriffsboard === '1');
  }
```

und die vier Aufrufe `istPhase4()` → `istCoThinkerPhase()`: in `lies` (`if (teile[i] === 'buehne' && !istCoThinkerPhase()) { continue; }`), im Roadmap-Takt (`var p4 = istCoThinkerPhase();`), in `buehneAktiv` und in `ladeBuehne` (`if (!istCoThinkerPhase()) { return; }`). Die Kommentare dort, die „Phase 4" als einzige CoThinker-Phase nennen, um „(oder Phase 1 mit Begriffsboard)" ergänzen. Danach `grep -n "istPhase4" interview_theater/web_vereint.py` → keine Treffer.

`web_vereint.seite` (Z. 1539):

```python
    phase = (daten.get("arbeitsstand") or {}).get("phase")
    # Der CoThinker-Tab ist sichtbar in Phase 4 -- und in Phase 1, wenn das
    # Profil das Begriffsboard faehrt (Karte t_4517d4ad). Derselbe Zustand,
    # den ``istCoThinkerPhase()`` im Browser bei jedem Takt neu herstellt.
    phase4 = phase == 4 or (phase == 1 and workshop.diskussion_aktiv())
```

(`workshop` ist in `seite` schon lokal importiert, Z. 1520.)

`_leiste_html`, die `<details class="roadmap" ...>`-Zeile:

```python
        f'<details class="roadmap" id="roadmap" data-aktive-phase="{aktiv["nummer"]}"'
        f'{_board_merkmal()}>'
```

mit, oberhalb von `_leiste_html`:

```python
def _board_merkmal() -> str:
    """``data-begriffsboard="1"`` am ``#roadmap``, wenn das Profil das
    Begriffsboard faehrt (Karte t_4517d4ad) -- HINTER ``data-aktive-phase``,
    damit ``tests/test_web_vereint.py`` dessen Regex unveraendert findet.
    Ohne Profil: nichts, Dortmund bleibt byte-gleich."""
    from interview_theater import workshop

    return ' data-begriffsboard="1"' if workshop.diskussion_aktiv() else ""
```

- [ ] **Step 4: Grün + Web-Nachbarn + Bitgleichheit**

Run: `$PY -m pytest tests/test_begriffsboard_web.py tests/test_web_vereint.py tests/test_buehne_nav_js.py tests/test_buehne_tafel_struktur.py tests/test_web_vereint_cothinker_status.py tests/test_werkbank_bitgleich.py tests/test_web_dashboard_en.py tests/test_web.py -q`
Expected: PASS (die Bitgleich-Fixtures gibt es nur für Vorgabe und Dortmund — dort ist `diskussion_aktiv()` falsch).

- [ ] **Step 5: Commit**

```bash
git add interview_theater/web_daten.py interview_theater/web.py interview_theater/web_vereint.py interview_theater/sprachen/en/texte.toml tests/test_begriffsboard_web.py
git commit -m "Begriffsboard: CoThinker-Tab zeigt das Board in Phase 1, funktionales Markup ohne Zitat (Aufgabe 8)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Onboarding-Satz an Phaseneintritt und Erstkontakt

**Files:**
- Modify: `interview_theater/begriffsboard.py` (Konstante `_TEXT_EINSTIEG`, Funktion `sende_einstieg`)
- Modify: `interview_theater/sprachen/en/texte.toml` (`["begriffsboard"]`)
- Modify: `interview_theater/knoepfe/stationen.py` (`eintritt_in_phase`, Zweig `PHASE_BEGRIFFE` ~Z. 327)
- Modify: `interview_theater/ablauf.py` (`antworte` ~Z. 891 und hinter `_nach_dem_senden` ~Z. 939)
- Test: `tests/test_begriffsboard_einstieg.py` (neu)

**Interfaces:**
- Produces: `begriffsboard.sende_einstieg(conn, tg, e, chat_id: int) -> bool` (True = gesendet), `begriffsboard._TEXT_EINSTIEG`

- [ ] **Step 1: Failing tests** — `tests/test_begriffsboard_einstieg.py`:

```python
"""Karte t_4517d4ad, Aufgabe 9: der Onboarding-Satz (D10)."""

import pytest

from interview_theater import ablauf, begriffsboard, db, einstellungen, repo, sprache, workshop
from interview_theater.knoepfe import stationen

CHAT = 1


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


class _TG:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append(text)
        return 100 + len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return self.sende(chat_id, text)

    def tippt(self, chat_id):
        pass


def test_englischer_wortlaut_im_padua_profil(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    try:
        assert begriffsboard.T._TEXT_EINSTIEG == (
            "Lay one phone in the middle -- it listens. Open the CoThinker tab "
            "on a second phone: the terms you mention appear there."
        )
    finally:
        monkeypatch.delenv(workshop.VARIABLE)
        workshop.vergiss()
        sprache.vergiss()


def test_ohne_profil_kein_satz(conn, einst):
    tg = _TG()
    assert begriffsboard.sende_einstieg(conn, tg, einst, CHAT) is False
    assert tg.gesendet == []


def test_mit_profil_satz_und_mitschrift(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    tg = _TG()
    assert begriffsboard.sende_einstieg(conn, tg, einst, CHAT) is True
    assert tg.gesendet == [begriffsboard.T._TEXT_EINSTIEG]
    assert repo.hat_bot_nachricht(conn, CHAT)


def test_eintritt_in_phase_1_sendet_den_satz(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    repo.setze_phase(conn, CHAT, 1)
    tg = _TG()
    stationen.eintritt_in_phase(conn, tg, None, einst, CHAT, 1)
    assert begriffsboard.T._TEXT_EINSTIEG in tg.gesendet


def test_eintritt_ohne_profil_ohne_satz(conn, einst):
    repo.setze_phase(conn, CHAT, 1)
    tg = _TG()
    stationen.eintritt_in_phase(conn, tg, None, einst, CHAT, 1)
    assert begriffsboard.T._TEXT_EINSTIEG not in tg.gesendet


def test_erste_antwort_einer_neuen_gruppe_bekommt_den_satz_dahinter(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(ablauf, "_erfrage_antwort", lambda *a, **k: "Willkommen!")
    repo.merke_nachricht(conn, CHAT, 1, "Gruppe", 0, "text", "Hallo", repo._jetzt())
    tg = _TG()
    ablauf.antworte(conn, tg, object(), einst, CHAT, list(repo.unbeantwortete(conn, CHAT)))
    assert tg.gesendet[-1] == begriffsboard.T._TEXT_EINSTIEG
    assert any("Willkommen!" in t for t in tg.gesendet[:-1])


def test_zweite_antwort_ohne_satz(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(ablauf, "_erfrage_antwort", lambda *a, **k: "Weiter so.")
    repo.merke_nachricht(conn, CHAT, 1, "gruppe1", 1, "text", "frueher", repo._jetzt())
    repo.merke_nachricht(conn, CHAT, 2, "Gruppe", 0, "text", "Noch was", repo._jetzt())
    tg = _TG()
    ablauf.antworte(conn, tg, object(), einst, CHAT, list(repo.unbeantwortete(conn, CHAT)))
    assert begriffsboard.T._TEXT_EINSTIEG not in tg.gesendet
```

ANNAHME: `ablauf.antworte` erreicht mit gepatchtem `_erfrage_antwort` den Versand (`befehle.behandle` → False für „Hallo"; `_zug_faellt_aus` → False ohne Szene/erwartete Antwort; `_sende_mit_leiste` braucht ggf. mehr von `tg` — fehlende Methoden der Attrappe ergänzen, Vorbild `tests/test_ablauf.py`). ANNAHME: `eintritt_in_phase(..., klm=None, ...)` läuft ohne Modell durch (Docstring: „Ohne Modell (Tests, Skripte) bleibt der feste Rahmen") und `_biete_modellwahl_wenn_faellig` kommt mit `_TG` aus; sonst `_TG` um die fehlende Methode ergänzen.

- [ ] **Step 2: Rot**

Run: `$PY -m pytest tests/test_begriffsboard_einstieg.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementierung** — `begriffsboard.py`, Konstante zu den Textkonstanten (vor `T = ...`):

```python
#: Der Einstiegssatz (D10) -- deterministisch, nur mit ``diskussion.aktiv``.
_TEXT_EINSTIEG = (
    "Legt ein Handy in die Mitte -- es hoert zu. Oeffnet auf einem zweiten "
    "Handy den Tab CoThinker: dort erscheinen die Begriffe, die ihr nennt."
)
```

Funktion anhängen:

```python
def sende_einstieg(conn, tg, e, chat_id: int) -> bool:
    """Der Einstiegssatz zum Mithoeren (D10), dort, wo der Bot den Knopf
    "Start listening" ankuendigt: beim Eintritt in Phase 1
    (``knoepfe/stationen.eintritt_in_phase``) und hinter der ersten Antwort
    einer neuen Gruppe (``ablauf.antworte``). Als Bot-Zeile mitgeschrieben,
    damit der naechste Gespraechszug ihn im Fenster sieht. Ohne Profil:
    nichts."""
    if not workshop.diskussion_aktiv():
        return False
    text = T._TEXT_EINSTIEG
    message_id = tg.sende(chat_id, text)
    repo.merke_nachricht(
        conn, chat_id, message_id, e.bot_name, 1, "text", text, repo._jetzt(),
    )
    return True
```

`sprachen/en/texte.toml`, `["begriffsboard"]`:

```toml
_TEXT_EINSTIEG = "Lay one phone in the middle -- it listens. Open the CoThinker tab on a second phone: the terms you mention appear there."
```

`knoepfe/stationen.eintritt_in_phase`, im Zweig `if nummer == PHASE_BEGRIFFE:` direkt nach `_biete_modellwahl_wenn_faellig(conn, tg, e, chat_id)`:

```python
        # Karte t_4517d4ad (D10): der deterministische Einstiegssatz zum
        # Mithoeren -- vor dem modellgeschriebenen Einstieg, der im Thread
        # laeuft. Ohne Profil ``diskussion.aktiv`` sendet er nichts.
        from interview_theater import begriffsboard

        begriffsboard.sende_einstieg(conn, tg, e, chat_id)
```

`ablauf.antworte`: direkt nach `versand_erfolgreich = False` (vor `try:`):

```python
    # Karte t_4517d4ad (D10): die erste Antwort einer neuen Gruppe bekommt
    # den Einstiegssatz zum Mithoeren dahinter -- VOR dem Zug gemessen, danach
    # gibt es eine Bot-Nachricht.
    erstkontakt_zug = not repo.hat_bot_nachricht(conn, chat_id)
```

direkt nach `_nach_dem_senden(conn, tg, e, chat_id, message_id, text)`:

```python
        if erstkontakt_zug and phasen.aktuelle(conn, chat_id) == 1:
            _sende_board_einstieg(conn, tg, e, chat_id)
```

und unter `_nach_dem_senden` die Hilfsfunktion:

```python
def _sende_board_einstieg(conn, tg, e, chat_id: int) -> None:
    """Der Einstiegssatz des Begriffsboards hinter der ersten Antwort (Karte
    t_4517d4ad). Ein Fehlschlag darf die schon verschickte Antwort nicht
    nachtraeglich zum Fehlerfall machen."""
    try:
        from interview_theater import begriffsboard

        begriffsboard.sende_einstieg(conn, tg, e, chat_id)
    except Exception:
        log.exception("Einstiegssatz des Begriffsboards fehlgeschlagen, chat_id=%s", chat_id)
```

ANNAHME: `phasen` ist in `ablauf.py` importiert (`phasen.aktuelle` wird dort schon benutzt, ~Z. 1041) und `repo.hat_bot_nachricht` existiert (`repo.py:3449`).

- [ ] **Step 4: Grün + Nachbarn**

Run: `$PY -m pytest tests/test_begriffsboard_einstieg.py tests/test_ablauf.py tests/test_fragen_ki.py tests/test_phasenende_eine_nachricht.py tests/test_sprache_bitgleich.py -q`
Expected: PASS (ohne Profil ändert sich nichts).

- [ ] **Step 5: Commit**

```bash
git add interview_theater/begriffsboard.py interview_theater/sprachen/en/texte.toml interview_theater/knoepfe/stationen.py interview_theater/ablauf.py tests/test_begriffsboard_einstieg.py
git commit -m "Begriffsboard: Einstiegssatz zum Mithoeren an Phase-1-Eintritt und Erstkontakt (Aufgabe 9)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: e2e — Start → Segment → Discussion done → Board im CoThinker → Top-5-Vorschlag

**Files:**
- Modify: `tests/e2e/test_web_diskussion_e2e.py`

**Interfaces:**
- Consumes: alles Obige über den echten Bot-/Webserver-Thread (Fixture `lauf`)

Zur Reihenfolge siehe „Bewusste Abweichungen", Punkt 2: im Browser gibt es nur `cap`-Schnitte, das Board entsteht deshalb im Schlusslauf nach „Discussion done".

- [ ] **Step 1: `LLMAttrappe` erweitern** — Attribut im `__init__`: `self.board = []`; in `schema`, vor dem `with self._sperre: self.nutzertexte.append(...)`:

```python
        if art == "begriffsboard":
            # Karte t_4517d4ad: der Boardlauf -- ``self.board`` setzt der
            # jeweilige Test; leer heisst: der heutige Satz bleibt.
            return {"board": list(self.board)}
```

- [ ] **Step 2: Bestehenden Test anpassen** — in `test_diskussion_voller_ablauf_im_browser`, Schritt (1), nach `expect(seite.locator(".blase.bot").first).to_contain_text(text_diskussion_an)` und **vor** `bot_blasen_vor_start = ...` den Einstiegssatz abwarten (sonst zählt die Bot-Blasen-Zahl je nach Poll-Takt mit oder ohne ihn):

```python
    # Karte t_4517d4ad (D10): hinter der Begruessung steht der Einstiegssatz.
    expect(
        seite.locator(".blase.bot").filter(has_text=begriffsboard.T._TEXT_EINSTIEG).first
    ).to_be_visible(timeout=GEDULD_MS)
```

und `begriffsboard` in den Import-Block `from interview_theater import (...)` aufnehmen. Der Rest des Tests bleibt: `klm.board` ist leer, also kommt nach „Discussion done" der heutige Satz.

- [ ] **Step 3: Neuer Test** — am Dateiende:

```python
def test_begriffsboard_im_cothinker_und_top5_vorschlag(lauf, seite, monkeypatch):
    """Karte t_4517d4ad: Start -> Segment -> "Discussion done" -> Schlusslauf
    -> Board-Eintrag im CoThinker-Panel -> Top-5-Vorschlag mit EINEM Knopf
    "Take these". Der Zwischenlauf nach einem Pausenschnitt ist im Browser
    nicht herstellbar (Dauerton, nur ``cap``-Schnitte, siehe Dateikopf) und
    in ``tests/test_begriffsboard_mithoeren.py`` am echten ``aufnahme``-Pfad
    getestet."""
    _basis, _token, _pfad, klm = lauf
    # Schlusslauf schon ab einem Zeichen (die Segmente tragen nur TRANSKRIPT).
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "1")
    klm.board = [{
        "begriff": "ankamen", "nennungen": 2, "zustimmung": 2,
        "begruendung": "Das Ankommen hier verbindet uns.",
        "zitat": "als wir hier ankamen", "doppelbedeutung": "", "status": "favorit",
    }]
    knopf_text = knoepfe.T._TEXT_BOARD_UEBERNEHMEN_KNOPF

    seite.fill("#eingabe", "Hallo, wir sind da!")
    seite.click("#senden")
    expect(seite.locator(".blase.bot").first).to_contain_text(web_chat.T._TEXT_DISKUSSION_AN)

    seite.click("#diskussion")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "1")
    segment_blase = seite.locator(".blase.gruppe.sprache").filter(has_text=TRANSKRIPT)
    expect(segment_blase.first).to_be_visible(timeout=GEDULD_MS)

    seite.click("#diskussion-beenden")
    expect(seite.locator("#diskussion")).to_have_attribute("data-laeuft", "0")

    # Der Top-5-Vorschlag ersetzt den heutigen Satz und traegt genau einen Knopf.
    vorschlag = seite.locator(".blase.bot").filter(has_text="1. ankamen")
    expect(vorschlag.first).to_be_visible(timeout=GEDULD_MS)
    expect(seite.get_by_role("button", name=knopf_text)).to_have_count(1)
    assert seite.locator(".blase.bot").filter(
        has_text=aufnahme.T._TEXT_DISKUSSION_FERTIG_BEGRIFFE).count() == 0

    # Der CoThinker-Tab ist in Phase 1 da und zeigt den Board-Eintrag als Top.
    tab = seite.locator('.tabs button[data-tab="buehne"]')
    expect(tab).to_be_visible(timeout=GEDULD_MS)
    tab.click()
    eintrag = seite.locator('#tab-buehne li[data-begriff="ankamen"][data-top="1"]')
    expect(eintrag).to_be_visible(timeout=GEDULD_MS)
    assert seite.locator("#tab-buehne").inner_text().count("als wir hier ankamen") == 0
```

`knoepfe` in den Import-Block aufnehmen (`from interview_theater import (..., knoepfe, ...)`).

ANNAHME: Der Webchat rendert Inline-Knöpfe als `<button>` mit der Beschriftung als zugänglichem Namen (so in `tests/e2e/test_web_chat_e2e.py`). Falls nicht, den Selektor aus jener Datei übernehmen. ANNAHME: Der CoThinker-Tab erscheint erst mit dem nächsten Roadmap-Takt nach dem Phase-1-Stand; die Gruppe steht in der `lauf`-Fixture schon in Phase 1 (sonst wäre `#diskussion` unsichtbar), der Tab ist also schon beim ersten Rendern sichtbar.

- [ ] **Step 4: Laufen lassen**

Run: `$E2E -m pytest tests/e2e/test_web_diskussion_e2e.py -q`
Expected: 2 passed. (Ohne Playwright wird die Datei übersprungen — dann im Abschlussbericht ausdrücklich „e2e nicht gelaufen" schreiben, nicht „grün".)

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_web_diskussion_e2e.py
git commit -m "Begriffsboard: e2e Start -> Segment -> Discussion done -> Board im CoThinker -> Top-5-Vorschlag (Aufgabe 10)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: AGENTS.md, volle Suite, Profilprüfung

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: AGENTS.md**

1. Modultabelle (alphabetisch nicht nötig — hinter der Zeile `kuerzung.py` oder hinter `aufnahme.py`):

```markdown
| `begriffsboard.py` | Das Begriffsboard der Phase 1 (04.10.2026, Karte t_4517d4ad): laufend mithören wie der Brainstorm in Phase 4 (`brainstorm.soll_reagieren` **unverändert**, eigene Zähler über `aufnahme.diskussion = 1`, eigene Sperre), ein Schema-Aufruf je qualifizierendem Segment im eigenen Thread (Opus nach Einwilligung, sonst Kimi), Tabelle `begriffsboard` (nur anhängen, letzter Stand gilt). Validiert **im Code**: Begriff muss im Transkript stehen, Zitat über `zitat.pruefe`. **Der Lauf kennt kein `tg`** — keine Chatzeile beim Mithören. Bei „Discussion done" der Top-5-Vorschlag mit EINEM Knopf „Take these"; `schreibe_detail` füllt `arbeitsstand.begriffe_detail` auf jedem Schreibweg von `begriffe` (AST-Test `tests/test_begriffe_detail_wege.py`). `detail_zeilen` ist die eine Prompt-Form für `kontext` (Phase 2, ≥ 4) und `fragen_ki` |
```

2. Schichten-Tabelle „Fachlogik": `begriffsboard.py` ergänzen.
3. „Wo man anfängt": `| Was steht auf dem Begriffsboard (und warum nicht)? | \`aufnahme._diskussion_abschliessen\` → \`begriffsboard.nach_segment\` → \`soll_laufen\` → \`_lauf_einmal\` → \`validiere\` |`
4. Den Absatz/die Tabellenzeile zu `aufnahme.py`/Phase 1 suchen (`grep -n "Hintergrund-Diskussion\|diskussion.py\|Mithören\|mithoeren" AGENTS.md`) und dort „ohne CoThinker-Karte"/„nur Material" so ergänzen, dass Phase 1 seit 04.10.2026 laufend das Begriffsboard schreibt (Birk 15:15: Phase 1 und 4 einheitlich automatisch) — der Rest (kein Zug, kein Erkenner) gilt weiter.
5. Den CoThinker-Abschnitt („Die Gestaltung"/„Eine Oberfläche je Gruppe" — `grep -n "CoThinker\|istPhase4\|buehne" AGENTS.md`): CoThinker auch in Phase 1 bei `diskussion.aktiv`, `#roadmap[data-begriffsboard]`, `istCoThinkerPhase()`.
6. In „Was bewusst fehlt", Übergaben Padua: neue Liste „Die Übergaben der Karte t_4517d4ad (Begriffsboard, 04.10.2026)" mit:
   - **Ungemessen:** kein bezahlter Lauf des neuen Prompts `begriffsboard.md` (DE/EN) gegen das echte Modell; keine Korpusfälle; ob Kimi das verschachtelte Schema im erzwungenen Modus annimmt, ist nur am Muster `erkenner` (Liste von Objekten) plausibel, nicht gemessen.
   - Die Schwellen sind die des Brainstorms (Erwachsenen-Meetings, `brainstorm.py`-Kopf), nicht an Schüler-Diskussionen gemessen.
   - Ein leeres Ergebnis ersetzt nie ein volles Board — dann rückt die Markierung nicht vor, und der nächste Pausenschnitt über der Schwelle löst erneut aus.
   - Der Merkplatz für den Vorschlag lebt im Prozess (wie `vorschlagssperre`): ein Neustart zwischen „Discussion done" und Ende des Schlusslaufs verliert den Vorschlag.
   - Das Board fließt nicht in die Bühnenkarten der Phase 4 (`buehnenkarte._kontext_phasen_1_bis_3`) — nur `begriffe_detail` über `kontext.baue`.
   - Die CoThinker-Darstellung ist ungestaltet (`data-*`, UX-Karte).

- [ ] **Step 2: Volle Suite (lang, > 800 s) — bis zum Ende abwarten und die Summenzeile lesen, bevor irgendetwas als fertig gemeldet wird**

Run: `$PY -m pytest -q --ignore=tests/e2e > .suite.log 2>&1; echo EXIT=$? >> .suite.log`
Die Suite lief zuletzt 835 s (Merge-Bericht t_b2d4ac2c), ein einzelner Bash-Aufruf bricht nach 600 s ab, und `pytest-xdist` ist im Interpreter nicht installiert (geprüft 04.10.2026). Deshalb im Hintergrund starten (`run_in_background`), auf das Prozessende warten, dann die letzten Zeilen von `.suite.log` lesen (Summenzeile + `EXIT=`). Nie eine Teilausgabe als Ergebnis melden. `.suite.log` bleibt ungetrackt.
Expected: Summenzeile ohne `failed`/`error`, `EXIT=0`. Jeder Fehler wird behoben. Hält ihn jemand für vorbestehend, muss er das belegen: der Plan-Commit dieses Branches ist die Basis; den fehlschlagenden Test gegen die Basisfassung des berührten Codes lesen (`git diff <plan-commit> -- <datei>`) und Befund samt Ausgabe in den Bericht schreiben — kein `git stash` (geteilter Stapel, siehe Umgebung).

Run: `$E2E -m pytest tests/e2e/test_web_diskussion_e2e.py -q`
Expected: 2 passed.

- [ ] **Step 3: Profilprüfung** (CLI gelesen in `scripts/pruefe_profil.py:389-407`)

Run: `$PY -m scripts.pruefe_profil dortmund-2026 && $PY -m scripts.pruefe_profil padua-2026 && $PY -m scripts.pruefe_profil --vorgabe`
Expected: je „<name>: in Ordnung", Exit 0.

Run: `$PY -m pytest tests/test_pruefe_sprache.py tests/test_profil_bitgleich.py tests/test_sprache_bitgleich.py -q`
Expected: PASS (Padua frei von Deutsch — siehe ANNAHME in Aufgabe 3).

- [ ] **Step 4: Commit + sauberer Baum**

```bash
git add AGENTS.md
git commit -m "AGENTS.md: Begriffsboard der Phase 1 -- Modul, Einstieg, Uebergaben (Aufgabe 11)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git status --short
```

Expected: leer bis auf ungetrackte `.cc-*`/`.superpowers-*`. **Kein Push, kein Merge.**

---

## Selbstprüfung gegen die Karte

| Kartenpunkt | Aufgabe |
|---|---|
| 1. Brainstorm-Mechanik in Phase 1, ein Lauf je Gruppe | 3 (Sperre, `soll_laufen`), 4 (Einhängen) |
| 1. Eingabe Transkripte + Board, Opus/Kimi | 3 (`_nutzertext`, `modellwahl`) |
| 1. Ausgabe-JSON, Zitate geprüft, nichts erfinden | 2 (`validiere`, Mutant), 3 (Schema) |
| 1. Tabelle `begriffsboard`, Historie, kein Chattext | 1, 3, 4 (D5-Mutant) |
| 2. CoThinker zeigt Board, sortiert, Top 5, aufklappbar, Poll | 2 (`sortiert`/`top`), 8 |
| 3. Discussion done → Top 5 als Knopf/Vorschlag, frei tippen | 6 |
| 3. `begriffe_detail` beim Speichern | 5 (alle Wege), 6 („Take these") |
| 4. Weitergabe Phase 2, isolierter KI-Aufruf, Phase 4+ | 7 |
| 5. Gesamtverdichtung bleibt | 4, 6 (`test_gesamtverdichtung_startet_unabhaengig`) |
| 6. Onboarding EN | 9 |
| Abnahme: Tests inkl. Mutanten | 2, 3, 4, 6, 7 |
| Abnahme: e2e | 10 |
| Abnahme: volle Suite, `pruefe_profil` beide Profile, Commit je Schritt, kein Push | 11, jede Aufgabe |
