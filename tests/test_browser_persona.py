import json

from simulation import browser_persona as p


class _FakeClient:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def json_objekt(self, system, nutzer, art="sim", bilder=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art,
                             "bilder": bilder})
        if isinstance(self.antwort, Exception):
            raise self.antwort
        return self.antwort


def test_aktion_geht_mit_bild_und_elementliste_hinaus():
    client = _FakeClient({"type": "click", "element_id": 2, "begruendung": "ok"})
    elemente = [{"id": 2, "art": "chip", "text": "Something else"}]
    aktion = p.naechste_aktion(client, "student", b"PNGDATEN", elemente,
                               "Collect terms.", ["Bot: hi"])
    assert aktion == {"type": "click", "element_id": 2, "begruendung": "ok"}
    aufruf = client.aufrufe[0]
    assert aufruf["bilder"] == [b"PNGDATEN"]
    assert "Something else" in aufruf["nutzer"]
    assert "Collect terms." in aufruf["nutzer"]
    assert p.PERSONEN["student"] in aufruf["system"]


def test_kaputtes_json_wird_zu_wait_statt_zu_werfen():
    aktion = p.naechste_aktion(_FakeClient(ValueError("boom")), "student",
                               b"x", [], "ziel", [])
    assert aktion["type"] == "wait"


def test_antwort_ohne_type_wird_zu_wait():
    aktion = p.naechste_aktion(_FakeClient({"begruendung": "nur das"}), "student",
                               b"x", [], "ziel", [])
    assert aktion["type"] == "wait"


def test_alle_vier_personas_existieren_und_unterscheiden_sich():
    assert set(p.PERSONEN) == {"student", "clicker", "giulia", "priya"}
    assert len(set(p.PERSONEN.values())) == 4


def test_priya_ist_erstnutzerin_ohne_push_to_talk():
    text = p.PERSONEN["priya"].lower()
    assert "never used push-to-talk" in text
    assert "ask" in text


def test_giulia_antwortet_auf_rueckfragen():
    assert "answer it in character" in p.PERSONEN["giulia"]


def test_hinweis_landet_im_nutzertext():
    client = _FakeClient({"type": "wait", "begruendung": "x"})
    p.naechste_aktion(client, "giulia", b"x", [], "ziel", [],
                      hinweis="The bot just asked you something. Answer it in character.")
    assert client.aufrufe[0]["nutzer"].rstrip().endswith(
        "The bot just asked you something. Answer it in character.")


def test_schema_nennt_done_station_und_offene_fragen():
    client = _FakeClient({"type": "wait", "begruendung": "x"})
    p.naechste_aktion(client, "priya", b"x", [], "ziel", [])
    system = client.aufrufe[0]["system"]
    assert "done_station" in system and "offene_fragen" in system


def test_offene_fragen_werden_bereinigt():
    aktion = {"offene_fragen": ["What is CoThinker?", "", 7, "x" * 300] + ["q"] * 9}
    fragen = p.offene_fragen(aktion)
    assert fragen[0] == "What is CoThinker?"
    assert all(isinstance(f, str) and f for f in fragen)
    assert len(fragen) == 5 and len(fragen[1]) == 200


def test_offene_fragen_fehlen_ergibt_leere_liste():
    assert p.offene_fragen({"type": "wait"}) == []
