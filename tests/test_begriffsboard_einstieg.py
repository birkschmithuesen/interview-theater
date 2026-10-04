"""Karte t_4517d4ad, Aufgabe 9: der Onboarding-Satz (D10)."""

import pytest

from interview_theater import ablauf, begriffsboard, db, einstellungen, repo, sprache, workshop
from interview_theater.knoepfe import stationen

CHAT = 1


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

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append(text)
        return 100 + len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        return self.sende(chat_id, text)

    def tippt(self, chat_id):
        pass


def test_englischer_wortlaut_im_padua_profil(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    try:
        assert begriffsboard.T._TEXT_EINSTIEG == (
            "Lay one phone in the middle -- it listens. Open the CoThinker tab "
            "on a second phone: the terms you mention appear there."
        )
    finally:
        monkeypatch.delenv(workshop.VARIABLE)
        workshop.vergiss()
        sprache.vergiss()


def test_ohne_profil_kein_satz(conn, einst):
    tg = _TG()
    assert begriffsboard.sende_einstieg(conn, tg, einst, CHAT) is False
    assert tg.gesendet == []


def test_mit_profil_satz_und_mitschrift(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    tg = _TG()
    assert begriffsboard.sende_einstieg(conn, tg, einst, CHAT) is True
    assert tg.gesendet == [begriffsboard.T._TEXT_EINSTIEG]
    assert repo.hat_bot_nachricht(conn, CHAT)


def test_eintritt_in_phase_1_sendet_den_satz(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    repo.setze_phase(conn, CHAT, 1)
    tg = _TG()
    stationen.eintritt_in_phase(conn, tg, None, einst, CHAT, 1)
    assert begriffsboard.T._TEXT_EINSTIEG in tg.gesendet


def test_eintritt_ohne_profil_ohne_satz(conn, einst):
    repo.setze_phase(conn, CHAT, 1)
    tg = _TG()
    stationen.eintritt_in_phase(conn, tg, None, einst, CHAT, 1)
    assert begriffsboard.T._TEXT_EINSTIEG not in tg.gesendet


def test_erste_antwort_einer_neuen_gruppe_bekommt_den_satz_dahinter(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(ablauf, "_erfrage_antwort", lambda *a, **k: "Willkommen!")
    repo.merke_nachricht(conn, CHAT, 1, "Gruppe", 0, "text", "Hallo", repo._jetzt())
    tg = _TG()
    ablauf.antworte(conn, tg, object(), einst, CHAT, list(repo.unbeantwortete(conn, CHAT)))
    assert tg.gesendet[-1] == begriffsboard.T._TEXT_EINSTIEG
    assert any("Willkommen!" in t for t in tg.gesendet[:-1])


def test_zweite_antwort_ohne_satz(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(ablauf, "_erfrage_antwort", lambda *a, **k: "Weiter so.")
    repo.merke_nachricht(conn, CHAT, 1, "gruppe1", 1, "text", "frueher", repo._jetzt())
    repo.merke_nachricht(conn, CHAT, 2, "Gruppe", 0, "text", "Noch was", repo._jetzt())
    tg = _TG()
    ablauf.antworte(conn, tg, object(), einst, CHAT, list(repo.unbeantwortete(conn, CHAT)))
    assert begriffsboard.T._TEXT_EINSTIEG not in tg.gesendet
