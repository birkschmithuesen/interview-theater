"""Der echte Stack fuer den Browserlauf: Web-Server + EIN Web-Bot-Prozess
gegen eine Wegwerf-Datenbank (Padua-UX-Simulation, 2026-10-03).

Betrieb (``betrieb/padua.db``, Units, Ports 8010/8030) wird nie beruehrt --
dieses Modul startet zwei eigene Prozesse auf freien Ports gegen eine
temporaere Datenbank und legt die eine Web-Gruppe darin selbst an (wie
``scripts/web_gruppe.py``, aber ohne eine Env-Datei zu lesen -- das macht
hier allein das generierte Bash-Skript, als Kindprozess).

Die echten Modell-Zugangsdaten (IT_LLM_*, IT_STT_*, IT_SZENE_*) werden NIE
von Python gelesen: ``bau_bot_skript`` erzeugt nur TEXT (eine ``source``-
Zeile mit dem Dateipfad, keine Werte), und erst die Bash-Shell des
Kindprozesses fuellt daraus ihre eigene Umgebung. Dieser Python-Prozess
sieht die Werte nie, kann sie also auch nie loggen oder committen.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from interview_theater import db, repo

WURZEL = Path(__file__).resolve().parent.parent
PY = sys.executable


def freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def baue_gruppe(db_pfad: str, bot_name: str) -> tuple[int, str]:
    """Legt die eine Web-Gruppe an -- derselbe Weg wie
    ``scripts/web_gruppe.lege_an``, hier direkt ueber ``repo``."""
    conn = db.verbinde(db_pfad)
    try:
        db.initialisiere(conn)
        chat_id = repo.naechste_web_chat_id(conn)
        repo.sichere_gruppe(conn, chat_id, bot_name, "Padua UX-Simulation")
        repo.setze_gruppe_kanal(conn, chat_id, "web")
        repo.setze_update_id(conn, bot_name, 0)
        token = repo.stelle_web_token_sicher(conn, chat_id)
        conn.commit()
    finally:
        conn.close()
    return chat_id, token


_BOT_SKRIPT = """\
set -euo pipefail
set -a
source "{env_datei}"
set +a
export IT_DB="{db_pfad}"
export IT_AUDIO="{audio_verz}"
export IT_KANAL=web
export IT_WEB_CHAT_ID="{chat_id}"
export IT_WORKSHOP=padua-2026
export IT_BOT_NAME=padua-browser-sim
export IT_WEB_URL=""
exec "{py}" -u -m interview_theater.bot
"""


def bau_bot_skript(env_datei: str, db_pfad: str, audio_verz: str,
                   chat_id: int, py: str = PY) -> str:
    """Nur Text -- keine Ausfuehrung, kein Secret wird hier gelesen."""
    return _BOT_SKRIPT.format(
        env_datei=env_datei, db_pfad=db_pfad, audio_verz=audio_verz,
        chat_id=chat_id, py=py,
    )


def _warte_gesund(prozess, basis: str, log_pfad: str, sekunden: float = 20.0) -> None:
    ende = time.time() + sekunden
    while time.time() < ende:
        if prozess.poll() is not None:
            raise RuntimeError(f"Webserver abgestuerzt, siehe {log_pfad}")
        try:
            with urllib.request.urlopen(f"{basis}/gesund", timeout=1) as a:
                if a.read().decode().strip() == "ok":
                    return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Webserver nicht erreichbar, siehe {log_pfad}")


def starte_web(db_pfad: str, audio_verz: str, log_pfad: str):
    bind = f"127.0.0.1:{freier_port()}"
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": db_pfad, "IT_WEB_BIND": bind, "IT_WEB_PREFIX": "",
        "IT_AUDIO": audio_verz, "IT_WORKSHOP": "padua-2026",
        "IT_WEB_SEGMENT_MS": "45000", "PYTHONPATH": str(WURZEL),
    })
    log = open(log_pfad, "w")
    prozess = subprocess.Popen(
        [PY, "-u", "-m", "interview_theater.web"],
        cwd=str(WURZEL), env=umgebung, stdout=log, stderr=subprocess.STDOUT,
    )
    basis = f"http://{bind}"
    try:
        _warte_gesund(prozess, basis, log_pfad)
    except Exception:
        prozess.terminate()
        log.close()
        raise
    return prozess, log, basis


def starte_bot(env_datei: str, db_pfad: str, audio_verz: str, chat_id: int,
              log_pfad: str):
    skript = bau_bot_skript(env_datei, db_pfad, audio_verz, chat_id)
    log = open(log_pfad, "w")
    prozess = subprocess.Popen(
        ["bash", "-c", skript], cwd=str(WURZEL),
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "HOME": os.environ.get("HOME", "")},
        stdout=log, stderr=subprocess.STDOUT,
    )
    time.sleep(2.0)
    if prozess.poll() is not None:
        log.close()
        raise RuntimeError(f"Bot-Prozess sofort beendet, siehe {log_pfad}")
    return prozess, log


@dataclass
class Stack:
    db_pfad: str
    audio_verz: str
    chat_id: int
    token: str
    web_basis: str
    web_prozess: subprocess.Popen
    bot_prozess: subprocess.Popen
    web_log: object
    bot_log: object

    def beende(self) -> None:
        for prozess in (self.bot_prozess, self.web_prozess):
            prozess.terminate()
        for prozess in (self.bot_prozess, self.web_prozess):
            try:
                prozess.wait(timeout=10)
            except subprocess.TimeoutExpired:
                prozess.kill()
        self.web_log.close()
        self.bot_log.close()


def starte_stack(env_datei: str, lauf_verzeichnis: Path) -> Stack:
    db_pfad = str(lauf_verzeichnis / "sim.db")
    audio_verz = str(lauf_verzeichnis / "audio")
    os.makedirs(audio_verz, exist_ok=True)
    chat_id, token = baue_gruppe(db_pfad, "padua-browser-sim")
    web_prozess, web_log, web_basis = starte_web(
        db_pfad, audio_verz, str(lauf_verzeichnis / "web.log"))
    bot_prozess, bot_log = starte_bot(
        env_datei, db_pfad, audio_verz, chat_id,
        str(lauf_verzeichnis / "bot.log"))
    return Stack(db_pfad, audio_verz, chat_id, token, web_basis,
                web_prozess, bot_prozess, web_log, bot_log)
