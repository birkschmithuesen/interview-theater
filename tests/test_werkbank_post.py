"""Der Werkbank-POST in Padua: 403. Die Chat-Wege laufen weiter."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, sprache, web, workshop

CHAT = 7_000_000_000_001
SCHLUESSEL = b"w" * 32


def _profil(monkeypatch, name):
    monkeypatch.setenv(workshop.VARIABLE, name)
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture
def dienst(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    server = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", token, pfad
    server.shutdown()
    workshop.vergiss()
    sprache.vergiss()


def _post(url: str, koerper: dict) -> tuple[int, str]:
    anfrage = urllib.request.Request(
        url, data=json.dumps(koerper).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _rahmen(pfad: str) -> str:
    conn = db.verbinde(pfad)
    try:
        return conn.execute(
            "SELECT rahmen FROM arbeitsstand WHERE chat_id = ?", (CHAT,)).fetchone()[0]
    finally:
        conn.close()


def _werkbank_post(basis, token):
    return _post(f"{basis}/g/{token}", {
        "nonce": web.nonce(SCHLUESSEL, token), "feld": "rahmen", "wert": "Markt, mittags"})


def test_werkbank_post_in_padua_ist_403(dienst, monkeypatch):
    basis, token, pfad = dienst
    _profil(monkeypatch, "padua-2026")
    status, text = _werkbank_post(basis, token)
    assert status == 403
    assert text == web.T._TEXT_WERKBANK_NUR_LESEN
    assert _rahmen(pfad) == "Bahnhof, nachts"


def test_werkbank_post_in_dortmund_wirkt_wie_bisher(dienst, monkeypatch):
    basis, token, pfad = dienst
    _profil(monkeypatch, "dortmund-2026")
    status, _text = _werkbank_post(basis, token)
    assert status == 200
    assert _rahmen(pfad) == "Markt, mittags"


def test_chat_senden_in_padua_wird_angenommen(dienst, monkeypatch):
    basis, token, _pfad = dienst
    _profil(monkeypatch, "padua-2026")
    status, _text = _post(f"{basis}/g/{token}/chat/senden",
                          {"nonce": web.nonce(SCHLUESSEL, token), "text": "hello bot"})
    assert status == 202


def test_phasenklick_in_padua_wird_angenommen(dienst, monkeypatch):
    basis, token, _pfad = dienst
    _profil(monkeypatch, "padua-2026")
    status, _text = _post(f"{basis}/g/{token}/chat/phase",
                          {"nonce": web.nonce(SCHLUESSEL, token), "nummer": 2, "bestaetigt": 1})
    assert status == 202
