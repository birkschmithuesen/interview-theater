"""Die drei Sprachprofile und der Nutzertext einer Stimme -- ohne Netz."""

import random

import pytest

from simulation import stimmen


def test_alle_drei_profile_lassen_sich_laden():
    for name in stimmen.PROFILE:
        text = stimmen.lade_profil(name)
        assert len(text) > 200, name


def test_unbekanntes_profil_ist_ein_programmierfehler():
    with pytest.raises(ValueError):
        stimmen.lade_profil("freundlich")


def test_jedes_profil_beschreibt_auch_was_es_nicht_tut():
    """Die Negativliste ist der Teil, der wirkt: ohne sie schreibt jedes
    Modell dieselbe hoefliche Workshop-Teilnehmerin."""
    for name in stimmen.PROFILE:
        assert "NICHT" in stimmen.lade_profil(name), name


def test_drei_personen_eine_je_profil():
    personen = stimmen.personen(random.Random(1))
    assert [p.profil for p in personen] == list(stimmen.PROFILE)
    assert len({p.name for p in personen}) == 3


def test_gleicher_seed_gleiche_besetzung():
    assert stimmen.personen(random.Random(7)) == stimmen.personen(random.Random(7))


def test_sprecherwahl_liefert_ein_oder_zwei_verschiedene():
    personen = stimmen.personen(random.Random(1))
    zufall = random.Random(3)
    gesehen = set()
    for _ in range(50):
        gewaehlt = stimmen.waehle_sprecher(zufall, personen)
        assert 1 <= len(gewaehlt) <= 2
        assert len({p.name for p in gewaehlt}) == len(gewaehlt)
        gesehen.add(len(gewaehlt))
    assert gesehen == {1, 2}, "beide Faelle muessen vorkommen"


def test_nutzertext_enthaelt_verlauf_ziel_und_namen():
    person = stimmen.Person("Ines", "skeptisch")
    verlauf = [{"absender": "Bot", "text": "Soll ich das notieren?"}]
    text = stimmen.baue_nutzertext(person, verlauf, "Ihr wollt Begriffe durchgeben.")
    assert "Bot: Soll ich das notieren?" in text
    assert "Ihr wollt Begriffe durchgeben." in text
    assert "als Ines" in text


def test_nutzertext_kuerzt_den_verlauf_auf_das_fenster():
    person = stimmen.Person("Jo", "knapp")
    verlauf = [{"absender": "Jo", "text": f"Nachricht {i}"} for i in range(80)]
    text = stimmen.baue_nutzertext(person, verlauf, "Ziel")
    assert "Nachricht 79" in text
    assert "Nachricht 40" not in text


def test_leerer_verlauf_wird_benannt_statt_weggelassen():
    text = stimmen.baue_nutzertext(stimmen.Person("Jo", "knapp"), [], "Ziel")
    assert "Der Chat ist noch leer" in text


class SimAttrappe:
    """Der Simulationsklient als Attrappe -- kein Netz, merkt sich den
    Aufruf."""

    def __init__(self, antwort=""):
        self.antwort = antwort
        self.gesehen = {}

    def text(self, system, nutzer, art="sim", max_tokens=None):
        self.gesehen.update(art=art, system=system, nutzer=nutzer,
                            max_tokens=max_tokens)
        return self.antwort


def test_sprich_nimmt_das_simulationsmodell_und_liefert_die_nachricht():
    """Die Stimmen laufen NICHT ueber den Bot-Klienten: der Bot ist der
    Prueflung, und ein Prueflung, der seine eigenen Teilnehmerinnen spielt,
    misst vor allem sich selbst."""
    sim = SimAttrappe("  ja passt  ")
    person = stimmen.Person("Jo", "knapp")
    assert stimmen.sprich(sim, person, [], "Ziel") == "ja passt"
    assert sim.gesehen["art"] == stimmen.ART
    assert sim.gesehen["system"] == stimmen.lade_profil("knapp")


def test_leere_antwort_wird_zum_leeren_string():
    assert stimmen.sprich(SimAttrappe(""), stimmen.Person("Jo", "knapp"), [], "Z") == ""


def test_sprecherpraefix_und_anfuehrungszeichen_werden_abgeraeumt():
    """Ohne Schema-Modus stellt das Modell gern den eigenen Namen voran --
    und die Kennzahl ``namensanrede`` zaehlte den Bot anschliessend dafuer ab,
    dass er zurueckspiegelt, was die Simulation hineingeschrieben hat."""
    assert stimmen.saeubere("Jo: ja passt", "Jo") == "ja passt"
    assert stimmen.saeubere('"ne, das war anders"', "Ines") == "ne, das war anders"
    assert stimmen.saeubere("Ines: „warum eigentlich“", "Ines") == "warum eigentlich"
    # Ein Doppelpunkt mitten im Satz ist kein Praefix.
    assert stimmen.saeubere("also: das passt", "Jo") == "also: das passt"
