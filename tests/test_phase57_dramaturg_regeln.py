"""Phasen 5 und 7: dramaturgische Rolle konsistent zu Phase 4 (07.10.2026, Birk).

Karte t_6177d71f: Phase 5 durfte bisher keine fachliche Beobachtung zu einem
Widerspruch zwischen Zitat und Figur aeussern (nur "Material ist ein Angebot,
kein Einwand"); jetzt darf sie einen erkennbaren Widerspruch benennen, ohne
das Material abzuwerten. Das "Erst fragen, dann vorschlagen"-Boilerplate
griff in Phase 5 kaum (die Zuordnung laeuft automatisch) und wurde durch
eine phasenspezifische Fassung ersetzt. Phase 7 bekommt eine kurze
Identitaetszeile vor den sechs schon bewaehrten Feinschliff-Regeln, deren
Wortlaut unveraendert bleibt (Phase 6 unveraendert: die globale
system.md-Ergaenzung aus Phase 4 deckt den einzigen gepruefte Fall -- einen
strukturell schwachen Szenenuebergang -- bereits ab).

``padua`` (IT_WORKSHOP=padua-2026, sprache.code="en") liefert die englische
Fassung; ohne diese Fixture bleibt ``sprache.code()`` auf der deutschen
Grundkonstante (siehe ``interview_theater/sprache.py``).
"""

import pytest

from interview_theater import kontext, workshop


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


def _flach(text):
    return " ".join(text.split())


def test_englische_phase_5_erlaubt_widerspruchsbeobachtung(padua):
    system = _flach(kontext.system("gruppe1", 5))
    assert "A recognisable contradiction may be named, a value judgement never." in system
    assert "That is dramaturgical framing, not a judgement of the material" in system
    assert "There is hardly any free suggestion-making in this phase" in system


def test_deutsche_phase_5_erlaubt_widerspruchsbeobachtung():
    system = _flach(kontext.system("gruppe4", 5))
    assert "Ein erkennbarer Widerspruch darf benannt werden, eine Abwertung nie." in system
    assert "Das ist dramaturgische Einordnung, keine Bewertung des Materials" in system
    assert "In dieser Phase gibt es kaum freie Vorschlaege" in system


def test_phase_5_behaelt_die_bestehende_grundregel(padua):
    system_en = _flach(kontext.system("gruppe1", 5))
    assert 'Never say something "doesn\'t fit the material"' in system_en


def test_deutsche_phase_5_behaelt_die_bestehende_grundregel():
    system_de = _flach(kontext.system("gruppe4", 5))
    assert 'Sag nie, etwas "passe nicht zum Material"' in system_de


def test_englische_phase_7_traegt_die_dramaturgenzeile(padua):
    system = _flach(kontext.system("gruppe1", 7))
    assert "This is the work of an experienced dramaturge on the text." in system
    # Die sechs bewaehrten Regeln bleiben woertlich unveraendert.
    assert "After EVERY change, output the complete text again." in system


def test_deutsche_phase_7_traegt_die_dramaturgenzeile():
    system = _flach(kontext.system("gruppe4", 7))
    assert "Hier arbeitest du wie ein erfahrener Dramaturg am Text." in system
    assert "Gib nach JEDER Aenderung den vollstaendigen Text neu aus." in system
