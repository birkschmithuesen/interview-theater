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

from interview_theater import db, repo, stt, web_daten, web_grenze, web_kanal

log = logging.getLogger(__name__)

#: Der Unterpfad unter ``/g/<token>/``. Steht wortgleich in
#: ``scripts/web_gruppe.CHAT_PFAD`` (Test).
CHAT_PFAD = "chat"

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
#: Gerechnet, nicht geraten: Opus bei 32 kbit/s ergibt fuer 45 s rund
#: 180 KiB, Safaris mp4/AAC bei 64 kbit/s rund 360 KiB. 8 MiB sind gut
#: zwanzigfache Luft fuer einen Browser, der eine hohe Bitrate waehlt -- und
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
_TEXT_EINGABE = "Schreiben …"
_TEXT_SENDEN = "Senden"
_TEXT_TIPPT = "schreibt …"
_TEXT_SPRACHE = "Sprachnachricht ({dauer})"
_TEXT_DATEI = "Datei: {name}"
_TEXT_ZUR_GRUPPENSEITE = "Zur Gruppenseite"
_TEXT_INTERVIEW_AN = "🎙 Interview aufnehmen"
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
_TEXT_PTT = "Halten und sprechen"
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
body { background: #fbfaf8; color: #17181b; padding: .6rem .7rem 9rem;
       max-width: 44rem; margin: 0 auto; }
.verlauf { display: flex; flex-direction: column; gap: .55rem; }
.blase { padding: .55rem .7rem; border-radius: .8rem; max-width: 88%;
         font-size: 1.02rem; overflow-wrap: anywhere; }
.blase.bot { background: #fff; border: 1px solid #e0ddd6; align-self: flex-start;
             border-bottom-left-radius: .2rem; }
.blase.gruppe { background: #1f6f5c; color: #fff; align-self: flex-end;
                border-bottom-right-radius: .2rem; }
.blase.sprache { font-style: italic; opacity: .85; }
.leiste { display: flex; flex-direction: column; gap: .35rem; margin: .1rem 0 .3rem;
          align-self: flex-start; width: 88%; }
.leiste button { font: inherit; text-align: left; padding: .65rem .8rem;
                 border-radius: .7rem; border: 1px solid #1f6f5c;
                 background: #fff; color: #17181b; min-height: 2.9rem; }
.leiste button:disabled { opacity: .45; }
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
#ptt[data-haelt="1"][data-weg="1"] { background: #6b6b6b; }
.fehler { font-size: .9rem; color: #a8201a; text-align: center; }
.fehler[hidden] { display: none; }
.angehalten { display: flex; flex-direction: column; gap: .35rem; font-size: .92rem;
              border: 1px solid #a8201a; border-radius: .7rem; padding: .5rem .6rem; }
.angehalten[hidden], .angehalten button[hidden] { display: none; }
.angehalten button { font: inherit; min-height: 2.9rem; border-radius: .7rem;
                     border: 1px solid #1f6f5c; background: #fff; color: #17181b; }
.pegel { height: .45rem; border-radius: .3rem; background: #e0ddd6; overflow: hidden; }
.pegel span { display: block; height: 100%; width: 0; background: #a8201a; }
.uhr { font-variant-numeric: tabular-nums; font-size: 1.3rem; text-align: center; }
.warteschlange { font-size: .82rem; opacity: .7; text-align: center; }
@media (prefers-color-scheme: dark) {
  body { background: #14161a; color: #e7e9ec; }
  .blase.bot { background: #1d2026; border-color: #2c313a; }
  .fuss { background: #14161a; border-color: #2c313a; }
  .zeile input { background: #1d2026; color: #e7e9ec; border-color: #2c313a; }
  .leiste button { background: #1d2026; color: #e7e9ec; }
  .interview-aktionen button { background: #1d2026; color: #e7e9ec; }
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
#: Segment (45 s, also unter ``aufnahme.HINWEIS_AB_S``) ein
#: Gespraechsbeitrag -- Gespraechszug, Erkenner und Journal ueber
#: Interviewmaterial. Deshalb wird nichts still nachgeschickt, die Gruppe
#: entscheidet.
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

#: Die Texte, die das JavaScript selbst setzt. Sie stehen als Konstanten in
#: diesem Modul (dieselben, die der Server fuer seine Seite benutzt) und
#: kommen als EIN JSON-Objekt ins Skript -- kein UI-Satz als Literal im JS.
_JS_TEXTE = {
    "tippt": _TEXT_TIPPT,
    "sprache": _TEXT_SPRACHE,
    "datei": _TEXT_DATEI,
    "interview_an": _TEXT_INTERVIEW_AN,
    "interview_aus": _TEXT_INTERVIEW_AUS,
    "interview_pause": _TEXT_INTERVIEW_PAUSE,
    "interview_weiter": _TEXT_INTERVIEW_WEITER,
    "interview_laeuft": _TEXT_INTERVIEW_LAEUFT,
    "interview_pausiert": _TEXT_INTERVIEW_PAUSIERT,
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
  var UPLOAD_WARTEN_MS = __UPLOAD_WARTEN_MS__;
  var TEXT = __TEXTE__;

  var verlauf = document.getElementById('verlauf');
  var fuss = document.getElementById('fuss');
  if (!verlauf || !fuss) { return; }
  var eingabe = document.getElementById('eingabe');
  var uhrFeld = document.getElementById('uhr');
  var pegelFeld = document.getElementById('pegel');
  var pegelBalken = pegelFeld ? pegelFeld.querySelector('span') : null;
  var warteFeld = document.getElementById('warteschlange');
  var fehlerFeld = document.getElementById('fehler');
  var tipptFeld = document.getElementById('tippt');
  var interviewKnopf = document.getElementById('interview');
  var interviewAktionenFeld = document.getElementById('interview-aktionen');
  var interviewPauseKnopf = document.getElementById('interview-pause');
  var interviewBeendenKnopf = document.getElementById('interview-beenden');
  var pttKnopf = document.getElementById('ptt');
  var angehaltenFeld = document.getElementById('angehalten');
  var angehaltenText = document.getElementById('angehalten-text');
  var nachreichenKnopf = document.getElementById('nachreichen');
  var verwerfenKnopf = document.getElementById('verwerfen');
  var SEGMENT_MS = parseInt(fuss.dataset.segmentMs, 10) || 45000;

  // Alle Wege absolut zum Verzeichnis der Gruppe, aus dem Pfad, den der
  // Browser sieht (mit oder ohne IT_WEB_PREFIX). Relative Wege zeigten unter
  // einer Adresse mit Schraegstrich am Ende ins Leere (Review-Befund 12).
  var BASIS = location.pathname.replace(/\\/+$/, '').replace(/\\/chat$/, '') + '/';
  function weg(pfad) { return BASIS + pfad; }

  var zustand = {
    letzte: parseInt(verlauf.dataset.letzte, 10) || 0,
    aenderung: parseInt(verlauf.dataset.aenderung, 10) || 0,
    servermodus: fuss.dataset.interview === '1',
    aufnahme: null,     // die laufende Interview-Aufnahme dieses Telefons
    wechsel: null,      // {ziel, gesendet}: ein Moduswechsel, den der Poll noch nicht zeigt
    warteschlange: [],  // Befehle und Segmente, der Reihe nach
    laeuft: false,      // ist der erste Auftrag gerade unterwegs?
    netzFehler: 0,      // Fehlversuche in Folge (Backoff)
    nachholTakt: null,
    uhrTakt: null,
    fehlerTakt: null,
    ptt: null,          // der laufende PTT-Druck, je Druck ein eigenes Objekt
    angehalten: []      // Aufnahmen, deren Modus ohne dieses Telefon endete (Re-Review H)
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

  function inhaltVon(n) {
    // Der Server hat schon gefiltert (sichere_html) -- ein Filter im Browser
    // laege auf der Seite, die er schuetzen soll.
    if (n.typ === 'sprache') {
      return escape(TEXT.sprache.replace('{dauer}', minuten(n.dauer || 0)));
    }
    if (n.typ === 'datei') {
      var link = '<a href="' + weg('chat/datei/' + n.id) + '">' +
                 escape(TEXT.datei.replace('{name}', n.dateiname || 'datei')) +
                 '</a>';
      return n.html ? n.html + '<br>' + link : link;
    }
    return n.html || '';
  }

  function klasseVon(n) {
    return (n.typ === 'sprache' || n.typ === 'datei') ? n.typ : 'text';
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

  function blaseZu(id) {
    return verlauf.querySelector('.blase[data-id="' + id + '"]');
  }

  function leisteZu(id) {
    return verlauf.querySelector('.leiste[data-message="' + id + '"]');
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
    if (leiste) { verlauf.appendChild(leiste); }
  }

  // Review-Befund 10: aendere_text, entferne_knoepfe und loesche_nachrichten
  // treffen Zeilen, die schon dastehen -- die Arbeitszeile wechselt, eine
  // ueberholte Leiste verschwindet, eine geloeschte Nachricht auch.
  function ersetze(n) {
    var huelle = blaseZu(n.id);
    var alte = leisteZu(n.id);
    if (n.geloescht) { entferne(huelle); entferne(alte); return; }
    if (!huelle) { return; }
    huelle.innerHTML = inhaltVon(n);
    var neue = baueLeiste(n);
    if (alte && neue) { alte.parentNode.replaceChild(neue, alte); }
    else if (alte) { entferne(alte); }
    else if (neue) { huelle.parentNode.insertBefore(neue, huelle.nextSibling); }
  }

  function nachUnten() {
    window.scrollTo(0, document.body.scrollHeight);
  }

  function nimmZustand(daten) {
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
    (daten.geaendert || []).forEach(ersetze);
    if (typeof daten.aenderung === 'number') {
      zustand.aenderung = daten.aenderung;
      verlauf.dataset.aenderung = daten.aenderung;
    }
    if (neu.length) { nachUnten(); }
    if (tipptFeld) { tipptFeld.textContent = daten.tippt ? TEXT.tippt : ''; }
    zustand.servermodus = !!daten.interviewmodus;
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
    zeigeAntworten(daten.antworten || {});
    arbeiteAb();   // ein wartendes Segment darf jetzt vielleicht raus
  }

  function zeigeAntworten(antworten) {
    Object.keys(antworten).forEach(function (id) {
      if (document.querySelector('.quittung[data-druck="' + id + '"]')) { return; }
      var zeile = document.createElement('div');
      zeile.className = 'quittung';
      zeile.dataset.druck = id;
      zeile.textContent = antworten[id];
      verlauf.appendChild(zeile);
    });
  }

  // Immer nur ein Poll unterwegs: zwei Antworten in vertauschter Reihenfolge
  // setzten sonst einen aelteren Stand ueber einen neueren.
  var holt = null;
  var nochmalHolen = false;
  function hole() {
    if (holt) { nochmalHolen = true; return holt; }
    holt = fetch(weg('chat/zustand?nach=' + zustand.letzte +
                     '&seit=' + zustand.aenderung), { cache: 'no-store' })
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
    return fetch(weg('chat/audio?dauer=' + auftrag.dauer), {
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
    function zurueck() { if (!eingabe.value) { eingabe.value = text; } }
    postJson('chat/senden', { text: text }).then(function (r) {
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
    postJson('chat/knopf', {
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
      ? postJson('chat/interview', { an: auftrag.an })
      : postAudio(auftrag);
    anfrage.then(function (r) {
      if (r.ok) {
        zustand.netzFehler = 0;
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
      if (teile.length && !sitzung.verworfen) {   // leere Stuecke nie
        auftrag = {
          art: 'audio', sitzung: sitzung,
          blob: new Blob(teile, { type: teile[0].type || r.mimeType || 'audio/webm' }),
          dauer: Math.max(1, Math.round((Date.now() - von) / 1000))
        };
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
      var werte = new Uint8Array(messer.frequencyBinCount);
      sitzung.pegelTakt = setInterval(function () {
        messer.getByteFrequencyData(werte);
        var summe = 0;
        for (var i = 0; i < werte.length; i++) { summe += werte[i]; }
        pegelBalken.style.width =
          Math.min(100, (summe / werte.length) * 2.2) + '%';
      }, 120);
    } catch (e) { /* ohne Pegel geht es auch */ }
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
    if (pegelBalken) { pegelBalken.style.width = '0'; }
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
    interviewKnopf.disabled = !!(zustand.wechsel && !zustand.wechsel.ziel);
    // Der grosse Knopf ist waehrend Laeuft/Pause nur noch eine Anzeige --
    // Pause/Weiter und Beenden stehen in der eigenen Leiste darunter.
    if (interviewAktionenFeld) { interviewAktionenFeld.hidden = !an; }
    if (interviewPauseKnopf) {
      interviewPauseKnopf.textContent = pausiert ? TEXT.interview_weiter : TEXT.interview_pause;
    }
    // Waehrend eine Interview-Aufnahme laeuft ODER pausiert ist, ist PTT
    // ausgeblendet (Birk, Punkt 2): zwei Mikrofone gleichzeitig sind keine
    // Bedienung, und eine Pause ist weiterhin "Modus an".
    if (pttKnopf) { pttKnopf.hidden = an || !!zustand.wechsel; }
  }

  function verwirfPtt() {
    var druck = zustand.ptt;
    if (!druck) { return; }
    zustand.ptt = null;
    druck.gehalten = false;
    druck.abgebrochen = true;
    if (pttKnopf) {
      pttKnopf.dataset.haelt = '0';
      try { pttKnopf.releasePointerCapture(druck.pointerId); } catch (e) { /* egal */ }
    }
    if (druck.recorder && druck.recorder.state !== 'inactive') {
      druck.recorder.stop();   // sein onstop gibt das Mikrofon frei
    }
  }

  function starteInterview() {
    // Review-Befund 4: nie zwei Recorder, nie ein Start mitten im Wechsel.
    if (zustand.aufnahme || zustand.wechsel) { return; }
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
      pausiert: false, erfassteMs: 0, legStart: null, fortsetzend: false
    };
    var wechsel = { ziel: true, gesendet: false };
    zustand.aufnahme = sitzung;
    zustand.wechsel = wechsel;
    zeigeModus();
    holeStrom().then(function (strom) {
      sitzung.strom = strom;
      if (sitzung.beendet) { gibFrei(sitzung); return; }   // vorher gestoppt
      // Die Aufnahme laeuft SOFORT -- sonst verliert man die ersten Worte.
      // Die Segmente warten in der Schlange hinter /interview (bereit()).
      sitzung.legStart = Date.now();
      sitzung.recorder = neuesSegment(sitzung);
      sitzung.gestartet = true;
      reiheEin({ art: 'befehl', an: true, sitzung: sitzung, wechsel: wechsel });
      uhrAn(sitzung);
      pegelAn(sitzung);
      sitzung.segmentTakt = setInterval(function () {
        if (!sitzung.recorder) { return; }
        var alt = sitzung.recorder;
        alt.stop();                      // liefert sein Segment im onstop
        sitzung.recorder = neuesSegment(sitzung);
      }, SEGMENT_MS);
    }).catch(function () {
      // Review-Befund 8: ein halb gestarteter Recorder wird gestoppt und das
      // Mikrofon freigegeben.
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
    sitzung.erfassteMs += Date.now() - sitzung.legStart;
    sitzung.legStart = null;
    sitzung.pausiert = true;
    if (sitzung.segmentTakt) { clearInterval(sitzung.segmentTakt); sitzung.segmentTakt = null; }
    var alt = sitzung.recorder;
    sitzung.recorder = null;
    // Wie starteInterview()/brichAb() bei einem Fehler: stop(), dann sofort
    // das Mikrofon los -- sein onstop hat die Daten bis hierhin schon im
    // ondataavailable gesammelt und reiht das Stueck ganz normal ein.
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
        fortsetzend: false
      };
      zustand.aufnahme = sitzung;   // synchron, wie starteInterview()
    }
    // Re-Review F, auch beim Wiederaufnehmen: ein gehaltener PTT-Druck wird
    // verworfen, sonst liefen zwei Recorder.
    if (zustand.ptt) { verwirfPtt(); }
    sitzung.fortsetzend = true;   // Sperrklinke: kein zweiter Recorder bei Doppeldruck
    zeigeModus();
    holeStrom().then(function (strom) {
      sitzung.fortsetzend = false;
      if (sitzung.beendet || sitzung.verworfen) {
        strom.getTracks().forEach(function (t) { t.stop(); });
        return;
      }
      sitzung.strom = strom;
      sitzung.legStart = Date.now();
      sitzung.pausiert = false;
      sitzung.gestartet = true;
      sitzung.recorder = neuesSegment(sitzung);
      sitzung.segmentTakt = setInterval(function () {
        if (!sitzung.recorder) { return; }
        var alt = sitzung.recorder;
        alt.stop();                      // liefert sein Segment im onstop
        sitzung.recorder = neuesSegment(sitzung);
      }, SEGMENT_MS);
      uhrAn(sitzung);
      pegelAn(sitzung);
      zeigeModus();
    }).catch(function () {
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

  // -- Push-to-Talk --------------------------------------------------------
  //
  // Halten = sprechen, loslassen = senden, Klasse 'kurz' (der Modus wird
  // NICHT geschaltet). Pointer Events mit setPointerCapture; pointercancel,
  // ein verlorener Zeiger oder ein Loslassen ausserhalb des Knopfs sendet
  // NICHTS, ebenso ein Druck unter PTT_MIN_MS.

  if (pttKnopf) {
    var ausserhalb = function (ev) {
      var k = pttKnopf.getBoundingClientRect();
      return ev.clientX < k.left || ev.clientX > k.right ||
             ev.clientY < k.top || ev.clientY > k.bottom;
    };

    pttKnopf.addEventListener('pointerdown', function (ev) {
      if (modusAn() || zustand.wechsel || zustand.ptt) { return; }
      if (ev.button !== undefined && ev.button > 0) { return; }
      ev.preventDefault();
      try { pttKnopf.setPointerCapture(ev.pointerId); } catch (e) { /* egal */ }
      // Review-Befund 6: jeder Druck traegt seinen eigenen Zustand -- ein
      // spaeterer Druck ueberschreibt nichts, was ein frueherer noch liest.
      var druck = {
        pointerId: ev.pointerId, von: Date.now(), dauerMs: 0,
        gehalten: true, abgebrochen: false, recorder: null, strom: null,
        teile: []
      };
      zustand.ptt = druck;
      pttKnopf.dataset.haelt = '1';
      pttKnopf.dataset.weg = '0';
      holeStrom().then(function (strom) {
        druck.strom = strom;
        // Review-Befund 5: losgelassen, bevor das Mikrofon da war -- dann
        // gar nicht erst aufnehmen, und das Mikrofon sofort wieder zu.
        if (!druck.gehalten) { gibFrei(druck); return; }
        var r = new MediaRecorder(strom);
        druck.recorder = r;
        r.ondataavailable = function (e) {
          if (e.data && e.data.size) { druck.teile.push(e.data); }
        };
        r.onstop = function () {
          gibFrei(druck);
          if (druck.abgebrochen || druck.dauerMs < PTT_MIN_MS ||
              !druck.teile.length) { return; }
          reiheEin({
            art: 'audio', sitzung: null,
            blob: new Blob(druck.teile,
                           { type: druck.teile[0].type || r.mimeType || 'audio/webm' }),
            dauer: Math.max(1, Math.round(druck.dauerMs / 1000))
          });
        };
        r.start();
      }).catch(function () {
        druck.abgebrochen = true;
        gibFrei(druck);
        if (zustand.ptt === druck) {
          zustand.ptt = null;
          pttKnopf.dataset.haelt = '0';
        }
        meldeFehler(TEXT.fehler_mikro);
      });
    });

    var lasseLos = function (ev, abbrechen) {
      var druck = zustand.ptt;
      if (!druck || ev.pointerId !== druck.pointerId) { return; }
      zustand.ptt = null;
      pttKnopf.dataset.haelt = '0';
      pttKnopf.dataset.weg = '0';
      druck.gehalten = false;
      // Die Haltezeit, nicht die Zeit bis das Mikrofon da war.
      druck.dauerMs = Date.now() - druck.von;
      // Review-Befund 7: mit setPointerCapture kommt auch ein Loslassen
      // NEBEN dem Knopf hier an -- weggezogen heisst abgebrochen.
      if (abbrechen || ausserhalb(ev)) { druck.abgebrochen = true; }
      try { pttKnopf.releasePointerCapture(ev.pointerId); } catch (e) { /* egal */ }
      if (druck.recorder && druck.recorder.state !== 'inactive') {
        druck.recorder.stop();
      }
    };

    pttKnopf.addEventListener('pointerup', function (ev) { lasseLos(ev, false); });
    pttKnopf.addEventListener('pointercancel', function (ev) { lasseLos(ev, true); });
    // Ein Systemdialog oder Kontextmenue kann den Zeiger entfuehren; nach
    // einem normalen pointerup ist zustand.ptt schon leer und das hier wirkt
    // nicht mehr.
    pttKnopf.addEventListener('lostpointercapture', function (ev) { lasseLos(ev, true); });
    pttKnopf.addEventListener('pointermove', function (ev) {
      var druck = zustand.ptt;
      if (!druck || ev.pointerId !== druck.pointerId) { return; }
      pttKnopf.dataset.weg = ausserhalb(ev) ? '1' : '0';
    });
    pttKnopf.addEventListener('contextmenu', function (ev) { ev.preventDefault(); });
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
  nachUnten();
  hole();
})();
"""


def _js() -> str:
    """``_CHAT_JS`` mit den Zahlen und Texten aus den Modulkonstanten.

    Platzhalter und keine f-String-Interpolation: das Skript ist voll mit
    geschweiften Klammern. Die Texte gehen als JSON hinein; ``</`` wird
    maskiert, damit kein Text das ``<script>`` beenden kann."""
    texte = json.dumps(_JS_TEXTE, ensure_ascii=True).replace("</", "<\\/")
    return (
        _CHAT_JS
        .replace("__POLL_MS__", str(POLL_MS))
        .replace("__POLL_MS_HINTERGRUND__", str(POLL_MS_HINTERGRUND))
        .replace("__PTT_MIN_MS__", str(PTT_MIN_MS))
        .replace("__UPLOAD_WARTEN_MS__", json.dumps(list(UPLOAD_WARTEN_MS)))
        .replace("__TEXTE__", texte)
    )


def _blase_html(n: dict) -> str:
    """Eine Nachricht als Blase, gegebenenfalls mit ihrer Leiste darunter."""
    if n["typ"] == "sprache":
        minuten, sekunden = divmod(int(n["dauer"] or 0), 60)
        inhalt = html.escape(_TEXT_SPRACHE.format(dauer=f"{minuten}:{sekunden:02d}"))
        klasse = "sprache"
    elif n["typ"] == "datei":
        inhalt = (
            f'<a href="{CHAT_PFAD}/datei/{n["id"]}">'
            + html.escape(_TEXT_DATEI.format(name=n["dateiname"] or "datei"))
            + "</a>"
        )
        if n["text"]:
            inhalt = sichere_html(n["text"]) + "<br>" + inhalt
        klasse = "datei"
    else:
        inhalt = sichere_html(n["text"])
        klasse = "text"

    teile = [
        f'<div class="blase {n["von"]} {klasse}" data-id="{n["id"]}">{inhalt}</div>'
    ]
    if n["knoepfe"]:
        knoepfe = "".join(
            f'<button type="button" data-message="{n["id"]}" '
            f'data-daten="{html.escape(daten, quote=True)}">'
            f"{html.escape(beschriftung)}</button>"
            for beschriftung, daten in n["knoepfe"]
        )
        teile.append(f'<div class="leiste" data-message="{n["id"]}">{knoepfe}</div>')
    return "\n".join(teile)


def chat_html(daten: dict, nonce_wert: str, token: str, praefix: str,
              segment_ms: int) -> str:
    """Die Chatansicht.

    Sie haengt sich in ``web._seite`` ein (dieselbe Klammer, dasselbe
    Grund-CSS), aber **ohne** dessen sanftes Nachladen: das tauscht den
    ``<body>`` aus, und mitten in einer laufenden Aufnahme wuerde das
    Recorder, Timer und Warteschlange mitreissen. Nachgeladen wird hier
    gezielt, per Poll (``_CHAT_JS``), und nur der Verlauf."""
    from interview_theater import web   # spaeter Import: web importiert web_chat

    modus = bool(daten["interviewmodus"])
    blasen = "\n".join(_blase_html(n) for n in daten["nachrichten"])
    if not blasen:
        blasen = f'<p class="leer">{html.escape(_TEXT_LEER)}</p>'

    koerper = (
        f"<h1>{html.escape(daten.get('titel') or _TEXT_TITEL)}</h1>\n"
        f'<p><a href="{html.escape(token)}">'
        f"{html.escape(_TEXT_ZUR_GRUPPENSEITE)}</a></p>\n"
        f'<noscript><p class="leer">{html.escape(_TEXT_OHNE_JS)}</p></noscript>\n'
        f'<div class="verlauf" id="verlauf" data-letzte="{daten["letzte"]}" '
        f'data-aenderung="{int(daten.get("aenderung") or 0)}">\n'
        f"{blasen}\n</div>\n"
        f'<div class="tippt" id="tippt"></div>\n'
        f'<input type="hidden" id="nonce" value="{html.escape(nonce_wert, quote=True)}">\n'
        f'<div class="fuss" id="fuss" data-segment-ms="{int(segment_ms)}"\n'
        f'     data-interview="{1 if modus else 0}">\n'
        f'  <div class="uhr" id="uhr" hidden></div>\n'
        f'  <div class="pegel" id="pegel" hidden><span></span></div>\n'
        f'  <div class="warteschlange" id="warteschlange"></div>\n'
        f'  <div class="fehler" id="fehler" role="alert" hidden></div>\n'
        f'  <div class="angehalten" id="angehalten" role="alert" hidden>\n'
        f'    <p id="angehalten-text"></p>\n'
        f'    <button type="button" id="nachreichen">'
        f'{html.escape(_TEXT_REST_NACHREICHEN)}</button>\n'
        f'    <button type="button" id="verwerfen">'
        f'{html.escape(_TEXT_REST_VERWERFEN)}</button>\n'
        f'  </div>\n'
        f'  <button type="button" id="interview" data-laeuft="{1 if modus else 0}" '
        f'data-pausiert="{1 if modus else 0}">'
        f'{html.escape(_TEXT_INTERVIEW_AUS if modus else _TEXT_INTERVIEW_AN)}'
        f'</button>\n'
        f'  <div class="interview-aktionen" id="interview-aktionen"'
        f'{"" if modus else " hidden"}>\n'
        f'    <button type="button" id="interview-pause">'
        f'{html.escape(_TEXT_INTERVIEW_WEITER if modus else _TEXT_INTERVIEW_PAUSE)}'
        f'</button>\n'
        f'    <button type="button" id="interview-beenden">'
        f'{html.escape(_TEXT_INTERVIEW_ENDEN)}</button>\n'
        f'  </div>\n'
        f'  <div class="zeile">\n'
        f'    <input type="text" id="eingabe" autocomplete="off" '
        f'placeholder="{html.escape(_TEXT_EINGABE, quote=True)}">\n'
        f'    <button type="button" id="ptt"{" hidden" if modus else ""} title="'
        f'{html.escape(_TEXT_PTT, quote=True)}">🎤</button>\n'
        f'    <button type="button" id="senden">'
        f'{html.escape(_TEXT_SENDEN)}</button>\n'
        f"  </div>\n"
        f"</div>\n"
    )
    return web._seite(
        daten.get("titel") or _TEXT_TITEL, _CSS_CHAT, koerper,
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


#: Die Tabelle der POST-Wege. Eine Tabelle statt einer if-Kette: ein neuer Weg
#: ist eine Zeile, und ``beantworte_post`` prueft Pfad, Token und Nonce fuer
#: alle gleich.
_POSTWEGE = {
    "senden": _senden,
    "knopf": _knopf,
    "audio": _audio,
    "interview": _interview,
}


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
