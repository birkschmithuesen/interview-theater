"""Der vollstaendige Padua-Prompt-Dump, offline in ein Temp-Verzeichnis.

Der Lauf geht nie ins Netz: ``scripts.mitschnitt`` ersetzt den Modellklienten,
``simulation.attrappe.TelegramAttrappe`` den Kanal, und die Datenbank ist eine
Wegwerfdatei.
"""
from pathlib import Path

import pytest

from scripts import erzeuge_prompts_padua_voll as dump
from scripts import fixture_padua_voll as fixture
from scripts import prompt_inventar as inv

#: Alle Dumps des Inventars -- Task 7 hebt die Teilliste aus Task 6 auf.
ALLE = tuple(e.datei for e in inv.INVENTAR)


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


@pytest.mark.parametrize("name", ALLE)
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


def test_alle_inventareintraege_haben_einen_treiber():
    fehlend = [e.datei for e in inv.INVENTAR if e.datei not in dump.TREIBER]
    assert not fehlend, fehlend


def test_ein_voller_lauf_schreibt_jede_datei_und_die_uebersicht(tmp_path):
    zeilen = dump.main_fuer_test(tmp_path)
    assert len(zeilen) == len(inv.INVENTAR)
    for eintrag in inv.INVENTAR:
        assert (tmp_path / f"{eintrag.datei}.txt").exists(), eintrag.datei
    kopf = (tmp_path / "uebersicht.tsv").read_text(
        encoding="utf-8").splitlines()[0].split("\t")
    assert kopf == list(dump.TSV_SPALTEN)


def test_voller_lauf_kontaminiert_keine_sprachstile(tmp_path):
    """Review-Fund Task 7: ``27-sprechweise``s Treiber nullt kurzzeitig
    ``figur.sprachstil`` der ersten Figur der Phase-7-Gruppe (``chats[7]``),
    um ``sprechweise._lauf`` ueberhaupt einen Modellaufruf machen zu lassen.
    Ohne Wiederherstellung sah jeder spaetere Dump derselben Gruppe
    (``28``-``32-szene-*``, ``34-stueckpruefung``, die Dramaturgie-Fragen ab
    Phase 7) eine Figur ohne Stil, obwohl die Fixture allen drei Figuren
    einen gibt (``szene._figuren_text`` listet ALLE Figuren der Gruppe ohne
    Besetzungsfilter). Isoliert gefahren (``nur=["28-szene-dialog"]``) faellt
    das nicht auf, weil ``_lauf`` pro Test eine frische Fixture baut -- nur
    der volle Lauf (alle Eintraege zusammen, dieselbe Verbindung) zeigt die
    Kontamination."""
    dump.main_fuer_test(tmp_path)
    nutzer = (tmp_path / "28-szene-dialog.txt").read_text(
        encoding="utf-8").split("=== NUTZER", 1)[1]
    for name, _beschreibung, stil in fixture._FIGUREN:
        if name in nutzer:
            assert stil in nutzer, (
                f"{name}: Sprachstil fehlt im Dump nach dem vollen Lauf")


def test_die_gespraechsdumps_tragen_blockanteile(tmp_path):
    dump.main_fuer_test(tmp_path, nur=["07-gespraech-phase4"])
    zeile = dict(zip(
        dump.TSV_SPALTEN,
        (tmp_path / "uebersicht.tsv").read_text(
            encoding="utf-8").splitlines()[1].split("\t")))
    for spalte in ("tok_system", "tok_status", "tok_verlauf",
                   "tok_zusammenfassung"):
        assert zeile[spalte] != "", spalte
        assert int(zeile[spalte]) >= 0
    assert int(zeile["tok_verlauf"]) > 0
    assert int(zeile["tok_zusammenfassung"]) > 0


def test_blockgruppen_decken_jeden_block_des_umrisses_ab():
    """Sonst faellt ein Block still aus der Messung -- und genau das war
    Befund C.1 des Audits vom 06.09.2026 (die Systemanweisung fehlte im
    Umriss, also war ein Viertel des Prompts unvermessen)."""
    from interview_theater import kontext

    gruppiert = {name for namen in dump.BLOCKGRUPPEN.values() for name in namen}
    assert set(kontext._REIHENFOLGE) == gruppiert, (
        set(kontext._REIHENFOLGE) ^ gruppiert)


def test_szene_und_kurzgeschichte_sind_als_gebaut_gekennzeichnet(tmp_path):
    dump.main_fuer_test(tmp_path, nur=["28-szene-dialog"])
    kopf = (tmp_path / "28-szene-dialog.txt").read_text(encoding="utf-8")
    assert "quelle=gebaut" in kopf


def test_die_fuenf_formen_liefern_fuenf_verschiedene_systemtexte(tmp_path):
    namen = ["28-szene-dialog", "29-szene-monolog", "30-szene-chor",
             "31-szene-lied", "32-szene-rap"]
    dump.main_fuer_test(tmp_path, nur=namen)
    texte = {
        n: dump_system((tmp_path / f"{n}.txt").read_text(encoding="utf-8"))
        for n in namen
    }
    assert len(set(texte.values())) == 5, "ein Regelblock je Form"


def test_die_richterdumps_laufen_nicht_auf_dem_schreibermodell(tmp_path):
    """Self-Enhancement Bias: der Richter ist nie das schreibende Modell
    (dramaturgie/fanout.waehle_richter)."""
    namen = [e.datei for e in inv.INVENTAR if e.art.startswith("dramaturgie_")]
    dump.main_fuer_test(tmp_path, nur=namen)
    for name in namen:
        kopf = (tmp_path / f"{name}.txt").read_text(encoding="utf-8")
        assert "weg=infomaniak" in kopf, name
        assert "claude" not in kopf.splitlines()[1], name


def test_phase7_szene_sieht_den_sprachstil_der_figuren(tmp_path):
    """Padua M1: figur.sprachstil steht als eigene Zeile im Szenen-Prompt."""
    dump.main_fuer_test(tmp_path, nur=["28-szene-dialog"])
    text = (tmp_path / "28-szene-dialog.txt").read_text(encoding="utf-8")
    assert "questions instead of statements" in text


def test_der_lauf_hinterlaesst_os_environ_exakt_wie_vorher(tmp_path, monkeypatch):
    """t_809cb7f1: _lauf() setzte IT_WORKSHOP/IT_DB ohne sie zurueckzusetzen --
    IT_WORKSHOP blieb fuer den Rest der pytest-Session auf 'padua-2026' stehen
    und faerbte jeden spaeteren Test rot, der workshop.workbench_bearbeitbar()
    durchlaeuft (das Profil hat [web] workbench_bearbeitbar = false).

    Exakt heisst hier: fehlte die Variable VOR dem Lauf, muss sie NACHHER
    wieder fehlen -- nicht nur 'irgendeinen' alten Wert tragen."""
    monkeypatch.delenv("IT_WORKSHOP", raising=False)
    monkeypatch.delenv("IT_DB", raising=False)
    import os

    assert "IT_WORKSHOP" not in os.environ
    assert "IT_DB" not in os.environ

    dump.main_fuer_test(tmp_path, nur=["13-begriffsboard"])

    assert "IT_WORKSHOP" not in os.environ, (
        "IT_WORKSHOP leakt aus _lauf() in die Prozessumgebung")
    assert "IT_DB" not in os.environ, (
        "IT_DB leakt aus _lauf() in die Prozessumgebung")


def test_der_lauf_stellt_einen_vorher_gesetzten_wert_auch_bei_abbruch_wieder_her(
    tmp_path, monkeypatch
):
    """War vor dem Lauf bereits ein anderer IT_WORKSHOP gesetzt (z.B. der
    echte Betriebs-Workshop), darf _lauf() ihn nicht dauerhaft durch
    'padua-2026' ersetzen -- auch wenn ``setdefault`` den fremden Wert gar
    nicht erst ueberschreibt und deshalb ``workshop.name() != 'padua-2026'``
    sofort mit SystemExit abbricht. Das finally muss trotzdem greifen."""
    monkeypatch.setenv("IT_WORKSHOP", "dortmund-2026")
    monkeypatch.setenv("IT_DB", "/pfad/zur/echten/betriebsdatenbank.db")
    import os

    with pytest.raises(SystemExit):
        dump.main_fuer_test(tmp_path, nur=["13-begriffsboard"])

    assert os.environ["IT_WORKSHOP"] == "dortmund-2026"
    assert os.environ["IT_DB"] == "/pfad/zur/echten/betriebsdatenbank.db"
