"""Der Interview-Modus der Gestaltung -- ohne Browser.

Birk (P2, Aufgabe 2): "endgeraet mobile. wichtig: interviews sauber
durchfuehren ohne ablenkung." Waehrend DIESES Telefon ein Interview
aufnimmt, zeigt die Seite nur noch Zustand, Dauer, Pegel, Stopp (und auf
Wunsch den Leitfaden). Was der Browser davon wirklich tut, prueft
``tests/e2e/test_web_gestalt_e2e.py``; hier steht, was man am
ausgelieferten CSS und JS messen kann.
"""

import re

import pytest

from interview_theater import sprache, web_gestalt

MODUS = 'html[data-ux-interview="1"]'


def _regeln(css: str) -> list[tuple[str, str]]:
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.findall(r"([^{}]+)\{([^{}]*)\}", ohne_kommentare)


def _im_modus(name: str) -> list[tuple[str, str]]:
    """Jede Regel, deren Selektor am Interview-Modus haengt."""
    return [(s.strip(), k) for s, k in _regeln(web_gestalt.css_interview(name))
            if MODUS in s]


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
@pytest.mark.parametrize("ziel", [
    "#roadmap",            # die Phasenleiste
    ".tabs",               # die Tableiste
    "#ux-belohnung",       # die Belohnung
    "#ux-vorhang",         # der Akt-Moment
    "#ux-ansage",
    "#verlauf",            # der bewegte Chatverlauf
    "#tippt",
    ".zeile",              # Eingabe, PTT, Senden
])
def test_im_interview_ist_die_ablenkung_weg(name, ziel):
    treffer = [k for s, k in _im_modus(name)
               if any(t.strip().endswith(ziel) for t in s.split(","))]
    assert treffer, ziel
    assert any("display: none" in k for k in treffer), ziel


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_im_interview_laeuft_keine_animation(name):
    """Keine Animation des Moduls darf im Interview-Zustand laufen -- und
    keine Regel des Modus startet selbst eine."""
    for selektor, koerper in _im_modus(name):
        # (Der reduced-motion-Block nennt dieselben Selektoren mit
        # ``none !important`` -- auch das ist "keine".)
        for wert in re.findall(r"animation:\s*([^;]+)", koerper):
            assert wert.replace("!important", "").strip() == "none", (selektor, wert)
        for wert in re.findall(r"transition:\s*([^;]+)", koerper):
            assert wert.replace("!important", "").strip() == "none", (selektor, wert)
    stumm = " ".join(s for s, k in _im_modus(name) if "animation: none" in k)
    for ziel in ("#interview", "#pegel span", "#ux-rec-zeile"):
        assert ziel in stumm, ziel


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_im_interview_bleibt_der_stopp_und_ist_der_hauptknopf(name):
    regeln = dict(_im_modus(name))
    beenden = [k for s, k in regeln.items() if s.endswith("#interview-beenden")]
    assert beenden
    assert any("min-height" in k for k in beenden)
    assert any("var(--rec)" in k for k in beenden)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_im_interview_ist_der_chat_immer_sichtbar(name):
    """Sonst stuende nach einem Zurueck-Wischen (Hash -> anderer Tab) ein
    Telefon ohne Stopp-Knopf und ohne Tableiste da."""
    sel = " ".join(s for s, k in _im_modus(name) if "display: block" in k)
    assert "#tab-chat" in sel
    versteckt = " ".join(s for s, k in _im_modus(name) if "display: none" in k)
    assert ".panel:not(#tab-chat)" in versteckt


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_modus_steht_in_bewegt(name):
    """Was der Modus stilllegt, steht auch im reduced-motion-Block (der
    Test in ``test_web_gestalt_css`` verlangt das fuer jede Regel mit
    ``animation:``)."""
    for selektor, koerper in _im_modus(name):
        if re.search(r"\b(animation|transition)\b\s*:", koerper):
            for einer in selektor.split(","):
                assert einer.strip() in web_gestalt.BEWEGT, einer


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_modus_steht_nicht_im_rahmen(name):
    """``css_rahmen()`` geht auch an die Probenansicht und an Telegram-
    Gruppen -- dort hat Chat-CSS nichts zu suchen
    (``test_telegram_gruppe_hat_kein_chat_panel``,
    ``test_kein_material_in_der_probenansicht``)."""
    rahmen = web_gestalt.css_rahmen(name)
    assert "#interview-beenden" not in rahmen
    assert "warteschlange" not in rahmen
    assert "Interview" not in rahmen


def test_die_vereinte_seite_haengt_den_modus_nur_mit_chat_an(tmp_path):
    """Am ausgelieferten HTML gemessen, nicht am Quelltext: eine Web-Gruppe
    bekommt das Modus-CSS, eine Telegram-Gruppe (kein Chat-Panel) nicht."""
    import threading
    import urllib.request

    from interview_theater import db, repo, web

    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 7_000_000_000_011, "gruppe1", "Mit Chat")
    repo.setze_gruppe_kanal(conn, 7_000_000_000_011, "web")
    repo.sichere_gruppe(conn, -1001, "gruppe2", "Ohne Chat")
    mit = repo.stelle_web_token_sicher(conn, 7_000_000_000_011)
    ohne = repo.stelle_web_token_sicher(conn, -1001)
    conn.commit()
    conn.close()
    server = web.baue_server(pfad, "127.0.0.1:0", "", schluessel=b"x" * 32)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        basis = f"http://127.0.0.1:{server.server_address[1]}"
        def hole(token):
            with urllib.request.urlopen(f"{basis}/g/{token}", timeout=5) as a:
                return a.read().decode("utf-8")
        mit_html, ohne_html = hole(mit), hole(ohne)
    finally:
        server.shutdown()
    # (``MODUS`` allein steht auch im reduced-motion-Block des Rahmens --
    # gemessen wird an Regeln, die nur ``css_interview()`` hat.)
    for nur_modus in (f"{MODUS} #interview-beenden", f"{MODUS} .tabs"):
        assert nur_modus in mit_html, nur_modus
        assert nur_modus not in ohne_html, nur_modus
    assert "wakeLock" in mit_html
    assert "wakeLock" not in ohne_html


# -- Das Skript --------------------------------------------------------------


@pytest.fixture(params=web_gestalt.ENTWUERFE)
def js(request):
    return web_gestalt.skript(request.param)


def test_das_skript_setzt_den_modus_an_der_wurzel(js):
    assert "document.documentElement" in js
    assert "data-ux-interview" in js


def test_der_modus_haengt_an_uhr_und_interview_nicht_an_ptt(js):
    """PTT ist kein Interview. Erkannt wird ein laufendes Interview an
    ``data-interview`` UND an der sichtbaren Uhr -- die zeigt _CHAT_JS nur,
    wenn DIESES Telefon aufnimmt (ein anderes Telefon, das den Modus
    haelt, laesst sie verborgen)."""
    baustein = web_gestalt._JS_INTERVIEW
    # Die eine Bedingung, an der der Modus haengt -- beide Haelften.
    assert re.search(
        r"var an = fuss\.dataset\.interview === '1' && !uhr\.hidden;", baustein)
    # Beobachtet wird genau das, woraus die Bedingung besteht.
    assert "attributeFilter: ['data-interview']" in baustein
    assert "uhr, { attributes: true, attributeFilter: ['hidden'] }" in baustein
    # Kein Weg ueber Push-to-Talk (Knopf, Ereignisse, Zustand).
    assert "ptt" not in baustein.lower()
    assert "pointerdown" not in baustein


def test_wake_lock_ist_feature_detected_und_wirft_nie(js):
    baustein = web_gestalt._JS_INTERVIEW
    assert "'wakeLock' in navigator" in baustein
    assert "request('screen')" in baustein
    assert ".release()" in baustein
    assert "visibilitychange" in baustein
    assert "try {" in baustein and "catch" in baustein


def test_ohne_chat_kein_interview_baustein():
    """Telegram-Gruppe: kein Chat-Panel, also auch nicht die Namen seiner
    Elemente im Skript (``test_telegram_gruppe_hat_kein_chat_panel``)."""
    ohne = web_gestalt.skript(chat_vorhanden=False)
    assert "wakeLock" not in ohne
    assert "data-ux-interview" not in ohne


def test_das_skript_schreibt_nie_in_den_interview_knopf():
    assert "interview').textContent" not in web_gestalt._JS_INTERVIEW
    assert "knopf.textContent" not in web_gestalt._JS_INTERVIEW


def test_die_belohnung_nach_dem_interview_kommt_ohne_auftritt():
    """Effekte nur beim Phasenwechsel -- die Bestaetigung "Interview ist
    drin" ist Information und kommt ruhig."""
    css = web_gestalt.css_rahmen()
    assert re.search(
        r'#ux-belohnung\[data-art="aufnahme"\][^{]*\{[^}]*animation: none', css)
    assert "dataset.art" in web_gestalt._JS_MOMENT


# -- Mikrotexte --------------------------------------------------------------


def test_die_pause_hat_einen_eigenen_text():
    """"Aufnahme laeuft." waehrend einer Pause ist falsch -- und ein
    falscher Zustand ist genau, was in Dortmund 14 Drucke kostete."""
    texte = web_gestalt._mikrotexte()
    assert texte["rec_pausiert"] and texte["rec_pausiert"] != texte["rec_laeuft"]
    assert "rec_pausiert" in web_gestalt._JS_AUFNAHME
    assert texte["leitfaden"]


def test_die_englischen_texte_nennen_keine_position(monkeypatch):
    """Der Stopp steht neben dem Kreis, nicht darunter, und ist im
    Ruhezustand gar nicht sichtbar -- der deutsche Text sagt keine Lage,
    der englische darf es auch nicht."""
    monkeypatch.setattr(sprache, "code", lambda: "en")
    texte = web_gestalt._mikrotexte()
    for wort in ("below", "above", "underneath"):
        assert wort not in texte["rec_ruht"].lower()
    assert texte["rec_pausiert"] != web_gestalt._TEXT_REC_PAUSIERT
    assert texte["leitfaden"] != web_gestalt._TEXT_LEITFADEN
