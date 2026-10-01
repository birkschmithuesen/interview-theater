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


# --- Teil 2: der Wortzaehler und der Rahmen je Form -----------------------

from interview_theater import laengen  # noqa: E402


def test_der_zaehler_zaehlt_woerter_und_keine_satzzeichen():
    """EINE Zaehlung fuer Eichung, Budget, Nachzaehlen und Befund -- gemessen
    wie die Eichung vom 30.09.2026: Markdown weg, dann Tokens ``\\w+('\\w+)?``."""
    assert laengen.zaehle_woerter("Zwei Woerter.") == 2
    assert laengen.zaehle_woerter("Eins, zwei -- drei!") == 3
    assert laengen.zaehle_woerter("**Am Steg**") == 2
    assert laengen.zaehle_woerter("## 1. Am Steg") == 3   # "1" zaehlt mit
    assert laengen.zaehle_woerter("don't stop") == 2
    assert laengen.zaehle_woerter("") == 0
    assert laengen.zaehle_woerter(None) == 0


def test_der_zaehler_zaehlt_auch_regieanweisungen_mit():
    """Anders als ``sprecher._worte``: fuer ein Laengenbudget zaehlt alles,
    was auf dem Blatt steht -- eine Seite Regie ist eine Seite."""
    # MIRA, steht, auf, Nein -- die Regie "(steht auf)" zaehlt mit.
    assert laengen.zaehle_woerter("MIRA: (steht auf) Nein.") == 4


def test_aus_ist_der_vorgabezustand():
    assert laengen.aktiv() is False
    assert laengen.sprachpass_aktiv() is False


def test_padua_ist_an(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert laengen.aktiv() is True
    assert laengen.sprachpass_aktiv() is True


def test_der_rahmen_kommt_aus_dem_profil(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert laengen.rahmen_fuer("chor") == (80, 200)
    assert laengen.rahmen_fuer("rap") == (120, 250)
    assert laengen.rahmen_fuer("dialog") == (200, 450)


def test_eine_unbekannte_form_nimmt_den_rueckfall(monkeypatch):
    """Ein freier Formwert ("Bewegungsszene") darf kein Absturz sein --
    ``szene.form`` ist ein freies Textfeld."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert laengen.rahmen_fuer("Bewegungsszene") == (200, 450)
    assert laengen.rahmen_fuer(None) == (200, 450)
    assert laengen.rahmen_fuer("  CHOR  ") == (80, 200)   # getrimmt, kleingeschrieben


def test_ein_kaputter_rahmen_faellt_zurueck_statt_zu_werfen(monkeypatch):
    """Die Leser sind nachsichtig, ``scripts/pruefe_profil.py`` ist streng:
    ein Tippfehler in der TOML soll den Start aufhalten, nicht einen Lauf
    mitten im Workshop."""
    monkeypatch.setattr(laengen, "_werte", lambda profil=None: {
        "rahmen": {"chor": [200]}, "vorgabe_min": 200, "vorgabe_max": 450,
    })
    assert laengen.rahmen_fuer("chor") == (200, 450)


def test_die_form_einer_szene_bestaetigt_schlaegt_vorschlag():
    """In Phase 6 ist ``form`` oft leer und ``form_vorschlag`` gesetzt. Das
    Budget LIEST die Form, es SETZT sie nie -- die Regel "die Form bestaetigt
    allein die Gruppe" bleibt unberuehrt."""
    assert laengen.form_der_szene({"form": "chor", "form_vorschlag": "rap"}) == "chor"
    assert laengen.form_der_szene({"form": "", "form_vorschlag": "rap"}) == "rap"
    assert laengen.form_der_szene({"form": None, "form_vorschlag": None}) == \
        workshop.form_vorgabe()
    assert laengen.form_der_szene({}) == workshop.form_vorgabe()
