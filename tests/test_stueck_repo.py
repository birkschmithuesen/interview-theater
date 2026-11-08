import json

from interview_theater import repo


def _szene(conn, nummer=1):
    return repo.stelle_szene_sicher(conn, 1, nummer)


def test_besetzung_mit_rolle_und_reihenfolge(conn):
    for n in ("Anna", "Pietro"):
        repo.setze_figur(conn, 1, n, "")
    anna, pietro = (repo.hole_figur(conn, 1, n)["id"] for n in ("Anna", "Pietro"))
    sid = _szene(conn)
    repo.setze_besetzung(conn, 1, sid, [(pietro, None), (anna, "(Arlecchino)")], "tutto il pubblico")
    reihen = repo.besetzung(conn, sid)
    assert [(r["name"], r["rolle"]) for r in reihen] == [("Pietro", None), ("Anna", "(Arlecchino)")]
    assert repo.hole_szene(conn, sid)["wer_zusatz"] == "tutto il pubblico"
    # szene_figuren folgt derselben Reihenfolge
    assert [f["name"] for f in repo.szene_figuren(conn, sid)] == ["Pietro", "Anna"]


def test_aktualisiere_szenenkarte_laesst_abnahme_stehen(conn):
    sid = _szene(conn)
    repo.setze_szenenkarte(conn, sid, json.dumps({"worum": "a"}))
    repo.setze_szenenkarte_bestaetigt(conn, sid)
    repo.aktualisiere_szenenkarte(conn, 1, sid, json.dumps({"worum": "b"}), "aenderung", "n")
    s = repo.hole_szene(conn, sid)
    assert json.loads(s["karte"])["worum"] == "b"
    assert s["karte_bestaetigt_am"]
    assert repo.karte_verlauf(conn, 1, sid)[-1]["notiz_text"] == "n"
    repo.setze_szenenkarte_offen(conn, sid)
    assert repo.hole_szene(conn, sid)["karte_bestaetigt_am"] is None


def test_szenenort(conn):
    sid = _szene(conn)
    repo.setze_szenenort(conn, sid, "Piazza")
    assert repo.hole_szene(conn, sid)["ort"] == "Piazza"


def test_offene_frage_lebenslauf(conn):
    sid = _szene(conn)
    fid = repo.lege_offene_frage_an(conn, 1, sid, "Wo steht Giona?", "test")
    assert [f["id"] for f in repo.offene_fragen(conn, 1, sid)] == [fid]
    repo.setze_frage_status(conn, fid, "beantwortet", "im Loch")
    assert repo.offene_fragen(conn, 1, sid) == []
    f = repo.hole_offene_frage(conn, fid)
    assert (f["status"], f["antwort"]) == ("beantwortet", "im Loch") and f["geschlossen_am"]
    assert [x["id"] for x in repo.fragen_der_szene(conn, 1, sid)] == [fid]


def test_veraltet_eine_offene_zeile_je_szene_und_ansicht(conn):
    sid = _szene(conn)
    a = repo.merke_veraltet(conn, 1, sid, "script", "neuer Ort", None)
    b = repo.merke_veraltet(conn, 1, sid, "script", "neue Figur Anna", None)
    assert a == b
    [zeile] = repo.offene_veraltet(conn, 1)
    assert zeile["grund"] == "neuer Ort; neue Figur Anna"
    repo.erledige_veraltet(conn, a, "lassen")
    assert repo.offene_veraltet(conn, 1) == []


def test_veraltet_angeboten_und_erledige_fuer(conn):
    sid = _szene(conn)
    v = repo.merke_veraltet(conn, 1, sid, "script", "x", None)
    repo.markiere_veraltet_angeboten(conn, v)
    assert repo.offene_veraltet(conn, 1, nur_unangeboten=True) == []
    assert repo.hole_veraltet(conn, v)["angeboten_am"]
    assert repo.erledige_veraltet_fuer(conn, 1, sid, "script", "neu") == 1


def test_nummeriere_szenen(conn):
    a, b, c = (_szene(conn, n) for n in (1, 2, 3))
    repo.nummeriere_szenen(conn, 1, [c, a, b])
    assert [repo.hole_szene(conn, i)["nummer"] for i in (a, b, c)] == [2, 3, 1]


def test_stueck_aenderung_nur_anhaengend(conn):
    i = repo.merke_stueck_aenderung(conn, 1, "setze_ort", {"szene": 1}, "Bar", "Piazza", "test")
    [z] = repo.stueck_aenderungen(conn, 1)
    assert z["id"] == i and json.loads(z["nachher"]) == "Piazza"
    assert repo.stueck_aenderungen(conn, 1, quelle="anders") == []
