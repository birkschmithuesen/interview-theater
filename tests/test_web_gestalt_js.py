"""Der Vertrag des Effekt-JavaScripts -- ohne Browser.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_gestalt_e2e.py``:
ob die Zustaende im echten Chromium wirklich umschalten. Hier steht, was
man am ausgelieferten Skript messen kann -- und das ist genug fuer die
Entscheidungen, die leicht verloren gehen.
"""

import re

import pytest

from interview_theater import web_gestalt


@pytest.fixture(params=web_gestalt.ENTWUERFE)
def js(request):
    return web_gestalt.skript(request.param)


# -- Der CSP-Vertrag im Skript ----------------------------------------------


def test_keine_platzhalter_bleiben_stehen(js):
    """Ein uebersehener ``__NAME__`` waere im Browser ein Syntaxfehler --
    und die ganze Gestaltung waere weg."""
    assert not re.search(r"__[A-Z_]+__", js)


def test_das_skript_setzt_werte_ueber_cssom(js):
    assert "setProperty(" in js
    assert "setAttribute('style'" not in js


@pytest.mark.xfail(
    reason="_JS_DENKT (Aufgabe 5) beobachtet per MutationObserver, es "
    "braucht keinen Klick-Handler -- addEventListener( kommt erst mit "
    "dem Aufnahmeknopf (Aufgabe 8, geprueft per grep gegen "
    "task-8-brief.md).",
    strict=False,
)
def test_das_skript_haengt_keine_handler_ins_markup(js):
    """Alles ueber ``addEventListener``; ein ``el.onclick =`` waere zwar
    CSP-konform, aber wuerde einen fremden Handler ueberschreiben."""
    assert "addEventListener(" in js
    assert not re.search(r"\.on(click|input|change)\s*=", js)


@pytest.mark.xfail(
    reason="_JS_DENKT (Aufgabe 5) legt kein eigenes Element neben "
    "#interview an -- ux-rec-zeile kommt erst mit dem Aufnahmeknopf "
    "(Aufgabe 8, geprueft per grep gegen task-8-brief.md).",
    strict=False,
)
def test_das_skript_schreibt_nie_in_den_interview_knopf(js):
    """Befund 2 an Karte A2: ``_CHAT_JS`` setzt dort ``textContent``.
    Zwei Schreiber auf einem Knoten sind ein Fehler, der erst im Workshop
    auffaellt -- die Gestaltung legt ihren Text daneben
    (``#ux-rec-zeile``)."""
    assert "ux-rec-zeile" in js
    for verboten in ("interview').textContent", 'interview").textContent',
                     "interviewKnopf.textContent"):
        assert verboten not in js


def test_das_skript_achtet_auf_reduzierte_bewegung(js):
    """Nicht nur im CSS: die Momente sind zeitgesteuert, und ein Timer
    laeuft auch dann, wenn die Animation aus ist."""
    assert "prefers-reduced-motion" in js
    assert "RUHIG" in js


# -- Chat --------------------------------------------------------------------


def test_der_denk_zustand_haengt_an_der_tippanzeige(js):
    """``#tippt`` kommt aus Karte A2 und traegt schon den Text. Die
    Gestaltung macht daraus eine Terminalzeile -- sie erfindet keine
    zweite Anzeige daneben."""
    assert "'tippt'" in js or '"tippt"' in js


def test_die_gestaltung_kennt_die_vorlaeufige_blase(js):
    """Sie gehoert Karte W; gestaltet wird sie, geschrieben nicht."""
    assert "vorlaeufig" in web_gestalt.css_chat("a")
    assert "vorlaeufig" in web_gestalt.css_chat("b")


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_das_chat_css_faerbt_beide_blasenarten(name):
    css = web_gestalt.css_chat(name)
    assert ".blase.bot" in css
    assert ".blase.gruppe" in css
    assert ".leiste button" in css


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_blasen_lesen_sich_gross_genug(name):
    """16 px ist die Untergrenze fuer Fliesstext am Telefon."""
    css = web_gestalt.css_chat(name)
    treffer = re.search(r"\.blase\s*\{[^}]*font-size:\s*([\d.]+)rem", css, flags=re.S)
    assert treffer, "die Blase setzt keine Schriftgroesse"
    assert float(treffer.group(1)) >= 1.0


def test_nur_entwurf_a_kennzeichnet_die_bot_blase():
    """Die Zeile ``bot ~ $`` ist Terminal; in B unterscheiden sich Bot und
    Gruppe wie Repliken -- durch Ausrichtung und Flaeche."""
    assert ".blase.bot::before" in web_gestalt.css_chat("a")
    assert ".blase.bot::before" not in web_gestalt.css_chat("b")


# -- Tabs und Panels ---------------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_tableiste_ist_am_daumen_gross_genug(name):
    css = web_gestalt.css_rahmen(name)
    assert ".tabs button" in css
    assert "min-height: var(--tippflaeche)" in css or "--tabs-hoehe" in css


def test_a_legt_die_tabs_unten_und_b_oben():
    """Die eine Entscheidung, die Karte W offen gelassen hat
    (Uebergabe 1: "auf einem Telefon spricht viel fuer unten")."""
    def tabblock(name):
        return re.search(r"\.tabs\s*\{([^}]*)\}",
                         web_gestalt.css_rahmen(name), flags=re.S).group(1)

    assert "position: fixed" in tabblock("a") and "bottom: 0" in tabblock("a")
    assert "position: sticky" in tabblock("b") and "top: 0" in tabblock("b")
    # ``--tabs-hoehe`` ist der Platz, den der Fuss nach unten frei laesst:
    # in B liegt die Leiste oben, also null.
    assert web_gestalt.TOKENS["a"]["tabs-hoehe"] != "0rem"
    assert web_gestalt.TOKENS["b"]["tabs-hoehe"] == "0rem"


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_fuss_weicht_der_tableiste(name):
    """In A liegt die Leiste unter dem Fuss; in B ist ``--tabs-hoehe``
    null und dieselbe Regel kostet nichts."""
    assert "bottom: var(--tabs-hoehe)" in web_gestalt.css_rahmen(name)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_fuss_verschwindet_ausserhalb_des_chats(name):
    """Im Skript liest man, dort tippt niemand. W setzt
    ``body[data-tab]`` -- also braucht das kein JavaScript."""
    css = web_gestalt.css_rahmen(name)
    assert 'body:not([data-tab="chat"]) .fuss' in css


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_gewaehlte_tab_ist_nicht_nur_farbig_markiert(name):
    """Farbe allein traegt keinen Zustand (WCAG 1.4.1): der gewaehlte Tab
    bekommt zusaetzlich eine Kante."""
    css = web_gestalt.css_rahmen(name)
    block = re.search(
        r'\.tabs button\[aria-selected="true"\]\s*\{([^}]*)\}', css, flags=re.S)
    assert block, "kein Stil fuer den gewaehlten Tab"
    assert "box-shadow" in block.group(1) or "border" in block.group(1)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_arbeitsstand_setzt_seine_feldkarten(name):
    css = web_gestalt.css_stand(name)
    assert "[data-feld]" in css or ".feld" in css


# -- Die sieben Akte ---------------------------------------------------------


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_die_aktleiste_hat_ihre_zustaende(name):
    css = web_gestalt.css_rahmen(name)
    for selektor in (".phase.aktiv", ".phase-knopf", ".aufgabe.erledigt",
                     ".aufgabe.laeuft"):
        assert selektor in css, selektor


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_der_bestaetigungszustand_sieht_anders_aus(name):
    """W schreibt beim ersten Druck die Rueckfrage in den Knopf
    (``data-sicher``). Sieht der Knopf dabei aus wie vorher, liest ihn
    niemand -- und der zweite Druck kommt aus Versehen."""
    assert '.phase-knopf[data-sicher="1"]' in web_gestalt.css_rahmen(name)


@pytest.mark.parametrize("name", web_gestalt.ENTWUERFE)
def test_eine_aufgabe_ist_gross_genug_zum_antippen(name):
    """Jede Aufgabe ist ein Sprungziel (``data-ziel-tab``)."""
    css = web_gestalt.css_rahmen(name)
    block = re.search(r"\.aufgabe\s*\{([^}]*)\}", css, flags=re.S)
    assert block and "min-height: var(--tippflaeche)" in block.group(1)


def test_der_fortschritt_wird_aus_dem_dom_gerechnet(js):
    """Kein neuer Schluessel im Zustands-Poll: die Zahlen stehen schon
    da."""
    assert "aufgabe" in js
    assert "erledigt" in js
    assert "setProperty('--fortschritt'" in js


def test_der_fortschritt_haengt_nicht_an_einer_festen_sieben(js):
    """``phasen.PHASEN`` hat sich seit dem 04.09.2026 dreimal geaendert.
    Die Gestaltung zaehlt, was da ist."""
    assert "querySelectorAll" in js
    assert re.search(r"/\s*7\b", js) is None


def test_die_akt_beschriftung_kommt_aus_den_mikrotexten(js):
    """Sonst stuende in Dortmund Englisch und in Padua Deutsch."""
    assert "TEXTE" in js
    assert "akt_kopf" in js
