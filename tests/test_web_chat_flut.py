"""Angriff: 50 Nachrichten in 10 Sekunden.

Ohne Rate-Limit landen alle 50 in web_post, und der Bot arbeitet 50
bezahlte Modellaufrufe ab. Verlangt: hoechstens 20 mal 202, der Rest 429 --
und genau 20 Zeilen in der Eingangstabelle. Die zweite Zahl ist die
wichtigere: ein 429, nach dem die Zeile trotzdem steht, waere kein Schutz,
sondern eine Luege.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_chat, web_grenze

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 200


@pytest.fixture(autouse=True)
def leer():
    web_grenze.vergiss()
    yield
    web_grenze.vergiss()


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    monkeypatch.setenv("IT_AUDIO", str(tmp_path / "audio"))
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, pfad
    dienst.shutdown()


def _senden(basis, token, text):
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/senden",
        data=json.dumps({"nonce": web.nonce(SCHLUESSEL, token), "text": text}).encode(),
        method="POST", headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            return antwort.status, dict(antwort.headers)
    except urllib.error.HTTPError as fehler:
        kopf = dict(fehler.headers)
        fehler.read()
        return fehler.code, kopf


def _laden(basis, token):
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/audio?dauer=45", data=WEBM, method="POST",
        headers={"Content-Type": "audio/webm", web.NONCE_KOPFZEILE: web.nonce(SCHLUESSEL, token)},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            return antwort.status
    except urllib.error.HTTPError as fehler:
        fehler.read()
        return fehler.code


def _eingang(pfad):
    conn = db.verbinde(pfad)
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM web_post WHERE chat_id = ? AND richtung = ?",
            (CHAT, repo.RICHTUNG_EIN),
        ).fetchone()["n"]
    finally:
        conn.close()


def test_fuenfzig_nachrichten_in_zehn_sekunden(aufbau):
    basis, token, pfad = aufbau
    ergebnisse = [_senden(basis, token, f"Nachricht {i}")[0] for i in range(50)]
    assert ergebnisse.count(202) == web_grenze.NACHRICHTEN_JE_MINUTE
    assert ergebnisse.count(429) == 50 - web_grenze.NACHRICHTEN_JE_MINUTE
    assert _eingang(pfad) == web_grenze.NACHRICHTEN_JE_MINUTE


def test_die_ersten_zwanzig_gehen_durch_die_einundzwanzigste_nicht(aufbau):
    basis, token, _pfad = aufbau
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        assert _senden(basis, token, f"x{i}")[0] == 202, i
    assert _senden(basis, token, "einundzwanzig")[0] == 429


def test_die_absage_traegt_retry_after(aufbau):
    basis, token, _pfad = aufbau
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        _senden(basis, token, f"x{i}")
    status, kopf = _senden(basis, token, "zuviel")
    assert status == 429
    assert kopf.get("Retry-After", "").isdigit()
    assert 0 < int(kopf["Retry-After"]) <= web_grenze.NACHRICHTEN_FENSTER_S


def test_knoepfe_zaehlen_in_denselben_topf(aufbau):
    """Sonst liesse sich abwechseln und die Rate verdoppeln."""
    basis, token, _pfad = aufbau
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        _senden(basis, token, f"x{i}")
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/knopf",
        data=json.dumps({"nonce": web.nonce(SCHLUESSEL, token),
                         "message_id": 1, "data": "k:1"}).encode(),
        method="POST", headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=10)
    assert fehler.value.code == 429


def test_uploads_haben_einen_eigenen_topf(aufbau):
    basis, token, _pfad = aufbau
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        _senden(basis, token, f"x{i}")
    assert _laden(basis, token) == 202


def test_ueber_der_uploadgrenze_kommt_429_und_nichts_auf_die_platte(aufbau, tmp_path):
    basis, token, pfad = aufbau
    for _ in range(web_grenze.UPLOADS_JE_STUNDE):
        assert _laden(basis, token) == 202
    assert _laden(basis, token) == 429
    dateien = list((tmp_path / "audio").rglob("*.webm"))
    assert len(dateien) == web_grenze.UPLOADS_JE_STUNDE


def test_eine_zweite_gruppe_ist_nicht_betroffen(aufbau):
    basis, token, pfad = aufbau
    conn = db.verbinde(pfad)
    repo.sichere_gruppe(conn, CHAT + 1, "gruppe2", "Die Zweiten")
    repo.setze_gruppe_kanal(conn, CHAT + 1, "web")
    zweites = repo.stelle_web_token_sicher(conn, CHAT + 1)
    conn.commit()
    conn.close()
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        _senden(basis, token, f"x{i}")
    assert _senden(basis, token, "zuviel")[0] == 429
    assert _senden(basis, zweites, "wir sind neu")[0] == 202


def test_lesen_wird_nicht_begrenzt(aufbau):
    """Das Limit haengt am POST. Ein GET auf die Chatansicht kostet nur eine
    read-only Abfrage -- und der Poll laeuft alle zwei Sekunden."""
    basis, token, _pfad = aufbau
    for _ in range(60):
        with urllib.request.urlopen(f"{basis}/g/{token}/chat/zustand?nach=0", timeout=10) as a:
            assert a.status == 200


def test_ein_vorfall_je_fenster_und_nicht_je_anfrage(aufbau):
    basis, token, pfad = aufbau
    for i in range(50):
        _senden(basis, token, f"x{i}")
    conn = db.verbinde(pfad)
    try:
        anzahl = conn.execute(
            "SELECT COUNT(*) AS n FROM vorfall WHERE chat_id = ? AND art = ?",
            (CHAT, "web_rate_limit"),
        ).fetchone()["n"]
    finally:
        conn.close()
    assert anzahl == 1
