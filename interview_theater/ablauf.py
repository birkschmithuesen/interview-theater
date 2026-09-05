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

Dazwischen liegt seit dem 05.09.2026 die **Echo-Sperre** (``ist_echo``,
``_ohne_echo``): eine Antwort, die nichts als eine der Nachrichten ist, auf
die sie antwortet, wird verworfen und **einmal** neu geholt. Gemessener Fall
vom 04.09. (Nachricht 55/56): der Bot schickte Birks Nachricht wortgleich
zurueck, mit "Birk:" davor. Formal eine Antwort, faktisch keine -- und fuer
die Gruppe sieht der Bot damit kaputt aus.


Es gibt bewusst KEINE Rueckfrage-Sequenz mehr (SPEC § 1.4, ersatzlos
gestrichen) -- inzwischen loest ohnehin jede Nachricht einen Zug aus, eine
gesonderte Rueckfrage-Logik waere ueberfluessig.
"""

import logging
import re
import threading
from contextlib import contextmanager

from interview_theater import befehle, knoepfe, kontext, phasen, repo, vorschlag
from interview_theater.llm import LLMFehler

log = logging.getLogger(__name__)

#: Waehrend ein Zug laeuft, alle TIPP_INTERVALL Sekunden ein erneutes
#: sendChatAction("typing"); nach HINWEIS_NACH Sekunden zusaetzlich eine
#: kurze Zeile (SPEC § 1.3). Die meiste Ungeduld entsteht daraus, dass gar
#: nichts passiert.
TIPP_INTERVALL = 4.0
HINWEIS_NACH = 10.0

_TEXT_HINWEIS = "Einen Moment, ich denke nach."
_TEXT_FEHLER = "Bei mir hakt gerade etwas - fragt nochmal."

#: Zeichen, an denen eine Antwort als Denkspur statt als Antwort erkannt wird
#: (gemessen 05.09. 04:10, Simulation --set birk, Zug S11: Kimi lieferte im
#: Feld "antwort" 90 Zeilen Selbstgespraech -- "Die Gruppe will von der Phase
#: 2 ... Ich soll: ... Perfekt. Das ist ein Angebot" -- und die Gruppe las das
#: im Chat). reasoning_effort war "none"; das Modell hat trotzdem laut gedacht,
#: nur eben IM JSON. Die Marker sind Formulierungen, die nur in einer Denkspur
#: vorkommen, nie in einer Nachricht an eine Gruppe.
_DENKSPUR_MARKER = (
    "ich soll:", "ich soll ", "die gruppe will", "was ist im material",
    "moegliche kernthemen:", "mögliche kernthemen:", "ich schlage ein ",
    "perfekt. das ist", "die regel sagt", "der erkenner setzt",
    "keine markdown", "unter 500 zeichen", "als angebot formulieren",
)
#: Diese Marker sind allein schon Beweis -- so redet niemand mit einer Gruppe.
_DENKSPUR_EINDEUTIG = ("ich soll:", "was ist im material", "der erkenner setzt",
                       "keine markdown", "unter 500 zeichen")


def ist_denkspur(text: str) -> bool:
    """True, wenn ein Antworttext nach Selbstgespraech aussieht: zwei oder
    mehr Marker, oder ein eindeutiger Marker irgendwo. Ein einzelner
    weicher Marker reicht nicht -- "die Gruppe will" kann in einer echten
    Antwort vorkommen."""
    t = text.lower()
    if any(m in t for m in _DENKSPUR_EINDEUTIG):
        return True
    return len([m for m in _DENKSPUR_MARKER if m in t]) >= 2


def _denkspur_kern(text: str) -> str | None:
    """Versucht, aus einer Denkspur den eigentlichen Antwortabsatz zu
    retten: der letzte Absatz ohne Marker, der wie eine Nachricht an die
    Gruppe beginnt und 40-700 Zeichen lang ist. Sonst None."""
    absaetze = [a.strip() for a in text.split("\n\n") if a.strip()]
    for a in reversed(absaetze):
        al = a.lower()
        if any(m in al for m in _DENKSPUR_MARKER):
            continue
        erstes = a.split()[0].rstrip(",.:") if a.split() else ""
        if erstes in ("Ihr", "Euer", "Eure", "Ein", "Eine", "Das", "Die", "Der", "Was", "Wie") or a.startswith('"'):
            if 40 <= len(a) <= 700:
                return a
    return None


def _ohne_denkspur(conn, klm, e, chat_id, system, koerper, text: str) -> str:
    """Faengt eine Antwort ab, die das Selbstgespraech des Modells ist statt
    die Nachricht an die Gruppe. Erst Kernabsatz retten, sonst ein zweiter
    Aufruf mit Ermahnung; beides als Vorfall vermerkt. Ist auch der zweite
    Anlauf Denkspur, geht er trotzdem raus (kein Endlos), als
    ``denkspur_wiederholt`` vermerkt."""
    if not ist_denkspur(text):
        return text
    kern = _denkspur_kern(text)
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None), "denkspur_verworfen",
        f"Antwort war Selbstgespraech ({len(text)} Zeichen); "
        + ("Kernabsatz gerettet" if kern else "kein Kern, zweiter Anlauf"),
    )
    if kern:
        return kern
    zweite = klm.schema(
        chat_id, system,
        f"{koerper}\n\nDeine letzte Antwort war dein Selbstgespraech, nicht die "
        "Nachricht an die Gruppe. Schreib NUR die Nachricht: was du der Gruppe "
        "sagst, in ihren Worten, unter 500 Zeichen.",
        SCHEMA, "gespraech",
    )["antwort"]
    if ist_denkspur(zweite):
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "denkspur_wiederholt",
            "auch der zweite Anlauf war Selbstgespraech, gesendet",
        )
    return zweite

#: Die Zeile, die dem zweiten Anlauf an den Nutzertext gehaengt wird, wenn der
#: erste ein Echo war (Live-Befund 04.09.2026, Nachricht 55/56: der Bot
#: schickte Birks Nachricht 1:1 zurueck, mit "Birk:" davor, und sonst nichts).
#: Sie sagt nicht nur, was falsch war, sondern was stattdessen kommen soll --
#: ein blosses "nicht zitieren" laesst offen, was der Bot dann tun soll.
_TEXT_ECHO_ERMAHNUNG = (
    "Deine letzte Antwort war ein Zitat der Gruppe. Zitiere nicht - antworte "
    "mit einem eigenen Impuls: eine Einschaetzung, ein Vorschlag oder eine "
    "Rueckfrage."
)

#: Ab welchem Anteil einer Ausloeser-Nachricht, den die Antwort woertlich
#: enthaelt, sie als Echo gilt. 80 % lassen eine Antwort durch, die einen
#: halben Satz aufgreift ("das mit der Kueche finde ich stark, weil ...") und
#: fangen die, die nichts Eigenes hinzufuegt.
ECHO_ANTEIL = 0.8

#: Kuerzere Ausloeser werden gar nicht erst geprueft. Ein Satz aus drei
#: Woertern ("machen wir so") steht mit einiger Wahrscheinlichkeit auch in
#: einer voellig eigenstaendigen Antwort -- und ihn zurueckzuspiegeln kostet
#: die Gruppe nichts, weil sie ihn ohnehin gerade gelesen hat.
ECHO_MINDEST_WOERTER = 5

#: Ein vorangestelltes "Birk:" -- genau die Form, in der der Live-Fall
#: auftrat. Bis zu 30 Zeichen ohne Leerzeichen vor dem Doppelpunkt, damit die
#: Regel einen Vornamen trifft und nicht einen Satz mit Doppelpunkt darin.
_NAMENSANREDE = re.compile(r"^[^\s:]{1,30}:\s*")


def _normalisiere_echo(text: str | None) -> str:
    """Kleinschreibung, Whitespace-Folgen zu einem Leerzeichen, ein fuehrendes
    "Name:" weg. Bewusst schlicht: hier wird kein Zitat geprueft (dafuer gibt
    es ``interview_theater.zitat``), sondern erkannt, ob zwei Texte dasselbe
    sagen."""
    ohne_anrede = _NAMENSANREDE.sub("", (text or "").strip(), count=1)
    return " ".join(ohne_anrede.lower().split())


def ist_echo(antwort: str | None, ausloeser: list) -> bool:
    """Ist diese Antwort nichts als eine der Nachrichten, auf die sie
    antwortet?

    Der Live-Fall (04.09.2026): der Bot schickte Birks Nachricht wortgleich
    zurueck, mit "Birk:" davor. Formal eine Antwort, faktisch keine -- und
    fuer die Gruppe sieht es aus, als sei der Bot kaputt.

    Geprueft wird gegen alle Nachrichten der Gruppe im Sammelfenster, nicht
    nur gegen die juengste: gesammelt wird alles seit dem Wasserzeichen
    (``bearbeite``), und das Modell kann jede davon zurueckspiegeln.
    Bot-Nachrichten zaehlen nicht -- seine eigene vorige Antwort aufzugreifen
    ist kein Echo, sondern ein Gespraech.

    'Enthaelt zu ueber ECHO_ANTEIL' heisst hier: die ersten 80 % der
    Ausloeser-Nachricht stehen woertlich in der Antwort. Ein grobes Mass, mit
    Absicht -- die Alternative waere ein Aehnlichkeitsmass, das in einem Pfad
    laeuft, in dem die Gruppe wartet, und das niemand mehr begruenden koennte,
    wenn es einmal danebengreift."""
    gesagt = _normalisiere_echo(antwort)
    if not gesagt:
        return False
    for nachricht in ausloeser:
        if nachricht["ist_bot"]:
            continue
        original = _normalisiere_echo(nachricht["text"])
        if len(original.split()) < ECHO_MINDEST_WOERTER:
            continue
        if gesagt == original:
            return True
        anfang = original[: int(len(original) * ECHO_ANTEIL)]
        if anfang and anfang in gesagt:
            return True
    return False

#: Ab welchem Anteil der Wortmenge einer Antwort, der schon in der VORIGEN
#: Bot-Nachricht stand, sie als Wiederholung verworfen wird (06.09.2026, Birk
#: nach der Testgruppe: "Insgesamt viel zu viel Wiederholung").
#:
#: 0,6 ist an der Testgruppe gemessen: der Filter haette dort 4 von 59
#: Bot-Nachrichten gefangen -- die beiden wortgleich verdoppelten
#: Notiert-Bloecke (21:50/21:52), die doppelte "Bin wieder da"-Zeile und eine
#: verdoppelte Interview-Meldung. Keine echte Antwort waere dabei
#: verlorengegangen. Tiefer waere gefaehrlich: eine Antwort, die einen
#: Vorschlag praezisiert, teilt zwangslaeufig die halbe Wortmenge mit ihm.
WIEDERHOLUNG_ANTEIL = 0.6

#: Kuerzere Antworten werden nicht geprueft. "Gut, ich hoere zu." teilt seine
#: paar Woerter leicht mit irgendetwas -- und eine kurze Zeile kostet die
#: Gruppe nichts, auch wenn sie sich aehnelt.
WIEDERHOLUNG_MINDEST_WOERTER = 12


def _wortmenge(text: str | None) -> set[str]:
    """Die inhaltstragenden Woerter eines Textes -- kleingeschrieben, ab vier
    Zeichen. Dasselbe grobe Mass wie in der Analyse
    (``docs/analyse-interaktion-testgruppe-2026-09-05.md``), damit die
    Schwelle hier und die gemessene Zahl dort dieselbe Groesse meinen."""
    return {w for w in re.findall(r"\w+", (text or "").lower()) if len(w) > 3}


def ist_wiederholung(antwort: str | None, vorige: str | None,
                     anteil: float = WIEDERHOLUNG_ANTEIL) -> bool:
    """Steckt diese Antwort zu ``anteil`` schon in der vorigen Bot-Nachricht?

    Der Live-Fall (05.09.2026, Testgruppe 21:50 und 21:52): der Bot schickte
    denselben Notiert-Block der Szenenfolge zweimal wortgleich, und um 16:39
    und 20:52 dieselbe Wiederkehr-Zeile. Fuer die Gruppe sieht das aus wie
    ein Bot, der nicht weiss, was er gerade gesagt hat.

    Gemessen wird die Wortmenge, nicht die Reihenfolge: eine umformulierte
    Wiederholung ist auch eine. Bewusst grob und ohne Modellaufruf -- der
    Filter laeuft im kritischen Pfad, in dem die Gruppe wartet."""
    gesagt = _wortmenge(antwort)
    if len(gesagt) < WIEDERHOLUNG_MINDEST_WOERTER:
        return False
    davor = _wortmenge(vorige)
    if not davor:
        return False
    return len(gesagt & davor) / len(gesagt) > anteil


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


def _ohne_echo(conn, klm, e, chat_id: int, system: str, koerper: str,
               offen: list, antwort: str) -> str:
    """Liefert die Antwort -- oder, wenn sie ein Echo war, die eines zweiten
    Anlaufs mit angehaengter Ermahnung (``_TEXT_ECHO_ERMAHNUNG``).

    **Genau ein zweiter Aufruf**, nie mehr: ist auch der zweite ein Echo, geht
    er trotzdem raus (Vorfall ``echo_wiederholt``). Eine Schleife waere hier
    das Schlimmste von beidem -- die Gruppe wartet, und ein Modell, das
    zweimal zitiert, zitiert auch beim dritten Mal.

    Scheitert der zweite Aufruf, gilt der erste: eine schwache Antwort ist
    besser als 'Bei mir hakt gerade etwas' -- die Gruppe wartet, und der
    Fehler waere hier ein selbstgemachter."""
    if not ist_echo(antwort, offen):
        return antwort
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None), "echo_verworfen",
        "Antwort war ein Zitat der Gruppe, zweiter Anlauf mit Ermahnung",
    )
    try:
        zweite = klm.schema(
            chat_id, system, f"{koerper}\n\n{_TEXT_ECHO_ERMAHNUNG}", SCHEMA, "gespraech"
        )["antwort"]
    except Exception:
        log.exception("Zweiter Anlauf nach Echo fehlgeschlagen, chat_id=%s", chat_id)
        return antwort
    if ist_echo(zweite, offen):
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "echo_wiederholt",
            "Auch der zweite Anlauf war ein Zitat -- trotzdem gesendet",
        )
    return zweite


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

        # Spaete Importe, wie ueberall hier: ``szene`` und ``szenenfolge``
        # greifen ihrerseits auf ``knoepfe`` zu -- ein Modulimport oben waere
        # ein Zyklus.
        from interview_theater import szene, szenenfolge

        # Ein laufender Szenenauftrag ist eine vollstaendige Antwort
        # (05.09.2026, Testgruppe 22:05): waehrend der Szenenlauf seine
        # Systemzeilen schickt ("Start frei", "Ich schreibe die Szene aus",
        # der USA-Hinweis), kommentierte der Gespraechs-Bot sie parallel und
        # stellte Rueckfragen zu laengst Festgelegtem ("wollt ihr die
        # Reihenfolge behalten?"). Der Zug faellt deshalb aus; das
        # Wasserzeichen rueckt im finally trotzdem vor, die Nachrichten
        # stehen also nicht als unbeantwortet herum. Was die Gruppe WIRKLICH
        # gefragt hat, geht damit nicht verloren: der Erkenner-Nachlauf
        # (bot._zug_und_erkenner) laeuft unabhaengig weiter.
        if szene.laeuft(chat_id):
            log.info("Gespraechszug unterdrueckt, Szenenlauf laeuft, chat_id=%s", chat_id)
            return

        # Die Regie-Notiz nach "Passt, aber anders" unter einem Szenentext
        # (05.09.2026, Phase 6): der Bot hat gerade gefragt, was anders werden
        # soll -- diese eine Nachricht ist die Antwort darauf und geht als
        # Auftrag in den Szenenlauf, nicht in den Gespraechszug. Ohne das
        # bekaeme die Gruppe eine freundliche Gespraechsantwort statt einer
        # neuen Fassung, und die Notiz waere verloren.
        nummer = szenenfolge.nimm_regienotiz(chat_id)
        if nummer is not None and (letzte_nachricht["text"] or "").strip():
            szene.starte(
                conn, tg, klm, e, chat_id,
                f"Schreib Szene {nummer} neu. {letzte_nachricht['text'].strip()}",
            )
            return

        # Dieselbe Bauart fuer die frei gesagte Figurenanzahl (05.09.2026
        # abends, "Andere Zahl"): der Bot hat gerade nach einer Zahl gefragt,
        # diese eine Nachricht ist die Antwort darauf. Steht keine Zahl darin,
        # geht die Nachricht ganz normal ins Gespraech -- die Gruppe hat dann
        # etwas anderes gemeint, und ein Bot, der auf einer Zahl beharrt,
        # waere genau der Kaefig, den es hier nicht gibt.
        if knoepfe.nimm_figurenanzahl_erwartung(chat_id):
            anzahl = knoepfe._zahl_aus(letzte_nachricht["text"] or "")
            if anzahl is not None:
                knoepfe.uebernimm_figurenanzahl(conn, tg, klm, e, chat_id, anzahl)
                return
            tg.sende(chat_id, knoepfe._TEXT_FIGURENZAHL_UNKLAR)
            knoepfe.erwarte_figurenanzahl(chat_id)
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
            system = kontext.system(e.bot_name, phase)
            ergebnis = klm.schema(chat_id, system, koerper, SCHEMA, "gespraech")
            # Das Modell liefert normalerweise {"antwort": "..."}, gelegentlich
            # aber einen blanken String (gemessen 05.09.2026 im Testlauf:
            # TypeError 'string indices must be integers' riss den ganzen
            # Gespraechszug mit, die Gruppe bekam gar nichts). Ein Zug darf an
            # der Verpackung nicht scheitern -- der Inhalt ist da.
            if isinstance(ergebnis, str):
                antwort = ergebnis
            elif isinstance(ergebnis, dict):
                antwort = ergebnis.get("antwort") or ""
            else:
                antwort = ""
            if not str(antwort).strip():
                raise LLMFehler(
                    "Sprachmodell lieferte keine verwertbare Antwort "
                    f"(Typ {type(ergebnis).__name__})"
                )
            text = _ohne_denkspur(conn, klm, e, chat_id, system, koerper, antwort)
            text = _ohne_echo(conn, klm, e, chat_id, system, koerper, offen, text)
            if hinweis:
                text = f"{text}\n\n{hinweis}"

        # Wiederholungsfilter (06.09.2026, Birk: "Insgesamt viel zu viel
        # Wiederholung"): steckt die Antwort zu ueber WIEDERHOLUNG_ANTEIL
        # schon in der vorigen Bot-Nachricht, wird sie NICHT verschickt --
        # ersatzlos, nicht durch eine Entschuldigung ersetzt. Ein Bot, der
        # nichts Neues zu sagen hat, schweigt; die Gruppe arbeitet weiter,
        # und die Speicherleiste haengt ohnehin unter der Nachricht, die den
        # Wert wirklich traegt.
        #
        # Kein zweiter Modellaufruf wie beim Echo: das Echo ist ein Fehler
        # des Modells, den ein Anlauf mit Ermahnung heilt -- eine
        # Wiederholung ist eine Antwort, die es einfach nicht braucht.
        vorige = repo.letzte_bot_nachricht_vor(conn, chat_id, letzte_message_id + 1)
        if vorige is not None and ist_wiederholung(text, vorige["text"]):
            log.info("Antwort als Wiederholung verworfen, chat_id=%s", chat_id)
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None), "wiederholung_verworfen",
                "Modellantwort stand zu ueber "
                f"{int(WIEDERHOLUNG_ANTEIL * 100)} % schon in der vorigen Bot-Nachricht",
            )
            versand_erfolgreich = True
            knoepfe.biete_phase_proaktiv(conn, tg, chat_id)
            return

        # Die Speicher-Leiste (05.09.2026): enthaelt die Antwort einen
        # Vorschlagsblock (``vorschlag.py``) fuer das, was gerade fehlt --
        # Begriffe in Phase 1, Fragen in 2, Kernthema/Figuren in 4 --, haengen
        # "So speichern" und "Nochmal anders" darunter. Ohne Block gibt es
        # nur den Text; geraten wird nichts. Die Markerzeilen fallen dabei
        # weg, die Gruppe sieht sie nie.
        #
        # Faellt die Tastatur aus (Telegram-Fehler), geht der Text trotzdem
        # raus: die Antwort ist wichtiger als ihre Knoepfe.
        try:
            message_id, _ = knoepfe.sende_mit_speicherleiste(conn, tg, chat_id, text)
            text = vorschlag.ohne_marker(text) or text
        except Exception:
            log.exception("Speicher-Leiste fehlgeschlagen, chat_id=%s", chat_id)
            text = vorschlag.ohne_marker(text) or text
            message_id = tg.sende(chat_id, text)
        versand_erfolgreich = True
        # Die Antwort des Modells wird als Bot-Nachricht mitgeschrieben, damit
        # sie im Verlaufsfenster des naechsten Zuges steht (kontext.baue liest
        # sie ueber repo.letzte_nachrichten mit) -- sonst wuerde das Modell
        # seine eigenen frueheren Aeusserungen vergessen.
        repo.merke_nachricht(
            conn, chat_id, message_id, e.bot_name, 1, "text", text, repo._jetzt(),
        )
        # Proaktiv zur naechsten Phase (06.09.2026, Birk nach der
        # Testgruppe): steht alles Noetige, sagt der Bot es SOFORT und in
        # einer eigenen, kurzen Nachricht -- nicht als vierter Knopf unter
        # einem langen Text. Gemessen am Testabend: neun angebotene
        # Phasenknoepfe, null Druecke.
        #
        # Der Merkposten ist derselbe wie fuer den Prompt-Hinweis
        # (``phasen.offenes_angebot``), es gibt also EIN Angebot je Stufe --
        # hat ``kontext.baue`` den Hinweis in diesem Zug schon gesetzt, ist
        # hier nichts mehr offen und es bleibt bei der einen Frage im Fluss.
        # Ein Fehlschlag darf die Antwort nicht nachtraeglich zum Fehlerfall
        # machen: sie steht schon in der Gruppe.
        try:
            knoepfe.biete_phase_proaktiv(conn, tg, chat_id)
        except Exception:
            log.exception("Phasenangebot fehlgeschlagen, chat_id=%s", chat_id)
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


# ---------------------------------------------------------------------------
# Auftragszug: ein Gespraechszug, den ein Knopf ausloest
# ---------------------------------------------------------------------------

#: Wie eine Anweisung an den Koerper des Gespraechs-Prompts gehaengt wird.
#: Sie steht am ENDE, hinter der ausloesenden Nachricht -- was zuletzt im
#: Prompt steht, wirkt am staerksten, und dieser Zug hat genau eine Aufgabe.
_AUFTRAG_KOPF = "Deine Aufgabe in genau diesem Zug:"


def auftragszug(conn, tg, klm, e, chat_id: int, anweisung: str) -> None:
    """Ein vollstaendiger Gespraechszug mit einer zusaetzlichen Anweisung --
    ausgeloest von einem Knopf, nicht von einer Nachricht (05.09.2026).

    **Warum es das gibt.** Ein Knopf-Handler ruft kein Sprachmodell
    (AGENTS.md, Zusage 2 in ``knoepfe.py``) -- was ein Modell braucht, geht
    an einen eigenen Thread, wie bei ``/szene``. Die Knopfwege der Phase 4
    und 5 brauchen das an mehreren Stellen: eine gewaehlte Kernthema-Richtung
    soll drei Formulierungen ergeben, "Anzahl aendern" eine neue
    Figurenliste, "Schlag du vor" ueberhaupt einen ersten Vorschlag.

    Der Zug ist ein normaler Gespraechszug: derselbe Kontext, dieselbe
    Systemanweisung, dieselben Sperren gegen Denkspur -- nur ohne
    ausloesende Nachricht und mit ``anweisung`` am Ende des Koerpers. Die
    Antwort geht wie jede andere durch ``knoepfe.sende_mit_speicherleiste``,
    traegt also automatisch die Leiste, die zum Vorschlagsblock passt.

    Fehler bleiben hier: die Gruppe hat einen Knopf gedrueckt und wartet, sie
    bekommt eine kurze Zeile (SPEC § 11.1)."""
    try:
        with _tippanzeige(tg, chat_id):
            phase = phasen.aktuelle(conn, chat_id)
            koerper = kontext.baue(conn, chat_id, [], e)
            koerper = f"{koerper}\n\n{_AUFTRAG_KOPF}\n{anweisung}"
            system = kontext.system(e.bot_name, phase)
            ergebnis = klm.schema(chat_id, system, koerper, SCHEMA, "gespraech")
            if isinstance(ergebnis, str):
                antwort = ergebnis
            elif isinstance(ergebnis, dict):
                antwort = ergebnis.get("antwort") or ""
            else:
                antwort = ""
            if not str(antwort).strip():
                raise LLMFehler("Sprachmodell lieferte keine verwertbare Antwort")
            text = _ohne_denkspur(conn, klm, e, chat_id, system, koerper, antwort)
    except Exception:
        log.exception("Auftragszug fehlgeschlagen, chat_id=%s", chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "auftragszug_fehlgeschlagen", "Knopf-Auftrag am Modell gescheitert",
            )
            tg.sende(chat_id, _TEXT_FEHLER)
        except Exception:
            log.exception("Fehlermeldung zum Auftragszug fehlgeschlagen")
        return

    try:
        message_id, _ = knoepfe.sende_mit_speicherleiste(conn, tg, chat_id, text)
        text = vorschlag.ohne_marker(text) or text
    except Exception:
        log.exception("Leiste am Auftragszug fehlgeschlagen, chat_id=%s", chat_id)
        text = vorschlag.ohne_marker(text) or text
        message_id = tg.sende(chat_id, text)
    try:
        repo.merke_nachricht(
            conn, chat_id, message_id, e.bot_name, 1, "text", text, repo._jetzt(),
        )
    except Exception:
        log.exception("Auftragsantwort nicht mitgeschrieben, chat_id=%s", chat_id)


def starte_auftrag(conn, tg, klm, e, chat_id: int, anweisung: str):
    """Gibt einen ``auftragszug`` an einen eigenen Thread ab und kehrt sofort
    zurueck -- dasselbe Muster wie ``szene.starte`` und
    ``sprachprofil.starte``. Liefert den Thread (fuer Tests) oder None."""
    if klm is None or not (anweisung or "").strip():
        log.error("Auftragszug ohne Modell oder Anweisung, chat_id=%s", chat_id)
        return None
    thread = threading.Thread(
        target=auftragszug, args=(conn, tg, klm, e, chat_id, anweisung), daemon=True,
    )
    thread.start()
    return thread
