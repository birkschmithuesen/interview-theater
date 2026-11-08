import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from simulation import browser_aktionen as a, browser_elemente  # noqa: E402

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
<div class="leiste"><button type="button" data-message="1" data-daten="k:7"
  onclick="document.body.dataset.chipGeklickt = '1';">Something else</button></div>
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


def test_click_trifft_das_element_per_id_nicht_den_ersten_treffer_der_seite(seite):
    """Realer Betriebsbefund (Padua-Abnahme): eine ``click``-Aktion ohne
    ``text`` landete auf ``locator("button, a, input").first`` -- dem
    Phasenknopf, nicht dem gemeinten Chip. ``element_id`` muss das Element
    aus der zuletzt extrahierten Liste treffen, egal welcher Knopf im DOM
    zuerst steht (hier steht der Phasenknopf spaeter, der Chip vorher --
    das allein darf das Ergebnis nicht entscheiden)."""
    elemente = browser_elemente.extrahiere(seite)
    chip = next(e for e in elemente if e["art"] == "chip")
    a.fuehre_aus(seite, {"type": "click", "element_id": chip["id"]})
    assert seite.evaluate("document.body.dataset.chipGeklickt") == "1"
    assert seite.locator(".phase-knopf").get_attribute("data-sicher") is None


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


def test_warte_auf_antwort_gibt_fertig_false_wenn_das_budget_abgelaufen_ist(seite):
    """Bleibt der Bot sichtbar aktiv, bis das Geduld-Budget ausgeht, ist das
    kein fertiges Ergebnis -- die Tippanzeige wird hier absichtlich nie
    geleert."""
    seite.evaluate(
        "document.getElementById('tippt').textContent = 'schreibt...';"
    )
    ergebnis = a.warte_auf_antwort(seite, geduld_s=1, anlauf_s=0.2)
    assert ergebnis["fertig"] is False


def test_tab_per_anzeigetext_trifft_den_data_tab(seite):
    protokoll = a.fuehre_aus(seite, {"type": "tab", "name": "Status"})
    assert protokoll == {"art": "tab", "ziel": "stand"}


def test_tab_per_data_tab_bleibt_unveraendert(seite):
    assert a.fuehre_aus(seite, {"type": "tab", "name": "stand"})["ziel"] == "stand"


_STEPPER = """
<div id="fehler" hidden></div>
<header class="phasenav" id="roadmap"><ol class="stepper">
  <li class="stepper-segment erledigt" data-phase="1" role="button">1</li>
  <li class="stepper-segment aktiv" data-phase="2" role="button">2</li>
</ol></header>
<div id="phasensheet" hidden><button id="phasensheet-los">go</button>
<button id="phasensheet-bleib">stay</button></div>
<script>
  window.__ablehnen = false;
  document.addEventListener('click', function (ev) {
    var s = ev.target.closest('.stepper-segment');
    if (s) { window.__ziel = s.dataset.phase; document.getElementById('phasensheet').hidden = false; return; }
    if (ev.target.id === 'phasensheet-los') {
      if (window.__ablehnen) {
        var f = document.getElementById('fehler'); f.textContent = 'Nope, no going back'; f.hidden = false;
      } else { document.body.dataset.gesprungen = window.__ziel;
        document.getElementById('phasensheet').hidden = true; }
    }
    if (ev.target.id === 'phasensheet-bleib') { document.getElementById('phasensheet').hidden = true; }
  });
</script>
"""


@pytest.fixture()
def stepper_seite():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 390, "height": 844})
        page.set_content(_STEPPER)
        yield page
        b.close()


def test_phase_nutzt_stepper_segment_und_bestaetigt_das_sheet(stepper_seite):
    protokoll = a.fuehre_aus(stepper_seite, {"type": "phase", "nummer": 1})
    assert protokoll["weg"] == "stepper"
    assert stepper_seite.evaluate("document.body.dataset.gesprungen") == "1"


def test_phase_abgelehnt_wird_als_befundausnahme_mit_servertext_gemeldet(stepper_seite):
    stepper_seite.evaluate("window.__ablehnen = true")
    with pytest.raises(a.PhasenwechselAbgelehnt, match="Nope, no going back"):
        a.fuehre_aus(stepper_seite, {"type": "phase", "nummer": 1})
    assert stepper_seite.locator("#phasensheet[hidden]").count() == 1


def test_phase_ohne_jedes_element_meldet_fehlendes_produktelement(seite):
    with pytest.raises(a.PhasenwechselFehlt, match="kein Element fuer Phase 7"):
        a.fuehre_aus(seite, {"type": "phase", "nummer": 7})
