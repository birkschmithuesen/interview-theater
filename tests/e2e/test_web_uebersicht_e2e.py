"""Die zwei Uebersichtsseiten im echten Chromium (P2, Aufgabe 3).

Das Team-Dashboard ``/`` haengt am Beamer im Plenum; die Gruppenseite
``/g/<token>#stand`` ist fuer die Gruppe selbst und fuer die inhaltliche
Diskussion im Plenum. Geprueft wird hier, was nur ein Browser sehen kann:
ob jeder sichtbare Text Kontrast hat, ob der Technikteil zu bleibt, solange
nichts klemmt, und ob ein Problem als klarer Hinweis dasteht.

**Nur erfundenes Material**, nie ``betrieb/``. Die Screenshots gehen ins
Repository (``docs/ux-padua/review-*.png``) -- aber nur mit
``IT_SCHUSS_AKTUALISIEREN=1``; sonst landen sie unter
``/tmp/it-ux-uebersicht-shots/``.

Die Screenshots tragen ein Suffix aus ``IT_REVIEW_SUFFIX`` (Vorgabe
``nachher``); die ``vorher``-Bilder sind mit demselben Test vor der Aenderung
entstanden.
"""

import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parents[2]
DB_PFAD = "/tmp/it-ux-uebersicht.db"
BIND = "127.0.0.1:8024"
#: Committet, weil Birk sie ansieht -- nur erfundene Fixture-Daten.
SCHUSS_REPO = WURZEL / "docs" / "ux-padua"
#: Jeder Lauf schreibt die Schuesse hierhin; ins Repository (``SCHUSS_REPO``)
#: nur mit ``IT_SCHUSS_AKTUALISIEREN=1`` (wie ``test_web_chat_e2e.py``).
SCHUSS = pathlib.Path("/tmp/it-ux-uebersicht-shots")
HANDY = {"width": 390, "height": 844}
BEAMER = {"width": 1920, "height": 1080}

KANAL = 7_000_000_000_101    # Phase 5, viel Inhalt, kein Problem
MARKT = 7_000_000_000_102    # Phase 2, Vorfall + Fehlschlag + Kosten
BRUECKE = 7_000_000_000_103  # Phase 3, Interviewmodus, Bot liest nicht

from test_web_gestalt_e2e import _ALLE_TEXTE, _HELLIGKEIT  # noqa: E402


def _vor(minuten: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minuten)).isoformat(
        timespec="seconds")


def _baue_datenbank(pfad: str) -> str:
    """Drei erfundene Gruppen in drei Phasen. Liefert das Token der ersten."""
    sys.path.insert(0, str(WURZEL))
    from interview_theater import db, repo

    if os.path.exists(pfad):
        os.remove(pfad)
    conn = db.verbinde(pfad)
    db.initialisiere(conn)

    # -- Gruppe 1: Canal Crew, Phase 5, alles da, nichts klemmt -------------
    repo.sichere_gruppe(conn, KANAL, "padua_bot1", "Canal Crew")
    repo.setze_gruppe_kanal(conn, KANAL, "web")
    for feld, wert in (
        ("begriffe", "bridge, laundry, night shift, grandmother's radio"),
        ("fragen", "Home: Where do you feel at home?\n"
                   "Work: What do you do when everyone else sleeps?\n"
                   "Noise: Which sound means the day is over?"),
        ("fragen_weich", ""),
        ("interview_eroeffnung", "Hi, we are making a play about this city."),
        ("interview_abschluss", "Thank you, that helps a lot."),
        ("rahmen", "A laundromat by the canal, 3 a.m., the power flickers"),
        ("geschichte", "Two night workers share a laundromat every night without "
                       "talking. When the power fails, they have to. "
                       + "The radio keeps playing on its battery, the dryers stop "
                         "mid-spin, a neighbour knocks on the glass, the baker's "
                         "apprentice tells a story about his grandmother's shop "
                         "and the nurse admits she has not slept for two days. " * 4),
    ):
        repo.setze_arbeitsstand(conn, KANAL, feld, wert)
    repo.setze_phase(conn, KANAL, 5)
    repo.setze_figur(conn, KANAL, "Nadia", "night nurse, counts the spins")
    repo.setze_figur(conn, KANAL, "Teo", "baker's apprentice, always too early")
    repo.setze_figur(conn, KANAL, "The Radio", "speaks only in old songs")
    # Spaetstand: zehn Figuren und mehr -- die Karte muss am Beamer trotzdem
    # in 1080 px passen (Review an 2841d83).
    for name, beschreibung in (
            ("Signora Bassi", "owns the laundromat, never sleeps, keeps a ledger "
                              "of every coin since 1987"),
            ("The Neighbour", "knocks on the glass when the music is too loud"),
            ("Officer Rinaldi", "on night patrol, pretends he is only passing by"),
            ("Giulia", "student, washes her one good dress before every exam"),
            ("Marco", "taxi driver, eats his dinner at four in the morning"),
            ("The Delivery Rider", "always in a hurry, always forgets his helmet"),
            ("Aunt Rosa", "Teo's aunt, tells the same story about the flood"),
            ("The Cat", "belongs to nobody, sleeps on the warm dryer"),
            ("Professor Lenti", "retired, reads the newspaper of yesterday aloud")):
        repo.setze_figur(conn, KANAL, name, beschreibung)
    for nr, titel, form, text in (
        (1, "Spin cycle", "dialog", "NADIA: You again.\nTEO: Me again."),
        (2, "Blackout", "chor", "CHOR: Dark. Warm. Dark."),
        (3, "The radio sings", "lied", None),
    ):
        sid = repo.lege_szene_an(conn, KANAL, nr, titel, f"Scene {nr}.", text)
        repo.setze_szenenfeld(conn, sid, "form", form)
    repo.schreibe_festlegung(conn, KANAL, "stil", "Every scene under 3 minutes")
    repo.merke_nachricht(conn, KANAL, 9, "Gruppe", 0, "sprache", None, _vor(90))
    aid = repo.lege_aufnahme_an(conn, KANAL, 9, "lang", "sprache", None, 420,
                                status="fertig")
    repo.speichere_verdichtung(
        conn, KANAL, aid, "A night porter talks about the hours nobody sees.",
        [{"thema": "Nights belong to the people who keep the city running",
          "kurz": "the invisible night shift",
          "beleg_zitat": "at four the city is ours", "zitat_geprueft": 1},
         {"thema": "Sounds as a clock", "kurz": "the radio as a clock",
          "beleg_zitat": "unverified line", "zitat_geprueft": 0}],
    )
    for nr, kurz in enumerate((
            ("the bakery at five", "flour on the stairs", "a bicycle with no lights"),
            ("the last vaporetto", "a song from Naples", "counting the bridges"),
            ("the hospital corridor", "coffee from a machine", "a patient who sings"),
            ("the market before dawn", "ice and fish", "a lost glove"),
    ), start=10):
        weitere = repo.lege_aufnahme_an(conn, KANAL, nr, "lang", "sprache", None, 300,
                                        status="fertig")
        repo.speichere_verdichtung(
            conn, KANAL, weitere, "Invented summary.",
            [{"thema": k, "kurz": k, "beleg_zitat": "x", "zitat_geprueft": 1}
             for k in kurz])
    # Buchhaltung des Betriebs -- darf KEINEN Hinweis ausloesen.
    repo.merke_vorfall(conn, KANAL, "padua_bot1", "kontext_gekuerzt", "routine")
    repo.merke_vorfall(conn, KANAL, "padua_bot1", "wiederholung_verworfen", "routine")
    repo.schreibe_journal(conn, KANAL, "entschieden",
                          "Setting is the laundromat by the canal", "extraktor")
    for i in range(6):
        repo.merke_aufruf(conn, KANAL, "gespraech", dauer_ms=900, erfolg=1,
                          kosten_chf=0.01)

    # -- Gruppe 2: Market Voices, Phase 2, ein Problem -------------------------
    repo.sichere_gruppe(conn, MARKT, "padua_bot2", "Market Voices")
    repo.setze_arbeitsstand(conn, MARKT, "begriffe", "market, fish, shouting, Sunday")
    repo.setze_phase(conn, MARKT, 2)
    repo.merke_vorfall(conn, MARKT, "padua_bot2", "transkription_fehlgeschlagen",
                       "speech-to-text timed out")
    repo.merke_aufruf(conn, MARKT, "gespraech", dauer_ms=30000, erfolg=0,
                      kosten_chf=4.30)

    # -- Gruppe 3: Bridge Night, Phase 3, Interview laeuft, Bot liest nicht --
    repo.sichere_gruppe(conn, BRUECKE, "padua_bot3", "Bridge Night")
    repo.setze_gruppe_kanal(conn, BRUECKE, "web")
    repo.setze_arbeitsstand(conn, BRUECKE, "begriffe", "bridge, tourists, selfie")
    repo.setze_arbeitsstand(conn, BRUECKE, "fragen", "Who crosses this bridge daily?")
    repo.setze_phase(conn, BRUECKE, 3)
    repo.setze_interviewmodus(conn, BRUECKE, _vor(12))
    repo.setze_update_id(conn, "padua_bot3", 0)
    pid = repo.lege_web_post_an(conn, BRUECKE, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT,
                                text="Are you there?")
    conn.execute("UPDATE web_post SET erstellt_am = ? WHERE id = ?", (_vor(9), pid))

    token = repo.stelle_web_token_sicher(conn, KANAL)
    for chat in (MARKT, BRUECKE):
        repo.stelle_web_token_sicher(conn, chat)
    conn.commit()
    conn.close()
    return token


@pytest.fixture(scope="module")
def dienst():
    token = _baue_datenbank(DB_PFAD)
    SCHUSS.mkdir(parents=True, exist_ok=True)
    umgebung = dict(os.environ, IT_DB=DB_PFAD, IT_WEB_BIND=BIND, IT_WEB_PREFIX="",
                    IT_WORKSHOP="padua-2026", IT_KOSTEN_DECKEL_CHF="5.0")
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


def _suffix() -> str:
    return os.environ.get("IT_REVIEW_SUFFIX", "nachher")


@pytest.mark.parametrize("viewport", [HANDY, BEAMER], ids=["handy", "beamer"])
@pytest.mark.parametrize("adresse", ["/", "#stand"])
def test_jeder_sichtbare_text_hat_kontrast(dienst, adresse, viewport):
    """Derselbe Rundgang wie in ``test_web_gestalt_e2e`` -- jeder sichtbare
    Text gegen seinen tatsaechlichen Grund."""
    basis, token = dienst
    url = f"{basis}/" if adresse == "/" else f"{basis}/g/{token}{adresse}"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport=viewport)
        seite.goto(url)
        seite.wait_for_timeout(800)
        schlecht = seite.evaluate(_ALLE_TEXTE, _HELLIGKEIT)
        assert not schlecht, schlecht
        browser.close()


def test_das_dashboard_zeigt_probleme_und_versteckt_die_technik(dienst):
    basis, _ = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport=BEAMER)
        seite.goto(f"{basis}/")
        karten = {k.locator("h2").inner_text(): k for k in seite.locator(".karte").all()}
        assert set(karten) == {"Canal Crew", "Market Voices", "Bridge Night"}
        # Kein Problem -> kein Hinweis; die Technik ist zu.
        assert karten["Canal Crew"].locator(".ux-achtung").count() == 0
        assert not karten["Canal Crew"].locator("details table").is_visible()
        # Vorfall, Fehlschlag, Kosten nah.
        markt = karten["Market Voices"].locator(".ux-achtung").inner_text()
        for teil in ("1 failed model call in the last 2 hours",
                     "1 incident in the last 2 hours",
                     "Daily cost cap almost reached (86 %)"):
            assert teil in markt, markt
        # Der Bot holt die Nachricht im Web-Kanal nicht ab.
        bruecke = karten["Bridge Night"].locator(".ux-achtung").inner_text()
        assert "hasn't picked up 1 message for 9 min" in bruecke, bruecke
        # Fortschritt auf einen Blick.
        assert "Act 5/7" in karten["Canal Crew"].locator(".ux-akt").inner_text()
        # Am Beamer drei Spalten nebeneinander.
        ys = {round(k.bounding_box()["y"]) for k in karten.values()}
        assert len(ys) == 1, ys
        # Und jede Karte passt in die Hoehe des Beamers -- auch Canal Crew
        # mit zwoelf Figuren, langer Geschichte und fuenf Interviews.
        for name, karte in karten.items():
            box = karte.bounding_box()
            assert box["y"] + box["height"] <= BEAMER["height"], (name, box)
        browser.close()


def test_der_arbeitsstand_ohne_doppelten_chatlink_und_mit_lesbarer_festlegung(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport=HANDY)
        seite.goto(f"{basis}/g/{token}#stand")
        seite.wait_for_selector("#tab-stand:not([hidden])")
        assert not seite.locator('#tab-stand a[href$="/chat"]').is_visible()
        marke = seite.locator("#tab-stand .festlegung .marke").first.bounding_box()
        text = seite.locator("#tab-stand .festlegung .marke + span").first.bounding_box()
        assert text["x"] >= marke["x"] + marke["width"] + 4
        # Was fehlt, steht vor den Formularen.
        fehlt = seite.locator("#tab-stand ul.fehlstellen").bounding_box()
        formular = seite.locator("#tab-stand [data-feld]").first.bounding_box()
        assert fehlt["y"] < formular["y"]
        # Abschnittsueberschriften sind nicht leiser als der Text (Review an
        # 2841d83): Textfarbe und Gewicht.
        h2, absatz = seite.evaluate(
            """() => [getComputedStyle(document.querySelector('#tab-stand h2')),
                      getComputedStyle(document.querySelector('#tab-stand'))]
                     .map(s => [s.color, s.fontWeight])""")
        assert h2[0] == absatz[0], (h2, absatz)
        assert int(h2[1]) >= 600, h2
        browser.close()


def test_review_screenshots(dienst):
    """Dashboard am Telefon und am Beamer, Arbeitsstand ebenso."""
    basis, token = dienst
    suffix = _suffix()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, viewport in (("handy", HANDY), ("beamer", BEAMER)):
            seite = browser.new_page(viewport=viewport)
            seite.goto(f"{basis}/")
            seite.wait_for_timeout(400)
            seite.screenshot(path=str(SCHUSS / f"review-dashboard-{name}-{suffix}.png"),
                             full_page=(name == "handy"))
            seite.goto(f"{basis}/g/{token}#stand")
            seite.wait_for_selector("#tab-stand:not([hidden])")
            seite.wait_for_timeout(400)
            # Erst das obere Bild (was man beim Oeffnen sieht), dann die ganze
            # Seite -- ueber die Fenstergroesse statt ``full_page``: beim
            # Zusammensetzen landete der feste Vorhang (``#ux-vorhang``)
            # sonst als Streifen mitten im Bild. Vorher nach oben: wer
            # ``#stand`` direkt oeffnet, landet heute am Seitenende (der Chat
            # scrollt beim Laden nach unten -- Befund im Bericht, Logik von A2).
            seite.evaluate("window.scrollTo(0, 0)")
            seite.wait_for_timeout(200)
            seite.screenshot(path=str(SCHUSS / f"review-stand-{name}-{suffix}.png"))
            hoehe = seite.evaluate("document.documentElement.scrollHeight")
            seite.set_viewport_size({"width": viewport["width"], "height": hoehe})
            seite.wait_for_timeout(300)
            seite.screenshot(
                path=str(SCHUSS / f"review-stand-{name}-ganz-{suffix}.png"))
            seite.close()
        browser.close()
    for datei in SCHUSS.glob(f"review-*-{suffix}.png"):
        assert datei.stat().st_size > 5_000, datei
    if os.environ.get("IT_SCHUSS_AKTUALISIEREN") == "1":
        SCHUSS_REPO.mkdir(parents=True, exist_ok=True)
        for datei in SCHUSS.glob(f"review-*-{suffix}.png"):
            shutil.copyfile(datei, SCHUSS_REPO / datei.name)
