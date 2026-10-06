import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from simulation import browser_zaehler as z  # noqa: E402


def test_kein_eigener_brainstorm_selektor_mehr():
    """Birk 05.10.2026 22:00: kein Toggle-Knopf mehr -- ``#brainstorm``
    existiert im Markup nicht mehr, weder in ``VERDRAHTETE_SELEKTOREN``
    noch im Vorgabe-Selektor von ``tap_ziele_zu_klein``."""
    assert "#brainstorm" not in z.VERDRAHTETE_SELEKTOREN
    import inspect

    vorgabe = inspect.signature(z.tap_ziele_zu_klein).parameters["selektor"].default
    assert "#brainstorm" not in vorgabe

#: Ein absichtlich kaputter Stand: alle fuenf Mutanten auf einmal, in einem
#: HTML-Dokument, das sonst wie eine Chip-Leiste/Tabs/Eingabe aussieht.
_KAPUTT = """
<style>
  body { width: 120vw; }               /* Mutant 1: seitliches Rutschen */
  .klein { width: 20px; height: 20px; }  /* Mutant 2: zu kleines Tippziel */
  #eingabe { font-size: 12px; }          /* Mutant 3: Zoom-Falle */
</style>
<div class="blase bot">Where does it happen? And who is there?</div>
<div class="leiste"><button class="klein" type="button">x</button></div>
<input id="eingabe">
<button id="tot" type="button">Tot</button>
<script>
  document.addEventListener('click', function (ev) {
    var k = ev.target.closest('.leiste button');
    if (k) { document.body.appendChild(document.createElement('span')); }
  });
</script>
"""

#: Dieselbe Struktur, aber durchgehend sauber -- muss bei JEDEM Zaehler
#: leer/falsch bleiben.
_SAUBER = """
<style>
  body { width: 100%; max-width: 44rem; }
  .ok { min-width: 44px; min-height: 44px; }
  #eingabe { font-size: 16px; }
</style>
<div class="blase bot">Where does it happen?</div>
<div class="leiste"><button class="ok" type="button">x</button></div>
<input id="eingabe">
<button id="tot" type="button">Tot</button>
<script>
  document.addEventListener('click', function (ev) {
    var k = ev.target.closest('.leiste button, #tot');
    if (k) { document.body.appendChild(document.createElement('span')); }
  });
</script>
"""


@pytest.fixture()
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _seite(browser, html):
    page = browser.new_page()
    z.installiere_messung(page.context)
    page.set_content(html)
    return page


def test_seitliches_rutschen_wird_im_kaputten_stand_gemeldet(browser):
    assert z.seitliches_rutschen(_seite(browser, _KAPUTT)) is True


def test_seitliches_rutschen_bleibt_im_sauberen_stand_aus(browser):
    assert z.seitliches_rutschen(_seite(browser, _SAUBER)) is False


def test_zu_kleines_tippziel_wird_gemeldet(browser):
    treffer = z.tap_ziele_zu_klein(_seite(browser, _KAPUTT), selektor=".leiste button")
    assert len(treffer) == 1


def test_tippziel_im_sauberen_stand_ist_gross_genug(browser):
    assert z.tap_ziele_zu_klein(_seite(browser, _SAUBER), selektor=".leiste button") == []


def test_zu_kleine_eingabeschrift_wird_gemeldet(browser):
    treffer = z.eingabefeld_schrift_zu_klein(_seite(browser, _KAPUTT))
    assert len(treffer) == 1


def test_eingabeschrift_im_sauberen_stand_reicht(browser):
    assert z.eingabefeld_schrift_zu_klein(_seite(browser, _SAUBER)) == []


def test_mehrere_fragen_je_nachricht_wird_gemeldet(browser):
    treffer = z.mehrere_fragen_pro_nachricht(_seite(browser, _KAPUTT))
    assert len(treffer) == 1


def test_eine_frage_je_nachricht_ist_in_ordnung(browser):
    assert z.mehrere_fragen_pro_nachricht(_seite(browser, _SAUBER)) == []


def test_knopf_ohne_handler_wird_gemeldet(browser):
    treffer = z.knoepfe_ohne_wirkung(_seite(browser, _KAPUTT))
    assert any(t["text"] == "Tot" for t in treffer)


def test_verdrahteter_knopf_wird_nicht_gemeldet(browser):
    treffer = z.knoepfe_ohne_wirkung(_seite(browser, _SAUBER))
    assert treffer == []


def test_bot_text_waehrend_zuhoermodus_ist_ein_befund():
    assert z.bot_text_waehrend_zuhoermodus("brainstorm", ["Here's a thought..."]) is True
    assert z.bot_text_waehrend_zuhoermodus("brainstorm", []) is False
    assert z.bot_text_waehrend_zuhoermodus("chat", ["anything"]) is False


def test_entwickler_meta_findet_code_gerede():
    from simulation import browser_zaehler as z
    texte = ["keep tapping Accept -- or say 'accept all mine' and see if the code reads that",
             "Saved your questions.", "That is a bug on my side."]
    assert z.entwickler_meta(texte) == [texte[0], texte[2]]
    assert z.entwickler_meta(["Your opening is warm."]) == []
