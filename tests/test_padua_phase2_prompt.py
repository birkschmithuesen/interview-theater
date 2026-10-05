from pathlib import Path

DATEI = Path("workshop/padua-2026/prompts/phasen/2.md")


def test_phase2_verbietet_entwickler_meta_gegenueber_der_gruppe():
    text = " ".join(DATEI.read_text(encoding="utf-8").split())
    assert "Never talk to the group about code." in text
    assert "what the code reads" in text
    assert "say plainly that it does not exist yet" in text


def test_phase2_kopf_nicht_doppelt_mit_der_statuszeile():
    """Prompt-Check Padua P1-2 (05.10.2026), Befund P2-M3 (Kopf): wie
    tests/test_padua_phase1_prompt.py, nur Phase 2."""
    text = DATEI.read_text(encoding="utf-8")
    assert "## Current phase" not in text
    assert text.startswith("## What this phase is about")


def test_phase2_ohne_toten_verweis_auf_fragen_weich():
    """Befund P2-N3: 'VORSCHLAG FRAGEN WEICH:' wird fuer dieses Profil
    nirgends geschrieben (die weiche Fassung ist abgeschaltet) -- der tote
    Markerverweis stand trotzdem noch in der Regel zum Schaerfen einer
    einzelnen Frage. Nur die positive Regel bleibt stehen."""
    text = " ".join(DATEI.read_text(encoding="utf-8").split())
    assert "FRAGEN WEICH" not in text
    assert "The group words its questions itself." in text


def test_phase2_ohne_entwicklervermerk_im_modellkontext():
    """Lesung Runde 2 (05.10.2026), billiger Fund c459: die Datei begann
    mit einem Entwicklervermerk ('Padua Phase 1+2 card, Task 13
    (2026-10-03): this file completely replaces the shared `phasen/2.md`
    for this profile only ...') -- eine Begruendung fuer Entwicklerinnen,
    kein Satz fuer das Modell, das diese Datei als Teil des Systemprompts
    liest."""
    text = DATEI.read_text(encoding="utf-8")
    assert "Task 13" not in text
    assert "completely replaces" not in text
    assert text.startswith("## What this phase is about")
