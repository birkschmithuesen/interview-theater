"""Karte t_cb2c4678, Aufgabe 6 (angepasst in der Design-Erweiterung,
04.10.2026): das Begriffsboard sortiert im echten Browser um, ohne zu
springen (D3). Ein echter Webserver-Prozess unter
``IT_WORKSHOP=padua-2026`` (sonst gibt es kein Board), eine Gruppe in
Phase 1, ein Board A; der Test legt ein umsortiertes Board B mit einer
Schaerfung ("Roboter" -> "KI-Roboter") in die Datenbank und wartet auf den
naechsten ``ladeBuehne()``-Takt. Nachgewiesen werden die Wirkungen der
Zuordnung: die verschobene und die geschaerfte Zeile bekommen ein
``translateY`` (mit reduzierter Bewegung: keins), und die alte Fassung
steht als ``<del>``. Seit der Design-Erweiterung gibt es kein
aufklappbares "Warum" mehr -- dieser Lauf klickt keins mehr an.

Ohne Playwright wird die Datei uebersprungen (``importorskip``). Der
Handy-Schuss landet immer unter /tmp und nur mit
``IT_SCHUSS_AKTUALISIEREN=1`` im Repository (Muster
``test_web_cothinker_status_screenshot_e2e.py``). Nur erfundenes Material.

**Vorher-Referenz der Design-Erweiterung:** der Screenshot, den dieser
Test erzeugt (mit ``IT_SCHUSS_AKTUALISIEREN=1``, zuletzt am 04.10.2026 VOR
der Design-Erweiterung gelaufen), liegt unter
``docs/web-begriffsboard/ranking-2026-10-04.png`` -- NICHT erneut mit
``IT_SCHUSS_AKTUALISIEREN=1`` laufen lassen, solange diese Datei als
"Vorher"-Beleg gilt (siehe ``docs/superpowers/plans/2026-10-04-padua-begriffsboard-design.md``,
Aufgabe 5)."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
from playwright.sync_api import sync_playwright  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo  # noqa: E402

DB_PFAD = "/tmp/it-bb-ranking.db"
AUDIO = "/tmp/it-bb-ranking-audio"
SERVERLOG = "/tmp/it-bb-ranking-server.log"
CHAT = 7_000_000_000_101
HANDY = {"width": 390, "height": 844}
SCHUSS = WURZEL / "docs" / "web-begriffsboard" / "ranking-2026-10-04.png"
SCHUSS_TMP = Path("/tmp/it-bb-ranking/ranking-2026-10-04.png")
GEDULD_MS = 30_000


def _e(begriff, status, zustimmung, nennungen, begruendung, vorgaenger=None):
    eintrag = {"begriff": begriff, "nennungen": nennungen, "zustimmung": zustimmung,
               "begruendung": begruendung, "zitat": "", "doppelbedeutung": "",
               "status": status}
    if vorgaenger:
        eintrag["vorgaenger"] = vorgaenger
    return eintrag


BOARD_A = [
    _e("Heimat", "favorit", 2, 3, "Alle wollen ueber Zuhause reden."),
    _e("Grenze", "kandidat", 1, 2, "Eine Grenze kann auch im Kopf sein."),
    _e("Roboter", "kandidat", 0, 1, "Einer will eine Maschine auf der Buehne."),
]
BOARD_B = [
    _e("KI-Roboter", "favorit", 2, 4,
       "Zuerst als 'Roboter' genannt, spaeter geschaerft auf 'KI-Roboter'.", ["Roboter"]),
    _e("Heimat", "kandidat", 1, 3, "Alle wollen ueber Zuhause reden."),
    _e("Grenze", "kandidat", 1, 2, "Eine Grenze kann auch im Kopf sein."),
]

#: Zeichnet jedes inline gesetzte ``transform`` einer Boardzeile auf -- im
#: Test, nicht im Produktivcode.
_BEOBACHTER = """() => {
  window.__bbTransforms = {};
  new MutationObserver(function (ms) {
    ms.forEach(function (m) {
      var t = m.target;
      if (t.matches && t.matches('li[data-begriff]') && t.style.transform) {
        window.__bbTransforms[t.getAttribute('data-begriff')] = t.style.transform;
      }
    });
  }).observe(document.getElementById('tab-buehne'),
             { subtree: true, attributes: true, attributeFilter: ['style'] });
}"""


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _baue_datenbank() -> str:
    for endung in ("", "-wal", "-shm"):
        Path(DB_PFAD + endung).unlink(missing_ok=True)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "rankingbot", "Rankinggruppe")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 1)
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(BOARD_A), "sovereign", 0)
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.close()
    return token


def _lege_board_b() -> None:
    conn = db.verbinde(DB_PFAD)
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(BOARD_B), "sovereign", 0)
    conn.close()


def _warte_auf_server(prozess, basis: str, sekunden: float = 15.0) -> None:
    ende = time.time() + sekunden
    while time.time() < ende:
        if prozess.poll() is not None:
            raise RuntimeError(f"Der Webserver ist abgestuerzt, siehe {SERVERLOG}.")
        try:
            with urllib.request.urlopen(f"{basis}/gesund", timeout=1) as antwort:
                if antwort.read().decode().strip() == "ok":
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError("Der Webserver ist nicht hochgekommen.")


@pytest.fixture
def server():
    token = _baue_datenbank()
    bind = f"127.0.0.1:{_freier_port()}"
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD, "IT_WEB_BIND": bind, "IT_WEB_PREFIX": "", "IT_AUDIO": AUDIO,
        "IT_WORKSHOP": "padua-2026", "PYTHONPATH": str(WURZEL),
    })
    log = open(SERVERLOG, "w")
    prozess = subprocess.Popen(
        [sys.executable, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        basis = f"http://{bind}"
        _warte_auf_server(prozess, basis)
        yield basis, token
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=5)
        except subprocess.TimeoutExpired:
            prozess.kill()
        log.close()


def _lauf(basis, token, *, ruhig: bool, schuss: bool):
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            kontext = chromium.new_context(
                viewport=HANDY, is_mobile=True,
                reduced_motion="reduce" if ruhig else "no-preference",
            )
            seite = kontext.new_page()
            seite.set_default_timeout(GEDULD_MS)
            seite.goto(f"{basis}/g/{token}#buehne")
            seite.wait_for_selector('#tab-buehne li[data-begriff="Roboter"]', state="visible")
            seite.evaluate(_BEOBACHTER)
            _lege_board_b()
            seite.wait_for_selector('#tab-buehne li[data-begriff="KI-Roboter"]', state="visible")
            seite.wait_for_timeout(600)   # FLIP-Dauer (320 ms) plus Luft

            neu = seite.locator('#tab-buehne li[data-begriff="KI-Roboter"]')
            assert neu.get_attribute("data-vorgaenger") == "Roboter"
            assert neu.locator(".vorgaenger del").inner_text() == "Roboter"
            assert seite.locator('#tab-buehne li[data-begriff="Roboter"]').count() == 0
            reihenfolge = seite.eval_on_selector_all(
                "#tab-buehne ol.begriffsboard > li", "els => els.map(e => e.dataset.begriff)")
            assert reihenfolge == ["KI-Roboter", "Heimat", "Grenze"]
            assert seite.locator("#tab-buehne details").count() == 0

            transforms = seite.evaluate("() => window.__bbTransforms")
            if ruhig:
                assert transforms == {}
            else:
                assert transforms.get("KI-Roboter", "").startswith("translateY(")
                assert transforms.get("Heimat", "").startswith("translateY(")
            # Die Bewegung ist vorbei: keine Zeile bleibt verschoben stehen.
            assert seite.eval_on_selector_all(
                "#tab-buehne ol.begriffsboard > li",
                "els => els.every(e => !e.style.transform)") is True

            if schuss:
                SCHUSS_TMP.parent.mkdir(parents=True, exist_ok=True)
                seite.screenshot(path=str(SCHUSS_TMP), full_page=False)
                assert SCHUSS_TMP.stat().st_size > 1000
                if os.environ.get("IT_SCHUSS_AKTUALISIEREN") == "1":
                    SCHUSS.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(SCHUSS_TMP, SCHUSS)
            kontext.close()
        finally:
            chromium.close()


def test_board_sortiert_um_ohne_zu_springen_und_zeigt_die_schaerfung(server):
    basis, token = server
    _lauf(basis, token, ruhig=False, schuss=True)


def test_reduzierte_bewegung_ohne_animation_aber_mit_offenem_warum(server):
    basis, token = server
    _lauf(basis, token, ruhig=True, schuss=False)
