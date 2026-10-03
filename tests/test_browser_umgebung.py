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
