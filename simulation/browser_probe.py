"""Billige Probe vor dem eigentlichen Stationen-Motor (Padua-Browserlauf,
2026-10-04): prueft zwei Annahmen, bevor ein teurer Lauf gebaut wird --
(1) nimmt Chromium mit den Fake-Media-Flags wirklich eine WAV-Datei als
Mikrofon ab, (2) liefert Whisper fuer einen 60-Sekunden-Ausschnitt der
erfundenen Diskussion die erwarteten Begriffe zurueck.

Nur Simulation -- nie aus ``interview_theater/`` importieren. Wie
``browser_umgebung.py`` werden echte Zugangsdaten (IT_STT_*, IT_LLM_*) NIE
von diesem Python-Prozess gelesen: ``_WHISPER_SKRIPT`` ist nur TEXT (eine
``source``-Zeile mit dem Dateipfad), ausgefuehrt in einer Bash-Kindshell,
die ihre eigene Umgebung daraus befuellt. Dieser Prozess sieht die Werte
nie und kann sie also auch nie loggen oder committen.
"""

from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path
from typing import Iterable

WURZEL = Path(__file__).resolve().parent.parent
PY = sys.executable

_AUSSCHNITT_SEKUNDEN = 60.0

_WHISPER_SKRIPT = """\
set -euo pipefail
set -a
source "{env_datei}"
set +a
exec "{py}" -u -m simulation.browser_probe _whisper_kind "{ausschnitt}"
"""


def schneide(quelle: Path, ziel: Path, sekunden: float) -> float:
    """Kappt ``quelle`` auf die ersten ``sekunden`` und schreibt ``ziel``.
    Reine Funktion, nur ``wave`` -- liefert die tatsaechliche Laenge."""
    with wave.open(str(quelle), "rb") as q:
        rate = q.getframerate()
        kanaele = q.getnchannels()
        breite = q.getsampwidth()
        anzahl = min(q.getnframes(), int(rate * sekunden))
        frames = q.readframes(anzahl)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(ziel), "wb") as z:
        z.setnchannels(kanaele)
        z.setsampwidth(breite)
        z.setframerate(rate)
        z.writeframes(frames)
    return anzahl / rate


def begriffe_gefunden(transkript: str, begriffe: Iterable[str]) -> list[str]:
    """Welche ``begriffe`` kommen (casefold, als Teilstring) im Transkript
    vor -- reine Funktion, Reihenfolge wie in ``begriffe``."""
    text = transkript.casefold()
    return [b for b in begriffe if b.casefold() in text]


def chromium_argumente(wav: Path, schleife: bool = False) -> list[str]:
    """Die drei Fake-Media-Flags fuer einen Chromium-Start mit ``wav`` als
    Mikrofoneingang. Ohne ``schleife`` endet die Wiedergabe nach einmal
    Abspielen (``%noloop``), damit eine Aufnahme nicht endlos weiterlaeuft."""
    pfad = f"--use-file-for-fake-audio-capture={wav}"
    if not schleife:
        pfad += "%noloop"
    return [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        pfad,
    ]


def _starte_web_fuer_probe() -> None:
    """CLI-Zweig ``mikro``: startet NUR den Webserver (kein Bot-Prozess) auf
    einer Wegwerf-Datenbank -- fuer eine Hand-Probe mit einem echten Browser
    und den Flags aus ``chromium_argumente``. Kein Env-Datei-Zugriff hier."""
    import tempfile

    from simulation import browser_umgebung as u

    with tempfile.TemporaryDirectory() as lauf:
        lauf_pfad = Path(lauf)
        db_pfad = str(lauf_pfad / "probe.db")
        audio_verz = str(lauf_pfad / "audio")
        chat_id, token = u.baue_gruppe(db_pfad, "padua-browser-probe")
        prozess, log, basis = u.starte_web(db_pfad, audio_verz,
                                           str(lauf_pfad / "web.log"))
        print(f"Webserver: {basis}  Gruppe: {basis}/g/{token}")
        print("Strg+C zum Beenden.")
        try:
            prozess.wait()
        except KeyboardInterrupt:
            prozess.terminate()
            prozess.wait(timeout=5)
        finally:
            log.close()


def _starte_whisper_probe(env_datei: str, wav: str) -> None:
    """CLI-Zweig ``whisper``: schneidet 60 s und reicht an eine Bash-
    Kindshell weiter, die die Env-Datei selbst einliest (wie
    ``browser_umgebung.bau_bot_skript``) -- dieser Prozess liest sie nie."""
    import tempfile

    with tempfile.TemporaryDirectory() as lauf:
        ausschnitt = str(Path(lauf) / "ausschnitt.wav")
        sekunden = schneide(Path(wav), Path(ausschnitt), _AUSSCHNITT_SEKUNDEN)
        print(f"Ausschnitt: {sekunden:.1f} s -> {ausschnitt}")
        skript = _WHISPER_SKRIPT.format(env_datei=env_datei, py=PY,
                                        ausschnitt=ausschnitt)
        subprocess.run(["bash", "-c", skript], cwd=str(WURZEL), check=True)


def _whisper_kind(ausschnitt: str) -> None:
    """Laeuft NUR in der Bash-Kindshell, die die Env-Datei schon per
    ``source`` geladen hat -- liest also echte Zugangsdaten aus der
    Prozessumgebung, nie aus einer Datei. Gibt NIE den Transkripttext aus,
    nur die gefundenen Begriffe und seine Laenge."""
    import httpx

    from interview_theater import einstellungen, stt

    begriffe = ["home", "border", "waiting", "belonging", "night shift",
                "noise", "language"]
    e = einstellungen.laden()
    with httpx.Client() as klient:
        transkript = stt.transkribiere(e, klient, Path(ausschnitt), 120.0)
    gefunden = begriffe_gefunden(transkript, begriffe)
    print(f"Transkriptlaenge: {len(transkript)} Zeichen")
    print(f"Begriffe gefunden: {gefunden}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "mikro":
        _starte_web_fuer_probe()
    elif len(sys.argv) >= 4 and sys.argv[1] == "whisper":
        _starte_whisper_probe(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 3 and sys.argv[1] == "_whisper_kind":
        _whisper_kind(sys.argv[2])
    else:
        print("Nutzung: python -m simulation.browser_probe mikro", file=sys.stderr)
        print("     oder python -m simulation.browser_probe whisper <env-datei> <wav>",
              file=sys.stderr)
        sys.exit(1)
