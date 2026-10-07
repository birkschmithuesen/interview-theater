

def test_json_nach_schluessel_findet_objekt_nach_langem_vortext():
    """Live-Fund 07.10.2026: Opus schrieb Vortext > Suchfenster vor das
    JSON-Objekt -> 'unverwertbar' -> Kimi-Rueckfall. Mutant: Hilfsfunktion
    liefert None -> rot."""
    from interview_theater import szene_claude
    text = "Thinking about it. " * 40 + '{"antwort": "Interview 3 fits."}'
    schema_ = {"properties": {"antwort": {"type": "string"}}}
    assert szene_claude._json_nach_schluessel(text, schema_) == {"antwort": "Interview 3 fits."}
    assert szene_claude._json_nach_schluessel("no json here", schema_) is None
