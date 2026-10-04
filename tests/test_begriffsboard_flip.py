"""Karte t_cb2c4678, Aufgabe 5: Live-Ranking ohne Springen (D3), direkt in
``ladeBuehne()``. Die reinen Helfer werden wie in
``tests/test_buehne_nav_js.py`` per Klammertiefe aus ``_VEREINT_JS``
geschnitten und unter Node gerufen."""

import json
import re
import shutil
import subprocess

import pytest

from interview_theater import web_gestalt, web_vereint

NODE = shutil.which("node")
_HELFER = ("bbSchluessel", "bbZuordnung", "bbVersatz")


def _extrahiere(skript: str, name: str) -> str:
    treffer = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", skript)
    assert treffer is not None, f"{name} nicht in _VEREINT_JS gefunden"
    i = treffer.end()
    tiefe = 1
    while tiefe:
        if skript[i] == "{":
            tiefe += 1
        elif skript[i] == "}":
            tiefe -= 1
        i += 1
    return skript[treffer.start():i]


@pytest.fixture
def harness():
    if NODE is None:
        pytest.skip("kein node auf PATH")
    return "\n".join(_extrahiere(web_vereint._VEREINT_JS, n) for n in _HELFER)


def _node(tmp_path, harness, anhang):
    pfad = tmp_path / "bb.js"
    pfad.write_text(harness + "\n" + anhang + "\n", encoding="utf-8")
    lauf = subprocess.run([NODE, str(pfad)], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout)


# -- Node: reine Helfer ------------------------------------------------------

def test_zuordnung_ueber_begriff_dann_ueber_vorgaenger(tmp_path, harness):
    wert = _node(tmp_path, harness, """
      console.log(JSON.stringify(bbZuordnung(['Heimat', 'Grenze', 'Roboter'], [
        {begriff: 'KI-Roboter', vorgaenger: 'Roboter'},
        {begriff: 'Heimat', vorgaenger: null},
        {begriff: 'Grenze', vorgaenger: ''}
      ])));
    """)
    assert wert == ["roboter", "heimat", "grenze"]


def test_zuordnung_vorgaenger_nur_wenn_die_alte_zeile_frei_ist(tmp_path, harness):
    wert = _node(tmp_path, harness, """
      console.log(JSON.stringify([
        bbZuordnung(['Roboter'], [{begriff: 'Roboter'}, {begriff: 'KI-Roboter', vorgaenger: 'Roboter'}]),
        bbZuordnung(['Roboter'], [{begriff: 'KI-Roboter', vorgaenger: 'Roboter'},
                                  {begriff: 'Haushaltsroboter', vorgaenger: 'Roboter'}]),
        bbZuordnung([], [{begriff: 'Neu'}])
      ]));
    """)
    assert wert == [["roboter", None], ["roboter", None], [None]]


def test_schluessel_gleicht_gross_klein_und_leerraum_an(tmp_path, harness):
    wert = _node(tmp_path, harness, """
      console.log(JSON.stringify([bbSchluessel('  KI-Roboter \\n'), bbSchluessel(null),
                                  bbZuordnung(['heimat '], [{begriff: 'Heimat'}])]));
    """)
    assert wert == ["ki-roboter", "", ["heimat"]]


def test_versatz_ist_alt_minus_neu_und_null_ohne_alte_lage(tmp_path, harness):
    wert = _node(tmp_path, harness, """
      console.log(JSON.stringify([
        bbVersatz({heimat: 0, roboter: 80}, ['roboter', 'heimat', null], [0, 40, 80]),
        bbVersatz(null, ['roboter'], [0]),
        bbVersatz({heimat: 0}, ['roboter'], [0])
      ]));
    """)
    assert wert == [[80, -40, None], [None], [None]]


# -- Einhaengung in ladeBuehne(), CSP, reduced motion -------------------------

def test_ladebuehne_merkt_vor_dem_tausch_und_spielt_danach():
    js = web_vereint._VEREINT_JS
    lade = _extrahiere(js, "ladeBuehne")
    merke = lade.index("var bbVorher = bbMerke(panel);")
    tausch = lade.index("panel.innerHTML = neu;")
    spiele = lade.index("bbSpiele(panel, bbVorher);")
    assert merke < tausch < spiele
    # Der Phase-4-Weg (zurueckgeblaettert) bleibt unangetastet: nur im
    # Zweig "aktuell" wird getauscht und damit gespielt.
    zweig = lade[lade.index("if (buehnePos === null) {"):spiele]
    assert "panel.innerHTML = neu;" in zweig


def test_ohne_board_tun_die_funktionen_nichts():
    js = web_vereint._VEREINT_JS
    merke = _extrahiere(js, "bbMerke")
    spiele = _extrahiere(js, "bbSpiele")
    assert "ol.begriffsboard" in merke and "return null" in merke
    assert spiele.index("if (!vorher") < spiele.index("querySelector")


def test_skript_haelt_die_csp_und_die_ruhe():
    js = web_vereint._VEREINT_JS
    teil = "\n".join(_extrahiere(js, n) for n in _HELFER + ("bbMerke", "bbSpiele"))
    assert "style=" not in teil and "setAttribute('style'" not in teil
    assert re.search(r"\son\w+=", teil) is None
    assert "prefers-reduced-motion: reduce" in teil
    assert ".style.transform" in teil and ".style.transition" in teil
    assert "innerHTML" not in teil            # der Tausch bleibt allein ladeBuehne()s
    assert "MutationObserver" not in teil     # kein Beobachter-Umweg


def test_css_ist_ruhend_ohne_media_und_ohne_hexfarbe():
    css = web_gestalt.css_buehne()
    teil = css[css.index(".begriffsboard .vorgaenger"):]
    for verboten in ("@media", "@keyframes", "transition", "animation", "url("):
        assert verboten not in teil, verboten
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", teil) is None
    assert "var(--text-leise)" in teil
    # Ueberlebt das Scoping wie der Rest von css_buehne():
    assert ".panel-buehne .begriffsboard .vorgaenger" in web_vereint.scope_css(css, ".panel-buehne")


def test_css_hat_rang_marke_trennlinie_und_verworfen_kursiv():
    """Design-Erweiterung (Karte t_cb2c4678, 04.10.2026): Rang 1-5 bekommt
    eine Scheinwerfer-Marke (CSS-Counter auf data-top), der Rest eine
    Trennlinie direkt danach, ``status="verworfen"`` eine stille
    Kursivschrift -- durchgestrichen bleibt allein der Schaerfungskette
    vorbehalten."""
    css = web_gestalt.css_buehne()
    assert 'li[data-top="1"]::before' in css
    assert "counter-increment: bbrang" in css
    assert 'li[data-top="1"] + li:not([data-top="1"])' in css
    assert 'li[data-status="verworfen"] .begriff { font-style: italic; }' in css
    # Durchstreichen bleibt exklusiv der Schaerfungskette: keine neue
    # text-decoration-Regel fuer verworfen.
    verworfen_regel = css[css.index('li[data-status="verworfen"]'):]
    verworfen_regel = verworfen_regel[:verworfen_regel.index("}") + 1]
    assert "text-decoration" not in verworfen_regel
    # Ueberlebt das Scoping wie der Rest von css_buehne().
    gescoped = web_vereint.scope_css(css, ".panel-buehne")
    assert '.panel-buehne .begriffsboard li[data-top="1"]::before' in gescoped
    assert '.panel-buehne .begriffsboard li[data-status="verworfen"] .begriff' in gescoped


def test_css_ohne_hexfarbe_bleibt_auch_mit_dem_neuen_design_wahr():
    """Regression auf der bestehenden Zusage: die ganze ``_BUEHNE``-Konstante
    bleibt frei von rohen Hexfarben, nicht nur der Teil ab ``.vorgaenger``."""
    css = web_gestalt.css_buehne()
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", css) is None
    for verboten in ("@media", "@keyframes", "transition", "animation", "url("):
        assert verboten not in css, verboten
