"""Phasenscroll-Karte (04.10.2026, t_abc12cf7): nach einem Phasenwechsel
zeigt der Chat den Anfang der neuen Phase, nicht das Ende des ganzen
(ungetrennten) Verlaufs.

Geprueft wird das auf der VEREINTEN Seite (``/g/<token>``, Chat-Tab) --
``/g/<token>/chat`` leitet seit Karte W per 302 dorthin um
(``web.py::_beantworte_gruppenseite``), und nur dort hat ``#verlauf`` ein
eigenes ``scrollTop`` (``web_vereint._css_schale``/Mobile-App-Shell); auf
einer Chat-Einzelseite wuerde das Dokument scrollen.

Was ``tests/test_web_chat_js.py`` nicht leistet: ob ein echter Browser nach
einem ueber den Poll ankommenden Phasenwechsel wirklich die neue Phasenzeile
ins Bild holt, statt wie bisher ans Ende zu springen.
"""

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
from playwright.sync_api import expect, sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, phasentexte, repo  # noqa: E402

DB_PFAD = "/tmp/it-phasenscroll.db"
AUDIO = "/tmp/it-phasenscroll-audio"
SERVERLOG = "/tmp/it-phasenscroll-server.log"
CHAT = 7_000_000_000_050

#: Zwei Sekunden Polltakt (``web_chat.POLL_MS``) -- mit etwas Spielraum
#: fuer den Subprozess-Server auf einer evtl. ausgelasteten Maschine.
POLL_WARTEN_S = 3.0

HANDY = {"width": 390, "height": 844}

SCHUSS_VERZEICHNIS = WURZEL / "docs" / "ux-padua" / "chat-zoom"


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _baue_datenbank() -> str:
    """Eine Web-Gruppe in Phase 2, mit einem langen (erfundenen) Verlauf,
    der den sichtbaren Bereich eines Handys klar uebersteigt."""
    for endung in ("", "-wal", "-shm"):
        pfad = DB_PFAD + endung
        if os.path.exists(pfad):
            os.remove(pfad)
    shutil.rmtree(AUDIO, ignore_errors=True)

    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "schussbot", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 2)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Ankommen, Arbeit, Nacht")
    repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
        text=phasentexte.eintritt(conn, CHAT, 2),
    )
    for i in range(1, 36):
        repo.lege_web_post_an(
            conn, CHAT,
            repo.RICHTUNG_EIN if i % 2 else repo.RICHTUNG_AUS,
            repo.WEB_TYP_TEXT,
            text=f"Erfundene Verlaufszeile Nummer {i}.",
        )
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.close()
    return token


def _wechsle_zu_phase_3() -> None:
    """Simuliert, was der Bot beim Phasenwechsel tut (``knoepfe.eintritt_in_
    phase`` -> ``stationen._sende_karte`` (Bild) + ``phasentexte.eintritt``
    + eine Bot-Zeile) -- OHNE Bot-Prozess, direkt gegen dieselbe Datenbank,
    waehrend die Seite schon offen ist und pollt.

    Vor der Kopfzeile steht die Telefon-Organisationskarte als eigene Blase
    mit Bild (``bild=phase-3.png``) -- genau wie ``stationen.eintritt_in_
    phase`` sie IMMER vor der Kopfzeile sendet. Nach der Kopfzeile stehen
    noch ein paar weitere, erfundene Zeilen -- sonst waere die Kopfzeile
    zugleich die JUENGSTE Nachricht im Verlauf, und ``nachUnten()`` (das
    alte, falsche Verhalten) traefe sie dann zufaellig genauso wie der Fix:
    der Test muss "Anfang der neuen Phase" von "Ende des ganzen Verlaufs"
    unterscheiden koennen."""
    conn = db.verbinde(DB_PFAD)
    try:
        repo.setze_phase(conn, CHAT, 3)
        repo.lege_web_post_an(
            conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
            text="Die Telefone liegen so.", bild="phase-3.png",
        )
        repo.lege_web_post_an(
            conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
            text=phasentexte.eintritt(conn, CHAT, 3),
        )
        for i in range(1, 11):
            repo.lege_web_post_an(
                conn, CHAT,
                repo.RICHTUNG_EIN if i % 2 else repo.RICHTUNG_AUS,
                repo.WEB_TYP_TEXT,
                text=f"Weitere erfundene Verlaufszeile Nummer {i}.",
            )
    finally:
        conn.close()


def _bot_antwort_auf_eigene_nachricht() -> None:
    """Simuliert, was der Bot-Prozess auf eine eigene Nachricht hin
    normalerweise antwortet -- in diesem Test ohne Bot-Prozess, direkt
    gegen dieselbe Datenbank (wie ``_weitere_bot_zeile_nach_dem_wechsel``)."""
    conn = db.verbinde(DB_PFAD)
    try:
        repo.lege_web_post_an(
            conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
            text="Antwort des Bots auf die eigene Nachricht.",
        )
    finally:
        conn.close()


def _weitere_bot_zeile_nach_dem_wechsel() -> None:
    """Was ein spaeterer Poll bringen kann, nachdem die Phase-3-Kopfzeile
    schon im Bild steht (z. B. ``leitfaden.sende_einmal``) -- muss den
    Anker oben NICHT nach unten reissen, solange niemand selbst
    runtergescrollt hat."""
    conn = db.verbinde(DB_PFAD)
    try:
        repo.lege_web_post_an(
            conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
            text="Noch eine Bot-Zeile, die danach eintrifft.",
        )
    finally:
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


@pytest.fixture(scope="module")
def token() -> str:
    return _baue_datenbank()


@pytest.fixture(scope="module")
def server(token):
    bind = f"127.0.0.1:{_freier_port()}"
    basis = f"http://{bind}"
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD, "IT_WEB_BIND": bind, "IT_WEB_PREFIX": "",
        "IT_AUDIO": AUDIO, "PYTHONPATH": str(WURZEL),
    })
    log = open(SERVERLOG, "w")
    prozess = subprocess.Popen(
        [sys.executable, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        _warte_auf_server(prozess, basis)
        yield basis
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=5)
        except subprocess.TimeoutExpired:
            prozess.kill()
        log.close()


def test_phasenwechsel_scrollt_zum_anfang_der_neuen_phase(server, token):
    """Phase 2 -> 3 mit langem Verlauf: die Phase-3-Kopfzeile landet im Bild,
    ``#verlauf`` steht danach NICHT am Ende."""
    basis = server
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            kontext = chromium.new_context(viewport=HANDY, is_mobile=True)
            seite = kontext.new_page()
            seite.set_default_timeout(8000)
            seite.goto(f"{basis}/g/{token}")
            # Der anfaengliche Seitenaufbau hat seinen eigenen Scroll (zum
            # Anfang von Phase 2) -- hier interessiert nur, was NACH dem
            # live erkannten Wechsel passiert. Einmal den ersten Polltakt
            # abwarten, bevor der Wechsel kommt.
            seite.wait_for_timeout(int(POLL_WARTEN_S * 1000))

            _wechsle_zu_phase_3()
            seite.wait_for_timeout(int(POLL_WARTEN_S * 1000))

            phase_3_zeile = seite.locator(".blase.bot", has_text="Phase 3")
            expect(phase_3_zeile.last).to_be_in_viewport()

            def verlauf_am_ende() -> bool:
                return seite.eval_on_selector(
                    "#verlauf",
                    "el => (el.scrollTop + el.clientHeight) >= (el.scrollHeight - 2)",
                )

            assert not verlauf_am_ende(), (
                "Der Verlauf steht am Ende -- die Phase-3-Kopfzeile haette "
                "oben im Bild stehen sollen, nicht das Ende des Verlaufs."
            )

            # Die Bildkarte (``bild=phase-3.png``) steht VOR der Kopfzeile --
            # Teil derselben Eintrittsnachricht, sie soll mit oben stehen.
            bild_karte = seite.locator("#verlauf img.karte").last
            expect(bild_karte).to_be_in_viewport()

            # Ein spaeterer Poll bringt eine weitere Bot-Zeile (z. B. den
            # Leitfaden) -- der Anker oben darf davon NICHT nach unten
            # gerissen werden, solange niemand selbst runtergescrollt hat.
            _weitere_bot_zeile_nach_dem_wechsel()
            seite.wait_for_timeout(int(POLL_WARTEN_S * 1000))

            expect(phase_3_zeile.last).to_be_in_viewport()
            assert not verlauf_am_ende(), (
                "Eine Bot-Zeile NACH dem Phasenwechsel hat den Anker oben "
                "wieder ans Ende des Verlaufs gerissen."
            )

            # Phasenscroll-Karte, Nachtrag (05.10.2026): die Gruppe schreibt
            # jetzt selbst, waehrend der Anker noch oben am Phasenanfang
            # steht -- die eigene Zeile UND die Bot-Antwort danach muessen
            # wieder unten im Bild landen, der Anker darf nicht stehen
            # bleiben.
            seite.fill("#eingabe", "Eigene Nachricht nach dem Phasenwechsel.")
            seite.click("#senden")
            seite.wait_for_timeout(int(POLL_WARTEN_S * 1000))

            eigene_zeile = seite.locator(".blase.gruppe",
                                          has_text="Eigene Nachricht nach dem Phasenwechsel.")
            expect(eigene_zeile.last).to_be_in_viewport()
            assert verlauf_am_ende(), (
                "Die eigene Nachricht haette den Verlauf wieder ans Ende "
                "scrollen sollen, der Anker ist oben stehengeblieben."
            )

            _bot_antwort_auf_eigene_nachricht()
            seite.wait_for_timeout(int(POLL_WARTEN_S * 1000))

            bot_antwort = seite.locator(".blase.bot",
                                         has_text="Antwort des Bots auf die eigene Nachricht.")
            expect(bot_antwort.last).to_be_in_viewport()
            assert verlauf_am_ende(), (
                "Die Bot-Antwort nach der eigenen Nachricht haette unten im "
                "Bild stehen sollen."
            )

            SCHUSS_VERZEICHNIS.mkdir(parents=True, exist_ok=True)
            seite.screenshot(
                path=str(SCHUSS_VERZEICHNIS / "phasenwechsel-2-zu-3.png"),
                full_page=False,
            )
            kontext.close()
        finally:
            chromium.close()
