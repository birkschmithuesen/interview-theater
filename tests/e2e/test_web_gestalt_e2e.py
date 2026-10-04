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
import shutil
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
#: Committet, weil Birk sie ansieht -- nur erfundene Fixture-Daten.
SCHUSS_REPO = WURZEL / "docs" / "ux-padua"
#: Jeder Lauf schreibt die Schuesse hierhin; ins Repository (``SCHUSS_REPO``)
#: nur mit ``IT_SCHUSS_AKTUALISIEREN=1`` -- sonst waere der Arbeitsbaum nach
#: jedem Lauf schmutzig (wie ``test_web_chat_e2e.py``).
SCHUSS = pathlib.Path("/tmp/it-ux-shots")
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
    # Signatur: lege_szene_an(conn, chat_id, nummer, titel,
    # kurzbeschreibung, volltext) -> szene_id; Form und Ort gehen ueber
    # den Einzelfeld-Weg (setze_szenenfeld), wie im Betrieb.
    szene_id = repo.lege_szene_an(
        conn, CHAT, 1, "Ankunft am Gleis",
        "Meryem kommt nachts an, Erhan wartet.",
        ("(Nacht. Die Halle ist zu hell.)\n"
         "MERYEM: Drei Jahre. Unter dem Bett. Gepackt.\n"
         "ERHAN: Du kannst ihn jetzt auspacken.\n"
         "CHOR: Keiner guckt. Keiner guckt."))
    repo.setze_szenenfeld(conn, szene_id, "form", "dialog")
    repo.setze_szenenfeld(conn, szene_id, "ort", "Bahnhofshalle")
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


#: Haelt die Mikrofonfreigabe 1,5 s auf -- so lange, wie sie auf einem
#: echten Telefon mit Rueckfrage leicht dauert. Ohne das liefert das
#: Fake-Mikrofon sofort, und der Uebergang ist nicht zu sehen.
_LANGSAMES_MIKROFON = """
(() => {
  const md = navigator.mediaDevices;
  const echt = md.getUserMedia.bind(md);
  md.getUserMedia = (c) => new Promise((ok, nein) =>
    setTimeout(() => echt(c).then(ok, nein), 1500));
})();
"""


def test_laeuft_erst_wenn_das_mikrofon_wirklich_aufnimmt(dienst):
    """Browserlauf 03.10.2026: ``_CHAT_JS`` setzt ``data-interview="1"``
    schon beim Druck (der Wechsel ist unterwegs), das Mikrofon kommt erst
    danach. Der Knopf stand damit auf "laeuft" und "Aufnahme laeuft.",
    waehrend noch nichts aufgenommen wurde -- genau die Sekunden, in denen
    in Dortmund geredet wurde, bevor etwas lief."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = browser.new_page(viewport=HANDY, permissions=["microphone"])
        seite.add_init_script(_LANGSAMES_MIKROFON)
        seite.goto(f"{basis}/g/{token}")
        seite.wait_for_selector("#interview")
        knopf = seite.locator("#interview")
        knopf.click()
        seite.wait_for_timeout(300)
        assert knopf.get_attribute("data-ux-zustand") == "startet"
        assert not seite.locator("#uhr").is_visible()
        seite.wait_for_selector('#interview[data-ux-zustand="laeuft"]',
                                timeout=10_000)
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
    """Seit Kanban-Karte Buehne/PTT (04.10.2026, Telegram-Vorbild) ist PTT
    wieder ein Halten-Knopf statt eines Klick-Umschalters (die Karte vom
    03.10.2026/Merge t_ea0d33e3 ist damit fuer PTT selbst zurueckgenommen,
    siehe AGENTS.md-Abschnitt zur Kanban-Karte Buehne/PTT) -- Finger drauf
    und halten startet, Finger weg nach einem Druck ueber ``PTT_MIN_MS``
    beendet und sendet sofort (kein verzoegertes Zuruecksetzen wie beim
    Kurztipp-Hinweis unter der Mindestdauer)."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        ptt = seite.locator("#ptt")
        kasten = ptt.bounding_box()
        assert kasten["width"] >= 44 and kasten["height"] >= 44
        cx = kasten["x"] + kasten["width"] / 2
        cy = kasten["y"] + kasten["height"] / 2
        seite.mouse.move(cx, cy)
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
        # state="attached": ein verborgenes Element wird nie "visible" --
        # die Vorgabe von wait_for_selector -- und der Test wartete ewig.
        seite.wait_for_selector("#ux-ansage[hidden]", state="attached",
                                timeout=3000)
        browser.close()


def test_die_lichter_ueberleben_den_tausch_der_aktfolge(dienst):
    """Karte W tauscht #roadmap nach einem Phasenklick per outerHTML aus
    (/teil/roadmap). Review an 834edbf: danach fehlten die Lichter --
    sichtbar im Akte- und im Textbuch-Bild. (Die Akt-Marke selbst ist seit
    der Kopfzeilen-Karte entfernt, siehe test_web_kopfzeile_e2e.py.)"""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.wait_for_selector("#roadmap #ux-balken", state="attached")
        alt = seite.evaluate_handle("() => document.getElementById('roadmap')")
        seite.eval_on_selector("#roadmap", "el => el.open = true")
        knopf = seite.locator('.phase-knopf[data-phase="4"]')
        knopf.click()
        knopf.click()
        seite.wait_for_function(
            "(alt) => document.getElementById('roadmap') !== alt", arg=alt,
            timeout=10_000)
        seite.wait_for_selector("#roadmap #ux-balken", state="attached",
                                timeout=3000)
        assert seite.locator("#roadmap #ux-balken i").count() == 7
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
        seite.wait_for_selector("#ux-belohnung[hidden]", state="attached",
                                timeout=8000)
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


# -- Was der erste Browserlauf gezeigt hat (03.10.2026) ---------------------
#
# Die Basis-CSS von A2/W ist HELL und schaltet nur unter
# ``prefers-color-scheme: dark`` um. Ein Telefon im hellen Modus (und
# Chromium headless) bekam deshalb weisse Flaechen mit der hellen Schrift
# der Gestaltung darauf -- Phasenknoepfe und Bot-Blasen unlesbar. Gemessen
# wird am berechneten Stil, nicht am CSS-Text.

#: Rechnet ``opacity`` mit: die Basis-CSS daempft Text gern ueber
#: ``opacity: .45`` statt ueber eine Farbe, und ein Farbvergleich allein
#: saehe davon nichts (Review an 834edbf). Die Schrift wird mit der
#: kumulierten Deckkraft aller Vorfahren ueber den Grund gemischt.
_HELLIGKEIT = """
(el) => {
  const rgb = (s) => s.match(/[\\d.]+/g).map(Number);
  const lum = (m) => {
    const k = m.slice(0, 3).map(v => { v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2];
  };
  let n = el, bg = null, deck = 1;
  while (n) {
    const cs = getComputedStyle(n);
    deck *= parseFloat(cs.opacity);
    const m = rgb(cs.backgroundColor);
    if (bg === null && !(m.length > 3 && m[3] === 0)) { bg = m; }
    n = n.parentElement;
  }
  if (bg === null) { bg = [0, 0, 0]; }
  const fg = rgb(getComputedStyle(el).color);
  const misch = [0, 1, 2].map(i => fg[i] * deck + bg[i] * (1 - deck));
  const a = lum(misch), b = lum(bg);
  const hell = Math.max(a, b), dunkel = Math.min(a, b);
  return {bg: b, deck: deck, kontrast: (hell + 0.05) / (dunkel + 0.05)};
}
"""

#: Was im Textbuch gelesen wird -- im Panel und auf der eigenen Seite.
_TEXTBUCH_SELEKTOREN = (".wege a", ".hinweis-druck", ".leiste .marke",
                        ".regie-zeile", ".angaben", ".sprecher", ".text p")


_ALLE_TEXTE = """
(f) => {
  const miss = eval(f), out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!el.getClientRects().length) { continue; }
    const eigen = [...el.childNodes].some(
      n => n.nodeType === 3 && n.textContent.trim());
    if (!eigen) { continue; }
    const w = miss(el);
    if (w.kontrast < 4.5) {
      out.push([el.tagName + '.' + el.className, el.textContent.trim().slice(0, 30),
                Math.round(w.kontrast * 100) / 100]);
    }
  }
  return out;
}
"""


@pytest.mark.parametrize("adresse", ["#chat", "#stand", "#textbuch",
                                     "/textbuch", "/leitfaden"])
def test_jeder_sichtbare_text_hat_kontrast(dienst, adresse):
    """Der Rundgang statt einer Selektorliste: jeder sichtbare Text auf
    jeder Seite gegen seinen tatsaechlichen Grund, Deckkraft eingerechnet.
    Fand beim ersten Lauf weisse Eingabefelder mit heller Schrift im
    Arbeitsstand (1.23:1) -- eine Liste haette sie nicht gekannt."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = browser.new_page(viewport=HANDY)
        seite.goto(f"{basis}/g/{token}{adresse}")
        seite.wait_for_timeout(800)
        if adresse.startswith("#"):
            seite.eval_on_selector("#roadmap", "el => el.open = true")
        schlecht = seite.evaluate(_ALLE_TEXTE, _HELLIGKEIT)
        assert not schlecht, schlecht
        browser.close()


@pytest.mark.parametrize("schema", ["light", "dark"])
def test_keine_hellen_reste_im_textbuch(dienst, schema):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        for adresse, wurzel in ((f"/g/{token}#textbuch", "#tab-textbuch "),
                                (f"/g/{token}/textbuch", "")):
            seite = browser.new_page(viewport=HANDY, color_scheme=schema)
            seite.goto(basis + adresse)
            seite.wait_for_selector(".probe-szene")
            for sel in _TEXTBUCH_SELEKTOREN:
                if seite.locator(wurzel + sel).count() == 0:
                    continue
                wert = seite.eval_on_selector(wurzel + sel, _HELLIGKEIT)
                assert wert["bg"] < 0.2, (schema, adresse, sel, wert)
                assert wert["kontrast"] >= 4.5, (schema, adresse, sel, wert)
            # Der Rollenfilter: die hervorgehobene Replik bekam eine helle
            # Flaeche (#fff6d9) unter die helle Schrift.
            seite.click(wurzel + '.leiste button:has-text("Meryem")')
            wert = seite.eval_on_selector(wurzel + ".replik.aktiv", _HELLIGKEIT)
            assert wert["bg"] < 0.2, (schema, adresse, "replik.aktiv", wert)
            assert wert["kontrast"] >= 4.5, (schema, adresse, "replik.aktiv", wert)
            seite.close()
        browser.close()


@pytest.mark.parametrize("schema", ["light", "dark"])
def test_keine_hellen_flaechen_aus_der_basis_css(dienst, schema):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token, color_scheme=schema)
        seite.eval_on_selector("#roadmap", "el => el.open = true")
        seite.locator("#interview").click()
        seite.wait_for_selector('#interview[data-ux-zustand="laeuft"]',
                                timeout=20_000)
        for sel in ("#tab-chat", ".blase.bot", ".phase-knopf",
                    ".phase.aktiv .phase-knopf", ".phase.aktiv .aufgabe",
                    "#interview-pause", "#interview-beenden"):
            wert = seite.eval_on_selector(sel, _HELLIGKEIT)
            assert wert["bg"] < 0.2, (schema, sel, wert)
            assert wert["kontrast"] >= 4.5, (schema, sel, wert)
        browser.close()


def test_die_eingabezeile_passt_aufs_telefon(dienst):
    """Am Handy stand "Senden" halb ausserhalb des Bildes."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        for sel in ("#eingabe", "#ptt", "#senden"):
            kasten = seite.locator(sel).bounding_box()
            assert kasten["x"] >= 0, sel
            assert kasten["x"] + kasten["width"] <= HANDY["width"], (sel, kasten)
        browser.close()


def test_die_beschriftung_bleibt_im_laufenden_knopf(dienst):
    """"INTERVIEW LAEUFT · 0:00" ragte links und rechts aus dem Kreis."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.locator("#interview").click()
        seite.wait_for_selector('#interview[data-ux-zustand="laeuft"]',
                                timeout=20_000)
        seite.wait_for_timeout(300)
        mass = seite.eval_on_selector("#interview", """el => {
            const r = document.createRange(); r.selectNodeContents(el);
            const t = r.getBoundingClientRect(), k = el.getBoundingClientRect();
            return {tl: t.left, tr: t.right, tt: t.top, tb: t.bottom,
                    kl: k.left, kr: k.right, kt: k.top, kb: k.bottom}; }""")
        assert mass["tl"] >= mass["kl"] and mass["tr"] <= mass["kr"], mass
        assert mass["tt"] >= mass["kt"] and mass["tb"] <= mass["kb"], mass
        # Review an 834edbf: unsichtbar, aber nicht weg -- der Knopf behaelt
        # seinen Namen fuer Vorleseprogramme, Zeit und Zustand stehen gross
        # daneben.
        knopf = seite.locator("#interview")
        assert knopf.evaluate("el => getComputedStyle(el).fontSize") == "0px"
        assert knopf.text_content().strip()
        assert seite.locator("#uhr").is_visible()
        assert seite.locator("#ux-rec-zeile").inner_text().strip()
        browser.close()


# -- Der Interview-Modus (P2, Aufgabe 2) ------------------------------------
#
# Birk: "interviews sauber durchfuehren ohne ablenkung". Waehrend DIESES
# Telefon aufnimmt, sieht man Zustand, Dauer, Pegel und Stopp -- und sonst
# nichts, was sich bewegt oder belohnt. Das Telefon liegt dabei oft vor der
# interviewten Person.

#: Ein Wake Lock, der mitzaehlt. Chromium headless kennt die API, lehnt
#: aber ab -- ohne Attrappe saehe der Test nur den Fehlerweg.
_WAKE_LOCK = """
(() => {
  window.__wl = { an: 0, aus: 0, offen: 0, hoerer: 0, letzte: null };
  const sperre = () => {
    const hoerer = [];
    const s = { released: false, type: 'screen',
      release() { if (!s.released) { s.released = true; window.__wl.aus++;
                                     window.__wl.offen--; }
                  return Promise.resolve(); },
      addEventListener(art, fn) { if (art === 'release') {
                                    hoerer.push(fn); window.__wl.hoerer++; } },
      // Der Browser gibt den Lock selbst frei (Tab im Hintergrund,
      // Akku-Sparmodus): released + Ereignis 'release', ohne release().
      __browserGibtFrei() { if (s.released) { return; }
                            s.released = true; window.__wl.offen--;
                            hoerer.forEach(fn => fn(new Event('release'))); } };
    window.__wl.letzte = s;
    return s;
  };
  Object.defineProperty(navigator, 'wakeLock', { configurable: true,
    value: { request(t) { window.__wl.an++; window.__wl.offen++;
                          return Promise.resolve(sperre()); } } });
})();
"""

#: Kein Wake Lock (Safari vor 16.4, Firefox) -- die Seite darf nicht werfen.
_OHNE_WAKE_LOCK = """
Object.defineProperty(navigator, 'wakeLock',
                      { configurable: true, value: undefined });
"""

#: Wake Lock vorhanden, aber abgelehnt (Akku-Sparmodus, kein Fokus).
_WAKE_LOCK_ABGELEHNT = """
Object.defineProperty(navigator, 'wakeLock', { configurable: true,
  value: { request() { return Promise.reject(new Error('NotAllowedError')); } } });
"""

#: Sichtbarkeit von aussen steuerbar -- ein gesperrtes Telefon oder ein
#: eingehender Anruf schickt ``visibilitychange`` mit ``hidden``.
_SICHTBARKEIT = """
(() => {
  window.__sicht = 'visible';
  Object.defineProperty(document, 'visibilityState',
                        { configurable: true, get: () => window.__sicht });
  Object.defineProperty(document, 'hidden',
                        { configurable: true, get: () => window.__sicht !== 'visible' });
})();
"""


def _interview_seite(browser, basis, token, *skripte, **kw):
    seite = browser.new_page(viewport=HANDY, permissions=["microphone"], **kw)
    fehler = []
    seite.on("pageerror", lambda e: fehler.append(str(e)))
    for s in skripte:
        seite.add_init_script(s)
    seite.goto(f"{basis}/g/{token}")
    seite.wait_for_selector("#interview")
    return seite, fehler


def _starte_interview(seite):
    seite.locator("#interview").click()
    seite.wait_for_selector('#interview[data-ux-zustand="laeuft"]',
                            state="attached", timeout=20_000)
    seite.wait_for_selector('html[data-ux-interview="1"]', state="attached",
                            timeout=5_000)


def test_im_interview_sieht_man_nur_die_aufnahme(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite, fehler = _interview_seite(browser, basis, token, _WAKE_LOCK)
        _starte_interview(seite)
        seite.wait_for_timeout(600)
        for weg in ("#roadmap", ".tabs", "#verlauf", "#tippt", "#eingabe",
                    "#ptt", "#senden", "#ux-belohnung", "#ux-ansage"):
            assert not seite.locator(weg).first.is_visible(), weg
        for da in ("#uhr", "#pegel", "#ux-rec-zeile", "#interview-beenden",
                   "#interview-pause"):
            assert seite.locator(da).is_visible(), da
        # Ein Hauptknopf, am Daumen: Stopp ist gross und in der unteren
        # Haelfte, ganz im Bild.
        stopp = seite.locator("#interview-beenden").bounding_box()
        assert stopp["height"] >= 60, stopp
        assert stopp["y"] > HANDY["height"] / 2, stopp
        assert stopp["y"] + stopp["height"] <= HANDY["height"], stopp
        pause = seite.locator("#interview-pause").bounding_box()
        assert pause["height"] < stopp["height"], (pause, stopp)
        # Keine Bewegung -- auch ohne reduced-motion.
        laufend = seite.evaluate(
            "() => document.getAnimations()"
            ".filter(a => a.playState === 'running')"
            ".map(a => (a.animationName || a.transitionProperty || '?'))")
        assert laufend == [], laufend
        assert not fehler, fehler
        browser.close()


def test_im_interview_hat_jeder_sichtbare_text_kontrast(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite, _ = _interview_seite(browser, basis, token, _WAKE_LOCK)
        _starte_interview(seite)
        seite.locator("#ux-leitfaden summary").click()
        seite.wait_for_timeout(300)
        schlecht = seite.evaluate(_ALLE_TEXTE, _HELLIGKEIT)
        assert not schlecht, schlecht
        browser.close()


def test_der_leitfaden_liegt_zugeklappt_bereit(dienst):
    """Optional und still: die Fragen stehen schon auf der Seite (Stand-
    Panel), das Skript zeigt sie im Interview zugeklappt -- ohne neuen
    Endpunkt."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite, _ = _interview_seite(browser, basis, token, _WAKE_LOCK)
        assert not seite.locator("#ux-leitfaden").is_visible()
        _starte_interview(seite)
        leitfaden = seite.locator("#ux-leitfaden")
        assert leitfaden.is_visible()
        assert leitfaden.get_attribute("open") is None
        marke = ("() => getComputedStyle(document.querySelector("
                 "'#ux-leitfaden summary'), '::before').content")
        # Ein Zeichen sagt, dass man aufklappen kann (display:flex nimmt den
        # eingebauten Marker weg).
        assert seite.evaluate(marke) == '"▸"'
        seite.locator("#ux-leitfaden summary").click()
        assert "Was hast du mitgebracht?" in leitfaden.inner_text()
        assert seite.evaluate(marke) == '"▾"'
        browser.close()


def test_wake_lock_wird_angefordert_und_beim_stopp_freigegeben(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite, fehler = _interview_seite(browser, basis, token, _WAKE_LOCK)
        assert seite.evaluate("() => window.__wl.an") == 0
        _starte_interview(seite)
        seite.wait_for_function("() => window.__wl.an === 1", timeout=3000)
        seite.locator("#interview-beenden").click()
        seite.wait_for_function(
            "() => document.documentElement.dataset.uxInterview !== '1'",
            timeout=10_000)
        seite.wait_for_function("() => window.__wl.offen === 0", timeout=3000)
        assert seite.evaluate("() => window.__wl.an") == 1
        assert not fehler, fehler
        browser.close()


def test_wake_lock_geht_beim_sperren_und_kommt_wieder(dienst):
    """Gesperrtes Telefon, Anruf: ``visibilitychange`` -> hidden. Der
    Browser gibt den Lock dann ohnehin frei; das Skript raeumt auf und
    fordert ihn beim Zurueckkommen neu an, solange das Interview laeuft."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite, fehler = _interview_seite(browser, basis, token,
                                         _WAKE_LOCK, _SICHTBARKEIT)
        _starte_interview(seite)
        seite.wait_for_function("() => window.__wl.offen === 1", timeout=3000)
        seite.evaluate("() => { window.__sicht = 'hidden';"
                       " document.dispatchEvent(new Event('visibilitychange')); }")
        seite.wait_for_function("() => window.__wl.offen === 0", timeout=3000)
        seite.evaluate("() => { window.__sicht = 'visible';"
                       " document.dispatchEvent(new Event('visibilitychange')); }")
        seite.wait_for_function("() => window.__wl.an === 2", timeout=3000)
        assert not fehler, fehler
        browser.close()


def test_gibt_der_browser_den_lock_frei_holt_das_skript_ihn_wieder(dienst):
    """Der Browser darf einen Wake Lock jederzeit selbst freigeben (Ereignis
    ``release`` am Sentinel, ohne dass das Skript ``release()`` ruft). Das
    Skript muss das hoeren -- sonst hielte es ein totes Sentinel fuer
    gueltig und forderte beim Zurueckkommen keinen neuen an."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite, fehler = _interview_seite(browser, basis, token,
                                         _WAKE_LOCK, _SICHTBARKEIT)
        _starte_interview(seite)
        seite.wait_for_function("() => window.__wl.offen === 1", timeout=3000)
        assert seite.evaluate("() => window.__wl.hoerer") == 1
        seite.evaluate("() => window.__wl.letzte.__browserGibtFrei()")
        assert seite.evaluate("() => window.__wl.offen") == 0
        # Kein release() des Skripts auf ein schon freies Sentinel.
        assert seite.evaluate("() => window.__wl.aus") == 0
        seite.evaluate("() => { window.__sicht = 'hidden';"
                       " document.dispatchEvent(new Event('visibilitychange'));"
                       " window.__sicht = 'visible';"
                       " document.dispatchEvent(new Event('visibilitychange')); }")
        seite.wait_for_function("() => window.__wl.an === 2", timeout=3000)
        seite.wait_for_function("() => window.__wl.offen === 1", timeout=3000)
        assert not fehler, fehler
        browser.close()


@pytest.mark.parametrize("attrappe", [_OHNE_WAKE_LOCK, _WAKE_LOCK_ABGELEHNT],
                         ids=["fehlt", "abgelehnt"])
def test_ohne_wake_lock_laeuft_das_interview_trotzdem(dienst, attrappe):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite, fehler = _interview_seite(browser, basis, token, attrappe)
        _starte_interview(seite)
        seite.wait_for_timeout(500)
        assert seite.locator("#uhr").is_visible()
        assert not fehler, fehler
        browser.close()


def test_push_to_talk_ist_kein_interview(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite, _ = _interview_seite(browser, basis, token, _WAKE_LOCK)
        kasten = seite.locator("#ptt").bounding_box()
        seite.mouse.move(kasten["x"] + kasten["width"] / 2,
                         kasten["y"] + kasten["height"] / 2)
        seite.mouse.down()
        seite.wait_for_timeout(900)
        assert seite.evaluate(
            "() => document.documentElement.dataset.uxInterview") != "1"
        assert seite.locator("#roadmap").is_visible()
        assert seite.evaluate("() => window.__wl.an") == 0
        seite.mouse.up()
        browser.close()


def test_in_der_pause_sagt_die_zeile_pause(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite, _ = _interview_seite(browser, basis, token, _WAKE_LOCK)
        _starte_interview(seite)
        laeuft = seite.locator("#ux-rec-zeile").inner_text().strip()
        seite.locator("#interview-pause").click()
        seite.wait_for_selector('#interview[data-pausiert="1"]',
                                state="attached", timeout=5000)
        pause = seite.locator("#ux-rec-zeile").inner_text().strip()
        assert pause and pause != laeuft
        # Die Pause ist noch Interview: die Ablenkung bleibt weg.
        assert seite.evaluate(
            "() => document.documentElement.dataset.uxInterview") == "1"
        browser.close()


def test_zurueck_wischen_im_interview_verliert_den_stopp_nicht(dienst):
    """Der Tab haengt am Fragment: ein Zurueck auf #stand schaltete das
    Chat-Panel weg -- und mit ihm den Stopp, bei verborgener Tableiste."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite, _ = _interview_seite(browser, basis, token, _WAKE_LOCK)
        _starte_interview(seite)
        seite.evaluate("() => { location.hash = '#stand'; }")
        seite.wait_for_timeout(400)
        assert seite.locator("#interview-beenden").is_visible()
        assert not seite.locator("#tab-stand").is_visible()
        browser.close()


# -- Auf einen Blick: was als Naechstes kommt (P2, Aufgabe 2, Punkt 2) -------

#: Unabhaengig vom Skript nachgerechnet: die erste nicht erledigte Aufgabe
#: der aktiven Phase, ohne ihr Zeichen; sonst die naechste Phase.
_ERWARTET_NAECHSTES = """() => {
  const aktiv = document.querySelector('#roadmap .phase.aktiv');
  if (!aktiv) { return ''; }
  const a = aktiv.querySelector('.aufgabe:not(.erledigt)');
  if (a) { return a.textContent.trim().replace(/^\\S+\\s+/, ''); }
  const n = aktiv.nextElementSibling;
  const k = n ? n.querySelector('.phase-knopf, .phase-name') : null;
  return k ? 'Phase ' + (k.dataset.bezeichnung || k.textContent).trim() : '';
}"""


@pytest.mark.parametrize("tab", ["chat", "stand", "textbuch"])
def test_auf_jedem_tab_steht_was_als_naechstes_kommt(dienst, tab):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.click(f'.tabs button[data-tab="{tab}"]')
        seite.wait_for_selector(f"#tab-{tab}:not([hidden])")
        zeile = seite.locator("#ux-naechstes")
        assert zeile.is_visible()
        text = zeile.inner_text().strip()
        assert text.startswith("Als Nächstes:"), text
        erwartet = seite.evaluate(_ERWARTET_NAECHSTES)
        assert erwartet and zeile.locator("b").inner_text().strip() == erwartet
        # Im ersten Blick: ganz im Bild, ueber der Tableiste, eine Zeile.
        kasten = zeile.bounding_box()
        tabs = seite.locator(".tabs").bounding_box()
        assert kasten["y"] >= 0 and kasten["y"] + kasten["height"] <= tabs["y"] + 1
        assert kasten["height"] < 40, kasten
        browser.close()


def test_die_naechste_sache_folgt_dem_tausch_der_aktfolge(dienst):
    """Karte W tauscht #roadmap aus (/teil/roadmap). Danach muss die Zeile
    neu rechnen -- hier mit einer Aktfolge, in der die bisher naechste
    Aufgabe erledigt ist."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.wait_for_selector("#ux-naechstes:not([hidden])", state="attached")
        vorher = seite.locator("#ux-naechstes b").inner_text().strip()
        # Kopfzeilen-Karte: der echte /teil/roadmap-Fetch liefert IMMER
        # unverzierte Server-HTML (ohne #ux-balken, ohne #ux-naechstes --
        # beide entstehen erst client-seitig). Ein rohes cloneNode(true)
        # haette die schon dekorierte Live-Kopie samt #ux-balken UND dem
        # jetzt in <summary> verschachtelten #ux-naechstes mitgenommen und
        # damit dekoriere()s Wache ("schon dekoriert, nichts zu tun")
        # faelschlich ausgeloest -- genau das simuliert kein echter Tausch.
        seite.evaluate("""() => {
          const alt = document.getElementById('roadmap');
          const kopie = alt.cloneNode(true);
          kopie.querySelectorAll('.phase.aktiv .aufgabe:not(.erledigt)')
            .forEach((a, i) => { if (i === 0) { a.classList.add('erledigt'); } });
          var alterBalken = kopie.querySelector('#ux-balken');
          if (alterBalken) { alterBalken.remove(); }
          var alteZeile = kopie.querySelector('#ux-naechstes');
          if (alteZeile) { alteZeile.remove(); }
          alt.outerHTML = kopie.outerHTML;
        }""")
        seite.wait_for_function(
            "(v) => { const b = document.querySelector('#ux-naechstes b');"
            " return !b || b.textContent.trim() !== v; }", arg=vorher,
            timeout=3000)
        erwartet = seite.evaluate(_ERWARTET_NAECHSTES)
        assert seite.locator("#ux-naechstes").count() == 1
        if erwartet:
            assert seite.locator("#ux-naechstes b").inner_text().strip() == erwartet
        else:
            assert not seite.locator("#ux-naechstes").is_visible()
        browser.close()


def test_im_interview_ist_die_naechste_sache_weg(dienst):
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite, _ = _interview_seite(browser, basis, token, _WAKE_LOCK)
        assert seite.locator("#ux-naechstes").is_visible()
        _starte_interview(seite)
        assert not seite.locator("#ux-naechstes").is_visible()
        browser.close()


# -- Die Abnahme-Screenshots ------------------------------------------------


def test_abnahme_screenshots(dienst):
    """Vier Motive, zwei Groessen -- die Abnahme der Karte.

    Sie liegen in ``docs/ux-padua/`` neben den Entwuerfen, damit man
    Entwurf und Ergebnis nebeneinander sehen kann -- neu geschrieben nur mit
    ``IT_SCHUSS_AKTUALISIEREN=1``, sonst nur unter ``/tmp/it-ux-shots/``."""
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
            if name == "handy":
                # P2, Aufgabe 2: der Leitfaden, aufgeklappt -- das Telefon
                # in der Hand der Interviewerin.
                seite.locator("#ux-leitfaden summary").click()
                seite.wait_for_timeout(200)
                seite.screenshot(
                    path=str(SCHUSS / "abnahme-handy-aufnahme-leitfaden.png"))
                seite.locator("#ux-leitfaden summary").click()
            # Gestoppt wird ueber "Beenden" -- der runde Knopf ist waehrend
            # der Aufnahme nur Anzeige (A2). Review an 834edbf: vorher zeigte
            # das Akte-Bild deshalb eine noch laufende Aufnahme.
            seite.locator("#interview-beenden").click()
            seite.wait_for_function(
                "() => ['ruht','laedt'].indexOf(document.getElementById("
                "'interview').dataset.uxZustand) >= 0", timeout=10_000)
            seite.wait_for_timeout(300)

            # Das Motiv "Phasenwechsel": der Akt-Moment nach dem zweiten
            # Druck auf einen Akt -- nicht die Liste allein.
            seite.eval_on_selector("#roadmap", "el => el.open = true")
            seite.eval_on_selector(
                ".phasen", "l => { const a = l.querySelector('.phase.aktiv');"
                " if (a) { l.scrollTop = a.offsetTop - l.offsetTop; } }")
            akt = seite.locator('.phase-knopf[data-phase="4"]')
            akt.click()
            akt.click()
            seite.wait_for_selector("#ux-ansage:not([hidden])", timeout=3000)
            seite.screenshot(path=str(SCHUSS / f"abnahme-{name}-akte.png"))
            seite.wait_for_selector("#ux-ansage[hidden]", state="attached",
                                    timeout=5000)
            # Die Belohnung darf nicht ins naechste Bild ragen.
            seite.wait_for_selector("#ux-belohnung[hidden]", state="attached",
                                    timeout=8000)
            seite.eval_on_selector("#roadmap", "el => el.open = false")

            if name == "handy":
                # P2, Aufgabe 2, Punkt 2: auch im Arbeitsstand steht oben,
                # was als Naechstes kommt.
                seite.click('.tabs button[data-tab="stand"]')
                seite.wait_for_selector("#tab-stand:not([hidden])")
                seite.screenshot(path=str(SCHUSS / "abnahme-handy-stand.png"))

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
    if os.environ.get("IT_SCHUSS_AKTUALISIEREN") == "1":
        SCHUSS_REPO.mkdir(parents=True, exist_ok=True)
        for datei in SCHUSS.glob("abnahme-*.png"):
            shutil.copyfile(datei, SCHUSS_REPO / datei.name)
