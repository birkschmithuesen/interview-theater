"""t_cf87ee0a / t_a8129d7f: Brainstorm ist ein Toggle (ein Bogen), ohne
Pausenschnitt; waehrend er laeuft, belegt er den Platz der Eingabezeile."""

import re

from interview_theater import web_chat

DATEN = {"nachrichten": [], "letzte": 0, "aenderung": 0, "interviewmodus": False,
         "titel": None, "phase": 4, "brainstorm_knopf": True}


def _seite(**kw):
    return web_chat.chat_html(dict(DATEN, **kw), "1.x", "tok", "", 45000)


def _fn(name, bis):
    js = web_chat._CHAT_JS
    return js[js.index(f"function {name}"):js.index(f"function {bis}")]


def test_markup_hat_nur_noch_den_einen_knopf():
    seite = _seite()
    for weg in ("brainstorm-aktionen", "brainstorm-pause", "brainstorm-beenden"):
        assert f'id="{weg}"' not in seite, weg
    assert re.search(r'<button type="button" id="brainstorm" data-laeuft="0">', seite)


def test_js_kennt_keine_brainstormpause():
    js = web_chat._CHAT_JS
    for name in ("pausiereBrainstorm", "fortsetzeBrainstorm", "brainstormPauseKnopf",
                 "brainstormBeendenKnopf"):
        assert name not in js, name


def test_der_knopf_schaltet_an_und_aus():
    js = web_chat._CHAT_JS
    verdrahtung = js[js.index("if (brainstormKnopf) {\n    brainstormKnopf.addEventListener"):]
    verdrahtung = verdrahtung[:verdrahtung.index("});") + 3]
    assert "beendeBrainstorm()" in verdrahtung and "starteBrainstorm()" in verdrahtung


def test_kein_pausenschnitt_im_brainstorm():
    pegel = _fn("pegelAn", "formatiereUhr")
    assert "sitzung.art !== 'brainstorm'" in pegel
    # der harte Zeitdeckel bleibt (stiller technischer Schnitt)
    assert "schneideSegment(sitzung, 'cap')" in pegel


def test_laufender_brainstorm_belegt_die_eingabezeile():
    zeige = _fn("zeigeBrainstormModus", "starteBrainstorm")
    assert "fuss.dataset.brainstorm = an ? '1' : '0'" in zeige
    assert '.fuss[data-brainstorm="1"] .zeile' in web_chat._CSS_CHAT


def test_hoehenaenderung_des_fusses_haelt_den_verlauf_unten():
    # t_a8129d7f Punkt 1: gemessen rot im e2e (letzte Blase 60px unter dem
    # sichtbaren Ende) -- ein ResizeObserver auf Fuss und Verlauf ruft
    # nachUnten(), wenn der Verlauf vor der Aenderung unten stand.
    js = web_chat._CHAT_JS
    block = js[js.index("if (window.ResizeObserver && fuss) {"):]
    block = block[:block.index("zeigeModus();")]
    assert "hoehenBeobachter.observe(fuss);" in block
    assert "if (verlaufWarUnten && fensterWarUnten) { nachUnten(); }" in block


def test_laeuft_text_sagt_wie_man_den_bogen_schliesst():
    assert "{zeit}" in web_chat._TEXT_BRAINSTORM_LAEUFT
    assert "tippen" in web_chat._TEXT_BRAINSTORM_LAEUFT.casefold()
