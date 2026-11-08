import json

from simulation import browser_lauf


def test_vermerke_szene_modell_schreibt_in_ergebnis_json(tmp_path):
    (tmp_path / "ergebnis.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    browser_lauf.vermerke_szene_modell(tmp_path, "claude-sonnet-5")
    daten = json.loads((tmp_path / "ergebnis.json").read_text(encoding="utf-8"))
    assert daten == {"a": 1, "szene_modell_override": "claude-sonnet-5"}
