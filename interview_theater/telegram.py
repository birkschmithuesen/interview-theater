"""Duenner HTTP-Wrapper um die Telegram-Bot-API (Aufgabe 3).

Bewusst kein Framework: der Bot haelt die getUpdates-Position selbst in der
Datenbank (siehe repo.hole_update_id/setze_update_id), ein Framework mit
eigener Offset-Verwaltung muesste dazu erst ueberredet werden.

Der httpx.Client wird von aussen uebergeben (Dependency Injection), damit
Tests einen httpx.MockTransport einsetzen koennen und nie ins Netz gehen.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

BASIS = "https://api.telegram.org"

#: Telegram-Grenze fuer ``callback_data`` (Bot-API: 1-64 Bytes). Deshalb
#: traegt ein Knopf hier nie einen Volltext, sondern nur eine kurze Referenz
#: auf eine Zeile in der Tabelle ``knopf`` (siehe interview_theater/knoepfe.py).
CALLBACK_DATA_GRENZE = 64

#: Telegram Bot-API: sendMessage nimmt hoechstens 4096 Zeichen. Etwas Luft,
#: weil Telegram in UTF-16-Einheiten zaehlt und Emojis doppelt wiegen.
NACHRICHT_GRENZE = 4000


def teile_text(text: str, grenze: int = NACHRICHT_GRENZE) -> list[str]:
    """Teilt einen Text in Stuecke, die Telegram annimmt -- bevorzugt an
    Absatz-, dann an Zeilen-, dann an Wortgrenzen; ein leerer Text bleibt ein
    einzelnes leeres Stueck, damit der Aufrufer immer ein letztes Stueck fuer
    die Tastatur hat."""
    if len(text) <= grenze:
        return [text]
    stuecke: list[str] = []
    rest = text
    while len(rest) > grenze:
        schnitt = -1
        for trenner in ("\n\n", "\n", " "):
            schnitt = rest.rfind(trenner, 0, grenze)
            if schnitt > grenze // 2:
                break
        if schnitt <= grenze // 2:
            schnitt = grenze
        stuecke.append(rest[:schnitt].rstrip())
        rest = rest[schnitt:].lstrip()
    stuecke.append(rest)
    return [s for s in stuecke if s] or [""]


class TelegramFehler(Exception):
    """Fehler beim Zugriff auf die Telegram-Bot-API.

    Die Meldung ist bereits um den Bot-Token bereinigt: spaetere Aufgaben
    fangen Ausnahmen ab und schreiben str(fehler) als Vorfall in eine Tabelle,
    die ein im Raum projiziertes Dashboard anzeigt. httpx.HTTPStatusError
    enthaelt in __str__ die volle Request-URL, und der Token steht im
    URL-Pfad (/bot<TOKEN>/...) -- ohne Bereinigung stuende er an der Wand.
    """


def _bereinige(text: str, token) -> str:
    """Ersetzt jedes Vorkommen des Bot-Tokens in text durch '<token>'.

    ``token`` wird bewusst nicht typgepruefet, sondern zu str gemacht: ist
    hier versehentlich etwas anderes als ein String durchgereicht worden
    (gemessen 05.09.2026 -- ein Aufrufer gab das ganze Einstellungen-Objekt
    weiter), warf ``str.replace`` einen TypeError. Der riss die
    Bereinigung mit und haette den unbereinigten Text samt Token nach oben
    durchgereicht: genau das, was diese Funktion verhindern soll. Ein
    Schutz, der beim Fehler aussteigt, ist keiner."""
    return str(text).replace(str(token), "<token>")


def _iso(unix_zeit: int) -> str:
    """Wandelt einen Telegram-Unix-Zeitstempel in ISO 8601 (UTC) um."""
    return datetime.fromtimestamp(unix_zeit, tz=timezone.utc).isoformat(timespec="seconds")


class Telegram:
    """Kapselt die wenigen Telegram-Bot-API-Aufrufe, die der Bot braucht."""

    def __init__(self, token: str, klient: httpx.Client):
        self._token = token
        self._klient = klient

    def _url(self, methode: str) -> str:
        return f"{BASIS}/bot{self._token}/{methode}"

    @contextmanager
    def _fange_http_fehler(self):
        """Faengt HTTP- und Transportfehler (Statuscode, Verbindungsabbruch, ...)
        und wirft sie als TelegramFehler mit token-bereinigter Meldung neu."""
        try:
            yield
        except httpx.HTTPError as fehler:
            raise TelegramFehler(_bereinige(str(fehler), self._token)) from fehler

    def hole_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        """Long-Poll auf neue Updates. Liefert das rohe `result`-Array."""
        with self._fange_http_fehler():
            antwort = self._klient.get(
                self._url("getUpdates"), params={"offset": offset, "timeout": timeout}
            )
            antwort.raise_for_status()
            return antwort.json()["result"]

    def sende(self, chat_id: int, text: str) -> int:
        """Schickt eine Textnachricht. Liefert die message_id der gesendeten Nachricht.

        Telegram nimmt hoechstens 4096 Zeichen je Nachricht (Bot-API,
        sendMessage). Laengere Texte werden in Stuecke geteilt (05.09.2026,
        Live-Fall Gruppe 2: ein Teil-Transkript mit 7 957 Zeichen -> HTTP 400
        auf beiden Sendewegen, das Echo kam nie an). Zurueck kommt die
        message_id des LETZTEN Stuecks -- an dem haengen Tastatur und
        Verweise."""
        letzte = 0
        for stueck in teile_text(text):
            with self._fange_http_fehler():
                antwort = self._klient.post(
                    self._url("sendMessage"), json={"chat_id": chat_id, "text": stueck}
                )
                antwort.raise_for_status()
                letzte = antwort.json()["result"]["message_id"]
        return letzte

    def sende_mit_knoepfen(
        self, chat_id: int, text: str, knoepfe: list[tuple[str, str]]
    ) -> int:
        """Wie ``sende``, nur mit einer Inline-Tastatur darunter: je Eintrag
        ``(beschriftung, callback_data)`` eine Zeile, untereinander.

        Untereinander und nicht nebeneinander, weil die Beschriftungen hier
        ganze Saetze sein koennen (Kernthema-Vorschlaege) -- nebeneinander
        wuerde Telegram sie auf dem Telefon abschneiden.

        Prueft die 64-Byte-Grenze von ``callback_data`` an genau dieser
        Stelle: schickt der Bot sie zu lang, antwortet Telegram mit
        BUTTON_DATA_INVALID, und der Fehler faende sich erst im Betrieb.
        Ein zu langer Wert ist ein Programmierfehler (der Aufrufer haette eine
        Knopf-id nehmen muessen), deshalb ValueError statt stiller Kuerzung."""
        for _, daten in knoepfe:
            if len(daten.encode("utf-8")) > CALLBACK_DATA_GRENZE:
                raise ValueError(f"callback_data zu lang: {len(daten)} Zeichen")
        tastatur = [[{"text": t, "callback_data": d}] for t, d in knoepfe]
        stuecke = teile_text(text)
        # Alle Stuecke bis auf das letzte ohne Tastatur -- die Knoepfe gehoeren
        # unter das Ende des Textes, nicht in seine Mitte.
        for stueck in stuecke[:-1]:
            self.sende(chat_id, stueck)
        with self._fange_http_fehler():
            antwort = self._klient.post(
                self._url("sendMessage"),
                json={
                    "chat_id": chat_id,
                    "text": stuecke[-1],
                    "reply_markup": {"inline_keyboard": tastatur},
                },
            )
            antwort.raise_for_status()
            return antwort.json()["result"]["message_id"]

    def sende_datei(
        self, chat_id: int, dateiname: str, inhalt: bytes | str,
        beschreibung: str = "",
    ) -> int:
        """Schickt eine Datei (sendDocument) -- gebraucht fuer den
        Textbuch-Export in Phase 7 (``szenenfolge.textbuch``).

        Warum eine Datei und nicht Nachrichten: ein Textbuch aus sechs Szenen
        sind leicht 30.000 Zeichen. Als Nachricht waeren das acht Stuecke
        (``teile_text``), die im Chat nicht mehr auffindbar sind und beim
        naechsten Scrollen verschwinden. Eine Datei laesst sich weiterreichen,
        ausdrucken und auf die Probe mitnehmen.

        ``inhalt`` als Text oder Bytes -- der Aufrufer soll sich nicht um die
        Kodierung kuemmern muessen (UTF-8, wie alles hier). Liefert die
        message_id der Dateinachricht."""
        daten = inhalt.encode("utf-8") if isinstance(inhalt, str) else inhalt
        felder = {"chat_id": str(chat_id)}
        if beschreibung:
            # Telegram begrenzt die Bildunterschrift auf 1024 Zeichen; laenger
            # antwortet die API mit HTTP 400, und die Datei kaeme nie an.
            felder["caption"] = beschreibung[:1024]
        with self._fange_http_fehler():
            antwort = self._klient.post(
                self._url("sendDocument"),
                data=felder,
                files={"document": (dateiname, daten, "text/markdown")},
            )
            antwort.raise_for_status()
            return antwort.json()["result"]["message_id"]

    def beantworte_knopf(self, callback_query_id: str, text: str = "") -> None:
        """answerCallbackQuery -- Telegram erwartet das auf JEDEN Knopfdruck.

        Ohne diese Antwort dreht sich in der App eine Ladeanzeige weiter,
        bis sie nach Sekunden von selbst aufgibt: fuer die Gruppe sieht
        genau das nach einem haengenden Bot aus. Deshalb wird sie auch dann
        geschickt, wenn der Druck gar nichts bewirkt hat (Knopf schon
        benutzt) -- die Rueckmeldung ist wichtiger als die Wirkung."""
        with self._fange_http_fehler():
            antwort = self._klient.post(
                self._url("answerCallbackQuery"),
                json={"callback_query_id": callback_query_id, "text": text},
            )
            antwort.raise_for_status()

    def entferne_knoepfe(self, chat_id: int, message_id: int) -> None:
        """Nimmt die Tastatur unter einer schon verschickten Nachricht weg
        (editMessageReplyMarkup mit leerer Tastatur).

        Damit verschwindet der Knopf, sobald er gewirkt hat: ein benutzter
        Knopf, der weiter klickbar dasteht, laedt zum zweiten Druck ein --
        idempotent ist das zwar (siehe repo.beanspruche_knopf), aber
        verwirrend. Ein Fehlschlag ist unkritisch und wird vom Aufrufer
        geschluckt: die Wirkung ist da, nur die Optik nicht aufgeraeumt."""
        with self._fange_http_fehler():
            antwort = self._klient.post(
                self._url("editMessageReplyMarkup"),
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": {"inline_keyboard": []},
                },
            )
            antwort.raise_for_status()

    def aktualisiere_knoepfe(
        self, chat_id: int, message_id: int, knoepfe: list[tuple[str, str]]
    ) -> None:
        """Tauscht die Tastatur unter einer schon verschickten Nachricht aus
        (editMessageReplyMarkup mit neuer Tastatur).

        Gebraucht fuer die **Mehrfachauswahl** der Phase 2 (06.09.2026): ein
        Druck togglet eine Frage, und die Gruppe soll das sehen, ohne dass
        zehn Fragen ein zweites Mal in den Chat wandern -- nur der Haken vor
        der Beschriftung aendert sich.

        Wie ``entferne_knoepfe`` ein Fehlschlag, der den Aufrufer nicht
        umbringt: der Zustand steht in der Datenbank
        (``arbeitsstand.fragen_gewaehlt``), die Tastatur zeigt ihn nur.
        Telegram antwortet mit HTTP 400, wenn die Tastatur unveraendert
        waere -- das kann hier nicht passieren, weil jeder Druck den Haken
        umdreht.
        """
        for _, daten in knoepfe:
            if len(daten.encode("utf-8")) > CALLBACK_DATA_GRENZE:
                raise ValueError(f"callback_data zu lang: {len(daten)} Zeichen")
        tastatur = [[{"text": t, "callback_data": d}] for t, d in knoepfe]
        with self._fange_http_fehler():
            antwort = self._klient.post(
                self._url("editMessageReplyMarkup"),
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": {"inline_keyboard": tastatur},
                },
            )
            antwort.raise_for_status()

    def loesche_nachrichten(self, chat_id: int, message_ids: list[int]) -> int:
        """Loescht bis zu 100 Nachrichten auf einmal (deleteMessages). Braucht
        Admin-Rechte in der Gruppe. Liefert die Zahl der uebergebenen IDs;
        Telegram meldet fuer laengst geloeschte oder unbekannte IDs keinen
        Fehler, sondern ignoriert sie -- deshalb kein Zaehlen des Erfolgs
        je ID. Nachrichten von VOR dem Eintritt des Bots kennt er nicht und
        kann sie nicht loeschen (scripts/chat_leeren.py)."""
        if not message_ids:
            return 0
        with self._fange_http_fehler():
            antwort = self._klient.post(
                self._url("deleteMessages"),
                json={"chat_id": chat_id, "message_ids": message_ids[:100]},
            )
            antwort.raise_for_status()
        return len(message_ids[:100])

    def setze_befehle(self, befehle: list[dict]) -> None:
        """Ruft setMyCommands (teil-b.md Aufgabe 6): die Befehle erscheinen im
        Telegram-Menue, wenn jemand '/' tippt. Wird einmal beim Start
        aufgerufen (``bot.main``); ob ein Fehlschlag den Bot-Start aufhalten
        darf, entscheidet der Aufrufer, nicht diese Methode -- hier wird nur
        der HTTP-Aufruf gekapselt."""
        with self._fange_http_fehler():
            antwort = self._klient.post(
                self._url("setMyCommands"), json={"commands": befehle}
            )
            antwort.raise_for_status()

    def tippt(self, chat_id: int) -> None:
        """Zeigt die Tippanzeige ("...schreibt") in der Gruppe."""
        with self._fange_http_fehler():
            antwort = self._klient.post(
                self._url("sendChatAction"), json={"chat_id": chat_id, "action": "typing"}
            )
            antwort.raise_for_status()

    def lade_datei(self, file_id: str, ziel: Path) -> None:
        """Laedt eine Datei herunter. Zwei Aufrufe: erst getFile fuer den
        file_path, dann ein GET auf die eigentliche Datei, als Strom geschrieben."""
        with self._fange_http_fehler():
            antwort = self._klient.get(self._url("getFile"), params={"file_id": file_id})
            antwort.raise_for_status()
            file_path = antwort.json()["result"]["file_path"]

            ziel.parent.mkdir(parents=True, exist_ok=True)
            datei_url = f"{BASIS}/file/bot{self._token}/{file_path}"
            with self._klient.stream("GET", datei_url) as antwort:
                antwort.raise_for_status()
                with open(ziel, "wb") as f:
                    for teil in antwort.iter_bytes():
                        f.write(teil)


def _bestimme_typ(nachricht: dict) -> str:
    """Prueft in genau dieser Reihenfolge (vor 'text', sonst wird eine
    Sprachnachricht mit Bildunterschrift falsch als 'text' einsortiert)."""
    if "voice" in nachricht:
        return "sprache"
    if "audio" in nachricht:
        return "sprache"
    if "document" in nachricht:
        return "dokument"
    if "text" in nachricht:
        return "text"
    if "photo" in nachricht:
        return "foto"
    if "sticker" in nachricht:
        return "sticker"
    return "sonstiges"


def _sprachquelle(nachricht: dict) -> dict:
    """voice und audio werden beide als 'sprache' behandelt (Auftragshinweis 5);
    folgerichtig gilt das auch fuer die Dauer, nicht nur fuer die file_id."""
    return nachricht.get("voice") or nachricht.get("audio") or {}


def _bestimme_file_id(nachricht: dict, typ: str) -> str | None:
    if typ == "sprache":
        return _sprachquelle(nachricht).get("file_id")
    if typ == "dokument":
        return nachricht.get("document", {}).get("file_id")
    if typ == "foto":
        fotos = nachricht.get("photo") or []
        return fotos[-1]["file_id"] if fotos else None
    if typ == "sticker":
        return nachricht.get("sticker", {}).get("file_id")
    return None


def lies_nachricht(update: dict) -> dict[str, Any] | None:
    """Normalisiert ein Telegram-Update auf die feste Schluesselmenge, mit der
    der Rest des Bots arbeitet. Liefert None, wenn das Update keine (auch keine
    editierte) Nachricht enthaelt."""
    nachricht = update.get("message") or update.get("edited_message")
    if nachricht is None:
        return None

    typ = _bestimme_typ(nachricht)

    reply = nachricht.get("reply_to_message") or {}
    antwortet_auf_bot = bool((reply.get("from") or {}).get("is_bot", False))

    return {
        "chat_id": nachricht["chat"]["id"],
        "chat_titel": nachricht["chat"].get("title"),
        "message_id": nachricht["message_id"],
        "absender": (nachricht.get("from") or {}).get("first_name"),
        "typ": typ,
        "text": nachricht.get("text", nachricht.get("caption")),
        "file_id": _bestimme_file_id(nachricht, typ),
        "dauer": _sprachquelle(nachricht).get("duration"),
        "gesendet_am": _iso(nachricht["date"]),
        "antwortet_auf_bot": antwortet_auf_bot,
    }


def lies_knopfdruck(update: dict) -> dict[str, Any] | None:
    """Normalisiert ein ``callback_query``-Update auf die Schluessel, mit
    denen ``knoepfe.behandle`` arbeitet -- das Gegenstueck zu
    ``lies_nachricht`` fuer den zweiten Update-Typ, den dieser Bot kennt.

    Liefert None, wenn das Update kein Knopfdruck ist. Ohne ``data`` (moeglich
    laut Bot-API bei Spiel-Knoepfen) ebenfalls None: darauf laesst sich nichts
    zuordnen, und raten waere hier der teuerste Ausgang.

    ``message`` fehlt bei sehr alten Nachrichten (Telegram haelt sie nicht
    ewig vor); ``chat_id`` und ``message_id`` sind deshalb optional. Der
    Aufrufer kann dann nicht mehr antworten, aber ``callback_query_id`` reicht
    weiterhin fuer answerCallbackQuery.

    Der Absender kommt NICHT mit: wer gedrueckt hat, ist fuer die Wirkung
    ohne Belang (die Gruppe entscheidet gemeinsam), und ein Name in einem
    Datensatz, der nirgends gebraucht wird, ist nur eine weitere Stelle, an
    der er auftauchen kann."""
    knopf = update.get("callback_query")
    if not knopf or not knopf.get("data"):
        return None
    nachricht = knopf.get("message") or {}
    chat = nachricht.get("chat") or {}
    return {
        "callback_query_id": knopf["id"],
        "data": knopf["data"],
        "chat_id": chat.get("id"),
        "chat_titel": chat.get("title"),
        "message_id": nachricht.get("message_id"),
    }
