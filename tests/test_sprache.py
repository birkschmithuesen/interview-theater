"""Der Sprachzugriff: Deutsch ist die Konstante selbst, Englisch die Tabelle."""

import sys
import types

import pytest

from interview_theater import sprache, workshop


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture
def testmodul(monkeypatch):
    """Ein erfundenes Modul mit deutschen Konstanten und eine erfundene
    englische Tabelle -- unabhaengig vom Stand der echten texte.toml."""
    modul = types.ModuleType("interview_theater._sprachtest")
    modul._TEXT_GRUSS = "Hallo {name}, schoen, dass ihr da seid."
    modul._ERLEDIGT = {2: "Eure Begriffe", 3: "Eure Fragen"}
    modul.ZEILEN = ("eins", "zwei")
    modul.LISTE = [{"command": "stand", "description": "Arbeitsstand anzeigen"}]
    monkeypatch.setitem(sys.modules, modul.__name__, modul)
    monkeypatch.setitem(sprache._TABELLEN, "en", {"_sprachtest": {
        "_TEXT_GRUSS": "Hello {name}, good to have you here.",
        "_ERLEDIGT": {"2": "Your terms", "3": "Your questions"},
        "ZEILEN": ["one", "two"],
        "LISTE": [{"command": "stand", "description": "Show where we are"}],
    }})
    return modul


def _englisch(monkeypatch):
    monkeypatch.setattr(sprache, "code", lambda: "en")


def test_deutsch_ist_die_konstante_selbst(testmodul):
    t = sprache.Texte(testmodul.__name__)
    assert t._TEXT_GRUSS is testmodul._TEXT_GRUSS
    assert t._ERLEDIGT is testmodul._ERLEDIGT


def test_deutsch_schlaegt_keine_tabelle_nach(testmodul, monkeypatch, caplog):
    """Im Deutschen gibt es keinen Umweg ueber eine Datei und keine
    Lueckenmeldung -- sonst loggte Dortmund jeden Text als fehlend."""
    def verboten(_code):
        raise AssertionError("Deutsch darf keine Tabelle lesen")

    monkeypatch.setattr(sprache, "tabelle", verboten)
    t = sprache.Texte(testmodul.__name__)
    assert t._TEXT_GRUSS is testmodul._TEXT_GRUSS
    assert "_sprachtest" not in caplog.text


def test_englisch_kommt_aus_der_tabelle(testmodul, monkeypatch):
    _englisch(monkeypatch)
    t = sprache.Texte(testmodul.__name__)
    assert t._TEXT_GRUSS == "Hello {name}, good to have you here."


def test_behaelter_bekommen_ihre_deutsche_form(testmodul, monkeypatch):
    _englisch(monkeypatch)
    t = sprache.Texte(testmodul.__name__)
    assert t._ERLEDIGT == {2: "Your terms", 3: "Your questions"}
    assert t.ZEILEN == ("one", "two")
    assert t.LISTE == [{"command": "stand", "description": "Show where we are"}]


def test_nachgeschlagen_wird_zur_aufrufzeit(testmodul, monkeypatch):
    """Ein Web-Prozess bedient mehrere Gruppen (A2), Tests schalten das
    Profil um -- ein beim Import gemerkter Text waere danach falsch."""
    t = sprache.Texte(testmodul.__name__)
    vorher = t._TEXT_GRUSS
    _englisch(monkeypatch)
    assert t._TEXT_GRUSS != vorher


def test_fehlender_eintrag_bleibt_deutsch_und_meldet_sich(testmodul, monkeypatch, caplog):
    _englisch(monkeypatch)
    testmodul._TEXT_NEU = "Neu hier"
    t = sprache.Texte(testmodul.__name__)
    assert t._TEXT_NEU == "Neu hier"
    assert "_sprachtest._TEXT_NEU" in caplog.text


def test_unbekannte_konstante_ist_ein_programmierfehler(testmodul):
    with pytest.raises(AttributeError):
        sprache.Texte(testmodul.__name__)._TEXT_GIBT_ES_NICHT


def test_texte_sind_nur_lesbar(testmodul):
    with pytest.raises(AttributeError):
        sprache.Texte(testmodul.__name__)._TEXT_GRUSS = "x"


def test_code_whisper_pseudonyme_aus_dem_profil(monkeypatch):
    assert sprache.code() == "de"
    assert sprache.whisper_vorgabe() == "de"
    assert sprache.pseudonyme() is False
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert sprache.code() == "en"
    assert sprache.whisper_vorgabe() == "auto"
    assert sprache.pseudonyme() is True


def test_je_sprache_faellt_auf_deutsch_zurueck(monkeypatch):
    assert sprache.je_sprache({"de": 1, "en": 2}) == 1
    _englisch(monkeypatch)
    assert sprache.je_sprache({"de": 1, "en": 2}) == 2
    assert sprache.je_sprache({"de": 1}) == 1


@pytest.mark.parametrize("text, erwartet", [
    ("Hallo {name}", {"{name}"}),
    ("{nummer:>3} von {gesamt!r}", {"{nummer}", "{gesamt}"}),
    ("worum es geht ({{projekt_kurz}})", {"{{projekt_kurz}}"}),
    ("%s Zeichen, %d Token", {"%s", "%d"}),
    ('JSON {"a": 1} bleibt aussen vor', set()),
])
def test_platzhalter(text, erwartet):
    assert sprache.platzhalter(text) == frozenset(erwartet)


def test_die_echte_tabelle_ist_gueltiges_toml():
    sprache.vergiss()
    assert isinstance(sprache.tabelle("en"), dict)


# --- Morgen-Auftrag 4: Texte(..., sprachcode=...) ---------------------------

def test_sprachcode_erzwingt_sprache_unabhaengig_vom_profil(testmodul, monkeypatch):
    monkeypatch.setitem(sprache._TABELLEN, "it", {"_sprachtest": {
        "_TEXT_GRUSS": "Ciao {name}, bello avervi qui.",
    }})
    t = sprache.Texte(testmodul.__name__, sprachcode="it")
    assert t._TEXT_GRUSS == "Ciao {name}, bello avervi qui."
    # Deutsches Profil (Vorgabe) aendert daran nichts -- sprachcode gewinnt.
    assert sprache.code() == sprache.DEUTSCH


def test_ohne_sprachcode_bleibt_profilsprache(testmodul, monkeypatch):
    _englisch(monkeypatch)
    monkeypatch.setitem(sprache._TABELLEN, "it", {"_sprachtest": {
        "_TEXT_GRUSS": "Ciao {name}, bello avervi qui.",
    }})
    t = sprache.Texte(testmodul.__name__)
    assert t._TEXT_GRUSS == "Hello {name}, good to have you here."
