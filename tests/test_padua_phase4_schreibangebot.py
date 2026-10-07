"""Padua Phase 4->5 Schreibangebot (Birk, Live-Test G3, 06.10.2026 ~21:35,
``betrieb/padua-test.db`` web_post id 1512): der Bot bot waehrend noch
aktiver Phase 4 schon den Szenentext an -- "Shall I write scene 1 now?" nach
einem vollstaendig ausformulierten Szenenformat (Place:/Who:/What happens:).
Das ist Phase-5-Territorium ("Prose Draft"); Phase 4 setzt nur den Rahmen.

Birks Vorgabe woertlich: "Keine Szenen ausformulieren in Phase 4. Nur Rahmen
setzen. Wenn die Nachfrage nach Szenen-Formulieren kommt, dann auf Phase 5
verweisen."

Kein Modellaufruf -- geprueft wird nur die zusammengesetzte Phase-4-Anweisung
(``anweisungen.hole("phasen/4")``, EN-Fassung, weil Padua auf
``sprache.code=en`` laeuft und keine eigene Padua-Datei fuer Phase 4
existiert, anders als Phase 1-3)."""

from pathlib import Path

import pytest

from interview_theater import anweisungen, sprache, workshop

DATEI_DE = Path(__file__).parents[1] / "interview_theater/prompts/phasen/4.md"
DATEI_EN = Path(__file__).parents[1] / "interview_theater/sprachen/en/prompts/phasen/4.md"


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


def test_uebergangsangebot_verspricht_keine_szenenvorschau(padua):
    """Das EINMALIGE Uebergangsangebot (Setting/Figuren/Geschichte/Szenen
    vollstaendig) darf kein Szenenformat und keine Schreibfrage ankuendigen
    -- genau das, was in Nachricht 1512 stand."""
    phase = _flach(anweisungen.hole("phasen/4"))
    for verbotenes in ("Place:", "Who:", "What happens:", "write scene", "Shall I write"):
        assert verbotenes not in phase, verbotenes
    assert "no preview of a scene" in phase or "never previews the scene" in phase


def test_schreibwunsch_in_phase_4_verweist_auf_phase_5(padua):
    """Fragt die Gruppe ausdruecklich danach, eine Szene auszuformulieren,
    liefert der Bot NICHT den Text, sondern verweist auf Prose Draft -- eine
    ausdrueckliche Ausnahme von der sonstigen Regel 'ausdruecklich gefragt,
    dann trotzdem' (Zeile "If the group explicitly asks for it, you do it
    anyway")."""
    phase = _flach(anweisungen.hole("phasen/4"))
    assert "Prose Draft" in phase
    assert "exception" in phase
    assert "write out" in phase or "draft a scene" in phase


def test_phase4_de_hat_dieselbe_abwehrregel():
    """Die deutsche Rohdatei (Referenz fuer andere Profile/Sprachen) traegt
    dieselbe Haertung wie die EN-Fassung, nur auf Deutsch."""
    text = DATEI_DE.read_text(encoding="utf-8")
    flach = _flach(text)
    for verbotenes in ("Place:", "Who:", "What happens:", "Shall I write"):
        assert verbotenes not in flach
    assert "Ausnahme" in flach
    assert "Schärfung" in flach or "Textentwurf" in flach


def test_phase4_en_rohdatei_hat_dieselbe_abwehrregel():
    text = DATEI_EN.read_text(encoding="utf-8")
    flach = _flach(text)
    assert "exception" in flach
    assert "Prose Draft" in flach
