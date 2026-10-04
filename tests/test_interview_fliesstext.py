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


# -- Aufgabe 4: eine Blase je Interview --------------------------------------


def test_vier_teile_sind_genau_eine_transkriptblase(conn, web, einst, klm, fliesstext):
    _interview(conn, web, einst, klm, TEILE)

    blasen = _posts(conn, repo.WEB_TYP_TRANSKRIPT)
    assert len(blasen) == 1, "eine Blase je Interview, nicht eine je Teil"
    text = blasen[0]["text"]
    assert text == "🎙 Interview 1\n\n" + "\n\n".join(TEILE)
    assert not re.search(r"\b(Teil|part)\b", text)
    assert not any(", Teil " in (p["text"] or "") for p in _posts(conn, repo.WEB_TYP_TEXT))


def test_die_blase_wird_einmal_mitgeschrieben(conn, web, einst, klm, fliesstext):
    """Entscheidung F: die nachricht-Zeile entsteht beim Anlegen, spaetere
    Aenderungen schreiben sie nicht nach (sie steht in keinem Fenster)."""
    kopf_id = _interview(conn, web, einst, klm, TEILE[:3])
    mitschrift = conn.execute(
        "SELECT * FROM nachricht WHERE chat_id = 1 AND typ = 'transkript'"
    ).fetchall()
    assert len(mitschrift) == 1
    assert mitschrift[0]["text"] == "🎙 Interview 1\n\n" + TEILE[0]
    assert repo.echo_message_id(conn, kopf_id) == _posts(conn, repo.WEB_TYP_TRANSKRIPT)[0]["id"]


def test_ohne_schalter_bleibt_es_im_web_ein_echo_je_teil(conn, web, einst, klm):
    _interview(conn, web, einst, klm, TEILE[:2])

    assert _posts(conn, repo.WEB_TYP_TRANSKRIPT) == []
    echos = [p["text"] for p in _posts(conn, repo.WEB_TYP_TEXT) if ", Teil " in (p["text"] or "")]
    assert echos == [
        f"Interview 1, Teil 1:\n{TEILE[0]}",
        f"Interview 1, Teil 2:\n{TEILE[1]}",
    ]


def test_telegram_bleibt_auch_mit_schalter_beim_echo_je_teil(conn, einst, klm, fliesstext):
    tg = TelegramAttrappe()  # hat kein aendere_text -- ein Aufruf waere ein Fehler
    _interview(conn, tg, einst, klm, TEILE[:2])

    assert [t for _, t, _ in tg.mit_knoepfen] == [
        f"Interview 1, Teil 1:\n{TEILE[0]}",
        f"Interview 1, Teil 2:\n{TEILE[1]}",
    ]
    assert all(leiste for _, _, leiste in tg.mit_knoepfen), "die Leiste aus biete_nach_teil bleibt"


# -- Aufgabe 5: Nebenlaeufigkeit ---------------------------------------------


class _LangsamerKanal(_Kanal):
    """Haelt ``sende`` 0,2 s auf -- genug, damit zwei Threads ohne Sperre
    beide "noch keine Blase" lesen und beide eine anlegen."""

    def sende(self, *args, **kw):
        time.sleep(0.2)
        return super().sende(*args, **kw)


def test_zwei_gleichzeitige_teile_ergeben_eine_blase(conn, einst, tmp_path, fliesstext):
    repo.setze_gruppe_kanal(conn, 1, "web")
    kanal = _LangsamerKanal(conn, 1, str(tmp_path / "audio"), schritt_s=0.01)
    kopf_id = interview_an(conn)
    for i, text in enumerate(TEILE[:2]):
        aid = repo.lege_aufnahme_an(
            conn, 1, 700 + i, "teil", "sprache", dauer=5, teil_von=kopf_id,
            status="transkribiert",
        )
        repo.setze_transkript(conn, aid, text)

    start = threading.Barrier(2)

    def lauf():
        start.wait()
        aufnahme._sende_transkript_blase(conn, kanal, einst, 1, kopf_id)

    faeden = [threading.Thread(target=lauf) for _ in range(2)]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join(timeout=10)

    blasen = _posts(conn, repo.WEB_TYP_TRANSKRIPT)
    assert len(blasen) == 1
    assert TEILE[0] in blasen[0]["text"] and TEILE[1] in blasen[0]["text"]
