"""Erzeugt die Diskussions-WAV fuer den Abnahmelauf P1-2 offline mit
espeak-ng (PyPI ``espeakng_loader``, bringt libespeak-ng und Daten mit).
Kein Netz-TTS: von diesem Rechner ist keins erreichbar (edge-tts lief am
04.10.2026 in den Timeout). Nur Simulation -- nie aus ``interview_theater/``
importieren. Ausgabe gehoert ins gitignorte Laufverzeichnis."""

from __future__ import annotations

import ctypes
import sys
import wave
from pathlib import Path

STIMMEN = {"A": "en-gb+m3", "B": "en-us+f2", "C": "en-gb+f4", "D": "en-us+m5"}
_AUDIO_OUTPUT_SYNCHRONOUS = 0x02
_POS_CHARACTER = 1
_ESPEAK_CHARS_UTF8 = 1
_ESPEAK_RATE = 1
_WOERTER_JE_MINUTE = 130
_PAUSEN = (1.5, 2.25, 3.0, 1.8, 2.6)

#: Die clientseitige VAD-Pausenschwelle (``IT_WEB_VAD_PAUSE_MS``, Vorgabe
#: 2500ms, ``interview_theater/web_chat.py``) -- hier als dokumentierter
#: Wert dupliziert, nicht importiert (reine Simulation, kein
#: Produktivimport noetig). Abnahme P1-2, Fortsetzung (Robo-Diagnose gegen
#: eine echte sim.db-Kopie): keines der sieben echten Segmente hatte
#: ``schnittgrund='pause'`` -- alle bisherigen Zeilenpausen (1.5-3.0s) lagen
#: darunter, die Begriffsboard-Karte reagiert aber nur auf einen
#: Pausen-Schnitt (oder auf "Discussion done", siehe browser_stationen.py).
VAD_PAUSE_SCHWELLE_S = 2.5
#: Deutlich ueber der Schwelle, mit Sicherheitsabstand.
LANGE_PAUSE_S = 4.0
#: Drei Stellen im 24-zeiligen Skript, an denen eine lange Stille die
#: Pause ueberschreibt -- verteilt, nicht gehaeuft, damit auch ein
#: laufender Pausen-Schnitt mitten in der Diskussion entsteht, nicht nur am
#: Ende.
_LANGE_PAUSE_INDIZES = (6, 13, 19)


def lies_skript(pfad: Path) -> list[tuple[str, str]]:
    zeilen = []
    for roh in Path(pfad).read_text(encoding="utf-8").splitlines():
        roh = roh.strip()
        if not roh or roh.startswith("#") or ":" not in roh:
            continue
        sprecher, text = roh.split(":", 1)
        zeilen.append((sprecher.strip(), text.strip()))
    return zeilen


def plane(zeilen: list[tuple[str, str]]) -> list[tuple[str, str, float]]:
    plan = []
    for i, (s, t) in enumerate(zeilen):
        pause = LANGE_PAUSE_S if i in _LANGE_PAUSE_INDIZES else _PAUSEN[i % len(_PAUSEN)]
        plan.append((STIMMEN[s], t, pause))
    return plan


def _espeak():
    import espeakng_loader

    lib = ctypes.cdll.LoadLibrary(str(espeakng_loader.get_library_path()))
    rate = lib.espeak_Initialize(_AUDIO_OUTPUT_SYNCHRONOUS, 0,
                                 str(espeakng_loader.get_data_path()).encode(), 0)
    if rate <= 0:
        raise RuntimeError("espeak_Initialize fehlgeschlagen")
    return lib, rate


def erzeuge(skript: Path, ziel: Path) -> float:
    lib, rate = _espeak()
    puffer: list[bytes] = []
    callback_typ = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short),
                                    ctypes.c_int, ctypes.c_void_p)

    def _sammle(wav, anzahl, _ereignisse):
        if wav and anzahl > 0:
            puffer.append(ctypes.string_at(wav, anzahl * 2))
        return 0

    rueckruf = callback_typ(_sammle)       # Referenz halten, sonst GC
    lib.espeak_SetSynthCallback(rueckruf)
    lib.espeak_SetParameter(_ESPEAK_RATE, _WOERTER_JE_MINUTE, 0)
    frames = bytearray()
    for stimme, text, pause in plane(lies_skript(skript)):
        lib.espeak_SetVoiceByName(stimme.encode())
        puffer.clear()
        roh = text.encode("utf-8") + b"\0"
        lib.espeak_Synth(roh, len(roh), 0, _POS_CHARACTER, 0, _ESPEAK_CHARS_UTF8, None, None)
        frames += b"".join(puffer) + b"\0\0" * int(rate * pause)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(ziel), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return len(frames) / 2 / rate


if __name__ == "__main__":
    ziel = Path(sys.argv[1])
    sekunden = erzeuge(Path(__file__).parent / "diskussion" / "p1-diskussion.txt", ziel)
    print(f"{ziel}: {sekunden:.1f} s")
