import pytest
from theatersoap import db, repo


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


def test_wasserzeichen_geht_nie_rueckwaerts(conn):
    repo.setze_beantwortet_bis(conn, 1, 12)
    repo.setze_beantwortet_bis(conn, 1, 5)
    assert repo.hole_gruppe(conn, 1)["letzte_beantwortete_message_id"] == 12


def test_merke_aufruf_schreibt_die_richtigen_spalten(conn):
    repo.merke_aufruf(
        conn,
        chat_id=1,
        art="gespraech",
        modus="A",
        geschaetzte_token=100,
        tatsaechliche_token=110,
        antwort_token=42,
        finish_reason="stop",
        dauer_ms=987,
        erfolg=1,
    )
    row = conn.execute("SELECT * FROM aufruf").fetchone()
    assert row["chat_id"] == 1
    assert row["art"] == "gespraech"
    assert row["modus"] == "A"
    assert row["geschaetzte_token"] == 100
    assert row["tatsaechliche_token"] == 110
    assert row["antwort_token"] == 42
    assert row["finish_reason"] == "stop"
    assert row["dauer_ms"] == 987
    assert row["erfolg"] == 1
    assert row["erstellt_am"] is not None


def test_letzte_nachrichten_liefert_die_letzten_in_chronologischer_reihenfolge(conn):
    for message_id in range(1, 6):
        repo.merke_nachricht(conn, 1, message_id, "Ada", 0, "text", f"n{message_id}",
                              f"2026-09-05T10:0{message_id}:00")
    ergebnis = repo.letzte_nachrichten(conn, 1, anzahl=3)
    assert [r["message_id"] for r in ergebnis] == [3, 4, 5]
