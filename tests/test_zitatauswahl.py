"""Tests fuer die Messung der Zitatauswahl (Karte t_2349e9a8 / t_2f905d2c,
Neuaufbau unter Datenschutz-Auflage t_4e8a59aa): Gold-Korpus, Recall@10 je
Ziel, Mutationstest.

Kein Netzzugriff, kein Modellaufruf: alles hier laeuft gegen eine frische
Test-DB und frei erfundene Saetze. Die echte Quelldatei mit dem Padua-
Wortlaut liegt privat unter IT_PRIVAT_KORPUS (Vorgabe: betrieb/korpus/,
``scripts.pruefe_prompts.PRIVATE_KORPUS_DATEIEN``-Konvention) und fehlt in
einem frischen Checkout bewusst -- Tests, die sie brauchen wuerden, gibt es
hier nicht; stattdessen deckt eine synthetische TOML-Fixture dieselbe
Lade-/Fehlerlogik ab.
"""

import json

import pytest

from interview_theater import repo, schaerfung
from scripts import zitatauswahl as za

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


# --- schaerfung.werte_aus ---------------------------------------------------


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


def test_werte_aus_an_einer_figur_setzt_figur_id():
    nach_nummer = {1: {"thema_id": 11, "zitat": "eins zwei drei vier"}}
    ziel = {"art": "figur", "id": 9}
    ergebnis = {"eintrag_nummern": [1], "staerke": [3], "begruendungen": ["b"], "zitate": [""]}

    zuordnungen = schaerfung.werte_aus(ergebnis, ziel, nach_nummer)

    assert zuordnungen == [{"verdichtung_thema_id": 11, "staerke": 3, "begruendung": "b", "figur_id": 9}]


# --- Quelle (privat) ---------------------------------------------------------


def test_lade_quelle_meldet_fehlende_datei_klar(tmp_path):
    pfad = tmp_path / "fehlt.toml"
    with pytest.raises(FileNotFoundError, match="zitatauswahl_quelle"):
        za.lade_quelle(pfad)


def test_lade_quelle_liest_karten_und_commit(tmp_path):
    pfad = tmp_path / "quelle.toml"
    pfad.write_text(
        'quelle_commit = "abc1234"\n\n'
        '[[karte]]\n'
        'id = "X1-1"\n'
        'gruppe = "X1"\n'
        'datei = "x.md"\n'
        'karte = 1\n'
        'szene = 1\n'
        'frage = "Frage?"\n'
        'wortlaut = "Ein frei erfundener Testsatz … noch ein Teil."\n'
        'label = "scene 1"\n',
        encoding="utf-8",
    )

    karten = za.lade_quelle(pfad)

    assert karten == [{
        "id": "X1-1", "gruppe": "X1", "datei": "x.md", "karte": 1, "szene": 1,
        "frage": "Frage?", "wortlaut": "Ein frei erfundener Testsatz … noch ein Teil.",
        "label": "scene 1", "quelle_commit": "abc1234",
    }]


# --- Fragmente / Verankerung -------------------------------------------------


QUELLE = [
    {"id": "G1-1", "gruppe": "G1", "datei": "x.md", "karte": 1, "szene": 1,
     "frage": "Wie war die Arbeit?", "label": "scene 1",
     "wortlaut": "Ich habe zwanzig Jahre genaeht … keiner hat gefragt."},
    {"id": "G1-2", "gruppe": "G1", "datei": "x.md", "karte": 2, "szene": 2,
     "frage": "Wochenende?", "label": "scene 2",
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


def test_mutation_erfundene_stelle_macht_pruefe_gold_rot(lage):
    """Karte: Gold-Korpus verfaelscht -> Lauf rot. Lauft auf dem VOLLEN,
    privat gebauten Gold (mit Fragmenten) -- die oeffentliche, auf die
    Platte geschriebene Fassung traegt keine Fragmente mehr (Datenschutz),
    deshalb prueft dieser Test direkt gegen ``baue_gold``."""
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    assert za.pruefe_gold(lage, gold) == []

    mutiert = [dict(gold[0], fragmente=["das hat nie jemand gesagt"],
                     thema_ids=[999], verdichtung_thema_id=999)] + gold[1:]

    fehler = za.pruefe_gold(lage, mutiert)
    assert any(f.startswith("G1-1:") and "Transkript" in f for f in fehler)
    assert any(f.startswith("G1-1:") and "999" in f for f in fehler)


def test_main_pruefe_erkennt_unbekanntes_thema_in_der_oeffentlichen_gold_datei(lage, tmp_path):
    """Die eingecheckte Gold-Datei traegt keine Fragmente mehr, aber
    ``pruefe`` muss trotzdem rot werden, wenn eine Stelle auf ein Thema
    zeigt, das es in der Gruppe nicht gibt."""
    db_pfad = str(tmp_path / "t.db")
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    pfad = tmp_path / "gold.jsonl"
    za.schreibe_gold(gold, pfad)
    assert za.main(["pruefe", "--db", db_pfad, "--gold", str(pfad)]) == 0

    gold[0]["thema_ids"] = [999]
    gold[0]["verdichtung_thema_id"] = 999
    za.schreibe_gold(gold, pfad)

    assert za.main(["pruefe", "--db", db_pfad, "--gold", str(pfad)]) == 1


def test_mutation_ein_wort_geaendert_ist_rot(lage):
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    gold[0]["fragmente"][1] = "keiner hat gelacht"
    assert za.pruefe_gold(lage, gold) != []


def test_mutation_falsche_szene_ist_rot(lage):
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    gold[0]["ziel"]["nummer"] = 7
    assert any("Szene" in f for f in za.pruefe_gold(lage, gold))


def test_schreibe_gold_laesst_wortlaut_und_fragmente_weg(lage, tmp_path):
    """Datenschutz (Birk 11.10.2026): auf der Platte steht kein echter
    Interview-Wortlaut, auch nicht in der eingecheckten Gold-Datei."""
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    pfad = tmp_path / "gold.jsonl"

    za.schreibe_gold(gold, pfad)

    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        eintrag = json.loads(zeile)
        assert "wortlaut" not in eintrag
        assert "fragmente" not in eintrag


# --- Rangliste, Recall, E7 ---------------------------------------------------


def _g(id_, gruppe, ziel_id, themen, polaritaet="positiv", im_pool=True):
    return {"id": id_, "gruppe": gruppe, "chat_id": 1, "polaritaet": polaritaet,
            "im_pool": im_pool, "ziel": {"art": "szene", "id": ziel_id, "nummer": 1},
            "thema_ids": themen,
            "verdichtung_thema_id": themen[0] if themen else None}


def test_rangliste_staerke_dann_reihenfolge_dedupliziert():
    zu = [{"verdichtung_thema_id": 5, "staerke": 2}, {"verdichtung_thema_id": 7, "staerke": 3},
          {"verdichtung_thema_id": 5, "staerke": 3}, {"verdichtung_thema_id": 9, "staerke": 3}]
    assert za.rangliste(zu) == [7, 5, 9]


def test_recall_zaehlt_nur_die_ersten_k_und_nur_im_pool():
    gold = [_g("G1-1", "G1", 2, [1]), _g("G1-2", "G1", 2, [11]),
            _g("G1-3", "G1", 2, [], im_pool=False), _g("G2-1", "G2", 4, [40, 41])]
    ranglisten = {"G1:szene:2": list(range(1, 13)), "G2:szene:4": [41]}

    r = za.recall_at_k(ranglisten, gold, k=10)

    assert r["G1"] == {"treffer": 1, "n": 2, "fehlt": 0}
    assert r["G2"] == {"treffer": 1, "n": 1, "fehlt": 0}
    assert r["gesamt"] == {"treffer": 2, "n": 3, "fehlt": 0}
    assert za.recall_at_k({}, gold)["gesamt"]["fehlt"] == 3


def test_recall_grenzwert_position_10_trifft_position_11_nicht():
    """Luecke der alten Suite (Karte t_4e8a59aa, Sekundaerbefund): ein
    Mutationstest liste[:k] -> liste[:k-1] muss hier auffallen -- ein Thema
    GENAU an Position 10 ist noch ein Treffer, eines GENAU an Position 11
    nicht mehr."""
    treffer_bei_10 = [_g("G1-1", "G1", 2, [10])]
    verfehlt_bei_11 = [_g("G1-1", "G1", 2, [11])]
    rangliste_ = {"G1:szene:2": list(range(1, 12))}  # 1..11, zehn Plaetze zaehlen

    assert za.recall_at_k(rangliste_, treffer_bei_10, k=10)["gesamt"]["treffer"] == 1
    assert za.recall_at_k(rangliste_, verfehlt_bei_11, k=10)["gesamt"]["treffer"] == 0


def test_mutation_verfaelschter_gold_korpus_senkt_recall_sichtbar():
    gold = [_g("G1-1", "G1", 2, [3]), _g("G1-2", "G1", 2, [8])]
    ranglisten = {"G1:szene:2": [3, 8, 1]}
    assert za.recall_at_k(ranglisten, gold)["gesamt"]["treffer"] == 2

    gold[1]["thema_ids"] = [999]

    assert za.recall_at_k(ranglisten, gold)["gesamt"]["treffer"] == 1


def test_negativ_at_k_zaehlt_verworfene_in_den_top_k():
    gold = [_g("G1-1", "G1", 2, [3]), _g("G1-n-0001", "G1", 2, [8], polaritaet="negativ"),
            _g("G1-n-0002", "G1", 5, [9], polaritaet="negativ")]
    assert za.negativ_at_k({"G1:szene:2": [3, 8, 9]}, gold) == {"G1": 1, "gesamt": 1}


def test_pool_recall_zaehlt_positive_im_pool():
    gold = [_g("G1-1", "G1", 2, [1]), _g("G1-2", "G1", 2, [], im_pool=False),
            _g("G1-n-0001", "G1", 2, [8], polaritaet="negativ")]
    assert za.pool_recall(gold)["G1"] == (1, 2)
    assert za.pool_recall(gold)["gesamt"] == (1, 2)


def test_historische_rangliste_nimmt_die_letzte_runde(lage):
    t, s = _themen(lage), _szenen(lage)
    repo.lege_schaerfung_an(lage, 1, [
        {"verdichtung_thema_id": t["Arbeit"], "szene_id": s[1], "staerke": 3}], runde=1)
    repo.lege_schaerfung_an(lage, 1, [
        {"verdichtung_thema_id": t["Stadt"], "szene_id": s[1], "staerke": 2},
        {"verdichtung_thema_id": t["Nachbarn"], "szene_id": s[1], "staerke": 3}], runde=2)
    gold = [_g("G1-1", "G1", s[1], [t["Arbeit"]])]

    assert za.ranglisten_historisch(lage, gold) == {f"G1:szene:{s[1]}": [t["Nachbarn"], t["Stadt"]]}


def _lauf(treffer_je_gruppe):
    recall = {g: {"treffer": t, "n": 5, "fehlt": 0} for g, t in treffer_je_gruppe.items()}
    recall["gesamt"] = {"treffer": sum(treffer_je_gruppe.values()), "n": 15, "fehlt": 0}
    return {"recall": recall, "ranglisten": {}, "maskiert": 0}


def test_e7_verlangt_zwei_stellen_keine_ueberlappung_keine_gruppe_schlechter():
    basis = {1: _lauf({"G1": 1, "G2": 4, "G3": 2}), 2: _lauf({"G1": 2, "G2": 4, "G3": 2})}
    gut = {1: _lauf({"G1": 3, "G2": 4, "G3": 3}), 2: _lauf({"G1": 4, "G2": 4, "G3": 3})}
    knapp = {1: _lauf({"G1": 2, "G2": 4, "G3": 3}), 2: _lauf({"G1": 3, "G2": 4, "G3": 2})}
    gruppe_faellt = {1: _lauf({"G1": 5, "G2": 2, "G3": 3}), 2: _lauf({"G1": 5, "G2": 2, "G3": 3})}

    assert za.entscheide(basis, gut)[0] is True
    assert za.entscheide(basis, knapp)[0] is False
    ok, gruende = za.entscheide(basis, gruppe_faellt)
    assert ok is False and any("G2" in g for g in gruende)
    assert za.entscheide(basis, {})[0] is False
