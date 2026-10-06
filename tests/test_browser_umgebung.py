import json
import os
import socket
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from simulation import browser_umgebung as u
from interview_theater import db, repo


def test_freier_port_ist_wirklich_frei():
    port = u.freier_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))  # waere belegt, schluege das fehl


def test_baue_gruppe_legt_eine_web_gruppe_an(tmp_path):
    db_pfad = str(tmp_path / "sim.db")
    chat_id, token = u.baue_gruppe(db_pfad, "padua-browser-sim")
    conn = db.verbinde(db_pfad)
    try:
        zeile = conn.execute(
            "SELECT kanal, web_token FROM gruppe WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        assert zeile["kanal"] == "web"
        assert zeile["web_token"] == token
    finally:
        conn.close()


def test_bot_skript_sourcet_die_env_datei_und_ueberschreibt_danach():
    skript = u.bau_bot_skript("/geheim/padua-test.env", "/tmp/sim.db",
                              "/tmp/audio", 7_000_000_000_123, py="/usr/bin/python3")
    zeilen = skript.splitlines()
    source_zeile = next(i for i, z in enumerate(zeilen) if "source" in z)
    db_zeile = next(i for i, z in enumerate(zeilen) if "IT_DB=" in z)
    assert source_zeile < db_zeile  # Overrides stehen NACH dem source
    assert '/geheim/padua-test.env' in skript
    assert "IT_KANAL=web" in skript
    assert "IT_WEB_CHAT_ID=\"7000000000123\"" in skript
    assert "IT_WORKSHOP=padua-2026" in skript
    assert "IT_BOT_NAME=padua-browser-sim" in skript
    assert skript.strip().endswith("-m interview_theater.bot")


def test_starte_web_antwortet_gesund(tmp_path):
    """Kein Geheimnis noetig: der Webserver braucht keine Modell-Zugangsdaten."""
    db_pfad = str(tmp_path / "sim.db")
    u.baue_gruppe(db_pfad, "padua-browser-sim")
    prozess, log, basis = u.starte_web(
        db_pfad, str(tmp_path / "audio"), str(tmp_path / "web.log"))
    try:
        with urllib.request.urlopen(f"{basis}/gesund", timeout=5) as a:
            assert a.read().decode().strip() == "ok"
    finally:
        prozess.terminate()
        prozess.wait(timeout=5)
        log.close()


def test_bot_skript_entfernt_board_vorgaben_nach_dem_sourcen(tmp_path):
    """Die Padua-Env enthaelt seit 05.10. 08:33 eine Sofortmassnahme
    (IT_BEGRIFFSBOARD_MIN_ZEICHEN=100) -- die Simulation prueft die
    Code-Vorgaben, sonst saehe sie die Board-Schwelle nie."""
    env = tmp_path / "x.env"
    env.write_text("IT_BEGRIFFSBOARD_MIN_ZEICHEN=100\n")
    text = u.bot_skript(env, modul_oder_datei="-m interview_theater.bot", app_wurzel=tmp_path)
    pos_source = text.index(str(env))
    unset_zeile = f"unset {' '.join(u.CODE_VORGABEN_ENTFERNEN)}"
    assert unset_zeile in text
    assert text.index(unset_zeile) > pos_source  # NACH dem source, nicht davor
    assert "exec " in text and "interview_theater.bot" in text


def test_bot_skript_nutzt_app_wurzel(tmp_path):
    app = tmp_path / "alt"
    app.mkdir()
    text = u.bot_skript(tmp_path / "x.env", modul_oder_datei="-m interview_theater.bot",
                        app_wurzel=app)
    assert str(app) in text


def test_baue_gruppe_zweimal_legt_zwei_verschiedene_gruppen_an(tmp_path):
    """Grundlage fuer ``starte_stack(..., gruppen=2)`` (Task 6): zwei Rufe
    ohne Netz gegen dieselbe tmp-DB muessen verschiedene Gruppen anlegen."""
    db_pfad = str(tmp_path / "sim.db")
    chat_id_1, token_1 = u.baue_gruppe(db_pfad, "padua-browser-sim")
    chat_id_2, token_2 = u.baue_gruppe(db_pfad, "padua-browser-sim-2")
    assert chat_id_1 != chat_id_2
    assert token_1 != token_2


def test_starte_stack_gibt_absolute_pfade_an_web_und_bot(tmp_path, monkeypatch):
    """Web und Bot laufen mit ``cwd=app_wurzel`` -- ein relativer Laufordner
    (so baut ihn ``browser_lauf.main``) liesse sie bei ``--app-wurzel`` auf
    einen anderen Checkout eine fremde, leere ``sim.db`` oeffnen."""
    harness = tmp_path / "harness"
    harness.mkdir()
    monkeypatch.chdir(harness)
    gesehen = {}

    def starte_web(db_pfad, audio_verz, log_pfad, *, app_wurzel):
        gesehen["web"] = (db_pfad, audio_verz)
        return None, None, "http://x"

    def starte_bot(env_datei, db_pfad, audio_verz, chat_id, log_pfad, *, app_wurzel):
        gesehen["bot"] = (db_pfad, audio_verz)
        return None, None

    monkeypatch.setattr(u, "starte_web", starte_web)
    monkeypatch.setattr(u, "starte_bot", starte_bot)
    lauf = Path("simulation/browser_laeufe/x")
    lauf.mkdir(parents=True)
    stack = u.starte_stack("/x.env", lauf, app_wurzel=tmp_path / "alt")
    for db_pfad, audio_verz in gesehen.values():
        assert Path(db_pfad).is_absolute() and Path(audio_verz).is_absolute()
        assert Path(db_pfad) == harness / lauf / "sim.db"
    assert Path(stack.db_pfad).is_absolute()


def test_bereite_vor_fuellt_phase_1_und_2_und_bleibt_in_phase_2(tmp_path):
    from interview_theater import db, phasen, repo
    from simulation import browser_umgebung as u

    pfad = str(tmp_path / "sim.db")
    chat_id, _token = u.baue_gruppe(pfad, "padua-browser-sim")
    u.bereite_vor(pfad, chat_id, startphase=3)
    conn = db.verbinde(pfad)
    try:
        stand = repo.hole_arbeitsstand(conn, chat_id)
        assert stand["begriffe"] and stand["fragen"]
        assert stand["interview_eroeffnung"] and stand["interview_abschluss"]
        assert phasen.aktuelle(conn, chat_id) == 2
    finally:
        conn.close()


def test_bereite_vor_tut_bei_startphase_1_nichts(tmp_path):
    from interview_theater import db, repo
    from simulation import browser_umgebung as u

    pfad = str(tmp_path / "sim.db")
    chat_id, _ = u.baue_gruppe(pfad, "padua-browser-sim")
    u.bereite_vor(pfad, chat_id, startphase=1)
    conn = db.verbinde(pfad)
    try:
        stand = repo.hole_arbeitsstand(conn, chat_id)
        assert stand is None or not stand["begriffe"]
    finally:
        conn.close()


def test_bereite_vor_startphase_5_erfuellt_voraussetzung_5_und_bleibt_in_phase_4(tmp_path):
    """Task 1 (BRIEF p57): startphase=5 soll die Materiallage fuer Phase 5
    herstellen (Setting, fixierte Figuren, Geschichte, Szenenzahl, ein
    ausgewertetes Interview), den Wechsel selbst aber ``browser_lauf.main``
    ueber den echten Endpunkt ueberlassen (die Gruppe bleibt in Phase 4)."""
    from interview_theater import aufnahme, db, phasen, repo
    from simulation import browser_umgebung as u

    pfad = str(tmp_path / "sim.db")
    chat_id, _token = u.baue_gruppe(pfad, "padua-browser-sim")
    u.bereite_vor(pfad, chat_id, startphase=5)
    conn = db.verbinde(pfad)
    try:
        assert phasen.voraussetzungen(conn, chat_id)[5] is True
        assert phasen.aktuelle(conn, chat_id) == 4
        assert aufnahme.unausgewertete_interviews(conn, chat_id) == []

        kopf = aufnahme.interviews(conn, chat_id)[0]
        transkript = repo.hole_aufnahme(conn, kopf["id"])["transkript"]
        verdichtung = repo.verdichtungen(conn, chat_id)[0]
        themen = repo.themen_zu(conn, verdichtung["id"])
        assert themen  # mindestens ein Thema
        for thema in themen:
            assert thema["zitat_geprueft"] == 1
            assert thema["beleg_zitat"] in transkript

        for szene in repo.hole_szenen(conn, chat_id):
            assert not (szene["prosa"] or "").strip()
            assert (szene["titel"] or "").strip()
            assert (szene["was_passiert"] or "").strip()

        for figur in repo.figuren(conn, chat_id):
            assert not (figur["sprachstil"] or "").strip()
    finally:
        conn.close()


def test_bereite_vor_startphase_3_bleibt_zeichengleich(tmp_path):
    """Die neue Fallunterscheidung in ``bereite_vor`` darf den bestehenden
    ``startphase=3``-Weg nicht veraendern -- derselbe Befund wie der aeltere
    Test ``test_bereite_vor_fuellt_phase_1_und_2_und_bleibt_in_phase_2``,
    hier nach der Erweiterung erneut geprueft."""
    from interview_theater import db, phasen, repo
    from simulation import browser_umgebung as u

    pfad = str(tmp_path / "sim.db")
    chat_id, _token = u.baue_gruppe(pfad, "padua-browser-sim")
    u.bereite_vor(pfad, chat_id, startphase=3)
    conn = db.verbinde(pfad)
    try:
        stand = repo.hole_arbeitsstand(conn, chat_id)
        assert stand["begriffe"] and stand["fragen"]
        assert stand["interview_eroeffnung"] and stand["interview_abschluss"]
        assert phasen.aktuelle(conn, chat_id) == 2
    finally:
        conn.close()


def test_bereite_vor_startphase_6_wirft_valueerror(tmp_path):
    from simulation import browser_umgebung as u

    pfad = str(tmp_path / "sim.db")
    chat_id, _token = u.baue_gruppe(pfad, "padua-browser-sim")
    with pytest.raises(ValueError):
        u.bereite_vor(pfad, chat_id, startphase=6)


def test_lauf_verzeichnis_ist_je_lauf_eindeutig(tmp_path):
    # Lazy-Import mit importorskip wie in tests/test_browser_lauf.py: nur
    # dieser eine Test braucht browser_lauf (zieht playwright beim Import
    # mit), der Rest dieser Datei soll auch ohne Playwright laufen.
    pytest.importorskip("playwright.sync_api", reason="playwright ist hier nicht installiert")
    from simulation import browser_lauf as bl

    a = bl.lauf_verzeichnis_fuer(tmp_path, "2026-10-05", "handy", "student", "invarianten", "101500")
    b = bl.lauf_verzeichnis_fuer(tmp_path, "2026-10-05", "handy", "student", "invarianten", "101501")
    assert a != b
    assert a.name.startswith("2026-10-05-handy-student-invarianten")
