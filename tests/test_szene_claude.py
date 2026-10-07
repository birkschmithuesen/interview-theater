

def test_json_nach_schluessel_findet_objekt_nach_langem_vortext():
    """Live-Fund 07.10.2026: Opus schrieb Vortext > Suchfenster vor das
    JSON-Objekt -> 'unverwertbar' -> Kimi-Rueckfall. Mutant: Hilfsfunktion
    liefert None -> rot."""
    from interview_theater import szene_claude
    text = "Thinking about it. " * 40 + '{"antwort": "Interview 3 fits."}'
    schema_ = {"properties": {"antwort": {"type": "string"}}}
    assert szene_claude._json_nach_schluessel(text, schema_) == {"antwort": "Interview 3 fits."}
    assert szene_claude._json_nach_schluessel("no json here", schema_) is None


def test_schema_klartext_ohne_json_wird_antwort(monkeypatch):
    """Live-Fund 07.10.2026 15:39: Opus lieferte Markdown ohne JSON; bei einem
    Schema mit nur ``antwort`` ist der Klartext die Antwort. Mutant: Zweig
    entfernt -> LLMFehler."""
    from interview_theater import llm as llm_modul
    from interview_theater import szene_claude
    text = "Here's more material.\n\n**Cos'e casa**\n- Interview 5: \"...\""
    monkeypatch.setattr(szene_claude, "prosa", lambda *a, **k: text)
    schema_ = {"type": "object", "required": ["antwort"], "properties": {"antwort": {"type": "string"}}}
    ergebnis = szene_claude.schema(None, None, None, 1, "sys", "nutzer", schema_, "gespraech", 10)
    assert ergebnis == {"antwort": text}
    schema2 = {"type": "object", "required": ["antwort", "x"], "properties": {"antwort": {}, "x": {}}}
    import pytest
    with pytest.raises(llm_modul.LLMFehler):
        szene_claude.schema(None, None, None, 1, "sys", "nutzer", schema2, "gespraech", 10)
