"""Das Bild-Overlay (Kanban-Karte t_abc12cf7, Task 2): die Telefon-
Organisationskarte (``.karte``, siehe ``tests/test_web_chat_karte.py``)
laesst sich antippen und oeffnet sich vollbildig mit Pinch-Zoom -- EIN
Markup fuer beide Seiten (Chat-Einzelseite UND vereinte Seite, siehe
``web_chat.chat_koerper``), kein zweites.

Was diese Datei NICHT leistet: ob ein echter Browser das Overlay wirklich
oeffnet/schliesst und das Bild laedt -- das prueft
``tests/e2e/test_web_chat_bildzoom_e2e.py``.
"""

from interview_theater import web_chat

_DATEN = {"titel": "Die Ankommenden", "nachrichten": [], "letzte": 0,
          "interviewmodus": False, "tippt": False, "antworten": {}}


def _koerper() -> str:
    return web_chat.chat_koerper(_DATEN, "nonce", "tok", 45_000)


def test_das_overlay_steht_einmal_im_koerper():
    koerper = _koerper()
    assert 'id="bild-overlay"' in koerper
    assert 'id="bild-overlay-img"' in koerper
    assert 'id="bild-overlay-schliessen"' in koerper


def test_das_overlay_ist_anfangs_versteckt():
    koerper = _koerper()
    anfang = koerper.index('id="bild-overlay"')
    tag = koerper[koerper.rindex("<", 0, anfang):koerper.index(">", anfang) + 1]
    assert "hidden" in tag


def test_das_overlay_bild_hat_kein_src_am_anfang():
    """Kein Bild haengt im Hintergrund, solange niemand getippt hat."""
    koerper = _koerper()
    anfang = koerper.index('id="bild-overlay-img"')
    tag = koerper[koerper.rindex("<", 0, anfang):koerper.index(">", anfang) + 1]
    assert 'src=""' in tag


def test_der_schliessen_knopf_ist_ein_knopf():
    koerper = _koerper()
    anfang = koerper.index('id="bild-overlay-schliessen"')
    tag = koerper[koerper.rindex("<", 0, anfang):koerper.index(">", anfang) + 1]
    assert tag.startswith("<button")


def test_css_sperrt_pinch_zoom_am_body_und_erlaubt_ihn_im_overlay():
    css = web_chat._CSS_CHAT
    assert "touch-action: pan-x pan-y" in css
    assert "touch-action: pinch-zoom" in css
    # Beide neuen Stellen (Overlay-Huelle UND Bild) tragen das Gegenstueck
    # zur Sperre am body -- zwei Treffer, nicht nur einer.
    assert css.count("touch-action: pinch-zoom") >= 2


def test_das_overlay_ist_ein_vollbild_ohne_vw_vh():
    css = web_chat._CSS_CHAT
    block = css[css.index(".bild-overlay {"):css.index(".bild-overlay[hidden]")]
    assert "inset: 0" in block
    assert "vw" not in block
    assert "vh" not in block


def test_js_enthaelt_die_overlay_funktionen():
    js = web_chat._js()
    assert "function oeffneBildOverlay" in js
    assert "function schliesseBildOverlay" in js


def test_js_oeffnet_das_overlay_per_delegiertem_klick_auf_die_karte():
    js = web_chat._CHAT_JS
    assert "closest" in js
    assert "img.karte" in js


def test_js_nutzt_history_fuer_die_zurueck_geste():
    js = web_chat._CHAT_JS
    funktion = js[js.index("function oeffneBildOverlay"):
                  js.index("function schliesseBildOverlay")]
    assert "history.pushState" in funktion
    schliessen = js[js.index("function schliesseBildOverlay"):]
    schliessen = schliessen[:schliessen.index("\n  }\n") + len("\n  }\n")]
    assert "history.back()" in schliessen
    assert "popstate" in js
