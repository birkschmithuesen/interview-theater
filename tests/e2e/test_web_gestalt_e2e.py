"""Die Gestaltung im echten Chromium -- und die Abnahme-Screenshots.

Was ``tests/test_web_gestalt_*.py`` NICHT pruefen kann: ob die vier
Zustaende des Aufnahmeknopfes wirklich umschalten, ob Push-to-Talk beim
Halten anders aussieht, ob der Akt-Moment kommt und wieder geht, und ob
bei reduzierter Bewegung wirklich nichts laeuft.

**Nur erfundenes Material** (``simulation/interviews/set1``), nie
``betrieb/``. Die Screenshots gehen ins Repository -- sie sind der Beleg
der Abnahme und duerfen nichts Echtes zeigen.
"""

import os
import pathlib
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parents[2]
DB_PFAD = "/tmp/it-ux.db"
BIND = "127.0.0.1:8023"
SCHUSS = WURZEL / "docs" / "ux-padua"
CHAT = 7_000_000_000_007
HANDY = {"width": 390, "height": 844}
LAPTOP = {"width": 1366, "height": 900}

#: Das Fake-Mikrofon: ohne diese beiden Schalter blockiert die Freigabe,
#: und der Knopf bleibt ewig auf "startet".
MIKROFON = ["--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream"]


def _baue_datenbank(pfad: str) -> str:
    """Eine Demo-Gruppe mit erfundenem Material aus simulation/."""
    sys.path.insert(0, str(WURZEL))
    from interview_theater import db, repo

    if os.path.exists(pfad):
        os.remove(pfad)
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe",
                            "Koffer, Bahnhof, Untermiete, Tomatensamen")
    repo.setze_arbeitsstand(conn, CHAT, "fragen",
                            "Was hast du mitgebracht?\nWas hast du nicht ausgepackt?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_weich", "")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung",
                            "Wir sind vom Theater und sammeln Geschichten.")
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Vielen Dank.")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhofshalle, nachts")
    repo.setze_arbeitsstand(conn, CHAT, "geschichte",
                            "Zwei kommen an und bleiben laenger als geplant.")
    repo.setze_phase(conn, CHAT, 3)
    repo.setze_figur(conn, CHAT, "Meryem", "kam mit einem Koffer")
    repo.setze_figur(conn, CHAT, "Erhan", "holte sie am Bahnhof ab")
    nummer = repo.lege_szene_an(conn, CHAT, 1, "Ankunft am Gleis")
    repo.aktualisiere_szene(
        conn, nummer, form="dialog", ort="Bahnhofshalle",
        volltext=("(Nacht. Die Halle ist zu hell.)\n"
                  "MERYEM: Drei Jahre. Unter dem Bett. Gepackt.\n"
                  "ERHAN: Du kannst ihn jetzt auspacken.\n"
                  "CHOR: Keiner guckt. Keiner guckt."))
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                          text="Wir sind zurueck vom Markt.")
    repo.lege_web_post_an(conn, CHAT, repo.RICHTUNG_AUS, repo.WEB_TYP_TEXT,
                          text="Interview 1 ist ausgewertet. Drei Kernthemen.")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return token


@pytest.fixture(scope="module")
def dienst():
    token = _baue_datenbank(DB_PFAD)
    SCHUSS.mkdir(parents=True, exist_ok=True)
    umgebung = dict(os.environ, IT_DB=DB_PFAD, IT_WEB_BIND=BIND, IT_WEB_PREFIX="")
    prozess = subprocess.Popen(
        [sys.executable, "-m", "interview_theater.web"], cwd=WURZEL, env=umgebung)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://{BIND}/gesund", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    yield f"http://{BIND}", token
    prozess.terminate()
    prozess.wait(timeout=10)


def _oeffne(browser, basis, token, viewport=HANDY, **kw):
    seite = browser.new_page(viewport=viewport, permissions=["microphone"], **kw)
    seite.goto(f"{basis}/g/{token}")
    seite.wait_for_selector("#interview")
    return seite


# -- Die vier Zustaende des Aufnahmeknopfes ---------------------------------


def test_der_aufnahmeknopf_durchlaeuft_seine_zustaende(dienst):
    """Der Kern der Karte. Dortmund Tag 1: ein Knopf 14x in 93 s
    gedrueckt, weil der Zustand nicht erkennbar war."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        knopf = seite.locator("#interview")
        assert knopf.get_attribute("data-ux-zustand") == "ruht"

        knopf.click()
        seite.wait_for_function(
            "() => document.getElementById('interview')"
            ".dataset.uxZustand !== 'ruht'", timeout=10_000)
        # 'startet' oder schon 'laeuft' -- beides ist richtig, je nachdem
        # wie schnell der Poll den Modus meldet.
        assert knopf.get_attribute("data-ux-zustand") in ("startet", "laeuft")

        seite.wait_for_selector('#interview[data-ux-zustand="laeuft"]',
                                timeout=20_000)
        assert seite.locator("#uhr").is_visible()
        browser.close()


def test_jeder_zustand_steht_auch_im_text(dienst):
    """Farbe allein traegt keinen Zustand -- der Probenraum ist schlecht
    beleuchtet."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        ruht = seite.locator("#ux-rec-zeile").inner_text().strip()
        assert ruht
        seite.locator("#interview").click()
        seite.wait_for_selector('#interview[data-ux-zustand="laeuft"]',
                                timeout=20_000)
        laeuft = seite.locator("#ux-rec-zeile").inner_text().strip()
        assert laeuft and laeuft != ruht
        browser.close()


def test_der_uebergang_ist_als_busy_markiert(dienst):
    """Er wird NICHT gesperrt -- das ist ein Befund an Karte A2 (Plan-Kopf,
    Befund 1). Sichtbar ist er trotzdem."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.locator("#interview").click()
        seite.wait_for_function(
            "() => ['startet','laeuft'].indexOf("
            "document.getElementById('interview').dataset.uxZustand) >= 0",
            timeout=10_000)
        if seite.locator("#interview").get_attribute("data-ux-zustand") == "startet":
            assert seite.locator("#interview").get_attribute("aria-busy") == "true"
        browser.close()


# -- Push-to-Talk -----------------------------------------------------------


def test_push_to_talk_sieht_beim_halten_anders_aus(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        ptt = seite.locator("#ptt")
        kasten = ptt.bounding_box()
        assert kasten["width"] >= 44 and kasten["height"] >= 44
        seite.mouse.move(kasten["x"] + kasten["width"] / 2,
                         kasten["y"] + kasten["height"] / 2)
        seite.mouse.down()
        seite.wait_for_timeout(700)
        assert ptt.get_attribute("data-haelt") == "1"
        seite.mouse.up()
        seite.wait_for_timeout(300)
        assert ptt.get_attribute("data-haelt") != "1"
        browser.close()


def test_die_zwei_mikrofone_sind_verschieden_gross_und_woanders(dienst):
    """Vier Achsen; zwei davon lassen sich messen."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        rec = seite.locator("#interview").bounding_box()
        ptt = seite.locator("#ptt").bounding_box()
        assert rec["height"] >= ptt["height"] * 1.4
        assert abs(rec["y"] - ptt["y"]) > 20
        browser.close()


# -- Der Akt-Moment ---------------------------------------------------------


def test_der_aktwechsel_zeigt_seinen_moment_und_raeumt_ihn_weg(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.eval_on_selector("#roadmap", "el => el.open = true")
        knopf = seite.locator('.phase-knopf[data-phase="4"]')
        knopf.click()          # erster Druck: die Rueckfrage
        assert knopf.get_attribute("data-sicher") == "1"
        knopf.click()          # zweiter Druck: der Moment
        seite.wait_for_selector("#ux-ansage:not([hidden])", timeout=3000)
        seite.wait_for_selector("#ux-ansage[hidden]", timeout=3000)
        browser.close()


def test_eine_belohnung_erscheint_und_verschwindet_wieder(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.eval_on_selector("#roadmap", "el => el.open = true")
        knopf = seite.locator('.phase-knopf[data-phase="5"]')
        knopf.click()
        knopf.click()
        seite.wait_for_selector("#ux-belohnung:not([hidden])", timeout=3000)
        seite.wait_for_selector("#ux-belohnung[hidden]", timeout=8000)
        browser.close()


# -- Reduzierte Bewegung ----------------------------------------------------


def test_bei_reduzierter_bewegung_laeuft_keine_animation(dienst):
    """``getAnimations()`` leer -- das ist der Test, den die Karte
    verlangt, und er misst mehr als ein Blick ins CSS."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token, reduced_motion="reduce")
        seite.locator("#interview").click()
        seite.wait_for_timeout(1500)
        laufend = seite.evaluate(
            "() => document.getAnimations()"
            ".filter(a => a.playState === 'running').length")
        assert laufend == 0, laufend
        browser.close()


def test_bei_reduzierter_bewegung_bleibt_alles_bedienbar(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token, reduced_motion="reduce")
        seite.click('.tabs button[data-tab="textbuch"]')
        seite.wait_for_selector("#tab-textbuch:not([hidden])")
        seite.click('.tabs button[data-tab="chat"]')
        seite.wait_for_selector("#tab-chat:not([hidden])")
        seite.locator("#interview").click()
        seite.wait_for_function(
            "() => document.getElementById('interview')"
            ".dataset.uxZustand !== 'ruht'", timeout=10_000)
        browser.close()


def test_der_tabwechsel_verliert_die_halb_getippte_nachricht_nicht(dienst):
    """Karte W garantiert das ueber ``hidden``; die Gestaltung darf es
    nicht kaputtmachen (etwa mit ``display: none`` auf dem falschen
    Knoten)."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.fill("#eingabe", "Das tippe ich gerade")
        seite.click('.tabs button[data-tab="stand"]')
        seite.wait_for_selector("#tab-stand:not([hidden])")
        seite.click('.tabs button[data-tab="chat"]')
        seite.wait_for_selector("#tab-chat:not([hidden])")
        assert seite.input_value("#eingabe") == "Das tippe ich gerade"
        browser.close()


# -- Die Abnahme-Screenshots ------------------------------------------------


def test_abnahme_screenshots(dienst):
    """Vier Motive, zwei Groessen -- die Abnahme der Karte.

    Sie liegen in ``docs/ux-padua/`` neben den Entwuerfen, damit man
    Entwurf und Ergebnis nebeneinander sehen kann."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        for name, viewport in (("handy", HANDY), ("laptop", LAPTOP)):
            seite = _oeffne(browser, basis, token, viewport=viewport)
            seite.screenshot(path=str(SCHUSS / f"abnahme-{name}-chat.png"))

            seite.locator("#interview").click()
            seite.wait_for_selector('#interview[data-ux-zustand="laeuft"]',
                                    timeout=20_000)
            seite.wait_for_timeout(1200)
            seite.screenshot(path=str(SCHUSS / f"abnahme-{name}-aufnahme.png"))
            seite.locator("#interview").click()
            seite.wait_for_timeout(500)

            seite.eval_on_selector("#roadmap", "el => el.open = true")
            seite.wait_for_timeout(200)
            seite.screenshot(path=str(SCHUSS / f"abnahme-{name}-akte.png"))
            seite.eval_on_selector("#roadmap", "el => el.open = false")

            seite.click('.tabs button[data-tab="textbuch"]')
            seite.wait_for_selector("#tab-textbuch:not([hidden])")
            seite.screenshot(path=str(SCHUSS / f"abnahme-{name}-textbuch.png"))
            seite.close()

        # Die Probenansicht als eigene Seite -- sie wird gedruckt.
        seite = browser.new_page(viewport=HANDY)
        seite.goto(f"{basis}/g/{token}/textbuch")
        seite.wait_for_selector(".probe-szene")
        seite.screenshot(path=str(SCHUSS / "abnahme-handy-probenansicht.png"))
        browser.close()

    for datei in SCHUSS.glob("abnahme-*.png"):
        assert datei.stat().st_size > 5_000, datei
