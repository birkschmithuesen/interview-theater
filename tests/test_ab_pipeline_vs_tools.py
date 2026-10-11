import json

import pytest

from interview_theater import erkenner, erkenner_werkzeuge as ew, szene_claude
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
    monkeypatch.setattr(erkenner, "_werkzeuglauf",
                        lambda conn_, e, ch, n: ([ausf[0].generisch], [], lauf, ausf))
    z = ab.laufe_tools(conn, einst, 1, FALL)
    assert (z["modus"], z["treffer"], z["fp"], z["fn"]) == ("tools", 1, 0, 0)
    assert z["abgelehnt"] == 1 and z["ohne_korpusart"] == 1
    assert z["still_fp"] == 1          # fp 0 + ohne_korpusart 1
    assert (z["runden"], z["eingabe_token"], z["dauer_ms"]) == (2, 100, 900)


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
