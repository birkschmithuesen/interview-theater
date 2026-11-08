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
import re
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


# Sofortmassnahme in der Padua-Env seit 05.10.2026 08:33
# (IT_BEGRIFFSBOARD_MIN_ZEICHEN=100): das sind Code-VORGABEN, keine
# geheimen Werte -- wuerde das Wrapper-Skript sie aus der Env-Datei
# durchlassen, saehe die Simulation die neue Board-Schwelle nie, weil die
# Env-Datei sie nach dem ``source`` ueberschreibt. Deshalb werden sie nach
# dem ``source`` wieder entfernt: die Simulation soll den Code pruefen, der
# alten App ebenso wie der neuen.
CODE_VORGABEN_ENTFERNEN = (
    "IT_BEGRIFFSBOARD_MIN_ZEICHEN",
    "IT_BEGRIFFSBOARD_MIN_ABSTAND_S",
)

_KOPF = """\
set -euo pipefail
set -a
source "{env_datei}"
set +a
unset {vorgaben}
export PYTHONPATH="{app_wurzel}"
"""


def _kopf(env_datei, app_wurzel: Path) -> str:
    return _KOPF.format(
        env_datei=env_datei, vorgaben=" ".join(CODE_VORGABEN_ENTFERNEN),
        app_wurzel=app_wurzel,
    )


def bot_skript(env_datei, *, modul_oder_datei: str, app_wurzel: Path, py: str = PY) -> str:
    """Nur Text -- keine Ausfuehrung, kein Secret wird hier gelesen (siehe
    Moduldoc). Sourct die Env-Datei, entfernt danach die Code-Vorgaben
    (``CODE_VORGABEN_ENTFERNEN``) und fuehrt dann ``python
    MODUL_ODER_DATEI`` mit ``PYTHONPATH=app_wurzel`` aus -- so kann der
    Aufrufer wahlweise ``-m interview_theater.bot`` oder den Pfad eines
    Skripts (z. B. ``prompt_abzug.py``) aus einem beliebigen Checkout
    starten."""
    return f'{_kopf(env_datei, app_wurzel)}exec "{py}" -u {modul_oder_datei}\n'


_SZENE_MODELL_MUSTER = re.compile(r"[A-Za-z0-9._-]+")


def pruefe_szene_modell(name: str) -> str:
    """Nur Buchstaben, Ziffern, Punkt, Bindestrich, Unterstrich -- der Name
    landet in einem Bash-Skript (keine Shell-Einschleusung)."""
    if not isinstance(name, str) or not _SZENE_MODELL_MUSTER.fullmatch(name):
        raise ValueError(f"Unzulaessiger Szenenmodell-Name: {name!r}")
    return name


def bau_bot_skript(env_datei: str, db_pfad: str, audio_verz: str, chat_id: int,
                   py: str = PY, app_wurzel: Path = WURZEL,
                   szene_modell: str | None = None) -> str:
    """Der Wrapper fuer den simulationseigenen Web-Bot: baut auf
    ``bot_skript`` auf (dieselbe Code-Vorgaben-Bereinigung und
    ``PYTHONPATH``), dazu die eigenen -- nicht geheimen -- Werte fuer DB,
    Audio-Verzeichnis, Kanal und Chat-ID."""
    eigene = (
        f'export IT_DB="{db_pfad}"\n'
        f'export IT_AUDIO="{audio_verz}"\n'
        "export IT_KANAL=web\n"
        f'export IT_WEB_CHAT_ID="{chat_id}"\n'
        "export IT_WORKSHOP=padua-2026\n"
        "export IT_BOT_NAME=padua-browser-sim\n"
        'export IT_WEB_URL=""\n'
    )
    if szene_modell:
        eigene += f'export IT_SZENE_MODELL="{pruefe_szene_modell(szene_modell)}"\n'
    return f'{_kopf(env_datei, app_wurzel)}{eigene}exec "{py}" -u -m interview_theater.bot\n'


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


def starte_web(db_pfad: str, audio_verz: str, log_pfad: str, *,
               app_wurzel: Path = WURZEL):
    bind = f"127.0.0.1:{freier_port()}"
    umgebung = dict(os.environ)
    umgebung.update({
        "IT_DB": db_pfad, "IT_WEB_BIND": bind, "IT_WEB_PREFIX": "",
        "IT_AUDIO": audio_verz, "IT_WORKSHOP": "padua-2026",
        "IT_WEB_SEGMENT_MS": "45000", "PYTHONPATH": str(app_wurzel),
    })
    log = open(log_pfad, "w")
    prozess = subprocess.Popen(
        [PY, "-u", "-m", "interview_theater.web"],
        cwd=str(app_wurzel), env=umgebung, stdout=log, stderr=subprocess.STDOUT,
    )
    basis = f"http://{bind}"
    try:
        _warte_gesund(prozess, basis, log_pfad)
    except Exception:
        prozess.terminate()
        try:
            prozess.wait(timeout=5)
        except subprocess.TimeoutExpired:
            prozess.kill()
            prozess.wait()
        log.close()
        raise
    return prozess, log, basis


def starte_bot(env_datei: str, db_pfad: str, audio_verz: str, chat_id: int,
              log_pfad: str, *, app_wurzel: Path = WURZEL,
              szene_modell: str | None = None):
    skript = bau_bot_skript(env_datei, db_pfad, audio_verz, chat_id,
                            app_wurzel=app_wurzel, szene_modell=szene_modell)
    log = open(log_pfad, "w")
    prozess = subprocess.Popen(
        ["bash", "-c", skript], cwd=str(app_wurzel),
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "HOME": os.environ.get("HOME", "")},
        stdout=log, stderr=subprocess.STDOUT,
    )
    time.sleep(2.0)
    if prozess.poll() is not None:
        log.close()
        raise RuntimeError(f"Bot-Prozess sofort beendet, siehe {log_pfad}")
    return prozess, log


#: Phase-1/2-Ergebnis fuer einen Lauf, der in Phase 3 beginnt -- dieselben
#: erfundenen Werte wie scripts/fixture_padua_voll._STAND_JE_PHASE[1]/[2]
#: (dort ist es eine private Konstante, hier die oeffentliche Abschrift).
STAND_PHASE_1_2 = (
    ("begriffe", "arrival, waiting, strangers, noise, belonging, home, trust, family"),
    ("fragen", "1. What do you remember about your first day here?\n"
               "2. Where did you wait the longest in your life?\n"
               "3. When did a strange place start to feel like yours?"),
    ("interview_eroeffnung", "Hi, we are acting students from the academy. "
                             "Do you have ten minutes for three questions?"),
    ("interview_abschluss", "Thank you. Your answers stay anonymous and become "
                            "material for a fictional play."),
)


#: Phase-4-Ergebnis fuer einen Lauf, der in Phase 5 beginnt -- dieselben
#: erfundenen Werte wie ``scripts/fixture_padua_voll._STAND_JE_PHASE[4]``
#: (dort privat, hier die oeffentliche Abschrift), dazu ``szenen_anzahl``:
#: Padua fragt in Phase 4 nach der Anzahl Szenen (``phasen.voraussetzungen``),
#: die Fixture legt dort direkt die echten Szenenzeilen an und braucht das
#: Feld deshalb nicht -- der Startzustand hier schon, weil er KEINE
#: Szenenfolge-Vorschlagsrunde durchlaeuft.
STAND_PHASE_4 = (
    ("rahmen", "A railway station in a northern Italian city, one wet "
               "November evening. A young man has just arrived and waits "
               "for a cousin who does not come."),
    ("geschichte",
     "Samir waits on a bench with two bags, one of them broken. He "
     "rehearses how to order a coffee and never goes. The woman at the "
     "station cafe notices him. When his cousin finally arrives, the broken "
     "bag opens in the middle of the hall - and for the first time Samir "
     "laughs here."),
    ("szenen_anzahl", "3"),
)

#: Drei Figuren OHNE Sprachstil -- Abschrift der Namen/Beschreibungen aus
#: ``scripts/fixture_padua_voll._FIGUREN`` (dort privat), der dortige Stil je
#: Figur wird hier bewusst NICHT uebernommen: Fakt 2 (Plan) misst, dass die
#: Live-Phase-4 ``figur.sprachstil`` nicht setzt, und Phase 7
#: (``sprechweise.py``) soll im Lauf genau diese Luecke fuellen.
FIGUREN_PHASE_4 = (
    ("Samir", "just arrived, wants to arrive without asking anyone"),
    ("Elena", "runs the station cafe, sees everyone and says little"),
    ("Tommaso", "the cousin, late, embarrassed, overly cheerful"),
)

#: Drei Szenenzeilen mit Titel/``was_passiert``/Besetzung, OHNE Prosa --
#: Abschrift von ``scripts/fixture_padua_voll._SZENEN`` (dort privat), das
#: Prosa-Feld wird hier bewusst NICHT uebernommen: Phase 5 soll die Prosa im
#: Lauf selbst schreiben, nicht vorgefunden.
SZENEN_PHASE_4 = (
    (1, "The bench", "Samir waits and rehearses his order.", ("Samir",)),
    (2, "The cafe", "Elena watches him not coming in.", ("Samir", "Elena")),
    (3, "Socks on the floor", "Tommaso arrives, the bag opens.",
     ("Samir", "Tommaso", "Elena")),
)

#: Dasselbe Interviewmaterial wie ``scripts/fixture_padua_voll.INTERVIEW``,
#: hier absolut ueber ``WURZEL`` aufgeloest -- dieses Modul soll nicht davon
#: abhaengen, aus welchem Verzeichnis der Harness gestartet wird.
INTERVIEW = WURZEL / "simulation" / "interviews" / "set1" / "2-ferzan-bahnhof.md"

#: Die zwei woertlichen, im Transkript stehenden Zitate -- dieselben wie in
#: ``scripts/fixture_padua_voll._material`` (dort privat).
_ZITATE_INTERVIEW = (
    "Ich habe drei Stunden auf dieser Bank gesessen und nichts gegessen.",
    "Der Lautsprecher hat geredet und ich habe kein einziges Wort verstanden.",
)


def _material(conn, chat_id: int) -> int:
    """Ein verdichtetes Interview mit zwei geprueften Zitaten -- derselbe Weg
    wie ``scripts/fixture_padua_voll._material`` (dort privat)."""
    roh = INTERVIEW.read_text(encoding="utf-8")
    transkript = roh.split("---", 2)[2].strip()
    assert all(z in transkript for z in _ZITATE_INTERVIEW), \
        "Interviewmaterial passt nicht"
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, 5, "lang", "text", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, transkript)
    repo.speichere_verdichtung(
        conn, chat_id, aufnahme_id,
        "The interviewee remembers his first day: three hours on a station "
        "bench with a broken bag, waiting for a cousin, too unsure to buy "
        "food, unable to understand the announcements.",
        [
            {"thema": "waiting", "beleg_zitat": _ZITATE_INTERVIEW[0],
             "zitat_geprueft": 1, "kurz": "three hours on the bench"},
            {"thema": "noise", "beleg_zitat": _ZITATE_INTERVIEW[1],
             "zitat_geprueft": 1, "kurz": "the loudspeaker"},
        ],
    )
    return aufnahme_id


def bereite_vor(db_pfad: str, chat_id: int, *, startphase: int) -> None:
    """Fuellt fuer ``startphase > 1`` den Stand der Phasen davor und laesst
    die Gruppe in ``startphase - 1`` stehen -- den Wechsel selbst macht
    ``browser_lauf.main`` ueber den echten Endpunkt (Eintrittsnachricht wie
    live). Gebaut: 3 (zeichengleich zum bisherigen Weg) und 5 (Task 1,
    BRIEF p57); andere Werte sind ein ValueError.

    Padua (``workshop/padua-2026/profil.toml``, ``[fragen_weich] aktiv =
    false``) braucht fuer ``phasen.voraussetzungen()[3]`` NICHT zusaetzlich
    ``fragen_weich``/``frage_einleitungen`` -- die Bedingung
    ``not workshop.fragen_weich_aktiv() or geprueft(...)`` ist mit
    ``fragen_weich_aktiv() == False`` schon erfuellt.

    ``startphase=5`` baut zusaetzlich den Phase-4-Stand (Setting,
    Geschichte, Szenenzahl), ein verdichtetes Interview (``_material``), drei
    Figuren ohne Sprachstil und drei Szenenzeilen ohne Prosa -- die Gruppe
    bleibt dabei in Phase 4 stehen (``phasen.voraussetzungen()[5]`` wird
    erfuellt, der Sprung selbst bleibt dem echten Endpunkt vorbehalten)."""
    if startphase <= 1:
        return
    if startphase not in (3, 5):
        raise ValueError(f"startphase {startphase} nicht gebaut")
    conn = db.verbinde(db_pfad)
    try:
        for feld, wert in STAND_PHASE_1_2:
            repo.setze_arbeitsstand(conn, chat_id, feld, wert)
        if startphase == 3:
            repo.setze_phase(conn, chat_id, 2)
            conn.commit()
            return
        for feld, wert in STAND_PHASE_4:
            repo.setze_arbeitsstand(conn, chat_id, feld, wert)
        repo.setze_arbeitsstand(conn, chat_id, "figuren_fixiert_am", repo._jetzt())
        _material(conn, chat_id)
        figuren = {}
        for name, beschreibung in FIGUREN_PHASE_4:
            repo.setze_figur(conn, chat_id, name, beschreibung)
            figuren[name] = repo.hole_figur(conn, chat_id, name)["id"]
        for nummer, titel, was_passiert, besetzung in SZENEN_PHASE_4:
            szene_id = repo.lege_szene_an(conn, chat_id, nummer, titel, was_passiert, None)
            repo.setze_szenenfeld(conn, szene_id, "was_passiert", was_passiert)
            repo.setze_szene_figuren(
                conn, chat_id, szene_id, [figuren[n] for n in besetzung])
        repo.setze_phase(conn, chat_id, 4)
        conn.commit()
    finally:
        conn.close()


@dataclass
class Gruppe:
    token: str
    chat_id: int


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
    gruppen: list[Gruppe]

    def beende(self) -> None:
        for prozess in (self.bot_prozess, self.web_prozess):
            prozess.terminate()
        for prozess in (self.bot_prozess, self.web_prozess):
            try:
                prozess.wait(timeout=10)
            except subprocess.TimeoutExpired:
                prozess.kill()
                try:
                    prozess.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        self.web_log.close()
        self.bot_log.close()


def starte_stack(env_datei: str, lauf_verzeichnis: Path, *,
                 app_wurzel: Path = WURZEL, gruppen: int = 1, startphase: int = 1,
                 szene_modell: str | None = None) -> Stack:
    """Baut den Stack aus ``app_wurzel`` (Vorgabe: dieser Checkout) --
    ``app_wurzel`` kann ein anderer Checkout sein (z. B. der alte Stand vor
    einem Live-Befund), um die alte App mit dem neuen Harness laufen zu
    lassen. ``gruppen`` legt mehrere Web-Gruppen in derselben ``sim.db`` an
    (``baue_gruppe`` laeuft dafuer in-process weiter gegen den Harness --
    das additive Schema vertraegt die alte wie die neue App); Web- und
    Bot-Prozess laufen weiter fuer die ERSTE Gruppe, wie bisher.

    Der Laufordner wird absolut gemacht: Web und Bot laufen mit
    ``cwd=app_wurzel`` -- ein relativer Pfad liesse sie bei einem anderen
    Checkout eine fremde, leere ``sim.db`` oeffnen.

    ``startphase`` (Task 2, ``browser_stationen.STARTPHASE``) fuellt per
    ``bereite_vor`` den Stand der Phasen davor in der ERSTEN Gruppe, BEVOR
    Web und Bot starten -- den tatsaechlichen Phasenwechsel macht erst
    ``browser_lauf.main`` ueber den echten Endpunkt."""
    lauf_verzeichnis = Path(lauf_verzeichnis).resolve()
    db_pfad = str(lauf_verzeichnis / "sim.db")
    audio_verz = str(lauf_verzeichnis / "audio")
    os.makedirs(audio_verz, exist_ok=True)
    gruppen_liste = []
    for i in range(gruppen):
        name = "padua-browser-sim" if i == 0 else f"padua-browser-sim-{i + 1}"
        chat_id, token = baue_gruppe(db_pfad, name)
        gruppen_liste.append(Gruppe(token=token, chat_id=chat_id))
    bereite_vor(db_pfad, gruppen_liste[0].chat_id, startphase=startphase)
    web_prozess, web_log, web_basis = starte_web(
        db_pfad, audio_verz, str(lauf_verzeichnis / "web.log"), app_wurzel=app_wurzel)
    bot_prozess, bot_log = starte_bot(
        env_datei, db_pfad, audio_verz, gruppen_liste[0].chat_id,
        str(lauf_verzeichnis / "bot.log"), app_wurzel=app_wurzel,
        szene_modell=szene_modell)
    return Stack(db_pfad, audio_verz, gruppen_liste[0].chat_id, gruppen_liste[0].token,
                web_basis, web_prozess, bot_prozess, web_log, bot_log, gruppen_liste)
