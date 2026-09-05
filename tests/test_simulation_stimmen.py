"""Die drei Personen und der Nutzertext einer Stimme -- ohne Netz."""

import random

import pytest

from simulation import stimmen


def test_jeder_steckbrief_laesst_sich_laden():
    for brief in stimmen.ALLE:
        text = stimmen.lade_profil(brief.schluessel)
        assert len(text) > 200, brief.schluessel


def test_unbekannter_steckbrief_ist_ein_programmierfehler():
    with pytest.raises(ValueError):
        stimmen.lade_profil("freundlich")


def test_jeder_steckbrief_beschreibt_auch_was_die_person_nicht_tut():
    """Die Negativliste ist der Teil, der wirkt: ohne sie schreibt jedes
    Modell dieselbe hoefliche Workshop-Teilnehmerin."""
    for brief in stimmen.ALLE:
        assert "NICHT" in stimmen.lade_profil(brief.schluessel), brief.schluessel


def test_jeder_steckbrief_nennt_alter_und_herkunft():
    """Personen, nicht Sprachstile: eine Schreibweise hat keinen Grund, und
    ohne Grund wird jede Stimme in jedem Schritt gleich kooperativ."""
    for brief in stimmen.BESETZUNG:
        text = stimmen.lade_profil(brief.schluessel)
        assert "Wer du bist:" in text, brief.schluessel
        assert "Dein Ziel im Workshop:" in text, brief.schluessel


def test_jede_person_hat_ein_eigenes_ziel():
    ziele = {b.ziel for b in stimmen.BESETZUNG}
    assert len(ziele) == 3
    assert all(z for z in ziele)


def test_drei_personen_feste_besetzung():
    personen = stimmen.personen(random.Random(1))
    assert [p.name for p in personen] == ["Guelten", "Dilan", "Halyna"]
    assert [p.profil for p in personen] == [b.schluessel for b in stimmen.BESETZUNG]


def test_der_seed_aendert_die_besetzung_nicht_mehr():
    """Sie sind Personen, keine Wuerfe aus einem Pool -- der Seed variiert nur
    noch, wer wann spricht."""
    assert stimmen.personen(random.Random(7)) == stimmen.personen(random.Random(99))


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


def test_wer_dem_computer_am_wenigsten_traut_schreibt_am_seltensten():
    """Guelten tippt mit einem Finger und misstraut dem Ding -- eine Gruppe,
    in der alle drei gleich viel schreiben, gibt es nicht."""
    assert min(stimmen.BESETZUNG, key=lambda b: b.gewicht).schluessel == "guelten"

    personen = stimmen.personen(random.Random(1))
    zufall = random.Random(5)
    zaehler = {p.name: 0 for p in personen}
    for _ in range(3000):
        for person in stimmen.waehle_sprecher(zufall, personen):
            zaehler[person.name] += 1
    assert zaehler["Guelten"] < zaehler["Halyna"] < zaehler["Dilan"]


def test_leere_kandidatenliste_liefert_keine_stimme():
    assert stimmen.waehle_sprecher(random.Random(1), []) == []


def test_nutzertext_enthaelt_verlauf_ziel_und_namen():
    person = stimmen.aus_steckbrief(stimmen.BESETZUNG[2])
    verlauf = [{"absender": "Bot", "text": "Soll ich das notieren?"}]
    text = stimmen.baue_nutzertext(person, verlauf, "Ihr wollt Begriffe durchgeben.")
    assert "Bot: Soll ich das notieren?" in text
    assert "Ihr wollt Begriffe durchgeben." in text
    assert "als Halyna" in text


def test_das_eigene_ziel_steht_vor_dem_schrittziel():
    """Die Gruppe will das eine, die Person daneben noch etwas anderes -- an
    der Reibung zwischen beidem zeigt sich, ob der Bot zuhoert."""
    person = stimmen.aus_steckbrief(stimmen.BESETZUNG[1])
    text = stimmen.baue_nutzertext(person, [], "Ihr wollt Begriffe durchgeben.")
    assert text.index(person.ziel) < text.index("Ihr wollt Begriffe durchgeben.")


def test_ein_zusatz_haengt_hinten_am_steckbrief():
    """Die Stelle, an der ``--set birk`` seiner Stimme den echten Chatverlauf
    als Stil-Referenz mitgibt."""
    person = stimmen.aus_steckbrief(stimmen.BIRK, zusatz="So hast du geschrieben: Go")
    assert person.system.startswith(stimmen.lade_profil("birk"))
    assert person.system.endswith("So hast du geschrieben: Go")


def test_nutzertext_kuerzt_den_verlauf_auf_das_fenster():
    person = stimmen.aus_steckbrief(stimmen.BESETZUNG[0])
    verlauf = [{"absender": "Guelten", "text": f"Nachricht {i}"} for i in range(80)]
    text = stimmen.baue_nutzertext(person, verlauf, "Ziel")
    assert "Nachricht 79" in text
    assert "Nachricht 40" not in text


def test_leerer_verlauf_wird_benannt_statt_weggelassen():
    text = stimmen.baue_nutzertext(
        stimmen.aus_steckbrief(stimmen.BESETZUNG[0]), [], "Ziel"
    )
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
    person = stimmen.aus_steckbrief(stimmen.BESETZUNG[0])
    assert stimmen.sprich(sim, person, [], "Ziel") == "ja passt"
    assert sim.gesehen["art"] == stimmen.ART
    assert sim.gesehen["system"] == stimmen.lade_profil("guelten")


def test_leere_antwort_wird_zum_leeren_string():
    person = stimmen.aus_steckbrief(stimmen.BESETZUNG[0])
    assert stimmen.sprich(SimAttrappe(""), person, [], "Z") == ""


def test_sprecherpraefix_und_anfuehrungszeichen_werden_abgeraeumt():
    """Ohne Schema-Modus stellt das Modell gern den eigenen Namen voran --
    und die Kennzahl ``namensanrede`` zaehlte den Bot anschliessend dafuer ab,
    dass er zurueckspiegelt, was die Simulation hineingeschrieben hat."""
    assert stimmen.saeubere("Dilan: ja passt", "Dilan") == "ja passt"
    assert stimmen.saeubere('"ne, das war anders"', "Halyna") == "ne, das war anders"
    assert stimmen.saeubere("Halyna: „warum eigentlich“", "Halyna") == "warum eigentlich"
    # Ein Doppelpunkt mitten im Satz ist kein Praefix.
    assert stimmen.saeubere("also: das passt", "Dilan") == "also: das passt"
