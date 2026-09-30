"""Begruessung, Hilfe, Stand und Phasenrahmen auf Englisch (Karte A1)."""

import pytest

from interview_theater import befehle, bot, leitfaden, phasentexte, repo, sprache, workshop
from simulation.attrappe import TelegramAttrappe


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def test_hilfe_auf_englisch(conn, einst, padua):
    tg = TelegramAttrappe()
    befehle.behandle(conn, tg, einst, 1, "/hilfe", None)
    assert tg.texte()[-1].startswith("Just write or speak")


def test_menue_behaelt_die_befehlsnamen(padua):
    deutsch = [b["command"] for b in befehle.BEFEHLE_LISTE]
    assert [b["command"] for b in befehle.T.BEFEHLE_LISTE] == deutsch


def test_eintrittskopf_auf_englisch(conn, padua):
    assert phasentexte.T._ZEILE_CHECKLISTE.startswith("What it takes:")
    assert "noch" not in " ".join(phasentexte.checkliste(conn, 1, 2).split())


def test_leitfaden_leer_auf_englisch(conn, padua):
    assert leitfaden.T.TEXT_LEER.startswith("I don't have an interview guide yet")


def test_leitfaden_schon_gezeigt_erkennt_beide_sprachfassungen(conn, padua):
    """Nachbesserung Aufgabe 14: ein Journaleintrag unter dem deutschen
    Marker (etwa aus einer Zeit vor dem Profilwechsel) muss den Leitfaden
    unter Englisch weiterhin als 'schon gezeigt' erkennen -- sonst schickt
    ein Profilwechsel ihn ein zweites Mal."""
    chat_id = 1
    assert leitfaden.T.JOURNAL_GEZEIGT != leitfaden.JOURNAL_GEZEIGT
    repo.schreibe_journal(
        conn, chat_id, "notiert", leitfaden.JOURNAL_GEZEIGT, quelle="leitfaden",
    )
    assert leitfaden._schon_gezeigt(conn, chat_id) is True


def test_dortmund_unveraendert(conn, einst):
    tg = TelegramAttrappe()
    befehle.behandle(conn, tg, einst, 1, "/hilfe", None)
    assert tg.texte()[-1] == befehle._TEXT_HILFE
