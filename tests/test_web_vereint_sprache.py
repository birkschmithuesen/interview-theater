"""Padua liest Englisch, Dortmund Deutsch -- aus derselben Seite.

Die Sprachschicht ist Karte A1; hier wird nur geprueft, dass die neuen Texte
dieser Karte wirklich durch sie laufen und dass das Dortmunder Profil dabei
Zeichen fuer Zeichen bleibt.
"""

import pytest

from interview_theater import roadmap, sprache, web_vereint


@pytest.fixture
def englisch(monkeypatch):
    monkeypatch.setenv("IT_WORKSHOP", "padua-2026")
    from interview_theater import workshop

    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def test_die_tabs_heissen_auf_englisch_anders(englisch):
    assert web_vereint.T._TEXT_TAB != web_vereint._TEXT_TAB
    assert set(web_vereint.T._TEXT_TAB) == set(web_vereint._TEXT_TAB)


def test_der_fehlt_hinweis_traegt_seinen_platzhalter(englisch):
    assert "{was}" in web_vereint.T._TEXT_PHASE_FEHLT_HINWEIS


def test_die_roadmap_hat_keine_zweite_texttabelle():
    """Die Aufgabentexte kommen aus ``phasentexte.PARAMETER_BESCHRIFTUNG`` --
    eine Uebersetzung, nicht zwei."""
    import pathlib

    quelle = pathlib.Path(roadmap.__file__).read_text(encoding="utf-8")
    assert "_TEXT_" not in quelle
