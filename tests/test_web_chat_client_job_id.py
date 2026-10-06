"""Serverseitiger Duplikatschutz fuer die IndexedDB-Warteschlange des Browsers
(Karte t_e2b0e489, kein Aufnahmeverlust am Handy).

Der Browser schickt mit jedem Segment eine selbst vergebene Client-Job-Id
(``?job=...`` an ``chat/audio``). Laedt er dasselbe Segment nach einem
Neuladen ein zweites Mal hoch (die IndexedDB-Warteschlange kennt den Erfolg
des ersten Versuchs nicht sicher), soll das keine zweite Zeile und keine
zweite Datei anlegen -- der zweite Upload bekommt dieselbe ``message_id``
zurueck wie der erste.
"""

import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_chat, web_daten, web_grenze

CHAT = 7_000_000_000_001
ANDERER_CHAT = 7_000_000_000_002
SCHLUESSEL = b"x" * 32

WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 200


@pytest.fixture(autouse=True)
def leer():
    web_grenze.vergiss()
    yield
    web_grenze.vergiss()


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    repo.sichere_gruppe(conn, ANDERER_CHAT, "gruppe2", "Die Anderen")
    repo.setze_gruppe_kanal(conn, ANDERER_CHAT, "web")
    token2 = repo.stelle_web_token_sicher(conn, ANDERER_CHAT)
    conn.commit()
    conn.close()
    monkeypatch.setenv("IT_AUDIO", str(tmp_path / "audio"))
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, token, token2, pfad, tmp_path / "audio"
    dienst.shutdown()


def _lade(basis, token, koerper, *, job=None, dauer=45):
    weg_ = f"/g/{token}/chat/audio?dauer={dauer}"
    if job is not None:
        weg_ += f"&job={job}"
    kopf = {"Content-Type": "audio/webm", web.NONCE_KOPFZEILE: web.nonce(SCHLUESSEL, token)}
    anfrage = urllib.request.Request(f"{basis}{weg_}", data=koerper, method="POST", headers=kopf)
    try:
        with urllib.request.urlopen(anfrage, timeout=15) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _zeilen(pfad, chat_id):
    c = db.verbinde(pfad)
    try:
        return c.execute(
            "SELECT COUNT(*) AS n FROM web_post WHERE chat_id = ? AND typ = 'sprache'",
            (chat_id,),
        ).fetchone()["n"]
    finally:
        c.close()


# -- repo --------------------------------------------------------------------


def test_lege_web_post_an_speichert_die_client_job_id(conn):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE, client_job_id="job-abc",
    )
    zeile = conn.execute(
        "SELECT client_job_id FROM web_post WHERE id = ?", (post_id,),
    ).fetchone()
    assert zeile["client_job_id"] == "job-abc"


def test_lege_web_post_an_ohne_client_job_id_ist_null(conn):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
    )
    zeile = conn.execute(
        "SELECT client_job_id FROM web_post WHERE id = ?", (post_id,),
    ).fetchone()
    assert zeile["client_job_id"] is None


# -- web_daten: der Nachschlag vor dem Schreiben -----------------------------


def test_web_post_id_fuer_client_job_findet_eine_vorhandene_zeile(conn):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE, client_job_id="job-abc",
    )
    conn.commit()
    assert web_daten.web_post_id_fuer_client_job(conn, CHAT, "job-abc") == post_id


def test_web_post_id_fuer_client_job_ist_none_ohne_treffer(conn):
    conn.commit()
    assert web_daten.web_post_id_fuer_client_job(conn, CHAT, "job-unbekannt") is None


def test_web_post_id_fuer_client_job_ist_je_chat_getrennt(conn):
    repo.sichere_gruppe(conn, ANDERER_CHAT, "gruppe2", "Die Anderen")
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE, client_job_id="job-abc",
    )
    conn.commit()
    assert web_daten.web_post_id_fuer_client_job(conn, ANDERER_CHAT, "job-abc") is None
    assert web_daten.web_post_id_fuer_client_job(conn, CHAT, "job-abc") == post_id


# -- Der volle Weg ueber HTTP --------------------------------------------------


def test_zweiter_upload_derselben_job_id_bekommt_dieselbe_message_id(aufbau):
    basis, token, _token2, pfad, _audio = aufbau
    status1, antwort1 = _lade(basis, token, WEBM, job="job-1")
    status2, antwort2 = _lade(basis, token, WEBM, job="job-1")
    assert status1 == 202 and status2 == 202
    assert antwort1 == antwort2, "zweiter Versuch muss dieselbe message_id liefern"
    assert _zeilen(pfad, CHAT) == 1, "nur EINE Zeile fuer dieselbe Client-Job-Id"


def test_zweiter_upload_ohne_job_id_legt_zwei_zeilen_an(aufbau):
    basis, token, _token2, pfad, _audio = aufbau
    _lade(basis, token, WEBM)
    _lade(basis, token, WEBM)
    assert _zeilen(pfad, CHAT) == 2, "ohne Job-Id gibt es keinen Dublettencheck (alte Clients)"


def test_zu_lange_job_id_wird_wie_keine_kennung_behandelt(aufbau):
    """Laenge > 128: wie der Fall ohne Job-Id behandelt (kein Dublettencheck),
    nicht etwa ein Fehler -- eine zu lange Kennung ist kein Sicherheitsproblem,
    nur ein Client, dem der Server nicht vertraut."""
    basis, token, _token2, pfad, _audio = aufbau
    zu_lang = "j" * 129
    status1, _ = _lade(basis, token, WEBM, job=zu_lang)
    status2, _ = _lade(basis, token, WEBM, job=zu_lang)
    assert status1 == 202 and status2 == 202
    assert _zeilen(pfad, CHAT) == 2, "zu lange Job-Id darf nicht dedupliziert werden"


def test_nicht_ascii_job_id_wird_wie_keine_kennung_behandelt(aufbau):
    basis, token, _token2, pfad, _audio = aufbau
    nicht_ascii = "j%C3%B6b-1"  # "jöb-1" URL-kodiert
    status1, _ = _lade(basis, token, WEBM, job=nicht_ascii)
    status2, _ = _lade(basis, token, WEBM, job=nicht_ascii)
    assert status1 == 202 and status2 == 202
    assert _zeilen(pfad, CHAT) == 2, "nicht-ASCII Job-Id darf nicht dedupliziert werden"


def test_verschiedene_job_ids_legen_zwei_zeilen_an(aufbau):
    basis, token, _token2, pfad, _audio = aufbau
    _lade(basis, token, WEBM, job="job-1")
    _lade(basis, token, WEBM, job="job-2")
    assert _zeilen(pfad, CHAT) == 2


def test_dieselbe_job_id_in_verschiedenen_gruppen_kollidiert_nicht(aufbau):
    basis, token, token2, pfad, _audio = aufbau
    status1, _ = _lade(basis, token, WEBM, job="job-1")
    status2, _ = _lade(basis, token2, WEBM, job="job-1")
    assert status1 == 202 and status2 == 202
    assert _zeilen(pfad, CHAT) == 1
    assert _zeilen(pfad, ANDERER_CHAT) == 1


def test_zweiter_upload_schreibt_keine_zweite_datei(aufbau):
    basis, token, _token2, pfad, audio = aufbau
    _lade(basis, token, WEBM, job="job-1")
    _lade(basis, token, WEBM, job="job-1")
    dateien = list(audio.rglob("*")) if audio.exists() else []
    dateien = [d for d in dateien if d.is_file()]
    assert len(dateien) == 1, f"erwartet genau eine Datei, gefunden: {dateien}"
