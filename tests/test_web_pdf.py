"""Das Stage Script als PDF (Birk 07.10.2026 ~19:35, Nachtrag 3 Punkt 2a):
Route ``/g/<token>/textbuch.pdf`` und Knopf "PDF" im Script-Tab nur unter
``[karten] aktiv``; gedruckt wird die Probenansicht mit A4-Druckregeln."""

import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from interview_theater import db, repo, web, web_pdf, workshop

from test_szenenkarte import padua  # noqa: F401


@pytest.fixture
def server(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 41, "gruppe1", "G")
    repo.setze_gruppe_kanal(conn, 41, "web")
    token = repo.stelle_web_token_sicher(conn, 41)
    sid = repo.stelle_szene_sicher(conn, 41, 1)
    repo.setze_szenenfeld(conn, sid, "titel", "Tornare")
    repo.setze_stagescript(conn, sid, "Emma steht auf.\n\n---\n\n> *Interview quote (6):* \"casa\"", None)
    conn.commit()
    conn.close()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token
    dienst.shutdown()


def _hole(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as f:
        return f.code, f.headers.get("Content-Type"), f.read()


def test_ohne_schalter_kein_pdf(server):
    basis, token = server
    assert workshop.szenenkarten_aktiv() is False
    status, _, _ = _hole(f"{basis}/g/{token}/textbuch.pdf")
    assert status == 404
    _, _, seite = _hole(f"{basis}/g/{token}/textbuch")
    assert b"textbuch.pdf" not in seite


def test_mit_schalter_pdf_und_knopf(server, padua, monkeypatch):
    basis, token = server
    gesehen = {}

    def falsches_pdf(html, chrome=None):
        gesehen["html"] = web_pdf.mit_druck_css(html)
        return b"%PDF-1.4 test"

    monkeypatch.setattr(web_pdf, "pdf_aus_html", falsches_pdf)
    status, typ, roh = _hole(f"{basis}/g/{token}/textbuch.pdf")
    assert (status, typ, roh) == (200, "application/pdf", b"%PDF-1.4 test")
    assert "@page { size: A4" in gesehen["html"] and "Emma steht auf." in gesehen["html"]
    assert '<hr class="trenner">' in gesehen["html"]
    assert 'class="interviewzitat"' in gesehen["html"]
    _, _, seite = _hole(f"{basis}/g/{token}/textbuch")
    assert b'class="pdf-knopf"' in seite and b"/textbuch.pdf" in seite


def test_fehler_beim_drucken_ist_503(server, padua, monkeypatch):
    basis, token = server

    def kaputt(html, chrome=None):
        raise RuntimeError("kein Chromium")

    monkeypatch.setattr(web_pdf, "pdf_aus_html", kaputt)
    status, _, _ = _hole(f"{basis}/g/{token}/textbuch.pdf")
    assert status == 503


@pytest.mark.skipif(not Path(web_pdf.CHROME_VORGABE).exists(), reason="ohne Headless-Shell")
def test_echtes_pdf_mit_der_headless_shell():
    roh = web_pdf.pdf_aus_html("<html><head></head><body><h1>Scene 1</h1></body></html>")
    assert roh.startswith(b"%PDF")
