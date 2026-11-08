"""Downloads an einem Bedarfspunkt (Birk 08.10.2026 ~13:50, Nachtrag 1):
``/g/<token>/bedarf/<datei>`` liefert NUR eine Datei, die ein (nicht
entfernter) Bedarfspunkt GENAU DIESER Gruppe traegt -- Dateiname gegen eine
strikte Positivliste und gegen ``bedarf_punkt.datei`` dieser Gruppe
geprueft, kein Dateisystempfad aus der URL. Gegen einen echten, lokalen
HTTP-Server gemessen wie ``tests/test_web_static_handys.py``."""

import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from interview_theater import db, repo, web

CHAT = 7_000_000_000_004
ANDERE_CHAT = 7_000_000_000_005


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    repo.ersetze_unerledigte_bedarf_punkte(
        conn, CHAT, [("Props", [("Floor plan", "floor-plan.pdf")])]
    )
    conn.commit()

    verz = tmp_path / "betrieb" / "bedarf" / str(CHAT)
    verz.mkdir(parents=True)
    (verz / "floor-plan.pdf").write_bytes(b"%PDF-1.4 echter inhalt")

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad, tmp_path
    dienst.shutdown()


def _hole_roh(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as antwort:
            return antwort.status, antwort.read(), antwort.headers
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read(), fehler.headers


def test_eine_eigene_datei_kommt_an(aufbau):
    basis, token, _pfad, _tmp = aufbau
    status, koerper, header = _hole_roh(
        f"{basis}/theatersoap/g/{token}/bedarf/floor-plan.pdf"
    )
    assert status == 200
    assert header["Content-Type"] == "application/pdf"
    assert header["Content-Disposition"] == 'attachment; filename="floor-plan.pdf"'
    assert koerper == b"%PDF-1.4 echter inhalt"


def test_falsches_token_ist_404(aufbau):
    basis, _token, _pfad, _tmp = aufbau
    status, _koerper, _header = _hole_roh(
        f"{basis}/theatersoap/g/falsches-token/bedarf/floor-plan.pdf"
    )
    assert status == 404


def test_fremde_gruppe_sieht_die_datei_nicht(aufbau):
    """Dieselbe Datei existiert auf der Platte (anderes Verzeichnis), aber
    die FREMDE Gruppe hat keinen Bedarfspunkt damit -- 404, nicht 200."""
    basis, _token, pfad, tmp_path = aufbau
    conn = db.verbinde(pfad)
    repo.sichere_gruppe(conn, ANDERE_CHAT, "gruppe2", "Andere Gruppe")
    repo.setze_gruppe_kanal(conn, ANDERE_CHAT, "web")
    anderer_token = repo.stelle_web_token_sicher(conn, ANDERE_CHAT)
    conn.commit()
    verz = tmp_path / "betrieb" / "bedarf" / str(ANDERE_CHAT)
    verz.mkdir(parents=True)
    (verz / "floor-plan.pdf").write_bytes(b"andere datei")

    status, _koerper, _header = _hole_roh(
        f"{basis}/theatersoap/g/{anderer_token}/bedarf/floor-plan.pdf"
    )
    assert status == 404


def test_fremde_gruppe_bekommt_die_eigentliche_datei_nicht_ueber_den_eigenen_token(aufbau):
    """Die FREMDE Gruppe darf NICHT ueber ihr eigenes (gueltiges) Token an
    die Datei der ersten Gruppe kommen, selbst wenn sie den Dateinamen
    kennt -- ``bedarf_punkt.datei`` dieser Gruppe entscheidet, nicht die
    Platte."""
    basis, _token, pfad, _tmp = aufbau
    conn = db.verbinde(pfad)
    repo.sichere_gruppe(conn, ANDERE_CHAT, "gruppe2", "Andere Gruppe")
    repo.setze_gruppe_kanal(conn, ANDERE_CHAT, "web")
    anderer_token = repo.stelle_web_token_sicher(conn, ANDERE_CHAT)
    conn.commit()

    status, _koerper, _header = _hole_roh(
        f"{basis}/theatersoap/g/{anderer_token}/bedarf/floor-plan.pdf"
    )
    assert status == 404


def test_unbekannte_datei_ist_404(aufbau):
    basis, token, _pfad, _tmp = aufbau
    status, _koerper, _header = _hole_roh(
        f"{basis}/theatersoap/g/{token}/bedarf/unbekannt.pdf"
    )
    assert status == 404


@pytest.mark.parametrize("name", [
    "..%2f..%2f..%2fetc%2fpasswd",
    "..%2ffloor-plan.pdf",
    "..%2f..%2fweb.py",
    f"{CHAT}%2ffloor-plan.pdf",
    "floor-plan.pdf%00.png",
    "a/floor-plan.pdf",
])
def test_traversal_bleibt_404(aufbau, name):
    basis, token, _pfad, _tmp = aufbau
    status, _koerper, _header = _hole_roh(
        f"{basis}/theatersoap/g/{token}/bedarf/{name}"
    )
    assert status == 404


def test_direkter_traversal_pfad_ohne_kodierung_ist_404(aufbau):
    basis, token, _pfad, _tmp = aufbau
    status, _koerper, _header = _hole_roh(
        f"{basis}/theatersoap/g/{token}/bedarf/../../../../etc/passwd"
    )
    assert status in (404, 400)


def test_entfernter_punkt_macht_die_datei_unerreichbar(aufbau):
    """Ein erneuter Seed-Lauf ohne den Floorplan-Punkt entfernt ihn weich --
    die Datei bleibt auf der Platte liegen (kein Loeschpfad hier), ist aber
    nicht mehr erreichbar."""
    basis, token, pfad, _tmp = aufbau
    conn = db.verbinde(pfad)
    repo.ersetze_unerledigte_bedarf_punkte(conn, CHAT, [("Props", ["Chair"])])
    conn.commit()

    status, _koerper, _header = _hole_roh(
        f"{basis}/theatersoap/g/{token}/bedarf/floor-plan.pdf"
    )
    assert status == 404


def test_datei_fehlt_auf_platte_ist_404(aufbau, tmp_path):
    basis, token, pfad, tmp = aufbau
    conn = db.verbinde(pfad)
    repo.ersetze_unerledigte_bedarf_punkte(
        conn, CHAT, [("Props", [("Floor plan", "floor-plan.pdf"), ("Missing", "fehlt.pdf")])]
    )
    conn.commit()

    status, _koerper, _header = _hole_roh(
        f"{basis}/theatersoap/g/{token}/bedarf/fehlt.pdf"
    )
    assert status == 404
