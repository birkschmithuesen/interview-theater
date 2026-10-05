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


class _ScriptedFakeClient:
    """Wie ``_ScriptedClient`` in ``tests/test_browser_lauf.py``: eine
    Antwort je Aufruf aus einer festen Folge -- fuer den Retry-Pfad von
    ``bewerte_erklaerung`` (erster Aufruf, dann der Hinweis-Aufruf)."""

    def __init__(self, folge):
        self._folge = list(folge)
        self.aufrufe = []

    def json_objekt(self, system, nutzer, art="sim", bilder=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "bilder": bilder})
        if self._folge:
            return self._folge.pop(0)
        return {"note_erklaerung": None, "schwaechstes_zitat": "", "vorschlag": ""}


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


def test_erklaerung_kriterien_stehen_im_prompt():
    from simulation import browser_judge
    client = _FakeClient({"note_erklaerung": 4, "schwaechstes_zitat": "Hi there",
                          "vorschlag": ""})
    browser_judge.bewerte_erklaerung(client, "p1-eintritt", ["Hi there, welcome!"])
    system = client.aufrufe[0]["system"]
    for kriterium in ("understandable", "short", "makes you want", "what happens now",
                      "no jargon", "no developer"):
        assert kriterium in system.lower()


def test_erklaerung_ohne_bot_text_ruft_kein_modell():
    from simulation import browser_judge
    client = _FakeClient({"note_erklaerung": 5, "schwaechstes_zitat": "", "vorschlag": ""})
    ergebnis = browser_judge.bewerte_erklaerung(client, "p1-eintritt", [])
    assert ergebnis == {"note_erklaerung": None, "schwaechstes_zitat": "", "vorschlag": ""}
    assert client.aufrufe == []


def test_erklaerung_zitat_muss_woertlich_aus_dem_bot_stammen():
    from simulation import browser_judge
    bot_texte = ["Welcome! Let's start with the terms that matter to your play."]
    client = _ScriptedFakeClient([
        {"note_erklaerung": 2, "schwaechstes_zitat": "this quote is invented",
         "vorschlag": "Say less."},
        {"note_erklaerung": 2, "schwaechstes_zitat": "Let's start with the terms",
         "vorschlag": "Say less."},
    ])
    ergebnis = browser_judge.bewerte_erklaerung(client, "p1-eintritt", bot_texte)
    assert ergebnis["note_erklaerung"] == 2
    assert ergebnis["schwaechstes_zitat"] == "Let's start with the terms"
    assert ergebnis.get("zitat_unbelegt") is not True

    client2 = _ScriptedFakeClient([
        {"note_erklaerung": 2, "schwaechstes_zitat": "invented one", "vorschlag": "x"},
        {"note_erklaerung": 2, "schwaechstes_zitat": "invented two", "vorschlag": "x"},
    ])
    ergebnis2 = browser_judge.bewerte_erklaerung(client2, "p1-eintritt", bot_texte)
    assert ergebnis2["schwaechstes_zitat"] == ""
    assert ergebnis2["zitat_unbelegt"] is True


def test_rubrik_erlaubt_das_begriffsboard_beim_zuhoeren():
    from simulation import browser_judge
    text = " ".join(browser_judge.lies_rubrik().split())
    assert ("Tell: a CoThinker-style card or a bot line appears during a pure "
            "context recording.") not in text
    assert "term board" in text
    assert "no bot line in the chat" in text.lower()
