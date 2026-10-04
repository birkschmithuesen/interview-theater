"""Der Chat im Browser (30.09.2026, Karte Padua A2).

Die Gegenseite zu ``web_kanal.py``: dort schreibt der Bot in ``web_post``,
hier liest der Browser es. **Eigenes Modul und nicht in ``web.py``**, weil
``web.py`` ein Kollisions-Hotspot mit Karte A1 ist -- dort stehen nur die
Routing-Zeilen, alles andere (HTML, CSS, JS, Handler) liegt hier.

**Kein SQL, kein Modell.** Gelesen wird ueber ``web_daten`` (read-only),
geschrieben ueber ``repo`` (Aufgaben 7-10). Der Webserver hat keinen
Modellklienten und soll keinen bekommen.

**Der HTML-Filter ist der Kern.** Bot-Ausgaben tragen Telegram-HTML
(``parse_mode="HTML"``, fuenf Stellen im Repo, u. a. ``vorschlag.menuetext``):
die Ansicht muss es darstellen und darf nichts anderes durchlassen. Der Weg
ist bewusst der langweilige: **alles maskieren, dann eine geschlossene Liste
wieder zulassen** -- nicht "das Gefaehrliche entfernen".
"""

import html
import json
import logging
import os
import re
import sqlite3
import urllib.parse
from contextlib import contextmanager
from pathlib import Path

from interview_theater import db, repo, sprache, stt, web_daten, web_grenze, web_kanal

log = logging.getLogger(__name__)

#: Padua Hotfix B6/B7: die Texte, die die EN-Oberflaeche zeigt, zur
#: Aufrufzeit aus ``sprachen/en/texte.toml`` (``["web_chat"]``) -- wie in
#: ``web.py``. Nur die dort eingetragenen Konstanten; der Rest bleibt deutsch.
T = sprache.Texte(__name__)

#: Der Unterpfad unter ``/g/<token>/``. Steht wortgleich in
#: ``scripts/web_gruppe.CHAT_PFAD`` (Test).
CHAT_PFAD = "chat"

#: Wo die Telefon-Organisationskarten liegen (UX-Knoepfe-Karte, Abschnitt 5)
#: -- wortgleich mit ``web.STATIC_HANDYS_PRAEFIX`` ohne den Schlussschraegstrich.
STATIC_HANDYS_PFAD = "static/handys"

#: Wie lang eine Nachricht aus dem Browser hoechstens ist. Dieselbe Zahl wie
#: ``telegram.NACHRICHT_GRENZE``: eine Gruppe, die im Browser arbeitet, soll
#: nicht mehr schreiben koennen, als der Telegram-Weg tragen wuerde -- sonst
#: laesst sich ein Workshop nicht von einem Kanal in den anderen retten.
MAX_TEXT_ZEICHEN = 4000

#: Was der Browser liefern darf, und mit welcher Endung es abgelegt wird --
#: DIESELBE Tabelle wie im Bot (``web_kanal.MIME_ERLAUBT``, dort auch die
#: Begruendung, Falle 3). Sie steht dort und nicht hier, weil ``hole_updates``
#: die Endung aus der Spalte ``mime`` ableitet (Abschlussreview C1), und der
#: Bot-Prozess importiert den Webserver nicht.
MIME_ERLAUBT = web_kanal.MIME_ERLAUBT

#: Wie gross ein einzelnes Segment sein darf.
#:
#: Gerechnet, nicht geraten -- seit dem Pausen-Schnitt (VAD, 02.10.2026) auf
#: den harten Zeitdeckel IT_WEB_VAD_MAX_MS (Vorgabe 90 s), nicht mehr auf die
#: alte feste Segmentlaenge von 45 s: Opus bei 32 kbit/s ergibt fuer 90 s rund
#: 360 KiB, Safaris mp4/AAC bei 64 kbit/s rund 720 KiB. 8 MiB sind immer noch
#: gut zehnfache Luft fuer einen Browser, der eine hohe Bitrate waehlt -- und
#: sie liegen klar unter ``stt.MAX_UPLOAD_BYTES`` (25 MiB): eine Datei, die
#: Whisper ohnehin ablehnen wuerde, soll gar nicht erst ankommen.
MAX_AUDIO_BYTES = 8 * 1024 * 1024

#: Obergrenze der vom Client gemeldeten Dauer (eine Stunde). Die Dauer
#: entscheidet mit ueber ``aufnahme.HINWEIS_AB_S`` (60 s: eine lange
#: Sprachnachricht ohne Interviewmodus wird gefragt, nicht gedeutet) -- eine
#: geratene Dauer waere dort eine geratene Entscheidung.
MAX_DAUER_S = 3600

#: Die Telegram-Teilmenge ohne Attribute. ``a`` steht nicht dabei, weil es
#: eins hat und eigens behandelt wird.
ERLAUBTE_TAGS = ("b", "i", "u", "s", "code", "pre", "blockquote")

_TAGS = re.compile(
    r"&lt;(/?)(" + "|".join(ERLAUBTE_TAGS) + r")&gt;", re.IGNORECASE
)
#: Nur http und https, nur ohne maskiertes Ampersand im Ziel. Eine URL mit
#: Query-Parametern (``&amp;``) bleibt deshalb Text statt Link -- die
#: Fehlerrichtung ist bewusst: ein nicht klickbarer Link ist ein
#: Schoenheitsfehler, ein durchgelassenes Attribut ist ein Loch.
#: (Korrektur: eine Zeichenklasse kennt nur einzelne Zeichen, keine
#: Entitaeten -- ``[^&quot;&lt;&gt;\s]`` schloss faelschlich auch q/u/o/t/
#: l/g aus. Das Ausschliessen von ``&`` allein reicht: eine Entitaet --
#: auch die abschliessende ``&quot;&gt;`` selbst -- beginnt immer mit ``&``.)
_LINK = re.compile(
    r"&lt;a href=&quot;(https?://[^&\s]+)&quot;&gt;", re.IGNORECASE
)
_LINK_ENDE = re.compile(r"&lt;/a&gt;", re.IGNORECASE)

#: Event-Attribute (``onclick=``, ``onerror=``, ``onload=`` ...) -- werden
#: schon aus dem Rohtext entfernt, nicht erst maskiert. Maskiert bliebe das
#: Wort selbst lesbar (``onerror=alert(1)`` als Chattext), und genau das soll
#: in der Ansicht nicht einmal als Text auftauchen.
_EVENT_ATTR = re.compile(
    r'\bon\w+\s*=\s*(".*?"|\'.*?\'|[^\s>]*)', re.IGNORECASE
)
#: Dieselbe Ueberlegung fuer URI-Schemata, die ein Browser ausfuehren oder
#: einbetten wuerde (``javascript:``, ``data:``, ``vbscript:``) -- entfernt
#: vor der Maskierung, damit das Schema selbst nicht als Text sichtbar bleibt.
_DANGEROUS_SCHEME = re.compile(r"\b(javascript|data|vbscript):", re.IGNORECASE)


def sichere_html(text) -> str:
    """Telegram-HTML als sicheres HTML fuer die Chatansicht.

    Schritte in dieser Reihenfolge: (0) einmal entmaskieren -- Telegram-HTML
    mischt echte Tags (``<b>``) mit maskierten Literalen (``&amp;``); ohne
    diesen Schritt wuerde ein schon maskiertes ``&amp;`` beim naechsten
    ``html.escape`` zu ``&amp;amp;`` doppelt maskiert. (0b) Event-Attribute
    und gefaehrliche URI-Schemata aus dem so gewonnenen Rohtext entfernen --
    nicht erst maskieren, sie sollen nicht einmal als Text auftauchen. (1)
    alles maskieren (``html.escape``, inklusive Anfuehrungszeichen), (2) die
    geschlossene Liste wieder zulassen, (3) Zeilenumbrueche sichtbar machen.

    Dass Schritt 1 (nach 0/0b) kommt, ist die ganze Sicherheit: danach gibt
    es im Text kein einziges ``<`` mehr, und Schritt 2 kann nur das
    erzeugen, was er ausdruecklich erlaubt. Ein Filter, der stattdessen
    ``<script>`` entfernt, ist eine Liste von Dingen, an die jemand gedacht
    hat."""
    roh = html.unescape(text or "")
    roh = _EVENT_ATTR.sub("", roh)
    roh = _DANGEROUS_SCHEME.sub("", roh)
    maskiert = html.escape(roh, quote=True)
    mit_tags = _TAGS.sub(lambda t: f"<{t.group(1)}{t.group(2).lower()}>", maskiert)
    mit_links = _LINK.sub(
        lambda t: (
            f'<a href="{t.group(1)}" target="_blank" rel="noopener noreferrer">'
        ),
        mit_tags,
    )
    mit_links = _LINK_ENDE.sub("</a>", mit_links)
    return mit_links.replace("\n", "<br>")


_TEXT_TITEL = "Chat mit dem Theaterbot"
_TEXT_LEER = "Noch nichts da. Schreibt mir, womit ihr anfangen wollt."
#: Der Standard-Platzhalter (UX-Knoepfe-Karte, Abschnitt 1): das Eingabefeld
#: ist nie gesperrt, auch nicht, solange Knoepfe (Abkuerzungen) offen stehen
#: -- der Platzhalter soll genau das einladen.
_TEXT_EINGABE = "Schreibt oder sprecht einfach – oder tippt eine Abkürzung"
#: Phase 2 mit einer gerade offenen Frage (``arbeitsstand.fragen_aktuell``):
#: eine freie Nachricht zaehlt dort als Schaerfungswunsch
#: (``fragen.nimm_offene_frage_text``) -- der Platzhalter sagt das.
_TEXT_EINGABE_FRAGEN = "Sagt, was an der Frage anders soll …"
#: Phase 4 (Setting, Figuren & Geschichte): freies Erfinden ohne feste
#: Reihenfolge, siehe AGENTS.md "Erst erfinden, dann schaerfen".
_TEXT_EINGABE_SETTING = "Erzählt eure Idee …"
_TEXT_SENDEN = "Senden"
#: UX-Knoepfe-Karte, Abschnitt 1: Knoepfe sind Abkuerzungen, keine Pflicht --
#: das kleine, gedaempfte Label sagt das jedes Mal, wenn eine Chip-Leiste
#: steht, ohne dass jemand lesen muesste.
_TEXT_ABKUERZUNG = "Abkürzung:"

#: UX-Knoepfe-Karte, Abschnitt 1: die VIER Texte oben (Platzhalter +
#: Abkuerzungs-Label) und, dazu, Padua Hotfix B6/B7: Interview-Knopftext,
#: Sprachnachricht/Transkript-Zeilen -- alle mit einem englischen Gegenstueck
#: (``sprachen/en/texte.toml``, Abschnitt ``[web_chat]``), nachgeschlagen zur
#: Aufrufzeit ueber ``T`` (oben, ein ``T`` fuer das ganze Modul, wie bei jedem
#: ``T``-umgestellten Modul, ``sprache.py``). Der Rest von ``web_chat.py``
#: ist weiterhin unuebersetzt (AGENTS.md, "Englische UI-Texte der
#: Chatansicht", Uebergabe an Karte A1) -- insbesondere ``_JS_TEXTE`` bleibt
#: ein beim Import eingefrorenes Woerterbuch und liest ``_TEXT_ABKUERZUNG``
#: deshalb bewusst nackt, nicht ueber ``T``: ein Prozess bedient genau eine
#: Sprache fuer seine ganze Laufzeit, aber ``T`` nachzuschlagen waere hier
#: nur Attrappe ohne Wirkung.
_TEXT_TIPPT = "schreibt …"
_TEXT_SPRACHE = "Sprachnachricht ({dauer})"
#: Padua Hotfix B7: solange abgetippt wird -- und mit Transkript (das
#: Mikrofon und die Dauer als Kennzeichen "gesprochen", ohne Sprache).
_TEXT_SPRACHE_LAEUFT = "{dauer} · wird abgetippt …"
_TEXT_SPRACHE_ABGETIPPT = "🎤 {dauer} · {text}"
_TEXT_DATEI = "Datei: {name}"
#: Dieselbe Zeile wie ``aufnahme._TEXT_BUEHNE_NEUE_KARTE`` (DE) und ihr
#: englisches Gegenstueck (``sprachen/en/texte.toml``, ["aufnahme"]) -- als
#: Literal statt als Import, weil ``aufnahme`` ein Fachlogik-Modul ist und
#: ``web_chat`` nur erkennen, nicht nachladen muss (UX-Knoepfe-Karte,
#: Abschnitt 5). Beide Fassungen stehen hier, damit die Erkennung
#: unabhaengig von der Profilsprache des laufenden Prozesses funktioniert.
_TEXTE_BUEHNE_NEUE_KARTE = (
    "Neue Karte im Tab Bühne", "New card in the Stage tab",
)
_TEXT_ZUR_GRUPPENSEITE = "Zur Gruppenseite"
#: Bild-Overlay-Karte (04.10.2026): der ✕-Knopf braucht ein Label fuer
#: Vorleseprogramme, das Zeichen selbst steht dort als Text.
_TEXT_BILD_SCHLIESSEN = "Schließen"
#: Padua Hotfix B6/B7: ohne Emoji und ueber ``T`` nachgeschlagen (EN-Mirror,
#: ["web_chat"] in sprachen/en/texte.toml) -- der Knopftext ist einer der
#: wenigen uebersetzten in diesem Modul.
_TEXT_INTERVIEW_AN = "Interview aufnehmen"
_TEXT_INTERVIEW_AUS = "Aufnahme beenden"
#: Die drei neuen Knoepfe des Drei-Zustands-Reglers (02.10.2026, Padua):
#: Pause haelt den Recorder an, OHNE den Interviewmodus serverseitig zu
#: beenden -- "Weiter" haengt an dieselbe Sitzung an, "Beenden" ist der
#: einzige Weg, der noch /fertig schickt.
_TEXT_INTERVIEW_PAUSE = "⏸ Pause"
_TEXT_INTERVIEW_WEITER = "▶ Weiter"
_TEXT_INTERVIEW_ENDEN = "■ Beenden"
#: Vorlagen mit ``{zeit}`` wie ``_TEXT_UHR`` -- der grosse Knopf zeigt die
#: erfasste Aufnahmedauer selbst an, nicht nur das separate ``#uhr``-Feld.
_TEXT_INTERVIEW_LAEUFT = "● Interview läuft · {zeit}"
_TEXT_INTERVIEW_PAUSIERT = "Pause · {zeit}"
#: Brainstorm mithören (Phase 4, nur Web, 02.10.2026): derselbe
#: Drei-Zustands-Regler wie beim Interview (Pause/Weiter/Beenden teilen sich
#: dieselben Beschriftungen, _TEXT_INTERVIEW_PAUSE usw.), nur der grosse
#: Knopf und die Laeuft-Zeile sind eigene -- "Brainstorm" ist kein Interview.
_TEXT_BRAINSTORM_AN = "🎙 Brainstorm mithören"
_TEXT_BRAINSTORM_LAEUFT = "● Hört mit · {zeit}"
#: Hintergrund-Mithoeren Phase 1 (Padua Phase 1+2 Umbau, 03.10.2026, Task 5):
#: derselbe Drei-Zustands-Regler wie Interview/Brainstorm -- Pause/Weiter
#: teilen sich die Interview-Beschriftungen (_TEXT_INTERVIEW_PAUSE usw.),
#: nur der grosse Knopf, die Laeuft-Zeile und der eigene Beenden-Knopftext
#: sind eigene.
_TEXT_DISKUSSION_AN = "Zuhoeren starten"
_TEXT_DISKUSSION_LAEUFT = "Hoert zu ({zeit})"
_TEXT_DISKUSSION_FERTIG_KNOPF = "Diskussion fertig"
#: Kanban-Karte Buehne/PTT (04.10.2026, Telegram-Vorbild): Halten statt
#: Tippen -- der Knopftitel beschreibt jetzt die Geste, die wirklich gilt.
_TEXT_PTT = "Halten zum Sprechen"
#: Kurzer Tipp (< PTT_MIN_MS): statt einfach nichts zu zeigen, haelt die
#: Anzeige-Box fuer rund 1,2-1,5 s nur diesen Satz. EN-Wert **woertlich**
#: aus der Kanban-Karte zitiert ("Hold to talk, slide up to lock") -- nicht
#: umformulieren.
_TEXT_PTT_HINWEIS = "Gedrückt halten zum Sprechen, nach oben schieben zum Sperren."
#: Der Wegwisch-Hinweis neben dem Mikrofon-Knopf, waehrend gehalten wird.
#: Das ``‹``-Zeichen ist rein dekorativ und steht im Markup, nicht hier.
_TEXT_PTT_WISCHEN = "nach links wischen zum Abbrechen"
#: aria-label des ``✕``-Verwerfen-Knopfs im gesperrten Zustand.
_TEXT_PTT_VERWERFEN = "Aufnahme verwerfen"
_TEXT_OHNE_JS = (
    "Fuer Chat und Aufnahme braucht diese Seite JavaScript. "
    "Die Gruppenseite und das Textbuch funktionieren auch ohne."
)

_TEXT_FEHLER_LEER = "Da steht nichts."
_TEXT_FEHLER_LANG = "Das ist zu lang für eine Nachricht."
_TEXT_FEHLER_VERALTET = "Die Seite ist veraltet — bitte einmal neu laden."
_TEXT_FEHLER_ANFRAGE = "Ungültige Anfrage."
_TEXT_FEHLER_KNOPF = "Diesen Knopf kenne ich hier nicht mehr — bitte neu laden."
_TEXT_FEHLER_TYP = "Dieses Audioformat kann ich nicht annehmen."
_TEXT_FEHLER_GROSS = "Die Aufnahme ist zu groß — bitte in kürzeren Stücken."
_TEXT_FEHLER_LEER_AUDIO = "Die Aufnahme ist leer angekommen."
_TEXT_FEHLER_DAUER = "Ungültige Aufnahmedauer."

#: Rate-Limit (Karte Padua S, Aufgabe 3): "zu viel auf einmal", kein
#: technischer Begriff ("Rate-Limit") -- die Gruppe soll lesen, dass es
#: gleich weitergeht, nicht, dass sie etwas falsch gemacht hat.
_TEXT_ZU_SCHNELL = "Das war zu viel auf einmal — einen Moment, dann wieder."

#: Die Seite ist gross gesetzt: sie liegt auf einem Telefon in einem
#: Probenraum, und die Gruppe liest im Stehen.
_CSS_CHAT = """
/* Bild-Overlay-Karte (04.10.2026): seitenweites Pinch-/Doppeltipp-Zoom im
   Chat ist aus -- es liess vorher den fixen Fuss (Record-/PTT-/Senden-
   Knopf) beim Zoomen ueberproportional mitwachsen. ``pan-x pan-y`` statt
   ``none``: Scrollen/Wischen bleibt erlaubt, nur Zoomen per Geste nicht --
   und statt ``manipulation`` (das Doppeltipp-Zoom zwar auch abschaltet,
   aber nichts ueber Pinch sagt und je Browser unterschiedlich ausgelegt
   wird). ``body`` wird auf der vereinten Seite beim Scopen zur Scope-
   Klasse selbst (``web_vereint.scope_css``), die Sperre bleibt also auf
   den Chat beschraenkt. */
body { background: #fbfaf8; color: #17181b; padding: .6rem .7rem 9rem;
       max-width: 44rem; margin: 0 auto; touch-action: pan-x pan-y; }
.verlauf { display: flex; flex-direction: column; gap: .55rem; }
.blase { padding: .55rem .7rem; border-radius: .8rem; max-width: 88%;
         font-size: 1.02rem; overflow-wrap: anywhere; }
.blase.bot { background: #fff; border: 1px solid #e0ddd6; align-self: flex-start;
             border-bottom-left-radius: .2rem; }
.blase.gruppe { background: #1f6f5c; color: #fff; align-self: flex-end;
                border-bottom-right-radius: .2rem; }
.blase.sprache { font-style: italic; opacity: .85; }
/* Karte t_ea994c7f: die EINE Transkriptblase eines Interviews -- kursiv
   wie eine Sprachnachricht, aber eine Bot-Blase (Rahmen, Seite). */
.blase.transkript { font-style: italic; }
.blase.system { background: transparent; border: none; color: #6b6f76;
                font-size: .88rem; padding: .25rem .2rem; max-width: 100%; }
/* UX-Knoepfe-Karte, Abschnitt 5: die Telefon-Organisationskarte je Phase. */
.karte { max-width: 100%; display: block; border-radius: .5rem; margin-bottom: .35rem; }
/* UX-Knoepfe-Karte, Abschnitt 1: Knoepfe sind kleine Abkuerzungs-Chips, keine
   vollbreiten Pflichtknoepfe -- die Hauptlast bleibt beim Eingabefeld. */
.leiste-label { font-size: .74rem; color: #9a9ea5; margin: .1rem 0 0;
                align-self: flex-start; }
.leiste { display: flex; flex-direction: row; flex-wrap: wrap; gap: .4rem;
          margin: 0 0 .3rem; align-self: flex-start; max-width: 94%; width: auto; }
.leiste button { font: inherit; font-size: .92rem; text-align: left;
                 padding: .45rem .85rem; border-radius: 999px;
                 border: 1px solid #1f6f5c; background: #fff; color: #1f6f5c;
                 min-height: 2.3rem; }
.leiste button:disabled { opacity: .45; }
/* Die Gruppe hat frei geschrieben oder gesprochen, statt einen Chip zu
   druecken: die Leiste bleibt sichtbar (eine Abkuerzung ist nicht falsch
   geworden), wird aber gedaempft -- rein optisch, der Server entscheidet
   weiterhin allein, wann ein Knopf wirklich verfaellt. */
.leiste.ueberholt button { opacity: .4; border-color: #c9c4b8; color: #8b8f97; }
.quittung { font-size: .82rem; opacity: .7; align-self: flex-start; }
.tippt { font-size: .85rem; opacity: .6; height: 1.2em; }
.fuss { position: fixed; left: 0; right: 0; bottom: 0; background: #fbfaf8;
        border-top: 1px solid #e0ddd6; padding: .5rem .7rem .8rem;
        display: flex; flex-direction: column; gap: .5rem; }
.zeile { display: flex; gap: .4rem; align-items: stretch; }
.zeile input { flex: 1; font: inherit; padding: .6rem .7rem; min-height: 2.9rem;
               border-radius: .7rem; border: 1px solid #c9c4b8; }
.zeile button { font: inherit; min-width: 3.4rem; min-height: 2.9rem;
                border-radius: .7rem; border: 0; background: #1f6f5c; color: #fff; }
#interview { font: inherit; font-weight: 600; min-height: 3.2rem; width: 100%;
             border-radius: .8rem; border: 1px solid #1f6f5c; background: #fff; }
#interview[data-laeuft="1"] { background: #a8201a; border-color: #a8201a;
                              color: #fff; min-height: 4rem; font-size: 1.15rem; }
#interview[data-laeuft="1"][data-pausiert="1"] { background: #8a8a8a;
                                                 border-color: #8a8a8a; }
/* Brainstorm mithören (Phase 4, nur Web): derselbe grosse Knopf wie
   #interview, Interview bleibt daneben erreichbar, aber kleiner/nachrangig
   (brief: "interview button stays reachable ... smaller/secondary"). */
#brainstorm { font: inherit; font-weight: 600; min-height: 3.2rem; width: 100%;
              border-radius: .8rem; border: 1px solid #1f6f5c; background: #fff;
              margin-bottom: .5rem; }
#brainstorm[data-laeuft="1"] { background: #a8201a; border-color: #a8201a;
                               color: #fff; min-height: 4rem; font-size: 1.15rem; }
#brainstorm[data-laeuft="1"][data-pausiert="1"] { background: #8a8a8a;
                                                  border-color: #8a8a8a; }
#interview.nebenknopf { font-weight: 400; min-height: 2.4rem; font-size: .9rem;
                        opacity: .8; }
.interview-aktionen { display: flex; gap: .5rem; margin-top: .4rem; }
.interview-aktionen[hidden] { display: none; }
.interview-aktionen button { flex: 1; min-height: 2.6rem; border-radius: .6rem;
                             font: inherit; border: 1px solid #1f6f5c;
                             background: #fff; color: #17181b; }
#ptt[hidden], #interview[hidden] { display: none; }
#interview:disabled { opacity: .55; }
/* PTT wird gehalten: kein Scrollen, kein Markieren, kein Kontextmenue unter
   dem Finger -- sonst bricht das Telefon den Druck ab oder blendet eine Lupe
   ein. */
#ptt { touch-action: none; user-select: none; -webkit-user-select: none;
       -webkit-touch-callout: none; }
#ptt[data-haelt="1"] { background: #a8201a; transform: scale(1.08); }
/* Die Anzeige-Box ueber dem Mikrofon-Knopf (Kanban-Karte Buehne/PTT,
   04.10.2026): Schloss-/Wegwisch-Hinweis, Timer, Pegel, Senden/Verwerfen im
   gesperrten Zustand. ANNAHME: Farben/Abstaende sind freie Gestaltung,
   konsistent mit dem Rest dieser Seite -- nur IDs/Zustaende sind Vorgabe. */
#ptt-anzeige { display: flex; align-items: center; gap: .5rem;
               font-size: .88rem; padding: .35rem .6rem; border-radius: .6rem;
               background: #eee9df; margin-bottom: -.1rem; }
#ptt-anzeige[hidden] { display: none; }
#ptt-anzeige[data-gesperrt="1"] { background: #fde8c8; }
/* "wird gleich abgebrochen", ab der Haelfte der Wegwischstrecke. */
#ptt-anzeige[data-wird-verworfen="1"] { opacity: .45; }
#ptt-schloss { opacity: .85; }
#ptt-wisch-hinweis { opacity: .6; flex: 1; white-space: nowrap; }
#ptt-zeit { font-variant-numeric: tabular-nums; min-width: 2.6rem; text-align: center; }
#ptt-anzeige .pegel { flex: 1; min-width: 3rem; margin: 0; }
#ptt-hinweistext { flex: 1; opacity: .9; }
#ptt-senden, #ptt-verwerfen { font: inherit; border-radius: .6rem; border: 0;
                              min-height: 2.2rem; }
#ptt-senden { background: #1f6f5c; color: #fff; padding: 0 .8rem; white-space: nowrap; }
#ptt-verwerfen { background: transparent; color: #a8201a;
                 border: 1px solid #a8201a; min-width: 2.2rem; }
.fehler { font-size: .9rem; color: #a8201a; text-align: center; }
.fehler[hidden] { display: none; }
.angehalten { display: flex; flex-direction: column; gap: .35rem; font-size: .92rem;
              border: 1px solid #a8201a; border-radius: .7rem; padding: .5rem .6rem; }
.angehalten[hidden], .angehalten button[hidden] { display: none; }
.angehalten button { font: inherit; min-height: 2.9rem; border-radius: .7rem;
                     border: 1px solid #1f6f5c; background: #fff; color: #17181b; }
.pegel { position: relative; height: .45rem; border-radius: .3rem;
         background: #e0ddd6; overflow: visible; }
/* Grau unterhalb, Gruen sobald der aktuelle Pegel die VAD-Schwelle
   uebersteigt (.ueber-schwelle, von pegelAn gesetzt) -- derselbe Rahmen wie
   .kalibrierung-balken/.kalibrierung-marke. */
.pegel span { display: block; height: 100%; width: 0; border-radius: .3rem;
              background: #6b6f76; }
.pegel.ueber-schwelle span { background: #1f6f5c; }
.pegel-schwelle { position: absolute; top: -.2rem; bottom: -.2rem; width: 2px;
                  background: #17181b; left: 0; }
.uhr { font-variant-numeric: tabular-nums; font-size: 1.3rem; text-align: center; }
.warteschlange { font-size: .82rem; opacity: .7; text-align: center; }
.kalibrierung { display: flex; flex-direction: column; gap: .5rem; font-size: .92rem;
                border: 1px solid #1f6f5c; border-radius: .7rem; padding: .6rem .7rem; }
.kalibrierung[hidden] { display: none; }
.kalibrierung-knoepfe { display: flex; flex-direction: column; gap: .4rem; }
.kalibrierung button { font: inherit; min-height: 2.9rem; border-radius: .7rem;
                       border: 1px solid #1f6f5c; background: #fff; color: #17181b; }
#kalibrierung-skip { border-color: #e0ddd6; color: #6b6f76; min-height: 2.3rem; }
#kalibrierung-neu { font: inherit; min-height: 2.1rem; border-radius: .7rem;
                    border: 1px solid #e0ddd6; background: #fff; color: #6b6f76; }
#kalibrierung-neu[hidden] { display: none; }
.kalibrierung-balken { position: relative; height: .6rem; border-radius: .35rem;
                       background: #e0ddd6; overflow: visible; }
.kalibrierung-balken[hidden] { display: none; }
.kalibrierung-balken span { display: block; height: 100%; width: 0; border-radius: .35rem;
                            background: #a8201a; }
.kalibrierung-marke { position: absolute; top: -.2rem; bottom: -.2rem; width: 2px;
                      background: #17181b; left: 0; }
.kalibrierung-erinnerung { font-size: .85rem; text-align: center; color: #1f6f5c; }
.kalibrierung-erinnerung[hidden] { display: none; }
.mitlauf-hinweis { font-size: .85rem; text-align: center; color: #1f6f5c; }
.mitlauf-hinweis[hidden] { display: none; }
/* Bild-Overlay-Karte: die Telefon-Organisationskarte (``.karte``) gross und
   zoombar. ``inset: 0`` statt ``100vw``/``100vh`` -- ein fixes Element
   braucht dafuer keine viewport-relative Einheit. ``touch-action:
   pinch-zoom`` auf Huelle UND Bild hebt die Sperre am ``body`` fuer dieses
   Element gezielt wieder auf. */
.bild-overlay { position: fixed; inset: 0; z-index: 9999;
                background: rgba(0, 0, 0, .9); display: flex;
                align-items: center; justify-content: center;
                touch-action: pinch-zoom; }
.bild-overlay[hidden] { display: none; }
.bild-overlay img { max-width: 100%; max-height: 100%; object-fit: contain;
                     touch-action: pinch-zoom; }
.bild-overlay button { position: absolute; top: .6rem; right: .6rem;
                        min-width: 2.75rem; min-height: 2.75rem;
                        border-radius: 999px; border: 0;
                        background: rgba(255, 255, 255, .15); color: #fff;
                        font-size: 1.3rem; }
@media (prefers-color-scheme: dark) {
  body { background: #14161a; color: #e7e9ec; }
  .blase.bot { background: #1d2026; border-color: #2c313a; }
  .fuss { background: #14161a; border-color: #2c313a; }
  .zeile input { background: #1d2026; color: #e7e9ec; border-color: #2c313a; }
  .leiste button { background: #1d2026; color: #6fcfb6; border-color: #2c6a58; }
  .leiste-label { color: #7d8290; }
  .interview-aktionen button { background: #1d2026; color: #e7e9ec; }
  .kalibrierung button, #kalibrierung-neu { background: #1d2026; color: #e7e9ec;
                                            border-color: #2c6a58; }
}
"""

#: Polltakt der Chatansicht (Millisekunden). Zwei Sekunden, solange der Tab
#: sichtbar ist -- schnell genug, dass eine Antwort nicht "haengt" wirkt, und
#: langsam genug, dass drei Gruppen mit je zwei Telefonen den stdlib-Server
#: nicht beschaeftigen. Im Hintergrund seltener (ein Telefon in der Tasche
#: muss nichts abholen).
POLL_MS = 2000
POLL_MS_HINTERGRUND = 10000

#: Kuerzer gedrueckt = nichts gesendet (Birk, 30.09.2026, Punkt 2). Ein
#: versehentlicher Tipper auf das Mikrofon soll keine leere Aufnahme in den
#: Chat legen -- und keinen Gespraechszug ausloesen.
PTT_MIN_MS = 500

#: Obergrenze fuer einen PTT-Druck (Kanban-Karte Buehne/PTT): laeuft die
#: Aufnahme laenger als 90 Sekunden, stoppt und sendet sie automatisch --
#: PTT ist fuer kurze Sprachnavigation gedacht, nicht fuer ein Interview.
PTT_MAX_MS = 90_000

#: Kanban-Karte Buehne/PTT (04.10.2026, Telegram-Vorbild): nach oben
#: geschoben (``dy`` seit ``pointerdown``, negativ), ab diesem Betrag in
#: CSS-Pixeln sperrt der Druck -- die Aufnahme laeuft danach ohne gehaltenen
#: Finger weiter, bis "Senden"/"Verwerfen" oder ``PTT_MAX_MS``.
PTT_LOCK_PX = 60

#: Nach links geschoben (``dx``, negativ), ab diesem Betrag in CSS-Pixeln
#: bricht der Druck sofort ab -- 0 POST, wie ``verwirfPtt()``.
PTT_CANCEL_PX = 80

#: Wartezeiten zwischen zwei Versuchen eines Uploads (Millisekunden), der
#: letzte Wert ist der Deckel. **Ohne Hoechstzahl an Versuchen**
#: (Review-Befund 3): bei Netzfehler oder 5xx wird wiederholt, bis es
#: klappt -- ein Netzaussetzer im Probenraum darf ein Segment nicht kosten,
#: und ein verworfenes Segment ist ein Loch mitten im Interview. Zusaetzlich
#: loest das ``online``-Ereignis des Browsers sofort einen Versuch aus.
#: Verworfen wird nur, was der Server endgueltig ablehnt (4xx), und das
#: sichtbar.
UPLOAD_WARTEN_MS = (1000, 3000, 8000)

_TEXT_WARTE_EINS = "Ein Stück wird hochgeladen …"
_TEXT_WARTE_MEHR = "{n} Stücke werden hochgeladen …"
_TEXT_WARTE_MODUS = "Aufnahme läuft — {n} Stück(e) warten, bis der Bot das Interview angelegt hat."
_TEXT_WARTE_NETZ = "Keine Verbindung — {n} offen, ich versuche es weiter …"
_TEXT_FEHLER_NETZ = "Keine Verbindung — das ist nicht angekommen."
_TEXT_FEHLER_MIKRO = "Ohne Mikrofon geht das nicht — bitte den Zugriff erlauben."
_TEXT_VERLASSEN = "Es wird noch aufgenommen oder hochgeladen."
_TEXT_UHR = "● {zeit}"
#: Re-Review H: der Interviewmodus ist serverseitig zu Ende, waehrend dieses
#: Telefon noch aufnahm oder Segmente offen hatte. Ohne Modus waere ein
#: Segment (seit dem Pausen-Schnitt bis zu IT_WEB_VAD_MAX_MS, Vorgabe 90 s --
#: damit laenger als ``aufnahme.HINWEIS_AB_S``, 60 s) ein Gespraechsbeitrag
#: -- Gespraechszug, Erkenner und Journal ueber Interviewmaterial. Das
#: ueberschreiten von HINWEIS_AB_S bleibt hier folgenlos, weil die
#: "war das ein Interview?"-Rueckfrage auf dem Web-Kanal ohnehin nie laeuft
#: (``aufnahme.ist_web_gruppe``-Ausnahme) -- die eigentliche Gefahr bleibt
#: dieselbe wie vorher: Interviewinhalt als Gespraechsbeitrag. Deshalb wird
#: nichts still nachgeschickt, die Gruppe entscheidet.
_TEXT_MODUS_WEG = (
    "Das Interview wurde beendet, die Aufnahme ist gestoppt. "
    "{n} Stück(e) sind noch nicht angekommen."
)
_TEXT_MODUS_WEG_LEER = "Das Interview wurde beendet, die Aufnahme ist gestoppt."
_TEXT_REST_NACHREICHEN = "Rest als Interview nachreichen"
_TEXT_REST_VERWERFEN = "Rest verwerfen"
#: Ein anderes Telefon hat inzwischen ein Interview gestartet: das
#: abschliessende /fertig des Nachreichens wuerde es beenden.
_TEXT_NACHREICHEN_SPAETER = (
    "Gerade läuft ein anderes Interview — nachreichen geht, sobald es beendet ist."
)

#: Task 4 (Kanban-Karte Mithoeren SICHER, 03.10.2026): einmal je Sitzung,
#: direkt nachdem das erste Segment fertig ist (``sitzung.hinweisGezeigt``
#: in ``neuesSegment()``s ``onstop`` -- kein ``localStorage``, reines
#: Sitzungsfeld, eine neue Sitzung zeigt ihn wieder). Eigenstaendig von
#: Task 2s "Handy herumreichen"-Erinnerung (anderer Ausloeser, anderer
#: Merkposten) -- nicht zusammenlegen.
_TEXT_MITLAUF_HINWEIS = (
    "Schaut den Mitschnitt im Chat nach — fehlen Worte, haltet das Handy "
    "näher ran."
)

# -- Pegel-Kalibrierung (Task 2, Kanban-Karte Mithoeren SICHER/             --
# -- Kalibrierung, 03.10.2026): Birks Korrektur gilt woertlich -- NICHTS in --
# -- diesem Ablauf startet von selbst, jeder Schritt wartet auf einen       --
# -- ausdruecklichen Knopfdruck (die eine Ausnahme ist der automatische     --
# -- Rueckfragen-Knopf nach 30s Stille in Schritt 4, der selbst ein Knopf   --
# -- ist). Wortlaut 1:1 aus dem Kartentext (Englisch bindend, Deutsch ist   --
# -- die treue Uebersetzung). --------------------------------------------

_TEXT_KALIBRIERUNG_ANKUENDIGUNG = (
    "Legt dieses Handy in die Mitte des Tisches, dort wo es während des "
    "Gesprächs bleiben wird. Setzt euch so, wie ihr beim Reden sitzen "
    "werdet — lehnt euch nicht vor und sprecht nicht ins Handy hinein. Wir "
    "testen es genauso wie die echte Situation. Wenn du den Knopf unten "
    "drückst, seid bitte 5 Sekunden lang vollkommen still — danach sagt "
    "eine*r von euch einen Satz in normaler Lautstärke."
)
_TEXT_KALIBRIERUNG_START_KNOPF = "Messung starten"
_TEXT_KALIBRIERUNG_STILLE = "Ruhe für noch {s} Sekunden — wir messen den Raum …"
_TEXT_KALIBRIERUNG_SPRECHEN_ANKUENDIGUNG = (
    "Stille gemessen. Jetzt sagt eine*r von euch einen Satz in normaler "
    "Lautstärke — am besten die Person, die am weitesten vom Handy entfernt "
    "sitzt. Sprich von deinem Platz aus, in normaler Lautstärke, nicht ins "
    "Handy hinein. Drück den Knopf, dann fang an zu sprechen."
)
_TEXT_KALIBRIERUNG_SPRECHEN_KNOPF = "Sprechen starten"
_TEXT_KALIBRIERUNG_HOEREN = "Ich höre zu … fang an, wann du bereit bist."
_TEXT_KALIBRIERUNG_NICHTS_GEHOERT = "Wir haben nichts gehört — nochmal versuchen?"
_TEXT_KALIBRIERUNG_MESSEN_KNOPF = "Nochmal messen"
_TEXT_KALIBRIERUNG_ZU_LEISE = "Das war zu leise, um zuverlässig verstanden zu werden."
_TEXT_KALIBRIERUNG_ZU_LEISE_1 = (
    "Stellt das Handy näher in die Mitte und sprecht etwas lauter — dann "
    "versucht es nochmal."
)
_TEXT_KALIBRIERUNG_ZU_LEISE_2 = (
    "Der Raum ist zu groß oder zu laut für ein Handy in der Mitte. Gebt das "
    "Handy herum: wer spricht, hält es (oder legt es neben sich). Dann "
    "versucht es nochmal."
)
_TEXT_KALIBRIERUNG_NOCHMAL_KNOPF = "Nochmal versuchen"
_TEXT_KALIBRIERUNG_WEITER_TROTZDEM = "Trotzdem weiter"
_TEXT_KALIBRIERUNG_TRANSKRIBIERT_WARTEN = "Der Testsatz wird abgetippt …"
_TEXT_KALIBRIERUNG_BESTAETIGUNG = "Wir haben gehört: „{transkript}“. Stimmt das?"
_TEXT_KALIBRIERUNG_JA_KNOPF = "Ja, stimmt"
_TEXT_KALIBRIERUNG_NEIN_KNOPF = "Nein, nochmal"
_TEXT_KALIBRIERUNG_FLOOR_HINWEIS = (
    "Der Raum ist laut, oder das Handy ist weit weg — stellt es näher an die "
    "Sprechenden."
)
_TEXT_KALIBRIERUNG_ERFOLG = "Raum gemessen ✓ — ihr seid bereit."
_TEXT_KALIBRIERUNG_SKIP_KNOPF = "Überspringen"
_TEXT_KALIBRIERUNG_BALKEN_LABEL = "Deine Stimme im Vergleich zum Raum"
_TEXT_KALIBRIERUNG_HERUMREICHEN_ERINNERUNG = (
    "Denkt daran: Gebt das Handy an die Person weiter, die spricht."
)

#: Die Texte, die das JavaScript selbst setzt. Sie stehen als Konstanten in
#: diesem Modul (dieselben, die der Server fuer seine Seite benutzt) und
#: kommen als EIN JSON-Objekt ins Skript -- kein UI-Satz als Literal im JS.
_JS_TEXTE = {
    "tippt": _TEXT_TIPPT,
    "sprache": _TEXT_SPRACHE,
    "sprache_laeuft": _TEXT_SPRACHE_LAEUFT,
    "sprache_text": _TEXT_SPRACHE_ABGETIPPT,
    "datei": _TEXT_DATEI,
    "interview_an": _TEXT_INTERVIEW_AN,
    "interview_aus": _TEXT_INTERVIEW_AUS,
    "interview_pause": _TEXT_INTERVIEW_PAUSE,
    "interview_weiter": _TEXT_INTERVIEW_WEITER,
    "interview_laeuft": _TEXT_INTERVIEW_LAEUFT,
    "interview_pausiert": _TEXT_INTERVIEW_PAUSIERT,
    "brainstorm_an": _TEXT_BRAINSTORM_AN,
    "brainstorm_laeuft": _TEXT_BRAINSTORM_LAEUFT,
    "diskussion_an": _TEXT_DISKUSSION_AN,
    "diskussion_laeuft": _TEXT_DISKUSSION_LAEUFT,
    "warte_eins": _TEXT_WARTE_EINS,
    "warte_mehr": _TEXT_WARTE_MEHR,
    "warte_modus": _TEXT_WARTE_MODUS,
    "warte_netz": _TEXT_WARTE_NETZ,
    "fehler_netz": _TEXT_FEHLER_NETZ,
    "fehler_mikro": _TEXT_FEHLER_MIKRO,
    "verlassen": _TEXT_VERLASSEN,
    "uhr": _TEXT_UHR,
    "modus_weg": _TEXT_MODUS_WEG,
    "modus_weg_leer": _TEXT_MODUS_WEG_LEER,
    "nachreichen_spaeter": _TEXT_NACHREICHEN_SPAETER,
    "mitlauf_hinweis": _TEXT_MITLAUF_HINWEIS,
    "ptt_hinweis": _TEXT_PTT_HINWEIS,
    "abkuerzung": _TEXT_ABKUERZUNG,
    "kal_ankuendigung": _TEXT_KALIBRIERUNG_ANKUENDIGUNG,
    "kal_start_knopf": _TEXT_KALIBRIERUNG_START_KNOPF,
    "kal_stille": _TEXT_KALIBRIERUNG_STILLE,
    "kal_sprechen_ankuendigung": _TEXT_KALIBRIERUNG_SPRECHEN_ANKUENDIGUNG,
    "kal_sprechen_knopf": _TEXT_KALIBRIERUNG_SPRECHEN_KNOPF,
    "kal_hoeren": _TEXT_KALIBRIERUNG_HOEREN,
    "kal_nichts_gehoert": _TEXT_KALIBRIERUNG_NICHTS_GEHOERT,
    "kal_messen_knopf": _TEXT_KALIBRIERUNG_MESSEN_KNOPF,
    "kal_zu_leise": _TEXT_KALIBRIERUNG_ZU_LEISE,
    "kal_zu_leise_1": _TEXT_KALIBRIERUNG_ZU_LEISE_1,
    "kal_zu_leise_2": _TEXT_KALIBRIERUNG_ZU_LEISE_2,
    "kal_nochmal_knopf": _TEXT_KALIBRIERUNG_NOCHMAL_KNOPF,
    "kal_weiter_trotzdem": _TEXT_KALIBRIERUNG_WEITER_TROTZDEM,
    "kal_transkribiert_warten": _TEXT_KALIBRIERUNG_TRANSKRIBIERT_WARTEN,
    "kal_bestaetigung": _TEXT_KALIBRIERUNG_BESTAETIGUNG,
    "kal_ja_knopf": _TEXT_KALIBRIERUNG_JA_KNOPF,
    "kal_nein_knopf": _TEXT_KALIBRIERUNG_NEIN_KNOPF,
    "kal_floor_hinweis": _TEXT_KALIBRIERUNG_FLOOR_HINWEIS,
    "kal_erfolg": _TEXT_KALIBRIERUNG_ERFOLG,
    "kal_skip_knopf": _TEXT_KALIBRIERUNG_SKIP_KNOPF,
    "kal_balken_label": _TEXT_KALIBRIERUNG_BALKEN_LABEL,
    "kal_herumreichen_erinnerung": _TEXT_KALIBRIERUNG_HERUMREICHEN_ERINNERUNG,
}


#: Das Chat-JavaScript. Vanilla, kein Build, kein Framework -- wie die
#: bestehende Seite (``_BEARBEITEN_JS``). Faellt es aus, bleibt der Verlauf
#: lesbar (serverseitig gerendert); nur Senden und Aufnehmen gehen nicht.
#:
#: Die Zahlen und Texte kommen als Platzhalter herein, damit sie an genau
#: einer Stelle stehen: in den Python-Konstanten darueber.
#:
#: **Testbarkeit (Aufgabe 13):** ``navigator.mediaDevices.getUserMedia`` und
#: ``window.MediaRecorder`` werden erst beim Gebrauch nachgeschlagen, nie beim
#: Laden gemerkt -- ein Browsertest ersetzt beide per ``add_init_script``.
#: Die Segmentlaenge steht in ``data-segment-ms`` (``IT_WEB_SEGMENT_MS``).
#:
#: **Zwei Zustaende fuer den Interviewmodus** (Review-Befund 4): ``servermodus``
#: ist, was der Poll meldet; ``aufnahme`` und ``wechsel`` sind, was dieses
#: Telefon gerade tut. Solange ein Wechsel unterwegs ist, schaltet der Poll
#: weder den Knopf noch PTT um -- sonst saehe ein zweiter Tipp waehrend der
#: Bot ``/interview`` noch nicht verarbeitet hat "aus" und startete einen
#: zweiten Recorder.
#:
#: **Eine Warteschlange fuer Befehle UND Segmente:** ``/interview``, alle
#: Segmente und ``/fertig`` laufen nacheinander durch dieselbe Schlange. Damit
#: ist die Reihenfolge, die der Bot sieht, die Reihenfolge, in der hier
#: aufgenommen wurde -- ``/fertig`` geht erst raus, wenn alle Segmente davor
#: angekommen sind (Review-Befund 1).
_CHAT_JS = """
(function () {
  var POLL_MS = __POLL_MS__;
  var POLL_MS_HINTERGRUND = __POLL_MS_HINTERGRUND__;
  var PTT_MIN_MS = __PTT_MIN_MS__;
  var PTT_MAX_MS = __PTT_MAX_MS__;
  var PTT_LOCK_PX = __PTT_LOCK_PX__;
  var PTT_CANCEL_PX = __PTT_CANCEL_PX__;
  var UPLOAD_WARTEN_MS = __UPLOAD_WARTEN_MS__;
  var TEXT = __TEXTE__;
  // Padua Brainstorm, 03.10.2026: wie nah am unteren Rand noch als "dort"
  // zaehlt -- ein Pixel exakt waere auf jedem Geraet eine andere Zahl.
  var UNTEN_TOLERANZ_PX = 48;

  // -- Pegel-Kalibrierung (Task 2, Kanban-Karte Mithoeren SICHER/           --
  // -- Kalibrierung, 03.10.2026): literale Konstanten aus der Karte, kein   --
  // -- Env-Override gewuenscht (anders als IT_WEB_VAD_KALIBRIERUNG, das die --
  // -- Karte als EINZIGEN Umgebungswert nennt). ------------------------------
  var KAL_STILLE_MS = 5000;
  var KAL_WARTE_MAX_MS = 30000;
  var KAL_SPRACH_MS = 4000;
  var KAL_SPRACH_FENSTER_MS = 15000;
  var KAL_SCHWELLE_FALLBACK = 0.006;
  var KAL_SCHWELLE_ABS_MIN = 0.004;
  var KAL_SCHWELLE_ABS_MAX = 0.08;
  var KAL_LS_BODEN = 'vad_boden_mess';
  var KAL_LS_REDE = 'vad_rede_mess';
  var KAL_LS_SCHWELLE = 'vad_schwelle';

  var verlauf = document.getElementById('verlauf');
  var fuss = document.getElementById('fuss');
  if (!verlauf || !fuss) { return; }
  var eingabe = document.getElementById('eingabe');
  var uhrFeld = document.getElementById('uhr');
  var pegelFeld = document.getElementById('pegel');
  var pegelBalken = pegelFeld ? pegelFeld.querySelector('span') : null;
  var pegelSchwelle = pegelFeld ? pegelFeld.querySelector('.pegel-schwelle') : null;
  var warteFeld = document.getElementById('warteschlange');
  var fehlerFeld = document.getElementById('fehler');
  // Task 4 (Kanban-Karte Mithoeren SICHER): der einmalige "Mitschnitt
  // pruefen"-Hinweis -- eigenstaendig von kalErinnerungFeld unten.
  var mitlaufHinweisFeld = document.getElementById('mitlauf-hinweis');
  var tipptFeld = document.getElementById('tippt');
  var interviewKnopf = document.getElementById('interview');
  var interviewAktionenFeld = document.getElementById('interview-aktionen');
  var interviewPauseKnopf = document.getElementById('interview-pause');
  var interviewBeendenKnopf = document.getElementById('interview-beenden');
  var pttKnopf = document.getElementById('ptt');
  // Die Anzeige-Box ueber dem Mikrofon-Knopf (Kanban-Karte Buehne/PTT,
  // 04.10.2026): Schloss-/Wegwisch-Hinweis, Timer, Pegel, Kurztipp-Hinweis,
  // Senden/Verwerfen im gesperrten Zustand.
  var pttAnzeige = document.getElementById('ptt-anzeige');
  var pttSchloss = document.getElementById('ptt-schloss');
  var pttWischHinweis = document.getElementById('ptt-wisch-hinweis');
  var pttZeit = document.getElementById('ptt-zeit');
  var pttPegelFeld = document.getElementById('ptt-pegel');
  var pttPegelBalken = pttPegelFeld ? pttPegelFeld.querySelector('span') : null;
  var pttHinweistext = document.getElementById('ptt-hinweistext');
  var pttSendeKnopf = document.getElementById('ptt-senden');
  var pttVerwerfenKnopf = document.getElementById('ptt-verwerfen');
  // Brainstorm mithören (Phase 4, nur Web) -- die Elemente stehen seit
  // Task 2 (Kanban-Karte Buehne/PTT) IMMER im Markup, ``hidden`` folgt der
  // Phase per Poll (wie beim Interview-Knopf), nicht mehr ihrer Existenz.
  var brainstormKnopf = document.getElementById('brainstorm');
  var brainstormAktionenFeld = document.getElementById('brainstorm-aktionen');
  var brainstormPauseKnopf = document.getElementById('brainstorm-pause');
  var brainstormBeendenKnopf = document.getElementById('brainstorm-beenden');
  // Hintergrund-Mithoeren Phase 1 (Padua Phase 1+2 Umbau, 03.10.2026, Task 6):
  // derselbe Aufbau wie Brainstorm (Task 2/5) -- die Elemente stehen seit
  // Task 5 IMMER im Markup, ``hidden`` folgt der Phase per Poll.
  var diskussionKnopf = document.getElementById('diskussion');
  var diskussionAktionenFeld = document.getElementById('diskussion-aktionen');
  var diskussionPauseKnopf = document.getElementById('diskussion-pause');
  var diskussionBeendenKnopf = document.getElementById('diskussion-beenden');
  var angehaltenFeld = document.getElementById('angehalten');
  var angehaltenText = document.getElementById('angehalten-text');
  var nachreichenKnopf = document.getElementById('nachreichen');
  var verwerfenKnopf = document.getElementById('verwerfen');
  // Bild-Overlay-Karte (04.10.2026): die Telefon-Organisationskarte
  // (``.karte``) gross und per Pinch-Zoom vergroesserbar.
  var bildOverlay = document.getElementById('bild-overlay');
  var bildOverlayImg = document.getElementById('bild-overlay-img');
  var bildOverlaySchliessen = document.getElementById('bild-overlay-schliessen');
  var SEGMENT_MS = parseInt(fuss.dataset.segmentMs, 10) || 45000;

  // -- Pegel-Kalibrierung: die Bedienelemente --------------------------------
  var kalFeld = document.getElementById('kalibrierung');
  var kalText = document.getElementById('kalibrierung-text');
  var kalBalkenFeld = document.getElementById('kalibrierung-balken');
  var kalBalkenBalken = kalBalkenFeld ? kalBalkenFeld.querySelector('span') : null;
  var kalBalkenMarke = kalBalkenFeld ? kalBalkenFeld.querySelector('.kalibrierung-marke') : null;
  var kalStartKnopf = document.getElementById('kalibrierung-start');
  var kalSprechenKnopf = document.getElementById('kalibrierung-sprechen');
  var kalNochmalHoerenKnopf = document.getElementById('kalibrierung-nochmal-hoeren');
  var kalVersuchKnopf = document.getElementById('kalibrierung-versuch');
  var kalWeiterTrotzdemKnopf = document.getElementById('kalibrierung-weiter-trotzdem');
  var kalJaKnopf = document.getElementById('kalibrierung-ja');
  var kalNeinKnopf = document.getElementById('kalibrierung-nein');
  var kalSkipKnopf = document.getElementById('kalibrierung-skip');
  var kalNeuKnopf = document.getElementById('kalibrierung-neu');
  var kalErinnerungFeld = document.getElementById('kalibrierung-erinnerung');

  // Die Basis aller Endpunkte. Auf der vereinten Seite (/g/<token>, Karte W)
  // steht sie explizit als data-basis am #fuss ("<token>/"), weil der
  // serverseitig gerenderte Dateilink (_blase_html) dieselbe Basis braucht
  // und dort kein location.pathname zur Verfuegung steht. Ohne data-basis
  // (die Chat-Einzelseite /g/<token>/chat) bleibt die bisherige, absolute
  // Herleitung aus dem Pfad bestehen -- robust auch bei einem
  // Schraegstrich am Ende der Adresse (Review-Befund 12).
  var BASIS = fuss.dataset.basis
    || (location.pathname.replace(/\\/+$/, '').replace(/\\/chat$/, '') + '/');
  function weg(pfad) { return BASIS + pfad; }

  var zustand = {
    letzte: parseInt(verlauf.dataset.letzte, 10) || 0,
    aenderung: parseInt(verlauf.dataset.aenderung, 10) || 0,
    // Phasenscroll-Karte (04.10.2026): 0 heisst "keine Phase bekannt" --
    // echte Phasen sind 1..7 und nie 0.
    phase: parseInt(verlauf.dataset.phase, 10) || 0,
    servermodus: fuss.dataset.interview === '1',
    knopfErlaubt: !interviewKnopf.hidden,   // Padua Hotfix B6: Phase 3 oder Modus
    brainstormErlaubt: !brainstormKnopf.hidden,   // Task 2: Phase 4
    diskussionErlaubt: !diskussionKnopf.hidden,   // Task 6: Phase 1
    aufnahme: null,     // die laufende Interview-Aufnahme dieses Telefons
    wechsel: null,      // {ziel, gesendet}: ein Moduswechsel, den der Poll noch nicht zeigt
    warteschlange: [],  // Befehle und Segmente, der Reihe nach
    laeuft: false,      // ist der erste Auftrag gerade unterwegs?
    netzFehler: 0,      // Fehlversuche in Folge (Backoff)
    nachholTakt: null,
    uhrTakt: null,
    fehlerTakt: null,
    ptt: null,          // der laufende PTT-Druck, je Druck ein eigenes Objekt
    angehalten: [],     // Aufnahmen, deren Modus ohne dieses Telefon endete (Re-Review H)
    // Task 2 (Kanban-Karte Mithoeren SICHER/Kalibrierung, 03.10.2026): der
    // Stand des zuletzt eingereichten Kalibrierungs-Testsatzes (vom Poll,
    // {message_id, status, transkript} oder null) und der gruppenweite
    // Hinweis-Modus ("herumreichen" oder null).
    kalibrierung: null,
    kalibrierungModus: fuss.dataset.kalibrierungModus || null
  };

  function nonce() {
    var feld = document.getElementById('nonce');
    return feld ? feld.value : '';
  }

  function entferne(element) {
    if (element && element.parentNode) { element.parentNode.removeChild(element); }
  }

  function meldeFehler(satz) {
    if (!fehlerFeld) { return; }
    fehlerFeld.textContent = satz || TEXT.fehler_netz;
    fehlerFeld.hidden = false;
    if (zustand.fehlerTakt) { clearTimeout(zustand.fehlerTakt); }
    zustand.fehlerTakt = setTimeout(function () {
      fehlerFeld.hidden = true;
      fehlerFeld.textContent = '';
    }, 8000);
  }

  // Der Server schickt bei 4xx einen Satz als Klartext (_TEXT_FEHLER_*).
  function fehlerAus(r) {
    return r.text().then(function (satz) {
      meldeFehler((satz || '').trim() || TEXT.fehler_netz);
    }, function () { meldeFehler(TEXT.fehler_netz); });
  }

  // -- Verlauf -------------------------------------------------------------

  function escape(text) {
    var hilf = document.createElement('div');
    hilf.textContent = text == null ? '' : String(text);
    return hilf.innerHTML;
  }

  function minuten(s) {
    return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2);
  }

  function bildVon(n) {
    // UX-Knoepfe-Karte, Abschnitt 5: dieselbe URL wie auf der Server-Seite
    // (web_chat._bild_html) -- ``weg()`` rechnet BASIS schon mit ein.
    if (!n.bild) { return ''; }
    return '<img src="' + weg('static/handys/' + n.bild) + '" alt="' +
           escape(n.text || '') + '" loading="lazy" class="karte">';
  }

  // Bild-Overlay-Karte (04.10.2026): die Telefon-Organisationskarte
  // (``.karte``, aus ``bildVon`` oben) vollbildig mit Pinch-Zoom. Ein
  // delegierter Klick-Listener auf ``verlauf`` (statt je Bild einzeln) --
  // Bilder kommen sowohl serverseitig vorgerendert als auch spaeter per
  // ``blase()``/``ersetze()`` dynamisch dazu.
  var ueberlagerungOffen = false;
  function oeffneBildOverlay(src, alt) {
    if (!bildOverlay || !bildOverlayImg) { return; }
    bildOverlayImg.src = src;
    bildOverlayImg.alt = alt || '';
    bildOverlay.hidden = false;
    ueberlagerungOffen = true;
    history.pushState({ bildUeberlagerung: true }, '');
  }
  function schliesseBildOverlay() {
    if (!ueberlagerungOffen || !bildOverlay) { return; }
    bildOverlay.hidden = true;
    bildOverlayImg.src = '';
    ueberlagerungOffen = false;
    if (history.state && history.state.bildUeberlagerung) { history.back(); }
  }
  if (bildOverlay) {
    verlauf.addEventListener('click', function (ev) {
      var img = ev.target.closest ? ev.target.closest('img.karte') : null;
      if (img) { oeffneBildOverlay(img.src, img.alt); }
    });
    // Tippen auf den dunklen Hintergrund schliesst -- auf das Bild selbst
    // NICHT, sonst stoert ein Tipp mitten in einer Pinch-Geste.
    bildOverlay.addEventListener('click', function (ev) {
      if (ev.target === bildOverlay) { schliesseBildOverlay(); }
    });
    if (bildOverlaySchliessen) {
      bildOverlaySchliessen.addEventListener('click', schliesseBildOverlay);
    }
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') { schliesseBildOverlay(); }
    });
    // Zurueck-Geste/-Taste: schliesst das Overlay, OHNE erneut
    // ``history.back()`` aufzurufen -- der Browser ist schon zurueck.
    window.addEventListener('popstate', function () {
      if (!ueberlagerungOffen) { return; }
      bildOverlay.hidden = true;
      bildOverlayImg.src = '';
      ueberlagerungOffen = false;
    });
  }

  function inhaltVon(n) {
    return bildVon(n) + textVon(n);
  }

  function textVon(n) {
    // Der Server hat schon gefiltert (sichere_html) -- ein Filter im Browser
    // laege auf der Seite, die er schuetzen soll.
    if (n.typ === 'sprache') {
      // Padua Hotfix B7: das Transkript als Text (escape, nie n.html), sonst
      // der Platzhalter, solange abgetippt wird.
      var dauer = minuten(n.dauer || 0);
      if (n.text) {
        return escape(TEXT.sprache_text.replace('{dauer}', dauer)
                      .replace('{text}', function () { return n.text; }));
      }
      return escape((n.abgetippt === false ? TEXT.sprache_laeuft : TEXT.sprache)
                    .replace('{dauer}', dauer));
    }
    if (n.typ === 'datei') {
      var link = '<a href="' + weg(`chat/datei/${n.id}`) + '">' +
                 escape(TEXT.datei.replace('{name}', n.dateiname || 'datei')) +
                 '</a>';
      return n.html ? n.html + '<br>' + link : link;
    }
    return n.html || '';
  }

  function klasseVon(n) {
    if (n.typ === 'sprache' || n.typ === 'datei' || n.typ === 'system' ||
        n.typ === 'transkript') {
      return n.typ;
    }
    return 'text';
  }

  // UX-Knoepfe-Karte, Abschnitt 1: ein gedaempftes Label VOR der Chip-Leiste
  // -- "Abkuerzung:" -- damit niemand den Eindruck hat, ein Knopf sei
  // Pflicht statt Vorschlag.
  function baueLabel(n) {
    var label = document.createElement('div');
    label.className = 'leiste-label';
    label.dataset.message = n.id;
    label.textContent = TEXT.abkuerzung;
    return label;
  }

  function baueLeiste(n) {
    if (!n.knoepfe || !n.knoepfe.length) { return null; }
    var leiste = document.createElement('div');
    leiste.className = 'leiste';
    leiste.dataset.message = n.id;
    n.knoepfe.forEach(function (paar) {
      var knopf = document.createElement('button');
      knopf.type = 'button';
      knopf.textContent = paar[0];
      knopf.dataset.message = n.id;
      knopf.dataset.daten = paar[1];
      leiste.appendChild(knopf);
    });
    return leiste;
  }

  // UX-Knoepfe-Karte, Abschnitt 1: schreibt oder spricht die Gruppe frei,
  // statt eine Abkuerzung zu druecken, bleibt die zuletzt gezeigte
  // Chip-Leiste stehen (eine Abkuerzung ist nicht falsch geworden), wird
  // aber gedaempft -- rein optisch, der Server entscheidet weiterhin allein,
  // wann ein Knopf wirklich verfaellt.
  function veralteLetzteLeiste() {
    var leisten = verlauf.querySelectorAll('.leiste');
    if (leisten.length) { leisten[leisten.length - 1].classList.add('ueberholt'); }
  }

  function blaseZu(id) {
    return verlauf.querySelector('.blase[data-id="' + id + '"]');
  }

  function leisteZu(id) {
    return verlauf.querySelector('.leiste[data-message="' + id + '"]');
  }

  function labelZu(id) {
    return verlauf.querySelector('.leiste-label[data-message="' + id + '"]');
  }

  function blase(n) {
    if (blaseZu(n.id)) { ersetze(n); return; }   // nie doppelt
    entferne(verlauf.querySelector('p.leer'));
    var huelle = document.createElement('div');
    huelle.className = 'blase ' + n.von + ' ' + klasseVon(n);
    huelle.dataset.id = n.id;
    huelle.innerHTML = inhaltVon(n);
    verlauf.appendChild(huelle);
    var leiste = baueLeiste(n);
    if (leiste) {
      verlauf.appendChild(baueLabel(n));
      verlauf.appendChild(leiste);
    }
  }

  // Review-Befund 10: aendere_text, entferne_knoepfe und loesche_nachrichten
  // treffen Zeilen, die schon dastehen -- die Arbeitszeile wechselt, eine
  // ueberholte Leiste verschwindet, eine geloeschte Nachricht auch.
  function ersetze(n) {
    var huelle = blaseZu(n.id);
    var altesLabel = labelZu(n.id);
    var alte = leisteZu(n.id);
    if (n.geloescht) { entferne(huelle); entferne(altesLabel); entferne(alte); return; }
    if (!huelle) { return; }
    huelle.innerHTML = inhaltVon(n);
    var neue = baueLeiste(n);
    if (alte && neue) { alte.parentNode.replaceChild(neue, alte); }
    else if (alte) { entferne(altesLabel); entferne(alte); }
    else if (neue) {
      huelle.parentNode.insertBefore(neue, huelle.nextSibling);
      huelle.parentNode.insertBefore(baueLabel(n), neue);
    }
  }

  function nachUnten() {
    // Mobile-App-Shell (03.10.2026, web_vereint._css_schale): auf der
    // vereinten Seite scrollt ``verlauf`` seit dieser Karte in sich selbst,
    // das Dokument gar nicht mehr -- die zweite Zeile ist dort ein No-Op.
    // Auf der (heute unerreichbaren, aber weiter unit-getesteten)
    // Chat-Einzelseite traegt umgekehrt nur ``window.scrollTo`` etwas bei,
    // weil ``verlauf`` dort kein eigenes Overflow hat. Beide Zeilen decken
    // je einen der beiden Faelle ab, ohne dass dieses Skript wissen muss,
    // auf welcher der beiden Seiten es laeuft.
    verlauf.scrollTop = verlauf.scrollHeight;
    window.scrollTo(0, document.body.scrollHeight);
  }

  // Padua Brainstorm, 03.10.2026: ob der Bildschirm schon am unteren Rand
  // stand -- VOR jeder DOM-Aenderung gelesen, sonst veraendert eine neue
  // Blase schon scrollHeight, bevor wir nachsehen konnten.
  function amUnterenRand() {
    return (window.innerHeight + window.scrollY)
      >= (document.body.scrollHeight - UNTEN_TOLERANZ_PX);
  }

  // Wurde die zurzeit letzte Blase im Verlauf gerade durch ``ersetze()``
  // veraendert? Das laufende Transkript eines Brainstorm-Segments legt keine
  // neue Nachricht an (nur eine Aenderung an der schon vorhandenen) -- ohne
  // diese Pruefung bliebe der Bildschirm stehen, waehrend die Blase unten
  // weiterwaechst.
  function letzteBlaseWurdeGeaendert(geaendert) {
    var blasen = verlauf.querySelectorAll('.blase');
    if (!blasen.length) { return false; }
    var letzteId = blasen[blasen.length - 1].dataset.id;
    return geaendert.some(function (n) { return String(n.id) === letzteId; });
  }

  // Phasenscroll-Karte (04.10.2026): die juengste Eintrittsnachricht einer
  // Phase im aktuell geladenen Verlauf -- ihr Praefix ist sprachunabhaengig
  // gleich (``phasentexte._KOPF_EINTRITT``), eine neue DB-Spalte ist dafuer
  // nicht noetig. Rueckwaerts gesucht, weil nur die LETZTE Phasenzeile
  // zaehlt -- eine aeltere stuende sonst im Weg.
  function phasenkopfzeile() {
    var blasen = verlauf.querySelectorAll('.blase.bot');
    for (var i = blasen.length - 1; i >= 0; i--) {
      if (blasen[i].textContent.indexOf('▶️ Phase ') === 0) { return blasen[i]; }
    }
    return null;
  }

  // Nach einem Phasenwechsel soll der Anfang der neuen Phase im Bild
  // stehen, nicht das Ende des ganzen (ungetrennten) Verlaufs.
  // ``scrollIntoView`` passt dabei automatisch jeden scrollbaren Vorfahren
  // an -- die Chat-Einzelseite (Dokument-Scroll) UND die vereinte Seite
  // (``verlauf`` scrollt in sich selbst) brauchen dafuer keinen eigenen Weg,
  // anders als ``nachUnten()``. Ohne Phasenzeile im Verlauf (z. B. ganz am
  // Anfang von Phase 1) bleibt der bisherige Rueckfall. Ohne Argument
  // entspricht der Aufruf laut Spezifikation genau dem Anfang des Elements
  // oben im sichtbaren Bereich und keiner seitlichen Verschiebung -- ebenso
  // wirksam wie mit ausgeschriebenen Werten.
  function scrolleZuPhasenanfang() {
    var kopf = phasenkopfzeile();
    if (kopf) { kopf.scrollIntoView(); return; }
    nachUnten();
  }

  function nimmZustand(daten) {
    var warUnten = amUnterenRand();
    // Review-Befund 2: die Seite laedt nie neu, ein Nonce gilt hoechstens
    // zwei Stunden -- der Poll bringt den laufenden mit.
    if (daten.nonce) {
      var feld = document.getElementById('nonce');
      if (feld) { feld.value = daten.nonce; }
    }
    var neu = daten.nachrichten || [];
    neu.forEach(blase);
    if (neu.length) {
      zustand.letzte = daten.letzte;
      verlauf.dataset.letzte = daten.letzte;
    }
    var geaendert = daten.geaendert || [];
    geaendert.forEach(ersetze);
    if (typeof daten.aenderung === 'number') {
      zustand.aenderung = daten.aenderung;
      verlauf.dataset.aenderung = daten.aenderung;
    }
    // Phasenscroll-Karte (04.10.2026): ein Wechsel zaehlt nur, wenn vorher
    // schon eine Phase bekannt war (sonst waere der allererste Poll immer
    // ein "Wechsel") und die neue sich von ihr unterscheidet.
    var phaseAlt = zustand.phase;
    var phaseNeu = (typeof daten.phase === 'number') ? daten.phase : null;
    var phasenwechsel = phaseAlt > 0 && phaseNeu !== null && phaseNeu !== phaseAlt;
    if (phaseNeu !== null) { zustand.phase = phaseNeu; }
    if (neu.length) {
      if (phasenwechsel) { scrolleZuPhasenanfang(); } else { nachUnten(); }
    } else if (warUnten && geaendert.length && letzteBlaseWurdeGeaendert(geaendert)) {
      nachUnten();
    }
    if (tipptFeld) { tipptFeld.textContent = daten.tippt ? TEXT.tippt : ''; }
    // UX-Knoepfe-Karte, Abschnitt 1: der Platzhalter folgt der Phase, das
    // Eingabefeld selbst bleibt dabei immer offen und unveraendert bedienbar.
    if (daten.platzhalter && eingabe) { eingabe.placeholder = daten.platzhalter; }
    zustand.servermodus = !!daten.interviewmodus;
    if (typeof daten.interview_knopf === 'boolean') { zustand.knopfErlaubt = daten.interview_knopf; }
    if (typeof daten.brainstorm_knopf === 'boolean') { zustand.brainstormErlaubt = daten.brainstorm_knopf; }
    if (typeof daten.diskussion_knopf === 'boolean') { zustand.diskussionErlaubt = daten.diskussion_knopf; }
    // Task 2 (Kanban-Karte Mithoeren SICHER/Kalibrierung, 03.10.2026): der
    // Kalibrierungsablauf liest beides selbst (kalWarteAufTranskript), hier
    // nur uebernehmen.
    zustand.kalibrierung = daten.kalibrierung || null;
    if (daten.kalibrierung_modus !== undefined) {
      zustand.kalibrierungModus = daten.kalibrierung_modus || null;
    }
    // Re-Review I: die Sperrklinke rastet auch ein, wenn noch kein Segment
    // vorn in der Schlange steht.
    if (zustand.aufnahme && zustand.aufnahme.angemeldet && zustand.servermodus) {
      zustand.aufnahme.bestaetigt = true;
    }
    if (!zustand.servermodus) { pruefeModusende(); }
    zeigeAngehalten();   // Nachreichen geht nur ohne laufendes Interview
    var w = zustand.wechsel;
    if (w && w.gesendet && zustand.servermodus === w.ziel) { zustand.wechsel = null; }
    zeigeModus();
    zeigeAntworten(daten.antworten || {}, daten.antworten_bezug || {});
    arbeiteAb();   // ein wartendes Segment darf jetzt vielleicht raus
  }

  // Birk 03.10.2026: die Quittung („✗ Discarded“) gehoert unter die Frage,
  // an deren Leiste gedrueckt wurde -- nicht ans Ende des Verlaufs, wo beim
  // Einzeldurchgang schon die naechste Frage steht. ``bezug`` (Druck-id ->
  // message_id) kommt vom Server; fehlt er (aelterer Server, Nachricht weg),
  // bleibt es beim alten Anhaengen unten.
  function zeigeAntworten(antworten, bezug) {
    bezug = bezug || {};
    Object.keys(antworten).forEach(function (id) {
      if (document.querySelector('.quittung[data-druck="' + id + '"]')) { return; }
      var zeile = document.createElement('div');
      zeile.className = 'quittung';
      zeile.dataset.druck = id;
      zeile.textContent = antworten[id];
      var ziel = bezug[id] != null ? leisteZu(bezug[id]) || blaseZu(bezug[id]) : null;
      if (ziel && ziel.parentNode === verlauf) {
        verlauf.insertBefore(zeile, ziel.nextSibling);
      } else {
        verlauf.appendChild(zeile);
      }
    });
  }

  // Immer nur ein Poll unterwegs: zwei Antworten in vertauschter Reihenfolge
  // setzten sonst einen aelteren Stand ueber einen neueren.
  var holt = null;
  var nochmalHolen = false;
  function hole() {
    if (holt) { nochmalHolen = true; return holt; }
    holt = fetch(weg(`chat/zustand?nach=${zustand.letzte}` +
                     `&seit=${zustand.aenderung}`), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d) { nimmZustand(d); } })
      .catch(function () { /* Netz weg: der naechste Takt versucht es wieder */ })
      .then(function () {
        holt = null;
        if (nochmalHolen) { nochmalHolen = false; return hole(); }
      });
    return holt;
  }

  var pollTakt = null;
  function planePoll() {
    if (pollTakt) { clearInterval(pollTakt); }
    var takt = document.hidden ? POLL_MS_HINTERGRUND : POLL_MS;
    pollTakt = setInterval(hole, takt);
  }
  document.addEventListener('visibilitychange', function () {
    planePoll();
    if (!document.hidden) { hole(); }
  });
  planePoll();

  // -- POST mit Nonce ------------------------------------------------------
  //
  // Ein 403 heisst fast immer "Nonce abgelaufen": einmal den Zustand holen
  // (er bringt den aktuellen Nonce mit), dann genau ein zweiter Versuch.

  function postJson(pfad, nutzlast, zweiter) {
    nutzlast.nonce = nonce();
    return fetch(weg(pfad), {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(nutzlast)
    }).then(function (r) {
      if (r.status === 403 && !zweiter) {
        return hole().then(function () { return postJson(pfad, nutzlast, true); });
      }
      return r;
    });
  }

  function postAudio(auftrag, zweiter) {
    var weg_ = `chat/audio?dauer=${auftrag.dauer}`;
    if (auftrag.grund) { weg_ += `&grund=${auftrag.grund}`; }
    if (auftrag.redeMs != null) { weg_ += `&rede=${Math.round(auftrag.redeMs)}`; }
    if (auftrag.sitzung && auftrag.sitzung.art === 'brainstorm') { weg_ += '&brainstorm=1'; }
    if (auftrag.sitzung && auftrag.sitzung.art === 'diskussion') { weg_ += '&diskussion=1'; }
    if (auftrag.kalibrierung) { weg_ += '&kalibrierung=1'; }
    return fetch(weg(weg_), {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': auftrag.blob.type || 'audio/webm',
                 'X-Nonce': nonce() },
      body: auftrag.blob
    }).then(function (r) {
      if (r.status === 403 && !zweiter) {
        return hole().then(function () { return postAudio(auftrag, true); });
      }
      return r;
    });
  }

  // -- Senden --------------------------------------------------------------

  function sendeText() {
    var text = (eingabe.value || '').trim();
    if (!text) { return; }
    eingabe.value = '';
    veralteLetzteLeiste();
    function zurueck() { if (!eingabe.value) { eingabe.value = text; } }
    postJson(`chat/senden`, { text: text }).then(function (r) {
      if (r.ok) { hole(); return; }
      zurueck();
      return fehlerAus(r);
    }).catch(function () { zurueck(); meldeFehler(TEXT.fehler_netz); });
  }

  document.getElementById('senden').addEventListener('click', sendeText);
  eingabe.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') { ev.preventDefault(); sendeText(); }
  });

  // -- Knoepfe -------------------------------------------------------------

  function schalteLeiste(leiste, aus) {
    if (!leiste) { return; }
    Array.prototype.forEach.call(leiste.querySelectorAll('button'),
      function (b) { b.disabled = aus; });
  }

  document.addEventListener('click', function (ev) {
    var knopf = ev.target.closest ? ev.target.closest('.leiste button') : null;
    if (!knopf) { return; }
    // Alle Knoepfe der Leiste aus: der zweite Druck wirkt serverseitig
    // idempotent nicht mehr, aber ein Knopf, der weiter klickbar
    // dasteht, laedt dazu ein.
    var leiste = knopf.closest('.leiste');
    schalteLeiste(leiste, true);
    postJson(`chat/knopf`, {
      message_id: parseInt(knopf.dataset.message, 10),
      data: knopf.dataset.daten
    }).then(function (r) {
      if (r.ok) { hole(); return; }
      schalteLeiste(leiste, false);
      hole();
      return fehlerAus(r);
    }).catch(function () {
      schalteLeiste(leiste, false);
      meldeFehler(TEXT.fehler_netz);
    });
  });

  // -- Warteschlange -------------------------------------------------------
  //
  // Streng der Reihe nach, ein Auftrag zur Zeit: /interview, die Segmente,
  // /fertig und PTT-Aufnahmen. Ein Auftrag bleibt vorn stehen, bis der
  // Server ihn angenommen (2xx) oder endgueltig abgelehnt (4xx) hat.

  function reiheEin(auftrag) {
    zustand.warteschlange.push(auftrag);
    zeigeWarteschlange();
    arbeiteAb();
  }

  // Der Wettlauf (Entscheidung I): ein Segment darf erst raus, wenn
  // /interview dieser Aufnahme angenommen ist UND der Poll den Modus meldet.
  // Sonst macht aufnahme.klasse_fuer daraus eine kurz-Aufnahme statt eines
  // Interview-Teils.
  //
  // Eine Sperrklinke je Aufnahme (Re-Review A): nur bis der Poll den Modus
  // EINMAL gemeldet hat, wird gewartet. Endet der Modus danach ohne dieses
  // Telefon (der Erkenner hoert "fertig" im Teil-Transkript, ein zweites
  // Telefon beendet), gehen die restlichen Segmente trotzdem raus -- sonst
  // stuende eines ewig vorn in der Schlange und alles dahinter mit ihm.
  //
  // Re-Review H: ein Segment geht NIE ohne Modus raus. Ohne Modus waere es
  // fuer den Bot eine 'kurz'-Aufnahme (aufnahme.klasse_fuer) und damit
  // ein Gespraechsbeitrag. Dass ein Segment deshalb nicht ewig vorn steht,
  // regelt pruefeModusende(): endet der Modus nach der Bestaetigung, wird
  // die Aufnahme angehalten und aus der Schlange genommen.
  function bereit(auftrag) {
    var sitzung = auftrag.sitzung;
    if (auftrag.art === 'audio' && sitzung) {
      // Brainstorm kennt keinen Modus-Befehl (kein /interview, kein
      // /fertig) -- ein Segment ist immer eine gewoehnliche 'kurz'-Aufnahme
      // und geht deshalb sofort raus, wie ein PTT-Druck.
      if (sitzung.art === 'brainstorm') { return true; }
      // Dasselbe gilt fuer das Hintergrund-Mithoeren in Phase 1 (Task 6):
      // kein Modus-Befehl, ein Segment ist immer eine gewoehnliche
      // 'kurz'-Aufnahme.
      if (sitzung.art === 'diskussion') { return true; }
      if (!sitzung.angemeldet || sitzung.angehalten) { return false; }
      if (zustand.servermodus) { sitzung.bestaetigt = true; }
      return zustand.servermodus;
    }
    return true;
  }

  // /fertig einer Aufnahme, deren Modus der Bot schon beendet hat, ist
  // ueberholt: nicht senden, den Stopp-Wechsel aber sauber aufloesen, damit
  // der Knopf wieder bedienbar ist.
  //
  // Bewusst NUR mit Sperrklinke: "angemeldet" allein hiesse, /interview ist
  // angenommen, aber vielleicht vom Bot noch nicht verarbeitet -- ein dann
  // verworfenes /fertig liesse den Modus spaeter dauerhaft an.
  function ueberholt(auftrag) {
    return auftrag.art === 'befehl' && auftrag.an === false &&
           auftrag.sitzung && auftrag.sitzung.bestaetigt && !zustand.servermodus;
  }

  function zeigeWarteschlange() {
    if (!warteFeld) { return; }
    var offen = zustand.warteschlange.length;
    var stuecke = zustand.warteschlange.filter(function (a) {
      return a.art === 'audio';
    }).length;
    var satz = '';
    if (offen && zustand.netzFehler) {
      satz = TEXT.warte_netz.replace('{n}', offen);
    } else if (stuecke && !bereit(zustand.warteschlange[0])) {
      satz = TEXT.warte_modus.replace('{n}', stuecke);
    } else if (stuecke) {
      satz = stuecke === 1 ? TEXT.warte_eins
                           : TEXT.warte_mehr.replace('{n}', stuecke);
    }
    warteFeld.textContent = satz;
  }

  function planeNachholen(ms) {
    if (zustand.nachholTakt) { return; }
    zustand.nachholTakt = setTimeout(function () {
      zustand.nachholTakt = null;
      arbeiteAb();
    }, ms);
  }

  // Review-Befund 3: Netzfehler und 5xx werden ohne Hoechstzahl wiederholt,
  // mit gedeckeltem Abstand. Ist das Netz wieder da, sofort.
  window.addEventListener('online', function () {
    if (zustand.nachholTakt) {
      clearTimeout(zustand.nachholTakt);
      zustand.nachholTakt = null;
    }
    arbeiteAb();
    hole();
  });

  // Re-Review zu a615327: war ein Segment beim Modusende schon unterwegs,
  // liess halteAn es vorn stehen. Ist es danach nicht angekommen (Netz, 5xx,
  // 403), stuende es mit laeuft = false fuer immer vorn -- bereit() sagt
  // wegen 'angehalten' nein, und alles dahinter (PTT, ein neues /interview,
  // ein Nachreichen) haenge mit. Es wird deshalb jetzt geparkt, und zwar
  // VORN: es ist aelter als alles, was halteAn schon geparkt hat.
  function parkeKopf(auftrag) {
    var sitzung = auftrag.sitzung;
    if (auftrag.art !== 'audio' || !sitzung || !sitzung.angehalten) { return false; }
    zustand.warteschlange.shift();
    if (!sitzung.restVerworfen) {   // "Rest verwerfen" gilt auch fuer dieses
      sitzung.geparkt.unshift(auftrag);
      if (zustand.angehalten.indexOf(sitzung) < 0) { zustand.angehalten.push(sitzung); }
    }
    zeigeWarteschlange();
    zeigeAngehalten();
    zeigeModus();
    return true;
  }

  function arbeiteAb() {
    if (zustand.laeuft || zustand.nachholTakt || !zustand.warteschlange.length) {
      return;
    }
    var auftrag = zustand.warteschlange[0];
    if (parkeKopf(auftrag)) { arbeiteAb(); return; }
    if (!bereit(auftrag)) { zeigeWarteschlange(); return; }   // der Poll ruft wieder
    if (ueberholt(auftrag)) {
      zustand.warteschlange.shift();
      if (auftrag.wechsel && zustand.wechsel === auftrag.wechsel) { zustand.wechsel = null; }
      zeigeWarteschlange();
      zeigeModus();
      arbeiteAb();
      return;
    }
    zustand.laeuft = true;
    zeigeWarteschlange();
    var anfrage = auftrag.art === 'befehl'
      ? postJson(`chat/interview`, { an: auftrag.an })
      : postAudio(auftrag);
    anfrage.then(function (r) {
      if (r.ok) {
        zustand.netzFehler = 0;
        // Task 2 (Kanban-Karte Mithoeren SICHER/Kalibrierung, 03.10.2026):
        // der Kalibrierungsablauf braucht die message_id dieses konkreten
        // Uploads zurueck, um spaeter gezielt auf SEIN Transkript zu warten
        // (zustand.kalibrierung, aus dem Poll) -- dieselbe id, die die
        // Antwort schon liefert, kein zweites Kennungsschema.
        if (auftrag.art === 'audio' && auftrag.kalibrierung && auftrag.sitzung) {
          r.json().then(function (daten) {
            auftrag.sitzung._kalMessageId = daten && daten.message_id;
          }).catch(function () { /* ohne id bricht die Wartefunktion selbst ab */ });
        }
        erledigt(auftrag, true);
        return;
      }
      // 403 auch nach dem Nonce-Poll: wie ein Netzfehler behandeln (Re-Review
      // C) -- der naechste Versuch holt erneut den Zustand und damit den Nonce.
      if (r.status >= 500 || r.status === 403 || r.status === 408 ||
          r.status === 429) {
        throw new Error('nochmal');
      }
      // Endgueltig abgelehnt: verwerfen -- aber sichtbar.
      zustand.netzFehler = 0;
      return fehlerAus(r).then(function () { erledigt(auftrag, false); });
    }).catch(function () {
      zustand.laeuft = false;
      zustand.netzFehler += 1;
      zeigeWarteschlange();
      planeNachholen(UPLOAD_WARTEN_MS[Math.min(zustand.netzFehler - 1,
                                               UPLOAD_WARTEN_MS.length - 1)]);
    });
  }

  function erledigt(auftrag, angenommen) {
    zustand.warteschlange.shift();
    zustand.laeuft = false;
    if (auftrag.art === 'befehl') {
      var w = auftrag.wechsel;
      if (w) {
        if (angenommen) { w.gesendet = true; }
        else if (zustand.wechsel === w) { zustand.wechsel = null; }
      }
      if (auftrag.an && auftrag.sitzung) {
        if (angenommen) { auftrag.sitzung.angemeldet = true; }
        else { brichAb(auftrag.sitzung); }
      }
    }
    zeigeWarteschlange();
    zeigeAngehalten();   // ein unterwegs gewesenes Segment ist jetzt erledigt
    zeigeModus();
    hole();
    arbeiteAb();
  }

  // Nimmt die noch nicht gesendeten Auftraege einer Aufnahme heraus. Der
  // gerade laufende bleibt stehen -- sein Ergebnis raeumt erledigt() ab.
  function entferneAuftraege(sitzung) {
    zustand.warteschlange = zustand.warteschlange.filter(function (a, i) {
      return a.sitzung !== sitzung || (i === 0 && zustand.laeuft);
    });
    zeigeWarteschlange();
  }

  // -- Mikrofon ------------------------------------------------------------

  function holeStrom() {
    return new Promise(function (ja, nein) {
      var geraete = navigator.mediaDevices;
      if (!geraete || !geraete.getUserMedia || !window.MediaRecorder) {
        nein(new Error('kein Mikrofon'));
        return;
      }
      geraete.getUserMedia({ audio: true }).then(ja, nein);
    });
  }

  // Review-Befund 8: Spuren stoppen (sonst bleibt die Mikrofonanzeige des
  // Telefons an), Pegel-Takt und AudioContext schliessen.
  function gibFrei(halter) {
    if (halter.pegelTakt) { clearInterval(halter.pegelTakt); halter.pegelTakt = null; }
    if (halter.kontext) {
      try { halter.kontext.close(); } catch (e) { /* schon zu */ }
      halter.kontext = null;
    }
    if (halter.strom) {
      halter.strom.getTracks().forEach(function (t) { t.stop(); });
      halter.strom = null;
    }
  }

  // -- Interview-Aufnahme --------------------------------------------------

  function neuesSegment(sitzung) {
    // Ein eigener Recorder je Segment -- KEINE Zeitscheibe: deren Stuecke
    // sind einzeln nicht dekodierbar, nur das erste traegt den
    // Container-Kopf. Whisper bekaeme ab dem zweiten Segment Bytes ohne Kopf.
    var r = new MediaRecorder(sitzung.strom);
    var teile = [];
    var von = Date.now();
    var nr = sitzung.naechsteNr;
    sitzung.naechsteNr += 1;
    sitzung.offen += 1;
    r.ondataavailable = function (ev) {
      if (ev.data && ev.data.size) { teile.push(ev.data); }
    };
    // Erst das stop-Ereignis sagt, dass alle Daten da sind
    // (ondataavailable kommt nach stop() asynchron).
    r.onstop = function () {
      sitzung.offen -= 1;
      var auftrag = null;
      // r._grund/r._redeMs werden von schneideSegment() (Schnitt) oder von
      // pausiereInterview()/beendeInterview() (Flush) VOR stop() gesetzt;
      // ohne VAD (Rueckfall auf den festen Takt) bleiben beide undefined.
      var redeMs = r._redeMs;
      var grund = r._grund || null;
      // Frueher wurde hier ueber redeMs verworfen (Birk, Szenario A: eine zu
      // hoch eingestellte Schwelle liess leise, aber echte Rede als "nicht
      // genug" durchfallen und das ganze Segment -- samt Woertern -- ging
      // nie hoch). Jedes Segment mit Bytes geht jetzt IMMER raus; redeMs
      // faehrt nur noch als Metadatum mit (Kanban-Karte Mithoeren SICHER).
      // r._kalVerworfen (Task 2, Kanban-Karte Mithoeren SICHER/
      // Kalibrierung, 03.10.2026): der 30s-Stille-Rueckfall der
      // Kalibrierung -- dieser Clip wird NIE verschickt, es gibt nichts zu
      // testen. r._kalibrierung markiert stattdessen den Testsatz-Clip
      // selbst, der ganz normal durch dieselbe Warteschlange geht wie jedes
      // andere Segment, nur mit dem zusaetzlichen Upload-Flag.
      if (teile.length && !sitzung.verworfen && !r._kalVerworfen) {   // leere Stuecke nie
        auftrag = {
          art: 'audio', sitzung: sitzung,
          blob: new Blob(teile, { type: teile[0].type || r.mimeType || 'audio/webm' }),
          dauer: Math.max(1, Math.round((Date.now() - von) / 1000)),
          grund: grund, redeMs: redeMs, kalibrierung: !!r._kalibrierung
        };
      }
      // Task 4 (Kanban-Karte Mithoeren SICHER, 03.10.2026): einmal je
      // Sitzung, direkt nachdem das erste Segment fertig ist -- kein
      // localStorage, reines Sitzungsfeld (sitzung.hinweisGezeigt), eine
      // neue Sitzung (neuer Interview-/Brainstorm-Start) zeigt ihn wieder.
      // Eigenstaendig von kalErinnerungFeld/zustand.kalibrierungModus oben
      // (Task 2s "Handy herumreichen"-Erinnerung): anderer Ausloeser,
      // anderer Merkposten, nicht zusammenlegen.
      if (!sitzung.hinweisGezeigt) {
        sitzung.hinweisGezeigt = true;
        if (mitlaufHinweisFeld) {
          mitlaufHinweisFeld.textContent = TEXT.mitlauf_hinweis;
          mitlaufHinweisFeld.hidden = false;
        }
      }
      // Re-Review B: zwei onstop koennen sich ueberholen (Stopp mitten im
      // Segmentwechsel). Eingereiht wird nach der laufenden Nummer.
      sitzung.fertige[nr] = auftrag;
      while (sitzung.fertige.hasOwnProperty(sitzung.einzureihen)) {
        var naechster = sitzung.fertige[sitzung.einzureihen];
        delete sitzung.fertige[sitzung.einzureihen];
        sitzung.einzureihen += 1;
        if (naechster && !sitzung.verworfen) {
          if (sitzung.angehalten) { sitzung.geparkt.push(naechster); }
          else { reiheEin(naechster); }
        }
      }
      pruefeEnde(sitzung);
    };
    r.start();
    return r;
  }

  // Review-Befund 1: /fertig erst, wenn der letzte Recorder sein
  // stop-Ereignis hatte -- dann ist das letzte Segment eingereiht, und weil
  // die Schlange der Reihe nach arbeitet, geht /fertig erst nach ihm raus.
  function pruefeEnde(sitzung) {
    if (!sitzung.beendet || sitzung.offen > 0 || sitzung.fertigEingereiht ||
        sitzung.verworfen) { return; }
    sitzung.fertigEingereiht = true;
    gibFrei(sitzung);
    if (sitzung.angehalten) { zeigeAngehalten(); return; }   // kein /fertig
    reiheEin({ art: 'befehl', an: false, sitzung: sitzung,
               wechsel: sitzung.wechselAus });
  }

  // -- Modusende ohne dieses Telefon (Re-Review H) ------------------------
  //
  // Konservativer Rueckfallweg, die Entscheidung liegt bei Birk: endet der
  // Interviewmodus serverseitig, waehrend eine bestaetigte Aufnahme dieses
  // Telefons noch laeuft oder Segmente offen hat, stoppt das Telefon selbst,
  // haelt den Rest an und fragt: nachreichen oder verwerfen.

  function pruefeModusende() {
    var betroffen = [];
    if (zustand.aufnahme && zustand.aufnahme.bestaetigt) {
      betroffen.push(zustand.aufnahme);
    }
    zustand.warteschlange.forEach(function (a, i) {
      if (a.art !== 'audio' || !a.sitzung || !a.sitzung.bestaetigt) { return; }
      if (i === 0 && zustand.laeuft) { return; }   // schon unterwegs
      if (betroffen.indexOf(a.sitzung) < 0) { betroffen.push(a.sitzung); }
    });
    betroffen.forEach(halteAn);
  }

  function halteAn(sitzung) {
    if (sitzung.angehalten || sitzung.verworfen) { return; }
    sitzung.angehalten = true;
    if (zustand.angehalten.indexOf(sitzung) < 0) { zustand.angehalten.push(sitzung); }
    if (zustand.aufnahme === sitzung) {
      zustand.aufnahme = null;
      anzeigeAus();
      sitzung.beendet = true;
      if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); sitzung.segmentTakt = null; }
      var letzter = sitzung.recorder;
      sitzung.recorder = null;
      // Sein onstop parkt das letzte Segment und gibt das Mikrofon frei.
      if (letzter && letzter.state !== 'inactive') { letzter.stop(); }
      else { pruefeEnde(sitzung); }
    }
    // Was noch nicht unterwegs ist, kommt aus der Schlange: Segmente werden
    // geparkt, das /fertig dieser Aufnahme entfaellt.
    zustand.warteschlange = zustand.warteschlange.filter(function (a, i) {
      if (a.sitzung !== sitzung || (i === 0 && zustand.laeuft)) { return true; }
      if (a.art === 'audio') { sitzung.geparkt.push(a); }
      return false;
    });
    if (sitzung.wechselAus && zustand.wechsel === sitzung.wechselAus) {
      zustand.wechsel = null;
    }
    zeigeWarteschlange();
    zeigeAngehalten();
    zeigeModus();
  }

  function geparkteZahl() {
    return zustand.angehalten.reduce(function (n, s) { return n + s.geparkt.length; }, 0);
  }

  // Steht ein Segment dieser Aufnahme gerade im Upload?
  function unterwegs(sitzung) {
    var kopf = zustand.warteschlange[0];
    return !!(zustand.laeuft && kopf && kopf.sitzung === sitzung);
  }

  function zeigeAngehalten() {
    if (!angehaltenFeld) { return; }
    if (!zustand.angehalten.length) { angehaltenFeld.hidden = true; return; }
    var n = geparkteZahl();
    var offen = zustand.angehalten.some(function (s) { return s.offen > 0 || unterwegs(s); });
    if (!n && !offen) {
      // Nichts liegt mehr hier: nur sagen, was passiert ist.
      zustand.angehalten = [];
      angehaltenFeld.hidden = true;
      meldeFehler(TEXT.modus_weg_leer);
      return;
    }
    var satz = n ? TEXT.modus_weg.replace('{n}', n) : TEXT.modus_weg_leer;
    // Laeuft inzwischen ein anderes Interview (zweites Telefon), schloesse
    // das /fertig des Nachreichens dessen Interview. Erst wenn es aus ist.
    if (n && zustand.servermodus) { satz += ' ' + TEXT.nachreichen_spaeter; }
    angehaltenText.textContent = satz;
    nachreichenKnopf.hidden = !n || zustand.servermodus;
    verwerfenKnopf.hidden = !n;
    angehaltenFeld.hidden = false;
  }

  // Ueber denselben Weg wie der Umschalter: /interview, die Segmente,
  // /fertig -- der Reihe nach durch die Schlange, mit eigener Sperrklinke.
  function reicheNach() {
    if (zustand.wechsel || zustand.aufnahme) { return; }   // erst das Laufende
    if (zustand.servermodus) { zeigeAngehalten(); return; }   // fremdes Interview
    if (zustand.angehalten.some(function (s) { return s.offen > 0 || unterwegs(s); })) {
      return;   // ein Segment ist noch im Recorder oder im Upload
    }
    var rest = [];
    zustand.angehalten.forEach(function (s) {
      rest = rest.concat(s.geparkt);
      s.geparkt = [];
    });
    zustand.angehalten = [];
    zeigeAngehalten();
    if (!rest.length) { return; }
    var w = { ziel: false, gesendet: false };
    var nach = {
      strom: null, recorder: null, kontext: null, pegelTakt: null,
      segmentTakt: null, offen: 0, gestartet: true, beendet: true,
      angemeldet: false, bestaetigt: false, verworfen: false,
      angehalten: false, geparkt: [], fertigEingereiht: true,
      naechsteNr: 0, einzureihen: 0, fertige: {}, wechselAus: w
    };
    zustand.wechsel = w;   // bis der Bot /fertig verarbeitet hat, kein neuer Start
    reiheEin({ art: 'befehl', an: true, sitzung: nach });
    rest.forEach(function (a) { a.sitzung = nach; reiheEin(a); });
    reiheEin({ art: 'befehl', an: false, sitzung: nach, wechsel: w });
    zeigeModus();
  }

  function verwirfRest() {
    // restVerworfen: ein Segment, das gerade unterwegs ist und danach
    // scheitert, wird von parkeKopf nicht wieder hervorgeholt.
    zustand.angehalten.forEach(function (s) { s.geparkt = []; s.restVerworfen = true; });
    zustand.angehalten = [];
    zeigeAngehalten();
    zeigeModus();
  }

  // Pausen-Schnitt (VAD, 02.10.2026): derselbe AnalyserNode wie der Pegel
  // liefert zusaetzlich getFloatTimeDomainData() fuer eine RMS-Schaetzung.
  // Schneidet sitzung.recorder NIE direkt -- das macht schneideSegment(),
  // das den Nachfolge-Recorder gleich mitanlegt, damit zwischen zwei
  // Segmenten keine Luecke entsteht.
  function schneideSegment(sitzung, grund) {
    var alt = sitzung.recorder;
    if (!alt) { return; }
    alt._grund = grund;
    alt._redeMs = sitzung.vadSpeechMs;
    if (alt.state !== 'inactive') { alt.stop(); }   // liefert sein Segment im onstop
    sitzung.recorder = neuesSegment(sitzung);
    sitzung.vadSegmentStart = Date.now();
    sitzung.vadSpeechMs = 0;
    sitzung.vadLetzteRede = sitzung.vadSegmentStart;
  }

  // -- Pegel-Kalibrierung (Task 2, Kanban-Karte Mithoeren SICHER/           --
  // -- Kalibrierung, 03.10.2026): die reinen Rechenfunktionen zuerst, damit --
  // -- sie woertlich (nicht nachgebaut) aus einem Node-Testlauf heraus      --
  // -- aufgerufen werden koennen (tests/test_web_chat_js.py). -------------

  function kalMedian(werte) {
    if (!werte.length) { return 0; }
    var sortiert = werte.slice().sort(function (a, b) { return a - b; });
    var mitte = Math.floor(sortiert.length / 2);
    return sortiert.length % 2
      ? sortiert[mitte]
      : (sortiert[mitte - 1] + sortiert[mitte]) / 2;
  }

  function kalPerzentil(werte, p) {
    if (!werte.length) { return 0; }
    var sortiert = werte.slice().sort(function (a, b) { return a - b; });
    return sortiert[Math.min(sortiert.length - 1, Math.floor(sortiert.length * p))];
  }

  // Item (d): zu leise, wenn die gemessene Rede nicht mindestens dreimal so
  // laut ist wie der Rauschboden, ODER wenn insgesamt zu wenig Stimmzeit
  // zusammenkam (unter 2000ms) -- beide Bedingungen gemeinsam, kein Ersatz
  // fuereinander.
  function kalZuLeise(redeMess, bodenMess, stimmMs) {
    return (redeMess < 3 * bodenMess) || (stimmMs < 2000);
  }

  // Geometrisches Mittel aus Boden- und Rede-Messung, geklemmt auf
  // [0.004, 0.08] -- derselbe Rahmen, in dem auch RMS_SCHWELLE/der feste
  // Rueckfall (0.006) liegen.
  function kalSchwelle(bodenMess, redeMess) {
    return Math.min(Math.max(Math.sqrt(bodenMess * redeMess), KAL_SCHWELLE_ABS_MIN),
                     KAL_SCHWELLE_ABS_MAX);
  }

  // 2d: der kalibrierte Festwert (sitzung.vadSchwelleFix) ist, wenn gesetzt,
  // die DECKE -- der rollende Boden darf die Schwelle nur noch nach UNTEN
  // ziehen (bis zum absoluten Minimum), nie darueber. Ohne Kalibrierung
  // (sitzung.vadSchwelleFix nicht gesetzt: Kill-Switch aus oder noch nicht
  // kalibriert) bleibt es BYTE-GLEICH die alte, feste Formel.
  function kalBerechneBodenUndSchwelle(sortiert, sitzung, RMS_SCHWELLE,
                                        BODEN_FAKTOR, BODEN_DECKEL_FAKTOR) {
    var kalibriert = sitzung.vadSchwelleFix != null;
    var bodenDeckel = kalibriert
      ? sitzung.vadBodenMess * 2
      : RMS_SCHWELLE * BODEN_DECKEL_FAKTOR;
    var boden = Math.min(sortiert[Math.floor(sortiert.length * 0.1)] || 0, bodenDeckel);
    var schwelle = kalibriert
      ? Math.min(sitzung.vadSchwelleFix, Math.max(KAL_SCHWELLE_ABS_MIN, boden * BODEN_FAKTOR))
      : Math.max(RMS_SCHWELLE, boden * BODEN_FAKTOR);
    return { boden: boden, schwelle: schwelle };
  }

  function pegelAn(sitzung) {
    var Kontext = window.AudioContext || window.webkitAudioContext;
    if (!pegelBalken || !Kontext) { return; }
    try {
      var kontext = new Kontext();
      sitzung.kontext = kontext;
      if (kontext.state === 'suspended' && kontext.resume) { kontext.resume(); }
      var messer = kontext.createAnalyser();
      messer.fftSize = 256;
      kontext.createMediaStreamSource(sitzung.strom).connect(messer);
      var zeitWerte = new Float32Array(messer.fftSize);
      var PAUSE_MS = parseInt(fuss.dataset.vadPauseMs, 10) || 2500;
      var MAX_MS = parseInt(fuss.dataset.vadMaxMs, 10) || 90000;
      var MIN_SPEECH_MS = parseInt(fuss.dataset.vadMinSpeechMs, 10) || 500;
      var RMS_SCHWELLE = parseFloat(fuss.dataset.vadRms) || 0.01;
      var BODEN_FAKTOR = parseFloat(fuss.dataset.vadFloorFaktor) || 2.5;
      var BODEN_FENSTER = Math.ceil(5000 / 120);
      // Deckel auf den Rauschboden, nicht aus CoThinker, sondern gegen eine
      // gemessene Falle gesetzt (siehe Kommentar im Takt unten): ohne ihn
      // zieht eine durchgehend laute Aufnahme den Boden auf ihre eigene
      // Lautstaerke und die Pause-Erkennung faellt dauerhaft aus.
      var BODEN_DECKEL_FAKTOR = 10;
      // Anzeige-Skala des Pegelbalkens (rein kosmetisch, keine
      // IT_WEB_VAD_*-Variable): 0.3 RMS = 100% Balkenbreite, deutlich ueber
      // KAL_SCHWELLE_ABS_MAX (0.08), damit auch eine kalibrierte, hohe
      // Schwelle noch sichtbar Platz nach oben laesst.
      var PEGEL_MAX_RMS = 0.3;
      sitzung.vadMinSpeechMs = MIN_SPEECH_MS;
      sitzung.vadAktiv = true;
      sitzung.vadBoden = [];
      sitzung.pegelTakt = setInterval(function () {
        messer.getFloatTimeDomainData(zeitWerte);
        var quadratsumme = 0;
        for (var j = 0; j < zeitWerte.length; j++) {
          quadratsumme += zeitWerte[j] * zeitWerte[j];
        }
        var rms = Math.sqrt(quadratsumme / zeitWerte.length);
        sitzung.vadBoden.push(rms);
        if (sitzung.vadBoden.length > BODEN_FENSTER) { sitzung.vadBoden.shift(); }
        // Niedriges Perzentil der letzten ~5 s als Rauschboden -- GESETZT,
        // NICHT GEMESSEN (anders als PAUSE_MS/MAX_MS/MIN_SPEECH_MS/
        // RMS_SCHWELLE, die aus CoThinker stammen). BODEN_DECKEL_FAKTOR
        // begrenzt, wie weit der Boden die Schwelle anheben darf: ohne
        // Deckel zieht eine durchgehend laute Aufnahme den Boden auf ihre
        // eigene Lautstaerke, und die Schwelle wird unerreichbar (gemessener
        // Fehler beim ersten Browserlauf: ein konstanter Testton zog sie
        // exakt auf seinen eigenen Pegel, danach wurde nie wieder "Rede"
        // erkannt). Mit Deckel bleibt ein echtes, aber maessiges
        // Raumrauschen weiter erkennbar (die Schwelle darf bis zum Zehnfachen
        // von RMS_SCHWELLE steigen), eine durchgehend laute Stimme kann sie
        // aber nicht mehr darueber hinausschieben.
        var sortiert = sitzung.vadBoden.slice().sort(function (a, b) { return a - b; });
        // 2d (Task 2): mit Kalibrierung ist sitzung.vadSchwelleFix die
        // Decke, der Boden-Deckel wird aus vadBodenMess gerechnet -- ohne
        // Kalibrierung bleibt es byte-gleich die alte, feste Formel.
        var berechnet = kalBerechneBodenUndSchwelle(
          sortiert, sitzung, RMS_SCHWELLE, BODEN_FAKTOR, BODEN_DECKEL_FAKTOR
        );
        var boden = berechnet.boden;
        var schwelle = berechnet.schwelle;
        // Der sichtbare Balken faehrt seit dieser Karte auf derselben
        // RMS-Skala wie der Schnitt selbst (vorher: Frequenzmittel * 2.2,
        // eine andere Zahl als die Schwelle) -- Anzeige und Entscheidung
        // sind damit dieselbe Messung, nur einmal gezeichnet.
        pegelBalken.style.width =
          Math.min(100, (rms / PEGEL_MAX_RMS) * 100) + '%';
        if (pegelSchwelle) {
          pegelSchwelle.style.left =
            Math.min(100, (schwelle / PEGEL_MAX_RMS) * 100) + '%';
        }
        pegelFeld.classList.toggle('ueber-schwelle', rms > schwelle);
        var jetzt = Date.now();
        if (rms > schwelle) {
          sitzung.vadSpeechMs += 120;
          sitzung.vadLetzteRede = jetzt;
        }
        if (!sitzung.recorder) { return; }
        var kappe = (jetzt - sitzung.vadSegmentStart) >= MAX_MS;
        var pause = (jetzt - sitzung.vadLetzteRede) >= PAUSE_MS;
        if (kappe) {
          // Hart: schneidet IMMER, auch ohne Pause und auch mit zu wenig
          // Rede (der seltene Fall landet in onstop() ohne Upload -- siehe
          // dortigen Kommentar).
          schneideSegment(sitzung, 'cap');
        } else if (pause && sitzung.vadSpeechMs >= MIN_SPEECH_MS) {
          schneideSegment(sitzung, 'pause');
        }
        // pause && vadSpeechMs < MIN_SPEECH_MS: kein Schnitt -- die Stille
        // wird Teil desselben, weiterlaufenden Segments ("in das naechste
        // Segment getragen", ohne Audio-Bytes ueber zwei MediaRecorder-
        // Instanzen hinweg zusammenfuegen zu muessen, was keine einzelne
        // dekodierbare Datei mehr ergaebe).
      }, 120);
    } catch (e) { /* ohne Pegel geht es auch -- dann der feste Takt (Rueckfall unten) */ }
  }

  // Die erfasste Aufnahmedauer einer Sitzung: angesammelte Zeit vor der
  // letzten Pause (sitzung.erfassteMs) plus, solange nicht pausiert, die
  // laufende Spanne seit sitzung.legStart. Pause friert sie ein, Weiter
  // setzt legStart neu -- kein zweiter Zaehler, der von erfassteMs abweichen
  // koennte.
  function formatiereUhr(sitzung) {
    if (!sitzung) { return minuten(0); }
    var ms = sitzung.erfassteMs +
      ((!sitzung.pausiert && sitzung.legStart) ? Date.now() - sitzung.legStart : 0);
    return minuten(Math.floor(ms / 1000));
  }

  // Dieselbe Funktion fuer Start UND Weiter (Wiederaufnahme): beide zeigen
  // #uhr wieder an und starten den Ticktakt neu, nur die Sitzung bringt die
  // schon erfasste Zeit mit.
  function uhrAn(sitzung) {
    uhrFeld.hidden = false;
    pegelFeld.hidden = false;
    // Task 2: der panel-level Messen-Knopf (#kalibrierung-neu) ist immer
    // verfuegbar, solange #pegel/#uhr es auch sind -- derselbe Schalter,
    // keine zweite Sichtbarkeitsregel.
    if (kalNeuKnopf) { kalNeuKnopf.hidden = false; }
    uhrFeld.textContent = TEXT.uhr.replace('{zeit}', formatiereUhr(sitzung));
    if (zustand.uhrTakt) { clearInterval(zustand.uhrTakt); }
    zustand.uhrTakt = setInterval(function () {
      uhrFeld.textContent = TEXT.uhr.replace('{zeit}', formatiereUhr(sitzung));
    }, 500);
  }

  function anzeigeAus() {
    if (zustand.uhrTakt) { clearInterval(zustand.uhrTakt); zustand.uhrTakt = null; }
    uhrFeld.hidden = true;
    pegelFeld.hidden = true;
    if (kalNeuKnopf) { kalNeuKnopf.hidden = true; }
    if (kalFeld) { kalFeld.hidden = true; }
    if (pegelBalken) { pegelBalken.style.width = '0'; }
    if (pegelFeld) { pegelFeld.classList.remove('ueber-schwelle'); }
    // Task 4: nicht in einen spaeteren Bildschirmzustand hinueberlaufen.
    if (mitlaufHinweisFeld) { mitlaufHinweisFeld.hidden = true; }
  }

  function modusAn() {
    if (zustand.wechsel) { return zustand.wechsel.ziel; }
    return !!zustand.aufnahme || zustand.servermodus;
  }

  // Drei Zustaende, eine Funktion (Design-Vorgabe: keine zweite, parallele
  // Merkvariable neben zustand.aufnahme): Leerlauf (an=false), Laeuft
  // (an=true, nicht pausiert) und Pause (an=true, pausiert) -- "pausiert"
  // gilt auch, wenn dieses Telefon ueberhaupt keine lokale Sitzung hat, der
  // Server den Modus aber schon meldet (Neuladen waehrend ein anderes
  // Telefon aufnimmt oder pausiert hat, Punkt 5): es gibt nichts, das HIER
  // liefe, also ist es fuer dieses Telefon eine Pause, keine Aufnahme.
  function zeigeModus() {
    var an = modusAn();
    var sitzung = zustand.aufnahme;
    var pausiert = an && (!sitzung || sitzung.pausiert);
    fuss.dataset.interview = an ? '1' : '0';
    interviewKnopf.dataset.laeuft = an ? '1' : '0';
    interviewKnopf.dataset.pausiert = pausiert ? '1' : '0';
    if (!an) {
      interviewKnopf.textContent = TEXT.interview_an;
    } else if (pausiert) {
      interviewKnopf.textContent = TEXT.interview_pausiert.replace('{zeit}', formatiereUhr(sitzung));
    } else {
      interviewKnopf.textContent = TEXT.interview_laeuft.replace('{zeit}', formatiereUhr(sitzung));
    }
    // Ein Stopp ist unterwegs: bis der Bot ihn bestaetigt, kein neuer Start.
    // Laeuft Brainstorm ODER Diskussion, ist der Interview-Knopf ebenfalls
    // deaktiviert -- zwei gleichzeitige Aufnahmen auf demselben Mikrofon
    // sind keine Bedienung (dieselbe Regel wie PTT, Phase 4, 02.10.2026).
    // Re-Review (Task 6, Fund 1): ``nebenAn`` ist die EINE Stelle, die
    // diese Verknuepfung bildet. Vorher schrieben zeigeBrainstormModus()
    // und zeigeDiskussionModus() dieselbe Zeile erneut und unbedingt, mit
    // je nur ihrem eigenen Sitzungsflag -- die zuletzt gerufene Funktion
    // gewann und loeschte die Sperre der anderen, sobald deren eigene
    // Sitzung leer war (im Normalfall: Brainstorm laeuft, Diskussion nie
    // angefasst). Beide Funktionen setzen diese Felder seitdem nicht mehr.
    var nebenAn = !!zustand.brainstorm || !!zustand.diskussion;
    interviewKnopf.disabled = !!(zustand.wechsel && !zustand.wechsel.ziel) || nebenAn;
    // Padua Hotfix B6: ausserhalb von Phase 3 kein Angebot -- nie aber
    // verborgen bei laufender Aufnahme, Wechsel oder voller Schlange.
    interviewKnopf.hidden = !(zustand.knopfErlaubt || an || !!zustand.wechsel ||
                              zustand.warteschlange.length > 0);
    // Der grosse Knopf ist waehrend Laeuft/Pause nur noch eine Anzeige --
    // Pause/Weiter und Beenden stehen in der eigenen Leiste darunter.
    if (interviewAktionenFeld) { interviewAktionenFeld.hidden = !an; }
    if (interviewPauseKnopf) {
      interviewPauseKnopf.textContent = pausiert ? TEXT.interview_weiter : TEXT.interview_pause;
    }
    // Waehrend eine Interview-Aufnahme laeuft ODER pausiert ist, ist PTT
    // ausgeblendet (Birk, Punkt 2): zwei Mikrofone gleichzeitig sind keine
    // Bedienung, und eine Pause ist weiterhin "Modus an". Dieselbe
    // Zusammenfuehrung wie bei interviewKnopf.disabled oben.
    if (pttKnopf) { pttKnopf.hidden = an || !!zustand.wechsel || nebenAn; }
    // Beide Anzeigen bleiben im selben Takt synchron, egal welche der
    // beiden Funktionen zuerst gerufen wurde.
    zeigeBrainstormModus();
    zeigeDiskussionModus();
    // "Nebenknopf"-Stil am Interview-Knopf: sichtbar, sobald Brainstorm
    // ODER Diskussion angeboten wird oder laeuft -- aus derselben Formel
    // wie in den beiden Funktionen oben, hier einmal zusammengefuehrt statt
    // zweimal unbedingt ueberschrieben (derselbe Fund wie oben).
    var nebenSichtbar = !!zustand.brainstormErlaubt || !!zustand.brainstorm ||
                        !!zustand.diskussionErlaubt || !!zustand.diskussion ||
                        !!zustand.wechsel;
    interviewKnopf.classList.toggle('nebenknopf', nebenSichtbar);
  }

  // Duenner Wrapper, Null-Argument -- bleibt so aufrufbar fuer die vier
  // externen Aufrufstellen (Interview/Brainstorm/Diskussion/Wechsel-Start).
  // Die eigentliche Arbeit steht bei ``pttVerwirf()`` weiter unten, neben
  // dem Rest der PTT-Zustandsmaschine (Kanban-Karte Buehne/PTT, 04.10.2026)
  // -- Funktionsdeklarationen sind in diesem Geltungsbereich gehoistet, die
  // Reihenfolge der beiden Definitionen spielt also keine Rolle.
  function verwirfPtt() {
    var druck = zustand.ptt;
    if (!druck) { return; }
    pttVerwirf(druck);
  }

  // -- Pegel-Kalibrierung: der Ablauf (Birks Korrektur, 03.10.2026) --------
  //
  // "Eine Rauschschwelle, die nie gegen den echten Raum gemessen wurde, ist
  // geraten, nicht gesetzt." Die Zahlen aus _vad_werte() (RMS_SCHWELLE/
  // BODEN_FAKTOR) waren genau das -- Betreiber-Schaetzungen. Dieser Ablauf
  // ersetzt sie durch eine Messung GEGEN DIESEN RAUM, button-gated in jedem
  // Schritt: Birks ausdrueckliche Korrektur war, dass ein selbststartender
  // Countdown nicht garantiert, dass der Raum wirklich still ist, und eine
  // selbststartende Sprachmessung riskiert, vor dem ersten Wort zu messen
  // oder eine langsame Person zu verpassen. NICHTS hier startet von selbst
  // -- die EINE Ausnahme ist die automatische Rueckfrage nach 30s Stille
  // (sie ist selbst ein Knopf, nur einer, den das System der Gruppe
  // vorlegt statt dass die Gruppe ihn verlangt).

  function kalibrierungAktiv() {
    return fuss.dataset.vadKalibrierung !== '0';
  }

  function kalibrierungCacheLesen() {
    try {
      var boden = parseFloat(localStorage.getItem(KAL_LS_BODEN));
      var rede = parseFloat(localStorage.getItem(KAL_LS_REDE));
      var schwelle = parseFloat(localStorage.getItem(KAL_LS_SCHWELLE));
      if (isFinite(boden) && isFinite(rede) && isFinite(schwelle)) {
        return { boden: boden, rede: rede, schwelle: schwelle };
      }
    } catch (e) { /* localStorage kann fehlen (privater Modus, alter Browser) */ }
    return null;
  }

  function kalibrierungCacheSchreiben(boden, rede, schwelle) {
    try {
      localStorage.setItem(KAL_LS_BODEN, String(boden));
      localStorage.setItem(KAL_LS_REDE, String(rede));
      localStorage.setItem(KAL_LS_SCHWELLE, String(schwelle));
    } catch (e) { /* Skip bleibt ohnehin die Rueckfallebene */ }
  }

  // Eigener, kleiner AnalyserNode -- UNABHAENGIG von pegelAn()s eigenem (der
  // waehrend der Kalibrierung noch gar nicht laeuft, siehe
  // kalEntscheideOderStarte). Zwei getrennte Zaehler auf demselben Strom
  // sind erlaubt und einfacher als sie zu teilen.
  function kalBaueMesser(sitzung) {
    var Kontext = window.AudioContext || window.webkitAudioContext;
    if (!Kontext || !sitzung.strom) { return null; }
    try {
      var kontext = new Kontext();
      if (kontext.state === 'suspended' && kontext.resume) { kontext.resume(); }
      var messer = kontext.createAnalyser();
      messer.fftSize = 256;
      kontext.createMediaStreamSource(sitzung.strom).connect(messer);
      var zeitWerte = new Float32Array(messer.fftSize);
      return {
        rms: function () {
          messer.getFloatTimeDomainData(zeitWerte);
          var summe = 0;
          for (var i = 0; i < zeitWerte.length; i++) { summe += zeitWerte[i] * zeitWerte[i]; }
          return Math.sqrt(summe / zeitWerte.length);
        },
        schliesse: function () { try { kontext.close(); } catch (e) { /* schon zu */ } }
      };
    } catch (e) { return null; }
  }

  function kalAlleKnoepfeAus() {
    [kalStartKnopf, kalSprechenKnopf, kalNochmalHoerenKnopf, kalVersuchKnopf,
     kalWeiterTrotzdemKnopf, kalJaKnopf, kalNeinKnopf].forEach(function (b) {
      if (b) { b.hidden = true; }
    });
  }

  function kalZeigeSchritt(text, knoepfe) {
    kalAlleKnoepfeAus();
    if (kalBalkenFeld) { kalBalkenFeld.hidden = true; }
    if (kalText) { kalText.textContent = text; }
    (knoepfe || []).forEach(function (b) { if (b) { b.hidden = false; } });
  }

  // Wie kalZeigeSchritt, laesst aber den "deine Stimme vs. der Raum"-Balken
  // stehen, den kalZeigeBalken() davor sichtbar gemacht hat -- ein vom
  // Pegel-Mess-Balken (#pegel) bewusst getrenntes, kleines Element (siehe
  // 2a Schritt 5), nur innerhalb des Kalibrierungs-Panels.
  function kalZeigeSchrittMitBalken(text, knoepfe) {
    kalAlleKnoepfeAus();
    if (kalText) { kalText.textContent = text; }
    (knoepfe || []).forEach(function (b) { if (b) { b.hidden = false; } });
  }

  function kalZeigeBalken(redeMess, bodenMess) {
    if (!kalBalkenFeld) { return; }
    kalBalkenFeld.hidden = false;
    var deckel = Math.max(redeMess, bodenMess * 3) * 1.2 || 1;
    if (kalBalkenBalken) {
      kalBalkenBalken.style.width = Math.min(100, (redeMess / deckel) * 100) + '%';
    }
    if (kalBalkenMarke) {
      kalBalkenMarke.style.left = Math.min(100, ((bodenMess * 3) / deckel) * 100) + '%';
    }
  }

  function kalZeigePanel(an) {
    if (kalFeld) { kalFeld.hidden = !an; }
  }

  // Drei Schnitt-Varianten, alle nach demselben Muster wie schneideSegment()
  // (stop-current/start-next, keine Luecke) -- aber orthogonal zu ``grund``
  // (der serverseitig gegen einen festen Wertebereich geprueft wird und
  // etwas anderes bedeutet): eine normale Grenze ohne Markierung, der
  // Testsatz-Clip selbst (r._kalibrierung) und der verworfene 30s-Rueckfall
  // (r._kalVerworfen, nie verschickt -- siehe onstop in neuesSegment()).
  function kalSchneideOhneMarkierung(sitzung) {
    var alt = sitzung.recorder;
    if (!alt) { return; }
    if (alt.state !== 'inactive') { alt.stop(); }
    sitzung.recorder = neuesSegment(sitzung);
  }

  function kalSchneideAlsKalibrierung(sitzung) {
    var alt = sitzung.recorder;
    if (!alt) { return; }
    alt._kalibrierung = true;
    // Zuruecksetzen GENAU HIER, nicht erst in kalStarteTestTranskript(): der
    // Upload dieses Clips laeuft im Hintergrund weiter, auch waehrend die
    // "zu leise"-Rueckfrage (Schritt 5) noch auf dem Bildschirm steht --
    // Der Knopf kalWeiterTrotzdemKnopf ruft kalStarteTestTranskript() fuer GENAU DIESEN
    // Clip auf und braucht die message_id, die hier schon unterwegs sein
    // kann. Ein Reset dort wuerde eine laengst eingetroffene Antwort
    // wieder loeschen und auf eine Antwort warten, die nie mehr kommt.
    sitzung._kalMessageId = null;
    if (sitzung._kal) { sitzung._kal.ueberschrieben = false; }
    if (alt.state !== 'inactive') { alt.stop(); }
    sitzung.recorder = neuesSegment(sitzung);
  }

  function kalSchneideUndVerwerfen(sitzung) {
    var alt = sitzung.recorder;
    if (!alt) { return; }
    alt._kalVerworfen = true;
    if (alt.state !== 'inactive') { alt.stop(); }
    sitzung.recorder = neuesSegment(sitzung);
  }

  function kalAufraeumen(sitzung) {
    var k = sitzung._kal;
    if (!k) { return; }
    if (k.stilleTakt) { clearInterval(k.stilleTakt); }
    if (k.warteTakt) { clearInterval(k.warteTakt); }
    if (k.sammelTakt) { clearInterval(k.sammelTakt); }
    if (k.messer) { k.messer.schliesse(); }
    sitzung._kal = null;
  }

  // -- Schritt 1: Ankuendigung ---------------------------------------------

  function kalibrierungStarte(sitzung) {
    var messer = kalBaueMesser(sitzung);
    if (!messer || !kalFeld) {
      // Keine Messung moeglich (kein AudioContext/kein Panel im Markup) --
      // derselbe Rueckfall wie der Kill-Switch, byte-gleich zur festen
      // Formel: sitzung.vadSchwelleFix bleibt unerreichbar fuer
      // pegelAn(), stattdessen nichts setzen und direkt starten.
      kalStarteEchteSchnitte(sitzung);
      return;
    }
    sitzung._kal = { messer: messer };
    sitzung._kalZuLeiseZaehler = sitzung._kalZuLeiseZaehler || 0;
    kalZeigePanel(true);
    kalZeigeSchritt(TEXT.kal_ankuendigung, [kalStartKnopf]);
  }

  // -- Schritt 2: die 5s-Stillemessung (nur nach Knopfdruck) ---------------

  function kalStarteStille(sitzung) {
    var k = sitzung._kal;
    if (!k || !k.messer) { return; }
    var samples = [];
    var start = Date.now();
    var restS = Math.ceil(KAL_STILLE_MS / 1000);
    kalZeigeSchritt(TEXT.kal_stille.replace('{s}', String(restS)), []);
    k.stilleTakt = setInterval(function () {
      samples.push(k.messer.rms());
      var vergangen = Date.now() - start;
      var rest = Math.max(0, Math.ceil((KAL_STILLE_MS - vergangen) / 1000));
      if (rest !== restS) {
        restS = rest;
        if (kalText) { kalText.textContent = TEXT.kal_stille.replace('{s}', String(restS)); }
      }
      if (vergangen >= KAL_STILLE_MS) {
        clearInterval(k.stilleTakt);
        k.stilleTakt = null;
        k.bodenMess = kalMedian(samples);
        kalZeigeSchritt(TEXT.kal_sprechen_ankuendigung, [kalSprechenKnopf]);
      }
    }, 120);
  }

  // -- Schritt 3/4: die Sprachmessung (nur nach Knopfdruck) ----------------

  function kalStarteSprechen(sitzung) {
    var k = sitzung._kal;
    if (!k) { return; }
    kalSchneideOhneMarkierung(sitzung);   // beendet das Vor-Sprechen-Segment normal
    kalZeigeSchritt(TEXT.kal_hoeren, []);
    kalWarteAufStimme(sitzung);
  }

  function kalWarteAufStimme(sitzung) {
    var k = sitzung._kal;
    if (!k || !k.messer) { return; }
    var start = Date.now();
    k.warteTakt = setInterval(function () {
      var rms = k.messer.rms();
      if (rms > 3 * k.bodenMess) {
        clearInterval(k.warteTakt);
        k.warteTakt = null;
        kalSammleStimme(sitzung, rms);
        return;
      }
      if (Date.now() - start >= KAL_WARTE_MAX_MS) {
        clearInterval(k.warteTakt);
        k.warteTakt = null;
        // Nichts gehoert: der Clip seit "Start speaking" wird verworfen,
        // es gibt nichts zu testen (2a Schritt 4).
        kalSchneideUndVerwerfen(sitzung);
        kalZeigeSchritt(TEXT.kal_nichts_gehoert, [kalNochmalHoerenKnopf]);
      }
    }, 120);
  }

  // Der In-Flow-Rueckfrage-Knopf (#kalibrierung-nochmal-hoeren, NICHT
  // #kalibrierung-neu -- unterschiedliche ids, unterschiedlicher Umfang):
  // schneidet einen frischen Clip an genau diesem Klick und startet NUR die
  // 30s-Wartezeit neu. boden_mess aus Schritt 2 bleibt stehen.
  function kalNochmalHoeren(sitzung) {
    var k = sitzung._kal;
    if (!k) { return; }
    kalSchneideOhneMarkierung(sitzung);
    kalZeigeSchritt(TEXT.kal_hoeren, []);
    kalWarteAufStimme(sitzung);
  }

  function kalSammleStimme(sitzung, ersteRms) {
    var k = sitzung._kal;
    var samples = [ersteRms];
    var stimmMs = 120;   // die Probe, die die Stimme erkannt hat, zaehlt mit
    var fensterStart = Date.now();
    k.sammelTakt = setInterval(function () {
      var rms = k.messer.rms();
      samples.push(rms);   // Pausen zaehlen mit in die Perzentil-Grundlage
      if (rms > 3 * k.bodenMess) { stimmMs += 120; }
      if (stimmMs >= KAL_SPRACH_MS ||
          (Date.now() - fensterStart) >= KAL_SPRACH_FENSTER_MS) {
        clearInterval(k.sammelTakt);
        k.sammelTakt = null;
        k.redeMess = kalPerzentil(samples, 0.8);
        k.stimmMsGemessen = stimmMs;
        kalSchneideAlsKalibrierung(sitzung);   // DER Testsatz-Clip
        kalPruefeZuLeise(sitzung);
      }
    }, 120);
  }

  // -- Schritt 5: "zu leise"? (deterministisch, kein Modellaufruf) --------

  function kalPruefeZuLeise(sitzung) {
    var k = sitzung._kal;
    if (kalZuLeise(k.redeMess, k.bodenMess, k.stimmMsGemessen)) {
      kalMeldeZuLeise(sitzung);
      return;
    }
    kalStarteTestTranskript(sitzung);
  }

  // Gemeinsamer Zaehler fuer Schritt 5 UND den Nachpruef-Zweig von Schritt 7
  // (leere/zu kurze Bestaetigungsantwort zaehlt wie "zu leise") -- derselbe
  // Zaehler, dieselbe Staffelung (1./2.+), wie die Karte verlangt.
  function kalMeldeZuLeise(sitzung) {
    sitzung._kalZuLeiseZaehler = (sitzung._kalZuLeiseZaehler || 0) + 1;
    var k = sitzung._kal;
    kalZeigeBalken(k ? (k.redeMess || 0) : 0, k ? (k.bodenMess || 0) : 0);
    if (sitzung._kalZuLeiseZaehler <= 1) {
      kalZeigeSchrittMitBalken(
        TEXT.kal_zu_leise + ' ' + TEXT.kal_zu_leise_1, [kalVersuchKnopf],
      );
      return;
    }
    kalZeigeSchrittMitBalken(
      TEXT.kal_zu_leise + ' ' + TEXT.kal_zu_leise_2,
      [kalVersuchKnopf, kalWeiterTrotzdemKnopf],
    );
    // Gruppenweiter Hinweis fuer spaetere Sitzungen (2a Schritt 5, 2f) --
    // best effort: schlaegt der Upload fehl, bleibt es bei der lokalen
    // Staffelung dieser Sitzung, nichts davon haengt an der Antwort.
    postJson(`chat/kalibrierung`, {}).catch(function () { /* best effort */ });
  }

  function kalVersuchErneut(sitzung) {
    // "restarts only step 4" -- zurueck auf die Schritt-3-Ankuendigung samt
    // ihrem Knopf, NICHT automatisch wieder ins Zuhoeren (nichts startet
    // von selbst).
    kalZeigeSchritt(TEXT.kal_sprechen_ankuendigung, [kalSprechenKnopf]);
  }

  function kalWeiterTrotzdem(sitzung) {
    // Merkt sich, dass die Gruppe die Pegel-Warnung ausdruecklich
    // uebergangen hat -- kalAntwortJa() ueberspringt deshalb GENAU den
    // Pegel-Vergleich (nicht den Text-Check) bei der Schritt-7-Pruefung,
    // sonst wuerde dieselbe, unveraenderte Messung dort sofort wieder
    // "zu leise" sagen und der Weiter-trotzdem-Knopf waere wirkungslos -- entgegen
    // 2a Schritt 5: "nothing here ever permanently blocks the group".
    if (sitzung._kal) { sitzung._kal.ueberschrieben = true; }
    kalStarteTestTranskript(sitzung);
  }

  // -- Schritt 6: der Testsatz --------------------------------------------
  //
  // Der Clip ist schon unterwegs (kalSchneideAlsKalibrierung() hat ihn
  // geschnitten, sein onstop reiht ihn ganz normal in dieselbe
  // Warteschlange ein wie jedes andere Segment) -- hier wird nur auf seine
  // message_id (arbeiteAb()) und danach auf sein Transkript (der Poll,
  // zustand.kalibrierung) gewartet.

  function kalStarteTestTranskript(sitzung) {
    kalZeigeSchritt(TEXT.kal_transkribiert_warten, []);
    // KEIN Reset von sitzung._kalMessageId hier -- kalSchneideAlsKalibrierung()
    // hat ihn schon auf null gesetzt, als der Clip geschnitten wurde, und
    // der Upload kann seitdem (auch waehrend der "zu leise"-Rueckfrage)
    // schon durchgelaufen sein.
    kalWarteAufUpload(sitzung, 0);
  }

  function kalWarteAufUpload(sitzung, versuche) {
    if (!sitzung._kal) { return; }   // Ablauf inzwischen verlassen (Skip/Neu)
    if (sitzung._kalMessageId != null) {
      kalWarteAufTranskript(sitzung);
      return;
    }
    if (versuche > 100) {   // ~20s Geduld -- danach defensiv wie "nichts gehoert"
      kalZeigeSchritt(TEXT.kal_nichts_gehoert, [kalNochmalHoerenKnopf]);
      return;
    }
    setTimeout(function () { kalWarteAufUpload(sitzung, versuche + 1); }, 200);
  }

  function kalWarteAufTranskript(sitzung) {
    if (!sitzung._kal) { return; }
    var info = zustand.kalibrierung;
    if (info && info.message_id === sitzung._kalMessageId) {
      if (info.status === 'fertig') {
        kalZeigeBestaetigung(sitzung, info.transkript || '');
        return;
      }
      if (info.status === 'fehler') {
        kalMeldeZuLeise(sitzung);   // wie eine leere Antwort behandeln
        return;
      }
    }
    setTimeout(function () { kalWarteAufTranskript(sitzung); }, 400);
  }

  // -- Schritt 7: Bestaetigung ----------------------------------------------

  function kalZeigeBestaetigung(sitzung, transkript) {
    var k = sitzung._kal;
    if (!k) { return; }
    k.letzterTranskript = transkript;
    kalZeigeSchritt(
      TEXT.kal_bestaetigung.replace('{transkript}', transkript),
      [kalJaKnopf, kalNeinKnopf],
    );
  }

  function kalAntwortNein(sitzung) {
    kalMeldeZuLeise(sitzung);
  }

  function kalAntwortJa(sitzung) {
    var k = sitzung._kal;
    if (!k) { return; }
    var transkript = (k.letzterTranskript || '').trim();
    var woerter = transkript ? transkript.split(/\s+/).filter(Boolean) : [];
    // k.ueberschrieben (gesetzt von kalWeiterTrotzdem): die Gruppe hat die
    // Pegel-Warnung schon einmal bewusst uebergangen -- derselbe Pegel
    // wuerde hier sonst dieselbe "zu leise" zurueckgeben und den Knopf
    // wirkungslos machen. Der Text-Check (leer/zu kurz) bleibt IMMER aktiv:
    // das ist eine neue Information (das Transkript selbst), keine
    // Wiederholung der Pegel-Messung.
    var zuLeiseFinal = (!k.ueberschrieben && kalZuLeise(k.redeMess, k.bodenMess, k.stimmMsGemessen)) ||
      !transkript || woerter.length < 3;
    if (zuLeiseFinal) {
      kalMeldeZuLeise(sitzung);
      return;
    }
    var schwelle = kalSchwelle(k.bodenMess, k.redeMess);
    // Zweite, LOOSERE Pruefung (2 statt 3): eine defensive Untergrenze auf
    // den ENDWERT, keine Wiederholung -- die Gruppe hat das Transkript
    // schon bestaetigt.
    if (k.redeMess < 2 * k.bodenMess) {
      meldeFehler(TEXT.kal_floor_hinweis);
      schwelle = KAL_SCHWELLE_FALLBACK;
    } else {
      meldeFehler(TEXT.kal_erfolg);
    }
    kalibrierungCacheSchreiben(k.bodenMess, k.redeMess, schwelle);
    kalibrierungBeenden(sitzung, schwelle, k.bodenMess);
  }

  // -- Schritt 8: Skip -------------------------------------------------------

  function kalibrierungSkip(sitzung) {
    kalAufraeumen(sitzung);
    kalZeigePanel(false);
    // Keine localStorage-Schreibung (E6-Ausnahme bleibt eng): Skip ist ein
    // einmaliger Rueckfall fuer DIESE Sitzung, kein Messergebnis, das das
    // naechste Mal wert waere, es zu cachen.
    kalibrierungBeenden(sitzung, KAL_SCHWELLE_FALLBACK, KAL_SCHWELLE_FALLBACK / 3);
  }

  // -- Gemeinsamer Abschluss: Schwelle anwenden, echte Schnitte starten ----

  function stoppePegelAn(sitzung) {
    if (sitzung.pegelTakt) { clearInterval(sitzung.pegelTakt); sitzung.pegelTakt = null; }
    if (sitzung.kontext) {
      try { sitzung.kontext.close(); } catch (e) { /* schon zu */ }
      sitzung.kontext = null;
    }
    sitzung.vadAktiv = false;
  }

  // Was vorher (ohne Kalibrierung) direkt in beginneAufnahme() stand:
  // pegelAn() an, oder ohne AnalyserNode der feste Segment-Takt. Eigene
  // Funktion, weil jetzt ZWEI Aufrufer sie brauchen -- der Normalfall
  // (beginneAufnahme) und das Ende eines Kalibrierungslaufs.
  function kalStarteEchteSchnitte(sitzung) {
    stoppePegelAn(sitzung);   // falls #kalibrierung-neu einen frueheren Lauf stoppt
    pegelAn(sitzung);
    if (!sitzung.vadAktiv) {
      if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); }
      sitzung.segmentTakt = setInterval(function () {
        if (!sitzung.recorder) { return; }
        var alt = sitzung.recorder;
        alt.stop();
        sitzung.recorder = neuesSegment(sitzung);
      }, SEGMENT_MS);
    }
  }

  function kalibrierungBeenden(sitzung, schwelleFix, bodenMess) {
    kalAufraeumen(sitzung);
    kalZeigePanel(false);
    sitzung.vadBodenMess = bodenMess;
    sitzung.vadSchwelleFix = schwelleFix;
    sitzung.kalibriert = true;
    kalStarteEchteSchnitte(sitzung);
  }

  // Der einmalige Hinweis "Handy herumgeben" (2f): gruppenweiter Zustand
  // (zustand.kalibrierungModus), aber nur EINMAL je JS-Sitzungsobjekt
  // gezeigt -- ein Pause/Weiter auf DERSELBEN Sitzung ruft
  // kalEntscheideOderStarte() zwar erneut auf, trifft aber schon
  // sitzung._kalibrierungEntschieden an. Mangels einer existierenden
  // Task-4-Infrastruktur (die Karte verweist darauf, sie ist aber noch
  // nicht gebaut) ist dieser Wurf hier die naheliegende Wahl: ein Flag auf
  // der Sitzung, dieselbe Groessenordnung wie sitzung.kalibriert.
  function kalZeigeHerumreichenErinnerungWennNeu(sitzung) {
    if (sitzung._kalibrierungEntschieden) { return; }
    sitzung._kalibrierungEntschieden = true;
    if (zustand.kalibrierungModus === 'herumreichen' && kalErinnerungFeld) {
      kalErinnerungFeld.textContent = TEXT.kal_herumreichen_erinnerung;
      kalErinnerungFeld.hidden = false;
      setTimeout(function () { kalErinnerungFeld.hidden = true; }, 10000);
    }
  }

  // Die EINE Weiche zwischen cache/kill-switch/frischem Ablauf -- aufgerufen
  // aus beginneAufnahme() UND von #kalibrierung-neu (das sitzung.kalibriert
  // vorher auf false setzt und dieselbe Weiche erneut anstoesst, ohne den
  // Cache zu pruefen, siehe kalibrierungNeu()).
  function kalEntscheideOderStarte(sitzung) {
    kalZeigeHerumreichenErinnerungWennNeu(sitzung);
    if (sitzung.kalibriert) {
      kalStarteEchteSchnitte(sitzung);
      return;
    }
    if (!kalibrierungAktiv()) {
      sitzung.kalibriert = true;
      kalStarteEchteSchnitte(sitzung);
      return;
    }
    var cache = kalibrierungCacheLesen();
    if (cache) {
      sitzung.vadBodenMess = cache.boden;
      sitzung.vadSchwelleFix = cache.schwelle;
      sitzung.kalibriert = true;
      kalStarteEchteSchnitte(sitzung);
      return;
    }
    kalibrierungStarte(sitzung);
  }

  // Panel-level Messen-Knopf (#kalibrierung-neu, bewusst andere id als
  // der In-Flow-Knopf #kalibrierung-nochmal-hoeren -- unterschiedlicher
  // Umfang): faehrt die GANZE Sitzung neu, ignoriert jeden Cache, und
  // wendet das Ergebnis auf die LAUFENDE Aufnahme an, ohne sie zu stoppen.
  function kalibrierungNeu(sitzung) {
    if (!sitzung) { return; }
    stoppePegelAn(sitzung);
    if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); sitzung.segmentTakt = null; }
    sitzung.kalibriert = false;
    kalibrierungStarte(sitzung);
  }

  if (kalStartKnopf) {
    kalStartKnopf.addEventListener('click', function () {
      kalStarteStille(zustand.aufnahme || zustand.brainstorm || zustand.diskussion);
    });
  }
  if (kalSprechenKnopf) {
    kalSprechenKnopf.addEventListener('click', function () {
      kalStarteSprechen(zustand.aufnahme || zustand.brainstorm || zustand.diskussion);
    });
  }
  if (kalNochmalHoerenKnopf) {
    kalNochmalHoerenKnopf.addEventListener('click', function () {
      kalNochmalHoeren(zustand.aufnahme || zustand.brainstorm || zustand.diskussion);
    });
  }
  if (kalVersuchKnopf) {
    kalVersuchKnopf.addEventListener('click', function () {
      kalVersuchErneut(zustand.aufnahme || zustand.brainstorm || zustand.diskussion);
    });
  }
  if (kalWeiterTrotzdemKnopf) {
    kalWeiterTrotzdemKnopf.addEventListener('click', function () {
      kalWeiterTrotzdem(zustand.aufnahme || zustand.brainstorm || zustand.diskussion);
    });
  }
  if (kalJaKnopf) {
    kalJaKnopf.addEventListener('click', function () {
      kalAntwortJa(zustand.aufnahme || zustand.brainstorm || zustand.diskussion);
    });
  }
  if (kalNeinKnopf) {
    kalNeinKnopf.addEventListener('click', function () {
      kalAntwortNein(zustand.aufnahme || zustand.brainstorm || zustand.diskussion);
    });
  }
  if (kalSkipKnopf) {
    kalSkipKnopf.addEventListener('click', function () {
      kalibrierungSkip(zustand.aufnahme || zustand.brainstorm || zustand.diskussion);
    });
  }
  if (kalNeuKnopf) {
    kalNeuKnopf.addEventListener('click', function () {
      kalibrierungNeu(zustand.aufnahme || zustand.brainstorm || zustand.diskussion);
    });
  }

  // Beginnt die tatsaechliche Aufzeichnung auf einer Sitzung, deren
  // Mikrofon gerade bereit wurde: Startzeitpunkt, Recorder, Segment-Takt,
  // Uhr und Pegel. Gemeinsame Stelle fuer starteInterview() und
  // fortsetzeInterview() -- und seit dem zweiten Re-Review (Befund: der
  // Pause-Schutz lag nur in starteInterview()'s .then(), nicht hier, also
  // NICHT "automatisch fuer beide Aufrufer" wie der alte Kommentar
  // behauptete) auch die EINZIGE Stelle, die prueft, ob inzwischen
  // pausiert wurde. Beide Aufrufer setzen sitzung.pausiert selbst auf
  // false, bevor ihr jeweils eigenes holeStrom() beginnt (starteInterview()
  // im Sitzungs-Objekt bei der Erstellung, fortsetzeInterview() explizit
  // kurz vor dem Aufruf) -- sitzung.pausiert === true heisst hier also fuer
  // BEIDE Aufrufer gleichermassen dasselbe: waehrend des Wartens auf das
  // Mikrofon kam eine Pause dazwischen, also gar nicht erst anfangen,
  // Mikrofon sofort wieder frei.
  //
  // Task 2 (Kanban-Karte Mithoeren SICHER/Kalibrierung): die Aufnahme
  // startet weiter SOFORT (sonst gehen die ersten Worte der echten
  // Diskussion verloren) -- gegated ist allein kalEntscheideOderStarte()
  // (pegelAn() + der Segment-Takt-Rueckfall), nie neuesSegment() selbst.
  function beginneAufnahme(sitzung) {
    if (sitzung.pausiert) {
      gibFrei(sitzung);
      return;
    }
    sitzung.legStart = Date.now();
    sitzung.recorder = neuesSegment(sitzung);
    sitzung.vadSegmentStart = Date.now();
    sitzung.vadSpeechMs = 0;
    sitzung.vadLetzteRede = sitzung.vadSegmentStart;
    sitzung.gestartet = true;
    uhrAn(sitzung);
    kalEntscheideOderStarte(sitzung);
  }

  // -- Brainstorm mithoeren (Phase 4, nur Web, 02.10.2026) ------------------
  //
  // Dieselbe Segment-Mechanik wie beim Interview (neuesSegment,
  // schneideSegment, pegelAn, beginneAufnahme sind bereits generisch ueber
  // die uebergebene Sitzung) -- aber OHNE Modus-Befehl: ein
  // Brainstorm-Segment ist serverseitig immer eine gewoehnliche
  // 'kurz'-Aufnahme, es gibt nichts anzumelden oder zu bestaetigen.
  // sitzung.art = 'brainstorm' schaltet bereit() auf "immer senden" (siehe
  // dort); fertigEingereiht bleibt dauerhaft true, damit pruefeEnde() NIE
  // ein 'befehl' einreiht. Bewusst eigene, kleinere Funktionen statt eines
  // sitzung.art-Zweigs mitten in starteInterview()/pausiereInterview()/
  // beendeInterview(): die dort gehaerteten Rennbedingungen (mehrere
  // "Re-Review"-Runden) sollen fuer den bestehenden, getesteten Weg
  // unberuehrt bleiben.

  function zeigeBrainstormModus() {
    if (!brainstormKnopf) { return; }
    var sitzung = zustand.brainstorm;
    var an = !!sitzung;
    var pausiert = an && sitzung.pausiert;
    brainstormKnopf.dataset.laeuft = an ? '1' : '0';
    brainstormKnopf.dataset.pausiert = pausiert ? '1' : '0';
    if (!an) {
      brainstormKnopf.textContent = TEXT.brainstorm_an;
    } else if (pausiert) {
      brainstormKnopf.textContent = TEXT.interview_pausiert.replace('{zeit}', formatiereUhr(sitzung));
    } else {
      brainstormKnopf.textContent = TEXT.brainstorm_laeuft.replace('{zeit}', formatiereUhr(sitzung));
    }
    // Zwei gleichzeitige Aufnahmen auf demselben Mikrofon sind keine
    // Bedienung (dieselbe Regel wie PTT vs. Interview). Waehrend ein
    // Interview-Stopp unterwegs ist (wechsel.ziel === false), ist modusAn()
    // schon wieder false -- genau wie beim Interview-Knopf selbst
    // (zeigeModus()) wird deshalb zusaetzlich auf ein laufendes wechsel
    // geprueft, sonst saehe der Knopf kurz bedienbar aus, obwohl
    // starteBrainstorm() ihn wegen desselben zustand.wechsel ablehnt.
    // Abschluss-Review (Finding 2): auch gegen zustand.diskussion gesperrt --
    // symmetrisch zur bestehenden Sperre von starteDiskussion() gegen
    // zustand.brainstorm (095e6e9). Ohne das blieb der Knopf bedienbar,
    // waehrend eine Diskussion-Sitzung (Phase 1) noch lief, z. B. wenn eine
    // Gruppe den Diskussion-Knopf in Phase 1 nie beendet und spaeter in
    // Phase 4 den Brainstorm-Knopf drueckt -- zwei MediaRecorder auf
    // demselben Mikrofon.
    brainstormKnopf.disabled = modusAn() || !!zustand.wechsel || !!zustand.diskussion;
    // Task 2 (Kanban-Karte Buehne/PTT): ausserhalb Phase 4 kein Angebot --
    // nie aber verborgen bei laufender Sitzung oder Wechsel, dieselbe Regel
    // wie beim Interview-Knopf (zeigeModus()). Die ``nebenknopf``-Klasse am
    // Interview-Knopf folgt derselben Sichtbarkeit wie das Server-Markup.
    var sichtbar = zustand.brainstormErlaubt || an || !!zustand.wechsel;
    brainstormKnopf.hidden = !sichtbar;
    if (brainstormAktionenFeld) { brainstormAktionenFeld.hidden = !an; }
    if (brainstormPauseKnopf) {
      brainstormPauseKnopf.textContent = pausiert ? TEXT.interview_weiter : TEXT.interview_pause;
    }
    // interviewKnopf.disabled/classList und pttKnopf.hidden werden seit
    // Task 6, Fix 1 NICHT mehr hier gesetzt -- das tut zeigeModus() einmal,
    // zusammengefuehrt mit zustand.diskussion (siehe dort).
  }

  function starteBrainstorm() {
    // Abschluss-Review (Finding 2): auch gegen zustand.diskussion gesperrt,
    // wie starteDiskussion()/pttPointerDown() es bereits tun -- sonst koennte eine
    // Gruppe, die eine Diskussion-Sitzung (Phase 1) nie beendet hat und in
    // Phase 4 weiterarbeitet, ueber den Brainstorm-Knopf einen zweiten
    // Recorder auf demselben Mikrofon starten.
    if (zustand.brainstorm || modusAn() || zustand.wechsel || zustand.diskussion) { return; }
    if (zustand.ptt) { verwirfPtt(); }
    var sitzung = {
      art: 'brainstorm',
      strom: null, recorder: null, kontext: null, pegelTakt: null,
      segmentTakt: null, offen: 0, gestartet: false, beendet: false,
      verworfen: false, angehalten: false, geparkt: [],
      fertigEingereiht: true, naechsteNr: 0, einzureihen: 0, fertige: {},
      pausiert: false, erfassteMs: 0, legStart: null, mikroUnterwegs: true,
      fortsetzend: false, hinweisGezeigt: false
    };
    zustand.brainstorm = sitzung;
    zeigeBrainstormModus();
    holeStrom().then(function (strom) {
      sitzung.mikroUnterwegs = false;
      sitzung.strom = strom;
      if (sitzung.beendet) { gibFrei(sitzung); return; }
      sitzung.gestartet = true;
      beginneAufnahme(sitzung);
      zeigeBrainstormModus();
    }).catch(function () {
      sitzung.mikroUnterwegs = false;
      sitzung.verworfen = true;
      sitzung.beendet = true;
      if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); }
      if (sitzung.recorder && sitzung.recorder.state !== 'inactive') {
        try { sitzung.recorder.stop(); } catch (e) { /* schon aus */ }
      }
      sitzung.recorder = null;
      gibFrei(sitzung);
      entferneAuftraege(sitzung);
      if (zustand.brainstorm === sitzung) { zustand.brainstorm = null; }
      anzeigeAus();
      zeigeBrainstormModus();
      meldeFehler(TEXT.fehler_mikro);
    });
  }

  function pausiereBrainstorm() {
    var sitzung = zustand.brainstorm;
    if (!sitzung || sitzung.pausiert || sitzung.verworfen || sitzung.beendet) { return; }
    if (sitzung.mikroUnterwegs) {
      sitzung.pausiert = true;
      zeigeBrainstormModus();
      return;
    }
    sitzung.erfassteMs += Date.now() - sitzung.legStart;
    sitzung.legStart = null;
    sitzung.pausiert = true;
    if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); sitzung.segmentTakt = null; }
    var alt = sitzung.recorder;
    sitzung.recorder = null;
    if (alt && sitzung.vadAktiv) { alt._grund = 'ende'; alt._redeMs = sitzung.vadSpeechMs; }
    if (alt && alt.state !== 'inactive') { alt.stop(); }
    gibFrei(sitzung);
    if (zustand.uhrTakt) { clearInterval(zustand.uhrTakt); zustand.uhrTakt = null; }
    if (uhrFeld) { uhrFeld.textContent = TEXT.uhr.replace('{zeit}', formatiereUhr(sitzung)); }
    zeigeBrainstormModus();
  }

  function fortsetzeBrainstorm() {
    var sitzung = zustand.brainstorm;
    // Dieselben Waechter wie fortsetzeInterview(): "pausiert" nur einmal
    // zuruecknehmen, und eine Sperrklinke (fortsetzend) gegen einen
    // hastigen Doppeldruck, der sonst zwei Recorder auf demselben Mikrofon
    // startete.
    if (!sitzung || !sitzung.pausiert || sitzung.verworfen || sitzung.beendet ||
        sitzung.fortsetzend) { return; }
    if (sitzung.mikroUnterwegs) { sitzung.pausiert = false; return; }
    sitzung.pausiert = false;
    sitzung.fortsetzend = true;
    sitzung.mikroUnterwegs = true;
    holeStrom().then(function (strom) {
      sitzung.mikroUnterwegs = false;
      sitzung.fortsetzend = false;
      if (!zustand.brainstorm || zustand.brainstorm !== sitzung || sitzung.beendet) {
        strom.getTracks().forEach(function (t) { t.stop(); });
        return;
      }
      sitzung.strom = strom;
      beginneAufnahme(sitzung);
      zeigeBrainstormModus();
    }).catch(function () {
      sitzung.mikroUnterwegs = false;
      sitzung.fortsetzend = false;
      sitzung.pausiert = true;
      zeigeBrainstormModus();
      meldeFehler(TEXT.fehler_mikro);
    });
    zeigeBrainstormModus();
  }

  function beendeBrainstorm() {
    var sitzung = zustand.brainstorm;
    if (!sitzung) { return; }
    zustand.brainstorm = null;
    anzeigeAus();
    if (!sitzung.gestartet) {
      sitzung.beendet = true;
      zeigeBrainstormModus();
      return;
    }
    sitzung.beendet = true;
    if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); sitzung.segmentTakt = null; }
    var letzter = sitzung.recorder;
    sitzung.recorder = null;
    if (letzter && sitzung.vadAktiv) { letzter._grund = 'ende'; letzter._redeMs = sitzung.vadSpeechMs; }
    if (letzter && letzter.state !== 'inactive') { letzter.stop(); }
    // Anders als beendeInterview(): pruefeEnde() tut bei Brainstorm NIE
    // etwas (fertigEingereiht bleibt immer true), also wird das Mikrofon
    // HIER sofort freigegeben -- wie bei pausiereInterview(), nicht erst im
    // onstop.
    gibFrei(sitzung);
    zeigeBrainstormModus();
  }

  // -- Hintergrund-Mithoeren Phase 1 (Padua Phase 1+2 Umbau, 03.10.2026,
  //    Task 6) -----------------------------------------------------------
  //
  // Derselbe Aufbau wie Brainstorm oben -- eigener Zustandsslot
  // (zustand.diskussion, nicht zustand.brainstorm), eigene DOM-Elemente
  // (#diskussion, #diskussion-pause, #diskussion-beenden), aber dieselbe
  // Segment-Mechanik OHNE Modus-Befehl: ein Diskussion-Segment ist
  // serverseitig immer eine gewoehnliche 'kurz'-Aufnahme. sitzung.art =
  // 'diskussion' schaltet bereit() auf "immer senden" (siehe dort);
  // fertigEingereiht bleibt dauerhaft true, damit pruefeEnde() NIE ein
  // 'befehl' einreiht.

  function zeigeDiskussionModus() {
    if (!diskussionKnopf) { return; }
    var sitzung = zustand.diskussion;
    var an = !!sitzung;
    var pausiert = an && sitzung.pausiert;
    diskussionKnopf.dataset.laeuft = an ? '1' : '0';
    diskussionKnopf.dataset.pausiert = pausiert ? '1' : '0';
    if (!an) {
      diskussionKnopf.textContent = TEXT.diskussion_an;
    } else if (pausiert) {
      diskussionKnopf.textContent = TEXT.interview_pausiert.replace('{zeit}', formatiereUhr(sitzung));
    } else {
      diskussionKnopf.textContent = TEXT.diskussion_laeuft.replace('{zeit}', formatiereUhr(sitzung));
    }
    // Zwei gleichzeitige Aufnahmen auf demselben Mikrofon sind keine
    // Bedienung (dieselbe Regel wie bei Brainstorm/PTT vs. Interview).
    diskussionKnopf.disabled = modusAn() || !!zustand.wechsel;
    // Ausserhalb Phase 1 kein Angebot -- nie aber verborgen bei laufender
    // Sitzung oder Wechsel, dieselbe Regel wie beim Brainstorm-Knopf.
    var sichtbar = zustand.diskussionErlaubt || an || !!zustand.wechsel;
    diskussionKnopf.hidden = !sichtbar;
    if (diskussionAktionenFeld) { diskussionAktionenFeld.hidden = !an; }
    if (diskussionPauseKnopf) {
      diskussionPauseKnopf.textContent = pausiert ? TEXT.interview_weiter : TEXT.interview_pause;
    }
    // interviewKnopf.disabled/classList und pttKnopf.hidden werden seit
    // Task 6, Fix 1 NICHT mehr hier gesetzt -- das tut zeigeModus() einmal,
    // zusammengefuehrt mit zustand.brainstorm (siehe dort). Vorher
    // ueberschrieb dieser Abschnitt unbedingt, mit nur dem eigenen Flag,
    // was zeigeBrainstormModus() kurz zuvor gesetzt hatte.
  }

  function starteDiskussion() {
    // Re-Review (Task 6, Fund 2): auch gegen zustand.brainstorm gesperrt,
    // wie starteInterview()/pttPointerDown() es bereits tun -- sonst koennte ein
    // Phase-4-zu-1-Wechsel mit noch laufendem Brainstorm auf einem anderen
    // Tab einen zweiten Recorder auf demselben Mikrofon starten.
    if (zustand.diskussion || modusAn() || zustand.wechsel || zustand.brainstorm) { return; }
    if (zustand.ptt) { verwirfPtt(); }
    var sitzung = {
      art: 'diskussion',
      strom: null, recorder: null, kontext: null, pegelTakt: null,
      segmentTakt: null, offen: 0, gestartet: false, beendet: false,
      verworfen: false, angehalten: false, geparkt: [],
      fertigEingereiht: true, naechsteNr: 0, einzureihen: 0, fertige: {},
      pausiert: false, erfassteMs: 0, legStart: null, mikroUnterwegs: true,
      fortsetzend: false
    };
    zustand.diskussion = sitzung;
    zeigeDiskussionModus();
    holeStrom().then(function (strom) {
      sitzung.mikroUnterwegs = false;
      sitzung.strom = strom;
      if (sitzung.beendet) { gibFrei(sitzung); return; }
      sitzung.gestartet = true;
      beginneAufnahme(sitzung);
      zeigeDiskussionModus();
    }).catch(function () {
      sitzung.mikroUnterwegs = false;
      sitzung.verworfen = true;
      sitzung.beendet = true;
      if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); }
      if (sitzung.recorder && sitzung.recorder.state !== 'inactive') {
        try { sitzung.recorder.stop(); } catch (e) { /* schon aus */ }
      }
      sitzung.recorder = null;
      gibFrei(sitzung);
      entferneAuftraege(sitzung);
      if (zustand.diskussion === sitzung) { zustand.diskussion = null; }
      anzeigeAus();
      zeigeDiskussionModus();
      meldeFehler(TEXT.fehler_mikro);
    });
  }

  function pausiereDiskussion() {
    var sitzung = zustand.diskussion;
    if (!sitzung || sitzung.pausiert || sitzung.verworfen || sitzung.beendet) { return; }
    if (sitzung.mikroUnterwegs) {
      sitzung.pausiert = true;
      zeigeDiskussionModus();
      return;
    }
    sitzung.erfassteMs += Date.now() - sitzung.legStart;
    sitzung.legStart = null;
    sitzung.pausiert = true;
    if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); sitzung.segmentTakt = null; }
    var alt = sitzung.recorder;
    sitzung.recorder = null;
    if (alt && sitzung.vadAktiv) { alt._grund = 'ende'; alt._redeMs = sitzung.vadSpeechMs; }
    if (alt && alt.state !== 'inactive') { alt.stop(); }
    gibFrei(sitzung);
    if (zustand.uhrTakt) { clearInterval(zustand.uhrTakt); zustand.uhrTakt = null; }
    if (uhrFeld) { uhrFeld.textContent = TEXT.uhr.replace('{zeit}', formatiereUhr(sitzung)); }
    zeigeDiskussionModus();
  }

  function fortsetzeDiskussion() {
    var sitzung = zustand.diskussion;
    // Dieselben Waechter wie fortsetzeBrainstorm(): "pausiert" nur einmal
    // zuruecknehmen, und eine Sperrklinke (fortsetzend) gegen einen
    // hastigen Doppeldruck, der sonst zwei Recorder auf demselben Mikrofon
    // startete.
    if (!sitzung || !sitzung.pausiert || sitzung.verworfen || sitzung.beendet ||
        sitzung.fortsetzend) { return; }
    if (sitzung.mikroUnterwegs) { sitzung.pausiert = false; return; }
    sitzung.pausiert = false;
    sitzung.fortsetzend = true;
    sitzung.mikroUnterwegs = true;
    holeStrom().then(function (strom) {
      sitzung.mikroUnterwegs = false;
      sitzung.fortsetzend = false;
      if (!zustand.diskussion || zustand.diskussion !== sitzung || sitzung.beendet) {
        strom.getTracks().forEach(function (t) { t.stop(); });
        return;
      }
      sitzung.strom = strom;
      beginneAufnahme(sitzung);
      zeigeDiskussionModus();
    }).catch(function () {
      sitzung.mikroUnterwegs = false;
      sitzung.fortsetzend = false;
      sitzung.pausiert = true;
      zeigeDiskussionModus();
      meldeFehler(TEXT.fehler_mikro);
    });
    zeigeDiskussionModus();
  }

  function beendeDiskussion() {
    var sitzung = zustand.diskussion;
    if (!sitzung) { return; }
    zustand.diskussion = null;
    anzeigeAus();
    if (!sitzung.gestartet) {
      sitzung.beendet = true;
      zeigeDiskussionModus();
      return;
    }
    sitzung.beendet = true;
    if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); sitzung.segmentTakt = null; }
    var letzter = sitzung.recorder;
    sitzung.recorder = null;
    if (letzter && sitzung.vadAktiv) { letzter._grund = 'ende'; letzter._redeMs = sitzung.vadSpeechMs; }
    if (letzter && letzter.state !== 'inactive') { letzter.stop(); }
    // Anders als beendeInterview(): pruefeEnde() tut bei Diskussion NIE
    // etwas (fertigEingereiht bleibt immer true), also wird das Mikrofon
    // HIER sofort freigegeben -- wie bei beendeBrainstorm(), nicht erst im
    // onstop.
    gibFrei(sitzung);
    zeigeDiskussionModus();
  }

  function starteInterview() {
    // Review-Befund 4: nie zwei Recorder, nie ein Start mitten im Wechsel.
    if (zustand.aufnahme || zustand.wechsel || zustand.brainstorm) { return; }
    // Re-Review F: ein gehaltener PTT-Druck (zweiter Finger) wird verworfen,
    // sonst liefen zwei Recorder.
    if (zustand.ptt) { verwirfPtt(); }
    var sitzung = {
      strom: null, recorder: null, kontext: null, pegelTakt: null,
      segmentTakt: null, offen: 0, gestartet: false, beendet: false,
      angemeldet: false, bestaetigt: false, verworfen: false,
      angehalten: false, geparkt: [],
      fertigEingereiht: false, naechsteNr: 0, einzureihen: 0, fertige: {},
      wechselAus: null,
      // Drei-Zustands-Regler (Pause/Weiter): erfassteMs ist die Dauer vor
      // der letzten Pause, legStart der Beginn der laufenden Spanne,
      // fortsetzend die Sperrklinke waehrend "Weiter" auf das Mikrofon
      // wartet (verhindert einen zweiten Recorder bei einem hastigen
      // Doppeldruck, siehe fortsetzeInterview).
      // mikroUnterwegs: zwischen dem Aufruf von holeStrom() und seinem
      // Ausgang (Erfolg oder Fehler) -- der Signal, an dem
      // pausiereInterview()/fortsetzeInterview() ein noch unterwegs
      // befindliches Mikrofon dieser Sitzung erkennen (Re-Review,
      // Befund 1), statt gegen das lange-schon-falsche "gestartet".
      pausiert: false, erfassteMs: 0, legStart: null, fortsetzend: false,
      mikroUnterwegs: false, hinweisGezeigt: false
    };
    var wechsel = { ziel: true, gesendet: false };
    zustand.aufnahme = sitzung;
    zustand.wechsel = wechsel;
    zeigeModus();
    sitzung.mikroUnterwegs = true;
    holeStrom().then(function (strom) {
      sitzung.mikroUnterwegs = false;
      sitzung.strom = strom;
      if (sitzung.beendet) { gibFrei(sitzung); return; }   // vorher gestoppt
      // Das Mikrofon ist da, also weiss der Bot jetzt, dass der Modus an
      // ist -- unabhaengig davon, ob gleich aufgenommen wird: /interview
      // wird genau einmal und immer hier angemeldet.
      sitzung.gestartet = true;
      reiheEin({ art: 'befehl', an: true, sitzung: sitzung, wechsel: wechsel });
      // Die Aufnahme laeuft SOFORT -- sonst verliert man die ersten Worte.
      // Die Segmente warten in der Schlange hinter /interview (bereit()).
      // Kam waehrend des Wartens eine Pause dazwischen (Re-Review, Befund 1;
      // zweites Re-Review, Befund: der Schutz dafuer lebt zentral in
      // beginneAufnahme(), nicht hier dupliziert), faengt sie gar nicht erst
      // an und gibt das Mikrofon selbst wieder frei.
      beginneAufnahme(sitzung);
      zeigeModus();
    }).catch(function () {
      // Review-Befund 8: ein halb gestarteter Recorder wird gestoppt und das
      // Mikrofon freigegeben.
      sitzung.mikroUnterwegs = false;
      sitzung.verworfen = true;
      sitzung.beendet = true;
      if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); }
      if (sitzung.recorder && sitzung.recorder.state !== 'inactive') {
        try { sitzung.recorder.stop(); } catch (e) { /* schon aus */ }
      }
      sitzung.recorder = null;
      gibFrei(sitzung);
      entferneAuftraege(sitzung);
      if (zustand.aufnahme === sitzung) { zustand.aufnahme = null; }
      if (zustand.wechsel === wechsel) { zustand.wechsel = null; }
      anzeigeAus();
      zeigeModus();
      meldeFehler(TEXT.fehler_mikro);
    });
  }

  // Der Bot hat /interview endgueltig abgelehnt: die Aufnahme haette keinen
  // Ort. Aufhoeren, Mikrofon frei, nichts davon hochladen.
  function brichAb(sitzung) {
    sitzung.verworfen = true;
    sitzung.beendet = true;
    if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); }
    if (sitzung.recorder && sitzung.recorder.state !== 'inactive') {
      try { sitzung.recorder.stop(); } catch (e) { /* schon aus */ }
    }
    sitzung.recorder = null;
    gibFrei(sitzung);
    entferneAuftraege(sitzung);
    if (zustand.aufnahme === sitzung) { zustand.aufnahme = null; anzeigeAus(); }
    // Ein Stopp dieser Aufnahme, der jetzt nie mehr gesendet wird, darf den
    // Knopf nicht dauerhaft ausgrauen.
    if (sitzung.wechselAus && zustand.wechsel === sitzung.wechselAus) {
      zustand.wechsel = null;
    }
  }

  function beendeInterview() {
    if (zustand.wechsel && !zustand.wechsel.ziel) { return; }   // schon unterwegs
    var sitzung = zustand.aufnahme;
    zustand.aufnahme = null;
    anzeigeAus();
    if (sitzung && !sitzung.gestartet) {
      // Das Mikrofon war noch nicht da: nichts aufgenommen, nichts angemeldet.
      sitzung.beendet = true;
      zustand.wechsel = null;
      zeigeModus();
      return;
    }
    var wechsel = { ziel: false, gesendet: false };
    zustand.wechsel = wechsel;
    if (!sitzung) {
      // Der Modus ist an, aber dieses Telefon nimmt nicht auf (neu geladen):
      // nur den Modus schliessen.
      reiheEin({ art: 'befehl', an: false, wechsel: wechsel });
      zeigeModus();
      return;
    }
    sitzung.beendet = true;
    sitzung.wechselAus = wechsel;
    if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); sitzung.segmentTakt = null; }
    var letzter = sitzung.recorder;
    sitzung.recorder = null;
    if (letzter && sitzung.vadAktiv) { letzter._grund = 'ende'; letzter._redeMs = sitzung.vadSpeechMs; }
    if (letzter && letzter.state !== 'inactive') {
      letzter.stop();          // sein onstop reiht das letzte Segment ein
    } else {
      pruefeEnde(sitzung);
    }
    zeigeModus();
  }

  // -- Pause / Weiter (Drei-Zustands-Regler, 02.10.2026, Padua) ------------
  //
  // "Pause" schickt NIE ein /fertig -- der Interviewmodus bleibt
  // serverseitig an, nur der Recorder dieses Telefons stoppt. Das letzte
  // Stueck geht trotzdem den normalen Weg (onstop -> fertige{}/einzureihen
  // -> reiheEin), unveraendert. "Weiter" haengt an GENAU dieselbe Sitzung
  // an (dieselbe naechsteNr-Folge) -- es gibt deshalb nie ein zweites
  // /interview fuer dasselbe Interview. zustand.aufnahme bleibt dabei die
  // ganze Zeit nicht-null; pausiert ist eine Eigenschaft der Sitzung
  // (sitzung.pausiert), keine zweite, parallele Merkvariable.

  function pausiereInterview(sitzungArg) {
    var sitzung = sitzungArg || zustand.aufnahme;
    if (!sitzung || sitzung.pausiert || sitzung.verworfen || sitzung.beendet) { return; }
    // Nur ein echt UNTERWEGS befindlicher Stopp blockiert -- die lingernde
    // Bestaetigung des eigenen Starts (wechsel.ziel === true, noch nicht
    // vom Poll bestaetigt) darf eine Pause nicht verhindern: der Recorder
    // laeuft schon, dieselbe Regel wie in beendeInterview().
    if (zustand.wechsel && !zustand.wechsel.ziel) { return; }
    if (sitzung.mikroUnterwegs) {
      // Re-Review, Befund 1: das Mikrofon dieser Sitzung ist noch unterwegs
      // (starteInterview() wartet auf holeStrom(), eine vom Menschen
      // beantwortete Berechtigungsfrage -- das Fenster kann Sekunden
      // dauern) -- sitzung.legStart ist noch null, das Falten gegen
      // Date.now() wuerde eine Muellzahl in die Uhr schreiben. Nur merken,
      // dass Pause gewuenscht ist: starteInterview() sieht das
      // Flag, sobald das Mikrofon kommt, und faengt dann gar nicht erst an
      // aufzunehmen (statt den Tipp stillschweigend zu verschlucken).
      sitzung.pausiert = true;
      zeigeModus();
      return;
    }
    sitzung.erfassteMs += Date.now() - sitzung.legStart;
    sitzung.legStart = null;
    sitzung.pausiert = true;
    if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); sitzung.segmentTakt = null; }
    var alt = sitzung.recorder;
    sitzung.recorder = null;
    // Wie starteInterview()/brichAb() bei einem Fehler: stop(), dann sofort
    // das Mikrofon los -- sein onstop hat die Daten bis hierhin schon im
    // ondataavailable gesammelt und reiht das Stueck ganz normal ein.
    // grund 'ende': ein manueller Flush haelt sich NICHT an MIN_SPEECH_MS --
    // "bei Pause/Beenden gesendet, wenn ueberhaupt Rede drin ist".
    if (alt && sitzung.vadAktiv) { alt._grund = 'ende'; alt._redeMs = sitzung.vadSpeechMs; }
    if (alt && alt.state !== 'inactive') { alt.stop(); }
    gibFrei(sitzung);
    if (zustand.uhrTakt) { clearInterval(zustand.uhrTakt); zustand.uhrTakt = null; }
    if (uhrFeld) { uhrFeld.textContent = TEXT.uhr.replace('{zeit}', formatiereUhr(sitzung)); }
    zeigeModus();
  }

  function fortsetzeInterview(sitzungArg) {
    var sitzung = sitzungArg;
    if (sitzung) {
      // Dieselbe grosszuegigere Regel wie in pausiereInterview(): nur ein
      // unterwegs befindlicher Stopp blockiert, nicht die lingernde
      // Start-Bestaetigung.
      if ((zustand.wechsel && !zustand.wechsel.ziel) || !sitzung.pausiert ||
          sitzung.verworfen || sitzung.beendet || sitzung.fortsetzend) { return; }
      if (sitzung.mikroUnterwegs) {
        // Re-Review, Befund 1 (Kehrseite): starteInterview() wartet selbst
        // noch auf sein eigenes Mikrofon -- einfach die Pause zuruecknehmen.
        // Dessen .then() sieht sitzung.pausiert === false und faengt von
        // sich aus an aufzunehmen; kein zweiter holeStrom()-Aufruf, also
        // nie zwei Recorder auf derselben Sitzung.
        sitzung.pausiert = false;
        zeigeModus();
        return;
      }
    } else {
      // Neu geladen, waehrend der Server den Modus schon meldet (Punkt 5):
      // keine lokale Sitzung, also auch kein zweites /interview -- der Bot
      // weiss es schon. naechsteNr startet bei 0, haengt aber an DASSELBE
      // serverseitige Interview an.
      if (zustand.aufnahme || zustand.wechsel || !zustand.servermodus) { return; }
      sitzung = {
        strom: null, recorder: null, kontext: null, pegelTakt: null,
        segmentTakt: null, offen: 0, gestartet: false, beendet: false,
        angemeldet: true, bestaetigt: true, verworfen: false,
        angehalten: false, geparkt: [],
        fertigEingereiht: false, naechsteNr: 0, einzureihen: 0, fertige: {},
        wechselAus: null, pausiert: true, erfassteMs: 0, legStart: null,
        fortsetzend: false, mikroUnterwegs: false, hinweisGezeigt: false
      };
      zustand.aufnahme = sitzung;   // synchron, wie starteInterview()
    }
    // Re-Review F, auch beim Wiederaufnehmen: ein gehaltener PTT-Druck wird
    // verworfen, sonst liefen zwei Recorder.
    if (zustand.ptt) { verwirfPtt(); }
    // Ab hier laeuft das EIGENE holeStrom() dieser Funktion (nicht mehr das
    // von starteInterview(), das ist der Zweig oben): sitzung.pausiert wird
    // deshalb schon JETZT auf false gesetzt, nicht erst in beginneAufnahme()
    // -- spiegelbildlich zu starteInterview(), dessen frisches Sitzungs-
    // Objekt ebenfalls mit pausiert: false in sein eigenes holeStrom() geht.
    // Kommt waehrend dieses Wartens eine Pause (pausiereInterview() sieht
    // dann !sitzung.pausiert, erkennt mikroUnterwegs und merkt sie erneut,
    // statt no-op zu sein), sieht beginneAufnahme() unten sitzung.pausiert
    // wieder true und faengt gar nicht erst an -- derselbe Schutz wie bei
    // starteInterview(), zentral an einer Stelle statt dupliziert.
    sitzung.pausiert = false;
    sitzung.fortsetzend = true;   // Sperrklinke: kein zweiter Recorder bei Doppeldruck
    zeigeModus();
    sitzung.mikroUnterwegs = true;
    holeStrom().then(function (strom) {
      sitzung.mikroUnterwegs = false;
      sitzung.fortsetzend = false;
      if (sitzung.beendet || sitzung.verworfen) {
        strom.getTracks().forEach(function (t) { t.stop(); });
        return;
      }
      sitzung.strom = strom;
      // Zentrale Stelle: beginneAufnahme() prueft selbst, ob inzwischen
      // pausiert wurde.
      beginneAufnahme(sitzung);
      zeigeModus();
    }).catch(function () {
      sitzung.mikroUnterwegs = false;
      sitzung.fortsetzend = false;
      zeigeModus();
      meldeFehler(TEXT.fehler_mikro);
    });
  }

  if (nachreichenKnopf) { nachreichenKnopf.addEventListener('click', reicheNach); }
  if (verwerfenKnopf) { verwerfenKnopf.addEventListener('click', verwirfRest); }

  if (interviewPauseKnopf) {
    interviewPauseKnopf.addEventListener('click', function () {
      var sitzung = zustand.aufnahme;
      if (sitzung) {
        if (sitzung.pausiert) { fortsetzeInterview(sitzung); } else { pausiereInterview(sitzung); }
      } else if (zustand.servermodus) {
        fortsetzeInterview(null);
      }
    });
  }
  if (interviewBeendenKnopf) {
    interviewBeendenKnopf.addEventListener('click', beendeInterview);
  }

  // Der grosse Knopf ist nur noch im Leerlauf ein Schalter -- waehrend
  // Laeuft/Pause ist er eine Anzeige, Beenden passiert ausschliesslich ueber
  // #interview-beenden.
  interviewKnopf.addEventListener('click', function () {
    if (interviewKnopf.disabled || modusAn()) { return; }
    starteInterview();
  });

  if (brainstormPauseKnopf) {
    brainstormPauseKnopf.addEventListener('click', function () {
      var sitzung = zustand.brainstorm;
      if (!sitzung) { return; }
      if (sitzung.pausiert) { fortsetzeBrainstorm(); } else { pausiereBrainstorm(); }
    });
  }
  if (brainstormBeendenKnopf) {
    brainstormBeendenKnopf.addEventListener('click', beendeBrainstorm);
  }
  if (brainstormKnopf) {
    brainstormKnopf.addEventListener('click', function () {
      if (brainstormKnopf.disabled || zustand.brainstorm) { return; }
      starteBrainstorm();
    });
  }

  if (diskussionPauseKnopf) {
    diskussionPauseKnopf.addEventListener('click', function () {
      var sitzung = zustand.diskussion;
      if (!sitzung) { return; }
      if (sitzung.pausiert) { fortsetzeDiskussion(); } else { pausiereDiskussion(); }
    });
  }
  if (diskussionBeendenKnopf) {
    diskussionBeendenKnopf.addEventListener('click', beendeDiskussion);
  }
  if (diskussionKnopf) {
    diskussionKnopf.addEventListener('click', function () {
      if (diskussionKnopf.disabled || zustand.diskussion) { return; }
      starteDiskussion();
    });
  }

  // -- Push-to-Talk --------------------------------------------------------
  //
  // Halten = aufnehmen, Loslassen = senden (Kanban-Karte Buehne/PTT,
  // 04.10.2026 -- Telegram-Vorbild, loest den Klick-Umschalter vom
  // 03.10.2026 wieder ab): Finger auf den Knopf und halten startet, Finger
  // weg beendet und sendet. Nach oben schieben (>= PTT_LOCK_PX) sperrt die
  // Aufnahme -- sie laeuft dann OHNE gehaltenen Finger weiter, bis "Senden"
  // oder "Verwerfen" gedrueckt wird oder PTT_MAX_MS erreicht ist (dann wie
  // ein normales Senden). Nach links wischen (>= PTT_CANCEL_PX) bricht
  // sofort ab, 0 POST. Ein Druck unter PTT_MIN_MS sendet NICHTS, zeigt aber
  // kurz einen Hinweis statt einfach nichts zu tun.

  // Ein eigener, kleiner AnalyserNode fuer den PTT-Pegelbalken -- bewusst
  // NICHT ``pegelAn()``/``#pegel``: die ist an die VAD-Kalibrierung und an
  // ``sitzung.pausiert``/``legStart``/``erfassteMs`` gekoppelt, die PTT
  // nicht hat. Nach dem Vorbild von ``kalBaueMesser()``, aber unabhaengig
  // davon (eigener Kontext auf demselben Strom ist erlaubt).
  function pttBaueMesser(strom) {
    var Kontext = window.AudioContext || window.webkitAudioContext;
    if (!Kontext || !strom) { return null; }
    try {
      var kontext = new Kontext();
      if (kontext.state === 'suspended' && kontext.resume) { kontext.resume(); }
      var knoten = kontext.createAnalyser();
      knoten.fftSize = 256;
      kontext.createMediaStreamSource(strom).connect(knoten);
      var zeitWerte = new Float32Array(knoten.fftSize);
      return {
        kontext: kontext,   // gibFrei(druck) schliesst ueber druck.kontext
        rms: function () {
          knoten.getFloatTimeDomainData(zeitWerte);
          var summe = 0;
          for (var i = 0; i < zeitWerte.length; i++) { summe += zeitWerte[i] * zeitWerte[i]; }
          return Math.sqrt(summe / zeitWerte.length);
        }
      };
    } catch (e) { return null; }
  }

  // Rueckstellung: Anzeige-Box ganz weg, #ptt wieder da -- derselbe Stand
  // wie vor dem allerersten Druck. ANNAHME: Opacity/Farben der Box sind
  // freie Gestaltung (siehe CSS), nur die IDs/Zustaende sind Vorgabe.
  function pttVerstecke() {
    if (pttAnzeige) {
      pttAnzeige.hidden = true;
      pttAnzeige.dataset.gesperrt = '0';
      pttAnzeige.dataset.wirdVerworfen = '0';
    }
    if (pttSchloss) { pttSchloss.hidden = false; }
    if (pttWischHinweis) { pttWischHinweis.hidden = false; }
    if (pttZeit) { pttZeit.hidden = false; pttZeit.textContent = ''; }
    if (pttPegelFeld) {
      pttPegelFeld.hidden = false;
      if (pttPegelBalken) { pttPegelBalken.style.width = '0%'; }
    }
    if (pttHinweistext) { pttHinweistext.hidden = true; }
    if (pttSendeKnopf) { pttSendeKnopf.hidden = true; }
    if (pttVerwerfenKnopf) { pttVerwerfenKnopf.hidden = true; }
    if (pttKnopf) { pttKnopf.hidden = false; pttKnopf.dataset.haelt = '0'; }
  }

  function pttZeigeAnzeige() {
    if (pttAnzeige) {
      pttAnzeige.hidden = false;
      pttAnzeige.dataset.gesperrt = '0';
      pttAnzeige.dataset.wirdVerworfen = '0';
    }
    if (pttSchloss) { pttSchloss.hidden = false; }
    if (pttWischHinweis) { pttWischHinweis.hidden = false; }
    if (pttZeit) { pttZeit.hidden = false; pttZeit.textContent = '0:00'; }
    if (pttPegelFeld) {
      pttPegelFeld.hidden = false;
      if (pttPegelBalken) { pttPegelBalken.style.width = '0%'; }
    }
    if (pttHinweistext) { pttHinweistext.hidden = true; }
    if (pttSendeKnopf) { pttSendeKnopf.hidden = true; }
    if (pttVerwerfenKnopf) { pttVerwerfenKnopf.hidden = true; }
  }

  // Kurzer Tipp (< PTT_MIN_MS, Kartenkriterium 4): statt die Box sofort
  // wegzunehmen, zeigt sie fuer PTT_HINWEIS_MS NUR den Halten-Hinweis.
  var PTT_HINWEIS_MS = 1400;   // innerhalb der von der Karte genannten 1200-1500 ms
  function pttZeigeKurztippHinweis() {
    if (pttSchloss) { pttSchloss.hidden = true; }
    if (pttWischHinweis) { pttWischHinweis.hidden = true; }
    if (pttZeit) { pttZeit.hidden = true; }
    if (pttPegelFeld) { pttPegelFeld.hidden = true; }
    if (pttHinweistext) { pttHinweistext.hidden = false; pttHinweistext.textContent = TEXT.ptt_hinweis; }
  }

  function pttSperren(druck) {
    druck.gesperrt = true;
    if (pttSchloss) { pttSchloss.hidden = true; }
    if (pttWischHinweis) { pttWischHinweis.hidden = true; }
    if (pttAnzeige) { pttAnzeige.dataset.gesperrt = '1'; pttAnzeige.dataset.wirdVerworfen = '0'; }
    if (pttKnopf) { pttKnopf.hidden = true; }
    if (pttSendeKnopf) { pttSendeKnopf.hidden = false; }
    if (pttVerwerfenKnopf) { pttVerwerfenKnopf.hidden = false; }
    if (navigator.vibrate) { try { navigator.vibrate(10); } catch (e) { /* egal */ } }
  }

  // Gemeinsamer Senden-Weg: normales Loslassen (>= PTT_MIN_MS), Klick auf
  // #ptt-senden im gesperrten Zustand, UND der PTT_MAX_MS-Timeout, egal ob
  // gesperrt. Der Recorder stoppt, sein onstop (siehe pttPointerDown) sendet.
  // druck.dauerMs wird HIER berechnet (nicht nur beim normalen Loslassen) --
  // sonst liefe der bestehende onstop-Waechter ``druck.dauerMs < PTT_MIN_MS``
  // beim gesperrten Senden-Knopf gegen den Anfangswert 0 und verwuerfe jede
  // gesperrte Aufnahme als "zu kurz", egal wie lange sie wirklich lief.
  function pttSende(druck) {
    if (zustand.ptt === druck) { zustand.ptt = null; }
    if (druck.timeout) { clearTimeout(druck.timeout); druck.timeout = null; }
    if (druck.takt) { clearInterval(druck.takt); druck.takt = null; }
    if (druck.hinweisTimeout) { clearTimeout(druck.hinweisTimeout); druck.hinweisTimeout = null; }
    druck.dauerMs = Date.now() - druck.von;
    pttVerstecke();
    if (druck.recorder && druck.recorder.state !== 'inactive') {
      druck.recorder.stop();
      return;
    }
    // Das Mikrofon ist noch nicht da (holeStrom() laeuft noch). Beim
    // normalen Loslassen (nicht gesperrt) hat der Aufrufer druck.gehalten
    // schon auf false gesetzt -- dann gibt die then()-Fortsetzung in
    // pttPointerDown auf, wie bisher (Regressionstest: Mikro kommt erst
    // nach dem Loslassen). Im gesperrten Zustand bleibt druck.gehalten
    // dagegen wahr: die Gruppe hat schon "Senden" gedrueckt, eine deshalb
    // verlorene Aufnahme waere falsch -- also sofort stoppen, SOBALD der
    // Recorder entsteht (siehe pttPointerDown, direkt nach r.start()).
    if (druck.gehalten) { druck.ausstehend = true; }
  }

  // Gemeinsamer Verwerfen-Weg: Wegwisch-Abbruch, Klick auf #ptt-verwerfen,
  // pointercancel/lostpointercapture (wenn nicht gesperrt), UND die vier
  // externen verwirfPtt()-Aufrufstellen (Interview/Brainstorm/Diskussion/
  // Wechsel-Start). druck.abgebrochen = true VOR recorder.stop(): der
  // bestehende onstop-Waechter verhindert damit das Senden.
  function pttVerwirf(druck) {
    if (zustand.ptt === druck) { zustand.ptt = null; }
    druck.gehalten = false;
    druck.abgebrochen = true;
    if (druck.timeout) { clearTimeout(druck.timeout); druck.timeout = null; }
    if (druck.takt) { clearInterval(druck.takt); druck.takt = null; }
    if (druck.hinweisTimeout) { clearTimeout(druck.hinweisTimeout); druck.hinweisTimeout = null; }
    pttVerstecke();
    if (druck.recorder && druck.recorder.state !== 'inactive') {
      druck.recorder.stop();   // sein onstop gibt das Mikrofon frei
    }
    // Kein Recorder (Mikrofon noch nicht da): die then()-Fortsetzung in
    // pttPointerDown prueft druck.gehalten und gibt dann selbst frei.
  }

  function pttPointerDown(ev) {
    if (!pttKnopf) { return; }
    // Abschluss-Review (Finding 2): auch gegen zustand.diskussion gesperrt --
    // dieselbe Regel wie gegen zustand.brainstorm, PTT ist ein drittes
    // Mikrofon auf demselben Geraet.
    if (modusAn() || zustand.wechsel || zustand.brainstorm || zustand.diskussion ||
        zustand.ptt) { return; }
    ev.preventDefault();
    try { pttKnopf.setPointerCapture(ev.pointerId); } catch (e) { /* ohne Capture geht es auch */ }
    // Review-Befund 6 (galt schon vorher): jeder Druck traegt seinen eigenen
    // Zustand -- ein spaeterer Druck ueberschreibt nichts, was ein
    // frueherer noch liest.
    var druck = {
      von: Date.now(), dauerMs: 0, gehalten: true, abgebrochen: false,
      recorder: null, strom: null, teile: [], timeout: null, takt: null,
      gesperrt: false, startX: ev.clientX, startY: ev.clientY,
      pointerId: ev.pointerId, pegelTakt: null, kontext: null,
      hinweisTimeout: null, ausstehend: false
    };
    zustand.ptt = druck;
    pttKnopf.dataset.haelt = '1';
    pttZeigeAnzeige();
    // Laufende Zeit sichtbar machen, solange der Druck laeuft.
    druck.takt = setInterval(function () {
      if (pttZeit) {
        pttZeit.textContent = '🔴 ' + minuten(Math.floor((Date.now() - druck.von) / 1000));
      }
    }, 500);
    if (navigator.vibrate) { try { navigator.vibrate(10); } catch (e) { /* egal */ } }
    holeStrom().then(function (strom) {
      druck.strom = strom;
      // Review-Befund 5: beendet, bevor das Mikrofon da war -- dann gar
      // nicht erst aufnehmen, und das Mikrofon sofort wieder zu.
      if (!druck.gehalten) { gibFrei(druck); return; }
      var messer = pttBaueMesser(strom);
      if (messer) {
        druck.kontext = messer.kontext;
        druck.pegelTakt = setInterval(function () {
          if (pttPegelBalken) {
            pttPegelBalken.style.width = Math.min(100, (messer.rms() / 0.3) * 100) + '%';
          }
        }, 120);
      }
      var r = new MediaRecorder(strom);
      druck.recorder = r;
      r.ondataavailable = function (e) {
        if (e.data && e.data.size) { druck.teile.push(e.data); }
      };
      r.onstop = function () {
        gibFrei(druck);   // schliesst druck.kontext, stoppt druck.pegelTakt/strom
        if (druck.abgebrochen || druck.dauerMs < PTT_MIN_MS ||
            !druck.teile.length) { return; }
        veralteLetzteLeiste();
        reiheEin({
          art: 'audio', sitzung: null,
          blob: new Blob(druck.teile,
                         { type: druck.teile[0].type || r.mimeType || 'audio/webm' }),
          dauer: Math.max(1, Math.round(druck.dauerMs / 1000))
        });
      };
      r.start();
      // "Senden" kam schon, bevor das Mikrofon da war (nur im gesperrten
      // Zustand moeglich, siehe pttSende): sofort stoppen, statt eine
      // Aufnahme zu verlieren, die die Gruppe schon freigegeben hat.
      if (druck.ausstehend) { r.stop(); }
    }).catch(function () {
      druck.abgebrochen = true;
      gibFrei(druck);
      if (zustand.ptt === druck) {
        zustand.ptt = null;
        if (druck.timeout) { clearTimeout(druck.timeout); }
        if (druck.takt) { clearInterval(druck.takt); }
        pttVerstecke();
      }
      meldeFehler(TEXT.fehler_mikro);
    });
    druck.timeout = setTimeout(function () {
      // Automatik nach PTT_MAX_MS -- derselbe Senden-Weg, EGAL ob gesperrt.
      if (zustand.ptt === druck) { pttSende(druck); }
    }, PTT_MAX_MS);
  }

  function pttPointerMove(ev) {
    var druck = zustand.ptt;
    if (!druck || ev.pointerId !== druck.pointerId || druck.gesperrt) { return; }
    var dx = ev.clientX - druck.startX;
    var dy = ev.clientY - druck.startY;
    if (dy <= -PTT_LOCK_PX) {
      pttSperren(druck);
      return;
    }
    if (dx <= -PTT_CANCEL_PX) {
      pttVerwirf(druck);
      return;
    }
    // Rueckmeldung "wird gleich abgebrochen" (ANNAHME, freie Gestaltung):
    // ab der Haelfte der Wegwischstrecke dimmt die Box per CSS-Attribut.
    if (pttAnzeige) {
      pttAnzeige.dataset.wirdVerworfen = (-dx >= PTT_CANCEL_PX * 0.5) ? '1' : '0';
    }
  }

  // Pointerup auf #ptt: gesperrt -> NICHTS tun (die Aufnahme laeuft ohne
  // gehaltenen Finger weiter, das ist der ganze Witz der Sperre), nur die
  // Pointer-Capture freigeben. Sonst normales Loslassen: unter PTT_MIN_MS
  // der Kurztipp-Hinweis (0 POST), sonst der Senden-Weg.
  function pttPointerUp(ev) {
    var druck = zustand.ptt;
    if (!druck || ev.pointerId !== druck.pointerId) { return; }
    try { pttKnopf.releasePointerCapture(ev.pointerId); } catch (e) { /* egal */ }
    if (druck.gesperrt) { return; }
    // Die Laufzeit, nicht die Zeit bis das Mikrofon da war.
    var dauerMs = Date.now() - druck.von;
    if (dauerMs < PTT_MIN_MS) {
      // Kurzer Tipp: der bestehende onstop-Waechter (druck.dauerMs <
      // PTT_MIN_MS) verhindert das Senden schon -- hier NICHT zusaetzlich
      // abgebrochen setzen, nur Timer abraeumen und kurz den Halten-Hinweis
      // zeigen, statt die Box sofort wegzunehmen. Das ist NICHT der
      // gemeinsame Senden-Weg (pttSende): der Kurztipp-Hinweis gehoert zu
      // keinem der drei Faelle, die pttSende abdeckt.
      if (druck.timeout) { clearTimeout(druck.timeout); druck.timeout = null; }
      if (druck.takt) { clearInterval(druck.takt); druck.takt = null; }
      druck.gehalten = false;
      druck.dauerMs = dauerMs;
      zustand.ptt = null;
      pttZeigeKurztippHinweis();
      druck.hinweisTimeout = setTimeout(function () { pttVerstecke(); }, PTT_HINWEIS_MS);
      if (druck.recorder && druck.recorder.state !== 'inactive') {
        druck.recorder.stop();
      }
      return;
    }
    // Normales Loslassen (>= PTT_MIN_MS): derselbe Senden-Weg wie der Klick
    // auf #ptt-senden und der PTT_MAX_MS-Timeout. gehalten=false ZUERST,
    // nicht in pttSende selbst -- kommt das Mikrofon hier erst NACH dem
    // Loslassen, wird aufgegeben statt gewartet (anders als im gesperrten
    // Zustand, wo die Gruppe den Finger laengst gehoben hat UND trotzdem
    // weiter aufgenommen wird).
    druck.gehalten = false;
    pttSende(druck);
  }

  // pointercancel/lostpointercapture: wie Verwerfen behandeln -- das
  // "Fundstueck" aus einer frueheren Fassung (vor dem Klick-Umschalter),
  // aufs neue Zustandsmodell uebertragen. NICHT, wenn schon gesperrt: sonst
  // wuerde das eigene releasePointerCapture() aus dem gesperrten Zweig von
  // pttPointerUp die gerade erst gesperrte, freilaufende Aufnahme sofort
  // wieder abbrechen -- exakt der Fehler, den die Sperre verhindern soll.
  function pttAbgebrochenesPointerEreignis(ev) {
    var druck = zustand.ptt;
    if (!druck || ev.pointerId !== druck.pointerId || druck.gesperrt) { return; }
    pttVerwirf(druck);
  }

  if (pttKnopf) {
    pttKnopf.addEventListener('pointerdown', pttPointerDown);
    pttKnopf.addEventListener('pointermove', pttPointerMove);
    pttKnopf.addEventListener('pointerup', pttPointerUp);
    pttKnopf.addEventListener('pointercancel', pttAbgebrochenesPointerEreignis);
    pttKnopf.addEventListener('lostpointercapture', pttAbgebrochenesPointerEreignis);
    pttKnopf.addEventListener('contextmenu', function (ev) { ev.preventDefault(); });
  }
  if (pttSendeKnopf) {
    pttSendeKnopf.addEventListener('click', function () {
      // #ptt-senden ist nur sichtbar, solange ein Druck gesperrt ist --
      // zustand.ptt ist in dem Fall genau dieser Druck.
      if (zustand.ptt) { pttSende(zustand.ptt); }
    });
  }
  if (pttVerwerfenKnopf) {
    pttVerwerfenKnopf.addEventListener('click', function () {
      if (zustand.ptt) { pttVerwirf(zustand.ptt); }
    });
  }

  // Nicht weg, solange etwas aufgenommen wird oder die Schlange nicht leer
  // ist: ein geschlossener Tab verliert, was noch nicht angekommen ist.
  window.addEventListener('beforeunload', function (ev) {
    if (!zustand.aufnahme && !zustand.ptt && !zustand.laeuft &&
        !zustand.warteschlange.length && !geparkteZahl()) { return; }
    ev.preventDefault();
    ev.returnValue = TEXT.verlassen;
    return TEXT.verlassen;
  });

  zeigeModus();   // den Zustand der Seite sofort anwenden, nicht erst nach dem Poll
  scrolleZuPhasenanfang();   // Phasenscroll-Karte: der Anfang der aktuellen Phase, sonst der Rueckfall ans Ende
  hole();
})();
"""


def _js() -> str:
    """``_CHAT_JS`` mit den Zahlen und Texten aus den Modulkonstanten.

    Platzhalter und keine f-String-Interpolation: das Skript ist voll mit
    geschweiften Klammern. Die Texte gehen als JSON hinein; ``</`` wird
    maskiert, damit kein Text das ``<script>`` beenden kann."""
    # Padua Hotfix B6/B7, erweitert Task 4 (Kanban-Karte Buehne/PTT): die
    # uebersetzten Texte zur Aufrufzeit (``T``).
    texte = dict(
        _JS_TEXTE,
        interview_an=T._TEXT_INTERVIEW_AN, interview_aus=T._TEXT_INTERVIEW_AUS,
        sprache=T._TEXT_SPRACHE, sprache_laeuft=T._TEXT_SPRACHE_LAEUFT,
        interview_pause=T._TEXT_INTERVIEW_PAUSE,
        interview_weiter=T._TEXT_INTERVIEW_WEITER,
        interview_laeuft=T._TEXT_INTERVIEW_LAEUFT,
        interview_pausiert=T._TEXT_INTERVIEW_PAUSIERT,
        brainstorm_an=T._TEXT_BRAINSTORM_AN,
        brainstorm_laeuft=T._TEXT_BRAINSTORM_LAEUFT,
        diskussion_an=T._TEXT_DISKUSSION_AN,
        diskussion_laeuft=T._TEXT_DISKUSSION_LAEUFT,
        kal_ankuendigung=T._TEXT_KALIBRIERUNG_ANKUENDIGUNG,
        kal_start_knopf=T._TEXT_KALIBRIERUNG_START_KNOPF,
        kal_stille=T._TEXT_KALIBRIERUNG_STILLE,
        kal_sprechen_ankuendigung=T._TEXT_KALIBRIERUNG_SPRECHEN_ANKUENDIGUNG,
        kal_sprechen_knopf=T._TEXT_KALIBRIERUNG_SPRECHEN_KNOPF,
        kal_hoeren=T._TEXT_KALIBRIERUNG_HOEREN,
        kal_nichts_gehoert=T._TEXT_KALIBRIERUNG_NICHTS_GEHOERT,
        kal_messen_knopf=T._TEXT_KALIBRIERUNG_MESSEN_KNOPF,
        kal_zu_leise=T._TEXT_KALIBRIERUNG_ZU_LEISE,
        kal_zu_leise_1=T._TEXT_KALIBRIERUNG_ZU_LEISE_1,
        kal_zu_leise_2=T._TEXT_KALIBRIERUNG_ZU_LEISE_2,
        kal_nochmal_knopf=T._TEXT_KALIBRIERUNG_NOCHMAL_KNOPF,
        kal_weiter_trotzdem=T._TEXT_KALIBRIERUNG_WEITER_TROTZDEM,
        kal_transkribiert_warten=T._TEXT_KALIBRIERUNG_TRANSKRIBIERT_WARTEN,
        kal_bestaetigung=T._TEXT_KALIBRIERUNG_BESTAETIGUNG,
        kal_ja_knopf=T._TEXT_KALIBRIERUNG_JA_KNOPF,
        kal_nein_knopf=T._TEXT_KALIBRIERUNG_NEIN_KNOPF,
        kal_floor_hinweis=T._TEXT_KALIBRIERUNG_FLOOR_HINWEIS,
        kal_erfolg=T._TEXT_KALIBRIERUNG_ERFOLG,
        kal_skip_knopf=T._TEXT_KALIBRIERUNG_SKIP_KNOPF,
        kal_balken_label=T._TEXT_KALIBRIERUNG_BALKEN_LABEL,
        kal_herumreichen_erinnerung=T._TEXT_KALIBRIERUNG_HERUMREICHEN_ERINNERUNG,
        mitlauf_hinweis=T._TEXT_MITLAUF_HINWEIS,
        ptt_hinweis=T._TEXT_PTT_HINWEIS,
    )
    texte = json.dumps(texte, ensure_ascii=True).replace("</", "<\\/")
    return (
        _CHAT_JS
        .replace("__POLL_MS__", str(POLL_MS))
        .replace("__POLL_MS_HINTERGRUND__", str(POLL_MS_HINTERGRUND))
        .replace("__PTT_MIN_MS__", str(PTT_MIN_MS))
        .replace("__PTT_MAX_MS__", str(PTT_MAX_MS))
        .replace("__PTT_LOCK_PX__", str(PTT_LOCK_PX))
        .replace("__PTT_CANCEL_PX__", str(PTT_CANCEL_PX))
        .replace("__UPLOAD_WARTEN_MS__", json.dumps(list(UPLOAD_WARTEN_MS)))
        .replace("__TEXTE__", texte)
    )


def _bild_html(n: dict, basis: str) -> str:
    """Das ``<img>`` einer Telefon-Organisationskarte (UX-Knoepfe-Karte,
    Abschnitt 5) -- leerer String ohne ``bild``.

    Derselbe ``basis``-Weg wie beim Datei-Link (``static/handys/<name>``
    statt ``chat/datei/<id>``): auf der vereinten Seite ``"<token>/"``, auf
    der Chat-Einzelseite leer. ``alt`` ist der Satz der Karte (``n["text"]``)
    -- dieselbe Information als Bild und fuer Screenreader."""
    name = n.get("bild")
    if not name:
        return ""
    quelle = f"{basis}{STATIC_HANDYS_PFAD}/{html.escape(name, quote=True)}"
    alt = html.escape(n["text"] or "", quote=True)
    return f'<img src="{quelle}" alt="{alt}" loading="lazy" class="karte">'


def _blase_html(n: dict, basis: str = "") -> str:
    """Eine Nachricht als Blase, gegebenenfalls mit ihrer Leiste darunter.

    ``basis`` ist das Praefix vor ``chat/...`` auf der vereinten Seite
    (Karte W) -- auf der Chat-Einzelseite bleibt es leer."""
    bild = _bild_html(n, basis)
    if n["typ"] == "sprache":
        minuten, sekunden = divmod(int(n["dauer"] or 0), 60)
        dauer = f"{minuten}:{sekunden:02d}"
        # Padua Hotfix B7: Transkript (maskiert) > Platzhalter > Dauer.
        if n.get("text"):
            inhalt = html.escape(_TEXT_SPRACHE_ABGETIPPT.format(dauer=dauer, text=n["text"]))
        elif n.get("abgetippt", True):
            inhalt = html.escape(T._TEXT_SPRACHE.format(dauer=dauer))
        else:
            inhalt = html.escape(T._TEXT_SPRACHE_LAEUFT.format(dauer=dauer))
        klasse = "sprache"
    elif n["typ"] == "datei":
        inhalt = (
            f'<a href="{basis}{CHAT_PFAD}/datei/{n["id"]}">'
            + html.escape(_TEXT_DATEI.format(name=n["dateiname"] or "datei"))
            + "</a>"
        )
        if n["text"]:
            inhalt = sichere_html(n["text"]) + "<br>" + inhalt
        klasse = "datei"
    elif n["typ"] == "transkript":
        # Karte t_ea994c7f: die EINE Transkriptblase eines Interviews
        # (Padua, ``[interview] fliesstext``). Inhalt wie jede Bot-Zeile;
        # das Mikrofon steht im Text, kursiv macht das CSS.
        inhalt = sichere_html(n["text"])
        klasse = "transkript"
    elif n["typ"] == "system":
        # UX-Knoepfe-Karte, Abschnitt 3: eine Speicherquittung ("Notiert: …",
        # ein Rueckgaengig-Ergebnis) ist keine Aeusserung des Bots, sondern
        # eine Systemzeile -- gedaempft statt als Sprechblase. Der Inhalt
        # selbst ist unveraendert derselbe Text.
        inhalt = sichere_html(n["text"])
        klasse = "system"
    elif n["von"] == "bot" and n["text"] in _TEXTE_BUEHNE_NEUE_KARTE:
        # UX-Knoepfe-Karte, Abschnitt 5 (02.10.2026): dieselbe Zeile wie
        # ``aufnahme._TEXT_BUEHNE_NEUE_KARTE`` -- hier nur erkannt, um sie
        # antippbar zu machen (oeffnet den Tab "buehne" auf der vereinten
        # Seite). Ohne den echten Tab (Chat-Einzelseite, Telegram) ist der
        # Sprung ins Leere harmlos: nur das URL-Fragment aendert sich.
        inhalt = f'<a href="#buehne">{html.escape(n["text"])}</a>'
        klasse = "text"
    else:
        inhalt = sichere_html(n["text"])
        klasse = "text"

    teile = [
        f'<div class="blase {n["von"]} {klasse}" data-id="{n["id"]}">{bild}{inhalt}</div>'
    ]
    if n["knoepfe"]:
        knoepfe = "".join(
            f'<button type="button" data-message="{n["id"]}" '
            f'data-daten="{html.escape(daten, quote=True)}">'
            f"{html.escape(beschriftung)}</button>"
            for beschriftung, daten in n["knoepfe"]
        )
        teile.append(f'<div class="leiste-label">{html.escape(T._TEXT_ABKUERZUNG)}</div>')
        teile.append(f'<div class="leiste" data-message="{n["id"]}">{knoepfe}</div>')
    return "\n".join(teile)


def chat_koerper(daten: dict, nonce_wert: str, token: str, segment_ms: int,
                  basis: str = "", mit_nonce: bool = True,
                  mit_gruppenlink: bool = True, vad: dict | None = None) -> str:
    """Der Rumpf der Chatansicht -- ohne die Klammer aus ``web._seite``.

    Herausgeloest fuer die vereinte Seite (30.09.2026, Karte W): dort steht
    dieser Rumpf als eines von drei Panels in EINEM Dokument. ``chat_html``
    ruft ihn und haengt die Klammer davor -- die Einzelseite bleibt damit
    Zeichen fuer Zeichen, was sie war (``tests/test_web_koerper.py``).

    ``basis`` ist das Praefix vor jedem ``chat/...``-Pfad: auf der
    Chat-Einzelseite (``/g/<token>/chat``) leer, auf der vereinten Seite
    (``/g/<token>``) ``"<token>/"``, weil die Seite dort eine Ebene hoeher
    liegt. Es steht als ``data-basis`` am ``#fuss`` und wird dort vom
    JavaScript gelesen (``BASIS``).

    ``mit_nonce`` ist ``False`` auf der vereinten Seite: das Stand-Panel
    traegt dort bereits ein ``id="nonce"``-Feld mit demselben Wert (beide
    Panels bekommen denselben ``nonce_wert``) -- ein zweites Element mit
    derselben id waere ungueltiges HTML, und ``document.getElementById``
    faende ohnehin nur das erste. Die Chat-Einzelseite braucht ihr eigenes
    Feld weiterhin (Vorgabe ``True``).

    ``mit_gruppenlink`` ist ``False`` auf der vereinten Seite (Fix-Runde 1,
    Karte W): dort zeigt der Link auf ``/g/<token>`` -- also auf die Seite,
    auf der er selbst steht. Auf der Chat-Einzelseite (``/g/<token>/chat``)
    bleibt er, weil er dort tatsaechlich woanders hinfuehrt (Vorgabe
    ``True``).

    ``vad`` sind die fuenf Pausen-Schnitt-Zahlen (UX-Knoepfe-Karte,
    Brainstorm-VAD) -- ungesetzt gilt ``_vad_werte()`` (Umgebung), auf jeder
    Seite gleich, weil sie nicht je Gruppe variieren."""
    from interview_theater import web   # spaeter Import: web importiert web_chat

    vad = vad if vad is not None else _vad_werte()
    modus = bool(daten["interviewmodus"])
    # Task 2 (Kanban-Karte Buehne/PTT): der Brainstorm-Block steht jetzt
    # IMMER im Markup (wie #interview), nur ``hidden`` folgt der Phase --
    # dieselbe Quelle fuer das ``hidden``-Attribut und die ``nebenknopf``-
    # Klasse am Interview-Knopf, nicht das rohe ``daten.get("phase") == 4``.
    brainstorm_erlaubt = daten.get("brainstorm_knopf", True)
    # Task 5 (Padua Phase 1+2 Umbau, 03.10.2026): derselbe Aufbau wie der
    # Brainstorm-Knopf, aber mit umgekehrter Vorgabe -- anders als Brainstorm
    # (Vorgabe ``True``) bleibt das Hintergrund-Mithoeren unsichtbar, wenn der
    # Server den Schluessel aus irgendeinem Grund gar nicht mitschickt. Die
    # Berechnung selbst (Phase 1 UND Profilflag) steht in
    # ``web_daten.web_chatzustand`` (Task 4).
    diskussion_erlaubt = daten.get("diskussion_knopf", False)
    blasen = "\n".join(_blase_html(n, basis) for n in daten["nachrichten"])
    if not blasen:
        blasen = f'<p class="leer">{html.escape(T._TEXT_LEER)}</p>'

    nonce_feld = (
        f'<input type="hidden" id="nonce" value="{html.escape(nonce_wert, quote=True)}">\n'
        if mit_nonce else ""
    )
    gruppenlink = (
        f'<p><a href="{html.escape(token)}">'
        f"{html.escape(T._TEXT_ZUR_GRUPPENSEITE)}</a></p>\n"
        if mit_gruppenlink else ""
    )
    return (
        f"<h1>{html.escape(daten.get('titel') or T._TEXT_TITEL)}</h1>\n"
        f"{gruppenlink}"
        f'<noscript><p class="leer">{html.escape(T._TEXT_OHNE_JS)}</p></noscript>\n'
        f'<div class="verlauf" id="verlauf" data-letzte="{daten["letzte"]}" '
        f'data-aenderung="{int(daten.get("aenderung") or 0)}" '
        # Phasenscroll-Karte (04.10.2026): leer, wenn keine Phase bekannt
        # ist -- echte Phasen sind 1..7 und nie 0, das JS liest eine leere
        # Zeichenkette ueber ``parseInt`` ohnehin als 0 (``|| 0``).
        f'data-phase="{daten.get("phase") or ""}">\n'
        f"{blasen}\n</div>\n"
        f'<div class="tippt" id="tippt"></div>\n'
        f"{nonce_feld}"
        f'<div class="fuss" id="fuss" data-segment-ms="{int(segment_ms)}"\n'
        f'     data-vad-pause-ms="{int(vad["pause_ms"])}" '
        f'data-vad-max-ms="{int(vad["max_ms"])}" '
        f'data-vad-min-speech-ms="{int(vad["min_speech_ms"])}"\n'
        f'     data-vad-rms="{vad["rms"]}" '
        f'data-vad-floor-faktor="{vad["floor_faktor"]}"\n'
        f'     data-vad-kalibrierung="{1 if vad.get("kalibrierung", True) else 0}"\n'
        f'     data-kalibrierung-modus="'
        f'{html.escape(daten.get("kalibrierung_modus") or "", quote=True)}"\n'
        f'     data-interview="{1 if modus else 0}" '
        f'data-basis="{html.escape(basis, quote=True)}">\n'
        f'  <div class="uhr" id="uhr" hidden></div>\n'
        f'  <div class="pegel" id="pegel" hidden>'
        f'<span></span><i class="pegel-schwelle"></i></div>\n'
        f'  <button type="button" id="kalibrierung-neu" hidden>'
        f'{html.escape(T._TEXT_KALIBRIERUNG_MESSEN_KNOPF)}</button>\n'
        f'  <div class="kalibrierung-erinnerung" id="kalibrierung-erinnerung" '
        f'role="status" hidden></div>\n'
        f'  <div class="kalibrierung" id="kalibrierung" hidden>\n'
        f'    <p id="kalibrierung-text"></p>\n'
        f'    <div class="kalibrierung-balken" id="kalibrierung-balken" hidden '
        f'aria-label="{html.escape(T._TEXT_KALIBRIERUNG_BALKEN_LABEL, quote=True)}">\n'
        f'      <span></span><i class="kalibrierung-marke"></i>\n'
        f'    </div>\n'
        f'    <div class="kalibrierung-knoepfe">\n'
        f'      <button type="button" id="kalibrierung-start" hidden>'
        f'{html.escape(T._TEXT_KALIBRIERUNG_START_KNOPF)}</button>\n'
        f'      <button type="button" id="kalibrierung-sprechen" hidden>'
        f'{html.escape(T._TEXT_KALIBRIERUNG_SPRECHEN_KNOPF)}</button>\n'
        f'      <button type="button" id="kalibrierung-nochmal-hoeren" hidden>'
        f'{html.escape(T._TEXT_KALIBRIERUNG_MESSEN_KNOPF)}</button>\n'
        f'      <button type="button" id="kalibrierung-versuch" hidden>'
        f'{html.escape(T._TEXT_KALIBRIERUNG_NOCHMAL_KNOPF)}</button>\n'
        f'      <button type="button" id="kalibrierung-weiter-trotzdem" hidden>'
        f'{html.escape(T._TEXT_KALIBRIERUNG_WEITER_TROTZDEM)}</button>\n'
        f'      <button type="button" id="kalibrierung-ja" hidden>'
        f'{html.escape(T._TEXT_KALIBRIERUNG_JA_KNOPF)}</button>\n'
        f'      <button type="button" id="kalibrierung-nein" hidden>'
        f'{html.escape(T._TEXT_KALIBRIERUNG_NEIN_KNOPF)}</button>\n'
        f'    </div>\n'
        f'    <button type="button" id="kalibrierung-skip">'
        f'{html.escape(T._TEXT_KALIBRIERUNG_SKIP_KNOPF)}</button>\n'
        f'  </div>\n'
        f'  <div class="warteschlange" id="warteschlange"></div>\n'
        f'  <div class="fehler" id="fehler" role="alert" hidden></div>\n'
        f'  <p class="mitlauf-hinweis" id="mitlauf-hinweis" role="status" hidden></p>\n'
        f'  <div class="angehalten" id="angehalten" role="alert" hidden>\n'
        f'    <p id="angehalten-text"></p>\n'
        f'    <button type="button" id="nachreichen">'
        f'{html.escape(T._TEXT_REST_NACHREICHEN)}</button>\n'
        f'    <button type="button" id="verwerfen">'
        f'{html.escape(T._TEXT_REST_VERWERFEN)}</button>\n'
        f'  </div>\n'
        + (
            f'  <button type="button" id="brainstorm" data-laeuft="0" '
            f'data-pausiert="0"'
            + ('' if brainstorm_erlaubt else ' hidden')
            + f'>{html.escape(T._TEXT_BRAINSTORM_AN)}</button>\n'
            f'  <div class="interview-aktionen" id="brainstorm-aktionen" hidden>\n'
            f'    <button type="button" id="brainstorm-pause">'
            f'{html.escape(T._TEXT_INTERVIEW_PAUSE)}</button>\n'
            f'    <button type="button" id="brainstorm-beenden">'
            f'{html.escape(T._TEXT_INTERVIEW_ENDEN)}</button>\n'
            f'  </div>\n'
        )
        + (
            f'  <button type="button" id="diskussion" data-laeuft="0" '
            f'data-pausiert="0"'
            + ('' if diskussion_erlaubt else ' hidden')
            + f'>{html.escape(T._TEXT_DISKUSSION_AN)}</button>\n'
            f'  <div class="interview-aktionen" id="diskussion-aktionen" hidden>\n'
            f'    <button type="button" id="diskussion-pause">'
            f'{html.escape(T._TEXT_INTERVIEW_PAUSE)}</button>\n'
            f'    <button type="button" id="diskussion-beenden" '
            f'data-discussion-done="1">'
            f'{html.escape(T._TEXT_DISKUSSION_FERTIG_KNOPF)}</button>\n'
            f'  </div>\n'
        )
        + (
            f'  <button type="button" id="interview" data-laeuft="{1 if modus else 0}" '
            f'data-pausiert="{1 if modus else 0}"'
            + (' class="nebenknopf"' if brainstorm_erlaubt else "")
            # Padua Hotfix B6: ausserhalb von Phase 3 (oder bei laufender
            # Aufnahme) kein Angebot -- dieselbe Bedingung wie das JS-Pendant
            # ``zustand.knopfErlaubt`` oben.
            + ('' if daten.get("interview_knopf", True) or modus else ' hidden')
            + '>'
            f'{html.escape(T._TEXT_INTERVIEW_AUS if modus else T._TEXT_INTERVIEW_AN)}'
            f'</button>\n'
            f'  <div class="interview-aktionen" id="interview-aktionen"'
            f'{"" if modus else " hidden"}>\n'
            f'    <button type="button" id="interview-pause">'
            f'{html.escape(T._TEXT_INTERVIEW_WEITER if modus else T._TEXT_INTERVIEW_PAUSE)}'
            f'</button>\n'
            f'    <button type="button" id="interview-beenden">'
            f'{html.escape(T._TEXT_INTERVIEW_ENDEN)}</button>\n'
            f'  </div>\n'
        )
        + _ptt_anzeige_html()
        + f'  <div class="zeile">\n'
        f'    <input type="text" id="eingabe" autocomplete="off" '
        f'placeholder="{html.escape(_platzhalter_fuer(daten.get("phase"), daten.get("fragen_aktuell")), quote=True)}">\n'
        f'    <button type="button" id="ptt"{" hidden" if modus else ""} title="'
        f'{html.escape(T._TEXT_PTT, quote=True)}">🎤</button>\n'
        f'    <button type="button" id="senden">'
        f'{html.escape(T._TEXT_SENDEN)}</button>\n'
        f"  </div>\n"
        f"</div>\n"
        # Bild-Overlay-Karte: EIN Overlay fuer beide Seiten (Chat-Einzelseite
        # UND vereinte Seite teilen sich diesen Koerper). Ausserhalb von
        # ``.fuss``, als eigenes Vollbild-Element -- seine Groesse kommt aus
        # ``position: fixed; inset: 0`` in ``_CSS_CHAT``, nicht aus seiner
        # Stellung im Markup.
        f'<div class="bild-overlay" id="bild-overlay" hidden>\n'
        f'  <button type="button" id="bild-overlay-schliessen" '
        f'aria-label="{html.escape(_TEXT_BILD_SCHLIESSEN, quote=True)}">✕</button>\n'
        f'  <img id="bild-overlay-img" src="" alt="">\n'
        f"</div>\n"
    )


def _ptt_anzeige_html() -> str:
    """Die Anzeige-Box ueber dem Mikrofon-Knopf: Schloss-/Wegwisch-Hinweis,
    Timer, Pegel, Kurztipp-Hinweis, Senden/Verwerfen im gesperrten Zustand
    (Kanban-Karte Buehne/PTT, 04.10.2026 -- Telegram-Vorbild). Reihenfolge
    der Kinder ist freie Gestaltung, nur die IDs sind Vorgabe -- die
    e2e-Tests suchen danach."""
    return (
        '  <div id="ptt-anzeige" hidden>\n'
        '    <span id="ptt-schloss">🔒 ↑</span>\n'
        f'    <span id="ptt-wisch-hinweis">‹ {html.escape(T._TEXT_PTT_WISCHEN)}</span>\n'
        '    <span id="ptt-zeit"></span>\n'
        '    <div class="pegel" id="ptt-pegel" hidden><span></span></div>\n'
        '    <span id="ptt-hinweistext" hidden></span>\n'
        f'    <button type="button" id="ptt-senden" hidden>■ '
        f'{html.escape(T._TEXT_SENDEN)}</button>\n'
        f'    <button type="button" id="ptt-verwerfen" hidden '
        f'aria-label="{html.escape(T._TEXT_PTT_VERWERFEN, quote=True)}">✕</button>\n'
        '  </div>\n'
    )


def chat_html(daten: dict, nonce_wert: str, token: str, praefix: str,
              segment_ms: int) -> str:
    """Die Chatansicht.

    Sie haengt sich in ``web._seite`` ein (dieselbe Klammer, dasselbe
    Grund-CSS), aber **ohne** dessen sanftes Nachladen: das tauscht den
    ``<body>`` aus, und mitten in einer laufenden Aufnahme wuerde das
    Recorder, Timer und Warteschlange mitreissen. Nachgeladen wird hier
    gezielt, per Poll (``_CHAT_JS``), und nur der Verlauf."""
    from interview_theater import web   # spaeter Import: web importiert web_chat

    return web._seite(
        daten.get("titel") or T._TEXT_TITEL, _CSS_CHAT,
        chat_koerper(daten, nonce_wert, token, segment_ms),
        nachladen=False, skript=_js(),
    )


def beantworte_get(handler, db_pfad: str, token: str, unterpfad: str,
                   praefix: str, schluessel: bytes, query: str) -> None:
    """Alles unter ``/g/<token>/chat``: die Seite, der Zustands-Poll und die
    Dateien aus ``sende_datei``. Alles Unbekannte ist 404 -- wie bei
    ``web._beantworte_gruppenseite``."""
    from interview_theater import web

    # Mit Schraegstrich am Ende (``/chat/``) zeigten die relativen Verweise
    # der Seite -- der Link zur Gruppenseite, die Dateien -- ins Leere
    # (Review-Befund 12). ``unterpfad`` kommt schon ohne Schraegstrich an,
    # deshalb der Blick auf den rohen Pfad.
    if urllib.parse.urlsplit(handler.path).path.endswith("/"):
        handler._antworte(404, web.nicht_gefunden_html())
        return
    if unterpfad == "":
        _sende_seite(handler, db_pfad, token, praefix, schluessel)
        return
    if unterpfad == "zustand":
        _sende_zustand(handler, db_pfad, token, query, schluessel)
        return
    if unterpfad.startswith("datei/"):
        _sende_datei(handler, db_pfad, token, unterpfad[len("datei/"):])
        return
    # Der laufende Text (30.09.2026, Karte W). Nur die Weiche steht hier;
    # der Strom selbst liegt in web_vereint.py. Lokaler Import, weil
    # web_vereint seinerseits web_chat braucht (die Panels der vereinten
    # Seite) -- im Modulkopf waere das ein Zyklus.
    from interview_theater import web_vereint

    if unterpfad == web_vereint.STROM_PFAD:
        web_vereint.sende_strom(handler, db_pfad, token, query)
        return
    handler._antworte(404, web.nicht_gefunden_html())


@contextmanager
def schreibend(db_pfad: str):
    """Eine schreibende Verbindung je Anfrage -- ``db.verbinde`` und nicht
    ``web_daten.oeffne_lesend``, wie im POST-Handler der Gruppenseite. WAL und
    ``busy_timeout`` (5 s) tragen das Nebeneinander mit den Bot-Prozessen; der
    modulweite ``repo._LOCK`` ist prozesslokal und richtet dagegen nichts aus
    (dieselbe Annahme wie ``scripts/begruessen.py``)."""
    conn = db.verbinde(db_pfad)
    try:
        yield conn
    finally:
        conn.close()


def _gruppe_oder_404(handler, db_pfad: str, token: str,
                     schliessen: bool = False) -> int | None:
    """Die chat_id zum Token, oder 404 und None -- auch fuer eine Gruppe, die
    nicht im Web-Kanal arbeitet (Abschlussreview I3): dort liest kein Bot
    ``web_post``, und was hier ankaeme, verschwaende still.

    ``schliessen`` fuer die POST-Wege: die 404 kommt dort vor dem Lesen des
    Koerpers (``web.schliesse_nach_antwort``)."""
    from interview_theater import web

    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        chat_id = web_daten.web_chat_id_nach_token(conn, token)
    finally:
        conn.close()
    if chat_id is None:
        if schliessen:
            web.schliesse_nach_antwort(handler)
        handler._antworte(404, web.nicht_gefunden_html())
    return chat_id


def _koerper_oder_400(handler, token: str, schluessel: bytes) -> dict | None:
    """JSON-Rumpf und Nonce in einem Griff. Reihenfolge wie in
    ``web._beantworte_post``: der Nonce kommt nach dem Token."""
    from interview_theater import web

    try:
        daten = handler._koerper()
    except ValueError as fehler:
        handler._fehler(400, str(fehler))
        return None
    if not web.nonce_gueltig(schluessel, token, daten.get("nonce")):
        handler._fehler(403, _TEXT_FEHLER_VERALTET)
        return None
    return daten


def _angenommen(handler, nutzlast: dict) -> None:
    """**202, nicht 200:** der Bot hat noch nicht geantwortet, die Nachricht
    liegt im Eingang. Der Browser schaltet daraufhin auf einen schnellen Poll,
    statt auf eine Antwort in dieser Anfrage zu warten -- ein Gespraechszug
    dauert Sekunden, und eine HTTP-Verbindung so lange offen zu halten waere
    ein Thread je Nachricht."""
    handler._antworte(
        202, json.dumps(nutzlast, ensure_ascii=False),
        "application/json; charset=utf-8",
    )


#: Welcher POST-Weg in welchen Topf zaehlt (Karte Padua S, Aufgabe 3).
#: Senden, Knopf und Umschalter teilen sich einen: alle drei loesen einen
#: Bot-Zug mit einem bezahlten Modellaufruf aus, und zwei Toepfe liessen
#: jemanden abwechseln und die Rate verdoppeln. Audio hat einen eigenen --
#: ein Upload kostet Platte und einen bezahlten Whisper-Aufruf, eine andere
#: Ressource.
_TOEPFE = {
    "senden": web_grenze.TOPF_NACHRICHT,
    "knopf": web_grenze.TOPF_NACHRICHT,
    "interview": web_grenze.TOPF_NACHRICHT,
    "audio": web_grenze.TOPF_UPLOAD,
    "phase": web_grenze.TOPF_NACHRICHT,
    "kalibrierung": web_grenze.TOPF_NACHRICHT,
}


def beantworte_post(handler, db_pfad: str, token: str, unterpfad: str,
                    schluessel: bytes) -> None:
    """Alles, was der Browser schickt. Reihenfolge der Pruefungen:
    **Pfad, Token, Rate-Limit, Handler** -- erst 404, dann 429, dann die
    Pruefungen des Handlers (Nonce, Wert).

    **Das Rate-Limit steht VOR dem Handler** (Aufgabe 3) und damit vor jeder
    Wirkung: eine abgewiesene Nachricht darf weder in ``web_post`` landen
    noch eine Datei auf die Platte legen. Das Limit braucht die ``chat_id`` und
    steht deshalb erst nach der Token-Pruefung (``_gruppe_oder_404``). Dass es
    auch vor dem Nonce zaehlt, ist Absicht: wer das Token hat, bekommt ueber
    die Seite ohnehin einen gueltigen Nonce -- die Reihenfolge gibt also
    keinen zusaetzlichen Hebel, und das Limit steht an genau einer Stelle."""
    from interview_theater import web

    # Alle drei Absagen hier liegen VOR dem Lesen des Koerpers: danach wird
    # die Verbindung geschlossen, sonst laese der Server den Koerper als
    # naechste Anfragezeile (``web.schliesse_nach_antwort``).
    if unterpfad not in _POSTWEGE:
        web.schliesse_nach_antwort(handler)
        handler._antworte(404, web.nicht_gefunden_html())
        return
    chat_id = _gruppe_oder_404(handler, db_pfad, token, schliessen=True)
    if chat_id is None:
        return
    warte = web_grenze.pruefe(_TOEPFE[unterpfad], chat_id)
    if warte:
        web.schliesse_nach_antwort(handler)
        _zu_schnell(handler, db_pfad, chat_id, warte)
        return
    try:
        _POSTWEGE[unterpfad](handler, db_pfad, token, chat_id, schluessel)
    except sqlite3.Error as fehler:
        handler.log_error("Datenbankfehler im Web-Chat: %s", fehler)
        handler._fehler(500, "Die Datenbank ist gerade nicht beschreibbar.")


def _zu_schnell(handler, db_pfad: str, chat_id: int, warte: int) -> None:
    """429 mit ``Retry-After`` und einem Satz.

    Der Vorfall geht **einmal je Fenster** in die Datenbank, nicht je
    Anfrage: eine Flut von fuenfzig schriebe sonst dreissig Zeilen und
    faerbte das Dashboard rot, ohne mehr zu sagen als eine. Gemerkt wird an
    der Sperre selbst (ein Zaehler-Topf mit Fenstergroesse 1), damit dafuer
    keine zweite Buchhaltung noetig ist."""
    handler.send_response(429)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    roh = _TEXT_ZU_SCHNELL.encode("utf-8")
    handler.send_header("Content-Length", str(len(roh)))
    handler.send_header("Retry-After", str(warte))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(roh)
    if web_grenze.pruefe(web_grenze.TOPF_VORFALL, chat_id) == 0:
        try:
            with schreibend(db_pfad) as conn:
                repo.merke_vorfall(
                    conn, chat_id, None, "web_rate_limit",
                    f"Rate-Limit gegriffen, {warte}s bis zum naechsten Platz",
                )
        except Exception:  # noqa: BLE001 -- ein Vorfall darf die Absage nie mitreissen
            log.exception("Vorfall zum Rate-Limit nicht geschrieben, chat_id=%s", chat_id)


def _senden(handler, db_pfad: str, token: str, chat_id: int,
            schluessel: bytes) -> None:
    """Eine Textnachricht der Gruppe.

    Der Text wird **nicht** gefiltert: gefiltert wird beim Lesen
    (``sichere_html``). Der Bot soll den Wortlaut sehen -- ein ``<`` in einer
    Nachricht ist ein Zeichen, keine Absicht."""
    daten = _koerper_oder_400(handler, token, schluessel)
    if daten is None:
        return
    text = str(daten.get("text") or "").strip()
    if not text:
        handler._fehler(400, _TEXT_FEHLER_LEER)
        return
    if len(text) > MAX_TEXT_ZEICHEN:
        handler._fehler(400, _TEXT_FEHLER_LANG)
        return
    with schreibend(db_pfad) as conn:
        message_id = repo.lege_web_post_an(
            conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_TEXT, text=text,
        )
    _angenommen(handler, {"message_id": message_id})


def endung_fuer(content_type) -> str | None:
    """Die Endung zu einem Content-Type, oder None.

    Parameter werden abgeschnitten (``audio/webm;codecs=opus``), gross und
    klein ist gleich. Eine **Allowlist** und keine Ablehnliste: was hier nicht
    steht, kommt nicht an."""
    return web_kanal.endung_fuer_mime(content_type)


def haupttyp(handler) -> str:
    """Der Haupt-MIME-Typ der Anfrage, fuer die Spalte ``mime`` -- ohne
    Parameter (``audio/webm;codecs=opus`` -> ``audio/webm``)."""
    roh = handler.headers.get("Content-Type") or ""
    return roh.split(";", 1)[0].strip().lower()


#: Dateianfaenge, an denen sich ein Audioformat wirklich erkennen laesst --
#: Endung zuerst, dann der Pruefer.
#:
#: **Warum nicht der Content-Type-Header:** der sagt, was der Absender
#: behauptet. An der Endung haengt der MIME-Typ, den Whisper sieht
#: (``stt.mime_typ``), und ein falscher laesst den Auftrag dauerhaft auf
#: 'pending' stehen -- 89,7 s statt 2,0 s, im Betrieb nur als "haengt"
#: sichtbar, und bezahlt (AGENTS.md, Falle 3). Der Header bleibt als
#: billiger Vorfilter (415, ohne den Koerper zu lesen); entscheiden tun die
#: Bytes.
#:
#: Die Reihenfolge ist Absicht: der MP3-Frame-Sync steht zuletzt, weil er
#: mit zwei Bytes die unschaerfste Regel ist.
MAGISCHE_ANFAENGE = (
    # EBML -- WebM/Matroska, das Format von MediaRecorder in Chrome/Firefox.
    (".webm", lambda k: k[:4] == b"\x1a\x45\xdf\xa3"),
    # OggS -- Opus/Vorbis, auch die Telegram-Sprachnachricht.
    (".ogg", lambda k: k[:4] == b"OggS"),
    # ISO-BMFF: 'ftyp' ab Byte 4, davor die Boxlaenge. mp4/m4a, Safari.
    (".m4a", lambda k: len(k) >= 12 and k[4:8] == b"ftyp"),
    # RIFF....WAVE
    (".wav", lambda k: len(k) >= 12 and k[:4] == b"RIFF" and k[8:12] == b"WAVE"),
    # ID3-Tag am Anfang.
    (".mp3", lambda k: k[:3] == b"ID3"),
    # MPEG-Frame-Sync: elf gesetzte Bits. Zuletzt, weil am unschaerfsten.
    (".mp3", lambda k: len(k) >= 2 and k[0] == 0xFF and (k[1] & 0xE0) == 0xE0),
)

#: Wie viele Bytes vom Anfang fuer die Erkennung reichen. Zwoelf genuegen
#: allen Regeln oben; gelesen wird trotzdem der ganze (begrenzte) Koerper --
#: haeppchenweise zu lesen brachte hier nichts und macht die Groessenpruefung
#: unuebersichtlich.
MAGISCHE_BYTES = 12

_TEXT_FEHLER_INHALT = "Diese Datei ist keine Audioaufnahme."


def endung_aus_bytes(kopf: bytes) -> str | None:
    """Die Endung aus dem Dateianfang, oder None.

    Eine **Allowlist**: was hier nicht steht, kommt nicht durch. Und die
    Endung, die hier herauskommt, ist die, unter der die Datei abgelegt wird
    -- ``stt.mime_typ`` leitet den MIME-Typ fuer Whisper daraus ab."""
    if not isinstance(kopf, (bytes, bytearray)) or not kopf:
        return None
    for endung, passt in MAGISCHE_ANFAENGE:
        try:
            if passt(bytes(kopf)):
                return endung
        except (IndexError, TypeError):
            continue
    return None


def _audio_verz() -> str:
    """``IT_AUDIO`` wie ``einstellungen._VORGABEWERTE`` -- der Webserver laedt
    keine ``Einstellungen`` (er braucht weder LLM- noch STT-Variablen), liest
    aber dieselbe Variable mit demselben Vorgabewert."""
    return os.environ.get("IT_AUDIO") or "audio"


#: Wie viel wir beim Verwerfen eines zu grossen Koerpers hoechstens lesen.
#: Das Doppelte von ``MAX_AUDIO_BYTES`` reicht fuer jeden ehrlichen Client,
#: der die Grenze nur knapp verfehlt hat -- einer, der um ein Vielfaches
#: mehr ankuendigt, bekommt den Verbindungsabbruch bewusst.
_VERWERF_GRENZE = MAX_AUDIO_BYTES * 2
_VERWERF_STUECK = 64 * 1024


def _verwerfe_koerper(handler, laenge: int) -> None:
    """Liest einen abgelehnten Koerper vollstaendig weg, statt ihn liegen zu
    lassen.

    Ohne das fuehrt eine Ablehnung VOR dem Lesen (``Content-Length`` zu
    gross) bei HTTP/1.1 zu einem Verbindungsabbruch, waehrend der Client noch
    sendet: ``urllib`` schreibt den ganzen Koerper in einem Zug, ohne auf
    eine Zwischenantwort zu warten, und saehe statt der 413-Antwort einen
    ``Broken pipe``. Verworfen wird in Stuecken, damit kein zu grosser
    Koerper komplett im Speicher landet."""
    uebrig = min(max(0, laenge), _VERWERF_GRENZE)
    while uebrig > 0:
        stueck = handler.rfile.read(min(uebrig, _VERWERF_STUECK))
        if not stueck:
            return
        uebrig -= len(stueck)


def _audio(handler, db_pfad: str, token: str, chat_id: int,
           schluessel: bytes) -> None:
    """Ein Aufnahmesegment aus dem Browser.

    **Roher Koerper, kein multipart:** die Standardbibliothek hat keinen
    Multipart-Parser, den man verantworten will (``cgi.FieldStorage`` ist in
    Python 3.13 entfernt), und MediaRecorder liefert genau einen Blob. Der
    Nonce steht deshalb in der Query -- er ist ein CSRF-Merkmal, kein
    Geheimnis ueber die Seite hinaus, und das Token steht ohnehin schon im
    Pfad und damit in jeder Logzeile.

    Reihenfolge der Pruefungen: **``Content-Length`` lesen, Typ-Vorfilter
    (415), Groesse (400/413), Nonce (403), Dauer (400), dann erst der
    Koerper, dann die Magic Bytes (415)** -- die Kopfzeilen kosten nichts,
    der Koerper kostet Speicher. Jeder ablehnende Zweig vor dem Lesen
    verwirft zuerst den angekuendigten Koerper (``_verwerfe_koerper``), bevor
    er antwortet: sonst sieht der Client bei einer grossen ``Content-Length``
    denselben Verbindungsabbruch wie frueher im 413-Zweig, nur jetzt bei
    415/403/400 -- ``urllib`` schreibt den ganzen Koerper in einem Zug, ohne
    auf eine Zwischenantwort zu warten.

    **Der Content-Type-Header ist nur ein Vorfilter, keine Entscheidung**
    (Karte Padua S, Aufgabe 4). Er sagt, was der Absender behauptet; die
    Endung, unter der die Datei abgelegt wird, und der ``mime``-Wert in der
    Datenbank kommen aus den Magic Bytes des tatsaechlichen Koerpers
    (``endung_aus_bytes``). Ein WebM mit ``Content-Type: audio/ogg`` landet
    als ``.webm`` -- sonst sieht Whisper ``audio/ogg`` zu einer WebM-Datei
    und der Auftrag bleibt dauerhaft auf 'pending' stehen (AGENTS.md,
    Falle 3).

    Geschrieben wird erst die Zeile, dann die Datei (der Pfad enthaelt die
    id), und erst danach der Verweis; bis dahin haelt
    ``WebKanal.hole_updates`` die Zeile zurueck (Abschlussreview C1).
    Scheitert die Datei, bleibt eine Zeile ohne ``datei`` stehen, geht nach
    ``web_kanal.DATEI_FRIST_S`` trotzdem an den Bot, und ``lade_datei``
    wirft -- ``aufnahme`` bittet die Gruppe dann, es nochmal zu schicken."""
    from interview_theater import web

    try:
        laenge = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        web.schliesse_nach_antwort(handler)
        handler._fehler(400, _TEXT_FEHLER_ANFRAGE)
        return

    # Billiger Vorfilter: was schon im Header nicht nach Audio aussieht,
    # kostet uns nicht einmal das Lesen. Die Endung, die am Ende gespeichert
    # wird, kommt trotzdem aus den Magic Bytes -- siehe unten.
    if endung_fuer(handler.headers.get("Content-Type")) is None:
        _verwerfe_koerper(handler, laenge)
        handler._fehler(415, _TEXT_FEHLER_TYP)
        return
    if laenge <= 0:
        web.schliesse_nach_antwort(handler)
        handler._fehler(400, _TEXT_FEHLER_LEER_AUDIO)
        return
    if laenge > MAX_AUDIO_BYTES:
        _verwerfe_koerper(handler, laenge)
        handler._fehler(413, _TEXT_FEHLER_GROSS)
        return

    felder = urllib.parse.parse_qs(urllib.parse.urlsplit(handler.path).query)
    # Der Nonce steht seit dem 30.09.2026 in einer Kopfzeile statt in der
    # Query (E-S9): eine Query landet in der Serverlogzeile, eine Kopfzeile
    # nicht. Die Query bleibt als Rueckfall, damit ein Telefon mit altem,
    # gecachtem JavaScript den Tag noch zu Ende bringt.
    kennung = handler.headers.get(web.NONCE_KOPFZEILE) or (felder.get("nonce") or [""])[0]
    if not web.nonce_gueltig(schluessel, token, kennung):
        _verwerfe_koerper(handler, laenge)
        handler._fehler(403, _TEXT_FEHLER_VERALTET)
        return
    roh_dauer = (felder.get("dauer") or [""])[0]
    #: Nur ASCII-Ziffern, und hoechstens 10 Stellen, BEVOR ``int()`` sie sieht:
    #: ein Unicode-Ziffernzeichen wie "²" (U+00B2) erfuellt ``isdigit()``,
    #: aber nicht ``isascii()`` -- ohne die Pruefung wirft ``int("²")`` ein
    #: nicht abgefangenes ``ValueError``. Und seit Python 3.11 hat ``int()``
    #: eine Umwandlungsgrenze fuer sehr lange Ziffernfolgen
    #: (``sys.set_int_max_str_digits``, Vorgabe 4300) -- die Laengengrenze
    #: haelt eine vom Client frei waehlbare Ziffernfolge weit darunter, statt
    #: sich auf die eingebaute Grenze zu verlassen.
    gueltig_ziffern = (
        roh_dauer.isascii() and roh_dauer.isdigit() and len(roh_dauer) <= 10
    )
    dauer = int(roh_dauer) if gueltig_ziffern else None
    if dauer is None or not 0 < dauer <= MAX_DAUER_S:
        _verwerfe_koerper(handler, laenge)
        handler._fehler(400, _TEXT_FEHLER_DAUER)
        return

    # Pausen-Schnitt (VAD) und Brainstorm-Flag (02.10.2026): beide optional,
    # beide vom Client gesetzt (web_chat._CHAT_JS, postAudio). Ein unbekannter
    # Wert zaehlt wie keiner -- das ist Bookkeeping fuer den Brainstorm-
    # Trigger, kein Sicherheitsmerkmal, eine falsche Zeichenkette soll den
    # Upload nicht scheitern lassen.
    roh_grund = (felder.get("grund") or [""])[0]
    grund = roh_grund if roh_grund in ("pause", "cap", "ende") else None
    brainstorm = (felder.get("brainstorm") or [""])[0] == "1"
    # Task 5 (Padua Phase 1+2 Umbau, 03.10.2026): dasselbe Bookkeeping wie
    # ``brainstorm``, nur fuer das Hintergrund-Mithoeren in Phase 1.
    diskussion = (felder.get("diskussion") or [""])[0] == "1"

    # redeMs (Kanban-Karte Mithoeren SICHER, 03.10.2026): wie viele ms
    # erkannte Rede der Client gemessen hat -- rein diagnostisch, seit
    # Aufgabe 1a kein Upload-Gate mehr (Birk, Szenario A). Dieselbe
    # defensive Ziffernpruefung wie bei ``dauer``, aber OHNE dessen 400: ein
    # fehlender oder kaputter Wert ist einfach None, nie ein Fehler.
    roh_rede = (felder.get("rede") or [""])[0]
    rede_ms = (
        int(roh_rede)
        if roh_rede.isascii() and roh_rede.isdigit() and len(roh_rede) <= 10
        else None
    )

    # kalibrierung (Task 2, Kanban-Karte Mithoeren SICHER/Kalibrierung,
    # 03.10.2026): derselbe additive Weg wie "brainstorm" -- ein Clip des
    # Kalibrierungsablaufs, nie ein gewoehnliches Segment. Kein
    # Sicherheitsmerkmal, ein falscher Wert zaehlt einfach wie keiner.
    kalibrierung = (felder.get("kalibrierung") or [""])[0] == "1"

    koerper = handler.rfile.read(laenge)
    if len(koerper) != laenge:
        web.schliesse_nach_antwort(handler)
        handler._fehler(400, _TEXT_FEHLER_LEER_AUDIO)
        return

    # Jetzt erst die Entscheidung, mit den tatsaechlichen Daten statt mit
    # einer Behauptung des Absenders.
    endung = endung_aus_bytes(koerper[:MAGISCHE_BYTES])
    if endung is None:
        handler._fehler(415, _TEXT_FEHLER_INHALT)
        return

    with schreibend(db_pfad) as conn:
        message_id = repo.lege_web_post_an(
            conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
            dauer=dauer, mime=stt.mime_typ(Path(f"x{endung}")),
            schnittgrund=grund, brainstorm=brainstorm, diskussion=diskussion,
            rede_ms=rede_ms, kalibrierung=kalibrierung,
        )
        # Absolut (I5): der Bot liest den Pfad in SEINEM Prozess, mit seinem
        # Arbeitsverzeichnis. Ein relativer Pfad hinge am cwd zweier Units.
        ziel = web_kanal.eingangspfad(
            _audio_verz(), chat_id, message_id, endung,
        ).resolve()
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(koerper)
        # Erst jetzt der Verweis: bis dahin haelt WebKanal.hole_updates die
        # Zeile zurueck (C1), statt den Bot einen leeren Pfad lesen zu lassen.
        repo.setze_web_datei(conn, message_id, str(ziel))
    _angenommen(handler, {"message_id": message_id})


def knopf_erlaubt(leiste, daten) -> bool:
    """Steht ``daten`` in dieser Leiste?

    **Die eine Pruefung des Knopfwegs.** Geprueft wird gegen die Leiste aus
    ``web_post`` und NICHT gegen ``knopf.message_id``: die ist nur gesetzt,
    wenn ein Aufrufer ``repo.merke_knopf_nachricht`` ruft, und das tun 22 von
    47 Sendestellen -- ``knoepfe.biete_einstieg`` zum Beispiel nicht. Eine
    Pruefung dagegen wuerde die Einstiegsknoepfe abweisen. Die Leiste in
    ``web_post`` schreibt ``WebKanal.sende_mit_knoepfen`` selbst; sie IST per
    Konstruktion, was gerade haengt.

    Ohne diese Pruefung waere jeder Knopf jeder Gruppe per ``curl``
    drueckbar, sobald jemand einen Link hat -- und die ``k:<id>`` sind
    fortlaufende Zahlen."""
    if not leiste or not isinstance(daten, str) or not daten:
        return False
    return any(daten == eintrag[1] for eintrag in leiste)


def _knopf(handler, db_pfad: str, token: str, chat_id: int,
          schluessel: bytes) -> None:
    """Ein Knopfdruck der Gruppe.

    Der Server stellt **nur** fest, dass der Knopf hier steht, und legt dann
    ein ``callback_query``-Update an. Die Wirkung macht ``knoepfe.behandle``
    im Bot-Prozess -- unveraendert, samt der Idempotenz-Sperre im ``repo``
    (Zusage 3: der zweite Druck wird beantwortet, wirkt aber nicht). Es gibt
    hier keinen zweiten Knopf-Handler und keinen Modellaufruf (Zusage 2)."""
    daten = _koerper_oder_400(handler, token, schluessel)
    if daten is None:
        return
    roh_id = daten.get("message_id")
    if not isinstance(roh_id, int) or isinstance(roh_id, bool) or roh_id < 1:
        handler._fehler(400, _TEXT_FEHLER_ANFRAGE)
        return
    wert = daten.get("data")

    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        leiste = web_daten.web_leiste(conn, chat_id, roh_id)
    finally:
        conn.close()
    if not knopf_erlaubt(leiste, wert):
        handler.log_error(
            "Knopfdruck abgewiesen: chat_id=%s message_id=%s leiste=%s",
            chat_id, roh_id, "fehlt" if leiste is None else len(leiste),
        )
        handler._fehler(400, _TEXT_FEHLER_KNOPF)
        return

    with schreibend(db_pfad) as schreiber:
        post_id = repo.lege_web_post_an(
            schreiber, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_KNOPF,
            daten=wert, bezug_message_id=roh_id,
        )
    _angenommen(handler, {"post_id": post_id})


#: Die zwei Befehle, die der Umschalter schickt. Woertlich die aus
#: ``befehle._BEKANNTE_BEFEHLE``: der Weg in den Interviewmodus ist
#: deterministisch und existiert schon (``befehle._befehl_interview`` /
#: ``_befehl_fertig``), und die Klasse einer Aufnahme haengt NUR am Modus
#: (``aufnahme.klasse_fuer``). Eine zweite Moduslogik hier waere eine zweite
#: Wahrheit -- und die eine, die dann irgendwann falsch ist.
BEFEHL_INTERVIEW_AN = "/interview"
BEFEHL_INTERVIEW_AUS = "/fertig"


def _interview(handler, db_pfad: str, token: str, chat_id: int,
               schluessel: bytes) -> None:
    """Der Interview-Umschalter (Birk, 30.09.2026, Punkt 1).

    Schickt ``/interview`` bzw. ``/fertig`` als Eingang. Der Bot faengt den
    Slash-Text in ``befehle.behandle`` ab, **bevor** ein Kontext gebaut oder
    ein Modell gerufen wird -- derselbe Weg wie bei einem getippten Befehl.

    In der Chatansicht bleibt die Zeile verborgen (``typ='befehl'``):
    Slash-Befehle werden nicht beworben (AGENTS.md), der Knopf steht schon da.

    ``an`` muss ein echter boolescher Wert sein. Der Fallstrick daneben ist
    dokumentiert: ``repo.setze_szene_usa`` nimmt einen bool, und ein
    nicht-leerer String ist wahr -- ein ``"nein"`` endete dort als
    Zustimmung. Hier wird deshalb nicht geraten."""
    daten = _koerper_oder_400(handler, token, schluessel)
    if daten is None:
        return
    an = daten.get("an")
    if not isinstance(an, bool):
        handler._fehler(400, _TEXT_FEHLER_ANFRAGE)
        return
    with schreibend(db_pfad) as conn:
        message_id = repo.lege_web_post_an(
            conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_BEFEHL,
            text=BEFEHL_INTERVIEW_AN if an else BEFEHL_INTERVIEW_AUS,
        )
    _angenommen(handler, {"message_id": message_id})


def _phase(handler, db_pfad: str, token: str, chat_id: int,
           schluessel: bytes) -> None:
    """Der Klick auf eine Phase (Karte W). Nur die Weiche steht hier."""
    from interview_theater import web_vereint

    web_vereint.phase_post(handler, db_pfad, token, chat_id, schluessel)


def _kalibrierung(handler, db_pfad: str, token: str, chat_id: int,
                  schluessel: bytes) -> None:
    """Task 2 (Kanban-Karte Mithoeren SICHER/Kalibrierung, 03.10.2026): die
    zweite "zu leise"-Messung in Folge einer Sitzung merkt gruppenweit, dass
    ein Handy in der Mitte fuer diesen Raum nicht reicht
    (``gruppe.kalibrierung_modus = 'herumreichen'``) -- unabhaengig davon, ob
    die Gruppe danach den Versuch- oder den Weiter-trotzdem-Knopf drueckt, und
    unabhaengig von jedem Audio-Upload (der an dieser Stelle noch gar nicht
    stattgefunden haben muss).

    Reiner Metadatum-Schreibweg wie ``web_schreiben.py``, kein Knopf im
    ``knoepfe``-Sinn und kein Modellaufruf (Zusage 2 gilt analog): die
    Entscheidung faellt rein client-seitig aus der RMS-Messung, hier wird
    nur das Ergebnis gemerkt."""
    daten = _koerper_oder_400(handler, token, schluessel)
    if daten is None:
        return
    with schreibend(db_pfad) as conn:
        repo.setze_kalibrierung_modus_herumreichen(conn, chat_id)
    handler._antworte(
        200, json.dumps({"ok": True}), "application/json; charset=utf-8",
    )


#: Die Tabelle der POST-Wege. Eine Tabelle statt einer if-Kette: ein neuer Weg
#: ist eine Zeile, und ``beantworte_post`` prueft Pfad, Token und Nonce fuer
#: alle gleich.
_POSTWEGE = {
    "senden": _senden,
    "knopf": _knopf,
    "audio": _audio,
    "interview": _interview,
    "phase": _phase,
    "kalibrierung": _kalibrierung,
}


def _platzhalter_fuer(phase, fragen_aktuell) -> str:
    """Der Platzhalter-Text zum aktuellen Stand (UX-Knoepfe-Karte,
    Abschnitt 1) -- reine Funktion, keine Datenbank: ``phase`` und
    ``fragen_aktuell`` kommen schon roh aus ``web_daten.web_chatzustand``.

    Nur zwei Phasen bekommen einen eigenen Text, beide aus einem konkreten
    Anlass: Phase 2 mit offener Frage (die Schaerfung ist deterministisch,
    ``fragen.nimm_offene_frage_text``) und Phase 4 (freies Erfinden ohne
    Material, AGENTS.md "Erst erfinden, dann schaerfen"). Jede andere Lage
    bleibt beim Standard -- kein Raten, welcher Text sonst passen wuerde."""
    phase = str(phase or "").strip()
    if phase == "2" and (fragen_aktuell or "").strip():
        return T._TEXT_EINGABE_FRAGEN
    if phase == "4":
        return T._TEXT_EINGABE_SETTING
    return T._TEXT_EINGABE


def _zustand(db_pfad: str, token: str, nach: int = 0,
             seit: int | None = None) -> dict | None:
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        return web_daten.web_chatzustand(conn, token, nach, seit)
    finally:
        conn.close()


def _sende_seite(handler, db_pfad: str, token: str, praefix: str,
                 schluessel: bytes) -> None:
    from interview_theater import web

    daten = _zustand(db_pfad, token)
    if daten is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    handler._antworte(
        200,
        chat_html(daten, web.nonce(schluessel, token), token, praefix,
                  _segment_ms()),
    )


def _sende_zustand(handler, db_pfad: str, token: str, query: str,
                   schluessel: bytes) -> None:
    from interview_theater import web

    daten = _zustand(db_pfad, token, _nach(query), _zahl(query, "seit"))
    if daten is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    # Der Verlauf enthaelt HTML aus Bot-Ausgaben -- er wird HIER gefiltert,
    # nicht im Browser: ein Filter im JavaScript liegt auf der Seite, die er
    # schuetzen soll.
    for nachricht in daten["nachrichten"] + daten["geaendert"]:
        nachricht["html"] = sichere_html(nachricht["text"])
    daten["segment_ms"] = _segment_ms()
    daten["platzhalter"] = _platzhalter_fuer(
        daten.get("phase"), daten.get("fragen_aktuell")
    )
    # Die Chatseite laedt nie neu, ein Nonce gilt aber hoechstens zwei
    # Stunden (``web.NONCE_FENSTER``): der Poll bringt den laufenden mit, und
    # das JS setzt ihn ins Feld (Review-Befund 2). Kein neues Geheimnis nach
    # aussen -- dieselbe Antwort geht nur an dieselbe Seite, und eine fremde
    # Seite kann sie ohne CORS-Freigabe nicht lesen.
    daten["nonce"] = web.nonce(schluessel, token)
    handler._antworte(
        200, json.dumps(daten, ensure_ascii=False),
        "application/json; charset=utf-8",
    )


def _sende_datei(handler, db_pfad: str, token: str, roh_id: str) -> None:
    from interview_theater import web

    if not roh_id.isdigit():
        handler._antworte(404, web.nicht_gefunden_html())
        return
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        chat_id = web_daten.web_chat_id_nach_token(conn, token)
        datei = (
            web_daten.web_ausgangsdatei(conn, chat_id, int(roh_id))
            if chat_id is not None else None
        )
    finally:
        conn.close()
    if datei is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    try:
        inhalt = Path(datei["pfad"]).read_text(encoding="utf-8")
    except OSError:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    handler._antworte(
        200, inhalt, "text/markdown; charset=utf-8",
        dateiname=datei["dateiname"],
    )


def _nach(query: str) -> int:
    """``?nach=<id>`` -- alles, was keine Zahl ist, gilt als 0. Ein
    Tippfehler in der Adresszeile soll keine 500 geben (wie
    ``web.fassungswahl``)."""
    return _zahl(query, "nach") or 0


def _zahl(query: str, name: str) -> int | None:
    """Ein Zahlenparameter aus der Query, oder None. Nur ASCII-Ziffern und
    hoechstens 18 Stellen (dieselbe Vorsicht wie bei ``dauer`` in
    ``_audio``)."""
    try:
        werte = urllib.parse.parse_qs(query or "")
    except ValueError:
        return None
    roh = (werte.get(name) or [""])[0]
    if roh.isascii() and roh.isdigit() and len(roh) <= 18:
        return int(roh)
    return None


def _segment_ms() -> int:
    """Die Segmentlaenge fuer den Browser. Aus der Umgebung, weil der
    Webserver keine ``Einstellungen`` laedt (er braucht weder LLM- noch
    STT-Variablen) -- derselbe Name wie dort
    (``einstellungen.VORGABE_SEGMENT_MS``)."""
    roh = (os.environ.get("IT_WEB_SEGMENT_MS") or "").strip()
    return int(roh) if roh.isdigit() and int(roh) > 0 else 45_000


def _umgebungszahl(name: str, vorgabe: float, *, ganzzahl: bool) -> float:
    """Eine einzelne VAD-Zahl aus der Umgebung, mit stillem Ruckfall auf die
    Vorgabe bei leerem/ungueltigem/nicht-positivem Wert -- derselbe
    Nachsichtsgrundsatz wie bei ``_segment_ms``."""
    roh = (os.environ.get(name) or "").strip()
    if not roh:
        return vorgabe
    try:
        wert = float(roh)
    except ValueError:
        return vorgabe
    if wert <= 0:
        return vorgabe
    return int(wert) if ganzzahl else wert


def _vad_werte() -> dict:
    """Die fuenf Zahlen fuer den Pausen-Schnitt (VAD), einzeln ueberschreibbar.

    Herkunft (Betreiber-Entscheidung 02.10.2026, CoThinker-Projekt):
    ``pause_ms``/``max_ms`` aus ``gateway/consumer.py --pause 2.5
    --max-block 90``, ``min_speech_ms`` aus ``stt_server/args.py
    --vad_min_speech_ms 500`` (Infomaniak-Pfad dort -- das ist auch unser
    STT-Anbieter), ``rms`` aus ``settings.BUILT_IN_DEFAULTS
    vad_energy_threshold 0.01`` (RMS reeller Zeitbereichs-Samples, Skala
    0..1). ``floor_faktor`` ist NICHT aus CoThinker gemessen -- gesetzt,
    nicht gemessen, als Schutz gegen laute Workshop-Raeume (Browser-Mikros
    unterscheiden sich von CoThinkers Aufbau)."""
    return {
        "pause_ms": _umgebungszahl("IT_WEB_VAD_PAUSE_MS", 2500, ganzzahl=True),
        "max_ms": _umgebungszahl("IT_WEB_VAD_MAX_MS", 90_000, ganzzahl=True),
        "min_speech_ms": _umgebungszahl(
            "IT_WEB_VAD_MIN_SPEECH_MS", 500, ganzzahl=True),
        "rms": _umgebungszahl("IT_WEB_VAD_RMS", 0.01, ganzzahl=False),
        "floor_faktor": _umgebungszahl(
            "IT_WEB_VAD_FLOOR_FACTOR", 2.5, ganzzahl=False),
        # Task 2 (Kanban-Karte Mithoeren SICHER/Kalibrierung, 03.10.2026):
        # der Not-Aus fuer den Workshop -- "0" schaltet die gemessene
        # Kalibrierung ganz aus, jeder andere Wert (auch das Fehlen der
        # Variable) laesst sie an. Bewusst NICHT ueber _umgebungszahl (die
        # faellt auf eine Zahl > 0 zurueck, nicht auf einen Schalter).
        "kalibrierung": (os.environ.get("IT_WEB_VAD_KALIBRIERUNG") or "1").strip() != "0",
    }
