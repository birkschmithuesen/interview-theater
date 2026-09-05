"""Telegram-Attrappe fuer den Simulator -- kein Netzzugriff, zeichnet auf.

Uebernommen aus ``tests/test_ablauf.py`` und um die Methoden erweitert, die
im vollen Codepfad vorkommen: ``setze_befehle`` (bot.main),
``loesche_nachrichten`` (scripts/chat_leeren.py) und ``lade_datei``
(aufnahme.empfange). Die drei sind No-Ops -- der Simulator schickt keine
Sprachnachrichten, Interviews kommen als Text (§ 10.5).

Der Unterschied zur Test-Attrappe: hier wird **mit Zeitstempel** und mit
laufender Nummer aufgezeichnet, weil die Kennzahlen (``kennzahlen.py``)
spaeter wissen muessen, welche Bot-Nachricht zu welchem Zug gehoert. Das
Schneiden macht der Aufrufer ueber ``len(tg.gesendet)`` vor und nach einer
Aktion -- die Attrappe selbst kennt weder Schritte noch Stimmen.
"""

from __future__ import annotations

import time
from pathlib import Path


class TelegramAttrappe:
    """Ersetzt ``interview_theater.telegram.Telegram``."""

    #: Erste vergebene message_id.
    ERSTE_MESSAGE_ID = 1_000

    def __init__(self) -> None:
        #: Liste von Dicts: chat_id, text, message_id, zeit (monotone Sekunden
        #: seit dem Anlegen der Attrappe).
        self.gesendet: list[dict] = []
        self.getippt: list[int] = []
        self.befehle: list = []
        self.geloescht: list = []
        self._message_id = self.ERSTE_MESSAGE_ID
        self._start = time.monotonic()

    def jetzt(self) -> float:
        """Sekunden seit dem Anlegen der Attrappe -- dieselbe Uhr, mit der
        ``sende`` seine Zeitstempel setzt.

        Ohne sie muesste der Aufrufer fuer die Latenzmessung
        (``kennzahlen.Zug.latenz_s``) selbst ``time.monotonic()`` nehmen und
        den Nullpunkt der Attrappe abziehen -- zwei Uhren fuer eine Messung,
        und die Differenz waere nirgends belegt."""
        return time.monotonic() - self._start

    def naechste_message_id(self) -> int:
        """Die naechste message_id -- **eine** Folge fuer Bot und Gruppe.

        Das ist kein Detail, sondern die Bedingung dafuer, dass der Simulator
        ueberhaupt misst: der Bot merkt sich seinen Stand als
        ``letzte_beantwortete_message_id`` und
        ``letzte_extrahierte_message_id`` und liest danach nur, was **groesser**
        ist (``repo.unbeantwortete``, ``repo.unextrahierte``). Zaehlten die
        Stimmen in einer eigenen, niedrigeren Folge, laege jede ihrer
        Nachrichten ab dem zweiten Zug unter dem Wasserzeichen -- der Bot
        beantwortete sie nie, der Erkenner saehe sie nie, und der Lauf
        bestuende aus dem Bot, der mit sich selbst spricht. Telegram vergibt
        die ids ebenfalls fortlaufend je Chat, ueber alle Absender hinweg."""
        self._message_id += 1
        return self._message_id

    # -- was der Bot benutzt -------------------------------------------------

    def sende(self, chat_id: int, text: str) -> int:
        message_id = self.naechste_message_id()
        self.gesendet.append({
            "chat_id": chat_id,
            "text": text,
            "message_id": message_id,
            "zeit": time.monotonic() - self._start,
        })
        return message_id

    def tippt(self, chat_id: int) -> None:
        self.getippt.append(chat_id)

    def setze_befehle(self, befehle) -> None:
        self.befehle = list(befehle)

    def loesche_nachrichten(self, chat_id: int, message_ids) -> None:
        self.geloescht.append((chat_id, list(message_ids)))

    def lade_datei(self, file_id: str, ziel: Path) -> None:
        """No-Op: der Simulator schickt keine Audiodateien. Legt die Datei
        trotzdem an, damit ein Aufrufer, der danach ``Path.exists()`` prueft,
        nicht ueber eine Attrappe stolpert."""
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"")

    # -- was der Simulator benutzt ------------------------------------------

    def texte(self, ab: int = 0) -> list[str]:
        """Die Texte der Bot-Nachrichten ab Index ``ab`` -- der Schnitt, mit
        dem der Lauf einen Zug von seinem Nachfolger trennt."""
        return [n["text"] for n in self.gesendet[ab:]]
