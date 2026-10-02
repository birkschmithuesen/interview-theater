"""Angriff: POST von einer fremden Seite -- mit gueltigem Nonce.

Der Nonce schuetzt, WEIL eine fremde Seite unser HTML nicht lesen kann. Er
schuetzt nicht mehr, sobald er anderswo auftaucht: beim Audio-Upload stand er
bis hier in der Query und damit in der Serverlogzeile (A2-Uebergabe Punkt 3),
und das Token steht ohnehin schon im Pfad. Wer das Log sieht, hat beides.

Deshalb Origin als zweite, unabhaengige Schicht -- sie haengt nicht an einem
Geheimnis, sondern daran, wo der Browser steht.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web

CHAT = 1
SCHLUESSEL = b"x" * 32


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_phase(conn, CHAT, 4)
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Eine Nacht im Treppenhaus")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad
    dienst.shutdown()


def _post(url: str, koerper: dict, kopf: dict | None = None):
    anfrage = urllib.request.Request(
        url, data=json.dumps(koerper).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", **(kopf or {})},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _gueltig(token: str) -> dict:
    return {"nonce": web.nonce(SCHLUESSEL, token), "feld": "rahmen",
            "wert": "Ein Hinterhof im Regen"}


def _rahmen(pfad: str) -> str | None:
    conn = db.verbinde(pfad)
    try:
        stand = repo.hole_arbeitsstand(conn, CHAT)
        return stand["rahmen"] if stand else None
    finally:
        conn.close()


# -- Der Angriff: fremde Herkunft, gueltiger Nonce ------------------------


def test_fremder_origin_ist_403_trotz_gueltigem_nonce(aufbau):
    basis, token, pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}", _gueltig(token),
                          {"Origin": "https://boese.example"})
    assert status == 403
    assert _rahmen(pfad) == "Eine Nacht im Treppenhaus"


def test_sec_fetch_site_cross_site_ist_403(aufbau):
    basis, token, pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}", _gueltig(token),
                          {"Sec-Fetch-Site": "cross-site"})
    assert status == 403
    assert _rahmen(pfad) == "Eine Nacht im Treppenhaus"


def test_eigener_origin_geht_durch(aufbau):
    basis, token, pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}", _gueltig(token),
                          {"Origin": basis})
    assert status == 200
    assert _rahmen(pfad) == "Ein Hinterhof im Regen"


def test_ohne_origin_entscheidet_der_nonce_wie_bisher(aufbau):
    """curl und alte Browser schicken keinen Origin. Ein 403 darauf machte
    das Reviewer-Drehbuch (Aufgabe 9) unmoeglich."""
    basis, token, pfad = aufbau
    assert _post(f"{basis}/g/{token}", _gueltig(token))[0] == 200
    assert _rahmen(pfad) == "Ein Hinterhof im Regen"


def test_sec_fetch_site_same_origin_geht_durch(aufbau):
    basis, token, _pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}", _gueltig(token),
                          {"Sec-Fetch-Site": "same-origin"})
    assert status == 200


def test_post_ohne_nonce_bleibt_403(aufbau):
    basis, token, pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}",
                          {"feld": "rahmen", "wert": "Ein Hinterhof im Regen"})
    assert status == 403
    assert _rahmen(pfad) == "Eine Nacht im Treppenhaus"


def test_die_herkunft_wird_vor_dem_nonce_geprueft(aufbau):
    """E-S9: 'vor jeder Wirkung, auch wenn der Nonce stimmt'. Umgekehrt
    heisst das: ein fremder Origin OHNE Nonce gibt ebenfalls 403 -- und
    zwar mit dem Herkunftstext, nicht mit dem Veraltet-Text."""
    basis, token, _pfad = aufbau
    status, text = _post(f"{basis}/g/{token}",
                         {"feld": "rahmen", "wert": "x"},
                         {"Origin": "https://boese.example"})
    assert status == 403
    assert web.TEXT_FREMDE_HERKUNFT in text


def test_fremder_origin_ist_403_auch_auf_dem_chatweg(aufbau):
    """Die Herkunft wird vor der Verzweigung in ``web_chat`` geprueft --
    auch ``/chat/senden`` bekommt keinen fremden Browser durch."""
    basis, token, _pfad = aufbau
    status, text = _post(f"{basis}/g/{token}/chat/senden",
                         {"nonce": web.nonce(SCHLUESSEL, token), "text": "hallo"},
                         {"Origin": "https://boese.example"})
    assert status == 403
    assert web.TEXT_FREMDE_HERKUNFT in text


# -- Hinter nginx: interner Host, oeffentlicher Origin --------------------

#: So kommt eine Browser-Anfrage hinter nginx an, wenn ``proxy_set_header
#: Host`` nicht gesetzt ist: der Host ist der interne, der Origin der
#: oeffentliche, und ``X-Forwarded-Host`` traegt den oeffentlichen nach.
INTERN = "100.75.24.33:8010"
OEFFENTLICH = "lab.example.org"


def test_hinter_dem_proxy_zaehlt_x_forwarded_host(aufbau):
    basis, token, pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}", _gueltig(token), {
        "Host": INTERN,
        "X-Forwarded-Host": OEFFENTLICH,
        "Origin": f"https://{OEFFENTLICH}",
    })
    assert status == 200
    assert _rahmen(pfad) == "Ein Hinterhof im Regen"


def test_x_forwarded_host_nimmt_den_ersten_wert_und_ignoriert_gross_klein(aufbau):
    basis, token, _pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}", _gueltig(token), {
        "Host": INTERN,
        "X-Forwarded-Host": f" {OEFFENTLICH.upper()} , intern.example",
        "Origin": f"https://{OEFFENTLICH}",
    })
    assert status == 200


def test_hinter_dem_proxy_bleibt_ein_fremder_origin_403(aufbau):
    basis, token, pfad = aufbau
    status, _text = _post(f"{basis}/g/{token}", _gueltig(token), {
        "Host": INTERN,
        "X-Forwarded-Host": OEFFENTLICH,
        "Origin": "https://boese.example",
    })
    assert status == 403
    assert _rahmen(pfad) == "Eine Nacht im Treppenhaus"


# -- Der Nonce steht nicht mehr in der Logzeile ---------------------------


def test_maskiere_token_kuerzt_auf_vier_zeichen():
    assert web.maskiere_token("/g/abcdefgh1234/chat") == "/g/abcd.../chat"
    assert web.maskiere_token("/theatersoap/g/abcdefgh1234") == "/theatersoap/g/abcd..."
    assert web.maskiere_token("/gesund") == "/gesund"
    assert web.maskiere_token("/") == "/"


def test_maskiere_token_wirft_die_query_weg():
    """Beim Audio-Upload stand der Nonce in der Query (A2). Er steht
    kuenftig in einer Kopfzeile -- und selbst wenn ihn jemand wieder in die
    Query legt, landet er nicht im Log."""
    assert "nonce" not in web.maskiere_token("/g/abcdefgh1234/chat/audio?nonce=xy&dauer=45")


def test_die_logzeile_traegt_weder_token_noch_nonce(aufbau, capsys):
    basis, token, _pfad = aufbau
    _post(f"{basis}/g/{token}", _gueltig(token))
    ausgabe = capsys.readouterr().out
    assert token not in ausgabe
    assert web.nonce(SCHLUESSEL, token) not in ausgabe
    assert token[:4] in ausgabe
