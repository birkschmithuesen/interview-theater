"""Die Rahmenwerte stehen im Profil UND im Befund -- und beide sagen dasselbe
(30.09.2026, Karte R).

Zwei Orte fuer eine Zahl sind erlaubt, solange ein Test sie aneinanderhaelt.
Ohne diesen Test waere der Befund nach der ersten Aenderung am Profil eine
falsche Aussage ueber den Betrieb -- und genau so ein Dokument hat am
06.09.2026 gefehlt.
"""

import re
from pathlib import Path

import pytest

from interview_theater import laengen, workshop

BEFUND = (Path(__file__).resolve().parent.parent / "docs"
          / "padua-r-laengen-2026-09-30" / "BEFUND.md")


@pytest.fixture(autouse=True)
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


def test_der_befund_existiert():
    assert BEFUND.is_file(), BEFUND


@pytest.mark.parametrize("form", ["dialog", "monolog", "chor", "lied", "rap"])
def test_jeder_rahmen_des_profils_steht_im_befund(form):
    unten, oben = laengen.rahmen_fuer(form)
    text = BEFUND.read_text(encoding="utf-8")
    assert f"{unten}-{oben}" in text or f"{unten}–{oben}" in text, (form, unten, oben)


def test_der_befund_markiert_die_werte_als_vorschlag():
    """Die Karte verlangt es ausdruecklich: "Rahmenwerte als Vorschlag
    markieren"."""
    text = BEFUND.read_text(encoding="utf-8").lower()
    assert "vorschlag" in text and "ungemessen" in text


def test_der_befund_nennt_die_gemessenen_vergleichszahlen():
    """Die Eichung muss belegt sein, nicht behauptet."""
    text = BEFUND.read_text(encoding="utf-8")
    for zahl in ("825", "802", "603", "794", "1400", "2.230"):
        assert zahl in text, zahl


def test_das_profil_markiert_die_werte_ebenfalls():
    """Wer die TOML oeffnet, soll es dort lesen und nicht im Befund suchen."""
    pfad = (Path(__file__).resolve().parent.parent / "workshop"
            / "padua-2026" / "profil.toml")
    text = pfad.read_text(encoding="utf-8").lower()
    assert "vorschlag" in text and "ungemessen" in text


def test_der_grenzwert_liegt_ueber_dem_gemessenen_anker():
    """Ein Grenzwert unter dem gemessenen Normalfall wuerde jeden Text
    beanstanden. Dortmund v2: 0,45 Gedankenstriche je 1.000 Woerter."""
    from interview_theater import sprachpass
    assert sprachpass.grenzwerte()["gedankenstriche"] > 0.45 * 2
