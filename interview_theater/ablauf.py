"""Gespraechszug -- Aufgabe 10, der letzte Baustein des Durchstichs
(SPEC-kontext-architektur.md § 1.2, § 1.3).

Drei getrennte Fragen, sauber auseinandergehalten:

1. **Ausloesen** (``ist_ausloeser``) -- soll DIESE eine Nachricht ueberhaupt
   einen Zug anstossen? Die Gruppe ist ein reines Interface zum Bot (die
   Teilnehmerinnen sprechen im Raum miteinander, nicht im Chat), also loest
   heute JEDE Nachricht aus -- ausser sie ist als ``unterdrueckt``
   gespeichert (Nachtstau, Sprachnachricht ohne Transkript) oder stammt vom
   Bot selbst; das filtert ``repo.unbeantwortete``, nicht diese Funktion.
2. **Sammeln** (``bearbeite``) -- eine Sperre je ``chat_id`` sorgt dafuer,
   dass waehrend ein Aufruf laeuft, keine zweite Anfrage losprescht. Kommt
   die Antwort zurueck, wird alles seit dem letzten Wasserzeichen als EIN
   naechster Zug behandelt, egal wie viele Nachrichten inzwischen
   aufgelaufen sind (SPEC § 1.3). Ohne diese Sperre wuerde jede Nachricht
   ihren eigenen Aufruf anstossen: drei parallele Anfragen, drei teils
   widersprechende Antworten in zufaelliger Reihenfolge -- der
   wahrscheinlichste Weg, wie der Bot am Samstagvormittag chaotisch wirkt.
   Seit jede Nachricht ausloest, greift genau dieses Sammeln haeufiger als
   zuvor -- es ist wichtiger geworden, nicht verzichtbar.
3. **Antworten** (``antworte``) -- baut den Kontext, fragt das Sprachmodell,
   schickt und protokolliert die Antwort. Scheitert der Aufruf, bekommt die
   Gruppe eine kurze, ehrliche Zeile statt einer Fehlermeldung im
   Sekundentakt -- das Wasserzeichen rueckt in JEDEM Fall vor (finally),
   sonst wuerde ein kaputter Zug endlos wiederholt (global-constraints.md
   'Fehlerhaltung').

Es gibt bewusst KEINE Rueckfrage-Sequenz mehr (SPEC § 1.4, ersatzlos
gestrichen) -- inzwischen loest ohnehin jede Nachricht einen Zug aus, eine
gesonderte Rueckfrage-Logik waere ueberfluessig.
"""

import logging
import threading
from contextlib import contextmanager

from interview_theater import befehle, kontext, phasen, repo

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
    soll (SPEC § 1.2).

    Die Gruppe ist ein reines Interface zum Bot: die Teilnehmerinnen
    diskutieren nicht im Chat miteinander, das passiert im Raum. Der Chat
    existiert nur fuer die Arbeit mit dem Bot -- also ist JEDE Nachricht an
    ihn gerichtet, und JEDE Nachricht loest einen Zug aus. Es gibt bewusst
    kein "beilaeufiges Geplauder" mehr, das dieses Gatter aussortieren
    muesste.

    Diese Funktion bleibt trotzdem als eigene, dokumentierte Stelle stehen,
    statt ersatzlos zu verschwinden: sie ist der EINE Ort, an dem diese
    Entscheidung getroffen wird, und sie koennte sich -- fuer einen anderen
    Workshop-Zuschnitt -- wieder aendern.

    Wichtig: dieses Gatter entscheidet nur, OB ein Zug beginnt, nicht WAS in
    ihn eingeht. Laeuft er einmal, nimmt ``bearbeite()``/
    ``repo.unbeantwortete()`` ausnahmslos alles seit dem Wasserzeichen mit,
    das die Filterung nach ``unterdrueckt`` (Nachtstau, Sprachnachricht ohne
    Transkript) und ``ist_bot`` uebernimmt -- unabhaengig von dieser
    Funktion, die diesen Filter nicht dupliziert und ihn deshalb auch nicht
    umgehen kann."""
    return True


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


def antworte(conn, tg, klm, e, chat_id: int, offen: list, hinweis: str | None = None) -> None:
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
    § 1.3).

    ``hinweis`` (Aufgabe 5, § 10.1): eine optionale Zeile, die an die Antwort
    angehaengt wird -- der beilaeufige Materialhinweis, wenn eine lange
    Sprachnachricht ausserhalb des Interviewmodus eintraf. Keine eigene
    Nachricht, keine Rueckfrage: sie haengt an der ohnehin faelligen Antwort,
    kommt also nur an, wenn diese Antwort auch wirklich verschickt wird.

    Aufgabe 6 (Notausgang): bevor irgendein Kontext gebaut wird, prueft
    ``befehle.behandle``, ob die JUENGSTE Nachricht in ``offen`` ein
    Slash-Befehl ist. Wenn ja, beantwortet ``behandle`` sie direkt und liefert
    ``True`` -- kein Kontextaufbau, kein Gespraechsaufruf, ein Befehl kann
    also nie am Gespraechsmodell scheitern. ``klm`` wird trotzdem
    durchgereicht: ``/szene`` braucht es, gibt den Aufruf aber sofort an einen
    eigenen Thread ab (``szene.starte``) und blockiert diesen Zug nicht.
    Die juengste Nachricht ist massgeblich, nicht
    irgendeine im Sammelfenster: ein Befehl loest laut ``ist_ausloeser`` immer
    einen eigenen Zug aus, mitgesammelte Nachrichten davor sind beilaeufig."""
    letzte_message_id = max(n["message_id"] for n in offen)
    letzte_nachricht = max(offen, key=lambda n: n["message_id"])
    # Haelt fest, ob die Antwort schon in der Gruppe steht -- ein Fehler
    # DANACH (z. B. merke_nachricht schlaegt fehl) darf keine zusaetzliche
    # "Bei mir hakt gerade etwas"-Zeile mehr ausloesen: die Gruppe haette dann
    # die richtige Antwort UND direkt darunter eine verwirrende Fehlermeldung
    # zu genau derselben Antwort gesehen.
    versand_erfolgreich = False
    try:
        if befehle.behandle(
            conn, tg, e, chat_id, letzte_nachricht["text"] or "",
            letzte_nachricht["absender"], klm=klm,
        ):
            # Befehl abgefangen und beantwortet -- kein Kontextaufbau, kein
            # Sprachmodell-Aufruf. Das Wasserzeichen rueckt trotzdem im
            # finally vor, wie bei jedem anderen erfolgreichen Zug.
            return

        with _tippanzeige(tg, chat_id):
            # Die Phase geht in die Systemanweisung (worauf der Bot gerade den
            # Fokus legt, prompts/phasen/N.md), nicht in den Koerper -- die
            # datengetriebenen Bloecke bleiben unveraendert (phasen.py).
            phase = phasen.aktuelle(conn, chat_id)
            # Allererster Zug der Gruppe: die Begruessung entsteht aus der
            # ersten Nachricht heraus (kontext.ERSTKONTAKT), nicht als fester
            # Text vorweg (bot.erstkontakt ist seit 04.09. abends nur noch
            # der Rueckfallweg, wenn der Modellaufruf scheitert).
            erstkontakt = not repo.hat_bot_nachricht(conn, chat_id)
            koerper = kontext.baue(conn, chat_id, offen, e, erstkontakt=erstkontakt)
            ergebnis = klm.schema(
                chat_id, kontext.system(e.bot_name, phase), koerper, SCHEMA, "gespraech"
            )
            text = ergebnis["antwort"]
            if hinweis:
                text = f"{text}\n\n{hinweis}"

        message_id = tg.sende(chat_id, text)
        versand_erfolgreich = True
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
            "Sprachmodell-Aufruf im Gespraechszug fehlgeschlagen" if not versand_erfolgreich
            else "Bot-Antwort in 'nachricht' mitzuschreiben ist fehlgeschlagen, obwohl "
                 "die Antwort schon in der Gruppe steht",
        )
        if not versand_erfolgreich:
            # Nur melden, wenn die Gruppe noch KEINE Antwort bekommen hat.
            # Beim allerersten Zug lieber die feste Begruessung als eine
            # Fehlerzeile -- die Gruppe soll nicht mit "hakt gerade" anfangen.
            try:
                if not repo.hat_bot_nachricht(conn, chat_id):
                    from interview_theater import bot as _bot
                    _bot.erstkontakt(conn, tg, e, chat_id)
                else:
                    tg.sende(chat_id, _TEXT_FEHLER)
            except Exception:
                log.exception("Fehlermeldung an die Gruppe fehlgeschlagen, chat_id=%s", chat_id)
    finally:
        repo.setze_beantwortet_bis(conn, chat_id, letzte_message_id)


def bearbeite(conn, tg, klm, e, chat_id: int, hinweis: str | None = None) -> None:
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
    nachgezuegelte Nachricht -- keine Rekursion, kein verlorener Beitrag.

    ``hinweis`` (Aufgabe 5) geht -- falls gesetzt -- ausschliesslich in den
    ERSTEN Antwortversuch dieses Aufrufs; ein etwaiger zweiter Sammelzug
    innerhalb derselben ``bearbeite()``-Ausfuehrung (Nachzuegler waehrend des
    ersten Versands) bekommt ihn nicht noch einmal angehaengt."""
    while True:
        sperre = _sperre_fuer(chat_id)
        if not sperre.acquire(blocking=False):
            return  # laeuft schon fuer diese Gruppe; der laufende Zug sammelt weiter
        try:
            offen = repo.unbeantwortete(conn, chat_id)
            if not offen:
                return
            antworte(conn, tg, klm, e, chat_id, offen, hinweis=hinweis)
            hinweis = None
        finally:
            sperre.release()
