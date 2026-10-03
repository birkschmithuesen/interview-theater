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


@pytest.mark.xfail(
    reason="_JS_DENKT (Aufgabe 5) braucht keinen dynamischen CSS-Wert -- "
    "setProperty( kommt erst mit dem Fortschritts-Baustein der Roadmap "
    "(Aufgabe 7, geprueft per grep gegen task-7-brief.md). Kein "
    "kuenstlicher setProperty()-Aufruf nur fuer diesen Test.",
    strict=False,
)
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
