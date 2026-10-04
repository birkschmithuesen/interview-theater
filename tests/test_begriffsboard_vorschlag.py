"""Karte t_4517d4ad, Aufgabe 6: "Discussion done" -> Top-5-Vorschlag (D6)."""

import json
import threading
import time

import pytest

from interview_theater import (
    aufnahme, begriffsboard, db, diskussion, einstellungen, knoepfe, repo, workshop,
)
from interview_theater.knoepfe import texte

CHAT = 1
TEXT = "Heimat und Grenze und Mut und Schule und Freunde und Angst und Musik."


@pytest.fixture(autouse=True)
def aktiv(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
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
        self.beantwortet = []
        self._id = 800

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._id += 1
        return self._id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        mid = self.sende(chat_id, text)
        self.mit_knoepfen.append((chat_id, text, list(knoepfe_)))
        return mid

    def beantworte_knopf(self, callback_query_id, text=""):
        self.beantwortet.append(text)

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    def tippt(self, chat_id):
        pass


def _e(begriff, status="kandidat", zustimmung=0, nennungen=1):
    return {"begriff": begriff, "nennungen": nennungen, "zustimmung": zustimmung,
            "begruendung": f"Weil {begriff}.", "zitat": "", "doppelbedeutung": "", "status": status}


def _ende(conn, message_id=900):
    aid = repo.lege_aufnahme_an(conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
                                diskussion=True, schnittgrund="ende")
    repo.setze_transkript(conn, aid, TEXT)
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "sprache", None, repo._jetzt(), 1)
    return repo.hole_aufnahme(conn, aid)


def _druecke(conn, tg, einst, daten, klm=None):
    return knoepfe.behandle(conn, tg, klm, einst, {
        "callback_query_id": "q1", "data": daten, "chat_id": CHAT,
        "chat_titel": "Testgruppe", "message_id": 777,
    })


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


def test_leeres_board_heutiger_text(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "100000")
    tg = _TG()
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, _ende(conn), aufnahme._kein_zug, False)
    assert tg.gesendet == [(CHAT, aufnahme.T._TEXT_DISKUSSION_FERTIG_BEGRIFFE)]
    assert tg.mit_knoepfen == []


def test_ohne_schlusslauf_sofort_die_top_fuenf_mit_einem_knopf(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "100000")
    board = [_e("Heimat", "favorit"), _e("Grenze", zustimmung=2), _e("Mut", zustimmung=1),
             _e("Schule"), _e("Freunde"), _e("Angst"), _e("Musik", "verworfen", 2, 9)]
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(board), "sovereign", 0)
    tg = _TG()
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, _ende(conn), aufnahme._kein_zug, False)
    assert len(tg.mit_knoepfen) == 1
    _chat, text, leiste = tg.mit_knoepfen[0]
    assert len(leiste) == 1
    beschriftung, daten = leiste[0]
    assert beschriftung == texte.T._TEXT_BOARD_UEBERNEHMEN_KNOPF
    assert daten.startswith("k:") and len(daten.encode()) < 64
    # Birk Live-Test 04.10.2026: ALLE nicht verworfenen Begriffe stehen in
    # der Liste, nur die Top 5 bekommen einen Stern -- "Schule" ist der
    # sechste (nicht verworfene) Begriff und steht trotzdem drin, nur ohne
    # Stern. "Musik" (verworfen) fehlt weiterhin komplett.
    for nr, begriff in enumerate(["Heimat", "Grenze", "Mut", "Angst", "Freunde"], 1):
        assert f"{nr}. {begriff} ⭐" in text
    assert "6. Schule" in text
    assert "Schule ⭐" not in text
    assert "Musik" not in text
    knopf = repo.hole_knopf(conn, int(daten[2:]))
    assert knopf["art"] == texte.ART_BOARD_UEBERNEHMEN
    assert knopf["wert"] == "Heimat, Grenze, Mut, Angst, Freunde"
    assert aufnahme.T._TEXT_DISKUSSION_FERTIG_BEGRIFFE not in [t for _c, t in tg.gesendet]


def test_mit_schlusslauf_kommt_der_vorschlag_erst_danach(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")
    halt = threading.Event()

    class KLM:
        def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
            halt.wait(5)
            return {"board": [_e("Heimat", "favorit")]}

    tg = _TG()
    aufnahme._kurz_abschliessen(conn, tg, KLM(), einst, _ende(conn), aufnahme._kein_zug, False)
    time.sleep(0.1)
    assert tg.mit_knoepfen == [] and tg.gesendet == []
    halt.set()
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    assert "1. Heimat" in tg.mit_knoepfen[0][1]


def test_gescheiterter_schlusslauf_nimmt_das_aktuelle_board(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps([_e("Grenze")]), "sovereign", 0)

    class KLM:
        def schema(self, *a, **k):
            raise RuntimeError("weg")

    tg = _TG()
    aufnahme._kurz_abschliessen(conn, tg, KLM(), einst, _ende(conn), aufnahme._kein_zug, False)
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    assert "1. Grenze" in tg.mit_knoepfen[0][1]


def test_gesamtverdichtung_startet_unabhaengig(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "100000")
    gestartet = []
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: gestartet.append(1))
    aufnahme._kurz_abschliessen(conn, _TG(), object(), einst, _ende(conn), aufnahme._kein_zug, False)
    assert gestartet == [1]


def test_take_these_speichert_begriffe_und_detail_einmal(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "100000")
    board = [_e("Heimat", "favorit"), _e("Grenze")]
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps(board), "sovereign", 0)
    tg = _TG()
    aufnahme._kurz_abschliessen(conn, tg, object(), einst, _ende(conn), aufnahme._kein_zug, False)
    daten = tg.mit_knoepfen[0][2][0][1]

    assert _druecke(conn, tg, einst, daten) is True
    stand = repo.hole_arbeitsstand(conn, CHAT)
    assert stand["begriffe"] == "Heimat, Grenze"
    assert [d["begruendung"] for d in json.loads(stand["begriffe_detail"])] == [
        "Weil Heimat.", "Weil Grenze.",
    ]

    vorher = len(tg.gesendet)
    _druecke(conn, tg, einst, daten)   # zweiter Druck: beantwortet, wirkt nicht (Zusage 3)
    assert repo.hole_arbeitsstand(conn, CHAT)["begriffe"] == "Heimat, Grenze"
    assert len(tg.gesendet) == vorher
