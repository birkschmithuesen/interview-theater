"""Die vereinte Seite: drei Panels, ein Dokument, alte Adressen leben weiter.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_vereint_e2e.py``:
das Umschalten selbst, die Zurueck-Taste, der Strom im Browser. Hier steht,
was man am ausgelieferten HTML messen kann.
"""

import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_vereint

CHAT = 7_000_000_000_001


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Arbeit")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


def _hole(url, folge=True):
    class OhneUmleitung(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):
            return None

    oeffner = (urllib.request.build_opener()
               if folge else urllib.request.build_opener(OhneUmleitung))
    try:
        with oeffner.open(url, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8"), antwort.headers
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8"), fehler.headers


# -- scope_css --------------------------------------------------------------


@pytest.mark.parametrize("css,erwartet", [
    ("body { color: red; }", ".p { color: red; }"),
    ("h1 { font-size: 2rem; }", ".p h1 { font-size: 2rem; }"),
    (".leiste button { color: blue; }", ".p .leiste button { color: blue; }"),
    ("body[data-figur] .replik { opacity: .4; }",
     ".p[data-figur] .replik { opacity: .4; }"),
    ("body.ohne-regie .regie { display: none; }",
     ".p.ohne-regie .regie { display: none; }"),
    ("a, b { color: red; }", ".p a, .p b { color: red; }"),
])
def test_scope_schraenkt_jeden_selektor_ein(css, erwartet):
    assert web_vereint.scope_css(css, ".p").strip() == erwartet.strip()


def test_scope_laesst_media_bloecke_stehen_und_schraenkt_darin_ein():
    css = "@media (prefers-color-scheme: dark) { body { color: #fff; } }"
    ergebnis = web_vereint.scope_css(css, ".p")
    assert "@media (prefers-color-scheme: dark)" in ergebnis
    assert ".p { color: #fff; }" in ergebnis.replace("\n", " ")


def test_scope_laesst_kommentare_unangetastet():
    assert "/* ein Wort */" in web_vereint.scope_css("/* ein Wort */\nbody{a:b}", ".p")


def test_die_leiste_der_probenansicht_kollidiert_nicht_mehr():
    """Gemessen am 30.09.2026: ``.leiste`` heisst in ``_CSS_TEXTBUCH`` die
    Rollenleiste und in ``_CSS_CHAT`` die Knopfleiste."""
    textbuch = web_vereint.scope_css(web._CSS_TEXTBUCH, ".panel-textbuch")
    assert "\n.leiste" not in "\n" + textbuch
    assert ".panel-textbuch .leiste" in textbuch


# -- die Seite --------------------------------------------------------------


def test_die_drei_panels_stehen_in_einem_dokument(aufbau):
    basis, token, _pfad = aufbau
    status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert status == 200
    assert text.count("<!doctype html>") == 1
    for tab in web_vereint.TABS:
        assert f'id="tab-{tab}"' in text, tab


def test_der_chat_ist_der_starttab(aufbau):
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert f'id="tab-{web_vereint.VORGABE_TAB}"' in text
    # Die beiden anderen kommen versteckt aus dem Server: ohne JS sieht man
    # den Chat, und nicht drei Seiten untereinander.
    assert text.count("hidden") >= 2


def test_der_arbeitsstand_traegt_seine_formulare(aufbau):
    """Das Stand-Panel IST die Gruppenseite -- Nonce und Felder inklusive."""
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert 'id="nonce"' in text
    assert 'data-feld="rahmen"' in text


def test_das_textbuch_panel_traegt_seinen_zustand_am_panel(aufbau):
    """Die Probenansicht haengt ihren Zustand heute an ``document.body``. Im
    gemeinsamen Dokument geht das nicht -- sonst faerbte der Rollenfilter
    auch den Chat."""
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert "data-textbuch" in text


def test_die_seite_laedt_sich_nicht_selbst_neu(aufbau):
    """``_SCROLL_JS`` tauscht ``document.body.innerHTML`` alle zehn Sekunden --
    das wuerde Chat, Aufnahme und Strom mitreissen."""
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert "document.body.innerHTML = neu" not in text


def test_die_grenzen_gelten_auch_vereint(aufbau):
    """Die vereinte Seite darf nicht mehr ausliefern als ihre drei Quellen
    einzeln: kein Transkript, kein Dateipfad, kein ungeprueftes Zitat."""
    basis, token, pfad = aufbau
    schreibend = db.verbinde(pfad)
    aufnahme_id = repo.lege_aufnahme_an(schreibend, CHAT, 9, "lang", "sprache",
                                        "/tmp/geheim/zwirbelkiste.ogg", 200)
    repo.speichere_verdichtung(
        schreibend, CHAT, aufnahme_id, "Kurz erzaehlt",
        [{"thema": "Arbeit", "beleg_zitat": "so hat das niemand gesagt",
          "zitat_geprueft": 0}],
    )
    schreibend.commit()
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert "zwirbelkiste" not in text.lower()
    assert "/tmp/" not in text
    assert "so hat das niemand gesagt" not in text


# -- alte Adressen ----------------------------------------------------------


def test_die_probenansicht_bleibt_eine_eigene_seite(aufbau):
    """Gedruckte QR-Codes und geteilte Rollenlinks duerfen nicht sterben --
    und ``@media print`` braucht eine Seite fuer sich."""
    basis, token, _pfad = aufbau
    for pfad in ("/textbuch", "/textbuch.md", "/textbuch.txt", "/leitfaden"):
        status, _text, _kopf = _hole(f"{basis}/g/{token}{pfad}")
        assert status == 200, pfad


def test_die_alte_chatadresse_leitet_auf_den_tab(aufbau):
    basis, token, _pfad = aufbau
    status, _text, kopf = _hole(f"{basis}/g/{token}/chat", folge=False)
    assert status == 302
    assert kopf["Location"].endswith(f"/g/{token}#chat")


def test_alles_greift_auch_unter_dem_praefix(aufbau):
    basis, token, _pfad = aufbau
    for pfad in ("", "/textbuch", "/leitfaden"):
        assert _hole(f"{basis}/theatersoap/g/{token}{pfad}")[0] == 200
    status, _text, kopf = _hole(f"{basis}/theatersoap/g/{token}/chat", folge=False)
    assert status == 302 and kopf["Location"].startswith("/theatersoap/")


def test_unbekannter_unterpfad_bleibt_404(aufbau):
    basis, token, _pfad = aufbau
    assert _hole(f"{basis}/g/{token}/quatsch")[0] == 404


def test_unbekanntes_token_ist_404(aufbau):
    basis, _token, _pfad = aufbau
    assert _hole(f"{basis}/g/gibtsnicht")[0] == 404


def test_das_dashboard_bleibt_wie_es_war(aufbau):
    """Es haengt am Beamer, es ist nicht diese Karte."""
    basis, _token, _pfad = aufbau
    status, text, _kopf = _hole(f"{basis}/")
    assert status == 200 and "Arbeitsstand aller Gruppen" in text


# -- das JS der Tabs --------------------------------------------------------


def test_das_tab_js_haengt_an_hashchange():
    """Ohne ``hashchange`` wechselt die Zurueck-Taste des Handys den Tab nicht."""
    assert "hashchange" in web_vereint._VEREINT_JS


def test_das_tab_js_schaltet_nur_hidden_um():
    """Ein Seitenwechsel riesse Aufnahme, Eingabefeld und Strom mit."""
    assert "hidden" in web_vereint._VEREINT_JS
    assert "location.href =" not in web_vereint._VEREINT_JS
    assert "location.reload" not in web_vereint._VEREINT_JS
