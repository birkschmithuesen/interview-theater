"""Der Padua-Prompt-Dump fuer Phase 1+2 und 3+4, offline in ein Temp-Verzeichnis.

Der Lauf geht nie ins Netz: ``scripts.mitschnitt`` ersetzt den Modellklienten,
``simulation.attrappe.TelegramAttrappe`` den Kanal, und die Datenbank ist eine
Wegwerfdatei.

Scopes p12 (Karte t_bf16f3a7, Phase 1+2), p34 (Task 3, Phase 3+4) und p57
(Task 5, Karte t_db7c6b2c, Phase 5-7) -- zusammen die 35 Dumps mit Treiber;
die restlichen Inventareintraege haben in diesem Skript keinen Treiber.
"""
import re
from pathlib import Path

import pytest

from scripts import erzeuge_prompts_padua_voll as dump
from scripts import prompt_inventar as inv

#: Die fuenf Dumps, fuer die dieser Scope Treiber hat.
TEIL_P1_P2 = (
    "01-gespraech-phase1", "05-gespraech-phase2",
    "13-begriffsboard", "14-diskussion-verdichtung", "15-fragen-ki",
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


@pytest.mark.parametrize("name", TEIL_P1_P2)
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


def test_phase1_gespraech_laeuft_auf_opus(tmp_path):
    """Seit der Padua Phase 1+2 Karte ist jede Phase ausser 3 Opus-faehig."""
    dump.main_fuer_test(tmp_path, nur=["01-gespraech-phase1"])
    kopf = (tmp_path / "01-gespraech-phase1.txt").read_text(encoding="utf-8")
    assert "weg=claude" in kopf


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


def test_die_phase_1_2_eintraege_haben_einen_treiber():
    p12 = [e.datei for e in inv.INVENTAR if e.phase in (1, 2)]
    fehlend = [d for d in p12 if d not in dump.TREIBER]
    assert not fehlend, fehlend


#: Die zehn Dumps, fuer die der Scope p34 Treiber hat (Task 3).
TEIL_P3_P4 = (
    "06-gespraech-phase3", "11-erkenner-aufnahme", "16-verdichter",
    "07-gespraech-phase4", "10-erkenner-verlauf", "12-journal",
    "17-buehnenkarte", "18-szenenfolge", "19-geschichte", "20-szenenfelder",
)


@pytest.mark.parametrize("name", TEIL_P3_P4)
def test_jeder_p34_dump_entsteht(tmp_path, name):
    dump.main_fuer_test(tmp_path, nur=[name])
    text = (tmp_path / f"{name}.txt").read_text(encoding="utf-8")
    assert "=== SYSTEM" in text and "=== NUTZER" in text
    assert len(dump_system(text)) > 200, name


def test_phase3_gespraech_laeuft_nie_ueber_claude(tmp_path):
    """Datenschutz: Phase 3 bleibt unbedingt Kimi (modellwahl.konversation_ueber_claude)."""
    dump.main_fuer_test(tmp_path, nur=["06-gespraech-phase3"])
    assert "weg=claude" not in (tmp_path / "06-gespraech-phase3.txt").read_text(encoding="utf-8")


def test_phase4_gespraech_laeuft_ueber_claude(tmp_path):
    dump.main_fuer_test(tmp_path, nur=["07-gespraech-phase4"])
    assert "weg=claude" in (tmp_path / "07-gespraech-phase4.txt").read_text(encoding="utf-8")


#: 42-uebersetzung steht im Inventar auf phase=4 (naeher an ihrer
#: Einordnung als phase=1/2), ist aber ein phasenunabhaengiger
#: Hintergrundlauf (periodischer Dashboard-Uebersetzer, siehe
#: interview_theater/uebersetzung.py) und kein P3/4-Dump wie die
#: anderen Eintraege hier -- erzeuge_prompts_padua_voll.py deckt bewusst
#: nur seine fuenf bestehenden Dumps ab (Karte t_bf16f3a7). Entscheidung
#: Birk/Karte t_d57c4ddb: kein neuer P34-Treiber, stattdessen diese
#: benannte Ausnahme (er laeuft live, gehoert also nicht in
#: NICHT_LIVE_IN_PADUA).
#:
#: 45-formberater (Karte t_256ec777) und 43-nachspeichern (Karte t_c5d68218):
#: laufen live ab Phase 4, aber ohne eigenen P3/4-Treiber -- derselbe Grund
#: wie bei 42-uebersetzung.
OHNE_P34_TREIBER = ("42-uebersetzung", "43-nachspeichern", "45-formberater")


def test_die_phase_3_4_eintraege_haben_einen_treiber():
    p34 = [e.datei for e in inv.INVENTAR if e.phase in (3, 4)
           and e.datei not in OHNE_P34_TREIBER]
    assert sorted(p34) == sorted(dump.SCOPE_P3_P4)
    assert not [d for d in p34 if d not in dump.TREIBER]


# --- P1-L7: Fixture-Artefakte duerfen nicht mehr im Dump stehen -----------
# (docs/prompt-audit/2026-10-05-padua-p12/lesung.json) --------------------


def test_phase1_dump_nennt_kein_spaetphasenjournal(tmp_path):
    dump.main_fuer_test(tmp_path, nur=["01-gespraech-phase1"])
    text = (tmp_path / "01-gespraech-phase1.txt").read_text(encoding="utf-8")
    nutzer = text.split("=== NUTZER")[1]
    assert "Story as short story" not in nutzer
    assert "fourth scene" not in nutzer.lower()


def test_phase1_dump_fenster_beginnt_nicht_mit_verwaistem_rauschen(tmp_path):
    """Die erste Zeile des Gespraechsverlaufs (nach dem Journal-Block, vor
    "Now:") darf keine Bot-Antwort ohne ihre Frage und kein Rauschen sein --
    siehe ``_GRUNDVERLAUF`` in ``fixture_padua_voll.py`` (P1-L7)."""
    dump.main_fuer_test(tmp_path, nur=["01-gespraech-phase1"])
    text = (tmp_path / "01-gespraech-phase1.txt").read_text(encoding="utf-8")
    nutzer = text.split("=== NUTZER")[1]
    rest = nutzer[nutzer.index("Journal:"):]
    erste_verlaufszeile = rest.split("\n\n", 1)[1].split("\n", 1)[0]
    assert "work status tab" not in erste_verlaufszeile
    assert "is anyone writing this down" not in erste_verlaufszeile


def test_begriffsboard_dump_nennt_keine_blosse_erwaehnung(tmp_path):
    dump.main_fuer_test(tmp_path, nur=["13-begriffsboard"])
    text = (tmp_path / "13-begriffsboard.txt").read_text(encoding="utf-8")
    assert "the group returns to it twice" not in text


# --- Scope p57 (Task 5, Karte t_db7c6b2c): Phase 5-7, offline -------------


#: Die 25 Dumps, fuer die dieser Scope Treiber hat.
TEIL_P5_P7 = (
    "08-gespraech-phase5", "21-schaerfung", "22-entwurf-uebersicht",
    "23-sprachprofil", "24-kernzitate", "04-szene-prosa-phase6",
    "02-gespraech-phase6", "25-kurzgeschichte", "03-kurzgeschichte-phase6",
    "35-dramaturgie-b1", "36-dramaturgie-a2", "37-dramaturgie-a6",
    "38-dramaturgie-a9", "39-dramaturgie-a10", "40-dramaturgie-a11",
    "41-dramaturgie-c1", "09-gespraech-phase7", "27-sprechweise",
    "28-szene-dialog", "29-szene-monolog", "30-szene-chor", "31-szene-lied",
    "32-szene-rap", "34-stueckpruefung",
    "43-prueflauf-ueberarbeitung", "44-nachpass",
)


def test_scope_p57_ist_genau_die_liste_der_treiber():
    assert dump.SCOPES["p57"] == dump.SCOPE_P5_P7
    assert sorted(dump.SCOPE_P5_P7) == sorted(TEIL_P5_P7)


@pytest.mark.parametrize("name", TEIL_P5_P7)
def test_jeder_p57_dump_entsteht(tmp_path, name):
    dump.main_fuer_test(tmp_path, nur=[name])
    text = (tmp_path / f"{name}.txt").read_text(encoding="utf-8")
    assert "=== SYSTEM" in text and "=== NUTZER" in text
    assert len(dump_system(text)) > 200, name


def test_die_phase_5_7_eintraege_haben_einen_treiber():
    p57 = [e.datei for e in inv.INVENTAR if e.phase in (5, 6, 7)]
    fehlend = [d for d in p57 if d not in dump.TREIBER]
    assert not fehlend, fehlend


@pytest.mark.parametrize("name", TEIL_P5_P7)
def test_kein_dump_traegt_einen_offenen_platzhalter(tmp_path, name):
    """Eine ``{name}``-Luecke, die kein ``.format()`` je fuellte, waere ein
    kaputter Prompt -- gemessen statt geglaubt (Task 5, "kein {platzhalter}
    offen")."""
    dump.main_fuer_test(tmp_path, nur=[name])
    text = (tmp_path / f"{name}.txt").read_text(encoding="utf-8")
    ungefuellt = re.findall(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", text)
    assert not ungefuellt, (name, ungefuellt)


#: Die beiden geprueften Belegzitate aus ``fixture_padua_voll._material`` --
#: jedes woertliche Zitat in einem Phase->=5-Dump muss eines der beiden sein.
_GEPRUEFTE_ZITATE = (
    "Ich habe drei Stunden auf dieser Bank gesessen und nichts gegessen.",
    "Der Lautsprecher hat geredet und ich habe kein einziges Wort verstanden.",
)


@pytest.mark.parametrize("name", ("21-schaerfung", "24-kernzitate"))
def test_claude_dumps_phase5_nennen_nur_geprueftes_zitat(tmp_path, name):
    """Was im Prompt an woertlichem Interviewmaterial steht, muss aus der
    Fixture stammen -- ``zitat_geprueft = 1`` (Task 5, Testliste).

    Nicht ``23-sprachprofil``: dessen Nutzertext ist das volle Transkript
    (``sprachprofil.baue_nutzertext``), nicht eine Materialliste mit
    ``Quote:``-Zeilen -- das Modell zieht die Zitate dort selbst, und
    ``zitat.pruefe`` prueft sie erst danach.

    **Nur der Nutzertext**, nicht die Systemanweisung: ``prompts/kernzitate.md``
    traegt selbst ein Few-Shot-Beispiel mit einer erfundenen ``Quote:``-Zeile
    ("I sewed for twenty years...") -- die gehoert dem Prompt, nicht der
    Fixture, und darf den Fixture-Check nicht roeten."""
    dump.main_fuer_test(tmp_path, nur=[name])
    text = (tmp_path / f"{name}.txt").read_text(encoding="utf-8")
    zeilen_mit_zitat = [z for z in dump_nutzer(text).splitlines() if "Quote:" in z]
    assert zeilen_mit_zitat, name
    for zeile in zeilen_mit_zitat:
        assert any(z in zeile for z in _GEPRUEFTE_ZITATE), zeile


def test_sprachprofil_transkript_enthaelt_die_geprueften_zitate(tmp_path):
    """Dasselbe Ziel wie oben, nur gegen das volle Transkript statt gegen
    ``Quote:``-Zeilen."""
    dump.main_fuer_test(tmp_path, nur=["23-sprachprofil"])
    nutzer = dump_nutzer(
        (tmp_path / "23-sprachprofil.txt").read_text(encoding="utf-8"))
    assert any(z in nutzer for z in _GEPRUEFTE_ZITATE)


#: Die Szenen-Dumps aus Phase 6/7, die einen Laengen-Budget-Block tragen
#: muessen (``laengen.block_szene``, Task 5 Testliste).
_SZENEN_MIT_LAENGENBLOCK = (
    "04-szene-prosa-phase6", "28-szene-dialog", "29-szene-monolog",
    "30-szene-chor", "31-szene-lied", "32-szene-rap", "44-nachpass",
)


@pytest.mark.parametrize("name", _SZENEN_MIT_LAENGENBLOCK)
def test_szenen_dumps_tragen_den_laengenblock(tmp_path, name):
    dump.main_fuer_test(tmp_path, nur=[name])
    text = (tmp_path / f"{name}.txt").read_text(encoding="utf-8")
    nutzer = dump_nutzer(text)
    assert "How long this scene should be" in nutzer, name


def dump_nutzer(text: str) -> str:
    return text.split("=== NUTZER")[1]


def test_phase6_gespraech_laeuft_ueber_claude(tmp_path):
    dump.main_fuer_test(tmp_path, nur=["02-gespraech-phase6"])
    assert "weg=claude" in (tmp_path / "02-gespraech-phase6.txt").read_text(encoding="utf-8")


def test_phase7_gespraech_laeuft_ueber_claude(tmp_path):
    dump.main_fuer_test(tmp_path, nur=["09-gespraech-phase7"])
    assert "weg=claude" in (tmp_path / "09-gespraech-phase7.txt").read_text(encoding="utf-8")


def test_die_fuenf_szenenform_dumps_tragen_je_ihre_form(tmp_path):
    """28-32 unterscheiden sich NUR in der Form -- jede muss im System- oder
    Nutzertext der Szene stehen (sonst dumpen alle fuenf denselben Prompt)."""
    formen = {
        "28-szene-dialog": "dialog",
        "29-szene-monolog": "monolog",
        "30-szene-chor": "chor",
        "31-szene-lied": "lied",
        "32-szene-rap": "rap",
    }
    for name, form in formen.items():
        dump.main_fuer_test(tmp_path, nur=[name])
        text = (tmp_path / f"{name}.txt").read_text(encoding="utf-8")
        assert form in text.lower(), (name, form)
