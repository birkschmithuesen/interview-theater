from pathlib import Path

DATEI = Path("workshop/padua-2026/prompts/phasen/1.md")


def test_phase1_erzaehlt_kein_plenum_und_keine_wand():
    """Abnahme P1-2 (05.10.2026, echter Browserlauf, laptop/priya): ohne
    eigenes ``workshop/padua-2026/prompts/phasen/1.md`` lief Phase 1 ueber
    die geteilte Vorgabe (``interview_theater/sprachen/en/prompts/phasen/1.md``),
    die weiter "The group has collected terms in the room -- on slips of
    paper, on the wall" sagt -- die alte Dortmunder Abgabe. Der Bot bat die
    Gruppe deshalb, ihre Begriffe zu TIPPEN, obwohl die Padua-Oberflaeche sie
    zum Hintergrund-Zuhoeren einlaedt (Karte t_4517d4ad): "Start listening"
    blieb in allen vier echten Laeufen ungeklickt, und das Begriffsboard
    wuchs nie. Diese eigene Phase-1-Datei beschreibt die echte Abfolge."""
    text = " ".join(DATEI.read_text(encoding="utf-8").split())
    for stelle in ("slips of paper", "on the wall", "collected in the room"):
        assert stelle not in text, stelle
    assert "This phase is the handover" not in text
    assert "Start listening" in text
    assert "Discussion done" in text
    assert "phone in the middle" in text


def test_phase1_behaelt_den_vorschlag_begriffe_marker_fuer_chat_korrekturen():
    """Die Gruppe darf ihre Begriffe weiterhin per Chat tippen oder
    korrigieren (gemessen: das ist in jedem der vier echten Laeufe
    passiert) -- der Marker-Block bleibt deshalb als Zweitweg stehen, nur
    die Rahmenerzaehlung aendert sich."""
    text = DATEI.read_text(encoding="utf-8")
    assert "VORSCHLAG BEGRIFFE:" in text
