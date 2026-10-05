import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from simulation import browser_beobachter as bb  # noqa: E402

_SEITE = """<!doctype html><nav class="tabs">
<button data-tab="chat">Chat</button><button data-tab="buehne">CoThinker</button></nav>
<ol class="begriffsboard"></ol>
<script>
document.querySelector('[data-tab=buehne]').onclick = () => { location.hash = 'buehne'; };
setTimeout(() => { document.querySelector('.begriffsboard').innerHTML =
  '<li data-begriff="home">home</li><li data-begriff="border">border</li>'; }, 400);
</script>"""


@pytest.fixture()
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _route(context):
    context.route("http://sim.test/**", lambda r: r.fulfill(
        status=200, content_type="text/html", body=_SEITE))


def test_board_waechst_ohne_reload(browser, monkeypatch):
    monkeypatch.setattr(bb, "_vor_goto", _route)
    beob = bb.Beobachter.oeffne(browser, "http://sim.test/g/x")
    beob.messe()  # je nach Timing 0 oder 2
    beob.page.wait_for_timeout(700)
    assert beob.messe() == 2
    ergebnis = beob.ergebnis()
    assert ergebnis["board_bestanden"] is True
    assert ergebnis["beobachter_neu_geladen"] is False
    assert beob.begriffe() == ("home", "border")
    beob.schliesse()


_SEITE_VERSTECKT = """<!doctype html><nav class="tabs">
<button data-tab="chat">Chat</button><button data-tab="buehne" hidden>CoThinker</button></nav>
<ol class="begriffsboard"></ol>
<script>
document.querySelector('[data-tab=buehne]').onclick = () => { location.hash = 'buehne'; };
</script>"""


def test_versteckter_tab_blockiert_nicht_und_wird_spaeter_gewaehlt(browser, monkeypatch):
    """P34 startet in Phase 3: dort ist der CoThinker-Tab ``hidden``. Das
    Oeffnen darf nicht 30 s auf einen Klick warten und abbrechen; sobald der
    Tab sichtbar ist (Phase 4), waehlt ``messe`` ihn -- ohne Neuladen."""
    def route(context):
        context.route("http://sim.test/**", lambda r: r.fulfill(
            status=200, content_type="text/html", body=_SEITE_VERSTECKT))
    monkeypatch.setattr(bb, "_vor_goto", route)
    beob = bb.Beobachter.oeffne(browser, "http://sim.test/g/x")
    assert not beob.page.url.endswith("#buehne")
    beob.messe()
    assert not beob.page.url.endswith("#buehne")
    # Phasenwechsel nach 4: die App macht den Tab sichtbar.
    beob.page.evaluate("document.querySelector('[data-tab=buehne]').hidden = false")
    beob.messe()
    assert beob.page.url.endswith("#buehne")
    assert beob.neu_geladen is False
    beob.schliesse()


def test_reload_wird_erkannt(browser, monkeypatch):
    monkeypatch.setattr(bb, "_vor_goto", _route)
    beob = bb.Beobachter.oeffne(browser, "http://sim.test/g/x")
    beob.page.reload()
    assert beob.neu_geladen is True
    assert beob.ergebnis()["board_bestanden"] is False
    beob.schliesse()
