import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from simulation import browser_aktionen as a  # noqa: E402

_FIXTURE = """
<div id="verlauf"></div>
<div id="tippt"></div>
<input id="eingabe">
<button id="senden" type="button" onclick="
  document.getElementById('verlauf').innerHTML =
    '<div class=\\'blase gruppe\\'>' + document.getElementById('eingabe').value + '</div>';
  document.getElementById('eingabe').value = '';
"></button>
<nav class="tabs"><button data-tab="stand">Status</button></nav>
<details class="roadmap"><summary>Phase 1/7</summary>
<div class="phase-kopfzeile">
  <button class="phase-knopf" data-phase="2" data-bereit="0">2 - Questions</button>
</div>
</details>
<script>
  var knopf = document.querySelector('.phase-knopf');
  knopf.addEventListener('click', function () {
    if (knopf.getAttribute('data-sicher') === '1') {
      knopf.dataset.gesprungen = '1';
      return;
    }
    knopf.setAttribute('data-sicher', '1');
  });
</script>
"""


@pytest.fixture()
def seite():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.set_content(_FIXTURE)
        yield page
        b.close()


def test_type_send_fuellt_und_sendet(seite):
    a.fuehre_aus(seite, {"type": "type_send", "text": "hello"})
    assert seite.locator(".blase.gruppe").text_content() == "hello"


def test_tab_klickt_den_passenden_tab(seite):
    protokoll = a.fuehre_aus(seite, {"type": "tab", "name": "stand"})
    assert protokoll["art"] == "tab"


def test_phase_oeffnet_die_geschlossene_roadmap_und_klickt_zweimal_wenn_unbereit(seite):
    """Die Roadmap ist zu Beginn geschlossen (wie auf der echten Seite) --
    die Aktion muss sie trotzdem treffen, ohne vorher ``summary`` zu klicken."""
    assert seite.locator("details.roadmap").get_attribute("open") is None
    a.fuehre_aus(seite, {"type": "phase", "nummer": 2})
    assert seite.locator(".phase-knopf").get_attribute("data-gesprungen") == "1"


def test_unbekannte_aktion_wirft(seite):
    with pytest.raises(a.UnbekannteAktion):
        a.fuehre_aus(seite, {"type": "foo"})


def test_warte_auf_antwort_ohne_aktivitaet_kehrt_schnell_zurueck(seite):
    ergebnis = a.warte_auf_antwort(seite, geduld_s=10, anlauf_s=1)
    assert ergebnis["fertig"] is True
    assert ergebnis["sekunden"] < 5


def test_warte_auf_antwort_wartet_auf_das_ende_der_tippanzeige(seite):
    seite.evaluate(
        "document.getElementById('tippt').textContent = 'schreibt...';"
        "setTimeout(function () {"
        "  document.getElementById('tippt').textContent = '';"
        "}, 500);"
    )
    ergebnis = a.warte_auf_antwort(seite, geduld_s=10, anlauf_s=1)
    assert ergebnis["fertig"] is True
    assert ergebnis["ohne_hinweis"] is False
