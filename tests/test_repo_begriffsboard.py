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
