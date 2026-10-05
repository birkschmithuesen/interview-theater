"""P34 Runde 1 (Lauf 205532, Prompt-Check docs/prompt-audit/2026-10-05-padua-p34):
eigene Padua-Datei ``workshop/padua-2026/prompts/phasen/3.md`` statt der
geteilten EN-Vorgabe. Kein Modellaufruf -- geprueft wird die
zusammengesetzte Systemanweisung (``anweisungen.system(phase=3)``) unter dem
Padua-Profil.

* A4 (= L3-5 + J-p3-gemischt-1): Dump 06:480 "In this phase you ask almost
  nothing" gegen 06:501 "Ask first, then suggest" -- Kimi stellte im Lauf
  2-4 Fragen je Nachricht (nachricht 18, 20).
* A3 (= J-p3-gemischt-4 + L3-6): der Bot sagte "Start interview", der
  Web-Knopf hiess "Record interview"; der Phasentext legte den Knopf "under
  the bot's messages" (06:470), im Browser steht er unten ueber dem
  Eingabefeld.
"""

from pathlib import Path

import pytest

from interview_theater import anweisungen, sprache, web_chat, workshop

DATEI = Path("workshop/padua-2026/prompts/phasen/3.md")


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


def _phasenteil(padua) -> str:
    return _flach(anweisungen.hole("phasen/3"))


def test_phase3_widerspricht_sich_bei_fragen_nicht(padua):
    """A4: die Phase-4-Regel "Ask first, then suggest" steht nicht mehr im
    Phase-3-Text, und die Frage-Regel der Phase stellt sich ausdruecklich
    ueber die allgemeine."""
    phase = _phasenteil(padua)
    gesamt = _flach(anweisungen.system(phase=3))
    for stelle in ("Ask first, then suggest", "two to three options", "exactly one field per message"):
        assert stelle not in phase, stelle
    # Die allgemeine Vorschlagsregel ("two to three options") steht weiter im
    # geteilten Systemprompt (robo-fbl) -- deshalb der Vorrang-Satz unten.
    assert "Ask first, then suggest" not in gesamt
    assert "takes precedence over every general rule" in gesamt
    assert "takes precedence over every general rule" in phase
    assert "ask **no question** by default" in phase
    assert "never two, never a list" in phase


def test_phase3_nennt_den_web_knopf_und_seinen_ort(padua):
    """A3: ein Name fuer den Knopf, und der Ort stimmt mit der Oberflaeche."""
    phase = _phasenteil(padua)
    assert "under the bot's messages" not in phase
    assert '"Start interview"' in phase
    assert "bottom of the screen" in phase
    assert web_chat.T._TEXT_INTERVIEW_AN == "Start interview"
    assert '"Start interview"' in _flach(anweisungen.system(phase=3))


def test_phase3_kopf_nicht_doppelt_mit_der_statuszeile():
    """Wie tests/test_padua_phase1_prompt.py: die Statuszeile nennt die
    Phase schon."""
    text = DATEI.read_text(encoding="utf-8")
    assert "## Current phase" not in text
    assert text.startswith("## What this phase is about")


def test_ohne_profil_bleibt_die_geteilte_phase3_datei():
    """Dortmund/Vorgabe liest die Profil-Datei nie."""
    workshop.vergiss()
    sprache.vergiss()
    assert "takes precedence over every general rule" not in anweisungen.hole("phasen/3")
