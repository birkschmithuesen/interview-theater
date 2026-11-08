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
    """Ohne ``parse_mode``/``klartext`` rendert ``sende`` eine freie
    Antwort selbst als leichtes Markdown (Karte t_cc147548, 07.10.2026) --
    "hallo" traegt keine Markdown-Zeichen, bleibt also textlich gleich,
    bekommt aber ``parse_mode="HTML"`` mit."""
    def handler(request: httpx.Request) -> httpx.Response:
        gesendet = json.loads(request.content)
        assert gesendet == {"chat_id": -100, "text": "hallo", "parse_mode": "HTML"}
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    bot = telegram.Telegram("T", _klient(handler))
    assert bot.sende(-100, "hallo") == 42


def test_sende_ohne_markdown_wunsch_bleibt_reiner_text():
    """Wer explizit reinen Text ohne Auszeichnung will, uebergibt
    ``klartext=text`` selbst -- dann rendert ``sende`` nichts."""
    def handler(request: httpx.Request) -> httpx.Response:
        gesendet = json.loads(request.content)
        assert gesendet == {"chat_id": -100, "text": "**roh**"}
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    bot = telegram.Telegram("T", _klient(handler))
    bot.sende(-100, "**roh**", klartext="**roh**")


def test_sende_rendert_freie_markdown_antwort_zu_html():
    """Die freie Modellantwort (kein vorgebautes Menue) traegt jetzt
    leichtes Markdown -- ``sende`` rendert es selbst zu Telegram-HTML und
    liefert den Originaltext als Klartext-Rueckfall mit."""
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["erst"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    bot = telegram.Telegram("T", _klient(handler))
    bot.sende(-100, "Schaut euch **Szene 2** an -- *kurz* gehalten.")

    assert gesehen["erst"]["text"] == (
        "Schaut euch <b>Szene 2</b> an -- <i>kurz</i> gehalten."
    )
    assert gesehen["erst"]["parse_mode"] == "HTML"


def test_sende_rendert_markdown_faellt_bei_400_auf_klartext_zurueck():
    """Lehnt Telegram die selbst gerenderte HTML-Fassung ab, geht der
    unveraenderte Originaltext (mit Sternchen) als Klartext raus --
    dieselbe Zusage wie beim vorgebauten Menue-HTML."""
    aufrufe = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        aufrufe.append(body)
        if body.get("parse_mode"):
            return httpx.Response(400, json={"ok": False, "description": "Bad Request"})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})

    bot = telegram.Telegram("T", _klient(handler))
    message_id = bot.sende(-100, "**fett**")

    assert message_id == 9
    assert aufrufe[0]["text"] == "<b>fett</b>"
    assert "parse_mode" not in aufrufe[1]
    assert aufrufe[1]["text"] == "**fett**"


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


def test_sende_bild_schickt_ein_multipart_foto():
    """Die Telefon-Organisationskarten (UX-Knoepfe-Karte, Abschnitt 5):
    sendPhoto mit Dateiname, Bildinhalt und Bildunterschrift."""
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["url"] = str(request.url)
        gesehen["koerper"] = request.content
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})

    bot = telegram.Telegram("T", _klient(handler))
    assert bot.sende_bild(-100, "phase-4.png", b"\x89PNG...", "Satz der Karte") == 9

    assert "sendPhoto" in gesehen["url"]
    assert b"phase-4.png" in gesehen["koerper"]
    assert b"PNG" in gesehen["koerper"]
    assert b"Satz der Karte" in gesehen["koerper"]


def test_sende_bild_kuerzt_eine_zu_lange_bildunterschrift():
    gesehen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen["koerper"] = request.content
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})

    bot = telegram.Telegram("T", _klient(handler))
    bot.sende_bild(-100, "phase-4.png", b"x", "A" * 2000)

    assert b"A" * 1024 in gesehen["koerper"]
    assert b"A" * 1025 not in gesehen["koerper"]


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


# Ein Reply auf eine Bot-Nachricht ist seit dem 06.09.2026 kein eigener Fall
# mehr: das Feld ``antwortet_auf_bot`` war seit der Ausloeser-Aenderung
# (``ablauf.ist_ausloeser`` antwortet auf jede Nachricht) von keinem Codepfad
# mehr gelesen und ist entfernt -- HANDOFF (f) Punkt 6. Der Fall selbst bleibt
# geprueft: er darf nicht knallen.

def test_lies_nachricht_kommt_mit_reply_zurecht():
    update = {"update_id": 8, "message": {
        "message_id": 15, "date": 1788600000,
        "chat": {"id": -100, "title": "Gruppe 1"}, "from": {"first_name": "Gil"},
        "text": "ja gerne",
        "reply_to_message": {"from": {"is_bot": True}}}}
    n = telegram.lies_nachricht(update)
    assert n["text"] == "ja gerne"


# Der folgende Test steht nicht im Brief, waere spaeter aber teuer zu finden:
# eine Sprachnachricht mit Bildunterschrift muss trotzdem als "sprache" erkannt
# werden (Punkt 5 der Auftragshinweise -- vor "text" pruefen).

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


# --- Leichtes Markdown freier Antworten (Karte t_cc147548, 07.10.2026) ---
# Jeder Test nennt den Mutanten, den er faengt (Brief: "name the mutant"),
# wie tests/test_buehne_markdown.py fuer die Web-Fassung derselben Regel.


def test_leichtes_markdown_fett_wird_b():
    """Mutant: ``_LEICHT_FETT.sub`` entfernt -- ``**x**`` bliebe woertlich
    stehen statt ``<b>x</b>``."""
    assert telegram.leichtes_markdown("Das ist **wichtig**.") == "Das ist <b>wichtig</b>."


def test_leichtes_markdown_kursiv_wird_i():
    """Mutant: ``_LEICHT_KURSIV.sub`` entfernt -- ``*x*`` bliebe woertlich
    stehen statt ``<i>x</i>``."""
    assert telegram.leichtes_markdown("Das ist *betont*.") == "Das ist <i>betont</i>."


def test_leichtes_markdown_fett_vor_kursiv_frisst_kein_sternpaar():
    """Mutant: Reihenfolge Fett/Kursiv vertauscht -- die Kursiv-Regel griffe
    zuerst auf die aeusseren Sterne eines Fett-Paares."""
    ergebnis = telegram.leichtes_markdown("**fett** und *kursiv*")
    assert ergebnis == "<b>fett</b> und <i>kursiv</i>"


def test_leichtes_markdown_aufzaehlung_bleibt_klartext():
    """Telegram-HTML kennt kein <ul>/<li> -- eine Aufzaehlungszeile bleibt
    deshalb mit ihrem Bindestrich stehen, statt in Tags verwandelt zu
    werden. Mutant: eine <ul>/<li>-Umwandlung wuerde Telegram mit 400
    ablehnen."""
    ergebnis = telegram.leichtes_markdown("- eins\n- zwei")
    assert ergebnis == "- eins\n- zwei"


def test_leichtes_markdown_maskiert_zuerst():
    """Ein woertliches ``<script>`` im Modelltext darf kein HTML werden --
    Mutant: Maskieren und Ersetzen vertauscht, dann waere das Escapen
    wirkungslos (dieselbe Sicherheitspruefung wie bei ``_buehne_markdown``)."""
    ergebnis = telegram.leichtes_markdown("<script>alert(1)</script> **fett**")
    assert ergebnis == "&lt;script&gt;alert(1)&lt;/script&gt; <b>fett</b>"


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
