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


def test_kontaktbogen_erzeugt_eine_png_datei_mit_den_echten_bildern(tmp_path):
    """Realer Betriebsbefund (Padua-Abnahme, 03.10.2026): die fruehere
    ``file://``-URI liess Chromium die Bilder stillschweigend NICHT laden
    (keine Seite aus ``set_content`` hat einen Ursprung, der Dateizugriff
    erlaubt) -- der Kontaktbogen wurde erzeugt, zeigte aber nur
    Dateinamen auf schwarzem Grund. Ein reiner Dateigroessen-Test haette
    das nicht gefangen (Text + Hintergrund ist auch "nicht trivial");
    deshalb hier echte, unterscheidbare Bildinhalte, und die Groesse wird
    gegen eine Fixture OHNE jedes Bild verglichen -- der Kontaktbogen mit
    echten Bildern muss sichtbar groesser sein."""
    rot = tmp_path / "001-phase1-vor.png"
    bild_bytes = _gefuelltes_png(60, 60, "#ff0000")
    rot.write_bytes(bild_bytes)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()

        leer_html_seite = context.new_page()
        leer_html_seite.set_content(
            "<style>body{margin:0;background:#222}</style><body></body>"
        )
        leere_ausgabe = tmp_path / "leer.png"
        leer_html_seite.screenshot(path=str(leere_ausgabe), full_page=True)
        leer_html_seite.close()

        ausgabe = tmp_path / "kontaktbogen.png"
        b.kontaktbogen(context, [rot, rot], ausgabe, spalten=2)
        context.close()
        browser.close()
    assert ausgabe.exists()
    # Zwei echte 60x60-Kacheln muessen spuerbar mehr PNG-Bytes brauchen als
    # dieselbe Seitengroesse ganz ohne Bildinhalt -- ein Faktor waere gegen
    # PNG-Kompression einer Flaeche zu knapp bemessen, ein fester
    # Byte-Abstand (empirisch: ~1,8 KB bei zwei 60x60-Kacheln) reicht.
    assert ausgabe.stat().st_size > leere_ausgabe.stat().st_size + 500


def test_kontaktbogen_meldet_ein_nicht_ladbares_bild_statt_still_leer_zu_bleiben(tmp_path):
    """Die Regel aus dem Befund oben, umgekehrt geprueft: ein Bild, das der
    Browser nicht decodieren kann, muss ``kontaktbogen`` laut scheitern
    lassen -- nicht eine huebsche, leere PNG ausliefern."""
    kaputt = tmp_path / "001-phase1-vor.png"
    kaputt.write_bytes(b"das ist kein PNG")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        ausgabe = tmp_path / "kontaktbogen.png"
        try:
            with pytest.raises(RuntimeError, match="liessen sich nicht laden"):
                b.kontaktbogen(context, [kaputt], ausgabe, spalten=1)
        finally:
            context.close()
            browser.close()
    assert not ausgabe.exists()


def _gefuelltes_png(breite: int, hoehe: int, farbe_hex: str) -> bytes:
    """Ein winziges, echtes PNG in einer Flaeche -- fuer einen Test, der
    pruefen will, dass ein Bild wirklich DECODIERT wurde, nicht nur, dass
    irgendeine Datei existiert. Kein Pillow: von Hand ueber zlib/struct,
    derselbe Minimalismus wie ``kontaktbogen`` selbst."""
    import struct
    import zlib

    r = int(farbe_hex[1:3], 16)
    g = int(farbe_hex[3:5], 16)
    bl = int(farbe_hex[5:7], 16)
    zeile = bytes([0]) + bytes([r, g, bl]) * breite
    roh = zeile * hoehe

    def chunk(art: bytes, daten: bytes) -> bytes:
        return (
            struct.pack(">I", len(daten)) + art + daten
            + struct.pack(">I", zlib.crc32(art + daten))
        )

    kopf = struct.pack(">IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", kopf)
        + chunk(b"IDAT", zlib.compress(roh))
        + chunk(b"IEND", b"")
    )
