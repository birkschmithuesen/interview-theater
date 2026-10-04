"""Karte t_cb2c4678, Aufgabe 4: die Schaerfung im CoThinker (D2). Nur
erfundenes Material."""

import json
import re
import sqlite3

import pytest

from interview_theater import db, repo, web, web_daten

CHAT = 1


def _e(begriff, **kw):
    eintrag = {"begriff": begriff, "nennungen": 1, "zustimmung": 0, "begruendung": "",
               "doppelbedeutung": "", "status": "kandidat"}
    eintrag.update(kw)
    return eintrag


def test_kette_steht_durchgestrichen_der_juengste_neben_dem_neuen():
    html_ = web._begriffsboard_html([_e("sozialer KI-Roboter",
                                        vorgaenger=["Roboter", "KI-Roboter"])])
    assert ('<span class="begriff">sozialer KI-Roboter</span>'
            '<span class="vorgaenger"><del>KI-Roboter</del> <del>Roboter</del></span>') in html_
    assert re.search(r'<li data-begriff="sozialer KI-Roboter"[^>]*'
                     r' data-vorgaenger="KI-Roboter"[^>]*>', html_)


def test_kette_wird_maskiert():
    html_ = web._begriffsboard_html([_e("Mut", vorgaenger=['<b>"A&B"</b>'])])
    assert "<del>&lt;b&gt;&quot;A&amp;B&quot;&lt;/b&gt;</del>" in html_
    assert 'data-vorgaenger="&lt;b&gt;&quot;A&amp;B&quot;&lt;/b&gt;"' in html_
    assert "<b>" not in html_


def test_ohne_kette_bleibt_die_zeile_zeichengleich():
    """Regression: ein Board ohne Schaerfung rendert wie vor dieser Karte."""
    assert web._begriffsboard_html([_e("Mut")]) == (
        '<div id="buehne-panel" data-ansicht="begriffsboard"><ol class="begriffsboard">'
        '<li data-begriff="Mut" data-status="kandidat" data-zustimmung="0" '
        'data-nennungen="1" data-top="1"><span class="begriff">Mut</span></li></ol></div>'
    )


def test_kein_style_kein_handler():
    html_ = web._begriffsboard_html([_e("KI-Roboter", vorgaenger=["Roboter"],
                                        begruendung="Erst Roboter, dann KI-Roboter.")])
    assert "style=" not in html_
    assert re.search(r"\son\w+=", html_) is None


@pytest.fixture
def pfad(tmp_path):
    p = str(tmp_path / "t.db")
    c = db.verbinde(p)
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    repo.lege_begriffsboard_an(c, CHAT, json.dumps([
        {"begriff": "KI-Roboter", "nennungen": 2, "zustimmung": 1,
         "begruendung": "Zuerst als Roboter genannt, dann geschaerft.",
         "zitat": "ZITAT-NIE-IM-WEB", "doppelbedeutung": "", "status": "favorit",
         "vorgaenger": ["Roboter"]},
    ]), "sovereign", 0)
    c.close()
    return p


def _ro(pfad):
    c = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def test_web_daten_reicht_die_kette_durch_ohne_zitat(pfad):
    eintraege = web_daten.begriffsboard(_ro(pfad), CHAT)
    assert eintraege[0]["vorgaenger"] == ["Roboter"]
    assert "zitat" not in eintraege[0]
    html_ = web._begriffsboard_html(eintraege)
    assert "<del>Roboter</del>" in html_
    assert "ZITAT-NIE-IM-WEB" not in html_
