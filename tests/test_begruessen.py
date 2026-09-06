"""scripts/begruessen.py -- aktive Erstkontakt-Begruessung ohne eingehende
Nachricht (05.09.2026, Birk: der Chat soll die Frauen schon begruesst haben,
wenn sie hineinschauen).

Alles mit Telegram-Attrappe, das Skript darf im Test nie ins Netz.
"""

import dataclasses

import pytest

from interview_theater import db, repo
from scripts import begruessen


class TelegramAttrappe:
    """Sammelt, was gesendet wurde -- wie in tests/test_bot.py."""

    def __init__(self):
        self.gesendet = []
        self.mit_knoepfen = []

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        return 500 + len(self.gesendet)

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        message_id = self.sende(chat_id, text)
        self.mit_knoepfen.append((chat_id, text, list(knoepfe_)))
        return message_id


@pytest.fixture
def leere_db(tmp_path):
    c = db.verbinde(str(tmp_path / "b.db"))
    db.initialisiere(c)
    return c


def test_begruesst_eine_unbekannte_gruppe_mit_link_und_knoepfen(leere_db, einst):
    mit_web = dataclasses.replace(einst, web_url="https://lab.test/theatersoap")
    tg = TelegramAttrappe()

    assert begruessen.begruesse(leere_db, tg, mit_web, -777) is True

    assert len(tg.gesendet) == 1
    text = tg.gesendet[0][1]
    token = repo.stelle_web_token_sicher(leere_db, -777)
    assert token is not None
    assert f"https://lab.test/theatersoap/g/{token}" in text, "der Link ist der Zweck der Uebung"
    assert tg.mit_knoepfen, "die Einstiegsknoepfe haengen darunter wie im Betrieb"

    # Die Gruppenzeile gehoert dem Bot der geladenen Env.
    zeile = leere_db.execute("SELECT bot_name FROM gruppe WHERE chat_id = -777").fetchone()
    assert zeile["bot_name"] == mit_web.bot_name

    # Als Bot-Nachricht mitgeschrieben -- sonst schickt der laufende Bot sie
    # beim ersten eingehenden Update ein zweites Mal.
    gemerkt = leere_db.execute(
        "SELECT text FROM nachricht WHERE chat_id = -777 AND ist_bot = 1"
    ).fetchone()
    assert gemerkt is not None
    assert gemerkt["text"] == text


def test_zweiter_aufruf_sendet_nichts(leere_db, einst):
    tg = TelegramAttrappe()
    assert begruessen.begruesse(leere_db, tg, einst, -778) is True
    assert begruessen.begruesse(leere_db, tg, einst, -778) is False, "schon begruesst"
    assert len(tg.gesendet) == 1


def test_bestehende_bot_nachricht_verhindert_die_begruessung(leere_db, einst):
    """Der Bot war schon dran: dann darf das Skript nicht dazwischenfunken."""
    repo.sichere_gruppe(leere_db, -779, einst.bot_name, "Gruppe 1")
    repo.merke_nachricht(
        leere_db, -779, 42, einst.bot_name, 1, "text", "Hallo schon mal", repo._jetzt(),
    )
    tg = TelegramAttrappe()

    assert begruessen.begruesse(leere_db, tg, einst, -779) is False
    assert tg.gesendet == []
