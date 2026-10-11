"""Tests fuer die Messung der Zitatauswahl (Karte t_2349e9a8 / t_2f905d2c):
Gold-Korpus, Recall@10 je Ziel, Mutationstest, Neu-Lauf ohne Kimi.

Kein Netzzugriff: der Claude-Proxy ist eine Attrappe."""

import ast
import json
from pathlib import Path

import pytest

from interview_theater import llm, repo, schaerfung, szene_claude

ZITAT_A = "Also ich, ich habe zwanzig Jahre genaeht und keiner hat gefragt."
TRANSKRIPT_A = "Wie war die Arbeit? " + ZITAT_A + " Danach war Ruhe."
ZITAT_B = "Am Samstag faehrt keiner, da steht die Stadt still."
TRANSKRIPT_B = "Was ist am Wochenende? " + ZITAT_B
ZITAT_C = "Der Hund vom Nachbarn bellt jeden Morgen um sechs."
TRANSKRIPT_C = "Und die Nachbarn? " + ZITAT_C


def _interview(conn, transkript, themen, name):
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_aufnahme_name(conn, kopf_id, name)
    repo.setze_transkript(conn, kopf_id, transkript)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Eine Zusammenfassung.", themen)
    return kopf_id


@pytest.fixture
def lage(conn):
    """Drei Interviews mit je einem geprueften Thema, zwei Szenen."""
    _interview(conn, TRANSKRIPT_A, [
        {"thema": "Arbeit", "beleg_zitat": ZITAT_A, "zitat_geprueft": 1}], "A")
    _interview(conn, TRANSKRIPT_B, [
        {"thema": "Stadt", "beleg_zitat": ZITAT_B, "zitat_geprueft": 1}], "B")
    _interview(conn, TRANSKRIPT_C, [
        {"thema": "Nachbarn", "beleg_zitat": ZITAT_C, "zitat_geprueft": 1}], "C")
    for nummer, titel in ((1, "Im Treppenhaus"), (2, "Am Kiosk")):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.setze_szenenfeld(conn, szene_id, "titel", titel)
    conn.commit()
    return conn


def _themen(conn):
    """thema -> id"""
    return {z["thema"]: z["id"] for z in repo.gepruefte_themen(conn, 1)}


def _szenen(conn):
    """nummer -> id"""
    return {s["nummer"]: s["id"] for s in repo.hole_szenen(conn, 1)}


# --- repo -------------------------------------------------------------------


def test_historie_liefert_auch_entfernte_zeilen(lage):
    t, s = _themen(lage), _szenen(lage)
    repo.lege_schaerfung_an(lage, 1, [
        {"verdichtung_thema_id": t["Arbeit"], "szene_id": s[1], "staerke": 3},
        {"verdichtung_thema_id": t["Stadt"], "szene_id": s[2], "staerke": 2},
    ])
    erste = repo.schaerfungen_historie(lage, 1)[0]["id"]
    repo.entferne_schaerfung(lage, erste)

    zeilen = repo.schaerfungen_historie(lage, 1)

    assert [z["verdichtung_thema_id"] for z in zeilen] == [t["Arbeit"], t["Stadt"]]
    assert zeilen[0]["entfernt_am"] is not None
    assert zeilen[1]["staerke"] == 2 and zeilen[1]["runde"] == 1


def test_themen_mit_aufnahme_tragen_aufnahme_und_pruefung(lage):
    zeilen = repo.themen_mit_aufnahme(lage, 1)

    assert [z["thema"] for z in zeilen] == ["Arbeit", "Stadt", "Nachbarn"]
    assert all(z["zitat_geprueft"] == 1 for z in zeilen)
    assert all(z["verdichtung_entfernt_am"] is None for z in zeilen)
    assert zeilen[0]["aufnahme_id"] != zeilen[1]["aufnahme_id"]
