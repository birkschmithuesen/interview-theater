import pytest

from interview_theater import db, repo, web_kanal

CHAT = 7_000_000_000_099


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web-Gruppe")
    repo.setze_gruppe_kanal(verbindung, CHAT, "web")
    return verbindung


@pytest.fixture
def kanal(conn, tmp_path):
    return web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio"), schritt_s=0.01)


def test_repo_beansprucht_den_hinweis_nur_einmal(conn):
    assert repo.beanspruche_abkuerzungen_hinweis(conn, CHAT) is True
    assert repo.beanspruche_abkuerzungen_hinweis(conn, CHAT) is False


def test_erste_knopfnachricht_traegt_den_hinweis_davor(conn, kanal):
    message_id = kanal.sende_mit_knoepfen(CHAT, "Weiter?", [("Ja", "k:1")])
    zeilen = conn.execute(
        "SELECT * FROM web_post WHERE chat_id = ? ORDER BY id", (CHAT,)
    ).fetchall()
    assert len(zeilen) == 2
    assert zeilen[0]["typ"] == repo.WEB_TYP_SYSTEM
    assert zeilen[0]["text"] == web_kanal.TEXT_ABKUERZUNG_HINWEIS
    assert zeilen[1]["id"] == message_id


def test_der_hinweis_kommt_kein_zweites_mal(conn, kanal):
    kanal.sende_mit_knoepfen(CHAT, "Weiter?", [("Ja", "k:1")])
    anzahl_vorher = conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE chat_id = ?", (CHAT,)
    ).fetchone()[0]
    kanal.sende_mit_knoepfen(CHAT, "Noch mal?", [("Ja", "k:2")])
    anzahl_nachher = conn.execute(
        "SELECT COUNT(*) FROM web_post WHERE chat_id = ?", (CHAT,)
    ).fetchone()[0]
    assert anzahl_nachher - anzahl_vorher == 1
