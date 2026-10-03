"""Audio durch die Naht -- und die Endung, an der Falle 3 haengt.

Der gemessene Fall (04.09.2026): ein fest verdrahtetes ``audio/ogg`` fuer eine
WAV-Datei wird vom Anbieter mit einer batch_id quittiert -- kein HTTP-Fehler,
keine Ablehnung -- und der Auftrag bleibt danach dauerhaft auf 'pending':
89,7 s statt 2,0 s, im Betrieb nur als "haengt" sichtbar.

Daraus folgt: die Endung der im Browser aufgenommenen Datei muss bis in
``aufnahme.empfange`` durchkommen, denn dort entsteht der Zielpfad, und
``stt.mime_typ()`` liest nur ihn.
"""

from pathlib import Path

import pytest

from interview_theater import aufnahme, db, repo, stt, telegram, web_kanal

CHAT = 7_000_000_000_001


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web-Gruppe")
    return verbindung


@pytest.fixture
def kanal(conn, tmp_path):
    return web_kanal.WebKanal(conn, CHAT, str(tmp_path / "audio"), schritt_s=0.01)


# -- die additive Erweiterung bleibt bitgleich fuer Telegram ----------------


def test_telegram_sprachnachricht_hat_keine_endung():
    """Bitgleich: ein echtes Telegram-Update traegt kein 'endung', also
    bleibt der Zielpfad ``.ogg`` wie bisher."""
    update = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "chat": {"id": -100123, "title": "Gruppe 1"},
            "from": {"first_name": "Ada"},
            "date": 1_790_000_000,
            "voice": {"file_id": "AwACAgI", "duration": 44},
        },
    }
    gedeutet = telegram.lies_nachricht(update)
    assert gedeutet["endung"] is None
    assert gedeutet["file_id"] == "AwACAgI"
    assert gedeutet["dauer"] == 44


def test_telegram_textnachricht_hat_auch_keine_endung():
    update = {
        "update_id": 1,
        "message": {
            "message_id": 11,
            "chat": {"id": -100123},
            "date": 1_790_000_000,
            "text": "Hallo",
        },
    }
    assert telegram.lies_nachricht(update)["endung"] is None


def test_die_schluesselmenge_waechst_um_genau_einen_eintrag():
    """``lies_nachricht`` ist eine feste Schluesselmenge, mit der der ganze
    Bot arbeitet. Waechst sie, soll man es hier sehen."""
    update = {"update_id": 1, "message": {"message_id": 1,
                                          "chat": {"id": 1}, "date": 1, "text": "x"}}
    assert set(telegram.lies_nachricht(update)) == {
        "chat_id", "chat_titel", "message_id", "absender", "typ", "text",
        "file_id", "dauer", "gesendet_am", "endung",
        # Brainstorm/VAD (02.10.2026): warum das Stueck geschnitten wurde
        # (Pause/Deckel/Ende) und ob es Brainstorm-Mitschrift statt Interview
        # ist -- beide None bei Telegram.
        "schnittgrund", "brainstorm",
        # Diskussion (Task 4, Padua Phase 1+2 Umbau, 03.10.2026): dieselbe
        # additive Durchreiche, Hintergrund-Mithoeren Phase 1 -- False bei
        # Telegram.
        "diskussion",
    }


def test_empfange_legt_ohne_endung_weiter_eine_ogg_datei_ab(conn, tmp_path):
    """Der Telegram-Pfad, unveraendert."""

    class TgAttrappe:
        def lade_datei(self, file_id, ziel):
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(b"OggS")

        def sende(self, chat_id, text, **kw):
            return 1

    class E:
        audio_verz = str(tmp_path / "audio")
        bot_name = "gruppe1"

    nachricht = {
        "chat_id": CHAT, "message_id": 10, "absender": "Ada", "typ": "sprache",
        "text": None, "file_id": "F1", "dauer": 5,
        "gesendet_am": "2026-09-30T10:00:00+00:00", "endung": None,
    }
    aufnahme_id = aufnahme.empfange(conn, TgAttrappe(), E(), nachricht)
    pfad = Path(repo.hole_aufnahme(conn, aufnahme_id)["audio_pfad"])
    assert pfad.suffix == ".ogg"
    assert stt.mime_typ(pfad) == "audio/ogg"


def test_empfange_nimmt_die_endung_aus_der_nachricht(conn, tmp_path):
    """Der Web-Pfad: eine WebM-Datei bekommt einen WebM-Pfad -- und damit den
    richtigen MIME-Typ (Falle 3)."""

    class TgAttrappe:
        def lade_datei(self, file_id, ziel):
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(b"\x1a\x45\xdf\xa3")   # EBML-Kopf

        def sende(self, chat_id, text, **kw):
            return 1

    class E:
        audio_verz = str(tmp_path / "audio")
        bot_name = "gruppe1"

    nachricht = {
        "chat_id": CHAT, "message_id": 11, "absender": web_kanal.ABSENDER,
        "typ": "sprache", "text": None, "file_id": "web:11.webm", "dauer": 45,
        "gesendet_am": "2026-09-30T10:00:00+00:00", "endung": ".webm",
    }
    aufnahme_id = aufnahme.empfange(conn, TgAttrappe(), E(), nachricht)
    pfad = Path(repo.hole_aufnahme(conn, aufnahme_id)["audio_pfad"])
    assert pfad.suffix == ".webm"
    assert stt.mime_typ(pfad) == "audio/webm"


# -- die Verweise ----------------------------------------------------------


@pytest.mark.parametrize("endung", [".webm", ".ogg", ".m4a", ".mp3"])
def test_verweis_hin_und_zurueck(endung):
    verweis = web_kanal.datei_verweis(42, endung)
    assert web_kanal.lies_verweis(verweis) == (42, endung)


@pytest.mark.parametrize("kaputt", ["", "AwACAgI", "web:", "web:abc.webm", None, 7])
def test_lies_verweis_ist_tolerant(kaputt):
    assert web_kanal.lies_verweis(kaputt) is None


# -- lade_datei ------------------------------------------------------------


def test_lade_datei_kopiert_die_hochgeladene_aufnahme(conn, kanal, tmp_path):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
        dauer=45, mime="audio/webm",
        datei=str(web_kanal.eingangspfad(str(tmp_path / "audio"), CHAT, 1, ".webm")),
    )
    quelle = Path(repo.hole_web_post(conn, post_id)["datei"])
    quelle.parent.mkdir(parents=True, exist_ok=True)
    quelle.write_bytes(b"\x1a\x45\xdf\xa3segment")

    ziel = tmp_path / "audio" / str(CHAT) / f"{post_id}.webm"
    kanal.lade_datei(web_kanal.datei_verweis(post_id, ".webm"), ziel)
    assert ziel.read_bytes() == b"\x1a\x45\xdf\xa3segment"


def test_lade_datei_wirft_bei_unbekanntem_verweis(kanal, tmp_path):
    """``aufnahme._lade_mit_wiederholung`` faengt jede Ausnahme und wiederholt
    mit ``stt.WARTEZEITEN``; danach entsteht ein Vorfall und die Gruppe wird
    gebeten, es nochmal zu schicken. Eine Ausnahme ist hier also der richtige
    Ausgang -- stillschweigend eine leere Datei anzulegen waere der falsche:
    daraus wuerde ein Interview mit erfundenem Inhalt."""
    with pytest.raises(Exception):
        kanal.lade_datei("web:999999.webm", tmp_path / "x.webm")


def test_lade_datei_wirft_wenn_die_quelle_fehlt(conn, kanal, tmp_path):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
        datei=str(tmp_path / "gibtsnicht.webm"), mime="audio/webm",
    )
    with pytest.raises(Exception):
        kanal.lade_datei(web_kanal.datei_verweis(post_id, ".webm"),
                         tmp_path / "y.webm")


def test_lade_datei_verlaesst_das_audioverzeichnis_nicht(conn, kanal, tmp_path):
    """Die ``datei``-Spalte wird vom Webserver geschrieben. Ein Pfad, der aus
    dem Audioverzeichnis herausfuehrt, darf nicht kopiert werden -- sonst
    liesse sich ueber einen manipulierten Eintrag jede lesbare Datei des
    Servers in ein Transkript verwandeln."""
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
        datei="/etc/passwd", mime="audio/webm",
    )
    with pytest.raises(Exception):
        kanal.lade_datei(web_kanal.datei_verweis(post_id, ".webm"),
                         tmp_path / "z.webm")


# -- sende_datei -----------------------------------------------------------


def test_sende_datei_legt_die_datei_und_eine_zeile_an(conn, kanal, tmp_path):
    message_id = kanal.sende_datei(
        CHAT, "textbuch.md", "# Unser Stueck\n\nSZENE 1\n", "Das Textbuch",
    )
    zeile = repo.hole_web_post(conn, message_id)
    assert zeile["typ"] == repo.WEB_TYP_DATEI
    assert zeile["dateiname"] == "textbuch.md"
    assert zeile["text"] == "Das Textbuch"
    assert Path(zeile["datei"]).read_text(encoding="utf-8").startswith("# Unser Stueck")


def test_sende_datei_nimmt_auch_bytes(conn, kanal):
    message_id = kanal.sende_datei(CHAT, "t.md", b"roh", "")
    assert Path(repo.hole_web_post(conn, message_id)["datei"]).read_bytes() == b"roh"


def test_sende_datei_saeubert_den_dateinamen(conn, kanal):
    """Der Name kommt aus dem Code, aber der Pfad entsteht daraus -- ein
    ``../`` darin schriebe neben das Audioverzeichnis."""
    message_id = kanal.sende_datei(CHAT, "../../etc/passwd", "x", "")
    pfad = Path(repo.hole_web_post(conn, message_id)["datei"]).resolve()
    assert web_kanal.AUSGANG_VERZ in pfad.parts
    assert ".." not in pfad.parts
