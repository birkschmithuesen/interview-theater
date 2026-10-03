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


def test_beide_personas_existieren_und_unterscheiden_sich():
    assert set(p.PERSONEN) == {"student", "clicker"}
    assert p.PERSONEN["student"] != p.PERSONEN["clicker"]
