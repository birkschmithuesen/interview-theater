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


# -- Fix Runde 1 -------------------------------------------------------------
#
# Vier Befunde aus der Review von Aufgabe 5, reproduziert von /tmp/t5probe.py:
# ein sauberes Verbindungsende ohne Abschlusssignal wurde als volle Antwort
# durchgereicht, eine werfende Senke riss den ganzen Zug mit, ein einzelner
# 429/5xx schaltete das Streaming dauerhaft fuer den Prozess ab, und eine
# reine Denkspur-Antwort loeste einen zweiten, bezahlten Versuch aus.


def test_stream_ohne_abschlusssignal_gilt_als_abbruch(conn):
    """Fix Runde 1, Punkt 1 (KRITISCH): ein sauberes Verbindungsende OHNE
    finish_reason und ohne [DONE] ist ein Abbruch, kein Erfolg -- sonst
    kommt ein abgeschnittener Satz als vollstaendige Antwort durch."""
    versuche = []

    def handler(anfrage):
        body = json.loads(anfrage.content)
        versuche.append(bool(body.get("stream")))
        if body.get("stream"):
            # Ein Stueck, dann schliesst die Verbindung sauber -- kein
            # finish_reason, kein [DONE].
            return httpx.Response(
                200, content=b'data: {"choices":[{"delta":{"content":"Es war "}}]}\n\n'
            )
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Es war einmal ganz"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })

    abbrueche = []

    class Senke:
        def __call__(self, text):
            pass

        def abbruch(self):
            abbrueche.append(True)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    text = klm.prosa(CHAT, "s", "n", "szene", bei_teil=Senke())
    assert text == "Es war einmal ganz"
    assert versuche == [True, False]
    assert abbrueche == [True]          # die vorlaeufige Blase verschwindet
    assert llm.strom_moeglich() is True  # ein Abbruch setzt die Flagge nie
    zeile = _aufrufzeile(conn)
    assert zeile["finish_reason"] == "stop" and zeile["erfolg"] == 1
    # Fix Runde 1, Punkt 6: nur der Nachversuch wird gebucht, der
    # abgerissene Stream zahlt nichts.
    assert conn.execute("SELECT COUNT(*) FROM aufruf").fetchone()[0] == 1


def test_eine_werfende_senke_bricht_den_zug_nicht_ab(conn):
    """Fix Runde 1, Punkt 2: eine Anzeige, die wirft (z. B. eine gesperrte
    Datenbank), darf die Antwort nicht kosten -- nur die Anzeige stoppt,
    der Text wird weiter gesammelt und normal zurueckgegeben."""
    aufrufe = []

    def bad(text):
        aufrufe.append(text)
        raise RuntimeError("db locked")

    inhalt = ("data: " + json.dumps(
        {"choices": [{"delta": {"content": '{"antwort": "Hi"}'},
                      "finish_reason": "stop"}]}
    ) + "\n\ndata: [DONE]\n\n").encode("utf-8")
    klm = llm.LLM(Einstellungen(),
                  _klient(lambda a: httpx.Response(200, content=inhalt)), conn)
    ergebnis = klm.schema(CHAT, "s", "n", {"type": "object"}, "gespraech",
                          bei_teil=bad)
    assert ergebnis == {"antwort": "Hi"}
    assert len(aufrufe) == 1    # die Senke wurde versucht, aber nicht erneut
    assert _aufrufzeile(conn)["erfolg"] == 1


@pytest.mark.parametrize("status", [408, 429, 500, 503])
def test_transiente_fehler_setzen_die_flagge_nicht(conn, status):
    """Fix Runde 1, Punkt 3: Infomaniak drosselt mit 429/5xx statt mit einer
    Warteschlange (AGENTS.md Falle 8) -- ein einzelner Drosselimpuls darf
    nicht jede weitere Antwort des Prozesses auf Nichtstreaming umschalten."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            return httpx.Response(status)
        return httpx.Response(200, json=_FERTIG)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    ergebnis = klm.schema(CHAT, "s", "n", {"type": "object"}, "gespraech",
                          bei_teil=lambda t: None)
    assert ergebnis == {"antwort": "Hallo ihr"}
    assert llm.strom_moeglich() is True


def test_transportfehler_vor_dem_ersten_stueck_faellt_zurueck_ohne_flagge(conn):
    """Fix Runde 1, Punkt 3: ein Verbindungsfehler vor dem ersten Stueck ist
    voruebergehend -- stiller Rueckfall, keine Prozessflagge, kein Vorfall."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            raise httpx.ConnectError("weg", request=anfrage)
        return httpx.Response(200, json=_FERTIG)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    ergebnis = klm.schema(CHAT, "s", "n", {"type": "object"}, "gespraech",
                          bei_teil=lambda t: None)
    assert ergebnis == {"antwort": "Hallo ihr"}
    assert llm.strom_moeglich() is True
    arten = [z["art"] for z in conn.execute("SELECT art FROM vorfall").fetchall()]
    assert "strom_nicht_verfuegbar" not in arten


class _ReisstNachEinemStueck(httpx.SyncByteStream):
    """Liefert ein gueltiges Stueck, dann wirft das Lesen ``fehler``."""

    def __init__(self, fehler):
        self._fehler = fehler

    def __iter__(self):
        yield b'data: {"choices":[{"delta":{"content":"Hal"}}]}\n\n'
        raise self._fehler


@pytest.mark.parametrize("fehler", [
    httpx.DecodingError("kaputt"),
    httpx.StreamClosed(),
    httpx.ReadError("weg"),
])
def test_lesefehler_nach_dem_ersten_stueck_ist_ein_abbruch(conn, fehler):
    """Fix Runde 1, Punkt 5: Dekodier-/Stream-/Transportfehler NACH dem ersten
    Stueck sind ein Abbruch -- Blase weg, EIN blockierender Versuch, keine
    Flagge."""
    versuche = []

    def handler(anfrage):
        body = json.loads(anfrage.content)
        versuche.append(bool(body.get("stream")))
        if body.get("stream"):
            return httpx.Response(200, stream=_ReisstNachEinemStueck(fehler))
        return httpx.Response(200, json=_FERTIG)

    abbrueche = []

    class Senke:
        def __call__(self, text):
            pass

        def abbruch(self):
            abbrueche.append(True)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    ergebnis = klm.schema(CHAT, "s", "n", {"type": "object"}, "gespraech",
                          bei_teil=Senke())
    assert ergebnis == {"antwort": "Hallo ihr"}
    assert versuche == [True, False]
    assert abbrueche == [True]
    assert llm.strom_moeglich() is True
    assert conn.execute("SELECT COUNT(*) FROM aufruf").fetchone()[0] == 1


def test_decoding_fehler_vor_dem_ersten_stueck_faellt_zurueck_ohne_flagge(conn):
    """Fix Runde 1, Punkt 5 (MINOR): httpx.DecodingError ist keine
    httpx.TransportError, muss aber genauso behandelt werden -- vor dem
    ersten Stueck ein stiller, flaggenloser Rueckfall."""
    def handler(anfrage):
        if json.loads(anfrage.content).get("stream"):
            # Deklariert gzip, liefert aber keins -- httpx wirft beim Lesen
            # ``DecodingError``.
            return httpx.Response(200, headers={"content-encoding": "gzip"},
                                  content=b"keine-gzip-daten")
        return httpx.Response(200, json=_FERTIG)

    klm = llm.LLM(Einstellungen(), _klient(handler), conn)
    ergebnis = klm.schema(CHAT, "s", "n", {"type": "object"}, "gespraech",
                          bei_teil=lambda t: None)
    assert ergebnis == {"antwort": "Hallo ihr"}
    assert llm.strom_moeglich() is True


def _sse_reasoning(stuecke, finish="stop"):
    """Wie ``_sse``, aber die Stuecke laufen als ``reasoning_content``."""
    zeilen = []
    for stueck in stuecke:
        zeilen.append("data: " + json.dumps(
            {"choices": [{"delta": {"reasoning_content": stueck}, "finish_reason": None}]}
        ))
    zeilen.append("data: " + json.dumps(
        {"choices": [{"delta": {}, "finish_reason": finish}]}
    ))
    zeilen.append("data: " + json.dumps(
        {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    ))
    zeilen.append("data: [DONE]")
    return ("\n\n".join(zeilen) + "\n\n").encode("utf-8")


def test_reine_denkspur_baut_dieselbe_form_wie_blockierend(conn):
    """Fix Runde 1, Punkt 4: landet die ganze Antwort nur als Denkspur
    (Fehlerbild 2 im Moduldocstring), verhaelt sich der Stream-Pfad wie der
    blockierende -- ``inhalt_aus`` findet ``message.reasoning`` -- statt
    einen zweiten, bezahlten Versuch auszuloesen."""
    teile = []
    klm = llm.LLM(
        Einstellungen(),
        _klient(lambda a: httpx.Response(
            200, content=_sse_reasoning(['{"antw', 'ort": "Hi"}'])
        )),
        conn,
    )
    ergebnis = klm.schema(CHAT, "s", "n", {"type": "object"}, "gespraech",
                          bei_teil=teile.append)
    assert ergebnis == {"antwort": "Hi"}
    assert teile == []    # niemals Denkspur an die Senke (Entscheidung C)
    assert llm.strom_moeglich() is True
    assert conn.execute("SELECT COUNT(*) FROM aufruf").fetchone()[0] == 1


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
