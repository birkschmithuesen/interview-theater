"""Die Telefon-Organisationskarten als statische Dateien (UX-Knoepfe-Karte,
Abschnitt 5): ``/g/<token>/static/handys/<name>.png`` liefert genau die
sieben committeten PNGs aus ``interview_theater/static/handys/`` aus --
ueber eine strikte Positivliste, kein Dateisystempfad aus der URL. Hier
gegen einen echten, lokalen HTTP-Server gemessen (wie
``tests/test_web_vereint.py``), damit ein Traversal-Versuch wirklich durch
die Leitung geht und nicht nur gegen eine Python-Funktion."""

import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from interview_theater import db, repo, web

CHAT = 7_000_000_000_003


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token
    dienst.shutdown()


def _hole_roh(url):
    """Wie ``test_web_vereint._hole``, nur OHNE ``.decode("utf-8")`` -- ein
    PNG ist kein Text."""
    try:
        with urllib.request.urlopen(url, timeout=5) as antwort:
            return antwort.status, antwort.read(), antwort.headers
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read(), fehler.headers


def test_eine_echte_karte_kommt_als_png_an(aufbau):
    basis, token = aufbau
    status, koerper, header = _hole_roh(
        f"{basis}/theatersoap/g/{token}/static/handys/phase-1.png"
    )

    assert status == 200
    assert header["Content-Type"] == "image/png"
    assert koerper[:8] == b"\x89PNG\r\n\x1a\n"  # PNG-Signatur
    assert len(koerper) > 1000


def test_der_body_ist_byte_fuer_byte_die_quelldatei(aufbau):
    """Regression fuer den Live-NameError in ``_antworte_binaer`` (Karte
    Padua Brainstorm, 03.10.2026): eine ueberzaehlige Zeile
    ``self.wfile.write(roh)`` griff auf einen nie definierten Namen zu und
    warf bei JEDEM Abruf einer Telefon-Organisationskarte einen NameError
    (``padua-web.log``, 21:40:02). Die Pruefung auf PNG-Signatur und
    Mindestlaenge allein haette das nicht bemerkt -- hier deshalb der
    gesamte Body gegen die Quelldatei auf der Platte, nicht nur ein
    Praefix."""
    basis, token = aufbau
    status, koerper, header = _hole_roh(
        f"{basis}/theatersoap/g/{token}/static/handys/phase-1.png"
    )
    quelle = (
        Path(__file__).resolve().parent.parent
        / "interview_theater" / "static" / "handys" / "phase-1.png"
    ).read_bytes()

    assert status == 200
    assert header["Content-Type"] == "image/png"
    assert koerper == quelle


def test_jede_der_sieben_karten_ist_erreichbar(aufbau):
    basis, token = aufbau
    for nummer in range(1, 8):
        status, _koerper, _header = _hole_roh(
            f"{basis}/theatersoap/g/{token}/static/handys/phase-{nummer}.png"
        )
        assert status == 200, nummer


def test_ein_unbekannter_name_ist_404(aufbau):
    basis, token = aufbau
    status, _koerper, _header = _hole_roh(
        f"{basis}/theatersoap/g/{token}/static/handys/phase-8.png"
    )
    assert status == 404


@pytest.mark.parametrize("name", [
    "..%2f..%2f..%2fetc%2fpasswd",
    "..%2fanweisungen.py",
    "..%2f..%2fweb.py",
    "phase-1.PNG",            # Grossbuchstaben -- die Positivliste ist eng
    "phase_1.png",            # Unterstrich statt Bindestrich
    "phase-1.png.py",
    "phase-1",
    ".png",
    "handys/phase-1.png",     # ein zweiter Schraegstrich im Namen
    "%2e%2e%2fphase-1.png",
])
def test_traversal_und_fremde_namen_bleiben_404(aufbau, name):
    basis, token = aufbau
    status, _koerper, _header = _hole_roh(
        f"{basis}/theatersoap/g/{token}/static/handys/{name}"
    )
    assert status == 404


def test_ein_direkter_traversal_pfad_ohne_kodierung_ist_404(aufbau):
    """``urlopen`` normalisiert ``../`` im Pfad selbst schon weg -- trotzdem
    schadlos, weil ``_sende_static_bild`` den Namen gegen die Positivliste
    prueft und nicht gegen einen aufgeloesten Pfad."""
    basis, token = aufbau
    status, _koerper, _header = _hole_roh(
        f"{basis}/theatersoap/g/{token}/static/handys/../../../../etc/passwd"
    )
    assert status in (404, 400)
