# Interview-Theater-Bot — Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Telegram-Bot, der eine Kleingruppe durch die Entwicklung eines Theaterstücks aus eigenen Interviews begleitet — ein Prozess pro Gruppe, gemeinsame SQLite, Infomaniak für Sprache und Sprachmodell.

**Architecture:** Ein synchroner Polling-Prozess je Gruppe. Der Zustand liegt vollständig in SQLite; der Prompt ist eine Funktion der Datenbank. Alles, was Netz anfasst, läuft in einem kleinen Thread-Pool und darf fehlschlagen, ohne den Gesprächsweg zu blockieren.

**Tech Stack:** Python 3.11 · `httpx` · `sqlite3` (Standardbibliothek) · `pytest` + `httpx.MockTransport`. **Keine weiteren Abhängigkeiten.**

**Grundlage:** `SPEC-kontext-architektur.md`. Paragraphenverweise (§) beziehen sich darauf.

**Vorlagen, aus denen abgeschrieben wird** (nur lesen, nie schreiben):
`/home/birk/projekte/kollektivgedaechtnis/kg/llm.py` und
`/home/birk/projekte/kollektivgedaechtnis/stt_backends/infomaniak_whisper_backend.py`.

---

## Global Constraints

**Datenbank (§ 3)** — bei jedem Verbindungsaufbau `PRAGMA journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`. Jede Tabelle außer `bot_zustand` hat `chat_id` (Grundlage der Löschzusage, per Test erzwungen). `nachricht` hat Primärschlüssel `(chat_id, message_id)`, Einfügen mit `INSERT OR IGNORE`.

**Sprachmodell (§ 4, § 11.3)** — Modus A: erzwungenes JSON-Schema, `reasoning_effort: "none"`. `max_tokens = 9000` bei jedem Aufruf. `finish_reason == "length"` ist ein Fehler plus Vorfall `abgeschnitten`, nie ein leeres Ergebnis. **`reasoning_effort` nur senden, wenn gesetzt** — sonst HTTP 400 bei Modellen, die das Feld nicht kennen. Defensives Parsen: führendes `{{` auf `{`, bei `content: null` auf `message.reasoning` ausweichen. In jedem Schema muss **jedes** Objekt `additionalProperties: false` und ein `required` mit **allen** Eigenschaften haben (Vorlage `strict_schema`). Retry bei 5xx/Timeout: `(0.7, 1.5, 3.0)` s mit Jitter.

**Whisper (§ 11.3 Punkt 5)** — zweistufig: `POST {base}/1/ai/{produkt}/openai/audio/transcriptions` (multipart `file`, `model=whisper`, `language=de`, `response_format=verbose_json`) → `batch_id`; dann `GET {base}/1/ai/{produkt}/results/{batch_id}` alle 0,5 s, bis `status == "success"`. **`data` ist ein JSON-String und muss ein zweites Mal geparst werden.** Abbruch bei `error|failed|aborted|canceled|cancelled`; alles andere heißt weiterwarten. 25 MB Grenze.

**Sprachverarbeitung (§ 10)** — `KURZ_GRENZE_S = 45`, `TIPPANZEIGE_AB_S = 5`, `MELDUNG_AB_S = 12`, `BUDGET_KURZ_S = 45`, `BUDGET_LANG_S = 90`, `NACHHOL_INTERVALL_S = 60`, `MAX_VERSUCHE = 5`. Alle an genau einer Stelle. Werte aus der Messung vom 03.09.2026 (76 Läufe, Median 2,9 s, einziger Ausreißer 8,88 s, kein Lauf über 10 s). **Genau ein sofortiger Wiederholungsversuch** mit neuem Upload; danach bleibt `status = 'empfangen'` für den Nachhol-Arbeiter. **Nicht schneiden** außer wegen der 25-MB-Grenze — Chunking bringt nichts.

**Kontext (§ 6, § 7)** — Schätzung Zeichen ÷ 3. Budgets: System 900 · Verdichtungen 3000 · Transkripte 5000 · Arbeitsstand 1200 · Szene 1500 · Journal 1500 · Fenster 2500 · Auslöser 300. Ziel 10 000, Reißleine 20 000. Kürzung: erst Transkripte ganz raus, dann Fenster von vorn beschneiden. Pausenmarkierung ab 60 Minuten.

**Belegzitate (§ 5)** — normalisieren (Whitespace, Anführungszeichen), Teilstring-Vergleich. Trifft nicht → ohne Zitat ausliefern, Vorfall. Kein Retry, keine Segmentzerlegung.

**Zeitschwellen (§ 9.1)** — Nachtstau: älter als 15 Minuten → `unterdrueckt = 1`. Begrüßung nur bei über 2 Stunden Pause.

**Fehlerhaltung** — Die Gruppe erfährt einen Fehler nur, wenn sie ihn beheben kann oder wartet. Alles andere als `vorfall` ans Dashboard. Jedes Update in `try/except`; eine Ausnahme darf den Prozess nie beenden.

**Konfiguration** — nur Umgebungsvariablen: `IT_BOT_TOKEN`, `IT_BOT_NAME`, `IT_DB`, `IT_AUDIO`, `IT_LLM_URL`, `IT_LLM_KEY`, `IT_LLM_MODELL`, `IT_STT_BASIS`, `IT_STT_PRODUKT`.

---

## Dateistruktur

```
interview_theater/
  einstellungen.py   Umgebungsvariablen, ein Dataclass, keine Logik
  db.py              Verbindung, PRAGMAs, Schema, Löschweg
  repo.py            alle SQL-Abfragen
  telegram.py        HTTP-Wrapper um die Bot-API
  llm.py             Infomaniak-Chat (Vorlage kg/llm.py)
  stt.py             Whisper, zweistufig (Vorlage infomaniak_whisper_backend.py)
  zitat.py           Belegzitat-Prüfung, reine Funktionen
  verdichter.py      Verdichter-Prompt
  aufnahme.py        Pipeline kurz/lang, Nachhol-Arbeiter, Whisper-Ausfall
  kontext.py         Prompt-Zusammenbau, Schätzung, Kürzung
  extraktor.py       Journal + Arbeitsstand + Änderungsmeldung   (Teil B)
  befehle.py         Slash-Befehle                                (Teil B)
  ablauf.py          ein Gesprächszug
  bot.py             Startroutine und Polling-Schleife
  prompts/{system,verdichter,extraktor}.md
scripts/{loeschen,rauchtest}.py
tests/
```

---

## Was gegenüber der ersten Planfassung gestrichen wurde

| Gestrichen | Warum |
|---|---|
| Segmentzerlegung, Reihenfolge- und Abstandsprüfung, Retry bei Zitaten | schützte gegen 1 Vorkommnis in 9 Läufen, konnte selbst falsch ablehnen (§ 5) |
| Fünfstufige Kürzungsleiter | zwei Schritte plus Notbremse reichen (§ 7.2) |
| Rückfrage-Sequenz mit Verfallszeit | Sprachnachrichten lösen ohnehin aus; Zustand, der ablaufen kann (§ 1.4) |
| `/szene`-Befehl, Szenen-Volltextblock | im Durchstich unbenutzt; Szenen entstehen erst in Phase 7/8 |
| `SEQUENZ_BEI_FRAGEZEICHEN` | Schalter ohne Nutzen vor dem Workshop |
| Journal-Beschneidung nach Rang | 40 Einträge sind ~1000 Token, das läuft nie über |
| `/gruendlich` + Modus B im Durchstich | nach Teil B verschoben; bei Sprache als Gesprächsbeitrag ist 34 s ohnehin unattraktiv |
| Eigene Aufgabe für den Verdichter | in die Aufnahme-Pipeline gefaltet |
| `scripts/rauchtest.py` als eigene Aufgabe | in Aufgabe 6 gezogen, damit die echte API früh angefasst wird |

---

# TEIL A — Durchstich

Ziel: Nachricht rein · Sprachnachricht transkribiert (kurz → Gespräch, lang → Material) · Verdichtung · Antwort raus · Zustand überlebt Neustart.

---

## Aufgabe 1: Gerüst, Einstellungen, Datenbank

**Files:** `pyproject.toml`, `.gitignore`, `interview_theater/__init__.py`, `interview_theater/einstellungen.py`, `interview_theater/db.py`, `scripts/loeschen.py`, `tests/test_db.py`

**Produces:**
- `einstellungen.laden() -> Einstellungen` mit `bot_token, bot_name, db_pfad, audio_verz, llm_url, llm_key, llm_modell, stt_basis, stt_produkt`
- `db.verbinde(pfad) -> sqlite3.Connection` (mit `check_same_thread=False`)
- `db.initialisiere(conn)`, `db.loesche_gruppe(conn, chat_id)`, `db.TABELLEN_MIT_CHAT_ID`

- [ ] **Schritt 1:** `pyproject.toml` (`requires-python = ">=3.11"`, `dependencies = ["httpx>=0.27"]`, dev `pytest`), `.gitignore` (`__pycache__/`, `.venv/`, `*.db*`, `audio/`, `betrieb/*.env`).

- [ ] **Schritt 2:** `einstellungen.py` — `@dataclass(frozen=True) Einstellungen`, `laden()` liest die neun Variablen, wirft `RuntimeError` bei fehlender Pflichtvariable. `IT_AUDIO` hat den Vorgabewert `"audio"`, `IT_STT_BASIS` den Vorgabewert `"https://api.infomaniak.com"`.

- [ ] **Schritt 3: Test schreiben** — `tests/test_db.py`:

```python
import pytest
from interview_theater import db


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "test.db"))
    db.initialisiere(c)
    return c


def test_pragmas_sind_gesetzt(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_jede_tabelle_ausser_bot_zustand_hat_chat_id(conn):
    """Grundlage der Loeschzusage: keine Tabelle ohne chat_id."""
    tabellen = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    assert "gruppe" in tabellen
    for tabelle in tabellen:
        if tabelle == "bot_zustand":
            continue
        spalten = [r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")]
        assert "chat_id" in spalten, f"{tabelle} hat kein chat_id"


def test_alle_tabellen_stehen_in_der_loeschliste(conn):
    tabellen = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert tabellen - {"bot_zustand"} == set(db.TABELLEN_MIT_CHAT_ID)


def test_loeschen_raeumt_die_gruppe(conn):
    conn.execute("INSERT INTO gruppe (chat_id, bot_name) VALUES (42, 'g1')")
    conn.execute("INSERT INTO nachricht (chat_id, message_id, typ, gesendet_am) "
                 "VALUES (42, 1, 'text', '2026-09-05T10:00:00')")
    conn.commit()
    db.loesche_gruppe(conn, 42)
    assert conn.execute("SELECT count(*) FROM nachricht").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM gruppe").fetchone()[0] == 0
```

- [ ] **Schritt 4:** Test laufen lassen → FAIL (`ModuleNotFoundError`).

- [ ] **Schritt 5:** `db.py` schreiben. `SCHEMA` **wörtlich aus SPEC § 3.1** übernehmen (alle Tabellen mit `IF NOT EXISTS`), `TABELLEN_MIT_CHAT_ID = ("gruppe","nachricht","aufnahme","verdichtung","verdichtung_thema","arbeitsstand","figur","szene","journal","vorfall","aufruf")`.

```python
def verbinde(pfad: str) -> sqlite3.Connection:
    conn = sqlite3.connect(pfad, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn
```

- [ ] **Schritt 6:** Test laufen lassen → PASS (4 Tests).

- [ ] **Schritt 7:** `scripts/loeschen.py` — nimmt `chat_id`, fragt `[ja/NEIN]`, ruft `db.loesche_gruppe` und entfernt `IT_AUDIO/<chat_id>/`.

**Fertigstellungsbedingung:** `python -m pytest tests/test_db.py -v` → 4 bestanden, darunter der Test, der jede Tabelle auf `chat_id` prüft.

- [ ] **Schritt 8:** Commit `Projektgeruest, Einstellungen, Datenbankschema und Loeschweg`

---

## Aufgabe 2: Repository-Schicht

**Files:** `interview_theater/repo.py`, `tests/test_repo.py`

**Produces:** `merke_nachricht(conn, chat_id, message_id, absender, ist_bot, typ, text, gesendet_am, unterdrueckt=0) -> bool` · `sichere_gruppe` · `hole_gruppe` · `unbeantwortete` · `setze_beantwortet_bis` · `letzte_nachrichten(conn, chat_id, anzahl=200)` · `hole_update_id` · `setze_update_id` · `merke_vorfall(conn, chat_id, bot_name, art, detail, stufe=None)` · `merke_aufruf(...)` · `_jetzt() -> str`

- [ ] **Schritt 1: Test schreiben** — `tests/test_repo.py`:

```python
import pytest
from interview_theater import db, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def test_nachricht_wird_nicht_doppelt_eingefuegt(conn):
    assert repo.merke_nachricht(conn, 1, 100, "Ada", 0, "text", "hallo", "2026-09-05T10:00:00")
    assert not repo.merke_nachricht(conn, 1, 100, "Ada", 0, "text", "hallo", "2026-09-05T10:00:00")
    assert conn.execute("SELECT count(*) FROM nachricht").fetchone()[0] == 1


def test_unbeantwortete_beachtet_wasserzeichen_und_unterdrueckung(conn):
    repo.merke_nachricht(conn, 1, 10, "Ada", 0, "text", "alt", "2026-09-05T10:00:00")
    repo.merke_nachricht(conn, 1, 11, "Bo", 0, "text", "nacht", "2026-09-05T22:00:00",
                         unterdrueckt=1)
    repo.merke_nachricht(conn, 1, 12, "Cem", 0, "text", "neu", "2026-09-06T12:00:00")
    repo.setze_beantwortet_bis(conn, 1, 10)
    assert [r["message_id"] for r in repo.unbeantwortete(conn, 1)] == [12]


def test_unbeantwortete_ignoriert_bot_nachrichten(conn):
    repo.merke_nachricht(conn, 1, 20, "Bot", 1, "text", "Antwort", "2026-09-05T10:00:00")
    assert repo.unbeantwortete(conn, 1) == []


def test_update_id_ueberlebt_eine_neue_verbindung(conn, tmp_path):
    repo.setze_update_id(conn, "gruppe1", 4711)
    conn.close()
    assert repo.hole_update_id(db.verbinde(str(tmp_path / "t.db")), "gruppe1") == 4711


def test_update_id_ist_null_wenn_unbekannt(conn):
    assert repo.hole_update_id(conn, "nochniegesehen") == 0
```

- [ ] **Schritt 2:** Test laufen lassen → FAIL.
- [ ] **Schritt 3:** `repo.py` schreiben. `unbeantwortete` filtert `ist_bot = 0 AND unterdrueckt = 0 AND message_id > gruppe.letzte_beantwortete_message_id`. `setze_update_id` per `INSERT … ON CONFLICT(bot_name) DO UPDATE`. Nach jedem Schreibvorgang `conn.commit()`.
- [ ] **Schritt 4:** Test laufen lassen → PASS (5 Tests).

**Fertigstellungsbedingung:** 5 Tests bestehen; belegt ist, dass unterdrückte Nachtnachrichten keinen Zug auslösen.

- [ ] **Schritt 5:** Commit `Repository-Schicht mit Wasserzeichen und Update-Position`

---

## Aufgabe 3: Telegram-Wrapper

**Files:** `interview_theater/telegram.py`, `tests/test_telegram.py`, `tests/conftest.py`

**Produces:** `Telegram(token, klient)` mit `.hole_updates(offset, timeout=25)`, `.sende(chat_id, text) -> int`, `.tippt(chat_id)`, `.lade_datei(file_id, ziel: Path)` · `lies_nachricht(update) -> dict | None` mit den Schlüsseln `chat_id, chat_titel, message_id, absender, typ, text, file_id, dauer, gesendet_am, antwortet_auf_bot`.

`typ` ∈ `text | sprache | dokument | foto | sticker | sonstiges`. `dauer` ist `voice.duration` in Sekunden, sonst `None`.

- [ ] **Schritt 1: `tests/conftest.py`**

```python
import httpx
import pytest
from interview_theater import einstellungen


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="110416",
    )
```

- [ ] **Schritt 2: Test schreiben** — `tests/test_telegram.py`: `hole_updates` liefert `result`; `sende` liefert `message_id`; `lies_nachricht` erkennt Sprachnachricht **mit `dauer`**, Text, Dokument, Sticker als `sonstiges`/`sticker`, liefert `None` ohne Nachricht, und setzt `antwortet_auf_bot`, wenn `reply_to_message.from.is_bot` gesetzt ist. Alles über `httpx.MockTransport`, **kein Netz**.

```python
def test_lies_nachricht_erkennt_sprachnachricht_mit_dauer():
    update = {"update_id": 1, "message": {
        "message_id": 9, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Ada"},
        "voice": {"file_id": "AwACabc", "duration": 312}}}
    n = telegram.lies_nachricht(update)
    assert n["typ"] == "sprache" and n["file_id"] == "AwACabc" and n["dauer"] == 312
    assert n["chat_id"] == -100 and n["absender"] == "Ada"
```

- [ ] **Schritt 3:** Test → FAIL. **Schritt 4:** `telegram.py` schreiben. **Schritt 5:** Test → PASS.

`lade_datei` macht zwei Aufrufe: `getFile` → `file_path`, dann `GET {BASIS}/file/bot{token}/{file_path}` als Strom in die Zieldatei, `ziel.parent.mkdir(parents=True, exist_ok=True)`.

**Fertigstellungsbedingung:** Alle Tests bestehen ohne Netzzugriff; `dauer` wird aus `voice.duration` übernommen (Grundlage der Klassenunterscheidung § 10.1).

- [ ] **Schritt 6:** Commit `Telegram-Wrapper mit Normalisierung und Sprachdauer`

---

## Aufgabe 4: Polling-Schleife, Update-Position, Nachtstau

**Files:** `interview_theater/bot.py`, `tests/test_bot.py`

**Produces:** `bot.ist_nachtstau(gesendet_am, jetzt) -> bool` · `bot.verarbeite_update(conn, e, update, jetzt, beim_start) -> dict | None` · `bot.schleife(...)` · `bot.main()`

- [ ] **Schritt 1: Test schreiben**

```python
def test_alte_nachricht_beim_start_wird_gespeichert_aber_unterdrueckt(conn, einst):
    alt = JETZT - timedelta(hours=14)
    n = bot.verarbeite_update(conn, einst, bau_update(1, 10, "Idee", alt), JETZT, True)
    zeile = conn.execute("SELECT * FROM nachricht WHERE message_id = 10").fetchone()
    assert zeile["text"] == "Idee", "Nachtnachricht muss gespeichert werden"
    assert zeile["unterdrueckt"] == 1
    assert n is None, "Nachtnachricht darf keinen Zug ausloesen"


def test_ist_nachtstau_zieht_die_grenze_bei_15_minuten():
    assert bot.ist_nachtstau((JETZT - timedelta(minutes=16)).isoformat(), JETZT)
    assert not bot.ist_nachtstau((JETZT - timedelta(minutes=14)).isoformat(), JETZT)


def test_gruppe_wird_beim_ersten_update_angelegt(conn, einst):
    bot.verarbeite_update(conn, einst, bau_update(3, 12, "hallo", JETZT), JETZT, False)
    assert repo.hole_gruppe(conn, -100)["titel"] == "Gruppe 1"
```

- [ ] **Schritt 2:** Test → FAIL. **Schritt 3:** `bot.py` schreiben (Erstfassung, Aufgabe 8/10/13 bauen darauf auf). **Schritt 4:** Test → PASS.

Die Schleife: Offset aus `bot_zustand` lesen, `+1`; je Update `try/except` um die Verarbeitung, `repo.setze_update_id` im `finally` (ein kaputtes Update darf nicht endlos wiederholt werden); `beim_start` nach dem ersten Durchlauf auf `False`.

**Fertigstellungsbedingung:** 3 Tests bestehen; eine 14 Stunden alte Nachricht wird gespeichert, aber nicht beantwortet (§ 9.1).

- [ ] **Schritt 5:** Commit `Polling-Schleife mit persistenter Update-Position und Nachtstau`

---

## Aufgabe 5: LLM-Client

**Vorlage lesen:** `/home/birk/projekte/kollektivgedaechtnis/kg/llm.py`. Abschreiben, nicht neu erfinden.

**Files:** `interview_theater/llm.py`, `tests/test_llm.py`

**Produces:** `LLM(e, klient, conn)` mit `.schema(chat_id, system, nutzer, schema, art) -> dict` und `.prosa(chat_id, system, nutzer, art) -> str` · `erster_json_block(text) -> str` · `inhalt_aus(koerper) -> str | None` · `LLMFehler` · `MAX_TOKENS = 9000` · `WARTEZEITEN = (0.7, 1.5, 3.0)`

- [ ] **Schritt 1: Test schreiben** — acht Tests, alle über `MockTransport`:

```python
def test_doppelte_klammer_wird_repariert(einst, conn)         # content '{{"a": 1}'
def test_inhalt_aus_reasoning_wenn_content_null(einst, conn)
def test_json_block_wird_aus_umgebendem_text_geschnitten(einst, conn)
def test_geschweifte_klammer_im_string_beendet_den_block_nicht()
    # llm.erster_json_block('{"zitat": "sie sagte } und ging"}') == der ganze String
def test_502_wird_wiederholt(einst, conn, monkeypatch)         # sleep gepatcht
def test_finish_reason_length_ist_fehler_und_vorfall(einst, conn)
def test_aufruf_wird_protokolliert(einst, conn)                # usage.prompt_tokens
def test_max_tokens_und_reasoning_effort_im_koerper(einst, conn)
```

- [ ] **Schritt 2:** Test → FAIL.

- [ ] **Schritt 3:** `llm.py` schreiben.

`erster_json_block` zählt Klammern **stringbewusst** (Anführungszeichen und Maskierung überspringen), damit eine geschweifte Klammer in einem Belegzitat den Block nicht vorzeitig beendet.

```python
def inhalt_aus(koerper: dict) -> str | None:
    nachricht = koerper["choices"][0].get("message") or {}
    return nachricht.get("content") or nachricht.get("reasoning")
```

`.schema()` sendet `reasoning_effort: "none"` und `response_format: {"type": "json_schema", "json_schema": {"name": art, "strict": True, "schema": schema}}`; danach `strip()`, `{{`→`{`, `erster_json_block`, `json.loads`. `.prosa()` sendet `reasoning_effort: "medium"` und liefert den Text.

**`reasoning_effort` nur in den Körper, wenn ein Wert gesetzt ist** (Vorlage: sonst HTTP 400).

Jeder Aufruf schreibt in `aufruf`: geschätzte Token (`(len(system)+len(nutzer))//3`), `usage.prompt_tokens`, `usage.completion_tokens`, `finish_reason`, Dauer, Erfolg, Modus — im `finally`, damit auch Fehlschläge protokolliert werden.

- [ ] **Schritt 4:** Test → PASS (8 Tests).

**Fertigstellungsbedingung:** Belegt sind `{{`-Reparatur, Ausweichen auf `reasoning`, Klammer im Zitat, 5xx-Wiederholung, `finish_reason: length` als Vorfall, Protokollierung, `max_tokens ≥ 9000`.

- [ ] **Schritt 5:** Commit `LLM-Client mit defensivem Parsen, Wiederholung und Aufrufprotokoll`

---

## Aufgabe 6: Whisper-Client und Rauchtest

**Vorlage lesen:** `/home/birk/projekte/kollektivgedaechtnis/stt_backends/infomaniak_whisper_backend.py`. **Zweistufig, asynchron** — das ist der Kern dieser Aufgabe.

**Files:** `interview_theater/stt.py`, `scripts/rauchtest.py`, `tests/test_stt.py`

**Produces:** `stt.transkribiere(e, klient, pfad: Path, budget_s: float) -> str` (mit genau einem sofortigen Wiederholungsversuch) · `stt.absenden(...) -> str` (batch_id) · `stt.abholen(...) -> str` · `STTFehler` · `POLL_INTERVALL_S = 0.5` · `MAX_UPLOAD_BYTES = 25*1024*1024`

- [ ] **Schritt 1: Test schreiben**

```python
def test_zweistufiger_weg_liefert_text(einst, tmp_path):
    """POST gibt batch_id, GET wird gepollt, data ist ein JSON-STRING."""
    zustand = {"polls": 0}

    def handler(request):
        if "audio/transcriptions" in request.url.path:
            assert b"testdaten" in request.read()
            return httpx.Response(200, json={"batch_id": "B1"})
        zustand["polls"] += 1
        if zustand["polls"] < 3:
            return httpx.Response(200, json={"status": "processing"})
        return httpx.Response(200, json={
            "status": "success",
            "data": json.dumps({"text": "Ich bin 1998 weggegangen."})})

    datei = tmp_path / "a.ogg"; datei.write_bytes(b"OggS-testdaten")
    klient = httpx.Client(transport=httpx.MockTransport(handler))
    assert stt.transkribiere(einst, klient, datei, 30.0) == "Ich bin 1998 weggegangen."
    assert zustand["polls"] == 3


def test_url_liegt_unter_eins_nicht_unter_zwei(einst, tmp_path):
    """Gemessen: /2/.../openai/v1/ antwortet 404."""
    gesehen = {}
    def handler(request):
        gesehen["pfad"] = request.url.path
        return httpx.Response(200, json={"batch_id": "B1"})
    ...
    assert gesehen["pfad"] == "/1/ai/110416/openai/audio/transcriptions"


def test_abbruchstatus_ist_ein_fehler(einst, tmp_path)      # status "failed" -> STTFehler
def test_unbekannter_status_wird_weiter_gepollt(einst, tmp_path)
def test_zeitbudget_bricht_ab(einst, tmp_path)              # immer "processing" -> STTFehler
def test_zu_grosse_datei_wird_abgelehnt(einst, tmp_path)    # ohne Upload
def test_5xx_beim_absenden_wird_wiederholt(einst, tmp_path)
```

- [ ] **Schritt 2:** Test → FAIL.

- [ ] **Schritt 3:** `stt.py` schreiben.

```python
def absenden(e, klient, pfad: Path, budget_s: float) -> str:
    if pfad.stat().st_size > MAX_UPLOAD_BYTES:
        raise STTFehler(f"{pfad.name} ist groesser als 25 MB")
    url = f"{e.stt_basis.rstrip('/')}/1/ai/{e.stt_produkt}/openai/audio/transcriptions"
    with open(pfad, "rb") as datei:
        antwort = klient.post(
            url, headers={"Authorization": f"Bearer {e.llm_key}"},
            files={"file": (pfad.name, datei, "audio/ogg")},
            data={"model": "whisper", "language": "de",
                  "response_format": "verbose_json"},
            timeout=budget_s)
    ...
    batch_id = (antwort.json() or {}).get("batch_id")
    if not batch_id:
        raise STTFehler("keine batch_id in der Antwort")
    return str(batch_id)


def abholen(e, klient, batch_id: str, budget_s: float) -> str:
    url = f"{e.stt_basis.rstrip('/')}/1/ai/{e.stt_produkt}/results/{batch_id}"
    frist = time.monotonic() + budget_s
    while True:
        koerper = klient.get(url, headers=..., timeout=30.0).json() or {}
        status = str(koerper.get("status", "")).lower()
        if status == "success":
            break
        if status in ("error", "failed", "aborted", "canceled", "cancelled"):
            raise STTFehler(f"Auftrag endete als {status!r}")
        if time.monotonic() >= frist:
            raise STTFehler(f"Auftrag {batch_id} war nach {budget_s}s noch {status!r}")
        time.sleep(POLL_INTERVALL_S)
    daten = koerper.get("data")
    if isinstance(daten, str):
        daten = json.loads(daten)      # gemessen: data ist ein JSON-String
    return str((daten or {}).get("text") or "").strip()
```

`transkribiere` verbindet beides und teilt das Budget: Absenden mit Wiederholung bei 5xx, Abholen mit dem Rest des Budgets. Leerer Text ist ein `STTFehler` — Stille ist kein gültiges Transkript.

- [ ] **Schritt 4:** Test → PASS.

- [ ] **Schritt 5:** `scripts/rauchtest.py` — **einmal gegen die echten Dienste**: ein Modus-A-Aufruf mit dem Verdichter-Schema auf einem eingebauten Beispieltranskript, dazu optional ein Audiopfad als Argument für Whisper. Gibt geschätzte gegen tatsächliche Token aus und errechnet den Divisor.

Run: `python -m scripts.rauchtest ./beispiel.ogg`

**Fertigstellungsbedingung:** Alle Tests bestehen. Der Test `test_url_liegt_unter_eins_nicht_unter_zwei` sichert das Detail, das man laut Vorlage „genau einmal herausfindet". Der Rauchtest läuft gegen die echte API und liefert gültiges JSON.

- [ ] **Schritt 6:** Commit `Whisper-Client, zweistufig und asynchron, plus Rauchtest`

---

## Aufgabe 7: Belegzitat-Prüfung und Verdichter

**Files:** `interview_theater/zitat.py`, `interview_theater/verdichter.py`, `interview_theater/prompts/verdichter.md`, Ergänzungen in `repo.py`, `tests/test_zitat.py`, `tests/test_verdichter.py`

**Produces:**
- `zitat.normalisiere(text) -> str`, `zitat.pruefe(zitat, transkript) -> bool`
- `verdichter.SCHEMA`, `verdichter.PROMPT`, `verdichter.verdichte(klm, conn, e, aufnahme_id) -> int`
- `repo`: `lege_aufnahme_an(conn, chat_id, message_id, klasse, quelle, audio_pfad=None, dauer=None) -> int` · `setze_status(conn, aufnahme_id, status, fehlertext=None)` · `setze_transkript(conn, aufnahme_id, text)` · `setze_aufnahme_name` · `hole_aufnahme` · `offene_aufnahmen(conn)` · `zaehle_aufnahmen(conn, chat_id)` · `speichere_verdichtung(conn, chat_id, aufnahme_id, zusammenfassung, themen) -> int` · `verdichtungen(conn, chat_id)` · `themen_zu(conn, verdichtung_id)` · `transkripte(conn, chat_id, name=None)`

- [ ] **Schritt 1: `tests/test_zitat.py` schreiben** — sechs Tests:

```python
def test_woertliches_zitat_besteht()
def test_typografische_anfuehrungszeichen_stoeren_nicht()   # „…“ und »…«
def test_mehrfache_leerzeichen_und_zeilenumbrueche_stoeren_nicht()
def test_erfundenes_zitat_faellt_durch()
def test_leeres_zitat_faellt_durch()
def test_zitat_mit_auslassung_faellt_durch_ohne_sonderbehandlung()
    # "A [...] B" wird NICHT zerlegt: kommt der String so nicht vor, ist er ungueltig
```

- [ ] **Schritt 2:** Test → FAIL. **Schritt 3:** `zitat.py` schreiben — rund zwanzig Zeilen:

```python
_ERSETZUNGEN = str.maketrans({"„": '"', "“": '"', "”": '"', "»": '"', "«": '"',
                              "‚": "'", "‘": "'", "’": "'", " ": " "})


def normalisiere(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").translate(_ERSETZUNGEN)
    return re.sub(r"\s+", " ", text).strip()


def pruefe(zitat: str, transkript: str) -> bool:
    z, t = normalisiere(zitat).strip('"\''), normalisiere(transkript)
    return bool(z) and bool(t) and z in t
```

- [ ] **Schritt 4:** Test → PASS.

- [ ] **Schritt 5:** `prompts/verdichter.md` schreiben. Kernanweisung: 3–5 Sätze Zusammenfassung, 2–4 Kernthemen mit je einem **buchstabengetreuen** Zitat, **keine Auslassungen mit `[...]`**, nichts erfinden, lieber ein Thema weglassen als ein Zitat konstruieren.

- [ ] **Schritt 6: `tests/test_verdichter.py` schreiben**

```python
def test_gueltiges_zitat_wird_gespeichert(conn, einst)
    # zitat_geprueft == 1, beleg_zitat gesetzt

def test_ungueltiges_zitat_wird_ohne_retry_verworfen(conn, einst):
    klm = LLMAttrappe({"zusammenfassung": "z", "kernthemen": [
        {"thema": "Abschied", "beleg_zitat": "Sie weinte bitterlich"}]})
    vid = verdichter.verdichte(klm, conn, einst, aid)
    assert klm.aufrufe == 1, "kein Retry"
    thema = repo.themen_zu(conn, vid)[0]
    assert thema["thema"] == "Abschied", "Vorschlag bleibt erhalten"
    assert thema["beleg_zitat"] is None and thema["zitat_geprueft"] == 0
    assert conn.execute(
        "SELECT count(*) FROM vorfall WHERE art='zitat_ungeprueft'").fetchone()[0] == 1
```

- [ ] **Schritt 7:** Test → FAIL. **Schritt 8:** `verdichter.py` + Repo-Ergänzungen schreiben. **Schritt 9:** Test → PASS.

Im Schema **jedes** Objekt mit `additionalProperties: false` und vollständigem `required`.

**Fertigstellungsbedingung:** Zitat-Tests und Verdichter-Tests bestehen; belegt ist, dass ein ungültiges Zitat **ohne Retry** entfernt wird und der Vorschlag trotzdem erhalten bleibt (§ 5).

- [ ] **Schritt 10:** Commit `Belegzitat-Pruefung und Verdichter`

---

## Aufgabe 8: Aufnahme-Pipeline, Nachhol-Arbeiter, Whisper-Ausfall

Die Aufgabe, in der § 10 lebt.

**Files:** `interview_theater/aufnahme.py`, Ergänzungen in `bot.py`, `tests/test_aufnahme.py`

**Produces:**
- Konstanten `KURZ_GRENZE_S = 45`, `TIPPANZEIGE_AB_S = 5`, `MELDUNG_AB_S = 12`, `BUDGET_KURZ_S = 45`, `BUDGET_LANG_S = 90`, `NACHHOL_INTERVALL_S = 60`, `MAX_VERSUCHE = 5`
- `aufnahme.klasse_fuer(dauer: int | None) -> str`
- `aufnahme.empfange(conn, tg, e, n: dict) -> int` — lädt herunter, legt `status='empfangen'` an, **ohne Whisper**
- `aufnahme.verarbeite(conn, tg, klm, e, klient, aufnahme_id) -> None`
- `aufnahme.importiere_text(conn, e, chat_id, message_id, text, name=None) -> int`
- `aufnahme.nachholen(conn, tg, klm, e, klient) -> None`
- `aufnahme.melde_ausfall(conn, tg, e, chat_id)` / `.melde_rueckkehr(conn, tg, e, chat_id)`

- [ ] **Schritt 1: Test schreiben** — die wichtigsten neun:

```python
def test_klasse_nach_dauer():
    assert aufnahme.klasse_fuer(7) == "kurz"
    assert aufnahme.klasse_fuer(45) == "kurz"
    assert aufnahme.klasse_fuer(46) == "lang"
    assert aufnahme.klasse_fuer(None) == "lang"   # im Zweifel Material


def test_datei_ist_gespeichert_bevor_whisper_gefragt_wird(conn, einst, tg):
    """Die eigentliche Absicherung (SPEC 10.2)."""
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=120))
    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["status"] == "empfangen"
    assert Path(zeile["audio_pfad"]).exists()
    # empfange() hat Whisper nie angefasst - es gibt keinen STT-Klienten im Aufruf


def test_lang_bekommt_empfangsbestaetigung_kurz_nicht(conn, einst, tg):
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300))
    assert any("hoere durch" in t for _, t in tg.gesendet)
    tg.gesendet.clear()
    aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=11))
    assert tg.gesendet == [], "ein Siebensekuender bekommt keine Bestaetigung"


def test_kurz_landet_als_nachricht_im_verlauf(conn, einst, tg, klm):
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("Mach mal lauter"), aid)
    zeile = conn.execute("SELECT * FROM nachricht WHERE typ='text' AND ist_bot=0 "
                         "ORDER BY message_id DESC").fetchone()
    assert zeile["text"] == "Mach mal lauter"
    assert repo.hole_aufnahme(conn, aid)["status"] == "fertig"
    assert repo.verdichtungen(conn, 1) == [], "kurz wird nicht verdichtet"


def test_lang_wird_verdichtet(conn, einst, tg, klm):
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe(TRANSKRIPT), aid)
    assert len(repo.verdichtungen(conn, 1)) == 1


def test_zeitbudget_ueberschritten_meldet_der_gruppe(conn, einst, tg, klm):
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=300))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)
    assert repo.hole_aufnahme(conn, aid)["status"] in ("empfangen", "fehlgeschlagen")
    assert any("nochmal" in t for _, t in tg.gesendet)


def test_whisper_ausfall_wird_genau_einmal_gemeldet(conn, einst, tg, klm):
    for i in range(3):
        aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=20 + i))
        aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)
    meldungen = [t for _, t in tg.gesendet if "nicht hoeren" in t]
    assert len(meldungen) == 1, "nicht bei jeder Nachricht wiederholen"


def test_rueckkehr_wird_gemeldet(conn, einst, tg, klm):
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)
    aid2 = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7, message_id=30))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_attrappe("da"), aid2)
    assert any("wieder hoeren" in t for _, t in tg.gesendet)
    assert repo.hole_gruppe(conn, 1)["whisper_stumm_seit"] is None


def test_nachholen_greift_empfangene_auf_und_loest_keine_antwort_aus(conn, einst, tg, klm):
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=7))
    aufnahme.verarbeite(conn, tg, klm, einst, stt_kaputt(), aid)
    aufnahme.nachholen(conn, tg, klm, einst, stt_attrappe("nachgeholt"))
    zeile = conn.execute("SELECT * FROM nachricht WHERE text='nachgeholt'").fetchone()
    assert zeile["unterdrueckt"] == 1, "Nachgeholtes loest nie eine Antwort aus"


def test_textimport_erzeugt_material_wie_eine_aufnahme(conn, einst, klm):
    aid = aufnahme.importiere_text(conn, einst, 1, 40, TRANSKRIPT, name="Recherche")
    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["quelle"] == "text" and zeile["status"] == "transkribiert"
    verdichter.verdichte(klm, conn, einst, aid)
    assert len(repo.verdichtungen(conn, 1)) == 1
```

- [ ] **Schritt 2:** Test → FAIL. **Schritt 3:** `aufnahme.py` schreiben.

Struktur von `verarbeite`: Budget nach Klasse wählen; bei `kurz` einen Timer starten, der nach `LANGSAM_AB_S` eine Zeile schickt; `stt.transkribiere` aufrufen; bei Erfolg `melde_rueckkehr`, Transkript speichern, dann je nach Klasse Nachricht schreiben oder verdichten; bei Fehler `versuche` hochzählen, `melde_ausfall`, und ab `MAX_VERSUCHE` auf `fehlgeschlagen` setzen und der Gruppe schreiben.

Die transkribierte Kurznachricht bekommt eine synthetische `message_id` (z. B. `aufnahme.message_id`, da die Sprachnachricht selbst als `typ='sprache'` ohne Text gespeichert ist — der Text kommt als **Aktualisierung** derselben Zeile, nicht als neue). Einfachste Umsetzung: `UPDATE nachricht SET text = ?, typ = 'text' WHERE chat_id = ? AND message_id = ?`. Damit bleibt die Reihenfolge im Verlauf korrekt und es entsteht kein Duplikat.

- [ ] **Schritt 4:** Test → PASS.

- [ ] **Schritt 5:** In `bot.py` einhängen: Sprachnachrichten → `pool.submit(aufnahme.empfange…)` und anschließend `verarbeite`; ein Hintergrund-Thread ruft alle `NACHHOL_INTERVALL_S` Sekunden `nachholen` auf; beim Start einmal `nachholen`.

**Fertigstellungsbedingung:** Alle Tests bestehen. Belegt sind: Klassengrenze bei 45 s, Datei liegt vor dem ersten Whisper-Aufruf in der DB, kurz bekommt keine Bestätigung und wird nicht verdichtet, Zeitbudget meldet der Gruppe, Ausfall wird **genau einmal** gemeldet, Rückkehr wird gemeldet, Nachgeholtes löst keine Antwort aus, Textimport erzeugt gleichwertiges Material.

- [ ] **Schritt 6:** Commit `Aufnahme-Pipeline mit zwei Klassen, Nachhol-Arbeiter und Ausfallmeldung`

---

## Aufgabe 9: Kontext-Zusammenbau

**Files:** `interview_theater/kontext.py`, `interview_theater/prompts/system.md`, Ergänzungen in `repo.py`, `tests/test_kontext.py`

**Produces:** `kontext.schaetze(text) -> int` · `kontext.SYSTEM` · `kontext.sprecherzeile(n) -> str` · `kontext.baue(conn, chat_id, ausloeser, e) -> str` · `BUDGETS`, `ZIEL = 10_000`, `REISSLEINE = 20_000`, `PAUSE_AB_MINUTEN = 60`
Repo-Ergänzungen: `hole_arbeitsstand` · `setze_arbeitsstand(conn, chat_id, feld, wert)` (nur `begriffe`, `kernthema`, `kernthema_begruendung`, `hauptkonflikt`) · `figuren` · `setze_figur(conn, chat_id, name, beschreibung)` · `journal` · `schreibe_journal`

- [ ] **Schritt 1:** `prompts/system.md` schreiben (§ 6.3): Rolle, die acht Stationen **als Beschreibung, nicht als Ablaufplan**, nichts erfinden, wörtlich zitieren ohne `[...]`, anbieten statt vorschreiben, kurz fassen, Befehlsliste, Verdichtungen werden nie geändert.

- [ ] **Schritt 2: Test schreiben**

```python
def test_schaetzung_ist_zeichen_durch_drei()
def test_leere_bloecke_fehlen_im_prompt(conn, einst)       # datengetrieben
def test_arbeitsstand_erscheint_sobald_er_existiert(conn, einst)
def test_pausenmarkierung_ab_einer_stunde(conn, einst)      # "[Pause: 18 Stunden]"
def test_keine_pausenmarkierung_bei_kurzem_abstand(conn, einst)
def test_kuerzung_haelt_die_reissleine_ein(conn, einst)     # 40 Aufnahmen, 400 Nachrichten
def test_notbremse_enthaelt_immer_die_ausloesende_nachricht(conn, einst)
```

- [ ] **Schritt 3:** Test → FAIL. **Schritt 4:** `kontext.py` schreiben. **Schritt 5:** Test → PASS.

Reihenfolge `verdichtungen, transkripte, arbeitsstand, journal, fenster, ausloeser` — **stabil nach vorn, flüchtig nach hinten**, begründet mit der Aufmerksamkeitsverteilung des Modells. **Kein Caching-Argument** (§ 6.1: bei Infomaniak unbelegt).

Kürzung (§ 7.2):

```python
if schaetze(zusammen(bloecke)) > ZIEL:
    bloecke["transkripte"] = ""
    repo.merke_vorfall(conn, chat_id, e.bot_name, "kuerzung", "Transkripte entfernt")
    while schaetze(zusammen(bloecke)) > ZIEL and bloecke["fenster"]:
        bloecke["fenster"] = _fenster_beschneiden(bloecke["fenster"])
```

**Fertigstellungsbedingung:** 7 Tests bestehen; die Reißleine hält auch bei 40 Aufnahmen und 400 Nachrichten, und die auslösende Nachricht überlebt jede Kürzung.

- [ ] **Schritt 6:** Commit `Kontext-Zusammenbau mit Budgets, Pausenmarkierung und Kuerzung`

---

## Aufgabe 10: Gesprächszug — Durchstich

**Files:** `interview_theater/ablauf.py`, Ergänzungen in `bot.py`, `tests/test_ablauf.py`

**Produces:** `ablauf.ist_ausloeser(n, bot_name) -> bool` · `ablauf.bearbeite(conn, tg, klm, e, chat_id)` · `ablauf.antworte(...)` · `TIPP_INTERVALL = 4.0`, `HINWEIS_NACH = 10.0`

- [ ] **Schritt 1: Test schreiben**

```python
def test_reply_auf_bot_loest_aus()
def test_erwaehnung_loest_aus()
def test_befehl_loest_aus()
def test_sprachnachricht_loest_immer_aus()
def test_beilaeufiges_geplauder_loest_nicht_aus()     # "ich hol mir Kaffee"

def test_nachzuegler_werden_in_einen_zug_gesammelt(conn, einst):
    """Waehrend ein Aufruf laeuft, sammeln sich Nachrichten (SPEC 1.3)."""
    # erster Zug in einem Thread, zwei Nachzuegler waehrenddessen
    assert len(klm.gesehen) == 2, "erster Zug, dann ein Sammelzug - nicht drei"

def test_wasserzeichen_wird_nach_der_antwort_gesetzt(conn, einst)
def test_bot_antwort_wird_mitgeschrieben(conn, einst)
def test_llm_fehler_meldet_der_gruppe_und_haelt_nicht_an(conn, einst)
```

- [ ] **Schritt 2:** Test → FAIL. **Schritt 3:** `ablauf.py` schreiben.

Die Sammelschleife — die äußere `while` ist wesentlich, sonst geht eine Nachricht verloren, die zwischen Abfrage und Freigabe eintrifft:

```python
def bearbeite(conn, tg, klm, e, chat_id: int) -> None:
    while True:
        sperre = _sperre_fuer(chat_id)
        if not sperre.acquire(blocking=False):
            return                      # laeuft schon; der laufende Zug nimmt sie mit
        try:
            offen = repo.unbeantwortete(conn, chat_id)
            if not offen:
                return
            antworte(conn, tg, klm, e, chat_id, offen)
        finally:
            sperre.release()
```

`antworte` setzt `setze_beantwortet_bis` im `finally` — auch ein gescheiterter Zug rückt vor, sonst wird er endlos wiederholt. Bei Fehler eine Zeile an die Gruppe („Bei mir hakt gerade etwas — fragt nochmal") plus `vorfall`. Tippanzeige als Kontextmanager mit Hintergrund-Thread, alle 4 s `tippt`, nach 10 s eine Zeile.

- [ ] **Schritt 4:** Test → PASS. **Schritt 5:** Gesamtlauf `python -m pytest -v`.

**Fertigstellungsbedingung des Durchstichs** — alle Tests bestehen **und** ein Lauf gegen die echten Dienste zeigt im Gruppenchat:

1. `@botname hallo` → der Bot antwortet.
2. Kurze Sprachnachricht (< 45 s) → wird transkribiert und **als Gesprächsbeitrag beantwortet**, ohne Empfangsbestätigung.
3. Lange Sprachnachricht (> 45 s) → Empfangsbestätigung, danach `aufnahme.status='fertig'` und mindestens ein Eintrag in `verdichtung_thema`.
4. `ich hol mir Kaffee` → keine Antwort, aber die Zeile steht in `nachricht`.
5. Prozess beenden, neu starten, `@botname und weiter?` → der Bot kennt den Verlauf; eine beim Beenden offene Aufnahme wird nachgeholt.

- [ ] **Schritt 6:** Commit `Gespraechszug mit Sperre, Sammeln und Tippanzeige - Durchstich steht`

---

# TEIL B — Ausbau

## Aufgabe 11: Extraktor (Journal + Arbeitsstand + Änderungsmeldung)

**Files:** `interview_theater/extraktor.py`, `interview_theater/prompts/extraktor.md`, Ergänzungen in `repo.py`/`bot.py`, `tests/test_extraktor.py`

Schema und Verhalten nach § 4.3. Die entscheidenden Tests:

```python
def test_arbeitsstand_wird_geschrieben_und_gemeldet(conn, einst, tg)
    # "Notiert: Kernthema = Ankommen" landet in tg.gesendet
def test_gleicher_wert_wird_nicht_erneut_gemeldet(conn, einst, tg)
def test_journaleintraege_werden_nicht_gemeldet(conn, einst, tg)
def test_null_felder_aendern_nichts(conn, einst, tg)
def test_leere_liste_ist_kein_fehler(conn, einst)
def test_fehlschlag_laesst_das_wasserzeichen_stehen(conn, einst)
def test_deckel_verwirft_das_fenster_und_meldet_es(conn, einst)
def test_nichts_zu_tun_ruft_das_modell_nicht_auf(conn, einst)
```

Läuft **nach** der Bot-Antwort im Hintergrund-Pool; ein Fehlschlag bleibt für die Gruppe unsichtbar.

- [ ] Commit `Extraktor schreibt Journal und Arbeitsstand und meldet jede Aenderung`

## Aufgabe 12: Befehle

Nach § 8. `/merken`, `/verworfen`, `/kernthema`, `/konflikt`, `/begriffe`, `/figur`, `/name`, `/material`, `/wortlaut`, `/stand`, `/hilfe`. **Korrekturweg, nicht Hauptweg.** `/stand` ohne LLM. `/material` ruft `aufnahme.importiere_text` und danach den Verdichter.

- [ ] Commit `Befehle als Korrekturweg zum Arbeitsstand`

## Aufgabe 13: Erstkontakt, Begrüßung, Betrieb

`bot.erstkontakt` (die allererste Nachricht erklärt, wie man den Bot anspricht), `bot.begruessung_faellig` (> 2 h), `betrieb/interview-theater@.service` mit `Restart=always`, `README.md` mit dem Hinweis **Privacy Mode bei BotFather ausschalten**.

- [ ] Commit `Erstkontakt, Begruessung und Betriebsdateien`

---

## Rangfolge, wenn die Zeit knapp wird

1. **Aufgaben 1–10 sind Pflicht.**
2. **Aufgabe 6 Schritt 5 (Rauchtest) so früh wie möglich** — ein Bot, der am Samstagmorgen zum ersten Mal die echte API sieht, ist kein Bot.
3. **Aufgabe 11 (Extraktor)** — ohne ihn bleibt der Arbeitsstand leer, und das ist nach der neuen Entscheidung der Hauptweg, nicht mehr eine Bequemlichkeit.
4. **Aufgabe 12 (Befehle)** — ohne sie gibt es keinen Korrekturweg und kein `/stand`.
5. **Aufgabe 13** — Kosmetik, aber billig.
