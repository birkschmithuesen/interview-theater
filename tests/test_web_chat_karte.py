"""Die Telefon-Organisationskarte als ``<img>`` in der Chatansicht
(UX-Knoepfe-Karte, Abschnitt 5): serverseitig (``_blase_html``, erster
Seitenaufbau) UND clientseitig (``inhaltVon``/``bildVon``, jede weitere Zeile
ueber den Poll) auf demselben Weg -- wie schon bei den Speicherquittungen
(``test_web_chat_system_zeile.py``)."""

from interview_theater import web_chat


def _nachricht(**zusatz):
    basis = {
        "id": 1, "von": "bot", "typ": "system",
        "text": "Eins hoert zu, eins steht aufgestellt.",
        "dauer": None, "dateiname": None, "bild": None, "knoepfe": [],
    }
    basis.update(zusatz)
    return basis


def test_ohne_bild_bleibt_die_blase_wie_bisher():
    html = web_chat._blase_html(_nachricht())

    assert "<img" not in html


def test_mit_bild_steht_ein_img_in_der_blase():
    html = web_chat._blase_html(_nachricht(bild="phase-4.png"))

    assert '<img src="static/handys/phase-4.png"' in html
    assert 'alt="Eins hoert zu, eins steht aufgestellt."' in html
    assert 'loading="lazy"' in html
    # Der Satz steht WEITERHIN als sichtbarer Text darunter -- das Bild
    # ersetzt ihn nicht, es ergaenzt ihn.
    assert "Eins hoert zu, eins steht aufgestellt." in html


def test_die_url_traegt_die_basis_der_vereinten_seite():
    html = web_chat._blase_html(_nachricht(bild="phase-4.png"), basis="tok123/")

    assert '<img src="tok123/static/handys/phase-4.png"' in html


def test_ein_bildname_mit_anfuehrungszeichen_wird_maskiert():
    """Der Dateiname kommt aus dem Code (``handykarten.dateiname``), nicht
    aus Nutzereingabe -- trotzdem wird er wie jeder Attributwert maskiert,
    keine Ausnahme fuer eine vermeintlich sichere Quelle."""
    html = web_chat._blase_html(_nachricht(bild='x".png'))

    assert "&quot;" in html or "&#34;" in html
    assert '".png"' not in html


def test_die_js_baut_dasselbe_bild_fuer_live_nachrichten():
    js = web_chat._js()

    assert "function bildVon(n)" in js
    assert "n.bild" in js
    assert "static/handys/" in js
    assert "function inhaltVon(n) {\n    return bildVon(n) + textVon(n);" in js
