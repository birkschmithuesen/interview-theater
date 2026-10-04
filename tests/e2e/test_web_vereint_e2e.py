"""Die vereinte Seite im echten Browser (Karte W).

Was ``tests/test_web_vereint_strom_js.py`` am Quelltext festhaelt, prueft
dieser Lauf im Chromium: die Blase waechst ueber mehr als ein Stueck Text,
eine abgebrochene Antwort verschwindet ersatzlos, eine fertige weicht der
Nachricht mit ihrer ``post_id`` -- und zwei gleichzeitige Zeilen haben zwei
Blasen. Dazu (Aufgabe 16): dass der **Tabwechsel wirklich nichts verliert**
-- halb getippter Text und laufende Strom-Blase ueberstehen das Umschalten,
weil nur ``hidden`` umgeschaltet wird --, dass die Zurueck-Taste des
Handys den Tab wechselt, ein geteilter Rollenlink das Textbuch mit der
richtigen Rolle oeffnet, die Phasenleiste auf- und zuklappt (und das auch
ueber einen Nachlade-Takt hinweg bleibt), und ein Phasenklick erst nach der
Rueckfrage den Eingang anlegt.

Kein Bot laeuft mit: der Test schreibt die ``web_strom``-Zeilen selbst ueber
``repo`` (``beginne_strom``/``schreibe_strom``/``beende_strom``), so wie es
die Strom-Senke im Bot taete. Alles Material ist frei erfunden.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_vereint_e2e.py -q

Im normalen ``pytest``-Lauf wird die Datei uebersprungen (``importorskip``).
Die Screenshots gehen ins Repository (``docs/web-vereint/``) -- sie sind der
Beleg der Abnahme und duerfen deshalb nichts Echtes zeigen.
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
from playwright.sync_api import sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo, web_kanal, web_vereint  # noqa: E402

DB_PFAD = "/tmp/it-webvereint.db"
AUDIO = "/tmp/it-webvereint-audio"
SERVERLOG = "/tmp/it-webvereint-server.log"
CHAT = 7_000_000_000_001
#: Eine zweite, Telegram-gefuehrte Gruppe (kanal != web) fuer den einen
#: billigen Fall "kein Chat-Tab" -- ausserhalb des synthetischen Web-Bereichs
#: (``repo.WEB_CHAT_ID_BASIS``), wie jede echte Telegram-chat_id.
TELEGRAM_CHAT = 555_555_555
HANDY = {"width": 390, "height": 844}
GEDULD = 8000
#: Die Screenshots der Abnahme -- committet, nur erfundenes Material.
SCHUSS = WURZEL / "docs" / "web-vereint"


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


BIND = f"127.0.0.1:{_freier_port()}"
BASIS = f"http://{BIND}"


def _baue_datenbank() -> tuple[str, str]:
    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Ankommen, Arbeit, Nacht")
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "Was war in deinem Koffer?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_weich", "")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung", "Wir sind vom Theater.")
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Vielen Dank.")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    repo.setze_arbeitsstand(conn, CHAT, "geschichte", "Zwei treffen sich und bleiben.")
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998 mit einem Koffer")
    repo.setze_phase(conn, CHAT, 4)
    # Eine Szene mit Volltext -- fuer den geteilten Rollenlink (Textbuch-Tab)
    # und die Screenshots des Stand-/Textbuch-Panels.
    szene_id = repo.lege_szene_an(conn, CHAT, 1, "Ankunft am Gleis", None, None)
    repo.aktualisiere_szene(
        conn, szene_id, "Ankunft am Gleis", None,
        "MERYEM: Ich bin da.\nALI: Endlich.",
    )
    kanal = web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01)
    kanal.sende(CHAT, "Eure Begriffe habe ich. Womit fangen wir an?")
    token = repo.stelle_web_token_sicher(conn, CHAT)

    # Telegram-Gruppe: kein Web-Kanal, also kein Chat-Tab auf ihrer Seite
    # (AGENTS.md, "Abschlussreview I3" -- kein Bot, der web_post laese).
    repo.sichere_gruppe(conn, TELEGRAM_CHAT, "telegramgruppe", "Die Telegramgruppe")
    telegram_token = repo.stelle_web_token_sicher(conn, TELEGRAM_CHAT)

    conn.commit()
    conn.close()
    return token, telegram_token


def _warte_auf_server(prozess, sekunden: float = 15.0) -> None:
    ende = time.time() + sekunden
    while time.time() < ende:
        if prozess.poll() is not None:
            raise RuntimeError(f"Der Webserver ist abgestuerzt, siehe {SERVERLOG}.")
        try:
            with urllib.request.urlopen(f"{BASIS}/gesund", timeout=1) as antwort:
                if antwort.read().decode().strip() == "ok":
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError("Der Webserver ist nicht hochgekommen.")


@pytest.fixture(scope="module")
def tokens() -> tuple[str, str]:
    return _baue_datenbank()


@pytest.fixture(scope="module")
def token(tokens) -> str:
    return tokens[0]


@pytest.fixture(scope="module")
def telegram_token(tokens) -> str:
    return tokens[1]


@pytest.fixture(scope="module")
def schuss_verzeichnis() -> Path:
    shutil.rmtree(SCHUSS, ignore_errors=True)
    SCHUSS.mkdir(parents=True, exist_ok=True)
    return SCHUSS


@pytest.fixture(scope="module")
def server(token):
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD, "IT_WEB_BIND": BIND, "IT_WEB_PREFIX": "/theatersoap",
        "IT_AUDIO": AUDIO, "PYTHONPATH": str(WURZEL),
    })
    log = open(SERVERLOG, "w")
    prozess = subprocess.Popen(
        [sys.executable, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        _warte_auf_server(prozess)
        yield prozess
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=5)
        except subprocess.TimeoutExpired:
            prozess.kill()
        log.close()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        yield chromium
        chromium.close()


@pytest.fixture
def conn():
    verbindung = db.verbinde(DB_PFAD)
    # Kein Rest aus dem vorigen Test laeuft weiter.
    for zeile in repo.laufende_stroeme(verbindung, CHAT):
        repo.beende_strom(verbindung, zeile["id"], repo.STROM_ABGEBROCHEN)
    yield verbindung
    verbindung.close()


@pytest.fixture
def seite(server, browser, token, conn):
    kontext = browser.new_context(viewport=HANDY, is_mobile=True, has_touch=True)
    blatt = kontext.new_page()
    blatt.set_default_timeout(GEDULD)
    blatt.goto(f"{BASIS}/g/{token}")
    blatt.wait_for_selector("#verlauf")
    yield blatt
    kontext.close()


def _warte(seite, bedingung, ms: int = GEDULD, schritt: int = 100) -> bool:
    ende = time.time() + ms / 1000
    while time.time() < ende:
        if bedingung():
            return True
        seite.wait_for_timeout(schritt)
    return bedingung()


def _blasen(seite) -> list[str]:
    return seite.eval_on_selector_all(
        ".blase.vorlaeufig", "els => els.map(e => e.textContent)")


def _beginne_und_wecke(seite, conn) -> int:
    """Eine laufende Zeile -- und die Tippanzeige, wie der Bot sie setzt:
    das ist der Anlass, bei dem die Ansicht den Strom oeffnet."""
    strom_id = repo.beginne_strom(conn, CHAT, "gespraech")
    web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01).tippt(CHAT)
    return strom_id


def test_die_blase_waechst_und_verschwindet_bei_abbruch(seite, conn):
    strom_id = _beginne_und_wecke(seite, conn)
    repo.schreibe_strom(conn, strom_id, "Das ist")
    assert _warte(seite, lambda: _blasen(seite) == ["Das ist"], ms=40000)
    repo.schreibe_strom(conn, strom_id, "Das ist ein Anfang")
    assert _warte(seite, lambda: _blasen(seite) == ["Das ist ein Anfang"])
    # Kein innerHTML: Markup im Teiltext bleibt Text.
    repo.schreibe_strom(conn, strom_id, "Das ist <b>fett</b>")
    assert _warte(seite, lambda: _blasen(seite) == ["Das ist <b>fett</b>"])
    assert seite.locator(".blase.vorlaeufig b").count() == 0
    repo.beende_strom(conn, strom_id, repo.STROM_ABGEBROCHEN)
    assert _warte(seite, lambda: _blasen(seite) == [])
    # Und sie kommt nicht wieder, auch wenn der Strom neu aufgeht.
    seite.wait_for_timeout(4000)
    assert _blasen(seite) == []


def test_die_fertige_blase_weicht_der_nachricht(seite, conn):
    strom_id = _beginne_und_wecke(seite, conn)
    repo.schreibe_strom(conn, strom_id, "Hier kommt die Antwort")
    assert _warte(seite, lambda: _blasen(seite) == ["Hier kommt die Antwort"], ms=40000)
    kanal = web_kanal.WebKanal(conn, CHAT, AUDIO, schritt_s=0.01)
    post_id = kanal.sende(CHAT, "Hier kommt die Antwort, fertig.")
    repo.beende_strom(conn, strom_id, repo.STROM_FERTIG, post_id)
    assert _warte(
        seite,
        lambda: seite.locator(f'.blase[data-id="{post_id}"]').count() == 1
        and _blasen(seite) == [],
        ms=15000,
    )


def test_zwei_zeilen_zwei_blasen(seite, conn):
    erste = _beginne_und_wecke(seite, conn)
    zweite = repo.beginne_strom(conn, CHAT, "szene")
    repo.schreibe_strom(conn, erste, "Gespraech")
    repo.schreibe_strom(conn, zweite, "Szene")
    assert _warte(seite, lambda: sorted(_blasen(seite)) == ["Gespraech", "Szene"],
                  ms=40000)
    repo.beende_strom(conn, erste, repo.STROM_ABGEBROCHEN)
    assert _warte(seite, lambda: _blasen(seite) == ["Szene"])
    repo.schreibe_strom(conn, zweite, "Szene waechst")
    assert _warte(seite, lambda: _blasen(seite) == ["Szene waechst"])
    repo.beende_strom(conn, zweite, repo.STROM_ABGEBROCHEN)
    assert _warte(seite, lambda: _blasen(seite) == [])


def test_der_tabwechsel_verliert_nichts(seite, conn):
    """Der Kern der Karte: halb getippter Text und laufende Strom-Blase
    ueberstehen den Wechsel -- weil nur ``hidden`` umgeschaltet wird."""
    seite.fill("#eingabe", "Das tippe ich gerade")
    strom_id = _beginne_und_wecke(seite, conn)
    repo.schreibe_strom(conn, strom_id, "Der Bot schreibt ger")
    assert _warte(seite, lambda: _blasen(seite) == ["Der Bot schreibt ger"], ms=40000)

    seite.click('.tabs button[data-tab="stand"]')
    seite.wait_for_selector("#tab-stand:not([hidden])")
    seite.click('.tabs button[data-tab="chat"]')
    seite.wait_for_selector("#tab-chat:not([hidden])")

    assert seite.input_value("#eingabe") == "Das tippe ich gerade"
    assert seite.is_visible(".blase.vorlaeufig")
    repo.schreibe_strom(conn, strom_id, "Der Bot schreibt gerade weiter.")
    assert _warte(seite, lambda: _blasen(seite) == ["Der Bot schreibt gerade weiter."])
    repo.beende_strom(conn, strom_id, repo.STROM_ABGEBROCHEN)
    assert _warte(seite, lambda: _blasen(seite) == [])


def test_die_zurueck_taste_wechselt_den_tab(seite):
    seite.click('.tabs button[data-tab="textbuch"]')
    seite.wait_for_selector("#tab-textbuch:not([hidden])")
    seite.go_back()
    seite.wait_for_selector("#tab-chat:not([hidden])")


def test_ein_geteilter_rollenlink_oeffnet_das_textbuch_mit_rolle(server, browser, token):
    """``#textbuch&figur=Meryem`` -- dieselbe Form wie auf der Probenansicht."""
    kontext = browser.new_context(viewport=HANDY)
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD)
    seite.goto(f"{BASIS}/g/{token}#textbuch&figur=Meryem")
    seite.wait_for_selector("#tab-textbuch:not([hidden])")
    assert seite.get_attribute("#tab-textbuch", "data-figur")
    kontext.close()


def test_die_phasenleiste_klappt_auf_und_zu(seite):
    assert not seite.is_visible(".roadmap .phasen")
    seite.click(".roadmap summary")
    seite.wait_for_selector(".roadmap .phasen", state="visible")
    # Fix-Runde 2 (Aufgabe 13) hielt den offenen Zustand ueber das
    # Nachladen fest -- das laesst sich nur im Browser messen: ueber einen
    # ganzen Nachlade-Takt (NACHLADEN_MS) hinweg bleibt sie auf.
    seite.wait_for_timeout(web_vereint.NACHLADEN_MS + 1500)
    assert seite.is_visible(".roadmap .phasen")
    seite.click(".roadmap summary")
    seite.wait_for_selector(".roadmap .phasen", state="hidden")


def test_ein_phasenklick_fragt_nach_und_legt_dann_den_eingang_ab(seite, conn):
    """Fehlgriff-Schutz und der Weg durch die Naht -- im Browser."""
    seite.click(".roadmap summary")
    knopf = seite.locator('.phase-knopf[data-phase="5"]')
    vorher = knopf.text_content()
    knopf.click()
    seite.wait_for_function(
        "document.querySelector('.phase-knopf[data-phase=\"5\"]')"
        ".getAttribute('data-sicher') === '1'", timeout=5_000)
    assert knopf.text_content() != vorher

    vor = len(repo.web_eingang(conn, CHAT, 0))
    knopf.click()
    seite.wait_for_timeout(1_000)
    eingaenge = repo.web_eingang(conn, CHAT, 0)
    assert len(eingaenge) == vor + 1
    assert eingaenge[-1]["text"] == "/phaseklick 5"
    # Das Menue schliesst sich nach dem erfolgreichen Sprung selbst (Teil B)
    # -- und bleibt es, auch ueber den naechsten Nachlade-Takt hinweg (siehe
    # unten im Betreff von ``ladeRoadmap``/``warOffen``).
    assert seite.locator("#roadmap").get_attribute("open") is None


def test_nein_bei_der_ruckfrage_schliesst_das_menue(seite, conn):
    """"Stay here": Abbrechen schliesst die Roadmap, ohne einen Eingang
    anzulegen -- die Rueckfrage wurde verworfen, kein Sprung (Teil B)."""
    seite.click(".roadmap summary")
    knopf = seite.locator('.phase-knopf[data-phase="5"]')
    knopf.click()
    seite.wait_for_function(
        "document.querySelector('.phase-knopf[data-phase=\"5\"]')"
        ".getAttribute('data-sicher') === '1'", timeout=5_000)

    vor = len(repo.web_eingang(conn, CHAT, 0))
    seite.click('.phase-abbrechen[data-phase="5"]')
    seite.wait_for_selector(".roadmap .phasen", state="hidden")
    assert seite.locator("#roadmap").get_attribute("open") is None
    assert len(repo.web_eingang(conn, CHAT, 0)) == vor


def test_tap_aussen_schliesst_das_menue(seite):
    """Ein Klick ausserhalb des Menues klappt es zu; ein Klick auf das Menue
    selbst (Knopf oder ``<summary>``) loest diesen Mechanismus NICHT aus --
    sonst merkt ein Bug, der bei JEDEM Klick zuklappt, niemand (Teil B)."""
    seite.click(".roadmap summary")
    seite.wait_for_selector(".roadmap .phasen", state="visible")

    # Gegenprobe zuerst: ein Klick AUF einen Knopf im Menue schliesst es
    # nicht ueber den Aussen-Mechanismus (die eigene Logik bewaffnet ihn
    # stattdessen -- das Menue bleibt offen).
    seite.click('.phase-knopf[data-phase="5"]')
    seite.wait_for_function(
        "document.querySelector('.phase-knopf[data-phase=\"5\"]')"
        ".getAttribute('data-sicher') === '1'", timeout=5_000)
    assert seite.locator("#roadmap").get_attribute("open") == ""

    # Jetzt ausserhalb klicken (ein Tab-Knopf) -- das Menue klappt zu.
    seite.click('.tabs button[data-tab="stand"]')
    seite.wait_for_selector(".roadmap .phasen", state="hidden")
    assert seite.locator("#roadmap").get_attribute("open") is None


def test_telegram_gruppe_oeffnet_auf_stand_ohne_chat_tab(server, browser, telegram_token):
    """Kein Web-Kanal, kein Chat-Tab (AGENTS.md "Abschlussreview I3")."""
    kontext = browser.new_context(viewport=HANDY)
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD)
    seite.goto(f"{BASIS}/g/{telegram_token}")
    seite.wait_for_selector("#tab-stand:not([hidden])")
    assert seite.locator('.tabs button[data-tab="chat"]').count() == 0
    kontext.close()


@pytest.mark.parametrize("breite,hoehe,name", [(390, 844, "handy"),
                                               (1366, 900, "laptop")])
def test_screenshots(server, browser, token, conn, schuss_verzeichnis,
                     breite, hoehe, name):
    """Die Abnahme der Karte: Chat mit laufendem Stream, Tab Arbeitsstand,
    Phasenuebersicht zu und auf."""
    kontext = browser.new_context(viewport={"width": breite, "height": hoehe})
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD)
    seite.goto(f"{BASIS}/g/{token}")
    seite.wait_for_selector("#verlauf")

    strom_id = _beginne_und_wecke(seite, conn)
    repo.schreibe_strom(conn, strom_id, "Mit euren Begriffen. Was faellt euch ")
    assert _warte(seite, lambda: _blasen(seite) == ["Mit euren Begriffen. Was faellt euch "],
                  ms=40000)
    seite.screenshot(path=str(schuss_verzeichnis / f"{name}-chat-stream.png"))

    seite.click(".roadmap summary")
    seite.wait_for_selector(".roadmap .phasen", state="visible")
    seite.screenshot(path=str(schuss_verzeichnis / f"{name}-phasen-auf.png"))
    seite.click(".roadmap summary")
    seite.wait_for_selector(".roadmap .phasen", state="hidden")
    seite.screenshot(path=str(schuss_verzeichnis / f"{name}-phasen-zu.png"))

    seite.click('.tabs button[data-tab="stand"]')
    seite.wait_for_selector("#tab-stand:not([hidden])")
    seite.screenshot(path=str(schuss_verzeichnis / f"{name}-stand.png"), full_page=True)

    repo.beende_strom(conn, strom_id, repo.STROM_ABGEBROCHEN)
    kontext.close()
