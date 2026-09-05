"""Die fuenfzehn erfundenen Interviews -- Form, Laenge, Zitate, Mischung.

Ohne Netz. Was hier rot wird, wuerde sonst erst in einem bezahlten Lauf
auffallen: ein fehlendes Kopffeld als stille Null im Bericht, ein Soll-Zitat,
das im Text gar nicht steht, als dauerhaft unerfuellbare Kennzahl.
"""

import pytest

from interview_theater import zitat
from simulation import material


@pytest.fixture(scope="module")
def alle():
    return material.lade_alle()


def test_fuenfzehn_interviews_in_drei_sets(alle):
    assert len(alle) == 15
    for nummer in material.SETS:
        assert len(material.lade_set(nummer)) == 5


def test_jedes_interview_hat_einen_vollstaendigen_kopf(alle):
    for interview in alle:
        assert interview.name
        assert interview.nummer in material.SETS
        assert len(interview.themen) >= 2, interview.kennung
        assert interview.sprachmerkmale, interview.kennung
        assert len(interview.zitate_soll) == 3, interview.kennung


def test_wortzahl_liegt_im_erlaubten_bereich(alle):
    for interview in alle:
        assert material.WOERTER_MIN <= interview.woerter <= material.WOERTER_MAX, (
            f"{interview.kennung}: {interview.woerter} Woerter"
        )


def test_sollzitate_stehen_woertlich_im_transkript(alle):
    """Geprueft mit ``zitat.pruefe`` -- genau der Funktion, die im Betrieb
    entscheidet, ob ein Belegzitat stehen bleibt. Eine andere Pruefung hier
    haette zur Folge, dass ein Zitat den Test besteht und die Kennzahl
    trotzdem nie erfuellt wird."""
    for interview in alle:
        for satz in interview.zitate_soll:
            assert zitat.pruefe(satz, interview.transkript), (
                f"{interview.kennung}: {satz!r} steht so nicht im Transkript"
            )


def test_jedes_transkript_hat_zwei_sprecher(alle):
    for interview in alle:
        sprecher = {
            z.split(":", 1)[0] for z in interview.transkript.splitlines()
            if ":" in z and z[:1].isupper() and len(z.split(":", 1)[0].split()) == 1
        }
        assert len(sprecher) >= 2, f"{interview.kennung}: {sprecher}"


# --- Mischung -------------------------------------------------------------


def test_set_liefert_fuenf_interviews_dieses_sets():
    gezogen = material.waehle(ein_set=2, seed=1)
    assert len(gezogen) == 5
    assert {i.nummer for i in gezogen} == {2}


def test_mix_nimmt_je_set_ein_bis_zwei():
    gezogen = material.waehle(mix=[1, 2, 3], seed=3)
    assert len(gezogen) == 5
    je_set = {n: sum(1 for i in gezogen if i.nummer == n) for n in (1, 2, 3)}
    assert all(1 <= anzahl <= 2 for anzahl in je_set.values()), je_set


def test_seed_allein_zieht_aus_allen_fuenfzehn():
    gezogen = material.waehle(seed=11)
    assert len(gezogen) == 5
    assert len({i.kennung for i in gezogen}) == 5


def test_gleicher_seed_gleiche_auswahl_und_reihenfolge():
    """Ohne das waere ein zweiter Lauf nach einer Prompt-Aenderung nicht mit
    dem ersten vergleichbar -- und genau dafuer gibt es den Simulator."""
    for kwargs in ({"seed": 4}, {"ein_set": 1, "seed": 4}, {"mix": [1, 3], "seed": 4}):
        erste = [i.kennung for i in material.waehle(**kwargs, anzahl=4)]
        zweite = [i.kennung for i in material.waehle(**kwargs, anzahl=4)]
        assert erste == zweite


def test_verschiedene_seeds_ergeben_verschiedene_reihenfolgen():
    a = [i.kennung for i in material.waehle(seed=1)]
    b = [i.kennung for i in material.waehle(seed=2)]
    assert a != b


def test_unmoegliche_verteilung_wird_abgelehnt():
    with pytest.raises(ValueError):
        material.waehle(mix=[1, 2], seed=1, anzahl=5)


# --- Kopf-Parser ----------------------------------------------------------


def test_kopf_ohne_trenner_ist_ein_fehler(tmp_path):
    pfad = tmp_path / "kaputt.md"
    pfad.write_text("name: X\n\nText", encoding="utf-8")
    with pytest.raises(ValueError, match="kein Kopf"):
        material.lade(pfad)


def test_fehlendes_kopffeld_ist_ein_fehler(tmp_path):
    pfad = tmp_path / "unvollstaendig.md"
    pfad.write_text(
        "---\nname: X\nset: 1\nthemen: [a, b]\nsprachmerkmale: [c]\n---\nText",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="zitate_soll"):
        material.lade(pfad)


def test_listenzeilen_zerbrechen_nicht_an_kommas(tmp_path):
    """Die Soll-Zitate sind ganze Saetze und enthalten Kommas -- eine Liste,
    die am Komma trennt, wuerde sie stillschweigend zerlegen."""
    pfad = tmp_path / "ok.md"
    pfad.write_text(
        "---\nname: X\nset: 1\nthemen: [a, b]\nsprachmerkmale: [c]\n"
        "zitate_soll:\n  - Erst dies, dann das.\n  - Und noch ein Satz.\n"
        "---\nText",
        encoding="utf-8",
    )
    geladen = material.lade(pfad)
    assert geladen.zitate_soll == ("Erst dies, dann das.", "Und noch ein Satz.")


# --- Begriffe und Fragen --------------------------------------------------


def test_begriffe_kommen_aus_den_themen_und_sind_dublettenfrei(alle):
    import random

    gezogen = material.waehle(ein_set=1, seed=1)
    begriffe = material.begriffe(gezogen, random.Random(1))
    assert material.BEGRIFFE_MIN <= len(begriffe) <= material.BEGRIFFE_MAX
    assert len(set(begriffe)) == len(begriffe)
    erlaubt = {t for i in gezogen for t in i.themen}
    assert set(begriffe) <= erlaubt


def test_fragenvorschlag_traegt_ein_thema_vor_dem_doppelpunkt():
    """Dasselbe Format, das ``erkenner.fragen_setzen`` erwartet und das die
    Gruppenseite fett setzen kann."""
    text = material.fragenvorschlag(["Koffer", "Bahnhof"])
    for zeile in text.splitlines():
        assert ":" in zeile


def test_teile_zerlegt_ohne_etwas_zu_verlieren(alle):
    interview = alle[0]
    stuecke = interview.teile(2)
    assert len(stuecke) == 2
    zusammen = " ".join(" ".join(s.split()) for s in stuecke)
    assert " ".join(interview.transkript.split()) == zusammen
