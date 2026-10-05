from pathlib import Path

DATEI = Path("workshop/padua-2026/prompts/phasen/2.md")


def test_phase2_verbietet_entwickler_meta_gegenueber_der_gruppe():
    text = " ".join(DATEI.read_text(encoding="utf-8").split())
    assert "Never talk to the group about code." in text
    assert "what the code reads" in text
    assert "say plainly that it does not exist yet" in text
