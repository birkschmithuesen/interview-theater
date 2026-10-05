"""Karte t_9258d2e9, Aufgabe 2: die fokussierte Analyse-Schicht (D3/D7).
Nicht live -- nur der Rauchtest ruft sie."""

import pathlib
import re

import pytest

from interview_theater import begriffsboard_analyse as analyse

TRANSKRIPT = (
    "The whether in our story should change all the time. First sun, then heavy rain.\n\n"
    "And a storm at the end. The whether gets worse and worse, wind and thunder."
)
BOARD = [{"begriff": "whether", "zitat": "GEHEIMES ZITAT", "begruendung": "GEHEIME BEGRUENDUNG"},
         {"begriff": "Storm"}]


def _alle_objekte(knoten):
    if isinstance(knoten, dict):
        if knoten.get("type") == "object":
            yield knoten
        for wert in knoten.values():
            yield from _alle_objekte(wert)


@pytest.mark.parametrize("schema", [analyse.SCHEMA, analyse.SCHEMA_VERHOERER])
def test_schema_ist_streng(schema):
    objekte = list(_alle_objekte(schema))
    assert objekte
    for objekt in objekte:
        assert objekt["additionalProperties"] is False
        assert set(objekt["required"]) == set(objekt["properties"])


def test_schema_felder():
    assert analyse.SCHEMA["required"] == ["wunsch", "verhoerer"]
    assert analyse.SCHEMA_VERHOERER["required"] == ["verhoerer"]
    paar = analyse.SCHEMA["properties"]["verhoerer"]["items"]["properties"]
    assert set(paar) == {"lesart_falsch", "lesart_richtig", "begruendung_kurz"}


def test_anweisung_kombiniert_und_nur_verhoerer():
    beide = analyse.anweisung()
    nur = analyse.anweisung(("verhoerer",))
    assert "wunsch" in beide and "verhoerer" in beide
    assert "verhoerer" in nur and "wunsch" not in nur
    assert "Not like this:" in beide and "Not like this:" in nur
    assert "not by count" in beide


def test_anweisung_kennt_nur_zwei_varianten():
    with pytest.raises(ValueError):
        analyse.anweisung(("wunsch",))


def test_schema_und_art_je_variante():
    assert analyse.schema_fuer(analyse.TEILE) is analyse.SCHEMA
    assert analyse.schema_fuer(("verhoerer",)) is analyse.SCHEMA_VERHOERER
    assert analyse.art_fuer(analyse.TEILE) == "begriffsboard_analyse"
    assert analyse.art_fuer(("verhoerer",)) == "begriffsboard_verhoerer"


def test_nutzertext_traegt_transkript_und_nur_begriffe():
    text = analyse.nutzertext(TRANSKRIPT, BOARD)
    assert TRANSKRIPT in text
    assert "- whether" in text and "- Storm" in text
    assert "GEHEIM" not in text


def test_validiere_wunsch_nur_fuer_boardbegriffe_und_geklemmt():
    roh = {"wunsch": [{"begriff": "STORM", "wunsch": 9}, {"begriff": "whether", "wunsch": "-5"},
                      {"begriff": "Freiheit", "wunsch": 2}, {"begriff": "storm", "wunsch": -1}, "kaputt"],
           "verhoerer": []}
    assert analyse.validiere(roh, TRANSKRIPT, BOARD)["wunsch"] == {"storm": 2, "whether": -2}


def test_validiere_verhoerer():
    roh = {"wunsch": [], "verhoerer": [
        {"lesart_falsch": " whether ", "lesart_richtig": "weather", "begruendung_kurz": "Rain, sun and storm. " * 30},
        {"lesart_falsch": "whether", "lesart_richtig": "weather", "begruendung_kurz": "doppelt"},
        {"lesart_falsch": "sunshine", "lesart_richtig": "sun", "begruendung_kurz": "steht nicht im Transkript"},
        {"lesart_falsch": "storm", "lesart_richtig": "STORM", "begruendung_kurz": "gleich"},
        {"lesart_falsch": "", "lesart_richtig": "rain", "begruendung_kurz": "leer"},
        "kaputt",
    ]}
    paare = analyse.validiere(roh, TRANSKRIPT, BOARD)["verhoerer"]
    assert [(p["lesart_falsch"], p["lesart_richtig"]) for p in paare] == [("whether", "weather")]
    assert len(paare[0]["begruendung_kurz"]) <= analyse.BEGRUENDUNG_MAX


@pytest.mark.parametrize("roh", [None, "kaputt", [], {"wunsch": "x", "verhoerer": None}])
def test_validiere_kaputt_ist_leer(roh):
    assert analyse.validiere(roh, TRANSKRIPT, BOARD) == {"wunsch": {}, "verhoerer": []}


class _KLM:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, **zusatz):
        self.aufrufe.append((chat_id, system, nutzer, schema, art, zusatz))
        return self.antwort


def test_analysiere_ruft_einmal_mit_modell_und_validiert():
    klm = _KLM({"wunsch": [{"begriff": "storm", "wunsch": 1}], "verhoerer": []})
    ergebnis = analyse.analysiere(klm, TRANSKRIPT, BOARD, modell="google/gemma-4-31B-it")
    assert ergebnis == {"wunsch": {"storm": 1}, "verhoerer": []}
    ((chat_id, system, nutzer, schema, art, zusatz),) = klm.aufrufe
    assert chat_id is None and schema is analyse.SCHEMA and art == analyse.ART
    assert zusatz == {"modell": "google/gemma-4-31B-it"}
    assert system == analyse.anweisung() and nutzer == analyse.nutzertext(TRANSKRIPT, BOARD)


def test_analysiere_ohne_modell_ohne_zusatz_und_nur_verhoerer():
    klm = _KLM({"verhoerer": []})
    analyse.analysiere(klm, TRANSKRIPT, BOARD, teile=("verhoerer",))
    ((_, _, _, schema, art, zusatz),) = klm.aufrufe
    assert schema is analyse.SCHEMA_VERHOERER and art == analyse.ART_VERHOERER and zusatz == {}


def test_kein_live_aufrufer():
    """D3: nicht in den Live-Pfad gehaengt -- nur der Rauchtest ruft es."""
    paket = pathlib.Path(__file__).resolve().parent.parent / "interview_theater"
    treffer = [p.name for p in paket.rglob("*.py")
               if p.name != "begriffsboard_analyse.py"
               and re.search(r"begriffsboard_analyse", p.read_text(encoding="utf-8"))]
    assert treffer == []
