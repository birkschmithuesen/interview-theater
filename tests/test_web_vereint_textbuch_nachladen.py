"""P57 Lauf 2 A1: das Textbuch-Panel laedt nach.

Befund: ``_TEILE`` kannte ``textbuch`` nicht, das Panel blieb auf dem Stand
des ersten Seitenaufbaus ("Not written yet" trotz Szenenprosa) bis zum
vollen Neuladen. B2: der Platzhalter stand ueber vorhandener Prosa."""

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
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    szene_id = repo.lege_szene_an(conn, CHAT, 1, "Ankunft", None, None)
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad, szene_id
    dienst.shutdown()


def _hole(url):
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def test_teil_textbuch_liefert_neue_prosa_ohne_neuladen(aufbau):
    basis, token, pfad, szene_id = aufbau
    status, text = _hole(f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/textbuch")
    assert status == 200
    assert "<!doctype html>" not in text
    assert "Der Zug fuhr ohne sie ab." not in text
    conn = db.verbinde(pfad)
    repo.aktualisiere_szene(conn, szene_id, "Ankunft", None, None,
                            prosa="Der Zug fuhr ohne sie ab.")
    conn.commit()
    _status, text = _hole(f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/textbuch")
    assert "Der Zug fuhr ohne sie ab." in text


def test_teil_textbuch_traegt_keinen_chat(aufbau):
    basis, token, _pfad, _sid = aufbau
    _status, text = _hole(f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/textbuch")
    assert 'id="tab-chat"' not in text
    assert 'id="nonce"' not in text


def test_textbuch_ist_ein_teil():
    assert "textbuch" in web_vereint._TEILE


def test_das_js_holt_das_textbuch_nach():
    js = web_vereint._VEREINT_JS
    assert "BASIS_TEIL + 'textbuch'" in js
    assert "tab-textbuch" in js
    assert "ladeTextbuch" in js


def test_platzhalter_nicht_ueber_vorhandener_prosa(aufbau):
    basis, token, pfad, szene_id = aufbau
    conn = db.verbinde(pfad)
    repo.aktualisiere_szene(conn, szene_id, "Ankunft", None, None,
                            prosa="Der Zug fuhr ohne sie ab.")
    conn.commit()
    _status, text = _hole(f"{basis}/g/{token}/{web_vereint.TEIL_PFAD}/textbuch")
    assert "Der Zug fuhr ohne sie ab." in text
    assert 'class="offen"' not in text


def test_textbuch_vergleicht_per_stempel_nicht_mit_erstem_abruf():
    """P57 Lauf 3 A1: der erste Abruf darf nicht nur 'gemerkt' werden -- die
    Seite kann vor der Szene gebaut sein und zeigte sonst den Altstand."""
    js = web_vereint._VEREINT_JS
    assert "textbuchLetzter" not in js
    assert "data-stempel" in js


def _koerper(pfad, token):
    conn = db.verbinde(pfad)
    from interview_theater import web_daten

    daten = web_daten.gruppe_nach_token(conn, token)
    return web.textbuch_koerper(daten, token)


@pytest.mark.parametrize("phase", [5, 6])
def test_koerper_zeigt_prosa_statt_platzhalter_in_phase_5_6(aufbau, phase):
    """Szene mit Prosa, ohne Volltext, Phase 5/6: Text statt 'Noch nicht
    geschrieben', und der Stempel aendert sich mit dem Inhalt."""
    _basis, token, pfad, szene_id = aufbau
    conn = db.verbinde(pfad)
    repo.setze_phase(conn, CHAT, phase)
    conn.commit()
    vorher = _koerper(pfad, token)
    assert 'class="offen"' in vorher
    repo.aktualisiere_szene(conn, szene_id, "Ankunft", None, None,
                            prosa="Der Zug fuhr ohne sie ab.")
    conn.commit()
    nachher = _koerper(pfad, token)
    assert "Der Zug fuhr ohne sie ab." in nachher
    assert 'class="offen"' not in nachher
    import re

    def stempel(t):
        return re.search(r'data-stempel="([0-9a-f]+)"', t).group(1)

    assert stempel(vorher) != stempel(nachher)
    assert stempel(nachher) == stempel(_koerper(pfad, token))
