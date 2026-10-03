"""Task 4 (Padua Phase 1+2 Umbau, 03.10.2026): der ``diskussion_knopf`` im
Poll-Feld von ``web_daten.web_chatzustand`` -- dieselbe Bauart wie
``brainstorm_knopf`` (``tests/test_web_chat_brainstorm_knopf.py``), aber mit
einer zweiten Bedingung: Phase 1 **und** das aktive Profil hat
``[diskussion] aktiv = true``. Beide Bedingungen muessen unabhaengig
voneinander greifen -- Phase 1 ohne die Profilzeile bleibt false (Dortmund),
eine andere Phase mit der Profilzeile bleibt ebenfalls false."""

import pytest

from interview_theater import db, repo, web_daten, workshop

CHAT = 7_000_000_000_003


@pytest.fixture
def datenbank(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Die Ankommenden")
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    token = repo.stelle_web_token_sicher(conn, CHAT)
    conn.commit()
    conn.close()
    return pfad, token


def _zustand(pfad, token, phase=None):
    schreibend = db.verbinde(pfad)
    if phase is not None:
        repo.setze_phase(schreibend, CHAT, phase)
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        return web_daten.web_chatzustand(lesend, token)
    finally:
        lesend.close()


def test_phase_1_und_profilflag_an_ergibt_wahr(datenbank, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=1)
    assert zustand["diskussion_knopf"] is True


def test_phase_1_ohne_profilflag_ergibt_falsch(datenbank, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=1)
    assert zustand["diskussion_knopf"] is False


@pytest.mark.parametrize("phase", [2, 3, 4, 5, 6, 7])
def test_andere_phase_mit_profilflag_an_ergibt_falsch(datenbank, monkeypatch, phase):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=phase)
    assert zustand["diskussion_knopf"] is False


def test_ohne_arbeitsstand_ergibt_falsch(datenbank, monkeypatch):
    """Keine Phase gesetzt (``_feld(stand, "phase")`` liefert ``None``) --
    ``None == 1`` ist falsch, unabhaengig vom Profilflag."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=None)
    assert zustand["diskussion_knopf"] is False
