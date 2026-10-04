"""Der Profilschalter der read-only Werkbank (Padua, 03.10.2026)."""

import pytest

from interview_theater import sprache, workshop


@pytest.fixture
def profil(monkeypatch):
    def setze(name):
        if name is None:
            monkeypatch.delenv(workshop.VARIABLE, raising=False)
        else:
            monkeypatch.setenv(workshop.VARIABLE, name)
        workshop.vergiss()
        sprache.vergiss()
    yield setze
    workshop.vergiss()
    sprache.vergiss()


def test_die_vorgabe_traegt_den_schluessel():
    assert workshop.VORGABE_WERTE["web"]["workbench_bearbeitbar"] is True


@pytest.mark.parametrize("name, erwartet", [
    (None, True), ("dortmund-2026", True), ("padua-2026", False),
])
def test_der_schalter_je_profil(profil, name, erwartet):
    profil(name)
    assert workshop.workbench_bearbeitbar() is erwartet
