"""Das CSS der Gestaltung: was drinstehen muss und was nie drinstehen darf.

Drei Vertraege, alle am Text der Konstanten gemessen und ohne Browser:

1. Keine Fremdquelle, kein Webfont -- die CSP aus Karte S hat
   ``default-src 'none'`` und kein ``font-src``.
2. ``prefers-reduced-motion: reduce`` legt JEDE Animation und JEDEN
   Uebergang des Moduls still, und zwar die, die es wirklich gibt: der
   Test sammelt die Selektoren aus dem CSS selbst, statt einer Liste zu
   glauben.
3. ``@keyframes`` und ``@media`` stehen nur im ungescopten Teil --
   ``web_vereint.scope_css`` machte aus dem Rumpf eines ``@keyframes``
   sonst eine gescopte Regel (``.panel-chat 50% { … }``).
"""

import re

import pytest

from interview_theater import web_gestalt, web_vereint

GESCOPT = ("css_chat", "css_stand", "css_textbuch")
ALLE = ("css_rahmen",) + GESCOPT


def _css(funktion: str, name: str) -> str:
    return getattr(web_gestalt, funktion)(name)


def _ganzes_css(name: str) -> str:
    return "".join(_css(f, name) for f in ALLE)


# -- 1. Keine Fremdquelle ----------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
@pytest.mark.parametrize("verboten", ["http://", "https://", "@font-face", "@import"])
def test_kein_fremdes_in_der_gestaltung(name, verboten):
    assert verboten not in _ganzes_css(name), verboten


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_keine_url_ueberhaupt(name):
    """Heute braucht die Gestaltung kein einziges ``url()``: Verlaeufe und
    Zeichen kommen aus CSS und aus Unicode. Auch ``//example.org/x.css``
    waere eine Fremdquelle und sieht im Diff aus wie ein Kommentar. Wer
    ein ``url()`` einfuehrt, faellt hier auf und traegt die CSP-Folge
    (``img-src 'self' data:``) im Commit nach."""
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", _ganzes_css(name), flags=re.S)
    assert "url(" not in ohne_kommentare


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_schriften_sind_systemstacks(name):
    for schluessel in ("schrift-lesen", "schrift-tech", "schrift-skript"):
        wert = web_gestalt.TOKENS[name][schluessel]
        assert wert.rstrip().endswith(("monospace", "serif", "sans-serif")), wert


# -- 2. prefers-reduced-motion ----------------------------------------------


def _bewegte_selektoren(css: str) -> set[str]:
    """Jeder Selektor, der ``animation``/``transition`` erklaert -- ohne
    den reduced-motion-Block selbst und ohne die Keyframe-Rumpfe."""
    ohne_ruhig = re.sub(
        r"@media\s*\(prefers-reduced-motion[^{]*\{.*?\n\}", "", css, flags=re.S)
    ohne_keyframes = re.sub(r"@keyframes[^{]*\{.*?\n\}", "", ohne_ruhig, flags=re.S)
    treffer = set()
    for selektoren, koerper in re.findall(r"([^{}]+)\{([^{}]*)\}", ohne_keyframes):
        if not re.search(r"\b(animation|transition)\b\s*:", koerper):
            continue
        for einer in selektoren.split(","):
            if einer.strip() and not einer.strip().startswith("@"):
                treffer.add(einer.strip())
    return treffer


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_es_gibt_ueberhaupt_bewegung_zum_abschalten(name):
    """Ein Test, der eine leere Menge prueft, prueft nichts."""
    assert _bewegte_selektoren(_ganzes_css(name))


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_reduzierte_bewegung_legt_jeden_bewegten_selektor_stumm(name):
    css = _ganzes_css(name)
    block = re.search(
        r"@media\s*\(prefers-reduced-motion[^{]*\{(.*?)\n\}", css, flags=re.S)
    assert block, "kein reduced-motion-Block"
    ruhig = block.group(1)
    fehlen = [s for s in _bewegte_selektoren(css) if s not in ruhig]
    assert not fehlen, fehlen


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_block_setzt_animation_und_transition_auf_none(name):
    block = re.search(
        r"@media\s*\(prefers-reduced-motion[^{]*\{(.*?)\n\}",
        _ganzes_css(name), flags=re.S).group(1)
    assert "animation: none !important" in block
    assert "transition: none !important" in block


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_block_legt_auch_die_bewegung_aus_a2_und_w_still(name):
    """``.blase.vorlaeufig::after`` (der Strom-Cursor aus Karte W) ist
    GESCOPT und damit spezifischer als alles hier -- ohne ``!important``
    und ohne ausdrueckliche Nennung blinkte er weiter."""
    block = re.search(
        r"@media\s*\(prefers-reduced-motion[^{]*\{(.*?)\n\}",
        _ganzes_css(name), flags=re.S).group(1)
    assert ".blase.vorlaeufig::after" in block


def test_bewegt_und_das_css_sagen_dasselbe():
    """``BEWEGT`` ist die Liste im Code, der Test oben liest das CSS.
    Laufen beide auseinander, ist die Liste die Luege."""
    for name in web_gestalt.ENTWUERFE:
        block = re.search(
            r"@media\s*\(prefers-reduced-motion[^{]*\{(.*?)\n\}",
            _ganzes_css(name), flags=re.S).group(1)
        for selektor in web_gestalt.BEWEGT:
            assert selektor in block, selektor


# -- 3. Was scope_css nicht vertraegt ---------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
@pytest.mark.parametrize("funktion", GESCOPT)
def test_kein_keyframes_und_kein_media_im_gescopten_teil(name, funktion):
    assert "@keyframes" not in _css(funktion, name)
    assert "@media" not in _css(funktion, name)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_jede_benutzte_animation_ist_auch_definiert(name):
    css = _ganzes_css(name)
    definiert = set(re.findall(r"@keyframes\s+([\w-]+)", css))
    benutzt = {t for t in re.findall(r"animation:\s*([\w-]+)", css) if t != "none"}
    assert benutzt <= definiert, benutzt - definiert
    assert set(web_gestalt.KEYFRAMES) == definiert


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_gescopte_teil_ueberlebt_scope_css(name):
    """Der eigentliche Beweis: durch dieselbe Funktion schicken, die der
    Aufrufer benutzt, und nachsehen, dass nichts zerfaellt."""
    for funktion, scope in (("css_chat", ".panel-chat"),
                            ("css_stand", ".panel-stand"),
                            ("css_textbuch", ".panel-textbuch")):
        ergebnis = web_vereint.scope_css(_css(funktion, name), scope)
        assert ergebnis.count("{") == ergebnis.count("}")
        # Kein Rumpf-Fragment ist zu einem Selektor geworden.
        assert not re.search(r"\.panel-\w+ \d+%", ergebnis)


# -- 4. Tokens werden benutzt, nicht umgangen -------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_keine_rohe_hexfarbe_ausserhalb_des_tokenblocks(name):
    """Sonst waere der Entwurfstausch kein Tausch. Ausgenommen ist
    ``@media print``: der Ausdruck ist bewusst nicht themenfaehig, er ist
    IMMER hell."""
    css = _ganzes_css(name)
    ohne_tokens = css.replace(web_gestalt.tokens_css(name), "")
    ohne_druck = re.sub(r"@media\s+print\s*\{.*?\n\}", "", ohne_tokens, flags=re.S)
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", ohne_druck, flags=re.S)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", ohne_kommentare)
