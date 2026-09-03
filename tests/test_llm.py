import json

import httpx
import pytest

from theatersoap import einstellungen, llm


def _klient(handler):
    """Baut einen httpx.Client mit MockTransport -- kein Netzzugriff (global-constraints.md)."""
    return httpx.Client(transport=httpx.MockTransport(handler))


def _antwort(content=None, reasoning=None, finish_reason="stop",
             prompt_tokens=10, completion_tokens=5, status=200):
    nachricht = {"content": content}
    if reasoning is not None:
        nachricht["reasoning"] = reasoning
    return httpx.Response(
        status,
        json={
            "choices": [{"message": nachricht, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        },
    )


def test_doppelte_klammer_wird_repariert(einst, conn):
    def handler(request: httpx.Request) -> httpx.Response:
        return _antwort(content='{{"a": 1}')

    ergebnis = llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")
    assert ergebnis == {"a": 1}


def test_inhalt_aus_reasoning_wenn_content_null(einst, conn):
    def handler(request: httpx.Request) -> httpx.Response:
        return _antwort(content=None, reasoning='{"a": 2}')

    ergebnis = llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")
    assert ergebnis == {"a": 2}


def test_json_block_wird_aus_umgebendem_text_geschnitten(einst, conn):
    def handler(request: httpx.Request) -> httpx.Response:
        return _antwort(content='Hier ist das Ergebnis: {"a": 3} Vielen Dank.')

    ergebnis = llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")
    assert ergebnis == {"a": 3}


def test_geschweifte_klammer_im_string_beendet_den_block_nicht():
    text = '{"zitat": "sie sagte } und ging"}'
    assert llm.erster_json_block(text) == text


def test_502_wird_wiederholt(einst, conn, monkeypatch):
    schlaf_aufrufe = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: schlaf_aufrufe.append(s))

    versuche = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        versuche["n"] += 1
        if versuche["n"] < 2:
            return httpx.Response(502, json={"error": "bad gateway"})
        return _antwort(content='{"a": 4}')

    ergebnis = llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")

    assert ergebnis == {"a": 4}
    assert versuche["n"] == 2
    assert len(schlaf_aufrufe) == 1


def test_finish_reason_length_ist_fehler_und_vorfall(einst, conn):
    def handler(request: httpx.Request) -> httpx.Response:
        return _antwort(content="{}", finish_reason="length")

    with pytest.raises(llm.LLMFehler):
        llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")

    zeile = conn.execute("SELECT art FROM vorfall WHERE chat_id = 1").fetchone()
    assert zeile is not None
    assert zeile["art"] == "abgeschnitten"


def test_aufruf_wird_protokolliert(einst, conn):
    def handler(request: httpx.Request) -> httpx.Response:
        return _antwort(content='{"a": 5}', prompt_tokens=123, completion_tokens=45)

    llm.LLM(einst, _klient(handler), conn).schema(1, "0123456789", "abc", {}, "extraktor")

    zeile = conn.execute("SELECT * FROM aufruf WHERE chat_id = 1").fetchone()
    assert zeile["tatsaechliche_token"] == 123
    assert zeile["antwort_token"] == 45
    assert zeile["finish_reason"] == "stop"
    assert zeile["erfolg"] == 1
    assert zeile["art"] == "extraktor"
    assert zeile["modus"] == "A"
    assert zeile["geschaetzte_token"] == (len("0123456789") + len("abc")) // 3
    assert zeile["dauer_ms"] is not None


def test_max_tokens_und_reasoning_effort_im_koerper(einst, conn):
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["body"] = json.loads(request.content)
        return _antwort(content="{}")

    llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")

    assert gesehen["body"]["max_tokens"] == llm.MAX_TOKENS
    assert llm.MAX_TOKENS >= 9000
    assert gesehen["body"]["reasoning_effort"] == "none"


def test_api_schluessel_landet_nicht_in_ausnahme(conn, monkeypatch, tmp_path):
    """Der Schluessel steht nur im Authorization-Header. Dieser Test provoziert
    einen HTTP-500-Fall (nach Ausschoepfen aller Wiederholungen) und prueft,
    dass er trotzdem nirgends in str(ausnahme) auftaucht."""
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    geheim = "GEHEIMER_LLM_SCHLUESSEL_999"
    e = einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key=geheim, llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="110416",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "kaputt"})

    with pytest.raises(llm.LLMFehler) as ausnahme_info:
        llm.LLM(e, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")

    meldung = str(ausnahme_info.value)
    assert geheim not in meldung
