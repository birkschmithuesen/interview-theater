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
        # state="attached": ein verborgenes Element wird nie "visible" --
        # die Vorgabe von wait_for_selector -- und der Test wartete ewig.
        seite.wait_for_selector("#ux-ansage[hidden]", state="attached",
                                timeout=3000)
        browser.close()


def test_akt_marke_und_lichter_ueberleben_den_tausch_der_aktfolge(dienst):
    """Karte W tauscht #roadmap nach einem Phasenklick per outerHTML aus
    (/teil/roadmap). Review an 834edbf: danach fehlten "Akt 3/7" und die
    Lichter -- sichtbar im Akte- und im Textbuch-Bild."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = _oeffne(browser, basis, token)
        seite.wait_for_selector("#roadmap .ux-akt", state="attached")
        alt = seite.evaluate_handle("() => document.getElementById('roadmap')")
        seite.eval_on_selector("#roadmap", "el => el.open = true")
        knopf = seite.locator('.phase-knopf[data-phase="4"]')
        knopf.click()
        knopf.click()
        seite.wait_for_function(
            "(alt) => document.getElementById('roadmap') !== alt", arg=alt,
            timeout=10_000)
        seite.wait_for_selector("#roadmap .ux-akt", state="attached",
                                timeout=3000)
        assert seite.locator("#roadmap #ux-balken i").count() == 7
        assert seite.locator("#roadmap .ux-akt").count() == 1
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
