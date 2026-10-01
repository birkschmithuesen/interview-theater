"""Der Interview-Umschalter -- ueber /interview und /fertig, nicht daneben.

Birk, 30.09.2026: "einmal tippen = Aufnahme laeuft, erneut tippen = Stopp."
Die Klasse einer Aufnahme haengt NUR am Modus (aufnahme.klasse_fuer,
aufnahme.py:208) -- also schaltet der Umschalter den Modus, und zwar auf dem
Weg, den es schon gibt. Eine zweite Moduslogik waere eine zweite Wahrheit.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import befehle, db, repo, telegram, web, web_kanal

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


def _post(basis, token, koerper):
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/interview",
        data=json.dumps({"nonce": web.nonce(SCHLUESSEL, token), **koerper}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(anfrage, timeout=5) as antwort:
        return antwort.status, json.loads(antwort.read().decode("utf-8"))


def test_an_schickt_den_interview_befehl(aufbau):
    basis, token, pfad = aufbau
    status, antwort = _post(basis, token, {"an": True})
    assert status == 202

    conn = db.verbinde(pfad)
    zeile = repo.hole_web_post(conn, antwort["message_id"])
    assert zeile["typ"] == repo.WEB_TYP_BEFEHL
    assert zeile["text"] == "/interview"


def test_aus_schickt_fertig(aufbau):
    basis, token, pfad = aufbau
    _status, antwort = _post(basis, token, {"an": False})
    conn = db.verbinde(pfad)
    assert repo.hole_web_post(conn, antwort["message_id"])["text"] == "/fertig"


def test_beide_befehle_sind_dem_bot_bekannt():
    """Wenn einer umbenannt wird, soll es hier auffallen und nicht im
    Browser."""
    assert "/interview" in befehle._BEKANNTE_BEFEHLE
    assert "/fertig" in befehle._BEKANNTE_BEFEHLE


def test_der_bot_liest_daraus_eine_gewoehnliche_textnachricht(aufbau):
    """``befehle.behandle`` faengt Slash-Text ab, bevor ein Kontext gebaut
    wird. Der Weg ist damit derselbe wie bei einem getippten ``/interview``."""
    basis, token, pfad = aufbau
    _status, antwort = _post(basis, token, {"an": True})
    conn = db.verbinde(pfad)
    kanal = web_kanal.WebKanal(conn, CHAT, "/tmp/audio", schritt_s=0.01)
    gedeutet = telegram.lies_nachricht(
        kanal.hole_updates(antwort["message_id"], timeout=0)[0]
    )
    assert gedeutet["typ"] == "text"
    assert gedeutet["text"] == "/interview"


def test_der_umschalter_steht_nicht_im_chatverlauf(aufbau):
    """Slash-Befehle werden nicht beworben (AGENTS.md) -- der Knopf steht
    schon da, sein Slash-Text gehoert nicht in die Blase."""
    basis, token, _pfad = aufbau
    _post(basis, token, {"an": True})
    with urllib.request.urlopen(f"{basis}/g/{token}/chat/zustand?nach=0",
                                timeout=5) as antwort:
        zustand = json.loads(antwort.read().decode("utf-8"))
    assert zustand["nachrichten"] == []


def test_der_zustand_meldet_den_modus_aus_der_datenbank(aufbau):
    """Seitenwechsel oder Neuladen bei laufendem Interview: der Knopf muss
    danach den Modus aus der DB zeigen und nicht aus dem Arbeitsspeicher des
    Browsers (Birk, Punkt 1: "Zustand unmissverstaendlich")."""
    basis, token, pfad = aufbau
    conn = db.verbinde(pfad)
    repo.setze_interviewmodus(conn, CHAT, repo._jetzt())
    conn.close()

    with urllib.request.urlopen(f"{basis}/g/{token}/chat/zustand?nach=0",
                                timeout=5) as antwort:
        assert json.loads(antwort.read().decode("utf-8"))["interviewmodus"] is True
    with urllib.request.urlopen(f"{basis}/g/{token}/chat", timeout=5) as antwort:
        assert 'data-interview="1"' in antwort.read().decode("utf-8")


@pytest.mark.parametrize("kaputt", [{}, {"an": "ja"}, {"an": 1}, {"an": None}])
def test_an_muss_ein_boolescher_wert_sein(aufbau, kaputt):
    """``repo.setze_szene_usa`` nimmt einen bool, und ein nicht-leerer String
    ist wahr -- ein "nein" wuerde dort als Zustimmung enden (AGENTS.md,
    Fallstrick). Dieselbe Strenge hier: der Umschalter raet nicht."""
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _post(basis, token, kaputt)
    assert fehler.value.code == 400


def test_ohne_nonce_gibt_403(aufbau):
    basis, token, _pfad = aufbau
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/chat/interview",
        data=json.dumps({"an": True}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 403


def test_kein_modellaufruf_und_keine_zweite_moduslogik():
    """``web_chat`` schaltet den Modus nicht selbst: es schickt den Befehl.
    Damit gilt Zusage 2 (kein Modell im Handler) und es gibt nur einen Ort,
    an dem ``interviewmodus_seit`` gesetzt wird."""
    from pathlib import Path

    from interview_theater import web_chat

    quelle = Path(web_chat.__file__).read_text(encoding="utf-8")
    assert "setze_interviewmodus" not in quelle
    assert "stelle_interview_sicher" not in quelle
    assert "beende_interview" not in quelle
    assert "import llm" not in quelle
    assert "import stt" not in quelle
