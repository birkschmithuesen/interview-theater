"""Audio-Upload aus dem Browser -- roher Koerper, Allowlist, Groessengrenze.

Die Endung entscheidet ueber den MIME-Typ, den Whisper sieht (Falle 3):
ein WebM als .ogg abgelegt laesst den Auftrag dauerhaft auf 'pending' stehen,
89,7 s statt 2,0 s, im Betrieb nur als "haengt" sichtbar. Deshalb ist die
Allowlist Content-Type -> Endung und nicht Content-Type -> "erlaubt ja/nein".
"""

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from interview_theater import db, repo, stt, telegram, web, web_chat, web_kanal

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32
#: EBML-Kopf -- so faengt eine WebM-Datei aus MediaRecorder an.
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 200


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


def _lade(basis, token, koerper: bytes, typ="audio/webm", dauer=45, nonce=None):
    kennung = nonce if nonce is not None else web.nonce(SCHLUESSEL, token)
    url = f"{basis}/g/{token}/chat/audio?nonce={kennung}&dauer={dauer}"
    anfrage = urllib.request.Request(
        url, data=koerper, headers={"Content-Type": typ}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=10) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


# -- die Allowlist ---------------------------------------------------------


@pytest.mark.parametrize("typ,endung", [
    ("audio/webm", ".webm"),
    ("audio/webm;codecs=opus", ".webm"),
    ("audio/webm; codecs=\"opus\"", ".webm"),
    ("AUDIO/WEBM", ".webm"),
    ("audio/ogg", ".ogg"),
    ("audio/ogg;codecs=opus", ".ogg"),
    ("audio/mp4", ".m4a"),
    ("audio/mp4;codecs=mp4a.40.2", ".m4a"),
    ("audio/mpeg", ".mp3"),
])
def test_erlaubte_typen_geben_eine_endung(typ, endung):
    assert web_chat.endung_fuer(typ) == endung


@pytest.mark.parametrize("typ", [
    None, "", "text/html", "application/octet-stream", "video/mp4",
    "audio/x-wav", "audio/flac", "audio/webm/../../etc",
])
def test_alles_andere_gibt_none(typ):
    assert web_chat.endung_fuer(typ) is None


def test_jede_endung_der_allowlist_ist_stt_bekannt():
    """Die Allowlist waere nutzlos, wenn ``stt.mime_typ`` die Endung nicht
    kennt: dann raet ``mimetypes.guess_type``, und im schlechten Fall kommt
    ``application/octet-stream`` bei Whisper an."""
    for typ, endung in web_chat.MIME_ERLAUBT.items():
        gemessen = stt.mime_typ(Path(f"x{endung}"))
        assert gemessen == typ.split(";")[0], (endung, gemessen, typ)


# -- der Weg ueber HTTP ----------------------------------------------------


def test_ein_segment_landet_als_sprachnachricht(aufbau):
    basis, token, pfad, audio = aufbau
    status, text = _lade(basis, token, WEBM)
    assert status == 202
    message_id = json.loads(text)["message_id"]

    conn = db.verbinde(pfad)
    zeile = repo.hole_web_post(conn, message_id)
    assert zeile["typ"] == repo.WEB_TYP_SPRACHE
    assert zeile["dauer"] == 45
    assert zeile["mime"] == "audio/webm"

    datei = Path(zeile["datei"])
    assert datei.read_bytes() == WEBM
    assert datei.suffix == ".webm"
    assert web_kanal.EINGANG_VERZ in datei.parts
    assert str(CHAT) in datei.parts


def test_der_bot_sieht_daraus_eine_sprachnachricht_mit_endung(aufbau):
    basis, token, pfad, audio = aufbau
    _status, text = _lade(basis, token, WEBM)
    message_id = json.loads(text)["message_id"]

    conn = db.verbinde(pfad)
    kanal = web_kanal.WebKanal(conn, CHAT, str(audio), schritt_s=0.01)
    gedeutet = telegram.lies_nachricht(kanal.hole_updates(message_id, timeout=0)[0])
    assert gedeutet["typ"] == "sprache"
    assert gedeutet["endung"] == ".webm"
    assert gedeutet["dauer"] == 45
    # Und der Weg zurueck: lade_datei findet die Datei wieder.
    ziel = audio / str(CHAT) / f"{message_id}.webm"
    kanal.lade_datei(gedeutet["file_id"], ziel)
    assert ziel.read_bytes() == WEBM


def test_fremder_typ_gibt_415(aufbau):
    basis, token, pfad, _audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, b"<html>", typ="text/html")
    assert fehler.value.code == 415
    conn = db.verbinde(pfad)
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0


def test_zu_grosses_segment_gibt_413(aufbau):
    basis, token, pfad, audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, b"\x00" * (web_chat.MAX_AUDIO_BYTES + 1))
    assert fehler.value.code == 413
    conn = db.verbinde(pfad)
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0
    # Und keine halbe Datei bleibt liegen.
    assert list(audio.rglob("*.webm")) == []


def test_leerer_koerper_gibt_400(aufbau):
    basis, token, _pfad, _audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, b"")
    assert fehler.value.code == 400


def test_ohne_nonce_gibt_403_und_speichert_nichts(aufbau):
    basis, token, pfad, audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, WEBM, nonce="0.deadbeef")
    assert fehler.value.code == 403
    conn = db.verbinde(pfad)
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0
    assert list(audio.rglob("*")) == [] or not any(
        p.is_file() for p in audio.rglob("*")
    )


def test_unbekanntes_token_gibt_404(aufbau):
    basis, token, _pfad, _audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        anfrage = urllib.request.Request(
            f"{basis}/g/gibtsnicht/chat/audio?nonce={web.nonce(SCHLUESSEL, token)}&dauer=5",
            data=WEBM, headers={"Content-Type": "audio/webm"}, method="POST",
        )
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 404


@pytest.mark.parametrize("dauer", [
    "", "abc", "-3", "99999999",
    "%C2%B2",  # "²" (U+00B2) -- isdigit()==True, aber kein ASCII;
               # int("²") wirft sonst ein nicht abgefangenes ValueError.
    "9" * 50,  # sehr lange Ziffernfolge -- ohne Laengengrenze liefe eine
               # noch laengere Folge in Python 3.11s int()-Umwandlungsgrenze
               # (ValueError, ``sys.set_int_max_str_digits``).
])
def test_kaputte_dauer_gibt_400(aufbau, dauer):
    """Die Dauer kommt vom Client und geht in ``aufnahme`` -- sie entscheidet
    unter anderem ueber ``HINWEIS_AB_S`` (60 s: eine lange Sprachnachricht
    ohne Interviewmodus wird gefragt, nicht gedeutet). Eine geratene Dauer
    waere dort eine geratene Entscheidung."""
    basis, token, _pfad, _audio = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, WEBM, dauer=dauer)
    assert fehler.value.code == 400


# -- der Koerper wird in jedem ablehnenden Zweig verworfen -----------------


def test_ungueltiger_nonce_mit_grossem_koerper_gibt_403(aufbau):
    """Vor dem Fix wurde der angekuendigte Koerper nur im 413-Zweig
    verworfen -- 415, 403 und 400 antworteten, ohne ihn zu lesen, und
    ``urllib`` (``Connection: close``, Koerper in einem Zug geschrieben)
    sah dabei denselben Verbindungsabbruch wie frueher bei 413. Ein grosser
    Koerper mit ungueltigem Nonce muss trotzdem die 403-Antwort ankommen
    lassen, nicht einen ``Broken pipe``."""
    basis, token, pfad, audio = aufbau
    gross = b"\x00" * (web_chat.MAX_AUDIO_BYTES - 1)
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, gross, nonce="0.deadbeef")
    assert fehler.value.code == 403
    conn = db.verbinde(pfad)
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0
    assert list(audio.rglob("*.webm")) == []


def test_fremder_typ_mit_grossem_koerper_gibt_415(aufbau):
    """Dieselbe Falle wie oben, diesmal am Typ-Zweig."""
    basis, token, pfad, audio = aufbau
    gross = b"\x00" * (web_chat.MAX_AUDIO_BYTES - 1)
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, gross, typ="text/html")
    assert fehler.value.code == 415
    conn = db.verbinde(pfad)
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0
    assert list(audio.rglob("*.webm")) == []


def test_kaputte_dauer_mit_grossem_koerper_gibt_400(aufbau):
    """Dieselbe Falle wie oben, diesmal am Dauer-Zweig."""
    basis, token, pfad, audio = aufbau
    gross = b"\x00" * (web_chat.MAX_AUDIO_BYTES - 1)
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _lade(basis, token, gross, dauer="abc")
    assert fehler.value.code == 400
    conn = db.verbinde(pfad)
    assert conn.execute("SELECT COUNT(*) FROM web_post").fetchone()[0] == 0
    assert list(audio.rglob("*.webm")) == []


def test_zwei_segmente_bekommen_zwei_dateien(aufbau):
    basis, token, pfad, audio = aufbau
    erste = json.loads(_lade(basis, token, WEBM)[1])["message_id"]
    zweite = json.loads(_lade(basis, token, WEBM + b"zwei")[1])["message_id"]
    assert erste != zweite

    conn = db.verbinde(pfad)
    pfade = {
        Path(repo.hole_web_post(conn, mid)["datei"]) for mid in (erste, zweite)
    }
    assert len(pfade) == 2
    assert all(p.exists() for p in pfade)


def test_eine_sprachnachricht_steht_im_verlauf_ohne_dateipfad(aufbau):
    basis, token, _pfad, _audio = aufbau
    _lade(basis, token, WEBM)
    with urllib.request.urlopen(f"{basis}/g/{token}/chat/zustand?nach=0",
                                timeout=5) as antwort:
        zustand = json.loads(antwort.read().decode("utf-8"))
    assert zustand["nachrichten"][0]["typ"] == "sprache"
    assert zustand["nachrichten"][0]["dauer"] == 45
    assert "datei" not in zustand["nachrichten"][0]


def test_das_json_post_limit_gilt_fuer_audio_nicht(aufbau):
    """``web.MAX_POST_BYTES`` (64 KiB) deckelt den JSON-Rumpf der
    Gruppenseite. Ein Audiosegment ist ein Vielfaches davon und laeuft
    deshalb NICHT durch ``handler._koerper``."""
    basis, token, _pfad, _audio = aufbau
    gross = b"\x1a\x45\xdf\xa3" + b"\x00" * (200 * 1024)
    assert len(gross) > web.MAX_POST_BYTES
    assert _lade(basis, token, gross)[0] == 202


# -- Pausen-Schnitt (VAD) und Brainstorm-Flag (02.10.2026) ------------------


def _lade_mit_grund(basis, token, koerper: bytes, *, grund=None, brainstorm=False,
                     diskussion=False, dauer=45):
    kennung = web.nonce(SCHLUESSEL, token)
    url = f"{basis}/g/{token}/chat/audio?nonce={kennung}&dauer={dauer}"
    if grund is not None:
        url += f"&grund={grund}"
    if brainstorm:
        url += "&brainstorm=1"
    if diskussion:
        url += "&diskussion=1"
    anfrage = urllib.request.Request(
        url, data=koerper, headers={"Content-Type": "audio/webm"}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=10) as antwort:
        return json.loads(antwort.read().decode("utf-8"))["message_id"]


def test_grund_und_brainstorm_landen_im_web_post(aufbau):
    basis, token, pfad, _audio = aufbau
    message_id = _lade_mit_grund(basis, token, WEBM, grund="pause", brainstorm=True)
    zeile = repo.hole_web_post(db.verbinde(pfad), message_id)
    assert zeile["schnittgrund"] == "pause"
    assert zeile["brainstorm"] == 1


def test_ohne_grund_und_brainstorm_bleiben_sie_leer(aufbau):
    basis, token, pfad, _audio = aufbau
    message_id = _lade_mit_grund(basis, token, WEBM)
    zeile = repo.hole_web_post(db.verbinde(pfad), message_id)
    assert zeile["schnittgrund"] is None
    assert zeile["brainstorm"] == 0


# -- Diskussion-Flag (Task 5, Padua Phase 1+2 Umbau, 03.10.2026) -----------


def test_diskussion_landet_im_web_post(aufbau):
    basis, token, pfad, _audio = aufbau
    message_id = _lade_mit_grund(basis, token, WEBM, diskussion=True)
    zeile = repo.hole_web_post(db.verbinde(pfad), message_id)
    assert zeile["diskussion"] == 1


def test_ohne_diskussion_bleibt_sie_leer(aufbau):
    basis, token, pfad, _audio = aufbau
    message_id = _lade_mit_grund(basis, token, WEBM)
    zeile = repo.hole_web_post(db.verbinde(pfad), message_id)
    assert zeile["diskussion"] == 0


def test_ein_unbekannter_grund_wird_zu_leer_statt_abgelehnt(aufbau):
    basis, token, pfad, _audio = aufbau
    message_id = _lade_mit_grund(basis, token, WEBM, grund="irgendwas")
    zeile = repo.hole_web_post(db.verbinde(pfad), message_id)
    assert zeile["schnittgrund"] is None
