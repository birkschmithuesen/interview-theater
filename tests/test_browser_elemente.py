import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from simulation import browser_elemente  # noqa: E402


def test_kein_eigener_brainstorm_selektor_mehr():
    """Birk 05.10.2026 22:00: kein Toggle-Knopf mehr -- ``#brainstorm``
    existiert im Markup nicht mehr (Phase 4 bedient sich ueber
    ``#diskussion``, das schon einen eigenen Eintrag hat). Der Stationstyp
    "brainstorm" (``Station.aufnahme``) bleibt unabhaengig davon stehen."""
    assert not any(selektor == "#brainstorm" for _art, selektor in browser_elemente._ARTEN)

#: Realistischer Default-Zustand: die Roadmap ist ein ``<details>`` OHNE
#: ``open`` -- exakt wie ``web_vereint._leiste_html`` sie serverseitig
#: ausliefert (Zeile ~1062). Nur die ``<summary>`` ist dann sichtbar, der
#: ``.phase-knopf`` darunter nicht -- das ist der Fall, den ein echter
#: Playwright-Klick mit "element is not visible" quittiert.
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

#: Derselbe Ausschnitt, aber mit ``open`` -- der Zustand NACH einem Klick auf
#: die Zusammenfassung. Eine eigene Fixture statt eines ``page.evaluate``,
#: damit die beiden Zustaende nicht an derselben, modulweiten Seite kleben.
_FIXTURE_OFFEN = """
<details class="roadmap" id="roadmap" data-aktive-phase="1" open>
  <summary>Phase 1/7</summary>
  <ol class="phasen"><li class="phase aktiv">
    <div class="phase-kopfzeile">
      <button type="button" class="phase-knopf" data-phase="2"
              data-bereit="0" data-fehlt="terms">2 - Questions</button>
    </div>
  </li></ol>
</details>
"""


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture(scope="module")
def seite(browser):
    page = browser.new_page()
    page.set_content(_FIXTURE)
    yield page
    page.close()


@pytest.fixture(scope="module")
def seite_offen(browser):
    page = browser.new_page()
    page.set_content(_FIXTURE_OFFEN)
    yield page
    page.close()


def test_sichtbare_elemente_werden_gefunden(seite):
    elemente = browser_elemente.extrahiere(seite)
    arten = {(e["art"], e["text"]) for e in elemente}
    assert ("tab", "Chat") in arten
    assert ("tab", "Status") in arten
    assert ("chip", "Something else") in arten
    assert ("senden", "Send") in arten
    assert ("eingabe", "") in arten


def test_roadmap_oeffnen_ist_immer_sichtbar(seite):
    """Die ``<summary>`` ist nie vom "Inhalt eines geschlossenen
    ``<details>`` ist unsichtbar"-Verhalten betroffen -- sie ist der einzige
    Weg, die Roadmap ueberhaupt aufzuklappen."""
    elemente = browser_elemente.extrahiere(seite)
    arten = {(e["art"], e["text"]) for e in elemente}
    assert ("roadmap_oeffnen", "Phase 1/7") in arten


def test_phase_knopf_fehlt_solange_roadmap_geschlossen_ist(seite):
    """Die Karte dieses Fixes: ein ``.phase-knopf`` in einem ``<details>``
    OHNE ``open`` ist nicht klickbar -- ein echter Playwright-Klick wuerde
    hier mit "element is not visible" scheitern, also darf er auch in der
    extrahierten Liste nicht auftauchen."""
    elemente = browser_elemente.extrahiere(seite)
    assert not any(e["art"] == "phase" for e in elemente)


def test_phase_knopf_erscheint_wenn_roadmap_offen_ist(seite_offen):
    """Gegenstueck: dieselbe Struktur, aber mit ``open`` -- der Zustand nach
    einem Klick auf die Zusammenfassung -- liefert den Knopf samt seinen
    ``data-*``-Attributen."""
    elemente = browser_elemente.extrahiere(seite_offen)
    phase = next(e for e in elemente if e["art"] == "phase")
    assert phase["text"] == "2 - Questions"
    assert phase["phase"] == "2"
    assert phase["bereit"] == "0"
    assert phase["fehlt"] == "terms"


def test_versteckte_elemente_fehlen(seite):
    elemente = browser_elemente.extrahiere(seite)
    texte = {e["text"] for e in elemente}
    assert "unsichtbar" not in texte
    assert not any(e["art"] == "interview" for e in elemente)  # hidden


def test_data_attribute_kommen_mit(seite):
    elemente = browser_elemente.extrahiere(seite)
    chip = next(e for e in elemente if e["art"] == "chip")
    assert chip["message"] == "1"
    assert chip["daten"] == "k:7"
    eingabe = next(e for e in elemente if e["art"] == "eingabe")
    assert eingabe["placeholder"] == "Type or speak..."


def test_bildschirmfoto_liefert_png_bytes(seite):
    bild = browser_elemente.bildschirmfoto(seite)
    assert bild[:8] == b"\x89PNG\r\n\x1a\n"


_FIXTURE_ZUHOEREN = """
<button id="diskussion" data-laeuft="0">Start listening</button>
<button id="diskussion-beenden">Discussion done</button>
<div id="kalibrierung"><button id="kalibrierung-start">Start check</button>
<button id="kalibrierung-skip">Skip</button></div>
"""


def test_zuhoeren_und_kalibrierung_stehen_in_der_elementliste(browser):
    # Eigene Seite auf dem modulweiten ``browser`` statt eines zweiten,
    # verschachtelten ``sync_playwright()``: zwei gleichzeitig offene
    # Sync-API-Kontexte im selben Thread (hier der ``browser``-Fixture oben,
    # die bis zum Modulende offen bleibt) wirft zuverlaessig "Sync API
    # inside the asyncio loop" -- unabhaengig vom Seiteninhalt.
    page = browser.new_page()
    page.set_content(_FIXTURE_ZUHOEREN)
    arten = {e["art"] for e in browser_elemente.extrahiere(page)}
    page.close()
    assert {"diskussion", "diskussion_beenden", "kalibrierung_start",
            "kalibrierung_skip"} <= arten


#: Abnahme P1-2, Fortsetzung (05.10.2026, echter Browserlauf nach dem Merge
#: von main): ``[web] phasennav_stepper = true`` ist jetzt fuer Padua aktiv
#: und ersetzt die alte ``<details class="roadmap">`` vollstaendig durch
#: dieses ``<header id="roadmap" data-stepper="1">`` -- die Persona konnte
#: weder die Stepper-Segmente noch das Bestaetigungsblatt sehen, das
#: Blatt blieb nach einem Klick offen und blockierte jeden weiteren Klick
#: (30s-Timeout, Lauf scheiterte an einer spaeteren Station).
_FIXTURE_STEPPER = """
<header class="phasenav" id="roadmap" data-stepper="1" data-aktive-phase="2">
  <ol class="stepper" role="list">
    <li class="stepper-segment erledigt" data-phase="1"
        data-bezeichnung="1 Terms" data-satz="" data-bereit="1" data-fehlt=""
        role="button" tabindex="0" aria-label="1 Terms">
      <span class="stepper-marke">✓</span>
    </li>
    <li class="stepper-segment aktiv" data-phase="2"
        data-bezeichnung="2 Questions" data-satz="" data-bereit="1"
        data-fehlt="" role="button" tabindex="0" aria-label="2 Questions">
      <span class="stepper-marke">2</span>
    </li>
  </ol>
  <div class="phasenav-zeile">
    <button type="button" class="phasenav-zurueck" data-phase="1"
            data-bezeichnung="1 Terms" data-satz="" data-bereit="1"
            data-fehlt="">&lsaquo; 1 Terms</button>
    <span class="phasenav-aktuell">2 Questions</span>
    <button type="button" class="phasenav-vor" data-phase="3"
            data-bezeichnung="3 Interviews" data-satz="" data-bereit="0"
            data-fehlt="guide">3 Interviews &rsaquo;</button>
  </div>
</header>
<div class="sheet" id="phasensheet" hidden role="dialog" aria-modal="true">
  <div class="sheet-hintergrund"></div>
  <div class="sheet-inhalt">
    <h3 id="phasensheet-titel"></h3>
    <div class="sheet-knoepfe">
      <button type="button" id="phasensheet-los">Go</button>
      <button type="button" id="phasensheet-bleib">Stay here</button>
    </div>
  </div>
</div>
"""


def test_stepper_segmente_und_pfeile_stehen_in_der_elementliste(browser):
    page = browser.new_page()
    page.set_content(_FIXTURE_STEPPER)
    elemente = browser_elemente.extrahiere(page)
    page.close()
    arten = {e["art"] for e in elemente}
    assert {"stepper_segment", "phasenav_pfeil"} <= arten
    segment = next(e for e in elemente if e["art"] == "stepper_segment"
                   and e["phase"] == "2")
    assert segment["bereit"] == "1"


def test_phasensheet_knoepfe_fehlen_solange_das_blatt_geschlossen_ist(browser):
    page = browser.new_page()
    page.set_content(_FIXTURE_STEPPER)
    arten = {e["art"] for e in browser_elemente.extrahiere(page)}
    page.close()
    assert "phasensheet_bleib" not in arten
    assert "phasensheet_los" not in arten


def test_phasensheet_bleib_erscheint_wenn_das_blatt_offen_ist(browser):
    page = browser.new_page()
    page.set_content(_FIXTURE_STEPPER.replace(
        '<div class="sheet" id="phasensheet" hidden',
        '<div class="sheet" id="phasensheet"'))
    elemente = browser_elemente.extrahiere(page)
    page.close()
    arten = {e["art"] for e in elemente}
    assert {"phasensheet_bleib", "phasensheet_los"} <= arten
