"""Laengen-Rhythmus je Szene (30.09.2026, Karte R) -- Teil 1: das Profil.

Der Hauptschalter ``laengen.aktiv`` steht im eingebauten Vorgabeprofil auf
``False``, und das ist die Zusage an Dortmund: ohne ``IT_WORKSHOP`` und mit
``IT_WORKSHOP=dortmund-2026`` aendert sich kein Zeichen an einem Prompt.
"""

import pytest

from interview_theater import workshop

STUFEN = ("schlag", "kurz", "mittel", "lang")


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    yield
    workshop.vergiss()


def test_die_vorgabe_hat_den_schalter_aus():
    """Die Zusage an Dortmund, als Test statt als Absichtserklaerung."""
    assert workshop.VORGABE.wert("laengen.aktiv") is False
    assert workshop.VORGABE.wert("sprachpass.aktiv") is False


def test_dortmund_hat_den_schalter_ebenfalls_aus(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    profil = workshop.aktiv()
    assert profil.wert("laengen.aktiv") is False
    assert profil.wert("sprachpass.aktiv") is False


def test_die_vorgabewerte_stehen_fest():
    v = workshop.VORGABE
    assert v.wert("laengen.kurz_faktor") == 0.25
    assert v.wert("laengen.nachzaehl_schwelle") == 1.3
    assert v.wert("laengen.vorgabe_min") == 200
    assert v.wert("laengen.vorgabe_max") == 450
    assert v.wert("sprachpass.gedankenstriche_je_1000") == 6.0
    assert v.wert("sprachpass.nicht_sondern_je_1000") == 2.0
    assert v.wert("sprachpass.adjektiv_dreier_je_1000") == 2.0
    assert v.wert("sprachpass.fazitsatz_je_text") == 1


def test_jedes_muster_traegt_mindestens_zwei_verschiedene_stufen():
    """"Nie alle gleich" faengt in der Tabelle an, nicht erst im Ergebnis:
    ein Muster aus einer einzigen Stufe koennte gar nichts anderes als flach
    werden."""
    muster = workshop.VORGABE.wert("laengen.muster")
    assert muster, "keine Muster in der Vorgabe"
    for eintrag in muster:
        assert len(eintrag) >= 2, eintrag
        assert set(eintrag) <= set(STUFEN), eintrag
        assert len(set(eintrag)) >= 2, f"flaches Muster: {eintrag}"


def test_jedes_muster_spannt_von_kurz_bis_lang():
    """Die Spreizung ist eine Zahl, kein Gefuehl: jedes Muster nennt eine
    Stufe mit Gewicht <= 0,2 und eine mit >= 1,0. Sonst kann die numerische
    Mindestspreizung (Aufgabe 3) nicht eingehalten werden."""
    gewicht = {"schlag": 0.0, "kurz": 0.2, "mittel": 0.5, "lang": 1.0}
    for eintrag in workshop.VORGABE.wert("laengen.muster"):
        werte = [gewicht[s] for s in eintrag]
        assert min(werte) <= 0.2, eintrag
        assert max(werte) >= 1.0, eintrag


def test_padua_traegt_die_rahmen_der_karte(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    profil = workshop.aktiv()
    assert profil.wert("laengen.aktiv") is True
    assert profil.wert("sprachpass.aktiv") is True
    rahmen = profil.wert("laengen.rahmen")
    formen = {f["name"] for f in profil.formen["form"]}
    assert rahmen, "Padua ohne Rahmen"
    # Jeder Rahmen gehoert zu einer Form dieses Profils (A8) ...
    assert set(rahmen) <= formen, sorted(set(rahmen) - formen)
    # ... und jede Zahl ist ein Paar min < max.
    for name, paar in rahmen.items():
        assert len(paar) == 2, (name, paar)
        assert 0 < paar[0] < paar[1], (name, paar)
