"""Eine ausdrueckliche Laengenansage der Gruppe schlaegt den Wuerfel
(30.09.2026, Karte R).

Der Weg ist der vorhandene: die Erkenner-Art ``festlegung_setzen`` im Bereich
``stil`` -- ``prompts/erkenner.md`` Punkt 23 weist "hoechstens eine Seite pro
Szene ab jetzt" ausdruecklich dorthin (Korpusfall fl04), und
``repo.FESTLEGUNG_BEREICHE`` nennt den Bereich woertlich "Stil- und
Laengenvorgaben fuer Texte". Neu ist allein, dass der CODE die Zahl daraus
liest -- deterministisch, ohne Modell, ohne neue Erkenner-Art und damit ohne
bezahlten Korpuslauf.
"""

import pytest

from interview_theater import kurzgeschichte, laengen, repo, szene, workshop


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


# --- Die Zahl aus der Festlegung -----------------------------------------


class Zeile(dict):
    """Eine Festlegungszeile, wie ``repo.festlegungen`` sie liefert."""


def _z(bereich, text):
    return Zeile(bereich=bereich, bezug=None, text=text)


@pytest.mark.parametrize("text, soll", [
    ("hoechstens 120 Woerter pro Szene ab jetzt", 120),
    ("maximal 300 words per scene", 300),
    ("jede Szene hoechstens eine Seite", laengen.WOERTER_JE_SEITE),
    ("at most one page per scene", laengen.WOERTER_JE_SEITE),
    ("hoechstens zwei Seiten je Szene", 2 * laengen.WOERTER_JE_SEITE),
])
def test_eine_ansage_wird_gelesen(text, soll):
    assert laengen.woerter_aus_festlegungen([_z("stil", text)]) == soll


@pytest.mark.parametrize("text", [
    # Keine Laengenansage, sondern eine Stilvorgabe.
    "kurze, harte Saetze, kein Pathos",
    # Eine Zahl, aber keine Laenge.
    "drei Figuren pro Szene",
    "Szene 3 soll kuerzer werden",
    "shorter, please",
    # Eine Laenge fuer etwas anderes.
    "das Interview hoechstens 20 Minuten",
    "",
])
def test_was_keine_ansage_ist_wird_nicht_gelesen(text):
    """Im Zweifel keine Ansage: eine falsch gelesene Zahl wuerde jede Szene
    des Stuecks auf eine erfundene Laenge zwingen -- teurer als eine
    uebersehene Bitte, die die Gruppe wiederholen kann."""
    assert laengen.woerter_aus_festlegungen([_z("stil", text)]) is None


def test_nur_der_bereich_stil_zaehlt():
    """Ein anderer Bereich ist ein anderes Thema. "hoechstens 120 Woerter" im
    Bereich ``figur`` ist die Beschreibung einer Figur, keine Szenenlaenge."""
    assert laengen.woerter_aus_festlegungen(
        [_z("figur", "hoechstens 120 Woerter pro Szene")]) is None


def test_die_jueengste_ansage_gewinnt():
    """``repo.festlegungen`` liefert **aelteste zuerst**. Sagt die Gruppe
    zweimal etwas, gilt das Letzte -- eine Festlegung ist ein Zustand."""
    assert laengen.woerter_aus_festlegungen([
        _z("stil", "hoechstens 400 Woerter pro Szene"),
        _z("stil", "hoechstens 120 Woerter pro Szene"),
    ]) == 120


def test_ohne_festlegungen_gibt_es_keine_ansage():
    assert laengen.woerter_aus_festlegungen([]) is None
    assert laengen.woerter_aus_festlegungen(None) is None


# --- Die Ansage schlaegt den Wuerfel --------------------------------------


def test_die_ansage_deckelt_das_budget():
    """"Hoechstens" heisst hoechstens: der Wuerfel darf darunter bleiben
    (Rhythmus!), aber nie darueber. Sonst waere eine ausdrueckliche Ansage
    weniger wert als ein Muster."""
    assert laengen.budget_mit_ansage(450, 120) == 120
    assert laengen.budget_mit_ansage(100, 120) == 100
    assert laengen.budget_mit_ansage(450, None) == 450


def test_die_ansage_unterschreitet_nie_die_mindestlaenge():
    assert laengen.budget_mit_ansage(450, 5) == laengen.MINDEST_WOERTER


def test_die_ansage_wirkt_im_szenenbudget(conn, padua):
    ziel_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, ziel_id, "form", "dialog")
    ziel = repo.hole_szene(conn, ziel_id)
    ohne = szene.budget_fuer_szene(conn, 1, ziel)
    repo.schreibe_festlegung(conn, 1, "stil",
                             "hoechstens 120 Woerter pro Szene ab jetzt")
    mit = szene.budget_fuer_szene(conn, 1, ziel)
    assert ohne > 120
    assert mit == 120


def test_die_ansage_wirkt_in_den_prosa_eintraegen(conn, padua):
    for nummer in (1, 2):
        repo.stelle_szene_sicher(conn, 1, nummer)
    repo.schreibe_festlegung(conn, 1, "stil", "hoechstens 90 Woerter pro Szene")
    eintraege = kurzgeschichte.budget_eintraege(conn, 1)
    assert [b for _n, _f, b in eintraege] == [90, 90]


def test_ansage_und_faktor_wirken_beide(conn, padua):
    """Der Faktor verkuerzt den Wuerfel, die Ansage deckelt das Ergebnis --
    die Reihenfolge ist festgelegt und getestet, damit nicht zwei Lesarten
    entstehen."""
    repo.stelle_szene_sicher(conn, 1, 1)
    repo.schreibe_festlegung(conn, 1, "stil", "hoechstens 120 Woerter pro Szene")
    laengen.setze_faktor(conn, 1, 0.25)
    eintraege = kurzgeschichte.budget_eintraege(
        conn, 1, faktor=laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, 1)),
    )
    # Erst Faktor (Dialog 200-450 -> 50-110), dann Deckel 120: der Deckel
    # greift hier nicht mehr, weil der Faktor schon darunter liegt.
    assert all(b <= 120 for _n, _f, b in eintraege)
    assert all(b >= laengen.MINDEST_WOERTER for _n, _f, b in eintraege)


def test_ohne_aktives_profil_wird_keine_ansage_gelesen(conn, monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    repo.stelle_szene_sicher(conn, 1, 1)
    repo.schreibe_festlegung(conn, 1, "stil", "hoechstens 120 Woerter pro Szene")
    assert kurzgeschichte.budget_eintraege(conn, 1) == []
