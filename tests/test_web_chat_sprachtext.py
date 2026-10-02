"""Padua Hotfix B7 (02.10.2026): die Sprachblase im Web-Chat zeigt nach der
Transkription den Text -- vorher "transcribing..." (EN) bzw.
"wird abgetippt ..." (DE).

Der Weg ist der vorhandene: ``repo.setze_web_sprachtext`` setzt
``web_post.text`` und zaehlt ``aenderung`` hoch, ``web_daten.web_chataenderungen``
liefert die Zeile neu aus, und der Browser ersetzt die Blase (``ersetze`` im
JS). Aufgerufen aus ``aufnahme._web_sprachblase``, nur im Web-Kanal.
"""

import pytest

from interview_theater import aufnahme, db, einstellungen, repo, sprache, web_chat, web_daten, workshop
from tests.test_aufnahme import (
    TEIL_A, LLMAttrappe, TelegramAttrappe, TelegramKaputterDownload, sprachnachricht,
    stt_attrappe, stt_kaputt,
)

WEB = repo.WEB_CHAT_ID_BASIS


@pytest.fixture
def pfad(tmp_path):
    return str(tmp_path / "t.db")


@pytest.fixture
def einst(tmp_path, pfad):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=pfad,
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(pfad):
    c = db.verbinde(pfad)
    db.initialisiere(c)
    repo.sichere_gruppe(c, WEB, "gruppe1", "Webgruppe")
    repo.setze_gruppe_kanal(c, WEB, "web")
    repo.sichere_gruppe(c, 1, "gruppe2", "Telegramgruppe")
    yield c
    c.close()


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    yield
    workshop.vergiss()
    sprache.vergiss()


def _kein_zug(*_a, **_k):
    return None


def _sprachpost(conn, tg, einst, dauer: int) -> tuple[int, int]:
    """Wie der Webserver (``web_chat._audio``) und der Bot (``aufnahme.empfange``)
    es tun: erst die web_post-Zeile, dann die Aufnahme mit derselben id."""
    post_id = repo.lege_web_post_an(conn, WEB, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
                                    dauer=dauer, mime="audio/webm")
    aid = aufnahme.empfange(conn, tg, einst,
                            sprachnachricht(dauer=dauer, message_id=post_id, chat_id=WEB))
    return post_id, aid


def _lies(pfad, seit):
    lesend = web_daten.oeffne_lesend(pfad)
    try:
        return (web_daten.web_chatverlauf(lesend, WEB),
                web_daten.web_chataenderungen(lesend, WEB, seit))
    finally:
        lesend.close()


def _stand(pfad):
    return _lies(pfad, None)[1][1]


def test_kurze_sprachnachricht_bekommt_ihr_transkript_in_die_blase(conn, pfad, einst, tg):
    post_id, aid = _sprachpost(conn, tg, einst, dauer=5)
    verlauf, _ = _lies(pfad, None)
    assert verlauf[0]["text"] is None
    assert verlauf[0]["abgetippt"] is False, "vor Whisper: Platzhalter"
    stand = _stand(pfad)

    aufnahme.verarbeite(conn, tg, LLMAttrappe(), einst, stt_attrappe("Mach mal lauter"),
                        aid, zug=_kein_zug)

    _, (geaendert, neu) = _lies(pfad, stand)
    assert [z["id"] for z in geaendert] == [post_id], "genau diese Zeile"
    assert geaendert[0]["text"] == "Mach mal lauter"
    assert geaendert[0]["abgetippt"] is True
    assert neu > stand


def test_lange_sprachnachricht_im_web_ist_ein_beitrag_mit_text(conn, pfad, einst, tg):
    """Auf dem Web-Kanal gibt es die Frage \"Ist das ein Interview?\" nicht
    (Phase-3-Web, e468900: PTT und Aufnahme-Regler sind getrennte Knoepfe --
    eine lange PTT-Aufnahme ist unzweideutig ein Beitrag). Der Hotfix-Test
    (B7) nahm hier noch das Telegram-Verhalten an (verstecktes Transkript);
    im Web bekommt die Blase deshalb ihren Text wie jede kurze Nachricht."""
    post_id, aid = _sprachpost(conn, tg, einst, dauer=186)
    stand = _stand(pfad)
    aufnahme.verarbeite(conn, tg, LLMAttrappe(), einst, stt_attrappe("eine lange Erzaehlung"),
                        aid, zug=_kein_zug)

    _, (geaendert, stand2) = _lies(pfad, stand)
    assert [(z["id"], z["text"], z["abgetippt"]) for z in geaendert] == [
        (post_id, "eine lange Erzaehlung", True)
    ]


def test_interview_teil_zeigt_den_text_nicht_doppelt(conn, pfad, einst, tg):
    """Ein Teil hat sein Transkript-Echo als eigene Nachricht -- die Blase
    traegt es nicht noch einmal, verliert aber den Platzhalter."""
    repo.setze_interviewmodus(conn, WEB, repo._jetzt())
    aufnahme.stelle_interview_sicher(conn, WEB)
    post_id, aid = _sprachpost(conn, tg, einst, dauer=42)
    stand = _stand(pfad)
    aufnahme.verarbeite(conn, tg, LLMAttrappe(), einst, stt_attrappe(TEIL_A), aid)

    assert any(TEIL_A in text for _, text in tg.gesendet), "das Echo bleibt"
    _, (geaendert, _) = _lies(pfad, stand)
    assert [(z["id"], z["text"], z["abgetippt"]) for z in geaendert] == [(post_id, None, True)]


def test_endgueltiger_fehlschlag_nimmt_den_platzhalter_weg(conn, pfad, einst, tg):
    post_id, aid = _sprachpost(conn, tg, einst, dauer=5)
    stand = _stand(pfad)
    for _ in range(aufnahme.MAX_VERSUCHE):
        aufnahme.verarbeite(conn, tg, LLMAttrappe(), einst, stt_kaputt(), aid, zug=_kein_zug)
    assert repo.hole_aufnahme(conn, aid)["status"] == "fehlgeschlagen"
    _, (geaendert, _) = _lies(pfad, stand)
    assert [(z["id"], z["text"], z["abgetippt"]) for z in geaendert] == [(post_id, None, True)]


def test_gescheiterter_download_nimmt_den_platzhalter_weg(conn, pfad, einst, monkeypatch):
    """Review-Fund zu B7: scheitert schon der Download endgueltig, entsteht
    keine ``aufnahme``-Zeile (``empfange`` liefert ``None``). Ohne eigenes
    Zeichen hinge die Blase sonst fuer immer auf "transcribing..." -- die
    Gruppe hat die Bitte, es nochmal zu schicken, aber die alte Blase taete so,
    als liefe noch etwas."""
    monkeypatch.setattr(aufnahme.time, "sleep", lambda s: None)
    post_id = repo.lege_web_post_an(conn, WEB, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
                                    dauer=5, mime="audio/webm")
    stand = _stand(pfad)
    aid = aufnahme.empfange(conn, TelegramKaputterDownload(), einst,
                            sprachnachricht(dauer=5, message_id=post_id, chat_id=WEB))
    assert aid is None

    verlauf, (geaendert, _) = _lies(pfad, stand)
    assert [(z["id"], z["text"], z["abgetippt"]) for z in geaendert] == [(post_id, None, True)]
    assert verlauf[0]["abgetippt"] is True, "auch beim Seitenaufbau kein Platzhalter mehr"


def test_unberuehrte_sprachzeile_bleibt_platzhalter(conn, pfad):
    """Gegenprobe: ohne Aufnahme und ohne Aenderung laeuft die Zeile noch
    (die Datei ist unterwegs) -- ``aenderung`` ist bei eingehenden
    Sprachzeilen bis zum ersten ``setze_web_sprachtext`` NULL."""
    post_id = repo.lege_web_post_an(conn, WEB, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
                                    dauer=5, mime="audio/webm")
    repo.setze_web_datei(conn, post_id, "/tmp/x.webm")
    assert conn.execute("SELECT aenderung FROM web_post WHERE id = ?",
                        (post_id,)).fetchone()[0] is None
    verlauf, _ = _lies(pfad, None)
    assert verlauf[0]["abgetippt"] is False


def test_telegram_gruppe_schreibt_nichts_in_web_post(conn, einst, tg, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(repo, "setze_web_sprachtext", lambda *a: aufrufe.append(a))
    aid = aufnahme.empfange(conn, tg, einst, sprachnachricht(dauer=5, message_id=50, chat_id=1))
    aufnahme.verarbeite(conn, tg, LLMAttrappe(), einst, stt_attrappe("hallo"), aid, zug=_kein_zug)
    assert aufrufe == []


# -- Darstellung -------------------------------------------------------------


def _blase(**n):
    zeile = {"id": 7, "von": "gruppe", "typ": "sprache", "text": None, "knoepfe": [],
             "dauer": 5, "dateiname": None}
    zeile.update(n)
    return web_chat._blase_html(zeile)


def test_blase_mit_text_zeigt_kennzeichen_und_maskierten_text():
    html = _blase(text="<b>laut</b> & klar", abgetippt=True)
    assert "🎤 0:05 · &lt;b&gt;laut&lt;/b&gt; &amp; klar" in html
    assert "<b>" not in html


def test_blase_ohne_text_zeigt_den_platzhalter_deutsch():
    assert "0:05 · wird abgetippt …" in _blase(abgetippt=False)
    assert "Sprachnachricht (0:05)" in _blase(abgetippt=True)


def test_blase_ohne_text_zeigt_den_platzhalter_englisch(padua):
    assert "0:05 · transcribing..." in _blase(abgetippt=False)
    assert "Voice message (0:05)" in _blase(abgetippt=True)
    texte = web_chat._js()
    assert '"sprache_laeuft": "{dauer} \\u00b7 transcribing..."' in texte


def test_das_js_maskiert_den_text_und_kennt_den_platzhalter():
    js = web_chat._js()
    assert "TEXT.sprache_text.replace('{dauer}', dauer)" in js
    assert ".replace('{text}', function () { return n.text; })" in js
    assert "n.abgetippt === false ? TEXT.sprache_laeuft : TEXT.sprache" in js
