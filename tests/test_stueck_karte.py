import json

from interview_theater import phasen, repo, stueck


def _szene(conn, nummer=1, volltext=None, **karte):
    sid = repo.stelle_szene_sicher(conn, 1, nummer)
    k = {"typ": "spoken", "modus": "none", "worum": "w", "punkte": ["p"], "zitate": []}
    k.update(karte)
    repo.setze_szenenkarte(conn, sid, json.dumps(k))
    repo.setze_szenenkarte_bestaetigt(conn, sid)
    if volltext:
        repo.setze_stagescript(conn, sid, volltext, None)
    return sid


def test_karte_aendern_in_phase_7_laesst_abnahme_stehen(conn):
    phasen.setze(conn, 1, 7, "test")
    sid = _szene(conn)
    e = stueck.karte_aendern(conn, 1, szene=1, punkte_hinzu=["Tutti si alzano"])
    assert e.ok and "punkte" in " ".join(e.diff)
    s = repo.hole_szene(conn, sid)
    assert s["karte_bestaetigt_am"]
    assert stueck.karte(conn, s)["punkte"] == ["p", "Tutti si alzano"]


def test_open_punkt_wird_offene_frage(conn):
    sid = _szene(conn)
    stueck.karte_aendern(conn, 1, szene=1, punkte_hinzu=["[OPEN] Wo steht Giona?"])
    k = stueck.karte(conn, repo.hole_szene(conn, sid))
    assert k["punkte"] == ["p", "[OPEN] Wo steht Giona?"]   # Ansicht
    roh = json.loads(repo.hole_szene(conn, sid)["karte"])
    assert roh["punkte"] == ["p"]                            # nicht im JSON
    [f] = repo.offene_fragen(conn, 1, sid)
    assert (f["text"], f["status"]) == ("Wo steht Giona?", "vertagt")


def test_kartentreue_markiert_mit_befund(conn):
    sid = _szene(conn, volltext="Gli dico che posto occupa nell'ordine di reclutamento: e l'ultimo.")
    e = stueck.karte_aendern(conn, 1, szene=1, punkte_hinzu=[
        "✔ No: Arlecchino gli dice solo di sedersi, senza dire che posto occupa "
        "nell'ordine di reclutamento"])
    [v] = repo.offene_veraltet(conn, 1)
    assert v["szene_id"] == sid and "che posto occupa" in v["grund"].lower()
    assert e.warnungen


def test_ungueltiger_typ(conn):
    _szene(conn)
    assert stueck.karte_aendern(conn, 1, szene=1, typ="oper").fehler == "ungueltig"


def test_zitat_nur_aus_bestand(conn):
    _szene(conn)
    assert stueck.karte_aendern(conn, 1, szene=1, zitate=[99]).fehler == "ungueltig"


def test_zitat_aus_geprueftem_bestand(conn, monkeypatch):
    from interview_theater import szenenkern

    sid = _szene(conn)
    monkeypatch.setattr(szenenkern, "_kandidaten", lambda c, chat, z: [
        ("Wir stehen im Loch.", "Interview 1"), ("Zweiter Satz.", "")])
    e = stueck.karte_aendern(conn, 1, szene=1, zitate=[2, 1])
    assert e.ok
    roh = json.loads(repo.hole_szene(conn, sid)["karte"])
    assert roh["zitate"] == [{"zitat": "Zweiter Satz.", "interview": ""},
                             {"zitat": "Wir stehen im Loch.", "interview": "Interview 1"}]


def test_nicht_zahl_ist_ungueltig(conn, monkeypatch):
    from interview_theater import szenenkern

    _szene(conn)
    monkeypatch.setattr(szenenkern, "_kandidaten", lambda c, chat, z: [("a", "")])
    assert stueck.karte_aendern(conn, 1, szene=1, zitate=["x"]).fehler == "ungueltig"
    assert stueck.reihenfolge_aendern(conn, 1, folge=["a"]).fehler == "ungueltig"
    assert stueck.reihenfolge_aendern(conn, 1, folge=[1, None]).fehler == "ungueltig"


def test_keine_karte(conn):
    repo.stelle_szene_sicher(conn, 1, 1)
    assert stueck.karte_aendern(conn, 1, szene=1, worum="x").fehler == "keine_karte"


def test_wieder_oeffnen(conn):
    sid = _szene(conn, volltext="T")
    repo.setze_szene_fertig(conn, sid, True)
    assert stueck.szene_wieder_oeffnen(conn, 1, szene=1, ebene="script").ok
    assert not repo.hole_szene(conn, sid)["fertig_am"]
    assert stueck.szene_wieder_oeffnen(conn, 1, szene=1, ebene="karte").ok
    assert not repo.hole_szene(conn, sid)["karte_bestaetigt_am"]
    assert stueck.szene_wieder_oeffnen(conn, 1, szene=1, ebene="x").fehler == "ungueltig"


def test_reihenfolge(conn):
    a, b, c = (_szene(conn, n, volltext=f"SCENE {n}") for n in (1, 2, 3))
    e = stueck.reihenfolge_aendern(conn, 1, folge=[3, 1, 2])
    assert e.ok
    assert [repo.hole_szene(conn, i)["nummer"] for i in (a, b, c)] == [2, 3, 1]
    assert {v["szene_id"] for v in repo.offene_veraltet(conn, 1)} == {a, b, c}
    assert stueck.reihenfolge_aendern(conn, 1, folge=[1, 1, 2]).fehler == "ungueltig"
