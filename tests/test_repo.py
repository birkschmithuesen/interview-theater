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
