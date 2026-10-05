"""Der vollstaendige Padua-Prompt-Dump, offline in ein Temp-Verzeichnis.

Der Lauf geht nie ins Netz: ``scripts.mitschnitt`` ersetzt den Modellklienten,
``simulation.attrappe.TelegramAttrappe`` den Kanal, und die Datenbank ist eine
Wegwerfdatei.
"""
from pathlib import Path

import pytest

from scripts import erzeuge_prompts_padua_voll as dump
from scripts import prompt_inventar as inv

#: Die Dumps, die Task 6 fahren muss. Task 7 setzt diese Liste auf
#: ``[e.datei for e in inv.INVENTAR]`` hoch.
TEIL1 = (
    "01-gespraech-phase1", "05-gespraech-phase2", "06-gespraech-phase3",
    "10-erkenner-verlauf", "11-erkenner-aufnahme", "12-journal",
    "13-begriffsboard", "14-diskussion-verdichtung", "15-fragen-ki",
    "16-verdichter",
)


def test_umgebung_spiegelt_den_padua_betrieb():
    e = dump.umgebung()
    assert e.szene_anbieter == "claude"
    assert e.szene_modell == "claude-opus-5"
    assert e.llm_modell.startswith("moonshotai/")
    assert e.erkenner_modell.startswith("google/gemma")


def test_anteile_fasst_die_bloecke_in_vier_gruppen():
    umriss = {
        "system": 100,
        "bloecke": {"arbeitsstand": 10, "festlegungen": 5, "fenster": 40,
                    "ausloeser": 2, "verdichtungen": 20, "journal": 3},
        "gesamt": 80, "gesamt_mit_system": 180, "gekuerzt": False,
    }
    assert dump.anteile(umriss) == {
        "tok_system": 100, "tok_status": 15, "tok_verlauf": 42,
        "tok_zusammenfassung": 23,
    }


def test_kopfzeile_nennt_art_phase_weg_modell_und_quelle():
    from scripts.mitschnitt import Aufruf

    eintrag = inv.eintrag_fuer("13-begriffsboard")
    zeile = dump.kopfzeile(eintrag, Aufruf("begriffsboard", "claude",
                                           "claude-opus-5", "S", "N"))
    for stueck in ("art=begriffsboard", "phase=1", "weg=claude",
                   "modell=claude-opus-5", "quelle=abgefangen"):
        assert stueck in zeile, stueck


@pytest.mark.parametrize("name", TEIL1)
def test_jeder_dump_entsteht_und_traegt_system_und_nutzertext(tmp_path, name):
    zeilen = dump.main_fuer_test(tmp_path, nur=[name])
    pfad = tmp_path / f"{name}.txt"
    assert pfad.exists(), name
    text = pfad.read_text(encoding="utf-8")
    assert "=== SYSTEM" in text and "=== NUTZER" in text
    system = dump_system(text)
    assert len(system) > 200, (name, len(system))
    assert len(zeilen) == 1


def dump_system(text: str) -> str:
    return text.split("=== NUTZER")[0]


def test_phase3_gespraech_laeuft_auf_kimi_und_nicht_auf_opus(tmp_path):
    """Die unverhandelbare Ausnahme (modellwahl.py, Phase 3 = Interviews)."""
    dump.main_fuer_test(tmp_path, nur=["06-gespraech-phase3"])
    kopf = (tmp_path / "06-gespraech-phase3.txt").read_text(encoding="utf-8")
    assert "weg=infomaniak" in kopf
    assert "modell=moonshotai/" in kopf


def test_phase1_gespraech_laeuft_auf_opus(tmp_path):
    """Seit der Padua Phase 1+2 Karte ist jede Phase ausser 3 Opus-faehig."""
    dump.main_fuer_test(tmp_path, nur=["01-gespraech-phase1"])
    kopf = (tmp_path / "01-gespraech-phase1.txt").read_text(encoding="utf-8")
    assert "weg=claude" in kopf


def test_verdichter_laeuft_immer_auf_kimi(tmp_path):
    """verdichter.py ruft modellwahl NICHT an -- das ist die ganze
    Durchsetzung (modellwahl.py, Moduldocstring)."""
    dump.main_fuer_test(tmp_path, nur=["16-verdichter"])
    kopf = (tmp_path / "16-verdichter.txt").read_text(encoding="utf-8")
    assert "weg=infomaniak" in kopf
    assert "modell=moonshotai/" in kopf


def test_erkenner_und_journal_laufen_auf_gemma(tmp_path):
    for name in ("10-erkenner-verlauf", "11-erkenner-aufnahme", "12-journal"):
        dump.main_fuer_test(tmp_path, nur=[name])
        kopf = (tmp_path / f"{name}.txt").read_text(encoding="utf-8")
        assert "modell=google/gemma" in kopf, name


def test_ein_dump_ohne_aufzeichnung_ist_ein_lauter_fehler(tmp_path):
    """Ein Treiber, der den Aufruf nicht erreicht, darf keine leere Datei
    hinterlassen -- sonst sieht ein fehlender Pfad aus wie ein kurzer Prompt."""
    with pytest.raises(dump.TreiberFehler):
        dump.main_fuer_test(tmp_path, nur=["99-gibt-es-nicht"])


def test_das_skript_oeffnet_nie_betrieb():
    import inspect

    quelle = inspect.getsource(dump)
    for wort in ("betrieb/", "soap.db"):
        assert wort not in quelle, wort
