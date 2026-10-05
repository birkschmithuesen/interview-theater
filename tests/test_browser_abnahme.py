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


def test_urteil_nein_bei_invariante_hoch():
    lauf = _lauf("handy")
    lauf["invarianten"] = [{"schluessel": "raumcheck_domainweit", "station": "p1-zuhoeren",
                             "text": "x", "schwere": "hoch",
                             "ursache": "App oder Werkzeug – ungeklaert"}]
    ok, grund = ab.urteil([lauf, _lauf("laptop")])
    assert ok is False
    assert "raumcheck_domainweit" in grund


def _inv_lauf(commit, *schluessel):
    return {"app_commit": commit, "invarianten": [
        {"schluessel": s, "station": "p1-zuhoeren", "text": f"t {s}", "schwere": "hoch",
         "ursache": "App oder Werkzeug – ungeklaert"} for s in schluessel]}


def test_vergleich_abnahme_erfuellt():
    vorher = _inv_lauf("cb200e4", "board_leer_nach_ende", "stille_nach_leerem_ende",
                        "werkbank_leer_phase2_gesperrt", "chat_kennt_board_nicht",
                        "chat_kennt_transkript_nicht", "raumcheck_domainweit")
    nachher = _inv_lauf("abc1234")
    md = ab.vergleichstabelle(vorher, nachher)
    assert "| Befund | vorher (cb200e4) | nachher (abc1234) |" in md
    assert md.count("gemeldet (hoch)") == 6
    assert "Abnahme erfüllt: ja" in md


def test_vergleich_abnahme_nicht_erfuellt_wenn_nachher_noch_da():
    vorher = _inv_lauf("cb200e4", "board_leer_nach_ende", "stille_nach_leerem_ende",
                        "werkbank_leer_phase2_gesperrt", "chat_kennt_board_nicht",
                        "chat_kennt_transkript_nicht", "raumcheck_domainweit")
    nachher = _inv_lauf("abc1234", "raumcheck_domainweit", "station_nicht_erreicht:p1-begriffe")
    md = ab.vergleichstabelle(vorher, nachher)
    assert "Abnahme erfüllt: nein" in md
    assert "station_nicht_erreicht:p1-begriffe" in md  # Restbefunde nachher


def test_board_nicht_nachgezogen_gehoert_zur_board_zeile():
    """Abnahmelauf cb200e4: ein Board mit Vorgeschichte, das die knappe
    Nennung nie liest, ist dieselbe Zeile wie das leere Board."""
    vorher = _inv_lauf("cb200e4", "board_nicht_nachgezogen", "stille_nach_leerem_ende",
                        "werkbank_leer_phase2_gesperrt", "chat_kennt_board_nicht",
                        "chat_kennt_transkript_nicht", "raumcheck_domainweit")
    md = ab.vergleichstabelle(vorher, _inv_lauf("abc1234"))
    assert md.count("gemeldet (hoch)") == 6
    assert "Abnahme erfüllt: ja" in md
    md = ab.vergleichstabelle(vorher, _inv_lauf("abc1234", "board_nicht_nachgezogen"))
    assert "Abnahme erfüllt: nein" in md


def test_invarianten_abschnitt_und_urteil():
    lauf = _inv_lauf("cb200e4", "werkbank_leer_phase2_gesperrt")
    md = ab.invarianten_abschnitt([lauf])
    assert "werkbank_leer_phase2_gesperrt" in md and "App oder Werkzeug – ungeklaert" in md and "hoch" in md


def test_vergleich_abnahme_nicht_erfuellt_wenn_vorher_unvollstaendig():
    # chat_kennt_transkript_nicht fehlt in vorher -- nachher ist sauber.
    vorher = _inv_lauf("cb200e4", "board_leer_nach_ende", "stille_nach_leerem_ende",
                        "werkbank_leer_phase2_gesperrt", "chat_kennt_board_nicht",
                        "raumcheck_domainweit")
    nachher = _inv_lauf("abc1234")
    md = ab.vergleichstabelle(vorher, nachher)
    assert "Abnahme erfüllt: nein" in md
    assert "chat_kennt_transkript_nicht" in md  # Grund: fehlt in vorher


def test_vergleich_abnahme_erfuellt_trotz_restbefund_ausserhalb_tabelle():
    # nachher hat nur einen hoch-Fund, der KEINER ABNAHME_BEFUNDE-Zeile
    # zugeordnet ist -- blockiert die Abnahme nicht, bleibt aber sichtbar.
    vorher = _inv_lauf("cb200e4", "board_leer_nach_ende", "stille_nach_leerem_ende",
                        "werkbank_leer_phase2_gesperrt", "chat_kennt_board_nicht",
                        "chat_kennt_transkript_nicht", "raumcheck_domainweit")
    nachher = _inv_lauf("abc1234", "station_nicht_erreicht:p1-begriffe")
    md = ab.vergleichstabelle(vorher, nachher)
    assert "Abnahme erfüllt: ja" in md
    assert "station_nicht_erreicht:p1-begriffe" in md  # Restbefunde nachher
    assert "Restbefunde hoch nachher: 1" in md


_VORHER_VOLL = ("board_leer_nach_ende", "stille_nach_leerem_ende",
                "werkbank_leer_phase2_gesperrt", "chat_kennt_board_nicht",
                "chat_kennt_transkript_nicht", "raumcheck_domainweit")


def _zeile(md, label):
    return next(z for z in md.splitlines() if z.startswith(f"| {label}"))


def test_vergleich_nicht_pruefbar_ist_kein_bestanden():
    """Abnahmelauf 05.10.2026: eine Pruefung, die nicht laufen konnte, stand
    als "–" in der nachher-Spalte und sah aus wie behoben."""
    nachher = _inv_lauf("abc1234", "nicht_pruefbar:raumcheck_domainweit")
    md = ab.vergleichstabelle(_inv_lauf("cb200e4", *_VORHER_VOLL), nachher)
    assert _zeile(md, "Raumcheck domainweit").split("|")[3].strip() == "nicht prüfbar"
    assert "Abnahme erfüllt: ja" not in md
    schluss = md.splitlines()[-1]
    assert schluss.startswith("Abnahme erfüllt: nein") and "Raumcheck domainweit" in schluss
    assert "nicht_pruefbar:raumcheck_domainweit" not in md.split("Restbefunde nachher:")[-1].split(
        "Restbefunde hoch")[0]


def test_vergleich_nicht_pruefbar_vorher():
    vorher = _inv_lauf("cb200e4", *[s for s in _VORHER_VOLL if s != "chat_kennt_board_nicht"],
                       "nicht_pruefbar:chat_kennt_board_nicht")
    md = ab.vergleichstabelle(vorher, _inv_lauf("abc1234"))
    assert _zeile(md, "Chat kennt Board nicht").split("|")[2].strip() == "nicht prüfbar"
    schluss = md.splitlines()[-1]
    assert schluss.startswith("Abnahme erfüllt: nein") and "Chat kennt Board nicht" in schluss


def test_vergleich_hinweiszeile_ueber_der_tabelle():
    md = ab.vergleichstabelle(_inv_lauf("cb200e4"), _inv_lauf("abc1234"))
    zeilen = md.splitlines()
    kopf = next(i for i, z in enumerate(zeilen) if z.startswith("| Befund |"))
    assert "– = nicht gemeldet; nicht prüfbar = Prüfung konnte nicht laufen" in "\n".join(zeilen[:kopf])


def test_leeres_ende_nachher_zaehlt_auch_stille_nach_ende():
    """Nachher schweigt der Bot nach dem Ende (``stille_nach_ende``, z. B.
    weil das 'ende' nie ankam) -- die Zeile darf nicht gruen werden."""
    vorher = _inv_lauf("cb200e4", *_VORHER_VOLL)
    md = ab.vergleichstabelle(vorher, _inv_lauf("abc1234", "stille_nach_ende"))
    assert _zeile(md, "Leeres Ende-Segment").split("|")[3].strip() == "gemeldet (hoch)"
    assert "Abnahme erfüllt: nein" in md
    assert "- stille_nach_ende" not in md     # gehoert zur Zeile, kein Restbefund
    # vorher verlangt weiter das LEERE Ende.
    vorher_ohne = _inv_lauf("cb200e4", *[s for s in _VORHER_VOLL if s != "stille_nach_leerem_ende"],
                            "stille_nach_ende")
    md = ab.vergleichstabelle(vorher_ohne, _inv_lauf("abc1234"))
    assert _zeile(md, "Leeres Ende-Segment").split("|")[2].strip() == "–"
    assert "vorher fehlt: stille_nach_leerem_ende" in md


def test_baue_abnahme_enthaelt_invarianten_abschnitt():
    md = ab.baue_abnahme(
        [_lauf("handy"), _lauf("laptop")], belege={}, b_befunde=[], leitbilder=[],
        harness_notizen=[], modellwahl_satz="")
    assert "## Invarianten" in md
