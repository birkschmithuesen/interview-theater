"""Server-Seite der Pegel-Kalibrierung (Task 2, Kanban-Karte Mithoeren
SICHER/Kalibrierung, 03.10.2026) -- der eine neue POST-Weg, der das
``herumreichen``-Flag gruppenweit merkt. Alles andere (Audio-Upload,
Chatverlauf-Filter, Lesezustand) steht in ``test_web_chat_audio.py`` und
``test_web_chat.py``.
"""

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
        f"{basis}/g/{token}/chat/kalibrierung",
        data=json.dumps({"nonce": web.nonce(SCHLUESSEL, token), **(koerper or {})}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=5) as antwort:
        return antwort.status, json.loads(antwort.read().decode("utf-8"))


def test_setzt_kalibrierung_modus_herumreichen(aufbau):
    basis, token, pfad = aufbau
    status, _antwort = _post(basis, token)
    assert status == 200

    conn = db.verbinde(pfad)
    gruppe = repo.hole_gruppe(conn, CHAT)
    assert gruppe["kalibrierung_modus"] == "herumreichen"


def test_wirkt_ohne_gueltigen_nonce_nicht(aufbau):
    basis, token, pfad = aufbau
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/kalibrierung",
        data=json.dumps({"nonce": "falsch"}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 403

    conn = db.verbinde(pfad)
    assert repo.hole_gruppe(conn, CHAT)["kalibrierung_modus"] is None


def test_zustand_zeigt_den_modus_danach(aufbau):
    basis, token, pfad = aufbau
    _post(basis, token)
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        assert web_daten.web_chatzustand(lesend, token)["kalibrierung_modus"] == "herumreichen"
    finally:
        lesend.close()
