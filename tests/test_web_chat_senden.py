"""Text aus dem Browser -- derselbe Weg wie eine Telegram-Nachricht.

Die Reihenfolge der Pruefungen ist dieselbe wie in web._beantworte_post:
Pfad, Token, Nonce, Wert -- erst 404, dann 403, dann 400. Ein unbekanntes
Token bekommt 404, weil der Nonce an das Token gebunden ist und fuer ein
Token, das es nicht gibt, gar nicht gueltig sein kann.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_chat

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad
    dienst.shutdown()


def _post(url: str, koerper: dict, typ: str = "application/json"):
    anfrage = urllib.request.Request(
        url, data=json.dumps(koerper).encode("utf-8"),
        headers={"Content-Type": typ}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def _nonce(token: str) -> str:
    return web.nonce(SCHLUESSEL, token)


def test_senden_legt_einen_eingang_an(aufbau):
    basis, token, pfad = aufbau
    status, text = _post(
        f"{basis}/g/{token}/chat/senden",
        {"nonce": _nonce(token), "text": "Unsere Begriffe: Ankommen, Arbeit, Nacht"},
    )
    assert status == 202
    message_id = json.loads(text)["message_id"]

    conn = db.verbinde(pfad)
    zeile = repo.hole_web_post(conn, message_id)
    assert zeile["richtung"] == repo.RICHTUNG_EIN
    assert zeile["typ"] == repo.WEB_TYP_TEXT
    assert zeile["text"] == "Unsere Begriffe: Ankommen, Arbeit, Nacht"
    assert zeile["chat_id"] == CHAT


def test_senden_greift_auch_hinter_dem_praefix(aufbau):
    basis, token, _pfad = aufbau
    status, _text = _post(
        f"{basis}/theatersoap/g/{token}/chat/senden",
        {"nonce": _nonce(token), "text": "hallo"},
    )
    assert status == 202


def test_ohne_nonce_gibt_es_403(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/senden", {"text": "hallo"})
    assert fehler.value.code == 403


def test_falscher_nonce_gibt_403(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/senden",
              {"nonce": "0.deadbeef", "text": "hallo"})
    assert fehler.value.code == 403


def test_unbekanntes_token_gibt_404_und_nicht_403(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/gibtsnicht/chat/senden",
              {"nonce": _nonce(token), "text": "hallo"})
    assert fehler.value.code == 404


def test_leerer_text_gibt_400_und_legt_nichts_an(aufbau):
    basis, token, pfad = aufbau
    for wert in ("", "   ", "\n\n"):
        with pytest.raises(urllib.error.HTTPError) as fehler:
            _post(f"{basis}/g/{token}/chat/senden",
                  {"nonce": _nonce(token), "text": wert})
        assert fehler.value.code == 400
    conn = db.verbinde(pfad)
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0


def test_zu_langer_text_gibt_400(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/senden",
              {"nonce": _nonce(token), "text": "A" * (web_chat.MAX_TEXT_ZEICHEN + 1)})
    assert fehler.value.code == 400


def test_kaputtes_json_gibt_400(aufbau):
    basis, token, _pfad = aufbau
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/senden", data=b"{kaputt",
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 400


def test_unbekannter_unterpfad_gibt_404(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/g/{token}/chat/irgendwas", {"nonce": _nonce(token)})
    assert fehler.value.code == 404


def test_das_dashboard_nimmt_weiter_kein_post_an(aufbau):
    """Es haengt am Beamer -- dort soll niemand im Vorbeigehen etwas
    umstellen (AGENTS.md)."""
    basis, _token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(f"{basis}/", {"nonce": "x"})
    assert fehler.value.code == 404


def test_die_gesendete_nachricht_steht_im_verlauf(aufbau):
    basis, token, _pfad = aufbau
    _post(f"{basis}/g/{token}/chat/senden",
          {"nonce": _nonce(token), "text": "Unsere Begriffe"})
    with urllib.request.urlopen(f"{basis}/g/{token}/chat/zustand?nach=0",
                                timeout=5) as antwort:
        zustand = json.loads(antwort.read().decode("utf-8"))
    assert [n["text"] for n in zustand["nachrichten"]] == ["Unsere Begriffe"]
    assert zustand["nachrichten"][0]["von"] == "gruppe"


def test_der_text_wird_nicht_beim_schreiben_gefiltert(aufbau):
    """Gefiltert wird beim LESEN (sichere_html), nicht beim Schreiben: der Bot
    soll den Wortlaut der Gruppe sehen, und ``<`` in einer Nachricht ist keine
    Absicht, sondern ein Zeichen."""
    basis, token, pfad = aufbau
    _status, text = _post(f"{basis}/g/{token}/chat/senden",
                          {"nonce": _nonce(token), "text": "3 < 5 & <b>fett</b>"})
    message_id = json.loads(text)["message_id"]
    conn = db.verbinde(pfad)
    assert repo.hole_web_post(conn, message_id)["text"] == "3 < 5 & <b>fett</b>"


def test_kein_absendername_liegt_im_eingang(aufbau):
    """E8: Web-Nachrichten tragen keinen Vornamen. Es gibt nicht einmal eine
    Spalte dafuer -- ``web_kanal.ABSENDER`` setzt das Rollenwort erst beim
    Bauen des Updates."""
    basis, token, pfad = aufbau
    _status, text = _post(f"{basis}/g/{token}/chat/senden",
                          {"nonce": _nonce(token), "text": "hallo"})
    conn = db.verbinde(pfad)
    zeile = repo.hole_web_post(conn, json.loads(text)["message_id"])
    assert "absender" not in zeile.keys()
