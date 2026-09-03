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


def test_loeschen_raeumt_die_gruppe(conn):
    conn.execute("INSERT INTO gruppe (chat_id, bot_name) VALUES (42, 'g1')")
    conn.execute("INSERT INTO nachricht (chat_id, message_id, typ, gesendet_am) "
                 "VALUES (42, 1, 'text', '2026-09-05T10:00:00')")
    conn.commit()
    db.loesche_gruppe(conn, 42)
    assert conn.execute("SELECT count(*) FROM nachricht").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM gruppe").fetchone()[0] == 0
