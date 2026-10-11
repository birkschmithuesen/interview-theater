import json

import pytest

from interview_theater import repo, erkenner, erkenner_werkzeuge as ew, szene_claude
from interview_theater.szene_claude import Schleifenergebnis
from scripts import ab_pipeline_vs_tools as ab

FALL = {"id": "x1", "arbeitsstand": {}, "nachrichten": [
    {"absender": "Sara", "text": "wir machen jetzt ein Interview"}],
    "erwartet": [{"art": "interview_starten", "wert": ""}]}


def test_json_zaehlt_wie_der_korpus(conn, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "schema", lambda *a, **k: {"aenderungen": [
        {"art": "interview_starten", "wert": ""}, {"art": "verworfen", "wert": "x"}]})
    z = ab.laufe_json(conn, einst, None, 1, FALL)
    assert (z["modus"], z["treffer"], z["fp"], z["fn"]) == ("json", 1, 1, 0)
    assert z["still_fp"] == 1 and z["abgelehnt"] == 0


def test_tools_uebersetzt_und_trennt_still_und_laut(conn, einst, monkeypatch):
    ausf = [
        ew.Ausfuehrung(ew.GENERISCH, {"art": "interview_starten", "wert": ""}, True,
                       {"ok": True}, None, {"art": "interview_starten", "wert": ""}),
        ew.Ausfuehrung("setze_ort", {"szene": 9, "ort": "x"}, False, {"ok": False},
                       "keine_szene", None),
        ew.Ausfuehrung("frage_stellen", {"frage": "Wer?"}, True, {"ok": True}, None, None),
    ]
    lauf = Schleifenergebnis((), 2, None, 100, 20, 900, "")
    def werkzeuglauf(conn_, e, ch, n):
        repo.merke_aufruf(conn_, ch, "erkenner", tatsaechliche_token=60, antwort_token=10)
        repo.merke_aufruf(conn_, ch, "erkenner", tatsaechliche_token=40, antwort_token=10)
        return ([ausf[0].generisch], [], lauf, ausf)
    monkeypatch.setattr(erkenner, "_werkzeuglauf",
                        werkzeuglauf)
    z = ab.laufe_tools(conn, einst, 1, FALL)
    assert (z["modus"], z["treffer"], z["fp"], z["fn"]) == ("tools", 1, 0, 0)
    assert z["abgelehnt"] == 1 and z["ohne_korpusart"] == 1
    assert z["still_fp"] == 1          # fp 0 + ohne_korpusart 1
    assert (z["runden"], z["eingabe_token"], z["ausgabe_token"]) == (2, 100, 20)
    assert z["modellaufrufe"] == 2


def test_abgelehnter_aufruf_zaehlt_als_absicht(conn, einst, monkeypatch):
    fall = {"id": "x2", "arbeitsstand": {}, "nachrichten": [
        {"absender": "Sara", "text": "der Ort ist ein Bahnhof"}],
        "erwartet": [{"art": "szene_planen", "wert": "9 Bahnhof"}]}
    ausf = [ew.Ausfuehrung("setze_ort", {"szene": 9, "ort": "Bahnhof"}, False,
                           {"ok": False}, "keine_szene", None)]
    lauf = Schleifenergebnis((), 1, None, 10, 5, 100, "")
    monkeypatch.setattr(erkenner, "_werkzeuglauf",
                        lambda c, e, ch, n: ([], [], lauf, ausf))
    z = ab.laufe_tools(conn, einst, 1, fall)
    assert (z["treffer"], z["fn"]) == (0, 1)
    assert (z["absicht_treffer"], z["absicht_fp"], z["absicht_fn"]) == (1, 0, 0)
    assert z["abgelehnt_gruende"] == {"keine_szene": 1}


def test_json_absicht_gleich_hauptzaehlung(conn, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "schema", lambda *a, **k: {"aenderungen": [
        {"art": "interview_starten", "wert": ""}, {"art": "verworfen", "wert": "x"}]})
    z = ab.laufe_json(conn, einst, None, 1, FALL)
    assert (z["absicht_treffer"], z["absicht_fp"], z["absicht_fn"]) == (
        z["treffer"], z["fp"], z["fn"])


def test_zeile_ist_jsonl_tauglich(conn, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "schema", lambda *a, **k: {"aenderungen": []})
    json.dumps(ab.laufe_json(conn, einst, None, 1, FALL))


def test_fehler_im_fall_bricht_den_lauf_nicht(conn, einst, monkeypatch):
    def kaputt(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(szene_claude, "schema", kaputt)
    z = ab.laufe_json(conn, einst, None, 1, FALL)
    assert "boom" in z["fehler"] and z["treffer"] == 0


def test_cli_kennt_keinen_automatiklauf():
    with pytest.raises(SystemExit):
        ab.main([])


def test_dauer_misst_nur_den_modellaufruf(conn, einst, monkeypatch):
    uhr = {"t": 0.0}
    monkeypatch.setattr(ab.time, "monotonic", lambda: uhr["t"])

    def nutzer(*a, **k):
        uhr["t"] += 50.0           # Nutzertext-Bau darf nicht zaehlen
        return "text"
    monkeypatch.setattr(ab, "nutzertext_fuer", nutzer)

    def schema(*a, **k):
        uhr["t"] += 2.0
        return {"aenderungen": []}
    monkeypatch.setattr(szene_claude, "schema", schema)
    assert ab.laufe_json(conn, einst, None, 1, FALL)["dauer_ms"] == 2000

    lauf = Schleifenergebnis((), 1, None, 0, 0, 777, "")

    def wl(*a, **k):
        uhr["t"] += 3.0
        return ([], [], lauf, [])
    monkeypatch.setattr(erkenner, "_werkzeuglauf", wl)
    assert ab.laufe_tools(conn, einst, 1, FALL)["dauer_ms"] == 3000


def test_json_summiert_alle_versuche(conn, einst, monkeypatch):
    def schema(c, e, k, ch, *a, **kw):
        for ein in (10, 20, 30):   # Retry: drei gebuchte Aufrufe
            repo.merke_aufruf(c, ch, "erkenner", tatsaechliche_token=ein, antwort_token=1)
        return {"aenderungen": []}
    monkeypatch.setattr(szene_claude, "schema", schema)
    z = ab.laufe_json(conn, einst, None, 1, FALL)
    assert (z["eingabe_token"], z["ausgabe_token"], z["modellaufrufe"]) == (60, 3, 3)


def test_db_nicht_leer_wird_abgelehnt(tmp_path):
    vorhanden = tmp_path / "alt.db"
    vorhanden.write_bytes(b"x")
    with pytest.raises(SystemExit, match="nicht leer"):
        ab._messkopie_db(str(vorhanden))
    ab._messkopie_db(str(tmp_path / "neu.db")).close()


def test_zeile_traegt_aufnahme_feld(conn, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "schema", lambda *a, **k: {"aenderungen": []})
    assert ab.laufe_json(conn, einst, None, 1, FALL)["aufnahme"] is False
    assert ab._leer("json", {**FALL, "aufnahme": {"x": 1}})["aufnahme"] is True
