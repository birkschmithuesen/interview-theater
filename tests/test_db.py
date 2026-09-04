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


def test_gruppe_hat_interviewmodus_seit_spalte(conn):
    """teil-b.md Aufgabe 5, SPEC § 10.1: Grundlage von aufnahme.klasse_fuer()."""
    spalten = [r[1] for r in conn.execute("PRAGMA table_info(gruppe)")]
    assert "interviewmodus_seit" in spalten


def test_gruppe_hat_web_token_spalte(conn):
    """Weboberflaeche (NACHTRAG N1-B): Zugang zur Gruppenseite laeuft ueber
    gruppe.web_token, es gibt kein Login."""
    spalten = [r[1] for r in conn.execute("PRAGMA table_info(gruppe)")]
    assert "web_token" in spalten


#: Die 'gruppe'-Tabelle, wie sie vor Aufgabe 5 aussah -- ohne
#: interviewmodus_seit. Fuer den Migrationstest unten bewusst hier hart
#: hinterlegt statt aus db.SCHEMA abgeleitet: der Test soll pruefen, dass
#: initialisiere() eine ECHTE Alt-Datenbank nachruestet, unabhaengig davon,
#: wie sich SCHEMA künftig weiterentwickelt.
_ALTE_GRUPPE_TABELLE = """
CREATE TABLE gruppe (
  chat_id                         INTEGER PRIMARY KEY,
  bot_name                        TEXT NOT NULL,
  titel                           TEXT,
  erste_nachricht_am              TEXT,
  letzte_beantwortete_message_id  INTEGER DEFAULT 0,
  letzte_extrahierte_message_id   INTEGER DEFAULT 0,
  wortlaut_modus                  TEXT,
  gruendlich_naechster_zug        INTEGER NOT NULL DEFAULT 0,
  whisper_stumm_seit              TEXT
);
"""


def test_migration_ergaenzt_fehlende_spalte_ohne_datenverlust(tmp_path):
    """Aufgabe 5, Auftragstest: initialisiere() muss auf einer Datenbank
    durchlaufen, der interviewmodus_seit fehlt (jede vor heute angelegte
    Datenbank) -- und darf dabei keine vorhandenen Daten verlieren. Die
    Migration ist allgemein (Soll- gegen Ist-Spalten, siehe
    db._migriere_fehlende_spalten), nicht auf genau diese eine Spalte
    zugeschnitten."""
    pfad = str(tmp_path / "alt.db")
    c = db.verbinde(pfad)
    c.executescript(_ALTE_GRUPPE_TABELLE)
    c.execute(
        "INSERT INTO gruppe (chat_id, bot_name, titel) VALUES (1, 'gruppe1', 'Testgruppe')"
    )
    c.commit()
    spalten_vorher = [r[1] for r in c.execute("PRAGMA table_info(gruppe)")]
    assert "interviewmodus_seit" not in spalten_vorher, "Testannahme: die Spalte fehlt wirklich"

    db.initialisiere(c)  # darf nicht krachen, obwohl 'gruppe' schon (alt) existiert

    spalten_nachher = [r[1] for r in c.execute("PRAGMA table_info(gruppe)")]
    assert "interviewmodus_seit" in spalten_nachher

    zeile = c.execute("SELECT * FROM gruppe WHERE chat_id = 1").fetchone()
    assert zeile["titel"] == "Testgruppe", "Migration darf keine Daten verlieren"
    assert zeile["bot_name"] == "gruppe1"
    assert zeile["interviewmodus_seit"] is None

    # Die nachgeruestete Spalte ist auch wirklich benutzbar.
    c.execute("UPDATE gruppe SET interviewmodus_seit = ? WHERE chat_id = 1", ("2026-09-05T10:00:00+00:00",))
    c.commit()
    assert c.execute(
        "SELECT interviewmodus_seit FROM gruppe WHERE chat_id = 1"
    ).fetchone()[0] == "2026-09-05T10:00:00+00:00"


def test_migration_ergaenzt_web_token_ohne_datenverlust(tmp_path):
    """Weboberflaeche: dieselbe Migration muss auch die neueste Spalte
    nachruesten -- eine Datenbank vom ersten Workshoptag kennt web_token
    nicht, ihre Nachrichten muessen den Nachruestlauf trotzdem ueberleben."""
    pfad = str(tmp_path / "alt.db")
    c = db.verbinde(pfad)
    c.executescript(_ALTE_GRUPPE_TABELLE)
    c.execute(
        "INSERT INTO gruppe (chat_id, bot_name, titel) VALUES (7, 'gruppe1', 'Gruppe Sieben')"
    )
    c.commit()
    assert "web_token" not in [r[1] for r in c.execute("PRAGMA table_info(gruppe)")], \
        "Testannahme: die Spalte fehlt wirklich"

    db.initialisiere(c)

    zeile = c.execute("SELECT * FROM gruppe WHERE chat_id = 7").fetchone()
    assert zeile["titel"] == "Gruppe Sieben", "Migration darf keine Daten verlieren"
    assert zeile["web_token"] is None, "nachgeruestet, aber noch nicht gefuellt"


def test_migration_ist_ein_no_op_wenn_alle_spalten_schon_da_sind(conn):
    """Ein zweiter initialisiere()-Lauf auf einer schon aktuellen Datenbank
    darf nicht krachen (kein ALTER TABLE auf eine schon vorhandene Spalte)."""
    db.initialisiere(conn)  # zweiter Lauf, darf keine Ausnahme werfen
    spalten = [r[1] for r in conn.execute("PRAGMA table_info(gruppe)")]
    assert "interviewmodus_seit" in spalten


def test_loeschen_raeumt_die_gruppe(conn):
    conn.execute("INSERT INTO gruppe (chat_id, bot_name) VALUES (42, 'g1')")
    conn.execute("INSERT INTO nachricht (chat_id, message_id, typ, gesendet_am) "
                 "VALUES (42, 1, 'text', '2026-09-05T10:00:00')")
    conn.commit()
    db.loesche_gruppe(conn, 42)
    assert conn.execute("SELECT count(*) FROM nachricht").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM gruppe").fetchone()[0] == 0
