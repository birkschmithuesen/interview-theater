"""Eine Ablehnung VOR dem Lesen des Koerpers darf die Verbindung nicht vergiften.

HTTP/1.1 haelt die Verbindung offen. Antwortet der Server, ohne den Koerper
gelesen zu haben, liegt der Koerper noch im Socket -- und wird als naechste
Anfragezeile gelesen. Ergebnis: die naechste, voellig ordentliche Anfrage auf
derselben Verbindung bekommt einen 400 aus Muell. Deshalb schliesst der
Server nach so einer Ablehnung die Verbindung (``Connection: close``).
"""

import http.client
import json
import threading

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
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield dienst.server_address[1], token
    dienst.shutdown()


def _danach_ordentlich(port: int, pfad: str, kopf: dict) -> None:
    """Abgelehnter POST mit Koerper, danach GET /gesund auf derselben
    Verbindung: entweder hat der Server sie geschlossen (dann eine neue),
    oder er beantwortet den GET richtig -- nie ein 400 aus den Koerperbytes."""
    verbindung = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    koerper = json.dumps({"feld": "rahmen", "wert": "x" * 200}).encode("utf-8")
    verbindung.request("POST", pfad, body=koerper,
                       headers={"Content-Type": "application/json", **kopf})
    erste = verbindung.getresponse()
    erste.read()
    assert erste.status >= 400
    if erste.will_close:
        verbindung.close()
        return
    verbindung.request("GET", "/gesund")
    zweite = verbindung.getresponse()
    zweite.read()
    verbindung.close()
    assert zweite.status == 200


def test_fremde_herkunft_vergiftet_die_verbindung_nicht(aufbau):
    port, token = aufbau
    _danach_ordentlich(port, f"/g/{token}", {"Origin": "https://boese.example"})


def test_chatweg_ohne_webgruppe_vergiftet_die_verbindung_nicht(aufbau):
    """Die Gruppe arbeitet nicht im Web-Kanal: 404 vor dem Lesen."""
    port, token = aufbau
    _danach_ordentlich(port, f"/g/{token}/chat/senden", {})


def test_unbekannter_chatweg_vergiftet_die_verbindung_nicht(aufbau):
    port, token = aufbau
    _danach_ordentlich(port, f"/g/{token}/chat/gibtsnicht", {})


def test_fremder_pfad_vergiftet_die_verbindung_nicht(aufbau):
    port, _token = aufbau
    _danach_ordentlich(port, "/irgendwo", {})


def test_zu_grosser_json_koerper_vergiftet_die_verbindung_nicht(aufbau):
    port, token = aufbau
    _danach_ordentlich(port, f"/g/{token}",
                       {"Content-Length": str(web.MAX_POST_BYTES + 1)})
