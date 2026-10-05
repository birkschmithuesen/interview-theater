"""Prompt-Abzug der Browser-Simulation: DB-Kopie, Aufruf im App-Checkout und
ein echter Abzug gegen den aktuellen ``kontext`` (ohne Netz, ohne Modell)."""

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from interview_theater import anweisungen, db, repo, workshop
from simulation import browser_umgebung, browser_wissen as bw, prompt_abzug


def test_kopiere_db_ist_eigenstaendig(tmp_path):
    quelle = tmp_path / "a.db"
    conn = sqlite3.connect(quelle)
    conn.execute("CREATE TABLE t (x)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()
    ziel = bw.kopiere_db(quelle, tmp_path / "b.db")
    assert sqlite3.connect(ziel).execute("SELECT x FROM t").fetchone() == (1,)
    assert ziel != quelle


def test_kopiere_db_nimmt_wal_inhalt_mit(tmp_path):
    quelle = tmp_path / "wal.db"
    offen = sqlite3.connect(quelle)
    offen.execute("PRAGMA journal_mode=WAL")
    offen.execute("CREATE TABLE t (x)")
    offen.execute("INSERT INTO t VALUES (42)")
    offen.commit()  # bleibt im -wal, solange die Verbindung offen ist
    try:
        ziel = bw.kopiere_db(quelle, tmp_path / "kopie.db")
        assert sqlite3.connect(ziel).execute("SELECT x FROM t").fetchone() == (42,)
    finally:
        offen.close()


def test_hole_prompt_ruft_abzug_im_app_checkout(tmp_path):
    aufrufe = []

    def ausfuehren(args, **kw):
        aufrufe.append((args, kw))
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"prompt": "SYSTEM\n\nNUTZER"}) + "\n", stderr="")

    db_pfad = tmp_path / "sim.db"
    sqlite3.connect(db_pfad).close()
    app = tmp_path / "app"
    app.mkdir()
    prompt = bw.hole_prompt(app_wurzel=app, env_datei=tmp_path / "x.env", db=db_pfad, chat_id=7,
                            text="Which terms?", arbeitsordner=tmp_path, ausfuehren=ausfuehren)
    assert prompt == "SYSTEM\n\nNUTZER"
    (args, kw), = aufrufe
    befehl = " ".join(args)
    assert "prompt_abzug" in befehl and "--chat-id" in befehl and "7" in befehl
    assert str(db_pfad) not in befehl  # gegen die Kopie, nie gegen die laufende DB
    assert kw.get("cwd") == app or str(app) in befehl
    for vorgabe in browser_umgebung.CODE_VORGABEN_ENTFERNEN:
        assert vorgabe in befehl


def test_hole_prompt_gibt_absoluten_kopiepfad_an_den_app_checkout(tmp_path, monkeypatch):
    """Der Abzug laeuft mit ``cwd=app_wurzel`` -- ein relativer Laufordner
    (``simulation/browser_laeufe/...`` aus ``main``) zeigte dort ins Leere,
    sobald ``--app-wurzel`` ein anderer Checkout ist."""
    aufrufe = []

    def ausfuehren(args, **kw):
        aufrufe.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"prompt": "P"}) + "\n", stderr="")

    harness = tmp_path / "harness"
    (harness / "lauf").mkdir(parents=True)
    sqlite3.connect(harness / "lauf" / "sim.db").close()
    app = tmp_path / "app"
    app.mkdir()
    monkeypatch.chdir(harness)
    bw.hole_prompt(app_wurzel=app, env_datei=tmp_path / "x.env", db=Path("lauf/sim.db"),
                   chat_id=7, text="x", arbeitsordner=Path("lauf"), ausfuehren=ausfuehren)
    args, = aufrufe
    assert f"--db {harness / 'lauf' / 'abzug-7.db'}" in " ".join(args)


def test_hole_prompt_fehler_wird_laut(tmp_path):
    def ausfuehren(args, **kw):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="Traceback ...")

    db_pfad = tmp_path / "sim.db"
    sqlite3.connect(db_pfad).close()
    with pytest.raises(RuntimeError, match="Traceback"):
        bw.hole_prompt(app_wurzel=tmp_path, env_datei=tmp_path / "x.env", db=db_pfad, chat_id=7,
                       text="x", arbeitsordner=tmp_path, ausfuehren=ausfuehren)


@pytest.fixture()
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


def test_abzug_echt_gegen_aktuellen_kontext(tmp_path, monkeypatch, capsys, padua):
    """In-process gegen den aktuellen Stand: Board-Begriff und Zugtext stehen
    im Prompt, die Original-DB bleibt unberuehrt (der Abzug schreibt nur in
    die Datei, die er bekommt -- im Lauf ist das die Kopie)."""
    monkeypatch.delenv("IT_DB", raising=False)
    pfad = tmp_path / "sim.db"
    chat_id, _ = browser_umgebung.baue_gruppe(str(pfad), "padua-browser-sim")
    conn = db.verbinde(str(pfad))
    repo.lege_begriffsboard_an(
        conn, chat_id,
        json.dumps([{"begriff": "windowsill", "status": "neu", "begruendung": ""}]), None, 0)
    conn.commit()
    conn.close()
    kopie = bw.kopiere_db(pfad, tmp_path / "kopie.db")

    rc = prompt_abzug.main(["--db", str(kopie), "--chat-id", str(chat_id), "--text", "hello zebra"])

    assert rc == 0
    zeile = capsys.readouterr().out.strip().splitlines()[-1]
    prompt = json.loads(zeile)["prompt"]
    assert "windowsill" in prompt
    assert "hello zebra" in prompt
    assert "\n\n" in prompt
    roh = sqlite3.connect(pfad)
    assert roh.execute("SELECT COUNT(*) FROM nachricht").fetchone()[0] == 0
