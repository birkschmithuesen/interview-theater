"""Startroutine und Polling-Schleife (Aufgabe 4, SPEC-kontext-architektur.md § 9.1).

Aufgabe 8 haengt die Aufnahme-Pipeline (Download, Transkription, Verdichtung)
an der Weiche in schleife() ein: Sprachnachrichten laufen im
ThreadPoolExecutor, ein Hintergrund-Thread ruft daneben periodisch den
Nachhol-Arbeiter auf (§ 10.3). Aufgabe 10 haengt daneben den Gespraechszug
(ablauf.py) ein: Textnachrichten -- heute jede, siehe ablauf.ist_ausloeser --
laufen im selben Pool wie Sprachnachrichten, und beide Wege in die
Aufnahme-Pipeline (Live und Nachhol-Arbeiter) reichen ``ablauf.bearbeite``
als ``zug`` durch.
"""

import logging
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx

from interview_theater import (
    ablauf, aufnahme, befehle, db, einstellungen, erkenner, journal, knoepfe, phasen,
    repo, telegram,
)
from interview_theater.einstellungen import Einstellungen
from interview_theater.llm import LLM
from interview_theater.telegram import Telegram, TelegramFehler

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
#: (teil-b.md Aufgabe 6/7): dieselbe Erklaerung, damit die einmalige
#: Begruessung und das jederzeit abrufbare /hilfe sich nie widersprechen.
#: Erklaert in dieser Reihenfolge: (1) dass der Bot auf alles antwortet --
#: die Gruppe ist ein reines Interface zu ihm, nicht ihr Diskussionsraum,
#: das findet im Raum statt --, (2) wie Interviews laufen, (3) /hilfe zeigt
#: den Rest (SPEC § 1.2, § 10.1, teil-b.md Aufgabe 7).
_TEXT_ERSTKONTAKT = (
    "Hallo, ich bin der Theaterbot fuer diesen Workshop.\n\n"
    "Schreibt oder sprecht einfach - ich lese alles mit und antworte.\n\n"
    "So laufen Interviews: tippt \"Aufnahme starten\" an, dann zeichne ich "
    "auf. Ein zweiter Druck beendet das Interview.\n\n"
    "Die Knoepfe unten zeigen euch den Weg."
)

#: Dieselbe Begruessung, aber fuer den Regelfall: eine Gruppe, die gerade
#: erst anfaengt, steht in Phase 1 (Begriffe) -- und dort gibt es nichts
#: aufzunehmen. Der zweite Absatz sagt deshalb, was JETZT dran ist, statt
#: wie man ein Interview startet.
#:
#: Anlass (05.09.2026, Birk im laufenden Workshop): "aber direkt schon mit
#: aufnahme starten? nach der begruessung kommt erst die eingabe der begriffe
#: und damit die fragen zu erstellen. hast du die reihenfolge der phasen
#: beachtet?" -- passend dazu steht unter dieser Begruessung auch kein
#: Aufnahme-Knopf mehr (``knoepfe._aufnahme_anbieten``).
_TEXT_ERSTKONTAKT_BEGRIFFE = (
    "Hallo, ich bin der Theaterbot fuer diesen Workshop.\n\n"
    "Schreibt oder sprecht einfach - ich lese alles mit und antworte.\n\n"
    "Als Erstes schickt ihr mir eure Begriffe aus dem Plenum: getippt oder "
    "als Sprachnachricht, so wie sie bei euch an der Wand stehen. Ich halte "
    "sie fest und ordne sie mit euch.\n\n"
    "Daraus entwickeln wir dann eure Interviewfragen - und erst danach geht "
    "es ans Aufnehmen.\n\n"
    "Die Knoepfe unten zeigen euch den Weg."
)

#: Angehaengt, wenn eine Weboberflaeche konfiguriert ist (IT_WEB_URL): die
#: Leseansicht der Gruppe, zum Mitlesen neben dem Chat. Der Link ist das
#: Geheimnis (kein Login) -- er geht nur in diese eine Gruppe.
_TEXT_GRUPPENSEITE = (
    "\n\nAlles, was wir festhalten, koennt ihr hier mitlesen (nur fuer eure "
    "Gruppe): {url}"
)

#: Die Wiederkehr-Zeile nennt die Arbeitsphase: nach einer Nacht Pause ist
#: die erste Frage im Raum, wo man stehengeblieben ist -- und die Phase ist
#: seit dem 04.09.2026 ein gespeicherter Zustand, der das beantworten kann
#: (interview_theater/phasen.py). Stimmt sie nicht mehr, korrigiert die Gruppe sie
#: mit einem Satz. Der Weg weiter steht seit 05.09.2026 als Knoepfe darunter
#: (``knoepfe.biete_einstieg``), nicht als Slash-Befehl im Text.
_TEXT_WIEDERKEHR = (
    "Bin wieder da. Wir sind bei {phase}. Wenn ihr weitermachen wollt, "
    "sagt mir Bescheid - oder tippt einen Knopf an."
)


def stelle_link_sicher(conn, e, chat_id: int) -> str | None:
    """Die URL der Gruppenseite -- und sie entsteht hier, falls es die
    Gruppenzeile noch nicht gibt (05.09.2026, Birk: "stelle sicher, dass zu
    Beginn bei der Begruessung die Website als Link angeboten wird").

    Der Grund: ``repo.gruppenseite_url`` braucht ``gruppe.web_token``, und
    das entsteht in ``repo.stelle_web_token_sicher`` -- aber nur, wenn es die
    Zeile ``gruppe`` ueberhaupt schon gibt. Im Regelweg legt
    ``verarbeite_update`` sie ueber ``repo.sichere_gruppe`` an, BEVOR
    irgendein Zug laeuft; ruft aber jemand ``erstkontakt`` von woanders auf
    (Rueckfallweg aus ``ablauf.antworte``, ein Test, ein spaeterer Aufrufer),
    faellt der Link sonst stillschweigend weg -- und die Gruppe erfaehrt nie,
    wo sie mitlesen kann.

    Deshalb wird die Zeile hier notfalls angelegt. Ohne ``IT_WEB_URL`` gibt
    es weiterhin keinen Link, das ist kein Fehlerfall."""
    basis = getattr(e, "web_url", "")
    if not basis:
        return None
    url = repo.gruppenseite_url(conn, chat_id, basis)
    if url:
        return url
    repo.sichere_gruppe(conn, chat_id, getattr(e, "bot_name", ""), "")
    return repo.gruppenseite_url(conn, chat_id, basis)


def erstkontakt(conn, tg, e, chat_id: int) -> None:
    """Schickt die Begruessung genau einmal je Gruppe (teil-b.md Aufgabe 7):
    erklaert, dass der Bot auf alles antwortet, den Interviewmodus und den
    Link zur Gruppenseite, in dieser Reihenfolge.
    'Es existiert noch keine Bot-Nachricht' ist die Bedingung dafuer, dass sie
    noch aussteht -- danach wird sie selbst als Bot-Nachricht mitgeschrieben,
    sonst wuerde sie beim naechsten Update erneut ausgeloest. Ein
    Sendefehlschlag wird nur geloggt: die Gruppe bekommt beim naechsten
    Update einen weiteren Versuch, aber der Bot bleibt insgesamt
    funktionsfaehig (global-constraints.md 'Fehlerhaltung').

    Der Link steht seit dem 05.09.2026 GARANTIERT drin, sobald ``IT_WEB_URL``
    gesetzt ist: ``stelle_link_sicher`` legt die Gruppenzeile notfalls selbst
    an, statt sich darauf zu verlassen, dass ``verarbeite_update`` vorher
    gelaufen ist. Darunter haengen die Einstiegsknoepfe
    (``knoepfe.biete_einstieg``) -- die Begruessung nennt deshalb keinen
    Slash-Befehl mehr."""
    from interview_theater import knoepfe  # spaeter Import, haelt den Modulkopf frei

    if repo.hat_bot_nachricht(conn, chat_id):
        return
    # Phase 1 (Begriffe) ist der Regelfall beim Erstkontakt: dann sagt die
    # Begruessung, dass jetzt die Begriffsliste aus dem Plenum kommt, und
    # nicht, wie man eine Aufnahme startet (05.09.2026).
    vorlage = (
        _TEXT_ERSTKONTAKT_BEGRIFFE
        if phasen.aktuelle(conn, chat_id) < knoepfe.PHASE_INTERVIEWS
        else _TEXT_ERSTKONTAKT
    )
    text = vorlage.format(bot_name=e.bot_name)
    url = stelle_link_sicher(conn, e, chat_id)
    if url:
        text += _TEXT_GRUPPENSEITE.format(url=url)
    try:
        message_id = knoepfe.biete_einstieg(conn, tg, chat_id, text)
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
    geloggt und reisst weder die anderen Gruppen noch den Bot-Start mit.

    Mit Knoepfen seit 05.09.2026 (``knoepfe.biete_einstieg``): "Aufnahme
    starten", ggf. "Weiter zu Phase N", "Stand zeigen", "Hilfe" -- der Weg
    zurueck in die Arbeit ist ein Druck, nicht ein Befehl, den sich jemand
    ueber Nacht merken musste."""
    from interview_theater import knoepfe  # spaeter Import, haelt den Modulkopf frei

    for gruppe in repo.gruppen_fuer_bot(conn, e.bot_name):
        try:
            letzte = repo.letzte_nachricht_zeit(conn, gruppe["chat_id"])
            if letzte is None or not begruessung_faellig(letzte, jetzt):
                continue
            text = _TEXT_WIEDERKEHR.format(
                phase=phasen.bezeichnung(phasen.aktuelle(conn, gruppe["chat_id"]))
            )
            message_id = knoepfe.biete_einstieg(conn, tg, gruppe["chat_id"], text)
            repo.merke_nachricht(
                conn, gruppe["chat_id"], message_id, e.bot_name, 1, "text",
                text, repo._jetzt(),
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
    """Fuehrt den Gespraechszug aus und stoesst DANACH Absichtserkenner UND
    Journal-Extraktor im selben Hintergrund-Pool-Auftrag an (teil-b.md
    Aufgabe 8, journal.py) -- nach dem Zug, nicht davor, damit die
    Bot-Antwort schon in der Gruppe steht, wenn beide ihren eigenen Kontext
    bauen. ``ablauf.bearbeite`` kuemmert sich um Sperre und Sammeln wie
    bisher; ``erkenner.laufe`` und ``journal.laufe`` fangen jeden eigenen
    Fehlschlag intern ab (geloggt, als vorfall vermerkt), bleiben also fuer
    die Gruppe unsichtbar, genau wie ein misslungener Gespraechszug selbst.

    Reihenfolge Erkenner vor Journal-Extraktor: rein konventionell, es gibt
    keine Abhaengigkeit zwischen beiden -- der Journal-Extraktor laeuft
    ohnehin nur bei Verdraengung (meistens also gar nicht) und schreibt eine
    andere Journal-Kategorie als der Erkenner (Arbeitsteilung, siehe
    journal.py Moduldocstring)."""
    ablauf.bearbeite(conn, tg, klm, e, chat_id, hinweis=hinweis)
    erkenner.laufe(klm, tg, conn, e, chat_id)
    journal.laufe(klm, conn, e, chat_id)


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


def _bearbeite_knopfdruck(conn, tg, klm, e, druck: dict) -> None:
    """Laeuft im ThreadPoolExecutor: ein Knopfdruck kostet zwei bis drei
    HTTP-Aufrufe (answerCallbackQuery, sendMessage, editMessageReplyMarkup),
    und die Polling-Schleife darf daran nicht haengen -- genauso wenig wie an
    einer Sprachnachricht (SPEC § 10.2).

    Ein Fehlschlag wird nur geloggt: er darf weder die Schleife stoppen noch
    das Weiterruecken der update_id verhindern (global-constraints.md
    'Fehlerhaltung')."""
    try:
        knoepfe.behandle(conn, tg, klm, e, druck)
    except Exception:
        log.exception("Knopfdruck fehlgeschlagen, chat_id=%s", druck.get("chat_id"))


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
                # Knopfdruck ZUERST und unabhaengig von verarbeite_update:
                # ein callback_query ist keine Nachricht, hat keine
                # message_id in 'nachricht' und darf weder Nachtstau noch
                # Duplikatpruefung durchlaufen (05.09.2026,
                # interview_theater/knoepfe.py). Er greift damit genauso
                # frueh und deterministisch wie ein Slash-Befehl.
                druck = telegram.lies_knopfdruck(update)
                if druck is not None:
                    pool.submit(_bearbeite_knopfdruck, conn, tg, klm, e, druck)
                    continue
                nachricht = verarbeite_update(conn, e, update, jetzt, beim_start)
                if nachricht is not None:
                    # Die Begruessung entsteht seit 04.09. abends im ersten
                    # Gespraechszug aus der ersten Nachricht heraus
                    # (kontext.ERSTKONTAKT); erstkontakt() ist nur noch der
                    # Rueckfallweg bei Modellfehler (ablauf.antworte).
                    if nachricht["typ"] == "sprache":
                        # Aufgabe 8: Download und Transkription duerfen die
                        # Schleife nie blockieren, daher im Thread-Pool.
                        pool.submit(
                            _bearbeite_sprachnachricht, conn, tg, klm, e, stt_klient, nachricht,
                        )
                    elif ablauf.ist_ausloeser(nachricht, e.bot_name):
                        # Aufgabe 10: jede Textnachricht loest heute einen Zug
                        # aus (ablauf.ist_ausloeser, SPEC § 1.2 -- die Gruppe
                        # ist ein reines Interface zum Bot). Sie laeuft im
                        # selben Pool wie Sprachnachrichten, damit ein
                        # laufender Gespraechszug (der mehrere Sekunden dauern
                        # kann) die Polling-Schleife nie blockiert.
                        # ablauf._sperre_fuer buendelt parallel eintreffende
                        # Nachrichten zu einem einzigen Sammelzug. Aufgabe 8:
                        # _zug_und_erkenner haengt danach noch den
                        # Absichtserkenner an, im selben Pool-Auftrag.
                        pool.submit(_zug_und_erkenner, conn, tg, klm, e, nachricht["chat_id"])
                    # sonst: kein Zug. Mit der heutigen ist_ausloeser()-Logik
                    # (SPEC § 1.2: jede Nachricht loest aus) greift dieser
                    # Zweig praktisch nie -- verarbeite_update() liefert fuer
                    # unterdrueckte Textnachrichten (Nachtstau) ohnehin schon
                    # None und kommt gar nicht bis hierher. Das if/elif bleibt
                    # trotzdem bestehen: die eine dokumentierte Stelle, an der
                    # sich das wieder aendern liesse.
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
