"""Nachgeladen wird nur das Stand-Panel -- und nur, wenn es vorn ist.

Der Grund steht im Plan: ``_SCROLL_JS`` tauscht ``document.body.innerHTML``
aus. Im gemeinsamen Dokument riesse das den laufenden MediaRecorder, das halb
getippte Feld und die Strom-Blase mit.
"""

import threading
import urllib.request

import pytest

from interview_theater import db, repo, web, web_vereint

CHAT = 7_000_000_000_001


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_arbeitsstand(conn, CHAT, "rahmen", "Bahnhof, nachts")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


def _hole(url):
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def test_der_teil_liefert_nur_das_panel(aufbau):
    basis, token, _pfad = aufbau
    status, text = _hole(f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/stand")
    assert status == 200
    assert "<!doctype html>" not in text
    assert "Bahnhof, nachts" in text
    # Der frische Nonce kommt mit: sonst waere jedes Formular nach dem
    # ersten Stundenwechsel ungueltig.
    assert 'id="nonce"' in text


def test_der_teil_traegt_keinen_chat(aufbau):
    basis, token, _pfad = aufbau
    _status, text = _hole(f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/stand")
    assert 'id="tab-chat"' not in text
    assert 'id="verlauf"' not in text


def test_ein_unbekannter_teil_ist_404(aufbau):
    basis, token, _pfad = aufbau
    with pytest.raises(urllib.error.HTTPError) as fehler:
        _hole(f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/chat")
    assert fehler.value.code == 404


def test_der_teil_greift_unter_dem_praefix(aufbau):
    basis, token, _pfad = aufbau
    assert _hole(f"{basis}/theatersoap/g/{token}/{web_vereint.TEIL_PFAD}/stand")[0] == 200


def test_der_teil_nimmt_kein_post(aufbau):
    """Geschrieben wird ueber ``/g/<token>`` wie bisher -- ein zweiter
    Schreibweg waere genau das, was N1 verhindert hat."""
    import urllib.error

    anfrage = urllib.request.Request(
        f"{basis_und_token(aufbau)}/{web_vereint.TEIL_PFAD}/stand",
        data=b"{}", method="POST",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 404


def basis_und_token(aufbau) -> str:
    basis, token, _pfad = aufbau
    return f"{basis}/g/{token}"


def test_das_js_ersetzt_nur_das_panel():
    js = web_vereint._VEREINT_JS
    assert "document.body.innerHTML" not in js
    assert "tab-stand" in js
    assert web_vereint.TEIL_PFAD in js


def test_das_js_haelt_die_beiden_sperren_ein():
    """Wer gerade tippt, verliert nichts (Brief 05.09. abends) -- dieselben
    zwei Sperren wie in ``_SCROLL_JS``."""
    js = web_vereint._VEREINT_JS
    assert "activeElement" in js
    assert "data-schmutzig" in js or "schmutzig" in js


def test_das_js_laedt_nicht_nach_solange_das_panel_verborgen_ist():
    assert ".hidden" in web_vereint._VEREINT_JS


def test_das_js_vergleicht_normalisiert():
    """Review Fix-Runde 1, Befund 1: ein roher Server-String gleicht nie der
    browser-serialisierten Form von ``panel.innerHTML`` -- ohne Normalisierung
    (``DOMParser``, wie ``web._SCROLL_JS``) wuerde der Austausch auf JEDEM
    Takt laufen, nicht nur bei einer echten Aenderung."""
    js = web_vereint._VEREINT_JS
    assert "DOMParser" in js
    # Die verworfene Fassung: der rohe Server-Text direkt gegen die
    # Live-DOM-Form verglichen -- die stimmt nie, der Austausch liefe jeden
    # Takt.
    assert "html === panel.innerHTML" not in js


def test_das_js_gibt_die_suche_an_den_teil_weiter():
    """Review Fix-Runde 1, Befund 2: eine per ``?szene=..&fassung=..``
    gewaehlte Fassung soll die Nachlade-Runde ueberleben."""
    assert "location.search" in web_vereint._VEREINT_JS


def test_der_teil_zeigt_die_gewaehlte_fassung(aufbau):
    """Review Fix-Runde 1, Befund 2: ``teil/stand`` muss dieselbe Fassungswahl
    honorieren wie die ganze Seite (``web.fassungswahl``)."""
    basis, token, pfad = aufbau
    conn = db.verbinde(pfad)
    szene_id = repo.stelle_szene_sicher(conn, CHAT, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Steg")
    repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")
    for text in ("eins", "zwei", "drei"):
        repo.haenge_szenenfassung_an(conn, CHAT, szene_id, text, None, "Dialog")
    repo.aktualisiere_szene(conn, szene_id, "Am Steg", None, "drei", None)
    conn.commit()
    conn.close()

    _status, aktuell = _hole(f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/stand")
    assert "Fassung 1 von 3" not in aktuell

    _status, gewaehlt = _hole(
        f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/stand?szene={szene_id}&fassung=1"
    )
    assert "Fassung 1 von 3" in gewaehlt
