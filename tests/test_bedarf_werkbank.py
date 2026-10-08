"""Die Bedarfsliste (Birk 08.10.2026 ~13:45, Padua) als Abhakliste in der
read-only Werkbank -- ein eigener Abschnitt direkt unter dem Hinweis, VOR
den Phasen. Englisch und unuebersetzt: der Inhalt kommt fertig aus der
Seed-Datei (``scripts/bedarf_seed.py``)."""

from interview_theater import web


def _minimal_daten(bedarf=None, web_token="tok123"):
    return {
        "titel": "Test group", "chat_id": 1, "web_token": web_token, "kanal": "web",
        "arbeitsstand": {}, "journal": [], "interviews": [],
        "figuren": [], "szenen": [], "festlegungen": [], "fragen_auswertung": None,
        "sprechanteile": None, "dramaturgie": None,
        "werkbank": {"phasen": [], "begriffe_detail": [], "szenen_anzahl": None},
        "bedarf": bedarf,
    }


def test_abschnitt_fehlt_ganz_ohne_bedarfspunkte():
    seite = web.werkbank_koerper(_minimal_daten([]))
    assert '<details class="wb-bedarf"' not in seite


def test_minimales_daten_dict_ohne_bedarf_schluessel_stuerzt_nicht():
    daten = _minimal_daten()
    del daten["bedarf"]
    seite = web.werkbank_koerper(daten)
    assert '<details class="wb-bedarf"' not in seite


def test_abschnitt_zeigt_sektionen_und_punkte_mit_checkbox():
    punkte = [
        {"id": 1, "sektion": "Props", "text": "Big wooden table", "erledigt": False},
        {"id": 2, "sektion": "Props", "text": "Six chairs", "erledigt": True},
        {"id": 3, "sektion": "Tech", "text": "Wireless mic", "erledigt": False},
    ]
    seite = web.werkbank_koerper(_minimal_daten(punkte))
    assert '<details class="wb-bedarf" open>' in seite
    assert "Needs list" in seite
    assert "Props" in seite and "Tech" in seite
    assert "Big wooden table" in seite
    assert '<input type="checkbox" class="wb-bedarf-check" data-bedarf-id="1">' in seite
    assert '<input type="checkbox" class="wb-bedarf-check" data-bedarf-id="2" checked>' in seite
    assert "1 of 3 done" in seite


def test_erledigter_punkt_traegt_die_erledigt_klasse():
    punkte = [{"id": 1, "sektion": "Props", "text": "Chair", "erledigt": True}]
    seite = web.werkbank_koerper(_minimal_daten(punkte))
    assert "wb-bedarf-erledigt" in seite


def test_bedarfsinhalt_wird_html_entschaerft_nicht_uebersetzt():
    punkte = [{"id": 1, "sektion": "Props<x>", "text": "A <script> tag", "erledigt": False}]
    seite = web.werkbank_koerper(_minimal_daten(punkte))
    assert "<script>" not in seite.split("</head>", 1)[-1].replace(
        "&lt;script&gt;", ""
    ) or "&lt;script&gt;" in seite
    assert "&lt;script&gt;" in seite
    assert "&lt;x&gt;" in seite


# -- Nachtrag Birk 08.10.2026 ~13:50: Downloads an einem Bedarfspunkt. --


def test_punkt_mit_datei_zeigt_download_link():
    punkte = [
        {"id": 1, "sektion": "Props", "text": "Floor plan", "erledigt": False,
         "datei": "floor-plan.pdf"},
    ]
    seite = web.werkbank_koerper(_minimal_daten(punkte, web_token="abTOK"))
    assert "⬇ PDF" in seite
    assert 'href="abTOK/bedarf/floor-plan.pdf"' in seite


def test_punkt_ohne_datei_zeigt_keinen_link():
    punkte = [{"id": 1, "sektion": "Props", "text": "Chair", "erledigt": False,
               "datei": None}]
    seite = web.werkbank_koerper(_minimal_daten(punkte))
    assert "⬇ PDF" not in seite


def test_punkt_ohne_datei_schluessel_stuerzt_nicht():
    """Aeltere Aufrufer (vor Nachtrag 1) kennen den Schluessel ``datei`` noch
    nicht -- wie bei ``phasen_summaries`` darf das nicht abstuerzen."""
    punkte = [{"id": 1, "sektion": "Props", "text": "Chair", "erledigt": False}]
    seite = web.werkbank_koerper(_minimal_daten(punkte))
    assert "⬇ PDF" not in seite


def test_dateiname_im_link_wird_html_entschaerft():
    punkte = [{"id": 1, "sektion": "Props", "text": "Chair", "erledigt": False,
               "datei": 'a"b.pdf'}]
    seite = web.werkbank_koerper(_minimal_daten(punkte, web_token="abTOK"))
    assert '"' not in seite.split('href="abTOK/bedarf/', 1)[1].split('"', 1)[0]


def test_abschnitt_steht_vor_der_ersten_phase():
    punkte = [{"id": 1, "sektion": "Props", "text": "Chair", "erledigt": False}]
    daten = _minimal_daten(punkte)
    daten["werkbank"] = {
        "phasen": [
            {"nummer": 1, "bezeichnung": "Begriffe", "erledigt": 0, "gesamt": 1,
             "fertig": False, "aktiv": True, "zeilen": []},
        ],
        "begriffe_detail": [], "szenen_anzahl": None,
    }
    seite = web.werkbank_koerper(daten)
    assert seite.index('<details class="wb-bedarf"') < seite.index('class="wb-phase"')
