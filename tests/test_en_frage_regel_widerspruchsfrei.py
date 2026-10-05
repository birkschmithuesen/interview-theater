from pathlib import Path

DATEI = Path("interview_theater/sprachen/en/prompts/system.md")


def test_frage_regel_widerspricht_sich_nicht_mehr():
    """Abnahme P1-2, Fortsetzung (Robo-Prompt-Check gegen den Padua-Dump):
    zwei Regeln standen nebeneinander -- "Every suggestion message ends
    with an open question" (Pflicht) gegen "At most ONE question per
    message" mit "With plain confirmations ... zero questions" (eine
    Frage ist optional). Beide widersprachen sich in der Frage, ob eine
    Frage je Vorschlag PFLICHT ist. Nur die englische Datei betroffen --
    die deutsche (Dortmund, eingefroren) bleibt unangetastet, Dortmund
    liest sprachen/en/ nie (sprache.code() faellt ohne Profil auf
    Deutsch zurueck)."""
    text = " ".join(DATEI.read_text(encoding="utf-8").split())
    assert "Every suggestion message ends with an open question" not in text
    assert "never a mandatory close" in text
    assert "At most ONE question per message" in text
    assert "zero questions" in text


def test_deutsche_dortmund_datei_bleibt_unangetastet():
    datei_de = Path("interview_theater/prompts/system.md")
    text = datei_de.read_text(encoding="utf-8")
    assert "Jede Vorschlagsnachricht endet mit einer offenen Frage" in text \
        or "endet mit einer offenen Frage" in text
