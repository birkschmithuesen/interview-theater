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
    sid = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, sid, "ort", "Bar")
    repo.setze_szenenkarte(conn, sid, json.dumps({
        "typ": "spoken", "modus": "none", "worum": "w", "ort": "Bar",
        "wer": "", "punkte": ["p"], "zitate": [], "fragen": []}))

    f = stueckmodell_ansichten.fakten(conn, 1)

    assert f["1"]["werkbank_ort"] == "Bar"
    assert f["1"]["karte_wo"] == "Bar"
    assert "Bar" in f["1"]["pdf_meta"]
