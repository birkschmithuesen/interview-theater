import json
from collections import Counter
from pathlib import Path

import pytest

INDEX = Path("docs/guide/bilder/index.json")


def test_leitbilder_klein_vollstaendig_und_hoechstens_fuenf_je_phase_und_geraet():
    if not INDEX.exists():
        pytest.skip("noch kein Schlusslauf")
    eintraege = json.loads(INDEX.read_text(encoding="utf-8"))
    assert eintraege
    for e in eintraege:
        datei = INDEX.parent / e["datei"]
        assert datei.exists(), e["datei"]
        assert datei.stat().st_size <= 400_000, e["datei"]
        assert e["geraet"] in {"handy", "laptop"} and e["unterschrift_en"]
    zahl = Counter((e["phase"], e["geraet"]) for e in eintraege)
    assert max(zahl.values()) <= 5
