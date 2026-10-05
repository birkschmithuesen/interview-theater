"""Karte t_9258d2e9, Aufgabe 3: alles Reine am bezahlten Rauchtest -- ohne Netz."""

import json
import pathlib
import types

import pytest

from interview_theater import begriffsboard, einstellungen
from scripts import rauchtest_begriffsboard_resonanz as rt

EN_PROMPT = (pathlib.Path(__file__).resolve().parent.parent
             / "interview_theater/sprachen/en/prompts/begriffsboard.md").read_text(encoding="utf-8")


def _e(begriff, zustimmung=0, nennungen=1, status="kandidat"):
    return {"begriff": begriff, "nennungen": nennungen, "zustimmung": zustimmung,
            "begruendung": "", "zitat": "", "doppelbedeutung": "", "status": status}


def _zeile(fall, arm, antwort, modell="m", fehler=None, **mehr):
    basis = {"fall": fall, "arm": arm, "modell": modell, "antwort": antwort, "fehler": fehler,
             "system_zeichen": 3000, "nutzer_zeichen": 1000, "eingabe_token": 1000,
             "ausgabe_token": 200, "dauer_ms": 1500, "kosten_chf": 0.001}
    basis.update(mehr)
    return basis


def test_sieben_faelle_und_ihre_arme():
    assert list(rt.FAELLE) == ["a_rezenz", "b_konsens", "c_abgelehnt", "d_kontrolle",
                               "e_verhoerer", "f_kontrolle_mehrheit", "g_zwei_begriffe"]
    assert all("board" in f["arme"] for f in rt.FAELLE.values())


def test_fall_a_ist_der_bestehende_rezenzfall():
    from scripts.rauchtest_begriffsboard import FAELLE as ALT
    assert rt.transkript("a_rezenz") == ALT["rezenz_statt_haeufigkeit"]["transkript"]


@pytest.mark.parametrize("arm, anzahl", [("board", 35), ("prompt_nur", 15),
                                         ("analyse", 30), ("verhoerer", 15)])
def test_geplante_aufrufe_je_arm(arm, anzahl):
    assert len(rt.auftraege([arm], set(), 5)) == anzahl


def test_unbekannter_arm():
    with pytest.raises(SystemExit):
        rt.auftraege(["quatsch"], set(), 5)


def test_trocken_ruft_nichts(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(einstellungen, "laden", lambda: (_ for _ in ()).throw(AssertionError("Netz!")))
    roh = tmp_path / "roh.jsonl"
    assert rt.main(["--arme", "board,prompt_nur,analyse,verhoerer", "--modell", "gespraech",
                    "--roh", str(roh), "--trocken"]) == 0
    assert "Geplant: 95 bezahlte Aufrufe" in capsys.readouterr().out
    assert not roh.exists()


def test_deckel_bricht_vor_dem_ersten_aufruf_ab(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(einstellungen, "laden", lambda: (_ for _ in ()).throw(AssertionError("Netz!")))
    roh = tmp_path / "roh.jsonl"
    roh.write_text("{}\n" * 170, encoding="utf-8")
    assert rt.main(["--arme", "board", "--modell", "gespraech", "--roh", str(roh)]) == 3
    assert "ABBRUCH" in capsys.readouterr().out


def test_prompt_nur_ersetzt_nur_die_mehrheitsregel():
    variante = rt.prompt_nur(EN_PROMPT)
    assert "Decide by majority" not in variante
    assert rt.VARIANTE_SINN_ZUERST in variante
    assert variante.startswith(EN_PROMPT[:EN_PROMPT.index("Decide by majority")])
    assert variante.endswith(EN_PROMPT[EN_PROMPT.index("Not like this:"):])


def test_prompt_nur_meldet_einen_geaenderten_prompt():
    with pytest.raises(ValueError):
        rt.prompt_nur("You keep the term board.")


def test_eingabe_board_ist_der_produktive_nutzertext():
    system, nutzer, schema, art = rt.eingabe("board", "b_konsens", EN_PROMPT)
    assert system == EN_PROMPT and schema is begriffsboard.SCHEMA
    assert nutzer == begriffsboard._nutzertext(rt.transkript("b_konsens"), [])
    assert art == "rauchtest_resonanz_board"


@pytest.mark.parametrize("reihe, erwartet", [(["ocean", "garden"], True), (["garden", "ocean"], False),
                                             (["Ozean", "Garten"], True), (["ocean"], False)])
def test_pruefe_reihe_rezenz(reihe, erwartet):
    assert rt.pruefe_reihe("a_rezenz", [_e(b) for b in reihe]) is erwartet


@pytest.mark.parametrize("reihe, erwartet", [(["station", "garden"], True), (["garden", "station"], False),
                                             (["station"], True)])
def test_pruefe_reihe_abgelehnt(reihe, erwartet):
    assert rt.pruefe_reihe("c_abgelehnt", [_e(b) for b in reihe]) is erwartet


@pytest.mark.parametrize("fall, begriffe, erwartet", [
    ("e_verhoerer", ["weather", "rain"], True),
    ("e_verhoerer", ["Wetter"], True),
    ("e_verhoerer", ["whether", "weather"], False),
    ("e_verhoerer", ["whether"], False),
    ("f_kontrolle_mehrheit", ["flower", "flour"], True),
    ("f_kontrolle_mehrheit", ["flour"], False),
    ("g_zwei_begriffe", ["knight", "night"], True),
    ("g_zwei_begriffe", ["Ritter", "Nacht"], True),
    ("g_zwei_begriffe", ["knight"], False),
    ("g_zwei_begriffe", ["knight at night"], False),
])
def test_pruefe_board_verhoerer(fall, begriffe, erwartet):
    assert rt.pruefe_board_verhoerer(fall, [_e(b) for b in begriffe]) is erwartet


@pytest.mark.parametrize("fall, paare, erwartet", [
    ("e_verhoerer", [("whether", "weather")], True),
    ("e_verhoerer", [("whether", "Wetter")], True),
    ("e_verhoerer", [], False),
    ("e_verhoerer", [("whether", "weather"), ("weather", "whether")], False),
    ("f_kontrolle_mehrheit", [], True),
    ("f_kontrolle_mehrheit", [("flour", "flower")], True),
    ("f_kontrolle_mehrheit", [("flower", "flour")], False),
    ("g_zwei_begriffe", [], True),
    ("g_zwei_begriffe", [("night", "knight")], False),
    ("g_zwei_begriffe", [("knight", "night")], False),
])
def test_pruefe_verhoerer(fall, paare, erwartet):
    v = [{"lesart_falsch": f, "lesart_richtig": r, "begruendung_kurz": ""} for f, r in paare]
    assert rt.pruefe_verhoerer(fall, v) is erwartet


def test_pruefe_analyse_rangfaelle():
    assert rt.pruefe_analyse("b_konsens", {"wunsch": {"lighthouse": 2, "motorbike": 1}, "verhoerer": []}) is True
    assert rt.pruefe_analyse("b_konsens", {"wunsch": {"lighthouse": 1, "motorbike": 1}, "verhoerer": []}) is False
    assert rt.pruefe_analyse("c_abgelehnt", {"wunsch": {"garden": -1, "station": 1}, "verhoerer": []}) is True
    assert rt.pruefe_analyse("c_abgelehnt", {"wunsch": {"station": 1}, "verhoerer": []}) is False


def test_bewerte_board_ohne_resonanzmodul():
    antwort = {"board": [_e("motorbike", 1, 6), _e("lighthouse", 2, 5)]}
    assert rt.bewerte(_zeile("b_konsens", "board", antwort)) == {"A": True, "B": None}


def test_bewerte_fehler_ist_durchgefallen():
    assert rt.bewerte(_zeile("b_konsens", "board", None, fehler="LLMFehler: x")) == {"A": False, "B": None}
    assert rt.bewerte(_zeile("e_verhoerer", "analyse", None, fehler="x")) == {"C": False}


def test_bewerte_kontrolle_d_ohne_aussage_fuer_a():
    antwort = {"board": [_e("river", 1, 3), _e("bridge", 1, 3)]}
    assert rt.bewerte(_zeile("d_kontrolle", "board", antwort))["A"] is None


def test_bewerte_b_mit_stub_modul():
    stub = types.SimpleNamespace(
        trage_ein=lambda eintraege, transkript, *, code=None: None,
        resonanz_je_begriff=lambda begriffe, transkript, *, code=None: {b.casefold(): 0 for b in begriffe},
    )
    antwort = {"board": [_e("river", 1, 3), _e("bridge", 1, 3)]}
    assert rt.bewerte(_zeile("d_kontrolle", "board", antwort), stub) == {"A": None, "B": True}
    assert rt.bewerte(_zeile("e_verhoerer", "board", {"board": [_e("weather")]}), stub) == {"A": True, "B": None}


def test_bewerte_analyse_validiert_gegen_die_feste_boardliste():
    antwort = {"wunsch": [], "verhoerer": [
        {"lesart_falsch": "whether", "lesart_richtig": "weather", "begruendung_kurz": "rain"}]}
    assert rt.bewerte(_zeile("e_verhoerer", "analyse", antwort)) == {"C": True}
    assert rt.bewerte(_zeile("e_verhoerer", "verhoerer", {"verhoerer": []})) == {"E": False}
    assert rt.bewerte(_zeile("e_verhoerer", "prompt_nur", {"board": [_e("weather")]})) == {"D": True}


def _gatezeilen(ok_b, ok_c, ok_e=5):
    zeilen = []
    for fall, ok in (("b_konsens", ok_b), ("c_abgelehnt", ok_c)):
        gut = {"board": [_e("lighthouse", 2), _e("motorbike", 1)]} if fall == "b_konsens" \
            else {"board": [_e("station", 2), _e("garden", -1)]}
        schlecht = {"board": [_e("motorbike", 2), _e("lighthouse", 1)]} if fall == "b_konsens" \
            else {"board": [_e("garden", 2), _e("station", 1)]}
        zeilen += [_zeile(fall, "board", gut if i < ok else schlecht) for i in range(5)]
    zeilen += [_zeile("e_verhoerer", "board", {"board": [_e("weather" if i < ok_e else "whether")]})
               for i in range(5)]
    return zeilen


def test_gate_ranking_widerlegt_bei_vier_von_fuenf():
    t = rt.tabelle(_gatezeilen(4, 5))
    assert rt.gate_ranking(t, "m") == rt.TEXT_PRAEMISSE_WIDERLEGT


def test_gate_ranking_bestaetigt_bei_drei_von_fuenf():
    t = rt.tabelle(_gatezeilen(5, 3))
    assert rt.gate_ranking(t, "m") == rt.TEXT_PRAEMISSE_BESTAETIGT


def test_gate_verhoerer():
    assert rt.gate_verhoerer(rt.tabelle(_gatezeilen(5, 5, 4)), "m") == rt.TEXT_VERHOERER_REICHT
    assert rt.gate_verhoerer(rt.tabelle(_gatezeilen(5, 5, 2)), "m") == rt.TEXT_VERHOERER_SCHEITERT


def test_hochrechnung_45_minuten():
    h = rt.hochrechnung(system_zeichen=3000, token_je_zeichen=0.25, ausgabe_token=500, preis=(0.60, 3.00))
    assert h["aufrufe"] == 30
    assert h["eingabe_token"] in (158512, 158513)
    assert h["ausgabe_token"] == 15000
    assert h["chf"] == pytest.approx(0.1401, abs=1e-4)
    assert rt.hochrechnung(system_zeichen=3000, token_je_zeichen=0.25, ausgabe_token=500,
                           preis=None)["chf"] is None


def test_bericht_traegt_tabellen_gates_und_keine_transkripte():
    text = rt.bericht(_gatezeilen(5, 5))
    for kopf in ("## Trefferquote", "## Messwerte", "## Hochrechnung", "## Gates"):
        assert kopf in text
    assert rt.TEXT_PRAEMISSE_WIDERLEGT in text
    for fall in rt.FAELLE:
        assert rt.transkript(fall)[:40] not in text


def test_auswerten_ohne_aufruf(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(einstellungen, "laden", lambda: (_ for _ in ()).throw(AssertionError("Netz!")))
    roh = tmp_path / "roh.jsonl"
    roh.write_text("".join(json.dumps(z) + "\n" for z in _gatezeilen(5, 5)), encoding="utf-8")
    ziel = tmp_path / "tabellen.md"
    assert rt.main(["--auswerten", "--roh", str(roh), "--bericht", str(ziel)]) == 0
    assert "## Gates" in ziel.read_text(encoding="utf-8")
