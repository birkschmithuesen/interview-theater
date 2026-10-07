"""Birk 07.10.2026: in Phase 5 bleibt der in Phase 4 gesetzte Rahmen
(Format, Setting, Figuren, Festlegungen) aenderbar -- Prompt (Padua/EN; Dortmund bleibt bitgleich) UND Erkenner."""
from interview_theater import erkenner


def test_phase5_prompt_sagt_rahmen_bleibt_aenderbar():
    from pathlib import Path
    basis = Path(erkenner.__file__).parent
    en = (basis / "sprachen/en/prompts/phasen/5.md").read_text(encoding="utf-8")
    assert "The frame stays changeable" in en


def test_rahmen_arten_sind_in_phase_5_nicht_gesperrt():
    for art in ("rahmen_setzen", "figur_setzen", "festlegung_setzen", "geschichte_setzen"):
        assert art not in erkenner.PHASEN_SPEZIFISCHE_ARTEN, art
        ab = erkenner.AB_PHASE_ARTEN.get(art)
        assert ab is None or ab <= 5, art
