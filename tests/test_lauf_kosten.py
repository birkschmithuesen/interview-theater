"""Task 2 (BRIEF p57): Kosten-Auswertung eines Browserlaufs ohne
``sqlite3``-CLI (AGENTS.md: auf diesem Host nicht verfuegbar)."""

import subprocess
import sys
from pathlib import Path

import pytest

from interview_theater import db, repo
from simulation import lauf_kosten

CHAT = 7_000_000_000_951
_REPO_WURZEL = Path(__file__).resolve().parent.parent


def _db(verzeichnis, zeilen):
    """``zeilen``: Liste von (art, modell, modus, kosten_chf). Legt
    ``sim.db`` direkt in ``verzeichnis`` an -- derselbe Dateiname, den
    ``main`` aus einem Laufordner baut."""
    pfad = str(Path(verzeichnis) / "sim.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "g", "G")
    for art, modell, modus, kosten in zeilen:
        conn.execute(
            "INSERT INTO aufruf (chat_id, art, modell, modus, kosten_chf, erstellt_am) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (CHAT, art, modell, modus, kosten, repo._jetzt()),
        )
    conn.commit()
    conn.close()
    return pfad


def test_zeilen_ohne_tabelle_liefert_leere_liste(tmp_path):
    pfad = str(tmp_path / "leer.db")
    assert lauf_kosten.zeilen(pfad) == []
    assert lauf_kosten.summe(pfad) == 0.0


def test_zeilen_gruppiert_nach_art_modell_modus(tmp_path):
    pfad = _db(tmp_path, [
        ("gespraech", "kimi", "A", 0.10),
        ("gespraech", "kimi", "A", 0.20),
        ("szene", "opus", "C", 0.50),
        ("erkenner", "gemma", "A", 0.0),
    ])
    daten = lauf_kosten.zeilen(pfad)
    nach_art = {(z["art"], z["modell"], z["modus"]): z for z in daten}
    gespraech = nach_art[("gespraech", "kimi", "A")]
    assert gespraech["anzahl"] == 2
    assert gespraech["chf"] == pytest.approx(0.30)
    szene = nach_art[("szene", "opus", "C")]
    assert szene["anzahl"] == 1
    assert szene["chf"] == pytest.approx(0.50)
    # absteigend nach Kosten: die teuerste Zeile (szene/opus) steht zuerst.
    assert daten[0]["art"] == "szene"


def test_summe_ueber_alle_zeilen(tmp_path):
    pfad = _db(tmp_path, [
        ("gespraech", "kimi", "A", 0.10),
        ("szene", "opus", "C", 0.50),
    ])
    assert lauf_kosten.summe(pfad) == pytest.approx(0.60)


def test_null_kosten_zaehlt_als_null_nicht_als_fehler(tmp_path):
    """``kosten_chf IS NULL`` (NACHTRAG, "aus der Zeit davor") zaehlt als 0,
    nicht als Fehler -- dieselbe Zusage wie beim Produktcode (db.py,
    Kommentar an ``aufruf.kosten_chf``)."""
    pfad = _db(tmp_path, [("gespraech", "kimi", "A", None)])
    daten = lauf_kosten.zeilen(pfad)
    assert daten[0]["chf"] == 0.0
    assert lauf_kosten.summe(pfad) == 0.0


def test_fehlende_modell_oder_modus_zeigt_fragezeichen(tmp_path):
    pfad = _db(tmp_path, [("verdichter", None, None, 0.05)])
    daten = lauf_kosten.zeilen(pfad)
    assert daten[0]["modell"] == "?"
    assert daten[0]["modus"] == "?"


def test_baue_tabelle_hat_kopf_und_summenzeile_auch_ohne_zeilen(tmp_path):
    pfad = str(tmp_path / "leer.db")
    tabelle = lauf_kosten.baue_tabelle(pfad)
    assert "| art | modell | modus | anzahl | CHF |" in tabelle
    assert "**Summe**" in tabelle
    assert "**0.0000**" in tabelle


def test_baue_tabelle_zeigt_jede_zeile_und_die_summe(tmp_path):
    pfad = _db(tmp_path, [
        ("gespraech", "kimi", "A", 0.90),
        ("szene", "opus", "C", 0.70),
    ])
    tabelle = lauf_kosten.baue_tabelle(pfad)
    assert "| gespraech | kimi | A | 1 | 0.9000 |" in tabelle
    assert "| szene | opus | C | 1 | 0.7000 |" in tabelle
    assert "**1.6000**" in tabelle


def test_main_ohne_argument_meldet_fehler_statt_absturz():
    ergebnis = subprocess.run(
        [sys.executable, "-m", "simulation.lauf_kosten"],
        capture_output=True, text=True, cwd=str(_REPO_WURZEL),
    )
    assert ergebnis.returncode != 0
    assert "Aufruf:" in ergebnis.stderr


def test_main_druckt_die_tabelle_fuer_einen_laufordner(tmp_path):
    laufordner = tmp_path / "2026-10-06-handy-priya-p57-101500"
    laufordner.mkdir()
    _db(laufordner, [("gespraech", "kimi", "A", 0.33)])
    ergebnis = subprocess.run(
        [sys.executable, "-m", "simulation.lauf_kosten", str(laufordner)],
        capture_output=True, text=True, cwd=str(_REPO_WURZEL),
    )
    assert ergebnis.returncode == 0
    assert "0.3300" in ergebnis.stdout
