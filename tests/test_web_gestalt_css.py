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


# -- 5. Buehnenlichter (Entwurf B) gegen die Kaskade -------------------------
#
# Review-Befund an Aufgabe 7: ``_TABS_B`` und ``_ROADMAP`` definieren
# beide ``#ux-balken``/``#ux-balken i``, und ``_ROADMAP`` steht in
# ``css_rahmen()`` NACH den Tabs. Bei gleicher Spezifitaet gewinnt in CSS
# die spaetere Regel -- also ``_ROADMAP``, egal was in ``_TABS_B`` steht.
# Der Fix erhoeht die Spezifitaet der B-Regeln (``.roadmap``-Praefix), und
# genau DAS pruefen die Tests hier -- nicht nur, dass ein Text irgendwo
# vorkommt, sondern dass die B-Regel bei einer echten Spezifitaetsrechnung
# gewinnt. Ein kuenftiger Fall, der die Praefixe wieder entfernt oder die
# Konkatenationsreihenfolge umdreht, faellt damit auf, weil die Rechnung
# selbst erneut gemacht wird -- nicht nur ihr heutiges Ergebnis abgefragt.


def _spezifitaet(selektor: str) -> tuple[int, int, int]:
    """Eine vereinfachte CSS-Spezifitaet (id, klasse/attribut/pseudo-
    klasse, typ) -- genug fuer die einfachen, kombinatorlosen Selektoren
    dieses Moduls."""
    sel = selektor.strip()
    ohne_attr = re.sub(r"\[[^\]]*\]", " ATTR ", sel)
    ids = ohne_attr.count("#")
    klassen = (ohne_attr.count(".") + ohne_attr.count("ATTR")
               + len(re.findall(r"(?<!:):[a-zA-Z-]+", ohne_attr)))
    rest = re.sub(r"[#.][\w-]+", " ", ohne_attr)
    rest = re.sub(r":[a-zA-Z-]+", " ", rest)
    rest = rest.replace("ATTR", " ")
    typen = len(re.findall(r"[a-zA-Z][\w-]*", rest))
    return (ids, klassen, typen)


def test_spezifitaetsrechnung_an_bekannten_selektoren():
    """Selbsttest der Hilfsfunktion, an Selektoren, deren Spezifitaet man
    von Hand nachrechnen kann -- sonst pruefte der Test unten eine
    Rechnung, der man nicht vertrauen kann."""
    assert _spezifitaet("#ux-balken") == (1, 0, 0)
    assert _spezifitaet(".roadmap #ux-balken") == (1, 1, 0)
    assert _spezifitaet("#ux-balken i") == (1, 0, 1)
    assert _spezifitaet(".roadmap #ux-balken i") == (1, 1, 1)
    assert _spezifitaet('.roadmap #ux-balken i[data-stand="fertig"]') == (1, 2, 1)


def _css_regeln(css: str) -> list[tuple[str, str]]:
    """Jede Regel als ``(selektor, koerper)`` in Dokumentreihenfolge,
    Kommentare vorher entfernt (sonst haengt ein ``/* ... */`` vor einer
    Regel am Selektortext)."""
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.findall(r"([^{}]+)\{([^{}]*)\}", ohne_kommentare)


def _trifft_dasselbe_element(selektor: str, basis: str) -> bool:
    """Zielt ``selektor`` -- ob roh (``_ROADMAP``) oder ``.roadmap``-
    praefixiert (``_TABS_B``) -- auf GENAU dasselbe Element wie ``basis``
    (z. B. ``"#ux-balken"`` oder ``"#ux-balken i"``)? Die data-stand-
    Varianten (Befund 2) zaehlen bewusst nicht mit, auch nicht als
    attributloses Praefix: ihre Selektorkette hat ein zusaetzliches
    Attribut und damit eine andere, hoehere Spezifitaet, die diesen
    Vergleich verzerren wuerde."""
    sel = selektor.strip()
    if "[" in sel:
        return False
    return sel == basis or sel.endswith(" " + basis)


def _gewinner(regeln: list[tuple[str, str]], basis: str) -> tuple[str, str]:
    """Die Regel, die bei einer echten Spezifitaetsrechnung (plus
    Dokumentreihenfolge als Tie-Breaker) fuer ``basis`` gewinnt --
    ``(selektor, koerper)``."""
    kandidaten = []
    for index, (selektoren, koerper) in enumerate(regeln):
        for roh in selektoren.split(","):
            sel = roh.strip()
            if _trifft_dasselbe_element(sel, basis):
                kandidaten.append((_spezifitaet(sel), index, sel, koerper))
    assert len(kandidaten) >= 2, (basis, kandidaten)  # B UND _ROADMAP vertreten
    _, _, sel, koerper = max(kandidaten, key=lambda k: (k[0], k[1]))
    return sel, koerper


def test_buehnenlichter_gewinnen_gegen_die_roadmap_regel():
    """Befund 1: ``.roadmap #ux-balken``/``.roadmap #ux-balken i`` aus
    ``_TABS_B`` muessen gegen die unpraefixierten Regeln aus ``_ROADMAP``
    gewinnen -- unabhaengig von der Position im zusammengesetzten CSS."""
    css = web_gestalt.css_rahmen("b")
    regeln = _css_regeln(css)

    for basis in ("#ux-balken", "#ux-balken i"):
        # Beide Quellen muessen ueberhaupt vertreten sein -- sonst waere
        # das kein Kollisionstest mehr, sondern eine leere Pruefung.
        rohe = [sel for sel, _ in regeln for s in sel.split(",")
                if s.strip() == basis]
        assert rohe, (basis, "die unpraefixierte _ROADMAP-Regel fehlt")

        sel, koerper = _gewinner(regeln, basis)
        assert sel.startswith(".roadmap "), (basis, sel)

    # Die gewonnenen Werte sind wirklich die aus B, nicht die aus
    # _ROADMAP (deren ``#ux-balken i`` ``width: var(--fortschritt, 0%)``
    # setzt -- das waere in B dauerhaft 0 %, also unsichtbar).
    _, aussen_koerper = _gewinner(regeln, "#ux-balken")
    assert "border: 0" in aussen_koerper
    assert "var(--linie)" not in aussen_koerper

    _, innen_koerper = _gewinner(regeln, "#ux-balken i")
    assert "width: auto" in innen_koerper
    assert "var(--fortschritt" not in innen_koerper


def test_die_drei_lichtzustaende_sind_unterscheidbar():
    """Befund 2: ``_JS_FORTSCHRITT`` setzt ``data-stand`` je Licht
    (``aktiv``/``offen``/``fertig``) -- ohne eigene Regeln je Zustand
    saehen alle drei gleich aus (nach Behebung von Befund 1 alle wie
    ``offen``)."""
    css = web_gestalt.css_rahmen("b")
    fertig = re.search(
        r'\.roadmap #ux-balken i\[data-stand="fertig"\]\s*\{([^}]*)\}', css)
    aktiv = re.search(
        r'\.roadmap #ux-balken i\[data-stand="aktiv"\]\s*\{([^}]*)\}', css)
    assert fertig and aktiv, "data-stand-Regeln fuer fertig/aktiv fehlen"
    assert "var(--signal)" in fertig.group(1)
    assert "var(--warn)" in aktiv.group(1)
    assert fertig.group(1) != aktiv.group(1)
    # Beide spezifischer als die Basisregel (die ``offen`` trifft) --
    # sonst ueberschriebe die Reihenfolge im Dokument das Ergebnis.
    basis_spez = _spezifitaet(".roadmap #ux-balken i")
    assert _spezifitaet('.roadmap #ux-balken i[data-stand="fertig"]') > basis_spez
    assert _spezifitaet('.roadmap #ux-balken i[data-stand="aktiv"]') > basis_spez
    # Keine rohe Hexfarbe (Vertrag aus Aufgabe 3).
    for koerper in (fertig.group(1), aktiv.group(1)):
        assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", koerper)
