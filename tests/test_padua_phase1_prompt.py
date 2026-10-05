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


def test_phase1_kopf_nicht_doppelt_mit_der_statuszeile():
    """Prompt-Check Padua P1-2 (05.10.2026), Befund P2-M3 (Kopf): die
    Ueberschrift '## Current phase: 1 - Terms' duplizierte woertlich die
    separat gebaute Statuszeile 'Current phase: 1 - Terms' im Nutzerteil
    (kontext.py, nicht Teil dieser Karte) -- derselbe Satz stand zweimal im
    selben Prompt."""
    text = DATEI.read_text(encoding="utf-8")
    assert "## Current phase" not in text
    assert text.startswith("## What this phase is about")


def test_phase1_behaelt_den_vorschlag_begriffe_marker_fuer_chat_korrekturen():
    """Die Gruppe darf ihre Begriffe weiterhin per Chat tippen oder
    korrigieren (gemessen: das ist in jedem der vier echten Laeufe
    passiert) -- der Marker-Block bleibt deshalb als Zweitweg stehen, nur
    die Rahmenerzaehlung aendert sich."""
    text = DATEI.read_text(encoding="utf-8")
    assert "VORSCHLAG BEGRIFFE:" in text


def test_phase1_begriffe_block_nur_mit_eigenem_wortlaut_der_gruppe():
    """Lesung Runde 3 (05.10.2026), Prompt-Check Klasse A
    (``docs/prompt-audit/2026-10-05-padua-p12-r3/lesung-p1.json``, Zeile
    526): 'It is saved automatically; without a block nothing is saved'
    sagt nicht, WAS in den Block darf -- UX-Regel 1 ('Bot proposals are
    never saved as decisions. Only what the group said or confirmed is
    saved.') braucht einen eigenen Satz, sonst speichert der Autosave
    eine Erfindung des Bots als Begriffs-Entscheidung."""
    text = " ".join(DATEI.read_text(encoding="utf-8").split())
    assert "without a block nothing is saved" in text
    assert "wording the group itself said or confirmed" in text
