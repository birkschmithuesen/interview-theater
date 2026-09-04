"""Gespraechszug -- Aufgabe 10, der letzte Baustein des Durchstichs
(SPEC-kontext-architektur.md § 1.2, § 1.3).

Drei getrennte Fragen, sauber auseinandergehalten:

1. **Ausloesen** (``ist_ausloeser``) -- soll DIESE eine Nachricht ueberhaupt
   einen Zug anstossen? Reply auf eine Bot-Nachricht, ``@botname``-Erwaehnung,
   ``/``-Befehl, Sprachnachricht -- sonst nichts. Beilaeufiges Geplauder wird
   trotzdem gespeichert (das erledigt schon ``bot.verarbeite_update``), aber
   nie beantwortet.
2. **Sammeln** (``bearbeite``) -- eine Sperre je ``chat_id`` sorgt dafuer,
   dass waehrend ein Aufruf laeuft, keine zweite Anfrage losprescht. Kommt
   die Antwort zurueck, wird alles seit dem letzten Wasserzeichen als EIN
   naechster Zug behandelt, egal wie viele Nachrichten inzwischen
   aufgelaufen sind (SPEC § 1.3). Ohne diese Sperre wuerde jede Nachricht
   ihren eigenen Aufruf anstossen: drei parallele Anfragen, drei teils
   widersprechende Antworten in zufaelliger Reihenfolge -- der
   wahrscheinlichste Weg, wie der Bot am Samstagvormittag chaotisch wirkt.
3. **Antworten** (``antworte``) -- baut den Kontext, fragt das Sprachmodell,
   schickt und protokolliert die Antwort. Scheitert der Aufruf, bekommt die
   Gruppe eine kurze, ehrliche Zeile statt einer Fehlermeldung im
   Sekundentakt -- das Wasserzeichen rueckt in JEDEM Fall vor (finally),
   sonst wuerde ein kaputter Zug endlos wiederholt (global-constraints.md
   'Fehlerhaltung').

Es gibt bewusst KEINE Rueckfrage-Sequenz mehr (SPEC § 1.4, ersatzlos
gestrichen) -- Sprachnachrichten loesen ohnehin immer aus, das war der
Hauptfall.
"""

import logging
import threading
from contextlib import contextmanager

from theatersoap import kontext, repo

log = logging.getLogger(__name__)

#: Waehrend ein Zug laeuft, alle TIPP_INTERVALL Sekunden ein erneutes
#: sendChatAction("typing"); nach HINWEIS_NACH Sekunden zusaetzlich eine
#: kurze Zeile (SPEC § 1.3). Die meiste Ungeduld entsteht daraus, dass gar
#: nichts passiert.
TIPP_INTERVALL = 4.0
HINWEIS_NACH = 10.0

_TEXT_HINWEIS = "Einen Moment, ich denke nach."
_TEXT_FEHLER = "Bei mir hakt gerade etwas - fragt nochmal."

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften, sonst lehnt der Anbieter den erzwungenen Modus ab
#: (global-constraints.md § 4).
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["antwort"],
    "properties": {
        "antwort": {"type": "string"},
    },
}

# Eine Sperre je chat_id, nicht eine einzige globale -- Gespraechszuege
# verschiedener Gruppen duerfen sich nie gegenseitig blockieren. Lebt fuer
# die Laufzeit des Prozesses (ein Prozess je Gruppe, siehe aufnahme.py); ein
# paar Bytes fuer ein threading.Lock je jemals gesehener chat_id sind kein
# Problem.
_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    """Liefert die (ggf. neu angelegte) Sperre fuer eine chat_id."""
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


def ist_ausloeser(n: dict, bot_name: str | None) -> bool:
    """Entscheidet, ob eine einzelne Nachricht einen Gespraechszug anstossen
    soll (SPEC § 1.2): Reply auf eine Bot-Nachricht, ``@botname``-Erwaehnung,
    ``/``-Befehl, oder eine Sprachnachricht -- sonst nichts.

    Wichtig: dieses Gatter entscheidet nur, OB ein Zug beginnt. Laeuft er
    einmal, nimmt ``bearbeite()``/``repo.unbeantwortete()`` ausnahmslos alles
    seit dem Wasserzeichen mit, auch beilaeufige Nachrichten, die
    zwischendurch aufgelaufen sind -- das Sammeln (§ 1.3) kennt keinen
    Unterschied zwischen Ausloeser und Mitlaeufer."""
    if n.get("typ") == "sprache":
        return True
    if n.get("antwortet_auf_bot"):
        return True
    text = n.get("text") or ""
    if text.startswith("/"):
        return True
    if bot_name and f"@{bot_name}".lower() in text.lower():
        return True
    return False


@contextmanager
def _tippanzeige(tg, chat_id: int):
    """Haelt die Tippanzeige waehrend eines laufenden Sprachmodell-Aufrufs am
    Leben (SPEC § 1.3): alle TIPP_INTERVALL Sekunden erneut ``tg.tippt``,
    nach HINWEIS_NACH Sekunden zusaetzlich eine kurze Zeile.

    Laeuft in einem Daemon-Thread, der beim Verlassen des with-Blocks sauber
    beendet wird: ``stop.set()`` laesst das laufende ``stop.wait()`` sofort
    zurueckkehren, ``join()`` wartet, bis der Thread das auch wirklich
    mitbekommen hat. Ein Fehlschlag der Tippanzeige selbst (Telegram down,
    was auch immer) darf den eigentlichen Zug nie stoeren -- deshalb wird
    hier alles abgefangen und nur geloggt."""
    stop = threading.Event()

    def _lauf() -> None:
        vergangen = 0.0
        hinweis_gesendet = False
        while not stop.wait(TIPP_INTERVALL):
            vergangen += TIPP_INTERVALL
            try:
                tg.tippt(chat_id)
            except Exception:
                log.exception("Tippanzeige fehlgeschlagen, chat_id=%s", chat_id)
            if not hinweis_gesendet and vergangen >= HINWEIS_NACH:
                hinweis_gesendet = True
                try:
                    tg.sende(chat_id, _TEXT_HINWEIS)
                except Exception:
                    log.exception("Hinweis-Zeile fehlgeschlagen, chat_id=%s", chat_id)

    thread = threading.Thread(target=_lauf, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=TIPP_INTERVALL + 1.0)


def antworte(conn, tg, klm, e, chat_id: int, offen: list) -> None:
    """Baut den Kontext aus allem seit dem Wasserzeichen, fragt das
    Sprachmodell und schickt/protokolliert die Antwort.

    Das Wasserzeichen (``repo.setze_beantwortet_bis``) rueckt im ``finally``
    vor -- IMMER, auch wenn der Aufruf scheitert. Ein gescheiterter Zug rueckt
    trotzdem vor, sonst wuerde er endlos wiederholt und die Gruppe saehe
    dieselbe Fehlermeldung im Sekundentakt; sie fragt bei Bedarf selbst
    nochmal (global-constraints.md 'Fehlerhaltung').

    ``offen`` ist die Liste der Nachrichten seit dem Wasserzeichen (aeltester
    zuerst, siehe ``repo.unbeantwortete``) -- sowohl der eigentliche Ausloeser
    als auch alles, was inzwischen an Mitlaeufern aufgelaufen ist (SPEC
    § 1.3)."""
    letzte_message_id = max(n["message_id"] for n in offen)
    try:
        with _tippanzeige(tg, chat_id):
            koerper = kontext.baue(conn, chat_id, offen, e)
            ergebnis = klm.schema(chat_id, kontext.SYSTEM, koerper, SCHEMA, "gespraech")
            text = ergebnis["antwort"]

        message_id = tg.sende(chat_id, text)
        # Die Antwort des Modells wird als Bot-Nachricht mitgeschrieben, damit
        # sie im Verlaufsfenster des naechsten Zuges steht (kontext.baue liest
        # sie ueber repo.letzte_nachrichten mit) -- sonst wuerde das Modell
        # seine eigenen frueheren Aeusserungen vergessen.
        repo.merke_nachricht(
            conn, chat_id, message_id, e.bot_name, 1, "text", text, repo._jetzt(),
        )
    except Exception:
        log.exception("Gespraechszug fehlgeschlagen, chat_id=%s", chat_id)
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "gespraechszug_fehlgeschlagen",
            "Sprachmodell-Aufruf im Gespraechszug fehlgeschlagen",
        )
        try:
            tg.sende(chat_id, _TEXT_FEHLER)
        except Exception:
            log.exception("Fehlermeldung an die Gruppe fehlgeschlagen, chat_id=%s", chat_id)
    finally:
        repo.setze_beantwortet_bis(conn, chat_id, letzte_message_id)


def bearbeite(conn, tg, klm, e, chat_id: int) -> None:
    """Ein Gespraechszug (SPEC § 1.2, § 1.3): hoechstens ein laufender Aufruf
    je Gruppe, Nachzuegler werden gesammelt statt einen eigenen Aufruf
    anzustossen.

    Die aeussere while-Schleife ist kein Zierrat, sondern die eigentliche
    Absicherung: ohne sie gaebe es ein Zeitfenster zwischen der Abfrage von
    ``unbeantwortete()`` und der Freigabe der Sperre, in dem eine neu
    eintreffende Nachricht liegen bliebe -- ihr eigener ``bearbeite()``-Aufruf
    traeffe auf eine gehaltene Sperre und liefe ins ``return``, ohne dass der
    gerade laufende Zug sie noch gesehen haette. Mit der Schleife greift
    GENAU dieser Zug nach dem Freigeben der Sperre erneut zu und findet die
    nachgezuegelte Nachricht -- keine Rekursion, kein verlorener Beitrag."""
    while True:
        sperre = _sperre_fuer(chat_id)
        if not sperre.acquire(blocking=False):
            return  # laeuft schon fuer diese Gruppe; der laufende Zug sammelt weiter
        try:
            offen = repo.unbeantwortete(conn, chat_id)
            if not offen:
                return
            antworte(conn, tg, klm, e, chat_id, offen)
        finally:
            sperre.release()
