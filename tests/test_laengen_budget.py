"""Der Rhythmus-Wuerfel und die Budgets (30.09.2026, Karte R).

Reine Funktionen: kein Modell, keine Datenbank, kein Netz. Gemessen wird,
dass dasselbe Seed dasselbe Muster liefert, dass kein Muster flach wird und
dass die Uebersteuerung greift.
"""

import pytest

from interview_theater import laengen, workshop


@pytest.fixture(autouse=True)
def padua(monkeypatch):
    """Alle Tests hier laufen unter dem Padua-Profil -- ohne aktiven Schalter
    gaebe es nichts zu wuerfeln."""
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


# --- Das Muster -----------------------------------------------------------


def test_dasselbe_seed_liefert_dasselbe_muster():
    """Reproduzierbarkeit ohne gespeicherten Zustand: der Seed IST die
    chat_id, es gibt keinen ``random``-Aufruf."""
    assert laengen.muster_fuer(4711) == laengen.muster_fuer(4711)


def test_verschiedene_seeds_liefern_verschiedene_muster():
    """Vier Muster in der Vorgabe -- ueber vier aufeinanderfolgende Seeds
    muessen mindestens zwei verschiedene dabei sein, sonst wuerfelt es nicht."""
    gesehen = {laengen.muster_fuer(s) for s in range(4)}
    assert len(gesehen) >= 2, gesehen


def test_eine_negative_chat_id_ist_ein_gueltiges_seed():
    """Telegram-Gruppen haben negative ids. Ein Absturz oder ein
    Index-Fehler hier waere ein Ausfall fuer jede echte Gruppe."""
    muster = laengen.muster_fuer(-1001234567890)
    assert muster in tuple(workshop.aktiv().wert("laengen.muster"))


def test_das_muster_wird_zyklisch_gelesen():
    """Die Stufe haengt an der Nummer, nicht an der Gesamtzahl: eine
    nachtraeglich eingefuegte Szene 6 darf das Budget von Szene 1 nicht
    verschieben."""
    muster = ("kurz", "lang", "schlag")
    assert [laengen.stufe_fuer(n, muster) for n in range(1, 8)] == [
        "kurz", "lang", "schlag", "kurz", "lang", "schlag", "kurz",
    ]


def test_eine_fehlende_nummer_gilt_als_erste_szene():
    """``szene.nummer`` darf NULL sein. Dann ist die erste Stufe die
    richtige Vermutung -- eine Ausnahme waere ein Lauf ohne Budget."""
    assert laengen.stufe_fuer(None, ("kurz", "lang")) == "kurz"
    assert laengen.stufe_fuer(0, ("kurz", "lang")) == "kurz"


# --- Flach und Spreizung --------------------------------------------------


def test_flach_heisst_alle_gleich():
    assert laengen.ist_flach(["kurz", "kurz", "kurz"]) is True
    assert laengen.ist_flach(["kurz"]) is True
    assert laengen.ist_flach([]) is True
    assert laengen.ist_flach(["kurz", "lang"]) is False


def test_kein_muster_der_vorgabe_ist_flach():
    """Der Kern der Zusage "nie alle gleich": schon die Tabelle kann es
    nicht."""
    for muster in workshop.aktiv().wert("laengen.muster"):
        stufen = [laengen.stufe_fuer(n, muster) for n in range(1, len(muster) + 1)]
        assert laengen.ist_flach(stufen) is False, muster


def test_die_spreizung_ist_eine_zahl():
    assert laengen.spreizung([100, 200]) == 2.0
    assert laengen.spreizung([200, 200]) == 1.0
    assert laengen.spreizung([]) == 1.0
    assert laengen.spreizung([0, 200]) == 1.0   # keine Division durch Null


@pytest.mark.parametrize("form", ["dialog", "monolog", "chor", "lied", "rap"])
def test_jedes_muster_spreizt_in_jeder_form_ueber_die_mindestgrenze(form):
    """Die Mindestspreizung ist gegen JEDEN Rahmen des Profils geprueft, nicht
    nur gegen den bequemsten -- ein schmaler Rahmen (Chor 80-200) ist der
    harte Fall."""
    for muster in workshop.aktiv().wert("laengen.muster"):
        werte = laengen.budgets([form] * len(muster),
                                nummern=list(range(1, len(muster) + 1)), seed=0)
        # ``budgets`` waehlt das Muster selbst; erzwungen wird hier nur, dass
        # jedes Muster der Tabelle die Grenze haelt.
        assert werte, muster
    for muster in workshop.aktiv().wert("laengen.muster"):
        unten, oben = laengen.rahmen_fuer(form)
        roh = [laengen._aus_stufe(s, unten, oben, 1.0) for s in muster]
        assert laengen.spreizung(roh) >= laengen.SPREIZUNG_MIN, (form, muster, roh)


# --- Die Budgets ----------------------------------------------------------


def test_das_budget_liegt_im_rahmen_der_form():
    for nummer in range(1, 7):
        wert = laengen.budget_fuer(nummer, "chor", seed=1)
        assert 80 <= wert <= 200, (nummer, wert)


def test_das_budget_ist_auf_zehn_gerundet():
    """"247 Woerter" gibt eine Genauigkeit vor, die es nicht gibt."""
    for nummer in range(1, 7):
        for form in ("dialog", "chor", "rap"):
            assert laengen.budget_fuer(nummer, form, seed=3) % 10 == 0


def test_dasselbe_seed_liefert_dasselbe_budget():
    a = laengen.budgets(["dialog"] * 5, nummern=[1, 2, 3, 4, 5], seed=99)
    b = laengen.budgets(["dialog"] * 5, nummern=[1, 2, 3, 4, 5], seed=99)
    assert a == b


def test_budgets_und_budget_fuer_sagen_dasselbe():
    """Zwei Wege zu einer Zahl muessen dieselbe Zahl liefern -- sonst plant
    der Prompt gegen ein anderes Budget als der Nachzaehler prueft."""
    formen = ["dialog", "chor", "rap", "dialog"]
    nummern = [1, 2, 3, 4]
    liste = laengen.budgets(formen, nummern=nummern, seed=7)
    einzeln = [laengen.budget_fuer(n, f, seed=7)
               for n, f in zip(nummern, formen)]
    assert liste == einzeln


def test_eine_folge_aus_einer_form_ist_nicht_flach():
    """Der eigentliche Zweck: vier Dialogszenen duerfen nicht vier gleiche
    Zahlen sein."""
    werte = laengen.budgets(["dialog"] * 4, nummern=[1, 2, 3, 4], seed=5)
    assert len(set(werte)) >= 2, werte
    assert laengen.spreizung(werte) >= laengen.SPREIZUNG_MIN, werte


def test_der_faktor_verkuerzt_alle_budgets():
    """"Instagram": ein Viertel, auf jedes Budget."""
    voll = laengen.budgets(["dialog"] * 3, nummern=[1, 2, 3], seed=2)
    kurz = laengen.budgets(["dialog"] * 3, nummern=[1, 2, 3], seed=2, faktor=0.25)
    assert len(voll) == len(kurz) == 3
    for a, b in zip(voll, kurz):
        assert b < a
        # Gerundet auf 10, also nicht exakt ein Viertel -- aber nah dran.
        assert abs(b - a * 0.25) <= laengen.RUNDUNG


def test_der_faktor_unterschreitet_nie_die_mindestlaenge():
    """0,25 auf den kleinsten Rahmen (Chor 80) ergaebe 20; ein kleinerer
    Faktor duerfte nicht auf 0 fallen -- eine Szene mit null Woertern ist
    keine."""
    werte = laengen.budgets(["chor"] * 3, nummern=[1, 2, 3], seed=1, faktor=0.05)
    assert min(werte) >= laengen.MINDEST_WOERTER, werte


def test_ohne_szenen_gibt_es_keine_budgets():
    assert laengen.budgets([], nummern=[], seed=1) == []


def test_zu_lang_greift_erst_ab_der_schwelle():
    """130 % des Budgets, an EINER Stelle konfiguriert."""
    assert laengen.zu_lang(100, 100) is False
    assert laengen.zu_lang(129, 100) is False
    assert laengen.zu_lang(130, 100) is True
    assert laengen.zu_lang(400, 100) is True
    # Kein Budget heisst keine Beanstandung.
    assert laengen.zu_lang(400, 0) is False
