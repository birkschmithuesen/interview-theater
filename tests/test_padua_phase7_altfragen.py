"""Quickfix 08.10.2026 (Birk, Live-Befund Phase 7 im Tester, chat
7000000000099, 08.10. 10:19-10:24): im Stage Script (Padua, ``[karten]
aktiv``) kamen Fragen aus der alten Prosa-/Formwahl-Mechanik im Chat an
("Scene 2 of 3 as Dialogue", "Giona could speak like Interview 7 -- does
that fit?", "Should all four speak..."), ohne dass sie je jemand
aufgriff. Der Phasentext selbst muss das verbieten, so wie Dortmunds
``phasen/7.md`` die Form- und Sprachstil-Frage schon verbietet
(``docs/agents/entscheidungen.md``)."""

from pathlib import Path

import pytest

from interview_theater import anweisungen, sprache, workshop

DATEI = Path(__file__).parents[1] / "workshop/padua-2026/prompts/phasen/7-karten.md"


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _flach(text: str) -> str:
    return " ".join(text.split())


def test_7_karten_verbietet_formfrage_und_sprechweisenfrage(padua):
    """Der Stage-Script-Phasentext selbst sagt, dass er nicht nach der Form,
    nicht danach, wer spricht, und nicht nach der Interview-Quelle einer
    Figur fragt."""
    phase = _flach(anweisungen.hole("phasen/7-karten"))
    assert "No question about a scene's form" in phase
    assert "No question about which interview a character speaks from" in phase


def test_system_phase_7_padua_traegt_das_verbot(padua):
    """Dieselbe Zusage in der zusammengesetzten Systemanweisung, die auch
    wirklich an das Modell geht."""
    gesamt = _flach(anweisungen.system(phase=7))
    assert "No question about a scene's form" in gesamt


def test_ohne_profil_bleibt_die_geteilte_phase7_datei():
    """Dortmund/Vorgabe liest die Padua-Profildatei nie -- byte-gleich."""
    workshop.vergiss()
    sprache.vergiss()
    assert "No question about a scene's form" not in anweisungen.hole("phasen/7")
