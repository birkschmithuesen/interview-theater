"""Die Buehne-Hinweiszeile im Chat oeffnet den Tab (UX-Knoepfe-Karte,
Abschnitt 5): dieselbe Zeile wie ``aufnahme._TEXT_BUEHNE_NEUE_KARTE`` wird
in ``_blase_html`` als Link auf ``#buehne`` erkannt -- textidentisch, nur
antippbar."""

from interview_theater import aufnahme, web_chat


def _nachricht(text, von="bot", typ="text", **zusatz):
    basis = {
        "id": 1, "von": von, "typ": typ, "text": text,
        "dauer": None, "dateiname": None, "knoepfe": [],
    }
    basis.update(zusatz)
    return basis


def test_die_buehnen_hinweiszeile_wird_ein_link_auf_den_tab():
    html = web_chat._blase_html(_nachricht(aufnahme._TEXT_BUEHNE_NEUE_KARTE))

    assert '<a href="#buehne">' in html
    assert aufnahme._TEXT_BUEHNE_NEUE_KARTE in html


def test_die_englische_fassung_wird_ebenfalls_erkannt():
    html = web_chat._blase_html(_nachricht("New card in the CoThinker tab"))

    assert '<a href="#buehne">' in html


def test_die_englische_fassung_nennt_den_tab_wie_die_tableiste():
    """P34 Runde 3, A9-Nebenbefund: der Tab heisst in EN "CoThinker"
    (["web_vereint"._TEXT_TAB] buehne), nicht "Stage" -- und der Erkenner in web_chat kennt
    genau diese Zeile."""
    import tomllib
    from pathlib import Path

    pfad = Path(web_chat.__file__).parent / "sprachen" / "en" / "texte.toml"
    en = tomllib.loads(pfad.read_text(encoding="utf-8"))
    zeile = en["aufnahme"]["_TEXT_BUEHNE_NEUE_KARTE"]

    assert zeile == "New card in the CoThinker tab"
    assert zeile in web_chat._TEXTE_BUEHNE_NEUE_KARTE


def test_alte_englische_zeile_im_verlauf_bleibt_ein_link():
    """Schon gespeicherte Bot-Zeilen mit dem alten Wortlaut bleiben antippbar."""
    html = web_chat._blase_html(_nachricht("New card in the Stage tab"))

    assert '<a href="#buehne">' in html


def test_dieselbe_zeile_aus_der_gruppe_bleibt_unverlinkt():
    """Nur eine Bot-Zeile wird erkannt -- sagt die Gruppe zufaellig
    wortgleich denselben Satz, ist das kein Link (keine Verwechslung mit
    Nutzertext, der denselben Wortlaut hat)."""
    html = web_chat._blase_html(
        _nachricht(aufnahme._TEXT_BUEHNE_NEUE_KARTE, von="gruppe")
    )

    assert '<a href="#buehne">' not in html


def test_eine_andere_bot_zeile_bleibt_schlichter_text():
    html = web_chat._blase_html(_nachricht("Notiert: Setting: Treppenhaus"))

    assert '<a href="#buehne">' not in html
    assert "Notiert: Setting: Treppenhaus" in html
