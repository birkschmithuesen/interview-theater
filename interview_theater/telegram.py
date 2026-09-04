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


class TelegramFehler(Exception):
    """Fehler beim Zugriff auf die Telegram-Bot-API.

    Die Meldung ist bereits um den Bot-Token bereinigt: spaetere Aufgaben
    fangen Ausnahmen ab und schreiben str(fehler) als Vorfall in eine Tabelle,
    die ein im Raum projiziertes Dashboard anzeigt. httpx.HTTPStatusError
    enthaelt in __str__ die volle Request-URL, und der Token steht im
    URL-Pfad (/bot<TOKEN>/...) -- ohne Bereinigung stuende er an der Wand.
    """


def _bereinige(text: str, token: str) -> str:
    """Ersetzt jedes Vorkommen des Bot-Tokens in text durch '<token>'."""
    return text.replace(token, "<token>")


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
        """Schickt eine Textnachricht. Liefert die message_id der gesendeten Nachricht."""
        with self._fange_http_fehler():
            antwort = self._klient.post(
                self._url("sendMessage"), json={"chat_id": chat_id, "text": text}
            )
            antwort.raise_for_status()
            return antwort.json()["result"]["message_id"]

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
