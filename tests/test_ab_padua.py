"""Achse B (Messung 2): Fixture ist SYNTHETISCH (erfundene Texte, E8)."""

import json

import pytest

from interview_theater import erkenner, szene_claude
from interview_theater.szene_claude import Schleifenergebnis
from scripts import ab_padua

ZEILE = json.dumps({
    "id": "s01-g9-synthetisch", "arbeitsstand": {},
    "nachrichten": [{"absender": "Bot", "text": "Shall we move on?", "ist_bot": 1},
                    {"absender": "Anna", "text": "Yes, let's start an interview.", "ist_bot": 0}],
    "erwartet": [{"art": "interview_starten", "wert": ""}],
    "notiz": "erfunden", "herkunft": {"gruppe": "g9", "post_id": 1},
})
NEGATIV = json.dumps({"id": "s02-g9-negativ", "arbeitsstand": {}, "erwartet": [],
                      "nachrichten": [{"absender": "Anna", "text": "ok"}],
                      "notiz": "", "herkunft": {"gruppe": "g9"}})


@pytest.fixture
def satz(tmp_path, monkeypatch):
    verz = tmp_path / "en"
    verz.mkdir()
    (verz / "padua_testsatz.jsonl").write_text(ZEILE + "\n\n" + NEGATIV + "\n", encoding="utf-8")
    monkeypatch.setenv("IT_PRIVAT_KORPUS", str(tmp_path))


def test_lade_testsatz_nutzt_den_korpusleser(satz):
    faelle = ab_padua.lade_testsatz()
    assert [f["id"] for f in faelle] == ["s01-g9-synthetisch", "s02-g9-negativ"]
    assert faelle[0]["erwartet"][0]["art"] == "interview_starten"
    assert ab_padua.lade_testsatz(nur=["s02-g9-negativ"])[0]["erwartet"] == []


def test_kopie_oeffnet_quelle_nur_lesend(tmp_path, monkeypatch):
    gesehen = []
    monkeypatch.setattr(ab_padua.stueckmodell_kopie, "kopiere",
                        lambda q, z: gesehen.append((q, z)))
    ab_padua.bereite_kopie_vor("betrieb/padua.db", str(tmp_path / "k.db"))
    assert gesehen == [("betrieb/padua.db", str(tmp_path / "k.db"))]


def test_padua_test_db_wird_abgelehnt(tmp_path):
    with pytest.raises(SystemExit):
        ab_padua.bereite_kopie_vor("betrieb/padua-test.db", str(tmp_path / "k.db"))


def test_chat_id_je_fall_und_modus_ist_eindeutig_und_disjunkt_von_achse_a():
    ids = {ab_padua.chat_id_fuer(n, m) for n in range(1, 40) for m in ("json", "tools")}
    assert len(ids) == 78
    assert all(i >= 100000 for i in ids)


def test_lauf_schreibt_zwei_zeilen_je_fall_mit_achse_b(satz, einst, tmp_path, monkeypatch):
    monkeypatch.setattr(szene_claude, "schema", lambda *a, **k: {"aenderungen": [
        {"art": "interview_starten", "wert": ""}]})
    lauf = Schleifenergebnis((), 1, None, 0, 0, 5, "")
    monkeypatch.setattr(erkenner, "_werkzeuglauf", lambda *a, **k: ([], [], lauf, []))
    aus = tmp_path / "B-test.jsonl"
    ab_padua.laufe_testsatz(ab_padua.lade_testsatz(), einst, str(tmp_path / "m.db"), str(aus))
    zeilen = [json.loads(z) for z in aus.read_text(encoding="utf-8").splitlines()]
    assert [(z["achse"], z["modus"], z["id"]) for z in zeilen] == [
        ("B", "json", "s01-g9-synthetisch"), ("B", "tools", "s01-g9-synthetisch"),
        ("B", "json", "s02-g9-negativ"), ("B", "tools", "s02-g9-negativ")]
    assert zeilen[0]["treffer"] == 1 and zeilen[3]["fp"] == 0
    assert zeilen[2]["fp"] == 1          # json lieferte etwas, erwartet war nichts


def test_standardausgabe_liegt_im_gitignorierten_berichtsverzeichnis():
    assert ab_padua.standard_ausgabe().parts[:3] == ("korpus", "berichte", "ab")
    assert ab_padua.standard_ausgabe().name.startswith("B-")


def test_main_bricht_bei_falscher_sprache_ab(monkeypatch):
    from interview_theater import sprache
    monkeypatch.setattr(sprache, "code", lambda: "de")
    with pytest.raises(SystemExit) as ex:
        ab_padua.main([])
    assert "sprache.code()" in str(ex.value)
