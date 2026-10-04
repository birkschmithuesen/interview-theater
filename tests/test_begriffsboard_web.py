"""Karte t_4517d4ad, Aufgabe 8: das Board im CoThinker-Tab (D9)."""

import json
import re
import sqlite3
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_daten, web_vereint, workshop

CHAT = 1
BOARD = [
    {"begriff": "Musik", "nennungen": 9, "zustimmung": 2, "begruendung": "", "zitat": "",
     "doppelbedeutung": "", "status": "verworfen"},
    {"begriff": "Heimat", "nennungen": 2, "zustimmung": 2, "begruendung": "Wo die <Oma> kocht.",
     "zitat": "ZITAT-NIE-IM-WEB", "doppelbedeutung": "Ort und Gefuehl", "status": "favorit"},
    {"begriff": "Grenze", "nennungen": 1, "zustimmung": 0, "begruendung": "", "zitat": "",
     "doppelbedeutung": "", "status": "kandidat"},
]

#: Dieselbe chat_id wie in ``tests/test_web_vereint.py`` -- fuer den
#: Seiten-Test unten, der dieselbe ``aufbau``-Fixture kopiert (per Auftrag,
#: nicht importiert).
CHAT_AUFBAU = 7_000_000_000_001


@pytest.fixture
def pfad(tmp_path):
    p = str(tmp_path / "t.db")
    c = db.verbinde(p)
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    repo.lege_begriffsboard_an(c, CHAT, json.dumps(BOARD), "sovereign", 0)
    c.close()
    return p


def _ro(pfad):
    c = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def test_web_daten_liest_sortiert_und_ohne_zitat(pfad):
    eintraege = web_daten.begriffsboard(_ro(pfad), CHAT)
    assert [e["begriff"] for e in eintraege] == ["Heimat", "Grenze", "Musik"]
    assert all("zitat" not in e for e in eintraege)


def test_web_daten_ohne_tabelle_ist_leer(tmp_path):
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    assert web_daten.begriffsboard(c, CHAT) == []


def test_html_ist_funktional_mit_data_attributen(pfad):
    html_ = web._begriffsboard_html(web_daten.begriffsboard(_ro(pfad), CHAT))
    assert 'data-ansicht="begriffsboard"' in html_
    assert re.search(r'<li data-begriff="Heimat" data-status="favorit"[^>]*data-top="1"', html_)
    assert re.search(r'<li data-begriff="Musik" data-status="verworfen"(?![^>]*data-top)[^>]*>', html_)
    assert "<details>" in html_ and "Ort und Gefuehl" in html_
    assert "&lt;Oma&gt;" in html_ and "<Oma>" not in html_
    assert "ZITAT-NIE-IM-WEB" not in html_
    assert "style=" not in html_
    assert re.search(r"\son\w+=", html_) is None


def test_leeres_board_hat_den_leertext():
    html_ = web._begriffsboard_html([])
    assert 'data-ansicht="begriffsboard"' in html_ and "<li" not in html_


def test_buehne_html_weicht_in_phase_1_aufs_board_aus():
    html_ = web._buehne_html({"begriffsboard_zeigen": True, "begriffsboard": [
        {"begriff": "Mut", "nennungen": 1, "zustimmung": 0, "begruendung": "",
         "doppelbedeutung": "", "status": "kandidat"},
    ]})
    assert 'data-begriff="Mut"' in html_


def test_buehne_html_ohne_schalter_wie_bisher():
    html_ = web._buehne_html({"buehnenkarten": []})
    assert "data-ansicht" not in html_


def test_js_laesst_den_cothinker_in_phase_1_mit_board_zu():
    js = web_vereint._VEREINT_JS
    assert "function istCoThinkerPhase()" in js
    assert "rm.dataset.begriffsboard === '1'" in js
    lade = js[js.index("function ladeBuehne()"):]
    assert lade.index("if (!istCoThinkerPhase()) { return; }") < lade.index("fetch(")
    assert "istPhase4()" not in js


def test_roadmap_traegt_das_board_merkmal_nur_mit_profil(monkeypatch):
    # ANNAHME-Korrektur: ``_leiste_html`` liest an der aktiven Phase auch
    # ``name``/``erledigt``/``gesamt`` (fuer die Kopfzeile) -- das Minimaldikt
    # der Kartenvorlage hatte nur ``nummer``/``bezeichnung``/``aktiv``/
    # ``aufgaben`` und waere an ``aktiv["name"]`` mit KeyError gescheitert.
    daten = [{
        "nummer": 1, "bezeichnung": "Terms", "name": "Terms",
        "aktiv": True, "erledigt": 0, "gesamt": 0, "aufgaben": [],
    }]
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    ohne = web_vereint._leiste_html(daten)
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    mit = web_vereint._leiste_html(daten)
    assert "data-begriffsboard" not in ohne
    assert re.search(r'id="roadmap" data-aktive-phase="1" data-begriffsboard="1"', mit)


def test_stepper_traegt_das_board_merkmal_nur_mit_profil(monkeypatch):
    """Derselbe Fall wie oben, aber fuer den Stepper (``_stepper_html``) --
    den zweiten Renderer von #roadmap, seit Padua live auf ihn umgeschaltet
    hat (``web.phasennav_stepper``). Bug Birk Live-Test 04.10.2026: nur
    ``_leiste_html`` haengte ``_board_merkmal()`` an, der Stepper nicht --
    der CoThinker-Tab blieb in Phase 1 unsichtbar, weil
    ``istCoThinkerPhase()`` (``_VEREINT_JS``) kein ``data-begriffsboard``
    fand. Beide Renderer MUESSEN dasselbe Attribut tragen."""
    daten = [{
        "nummer": 1, "bezeichnung": "Terms", "name": "Terms",
        "aktiv": True, "erledigt": 0, "gesamt": 0, "aufgaben": [],
        "satz": "Take in and sort the list of terms collected in the plenary.",
        "bereit": True, "fehlt": (),
    }]
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    ohne = web_vereint._stepper_html(daten)
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    mit = web_vereint._stepper_html(daten)
    assert "data-begriffsboard" not in ohne
    assert re.search(r'id="roadmap" data-stepper="1" data-aktive-phase="1" data-begriffsboard="1"', mit)


# -- Seiten-Test (kopierte Fixture/Helfer aus tests/test_web_vereint.py) ----


@pytest.fixture
def aufbau(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT_AUFBAU, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT_AUFBAU, "web")
    repo.setze_arbeitsstand(conn, CHAT_AUFBAU, "begriffe", "Heimat, Arbeit")
    repo.setze_arbeitsstand(conn, CHAT_AUFBAU, "rahmen", "Bahnhof, nachts")
    repo.setze_figur(conn, CHAT_AUFBAU, "Meryem", "kam 1998")
    token = repo.stelle_web_token_sicher(conn, CHAT_AUFBAU)
    conn.commit()

    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=b"x" * 32)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", token, pfad
    dienst.shutdown()


def _hole(url, folge=True):
    class OhneUmleitung(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):
            return None

    oeffner = (urllib.request.build_opener()
               if folge else urllib.request.build_opener(OhneUmleitung))
    try:
        with oeffner.open(url, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8"), antwort.headers
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8"), fehler.headers


def test_teil_buehne_liefert_das_board_in_phase_1(aufbau, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    basis, token, pfad_ = aufbau
    c = db.verbinde(pfad_)
    repo.setze_phase(c, CHAT_AUFBAU, 1)
    repo.lege_begriffsboard_an(c, CHAT_AUFBAU, json.dumps(BOARD), "sovereign", 0)
    _status, teil, _kopf = _hole(f"{basis}/g/{token}/teil/buehne")
    assert 'data-begriff="Heimat"' in teil
    _status, seite, _kopf = _hole(f"{basis}/g/{token}")
    assert re.search(r'<button[^>]*data-tab="buehne"(?![^>]*hidden)', seite)


def test_teil_buehne_ohne_profil_in_phase_1_zeigt_kein_board(aufbau, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    basis, token, pfad_ = aufbau
    c = db.verbinde(pfad_)
    repo.setze_phase(c, CHAT_AUFBAU, 1)
    repo.lege_begriffsboard_an(c, CHAT_AUFBAU, json.dumps(BOARD), "sovereign", 0)
    _status, teil, _kopf = _hole(f"{basis}/g/{token}/teil/buehne")
    assert "data-begriff" not in teil
