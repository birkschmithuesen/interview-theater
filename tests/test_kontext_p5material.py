"""Testbot-Karte (Birk/Robo 07.10.2026, 13:33): ab Phase 5 sah der Chat auf
dem Opus-Pfad fast kein Interviewmaterial (0 Kernthemen, 0 Kernzitate),
waehrend die Werkbank alles zeigte. Mit Zustimmung (``ueber_claude=True``)
und dem Profilschalter ``modellwahl.vollmaterial_phase5`` bekommt der Chat
ab Phase 5 zusaetzlich ALLE Verdichtungen (mit Themen und Belegzitaten) und
das volle, nicht gekappte Mitgehoert-Transkript aus Phase 1/4. Kimi-Pfad und
Dortmund/Vorgabeprofil bleiben unberuehrt."""

from datetime import datetime, timedelta, timezone

import pytest

from interview_theater import db, einstellungen, kontext, phasen, repo, workshop


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
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


@pytest.fixture
def an(monkeypatch):
    """Profilschalter an, ohne eine echte TOML-Datei zu brauchen."""
    monkeypatch.setattr(workshop, "vollmaterial_phase5_aktiv", lambda profil=None: True)


BASIS = datetime(2026, 9, 6, 10, 0, 0, tzinfo=timezone.utc)


def _iso(versatz_minuten: int) -> str:
    return (BASIS + timedelta(minutes=versatz_minuten)).isoformat(timespec="seconds")


def _sende(conn, chat_id, message_id, absender, text, gesendet_am):
    repo.merke_nachricht(conn, chat_id, message_id, absender, 0, "text", text, gesendet_am)
    return repo.hole_nachricht(conn, chat_id, message_id)


def _verdichtetes_interview(conn, chat_id=1, name="Maria"):
    """Eine Verdichtung mit ZWEI Themen, KEINES als Kernthema markiert --
    genau die Padua-Lage ("0 Themen zum_kernthema, 0 Kernzitate")."""
    repo.merke_nachricht(conn, chat_id, 90, "Ada", 0, "sprache", None, _iso(0))
    aufnahme_id = repo.lege_aufnahme_an(conn, chat_id, 90, "lang", "sprache", "/tmp/a.ogg", 300)
    repo.setze_aufnahme_name(conn, aufnahme_id, name)
    repo.speichere_verdichtung(
        conn, chat_id, aufnahme_id,
        "Maria erzaehlt von der Ankunft 1998 und vom ersten Winter.",
        [
            {"thema": "Ankommen", "beleg_zitat": "Ich hatte nur einen Koffer",
             "zitat_geprueft": 1},
            {"thema": "Arbeit", "beleg_zitat": None, "zitat_geprueft": 0},
        ],
    )
    return aufnahme_id


def _mitgehoertes_segment(conn, chat_id, mid, text, gesendet_am, *, brainstorm):
    repo.merke_nachricht(conn, chat_id, mid, "Gruppe", 0, "sprache", None, gesendet_am, 1)
    aid = repo.lege_aufnahme_an(conn, chat_id, mid, "kurz", "sprache", status="transkribiert",
                                diskussion=not brainstorm, brainstorm=brainstorm,
                                schnittgrund="pause")
    repo.setze_transkript(conn, aid, text)
    repo.setze_status(conn, aid, "fertig")


def test_phase_5_mit_zustimmung_zeigt_alle_verdichtungen(conn, einst, an):
    _verdichtetes_interview(conn)
    phasen.setze(conn, 1, 5, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Was steckt da drin?", _iso(1))]

    prompt = kontext.baue(conn, 1, ausloeser, einst, ueber_claude=True)

    assert "Verdichtungen:" in prompt
    assert '- Ankommen: "Ich hatte nur einen Koffer"' in prompt
    assert "- Arbeit" in prompt


def test_phase_4_bleibt_ohne_vollmaterial(conn, einst, an):
    """Phase 4 bleibt die Erfindungsphase -- ``kernpaket_erlaubt`` ist dort
    falsch, der neue Block darf also nicht greifen, egal ob Opus oder nicht."""
    _verdichtetes_interview(conn)
    phasen.setze(conn, 1, 4, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Was steckt da drin?", _iso(1))]

    prompt = kontext.baue(conn, 1, ausloeser, einst, ueber_claude=True)

    assert "Verdichtungen:" not in prompt
    assert "Ich hatte nur einen Koffer" not in prompt


def test_phase_5_ohne_claude_pfad_bleibt_unveraendert(conn, einst, an):
    """Kimi-Pfad (keine Zustimmung/kein ``ueber_claude``): heutiges
    Verhalten bleibt stehen, auch mit dem Profilschalter an."""
    _verdichtetes_interview(conn)
    phasen.setze(conn, 1, 5, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Was steckt da drin?", _iso(1))]

    prompt = kontext.baue(conn, 1, ausloeser, einst)

    assert "Verdichtungen:" not in prompt
    assert "Ich hatte nur einen Koffer" not in prompt


def test_phase_5_ohne_profilschalter_bleibt_unveraendert(conn, einst):
    """Dortmund/Vorgabeprofil (kein Schalter gesetzt): byte-gleich, auch auf
    dem Opus-Pfad."""
    _verdichtetes_interview(conn)
    phasen.setze(conn, 1, 5, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Was steckt da drin?", _iso(1))]

    prompt = kontext.baue(conn, 1, ausloeser, einst, ueber_claude=True)

    assert "Verdichtungen:" not in prompt
    assert "Ich hatte nur einen Koffer" not in prompt


def test_phase_5_mit_zustimmung_zeigt_volles_mitgehoert_ueber_der_grenze(conn, einst, an, monkeypatch):
    """G3-Lage: zusammen weit ueber den 60.000 Zeichen -- auf dem Opus-Pfad
    bleibt das AELTESTE trotzdem stehen, statt vorn wegzufallen."""
    monkeypatch.setattr(kontext, "MITGEHOERT_ZEICHEN", 80)
    _mitgehoertes_segment(conn, 1, 10, "Das Allererste, ganz am Anfang gesagt.",
                          _iso(0), brainstorm=False)
    _mitgehoertes_segment(conn, 1, 11, "Und viel spaeter noch etwas Neues.",
                          _iso(1), brainstorm=True)
    phasen.setze(conn, 1, 5, "befehl")
    ausloeser = [_sende(conn, 1, 1, "Ada", "Und jetzt?", _iso(2))]

    prompt = kontext.baue(conn, 1, ausloeser, einst, ueber_claude=True)

    assert "Das Allererste, ganz am Anfang gesagt." in prompt
    assert "Und viel spaeter noch etwas Neues." in prompt


def test_mitgehoert_grenze_greift_weiter_ohne_voll(conn, monkeypatch):
    """Unveraenderter Kimi-Pfad: ``_baue_mitgehoert`` ohne ``voll`` kappt wie
    bisher."""
    monkeypatch.setattr(kontext, "MITGEHOERT_ZEICHEN", 80)
    _mitgehoertes_segment(conn, 1, 10, "a" * 100, _iso(0), brainstorm=False)
    _mitgehoertes_segment(conn, 1, 11, "b" * 100, _iso(1), brainstorm=True)

    block_gekappt = kontext._baue_mitgehoert(conn, 1)
    block_voll = kontext._baue_mitgehoert(conn, 1, voll=True)

    assert "a" * 100 not in block_gekappt
    assert "a" * 100 in block_voll
