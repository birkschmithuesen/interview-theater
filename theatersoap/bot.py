"""Startroutine und Polling-Schleife (Aufgabe 4, SPEC-kontext-architektur.md § 9.1).

Diese Erstfassung hoert zu und schreibt mit, antwortet aber noch nicht: die
Aufnahme-Pipeline fuer Sprachnachrichten kommt in Aufgabe 8, der Gespraechszug
in Aufgabe 10. Beide haengen sich an der Weiche in schleife() ein.
"""

import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import httpx

from theatersoap import db, einstellungen, repo, telegram
from theatersoap.einstellungen import Einstellungen
from theatersoap.telegram import Telegram, TelegramFehler

log = logging.getLogger(__name__)

NACHTSTAU_MINUTEN = 15


def ist_nachtstau(gesendet_am: str, jetzt: datetime) -> bool:
    """Liefert True, wenn gesendet_am mehr als 15 Minuten vor jetzt liegt
    (global-constraints.md § 9.1: 'aelter als 15 Minuten')."""
    gesendet = datetime.fromisoformat(gesendet_am)
    return jetzt - gesendet > timedelta(minutes=NACHTSTAU_MINUTEN)


def verarbeite_update(
    conn: sqlite3.Connection,
    e: Einstellungen,
    update: dict,
    jetzt: datetime,
    beim_start: bool,
) -> dict | None:
    """Normalisiert und speichert ein Update. Liefert das Nachrichten-Dictionary,
    wenn die Schleife noch etwas damit tun muss (Aufnahme-Pipeline oder
    Gespraechszug), sonst None.

    None bedeutet: kein Nachrichtenupdate, Duplikat, oder Nachtstau. Eine
    Sprachnachricht wird trotz unterdrueckt=1 zurueckgeliefert, weil sie noch
    zur Aufnahme-Pipeline muss (Auftragshinweis 1)."""
    nachricht = telegram.lies_nachricht(update)
    if nachricht is None:
        return None

    nachtstau = beim_start and ist_nachtstau(nachricht["gesendet_am"], jetzt)
    unterdrueckt = 1 if (nachtstau or nachricht["typ"] == "sprache") else 0

    repo.sichere_gruppe(conn, nachricht["chat_id"], e.bot_name, nachricht["chat_titel"])
    neu = repo.merke_nachricht(
        conn,
        nachricht["chat_id"],
        nachricht["message_id"],
        nachricht["absender"],
        0,
        nachricht["typ"],
        nachricht["text"],
        nachricht["gesendet_am"],
        unterdrueckt,
    )
    if not neu:
        return None  # Duplikat (INSERT OR IGNORE hat nichts eingefuegt)
    if nachtstau:
        return None  # gespeichert, aber ueber Nacht aufgelaufen -- kein Zug

    return nachricht


def schleife(conn: sqlite3.Connection, e: Einstellungen, tg: Telegram) -> None:
    """Long-Poll-Schleife. Laeuft, bis der Prozess beendet wird; eine einzelne
    kaputte Verarbeitung darf sie nie stoppen (global-constraints.md
    'Fehlerhaltung')."""
    beim_start = True  # nur der erste Durchlauf holt den Nachtstau ab (§ 9.1)

    while True:
        offset = repo.hole_update_id(conn, e.bot_name) + 1
        try:
            updates = tg.hole_updates(offset)
        except TelegramFehler as fehler:
            log.error("getUpdates fehlgeschlagen: %s", fehler)
            time.sleep(5)
            continue

        for update in updates:
            try:
                jetzt = datetime.now(timezone.utc)
                nachricht = verarbeite_update(conn, e, update, jetzt, beim_start)
                if nachricht is not None:
                    if nachricht["typ"] == "sprache":
                        # Weiche fuer Aufgabe 8: Aufnahme-Pipeline (Download,
                        # Transkription) haengt sich hier ein.
                        log.info(
                            "Sprachnachricht empfangen (Aufnahme-Pipeline folgt in "
                            "Aufgabe 8): chat_id=%s message_id=%s",
                            nachricht["chat_id"], nachricht["message_id"],
                        )
                    else:
                        # Weiche fuer Aufgabe 10: Gespraechszug haengt sich hier ein.
                        log.info(
                            "Nachricht wartet auf Gespraechszug (folgt in Aufgabe 10): "
                            "chat_id=%s message_id=%s",
                            nachricht["chat_id"], nachricht["message_id"],
                        )
            except Exception:
                log.exception(
                    "Verarbeitung eines Updates fehlgeschlagen, update_id=%s",
                    update.get("update_id"),
                )
            finally:
                # Ein kaputtes Update darf nicht endlos wiederholt werden --
                # die Position ruecken wir in jedem Fall weiter (Auftragshinweis 4).
                repo.setze_update_id(conn, e.bot_name, update["update_id"])

        beim_start = False


def main() -> None:
    """Liest die Einstellungen, oeffnet die Datenbank und startet die Schleife."""
    logging.basicConfig(level=logging.INFO)

    e = einstellungen.laden()
    conn = db.verbinde(e.db_pfad)
    db.initialisiere(conn)

    klient = httpx.Client(timeout=30.0)
    tg = Telegram(e.bot_token, klient)

    schleife(conn, e, tg)


if __name__ == "__main__":
    main()
