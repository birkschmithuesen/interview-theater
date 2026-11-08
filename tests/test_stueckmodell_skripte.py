"""Messbasis des Stueckmodells (Karte t_fd88600b, Task 0): Kopie read-only,
Ansichten-Fakten je Szene."""

import json
import sqlite3

import pytest

from interview_theater import db, repo, workshop
from scripts import stueckmodell_ansichten, stueckmodell_kopie


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def test_kopie_entsteht_und_quelle_bleibt_unberuehrt(tmp_path):
    quelle = tmp_path / "q.db"
    c = db.verbinde(str(quelle))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "g1", "G")
    c.close()
    vorher = quelle.read_bytes()
    ziel = tmp_path / "k.db"

    stueckmodell_kopie.kopiere(str(quelle), str(ziel))

    assert quelle.read_bytes() == vorher
    k = sqlite3.connect(ziel)
    assert k.execute("SELECT count(*) FROM gruppe").fetchone()[0] == 1


def test_kopie_ueberschreibt_nie(tmp_path):
    quelle = tmp_path / "q.db"
    db.initialisiere(db.verbinde(str(quelle)))
    ziel = tmp_path / "k.db"
    ziel.write_bytes(b"x")
    with pytest.raises(FileExistsError):
        stueckmodell_kopie.kopiere(str(quelle), str(ziel))


def test_fakten_lesen_ort_aus_allen_ansichten(conn, padua):
    from tests.stueck_hilfe import lege_karte_an

    lege_karte_an(conn, ort="Bar")
    f = stueckmodell_ansichten.fakten(conn, 1)

    assert f["1"]["werkbank_ort"] == "Bar"
    assert f["1"]["karte_wo"] == "Bar"
    assert "Bar" in f["1"]["pdf_meta"]


def test_bericht_liest_nur_migrationszeilen(conn):
    from scripts import stueckmodell_migration as m

    repo.merke_stueck_aenderung(conn, 1, "konflikt_ort", {"szene": 1}, "a", "b", "migration")
    repo.merke_stueck_aenderung(conn, 1, "setze_ort", {"szene": 1}, "b", "c", "gruppe")
    b = m.bericht(conn)
    assert b["zaehler"] == {"konflikt_ort": 1}
    assert b["konflikte"][0]["szene"] == 1
    assert "konflikt_ort" in m.als_markdown(b)


def test_struktur_regel_und_zaehlung():
    from scripts import stueckmodell_wiedergabe as w

    audit = [
        {"post_id": 1, "ziel": "Karte", "fehlerklasse": None, "status": "DRIN", "beleg": "x"},
        {"post_id": 2, "ziel": "Script", "fehlerklasse": "Karte nicht nachgezogen", "status": "TEILWEISE", "beleg": ""},
        {"post_id": 3, "ziel": "nur Antwort", "fehlerklasse": None, "status": "DRIN", "beleg": ""},
        {"post_id": 4, "ziel": "Rahmen", "fehlerklasse": None, "status": "DRIN", "beleg": "Robo-Patch"},
    ]
    assert [a["post_id"] for a in w.struktur(audit)] == [1, 2, 4]


def test_vergleich_konsistent_und_vereinheitlicht():
    from scripts import stueckmodell_vergleich as v

    vorher = {"1": {"1": {"karte_wo": "Bar", "werkbank_ort": "Bar", "prompt_wo": "Bar", "pdf_meta": "x · Bar",
                          "karte_wer": "", "pdf_besetzung": "", "werkbank_figuren": [], "fragen": [], "punkte_offen": []},
                    "2": {"karte_wo": "Sala", "werkbank_ort": "room", "prompt_wo": "Sala", "pdf_meta": "Sala",
                          "karte_wer": "", "pdf_besetzung": "", "werkbank_figuren": [], "fragen": [], "punkte_offen": []}}}
    nachher = {"1": {"1": dict(vorher["1"]["1"]),
                     "2": dict(vorher["1"]["2"], werkbank_ort="Sala")}}
    konflikte = {"konflikte": [{"chat_id": 1, "szene": 2, "art": "konflikt_ort"}]}
    r = v.vergleiche(vorher, nachher, konflikte)
    assert (r["konsistent_gleich"], r["vereinheitlicht"], r["fehler"]) == (1, 1, [])


def test_spiele_ausgang_aufruf_erwartung_und_zaehlung(conn, padua):
    from scripts import stueckmodell_wiedergabe as w
    from tests.stueck_hilfe import lege_karte_an

    repo.sichere_gruppe(conn, 1, "padua-gruppe1", "G")
    lege_karte_an(conn, punkte=["Tutti si alzano"])
    audit = [{"post_id": 7, "ziel": "Karte", "status": "DRIN", "beleg": "Robo-Patch"},
             {"post_id": 8, "ziel": "Rahmen", "status": "DRIN", "beleg": ""}]
    plan = [{"post_id": 7, "gruppe": "G1",
             "ausgang": [{"werkzeug": "karte_aendern", "argumente": {"szene": 1, "punkte_weg": ["Tutti si alzano"]}}],
             "aufrufe": [{"werkzeug": "karte_aendern", "argumente": {"szene": 1, "punkte_hinzu": ["Tutti si alzano"]}}],
             "erwartet": [{"ansicht": "karte", "szene": 1, "enthaelt": "tutti si alzano"}]},
            {"post_id": 8, "gruppe": "G1", "nicht_anwendbar": True}]
    r = w.spiele(conn, audit, plan)
    assert (r["struktur"], r["nicht_anwendbar"], r["vorher_drin"], r["vorher_automatisch"],
            r["nachher_korrekt"], r["fehler"]) == (2, [8], 1, 0, 1, [])


def test_spiele_nennt_unerfuellte_erwartung(conn, padua):
    from scripts import stueckmodell_wiedergabe as w
    from tests.stueck_hilfe import lege_karte_an

    repo.sichere_gruppe(conn, 1, "padua-gruppe1", "G")
    lege_karte_an(conn)
    r = w.spiele(conn, [{"post_id": 9, "ziel": "Karte", "status": "TEILWEISE", "beleg": ""}],
                 [{"post_id": 9, "gruppe": "G1", "aufrufe": [],
                   "erwartet": [{"ansicht": "veraltet", "szene": 1}]}])
    assert r["nachher_korrekt"] == 0 and r["fehler"]
