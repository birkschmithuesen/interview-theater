"""Worauf die UX-Karte steht: A1, A2, W und S muessen in ``main`` sein.

Diese Karte gestaltet, was andere Karten bauen. Faellt hier etwas aus,
BRICHT die Umsetzung ab und meldet genau das -- A2 oder W nachzubauen
waere teurer als ein Wartetag, und zwei Fassungen von ``web_vereint.py``
waeren der teuerste Fehler dieser Kette.

Der Test ist absichtlich stumpf: er prueft Namen, nicht Verhalten. Das
Verhalten pruefen die Tests der jeweiligen Karte.
"""

import pytest

from interview_theater import sprache, web, web_chat, web_vereint


@pytest.mark.parametrize("name", ["Texte", "code", "text"])
def test_a1_sprache_ist_da(name):
    assert hasattr(sprache, name), f"A1 fehlt: sprache.{name}"


@pytest.mark.parametrize("name", [
    "CSP_VORLAGE", "mit_nonce", "csp_nonce",          # Karte S
    "_seite", "textbuch_html", "leitfaden_html",      # heute schon da
    "_CSS_TEXTBUCH", "_TEXTBUCH_JS",
])
def test_web_flaeche_ist_da(name):
    assert hasattr(web, name), f"fehlt: web.{name}"


@pytest.mark.parametrize("name", ["_CSS_CHAT", "CHAT_PFAD"])
def test_a2_chatansicht_ist_da(name):
    assert hasattr(web_chat, name), f"A2 fehlt: web_chat.{name}"


@pytest.mark.parametrize("name", [
    "seite", "scope_css", "TABS", "_CSS_VEREINT",
    "_tabs_html", "_leiste_html", "_VEREINT_JS", "_STROM_JS",
])
def test_w_vereinte_seite_ist_da(name):
    assert hasattr(web_vereint, name), f"W fehlt: web_vereint.{name}"


def test_die_csp_hat_kein_font_src():
    """Der Grund, warum diese Karte keinen Webfont einbettet: die
    Richtlinie hat ``default-src 'none'`` und kein ``font-src``. Ein
    ``@font-face`` -- auch mit ``data:``-URL -- waere geblockt."""
    assert "default-src 'none'" in web.CSP_VORLAGE
    assert "font-src" not in web.CSP_VORLAGE


def test_die_csp_erlaubt_kein_unsafe_inline():
    """Deshalb kein ``style="…"``-Attribut und kein ``on…=``-Handler --
    und deshalb CSSOM fuer dynamische Werte."""
    assert "'unsafe-inline'" not in web.CSP_VORLAGE
    assert "'nonce-{nonce}'" in web.CSP_VORLAGE
