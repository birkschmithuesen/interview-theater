"""Angriff: der alte Link nach einer Rotation.

Ein Gruppenlink hat kein Login; das Token IST das Geheimnis. Es wandert in
der Probe von Hand zu Hand, landet in einem Screenshot, auf einem Foto von
der Leinwand. Bis hier gab es keinen Weg, es zu wechseln.

Geprueft wird die ganze Kette: altes Token -> 404 (GET und POST), neues
Token -> 200, und der Nonce des alten Tokens gilt am neuen nicht.
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
    alt = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    yield basis, alt, pfad
    dienst.shutdown()


def _hole(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as antwort:
            return antwort.status
    except urllib.error.HTTPError as fehler:
        fehler.read()
        return fehler.code


def _post(url, koerper):
    anfrage = urllib.request.Request(
        url, data=json.dumps(koerper).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            antwort.read()
            return antwort.status
    except urllib.error.HTTPError as fehler:
        fehler.read()
        return fehler.code


def _rotiere(pfad):
    conn = db.verbinde(pfad)
    try:
        return repo.erneuere_web_token(conn, CHAT)
    finally:
        conn.close()


# -- Die Funktion ---------------------------------------------------------


def test_erneuern_gibt_ein_neues_token(aufbau):
    _basis, alt, pfad = aufbau
    neu = _rotiere(pfad)
    assert neu and neu != alt
    assert len(neu) >= 32


def test_erneuern_ist_nicht_idempotent(aufbau):
    """Zweimal rotieren gibt zwei verschiedene Token -- anders als
    ``stelle_web_token_sicher``, das ein vorhandenes stehen laesst."""
    _basis, _alt, pfad = aufbau
    assert _rotiere(pfad) != _rotiere(pfad)


def test_erneuern_einer_unbekannten_gruppe_gibt_none(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    assert repo.erneuere_web_token(conn, 999) is None
    conn.close()


def test_andere_gruppen_bleiben_unberuehrt(aufbau):
    _basis, _alt, pfad = aufbau
    conn = db.verbinde(pfad)
    repo.sichere_gruppe(conn, 2, "gruppe2", "Die Zweiten")
    fremdes = repo.stelle_web_token_sicher(conn, 2)
    conn.commit()
    conn.close()
    _rotiere(pfad)
    conn = db.verbinde(pfad)
    try:
        assert repo.stelle_web_token_sicher(conn, 2) == fremdes
    finally:
        conn.close()


# -- Der Angriff: der alte Link -------------------------------------------


def test_der_alte_link_ist_sofort_404(aufbau):
    basis, alt, pfad = aufbau
    assert _hole(f"{basis}/g/{alt}") == 200
    neu = _rotiere(pfad)
    assert _hole(f"{basis}/g/{alt}") == 404
    assert _hole(f"{basis}/g/{neu}") == 200


def test_alle_unterseiten_des_alten_links_sind_404(aufbau):
    basis, alt, pfad = aufbau
    _rotiere(pfad)
    for weg in ("", "/textbuch", "/leitfaden", "/textbuch.md", "/textbuch.txt"):
        assert _hole(f"{basis}/g/{alt}{weg}") == 404, weg


def test_post_auf_den_alten_link_ist_404(aufbau):
    basis, alt, pfad = aufbau
    nonce_alt = web.nonce(SCHLUESSEL, alt)
    _rotiere(pfad)
    status = _post(f"{basis}/g/{alt}",
                   {"nonce": nonce_alt, "feld": "rahmen", "wert": "Ein Hinterhof"})
    assert status == 404
    conn = db.verbinde(pfad)
    try:
        assert repo.hole_arbeitsstand(conn, CHAT)["rahmen"] == "Eine Nacht im Treppenhaus"
    finally:
        conn.close()


def test_der_alte_nonce_gilt_am_neuen_token_nicht(aufbau):
    """Der Nonce ist an den Token-String gebunden (web.nonce). Diese
    Eigenschaft traegt die Rotation -- und verschwindet beim naechsten Umbau
    lautlos, wenn sie kein Test festhaelt."""
    basis, alt, pfad = aufbau
    nonce_alt = web.nonce(SCHLUESSEL, alt)
    neu = _rotiere(pfad)
    status = _post(f"{basis}/g/{neu}",
                   {"nonce": nonce_alt, "feld": "rahmen", "wert": "Ein Hinterhof"})
    assert status == 403
    conn = db.verbinde(pfad)
    try:
        assert repo.hole_arbeitsstand(conn, CHAT)["rahmen"] == "Eine Nacht im Treppenhaus"
    finally:
        conn.close()


def test_mit_dem_neuen_nonce_geht_es_wieder(aufbau):
    basis, _alt, pfad = aufbau
    neu = _rotiere(pfad)
    status = _post(f"{basis}/g/{neu}",
                   {"nonce": web.nonce(SCHLUESSEL, neu),
                    "feld": "rahmen", "wert": "Ein Hinterhof"})
    assert status == 200


def test_der_webserver_haelt_kein_token_im_speicher(aufbau):
    """Kein Neustart der Unit noetig: jede Anfrage oeffnet ihre eigene
    read-only Verbindung (web.py:2652, web_daten.py:1044). Der Test faehrt
    die Rotation gegen einen LAUFENDEN Server."""
    basis, alt, pfad = aufbau
    assert _hole(f"{basis}/g/{alt}") == 200
    neu = _rotiere(pfad)
    assert _hole(f"{basis}/g/{alt}") == 404
    assert _hole(f"{basis}/g/{neu}") == 200


# -- Das Skript -----------------------------------------------------------


def test_das_skript_ist_ohne_ja_ein_trockenlauf(aufbau, monkeypatch, capsys):
    from scripts import web_token_neu

    basis, alt, pfad = aufbau
    monkeypatch.setenv("IT_DB", pfad)
    monkeypatch.setenv("IT_WEB_URL", "https://beispiel.invalid/theatersoap")
    web_token_neu.main([str(CHAT)])
    ausgabe = capsys.readouterr().out
    assert "Trockenlauf" in ausgabe
    assert _hole(f"{basis}/g/{alt}") == 200


def test_das_skript_gibt_kein_altes_token_aus(aufbau, monkeypatch, capsys):
    """Das alte Token ist nach der Rotation wertlos, aber es steht in
    Screenshots von frueher -- es gehoert nicht noch einmal in eine
    Terminalausgabe, die jemand weiterschickt."""
    from scripts import web_token_neu

    _basis, alt, pfad = aufbau
    monkeypatch.setenv("IT_DB", pfad)
    web_token_neu.main([str(CHAT), "--ja"])
    ausgabe = capsys.readouterr().out
    assert alt not in ausgabe


def test_das_skript_rotiert_und_legt_ein_backup_an(aufbau, monkeypatch, capsys, tmp_path):
    from scripts import web_token_neu

    basis, alt, pfad = aufbau
    monkeypatch.setenv("IT_DB", pfad)
    monkeypatch.setenv("IT_WEB_URL", "https://beispiel.invalid/theatersoap")
    web_token_neu.main([str(CHAT), "--ja"])
    ausgabe = capsys.readouterr().out
    assert "https://beispiel.invalid/theatersoap/g/" in ausgabe
    assert _hole(f"{basis}/g/{alt}") == 404
    assert list(tmp_path.glob("t.db.bak-*"))


def test_das_skript_schreibt_einen_journaleintrag_ohne_token(aufbau, monkeypatch, capsys):
    from scripts import web_token_neu

    _basis, _alt, pfad = aufbau
    monkeypatch.setenv("IT_DB", pfad)
    web_token_neu.main([str(CHAT), "--ja"])
    capsys.readouterr()
    conn = db.verbinde(pfad)
    try:
        neu = repo.stelle_web_token_sicher(conn, CHAT)
        eintraege = [z["text"] for z in repo.journal(conn, CHAT)]
    finally:
        conn.close()
    assert any("Zugangslink" in t for t in eintraege)
    assert not any(neu in t for t in eintraege)


def test_das_skript_verweigert_eine_unbekannte_gruppe(aufbau, monkeypatch, capsys):
    from scripts import web_token_neu

    _basis, _alt, pfad = aufbau
    monkeypatch.setenv("IT_DB", pfad)
    with pytest.raises(SystemExit) as beendet:
        web_token_neu.main(["999999", "--ja"])
    assert beendet.value.code != 0
