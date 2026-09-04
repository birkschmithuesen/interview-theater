"""Datenbankschema und Verbindungsaufbau (SPEC-kontext-architektur.md § 3.1)."""

import re
import sqlite3

# Woertlich aus SPEC-kontext-architektur.md § 3.1 uebernommen, nur um
# "IF NOT EXISTS" ergaenzt, damit initialisiere() gefahrlos mehrfach laufen kann.
SCHEMA = """
-- Pro Bot-Token, nicht pro Gruppe: die getUpdates-Position
CREATE TABLE IF NOT EXISTS bot_zustand (
  bot_name              TEXT PRIMARY KEY,
  letzte_update_id      INTEGER,
  gestartet_am          TEXT,
  letzte_aktivitaet_am  TEXT
);

CREATE TABLE IF NOT EXISTS gruppe (
  chat_id                         INTEGER PRIMARY KEY,
  bot_name                        TEXT NOT NULL,
  titel                           TEXT,
  erste_nachricht_am              TEXT,
  -- Antwort- und Extraktionsstand
  letzte_beantwortete_message_id  INTEGER DEFAULT 0,
  letzte_extrahierte_message_id   INTEGER DEFAULT 0,
  -- Journal-Extraktor-Wasserzeichen (Verdraengung statt jedem Zug, siehe journal.py)
  letzte_journalisierte_message_id INTEGER DEFAULT 0,
  -- Schalter
  wortlaut_modus                  TEXT,     -- NULL=aus, '*'=alle, sonst Aufnahmename
  gruendlich_naechster_zug        INTEGER NOT NULL DEFAULT 0,  -- Modus B einmalig (§ 4.5)
  whisper_stumm_seit              TEXT,     -- gesetzt = Ausfall gemeldet (§ 10.4)
  interviewmodus_seit             TEXT      -- gesetzt = Interviewmodus an (teil-b.md Aufgabe 5, § 10.1)
);

CREATE TABLE IF NOT EXISTS nachricht (
  chat_id        INTEGER NOT NULL,
  message_id     INTEGER NOT NULL,
  telegram_user  INTEGER,
  absender       TEXT,                      -- Vorname oder 'Bot'
  ist_bot        INTEGER NOT NULL DEFAULT 0,
  typ            TEXT NOT NULL,             -- text|sprache|foto|sticker|sonstiges
  text           TEXT,
  gesendet_am    TEXT NOT NULL,             -- ISO 8601
  unterdrueckt   INTEGER NOT NULL DEFAULT 0,-- 1 = nie Antwort auslösen (Nachtstau)
  PRIMARY KEY (chat_id, message_id)
);
CREATE INDEX IF NOT EXISTS idx_nachricht_zeit ON nachricht(chat_id, message_id);

-- Sprachaufnahmen UND Textimporte. Eine Statusmaschine fuer beides (§ 10).
CREATE TABLE IF NOT EXISTS aufnahme (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  message_id      INTEGER NOT NULL,
  name            TEXT,                     -- 'Maria'; Ersatz: 'Interview 3'
  klasse          TEXT NOT NULL,            -- kurz (Gespraechsbeitrag) | lang (Material)
  quelle          TEXT NOT NULL,            -- sprache | text
  audio_pfad      TEXT,                     -- NULL bei quelle='text'
  transkript      TEXT,
  dauer_sekunden  INTEGER,
  status          TEXT NOT NULL,            -- empfangen|transkribiert|fertig|fehlgeschlagen
  fehlertext      TEXT,
  versuche        INTEGER NOT NULL DEFAULT 0,
  empfangen_am    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_aufnahme_offen ON aufnahme(status);

CREATE TABLE IF NOT EXISTS verdichtung (
  id               INTEGER PRIMARY KEY,
  chat_id          INTEGER NOT NULL,
  aufnahme_id      INTEGER NOT NULL,
  zusammenfassung  TEXT NOT NULL,
  erstellt_am      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verdichtung_thema (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  verdichtung_id  INTEGER NOT NULL,
  thema           TEXT NOT NULL,
  beleg_zitat     TEXT,                     -- NULL, wenn Prüfung nach § 5 fehlschlug
  zitat_geprueft  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS arbeitsstand (
  chat_id                INTEGER PRIMARY KEY,
  begriffe               TEXT,
  kernthema              TEXT,
  kernthema_begruendung  TEXT,
  hauptkonflikt          TEXT,
  geaendert_am           TEXT
);

CREATE TABLE IF NOT EXISTS figur (
  id            INTEGER PRIMARY KEY,
  chat_id       INTEGER NOT NULL,
  name          TEXT NOT NULL,
  beschreibung  TEXT,
  beleg_zitat   TEXT,
  geaendert_am  TEXT
);

CREATE TABLE IF NOT EXISTS szene (
  id                INTEGER PRIMARY KEY,
  chat_id           INTEGER NOT NULL,
  nummer            INTEGER,
  titel             TEXT,
  kurzbeschreibung  TEXT,                   -- eine Zeile, geht immer mit
  volltext          TEXT,                   -- nur die zuletzt geänderte Szene geht mit
  geaendert_am      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_szene_aktuell ON szene(chat_id, geaendert_am DESC);

CREATE TABLE IF NOT EXISTS journal (
  id                INTEGER PRIMARY KEY,
  chat_id           INTEGER NOT NULL,
  art               TEXT NOT NULL,          -- vorgeschlagen|verworfen|entschieden|offen
  text              TEXT NOT NULL,
  quelle            TEXT NOT NULL,          -- extraktor|befehl
  bis_message_id    INTEGER,
  erstellt_am       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_journal_chat ON journal(chat_id, id);

-- Was das Dashboard rot färbt
CREATE TABLE IF NOT EXISTS vorfall (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER,                     -- NULL bei bot-weiten Vorfällen
  bot_name     TEXT,
  art          TEXT NOT NULL,               -- kuerzung|fenster_verworfen|extraktor_fehler|
                                            -- zitat_ungeprueft|http_5xx|abgeschnitten|…
  stufe        INTEGER,
  detail       TEXT,
  erstellt_am  TEXT NOT NULL
);

-- Selbstkorrektur der Token-Schätzung
CREATE TABLE IF NOT EXISTS aufruf (
  id                     INTEGER PRIMARY KEY,
  chat_id                INTEGER,
  art                    TEXT NOT NULL,     -- gespraech|verdichter|extraktor
  modus                  TEXT,              -- A|B
  geschaetzte_token      INTEGER,
  tatsaechliche_token    INTEGER,           -- usage.prompt_tokens
  antwort_token          INTEGER,
  finish_reason          TEXT,
  dauer_ms               INTEGER,
  erfolg                 INTEGER,
  erstellt_am            TEXT NOT NULL
);
"""

# Alle Tabellen mit chat_id -- Grundlage der Loeschzusage (§ 3, global-constraints.md).
TABELLEN_MIT_CHAT_ID = (
    "gruppe",
    "nachricht",
    "aufnahme",
    "verdichtung",
    "verdichtung_thema",
    "arbeitsstand",
    "figur",
    "szene",
    "journal",
    "vorfall",
    "aufruf",
)


def verbinde(pfad: str) -> sqlite3.Connection:
    """Baut eine Verbindung mit den projektweiten PRAGMAs auf (global-constraints.md § 3)."""
    conn = sqlite3.connect(pfad, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


#: Zeilenanfaenge, die keine Spalte sind, sondern eine Tabellen-Constraint
#: (z. B. ``PRIMARY KEY (chat_id, message_id)`` in ``nachricht``) -- die
#: Migration unten darf so eine Zeile nicht als fehlende Spalte missverstehen
#: und per ALTER TABLE anzulegen versuchen.
_KEINE_SPALTE_PRAEFIXE = ("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "CONSTRAINT")


def _tabellenspalten_aus_schema() -> dict[str, list[tuple[str, str]]]:
    """Liest Tabellen- und Sollspalten direkt aus SCHEMA statt aus einem
    zweiten, von Hand gepflegten Katalog -- der koennte sonst aus dem Tritt
    geraten, sobald jemand nur SCHEMA aendert. Liefert je Tabelle eine Liste
    aus (Spaltenname, Rest-Definition-fuer-ALTER-TABLE)."""
    ergebnis: dict[str, list[tuple[str, str]]] = {}
    for tabelle, koerper in re.findall(
        r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", SCHEMA, re.DOTALL
    ):
        spalten = []
        for zeile in koerper.splitlines():
            zeile = zeile.split("--", 1)[0].strip().rstrip(",")
            if not zeile or zeile.upper().startswith(_KEINE_SPALTE_PRAEFIXE):
                continue
            name, _, definition = zeile.partition(" ")
            spalten.append((name, definition.strip()))
        ergebnis[tabelle] = spalten
    return ergebnis


def _migriere_fehlende_spalten(conn: sqlite3.Connection) -> None:
    """Ergaenzt in einer schon bestehenden Datenbank Spalten, die im SCHEMA
    seither hinzugekommen sind (z. B. gruppe.interviewmodus_seit, teil-b.md
    Aufgabe 5) -- per ``ALTER TABLE ... ADD COLUMN``, allgemein anhand eines
    Vergleichs Soll- (SCHEMA) gegen Ist-Spalten (``PRAGMA table_info``), nicht
    als Einzelfall fuer genau eine Spalte. Ohne das braeche jede Datenbank,
    die vor einer Schemaerweiterung angelegt wurde -- schon vorhandene Spalten
    werden stillschweigend uebersprungen."""
    for tabelle, spalten in _tabellenspalten_aus_schema().items():
        vorhandene = {zeile[1] for zeile in conn.execute(f"PRAGMA table_info({tabelle})")}
        for name, definition in spalten:
            if name in vorhandene:
                continue
            conn.execute(f"ALTER TABLE {tabelle} ADD COLUMN {name} {definition}")
    conn.commit()


def initialisiere(conn: sqlite3.Connection) -> None:
    """Legt das Schema an, falls noch nicht vorhanden, und ergaenzt in einer
    schon vorhandenen Datenbank fehlende Spalten (siehe
    _migriere_fehlende_spalten)."""
    conn.executescript(SCHEMA)
    conn.commit()
    _migriere_fehlende_spalten(conn)


def loesche_gruppe(conn: sqlite3.Connection, chat_id: int) -> None:
    """Loescht alle Datensaetze einer Gruppe (Loeschzusage). Das Audioverzeichnis
    liegt ausserhalb der Datenbank und wird von scripts/loeschen.py entfernt."""
    for tabelle in TABELLEN_MIT_CHAT_ID:
        conn.execute(f"DELETE FROM {tabelle} WHERE chat_id = ?", (chat_id,))
    conn.commit()
