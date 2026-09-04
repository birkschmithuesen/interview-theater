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


def test_sprich_nimmt_das_gespraechsmodell_und_liefert_die_nachricht():
    gesehen = {}

    class KLM:
        def schema(self, chat_id, system, nutzer, schema, art, modell=None,
                   temperature=None):
            gesehen.update(art=art, modell=modell, system=system)
            return {"nachricht": "  ja passt  "}

    class E:
        llm_modell = "kimi"

    person = stimmen.Person("Jo", "knapp")
    assert stimmen.sprich(KLM(), E(), person, [], "Ziel") == "ja passt"
    assert gesehen["art"] == stimmen.ART
    assert gesehen["modell"] == "kimi"
    assert gesehen["system"] == stimmen.lade_profil("knapp")


def test_leere_antwort_wird_zum_leeren_string():
    class KLM:
        def schema(self, *a, **k):
            return {}

    class E:
        llm_modell = "kimi"

    assert stimmen.sprich(KLM(), E(), stimmen.Person("Jo", "knapp"), [], "Z") == ""
