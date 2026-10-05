"""Birk 05.10.2026 22:00: kein Per-Gedanke-Toggle mehr -- Phase 4 bedient
sich mit demselben Knopf wie Phase 1 ("Start listening"/"Discussion done",
``#diskussion``/``#diskussion-beenden``). Loest
``tests/test_web_chat_brainstorm_knopf.py`` ab (geloescht): kein eigener
``#brainstorm``-Knopf mehr, der Markup-Unterschied zwischen den Phasen ist
jetzt nur noch das ``data-mithoeren-ziel``-Attribut am EINEN Knopf. Die
Browser-JS-Seite (``starteDiskussion``/``beendeDiskussion``, ``sitzung.ziel``)
ist Aufgabe einer spaeteren Karte (Task 3) -- hier geht es nur um das von
Python gerenderte Markup und die Server-Entscheidung in
``web_daten.web_chatzustand`` (siehe auch
``tests/test_web_daten_diskussion_knopf.py``)."""

import re

import pytest

from interview_theater import db, repo, web_chat, web_daten

CHAT = 7_000_000_000_002


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


def _interview_tag(seite: str) -> str:
    treffer = re.search(r'<button type="button" id="interview"[^>]*>', seite)
    assert treffer, seite
    return treffer.group(0)


@pytest.mark.parametrize("phase, sichtbar", [
    (None, False), (1, False), (2, False), (3, False), (4, True), (7, False),
])
def test_der_poll_meldet_den_knopf_in_phase_1_und_4(datenbank, phase, sichtbar, monkeypatch):
    from interview_theater import workshop
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase)
    assert zustand["diskussion_knopf"] is sichtbar


def test_es_gibt_keinen_eigenen_brainstorm_knopf_mehr(datenbank):
    """Birk 05.10.2026 22:00: kein ``#brainstorm`` im Markup, in keiner
    Phase -- Phase 4 benutzt ``#diskussion``."""
    pfad, token = datenbank
    for phase in (1, 2, 3, 4, 5, 6, 7):
        zustand = _zustand(pfad, token, phase)
        seite = web_chat.chat_html(zustand, "n", token, "", 45000)
        assert 'id="brainstorm"' not in seite, phase


@pytest.mark.parametrize("phase, verborgen", [
    (None, True), (1, True), (2, True), (3, True), (4, False), (7, True),
])
def test_die_seite_rendert_den_diskussion_knopf_hidden_ausserhalb_von_phase_4(
        datenbank, phase, verborgen, monkeypatch):
    from interview_theater import workshop
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase)
    seite = web_chat.chat_html(zustand, "n", token, "", 45000)
    tag = _diskussion_tag(seite)
    assert (" hidden" in tag) is verborgen


def test_der_diskussion_knopf_traegt_das_mithoeren_ziel_in_phase_4(datenbank):
    """Markup-Zusage (Task 2): in Phase 4 steht am ``#diskussion``-Knopf
    ``data-mithoeren-ziel="brainstorm"``, sonst ``"diskussion"``."""
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=4)
    seite = web_chat.chat_html(zustand, "n", token, "", 45000)
    tag = _diskussion_tag(seite)
    assert 'data-mithoeren-ziel="brainstorm"' in tag


def test_der_diskussion_knopf_traegt_diskussion_als_ziel_in_phase_1(datenbank, monkeypatch):
    from interview_theater import workshop
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=1)
    seite = web_chat.chat_html(zustand, "n", token, "", 45000)
    tag = _diskussion_tag(seite)
    assert 'data-mithoeren-ziel="diskussion"' in tag


def test_der_diskussion_knopf_zeigt_die_phase_1_beschriftungen(datenbank):
    """Markup-Zusage (Task 2): derselbe Knopftext in Phase 4 wie in Phase 1
    -- ``T._TEXT_DISKUSSION_AN``/``_TEXT_DISKUSSION_FERTIG_KNOPF``, keine
    eigene Brainstorm-Beschriftung mehr."""
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase=4)
    seite = web_chat.chat_html(zustand, "n", token, "", 45000)
    assert web_chat._TEXT_DISKUSSION_AN in seite
    assert web_chat._TEXT_DISKUSSION_FERTIG_KNOPF in seite
    assert web_chat._TEXT_BRAINSTORM_AN not in seite


@pytest.mark.parametrize("phase, nebenknopf", [
    (None, False), (1, False), (2, False), (3, False), (4, True), (7, False),
])
def test_der_interview_knopf_ist_nebenknopf_genau_wenn_diskussion_sichtbar_ist(
        datenbank, phase, nebenknopf, monkeypatch):
    from interview_theater import workshop
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase)
    seite = web_chat.chat_html(zustand, "n", token, "", 45000)
    tag = _interview_tag(seite)
    assert ('class="nebenknopf"' in tag) is nebenknopf
