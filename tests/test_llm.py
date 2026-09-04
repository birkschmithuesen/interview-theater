import json

import httpx
import pytest

from interview_theater import einstellungen, llm


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
    """Regressionstest: eine geschweifte Klammer innerhalb eines woertlichen
    Zitats (haeufig in Interview-Ausschnitten) darf lies_json nicht aus der
    Fassung bringen -- json.loads ist von sich aus stringbewusst."""
    text = '{"zitat": "sie sagte } und ging"}'
    assert llm.lies_json(text) == {"zitat": "sie sagte } und ging"}


def test_praefix_ein_zeichen_wird_gelesen():
    """Historischer Fehlerfall: die eine ueberzaehlige Klammer vor dem
    eigentlichen JSON (das urspruengliche 'blindes text[1:]'-Fehlerbild)."""
    text = '{{"a": 1}'
    assert llm.lies_json(text) == {"a": 1}


def test_praefix_zwei_zeichen_wird_gelesen():
    """SPEC-kontext-architektur.md § 4.4: das gemessene Praefix-Artefakt war
    ' {{' -- ein Leerzeichen plus eine ueberzaehlige Klammer, also zwei
    Zeichen vor dem eigentlichen JSON, nicht eines. Ein blindes text[1:]
    (die alte Reparatur) haette hier versagt."""
    text = ' {{"a": 1}'
    assert llm.lies_json(text) == {"a": 1}


def test_lies_json_ohne_jedes_json_ist_fehler():
    with pytest.raises(llm.LLMFehler):
        llm.lies_json("nur Fliesstext, kein JSON weit und breit")


def test_zwei_json_bloecke_sind_mehrdeutig():
    """Review-Befund: raw_decode toleriert Text nach dem JSON-Objekt, das
    darf aber kein zweiter JSON-Wert sein -- sonst wuerde der haeufige leere
    Fall ({"aenderungen": []}) den inhaltstragenden zweiten Block still
    verdecken. Genau der beim Absichtserkenner erwartete Normalfall."""
    text = (
        '{"aenderungen": []} '
        '{"aenderungen": [{"art": "kernthema_setzen", "wert": "X"}]}'
    )
    with pytest.raises(llm.LLMFehler, match="mehrdeutig"):
        llm.lies_json(text)


def test_json_mit_nachgestelltem_fliesstext_ohne_weitere_klammer_bleibt_erlaubt():
    text = '{"a": 3} Vielen Dank.'
    assert llm.lies_json(text) == {"a": 3}


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


def test_connect_error_wird_wiederholt_und_als_llmfehler_verpackt(einst, conn, monkeypatch):
    """Das Betriebsszenario 'Infomaniak ist komplett weg' (SPEC § 11.1) zeigt
    sich in der Praxis meist als ConnectError, nicht als HTTP 500 oder
    Timeout. Muss trotzdem wiederholt und am Ende als LLMFehler geworfen
    werden -- der Aufrufer faengt LLMFehler, kein rohes httpx."""
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    aufrufe = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        aufrufe["n"] += 1
        raise httpx.ConnectError("Verbindung abgelehnt")

    with pytest.raises(llm.LLMFehler) as ausnahme_info:
        llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")

    assert not isinstance(ausnahme_info.value, httpx.ConnectError)
    assert aufrufe["n"] == len(llm.WARTEZEITEN) + 1


def test_erfolgreiche_wiederholung_nach_502_zaehlt_als_vorfall(einst, conn, monkeypatch):
    """SPEC § 11.3 Punkt 3: erfolgreiche Wiederholungen erreichen die Gruppe
    nicht, sollen aber als Vorfall http_5xx gezaehlt werden."""
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    versuche = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        versuche["n"] += 1
        if versuche["n"] < 2:
            return httpx.Response(502, json={"error": "bad gateway"})
        return _antwort(content='{"a": 6}')

    ergebnis = llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")

    assert ergebnis == {"a": 6}
    zeilen = conn.execute("SELECT art FROM vorfall WHERE chat_id = 1").fetchall()
    assert [z["art"] for z in zeilen] == ["http_5xx"]


def test_finish_reason_length_ist_fehler_und_vorfall(einst, conn):
    def handler(request: httpx.Request) -> httpx.Response:
        return _antwort(content="{}", finish_reason="length")

    with pytest.raises(llm.LLMFehler) as ausnahme_info:
        llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")

    # SPEC § 4.4: ein abgeschnittenes Ergebnis ist ein Budgetproblem
    # (max_tokens zu klein), kein Formatproblem -- der Fehlertext muss das
    # beim Lesen im Log klarstellen, statt zu einer Parserfehlersuche zu verleiten.
    meldung = str(ausnahme_info.value)
    assert "max_tokens" in meldung
    assert "zu klein" in meldung

    zeile = conn.execute("SELECT art, detail FROM vorfall WHERE chat_id = 1").fetchone()
    assert zeile is not None
    assert zeile["art"] == "abgeschnitten"
    assert "max_tokens" in zeile["detail"]


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


def test_reasoning_effort_wird_immer_gesendet_ohne_dass_schema_es_uebergibt(einst, conn):
    """SPEC § 4.4: reasoning_effort ist bei Infomaniak binaer -- das Feld
    wegzulassen schaltet Reasoning AN, es gibt keine stille Voreinstellung
    'aus'. schema() uebergibt reasoning_effort deshalb gar nicht mehr an
    _anfrage, sondern verlaesst sich auf deren Vorgabewert 'none'. Dieser
    Test waere mit dem alten 'if reasoning_effort:'-Rueckfall bei einem
    leeren/fehlenden Wert rot (Reasoning still eingeschaltet)."""
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["body"] = json.loads(request.content)
        return _antwort(content="{}")

    llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")

    assert "reasoning_effort" in gesehen["body"]
    assert gesehen["body"]["reasoning_effort"] == "none"


def test_modell_parameter_landet_im_koerper(einst, conn):
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["body"] = json.loads(request.content)
        return _antwort(content="{}")

    llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor", modell="foo")

    assert gesehen["body"]["model"] == "foo"


def test_ohne_modell_parameter_gilt_e_llm_modell(einst, conn):
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["body"] = json.loads(request.content)
        return _antwort(content="{}")

    llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")

    assert gesehen["body"]["model"] == einst.llm_modell


def test_temperature_parameter_landet_im_koerper(einst, conn):
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["body"] = json.loads(request.content)
        return _antwort(content="{}")

    llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor", temperature=0.2)

    assert gesehen["body"]["temperature"] == 0.2


def test_reasoning_effort_none_wird_zu_none_string_normalisiert(einst, conn):
    """Review-Befund: reasoning_effort hat den Vorgabewert "none" (str), aber
    Python erzwingt Typannotationen nicht zur Laufzeit. Ein interner
    Aufrufer, der explizit None uebergibt, darf nicht "reasoning_effort":
    null in den Koerper schreiben -- dieselbe binaere Falle eine Ebene
    tiefer (SPEC § 4.4)."""
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["body"] = json.loads(request.content)
        return _antwort(content="{}")

    klm = llm.LLM(einst, _klient(handler), conn)
    klm._anfrage(
        chat_id=1, system="s", nutzer="n", art="extraktor", modus="A",
        response_format=None, reasoning_effort=None,
    )

    assert gesehen["body"]["reasoning_effort"] == "none"


def test_ohne_temperature_parameter_fehlt_das_feld(einst, conn):
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["body"] = json.loads(request.content)
        return _antwort(content="{}")

    llm.LLM(einst, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")

    assert "temperature" not in gesehen["body"]


def test_prosa_schaltet_reasoning_an_und_bekommt_genug_ausgabebudget(einst, conn):
    """Modus B ist der einzige Aufruf mit aktivem Reasoning (SPEC § 4.5,
    interview_theater/szene.py). "an" heisst bei Infomaniak schlicht: irgendein
    Wert ausser "none" -- die Stufen sind untereinander nicht
    unterscheidbar. Dazu die gemessene Randbedingung: mit zu knappem
    max_tokens endet der Lauf IM Denken und liefert HTTP 200 mit leerem
    Inhalt."""
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["body"] = json.loads(request.content)
        return _antwort(content="TITEL: Am Bahnhof")

    text = llm.LLM(einst, _klient(handler), conn).prosa(
        1, "s", "n", "szene", max_tokens=12_000, timeout=150.0,
    )

    assert text == "TITEL: Am Bahnhof"
    assert gesehen["body"]["reasoning_effort"] != "none"
    assert gesehen["body"]["max_tokens"] >= 12_000
    assert "response_format" not in gesehen["body"]


def test_prosa_ohne_eigene_grenzen_bleibt_beim_vorgabebudget(einst, conn):
    """Die zwei neuen Parameter sind additiv: ohne sie verhaelt sich prosa
    wie zuvor."""
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["body"] = json.loads(request.content)
        return _antwort(content="Text")

    llm.LLM(einst, _klient(handler), conn).prosa(1, "s", "n", "szene")

    assert gesehen["body"]["max_tokens"] == llm.MAX_TOKENS


def test_prosa_wird_als_modus_b_protokolliert(einst, conn):
    """Die Tabelle aufruf trennt die Modi -- Grundlage dafuer, dass sich
    Latenz und Tokenverbrauch des Reasoning-Aufrufs spaeter getrennt von den
    Chat-Zuegen auswerten lassen."""
    def handler(request: httpx.Request) -> httpx.Response:
        return _antwort(content="Text")

    llm.LLM(einst, _klient(handler), conn).prosa(1, "s", "n", "szene")

    zeile = conn.execute("SELECT art, modus, erfolg FROM aufruf").fetchone()
    assert (zeile["art"], zeile["modus"], zeile["erfolg"]) == ("szene", "B", 1)


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
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "kaputt"})

    with pytest.raises(llm.LLMFehler) as ausnahme_info:
        llm.LLM(e, _klient(handler), conn).schema(1, "s", "n", {}, "extraktor")

    meldung = str(ausnahme_info.value)
    assert geheim not in meldung
