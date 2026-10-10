import json

from interview_theater import repo, stueck, szenenkarte
from tests.stueck_hilfe import TG, lege_karte_an


class E:
    bot_name = "test"


def test_antwort_schliesst_sofort_auch_bei_abbruch(conn):
    sid = lege_karte_an(conn, fragen=["Wo?", "Wann?", "Wer?"])
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, E(), 1, 1)
    assert szenenkarte.beantworte_frage(conn, tg, None, E(), 1, "Im Loch") is True
    status = {f["text"]: f["status"] for f in repo.fragen_der_szene(conn, 1, sid)}
    assert status == {"Wo?": "beantwortet", "Wann?": "offen", "Wer?": "offen"}
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["fragen"] == ["Wann?", "Wer?"]


def test_skip_wird_vertagt(conn):
    sid = lege_karte_an(conn, fragen=["Wo?"])
    tg = TG()
    szenenkarte.starte_fragenklaerung(conn, tg, E(), 1, 1)
    szenenkarte.beantworte_frage(conn, tg, None, E(), 1, "skip")
    [f] = repo.fragen_der_szene(conn, 1, sid)
    assert f["status"] == "vertagt"


def test_ueberspringen_verwirft_ohne_json_aenderung(conn):
    sid = lege_karte_an(conn, fragen=["Unpassend?"])
    roh = repo.hole_szene(conn, sid)["karte"]
    szenenkarte.ueberspringe_fragen(conn, TG(), E(), 1, 1)
    assert repo.hole_szene(conn, sid)["karte"] == roh
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["fragen"] == []


def test_alte_klaerung_ohne_ids_wird_zurueckgesetzt(conn):
    sid = lege_karte_an(conn, fragen=["Wo?"])
    repo.setze_szenenkarte_klaerung(conn, sid, json.dumps({"index": 0, "antworten": []}))
    assert szenenkarte.beantworte_frage(conn, TG(), None, E(), 1, "x") is False
    assert repo.hole_szene(conn, sid)["karte_klaerung"] is None


def test_erzeuge_schreibt_struktur_an_ihre_stelle(conn, monkeypatch):
    from interview_theater import modellwahl

    repo.stelle_szene_sicher(conn, 1, 1)
    monkeypatch.setattr(modellwahl, "aufruf_schema", lambda *a, **k: {
        "typ": "spoken", "modus": "none", "worum": "w", "ort": "Bar", "wer": "il pubblico",
        "punkte": ["p"], "zitate": [], "questions": ["Licht?"]})
    k = szenenkarte.erzeuge(conn, object(), E(), 1, 1)
    s = repo.hole_szene(conn, repo.stelle_szene_sicher(conn, 1, 1))
    assert s["ort"] == "Bar" and s["wer_zusatz"] == "il pubblico"
    assert not {"ort", "wer", "fragen"} & set(json.loads(s["karte"]))
    assert k["fragen"] == ["Licht?"]
