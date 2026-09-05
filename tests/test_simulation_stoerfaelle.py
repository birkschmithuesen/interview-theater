"""Ausfall, Pause, Parallellauf und Kostenhochrechnung (N5) -- ohne Netz.

Die drei Schalter ``--stoerung``, ``--pause`` und ``--parallel`` erzeugen
Situationen, die im Betrieb nur bei schlechtem Wetter vorkommen: der Anbieter
ist weg, die Gruppe kommt am naechsten Morgen wieder, drei Gruppen arbeiten
gleichzeitig. Was hier geprueft wird, ist, dass die Situationen wirklich
entstehen -- was der Bot dann tut, sagt der Bericht.
"""

import json

import pytest

from interview_theater import einstellungen, llm, repo
from simulation import bericht, claude, kennzahlen, lauf, skript, stoerung

from scripts import simulation as sim


# --- Die Huelle ------------------------------------------------------------


class _Innen:
    def __init__(self):
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, **k):
        self.aufrufe.append(art)
        return {"antwort": "da"}

    def prosa(self, chat_id, system, nutzer, art, **k):
        self.aufrufe.append(art)
        return "Szenentext"


def test_vor_dem_zug_n_geht_alles_durch():
    innen = _Innen()
    huelle = stoerung.StoerungsLLM(innen, "429", ab_zug=3)
    huelle.neuer_zug()
    assert huelle.schema(1, "s", "n", {}, "gespraech") == {"antwort": "da"}
    assert huelle.geworfen == 0


def test_ab_dem_zug_n_wird_dreimal_geworfen():
    innen = _Innen()
    huelle = stoerung.StoerungsLLM(innen, "5xx", ab_zug=2)
    huelle.neuer_zug()
    huelle.schema(1, "s", "n", {}, "gespraech")
    for _ in range(3):
        huelle.neuer_zug()
        with pytest.raises(llm.LLMFehler):
            huelle.schema(1, "s", "n", {}, "gespraech")
    # Der vierte geht wieder durch -- die Erholung ist der eigentliche Befund.
    huelle.neuer_zug()
    assert huelle.schema(1, "s", "n", {}, "gespraech") == {"antwort": "da"}
    assert huelle.geworfen == 3
    assert huelle.zuege_betroffen == [2, 3, 4]


def test_nur_gespraechsaufrufe_werden_gestoert():
    """Ein Erkenner, der ausfaellt, ist ein anderer Befund -- er laeuft
    nachgelagert, niemand wartet darauf."""
    huelle = stoerung.StoerungsLLM(_Innen(), "timeout", ab_zug=1)
    huelle.neuer_zug()
    assert huelle.schema(1, "s", "n", {}, "erkenner") == {"antwort": "da"}
    assert huelle.schema(1, "s", "n", {}, "journal") == {"antwort": "da"}
    assert huelle.geworfen == 0


def test_die_meldung_ist_die_des_echten_klienten():
    """Ein Fehlertext, den es im Betrieb so nie gibt, wuerde eine
    Fehlerbehandlung messen, die nur in dieser Datei existiert."""
    huelle = stoerung.StoerungsLLM(_Innen(), "429", ab_zug=1)
    huelle.neuer_zug()
    with pytest.raises(llm.LLMFehler, match="HTTP 429"):
        huelle.schema(1, "s", "n", {}, "gespraech")


def test_prosa_wird_ebenso_gestoert():
    huelle = stoerung.StoerungsLLM(_Innen(), "5xx", ab_zug=1)
    huelle.neuer_zug()
    assert huelle.prosa(1, "s", "n", "szene") == "Szenentext"


def test_unbekannte_art_ist_ein_programmierfehler():
    with pytest.raises(ValueError):
        stoerung.StoerungsLLM(_Innen(), "kaputt")


# --- Wiederkehr und Hochrechnung ------------------------------------------


def test_die_wiederkehr_wird_an_der_phase_gemessen():
    lage = kennzahlen.wiederkehr(
        ["Bin wieder da. Wir sind bei 4 · Kernthema & Figuren."],
        "4 · Kernthema & Figuren",
    )
    assert lage["wiederkehr_phase_richtig"] is True
    assert lage["wiederkehr_erklaert_befehle"] is False


def test_eine_nochmalige_bedienungserklaerung_faellt_auf():
    """Die Wiederkehr-Zeile soll sagen, wo man steht, und sonst nichts -- wer
    den Interviewmodus zum zweiten Mal erklaert bekommt, liest ihn nicht."""
    lage = kennzahlen.wiederkehr(
        ["Bin wieder da. /hilfe zeigt den Rest."], "4 · Kernthema & Figuren"
    )
    assert lage["wiederkehr_erklaert_befehle"] is True


def test_eine_falsche_phase_faellt_auf():
    lage = kennzahlen.wiederkehr(["Bin wieder da. Wir sind bei 1 · Begriffe."],
                                 "4 · Kernthema & Figuren")
    assert lage["wiederkehr_phase_richtig"] is False


def test_gar_keine_wiederkehr_ist_kein_absturz():
    lage = kennzahlen.wiederkehr([], "1 · Begriffe")
    assert lage["wiederkehr_zeilen"] == []
    assert lage["wiederkehr_phase_richtig"] is False


def test_die_hochrechnung_nennt_padua():
    zeilen = kennzahlen.hochrechnung(0.40)
    namen = [n for n, _ in zeilen]
    assert any("Padua" in n for n in namen)
    assert dict(zeilen)["3 Gruppen x 2 Tage"] == pytest.approx(2.4)
    assert dict(zeilen)["3 Gruppen x 15 Tage (Padua)"] == pytest.approx(18.0)


def test_vorfaelle_werden_je_art_gezaehlt(conn, einst):
    repo.merke_vorfall(conn, 1, "gruppe1", "http_5xx", "erster")
    repo.merke_vorfall(conn, 1, "gruppe1", "http_5xx", "zweiter")
    repo.merke_vorfall(conn, 1, "gruppe1", "kuerzung", "Transkripte entfernt")
    assert kennzahlen.vorfaelle(conn, 1) == {"http_5xx": 2, "kuerzung": 1}


# --- Ein ganzer Lauf mit --stoerung, --pause, --parallel ------------------


@pytest.fixture
def mini(monkeypatch, tmp_path):
    """Zwei Schritte, alles attrappiert -- der Rahmen fuer die drei
    Schalter."""
    def falsche_einstellungen():
        return einstellungen.Einstellungen(
            bot_token="T", bot_name="simulation", db_pfad=str(tmp_path / "x.db"),
            audio_verz=str(tmp_path / "audio"),
            llm_url="https://llm.test/v1/chat/completions", llm_key="K",
            llm_modell="moonshotai/Kimi-K2.6", stt_basis="https://stt.test",
            stt_produkt="P", erkenner_modell="google/gemma-4-31B-it",
        )

    def falsches_schema(self, chat_id, system, nutzer, schema, art,
                        modell=None, temperature=None):
        if art == "erkenner":
            if "Begriffe:" not in nutzer:
                return {"aenderungen": [
                    {"art": "begriffe_setzen", "wert": "Koffer, Bahnhof"}
                ]}
            return {"aenderungen": [
                {"art": "fragen_setzen", "wert": "Koffer: Was war drin?"}
            ]}
        if art == "journal":
            return {"eintraege": []}
        return {"antwort": "Ich habe eure Begriffe."}

    class SimAttrappe:
        modell = "claude-opus-5"

        def __init__(self):
            self.statistik = claude.Statistik()

        def text(self, system, nutzer, art="sim", max_tokens=None):
            self.statistik.buche(art, 10, 5, True)
            return "ja passt, nimm die so"

        def json_objekt(self, system, nutzer, art="sim", max_tokens=None):
            self.statistik.buche(art, 10, 5, True)
            if "form_eingehalten" in nutzer:
                return {"szene_stimmt_zur_planung": 2, "stimmen_unterscheidbar": 2,
                        "form_eingehalten": 2, "satz": "ok"}
            if "information_lag_vor" in nutzer:
                return {"information_lag_vor": 2, "satz": "alles war da"}
            if "fehlt_im_journal" in nutzer:
                return {"wiedergefunden": [], "nicht_wiedergefunden": [],
                        "fehlt_im_journal": [], "satz": "ok"}
            return {"geht_auf_gesagtes_ein": 2, "bietet_an_statt_vorzuschreiben": 2,
                    "phase_transparent": 2, "korrektur_angenommen": 2,
                    "satz": "ok", "zustimmungen": ["S1"],
                    "schlechteste_antwort": "", "begruendung": ""}

        def schliesse(self):
            pass

    monkeypatch.setattr(sim.einstellungen, "laden", falsche_einstellungen)
    monkeypatch.setattr(llm.LLM, "schema", falsches_schema)
    monkeypatch.setattr(sim.claude, "Claude", lambda *a, **k: SimAttrappe())
    monkeypatch.setattr(bericht, "LAEUFE", tmp_path / "laeufe")
    monkeypatch.setattr(bericht, "BERICHTE", tmp_path / "berichte")
    monkeypatch.setattr(bericht, "VERLAUF", tmp_path / "berichte" / "verlauf.jsonl")
    monkeypatch.setattr(
        sim, "_schritte",
        lambda args: (skript.schritt_fuer("begriffe"), skript.schritt_fuer("fragen")),
    )
    monkeypatch.setattr(sim.time, "sleep", lambda s: None)
    return tmp_path


def _zeilen(tmp_path) -> list[dict]:
    text = (tmp_path / "berichte" / "verlauf.jsonl").read_text(encoding="utf-8")
    return [json.loads(z) for z in text.splitlines()]


def test_stoerung_landet_im_bericht_und_der_lauf_geht_weiter(mini):
    assert sim.main(["--set", "1", "--seed", "1", "--ohne-szene",
                     "--stoerung", "5xx", "--stoerung-ab", "1",
                     "--bericht"]) == 0
    daten = _zeilen(mini)[0]
    assert daten["stoerung"] == "5xx"
    assert daten["stoerung_geworfen"] == 3
    text = list((mini / "berichte").glob("*.md"))[0].read_text(encoding="utf-8")
    assert "## Ausfall-Simulation (5xx)" in text
    assert "Danach weitergelaufen" in text


def test_ohne_stoerung_faellt_der_abschnitt_weg(mini):
    sim.main(["--set", "1", "--seed", "1", "--ohne-szene", "--bericht"])
    text = list((mini / "berichte").glob("*.md"))[0].read_text(encoding="utf-8")
    assert "Ausfall-Simulation" not in text
    assert _zeilen(mini)[0]["stoerung"] == ""


def test_pause_datiert_zurueck_und_misst_die_wiederkehr(mini, monkeypatch):
    """Nach Schritt 4 -- hier nach dem zweiten, weil der Mini-Lauf nur zwei
    hat; gemessen wird derselbe Weg."""
    monkeypatch.setattr(lauf, "PAUSE_NACH_SCHRITT", 2)
    assert sim.main(["--set", "1", "--seed", "1", "--ohne-szene", "--pause",
                     "--bericht"]) == 0
    daten = _zeilen(mini)[0]
    assert daten["wiederkehr_zeilen"], "der Bot muss sich zurueckmelden"
    assert daten["wiederkehr_phase_richtig"] is True
    text = list((mini / "berichte").glob("*.md"))[0].read_text(encoding="utf-8")
    assert "## Wiederkehr nach der Nacht" in text


def test_ohne_pause_faellt_der_abschnitt_weg(mini):
    sim.main(["--set", "1", "--seed", "1", "--ohne-szene", "--bericht"])
    text = list((mini / "berichte").glob("*.md"))[0].read_text(encoding="utf-8")
    assert "Wiederkehr nach der Nacht" not in text


def test_parallel_faehrt_zwei_laeufe_mit_verschiedenen_seeds(mini):
    assert sim.main(["--set", "1", "--seed", "5", "--ohne-szene",
                     "--parallel", "2"]) == 0
    zeilen = _zeilen(mini)
    assert len(zeilen) == 2
    assert sorted(z["seed"] for z in zeilen) == [5, 6]
    # Jeder Lauf zaehlt seine eigenen Vorfaelle -- das ist die Messung.
    assert all("vorfaelle" in z for z in zeilen)


def test_die_verlaufszeile_traegt_alle_neuen_felder(mini):
    """Ein Vorher/Nachher je Prompt-Aenderung soll EINE Zeile sein (N5.7)."""
    sim.main(["--set", "1", "--seed", "1", "--ohne-szene"])
    daten = _zeilen(mini)[0]
    for feld in ("latenzen", "optionenlisten", "zitat_erfunden", "hochrechnung",
                 "kontext_bloecke", "kontext_gekuerzt", "journal_je_art",
                 "journal_ausgeloest", "vorfaelle", "stoerung", "chf_je_art",
                 "sim_aufrufe", "bot_rueckfragen"):
        assert feld in daten, feld


def test_der_bericht_rechnet_die_kosten_hoch(mini):
    sim.main(["--set", "1", "--seed", "1", "--ohne-szene", "--bericht"])
    text = list((mini / "berichte").glob("*.md"))[0].read_text(encoding="utf-8")
    assert "## Kosten und Hochrechnung" in text
    assert "Padua" in text
    assert "ein Lauf = ein Workshoptag einer Gruppe" in text


def test_fenster_klein_setzt_das_budget_und_stellt_es_zurueck():
    from interview_theater import kontext

    vorher = kontext.BUDGETS["fenster"]
    with sim.fenster_klein(True):
        assert kontext.BUDGETS["fenster"] == sim.FENSTER_KLEIN
    assert kontext.BUDGETS["fenster"] == vorher

    with sim.fenster_klein(False):
        assert kontext.BUDGETS["fenster"] == vorher
