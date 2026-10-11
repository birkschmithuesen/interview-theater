"""Achse C (Messung 2, t_9b2b33cb): Zitatsuche Pipeline gegen Agent.

Alles synthetisch (erfundene Saetze, E8), kein Netz, kein Modell. Die
Recall-Definition ist die von ``scripts.zitatauswahl`` (Recall@10 je Ziel
ueber ``verdichtung_thema_id``-Ranglisten) und wird hier nur wiederverwendet.
"""

import ast
import dataclasses
import json
import pathlib

import pytest

from interview_theater import repo
from scripts import ab_zitate as az
from scripts import zitatauswahl as za

ZITAT_A = "Am Bahnhof hat meine Mutter geweint und wir sind nie zurueckgegangen."
ZITAT_B = "Am Samstag faehrt keiner, da steht die Stadt still und alle warten."
TRANSKRIPT_A = "Wo warst du? " + ZITAT_A + " Danach war Ruhe im Haus."
TRANSKRIPT_B = "Und am Wochenende? " + ZITAT_B


def _interview(conn, transkript, thema, zitat, name):
    kopf = repo.lege_interview_an(conn, 1)
    repo.setze_aufnahme_name(conn, kopf, name)
    repo.setze_transkript(conn, kopf, transkript)
    repo.setze_status(conn, kopf, "fertig")
    repo.setze_interview_beendet(conn, kopf)
    repo.speichere_verdichtung(conn, 1, kopf, "Eine Zusammenfassung.",
                               [{"thema": thema, "beleg_zitat": zitat, "zitat_geprueft": 1}])
    return kopf


@pytest.fixture
def lage(conn):
    a = _interview(conn, TRANSKRIPT_A, "Abschied", ZITAT_A, "A")
    b = _interview(conn, TRANSKRIPT_B, "Stadt", ZITAT_B, "B")
    szene = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene, "titel", "Abschied am Gleis")
    conn.commit()
    themen = {t["thema"]: t["id"] for t in repo.gepruefte_themen(conn, 1)}
    return {"a": a, "b": b, "szene": szene, "themen": themen}


def _ziel(lage):
    return {"art": "szene", "id": lage["szene"], "nummer": 1, "titel": "Abschied am Gleis",
            "was_passiert": "", "form": "", "beschreibung_text": "Szene 1 -- Abschied am Gleis"}


class KlmFolge:
    def __init__(self, antworten):
        self.antworten = list(antworten)
        self.nutzer = []
        self.modelle = []

    def schema(self, chat_id, system, nutzer, schema, art, **kw):
        self.nutzer.append(nutzer)
        self.modelle.append(kw.get("modell"))
        return self.antworten.pop(0)


# --- Suche ------------------------------------------------------------------


def test_suche_findet_fenster_und_sortiert_nach_treffern(conn, lage):
    treffer = az.suche(conn, 1, "Mutter weint Bahnhof")
    assert treffer and treffer[0]["aufnahme_id"] == lage["a"]
    assert "Mutter" in treffer[0]["text"]
    assert len(treffer[0]["text"]) <= az.FENSTER_ZEICHEN + 2


def test_suche_ohne_treffer_ist_leer(conn, lage):
    assert az.suche(conn, 1, "Raumschiff") == []


# --- Agent ------------------------------------------------------------------


def test_agent_sucht_dann_liefert_nur_gepruefte_stellen(conn, einst, lage):
    klm = KlmFolge([
        {"aktion": "suche", "anfrage": "Mutter Bahnhof", "stellen": []},
        {"aktion": "fertig", "anfrage": "", "stellen": [
            {"aufnahme_id": lage["a"], "zitat": "meine Mutter geweint"},
            {"aufnahme_id": lage["a"], "zitat": "erfunden"}]},
    ])
    stellen, info = az.agent_top10(klm, conn, einst, 1, _ziel(lage))
    assert [s["text"] for s in stellen] == ["meine Mutter geweint"]
    assert info["verworfen_zitat"] == 1 and info["runden"] == 2
    assert "Mutter" in klm.nutzer[1]
    assert klm.modelle == ["kimi", "kimi"]          # e.llm_modell, nie ein Claude-Modell


def test_agent_stelle_wird_auf_die_thema_id_abgebildet(conn, einst, lage):
    klm = KlmFolge([{"aktion": "fertig", "anfrage": "", "stellen": [
        {"aufnahme_id": lage["a"], "zitat": "Am Bahnhof hat meine Mutter geweint"}]}])
    stellen, _ = az.agent_top10(klm, conn, einst, 1, _ziel(lage))
    assert stellen[0]["verdichtung_thema_id"] == lage["themen"]["Abschied"]


def test_agent_rundendeckel(conn, einst, lage):
    klm = KlmFolge([{"aktion": "suche", "anfrage": "x", "stellen": []}] * 10)
    stellen, info = az.agent_top10(klm, conn, einst, 1, _ziel(lage))
    assert stellen == [] and info["abbruch"] == "runden" and info["runden"] == az.MAX_RUNDEN


def test_agent_zitatsuche_geht_nie_ueber_den_proxy():
    quelle = pathlib.Path(az.__file__).read_text(encoding="utf-8")
    importe = {a.name for n in ast.walk(ast.parse(quelle))
               if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    assert "szene_claude" not in importe


# --- Pipeline ---------------------------------------------------------------


def test_pipeline_kimi_liefert_staerke_sortierte_kandidaten(conn, einst, lage):
    # Nummer 2 (Stadt) staerker als 1 (Abschied); 9 gibt es nicht.
    klm = KlmFolge([{"eintrag_nummern": [1, 2, 9], "staerke": [2, 3, 3],
                     "begruendungen": ["a", "b", "c"]}])
    e = dataclasses.replace(einst, szene_anbieter="claude")
    kand = az.pipeline_top10(klm, conn, e, 1, _ziel(lage), ueber_claude=False)
    assert [k["verdichtung_thema_id"] for k in kand] == [
        lage["themen"]["Stadt"], lage["themen"]["Abschied"]]
    assert kand[0]["text"] == ZITAT_B
    assert klm.modelle == ["kimi"]       # Kontrollzeile: Kimi, nicht das Erkennermodell (gemma)


# --- Recall (Definition aus scripts.zitatauswahl) ---------------------------


def _gold(thema_ids, im_pool=True, ziel_id=5):
    return {"id": "G1-1", "gruppe": "G1", "ziel": {"art": "szene", "id": ziel_id, "nummer": 1},
            "polaritaet": "positiv", "im_pool": im_pool, "thema_ids": thema_ids,
            "verdichtung_thema_id": thema_ids[0], "chat_id": 1}


def test_recall_at_10_zaehlt_nur_die_ersten_zehn_und_dedupliziert():
    kand = [{"verdichtung_thema_id": 1, "staerke": 9}] * 3 + [
        {"verdichtung_thema_id": i, "staerke": 9 - i} for i in range(2, 14)]
    # Dreimal Thema 1 belegt nur EINEN Platz: Thema 10 ist Platz 10, 11 Platz 11.
    assert az.recall_at_10(az.rangliste_von(kand), [_gold([11])]) == 0.0
    assert az.recall_at_10(az.rangliste_von(kand), [_gold([10])]) == 1.0


def test_recall_ohne_gold_im_pool_ist_none():
    assert az.recall_at_10([1], [_gold([1], im_pool=False)]) is None
    assert az.recall_at_10([1], []) is None


def test_ungemappte_kandidaten_zaehlen_nicht_in_der_rangliste():
    kand = [{"verdichtung_thema_id": None, "staerke": 9}, {"verdichtung_thema_id": 4, "staerke": 1}]
    assert az.rangliste_von(kand) == [4]


# --- Lauf, Rohzeile, Datenschutz --------------------------------------------


def test_zeile_traegt_nur_kennungen_und_keinen_wortlaut(conn, einst, lage):
    gold = _gold([lage["themen"]["Abschied"]], ziel_id=lage["szene"])
    klm = KlmFolge([{"aktion": "fertig", "anfrage": "", "stellen": [
        {"aufnahme_id": lage["a"], "zitat": "Am Bahnhof hat meine Mutter geweint"}]}])
    zeile = az.laufe_ziel(klm, conn, einst, gold, "agent_kimi")
    text = json.dumps(zeile, ensure_ascii=False)
    assert "Mutter" not in text and "Bahnhof" not in text
    assert zeile["achse"] == "C" and zeile["variante"] == "agent_kimi"
    assert zeile["recall_at_10"] == 1.0 and zeile["fehler"] is None
    assert zeile["kandidaten"] == [{"aufnahme_id": lage["a"],
                                    "verdichtung_thema_id": lage["themen"]["Abschied"],
                                    "staerke": 10}]
    assert zeile["rangliste"] == [lage["themen"]["Abschied"]]


def test_fehler_im_ziel_bricht_den_lauf_nicht_ab(conn, einst, lage):
    class Kaputt:
        def schema(self, *a, **k):
            raise RuntimeError("netz weg")

    gold = _gold([1], ziel_id=lage["szene"])
    zeile = az.laufe_ziel(Kaputt(), conn, einst, gold, "agent_kimi")
    assert zeile["fehler"] == "RuntimeError" and zeile["kandidaten"] == []


def test_cli_ohne_kosten_flag_bricht_vor_jedem_aufruf_ab(tmp_path, monkeypatch):
    def nie(*a, **k):
        raise AssertionError("Modell/DB angefasst")

    monkeypatch.setattr(az.llm, "LLM", nie)
    monkeypatch.setattr(az, "_verbinde", nie)
    with pytest.raises(SystemExit) as fehler:
        az.main(["--gold", "x.jsonl", "--db", str(tmp_path / "k.db"), "--gruppe", "G1"])
    assert "--kosten-ok" in str(fehler.value)


def test_cli_lehnt_live_db_und_padua_test_ab(tmp_path):
    for name in ("padua-test.db",):
        with pytest.raises(SystemExit):
            az.main(["--gold", "x.jsonl", "--db", str(tmp_path / name), "--kosten-ok"])
    with pytest.raises(SystemExit):
        az.main(["--gold", "x.jsonl", "--db", str(az.za.LIVE_DB), "--ohne-modell"])


def test_rohverzeichnis_ist_gitignoriert():
    import subprocess

    ergebnis = subprocess.run(["git", "check-ignore", "-q", str(az.ROH_VERZ / "C-x.jsonl")],
                              cwd=pathlib.Path(az.__file__).resolve().parent.parent)
    assert ergebnis.returncode == 0


def test_ohne_modell_prueft_gold_und_zeigt_b0(conn, lage, tmp_path, capsys):
    gold = [dict(_gold([lage["themen"]["Abschied"]], ziel_id=lage["szene"]),
                 aufnahme_id=lage["a"], frage="f", quelle={})]
    gold[0]["ziel"]["titel"] = "Abschied am Gleis"
    gold[0]["ziel"]["nummer"] = 1
    pfad = tmp_path / "gold.jsonl"
    za.schreibe_gold(gold, pfad)
    b0 = tmp_path / "B0.jsonl"
    b0.write_text(json.dumps({"variante": "B0", "gruppe": "G1", "ranglisten": {
        f"G1:szene:{lage['szene']}": [lage["themen"]["Abschied"]]}}) + "\n", encoding="utf-8")
    az.zeige_b0(gold, b0)
    assert "G1: Recall@10 1/1" in capsys.readouterr().out


# --- Review Task 8: Rueckfall, Fairness, Fehlertext ---------------------------


def test_opus_rueckfall_auf_kimi_wird_markiert_und_bezahlt_gebucht(conn, einst, lage, monkeypatch):
    gold = _gold([lage["themen"]["Abschied"]], ziel_id=lage["szene"])

    def faellt_zurueck(klm, conn_, e, chat_id, ziel, *, ueber_claude):
        # So bucht llm._anfrage den Kimi-Rueckfall (modus A, mit Kosten).
        repo.merke_aufruf(conn_, chat_id, "schaerfung", "A", 10, 1000, 200, "stop", 5, 1,
                          "kimi", 0.0123)
        return [{"aufnahme_id": lage["a"], "verdichtung_thema_id": lage["themen"]["Abschied"],
                 "staerke": 3, "text": "x"}]

    monkeypatch.setattr(az, "pipeline_top10", faellt_zurueck)
    zeile = az.laufe_ziel(KlmFolge([]), conn, einst, gold, "pipeline_opus")
    assert zeile["fehler"] == "fallback_kimi"
    assert zeile["recall_at_10"] is None
    assert zeile["kosten_chf"] == pytest.approx(0.0123)


def test_opus_ohne_rueckfall_bleibt_gratis_und_gewertet(conn, einst, lage, monkeypatch):
    gold = _gold([lage["themen"]["Abschied"]], ziel_id=lage["szene"])

    def sauber(klm, conn_, e, chat_id, ziel, *, ueber_claude):
        repo.merke_aufruf(conn_, chat_id, "schaerfung", "C", 10, 1000, 200, "stop", 5, 1,
                          "claude", 0.0)
        return [{"aufnahme_id": lage["a"], "verdichtung_thema_id": lage["themen"]["Abschied"],
                 "staerke": 3, "text": "x"}]

    monkeypatch.setattr(az, "pipeline_top10", sauber)
    zeile = az.laufe_ziel(KlmFolge([]), conn, einst, gold, "pipeline_opus")
    assert zeile["fehler"] is None and zeile["recall_at_10"] == 1.0 and zeile["kosten_chf"] == 0.0


def test_agent_sieht_denselben_hintergrund_wie_die_pipeline(conn, einst, lage, monkeypatch):
    monkeypatch.setattr(az.schaerfung, "_hintergrund_zeilen",
                        lambda c, chat: ["HINTERGRUND-MARKE Kernthema Abschied"])
    klm = KlmFolge([{"aktion": "fertig", "anfrage": "", "stellen": []}])
    az.agent_top10(klm, conn, einst, 1, _ziel(lage))
    assert "HINTERGRUND-MARKE" in klm.nutzer[0]


def test_fehlerzeile_traegt_nur_den_typnamen(conn, einst, lage):
    class Kaputt:
        def schema(self, *a, **k):
            raise RuntimeError("Am Bahnhof hat meine Mutter geweint")

    gold = _gold([1], ziel_id=lage["szene"])
    zeile = az.laufe_ziel(Kaputt(), conn, einst, gold, "agent_kimi")
    assert zeile["fehler"] == "RuntimeError"


def test_deckel_erkennung_per_typ(conn, einst, lage):
    from interview_theater import kosten

    class Deckel:
        def schema(self, *a, **k):
            raise kosten.KostendeckelErreicht("voll")

    zeile = az.laufe_ziel(Deckel(), conn, einst, _gold([1], ziel_id=lage["szene"]), "agent_kimi")
    assert az.ist_deckel_fehler(zeile) is True
    assert az.ist_deckel_fehler({"fehler": "RuntimeError"}) is False
    assert az.ist_deckel_fehler({"fehler": None}) is False


def test_gruppe_ohne_treffer_bricht_ab(tmp_path):
    pfad = tmp_path / "gold.jsonl"
    za.schreibe_gold([_gold([1])], pfad)
    with pytest.raises(SystemExit):
        az.main(["--gold", str(pfad), "--db", str(tmp_path / "k.db"), "--gruppe", "ZZ",
                 "--ohne-modell"])
