"""Karte t_2b9d2cbe: Belegpflicht der Begruendung im Begriffsboard (D1, D2).

Alle Beispiele sind frei erfunden -- keine Zeile aus betrieb/padua.db."""

import pytest

from interview_theater import begriffsboard as bb

TRANSKRIPT = (
    "okay test test eins zwei drei. also der erste Gepäck ist Heimat. "
    "Heimat, weil meine Oma jeden Sonntag für zwanzig Leute kocht. "
    "the first term is lighthouse. I'd suggest silence."
)


# -- Wortlisten ----------------------------------------------------------------

@pytest.mark.parametrize("liste", ["_STOPPWOERTER", "_ANSAGEWOERTER", "_METAWOERTER"])
def test_wortlisten_stehen_in_casefold_form(liste):
    """_woerter vergleicht casefold -- ein Eintrag mit Grossbuchstaben oder
    'ß' wuerde nie treffen."""
    for wort in getattr(bb, liste):
        assert wort == wort.casefold(), wort


def test_beleg_min_ist_zwei():
    assert bb.BELEG_MIN_INHALTSWOERTER == 2


# -- inhaltswoerter -----------------------------------------------------------

@pytest.mark.parametrize("text, begriff, erwartet", [
    ("the first term is lighthouse", "lighthouse", []),
    ("I'd suggest silence", "silence", []),
    ("also der erste Gepäck ist Heimat", "Heimat", []),
    ("Mikrofon Test eins zwei drei 1 2 3", "Heimat", []),
    ("weil meine Oma jeden Sonntag für zwanzig Leute kocht", "Heimat",
     ["oma", "jeden", "sonntag", "zwanzig", "leute", "kocht"]),
    ("wo meine Oma kocht", "Heimat", ["oma", "kocht"]),
    ("KI-Roboter, der alles mitschreibt", "KI-Roboter", ["mitschreibt"]),  # "alles" ist Stoppwort
])
def test_inhaltswoerter(text, begriff, erwartet):
    assert bb.inhaltswoerter(text, begriff) == erwartet


# -- traegt_beleg -------------------------------------------------------------

def _e(zitat, begriff="Heimat", begruendung="egal"):
    return {"begriff": begriff, "zitat": zitat, "begruendung": begruendung}


def test_beleg_mit_inhalt_traegt():
    assert bb.traegt_beleg(_e("weil meine Oma jeden Sonntag für zwanzig Leute kocht"), TRANSKRIPT)


def test_leeres_zitat_traegt_nicht():
    assert not bb.traegt_beleg(_e(""), TRANSKRIPT)


def test_nicht_woertliches_zitat_traegt_nicht():
    assert not bb.traegt_beleg(_e("weil die Oma immer kocht und backt"), TRANSKRIPT)


def test_nur_ansage_traegt_nicht():
    assert not bb.traegt_beleg(_e("also der erste Gepäck ist Heimat"), TRANSKRIPT)
    assert not bb.traegt_beleg(_e("the first term is lighthouse", "lighthouse"), TRANSKRIPT)


def test_ein_restwort_traegt_nicht():
    transkript = "die Sprecherin nennt Heimat als besten Begriff"
    assert not bb.traegt_beleg(_e("Heimat als besten Begriff"), transkript)


# -- ist_fuellsatz ------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Wird als Begriff gesammelt.",
    "Wird als dritter Begriff gesammelt.",
    "Wird als etwas Erwähntes aufgeführt.",
    "Wurde im Gespräch genannt.",
    "Kam zweimal vor.",
    "Die Sprecherin schlägt es als ersten Gepäck vor.",
    "Die Gruppe nennt es als Begriff.",
    "Is mentioned as a term.",
    "Was suggested by the group.",
    "Came up twice.",
    "The speaker proposes it as the first term.",
])
def test_fuellsatz_wird_erkannt(text):
    assert bb.ist_fuellsatz(text)


@pytest.mark.parametrize("text", [
    "",
    "Wo die Oma kocht.",
    "Heimat ist für sie der Ort, an dem die Oma sonntags kocht.",
    "Wird genannt, weil die Oma dort jeden Sonntag kocht.",
    "It was named because the grandfather kept the light on every night.",
    "The pier is where the old men tell their stories.",
])
def test_echter_grund_ist_kein_fuellsatz(text):
    assert not bb.ist_fuellsatz(text)


# -- ist_metabegriff ----------------------------------------------------------

@pytest.mark.parametrize("begriff", [
    "Begriff", "Term", "Gepäck", "GEPÄCK", "Gepaeck", "Betreff", "Test",
    "Test 1 2 3", "Mikrofon Test", "microphone", "Wort",
])
def test_metabegriff(begriff):
    assert bb.ist_metabegriff(begriff)


@pytest.mark.parametrize("begriff", [
    "Heimat", "KI", "KI-Roboter", "Alice Hotel", "Cappuccino", "eins", "", None,
])
def test_kein_metabegriff(begriff):
    assert not bb.ist_metabegriff(begriff)
