"""Startroutine und Polling-Schleife (Aufgabe 4, SPEC-kontext-architektur.md § 9.1).

Aufgabe 8 haengt die Aufnahme-Pipeline (Download, Transkription, Verdichtung)
an der Weiche in schleife() ein: Sprachnachrichten laufen im
ThreadPoolExecutor, ein Hintergrund-Thread ruft daneben periodisch den
Nachhol-Arbeiter auf (§ 10.3). Der Gespraechszug (ablauf.py) kommt erst in
Aufgabe 10 -- bis dahin bleibt an dieser Stelle die Log-Zeile stehen.
"""

import logging
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx

from theatersoap import aufnahme, db, einstellungen, repo, telegram
from theatersoap.einstellungen import Einstellungen
from theatersoap.llm import LLM
from theatersoap.telegram import Telegram, TelegramFehler

log = logging.getLogger(__name__)

#: Anzahl gleichzeitiger Uploads/Transkriptionen. Gemessen (§ 11.3 Punkt 4):
#: kein Rate-Limiting bei Whisper festgestellt, zehn gleichzeitige Uploads
#: gingen alle durch -- der Thread-Pool darf grosszuegig parallel arbeiten.
POOL_GROESSE = 8

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

    None bedeutet: kein Nachrichtenupdate, Duplikat, oder Nachtstau bei einer
    Nicht-Sprachnachricht. Eine Sprachnachricht wird auch bei Nachtstau trotz
    unterdrueckt=1 zurueckgeliefert, weil sie noch zur Aufnahme-Pipeline muss
    (Auftragshinweis 1) -- sonst verschwaende ein Interview, das ueber Nacht
    eintrifft, spurlos."""
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
    if nachtstau and nachricht["typ"] != "sprache":
        return None  # gespeichert, aber ueber Nacht aufgelaufen -- kein Zug

    # Sprachnachrichten muessen die Pipeline auch bei Nachtstau erreichen: sonst
    # wird die Audiodatei nie heruntergeladen, und der Nachhol-Arbeiter (§ 10.3)
    # kann eine Zeile, die nie in 'aufnahme' entstand, nicht retten (SPEC § 9.1).
    # unterdrueckt bleibt in diesem Fall trotzdem 1 -- es wird nur kein Zug daraus.
    return nachricht


def _bearbeite_sprachnachricht(conn, tg, klm, e, stt_klient, nachricht: dict) -> None:
    """Laeuft im ThreadPoolExecutor: Download und Transkription duerfen die
    Polling-Schleife nie blockieren, sonst haengt die ganze Gruppe an einer
    einzigen Sprachnachricht (SPEC § 10.2). Download (empfange) und
    Transkription (verarbeite) laufen bewusst im selben Pool-Auftrag
    nacheinander -- die eigentliche Absicherung ist, dass empfange() die Datei
    sichert, bevor verarbeite() ueberhaupt Whisper fragt, nicht dass beide in
    getrennten Auftraegen liefen."""
    try:
        aufnahme_id = aufnahme.empfange(conn, tg, e, nachricht)
        if aufnahme_id is None:
            return  # Download endgueltig gescheitert -- schon gemeldet, siehe aufnahme.empfange
        aufnahme.verarbeite(conn, tg, klm, e, stt_klient, aufnahme_id)
    except Exception:
        log.exception(
            "Aufnahme-Pipeline fehlgeschlagen: chat_id=%s message_id=%s",
            nachricht["chat_id"], nachricht["message_id"],
        )


def _nachhol_schleife(stop: threading.Event, conn, e: Einstellungen, tg, klm, stt_klient) -> None:
    """Ruft aufnahme.nachholen() beim Start und danach alle
    aufnahme.NACHHOL_INTERVALL_S Sekunden auf (§ 10.3). Laeuft in einem
    eigenen Daemon-Thread; eine Ausnahme darf ihn nie stoppen (global-
    constraints.md 'Fehlerhaltung')."""
    while not stop.is_set():
        try:
            aufnahme.nachholen(conn, tg, klm, e, stt_klient)
        except Exception:
            log.exception("Nachholen fehlgeschlagen")
        stop.wait(aufnahme.NACHHOL_INTERVALL_S)


def schleife(
    conn: sqlite3.Connection,
    e: Einstellungen,
    tg: Telegram,
    klm,
    stt_klient,
    pool: ThreadPoolExecutor,
) -> None:
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
                        # Aufgabe 8: Download und Transkription duerfen die
                        # Schleife nie blockieren, daher im Thread-Pool.
                        pool.submit(
                            _bearbeite_sprachnachricht, conn, tg, klm, e, stt_klient, nachricht,
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
    """Liest die Einstellungen, oeffnet die Datenbank und startet die Schleife.

    Ein ThreadPoolExecutor bearbeitet Sprachnachrichten, ein Daemon-Thread
    holt in festen Abstaenden nach, was liegen geblieben ist (Aufgabe 8,
    § 10.3) -- inklusive eines Anlaufs sofort beim Start, der genau denselben
    Weg nimmt wie die Nacht zwischen zwei Workshoptagen (§ 9.1 Schritt 3)."""
    logging.basicConfig(level=logging.INFO)

    e = einstellungen.laden()
    conn = db.verbinde(e.db_pfad)
    db.initialisiere(conn)

    klient = httpx.Client(timeout=30.0)
    tg = Telegram(e.bot_token, klient)
    klm = LLM(e, klient, conn)

    pool = ThreadPoolExecutor(max_workers=POOL_GROESSE)
    stop = threading.Event()
    nachhol_thread = threading.Thread(
        target=_nachhol_schleife, args=(stop, conn, e, tg, klm, klient), daemon=True,
    )
    nachhol_thread.start()

    try:
        schleife(conn, e, tg, klm, klient, pool)
    finally:
        stop.set()
        pool.shutdown(wait=False)


if __name__ == "__main__":
    main()
