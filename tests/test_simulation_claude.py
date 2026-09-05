"""Der Simulationsklient: Anfrageform, Antwortlesen, Reparatur, Wiederholung.

Kein Netz: alles laeuft ueber ``httpx.MockTransport``. Was hier geprueft
wird, ist genau das, was am 05.09.2026 am lebenden Proxy gemessen wurde --
Anthropic-Messages-Format, kein Authorization-Header, Text in
``content[].text``.
"""

import json

import httpx
import pytest

from simulation import claude


def _klient(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _antwort(text: str, ein: int = 42, aus: int = 7) -> httpx.Response:
    return httpx.Response(200, json={
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": ein, "output_tokens": aus},
    })


# --- Anfrage --------------------------------------------------------------


def test_die_anfrage_hat_das_anthropic_format_und_keinen_schluessel():
    """Kein Authorization-Header: den setzt der Proxy. Ein eigener wuerde ihn
    ueberschreiben und der Aufruf schluege mit 401 fehl."""
    gesehen = {}

    def handler(anfrage: httpx.Request) -> httpx.Response:
        gesehen["headers"] = dict(anfrage.headers)
        gesehen["koerper"] = json.loads(anfrage.content)
        return _antwort("OK")

    c = claude.Claude(_klient(handler), basis_url="http://proxy/v1/messages",
                      modellname="claude-opus-5")
    assert c.text("Sei knapp.", "Sag OK") == "OK"

    assert gesehen["headers"]["anthropic-version"] == claude.API_VERSION
    assert "authorization" not in gesehen["headers"]
    assert gesehen["koerper"] == {
        "model": "claude-opus-5",
        "max_tokens": claude.MAX_TOKENS,
        "system": "Sei knapp.",
        "messages": [{"role": "user", "content": "Sag OK"}],
    }


def test_env_setzt_endpunkt_und_modell(monkeypatch):
    monkeypatch.setenv("IT_SIM_URL", "http://anderswo/v1/messages")
    monkeypatch.setenv("IT_SIM_MODELL", "claude-sonnet-5")
    assert claude.url() == "http://anderswo/v1/messages"
    assert claude.modell() == "claude-sonnet-5"


def test_ohne_env_gelten_die_vorgaben(monkeypatch):
    monkeypatch.delenv("IT_SIM_URL", raising=False)
    monkeypatch.delenv("IT_SIM_MODELL", raising=False)
    assert claude.url() == claude.URL_VORGABE
    assert claude.modell() == claude.MODELL_VORGABE


# --- Antwort lesen --------------------------------------------------------


def test_mehrere_textbloecke_werden_zusammengehaengt():
    """Claude darf eine Antwort zerlegen -- und stellt bei aktivem Denken
    einen Denkblock voran. Blind ``content[0]`` zu nehmen liefert dann das
    Denken statt der Antwort."""
    koerper = {"content": [
        {"type": "thinking", "thinking": "hm"},
        {"type": "text", "text": "erste Haelfte"},
        {"type": "text", "text": "zweite Haelfte"},
    ]}
    assert claude._inhalt_aus(koerper) == "erste Haelfte\nzweite Haelfte"


def test_antwort_ohne_textblock_ist_ein_fehler():
    with pytest.raises(claude.ClaudeFehler):
        claude._inhalt_aus({"content": [{"type": "thinking", "thinking": "nur denken"}]})


# --- JSON und der eine Reparaturversuch -----------------------------------


def test_reines_json_wird_direkt_gelesen():
    assert claude.lies_json('{"note": 2}') == {"note": 2}


def test_ein_json_zaun_wird_entfernt():
    text = '```json\n{"note": 1, "satz": "geht so"}\n```'
    assert claude.lies_json(text)["satz"] == "geht so"


def test_ein_zaun_ohne_sprachangabe_wird_auch_entfernt():
    assert claude.lies_json('```\n{"a": 1}\n```') == {"a": 1}


def test_ein_abgeschnittener_zaun_wird_trotzdem_versucht():
    """Ein Text ohne schliessenden Zaun ist der haeufigste Abbruchfall -- was
    davor steht, ist trotzdem der beste Versuch."""
    assert claude.lies_json('```json\n{"a": 1}') == {"a": 1}


def test_kaputtes_json_ist_ein_fehler_und_wird_nicht_geraten():
    """Genau ein Reparaturversuch. Wer anfaengt, fehlende Klammern zu
    ergaenzen, rekonstruiert irgendwann Noten, die das Modell nie vergab."""
    with pytest.raises(claude.ClaudeFehler):
        claude.lies_json('{"note": ')


def test_json_objekt_geht_ueber_den_klienten():
    c = claude.Claude(_klient(lambda a: _antwort('```json\n{"note": 2}\n```')))
    assert c.json_objekt("S", "N", "richter") == {"note": 2}


# --- Wiederholung ---------------------------------------------------------


def test_429_wird_wiederholt(monkeypatch):
    monkeypatch.setattr(claude.time, "sleep", lambda s: None)
    versuche = {"n": 0}

    def handler(anfrage):
        versuche["n"] += 1
        if versuche["n"] < 3:
            return httpx.Response(429, json={"error": "rate"})
        return _antwort("endlich")

    c = claude.Claude(_klient(handler), wartezeiten=(0, 0, 0))
    assert c.text("S", "N") == "endlich"
    assert versuche["n"] == 3


def test_5xx_wird_wiederholt_und_gibt_irgendwann_auf(monkeypatch):
    monkeypatch.setattr(claude.time, "sleep", lambda s: None)
    versuche = {"n": 0}

    def handler(anfrage):
        versuche["n"] += 1
        return httpx.Response(503)

    c = claude.Claude(_klient(handler), wartezeiten=(0, 0))
    with pytest.raises(claude.ClaudeFehler):
        c.text("S", "N")
    assert versuche["n"] == 3


def test_ein_400_wird_nicht_wiederholt():
    """Ein falsches Modell oder ein kaputter Koerper wird beim vierten
    Versuch nicht richtiger -- nur langsamer."""
    versuche = {"n": 0}

    def handler(anfrage):
        versuche["n"] += 1
        return httpx.Response(400, json={"error": "unknown model"})

    c = claude.Claude(_klient(handler))
    with pytest.raises(claude.ClaudeFehler):
        c.text("S", "N")
    assert versuche["n"] == 1


# --- Statistik ------------------------------------------------------------


def test_die_statistik_zaehlt_je_art():
    c = claude.Claude(_klient(lambda a: _antwort('{"note": 2}', ein=100, aus=10)))
    c.text("S", "N", "stimme")
    c.text("S", "N", "stimme")
    c.json_objekt("S", "N", "richter")
    daten = c.statistik.als_dict()
    assert daten["sim_aufrufe"] == 3
    assert daten["sim_aufrufe_je_art"] == {"richter": 1, "stimme": 2}
    assert daten["sim_token_ein"] == 300
    assert daten["sim_token_aus"] == 30
    assert daten["sim_fehler"] == 0


def test_ein_fehlschlag_wird_mitgezaehlt():
    c = claude.Claude(_klient(lambda a: httpx.Response(400)))
    with pytest.raises(claude.ClaudeFehler):
        c.text("S", "N", "stimme")
    assert c.statistik.als_dict()["sim_fehler"] == 1
