import wave
from pathlib import Path

import pytest

from simulation import erzeuge_diskussion_audio as e

SKRIPT = Path("simulation/diskussion/p1-diskussion.txt")


def test_skript_hat_vier_sprecher_und_genug_text():
    zeilen = e.lies_skript(SKRIPT)
    assert {s for s, _ in zeilen} == {"A", "B", "C", "D"}
    text = " ".join(t for _, t in zeilen)
    assert len(text) >= 1200                       # brainstorm.VORGABE_MIN_ZEICHEN
    for begriff in ("home", "border", "waiting", "belonging", "night shift"):
        assert text.lower().count(begriff) >= 3


def test_plan_ist_deterministisch_mit_pausen():
    zeilen = e.lies_skript(SKRIPT)
    plan1, plan2 = e.plane(zeilen), e.plane(zeilen)
    assert plan1 == plan2
    assert all(1.5 <= pause <= e.LANGE_PAUSE_S for _, _, pause in plan1)
    assert {stimme for stimme, _, _ in plan1} == set(e.STIMMEN.values())


def test_mindestens_zwei_pausen_ueberschreiten_die_vad_schwelle():
    """Abnahme P1-2, Fortsetzung (Robo, gegen eine echte sim.db-Kopie
    diagnostiziert): keines der sieben echten Diskussionssegmente hatte
    ``schnittgrund='pause'`` -- die kurzen 1.5-3.0s-Pausen zwischen den
    Zeilen lagen alle UNTER der clientseitigen VAD-Schwelle
    (``IT_WEB_VAD_PAUSE_MS``, Vorgabe 2500ms, ``web_chat.py``). Ohne eine
    Stille, die laenger ist als diese Schwelle, kann die live wachsende
    Begriffsboard-Karte (reason='pause') nie ausgeloest werden."""
    zeilen = e.lies_skript(SKRIPT)
    plan = e.plane(zeilen)
    lange = [p for _, _, p in plan if p >= e.LANGE_PAUSE_S]
    assert len(lange) >= 2
    assert all(p > e.VAD_PAUSE_SCHWELLE_S for p in lange)


def test_erzeugt_eine_wav_von_mindestens_zwei_minuten(tmp_path):
    pytest.importorskip("espeakng_loader")
    ziel = tmp_path / "d.wav"
    wav = e.erzeuge(SKRIPT, ziel)
    sekunden = e.dauer_s(wav)
    assert sekunden >= 120
    with wave.open(str(wav)) as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        assert abs(w.getnframes() / w.getframerate() - sekunden) < 0.5
