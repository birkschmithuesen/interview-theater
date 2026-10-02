"""Speicherquittungen als Systemzeile in der Chatansicht (UX-Knoepfe-Karte,
Abschnitt 3): ``web_post.typ = 'system'`` bekommt eine eigene CSS-Klasse
statt wie eine gewoehnliche Bot-Sprechblase auszusehen -- serverseitig
(``_blase_html``, erster Seitenaufbau) und clientseitig (``klasseVon``,
jede weitere Zeile ueber den Poll) auf demselben Weg."""

from interview_theater import web_chat


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
