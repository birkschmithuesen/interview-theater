import wave

import pytest

from simulation import diskussionen as d
from simulation import erzeuge_diskussion_audio as audio


def test_registry_und_dateien():
    assert {"lang", "knapp", "verhoerer", "nachtrag"} <= set(d.DISKUSSIONEN)
    for disk in d.DISKUSSIONEN.values():
        assert disk.datei.is_file(), disk.datei


def test_knapp_liegt_unter_der_alten_schwelle():
    assert d.DISKUSSIONEN["knapp"].zeichen() < 300
    assert d.DISKUSSIONEN["knapp"].ende_pause_s >= 6.0  # leeres Ende-Segment provozieren


def test_verhoerer_skript_ist_lang_und_traegt_kontext():
    disk = d.DISKUSSIONEN["verhoerer"]
    assert disk.zeichen() > 600
    assert disk.verhoerer == {"night shed": "night shift"}
    assert "night shed" in disk.text().casefold() and "night shift" in disk.text().casefold()


def test_text_ohne_sprecherpraefix():
    assert not d.DISKUSSIONEN["knapp"].text().startswith("A:")


@pytest.mark.skipif(not audio.verfuegbar(), reason="espeak-ng fehlt")
def test_endpause_verlaengert_die_datei(tmp_path):
    ohne = audio.erzeuge(d.DISKUSSIONEN["nachtrag"].datei, tmp_path / "a.wav")
    mit = audio.erzeuge(d.DISKUSSIONEN["nachtrag"].datei, tmp_path / "b.wav", ende_pause_s=6.0)
    assert audio.dauer_s(mit) - audio.dauer_s(ohne) == pytest.approx(6.0, abs=0.2)
