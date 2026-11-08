from interview_theater import db


def _spalten(conn, tabelle):
    return {z[1] for z in conn.execute(f"PRAGMA table_info({tabelle})")}


def test_neue_stellen_existieren(conn):
    assert "wer_zusatz" in _spalten(conn, "szene")
    assert {"rolle", "position"} <= _spalten(conn, "szene_figur")
    assert {"szene_id", "text", "status", "antwort", "quelle"} <= _spalten(conn, "offene_frage")
    assert {"szene_id", "ansicht", "grund", "angeboten_am", "erledigt_am", "entscheidung"} <= _spalten(conn, "veraltet")
    assert {"art", "ziel", "vorher", "nachher", "quelle"} <= _spalten(conn, "stueck_aenderung")


def test_neue_tabellen_stehen_in_der_loeschzusage():
    for t in ("offene_frage", "veraltet", "stueck_aenderung"):
        assert t in db.TABELLEN_MIT_CHAT_ID


def test_alte_datenbank_bekommt_die_spalten_additiv(tmp_path):
    c = db.verbinde(str(tmp_path / "alt.db"))
    c.executescript(
        "CREATE TABLE szene_figur (chat_id INTEGER NOT NULL, szene_id INTEGER NOT NULL,"
        " figur_id INTEGER NOT NULL, PRIMARY KEY (szene_id, figur_id));"
        "INSERT INTO szene_figur VALUES (1, 2, 3);"
    )
    db.initialisiere(c)
    assert tuple(c.execute("SELECT rolle, position FROM szene_figur").fetchone()) == (None, None)
