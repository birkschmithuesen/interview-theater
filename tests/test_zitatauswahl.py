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


# --- Rangliste, Recall, E7 ----------------------------------------------------


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


def test_mutation_verfaelschter_gold_korpus_senkt_recall_sichtbar():
    """Karte: Gold-Korpus verfaelscht -> Lauf rot. Ohne Pruefung faellt der
    berichtete Wert sichtbar (deterministisch, ohne Modell)."""
    gold = [_g("G1-1", "G1", 2, [3]), _g("G1-2", "G1", 2, [8])]
    ranglisten = {"G1:szene:2": [3, 8, 1]}
    assert za.recall_at_k(ranglisten, gold)["gesamt"]["treffer"] == 2

    gold[1]["thema_ids"] = [999]

    assert za.recall_at_k(ranglisten, gold)["gesamt"]["treffer"] == 1


def test_negativ_at_k_zaehlt_verworfene_in_den_top_k():
    gold = [_g("G1-1", "G1", 2, [3]), _g("G1-n-0001", "G1", 2, [8], polaritaet="negativ"),
            _g("G1-n-0002", "G1", 5, [9], polaritaet="negativ")]
    assert za.negativ_at_k({"G1:szene:2": [3, 8, 9]}, gold) == {"G1": 1, "gesamt": 1}


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


def test_roh_zeilen_werden_je_lauf_und_gruppe_zusammengefuehrt(tmp_path):
    pfad = tmp_path / "B1.jsonl"
    za.haenge_an({"variante": "B1", "lauf": 1, "gruppe": "G2", "ranglisten": {"a": [1]},
                  "maskiert": {"a": 0}, "fehler": {}, "dauer_ms": {"a": 5}}, pfad)
    za.haenge_an({"variante": "B1", "lauf": 1, "gruppe": "G2", "ranglisten": {"b": [2]},
                  "maskiert": {"b": 1}, "fehler": {}, "dauer_ms": {"b": 6}}, pfad)

    za.haenge_an({"variante": "B1", "lauf": 1, "gruppe": "G3", "ranglisten": {"c": None},
                  "maskiert": {}, "fehler": {"c": "ClaudeFehler: aus"}, "dauer_ms": {}}, pfad)
    za.haenge_an({"variante": "B1", "lauf": 1, "gruppe": "G3", "ranglisten": {"c": [3]},
                  "maskiert": {"c": 0}, "fehler": {}, "dauer_ms": {"c": 7}}, pfad)

    zeilen = {z["gruppe"]: z for z in za.lade_roh(tmp_path)}

    assert zeilen["G2"]["ranglisten"] == {"a": [1], "b": [2]}
    assert zeilen["G3"]["ranglisten"] == {"c": [3]} and zeilen["G3"]["fehler"] == {}


def test_laeufe_nimmt_nur_vollstaendige_laeufe():
    gold = [_g("G1-1", "G1", 2, [3]), _g("G2-1", "G2", 4, [8])]
    zeilen = [
        {"variante": "B1", "lauf": 1, "gruppe": "G1", "ranglisten": {"G1:szene:2": [3]}, "maskiert": {}, "fehler": {}},
        {"variante": "B1", "lauf": 1, "gruppe": "G2", "ranglisten": {"G2:szene:4": [1]}, "maskiert": {}, "fehler": {}},
        {"variante": "B1", "lauf": 2, "gruppe": "G1", "ranglisten": {"G1:szene:2": [3]}, "maskiert": {}, "fehler": {}},
        {"variante": "B1", "lauf": 3, "gruppe": "G1", "ranglisten": {"G1:szene:2": None}, "maskiert": {}, "fehler": {"G1:szene:2": "x"}},
        {"variante": "B1", "lauf": 3, "gruppe": "G2", "ranglisten": {"G2:szene:4": [8]}, "maskiert": {}, "fehler": {}},
    ]

    l = za.laeufe(zeilen, gold, "B1")

    assert list(l) == [1]
    assert l[1]["recall"]["gesamt"] == {"treffer": 1, "n": 2, "fehlt": 0}


# --- Neu-Lauf -----------------------------------------------------------------


def test_nutzertext_ohne_maske_ist_bitgleich_zum_betrieb(lage):
    eintraege = schaerfung._eintraege(lage, 1)
    for ziel in schaerfung._ziele(lage, 1):
        assert za.nutzertext_maskiert(lage, 1, eintraege, ziel, []) == (
            schaerfung._baue_nutzertext_ziel(lage, 1, eintraege, ziel), 0)


def test_maske_trifft_nur_kopf_und_ziel_nicht_das_material(lage):
    s = _szenen(lage)
    repo.setze_szenenfeld(lage, s[1], "titel", "Ich habe zwanzig Jahre genaeht")
    eintraege = schaerfung._eintraege(lage, 1)
    ziel = next(z for z in schaerfung._ziele(lage, 1) if z["id"] == s[1])

    text, n = za.nutzertext_maskiert(lage, 1, eintraege, ziel, ["ich habe zwanzig Jahre genaeht"])

    kopf, material = text.split(schaerfung.T._MATERIAL_KOPF, 1)
    assert n >= 2  # Szenenliste und Ziel-Zeile
    assert "zwanzig Jahre" not in kopf and "[…]" in kopf
    assert "ich habe zwanzig Jahre genaeht" in material


class _Proxy:
    def __init__(self, antwort=None, fehler=None):
        self.antwort, self.fehler, self.aufrufe = antwort, fehler, []

    def __call__(self, conn, e, klient, chat_id, system, nutzer, schema_, art, timeout,
                 bei_teil=None, teil_feld=None, wartezeiten=None, modell=None):
        self.aufrufe.append({"modell": modell, "art": art, "system": system, "nutzer": nutzer})
        if self.fehler:
            raise self.fehler
        return self.antwort


@pytest.fixture
def ohne_kimi(monkeypatch):
    """Datenschutz/Kosten: der Neu-Lauf darf llm.LLM nie anfassen."""
    class Verboten:
        def __init__(self, *a, **k):
            raise AssertionError("Kimi/gemma im Neu-Lauf")
    monkeypatch.setattr(llm, "LLM", Verboten)


def test_neu_lauf_nur_ueber_den_proxy_mit_opus(lage, tmp_path, monkeypatch, ohne_kimi):
    t, s = _themen(lage), _szenen(lage)
    proxy = _Proxy({"eintrag_nummern": [2, 1], "staerke": [3, 3], "begruendungen": ["x", "y"]})
    monkeypatch.setattr(szene_claude, "schema", proxy)
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})

    zeile = za.neu_lauf(lage, za.einstellungen_messung(str(tmp_path / "t.db")), None,
                        gold, "G1", "SYSTEM")

    assert set(zeile["ranglisten"]) == {f"G1:szene:{s[1]}", f"G1:szene:{s[2]}"}
    assert zeile["ranglisten"][f"G1:szene:{s[1]}"] == [t["Stadt"], t["Arbeit"]]
    assert zeile["fehler"] == {}
    assert {a["modell"] for a in proxy.aufrufe} == {"claude-opus-5"}
    assert all(a["system"] == "SYSTEM" for a in proxy.aufrufe)


def test_neu_lauf_notiert_fehler_statt_rueckfall(lage, tmp_path, monkeypatch, ohne_kimi):
    monkeypatch.setattr(szene_claude, "schema", _Proxy(fehler=szene_claude.ClaudeFehler("aus")))
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})

    zeile = za.neu_lauf(lage, za.einstellungen_messung(str(tmp_path / "t.db")), None,
                        gold, "G1", "SYSTEM")

    assert all(r is None for r in zeile["ranglisten"].values())
    assert all("ClaudeFehler" in f for f in zeile["fehler"].values())


class _Antwort:
    def __init__(self, status=200, daten=None):
        self.status_code, self._daten = status, daten

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                "x", request=httpx.Request("POST", "http://proxy"), response=self)

    def json(self):
        return self._daten


class _Klient:
    """Attrappe NUR fuer die HTTP-Ebene: szene_claude.schema/prosa laufen echt."""
    def __init__(self, antworten):
        self.antworten, self.posts = list(antworten), []

    def post(self, url, headers=None, json=None, timeout=None):
        self.posts.append({"url": url, "json": json})
        a = self.antworten.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


@pytest.fixture
def llm_verboten(monkeypatch):
    """Spec § 6: jede Beruehrung von llm.LLM (Instanz, Methode) macht rot."""
    def verboten(*a, **k):
        raise AssertionError("llm.LLM im Neu-Lauf beruehrt")

    class Verboten:
        def __init__(self, *a, **k):
            verboten()

        def __getattr__(self, name):
            verboten()

    monkeypatch.setattr(llm, "LLM", Verboten)
    monkeypatch.setattr(szene_claude.time, "sleep", lambda s: None)


def _messages_antwort(inhalt: dict):
    return _Antwort(200, {"content": [{"type": "text", "text": json.dumps(inhalt)}],
                          "usage": {"input_tokens": 10, "output_tokens": 5},
                          "stop_reason": "end_turn"})


def test_neu_lauf_echter_claude_pfad_beruehrt_llm_nie(lage, tmp_path, llm_verboten):
    t, s = _themen(lage), _szenen(lage)
    gueltig = {"eintrag_nummern": [2, 1], "staerke": [3, 3], "begruendungen": ["x", "y"]}
    klient = _Klient([_messages_antwort(gueltig), _messages_antwort(gueltig)])
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})

    zeile = za.neu_lauf(lage, za.einstellungen_messung(str(tmp_path / "t.db")), klient,
                        gold, "G1", "SYSTEM")

    assert zeile["fehler"] == {}
    assert zeile["ranglisten"][f"G1:szene:{s[1]}"] == [t["Stadt"], t["Arbeit"]]
    assert len(klient.posts) == 2
    assert {p["json"]["model"] for p in klient.posts} == {"claude-opus-5"}
    assert all(p["url"].startswith("http://127.0.0.1:28764/") for p in klient.posts)


@pytest.mark.parametrize("fehler", [
    _Antwort(500), _Antwort(400),
])
def test_neu_lauf_proxy_fehler_wird_notiert_ohne_kimi(lage, tmp_path, llm_verboten, fehler):
    klient = _Klient([fehler] * 20)
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})

    zeile = za.neu_lauf(lage, za.einstellungen_messung(str(tmp_path / "t.db")), klient,
                        gold, "G1", "SYSTEM")

    assert zeile["ranglisten"] and all(r is None for r in zeile["ranglisten"].values())
    assert all("ClaudeFehler" in f for f in zeile["fehler"].values())
    assert klient.posts  # der Proxy wurde versucht, sonst nichts


def test_neu_lauf_transportfehler_wird_notiert_ohne_kimi(lage, tmp_path, llm_verboten):
    import httpx
    klient = _Klient([httpx.ReadTimeout("t")] * 20)
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})

    zeile = za.neu_lauf(lage, za.einstellungen_messung(str(tmp_path / "t.db")), klient,
                        gold, "G1", "SYSTEM")

    assert all(r is None for r in zeile["ranglisten"].values())
    assert all("ClaudeFehler" in f for f in zeile["fehler"].values())


def test_nur_mit_unbekanntem_schluessel_haengt_nichts_an(lage, tmp_path, monkeypatch, capsys):
    gold = za.baue_gold(lage, QUELLE, {"G1": 1})
    monkeypatch.setenv("IT_WORKSHOP", "x")  # main() setzt es per setdefault: nach dem Test zurueck
    monkeypatch.delenv("IT_WORKSHOP")
    monkeypatch.setattr(za, "_verbinde", lambda pfad: lage)
    monkeypatch.setattr(za, "lade_gold", lambda pfad: gold)
    monkeypatch.setattr(za, "pruefe_gold", lambda conn, g: [])
    aus = tmp_path / "roh.jsonl"

    rc = za.main(["neu", "--db", "x.db", "--variante", "B1", "--lauf", "1", "--gruppe", "G1",
                  "--nur", "G1:szene:99999", "--aus", str(aus)])

    assert rc == 2
    assert "G1:szene:99999" in capsys.readouterr().err
    assert not aus.exists()


def test_skript_importiert_keine_interviewstrecke():
    """Interviews bleiben hart auf Kimi (Karte): das Messskript ruft weder
    Verdichter noch Erkenner noch die Aufnahme-Pipeline noch llm direkt."""
    baum = ast.parse(Path("scripts/zitatauswahl.py").read_text(encoding="utf-8"))
    namen = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom) and knoten.module:
            namen |= {f"{knoten.module}.{a.name}" for a in knoten.names}
        elif isinstance(knoten, ast.Import):
            namen |= {a.name for a in knoten.names}
    verboten = {f"interview_theater.{m}" for m in ("verdichter", "erkenner", "aufnahme", "llm")}
    assert not namen & verboten


# --- Bericht ------------------------------------------------------------------


def test_bericht_traegt_abschnitte_zahlen_und_kommandos(tmp_path):
    gold = [dict(_g("G1-1", "G1", 2, [3]), wortlaut="x", frage="f?"),
            dict(_g("G1-2", "G1", 2, [8]), wortlaut="y", frage="g?")]
    zeilen = [{"variante": "B0", "lauf": 1, "gruppe": "G1", "ranglisten": {"G1:szene:2": [3, 1]},
               "maskiert": {}, "fehler": {}, "dauer_ms": {}}]
    zeilen += [{"variante": "B1", "lauf": i, "gruppe": "G1", "ranglisten": {"G1:szene:2": [3]},
                "maskiert": {"G1:szene:2": 1}, "fehler": {}, "dauer_ms": {}} for i in (1, 2, 3)]
    pfad = tmp_path / "bericht.md"

    text = za.schreibe_bericht(gold, zeilen, pfad)

    assert pfad.read_text(encoding="utf-8") == text
    for kopf in ("## Kurzfassung", "## Gold-Korpus", "### Format", "### Herkunft und Diskrepanzen",
                 "## Ergebnisse je Gruppe", "## Rang jeder Gold-Stelle", "## Entscheidungen (E7)",
                 "## Kommandos zum Nachrechnen", "## Grenzen"):
        assert kopf in text
    assert "| G1 | B0 | 1/2 |" in text
    assert "python -m scripts.zitatauswahl historisch" in text
    assert "korpus/zitatauswahl_gold.jsonl" in text
    assert "I-a: nicht gemessen" in text
