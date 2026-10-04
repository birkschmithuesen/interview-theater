import sqlite3

import pytest

from simulation import browser_abnahme as ab


def _lauf(geraet, fertig=True, board=True, meta=(), mit_p1_start=True):
    stationen = []
    if mit_p1_start:
        stationen.append({
            "schluessel": "p1-start", "phase": 1, "schritte": 0,
            "nachfragen_beantwortet": 0, "offene_fragen": [], "fertig": True,
            "fallback_benutzt": False, "note": None, "befunde": [],
            "screenshots_fuer_bericht": [], "note_erklaerung": None,
            "schwaechstes_zitat": "", "vorschlag": "",
            "bot_nachricht": False, "kalibrierung_sichtbar": False,
            "zuhoeren_laeuft": False, "leertext_sichtbar": True,
        })
    stationen += [
        {"schluessel": "p1-eintritt", "phase": 1, "schritte": 2,
         "nachfragen_beantwortet": 1, "offene_fragen": ["What is CoThinker?"],
         "fertig": True, "fallback_benutzt": False, "note": 4, "befunde": [],
         "screenshots_fuer_bericht": ["001.png"], "note_erklaerung": 4,
         "schwaechstes_zitat": "Welcome to phase one", "vorschlag": ""},
        {"schluessel": "p2-eroeffnung", "phase": 2, "schritte": 5,
         "nachfragen_beantwortet": 0, "offene_fragen": [], "fertig": fertig,
         "fallback_benutzt": False, "note": 3, "befunde": [],
         "screenshots_fuer_bericht": [], "note_erklaerung": 2,
         "schwaechstes_zitat": "", "vorschlag": "Say less.",
         "zitat_unbelegt": True},
    ]
    return {"geraet": geraet, "persona": "giulia" if geraet == "handy" else "priya",
            "stationen_ergebnisse": stationen,
            "board_verlauf": [0, 2, 5] if board else [0, 0], "board_bestanden": board,
            "beobachter_neu_geladen": False, "entwickler_meta": list(meta)}


def test_urteil_ja_und_nein():
    assert ab.urteil([_lauf("handy"), _lauf("laptop")])[0] is True
    ok, grund = ab.urteil([_lauf("handy"), _lauf("laptop", fertig=False)])
    assert ok is False and "laptop" in grund and "p2-eroeffnung" in grund
    assert ab.urteil([_lauf("handy", board=False), _lauf("laptop")])[0] is False
    assert ab.urteil([_lauf("handy", meta=["the code reads"]), _lauf("laptop")])[0] is False


def test_bericht_beginnt_mit_dem_urteil_und_enthaelt_alle_teile():
    md = ab.baue_abnahme(
        [_lauf("handy"), _lauf("laptop")],
        belege={"handy": [("gespraech", "moonshotai/Kimi-K2.6", 12, 0.04)]},
        b_befunde=[{"titel": "Phase 2 · Alle annehmen", "text": "24 Taps.",
                    "vorschlag": "Knopf 'Accept all mine'."}],
        leitbilder=[{"datei": "phase-1-eintritt-handy.png", "unterschrift_en": "x"}],
        harness_notizen=["Kalibrierung mit Fake-Audio: bestanden"],
        modellwahl_satz="Kimi, Modellwahl noch nicht gemergt")
    erste = md.splitlines()[0]
    assert erste.startswith("Phase 1-2 abnahmebereit: ja")
    for teil in ("## Testanleitung fuer Birk", "## Stationen", "What is CoThinker?",
                 "## Begriffsboard", "0 → 2 → 5", "## Modellbeleg", "Kimi-K2.6",
                 "## B-Befunde", "Frage: Soll ich?", "docs/guide/bilder/phase-1-eintritt-handy.png",
                 "Kimi, Modellwahl noch nicht gemergt", "## Harness-Notizen",
                 "Erklaerung", "schwaechstes Zitat", "Vorschlag", "Say less.",
                 "(unbelegt)", "Seite neu oeffnen, nichts tippen",
                 "Leertext sichtbar: ja"):
        assert teil in md, teil


def test_mehr_als_fuenf_b_befunde_sind_ein_fehler():
    with pytest.raises(ValueError):
        ab.baue_abnahme([_lauf("handy")], belege={}, leitbilder=[], harness_notizen=[],
                        modellwahl_satz="", b_befunde=[{"titel": "t", "text": "x",
                                                        "vorschlag": "v"}] * 6)


def test_modellbeleg_und_kosten(tmp_path):
    pfad = str(tmp_path / "s.db")
    conn = sqlite3.connect(pfad)
    conn.execute("CREATE TABLE aufruf (art TEXT, modell TEXT, kosten_chf REAL)")
    conn.executemany("INSERT INTO aufruf VALUES (?,?,?)",
                     [("gespraech", "kimi", 0.01), ("gespraech", "kimi", 0.02),
                      ("stt", "whisper", None)])
    conn.commit(); conn.close()
    assert ab.modellbeleg(pfad) == [("gespraech", "kimi", 2, 0.03), ("stt", "whisper", 1, 0.0)]
    assert ab.kosten_summe([pfad, pfad]) == pytest.approx(0.06)
