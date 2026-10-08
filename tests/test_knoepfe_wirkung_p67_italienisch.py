"""Nachtauftrag cc-p67texte (08.10.2026, Befund G1-G3 live): nach "No,
change" auf einer Szene in Phase 6/7 (generischer Weg, kein Dialog ueber die
Szenenkarte) blieb ``_TEXT_SZENE_ANDERS_FRAGE`` ("What should change? Tell
me, and I'll rewrite it.") englisch, obwohl ``phasentexte``/``erkenner``/
``szenenkarte``/``stagescript`` seit dem Morgen-Auftrag 4 schon italienisch
schreiben fuer Chats aus ``workshop.italienisch_ab_phase6_chats()``.
Derselbe Mechanismus (``_T_IT`` + ``_texte_fuer_phase``, nur in Phase 6/7);
Knopfbeschriftungen bleiben englisch."""

import pytest

from interview_theater import phasen, workshop
from interview_theater.knoepfe import wirkung
from interview_theater.knoepfe.wirkung import Druck


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        return 9001


@pytest.fixture
def conn(tmp_path):
    from interview_theater import db, repo

    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    monkeypatch.setattr(workshop, "italienisch_ab_phase6_chats", lambda *a, **k: frozenset({1}))
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def test_texte_fuer_phase_italienisch_in_phase_6(conn, padua):
    phasen.setze(conn, 1, 6, "test")
    assert wirkung._texte_fuer_phase(conn, 1) is wirkung._T_IT


def test_texte_fuer_phase_italienisch_in_phase_7(conn, padua):
    phasen.setze(conn, 1, 7, "test")
    assert wirkung._texte_fuer_phase(conn, 1) is wirkung._T_IT


def test_texte_fuer_phase_bleibt_englisch_ausserhalb_6_7(conn, padua):
    phasen.setze(conn, 1, 4, "test")
    assert wirkung._texte_fuer_phase(conn, 1) is wirkung.T


def test_texte_fuer_phase_tester_chat_bleibt_englisch(conn, padua, monkeypatch):
    monkeypatch.setattr(workshop, "italienisch_ab_phase6_chats", lambda *a, **k: frozenset())
    phasen.setze(conn, 1, 7, "test")
    assert wirkung._texte_fuer_phase(conn, 1) is wirkung.T


def test_wirkung_szene_anders_italienisch_in_phase_7(conn, padua):
    phasen.setze(conn, 1, 7, "test")
    tg = TelegramAttrappe()
    d = Druck(tg, None, None, {"wert": "1"}, 1)

    antwort = wirkung._wirkung_szene_anders(conn, d)

    assert any(
        "Cosa deve cambiare? Ditemelo e la riscrivo." in t for _, t in tg.gesendet
    )
    assert not any("What should change" in t for _, t in tg.gesendet)
    assert antwort == "Cosa deve cambiare?"


def test_wirkung_szene_anders_dortmund_bytegleich(conn):
    """Ohne Padua-Profil: dieselbe deutsche Zeile wie vor dem Nachtauftrag."""
    phasen.setze(conn, 1, 7, "test")
    tg = TelegramAttrappe()
    d = Druck(tg, None, None, {"wert": "1"}, 1)

    antwort = wirkung._wirkung_szene_anders(conn, d)

    assert any(
        "Was soll anders werden? Sagt es mir, dann schreibe ich sie neu." in t
        for _, t in tg.gesendet
    )
    assert antwort == "Was soll anders werden?"
