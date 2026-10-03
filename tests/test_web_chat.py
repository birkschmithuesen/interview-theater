"""Die Chatansicht: was der Server liefert -- ohne Browser.

Der HTML-Filter ist der Kern dieser Datei. Bot-Ausgaben tragen
Telegram-HTML (parse_mode="HTML", fuenf Stellen im Repo, u. a.
vorschlag.menuetext): die Chatansicht muss es DARSTELLEN und darf dabei
nichts anderes durchlassen.
"""

import json
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_chat, web_daten

CHAT = 7_000_000_000_001


@pytest.fixture
def datenbank(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return pfad, token


# -- der HTML-Filter (Entscheidung F) --------------------------------------


@pytest.mark.parametrize("gefaehrlich", [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<a href=\"javascript:alert(1)\">klick</a>",
    "<iframe src=\"https://example.invalid\"></iframe>",
    "<b onclick=\"alert(1)\">fett</b>",
    "<svg/onload=alert(1)>",
    "<a href=\"data:text/html,<script>alert(1)</script>\">x</a>",
    "<style>body{display:none}</style>",
])
def test_nichts_gefaehrliches_kommt_durch(gefaehrlich):
    ergebnis = web_chat.sichere_html(gefaehrlich)
    for verboten in ("<script", "<img", "<iframe", "<svg", "<style",
                     "onerror", "onclick", "onload", "javascript:", "data:text"):
        assert verboten not in ergebnis.lower(), ergebnis


@pytest.mark.parametrize("tag", list(web_chat.ERLAUBTE_TAGS))
def test_die_telegram_teilmenge_kommt_durch(tag):
    ergebnis = web_chat.sichere_html(f"<{tag}>Text</{tag}>")
    assert ergebnis == f"<{tag}>Text</{tag}>"


def test_ein_link_kommt_durch_und_bekommt_noopener():
    ergebnis = web_chat.sichere_html(
        '<a href="https://lab.example/theatersoap/g/x">Gruppenseite</a>'
    )
    assert 'href="https://lab.example/theatersoap/g/x"' in ergebnis
    assert "noopener" in ergebnis
    assert ">Gruppenseite</a>" in ergebnis


def test_ein_link_ohne_http_kommt_nicht_durch():
    ergebnis = web_chat.sichere_html('<a href="ftp://x/y">z</a>')
    assert "<a " not in ergebnis
    assert "&lt;a" in ergebnis


def test_der_ampersand_bleibt_ein_ampersand():
    """Telegram-HTML maskiert & als &amp; (telegram.escape_html). Die Ansicht
    darf daraus kein doppelt maskiertes &amp;amp; machen."""
    assert web_chat.sichere_html("Kaffee &amp; Kuchen") == "Kaffee &amp; Kuchen"
    assert web_chat.sichere_html("Kaffee & Kuchen") == "Kaffee &amp; Kuchen"


def test_zeilenumbrueche_werden_sichtbar():
    assert web_chat.sichere_html("eins\nzwei") == "eins<br>zwei"


def test_leerer_text_ist_leer():
    assert web_chat.sichere_html(None) == ""
    assert web_chat.sichere_html("") == ""


def test_ein_echter_vorschlagsblock_bleibt_lesbar():
    """Der gemessene Fall: vorschlag.menuetext baut genau diese Form."""
    roh = ("Drei Richtungen:\n"
           "1. <b>Ankunft am Steg</b> — sie warten auf ein Boot\n"
           "2. <b>Nacht im Treppenhaus</b> — niemand schlaeft")
    ergebnis = web_chat.sichere_html(roh)
    assert "<b>Ankunft am Steg</b>" in ergebnis
    assert ergebnis.count("<br>") == 2


# -- der Verlauf (web_daten, read-only) ------------------------------------


def test_verlauf_zeigt_beide_richtungen_in_der_reihenfolge(datenbank):
    pfad, _token = datenbank
    schreibend = db.verbinde(pfad)
    ein = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN,
                                repo.WEB_TYP_TEXT, text="Unsere Begriffe")
    aus = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_AUS,
                                repo.WEB_TYP_TEXT, text="Notiert.",
                                knoepfe=[("Ja, speichern", "k:1")])
    schreibend.close()

    lesend = web_daten.oeffne_lesend(pfad)
    verlauf = web_daten.web_chatverlauf(lesend, CHAT)
    lesend.close()

    assert [z["id"] for z in verlauf] == [ein, aus]
    assert verlauf[0]["von"] == "gruppe"
    assert verlauf[1]["von"] == "bot"
    assert verlauf[1]["knoepfe"] == [["Ja, speichern", "k:1"]]


def test_verlauf_verbirgt_befehle_und_geloeschtes(datenbank):
    """'befehl' ist der Umschalter-Druck, der als Slash-Text in den Bot geht.
    Slash-Befehle werden nicht beworben (AGENTS.md) -- er steht nicht im Chat."""
    pfad, _token = datenbank
    schreibend = db.verbinde(pfad)
    repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN,
                          repo.WEB_TYP_BEFEHL, text="/interview")
    weg = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_AUS,
                                repo.WEB_TYP_TEXT, text="Arbeitszeile")
    repo.loesche_web_posts(schreibend, CHAT, [weg])
    bleibt = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_AUS,
                                   repo.WEB_TYP_TEXT, text="Notiert.")
    schreibend.close()

    lesend = web_daten.oeffne_lesend(pfad)
    verlauf = web_daten.web_chatverlauf(lesend, CHAT)
    lesend.close()
    assert [z["id"] for z in verlauf] == [bleibt]


def test_verlauf_ab_nach(datenbank):
    pfad, _token = datenbank
    schreibend = db.verbinde(pfad)
    erste = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN,
                                  repo.WEB_TYP_TEXT, text="a")
    zweite = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_AUS,
                                   repo.WEB_TYP_TEXT, text="b")
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    assert [z["id"] for z in web_daten.web_chatverlauf(lesend, CHAT, nach=erste)] == [zweite]
    lesend.close()


def test_eine_sprachnachricht_zeigt_die_dauer_und_keinen_pfad(datenbank):
    """Der Dateipfad gehoert nicht ins HTML: er ist eine Serverinnerei, und
    die Ansicht ist ohne Login erreichbar."""
    pfad, _token = datenbank
    schreibend = db.verbinde(pfad)
    repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
                          dauer=45, datei="/tmp/geheim/1.webm", mime="audio/webm")
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    zeile = web_daten.web_chatverlauf(lesend, CHAT)[0]
    lesend.close()
    assert zeile["typ"] == repo.WEB_TYP_SPRACHE
    assert zeile["dauer"] == 45
    assert "datei" not in zeile


def test_zustand_nennt_phase_interviewmodus_und_tippt(datenbank):
    pfad, token = datenbank
    schreibend = db.verbinde(pfad)
    repo.setze_phase(schreibend, CHAT, 3)
    repo.setze_interviewmodus(schreibend, CHAT, repo._jetzt())
    schreibend.close()

    lesend = web_daten.oeffne_lesend(pfad)
    zustand = web_daten.web_chatzustand(lesend, token)
    lesend.close()

    assert zustand["chat_id"] == CHAT
    assert zustand["phase"] == 3
    assert zustand["interviewmodus"] is True
    assert zustand["tippt"] is False
    assert zustand["nachrichten"] == []
    assert zustand["letzte"] == 0


def test_zustand_meldet_tippt_nur_solange_es_gilt(datenbank):
    pfad, token = datenbank
    schreibend = db.verbinde(pfad)
    repo.setze_web_tippt(schreibend, CHAT, "2020-01-01T00:00:00+00:00")
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    assert web_daten.web_chatzustand(lesend, token)["tippt"] is False
    lesend.close()


def test_zustand_traegt_die_knopfantwort_mit(datenbank):
    pfad, token = datenbank
    schreibend = db.verbinde(pfad)
    post_id = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN,
                                    repo.WEB_TYP_KNOPF, daten="k:1",
                                    bezug_message_id=1)
    repo.setze_web_antwort(schreibend, post_id, "Begriffe uebernommen")
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    zustand = web_daten.web_chatzustand(lesend, token)
    lesend.close()
    assert zustand["antworten"] == {str(post_id): "Begriffe uebernommen"}


def test_zustand_nennt_die_nachricht_unter_die_die_quittung_gehoert(datenbank):
    """Birk 03.10.2026: „Discarded steht unten unter allem Chat, muss aber
    unter der abgelehnten Frage stehen.“ Der Poll muss dafuer sagen, an
    welcher Nachricht gedrueckt wurde."""
    pfad, token = datenbank
    schreibend = db.verbinde(pfad)
    post_id = repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN,
                                    repo.WEB_TYP_KNOPF, daten="fe:3:nein",
                                    bezug_message_id=42)
    repo.setze_web_antwort(schreibend, post_id, "✗ Discarded")
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    zustand = web_daten.web_chatzustand(lesend, token)
    lesend.close()
    assert zustand["antworten_bezug"] == {str(post_id): 42}


def test_zustand_bei_unbekanntem_token_ist_none(datenbank):
    pfad, _token = datenbank
    lesend = web_daten.oeffne_lesend(pfad)
    assert web_daten.web_chatzustand(lesend, "gibtsnicht") is None
    lesend.close()


# -- Pegel-Kalibrierung (Task 2, Kanban-Karte Mithoeren SICHER/             --
# -- Kalibrierung, 03.10.2026) ----------------------------------------------


def test_zustand_kalibrierung_modus_ist_ohne_herumreichen_none(datenbank):
    pfad, token = datenbank
    lesend = web_daten.oeffne_lesend(pfad)
    assert web_daten.web_chatzustand(lesend, token)["kalibrierung_modus"] is None
    lesend.close()


def test_zustand_nennt_kalibrierung_modus_herumreichen(datenbank):
    pfad, token = datenbank
    schreibend = db.verbinde(pfad)
    repo.setze_kalibrierung_modus_herumreichen(schreibend, CHAT)
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    assert web_daten.web_chatzustand(lesend, token)["kalibrierung_modus"] == "herumreichen"
    lesend.close()


def test_zustand_kalibrierung_upload_ist_ohne_upload_none(datenbank):
    pfad, token = datenbank
    lesend = web_daten.oeffne_lesend(pfad)
    assert web_daten.web_chatzustand(lesend, token)["kalibrierung"] is None
    lesend.close()


@pytest.mark.parametrize("status,erwartet", [
    ("empfangen", "laufend"),
    ("transkribiert", "laufend"),
    ("fertig", "fertig"),
    ("fehlgeschlagen", "fehler"),
])
def test_zustand_meldet_den_kalibrierungs_upload_stand(datenbank, status, erwartet):
    pfad, token = datenbank
    schreibend = db.verbinde(pfad)
    aufnahme_id = repo.lege_aufnahme_an(
        schreibend, CHAT, 900, "kurz", "sprache", status=status, kalibrierung=True,
    )
    repo.setze_transkript(schreibend, aufnahme_id, "Ein Testsatz fuer die Kalibrierung.")
    repo.setze_status(schreibend, aufnahme_id, status)
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    stand = web_daten.web_chatzustand(lesend, token)["kalibrierung"]
    lesend.close()
    assert stand == {
        "message_id": 900, "status": erwartet,
        "transkript": "Ein Testsatz fuer die Kalibrierung.",
    }


def test_kalibrierungszeile_fehlt_im_chatverlauf_und_im_zustand(datenbank):
    """Item (g): eine ``web_post``-Zeile mit ``kalibrierung=1`` darf nie als
    gewoehnliche Chatblase erscheinen -- weder im Verlauf noch im Poll."""
    pfad, token = datenbank
    schreibend = db.verbinde(pfad)
    sichtbar_id = repo.lege_web_post_an(
        schreibend, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE, dauer=3,
    )
    kalibrierung_id = repo.lege_web_post_an(
        schreibend, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE, dauer=4,
        kalibrierung=True,
    )
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    verlauf_ids = {z["id"] for z in web_daten.web_chatverlauf(lesend, CHAT)}
    zustand_ids = {z["id"] for z in web_daten.web_chatzustand(lesend, token)["nachrichten"]}
    lesend.close()
    assert sichtbar_id in verlauf_ids
    assert kalibrierung_id not in verlauf_ids
    assert sichtbar_id in zustand_ids
    assert kalibrierung_id not in zustand_ids


# -- Routing --------------------------------------------------------------


@pytest.fixture
def server(datenbank):
    pfad, token = datenbank
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    import threading

    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad
    dienst.shutdown()


def _hole(url: str):
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def test_die_chatansicht_ist_erreichbar(server):
    basis, token, _pfad = server
    for url in (f"{basis}/g/{token}/chat", f"{basis}/theatersoap/g/{token}/chat"):
        status, text = _hole(url)
        assert status == 200
        assert "<!doctype html>" in text


def test_der_zustand_kommt_als_json(server):
    basis, token, _pfad = server
    status, text = _hole(f"{basis}/g/{token}/chat/zustand?nach=0")
    assert status == 200
    zustand = json.loads(text)
    assert zustand["chat_id"] == CHAT
    assert "nachrichten" in zustand


def test_unbekanntes_token_ist_404(server):
    basis, _token, _pfad = server
    for pfad in ("/g/gibtsnicht/chat", "/g/gibtsnicht/chat/zustand"):
        with pytest.raises(urllib.error.HTTPError) as fehler:
            _hole(basis + pfad)
        assert fehler.value.code == 404


def test_unbekannter_unterpfad_ist_404(server):
    basis, token, _pfad = server
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _hole(f"{basis}/g/{token}/chat/irgendwas")
    assert fehler.value.code == 404


def test_die_bestehenden_routen_leben_weiter(server):
    """E1 im Kleinen: die Gruppenseite, die Probenansicht und der Leitfaden
    duerfen durch das neue Routing nicht verschwinden."""
    basis, token, _pfad = server
    for pfad in ("", "/textbuch", "/leitfaden", "/textbuch.md"):
        status, _text = _hole(f"{basis}/g/{token}{pfad}")
        assert status == 200
    assert _hole(f"{basis}/gesund")[1].strip() == "ok"


def test_die_gruppenseite_verlinkt_den_chat(server):
    basis, token, _pfad = server
    _status, text = _hole(f"{basis}/g/{token}")
    assert f"{token}/{web_chat.CHAT_PFAD}" in text


def test_kein_transkript_und_kein_pfad_im_chat_html(server):
    """Dieselben drei Grenzen wie auf der Gruppenseite (AGENTS.md): kein
    Volltranskript, kein Dateipfad, kein unbelegtes Zitat -- die Ansicht ist
    ohne Login erreichbar."""
    basis, token, pfad = server
    schreibend = db.verbinde(pfad)
    repo.lege_web_post_an(schreibend, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
                          dauer=45, datei="/tmp/geheim/zwirbelkiste.webm",
                          mime="audio/webm")
    schreibend.close()
    _status, text = _hole(f"{basis}/g/{token}/chat")
    assert "zwirbelkiste" not in text.lower()
    assert "/tmp/" not in text


def test_der_chat_pfad_ist_in_skript_und_modul_derselbe():
    from scripts import web_gruppe

    assert web_gruppe.CHAT_PFAD == web_chat.CHAT_PFAD


# -- Aenderungen und Loeschungen im Poll (Review-Befund 10) -----------------


def _lies_zustand(pfad, token, nach=0, seit=None):
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        return web_daten.web_chatzustand(lesend, token, nach, seit)
    finally:
        lesend.close()


def test_aenderungszaehler_steigt_mit_jeder_aenderung(datenbank):
    """Ein Zaehler und keine Uhrzeit: SQLite serialisiert die Schreiber, der
    Wert ist deshalb in Commit-Reihenfolge aufsteigend -- ein Poll, der
    'alles nach N' fragt, verpasst nichts, was nach seinem Lesen kommt."""
    pfad, _token = datenbank
    conn = db.verbinde(pfad)
    a = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                              text="eins", knoepfe=[("Ja", "k:1")])
    b = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                              text="zwei")
    assert repo.hole_web_post(conn, a)["aenderung"] is None
    repo.aendere_web_text(conn, CHAT, a, "eins neu")
    erste = repo.hole_web_post(conn, a)["aenderung"]
    repo.setze_web_knoepfe(conn, CHAT, a, None)
    zweite = repo.hole_web_post(conn, a)["aenderung"]
    repo.loesche_web_posts(conn, CHAT, [b])
    dritte = repo.hole_web_post(conn, b)["aenderung"]
    conn.close()
    assert 0 < erste < zweite < dritte


def test_zustand_liefert_geaenderte_und_geloeschte_zeilen(datenbank):
    """``WebKanal.aendere_text``/``entferne_knoepfe``/``loesche_nachrichten``
    aendern Zeilen, die der Browser schon hat. Ohne diese Liste bliebe die
    Arbeitszeile stehen und eine ueberholte Leiste klickbar."""
    pfad, token = datenbank
    conn = db.verbinde(pfad)
    arbeit = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                   text="Ich schreibe ...")
    leiste = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                   text="Welche?", knoepfe=[("A", "k:1")])
    conn.close()

    vorher = _lies_zustand(pfad, token)
    assert vorher["geaendert"] == []
    stand = vorher["aenderung"]
    letzte = vorher["letzte"]

    conn = db.verbinde(pfad)
    repo.aendere_web_text(conn, CHAT, leiste, "Welche <b>jetzt</b>?")
    repo.setze_web_knoepfe(conn, CHAT, leiste, None)
    repo.loesche_web_posts(conn, CHAT, [arbeit])
    conn.close()

    danach = _lies_zustand(pfad, token, letzte, stand)
    nach_id = {z["id"]: z for z in danach["geaendert"]}
    assert set(nach_id) == {arbeit, leiste}
    assert nach_id[arbeit]["geloescht"] is True
    assert nach_id[leiste]["geloescht"] is False
    assert nach_id[leiste]["text"] == "Welche <b>jetzt</b>?"
    assert nach_id[leiste]["knoepfe"] == []
    assert danach["aenderung"] > stand
    assert danach["nachrichten"] == []

    # Wer den neuen Stand mitschickt, bekommt nichts doppelt.
    ruhig = _lies_zustand(pfad, token, letzte, danach["aenderung"])
    assert ruhig["geaendert"] == []
    assert ruhig["aenderung"] == danach["aenderung"]


def test_geaenderte_zeilen_fremder_gruppen_kommen_nicht_mit(datenbank):
    pfad, token = datenbank
    andere = CHAT + 1
    conn = db.verbinde(pfad)
    repo.sichere_gruppe(conn, andere, "gruppe2", "Andere")
    fremd = repo.lege_web_post_an(conn, andere, repo.RICHTUNG_AUS,
                                  repo.WEB_TYP_TEXT, text="fremd")
    repo.aendere_web_text(conn, andere, fremd, "fremd neu")
    conn.close()
    assert _lies_zustand(pfad, token, 0, 0)["geaendert"] == []


def test_der_poll_liefert_den_aktuellen_nonce_und_gefiltertes_html(server):
    """Review-Befund 2: die Chatseite laedt nie neu, ein Nonce gilt hoechstens
    zwei Stunden. Der Poll bringt deshalb den laufenden mit."""
    basis, token, pfad = server
    conn = db.verbinde(pfad)
    zeile = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                  text="alt")
    conn.close()
    _status, text = _hole(f"{basis}/g/{token}/chat/zustand?nach=0")
    zustand = json.loads(text)
    assert web.nonce_gueltig(b"x" * 32, token, zustand["nonce"])
    assert zustand["nonce"] == web.nonce(b"x" * 32, token)

    conn = db.verbinde(pfad)
    repo.aendere_web_text(conn, CHAT, zeile, "<script>x</script><b>neu</b>")
    conn.close()
    stand = zustand["aenderung"]
    _status, text = _hole(
        f"{basis}/g/{token}/chat/zustand?nach={zeile}&seit={stand}"
    )
    geaendert = json.loads(text)["geaendert"]
    assert [z["id"] for z in geaendert] == [zeile]
    assert "<script>" not in geaendert[0]["html"]
    assert "<b>neu</b>" in geaendert[0]["html"]


def test_die_seite_traegt_den_aenderungsstand(server):
    basis, token, pfad = server
    conn = db.verbinde(pfad)
    zeile = repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                                  text="a")
    repo.aendere_web_text(conn, CHAT, zeile, "b")
    stand = repo.hole_web_post(conn, zeile)["aenderung"]
    conn.close()
    _status, text = _hole(f"{basis}/g/{token}/chat")
    assert f'data-aenderung="{stand}"' in text


def test_chat_mit_schraegstrich_ist_404(server):
    """Review-Befund 12: unter ``/chat/`` zeigten die relativen Pfade der
    Seite (``chat/zustand``, der Link zur Gruppenseite) ins Leere."""
    basis, token, _pfad = server
    for pfad in (f"/g/{token}/chat/", f"/theatersoap/g/{token}/chat/",
                 f"/g/{token}/chat/zustand/"):
        with pytest.raises(urllib.error.HTTPError) as fehler:
            _hole(basis + pfad)
        assert fehler.value.code == 404, pfad
