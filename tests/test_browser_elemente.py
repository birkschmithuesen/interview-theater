import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from simulation import browser_elemente  # noqa: E402

_FIXTURE = """
<nav class="tabs" role="tablist">
  <button type="button" data-tab="chat" aria-selected="true">Chat</button>
  <button type="button" data-tab="stand" aria-selected="false">Status</button>
</nav>
<details class="roadmap" id="roadmap" data-aktive-phase="1">
  <summary>Phase 1/7</summary>
  <ol class="phasen"><li class="phase aktiv">
    <div class="phase-kopfzeile">
      <button type="button" class="phase-knopf" data-phase="2"
              data-bereit="0" data-fehlt="terms">2 - Questions</button>
    </div>
  </li></ol>
</details>
<div class="verlauf" id="verlauf">
  <div class="blase bot" data-id="1">Hello, what terms did you collect?</div>
</div>
<div class="leiste" data-message="1">
  <button type="button" data-message="1" data-daten="k:7">Something else</button>
</div>
<input id="eingabe" placeholder="Type or speak...">
<button id="senden" type="button">Send</button>
<button id="interview" hidden>Start interview</button>
<div style="display:none"><button data-tab="hidden-tab">unsichtbar</button></div>
"""


@pytest.fixture(scope="module")
def seite():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(_FIXTURE)
        yield page
        browser.close()


def test_sichtbare_elemente_werden_gefunden(seite):
    elemente = browser_elemente.extrahiere(seite)
    arten = {(e["art"], e["text"]) for e in elemente}
    assert ("tab", "Chat") in arten
    assert ("tab", "Status") in arten
    assert ("phase", "2 - Questions") in arten
    assert ("chip", "Something else") in arten
    assert ("senden", "Send") in arten
    assert ("eingabe", "") in arten


def test_versteckte_elemente_fehlen(seite):
    elemente = browser_elemente.extrahiere(seite)
    texte = {e["text"] for e in elemente}
    assert "unsichtbar" not in texte
    assert not any(e["art"] == "interview" for e in elemente)  # hidden


def test_data_attribute_kommen_mit(seite):
    elemente = browser_elemente.extrahiere(seite)
    phase = next(e for e in elemente if e["art"] == "phase")
    assert phase["phase"] == "2"
    assert phase["bereit"] == "0"
    assert phase["fehlt"] == "terms"
    chip = next(e for e in elemente if e["art"] == "chip")
    assert chip["message"] == "1"
    assert chip["daten"] == "k:7"
    eingabe = next(e for e in elemente if e["art"] == "eingabe")
    assert eingabe["placeholder"] == "Type or speak..."


def test_bildschirmfoto_liefert_png_bytes(seite):
    bild = browser_elemente.bildschirmfoto(seite)
    assert bild[:8] == b"\x89PNG\r\n\x1a\n"
