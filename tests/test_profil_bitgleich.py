"""Dortmund bleibt bitgleich -- mit ``IT_WORKSHOP`` und ohne.

**Das Abnahmekriterium des Profil-Umbaus** (06.09.2026). Alles Individuelle
wandert nach ``workshop/dortmund-2026/``; dabei darf sich an dem, was der
Bot tatsaechlich an ein Modell schickt, **kein Zeichen** aendern. Geprueft
wird dreifach gegen denselben Massstab:

1. ohne ``IT_WORKSHOP`` (eingebautes Vorgabeprofil),
2. mit ``IT_WORKSHOP=dortmund-2026``,
3. gegen ``docs/prompt-audit/schnappschuss-vor-profilumbau.txt`` -- den
   Fingerabdruck aus der Zeit vor dem ersten Umbauschritt.

Der Schnappschuss entsteht in ``scripts/prompt_schnappschuss.py`` und deckt
jede Prompt-Datei, jede zusammengesetzte Systemanweisung, die Formenliste,
die Phasen, die Phasentexte und die Leitfaden-Bausteine ab.

**Warum nicht direkt gegen die 21 Dumps** unter
``docs/prompt-audit/2026-09-06/``? Zwei Gruende, beide gemessen am
06.09.2026: ``scripts/erzeuge_prompts.py`` braucht eine Kopie der
Betriebsdatenbank, die es hier nicht gibt; und ihr Nutzertext-Teil haengt an
echten Interviews. Ihr SYSTEM-Teil dagegen ist rein aus Dateien gebaut --
soweit er zum heutigen Code passt, wird er unten mitgeprueft
(``GOLDEN_SYSTEM``). Die uebrigen Dumps sind seit ``f908b68`` durch den
Feinschliff-Umbau ueberholt und waeren ein falscher Massstab.
"""

import re
from pathlib import Path

import pytest

from interview_theater import (
    anweisungen, erkenner, journal, kernzitate, sprachprofil,
    verdichter, workshop,
)
from scripts import prompt_schnappschuss

WURZEL = Path(__file__).resolve().parent.parent

#: Der festgeschriebene Fingerabdruck vor dem ersten Umbauschritt.
SCHNAPPSCHUSS = WURZEL / "docs" / "prompt-audit" / "schnappschuss-vor-profilumbau.txt"

#: Das Profil, das exakt den Repo-Stand von vor dem Umbau tragen muss.
DORTMUND = "dortmund-2026"

#: Die Prompt-Dumps vom 06.09.2026, deren SYSTEM-Teil heute noch dem Code
#: entspricht -- gemessen, nicht geraten. Die uebrigen 15 sind seit
#: ``f908b68`` ueberholt (Feinschliff-Umbau, Phase 8 -> 7, Stil-Block).
#: Schlaegt hier etwas fehl, ist entweder das Profil undicht oder der Dump
#: veraltet; beides gehoert angesehen und nicht weggedrueckt.
GOLDEN_SYSTEM = {
    "04-erkenner": lambda: erkenner.prompt(),
    "06-verdichter": lambda: verdichter.prompt(),
    "07-journal": lambda: journal.prompt(),
    "08-sprachprofil": lambda: sprachprofil.prompt(),
    "09-kernzitate": lambda: kernzitate.prompt(),
    # "10-schaerfung" entfernt (Birk/Robo 07.10.2026, Zuordnung-Umbau): der
    # Dump vom 06.09.2026 ist jetzt wie die anderen 15 "ueberholt" --
    # schaerfung.prompt() beschreibt seitdem Je-Ziel-Aufrufe statt des
    # Pauschal-Laufs, absichtlich, nicht ein Profil-Leck.
}

_DUMPS = WURZEL / "docs" / "prompt-audit" / "2026-09-06"


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    """Weder Profil noch Prompt-Zwischenspeicher aus einem frueheren Test."""
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


#: Eine Zeile des Fingerabdrucks: Pruefsumme, Laenge (rechtsbuendig), Name.
_ZEILE = re.compile(r"^(\S+)\s+(\d+)\s+(.*)$")


def _fingerabdruck() -> dict[str, str]:
    """Abschnittsname -> ``sha256 laenge``."""
    anweisungen._CACHE.clear()
    zeilen = prompt_schnappschuss.fingerabdruck().splitlines()
    fertig = {}
    for zeile in zeilen:
        pruef, laenge, name = _ZEILE.match(zeile).groups()
        fertig[name] = f"{pruef} {laenge}"
    return fertig


def _vergleiche(erwartet: dict[str, str], jetzt: dict[str, str]) -> None:
    """Jeder Abschnitt des Massstabs muss unveraendert dastehen.

    **Neue** Abschnitte sind erlaubt: eine zusaetzliche Prompt-Datei ist eine
    gewoehnliche Repo-Aenderung und keine Undichtigkeit des Profils -- sie
    kann an dem, was schon da war, nichts verschieben, und genau das prueft
    diese Schleife. Ein **fehlender** Abschnitt ist dagegen immer ein
    Befund."""
    fehlend = sorted(set(erwartet) - set(jetzt))
    assert not fehlend, f"Abschnitt(e) verschwunden: {', '.join(fehlend)}"
    abweichend = [
        f"\n  {name}\n    erwartet: {erwartet[name]}\n    bekommen: {jetzt[name]}"
        for name in erwartet if erwartet[name] != jetzt[name]
    ]
    assert not abweichend, "".join(abweichend)


def _massstab() -> dict[str, str]:
    fertig = {}
    for zeile in SCHNAPPSCHUSS.read_text(encoding="utf-8").splitlines():
        pruef, laenge, name = _ZEILE.match(zeile).groups()
        fertig[name] = f"{pruef} {laenge}"
    return fertig


@pytest.mark.dortmund  # Dortmund eingefroren (AGENTS.md, 04.10.2026): Formberater-Prompt-Haertung (system.md/phasen/4.md, Karte t_256ec777/t_b19d37ac) aendert auch den Dortmund-/Vorgabe-Fingerabdruck
def test_ohne_variable_wie_vor_dem_umbau():
    """Ohne ``IT_WORKSHOP`` entspricht dem eingefrorenen Dortmund-Verhalten
    (``test_dortmund_und_keine_variable_sind_identisch``) -- eine Padua-only
    Prompt-Haertung (``prompts/phasen/4.md``, Karte Phase 4->5
    Szenentext-Abgrenzung) macht diesen Massstab bewusst rot, siehe
    AGENTS.md "Dortmund eingefroren"."""
    _vergleiche(_massstab(), _fingerabdruck())


@pytest.mark.dortmund  # Dortmund eingefroren (AGENTS.md, 04.10.2026): vergleicht gegen den eingefrorenen Dortmund-Fingerabdruck
def test_dortmund_wie_vor_dem_umbau(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, DORTMUND)
    _vergleiche(_massstab(), _fingerabdruck())


def test_dortmund_und_keine_variable_sind_identisch(monkeypatch):
    ohne = _fingerabdruck()
    monkeypatch.setenv(workshop.VARIABLE, DORTMUND)
    mit = _fingerabdruck()
    assert mit == ohne, _vergleiche(ohne, mit)


def _golden_system(name: str) -> str:
    text = (_DUMPS / f"{name}.txt").read_text(encoding="utf-8")
    treffer = re.search(
        r"=== SYSTEM \(\d+ Zeichen, ~\d+ Token\) ===\n(.*?)\n\n=== NUTZER ",
        text, re.S,
    )
    assert treffer, f"{name}.txt hat keinen SYSTEM-Block"
    return treffer.group(1)


@pytest.mark.parametrize("name", sorted(GOLDEN_SYSTEM))
def test_golden_dump_ohne_variable(name):
    assert GOLDEN_SYSTEM[name]() == _golden_system(name)


@pytest.mark.parametrize("name", sorted(GOLDEN_SYSTEM))
def test_golden_dump_mit_dortmund(name, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, DORTMUND)
    anweisungen._CACHE.clear()
    assert GOLDEN_SYSTEM[name]() == _golden_system(name)


def test_der_schnappschuss_deckt_die_prompt_dateien_ab():
    """Ein Abschnitt je Prompt-Datei -- sonst prueft der Test daran vorbei."""
    namen = {name for name, _ in prompt_schnappschuss.teile()}
    for pfad in anweisungen._VERZEICHNIS.rglob("*.md"):
        kurz = str(pfad.relative_to(anweisungen._VERZEICHNIS).with_suffix(""))
        assert f"prompt {kurz}" in namen
