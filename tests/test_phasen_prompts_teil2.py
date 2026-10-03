"""Padua Phasen TEIL 2: Gattungsspezifisches nur in formen/<form>.md."""
from pathlib import Path

EN = Path(__file__).resolve().parent.parent / "interview_theater" / "sprachen" / "en" / "prompts"


def test_phase7_en_ohne_hook():
    assert "hook" not in (EN / "phasen" / "7.md").read_text(encoding="utf-8").lower()


def test_rap_chor_lied_en_mit_hook():
    for form in ("rap", "chor", "lied"):
        assert "hook" in (EN / "formen" / f"{form}.md").read_text(encoding="utf-8").lower(), form


def test_phase6_en_ohne_alten_einzelszenen_ausloeser():
    """Flow-Audit B3: kein 'write us scene 3' mehr neben dem Ablauf."""
    text = (EN / "phasen" / "6.md").read_text(encoding="utf-8").lower()
    assert "write us scene" not in text
    assert "script tab" in text


def test_phase7_en_nennt_formwahl_sprechweisen_und_script_tab():
    text = (EN / "phasen" / "7.md").read_text(encoding="utf-8").lower()
    assert "which form for each number" in text
    assert "script tab" in text
