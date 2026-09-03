from datetime import datetime, timedelta, timezone

import pytest

from theatersoap import bot, db, repo

JETZT = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    return c


def bau_update(update_id: int, message_id: int, text: str, gesendet_am: datetime) -> dict:
    """Baut ein rohes Telegram-Update mit fester Gruppe (-100, 'Gruppe 1')."""
    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "date": int(gesendet_am.timestamp()),
            "chat": {"id": -100, "title": "Gruppe 1"},
            "from": {"first_name": "Ada"},
            "text": text,
        },
    }


def bau_sprachupdate(update_id: int, message_id: int, gesendet_am: datetime) -> dict:
    """Baut ein rohes Telegram-Update mit einer Sprachnachricht."""
    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "date": int(gesendet_am.timestamp()),
            "chat": {"id": -100, "title": "Gruppe 1"},
            "from": {"first_name": "Ada"},
            "voice": {"file_id": "AwACabc", "duration": 12},
        },
    }


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


def test_sprachnachricht_wird_unterdrueckt_aber_zurueckgeliefert(conn, einst):
    """Auftragshinweis 1: Sprache hat noch kein Transkript und darf deshalb keinen
    Zug ausloesen -- ist aber kein Duplikat/Nachtstau, die Schleife muss sie an
    die Aufnahme-Pipeline (Aufgabe 8) weiterreichen koennen."""
    n = bot.verarbeite_update(conn, einst, bau_sprachupdate(4, 13, JETZT), JETZT, False)
    zeile = conn.execute("SELECT * FROM nachricht WHERE message_id = 13").fetchone()
    assert zeile["unterdrueckt"] == 1
    assert n is not None
    assert n["typ"] == "sprache"


def test_duplikat_liefert_none(conn, einst):
    update = bau_update(5, 14, "einmal", JETZT)
    erster = bot.verarbeite_update(conn, einst, update, JETZT, False)
    zweiter = bot.verarbeite_update(conn, einst, update, JETZT, False)
    assert erster is not None
    assert zweiter is None
