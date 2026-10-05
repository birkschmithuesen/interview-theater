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


# -- Feedbackloop P1-M3: der Padua-Stepper auf schmalen Telefonen ----------


def test_der_stepper_kompaktiert_sich_auf_schmalen_telefonen():
    """Gemessen am echten Chromium (360x640): Kopf + Tabs zusammen kamen
    auf 40% des Schirms, sobald Stepper-Hinweis und "Next up" beide
    sichtbar waren. ``css_stepper()`` ist schon unscopiert UND
    Padua-exklusiv (nie fuer Dortmund gerendert) -- ein ``@media`` hier
    verstoesst nicht gegen den scope_css-Grund, dem ``css_rahmen()`` das
    Privileg vorbehaelt (``test_kein_keyframes_und_kein_media_im_
    gescopten_teil`` oben gilt nur fuer ``GESCOPT``, nicht fuer den
    Stepper)."""
    css = web_gestalt.css_stepper()
    block = re.search(r"@media\s*\(max-width:\s*430px\)\s*\{(.*?)\n\}\n",
                       css, flags=re.S)
    assert block, "keine kompaktierende Regel fuer schmale Telefone"
    assert "header.phasenav" in block.group(1)
    assert ".stepper-hinweis" in block.group(1)
    # Keine Tippflaeche darf unter das Mindestmass fallen -- geschrumpft
    # wird nur Polster/Abstand, nie ``min-height``/``min-width``.
    assert "min-height" not in block.group(1)
    assert "min-width" not in block.group(1)


def test_der_stepper_bleibt_padua_exklusiv_und_ausserhalb_von_css_rahmen():
    """``css_stepper()`` wird nur angehaengt, wenn ``[web]
    phasennav_stepper`` an ist (``web_vereint.seite``) -- landet also nie
    in Dortmunds ``<style>``-Block. Die neue Zeile muss deshalb in
    ``css_stepper()`` stehen, nicht in ``css_rahmen()`` (das bleibt fuer
    Dortmund bitgleich, ``tests/test_web_vereint_bitgleich.py``)."""
    assert "max-width: 430px" not in web_gestalt.css_rahmen()
    assert "max-width: 430px" in web_gestalt.css_stepper()


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


_GESCOPTE_PRAEFIXE = {
    "css_chat": ".panel-chat",
    "css_stand": ".panel-stand",
    "css_textbuch": ".panel-textbuch",
}


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
@pytest.mark.parametrize("funktion", GESCOPT)
def test_jeder_selektor_traegt_den_scope_praefix_nach_scope_css(name, funktion):
    """Review-Befund zu 083bbaa: ein CSS-Kommentar mit Kommas direkt vor
    einer Regel (``/* Feedbackloop P1-H1b: ... */`` vor ``#interview[hidden]
    + #ux-rec-zeile, ...`` in ``_CHAT_A``/``_CHAT_B``) wird von
    ``web_vereint.scope_css`` an JEDEM Komma gesplittet, bevor der
    Scope-Praefix gesetzt wird -- der Kommentar selbst enthaelt Kommas, der
    echte erste Selektor landet deshalb NICHT am Anfang eines Split-Stuecks
    und bekommt keinen Praefix (``_ein_selektor`` setzt ihn nur vorne an).
    Jede echte, im Markup benutzte Selektor-Kette, die ``scope_css``
    ausgibt, muss deshalb mit dem Scope-Praefix beginnen -- gemessen am
    tatsaechlichen Aufruf aus ``web_vereint.seite``, nicht nur an Klammern-
    und Fragment-Zaehlung wie oben."""
    scope = _GESCOPTE_PRAEFIXE[funktion]
    ergebnis = web_vereint.scope_css(_css(funktion, name), scope)
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", ergebnis, flags=re.S)
    for selektoren, _koerper in re.findall(r"([^{}]+)\{([^{}]*)\}", ohne_kommentare):
        for roh in selektoren.split(","):
            sel = roh.strip()
            if not sel:
                continue
            assert sel.startswith(scope), (funktion, name, sel)


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


def _kanonisch_summary(sel: str) -> bool:
    """Trifft ``sel`` dasselbe ``<summary>``-Element wie ``.roadmap >
    summary``, egal ob roh (``_ROADMAP``) oder mit verdoppeltem
    ``.roadmap``-Praefix (``_TABS_B`` nach dem Fix)? Anders als bei
    ``#ux-balken`` hat hier schon die _ROADMAP-Fassung ``.roadmap`` im
    Selektor -- ein Nachfahren-Praefix waere deshalb kein zweiter Fund,
    sondern derselbe Text zweimal; die Klassen-Verdopplung ist die Form,
    die trotzdem noch auf genau dieses Element zielt."""
    return bool(re.fullmatch(r"(\.roadmap)+\s*>\s*summary", sel.strip()))


def _kanonisch_phase_knopf(sel: str) -> bool:
    """Trifft ``sel`` dasselbe ``.phase-knopf``-Element, roh (_ROADMAP)
    oder mit Nachfahren-Praefix (_TABS_B nach dem Fix)?"""
    return bool(re.fullmatch(r"(\.roadmap\s+)?\.phase-knopf", sel.strip()))


@pytest.mark.parametrize(
    "ist_treffer,erwarteter_wert,verbotener_wert",
    [
        (_kanonisch_summary, "var(--schrift-skript)", "var(--schrift-tech)"),
        (_kanonisch_phase_knopf, "font-family: var(--schrift-skript)", "font: inherit"),
    ],
    ids=["roadmap-summary", "phase-knopf"],
)
def test_abschlussreview_befund1_schrift_gewinnt_gegen_die_roadmap_regel(
    ist_treffer, erwarteter_wert, verbotener_wert,
):
    """Abschluss-Review, Befund 1: ``.roadmap > summary`` und
    ``.phase-knopf`` stehen in ``_TABS_B`` UND -- mit exakt derselben
    Spezifitaet -- in ``_ROADMAP``, das in ``css_rahmen()`` NACH den Tabs
    steht. Vor dem Fix gewinnt deshalb ``_ROADMAP``
    (``var(--schrift-tech)`` bzw. die Shorthand ``font: inherit``, die
    ``font-family`` explizit zuruecksetzt), nicht die B-Regel. Gerechnet
    wird wie bei ``#ux-balken`` oben: echte Spezifitaet plus
    Dokumentreihenfolge als Tie-Breaker, nicht nur ein Textvorkommen.

    Gefiltert wird auf Regeln, die ueberhaupt ``font``/``font-family``
    setzen -- sonst mischt sich bei ``.phase-knopf`` die
    ``prefers-reduced-motion``-Regel (dieselbe bare Klasse, aber
    ``animation``/``transition``) unter die Kandidaten und verzerrt die
    Tie-Break-Reihenfolge."""
    css = web_gestalt.css_rahmen("b")
    regeln = _css_regeln(css)

    kandidaten = []
    for index, (selektoren, koerper) in enumerate(regeln):
        for roh in selektoren.split(","):
            sel = roh.strip()
            if ist_treffer(sel) and re.search(r"\bfont(-family)?\s*:", koerper):
                kandidaten.append((_spezifitaet(sel), index, sel, koerper))
    assert len(kandidaten) >= 2, kandidaten  # B UND _ROADMAP vertreten

    _, _, sel, koerper = max(kandidaten, key=lambda k: (k[0], k[1]))
    assert erwarteter_wert in koerper, (sel, koerper)
    assert verbotener_wert not in koerper, (sel, koerper)


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


# -- 5. Der Druck bleibt ein helles Manuskript ------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_druckblock_macht_die_seite_hell(name):
    """Gestaltung steht im ``<style>`` NACH ``_CSS_TEXTBUCH`` und faerbt
    ``body`` dunkel -- ohne diesen Block kaeme ein schwarzes Blatt aus dem
    Drucker."""
    block = re.search(r"@media\s+print\s*\{(.*?)\n\}",
                      web_gestalt.css_rahmen(name), flags=re.S)
    assert block, "kein @media print"
    assert "background: #fff !important" in block.group(1)
    assert "color: #000 !important" in block.group(1)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_im_druck_faellt_jede_bedienung_weg(name):
    block = re.search(r"@media\s+print\s*\{(.*?)\n\}",
                      web_gestalt.css_rahmen(name), flags=re.S).group(1)
    for weg in (".tabs", ".roadmap", ".fuss", "#ux-belohnung", "#ux-vorhang"):
        assert weg in block, weg


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_sprecher_ist_im_druck_schwarz_und_fett(name):
    """Ein Manuskript, kein Bildschirmtext: Signalfarbe auf Papier ist
    hellgrau."""
    block = re.search(r"@media\s+print\s*\{(.*?)\n\}",
                      web_gestalt.css_rahmen(name), flags=re.S).group(1)
    assert ".sprecher" in block
    assert "font-weight: 700" in block


# -- 6. Das Skript als Manuskript -------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_szenentext_ist_in_der_skriptschrift_gesetzt(name):
    css = web_gestalt.css_textbuch(name)
    assert "var(--schrift-skript)" in css
    assert ".replik" in css
    assert ".regie" in css


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_regieanweisung_ist_kursiv_und_gedaempft(name):
    css = web_gestalt.css_textbuch(name)
    block = re.search(r"\.regie\s*\{([^}]*)\}", css, flags=re.S)
    assert block and "italic" in block.group(1)
    assert "var(--text-leise)" in block.group(1)


def test_a_setzt_den_sprecher_in_die_zeile_und_b_darueber():
    """Die vierte benannte Komponenten-Abweichung."""
    assert "display: block" in re.search(
        r"\.sprecher\s*\{([^}]*)\}", web_gestalt.css_textbuch("b"),
        flags=re.S).group(1)
    assert "display: block" not in re.search(
        r"\.sprecher\s*\{([^}]*)\}", web_gestalt.css_textbuch("a"),
        flags=re.S).group(1)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_rollenfilter_bleibt_unangetastet(name):
    """``body[data-figur] .replik`` gehoert ``_CSS_TEXTBUCH``; die
    Gestaltung faerbt, sie filtert nicht."""
    assert "data-figur" not in web_gestalt.css_textbuch(name)
