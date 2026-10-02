"""Die Tabelle web_strom: der laufende Text zwischen zwei Prozessen.

Der Bot ruft das Modell, der Webserver haengt am Browser -- sie teilen nur
die SQLite-Datei (WAL). Eine Zeile je laufendem Aufruf: der Bot schreibt
gedrosselt, der Webserver liest read-only und schickt die Deltas per SSE.
"""

import pytest

from interview_theater import db, repo

CHAT = 7_000_000_000_001
ANDERE = 7_000_000_000_002


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web-Gruppe")
    return verbindung


def test_eine_zeile_entsteht_laufend(conn):
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    zeile = repo.hole_strom(conn, sid)
    assert zeile["zustand"] == repo.STROM_LAEUFT
    assert zeile["art"] == "gespraech"
    assert zeile["text"] == ""
    assert zeile["post_id"] is None


def test_text_waechst_und_die_zeit_rueckt_vor(conn):
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    vorher = repo.hole_strom(conn, sid)["aktualisiert_am"]
    repo.schreibe_strom(conn, sid, "Hallo")
    repo.schreibe_strom(conn, sid, "Hallo ihr")
    zeile = repo.hole_strom(conn, sid)
    assert zeile["text"] == "Hallo ihr"
    assert zeile["aktualisiert_am"] >= vorher


def test_abschluss_setzt_zustand_und_post_id(conn):
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.beende_strom(conn, sid, repo.STROM_FERTIG, post_id=17)
    zeile = repo.hole_strom(conn, sid)
    assert zeile["zustand"] == repo.STROM_FERTIG
    assert zeile["post_id"] == 17


def test_abbruch_laesst_keine_post_id_zurueck(conn):
    sid = repo.beginne_strom(conn, CHAT, "szene")
    repo.schreibe_strom(conn, sid, "halber Satz")
    repo.beende_strom(conn, sid, repo.STROM_ABGEBROCHEN)
    zeile = repo.hole_strom(conn, sid)
    assert zeile["zustand"] == repo.STROM_ABGEBROCHEN
    assert zeile["post_id"] is None
    # Der Teiltext bleibt in der Zeile stehen -- er ist nie eine Nachricht
    # geworden, aber im Log der Gruppe nachvollziehbar, was zu sehen war.
    assert zeile["text"] == "halber Satz"


def test_laufende_nur_die_eigene_gruppe(conn):
    repo.sichere_gruppe(conn, ANDERE, "gruppe2", "Andere")
    meiner = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.beginne_strom(conn, ANDERE, "gespraech")
    assert [z["id"] for z in repo.laufende_stroeme(conn, CHAT)] == [meiner]


def test_beendete_zaehlen_nicht_mehr_als_laufend(conn):
    sid = repo.beginne_strom(conn, CHAT, "gespraech")
    repo.beende_strom(conn, sid, repo.STROM_FERTIG, post_id=1)
    assert repo.laufende_stroeme(conn, CHAT) == []


def test_web_strom_steht_im_loeschweg():
    """Die Loeschzusage ist ein DELETE je Tabelle (db.loesche_gruppe) -- eine
    Tabelle mit chat_id, die dort fehlt, ueberlebt das Loeschen einer Gruppe."""
    assert "web_strom" in db.TABELLEN_MIT_CHAT_ID


def test_loesche_gruppe_nimmt_die_stroeme_mit(conn):
    repo.beginne_strom(conn, CHAT, "gespraech")
    db.loesche_gruppe(conn, CHAT)
    assert conn.execute(
        "SELECT COUNT(*) FROM web_strom WHERE chat_id = ?", (CHAT,)
    ).fetchone()[0] == 0


def test_migration_ruestet_die_tabelle_nach(tmp_path):
    """db.py migriert ausschliesslich additiv (AGENTS.md): eine Datenbank ohne
    die Tabelle bekommt sie beim naechsten Start, ohne user_version-Schritt."""
    pfad = str(tmp_path / "alt.db")
    alt = db.verbinde(pfad)
    db.initialisiere(alt)
    vorher = alt.execute("PRAGMA user_version").fetchone()[0]
    alt.execute("DROP TABLE web_strom")
    alt.commit()
    alt.close()

    neu = db.verbinde(pfad)
    db.initialisiere(neu)
    repo.sichere_gruppe(neu, CHAT, "gruppe1", "X")
    assert repo.beginne_strom(neu, CHAT, "gespraech") > 0
    assert neu.execute("PRAGMA user_version").fetchone()[0] == vorher
