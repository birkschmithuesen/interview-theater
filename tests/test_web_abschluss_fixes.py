"""Abschlussreview der Karte t_d37deda1 (Padua A2): C1, I1-I5, M4 -- je ein
Test, und je einer, der den Telegram-Weg festhaelt (E1).

Ohne Netz, ohne Browser. Die Reihenfolge-Tests rufen ``hole_updates`` mit
``timeout=0`` -- genau eine Abfrage, dieselbe Form wie in test_web_kanal.py.
"""

import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from interview_theater import (
    aufnahme, bot, db, einstellungen, repo, stt, telegram, web, web_chat,
    web_daten, web_kanal,
)
from scripts import web_gruppe

CHAT = 7_000_000_000_001
TG_CHAT = -100_123


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web-Gruppe")
    repo.setze_gruppe_kanal(verbindung, CHAT, "web")
    return verbindung


@pytest.fixture
def audio(tmp_path):
    return tmp_path / "audio"


@pytest.fixture
def kanal(conn, audio):
    return web_kanal.WebKanal(conn, CHAT, str(audio), schritt_s=0.01)


def _altere(conn, post_id: int, sekunden: float) -> None:
    """Setzt ``erstellt_am`` zurueck -- die Fristen rechnen damit."""
    frueher = datetime.now(timezone.utc) - timedelta(seconds=sekunden)
    conn.execute(
        "UPDATE web_post SET erstellt_am = ? WHERE id = ?",
        (frueher.isoformat(timespec="seconds"), post_id),
    )
    conn.commit()


def _segment(conn, audio: Path, *, mime="audio/webm", mit_datei=True) -> int:
    """Ein Segment, wie ``web_chat._audio`` es anlegt: erst die Zeile, dann
    die Datei, dann der Verweis."""
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE, dauer=5, mime=mime,
    )
    if mit_datei:
        endung = web_kanal.MIME_ERLAUBT[mime]
        ziel = web_kanal.eingangspfad(str(audio), CHAT, post_id, endung)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"\x1a\x45\xdf\xa3" + b"x" * 64)
        repo.setze_web_datei(conn, post_id, str(ziel.resolve()))
    return post_id


def _befehl(conn, text="/fertig") -> int:
    return repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_BEFEHL, text=text,
    )


def _text(conn, text="noch was") -> int:
    return repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text=text,
    )


def _ids(updates) -> list[int]:
    return [u["update_id"] for u in updates]


# -- C1: eine Sprachzeile ohne Datei wird noch nicht ausgeliefert -----------


def test_c1_sprachzeile_ohne_datei_wartet(conn, kanal, audio):
    """Der Webserver legt die Zeile an, BEVOR er die Datei schreibt. Liest
    der Bot dazwischen, darf er die Zeile nicht sehen -- sonst ging WebM als
    ``.ogg`` an Whisper (Falle 3: haengt)."""
    post_id = _segment(conn, audio, mit_datei=False)
    assert kanal.hole_updates(0, timeout=0) == []

    ziel = web_kanal.eingangspfad(str(audio), CHAT, post_id, ".webm")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(b"webm")
    repo.setze_web_datei(conn, post_id, str(ziel))

    updates = kanal.hole_updates(0, timeout=0)
    assert _ids(updates) == [post_id]
    stimme = telegram.lies_nachricht(updates[0])
    assert stimme["endung"] == ".webm"
    assert stimme["file_id"] == f"web:{post_id}.webm"


def test_c1_spaetere_posts_ueberholen_die_wartende_zeile_nicht(conn, kanal, audio):
    """Die Wahl: ``hole_updates`` liefert immer ein lueckenloses Praefix.
    ``bot.schleife`` rueckt den Offset je ausgeliefertem Update vor -- ein
    Text HINTER der wartenden Zeile wuerde sie sonst fuer immer
    ueberspringen."""
    wartend = _segment(conn, audio, mit_datei=False)
    danach = _text(conn)
    assert kanal.hole_updates(0, timeout=0) == []

    ziel = web_kanal.eingangspfad(str(audio), CHAT, wartend, ".webm")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(b"webm")
    repo.setze_web_datei(conn, wartend, str(ziel))

    assert _ids(kanal.hole_updates(0, timeout=0)) == [wartend]
    # Der Text kommt erst, wenn das Segment beim Bot angekommen ist (I1).
    repo.lege_aufnahme_an(conn, CHAT, wartend, "kurz", "sprache")
    assert _ids(kanal.hole_updates(wartend + 1, timeout=0)) == [danach]


def test_c1_endung_kommt_aus_der_spalte_mime(conn, kanal, audio, caplog):
    """Auch eine Zeile, deren Datei nie kam (Webserver abgestuerzt), traegt
    die richtige Endung -- sie steht in ``mime``, nicht erst im Pfad. Nach
    der Frist geht sie trotzdem raus, laut geloggt: ``lade_datei`` wirft,
    und ``aufnahme`` bittet die Gruppe, es nochmal zu schicken."""
    post_id = _segment(conn, audio, mime="audio/mp4", mit_datei=False)
    _altere(conn, post_id, web_kanal.DATEI_FRIST_S + 5)
    with caplog.at_level(logging.WARNING, logger="interview_theater.web_kanal"):
        updates = kanal.hole_updates(0, timeout=0)
    assert _ids(updates) == [post_id]
    assert telegram.lies_nachricht(updates[0])["endung"] == ".m4a"
    assert str(post_id) in caplog.text


def test_c1_die_mime_tabelle_steht_an_einer_stelle():
    assert web_chat.MIME_ERLAUBT is web_kanal.MIME_ERLAUBT
    assert web_kanal.endung_fuer_mime("audio/webm;codecs=opus") == ".webm"
    assert web_kanal.endung_fuer_mime("audio/x-unbekannt") is None


# -- I1: /fertig ueberholt das letzte Segment nicht ------------------------


def test_i1_befehl_wartet_bis_alle_frueheren_segmente_angekommen_sind(conn, kanal, audio):
    """Zwei Segmente und /fertig im SELBEN Stapel. Ohne Wartepunkt laufen
    alle drei parallel im Pool (bot.POOL_GROESSE), und /fertig kann das
    zweite Segment ueberholen: ``klasse_fuer`` liest den Modus erst bei der
    Verarbeitung, ``hat_offene_teile`` sieht nur existierende Zeilen."""
    erstes = _segment(conn, audio)
    zweites = _segment(conn, audio)
    fertig = _befehl(conn, "/fertig")
    danach = _text(conn)

    # Der Stapel endet VOR dem Befehl.
    assert _ids(kanal.hole_updates(0, timeout=0)) == [erstes, zweites]

    # Erst ein Segment angekommen: weiter warten -- und der Text dahinter
    # ueberholt den Befehl nicht.
    repo.lege_aufnahme_an(conn, CHAT, erstes, "teil", "sprache")
    assert kanal.hole_updates(zweites + 1, timeout=0) == []

    repo.lege_aufnahme_an(conn, CHAT, zweites, "teil", "sprache")
    assert _ids(kanal.hole_updates(zweites + 1, timeout=0)) == [fertig, danach]


def test_i1_auch_ein_knopfdruck_wartet(conn, kanal, audio):
    """"Aufnahme beenden" als Knopf hat denselben Wettlauf wie /fertig."""
    segment = _segment(conn, audio)
    druck = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_KNOPF, daten="k:1",
        bezug_message_id=1,
    )
    assert _ids(kanal.hole_updates(0, timeout=0)) == [segment]
    assert kanal.hole_updates(segment + 1, timeout=0) == []
    repo.lege_aufnahme_an(conn, CHAT, segment, "teil", "sprache")
    assert _ids(kanal.hole_updates(segment + 1, timeout=0)) == [druck]


def test_i1_ein_endgueltig_gescheiterter_download_gibt_frei(conn, kanal, audio, tmp_path, monkeypatch):
    """Das Kennzeichen fuer "endgueltig gescheitert" ist der Vorfall, den
    ``aufnahme.empfange`` schreibt -- hier ueber den ECHTEN Weg erzeugt, damit
    eine Aenderung am Wortlaut dort diesen Test bricht."""
    monkeypatch.setattr(stt, "WARTEZEITEN", ())
    segment = _segment(conn, audio, mit_datei=False)
    # Eine Datei ausserhalb von IT_AUDIO: lade_datei wirft.
    fremd = tmp_path / "fremd.webm"
    fremd.write_bytes(b"x")
    repo.setze_web_datei(conn, segment, str(fremd))
    fertig = _befehl(conn)

    updates = kanal.hole_updates(0, timeout=0)
    assert _ids(updates) == [segment]
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe1", db_pfad="", audio_verz=str(audio),
        llm_url="u", llm_key="k", llm_modell="m", stt_basis="b", stt_produkt="p",
        kanal=einstellungen.KANAL_WEB, web_chat_id=CHAT,
    )
    assert aufnahme.empfange(conn, kanal, e, telegram.lies_nachricht(updates[0])) is None

    assert _ids(kanal.hole_updates(segment + 1, timeout=0)) == [fertig]


def test_i1_befehl_wartet_nicht_ewig(conn, kanal, audio, caplog):
    segment = _segment(conn, audio)
    fertig = _befehl(conn)
    _altere(conn, segment, web_kanal.ANKUNFT_FRIST_S + 5)
    with caplog.at_level(logging.WARNING, logger="interview_theater.web_kanal"):
        assert _ids(kanal.hole_updates(segment + 1, timeout=0)) == [fertig]
    assert str(segment) in caplog.text


def test_i1_segmente_anderer_gruppen_halten_nichts_auf(conn, kanal, audio):
    repo.sichere_gruppe(conn, CHAT + 1, "gruppe2", "Andere")
    repo.lege_web_post_an(
        conn, CHAT + 1, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE, dauer=5,
        mime="audio/webm", datei="/irgendwo.webm",
    )
    fertig = _befehl(conn)
    assert _ids(kanal.hole_updates(0, timeout=0)) == [fertig]


# -- I2: der Offset eines frueheren Telegram-Bots ---------------------------


def test_i2_web_gruppe_anlegen_setzt_den_offset_auf_null(conn):
    repo.setze_update_id(conn, "gruppe4", 123_456_789)
    web_gruppe.lege_an(conn, "gruppe4", "D", "")
    assert repo.hole_update_id(conn, "gruppe4") == 0


def _einst(tmp_path, kanal=einstellungen.KANAL_WEB):
    return einstellungen.Einstellungen(
        bot_token="1:a", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"), llm_url="u", llm_key="k",
        llm_modell="m", stt_basis="b", stt_produkt="p",
        kanal=kanal, web_chat_id=CHAT if kanal == einstellungen.KANAL_WEB else None,
    )


def test_i2_baue_kanal_setzt_einen_telegram_offset_laut_zurueck(conn, tmp_path, caplog):
    erste = _text(conn, "hallo")
    repo.setze_update_id(conn, "gruppe1", 987_654_321)
    with caplog.at_level(logging.WARNING, logger="interview_theater.bot"):
        kanal = bot.baue_kanal(conn, _einst(tmp_path), klient=None)
    assert repo.hole_update_id(conn, "gruppe1") == 0
    assert "987654321" in caplog.text
    # ... und der Bot hoert danach wirklich, was schon im Eingang liegt.
    assert _ids(kanal.hole_updates(repo.hole_update_id(conn, "gruppe1") + 1, timeout=0)) == [erste]


def test_i2_ein_gueltiger_offset_bleibt_stehen(conn, tmp_path):
    _text(conn)
    zweite = _text(conn)
    repo.setze_update_id(conn, "gruppe1", zweite)
    bot.baue_kanal(conn, _einst(tmp_path), klient=None)
    assert repo.hole_update_id(conn, "gruppe1") == zweite


def test_i2_telegram_offset_bleibt_ohne_web_kanal_unberuehrt(conn, tmp_path):
    """E1: ohne IT_KANAL fasst baue_kanal den Offset nicht an."""
    repo.setze_update_id(conn, "gruppe1", 987_654_321)
    assert isinstance(
        bot.baue_kanal(conn, _einst(tmp_path, kanal=einstellungen.KANAL_TELEGRAM), klient=None),
        telegram.Telegram,
    )
    assert repo.hole_update_id(conn, "gruppe1") == 987_654_321


def test_i2_web_post_ids_werden_nie_wiederverwendet(conn):
    """AUTOINCREMENT: verschwindet die hoechste Zeile (Loeschweg einer
    Gruppe), bekommt die naechste trotzdem eine neue id -- sonst laege sie
    unter dem Offset eines Bots, der die alte schon gesehen hat."""
    repo.sichere_gruppe(conn, CHAT + 1, "gruppe2", "Andere")
    _text(conn)
    fremd = repo.lege_web_post_an(
        conn, CHAT + 1, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text="x",
    )
    db.loesche_gruppe(conn, CHAT + 1)
    assert _text(conn) > fremd
    assert repo.hoechste_web_post_id(conn) > fremd


# -- I3: Chat-Link und Chat-Wege nur fuer Web-Gruppen -----------------------


SCHLUESSEL = b"x" * 32


@pytest.fixture
def server(tmp_path):
    pfad = str(tmp_path / "s.db")
    verbindung = db.verbinde(pfad)
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web")
    repo.setze_gruppe_kanal(verbindung, CHAT, "web")
    repo.sichere_gruppe(verbindung, TG_CHAT, "gruppe2", "Telegram")
    web_token = repo.stelle_web_token_sicher(verbindung, CHAT)
    tg_token = repo.stelle_web_token_sicher(verbindung, TG_CHAT)
    verbindung.close()
    dienst = web.baue_server(pfad, "127.0.0.1:0", "/theatersoap", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{dienst.server_address[1]}", web_token, tg_token, pfad
    dienst.shutdown()
    dienst.server_close()


def _hole(url):
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def _status_post(url, koerper: bytes, typ="application/json"):
    anfrage = urllib.request.Request(url, data=koerper, headers={"Content-Type": typ},
                                     method="POST")
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            return antwort.status
    except urllib.error.HTTPError as fehler:
        return fehler.code


def test_i3_telegram_gruppe_hat_keinen_chat_link(server):
    basis, web_token, tg_token, _pfad = server
    _s, seite = _hole(f"{basis}/g/{tg_token}")
    assert f"{tg_token}/{web_chat.CHAT_PFAD}" not in seite
    _s, seite = _hole(f"{basis}/g/{web_token}")
    assert f"{web_token}/{web_chat.CHAT_PFAD}" in seite


def test_i3_chat_get_ist_fuer_telegram_gruppen_404(server):
    basis, web_token, tg_token, _pfad = server
    for unter in ("chat", "chat/zustand?nach=0", "chat/datei/1"):
        with pytest.raises(urllib.error.HTTPError) as fehler:
            _hole(f"{basis}/g/{tg_token}/{unter}")
        assert fehler.value.code == 404, unter
    assert _hole(f"{basis}/g/{web_token}/chat")[0] == 200
    assert _hole(f"{basis}/g/{web_token}/chat/zustand?nach=0")[0] == 200


def test_i3_chat_post_ist_fuer_telegram_gruppen_404_und_schreibt_nichts(server):
    basis, web_token, tg_token, pfad = server
    nonce = web.nonce(SCHLUESSEL, tg_token)
    koerper = json.dumps({"nonce": nonce, "text": "hallo"}).encode("utf-8")
    assert _status_post(f"{basis}/g/{tg_token}/chat/senden", koerper) == 404
    assert _status_post(
        f"{basis}/g/{tg_token}/chat/audio?nonce={nonce}&dauer=3", b"\x1a\x45\xdf\xa3",
        "audio/webm",
    ) == 404
    # Gegenprobe: die Web-Gruppe nimmt an.
    koerper = json.dumps({"nonce": web.nonce(SCHLUESSEL, web_token), "text": "hallo"})
    assert _status_post(f"{basis}/g/{web_token}/chat/senden", koerper.encode("utf-8")) == 202

    lesend = web_daten.oeffne_lesend(pfad)
    try:
        zeilen = lesend.execute("SELECT chat_id FROM web_post").fetchall()
    finally:
        lesend.close()
    assert [z["chat_id"] for z in zeilen] == [CHAT]


def test_i3_chatzustand_kennt_nur_web_gruppen(server):
    _basis, web_token, tg_token, pfad = server
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        assert web_daten.web_chatzustand(lesend, tg_token) is None
        assert web_daten.web_chatzustand(lesend, web_token)["chat_id"] == CHAT
        # Die anderen Wege (Textbuch, Gruppenseite) bleiben fuer beide.
        assert web_daten.chat_id_nach_token(lesend, tg_token) == TG_CHAT
        assert web_daten.gruppe_nach_token(lesend, tg_token)["kanal"] == "telegram"
    finally:
        lesend.close()


# -- I4: keine Nachzuegler im Web --------------------------------------------


def test_i4_web_sammelt_keine_nachzuegler_ein(conn):
    """Im Web ist eine PTT-Nachricht ausdruecklich "an den Bot" -- sie
    gehoert nicht ins naechste Interview."""
    zuruf = repo.lege_aufnahme_an(conn, CHAT, 950, "kurz", "sprache")
    kopf_id = aufnahme.stelle_interview_sicher(conn, CHAT)
    assert repo.hole_aufnahme(conn, zuruf)["teil_von"] is None
    assert repo.hole_aufnahme(conn, zuruf)["klasse"] == "kurz"
    assert repo.hole_teile(conn, kopf_id) == []


def test_i4_telegram_sammelt_weiter_nachzuegler_ein(conn):
    """E1: bitgleich -- mit Gruppenzeile (kanal='telegram') und ohne."""
    repo.sichere_gruppe(conn, TG_CHAT, "gruppe2", "Telegram")
    for chat in (TG_CHAT, 42):
        gesprochen = repo.lege_aufnahme_an(conn, chat, 950, "kurz", "sprache")
        kopf_id = aufnahme.stelle_interview_sicher(conn, chat)
        assert repo.hole_aufnahme(conn, gesprochen)["teil_von"] == kopf_id
        assert repo.hole_aufnahme(conn, gesprochen)["klasse"] == "teil"


# -- I5: der Webserver speichert absolute Pfade ------------------------------


def test_i5_upload_pfad_ist_absolut(tmp_path, monkeypatch):
    """Der Bot loest gegen SEIN IT_AUDIO und sein Arbeitsverzeichnis auf.
    Ein relativer Pfad in ``web_post.datei`` hinge damit am cwd zweier
    Prozesse."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("IT_AUDIO", "audio-relativ")
    pfad = str(tmp_path / "s.db")
    verbindung = db.verbinde(pfad)
    db.initialisiere(verbindung)
    repo.sichere_gruppe(verbindung, CHAT, "gruppe1", "Web")
    repo.setze_gruppe_kanal(verbindung, CHAT, "web")
    token = repo.stelle_web_token_sicher(verbindung, CHAT)
    dienst = web.baue_server(pfad, "127.0.0.1:0", "", schluessel=SCHLUESSEL)
    threading.Thread(target=dienst.serve_forever, daemon=True).start()
    try:
        basis = f"http://127.0.0.1:{dienst.server_address[1]}"
        nonce = web.nonce(SCHLUESSEL, token)
        assert _status_post(
            f"{basis}/g/{token}/chat/audio?nonce={nonce}&dauer=3",
            b"\x1a\x45\xdf\xa3" + b"x" * 32, "audio/webm;codecs=opus",
        ) == 202
    finally:
        dienst.shutdown()
        dienst.server_close()
    datei = verbindung.execute("SELECT datei FROM web_post").fetchone()["datei"]
    verbindung.close()
    assert Path(datei).is_absolute()
    assert Path(datei) == (tmp_path / "audio-relativ").resolve() / str(CHAT) / \
        web_kanal.EINGANG_VERZ / Path(datei).name
    assert Path(datei).is_file()


def test_i5_web_unit_setzt_it_audio():
    vorlage = (Path(__file__).resolve().parent.parent / "docs"
               / "interview-theater-web.service").read_text(encoding="utf-8")
    assert "Environment=IT_AUDIO=" in vorlage


# -- M4: lade_datei bleibt in der eigenen Gruppe ----------------------------


def test_m4_lade_datei_nimmt_keine_fremde_gruppe(conn, kanal, audio, tmp_path):
    repo.sichere_gruppe(conn, CHAT + 1, "gruppe2", "Andere")
    fremd = repo.lege_web_post_an(
        conn, CHAT + 1, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE, dauer=5,
        mime="audio/webm",
    )
    ziel = web_kanal.eingangspfad(str(audio), CHAT + 1, fremd, ".webm")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(b"fremdes Material")
    repo.setze_web_datei(conn, fremd, str(ziel))
    with pytest.raises(ValueError):
        kanal.lade_datei(web_kanal.datei_verweis(fremd, ".webm"), tmp_path / "x.webm")
    assert not (tmp_path / "x.webm").exists()
