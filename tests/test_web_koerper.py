"""Der Rumpf einer Seite, ohne ihre Klammer.

Die vereinte Seite (Karte W) traegt Arbeitsstand, Textbuch und Chat als drei
Panels in EINEM Dokument. Sie braucht deshalb von jeder Seite den Koerper --
und die Einzelseiten muessen dabei Zeichen fuer Zeichen bleiben, was sie
waren. Genau das prueft diese Datei.
"""

from interview_theater import db, repo, web, web_chat

CHAT = 7_000_000_000_001


def _daten(tmp_path):
    from interview_theater import web_daten

    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    lesend = web_daten.oeffne_lesend(pfad)
    daten = web_daten.gruppe_nach_token(lesend, token)
    lesend.close()
    return daten, token


def test_die_gruppenseite_ist_ihr_koerper_in_der_klammer(tmp_path):
    daten, token = _daten(tmp_path)
    seite = web.gruppe_html(daten, "nonce", token)
    koerper = web.gruppe_koerper(daten, "nonce", token)
    assert koerper in seite
    assert not koerper.startswith("<!doctype")


def test_die_probenansicht_ist_ihr_koerper_in_der_klammer(tmp_path):
    daten, token = _daten(tmp_path)
    assert web.textbuch_koerper(daten, token) in web.textbuch_html(daten, token)


def test_die_chatansicht_ist_ihr_koerper_in_der_klammer(tmp_path):
    daten = {"titel": "Die Ankommenden", "nachrichten": [], "letzte": 0,
             "interviewmodus": False, "tippt": False, "antworten": {}}
    seite = web_chat.chat_html(daten, "nonce", "tok", "/theatersoap", 45_000)
    assert web_chat.chat_koerper(daten, "nonce", "tok", 45_000) in seite


def test_die_basis_steht_im_chatkoerper(tmp_path):
    """Auf der vereinten Seite ist die Basis ``/g/<token>`` statt
    ``/g/<token>/chat`` -- jede relative URL des Chat-JS braucht deshalb ein
    Praefix, und es steht als ``data-basis`` in der Seite."""
    daten = {"titel": "x", "nachrichten": [], "letzte": 0,
             "interviewmodus": False, "tippt": False, "antworten": {}}
    ohne = web_chat.chat_koerper(daten, "n", "tok", 45_000)
    mit = web_chat.chat_koerper(daten, "n", "tok", 45_000, basis="tok/")
    assert 'data-basis=""' in ohne
    assert 'data-basis="tok/"' in mit


def test_mit_gruppenlink_schaltet_den_link_ab(tmp_path):
    """Fix-Runde 1 (Aufgabe 16): auf der vereinten Seite fuehrte der Link
    auf die Seite, auf der er selbst stand -- ``mit_gruppenlink=False``
    laesst ihn weg, die Vorgabe (Chat-Einzelseite) behaelt ihn."""
    daten = {"titel": "x", "nachrichten": [], "letzte": 0,
             "interviewmodus": False, "tippt": False, "antworten": {}}
    mit = web_chat.chat_koerper(daten, "n", "tok", 45_000)
    ohne = web_chat.chat_koerper(daten, "n", "tok", 45_000, mit_gruppenlink=False)
    assert web_chat._TEXT_ZUR_GRUPPENSEITE in mit
    assert web_chat._TEXT_ZUR_GRUPPENSEITE not in ohne


def test_das_chat_js_baut_seine_pfade_ueber_die_basis():
    """Ohne diese Regel zeigte jeder ``fetch`` der vereinten Seite auf
    ``/g/chat/zustand`` -- ein stilles 404 im Browser."""
    assert "data-basis" in web_chat._CHAT_JS or "dataset.basis" in web_chat._CHAT_JS
    # Kein nackter Pfad mehr: jedes 'chat/...' haengt an BASIS.
    for treffer in ("'chat/", '"chat/'):
        assert treffer not in web_chat._CHAT_JS, treffer
