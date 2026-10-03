"""Das CoThinker/Workbench-Panel im echten Chromium (Birk, Live-Feedback
03.10.2026 23:10, woertlich: "CoThinker ist kaum lesbar. Weisser
Hintergrund.").

Was ``tests/test_web_gestalt_tokens.py`` nicht pruefen kann: ob der
tatsaechlich GERENDERTE Grund im Buehne-Panel (``#buehne-panel .karte``,
``.stueckkarte``) noch die alten, hellen Werte aus ``web._CSS_BUEHNE`` trug,
und ob der Fehler eine Panel-Ebene hoeher (die ``.begriff``-Chips und die
``.fassung``-Leiste im Arbeitsstand, aus ``web._CSS_GRUPPE``) genauso
hartcodiert hell war. Beide Male fehlte in ``web_gestalt.py`` eine
Ueberschreibung -- diese Datei misst, dass sie jetzt da ist und wirkt.

**Nur erfundenes Material**, nie ``betrieb/``.
"""

import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo  # noqa: E402

DB_PFAD = "/tmp/it-buehne-kontrast.db"
#: Eine eigene chat_id, nicht in Gebrauch bei einer anderen e2e-Datei
#: (geprueft gegen ``grep -rn "CHAT = " tests/e2e``).
CHAT = 7_000_000_000_511
HANDY = {"width": 390, "height": 844}

#: Das Fake-Mikrofon: ohne diese beiden Schalter blockiert die Freigabe.
MIKROFON = ["--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream"]


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


BIND = f"127.0.0.1:{_freier_port()}"


def _baue_datenbank() -> str:
    """Eine Gruppe in Phase 4 (alle vier Tabs erreichbar, siehe
    ``tests/e2e/test_web_app_shell_e2e.py:_baue_datenbank``) -- dazu ein
    Interview mit Kernbegriffen (fuer ``.begriff``), eine Szene mit zwei
    Fassungen (fuer ``.fassung``) und zwei Buehnenkarten (fuer ``.karte``/
    ``.karte.alt`` im CoThinker-Panel)."""
    for endung in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + endung):
            os.remove(DB_PFAD + endung)
    conn = db.verbinde(DB_PFAD)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Ankommen, Arbeit, Nacht, Koffer")
    repo.setze_arbeitsstand(conn, CHAT, "fragen", "Was war in deinem Koffer?")
    repo.setze_arbeitsstand(conn, CHAT, "fragen_weich", "")
    repo.setze_arbeitsstand(conn, CHAT, "interview_eroeffnung", "Wir sind vom Theater.")
    repo.setze_arbeitsstand(conn, CHAT, "interview_abschluss", "Vielen Dank.")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhofshalle, spaet nachts, Winter")
    repo.setze_arbeitsstand(
        conn, CHAT, "geschichte",
        "Zwei kommen nachts am selben Bahnhof an und bleiben laenger als geplant, "
        "weil der letzte Zug schon weg ist und der naechste erst morgens faehrt.",
    )
    repo.setze_figur(conn, CHAT, "Meryem", "kam 1998 mit einem Koffer")
    repo.setze_figur(conn, CHAT, "Erhan", "holte sie am Bahnhof ab")
    repo.setze_phase(conn, CHAT, 4)

    # Ein Interview mit Verdichtung und Kernbegriffen -- damit
    # ``web._begriffe_html`` wirklich Chips rendert (sonst leer).
    aufnahme_id = repo.lege_aufnahme_an(conn, CHAT, 1, "lang", "sprache", None, 90)
    verdichtung_id = repo.speichere_verdichtung(
        conn, CHAT, aufnahme_id, "Meryem erzaehlt von ihrer Ankunft.",
        [{
            "thema": "Ankommen", "kurz": "Ankommen",
            "beleg_zitat": "Drei Jahre. Unter dem Bett. Gepackt.",
            "zitat_geprueft": 1,
        }],
    )
    repo.setze_verdichtung_begriffe(conn, CHAT, verdichtung_id, ["Koffer", "Bahnhof"])

    # Eine Szene mit zwei Fassungen -- ``web._fassungen_html`` zeigt die
    # Leiste erst ab zwei Fassungen.
    szene_id = repo.lege_szene_an(conn, CHAT, 1, "Ankunft am Gleis", None, None)
    repo.aktualisiere_szene(
        conn, szene_id, "Ankunft am Gleis", None,
        "MERYEM: Drei Jahre. Unter dem Bett. Gepackt.\nERHAN: Du kannst ihn jetzt auspacken.",
    )
    repo.haenge_szenenfassung_an(
        conn, CHAT, szene_id, "MERYEM: Drei Jahre.\nERHAN: Pack aus.", None, "Dialog",
    )
    repo.haenge_szenenfassung_an(
        conn, CHAT, szene_id,
        "MERYEM: Drei Jahre. Unter dem Bett. Gepackt.\nERHAN: Du kannst ihn jetzt auspacken.",
        None, "Dialog",
    )

    # Zwei Buehnenkarten -- die neueste gross, die aeltere klein/ausgegraut.
    repo.lege_buehnenkarte_an(conn, CHAT, "Was, wenn der Koffer leer ist?", "opus")
    repo.lege_buehnenkarte_an(conn, CHAT, "Wer wartet eigentlich auf wen?", "opus")

    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return token


def _warte_auf_server(prozess, sekunden: float = 15.0) -> None:
    ende = time.time() + sekunden
    while time.time() < ende:
        if prozess.poll() is not None:
            raise RuntimeError("Der Webserver ist abgestuerzt.")
        try:
            with urllib.request.urlopen(f"http://{BIND}/gesund", timeout=1) as antwort:
                if antwort.read().decode().strip() == "ok":
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("Der Webserver ist nicht hochgekommen.")


@pytest.fixture(scope="module")
def dienst():
    token = _baue_datenbank()
    umgebung = dict(os.environ, IT_DB=DB_PFAD, IT_WEB_BIND=BIND, IT_WEB_PREFIX="")
    prozess = subprocess.Popen(
        [sys.executable, "-m", "interview_theater.web"], cwd=WURZEL, env=umgebung)
    try:
        _warte_auf_server(prozess)
        yield f"http://{BIND}", token
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=10)
        except subprocess.TimeoutExpired:
            prozess.kill()


# -- Rechnet ``opacity`` mit (Review an 834edbf), kopiert verbatim aus
# ``tests/e2e/test_web_gestalt_e2e.py:378-401`` -- eine String-Konstante,
# kein Import (Testdateien sind keine Bibliotheken). ----------------------

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


def test_cothinker_panel_hat_kontrast(dienst):
    """Birk, Live-Feedback 03.10.2026 23:10: 'CoThinker ist kaum lesbar.
    Weisser Hintergrund.' -- jeder sichtbare Text im Buehne-Panel gegen
    seinen tatsaechlichen, gerenderten Grund."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = browser.new_page(viewport=HANDY)
        seite.goto(f"{basis}/g/{token}#buehne")
        seite.wait_for_timeout(500)
        seite.eval_on_selector("#tab-buehne", "el => el.hidden = false")
        schlecht = seite.eval_on_selector(
            "#buehne-panel",
            """(wurzel, miss) => {
              const f = eval(miss), out = [];
              for (const el of wurzel.querySelectorAll('*')) {
                if (!el.getClientRects().length) { continue; }
                const eigen = [...el.childNodes].some(
                  n => n.nodeType === 3 && n.textContent.trim());
                if (!eigen) { continue; }
                const w = f(el);
                if (w.kontrast < 4.5) {
                  out.push([el.tagName + '.' + el.className,
                            el.textContent.trim().slice(0, 30),
                            Math.round(w.kontrast * 100) / 100]);
                }
              }
              return out;
            }""",
            _HELLIGKEIT,
        )
        assert not schlecht, schlecht
        browser.close()


def test_begriff_und_fassung_chips_haben_kontrast(dienst):
    """Derselbe Fehler eine Panel-Ebene hoeher: die Begriffs-Chips und die
    Fassungsleiste im Arbeitsstand-Panel."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = browser.new_page(viewport=HANDY)
        seite.goto(f"{basis}/g/{token}#stand")
        seite.wait_for_timeout(500)
        for sel in (".begriff", ".fassung"):
            if seite.locator(sel).count() == 0:
                continue
            wert = seite.eval_on_selector(sel, _HELLIGKEIT)
            assert wert["kontrast"] >= 4.5, (sel, wert)
        browser.close()


def test_stand_panel_bleibt_insgesamt_lesbar(dienst):
    """Rundgang wie in ``test_web_gestalt_e2e.py`` -- die neuen Regeln
    duerfen keinen anderen Text im Arbeitsstand verschlechtern."""
    basis, token = dienst
    with sync_playwright() as p:
        browser = p.chromium.launch(args=MIKROFON)
        seite = browser.new_page(viewport=HANDY)
        seite.goto(f"{basis}/g/{token}#stand")
        seite.wait_for_timeout(500)
        schlecht = seite.evaluate(_ALLE_TEXTE, _HELLIGKEIT)
        assert not schlecht, schlecht
        browser.close()
