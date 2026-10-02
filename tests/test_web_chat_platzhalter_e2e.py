"""Der Platzhalter kommt wirklich beim Browser an -- ueber die erste Seite
UND ueber den Poll (UX-Knoepfe-Karte, Abschnitt 1). Derselbe Serveraufbau
wie ``tests/test_web_chat_js.py``."""

import json
import threading
import urllib.request

import pytest

from interview_theater import db, phasen, repo, web, web_chat

CHAT = 7_000_000_000_002
SCHLUESSEL = b"y" * 32


def _starte(tmp_path, phase=None, fragen_aktuell=None):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    if phase is not None:
        phasen.setze(conn, CHAT, int(phase), "befehl")
    if fragen_aktuell is not None:
        repo.setze_arbeitsstand(conn, CHAT, "fragen_aktuell", str(fragen_aktuell))
    conn.commit()
    conn.close()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    return dienst, basis, token


def test_die_erste_seite_traegt_den_phasenpassenden_platzhalter(tmp_path):
    dienst, basis, token = _starte(tmp_path, phase=4)
    try:
        with urllib.request.urlopen(f"{basis}/g/{token}/chat", timeout=5) as antwort:
            seite = antwort.read().decode("utf-8")
    finally:
        dienst.shutdown()
    assert web_chat._TEXT_EINGABE_SETTING in seite


def test_der_poll_traegt_denselben_platzhalter(tmp_path):
    dienst, basis, token = _starte(tmp_path, phase=2, fragen_aktuell=3)
    try:
        with urllib.request.urlopen(
            f"{basis}/g/{token}/chat/zustand", timeout=5
        ) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    finally:
        dienst.shutdown()
    assert daten["platzhalter"] == web_chat._TEXT_EINGABE_FRAGEN


def test_ohne_besondere_phase_bleibt_es_beim_standard(tmp_path):
    dienst, basis, token = _starte(tmp_path)
    try:
        with urllib.request.urlopen(f"{basis}/g/{token}/chat", timeout=5) as antwort:
            seite = antwort.read().decode("utf-8")
    finally:
        dienst.shutdown()
    assert web_chat._TEXT_EINGABE in seite
