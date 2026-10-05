import wave
from pathlib import Path

from simulation import browser_probe as bp


def _wav(pfad: Path, sekunden: float, rate=8000):
    with wave.open(str(pfad), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\0\0" * int(rate * sekunden))


def test_schneide_kappt_auf_sekunden(tmp_path):
    _wav(tmp_path / "a.wav", 5.0)
    assert bp.schneide(tmp_path / "a.wav", tmp_path / "b.wav", 2.0) == 2.0
    with wave.open(str(tmp_path / "b.wav")) as w:
        assert w.getnframes() == 16000


def test_begriffe_gefunden():
    assert bp.begriffe_gefunden("We said Home and the night shift.",
                                ["home", "border", "night shift"]) == ["home", "night shift"]


def test_chromium_argumente_ohne_schleife(tmp_path):
    args = bp.chromium_argumente(tmp_path / "d.wav")
    assert "--use-fake-ui-for-media-stream" in args
    assert "--use-fake-device-for-media-stream" in args
    assert args[-1] == f"--use-file-for-fake-audio-capture={tmp_path / 'd.wav'}%noloop"
    assert bp.chromium_argumente(tmp_path / "d.wav", schleife=True)[-1].endswith("d.wav")
