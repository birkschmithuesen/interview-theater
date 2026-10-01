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


@pytest.mark.xfail(reason="Aufgabe 4")
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
