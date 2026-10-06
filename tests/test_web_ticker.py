"""Der Regie-Ticker als Webseite: Tab im Dashboard, eigene Route
``/dashboard/<token>/ticker`` (Birk 05.10.2026 21:45, Addendum 3
06.10.2026) -- derselbe Token-Check wie ``/dashboard/<token>``, Eintraege
aus ``IT_WEB_TICKER_DATEI`` (JSON-Zeilen), neueste zuerst, gross und offen;
aeltere gedaempft und eingeklappt. TECHNIK steckt je Eintrag in einem
eingeklappten ``<details>`` mit einer Ampel im Titel. Ohne die Variable
bleibt das Dashboard byte-gleich wie vorher (Dortmund setzt sie nie)."""
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


def _jetzt_iso(vor_minuten: float = 0) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(minutes=vor_minuten)).isoformat()


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
        json.dumps({"zeit": _jetzt_iso(20), "text": "erster Eintrag"}) + "\n"
        + json.dumps({"zeit": _jetzt_iso(5), "text": "zweiter Eintrag"}) + "\n",
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
        json.dumps({"zeit": _jetzt_iso(5), "text": "gueltiger Eintrag"}) + "\n"
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


def test_altes_format_rendert_weiterhin(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({"zeit": _jetzt_iso(5), "text": "alter Eintrag ohne Teile"}) + "\n",
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert "alter Eintrag ohne Teile" in text
        assert '<details class="ticker-technik">' not in text  # kein Technik-Detail
        assert 'class="ticker-eintrag' in text
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


# --- Addendum 3: Technik als eingeklapptes Detail mit Ampel -----------------

def test_technik_steckt_in_geschlossenem_details_ohne_open_attribut(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({
            "zeit": _jetzt_iso(1), "text": "zusammengefasst",
            "inhalt": "• G1: ruhig", "technik": "✓ Technik unauffällig",
        }) + "\n",
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert '<details class="ticker-technik">' in text
        assert '<details class="ticker-technik" open' not in text
        assert "<details open" not in text
    finally:
        srv.shutdown()


def test_technik_ampel_gruen_ohne_warnung(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({
            "zeit": _jetzt_iso(1), "text": "x",
            "inhalt": "• G1: ruhig", "technik": "✓ Technik unauffällig",
        }) + "\n",
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert '<summary class="ampel-gruen">' in text
        assert "Technik unauffällig" in text
        assert '<summary class="ampel-gelb">' not in text
    finally:
        srv.shutdown()


def test_technik_ampel_gelb_mit_anzahl_der_warnungen(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({
            "zeit": _jetzt_iso(1), "text": "x",
            "inhalt": "• G1: ruhig",
            "technik": "⚠ Verdacht: G2 Aufnahme haengt seit 7 min\n"
                       "⚠ Verdacht: Dienst padua-gruppe2 ist failed\n• wirkt normal sonst",
        }) + "\n",
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert '<summary class="ampel-gelb">' in text
        assert "Verdacht (2)" in text
        assert 'class="ticker-warnung"' in text
        assert "G2 Aufnahme haengt seit 7 min" in text
    finally:
        srv.shutdown()


def test_inhalt_block_steht_vor_dem_technik_block(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({
            "zeit": _jetzt_iso(1), "text": "x",
            "inhalt": "• G1: markanter Inhaltstext",
            "technik": "⚠ Verdacht: markanter Technikfund",
        }) + "\n",
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert text.index("markanter Inhaltstext") < text.index("markanter Technikfund")
        assert text.index('class="ticker-inhalt"') < text.index('class="ticker-technik"')
    finally:
        srv.shutdown()


def test_inhalt_gruppiert_nach_g1_g2_g3_praefix(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({
            "zeit": _jetzt_iso(1), "text": "x",
            "inhalt": "• G1: ruhig in Phase Fragen\n• G2: Konflikt um Begriff\n"
                      "• ✨ ein starkes Zitat",
            "technik": "✓ Technik unauffällig",
        }) + "\n",
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert "<h3>G1</h3>" in text
        assert "<h3>G2</h3>" in text
        assert "ruhig in Phase Fragen" in text
        assert "✨ ein starkes Zitat" in text
    finally:
        srv.shutdown()


def test_echte_ul_bullets_statt_rohem_punkt_text(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({
            "zeit": _jetzt_iso(1), "text": "x",
            "inhalt": "• G1: etwas", "technik": "✓ Technik unauffällig",
        }) + "\n",
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert "<ul>" in text
        assert "<li>" in text
    finally:
        srv.shutdown()


def test_stale_warnung_wenn_neuester_eintrag_ueber_15_minuten_alt(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({"zeit": _jetzt_iso(23), "text": "letzter Stand"}) + "\n",
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert "Ticker steht seit 23 min" in text
    finally:
        srv.shutdown()


def test_keine_stale_warnung_bei_frischem_eintrag(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({"zeit": _jetzt_iso(2), "text": "letzter Stand"}) + "\n",
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert '<span class="ticker-stale">' not in text
        assert "Ticker steht" not in text
    finally:
        srv.shutdown()


def test_aeltere_eintraege_sind_eingeklappte_details(server, monkeypatch, tmp_path):
    datei = tmp_path / "eintraege.jsonl"
    datei.write_text(
        json.dumps({"zeit": _jetzt_iso(12), "text": "aelterer Eintrag"}) + "\n"
        + json.dumps({"zeit": _jetzt_iso(1), "text": "neuester Eintrag"}) + "\n",
        encoding="utf-8",
    )
    srv, basis = _laufe(server, monkeypatch, ticker_datei=datei)
    try:
        code, text = _hole(basis, f"/padua/dashboard/{TOKEN}/ticker")
        assert code == 200
        assert '<article class="ticker-eintrag ticker-neu">' in text
        assert '<details class="ticker-eintrag ticker-alt">' in text
        # kein "open" auf dem aelteren Eintrag -- er bleibt eingeklappt
        assert '<details class="ticker-eintrag ticker-alt" open' not in text
    finally:
        srv.shutdown()
