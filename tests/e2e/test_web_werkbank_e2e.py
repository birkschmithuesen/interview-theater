"""Die read-only Werkbank im echten Chromium (Padua, 03.10.2026).

Drei erfundene Web-Gruppen in Phase 1, 3 und 5 unter ``IT_WORKSHOP=padua-2026``:
kein Eingabeelement im Arbeitsstand, die aktuelle Phase aufgeklappt, die
sieben Phasen in Reihenfolge, jeder sichtbare Text mit Kontrast -- und die
Screenshots fuer Birk (Telefon 390x844 und Laptop).

**Nur erfundenes Material**, nie ``betrieb/``. Die Screenshots landen bei
jedem Lauf unter ``/tmp/it-werkbank-shots/``, ins Repository
(``docs/ux-padua/workbench/``) nur mit ``IT_SCHUSS_AKTUALISIEREN=1``.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_werkbank_e2e.py -q
"""

import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parents[2]
DB_PFAD = "/tmp/it-werkbank.db"
SCHUSS = pathlib.Path("/tmp/it-werkbank-shots")
SCHUSS_REPO = WURZEL / "docs" / "ux-padua" / "workbench"
HANDY = {"width": 390, "height": 844}
LAPTOP = {"width": 1366, "height": 900}
GRUPPEN = {1: 7_000_000_000_201, 3: 7_000_000_000_203, 5: 7_000_000_000_205}

from test_web_gestalt_e2e import _ALLE_TEXTE, _HELLIGKEIT  # noqa: E402


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


BIND = f"127.0.0.1:{_freier_port()}"


def _baue_datenbank() -> dict[int, str]:
    sys.path.insert(0, str(WURZEL))
    from interview_theater import db, repo

    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    tokens = {}
    for phase, chat in GRUPPEN.items():
        repo.sichere_gruppe(conn, chat, f"padua_bot{phase}", f"Workbench {phase}")
        repo.setze_gruppe_kanal(conn, chat, "web")
        repo.setze_arbeitsstand(conn, chat, "begriffe", "bridge, market, rain, courage")
        if phase >= 3:
            for feld, wert in (
                ("fragen", "1. Where do you feel at home?\n2. Who do you argue with?\n"
                           "3. What gives you courage?"),
                ("fragen_weich", ""),
                ("interview_eroeffnung", "Hi, we are a youth theatre group."),
                ("interview_abschluss", "Thank you very much."),
            ):
                repo.setze_arbeitsstand(conn, chat, feld, wert)
            for nummer, verdichtet in ((1, True), (2, False)):
                aid = repo.lege_aufnahme_an(conn, chat, 10 + nummer, "lang", "sprache",
                                            status="fertig")
                repo.setze_transkript(conn, aid, f"Invented talk {nummer}. Home is the bridge.")
                if verdichtet:
                    repo.speichere_verdichtung(conn, chat, aid, "She talks about the bridge.", [
                        {"thema": "home", "beleg_zitat": "Home is the bridge.",
                         "zitat_geprueft": 1, "kurz": "home"}])
        if phase >= 5:
            repo.setze_arbeitsstand(conn, chat, "rahmen", "A bus stop at night.")
            repo.setze_arbeitsstand(conn, chat, "geschichte",
                                    "Nadia wants to leave; Tomas wants her to stay.")
            repo.setze_figur(conn, chat, "Nadia", "the older sister, restless")
            repo.setze_figur(conn, chat, "Tomas", "the younger brother, stubborn")
            repo.schreibe_festlegung(conn, chat, "sonstiges", "Nobody dies.", quelle="befehl")
            for nummer, titel, prosa in ((1, "Last bus", "Nadia waits at the stop."),
                                         (2, "One more night", None)):
                sid = repo.lege_szene_an(conn, chat, nummer, titel, None, None)
                if prosa:
                    repo.aktualisiere_szene(conn, sid, titel, None, None, prosa=prosa)
        repo.setze_phase(conn, chat, phase)
        tokens[phase] = repo.stelle_web_token_sicher(conn, chat)
    conn.commit()
    conn.close()
    return tokens


@pytest.fixture(scope="module")
def dienst():
    tokens = _baue_datenbank()
    SCHUSS.mkdir(parents=True, exist_ok=True)
    umgebung = dict(os.environ, IT_DB=DB_PFAD, IT_WEB_BIND=BIND, IT_WEB_PREFIX="",
                    IT_WORKSHOP="padua-2026")
    umgebung.pop("IT_UX_ENTWURF", None)
    prozess = subprocess.Popen(
        [sys.executable, "-m", "interview_theater.web"], cwd=WURZEL, env=umgebung)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://{BIND}/gesund", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    yield f"http://{BIND}", tokens
    prozess.terminate()
    prozess.wait(timeout=10)


def _oeffne(browser, basis, token, viewport=HANDY):
    seite = browser.new_page(viewport=viewport)
    seite.goto(f"{basis}/g/{token}#stand")
    seite.wait_for_selector("#tab-stand:not([hidden])")
    return seite


@pytest.mark.parametrize("phase", sorted(GRUPPEN))
def test_die_werkbank_ist_reine_anzeige(dienst, phase):
    basis, tokens = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = _oeffne(browser, basis, tokens[phase])
        elemente = "#tab-stand :is(input, select, textarea, button, [contenteditable])"
        assert seite.locator(elemente).count() == 0
        offen = seite.locator("#tab-stand details.wb-phase[open]")
        assert offen.count() == 1
        assert offen.first.get_attribute("data-wb-phase") == str(phase)
        reihenfolge = seite.eval_on_selector_all(
            "#tab-stand details.wb-phase", "els => els.map(e => e.dataset.wbPhase)")
        assert reihenfolge == [str(n) for n in range(1, 8)]
        browser.close()


@pytest.mark.parametrize("viewport", [HANDY, LAPTOP], ids=["handy", "laptop"])
def test_jeder_sichtbare_text_hat_kontrast(dienst, viewport):
    basis, tokens = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for token in tokens.values():
            seite = _oeffne(browser, basis, token, viewport)
            seite.wait_for_timeout(500)
            schlecht = seite.evaluate(_ALLE_TEXTE, _HELLIGKEIT)
            assert not schlecht, schlecht
            seite.close()
        browser.close()


def test_screenshots(dienst):
    """Telefon und Laptop je Phase 1, 3, 5 -- fuer Birk."""
    basis, tokens = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for phase, token in sorted(tokens.items()):
            for geraet, viewport in (("handy", HANDY), ("laptop", LAPTOP)):
                seite = _oeffne(browser, basis, token, viewport)
                seite.wait_for_timeout(400)
                seite.screenshot(path=str(SCHUSS / f"werkbank-phase{phase}-{geraet}.png"))
                seite.close()
        browser.close()
    dateien = sorted(SCHUSS.glob("werkbank-phase*.png"))
    assert len(dateien) == 6
    for datei in dateien:
        assert datei.stat().st_size > 5_000, datei
    if os.environ.get("IT_SCHUSS_AKTUALISIEREN") == "1":
        SCHUSS_REPO.mkdir(parents=True, exist_ok=True)
        for datei in dateien:
            shutil.copyfile(datei, SCHUSS_REPO / datei.name)
