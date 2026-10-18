"""Server-Seite der Watchdog-Meldung (Karte InScribe: Diskussionsaufnahme
laedt still nicht mehr hoch, 2026-10-17) -- der eine neue POST-Weg, ueber
den der Chat-Client meldet, wie viele Audiosegmente er gerade im Handy
(IndexedDB) gepuffert haelt, weil ein Upload haengt. Derselbe Aufbau wie
``test_web_chat_kalibrierung.py``."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_daten

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    repo.setze_phase(conn, CHAT, 4)
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad
    dienst.shutdown()


def _post(basis, token, koerper=None):
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/puffer",
        data=json.dumps({"nonce": web.nonce(SCHLUESSEL, token), **(koerper or {})}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=5) as antwort:
        return antwort.status, json.loads(antwort.read().decode("utf-8"))


def test_meldet_die_anzahl_gruppenweit(aufbau):
    basis, token, pfad = aufbau
    status, antwort = _post(basis, token, {"anzahl": 3, "haengt": True})
    assert status == 200
    assert antwort == {"ok": True}

    conn = db.verbinde(pfad)
    gruppe = repo.hole_gruppe(conn, CHAT)
    assert gruppe["client_puffer_segmente"] == 3
    assert gruppe["client_puffer_seit"] is not None


def test_null_loescht_die_meldung_wieder(aufbau):
    basis, token, pfad = aufbau
    _post(basis, token, {"anzahl": 2, "haengt": True})
    _post(basis, token, {"anzahl": 0})
    conn = db.verbinde(pfad)
    gruppe = repo.hole_gruppe(conn, CHAT)
    assert gruppe["client_puffer_segmente"] == 0
    assert gruppe["client_puffer_seit"] is None


def test_erstes_haengen_traegt_einen_vorfall_ein(aufbau):
    basis, token, pfad = aufbau
    _post(basis, token, {"anzahl": 4, "haengt": True})
    conn = db.verbinde(pfad)
    vorfall = conn.execute(
        "SELECT art, chat_id FROM vorfall WHERE chat_id = ?", (CHAT,)
    ).fetchone()
    assert vorfall is not None
    assert vorfall["art"] == "web_upload_haengt"


def test_ohne_haengt_flag_wird_kein_vorfall_eingetragen(aufbau):
    basis, token, pfad = aufbau
    _post(basis, token, {"anzahl": 1})
    conn = db.verbinde(pfad)
    anzahl = conn.execute(
        "SELECT COUNT(*) AS n FROM vorfall WHERE chat_id = ?", (CHAT,)
    ).fetchone()["n"]
    assert anzahl == 0


def test_wirkt_ohne_gueltigen_nonce_nicht(aufbau):
    basis, token, pfad = aufbau
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/puffer",
        data=json.dumps({"nonce": "falsch", "anzahl": 7}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 403
    conn = db.verbinde(pfad)
    assert repo.hole_gruppe(conn, CHAT)["client_puffer_segmente"] is None


def test_zustand_poll_zeigt_den_cothinker_status_mit_puffer(aufbau):
    basis, token, pfad = aufbau
    _post(basis, token, {"anzahl": 2, "haengt": True})
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        daten = web_daten.gruppe_nach_token(lesend, token)
    finally:
        lesend.close()
    assert daten["cothinker_status"] == {"puffer": 2}
