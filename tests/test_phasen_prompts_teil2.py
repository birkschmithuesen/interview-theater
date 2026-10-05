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


def test_system_en_marker_katalog_nennt_eigene_fragen():
    """Prompt-Check Padua P1-2 (05.10.2026): Padua Phase 2
    (workshop/padua-2026/prompts/phasen/2.md) laesst den Bot
    ``VORSCHLAG EIGENE FRAGEN:`` als 13. Marker schreiben
    (interview_theater/knoepfe/fragen.py:uebernimm_eigene), aber der
    EN-Systemprompt behauptete 'There are twelve markers, no more' und
    listete ihn nicht -- ein Modell, das die Behauptung ernst nimmt,
    haette den Marker fuer ungueltig gehalten."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "There are twelve markers, no more" not in text
    assert "There are thirteen markers, no more" in text
    assert "VORSCHLAG EIGENE FRAGEN:" in text


def test_system_en_widerspricht_nicht_dem_echten_phase1_ablauf():
    """Opus-Lesung Prompt-Check P1-2 (05.10.2026, Karte t_bf16f3a7, Befund
    kategorie=b, Zeile 44 von ``01-gespraech-phase1.txt``): der geteilte
    EN-Systemprompt sagte 'Phase 1 is a handover: the terms have been
    collected in the room, you receive the list. You don't collect them
    yourself -- that happens offline, in the plenary session, without the
    chat.' -- genau das Gegenteil von Paduas echtem Ablauf (Hintergrund-
    Zuhoeren im Chat/CoThinker, 'Discussion done', automatischer
    Begriffsvorschlag), der im selben geladenen Prompt-Satz
    (workshop/padua-2026/prompts/phasen/1.md) steht. Ein Modell, das beide
    Saetze liest, bekommt zwei widersprechende Ablaeufe fuer dieselbe
    Phase."""
    text = (EN / "system.md").read_text(encoding="utf-8")
    assert "Phase 1 is a handover" not in text
    assert "that happens offline" not in text
