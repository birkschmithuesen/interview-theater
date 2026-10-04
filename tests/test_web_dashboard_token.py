"""Die Uebersicht ist mit IT_WEB_DASHBOARD_TOKEN nur unter /dashboard/<token> lesbar
(Birk 04.10.2026: offen unter "/" verriet sie alle Gruppenlinks)."""
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web

TOKEN = "dash-test-token-123"


def _hole(basis, pfad):
    try:
        with urllib.request.urlopen(basis + pfad, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as f:
        return f.code, ""


@pytest.fixture
def server(tmp_path):
    pfad = str(tmp_path / "d.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "g1", "Gruppe Eins")
    gtoken = repo.stelle_web_token_sicher(conn, 1)
    conn.commit()
    conn.close()
    return pfad, gtoken


def _laufe(pfad, monkeypatch, dash_token):
    if dash_token:
        monkeypatch.setenv("IT_WEB_DASHBOARD_TOKEN", dash_token)
    else:
        monkeypatch.delenv("IT_WEB_DASHBOARD_TOKEN", raising=False)
    handler = web.mache_handler(pfad, "/padua", b"k" * 32)
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_ohne_token_bleibt_die_uebersicht_unter_root(server, monkeypatch):
    pfad, gtoken = server
    srv, basis = _laufe(pfad, monkeypatch, None)
    try:
        code, text = _hole(basis, "/padua/")
        assert code == 200 and gtoken in text
    finally:
        srv.shutdown()


def test_mit_token_ist_root_404_und_u_token_zeigt_die_uebersicht(server, monkeypatch):
    pfad, gtoken = server
    srv, basis = _laufe(pfad, monkeypatch, TOKEN)
    try:
        code, text = _hole(basis, "/padua/")
        assert code == 404 and gtoken not in text
        assert _hole(basis, "/padua/dashboard/falsch")[0] == 404
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}")
        assert code == 200 and gtoken in text
        assert _hole(basis, f"/padua/g/{gtoken}")[0] == 200
    finally:
        srv.shutdown()
