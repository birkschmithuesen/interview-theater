"""Der kontextabhaengige Platzhalter im Eingabefeld (UX-Knoepfe-Karte,
Abschnitt 1): das Eingabefeld ist NIE gesperrt, aber was es einladend
vorschlaegt, soll zur Phase passen -- Standard, eine offene Frage in
Phase 2, freies Erzaehlen in Phase 4."""

from interview_theater import sprache, web_chat


def test_ohne_phase_steht_die_einladung_zum_freien_schreiben():
    assert web_chat._platzhalter_fuer(None, None) == web_chat._TEXT_EINGABE


def test_phase_2_ohne_offene_frage_bleibt_beim_standard():
    assert web_chat._platzhalter_fuer("2", None) == web_chat._TEXT_EINGABE


def test_phase_2_mit_offener_frage_laedt_zur_schaerfung_ein():
    assert web_chat._platzhalter_fuer("2", "3") == web_chat._TEXT_EINGABE_FRAGEN


def test_phase_4_laedt_zum_erzaehlen_ein():
    assert web_chat._platzhalter_fuer("4", None) == web_chat._TEXT_EINGABE_SETTING


def test_andere_phasen_bleiben_beim_standard():
    assert web_chat._platzhalter_fuer("6", None) == web_chat._TEXT_EINGABE


def test_das_eingabefeld_wird_nirgends_gesperrt():
    """UX-Knoepfe-Karte, Abschnitt 1: Pflichtsatz -- auch mit offenen
    Knoepfen bleibt das Feld bedienbar. Kein ``eingabe.disabled``, kein
    ``hidden`` am Eingabefeld, in keinem Zweig des Skripts."""
    js = web_chat._CHAT_JS
    assert "eingabe.disabled" not in js
    seite = web_chat.chat_html(
        {"nachrichten": [], "letzte": 0, "aenderung": 0,
         "interviewmodus": False, "titel": None},
        "1.x", "tok", "", 45000,
    )
    assert '<input type="text" id="eingabe"' in seite
    assert 'id="eingabe" autocomplete="off" placeholder="' in seite
    # Das Eingabefeld selbst traegt nie "disabled" oder "hidden".
    zeile = next(z for z in seite.splitlines() if 'id="eingabe"' in z)
    assert "disabled" not in zeile
    assert "hidden" not in zeile


def test_auf_englisch_kommt_der_englische_platzhalter(monkeypatch):
    monkeypatch.setattr(sprache, "code", lambda: "en")
    assert web_chat._platzhalter_fuer(None, None) != web_chat._TEXT_EINGABE
    assert "write" in web_chat._platzhalter_fuer(None, None).lower() \
        or "speak" in web_chat._platzhalter_fuer(None, None).lower()
    assert web_chat._platzhalter_fuer("4", None) != web_chat._TEXT_EINGABE_SETTING


def test_auf_englisch_kommt_das_englische_abkuerzungs_label(monkeypatch):
    monkeypatch.setattr(sprache, "code", lambda: "en")
    html = web_chat._blase_html({
        "id": 1, "von": "bot", "typ": "text", "text": "Weiter?",
        "dauer": None, "dateiname": None,
        "knoepfe": [("Ja", "k:1")],
    })
    assert web_chat._TEXT_ABKUERZUNG not in html
