from simulation import browser_judge as j


class _FakeClient:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def json_objekt(self, system, nutzer, art="sim", bilder=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "bilder": bilder})
        if isinstance(self.antwort, Exception):
            raise self.antwort
        return self.antwort


def test_rubrik_wird_gelesen_und_steht_im_system_prompt():
    client = _FakeClient({"note": 4, "befunde": []})
    j.bewerte_phase(client, 1, "Terms", [b"img"], ["001.png"], {"x": 1})
    system = client.aufrufe[0]["system"]
    assert "The group authors, the bot assists" in system  # aus ux_rubrik.md


def test_bild_und_zaehler_gehen_mit():
    client = _FakeClient({"note": 3, "befunde": [{"text": "zu viele Fragen",
                                                   "schwere": "mittel"}]})
    ergebnis = j.bewerte_phase(client, 2, "Questions", [b"a", b"b"],
                               ["001.png", "002.png"], {"mehrere_fragen": 1})
    assert ergebnis["note"] == 3
    assert ergebnis["befunde"][0]["text"] == "zu viele Fragen"
    assert client.aufrufe[0]["bilder"] == [b"a", b"b"]
    assert "mehrere_fragen" in client.aufrufe[0]["nutzer"]


def test_modellfehler_liefert_keine_note_statt_zu_werfen():
    ergebnis = j.bewerte_phase(_FakeClient(ValueError("boom")), 1, "Terms",
                               [], [], {})
    assert ergebnis["note"] is None
    assert ergebnis["befunde"] == []
