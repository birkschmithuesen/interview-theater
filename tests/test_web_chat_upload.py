"""Angriff auf den Upload: zu gross, falscher Typ, gelogene Laenge.

Der gefaehrlichste der drei ist der falsche Typ, und zwar nicht wegen HTTP:
die Endung entscheidet ueber den MIME-Typ, den Whisper sieht (AGENTS.md,
Falle 3). Ein WebM als .ogg abgelegt laesst den Auftrag dauerhaft auf
'pending' stehen -- 89,7 s statt 2,0 s, im Betrieb nur als "haengt"
sichtbar, und bezahlt. A2 liest dafuer den Content-Type-HEADER, also das,
was der Absender behauptet.

Jeder Test prueft zwei Dinge: den Statuscode UND dass nichts auf der Platte
und nichts in der Datenbank steht. Ein 413, nach dem die Datei trotzdem
liegt, waere kein Schutz.
"""

import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, stt, web, web_chat, web_grenze

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32

#: Echte Dateianfaenge. WEBM ist ein EBML-Kopf (MediaRecorder in
#: Chrome/Firefox), MP4 hat 'ftyp' ab Byte 4 (Safari), OGG faengt mit 'OggS'
#: an (Telegram-Sprachnachricht), WAV mit RIFF/WAVE, MP3 mit ID3 oder einem
#: Frame-Sync.
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 200
OGG = b"OggS" + b"\x00" * 200
MP4 = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 200
WAV = b"RIFF\x24\x08\x00\x00WAVEfmt " + b"\x00" * 200
MP3_ID3 = b"ID3\x03\x00\x00\x00" + b"\x00" * 200
MP3_SYNC = b"\xff\xfb\x90\x00" + b"\x00" * 200


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
    yield basis, token, pfad, tmp_path / "audio"
    dienst.shutdown()


def _lade(basis, token, koerper, typ="audio/webm", dauer=45, laenge=None):
    kopf = {"Content-Type": typ, web.NONCE_KOPFZEILE: web.nonce(SCHLUESSEL, token)}
    if laenge is not None:
        kopf["Content-Length"] = str(laenge)
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/audio?dauer={dauer}", data=koerper,
        method="POST", headers=kopf,
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=15) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _zeilen(pfad):
    conn = db.verbinde(pfad)
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM web_post WHERE chat_id = ?", (CHAT,)
        ).fetchone()["n"]
    finally:
        conn.close()


# -- Die Erkennung an den Magic Bytes -------------------------------------


@pytest.mark.parametrize("kopf,endung", [
    (WEBM, ".webm"), (OGG, ".ogg"), (MP4, ".m4a"),
    (WAV, ".wav"), (MP3_ID3, ".mp3"), (MP3_SYNC, ".mp3"),
])
def test_echte_dateianfaenge_werden_erkannt(kopf, endung):
    assert web_chat.endung_aus_bytes(kopf) == endung


@pytest.mark.parametrize("kopf", [
    b"", b"\x00" * 64, b"<!doctype html><html>", b"%PDF-1.4",
    b"\x89PNG\r\n\x1a\n", b"PK\x03\x04", b"\x7fELF", b"#!/bin/sh\n",
    b"\x1a\x45\xdf",                      # EBML, aber ein Byte zu kurz
])
def test_alles_andere_gibt_none(kopf):
    assert web_chat.endung_aus_bytes(kopf) is None


def test_jede_erkannte_endung_ist_stt_bekannt():
    """Sonst raet ``mimetypes.guess_type``, und im schlechten Fall kommt
    ``application/octet-stream`` bei Whisper an (Falle 3)."""
    from pathlib import Path

    for kopf in (WEBM, OGG, MP4, WAV, MP3_ID3, MP3_SYNC):
        endung = web_chat.endung_aus_bytes(kopf)
        assert stt.mime_typ(Path(f"x{endung}")) != "application/octet-stream", endung


# -- Der Angriff: falscher Typ --------------------------------------------


def test_html_als_audio_deklariert_ist_415(aufbau):
    basis, token, pfad, verzeichnis = aufbau
    status, _text = _lade(basis, token, b"<!doctype html>" + b"x" * 500,
                          typ="audio/webm")
    assert status == 415
    assert _zeilen(pfad) == 0
    assert not list(verzeichnis.rglob("*")) or not any(
        p.is_file() for p in verzeichnis.rglob("*")
    )


def test_webm_als_ogg_deklariert_bekommt_die_webm_endung(aufbau):
    """Der Kern von Falle 3: nicht 415, sondern die RICHTIGE Endung. Der
    Absender hat sich geirrt (oder gelogen), die Datei ist in Ordnung -- und
    Whisper bekommt, was wirklich drinsteht."""
    basis, token, pfad, verzeichnis = aufbau
    status, _text = _lade(basis, token, WEBM, typ="audio/ogg")
    assert status == 202
    dateien = [p.name for p in verzeichnis.rglob("*") if p.is_file()]
    assert len(dateien) == 1 and dateien[0].endswith(".webm")


def test_unbekannter_content_type_wird_ohne_lesen_abgewiesen(aufbau):
    basis, token, pfad, _verzeichnis = aufbau
    for typ in ("text/html", "application/octet-stream", "video/mp4", ""):
        status, _text = _lade(basis, token, WEBM, typ=typ)
        assert status == 415, typ
    assert _zeilen(pfad) == 0


# -- Der Angriff: zu gross ------------------------------------------------


def test_upload_ueber_der_grenze_ist_413_und_nichts_bleibt(aufbau):
    basis, token, pfad, verzeichnis = aufbau
    zuviel = WEBM + b"\x00" * (web_chat.MAX_AUDIO_BYTES + 1 - len(WEBM))
    status, _text = _lade(basis, token, zuviel)
    assert status == 413
    assert _zeilen(pfad) == 0
    assert not any(p.is_file() for p in verzeichnis.rglob("*"))


def test_genau_auf_der_grenze_geht_noch(aufbau):
    basis, token, pfad, _verzeichnis = aufbau
    genau = WEBM + b"\x00" * (web_chat.MAX_AUDIO_BYTES - len(WEBM))
    assert _lade(basis, token, genau)[0] == 202
    assert _zeilen(pfad) == 1


def test_gelogene_content_length_legt_nichts_an(aufbau):
    """Content-Length sagt 'klein', der Koerper ist gross. Gelesen wird
    genau Content-Length Bytes und nie mehr -- der Rest bleibt im Socket und
    die Verbindung wird geschlossen."""
    basis, token, pfad, verzeichnis = aufbau
    status, _text = _lade(basis, token, WEBM + b"\x00" * 5000, laenge=len(WEBM))
    # Entweder 202 mit genau len(WEBM) Bytes auf der Platte, oder 400 --
    # was nicht passieren darf, ist eine Datei mit 5000 Bytes mehr.
    assert status in (202, 400)
    for datei in verzeichnis.rglob("*"):
        if datei.is_file():
            assert datei.stat().st_size == len(WEBM)


def test_leerer_koerper_ist_400(aufbau):
    basis, token, pfad, _verzeichnis = aufbau
    assert _lade(basis, token, b"")[0] == 400
    assert _zeilen(pfad) == 0


# -- Der Angriff: Unsinnsdauer --------------------------------------------


@pytest.mark.parametrize("dauer", ["0", "-5", "abc", "", "99999999"])
def test_unsinnige_dauer_ist_400(aufbau, dauer):
    basis, token, pfad, _verzeichnis = aufbau
    assert _lade(basis, token, WEBM, dauer=dauer)[0] == 400
    assert _zeilen(pfad) == 0


def test_die_dauergrenze_kommt_aus_der_konstante(aufbau):
    basis, token, _pfad, _verzeichnis = aufbau
    assert _lade(basis, token, WEBM, dauer=web_chat.MAX_DAUER_S)[0] == 202
    assert _lade(basis, token, WEBM, dauer=web_chat.MAX_DAUER_S + 1)[0] == 400


def test_die_groessengrenze_liegt_unter_der_whisper_grenze():
    """Eine Datei, die Whisper ohnehin ablehnt, soll gar nicht erst
    ankommen."""
    assert web_chat.MAX_AUDIO_BYTES < stt.MAX_UPLOAD_BYTES
