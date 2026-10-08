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

from interview_theater import (
    befehle, formberater, knoepfe, kontext, kosten, modellwahl, phasen, repo,
    strom, vorschlag,
)
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
    "unter 500 zeichen", "als angebot formulieren",
    # 06.09.2026 11:55 (Testgruppe): Kimi schrieb sich SELBST eine Anweisung
    # in die Antwort -- "Du sollst die Szene schreiben, nicht Birk. ... Dein
    # Zug ist leer oder ein Satz Zuspruch. Keine Frage, keine Wiederholung,
    # keine Erklaerung." -- der Wortlaut der Systemanweisung, an die Gruppe
    # gesendet. Ein Bot spricht die Gruppe nie mit "du sollst" ueber sich
    # selbst an und nennt nie "dein Zug"/"Systemzeile"/"System-Ankuendigung".
    "du sollst ", "dein zug ist", "systemzeile", "system-ankuendigung",
    "system-ankündigung", "die systemanweisung", "satz zuspruch",
    # Abnahme P3-4, Befund A1 (06.10.2026, sim.db nachricht.message_id=17):
    # Kimi schrieb "Der Benutzer fragt ... Ich sollte kurz sein ... Laut den
    # Instruktionen ... Die Instruktionen sagen ..." -- durchweg Formulierungen,
    # in denen das Modell sich selbst als Ausfuehrendes einer Anweisung
    # beschreibt bzw. eine Systemanweisung zitiert. "ich sollte " ist weich
    # (wie "ich soll ") -- allein zu generisch, erst im Verbund mit einem
    # zweiten Treffer; die anderen drei sind so eindeutig wie "die
    # systemanweisung": kein Bot nennt die Gruppe "der Benutzer" oder zitiert
    # "die Instruktionen" ueber sich selbst.
    "ich sollte ", "der benutzer fragt", "laut den instruktionen",
    "die instruktionen sagen",
)
#: Diese Marker sind allein schon Beweis -- so redet niemand mit einer Gruppe.
#: "keine markdown" stand hier bis Karte t_cc147548 (07.10.2026): die alte
#: Systemanweisung verbot Markdown, und ihr woertliches Zitat war ein
#: Denkspur-Beweis. Seit die Regel erlaubt, was sie vorher verbot, waere der
#: Marker ein False Positive, sobald das Modell legitim ueber Formatierung
#: spricht -- ersatzlos entfernt, nicht durch die neue Regel ersetzt (die hat
#: keinen eindeutigen Wortlaut, den niemand sonst verwenden wuerde).
_DENKSPUR_EINDEUTIG = ("ich soll:", "was ist im material", "der erkenner setzt",
                       "unter 500 zeichen",
                       "dein zug ist", "systemzeile", "system-ankuendigung",
                       "system-ankündigung", "die systemanweisung",
                       "der benutzer fragt", "laut den instruktionen",
                       "die instruktionen sagen")

#: Dieselben Marker auf Englisch (Karte A1, K5) -- ein Modell denkt auch mal
#: in der anderen Sprache laut. Gelesen wird die Vereinigung, fuer beide
#: Profile. Abweichung vom Plan: "you should " fehlt -- anders als "du
#: sollst" ist es die normale englische Ratschlagsform an eine Gruppe
#: ("you should ask her about ..."), zusammen mit einem zweiten weichen
#: Marker waere eine echte Antwort als Denkspur verworfen worden.
#: Nachbesserung (Review Commit fbc47e9, Befund 1): vier weitere Marker
#: waren so allgemein formuliert, dass sie normale Antworten trafen --
#: gemessen: "Perfect. That is a strong ending. I suggest a title: The
#: Pier." (zwei weiche Treffer aus "perfect. that is" + "i suggest a ");
#: "Good idea. I should mention that scene 2 still has no place. I suggest
#: a park at night." (aus "i should " + "i suggest a "); "Nice. The group
#: wants a sad ending, so I suggest a final image at the station." (aus
#: "the group wants" + "i suggest a "); "Your turn is next: tell me who the
#: third character is." (allein aus dem eindeutigen "your turn is"). "i
#: suggest a " und das weiche "i should " sind deshalb ganz raus -- ein
#: Vorschlag oder ein Ratschlag ist eine normale Antwort an eine Gruppe,
#: kein Selbstgespraech --, "perfect. that is" und "your turn is" wurden auf
#: den vollen Denkspur-Wortlaut verengt, so spezifisch wie ihre deutschen
#: Vorbilder ("perfekt. das ist [ein Angebot]", "dein zug ist [leer]").
#: Englische Entsprechungen von "der benutzer fragt"/"laut den
#: instruktionen"/"die instruktionen sagen" (Abnahme P3-4, Befund A1,
#: 06.10.2026) -- die DE-Liste bekam sie damals, die EN-Liste nicht. Live-
#: Fund 07.10.2026 (Testgruppe chat_id=7000000000099, web_post.id=1694):
#: Kimi schrieb "Member 1 asks ..." und "the instructions also say ..." ins
#: "antwort"-Feld, beides ging an keinem EN-Marker haengen. "under 500
#: chars" ist die abgekuerzte Form von "under 500 characters" -- dieselbe
#: Selbstanweisung, nur kuerzer getippt.
_DENKSPUR_MARKER_EN = (
    "i should:", "the group wants", "what is in the material",
    "possible core themes:", "perfect. that is an offer",
    "the rule says", "the recogniser sets",
    "under 500 characters", "under 500 chars", "phrase it as an offer",
    "your turn is empty",
    "system line", "system announcement", "the system instruction",
    "one sentence of encouragement", "the instructions say",
    "the instructions also say", "according to the instructions",
)
#: "no markdown" raus seit Karte t_cc147548 (07.10.2026), wie "keine
#: markdown" oben -- dieselbe Begruendung.
_DENKSPUR_EINDEUTIG_EN = ("i should:", "what is in the material", "the recogniser sets",
                          "under 500 characters", "under 500 chars", "your turn is empty",
                          "system line", "system announcement", "the system instruction",
                          "the instructions say", "the instructions also say",
                          "according to the instructions")

#: "Member 1 asks"/"wants" usw. -- die englische Entsprechung von "der
#: benutzer fragt": ein Bot, der zur Gruppe spricht, beschreibt sie nie in
#: der dritten Person als "Member N", das ist Selbstgespraech ueber die
#: Nachricht statt eine Antwort an sie (direkte Anrede waere "you asked").
#: Live-Fund 07.10.2026 (siehe Kommentar oben).
_DENKSPUR_BENUTZER_EN = re.compile(
    r"\bmember\s+\d+\s+(asks|asked|wants|wanted|said|wrote)\b", re.IGNORECASE
)

#: Womit ein geretteter Antwortabsatz anfangen darf -- deutsch und englisch.
_KERN_ANFAENGE = ("Ihr", "Euer", "Eure", "Ein", "Eine", "Das", "Die", "Der", "Was", "Wie")
_KERN_ANFAENGE_EN = ("You", "Your", "A", "An", "The", "What", "How", "This", "Here")


def ist_denkspur(text: str) -> bool:
    """True, wenn ein Antworttext nach Selbstgespraech aussieht: zwei oder
    mehr Marker, oder ein eindeutiger Marker irgendwo. Ein einzelner
    weicher Marker reicht nicht -- "die Gruppe will" kann in einer echten
    Antwort vorkommen."""
    t = text.lower()
    if any(m in t for m in _DENKSPUR_EINDEUTIG + _DENKSPUR_EINDEUTIG_EN):
        return True
    if _DENKSPUR_BENUTZER_EN.search(text):
        return True
    return len([m for m in _DENKSPUR_MARKER + _DENKSPUR_MARKER_EN if m in t]) >= 2


def _denkspur_kern(text: str) -> str | None:
    """Versucht, aus einer Denkspur den eigentlichen Antwortabsatz zu
    retten: der letzte Absatz ohne Marker, der wie eine Nachricht an die
    Gruppe beginnt und 40-700 Zeichen lang ist. Sonst None.

    Nachbesserung (Review Commit fbc47e9, Befund 2): welche Anfaenge als
    "das klingt nach einer Nachricht an die Gruppe" gelten, war bisher immer
    die Vereinigung aus Deutsch und Englisch -- eine kleine Verhaltensaenderung
    auch fuer Dortmund, das nie englisch antwortet. Jetzt gilt je aktivem
    Profil genau eine Liste (``sprache.je_sprache``), fuer ``code() == "de"``
    also wortgleich wie vor der Karte A1."""
    anfaenge = sprache.je_sprache({"de": _KERN_ANFAENGE, "en": _KERN_ANFAENGE_EN})
    absaetze = [a.strip() for a in text.split("\n\n") if a.strip()]
    for a in reversed(absaetze):
        al = a.lower()
        if any(m in al for m in _DENKSPUR_MARKER + _DENKSPUR_MARKER_EN):
            continue
        erstes = a.split()[0].rstrip(",.:") if a.split() else ""
        if erstes in anfaenge or a.startswith('"'):
            if 40 <= len(a) <= 700:
                return a
    return None


def _ohne_denkspur(conn, klm, e, chat_id, system, koerper, text: str,
                   bei_teil=None, ueber_claude: bool = False) -> str:
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
    # Der zweite Anlauf ersetzt den ersten -- der Strom beginnt NEU, sonst
    # klebte die verworfene Antwort sichtbar davor (Karte W, Entscheidung D).
    if bei_teil is not None:
        neu = getattr(bei_teil, "neu", None)
        if callable(neu):
            neu()
    zweite = modellwahl.aufruf_schema(
        conn, klm, e, chat_id, system,
        f"{koerper}\n\n{T._TEXT_DENKSPUR_ERMAHNUNG}",
        SCHEMA, "gespraech", ueber_claude=ueber_claude, bei_teil=bei_teil,
        teil_feld="antwort",
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
#: Dasselbe fuer den zweiten Anlauf nach einer Denkspur (``_ohne_denkspur``).
_TEXT_DENKSPUR_ERMAHNUNG = (
    "Deine letzte Antwort war dein Selbstgespraech, nicht die "
    "Nachricht an die Gruppe. Schreib NUR die Nachricht: was du der Gruppe "
    "sagst, in ihren Worten, unter 500 Zeichen."
)

_TEXT_ECHO_ERMAHNUNG = (
    "Deine letzte Antwort war ein Zitat der Gruppe. Zitiere nicht - antworte "
    "mit einem eigenen Impuls: eine Einschaetzung, ein Vorschlag oder eine "
    "Rueckfrage."
)

#: Die Ermahnung fuer den zweiten Anlauf nach einer Ankuendigung ohne Inhalt
#: (Padua-Befund 02.10.2026, Nachricht 20: "Here they are, numbered:" und dann
#: nichts -- das Modell beendete seinen Zug auf der Ankuendigung, die Liste
#: kam erst drei Nachrichten spaeter). Wie bei Denkspur/Echo sagt sie nicht
#: nur, was falsch war, sondern was stattdessen zu tun ist.
_TEXT_ANKUENDIGUNG_ERMAHNUNG = (
    "Deine letzte Antwort hat etwas angekuendigt, aber nicht geliefert -- sie "
    "endete auf einem Doppelpunkt ohne das Versprochene danach. Schreib die "
    "Nachricht neu und liefere den Inhalt JETZT, in dieser einen Nachricht."
)

#: Phase 4 (Karte t_b19d37ac, Birk 06.10.2026): "Keine Szenen ausformulieren
#: in Phase 4. Nur Rahmen setzen." -- die Ermahnung fuer den zweiten Anlauf,
#: wenn die Antwort trotzdem eine Szene auslegt oder anbietet, sie zu
#: schreiben (``ist_schreibangebot``).
_TEXT_SCHREIBANGEBOT_ERMAHNUNG = (
    "Deine letzte Antwort hat eine Szene ausgelegt (Form, Ort, Wer, Was "
    "passiert) oder angeboten, eine Szene zu schreiben. In dieser Station "
    "wird nur der Rahmen gesetzt, geschrieben wird erst in der naechsten. "
    "Schreib die Nachricht neu, ohne Szenenformat und ohne Schreibangebot: "
    "steht der Rahmen, eine kurze Zeile, was steht, und die Frage, ob es "
    "weitergehen soll; wollte die Gruppe eine Szene geschrieben haben, sag, "
    "dass das in der naechsten Station kommt."
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

#: Eine "vorige" Bot-Nachricht, die laenger ist als jede legitime einzelne
#: Antwort sein kann (Hausregel im Systemprompt: "unter 500 Zeichen"/"under
#: 500 characters" -- hier grosszuegig verdreifacht, nicht an der Hausregel
#: selbst gemessen), ist selbst ein Fehlerfall (z. B. eine durchgerutschte
#: Denkspur) und kein Massstab: jede inhaltlich verwandte, EHRLICHE neue
#: Antwort teilt zwangslaeufig einen grossen Teil ihrer Wortmenge mit einem
#: so langen Text ueber dasselbe Thema. Live-Fund 07.10.2026, Addendum Robo
#: 14:41 (Testgruppe chat_id=7000000000099): nachdem die 6107 Zeichen lange
#: Denkspur aus web_post.id=1694 als Bot-Nachricht gespeichert war, verwarf
#: der Wiederholungsfilter DREI weitere Anlaeufe in Folge (12:23, 12:34,
#: 12:51 UTC) -- die Gruppe sah nur noch "One moment, I'm thinking.", ohne
#: jede weitere Antwort.
_VORIGE_LAENGE_MAX_FUER_WIEDERHOLUNG = 1500


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


#: Nachrichten, die einen Auftrag ausloesen und deshalb KEINE
#: Gespraechsantwort bekommen (06.09.2026, Birk, Testgruppe 00:30):
#:
#:   00:30:28  Birk:  "neu schreiben"
#:   00:30:31  Bot:   "Birk, klar -- Szene 1 neu. Eine Frage dazu: Soll der
#:                     Typ wirklich kommen ...?"
#:   00:30:32  Bot:   [USA-Hinweis]  "Ich schreibe die Szene aus"
#:
#: Der erste Teil muss weg. Loest eine Nachricht einen Auftrag aus, spricht
#: der Auftrag selbst -- der Gespraechs-Bot sagt dazu nichts, keine
#: Bestaetigung, keine Rueckfrage, kein "klar". In der Testgruppe stand eine
#: solche Doppelung **14 Mal** im Chat.
#:
#: Warum deterministisch und nicht ueber den Erkenner: der Erkenner laeuft
#: NACH dem Gespraechszug (``bot._zug_und_erkenner``, aus gutem Grund -- er
#: soll die Bot-Antwort mitlesen). Zum Zeitpunkt des Zuges ist seine Antwort
#: also noch nicht da. Diese Liste faengt die Formen, die im Testabend
#: wirklich vorkamen; alles andere faengt weiterhin ``szene.laeuft`` eine
#: Sekunde spaeter. Die Liste ist absichtlich eng: eine falsch
#: unterdrueckte Antwort ist teurer als eine ueberfluessige.
_AUFTRAGSFORMEN = (
    r"neu\s*schreiben",
    r"(schreib|mach)\s*(mir\s*)?(die\s*)?szene\b",
    r"^\s*(nochmal|noch mal)\s*(neu)?\s*$",
    r"^\s*weiter\s*schreiben\s*$",
    r"^\s*ausschreiben\s*$",
    r"interview\s*starten",
    r"^\s*aufnahme\s*(starten|beenden)\s*$",
    # **Interview starten/beenden, gesprochen wie getippt** (06.09.2026,
    # Birk 10:45): "wir wollen jetzt ein interview machen", "interview
    # anfangen", "interview los". Der Erkenner erkennt es eine Sekunde
    # spaeter und legt die Systemzeile mit dem Knopf hin -- der
    # Gespraechs-Bot erklaerte bis dahin parallel die Bedienung ("tippt
    # unten auf ..."), und der Knopf, auf den er verwies, war noch gar
    # nicht da.
    r"interview\b.{0,20}\b(starten|machen|anfangen|los)\b",
    r"\b(starten|machen|anfangen|los)\b.{0,20}\binterview\b",
    r"interview\s*(beenden|fertig|aus)\b",
)

_AUFTRAG = re.compile("|".join(_AUFTRAGSFORMEN), re.IGNORECASE)

#: Dieselben Auftragsformen fuer eine englischsprachige Gruppe (Karte A1,
#: Aufgabe 22). Gewaehlt wird je Sprache des Profils, nicht vereinigt: was
#: die Gruppe tippt, ist in ihrer Sprache -- die deutsche Liste bleibt
#: dadurch fuer Dortmund zeichengleich wirksam.
#: Nachbesserung (Review Commit 15d70a8, Befund 2/3, mit dem Interpreter
#: gemessen): das erste Muster war unverankert -- "I would rewrite the
#: ending" traf mitten im Satz --, jetzt am Satzanfang verankert. Das
#: Interview-Muster mit "go" traf harmlose Fragen und Feststellungen
#: ("How did the interview go?", "The interview will go well") -- "go"
#: ist gestrichen, "start"/"begin" bleiben (Faelle wie "let's go" fehlen
#: dadurch bewusst; ein leiser Auftrag ist billiger als ein falscher).
_AUFTRAGSFORMEN_EN = (
    r"^\s*(please\s+)?re-?write\b",
    r"(write|make)\s*(me\s*|us\s*)?(the\s*)?scene\b",
    r"^\s*(again|once more)\s*$",
    r"^\s*(keep|continue)\s*writing\s*$",
    r"^\s*write\s*it\s*out\s*$",
    r"(start|begin)\s*(the\s*|an?\s*)?interview",
    r"^\s*(start|stop|end)\s*(the\s*)?recording\s*$",
    r"interview\b.{0,20}\b(start|begin)\b",
    r"\b(start|begin|let'?s\s+do)\b.{0,20}\binterview\b",
    r"(end|finish|stop)\s*(the\s*)?interview\b|interview\s*(done|finished|over)\b",
)

_AUFTRAG_EN = re.compile("|".join(_AUFTRAGSFORMEN_EN), re.IGNORECASE)

#: Laengere Nachrichten sind keine reinen Auftraege mehr, sondern tragen
#: Inhalt -- "Schreib Szene 1. Stell immer nur eine Frage auf einmal." ist
#: beides, und die Regieanweisung darin darf nicht verlorengehen. 60 Zeichen
#: ist die Grenze, unter der eine Nachricht nichts als der Auftrag ist.
AUFTRAG_HOECHSTLAENGE = 60


#: Die Bitte um den WORTLAUT einer Szene (06.09.2026, Nacht-Simulation
#: Punkt 7): "lies uns Szene 2 vor", "zeig mal den text von szene 3",
#: "szene 1 ansehen".
#:
#: Der gemessene Fall: die Gruppe fragte in Phase 7/8 nach dem Text einer
#: Szene, und der Gespraechs-Bot antwortete INHALTLICH -- obwohl der
#: Volltext gar nicht in seinem Kontext liegt (``kontext.baue`` gibt nur die
#: zuletzt geaenderte Szene). Er hat also zusammengefasst oder erfunden, was
#: er nicht kennt. Der Prompt sagt es jetzt (system.md, phasen/7.md,
#: phasen/8.md); dieser Weg hier braucht das Modell gar nicht erst: die
#: Gruppe bekommt den echten Volltext aus der Datenbank.
#:
#: Zwei Bedingungen, beide muessen zutreffen -- eine Nummer ("szene 2") UND
#: ein Wort, das nach dem Text fragt. Absichtlich eng: "in szene 2 soll er
#: gehen" ist kein Lesewunsch und darf weiter ins Gespraech.
_SZENENTEXT_NUMMER = re.compile(r"szene\s*(?:nr\.?\s*)?(\d{1,3})", re.IGNORECASE)
_SZENENTEXT_WOERTER = re.compile(
    r"zeig|lies|vorles|vorlesen|ansehen|anschauen|\btext\b|wortlaut|"
    r"was steht|zeigen",
    re.IGNORECASE,
)
#: Englische Fassung derselben zwei Bedingungen (Aufgabe 22), je Sprache
#: gewaehlt.
#: Nachbesserung (Review Commit 15d70a8, Befund 1, mit dem Interpreter
#: gemessen): ohne Wortgrenzen traf "read" den Substring in "already" und
#: "show" den in "shower"; "what does" allein loeste bei jeder Frage aus
#: ("what does she want in scene 3"). Jetzt mit Wortgrenzen, "what does"
#: gestrichen -- die Zahl allein reicht ohnehin nicht, es braucht weiter
#: eines der uebrigen Lesewoerter.
_SZENENTEXT_NUMMER_EN = re.compile(r"scene\s*(?:no\.?\s*|number\s*)?(\d{1,3})", re.I)
_SZENENTEXT_WOERTER_EN = re.compile(
    r"\bshow\b|\bread\b|\blook at\b|\btext\b|\bwording\b", re.I
)

#: P57 Lauf 3 A3: Lesewoerter, die KEINE Bitte um den Szenentext sind --
#: Zukunft/Spaeter ("I will read that later"), Verweis auf den Reiter
#: ("read it in the Script tab") und Fragen nach Interviewstellen statt dem
#: Szenentext ("show me the interview passages for scene 2").
_NICHT_LESEWUNSCH_VOR = {
    "de": re.compile(r"(?:werden|werde|wir|ich|spaeter|später)\s+(?:\w+\s+)?$", re.I),
    "en": re.compile(
        r"(?:\bwill|'ll|\bgoing to|\bgonna|\bwould|\bmight|\bmay|\bshall)\s+(?:\w+\s+)?$",
        re.I,
    ),
}
_NICHT_LESEWUNSCH_NACH = {
    "de": re.compile(
        r"^.{0,40}?(?:\bspaeter\b|\bspäter\b|\bnachher\b|\bim\s+(?:reiter|tab)\b|"
        r"\bin\s+(?:dem|der)\s+(?:reiter|tab)\b|\btextbuch[-\s]?(?:reiter|tab)\b)",
        re.I,
    ),
    "en": re.compile(
        r"^.{0,40}?(?:\blater\b|\bafterwards\b|\bin\s+the\s+\w+\s+tab\b|"
        r"\bin\s+the\s+tab\b|\bscript\s+tab\b|\btab\b)",
        re.I,
    ),
}
_NICHT_SZENENTEXT = {
    "de": re.compile(
        r"interview|passage|passagen|zitat|zitate|stelle\b|stellen\b|belegstell",
        re.I,
    ),
    "en": re.compile(r"interview|passage|quote|excerpt|\bcitation", re.I),
}


def szenentext_gewuenscht(text: str | None) -> int | None:
    """Die Szenennummer, deren TEXT die Gruppe sehen will -- oder None.

    Reiner Musterabgleich, kein Modellaufruf (Zusage 2)."""
    roh = (text or "").strip()
    if not roh:
        return None
    nummer = sprache.je_sprache({"de": _SZENENTEXT_NUMMER, "en": _SZENENTEXT_NUMMER_EN})
    woerter = sprache.je_sprache({"de": _SZENENTEXT_WOERTER, "en": _SZENENTEXT_WOERTER_EN})
    nummern = list(nummer.finditer(roh))
    sp = "en" if sprache.je_sprache({"de": False, "en": True}) else "de"
    if _NICHT_SZENENTEXT[sp].search(roh):
        return None
    leseworte = [
        w for w in woerter.finditer(roh)
        if not _NICHT_LESEWUNSCH_VOR[sp].search(roh[max(0, w.start() - 20):w.start()])
        and not _NICHT_LESEWUNSCH_NACH[sp].search(roh[w.end():w.end() + 60])
    ]
    if not nummern or not leseworte:
        return None
    # P57 Lauf 2 A2: nicht die ERSTE Nummer, sondern die, die zum Lesewunsch
    # gehoert -- "Scene 1 is good now. Please show scene 2." will Szene 2.
    # Gemessen wird der Abstand zwischen Lesewort und Nummer; bei Gleichstand
    # gewinnt die Nummer HINTER dem Lesewort ("zeig Szene 2").
    def abstand(n: re.Match) -> tuple[int, int]:
        kuerzester = None
        for w in leseworte:
            if n.start() >= w.end():
                kandidat = (n.start() - w.end(), 0)
            else:
                kandidat = (max(0, w.start() - n.end()), 1)
            if kuerzester is None or kandidat < kuerzester:
                kuerzester = kandidat
        return kuerzester
    return int(min(nummern, key=abstand).group(1))


def ist_auftrag(text: str | None) -> bool:
    """Ist diese Nachricht nichts als ein Auftrag, den ein anderer Weg
    ausfuehrt? Dann schweigt der Gespraechs-Bot (06.09.2026). Die Muster
    kommen aus der Sprache des Profils (Karte A1): eine englische Gruppe
    schreibt 'write the scene'."""
    roh = (text or "").strip()
    if not roh or len(roh) > AUFTRAG_HOECHSTLAENGE:
        return False
    muster = sprache.je_sprache({"de": _AUFTRAG, "en": _AUFTRAG_EN})
    return muster.search(roh) is not None


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
def arbeitet_sichtbar(tg, chat_id: int, text: str | None = None,
                      art: str | None = None, conn=None):
    """Tippanzeige plus wechselnde Arbeitszeile waehrend eines laufenden
    Modellaufrufs (06.09.2026, 10:10/11:15, Birk).

    Der Anlass: nach dem Speichern der Fragen sagte der Bot minutenlang
    nichts, und die Gruppe wusste nicht, ob noch etwas kommt. Die Zeile geht
    **im Handler** raus, nicht im Thread -- sie ist deterministisch, kostet
    keinen Modellaufruf und steht damit VOR der Wartezeit statt danach.

    Seit dem 06.09.2026, 11:15 ist es **eine** Umsetzung fuer alle Auftraege
    (``arbeitszeilen.Lauf``, vorher zusaetzlich ``szene._arbeitet_sichtbar``):
    sofort die erste Zeile, danach alle ``arbeitszeilen.TAKT_S`` eine neue
    (editMessageText), am Ende geloescht. ``art`` waehlt die Liste
    (``arbeitszeilen.ZEILEN``); ``text`` ist der alte Weg mit genau EINER
    festen Zeile und bleibt fuer die Stellen, die einen bestimmten Satz
    zeigen wollen.

    Eine Arbeitsmeldung, die stehen bleibt, liest sich beim naechsten Blick
    wie eine haengende Aufgabe -- deshalb wird immer aufgeraeumt. Schlaegt
    das fehl, bleibt sie stehen: Schmuck darf einen Zug nie mitreissen."""
    from interview_theater import arbeitszeilen

    lauf = None
    arbeitszeile = None
    if art:
        lauf = arbeitszeilen.sichtbar(tg, chat_id, art)
    elif text:
        try:
            arbeitszeile = tg.sende(chat_id, text)
        except Exception:
            log.exception("Arbeitszeile fehlgeschlagen, chat_id=%s", chat_id)
    try:
        if lauf is not None:
            # Der Lauf haelt die Tippanzeige selbst am Leben.
            yield
        else:
            with _tippanzeige(tg, chat_id, conn=conn):
                yield
    finally:
        if lauf is not None:
            lauf.stoppe()
        if arbeitszeile is not None:
            try:
                tg.loesche_nachrichten(chat_id, [arbeitszeile])
            except Exception:
                log.exception("Arbeitszeile nicht geloescht, chat_id=%s", chat_id)


@contextmanager
def _tippanzeige(tg, chat_id: int, stand: dict | None = None, conn=None):
    """Haelt die Tippanzeige waehrend eines laufenden Sprachmodell-Aufrufs am
    Leben (SPEC § 1.3): alle TIPP_INTERVALL Sekunden erneut ``tg.tippt``,
    nach HINWEIS_NACH Sekunden zusaetzlich eine kurze Zeile.

    ``conn`` (Nachtauftrag cc-p67texte, 08.10.2026): nur fuer
    ``_texte_fuer_phase`` -- welche Sprache die Hinweiszeile traegt. Ohne
    ``conn`` (alter Testaufruf) bleibt es bei ``T``.

    ``stand`` (Addendum Robo 14:41, Live-Fund 07.10.2026): ein von aussen
    uebergebenes Dict, in das ``hinweis_gesendet`` geschrieben wird, sobald
    die Hinweiszeile wirklich raus ist -- ``antworte`` liest es danach, um
    zu wissen, ob die Gruppe schon "Einen Moment, ich denke nach" gesehen
    hat, und darf dann nicht mehr ersatzlos schweigen (siehe
    ``_wiederholt_die_vorige``-Aufruf unten). Ohne ``stand`` (der zweite,
    unveraenderte Aufrufer ``arbeitet_sichtbar``) wird ein eigenes Dict
    angelegt, das niemand ausliest -- Verhalten dort zeichengleich (E1).

    Laeuft in einem Daemon-Thread, der beim Verlassen des with-Blocks sauber
    beendet wird: ``stop.set()`` laesst das laufende ``stop.wait()`` sofort
    zurueckkehren, ``join()`` wartet, bis der Thread das auch wirklich
    mitbekommen hat. Ein Fehlschlag der Tippanzeige selbst (Telegram down,
    was auch immer) darf den eigentlichen Zug nie stoeren -- deshalb wird
    hier alles abgefangen und nur geloggt."""
    if stand is None:
        stand = {"hinweis_gesendet": False}
    stop = threading.Event()

    def _lauf() -> None:
        vergangen = 0.0
        while not stop.wait(TIPP_INTERVALL):
            vergangen += TIPP_INTERVALL
            try:
                tg.tippt(chat_id)
            except Exception:
                log.exception("Tippanzeige fehlgeschlagen, chat_id=%s", chat_id)
            if not stand["hinweis_gesendet"] and vergangen >= HINWEIS_NACH:
                stand["hinweis_gesendet"] = True
                try:
                    tg.sende(chat_id, _texte_fuer_phase(conn, chat_id)._TEXT_HINWEIS)
                except Exception:
                    log.exception("Hinweis-Zeile fehlgeschlagen, chat_id=%s", chat_id)

    thread = threading.Thread(target=_lauf, daemon=True)
    thread.start()
    try:
        yield stand
    finally:
        stop.set()
        thread.join(timeout=TIPP_INTERVALL + 1.0)


#: Systemzeilen, die **nur** der Szenenlauf schreibt (06.09.2026, Birk
#: 12:25). Der Gespraechs-Bot hat sie im Verlauf gelesen und sie live
#: nachgesprochen -- "Start frei", "Ich schreibe die Szene aus", die
#: US-Frage. Fuer die Gruppe sah das wie ein laufender Auftrag aus, und es
#: lief keiner: die Nachricht war erfunden.
_SYSTEMZEILEN = (
    r"start\s*frei",
    # "ich schreibe die Szene aus", "ich schreibe eure Szene jetzt aus" --
    # zwischen Szene und "aus" darf stehen, was das Modell dazwischenschiebt
    # (gemessen live: "jetzt", "gleich", "gerade").
    r"schreibe\s+(die|eure|euch\s+die)\s+szene\b[^.\n]{0,30}\baus\b",
    r"us[- ]?server",
    r"us[- ]?modell.*\?",
    r"\bschweiz\b.*\bus\b|\bus\b.*\bschweiz\b",
)
_SYSTEMZEILE = re.compile("|".join(_SYSTEMZEILEN), re.IGNORECASE)

#: Dieselben Zeilen auf Englisch (Karte A1, Aufgabe 24) -- die Wendungen,
#: die ``sprachen/en/prompts/system.md`` unter "What you do NOT say"
#: verbietet ("Starting now", "I'm writing out the scene", US-Server,
#: US-Modell, Switzerland), angepasst an ``szene._TEXT_ANGEKUENDIGT`` in
#: ``sprachen/en/texte.toml``. Enger als das Deutsche, weil "us" im
#: Englischen ein Pronomen ist: US steht nur **grossgeschrieben**
#: (``(?-i:...)``), sonst traefe "Tell us ... Switzerland". "Starting now"
#: gilt nur am Satzanfang -- "we could try starting now" ist ein Vorschlag.
_SYSTEMZEILEN_EN = (
    r"(?:^|[.!?]\s+)starting\s+now\b",
    r"\bwriting\s+out\s+(?:the|your)\s+scene\b",
    r"\bwriting\s+(?:the|your)\s+scene\s+(?:now|out)\b",
    r"\b(?-i:US)[- ]?servers?\b",
    r"\b(?-i:US)[- ]?model\b.*\?",
    r"\bswitzerland\b.*\b(?-i:USA?)\b|\b(?-i:USA?)\b.*\bswitzerland\b",
)
_SYSTEMZEILE_EN = re.compile("|".join(_SYSTEMZEILEN_EN), re.IGNORECASE)


def ist_erfundene_systemzeile(text: str | None) -> bool:
    """Sieht diese Gespraechsantwort aus wie eine Systemzeile des
    Szenenlaufs?

    Reiner Musterabgleich, kein Modellaufruf. Der Aufrufer prueft
    zusaetzlich, ob wirklich ein Lauf laeuft -- steht einer, ist die Zeile
    echt und geht durch. Modellausgabe, deshalb beide Sprachen (K5),
    Deutsch zuerst."""
    roh = (text or "").strip()
    return any(muster.search(roh) is not None
               for muster in (_SYSTEMZEILE, _SYSTEMZEILE_EN))


#: Padua Phasen TEIL 2 / Flow-Audit B2: der Gespraechs-Bot schrieb "Noted:"
#: ohne dass etwas geschrieben war. "Noted:" ist der Kopf der
#: Erkenner-Meldung (erkenner._NOTIERT_KOPF, englisch) -- im Gespraechszug
#: ist er immer erfunden.
_NOTIERT_ERFUNDEN_EN = re.compile(r"^\s*noted\b", re.IGNORECASE)


def ist_erfundenes_notiert(text: str | None) -> bool:
    return _NOTIERT_ERFUNDEN_EN.search((text or "")) is not None


#: Abnahme P1-2, Fortsetzung (05.10.2026, echter Browserlauf handy/giulia):
#: eine Antwort kam als "Benutzer hat Chat-Standort (New Zealand) erhalten.
#: Er/Sie spricht vielleicht Englisch mit neuseelaendischem Dialekt. [...]
#: BTW, Du kannst es immer auf 'Waehle eine Sprache' aendern, wenn ich etwas
#: falsch mache." -- eine deutsche, anbieterseitige Standort-/Sprachhinweis-
#: Injektion (Infomaniak/Kimi), die als Gespraechsantwort durchgereicht und
#: als Bot-Nachricht gespeichert wurde. Das Fenster liest sie danach bei
#: jedem weiteren Zug mit und verwirrt die Gruppe ("why does it say New
#: Zealand?"). Nur EIN Vorkommen bisher gemessen -- der Anker ist bewusst
#: eng am genauen Wortlaut, damit er nicht versehentlich eine echte
#: Antwort trifft, die zufaellig "Sprache" oder "Standort" erwaehnt.
_ANBIETER_INJEKTION = re.compile(r"Chat-Standort|W[aä]hle eine Sprache", re.IGNORECASE)


def ist_anbieter_systeminjektion(text: str | None) -> bool:
    return _ANBIETER_INJEKTION.search((text or "")) is not None


#: Angekuendigte Phrasen, die ohne Doppelpunkt enden und trotzdem nichts
#: liefern (Padua-Befund 02.10.2026, Nachricht 22/24: "I see the button list
#: didn't come through. I'll try once more with the block format." --
#: angekuendigt, nie geliefert, zweimal wortgleich wiederholt). Jedes Muster
#: ist an das Ende der Antwort verankert (``$``), damit eine echte Antwort,
#: die zufaellig eine aehnliche Wendung MITTENDRIN benutzt und danach noch
#: etwas sagt, nicht trifft -- nur wenn die Ankuendigung das letzte ist, was
#: dasteht, ist sie ein Holzweg.
_ANKUENDIGUNG_OHNE_DOPPELPUNKT = (
    r"einen moment,?\s*ich (denke nach|schaue nach)\.?\s*$",
    r"ich (schlage|werde|gebe euch|liefere euch)[^.\n]*(gleich|gerade|jetzt)[^.\n]*\.\s*$",
    r"i(?:'| wi)ll try (?:once more|again)[^.\n]*\.\s*$",
    r"i(?:'m| am) (?:putting together|working on)[^.\n]*\.\s*$",
)
_ANKUENDIGUNG_OHNE_DOPPELPUNKT_MUSTER = re.compile(
    "|".join(_ANKUENDIGUNG_OHNE_DOPPELPUNKT), re.IGNORECASE,
)


def ist_ankuendigung_ohne_inhalt(text: str | None) -> bool:
    """Endet diese Antwort auf einer Ankuendigung, ohne den versprochenen
    Inhalt zu liefern?

    Padua-Befund 02.10.2026 (Nachricht 20, Phase 2): nach einem zustimmenden
    "Yes" kam "Great. I'll build one question per term -- five for each, so
    you can mix. Here they are, numbered:" -- und dann nichts. Die Liste kam
    erst drei Nachrichten spaeter, nachdem die Gruppe noch einmal ausdruecklich
    danach gefragt hatte ("Give suggestions"). Das Muster ist allgemein: ein
    Gespraechsmodell kuendigt Inhalt an und beendet seinen Zug auf der
    Ankuendigung, statt ihn im selben Zug zu liefern.

    Zwei Signale, reiner Musterabgleich, kein Modellaufruf:

    1. **Die Antwort endet auf einem Doppelpunkt** (nach Entfernen von
       Leerraum). Das ist die haerteste und allgemeinste Form -- ein
       Vorschlagsblock wie ``VORSCHLAG FRAGENAUSWAHL:`` endet NIE so, weil
       die eigentlichen Zeilen danach folgen; nur eine Ankuendigung ohne
       Fortsetzung tut das.
    2. **Eine bekannte Ankuendigungsfloskel ohne Doppelpunkt** steht ganz am
       Ende der Antwort, als letzter Satz (``_ANKUENDIGUNG_OHNE_DOPPELPUNKT``,
       DE+EN) -- der Live-Fall aus Nachricht 22/24, zweimal wortgleich
       wiederholt.

    Eine sehr kurze Antwort (unter 10 Zeichen) wird nicht geprueft: ein
    blosses ":" oder ein Emoji sind kein Fall dieses Musters."""
    roh = (text or "").strip()
    if len(roh) < 10:
        return False
    if roh.endswith(":"):
        return True
    return _ANKUENDIGUNG_OHNE_DOPPELPUNKT_MUSTER.search(roh) is not None


def _ohne_ankuendigung(conn, klm, e, chat_id: int, system: str, koerper: str,
                       text: str, bei_teil=None,
                       ueber_claude: bool = False) -> str:
    """Liefert die Antwort -- oder, wenn sie eine Ankuendigung ohne Inhalt
    war, die eines zweiten Anlaufs mit angehaengter Ermahnung
    (``_TEXT_ANKUENDIGUNG_ERMAHNUNG``).

    Gleiches Muster wie ``_ohne_echo``/``_ohne_denkspur``: **genau ein**
    zweiter Aufruf, nie mehr -- ist auch der zweite eine Ankuendigung ohne
    Inhalt, geht er trotzdem raus (Vorfall ``ankuendigung_wiederholt``). Ein
    Vorschlagsblock in der Antwort gilt nie als Ankuendigung ohne Inhalt: er
    traegt den Inhalt schon (``vorschlag.enthaelt_block``), auch wenn der
    Fliesstext davor auf einem Doppelpunkt endet (etwa ein Doppelpunkt vor
    einer Aufzaehlung, die als Block kommt statt im Fliesstext)."""
    if vorschlag.enthaelt_block(text) or not ist_ankuendigung_ohne_inhalt(text):
        return text
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None), "ankuendigung_ohne_inhalt",
        f"Antwort endete auf einer Ankuendigung ohne Inhalt ({len(text)} "
        "Zeichen), zweiter Anlauf mit Ermahnung",
    )
    # Der zweite Anlauf ersetzt den ersten -- der Strom beginnt NEU, sonst
    # klebte die verworfene Ankuendigung sichtbar davor (wie bei Echo/Denkspur).
    if bei_teil is not None:
        neu = getattr(bei_teil, "neu", None)
        if callable(neu):
            neu()
    try:
        zweite = modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system,
            f"{koerper}\n\n{T._TEXT_ANKUENDIGUNG_ERMAHNUNG}",
            SCHEMA, "gespraech", ueber_claude=ueber_claude, bei_teil=bei_teil,
            teil_feld="antwort",
        )["antwort"]
    except Exception:
        log.exception(
            "Zweiter Anlauf nach Ankuendigung ohne Inhalt fehlgeschlagen, "
            "chat_id=%s", chat_id,
        )
        # Der erste Anlauf gilt -- dieselbe Begruendung wie in _ohne_echo:
        # eine schwache Antwort ist besser als 'Bei mir hakt gerade etwas'.
        if bei_teil is not None:
            neu = getattr(bei_teil, "neu", None)
            if callable(neu):
                neu()
            try:
                bei_teil(text)
            except Exception:  # noqa: BLE001 -- wie in _ohne_echo
                log.exception(
                    "bei_teil-Nachtrag nach gescheitertem Ankuendigungs-Anlauf "
                    "fehlgeschlagen, chat_id=%s", chat_id,
                )
        return text
    if not vorschlag.enthaelt_block(zweite) and ist_ankuendigung_ohne_inhalt(zweite):
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "ankuendigung_wiederholt",
            "Auch der zweite Anlauf endete auf einer Ankuendigung ohne "
            "Inhalt -- trotzdem gesendet",
        )
    return zweite


#: Das Schreibangebot einer Szene (Live-Fall 06.10.2026, G3, Phase 4:
#: "Shall I write scene 1 now?"), englisch und deutsch.
_SCHREIBANGEBOT_MUSTER = re.compile(
    r"\b(?:shall|should|can|may)\s+i\s+(?:now\s+|go\s+ahead\s+and\s+)?"
    r"(?:write|draft|formulate)(?:\s+out)?\s+(?:up\s+)?(?:the\s+)?(?:first\s+)?"
    r"(?:scene|scenes)\b"
    r"|\bwant\s+me\s+to\s+(?:write|draft)(?:\s+out)?\s+(?:the\s+)?(?:first\s+)?scene"
    r"|\bsoll\s+ich\s+(?:jetzt\s+|nun\s+)?(?:die\s+)?(?:erste\s+)?szene"
    r"(?:\s+\d+)?\s+(?:jetzt\s+)?(?:schreiben|ausformulieren|ausschreiben)",
    re.IGNORECASE,
)

#: Eine Zeile eines Szenenformats ("Form: still open", "**Place:** ...").
_SZENENFORMAT_ZEILE = re.compile(
    r"^\s*(?:[-*•]\s*)?\**(?:form|place|who|what happens|ort|wer|"
    r"was passiert)\**\s*:", re.IGNORECASE | re.MULTILINE,
)


def ist_schreibangebot(text: str | None) -> bool:
    """Legt diese Antwort eine Szene aus oder bietet an, eine zu schreiben?

    Karte t_b19d37ac (Live-Test 06.10.2026, G3): noch in Phase 4 kam "Scene
    1: The Pitch / Form: still open / Place: ... / Who: still open / What
    happens: ... Shall I write scene 1 now?" -- Phase-5-Gebiet. Zwei
    Signale, reiner Musterabgleich: die Frage nach dem Schreiben
    (``_SCHREIBANGEBOT_MUSTER``) oder mindestens drei Zeilen eines
    Szenenformats (Form/Ort/Wer/Was passiert)."""
    roh = text or ""
    if _SCHREIBANGEBOT_MUSTER.search(roh):
        return True
    return len(_SZENENFORMAT_ZEILE.findall(roh)) >= 3


def _ohne_schreibangebot(conn, klm, e, chat_id: int, system: str, koerper: str,
                         text: str, phase: int, bei_teil=None,
                         ueber_claude: bool = False) -> str:
    """Phase 4 mit Prosa-Entwurf in Phase 5 (Padua, ``workshop.
    prosa_entwurf_aktiv``): eine Antwort mit Schreibangebot oder
    Szenenformat bekommt GENAU EINEN zweiten Anlauf mit Ermahnung
    (``_TEXT_SCHREIBANGEBOT_ERMAHNUNG``) -- dasselbe Muster wie
    ``_ohne_ankuendigung``. Ist auch der zweite eins, geht er trotzdem raus
    (Vorfall ``schreibangebot_wiederholt``)."""
    from interview_theater import workshop
    from interview_theater.knoepfe.texte import PHASE_SETTING

    if phase != PHASE_SETTING or not workshop.prosa_entwurf_aktiv():
        return text
    if not ist_schreibangebot(text):
        return text
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None), "schreibangebot_phase_4",
        f"Antwort in Phase 4 legte eine Szene aus oder bot an, sie zu "
        f"schreiben ({len(text)} Zeichen), zweiter Anlauf mit Ermahnung",
    )
    if bei_teil is not None:
        neu = getattr(bei_teil, "neu", None)
        if callable(neu):
            neu()
    try:
        zweite = _antworttext(modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system,
            f"{koerper}\n\n{T._TEXT_SCHREIBANGEBOT_ERMAHNUNG}",
            SCHEMA, "gespraech", ueber_claude=ueber_claude, bei_teil=bei_teil,
            teil_feld="antwort",
        ))
    except Exception:
        log.exception("Zweiter Anlauf nach Schreibangebot fehlgeschlagen, "
                      "chat_id=%s", chat_id)
        zweite = ""
    if not zweite.strip():
        # Der erste Anlauf gilt -- eine schwache Antwort ist besser als
        # keine (wie in _ohne_ankuendigung).
        if bei_teil is not None:
            neu = getattr(bei_teil, "neu", None)
            if callable(neu):
                neu()
            try:
                bei_teil(text)
            except Exception:  # noqa: BLE001 -- wie in _ohne_echo
                log.exception("bei_teil-Nachtrag nach Schreibangebot "
                              "fehlgeschlagen, chat_id=%s", chat_id)
        return text
    if ist_schreibangebot(zweite):
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "schreibangebot_wiederholt",
            "Auch der zweite Anlauf in Phase 4 legte eine Szene aus -- "
            "trotzdem gesendet",
        )
    return zweite


def _ohne_echo(conn, klm, e, chat_id: int, system: str, koerper: str,
               offen: list, antwort: str, bei_teil=None,
               ueber_claude: bool = False) -> str:
    """Liefert die Antwort -- oder, wenn sie ein Echo war, die eines zweiten
    Anlaufs mit angehaengter Ermahnung (``_TEXT_ECHO_ERMAHNUNG``).

    **Genau ein zweiter Aufruf**, nie mehr: ist auch der zweite ein Echo, geht
    er trotzdem raus (Vorfall ``echo_wiederholt``). Eine Schleife waere hier
    das Schlimmste von beidem -- die Gruppe wartet, und ein Modell, das
    zweimal zitiert, zitiert auch beim dritten Mal.

    Scheitert der zweite Aufruf, gilt der erste: eine schwache Antwort ist
    besser als 'Bei mir hakt gerade etwas' -- die Gruppe wartet, und der
    Fehler waere hier ein selbstgemachter.

    Geprueft wird der Text OHNE Vorschlagsbloecke (P2-M9, Prompt-Check
    05.10.2026): in Phase 2 steht die diktierte Frage der Gruppe zwingend
    auch im Block ``VORSCHLAG EIGENE FRAGEN:`` (Format ``Begriff: Frage``)
    -- gegen den unveraenderten Text gemessen, war das ein Fehlalarm bei
    jeder diktierten Frage. Ein echtes Echo im sichtbaren Fliesstext bleibt
    weiter erkennbar, denn ``vorschlag.ohne_bloecke`` laesst ihn stehen."""
    if not ist_echo(vorschlag.ohne_bloecke(antwort), offen):
        return antwort
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None), "echo_verworfen",
        "Antwort war ein Zitat der Gruppe, zweiter Anlauf mit Ermahnung",
    )
    # Der zweite Anlauf ersetzt den ersten -- der Strom beginnt NEU, sonst
    # klebte die verworfene Antwort sichtbar davor (Karte W, Entscheidung D).
    if bei_teil is not None:
        neu = getattr(bei_teil, "neu", None)
        if callable(neu):
            neu()
    try:
        zweite = modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system, f"{koerper}\n\n{T._TEXT_ECHO_ERMAHNUNG}",
            SCHEMA, "gespraech", ueber_claude=ueber_claude, bei_teil=bei_teil,
            teil_feld="antwort",
        )["antwort"]
    except Exception:
        log.exception("Zweiter Anlauf nach Echo fehlgeschlagen, chat_id=%s", chat_id)
        # Der erste Anlauf gilt -- dann muss auch die Stromzeile ihn tragen
        # und nicht den halben Text des gescheiterten zweiten (Fix-Runde 1,
        # Befund 3): verwerfen und neu beginnen, mit genau dem Text, der
        # gleich verschickt wird.
        if bei_teil is not None:
            neu = getattr(bei_teil, "neu", None)
            if callable(neu):
                neu()
            # Derselbe Grundsatz wie in der Streaming-Schleife
            # (``llm._sende_strom``, Fix Runde 1, Punkt 2): ``bei_teil`` ist
            # ein Schreibvorgang (z. B. "database is locked") und darf nicht
            # weiter nach oben reichen -- die erste Antwort steht fest, eine
            # werfende Anzeige darf sie nicht mehr kosten.
            try:
                bei_teil(antwort)
            except Exception:  # noqa: BLE001 -- eine werfende Anzeige darf
                # die schon feststehende erste Antwort nicht kosten.
                log.exception(
                    "bei_teil-Nachtrag nach gescheitertem Echo-Anlauf "
                    "fehlgeschlagen, chat_id=%s", chat_id,
                )
        return antwort
    if ist_echo(vorschlag.ohne_bloecke(zweite), offen):
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
    # Addendum Robo 14:41 (Live-Fund 07.10.2026): haelt fest, ob die Gruppe
    # in diesem Zug schon "Einen Moment, ich denke nach" gesehen hat
    # (_tippanzeige schreibt hinein) -- dann darf ``_wiederholt_die_vorige``
    # unten nicht mehr ersatzlos schweigen, sonst bleibt genau diese Zeile
    # auf Dauer die letzte.
    tippstand = {"hinweis_gesendet": False}
    # Befund H2: der Stand VOR dem Zug -- ob er den Vergleich anstoesst,
    # liest ``_merke_vergleich_im_zug`` im ``finally`` ab.
    try:
        vergleich_vorher = _vergleich_stand(conn, chat_id)
    except Exception:
        log.exception("Vergleichsstand nicht gelesen, chat_id=%s", chat_id)
        vergleich_vorher = None
    try:
        if befehle.behandle(
            conn, tg, e, chat_id, letzte_nachricht["text"] or "",
            letzte_nachricht["absender"], klm=klm,
        ):
            # Befehl abgefangen und beantwortet -- kein Kontextaufbau, kein
            # Sprachmodell-Aufruf. Das Wasserzeichen rueckt trotzdem im
            # finally vor, wie bei jedem anderen erfolgreichen Zug.
            return

        if _zug_faellt_aus(conn, tg, klm, e, chat_id, letzte_nachricht):
            return

        _pruefe_formen(conn, tg, klm, e, chat_id, offen)
        text = _erfrage_antwort(conn, klm, e, chat_id, offen, tg, hinweis,
                                tippstand=tippstand)

        if _erfundene_systemzeile(conn, e, chat_id, text):
            strom.verwirf(tg, chat_id)          # die vorlaeufige Blase verschwindet
            versand_erfolgreich = True
            return

        if _erfundenes_notiert(conn, e, chat_id, text):
            strom.verwirf(tg, chat_id)
            versand_erfolgreich = True
            return

        if _anbieter_systeminjektion(conn, e, chat_id, text):
            strom.verwirf(tg, chat_id)
            versand_erfolgreich = True
            return

        if _wiederholt_die_vorige(conn, e, chat_id, text, letzte_message_id):
            strom.verwirf(tg, chat_id)
            versand_erfolgreich = True
            if tippstand["hinweis_gesendet"]:
                # Addendum Robo 14:41: die Gruppe sieht bereits "Einen
                # Moment, ich denke nach" -- ersatzloses Schweigen wuerde
                # das auf Dauer zur letzten Zeile machen (Live-Fund
                # 07.10.2026, drei Anlaeufe in Folge). Eine kurze ehrliche
                # Zeile schliesst den Zug ab statt die Gruppe warten zu
                # lassen.
                try:
                    tg.sende(chat_id, T._TEXT_FEHLER)
                except Exception:
                    log.exception(
                        "Ersatzzeile nach Wiederholung fehlgeschlagen, chat_id=%s",
                        chat_id,
                    )
            knoepfe.biete_phase_proaktiv(conn, tg, chat_id)
            return

        # Padua Phase 7 (Birk 08.10.2026 ~13:20, erweitert ~14:00): eine
        # vollstaendige Szenenfassung im Chat wird die Script-Fassung --
        # VOR dem Versand geprueft, damit die Gruppe nie den vollen
        # Szenentext sieht, nur die Diff-Nachricht, die
        # ``uebernimm_chatfassung`` selbst schickt (mit Yes/No).
        uebernommen_message_id = _uebernimm_stagescript_vor_dem_senden(
            conn, tg, klm, e, chat_id, text, letzte_nachricht)
        if uebernommen_message_id is not None:
            versand_erfolgreich = True
            strom.schliesse(tg, chat_id, uebernommen_message_id)
            return
        if _szenenfassung_waehrend_neuschreiben(conn, chat_id, text):
            # Live G3 08.10.2026 14:32: der Neuschreiblauf lief schon
            # ("Riscrivo la scena 3"), der Gespraechsbot schickte trotzdem
            # die ganze Szene als zweite, konkurrierende Fassung (dazu auf
            # Englisch). Der Lauf schickt gleich selbst die Aenderung mit
            # Yes/No -- diese Fassung faellt weg.
            log.info("Szenenfassung des Gespraechsbots verworfen (Neuschreiben laeuft), chat_id=%s",
                     chat_id)
            strom.verwirf(tg, chat_id)
            versand_erfolgreich = True
            return

        message_id, text = _sende_mit_leiste(conn, tg, chat_id, text, klm=klm, e=e)
        # Ab hier steht die Antwort in der Gruppe: markiert, BEVOR der Strom
        # schliesst (Fix-Runde Abschluss, Befund 2) -- ``strom.schliesse``
        # schluckt einen werfenden Abschluss zwar selbst schon (``strom.py``),
        # aber ein Fehler dort soll unter keinen Umstaenden mehr als
        # "versand nicht erfolgreich" gelten: die Blase wird in jedem Fall
        # geschlossen, durch genau diese Nachricht ersetzt (Zuordnung ueber
        # ``web_strom.post_id``).
        versand_erfolgreich = True
        strom.schliesse(tg, chat_id, message_id)
        _nach_dem_senden(conn, tg, e, chat_id, message_id, text)
        # Bis 05.10.2026 folgte hier in Phase 1 der Einstiegssatz des
        # Begriffsboards (``begriffsboard.sende_einstieg``). Seit Birks
        # Live-Test erklaert die Begruessung die zwei Handys selbst
        # (``kontext.ERSTKONTAKT_DISKUSSION``) und endet mit "Start
        # listening" -- ein Satz dahinter kaeme doppelt und nach dem Schluss.
    except Exception:
        log.exception("Gespraechszug fehlgeschlagen, chat_id=%s", chat_id)
        strom.verwirf(tg, chat_id)
        _melde_fehler(conn, tg, e, chat_id, versand_erfolgreich)
    finally:
        _merke_vergleich_im_zug(conn, chat_id, vergleich_vorher, letzte_message_id)
        repo.setze_beantwortet_bis(conn, chat_id, letzte_message_id)


def _pruefe_formen(conn, tg, klm, e, chat_id: int, offen: list) -> None:
    """Ausloeser A des Formberaters (Karte t_256ec777): ab Phase 4 ein
    deterministischer Abgleich der neuen Gruppenbeitraege gegen den
    Formen-Katalog, VOR dem Kontextbau -- eine genannte Form steht damit
    schon in diesem Zug im Prompt; der Modellaufruf (nur bei einem neuen
    Treffer) laeuft im eigenen Thread und wirkt ab dem naechsten Zug. Ein
    Fehler hier kostet den Zug nie."""
    try:
        texte = [
            n["text"] or "" for n in offen
            if not ("ist_bot" in n.keys() and n["ist_bot"])
        ]
        formberater.pruefe_zug(conn, tg, klm, e, chat_id, texte)
    except Exception:
        log.exception("Formberater-Abgleich gescheitert, chat_id=%s", chat_id)


def _nach_dem_senden(conn, tg, e, chat_id: int, message_id: int, text: str) -> None:
    """Was nach einer verschickten Antwort noch faellig ist: mitschreiben und
    das Phasenangebot.

    Die Antwort des Modells wird als Bot-Nachricht mitgeschrieben, damit sie im
    Verlaufsfenster des naechsten Zuges steht (``kontext.baue`` liest sie ueber
    ``repo.letzte_nachrichten`` mit) -- sonst wuerde das Modell seine eigenen
    frueheren Aeusserungen vergessen.

    Proaktiv zur naechsten Phase (06.09.2026, Birk nach der Testgruppe): steht
    alles Noetige, sagt der Bot es SOFORT und in einer eigenen, kurzen
    Nachricht -- nicht als vierter Knopf unter einem langen Text. Gemessen am
    Testabend: neun angebotene Phasenknoepfe, null Druecke. Der Merkposten ist
    derselbe wie fuer den Prompt-Hinweis (``phasen.offenes_angebot``), es gibt
    also EIN Angebot je Stufe -- hat ``kontext.baue`` den Hinweis in diesem Zug
    schon gesetzt, ist hier nichts mehr offen und es bleibt bei der einen Frage
    im Fluss. Ein Fehlschlag darf die Antwort nicht nachtraeglich zum
    Fehlerfall machen: sie steht schon in der Gruppe."""
    repo.merke_nachricht(
        conn, chat_id, message_id, e.bot_name, 1, "text", text, repo._jetzt(),
    )
    try:
        knoepfe.biete_phase_proaktiv(conn, tg, chat_id)
    except Exception:
        log.exception("Phasenangebot fehlgeschlagen, chat_id=%s", chat_id)


def _wiederholt_die_vorige(conn, e, chat_id: int, text: str,
                           letzte_message_id: int) -> bool:
    """Der Wiederholungsfilter (06.09.2026, Birk: "Insgesamt viel zu viel
    Wiederholung"): steckt die Antwort zu ueber ``WIEDERHOLUNG_ANTEIL`` schon
    in der vorigen Bot-Nachricht, wird sie NICHT verschickt -- ersatzlos, nicht
    durch eine Entschuldigung ersetzt. Ein Bot, der nichts Neues zu sagen hat,
    schweigt; die Gruppe arbeitet weiter, und die Speicherleiste haengt ohnehin
    unter der Nachricht, die den Wert wirklich traegt.

    Kein zweiter Modellaufruf wie beim Echo: das Echo ist ein Fehler des
    Modells, den ein Anlauf mit Ermahnung heilt -- eine Wiederholung ist eine
    Antwort, die es einfach nicht braucht.

    **Ein Vorschlagsblock ist nie eine sinnlose Wiederholung** (06.09.2026
    12:30, Gruppe 1 live): "Kannst du die zweite Formulierung umaendern" ->
    das Modell lieferte den ueberarbeiteten Vorschlagsblock, der zwangslaeufig
    zu ueber 60 % aus denselben Woertern besteht wie der vorige -- und wurde
    ZWEIMAL verworfen; die Gruppe bekam keine Antwort. Er traegt den neuen
    Wert und geht deshalb immer raus."""
    from interview_theater import vorschlag as _vorschlag

    vorige = repo.letzte_bot_nachricht_vor(conn, chat_id, letzte_message_id + 1)
    if vorige is None or _vorschlag.enthaelt_block(text):
        return False
    if len(vorige["text"] or "") > _VORIGE_LAENGE_MAX_FUER_WIEDERHOLUNG:
        return False
    if not ist_wiederholung(text, vorige["text"]):
        return False
    log.info("Antwort als Wiederholung verworfen, chat_id=%s", chat_id)
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None), "wiederholung_verworfen",
        "Modellantwort stand zu ueber "
        f"{int(WIEDERHOLUNG_ANTEIL * 100)} % schon in der vorigen Bot-Nachricht",
    )
    return True


def _erfundene_systemzeile(conn, e, chat_id: int, text: str) -> bool:
    """**Keine erfundenen Systemzeilen** (06.09.2026, Birk 12:25): sagt der
    Gespraechs-Bot "Start frei", "ich schreibe die Szene aus" oder etwas ueber
    US-Server und Schweiz, OHNE dass ein Szenenlauf laeuft, ist die Zeile
    erfunden -- sie sieht fuer die Gruppe wie ein laufender Auftrag aus, und es
    laeuft keiner. Sie wird ersatzlos verworfen (wie eine Wiederholung), mit
    Vorfall."""
    from interview_theater import szene

    if not ist_erfundene_systemzeile(text) or szene.laeuft(chat_id):
        return False
    log.info("Erfundene Systemzeile verworfen, chat_id=%s", chat_id)
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None),
        "gespraech_systemzeile_erfunden",
        "Antwort klang wie eine Systemzeile des Szenenlaufs, "
        "ohne dass ein Lauf lief",
    )
    return True


def _anbieter_systeminjektion(conn, e, chat_id: int, text: str) -> bool:
    """Eine anbieterseitige Standort-/Sprachhinweis-Injektion, die als
    Gespraechsantwort durchgereicht wurde (Abnahme P1-2, Fortsetzung,
    05.10.2026) -- wird wie eine erfundene Systemzeile ersatzlos verworfen,
    mit Vorfall, statt die Gruppe zu verwirren und das Fenster dauerhaft zu
    verschmutzen."""
    if not ist_anbieter_systeminjektion(text):
        return False
    log.info("Anbieter-Systeminjektion verworfen, chat_id=%s", chat_id)
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None),
        "gespraech_anbieter_injektion",
        "Antwort enthielt eine anbieterseitige Standort-/Sprachhinweis-"
        "Injektion statt einer echten Antwort",
    )
    return True


def _erfundenes_notiert(conn, e, chat_id: int, text: str) -> bool:
    """Ein "Noted: ..." aus dem Gespraechszug (Flow-Audit B2) wird ersatzlos
    verworfen, mit Vorfall -- wie eine erfundene Systemzeile. Nur in Padua
    (``ueberarbeitung.aktiv()``) und nur in den Phasen 6 und 7: dort sagte
    der Bot "Noted" zu einer Rueckmeldung zum Text, und nichts war
    geschrieben."""
    from interview_theater import ueberarbeitung

    if not ueberarbeitung.aktiv() or not ist_erfundenes_notiert(text):
        return False
    if phasen.aktuelle(conn, chat_id) not in (
            ueberarbeitung.PHASE_UEBERARBEITUNG, ueberarbeitung.PHASE_BUEHNE):
        return False
    log.info("Erfundenes Notiert verworfen, chat_id=%s", chat_id)
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None),
        "gespraech_notiert_erfunden",
        "Antwort begann mit \"Noted\", ohne dass der Erkenner etwas "
        "geschrieben hatte",
    )
    return True


def _melde_fehler(conn, tg, e, chat_id: int, versand_erfolgreich: bool) -> None:
    """Der Vorfall zum gescheiterten Zug -- und die Zeile an die Gruppe, aber
    nur, wenn sie noch KEINE Antwort bekommen hat.

    Ist der Tagesdeckel erreicht (Karte Padua S), war es kein Fehler: dann
    geht hoechstens die Pausenmeldung hinaus (``kosten.melde_pause_wenn_deckel``
    drosselt selbst), und weder "hakt gerade" noch die Begruessung noch ein
    ``gespraechszug_fehlgeschlagen`` -- den Tag haelt der eine Vorfall
    ``kostendeckel_erreicht`` fest."""
    if not versand_erfolgreich and kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id):
        return
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None), "gespraechszug_fehlgeschlagen",
        "Sprachmodell-Aufruf im Gespraechszug fehlgeschlagen" if not versand_erfolgreich
        else "Bot-Antwort in 'nachricht' mitzuschreiben ist fehlgeschlagen, obwohl "
             "die Antwort schon in der Gruppe steht",
    )
    if versand_erfolgreich:
        return
    # Beim allerersten Zug lieber die feste Begruessung als eine Fehlerzeile --
    # die Gruppe soll nicht mit "hakt gerade" anfangen.
    try:
        if not repo.hat_bot_nachricht(conn, chat_id):
            from interview_theater import bot as _bot
            _bot.erstkontakt(conn, tg, e, chat_id)
        else:
            tg.sende(chat_id, T._TEXT_FEHLER)
    except Exception:
        log.exception("Fehlermeldung an die Gruppe fehlgeschlagen, chat_id=%s", chat_id)


def _zug_faellt_aus(conn, tg, klm, e, chat_id: int, letzte_nachricht) -> bool:
    """Die Vorfahrtsregeln vor dem Gespraechszug: liefert True, wenn dieser Zug
    ausfaellt, weil die Nachricht schon anderswo beantwortet ist.

    Alle sieben Faelle haben denselben Grund -- **zwei Antworten auf dieselbe
    Nachricht sind eine zu viel**. Das Wasserzeichen rueckt im ``finally`` von
    ``antworte`` trotzdem vor, die Nachrichten stehen also nicht als
    unbeantwortet herum; und der Erkenner-Nachlauf (``bot._zug_und_erkenner``)
    laeuft unabhaengig weiter."""
    return _szene_hat_vorfahrt(
        conn, tg, klm, e, chat_id, letzte_nachricht
    ) or _war_die_erwartete_antwort(conn, tg, klm, e, chat_id, letzte_nachricht)


#: Welche Nachricht schon als Regie-Notiz verbraucht wurde (Padua Phasen TEIL
#: 2, Abschlussreview Fix 3): chat_id -> message_id. ``bot._zug_und_erkenner``
#: laesst ERST ``bearbeite`` laufen (die Notiz nach "No, change it again"
#: startet die Ueberarbeitung und nimmt die Sperre), DANN den Erkenner auf
#: derselben Nachricht -- der las sie als ``text_ueberarbeiten`` und meldete
#: "laeuft noch" ueber genau den Lauf, den die Nachricht gerade selbst
#: gestartet hatte. Ein Eintrag je Gruppe, im Prozess (wie
#: ``szenenfolge._regienotiz_erwartet``); ein Neustart verliert ihn, und dann
#: kommt hoechstens die alte, harmlose Zeile.
_notiz_verbraucht: dict[int, int] = {}
_notiz_verbraucht_schutz = threading.Lock()


def _merke_notiz_verbraucht(chat_id: int, letzte_nachricht) -> None:
    """Nur mit ``ueberarbeitung.aktiv()`` -- nur dort liest der Erkenner
    dieselbe Nachricht noch einmal als Ueberarbeitung (Dortmund unveraendert)."""
    from interview_theater import ueberarbeitung

    if not ueberarbeitung.aktiv():
        return
    try:
        message_id = letzte_nachricht["message_id"]
    except (KeyError, IndexError, TypeError):
        return
    if message_id is None:
        return
    with _notiz_verbraucht_schutz:
        _notiz_verbraucht[chat_id] = message_id


def _uebernimm_stagescript_vor_dem_senden(conn, tg, klm, e, chat_id: int, text: str,
                                          letzte_nachricht) -> int | None:
    """Padua Phase 7 (Birk 08.10.2026 ~14:00): ist diese Antwort des
    Gespraechsbots eine vollstaendige Szenenfassung, wird sie VOR dem Versand
    ins Script uebernommen -- ``stagescript.uebernimm_chatfassung`` schickt
    dann selbst die Diff-Nachricht mit Yes/No, die Gruppe sieht den
    Volltext nie. Liefert die ``message_id`` dieser Nachricht, oder ``None``
    (kein Treffer -- der normale Versand des Gespraechstexts folgt).

    Markiert die ausloesende Nachricht als Regie-Notiz verbraucht
    (``_merke_notiz_verbraucht``), damit der Erkenner-Nachlauf
    (``erkenner._starte_stagescript_notiz``) dieselbe Nachricht nicht noch
    einmal als Neuschreibauftrag liest -- Live-Befund G1 (08.10.2026,
    web_post 10:57-11:07): sonst liefen Gespraechsbot UND Neuschreiblauf auf
    dieselbe Nachricht, zwei verschiedene Fassungen entstanden."""
    try:
        from interview_theater import stagescript

        message_id = stagescript.uebernimm_chatfassung(conn, tg, klm, e, chat_id, text)
    except Exception:
        log.exception("Chat-Fassung nicht ins Script uebernommen, chat_id=%s", chat_id)
        return None
    if not message_id:
        return None
    _merke_notiz_verbraucht(chat_id, letzte_nachricht)
    return message_id


def _szenenfassung_waehrend_neuschreiben(conn, chat_id: int, text: str) -> bool:
    """Phase 7 mit ``[karten] p7_aenderung_im_chat``: ist ``text`` eine
    vollstaendige Szenenfassung, waehrend ein Stage-Script-Lauf fuer diese
    Gruppe laeuft? Dann ist sie eine zweite Fassung neben der des Laufs."""
    try:
        from interview_theater import phasen, stagescript, workshop as _workshop

        if not _workshop.p7_aenderung_im_chat_aktiv():
            return False
        if phasen.aktuelle(conn, chat_id) != 7 or not stagescript.laeuft(chat_id):
            return False
        return stagescript.chatfassung(conn, chat_id, text) is not None
    except Exception:
        log.exception("Pruefung Szenenfassung/Neuschreiben fehlgeschlagen, chat_id=%s", chat_id)
        return False


def nimm_notiz_verbraucht(chat_id: int, message_ids) -> bool:
    """War eine dieser Nachrichten (der Stapel eines Erkennerlaufs) schon eine
    Regie-Notiz, die ``bearbeite`` verbraucht hat? Raeumt den Eintrag dabei
    ab -- eine Nachricht, ein Lauf. Ein Eintrag fuer eine Nachricht AUSSERHALB
    des Stapels bleibt stehen (ein anderer, gleichzeitiger Lauf)."""
    with _notiz_verbraucht_schutz:
        message_id = _notiz_verbraucht.get(chat_id)
        if message_id is None or message_id not in set(message_ids):
            return False
        del _notiz_verbraucht[chat_id]
        return True


#: Feedbackloop P1-2, Runde 3, Befund H2 (05.10.2026, sim.db msg 186-189):
#: welche Gruppennachricht der Gespraechszug schon als "eigene Fragen fertig"
#: gelesen hat -- er startete darauf den Vergleich ("Question 1/27"), und
#: sechs Sekunden spaeter setzte der Erkenner aus DERSELBEN Nachricht ("we
#: can go to the interviews") Phase 3; der Durchgang lief dann in Phase 3.
#: chat_id -> message_id, im Prozess wie ``_notiz_verbraucht``. Der Erkenner
#: holt den Eintrag ab (``nimm_vergleich_im_zug``) und laesst fuer genau diese
#: Nachricht ``phase_setzen`` fallen; eine SPAETERE Nachricht wechselt die
#: Phase wie immer (die Phase setzt die Gruppe).
_vergleich_im_zug: dict[int, int] = {}
_vergleich_im_zug_schutz = threading.Lock()


def _vergleich_stand(conn, chat_id: int) -> tuple[bool, bool]:
    """(eigene Fragen fertig gemeldet, Einzeldurchgang laeuft) -- der Stand,
    an dem ``antworte`` vor und nach dem Zug abliest, ob GENAU dieser Zug den
    Vergleich angestossen hat (``knoepfe.fragen._eigene_fertig``: setzt
    ``fragen_eigene_erstellt_am`` und startet den Durchgang, sobald die
    KI-Fragen stehen). Gelesen statt in ``knoepfe/fragen.py`` gesetzt."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        fertig = bool(stand["fragen_eigene_erstellt_am"]) if stand else False
    except (IndexError, KeyError):
        fertig = False
    return fertig, knoepfe.einzeln_aktiv(conn, chat_id)


def _merke_vergleich_im_zug(conn, chat_id: int, vorher: tuple[bool, bool] | None,
                            message_id: int) -> None:
    """Hat sich zwischen ``vorher`` und jetzt einer der beiden Schalter
    eingeschaltet, war es dieser Zug -- dann gilt der Merker fuer
    ``message_id``. Weich: ein Fehler hier darf den Zug nicht stoeren."""
    if vorher is None:
        return
    try:
        nachher = _vergleich_stand(conn, chat_id)
    except Exception:
        log.exception("Vergleichs-Merker nicht gesetzt, chat_id=%s", chat_id)
        return
    if any(n and not v for v, n in zip(vorher, nachher)):
        with _vergleich_im_zug_schutz:
            _vergleich_im_zug[chat_id] = message_id


def nimm_vergleich_im_zug(conn, chat_id: int) -> bool:
    """Hat der Gespraechszug auf eine der Nachrichten, die der Erkenner gleich
    liest (``repo.unextrahierte`` -- also VOR ``erkenner.erkenne`` fragen),
    den Vergleich gestartet? Raeumt den Eintrag in jedem Fall ab: eine
    Nachricht, ein Erkennerlauf."""
    with _vergleich_im_zug_schutz:
        message_id = _vergleich_im_zug.pop(chat_id, None)
    if message_id is None:
        return False
    return message_id in {n["message_id"] for n in repo.unextrahierte(conn, chat_id)}


def vergiss_vergleich_im_zug() -> None:
    """Fuer Tests: alle Merker abraeumen."""
    with _vergleich_im_zug_schutz:
        _vergleich_im_zug.clear()


def _szene_hat_vorfahrt(conn, tg, klm, e, chat_id: int, letzte_nachricht) -> bool:
    """Die fuenf Faelle, in denen der Szenenweg die Nachricht beantwortet."""
    # Spaete Importe, wie ueberall hier: ``szene`` und ``szenenfolge``
    # greifen ihrerseits auf ``knoepfe`` zu -- ein Modulimport oben waere
    # ein Zyklus.
    from interview_theater import szene, szenenfolge, szenenkarte, workshop

    # "Clear the questions" auf einer Szenenkarte (Birk 08.10.2026 ~09:20):
    # die naechste Nachricht ist die Antwort auf GENAU die gestellte Frage,
    # nicht ein Gespraechsbeitrag -- derselbe Gedanke wie die Regie-Notiz
    # unten, nur DB-gestuetzt (``szene.karte_klaerung`` ueberlebt einen
    # Neustart, anders als ``szenenfolge._regienotiz_erwartet``).
    text = (letzte_nachricht["text"] or "").strip()
    if workshop.szenenkarten_aktiv() and text:
        if szenenkarte.beantworte_frage(conn, tg, klm, e, chat_id, text):
            log.info(
                "Gespraechszug unterdrueckt, Antwort auf Kartenfrage, chat_id=%s", chat_id)
            _merke_notiz_verbraucht(chat_id, letzte_nachricht)
            return True

        # Der "No, change"-Dialog (Birk 08.10.2026 ~09:35, Nachtrag, Punkt
        # 4): spricht die Gruppe MITTEN IM DIALOG erkennbar von den
        # Fragen selbst, bietet der Bot den Klaerweg an statt selbst zu
        # antworten -- kein Modellaufruf, derselbe Gedanke wie oben.
        dialog_nummer = szenenkarte.dialog_aktive_nummer(conn, chat_id)
        if dialog_nummer is not None and szenenkarte.notiz_betrifft_fragen(text):
            szene_dialog = szenenkarte._szene_mit_nummer(conn, chat_id, dialog_nummer)
            karte_dialog = szenenkarte.karte_von(szene_dialog) if szene_dialog else None
            if karte_dialog is not None and karte_dialog.get("fragen"):
                szenenkarte.biete_klaerweg_im_dialog(conn, tg, e, chat_id, dialog_nummer)
                log.info(
                    "Gespraechszug unterdrueckt, Klaerweg im Dialog angeboten, "
                    "chat_id=%s", chat_id)
                _merke_notiz_verbraucht(chat_id, letzte_nachricht)
                return True

    # Ein laufender Szenenauftrag ist eine vollstaendige Antwort
    # (05.09.2026, Testgruppe 22:05): waehrend der Szenenlauf seine
    # Systemzeilen schickt ("Start frei", "Ich schreibe die Szene aus",
    # der USA-Hinweis), kommentierte der Gespraechs-Bot sie parallel und
    # stellte Rueckfragen zu laengst Festgelegtem ("wollt ihr die
    # Reihenfolge behalten?").
    if szene.laeuft(chat_id):
        log.info("Gespraechszug unterdrueckt, Szenenlauf laeuft, chat_id=%s", chat_id)
        return True

    # Und derselbe Gedanke eine Sekunde frueher (06.09.2026, Testgruppe
    # 00:30): ist die ausloesende Nachricht nichts als ein Auftrag ("neu
    # schreiben"), faellt der Gespraechszug aus, BEVOR der Szenenlauf
    # ueberhaupt angelaufen ist. Der Erkenner-Nachlauf startet den
    # Auftrag; dessen eigene Systemzeilen sind die vollstaendige Antwort.
    #
    # Ohne das antwortete der Bot am Testabend um 00:30:31 mit "Birk,
    # klar -- Szene 1 neu. Eine Frage dazu: ...?" und eine Sekunde
    # spaeter lief die Szene trotzdem los: die Frage war nie eine, sie
    # stand nur im Weg.
    if ist_auftrag(letzte_nachricht["text"]):
        log.info(
            "Gespraechszug unterdrueckt, Nachricht ist ein Auftrag, chat_id=%s",
            chat_id,
        )
        return True

    # "Lies uns Szene 2 vor" (06.09.2026, Nacht-Simulation Punkt 7): die
    # Gruppe will den WORTLAUT einer Szene sehen. Den hat der
    # Gespraechs-Bot gar nicht im Kontext (``kontext.baue`` gibt nur die
    # zuletzt geaenderte Szene) -- in der Simulation hat er deshalb
    # zusammengefasst statt gezeigt. Hier geht stattdessen der echte
    # Text aus der Datenbank raus, derselbe Weg wie hinter dem Knopf
    # "Szene N ansehen". Reiner Musterabgleich, kein Modellaufruf.
    gewuenscht = szenentext_gewuenscht(letzte_nachricht["text"])
    if gewuenscht is not None:
        log.info(
            "Gespraechszug unterdrueckt, Szenentext gewuenscht (%s), chat_id=%s",
            gewuenscht, chat_id,
        )
        knoepfe.zeige_szenentext(conn, tg, chat_id, gewuenscht)
        return True

    # Die Regie-Notiz nach "Passt, aber anders" unter einem Szenentext
    # (05.09.2026, Phase 6): der Bot hat gerade gefragt, was anders werden
    # soll -- diese eine Nachricht ist die Antwort darauf und geht als
    # Auftrag in den Szenenlauf, nicht in den Gespraechszug. Ohne das
    # bekaeme die Gruppe eine freundliche Gespraechsantwort statt einer
    # neuen Fassung, und die Notiz waere verloren.
    # Padua Phasen TEIL 2 (Phase 6/7, Rewrite/Stage Version): beide Notizen
    # gehen ueber den EINEN Rueckmeldeweg ``ueberarbeitung.ueberarbeite`` --
    # in der Prosa-Phase traegt der Auftrag dort ``BISHER_MARKER``, sonst
    # saehe das Modell die bestehende Prosa nicht. Ohne den Schalter (und in
    # Phase 5) bleiben die Aufrufe unten zeichengleich.
    from interview_theater import phasen, ueberarbeitung

    ueber = (ueberarbeitung.aktiv()
             and phasen.aktuelle(conn, chat_id) in (6, 7))
    nummer = szenenfolge.nimm_regienotiz(chat_id)
    if nummer is not None and (letzte_nachricht["text"] or "").strip():
        _merke_notiz_verbraucht(chat_id, letzte_nachricht)
    if ueber and nummer is not None and (letzte_nachricht["text"] or "").strip():
        ueberarbeitung.ueberarbeite(
            conn, tg, klm, e, chat_id, letzte_nachricht["text"].strip(),
            nummer=nummer)
        return True
    if nummer is not None and (letzte_nachricht["text"] or "").strip():
        szene.starte(
            conn, tg, klm, e, chat_id,
            szene.T.TEXT_AUFTRAG_NEU.format(
                nummer=nummer, notiz=letzte_nachricht["text"].strip()),
        )
        return True

    # Dieselbe Bauart fuer die Kurzgeschichte (06.09.2026, Birk 11:50):
    # nach "Etwas aendern" unter der fertigen Geschichte ist diese eine
    # Nachricht die Regie-Notiz -- sie geht als Anweisung in den
    # naechsten Lauf, nicht in den Gespraechszug.
    # Uebersicht/Logline (Birk 07.10.2026 ~18:15): nach "No, change" ist
    # die naechste Nachricht das Feedback fuer den neuen Lauf.
    from interview_theater.knoepfe import szenen as _knoepfe_szenen

    if _knoepfe_szenen.nimm_uebersicht_notiz(chat_id) and (
        letzte_nachricht["text"] or ""
    ).strip():
        from interview_theater import entwurf

        _merke_notiz_verbraucht(chat_id, letzte_nachricht)
        entwurf.starte_uebersicht(conn, tg, klm, e, chat_id,
                                  notiz=letzte_nachricht["text"].strip())
        return True

    if knoepfe.nimm_geschichte_notiz(chat_id) and (
        letzte_nachricht["text"] or ""
    ).strip():
        from interview_theater import kurzgeschichte

        _merke_notiz_verbraucht(chat_id, letzte_nachricht)

        # Die Geschichte-Notiz geht nur in Phase 6 (Rewrite) ueber den
        # Rueckmeldeweg; ohne Ziel sagt ``ueberarbeite`` das selbst
        # (``_TEXT_KEIN_ZIEL``), statt die Notiz zu verschlucken.
        if ueber and phasen.aktuelle(conn, chat_id) == 6:
            ueberarbeitung.ueberarbeite(
                conn, tg, klm, e, chat_id, letzte_nachricht["text"].strip())
            return True
        kurzgeschichte.starte(
            conn, tg, klm, e, chat_id, letzte_nachricht["text"].strip(),
        )
        return True

    return False


def _war_die_erwartete_antwort(conn, tg, klm, e, chat_id: int,
                               letzte_nachricht) -> bool:
    """Die zwei Faelle, in denen der Bot gerade nach etwas Bestimmtem gefragt
    hat und diese eine Nachricht die Antwort darauf ist."""
    # Dieselbe Bauart fuer die freie Nachricht in der Phase-2-Stufe "Fragen
    # einzeln" (02.10.2026, Padua): nach "Andere Richtung" ist die naechste
    # Nachricht die gewuenschte Richtung, und waehrend eine Frage die
    # aktuelle ist, ist jede freie Nachricht ihr Schaerfungswunsch --
    # deterministisch, kein Erkenner-Lauf nur zum Klassifizieren.
    if knoepfe.nimm_offene_frage_text(
        conn, tg, klm, e, chat_id, letzte_nachricht["text"] or "",
    ):
        return True

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
            return True
        tg.sende(chat_id, knoepfe._TEXT_FIGURENZAHL_UNKLAR)
        knoepfe.erwarte_figurenanzahl(chat_id)
        return True

    return False


def _erfrage_antwort(conn, klm, e, chat_id: int, offen: list, tg,
                     hinweis: str | None, tippstand: dict | None = None) -> str:
    """Der eigentliche Gespraechszug: Kontext bauen, Modell fragen, Antwort
    saeubern. Liefert den fertigen Text, wirft bei einer unbrauchbaren
    Modellantwort ``LLMFehler``.

    Die Tippanzeige laeuft ueber den ganzen Aufruf -- auch ueber die
    Nachfassaufrufe in ``_ohne_denkspur`` und ``_ohne_echo``, die aus Sicht der
    Gruppe zur selben Wartezeit gehoeren.

    ``tippstand`` (Addendum Robo 14:41): wird unveraendert an
    ``_tippanzeige`` durchgereicht, siehe dort."""
    with _tippanzeige(tg, chat_id, tippstand, conn=conn):
        # Die Phase geht in die Systemanweisung (worauf der Bot gerade den
        # Fokus legt, prompts/phasen/N.md), nicht in den Koerper -- die
        # datengetriebenen Bloecke bleiben unveraendert (phasen.py).
        phase = phasen.aktuelle(conn, chat_id)
        # Modellwahl-Karte (02.10.2026): die EINE Entscheidung fuer diesen
        # Zug, VOR dem Kontextbau -- das Budget haengt daran (groesseres
        # Fenster fuer Opus, kontext.baue(ueber_claude=...)).
        ueber_claude = modellwahl.konversation_ueber_claude(e, conn, chat_id)
        # Allererster Zug der Gruppe: die Begruessung entsteht aus der
        # ersten Nachricht heraus (kontext.ERSTKONTAKT), nicht als fester
        # Text vorweg (bot.erstkontakt ist seit 04.09. abends nur noch
        # der Rueckfallweg, wenn der Modellaufruf scheitert).
        erstkontakt = not repo.hat_bot_nachricht(conn, chat_id)
        koerper = kontext.baue(conn, chat_id, offen, e, erstkontakt=erstkontakt,
                               ueber_claude=ueber_claude)
        system = kontext.system(e.bot_name, phase, chat_id)
        # Der laufende Text (30.09.2026, Karte W): ``senke`` ist ``None``,
        # solange der Kanal keinen Strom kann -- der Telegram-Weg bleibt damit
        # Zeichen fuer Zeichen, wie er war (E1). Abgeschlossen wird sie NICHT
        # hier, sondern in ``antworte``: erst dort steht fest, ob die Antwort
        # wirklich verschickt wurde.
        #
        # Phase 7 mit ``[karten] p7_aenderung_im_chat`` (Robo-Entscheidung
        # 08.10.2026 ~14:00): eine vollstaendige Szenenfassung wird NIE als
        # Volltext verschickt, nur als Diff -- ohne Streaming bleibt die
        # Wall of Text erst recht nicht einmal kurz als laufende Blase
        # stehen (notfalls Streaming abschalten, siehe Auftrag).
        from interview_theater import workshop as _workshop

        if phase == 7 and _workshop.p7_aenderung_im_chat_aktiv():
            senke = None
        else:
            senke = strom.senke(tg, chat_id, "gespraech")
        ergebnis = modellwahl.aufruf_schema(
            conn, klm, e, chat_id, system, koerper, SCHEMA, "gespraech",
            ueber_claude=ueber_claude, bei_teil=senke, teil_feld="antwort",
        )
        antwort = _antworttext(ergebnis)
        if not str(antwort).strip():
            raise LLMFehler(
                "Sprachmodell lieferte keine verwertbare Antwort "
                f"(Typ {type(ergebnis).__name__})"
            )
        text = _ohne_denkspur(conn, klm, e, chat_id, system, koerper, antwort,
                              bei_teil=senke, ueber_claude=ueber_claude)
        text = _ohne_echo(conn, klm, e, chat_id, system, koerper, offen, text,
                          bei_teil=senke, ueber_claude=ueber_claude)
        text = _ohne_ankuendigung(conn, klm, e, chat_id, system, koerper, text,
                                  bei_teil=senke, ueber_claude=ueber_claude)
        text = _ohne_schreibangebot(conn, klm, e, chat_id, system, koerper,
                                    text, phase, bei_teil=senke,
                                    ueber_claude=ueber_claude)
        if hinweis:
            text = f"{text}\n\n{hinweis}"
    return text


def _antworttext(ergebnis) -> str:
    """Der Antworttext aus dem, was das Modell geliefert hat.

    Normalerweise ``{"antwort": "..."}``, gelegentlich aber ein blanker String
    (gemessen 05.09.2026 im Testlauf: TypeError 'string indices must be
    integers' riss den ganzen Gespraechszug mit, die Gruppe bekam gar nichts).
    Ein Zug darf an der Verpackung nicht scheitern -- der Inhalt ist da."""
    if isinstance(ergebnis, str):
        return ergebnis
    if isinstance(ergebnis, dict):
        return ergebnis.get("antwort") or ""
    return ""


def _sende_mit_leiste(conn, tg, chat_id: int, text: str, klm=None,
                      e=None) -> tuple[int, str]:
    """Schickt die Antwort mit der Speicher-Leiste und liefert
    ``(message_id, text_ohne_marker)`` -- den Text so, wie er auch in
    ``nachricht`` mitgeschrieben wird.

    Die Speicher-Leiste (05.09.2026): enthaelt die Antwort einen
    Vorschlagsblock (``vorschlag.py``) fuer das, was gerade fehlt -- Begriffe
    in Phase 1, Fragen in 2, Kernthema/Figuren in 4 --, haengen "So speichern"
    und "Nochmal anders" darunter. Ohne Block gibt es nur den Text; geraten
    wird nichts. Die Markerzeilen fallen dabei weg, die Gruppe sieht sie nie.

    ``klm``/``e`` reichen bis zum Padua-Autosave in Phase 1/2 durch
    (``knoepfe.basis._autospeichere``): derselbe Undo-Mechanismus wie ein
    Erkennerlauf (``erkenner.lauf_fuer_knopf``) und derselbe automatische
    Phasensprung wie am "Ja, speichern"-Knopf (``uebergang_nach_speichern``)
    -- ausser fuer Begriffe in Phase 1: dort kein Sprung, die Antwort traegt
    die Frage "Move on?" (``knoepfe.basis._korrigiere_begriffe``).

    Faellt die Tastatur aus (Telegram-Fehler), geht der Text trotzdem raus: die
    Antwort ist wichtiger als ihre Knoepfe."""
    try:
        message_id, _ = knoepfe.sende_mit_speicherleiste(
            conn, tg, chat_id, text, klm=klm, e=e,
        )
        return message_id, vorschlag.ohne_marker(text) or text
    except Exception:
        log.exception("Speicher-Leiste fehlgeschlagen, chat_id=%s", chat_id)
        sauber = vorschlag.ohne_marker(text) or text
        return tg.sende(chat_id, sauber), sauber


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


#: Die Anweisung des Auftragszugs, dessen Antwort in DIESEM Thread gerade
#: abgeliefert wird (S1-Review, Feedbackloop P1-2): eine Schaerfung der
#: Phase 2 laeuft ohne Sperre je Gruppe im eigenen Thread, waehrenddessen kann
#: die Gruppe die Frage schon annehmen. ``fragen.uebernimm_schaerfung`` ordnet
#: die spaete Antwort darueber der Frage zu, fuer die sie gestartet wurde --
#: nicht der, die inzwischen dasteht. Thread-lokal statt eines weiteren
#: Parameters, weil ``starte_auftrag`` seine Signatur mit dem Simulator teilt.
_LAUFENDER_AUFTRAG = threading.local()


@contextmanager
def laeuft_als_auftrag(anweisung: str):
    """Rahmen um die Ablieferung einer Auftragsantwort (``auftragszug``)."""
    vorher = getattr(_LAUFENDER_AUFTRAG, "anweisung", None)
    _LAUFENDER_AUFTRAG.anweisung = anweisung
    try:
        yield
    finally:
        _LAUFENDER_AUFTRAG.anweisung = vorher


def laufender_auftrag() -> str | None:
    """Die Anweisung des Auftrags, dessen Antwort dieser Thread gerade
    abliefert -- None ausserhalb von ``laeuft_als_auftrag``."""
    return getattr(_LAUFENDER_AUFTRAG, "anweisung", None)


def auftragszug(conn, tg, klm, e, chat_id: int, anweisung: str,
                arbeitszeile: str | None = None,
                arbeitsart: str | None = None) -> None:
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
        # ``arbeitszeile``: eine kurze Zeile, die SOFORT sichtbar macht, dass
        # der Bot arbeitet, und beim Ende wieder verschwindet (06.09.2026,
        # 10:10). Ohne sie schwieg der Bot zwischen "Notiert: Fragen ..." und
        # der Sensibilitaetspruefung minutenlang.
        with arbeitet_sichtbar(tg, chat_id, arbeitszeile, arbeitsart, conn=conn):
            phase = phasen.aktuelle(conn, chat_id)
            ueber_claude = modellwahl.konversation_ueber_claude(e, conn, chat_id)
            koerper = kontext.baue(conn, chat_id, [], e, ueber_claude=ueber_claude)
            koerper = f"{koerper}\n\n{T._AUFTRAG_KOPF}\n{anweisung}"
            system = kontext.system(e.bot_name, phase, chat_id)
            senke = strom.senke(tg, chat_id, "gespraech")
            ergebnis = modellwahl.aufruf_schema(
                conn, klm, e, chat_id, system, koerper, SCHEMA, "gespraech",
                ueber_claude=ueber_claude, bei_teil=senke, teil_feld="antwort",
            )
            if isinstance(ergebnis, str):
                antwort = ergebnis
            elif isinstance(ergebnis, dict):
                antwort = ergebnis.get("antwort") or ""
            else:
                antwort = ""
            if not str(antwort).strip():
                raise LLMFehler("Sprachmodell lieferte keine verwertbare Antwort")
            text = _ohne_denkspur(conn, klm, e, chat_id, system, koerper, antwort,
                                  bei_teil=senke, ueber_claude=ueber_claude)
    except Exception:
        log.exception("Auftragszug fehlgeschlagen, chat_id=%s", chat_id)
        strom.verwirf(tg, chat_id)
        try:
            # Tagesdeckel (Karte Padua S): Pause statt Fehlerzeile.
            if kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id):
                return
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "auftragszug_fehlgeschlagen", "Knopf-Auftrag am Modell gescheitert",
            )
            tg.sende(chat_id, T._TEXT_FEHLER)
        except Exception:
            log.exception("Fehlermeldung zum Auftragszug fehlgeschlagen")
        return

    try:
        with laeuft_als_auftrag(anweisung):
            message_id, _ = knoepfe.sende_mit_speicherleiste(
                conn, tg, chat_id, text, klm=klm, e=e,
            )
        text = vorschlag.ohne_marker(text) or text
    except Exception:
        log.exception("Leiste am Auftragszug fehlgeschlagen, chat_id=%s", chat_id)
        text = vorschlag.ohne_marker(text) or text
        try:
            message_id = tg.sende(chat_id, text)
        except Exception:
            # Auch der Rueckfall ist gescheitert: keine Nachricht, also auch
            # keine Blase, die auf sie wartet (Fix-Runde 1, Befund 5). Der
            # Fehler fliegt weiter wie bisher.
            strom.verwirf(tg, chat_id)
            raise
    strom.schliesse(tg, chat_id, message_id)
    if not message_id:
        # R2-1: ``fragen.uebernimm_schaerfung`` verwirft eine spaet
        # abgelieferte Schaerfung fuer eine schon entschiedene Frage stumm
        # und liefert dafuer ``None`` statt einer ``message_id`` -- nichts
        # wurde an die Gruppe geschickt, also ist auch nichts mitzuschreiben.
        # ``strom.schliesse(..., None)`` laesst die vorlaeufige Blase
        # ersatzlos verschwinden (``web_vereint``: "fertig ohne Nachricht"
        # zaehlt wie "abgebrochen").
        return
    try:
        repo.merke_nachricht(
            conn, chat_id, message_id, e.bot_name, 1, "text", text, repo._jetzt(),
        )
    except Exception:
        log.exception("Auftragsantwort nicht mitgeschrieben, chat_id=%s", chat_id)


def starte_auftrag(conn, tg, klm, e, chat_id: int, anweisung: str,
                   arbeitszeile: str | None = None,
                   arbeitsart: str | None = None):
    """Gibt einen ``auftragszug`` an einen eigenen Thread ab und kehrt sofort
    zurueck -- dasselbe Muster wie ``szene.starte`` und
    ``sprachprofil.starte``. Liefert den Thread (fuer Tests) oder None.

    ``arbeitszeile`` wird im Thread gesendet und am Ende wieder geloescht
    (``arbeitet_sichtbar``) -- fuer jeden Auftrag, der laenger als ein paar
    Sekunden dauern kann."""
    if klm is None or not (anweisung or "").strip():
        log.error("Auftragszug ohne Modell oder Anweisung, chat_id=%s", chat_id)
        return None
    thread = threading.Thread(
        target=auftragszug,
        args=(conn, tg, klm, e, chat_id, anweisung, arbeitszeile, arbeitsart),
        daemon=True,
    )
    thread.start()
    return thread


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)

T = sprache.Texte(__name__)
#: Nachtauftrag cc-p67texte (08.10.2026): die Hinweiszeile ("One moment,
#: I'm thinking.") italienisch in Phase 6/7 -- Auswahl in
#: ``_texte_fuer_phase``, derselbe Mechanismus wie ``erkenner.py``/
#: ``stagescript.py``.
_T_IT = sprache.Texte(__name__, sprachcode="it")


def _texte_fuer_phase(conn, chat_id: int) -> sprache.Texte:
    """``_T_IT`` nur wenn ``conn`` da ist, die Gruppe in Phase 6/7 steht UND
    chat_id in ``workshop.italienisch_ab_phase6_chats()`` steht -- sonst
    ``T``. ``conn`` fehlt beim alten, direkten Test-Aufruf von
    ``_tippanzeige`` ohne Datenbank."""
    if conn is None:
        return T
    from interview_theater import workshop

    if (phasen.aktuelle(conn, chat_id) in (6, 7)
            and chat_id in workshop.italienisch_ab_phase6_chats()):
        return _T_IT
    return T
