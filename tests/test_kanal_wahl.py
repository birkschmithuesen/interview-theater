"""Ohne IT_KANAL bleibt alles, wie es war (E1: Telegram ist Plan B).

Die Weiche steht in bot.main und NICHT in bot.schleife: die Schleife kennt
nur ein Objekt mit hole_updates, und genau das ist die Naht.
"""

import pytest

from interview_theater import bot, einstellungen, db, repo, telegram, web_kanal

PFLICHT = {
    "IT_BOT_NAME": "gruppe1",
    "IT_DB": "/tmp/egal.db",
    "IT_LLM_URL": "https://example.invalid/chat/completions",
    "IT_LLM_KEY": "k",
    "IT_LLM_MODELL": "m",
    "IT_STT_PRODUKT": "p",
}


def _umgebung(monkeypatch, **zusatz):
    for name in list(einstellungen._VORGABEWERTE) + [
        "IT_KANAL", "IT_WEB_CHAT_ID", "IT_WEB_SEGMENT_MS",
    ]:
        monkeypatch.delenv(name, raising=False)
    for name, wert in {**PFLICHT, **zusatz}.items():
        monkeypatch.setenv(name, wert)


def test_ohne_variable_ist_der_kanal_telegram(monkeypatch):
    _umgebung(monkeypatch, IT_BOT_TOKEN="123:abc")
    e = einstellungen.laden()
    assert e.kanal == einstellungen.KANAL_TELEGRAM
    assert e.bot_token == "123:abc"
    assert e.web_chat_id is None


def test_ohne_variable_bleibt_der_bot_token_pflicht(monkeypatch):
    _umgebung(monkeypatch)   # kein IT_BOT_TOKEN
    with pytest.raises(RuntimeError) as fehler:
        einstellungen.laden()
    assert "IT_BOT_TOKEN" in str(fehler.value)


def test_im_web_kanal_ist_der_bot_token_keine_pflicht(monkeypatch):
    _umgebung(monkeypatch, IT_KANAL="web", IT_WEB_CHAT_ID="7000000000001")
    e = einstellungen.laden()
    assert e.kanal == einstellungen.KANAL_WEB
    assert e.web_chat_id == 7_000_000_000_001
    assert e.bot_token == ""


def test_kanal_wird_normalisiert(monkeypatch):
    _umgebung(monkeypatch, IT_KANAL="  WEB  ", IT_WEB_CHAT_ID="7000000000001")
    assert einstellungen.laden().kanal == einstellungen.KANAL_WEB


def test_unbekannter_kanal_bricht_ab(monkeypatch):
    """Ein Tippfehler in einer Env-Datei soll nicht still auf Telegram
    zurueckfallen: dann sucht jemand am Workshopmorgen, warum der Browser
    nichts sieht."""
    _umgebung(monkeypatch, IT_BOT_TOKEN="1:a", IT_KANAL="webb")
    with pytest.raises(RuntimeError) as fehler:
        einstellungen.laden()
    assert "IT_KANAL" in str(fehler.value)


def test_web_kanal_ohne_chat_id_bricht_ab(monkeypatch):
    _umgebung(monkeypatch, IT_KANAL="web")
    with pytest.raises(RuntimeError) as fehler:
        einstellungen.laden()
    assert "IT_WEB_CHAT_ID" in str(fehler.value)


def test_segmentlaenge_hat_einen_vorgabewert(monkeypatch):
    _umgebung(monkeypatch, IT_BOT_TOKEN="1:a")
    assert einstellungen.laden().web_segment_ms == 45_000
    _umgebung(monkeypatch, IT_BOT_TOKEN="1:a", IT_WEB_SEGMENT_MS="800")
    assert einstellungen.laden().web_segment_ms == 800


def test_baue_kanal_liefert_telegram_ohne_variable(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    e = einstellungen.Einstellungen(
        bot_token="1:a", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"), llm_url="u", llm_key="k",
        llm_modell="m", stt_basis="b", stt_produkt="p",
    )
    assert isinstance(bot.baue_kanal(conn, e, klient=None), telegram.Telegram)


def test_baue_kanal_liefert_webkanal_im_web_modus(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 7_000_000_000_001, "gruppe1", "Web-Gruppe")
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"), llm_url="u", llm_key="k",
        llm_modell="m", stt_basis="b", stt_produkt="p",
        kanal=einstellungen.KANAL_WEB, web_chat_id=7_000_000_000_001,
    )
    kanal = bot.baue_kanal(conn, e, klient=None)
    assert isinstance(kanal, web_kanal.WebKanal)


def test_baue_kanal_verweigert_eine_unbekannte_gruppe(tmp_path):
    """Der Web-Bot-Prozess bedient genau seine IT_WEB_CHAT_ID. Gibt es die
    Gruppe nicht, hat niemand ``scripts/web_gruppe.py`` laufen lassen -- und
    ein Bot, der auf eine leere Gruppe hoert, sieht aus wie einer, der
    haengt."""
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    e = einstellungen.Einstellungen(
        bot_token="", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"), llm_url="u", llm_key="k",
        llm_modell="m", stt_basis="b", stt_produkt="p",
        kanal=einstellungen.KANAL_WEB, web_chat_id=7_000_000_000_999,
    )
    with pytest.raises(RuntimeError) as fehler:
        bot.baue_kanal(conn, e, klient=None)
    assert "web_gruppe" in str(fehler.value)


def test_schleife_ist_nicht_angefasst_worden():
    """Die Naht traegt genau dann, wenn bot.schleife nichts vom Kanal weiss.

    Gemessen: im Quelltext von ``schleife`` steht kein 'telegram' und kein
    'web' -- sie ruft nur ``tg.hole_updates`` und ``telegram.lies_*``."""
    import inspect

    quelle = inspect.getsource(bot.schleife)
    assert "web_kanal" not in quelle
    assert "IT_KANAL" not in quelle
    assert "kanal" not in quelle
