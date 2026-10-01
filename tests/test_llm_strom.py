"""Streaming bei Infomaniak: gleiche Rueckgabe, gleiche Buchung, sauberer Rueckfall.

Der Kern dieser Datei ist der Vergleich: derselbe Aufruf einmal mit und
einmal ohne ``bei_teil`` muss dieselbe ``aufruf``-Zeile hinterlassen
(prompt_tokens, completion_tokens, finish_reason, erfolg) -- sonst steht der
Kostendeckel (E7, Karte S) beim Streamen auf Sand.

Kein Netz: httpx.MockTransport spielt den Anbieter.
"""

import json

import httpx
import pytest

from interview_theater import db, llm, repo

CHAT = 7_000_000_000_001


class Einstellungen:
    llm_url = "https://example.invalid/v1/chat/completions"
    llm_key = "geheim"
    llm_modell = "moonshotai/Kimi-K2.6"
    bot_name = "gruppe1"


@pytest.fixture(autouse=True)
def frischer_prozesszustand():
    llm.vergiss_strom()
    yield
    llm.vergiss_strom()


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "X")
    return verbindung


def _sse(stuecke, usage=True, finish="stop"):
    """Baut eine OpenAI-Stream-Antwort aus Textstuecken."""
    zeilen = []
    for stueck in stuecke:
        zeilen.append("data: " + json.dumps(
            {"choices": [{"delta": {"content": stueck}, "finish_reason": None}]}
        ))
    zeilen.append("data: " + json.dumps(
        {"choices": [{"delta": {}, "finish_reason": finish}]}
    ))
    if usage:
        zeilen.append("data: " + json.dumps(
            {"choices": [], "usage": {"prompt_tokens": 120, "completion_tokens": 34}}
        ))
    zeilen.append("data: [DONE]")
    return ("\n\n".join(zeilen) + "\n\n").encode("utf-8")


_FERTIG = {
    "choices": [{"message": {"content": '{"antwort": "Hallo ihr"}'},
                 "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 120, "completion_tokens": 34},
}

#: Das JSON kommt in fuenf Stuecken -- der Dekoder sieht also jeden Zwischenstand.
_STUECKE = ['{"antw', 'ort": "Hal', "lo ", "ihr", '"}']


def _klient(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _aufrufzeile(conn):
    return conn.execute("SELECT * FROM aufruf ORDER BY id DESC LIMIT 1").fetchone()


# -- ohne bei_teil bleibt alles, wie es war ---------------------------------


def test_ohne_bei_teil_steht_kein_stream_im_koerper(conn):
    """E1 im Kleinen: ein Aufrufer, der nichts von Streaming weiss, schickt
    denselben Anfragekoerper wie vor dieser Karte."""
    gesehen = {}

    def handler(anfrage):
        gesehen["body"] = json.loads(anfrage.content)
        return httpx.Response(200, json=_FERTIG)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech")
    assert "stream" not in gesehen["body"]
    assert "stream_options" not in gesehen["body"]


# -- mit bei_teil ------------------------------------------------------------


def test_stream_liefert_mehr_als_ein_teilstueck(conn):
    teile = []

    def handler(anfrage):
        assert json.loads(anfrage.content)["stream"] is True
        assert json.loads(anfrage.content)["stream_options"] == {"include_usage": True}
        return httpx.Response(200, content=_sse(_STUECKE))

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    ergebnis = klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                          bei_teil=teile.append)
    assert len(teile) > 1
    assert teile == [t for t in teile if isinstance(t, str)]
    # Der Dekoder liefert den bisherigen Wert, nie das rohe JSON.
    assert all("antwort" not in t for t in teile)
    assert teile[-1] == "Hallo ihr"
    assert ergebnis == {"antwort": "Hallo ihr"}


def test_der_endtext_ist_der_rueckgabewert(conn):
    teile = []
    klm = llm.LLM(Einstellungen(),
                  _klient(lambda a: httpx.Response(200, content=_sse(_STUECKE))), conn)
    ergebnis = klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                          bei_teil=teile.append)
    assert ergebnis["antwort"] == teile[-1]


def test_die_aufrufzeile_ist_dieselbe_wie_ohne_stream(conn):
    """Die Abnahme der Karte: ``aufruf``-Kosten wie ohne Stream."""
    klm_ohne = llm.LLM(Einstellungen(),
                       _klient(lambda a: httpx.Response(200, json=_FERTIG)), conn)
    klm_ohne.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech")
    ohne = _aufrufzeile(conn)

    klm_mit = llm.LLM(Einstellungen(),
                      _klient(lambda a: httpx.Response(200, content=_sse(_STUECKE))), conn)
    klm_mit.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                   bei_teil=lambda t: None)
    mit = _aufrufzeile(conn)

    for spalte in ("art", "modus", "geschaetzte_token", "tatsaechliche_token",
                   "antwort_token", "finish_reason", "erfolg"):
        assert mit[spalte] == ohne[spalte], spalte


def test_prosa_streamt_den_rohen_text(conn):
    teile = []
    klm = llm.LLM(
        Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=_sse(["Es war ", "einmal"]))),
        conn,
    )
    text = klm.prosa(CHAT, "sys", "nutz", "szene", bei_teil=teile.append)
    assert teile == ["Es war ", "Es war einmal"]
    assert text == "Es war einmal"


def test_reasoning_geht_nie_an_bei_teil(conn):
    """Die Denkspur ist nie fuer die Gruppe (Entscheidung C)."""
    inhalt = (
        'data: {"choices": [{"delta": {"reasoning_content": "ich ueberlege"}}]}\n\n'
        'data: {"choices": [{"delta": {"content": "Hallo"}}]}\n\n'
        'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}\n\n'
        'data: {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}\n\n'
        "data: [DONE]\n\n"
    ).encode("utf-8")
    teile = []
    klm = llm.LLM(Einstellungen(),
                  _klient(lambda a: httpx.Response(200, content=inhalt)), conn)
    klm.prosa(CHAT, "sys", "nutz", "szene", bei_teil=teile.append)
    assert teile == ["Hallo"]


def test_finish_reason_length_bleibt_ein_budgetfehler(conn):
    """Fehlerbild 3 aus dem Moduldocstring gilt im Stream genauso."""
    klm = llm.LLM(
        Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=_sse(["halb"], finish="length"))),
        conn,
    )
    with pytest.raises(llm.LLMFehler) as fehler:
        klm.prosa(CHAT, "sys", "nutz", "szene", bei_teil=lambda t: None)
    assert "abgeschnitten" in str(fehler.value)


# -- Rueckfall ---------------------------------------------------------------


def test_abbruch_nach_dem_ersten_stueck_wird_ohne_stream_wiederholt(conn):
    """Entscheidung E: kein halber Text wird zur Nachricht -- die Gruppe
    bekommt die vollstaendige Antwort aus einem zweiten, blockierenden Lauf."""
    versuche = []

    def handler(anfrage):
        body = json.loads(anfrage.content)
        versuche.append(bool(body.get("stream")))
        if body.get("stream"):
            # Zwei Stuecke, dann reisst die Verbindung.
            return httpx.Response(200, content=(
                'data: {"choices": [{"delta": {"content": "Hal"}}]}\n\n'
                'data: {"choices": [{"delta": {"content": "lo"}}]}\n\n'
            ).encode("utf-8") + b"data: {kaputt")
        return httpx.Response(200, json=_FERTIG)

    abbrueche = []

    class Senke:
        def __call__(self, text):
            pass

        def abbruch(self):
            abbrueche.append(True)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    ergebnis = klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                          bei_teil=Senke())
    assert ergebnis == {"antwort": "Hallo ihr"}
    assert versuche == [True, False]
    assert abbrueche == [True]
    # Genau EINE Buchung, obwohl zwei HTTP-Aufrufe noetig waren: der Zug ist
    # einer, und ``_anfrage`` bucht im finally.
    assert conn.execute("SELECT COUNT(*) FROM aufruf").fetchone()[0] == 1


def test_ein_4xx_auf_stream_faellt_still_zurueck(conn):
    """Kennt der Anbieter ``stream`` nicht, laeuft der Zug blockierend weiter --
    und der Vorfall sagt einmal, warum."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            return httpx.Response(400, json={"error": "unknown parameter"})
        return httpx.Response(200, json=_FERTIG)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    assert klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                      bei_teil=lambda t: None) == {"antwort": "Hallo ihr"}
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "strom_nicht_verfuegbar" in arten


def test_nach_einem_fehlschlag_streamt_der_prozess_nicht_mehr(conn):
    """Eine Prozessflagge, kein Dauerversuch: der zweite Aufruf geht sofort
    blockierend -- sonst zahlte jede Antwort den Fehlversuch mit."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            return httpx.Response(400, json={"error": "unknown parameter"})
        return httpx.Response(200, json=_FERTIG)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
               bei_teil=lambda t: None)
    assert llm.strom_moeglich() is False
    teile = []
    klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
               bei_teil=teile.append)
    assert teile == []


def test_ohne_usage_wird_nicht_zweimal_bezahlt(conn):
    """Abweichung 2 im Plan-Kopf: eine fehlende usage merkt man erst am ENDE.
    Den Aufruf zu wiederholen kostete eine zweite Generierung und zeigte der
    Gruppe denselben Text zweimal. Also: Vorfall, Prozessflagge, weiter."""
    klm = llm.LLM(
        Einstellungen(),
        _klient(lambda a: httpx.Response(200, content=_sse(_STUECKE, usage=False))),
        conn,
    )
    ergebnis = klm.schema(CHAT, "sys", "nutz", {"type": "object"}, "gespraech",
                          bei_teil=lambda t: None)
    assert ergebnis == {"antwort": "Hallo ihr"}
    assert conn.execute("SELECT COUNT(*) FROM aufruf").fetchone()[0] == 1
    zeile = _aufrufzeile(conn)
    assert zeile["erfolg"] == 1 and zeile["tatsaechliche_token"] is None
    assert zeile["geschaetzte_token"] > 0     # E7 steht nie ganz ohne Zahl da
    assert llm.strom_moeglich() is False
