import json

from interview_theater import repo, stueck
from tests.stueck_hilfe import lege_karte_an


def test_frage_beantworten_schliesst_im_modell(conn):
    sid = lege_karte_an(conn, fragen=["Wo steht Giona?"])
    [f] = repo.offene_fragen(conn, 1, sid)
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["fragen"] == ["Wo steht Giona?"]
    e = stueck.frage_beantworten(conn, 1, frage_id=f["id"], antwort="im Loch")
    assert e.ok
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["fragen"] == []


def test_beantwortete_frage_kommt_nie_wieder(conn):
    sid = lege_karte_an(conn, fragen=["Wo steht Giona?"])
    [f] = repo.offene_fragen(conn, 1, sid)
    stueck.frage_beantworten(conn, 1, frage_id=f["id"], antwort="im Loch")
    e = stueck.frage_stellen(conn, 1, szene=1, frage="wo steht giona?")
    assert e.ok and e.frage_id == f["id"] and e.warnungen
    assert repo.offene_fragen(conn, 1, sid) == []


def test_zurueckstellen_wird_open_punkt_und_sperrt_nicht(conn):
    sid = lege_karte_an(conn, fragen=["Musik?"])
    [f] = repo.offene_fragen(conn, 1, sid)
    stueck.frage_zurueckstellen(conn, 1, frage_id=f["id"])
    k = stueck.karte(conn, repo.hole_szene(conn, sid))
    assert k["fragen"] == [] and "[OPEN] Musik?" in k["punkte"]


def test_verwerfen(conn):
    sid = lege_karte_an(conn, fragen=["Unpassend?"])
    [f] = repo.offene_fragen(conn, 1, sid)
    stueck.frage_verwerfen(conn, 1, frage_id=f["id"])
    assert stueck.karte(conn, repo.hole_szene(conn, sid))["punkte"] == ["p"]


def test_beantwortete_frage_wird_nicht_zurueckgestellt_oder_verworfen(conn):
    sid = lege_karte_an(conn, fragen=["Wo steht Giona?"])
    [f] = repo.offene_fragen(conn, 1, sid)
    stueck.frage_beantworten(conn, 1, frage_id=f["id"], antwort="im Loch")
    n = len(repo.stueck_aenderungen(conn, 1))
    for werkzeug in (stueck.frage_zurueckstellen, stueck.frage_verwerfen):
        e = werkzeug(conn, 1, frage_id=f["id"])
        assert e.ok and e.aenderung_id is None
    zeile = repo.hole_offene_frage(conn, f["id"])
    assert (zeile["status"], zeile["antwort"]) == ("beantwortet", "im Loch")
    assert len(repo.stueck_aenderungen(conn, 1)) == n


def test_busy_gate_fragen_und_pruefung(conn, monkeypatch):
    from interview_theater import ueberarbeitung

    sid = lege_karte_an(conn, fragen=["Wo steht Giona?"])
    [f] = repo.offene_fragen(conn, 1, sid)
    repo.setze_stagescript(conn, sid, "ANNA: x.", None)
    monkeypatch.setattr(ueberarbeitung, "laeuft", lambda chat_id: True)
    for e in (stueck.frage_stellen(conn, 1, szene=1, frage="Neu?"),
              stueck.frage_beantworten(conn, 1, frage_id=f["id"], antwort="a"),
              stueck.frage_zurueckstellen(conn, 1, frage_id=f["id"]),
              stueck.frage_verwerfen(conn, 1, frage_id=f["id"]),
              stueck.pruefe_szene(conn, 1, szene=1)):
        assert not e.ok and e.fehler == "beschaeftigt"
    assert repo.hole_offene_frage(conn, f["id"])["status"] == "offen"
    assert len(repo.offene_fragen(conn, 1, sid)) == 1
    assert stueck.frage_stellen(conn, 1, szene=1, frage="Neu?", quelle=stueck.QUELLE_SCRIPT).ok
    assert stueck.pruefe_szene(conn, 1, szene=1, quelle=stueck.QUELLE_SCRIPT).ok


def test_karte_aus_modell_ohne_unbekannte_namen_behaelt_zusatz(conn):
    repo.setze_figur(conn, 1, "Anna", "")
    sid = lege_karte_an(conn, wer="Anna, il pubblico")
    assert repo.hole_szene(conn, sid)["wer_zusatz"] == "il pubblico"
    lege_karte_an(conn, wer="Anna")
    assert repo.hole_szene(conn, sid)["wer_zusatz"] == "il pubblico"


def test_fremde_frage(conn):
    assert stueck.frage_beantworten(conn, 1, frage_id=999, antwort="x").fehler == "unbekannte_frage"


def test_karte_aus_modell_trennt_struktur_vom_json(conn):
    repo.setze_figur(conn, 1, "Anna", "")
    sid = lege_karte_an(conn, ort="Bar", wer="Anna (Arlecchino), tutto il pubblico",
                        fragen=["Wann?"], punkte=["p", "[OPEN] Licht?"])
    roh = json.loads(repo.hole_szene(conn, sid)["karte"])
    assert not {"ort", "wer", "fragen"} & set(roh) and roh["punkte"] == ["p"]
    k = stueck.karte(conn, repo.hole_szene(conn, sid))
    assert (k["ort"], k["wer"], k["fragen"]) == ("Bar", "Anna (Arlecchino), tutto il pubblico", ["Wann?"])
    assert "[OPEN] Licht?" in k["punkte"]
    assert json.loads(repo.karte_verlauf(conn, 1, sid)[-1]["karte_json"])["ort"] == "Bar"


def test_karte_aus_modell_entfernt_nie_still(conn):
    for n in ("Anna", "Pietro"):
        repo.setze_figur(conn, 1, n, "")
    sid = lege_karte_an(conn, wer="Anna, Pietro")
    lege_karte_an(conn, wer="Anna")
    assert [b["name"] for b in repo.besetzung(conn, sid)] == ["Anna", "Pietro"]


def test_pruefe_szene_vermerkt_widerspruch(conn):
    sid = lege_karte_an(conn, punkte=["✔ No: senza dire saresti l'ultimo"])
    repo.setze_stagescript(conn, sid, "ANNA: Saresti l'ultimo.", None)
    e = stueck.pruefe_szene(conn, 1, szene=1)
    assert e.ok and e.veraltet and e.warnungen
