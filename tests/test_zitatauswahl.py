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


# --- schaerfung.werte_aus -----------------------------------------------------


def test_werte_aus_haelt_reihenfolge_und_regeln():
    nach_nummer = {
        1: {"thema_id": 11, "zitat": "eins zwei drei vier"},
        2: {"thema_id": 22, "zitat": "fuenf sechs sieben acht"},
    }
    ziel = {"art": "szene", "id": 7}
    ergebnis = {
        "eintrag_nummern": [2, 99, 1, 1],
        "staerke": [3, 3, 2, 1],
        "begruendungen": ["b2", "erfunden", "b1", "zu schwach"],
        "zitate": ["", "", "eins zwei", ""],
    }

    zuordnungen = schaerfung.werte_aus(ergebnis, ziel, nach_nummer)

    assert [(z["verdichtung_thema_id"], z["staerke"]) for z in zuordnungen] == [(22, 3), (11, 2)]
    assert all(z["szene_id"] == 7 for z in zuordnungen)
    assert zuordnungen[0]["begruendung"] == "b2"


# --- Gold-Korpus ------------------------------------------------------------

from scripts import zitatauswahl as za  # noqa: E402

QUELLE = [
    {"id": "G1-1", "gruppe": "G1", "datei": "x.md", "karte": 1, "szene": 1,
     "frage": "How was work?", "label": "scene 1",
     "wortlaut": "Ich habe zwanzig Jahre genaeht … keiner hat gefragt."},
    {"id": "G1-2", "gruppe": "G1", "datei": "x.md", "karte": 2, "szene": 2,
     "frage": "Weekend?", "label": "scene 2",
     "wortlaut": "am samstag faehrt keiner, da steht die Stadt"},
]


def test_fragmente_trennt_an_auslassungen():
    assert za.fragmente("«Eins zwei … drei vier.»") == ["Eins zwei", "drei vier"]


def test_verankere_liefert_den_originalwortlaut():
    assert za.verankere("Ich habe zwanzig Jahre genaeht", TRANSKRIPT_A) == "ich habe zwanzig Jahre genaeht"
    assert za.verankere("das hat nie jemand gesagt", TRANSKRIPT_A) is None


def test_gold_aus_der_quelle(lage):
    t, s = _themen(lage), _szenen(lage)

    gold = za.baue_gold(lage, QUELLE, {"G1": 1})

    positiv = [g for g in gold if g["polaritaet"] == "positiv"]
    assert [g["id"] for g in positiv] == ["G1-1", "G1-2"]
    eins = positiv[0]
    assert eins["fragmente"] == ["ich habe zwanzig Jahre genaeht", "keiner hat gefragt"]
    assert eins["verdichtung_thema_id"] == t["Arbeit"] and eins["thema_ids"] == [t["Arbeit"]]
    assert eins["im_pool"] is True
    assert eins["ziel"] == {"art": "szene", "nummer": 1, "id": s[1], "titel": "Im Treppenhaus"}
    assert eins["quelle"]["karte"] == 1
    assert za.pruefe_gold(lage, gold) == []


def test_negativ_nur_nein_ohne_ja_und_nicht_positiv(lage):
    t, s = _themen(lage), _szenen(lage)
    repo.lege_schaerfung_an(lage, 1, [
        {"verdichtung_thema_id": t["Nachbarn"], "szene_id": s[1], "staerke": 3},  # nein -> negativ
        {"verdichtung_thema_id": t["Nachbarn"], "szene_id": s[2], "staerke": 3},  # nein ...
        {"verdichtung_thema_id": t["Nachbarn"], "szene_id": s[2], "staerke": 3},  # ... und ja -> raus
        {"verdichtung_thema_id": t["Arbeit"], "szene_id": s[2], "staerke": 2},    # positiv -> raus
    ])
    ids = [z["id"] for z in repo.schaerfungen_historie(lage, 1)]
    for sid, wert in zip(ids, ["nein", "nein", "ja", "nein"]):
        assert repo.setze_schaerfung_entscheidung(lage, 1, sid, wert)

    gold = za.baue_gold(lage, QUELLE, {"G1": 1})

    negativ = [g for g in gold if g["polaritaet"] == "negativ"]
    assert [(g["verdichtung_thema_id"], g["ziel"]["id"]) for g in negativ] == [(t["Nachbarn"], s[1])]
    assert negativ[0]["id"] == f"G1-n-{ids[0]:04d}"
    assert "wortlaut" not in negativ[0] and "fragmente" not in negativ[0]


def test_trifft_ueber_thema_oder_wortlaut():
    gold = {"thema_ids": [3, 30], "fragmente": ["allein gegangen"]}
    assert za.trifft({"verdichtung_thema_id": 30}, gold)
    assert not za.trifft({"verdichtung_thema_id": 4}, gold)
    assert za.trifft({"text": "ich bin damals allein gegangen"}, gold)


def test_mutation_erfundene_stelle_macht_den_lauf_rot(lage, tmp_path):
    """Spec § 6 / Karte: Gold-Korpus verfaelscht -> Lauf rot."""
    db_pfad = str(tmp_path / "t.db")
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    pfad = tmp_path / "gold.jsonl"
    za.schreibe_gold(gold, pfad)
    assert za.main(["pruefe", "--db", db_pfad, "--gold", str(pfad)]) == 0

    gold[0]["fragmente"] = ["das hat nie jemand gesagt"]
    gold[0]["thema_ids"] = [999]
    gold[0]["verdichtung_thema_id"] = 999
    za.schreibe_gold(gold, pfad)

    assert za.main(["pruefe", "--db", db_pfad, "--gold", str(pfad)]) == 1
    fehler = za.pruefe_gold(lage, za.lade_gold(pfad))
    assert any(f.startswith("G1-1:") and "Transkript" in f for f in fehler)
    assert any(f.startswith("G1-1:") and "999" in f for f in fehler)


def test_mutation_ein_wort_geaendert_ist_rot(lage):
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    gold[0]["fragmente"][1] = "keiner hat gelacht"
    assert za.pruefe_gold(lage, gold) != []


def test_mutation_falsche_szene_ist_rot(lage):
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    gold[0]["ziel"]["nummer"] = 7
    assert any("Szene" in f for f in za.pruefe_gold(lage, gold))
