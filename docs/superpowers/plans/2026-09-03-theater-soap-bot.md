# Theater-Soap-Bot — Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Telegram-Bot, der eine Kleingruppe durch die Entwicklung eines Theaterstücks aus eigenen Interviews begleitet — ein Prozess pro Gruppe, gemeinsame SQLite, Infomaniak für Sprache und Sprachmodell.

**Architecture:** Ein einzelner synchroner Polling-Prozess je Gruppe. Der Zustand liegt vollständig in SQLite und wird nie im Speicher gehalten; der Prompt ist eine Funktion der Datenbank. Nebenarbeiten (Tippanzeige, Extraktor, Interview-Pipeline) laufen in einem kleinen Thread-Pool und dürfen fehlschlagen, ohne den Gesprächsweg zu blockieren.

**Tech Stack:** Python 3.11 · `httpx` (Telegram- und Infomaniak-HTTP) · `sqlite3` aus der Standardbibliothek · `pytest` + `httpx.MockTransport` für Tests. **Keine weiteren Abhängigkeiten** — kein Telegram-Framework, kein ORM, kein Async-Stack. Zwei Tage vor dem Workshop ist jede Abhängigkeit, deren Verhalten wir nicht kennen, ein Risiko ohne Gegenwert.

**Grundlage:** `SPEC-kontext-architektur.md` im Repo-Wurzelverzeichnis. Paragraphenverweise (§) beziehen sich darauf.

**Nicht Teil dieses Plans:** das Dashboard. Es liest dieselbe SQLite und wird getrennt gebaut. Dieser Plan schreibt die Tabellen `vorfall` und `aufruf` so, dass das Dashboard sie ohne weitere Vorbereitung lesen kann.

---

## Global Constraints

Diese Werte gelten für **jede** Aufgabe. Sie sind aus der Spec wörtlich übernommen; keine Aufgabe darf sie eigenmächtig ändern.

**Sprache und Stil**
- Python 3.11. Bezeichner, Tabellen- und Spaltennamen **auf Deutsch** (wie im Spec-Schema). Kommentare und Commit-Nachrichten auf Deutsch, Commit-Nachrichten ohne Umlaute.
- Jede Datei hat eine Zuständigkeit. Keine Datei über ~200 Zeilen ohne guten Grund.

**Datenbank (§ 3)**
- Bei **jedem** Verbindungsaufbau: `PRAGMA journal_mode = WAL`, `PRAGMA busy_timeout = 5000`, `PRAGMA synchronous = NORMAL`.
- **Jede Tabelle außer `bot_zustand` hat eine Spalte `chat_id`.** Das ist keine Konvention, sondern die Grundlage der Löschzusage (§ 9.3) und wird durch einen Test erzwungen.
- Primärschlüssel `(chat_id, message_id)` auf `nachricht`, Einfügen immer mit `INSERT OR IGNORE` (§ 9.2).

**Sprachmodell (§ 4, § 11.3)**
- Vorgabe ist **Modus A**: erzwungenes JSON-Schema, `reasoning_effort: "none"`.
- **`max_tokens` ≥ 9000 bei jedem Aufruf**, zwingend bei jedem Aufruf mit Reasoning.
- `finish_reason` bei jedem Aufruf prüfen und speichern. `"length"` ist ein Vorfall `abgeschnitten`, kein leeres Ergebnis zum Durchreichen.
- Defensives Parsen bei allen Schema-Aufrufen: führendes `{{` auf `{` normalisieren, bei `content: null` auf `message.reasoning` ausweichen.
- Wiederholung bei 5xx und Timeout: Wartezeiten `(0.7, 1.5, 3.0)` Sekunden mit Jitter, also bis zu vier Versuche insgesamt.
- **Kein Prompt-Caching als Annahme** (§ 6.1) — `usage.prompt_tokens_details` ist bei Infomaniak `null`. Nur mitloggen, nicht darauf bauen.

**Kontext (§ 6, § 7)**
- Token-Schätzung: **Zeichen ÷ 3**. Kein Tokenizer.
- Budgets je Block: Systemanweisung 900 · Verdichtungen 3000 · Volltranskripte 5000 · Arbeitsstand 1200 · aktuelle Szene 1500 · Journal 1500 · kurzes Fenster 2500 · auslösende Nachricht 300.
- Zielgröße 10 000 Token, Reißleine 20 000.
- Kürzungsleiter in genau dieser Reihenfolge: Transkripte → Fenster auf 1500 → Belegzitate → Journal nach Rang → Notbremse.
- Pausenmarkierung im Fenster ab **60 Minuten** Abstand.

**Belegzitate (§ 5)**
- Mindestlänge Segment **15 Zeichen**, Höchstabstand zwischen `[...]`-Segmenten **600 Zeichen**, Segmente müssen in Reihenfolge vorkommen.
- Bei Fehlschlag: genau **ein** Retry, danach Vorschlag **ohne** Zitat ausliefern, nie den Vorschlag verwerfen. Vorfall `zitat_ungeprueft`.

**Zeitschwellen (§ 1.4, § 9.1)**
- Rückfrage-Sequenz verfällt nach **10 Minuten**, wird nie wiederholt.
- Nachtstau: alles älter als **15 Minuten** bekommt `unterdrueckt = 1`.
- Begrüßung beim Start nur bei über **2 Stunden** Pause.
- Extraktor-Zusatzauslöser bei **1500** Token, Deckel bei **4000** Token.

**Fehlerhaltung (§ 0 Leitsatz 5, § 11)**
- Die Gruppe erfährt von einem Fehler nur, wenn sie ihn beheben kann oder wenn sie gerade darauf wartet. Alles andere geht als `vorfall` ans Dashboard.
- Jedes Update in `try/except`. Eine Ausnahme darf den Prozess niemals beenden.

**Konfiguration** — ausschließlich Umgebungsvariablen, nie im Code, nie im Repo:

| Variable | Bedeutung |
|---|---|
| `TS_BOT_TOKEN` | Telegram-Token dieser Gruppe |
| `TS_BOT_NAME` | Kurzname, z. B. `gruppe1` (Schlüssel in `bot_zustand`) |
| `TS_DB` | Pfad zur gemeinsamen SQLite |
| `TS_AUDIO` | Verzeichnis für heruntergeladene Sprachnachrichten |
| `TS_LLM_URL` | OpenAI-kompatibler Endpunkt bei Infomaniak |
| `TS_LLM_KEY` | API-Schlüssel |
| `TS_LLM_MODELL` | Modellkennung Kimi K2.6 |
| `TS_STT_URL` | Whisper-V3-Endpunkt |

---

## Dateistruktur

```
theatersoap/
  __init__.py
  einstellungen.py   Umgebungsvariablen einlesen, ein Objekt, keine Logik
  db.py              Verbindung, PRAGMAs, Schema, Löschweg
  repo.py            alle SQL-Abfragen; einzige Stelle mit SQL außer db.py
  telegram.py        dünner HTTP-Wrapper um die Telegram-Bot-API
  llm.py             Infomaniak-Chat: Modus A/B, Wiederholung, defensives Parsen
  stt.py             Whisper V3
  zitat.py           Belegzitat-Verifikation (§ 5), reine Funktionen
  kontext.py         Prompt-Zusammenbau, Token-Schätzung, Kürzungsleiter
  verdichter.py      Verdichter-Prompt und Interview-Pipeline
  extraktor.py       Extraktor-Prompt, Wasserzeichen, Journal
  befehle.py         alle Slash-Befehle
  ablauf.py          ein Gesprächszug: Auslöser, Sperre, Sammeln, Antwort
  bot.py             Einstiegspunkt: Startroutine und Polling-Schleife
  prompts/
    system.md        Systemanweisung (§ 6.3)
    verdichter.md
    extraktor.md
scripts/
  loeschen.py        Gruppe vollständig löschen (§ 9.3)
  rauchtest.py       ein echter Aufruf gegen Infomaniak und Whisper
tests/
  ...                je Modul eine Datei
```

**Warum diese Schnitte.** `repo.py` ist die einzige Stelle mit SQL — dadurch ist die Löschzusage an einem Ort prüfbar. `zitat.py` enthält nur reine Funktionen und ist damit ohne Netz und ohne Datenbank testbar, was wichtig ist, weil es die Prüfung ist, auf der Modus A ruht. `ablauf.py` und `bot.py` sind getrennt, damit ein Gesprächszug ohne laufende Polling-Schleife testbar ist.

---

## Aufgabe 0: Vorlagen lesen (Voraussetzung für Aufgabe 5 und 6)

**Nicht überspringen.** Die Infomaniak-Anbindung existiert bereits erprobt; sie nachzubauen statt abzuschreiben ist zwei Tage vor dem Workshop die teuerste denkbare Entscheidung.

**Dateien (nur lesen):**
- `/home/birk/projekte/kollektivgedaechtnis/kg/llm.py`
- `/home/birk/projekte/kollektivgedaechtnis/stt_backends/infomaniak_whisper_backend.py`

> **Zugriff:** Dieses Verzeichnis ist derzeit nicht als Arbeitsverzeichnis freigegeben. Vor Beginn freigeben, sonst kann diese Aufgabe nicht erfüllt werden.

- [ ] **Schritt 1: Beide Dateien lesen** und in `docs/vorlagen-notiz.md` festhalten: exakte URL-Pfade, Header-Namen, Aufbau des Anfragekörpers, wie `response_format` gesetzt wird, wie die Audiodatei an Whisper übergeben wird (Feldname, MIME-Typ), welche Ausnahmen behandelt werden.

- [ ] **Schritt 2: Abweichungen notieren.** Alles, was der Plan in Aufgabe 5/6 anders vorsieht als die Vorlage, wird in derselben Datei mit Begründung vermerkt. Im Zweifel gilt die Vorlage — sie lief schon.

**Fertigstellungsbedingung:** `docs/vorlagen-notiz.md` existiert und nennt für beide Dienste den vollständigen Anfrageaufbau (URL, Header, Körper) so konkret, dass Aufgabe 5 und 6 ohne erneutes Nachschlagen umgesetzt werden können.

- [ ] **Schritt 3: Commit**

```bash
git add docs/vorlagen-notiz.md
git commit -m "Notiz zu den Infomaniak-Vorlagen aus kollektivgedaechtnis"
```

---

## TEIL A — Durchstich

Ziel von Teil A: Nachricht rein, Sprachnachricht transkribiert, Verdichtung, Antwort raus, Zustand überlebt Neustart. Nach Aufgabe 10 läuft der Bot. Alles danach ist Ausbau.

---

## Aufgabe 1: Projektgerüst, Einstellungen, Datenbank

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `theatersoap/__init__.py`, `theatersoap/einstellungen.py`, `theatersoap/db.py`, `scripts/loeschen.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `einstellungen.laden() -> Einstellungen` (Attribute: `bot_token`, `bot_name`, `db_pfad`, `audio_verz`, `llm_url`, `llm_key`, `llm_modell`, `stt_url`)
- Produces: `db.verbinde(pfad: str) -> sqlite3.Connection`, `db.initialisiere(conn) -> None`, `db.loesche_gruppe(conn, chat_id: int) -> None`, `db.TABELLEN_MIT_CHAT_ID: tuple[str, ...]`

- [ ] **Schritt 1: Gerüst anlegen**

`pyproject.toml`:

```toml
[project]
name = "theatersoap"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["httpx>=0.27"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`.gitignore`:

```
__pycache__/
*.pyc
.venv/
*.db
*.db-wal
*.db-shm
audio/
.env
```

`theatersoap/__init__.py`: leer.

- [ ] **Schritt 2: Einstellungen**

`theatersoap/einstellungen.py`:

```python
"""Umgebungsvariablen einlesen. Keine Logik, keine Vorgabewerte fuer Geheimnisse."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Einstellungen:
    bot_token: str
    bot_name: str
    db_pfad: str
    audio_verz: str
    llm_url: str
    llm_key: str
    llm_modell: str
    stt_url: str


def _pflicht(name: str) -> str:
    wert = os.environ.get(name)
    if not wert:
        raise RuntimeError(f"Umgebungsvariable {name} fehlt")
    return wert


def laden() -> Einstellungen:
    return Einstellungen(
        bot_token=_pflicht("TS_BOT_TOKEN"),
        bot_name=_pflicht("TS_BOT_NAME"),
        db_pfad=_pflicht("TS_DB"),
        audio_verz=os.environ.get("TS_AUDIO", "audio"),
        llm_url=_pflicht("TS_LLM_URL"),
        llm_key=_pflicht("TS_LLM_KEY"),
        llm_modell=_pflicht("TS_LLM_MODELL"),
        stt_url=_pflicht("TS_STT_URL"),
    )
```

- [ ] **Schritt 3: Den fehlschlagenden Test schreiben**

`tests/test_db.py`:

```python
import sqlite3
import pytest
from theatersoap import db


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "test.db"))
    db.initialisiere(c)
    return c


def test_pragmas_sind_gesetzt(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_jede_tabelle_ausser_bot_zustand_hat_chat_id(conn):
    """Grundlage der Loeschzusage: es darf keine Tabelle ohne chat_id geben."""
    tabellen = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    ]
    assert "gruppe" in tabellen, "Schema wurde nicht angelegt"
    for tabelle in tabellen:
        if tabelle == "bot_zustand":
            continue
        spalten = [r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")]
        assert "chat_id" in spalten, f"{tabelle} hat kein chat_id"


def test_loeschen_raeumt_alle_tabellen(conn):
    for tabelle in db.TABELLEN_MIT_CHAT_ID:
        spalten = [r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")]
        nicht_null = [
            r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")
            if r[3] == 1 and r[1] != "chat_id" and r[5] == 0
        ]
        werte = {"chat_id": 42}
        for s in nicht_null:
            werte[s] = "x"
        if "message_id" in spalten:
            werte["message_id"] = 1
        namen = ", ".join(werte)
        platzhalter = ", ".join("?" * len(werte))
        conn.execute(
            f"INSERT INTO {tabelle} ({namen}) VALUES ({platzhalter})",
            tuple(werte.values()),
        )
    conn.commit()

    db.loesche_gruppe(conn, 42)

    for tabelle in db.TABELLEN_MIT_CHAT_ID:
        anzahl = conn.execute(
            f"SELECT count(*) FROM {tabelle} WHERE chat_id = 42"
        ).fetchone()[0]
        assert anzahl == 0, f"{tabelle} nicht geleert"
```

- [ ] **Schritt 4: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.db'`

- [ ] **Schritt 5: `db.py` schreiben**

`theatersoap/db.py` — `SCHEMA` wörtlich aus `SPEC-kontext-architektur.md` § 3.1 übernehmen (alle zwölf `CREATE TABLE` und die `CREATE INDEX`), jeweils mit `IF NOT EXISTS`:

```python
"""Verbindung, PRAGMAs, Schema und Loeschweg. Einzige Stelle mit DDL."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS bot_zustand ( ... );
CREATE TABLE IF NOT EXISTS gruppe ( ... );
-- ... alle Tabellen aus SPEC § 3.1, unveraendert bis auf IF NOT EXISTS
"""

TABELLEN_MIT_CHAT_ID = (
    "gruppe", "nachricht", "interview", "verdichtung", "verdichtung_thema",
    "arbeitsstand", "figur", "szene", "journal", "vorfall", "aufruf",
)


def verbinde(pfad: str) -> sqlite3.Connection:
    conn = sqlite3.connect(pfad, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def initialisiere(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def loesche_gruppe(conn: sqlite3.Connection, chat_id: int) -> None:
    """Loescht restlos alles zu einer Gruppe. Audiodateien raeumt scripts/loeschen.py."""
    for tabelle in TABELLEN_MIT_CHAT_ID:
        conn.execute(f"DELETE FROM {tabelle} WHERE chat_id = ?", (chat_id,))
    conn.commit()
```

> **Achtung:** `vorfall.chat_id` ist in der Spec `NULL`-fähig (bot-weite Vorfälle). Die Tabelle bleibt trotzdem in `TABELLEN_MIT_CHAT_ID` — Vorfälle *mit* `chat_id` müssen mitgelöscht werden.

- [ ] **Schritt 6: Test laufen lassen**

Run: `python -m pytest tests/test_db.py -v`
Expected: PASS, 3 Tests

- [ ] **Schritt 7: Löschskript**

`scripts/loeschen.py`:

```python
"""Loescht eine Gruppe restlos. Kein Chatbefehl, bewusst nur von Hand (SPEC 9.3)."""
import shutil
import sys
from pathlib import Path

from theatersoap import db, einstellungen


def main() -> None:
    if len(sys.argv) != 2:
        print("Aufruf: python -m scripts.loeschen <chat_id>")
        raise SystemExit(2)
    chat_id = int(sys.argv[1])
    e = einstellungen.laden()
    antwort = input(f"Gruppe {chat_id} unwiderruflich loeschen? [ja/NEIN] ")
    if antwort.strip().lower() != "ja":
        print("Abgebrochen.")
        return
    conn = db.verbinde(e.db_pfad)
    db.loesche_gruppe(conn, chat_id)
    verzeichnis = Path(e.audio_verz) / str(chat_id)
    if verzeichnis.exists():
        shutil.rmtree(verzeichnis)
    print(f"Gruppe {chat_id} geloescht.")


if __name__ == "__main__":
    main()
```

**Fertigstellungsbedingung:** `python -m pytest tests/test_db.py -v` meldet 3 bestandene Tests, darunter der Test, der jede Tabelle auf `chat_id` prüft.

- [ ] **Schritt 8: Commit**

```bash
git add pyproject.toml .gitignore theatersoap/ scripts/ tests/
git commit -m "Projektgeruest, Einstellungen, Datenbankschema und Loeschweg"
```

---

## Aufgabe 2: Repository-Schicht

**Files:**
- Create: `theatersoap/repo.py`
- Test: `tests/test_repo.py`

**Interfaces:**
- Consumes: `db.verbinde`, `db.initialisiere`
- Produces:
  - `repo.merke_nachricht(conn, chat_id, message_id, absender, ist_bot, typ, text, gesendet_am, unterdrueckt=0) -> bool` (True = neu eingefügt)
  - `repo.sichere_gruppe(conn, chat_id, bot_name, titel) -> None`
  - `repo.hole_gruppe(conn, chat_id) -> sqlite3.Row | None`
  - `repo.unbeantwortete(conn, chat_id) -> list[sqlite3.Row]`
  - `repo.setze_beantwortet_bis(conn, chat_id, message_id) -> None`
  - `repo.letzte_nachrichten(conn, chat_id, anzahl=80) -> list[sqlite3.Row]` (aufsteigend nach `message_id`)
  - `repo.hole_update_id(conn, bot_name) -> int`
  - `repo.setze_update_id(conn, bot_name, update_id) -> None`
  - `repo.merke_vorfall(conn, chat_id, bot_name, art, detail, stufe=None) -> None`
  - `repo.merke_aufruf(conn, chat_id, art, modus, geschaetzt, tatsaechlich, antwort_token, finish_reason, dauer_ms, erfolg) -> None`

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_repo.py`:

```python
import pytest
from theatersoap import db, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def test_nachricht_wird_nicht_doppelt_eingefuegt(conn):
    neu1 = repo.merke_nachricht(conn, 1, 100, "Ada", 0, "text", "hallo", "2026-09-05T10:00:00")
    neu2 = repo.merke_nachricht(conn, 1, 100, "Ada", 0, "text", "hallo", "2026-09-05T10:00:00")
    assert neu1 is True
    assert neu2 is False
    anzahl = conn.execute("SELECT count(*) FROM nachricht").fetchone()[0]
    assert anzahl == 1


def test_unbeantwortete_beachtet_wasserzeichen_und_unterdrueckung(conn):
    repo.merke_nachricht(conn, 1, 10, "Ada", 0, "text", "alt", "2026-09-05T10:00:00")
    repo.merke_nachricht(conn, 1, 11, "Bo", 0, "text", "nacht", "2026-09-05T22:00:00",
                         unterdrueckt=1)
    repo.merke_nachricht(conn, 1, 12, "Cem", 0, "text", "neu", "2026-09-06T12:00:00")
    repo.setze_beantwortet_bis(conn, 1, 10)

    offen = repo.unbeantwortete(conn, 1)

    assert [r["message_id"] for r in offen] == [12]


def test_unbeantwortete_ignoriert_bot_nachrichten(conn):
    repo.merke_nachricht(conn, 1, 20, "Bot", 1, "text", "Antwort", "2026-09-05T10:00:00")
    assert repo.unbeantwortete(conn, 1) == []


def test_update_id_ueberlebt_neue_verbindung(conn, tmp_path):
    repo.setze_update_id(conn, "gruppe1", 4711)
    conn.close()
    conn2 = db.verbinde(str(tmp_path / "t.db"))
    assert repo.hole_update_id(conn2, "gruppe1") == 4711


def test_update_id_ist_null_wenn_unbekannt(conn):
    assert repo.hole_update_id(conn, "nochniegesehen") == 0
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_repo.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.repo'`

- [ ] **Schritt 3: `repo.py` schreiben**

```python
"""Alle SQL-Abfragen. Einzige Stelle mit SQL ausser db.py."""
import sqlite3
from datetime import datetime, timezone


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sichere_gruppe(conn, chat_id: int, bot_name: str, titel: str | None) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO gruppe (chat_id, bot_name, titel, erste_nachricht_am) "
        "VALUES (?, ?, ?, ?)",
        (chat_id, bot_name, titel, _jetzt()),
    )
    conn.commit()


def hole_gruppe(conn, chat_id: int):
    return conn.execute("SELECT * FROM gruppe WHERE chat_id = ?", (chat_id,)).fetchone()


def merke_nachricht(conn, chat_id, message_id, absender, ist_bot, typ, text,
                    gesendet_am, unterdrueckt: int = 0) -> bool:
    cur = conn.execute(
        "INSERT OR IGNORE INTO nachricht "
        "(chat_id, message_id, absender, ist_bot, typ, text, gesendet_am, unterdrueckt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (chat_id, message_id, absender, ist_bot, typ, text, gesendet_am, unterdrueckt),
    )
    conn.commit()
    return cur.rowcount == 1


def unbeantwortete(conn, chat_id: int) -> list:
    return list(conn.execute(
        "SELECT n.* FROM nachricht n JOIN gruppe g ON g.chat_id = n.chat_id "
        "WHERE n.chat_id = ? AND n.ist_bot = 0 AND n.unterdrueckt = 0 "
        "AND n.message_id > g.letzte_beantwortete_message_id "
        "ORDER BY n.message_id",
        (chat_id,),
    ))


def setze_beantwortet_bis(conn, chat_id: int, message_id: int) -> None:
    conn.execute(
        "UPDATE gruppe SET letzte_beantwortete_message_id = ? "
        "WHERE chat_id = ? AND letzte_beantwortete_message_id < ?",
        (message_id, chat_id, message_id),
    )
    conn.commit()


def letzte_nachrichten(conn, chat_id: int, anzahl: int = 80) -> list:
    zeilen = list(conn.execute(
        "SELECT * FROM nachricht WHERE chat_id = ? ORDER BY message_id DESC LIMIT ?",
        (chat_id, anzahl),
    ))
    return list(reversed(zeilen))


def hole_update_id(conn, bot_name: str) -> int:
    zeile = conn.execute(
        "SELECT letzte_update_id FROM bot_zustand WHERE bot_name = ?", (bot_name,)
    ).fetchone()
    return zeile["letzte_update_id"] if zeile and zeile["letzte_update_id"] else 0


def setze_update_id(conn, bot_name: str, update_id: int) -> None:
    conn.execute(
        "INSERT INTO bot_zustand (bot_name, letzte_update_id, gestartet_am, "
        "letzte_aktivitaet_am) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(bot_name) DO UPDATE SET letzte_update_id = excluded.letzte_update_id, "
        "letzte_aktivitaet_am = excluded.letzte_aktivitaet_am",
        (bot_name, update_id, _jetzt(), _jetzt()),
    )
    conn.commit()


def merke_vorfall(conn, chat_id, bot_name, art, detail, stufe=None) -> None:
    conn.execute(
        "INSERT INTO vorfall (chat_id, bot_name, art, stufe, detail, erstellt_am) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, bot_name, art, stufe, detail, _jetzt()),
    )
    conn.commit()


def merke_aufruf(conn, chat_id, art, modus, geschaetzt, tatsaechlich, antwort_token,
                 finish_reason, dauer_ms, erfolg) -> None:
    conn.execute(
        "INSERT INTO aufruf (chat_id, art, modus, geschaetzte_token, tatsaechliche_token, "
        "antwort_token, finish_reason, dauer_ms, erfolg, erstellt_am) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (chat_id, art, modus, geschaetzt, tatsaechlich, antwort_token, finish_reason,
         dauer_ms, erfolg, _jetzt()),
    )
    conn.commit()
```

- [ ] **Schritt 4: Test laufen lassen**

Run: `python -m pytest tests/test_repo.py -v`
Expected: PASS, 5 Tests

**Fertigstellungsbedingung:** Alle fünf Tests bestehen; insbesondere belegt `test_unbeantwortete_beachtet_wasserzeichen_und_unterdrueckung`, dass unterdrückte Nachtnachrichten keinen Zug auslösen (§ 9.1).

- [ ] **Schritt 5: Commit**

```bash
git add theatersoap/repo.py tests/test_repo.py
git commit -m "Repository-Schicht mit Wasserzeichen und Update-Position"
```

---

## Aufgabe 3: Telegram-Wrapper

**Files:**
- Create: `theatersoap/telegram.py`
- Test: `tests/test_telegram.py`

**Interfaces:**
- Produces: `telegram.Telegram(token: str, klient: httpx.Client)` mit
  - `.hole_updates(offset: int, timeout: int = 25) -> list[dict]`
  - `.sende(chat_id: int, text: str) -> int` (liefert `message_id`)
  - `.tippt(chat_id: int) -> None`
  - `.lade_datei(file_id: str, ziel: pathlib.Path) -> None`
- Produces: `telegram.lies_nachricht(update: dict) -> dict | None` — normalisiert ein Update zu
  `{"chat_id", "message_id", "absender", "typ", "text", "gesendet_am", "file_id", "chat_titel"}`.
  `typ` ist einer von `text|sprache|foto|sticker|sonstiges`. `None` bei Updates ohne Nachricht.

Warum ein eigener Wrapper statt eines Frameworks: Wir müssen die Update-Position selbst persistieren (§ 9.1) und den Nachtstau selbst unterdrücken. Ein Framework, das den Offset intern verwaltet, müsste dafür überredet werden. Der Wrapper ist rund 80 Zeilen und hat kein Eigenleben.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_telegram.py`:

```python
import httpx
import pytest
from theatersoap import telegram


def klient_mit(antworten: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        for teil, nutzlast in antworten.items():
            if teil in request.url.path:
                return httpx.Response(200, json=nutzlast)
        return httpx.Response(404, json={"ok": False})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_hole_updates_liefert_ergebnisliste():
    tg = telegram.Telegram("TOKEN", klient_mit(
        {"getUpdates": {"ok": True, "result": [{"update_id": 7}]}}
    ))
    assert tg.hole_updates(offset=0) == [{"update_id": 7}]


def test_sende_liefert_message_id():
    tg = telegram.Telegram("TOKEN", klient_mit(
        {"sendMessage": {"ok": True, "result": {"message_id": 55}}}
    ))
    assert tg.sende(1, "hallo") == 55


def test_lies_nachricht_erkennt_sprachnachricht():
    update = {
        "update_id": 1,
        "message": {
            "message_id": 9,
            "date": 1788600000,
            "chat": {"id": -100, "title": "Gruppe 1"},
            "from": {"first_name": "Ada"},
            "voice": {"file_id": "AwACabc", "duration": 312},
        },
    }
    n = telegram.lies_nachricht(update)
    assert n["typ"] == "sprache"
    assert n["file_id"] == "AwACabc"
    assert n["chat_id"] == -100
    assert n["absender"] == "Ada"
    assert n["gesendet_am"].startswith("2026-")


def test_lies_nachricht_erkennt_text():
    update = {
        "update_id": 2,
        "message": {
            "message_id": 10,
            "date": 1788600000,
            "chat": {"id": -100, "title": "Gruppe 1"},
            "from": {"first_name": "Bo"},
            "text": "Heimat, Bruch, Ankommen",
        },
    }
    n = telegram.lies_nachricht(update)
    assert n["typ"] == "text"
    assert n["text"] == "Heimat, Bruch, Ankommen"
    assert n["file_id"] is None


def test_lies_nachricht_gibt_none_ohne_nachricht():
    assert telegram.lies_nachricht({"update_id": 3, "poll": {}}) is None


def test_lies_nachricht_kennzeichnet_sticker_als_sonstiges():
    update = {
        "update_id": 4,
        "message": {
            "message_id": 11,
            "date": 1788600000,
            "chat": {"id": -100},
            "from": {"first_name": "Cem"},
            "sticker": {"file_id": "S1"},
        },
    }
    assert telegram.lies_nachricht(update)["typ"] == "sticker"
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_telegram.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.telegram'`

- [ ] **Schritt 3: `telegram.py` schreiben**

```python
"""Duenner Wrapper um die Telegram-Bot-API. Kein Zustand, kein Eigenleben."""
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASIS = "https://api.telegram.org"


class TelegramFehler(RuntimeError):
    pass


class Telegram:
    def __init__(self, token: str, klient: httpx.Client):
        self._token = token
        self._klient = klient

    def _ruf(self, methode: str, **daten):
        antwort = self._klient.post(
            f"{BASIS}/bot{self._token}/{methode}", json=daten, timeout=40.0
        )
        antwort.raise_for_status()
        koerper = antwort.json()
        if not koerper.get("ok"):
            raise TelegramFehler(f"{methode}: {koerper}")
        return koerper["result"]

    def hole_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        return self._ruf("getUpdates", offset=offset, timeout=timeout)

    def sende(self, chat_id: int, text: str) -> int:
        return self._ruf("sendMessage", chat_id=chat_id, text=text)["message_id"]

    def tippt(self, chat_id: int) -> None:
        self._ruf("sendChatAction", chat_id=chat_id, action="typing")

    def lade_datei(self, file_id: str, ziel: Path) -> None:
        pfad = self._ruf("getFile", file_id=file_id)["file_path"]
        with self._klient.stream(
            "GET", f"{BASIS}/file/bot{self._token}/{pfad}", timeout=120.0
        ) as strom:
            strom.raise_for_status()
            ziel.parent.mkdir(parents=True, exist_ok=True)
            with open(ziel, "wb") as datei:
                for brocken in strom.iter_bytes():
                    datei.write(brocken)


def lies_nachricht(update: dict) -> dict | None:
    """Normalisiert ein Update. Unbekannte Typen werden mitgeschrieben, nie verworfen."""
    nachricht = update.get("message") or update.get("edited_message")
    if not nachricht:
        return None

    if "voice" in nachricht:
        typ, file_id = "sprache", nachricht["voice"]["file_id"]
    elif "audio" in nachricht:
        typ, file_id = "sprache", nachricht["audio"]["file_id"]
    elif "text" in nachricht:
        typ, file_id = "text", None
    elif "photo" in nachricht:
        typ, file_id = "foto", None
    elif "sticker" in nachricht:
        typ, file_id = "sticker", None
    else:
        typ, file_id = "sonstiges", None

    chat = nachricht.get("chat", {})
    absender = (nachricht.get("from") or {}).get("first_name") or "unbekannt"
    return {
        "chat_id": chat.get("id"),
        "chat_titel": chat.get("title"),
        "message_id": nachricht["message_id"],
        "absender": absender,
        "typ": typ,
        "text": nachricht.get("text") or nachricht.get("caption"),
        "file_id": file_id,
        "gesendet_am": datetime.fromtimestamp(
            nachricht["date"], tz=timezone.utc
        ).isoformat(timespec="seconds"),
    }
```

- [ ] **Schritt 4: Test laufen lassen**

Run: `python -m pytest tests/test_telegram.py -v`
Expected: PASS, 6 Tests

**Fertigstellungsbedingung:** Alle sechs Tests bestehen, ohne dass ein Netzzugriff stattfindet (nur `httpx.MockTransport`).

- [ ] **Schritt 5: Commit**

```bash
git add theatersoap/telegram.py tests/test_telegram.py
git commit -m "Telegram-Wrapper mit Normalisierung aller Nachrichtentypen"
```

---

## Aufgabe 4: Polling-Schleife, Update-Position, Nachtstau

Ab hier läuft der Bot zum ersten Mal — er hört zu und schreibt mit, antwortet aber noch nicht.

**Files:**
- Create: `theatersoap/bot.py`
- Test: `tests/test_bot.py`

**Interfaces:**
- Consumes: `telegram.Telegram`, `repo.*`, `db.*`, `einstellungen.Einstellungen`
- Produces:
  - `bot.verarbeite_update(conn, tg, e, update, jetzt: datetime, beim_start: bool) -> int | None` — schreibt die Nachricht weg, liefert die `chat_id`, wenn ein Zug ausgelöst werden soll, sonst `None`
  - `bot.ist_nachtstau(gesendet_am: str, jetzt: datetime) -> bool`
  - `bot.schleife(conn, tg, e) -> None`

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_bot.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest
from theatersoap import bot, db, repo

JETZT = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


def bau_update(update_id, message_id, text, wann: datetime):
    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "date": int(wann.timestamp()),
            "chat": {"id": -100, "title": "Gruppe 1"},
            "from": {"first_name": "Ada"},
            "text": text,
        },
    }


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    return c


def test_alte_nachricht_beim_start_wird_unterdrueckt(conn, einst, tg_attrappe):
    alt = JETZT - timedelta(hours=14)
    ausloeser = bot.verarbeite_update(
        conn, tg_attrappe, einst, bau_update(1, 10, "Idee fuer Maria", alt),
        jetzt=JETZT, beim_start=True,
    )
    zeile = conn.execute("SELECT * FROM nachricht WHERE message_id = 10").fetchone()
    assert zeile["text"] == "Idee fuer Maria", "Nachtnachricht muss gespeichert werden"
    assert zeile["unterdrueckt"] == 1
    assert ausloeser is None, "Nachtnachricht darf keinen Zug ausloesen"


def test_frische_nachricht_beim_start_wird_nicht_unterdrueckt(conn, einst, tg_attrappe):
    frisch = JETZT - timedelta(minutes=3)
    bot.verarbeite_update(
        conn, tg_attrappe, einst, bau_update(2, 11, "guten morgen", frisch),
        jetzt=JETZT, beim_start=True,
    )
    zeile = conn.execute("SELECT * FROM nachricht WHERE message_id = 11").fetchone()
    assert zeile["unterdrueckt"] == 0


def test_ist_nachtstau_zieht_die_grenze_bei_15_minuten():
    alt = (JETZT - timedelta(minutes=16)).isoformat()
    neu = (JETZT - timedelta(minutes=14)).isoformat()
    assert bot.ist_nachtstau(alt, JETZT) is True
    assert bot.ist_nachtstau(neu, JETZT) is False


def test_gruppe_wird_beim_ersten_update_angelegt(conn, einst, tg_attrappe):
    bot.verarbeite_update(
        conn, tg_attrappe, einst, bau_update(3, 12, "hallo", JETZT),
        jetzt=JETZT, beim_start=False,
    )
    assert repo.hole_gruppe(conn, -100)["titel"] == "Gruppe 1"
```

`tests/conftest.py`:

```python
import httpx
import pytest
from theatersoap import einstellungen, telegram


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"), llm_url="https://llm.test/v1/chat/completions",
        llm_key="K", llm_modell="kimi", stt_url="https://stt.test/v1/audio/transcriptions",
    )


@pytest.fixture
def tg_attrappe():
    def handler(request):
        if "sendMessage" in request.url.path:
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 999}})
        return httpx.Response(200, json={"ok": True, "result": []})
    return telegram.Telegram("T", httpx.Client(transport=httpx.MockTransport(handler)))
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_bot.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.bot'`

- [ ] **Schritt 3: `bot.py` schreiben** (Erstfassung; Aufgabe 10 und 15 bauen darauf auf)

```python
"""Einstiegspunkt: Startroutine und Polling-Schleife."""
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from theatersoap import db, einstellungen, repo, telegram

log = logging.getLogger("theatersoap")

NACHTSTAU_GRENZE = timedelta(minutes=15)


def ist_nachtstau(gesendet_am: str, jetzt: datetime) -> bool:
    """Aelter als 15 Minuten heisst: mitschreiben, aber nicht beantworten (SPEC 9.1)."""
    return jetzt - datetime.fromisoformat(gesendet_am) > NACHTSTAU_GRENZE


def verarbeite_update(conn, tg, e, update: dict, jetzt: datetime,
                      beim_start: bool) -> int | None:
    n = telegram.lies_nachricht(update)
    if not n or n["chat_id"] is None:
        return None

    repo.sichere_gruppe(conn, n["chat_id"], e.bot_name, n["chat_titel"])
    unterdrueckt = 1 if (beim_start and ist_nachtstau(n["gesendet_am"], jetzt)) else 0
    neu = repo.merke_nachricht(
        conn, n["chat_id"], n["message_id"], n["absender"], 0, n["typ"],
        n["text"], n["gesendet_am"], unterdrueckt=unterdrueckt,
    )
    if not neu or unterdrueckt:
        return None
    return n["chat_id"]


def schleife(conn, tg, e) -> None:
    offset = repo.hole_update_id(conn, e.bot_name) + 1
    beim_start = True
    while True:
        try:
            updates = tg.hole_updates(offset=offset)
        except Exception:
            log.exception("getUpdates fehlgeschlagen")
            time.sleep(3.0)
            continue

        jetzt = datetime.now(timezone.utc)
        for update in updates:
            offset = update["update_id"] + 1
            try:
                chat_id = verarbeite_update(conn, tg, e, update, jetzt, beim_start)
                if chat_id is not None:
                    # Aufgabe 10 haengt hier den Gespraechszug ein.
                    log.info("Zug faellig fuer %s", chat_id)
            except Exception:
                # Ein Update darf den Prozess niemals beenden (SPEC 9.4).
                log.exception("Update %s fehlgeschlagen", update.get("update_id"))
            finally:
                repo.setze_update_id(conn, e.bot_name, update["update_id"])
        beim_start = False


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    e = einstellungen.laden()
    conn = db.verbinde(e.db_pfad)
    db.initialisiere(conn)
    tg = telegram.Telegram(e.bot_token, httpx.Client())
    log.info("Bot %s gestartet", e.bot_name)
    schleife(conn, tg, e)


if __name__ == "__main__":
    main()
```

> **Wichtig:** `repo.setze_update_id` steht im `finally`. Ein Update, das beim Verarbeiten scheitert, wird dadurch nicht endlos wiederholt — es bleibt in der Datenbank stehen und der Bot kommt voran. Das ist beabsichtigt: eine Endlosschleife auf einem kaputten Update wäre am Workshoptag fatal.

- [ ] **Schritt 4: Test laufen lassen**

Run: `python -m pytest tests/test_bot.py -v`
Expected: PASS, 4 Tests

**Fertigstellungsbedingung:** Alle vier Tests bestehen. Insbesondere ist belegt, dass eine 14 Stunden alte Nachricht **gespeichert**, aber **nicht beantwortet** wird (§ 9.1 Schritt 2).

- [ ] **Schritt 5: Commit**

```bash
git add theatersoap/bot.py tests/test_bot.py tests/conftest.py
git commit -m "Polling-Schleife mit persistenter Update-Position und Nachtstau"
```

---

## Aufgabe 5: LLM-Client

Das Herzstück der Robustheit. Hier stecken alle drei gemessenen Fehlerbilder.

**Voraussetzung:** Aufgabe 0 abgeschlossen.

**Files:**
- Create: `theatersoap/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces:
  - `llm.LLM(e: Einstellungen, klient: httpx.Client, conn)` mit
    - `.schema(chat_id, system: str, nutzer: str, schema: dict, art: str) -> dict` — Modus A
    - `.prosa(chat_id, system: str, nutzer: str, art: str) -> str` — Modus B
  - `llm.erster_json_block(text: str) -> str`
  - `llm.inhalt_aus(koerper: dict) -> str | None`
  - `llm.LLMFehler`

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_llm.py`:

```python
import httpx
import pytest
from theatersoap import db, llm


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    return c


def antwort_mit(nachricht: dict, finish_reason: str = "stop") -> dict:
    return {
        "choices": [{"message": nachricht, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 1234, "completion_tokens": 56,
                  "prompt_tokens_details": None},
    }


def baue(einst, conn, antworten: list):
    zaehler = {"n": 0}

    def handler(request):
        i = min(zaehler["n"], len(antworten) - 1)
        zaehler["n"] += 1
        eintrag = antworten[i]
        if isinstance(eintrag, int):
            return httpx.Response(eintrag, json={"fehler": "kaputt"})
        return httpx.Response(200, json=eintrag)

    klient = httpx.Client(transport=httpx.MockTransport(handler))
    return llm.LLM(einst, klient, conn), zaehler


def test_doppelte_klammer_wird_repariert(einst, conn):
    k, _ = baue(einst, conn, [antwort_mit({"content": '{{"a": 1}'})])
    assert k.schema(1, "s", "n", {"type": "object"}, "test") == {"a": 1}


def test_inhalt_aus_reasoning_wenn_content_null(einst, conn):
    k, _ = baue(einst, conn,
                [antwort_mit({"content": None, "reasoning": '{"a": 2}'})])
    assert k.schema(1, "s", "n", {"type": "object"}, "test") == {"a": 2}


def test_json_block_wird_aus_umgebendem_text_geschnitten(einst, conn):
    k, _ = baue(einst, conn,
                [antwort_mit({"content": 'Hier: {"a": 3} — fertig.'})])
    assert k.schema(1, "s", "n", {"type": "object"}, "test") == {"a": 3}


def test_geschweifte_klammer_im_string_beendet_den_block_nicht():
    text = '{"zitat": "sie sagte } und ging"}'
    assert llm.erster_json_block(text) == text


def test_502_wird_wiederholt(einst, conn, monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    k, zaehler = baue(einst, conn, [502, antwort_mit({"content": '{"a": 4}'})])
    assert k.schema(1, "s", "n", {"type": "object"}, "test") == {"a": 4}
    assert zaehler["n"] == 2


def test_finish_reason_length_ist_ein_fehler_und_ein_vorfall(einst, conn):
    k, _ = baue(einst, conn,
                [antwort_mit({"content": None}, finish_reason="length")])
    with pytest.raises(llm.LLMFehler):
        k.schema(1, "s", "n", {"type": "object"}, "test")
    zeile = conn.execute(
        "SELECT art FROM vorfall WHERE art = 'abgeschnitten'"
    ).fetchone()
    assert zeile is not None, "abgeschnittene Antwort muss ein Vorfall sein"


def test_aufruf_wird_protokolliert(einst, conn):
    k, _ = baue(einst, conn, [antwort_mit({"content": '{"a": 5}'})])
    k.schema(1, "s", "n", {"type": "object"}, "test")
    zeile = conn.execute("SELECT * FROM aufruf").fetchone()
    assert zeile["tatsaechliche_token"] == 1234
    assert zeile["modus"] == "A"
    assert zeile["erfolg"] == 1


def test_max_tokens_ist_mindestens_9000(einst, conn):
    gesehen = {}

    def handler(request):
        gesehen.update(request.read() and __import__("json").loads(request.read()))
        return httpx.Response(200, json=antwort_mit({"content": '{"a": 6}'}))

    k = llm.LLM(einst, httpx.Client(transport=httpx.MockTransport(handler)), conn)
    k.schema(1, "s", "n", {"type": "object"}, "test")
    assert gesehen["max_tokens"] >= 9000
    assert gesehen["reasoning_effort"] == "none"
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_llm.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.llm'`

- [ ] **Schritt 3: `llm.py` schreiben**

```python
"""Infomaniak-Chat. Enthaelt alle drei gemessenen Fehlerbilder als Gegenmassnahme."""
import json
import logging
import random
import time

import httpx

from theatersoap import repo

log = logging.getLogger("theatersoap.llm")

WARTEZEITEN = (0.7, 1.5, 3.0)   # SPEC 11.3: bis zu vier Versuche
MAX_TOKENS = 9000               # SPEC 11.3: bei 3000 stiller Durchfall


class LLMFehler(RuntimeError):
    pass


def inhalt_aus(koerper: dict) -> str | None:
    """content, sonst reasoning. Gemessenes Fehlerbild 2 (SPEC 4.4)."""
    nachricht = koerper["choices"][0].get("message") or {}
    return nachricht.get("content") or nachricht.get("reasoning")


def erster_json_block(text: str) -> str:
    """Schneidet den ersten vollstaendigen {...}-Block heraus.

    Zeichenketten werden uebersprungen, damit eine geschweifte Klammer in einem
    Belegzitat den Block nicht vorzeitig beendet.
    """
    start = text.find("{")
    if start < 0:
        raise LLMFehler("keine oeffnende Klammer gefunden")
    tiefe = 0
    in_kette = False
    maskiert = False
    for i in range(start, len(text)):
        z = text[i]
        if in_kette:
            if maskiert:
                maskiert = False
            elif z == "\\":
                maskiert = True
            elif z == '"':
                in_kette = False
            continue
        if z == '"':
            in_kette = True
        elif z == "{":
            tiefe += 1
        elif z == "}":
            tiefe -= 1
            if tiefe == 0:
                return text[start:i + 1]
    raise LLMFehler("unvollstaendiger JSON-Block")


class LLM:
    def __init__(self, e, klient: httpx.Client, conn):
        self._e = e
        self._klient = klient
        self._conn = conn

    def _sende(self, koerper: dict) -> dict:
        letzter = None
        for versuch in range(len(WARTEZEITEN) + 1):
            try:
                antwort = self._klient.post(
                    self._e.llm_url,
                    headers={"Authorization": f"Bearer {self._e.llm_key}",
                             "Content-Type": "application/json"},
                    json=koerper,
                    timeout=120.0,
                )
                if antwort.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"HTTP {antwort.status_code}", request=antwort.request,
                        response=antwort,
                    )
                antwort.raise_for_status()
                return antwort.json()
            except (httpx.HTTPStatusError, httpx.TimeoutException,
                    httpx.TransportError) as fehler:
                letzter = fehler
                if versuch >= len(WARTEZEITEN):
                    break
                warte = WARTEZEITEN[versuch] * (1.0 + random.random() * 0.2)
                log.warning("LLM-Aufruf fehlgeschlagen (%s), Wiederholung in %.1fs",
                            fehler, warte)
                time.sleep(warte)
        raise LLMFehler(f"LLM nicht erreichbar: {letzter}")

    def _ruf(self, chat_id, system, nutzer, art, modus, zusatz: dict) -> dict:
        koerper = {
            "model": self._e.llm_modell,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": nutzer}],
            "max_tokens": MAX_TOKENS,
            **zusatz,
        }
        geschaetzt = (len(system) + len(nutzer)) // 3
        beginn = time.monotonic()
        erfolg = 0
        finish_reason = None
        koerper_antwort = None
        try:
            koerper_antwort = self._sende(koerper)
            finish_reason = koerper_antwort["choices"][0].get("finish_reason")
            if finish_reason == "length":
                repo.merke_vorfall(
                    self._conn, chat_id, self._e.bot_name, "abgeschnitten",
                    f"art={art} max_tokens={MAX_TOKENS}",
                )
                raise LLMFehler("Antwort abgeschnitten (finish_reason=length)")
            erfolg = 1
            return koerper_antwort
        finally:
            nutzung = (koerper_antwort or {}).get("usage") or {}
            repo.merke_aufruf(
                self._conn, chat_id, art, modus, geschaetzt,
                nutzung.get("prompt_tokens"), nutzung.get("completion_tokens"),
                finish_reason, int((time.monotonic() - beginn) * 1000), erfolg,
            )

    def schema(self, chat_id, system: str, nutzer: str, schema: dict, art: str) -> dict:
        """Modus A: erzwungenes Schema, kein Reasoning (SPEC 4.1)."""
        antwort = self._ruf(chat_id, system, nutzer, art, "A", {
            "reasoning_effort": "none",
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": art, "strict": True, "schema": schema},
            },
        })
        text = inhalt_aus(antwort)
        if not text:
            raise LLMFehler("leere Antwort")
        text = text.strip()
        if text.startswith("{{"):      # gemessenes Fehlerbild 1 (SPEC 4.4)
            text = text[1:]
        return json.loads(erster_json_block(text))

    def prosa(self, chat_id, system: str, nutzer: str, art: str) -> str:
        """Modus B: freier Text mit Reasoning. Nur ueber /gruendlich (SPEC 4.5)."""
        antwort = self._ruf(chat_id, system, nutzer, art, "B",
                            {"reasoning_effort": "medium"})
        text = inhalt_aus(antwort)
        if not text:
            raise LLMFehler("leere Antwort")
        return text.strip()
```

- [ ] **Schritt 4: Test laufen lassen**

Run: `python -m pytest tests/test_llm.py -v`
Expected: PASS, 8 Tests

**Fertigstellungsbedingung:** Alle acht Tests bestehen. Damit sind belegt: `{{`-Reparatur, Ausweichen auf `reasoning`, Klammer im Belegzitat, 5xx-Wiederholung, `finish_reason: length` als Vorfall statt stiller Leere, Protokollierung in `aufruf`, `max_tokens ≥ 9000`.

- [ ] **Schritt 5: Commit**

```bash
git add theatersoap/llm.py tests/test_llm.py
git commit -m "LLM-Client mit defensivem Parsen, Wiederholung und Aufrufprotokoll"
```

---

## Aufgabe 6: Whisper-Anbindung

**Voraussetzung:** Aufgabe 0 abgeschlossen — der genaue Feldname und MIME-Typ stehen in `docs/vorlagen-notiz.md`.

**Files:**
- Create: `theatersoap/stt.py`
- Test: `tests/test_stt.py`

**Interfaces:**
- Produces: `stt.transkribiere(e, klient: httpx.Client, pfad: pathlib.Path) -> str`
- Produces: `stt.STTFehler`

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_stt.py`:

```python
import httpx
import pytest
from theatersoap import stt


def test_transkript_wird_zurueckgegeben(einst, tmp_path):
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"OggS-testdaten")

    def handler(request):
        assert b"OggS-testdaten" in request.read()
        return httpx.Response(200, json={"text": "Ich bin 1998 weggegangen."})

    klient = httpx.Client(transport=httpx.MockTransport(handler))
    assert stt.transkribiere(einst, klient, datei) == "Ich bin 1998 weggegangen."


def test_5xx_wird_wiederholt(einst, tmp_path, monkeypatch):
    monkeypatch.setattr(stt.time, "sleep", lambda _: None)
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"x")
    zaehler = {"n": 0}

    def handler(request):
        zaehler["n"] += 1
        if zaehler["n"] == 1:
            return httpx.Response(503, json={})
        return httpx.Response(200, json={"text": "ok"})

    klient = httpx.Client(transport=httpx.MockTransport(handler))
    assert stt.transkribiere(einst, klient, datei) == "ok"
    assert zaehler["n"] == 2


def test_leeres_transkript_ist_ein_fehler(einst, tmp_path, monkeypatch):
    monkeypatch.setattr(stt.time, "sleep", lambda _: None)
    datei = tmp_path / "a.ogg"
    datei.write_bytes(b"x")
    klient = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"text": "  "}))
    )
    with pytest.raises(stt.STTFehler):
        stt.transkribiere(einst, klient, datei)
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_stt.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.stt'`

- [ ] **Schritt 3: `stt.py` schreiben**

Feldnamen (`file`, `model`) und MIME-Typ gegen `docs/vorlagen-notiz.md` abgleichen; im Zweifel gilt die Vorlage.

```python
"""Whisper V3 bei Infomaniak."""
import logging
import random
import time
from pathlib import Path

import httpx

log = logging.getLogger("theatersoap.stt")

WARTEZEITEN = (0.7, 1.5, 3.0)


class STTFehler(RuntimeError):
    pass


def transkribiere(e, klient: httpx.Client, pfad: Path) -> str:
    letzter = None
    for versuch in range(len(WARTEZEITEN) + 1):
        try:
            with open(pfad, "rb") as datei:
                antwort = klient.post(
                    e.stt_url,
                    headers={"Authorization": f"Bearer {e.llm_key}"},
                    files={"file": (pfad.name, datei, "audio/ogg")},
                    data={"model": "whisper-v3"},
                    timeout=300.0,
                )
            if antwort.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"HTTP {antwort.status_code}", request=antwort.request,
                    response=antwort,
                )
            antwort.raise_for_status()
            text = (antwort.json().get("text") or "").strip()
            if not text:
                raise STTFehler("leeres Transkript")
            return text
        except (httpx.HTTPStatusError, httpx.TimeoutException,
                httpx.TransportError) as fehler:
            letzter = fehler
            if versuch >= len(WARTEZEITEN):
                break
            warte = WARTEZEITEN[versuch] * (1.0 + random.random() * 0.2)
            log.warning("Whisper fehlgeschlagen (%s), Wiederholung in %.1fs",
                        fehler, warte)
            time.sleep(warte)
    raise STTFehler(f"Whisper nicht erreichbar: {letzter}")
```

- [ ] **Schritt 4: Test laufen lassen**

Run: `python -m pytest tests/test_stt.py -v`
Expected: PASS, 3 Tests

**Fertigstellungsbedingung:** Drei Tests bestehen; ein leeres Transkript wird als Fehler behandelt und nicht als gültiges Ergebnis durchgereicht.

- [ ] **Schritt 5: Commit**

```bash
git add theatersoap/stt.py tests/test_stt.py
git commit -m "Whisper-Anbindung mit Wiederholung"
```

---

## Aufgabe 7: Belegzitat-Verifikation

**Das Fundament, auf dem Modus A ruht** (§ 5). Reine Funktionen, kein Netz, keine Datenbank.

**Files:**
- Create: `theatersoap/zitat.py`
- Test: `tests/test_zitat.py`

**Interfaces:**
- Produces: `zitat.normalisiere(text: str) -> str`
- Produces: `zitat.pruefe(zitat: str, transkript: str) -> bool`
- Produces: `zitat.MIN_SEGMENT = 15`, `zitat.MAX_ABSTAND = 600`

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_zitat.py`:

```python
from theatersoap import zitat

TRANSKRIPT = (
    "Also ich bin 1998 weggegangen, mit dem Zug, morgens um sechs. "
    "Meine Mutter hat nicht gewinkt. " + ("Fuellmaterial dazwischen. " * 40) +
    "Und heute weiss ich gar nicht mehr, wo ich eigentlich hingehoere."
)


def test_woertliches_zitat_besteht():
    assert zitat.pruefe("mit dem Zug, morgens um sechs", TRANSKRIPT) is True


def test_typografische_anfuehrungszeichen_stoeren_nicht():
    assert zitat.pruefe("„Meine Mutter hat nicht gewinkt.“", TRANSKRIPT) is True


def test_mehrfache_leerzeichen_und_zeilenumbrueche_stoeren_nicht():
    assert zitat.pruefe("Meine   Mutter\n hat nicht gewinkt", TRANSKRIPT) is True


def test_erfundenes_zitat_faellt_durch():
    assert zitat.pruefe("Ich war nie ungluecklich dabei", TRANSKRIPT) is False


def test_kurzes_fragment_faellt_durch():
    assert zitat.pruefe("mit dem Zug", TRANSKRIPT) is False


def test_benachbarte_segmente_bestehen():
    z = "Also ich bin 1998 weggegangen [...] Meine Mutter hat nicht gewinkt"
    assert zitat.pruefe(z, TRANSKRIPT) is True


def test_weit_auseinanderliegende_segmente_fallen_durch():
    """Der gemessene Schadensfall: zwei je fuer sich woertliche Stellen,
    ueber 600 Zeichen auseinander, zu einer scheinbaren Aussage verschweisst."""
    z = ("Also ich bin 1998 weggegangen [...] "
         "Und heute weiss ich gar nicht mehr, wo ich eigentlich hingehoere")
    assert zitat.pruefe(z, TRANSKRIPT) is False


def test_vertauschte_reihenfolge_faellt_durch():
    z = ("Meine Mutter hat nicht gewinkt [...] "
         "Also ich bin 1998 weggegangen, mit dem Zug")
    assert zitat.pruefe(z, TRANSKRIPT) is False


def test_leeres_zitat_faellt_durch():
    assert zitat.pruefe("", TRANSKRIPT) is False
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_zitat.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.zitat'`

- [ ] **Schritt 3: `zitat.py` schreiben**

```python
"""Belegzitat-Verifikation (SPEC 5). Reine Funktionen, keine Seiteneffekte."""
import re
import unicodedata

MIN_SEGMENT = 15    # kuerzere Fragmente treffen zufaellig
MAX_ABSTAND = 600   # gesetzt, nicht gemessen (SPEC 12)

_ERSETZUNGEN = str.maketrans({
    "„": '"', "“": '"', "”": '"', "»": '"', "«": '"',
    "‚": "'", "‘": "'", "’": "'", "‛": "'",
    "–": "-", "—": "-", " ": " ",
})

_AUSLASSUNG = re.compile(r"\[\s*\.\.\.\s*\]|\[\s*…\s*\]|…")


def normalisiere(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = text.translate(_ERSETZUNGEN)
    return re.sub(r"\s+", " ", text).strip()


def pruefe(zitat: str, transkript: str) -> bool:
    """True nur, wenn jedes Segment woertlich, in Reihenfolge und nah beieinander steht."""
    t = normalisiere(transkript)
    z = normalisiere(zitat)
    if not z or not t:
        return False

    segmente = [s.strip(' "\'') for s in _AUSLASSUNG.split(z)]
    segmente = [s for s in segmente if s]
    if not segmente:
        return False
    if any(len(s) < MIN_SEGMENT for s in segmente):
        return False

    suchbeginn = 0
    vorheriges_ende = None
    for segment in segmente:
        i = t.find(segment, suchbeginn)
        if i < 0:
            return False
        if vorheriges_ende is not None and i - vorheriges_ende > MAX_ABSTAND:
            return False
        vorheriges_ende = i + len(segment)
        suchbeginn = vorheriges_ende
    return True
```

> **Warum `find` ab `suchbeginn`:** Dadurch ist die Reihenfolgeprüfung geschenkt. Ein Segment, das im Transkript nur *vor* dem vorigen vorkommt, wird nicht gefunden — genau das soll `test_vertauschte_reihenfolge_faellt_durch` zeigen.

- [ ] **Schritt 4: Test laufen lassen**

Run: `python -m pytest tests/test_zitat.py -v`
Expected: PASS, 9 Tests

**Fertigstellungsbedingung:** Alle neun Tests bestehen — insbesondere `test_weit_auseinanderliegende_segmente_fallen_durch`, das den in der Messung beobachteten Schadensfall abbildet. Ohne diesen Test wäre die Prüfung wertlos, weil beide Segmente für sich wörtlich sind.

- [ ] **Schritt 5: Commit**

```bash
git add theatersoap/zitat.py tests/test_zitat.py
git commit -m "Belegzitat-Verifikation mit Reihenfolge und Hoechstabstand"
```

---

## Aufgabe 8: Verdichter und Interview-Pipeline

**Files:**
- Create: `theatersoap/verdichter.py`, `theatersoap/prompts/verdichter.md`
- Modify: `theatersoap/repo.py` (Interview- und Verdichtungs-Abfragen anhängen)
- Test: `tests/test_verdichter.py`

**Interfaces:**
- Consumes: `llm.LLM.schema`, `stt.transkribiere`, `zitat.pruefe`, `telegram.Telegram`
- Produces (in `repo.py`):
  - `repo.lege_interview_an(conn, chat_id, message_id, audio_pfad) -> int`
  - `repo.setze_interview_status(conn, interview_id, status, fehlertext=None) -> None`
  - `repo.setze_interview_transkript(conn, interview_id, transkript) -> None`
  - `repo.setze_interview_name(conn, interview_id, name) -> None`
  - `repo.hole_interview(conn, interview_id) -> sqlite3.Row | None`
  - `repo.offene_interviews(conn) -> list[sqlite3.Row]`
  - `repo.zaehle_interviews(conn, chat_id) -> int`
  - `repo.speichere_verdichtung(conn, chat_id, interview_id, zusammenfassung, themen) -> int`
    (`themen`: `list[dict]` mit `thema`, `beleg_zitat`, `zitat_geprueft`)
  - `repo.verdichtungen(conn, chat_id) -> list[sqlite3.Row]`
  - `repo.themen_zu(conn, verdichtung_id) -> list[sqlite3.Row]`
  - `repo.transkripte(conn, chat_id, name: str | None = None) -> list[sqlite3.Row]`
- Produces (in `verdichter.py`):
  - `verdichter.SCHEMA: dict`
  - `verdichter.verdichte(klm, conn, e, interview_id) -> int` (liefert `verdichtung_id`)
  - `verdichter.pipeline(conn, tg, klm, e, klient, chat_id, message_id, file_id) -> None`
  - `verdichter.greife_offene_auf(conn, tg, klm, e, klient) -> None`

- [ ] **Schritt 1: Prompt schreiben**

`theatersoap/prompts/verdichter.md`:

```markdown
Du verdichtest ein Interviewtranskript fuer eine Theatergruppe.

Liefere:
- eine Zusammenfassung in 3 bis 5 Saetzen
- zwei bis vier Kernthemen, jedes mit einem Belegzitat

Regeln fuer Belegzitate:
- Zitiere WOERTLICH aus dem Transkript. Buchstabengetreu.
- Verwende KEINE Auslassungen wie [...]. Nimm lieber eine kuerzere zusammenhaengende Stelle.
- Ein Zitat muss mindestens 15 Zeichen lang sein.
- Erfinde nichts. Wenn du fuer ein Thema keine Stelle findest, nimm das Thema nicht auf.

Antworte ausschliesslich im vorgegebenen JSON-Schema.
```

- [ ] **Schritt 2: Den fehlschlagenden Test schreiben**

`tests/test_verdichter.py`:

```python
import pytest
from theatersoap import db, repo, verdichter

TRANSKRIPT = (
    "Also ich bin 1998 weggegangen, mit dem Zug, morgens um sechs. "
    "Meine Mutter hat nicht gewinkt."
)


class LLMAttrappe:
    def __init__(self, *antworten):
        self.antworten = list(antworten)
        self.aufrufe = 0

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe += 1
        return self.antworten[min(self.aufrufe - 1, len(self.antworten) - 1)]


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "G")
    return c


def _interview(conn):
    iid = repo.lege_interview_an(conn, 1, 10, "/tmp/a.ogg")
    repo.setze_interview_transkript(conn, iid, TRANSKRIPT)
    return iid


def test_gueltiges_zitat_wird_gespeichert(conn, einst):
    iid = _interview(conn)
    klm = LLMAttrappe({
        "zusammenfassung": "Aufbruch und Kaelte.",
        "kernthemen": [{"thema": "Abschied",
                        "beleg_zitat": "Meine Mutter hat nicht gewinkt"}],
    })
    vid = verdichter.verdichte(klm, conn, einst, iid)
    thema = repo.themen_zu(conn, vid)[0]
    assert thema["beleg_zitat"] == "Meine Mutter hat nicht gewinkt"
    assert thema["zitat_geprueft"] == 1


def test_erfundenes_zitat_loest_genau_einen_retry_aus(conn, einst):
    iid = _interview(conn)
    klm = LLMAttrappe(
        {"zusammenfassung": "z", "kernthemen": [
            {"thema": "Abschied", "beleg_zitat": "Sie weinte bitterlich dabei"}]},
        {"zusammenfassung": "z", "kernthemen": [
            {"thema": "Abschied", "beleg_zitat": "Meine Mutter hat nicht gewinkt"}]},
    )
    vid = verdichter.verdichte(klm, conn, einst, iid)
    assert klm.aufrufe == 2, "genau ein Retry"
    assert repo.themen_zu(conn, vid)[0]["zitat_geprueft"] == 1


def test_nach_dem_retry_wird_ohne_zitat_ausgeliefert(conn, einst):
    iid = _interview(conn)
    klm = LLMAttrappe(
        {"zusammenfassung": "z", "kernthemen": [
            {"thema": "Abschied", "beleg_zitat": "erfunden eins und zwei"}]},
    )
    vid = verdichter.verdichte(klm, conn, einst, iid)
    assert klm.aufrufe == 2, "genau ein Retry, dann aufgeben"
    thema = repo.themen_zu(conn, vid)[0]
    assert thema["thema"] == "Abschied", "Vorschlag bleibt erhalten"
    assert thema["beleg_zitat"] is None
    assert thema["zitat_geprueft"] == 0
    vorfall = conn.execute(
        "SELECT * FROM vorfall WHERE art = 'zitat_ungeprueft'"
    ).fetchone()
    assert vorfall is not None


def test_offene_interviews_werden_beim_start_gefunden(conn):
    repo.lege_interview_an(conn, 1, 10, "/tmp/a.ogg")
    iid2 = repo.lege_interview_an(conn, 1, 11, "/tmp/b.ogg")
    repo.setze_interview_status(conn, iid2, "verdichtet")
    offen = repo.offene_interviews(conn)
    assert [r["message_id"] for r in offen] == [10]
```

- [ ] **Schritt 3: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_verdichter.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.verdichter'`

- [ ] **Schritt 4: Repository-Abfragen anhängen**

An `theatersoap/repo.py` anhängen:

```python
def lege_interview_an(conn, chat_id, message_id, audio_pfad) -> int:
    nummer = zaehle_interviews(conn, chat_id) + 1
    cur = conn.execute(
        "INSERT INTO interview (chat_id, message_id, name, audio_pfad, status, "
        "empfangen_am) VALUES (?, ?, ?, ?, 'empfangen', ?)",
        (chat_id, message_id, f"Interview {nummer}", audio_pfad, _jetzt()),
    )
    conn.commit()
    return cur.lastrowid


def zaehle_interviews(conn, chat_id) -> int:
    return conn.execute(
        "SELECT count(*) FROM interview WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]


def setze_interview_status(conn, interview_id, status, fehlertext=None) -> None:
    conn.execute(
        "UPDATE interview SET status = ?, fehlertext = ?, versuche = versuche + 1 "
        "WHERE id = ?",
        (status, fehlertext, interview_id),
    )
    conn.commit()


def setze_interview_transkript(conn, interview_id, transkript) -> None:
    conn.execute(
        "UPDATE interview SET transkript = ?, status = 'transkribiert' WHERE id = ?",
        (transkript, interview_id),
    )
    conn.commit()


def setze_interview_name(conn, interview_id, name) -> None:
    conn.execute("UPDATE interview SET name = ? WHERE id = ?", (name, interview_id))
    conn.commit()


def hole_interview(conn, interview_id):
    return conn.execute(
        "SELECT * FROM interview WHERE id = ?", (interview_id,)
    ).fetchone()


def offene_interviews(conn) -> list:
    return list(conn.execute(
        "SELECT * FROM interview WHERE status NOT IN ('verdichtet', 'fehlgeschlagen') "
        "ORDER BY id"
    ))


def speichere_verdichtung(conn, chat_id, interview_id, zusammenfassung, themen) -> int:
    cur = conn.execute(
        "INSERT INTO verdichtung (chat_id, interview_id, zusammenfassung, erstellt_am) "
        "VALUES (?, ?, ?, ?)",
        (chat_id, interview_id, zusammenfassung, _jetzt()),
    )
    vid = cur.lastrowid
    for t in themen:
        conn.execute(
            "INSERT INTO verdichtung_thema (chat_id, verdichtung_id, thema, "
            "beleg_zitat, zitat_geprueft) VALUES (?, ?, ?, ?, ?)",
            (chat_id, vid, t["thema"], t["beleg_zitat"], t["zitat_geprueft"]),
        )
    conn.commit()
    return vid


def verdichtungen(conn, chat_id) -> list:
    return list(conn.execute(
        "SELECT v.*, i.name FROM verdichtung v JOIN interview i ON i.id = v.interview_id "
        "WHERE v.chat_id = ? ORDER BY v.id",
        (chat_id,),
    ))


def themen_zu(conn, verdichtung_id) -> list:
    return list(conn.execute(
        "SELECT * FROM verdichtung_thema WHERE verdichtung_id = ? ORDER BY id",
        (verdichtung_id,),
    ))


def transkripte(conn, chat_id, name: str | None = None) -> list:
    if name:
        return list(conn.execute(
            "SELECT * FROM interview WHERE chat_id = ? AND transkript IS NOT NULL "
            "AND lower(name) LIKE ? ORDER BY id",
            (chat_id, f"%{name.lower()}%"),
        ))
    return list(conn.execute(
        "SELECT * FROM interview WHERE chat_id = ? AND transkript IS NOT NULL ORDER BY id",
        (chat_id,),
    ))
```

- [ ] **Schritt 5: `verdichter.py` schreiben**

```python
"""Verdichter-Prompt (SPEC 4.2) und Interview-Pipeline (SPEC 10)."""
import logging
from pathlib import Path

from theatersoap import repo, stt, zitat

log = logging.getLogger("theatersoap.verdichter")

PROMPT = (Path(__file__).parent / "prompts" / "verdichter.md").read_text(encoding="utf-8")

SCHEMA = {
    "type": "object",
    "properties": {
        "zusammenfassung": {"type": "string"},
        "kernthemen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "thema": {"type": "string"},
                    "beleg_zitat": {"type": "string"},
                },
                "required": ["thema", "beleg_zitat"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["zusammenfassung", "kernthemen"],
    "additionalProperties": False,
}

NACHFASSEN = (
    "\n\nDein vorheriges Zitat stand so nicht im Transkript. "
    "Zitiere buchstabengetreu eine zusammenhaengende Stelle, ohne Auslassungen."
)


def verdichte(klm, conn, e, interview_id: int) -> int:
    """Verdichtet ein Interview. Genau ein Retry bei ungueltigem Zitat (SPEC 5.2)."""
    interview = repo.hole_interview(conn, interview_id)
    transkript = interview["transkript"]
    chat_id = interview["chat_id"]

    ergebnis = klm.schema(chat_id, PROMPT, transkript, SCHEMA, "verdichter")
    themen = _pruefe_themen(ergebnis.get("kernthemen", []), transkript)

    if any(t["zitat_geprueft"] == 0 for t in themen):
        ergebnis = klm.schema(chat_id, PROMPT + NACHFASSEN, transkript, SCHEMA,
                              "verdichter")
        themen = _pruefe_themen(ergebnis.get("kernthemen", []), transkript)

    for t in themen:
        if t["zitat_geprueft"] == 0:
            repo.merke_vorfall(conn, chat_id, e.bot_name, "zitat_ungeprueft",
                               f"interview={interview_id} zitat={t['_verworfen']!r}")
            t["beleg_zitat"] = None
        t.pop("_verworfen", None)

    return repo.speichere_verdichtung(
        conn, chat_id, interview_id, ergebnis.get("zusammenfassung", ""), themen
    )


def _pruefe_themen(rohthemen: list, transkript: str) -> list:
    geprueft = []
    for t in rohthemen:
        roh = t.get("beleg_zitat") or ""
        gueltig = zitat.pruefe(roh, transkript)
        geprueft.append({
            "thema": t.get("thema", ""),
            "beleg_zitat": roh if gueltig else None,
            "zitat_geprueft": 1 if gueltig else 0,
            "_verworfen": None if gueltig else roh,
        })
    return geprueft


def pipeline(conn, tg, klm, e, klient, chat_id, message_id, file_id) -> None:
    """Sprachnachricht bis zur fertigen Verdichtung. Laeuft im Hintergrund-Thread."""
    ziel = Path(e.audio_verz) / str(chat_id) / f"{message_id}.ogg"
    interview_id = None
    try:
        tg.sende(chat_id, "Kommt an, ich hoere durch - dauert einen Moment.")
        tg.lade_datei(file_id, ziel)
        interview_id = repo.lege_interview_an(conn, chat_id, message_id, str(ziel))
        _weiter(conn, tg, klm, e, klient, interview_id)
    except Exception:
        log.exception("Interview-Pipeline fehlgeschlagen")
        if interview_id is not None:
            repo.setze_interview_status(conn, interview_id, "fehlgeschlagen", "Pipeline")
        repo.merke_vorfall(conn, chat_id, e.bot_name, "interview_fehler",
                           f"message_id={message_id}")
        tg.sende(chat_id, "Diese Aufnahme konnte ich nicht verstehen - "
                          "schickt sie bitte nochmal.")


def _weiter(conn, tg, klm, e, klient, interview_id: int) -> None:
    interview = repo.hole_interview(conn, interview_id)
    if interview["status"] == "empfangen":
        text = stt.transkribiere(e, klient, Path(interview["audio_pfad"]))
        repo.setze_interview_transkript(conn, interview_id, text)
        # Aufgabe 14 stellt hier die Namensrueckfrage.
    verdichte(klm, conn, e, interview_id)
    repo.setze_interview_status(conn, interview_id, "verdichtet")


def greife_offene_auf(conn, tg, klm, e, klient) -> None:
    """Beim Start: alles zu Ende bringen, was nicht in einem Endzustand steht (SPEC 9.1)."""
    for interview in repo.offene_interviews(conn):
        try:
            _weiter(conn, tg, klm, e, klient, interview["id"])
            log.info("Interview %s nachtraeglich fertiggestellt", interview["id"])
        except Exception:
            log.exception("Wiederaufnahme von Interview %s gescheitert", interview["id"])
            repo.setze_interview_status(conn, interview["id"], "fehlgeschlagen",
                                        "Wiederaufnahme")
```

- [ ] **Schritt 6: Test laufen lassen**

Run: `python -m pytest tests/test_verdichter.py -v`
Expected: PASS, 4 Tests

**Fertigstellungsbedingung:** Vier Tests bestehen. Belegt sind: gültiges Zitat wird gespeichert, ungültiges löst **genau einen** Retry aus, nach dem Retry wird der Vorschlag **ohne Zitat** ausgeliefert statt verworfen (§ 5.2), und offene Interviews sind beim Start auffindbar.

- [ ] **Schritt 7: Commit**

```bash
git add theatersoap/verdichter.py theatersoap/prompts/ theatersoap/repo.py tests/test_verdichter.py
git commit -m "Verdichter und Interview-Pipeline mit geprueften Belegzitaten"
```

---

## Aufgabe 9: Kontext-Zusammenbau, Budget, Kürzungsleiter

**Files:**
- Create: `theatersoap/kontext.py`, `theatersoap/prompts/system.md`
- Modify: `theatersoap/repo.py` (Arbeitsstand-, Journal- und Szenen-Abfragen anhängen)
- Test: `tests/test_kontext.py`

**Interfaces:**
- Produces (in `repo.py`):
  - `repo.hole_arbeitsstand(conn, chat_id) -> sqlite3.Row | None`
  - `repo.setze_arbeitsstand(conn, chat_id, feld: str, wert: str) -> None` (nur die Felder `begriffe`, `kernthema`, `kernthema_begruendung`, `hauptkonflikt`)
  - `repo.figuren(conn, chat_id) -> list[sqlite3.Row]`
  - `repo.lege_figur_an(conn, chat_id, name, beschreibung, beleg_zitat=None) -> int`
  - `repo.szenen(conn, chat_id) -> list[sqlite3.Row]`
  - `repo.aktuelle_szene(conn, chat_id) -> sqlite3.Row | None`
  - `repo.lege_szene_an(conn, chat_id, titel, kurzbeschreibung) -> int`
  - `repo.journal(conn, chat_id) -> list[sqlite3.Row]`
  - `repo.schreibe_journal(conn, chat_id, art, text, quelle, bis_message_id=None) -> None`
- Produces (in `kontext.py`):
  - `kontext.schaetze(text: str) -> int`
  - `kontext.SYSTEM: str`
  - `kontext.baue(conn, chat_id, ausloeser: list, e) -> str` — liefert die Nutzernachricht
  - `kontext.BUDGETS: dict[str, int]`, `kontext.ZIEL = 10000`, `kontext.REISSLEINE = 20000`

- [ ] **Schritt 1: Systemanweisung schreiben**

`theatersoap/prompts/system.md` (§ 6.3):

```markdown
Du begleitest eine Kleingruppe von Laienschauspielerinnen dabei, aus eigenen Interviews
ein Theaterstueck zu entwickeln. Du bist dramaturgischer Begleiter, nicht Regisseur.

Der Weg fuehrt ueblicherweise ueber diese Stationen: Begriffe sammeln, Interviewfragen
entwickeln, Interviews fuehren, zu einem Kernthema verdichten, Figuren entwickeln,
Hauptkonflikte finden, Szenen bauen, Szenen feinschleifen. Das ist eine Beschreibung,
kein Ablaufplan. Die Gruppe darf jederzeit abbiegen, zurueckspringen oder etwas
verwerfen. Widersprich ihr nicht mit Verweis auf eine Reihenfolge.

Regeln:
- Erfinde nichts, was nicht im Material steht.
- Belege Vorschlaege nach Moeglichkeit mit einem woertlichen Zitat aus den Interviews.
- Zitiere buchstabengetreu. Keine Auslassungen mit [...]. Zitate werden geprueft und
  fliegen sonst raus.
- Biete an, statt vorzuschreiben. Zwei Vorschlaege sind besser als eine Anweisung.
- Fasse dich kurz. Die Gruppe liest auf dem Telefon.

Du kennst diese Befehle und darfst sie von dir aus anbieten:
/wortlaut <name> - ich lese das Originaltranskript einer Person mit
/merken <text> - haelt eine Entscheidung fest
/verworfen <text> - haelt fest, was verworfen wurde
/stand - zeigt den aktuellen Arbeitsstand
/gruendlich - ich nehme mir fuer den naechsten Zug mehr Zeit

Verdichtungen von Interviews werden nie nachtraeglich geaendert. Was einmal
festgehalten wurde, bleibt stehen.
```

- [ ] **Schritt 2: Den fehlschlagenden Test schreiben**

`tests/test_kontext.py`:

```python
import pytest
from theatersoap import db, kontext, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "G")
    return c


def test_schaetzung_ist_zeichen_durch_drei():
    assert kontext.schaetze("a" * 300) == 100


def test_leere_bloecke_fehlen_im_prompt(conn, einst):
    text = kontext.baue(conn, 1, [], einst)
    assert "VERDICHTUNGEN" not in text
    assert "FIGUREN" not in text
    assert "JOURNAL" not in text


def test_arbeitsstand_erscheint_sobald_er_existiert(conn, einst):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    text = kontext.baue(conn, 1, [], einst)
    assert "Ankommen" in text


def test_pausenmarkierung_ab_einer_stunde(conn, einst):
    repo.merke_nachricht(conn, 1, 1, "Ada", 0, "text", "bis morgen",
                         "2026-09-05T18:00:00+00:00")
    repo.merke_nachricht(conn, 1, 2, "Ada", 0, "text", "guten morgen",
                         "2026-09-06T12:00:00+00:00")
    text = kontext.baue(conn, 1, [], einst)
    assert "[Pause: 18 Stunden]" in text


def test_keine_pausenmarkierung_bei_kurzem_abstand(conn, einst):
    repo.merke_nachricht(conn, 1, 1, "Ada", 0, "text", "a",
                         "2026-09-05T18:00:00+00:00")
    repo.merke_nachricht(conn, 1, 2, "Ada", 0, "text", "b",
                         "2026-09-05T18:05:00+00:00")
    assert "[Pause" not in kontext.baue(conn, 1, [], einst)


def test_kuerzungsleiter_haelt_die_reissleine_ein(conn, einst):
    """Auch bei absurd viel Material muss der Prompt unter der Reissleine bleiben."""
    for i in range(40):
        iid = repo.lege_interview_an(conn, 1, 100 + i, f"/tmp/{i}.ogg")
        repo.setze_interview_transkript(conn, iid, "Wort " * 3000)
        repo.speichere_verdichtung(conn, 1, iid, "Zusammenfassung " * 200, [])
    for i in range(300):
        repo.schreibe_journal(conn, 1, "vorgeschlagen", f"Vorschlag {i}", "extraktor")
    for i in range(400):
        repo.merke_nachricht(conn, 1, 1000 + i, "Ada", 0, "text", "Gerede " * 50,
                             "2026-09-05T12:00:00+00:00")
    conn.execute("UPDATE gruppe SET wortlaut_modus = '*' WHERE chat_id = 1")
    conn.commit()

    text = kontext.baue(conn, 1, [], einst)

    assert kontext.schaetze(text) < kontext.REISSLEINE
    vorfaelle = conn.execute(
        "SELECT count(*) FROM vorfall WHERE art = 'kuerzung'"
    ).fetchone()[0]
    assert vorfaelle >= 1, "jede gezogene Stufe muss ein Vorfall sein"


def test_notbremse_enthaelt_immer_die_ausloesende_nachricht(conn, einst):
    for i in range(400):
        repo.merke_nachricht(conn, 1, 1000 + i, "Ada", 0, "text", "Gerede " * 200,
                             "2026-09-05T12:00:00+00:00")
    text = kontext.baue(conn, 1, [{"absender": "Bo", "text": "WICHTIGE FRAGE"}], einst)
    assert "WICHTIGE FRAGE" in text
```

- [ ] **Schritt 3: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_kontext.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.kontext'`

- [ ] **Schritt 4: Repository-Abfragen anhängen**

An `theatersoap/repo.py` anhängen:

```python
ARBEITSSTAND_FELDER = ("begriffe", "kernthema", "kernthema_begruendung", "hauptkonflikt")


def hole_arbeitsstand(conn, chat_id):
    return conn.execute(
        "SELECT * FROM arbeitsstand WHERE chat_id = ?", (chat_id,)
    ).fetchone()


def setze_arbeitsstand(conn, chat_id, feld: str, wert: str) -> None:
    if feld not in ARBEITSSTAND_FELDER:
        raise ValueError(f"unbekanntes Feld: {feld}")
    conn.execute(
        "INSERT INTO arbeitsstand (chat_id, geaendert_am) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO NOTHING",
        (chat_id, _jetzt()),
    )
    conn.execute(
        f"UPDATE arbeitsstand SET {feld} = ?, geaendert_am = ? WHERE chat_id = ?",
        (wert, _jetzt(), chat_id),
    )
    conn.commit()


def figuren(conn, chat_id) -> list:
    return list(conn.execute(
        "SELECT * FROM figur WHERE chat_id = ? ORDER BY id", (chat_id,)
    ))


def lege_figur_an(conn, chat_id, name, beschreibung, beleg_zitat=None) -> int:
    cur = conn.execute(
        "INSERT INTO figur (chat_id, name, beschreibung, beleg_zitat, geaendert_am) "
        "VALUES (?, ?, ?, ?, ?)",
        (chat_id, name, beschreibung, beleg_zitat, _jetzt()),
    )
    conn.commit()
    return cur.lastrowid


def szenen(conn, chat_id) -> list:
    return list(conn.execute(
        "SELECT * FROM szene WHERE chat_id = ? ORDER BY nummer, id", (chat_id,)
    ))


def aktuelle_szene(conn, chat_id):
    return conn.execute(
        "SELECT * FROM szene WHERE chat_id = ? ORDER BY geaendert_am DESC LIMIT 1",
        (chat_id,),
    ).fetchone()


def lege_szene_an(conn, chat_id, titel, kurzbeschreibung) -> int:
    nummer = conn.execute(
        "SELECT coalesce(max(nummer), 0) + 1 FROM szene WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO szene (chat_id, nummer, titel, kurzbeschreibung, geaendert_am) "
        "VALUES (?, ?, ?, ?, ?)",
        (chat_id, nummer, titel, kurzbeschreibung, _jetzt()),
    )
    conn.commit()
    return cur.lastrowid


def journal(conn, chat_id) -> list:
    return list(conn.execute(
        "SELECT * FROM journal WHERE chat_id = ? ORDER BY id", (chat_id,)
    ))


def schreibe_journal(conn, chat_id, art, text, quelle, bis_message_id=None) -> None:
    conn.execute(
        "INSERT INTO journal (chat_id, art, text, quelle, bis_message_id, erstellt_am) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, art, text, quelle, bis_message_id, _jetzt()),
    )
    conn.commit()
```

- [ ] **Schritt 5: `kontext.py` schreiben**

```python
"""Prompt-Zusammenbau (SPEC 6) und Kuerzungsleiter (SPEC 7)."""
from datetime import datetime
from pathlib import Path

from theatersoap import repo

SYSTEM = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")

ZIEL = 10_000
REISSLEINE = 20_000
PAUSE_AB_MINUTEN = 60
JOURNAL_RANG = {"entschieden": 0, "verworfen": 1, "offen": 2, "vorgeschlagen": 3}

BUDGETS = {
    "verdichtungen": 3000,
    "transkripte": 5000,
    "arbeitsstand": 1200,
    "szene": 1500,
    "journal": 1500,
    "fenster": 2500,
    "ausloeser": 300,
}

# Reihenfolge im Prompt: stabil nach vorn, fluechtig nach hinten (SPEC 6.1).
# Begruendung ist die Aufmerksamkeitsverteilung des Modells - kein Caching-Argument,
# Caching ist bei Infomaniak unbelegt.
REIHENFOLGE = ("verdichtungen", "transkripte", "arbeitsstand", "szene",
               "journal", "fenster", "ausloeser")


def schaetze(text: str) -> int:
    """Zeichen durch drei. Ueberschaetzt fuer Deutsch leicht - richtige Fehlerrichtung."""
    return len(text or "") // 3


def _kappe(text: str, budget: int) -> str:
    grenze = budget * 3
    return text if len(text) <= grenze else text[:grenze]


def _verdichtungen(conn, chat_id, mit_zitaten: bool) -> str:
    zeilen = []
    for v in repo.verdichtungen(conn, chat_id):
        zeilen.append(f"- {v['name']}: {v['zusammenfassung']}")
        for t in repo.themen_zu(conn, v["id"]):
            if mit_zitaten and t["beleg_zitat"]:
                zeilen.append(f"  * {t['thema']} — \"{t['beleg_zitat']}\"")
            else:
                zeilen.append(f"  * {t['thema']}")
    return "VERDICHTUNGEN DER INTERVIEWS\n" + "\n".join(zeilen) if zeilen else ""


def _transkripte(conn, chat_id, modus: str | None, nur_neuestes: bool) -> str:
    if not modus:
        return ""
    zeilen = repo.transkripte(conn, chat_id, None if modus == "*" else modus)
    if nur_neuestes and zeilen:
        zeilen = zeilen[-1:]
    if not zeilen:
        return ""
    teile = [f"--- {i['name']} ---\n{i['transkript']}" for i in zeilen]
    return "VOLLTRANSKRIPTE\n" + "\n\n".join(teile)


def _arbeitsstand(conn, chat_id) -> str:
    a = repo.hole_arbeitsstand(conn, chat_id)
    zeilen = []
    if a:
        for feld, beschriftung in (("begriffe", "Begriffe"),
                                   ("kernthema", "Kernthema"),
                                   ("kernthema_begruendung", "Begruendung"),
                                   ("hauptkonflikt", "Hauptkonflikt")):
            if a[feld]:
                zeilen.append(f"{beschriftung}: {a[feld]}")
    figuren = repo.figuren(conn, chat_id)
    if figuren:
        zeilen.append("FIGUREN")
        zeilen += [f"- {f['name']}: {f['beschreibung'] or ''}" for f in figuren]
    szenen = repo.szenen(conn, chat_id)
    if szenen:
        zeilen.append("SZENEN")
        zeilen += [f"- {s['nummer']}. {s['titel']}: {s['kurzbeschreibung'] or ''}"
                   for s in szenen]
    return "ARBEITSSTAND\n" + "\n".join(zeilen) if zeilen else ""


def _szene(conn, chat_id) -> str:
    s = repo.aktuelle_szene(conn, chat_id)
    if not s or not s["volltext"]:
        return ""
    return f"AKTUELLE SZENE ({s['titel']})\n{s['volltext']}"


def _journal(conn, chat_id, hoechstens: int | None = None) -> str:
    eintraege = repo.journal(conn, chat_id)
    if hoechstens is not None and len(eintraege) > hoechstens:
        # Nach Rang beschneiden, nicht nach Alter (SPEC 6.2).
        eintraege = sorted(
            sorted(eintraege, key=lambda j: j["id"]),
            key=lambda j: JOURNAL_RANG.get(j["art"], 9),
        )[:hoechstens]
        eintraege = sorted(eintraege, key=lambda j: j["id"])
    if not eintraege:
        return ""
    zeilen = [f"- [{j['art']}] {j['text']}" for j in eintraege]
    return "JOURNAL\n" + "\n".join(zeilen)


def _fenster(conn, chat_id, budget: int) -> str:
    zeilen = []
    vorige: datetime | None = None
    for n in repo.letzte_nachrichten(conn, chat_id, anzahl=200):
        wann = datetime.fromisoformat(n["gesendet_am"])
        if vorige is not None:
            minuten = (wann - vorige).total_seconds() / 60
            if minuten >= PAUSE_AB_MINUTEN:
                zeilen.append(f"[Pause: {round(minuten / 60)} Stunden]")
        vorige = wann
        sprecher = "Du" if n["ist_bot"] else n["absender"]
        # Nachrichten ohne Text (Sprache, Foto, Sticker) erscheinen als "Ada: (sprache)":
        # die Gruppe hat etwas geschickt, und das Modell soll das wissen.
        inhalt = n["text"] or f"({n['typ']})"
        zeilen.append(f"{sprecher}: {inhalt}")
    text = "VERLAUF\n" + "\n".join(zeilen)
    if schaetze(text) <= budget:
        return text
    # von hinten fuellen
    behalten = []
    summe = 0
    for zeile in reversed(zeilen):
        summe += schaetze(zeile) + 1
        if summe > budget:
            break
        behalten.append(zeile)
    return "VERLAUF\n" + "\n".join(reversed(behalten))


def _ausloeser(ausloeser: list) -> str:
    if not ausloeser:
        return ""
    zeilen = [f"{n['absender']}: {n['text']}" for n in ausloeser]
    return "DARAUF ANTWORTEST DU JETZT\n" + "\n".join(zeilen)


def baue(conn, chat_id: int, ausloeser: list, e) -> str:
    gruppe = repo.hole_gruppe(conn, chat_id)
    modus = gruppe["wortlaut_modus"] if gruppe else None

    def zusammen(bloecke: dict) -> str:
        return "\n\n".join(bloecke[k] for k in REIHENFOLGE if bloecke.get(k))

    bloecke = {
        "verdichtungen": _kappe(_verdichtungen(conn, chat_id, True),
                                BUDGETS["verdichtungen"]),
        "transkripte": _kappe(_transkripte(conn, chat_id, modus, False),
                              BUDGETS["transkripte"]),
        "arbeitsstand": _kappe(_arbeitsstand(conn, chat_id), BUDGETS["arbeitsstand"]),
        "szene": _kappe(_szene(conn, chat_id), BUDGETS["szene"]),
        "journal": _kappe(_journal(conn, chat_id), BUDGETS["journal"]),
        "fenster": _fenster(conn, chat_id, BUDGETS["fenster"]),
        "ausloeser": _kappe(_ausloeser(ausloeser), BUDGETS["ausloeser"]),
    }

    if schaetze(zusammen(bloecke)) <= ZIEL:
        return zusammen(bloecke)

    stufen = (
        (1, lambda b: b.update(
            transkripte=_kappe(_transkripte(conn, chat_id, modus, True),
                               BUDGETS["transkripte"]))),
        (2, lambda b: b.update(fenster=_fenster(conn, chat_id, 1500))),
        (3, lambda b: b.update(
            verdichtungen=_kappe(_verdichtungen(conn, chat_id, False),
                                 BUDGETS["verdichtungen"]))),
        (4, lambda b: b.update(journal=_journal(conn, chat_id, hoechstens=20))),
        (5, lambda b: b.update(verdichtungen="", transkripte="", szene="", journal="")),
    )
    for nummer, anwenden in stufen:
        anwenden(bloecke)
        repo.merke_vorfall(conn, chat_id, e.bot_name, "kuerzung",
                           f"Stufe {nummer} gezogen", stufe=nummer)
        if schaetze(zusammen(bloecke)) <= ZIEL:
            break
    return zusammen(bloecke)
```

> **Zur Kürzungsleiter:** Stufe 5 setzt alles ausser `arbeitsstand`, `fenster` und
> `ausloeser` auf leer. Das ist die Notbremse aus § 7.2 — sie passt immer, und deshalb gibt
> es keinen Zustand, in dem der Bot wegen des Budgets nicht antwortet. Der Test
> `test_notbremse_enthaelt_immer_die_ausloesende_nachricht` sichert genau das ab.

- [ ] **Schritt 6: Test laufen lassen**

Run: `python -m pytest tests/test_kontext.py -v`
Expected: PASS, 7 Tests

**Fertigstellungsbedingung:** Sieben Tests bestehen. Belegt sind: leere Blöcke fehlen ganz (§ 6.1 datengetrieben), Pausenmarkierung ab 60 Minuten, Kürzungsleiter hält die Reißleine auch bei 40 Interviews und 400 Nachrichten ein, jede Stufe schreibt einen Vorfall, und die auslösende Nachricht überlebt die Notbremse.

- [ ] **Schritt 7: Commit**

```bash
git add theatersoap/kontext.py theatersoap/prompts/system.md theatersoap/repo.py tests/test_kontext.py
git commit -m "Kontext-Zusammenbau mit Budgets, Pausenmarkierung und Kuerzungsleiter"
```

---

## Aufgabe 10: Gesprächszug — Auslöser, Sperre, Sammeln, Antwort

**Nach dieser Aufgabe läuft der Durchstich.**

**Files:**
- Create: `theatersoap/ablauf.py`
- Modify: `theatersoap/bot.py` (Zug einhängen, Hintergrund-Pool, Wiederaufnahme beim Start)
- Test: `tests/test_ablauf.py`

**Interfaces:**
- Produces:
  - `ablauf.ist_ausloeser(n: dict, bot_name: str, gruppe) -> bool`
  - `ablauf.bearbeite(conn, tg, klm, e, chat_id) -> None`
  - `ablauf.antworte(conn, tg, klm, e, chat_id, ausloeser: list) -> None`
  - `ablauf.TIPP_INTERVALL = 4.0`, `ablauf.HINWEIS_NACH = 10.0`

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_ablauf.py`:

```python
import threading
import time

import pytest
from theatersoap import ablauf, db, repo


class LLMAttrappe:
    def __init__(self, antwort="Gute Frage.", verzoegerung=0.0):
        self.antwort = antwort
        self.verzoegerung = verzoegerung
        self.gesehen = []

    def schema(self, chat_id, system, nutzer, schema, art):
        time.sleep(self.verzoegerung)
        self.gesehen.append(nutzer)
        return {"antwort": self.antwort}


class TGAttrappe:
    def __init__(self):
        self.gesendet = []
        self._id = 500

    def sende(self, chat_id, text):
        self._id += 1
        self.gesendet.append((chat_id, text))
        return self._id

    def tippt(self, chat_id):
        pass


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "G")
    return c


def gruppe(conn):
    return repo.hole_gruppe(conn, 1)


def test_reply_auf_bot_loest_aus(conn):
    n = {"typ": "text", "text": "und weiter?", "antwortet_auf_bot": True,
         "message_id": 1}
    assert ablauf.ist_ausloeser(n, "meinbot", gruppe(conn)) is True


def test_erwaehnung_loest_aus(conn):
    n = {"typ": "text", "text": "@meinbot was meinst du?", "antwortet_auf_bot": False,
         "message_id": 1}
    assert ablauf.ist_ausloeser(n, "meinbot", gruppe(conn)) is True


def test_befehl_loest_aus(conn):
    n = {"typ": "text", "text": "/stand", "antwortet_auf_bot": False, "message_id": 1}
    assert ablauf.ist_ausloeser(n, "meinbot", gruppe(conn)) is True


def test_sprachnachricht_loest_immer_aus(conn):
    n = {"typ": "sprache", "text": None, "antwortet_auf_bot": False, "message_id": 1}
    assert ablauf.ist_ausloeser(n, "meinbot", gruppe(conn)) is True


def test_beilaeufiges_geplauder_loest_nicht_aus(conn):
    n = {"typ": "text", "text": "ich hol mir Kaffee", "antwortet_auf_bot": False,
         "message_id": 1}
    assert ablauf.ist_ausloeser(n, "meinbot", gruppe(conn)) is False


def test_nachzuegler_werden_in_einen_zug_gesammelt(conn, einst):
    """Waehrend ein Aufruf laeuft, sammeln sich Nachrichten und werden
    gemeinsam beantwortet - nicht parallel (SPEC 1.3)."""
    repo.merke_nachricht(conn, 1, 1, "Ada", 0, "text", "@bot erste",
                         "2026-09-05T12:00:00+00:00")
    klm = LLMAttrappe(verzoegerung=0.3)
    tg = TGAttrappe()

    t = threading.Thread(target=ablauf.bearbeite, args=(conn, tg, klm, einst, 1))
    t.start()
    time.sleep(0.1)
    repo.merke_nachricht(conn, 1, 2, "Bo", 0, "text", "@bot zweite",
                         "2026-09-05T12:00:05+00:00")
    repo.merke_nachricht(conn, 1, 3, "Cem", 0, "text", "@bot dritte",
                         "2026-09-05T12:00:06+00:00")
    ablauf.bearbeite(conn, tg, klm, einst, 1)
    t.join(timeout=5)

    assert len(klm.gesehen) == 2, "erster Zug, dann ein Sammelzug - nicht drei"
    assert "zweite" in klm.gesehen[1] and "dritte" in klm.gesehen[1]


def test_wasserzeichen_wird_nach_der_antwort_gesetzt(conn, einst):
    repo.merke_nachricht(conn, 1, 7, "Ada", 0, "text", "@bot hallo",
                         "2026-09-05T12:00:00+00:00")
    ablauf.bearbeite(conn, TGAttrappe(), LLMAttrappe(), einst, 1)
    assert repo.unbeantwortete(conn, 1) == []


def test_bot_antwort_wird_mitgeschrieben(conn, einst):
    repo.merke_nachricht(conn, 1, 8, "Ada", 0, "text", "@bot hallo",
                         "2026-09-05T12:00:00+00:00")
    ablauf.bearbeite(conn, TGAttrappe(), LLMAttrappe("Meine Antwort"), einst, 1)
    zeile = conn.execute(
        "SELECT * FROM nachricht WHERE ist_bot = 1"
    ).fetchone()
    assert zeile["text"] == "Meine Antwort"


def test_llm_fehler_meldet_der_gruppe_und_haelt_nicht_an(conn, einst):
    class Kaputt:
        def schema(self, *a, **k):
            raise RuntimeError("Infomaniak weg")

    repo.merke_nachricht(conn, 1, 9, "Ada", 0, "text", "@bot hallo",
                         "2026-09-05T12:00:00+00:00")
    tg = TGAttrappe()
    ablauf.bearbeite(conn, tg, Kaputt(), einst, 1)
    assert any("hakt" in text for _, text in tg.gesendet)
    assert repo.unbeantwortete(conn, 1) == [], "Zug gilt als erledigt, kein Endlosversuch"
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_ablauf.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.ablauf'`

- [ ] **Schritt 3: `ablauf.py` schreiben**

```python
"""Ein Gespraechszug: Ausloeser pruefen, sammeln, antworten (SPEC 1.2, 1.3)."""
import logging
import threading

from theatersoap import kontext, repo

log = logging.getLogger("theatersoap.ablauf")

TIPP_INTERVALL = 4.0
HINWEIS_NACH = 10.0

ANTWORT_SCHEMA = {
    "type": "object",
    "properties": {"antwort": {"type": "string"}},
    "required": ["antwort"],
    "additionalProperties": False,
}

_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _sperren_schutz:
        return _sperren.setdefault(chat_id, threading.Lock())


def ist_ausloeser(n: dict, bot_name: str, gruppe) -> bool:
    """Reply, Erwaehnung, Befehl, Sprachnachricht - sonst nicht (SPEC 1.2).
    Die offene Rueckfrage-Sequenz kommt in Aufgabe 13 dazu."""
    if n["typ"] == "sprache":
        return True
    if n.get("antwortet_auf_bot"):
        return True
    text = (n.get("text") or "").strip()
    if text.startswith("/"):
        return True
    return f"@{bot_name}".lower() in text.lower()


class _Tippanzeige:
    """Haelt die Tippanzeige am Leben und schickt nach 10 Sekunden einen Hinweis."""

    def __init__(self, tg, chat_id):
        self._tg = tg
        self._chat_id = chat_id
        self._ende = threading.Event()
        self._faden = threading.Thread(target=self._laufen, daemon=True)

    def __enter__(self):
        self._faden.start()
        return self

    def __exit__(self, *_):
        self._ende.set()

    def _laufen(self):
        vergangen = 0.0
        hinweis_geschickt = False
        while not self._ende.is_set():
            try:
                self._tg.tippt(self._chat_id)
            except Exception:
                log.debug("Tippanzeige fehlgeschlagen", exc_info=True)
            if vergangen >= HINWEIS_NACH and not hinweis_geschickt:
                hinweis_geschickt = True
                try:
                    self._tg.sende(self._chat_id, "Einen Moment, ich denke nach.")
                except Exception:
                    log.debug("Hinweis fehlgeschlagen", exc_info=True)
            self._ende.wait(TIPP_INTERVALL)
            vergangen += TIPP_INTERVALL


def antworte(conn, tg, klm, e, chat_id: int, ausloeser: list) -> None:
    letzte_id = ausloeser[-1]["message_id"]
    try:
        nutzer = kontext.baue(conn, chat_id, ausloeser, e)
        with _Tippanzeige(tg, chat_id):
            ergebnis = klm.schema(chat_id, kontext.SYSTEM, nutzer,
                                  ANTWORT_SCHEMA, "gespraech")
        text = (ergebnis.get("antwort") or "").strip() or "Dazu faellt mir gerade nichts ein."
        message_id = tg.sende(chat_id, text)
        repo.merke_nachricht(conn, chat_id, message_id, "Bot", 1, "text", text,
                             repo._jetzt())
    except Exception:
        log.exception("Gespraechszug fehlgeschlagen")
        repo.merke_vorfall(conn, chat_id, e.bot_name, "gespraech_fehler",
                           f"bis message_id={letzte_id}")
        try:
            tg.sende(chat_id, "Bei mir hakt gerade etwas - fragt nochmal.")
        except Exception:
            log.exception("Fehlermeldung konnte nicht zugestellt werden")
    finally:
        # In jedem Fall vorruecken. Ein Zug, der scheitert, darf nicht ewig
        # wiederholt werden - die Gruppe fragt selbst nach.
        repo.setze_beantwortet_bis(conn, chat_id, letzte_id)


def bearbeite(conn, tg, klm, e, chat_id: int) -> None:
    """Ein Zug zur Zeit je Gruppe. Nachzuegler werden gesammelt statt parallel
    beantwortet (SPEC 1.3)."""
    while True:
        sperre = _sperre_fuer(chat_id)
        if not sperre.acquire(blocking=False):
            return  # laeuft schon; der laufende Zug nimmt die Nachricht mit
        try:
            offen = repo.unbeantwortete(conn, chat_id)
            if not offen:
                return
            antworte(conn, tg, klm, e, chat_id, offen)
        finally:
            sperre.release()
```

> **Warum die äussere `while`-Schleife.** Ohne sie gäbe es ein Zeitfenster: Eine Nachricht, die eintrifft, nachdem der laufende Zug `unbeantwortete` abgefragt hat, aber bevor er die Sperre freigibt, würde liegenbleiben — ihr eigener `bearbeite`-Aufruf lief ins `return`. Mit der Schleife greift der Zug nach dem Freigeben erneut zu und findet sie. Keine Rekursion, kein verlorener Beitrag.

- [ ] **Schritt 4: `bot.py` erweitern**

In `theatersoap/bot.py`:

```python
from concurrent.futures import ThreadPoolExecutor

from theatersoap import ablauf, llm as llm_modul, verdichter
```

`verarbeite_update` liefert jetzt die normalisierte Nachricht statt nur der `chat_id`:

```python
def verarbeite_update(conn, tg, e, update, jetzt, beim_start):
    n = telegram.lies_nachricht(update)
    if not n or n["chat_id"] is None:
        return None
    n["antwortet_auf_bot"] = bool(
        ((update.get("message") or {}).get("reply_to_message") or {})
        .get("from", {}).get("is_bot")
    )
    repo.sichere_gruppe(conn, n["chat_id"], e.bot_name, n["chat_titel"])
    unterdrueckt = 1 if (beim_start and ist_nachtstau(n["gesendet_am"], jetzt)) else 0
    neu = repo.merke_nachricht(
        conn, n["chat_id"], n["message_id"], n["absender"], 0, n["typ"],
        n["text"], n["gesendet_am"], unterdrueckt=unterdrueckt,
    )
    if not neu or unterdrueckt:
        return None
    return n
```

In der Schleife statt der Protokollzeile:

```python
n = verarbeite_update(conn, tg, e, update, jetzt, beim_start)
if n is None:
    continue
if n["typ"] == "sprache":
    pool.submit(verdichter.pipeline, conn, tg, klm, e, klient,
                n["chat_id"], n["message_id"], n["file_id"])
elif ablauf.ist_ausloeser(n, e.bot_name, repo.hole_gruppe(conn, n["chat_id"])):
    pool.submit(ablauf.bearbeite, conn, tg, klm, e, n["chat_id"])
```

`main()`:

```python
def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    e = einstellungen.laden()
    conn = db.verbinde(e.db_pfad)
    conn.execute("PRAGMA busy_timeout = 5000")
    db.initialisiere(conn)
    klient = httpx.Client()
    tg = telegram.Telegram(e.bot_token, klient)
    klm = llm_modul.LLM(e, klient, conn)
    pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ts")
    log.info("Bot %s gestartet", e.bot_name)
    verdichter.greife_offene_auf(conn, tg, klm, e, klient)
    schleife(conn, tg, klm, e, klient, pool)
```

> **SQLite über Threads.** Die Verbindung wird mit `sqlite3.connect(..., check_same_thread=False)` geöffnet (in `db.verbinde` ergänzen) und alle Schreibvorgänge sind kurze, sofort committete Anweisungen. Mit WAL und `busy_timeout=5000` ist das für vier Arbeitsfäden je Prozess tragfähig. Eine Verbindung je Faden wäre sauberer, ist aber mehr Maschinerie als der Fall hergibt — und `busy_timeout` fängt genau die Kollision ab, um die es geht.

- [ ] **Schritt 5: Test laufen lassen**

Run: `python -m pytest tests/test_ablauf.py -v`
Expected: PASS, 9 Tests

- [ ] **Schritt 6: Gesamtlauf**

Run: `python -m pytest -v`
Expected: PASS, alle Tests aus Aufgaben 1–10

**Fertigstellungsbedingung des Durchstichs:** Alle Tests bestehen, und ein Trockenlauf gegen echte Dienste funktioniert:

```bash
export TS_BOT_TOKEN=... TS_BOT_NAME=gruppe1 TS_DB=./theatersoap.db \
       TS_AUDIO=./audio TS_LLM_URL=... TS_LLM_KEY=... TS_LLM_MODELL=... TS_STT_URL=...
python -m theatersoap.bot
```

Im Telegram-Gruppenchat nachweisbar:
1. `@botname hallo` → der Bot antwortet.
2. Eine Sprachnachricht → Empfangsbestätigung, dann liegt in `interview` eine Zeile mit `status='verdichtet'` und in `verdichtung_thema` mindestens ein Thema.
3. `ich hol mir Kaffee` (ohne Erwähnung) → der Bot antwortet **nicht**, die Zeile steht aber in `nachricht`.
4. Prozess mit `Strg+C` beenden, neu starten, `@botname und weiter?` → der Bot kennt den bisherigen Verlauf.

- [ ] **Schritt 7: Commit**

```bash
git add theatersoap/ablauf.py theatersoap/bot.py tests/test_ablauf.py
git commit -m "Gespraechszug mit Sperre, Sammeln und Tippanzeige - Durchstich steht"
```

---

# TEIL B — Ausbau

Ab hier läuft der Bot bereits. Jede Aufgabe ist einzeln nutzbar; bricht die Zeit weg, ist die Reihenfolge unten die Rangfolge nach Nutzen.

---

## Aufgabe 11: Extraktor und Journal

**Files:**
- Create: `theatersoap/extraktor.py`, `theatersoap/prompts/extraktor.md`
- Modify: `theatersoap/repo.py`, `theatersoap/ablauf.py`
- Test: `tests/test_extraktor.py`

**Interfaces:**
- Produces (in `repo.py`):
  - `repo.unextrahierte(conn, chat_id) -> list[sqlite3.Row]`
  - `repo.setze_extrahiert_bis(conn, chat_id, message_id) -> None`
- Produces (in `extraktor.py`):
  - `extraktor.SCHEMA: dict`, `extraktor.DECKEL = 4000`, `extraktor.SCHWELLE = 1500`
  - `extraktor.laufe(conn, klm, e, chat_id) -> None`

- [ ] **Schritt 1: Prompt schreiben**

`theatersoap/prompts/extraktor.md`:

```markdown
Du liest einen Ausschnitt aus dem Gruppenchat einer Theatergruppe und haeltst fest,
was darin an Arbeitsstand entstanden ist.

Kategorien:
- vorgeschlagen: etwas wurde in den Raum gestellt, ohne Entscheidung
- verworfen: etwas wurde ausdruecklich abgelehnt
- entschieden: die Gruppe hat sich festgelegt
- offen: eine Frage steht im Raum

WICHTIG: Meistens ist nichts davon passiert. Eine leere Liste ist der Normalfall
und die richtige Antwort. Erfinde keine Bedeutung in Alltagsgeplauder hinein.
"Ich hol mir Kaffee" ist kein Eintrag.

Jeder Eintrag ist eine knappe Zeile, hoechstens 15 Woerter.
Antworte ausschliesslich im vorgegebenen JSON-Schema.
```

- [ ] **Schritt 2: Den fehlschlagenden Test schreiben**

`tests/test_extraktor.py`:

```python
import pytest
from theatersoap import db, extraktor, repo


class LLMAttrappe:
    def __init__(self, ergebnis=None, kaputt=False):
        self.ergebnis = ergebnis or {"eintraege": []}
        self.kaputt = kaputt
        self.aufrufe = 0

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe += 1
        if self.kaputt:
            raise RuntimeError("ungueltiges JSON")
        return self.ergebnis


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "G")
    return c


def fuelle(conn, anzahl, laenge=20, ab=1):
    for i in range(anzahl):
        repo.merke_nachricht(conn, 1, ab + i, "Ada", 0, "text", "x" * laenge,
                             "2026-09-05T12:00:00+00:00")


def test_eintraege_landen_im_journal(conn, einst):
    fuelle(conn, 3)
    klm = LLMAttrappe({"eintraege": [
        {"art": "verworfen", "text": "Kindheitsfragen - zu privat"}]})
    extraktor.laufe(conn, klm, einst, 1)
    eintraege = repo.journal(conn, 1)
    assert len(eintraege) == 1
    assert eintraege[0]["art"] == "verworfen"
    assert eintraege[0]["quelle"] == "extraktor"


def test_leere_liste_ist_kein_fehler(conn, einst):
    fuelle(conn, 3)
    extraktor.laufe(conn, LLMAttrappe(), einst, 1)
    assert repo.journal(conn, 1) == []
    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 3


def test_fehlschlag_laesst_das_wasserzeichen_stehen(conn, einst):
    fuelle(conn, 3)
    extraktor.laufe(conn, LLMAttrappe(kaputt=True), einst, 1)
    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 0, \
        "das Fenster wird beim naechsten Mal mitgelesen"
    assert conn.execute(
        "SELECT count(*) FROM vorfall WHERE art = 'extraktor_fehler'"
    ).fetchone()[0] == 1


def test_deckel_verwirft_das_fenster_und_meldet_es(conn, einst):
    fuelle(conn, 200, laenge=100)   # weit ueber 4000 Token
    extraktor.laufe(conn, LLMAttrappe(kaputt=True), einst, 1)
    assert repo.hole_gruppe(conn, 1)["letzte_extrahierte_message_id"] == 200, \
        "Wasserzeichen wird trotzdem vorgerueckt"
    assert conn.execute(
        "SELECT count(*) FROM vorfall WHERE art = 'fenster_verworfen'"
    ).fetchone()[0] == 1


def test_nichts_zu_tun_ruft_das_modell_nicht_auf(conn, einst):
    klm = LLMAttrappe()
    extraktor.laufe(conn, klm, einst, 1)
    assert klm.aufrufe == 0
```

- [ ] **Schritt 3: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_extraktor.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.extraktor'`

- [ ] **Schritt 4: Repository-Abfragen anhängen**

```python
def unextrahierte(conn, chat_id) -> list:
    return list(conn.execute(
        "SELECT n.* FROM nachricht n JOIN gruppe g ON g.chat_id = n.chat_id "
        "WHERE n.chat_id = ? AND n.message_id > g.letzte_extrahierte_message_id "
        "ORDER BY n.message_id",
        (chat_id,),
    ))


def setze_extrahiert_bis(conn, chat_id, message_id) -> None:
    conn.execute(
        "UPDATE gruppe SET letzte_extrahierte_message_id = ? "
        "WHERE chat_id = ? AND letzte_extrahierte_message_id < ?",
        (message_id, chat_id, message_id),
    )
    conn.commit()
```

- [ ] **Schritt 5: `extraktor.py` schreiben**

```python
"""Nachgelagerter Extraktor (SPEC 4.3). Laeuft ins Leere: Fehlschlag bleibt folgenlos."""
import logging
from pathlib import Path

from theatersoap import kontext, repo

log = logging.getLogger("theatersoap.extraktor")

PROMPT = (Path(__file__).parent / "prompts" / "extraktor.md").read_text(encoding="utf-8")

SCHWELLE = 1500   # Zusatzausloeser, wenn die Gruppe lange unter sich redet
DECKEL = 4000     # darueber wird das Fenster fallengelassen

SCHEMA = {
    "type": "object",
    "properties": {
        "eintraege": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "art": {"type": "string",
                            "enum": ["vorgeschlagen", "verworfen", "entschieden", "offen"]},
                    "text": {"type": "string"},
                },
                "required": ["art", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["eintraege"],
    "additionalProperties": False,
}


def laufe(conn, klm, e, chat_id: int) -> None:
    offen = repo.unextrahierte(conn, chat_id)
    if not offen:
        return

    fenster = "\n".join(kontext.sprecherzeile(n) for n in offen)
    letzte_id = offen[-1]["message_id"]

    if kontext.schaetze(fenster) > DECKEL:
        repo.setze_extrahiert_bis(conn, chat_id, letzte_id)
        repo.merke_vorfall(conn, chat_id, e.bot_name, "fenster_verworfen",
                           f"{kontext.schaetze(fenster)} Token, bis {letzte_id}")
        return

    try:
        ergebnis = klm.schema(chat_id, PROMPT, fenster, SCHEMA, "extraktor")
    except Exception as fehler:
        # Wasserzeichen bleibt stehen: kostenloser Wiederholungsversuch beim
        # naechsten Mal, ohne eigene Retry-Logik (SPEC 4.3).
        log.warning("Extraktor fehlgeschlagen: %s", fehler)
        repo.merke_vorfall(conn, chat_id, e.bot_name, "extraktor_fehler", str(fehler))
        return

    for eintrag in ergebnis.get("eintraege", []):
        repo.schreibe_journal(conn, chat_id, eintrag["art"], eintrag["text"],
                              "extraktor", bis_message_id=letzte_id)
    repo.setze_extrahiert_bis(conn, chat_id, letzte_id)
```

> **Vorher in `kontext.py` herausziehen.** Die Sprecherzeile wird jetzt an zwei Stellen
> gebraucht. Ersetze die Formatierung in `kontext._fenster` durch einen Aufruf dieser
> Funktion, damit die beiden Stellen nicht auseinanderdriften:
> ```python
> def sprecherzeile(n) -> str:
>     sprecher = "Du" if n["ist_bot"] else n["absender"]
>     inhalt = n["text"] or f"({n['typ']})"
>     return f"{sprecher}: {inhalt}"
> ```

- [ ] **Schritt 6: Extraktor in `ablauf.antworte` einhängen**

Am Ende von `antworte`, **nach** dem `finally`-Block, im Hintergrund-Pool:

```python
# in bot.py, wo der Zug abgeschickt wird:
def zug_und_nachlauf(conn, tg, klm, e, chat_id):
    ablauf.bearbeite(conn, tg, klm, e, chat_id)
    try:
        extraktor.laufe(conn, klm, e, chat_id)
    except Exception:
        log.exception("Extraktor-Nachlauf gescheitert")

pool.submit(zug_und_nachlauf, conn, tg, klm, e, n["chat_id"])
```

Zusätzlich der Schwellwert-Auslöser: In der Polling-Schleife nach jedem Update, das **keinen** Zug ausgelöst hat:

```python
else:
    offen = repo.unextrahierte(conn, n["chat_id"])
    text = "".join(x["text"] or "" for x in offen)
    if kontext.schaetze(text) > extraktor.SCHWELLE:
        pool.submit(extraktor.laufe, conn, klm, e, n["chat_id"])
```

- [ ] **Schritt 7: Test laufen lassen**

Run: `python -m pytest tests/test_extraktor.py -v`
Expected: PASS, 5 Tests

**Fertigstellungsbedingung:** Fünf Tests bestehen. Belegt sind: leere Liste ist der Normalfall, Fehlschlag lässt das Wasserzeichen stehen (kostenlose Wiederholung), der 4000-Token-Deckel rückt trotzdem vor und schreibt einen **sichtbaren** Vorfall, und ohne neue Nachrichten wird das Modell gar nicht erst gerufen.

- [ ] **Schritt 8: Commit**

```bash
git add theatersoap/extraktor.py theatersoap/prompts/extraktor.md theatersoap/repo.py theatersoap/bot.py tests/test_extraktor.py
git commit -m "Extraktor mit Wasserzeichen, Deckel und Journalschreibung"
```

---

## Aufgabe 12: Befehle und Schreibpfad in den Arbeitsstand

> **Entwurfsentscheidung, die hier festgelegt wird.** Die Spec sagt nicht, wie ein
> Modellvorschlag zu einem bestätigten Feld in `arbeitsstand`, `figur` oder `szene` wird.
> Dieser Plan entscheidet: **Befehle schreiben den Arbeitsstand, das Modell nie.**
> Der Grund ist die Fehlerrichtung. Schriebe das Modell selbst, füllte sich der Arbeitsstand
> mit unbestätigten Entwürfen, und die Gruppe müsste gegen ihren eigenen Bot anarbeiten — die
> Kernthema-Zeile stünde falsch in jedem folgenden Prompt. Ein Befehl ist zwar Zeremonie, aber
> das Setzen des Kernthemas *ist* ein zeremonieller Moment: die Gruppe hat sich gerade
> geeinigt. Das unterscheidet ihn von `/merken`, das im Fluss stört.
> Das Sicherheitsnetz für nicht getippte Entscheidungen ist der Extraktor: er schreibt
> `entschieden`-Einträge ins Journal, auch wenn niemand einen Befehl eingibt.

**Files:**
- Create: `theatersoap/befehle.py`
- Modify: `theatersoap/ablauf.py` (Befehle vor dem LLM-Aufruf abfangen)
- Test: `tests/test_befehle.py`

**Interfaces:**
- Produces: `befehle.behandle(conn, tg, e, chat_id, text: str, absender: str) -> bool` — `True`, wenn der Text ein Befehl war und behandelt wurde (dann kein LLM-Aufruf)

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_befehle.py`:

```python
import pytest
from theatersoap import befehle, db, repo


class TGAttrappe:
    def __init__(self):
        self.gesendet = []
        self._id = 700

    def sende(self, chat_id, text):
        self._id += 1
        self.gesendet.append(text)
        return self._id


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "G")
    return c


def test_kein_befehl_wird_durchgelassen(conn, einst):
    assert befehle.behandle(conn, TGAttrappe(), einst, 1, "was meinst du?", "Ada") is False


def test_merken_schreibt_ins_journal(conn, einst):
    assert befehle.behandle(conn, TGAttrappe(), einst, 1,
                            "/merken Kernthema ist Ankommen", "Ada") is True
    eintrag = repo.journal(conn, 1)[0]
    assert eintrag["art"] == "entschieden"
    assert eintrag["quelle"] == "befehl"


def test_verworfen_schreibt_die_andere_kategorie(conn, einst):
    befehle.behandle(conn, TGAttrappe(), einst, 1, "/verworfen Kindheitsfragen", "Ada")
    assert repo.journal(conn, 1)[0]["art"] == "verworfen"


def test_kernthema_setzt_den_arbeitsstand(conn, einst):
    befehle.behandle(conn, TGAttrappe(), einst, 1, "/kernthema Ankommen", "Ada")
    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Ankommen"


def test_wortlaut_ist_klebrig_und_ueberlebt(conn, einst):
    befehle.behandle(conn, TGAttrappe(), einst, 1, "/wortlaut", "Ada")
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] == "*"
    befehle.behandle(conn, TGAttrappe(), einst, 1, "/wortlaut aus", "Ada")
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] is None


def test_wortlaut_mit_unbekanntem_namen_zaehlt_die_namen_auf(conn, einst):
    iid = repo.lege_interview_an(conn, 1, 10, "/tmp/a.ogg")
    repo.setze_interview_transkript(conn, iid, "text")
    repo.setze_interview_name(conn, iid, "Maria")
    tg = TGAttrappe()
    befehle.behandle(conn, tg, einst, 1, "/wortlaut Peter", "Ada")
    assert "Maria" in tg.gesendet[0]
    assert repo.hole_gruppe(conn, 1)["wortlaut_modus"] is None


def test_gruendlich_ist_einmalig(conn, einst):
    befehle.behandle(conn, TGAttrappe(), einst, 1, "/gruendlich", "Ada")
    assert repo.hole_gruppe(conn, 1)["gruendlich_naechster_zug"] == 1


def test_stand_antwortet_ohne_llm(conn, einst):
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    tg = TGAttrappe()
    befehle.behandle(conn, tg, einst, 1, "/stand", "Ada")
    assert "Ankommen" in tg.gesendet[0]
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_befehle.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'theatersoap.befehle'`

- [ ] **Schritt 3: `befehle.py` schreiben**

```python
"""Slash-Befehle (SPEC 8). Kein LLM-Aufruf, nichts davon kann fehlschlagen."""
from theatersoap import repo

HILFE = (
    "So erreichst du mich: antworte auf eine meiner Nachrichten, schreib @{bot} "
    "davor, oder schick eine Sprachnachricht.\n\n"
    "/merken <text> - Entscheidung festhalten\n"
    "/verworfen <text> - festhalten, was wir verworfen haben\n"
    "/kernthema <text> - Kernthema setzen\n"
    "/konflikt <text> - Hauptkonflikt setzen\n"
    "/begriffe <text> - eure Begriffe setzen\n"
    "/figur <name>: <beschreibung> - Figur anlegen\n"
    "/szene <titel>: <kurzbeschreibung> - Szene anlegen\n"
    "/wortlaut [name|aus] - Originaltranskripte mitlesen\n"
    "/gruendlich - ich nehme mir fuer den naechsten Zug mehr Zeit\n"
    "/stand - aktueller Arbeitsstand\n"
    "/hilfe - diese Uebersicht"
)


def _stand(conn, chat_id) -> str:
    a = repo.hole_arbeitsstand(conn, chat_id)
    zeilen = []
    if a:
        for feld, titel in (("begriffe", "Begriffe"), ("kernthema", "Kernthema"),
                            ("kernthema_begruendung", "Begruendung"),
                            ("hauptkonflikt", "Hauptkonflikt")):
            if a[feld]:
                zeilen.append(f"{titel}: {a[feld]}")
    for f in repo.figuren(conn, chat_id):
        zeilen.append(f"Figur {f['name']}: {f['beschreibung'] or ''}")
    for s in repo.szenen(conn, chat_id):
        zeilen.append(f"Szene {s['nummer']}. {s['titel']}")
    interviews = repo.verdichtungen(conn, chat_id)
    if interviews:
        zeilen.append("Interviews: " + ", ".join(i["name"] for i in interviews))
    return "\n".join(zeilen) if zeilen else "Noch nichts festgehalten."


def _wortlaut(conn, tg, chat_id, rest: str) -> None:
    if rest.lower() in ("aus", "off"):
        conn.execute("UPDATE gruppe SET wortlaut_modus = NULL WHERE chat_id = ?",
                     (chat_id,))
        conn.commit()
        tg.sende(chat_id, "Gut, ich lese die Transkripte nicht mehr mit.")
        return
    if not rest:
        conn.execute("UPDATE gruppe SET wortlaut_modus = '*' WHERE chat_id = ?",
                     (chat_id,))
        conn.commit()
        tg.sende(chat_id, "Ich lese ab jetzt alle Originaltranskripte mit.")
        return
    treffer = repo.transkripte(conn, chat_id, rest)
    if not treffer:
        namen = [i["name"] for i in repo.transkripte(conn, chat_id)]
        tg.sende(chat_id, "Den Namen kenne ich nicht. Ich habe: "
                          + (", ".join(namen) if namen else "noch keine Interviews"))
        return
    conn.execute("UPDATE gruppe SET wortlaut_modus = ? WHERE chat_id = ?",
                 (rest, chat_id))
    conn.commit()
    tg.sende(chat_id, f"Ich lese ab jetzt das Transkript von {treffer[0]['name']} mit.")


def behandle(conn, tg, e, chat_id: int, text: str, absender: str) -> bool:
    text = (text or "").strip()
    if not text.startswith("/"):
        return False
    teile = text[1:].split(maxsplit=1)
    befehl = teile[0].split("@")[0].lower()
    rest = teile[1].strip() if len(teile) > 1 else ""

    if befehl == "merken" and rest:
        repo.schreibe_journal(conn, chat_id, "entschieden", rest, "befehl")
        tg.sende(chat_id, "Festgehalten.")
    elif befehl == "verworfen" and rest:
        repo.schreibe_journal(conn, chat_id, "verworfen", rest, "befehl")
        tg.sende(chat_id, "Notiert, dass ihr das verworfen habt.")
    elif befehl == "kernthema" and rest:
        repo.setze_arbeitsstand(conn, chat_id, "kernthema", rest)
        repo.schreibe_journal(conn, chat_id, "entschieden", f"Kernthema: {rest}", "befehl")
        tg.sende(chat_id, f"Kernthema gesetzt: {rest}")
    elif befehl == "konflikt" and rest:
        repo.setze_arbeitsstand(conn, chat_id, "hauptkonflikt", rest)
        tg.sende(chat_id, f"Hauptkonflikt gesetzt: {rest}")
    elif befehl == "begriffe" and rest:
        repo.setze_arbeitsstand(conn, chat_id, "begriffe", rest)
        tg.sende(chat_id, f"Begriffe gesetzt: {rest}")
    elif befehl == "figur" and rest:
        name, _, beschreibung = rest.partition(":")
        repo.lege_figur_an(conn, chat_id, name.strip(), beschreibung.strip())
        tg.sende(chat_id, f"Figur {name.strip()} angelegt.")
    elif befehl == "szene" and rest:
        titel, _, kurz = rest.partition(":")
        repo.lege_szene_an(conn, chat_id, titel.strip(), kurz.strip())
        tg.sende(chat_id, f"Szene {titel.strip()} angelegt.")
    elif befehl == "wortlaut":
        _wortlaut(conn, tg, chat_id, rest)
    elif befehl == "gruendlich":
        conn.execute("UPDATE gruppe SET gruendlich_naechster_zug = 1 WHERE chat_id = ?",
                     (chat_id,))
        conn.commit()
        tg.sende(chat_id, "Gut - fuer den naechsten Zug nehme ich mir mehr Zeit. "
                          "Das dauert dann etwa eine halbe Minute.")
    elif befehl == "stand":
        tg.sende(chat_id, _stand(conn, chat_id))
    elif befehl == "hilfe":
        tg.sende(chat_id, HILFE.format(bot=e.bot_name))
    else:
        tg.sende(chat_id, "Den Befehl kenne ich nicht. /hilfe zeigt alle.")
    return True
```

- [ ] **Schritt 4: In `ablauf.antworte` einhängen**

Ganz am Anfang von `antworte`, vor dem Kontext-Zusammenbau:

```python
if len(ausloeser) == 1 and befehle.behandle(
    conn, tg, e, chat_id, ausloeser[0]["text"] or "", ausloeser[0]["absender"]
):
    repo.setze_beantwortet_bis(conn, chat_id, ausloeser[0]["message_id"])
    return
```

Und der Modus-B-Zweig im selben `antworte`:

```python
gruppe = repo.hole_gruppe(conn, chat_id)
if gruppe["gruendlich_naechster_zug"]:
    conn.execute("UPDATE gruppe SET gruendlich_naechster_zug = 0 WHERE chat_id = ?",
                 (chat_id,))
    conn.commit()
    tg.sende(chat_id, "Ich nehme mir dafuer mehr Zeit - das dauert etwa eine halbe Minute.")
    with _Tippanzeige(tg, chat_id):
        text = klm.prosa(chat_id, kontext.SYSTEM, nutzer, "gespraech")
else:
    with _Tippanzeige(tg, chat_id):
        ergebnis = klm.schema(chat_id, kontext.SYSTEM, nutzer, ANTWORT_SCHEMA, "gespraech")
        text = (ergebnis.get("antwort") or "").strip()
```

- [ ] **Schritt 5: Test laufen lassen**

Run: `python -m pytest tests/test_befehle.py -v`
Expected: PASS, 8 Tests

**Fertigstellungsbedingung:** Acht Tests bestehen. Belegt sind: normale Nachrichten werden durchgelassen, `/merken` und `/verworfen` schreiben verschiedene Kategorien, `/kernthema` schreibt den Arbeitsstand, `/wortlaut` ist klebrig und zählt bei unbekanntem Namen die vorhandenen auf statt zu raten, `/gruendlich` ist einmalig, `/stand` antwortet ohne LLM.

- [ ] **Schritt 6: Commit**

```bash
git add theatersoap/befehle.py theatersoap/ablauf.py tests/test_befehle.py
git commit -m "Befehle inklusive Schreibpfad in den Arbeitsstand und Modus B"
```

---

## Aufgabe 13: Rückfrage-Sequenz und Interview-Benennung

**Files:**
- Modify: `theatersoap/repo.py`, `theatersoap/ablauf.py`, `theatersoap/verdichter.py`
- Test: `tests/test_rueckfrage.py`

**Interfaces:**
- Produces (in `repo.py`):
  - `repo.setze_rueckfrage(conn, chat_id, art: str, kontext_id: int) -> None`
  - `repo.loesche_rueckfrage(conn, chat_id) -> None`
  - `repo.offene_rueckfrage(conn, chat_id, jetzt: datetime) -> sqlite3.Row | None` — liefert `None`, wenn älter als 10 Minuten
- Produces (in `ablauf.py`): Erweiterung von `ist_ausloeser` um die Sequenz

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_rueckfrage.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest
from theatersoap import ablauf, db, repo

JETZT = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "G")
    return c


def test_offene_rueckfrage_macht_die_naechste_nachricht_zum_ausloeser(conn):
    repo.setze_rueckfrage(conn, 1, "interview_name", 5)
    n = {"typ": "text", "text": "Maria", "antwortet_auf_bot": False, "message_id": 2}
    assert ablauf.ist_ausloeser(n, "meinbot", repo.hole_gruppe(conn, 1)) is True


def test_rueckfrage_verfaellt_nach_zehn_minuten(conn):
    repo.setze_rueckfrage(conn, 1, "interview_name", 5)
    conn.execute(
        "UPDATE gruppe SET rueckfrage_gestellt_am = ? WHERE chat_id = ?",
        ((JETZT - timedelta(minutes=11)).isoformat(), 1),
    )
    conn.commit()
    assert repo.offene_rueckfrage(conn, 1, JETZT) is None


def test_rueckfrage_gilt_kurz_davor_noch(conn):
    repo.setze_rueckfrage(conn, 1, "interview_name", 5)
    conn.execute(
        "UPDATE gruppe SET rueckfrage_gestellt_am = ? WHERE chat_id = ?",
        ((JETZT - timedelta(minutes=9)).isoformat(), 1),
    )
    conn.commit()
    assert repo.offene_rueckfrage(conn, 1, JETZT) is not None


def test_befehl_verbraucht_die_sequenz_nicht(conn):
    repo.setze_rueckfrage(conn, 1, "interview_name", 5)
    n = {"typ": "text", "text": "/stand", "antwortet_auf_bot": False, "message_id": 2}
    ablauf.ist_ausloeser(n, "meinbot", repo.hole_gruppe(conn, 1))
    assert repo.hole_gruppe(conn, 1)["offene_rueckfrage"] == "interview_name"


def test_antwort_benennt_das_interview_und_leert_die_sequenz(conn, einst):
    iid = repo.lege_interview_an(conn, 1, 10, "/tmp/a.ogg")
    repo.setze_interview_transkript(conn, iid, "text")
    repo.setze_rueckfrage(conn, 1, "interview_name", iid)

    ablauf.verbrauche_rueckfrage(conn, 1, "Maria", JETZT)

    assert repo.hole_interview(conn, iid)["name"] == "Maria"
    assert repo.hole_gruppe(conn, 1)["offene_rueckfrage"] is None


def test_unsinnige_antwort_leert_die_sequenz_trotzdem(conn, einst):
    """Die Rueckfrage wird nie wiederholt (SPEC 1.4)."""
    iid = repo.lege_interview_an(conn, 1, 10, "/tmp/a.ogg")
    repo.setze_rueckfrage(conn, 1, "interview_name", iid)

    ablauf.verbrauche_rueckfrage(conn, 1, "hahaha wie geil war das denn bitte", JETZT)

    assert repo.hole_interview(conn, iid)["name"] == "Interview 1", "Ersatzname bleibt"
    assert repo.hole_gruppe(conn, 1)["offene_rueckfrage"] is None
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_rueckfrage.py -v`
Expected: FAIL mit `AttributeError: module 'theatersoap.repo' has no attribute 'setze_rueckfrage'`

- [ ] **Schritt 3: Repository-Abfragen anhängen**

```python
from datetime import datetime, timedelta

RUECKFRAGE_VERFALL = timedelta(minutes=10)


def setze_rueckfrage(conn, chat_id, art: str, kontext_id: int) -> None:
    conn.execute(
        "UPDATE gruppe SET offene_rueckfrage = ?, rueckfrage_kontext_id = ?, "
        "rueckfrage_gestellt_am = ? WHERE chat_id = ?",
        (art, kontext_id, _jetzt(), chat_id),
    )
    conn.commit()


def loesche_rueckfrage(conn, chat_id) -> None:
    conn.execute(
        "UPDATE gruppe SET offene_rueckfrage = NULL, rueckfrage_kontext_id = NULL, "
        "rueckfrage_gestellt_am = NULL WHERE chat_id = ?",
        (chat_id,),
    )
    conn.commit()


def offene_rueckfrage(conn, chat_id, jetzt: datetime):
    g = hole_gruppe(conn, chat_id)
    if not g or not g["offene_rueckfrage"] or not g["rueckfrage_gestellt_am"]:
        return None
    if jetzt - datetime.fromisoformat(g["rueckfrage_gestellt_am"]) > RUECKFRAGE_VERFALL:
        return None
    return g
```

- [ ] **Schritt 4: `ablauf.py` erweitern**

```python
import re
from datetime import datetime, timezone

# Ein plausibler Name: ein bis drei Woerter, keine Satzzeichen, hoechstens 40 Zeichen.
_NAME = re.compile(r"^[^\W\d_][\w'’\-]*(?:\s+[^\W\d_][\w'’\-]*){0,2}$", re.UNICODE)


def ist_ausloeser(n: dict, bot_name: str, gruppe) -> bool:
    if n["typ"] == "sprache":
        return True
    if n.get("antwortet_auf_bot"):
        return True
    text = (n.get("text") or "").strip()
    if text.startswith("/"):
        return True   # Befehle verbrauchen die Sequenz ausdruecklich nicht
    if f"@{bot_name}".lower() in text.lower():
        return True
    # Offene Rueckfrage-Sequenz (SPEC 1.4): nur bei code-initiierten Rueckfragen.
    return bool(gruppe and gruppe["offene_rueckfrage"])


def verbrauche_rueckfrage(conn, chat_id: int, text: str, jetzt: datetime) -> None:
    """Wird genau einmal ausgewertet und danach in jedem Fall geleert.
    Passt die Antwort nicht, bleibt der Ersatzname stehen - kein Nachfassen."""
    g = repo.offene_rueckfrage(conn, chat_id, jetzt)
    if not g:
        repo.loesche_rueckfrage(conn, chat_id)
        return
    try:
        if g["offene_rueckfrage"] == "interview_name":
            kandidat = (text or "").strip().strip(".!?,")
            if len(kandidat) <= 40 and _NAME.match(kandidat):
                repo.setze_interview_name(conn, g["rueckfrage_kontext_id"], kandidat)
    finally:
        repo.loesche_rueckfrage(conn, chat_id)
```

In `antworte`, direkt nach der Befehlsbehandlung:

```python
jetzt = datetime.now(timezone.utc)
if repo.offene_rueckfrage(conn, chat_id, jetzt):
    verbrauche_rueckfrage(conn, chat_id, ausloeser[0]["text"] or "", jetzt)
```

In `verdichter._weiter`, nach `repo.setze_interview_transkript`:

```python
tg.sende(interview["chat_id"], "Aufnahme ist drin. Wer wurde da interviewt?")
repo.setze_rueckfrage(conn, interview["chat_id"], "interview_name", interview_id)
```

- [ ] **Schritt 5: Test laufen lassen**

Run: `python -m pytest tests/test_rueckfrage.py -v`
Expected: PASS, 6 Tests

**Fertigstellungsbedingung:** Sechs Tests bestehen. Belegt sind: die Sequenz macht die nächste Nachricht zum Auslöser, sie verfällt nach genau 10 Minuten, ein Befehl verbraucht sie nicht, und eine unsinnige Antwort leert sie trotzdem — die Rückfrage wird nie wiederholt.

- [ ] **Schritt 6: Commit**

```bash
git add theatersoap/repo.py theatersoap/ablauf.py theatersoap/verdichter.py tests/test_rueckfrage.py
git commit -m "Rueckfrage-Sequenz mit Verfall und Interview-Benennung"
```

---

## Aufgabe 14: Startbegrüßung, Betrieb, Rauchtest

**Files:**
- Modify: `theatersoap/bot.py`
- Create: `scripts/rauchtest.py`, `betrieb/theatersoap@.service`, `README.md`
- Test: `tests/test_start.py`

**Interfaces:**
- Produces: `bot.begruessung_faellig(conn, chat_id, jetzt: datetime) -> bool`
- Produces: `bot.erstkontakt(conn, tg, e, chat_id) -> None` — die allererste Nachricht in einer Gruppe (§ 1.2)

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_start.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest
from theatersoap import bot, db, repo

JETZT = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "G")
    return c


def test_begruessung_nach_langer_pause(conn):
    repo.merke_nachricht(conn, 1, 1, "Ada", 0, "text", "bis morgen",
                         (JETZT - timedelta(hours=18)).isoformat())
    assert bot.begruessung_faellig(conn, 1, JETZT) is True


def test_keine_begruessung_nach_kurzem_absturz(conn):
    repo.merke_nachricht(conn, 1, 1, "Ada", 0, "text", "moment",
                         (JETZT - timedelta(seconds=30)).isoformat())
    assert bot.begruessung_faellig(conn, 1, JETZT) is False


def test_keine_begruessung_ohne_verlauf(conn):
    assert bot.begruessung_faellig(conn, 1, JETZT) is False
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest tests/test_start.py -v`
Expected: FAIL mit `AttributeError: module 'theatersoap.bot' has no attribute 'begruessung_faellig'`

- [ ] **Schritt 3: `bot.py` erweitern**

```python
BEGRUESSUNG_AB = timedelta(hours=2)

ERSTKONTAKT = (
    "Hallo! Ich begleite euch durch die Arbeit an eurem Stueck.\n\n"
    "So erreicht ihr mich: antwortet auf eine meiner Nachrichten, schreibt "
    "@{bot} davor, oder schickt eine Sprachnachricht - die hoere ich immer.\n"
    "Untereinander koennt ihr reden, ohne dass ich dazwischenrede.\n\n"
    "/hilfe zeigt, was ich sonst noch kann."
)


def begruessung_faellig(conn, chat_id: int, jetzt: datetime) -> bool:
    zeile = conn.execute(
        "SELECT max(gesendet_am) AS letzte FROM nachricht WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    if not zeile or not zeile["letzte"]:
        return False
    return jetzt - datetime.fromisoformat(zeile["letzte"]) > BEGRUESSUNG_AB


def erstkontakt(conn, tg, e, chat_id: int) -> None:
    """Die allererste Nachricht in einer Gruppe (SPEC 1.2)."""
    schon_da = conn.execute(
        "SELECT count(*) FROM nachricht WHERE chat_id = ? AND ist_bot = 1", (chat_id,)
    ).fetchone()[0]
    if schon_da:
        return
    text = ERSTKONTAKT.format(bot=e.bot_name)
    message_id = tg.sende(chat_id, text)
    repo.merke_nachricht(conn, chat_id, message_id, "Bot", 1, "text", text,
                         repo._jetzt())
```

In `main()`, nach `greife_offene_auf`, für jede bekannte Gruppe dieses Bots:

```python
jetzt = datetime.now(timezone.utc)
for zeile in conn.execute("SELECT chat_id FROM gruppe WHERE bot_name = ?",
                          (e.bot_name,)):
    if begruessung_faellig(conn, zeile["chat_id"], jetzt):
        tg.sende(zeile["chat_id"], "Guten Morgen - ich bin wieder da. "
                                   "/stand zeigt, wo wir stehen.")
```

Und in `verarbeite_update`, direkt nach `repo.sichere_gruppe`: `erstkontakt(conn, tg, e, n["chat_id"])`.

- [ ] **Schritt 4: Rauchtest schreiben**

`scripts/rauchtest.py` — **vor dem Workshop einmal ausführen.** Er ist der einzige Test, der die echten Dienste anfasst.

```python
"""Ein echter Aufruf gegen Infomaniak und Whisper. Vor dem Workshop ausfuehren."""
import sys
from pathlib import Path

import httpx

from theatersoap import db, einstellungen, llm, stt

TRANSKRIPT = ("Also ich bin 1998 weggegangen, mit dem Zug, morgens um sechs. "
              "Meine Mutter hat nicht gewinkt.")


def main() -> None:
    e = einstellungen.laden()
    conn = db.verbinde(":memory:")
    db.initialisiere(conn)
    klient = httpx.Client()

    from theatersoap import verdichter
    klm = llm.LLM(e, klient, conn)
    ergebnis = klm.schema(0, verdichter.PROMPT, TRANSKRIPT, verdichter.SCHEMA, "rauchtest")
    print("Modus A ok:", ergebnis)

    zeile = conn.execute("SELECT * FROM aufruf").fetchone()
    print(f"geschaetzt {zeile['geschaetzte_token']} / tatsaechlich "
          f"{zeile['tatsaechliche_token']} Token, {zeile['dauer_ms']} ms")
    if zeile["tatsaechliche_token"]:
        print("Divisor waere:", round(
            (len(verdichter.PROMPT) + len(TRANSKRIPT)) / zeile["tatsaechliche_token"], 2))

    if len(sys.argv) > 1:
        pfad = Path(sys.argv[1])
        print("Whisper ok:", stt.transkribiere(e, klient, pfad)[:120])
    else:
        print("Kein Audiopfad uebergeben - Whisper nicht geprueft.")


if __name__ == "__main__":
    main()
```

Run: `python -m scripts.rauchtest ./beispiel.ogg`
Expected: gültiges JSON mit `zusammenfassung` und `kernthemen`, dazu die gemessene Token-Zahl und der daraus errechnete Divisor. **Weicht der Divisor stark von 3 ab, wird `kontext.schaetze` angepasst** (§ 7.1).

- [ ] **Schritt 5: Betrieb**

`betrieb/theatersoap@.service`:

```ini
[Unit]
Description=Theater-Soap-Bot %i
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/theatersoap
EnvironmentFile=/opt/theatersoap/betrieb/%i.env
ExecStart=/opt/theatersoap/.venv/bin/python -m theatersoap.bot
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Je Gruppe eine Datei `betrieb/gruppe1.env` mit den Umgebungsvariablen (nicht im Repo — `.gitignore` deckt `betrieb/*.env` ab; ergänzen). Start: `systemctl enable --now theatersoap@gruppe1`.

`README.md` mit: Voraussetzungen, BotFather-Einstellungen (**Privacy Mode aus**, sonst kommen Sprachnachrichten nie an), Umgebungsvariablen, Start, Rauchtest, Löschweg.

- [ ] **Schritt 6: Gesamtlauf**

Run: `python -m pytest -v`
Expected: PASS, alle Tests

**Fertigstellungsbedingung:** Alle Tests bestehen, `python -m scripts.rauchtest` liefert gültiges JSON von der echten API, und `README.md` nennt ausdrücklich, dass der Privacy Mode bei BotFather ausgeschaltet sein muss.

- [ ] **Schritt 7: Commit**

```bash
git add theatersoap/bot.py scripts/rauchtest.py betrieb/ README.md tests/test_start.py .gitignore
git commit -m "Startbegruessung, Erstkontakt, Rauchtest und Betriebsdateien"
```

---

## Rangfolge, wenn die Zeit knapp wird

Der Workshop ist am 05.09. Falls nicht alles fertig wird, ist dies die Reihenfolge, in der abgeschnitten wird:

1. **Aufgaben 1–10 sind Pflicht.** Ohne sie gibt es keinen Bot.
2. **Aufgabe 14 (Rauchtest) vorziehen**, sobald Aufgabe 5 und 6 stehen. Ein Bot, der am Samstagmorgen zum ersten Mal die echte API sieht, ist kein Bot.
3. **Aufgabe 12 (Befehle)** — ohne sie kann die Gruppe nichts festnageln, und `/stand` fehlt nach der Nacht.
4. **Aufgabe 13 (Rückfrage-Sequenz)** — ohne sie heißen alle Interviews `Interview n`. Ärgerlich, nicht tödlich.
5. **Aufgabe 11 (Extraktor)** — das Journal bleibt leer, der Bot vergisst Verworfenes. Der schmerzhafteste Verzicht inhaltlich, aber der einzige, der nichts kaputtmacht.

---

## Selbstprüfung gegen die Spec

| Spec | Aufgabe |
|---|---|
| § 1.1 Privacy Mode aus, alles roh speichern | 3, 4, 14 (README) |
| § 1.2 Antwort-Auslöser | 10, 13 |
| § 1.3 Sperre und Sammeln, Tippanzeige | 10 |
| § 1.4 Rückfrage-Sequenz, Verfall, nie wiederholen | 13 |
| § 2 Gedächtnisschichten | 8, 9, 11 |
| § 3 Schema, PRAGMAs, chat_id überall | 1, 2 |
| § 4.1 Modus A als Vorgabe | 5, 10 |
| § 4.2 Verdichter mit Belegzitaten | 8 |
| § 4.3 Extraktor, Wasserzeichen, Deckel | 11 |
| § 4.4 Defensives Parsen | 5 |
| § 4.5 Modus B über `/gruendlich` | 12 |
| § 5 Belegzitat-Verifikation | 7, 8 |
| § 6 Zusammenbau, Budgets, Pausenmarkierung | 9 |
| § 7 Schätzung, Kürzungsleiter, Selbstkorrektur | 9, 5, 14 |
| § 8 Befehle | 12 |
| § 9 Neustart, Update-Position, Wiederaufnahme, Löschweg | 1, 4, 8, 14 |
| § 10 Interview-Pipeline | 8 |
| § 11.1/11.2 Fehlerverhalten | 8, 10, 11 |
| § 11.3 max_tokens, finish_reason, 5xx-Backoff | 5, 6 |
| § 12 Divisor nachjustieren | 14 (Rauchtest) |

**Bewusst nicht umgesetzt:** `SEQUENZ_BEI_FRAGEZEICHEN` (§ 12) bleibt aus — der Schalter wäre nur Code ohne Nutzen vor dem Workshop. `usage.prompt_tokens_details` wird nicht gesondert protokolliert; wer Caching prüfen will, liest es aus einer Rohantwort, statt jetzt eine Spalte dafür zu bauen.
