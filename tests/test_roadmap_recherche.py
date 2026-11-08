"""Der Recherche-Abschnitt der Werkbank (Karte t_c5117c91) -- unabhaengig
von den sieben Phasen, reine Funktion ueber Dicts wie ``aus_daten``/
``werkbank``."""

from interview_theater import roadmap


def test_ohne_recherchen_leere_liste():
    assert roadmap.recherche_abschnitt([]) == []


def test_recherche_abschnitt_traegt_frage_text_und_quellen():
    recherchen = [{
        "frage": "When was the bridge built?",
        "ergebnis_text": "The bridge was built in 1900 (Example, https://x.test).",
        "quellen": [{"titel": "Example", "url": "https://x.test"}],
    }]

    ergebnis = roadmap.recherche_abschnitt(recherchen)

    assert ergebnis == [{
        "frage": "When was the bridge built?",
        "ergebnis_text": "The bridge was built in 1900 (Example, https://x.test).",
        "quellen": ["Example"],
    }]


def test_quelle_ohne_titel_faellt_auf_die_url_zurueck():
    recherchen = [{
        "frage": "Q?", "ergebnis_text": "A.",
        "quellen": [{"titel": "", "url": "https://x.test"}],
    }]

    ergebnis = roadmap.recherche_abschnitt(recherchen)

    assert ergebnis[0]["quellen"] == ["https://x.test"]
