"""Die Prompt-Bausteine des Laengen-Rhythmus (30.09.2026, Karte R).

Die Bausteine sind Text, kein Modellaufruf: derselbe Stand liefert denselben
Block. Gemessen wird, dass jede Zahl genau EINMAL im Block steht, dass der
Block das Budget als Vorrang ausweist (sonst gewinnt die Laengenangabe aus
``formen/prosa.md``) und dass ohne Budget nichts dasteht.
"""

import pytest

from interview_theater import laengen, workshop


@pytest.fixture(autouse=True)
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


def test_der_szenenblock_nennt_das_budget_einmal():
    block = laengen.block_szene(320)
    assert "320" in block
    assert block.count("320") == 1
    assert laengen.T.BLOCK_KOPF_SZENE in block


def test_ohne_budget_gibt_es_keinen_block():
    """Datengetrieben wie ``kontext.baue``: ein leerer Block faellt ersatzlos
    weg, und der Nutzertext bleibt zeichengleich."""
    assert laengen.block_szene(0) == ""
    assert laengen.block_prosa([]) == ""


def test_der_prosablock_nennt_jeden_abschnitt_mit_nummer_form_und_budget():
    block = laengen.block_prosa([(1, "chor", 100), (2, "dialog", 450),
                                 (3, "rap", 120)])
    for teil in ("1", "chor", "100", "2", "dialog", "450", "3", "rap", "120"):
        assert teil in block, teil
    # Die Summe steht auch da -- sie tritt an die Stelle der festen Zeile
    # "Insgesamt 1.500 bis 3.500 Woerter".
    assert "670" in block


def test_der_prosablock_bindet_die_abschnittszahl():
    """Ohne Bindung hat eine Liste von Budgets je Abschnitt keinen Adressaten:
    ``kurzgeschichte.ANWEISUNG`` stellt dem Modell die Zahl sonst frei."""
    block = laengen.block_prosa([(1, "chor", 100), (2, "dialog", 450)])
    assert laengen.T.SATZ_BINDUNG.format(anzahl=2) in block


def test_der_block_weist_sich_selbst_als_vorrang_aus():
    """``formen/prosa.md`` und die Formen-Regelbloecke nennen eigene Laengen.
    Steht die Zahl an zwei Stellen, muss eine von beiden ausdruecklich die
    gueltige sein -- sonst ergaenzt das Modell selbst."""
    assert laengen.T.SATZ_VORRANG in laengen.block_szene(300)
    assert laengen.T.SATZ_VORRANG in laengen.block_prosa([(1, "chor", 100)])


def test_die_gesamtzeile_ist_eine_zeile_mit_einer_zahl():
    zeile = laengen.gesamtzeile([100, 450, 120])
    assert "670" in zeile
    assert "\n" not in zeile


def test_die_journalzeile_haelt_seed_muster_und_budgets_fest():
    """Reproduzierbar heisst: ein Mensch kann es nachrechnen. Seed, Muster und
    Faktor stehen deshalb in EINER Journalzeile -- angehaengt, nie geaendert."""
    zeile = laengen.journalzeile(
        seed=-100123, muster=("kurz", "lang", "kurz"), faktor=0.25,
        eintraege=[(1, "chor", 20), (2, "dialog", 110)],
    )
    assert "-100123" in zeile
    assert "kurz" in zeile and "lang" in zeile
    assert "0.25" in zeile or "25" in zeile
    assert "20" in zeile and "110" in zeile
    assert "\n" not in zeile, "eine Journalzeile ist eine Zeile"


def test_die_texte_laufen_ueber_T(monkeypatch):
    """A1-Konvention K1: jeder Nutzertext ist ueber ``T`` erreichbar, damit
    die englische Fassung aus ``sprachen/en/texte.toml`` kommt.

    Abweichung vom Plan: Padua spricht Englisch, also liefert ``T`` dort die
    englische Fassung -- die Gleichheit mit der deutschen Konstante gilt nur
    ohne Profil."""
    assert laengen.T.BLOCK_KOPF_SZENE == "How long this scene should be:"
    assert laengen.T.SATZ_VORRANG != laengen.SATZ_VORRANG
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    assert laengen.T.BLOCK_KOPF_SZENE == laengen.BLOCK_KOPF_SZENE
    assert laengen.T.SATZ_VORRANG == laengen.SATZ_VORRANG
    assert laengen.SATZ_VORRANG in laengen.block_szene(300)
