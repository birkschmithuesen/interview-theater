"""Die Statuspunkte der read-only Werkbank (Padua, 03.10.2026): Form und Farbe
tragen den Zustand, jede Farbe haelt 3:1 (WCAG 1.4.11), kein Emoji."""

import re

import pytest

from interview_theater import web_gestalt

PUNKTE = {
    ("signal", "grund"), ("warn", "grund"), ("text-leise", "grund"),
    ("signal", "grund-2"), ("warn", "grund-2"), ("text-leise", "grund-2"),
    ("auf-signal", "signal"),
}


def _regel(css: str, selektor: str) -> str:
    treffer = re.search(re.escape(selektor) + r"\s*\{([^}]*)\}", css)
    assert treffer, selektor
    return treffer.group(1)


def test_die_statuspunkte_stehen_in_der_kontrasttabelle():
    paare = {(p.vorn, p.hinten) for p in web_gestalt.KONTRAST
             if p.zweck.startswith("Werkbank") and p.mindest >= 3.0}
    assert PUNKTE <= paare


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_jeder_statuspunkt_haelt_drei_zu_eins(name):
    tokens = web_gestalt.TOKENS[name]
    for vorn, hinten in PUNKTE:
        assert web_gestalt.kontrastverhaeltnis(tokens[vorn], tokens[hinten]) >= 3.0, (vorn, hinten)


def test_die_form_traegt_den_zustand_nicht_nur_die_farbe():
    css = web_gestalt.css_werkbank()
    erledigt = _regel(css, ".wb-punkt.wb-erledigt")
    offen = _regel(css, ".wb-punkt.wb-offen")
    spaeter = _regel(css, ".wb-punkt.wb-spaeter")
    assert "background: var(--signal)" in erledigt
    assert "transparent" in offen and "solid var(--warn)" in offen
    assert "transparent" in spaeter and "dashed var(--text-leise)" in spaeter
    assert '"✓"' in _regel(css, ".wb-punkt.wb-erledigt::after")


def test_der_zaehler_ist_leise():
    assert "var(--text-leise)" in _regel(web_gestalt.css_werkbank(), ".wb-zahl")


def test_ohne_media_keyframes_und_fremdquelle():
    css = web_gestalt.css_werkbank()
    for verboten in ("@media", "@keyframes", "@import", "@font-face", "url("):
        assert verboten not in css


def test_ohne_ampel_emoji():
    css = web_gestalt.css_werkbank()
    for zeichen in ("🟢", "🔴", "⚪", "🟡"):
        assert zeichen not in css


def test_fuer_beide_entwuerfe_gleich():
    assert web_gestalt.css_werkbank("a") == web_gestalt.css_werkbank("b")
