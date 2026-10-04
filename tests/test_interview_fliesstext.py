"""Padua: ein Interview = EINE Transkriptblase im Web-Chat (Karte
t_ea994c7f, ``[interview] fliesstext``). Telegram und das Vorgabeprofil
bleiben beim Echo je Teil."""

import inspect
import re
import threading
import time

import pytest

from interview_theater import (
    aufnahme, db, phasen, repo, sprache, telegram, web_daten, web_kanal, workshop,
)
from tests.test_aufnahme import (
    LLMAttrappe, TEIL_A, TEIL_B, TelegramAttrappe, interview_an, sprachnachricht,
    stt_attrappe,
)

#: Vier Teile ohne die Woerter "Teil"/"part" -- der Test sucht genau die.
TEILE = [
    "Ich kam im Winter an.",
    "Der Bahnhof war leer.",
    "Niemand hat gewartet.",
    "Dann kam meine Tante.",
]


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    # Phase 3: in Padua liefe eine Sprachnachricht in Phase 1 sonst in die
    # Hintergrund-Diskussion ([diskussion] aktiv).
    phasen.setze(c, 1, 3, "befehl")
    return c


@pytest.fixture
def klm():
    return LLMAttrappe()


class _Kanal(web_kanal.WebKanal):
    """Der echte WebKanal (schreibt ``web_post``), nur ohne Upload-Verzeichnis:
    ``lade_datei`` legt eine fingierte Audiodatei hin wie die
    TelegramAttrappe aus ``tests/test_aufnahme.py``."""

    def lade_datei(self, file_id, ziel):
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"OggS-fingierte-audiodaten")


@pytest.fixture
def web(conn, tmp_path):
    repo.setze_gruppe_kanal(conn, 1, "web")
    return _Kanal(conn, 1, str(tmp_path / "audio"), schritt_s=0.01)


@pytest.fixture
def fliesstext(monkeypatch):
    monkeypatch.setattr(workshop, "interview_fliesstext", lambda profil=None: True)


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _interview(conn, kanal, einst, klm, texte, message_id=600):
    """Modus an, je Text eine Sprachnachricht durch den echten Weg
    (``empfange`` + ``verarbeite``). Liefert die id des Kopfes."""
    kopf_id = interview_an(conn)
    for i, text in enumerate(texte):
        aid = aufnahme.empfange(
            conn, kanal, einst, sprachnachricht(dauer=20, message_id=message_id + i)
        )
        aufnahme.verarbeite(conn, kanal, klm, einst, stt_attrappe(text), aid)
    return kopf_id


def _posts(conn, typ):
    return conn.execute(
        "SELECT * FROM web_post WHERE chat_id = 1 AND richtung = 'aus' AND typ = ? "
        "ORDER BY id", (typ,),
    ).fetchall()


# -- Aufgabe 3: die Kanalflaeche ---------------------------------------------


def test_webkanal_legt_eine_transkriptzeile_an_und_aendert_sie(conn, web):
    mid = web.sende(1, "🎙 Interview 1\n\nHallo", transkript=True)
    zeile = conn.execute("SELECT typ FROM web_post WHERE id = ?", (mid,)).fetchone()
    assert zeile["typ"] == repo.WEB_TYP_TRANSKRIPT == "transkript"

    web.aendere_text(1, mid, "🎙 Interview 1\n\nHallo\n\nWelt")
    zeile = conn.execute("SELECT typ, text, aenderung FROM web_post WHERE id = ?", (mid,)).fetchone()
    assert zeile["typ"] == "transkript", "aendere_text laesst den typ stehen"
    assert zeile["text"].endswith("Welt")
    assert zeile["aenderung"] is not None


def test_der_poll_liefert_die_transkriptzeile_und_ihre_aenderung(conn, web):
    mid = web.sende(1, "🎙 Interview 1\n\nHallo", transkript=True)
    assert [z["typ"] for z in web_daten.web_chatverlauf(conn, 1) if z["id"] == mid] == ["transkript"]

    web.aendere_text(1, mid, "🎙 Interview 1\n\nHallo\n\nWelt")
    geaendert, _stand = web_daten.web_chataenderungen(conn, 1, 0)
    assert mid in [z["id"] for z in geaendert]


def test_telegram_kennt_transkript_als_no_op():
    parameter = inspect.signature(telegram.Telegram.sende).parameters
    assert parameter["transkript"].default is False
    assert list(parameter)[-2:] == ["system", "transkript"]
