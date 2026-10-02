"""Padua Hotfix B6 (02.10.2026): der Interview-Knopf der Web-Fussleiste nur in
Phase 3 oder bei laufender Aufnahme -- dieselbe Regel wie die Telegram-Knoepfe
(``knoepfe._aufnahme_anbieten``, ``nur_phase_3``), geteilt ueber
``phasen.aufnahme_anbieten``. Dazu: der Knopftext in der EN-Oberflaeche."""

import re

import pytest

from interview_theater import db, phasen, repo, sprache, web_chat, web_daten, workshop

CHAT = 7_000_000_000_001


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


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _zustand(pfad, token, phase=None, modus=False):
    schreibend = db.verbinde(pfad)
    if phase is not None:
        repo.setze_phase(schreibend, CHAT, phase)
    if modus:
        repo.setze_interviewmodus(schreibend, CHAT, repo._jetzt())
    schreibend.close()
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        return web_daten.web_chatzustand(lesend, token)
    finally:
        lesend.close()


def _knopf_tag(seite: str) -> str:
    treffer = re.search(r'<button type="button" id="interview"[^>]*>', seite)
    assert treffer, seite
    return treffer.group(0)


@pytest.mark.parametrize("phase, sichtbar", [
    (None, False), (1, False), (2, False), (3, True), (4, False), (7, False),
])
def test_der_poll_meldet_den_knopf_nur_in_phase_3(datenbank, phase, sichtbar):
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase)
    assert zustand["interview_knopf"] is sichtbar


@pytest.mark.parametrize("phase", [1, 2, 4])
def test_bei_laufender_aufnahme_steht_der_knopf_in_jeder_phase(datenbank, phase):
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase, modus=True)
    assert zustand["interview_knopf"] is True
    assert 'hidden' not in _knopf_tag(web_chat.chat_html(zustand, "n", token, "", 45000))


@pytest.mark.parametrize("phase, verborgen", [(1, True), (2, True), (3, False), (4, True)])
def test_die_seite_rendert_den_knopf_hidden_ausserhalb_von_phase_3(datenbank, phase, verborgen):
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase)
    tag = _knopf_tag(web_chat.chat_html(zustand, "n", token, "", 45000))
    assert (" hidden" in tag) is verborgen


def test_das_js_liest_das_flag_und_verbirgt_nie_eine_laufende_aufnahme():
    js = web_chat._js()
    assert "daten.interview_knopf" in js
    assert "interviewKnopf.hidden = !(zustand.knopfErlaubt || an || !!zustand.wechsel" in js


def test_telegram_und_web_teilen_dieselbe_regel():
    """``_aufnahme_anbieten`` delegiert an ``phasen.aufnahme_anbieten`` --
    dieselbe Antwort fuer jede Phase."""
    for phase in range(1, 8):
        assert phasen.aufnahme_anbieten(phase, False, nur_phase_3=True) is (phase == 3)
        assert phasen.aufnahme_anbieten(phase, False) is (phase >= 3)
        assert phasen.aufnahme_anbieten(phase, True, nur_phase_3=True) is True


def test_der_knopftext_ist_in_padua_englisch(datenbank, padua):
    pfad, token = datenbank
    zustand = _zustand(pfad, token, 3)
    seite = web_chat.chat_html(zustand, "n", token, "", 45000)
    assert ">Record interview</button>" in seite
    assert "Interview aufnehmen" not in seite
    assert '"interview_an": "Record interview"' in web_chat._js()
    assert '"interview_aus": "Stop recording"' in web_chat._js()


def test_der_knopftext_bleibt_ohne_profil_deutsch(datenbank):
    pfad, token = datenbank
    zustand = _zustand(pfad, token, 3)
    assert ">Interview aufnehmen</button>" in web_chat.chat_html(zustand, "n", token, "", 45000)
