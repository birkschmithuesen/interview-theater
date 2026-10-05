"""Pflichtpunkt 2, Fix 1 von 2 (04.10.2026): der erste Seitenaufruf einer
frischen Web-Gruppe loest genau eine Begruessung aus.

Der Mechanismus spiegelt die bestehende ``/phaseklick``-Naht
(``tests/test_phase_klick.py``): der Webserver legt ``/start`` nur als
gewoehnlichen Eingang ab, wenn der Chat noch leer ist
(``repo.hat_bot_nachricht``), und der Bot fuehrt ``bot.erstkontakt`` aus --
ueber denselben Weg, den die erste echte Unterhaltung heute schon nimmt.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import befehle, db, repo, web

CHAT = 7_000_000_000_777
SCHLUESSEL = b"x" * 32


class TelegramAttrappe:
    """Wie in ``tests/test_befehle.py`` -- zeichnet nur auf, was gesendet
    wurde, ohne Netz."""

    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        return 9001

    def sende_mit_knoepfen(self, chat_id, text, knoepfe, **_kw):
        self.gesendet.append((chat_id, text))
        return 9001


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _post(url, nutzlast):
    anfrage = urllib.request.Request(
        url, data=json.dumps(nutzlast).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def _eingaenge(pfad):
    conn = db.verbinde(pfad)
    try:
        return [dict(z) for z in repo.web_eingang(conn, CHAT, 0)]
    finally:
        conn.close()


@pytest.fixture
def server(tmp_path):
    pfad = str(tmp_path / "web.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


# -- der Weg durch den Webserver --------------------------------------------


def test_der_erste_seitenaufruf_legt_start_an(server):
    basis, token, pfad = server
    status, _text = _post(f"{basis}/g/{token}/chat/start",
                          {"nonce": web.nonce(SCHLUESSEL, token)})
    assert status == 202
    eingaenge = _eingaenge(pfad)
    assert [(z["typ"], z["text"]) for z in eingaenge] == [(repo.WEB_TYP_BEFEHL, "/start")]


def test_eine_schon_begruesste_gruppe_bekommt_kein_start(server):
    """Die Bedingung, die 'zweiter Aufruf erzeugt nichts' wahr macht, OHNE
    dass der Bot zur Pruefzeit laeuft: der Chat ist schon nicht mehr leer."""
    basis, token, pfad = server
    conn = db.verbinde(pfad)
    repo.merke_nachricht(conn, CHAT, 1, "gruppe1", 1, "text", "Hallo!", repo._jetzt())
    conn.commit()
    conn.close()

    status, _text = _post(f"{basis}/g/{token}/chat/start",
                          {"nonce": web.nonce(SCHLUESSEL, token)})
    assert status == 202
    assert _eingaenge(pfad) == []


def test_ohne_nonce_passiert_nichts(server):
    basis, token, pfad = server
    status, _text = _post(f"{basis}/g/{token}/chat/start", {})
    assert status == 403
    assert _eingaenge(pfad) == []


def test_start_fuer_telegram_gruppe_ist_404(tmp_path):
    """Derselbe Schutz wie bei jedem anderen ``/chat/*``-Weg (AGENTS.md,
    Abschlussreview I3): eine Telegram-Gruppe hat keinen Bot, der
    ``web_post`` liest."""
    pfad = str(tmp_path / "telegram.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    try:
        basis = f"http://127.0.0.1:{dienst.server_address[1]}"
        status, _text = _post(f"{basis}/g/{token}/chat/start",
                              {"nonce": web.nonce(SCHLUESSEL, token)})
        assert status == 404
    finally:
        dienst.shutdown()


# -- die Naht (Befehl, versteckt) --------------------------------------------


def test_start_ist_versteckt():
    assert "/start" in befehle._bekannte_befehle()
    assert "start" not in {b["command"] for b in befehle.BEFEHLE_LISTE}


def test_befehl_start_begruesst_eine_frische_gruppe(conn, einst, tg):
    assert repo.hat_bot_nachricht(conn, 1) is False
    behandelt = befehle.behandle(conn, tg, einst, 1, "/start", None)
    assert behandelt is True
    assert tg.gesendet  # die Begruessung (bot.erstkontakt) ist raus
    assert repo.hat_bot_nachricht(conn, 1) is True


def test_befehl_start_tut_nichts_wenn_schon_begruesst(conn, einst, tg):
    """Die defensive Gegenpruefung im Bot: der Webserver macht den
    gewoehnlichen Fall idempotent, das hier faengt das Wettrennen zwischen
    zwei fast gleichzeitigen Seitenaufrufen ab."""
    repo.merke_nachricht(conn, 1, 1, einst.bot_name, 1, "text", "Hallo!", repo._jetzt())

    behandelt = befehle.behandle(conn, tg, einst, 1, "/start", None)

    assert behandelt is True
    assert tg.gesendet == []
