"""Harness-Seite des Prompt-Abzugs: DB kopieren, Abzug im App-Checkout starten.

Der Abzug (``simulation/prompt_abzug.py``) laeuft als Kindprozess ueber
``browser_umgebung.bot_skript``: Env-Datei sourcen, Code-Vorgaben entfernen,
``PYTHONPATH=<app_wurzel>`` -- so baut der ``kontext`` des geprueften
App-Stands (auch cb200e4) den Prompt, nie der des Harness. Er bekommt immer
eine Kopie der Sim-DB, weil er die ausloesende Nachricht hineinschreibt.
"""

from __future__ import annotations

import json
import shlex
import sqlite3
import subprocess
from pathlib import Path

from simulation import browser_umgebung

ABZUG = Path(__file__).resolve().parent / "prompt_abzug.py"

#: Dieselben Werte wie der simulationseigene Bot (``bau_bot_skript``): das
#: Padua-Profil, der Bot-Name der Sim-Gruppe, keine Gruppenseiten-URL.
WORKSHOP = "padua-2026"
BOT_NAME = "padua-browser-sim"


def kopiere_db(quelle: Path, ziel: Path) -> Path:
    """Konsistente Kopie ueber die Backup-API -- nimmt auch den Inhalt einer
    noch nicht checkpointeten ``-wal``-Datei mit, ohne die Quelle zu sperren."""
    ziel = Path(ziel)
    ziel.unlink(missing_ok=True)
    alt = sqlite3.connect(f"file:{Path(quelle)}?mode=ro", uri=True, timeout=10)
    neu = sqlite3.connect(ziel)
    try:
        alt.backup(neu)
    finally:
        neu.close()
        alt.close()
    return ziel


def hole_prompt(*, app_wurzel: Path, env_datei: Path, db: Path, chat_id: int, text: str,
                arbeitsordner: Path, ausfuehren=subprocess.run) -> str:
    # Absolut: der Abzug laeuft mit ``cwd=app_wurzel`` (evtl. ein anderer
    # Checkout), ein relativer Pfad zeigte dort ins Leere.
    kopie = kopiere_db(db, Path(arbeitsordner).resolve() / f"abzug-{chat_id}.db")
    aufruf = (
        f"{shlex.quote(str(ABZUG))} --db {shlex.quote(str(kopie))} --chat-id {int(chat_id)} "
        f"--text {shlex.quote(text)} --workshop {WORKSHOP} --bot-name {BOT_NAME} --web-url ''"
    )
    skript = browser_umgebung.bot_skript(env_datei, modul_oder_datei=aufruf, app_wurzel=app_wurzel)
    ergebnis = ausfuehren(["bash", "-c", skript], cwd=app_wurzel, capture_output=True, text=True, timeout=120)
    if ergebnis.returncode != 0:
        raise RuntimeError(f"prompt_abzug fehlgeschlagen: {ergebnis.stderr[-2000:]}")
    zeilen = ergebnis.stdout.strip().splitlines()
    if not zeilen:
        raise RuntimeError(f"prompt_abzug ohne Ausgabe: {ergebnis.stderr[-2000:]}")
    return json.loads(zeilen[-1])["prompt"]
