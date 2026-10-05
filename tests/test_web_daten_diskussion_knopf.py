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


@pytest.mark.parametrize("phase", [2, 3, 5, 6, 7])
def test_andere_phase_mit_profilflag_an_ergibt_falsch(datenbank, monkeypatch, phase):
    """Phase 4 fliegt hier raus (Birk 05.10.2026 22:00): seit Phase 4
    denselben Knopf wie Phase 1 benutzt, ist ``diskussion_knopf`` dort immer
    wahr, auch ohne Profilflag -- siehe
    ``test_phase_4_zeigt_den_mithoer_knopf_auch_ohne_profilflag``."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=phase)
    assert zustand["diskussion_knopf"] is False


def test_phase_4_zeigt_den_mithoer_knopf_auch_ohne_profilflag(datenbank, monkeypatch):
    """Birk 05.10.2026 22:00: kein Toggle mehr -- Phase 4 bedient sich mit
    demselben Knopf wie Phase 1, aber OHNE das Profilflag der Phase 1
    (``workshop.diskussion_aktiv``): Phase 4 braucht es nicht, ``cap``/
    ``pause`` loesen dort unabhaengig vom Begriffsboard-Profil aus."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=4)
    assert zustand["diskussion_knopf"] is True


@pytest.mark.parametrize("phase, ziel", [
    (1, "diskussion"), (2, "diskussion"), (3, "diskussion"), (4, "brainstorm"),
    (5, "diskussion"), (6, "diskussion"), (7, "diskussion"),
])
def test_mithoeren_ziel_ist_brainstorm_nur_in_phase_4(datenbank, phase, ziel):
    """Birk 05.10.2026 22:00: ``mithoeren_ziel`` sagt dem Client, wohin das
    Audio dieser Sitzung geht -- nur in Phase 4 'brainstorm' (Buehnenkarten),
    sonst 'diskussion' (Begriffsboard Phase 1)."""
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=phase)
    assert zustand["mithoeren_ziel"] == ziel


def test_ohne_arbeitsstand_mit_profilflag_ergibt_wahr(datenbank, monkeypatch):
    """Keine Phase gesetzt (``_feld(stand, "phase")`` liefert ``None``) heisst
    ERSTE (Phase 1), nicht "keine Phase" -- Bug Birk Live-Test 04.10.2026:
    eine frische Gruppe hat noch keine ``arbeitsstand``-Zeile und sah den
    Knopf nie, obwohl sie in Phase 1 war. Derselbe Fallback wie beim
    Interview-Knopf (``phasen.ERSTE``)."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=None)
    assert zustand["diskussion_knopf"] is True


def test_ohne_arbeitsstand_ohne_profilflag_ergibt_falsch(datenbank, monkeypatch):
    """Dieselbe Lage, aber Dortmund (Profilflag aus) bleibt unberuehrt."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=None)
    assert zustand["diskussion_knopf"] is False
