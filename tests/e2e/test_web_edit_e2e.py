"""Die Gruppenseite im echten Browser -- geklickt, nicht simuliert.

Was dieser Lauf leistet, was ``tests/test_web_edit.py`` nicht leistet: dort
schickt urllib ein JSON an den Server, hier klickt ein echtes Chromium auf
echte Knoepfe. Alles zwischen Klick und Datenbank kommt damit mit: das
Dropdown, ``_BEARBEITEN_JS``, fetch, der Nonce aus der Seite, das sanfte
Nachladen und die Frage, ob die Seite nach einem Neuladen wirklich den neuen
Wert zeigt.

Gefahren wird gegen einen **echten Serverprozess** (``python -m
interview_theater.web``) auf einer **Wegwerf-Datenbank** -- nie gegen
``IT_DB`` aus dem Betrieb.

Aufruf::

    /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m pytest \\
        tests/e2e/test_web_edit_e2e.py -q

Im normalen ``pytest``-Lauf wird die Datei uebersprungen: dort gibt es kein
playwright (``importorskip`` unten).
"""

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

playwright_api = pytest.importorskip(
    "playwright.sync_api", reason="playwright ist hier nicht installiert"
)
from playwright.sync_api import expect, sync_playwright  # noqa: E402

pytestmark = pytest.mark.e2e

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import db, repo  # noqa: E402

#: Wegwerf-Datenbank und Adresse aus dem Brief. Beides bewusst fest: der Lauf
#: soll auch von Hand nachvollziehbar sein (``curl
#: http://127.0.0.1:8019/g/<token>``).
DB_PFAD = "/tmp/it-webtest.db"
BIND = "127.0.0.1:8019"
BASIS = f"http://{BIND}"

#: Hier schaut Birk die Seite an.
SCHUSSVERZEICHNIS = Path("/tmp/it-webedit-shots")

#: Kommt im Transkript vor und darf auf keiner Seite stehen.
MARKER = "Zwirbelkiste"

#: Playwright wartet in Millisekunden. Fuenf Sekunden sind grosszuegig fuer
#: einen lokalen Server und trotzdem kurz genug, dass ein haengender Lauf
#: nicht den Abend kostet.
GEDULD = 5000


def _baue_datenbank(pfad: str) -> str:
    """Die Wegwerf-Datenbank: eine Gruppe in Phase 4, drei angebotene
    Richtungen, zwei Kernthema-Vorschlaege, zwei Figuren, zwei Interviews und
    eine Szene. Aufgebaut ueber ``repo``, nicht ueber SQL -- so steht am Ende
    genau das da, was auch im Betrieb entsteht."""
    if os.path.exists(pfad):
        os.remove(pfad)
    for endung in ("-wal", "-shm"):
        if os.path.exists(pfad + endung):
            os.remove(pfad + endung)
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 4711, "gruppe1", "Die Ankommenden")
    repo.setze_phase(conn, 4711, 4)
    repo.setze_arbeitsstand(conn, 4711, "begriffe", "Ankommen, Arbeit, Nacht")
    repo.setze_arbeitsstand(conn, 4711, "fragen", "Was war in deinem Koffer?")
    repo.setze_arbeitsstand(conn, 4711, "kernthema", "Ankommen und Bleiben")
    repo.setze_arbeitsstand(conn, 4711, "kernthema_richtung", "Heimat")

    for wert in ("Heimat", "Arbeit", "Nachtschicht"):
        repo.lege_knopf_an(conn, 4711, "richtung", wert)
    for wert in ("Ankommen und Bleiben", "Zwei Staedte, ein Koffer"):
        repo.lege_knopf_an(conn, 4711, "kernthema", wert)
    repo.lege_knopf_an(conn, 4711, "rahmen", "Eine Nacht im Treppenhaus")

    repo.setze_figur(conn, 4711, "Mira", "24, arbeitet nachts")
    repo.setze_figur(conn, 4711, "Pola", "58, will zurueck")

    for nummer in (1, 2):
        repo.merke_nachricht(
            conn, 4711, 100 + nummer, "Ada", 0, "sprache", "",
            f"2026-09-05T09:0{nummer}:00+00:00",
        )
        aufnahme_id = repo.lege_aufnahme_an(
            conn, 4711, 100 + nummer, "lang", "sprache", f"/tmp/a{nummer}.ogg", 200
        )
        # Ein Transkript mit Markerwort: es steht in der Datenbank und darf
        # trotzdem auf keiner Seite auftauchen.
        repo.setze_transkript(
            conn, aufnahme_id, f"Ich hatte nur einen Koffer und eine {MARKER} dabei."
        )
    repo.setze_figur_quelle(
        conn, repo.hole_figur(conn, 4711, "Mira")["id"],
        repo.transkripte(conn, 4711)[0]["id"],
    )

    szene_id = repo.stelle_szene_sicher(conn, 4711, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Im Treppenhaus")
    repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")
    repo.setze_szenenfeld(conn, szene_id, "ort", "Treppenhaus")

    repo.schreibe_journal(conn, 4711, "entschieden", "Kernthema steht", "extraktor")
    token = repo.stelle_web_token_sicher(conn, 4711)
    conn.commit()
    conn.close()
    return token


def _warte_auf_server(sekunden: float = 15.0) -> None:
    ende = time.time() + sekunden
    while time.time() < ende:
        try:
            with urllib.request.urlopen(f"{BASIS}/gesund", timeout=1) as antwort:
                if antwort.read().decode().strip() == "ok":
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError("Der Webserver ist nicht hochgekommen.")


@pytest.fixture(scope="module")
def token() -> str:
    return _baue_datenbank(DB_PFAD)


@pytest.fixture(scope="module")
def server(token):
    """Ein echter Serverprozess, wie ihn die systemd-Unit startet -- nur mit
    der Wegwerf-Datenbank und auf 127.0.0.1."""
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": DB_PFAD,
        "IT_WEB_BIND": BIND,
        "IT_WEB_PREFIX": "/theatersoap",
        "PYTHONPATH": str(WURZEL),
    })
    prozess = subprocess.Popen(
        [sys.executable, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        _warte_auf_server()
        yield prozess
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=5)
        except subprocess.TimeoutExpired:
            prozess.kill()


@pytest.fixture(scope="module")
def browser():
    if SCHUSSVERZEICHNIS.exists():
        shutil.rmtree(SCHUSSVERZEICHNIS)
    SCHUSSVERZEICHNIS.mkdir(parents=True)
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        yield chromium
        chromium.close()


@pytest.fixture
def seite(server, browser, token):
    """Eine frische Seite je Test, auf der Gruppenseite geoeffnet."""
    kontext = browser.new_context(viewport={"width": 420, "height": 1100})
    seite = kontext.new_page()
    seite.set_default_timeout(GEDULD)
    seite.goto(f"{BASIS}/g/{token}")
    yield seite
    kontext.close()


@pytest.fixture
def datenbank():
    """Eine eigene Verbindung zum Nachsehen -- der Server schreibt aus einem
    anderen Prozess in dieselbe Datei. Genau die Konstellation, die WAL und
    busy_timeout tragen muessen."""
    conn = db.verbinde(DB_PFAD)
    yield conn
    conn.close()


def feld(seite, name: str, index: int = 0):
    return seite.locator(f'.feld[data-feld="{name}"]').nth(index)


def speichere(bereich) -> None:
    """Klickt den Speicherknopf und wartet, bis die Seite 'gespeichert'
    sagt -- die Bestaetigung kommt erst, wenn der Server geantwortet hat."""
    bereich.locator("button.speichern").click()
    expect(bereich.locator(".hinweis")).to_have_text("gespeichert", timeout=GEDULD)


def journaltexte(conn) -> list[str]:
    return [e["text"] for e in repo.journal(conn, 4711) if e["quelle"] == "web"]


def oeffne_journal(seite):
    seite.locator("summary", has_text="Journal").click()


def schuss(seite, name: str) -> None:
    seite.screenshot(path=str(SCHUSSVERZEICHNIS / name), full_page=True)


# --- Der Lauf --------------------------------------------------------------


def test_die_seite_steht_und_zeigt_die_bedienelemente(seite):
    expect(seite.locator("h1")).to_have_text("Die Ankommenden")
    expect(feld(seite, "kernthema").locator("select.auswahl")).to_be_visible()
    expect(feld(seite, "phase").locator("select.auswahl")).to_be_visible()
    expect(feld(seite, "kernfrage").locator("textarea")).to_be_visible()
    # Und die Grenze: das Transkript aus der Datenbank steht nirgends.
    assert MARKER not in seite.content()
    schuss(seite, "01-start.png")


def test_kernthema_ueber_das_dropdown_aendern(seite, datenbank, token):
    """Birks Beispiel, ganz durch: mehrere Vorschlaege im Dropdown, der
    gewaehlte vorausgewaehlt, umstellen, speichern, neu laden -- der neue
    Wert steht, und im Journal steht die Zeile."""
    bereich = feld(seite, "kernthema")
    auswahl = bereich.locator("select.auswahl")
    expect(auswahl).to_have_value("Ankommen und Bleiben")

    auswahl.select_option("Zwei Staedte, ein Koffer")
    speichere(bereich)
    schuss(seite, "02-kernthema-gespeichert.png")

    seite.reload()
    expect(feld(seite, "kernthema").locator("select.auswahl")).to_have_value(
        "Zwei Staedte, ein Koffer"
    )
    assert repo.hole_arbeitsstand(datenbank, 4711)["kernthema"] == \
        "Zwei Staedte, ein Koffer"

    oeffne_journal(seite)
    expect(seite.locator(".eintrag", has_text="Kernthema geändert")).to_be_visible()
    assert any(
        t.startswith("Kernthema geändert über die Gruppenseite: "
                     "Ankommen und Bleiben → Zwei Staedte, ein Koffer")
        for t in journaltexte(datenbank)
    )
    schuss(seite, "03-journal.png")


def test_eigene_formulierung_statt_eines_vorschlags(seite, datenbank):
    """Fehlt der passende Vorschlag, traegt „eigene …" das Freitextfeld
    daneben frei."""
    bereich = feld(seite, "kernthema_richtung")
    bereich.locator("select.auswahl").select_option("__EIGENE__")
    frei = bereich.locator("input.eigene")
    expect(frei).to_be_visible()
    frei.fill("Bleiben, obwohl man gehen könnte")
    speichere(bereich)

    assert repo.hole_arbeitsstand(datenbank, 4711)["kernthema_richtung"] == \
        "Bleiben, obwohl man gehen könnte"


def test_kernfrage_in_die_textbox_schreiben(seite, datenbank):
    """Die Konkretisierung neben dem Kernthema: leer heisst 'noch offen'."""
    bereich = feld(seite, "kernfrage")
    kasten = bereich.locator("textarea")
    expect(kasten).to_have_value("")

    kasten.fill(
        "Frage: Was passiert, wenn man bleibt?\n"
        "Gegensatz: ankommen wollen gegen zurückwollen\n"
        "Einsatz: die eigene Geschichte"
    )
    speichere(bereich)
    schuss(seite, "04-kernfrage.png")

    seite.reload()
    expect(feld(seite, "kernfrage").locator("textarea")).to_contain_text(
        "Was passiert, wenn man bleibt?"
    )
    assert "Gegensatz" in repo.hole_arbeitsstand(datenbank, 4711)["kernfrage"]


def test_figur_umbenennen(seite, datenbank):
    bereich = feld(seite, "figur_name")
    bereich.locator("textarea").fill("Meryem")
    speichere(bereich)

    seite.reload()
    assert [f["name"] for f in repo.figuren(datenbank, 4711)] == ["Meryem", "Pola"]
    expect(feld(seite, "figur_name").locator("textarea")).to_have_value("Meryem")
    schuss(seite, "05-figur-umbenannt.png")


def test_figur_wechselt_das_interview(seite, datenbank):
    """Der Wechsel leert das Sprachprofil und nimmt die Abnahme zurueck --
    im Web laeuft dafuer kein Modell, der Bot holt es im naechsten Zug nach."""
    figur_id = repo.figuren(datenbank, 4711)[0]["id"]
    repo.setze_sprachprofil(datenbank, figur_id, "Kurze Saetze.", ["Ich war da"])
    repo.setze_figur_geprueft(datenbank, figur_id, repo._jetzt())
    interviews = repo.transkripte(datenbank, 4711)

    seite.reload()
    bereich = feld(seite, "figur_quelle")
    expect(bereich.locator("select.auswahl")).to_have_value(str(interviews[0]["id"]))
    bereich.locator("select.auswahl").select_option(str(interviews[1]["id"]))
    speichere(bereich)

    frisch = repo.hole_figur_nach_id(datenbank, figur_id)
    assert frisch["quelle_aufnahme_id"] == interviews[1]["id"]
    assert not (frisch["sprachprofil"] or "").strip()
    assert frisch["geprueft_am"] is None
    assert any(t.startswith("Sprachprofil neu nötig") for t in journaltexte(datenbank))
    schuss(seite, "06-figur-interview.png")


def test_szene_form_aendern(seite, datenbank):
    """Die Szenenplanung steckt in einem zugeklappten <details> -- erst
    aufklappen, dann umstellen."""
    seite.locator("details.szene summary").first.click()
    bereich = feld(seite, "szene_form")
    expect(bereich.locator("select.auswahl")).to_have_value("Dialog")

    bereich.locator("select.auswahl").select_option("Lied")
    speichere(bereich)
    schuss(seite, "07-szene-form.png")

    szene_id = repo.hole_szenen(datenbank, 4711)[0]["id"]
    assert repo.hole_szene(datenbank, szene_id)["form"] == "Lied"
    # Und kein anderes Feld ist mitgegangen.
    assert repo.hole_szene(datenbank, szene_id)["ort"] == "Treppenhaus"


def test_besetzung_der_szene_setzen(seite, datenbank):
    seite.locator("details.szene summary").first.click()
    bereich = feld(seite, "szene_figuren")
    namen = [f["name"] for f in repo.figuren(datenbank, 4711)]
    bereich.locator("select[multiple]").select_option(label=namen)
    speichere(bereich)

    szene_id = repo.hole_szenen(datenbank, 4711)[0]["id"]
    assert [f["name"] for f in repo.szene_figuren(datenbank, szene_id)] == namen


def test_phase_aendern(seite, datenbank):
    bereich = feld(seite, "phase")
    expect(bereich.locator("select.auswahl")).to_have_value("4")

    bereich.locator("select.auswahl").select_option("6")
    speichere(bereich)

    seite.reload()
    expect(feld(seite, "phase").locator("select.auswahl")).to_have_value("6")
    assert repo.hole_phase(datenbank, 4711) == 6
    assert any("Phase 6 · Szenen" in t for t in journaltexte(datenbank))
    schuss(seite, "08-phase.png")


def test_phase_ausserhalb_wird_abgewiesen(seite, datenbank):
    """Was das Dropdown nicht anbietet, weist der Server ab -- geprueft mit
    einer von Hand eingehaengten Option, also genau so, wie es ein
    manipuliertes Formular versuchen wuerde."""
    vorher = repo.hole_phase(datenbank, 4711)
    bereich = feld(seite, "phase")
    bereich.locator("select.auswahl").evaluate(
        "el => { var o = document.createElement('option'); o.value = '9'; "
        "el.appendChild(o); el.value = '9'; }"
    )
    bereich.locator("button.speichern").click()

    expect(bereich.locator(".hinweis")).to_contain_text("1 bis 7", timeout=GEDULD)
    assert repo.hole_phase(datenbank, 4711) == vorher


def test_nachladen_ueberschreibt_kein_offenes_feld(seite):
    """Der Edit-Zustand eines offenen Feldes darf durch das sanfte Nachladen
    nicht verlorengehen. Geprueft ueber die Zeit: NEULADEN_SEKUNDEN ist 10,
    wir warten laenger und tippen dabei nicht zu Ende."""
    bereich = feld(seite, "kernfrage")
    kasten = bereich.locator("textarea")
    kasten.click()
    kasten.fill("Halb getippt, noch nicht gespeichert")

    seite.wait_for_timeout(12000)

    expect(kasten).to_have_value("Halb getippt, noch nicht gespeichert")
    assert bereich.get_attribute("data-schmutzig") == "1"


def test_figur_hinzufuegen_und_wieder_entfernen(seite, datenbank):
    hinzu = feld(seite, "figur_neu")
    hinzu.locator("textarea").fill("Pal")
    speichere(hinzu)

    seite.reload()
    assert "Pal" in [f["name"] for f in repo.figuren(datenbank, 4711)]

    # Entfernen fragt einmal nach: der erste Klick beschriftet den Knopf um.
    letzte = seite.locator('.feld[data-feld="figur_entfernen"]').last
    knopf = letzte.locator("button.speichern")
    knopf.click()
    expect(knopf).to_have_text("Wirklich entfernen?")
    speichere(letzte)

    assert "Pal" not in [f["name"] for f in repo.figuren(datenbank, 4711)]
    schuss(seite, "09-ende.png")


def test_ohne_gueltigen_nonce_schreibt_die_seite_nicht(seite, datenbank, token):
    """Ein fremder Link soll nicht schreiben koennen. Hier von innen
    geprueft: der Nonce wird aus der Seite entfernt, danach geht nichts
    mehr durch."""
    vorher = repo.hole_arbeitsstand(datenbank, 4711)["begriffe"]
    seite.evaluate("document.getElementById('nonce').value = 'kaputt'")
    bereich = feld(seite, "begriffe")
    bereich.locator("textarea").fill("Heimlich geaendert")
    bereich.locator("button.speichern").click()

    expect(bereich.locator(".hinweis")).to_contain_text("neu laden", timeout=GEDULD)
    assert repo.hole_arbeitsstand(datenbank, 4711)["begriffe"] == vorher
