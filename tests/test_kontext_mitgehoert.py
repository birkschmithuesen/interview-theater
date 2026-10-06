"""Birk 05.10.2026 (Nachtrag 5, I): "Der Chat muss immer ueber alles
Bescheid wissen." Live sagte der Bot "I can't see what's on the cothinker
page" und "what reaches me is only the marker for a voice recording" -- die
Diskussionssegmente standen im Fenster als "(sprache)" ohne Wortlaut, und
das Begriffsboard stand in Phase 1 gar nicht im Prompt. Seitdem: was
mitgehoert wurde, steht mit Wortlaut im Gespraechsprompt (juengstes zuerst
behalten), das Board als eigener Block, in jeder Phase. Nur erfundenes
Material."""

import json

import pytest

from interview_theater import begriffsboard, db, kontext, repo, sprache, workshop

CHAT = 1
BOARD = [
    {"begriff": "Heimat", "nennungen": 3, "zustimmung": 2, "begruendung": "Wo man bleibt.",
     "zitat": "", "doppelbedeutung": "", "status": "favorit"},
    {"begriff": "Grenze", "nennungen": 1, "zustimmung": 1, "begruendung": "",
     "zitat": "", "doppelbedeutung": "", "status": "kandidat"},
    {"begriff": "Musik", "nennungen": 1, "zustimmung": -2, "begruendung": "",
     "zitat": "", "doppelbedeutung": "", "status": "verworfen"},
]
SEGMENTE = [
    "Heimat ist fuer mich der Ort, an dem man bleibt.",
    "Und Grenze, die man nicht sieht, aber spuert.",
    "Es ist alles so furchtbar kompliziert.",
]


class _E:
    bot_name = "gruppe1"
    web_url = ""


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def _segmente(conn, *, brainstorm=False):
    for i, text in enumerate(SEGMENTE):
        mid = 10 + i
        repo.merke_nachricht(conn, CHAT, mid, "Gruppe", 0, "sprache", None, repo._jetzt(), 1)
        aid = repo.lege_aufnahme_an(conn, CHAT, mid, "kurz", "sprache", status="transkribiert",
                                    diskussion=not brainstorm, brainstorm=brainstorm,
                                    schnittgrund="pause")
        repo.setze_transkript(conn, aid, text)
        repo.setze_status(conn, aid, "fertig")


def _prompt(conn):
    repo.merke_nachricht(conn, CHAT, 50, "Gruppe", 0, "text",
                         "Speichere die Begriffe", repo._jetzt())
    ausloeser = repo.letzte_nachrichten(conn, CHAT, 1)
    return kontext.baue(conn, CHAT, ausloeser, _E())


def test_phase_1_prompt_hat_wortlaut_und_board(conn):
    _segmente(conn)
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(BOARD), "sovereign", 12)
    text = _prompt(conn)
    for satz in SEGMENTE:
        assert satz in text
    assert kontext.T.MITGEHOERT_KOPF in text
    assert kontext.T.BOARD_KOPF in text
    assert "1. Heimat" in text and "2. Grenze" in text
    assert "Musik" not in text          # verworfen
    assert "Wo man bleibt." in text     # Begruendung steht mit
    assert ": (sprache)" not in text    # kein nackter Marker mehr


def test_verworfener_aber_gespeicherter_begriff_behaelt_seine_begruendung(conn):
    """R-1: ein Begriff, den das Board als "verworfen" fuehrt, taucht in
    ``_baue_board`` gar nicht auf (die Zeile zeigt nur nicht verworfene
    Begriffe) -- hat die Gruppe ihn trotzdem gespeichert, verliert er so
    seine Begruendung komplett, denn ``begriffe_detail`` schwieg bisher
    IMMER, wenn das Board irgendetwas trug (egal in welcher Phase). Jetzt
    zeigt ``begriffe_detail`` genau die Begriffe, die das Board selbst
    nicht trägt -- in jeder Phase, auch 1 und 3."""
    board = BOARD[:2] + [
        {"begriff": "Musik", "nennungen": 2, "zustimmung": -2,
         "begruendung": "Kam oft vor, aber die Gruppe will nicht in diese Richtung.",
         "zitat": "", "doppelbedeutung": "", "status": "verworfen"},
    ]  # dieselbe Musik-Zeile wie im Modul-BOARD, aber MIT Begruendung --
       # sonst taeuscht ein Duplikat (zwei "Musik" in derselben Zeile) das
       # Ergebnis vor.
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(board), "sovereign", 0)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat, Musik")
    begriffsboard.schreibe_detail(conn, CHAT, "Heimat, Musik")

    for phase in (1, 3):
        repo.setze_phase(conn, CHAT, phase)
        text = _prompt(conn)
        assert "1. Heimat" in text
        assert "2. Musik" not in text and "· Musik" not in text, (
            "Musik steht nicht im Board-Block (verworfen)"
        )
        assert "Kam oft vor" in text, f"Begruendung fehlt in Phase {phase}"


def test_begriff_auf_dem_board_behaelt_seine_doppelbedeutung(conn):
    """MINOR 3 (Review T3): der Board-Block zeigt je Begriff nur die
    Begruendung (``_baue_board``), nie die Doppelbedeutung. Ein Begriff, der
    schon auf dem Board steht, darf deshalb nicht KOMPLETT aus dem
    Detail-Block fallen -- nur seine Begruendung ist dort doppelt, die
    Doppelbedeutung traegt der Board-Block gar nicht."""
    board = [
        {"begriff": "Heimat", "nennungen": 3, "zustimmung": 2,
         "begruendung": "Wo man bleibt.", "zitat": "",
         "doppelbedeutung": "Ort und Gefuehl", "status": "favorit"},
    ]
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(board), "sovereign", 0)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Heimat")
    begriffsboard.schreibe_detail(conn, CHAT, "Heimat")
    repo.setze_phase(conn, CHAT, 2)

    text = _prompt(conn)

    assert "1. Heimat (Favorit) -- Wo man bleibt." in text, "Begruendung steht auf dem Board"
    assert text.count("Wo man bleibt.") == 1, "die Begruendung steht nicht doppelt"
    assert "Ort und Gefuehl" in text, "die Doppelbedeutung darf nicht verloren gehen"


def test_board_steht_auch_in_spaeteren_phasen(conn):
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(BOARD), "sovereign", 0)
    for phase in (2, 3, 4, 5):
        repo.setze_phase(conn, CHAT, phase)
        assert kontext.T.BOARD_KOPF in _prompt(conn), phase


def test_brainstorm_wortlaut_steht_ebenfalls_im_prompt(conn):
    _segmente(conn, brainstorm=True)
    repo.setze_phase(conn, CHAT, 4)
    text = _prompt(conn)
    assert "furchtbar kompliziert" in text


def test_ohne_mitgehoertes_kein_block(conn):
    text = _prompt(conn)
    assert kontext.T.MITGEHOERT_KOPF not in text
    assert kontext.T.BOARD_KOPF not in text


def test_juengstes_bleibt_wenn_das_budget_knapp_ist(conn, monkeypatch):
    monkeypatch.setattr(kontext, "MITGEHOERT_ZEICHEN", 80)
    _segmente(conn)
    block = kontext._baue_mitgehoert(conn, CHAT)
    assert "furchtbar kompliziert" in block
    assert "der Ort, an dem man bleibt" not in block


def test_englische_systemanweisung_sagt_dass_alles_vorliegt(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    try:
        text = " ".join(kontext.system("gruppe1", 1).split())
        assert "never ask the group to retype it" in text
        assert "CoThinker" in text
    finally:
        monkeypatch.delenv(workshop.VARIABLE)
        workshop.vergiss()
        sprache.vergiss()


def test_englischer_board_kopf_behauptet_keine_feste_top_fuenf(monkeypatch):
    """Lesung Runde 2 (05.10.2026), Prompt-Check "by design", Dump P1
    01:551: ``BOARD_KOPF`` behauptete "the first five are saved as their
    terms" -- das Top-5-Autosave gilt nur, solange die Gruppe keine eigene
    Liste hat (Fixture Runde 2: gespeichert waren fuenf andere Begriffe in
    anderer Reihenfolge als der Board-Rang, ``begriffe_board_wert``). Die
    Klammer nennt jetzt keine Zahl mehr, nur den Verweis auf "Terms"."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    try:
        assert "the first five are saved as their terms" not in kontext.T.BOARD_KOPF
        assert "the saved terms are the ones under Terms above" in kontext.T.BOARD_KOPF
    finally:
        monkeypatch.delenv(workshop.VARIABLE)
        workshop.vergiss()
        sprache.vergiss()


def test_mitgehoert_grenze_aus_umgebung(monkeypatch):
    """Padua 06.10.2026: die Grenze ist per IT_MITGEHOERT_ZEICHEN umstellbar,
    Vorgabe 60.000 (Mutant: Vorgabe zurueck auf 6000 -> zweite Zusicherung rot)."""
    monkeypatch.delenv("IT_MITGEHOERT_ZEICHEN", raising=False)
    assert kontext.mitgehoert_zeichen() == 60_000
    monkeypatch.setenv("IT_MITGEHOERT_ZEICHEN", "12000")
    assert kontext.mitgehoert_zeichen() == 12_000
    monkeypatch.setenv("IT_MITGEHOERT_ZEICHEN", "kaputt")
    assert kontext.mitgehoert_zeichen() == 60_000
