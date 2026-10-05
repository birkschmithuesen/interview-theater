"""Jeder Modellaufruf im Produktivcode ist im Prompt-Dump -- oder begruendet nicht.

Das ist der Nagel, der den Prompt-Check zum festen Schritt macht (Architekt D2,
Muster ``tests/test_knoepfe_struktur.py``): wer einen neuen Modellaufruf baut,
macht die Suite rot, bis er im Inventar steht. Gelesen wird der **Quelltext**,
nicht das Verhalten -- ``art`` wird fast immer positionell uebergeben, ein
``grep 'art="'`` findet fast nichts.
"""
import pytest

from scripts import prompt_inventar as inv


def test_der_scanner_findet_die_bekannten_stellen():
    """Sichert den Scanner selbst ab: findet er die Stellen nicht mehr, ist
    nicht der Code sauber, sondern der Scanner kaputt."""
    stellen = inv.aufrufstellen()
    assert len(stellen) >= 25, len(stellen)
    paare = {(s.modul, s.art_quelle) for s in stellen}
    assert ("interview_theater.verdichter", "'verdichter'") in paare
    assert ("interview_theater.begriffsboard", "ART") in paare
    assert ("interview_theater.ablauf", "'gespraech'") in paare


def test_keine_offene_aufrufstelle():
    offen = inv.offen()
    assert not offen, "\n".join(
        f"{s.modul}:{s.zeile} {s.aufruf} art={s.art_quelle}" for s in offen
    )


def test_jeder_inventareintrag_zeigt_auf_eine_echte_aufrufstelle():
    paare = {(s.modul, s.art_quelle) for s in inv.aufrufstellen()}
    for eintrag in inv.INVENTAR:
        assert (eintrag.modul, eintrag.art_quelle) in paare, eintrag


def test_jede_ausnahme_traegt_einen_grund():
    for schluessel, grund in inv.NICHT_LIVE_IN_PADUA.items():
        assert grund.strip(), schluessel
        assert len(grund) > 20, (schluessel, grund)


def test_dumpnamen_sind_eindeutig_und_jede_phase_kommt_vor():
    namen = [e.datei for e in inv.INVENTAR]
    assert len(namen) == len(set(namen))
    assert {e.phase for e in inv.INVENTAR} >= {1, 2, 3, 4, 5, 6, 7}


def test_gebaute_eintraege_begruenden_sich():
    for eintrag in inv.INVENTAR:
        if eintrag.weg == "gebaut":
            assert len(eintrag.grund) > 20, eintrag
        else:
            assert eintrag.weg == "abgefangen", eintrag


def test_die_vier_dumps_des_vorgaengers_behalten_ihre_namen():
    """Vergleichbarkeit mit docs/prompt-audit/2026-10-02-padua-p2 (D1)."""
    namen = {e.datei for e in inv.INVENTAR}
    for alt in ("01-gespraech-phase1", "02-gespraech-phase6",
                "03-kurzgeschichte-phase6", "04-szene-prosa-phase6"):
        assert alt in namen, alt
