"""Task 5 (Padua Phase 1+2 Umbau, 03.10.2026): der ``#diskussion``-Knopf der
Web-Fussleiste -- dieselbe Bauart wie der Brainstorm-Knopf
(``tests/test_web_chat_brainstorm_knopf.py``): ein Drei-Zustands-Regler mit
Toggle- und zwei Aktionsknoepfen. Die *Berechnung* von ``diskussion_knopf``
(Phase 1 UND Profilflag) liegt in ``web_daten.web_chatzustand`` und ist
bereits getestet (``tests/test_web_daten_diskussion_knopf.py``, Task 4) --
dieser Test prueft nur das Rendern aus dem fertigen Flag.

``data-discussion-done="1"`` steht auf dem Beenden-Knopf, nicht auf dem
Toggle-Knopf: er ist die eigentliche "Diskussion fertig"-Aktion fuer die
UX-Knoepfe-Parallelkarte."""

import re

import pytest

from interview_theater import db, repo, web_chat, web_daten, workshop

CHAT = 7_000_000_000_004


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


def _diskussion_tag(seite: str) -> str:
    treffer = re.search(r'<button type="button" id="diskussion"[^>]*>', seite)
    assert treffer, seite
    return treffer.group(0)


def _beenden_tag(seite: str) -> str:
    treffer = re.search(r'<button type="button" id="diskussion-beenden"[^>]*>', seite)
    assert treffer, seite
    return treffer.group(0)


def _toggle_tag(seite: str) -> str:
    treffer = re.search(r'<button type="button" id="diskussion"[^>]*>', seite)
    assert treffer, seite
    return treffer.group(0)


def test_der_knopf_ist_standardmaessig_verborgen(datenbank, monkeypatch):
    """Ohne Profilflag und ausserhalb Phase 1 bleibt ``diskussion_knopf``
    falsch (Task 4) -- und die vier Elemente stehen trotzdem IMMER im
    Markup, nur ``hidden`` folgt dem Flag (wie beim Brainstorm-Knopf)."""
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=1)
    assert zustand["diskussion_knopf"] is False
    seite = web_chat.chat_html(zustand, "n", token, "", 45000)
    for kennung in ("diskussion", "diskussion-aktionen", "diskussion-pause",
                    "diskussion-beenden"):
        assert f'id="{kennung}"' in seite, kennung
    tag = _diskussion_tag(seite)
    assert " hidden" in tag


def test_der_knopf_ist_sichtbar_wenn_das_flag_wahr_ist(datenbank, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=1)
    assert zustand["diskussion_knopf"] is True
    seite = web_chat.chat_html(zustand, "n", token, "", 45000)
    tag = _diskussion_tag(seite)
    assert " hidden" not in tag


def test_fehlt_das_flag_ganz_bleibt_der_knopf_verborgen():
    """Verteidigungstiefe (Brief Schritt 2): ``daten.get("diskussion_knopf",
    False)`` -- anders als beim Brainstorm-Knopf (Vorgabe ``True``) bleibt
    das Feature unsichtbar, wenn der Server den Schluessel aus irgendeinem
    Grund gar nicht mitschickt."""
    daten = {
        "interviewmodus": False, "nachrichten": [], "letzte": 0,
        "titel": "t", "phase": None,
    }
    seite = web_chat.chat_html(daten, "n", "tok", "", 45000)
    tag = _diskussion_tag(seite)
    assert " hidden" in tag


def test_data_discussion_done_steht_nur_auf_dem_beenden_knopf(datenbank, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=1)
    seite = web_chat.chat_html(zustand, "n", token, "", 45000)
    beenden_tag = _beenden_tag(seite)
    assert 'data-discussion-done="1"' in beenden_tag
    toggle_tag = _toggle_tag(seite)
    assert 'data-discussion-done' not in toggle_tag
