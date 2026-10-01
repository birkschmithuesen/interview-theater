"""Die Doku nennt, was diese Karte gebaut hat (30.09.2026, Karte R).

Kein Stilwaechter: geprueft wird nur, dass ein Mensch, der AGENTS.md liest,
die drei neuen Module, die neue Spalte, den Profilabschnitt und die beiden
neuen ``art``-Werte ueberhaupt findet. Ein Modul, das dort fehlt, wird beim
naechsten Umbau versehentlich umgangen.
"""

from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
AGENTS = (WURZEL / "AGENTS.md").read_text(encoding="utf-8")
LIESMICH = (WURZEL / "workshop" / "padua-2026" / "LIESMICH.md").read_text(
    encoding="utf-8")


@pytest.mark.parametrize("modul", ["laengen.py", "sprachpass.py", "nachpass.py"])
def test_jedes_neue_modul_steht_in_der_modultabelle(modul):
    assert modul in AGENTS, modul


@pytest.mark.parametrize("name", ["laengen", "sprachpass", "nachpass"])
def test_jedes_neue_modul_steht_in_der_modulkarte(name):
    """Die Modulkarte sagt, in welche Richtung die Abhaengigkeiten zeigen --
    ``laengen`` und ``sprachpass`` sind Fachlogik, ``nachpass`` auch."""
    karte = AGENTS[AGENTS.index("## Modulkarte"):]
    assert f"`{name}.py`" in karte, name


def test_die_neue_spalte_steht_in_agents():
    assert "laengen_faktor" in AGENTS


def test_der_profilabschnitt_steht_in_agents():
    assert "[laengen]" in AGENTS
    assert "[sprachpass]" in AGENTS


@pytest.mark.parametrize("art", ["szene_nachpass", "kurzgeschichte_nachpass"])
def test_die_neuen_aufruf_arten_stehen_in_agents(art):
    """Wie ``dramaturgie_b1``: damit Dashboard und Kostenzeile den Weg
    getrennt sehen -- und damit jemand weiss, wonach er zaehlen kann."""
    assert art in AGENTS, art


def test_agents_nennt_die_zusage_an_dortmund():
    assert "aktiv = false" in AGENTS.lower()


def test_agents_nennt_den_einen_lauf():
    """Die Zahl, an der der Kostendeckel haengt."""
    abschnitt = AGENTS[AGENTS.index("Laengen-Rhythmus"):]
    assert "genau ein" in abschnitt.lower() or "GENAU EIN" in abschnitt


def test_die_liesmich_des_padua_profils_nennt_die_rahmenwerte():
    assert "[laengen" in LIESMICH
    assert "vorschlag" in LIESMICH.lower()


def test_der_befund_ist_verlinkt():
    assert "padua-r-laengen-2026-09-30" in AGENTS
