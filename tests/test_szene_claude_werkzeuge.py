import dataclasses
import json

import httpx
import pytest

from interview_theater import szene_claude

CHAT = 1


@pytest.fixture
def opus_e(einst):
    return dataclasses.replace(einst, szene_anbieter="claude")


def _antwort(content, stop, ein=10, aus=5):
    return httpx.Response(200, json={
        "content": content, "stop_reason": stop,
        "usage": {"input_tokens": ein, "output_tokens": aus},
    })


def _tool(i, name="setze_ort", eingabe=None):
    return {"type": "tool_use", "id": f"t{i}", "name": name,
            "input": eingabe or {"szene": 1, "ort": "Küche"}}


def _klient(antworten, koerper):
    folge = iter(antworten)

    def handler(anfrage):
        koerper.append(json.loads(anfrage.content))
        antwort = next(folge)
        if isinstance(antwort, Exception):
            raise antwort
        return antwort
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ausfuehren(protokoll):
    def f(name, eingabe):
        protokoll.append((name, eingabe))
        return json.dumps({"ok": True}), False
    return f


def test_eine_runde_werkzeug_dann_fertig(conn, opus_e):
    koerper, protokoll = [], []
    klient = _klient([_antwort([_tool(1)], "tool_use"),
                      _antwort([{"type": "text", "text": "erledigt"}], "end_turn")], koerper)
    r = szene_claude.werkzeug_schleife(
        conn, opus_e, klient, CHAT, "sys", "nutz", [{"name": "setze_ort"}],
        _ausfuehren(protokoll), art="erkenner")
    assert r.abbruch is None and r.runden == 2 and r.text == "erledigt"
    assert protokoll == [("setze_ort", {"szene": 1, "ort": "Küche"})]
    assert r.eingabe_token == 20 and r.ausgabe_token == 10
    assert koerper[0]["tools"] == [{"name": "setze_ort"}]
    assert koerper[0]["tool_choice"] == {"type": "auto"}
    letzte = koerper[1]["messages"][-1]
    assert letzte["role"] == "user"
    assert letzte["content"][0] == {"type": "tool_result", "tool_use_id": "t1",
                                    "content": '{"ok": true}', "is_error": False}
    zeilen = conn.execute("SELECT modus FROM aufruf WHERE art='erkenner'").fetchall()
    assert [z["modus"] for z in zeilen] == ["C", "C"]


def test_rundendeckel(conn, opus_e):
    antworten = [_antwort([_tool(i)], "tool_use") for i in range(10)]
    r = szene_claude.werkzeug_schleife(
        conn, opus_e, _klient(antworten, []), CHAT, "s", "n", [], _ausfuehren([]),
        art="erkenner", max_runden=3, max_aufrufe=99)
    assert r.abbruch == "runden" and r.runden == 3


def test_aufrufdeckel_fuehrt_nicht_mehr_aus(conn, opus_e):
    protokoll = []
    antworten = [_antwort([_tool(1), _tool(2), _tool(3)], "tool_use")]
    r = szene_claude.werkzeug_schleife(
        conn, opus_e, _klient(antworten, []), CHAT, "s", "n", [], _ausfuehren(protokoll),
        art="erkenner", max_aufrufe=2)
    assert r.abbruch == "aufrufe" and len(protokoll) == 2
    assert [a["is_error"] for a in r.aufrufe] == [False, False]


def test_zeitdeckel(conn, opus_e):
    zeiten = iter([0.0, 0.0, 500.0, 500.0, 500.0])
    antworten = [_antwort([_tool(1)], "tool_use"), _antwort([_tool(2)], "tool_use")]
    r = szene_claude.werkzeug_schleife(
        conn, opus_e, _klient(antworten, []), CHAT, "s", "n", [], _ausfuehren([]),
        art="erkenner", gesamt_timeout=120.0, uhr=lambda: next(zeiten))
    assert r.abbruch == "zeit" and r.runden == 1


def test_erster_aufruf_scheitert_wirft_claudefehler(conn, opus_e):
    klient = _klient([httpx.Response(400, json={})], [])
    with pytest.raises(szene_claude.ClaudeFehler):
        szene_claude.werkzeug_schleife(conn, opus_e, klient, CHAT, "s", "n", [],
                                       _ausfuehren([]), art="erkenner")


def test_spaeterer_fehler_ist_abbruch_kein_wurf(conn, opus_e):
    protokoll = []
    klient = _klient([_antwort([_tool(1)], "tool_use"), httpx.Response(400, json={})], [])
    r = szene_claude.werkzeug_schleife(conn, opus_e, klient, CHAT, "s", "n", [],
                                       _ausfuehren(protokoll), art="erkenner")
    assert r.abbruch == "fehler" and len(protokoll) == 1


def test_prosa_koerper_bleibt_ohne_tools(conn, opus_e):
    koerper = []
    klient = _klient([_antwort([{"type": "text", "text": "x"}], "end_turn")], koerper)
    szene_claude.prosa(conn, opus_e, klient, CHAT, "s", "n", "szene", timeout=5)
    assert "tools" not in koerper[0] and "tool_choice" not in koerper[0]
