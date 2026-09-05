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
        #: Inline-Knoepfe (interview_theater/knoepfe.py) -- je Angebot ein
        #: Dict, damit ein Lauf nachtraeglich pruefen kann, ob der Bot an
        #: einem Auswahl-Moment ueberhaupt Knoepfe angeboten hat.
        self.knoepfe: list[dict] = []
        #: Die aktuell haengende Leiste je ``message_id`` -- was eine Gruppe
        #: auf dem Handy gerade antippen KANN. ``entferne_knoepfe`` nimmt sie
        #: heraus, ``aktualisiere_knoepfe`` tauscht sie aus.
        self.leisten: dict[int, list] = {}
        self.knoepfe_aktualisiert: list[tuple[int, int, list]] = []
        self.beantwortet: list[tuple[str, str]] = []
        self.knoepfe_entfernt: list[tuple[int, int]] = []
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

    def sende_mit_knoepfen(self, chat_id: int, text: str, knoepfe) -> int:
        """Inline-Knoepfe (interview_theater/knoepfe.py) im simulierten Lauf.

        Der Text geht denselben Weg wie bei ``sende``: fuer die Bewertung
        eines Laufs zaehlt, was in der Gruppe steht, nicht ob eine Tastatur
        darunter hing.

        Seit dem 06.09.2026 **merkt sich** die Attrappe die Leiste je
        ``message_id``: die Knoepfe sind der Hauptweg durch den Bot geworden
        (Grundleiste, Fragenauswahl, Figurenanzahl, Form je Szene,
        Phasenknoepfe), und eine Simulation, deren Stimmen nur sprechen,
        misst den Bot an einem Weg, den eine echte Gruppe nicht mehr geht."""
        message_id = self.sende(chat_id, text)
        self.knoepfe.append({
            "chat_id": chat_id,
            "text": text,
            "knoepfe": list(knoepfe),
            "message_id": message_id,
        })
        self.leisten[message_id] = list(knoepfe)
        return message_id

    def aktualisiere_knoepfe(self, chat_id: int, message_id: int, knoepfe) -> None:
        """Tauscht die Tastatur einer schon gesendeten Nachricht aus.

        Der Toggle der Fragenauswahl (``knoepfe._toggle_frage``) braucht das:
        ohne diese Methode faellt er in seinen ``except``-Zweig, die Haken
        werden nie sichtbar, und \"Diese 3 nehmen\" waehlt gegen eine
        Tastatur, die es so nie gab."""
        self.leisten[message_id] = list(knoepfe)
        self.knoepfe_aktualisiert.append((chat_id, message_id, list(knoepfe)))

    def beantworte_knopf(self, callback_query_id: str, text: str = "") -> None:
        self.beantwortet.append((callback_query_id, text))

    def entferne_knoepfe(self, chat_id: int, message_id: int) -> None:
        self.knoepfe_entfernt.append((chat_id, message_id))
        self.leisten.pop(message_id, None)

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

    def offene_knoepfe(self) -> list[dict]:
        """Alle Knoepfe, die gerade wirklich antippbar sind -- je Eintrag
        ``{"message_id", "text", "beschriftung", "daten"}``.

        Aus ``leisten``, nicht aus ``knoepfe``: die zweite Liste ist ein
        Protokoll aller je angebotenen Leisten, die erste der Stand jetzt.
        Eine Stimme, die einen laengst abgenommenen Knopf drueckt, misst
        nichts -- ``knoepfe.behandle`` antwortet darauf mit \"schon benutzt\".

        Juengste Nachricht zuerst: was zuletzt im Chat stand, ist das, was
        eine Gruppe auf dem Handy sieht.
        """
        nach_id = {n["message_id"]: n["text"] for n in self.gesendet}
        offen = []
        for message_id in sorted(self.leisten, reverse=True):
            for beschriftung, daten in self.leisten[message_id]:
                offen.append({
                    "message_id": message_id,
                    "text": nach_id.get(message_id, ""),
                    "beschriftung": beschriftung,
                    "daten": daten,
                })
        return offen
