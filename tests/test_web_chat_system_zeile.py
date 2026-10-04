"""Speicherquittungen als Systemzeile in der Chatansicht (UX-Knoepfe-Karte,
Abschnitt 3): ``web_post.typ = 'system'`` bekommt eine eigene CSS-Klasse
statt wie eine gewoehnliche Bot-Sprechblase auszusehen -- serverseitig
(``_blase_html``, erster Seitenaufbau) und clientseitig (``klasseVon``,
jede weitere Zeile ueber den Poll) auf demselben Weg."""

import re

import pytest

from interview_theater import web_chat
from interview_theater import web_gestalt

_KURSIV = re.compile(r"\.blase\.transkript\s*\{[^}]*font-style:\s*italic")


def _nachricht(typ, **zusatz):
    basis = {
        "id": 1, "von": "bot", "typ": typ, "text": "Notiert: Setting: Treppenhaus",
        "dauer": None, "dateiname": None, "knoepfe": [],
    }
    basis.update(zusatz)
    return basis


def test_eine_systemzeile_bekommt_die_klasse_system():
    html = web_chat._blase_html(_nachricht("system"))

    assert 'class="blase bot system"' in html


def test_eine_gewoehnliche_antwort_bleibt_bei_text():
    html = web_chat._blase_html(_nachricht("text"))

    assert 'class="blase bot text"' in html


def test_die_js_kennt_denselben_typ():
    """``klasseVon`` im Browser muss dieselbe Unterscheidung treffen wie
    ``_blase_html`` auf dem Server -- sonst sieht die erste Zeile anders aus
    als jede, die ueber den Poll nachkommt."""
    js = web_chat._js()

    assert "n.typ === 'system'" in js


def test_eine_transkriptblase_bekommt_die_klasse_transkript():
    """Karte t_ea994c7f: die EINE Transkriptblase eines Interviews bleibt
    eine Bot-Blase, nur mit der Klasse ``transkript``."""
    html = web_chat._blase_html(
        _nachricht("transkript", text="🎙 Interview 1\n\nIch kam im Winter an.")
    )
    assert 'class="blase bot transkript"' in html
    assert "🎙 Interview 1<br><br>Ich kam im Winter an." in html
    assert 'style="' not in html


def test_die_js_kennt_die_transkriptblase():
    assert "n.typ === 'transkript'" in web_chat._js()


def test_das_chat_css_setzt_die_transkriptblase_kursiv():
    assert _KURSIV.search(web_chat._CSS_CHAT)


@pytest.mark.parametrize("entwurf", ["a", "b"])
def test_beide_entwuerfe_setzen_die_transkriptblase_kursiv(entwurf):
    css = web_gestalt.css_chat(entwurf)
    assert _KURSIV.search(css)
    regel = re.search(r"\.blase\.transkript\s*\{([^}]*)\}", css).group(1)
    assert "var(--text)" in regel, "Theme-Token, keine feste Farbe (KONTRAST text/grund-2)"
