"""Startroutine und Polling-Schleife (Aufgabe 4, SPEC-kontext-architektur.md § 9.1).

Aufgabe 8 haengt die Aufnahme-Pipeline (Download, Transkription, Verdichtung)
an der Weiche in schleife() ein: Sprachnachrichten laufen im
ThreadPoolExecutor, ein Hintergrund-Thread ruft daneben periodisch den
Nachhol-Arbeiter auf (§ 10.3). Aufgabe 10 haengt daneben den Gespraechszug
(ablauf.py) ein: Text-Ausloeser (Reply, @Erwaehnung, /Befehl) laufen im
selben Pool wie Sprachnachrichten, und beide Wege in die Aufnahme-Pipeline
(Live und Nachhol-Arbeiter) reichen ``ablauf.bearbeite`` als ``zug`` durch.
"""

import logging
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx

from theatersoap import ablauf, aufnahme, befehle, db, einstellungen, erkenner, repo, telegram
from theatersoap.einstellungen import Einstellungen
from theatersoap.llm import LLM
from theatersoap.telegram import Telegram, TelegramFehler

log = logging.getLogger(__name__)

#: Anzahl gleichzeitiger Uploads/Transkriptionen. Gemessen (§ 11.3 Punkt 4):
#: kein Rate-Limiting bei Whisper festgestellt, zehn gleichzeitige Uploads
#: gingen alle durch -- der Thread-Pool darf grosszuegig parallel arbeiten.
POOL_GROESSE = 8

NACHTSTAU_MINUTEN = 15

#: Ab dieser Pause seit der letzten Nachricht einer Gruppe schickt der Bot
#: beim Neustart eine kurze Wiederkehr-Zeile (teil-b.md Aufgabe 7) -- billiger
#: Hinweis, dass er wieder da ist, ohne die volle Erstkontakt-Begruessung zu
#: wiederholen.
PAUSE_GRENZE_STUNDEN = 2


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


#: Wortidentisch mit den ersten beiden Absaetzen von befehle._TEXT_HILFE
#: (teil-b.md Aufgabe 6/7): dieselbe Erklaerung zu Ansprache und
#: Interviewmodus, damit die einmalige Begruessung und das jederzeit
#: abrufbare /hilfe sich nie widersprechen. Erklaert in dieser Reihenfolge:
#: (1) wie man den Bot anspricht, (2) wie Interviews laufen, (3) /hilfe zeigt
#: den Rest (SPEC § 10.1, teil-b.md Aufgabe 7).
_TEXT_ERSTKONTAKT = (
    "Hallo, ich bin der Theaterbot fuer diesen Workshop.\n\n"
    "So sprecht ihr mich an: antwortet auf eine meiner Nachrichten, schreibt "
    "@{bot_name} davor, oder schickt mir eine Sprachnachricht. Untereinander "
    "koennt ihr reden, ohne dass ich dazwischenrede.\n\n"
    "So laufen Interviews: sagt \"wir machen jetzt ein Interview\", dann "
    "zeichne ich auf. \"Fertig\" beendet es.\n\n"
    "/hilfe zeigt den Rest."
)

_TEXT_WIEDERKEHR = "Bin wieder da. Wenn ihr weitermachen wollt, sagt mir Bescheid."


def erstkontakt(conn, tg, e, chat_id: int) -> None:
    """Schickt die Begruessung genau einmal je Gruppe (teil-b.md Aufgabe 7):
    erklaert Ansprache, Interviewmodus und /hilfe, in dieser Reihenfolge.
    'Es existiert noch keine Bot-Nachricht' ist die Bedingung dafuer, dass sie
    noch aussteht -- danach wird sie selbst als Bot-Nachricht mitgeschrieben,
    sonst wuerde sie beim naechsten Update erneut ausgeloest. Ein
    Sendefehlschlag wird nur geloggt: die Gruppe bekommt beim naechsten
    Update einen weiteren Versuch, aber der Bot bleibt insgesamt
    funktionsfaehig (global-constraints.md 'Fehlerhaltung')."""
    if repo.hat_bot_nachricht(conn, chat_id):
        return
    text = _TEXT_ERSTKONTAKT.format(bot_name=e.bot_name)
    try:
        message_id = tg.sende(chat_id, text)
        repo.merke_nachricht(
            conn, chat_id, message_id, e.bot_name, 1, "text", text, repo._jetzt(),
        )
    except Exception:
        log.exception("Erstkontakt-Begruessung fehlgeschlagen, chat_id=%s", chat_id)


def begruessung_faellig(letzte_nachricht_am: str, jetzt) -> bool:
    """Liefert True, wenn seit der letzten Nachricht einer Gruppe mehr als
    PAUSE_GRENZE_STUNDEN vergangen sind (teil-b.md Aufgabe 7) -- analog zu
    ist_nachtstau(), Grundlage fuer die kurze Wiederkehr-Zeile beim
    Neustart."""
    letzte = datetime.fromisoformat(letzte_nachricht_am)
    return jetzt - letzte > timedelta(hours=PAUSE_GRENZE_STUNDEN)


def sende_wiederkehr_begruessungen(conn, tg, e, jetzt) -> None:
    """Schickt jeder Gruppe dieses Bot-Prozesses eine kurze Wiederkehr-Zeile,
    wenn seit ihrer letzten Nachricht mehr als PAUSE_GRENZE_STUNDEN vergangen
    sind (teil-b.md Aufgabe 7) -- gedacht fuer einen Neustart nach einer
    laengeren Pause (z. B. ueber Nacht). Ein Fehlschlag je Gruppe wird nur
    geloggt und reisst weder die anderen Gruppen noch den Bot-Start mit."""
    for gruppe in repo.gruppen_fuer_bot(conn, e.bot_name):
        try:
            letzte = repo.letzte_nachricht_zeit(conn, gruppe["chat_id"])
            if letzte is None or not begruessung_faellig(letzte, jetzt):
                continue
            message_id = tg.sende(gruppe["chat_id"], _TEXT_WIEDERKEHR)
            repo.merke_nachricht(
                conn, gruppe["chat_id"], message_id, e.bot_name, 1, "text",
                _TEXT_WIEDERKEHR, repo._jetzt(),
            )
        except Exception:
            log.exception(
                "Wiederkehr-Begruessung fehlgeschlagen, chat_id=%s", gruppe["chat_id"],
            )


def warmlaufen(klm, conn, e) -> None:
    """Setzt einen winzigen Absichtserkenner-Aufruf ins Leere ab (teil-b.md
    Aufgabe 8): google/gemma-4-31B-it hat 28,5 Sekunden Kaltstart, danach
    unter einer Sekunde. Ohne das wuerde die erste ECHTE Erkennung der ersten
    Gruppe eine halbe Minute warten -- mitten im Workshop-Beginn. Laeuft in
    main() in einem eigenen Daemon-Thread; ein Fehlschlag wird nur geloggt --
    der naechste echte Aufruf zahlt dann eben doch den Kaltstart, aber weder
    dieser Aufruf noch der Bot-Start selbst duerfen daran haengen bleiben."""
    try:
        klm.schema(
            None, "Testaufruf.", "Testaufruf.", erkenner.SCHEMA, "erkenner",
            modell=e.erkenner_modell, temperature=erkenner.TEMPERATURE,
        )
    except Exception:
        log.exception("Warmlauf des Absichtserkenners fehlgeschlagen")


def _zug_und_erkenner(conn, tg, klm, e, chat_id: int, hinweis: str | None = None) -> None:
    """Fuehrt den Gespraechszug aus und stoesst DANACH den Absichtserkenner
    im selben Hintergrund-Pool-Auftrag an (teil-b.md Aufgabe 8) -- nach dem
    Zug, nicht davor, damit die Bot-Antwort schon in der Gruppe steht, wenn
    der Erkenner seinen eigenen Kontext baut. ``ablauf.bearbeite`` kuemmert
    sich um Sperre und Sammeln wie bisher; ``erkenner.laufe`` faengt jeden
    eigenen Fehlschlag intern ab (geloggt, als vorfall vermerkt), bleibt also
    fuer die Gruppe unsichtbar, genau wie ein misslungener Gespraechszug
    selbst."""
    ablauf.bearbeite(conn, tg, klm, e, chat_id, hinweis=hinweis)
    erkenner.laufe(klm, tg, conn, e, chat_id)


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
        # Aufgabe 10: der echte Gespraechszug fuer Klasse *kurz* -- die
        # Alters-/Nachhol-Pruefung in aufnahme._kurz_abschliessen entscheidet,
        # ob er ueberhaupt aufgerufen wird. Aufgabe 8: _zug_und_erkenner haengt
        # danach noch den Absichtserkenner an, im selben Pool-Auftrag.
        aufnahme.verarbeite(conn, tg, klm, e, stt_klient, aufnahme_id, zug=_zug_und_erkenner)
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
            # Aufgabe 10: zug wird durchgereicht, aber aufnahme._kurz_abschliessen
            # ruft ihn bei nachgeholt=True strukturell nie auf (SPEC: "Nachgeholtes
            # loest nie eine Antwort aus") -- die Alterspruefung allein genuegt
            # nicht, siehe Docstring von aufnahme.verarbeite. Aufgabe 8:
            # _zug_und_erkenner haengt danach noch den Absichtserkenner an.
            aufnahme.nachholen(conn, tg, klm, e, stt_klient, zug=_zug_und_erkenner)
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
                    # Aufgabe 7: die Begruessung kommt genau einmal je Gruppe --
                    # erstkontakt() prueft das selbst (repo.hat_bot_nachricht)
                    # und ist deshalb ein billiger No-Op bei jeder weiteren
                    # Nachricht derselben Gruppe.
                    erstkontakt(conn, tg, e, nachricht["chat_id"])
                    if nachricht["typ"] == "sprache":
                        # Aufgabe 8: Download und Transkription duerfen die
                        # Schleife nie blockieren, daher im Thread-Pool.
                        pool.submit(
                            _bearbeite_sprachnachricht, conn, tg, klm, e, stt_klient, nachricht,
                        )
                    elif ablauf.ist_ausloeser(nachricht, e.bot_name):
                        # Aufgabe 10: Text-Ausloeser (Reply auf den Bot,
                        # @Erwaehnung, /Befehl) laufen im selben Pool wie
                        # Sprachnachrichten, damit ein laufender Gespraechszug
                        # (der mehrere Sekunden dauern kann) die Polling-Schleife
                        # nie blockiert. ablauf._sperre_fuer buendelt parallel
                        # eintreffende Ausloeser zu einem einzigen Sammelzug.
                        # Aufgabe 8: _zug_und_erkenner haengt danach noch den
                        # Absichtserkenner an, im selben Pool-Auftrag.
                        pool.submit(_zug_und_erkenner, conn, tg, klm, e, nachricht["chat_id"])
                    # sonst: beilaeufige Nachricht -- gespeichert (s.o.), aber
                    # kein Zug (SPEC § 1.2).
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

    # Aufgabe 6: einmal beim Start, damit die Befehle im Telegram-Menue
    # erscheinen, wenn jemand '/' tippt. Ein Fehlschlag wird nur geloggt --
    # ohne die Befehle im Menue funktioniert der Bot trotzdem, sie muessten
    # nur von Hand getippt werden.
    try:
        tg.setze_befehle(befehle.BEFEHLE_LISTE)
    except Exception:
        log.exception("setMyCommands fehlgeschlagen")

    # Aufgabe 8: winziger Absichtserkenner-Aufruf ins Leere, im Hintergrund,
    # gegen den 28,5-Sekunden-Kaltstart von gemma -- die erste ECHTE
    # Erkennung soll nicht darauf warten muessen.
    threading.Thread(target=warmlaufen, args=(klm, conn, e), daemon=True).start()

    # Aufgabe 7: kurze Wiederkehr-Zeile fuer Gruppen, deren letzte Nachricht
    # mehr als PAUSE_GRENZE_STUNDEN zurueckliegt (z. B. Neustart am naechsten
    # Morgen). Fehlschlaege je Gruppe werden schon in der Funktion geloggt.
    try:
        sende_wiederkehr_begruessungen(conn, tg, e, datetime.now(timezone.utc))
    except Exception:
        log.exception("Wiederkehr-Begruessungen fehlgeschlagen")

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
