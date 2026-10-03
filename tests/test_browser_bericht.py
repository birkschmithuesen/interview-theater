from simulation import browser_bericht as b


def test_markdown_zeigt_titel_modelle_und_top_befunde():
    text = b.baue_markdown(
        "Padua browser run", "handy",
        {"persona": "claude-opus-5", "bot_gespraech": "kimi-k2"},
        [{"nummer": 1, "name": "Terms", "note": 4, "befunde": [],
          "zaehler_summe": {"seitliches_rutschen": False}}],
        [{"phase": 1, "schwere": "hoch", "text": "Chips blockieren die Eingabe"}],
    )
    assert "# Padua browser run (handy)" in text
    assert "claude-opus-5" in text
    assert "kimi-k2" in text
    assert "Chips blockieren die Eingabe" in text
    assert "## Phase 1 · Terms — note 4/5" in text
    assert "seitliches_rutschen" in text


def test_markdown_markiert_operator_fallback():
    text = b.baue_markdown("t", "handy", {}, [
        {"nummer": 3, "name": "Interviews", "note": None, "befunde": [],
         "fallback_benutzt": True, "zaehler_summe": {}},
    ], [])
    assert "Operator fallback used" in text


import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402


def test_kontaktbogen_erzeugt_eine_png_datei(tmp_path):
    bild = tmp_path / "001-phase1-vor.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page()
        seite.set_content("<h1>fixture</h1>")
        seite.screenshot(path=str(bild))
        ausgabe = tmp_path / "kontaktbogen.png"
        b.kontaktbogen(seite.context, [bild, bild], ausgabe, spalten=2)
        browser.close()
    assert ausgabe.exists()
    assert ausgabe.stat().st_size > 0
