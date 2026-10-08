"""``scripts/bedarf_seed.py`` -- die Bedarfsliste je Gruppe aus einer
JSON-Datei einspielen. Idempotent: ein erneuter Lauf ersetzt nur
UNERLEDIGTE Punkte einer Gruppe, erledigte bleiben stehen (Birk 08.10.2026
~13:45). Ohne ``--ja`` nur ein Bericht, keine Schreibwirkung."""

import json

import pytest

from interview_theater import db, repo
from scripts import bedarf_seed

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    pfad = str(tmp_path / "t.db")
    c = db.verbinde(pfad)
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    c.commit()
    return pfad, c


def _schreibe_json(tmp_path, inhalt) -> str:
    pfad = tmp_path / "seed.json"
    pfad.write_text(json.dumps(inhalt), encoding="utf-8")
    return str(pfad)


def test_main_ohne_ja_schreibt_nichts(conn, tmp_path, capsys):
    pfad, c = conn
    json_pfad = _schreibe_json(tmp_path, {
        str(CHAT): {"sektionen": [{"name": "Props", "punkte": ["Chair", "Table"]}]},
    })

    assert bedarf_seed.main(["--db", pfad, "--json", json_pfad]) == 0

    assert repo.bedarf(c, CHAT) == []
    ausgabe = capsys.readouterr().out
    assert "--ja" in ausgabe


def test_main_mit_ja_legt_punkte_an(conn, tmp_path):
    pfad, c = conn
    json_pfad = _schreibe_json(tmp_path, {
        str(CHAT): {"sektionen": [
            {"name": "Props", "punkte": ["Chair", "Table"]},
            {"name": "Tech", "punkte": ["Mic"]},
        ]},
    })

    assert bedarf_seed.main(["--db", pfad, "--json", json_pfad, "--ja"]) == 0

    punkte = repo.bedarf(c, CHAT)
    assert [p["text"] for p in punkte] == ["Chair", "Table", "Mic"]
    assert [p["sektion"] for p in punkte] == ["Props", "Props", "Tech"]


def test_main_mit_ja_erhaelt_erledigte_punkte(conn, tmp_path):
    pfad, c = conn
    repo.ersetze_unerledigte_bedarf_punkte(c, CHAT, [("Props", ["Chair"])])
    erster = repo.bedarf(c, CHAT)[0]
    repo.setze_bedarf_erledigt(c, CHAT, erster["id"], True)
    json_pfad = _schreibe_json(tmp_path, {
        str(CHAT): {"sektionen": [{"name": "Props", "punkte": ["Table"]}]},
    })

    assert bedarf_seed.main(["--db", pfad, "--json", json_pfad, "--ja"]) == 0

    punkte = repo.bedarf(c, CHAT)
    texte = {p["text"]: p["erledigt_am"] is not None for p in punkte}
    assert texte == {"Chair": True, "Table": False}


def test_main_ist_idempotent_fuer_unveraenderte_sektionen(conn, tmp_path):
    pfad, c = conn
    json_pfad = _schreibe_json(tmp_path, {
        str(CHAT): {"sektionen": [{"name": "Props", "punkte": ["Chair"]}]},
    })

    bedarf_seed.main(["--db", pfad, "--json", json_pfad, "--ja"])
    bedarf_seed.main(["--db", pfad, "--json", json_pfad, "--ja"])

    punkte = repo.bedarf(c, CHAT)
    assert [p["text"] for p in punkte] == ["Chair"]


def test_main_mehrere_gruppen_aus_einer_datei(tmp_path):
    pfad = str(tmp_path / "t.db")
    c = db.verbinde(pfad)
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "A")
    repo.sichere_gruppe(c, 2, "gruppe2", "B")
    c.commit()
    json_pfad = _schreibe_json(tmp_path, {
        "1": {"sektionen": [{"name": "Props", "punkte": ["Chair"]}]},
        "2": {"sektionen": [{"name": "Tech", "punkte": ["Mic"]}]},
    })

    assert bedarf_seed.main(["--db", pfad, "--json", json_pfad, "--ja"]) == 0

    assert [p["text"] for p in repo.bedarf(c, 1)] == ["Chair"]
    assert [p["text"] for p in repo.bedarf(c, 2)] == ["Mic"]
