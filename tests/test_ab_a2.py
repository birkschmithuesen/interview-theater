"""Achse A2 (Messung 2, Karte t_9b2b33cb): Stueckwerkzeuge im Arbeitsstand."""

import json
import subprocess
from pathlib import Path

import pytest

from interview_theater import erkenner, erkenner_werkzeuge as ew, repo, stueck, szene_claude
from interview_theater.szene_claude import Schleifenergebnis
from scripts import ab_pipeline_vs_tools as ab

WURZEL = Path(__file__).resolve().parent.parent
FALL = {"id": "a2x", "arbeitsstand": {}, "nachrichten": [
    {"absender": "Sara", "text": "Szene 2 spielt jetzt im Treppenhaus"}],
    "erwartet": [{"art": "szene_planen", "wert": "Treppenhaus"}]}


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_stand_hat_drei_szenen_figuren_besetzung_frage(conn, sprache):
    ab.lege_szenenstand(conn, 1, sprache)
    szenen = repo.hole_szenen(conn, 1)
    assert [s["nummer"] for s in szenen] == [1, 2, 3]
    assert all(s["ort"] and s["titel"] and s["karte"] for s in szenen)
    assert 2 <= len(repo.figuren(conn, 1)) <= 3
    assert all(repo.besetzung(conn, s["id"]) for s in szenen)
    assert any(repo.offene_fragen(conn, 1, s["id"]) for s in szenen)
    assert repo.hole_arbeitsstand(conn, 1)["rahmen"]


def test_stand_ist_deterministisch_und_je_chat_gleich(conn):
    repo.sichere_gruppe(conn, 2, "ab", "z")
    ab.lege_szenenstand(conn, 1, "de")
    ab.lege_szenenstand(conn, 2, "de")
    form = lambda c: [(s["nummer"], s["titel"], s["ort"]) for s in repo.hole_szenen(conn, c)]  # noqa: E731
    assert form(1) == form(2)


def test_stand_ist_fuer_die_stueckwerkzeuge_tauglich(conn):
    ab.lege_szenenstand(conn, 1, "de")
    assert ew.fuehre_aus(conn, 1, "setze_ort", {"szene": 2, "ort": "Keller"}).ok
    assert ew.fuehre_aus(conn, 1, "karte_aendern", {"szene": 1, "worum": "Neu"}).ok
    assert ew.fuehre_aus(conn, 1, "figur_aus_szene", {"name": "Anna", "szene": 1}).ok
    assert stueck.QUELLE_AGENT


def test_stand_text_zeigt_szenen_orte_figuren_fragen_mit_id(conn):
    ab.lege_szenenstand(conn, 1, "de")
    text = ab.szenenstand_text(conn, 1, "de")
    for s in repo.hole_szenen(conn, 1):
        assert s["ort"] in text and s["titel"] in text
    for f in repo.offene_fragen(conn, 1, None) + [
            q for s in repo.hole_szenen(conn, 1) for q in repo.offene_fragen(conn, 1, s["id"])]:
        assert str(f["id"]) in text and f["text"] in text
    assert "Anna" in text


def test_nutzertext_mit_und_ohne_stand(conn):
    ab.lege_szenenstand(conn, 1, "de")
    ohne = ab.nutzertext_fuer(conn, 1, FALL)
    mit = ab.nutzertext_fuer(conn, 1, FALL, szenen="de")
    assert ab.szenenstand_text(conn, 1, "de") in mit
    assert ab.szenenstand_text(conn, 1, "de") not in ohne
    assert ohne in mit


def test_beide_modi_sehen_denselben_nutzertext(conn, einst, monkeypatch):
    ab.lege_szenenstand(conn, 1, "de")
    gesehen = {}
    monkeypatch.setattr(szene_claude, "schema",
                        lambda c, e, k, ch, system, nutzer, *a, **kw:
                        gesehen.setdefault("json", nutzer) and {"aenderungen": []})
    lauf = Schleifenergebnis((), 1, None, 0, 0, 1, "")

    def wl(c, e, ch, nutzer):
        gesehen["tools"] = nutzer
        return ([], [], lauf, [])
    monkeypatch.setattr(erkenner, "_werkzeuglauf", wl)
    zj = ab.laufe_json(conn, einst, None, 1, FALL, szenen="de")
    zt = ab.laufe_tools(conn, einst, 1, FALL, szenen="de")
    assert gesehen["json"] == gesehen["tools"]
    assert ab.szenenstand_text(conn, 1, "de") in gesehen["json"]
    assert (zj["achse"], zt["achse"]) == ("A2", "A2")


def test_ohne_szenen_bleibt_achse_a(conn, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "schema", lambda *a, **k: {"aenderungen": []})
    assert ab.laufe_json(conn, einst, None, 1, FALL)["achse"] == "A"


def test_erwartete_werkzeuge_werden_gezaehlt_und_sind_kein_still_fp(conn, einst, monkeypatch):
    fall = {**FALL, "id": "a2f", "erwartet": [], "erwartet_werkzeuge": ["frage_stellen"]}
    ausf = [ew.Ausfuehrung("frage_stellen", {"frage": "Wer?"}, True, {"ok": True}, None, None),
            ew.Ausfuehrung("pruefe_szene", {"szene": 1}, True, {"ok": True}, None, None)]
    lauf = Schleifenergebnis((), 1, None, 0, 0, 1, "")
    monkeypatch.setattr(erkenner, "_werkzeuglauf", lambda c, e, ch, n: ([], [], lauf, ausf))
    z = ab.laufe_tools(conn, einst, 1, fall)
    assert (z["werkzeug_erwartet"], z["werkzeug_treffer"]) == (1, 1)
    assert z["ohne_korpusart"] == 1 and z["still_fp"] == 1   # nur pruefe_szene


def test_json_hat_keine_werkzeugtreffer(conn, einst, monkeypatch):
    monkeypatch.setattr(szene_claude, "schema", lambda *a, **k: {"aenderungen": []})
    fall = {**FALL, "erwartet": [], "erwartet_werkzeuge": ["frage_stellen"]}
    z = ab.laufe_json(conn, einst, None, 1, fall)
    assert (z["werkzeug_erwartet"], z["werkzeug_treffer"]) == (1, 0)


def test_cli_optionen():
    a = ab.baue_argumente(["erkenner", "--szenen", "--faelle", "korpus/ab_a2_de.jsonl"])
    assert a.szenen is True and a.faelle == "korpus/ab_a2_de.jsonl"
    b = ab.baue_argumente(["erkenner"])
    assert b.szenen is False and b.faelle is None


# --- synthetische Fallisten -------------------------------------------------

@pytest.mark.parametrize("sprache", ["de", "en"])
def test_synthetische_faelle(sprache):
    pfad = WURZEL / "korpus" / f"ab_a2_{sprache}.jsonl"
    faelle = [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]
    assert len({f["id"] for f in faelle}) == len(faelle)
    for f in faelle:
        assert {"id", "arbeitsstand", "nachrichten", "erwartet"} <= set(f)
        assert all(e["art"] in ew.ART_FUER_WERKZEUG.values() for e in f["erwartet"])
    abgedeckt = set()
    for f in faelle:
        abgedeckt |= set(f.get("erwartet_werkzeuge", []))
    assert abgedeckt == set(stueck.WERKZEUGE)
    for name in stueck.WERKZEUGE:
        assert sum(name in f.get("erwartet_werkzeuge", []) for f in faelle) >= 2, name
    negativ = [f for f in faelle if not f["erwartet"] and not f.get("erwartet_werkzeuge")]
    assert 3 <= len(negativ) <= 5
    # erwartet_werkzeuge und erwartet widersprechen sich nicht: Art-Werkzeuge ->
    # genau die passende Art in erwartet
    for f in faelle:
        arten = {ew.ART_FUER_WERKZEUG[n] for n in f.get("erwartet_werkzeuge", [])
                 if n in ew.ART_FUER_WERKZEUG}
        assert arten <= {e["art"] for e in f["erwartet"]}


def test_synthetische_faelle_sind_nicht_gitignoriert():
    for sprache in ("de", "en"):
        r = subprocess.run(["git", "check-ignore", f"korpus/ab_a2_{sprache}.jsonl"],
                           cwd=WURZEL, capture_output=True)
        assert r.returncode == 1


def test_faellelisten_bringen_bestehende_korpora_nicht_durcheinander():
    for pfad in ("korpus/erkenner.jsonl", "korpus/en/erkenner.jsonl"):
        assert "erwartet_werkzeuge" not in (WURZEL / pfad).read_text(encoding="utf-8")


# --- Bericht ----------------------------------------------------------------

def _zeile(achse, modus, **kw):
    z = {"achse": achse, "modus": modus, "id": "x", "sprache": "de", "aufnahme": False,
         "treffer": 1, "fp": 0, "fn": 0, "absicht_treffer": 1, "absicht_fp": 0, "absicht_fn": 0,
         "still_fp": 0, "ohne_korpusart": 0, "abgelehnt": 0, "abbruch": None, "runden": 1,
         "eingabe_token": 1, "ausgabe_token": 1, "dauer_ms": 10, "fehler": None,
         "modellaufrufe": 1, "kosten_chf": 0.0, "aufrufe": [],
         "werkzeug_erwartet": 0, "werkzeug_treffer": 0}
    z.update(kw)
    return z


def test_bericht_a2_abschnitt_mit_werkzeugverteilung():
    zeilen = [_zeile("A2", "json"),
              _zeile("A2", "tools", werkzeug_erwartet=2, werkzeug_treffer=1,
                     aufrufe=[{"name": "setze_ort", "ok": True}]),
              _zeile("A", "tools", aufrufe=[{"name": "figur_hinzu", "ok": True}])]
    md = ab.baue_bericht(zeilen, {}, [])
    assert "## Achse A2: Stückwerkzeuge im Arbeitsstand" in md
    a2 = md.split("## Achse A2: Stückwerkzeuge im Arbeitsstand")[1].split("\n## ")[0]
    assert "| Achse A2 | setze_ort | 1 | 0 |" in a2 and "| Achse A |" not in a2
    assert "1 / 2" in a2                       # Werkzeugtreffer / erwartet
    assert "Achse A2: 0" not in md


def test_bericht_a2_fehlt_mit_grund():
    md = ab.baue_bericht([_zeile("A", "json")], {}, [], gruende={"A2": "nicht gefahren"})
    assert "Achse A2: 0 — nicht gefahren" in md
    md2 = ab.baue_bericht([_zeile("A", "json")], {}, [])
    assert "Achse A2: 0 — " in md2


def test_bericht_cli_kennt_a2_grund():
    a = ab.baue_argumente(["bericht", "--roh", "x", "--achse-a2-grund", "g"])
    assert a.achse_a2_grund == "g"


# --- Review A2: Gruppen im Bericht, abgenommener Stand ----------------------

def _a2_abschnitt(zeilen):
    md = ab.baue_bericht(zeilen, {}, [])
    return md.split("## Achse A2: Stückwerkzeuge im Arbeitsstand")[1].split("\n## ")[0]


def test_bericht_a2_trennt_json_ausdrueckbar_nur_tools_negativ():
    zeilen = [
        _zeile("A2", "json", id="a", treffer=1, fn=1, fp=0),
        _zeile("A2", "tools", id="a", treffer=2, fn=0, fp=1),
        _zeile("A2", "json", id="b", treffer=0, fn=0, fp=0, werkzeug_erwartet=1),
        _zeile("A2", "tools", id="b", treffer=0, fn=0, fp=0, werkzeug_erwartet=1, werkzeug_treffer=1),
        _zeile("A2", "json", id="c", treffer=0, fn=0, fp=2, still_fp=2),
        _zeile("A2", "tools", id="c", treffer=0, fn=0, fp=0, still_fp=1),
    ]
    a2 = _a2_abschnitt(zeilen)
    assert "| json-ausdrückbar | 1 | Treffer 1 / FP 0 / FN 1 | Treffer 2 / FP 1 / FN 0 |" in a2
    assert "| nur tools | 1 | n/a — json kann diese Absicht nicht ausdrücken | Werkzeug-Treffer 1 / 1 |" in a2
    assert "| Negativ (Fehlalarm) | 1 | FP 2 / still_fp 2 bei 1 Fällen | FP 0 / still_fp 1 bei 1 Fällen |" in a2
    assert "nur ausgeführte (ok) Aufrufe" in a2


def test_stand_hat_abgenommene_karte_und_text_zeigt_sie(conn):
    for sprache, marke in (("de", "Karte abgenommen"), ("en", "Card approved")):
        repo.sichere_gruppe(conn, 5 if sprache == "de" else 6, "ab", "z")
        chat = 5 if sprache == "de" else 6
        ab.lege_szenenstand(conn, chat, sprache)
        text = ab.szenenstand_text(conn, chat, sprache)
        assert text.count(marke) == len(ab.ABGENOMMEN) >= 1
        szene2 = [x for x in repo.hole_szenen(conn, chat) if x["nummer"] == 2][0]
        assert szene2["karte_bestaetigt_am"]
        assert ew.fuehre_aus(conn, chat, "szene_wieder_oeffnen", {"szene": 2}).ok
        assert not repo.hole_szene(conn, szene2["id"])["karte_bestaetigt_am"]
