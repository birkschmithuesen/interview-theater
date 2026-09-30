"""Die Knopftabelle: Deutsch unveraendert ueber knoepfe.X und knoepfe.T.X,
Englisch ueber knoepfe.T.X (D3)."""

import pytest

from interview_theater import knoepfe, sprache, workshop


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def test_reexport_bleibt_deutsch():
    assert knoepfe._TEXT_SCHON_BENUTZT == "Das habe ich schon uebernommen."
    assert knoepfe.T._TEXT_SCHON_BENUTZT is knoepfe._TEXT_SCHON_BENUTZT
    assert knoepfe._ERLEDIGT_FUER[2] == "Eure Begriffe"


def test_padua_liest_englisch(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert knoepfe.T._TEXT_SPEICHERN_KNOPF == "Yes, save"
    assert knoepfe.T._ERLEDIGT_FUER[2] == "Your terms"
    assert knoepfe.T.ANWEISUNGEN.keys() == knoepfe.ANWEISUNGEN.keys()
    assert "{{projekt_kurz}}" in knoepfe.T.ANWEISUNG_EROEFFNUNG
    assert "VORSCHLAG EROEFFNUNG:" in knoepfe.T.ANWEISUNG_EROEFFNUNG


def test_englischer_eroeffnungsauftrag_nennt_das_abschluss_token(monkeypatch):
    """Bis Aufgabe 23 liest ``fragen._speichere_eroeffnung`` nur eine Zeile,
    deren Kopf (klein geschrieben) mit "abschluss" beginnt. Der englische
    Auftrag nennt das Token deshalb woertlich -- in Grossbuchstaben, als
    Protokoll-Token wie VORSCHLAG ...: (K6)."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert "'ABSCHLUSS:'" in knoepfe.T.ANWEISUNG_EROEFFNUNG
    assert "ABSCHLUSS".lower().startswith("abschluss")
