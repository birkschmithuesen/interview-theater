""""Was als Naechstes kommt" -- die zweite Kopfzeile, ohne Browser.

Birk (P2, Aufgabe 2, Punkt 2): "die wichtigen sachen auf einen blick" --
auf jedem Tab muss in zwei Sekunden klar sein, wo die Gruppe steht UND was
als Naechstes kommt. Wo sie steht, sagt die Aktzeile von Karte W; was als
Naechstes kommt, stand bis hierhin nur in der zugeklappten Aktfolge.

Die Zeile entsteht aus dem DOM (wie ``_JS_FORTSCHRITT``): die erste noch
nicht erledigte Aufgabe der aktiven Phase, sonst die naechste Phase, sonst
nichts. Kein neuer Endpunkt, kein Serverschluessel. Was der Browser daraus
macht, prueft ``tests/e2e/test_web_gestalt_e2e.py``.
"""

import re

import pytest

from interview_theater import sprache, web_gestalt

MODUS = 'html[data-ux-interview="1"]'


def _regeln(css: str) -> list[tuple[str, str]]:
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(s.strip(), k) for s, k in
            re.findall(r"([^{}]+)\{([^{}]*)\}", ohne_kommentare)]


def test_die_texte_kommen_aus_den_mikrotexten():
    texte = web_gestalt._mikrotexte()
    assert "{was}" in texte["naechstes"]
    assert "{bezeichnung}" in texte["naechste_phase"]
    assert "TEXTE.naechstes" in web_gestalt._JS_NAECHSTES
    assert "TEXTE.naechste_phase" in web_gestalt._JS_NAECHSTES


def test_die_englischen_texte_sind_uebersetzt(monkeypatch):
    monkeypatch.setattr(sprache, "code", lambda: "en")
    texte = web_gestalt._mikrotexte()
    assert texte["naechstes"] != web_gestalt._TEXT_NAECHSTES
    assert "{was}" in texte["naechstes"]
    assert "{bezeichnung}" in texte["naechste_phase"]


@pytest.mark.parametrize("mit_chat", [True, False])
def test_die_zeile_steht_mit_und_ohne_chat_im_skript(mit_chat):
    """Auch eine Telegram-Gruppe hat Arbeitsstand und Textbuch -- und dort
    gilt "auf einen Blick" genauso."""
    js = web_gestalt.skript(chat_vorhanden=mit_chat)
    assert "ux-naechstes" in js


def test_die_zeile_liest_nur_das_dom():
    baustein = web_gestalt._JS_NAECHSTES
    assert "el('roadmap')" in baustein
    assert ".phase.aktiv" in baustein
    assert ".aufgabe:not(.erledigt)" in baustein
    for verboten in ("fetch(", "XMLHttpRequest", "innerHTML", "setAttribute('style'"):
        assert verboten not in baustein, verboten
    # Den Austausch der Aktfolge (/teil/roadmap) muss sie ueberleben.
    assert "MutationObserver" in baustein


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_zeile_hat_ihre_regel_im_rahmen(name):
    """Im Rahmen und nicht im Chat-CSS: sie steht ueber allen Tabs."""
    regeln = _regeln(web_gestalt.css_rahmen(name))
    eigene = [k for s, k in regeln if s == "#ux-naechstes"]
    assert eigene
    assert any("text-overflow: ellipsis" in k for k in eigene)
    assert any(s == "#ux-naechstes[hidden]" and "display: none" in k
               for s, k in regeln)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_zeile_ist_im_interview_weg(name):
    versteckt = [s for s, k in _regeln(web_gestalt.css_interview(name))
                 if MODUS in s and "display: none" in k]
    assert any(t.strip().endswith("#ux-naechstes")
               for s in versteckt for t in s.split(",")), versteckt


def test_die_zeile_ist_im_ausdruck_weg():
    druck = re.search(r"@media print \{.*?\n\}", web_gestalt.css_rahmen(), re.S)
    assert druck and "#ux-naechstes" in druck.group(0)
