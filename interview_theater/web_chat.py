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
import os
import re
import sqlite3
import urllib.parse
from contextlib import contextmanager
from pathlib import Path

from interview_theater import db, repo, web_daten, web_kanal

#: Der Unterpfad unter ``/g/<token>/``. Steht wortgleich in
#: ``scripts/web_gruppe.CHAT_PFAD`` (Test).
CHAT_PFAD = "chat"

#: Wie lang eine Nachricht aus dem Browser hoechstens ist. Dieselbe Zahl wie
#: ``telegram.NACHRICHT_GRENZE``: eine Gruppe, die im Browser arbeitet, soll
#: nicht mehr schreiben koennen, als der Telegram-Weg tragen wuerde -- sonst
#: laesst sich ein Workshop nicht von einem Kanal in den anderen retten.
MAX_TEXT_ZEICHEN = 4000

#: Was der Browser liefern darf, und mit welcher Endung es abgelegt wird.
#:
#: **Content-Type -> ENDUNG und nicht Content-Type -> ja/nein**, und das ist
#: Falle 3: ``stt.mime_typ()`` leitet den MIME-Typ, den Whisper sieht, aus der
#: Dateiendung ab. Ein WebM als ``.ogg`` abgelegt wird von Infomaniak mit
#: einer ``batch_id`` quittiert -- kein HTTP-Fehler -- und bleibt danach
#: dauerhaft auf 'pending': 89,7 s statt 2,0 s, im Betrieb nur als "haengt"
#: sichtbar.
#:
#: Chrome und Firefox liefern ``audio/webm;codecs=opus``, Safari
#: ``audio/mp4``. ``audio/ogg`` und ``audio/mpeg`` stehen daneben, weil ein
#: Browser sie waehlen darf und beide bei Whisper unstrittig sind.
MIME_ERLAUBT = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
}

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
_TEXT_INTERVIEW_AN = "Interview aufnehmen"
_TEXT_INTERVIEW_AUS = "Aufnahme beenden"
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
#ptt[hidden], #interview[hidden] { display: none; }
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

#: Wie oft ein fehlgeschlagener Upload wiederholt wird, und mit welchen
#: Wartezeiten (Sekunden). Dieselbe Haltung wie ``stt.WARTEZEITEN``: ein
#: Netzaussetzer im Probenraum darf ein Segment nicht kosten.
UPLOAD_VERSUCHE = 4
UPLOAD_WARTEN_MS = (1000, 3000, 8000)


#: Das Chat-JavaScript. Vanilla, kein Build, kein Framework -- wie die
#: bestehende Seite (``_BEARBEITEN_JS``). Faellt es aus, bleibt der Verlauf
#: lesbar (serverseitig gerendert); nur Senden und Aufnehmen gehen nicht.
#:
#: Die Zahlen kommen als Platzhalter herein, damit sie an genau einer Stelle
#: stehen: in den Python-Konstanten darueber.
_CHAT_JS = """
(function () {
  var POLL_MS = __POLL_MS__;
  var POLL_MS_HINTERGRUND = __POLL_MS_HINTERGRUND__;
  var PTT_MIN_MS = __PTT_MIN_MS__;
  var UPLOAD_VERSUCHE = __UPLOAD_VERSUCHE__;
  var UPLOAD_WARTEN_MS = __UPLOAD_WARTEN_MS__;

  var verlauf = document.getElementById('verlauf');
  var fuss = document.getElementById('fuss');
  if (!verlauf || !fuss) { return; }
  var eingabe = document.getElementById('eingabe');
  var uhrFeld = document.getElementById('uhr');
  var pegelFeld = document.getElementById('pegel');
  var pegelBalken = pegelFeld ? pegelFeld.querySelector('span') : null;
  var warteFeld = document.getElementById('warteschlange');
  var tipptFeld = document.getElementById('tippt');
  var interviewKnopf = document.getElementById('interview');
  var pttKnopf = document.getElementById('ptt');
  var SEGMENT_MS = parseInt(fuss.dataset.segmentMs, 10) || 45000;

  var zustand = {
    letzte: parseInt(verlauf.dataset.letzte, 10) || 0,
    interview: fuss.dataset.interview === '1',
    warteschlange: [],
    laeuft: false,        // sendet gerade ein Upload?
    recorder: null,
    strom: null,
    beginn: 0,
    uhrTakt: null,
    pegelTakt: null,
    segmentTakt: null,
    pttVon: 0,
    pttAbgebrochen: false
  };

  function nonce() {
    var feld = document.getElementById('nonce');
    return feld ? feld.value : '';
  }

  // -- Verlauf -------------------------------------------------------------

  function escape(text) {
    var hilf = document.createElement('div');
    hilf.textContent = text == null ? '' : String(text);
    return hilf.innerHTML;
  }

  function blase(n) {
    var huelle = document.createElement('div');
    // Der Server hat schon gefiltert (sichere_html) -- ein Filter im Browser
    // laege auf der Seite, die er schuetzen soll.
    var inhalt = n.html;
    if (n.typ === 'sprache') {
      var s = n.dauer || 0;
      inhalt = escape('Sprachnachricht (' + Math.floor(s / 60) + ':' +
                      ('0' + (s % 60)).slice(-2) + ')');
    } else if (n.typ === 'datei') {
      inhalt = '<a href="chat/datei/' + n.id + '">' +
               escape(n.dateiname || 'Datei') + '</a>';
    }
    huelle.className = 'blase ' + n.von + ' ' + n.typ;
    huelle.dataset.id = n.id;
    huelle.innerHTML = inhalt;
    verlauf.appendChild(huelle);

    if (n.knoepfe && n.knoepfe.length) {
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
      verlauf.appendChild(leiste);
    }
  }

  function nachUnten() {
    window.scrollTo(0, document.body.scrollHeight);
  }

  function nimmZustand(daten) {
    (daten.nachrichten || []).forEach(blase);
    if (daten.nachrichten && daten.nachrichten.length) {
      zustand.letzte = daten.letzte;
      verlauf.dataset.letzte = daten.letzte;
      // Eine Leiste, deren Nachricht ueberholt ist, nimmt der Server weg
      // (entferne_knoepfe) -- hier wird nur ergaenzt, nie geraten.
      nachUnten();
    }
    if (tipptFeld) { tipptFeld.textContent = daten.tippt ? 'schreibt …' : ''; }
    setzeInterview(!!daten.interviewmodus);
    zeigeAntworten(daten.antworten || {});
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

  function hole() {
    return fetch('chat/zustand?nach=' + zustand.letzte, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d) { nimmZustand(d); } })
      .catch(function () { /* Netz weg: der naechste Takt versucht es wieder */ });
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

  // -- Senden --------------------------------------------------------------

  function sendeText() {
    var text = (eingabe.value || '').trim();
    if (!text) { return; }
    eingabe.value = '';
    fetch('chat/senden', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nonce: nonce(), text: text })
    }).then(function () { hole(); })
      .catch(function () { eingabe.value = text; });
  }

  document.getElementById('senden').addEventListener('click', sendeText);
  eingabe.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') { ev.preventDefault(); sendeText(); }
  });

  // -- Knoepfe -------------------------------------------------------------

  document.addEventListener('click', function (ev) {
    var knopf = ev.target.closest ? ev.target.closest('.leiste button') : null;
    if (!knopf) { return; }
    // Alle Knoepfe der Leiste aus: der zweite Druck wirkt serverseitig
    // idempotent nicht mehr, aber ein Knopf, der weiter klickbar
    // dasteht, laedt dazu ein.
    var leiste = knopf.closest('.leiste');
    if (leiste) {
      Array.prototype.forEach.call(leiste.querySelectorAll('button'),
        function (b) { b.disabled = true; });
    }
    fetch('chat/knopf', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nonce: nonce(),
        message_id: parseInt(knopf.dataset.message, 10),
        data: knopf.dataset.daten
      })
    }).then(function (r) {
      if (!r.ok && leiste) {
        Array.prototype.forEach.call(leiste.querySelectorAll('button'),
          function (b) { b.disabled = false; });
      }
      hole();
    }).catch(function () {
      if (leiste) {
        Array.prototype.forEach.call(leiste.querySelectorAll('button'),
          function (b) { b.disabled = false; });
      }
    });
  });

  // -- Upload-Warteschlange ------------------------------------------------
  //
  // Sequentiell mit Wiederholung: ein Netzaussetzer im Probenraum darf ein
  // Segment nicht kosten. Und sequentiell, damit die Segmente in der
  // Reihenfolge ankommen, in der gesprochen wurde.

  function reiheEin(auftrag) {
    zustand.warteschlange.push(auftrag);
    zeigeWarteschlange();
    arbeiteAb();
  }

  function zeigeWarteschlange() {
    if (!warteFeld) { return; }
    var offen = zustand.warteschlange.length + (zustand.laeuft ? 1 : 0);
    warteFeld.textContent = offen
      ? (offen === 1 ? 'ein Stück wird hochgeladen …'
                     : offen + ' Stücke werden hochgeladen …')
      : '';
  }

  function arbeiteAb() {
    if (zustand.laeuft || !zustand.warteschlange.length) { return; }
    var auftrag = zustand.warteschlange[0];
    // Der Wettlauf: das erste Segment darf erst raus, wenn der Bot den
    // Interviewmodus wirklich an hat. Sonst macht aufnahme.klasse_fuer
    // daraus eine kurz-Aufnahme statt eines Interview-Teils.
    if (auftrag.brauchtInterview && !zustand.interview) {
      setTimeout(arbeiteAb, 500);
      return;
    }
    zustand.laeuft = true;
    zeigeWarteschlange();
    schicke(auftrag, 0);
  }

  function schicke(auftrag, versuch) {
    fetch('chat/audio?nonce=' + encodeURIComponent(nonce()) +
          '&dauer=' + auftrag.dauer, {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': auftrag.blob.type || 'audio/webm' },
      body: auftrag.blob
    }).then(function (r) {
      if (!r.ok && r.status >= 500 && versuch + 1 < UPLOAD_VERSUCHE) {
        throw new Error('nochmal');
      }
      fertig(auftrag);
    }).catch(function () {
      if (versuch + 1 >= UPLOAD_VERSUCHE) { fertig(auftrag); return; }
      setTimeout(function () { schicke(auftrag, versuch + 1); },
                 UPLOAD_WARTEN_MS[Math.min(versuch, UPLOAD_WARTEN_MS.length - 1)]);
    });
  }

  function fertig(auftrag) {
    zustand.warteschlange.shift();
    zustand.laeuft = false;
    zeigeWarteschlange();
    if (auftrag.danach) { auftrag.danach(); }
    hole();
    arbeiteAb();
  }

  function leer() {
    return !zustand.warteschlange.length && !zustand.laeuft;
  }

  // -- Aufnahme ------------------------------------------------------------

  function strom() {
    if (zustand.strom) { return Promise.resolve(zustand.strom); }
    return navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function (s) { zustand.strom = s; return s; });
  }

  function neuerRecorder(s) {
    // Ein eigener Recorder je Segment -- KEINE Zeitscheibe
    // (start(timeslice)): deren Stuecke sind einzeln nicht dekodierbar, nur
    // das erste traegt den Container-Kopf. Whisper bekaeme ab dem zweiten
    // Segment Bytes ohne Kopf.
    var r = new MediaRecorder(s);
    var von = Date.now();
    r.ondataavailable = function (ev) {
      if (!ev.data || !ev.data.size) { return; }
      var dauer = Math.max(1, Math.round((Date.now() - von) / 1000));
      reiheEin({ blob: ev.data, dauer: dauer, brauchtInterview: true });
    };
    r.start();
    return r;
  }

  function pegelAn(s) {
    if (!pegelBalken || !window.AudioContext) { return; }
    var kontext = new AudioContext();
    var messer = kontext.createAnalyser();
    messer.fftSize = 256;
    kontext.createMediaStreamSource(s).connect(messer);
    var werte = new Uint8Array(messer.frequencyBinCount);
    zustand.pegelTakt = setInterval(function () {
      messer.getByteFrequencyData(werte);
      var summe = 0;
      for (var i = 0; i < werte.length; i++) { summe += werte[i]; }
      pegelBalken.style.width =
        Math.min(100, (summe / werte.length) * 2.2) + '%';
    }, 120);
  }

  function uhrAn() {
    zustand.beginn = Date.now();
    uhrFeld.hidden = false;
    pegelFeld.hidden = false;
    zustand.uhrTakt = setInterval(function () {
      var s = Math.floor((Date.now() - zustand.beginn) / 1000);
      uhrFeld.textContent = '● ' + Math.floor(s / 60) + ':' +
                            ('0' + (s % 60)).slice(-2);
    }, 500);
  }

  function anzeigeAus() {
    [zustand.uhrTakt, zustand.pegelTakt, zustand.segmentTakt]
      .forEach(function (t) { if (t) { clearInterval(t); } });
    zustand.uhrTakt = zustand.pegelTakt = zustand.segmentTakt = null;
    uhrFeld.hidden = true;
    pegelFeld.hidden = true;
    if (pegelBalken) { pegelBalken.style.width = '0'; }
  }

  function setzeInterview(an) {
    zustand.interview = an;
    fuss.dataset.interview = an ? '1' : '0';
    interviewKnopf.dataset.laeuft = an ? '1' : '0';
    interviewKnopf.textContent = an ? 'Aufnahme beenden' : 'Interview aufnehmen';
    // Waehrend eine Interview-Aufnahme laeuft, ist PTT ausgeblendet
    // (Birk, Punkt 2): zwei Mikrofone gleichzeitig sind keine Bedienung.
    if (pttKnopf) { pttKnopf.hidden = an; }
  }

  function starteInterview() {
    strom().then(function (s) {
      // Die Aufnahme laeuft SOFORT -- sonst verliert man die ersten Worte.
      // Der Upload wartet in der Warteschlange, bis der Modus wirklich an
      // ist (arbeiteAb).
      zustand.recorder = neuerRecorder(s);
      uhrAn();
      pegelAn(s);
      zustand.segmentTakt = setInterval(function () {
        if (!zustand.recorder) { return; }
        zustand.recorder.stop();            // liefert ondataavailable
        zustand.recorder = neuerRecorder(s);
      }, SEGMENT_MS);
      setzeInterview(true);
      return fetch('chat/interview', {
        method: 'POST', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nonce: nonce(), an: true })
      });
    }).then(hole).catch(function () {
      setzeInterview(false);
      anzeigeAus();
    });
  }

  function beendeInterview() {
    var laufend = zustand.recorder;
    zustand.recorder = null;
    anzeigeAus();
    if (laufend && laufend.state !== 'inactive') { laufend.stop(); }
    setzeInterview(false);
    // /fertig erst, wenn ALLE Uploads durch sind -- sonst verdichtet der Bot
    // ein Interview, dem das letzte Segment fehlt.
    (function warte(versuche) {
      if (!leer() && versuche > 0) {
        setTimeout(function () { warte(versuche - 1); }, 500);
        return;
      }
      fetch('chat/interview', {
        method: 'POST', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nonce: nonce(), an: false })
      }).then(hole);
    })(240);
  }

  interviewKnopf.addEventListener('click', function () {
    if (zustand.interview) { beendeInterview(); } else { starteInterview(); }
  });

  // -- Push-to-Talk --------------------------------------------------------
  //
  // Halten = sprechen, loslassen = senden, Klasse 'kurz' (der Modus wird
  // NICHT geschaltet). Pointer Events mit setPointerCapture, damit ein
  // Finger, der vom Knopf rutscht, weiter erkannt wird -- und pointercancel
  // sendet NICHTS.

  if (pttKnopf) {
    var pttRecorder = null;

    pttKnopf.addEventListener('pointerdown', function (ev) {
      if (zustand.interview) { return; }
      ev.preventDefault();
      pttKnopf.setPointerCapture(ev.pointerId);
      zustand.pttVon = Date.now();
      zustand.pttAbgebrochen = false;
      pttKnopf.dataset.haelt = '1';
      strom().then(function (s) {
        if (zustand.pttAbgebrochen) { return; }
        pttRecorder = new MediaRecorder(s);
        pttRecorder.ondataavailable = function (e) {
          var dauer = Math.round((Date.now() - zustand.pttVon) / 1000);
          // Zu kurz oder abgebrochen: NICHTS senden. Ein versehentlicher
          // Tipper soll keine leere Aufnahme in den Chat legen.
          if (zustand.pttAbgebrochen ||
              Date.now() - zustand.pttVon < PTT_MIN_MS ||
              !e.data || !e.data.size) { return; }
          reiheEin({ blob: e.data, dauer: Math.max(1, dauer),
                     brauchtInterview: false });
        };
        pttRecorder.start();
      }).catch(function () { zustand.pttAbgebrochen = true; });
    });

    function pttEnde(abbrechen) {
      return function (ev) {
        if (pttKnopf.dataset.haelt !== '1') { return; }
        pttKnopf.dataset.haelt = '0';
        if (abbrechen) { zustand.pttAbgebrochen = true; }
        try { pttKnopf.releasePointerCapture(ev.pointerId); } catch (e) {}
        if (pttRecorder && pttRecorder.state !== 'inactive') {
          pttRecorder.stop();
        }
        pttRecorder = null;
      };
    }

    pttKnopf.addEventListener('pointerup', pttEnde(false));
    pttKnopf.addEventListener('pointercancel', pttEnde(true));
    // Wegziehen: mit setPointerCapture bleibt der Knopf das Ziel, aber ein
    // Kontextmenue oder ein Systemdialog kann den Zeiger entfuehren.
    pttKnopf.addEventListener('lostpointercapture', function (ev) {
      if (pttKnopf.dataset.haelt === '1') { pttEnde(true)(ev); }
    });
  }

  nachUnten();
  hole();
})();
"""


def _js() -> str:
    """``_CHAT_JS`` mit den Zahlen aus den Modulkonstanten.

    Platzhalter und keine f-String-Interpolation: das Skript ist voll mit
    geschweiften Klammern."""
    return (
        _CHAT_JS
        .replace("__POLL_MS__", str(POLL_MS))
        .replace("__POLL_MS_HINTERGRUND__", str(POLL_MS_HINTERGRUND))
        .replace("__PTT_MIN_MS__", str(PTT_MIN_MS))
        .replace("__UPLOAD_VERSUCHE__", str(UPLOAD_VERSUCHE))
        .replace("__UPLOAD_WARTEN_MS__", json.dumps(list(UPLOAD_WARTEN_MS)))
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

    blasen = "\n".join(_blase_html(n) for n in daten["nachrichten"])
    if not blasen:
        blasen = f'<p class="leer">{html.escape(_TEXT_LEER)}</p>'

    koerper = (
        f"<h1>{html.escape(daten.get('titel') or _TEXT_TITEL)}</h1>\n"
        f'<p><a href="{html.escape(token)}">'
        f"{html.escape(_TEXT_ZUR_GRUPPENSEITE)}</a></p>\n"
        f'<noscript><p class="leer">{html.escape(_TEXT_OHNE_JS)}</p></noscript>\n'
        f'<div class="verlauf" id="verlauf" data-letzte="{daten["letzte"]}">\n'
        f"{blasen}\n</div>\n"
        f'<div class="tippt" id="tippt"></div>\n'
        f'<input type="hidden" id="nonce" value="{html.escape(nonce_wert, quote=True)}">\n'
        f'<div class="fuss" id="fuss" data-segment-ms="{int(segment_ms)}"\n'
        f'     data-interview="{1 if daten["interviewmodus"] else 0}">\n'
        f'  <div class="uhr" id="uhr" hidden></div>\n'
        f'  <div class="pegel" id="pegel" hidden><span></span></div>\n'
        f'  <div class="warteschlange" id="warteschlange"></div>\n'
        f'  <button type="button" id="interview">'
        f'{html.escape(_TEXT_INTERVIEW_AN)}</button>\n'
        f'  <div class="zeile">\n'
        f'    <input type="text" id="eingabe" autocomplete="off" '
        f'placeholder="{html.escape(_TEXT_EINGABE, quote=True)}">\n'
        f'    <button type="button" id="ptt" title="'
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

    if unterpfad == "":
        _sende_seite(handler, db_pfad, token, praefix, schluessel)
        return
    if unterpfad == "zustand":
        _sende_zustand(handler, db_pfad, token, query)
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


def _gruppe_oder_404(handler, db_pfad: str, token: str) -> int | None:
    """Die chat_id zum Token, oder 404 und None."""
    from interview_theater import web

    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        chat_id = web_daten.chat_id_nach_token(conn, token)
    finally:
        conn.close()
    if chat_id is None:
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


def beantworte_post(handler, db_pfad: str, token: str, unterpfad: str,
                    schluessel: bytes) -> None:
    """Alles, was der Browser schickt. Reihenfolge der Pruefungen:
    **Pfad, Token, Nonce, Wert** -- erst 404, dann 403, dann 400."""
    from interview_theater import web

    if unterpfad not in _POSTWEGE:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    chat_id = _gruppe_oder_404(handler, db_pfad, token)
    if chat_id is None:
        return
    try:
        _POSTWEGE[unterpfad](handler, db_pfad, token, chat_id, schluessel)
    except sqlite3.Error as fehler:
        handler.log_error("Datenbankfehler im Web-Chat: %s", fehler)
        handler._fehler(500, "Die Datenbank ist gerade nicht beschreibbar.")


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
    if not isinstance(content_type, str) or not content_type.strip():
        return None
    haupt = content_type.split(";", 1)[0].strip().lower()
    return MIME_ERLAUBT.get(haupt)


def haupttyp(handler) -> str:
    """Der Haupt-MIME-Typ der Anfrage, fuer die Spalte ``mime`` -- ohne
    Parameter (``audio/webm;codecs=opus`` -> ``audio/webm``)."""
    roh = handler.headers.get("Content-Type") or ""
    return roh.split(";", 1)[0].strip().lower()


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

    Reihenfolge der Pruefungen: **``Content-Length`` lesen, Typ (415),
    Groesse (400/413), Nonce (403), Dauer (400), dann erst der Koerper** --
    die Kopfzeilen kosten nichts, der Koerper kostet Speicher. Jeder
    ablehnende Zweig verwirft zuerst den angekuendigten Koerper
    (``_verwerfe_koerper``), bevor er antwortet: sonst sieht der Client bei
    einer grossen ``Content-Length`` denselben Verbindungsabbruch wie frueher
    im 413-Zweig, nur jetzt bei 415/403/400 -- ``urllib`` schreibt den ganzen
    Koerper in einem Zug, ohne auf eine Zwischenantwort zu warten. Geschrieben
    wird erst die Zeile, dann die Datei (der Pfad enthaelt die id), und erst
    danach der Verweis; scheitert die Datei, bleibt eine Zeile ohne ``datei``
    stehen und ``lade_datei`` wirft -- ``aufnahme`` bittet die Gruppe dann,
    es nochmal zu schicken."""
    from interview_theater import web

    try:
        laenge = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        handler._fehler(400, _TEXT_FEHLER_ANFRAGE)
        return

    endung = endung_fuer(handler.headers.get("Content-Type"))
    if endung is None:
        _verwerfe_koerper(handler, laenge)
        handler._fehler(415, _TEXT_FEHLER_TYP)
        return
    if laenge <= 0:
        handler._fehler(400, _TEXT_FEHLER_LEER_AUDIO)
        return
    if laenge > MAX_AUDIO_BYTES:
        _verwerfe_koerper(handler, laenge)
        handler._fehler(413, _TEXT_FEHLER_GROSS)
        return

    felder = urllib.parse.parse_qs(urllib.parse.urlsplit(handler.path).query)
    if not web.nonce_gueltig(schluessel, token, (felder.get("nonce") or [""])[0]):
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
        handler._fehler(400, _TEXT_FEHLER_LEER_AUDIO)
        return

    with schreibend(db_pfad) as conn:
        message_id = repo.lege_web_post_an(
            conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
            dauer=dauer, mime=haupttyp(handler),
        )
        ziel = web_kanal.eingangspfad(_audio_verz(), chat_id, message_id, endung)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(koerper)
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


def _zustand(db_pfad: str, token: str, nach: int = 0) -> dict | None:
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        return web_daten.web_chatzustand(conn, token, nach)
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


def _sende_zustand(handler, db_pfad: str, token: str, query: str) -> None:
    from interview_theater import web

    daten = _zustand(db_pfad, token, _nach(query))
    if daten is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    # Der Verlauf enthaelt HTML aus Bot-Ausgaben -- er wird HIER gefiltert,
    # nicht im Browser: ein Filter im JavaScript liegt auf der Seite, die er
    # schuetzen soll.
    for nachricht in daten["nachrichten"]:
        nachricht["html"] = sichere_html(nachricht["text"])
    daten["segment_ms"] = _segment_ms()
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
        chat_id = web_daten.chat_id_nach_token(conn, token)
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
    try:
        werte = urllib.parse.parse_qs(query or "")
    except ValueError:
        return 0
    roh = (werte.get("nach") or ["0"])[0]
    return int(roh) if roh.isdigit() else 0


def _segment_ms() -> int:
    """Die Segmentlaenge fuer den Browser. Aus der Umgebung, weil der
    Webserver keine ``Einstellungen`` laedt (er braucht weder LLM- noch
    STT-Variablen) -- derselbe Name wie dort
    (``einstellungen.VORGABE_SEGMENT_MS``)."""
    roh = (os.environ.get("IT_WEB_SEGMENT_MS") or "").strip()
    return int(roh) if roh.isdigit() and int(roh) > 0 else 45_000
