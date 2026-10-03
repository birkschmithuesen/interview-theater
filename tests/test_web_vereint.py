"""Die vereinte Seite: drei Panels, ein Dokument, alte Adressen leben weiter.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_vereint_e2e.py``:
das Umschalten selbst, die Zurueck-Taste, der Strom im Browser. Hier steht,
was man am ausgelieferten HTML messen kann.
"""

import re
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_vereint

CHAT = 7_000_000_000_001

#: Eine zweite chat_id fuer die Telegram-Faelle (Fix-Runde 1, Befund 1).
CHAT_TELEGRAM = 7_000_000_000_002


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


@pytest.fixture
def aufbau_telegram(tmp_path):
    """Dieselbe Bauart wie ``aufbau``, aber OHNE ``setze_gruppe_kanal`` --
    die Gruppe bleibt auf dem Schema-Vorgabewert (Telegram) und hat deshalb
    keinen Chatzustand (``web_daten.web_chatzustand`` → ``None``,
    AGENTS.md "Abschlussreview I3"). Eigene Datenbank statt einer zweiten
    Gruppe in ``aufbau``, damit kein bestehender Test seine Destrukturierung
    aendern muss."""
    pfad = str(tmp_path / "t-telegram.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT_TELEGRAM, "gruppe2", "Die Gebliebenen")
    repo.setze_arbeitsstand(conn, CHAT_TELEGRAM, "begriffe", "Ankommen")
    repo.setze_arbeitsstand(conn, CHAT_TELEGRAM, "rahmen", "Hinterhof, tags")
    token = repo.stelle_web_token_sicher(conn, CHAT_TELEGRAM)
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


def _panel_tag(text: str, tab: str) -> str:
    """Das oeffnende ``<section>``-Tag genau dieses Panels, fuer Assertions
    auf seine eigenen Attribute statt irgendwo im Dokument."""
    treffer = re.search(rf'<section[^>]*id="tab-{tab}"[^>]*>', text)
    assert treffer is not None, f"kein Panel fuer Tab {tab!r}"
    return treffer.group(0)


def test_der_chat_ist_der_starttab(aufbau):
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert f'id="tab-{web_vereint.VORGABE_TAB}"' in text
    # Der Start-Tab selbst ist sichtbar -- die beiden anderen kommen
    # versteckt aus dem Server: ohne JS sieht man den Chat, und nicht drei
    # Seiten untereinander. Geprueft am Panel-Tag selbst, nicht irgendwo im
    # Dokument (sonst bewiese ein ``hidden`` in einem Formularfeld dasselbe).
    assert "hidden" not in _panel_tag(text, "chat")
    assert "hidden" in _panel_tag(text, "stand")
    assert "hidden" in _panel_tag(text, "textbuch")


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
    assert "data-textbuch" in _panel_tag(text, "textbuch")
    # Und NICHT am <body> -- sonst faerbte der Rollenfilter auch den Chat.
    body = re.search(r"<body[^>]*>", text)
    assert body is not None
    assert "data-textbuch" not in body.group(0)


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


# -- Telegram-Gruppen (kein Web-Kanal) --------------------------------------
#
# Fix-Runde 1, Befund 1: eine Gruppe ohne Web-Kanal hat keinen Bot, der
# ``web_post`` liest -- vor dem Fix bekam sie trotzdem das volle Chat-Panel
# samt Eingabefeld, Aufnahme-Umschalter und PTT-Knopf, deren POSTs und Polls
# alle 404 liefern (``web_chat._gruppe_oder_404``). Was die Gruppe dort
# eintippen wuerde, ginge spurlos verloren.


def test_telegram_gruppe_hat_kein_chat_panel(aufbau_telegram):
    basis, token, _pfad = aufbau_telegram
    status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert status == 200
    assert 'id="tab-chat"' not in text
    assert 'id="eingabe"' not in text
    assert 'id="interview"' not in text
    assert 'id="ptt"' not in text
    # Kein Chat-Tab in der Leiste, und kein Chat-Skript im Dokument.
    #
    # Aufgabe 6 (UX): ``web_gestalt.css_rahmen()`` haengt seit dieser Karte
    # IMMER (auch ohne Chat-Panel) die Regel
    # ``body:not([data-tab="chat"]) .fuss { display: none; }`` an -- eine
    # blosse Teilstring-Suche nach ``data-tab="chat"`` traefe also auch
    # diesen CSS-Selektor, der kein Markup ist und bei einer
    # Telegram-Gruppe (kein ``.fuss``-Element) wirkungslos bleibt. Geprueft
    # wird deshalb gegen den tatsaechlichen Knopf
    # (``_tabs_html``: ``data-tab="{tab}" aria-selected=...``), nicht gegen
    # die blosse Attributerwaehnung.
    assert 'data-tab="chat" aria-selected' not in text
    assert "warteschlange" not in text  # Marker aus web_chat._js()


def test_telegram_gruppe_startet_auf_dem_arbeitsstand(aufbau_telegram):
    basis, token, _pfad = aufbau_telegram
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert 'id="tab-stand"' in text
    assert "hidden" not in _panel_tag(text, "stand")
    assert 'id="tab-textbuch"' in text
    assert "hidden" in _panel_tag(text, "textbuch")
    # Die beiden anderen Panels tragen die Seite weiter.
    assert 'data-feld="rahmen"' in text
    # Das eingebettete TABS/VORGABE-Skript faellt automatisch auf "stand"
    # zurueck -- auch bei einem Fragment wie "#chat": "chat" steht gar
    # nicht mehr in der TABS-Liste, also greift in ``lies()`` der
    # Vorgabewert.
    assert "var VORGABE = 'stand';" in text
    assert '"chat"' not in text.split("var TABS = ", 1)[1].split(";", 1)[0]


def test_telegram_gruppe_hat_dennoch_arbeitsstand_und_textbuch(aufbau_telegram):
    """Die beiden Nachschlagewerke bleiben -- nur der Chat fehlt."""
    basis, token, _pfad = aufbau_telegram
    status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert status == 200
    assert "Ankommen" in text  # Begriffe, aus dem Stand-Panel
    for pfad in ("/textbuch", "/leitfaden"):
        assert _hole(f"{basis}/g/{token}{pfad}")[0] == 200, pfad


def test_web_gruppe_hat_weiterhin_das_volle_chat_panel(aufbau):
    """Gegenprobe: eine Web-Gruppe behaelt Chat-Tab und -Bedienelemente."""
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert 'id="tab-chat"' in text
    assert 'id="eingabe"' in text
    assert 'id="interview"' in text
    assert f'id="tab-{web_vereint.VORGABE_TAB}"' in text
    assert web_vereint.VORGABE_TAB == "chat"


# -- der Buehne-Tab (UX-Knoepfe-Karte, Abschnitt 5) ----------------------
#
# Seit dem Merge mit feat/brainstorm-vad wandert der dortige Stopgap
# ("Chat · Buehne", verschachtelt im Stand-Panel) hierher: ein echter,
# vierter Tab -- aber nur in Phase 4, sonst steht er gar nicht in ``TABS``.


def _tabs_liste(text: str) -> str:
    return text.split("var TABS = ", 1)[1].split(";", 1)[0]


def test_buehne_fehlt_ausserhalb_phase_4(aufbau):
    """Root-Cause-Fix (Birk, 02.10.2026): der Tab-Knopf UND sein Panel stehen
    jetzt IMMER im Dokument -- vorher fehlten sie ausserhalb Phase 4 ganz,
    und eine Gruppe, die WAEHREND die Seite offen war in Phase 4 eintrat,
    bekam den Tab nie, bis jemand von Hand neu lud. Verborgen wird seitdem
    ausschliesslich ueber ``hidden`` (serverseitig vorab, danach vom JS bei
    jedem Roadmap-Takt aus ``#roadmap``s ``data-aktive-phase`` nachgefuehrt).
    Im eingebetteten TABS-Array steht "buehne" deshalb ebenfalls immer --
    ein mitgebrachtes "#buehne" (alter Link) faellt in ``lies()`` trotzdem
    automatisch auf VORGABE zurueck, solange die Phase nicht 4 ist."""
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert 'data-tab="buehne"' in text
    assert 'id="tab-buehne"' in text
    assert "hidden" in _panel_tag(text, "buehne")
    knopf = re.search(r'<button[^>]*data-tab="buehne"[^>]*>', text)
    assert knopf is not None
    assert "hidden" in knopf.group(0)
    assert '"buehne"' in _tabs_liste(text)


def test_buehne_wird_ein_echter_tab_in_phase_4(aufbau):
    basis, token, pfad = aufbau
    conn = db.verbinde(pfad)
    repo.setze_phase(conn, CHAT, 4)
    conn.commit()
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert 'data-tab="buehne"' in text
    assert 'id="tab-buehne"' in text
    assert 'id="buehne-panel"' in text
    assert '"buehne"' in _tabs_liste(text)
    # Vierter Tab, nicht der Starttab: er steht verborgen neben Stand und
    # Textbuch, der Chat bleibt vorn.
    assert "hidden" in _panel_tag(text, "buehne")
    assert web_vereint.T._TEXT_TAB["buehne"] in text


def test_der_roadmap_takt_traegt_die_aktive_phase_fuer_die_tab_schaltung(aufbau):
    """``_VEREINT_JS`` schaltet den CoThinker-Tab (Knopf + Panel) bei jedem
    Nachlade-Takt allein anhand von ``#roadmap``s ``data-aktive-phase``
    (``istPhase4()``) -- ohne ein volles Neuladen der Seite. Das pruefen wir
    hier an der Quelle dieses Takts: ``GET /g/<token>/teil/roadmap`` muss die
    jeweils aktuelle Phase tragen, auch nachdem sich die Phase geaendert hat,
    waehrend die Seite schon offen war."""
    basis, token, pfad = aufbau
    conn = db.verbinde(pfad)

    _status, teil, _kopf = _hole(f"{basis}/g/{token}/teil/roadmap")
    treffer = re.search(r'id="roadmap" data-aktive-phase="(\d+)"', teil)
    assert treffer is not None
    assert treffer.group(1) != "4"

    repo.setze_phase(conn, CHAT, 4)
    conn.commit()
    _status, teil, _kopf = _hole(f"{basis}/g/{token}/teil/roadmap")
    treffer = re.search(r'id="roadmap" data-aktive-phase="(\d+)"', teil)
    assert treffer is not None
    assert treffer.group(1) == "4"


def test_buehne_bleibt_auch_fuer_eine_telegram_gruppe_erreichbar(aufbau_telegram):
    """Die Buehne haengt an der Phase, nicht am Kanal -- anders als der
    Chat-Tab (der ohne Web-Kanal ganz fehlt, siehe
    ``test_telegram_gruppe_hat_kein_chat_panel``)."""
    basis, token, pfad = aufbau_telegram
    conn = db.verbinde(pfad)
    repo.setze_phase(conn, CHAT_TELEGRAM, 4)
    conn.commit()
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert 'id="tab-buehne"' in text


# -- eine id="nonce" statt zwei -----------------------------------------

# Fix-Runde 1, Befund 2: Chat-Panel und Stand-Panel brachten je ein
# ``id="nonce"``-Element mit -- ungueltiges HTML. Das Chat-Panel bekommt
# seines seitdem nicht mehr (``mit_nonce=False``), das Stand-Panel behaelt
# seines unveraendert.


def test_nur_eine_nonce_id_in_der_vereinten_seite(aufbau):
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert text.count('id="nonce"') == 1


def test_chat_koerper_allein_traegt_weiterhin_eine_nonce(aufbau):
    """Die Chat-Einzelseite (``chat_html`` → ``chat_koerper`` ohne
    ``mit_nonce=False``) ist von der vereinten Seite unabhaengig und braucht
    ihr eigenes Feld weiterhin -- nur die vereinte Seite unterdrueckt es."""
    from interview_theater import web_chat
    text = web_chat.chat_koerper(
        {"interviewmodus": False, "nachrichten": [], "letzte": 0}, "n", "tok", 45_000,
    )
    assert text.count('id="nonce"') == 1


# -- "Zur Gruppenseite" nur, wo sie woanders hinfuehrt -----------------------

# Fix-Runde 1 (Aufgabe 16): auf der vereinten Seite (``/g/<token>``) zeigte
# der Link im Chat-Panel auf ``/g/<token>`` -- also auf die Seite, auf der er
# selbst stand. ``mit_gruppenlink=False`` unterdrueckt ihn dort. Die
# Chat-Einzelseite selbst ist seit derselben Karte nicht mehr per HTTP
# erreichbar -- ``/g/<token>/chat`` leitet schon weiter (siehe
# ``test_die_alte_chatadresse_leitet_auf_den_tab`` unten), die Vorgabe
# ``mit_gruppenlink=True`` von ``chat_koerper``/``chat_html`` bleibt als
# Funktion aber bestehen und wird in ``tests/test_web_koerper.py`` direkt
# geprueft (``test_mit_gruppenlink_schaltet_den_link_ab``).


def test_die_vereinte_seite_zeigt_keinen_link_auf_sich_selbst(aufbau):
    from interview_theater import web_chat
    basis, token, _pfad = aufbau
    _status, text, _kopf = _hole(f"{basis}/g/{token}")
    assert web_chat._TEXT_ZUR_GRUPPENSEITE not in text


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
