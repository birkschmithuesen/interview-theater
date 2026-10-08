"""Volltranskript-PDFs je Interview-Untergruppe in der Werkbank (Birk
08.10.2026 ~15:15): Route liefert nur PDFs aus dem Verzeichnis der eigenen
Gruppe, Liste erscheint unter Interviews."""
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web

CHAT = 7_000_000_000_004
ANDERE = 7_000_000_000_005


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    for ch in (CHAT, ANDERE):
        repo.sichere_gruppe(conn, ch, f"g{ch}", "G")
        repo.setze_gruppe_kanal(conn, ch, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    for ch, name in ((CHAT, "G1-trascrizioni-sottogruppo-1.pdf"), (ANDERE, "G2-fremd.pdf")):
        v = tmp_path / "betrieb" / "transkripte" / str(ch)
        v.mkdir(parents=True)
        (v / name).write_bytes(b"%PDF-1.4 x")
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/p", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}/p/g/{token}"
    dienst.shutdown()


def _hole(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as a:
            return a.status, a.read()
    except urllib.error.HTTPError as f:
        return f.code, b""


def test_eigene_transkripte_kommen_an_fremde_nicht(aufbau):
    assert _hole(f"{aufbau}/transkripte/G1-trascrizioni-sottogruppo-1.pdf") == (200, b"%PDF-1.4 x")
    assert _hole(f"{aufbau}/transkripte/G2-fremd.pdf")[0] == 404
    assert _hole(f"{aufbau}/transkripte/..%2F..%2Ft.db")[0] == 404
    assert _hole(f"{aufbau}/transkripte/nicht-da.pdf")[0] == 404


def test_liste_in_der_werkbank(aufbau, tmp_path):
    html = web._transkript_downloads_html(CHAT, "tok")
    assert "tok/transkripte/G1-trascrizioni-sottogruppo-1.pdf" in html
    assert "G2-fremd" not in html
    assert web._transkript_downloads_html(7_000_000_000_999, "tok") == ""
