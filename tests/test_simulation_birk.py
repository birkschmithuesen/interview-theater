"""``--set birk``: Frontmatter, drei Teile, Skript-Ziele, Referenzzahlen.

**Ohne Netz und ohne das echte Material.** Die meisten Tests hier laufen
gegen ein nachgebautes Verzeichnis in ``tmp_path`` (``IT_SIM_BIRK``): das
echte Material liegt ausserhalb des Repositories, und eine Testsuite, die
davon abhaengt, waere auf jedem anderen Rechner rot. Genau zwei Tests fassen
das echte Material an und ueberspringen sich, wenn es fehlt -- sie sind die
Gegenprobe, dass die Konstanten hier noch zu der Datei passen, die der
Betreiber hat.
"""

import json

import pytest

from simulation import birk, skript, stimmen

# --- ein nachgebautes Material -------------------------------------------

#: Ein Transkript in drei Absaetzen, das die drei Soll-Zitate woertlich
#: enthaelt -- sonst schlaegt ``birk.lade`` mit Absicht fehl.
_TRANSKRIPT = "\n\n".join([
    "So, also die erste Frage. Hm, okay. "
    + birk.ZITATE_SOLL[0]
    + " Und die habe ich vor drei Monaten gemacht.",
    "Die zweite Frage bezieht sich auf deine erste Liebe. Puh. "
    + birk.ZITATE_SOLL[1]
    + " Ja, doch, wir haben zusammen gepogt.",
    "Und die letzte Frage, Hawaii. " + birk.ZITATE_SOLL[2] + " Kommt einfach so.",
])

_KOPF = """---
name: Birk-Testinterview 04.09.2026
quelle: theatersoap1_bot
fragen:
  - "Kueche: Erzaehl mir von einem Gericht, das nur du so machst."
  - "Erste Liebe: Erzaehl mir von einem Moment mit deiner ersten Liebe."
  - "Fernweh nach Hawaii: Was ist das erste Bild, das hochkommt?"
begriffe: "Kueche, erste Liebe, Fernweh nach Hawaii"
---
"""

_CHAT = {
    "nachrichten": [
        {"message_id": 1, "absender": "Birk", "ist_bot": 0, "typ": "text",
         "text": "Hier kommen die drei Begriffe."},
        {"message_id": 2, "absender": "bot", "ist_bot": 1, "typ": "text",
         "text": "Hab die drei Begriffe. Noch was, oder seid ihr durch?"},
        {"message_id": 3, "absender": "bot", "ist_bot": 1, "typ": "text",
         "text": "Notiert:\nBegriffe: Kueche, erste Liebe\nFalls nicht, sagt es."},
        {"message_id": 4, "absender": "Birk", "ist_bot": 0, "typ": "text",
         "text": "Ja passt. Mach vorschlag fuer die Fragen, ich habe keine Ideen."},
        {"message_id": 5, "absender": "bot", "ist_bot": 1, "typ": "text",
         "text": "Ja passt. Mach vorschlag fuer die Fragen, ich habe keine Ideen."},
        {"message_id": 6, "absender": "Birk", "ist_bot": 0, "typ": "text",
         "text": "Ne, das passt so."},
        {"message_id": 7, "absender": "bot", "ist_bot": 1, "typ": "text",
         "text": "Korrigiere ich im Arbeitsstand -- das steht jetzt so drin."},
    ]
}


@pytest.fixture
def material_dir(tmp_path, monkeypatch):
    verzeichnis = tmp_path / "birk-test"
    verzeichnis.mkdir()
    (verzeichnis / "interview-birk.md").write_text(_KOPF + _TRANSKRIPT, encoding="utf-8")
    (verzeichnis / "chat-04-09.json").write_text(
        json.dumps(_CHAT, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setenv("IT_SIM_BIRK", str(verzeichnis))
    return verzeichnis


# --- Frontmatter ----------------------------------------------------------


def test_der_kopf_liefert_begriffe_und_fragen(material_dir):
    assert birk.begriffe() == ["Kueche", "erste Liebe", "Fernweh nach Hawaii"]
    fragen = birk.fragen()
    assert len(fragen) == 3
    assert fragen[0].startswith("Kueche:")


def test_das_interview_hat_dieselbe_form_wie_die_erfundenen(material_dir):
    """Der Lauf soll nichts von diesem Sonderfall wissen muessen."""
    interview = birk.lade()
    assert interview.kennung == birk.KENNUNG
    assert interview.name == birk.INTERVIEW_NAME
    assert interview.nummer == 0
    assert interview.themen == ("Kueche", "erste Liebe", "Fernweh nach Hawaii")
    assert interview.zitate_soll == birk.ZITATE_SOLL


def test_das_interview_zerfaellt_in_genau_drei_teile(material_dir):
    """Drei Antworten auf drei Fragen -- und daran wird gemessen, ob der Bot
    aus drei Textimporten EINE Verdichtung macht (§ 10.6) statt drei."""
    stuecke = birk.lade().teile(birk.TEILE)
    assert len(stuecke) == 3
    for stueck, zitat_soll in zip(stuecke, birk.ZITATE_SOLL):
        assert zitat_soll in stueck


def test_ein_verlorenes_sollzitat_faellt_beim_laden_auf(material_dir):
    """Sonst waere es im Bericht eine Null, die niemand erklaeren kann."""
    (material_dir / "interview-birk.md").write_text(
        _KOPF + "Ein ganz anderer Text ohne die Saetze.", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Soll-Zitate"):
        birk.lade()


def test_fehlendes_material_ist_kein_absturz(tmp_path, monkeypatch):
    monkeypatch.setenv("IT_SIM_BIRK", str(tmp_path / "gibtsnicht"))
    assert birk.vorhanden() is False
    assert birk.chat() == []
    assert birk.referenz() == {}
    assert birk.stil_referenz() == ""


# --- Die Stimme -----------------------------------------------------------


def test_die_stimme_ist_eine_person_kalibriert_auf_den_echten_chat(material_dir):
    person = birk.person()
    assert person.name == "Birk"
    assert person.system.startswith(stimmen.lade_profil("birk"))
    # Nur SEINE Nachrichten, nicht die des Bots: die Stimme soll lernen, wie
    # er schreibt.
    assert "Mach vorschlag" in person.system
    assert "Hab die drei Begriffe" not in person.system


def test_ohne_chat_traegt_der_steckbrief_allein(material_dir):
    (material_dir / "chat-04-09.json").unlink()
    person = birk.person()
    assert person.system == stimmen.lade_profil("birk")


# --- Die Referenzzahlen ---------------------------------------------------


def test_referenz_zaehlt_abschnitte_zwischen_den_notiert_zeilen(material_dir):
    """Die Notiert-Zeilen sind die Trennmarken zwischen den Arbeitsschritten:
    was dazwischen liegt, hat die Gruppe gebraucht, um eine Festlegung
    durchzubekommen."""
    r = birk.referenz()
    assert r["nachrichten_je_abschnitt"] == [1, 2]
    assert r["nachrichten_gesamt"] == 3


def test_referenz_zaehlt_rueckfrage_echo_und_behauptung(material_dir):
    r = birk.referenz()
    assert r["rueckfragen"] == 1        # Nachricht 2 endet auf "?"
    assert r["echo"] == 1               # Nachricht 5 spiegelt Nachricht 4
    assert r["behauptete_schreibvorgaenge"] == 1   # Nachricht 7, ohne Notiert


def test_die_handzaehlung_steht_daneben_und_wird_nicht_nachgerechnet(material_dir):
    """Was Birk als 'Rueckfrage' gezaehlt hat, ist ein Urteil -- keine
    mechanische Regel trifft es. Eine Zahl hinzubiegen, bis sie 4 ergibt,
    waere das Gegenteil einer Messung."""
    assert birk.referenz()["handzaehlung"] == birk.HANDZAEHLUNG
    assert birk.HANDZAEHLUNG["rueckfragen"] == 4
    assert birk.HANDZAEHLUNG["echo"] == 1
    assert birk.HANDZAEHLUNG["behauptete_schreibvorgaenge"] == 5


# --- Das Skript -----------------------------------------------------------


def test_das_birk_skript_hat_ein_interview_in_drei_teilen():
    schritt = skript.schritt_fuer("interviews", skript.SCHRITTE_BIRK)
    assert schritt.teile == birk.TEILE == 3
    assert schritt.mit_frage is False


def test_das_birk_skript_laesst_drei_szenen_in_drei_formen_schreiben():
    szenen = [s for s in skript.SCHRITTE_BIRK if s.art == "szene"]
    assert [s.szene_nummer for s in szenen] == [1, 2, 3]
    assert [s.form for s in szenen] == list(skript.FORMEN_BIRK)


def test_jeder_szenenschritt_prueft_seine_eigene_nummer(conn):
    """Bei drei Szenen hintereinander genuegt 'irgendeine Szene hat einen
    Volltext' nicht: nach Szene 1 waere jeder weitere Schritt sofort fertig,
    und die Szenen 2 und 3 entstuenden nie."""
    from interview_theater import repo

    szenen = [s for s in skript.SCHRITTE_BIRK if s.art == "szene"]
    assert not any(s.fertig(conn, 1, {}) for s in szenen)

    repo.lege_szene_an(conn, 1, 1, "Der Kessel", "kurz", "MIRA: Los.")
    assert szenen[0].fertig(conn, 1, {}) is True
    assert szenen[1].fertig(conn, 1, {}) is False
    assert szenen[2].fertig(conn, 1, {}) is False


def test_das_format_der_phase_fuenf_nennt_alle_drei_formen():
    schritt = skript.schritt_fuer("phase_mitte", skript.SCHRITTE_BIRK)
    for form in skript.FORMEN_BIRK:
        assert form in schritt.ziel


def test_die_drei_szenenziele_nennen_ort_und_anlass():
    ziele = " ".join(
        s.ziel for s in skript.SCHRITTE_BIRK if s.art == "szene"
    ).lower()
    for stichwort in ("polizeikessel", "riviera", "pfannkuchen", "hawaii",
                      "autonome"):
        assert stichwort in ziele


def test_ohne_szene_nimmt_dem_birk_skript_die_drei_szenen():
    uebrig = skript.ohne_szene(skript.SCHRITTE_BIRK)
    assert not any(s.art == "szene" for s in uebrig)
    assert len(uebrig) == len(skript.SCHRITTE_BIRK) - 3


# --- Ein ganzer --set-birk-Lauf, ohne Netz --------------------------------


#: Ziel-Stichwort im Stimmen-Prompt -> was Birk daraufhin schreibt.
_STIMME = (
    ("Interview", "wir machen jetzt ein interview"),
    ("fertig bist", "fertig"),
    ("an der Wand", "kueche, erste liebe, fernweh nach hawaii"),
    ("Interviewfragen", "ne, die frageliste passt so"),
    ("Kernthema", "das kernthema ist woher die bilder in uns kommen"),
    ("Figuren", "figur Mira: die sammlerin"),
    ("Format", "der hauptkonflikt ist eigenes bild gegen fremdes bild"),
    ("Szene 1", "polizeikessel auf der demo, alle drei"),
    ("Szene 2", "pals kueche, pfannkuchen"),
    ("Szene 3", "nachts im autonomen zentrum, hawaii"),
)

#: Was Birk geschrieben hat -> was der Erkenner daraus macht.
_ERKENNER = (
    ("wir machen jetzt ein interview", "interview_starten", ""),
    ("fertig", "interview_beenden", ""),
    ("kueche, erste liebe", "begriffe_setzen", "Kueche, erste Liebe"),
    ("frageliste", "fragen_setzen", "Kueche: Was kochst du?"),
    ("kernthema ist", "kernthema_setzen", "Woher die Bilder kommen"),
    ("figur ", "figur_setzen", ""),
    ("hauptkonflikt ist", "hauptkonflikt_setzen", "eigenes gegen fremdes Bild"),
)


@pytest.fixture
def birk_lauf(material_dir, monkeypatch, tmp_path):
    from interview_theater import einstellungen, llm
    from simulation import bericht, claude as sim_claude
    from scripts import simulation as sim

    szenen = {"n": 0}

    def stimme(nutzer):
        _, _, ziel = nutzer.partition(stimmen._ZIEL_KOPF)
        for stichwort, antwort in _STIMME:
            if stichwort in ziel:
                return antwort
        return "go"

    def erkenner(nutzer):
        _, _, gesagt = nutzer.partition("Neue Nachrichten:")
        gesagt = gesagt.lower()
        for stichwort, art, wert in _ERKENNER:
            if stichwort not in gesagt:
                continue
            if art == "figur_setzen":
                return {"aenderungen": [
                    {"art": "figur_setzen", "wert": f"{n}: eine Figur"}
                    for n in birk.FIGUREN_DAMALS
                ]}
            return {"aenderungen": [{"art": art, "wert": wert}]}
        return {"aenderungen": []}

    def falsches_schema(self, chat_id, system, nutzer, schema, art,
                        modell=None, temperature=None):
        if art == "erkenner":
            return erkenner(nutzer)
        if art == "journal":
            return {"eintraege": []}
        if art == "verdichter":
            return {"zusammenfassung": "Er erzaehlt von Pfannkuchen.",
                    "kernthemen": [{"thema": "Kueche", "kurz": "Kueche",
                                    "beleg_zitat": birk.ZITATE_SOLL[0]}]}
        return {"antwort": "Erzaehl mir mehr davon."}

    def falsche_prosa(self, chat_id, system, nutzer, art, max_tokens=None,
                      timeout=None):
        szenen["n"] += 1
        return (f"TITEL: Szene {szenen['n']}\nKURZ: kurz\n\n"
                "MIRA: Riviera.\nPOLA: Nein.\nPAL: Pfannkuchen.")

    class SimAttrappe:
        modell = "claude-opus-5"

        def __init__(self):
            self.statistik = sim_claude.Statistik()

        def text(self, system, nutzer, art="sim", max_tokens=None):
            self.statistik.buche(art, 10, 5, True)
            return stimme(nutzer)

        def json_objekt(self, system, nutzer, art="sim", max_tokens=None):
            self.statistik.buche(art, 10, 5, True)
            if "form_eingehalten" in nutzer:
                return {"szene_stimmt_zur_planung": 2, "stimmen_unterscheidbar": 1,
                        "form_eingehalten": 2, "satz": "passt zur Form"}
            return {"geht_auf_gesagtes_ein": 2, "bietet_an_statt_vorzuschreiben": 2,
                    "phase_transparent": 2, "korrektur_angenommen": 2,
                    "satz": "ok", "zustimmungen": ["S1"],
                    "schlechteste_antwort": "", "begruendung": ""}

        def schliesse(self):
            pass

    monkeypatch.setattr(
        sim.einstellungen, "laden",
        lambda: einstellungen.Einstellungen(
            bot_token="T", bot_name="simulation", db_pfad=str(tmp_path / "x.db"),
            audio_verz=str(tmp_path / "audio"),
            llm_url="https://llm.test/v1/chat/completions", llm_key="K",
            llm_modell="moonshotai/Kimi-K2.6", stt_basis="https://stt.test",
            stt_produkt="P", erkenner_modell="google/gemma-4-31B-it",
        ),
    )
    monkeypatch.setattr(llm.LLM, "schema", falsches_schema)
    monkeypatch.setattr(llm.LLM, "prosa", falsche_prosa)
    monkeypatch.setattr(sim.claude, "Claude", lambda *a, **k: SimAttrappe())
    monkeypatch.setattr(bericht, "LAEUFE", tmp_path / "laeufe")
    monkeypatch.setattr(bericht, "BERICHTE", tmp_path / "berichte")
    monkeypatch.setattr(bericht, "VERLAUF", tmp_path / "berichte" / "verlauf.jsonl")
    return {"tmp": tmp_path, "sim": sim}


def _verlaufszeile(birk_lauf) -> dict:
    zeilen = (birk_lauf["tmp"] / "berichte" / "verlauf.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    return json.loads(zeilen[-1])


def test_ein_ganzer_birk_lauf_geht_durch(birk_lauf):
    assert birk_lauf["sim"].main(["--set", "birk", "--seed", "1"]) == 0
    daten = _verlaufszeile(birk_lauf)
    assert daten["mischung"] == "birk"
    assert daten["verdichtungen"] == 1, "drei Textimporte, EINE Verdichtung (§ 10.6)"
    assert daten["interviews_soll"] == 1
    assert [s["nummer"] for s in daten["szenen"]] == [1, 2, 3]
    assert [s["form"] for s in daten["szenen"]] == list(skript.FORMEN_BIRK)


def test_der_bericht_zeigt_die_drei_szenen_vollstaendig_und_den_vergleich(birk_lauf):
    birk_lauf["sim"].main(["--set", "birk", "--seed", "1", "--bericht"])
    text = list((birk_lauf["tmp"] / "berichte").glob("*.md"))[0].read_text(
        encoding="utf-8"
    )
    assert "## Referenzvergleich" in text
    assert "Handzaehlung Birk" in text
    for form in skript.FORMEN_BIRK:
        assert f"Form: {form}" in text
    assert "form_eingehalten" in text
    # Drei Szenenbloecke, jeder ungekuerzt -- der Zaehler liegt hoeher, weil
    # die Vorschau derselben Szene auch im Abschnitt "schlechteste Antworten"
    # stehen kann.
    assert text.count("```") == 6, "drei Szenenbloecke"
    assert text.count("PAL: Pfannkuchen.") >= 3, "jede Szene ungekuerzt"
    assert birk.KERNTHEMA_DAMALS in text


def test_ohne_szene_ist_bei_birk_verboten(birk_lauf):
    """Die drei Szenen SIND dieser Lauf -- ohne sie waere er zehn Minuten
    billiger und ohne Aussage."""
    with pytest.raises(SystemExit, match="ohne-szene"):
        birk_lauf["sim"].main(["--set", "birk", "--ohne-szene"])


def test_ohne_material_bricht_der_lauf_verstaendlich_ab(birk_lauf, monkeypatch,
                                                       tmp_path):
    monkeypatch.setenv("IT_SIM_BIRK", str(tmp_path / "weg"))
    with pytest.raises(SystemExit, match="IT_SIM_BIRK"):
        birk_lauf["sim"].main(["--set", "birk"])


# --- Gegenprobe am echten Material ---------------------------------------

_echt = pytest.mark.skipif(
    not birk.VERZEICHNIS_VORGABE.is_dir(),
    reason="das echte Testmaterial liegt ausserhalb des Repositories",
)


@_echt
def test_das_echte_interview_traegt_die_drei_sollzitate(monkeypatch):
    monkeypatch.delenv("IT_SIM_BIRK", raising=False)
    interview = birk.lade()
    assert len(interview.teile(birk.TEILE)) == 3
    assert interview.themen == ("Küche", "erste Liebe", "Fernweh nach Hawaii")


@_echt
def test_der_echte_chat_liefert_echo_und_behauptungen_wie_gezaehlt(monkeypatch):
    """Echo und die unbelegten 'notiert'-Behauptungen rechnet die mechanische
    Zaehlung genauso wie Birks Handzaehlung -- bei den Rueckfragen tut sie es
    nicht, und deshalb stehen im Bericht beide Spalten."""
    monkeypatch.delenv("IT_SIM_BIRK", raising=False)
    r = birk.referenz()
    assert r["echo"] == birk.HANDZAEHLUNG["echo"]
    assert (r["behauptete_schreibvorgaenge"]
            == birk.HANDZAEHLUNG["behauptete_schreibvorgaenge"])
    assert r["nachrichten_gesamt"] > 40
