"""Karte t_4517d4ad, Aufgabe 4: das Board haengt am echten Mithoer-Pfad
(``aufnahme._kurz_abschliessen`` -> ``_diskussion_abschliessen``), und es
entsteht dabei keine Chatzeile (D5, mit Mutant)."""

import threading
import time

import pytest

from interview_theater import aufnahme, begriffsboard, db, diskussion, einstellungen, repo, workshop

CHAT = 1
TEXT = "Wir reden ueber Heimat und Grenze. Heimat ist, wo meine Oma kocht."
HEIMAT = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 1, "begruendung": "Oma.",
          "zitat": "wo meine Oma kocht", "doppelbedeutung": "", "status": "favorit"}


@pytest.fixture(autouse=True)
def aktiv(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ABSTAND_S", "1")
    # Die Gesamtverdichtung ist nicht Gegenstand dieser Datei.
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: None)


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


class _TG:
    def __init__(self):
        self.gesendet = []
        self.mit_knoepfen = []
        self._id = 500

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._id += 1
        return self._id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        mid = self.sende(chat_id, text)
        self.mit_knoepfen.append((chat_id, text, list(knoepfe_)))
        return mid


class _KLM:
    def __init__(self, board):
        self.aufrufe = 0
        self._board = board

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        return {"board": self._board}


def _zeile(conn, message_id, schnittgrund, text=TEXT):
    aid = repo.lege_aufnahme_an(
        conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
        diskussion=True, schnittgrund=schnittgrund,
    )
    repo.setze_transkript(conn, aid, text)
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "sprache", None, repo._jetzt(), 1)
    return repo.hole_aufnahme(conn, aid)


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


def _segment_mit_board(conn, tg, einst, klm, message_id=700):
    row = _zeile(conn, message_id, "pause")
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, row, aufnahme._kein_zug, False)
    _warte_bis(lambda: repo.letztes_begriffsboard(conn, CHAT) is not None)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))


def _keine_chatzeile(tg):
    assert tg.gesendet == [] and tg.mit_knoepfen == []


def test_pausensegment_fuellt_das_board(conn, einst):
    tg, klm = _TG(), _KLM([HEIMAT])
    _segment_mit_board(conn, tg, einst, klm)
    assert [e["begriff"] for e in begriffsboard.aktuelles(conn, CHAT)] == ["Heimat"]
    assert klm.aufrufe == 1


def test_waehrend_des_mithoerens_keine_chatzeile(conn, einst):
    tg = _TG()
    _segment_mit_board(conn, tg, einst, _KLM([HEIMAT]))
    _keine_chatzeile(tg)


def test_mutant_sende_im_boardlauf_faellt_auf(conn, einst, monkeypatch):
    """D5-Mutant: schreibt der Boardlauf doch eine Chatzeile, muss
    ``_keine_chatzeile`` es merken."""
    tg = _TG()
    echt = begriffsboard._lauf_einmal

    def mutant(conn_, klm_, e_, chat_id, bis_id):
        echt(conn_, klm_, e_, chat_id, bis_id)
        tg.sende(chat_id, "Neuer Begriff auf dem Board!")

    monkeypatch.setattr(begriffsboard, "_lauf_einmal", mutant)
    _segment_mit_board(conn, tg, einst, _KLM([HEIMAT]))
    with pytest.raises(AssertionError):
        _keine_chatzeile(tg)


def test_kein_gespraechszug_und_keine_buehnenkarte(conn, einst, monkeypatch):
    karten = []
    monkeypatch.setattr(aufnahme, "_starte_buehnenkarte", lambda *a, **k: karten.append(1))
    zuege = []
    row = _zeile(conn, 701, "pause")
    aufnahme._kurz_abschliessen(conn, _TG(), _KLM([HEIMAT]), einst, row,
                                lambda *a, **k: zuege.append(1), False)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    assert karten == [] and zuege == []


def test_cap_segment_startet_keinen_lauf(conn, einst):
    klm = _KLM([HEIMAT])
    row = _zeile(conn, 702, "cap")
    aufnahme._kurz_abschliessen(conn, _TG(), klm, einst, row, aufnahme._kein_zug, False)
    time.sleep(0.1)
    assert klm.aufrufe == 0


def test_ohne_profil_bleibt_alles_wie_vorher(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: False)
    klm, tg = _KLM([HEIMAT]), _TG()
    row = _zeile(conn, 703, "ende")
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, row, aufnahme._kein_zug, False)
    time.sleep(0.1)
    assert klm.aufrufe == 0
    assert tg.gesendet == [(CHAT, aufnahme.T._TEXT_DISKUSSION_KEINE_BEGRIFFE)]
