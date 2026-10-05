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


# Fix round 1 (Review, Task 5): drei Minor-Befunde.

def test_der_tipp_hinweis_verschwindet_unter_dem_laufenden_toggle():
    # Befund 1: "Einmal tippen zum Starten." (#ux-rec-zeile, aus
    # web_gestalt.py) sitzt als Geschwister von #interview im Fuss, nicht
    # in .zeile -- die bestehende Regel blendet ihn also nicht mit aus.
    assert '.fuss[data-brainstorm="1"] #ux-rec-zeile { display: none; }' in web_chat._CSS_CHAT


def test_die_redundante_brainstorm_breite_ist_weg():
    # Befund 3: "#brainstorm { width: 100% }" steht schon in der
    # unbedingten Regel (ganzer Knopf ist immer volle Breite) --
    # die Wiederholung unter [data-brainstorm="1"] war totes Gewicht.
    assert web_chat._CSS_CHAT.count("#brainstorm") >= 1
    assert '.fuss[data-brainstorm="1"] #brainstorm { width: 100%; }' not in web_chat._CSS_CHAT


def test_zeigebrainstormmodus_scrollt_nur_bei_tatsaechlichem_wechsel():
    # Befund 2: zeigeModus() ruft zeigeBrainstormModus() bei JEDEM Poll --
    # vorher riss "if (warUnten) { nachUnten(); }" den Verlauf bei jedem
    # Tick nach unten, auch ohne Aenderung an fuss.dataset.brainstorm.
    zeige = _fn("zeigeBrainstormModus", "starteBrainstorm")
    assert "var fussVorher = fuss.dataset.brainstorm;" in zeige
    assert "if (warUnten) { nachUnten(); }" not in zeige
    assert "if (warUnten && fuss.dataset.brainstorm !== fussVorher) { nachUnten(); }" in zeige
