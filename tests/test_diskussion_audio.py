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
    assert all(1.5 <= pause <= 3.0 for _, _, pause in plan1)
    assert {stimme for stimme, _, _ in plan1} == set(e.STIMMEN.values())


def test_erzeugt_eine_wav_von_mindestens_zwei_minuten(tmp_path):
    pytest.importorskip("espeakng_loader")
    ziel = tmp_path / "d.wav"
    sekunden = e.erzeuge(SKRIPT, ziel)
    assert sekunden >= 120
    with wave.open(str(ziel)) as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        assert abs(w.getnframes() / w.getframerate() - sekunden) < 0.5
