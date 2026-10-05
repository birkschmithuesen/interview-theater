"""``Sammler.nimm`` gegen eine echte Seite -- eigene Datei, weil sie
Playwright braucht (``tests/test_browser_leitbilder.py`` bleibt rein und
laeuft unter $PY ohne Browser, siehe Package G)."""

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

from simulation import browser_leitbilder as lb  # noqa: E402

TOKEN = "AbC123tokenXYZ"


def _seite(phase: int) -> str:
    return (
        f'<div id="roadmap" data-aktive-phase="{phase}"></div>'
        '<p>Phase starts: the app explains what this phase is for.</p>'
    )


@pytest.fixture()
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def test_falsche_phase_in_der_kopfzeile_wird_abgelehnt(browser, tmp_path):
    seite = browser.new_page()
    seite.set_content(_seite(phase=2))
    sammler = lb.Sammler(token=TOKEN, geraet="handy", ziel=tmp_path)
    eintrag = sammler.nimm(seite, phase=1, station="eintritt")
    assert eintrag is None
    assert not list(tmp_path.glob("*.png"))


def test_richtige_phase_wird_genommen(browser, tmp_path):
    seite = browser.new_page()
    seite.set_content(_seite(phase=1))
    sammler = lb.Sammler(token=TOKEN, geraet="handy", ziel=tmp_path)
    eintrag = sammler.nimm(seite, phase=1, station="eintritt")
    assert eintrag is not None
    assert (tmp_path / eintrag["datei"]).exists()


def test_pixelgleiches_zweitbild_wird_abgelehnt(browser, tmp_path):
    seite = browser.new_page()
    seite.set_content(_seite(phase=1))
    sammler = lb.Sammler(token=TOKEN, geraet="handy", ziel=tmp_path)
    erstes = sammler.nimm(seite, phase=1, station="eintritt")
    assert erstes is not None
    # Dieselbe, unveraenderte Seite -- derselbe Bildinhalt, aber eine
    # andere Station, damit `_genommen` nicht schon vorher greift.
    zweites = sammler.nimm(seite, phase=1, station="kalibrierung")
    assert zweites is None
    assert len(list(tmp_path.glob("*.png"))) == 1


def test_veraendertes_zweitbild_wird_genommen(browser, tmp_path):
    seite = browser.new_page()
    seite.set_content(_seite(phase=1))
    sammler = lb.Sammler(token=TOKEN, geraet="handy", ziel=tmp_path)
    erstes = sammler.nimm(seite, phase=1, station="eintritt")
    assert erstes is not None
    seite.set_content(
        '<div id="roadmap" data-aktive-phase="1"></div>'
        '<p>A short microphone check before the group starts talking.</p>'
    )
    zweites = sammler.nimm(seite, phase=1, station="kalibrierung")
    assert zweites is not None
    assert len(list(tmp_path.glob("*.png"))) == 2
