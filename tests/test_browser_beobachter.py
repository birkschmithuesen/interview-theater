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
    beob.schliesse()


def test_reload_wird_erkannt(browser, monkeypatch):
    monkeypatch.setattr(bb, "_vor_goto", _route)
    beob = bb.Beobachter.oeffne(browser, "http://sim.test/g/x")
    beob.page.reload()
    assert beob.neu_geladen is True
    assert beob.ergebnis()["board_bestanden"] is False
    beob.schliesse()
