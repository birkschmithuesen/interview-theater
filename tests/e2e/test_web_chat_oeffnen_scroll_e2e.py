"""Nachtfix 05.10.2026: wohin der Chat beim OEFFNEN scrollt.

Birk, 05.10.2026 22:00: zum Anfang der aktuellen Phase nur beim ersten
Oeffnen dieses Geraets in dieser Phase -- jedes spaetere Oeffnen (Reload)
steht unten bei der neuesten Nachricht. Gemerkt wird je Geraet in
``localStorage`` (``phase_gesehen:<gruppe>:<phase>``).

Dazu Klasse A: mit mehr als 200 sichtbaren Nachrichten lieferte der
Seitenaufbau die AELTESTEN 200 -- die aktuelle Phasenzeile kam gar nicht
erst auf die Seite. Gruppe B hat 250 Nachrichten mit der Kopfzeile kurz vor
dem Ende.

Geprueft auf der vereinten Seite (``/g/<token>``) im Telefonformat; Aufbau
wie ``test_web_chat_phasenscroll_e2e.py``. Nur erfundenes Material.
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

DB_PFAD = "/tmp/it-oeffnen-scroll.db"
AUDIO = "/tmp/it-oeffnen-scroll-audio"
SERVERLOG = "/tmp/it-oeffnen-scroll-server.log"
CHAT_A = 7_000_000_000_060
CHAT_B = 7_000_000_000_061

HANDY = {"width": 390, "height": 844}
#: Zeit fuer Seitenaufbau und den ersten Scroll (kein Poll noetig).
SETZEN_MS = 1500


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _zeilen(conn, chat_id: int, anzahl: int, praefix: str) -> None:
    for i in range(1, anzahl + 1):
        repo.lege_web_post_an(
            conn, chat_id,
            repo.RICHTUNG_EIN if i % 2 else repo.RICHTUNG_AUS,
            repo.WEB_TYP_TEXT,
            text=f"{praefix} {i}.",
        )


def _baue_datenbank() -> tuple[str, str]:
    """Gruppe A: Phase 2, Kopfzeile am Anfang, 40 Zeilen danach.
    Gruppe B: Phase 3, 220 Zeilen, Kopfzeile Phase 3, 30 Zeilen danach --
    zusammen 251 sichtbare Nachrichten, also mehr als ``CHAT_GRENZE``."""
    for endung in ("", "-wal", "-shm"):
        pfad = DB_PFAD + endung
        if os.path.exists(pfad):
            os.remove(pfad)
    shutil.rmtree(AUDIO, ignore_errors=True)

    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    for chat_id, name in ((CHAT_A, "scrollbot_a"), (CHAT_B, "scrollbot_b")):
        repo.sichere_gruppe(conn, chat_id, name, "Die Ankommenden")
        repo.setze_gruppe_kanal(conn, chat_id, "web")
        repo.setze_arbeitsstand(conn, chat_id, "begriffe", "Ankommen, Arbeit, Nacht")

    repo.setze_phase(conn, CHAT_A, 2)
    repo.lege_web_post_an(conn, CHAT_A, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text=phasentexte.eintritt(conn, CHAT_A, 2))
    _zeilen(conn, CHAT_A, 40, "Erfundene Zeile A Nummer")

    repo.setze_phase(conn, CHAT_B, 3)
    _zeilen(conn, CHAT_B, 220, "Alte erfundene Zeile B Nummer")
    repo.lege_web_post_an(conn, CHAT_B, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text=phasentexte.eintritt(conn, CHAT_B, 3))
    _zeilen(conn, CHAT_B, 30, "Neue erfundene Zeile B Nummer")

    tok_a = repo.stelle_web_token_sicher(conn, CHAT_A)
    tok_b = repo.stelle_web_token_sicher(conn, CHAT_B)
    conn.commit()
    conn.close()
    return tok_a, tok_b


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
def tokens() -> tuple[str, str]:
    return _baue_datenbank()


@pytest.fixture(scope="module")
def server(tokens):
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


#: Dieselbe Toleranz wie ``UNTEN_TOLERANZ_PX`` im Chat-Skript ("steht
#: unten" fuer den Poll). Gemessen 05.10.2026: der einmalige Stepper-Hinweis
#: (``web_vereint._STEPPER_JS``, ``zeigeHinweisEinmal``) erscheint NACH dem
#: Scroll des Chat-Skripts und verkleinert ``#verlauf`` um 35 px -- der
#: Verlauf steht dann 35 px vor dem Ende. Das war vorher genauso (jeder
#: Rueckfall ``nachUnten()`` beim Aufbau); die Seite zaehlt es weiter als
#: "unten", neue Nachrichten ziehen also mit.
UNTEN_TOLERANZ_PX = 48


def _abstand_zum_ende(seite) -> int:
    return seite.eval_on_selector(
        "#verlauf", "el => el.scrollHeight - (el.scrollTop + el.clientHeight)",
    )


def _verlauf_am_ende(seite) -> bool:
    return _abstand_zum_ende(seite) <= UNTEN_TOLERANZ_PX


def _oeffnen_dann_neu_laden(basis: str, token: str, kopf_text: str, letzte_text: str,
                            vor_dem_reload=None) -> None:
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            kontext = chromium.new_context(viewport=HANDY, is_mobile=True)
            seite = kontext.new_page()
            seite.set_default_timeout(8000)
            kopf = seite.locator(".blase.bot", has_text=kopf_text).last
            letzte = seite.locator(".blase", has_text=letzte_text).last

            # Erstes Oeffnen in dieser Phase: der Phasenanfang steht im Bild.
            seite.goto(f"{basis}/g/{token}")
            seite.wait_for_timeout(SETZEN_MS)
            expect(kopf).to_be_in_viewport()
            expect(letzte).not_to_be_in_viewport()
            assert not _verlauf_am_ende(seite)
            if vor_dem_reload:
                vor_dem_reload(seite)

            # Jedes spaetere Oeffnen: unten, bei der neuesten Nachricht.
            seite.reload()
            seite.wait_for_timeout(SETZEN_MS)
            expect(letzte).to_be_in_viewport()
            expect(kopf).not_to_be_in_viewport()
            assert _verlauf_am_ende(seite), _abstand_zum_ende(seite)
            kontext.close()
        finally:
            chromium.close()


def test_erstes_oeffnen_phasenanfang_reload_unten(server, tokens):
    tok_a, _ = tokens
    _oeffnen_dann_neu_laden(server, tok_a, "Phase 2", "Erfundene Zeile A Nummer 40.")


def test_ueber_200_nachrichten_kopfzeile_kurz_vor_dem_ende(server, tokens):
    """Klasse A im Browser: 251 Nachrichten, die Phase-3-Kopfzeile ist die
    222. -- vor dem Fix stand sie gar nicht auf der Seite (die aeltesten 200
    wurden geladen) und das Oeffnen landete in alten Zeilen."""
    _, tok_b = tokens

    def nur_die_neuesten_geladen(seite):
        assert seite.locator(".blase", has_text="Alte erfundene Zeile B Nummer 1.").count() == 0
        assert seite.locator(".blase", has_text="Neue erfundene Zeile B Nummer 30.").count() == 1

    _oeffnen_dann_neu_laden(server, tok_b, "Phase 3", "Neue erfundene Zeile B Nummer 30.",
                            vor_dem_reload=nur_die_neuesten_geladen)
