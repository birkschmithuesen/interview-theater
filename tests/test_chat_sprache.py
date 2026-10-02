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


from interview_theater import aufnahme, erkenner, kontext, stile  # noqa: E402,F401


def test_notiert_zeile_auf_englisch(padua):
    meldung = erkenner.baue_meldung([{"art": "begriffe_setzen", "wert": "love, anger"}])
    assert meldung.startswith("Noted:")


def test_bot_heisst_im_verlauf_you(padua):
    assert kontext.sprecherzeile({"ist_bot": 1, "absender": "x", "text": "hi", "typ": "text"}) == "You: hi"


def test_bot_heisst_im_verlauf_weiter_du():
    assert kontext.sprecherzeile({"ist_bot": 1, "absender": "x", "text": "hi", "typ": "text"}) == "Du: hi"


def test_foto_ohne_transkript_ist_fuer_englisch_als_nicht_sichtbar_markiert(padua):
    """Padua Hotfix Befund 2 (02.10.2026): das Gespraechsmodell sieht keine
    Bilder. Vor dem Fix erschien eine Foto-Nachricht wortgleich mit ihrem
    (immer deutschen) Telegram-Typnamen, auch im englischen Prompt --
    "Maria: (foto)". Jetzt steht dort ein lokalisierter Hinweis, dass das
    Modell die Datei nicht sieht."""
    zeile = kontext.sprecherzeile(
        {"ist_bot": 0, "absender": "Maria", "text": None, "typ": "foto"})
    assert zeile == "Maria: (file -- not visible to you)"


def test_sticker_ohne_transkript_ist_fuer_englisch_als_nicht_sichtbar_markiert(padua):
    zeile = kontext.sprecherzeile(
        {"ist_bot": 0, "absender": "Maria", "text": None, "typ": "sticker"})
    assert zeile == "Maria: (file -- not visible to you)"


def test_stile_zeigen_englisch_aber_gleiche_slugs(padua):
    assert [s["slug"] for s in stile.T.STILE] == [s["slug"] for s in stile.STILE]


def test_vorlauf_ueberspringt_auch_englische_notiert_zeilen(conn):
    """Rundreise: repo.letzte_bot_nachricht_vor filtert die Meldung des
    Erkenners heraus -- in Padua beginnt sie mit "Noted:" statt "Notiert:"."""
    repo.sichere_gruppe(conn, 1, "bot", "g")
    repo.merke_nachricht(conn, 1, 10, "Bot", 1, "text", "Suggestion: Mira.", "2026-09-05T04:00:00+00:00")
    repo.merke_nachricht(conn, 1, 11, "Bot", 1, "text", "Noted:\nTerms: x", "2026-09-05T04:00:01+00:00")
    assert repo.letzte_bot_nachricht_vor(conn, 1, 12)["message_id"] == 10
