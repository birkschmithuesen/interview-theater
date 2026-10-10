import pytest

from interview_theater import repo, stueck, web, web_daten, workshop
from tests.stueck_hilfe import lege_karte_an


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def test_web_und_bot_zeigen_dieselbe_karte(conn, padua):
    repo.setze_figur(conn, 1, "Anna", "")
    sid = lege_karte_an(conn, ort="Bar", wer="Anna (Arlecchino), il pubblico", fragen=["Wann?"])
    token = repo.stelle_web_token_sicher(conn, 1)
    daten = web_daten.gruppe_nach_token(conn, token)
    [s] = daten["szenen"]
    assert s["karte"] == stueck.karte(conn, repo.hole_szene(conn, sid))
    [k] = web_daten.szenenkarten(conn, 1)
    assert k["karte"] == s["karte"]


def test_padua_werkbank_zeigt_wo_und_wer(conn, padua):
    repo.setze_figur(conn, 1, "Anna", "")
    lege_karte_an(conn, ort="Sala riunioni", wer="Anna")
    token = repo.stelle_web_token_sicher(conn, 1)
    daten = web_daten.gruppe_nach_token(conn, token)
    html = web._wb_szenen_verdichtet_html(
        [dict(s, verdichtet=s.get("verdichtet") or {}) for s in daten["szenen"]])
    assert "Sala riunioni" in html and "Anna" in html
