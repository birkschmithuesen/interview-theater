import json

from interview_theater import db, repo, stueck


def _alt(conn, nummer, karte, ort=None, figuren=()):
    sid = repo.stelle_szene_sicher(conn, 1, nummer)
    if ort is not None:
        conn.execute("UPDATE szene SET ort = ? WHERE id = ?", (ort, sid))
    conn.execute("UPDATE szene SET karte = ?, karte_bestaetigt_am = 'x' WHERE id = ?",
                 (json.dumps(karte), sid))
    for f in figuren:
        repo.setze_figur(conn, 1, f, "")
        conn.execute("INSERT INTO szene_figur (chat_id, szene_id, figur_id) VALUES (1, ?, ?)",
                     (sid, repo.hole_figur(conn, 1, f)["id"]))
    conn.commit()
    return sid


K = {"typ": "spoken", "modus": "none", "worum": "w", "punkte": ["p"], "zitate": []}


def test_konsistent_bleibt_gleich(conn):
    sid = _alt(conn, 1, dict(K, ort="Bar", wer="Anna", fragen=[]), ort="Bar", figuren=["Anna"])
    db._migriere_stueckmodell(conn)
    k = stueck.karte(conn, repo.hole_szene(conn, sid))
    assert (k["ort"], k["wer"]) == ("Bar", "Anna")
    assert repo.stueck_aenderungen(conn, 1, quelle="migration") == []


def test_widerspruch_ein_wert_und_bericht(conn):
    sid = _alt(conn, 1, dict(K, ort="Sala riunioni", wer="Emma, Giada e tutto il pubblico", fragen=[]),
               ort="meeting room", figuren=["Emma", "Giona"])
    repo.setze_figur(conn, 1, "Giada", "")
    z = db._migriere_stueckmodell(conn)
    s = repo.hole_szene(conn, sid)
    assert s["ort"] == "Sala riunioni"
    assert [b["name"] for b in repo.besetzung(conn, sid)] == ["Emma", "Giada", "Giona"]
    assert s["wer_zusatz"] == "tutto il pubblico"
    assert z["konflikt_ort"] == 1 and z["konflikt_wer"] == 1
    assert s["karte_bestaetigt_am"] == "x"


def test_name_ohne_figur_wird_berichtet_nicht_angelegt(conn):
    sid = _alt(conn, 1, dict(K, wer="Anna, Chicca", fragen=[]), figuren=["Anna"])
    z = db._migriere_stueckmodell(conn)
    assert z["name_ohne_figur"] == 1
    assert repo.hole_figur(conn, 1, "Chicca") is None
    assert repo.hole_szene(conn, sid)["wer_zusatz"] == "Chicca"


def test_fragen_und_open_punkte(conn):
    sid = _alt(conn, 1, dict(K, punkte=["p", "[OPEN] Licht?"], fragen=["Wann?"]))
    db._migriere_stueckmodell(conn)
    assert [(f["text"], f["status"]) for f in repo.offene_fragen(conn, 1, sid)] == [
        ("Wann?", "offen"), ("Licht?", "vertagt")]
    roh = json.loads(repo.hole_szene(conn, sid)["karte"])
    assert roh["punkte"] == ["p"] and not {"ort", "wer", "fragen"} & set(roh)


def test_idempotent(conn):
    _alt(conn, 1, dict(K, ort="Bar", wer="", fragen=["Wann?"]))
    db._migriere_stueckmodell(conn)
    vorher = conn.execute("SELECT count(*) FROM offene_frage").fetchone()[0]
    assert db._migriere_stueckmodell(conn) == {}
    assert conn.execute("SELECT count(*) FROM offene_frage").fetchone()[0] == vorher


def test_initialisiere_ruft_die_migration(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "g", "G")
    sid = repo.stelle_szene_sicher(c, 1, 1)
    c.execute("UPDATE szene SET karte = ? WHERE id = ?", (json.dumps(dict(K, ort="Bar")), sid))
    c.commit()
    db.initialisiere(c)
    assert repo.hole_szene(c, sid)["ort"] == "Bar"


def test_offene_transaktion_und_kaputtes_json_stoeren_nicht(conn):
    sid = _alt(conn, 1, dict(K, ort="Bar"))
    kaputt = repo.stelle_szene_sicher(conn, 1, 2)
    conn.execute("UPDATE szene SET karte = ? WHERE id = ?", ('{"ort": kaputt', kaputt))
    conn.execute("UPDATE szene SET ort = ? WHERE id = ?", ("x", kaputt))  # offene Transaktion
    db._migriere_stueckmodell(conn)
    assert repo.hole_szene(conn, sid)["ort"] == "Bar"
    assert repo.hole_szene(conn, kaputt)["karte"] == '{"ort": kaputt'


def test_vorhandenes_wer_zusatz_bleibt_bei_leerem_rest(conn):
    sid = _alt(conn, 1, dict(K, wer="Anna"), figuren=["Anna"])
    conn.execute("UPDATE szene SET wer_zusatz = 'Publikum' WHERE id = ?", (sid,))
    conn.commit()
    db._migriere_stueckmodell(conn)
    assert repo.hole_szene(conn, sid)["wer_zusatz"] == "Publikum"


def test_entfernte_szene_bleibt_unberuehrt(conn):
    sid = _alt(conn, 1, dict(K, ort="Bar"))
    conn.execute("UPDATE szene SET entfernt_am = 'x' WHERE id = ?", (sid,))
    conn.commit()
    assert db._migriere_stueckmodell(conn) == {}
    assert "ort" in json.loads(repo.hole_szene(conn, sid)["karte"])


def test_beantwortete_frage_bleibt_beantwortet_beim_zweiten_lauf(conn):
    """Abschlussreview I3: schreibt ein alter Prozess ``karte.fragen`` wieder
    ins JSON, darf die Migration eine schon bekannte (auch beantwortete)
    Frage nicht erneut als offen anlegen."""
    sid = _alt(conn, 1, dict(K, punkte=["p", "[OPEN] Licht?"], fragen=["Wann?"]))
    db._migriere_stueckmodell(conn)
    frage = next(f for f in repo.offene_fragen(conn, 1, sid) if f["text"] == "Wann?")
    assert stueck.frage_beantworten(conn, 1, frage_id=frage["id"], antwort="Abends").ok
    conn.execute("UPDATE szene SET karte = ? WHERE id = ?", (
        json.dumps(dict(K, punkte=["p", "[OPEN]  licht?"], fragen=["wann?"])), sid))
    conn.commit()
    z = db._migriere_stueckmodell(conn)
    alle = repo.fragen_der_szene(conn, 1, sid)
    assert len(alle) == 2
    assert next(f for f in alle if f["text"] == "Wann?")["status"] == "beantwortet"
    assert not z.get("frage_uebernommen")
    assert "fragen" not in json.loads(repo.hole_szene(conn, sid)["karte"])
