"""Ein vollstaendiger Durchlauf ohne Netz -- alle neun Schritte, mit Szene.

Der Mini-Lauf in ``test_simulation_lauf.py`` prueft die Verdrahtung bis in
den Bericht. Hier geht es um die drei Schritte, die mehr tun als reden: die
Interviews (Textimport, Verdichtung, "fertig"), die Szene (Reasoning-Aufruf
ueber ``LLM.prosa``) und das Entfernen einer Figur.

Die Attrappe ist ein winziges Modell mit fester Verdrahtung: die Stimme
antwortet auf das Schrittziel, der Erkenner liest ihre Nachricht und leitet
die passende Aenderungsart daraus ab. Nicht klug -- nur klug genug, dass der
echte Code alle seine Wege einmal geht, bevor jemand Geld dafuer ausgibt.
"""

import json

import pytest

from interview_theater import einstellungen, llm
from simulation import bericht, claude, material, skript, stimmen

from scripts import simulation as sim


#: Ziel-Stichwort im Stimmen-Prompt -> was die Stimme daraufhin schreibt.
#: Die Reihenfolge ist die Pruefreihenfolge, das erste Stichwort gewinnt.
STIMME = (
    ("fangt jetzt ein Interview", "wir machen jetzt ein interview"),
    ("ist zu Ende", "so, fertig"),
    ("zweite Frage", "was war nochmal die zweite frage"),
    ("Begriffe gesammelt", "unsere begriffe: Koffer, Bahnhof, Winter"),
    ("Interviewfragen", "ja, die frageliste nehmen wir so"),
    ("Kernthema", "das kernthema ist das Warten zwischen zwei Laendern"),
    ("drei Figuren", "figur Meryem: die Aeltere"),
    ("stimmt ein Name", "die figur Meryem fliegt raus"),
    ("WAS aus dem Material entsteht", "ja, machen wir ein musical daraus"),
    ("wo sie spielt", "am bahnhof, Meryem und Ferzan, sie warten"),
)

#: Was die Stimme geschrieben hat -> was der Erkenner daraus macht.
ERKENNER = (
    ("wir machen jetzt ein interview", "interview_starten", ""),
    ("fertig", "interview_beenden", ""),
    ("unsere begriffe", "begriffe_setzen", "Koffer, Bahnhof, Winter"),
    ("frageliste", "fragen_setzen", "Koffer: Was war drin?"),
    ("kernthema ist", "kernthema_setzen", "Warten zwischen zwei Laendern"),
    ("fliegt raus", "entfernen", "Figur Meryem"),
    ("figur ", "figur_setzen", "Meryem: die Aeltere"),
    ("musical", "format_setzen", "Musical: Dialog, Lied, Rap"),
)


def _stimme(nutzer: str) -> str:
    """Antwortet auf das **Ziel** des Schritts, nicht auf den Chatverlauf.

    Der Verlauf steht im selben Nutzertext und enthaelt die Saetze aller
    vorherigen Schritte -- wer darin nach Stichwoertern sucht, bekommt ab
    Schritt 4 immer die Antwort von Schritt 4."""
    _, _, ziel = nutzer.partition(stimmen._ZIEL_KOPF)
    for stichwort, antwort in STIMME:
        if stichwort in ziel:
            return antwort
    return "ok"


def _neue_nachrichten(nutzer: str) -> str:
    _, _, rest = nutzer.partition("Neue Nachrichten:")
    return rest.lower()


def _erkenner(nutzer: str, figuren: list[str]) -> dict:
    gesagt = _neue_nachrichten(nutzer)
    for stichwort, art, wert in ERKENNER:
        if stichwort not in gesagt:
            continue
        if art == "figur_setzen":
            # Drei Figuren aus einer Nachricht: der Schritt verlangt drei,
            # und ein Erkennerlauf darf bis zu MAX_AENDERUNGEN liefern.
            return {"aenderungen": [
                {"art": "figur_setzen", "wert": f"{name}: eine Frau"}
                for name in figuren
            ]}
        return {"aenderungen": [{"art": art, "wert": wert}]}
    return {"aenderungen": []}


def _verdichter(nutzer: str) -> dict:
    """Nimmt den ersten laengeren Satz des Transkripts als Belegzitat -- so
    besteht er ``zitat.pruefe`` und die Verdichtung wird wirklich
    gespeichert (N2: ohne geprueftes Zitat kein Thema)."""
    saetze = [z.split(": ", 1)[-1].strip() for z in nutzer.splitlines()]
    beleg = next((s for s in saetze if len(s) > 40), "")
    return {
        "zusammenfassung": "Sie erzaehlt vom Ankommen.",
        "kernthemen": [{"thema": "Ankommen", "kurz": "Ankommen",
                        "beleg_zitat": beleg}],
    }


def _richter(nutzer: str) -> dict:
    if "stimmen_unterscheidbar" in nutzer:
        return {"szene_stimmt_zur_planung": 2, "stimmen_unterscheidbar": 2,
                "satz": "Ort und Figuren stimmen."}
    return {
        "geht_auf_gesagtes_ein": 2, "bietet_an_statt_vorzuschreiben": 2,
        "phase_transparent": 1, "korrektur_angenommen": 2,
        "satz": "Der Bot bleibt am Thema.", "zustimmungen": ["S1"],
        "schlechteste_antwort": "", "begruendung": "",
    }


@pytest.fixture
def durchlauf(monkeypatch, tmp_path):
    """Zwei Interviews statt fuenf -- derselbe Weg, ein Drittel der
    Laufzeit."""
    gezogene = material.waehle(ein_set=1, seed=1, anzahl=2)
    figuren = ["Meryem", "Ferzan", "Aynur"]

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
            return _erkenner(nutzer, figuren)
        if art == "journal":
            return {"eintraege": []}
        if art == "verdichter":
            return _verdichter(nutzer)
        return {"antwort": "Erzaehlt mir mehr davon."}

    def falsche_prosa(self, chat_id, system, nutzer, art, max_tokens=None,
                      timeout=None):
        return ("TITEL: Am Bahnhof\nKURZ: Zwei Frauen warten\n\n"
                "MERYEM: Es ist kalt.\nFERZAN: Ja. Sehr.")

    class SimAttrappe:
        """Stimmen und Richter -- der lokale Proxy, ohne Netz."""

        modell = "claude-opus-5"

        def __init__(self):
            self.statistik = claude.Statistik()

        def text(self, system, nutzer, art="sim", max_tokens=None):
            self.statistik.buche(art, 10, 5, True)
            return _stimme(nutzer)

        def json_objekt(self, system, nutzer, art="sim", max_tokens=None):
            self.statistik.buche(art, 10, 5, True)
            return _richter(nutzer)

        def schliesse(self):
            pass

    monkeypatch.setattr(sim.einstellungen, "laden", falsche_einstellungen)
    monkeypatch.setattr(llm.LLM, "schema", falsches_schema)
    monkeypatch.setattr(llm.LLM, "prosa", falsche_prosa)
    monkeypatch.setattr(sim.claude, "Claude", lambda *a, **k: SimAttrappe())
    monkeypatch.setattr(sim.material, "waehle", lambda **k: gezogene)
    monkeypatch.setattr(bericht, "LAEUFE", tmp_path / "laeufe")
    monkeypatch.setattr(bericht, "BERICHTE", tmp_path / "berichte")
    monkeypatch.setattr(bericht, "VERLAUF", tmp_path / "berichte" / "verlauf.jsonl")
    return {"tmp": tmp_path, "gezogene": gezogene}


def _verlauf(durchlauf) -> dict:
    zeilen = (durchlauf["tmp"] / "berichte" / "verlauf.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(zeilen) == 1
    return json.loads(zeilen[0])


def test_alle_neun_schritte_erreichen_ihren_zielzustand(durchlauf):
    assert sim.main(["--set", "1", "--seed", "1"]) == 0
    daten = _verlauf(durchlauf)
    assert daten["schritte_gescheitert"] == []
    assert daten["notausgaenge"] == 0


def test_jedes_interview_ergibt_genau_eine_verdichtung(durchlauf):
    """Auch das, das in zwei Textimporten hereinkommt: ein Interview ist eine
    Einheit (§ 10.6), zwei Koepfe waeren zwei Verdichtungen fuer ein
    Gespraech."""
    sim.main(["--set", "1", "--seed", "1"])
    daten = _verlauf(durchlauf)
    assert daten["verdichtungen"] == len(durchlauf["gezogene"]) == 2
    assert daten["interviews_soll"] == 2


def test_die_sollzitate_tauchen_als_beleg_auf(durchlauf):
    sim.main(["--set", "1", "--seed", "1"])
    daten = _verlauf(durchlauf)
    assert daten["zitate_geprueft"] == daten["themen"] > 0


def test_der_szenentext_landet_in_der_datenbank_und_im_bericht(durchlauf):
    sim.main(["--set", "1", "--seed", "1", "--bericht"])
    text = list((durchlauf["tmp"] / "berichte").glob("*.md"))[0].read_text(
        encoding="utf-8"
    )
    assert "szene_stimmt_zur_planung" in text
    assert "Ort und Figuren stimmen." in text
    daten = _verlauf(durchlauf)
    assert daten["szene"]["stimmen_unterscheidbar"] == 2


def test_ohne_szene_laesst_den_teuren_lauf_weg(durchlauf, monkeypatch):
    def keine_prosa(self, *a, **k):
        raise AssertionError("--ohne-szene darf keinen Reasoning-Lauf ausloesen")

    monkeypatch.setattr(llm.LLM, "prosa", keine_prosa)
    assert sim.main(["--set", "1", "--seed", "1", "--ohne-szene"]) == 0
    daten = _verlauf(durchlauf)
    assert "szene" not in daten["schritte_gescheitert"]
    assert daten["szene"]["stimmen_unterscheidbar"] is None


def test_das_transkript_haelt_jeden_schritt_fest(durchlauf):
    sim.main(["--set", "1", "--seed", "1"])
    text = list((durchlauf["tmp"] / "laeufe").glob("*.md"))[0].read_text(
        encoding="utf-8"
    )
    for schritt in skript.SCHRITTE:
        assert f"## {schritt.titel}" in text
    assert "Transkript von" in text, "der Textimport muss im Protokoll stehen"
    assert "[S1]" in text


def test_ein_verpasstes_fertig_nimmt_den_notausgang(durchlauf, monkeypatch):
    """Hoert der Erkenner das Ende eines Interviews nicht, schliesst der
    Simulator es selbst ab -- und zaehlt es. Ohne diesen Ausgang haette ein
    Lauf mit einem tauben Erkenner ab Schritt 3 nichts mehr zu messen."""
    ohne_ende = tuple(e for e in ERKENNER if e[1] != "interview_beenden")
    monkeypatch.setitem(globals(), "ERKENNER", ohne_ende)
    sim.main(["--set", "1", "--seed", "1", "--ohne-szene"])
    daten = _verlauf(durchlauf)
    assert daten["notausgaenge"] == 2
    assert daten["verdichtungen"] == 2, "das Material darf trotzdem nicht verloren gehen"
