import json

from scripts import ab_pipeline_vs_tools as ab


def _z(modus, **kw):
    basis = {"achse": "A", "sprache": "de", "modus": modus, "id": "x", "treffer": 1,
             "fp": 0, "fn": 0, "still_fp": 0, "ohne_korpusart": 0, "abgelehnt": 0,
             "abbruch": None, "runden": 1, "eingabe_token": 100, "ausgabe_token": 10,
             "dauer_ms": 1000, "fehler": None, "aufnahme": False,
             "absicht_treffer": 1, "absicht_fp": 0, "absicht_fn": 0}
    basis.update(kw)
    return basis


def _c(variante, gruppe="G1", ziel="G1:szene:1", recall=0.5, **kw):
    basis = {"achse": "C", "gruppe": gruppe, "ziel": ziel, "variante": variante,
             "recall_at_10": recall, "runden": 1, "abbruch": None, "eingabe_token": 10,
             "ausgabe_token": 5, "dauer_ms": 100, "kosten_chf": 0.0, "fehler": None}
    basis.update(kw)
    return basis


VOR = {"ACHSE_B": "nein", "ACHSE_C": "nein", "PROXY_TOOLS": "ja"}


def test_bericht_hat_tabelle_je_kennzahl_und_beide_modi():
    text = ab.baue_bericht([_z("json"), _z("tools", runden=3, dauer_ms=3000)], VOR, ["cmd"])
    for kennzahl in ("Treffer", "stille Fehler", "abgelehnt (laut)", "Abbrüche",
                     "Latenz", "Token", "Kosten", "Absicht erkannt"):
        assert kennzahl in text
    assert "Kennzahl | json | tools |" in text


def test_opus_kosten_sind_abo_keine_erfundene_chf_zahl():
    text = ab.baue_bericht([_z("json"), _z("tools")], VOR, [])
    assert "0 CHF (Abo)" in text


def test_fehlende_achsen_stehen_als_null_mit_grund():
    text = ab.baue_bericht([_z("json")], VOR, [])
    assert "Achse B: 0 — Padua-Testsatz fehlte" in text
    assert "Achse C: 0 — Gold-Korpus fehlte" in text


def test_grund_per_option_ueberschreibt():
    text = ab.baue_bericht([_z("json")], VOR, [], gruende={"C": "nicht freigegeben (Kosten)"})
    assert "Achse C: 0 — nicht freigegeben (Kosten)" in text


def test_aufnahme_faelle_getrennt():
    zeilen = [_z("json", id="g1"), _z("tools", id="g1"),
              _z("json", id="a1", aufnahme=True, treffer=7),
              _z("tools", id="a1", aufnahme=True, treffer=7)]
    text = ab.baue_bericht(zeilen, VOR, [])
    assert "Aufnahme-Fälle" in text and "Infomaniak" in text
    assert text.count("Kennzahl | json | tools |") == 2


def test_nebenzaehlung_erklaert():
    text = ab.baue_bericht([_z("json"), _z("tools", absicht_treffer=2)], VOR, [])
    assert "abgelehnt" in text and "Nebenzählung" in text


def test_achse_c_recall_neben_b0_fallback_nicht_gemittelt(tmp_path):
    zeilen = [_c("pipeline_opus", recall=1.0), _c("pipeline_opus", ziel="G1:szene:2", recall=0.0),
              _c("pipeline_opus", ziel="G1:szene:3", recall=None, fehler="fallback_kimi",
                 kosten_chf=0.25),
              _c("agent_kimi", recall=0.5, kosten_chf=0.1)]
    text = ab.baue_bericht(zeilen, VOR, [], b0={"G1": (0.25, 4)})
    assert "Recall@10" in text
    assert "0.50 (n=2)" in text  # (1.0+0.0)/2, Fallback nicht gemittelt
    assert "0.25 (n=4)" in text  # B0
    assert "Rückfall auf Kimi (fallback_kimi, nicht gemittelt) | 1 | 0 |" in text
    assert "0.2500 CHF" in text and "0.1000 CHF" in text
    assert "Achse C: 0" not in text


def test_was_die_messung_nicht_zeigt():
    text = ab.baue_bericht([_z("json")], VOR, [])
    abschnitt = text[text.index("## Was die Messung NICHT zeigt"):]
    for stichwort in ("Laien", "Gruppenerlebnis", "§ 3.4", "Szenenkern", "3/27", "Infomaniak"):
        assert stichwort in abschnitt


def test_keine_empfehlung_umstellen():
    text = ab.baue_bericht([_z("json"), _z("tools")], VOR, [])
    assert "Die Entscheidung trifft Birk" in text
    assert "Vision/Pflege" in text
    assert "empfehlen umzustellen" not in text.lower()


def test_kommandos_zum_nachrechnen_stehen_drin():
    text = ab.baue_bericht([_z("json")], VOR, ["uv run ... erkenner --sprache de"])
    assert "## Kommandos zum Nachrechnen" in text
    assert "uv run ... erkenner --sprache de" in text


def test_kein_wortlaut_aus_rohzeilen():
    z = _z("tools", geliefert=[{"art": "x", "wert": "GEHEIMER WORTLAUT"}], abgelehnt_gruende={"GEHEIM": 1})
    assert "GEHEIM" not in ab.baue_bericht([_z("json"), z], VOR, [])


def test_cli_bericht_schreibt_datei_und_ueberlebt_fehlende_rohdatei(tmp_path):
    roh = tmp_path / "A.jsonl"
    roh.write_text(json.dumps(_z("json")) + "\n" + json.dumps(_z("tools")) + "\n", encoding="utf-8")
    aus = tmp_path / "b.md"
    rc = ab.main(["bericht", "--roh", str(roh), str(tmp_path / "gibtsnicht.jsonl"),
                  "--aus", str(aus), "--achse-c-grund", "nicht freigegeben (Kosten)",
                  "--gold", str(tmp_path / "kein_gold.jsonl")])
    assert rc == 0
    text = aus.read_text(encoding="utf-8")
    assert "Achse C: 0 — nicht freigegeben (Kosten)" in text
    assert "Achse B: 0 — Padua-Testsatz fehlte" in text
    assert "bericht --roh" in text


def _aufrufe(*namen, abgelehnt=()):
    return [{"name": n, "eingabe": {}, "ok": n not in abgelehnt, "fehler": None}
            for n in namen]


def test_werkzeugtabelle_zaehlt_aufrufe_und_abgelehnte_je_achse():
    zeilen = [
        _z("tools", aufrufe=_aufrufe("aenderung_melden", "aenderung_melden", "setze_ort",
                                     abgelehnt=("setze_ort",))),
        _z("tools", achse="B", aufrufe=_aufrufe("aenderung_melden")),
        _z("json"),
    ]
    text = ab.baue_bericht(zeilen, VOR, [])
    assert "Aufrufe je Werkzeug" in text
    assert "| Achse A | aenderung_melden | 2 | 0 |" in text
    assert "| Achse A | setze_ort | 1 | 1 |" in text
    assert "| Achse B | aenderung_melden | 1 | 0 |" in text


def test_ungerufene_werkzeuge_stehen_als_nicht_geprueft_mit_anteil():
    from interview_theater import erkenner_werkzeuge, stueck

    zeilen = [_z("tools", aufrufe=_aufrufe("aenderung_melden", "aenderung_melden",
                                           "aenderung_melden", "setze_ort"))]
    text = ab.baue_bericht(zeilen, VOR, [])
    abschnitt = text[text.index("## Was die Messung NICHT zeigt"):]
    assert "nicht geprüft" in abschnitt
    assert "75 %" in abschnitt and "Mess-DB" in abschnitt
    for name in stueck.WERKZEUGE:
        if name != "setze_ort":
            assert name in abschnitt
    assert "setze_ort" not in abschnitt.split("nicht geprüft")[1].split("\n")[0]
    assert erkenner_werkzeuge.GENERISCH in abschnitt


def test_kosten_aus_rohzeilen_abgeleitet():
    text = ab.baue_bericht([_z("json", kosten_chf=0.0), _z("tools", kosten_chf=0.5)], VOR, [])
    assert "0.5000 CHF" in text
    assert "kosten_chf" in text


def test_messgrenzen_nennen_asymmetrische_timeouts():
    from interview_theater import szene_claude

    text = ab.baue_bericht([_z("json")], VOR, [])
    assert "60 s" in text
    assert f"{szene_claude.GESAMT_TIMEOUT_S:.0f} s" in text
