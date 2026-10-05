"""Das Pruefskript des AGENTS.md-Umzugs (Spec 2026-10-05, Abnahme 2)."""

import subprocess
import sys
from pathlib import Path

from scripts import pruefe_agents_umzug as p

ALT = """# Titel

Erster Absatz,
zweite Zeile.

## Doppelt

Alte Fassung eines Satzes.

## Einmalig

Ein Absatz, der nur hier steht.

## Doppelt

Neue Fassung eines Satzes.
"""


def test_absaetze_tragen_ihre_startzeile():
    assert p.absaetze(ALT)[:2] == [(1, "# Titel"), (3, "Erster Absatz,\nzweite Zeile.")]


def test_normalisiere_glaettet_leerraum_und_ueberschriftsebene():
    assert p.normalisiere("### Kopf\n  a   b\n") == p.normalisiere("# Kopf a b")


def test_doppelte_kapitel_werden_erkannt():
    zeilen = p.doppelte_kapitel_zeilen(ALT)
    assert 8 in zeilen and 16 in zeilen
    assert 12 not in zeilen and 3 not in zeilen


def test_alles_umgezogen_ist_gruen():
    b = p.pruefe(ALT, ALT, set())
    assert b.gruen and not b.fehlend


def test_fehlender_absatz_ist_rot():
    neu = ALT.replace("Ein Absatz, der nur hier steht.", "")
    b = p.pruefe(ALT, neu, set())
    assert not b.gruen
    assert b.fehlend == [(12, "Ein Absatz, der nur hier steht.")]


def test_dublette_mit_ausnahme_ist_gruen_und_wird_gelistet():
    neu = ALT.replace("Alte Fassung eines Satzes.", "")
    b = p.pruefe(ALT, neu, {8})
    assert b.gruen
    assert b.dubletten == [(8, "Alte Fassung eines Satzes.")]


def test_ausnahme_ausserhalb_doppelter_kapitel_ist_ungueltig():
    neu = ALT.replace("Ein Absatz, der nur hier steht.", "")
    b = p.pruefe(ALT, neu, {12})
    assert not b.gruen
    assert 12 in b.ungueltige_ausnahmen


def test_lies_ausnahmen_ignoriert_kommentare(tmp_path):
    d = tmp_path / "a.txt"
    d.write_text("# Kopf\n\n1288  # Fallen, aeltere Fassung\n1300\n", encoding="utf-8")
    assert p.lies_ausnahmen(d) == {1288, 1300}


def test_cli_positivkontrolle(tmp_path):
    """Ein absichtlich entfernter Absatz macht das Skript rot (Exit 1)."""
    alt = tmp_path / "alt.md"
    alt.write_text(ALT, encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Index\n", encoding="utf-8")
    (tmp_path / "docs" / "agents").mkdir(parents=True)
    ziel = tmp_path / "docs" / "agents" / "alles.md"
    ziel.write_text(ALT, encoding="utf-8")
    befehl = [sys.executable, "-m", "scripts.pruefe_agents_umzug",
              "--wurzel", str(tmp_path), "--alt-datei", str(alt)]
    wurzel = Path(__file__).resolve().parent.parent
    gruen = subprocess.run(befehl, cwd=wurzel, capture_output=True, text=True)
    assert gruen.returncode == 0, gruen.stdout
    assert gruen.stdout.strip().splitlines()[-1] == "GRUEN"
    ziel.write_text(ALT.replace("Ein Absatz, der nur hier steht.", ""), encoding="utf-8")
    rot = subprocess.run(befehl, cwd=wurzel, capture_output=True, text=True)
    assert rot.returncode == 1
    assert rot.stdout.strip().splitlines()[-1] == "ROT"
    assert "Z. 12" in rot.stdout
