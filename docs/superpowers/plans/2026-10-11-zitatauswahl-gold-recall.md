# InScribe Zitatauswahl: Gold-Korpus, Recall@10, Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Zitatauswahl der Schärfung (`schaerfung.py`) an einem Gold-Korpus
aus Padua messen (Recall@10 je Ziel) und nur dann einen Fix übernehmen, wenn
Recall@10 messbar steigt.

**Architecture:** Ein Messskript `scripts/zitatauswahl.py` baut den Gold-Korpus
`korpus/zitatauswahl_gold.jsonl` aus einer handgeschriebenen Quelldatei (16
Plakatkarten) und einer `VACUUM INTO`-Kopie von `betrieb/padua.db`. Es misst
die historische Liste (B0, ohne Modell) und Neu-Läufe der Schärfung je Gold-Ziel
direkt über den Claude-Proxy (B1, I-a, I-b; 0 CHF, ohne Rückfall). Ergebnisse
liegen als JSONL unter `docs/messung/zitatauswahl/`; der Bericht
`docs/messung/2026-10-zitatauswahl.md` wird daraus erzeugt. Am Betrieb ändert
sich nur, was eine Intervention nach der Schwelle E7 gewinnt.

**Tech Stack:** Python 3.11 (Standardbibliothek, `tomllib`), SQLite, pytest
(+ xdist), vorhandene Module `repo`, `schaerfung`, `szene_claude`, `zitat`,
`scripts.stueckmodell_kopie`.

**Spec:** `docs/superpowers/specs/2026-10-11-zitatauswahl-gold-recall-design.md`
(lies §§ 3–7, bevor du anfängst; die Entscheidungen E1–E9 sind bindend).

## Global Constraints

- Branch `wt/t_2f905d2c`. **Jede Commit-Message enthält `(t_2f905d2c)`**:
  Messung 2 findet den Korpus über `git log --oneline --grep=t_2f905d2c main`.
- Commit-Messages enden mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `betrieb/padua.db` nur `mode=ro`; Kopien nur über
  `scripts.stueckmodell_kopie.kopiere` (`VACUUM INTO`) nach `var/zitatauswahl/`.
  `var/` wird **nie** eingecheckt; `git add` immer mit expliziten Pfaden.
  `betrieb/padua-test.db` ist keine Messquelle.
- Nicht anfassen: `interview_theater/verdichter.py`, `interview_theater/erkenner.py`,
  `interview_theater/aufnahme.py`, `interview_theater/kernzitate.py`, das Modell
  der Interviewstrecke (Kimi/Infomaniak) und das Modell der Schärfung
  (`claude-opus-5` über den Proxy).
- SQL nur in `repo.py`/`db.py`; neue `repo`-Funktionen mit `@_gesperrt`.
- Kein Modellaufruf in Knopf-Handlern; `schaerfung.starte` → `_lauf` bleibt das Thread-Muster.
- Dortmund eingefroren: kein neuer Profilschalter, DE-Prompt
  `interview_theater/prompts/schaerfung.md` bleibt byte-gleich.
- Live-Dienste (`interview-theater*`) nie starten, stoppen oder neu starten.
- Neu-Läufe nur über den Proxy (`http://127.0.0.1:28764/v1/messages`, Abo,
  0 CHF), nie über Kimi/gemma. Kein anderes Geld kostendes Skript starten.
- Ins Repo kommt kein Interviewtext außer den 16 Plakatzitaten (schon
  veröffentlicht); Negative und Rohergebnisse tragen nur Kennungen und Zahlen.
- Eine Bash-Anweisung je Aufruf, kein `cd`, kein `&&`, kein `$VAR`; lange
  Befehle mit Timeout 900000 ms im Vordergrund.
- Gezielter Test: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
- Volle Suite (einmal am Ende): `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2`

## Dateien

| Datei | Aufgabe | Task |
|---|---|---|
| `interview_theater/repo.py` | `schaerfungen_historie`, `themen_mit_aufnahme` (Lesefunktionen) | 1 |
| `interview_theater/schaerfung.py` | `werte_aus` aus `_mappe_ziel` herauslösen (keine Verhaltensänderung) | 2 |
| `korpus/zitatauswahl_quelle.toml` (neu) | 16 Plakatkarten im Wortlaut | 3 |
| `scripts/zitatauswahl.py` (neu) | Gold bauen/prüfen, Ranglisten, Recall, Neu-Lauf, Bericht, CLI | 3–6 |
| `korpus/zitatauswahl_gold.jsonl` (neu, erzeugt) | Gold-Korpus | 3 |
| `docs/messung/zitatauswahl/*.jsonl` (neu, erzeugt) | Rohergebnisse B0/B1/I-a/I-b | 4, 5, 7, 8 |
| `docs/messung/2026-10-zitatauswahl.md` (neu, erzeugt) | Bericht + Format-Doku | 6–9 |
| `docs/messung/zitatauswahl/prompt-I-a.md` (neu) | Kandidat-Prompt I-a | 7 |
| `interview_theater/sprachen/en/prompts/schaerfung.md` | nur wenn I-a gewinnt | 7 |
| `interview_theater/zitat.py` | `frage_vor` (nur wenn Gate I-b offen) | 8 |
| `docs/agents/korpus-und-simulation.md` | Verweis auf Korpus und Skript | 9 |
| `tests/test_zitatauswahl.py` (neu) | alle Tests dieser Karte | 1–8 |

---

### Task 0: Vorbedingungen und DB-Kopie (kein Produktivcode)

**Files:** keine (nur `var/`, nicht eingecheckt)

- [ ] **Step 1: Branch prüfen**

Run: `git branch --show-current`
Expected: `wt/t_2f905d2c`. Sonst stoppen und fragen.

- [ ] **Step 2: Kopie der Live-DB anlegen**

Run: `uv run --extra dev python -m scripts.stueckmodell_kopie betrieb/padua.db var/zitatauswahl/padua-kopie.db`
Expected: `Kopie: var/zitatauswahl/padua-kopie.db`. Existiert die Datei schon
(`FileExistsError`), nimm sie; die Kopie bleibt für alle Läufe dieselbe.

- [ ] **Step 3: Proxy erreichbar? (0 CHF)**

Run:
```
curl -s -m 120 http://127.0.0.1:28764/v1/messages -H "content-type: application/json" -H "anthropic-version: 2023-06-01" -d '{"model":"claude-opus-5","max_tokens":20,"messages":[{"role":"user","content":"Sag ok."}]}'
```
Expected: JSON mit `"type":"message"`. Sonst: Tasks 1–4 und 6 trotzdem bauen,
Task 5 Step 7 (die Läufe) und Task 7/8 erst bei laufendem Proxy; Ausfall im
Bericht vermerken.

---

### Task 1: Lesefunktionen in `repo`

**Files:**
- Modify: `interview_theater/repo.py` (direkt hinter `setze_schaerfung_entscheidung`)
- Test: `tests/test_zitatauswahl.py` (neu)

**Interfaces:**
- Produces:
  - `repo.schaerfungen_historie(conn, chat_id: int) -> list[sqlite3.Row]` mit Spalten
    `id, verdichtung_thema_id, szene_id, figur_id, staerke, runde, entscheidung, uebernommen_am, entfernt_am`,
    **alle** Zeilen (auch entfernte), sortiert nach `id`.
  - `repo.themen_mit_aufnahme(conn, chat_id: int) -> list[sqlite3.Row]` mit
    `id, thema, beleg_zitat, zitat_geprueft, aufnahme_id, verdichtung_entfernt_am`,
    alle Themen (auch aus entfernten Verdichtungen), sortiert nach `id`.
  - Test-Helfer in `tests/test_zitatauswahl.py`: `_interview(conn, transkript, themen, name) -> int`, Fixture `lage`.

- [ ] **Step 1: Failing tests schreiben**

`tests/test_zitatauswahl.py`:

```python
"""Tests fuer die Messung der Zitatauswahl (Karte t_2349e9a8 / t_2f905d2c):
Gold-Korpus, Recall@10 je Ziel, Mutationstest, Neu-Lauf ohne Kimi.

Kein Netzzugriff: der Claude-Proxy ist eine Attrappe."""

import ast
import json
from pathlib import Path

import pytest

from interview_theater import llm, repo, schaerfung, szene_claude

ZITAT_A = "Also ich, ich habe zwanzig Jahre genaeht und keiner hat gefragt."
TRANSKRIPT_A = "Wie war die Arbeit? " + ZITAT_A + " Danach war Ruhe."
ZITAT_B = "Am Samstag faehrt keiner, da steht die Stadt still."
TRANSKRIPT_B = "Was ist am Wochenende? " + ZITAT_B
ZITAT_C = "Der Hund vom Nachbarn bellt jeden Morgen um sechs."
TRANSKRIPT_C = "Und die Nachbarn? " + ZITAT_C


def _interview(conn, transkript, themen, name):
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_aufnahme_name(conn, kopf_id, name)
    repo.setze_transkript(conn, kopf_id, transkript)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Eine Zusammenfassung.", themen)
    return kopf_id


@pytest.fixture
def lage(conn):
    """Drei Interviews mit je einem geprueften Thema, zwei Szenen."""
    _interview(conn, TRANSKRIPT_A, [
        {"thema": "Arbeit", "beleg_zitat": ZITAT_A, "zitat_geprueft": 1}], "A")
    _interview(conn, TRANSKRIPT_B, [
        {"thema": "Stadt", "beleg_zitat": ZITAT_B, "zitat_geprueft": 1}], "B")
    _interview(conn, TRANSKRIPT_C, [
        {"thema": "Nachbarn", "beleg_zitat": ZITAT_C, "zitat_geprueft": 1}], "C")
    for nummer, titel in ((1, "Im Treppenhaus"), (2, "Am Kiosk")):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.setze_szenenfeld(conn, szene_id, "titel", titel)
    conn.commit()
    return conn


def _themen(conn):
    """thema -> id"""
    return {z["thema"]: z["id"] for z in repo.gepruefte_themen(conn, 1)}


def _szenen(conn):
    """nummer -> id"""
    return {s["nummer"]: s["id"] for s in repo.hole_szenen(conn, 1)}


# --- repo -------------------------------------------------------------------


def test_historie_liefert_auch_entfernte_zeilen(lage):
    t, s = _themen(lage), _szenen(lage)
    repo.lege_schaerfung_an(lage, 1, [
        {"verdichtung_thema_id": t["Arbeit"], "szene_id": s[1], "staerke": 3},
        {"verdichtung_thema_id": t["Stadt"], "szene_id": s[2], "staerke": 2},
    ])
    erste = repo.schaerfungen_historie(lage, 1)[0]["id"]
    repo.entferne_schaerfung(lage, erste)

    zeilen = repo.schaerfungen_historie(lage, 1)

    assert [z["verdichtung_thema_id"] for z in zeilen] == [t["Arbeit"], t["Stadt"]]
    assert zeilen[0]["entfernt_am"] is not None
    assert zeilen[1]["staerke"] == 2 and zeilen[1]["runde"] == 1


def test_themen_mit_aufnahme_tragen_aufnahme_und_pruefung(lage):
    zeilen = repo.themen_mit_aufnahme(lage, 1)

    assert [z["thema"] for z in zeilen] == ["Arbeit", "Stadt", "Nachbarn"]
    assert all(z["zitat_geprueft"] == 1 for z in zeilen)
    assert all(z["verdichtung_entfernt_am"] is None for z in zeilen)
    assert zeilen[0]["aufnahme_id"] != zeilen[1]["aufnahme_id"]
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: FAIL mit `AttributeError: module 'interview_theater.repo' has no attribute 'schaerfungen_historie'`.

- [ ] **Step 3: Implementieren**

In `interview_theater/repo.py` direkt nach dem Ende von `setze_schaerfung_entscheidung` einfügen:

```python
@_gesperrt
def schaerfungen_historie(conn: sqlite3.Connection, chat_id: int) -> list[sqlite3.Row]:
    """ALLE Schaerfungen einer Gruppe -- auch entfernte und uebernommene --
    in der Reihenfolge ihres Entstehens (``id``). Nur fuer Messungen
    (``scripts/zitatauswahl.py``, Karte t_2f905d2c): der Betrieb liest
    ``schaerfungen``, das Entferntes ausblendet."""
    return conn.execute(
        """
        SELECT id, verdichtung_thema_id, szene_id, figur_id, staerke, runde,
               entscheidung, uebernommen_am, entfernt_am
        FROM schaerfung WHERE chat_id = ? ORDER BY id ASC
        """,
        (chat_id,),
    ).fetchall()


@_gesperrt
def themen_mit_aufnahme(conn: sqlite3.Connection, chat_id: int) -> list[sqlite3.Row]:
    """Alle Verdichtungsthemen einer Gruppe mit ``aufnahme_id`` -- auch
    ungepruefte und solche aus entfernten Verdichtungen (``gepruefte_themen``
    filtert beides). Nur fuer Messungen (``scripts/zitatauswahl.py``): der
    Gold-Korpus fuehrt Dubletten einer Stelle aus entfernten Verdichtungen
    mit, damit eine historische Zuordnung auf die alte id noch trifft."""
    return conn.execute(
        """
        SELECT t.id, t.thema, t.beleg_zitat, t.zitat_geprueft,
               v.aufnahme_id AS aufnahme_id, v.entfernt_am AS verdichtung_entfernt_am
        FROM verdichtung_thema t
        JOIN verdichtung v ON v.id = t.verdichtung_id
        WHERE t.chat_id = ? ORDER BY t.id ASC
        """,
        (chat_id,),
    ).fetchall()
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/repo.py tests/test_zitatauswahl.py
git commit -m "feat(repo): Lesefunktionen schaerfungen_historie, themen_mit_aufnahme fuer die Zitat-Messung (t_2f905d2c)"
```

---

### Task 2: `schaerfung.werte_aus` herauslösen (keine Verhaltensänderung)

**Files:**
- Modify: `interview_theater/schaerfung.py:440-499` (`_mappe_ziel`)
- Test: `tests/test_zitatauswahl.py`

**Interfaces:**
- Produces: `schaerfung.werte_aus(ergebnis: dict, ziel: dict, nach_nummer: dict) -> list[dict]`.
  Das sind die Zuordnungen in **Ausgabereihenfolge des Modells**, jede mit
  `verdichtung_thema_id`, `staerke`, `begruendung` und `szene_id` oder `figur_id`.
  Dieselben Regeln wie bisher: Nummer muss existieren, Wortlaut muss passen,
  `staerke >= STAERKE_MIN`.

- [ ] **Step 1: Failing test anhängen**

```python
# --- schaerfung.werte_aus -----------------------------------------------------


def test_werte_aus_haelt_reihenfolge_und_regeln():
    nach_nummer = {
        1: {"thema_id": 11, "zitat": "eins zwei drei vier"},
        2: {"thema_id": 22, "zitat": "fuenf sechs sieben acht"},
    }
    ziel = {"art": "szene", "id": 7}
    ergebnis = {
        "eintrag_nummern": [2, 99, 1, 1],
        "staerke": [3, 3, 2, 1],
        "begruendungen": ["b2", "erfunden", "b1", "zu schwach"],
        "zitate": ["", "", "eins zwei", ""],
    }

    zuordnungen = schaerfung.werte_aus(ergebnis, ziel, nach_nummer)

    assert [(z["verdichtung_thema_id"], z["staerke"]) for z in zuordnungen] == [(22, 3), (11, 2)]
    assert all(z["szene_id"] == 7 for z in zuordnungen)
    assert zuordnungen[0]["begruendung"] == "b2"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: FAIL `AttributeError: … has no attribute 'werte_aus'`.

- [ ] **Step 3: Umbauen**

In `interview_theater/schaerfung.py` ersetzt du in `_mappe_ziel` alles ab
`nummern = _liste(ergebnis, "eintrag_nummern")` bis zum Ende der Funktion
(`return zuordnungen`) durch:

```python
    return werte_aus(ergebnis, ziel, nach_nummer)
```

und fügst direkt **vor** `def _mappe_ziel` ein:

```python
def werte_aus(ergebnis: dict, ziel: dict, nach_nummer: dict) -> list[dict]:
    """Die Antwort EINES Ziel-Aufrufs als Zuordnungen, in der Reihenfolge
    des Modells (die Betriebssortierung ``(-staerke, runde, id)`` nutzt sie
    als Gleichstandsregel, weil ``lege_schaerfung_an`` in dieser Reihenfolge
    anlegt). Oeffentlich, damit die Zitat-Messung (``scripts/zitatauswahl.py``,
    t_2f905d2c) dieselben Regeln anwendet wie der Betrieb."""
    nummern = _liste(ergebnis, "eintrag_nummern")
    staerken = _liste(ergebnis, "staerke")
    begruendungen = _liste(ergebnis, "begruendungen")
    wortlaute = _liste(ergebnis, "zitate")

    zuordnungen: list[dict] = []
    for lauf, roh in enumerate(nummern):
        try:
            eintrag = nach_nummer.get(int(roh))
        except (TypeError, ValueError):
            continue
        if eintrag is None:
            # Eine Nummer, die es nicht gibt, ist genau der Fall, gegen den
            # die Nummerierung schuetzt: verworfen, nicht geraten.
            continue
        # Der mitgeschriebene Wortlaut wird gegen das Original gehalten:
        # schreibt das Modell etwas anderes hin als das Zitat, auf dessen
        # Nummer es zeigt, meint es nicht diese Stelle.
        wortlaut = str(wortlaute[lauf] or "").strip() if lauf < len(wortlaute) else ""
        if wortlaut and not zitat.pruefe(wortlaut, eintrag["zitat"]):
            log.info("Schaerfung verworfen: Wortlaut passt nicht zu Nummer %s", roh)
            continue
        try:
            staerke = int(staerken[lauf]) if lauf < len(staerken) else 0
        except (TypeError, ValueError):
            staerke = 0
        if staerke < STAERKE_MIN:
            continue
        zuordnung = {
            "verdichtung_thema_id": eintrag["thema_id"],
            "staerke": staerke,
            "begruendung": (
                str(begruendungen[lauf] or "").strip()
                if lauf < len(begruendungen) else None
            ),
        }
        if ziel["art"] == "szene":
            zuordnung["szene_id"] = ziel["id"]
        else:
            zuordnung["figur_id"] = ziel["id"]
        zuordnungen.append(zuordnung)
    return zuordnungen
```

- [ ] **Step 4: Run, expect PASS (neu und alt)**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py tests/test_schaerfung.py`
Expected: alle grün (`test_schaerfung.py` deckt `_mappe_ziel` unverändert ab).

- [ ] **Step 5: Commit**

```bash
git add interview_theater/schaerfung.py tests/test_zitatauswahl.py
git commit -m "refactor(schaerfung): werte_aus aus _mappe_ziel herausloesen, fuer die Zitat-Messung (t_2f905d2c)"
```

---

### Task 3: Quelldatei, Gold-Korpus bauen und prüfen (inkl. Mutationstest „Lauf rot")

**Files:**
- Create: `korpus/zitatauswahl_quelle.toml`
- Create: `scripts/zitatauswahl.py`
- Create (erzeugt): `korpus/zitatauswahl_gold.jsonl`
- Test: `tests/test_zitatauswahl.py`

**Interfaces:**
- Consumes: `repo.schaerfungen_historie`, `repo.themen_mit_aufnahme` (Task 1),
  `repo.transkripte`, `repo.hole_aufnahme`, `repo.zusammengefuegtes_transkript`,
  `repo.hole_szenen`, `repo.figuren`, `repo.gepruefte_themen`, `zitat.pruefe`,
  `scripts.stueckmodell_kopie.kopiere`.
- Produces (in `scripts/zitatauswahl.py`):
  - Konstanten `GRUPPEN = {"G1": 7000000000000, "G2": 7000000000001, "G3": 7000000000002}`,
    `QUELLE = Path("korpus/zitatauswahl_quelle.toml")`, `GOLD = Path("korpus/zitatauswahl_gold.jsonl")`,
    `ROH = Path("docs/messung/zitatauswahl")`, `BERICHT = Path("docs/messung/2026-10-zitatauswahl.md")`,
    `K = 10`, `LOSE_SCHWELLE = 0.5`
  - `fragmente(wortlaut: str) -> list[str]`
  - `verankere(fragment: str, transkript: str) -> str | None`
  - `anteil(fragmente: list[str], text: str) -> float`
  - `lade_quelle(pfad) -> list[dict]`
  - `baue_gold(conn, quelle: list[dict], gruppen: dict[str, int]) -> list[dict]`
  - `pruefe_gold(conn, gold: list[dict]) -> list[str]` (leer = gültig)
  - `lade_gold(pfad) -> list[dict]`, `schreibe_gold(gold, pfad) -> None`
  - `ziel_schluessel(zeile: dict) -> str` → `"G1:szene:2"`
  - `trifft(kandidat: dict, gold: dict) -> bool` (Spec E4)
  - `main(argv: list[str] | None = None) -> int` mit Unterbefehlen `kopie`, `gold`, `pruefe`

- [ ] **Step 1: Quelldatei schreiben**

`korpus/zitatauswahl_quelle.toml` (Wortlaut 1:1 aus entities `3fa1f46`,
`### cards: quotes`, Spalten `title` → `wortlaut`, `meta` → `frage`, `label`
→ `label`, erste Szenennummer in `label` → `szene`):

```toml
# Gold-Korpus Zitatauswahl Padua, positive Stellen (Karte t_2349e9a8 / t_2f905d2c).
# Quelle: hermes-entities, Commit 3fa1f46 (09.10.2026 13:26),
# entities/artesmobiles/projekte/padua-workshop/deliverables/2026-10-09-plakat-a3/en/content/
# Abschnitt "### cards: quotes" der Gruppenplakate ("Variante A: nur Zitate, die
# im Stueck landen"). Prozessplakat 01_prozess.md bewusst NICHT (Spec F7.1).
# Auslassungen im Plakat: " … ". Gebaut wird daraus mit
#   uv run --extra dev python -m scripts.zitatauswahl gold --db var/zitatauswahl/padua-kopie.db

quelle_commit = "3fa1f46"

[[karte]]
id = "G1-1"
gruppe = "G1"
datei = "02_g1.md"
karte = 1
szene = 2
frage = "If your home could talk, what would it say about you?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "spoken in scene 2, The voices"

[[karte]]
id = "G1-2"
gruppe = "G1"
datei = "02_g1.md"
karte = 2
szene = 2
frage = "If your home could talk, what would it say about you?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "spoken in scene 2, The voices"

[[karte]]
id = "G1-3"
gruppe = "G1"
datei = "02_g1.md"
karte = 3
szene = 2
frage = "What has to happen in a new place before you call it home?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "spoken in scene 2, The voices"

[[karte]]
id = "G1-4"
gruppe = "G1"
datei = "02_g1.md"
karte = 4
szene = 2
frage = "What do you do to feel at home when you are far away?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "spoken in scene 2, The voices"

[[karte]]
id = "G1-5"
gruppe = "G1"
datei = "02_g1.md"
karte = 5
szene = 2
frage = "Which smells take you back home?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "spoken in scene 2, The voices"

[[karte]]
id = "G2-1"
gruppe = "G2"
datei = "03_g2.md"
karte = 1
szene = 1
frage = "Is it hard to start a conversation in a new place where you know no one?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "scene 1, Beginning: the theme of the scene, one person alone at an empty table"

[[karte]]
id = "G2-2"
gruppe = "G2"
datei = "03_g2.md"
karte = 2
szene = 2
frage = "And with friends, what actually helps you relate to someone?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "scene 2, Recruitment: the theme of the scene, the table starts to fill"

[[karte]]
id = "G2-3"
gruppe = "G2"
datei = "03_g2.md"
karte = 3
szene = 2
frage = "Why do you text rather than call?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "scene 2, Recruitment: becomes Pietro's line"

[[karte]]
id = "G2-4"
gruppe = "G2"
datei = "03_g2.md"
karte = 4
szene = 3
frage = "If you could teach a 15-year-old one hour of sex and relationship education, what would you teach?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "scene 3, The last seat: every no from a passer-by is accepted at once"

[[karte]]
id = "G2-5"
gruppe = "G2"
datei = "03_g2.md"
karte = 5
szene = 4
frage = "What do you know about HPV? (answered in Spanish)"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "scene 4, Discussion: the prejudice the whole table argues"

[[karte]]
id = "G3-1"
gruppe = "G3"
datei = "04_g3.md"
karte = 1
szene = 2
frage = "Where were you on 11 September 2001, if you were born?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "scene 2, Slow Start, and again in scene 6"

[[karte]]
id = "G3-2"
gruppe = "G3"
datei = "04_g3.md"
karte = 2
szene = 2
frage = "The Millennium Bug: if you had had the choice, would you have pressed the button?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "scene 2, Slow Start"

[[karte]]
id = "G3-3"
gruppe = "G3"
datei = "04_g3.md"
karte = 3
szene = 3
frage = "Mara Venier died this morning. Your reaction? (invented news)"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "scene 3, Fast Rise: true and false pile up"

[[karte]]
id = "G3-4"
gruppe = "G3"
datei = "04_g3.md"
karte = 4
szene = 3
frage = "Which story about the gangster Felice Maniero struck you most?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "scene 3, Fast Rise"

[[karte]]
id = "G3-5"
gruppe = "G3"
datei = "04_g3.md"
karte = 5
szene = 3
frage = "Something that happened where you live?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "scene 3, Fast Rise"

[[karte]]
id = "G3-6"
gruppe = "G3"
datei = "04_g3.md"
karte = 6
szene = 5
frage = "A personal event that made a before and after in your life?"
wortlaut = "<entfernt, siehe betrieb/korpus/zitatauswahl_quelle.toml>"
label = "scene 5, Second Rise, and again in scene 6"
```

- [ ] **Step 2: Failing tests anhängen**

```python
# --- Gold-Korpus ------------------------------------------------------------

from scripts import zitatauswahl as za  # noqa: E402

QUELLE = [
    {"id": "G1-1", "gruppe": "G1", "datei": "x.md", "karte": 1, "szene": 1,
     "frage": "How was work?", "label": "scene 1",
     "wortlaut": "Ich habe zwanzig Jahre genaeht … keiner hat gefragt."},
    {"id": "G1-2", "gruppe": "G1", "datei": "x.md", "karte": 2, "szene": 2,
     "frage": "Weekend?", "label": "scene 2",
     "wortlaut": "am samstag faehrt keiner, da steht die Stadt"},
]


def test_fragmente_trennt_an_auslassungen():
    assert za.fragmente("«Eins zwei … drei vier.»") == ["Eins zwei", "drei vier"]


def test_verankere_liefert_den_originalwortlaut():
    assert za.verankere("Ich habe zwanzig Jahre genaeht", TRANSKRIPT_A) == "ich habe zwanzig Jahre genaeht"
    assert za.verankere("das hat nie jemand gesagt", TRANSKRIPT_A) is None


def test_gold_aus_der_quelle(lage):
    t, s = _themen(lage), _szenen(lage)

    gold = za.baue_gold(lage, QUELLE, {"G1": 1})

    positiv = [g for g in gold if g["polaritaet"] == "positiv"]
    assert [g["id"] for g in positiv] == ["G1-1", "G1-2"]
    eins = positiv[0]
    assert eins["fragmente"] == ["ich habe zwanzig Jahre genaeht", "keiner hat gefragt"]
    assert eins["verdichtung_thema_id"] == t["Arbeit"] and eins["thema_ids"] == [t["Arbeit"]]
    assert eins["im_pool"] is True
    assert eins["ziel"] == {"art": "szene", "nummer": 1, "id": s[1], "titel": "Im Treppenhaus"}
    assert eins["quelle"]["karte"] == 1
    assert za.pruefe_gold(lage, gold) == []


def test_negativ_nur_nein_ohne_ja_und_nicht_positiv(lage):
    t, s = _themen(lage), _szenen(lage)
    repo.lege_schaerfung_an(lage, 1, [
        {"verdichtung_thema_id": t["Nachbarn"], "szene_id": s[1], "staerke": 3},  # nein -> negativ
        {"verdichtung_thema_id": t["Nachbarn"], "szene_id": s[2], "staerke": 3},  # nein ...
        {"verdichtung_thema_id": t["Nachbarn"], "szene_id": s[2], "staerke": 3},  # ... und ja -> raus
        {"verdichtung_thema_id": t["Arbeit"], "szene_id": s[2], "staerke": 2},    # positiv -> raus
    ])
    ids = [z["id"] for z in repo.schaerfungen_historie(lage, 1)]
    for sid, wert in zip(ids, ["nein", "nein", "ja", "nein"]):
        assert repo.setze_schaerfung_entscheidung(lage, 1, sid, wert)

    gold = za.baue_gold(lage, QUELLE, {"G1": 1})

    negativ = [g for g in gold if g["polaritaet"] == "negativ"]
    assert [(g["verdichtung_thema_id"], g["ziel"]["id"]) for g in negativ] == [(t["Nachbarn"], s[1])]
    assert negativ[0]["id"] == f"G1-n-{ids[0]:04d}"
    assert "wortlaut" not in negativ[0] and "fragmente" not in negativ[0]


def test_trifft_ueber_thema_oder_wortlaut():
    gold = {"thema_ids": [3, 30], "fragmente": ["allein gegangen"]}
    assert za.trifft({"verdichtung_thema_id": 30}, gold)
    assert not za.trifft({"verdichtung_thema_id": 4}, gold)
    assert za.trifft({"text": "ich bin damals allein gegangen"}, gold)


def test_mutation_erfundene_stelle_macht_den_lauf_rot(lage, tmp_path):
    """Spec § 6 / Karte: Gold-Korpus verfaelscht -> Lauf rot."""
    db_pfad = str(tmp_path / "t.db")
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    pfad = tmp_path / "gold.jsonl"
    za.schreibe_gold(gold, pfad)
    assert za.main(["pruefe", "--db", db_pfad, "--gold", str(pfad)]) == 0

    gold[0]["fragmente"] = ["das hat nie jemand gesagt"]
    gold[0]["thema_ids"] = [999]
    gold[0]["verdichtung_thema_id"] = 999
    za.schreibe_gold(gold, pfad)

    assert za.main(["pruefe", "--db", db_pfad, "--gold", str(pfad)]) == 1
    fehler = za.pruefe_gold(lage, za.lade_gold(pfad))
    assert any(f.startswith("G1-1:") and "Transkript" in f for f in fehler)
    assert any(f.startswith("G1-1:") and "999" in f for f in fehler)


def test_mutation_ein_wort_geaendert_ist_rot(lage):
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    gold[0]["fragmente"][1] = "keiner hat gelacht"
    assert za.pruefe_gold(lage, gold) != []


def test_mutation_falsche_szene_ist_rot(lage):
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    gold[0]["ziel"]["nummer"] = 7
    assert any("Szene" in f for f in za.pruefe_gold(lage, gold))
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: FAIL `ModuleNotFoundError: No module named 'scripts.zitatauswahl'`.

- [ ] **Step 4: `scripts/zitatauswahl.py` anlegen (Teil 1)**

```python
"""Messung der Zitatauswahl (Karte t_2349e9a8, Umsetzung t_2f905d2c).

Misst, ob die Schaerfung (``schaerfung.py``) die Stellen nach vorn bringt,
die in Padua tatsaechlich im Stueck gelandet sind: Recall@10 JE ZIEL (Spec E1),
gegen den Gold-Korpus ``korpus/zitatauswahl_gold.jsonl``.

Kommandos (Reihenfolge; Bericht: docs/messung/2026-10-zitatauswahl.md):

    uv run --extra dev python -m scripts.zitatauswahl kopie
    uv run --extra dev python -m scripts.zitatauswahl gold --db var/zitatauswahl/padua-kopie.db
    uv run --extra dev python -m scripts.zitatauswahl pruefe --db var/zitatauswahl/padua-kopie.db
    uv run --extra dev python -m scripts.zitatauswahl historisch --db var/zitatauswahl/padua-kopie.db
    uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante B1 --lauf 1 --gruppe G1
    uv run --extra dev python -m scripts.zitatauswahl bericht

Quelle der Live-DB nur read-only (``stueckmodell_kopie.kopiere``, VACUUM INTO).
Neu-Laeufe nur ueber den Claude-Proxy (0 CHF), nie ueber Kimi/gemma.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

from interview_theater import repo, zitat

GRUPPEN = {"G1": 7000000000000, "G2": 7000000000001, "G3": 7000000000002}
QUELLE = Path("korpus/zitatauswahl_quelle.toml")
GOLD = Path("korpus/zitatauswahl_gold.jsonl")
ROH = Path("docs/messung/zitatauswahl")
BERICHT = Path("docs/messung/2026-10-zitatauswahl.md")
LIVE_DB = Path("betrieb/padua.db")
KOPIE = Path("var/zitatauswahl/padua-kopie.db")
K = 10
#: Anteil der 4-Wort-Fenster einer Plakatstelle, der in einem Belegzitat
#: stehen muss, damit das Thema als dieselbe Stelle gilt (Sondierung
#: 11.10.2026: echte Paare 0,59-1,0, sonst 0).
LOSE_SCHWELLE = 0.5


def _woerter(text: str) -> list[str]:
    return re.findall(r"\w+", (text or "").lower())


def fragmente(wortlaut: str) -> list[str]:
    """Die Teile einer Plakatstelle zwischen den Auslassungen (``…``)."""
    teile = (wortlaut or "").strip().strip("«»\"").split("…")
    return [t.strip().strip("«»\" .,") for t in teile if t.strip().strip("«»\" .,")]


def verankere(fragment: str, transkript: str) -> str | None:
    """Die Stelle im Transkript mit derselben Wortfolge wie das Fragment
    (klein, ohne Satzzeichen) -- im ORIGINALWORTLAUT des Transkripts, damit
    ``zitat.pruefe`` sie danach exakt findet. ``None``, wenn es sie nicht gibt."""
    gesucht = _woerter(fragment)
    if not gesucht or not transkript:
        return None
    treffer = list(re.finditer(r"\w+", transkript))
    worte = [m.group(0).lower() for m in treffer]
    n = len(gesucht)
    for i in range(len(worte) - n + 1):
        if worte[i:i + n] == gesucht:
            return transkript[treffer[i].start():treffer[i + n - 1].end()]
    return None


def anteil(fragmente_: list[str], text: str) -> float:
    """Anteil der 4-Wort-Fenster der Fragmente, die in ``text`` vorkommen
    (kuerzere Fragmente: das ganze Fragment als ein Fenster)."""
    ziel = " " + " ".join(_woerter(text)) + " "
    fenster = []
    for f in fragmente_:
        w = _woerter(f)
        fenster += [" " + " ".join(w[i:i + 4]) + " " for i in range(max(1, len(w) - 3))]
    return sum(f in ziel for f in fenster) / len(fenster) if fenster else 0.0


def _transkript(conn, aufnahme_id: int) -> str:
    zeile = repo.hole_aufnahme(conn, aufnahme_id)
    if zeile is None:
        return ""
    return (zeile["transkript"] or "") or repo.zusammengefuegtes_transkript(conn, aufnahme_id)


def _im_pool(thema) -> bool:
    return (thema is not None and thema["zitat_geprueft"] == 1
            and thema["verdichtung_entfernt_am"] is None and bool(thema["beleg_zitat"]))


def lade_quelle(pfad=QUELLE) -> list[dict]:
    with open(pfad, "rb") as f:
        daten = tomllib.load(f)
    commit = daten.get("quelle_commit", "")
    return [dict(k, quelle_commit=commit) for k in daten["karte"]]


def _positive_stelle(conn, karte: dict, chat_id: int) -> dict:
    fr = fragmente(karte["wortlaut"])
    aufnahme_id, anker = None, []
    for aufnahme in repo.transkripte(conn, chat_id):
        text = _transkript(conn, aufnahme["id"])
        kandidat = [verankere(f, text) for f in fr]
        if fr and all(kandidat):
            aufnahme_id, anker = aufnahme["id"], kandidat
            break
    if aufnahme_id is None:
        raise ValueError(f"{karte['id']}: Wortlaut steht in keinem Transkript der Gruppe")
    themen = [t for t in repo.themen_mit_aufnahme(conn, chat_id)
              if t["aufnahme_id"] == aufnahme_id
              and anteil(anker, t["beleg_zitat"] or "") >= LOSE_SCHWELLE]
    im_pool = [t["id"] for t in themen if _im_pool(t)]
    szene = next((s for s in repo.hole_szenen(conn, chat_id) if s["nummer"] == karte["szene"]), None)
    if szene is None:
        raise ValueError(f"{karte['id']}: Szene {karte['szene']} fehlt")
    return {
        "id": karte["id"], "gruppe": karte["gruppe"], "chat_id": chat_id,
        "polaritaet": "positiv",
        "ziel": {"art": "szene", "nummer": szene["nummer"], "id": szene["id"],
                 "titel": szene["titel"] or ""},
        "frage": karte["frage"], "wortlaut": karte["wortlaut"], "fragmente": anker,
        "aufnahme_id": aufnahme_id,
        "verdichtung_thema_id": im_pool[0] if im_pool else None,
        "thema_ids": [t["id"] for t in themen], "im_pool": bool(im_pool),
        "quelle": {"repo": "hermes-entities", "commit": karte.get("quelle_commit", ""),
                   "datei": karte["datei"], "karte": karte["karte"], "label": karte["label"]},
    }


def _negative(conn, gruppe: str, chat_id: int, positiv_themen: set[int]) -> list[dict]:
    """Spec F7.3: ein Paar (Thema, Ziel) mit mindestens einem ``nein``, ohne
    ``ja`` an diesem Ziel, und das Thema ist nirgends positiv. Nur Kennungen."""
    themen = {t["id"]: t for t in repo.themen_mit_aufnahme(conn, chat_id)}
    paare: dict[tuple, dict] = {}
    for z in repo.schaerfungen_historie(conn, chat_id):
        art, zid = ("szene", z["szene_id"]) if z["szene_id"] is not None else ("figur", z["figur_id"])
        p = paare.setdefault((z["verdichtung_thema_id"], art, zid), {"ja": False, "nein": []})
        if z["entscheidung"] == "ja":
            p["ja"] = True
        elif z["entscheidung"] == "nein":
            p["nein"].append(z["id"])
    szenen = {s["id"]: s for s in repo.hole_szenen(conn, chat_id)}
    figuren = {f["id"]: f for f in repo.figuren(conn, chat_id)}
    aus = []
    for (thema_id, art, zid), p in paare.items():
        if not p["nein"] or p["ja"] or thema_id in positiv_themen:
            continue
        if art == "szene" and zid in szenen:
            ziel = {"art": "szene", "nummer": szenen[zid]["nummer"], "id": zid,
                    "titel": szenen[zid]["titel"] or ""}
        elif art == "figur" and zid in figuren:
            ziel = {"art": "figur", "nummer": None, "id": zid, "titel": figuren[zid]["name"]}
        else:
            continue
        thema = themen.get(thema_id)
        aus.append({
            "id": f"{gruppe}-n-{min(p['nein']):04d}", "gruppe": gruppe, "chat_id": chat_id,
            "polaritaet": "negativ", "ziel": ziel,
            "aufnahme_id": thema["aufnahme_id"] if thema is not None else None,
            "verdichtung_thema_id": thema_id, "thema_ids": [thema_id],
            "im_pool": _im_pool(thema), "schaerfung_ids": sorted(p["nein"]),
            "quelle": {"tabelle": "schaerfung", "entscheidung": "nein"},
        })
    return aus


def baue_gold(conn, quelle: list[dict], gruppen: dict[str, int]) -> list[dict]:
    positiv = [_positive_stelle(conn, k, gruppen[k["gruppe"]]) for k in quelle]
    gold = list(positiv)
    for gruppe in sorted({k["gruppe"] for k in quelle}):
        themen = {t for g in positiv if g["gruppe"] == gruppe for t in g["thema_ids"]}
        gold += _negative(conn, gruppe, gruppen[gruppe], themen)
    return sorted(gold, key=lambda g: g["id"])


def pruefe_gold(conn, gold: list[dict]) -> list[str]:
    """Jeder Fehler eine Zeile ``<id>: <grund>``; leer = gueltig (Spec § 6)."""
    fehler = []
    for g in gold:
        chat_id = g["chat_id"]
        themen = {t["id"]: t for t in repo.themen_mit_aufnahme(conn, chat_id)}
        if g["polaritaet"] == "positiv":
            aufnahme = repo.hole_aufnahme(conn, g["aufnahme_id"])
            if aufnahme is None or aufnahme["chat_id"] != chat_id:
                fehler.append(f"{g['id']}: Aufnahme {g['aufnahme_id']} gehoert nicht zur Gruppe")
                continue
            text = _transkript(conn, g["aufnahme_id"])
            for f in g["fragmente"]:
                if not zitat.pruefe(f, text):
                    fehler.append(f"{g['id']}: Fragment nicht im Transkript: {f[:40]!r}")
        for t in g["thema_ids"]:
            if t not in themen:
                fehler.append(f"{g['id']}: Thema {t} gibt es in dieser Gruppe nicht")
        pool = [t for t in g["thema_ids"] if _im_pool(themen.get(t))]
        if bool(pool) != g["im_pool"] or (g["verdichtung_thema_id"] is not None
                                          and g["verdichtung_thema_id"] not in g["thema_ids"]):
            fehler.append(f"{g['id']}: im_pool/verdichtung_thema_id passen nicht zu den Themen")
        if g["ziel"]["art"] == "szene":
            szene = next((s for s in repo.hole_szenen(conn, chat_id) if s["id"] == g["ziel"]["id"]), None)
            if szene is None or szene["nummer"] != g["ziel"]["nummer"]:
                fehler.append(f"{g['id']}: Szene {g['ziel']['nummer']} (id {g['ziel']['id']}) passt nicht")
    return fehler


def lade_gold(pfad=GOLD) -> list[dict]:
    with open(pfad, encoding="utf-8") as f:
        return [json.loads(z) for z in f if z.strip()]


def schreibe_gold(gold: list[dict], pfad=GOLD) -> None:
    Path(pfad).parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as f:
        for g in sorted(gold, key=lambda g: g["id"]):
            f.write(json.dumps(g, ensure_ascii=False, sort_keys=True) + "\n")


def ziel_schluessel(zeile: dict) -> str:
    return f"{zeile['gruppe']}:{zeile['ziel']['art']}:{zeile['ziel']['id']}"


def trifft(kandidat: dict, gold: dict) -> bool:
    """Spec E4, verbindlich auch fuer Messung 2: gleiche Thema-Kennung, oder --
    traegt der Kandidat keine -- alle Fragmente stehen in seinem Text."""
    if kandidat.get("verdichtung_thema_id") is not None:
        return kandidat["verdichtung_thema_id"] in gold["thema_ids"]
    text = kandidat.get("text") or ""
    return bool(gold.get("fragmente")) and all(zitat.pruefe(f, text) for f in gold["fragmente"])


def _verbinde(pfad: str):
    from interview_theater import db

    if Path(pfad).resolve() == LIVE_DB.resolve() or "padua-test" in Path(pfad).name:
        raise SystemExit(f"Messung nur auf einer Kopie, nicht auf {pfad}")
    return db.verbinde(pfad)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.zitatauswahl")
    sub = p.add_subparsers(dest="befehl", required=True)
    k = sub.add_parser("kopie")
    k.add_argument("--quelle", default=str(LIVE_DB))
    k.add_argument("--ziel", default=str(KOPIE))
    for name in ("gold", "pruefe"):
        s = sub.add_parser(name)
        s.add_argument("--db", default=str(KOPIE))
        s.add_argument("--gold", default=str(GOLD))
        if name == "gold":
            s.add_argument("--quelle", default=str(QUELLE))
    a = p.parse_args(argv)

    if a.befehl == "kopie":
        from scripts import stueckmodell_kopie

        if "padua-test" in Path(a.quelle).name:
            raise SystemExit("Messung nur auf betrieb/padua.db")
        stueckmodell_kopie.kopiere(a.quelle, a.ziel)
        print(f"Kopie: {a.ziel}")
        return 0

    conn = _verbinde(a.db)
    if a.befehl == "gold":
        gold = baue_gold(conn, lade_quelle(a.quelle), GRUPPEN)
        fehler = pruefe_gold(conn, gold)
        if fehler:
            print("\n".join(fehler), file=sys.stderr)
            return 1
        schreibe_gold(gold, a.gold)
        pos = [g for g in gold if g["polaritaet"] == "positiv"]
        for gruppe in sorted(GRUPPEN):
            p_ = [g for g in pos if g["gruppe"] == gruppe]
            n_ = [g for g in gold if g["gruppe"] == gruppe and g["polaritaet"] == "negativ"]
            print(f"{gruppe}: positiv {len(p_)} (im Pool {sum(g['im_pool'] for g in p_)}), negativ {len(n_)}")
        return 0
    if a.befehl == "pruefe":
        fehler = pruefe_gold(conn, lade_gold(a.gold))
        if fehler:
            print("\n".join(fehler), file=sys.stderr)
            return 1
        print("Gold-Korpus gueltig")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run, expect PASS**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: alle grün. Wenn `test_mutation_erfundene_stelle_macht_den_lauf_rot`
an `main` scheitert, weil die Fixture-Verbindung nicht gespeichert hat:
`lage` ruft `conn.commit()` am Ende auf. Liegt es daran, dann nach
`repo.lege_schaerfung_an`/`setze_schaerfung_entscheidung` im Test ebenfalls
`lage.commit()` aufrufen.

- [ ] **Step 6: Gold-Korpus aus der Kopie bauen**

Run: `uv run --extra dev python -m scripts.zitatauswahl gold --db var/zitatauswahl/padua-kopie.db`
Expected (Sondierung 11.10.2026, Spec F6):
```
G1: positiv 5 (im Pool 5), negativ <n1>
G2: positiv 5 (im Pool 5), negativ <n2>
G3: positiv 6 (im Pool 5), negativ <n3>
```
`<n1..n3>` notieren (sie stehen später im Bericht). Weicht „im Pool" ab oder
endet der Lauf mit `ValueError`/Exit 1: **nicht** die Schwelle oder den
Wortlaut zurechtbiegen. Stattdessen die betroffene Karte mit einem
Wegwerfskript unter `var/zitatauswahl/` (nicht eingecheckt, nur lesend auf
der Kopie) nachprüfen und die Abweichung in der Konstante `GRENZEN`
(Task 6) festhalten. Lässt sich eine Karte gar nicht verankern: stoppen und
mit `FRAGE:` melden.
Prüfe außerdem in `korpus/zitatauswahl_gold.jsonl`: G3-3 `"im_pool": false`;
G1-1 `"thema_ids": [114]`; G3-1 `"thema_ids"` enthält 24 und 403, und
`"verdichtung_thema_id": 403`.

- [ ] **Step 7: Prüflauf**

Run: `uv run --extra dev python -m scripts.zitatauswahl pruefe --db var/zitatauswahl/padua-kopie.db`
Expected: `Gold-Korpus gueltig`, Exit 0.

- [ ] **Step 8: Commit**

```bash
git add korpus/zitatauswahl_quelle.toml korpus/zitatauswahl_gold.jsonl scripts/zitatauswahl.py tests/test_zitatauswahl.py
git commit -m "feat(messung): Gold-Korpus Zitatauswahl Padua aus den Gruppenplakaten, Pruefung und Mutationstest (t_2f905d2c)"
```

---

### Task 4: Ranglisten, Recall@k, Schwelle E7, Baseline B0

**Files:**
- Modify: `scripts/zitatauswahl.py`
- Create (erzeugt): `docs/messung/zitatauswahl/B0.jsonl`
- Test: `tests/test_zitatauswahl.py`

**Interfaces:**
- Consumes: `ziel_schluessel`, `lade_gold`, `pruefe_gold`, `_verbinde`, `repo.schaerfungen_historie`.
- Produces:
  - `rangliste(zuordnungen: list[dict]) -> list[int]`: Sortierung `(-staerke, Listenposition)`, Themen dedupliziert.
  - `ranglisten_historisch(conn, gold: list[dict]) -> dict[str, list[int]]`: je Gold-Ziel (positiv), letzte Runde.
  - `recall_at_k(ranglisten: dict[str, list[int] | None], gold: list[dict], k: int = K) -> dict[str, dict]`:
    Schlüssel sind die Gruppen und `"gesamt"`, Werte `{"treffer": int, "n": int, "fehlt": int}`.
  - `negativ_at_k(ranglisten, gold, k=K) -> dict[str, int]`
  - `pool_recall(gold) -> dict[str, tuple[int, int]]`: (im Pool, alle positiven) je Gruppe und `"gesamt"`
  - Rohzeile (JSONL): `{"variante": str, "lauf": int, "gruppe": str, "ranglisten": {schluessel: [int] | null}, "maskiert": {schluessel: int}, "fehler": {schluessel: str}, "dauer_ms": {schluessel: int}}`
  - `haenge_an(zeile: dict, pfad) -> None`, `lade_roh(verz=ROH) -> list[dict]` (führt Zeilen mit gleichem `(variante, lauf, gruppe)` zusammen)
  - `laeufe(zeilen, gold, variante: str, k: int = K) -> dict[int, dict]`: nur **vollständige** Läufe (alle Gold-Ziele aller Gruppen, kein Fehler); Wert `{"recall": recall_at_k(...), "ranglisten": {...}, "maskiert": int}`
  - `entscheide(basis: dict[int, dict], variante: dict[int, dict]) -> tuple[bool, list[str]]` (Spec E7)
  - CLI `historisch --db --gold --aus` (Vorgabe `--aus docs/messung/zitatauswahl/B0.jsonl`)

- [ ] **Step 1: Failing tests anhängen**

```python
# --- Rangliste, Recall, E7 ----------------------------------------------------


def _g(id_, gruppe, ziel_id, themen, polaritaet="positiv", im_pool=True):
    return {"id": id_, "gruppe": gruppe, "chat_id": 1, "polaritaet": polaritaet,
            "im_pool": im_pool, "ziel": {"art": "szene", "id": ziel_id, "nummer": 1},
            "thema_ids": themen,
            "verdichtung_thema_id": themen[0] if themen else None}


def test_rangliste_staerke_dann_reihenfolge_dedupliziert():
    zu = [{"verdichtung_thema_id": 5, "staerke": 2}, {"verdichtung_thema_id": 7, "staerke": 3},
          {"verdichtung_thema_id": 5, "staerke": 3}, {"verdichtung_thema_id": 9, "staerke": 3}]
    assert za.rangliste(zu) == [7, 5, 9]


def test_recall_zaehlt_nur_die_ersten_k_und_nur_im_pool():
    gold = [_g("G1-1", "G1", 2, [1]), _g("G1-2", "G1", 2, [11]),
            _g("G1-3", "G1", 2, [], im_pool=False), _g("G2-1", "G2", 4, [40, 41])]
    ranglisten = {"G1:szene:2": list(range(1, 13)), "G2:szene:4": [41]}

    r = za.recall_at_k(ranglisten, gold, k=10)

    assert r["G1"] == {"treffer": 1, "n": 2, "fehlt": 0}
    assert r["G2"] == {"treffer": 1, "n": 1, "fehlt": 0}
    assert r["gesamt"] == {"treffer": 2, "n": 3, "fehlt": 0}
    assert za.recall_at_k({}, gold)["gesamt"]["fehlt"] == 3


def test_mutation_verfaelschter_gold_korpus_senkt_recall_sichtbar():
    """Karte: Gold-Korpus verfaelscht -> Lauf rot. Ohne Pruefung faellt der
    berichtete Wert sichtbar (deterministisch, ohne Modell)."""
    gold = [_g("G1-1", "G1", 2, [3]), _g("G1-2", "G1", 2, [8])]
    ranglisten = {"G1:szene:2": [3, 8, 1]}
    assert za.recall_at_k(ranglisten, gold)["gesamt"]["treffer"] == 2

    gold[1]["thema_ids"] = [999]

    assert za.recall_at_k(ranglisten, gold)["gesamt"]["treffer"] == 1


def test_negativ_at_k_zaehlt_verworfene_in_den_top_k():
    gold = [_g("G1-1", "G1", 2, [3]), _g("G1-n-0001", "G1", 2, [8], polaritaet="negativ"),
            _g("G1-n-0002", "G1", 5, [9], polaritaet="negativ")]
    assert za.negativ_at_k({"G1:szene:2": [3, 8, 9]}, gold) == {"G1": 1, "gesamt": 1}


def test_historische_rangliste_nimmt_die_letzte_runde(lage):
    t, s = _themen(lage), _szenen(lage)
    repo.lege_schaerfung_an(lage, 1, [
        {"verdichtung_thema_id": t["Arbeit"], "szene_id": s[1], "staerke": 3}], runde=1)
    repo.lege_schaerfung_an(lage, 1, [
        {"verdichtung_thema_id": t["Stadt"], "szene_id": s[1], "staerke": 2},
        {"verdichtung_thema_id": t["Nachbarn"], "szene_id": s[1], "staerke": 3}], runde=2)
    gold = [_g("G1-1", "G1", s[1], [t["Arbeit"]])]

    assert za.ranglisten_historisch(lage, gold) == {f"G1:szene:{s[1]}": [t["Nachbarn"], t["Stadt"]]}


def _lauf(treffer_je_gruppe):
    recall = {g: {"treffer": t, "n": 5, "fehlt": 0} for g, t in treffer_je_gruppe.items()}
    recall["gesamt"] = {"treffer": sum(treffer_je_gruppe.values()), "n": 15, "fehlt": 0}
    return {"recall": recall, "ranglisten": {}, "maskiert": 0}


def test_e7_verlangt_zwei_stellen_keine_ueberlappung_keine_gruppe_schlechter():
    basis = {1: _lauf({"G1": 1, "G2": 4, "G3": 2}), 2: _lauf({"G1": 2, "G2": 4, "G3": 2})}
    gut = {1: _lauf({"G1": 3, "G2": 4, "G3": 3}), 2: _lauf({"G1": 4, "G2": 4, "G3": 3})}
    knapp = {1: _lauf({"G1": 2, "G2": 4, "G3": 3}), 2: _lauf({"G1": 3, "G2": 4, "G3": 2})}
    gruppe_faellt = {1: _lauf({"G1": 5, "G2": 2, "G3": 3}), 2: _lauf({"G1": 5, "G2": 2, "G3": 3})}

    assert za.entscheide(basis, gut)[0] is True
    assert za.entscheide(basis, knapp)[0] is False
    ok, gruende = za.entscheide(basis, gruppe_faellt)
    assert ok is False and any("G2" in g for g in gruende)
    assert za.entscheide(basis, {})[0] is False


def test_roh_zeilen_werden_je_lauf_und_gruppe_zusammengefuehrt(tmp_path):
    pfad = tmp_path / "B1.jsonl"
    za.haenge_an({"variante": "B1", "lauf": 1, "gruppe": "G2", "ranglisten": {"a": [1]},
                  "maskiert": {"a": 0}, "fehler": {}, "dauer_ms": {"a": 5}}, pfad)
    za.haenge_an({"variante": "B1", "lauf": 1, "gruppe": "G2", "ranglisten": {"b": [2]},
                  "maskiert": {"b": 1}, "fehler": {}, "dauer_ms": {"b": 6}}, pfad)

    za.haenge_an({"variante": "B1", "lauf": 1, "gruppe": "G3", "ranglisten": {"c": None},
                  "maskiert": {}, "fehler": {"c": "ClaudeFehler: aus"}, "dauer_ms": {}}, pfad)
    za.haenge_an({"variante": "B1", "lauf": 1, "gruppe": "G3", "ranglisten": {"c": [3]},
                  "maskiert": {"c": 0}, "fehler": {}, "dauer_ms": {"c": 7}}, pfad)

    zeilen = {z["gruppe"]: z for z in za.lade_roh(tmp_path)}

    assert zeilen["G2"]["ranglisten"] == {"a": [1], "b": [2]}
    assert zeilen["G3"]["ranglisten"] == {"c": [3]} and zeilen["G3"]["fehler"] == {}


def test_laeufe_nimmt_nur_vollstaendige_laeufe():
    gold = [_g("G1-1", "G1", 2, [3]), _g("G2-1", "G2", 4, [8])]
    zeilen = [
        {"variante": "B1", "lauf": 1, "gruppe": "G1", "ranglisten": {"G1:szene:2": [3]}, "maskiert": {}, "fehler": {}},
        {"variante": "B1", "lauf": 1, "gruppe": "G2", "ranglisten": {"G2:szene:4": [1]}, "maskiert": {}, "fehler": {}},
        {"variante": "B1", "lauf": 2, "gruppe": "G1", "ranglisten": {"G1:szene:2": [3]}, "maskiert": {}, "fehler": {}},
        {"variante": "B1", "lauf": 3, "gruppe": "G1", "ranglisten": {"G1:szene:2": None}, "maskiert": {}, "fehler": {"G1:szene:2": "x"}},
        {"variante": "B1", "lauf": 3, "gruppe": "G2", "ranglisten": {"G2:szene:4": [8]}, "maskiert": {}, "fehler": {}},
    ]

    l = za.laeufe(zeilen, gold, "B1")

    assert list(l) == [1]
    assert l[1]["recall"]["gesamt"] == {"treffer": 1, "n": 2, "fehlt": 0}
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: FAIL `AttributeError: module 'scripts.zitatauswahl' has no attribute 'rangliste'`.

- [ ] **Step 3: Implementieren**

In `scripts/zitatauswahl.py` vor `def _verbinde` einfügen:

```python
def rangliste(zuordnungen: list[dict]) -> list[int]:
    """Wie ``schaerfung.offene_stellen``/``web_daten.schaerfungsliste``:
    Staerke absteigend, bei Gleichstand die Listenposition (= Reihenfolge
    des Modells bzw. ``id``); jedes Thema nur einmal (Spec E1)."""
    geordnet = sorted(enumerate(zuordnungen), key=lambda p: (-(p[1].get("staerke") or 0), p[0]))
    aus: list[int] = []
    for _, z in geordnet:
        if z["verdichtung_thema_id"] not in aus:
            aus.append(z["verdichtung_thema_id"])
    return aus


def _positive(gold: list[dict]) -> list[dict]:
    return [g for g in gold if g["polaritaet"] == "positiv"]


def ranglisten_historisch(conn, gold: list[dict]) -> dict[str, list[int]]:
    """B0 (Spec E5): je Gold-Ziel die Zeilen der LETZTEN Runde, in der dieses
    Ziel Zeilen hat -- entfernte eingeschlossen (sie waren in ihrer Runde
    sichtbar)."""
    aus: dict[str, list[int]] = {}
    historie: dict[int, list] = {}
    for g in _positive(gold):
        schluessel = ziel_schluessel(g)
        if schluessel in aus:
            continue
        if g["chat_id"] not in historie:
            historie[g["chat_id"]] = repo.schaerfungen_historie(conn, g["chat_id"])
        spalte = "szene_id" if g["ziel"]["art"] == "szene" else "figur_id"
        zeilen = [dict(z) for z in historie[g["chat_id"]] if z[spalte] == g["ziel"]["id"]]
        if not zeilen:
            aus[schluessel] = []
            continue
        letzte = max(z["runde"] for z in zeilen)
        aus[schluessel] = rangliste([z for z in zeilen if z["runde"] == letzte])
    return aus


def recall_at_k(ranglisten: dict, gold: list[dict], k: int = K) -> dict[str, dict]:
    """Spec E1: je Gruppe und gesamt, nur positive Stellen im Pool. Fehlt die
    Rangliste eines Ziels (``None``/nicht da), zaehlt die Stelle unter ``fehlt``."""
    aus = {gr: {"treffer": 0, "n": 0, "fehlt": 0}
           for gr in sorted({g["gruppe"] for g in gold}) + ["gesamt"]}
    for g in _positive(gold):
        if not g["im_pool"]:
            continue
        liste = ranglisten.get(ziel_schluessel(g))
        for gr in (g["gruppe"], "gesamt"):
            if liste is None:
                aus[gr]["fehlt"] += 1
                continue
            aus[gr]["n"] += 1
            if set(g["thema_ids"]) & set(liste[:k]):
                aus[gr]["treffer"] += 1
    return aus


def negativ_at_k(ranglisten: dict, gold: list[dict], k: int = K) -> dict[str, int]:
    """Verworfene Paare (Spec E3), deren Thema an IHREM Ziel in den Top-k
    steht -- nur an Zielen mit Rangliste (= Gold-Zielen)."""
    aus: dict[str, int] = {"gesamt": 0}
    for g in gold:
        if g["polaritaet"] != "negativ":
            continue
        liste = ranglisten.get(ziel_schluessel(g))
        if not liste:
            continue
        if set(g["thema_ids"]) & set(liste[:k]):
            aus[g["gruppe"]] = aus.get(g["gruppe"], 0) + 1
            aus["gesamt"] += 1
    return aus


def pool_recall(gold: list[dict]) -> dict[str, tuple[int, int]]:
    aus: dict[str, list[int]] = {}
    for g in _positive(gold):
        for gr in (g["gruppe"], "gesamt"):
            aus.setdefault(gr, [0, 0])
            aus[gr][0] += int(g["im_pool"])
            aus[gr][1] += 1
    return {gr: (a, n) for gr, (a, n) in aus.items()}


def haenge_an(zeile: dict, pfad) -> None:
    Path(pfad).parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "a", encoding="utf-8") as f:
        f.write(json.dumps(zeile, ensure_ascii=False, sort_keys=True) + "\n")


def lade_roh(verz=ROH) -> list[dict]:
    """Alle Rohzeilen; Zeilen desselben (variante, lauf, gruppe) -- etwa ein
    Neu-Lauf in mehreren Aufrufen je Ziel -- werden zusammengefuehrt."""
    zusammen: dict[tuple, dict] = {}
    for pfad in sorted(Path(verz).glob("*.jsonl")):
        with open(pfad, encoding="utf-8") as f:
            for roh in f:
                if not roh.strip():
                    continue
                z = json.loads(roh)
                schluessel = (z["variante"], z["lauf"], z["gruppe"])
                ziel = zusammen.setdefault(schluessel, {
                    "variante": z["variante"], "lauf": z["lauf"], "gruppe": z["gruppe"],
                    "ranglisten": {}, "maskiert": {}, "fehler": {}, "dauer_ms": {}})
                for feld in ("ranglisten", "maskiert", "fehler", "dauer_ms"):
                    ziel[feld].update(z.get(feld) or {})
                # Eine spaetere erfolgreiche Wiederholung (``--nur``) hebt den
                # Fehler desselben Ziels in diesem Lauf auf.
                for s, r in (z.get("ranglisten") or {}).items():
                    if r is not None and s not in (z.get("fehler") or {}):
                        ziel["fehler"].pop(s, None)
    return list(zusammen.values())


def laeufe(zeilen: list[dict], gold: list[dict], variante: str, k: int = K) -> dict[int, dict]:
    """Nur vollstaendige Laeufe: jedes Gold-Ziel hat eine Rangliste, kein
    Ziel hat einen Fehler (Spec § 6: ein Lauf mit Fehler zaehlt nicht fuer E7)."""
    noetig = {ziel_schluessel(g) for g in _positive(gold) if g["im_pool"]}
    je_lauf: dict[int, dict] = {}
    for z in zeilen:
        if z["variante"] != variante:
            continue
        l = je_lauf.setdefault(z["lauf"], {"ranglisten": {}, "fehler": {}, "maskiert": 0})
        l["ranglisten"].update(z["ranglisten"])
        l["fehler"].update(z.get("fehler") or {})
        l["maskiert"] += sum((z.get("maskiert") or {}).values())
    aus = {}
    for lauf, l in sorted(je_lauf.items()):
        if l["fehler"] or any(l["ranglisten"].get(s) is None for s in noetig):
            continue
        aus[lauf] = {"recall": recall_at_k(l["ranglisten"], gold, k),
                     "ranglisten": l["ranglisten"], "maskiert": l["maskiert"]}
    return aus


#: Spec E7: so viele Gold-Stellen muss eine Variante im Mittel mehr treffen.
MINDEST_GEWINN = 2


def entscheide(basis: dict[int, dict], variante: dict[int, dict]) -> tuple[bool, list[str]]:
    """Spec E7 -- alle drei Bedingungen, sonst kein Fix."""
    if not basis or not variante:
        return False, ["zu wenige vollstaendige Laeufe"]

    def werte(l, gr):
        return [x["recall"][gr]["treffer"] for x in l.values()]

    def mittel(l, gr):
        w = werte(l, gr)
        return sum(w) / len(w)

    gruende = []
    gewinn = mittel(variante, "gesamt") - mittel(basis, "gesamt")
    if gewinn < MINDEST_GEWINN:
        gruende.append(f"Gewinn {gewinn:+.2f} Stellen < {MINDEST_GEWINN}")
    if min(werte(variante, "gesamt")) < max(werte(basis, "gesamt")):
        gruende.append("schlechtester Variantenlauf unter bestem Basislauf")
    gruppen = sorted(g for g in next(iter(basis.values()))["recall"] if g != "gesamt")
    for gr in gruppen:
        if mittel(variante, gr) < mittel(basis, gr):
            gruende.append(f"{gr} sinkt ({mittel(basis, gr):.2f} -> {mittel(variante, gr):.2f})")
    return not gruende, gruende
```

In `main` die Unterbefehle erweitern. Ersetze den Block
`for name in ("gold", "pruefe"):` … bis vor `a = p.parse_args(argv)` durch:

```python
    for name in ("gold", "pruefe", "historisch"):
        s = sub.add_parser(name)
        s.add_argument("--db", default=str(KOPIE))
        s.add_argument("--gold", default=str(GOLD))
        if name == "gold":
            s.add_argument("--quelle", default=str(QUELLE))
        if name == "historisch":
            s.add_argument("--aus", default=str(ROH / "B0.jsonl"))
```

und vor `return 2` am Ende von `main`:

```python
    if a.befehl == "historisch":
        gold = lade_gold(a.gold)
        fehler = pruefe_gold(conn, gold)
        if fehler:
            print("\n".join(fehler), file=sys.stderr)
            return 1
        ranglisten = ranglisten_historisch(conn, gold)
        if Path(a.aus).exists():
            Path(a.aus).unlink()  # B0 ist deterministisch: neu schreiben statt anhaengen
        for gruppe in sorted({g["gruppe"] for g in gold}):
            eigene = {s: r for s, r in ranglisten.items() if s.startswith(gruppe + ":")}
            haenge_an({"variante": "B0", "lauf": 1, "gruppe": gruppe, "ranglisten": eigene,
                       "maskiert": {}, "fehler": {}, "dauer_ms": {}}, a.aus)
        r = recall_at_k(ranglisten, gold)
        for gr, w in r.items():
            print(f"{gr}: Recall@{K} {w['treffer']}/{w['n']}")
        return 0
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: alle grün.

- [ ] **Step 5: B0 auf der Kopie**

Run: `uv run --extra dev python -m scripts.zitatauswahl historisch --db var/zitatauswahl/padua-kopie.db`
Expected (Richtwert aus der Sondierung, Spec F6):
```
G1: Recall@10 1/5
G2: Recall@10 4/5
G3: Recall@10 2/5
gesamt: Recall@10 7/15
```
Bei Abweichung die Ränge mit dem Bericht aus Task 6 (Tabelle „Rang jeder
Gold-Stelle") gegen Spec F6 halten und den Unterschied im Bericht erklären.
Die Zahlen nicht anpassen.

- [ ] **Step 6: Commit**

```bash
git add scripts/zitatauswahl.py tests/test_zitatauswahl.py docs/messung/zitatauswahl/B0.jsonl
git commit -m "feat(messung): Recall@10 je Ziel, Schwelle E7, Baseline B0 historisch (t_2f905d2c)"
```

---

### Task 5: Neu-Lauf über den Proxy (B1), Leck-Maskierung, Datenschutz

**Files:**
- Modify: `scripts/zitatauswahl.py`
- Create (erzeugt): `docs/messung/zitatauswahl/B1.jsonl`
- Test: `tests/test_zitatauswahl.py`

**Interfaces:**
- Consumes: `schaerfung.werte_aus` (Task 2), `schaerfung._eintraege`, `schaerfung._ziele`,
  `schaerfung._erfundenes_zeilen`, `schaerfung._hintergrund_zeilen`, `schaerfung._material_zeilen`,
  `schaerfung._baue_nutzertext_ziel`, `schaerfung.T._ZIEL_ZEILE`, `schaerfung.ZIEL_SCHEMA`,
  `schaerfung.PROMPT_ZITAT_WOERTER`, `schaerfung.CLAUDE_TIMEOUT_S`, `schaerfung.CLAUDE_WARTEZEITEN`,
  `schaerfung.prompt()`, `szene_claude.schema(conn, e, klient, chat_id, system, nutzer, schema_, art, timeout, wartezeiten=..., modell=...)`,
  `szene_claude.MODELL_VORGABE`, `einstellungen.Einstellungen`, `rangliste`, `haenge_an`.
- Produces:
  - `maskiere(text: str, fragmente_: list[str]) -> tuple[str, int]`
  - `nutzertext_maskiert(conn, chat_id, eintraege, ziel, fragmente_) -> tuple[str, int]`
  - `einstellungen_messung(db_pfad: str)` → `Einstellungen` mit `szene_anbieter="claude"`, `schaerfung_modell=szene_claude.MODELL_VORGABE`
  - `neu_lauf(conn, e, klient, gold, gruppe, system, *, nur=None) -> dict`: eine Rohzeile ohne `variante`/`lauf`.
  - CLI `neu --db --gold --variante --lauf --gruppe [--nur SCHLUESSEL] [--prompt PFAD] [--aus PFAD]` (Vorgabe `--aus` = `ROH / f"{variante}.jsonl"`)

- [ ] **Step 1: Failing tests anhängen**

```python
# --- Neu-Lauf -----------------------------------------------------------------


def test_nutzertext_ohne_maske_ist_bitgleich_zum_betrieb(lage):
    eintraege = schaerfung._eintraege(lage, 1)
    for ziel in schaerfung._ziele(lage, 1):
        assert za.nutzertext_maskiert(lage, 1, eintraege, ziel, []) == (
            schaerfung._baue_nutzertext_ziel(lage, 1, eintraege, ziel), 0)


def test_maske_trifft_nur_kopf_und_ziel_nicht_das_material(lage):
    s = _szenen(lage)
    repo.setze_szenenfeld(lage, s[1], "titel", "Ich habe zwanzig Jahre genaeht")
    eintraege = schaerfung._eintraege(lage, 1)
    ziel = next(z for z in schaerfung._ziele(lage, 1) if z["id"] == s[1])

    text, n = za.nutzertext_maskiert(lage, 1, eintraege, ziel, ["ich habe zwanzig Jahre genaeht"])

    kopf, material = text.split(schaerfung.T._MATERIAL_KOPF, 1)
    assert n >= 2  # Szenenliste und Ziel-Zeile
    assert "zwanzig Jahre" not in kopf and "[…]" in kopf
    assert "ich habe zwanzig Jahre genaeht" in material


class _Proxy:
    def __init__(self, antwort=None, fehler=None):
        self.antwort, self.fehler, self.aufrufe = antwort, fehler, []

    def __call__(self, conn, e, klient, chat_id, system, nutzer, schema_, art, timeout,
                 bei_teil=None, teil_feld=None, wartezeiten=None, modell=None):
        self.aufrufe.append({"modell": modell, "art": art, "system": system, "nutzer": nutzer})
        if self.fehler:
            raise self.fehler
        return self.antwort


@pytest.fixture
def ohne_kimi(monkeypatch):
    """Datenschutz/Kosten: der Neu-Lauf darf llm.LLM nie anfassen."""
    class Verboten:
        def __init__(self, *a, **k):
            raise AssertionError("Kimi/gemma im Neu-Lauf")
    monkeypatch.setattr(llm, "LLM", Verboten)


def test_neu_lauf_nur_ueber_den_proxy_mit_opus(lage, tmp_path, monkeypatch, ohne_kimi):
    t, s = _themen(lage), _szenen(lage)
    proxy = _Proxy({"eintrag_nummern": [2, 1], "staerke": [3, 3], "begruendungen": ["x", "y"]})
    monkeypatch.setattr(szene_claude, "schema", proxy)
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})

    zeile = za.neu_lauf(lage, za.einstellungen_messung(str(tmp_path / "t.db")), None,
                        gold, "G1", "SYSTEM")

    assert set(zeile["ranglisten"]) == {f"G1:szene:{s[1]}", f"G1:szene:{s[2]}"}
    assert zeile["ranglisten"][f"G1:szene:{s[1]}"] == [t["Stadt"], t["Arbeit"]]
    assert zeile["fehler"] == {}
    assert {a["modell"] for a in proxy.aufrufe} == {"claude-opus-5"}
    assert all(a["system"] == "SYSTEM" for a in proxy.aufrufe)


def test_neu_lauf_notiert_fehler_statt_rueckfall(lage, tmp_path, monkeypatch, ohne_kimi):
    monkeypatch.setattr(szene_claude, "schema", _Proxy(fehler=szene_claude.ClaudeFehler("aus")))
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})

    zeile = za.neu_lauf(lage, za.einstellungen_messung(str(tmp_path / "t.db")), None,
                        gold, "G1", "SYSTEM")

    assert all(r is None for r in zeile["ranglisten"].values())
    assert all("ClaudeFehler" in f for f in zeile["fehler"].values())


def test_skript_importiert_keine_interviewstrecke():
    """Interviews bleiben hart auf Kimi (Karte): das Messskript ruft weder
    Verdichter noch Erkenner noch die Aufnahme-Pipeline noch llm direkt."""
    baum = ast.parse(Path("scripts/zitatauswahl.py").read_text(encoding="utf-8"))
    namen = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom) and knoten.module:
            namen |= {f"{knoten.module}.{a.name}" for a in knoten.names}
        elif isinstance(knoten, ast.Import):
            namen |= {a.name for a in knoten.names}
    verboten = {f"interview_theater.{m}" for m in ("verdichter", "erkenner", "aufnahme", "llm")}
    assert not namen & verboten
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: FAIL `AttributeError: … has no attribute 'nutzertext_maskiert'`.

- [ ] **Step 3: Implementieren**

Oben in `scripts/zitatauswahl.py` die Importe ergänzen:

```python
import os
import time
```

Vor `def _verbinde` einfügen:

```python
def maskiere(text: str, fragmente_: list[str]) -> tuple[str, int]:
    """Spec E6: jedes Gold-Fragment (ab drei Woertern) im Text durch ``[…]``
    ersetzen, Gross-/Kleinschreibung und Satzzeichen dazwischen egal."""
    anzahl = 0
    for f in sorted(set(fragmente_), key=len, reverse=True):
        worte = _woerter(f)
        if len(worte) < 3:
            continue
        muster = r"(?<!\w)" + r"\W+".join(re.escape(w) for w in worte) + r"(?!\w)"
        text, n = re.subn(muster, "[…]", text, flags=re.IGNORECASE)
        anzahl += n
    return text, anzahl


def nutzertext_maskiert(conn, chat_id: int, eintraege: list[dict], ziel: dict,
                        fragmente_: list[str]) -> tuple[str, int]:
    """Derselbe Nutzertext wie ``schaerfung._baue_nutzertext_ziel`` (ohne
    Fragmente bitgleich, Test), aber Gold-Fragmente im Nicht-Material-Teil
    maskiert -- die Materialliste bleibt unangetastet."""
    from interview_theater import schaerfung

    kopf = schaerfung._erfundenes_zeilen(conn, chat_id)
    hintergrund = schaerfung._hintergrund_zeilen(conn, chat_id)
    if hintergrund:
        kopf.append("")
        kopf.extend(hintergrund)
    kopf.append("")
    kopf.append(schaerfung.T._ZIEL_ZEILE.format(beschreibung=ziel["beschreibung_text"]))
    kopf.append("")
    text_kopf, anzahl = maskiere("\n".join(kopf), fragmente_)
    material = schaerfung._material_zeilen(eintraege, woerter=schaerfung.PROMPT_ZITAT_WOERTER)
    return text_kopf + "\n" + "\n".join(material), anzahl


def einstellungen_messung(db_pfad: str):
    """Einstellungen ohne Umgebung: nur der Claude-Pfad ist echt; Kimi-Felder
    sind Platzhalter, damit ein versehentlicher Kimi-Aufruf scheitert statt
    zu kosten."""
    from interview_theater import einstellungen, szene_claude

    return einstellungen.Einstellungen(
        bot_token="-", bot_name="messung-zitatauswahl", db_pfad=db_pfad,
        audio_verz="var/zitatauswahl/audio", llm_url="-", llm_key="-", llm_modell="-",
        stt_basis="-", stt_produkt="-", erkenner_modell="-",
        szene_anbieter="claude", schaerfung_modell=szene_claude.MODELL_VORGABE,
    )


def neu_lauf(conn, e, klient, gold: list[dict], gruppe: str, system: str, *,
             nur: list[str] | None = None, eintraege: list[dict] | None = None) -> dict:
    """B1/I-a/I-b (Spec E5): je Gold-Ziel der Gruppe EIN Schema-Aufruf ueber
    den Proxy, seriell, ohne Rueckfall. ``eintraege`` erlaubt I-b eine
    veraenderte Materialliste; sonst ``schaerfung._eintraege``."""
    from interview_theater import schaerfung, szene_claude

    positiv = [g for g in _positive(gold) if g["gruppe"] == gruppe]
    if not positiv:
        raise SystemExit(f"keine Gold-Stellen fuer {gruppe}")
    chat_id = positiv[0]["chat_id"]
    if eintraege is None:
        eintraege = schaerfung._eintraege(conn, chat_id)
    nach_nummer = {x["nummer"]: x for x in eintraege}
    alle_fragmente = [f for g in _positive(gold) for f in g["fragmente"]]
    ziele = {(z["art"], z["id"]): z for z in schaerfung._ziele(conn, chat_id)}
    zeile = {"gruppe": gruppe, "ranglisten": {}, "maskiert": {}, "fehler": {}, "dauer_ms": {}}
    for schluessel in sorted({ziel_schluessel(g) for g in positiv}):
        if nur and schluessel not in nur:
            continue
        _, art, zid = schluessel.split(":")
        ziel = ziele.get((art, int(zid)))
        if ziel is None:
            zeile["ranglisten"][schluessel] = None
            zeile["fehler"][schluessel] = "Ziel fehlt in der Kopie"
            continue
        nutzer, anzahl = nutzertext_maskiert(conn, chat_id, eintraege, ziel, alle_fragmente)
        zeile["maskiert"][schluessel] = anzahl
        start = time.monotonic()
        try:
            ergebnis = szene_claude.schema(
                conn, e, klient, chat_id, system, nutzer, schaerfung.ZIEL_SCHEMA,
                f"messung_zitatauswahl_{art}_{zid}", timeout=schaerfung.CLAUDE_TIMEOUT_S,
                wartezeiten=schaerfung.CLAUDE_WARTEZEITEN, modell=e.schaerfung_modell,
            )
            zeile["ranglisten"][schluessel] = rangliste(
                schaerfung.werte_aus(ergebnis, ziel, nach_nummer))
        except Exception as fehler:  # Spec § 6: notieren, nicht ersetzen
            zeile["ranglisten"][schluessel] = None
            zeile["fehler"][schluessel] = f"{type(fehler).__name__}: {fehler}"[:300]
        zeile["dauer_ms"][schluessel] = int((time.monotonic() - start) * 1000)
    return zeile
```

In `main`: Parser ergänzen (nach der `for name in (...)`-Schleife):

```python
    n = sub.add_parser("neu")
    n.add_argument("--db", default=str(KOPIE))
    n.add_argument("--gold", default=str(GOLD))
    n.add_argument("--variante", required=True, choices=["B1", "I-a", "I-b"])
    n.add_argument("--lauf", type=int, required=True)
    n.add_argument("--gruppe", required=True, choices=sorted(GRUPPEN))
    n.add_argument("--nur", nargs="*", default=None, help="nur diese Ziel-Schluessel, z. B. G2:szene:5")
    n.add_argument("--prompt", default=None, help="Kandidat-Prompt statt schaerfung.prompt()")
    n.add_argument("--mit-frage", action="store_true", help="nur I-b (Task 8)")
    n.add_argument("--aus", default=None)
```

und vor `return 2`:

```python
    if a.befehl == "neu":
        import httpx

        from interview_theater import schaerfung

        # Profil nur hier setzen (nicht beim Import): Padua-Prompt und -Texte.
        os.environ.setdefault("IT_WORKSHOP", "padua-2026")
        gold = lade_gold(a.gold)
        fehler = pruefe_gold(conn, gold)
        if fehler:
            print("\n".join(fehler), file=sys.stderr)
            return 1
        system = Path(a.prompt).read_text(encoding="utf-8") if a.prompt else schaerfung.prompt()
        eintraege = None
        if a.mit_frage:
            eintraege = eintraege_mit_frage(conn, GRUPPEN[a.gruppe])
        e = einstellungen_messung(a.db)
        with httpx.Client(timeout=schaerfung.CLAUDE_TIMEOUT_S) as klient:
            zeile = neu_lauf(conn, e, klient, gold, a.gruppe, system, nur=a.nur, eintraege=eintraege)
        zeile.update(variante=a.variante, lauf=a.lauf)
        haenge_an(zeile, a.aus or ROH / f"{a.variante}.jsonl")
        for s, r in sorted(zeile["ranglisten"].items()):
            print(s, "FEHLER " + zeile["fehler"][s] if r is None else f"{len(r)} Stellen",
                  f"maskiert {zeile['maskiert'].get(s, 0)}", f"{zeile['dauer_ms'].get(s, 0)} ms")
        return 0
```

`eintraege_mit_frage` entsteht erst in Task 8. Bis dahin oben vor `main` eine Platzhalter-Sperre einfügen,
die Task 8 ersetzt:

```python
def eintraege_mit_frage(conn, chat_id: int) -> list[dict]:
    """I-b (Task 8) -- nur nach Birks Freigabe des Datenflusses (Spec E8)."""
    raise SystemExit("I-b ist gesperrt: Datenschutz-Gate (Spec E8) nicht freigegeben")
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: alle grün.

- [ ] **Step 5: Commit (Code)**

```bash
git add scripts/zitatauswahl.py tests/test_zitatauswahl.py
git commit -m "feat(messung): Neu-Lauf der Schaerfung je Gold-Ziel ueber den Proxy, Leck-Maskierung, ohne Kimi (t_2f905d2c)"
```

- [ ] **Step 6: Ein Ziel als Probe (0 CHF)**

Run (Timeout 900000): `uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante B1 --lauf 0 --gruppe G1 --aus var/zitatauswahl/probe.jsonl`
Expected: eine Zeile `G1:szene:2 <n> Stellen maskiert <m> <ms> ms`, kein
`FEHLER`. Die Probe liegt unter `var/` und zählt nicht. Bei `FEHLER`: Proxy
prüfen (Task 0 Step 3); nicht auf ein anderes Modell ausweichen.

- [ ] **Step 7: B1, drei Läufe × drei Gruppen**

Je Aufruf ein Lauf einer Gruppe (Timeout 900000; G2 hat vier Ziele — läuft ein
Aufruf in den Timeout, mit `--nur G2:szene:4 G2:szene:5` und danach
`--nur G2:szene:6 G2:szene:7` teilen; `lade_roh` führt das zusammen):

```
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante B1 --lauf 1 --gruppe G1
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante B1 --lauf 1 --gruppe G2
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante B1 --lauf 1 --gruppe G3
```
dasselbe für `--lauf 2` und `--lauf 3`. Expected: keine `FEHLER`-Zeile. Ein
Ziel mit Fehler: denselben Lauf nur für dieses Ziel wiederholen
(`--lauf <n> --gruppe <G> --nur <schluessel>`). Die Fehlerzeile bleibt in der
Datei (Nachvollziehbarkeit); `lade_roh` hebt den Fehler durch die
erfolgreiche Wiederholung auf (Test `test_roh_zeilen_…`). Die Zahl der
Wiederholungen kommt in die Commit-Message.

- [ ] **Step 8: Commit (Daten)**

```bash
git add docs/messung/zitatauswahl/B1.jsonl
git commit -m "messung: Baseline B1 Neu-Lauf, 3 Laeufe je Gruppe (t_2f905d2c)"
```

---

### Task 6: Bericht erzeugen (mit Format-Doku für Messung 2)

**Files:**
- Modify: `scripts/zitatauswahl.py`
- Create (erzeugt): `docs/messung/2026-10-zitatauswahl.md`
- Test: `tests/test_zitatauswahl.py`

**Interfaces:**
- Consumes: `lade_gold`, `lade_roh`, `laeufe`, `entscheide`, `negativ_at_k`, `pool_recall`, `ziel_schluessel`.
- Produces: `schreibe_bericht(gold: list[dict], zeilen: list[dict], pfad) -> str`; CLI `bericht [--gold] [--roh] [--aus]`.
  Der Bericht hat diese Überschriften (Messung 2 und Tests verlassen sich darauf):
  `## Kurzfassung`, `## Gold-Korpus`, `### Format`, `### Herkunft und Diskrepanzen`,
  `## Ergebnisse je Gruppe`, `## Rang jeder Gold-Stelle`, `## Entscheidungen (E7)`,
  `## Kommandos zum Nachrechnen`, `## Grenzen`.

- [ ] **Step 1: Failing test anhängen**

```python
# --- Bericht ------------------------------------------------------------------


def test_bericht_traegt_abschnitte_zahlen_und_kommandos(tmp_path):
    gold = [dict(_g("G1-1", "G1", 2, [3]), wortlaut="x", frage="f?"),
            dict(_g("G1-2", "G1", 2, [8]), wortlaut="y", frage="g?")]
    zeilen = [{"variante": "B0", "lauf": 1, "gruppe": "G1", "ranglisten": {"G1:szene:2": [3, 1]},
               "maskiert": {}, "fehler": {}, "dauer_ms": {}}]
    zeilen += [{"variante": "B1", "lauf": i, "gruppe": "G1", "ranglisten": {"G1:szene:2": [3]},
                "maskiert": {"G1:szene:2": 1}, "fehler": {}, "dauer_ms": {}} for i in (1, 2, 3)]
    pfad = tmp_path / "bericht.md"

    text = za.schreibe_bericht(gold, zeilen, pfad)

    assert pfad.read_text(encoding="utf-8") == text
    for kopf in ("## Kurzfassung", "## Gold-Korpus", "### Format", "### Herkunft und Diskrepanzen",
                 "## Ergebnisse je Gruppe", "## Rang jeder Gold-Stelle", "## Entscheidungen (E7)",
                 "## Kommandos zum Nachrechnen", "## Grenzen"):
        assert kopf in text
    assert "| G1 | B0 | 1/2 |" in text
    assert "python -m scripts.zitatauswahl historisch" in text
    assert "korpus/zitatauswahl_gold.jsonl" in text
    assert "I-a: nicht gemessen" in text
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: FAIL `AttributeError: … 'schreibe_bericht'`.

- [ ] **Step 3: Implementieren**

Vor `def _verbinde` einfügen:

```python
VARIANTEN = ("B0", "B1", "I-a", "I-b")

FORMAT_DOKU = """\
Datei: `korpus/zitatauswahl_gold.jsonl` -- eine JSON-Zeile je Stelle, UTF-8,
sortiert nach `id`. Leser: `scripts.zitatauswahl.lade_gold(pfad)`.
Treffer-Regel: `scripts.zitatauswahl.trifft(kandidat, gold)`.

| Feld | Bedeutung |
|---|---|
| `id` | `G1-1` (positiv, Gruppe-Karte) bzw. `G1-n-0286` (negativ, kleinste `schaerfung.id`) |
| `gruppe` | `G1` / `G2` / `G3` |
| `chat_id` | 7000000000000 / …001 / …002 |
| `polaritaet` | `positiv` (im Stueck, Plakat) / `negativ` (`nein` an diesem Ziel, nie `ja`, nirgends positiv) |
| `ziel` | `{"art": "szene"|"figur", "nummer", "id", "titel"}` -- `id` = `szene.id`/`figur.id` in padua.db |
| `frage` | Interviewfrage laut Plakat (EN, nur positiv) |
| `wortlaut` | Plakatwortlaut, Auslassungen ` … ` (nur positiv) |
| `fragmente` | Teile zwischen den Auslassungen im Originalwortlaut des Transkripts; jedes besteht `zitat.pruefe` (nur positiv) |
| `aufnahme_id` | Interview (Kopf), in dem die Stelle steht |
| `verdichtung_thema_id` | das Thema im Pool (`repo.gepruefte_themen`), sonst `null` |
| `thema_ids` | alle Themen derselben Stelle (auch aus entfernten Verdichtungen) |
| `im_pool` | ob eines davon im Pool der Schaerfung steht |
| `schaerfung_ids` | nur negativ: die `nein`-Zeilen |
| `quelle` | positiv: entities-Commit, Datei, Karte, Label; negativ: Tabelle |

**Recall@10** (Spec E1) gilt **je Ziel**: eine positive Stelle im Pool ist
getroffen, wenn eines ihrer `thema_ids` unter den ersten 10 verschiedenen
Themen der Rangliste IHRES Ziels steht. Sortiert wird wie im Betrieb:
`(-staerke, runde, Reihenfolge des Modells)`. Gemittelt wird mikro, je Gruppe
und gesamt. Fuer Kandidaten ohne Thema-Kennung (Agent) gilt `trifft`: alle
`fragmente` stehen im Kandidatentext.
"""

DISKREPANZEN = """\
Positiv sind nur die Karten der drei Gruppenplakate (hermes-entities `3fa1f46`,
`### cards: quotes`, "Variante A: nur Zitate, die im Stueck landen"):
G1 5, G2 5, G3 6.

- Kommentar 1402 (hermes-dev, t_56f8d856) nennt "G2 8 Stellen". Plakat G2 hat
  5; die Notizzeile "Int. 9, 13, 29, 21, 38" stammt aus einer frueheren
  Fassung. Das Prozessplakat (`01_prozess.md`, "Nicht doppelt zu den
  Gruppenplakaten") illustriert nur und belegt keine Verwendung im Stueck --
  nicht im Korpus.
- Kommentar 1402 nennt ein generisches Zitat (G2-2) einen generischen
  Erstvorschlag; das Plakat G2 Karte 2 verwendet die Stelle. Massgeblich ist
  der Plakatstand; 1402 ist nur Quelle der Hypothesen.
- `entfernt_am` ist nicht "verworfen" (G1-4 ist positiv und hat nur
  entfernte Zeilen). Negativ ist nur `nein` ohne `ja` (Spec F7.3).
- Hypothese (d) "nachgeladenes Material nie im Pool" ist fuer den Pool
  widerlegt (Queer-Viertel, lingua del santo stehen geprueft im Pool); es
  stand in der Rangliste zu weit hinten.

Volle Begruendung: `docs/superpowers/specs/2026-10-11-zitatauswahl-gold-recall-design.md`.
"""

KOMMANDOS = """\
```
uv run --extra dev python -m scripts.zitatauswahl kopie
uv run --extra dev python -m scripts.zitatauswahl gold --db var/zitatauswahl/padua-kopie.db
uv run --extra dev python -m scripts.zitatauswahl pruefe --db var/zitatauswahl/padua-kopie.db
uv run --extra dev python -m scripts.zitatauswahl historisch --db var/zitatauswahl/padua-kopie.db
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante B1 --lauf 1 --gruppe G1
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante I-a --lauf 1 --gruppe G1 --prompt docs/messung/zitatauswahl/prompt-I-a.md
uv run --extra dev python -m scripts.zitatauswahl bericht
uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py
```

(`neu` je Variante fuer `--lauf 1 2 3` und `--gruppe G1 G2 G3`; Mutationstest:
`test_mutation_*` in `tests/test_zitatauswahl.py`. Rohergebnisse:
`docs/messung/zitatauswahl/*.jsonl`. Kopie und Proxy: Spec E5.)
"""

GRENZEN = """\
- n = 15 Stellen im Pool (G3-3 "Mara Venier" liegt ausserhalb, Hypothese c);
  eine Stelle sind 6,7 Prozentpunkte. Deshalb die Schwelle E7 (mindestens zwei
  Stellen, keine Ueberlappung der Laeufe, keine Gruppe schlechter).
- B0 ist verzerrt: die Gruppen haben aus den sichtbaren Top-5 gewaehlt.
  Verglichen wird nur Neu-Lauf gegen Neu-Lauf.
- Die Kopie zeigt den Stand vom 11.10.2026, nicht den zur Zeit der Schaerfung
  (07./08.10.); Gold-Fragmente im Nicht-Material-Teil sind maskiert (Spalte
  "maskiert", Spec E6).
- Der Pool selbst (ein Beleg je Thema, `verdichter.py`) ist nicht Gegenstand
  dieser Karte.
"""


def _zahl(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _zeile_variante(gruppe: str, variante: str, l: dict, l5: dict, gold: list[dict]) -> str | None:
    if not l:
        return None
    t = [x["recall"][gruppe]["treffer"] for x in l.values()]
    n = next(iter(l.values()))["recall"][gruppe]["n"]
    t5 = [x["recall"][gruppe]["treffer"] for x in l5.values()]
    neg = [negativ_at_k(x["ranglisten"], gold).get(gruppe, 0) for x in l.values()]
    mittel = sum(t) / len(t)
    spanne = f"{min(t)}–{max(t)}" if len(t) > 1 else str(t[0])
    zehn = f"{t[0]}/{n}" if len(t) == 1 else f"{_zahl(mittel)}/{n} ({spanne})"
    fuenf = _zahl(sum(t5) / len(t5)) if t5 else "–"
    return (f"| {gruppe} | {variante} | {zehn} | {fuenf} | {_zahl(sum(neg) / len(neg))} "
            f"| {len(l)} | {sum(x['maskiert'] for x in l.values())} |")


def _rang(liste: list[int] | None, themen: list[int]) -> str:
    if liste is None:
        return "?"
    for i, t in enumerate(liste, start=1):
        if t in themen:
            return str(i)
    return "–"


def schreibe_bericht(gold: list[dict], zeilen: list[dict], pfad=BERICHT) -> str:
    gruppen = sorted({g["gruppe"] for g in gold})
    l10 = {v: laeufe(zeilen, gold, v) for v in VARIANTEN}
    l5 = {v: laeufe(zeilen, gold, v, k=5) for v in VARIANTEN}
    ia_ok, ia_gruende = entscheide(l10["B1"], l10["I-a"])
    ib_basis = "I-a" if ia_ok else "B1"
    ib_ok, ib_gruende = entscheide(l10[ib_basis], l10["I-b"])

    def entscheidung(name, basis, ok, gruende):
        if not l10[name]:
            return f"- {name}: nicht gemessen (keine vollstaendigen Laeufe)."
        if ok:
            return f"- {name} gegen {basis}: **uebernommen** -- alle drei Bedingungen E7 erfuellt."
        return f"- {name} gegen {basis}: **nicht uebernommen** -- " + "; ".join(gruende) + "."

    entscheidungen = [entscheidung("I-a", "B1", ia_ok, ia_gruende),
                      entscheidung("I-b", ib_basis, ib_ok, ib_gruende)]
    fix = [n for n, ok in (("I-a", ia_ok), ("I-b", ib_ok)) if ok and l10[n]]

    pos = _positive(gold)
    neg = [g for g in gold if g["polaritaet"] == "negativ"]
    pool = pool_recall(gold)
    z = ["# Messung Zitatauswahl InScribe (Padua, Oktober 2026)", "",
         "Karte `t_2349e9a8` / Umsetzung `t_2f905d2c`. Erzeugt mit "
         "`python -m scripts.zitatauswahl bericht`; Spec: "
         "`docs/superpowers/specs/2026-10-11-zitatauswahl-gold-recall-design.md`.", "",
         "## Kurzfassung", ""]
    def gesamt(v):
        l = l10[v]
        if not l:
            return "nicht gemessen"
        t = [x["recall"]["gesamt"]["treffer"] for x in l.values()]
        n = next(iter(l.values()))["recall"]["gesamt"]["n"]
        return f"{_zahl(sum(t) / len(t))}/{n}"
    z.append("Recall@10 gesamt: " + " · ".join(f"{v} {gesamt(v)}" for v in VARIANTEN) + ".")
    z.append("")
    z.append(f"Fix: **{', '.join(fix)}** uebernommen." if fix
             else "Fix: **keiner** -- keine Intervention erfuellt die Schwelle E7.")
    z += ["", "## Gold-Korpus", "",
          f"Positiv {len(pos)} (im Pool {sum(g['im_pool'] for g in pos)}), negativ {len(neg)}. "
          + " · ".join(f"{gr}: positiv {pool[gr][1]}, im Pool {pool[gr][0]}, negativ "
                       f"{sum(1 for g in neg if g['gruppe'] == gr)}" for gr in gruppen) + ".",
          "", "### Format", "", FORMAT_DOKU, "### Herkunft und Diskrepanzen", "", DISKREPANZEN,
          "## Ergebnisse je Gruppe", "",
          "Recall@10: Mittel/n (min–max ueber Laeufe); Recall@5 = sichtbare Liste; "
          "Negativ@10 = verworfene Paare in den Top-10 (Mittel).", "",
          "| Gruppe | Variante | Recall@10 | Recall@5 | Negativ@10 | Laeufe | maskiert |",
          "|---|---|---|---|---|---|---|"]
    for gr in gruppen + ["gesamt"]:
        for v in VARIANTEN:
            zeile = _zeile_variante(gr, v, l10[v], l5[v], gold)
            if zeile:
                z.append(zeile)
    z += ["", "Pool-Recall (Obergrenze, Hypothese c): "
          + " · ".join(f"{gr} {pool[gr][0]}/{pool[gr][1]}" for gr in gruppen + ["gesamt"]) + ".",
          "", "## Rang jeder Gold-Stelle", "",
          "Rang des ersten Gold-Themas in der Rangliste des Ziels, je Lauf (`–` = nicht in der Liste, "
          "`?` = Fehler).", "",
          "| Stelle | Ziel | " + " | ".join(VARIANTEN) + " |",
          "|---|---|" + "---|" * len(VARIANTEN)]
    for g in pos:
        zellen = []
        for v in VARIANTEN:
            r = [_rang(x["ranglisten"].get(ziel_schluessel(g)), g["thema_ids"]) for x in l10[v].values()]
            zellen.append("/".join(r) if r else "")
        im = "" if g["im_pool"] else " (nicht im Pool)"
        z.append(f"| {g['id']}{im} | Szene {g['ziel']['nummer']} | " + " | ".join(zellen) + " |")
    z += ["", "## Entscheidungen (E7)", "", *entscheidungen, "",
          "## Kommandos zum Nachrechnen", "", KOMMANDOS, "## Grenzen", "", GRENZEN]
    text = "\n".join(z)
    Path(pfad).parent.mkdir(parents=True, exist_ok=True)
    Path(pfad).write_text(text, encoding="utf-8")
    return text
```

In `main` den Parser ergänzen:

```python
    b = sub.add_parser("bericht")
    b.add_argument("--gold", default=str(GOLD))
    b.add_argument("--roh", default=str(ROH))
    b.add_argument("--aus", default=str(BERICHT))
```

Der Befehl `bericht` braucht keine DB. Behandle ihn deshalb **vor**
`conn = _verbinde(a.db)` direkt nach dem `kopie`-Zweig:

```python
    if a.befehl == "bericht":
        schreibe_bericht(lade_gold(a.gold), lade_roh(a.roh), a.aus)
        print(f"Bericht: {a.aus}")
        return 0
```

Hinweis zum Test: Der Test erwartet `"I-a: nicht gemessen"`. Das liefert
`entscheidung("I-a", …)` bei leeren Läufen (`- I-a: nicht gemessen …`).

- [ ] **Step 4: Run, expect PASS**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: alle grün.

- [ ] **Step 5: Baseline-Bericht erzeugen**

Run: `uv run --extra dev python -m scripts.zitatauswahl bericht`
Expected: `Bericht: docs/messung/2026-10-zitatauswahl.md`. Darin B0 7/15
(Richtwert) und B1 mit drei Läufen. Lies die Tabelle „Rang jeder
Gold-Stelle" einmal gegen Spec F6 (B0-Spalte).

- [ ] **Step 6: Commit**

```bash
git add scripts/zitatauswahl.py tests/test_zitatauswahl.py docs/messung/2026-10-zitatauswahl.md
git commit -m "feat(messung): Bericht Zitatauswahl mit Gold-Format fuer Messung 2, Baseline B0/B1 (t_2f905d2c)"
```

---

### Task 7: Intervention I-a (Hypothese a: Reihenfolge nach Bühnenwirkung, Stärke 3 knapp)

**Files:**
- Create: `docs/messung/zitatauswahl/prompt-I-a.md`
- Create (erzeugt): `docs/messung/zitatauswahl/I-a.jsonl`, aktualisiert `docs/messung/2026-10-zitatauswahl.md`
- Modify (nur bei Übernahme): `interview_theater/sprachen/en/prompts/schaerfung.md`

**Interfaces:**
- Consumes: CLI `neu --prompt`, `bericht` (Tasks 5, 6).
- Produces: Entscheidung I-a (im Bericht) — Task 8 setzt bei Übernahme auf I-a auf.

- [ ] **Step 1: Kandidat-Prompt schreiben**

`docs/messung/zitatauswahl/prompt-I-a.md` ist der heutige EN-Prompt mit
geänderter Regel 2 und zwei neuen Regeln 7 und 8. Er enthält bewusst **kein**
Beispiel aus dem Padua-Material (sonst wäre er auf den Gold-Korpus
zugeschnitten):

```markdown
You check interview material AGAINST EXACTLY ONE target of an invented
theatre story: a single scene or a single character.

A theatre group has made up a setting, characters and a story with scenes by
themselves. Before that, they conducted and analysed interviews. Your task:
**find EVERYTHING in the material that gives this ONE target concrete
material** -- a situation, an attitude, a phrase, a contradiction the scene
or the character can use -- so the group can sharpen their invented story
against real material.

Below you first get what was invented (setting, characters, story, scenes
with numbers), then the ONE target you are checking right now, and then the
material: a numbered list of checked interview passages with theme, summary
and word-for-word quote.

**What you deliver**, as three lists of equal length, **in the order of
rule 7** (strongest first):

* `eintrag_nummern` -- the number of the material passage from the list
  below that fits THIS ONE target.
* `staerke` -- how closely it fits: 1 (fits at the edge), 2 (fits well) or 3
  (fits very closely, gives the scene/character something concrete).
* `begruendungen` -- a half-sentence on WHAT this passage gives the target
  (a concrete suggestion, not "fits well").

Optionally also `zitate`: the word-for-word sentence from the passage whose
number you point to. It is checked against the original.

Write your summary in English. Supporting quotes stay word for word in the
language of the transcript - never translate them, never tidy them up. An
Italian sentence stays Italian, an Arabic sentence stays Arabic. Here your
summary is the half-sentences in `begruendungen`.

**The rules:**

1. **Only from the list.** Point to numbers, invent nothing. A passage you
   can't find in the list doesn't exist.
2. **Check every passage seriously against THIS ONE target.** Name ALL
   numbers that contribute something concrete -- even if there are many.
   Don't force anything: a passage that only touches the target at the edge
   gets strength 1 or stays out entirely.
3. **You only check this ONE target**, not the whole story. Whether a
   passage might also fit another scene or character is not your question --
   a separate call handles that.
4. **A passage may appear more than once** if it contributes something
   different to this target more than once -- then it stands twice in
   `eintrag_nummern`, each with its own reason.
5. **The story is not up for negotiation.** You assign material; you don't
   suggest a different plot, a different ending or different characters.
6. **Only real quotes.** What stands in `zitate` stands like that in the
   list below.
7. **Order matters: strongest first.** List the numbers in the order a
   director would want to read them for THIS target. First come passages
   with their own, concrete, surprising voice: a specific image, a
   contradiction, a detail only this person says. General statements,
   proverbs and commonplaces come later, even if they fit the topic just as
   well. Fitting the topic is not by itself a reason to be early in the list.
8. **Strength 3 is scarce.** Give strength 3 to at most five passages for
   this target -- the ones you would put on stage first. Everything else that
   fits well gets 2.

Answer only in the given schema.
```

Prüfe vor dem Weiterarbeiten, dass Regeln 1–6 und alle übrigen Absätze
**wortgleich** zur Datei `interview_theater/sprachen/en/prompts/schaerfung.md`
sind. Geändert sind nur Regel 2 (der Halbsatz „name all of them, not just the
three strongest" fällt weg), der Satz „**What you deliver** …" und die neuen
Regeln 7–8. Abgleich:

Run: `git diff --no-index interview_theater/sprachen/en/prompts/schaerfung.md docs/messung/zitatauswahl/prompt-I-a.md`
Expected: nur diese drei Stellen.

- [ ] **Step 2: Commit (Kandidat, Betrieb unverändert)**

```bash
git add docs/messung/zitatauswahl/prompt-I-a.md
git commit -m "messung: Kandidat-Prompt I-a (Reihenfolge nach Buehnenwirkung, Staerke 3 knapp) (t_2f905d2c)"
```

- [ ] **Step 3: I-a, drei Läufe × drei Gruppen**

```
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante I-a --lauf 1 --gruppe G1 --prompt docs/messung/zitatauswahl/prompt-I-a.md
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante I-a --lauf 1 --gruppe G2 --prompt docs/messung/zitatauswahl/prompt-I-a.md
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante I-a --lauf 1 --gruppe G3 --prompt docs/messung/zitatauswahl/prompt-I-a.md
```
und dasselbe für `--lauf 2`, `--lauf 3` (Timeout 900000; Fehlerbehandlung
wie in Task 5 Step 7).

- [ ] **Step 4: Bericht und Entscheidung**

Run: `uv run --extra dev python -m scripts.zitatauswahl bericht`
Expected: Abschnitt „Entscheidungen (E7)" mit `- I-a gegen B1: **uebernommen** …`
oder `**nicht uebernommen** -- <Gründe>`.

- [ ] **Step 5: Commit (Daten + Bericht)**

```bash
git add docs/messung/zitatauswahl/I-a.jsonl docs/messung/2026-10-zitatauswahl.md
git commit -m "messung: Intervention I-a gemessen, Entscheidung nach E7 (t_2f905d2c)"
```

- [ ] **Step 6: Nur wenn „uebernommen": Prompt in den Betrieb**

Den Inhalt von `docs/messung/zitatauswahl/prompt-I-a.md` 1:1 nach
`interview_theater/sprachen/en/prompts/schaerfung.md` übernehmen. Der
DE-Prompt `interview_theater/prompts/schaerfung.md` bleibt unverändert
(Dortmund eingefroren).

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_schaerfung.py tests/test_sprache_prompts.py tests/test_prompt_audit.py tests/test_sprache_bitgleich.py tests/test_erzeuge_prompts_padua_voll.py tests/test_szene_verdichtet_prompt.py`
Expected: grün. Falls ein Padua-Prompt-Schnappschuss rot wird: die
Fehlermeldung nennt das Erzeugerskript. Nur den **Padua**-Schnappschuss neu
erzeugen, keine Dortmund-/Vorgabe-Fixture. Ein Test, der nur wegen
Dortmund rot wird, bekommt `@pytest.mark.dortmund`. Bekommt ein Test eine
Parität DE↔EN vorgeschrieben (Regelanzahl), die Regeln 7–8 in seinem
Erwartungswert für EN zulassen, nicht im DE-Prompt nachziehen.

Hinweis Betrieb: Prompts werden heiß nachgeladen (mtime). Nach dem Merge
gilt der neue Prompt ohne Neustart für die nächste Schärfungsrunde der
Padua-Bots. Das ist der beabsichtigte Fix; der Agent startet nichts neu.

```bash
git add interview_theater/sprachen/en/prompts/schaerfung.md
git commit -m "fix(schaerfung): EN-Prompt ordnet nach Buehnenwirkung, Staerke 3 knapp -- Recall@10 gestiegen (t_2f905d2c)"
```

(Schnappschuss-Dateien, falls neu erzeugt, mit in denselben Commit.)

---

### Task 8: Intervention I-b (Hypothese b: Frage-Kontext) — NUR nach Birks Freigabe

**Gate (Spec E8, Datenschutz):** I-b schickt Transkripttext außerhalb des
Belegzitats an Opus (USA), und Interviewfragen enthalten Vornamen
(Aufnahme 139). Prüfe in den Kommentaren der Karte `t_2f905d2c` (bzw.
`t_2349e9a8`), ob Birk diesen Datenfluss **schriftlich** freigegeben hat.

- [ ] **Step 1: Gate prüfen**

Ohne Freigabe: Task 8 überspringen und im Bericht nichts messen (der Bericht
zeigt dann `- I-b: nicht gemessen (keine vollstaendigen Laeufe).`). Unter
„Grenzen" diesen Satz von Hand ergänzen, und zwar in der Konstante
`GRENZEN` in `scripts/zitatauswahl.py`, damit er beim nächsten `bericht`
bleibt:
`- I-b (Frage-Kontext) nicht gemessen: Datenschutz-Gate (Spec E8), keine Freigabe durch Birk.`
Commit (`fix(messung): I-b gesperrt vermerkt (t_2f905d2c)`), dann weiter mit
Task 9. Die Steps 2–7 gelten nur mit Freigabe.

**Files (nur mit Freigabe):**
- Modify: `interview_theater/zitat.py` (`frage_vor`)
- Modify: `scripts/zitatauswahl.py` (`eintraege_mit_frage` ersetzt die Sperre aus Task 5)
- Test: `tests/test_zitatauswahl.py`

**Interfaces:**
- Produces: `zitat.frage_vor(transkript: str, beleg: str, fenster: int = 400) -> str | None`.
  Liefert den letzten Satz mit `?`, der höchstens `fenster` Zeichen vor dem
  Belegzitat endet, normalisiert und höchstens 300 Zeichen lang; sonst `None`.
  `scripts.zitatauswahl.eintraege_mit_frage(conn, chat_id) -> list[dict]`: wie
  `schaerfung._eintraege`, nur mit `thema = "<frage> — <thema>"`, wo eine Frage
  gefunden wird.

- [ ] **Step 2: Failing tests**

```python
# --- I-b: Frage-Kontext (nur nach Freigabe) -----------------------------------

from interview_theater import zitat  # noqa: E402


def test_frage_vor_findet_die_letzte_frage_vor_dem_zitat():
    t = "Hallo. Wie war die Arbeit? Also ich habe zwanzig Jahre genaeht."
    assert zitat.frage_vor(t, "ich habe zwanzig Jahre genaeht") == "Wie war die Arbeit?"


def test_frage_vor_ohne_frage_oder_zu_weit_weg_ist_none():
    assert zitat.frage_vor("Nur Aussagen. Ich habe genaeht.", "Ich habe genaeht") is None
    weit = "Wie war es? " + "x " * 300 + "Ich habe genaeht."
    assert zitat.frage_vor(weit, "Ich habe genaeht") is None


def test_eintraege_mit_frage_setzen_die_frage_vor_das_thema(lage):
    eintraege = za.eintraege_mit_frage(lage, 1)
    arbeit = next(e for e in eintraege if e["zitat"] == ZITAT_A)
    assert arbeit["thema"] == "Wie war die Arbeit? — Arbeit"
    assert [e["nummer"] for e in eintraege] == [e["nummer"] for e in schaerfung._eintraege(lage, 1)]
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`
Expected: FAIL `AttributeError: module 'interview_theater.zitat' has no attribute 'frage_vor'`.

- [ ] **Step 4: Implementieren**

An `interview_theater/zitat.py` anhängen:

```python
def frage_vor(transkript: str, beleg: str, fenster: int = 400) -> str | None:
    """Die Interviewfrage vor einem Belegzitat: der letzte Satz mit ``?``,
    der hoechstens ``fenster`` Zeichen vor dem Zitat endet (Karte
    t_2f905d2c, Hypothese b). Deterministisch, kein Modell. ``None``, wenn
    das Zitat nicht im Transkript steht oder keine Frage nahe davor."""
    t = normalisiere(transkript)
    z = normalisiere(beleg).strip('"\'')
    stelle = t.find(z) if z else -1
    if stelle < 0:
        return None
    vor = t[:stelle]
    ende = vor.rfind("?")
    if ende < 0 or stelle - ende > fenster:
        return None
    anfang = max(vor.rfind(".", 0, ende), vor.rfind("!", 0, ende), vor.rfind("?", 0, ende)) + 1
    frage = vor[anfang:ende + 1].strip()
    if len(frage.split()) < 3:
        return None
    return frage[-300:]
```

In `scripts/zitatauswahl.py` die Sperre `eintraege_mit_frage` ersetzen durch:

```python
def eintraege_mit_frage(conn, chat_id: int) -> list[dict]:
    """I-b (Spec E8, nach Birks Freigabe): die Materialliste der Schaerfung,
    das Thema mit der Interviewfrage davor -- gleiche Nummern, gleiche
    Reihenfolge, gleiche T-Zeilen (kein neuer Text)."""
    from interview_theater import schaerfung

    aus = []
    for eintrag in schaerfung._eintraege(conn, chat_id):
        frage = zitat.frage_vor(_transkript(conn, eintrag["aufnahme_id"]), eintrag["zitat"])
        if frage:
            eintrag = dict(eintrag, thema=f"{frage} — {eintrag['thema']}")
        aus.append(eintrag)
    return aus
```

- [ ] **Step 5: Run, expect PASS; Commit**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py`

```bash
git add interview_theater/zitat.py scripts/zitatauswahl.py tests/test_zitatauswahl.py
git commit -m "feat(messung): I-b Frage-Kontext vor dem Belegzitat, nach Datenschutz-Freigabe (t_2f905d2c)"
```

- [ ] **Step 6: I-b messen**

Prompt: wurde I-a übernommen, gilt der Betriebsprompt (ohne `--prompt`),
sonst ebenfalls der Betriebsprompt (= B1). Je Gruppe und Lauf 1–3:

```
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante I-b --lauf 1 --gruppe G1 --mit-frage
```
(G2, G3, Läufe 2 und 3 analog; Timeout 900000.) Dann
`uv run --extra dev python -m scripts.zitatauswahl bericht` und:

```bash
git add docs/messung/zitatauswahl/I-b.jsonl docs/messung/2026-10-zitatauswahl.md
git commit -m "messung: Intervention I-b gemessen, Entscheidung nach E7 (t_2f905d2c)"
```

- [ ] **Step 7: Nur wenn I-b „uebernommen": in den Betrieb**

In `interview_theater/schaerfung.py`, `_eintraege`: nach dem Aufbau jedes
Eintrags die Frage voranstellen (gleiche Form wie `eintraege_mit_frage`):

```python
        eintrag = {
            "nummer": nummer,
            "thema_id": zeile["id"],
            "aufnahme_id": zeile["aufnahme_id"],
            "interview": kontext.interviewbezeichnung(
                conn, chat_id, zeile["aufnahme_id"]
            ) or f"Interview {zeile['aufnahme_id']}",
            "thema": zeile["thema"] or "",
            "zusammenfassung": zeile["zusammenfassung"] or "",
            "zitat": zeile["beleg_zitat"] or "",
        }
        # Karte t_2f905d2c (I-b, gemessen, Datenschutz freigegeben): die
        # Interviewfrage vor dem Beleg gibt dem Ziel-Aufruf den Kontext.
        aufnahme = repo.hole_aufnahme(conn, zeile["aufnahme_id"])
        frage = zitat.frage_vor(
            (aufnahme["transkript"] if aufnahme else "") or "", eintrag["zitat"])
        if frage:
            eintrag["thema"] = f"{frage} — {eintrag['thema']}"
        eintraege.append(eintrag)
```

(ersetzt das bisherige `eintraege.append({...})`). Kein Profilschalter (AGENTS.md:
Padua-Verhalten direkt). Dann:

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_schaerfung.py tests/test_zitatauswahl.py tests/test_kernzitate.py tests/test_prompt_audit.py tests/test_erzeuge_prompts_padua_voll.py`
Expected: grün. Ein Test, der nur wegen Dortmund rot wird, bekommt
`@pytest.mark.dortmund`. Padua-Schnappschüsse wie in Task 7 Step 6 behandeln.

```bash
git add interview_theater/schaerfung.py
git commit -m "fix(schaerfung): Interviewfrage vor dem Belegzitat im Material -- Recall@10 gestiegen (t_2f905d2c)"
```

---

### Task 9: Doku, Abschlussprüfung

**Files:**
- Modify: `docs/agents/korpus-und-simulation.md`
- Modify (erzeugt): `docs/messung/2026-10-zitatauswahl.md` (letzter `bericht`-Lauf)

- [ ] **Step 1: Verweis in die Agenten-Doku**

An `docs/agents/korpus-und-simulation.md` anhängen (nicht an AGENTS.md):

```markdown
## Gold-Korpus Zitatauswahl (Padua, t_2f905d2c)

`korpus/zitatauswahl_gold.jsonl` -- die 16 Stellen der drei Padua-
Gruppenplakate (positiv) und die mit `nein` verworfenen Zuordnungen der
Schaerfung (negativ, nur Kennungen). Quelle: `korpus/zitatauswahl_quelle.toml`.
Format, Recall@10-Definition (je Ziel) und Ergebnisse:
`docs/messung/2026-10-zitatauswahl.md`. Skript: `python -m scripts.zitatauswahl`
(`gold`, `pruefe`, `historisch`, `neu`, `bericht`). `neu` ruft Opus ueber den
Proxy (0 CHF) und laeuft nie automatisch; Messung immer auf einer Kopie
(`kopie`), nie auf `betrieb/padua.db`.
```

- [ ] **Step 2: Bericht final erzeugen und Gold prüfen**

Run: `uv run --extra dev python -m scripts.zitatauswahl pruefe --db var/zitatauswahl/padua-kopie.db`
Expected: `Gold-Korpus gueltig`.
Run: `uv run --extra dev python -m scripts.zitatauswahl bericht`
Expected: Bericht ohne Änderung gegenüber dem letzten Commit, oder nur mit der Gate-Zeile.

- [ ] **Step 3: Doku-Tests und gezielte Tests**

Run: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py tests/test_schaerfung.py tests/test_agents_md_groesse.py tests/test_doku_laengen.py`
Expected: grün.

- [ ] **Step 4: Commit**

```bash
git add docs/agents/korpus-und-simulation.md docs/messung/2026-10-zitatauswahl.md
git commit -m "docs: Gold-Korpus Zitatauswahl und Messskript in der Agenten-Doku (t_2f905d2c)"
```

- [ ] **Step 5: Volle Suite (einmal)**

Run (Timeout 900000): `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2`
Expected: grün. Rot → `superpowers:systematic-debugging`, nicht raten.
(Fährt der Lauf-Rahmen die Suite selbst, entfällt dieser Schritt.)

- [ ] **Step 6: Abschluss-Check gegen die Karte**

- `git status --short var/` zeigt nichts Eingechecktes; `git log --oneline --grep=t_2f905d2c` listet die Commits.
- Kein Diff an `interview_theater/verdichter.py`, `erkenner.py`, `aufnahme.py`, `kernzitate.py`, `interview_theater/prompts/schaerfung.md`:
  Run: `git diff --stat main -- interview_theater/verdichter.py interview_theater/erkenner.py interview_theater/aufnahme.py interview_theater/kernzitate.py interview_theater/prompts/schaerfung.md`
  Expected: leer.

---

## Abdeckung der Karte

| Anforderung | Wo |
|---|---|
| Bericht mit Baseline/Nachher je Gruppe, Kommandos | Task 6 (`schreibe_bericht`), 7, 8, 9 |
| Fix nur bei messbarem Anstieg | Spec E7 → `entscheide` (Task 4), Übernahme nur in Task 7 Step 6 / Task 8 Step 7 |
| Mutationstest: Gold verfälscht → Lauf rot | Task 3 (`test_mutation_*`, `pruefe` Exit 1), Task 4 (`test_mutation_verfaelschter_gold_korpus_senkt_recall_sichtbar`) |
| Gold-Korpus für Messung 2 wiederverwendbar | Task 3 (Datei), Task 6 (`### Format`, `trifft`), Commits mit `t_2f905d2c` |
| Volle Suite grün | Task 9 Step 5 |
| Kein Bot-Neustart | Global Constraints; nichts startet Dienste |
| Interviews hart auf Kimi | Task 5 `test_skript_importiert_keine_interviewstrecke`, `ohne_kimi`; Task 9 Step 6 |
| Interventionen einzeln messen | Task 7 (I-a) vor Task 8 (I-b), je eigene Läufe |
| Datenschutz | Spec § 7; Negative ohne Text (Task 3), Gate I-b (Task 8) |
