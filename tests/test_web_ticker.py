"""Der Regie-Ticker als Webseite: Tab im Dashboard, eigene Route
``/dashboard/<token>/ticker`` (Birk 05.10.2026 21:45) -- derselbe
Token-Check wie ``/dashboard/<token>``, Eintraege aus ``IT_WEB_TICKER_DATEI``
(JSON-Zeilen), neueste zuerst. Ohne die Variable bleibt das Dashboard
byte-gleich wie vorher (Dortmund setzt sie nie)."""
import json
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
    conn.commit()
    conn.close()
    return pfad


def _laufe(pfad, monkeypatch, ticker_datei=None):
    monkeypatch.setenv("IT_WEB_DASHBOARD_TOKEN", TOKEN)
    if ticker_datei is not None:
        monkeypatch.setenv("IT_WEB_TICKER_DATEI", str(ticker_datei))
    else:
        monkeypatch.delenv("IT_WEB_TICKER_DATEI", raising=False)
    handler = web.mache_handler(pfad, "/padua", b"k" * 32)
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_falscher_token_404(server, monkeypatch):
    srv, basis = _laufe(server, monkeypatch)
    try:
        code, _ = _hole(basis, "/padua/dashboard/falsch/ticker")
        assert code == 404
    finally:
        srv.shutdown()


def test_ohne_umgebungsvariable_200_und_freundlicher_text(server, monkeypatch):
    srv, basis = _laufe(server, monkeypatch, ticker_datei=None)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert "Ticker aus" in text
    finally:
        srv.shutdown()


def test_datei_fehlt_200_und_freundlicher_text(server, monkeypatch, tmp_path):
    fehlend = tmp_path / "nicht-da.jsonl"
    srv, basis = _laufe(server, monkeypatch, ticker_datei=fehlend)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert "Noch keine" in text
    finally:
        srv.shutdown()


def test_eintraege_neueste_zuerst(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({"zeit": "2026-10-05T10:00:00+00:00", "text": "erster Eintrag"}) + "\n"
        + json.dumps({"zeit": "2026-10-05T11:00:00+00:00", "text": "zweiter Eintrag"}) + "\n",
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert text.index("zweiter Eintrag") < text.index("erster Eintrag")
    finally:
        srv.shutdown()


def test_unvollstaendige_zeile_wird_ignoriert(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({"zeit": "2026-10-05T10:00:00+00:00", "text": "gueltiger Eintrag"}) + "\n"
        + '{"zeit": "2026-10-05T11:00:00+00:00", "text": "abgeschn',
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert "gueltiger Eintrag" in text
        assert "abgeschn" not in text
    finally:
        srv.shutdown()


def test_tab_im_dashboard_nur_mit_gesetzter_umgebungsvariable(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text("", encoding="utf-8")
    srv, basis = _laufe(server, monkeypatch, ticker_datei=None)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}")
        assert code == 200
        assert f"/dashboard/{TOKEN}/ticker" not in text
    finally:
        srv.shutdown()
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}")
        assert code == 200
        assert f"/dashboard/{TOKEN}/ticker" in text
    finally:
        srv.shutdown()
