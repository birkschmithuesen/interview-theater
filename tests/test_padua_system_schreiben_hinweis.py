"""P57 Lauf 2 A3: der Systemprompt schickte auf den Knopf "Geschichte
schreiben" bzw. "Write the story", den es in Padua Phase 5/6 nicht gibt --
das Modell improvisierte ("tap 5 in the numbered bar"). Padua bekommt einen
eigenen Baustein ``schreiben_hinweis``; der Dortmund-Wortlaut bleibt."""

import pytest

from interview_theater import anweisungen, sprache, workshop


def _flach(text: str) -> str:
    return " ".join(text.split())


def _profil(monkeypatch, name):
    if name is None:
        monkeypatch.delenv(workshop.VARIABLE, raising=False)
    else:
        monkeypatch.setenv(workshop.VARIABLE, name)
    workshop.vergiss()
    sprache.vergiss()


@pytest.fixture(autouse=True)
def _aufraeumen():
    yield
    workshop.vergiss()
    sprache.vergiss()


@pytest.mark.parametrize("phase", [5, 6])
def test_padua_nennt_keinen_nichtvorhandenen_knopf(monkeypatch, phase):
    _profil(monkeypatch, "padua-2026")
    text = _flach(anweisungen.system(phase=phase))
    assert "Write the story" not in text
    assert "Geschichte schreiben" not in text
    assert "{{schreiben_hinweis}}" not in text
    assert "do not announce or promise a writing button" in text
    assert "shows it itself" in text
    assert "Yes, save" in text
    # der echte Ablauf
    assert "drafted as prose automatically" in text
    assert "Script tab" in text


def test_dortmund_text_bleibt_unveraendert(monkeypatch):
    _profil(monkeypatch, "dortmund-2026")
    text = _flach(anweisungen.system(phase=6))
    assert 'verweist du auf den Knopf "Geschichte schreiben"' in text
    assert "{{schreiben_hinweis}}" not in text


def test_englische_vorgabe_ohne_profil_behaelt_den_knopf(monkeypatch):
    _profil(monkeypatch, None)
    assert "{{schreiben_hinweis}}" not in anweisungen.system(phase=6)
