"""Task 2 (Kanban-Karte Buehne/PTT, 03.10.2026): der Brainstorm-Knopf der
Web-Fussleiste nur in Phase 4 -- dieselbe Bauart wie der Interview-Knopf
(Padua Hotfix B6, ``tests/test_web_chat_phase_knopf.py``): ein Poll-Feld in
``web_daten.web_chatzustand``, ein ``hidden``-Attribut, das derselben Quelle
folgt wie die ``nebenknopf``-Klasse am Interview-Knopf, und ein JS, das das
Feld bei jedem Poll nachliest. Anders als beim Interview-Knopf gibt es
serverseitig KEINE "laeuft gerade"-Ausnahme -- eine Brainstorm-Sitzung ist
rein clientseitiger Zustand, siehe ``AGENTS.md``/Brief Abschnitt 1."""

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


def _brainstorm_tag(seite: str) -> str:
    treffer = re.search(r'<button type="button" id="brainstorm"[^>]*>', seite)
    assert treffer, seite
    return treffer.group(0)


def _interview_tag(seite: str) -> str:
    treffer = re.search(r'<button type="button" id="interview"[^>]*>', seite)
    assert treffer, seite
    return treffer.group(0)


@pytest.mark.parametrize("phase, sichtbar", [
    (None, False), (1, False), (2, False), (3, False), (4, True), (7, False),
])
def test_der_poll_meldet_den_knopf_nur_in_phase_4(datenbank, phase, sichtbar):
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase)
    assert zustand["brainstorm_knopf"] is sichtbar


@pytest.mark.parametrize("phase, verborgen", [
    (None, True), (1, True), (2, True), (3, True), (4, False), (7, True),
])
def test_die_seite_rendert_den_knopf_hidden_ausserhalb_von_phase_4(datenbank, phase, verborgen):
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase)
    seite = web_chat.chat_html(zustand, "n", token, "", 45000)
    # Der Knopf steht IMMER im Markup (wie #interview) -- nur ``hidden``
    # folgt der Phase. t_cf87ee0a: Toggle statt Pause/Beenden -- die
    # Aktionsleiste (#brainstorm-aktionen/-pause/-beenden) gibt es nicht mehr.
    for kennung in ("brainstorm",):
        assert f'id="{kennung}"' in seite, kennung
    for weg in ("brainstorm-aktionen", "brainstorm-pause", "brainstorm-beenden"):
        assert f'id="{weg}"' not in seite, weg
    tag = _brainstorm_tag(seite)
    assert (" hidden" in tag) is verborgen


@pytest.mark.parametrize("phase, nebenknopf", [
    (None, False), (1, False), (2, False), (3, False), (4, True), (7, False),
])
def test_der_interview_knopf_ist_nebenknopf_genau_wenn_brainstorm_sichtbar_ist(
        datenbank, phase, nebenknopf):
    pfad, token = datenbank
    zustand = _zustand(pfad, token, phase)
    seite = web_chat.chat_html(zustand, "n", token, "", 45000)
    tag = _interview_tag(seite)
    assert ('class="nebenknopf"' in tag) is nebenknopf


def test_das_js_liest_das_flag_und_blendet_bei_laufender_sitzung_nie_aus():
    js = web_chat._js()
    assert "daten.brainstorm_knopf" in js
    assert (
        "var sichtbar = zustand.brainstormErlaubt || an || !!zustand.wechsel;"
        in js
    )
    assert "brainstormKnopf.hidden = !sichtbar;" in js
