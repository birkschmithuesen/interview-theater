"""Welche Sprache Whisper hoert: der Gruppenwert vor dem Profilwert (D2)."""

import pytest

from interview_theater import aufnahme, db, repo, stt, workshop


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    yield
    workshop.vergiss()


def test_neue_spalte_ist_zuerst_leer(conn):
    assert repo.stt_sprache(conn, 1) is None


def test_setzen_und_zuruecknehmen(conn):
    repo.setze_stt_sprache(conn, 1, "it")
    assert repo.stt_sprache(conn, 1) == "it"
    repo.setze_stt_sprache(conn, 1, None)
    assert repo.stt_sprache(conn, 1) is None


def test_alte_datenbank_bekommt_die_spalte(tmp_path):
    c = db.verbinde(str(tmp_path / "alt.db"))
    c.execute("CREATE TABLE gruppe (chat_id INTEGER PRIMARY KEY, bot_name TEXT NOT NULL)")
    c.commit()
    db.initialisiere(c)
    spalten = {z[1] for z in c.execute("PRAGMA table_info(gruppe)")}
    assert "stt_sprache" in spalten


def test_ohne_gruppenwert_gilt_das_profil(conn, monkeypatch):
    assert aufnahme.whisper_sprache(conn, 1) == "de"
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert aufnahme.whisper_sprache(conn, 1) == "auto"


def test_gruppenwert_schlaegt_profil(conn, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    repo.setze_stt_sprache(conn, 1, "it")
    assert aufnahme.whisper_sprache(conn, 1) == "it"


def test_die_aufnahme_reicht_die_sprache_an_whisper(conn, einst, tmp_path, monkeypatch):
    gesehen = []

    def transkribiere(e, klient, pfad, budget, *, sprache="de"):
        gesehen.append(sprache)
        return "Ciao."

    monkeypatch.setattr(stt, "transkribiere", transkribiere)
    repo.setze_stt_sprache(conn, 1, "auto")

    class TG:
        def tippt(self, chat_id): pass
        def sende(self, chat_id, text): return 1

    zeile = {"id": 1, "chat_id": 1, "klasse": "kurz",
             "audio_pfad": str(tmp_path / "a.ogg")}
    assert aufnahme._transkribiere_mit_meldung(conn, TG(), einst, None, zeile) == "Ciao."
    assert gesehen == ["auto"]
