import json

import httpx
import pytest

from interview_theater import telegram


def _klient(handler):
    """Baut einen httpx.Client mit MockTransport -- kein Netzzugriff (global-constraints.md)."""
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_hole_updates_liefert_result():
    gesehene_anfrage = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehene_anfrage["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True, "result": [{"update_id": 1}]})

    bot = telegram.Telegram("T", _klient(handler))
    ergebnis = bot.hole_updates(offset=5, timeout=25)

    assert ergebnis == [{"update_id": 1}]
    assert "getUpdates" in gesehene_anfrage["url"]
    assert "offset=5" in gesehene_anfrage["url"]
    assert "timeout=25" in gesehene_anfrage["url"]


def test_sende_liefert_message_id():
    def handler(request: httpx.Request) -> httpx.Response:
        gesendet = json.loads(request.content)
        assert gesendet == {"chat_id": -100, "text": "hallo"}
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    bot = telegram.Telegram("T", _klient(handler))
    assert bot.sende(-100, "hallo") == 42


def test_sende_datei_schickt_ein_multipart_dokument():
    """Der Textbuch-Export in Phase 7 (``szenenfolge.textbuch``): sendDocument
    mit Dateiname, Inhalt und Bildunterschrift -- multipart, nicht JSON."""
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["url"] = str(request.url)
        gesehen["koerper"] = request.content.decode("utf-8", "replace")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    bot = telegram.Telegram("T", _klient(handler))
    assert bot.sende_datei(-100, "textbuch.md", "# Textbuch", "Euer Textbuch") == 7

    assert "sendDocument" in gesehen["url"]
    assert "textbuch.md" in gesehen["koerper"]
    assert "# Textbuch" in gesehen["koerper"]
    assert "Euer Textbuch" in gesehen["koerper"]


def test_sende_datei_kuerzt_eine_zu_lange_bildunterschrift():
    """Telegram nimmt hoechstens 1024 Zeichen als caption; laenger antwortet
    die API mit HTTP 400 und die Datei kaeme nie an."""
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["koerper"] = request.content.decode("utf-8", "replace")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    bot = telegram.Telegram("T", _klient(handler))
    bot.sende_datei(-100, "textbuch.md", "x", "A" * 2000)

    assert "A" * 1024 in gesehen["koerper"]
    assert "A" * 1025 not in gesehen["koerper"]


def test_tippt_schickt_typing_aktion():
    gesehene_anfrage = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehene_anfrage["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": True})

    bot = telegram.Telegram("T", _klient(handler))
    bot.tippt(-100)

    assert gesehene_anfrage["body"] == {"chat_id": -100, "action": "typing"}


def test_lade_datei_macht_zwei_aufrufe_und_schreibt_ziel(tmp_path):
    aufrufe = []

    def handler(request: httpx.Request) -> httpx.Response:
        aufrufe.append(str(request.url))
        if "getFile" in str(request.url):
            return httpx.Response(
                200, json={"ok": True, "result": {"file_path": "voice/xyz.oga"}}
            )
        return httpx.Response(200, content=b"binaerdaten")

    bot = telegram.Telegram("T", _klient(handler))
    ziel = tmp_path / "audio" / "1" / "datei.oga"
    bot.lade_datei("AwACabc", ziel)

    assert len(aufrufe) == 2
    assert "getFile" in aufrufe[0]
    assert "file/botT/voice/xyz.oga" in aufrufe[1]
    assert ziel.read_bytes() == b"binaerdaten"


def test_http_fehler_wird_ohne_token_geworfen():
    """Der Token steht im URL-Pfad; httpx.HTTPStatusError.__str__ enthaelt die
    volle Request-URL. Ohne Bereinigung stuende der Token auf dem im Raum
    projizierten Vorfall-Dashboard (str(fehler) wird dort direkt angezeigt)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"ok": False, "description": "kaputt"})

    token = "GEHEIMER_TOKEN_123"
    bot = telegram.Telegram(token, _klient(handler))

    with pytest.raises(telegram.TelegramFehler) as ausnahme_info:
        bot.hole_updates(offset=1)

    meldung = str(ausnahme_info.value)
    assert token not in meldung
    assert "<token>" in meldung


def test_setze_befehle_schickt_die_richtige_nutzlast():
    gesehene_anfrage = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehene_anfrage["body"] = json.loads(request.content)
        gesehene_anfrage["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True, "result": True})

    bot = telegram.Telegram("T", _klient(handler))
    befehle = [{"command": "stand", "description": "Arbeitsstand anzeigen"}]
    bot.setze_befehle(befehle)

    assert "setMyCommands" in gesehene_anfrage["url"]
    assert gesehene_anfrage["body"] == {"commands": befehle}


def test_setze_befehle_wirft_bei_http_fehler():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"ok": False, "description": "kaputt"})

    bot = telegram.Telegram("T", _klient(handler))
    with pytest.raises(telegram.TelegramFehler):
        bot.setze_befehle([{"command": "stand", "description": "x"}])


def test_lies_nachricht_erkennt_sprachnachricht_mit_dauer():
    update = {"update_id": 1, "message": {
        "message_id": 9, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Ada"},
        "voice": {"file_id": "AwACabc", "duration": 312}}}
    n = telegram.lies_nachricht(update)
    assert n["typ"] == "sprache" and n["file_id"] == "AwACabc" and n["dauer"] == 312
    assert n["chat_id"] == -100 and n["absender"] == "Ada"


def test_lies_nachricht_erkennt_text():
    update = {"update_id": 2, "message": {
        "message_id": 10, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Bo"},
        "text": "hallo zusammen"}}
    n = telegram.lies_nachricht(update)
    assert n["typ"] == "text"
    assert n["text"] == "hallo zusammen"
    assert n["dauer"] is None
    assert n["file_id"] is None


def test_lies_nachricht_erkennt_dokument():
    update = {"update_id": 3, "message": {
        "message_id": 11, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Cem"},
        "document": {"file_id": "DocAbc", "file_name": "szene.txt"}}}
    n = telegram.lies_nachricht(update)
    assert n["typ"] == "dokument"
    assert n["file_id"] == "DocAbc"
    assert n["dauer"] is None


def test_lies_nachricht_erkennt_sticker():
    update = {"update_id": 4, "message": {
        "message_id": 12, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Dea"},
        "sticker": {"file_id": "StickAbc"}}}
    n = telegram.lies_nachricht(update)
    assert n["typ"] == "sticker"
    assert n["file_id"] == "StickAbc"


def test_lies_nachricht_erkennt_audio_als_sprache_mit_dauer():
    """audio wird wie voice als 'sprache' behandelt (Punkt 5); folgerichtig muss
    auch die Dauer aus audio.duration kommen, nicht nur aus voice.duration."""
    update = {"update_id": 30, "message": {
        "message_id": 20, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Kim"},
        "audio": {"file_id": "AudAbc", "duration": 90}}}
    n = telegram.lies_nachricht(update)
    assert n["typ"] == "sprache"
    assert n["file_id"] == "AudAbc"
    assert n["dauer"] == 90


def test_lies_nachricht_erkennt_foto_und_waehlt_hoechste_aufloesung():
    update = {"update_id": 31, "message": {
        "message_id": 21, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Lia"},
        "photo": [
            {"file_id": "FotoKlein", "width": 90, "height": 90},
            {"file_id": "FotoGross", "width": 1280, "height": 1280},
        ]}}
    n = telegram.lies_nachricht(update)
    assert n["typ"] == "foto"
    assert n["file_id"] == "FotoGross"
    assert n["dauer"] is None


def test_lies_nachricht_erkennt_unbekannten_typ_als_sonstiges():
    update = {"update_id": 5, "message": {
        "message_id": 13, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Emo"},
        "location": {"latitude": 1.0, "longitude": 2.0}}}
    n = telegram.lies_nachricht(update)
    assert n["typ"] == "sonstiges"
    assert n["file_id"] is None
    assert n["dauer"] is None


def test_lies_nachricht_liefert_none_ohne_nachricht():
    update = {"update_id": 6, "my_chat_member": {}}
    assert telegram.lies_nachricht(update) is None


def test_lies_nachricht_verarbeitet_edited_message_wie_eine_normale_nachricht():
    update = {"update_id": 7, "edited_message": {
        "message_id": 14, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Fee"},
        "text": "korrigiert"}}
    n = telegram.lies_nachricht(update)
    assert n is not None
    assert n["typ"] == "text"
    assert n["text"] == "korrigiert"


def test_lies_nachricht_setzt_antwortet_auf_bot():
    update = {"update_id": 8, "message": {
        "message_id": 15, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Gil"},
        "text": "ja gerne",
        "reply_to_message": {"from": {"is_bot": True}}}}
    n = telegram.lies_nachricht(update)
    assert n["antwortet_auf_bot"] is True


# Die folgenden zwei Tests stehen nicht im Brief, waeren spaeter aber teuer zu
# finden: fehlendes reply_to_message darf nicht knallen, und eine Sprachnachricht
# mit Bildunterschrift muss trotzdem als "sprache" erkannt werden (Punkt 5 der
# Auftragshinweise -- vor "text" pruefen).

def test_lies_nachricht_antwortet_auf_bot_ist_false_ohne_reply():
    update = {"update_id": 9, "message": {
        "message_id": 16, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Ina"},
        "text": "einfach so"}}
    n = telegram.lies_nachricht(update)
    assert n["antwortet_auf_bot"] is False


def test_lies_nachricht_erkennt_sprache_trotz_bildunterschrift():
    update = {"update_id": 10, "message": {
        "message_id": 17, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Jo"},
        "voice": {"file_id": "AwACdef", "duration": 5},
        "caption": "Regieanweisung"}}
    n = telegram.lies_nachricht(update)
    assert n["typ"] == "sprache"
    assert n["text"] == "Regieanweisung"
    assert n["dauer"] == 5


def test_loesche_nachrichten_schickt_hoechstens_hundert_ids():
    """deleteMessages nimmt maximal 100 IDs je Aufruf; der Aufrufer
    (scripts/chat_leeren.py) stueckelt, der Wrapper kappt zur Sicherheit."""
    gesehen = []

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen.append(json.loads(request.content))
        assert "deleteMessages" in str(request.url)
        return httpx.Response(200, json={"ok": True, "result": True})

    bot = telegram.Telegram("T", _klient(handler))
    assert bot.loesche_nachrichten(-100, list(range(1, 151))) == 100
    assert gesehen[0]["chat_id"] == -100
    assert len(gesehen[0]["message_ids"]) == 100


def test_loesche_nachrichten_ohne_ids_ruft_nichts():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("kein Aufruf erwartet")

    bot = telegram.Telegram("T", _klient(handler))
    assert bot.loesche_nachrichten(-100, []) == 0


def test_loesche_nachrichten_bereinigt_token_im_fehler():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": "not enough rights"})

    bot = telegram.Telegram("GEHEIM", _klient(handler))
    with pytest.raises(telegram.TelegramFehler) as info:
        bot.loesche_nachrichten(-100, [1])
    assert "GEHEIM" not in str(info.value)


def test_bereinige_steigt_nicht_aus_wenn_der_token_kein_string_ist():
    """05.09.2026: ein Aufrufer reichte versehentlich das ganze
    Einstellungen-Objekt statt des Tokens durch. ``str.replace`` warf einen
    TypeError -- der riss die Bereinigung mit, und der unbereinigte Text
    (inklusive Token in der URL) waere nach oben durchgereicht worden.

    Ein Schutz, der beim Fehler aussteigt, ist keiner: deshalb wird hier
    stumpf zu str gemacht statt auf den Typ zu vertrauen."""
    from interview_theater import telegram

    class Fremd:
        def __str__(self):
            return "GEHEIM123"

    text = "Fehler bei https://api.telegram.org/botGEHEIM123/sendMessage"
    assert telegram._bereinige(text, Fremd()) == (
        "Fehler bei https://api.telegram.org/bot<token>/sendMessage"
    )
    assert "GEHEIM123" not in telegram._bereinige(text, Fremd())


# --- HTML fuer Vorschlagsmenues (06.09.2026, Birk 11:05) ------------------


def test_menuetext_setzt_fette_titel_und_nummern():
    from interview_theater import vorschlag

    html, klar = vorschlag.menuetext(
        "Woran wollt ihr entlang?",
        "Der lange Weg — sie geht ohne Abschied\nZurueck — sie bleibt",
    )

    assert "1. <b>Der lange Weg</b> — sie geht ohne Abschied" in html
    assert "2. <b>Zurueck</b> — sie bleibt" in html
    assert "<b>" not in klar
    assert "1. Der lange Weg — sie geht ohne Abschied" in klar


def test_menuetext_maskiert_spitze_klammern():
    from interview_theater import vorschlag

    html, klar = vorschlag.menuetext("", "Ein <Ort> & eine Zeit — jetzt")

    assert "&lt;Ort&gt; &amp; eine Zeit" in html
    assert "<Ort>" in klar


def test_sende_mit_html_faellt_bei_400_auf_klartext_zurueck():
    """Eine Nachricht, die wegen Fettschrift gar nicht ankommt, waere der
    teuerste Ausgang -- deshalb der Rueckfall (06.09.2026)."""
    gesehen = []

    def handler(request: httpx.Request) -> httpx.Response:
        nutzlast = json.loads(request.content)
        gesehen.append(nutzlast)
        if nutzlast.get("parse_mode"):
            return httpx.Response(400, json={"description": "can't parse entities"})
        return httpx.Response(200, json={"result": {"message_id": 7}})

    klient = httpx.Client(transport=httpx.MockTransport(handler))
    tg = telegram.Telegram("TOKEN", klient)

    message_id = tg.sende(1, "1. <b>A</b>", parse_mode="HTML", klartext="1. A")

    assert message_id == 7
    assert len(gesehen) == 2
    assert gesehen[1].get("parse_mode") is None
    assert gesehen[1]["text"] == "1. A"
