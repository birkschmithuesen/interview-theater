"""Der Serververtrag des Chat-JavaScripts -- ohne Browser.

Was hier NICHT geprueft wird, prueft ``tests/e2e/test_web_chat_e2e.py``: der
Recorder, die Segmente, PTT, die Warteschlange. Hier steht, was man am HTML
messen kann -- und das ist mehr, als es klingt: jede Zahl, die das JS braucht,
und jeder Endpunkt, den es ruft.
"""

import re
import threading
import urllib.request
from pathlib import Path

import pytest

from interview_theater import db, repo, web, web_chat

CHAT = 7_000_000_000_001
SCHLUESSEL = b"x" * 32


@pytest.fixture
def seite(tmp_path, monkeypatch):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    monkeypatch.setenv("IT_WEB_SEGMENT_MS", "1200")

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{dienst.server_address[1]}"
    with urllib.request.urlopen(f"{basis}/g/{token}/chat", timeout=5) as antwort:
        html = antwort.read().decode("utf-8")
    dienst.shutdown()
    return html


def test_die_bedienelemente_stehen_da(seite):
    for kennung in ("verlauf", "eingabe", "senden", "ptt", "interview",
                    "uhr", "pegel", "warteschlange", "nonce", "tippt", "fuss"):
        assert f'id="{kennung}"' in seite, kennung


def test_die_segmentlaenge_kommt_aus_der_umgebung(seite):
    """Der Browsertest verkuerzt sie per Parameter -- 45 Sekunden je Segment
    wuerden einen Testlauf nutzlos lang machen."""
    assert 'data-segment-ms="1200"' in seite


def test_der_nonce_steht_im_body_und_nicht_daran(seite):
    """Dieselbe Entscheidung wie auf der Gruppenseite (``web.nonce``):
    abgeleitet, nicht gewuerfelt, und IM body -- sonst reisst ein
    Fensterwechsel jedes offene Eingabefeld mit."""
    assert re.search(r'<input type="hidden" id="nonce" value="\d+\.[0-9a-f]{32}">', seite)


def test_das_js_ruft_nur_endpunkte_die_es_gibt(seite):
    """Jeder ``fetch``-Pfad im JS muss in ``_POSTWEGE`` oder unter den
    GET-Wegen stehen. Ein Tippfehler waere im Browser ein stilles 404."""
    pfade = set(re.findall(r"chat/([a-z]+)", web_chat._CHAT_JS))
    erlaubt = set(web_chat._POSTWEGE) | {"zustand", "datei"}
    assert pfade <= erlaubt, pfade - erlaubt


def test_das_js_nennt_jeden_postweg(seite):
    """Die andere Richtung: ein Endpunkt ohne Aufrufer im JS ist entweder
    toter Code oder ein vergessener Knopf."""
    for weg in web_chat._POSTWEGE:
        assert f"chat/{weg}" in web_chat._CHAT_JS, weg


def test_die_ptt_mindestdauer_kommt_aus_einer_konstante(seite):
    assert web_chat.PTT_MIN_MS == 500
    assert f"var PTT_MIN_MS = {web_chat.PTT_MIN_MS};" in seite
    # Kein zweiter Ort: im JS-Rohtext steht der Platzhalter, nicht die Zahl.
    assert "__PTT_MIN_MS__" in web_chat._CHAT_JS


def test_pointercancel_und_setpointercapture_stehen_im_js():
    """Birks Vorgabe woertlich: Pointer Events + setPointerCapture, Abbruch
    bei Wegziehen/pointercancel sendet NICHTS."""
    for baustein in ("setPointerCapture", "pointercancel", "pointerdown",
                     "pointerup", "releasePointerCapture"):
        assert baustein in web_chat._CHAT_JS, baustein


def test_kein_schieben_zum_sperren(seite):
    """Birk, verbindlich: ZWEI getrennte Knoepfe, KEIN Schieben-zum-Sperren.
    Ein Test, der eine Entscheidung festhaelt, die sonst niemand mehr kennt."""
    for verboten in ("slideToLock", "sperren", "lock", "swipe"):
        assert verboten.lower() not in web_chat._CHAT_JS.lower(), verboten


def test_das_js_startet_einen_eigenen_recorder_je_segment():
    """MediaRecorder-Zeitscheiben sind einzeln nicht dekodierbar: nur das
    erste Stueck traegt den Container-Kopf. Also stop() + start() je Segment,
    NICHT start(timeslice)."""
    assert "new MediaRecorder" in web_chat._CHAT_JS
    assert re.search(r"\.start\(\s*\)", web_chat._CHAT_JS)
    assert not re.search(r"\.start\(\s*[A-Za-z0-9_]+\s*\)", web_chat._CHAT_JS)


def test_das_js_wartet_auf_den_interviewmodus_vor_dem_ersten_upload():
    """Der Wettlauf: die Aufnahme startet sofort, der Upload wartet bis
    ``interviewmodus: true``. Sonst kaeme das erste Segment vor dem
    ``/interview`` an, und ``aufnahme.klasse_fuer`` machte daraus eine
    kurz-Aufnahme statt eines Interview-Teils."""
    assert "interviewmodus" in web_chat._CHAT_JS


def test_das_js_laedt_ohne_nachladen_der_ganzen_seite(seite):
    """``web._seite(..., nachladen=False)``: das sanfte Nachladen tauscht den
    ``<body>`` aus, und mitten in einer Aufnahme riss das Recorder, Timer und
    Warteschlange mit."""
    assert "__NEULADEN_MS__" not in seite
    assert "location.reload" not in seite


def test_die_polltakte_stehen_als_konstanten():
    assert web_chat.POLL_MS == 2000
    assert web_chat.POLL_MS_HINTERGRUND == 10000
    fertig = web_chat._js()
    assert f"var POLL_MS = {web_chat.POLL_MS};" in fertig
    assert f"var POLL_MS_HINTERGRUND = {web_chat.POLL_MS_HINTERGRUND};" in fertig


def test_das_js_setzt_kein_cookie_und_nichts_in_den_speicher():
    """E6: der Zustand steht im DOM und in der URL, nirgends sonst -- damit
    ein Link teilbar bleibt und ein zweites Telefon dieselbe Gruppe sieht."""
    for verboten in ("document.cookie", "localStorage", "sessionStorage",
                     "WebSocket", "EventSource"):
        assert verboten not in web_chat._CHAT_JS, verboten
