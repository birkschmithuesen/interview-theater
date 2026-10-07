"""Der kleine Webserver: Team-Dashboard und Leseansicht je Gruppe.

Zwei Routen derselben Anwendung
(NACHTRAG-weboberflaeche-und-sprache.md N1):

* ``/`` -- Team-Dashboard, alle Gruppen nebeneinander, projiziert. Ohne
  Nachrichtentext und ohne Transkripte: auf dem Beamer stehen sonst
  Lebensgeschichten.
* ``/g/<token>`` -- Leseansicht einer Gruppe fuers Handy, Zugang ueber das
  Zufallstoken aus ``gruppe.web_token``, kein Login.
* ``/gesund`` -- Health-Check, antwortet ohne Datenbankzugriff.

**Nur Standardbibliothek**, kein Framework, kein Build-Schritt: das Ding muss
am Workshoptag starten, nicht gepflegt werden.

**Lesen read-only, Schreiben nur ueber ``repo``** (05.09.2026 abends). Jedes
GET laeuft ueber die read-only geoeffnete Verbindung aus ``web_daten``. Die
Gruppenseite kann seitdem zusaetzlich eine kleine, feste Liste von Parametern
aendern (``web_schreiben.FELDER``): dafuer, und nur dafuer, oeffnet der
POST-Handler eine schreibende Verbindung (``db.verbinde`` -- WAL und
``busy_timeout``) und ruft dieselben ``repo``-Funktionen wie die Knoepfe im
Chat. Kein SQL im Webserver, kein Modellaufruf, kein Material: Transkripte,
Verdichtungen, Belegzitate, der Szenen-Volltext und das Journal bleiben
unveraenderlich. Das **Dashboard bleibt vollstaendig read-only** -- es haengt
am Beamer, dort soll niemand im Vorbeigehen etwas umstellen.

Start::

    IT_DB=betrieb/soap.db python -m interview_theater.web

Umgebung: ``IT_DB`` (Pflicht), ``IT_WEB_BIND`` (Vorgabe ``127.0.0.1:8010``),
``IT_WEB_PREFIX`` (Vorgabe ``/theatersoap``).

Von aussen haengt der Server hinter nginx unter
``https://lab.artesmobiles.art/theatersoap/``. Ob nginx das Praefix
weiterreicht oder abschneidet, entscheidet die dortige Konfiguration und
nicht dieser Code -- deshalb nimmt das Routing beide Formen an
(``/g/<token>`` und ``/theatersoap/g/<token>``), und alle erzeugten Links
sind relativ.
"""

import hashlib
import hmac
import html
import json
import re
import os
import secrets
import sqlite3
import sys
import time
import traceback
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import cothinker_status, db, phasen, vorspann, web_daten, web_schreiben  # noqa: F401 -- SZENENFELDER im HTML

VORGABE_BIND = "127.0.0.1:8010"
#: Externer URL-Pfad, unter dem nginx auf herkules den Server durchreicht.
#: Historischer Name aus dem ersten Einsatz -- er steht in der nginx-Konfig,
#: nicht im Code; aendern heisst dort aendern (und IT_WEB_PREFIX mitziehen).
VORGABE_PRAEFIX = "/theatersoap"

#: Sekunden bis zum Selbst-Neuladen beider Seiten. Per <meta refresh>, damit
#: die Seite ohne JavaScript aktuell bleibt -- ein projizierter Rechner soll
#: nach einem Browserneustart einfach weiterlaufen.
NEULADEN_SEKUNDEN = 10

#: Wie lange ein Formular-Nonce gilt (Sekunden). Zwei Fenster werden
#: akzeptiert, ein Nonce lebt also zwischen einer und zwei Stunden.
NONCE_FENSTER = 3600

#: Der Wert, den ein Dropdown traegt, wenn daneben das Freitextfeld gilt.
#: Steht wortgleich in ``_BEARBEITEN_JS``.
EIGENE = "__EIGENE__"

#: Die Kopfzeilen, die auf JEDER Antwort stehen -- auch 404, 413, 429, 500,
#: auch /gesund und die .md/.txt-Downloads. Angehaengt in
#: ``_Basishandler.end_headers`` und damit an genau EINER Stelle: ``_antworte``
#: allein wuerde ``send_error`` der Standardbibliothek verfehlen (501 bei
#: unbekannter Methode, 400 bei kaputter Anfragezeile).
#:
#: ``microphone=(self)`` steht hier, weil die Chatansicht (Karte A2) im
#: Browser aufnimmt; alles andere ist nicht aufgezaehlt und damit aus.
SICHERHEITSKOPFZEILEN = (
    ("Referrer-Policy", "no-referrer"),
    ("X-Robots-Tag", "noindex, nofollow"),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Permissions-Policy", "microphone=(self)"),
)

#: Die Inhaltsrichtlinie. **Keine Fremdquelle** -- der Workshopraum haengt an
#: einem Tailnet, und eine Seite ohne Login soll nichts nachladen, was
#: jemand anders liefert. ``'unsafe-inline'`` steht bewusst NICHT da: die
#: beiden Inline-Tags aus ``_seite`` bekommen einen Nonce (siehe
#: ``csp_nonce``).
#:
#: ``media-src 'self' blob:`` fuer die Wiedergabe der eigenen Aufnahme im
#: Browser (MediaRecorder liefert einen Blob), ``connect-src 'self'`` fuer
#: das sanfte Nachladen und den Poll.
CSP_VORLAGE = (
    "default-src 'none'; "
    "script-src 'nonce-{nonce}'; "
    "style-src 'nonce-{nonce}'; "
    "img-src 'self' data:; "
    "media-src 'self' blob:; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'"
)

#: Was eine unerwartete Ausnahme nach aussen sagt. Ein Satz, kein Pfad, keine
#: Klasse, keine Zeile -- das steht im Log (siehe ``log_error``). Die Gruppe
#: kann daran nichts beheben, aber sie wartet gerade (docs/agents/entscheidungen.md: "Die Gruppe
#: erfaehrt von einem Fehler nur, wenn sie ihn beheben kann oder gerade
#: darauf wartet").
TEXT_500 = "Da ist bei uns etwas schiefgegangen."

#: 403-Text fuer eine Anfrage, die von woanders kommt. Ein Satz, kein
#: Hinweis darauf, WAS nicht gepasst hat -- wer das Formular vor sich hat,
#: sieht diesen Text nie.
TEXT_FREMDE_HERKUNFT = "Diese Anfrage kommt nicht von dieser Seite."

#: Wo der Formular-Nonce beim Audio-Upload steht (E-S9). In der Query stand
#: er in der Serverlogzeile -- und der ist die eine Stelle, an der ein
#: CSRF-Merkmal garantiert aufgeschrieben wird.
NONCE_KOPFZEILE = "X-Nonce"


def eigene_herkunft(handler) -> bool:
    """Kommt diese Anfrage von unserer eigenen Seite?

    **Zwei Merkmale, beide optional, beide streng, wenn sie da sind:**

    * ``Sec-Fetch-Site`` -- jeder Browser ab 2020 schickt ihn.
      ``cross-site`` heisst ausdruecklich "von woanders" und faellt auch bei
      ``Origin: null`` (sandboxed iframe), wo der Vergleich unten nichts
      sagen kann.
    * ``Origin`` -- verglichen gegen den ``Host``-Header **oder** den ersten
      Wert von ``X-Forwarded-Host``. Nicht gegen ``IT_WEB_URL``: eine
      Konfiguration, die im Betrieb nicht passt, waere ein 403 auf alles.
      ``X-Forwarded-Host`` ist noetig, weil nginx ohne
      ``proxy_set_header Host $host`` den internen Host weiterreicht
      (``100.75.24.33:8010``), der Browser aber den oeffentlichen Origin
      schickt -- sonst waere jeder echte POST ein 403 (Abschlussreview).
      Das oeffnet nichts: eine fremde Seite kann im Browser keine eigene
      Kopfzeile wie ``X-Forwarded-Host`` setzen, ohne einen CORS-Preflight
      auszuloesen, und den beantwortet dieser Server nie. Ein Angreifer
      ausserhalb eines Browsers kann sie setzen -- er kann aber auch den
      Origin weglassen und landete schon bisher beim Nonce.

    **Fehlen beide, ist die Antwort True** und der Nonce entscheidet wie
    bisher. ``curl`` schickt keinen Origin, und das Reviewer-Drehbuch faehrt
    mit ``curl``; ein 403 darauf machte die Pruefung unmoeglich. Das kostet
    nichts: ein Angriff ueber einen Browser TRAEGT die Kopfzeilen, und ein
    Angreifer, der sie weglassen kann, hat ohnehin keinen fremden Browser
    dazwischen -- er braucht dann aber Token und Nonce, und das ist die
    Schicht, die es schon gab."""
    if (handler.headers.get("Sec-Fetch-Site") or "").strip().lower() == "cross-site":
        return False
    herkunft = (handler.headers.get("Origin") or "").strip()
    if not herkunft:
        return True
    wirt = (handler.headers.get("Host") or "").strip().lower()
    weitergereicht = (
        (handler.headers.get("X-Forwarded-Host") or "").split(",", 1)[0].strip().lower()
    )
    erlaubt = {w for w in (wirt, weitergereicht) if w}
    if not erlaubt:
        return False
    eigene = urllib.parse.urlsplit(herkunft).netloc.lower()
    return bool(eigene) and eigene in erlaubt


def schliesse_nach_antwort(handler) -> None:
    """Nach dieser Antwort wird die Verbindung geschlossen (``Connection:
    close``).

    Fuer jede Ablehnung, die antwortet, BEVOR der Koerper gelesen ist: bei
    HTTP/1.1 bleibt die Verbindung sonst offen, der ungelesene Koerper liegt
    im Socket und wird als naechste Anfragezeile gelesen -- die naechste,
    ordentliche Anfrage bekaeme einen 400 aus Muell (Abschlussreview).
    Schliessen statt Weglesen, weil eine Absage (429, 403) nicht dafuer
    bezahlen soll, bis zu 8 MiB anzunehmen. Die Kopfzeile setzt
    ``_Basishandler.end_headers``; bei einer Attrappe ohne diese Klasse
    bleibt es beim Merker."""
    handler.verbindung_schliessen = True


def maskiere_token(pfad: str) -> str:
    """Der Anfragepfad fuer die Logzeile: Token auf vier Zeichen, Query weg.

    Vier Zeichen bleiben stehen, damit man zwei Gruppen im Log
    auseinanderhalten kann -- das ist der ganze Zweck, den das Token dort je
    hatte. Die Query faellt komplett: beim Audio-Upload stand der
    Formular-Nonce darin (A2-Uebergabe Punkt 3), und die Logzeile ist die
    eine Stelle, an der ein CSRF-Merkmal garantiert aufgeschrieben wird."""
    ohne_query = pfad.split("?", 1)[0]
    stelle = ohne_query.find("/g/")
    if stelle < 0:
        return ohne_query
    kopf = ohne_query[: stelle + len("/g/")]
    rest = ohne_query[stelle + len("/g/"):]
    token, trenner, schwanz = rest.partition("/")
    if len(token) <= 4:
        return ohne_query
    return f"{kopf}{token[:4]}...{trenner}{schwanz}"


def _html_500() -> str:
    """Die 500-Seite, in der aktiven Sprache aufgebaut (wie
    ``nicht_gefunden_html``) -- nicht beim Import eingefroren, sonst bliebe
    sie beim deutschen Stand, auch wenn das Profil Englisch spricht."""
    return (
        f'<!doctype html><html lang="{html.escape(sprache.code())}">'
        f'<meta charset="utf-8"><p>{html.escape(T.TEXT_500)}</p></html>'
    )


def csp_nonce(schluessel: bytes, token: str, jetzt: float | None = None) -> str:
    """Der CSP-Nonce einer Antwort -- **aus dem Stundenfenster abgeleitet**,
    nicht gewuerfelt.

    Das ist die eine Stelle, an der die Standardempfehlung ("ein Nonce je
    Antwort") hier falsch waere. ``_SCROLL_JS`` vergleicht alle zehn Sekunden
    ``document.body.innerHTML`` mit dem vorigen Stand und tauscht den Koerper
    nur bei Unterschied. Das ``<script>``-Tag steht IM Koerper; ein je Antwort
    neuer Nonce stuende als Attribut darin, der Vergleich schluege bei jedem
    Poll an, und die Seite risse alle zehn Sekunden jedes offene Eingabefeld
    mit. Genau dafuer ist schon der Formular-Nonce abgeleitet (siehe
    ``nonce``); hier gilt derselbe Grund und dieselbe Fensterbreite, damit
    beide zur selben Sekunde wechseln.

    Eigenes Praefix ``csp:``: der Formular-Nonce steht beim Audio-Upload in
    einer Kopfzeile und frueher in der Query -- ein Leck des einen darf den
    anderen nicht mitnehmen."""
    jetzt = time.time() if jetzt is None else jetzt
    fenster = int(jetzt) // NONCE_FENSTER
    return hmac.new(
        schluessel, f"csp:{token}:{fenster}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]


def mit_nonce(html_text: str, nonce_wert: str) -> str:
    """Haengt den Nonce an die beiden Inline-Tags aus ``_seite``.

    **Warum nachtraeglich und nicht als Parameter von ``_seite``:** ``_seite``
    hat sechs Aufrufer, einer davon in ``web_chat`` (Karte A2). Eine
    Signaturaenderung dort waere ein Eingriff in ein Modul, das diese Karte
    sonst nicht anfasst.

    **Warum das sicher ist:** ``_seite`` ist der einzige Erzeuger eines
    literalen ``<style>``/``<script>``. Jeder Text aus der Gruppe laeuft
    vorher durch ``html.escape`` bzw. den Filter aus A2 und traegt ``&lt;``
    statt ``<`` -- ``test_mit_nonce_ruehrt_escapten_text_nicht_an`` haelt das
    fest."""
    return (
        html_text
        .replace("<style>", f'<style nonce="{nonce_wert}">')
        .replace("<script>", f'<script nonce="{nonce_wert}">')
    )


def _nonce_roh(schluessel: bytes, token: str, fenster: int) -> str:
    unterschrift = hmac.new(
        schluessel, f"{token}:{fenster}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]
    return f"{fenster}.{unterschrift}"


def nonce(schluessel: bytes, token: str, jetzt: float | None = None) -> str:
    """Der Formular-Nonce einer Gruppenseite.

    **Wozu**, wo das Token in der URL doch schon das Geheimnis ist: gegen
    einen fremden Link. Wer jemanden dazu bringt, eine fremde Seite zu
    oeffnen, kann von dort aus ein POST an unsere Adresse schicken -- das
    Token steckt dann nicht darin, aber ein geratener oder mitgelesener Link
    wuerde reichen. Der Nonce steht nur IM HTML der Seite, und eine fremde
    Seite kann unser HTML nicht lesen (keine CORS-Freigabe). Ohne ihn: 403.

    **Abgeleitet statt gespeichert**, und das ist kein Geiz mit Speicher,
    sondern noetig: die Seite laedt sich alle zehn Sekunden per fetch nach und
    vergleicht den neuen ``<body>`` mit dem alten. Ein bei jedem Aufruf neu
    gewuerfelter Nonce stuende in diesem body -- der Vergleich schluege immer
    an, die Seite tauschte sich alle zehn Sekunden aus und riss dabei jedes
    offene Eingabefeld mit. Ein aus Token und Stundenfenster abgeleiteter
    Nonce ist innerhalb einer Stunde derselbe; der body bleibt gleich, solange
    sich an den Daten nichts aendert."""
    jetzt = time.time() if jetzt is None else jetzt
    return _nonce_roh(schluessel, token, int(jetzt) // NONCE_FENSTER)


def nonce_gueltig(
    schluessel: bytes, token: str, wert, jetzt: float | None = None
) -> bool:
    """Prueft einen Nonce gegen das laufende und das vorige Fenster.

    Zwei Fenster, damit eine Seite, die kurz vor dem Stundenwechsel geoeffnet
    wurde, nicht eine Minute spaeter ins Leere schreibt. Vergleich ueber
    ``compare_digest``, nicht ``==``."""
    if not isinstance(wert, str) or "." not in wert:
        return False
    kopf, _, _rest = wert.partition(".")
    if not kopf.isdigit():
        return False
    jetzt = time.time() if jetzt is None else jetzt
    aktuell = int(jetzt) // NONCE_FENSTER
    return any(
        hmac.compare_digest(_nonce_roh(schluessel, token, fenster), wert)
        for fenster in (aktuell, aktuell - 1)
    )


#: Haelt die Scrollposition ueber das Neuladen hinweg. Das Minimum an
#: JavaScript, das die Seite ertraeglich macht: ohne das springt eine lange
#: Gruppenseite alle zehn Sekunden nach oben, mitten im Lesen. Faellt JS aus,
#: bleibt alles andere benutzbar.
_SCROLL_JS = """
(function () {
  // Sanftes Nachladen (Birk 05.09.: "wenn ich etwas ausklappe, geht es
  // immer wieder zu, sobald die Seite neu laedt"). Kein meta refresh mehr:
  // alle NEULADEN Sekunden wird die Seite per fetch geholt; hat sich der
  // Inhalt nicht geaendert, passiert nichts. Hat er sich geaendert, wird
  // nur der <body> getauscht -- und vorher gemerkt, welche <details> offen
  // waren (am summary-Text), danach wieder geoeffnet. Scrollposition
  // bleibt, weil das Dokument nicht neu geladen wird.
  var INTERVALL_MS = __NEULADEN_MS__;
  var offene = function () {
    var s = {};
    document.querySelectorAll('details[open] > summary').forEach(function (el) {
      s[el.textContent.trim()] = true;
    });
    return s;
  };
  var stelleHer = function (zustand) {
    document.querySelectorAll('details > summary').forEach(function (el) {
      if (zustand[el.textContent.trim()]) { el.parentElement.setAttribute('open', ''); }
    });
  };
  // Wer gerade tippt, verliert nichts (Brief 05.09. abends): steht der
  // Fokus in einem Bearbeitungsfeld oder ist eines geaendert und noch nicht
  // gespeichert, wird gar nicht erst nachgeladen. Sonst tauschte der
  // Austausch des <body> den halb getippten Satz gegen den alten Stand aus
  // -- dieselbe Sorte Aerger wie das Zuklappen der <details> vorher.
  var wirdBearbeitet = function () {
    var aktiv = document.activeElement;
    if (aktiv && aktiv.closest && aktiv.closest('.feld')) { return true; }
    return !!document.querySelector('.feld[data-schmutzig="1"]');
  };
  var letzter = document.body.innerHTML;
  var laeuft = false;
  setInterval(function () {
    if (laeuft || document.hidden || wirdBearbeitet()) { return; }
    laeuft = true;
    fetch(location.href, { cache: 'no-store', headers: { 'X-Nachladen': '1' } })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        if (!html) { return; }
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var neu = doc.body ? doc.body.innerHTML : null;
        if (!neu || neu === letzter) { return; }
        var zustand = offene();
        var y = window.scrollY;
        document.body.innerHTML = neu;
        stelleHer(zustand);
        window.scrollTo(0, y);
        letzter = neu;
      })
      .catch(function () {})
      .finally(function () { laeuft = false; });
  }, INTERVALL_MS);
})();
"""
#: Das Speichern auf der Gruppenseite. Wieder das Minimum an JavaScript:
#: Ereignisdelegation an ``document``, damit nach einem Austausch des
#: ``<body>`` durch das sanfte Nachladen nichts neu verdrahtet werden muss.
#: Ohne JS bleibt die Seite lesbar -- nur nicht beschreibbar.
_BEARBEITEN_JS = """
(function () {
  var wertVon = function (feld) {
    var auswahl = feld.querySelector('select.auswahl');
    if (auswahl) {
      if (auswahl.value === '__EIGENE__') {
        var frei = feld.querySelector('.eigene');
        return frei ? frei.value : '';
      }
      return auswahl.value;
    }
    var mehrfach = feld.querySelector('select[multiple]');
    if (mehrfach) {
      return Array.prototype.slice.call(mehrfach.selectedOptions)
        .map(function (o) { return o.value; }).join(',');
    }
    var eingabe = feld.querySelector('textarea, input');
    return eingabe ? eingabe.value : '';
  };
  // Die Meldungen stehen als data-Attribute im <body> (#meldungen), in der
  // Sprache des Profils -- im Skript steht kein Nutzertext (Karte A1).
  var meldung = function (name) {
    var m = document.getElementById('meldungen');
    return (m && m.dataset[name]) || '';
  };
  var melde = function (feld, text, schlecht) {
    var hinweis = feld.querySelector('.hinweis');
    if (!hinweis) { return; }
    hinweis.textContent = text;
    hinweis.className = schlecht ? 'hinweis schlecht' : 'hinweis gut';
  };
  document.addEventListener('input', function (ev) {
    var feld = ev.target.closest ? ev.target.closest('.feld') : null;
    if (feld) { feld.dataset.schmutzig = '1'; melde(feld, '', false); }
  });
  document.addEventListener('change', function (ev) {
    var feld = ev.target.closest ? ev.target.closest('.feld') : null;
    if (!feld) { return; }
    feld.dataset.schmutzig = '1';
    melde(feld, '', false);
    var auswahl = feld.querySelector('select.auswahl');
    var frei = feld.querySelector('.eigene');
    if (auswahl && frei) { frei.hidden = auswahl.value !== '__EIGENE__'; }
  });
  document.addEventListener('click', function (ev) {
    var knopf = ev.target.closest ? ev.target.closest('button.speichern') : null;
    if (!knopf) { return; }
    var feld = knopf.closest('.feld');
    if (!feld) { return; }
    // Entfernen fragt einmal nach -- ohne Dialogfenster, damit ein
    // Fehlgriff auf dem Telefon nicht gleich eine Figur kostet.
    var entfernt = (feld.dataset.feld || '').slice(-10) === '_entfernen';
    if (entfernt && knopf.dataset.sicher !== '1') {
      knopf.dataset.sicher = '1';
      knopf.textContent = meldung('sicher');
      return;
    }
    knopf.disabled = true;
    melde(feld, meldung('speichert'), false);
    fetch(location.pathname, {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        // Der Nonce steht IM body, nicht an ihm: das sanfte Nachladen
        // tauscht nur innerHTML aus, und so kommt beim Fensterwechsel der
        // frische Nonce von selbst mit.
        nonce: (document.getElementById('nonce') || {}).value || '',
        feld: feld.dataset.feld,
        ziel: feld.dataset.ziel || null,
        wert: wertVon(feld)
      })
    }).then(function (r) {
      return r.text().then(function (t) { return { ok: r.ok, text: t }; });
    }).then(function (a) {
      knopf.disabled = false;
      if (!a.ok) { melde(feld, a.text || meldung('fehler'), true); return; }
      feld.dataset.schmutzig = '0';
      melde(feld, meldung('gespeichert'), false);
    }).catch(function () {
      knopf.disabled = false;
      melde(feld, meldung('fehler'), true);
    });
  });
})();
"""

#: Mobile-App-Shell, Nachbesserung 03.10.2026 (Birk-Befund 09:19): dieselbe
#: Zeile an allen drei Stellen, die ein ``<head>`` von Hand bauen (``_seite``,
#: ``leitfaden_html``, ``nicht_gefunden_html``). ``viewport-fit=cover``
#: erlaubt ``env(safe-area-inset-*)`` (Notch/Home-Indikator);
#: ``interactive-widget=resizes-content`` laesst Chrome/Android den
#: sichtbaren Bereich wirklich verkleinern, wenn die Tastatur aufgeht, statt
#: ihn nur zu ueberlagern -- ohne das blieb ``100dvh`` unter der Tastatur
#: hoch, und der Fuss schwamm darueber. iOS Safari ignoriert den Zusatz
#: (daher der ``visualViewport``-Umweg in ``web_vereint._VH_JS``).
_VIEWPORT_META = (
    '<meta name="viewport" content="width=device-width, initial-scale=1, '
    'viewport-fit=cover, interactive-widget=resizes-content">'
)

#: Mobile-App-Shell (03.10.2026): kein horizontales Scrollen auf
#: irgendeiner Seite -- ``100vw`` ist auf dem Telefon oft breiter als der
#: sichtbare Bereich (Scrollbar-Kompensation, Rundung), und genau das
#: erzeugt das seitliche Wackeln aus Birks Befund. Gilt fuer jede Seite
#: dieses Moduls, nicht nur die vereinte -- Dashboard, Leitfaden und
#: Probenansicht haben keinen legitimen Grund, seitlich zu scrollen.
#: Keine Erklaerung dazu IM CSS-Text (anders als sonst in diesem Projekt
#: ueblich): ``_CSS_GEMEINSAM`` ist nicht in ``BLEIBT_DEUTSCH``
#: (tests/test_sprache_texte.py) eingetragen, ein deutscher CSS-Kommentar
#: darin wuerde dort als unuebersetzte Konstante auffallen.
_CSS_GEMEINSAM = """
ul.fragen { list-style: none; padding: 0; margin: 0; }
ul.fragen li { margin: .25em 0; }
pre.leitfaden { white-space: pre-wrap; font-family: inherit; margin: 0; }
* { box-sizing: border-box; }
html { overflow-x: hidden; }
body { margin: 0; padding: 1rem 1.2rem 3rem; overflow-x: hidden;
       font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
       line-height: 1.45; }
h1 { font-size: 1.5rem; margin: 0 0 .8rem; }
h2 { font-size: 1.15rem; margin: 1.6rem 0 .5rem; }
h3 { font-size: 1rem; margin: 0 0 .4rem; }
.stand { font-weight: normal; font-size: .8rem; opacity: .6; }
.leer { opacity: .45; font-style: italic; }
dt { font-size: .78rem; text-transform: uppercase; letter-spacing: .04em;
     opacity: .6; margin-top: .5rem; }
dd { margin: 0; }
dl { margin: 0; }
"""

_CSS_DASHBOARD = """
body { background: #14161a; color: #e7e9ec; }
.gruppen { display: grid; gap: .9rem;
           grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr)); }
.karte { background: #1d2026; border: 1px solid #2c313a; border-radius: .5rem;
         padding: .8rem .9rem; }
.karte h2 { margin: 0; font-size: 1.2rem; }
.kopf { display: flex; justify-content: space-between; align-items: baseline;
        gap: .5rem; border-bottom: 1px solid #2c313a; padding-bottom: .4rem;
        margin-bottom: .3rem; }
.bot { font-size: .78rem; opacity: .6; }
.marke { display: inline-block; font-size: .72rem; padding: .1rem .45rem;
         border-radius: .8rem; background: #2f4858; color: #cfe8ff; }
.zahlen { display: flex; flex-wrap: wrap; gap: .1rem .9rem; font-size: .85rem;
          margin-top: .6rem; }
.zahlen b { font-weight: 600; }
.vorfaelle { margin-top: .6rem; border-left: 3px solid #e04a4a;
             background: #2a1a1c; padding: .35rem .5rem; font-size: .82rem; }
.vorfaelle div { margin: .15rem 0; }
.vorfaelle .art { color: #ff8f8f; font-weight: 600; }
.zeit { opacity: .55; font-size: .75rem; }
table { border-collapse: collapse; width: 100%; font-size: .85rem; }
th, td { text-align: left; padding: .25rem .6rem .25rem 0;
         border-bottom: 1px solid #2c313a; }
th { opacity: .6; font-weight: 600; }
.figuren li { margin-bottom: .15rem; }
/* Je Interview eine Zeile mit den Ergebnissen als Kurzform (N6) -- ohne
   Zitate und ohne Zusammenfassung, das Dashboard haengt am Beamer. */
.ergebnisse { margin: .5rem 0 0; font-size: .85rem; }
.ergebnisse li { margin-bottom: .15rem; }
ul { margin: .2rem 0; padding-left: 1.1rem; }
"""

#: Nur der Ticker (Padua, 06.10.2026) -- NICHT in ``_CSS_DASHBOARD``: das
#: Dashboard (``dashboard_html``) teilt sich die Konstante mit dem Ticker,
#: und die Bitgleich-Tests (``tests/test_web_dashboard_en.py``) gelten fuer
#: beide Profile, nicht nur Dortmund (selbst gemessen, kein Dortmund-Fall).
#: Addendum 3 (06.10.2026): ein Eintrag, zwei Bloecke (Inhalt gross+offen,
#: Technik als Ampel-``<details>``), grosse lesbare Schrift fuers Telefon.
_CSS_TICKER = """
.ticker-status { display: flex; flex-wrap: wrap; gap: .25rem 1.2rem;
                 font-size: .9rem; opacity: .75; margin-bottom: 1rem; }
.ticker-stale { color: #ffb020; font-weight: 600; opacity: 1; }
.ticker-liste { font-size: 1.15rem; line-height: 1.5; }
.ticker-eintrag { display: block; margin-bottom: .9rem; padding: .7rem .9rem;
                  border: 1px solid #2c313a; border-radius: .6rem; background: #1d2026; }
.ticker-neu { font-size: 1.08em; border-color: #3a4454; }
.ticker-alt { opacity: .72; font-size: .9em; }
.ticker-alt summary { cursor: pointer; }
.ticker-kopf { font-size: .78em; opacity: .7; margin-bottom: .4rem; }
.ticker-kopf .zeit { font-weight: 600; opacity: 1; }
.ticker-inhalt h3 { margin: .6rem 0 .2rem; font-size: .8em; text-transform: uppercase;
                    letter-spacing: .04em; opacity: .65; }
.ticker-inhalt h3:first-child { margin-top: 0; }
.ticker-inhalt ul, .ticker-technik ul { margin: .1rem 0 .4rem; padding-left: 1.2rem; }
.ticker-technik { margin-top: .5rem; }
.ticker-technik summary { cursor: pointer; font-weight: 600; list-style: none; }
.ticker-technik summary::-webkit-details-marker { display: none; }
.ampel-gruen { color: #7fd99a; }
.ampel-gelb { color: #ffd166; }
.ticker-warnung { color: #ff8f8f; }
"""

_CSS_GRUPPE = """
body { background: #fbfaf7; color: #1b1b1b; font-size: 1.05rem;
       max-width: 44rem; margin: 0 auto; }
h1 { font-size: 1.6rem; }
h2 { border-bottom: 1px solid #ddd8cc; padding-bottom: .2rem; }
.szene { margin: 0 0 1.4rem; }
.szene .volltext { white-space: pre-wrap; background: #fff; border: 1px solid #e6e1d6;
                   border-radius: .4rem; padding: .7rem .8rem; }
.verdichtung { margin: 0 0 1.2rem; }
blockquote { margin: .2rem 0 .5rem; padding-left: .7rem;
             border-left: 3px solid #c9b98d; font-style: italic; }
.thema { margin-bottom: .5rem; }
.art { display: inline-block; font-size: .72rem; text-transform: uppercase;
       letter-spacing: .04em; background: #ece7db; border-radius: .8rem;
       padding: .05rem .5rem; margin-right: .4rem; }
details { margin-top: .5rem; }
summary { cursor: pointer; font-weight: 600; }
details.szene, details.verdichtung { border-bottom: 1px solid #e6e1d6;
                                     padding-bottom: .5rem; }
/* Die Kernbegriffe je Interview als Chips (06.09.2026). Kompakt und im
   bestehenden Ton der Seite -- dieselbe Rundung und dieselbe Sandfarbe wie
   .art, nur mit Rahmen statt Flaeche, damit sie neben der Themenzeile nicht
   um Aufmerksamkeit ringen. */
.begriffe { display: flex; flex-wrap: wrap; gap: .3rem; margin: .1rem 0 .5rem; }
.begriff { display: inline-block; font-size: .76rem; padding: .1rem .55rem;
           border-radius: .8rem; border: 1px solid #c9b98d; background: #f2ede1;
           color: #4a4032; }
/* Das Sprachprofil einer Figur: mehrzeilig, so wie es gespeichert ist. */
.profil { white-space: pre-wrap; font-size: .92rem; opacity: .8;
          margin: .2rem 0 .3rem; }
.eintrag { margin: .35rem 0; }
.zeit { opacity: .5; font-size: .78rem; }
/* Die Szenen-Uebersicht (06.09.2026, Birk: "Was mir in der Webansicht
   gefehlt hat, ist eine Uebersicht ueber die Szenen"). Eine Zeile je Szene,
   ueber den aufklappbaren Bloecken -- kompakt genug fuers Telefon. */
table.uebersicht { width: 100%; border-collapse: collapse; margin: 0 0 1rem;
                   font-size: .92rem; }
table.uebersicht th { text-align: left; font-size: .74rem;
                      text-transform: uppercase; letter-spacing: .04em;
                      opacity: .55; border-bottom: 1px solid #ddd8cc;
                      padding: .2rem .4rem .2rem 0; }
table.uebersicht td { vertical-align: top; padding: .3rem .4rem .3rem 0;
                      border-bottom: 1px solid #efeade; }
table.uebersicht td.nr { white-space: nowrap; opacity: .6; }
table.uebersicht .vorschlag { opacity: .6; font-style: italic; }
table.uebersicht .umfang { white-space: nowrap; opacity: .7;
                           font-size: .82rem; }
/* Die Bearbeitung (05.09.2026 abends). Grosse Bedienelemente: die Seite wird
   auf dem Telefon benutzt, im Stehen, im Probenraum. */
.feld { display: flex; flex-wrap: wrap; align-items: center; gap: .4rem;
        margin: .15rem 0 .6rem; }
.feld select, .feld input[type=text], .feld textarea {
        flex: 1 1 14rem; font: inherit; font-size: .98rem;
        padding: .35rem .45rem; border: 1px solid #cfc8b6; border-radius: .3rem;
        background: #fff; color: inherit; }
.feld textarea { min-height: 2.2rem; resize: vertical; }
.feld select[multiple] { min-height: 5rem; }
.feld button { font: inherit; font-size: .85rem; padding: .35rem .7rem;
               border: 1px solid #c9b98d; border-radius: .3rem;
               background: #ece7db; color: #1b1b1b; cursor: pointer; }
.feld button[disabled] { opacity: .5; cursor: default; }
.feld .hinweis { font-size: .78rem; opacity: .7; min-width: 5rem; }
.feld .hinweis.schlecht { color: #a12b2b; opacity: 1; }
/* Die Schaerfung: read-only, deshalb ohne Kasten und ohne Knopf. */
.schaerfung { font-size: .85rem; margin: .3rem 0 .5rem; opacity: .85; }
.schaerfung ul { margin: .1rem 0 0; }
/* Die frueheren Fassungen: ein Block im Block, deshalb eingerueckt und
   kleiner gesetzt als der aktuelle Text. Read-only, ohne Knopf. */
details.fassungen { margin-top: .6rem; font-size: .92rem; }
details.fassungen summary { font-weight: 600; opacity: .75; }
details.fassung { margin: .3rem 0 .3rem .8rem; }
details.fassung summary { font-weight: normal; opacity: .7; }
/* Wer wie viel spricht: vier schmale Spalten, damit die Tabelle auf ein
   Telefon passt. Die Hinweiszeilen darunter sind Fliesstext, kein Alarm. */
table.anteile { margin: .3rem 0 .5rem; }
table.anteile th, table.anteile td { text-align: left;
       padding: .2rem .8rem .2rem 0; border-bottom: 1px solid #e6e1d6; }
table.anteile th { font-size: .78rem; text-transform: uppercase;
       letter-spacing: .04em; opacity: .6; font-weight: 600; }
.hinweiszeile { font-size: .9rem; opacity: .8; margin: .2rem 0; }
/* Das Fehlstellen-Register: eine Arbeitsliste, kein Alarm -- deshalb
   dieselbe Papierfarbe wie der Rest und nur ein Strich an der Seite. */
ul.fehlstellen { list-style: none; padding: 0 0 0 .7rem; margin: .2rem 0;
                 border-left: 3px solid #c9b98d; }
ul.fehlstellen li { margin: .3rem 0; }
/* Die Dramaturgie-Pruefung: ebenfalls read-only. Die Schwere faerbt, mehr
   nicht -- entschieden wird im Chat. */
.befund { font-size: .9rem; margin: .35rem 0; padding-left: .6rem;
          border-left: 3px solid #d8d0bd; }
.befund.hart { border-left-color: #a12b2b; }
.befund.blocker, .befund.hoch { border-left-color: #a12b2b; }
.befund .marke { font-size: .75rem; opacity: .6; }
.befund .vorschlag { display: block; font-size: .82rem; opacity: .8; }
/* Die Fassungsleiste (07.09.2026): umschalten, nicht aufklappen. Grosse
   Trefferflaechen -- die Seite wird auf dem Telefon benutzt, im Stehen. */
nav.fassungen { display: flex; flex-wrap: wrap; gap: .3rem; margin: .3rem 0; }
.fassung { display: inline-block; min-width: 2rem; text-align: center;
           font-size: .85rem; padding: .25rem .55rem; border-radius: .3rem;
           border: 1px solid #c9b98d; background: #f2ede1; color: #4a4032;
           text-decoration: none; }
.fassung.aktiv { background: #4a4032; border-color: #4a4032; color: #f7f3e8; }
/* Der Vorspann (07.09.2026): read-only, deshalb ohne Kasten und ohne Knopf --
   dieselbe ruhige Flaeche wie .schaerfung, nur mit Zwischenueberschriften. */
.vorspann h3 { font-size: .78rem; text-transform: uppercase;
               letter-spacing: .04em; opacity: .55; font-weight: 600;
               margin: .8rem 0 .15rem; }
.vorspann p { margin: 0 0 .2rem; }
.vorspann ul { list-style: none; margin: 0; padding: 0; }
.vorspann li { margin: .1rem 0; }
.figur { border-top: 1px solid #eee7d8; padding-top: .5rem; margin-top: .5rem; }
.figur .marke { font-size: .78rem; opacity: .6; }
.hinzu { margin-top: .8rem; }
"""

#: Der Buehne-Inhalt (Phase 4, nur Web, 02.10.2026) -- eigene Konstante statt
#: an ``_CSS_GRUPPE`` angehaengt, damit diese bitgleich bleibt
#: (tests/test_sprache_bitgleich.py: eine neue Konstante ist kein Befund,
#: eine geaenderte schon). Seit dem naechsten Integrationsschritt ist
#: "Buehne" ein echter Tab von Karte W (``web_vereint.seite``, eigenes
#: ``<section class="panel panel-buehne">``, ueber ``scope_css`` eingehaengt)
#: statt eines eigenen Umschalters -- hier steht nur noch, wie der Inhalt
#: DRINNEN aussieht, keine Tab-/Sichtbarkeitsregeln mehr.
#: Die CoThinker-Tafel (Task 1, Padua CoThinker-Tab clean, 03.10.2026):
#: EINE Karte auf einmal, gross gesetzt, mit Browser-seitigem Verlauf
#: (siehe ``_buehne_html``/``_VEREINT_JS`` fuer die Portierung aus
#: ``cothinker/stage/stage.py``). Ersetzt die gestapelte Kartenliste samt
#: Stueckkarte-Streifen (``.stueckkarte``/``.sk-*``/``.karte``/``.hoert-zu``
#: sind damit Geschichte -- eine Retheming-Karte (``wt/t_cc4306db``) fasst
#: diese neuen Regeln spaeter an, nicht ``.karte`` selbst). Nur Theme-Token
#: aus ``web_gestalt.TOKENS``, keine neuen Hexfarben.
_CSS_BUEHNE = """
#buehne-panel { display: flex; flex-direction: column; gap: .9rem;
                padding: .4rem 0 1.2rem; }
#buehne-status { margin: 0; font-size: .95rem; color: var(--text-leise); }
/* Typografie laut Karte: >= 1.15rem auf Telefonbreite, eine Zeilenlaenge,
   die nicht Kante an Kante laeuft, viel Weissraum, Kontrast aus dem
   Token-Paar (text, grund-2) -- bereits in web_gestalt.KONTRAST gefuehrt. */
#buehne-tafel { font-size: 1.15rem; line-height: 1.55;
                max-width: 34rem; margin: 0 auto; width: 100%;
                box-sizing: border-box; padding: 1.1rem 1.2rem;
                background: var(--grund-2); border: 1px solid var(--rand);
                border-radius: var(--radius-gross); color: var(--text); }
#buehne-tafel .buehne-alter { display: block; margin-top: .7rem;
                               font-size: .8rem; color: var(--text-leise); }
#buehne-tafel p { margin: 0 0 .7rem; }
#buehne-tafel p:last-of-type { margin-bottom: 0; }
#buehne-tafel ul { margin: 0 0 .7rem 1.1rem; padding: 0; }
#buehne-tafel li { margin: 0 0 .3rem; }
#buehne-tafel li:last-child { margin-bottom: 0; }
#buehne-tafel .buehne-ueberschrift { margin-top: .9rem; }
#buehne-tafel .buehne-ueberschrift:first-child { margin-top: 0; }
/* Die Navigation: Inhalt kommt IMMER aus JS (male()-Aequivalent), das
   leere Element ist hier nur der Platzhalter. Tippflaechen >= 44px. */
#buehne-nav { display: flex; align-items: center; justify-content: center;
              gap: .6rem; flex-wrap: wrap; font-size: .9rem;
              color: var(--text-leise); }
#buehne-nav button { min-width: 44px; min-height: 44px; font-size: 1.2rem;
                      line-height: 1; border: 1px solid var(--rand);
                      border-radius: var(--radius); background: var(--grund-2);
                      color: var(--signal); }
#buehne-nav button:disabled { opacity: .35; }
#buehne-nav a[data-v="live"] { color: var(--signal); }
#buehne-nav .neu { color: var(--warn); }
.buehne-leer { color: var(--text-leise); margin: 1rem 0; }
/* Die Stueckkarte: ein fester Streifen ueber den Karten -- Setting, Figuren,
   Geschichte mit Haken/offen, dazu die freien Festlegungen aus demselben
   Datentopf wie der Abschnitt "Festlegungen" weiter unten (kein zweiter
   Lesevorgang, siehe web_daten.stueckkarte_felder). */
.stueckkarte { display: flex; flex-wrap: wrap; gap: .4rem; margin: 0 0 1rem;
               padding: .5rem .6rem; background: #f2ede1; border-radius: .5rem; }
.sk-feld { font-size: .85rem; white-space: nowrap; }
.sk-haken { opacity: .6; margin-right: .15rem; }
.sk-frei { font-size: .85rem; opacity: .75; }
/* Die Karten: neueste oben und gross, aeltere kleiner und ausgegraut
   darunter (Brief: "large type, the newest card on top"). */
#buehne-panel .karte { background: #fff; border: 1px solid #e6e1d6;
                       border-radius: .5rem; padding: .8rem .9rem;
                       margin: 0 0 .7rem; font-size: 1.08rem;
                       white-space: pre-wrap; }
#buehne-panel .karte.alt { font-size: .85rem; opacity: .6; padding: .5rem .7rem; }
#buehne-panel .karte .zeit { display: block; margin-top: .3rem; }
/* Der ruhige Hinweis, wenn der juengste Versuch ein Schweigen war (Karte
   Padua Brainstorm, 03.10.2026) -- gedaempft wie ".leer", aber ohne ihren
   Platz zu beanspruchen: er steht VOR einer noch stehenden letzten Karte. */
#buehne-panel .hoert-zu { opacity: .55; font-style: italic; font-size: .95rem;
                          margin: 0 0 .7rem; }
/* Die CoThinker-Statuszeile UEBER dem Panel (Karte CoThinker-Statuszeile,
   03.10.2026; Theme-Token-Nachbesserung fuer t_cc4306db, 04.10.2026) -- nur
   Farb-Tokens aus ``web_gestalt.FARBTOKENS`` (``:root``, immer ueber
   ``web_gestalt.css_rahmen()`` auf derselben Seite vorhanden, siehe
   ``web_vereint.seite()``), KEIN rohes Hex hier. ``--warn`` traegt im
   bestehenden ``KONTRAST``-Vertrag schon die Bedeutung "laufender Zustand
   in der Karte" (siehe web_gestalt.KONTRAST) -- das ist wortgleich der
   "denkt"-Zustand hier, deshalb kein neuer Ton. Die eigentliche Animation
   (``@keyframes``) steht ungescopt in ``CSS_COTHINKER_KEYFRAMES``, siehe
   dort. Genau eine Zeile, nie zwei: ``flex-wrap: nowrap`` am Rahmen,
   ``text-overflow: ellipsis`` am Text -- ``min-width: 0`` ist der
   Flexbox-Kniff, ohne den ein Flex-Kind nicht unter seine Inhaltsbreite
   schrumpft und das Abschneiden nie greift. */
#cothinker-status { display: flex; align-items: center; gap: .5rem;
                     flex-wrap: nowrap; margin: 0 0 .6rem;
                     padding: .4rem .6rem; border-radius: .5rem;
                     background: var(--grund-2); color: var(--text);
                     font-size: .9rem; min-width: 0; }
#cothinker-status .co-icon { width: .6rem; height: .6rem;
                              border-radius: 50%; background: currentColor;
                              flex: 0 0 auto; }
#cothinker-status.co-hoert, #cothinker-status.co-transkribiert { color: var(--signal); }
#cothinker-status.co-denkt { color: var(--warn); }
#cothinker-status.co-schweigt { color: var(--text-leise); opacity: .75; }
#cothinker-status .co-text { overflow: hidden; text-overflow: ellipsis;
                              white-space: nowrap; min-width: 0; }
#cothinker-status .co-dauer { font-variant-numeric: tabular-nums; opacity: .75;
                               white-space: nowrap; flex: 0 0 auto; }
#cothinker-status.co-hoert .co-icon,
#cothinker-status.co-transkribiert .co-icon { animation: co-atmen 1.8s ease-in-out infinite; }
#cothinker-status.co-denkt .co-icon { animation: co-punkte 1.2s steps(3, end) infinite; }
"""

#: Die ``@keyframes`` der CoThinker-Statuszeile -- EIGENE, UNGESCOPTE
#: Konstante (03.10.2026). ``web_vereint.scope_css()`` versteht ``@media``,
#: aber nicht ``@keyframes``: ihre Regex haette ``50% { ... }`` faelschlich
#: als verschachtelten Selektor gelesen und zu z. B. ``.panel-buehne 50%``
#: verunstaltet (derselbe dokumentierte Fehler wie bei ``web_gestalt.py``s
#: eigenem ``scope_css``, siehe docs/agents/weboberflaeche.md "``@keyframes`` und ``@media`` nur
#: in ``css_rahmen()``"). Deshalb geht diese Konstante in
#: ``web_vereint.seite()`` ROH in die CSS-Verkettung ein, genau wie
#: ``_CSS_VEREINT`` -- niemals durch ``scope_css()``.
CSS_COTHINKER_KEYFRAMES = """
@keyframes co-atmen { 0%, 100% { opacity: .4; transform: scale(.85); }
                       50% { opacity: 1; transform: scale(1); } }
@keyframes co-punkte { 0% { opacity: .25; } 50% { opacity: 1; }
                        100% { opacity: .25; } }
@media (prefers-reduced-motion: reduce) {
  #cothinker-status .co-icon { animation: none !important; }
}
"""


#: Die Leitfaden-Ansicht (06.09.2026): gross gesetzt, hoher Kontrast, für ein
#: Telefon in der Hand -- und für ein Blatt Papier. Kein gemeinsames CSS mit
#: der Gruppenseite: dort geht es ums Überblicken, hier ums Vorlesen im
#: Stehen, vor einer fremden Person.
_CSS_LEITFADEN = """
body { background: #ffffff; color: #000000; font-size: 1.25rem;
       max-width: 34rem; margin: 0 auto; padding: 1.2rem 1.2rem 4rem;
       line-height: 1.5; }
h1 { font-size: 1.35rem; margin: 0 0 1.4rem; font-weight: 600; }
h2 { font-size: 1.05rem; margin: 2rem 0 .5rem; text-transform: uppercase;
     letter-spacing: .06em; border: 0; opacity: .65; }
.block { border-top: 3px solid #000; padding-top: .8rem; margin-top: 1.6rem; }
.frage { border-top: 2px solid #000; padding: 1rem 0 .2rem;
         margin-top: 1.4rem; }
.frage .nummer { font-size: .95rem; font-weight: 700; opacity: .55;
                 display: block; margin-bottom: .3rem; }
.frage p { margin: 0; font-size: 1.35rem; }
.frage .kern, .frage .vorher { font-size: 1rem; margin-top: .6rem;
                               opacity: .75; }
.frage .vorher { border-left: 4px solid #000; padding-left: .7rem;
                 opacity: .85; }
.sagen { font-size: 1.2rem; white-space: pre-wrap; margin: 0; }
.leer { font-size: 1.15rem; opacity: .7; }
.zurueck { display: block; margin-top: 3rem; font-size: .95rem; opacity: .6; }
@media print {
  /* Ausgedruckt gehört das Blatt der Gruppe: keine Navigation, kein
     Grauschleier, und jede Frage bleibt auf einer Seite zusammen. */
  body { font-size: 12pt; max-width: none; padding: 0; }
  .zurueck { display: none; }
  h2, .frage .nummer, .frage .kern { opacity: 1; }
  .frage, .block { page-break-inside: avoid; }
}
/* Die Festlegungen: eine Zeile je Eintrag, die Bereichsmarke davor. Ohne
   Kasten und ohne Aufklappen -- sie sollen gelesen werden, nicht geoeffnet. */
.festlegung { display: flex; flex-wrap: wrap; align-items: baseline;
              gap: .1rem .5rem; padding: .3rem 0;
              border-top: 1px solid #eee7d8; }
.festlegung:first-child { border-top: none; }
.festlegung .marke { font-size: .72rem; opacity: .6; text-transform: uppercase;
                     letter-spacing: .04em; }
.festlegung .feld { flex: 0 0 auto; }
"""


# --- Die sichtbaren Texte der Gruppenseite, Probenansicht, Leitfaden-Seite --
#
# Karte A1 (Aufgabe 17): die deutschen Konstanten SIND die deutsche Tabelle,
# die englische steht in ``sprachen/en/texte.toml`` unter ``["web"]``. Gelesen
# wird ueber ``T`` zur Aufrufzeit -- ein Web-Prozess bedient alle Gruppen, ein
# beim Import eingefrorener Text waere der falsche Workshop. **Nicht** hier:
# die Texte des Team-Dashboards (``dashboard_html``) -- es haengt am Beamer,
# ist fuer das Team und bleibt deutsch (``INLINE_ERLAUBT`` in
# ``tests/test_sprache_texte.py``).

#: Die Beschriftungen im Arbeitsstand (``<dt>``), je Feld.
ARBEITSSTAND_BESCHRIFTUNG = {
    "phase": "Phase",
    "begriffe": "Begriffe",
    "fragen": "Fragen",
    "leitfaden": "Leitfaden",
    "kernthema": "Kernthema",
    "rahmen": "Setting",
    "geschichte": "Geschichte",
    "hauptkonflikt": "Hauptkonflikt",
    "figuren": "Figuren",
    "format": "Format",
    "formen_nah": "Nahe Formen",
}

#: Die Beschriftungen aus ``web_daten.SZENENFELDER`` (K4: deutsch auf sich
#: selbst abgebildet). ``web_daten`` bleibt ohne Sprachzugriff -- es liefert
#: Daten, beschriftet wird hier.
SZENENFELD_BESCHRIFTUNG = {
    "Form": "Form",
    "Form (Vorschlag)": "Form (Vorschlag)",
    "Stil": "Stil",
    "Ort": "Ort",
    "Zeit": "Zeit",
    "Anlass": "Anlass",
    "Was passiert": "Was passiert",
    "Was anders ist": "Was anders ist",
    "Kernsätze": "Kernsätze",
    "Ton": "Ton",
}

#: Wie eine Form auf der Seite heisst. Der Schluessel ist der Datenbankwert
#: (Protokoll, ``szene.form``), der Wert die Anzeige -- deutsch der Wert
#: selbst, damit Dortmund zeigt, was es immer zeigte. Das Dropdown setzt ihn
#: mit ``capitalize()`` (wie ``knoepfe.biete_szenenform``).
#:
#: **Eine zweite Liste neben ``workshop.form_anzeige``**: die Schluessel sind
#: die fuenf Formen der Vorgabe. Ein Profil mit einer anderen Formenliste
#: zieht hier nicht nach -- eine unbekannte Form bleibt als Rohwert stehen
#: (``_form_anzeige``). Fuer Padua haelt
#: ``tests/test_web_sprache.py::test_web_formnamen_passen_zum_profil`` beide
#: Listen gleich (Aufgabe 29); offen fuer Aufgabe 32: diese Tabelle aus dem
#: Profil speisen oder durch ``workshop.form_anzeige`` ersetzen.
FORM_BESCHRIFTUNG = {
    "dialog": "dialog",
    "monolog": "monolog",
    "chor": "chor",
    "lied": "lied",
    "rap": "rap",
}

#: Wie eine Journalart als Marke heisst -- Schluessel ist der Datenbankwert
#: (``repo.schreibe_journal``), deutsch der Wert selbst.
JOURNALART_BESCHRIFTUNG = {
    "vorgeschlagen": "vorgeschlagen",
    "verworfen": "verworfen",
    "entschieden": "entschieden",
    "offen": "offen",
    "notiert": "notiert",
}

#: Wie der Bereich einer Festlegung als Marke heisst -- Schluessel ist der
#: Datenbankwert (``repo.FESTLEGUNG_BEREICHE``, Protokoll), deutsch der Wert
#: selbst (K4). ``web`` importiert ``repo`` nicht; ein Test haelt die
#: Schluessel deckungsgleich.
#:
#: Abnahme-Befund A13/laptop-A1 (06.10.2026): zusaetzlich ``rahmen`` -- kein
#: Bereich aus ``repo.FESTLEGUNG_BEREICHE`` (das Setting hat mit
#: ``arbeitsstand.rahmen`` schon ein Zuhause, repo.py:3441-3449), aber ein
#: Modell loest "If none fits, use a short word of your own" bei
#: ``festlegung_setzen`` manchmal mit genau diesem Wort ein -- es steht
#: GROSSBUCHSTABEN in derselben Protokollliste, nur fuer ``entfernen``
#: (sprachen/en/prompts/erkenner.md Punkt 20). Gemessen:
#: ``festlegung.bereich='RAHMEN'``.
FESTLEGUNG_BEREICH_BESCHRIFTUNG = {
    "figur": "figur",
    "gruppe": "gruppe",
    "ort": "ort",
    "struktur": "struktur",
    "form": "form",
    "stil": "stil",
    "sonstiges": "sonstiges",
    "rahmen": "rahmen",
}

#: Wie eine Pruefkennung der Dramaturgie-Pruefung als Marke heisst --
#: Schluessel ist ``dramaturgie_befund.pruefung`` (die Judge-Fragen aus
#: ``fanout.PROMPTS`` und die mechanischen Pruefungen aus ``mechanik``, alle
#: in ``fanout.EBENEN``), deutsch der Wert selbst (K4).
PRUEFUNG_BESCHRIFTUNG = {
    "a2": "a2",
    "a6": "a6",
    "a9": "a9",
    "a10": "a10",
    "a11": "a11",
    "b1": "b1",
    "c1": "c1",
    "namensstabilitaet": "namensstabilitaet",
    "geisterfigur": "geisterfigur",
    "erstauftritt": "erstauftritt",
    "figur_ohne_auftritt": "figur_ohne_auftritt",
    "fokus": "fokus",
    "besetzung_stumm": "besetzung_stumm",
    "besetzung_fremd": "besetzung_fremd",
    "formverteilung": "formverteilung",
    "form_regel": "form_regel",
    "tschechow": "tschechow",
    "sprechanteil": "sprechanteil",
}

TEXT_SPEICHERN = "Speichern"
TEXT_ENTFERNEN = "Entfernen"
_TEXT_EIGENE = "eigene …"
_TEXT_EIGENE_FORMULIERUNG = "eigene Formulierung"
_TEXT_OHNE_BESCHREIBUNG = "ohne Beschreibung"
_TEXT_SPRECHWEISE_AUS = "Sprechweise aus {quelle}"
_TEXT_SPRICHT_AUS = "Spricht aus"
_TEXT_KEIN_INTERVIEW = "— kein Interview —"
_TEXT_NOCH_OFFEN = "— noch offen —"
_TEXT_OFFEN = "— offen —"
_TEXT_OHNE_STIL = "— ohne Stilvorlage —"
_TEXT_OHNE_TITEL = "ohne Titel"
#: Ein woertliches Zitat in Anfuehrungszeichen der Sprache.
_ZITAT = "„{zitat}“"
_TEXT_KEINE_FIGUREN = "Noch keine Figuren."
_TEXT_KEINE_FIGUR = "Noch keine Figur."
_TEXT_NOCH_KEINE = "noch keine"
_TEXT_SCHAERFUNG = "Schärfung"
_TEXT_SZENE = "Szene"
_TEXT_SZENE_NR = "Szene {nummer}"
_UEBERSCHRIFT_DRAMATURGIE = "Dramaturgie-Prüfung"
_TEXT_DRAMATURGIE_RUNDE = "Runde {runde}, {anzahl} Befunde. Entschieden wird im Chat."
_TEXT_KEINE_FESTLEGUNGEN = "Noch nichts festgehalten, was in kein Feld passt."
_PLATZ_SETTING = "Ort, Zeit, Anlass"
_PLATZ_GESCHICHTE = "was passiert, wie es endet"
_PLATZ_NEUE_FIGUR = "Name der neuen Figur"
_TEXT_FIGUR_HINZU = "Figur hinzufügen"
#: Die Spaltenkoepfe der Sprechanteile: Figur, Anteil, Repliken, Szenen.
_SPRECHANTEILE_KOEPFE = ("Figur", "Anteil", "Repliken", "Szenen")
_TEXT_EIN_TEIL = "1 Teil"
_TEXT_TEILE = "{anzahl} Teile"
_TEXT_WER = "Wer"
_TEXT_VORSCHLAG = "Vorschlag: {form}"
_TEXT_KURZ = "Kurz"
_TEXT_ZUSAMMENFASSUNG = "Zusammenfassung"
_TEXT_ALS_GESCHICHTE = "Als Geschichte"
_TEXT_GEPLANT = "Noch kein Text — die Szene ist geplant."
_TEXT_FASSUNG_NR = "Fassung {nummer}"
_TEXT_N_FASSUNGEN = "{anzahl} Fassungen"
_TEXT_FASSUNG_VON = "Fassung {nummer} von {gesamt}"
_TEXT_DIE_AKTUELLE = "die aktuelle"
_TEXT_VORIGE_FASSUNG = "← vorige Fassung ({nummer})"
#: Die Spaltenkoepfe der Szenenuebersicht.
_UEBERSICHT_KOEPFE = ("Nr.", "Szene", "Form", "Stil", "Text", "Fassungen")
_TEXT_ALS_VORSCHLAG = "{form} (Vorschlag)"
_TEXT_UMFANG_PROSA = "Prosa {zeichen} Z."
_TEXT_UMFANG_TEXT = "Text {zeichen} Z."
_TEXT_KEIN_TEXT = "noch kein Text"
_TEXT_INTERVIEW = "Interview"
_TEXT_NICHT_VERDICHTET = "Noch nicht verdichtet."
_TEXT_KEINE_SZENE = "Noch keine Szene. Die entstehen in der letzten Phase."
_TEXT_KEIN_INTERVIEW_NOCH = (
    "Noch kein Interview — sagt „wir machen jetzt ein Interview“ und "
    "sprecht drauflos."
)
_TEXT_NICHTS_NOTIERT = "Noch nichts notiert."
_TEXT_GRUPPE = "Gruppe {chat_id}"
_TITEL_GRUPPENSEITE = "{titel} — interview-theater"
_UEBERSCHRIFT_UEBERBLICK = "Überblick"
_UEBERSCHRIFT_ARBEITSSTAND = "Arbeitsstand"
#: Padua-Brainstorming-Umbau (02.10.2026): die Stueckkarte -- die vier
#: festen Phase-4-Felder mit ✓/„offen", direkt ueber den freien
#: Festlegungen. ``_STUECKKARTE_*`` sind die Feldnamen, nicht Nutzertext im
#: engeren Sinn, aber ebenfalls uebersetzt (K3).
_UEBERSCHRIFT_STUECKKARTE = "Stückkarte"
_STUECKKARTE_SETTING = "Setting"
_STUECKKARTE_FIGUREN = "Figuren"
_STUECKKARTE_GESCHICHTE = "Geschichte"
_STUECKKARTE_SZENENANZAHL = "Anzahl Szenen"
_TEXT_STUECKKARTE_OFFEN = "offen"
_UEBERSCHRIFT_FESTLEGUNGEN = "Weitere Festlegungen"
_UEBERSCHRIFT_SZENEN = "Szenen"
_UEBERSCHRIFT_INTERVIEWS = "Aus den Interviews"
_UEBERSCHRIFT_WEG = "Der Weg dahin"
_TEXT_JOURNAL = "Journal ({anzahl})"
# --- Die read-only Werkbank (Padua, 03.10.2026) ----------------------------
_TEXT_WERKBANK_HINWEIS = "Etwas ändern? Sagt es einfach dem Bot im Chat."
_TEXT_WERKBANK_ZAHL = "{erledigt} von {gesamt}"
_TEXT_STATUS_ERLEDIGT = "erledigt"
_TEXT_STATUS_OFFEN = "offen"
_TEXT_STATUS_SPAETER = "später"
_TEXT_WERKBANK_LAEUFT = "läuft"
_TEXT_WB_DISKUSSION = "Diskussion zusammengefasst"
_TEXT_WB_INTERVIEW_FERTIG = "{bezug}: aufgenommen, ausgewertet"
_TEXT_WB_INTERVIEW_OFFEN = "{bezug}: aufgenommen, noch nicht ausgewertet"
_TEXT_WB_PROSA = "Szene {bezug}: Prosa"
_TEXT_WB_GESAMTTEXT = "Rückmeldung zum ganzen Text"
_TEXT_WB_UEBERARBEITET = "Szene {bezug}: überarbeitet"
_TEXT_WB_FORM = "Szene {bezug}: Form"
_TEXT_WB_SPRECHWEISE = "{bezug}: Sprechweise"
_TEXT_WB_AUCH_VEREINBART = "Auch vereinbart"
_TEXT_WERKBANK_NUR_LESEN = "Hier wird nur angezeigt – Änderungen bitte im Chat."
#: Der Recherche-Abschnitt der Werkbank (Karte t_c5117c91) -- ein eigener,
#: von den sieben Phasen unabhaengiger Abschnitt unter dem Journal: eine
#: Internet-Recherche gehoert zu keiner Phase und ist klar vom
#: Interviewmaterial getrennt (derselbe Grundsatz wie kontext.RECHERCHE_KOPF).
_UEBERSCHRIFT_RECHERCHE = "Recherche aus dem Internet (kein Interviewmaterial)"
_TEXT_RECHERCHE_LEER = "Noch keine Recherche."
_TEXT_RECHERCHE_QUELLEN = "Quellen: {quellen}"
#: Der Buehne-Inhalt (Phase 4, nur Web, 02.10.2026). Die Tab-Beschriftung
#: selbst steht seit dem Umzug in Karte Ws Tableiste in
#: ``web_vereint._TEXT_TAB["buehne"]``, nicht mehr hier.
#:
#: Task 1 (Padua CoThinker-Tab clean, 03.10.2026): der leere Zustand nennt
#: jetzt eine konkrete Handlung statt nur den Mangel ("Noch keine Karte.")
#: zu melden -- der Chat ist der einzige Weg, wie eine erste Karte entsteht.
_TEXT_BUEHNE_LEER = "Im Chat sprechen — hier erscheinen die Gedanken."
#: Das Begriffsboard im CoThinker-Tab (Phase 1, Karte t_4517d4ad).
_TEXT_BOARD_LEER = "Hier erscheinen die Begriffe, die ihr in der Diskussion nennt."
#: Die Fragenuebersicht im CoThinker-Tab (Phase 2, Birk 05.10.2026) -- ohne
#: Soll-Zahl: wie viele Fragen ein Begriff bekommt, entscheidet die Gruppe.
_TEXT_FRAGEN_UEBERSICHT_KOPF = "Eure Fragen"
_TEXT_FRAGEN_UEBERSICHT_LEER = "Hier erscheinen eure Fragen, je Begriff."
_TEXT_FRAGEN_UEBERSICHT_OFFEN = "noch keine Frage"
#: Die Auswahlliste im CoThinker (Padua Phase 2, 05.10.2026): je Frage
#: ✓/✗/✎, ein Zaehler und "Fertig sortiert" (``_auswahlliste_html``).
_TEXT_AUSWAHL_ZAEHLER = "{ja} behalten · {nein} weg · {schaerfen} umformulieren · {offen} offen"
_TEXT_AUSWAHL_EIGEN = "eigene"
_TEXT_AUSWAHL_KI = "KI"
_TEXT_AUSWAHL_JA = "Behalten"
_TEXT_AUSWAHL_NEIN = "Weg"
_TEXT_AUSWAHL_SCHAERFEN = "Umformulieren"
_TEXT_AUSWAHL_FERTIG = "Fertig sortiert – offene zählen als behalten"
#: Die Schaerfungs-Sortierliste im CoThinker (Padua Phase 5, 07.10.2026,
#: "Show more" war unsinnig): Yes/No statt der drei Zustaende der
#: Fragenliste, darum ein eigener Zaehlertext und eigene Knopfbeschriftungen
#: (``_schaerfungsliste_html``).
_TEXT_SCHAERFUNGSLISTE_ZAEHLER = "{ja} dabei · {nein} weg · {offen} offen"
_TEXT_SCHAERFUNGSLISTE_JA = "Dabei"
_TEXT_SCHAERFUNGSLISTE_NEIN = "Weg"
_TEXT_SCHAERFUNGSLISTE_FERTIG = "Fertig – offene bleiben für die nächste Runde"
_TEXT_SCHAERFUNGSLISTE_SZENE = "Szene {nummer}"
_TEXT_SCHAERFUNGSLISTE_ERKLAERUNG = ("Die stärksten Interviewstellen je Szene und Figur. "
    "Dabei = die Idee (→) geht in die Beschreibung ein, das Zitat wird Bezugssatz für den Text.")
_TEXT_SCHAERFUNGSLISTE_ANZAHL = "{anzahl} Vorschläge"
#: Nachtrag Karte Padua Brainstorm (03.10.2026): steht statt/vor der letzten
#: Karte, wenn der juengste Versuch ein bewusstes Schweigen war
#: (``buehnenkarte.schweigen = 1``) -- eine leere Flaeche liess nicht
#: erkennen, ob das Mithoeren ueberhaupt laeuft.
_TEXT_BUEHNE_HOERT_ZU = "Hört zu … bisher nichts beizutragen."
#: Task 1: die zweite, bewusst ANDERS formulierte Statuszeile -- eine
#: laufende/wartende Aufnahme (``aufnahme.status in ('empfangen','laeuft')``)
#: ist ein anderer Zustand als "das Modell hat zugehoert und nichts
#: beizutragen" oben, und beide duerfen auf der Tafel nicht gleich klingen
#: (siehe Report, Abschnitt "Zwei verschiedene 'hört zu'").
_TEXT_BUEHNE_AUFNAHME_LAEUFT = "Eine Aufnahme läuft gerade."
#: Der "zurueck zur aktuellen Ansicht"-Baustein der Verlaufsleiste --
#: INKLUSIVE des eigenen Gedankenstrichs, die JS haengt ihn nur noch ans
#: Ende der Zaehler-Anzeige (``_VEREINT_JS`` traegt dafuer selbst keinen
#: Nutzertext, siehe ``tests/test_sprache_texte.py``).
_TEXT_BUEHNE_ZURUECK = " — zurück zur aktuellen Ansicht"
#: Das Praefix vor der Vorschau einer neu eingetroffenen Karte, waehrend
#: wer zurueckgeblaettert hat liest -- nie ein Sprung, nur ein Hinweis
#: (siehe Brief/Referenz ``cothinker/stage/stage.py``, ``male()``).
_TEXT_BUEHNE_NEU_PRAEFIX = "neu: "
#: Die gedaempfte Alterszeile der Tafel -- nur ab 5 Minuten, siehe
#: ``_buehne_alterszeile``.
_TEXT_BUEHNE_ALTER = "vor {minuten} Min."
_TEXT_BUEHNE_OFFEN = "offen"
#: Die CoThinker-Statuszeile ueber dem Buehne-Panel (Karte CoThinker-
#: Statuszeile, 03.10.2026) -- ein Text je ``cothinker_status.ZUSTAND_*``.
_TEXT_COTHINKER_HOERT = "hört zu"
_TEXT_COTHINKER_TRANSKRIBIERT = "verschriftlicht"
_TEXT_COTHINKER_DENKT = "denkt nach"
_TEXT_COTHINKER_SCHWEIGT = "zugehört, gerade nichts hinzuzufügen"
#: Was das Speichern auf der Gruppenseite neben dem Feld meldet. Das
#: JavaScript liest sie aus ``data-``-Attributen (``_BEARBEITEN_JS``), damit
#: kein Nutzertext im Skript steht.
_JS_SICHER = "Wirklich entfernen?"
_JS_SPEICHERT = "speichert …"
_JS_GESPEICHERT = "gespeichert"
_JS_FEHLER = "ging nicht"
# Probenansicht
_TEXT_STUECK_LEER = "Noch keine Szene — hier steht das Stück, sobald es eine gibt."
_TITEL_PROBENANSICHT = "{titel} — Probenansicht"
_TEXT_ZUM_ARBEITSSTAND = "‹ Arbeitsstand"
_TEXT_TEXTBUCH_MD = "Textbuch .md"
_TEXT_TEXTBUCH_TXT = "Textbuch .txt"
_TEXT_SCHRIFT = "Schrift"
_TEXT_SCHRIFT_KLEIN = "klein"
_TEXT_SCHRIFT_MITTEL = "mittel"
_TEXT_SCHRIFT_GROSS = "groß"
_TEXT_REGIE_AUS = "Regieanweisungen ausblenden"
_TEXT_DRUCKEN = (
    "Zum Ausdrucken: die Druckfunktion des Browsers — je Szene eine Seite, "
    "ohne Leisten und Farben."
)
_TEXT_ROLLE = "Rolle"
_TEXT_ALLE = "alle"
_TEXT_BESETZUNG = "Besetzung: {figuren}"
_TEXT_ALS_GESCHICHTE_DOPPELPUNKT = "Als Geschichte:"
# Zweisprachiges Textbuch (Birk, Live-Workshop 07.10.2026 ~17:20,
# Padua-Profilschalter [skript] zweisprachig): nur sichtbar, wenn eine
# Szene ``prosa_it`` traegt -- sonst bleibt es bei der einsprachigen
# Zeile oben.
_TEXT_ALS_GESCHICHTE_EN = "Als Geschichte (Englisch):"
_TEXT_ALS_GESCHICHTE_IT = "Als Geschichte (Italienisch):"
_TEXT_KERNSAETZE_IT = "Kernsätze (italienisches Original):"
# Leitfaden-Seite
_TITEL_LEITFADEN = "Leitfaden — {titel}"
_TEXT_VORHER_SAGEN = "Vorher sagen: {text}"
_TEXT_KERN = "Kern: {text}"
# Fehlerseiten und Fehlermeldungen
_TITEL_NICHT_GEFUNDEN = "Nicht gefunden"
_TEXT_NICHT_GEFUNDEN = "Diese Adresse gibt es nicht. Fragt im Workshop nach dem Link."
_TEXT_DB_NICHT_LESBAR = "Die Datenbank ist gerade nicht lesbar."
_TEXT_DB_NICHT_BESCHREIBBAR = "Die Datenbank ist gerade nicht beschreibbar."
_TEXT_SEITE_VERALTET = "Die Seite ist veraltet — bitte einmal neu laden."
_TEXT_UNGUELTIG = "Ungültige Anfrage."
_TEXT_LEER_ANFRAGE = "Leere Anfrage."
_TEXT_ZU_LANG = "Der Text ist zu lang."


def _t(wert, ersatz: str = "—") -> str:
    """Maskiert einen Wert aus der Datenbank fuer HTML.

    ALLES aus der Datenbank laeuft hier durch: Gruppentitel, Figurennamen und
    Szenentexte kommen aus Telegram und aus einem Sprachmodell, beides sind
    fremde Eingaben. ``None`` und Leerstrings werden zum Ersatzzeichen, damit
    im Dashboard kein 'None' steht."""
    if wert is None or wert == "":
        return ersatz
    return html.escape(str(wert))


def _zeitpunkt(iso: str | None) -> str:
    """Formatiert einen UTC-Zeitstempel als Ortszeit 'TT.MM. HH:MM'.

    In der Datenbank steht UTC; auf dem Beamer soll die Uhrzeit im Raum
    stehen. Laesst sich der Wert nicht lesen, wird er maskiert
    durchgereicht -- eine unerwartete Schreibweise ist kein Grund, die Seite
    scheitern zu lassen."""
    if not iso:
        return "—"
    gelesen = web_daten.lies_zeitstempel(iso)
    if gelesen is None:
        return html.escape(str(iso))
    return gelesen.astimezone().strftime("%d.%m. %H:%M")


def _sekunden(millisekunden: int | None) -> str:
    """Millisekunden als Sekunden mit dem Dezimalzeichen der Sprache --
    deutsch '5,1 s' ('5.1 s' liest sich dort falsch), englisch '5.1 s'.
    Einziger Aufrufer ist das Team-Dashboard."""
    if millisekunden is None:
        return "—"
    return f"{millisekunden / 1000:.1f}".replace(".", T._DEZIMALZEICHEN) + " s"


def _dauer(sekunden: int | None) -> str:
    """Eine Aufnahmedauer als 'M:SS' -- 'Interview 3 · 4 Teile · 12:07' sagt
    der Gruppe mehr ueber ihr Material als eine Zahl in Sekunden."""
    if not sekunden:
        return ""
    return f"{int(sekunden) // 60}:{int(sekunden) % 60:02d}"


def _zeitpunkt(iso: str | None) -> str:
    """Datum und Uhrzeit des Aufnahmebeginns (06.09.2026 14:00, Birk: neben
    der Nummer immer Datum, Uhrzeit und Dauer) -- lokale Zeit Europe/Berlin,
    als Praefix mit Trenner; leer, wenn unbekannt."""
    if not iso:
        return ""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=ZoneInfo("UTC"))
        lokal = t.astimezone(ZoneInfo("Europe/Berlin"))
        return f"{lokal.strftime('%d.%m.%Y %H:%M')} · "
    except (ValueError, TypeError):
        return ""


def _umfang(teile: int, sekunden: int | None) -> str:
    """Die Kopfzeile eines Interviews auf der Gruppenseite: aus wie vielen
    Sprachnachrichten es besteht und wie lang es insgesamt ist (§ 10.6).

    Ohne Teile (Textimport, Aufnahme aus der Zeit vor dem Nachtrag) bleibt die
    Teile-Zahl weg statt '0 Teile' zu behaupten."""
    stuecke = []
    if teile == 1:
        stuecke.append(T._TEXT_EIN_TEIL)
    elif teile > 1:
        stuecke.append(T._TEXT_TEILE.format(anzahl=teile))
    dauer = _dauer(sekunden)
    if dauer:
        stuecke.append(dauer)
    return " · ".join(stuecke)


def _seite(
    titel: str,
    css: str,
    koerper: str,
    bearbeitbar: bool = False,
    nachladen: bool = True,
    skript: str = "",
    lang: str | None = None,
    koerper_attribute: str = "",
) -> str:
    """Rahmen aller Seiten: ein einziges eingebettetes CSS, keine externe
    Ressource (der Workshopraum haengt an einem Tailnet, nicht am offenen
    Netz), sanftes Nachladen per fetch (siehe _SCROLL_JS) -- kein meta
    refresh mehr, der jedes aufgeklappte <details> wieder zuklappte.

    ``bearbeitbar`` haengt zusaetzlich ``_BEARBEITEN_JS`` an: nur die
    Gruppenseite bekommt es, das Dashboard nie.

    ``nachladen=False`` laesst das Nachladen ganz weg -- die Probenansicht
    (06.09.2026) braucht es nicht: sie ist ein Manuskript, das man liest und
    ausdruckt, und ein Austausch des ``<body>`` mitten in der Probe wuerde
    Rollenfilter und Schriftgroesse zuruecksetzen. ``skript`` haengt statt
    dessen das eigene JavaScript der Seite an.

    ``lang`` ist die Sprache der Seite -- ohne Angabe die des Profils (Karte
    A1). Seit Padua (02.10.2026) gilt das auch fuer das Team-Dashboard; es
    gibt keine Sprache mehr vor.

    ``koerper_attribute`` haengt zusaetzliche Attribute an ``<body>`` --
    bislang nur ``textbuch_html`` (``data-textbuch`` als Wurzel des
    Rollenfilters, Karte W)."""
    skripte = (
        _SCROLL_JS.replace("__NEULADEN_MS__", str(NEULADEN_SEKUNDEN * 1000))
        if nachladen
        else ""
    )
    if bearbeitbar:
        skripte += _BEARBEITEN_JS
    skripte += skript
    return (
        "<!doctype html>\n"
        f'<html lang="{html.escape(lang or sprache.code())}"><head><meta charset="utf-8">\n'
        f"{_VIEWPORT_META}\n"
        f"<title>{html.escape(titel)}</title>\n"
        f"<style>{_CSS_GEMEINSAM}{css}</style></head>\n<body{koerper_attribute}>\n"
        f"{koerper}\n"
        f"<script>{skripte}</script>\n"
        "</body></html>\n"
    )


def _fragen_html(fragen: str | None) -> str:
    """Eine Zeile je Frage, das Thema fett (Birk 04.09.: 'jede Frage eine
    eigene Zeile mit dem Thema der Frage fett gedruckt').

    Der Erkenner liefert die Fragen als einen String; getrennt wird an
    Zeilenumbruch oder ' | ', das Thema ist das, was vor dem ersten
    Doppelpunkt steht -- wenn es kurz genug ist, um ein Thema zu sein.
    Fehlt es, steht die Frage allein. Alles HTML-escaped."""
    if not fragen:
        return _t(None)
    teile = [t.strip(" -•") for t in re.split(r"\n+| \| ", fragen) if t.strip(" -•")]
    zeilen = []
    for teil in teile:
        thema, sep, frage = teil.partition(":")
        if sep and 0 < len(thema.strip()) <= 40 and frage.strip():
            zeilen.append(f"<li><b>{_t(thema.strip())}</b> {_t(frage.strip())}</li>")
        else:
            zeilen.append(f"<li>{_t(teil)}</li>")
    return "<ul class=\"fragen\">" + "".join(zeilen) + "</ul>"


#: Fast-Track 06.10.2026 ("so schnell wie möglich live"): die Fortschrittszeile
#: im Regie-Dashboard, waehrend eine Gruppe noch sortiert
#: (``auswahl.dashboard_fragen``, ``offen=True``).
_TEXT_FRAGEN_DASHBOARD_FORTSCHRITT = "Sortierung läuft · {kept} schon behalten"
_TEXT_FRAGEN_DASHBOARD_VORHER = "Sortierung läuft · noch nichts behalten – oben die bisherige Liste"


def _fragen_dashboard_html(g: dict, en: dict, uebersetzen: bool) -> str:
    """Alle ausgewaehlten Fragen des Regie-Dashboards (Fast-Track
    06.10.2026, ``auswahl.dashboard_fragen``): je Begriff eine Ueberschrift,
    darunter eine Liste mit der Nummer, die die Frage auch im Chat hat
    (``<li value>``, deshalb keine durchgehende Nummerierung je Liste),
    eigen/KI markiert. ``""`` ohne etwas zu zeigen.

    Waehrend die Sortierung noch laeuft, steht zusaetzlich eine
    Fortschrittszeile ("k schon behalten"). Englisch (``en``/``uebersetzen``):
    Fragetext und Ueberschrift je einzeln ueber ``uebersetzung.zeile_schluessel``/
    ``begriff_schluessel`` nachgeschlagen (Hash ueber den Inhalt, nicht die
    Position) -- funktioniert deshalb gleich in der offenen Sortierung, der
    geschlossenen Liste und im "bisherige Liste"-Rueckfall, unabhaengig von
    Reihenfolge oder Anzahl. Ohne Treffer bleibt die Zeile/Ueberschrift
    Original, markiert wie der Rest der Karte (``_en_oder_original``). Kein
    Modellaufruf hier (P2, Aufgabe 3 / § 6)."""
    from interview_theater import auswahl as _auswahl
    from interview_theater import uebersetzung

    stand = g["arbeitsstand"]
    fd = _auswahl.dashboard_fragen(stand)
    if not fd or not fd["gruppen"]:
        return ""

    def _frage_text(eintrag: dict) -> str:
        schluessel = uebersetzung.zeile_schluessel(eintrag["roh"])
        return _en_oder_original(en, schluessel, eintrag["text"], uebersetzen)

    marke = {"eigen": T._TEXT_AUSWAHL_EIGEN, "ki": T._TEXT_AUSWAHL_KI}
    teile = []
    for gruppe in fd["gruppen"]:
        if gruppe["titel"]:
            schluessel = uebersetzung.begriff_schluessel(gruppe["titel"])
            titel_html = _en_oder_original(en, schluessel, gruppe["titel"], uebersetzen)
            teile.append(f'<h4 class="fragen-begriff">{titel_html}</h4>')
        zeilen = []
        for eintrag in gruppe["eintraege"]:
            name = marke.get(eintrag["herkunft"])
            marke_html = (
                f'<span class="herkunft {eintrag["herkunft"]}">{_t(name)}</span>'
                if name else ""
            )
            zeilen.append(
                f'<li value="{eintrag["nummer"]}">{_frage_text(eintrag)}{marke_html}</li>'
            )
        teile.append(f'<ol class="fragen-gruppe">{"".join(zeilen)}</ol>')
    fortschritt_text = (T._TEXT_FRAGEN_DASHBOARD_VORHER if fd.get("vorher")
                        else T._TEXT_FRAGEN_DASHBOARD_FORTSCHRITT.format(kept=fd["kept"]))
    fortschritt = (
        f'<p class="fragen-fortschritt">{_t(fortschritt_text)}</p>'
        if fd["offen"] else ""
    )
    return f'<dd class="fragen-voll">{"".join(teile)}{fortschritt}</dd>'


#: Die Beschriftung des Links auf die große Ansicht. Als Konstante, damit
#: Test und Chat denselben Wortlaut prüfen können.
TEXT_LEITFADEN_LINK = "Groß und zum Ausdrucken"


def _leitfaden_link(token: str | None) -> str:
    """Der Link auf ``/g/<token>/leitfaden`` -- relativ, damit er hinter
    nginx genauso geht wie direkt auf Port 8010 (die Seite steht unter
    ``…/g/<token>``, also führt ``<token>/leitfaden`` eine Ebene tiefer)."""
    if not token:
        return ""
    return (
        f'<div class="zeit"><a href="{_t(token)}/{leitfaden_pfad()}">'
        f"{html.escape(T.TEXT_LEITFADEN_LINK)}</a></div>"
    )


#: Der Weg vom Lesen ins Arbeiten (30.09.2026): auf der Gruppenseite steht,
#: was entschieden ist -- im Chat entscheidet man. Relativ verlinkt, wie der
#: Leitfaden.
_TEXT_CHAT_LINK = "Chat mit dem Bot"


def _chat_link(token: str | None, kanal: str | None = None) -> str:
    """Nur fuer eine Gruppe im Web-Kanal (Abschlussreview I3). Der Plan
    (Aufgabe 6) sah den Link fuer jede Gruppe vor; E1 geht vor: eine
    Telegram-Gruppe hat keinen Bot, der den Web-Eingang liest, und was sie
    dort schriebe, ginge still verloren."""
    if not token or kanal != "web":
        return ""
    from interview_theater import web_chat

    return (
        f'<p><a href="{html.escape(token)}/{web_chat.CHAT_PFAD}">'
        f"{html.escape(T._TEXT_CHAT_LINK)}</a></p>"
    )


def leitfaden_pfad() -> str:
    """``leitfaden`` -- der Pfad steht in ``leitfaden.WEB_PFAD``, damit
    Routing und Link nicht auseinanderlaufen."""
    from interview_theater import leitfaden

    return leitfaden.WEB_PFAD


def _leitfaden_html(arbeitsstand: dict, token: str | None = None) -> str:
    """Der Gespraechsleitfaden als eigener Eintrag unter den Fragen -- oder
    gar nichts (06.09.2026).

    Read-only und ohne Werbung fuer sich selbst: steht kein Leitfaden, fehlt
    die Zeile ganz, statt als leere Aufgabe dazustehen (dieselbe Regel wie
    beim Hauptkonflikt). Der Text kommt aus ``leitfaden.aus_feldern`` -- der
    reinen Funktion, die auch der Chat benutzt, damit auf der Gruppenseite
    nichts anderes steht als auf dem Telefon. ``leitfaden`` selbst haengt an
    keinem Schreib-Lock, solange es nur diese Funktion ist.
    """
    from interview_theater import leitfaden

    text = leitfaden.aus_feldern(arbeitsstand)
    if text == leitfaden.T.TEXT_LEER:
        return ""
    return (
        f"<dt>{html.escape(T.ARBEITSSTAND_BESCHRIFTUNG['leitfaden'])}</dt><dd>"
        f'<pre class="leitfaden">{_t(text)}</pre>'
        # Der Link auf die große Ansicht (06.09.2026) -- zusätzlich, der Text
        # bleibt: wer hier liest, will überblicken; wer losgeht, braucht ihn
        # groß.
        f"{_leitfaden_link(token)}</dd>"
    )


def _fehlstellen_html(eintraege: list[dict] | None) -> str:
    """Der Abschnitt „Was noch fehlt" -- oder gar nichts (06.09.2026).

    **Nur, wenn es Fehlstellen gibt.** Eine Ueberschrift mit der Zeile
    „nichts fehlt" waere Laerm auf einer Seite, die sich alle zehn Sekunden
    selbst nachlaedt. Read-only, ohne Knopf: die Liste ist ein Vorschlag,
    keine Aufgabe, die man hier abhakt.

    Der Text kommt aus ``fehlstellen.aus_daten`` -- derselben Funktion, aus
    der auch ``/stand`` liest."""
    if not eintraege:
        return ""
    from interview_theater import fehlstellen

    zeilen = "".join(f"<li>{_t(e['text'])}</li>" for e in eintraege)
    return (
        f"<h2>{html.escape(fehlstellen.T.UEBERSCHRIFT)}</h2>"
        f'<ul class="fehlstellen">{zeilen}</ul>'
    )


def _fragen_auswertung_text(daten: dict | None) -> str | None:
    """"Fragen behalten: 2 eigene, 3 KI" -- oder ``None`` (Aufgabe 14).

    **Nur, wenn der A/B-Vergleich ueberhaupt Zahlen hergibt.** Lief er nie
    fuer diese Gruppe (klassischer Ablauf, oder ``workshop.
    fragen_ab_aktiv()`` aus), ist ``gesamt`` 0/0 -- eine Zeile "0 eigene,
    0 KI" waere Laerm wie "nichts fehlt" bei den Fehlstellen. Derselbe
    Schluessel ``fragen_auswertung`` wie im Dashboard (``web_daten.
    dashboard``) und auf der Gruppenseite (``web_daten.gruppe_nach_token``)."""
    if not daten:
        return None
    gesamt = daten.get("gesamt") or {}
    eigen, ki = gesamt.get("eigen", 0), gesamt.get("ki", 0)
    if not eigen and not ki:
        return None
    return _t(T._TEXT_FRAGEN_AUSWERTUNG).format(eigen=eigen, ki=ki)


def _fragen_auswertung_html(daten: dict | None) -> str:
    """Die Gruppenseite: ``_fragen_auswertung_text`` als eigener Absatz,
    oder gar nichts (dasselbe Prinzip wie ``_fehlstellen_html``)."""
    text = _fragen_auswertung_text(daten)
    return f"<p>{text}</p>" if text else ""


def _sprechanteile_html(daten: dict | None) -> str:
    """Wie viel jede Figur spricht -- Liste und Hinweiszeilen (06.09.2026).

    **Nur, wenn mindestens eine Szene zählbar war.** Konnte in keinem
    Szenentext eine Sprecherzeile erkannt werden (Lied, Rap, Chor), bleibt
    der Abschnitt weg -- eine Tabelle voller Nullen wäre eine Aussage, die
    die Zählung nicht deckt.

    Die Hinweiszeilen unter der Liste sind bewusst sachlich: die Zahl steht
    da, die Entscheidung gehört der Gruppe."""
    if not (daten or {}).get("szenen"):
        return ""
    from interview_theater import sprecher

    zeilen = "".join(
        "<tr><td>{name}</td><td>{anteil}</td><td>{repliken}</td>"
        "<td>{szenen}</td></tr>".format(
            name=_t(f["name"]),
            anteil=_t(sprecher._prozent(f["anteil"])),
            repliken=f["repliken"],
            szenen=f["szenen"],
        )
        for f in daten["figuren"]
    )
    leise = [f for f in daten["figuren"] if f["anteil"] < sprecher.SCHWELLE_ANTEIL]
    hinweise = "".join(
        f'<div class="hinweiszeile">{_t(sprecher.hinweis(f, daten["szenen"]))}</div>'
        for f in leise
    )
    koepfe = "".join(f"<th>{html.escape(k)}</th>" for k in T._SPRECHANTEILE_KOEPFE)
    return (
        f"<h2>{html.escape(sprecher.T.UEBERSCHRIFT)}</h2>"
        f'<table class="anteile"><tr>{koepfe}</tr>{zeilen}</table>'
        f"{hinweise}"
    )


def _figur_html(f: dict, mit_stimme: bool) -> str:
    """Eine Figur: Name, Beschreibung -- und auf der Gruppenseite zusaetzlich
    das Interview, aus dem sie spricht, ihr Sprachprofil und ihre woertlichen
    Zitate (05.09.2026).

    ``mit_stimme=False`` auf dem **Dashboard**: das haengt am Beamer, und ein
    woertlicher Satz aus einem Interview gehoert dort nicht hin -- dieselbe
    Grenze wie bei Nachrichtentext und Transkripten. Die Zitate selbst sind
    vor dem Speichern geprueft (``sprachprofil.erstelle``), stehen also unter
    derselben Zusage wie die Belegzitate der Verdichtungen: kein Satz in
    Anfuehrungszeichen, den niemand gesagt hat."""
    teile = [f"<b>{_t(f['name'])}</b> — {_t(f.get('beschreibung'), T._TEXT_OHNE_BESCHREIBUNG)}"]
    if f.get("quelle"):
        teile.append(f'<div class="zeit">{_sprechweise(f["quelle"])}</div>')
    if mit_stimme:
        if f.get("sprachprofil"):
            teile.append(f'<div class="profil">{_t(f["sprachprofil"])}</div>')
        for satz in f.get("zitate") or []:
            teile.append(f"<blockquote>{_zitat(satz)}</blockquote>")
    return "<li>" + "".join(teile) + "</li>"


def _sprechweise(quelle) -> str:
    """"Sprechweise aus Interview 2" -- maskiert."""
    return _t(T._TEXT_SPRECHWEISE_AUS.format(quelle=quelle))


def _zitat(satz) -> str:
    """Ein woertliches Zitat in den Anfuehrungszeichen der Seitensprache --
    der Satz selbst bleibt, wie er ist (D7: Zitate werden nie uebersetzt)."""
    return T._ZITAT.format(zitat=_t(satz))


def _form_anzeige(wert) -> str:
    """Wie ein Formwert aus der Datenbank auf der Seite heisst (roh, nicht
    maskiert). Deutsch der Wert selbst; unbekannte Werte bleiben stehen."""
    return T.FORM_BESCHRIFTUNG.get(wert, wert)


# --- Bearbeiten: die Bausteine der Formulare ------------------------------
#
# Alle drei Bausteine liefern denselben Rahmen: ein ``<div class="feld">`` mit
# ``data-feld`` (der Parametername aus ``web_schreiben.FELDER``), optional
# ``data-ziel`` (die id einer Figur oder Szene) und einem Speicherknopf.
# ``_BEARBEITEN_JS`` braucht nichts weiter zu wissen -- deshalb kommt kein
# einziger Feldname im JavaScript vor.


def _rahmen(inhalt: str, feld: str, ziel=None, knopf: str | None = None) -> str:
    ziel_attr = f' data-ziel="{_t(ziel, "")}"' if ziel is not None else ""
    return (
        f'<div class="feld" data-feld="{_t(feld)}"{ziel_attr}>{inhalt}'
        f'<button type="button" class="speichern">{_t(knopf or T.TEXT_SPEICHERN)}</button>'
        '<span class="hinweis" aria-live="polite"></span></div>'
    )


def _textfeld(
    feld: str, wert, ziel=None, zeilen: int = 1, platzhalter: str = "",
    beschriftung: str = "", knopf: str | None = None,
) -> str:
    """Ein Textfeld mit Speicherknopf. Immer ``<textarea>``, auch einzeilig:
    eine Begriffsliste ist laenger als der Bildschirm, und ein ``<input>``
    zeigt davon eine Zeile ohne Umbruch."""
    marke = (
        f'<label class="marke">{_t(beschriftung)}</label>' if beschriftung else ""
    )
    return _rahmen(
        marke
        + f'<textarea rows="{int(zeilen)}" placeholder="{_t(platzhalter, "")}">'
        + _t(wert, "")
        + "</textarea>",
        feld,
        ziel,
        knopf,
    )


def _optionen(paare, aktuell: str) -> str:
    return "".join(
        '<option value="{w}"{sel}>{b}</option>'.format(
            w=_t(wert, ""),
            b=_t(beschriftung, ""),
            sel=" selected" if str(wert) == aktuell else "",
        )
        for wert, beschriftung in paare
    )


def _dropdown(
    feld: str,
    paare,
    aktuell,
    ziel=None,
    mit_eigener: bool = False,
    platzhalter: str | None = None,
    leer: str | None = None,
    beschriftung: str = "",
) -> str:
    """Ein Dropdown, optional mit „eigene …" und Freitextfeld daneben.

    Der aktuelle Wert ist **immer** waehlbar, auch wenn er nicht mehr unter
    den angebotenen steht (Birk: der gewaehlte Vorschlag ist vorausgewaehlt).
    Steht er nicht in der Liste, waehlt das Dropdown „eigene …" und der
    Freitext traegt ihn -- so kann ein im Chat frei formuliertes Kernthema
    hier gelesen und weiterbearbeitet werden, statt stumm zu verschwinden."""
    aktuell = "" if aktuell is None else str(aktuell)
    liste = [(w, b) for w, b in paare]
    bekannt = {str(w) for w, _ in liste}
    if leer is not None:
        liste.insert(0, ("", leer))
        bekannt.add("")
    frei = mit_eigener and aktuell not in bekannt
    if mit_eigener:
        liste.append((EIGENE, T._TEXT_EIGENE))
    gewaehlt = EIGENE if frei else aktuell
    stuecke = []
    if beschriftung:
        stuecke.append(f'<label class="marke">{_t(beschriftung)}</label>')
    stuecke.append(f'<select class="auswahl">{_optionen(liste, gewaehlt)}</select>')
    if mit_eigener:
        stuecke.append(
            '<input type="text" class="eigene" value="{wert}" '
            'placeholder="{platz}"{versteckt}>'.format(
                wert=_t(aktuell if frei else "", ""),
                platz=_t(platzhalter or T._TEXT_EIGENE_FORMULIERUNG, ""),
                versteckt="" if frei else " hidden",
            )
        )
    return _rahmen("".join(stuecke), feld, ziel)


def _mehrfachauswahl(feld: str, paare, gewaehlt, ziel=None) -> str:
    """Die Besetzung einer Szene: ein ``<select multiple>``. Kein Framework,
    keine Chips -- eine Mehrfachauswahl ist auf dem Telefon eine Liste, die
    man antippt, und genau das leistet das Element von sich aus."""
    ausgewaehlt = {str(w) for w in gewaehlt}
    optionen = "".join(
        '<option value="{w}"{sel}>{b}</option>'.format(
            w=_t(wert, ""),
            b=_t(beschriftung, ""),
            sel=" selected" if str(wert) in ausgewaehlt else "",
        )
        for wert, beschriftung in paare
    )
    if not optionen:
        return f'<p class="leer">{html.escape(T._TEXT_KEINE_FIGUREN)}</p>'
    return _rahmen(
        f'<select multiple size="4">{optionen}</select>', feld, ziel
    )


def _schaerfungen_html(kurzformen, was: str | None = None) -> str:
    """Die bei der Schärfung zugeordneten Interviewstellen -- **read-only**,
    als Zähler mit Liste (Phase 6, Umbau 05.09.2026 nachts).

    Nur die Kurzformen (höchstens acht Wörter Arbeitsergebnis, wie am
    Beamer), nie das Belegzitat und nie die Begründung des Laufs. Und nichts
    zum Anklicken: die Zuordnung entsteht im Chat und wird dort abgenommen
    („Gefällt uns, weiter" / „Noch eine Runde"). Ohne Zuordnungen fehlt die
    Zeile ganz, statt als leere Aufgabe dazustehen."""
    kurzformen = [k for k in (kurzformen or []) if k]
    if not kurzformen:
        return ""
    zeilen = "".join(f"<li>{_t(k)}</li>" for k in kurzformen)
    return (
        f'<div class="schaerfung"><b>{_t(was or T._TEXT_SCHAERFUNG)} ({len(kurzformen)})</b>'
        f"<ul>{zeilen}</ul></div>"
    )


def _dramaturgie_html(daten: dict) -> str:
    """Der Abschnitt „Dramaturgie-Prüfung" auf der Gruppenseite: die Befunde
    der letzten Runde, **read-only** und **ohne Belegzitat**.

    Dieselbe Grenze wie bei den Verdichtungen (docs/agents/weboberflaeche.md, „Drei Grenzen"): das
    Belegzitat ist der Nachweis, mit dem der Code den Befund zugelassen hat,
    nicht der Text für die Seite — und eine Seite ohne Login ist nicht der
    Ort, an dem geprüfte und ungeprüfte Zitate nebeneinander stehen.

    Ohne gelaufene Runde fehlt der Abschnitt ganz, statt als leere
    Überschrift dazustehen."""
    runde = (daten or {}).get("runde")
    befunde = (daten or {}).get("befunde") or []
    if not runde or not befunde:
        return ""
    zeilen = []
    for b in befunde:
        schwere = (b.get("schwere") or "").lower()
        pruefung = b.get("pruefung") or ""
        marke = T.PRUEFUNG_BESCHRIFTUNG.get(pruefung, pruefung)
        if b.get("szene") is not None:
            marke = f"{T._TEXT_SZENE_NR.format(nummer=b['szene'])} · {marke}"
        vorschlag = (b.get("vorschlag") or "").strip()
        zusatz = (
            f'<span class="vorschlag">{_t(vorschlag)}</span>' if vorschlag else ""
        )
        zeilen.append(
            f'<div class="befund {html.escape(schwere)}">'
            f'<span class="marke">{_t(marke)}</span><br>{_t(b.get("text"))}'
            f"{zusatz}</div>"
        )
    kopf = T._TEXT_DRAMATURGIE_RUNDE.format(runde=int(runde), anzahl=len(befunde))
    return (
        f"<h2>{html.escape(T._UEBERSCHRIFT_DRAMATURGIE)}</h2>"
        f'<p class="leer">{html.escape(kopf)}</p>' + "".join(zeilen)
    )


def _figur_formular(f: dict, interviews: list[dict]) -> str:
    """Eine Figur zum Bearbeiten: Name, Beschreibung, Interview, Entfernen.

    Sprachprofil und Zitate stehen daneben, aber **nur zum Lesen** -- sie
    stammen aus einem geprueften Modellauf ueber ein Transkript und sind kein
    Parameter, den man von Hand nachbessert. Wer die Stimme aendern will,
    wechselt das Interview; das Profil entsteht dann neu."""
    stuecke = [
        f'<div class="figur" data-figur="{_t(f["id"])}">',
        _textfeld(
            "figur_name", f["name"], f["id"],
            beschriftung=web_schreiben.T.FIGURENFELDER["name"],
        ),
        _textfeld(
            "figur_beschreibung", f.get("beschreibung"), f["id"],
            zeilen=2, platzhalter=T._TEXT_OHNE_BESCHREIBUNG,
            beschriftung=web_schreiben.T.FIGURENFELDER["beschreibung"],
        ),
        _dropdown(
            "figur_quelle",
            [(i["id"], i["bezeichnung"]) for i in interviews],
            f.get("quelle_aufnahme_id"),
            f["id"],
            leer=T._TEXT_KEIN_INTERVIEW,
            beschriftung=T._TEXT_SPRICHT_AUS,
        ),
    ]
    if f.get("quelle"):
        # Bleibt neben dem Dropdown stehen: die Zeile sagt in Worten, was
        # das Auswahlfeld nur als markierte Option zeigt -- und sie ist die
        # Zeile, an der die Gruppe die Stimme der Figur wiedererkennt.
        stuecke.append(f'<div class="zeit">{_sprechweise(f["quelle"])}</div>')
    if f.get("sprachprofil"):
        stuecke.append(f'<div class="profil">{_t(f["sprachprofil"])}</div>')
    for satz in f.get("zitate") or []:
        stuecke.append(f"<blockquote>{_zitat(satz)}</blockquote>")
    stuecke.append(_schaerfungen_html(f.get("schaerfungen")))
    stuecke.append(
        _rahmen("", "figur_entfernen", f["id"], knopf=T.TEXT_ENTFERNEN)
    )
    stuecke.append("</div>")
    return "".join(stuecke)


def _stueckkarte_html(daten: dict) -> str:
    """Die Stueckkarte (Padua-Brainstorming-Umbau, 02.10.2026): die vier
    festen Felder aus Phase 4 -- Setting, Figuren, Geschichte, Anzahl
    Szenen -- mit ✓, wenn gesetzt, und ``offen`` sonst. Dieselbe Haltung wie
    ``phasentexte.checkliste`` im Chat (✅/⬜), hier als lesbarer Web-
    Abschnitt ohne Emoji, mit dem gesetzten Wert statt nur dem Haeckchen.

    Rein lesend wie der ganze Dashboard-Lesepfad: ``daten`` kommt aus
    ``web_daten.gruppe_nach_token``, kein SQL hier."""
    stand = daten.get("arbeitsstand") or {}
    figuren = daten.get("figuren") or []
    felder = (
        (T._STUECKKARTE_SETTING, (stand.get("rahmen") or "").strip()),
        (
            T._STUECKKARTE_FIGUREN,
            ", ".join(f["name"] for f in figuren)
            if (stand.get("figuren_fixiert_am") or "").strip() and figuren
            else "",
        ),
        (T._STUECKKARTE_GESCHICHTE, (stand.get("geschichte") or "").strip()),
        (T._STUECKKARTE_SZENENANZAHL, (stand.get("szenen_anzahl") or "").strip()),
    )
    zeilen = []
    for name, wert in felder:
        if wert:
            zeilen.append(
                f'<li class="erledigt">✓ {_t(name)}: {_t(wert)}</li>'
            )
        else:
            zeilen.append(
                f'<li class="offen">{html.escape(T._TEXT_STUECKKARTE_OFFEN)} '
                f"· {_t(name)}</li>"
            )
    return f'<ul class="stueckkarte">{"".join(zeilen)}</ul>'


def _festlegungen_html(daten: dict, nonce_wert: str | None) -> str:
    """Was die Gruppe festgelegt hat und wofuer es kein Feld gibt.

    **Aufgeklappt**, nicht in einem ``<details>`` wie das Journal. Das ist
    der eine Punkt, an dem sich dieser Abschnitt vom Journal unterscheidet,
    und er ist der Grund, warum es ihn gibt: das Journal steht auf derselben
    Seite, eingeklappt, und war damit *sichtbar, nicht wirksam*
    (docs/analyse-phase4-datenverlust-2026-09-06.md § 2.7).

    Mit ``nonce_wert`` bekommt jede Zeile einen Loeschknopf -- Pflicht, nicht
    Kuer (§ 4.4 Risiko 3): ohne ihn bleibt eine ueberholte Festlegung fuer
    immer stehen, so wie am 06.09. der Eintrag ueber einen laengst
    zurueckgenommenen zweiten Spielort. Angelegt wird hier nichts; das tut
    der Chat."""
    zeilen = daten.get("festlegungen") or []
    if not zeilen:
        return f'<p class="leer">{html.escape(T._TEXT_KEINE_FESTLEGUNGEN)}</p>'
    stuecke = []
    for z in zeilen:
        # .lower(): ein kanonischer Bereich kommt aus repo.normiere_bereich
        # schon kleingeschrieben, ein geleckter (``rahmen``, A13/laptop-A1)
        # dagegen oft GROSSBUCHSTABEN, wie es das Protokoll fuer den Fall
        # verlangt, aus dem er stammt (``entfernen``, nicht
        # ``festlegung_setzen``) -- ohne ``.lower()`` liefe der Nachschlag
        # an "RAHMEN" vorbei auf den rohen, unuebersetzten Wert zurueck. Ein
        # wirklich freier Titel (kein bekannter Bereich) bekommt wie im Chat
        # (``erkenner._bereich_titel``) keine erfundene Uebersetzung, aber
        # auch keine stehenbleibenden GROSSBUCHSTABEN (Review-Fix RAHMEN,
        # 06.10.2026): ``str.capitalize()`` statt dem rohen Modellwert.
        roh = z["bereich"] or ""
        bereich = T.FESTLEGUNG_BEREICH_BESCHRIFTUNG.get(roh.lower())
        if bereich is None:
            bereich = roh.capitalize()
        marke = bereich + (f" · {z['bezug']}" if z.get("bezug") else "")
        knopf = (
            _rahmen("", "festlegung_entfernen", z["id"], knopf=T.TEXT_ENTFERNEN)
            if nonce_wert
            else ""
        )
        stuecke.append(
            '<div class="festlegung"><span class="marke">{marke}</span>'
            "<span>{text}</span>{knopf}</div>".format(
                marke=_t(marke), text=_t(z["text"]), knopf=knopf
            )
        )
    return "".join(stuecke)


def _altbestand_html(stand: dict) -> str:
    """Die Felder der alten Dramaturgie -- **nur wenn gesetzt, nur zum Lesen**
    (Phasen-Umbau 05.09.2026 nachts).

    Kernthema, Kernthema-Richtung, Kernfrage und Hauptkonflikt sind keine
    Station mehr; ``arbeitsstand.geschichte`` hat ihre Rolle übernommen. Ein
    Formular dafür wäre eine Einladung, an einer Stelle weiterzuarbeiten, die
    der Bot nicht mehr anbietet. Wegzulassen wäre aber auch falsch: eine
    Gruppe, die gestern ein Kernthema gesetzt hat, soll es nicht stumm
    verlieren. Also: steht etwas da, steht es da — sonst fehlt die Zeile ganz
    (dieselbe Regel wie beim Hauptkonflikt)."""
    zeilen = [
        f"<dt>{label}</dt><dd>{_t(stand.get(feld))}</dd>"
        for feld, label in web_schreiben.T.NUR_ANZEIGE.items()
        if (stand.get(feld) or "").strip()
    ]
    return "".join(zeilen)


def _bearbeiten_html(daten: dict, nonce_wert: str) -> str:
    """Der Arbeitsstand der Gruppenseite -- zum Lesen **und** zum Ändern.

    Editierbar ist genau, was die Gruppe hier auch **fertig entscheiden**
    kann: Setting, Geschichte, die Figuren und die Szenenplanung. Alles davor
    führt der Chat (Birk, 06.09.2026 10:25) — Phase, Begriffe, Fragen und die
    drei Leitfaden-Felder stehen als Anzeige da, denn sie entstehen über
    Knöpfe und Ping-Pong, oft mit einem Modellaufruf dahinter, und der
    Webserver hat keinen Modellklienten. Statt der drei Rohfelder steht der
    **gebaute Leitfaden** (``leitfaden.aus_feldern``): das, was die Gruppe im
    Interview wirklich in der Hand hält.

    Was sonst fehlt, fehlt mit Absicht: Material wird nicht angefasst, der
    Szenen-Volltext gehört in den Chat, und die Felder der alten
    Kernthema-Station stehen nur noch read-only da (``_altbestand_html``)."""
    stand = daten["arbeitsstand"]
    auswahl = daten.get("bearbeitbares") or {}
    phase = stand.get("phase") or phasen.ERSTE
    dt = T.ARBEITSSTAND_BESCHRIFTUNG
    figuren = "".join(
        _figur_formular(f, auswahl.get("interviews") or [])
        for f in daten["figuren"]
    ) or f'<p class="leer">{html.escape(T._TEXT_KEINE_FIGUR)}</p>'
    # Die Meldungen des Speicherns (``_BEARBEITEN_JS``) als data-Attribute:
    # im Skript steht kein Nutzertext, und sie kommen mit dem <body> frisch
    # aus der Sprache des Profils.
    meldungen = (
        '<span id="meldungen" hidden data-sicher="{sicher}" '
        'data-speichert="{speichert}" data-gespeichert="{gespeichert}" '
        'data-fehler="{fehler}"></span>'.format(
            sicher=_t(T._JS_SICHER), speichert=_t(T._JS_SPEICHERT),
            gespeichert=_t(T._JS_GESPEICHERT), fehler=_t(T._JS_FEHLER),
        )
    )
    return (
        f'<input type="hidden" id="nonce" value="{_t(nonce_wert)}">'
        f"{meldungen}"
        "<dl>"
        # Die Phase steht oben, weil sie alles darunter einordnet -- als
        # Anzeige. Gesetzt wird sie allein von der Gruppe, und zwar im Chat
        # (AGENTS.md, "Die Phase setzt allein die Gruppe"): der Bot bietet den
        # Wechsel an, sobald die Materiallage ihn hergibt.
        f"<dt>{_t(dt['phase'])}</dt><dd>{_t(phasen.bezeichnung(phase))}</dd>"
        f"<dt>{_t(dt['begriffe'])}</dt><dd>{_t(stand['begriffe'])}</dd>"
        f"<dt>{_t(dt['fragen'])}</dt><dd>{_fragen_html(stand.get('fragen'))}</dd>"
        # Der Leitfaden statt seiner drei Rohfelder: er ist das Ergebnis, das
        # die Gruppe braucht, und er wird gebaut, nicht getippt -- aus
        # denselben Feldern wie im Chat (``leitfaden.aus_feldern``).
        + _leitfaden_html(stand, daten.get("web_token"))
        + f"<dt>{_t(dt['rahmen'])}</dt><dd>"
        + _dropdown(
            "rahmen",
            [(w, w) for w in auswahl.get("rahmen") or []],
            stand.get("rahmen"),
            mit_eigener=True,
            platzhalter=T._PLATZ_SETTING,
            leer=T._TEXT_NOCH_OFFEN,
        )
        + "</dd>"
        + f"<dt>{_t(dt['geschichte'])}</dt><dd>"
        + _textfeld(
            "geschichte",
            stand.get("geschichte"),
            zeilen=5,
            platzhalter=T._PLATZ_GESCHICHTE,
        )
        + "</dd>"
        + _altbestand_html(stand)
        + f"<dt>{_t(dt['figuren'])}</dt><dd>{figuren}"
        + '<div class="hinzu">'
        + _textfeld(
            "figur_neu", "", platzhalter=T._PLATZ_NEUE_FIGUR,
            knopf=T._TEXT_FIGUR_HINZU,
        )
        + "</div></dd></dl>"
    )


def _arbeitsstand_html(
    arbeitsstand: dict, figuren: list[dict], mit_stimmen: bool = False,
    token: str | None = None,
) -> str:
    figuren_html = "".join(_figur_html(f, mit_stimmen) for f in figuren)
    # Die Phase steht oben: sie ordnet alles darunter ein. Eine ungesetzte
    # Phase (NULL) gilt wie 1 -- diese Anzeigeregel steht hier, web_daten
    # liefert den rohen Wert (interview_theater/phasen.py).
    phase = arbeitsstand.get("phase") or phasen.ERSTE
    dt = T.ARBEITSSTAND_BESCHRIFTUNG
    return (
        "<dl>"
        f"<dt>{_t(dt['phase'])}</dt><dd>{_t(phasen.bezeichnung(phase))}</dd>"
        f"<dt>{_t(dt['begriffe'])}</dt><dd>{_t(arbeitsstand['begriffe'])}</dd>"
        f"<dt>{_t(dt['fragen'])}</dt><dd>{_fragen_html(arbeitsstand.get('fragen'))}</dd>"
        # Der Leitfaden steht direkt unter den Fragen -- er ist ihre
        # Gebrauchsanweisung (06.09.2026). Read-only wie alles hier: gebaut
        # wird er aus denselben Feldern wie im Chat (``leitfaden.aus_feldern``),
        # damit auf der Wand nichts anderes steht als auf dem Telefon.
        + _leitfaden_html(arbeitsstand, token)
        + f"<dt>{_t(dt['kernthema'])}</dt><dd>{_t(arbeitsstand['kernthema'])}"
        + (
            f"<div class=\"zeit\">{_t(arbeitsstand['kernthema_begruendung'], '')}</div>"
            if arbeitsstand["kernthema_begruendung"]
            else ""
        )
        + "</dd>"
        + f"<dt>{_t(dt['rahmen'])}</dt><dd>{_t(arbeitsstand.get('rahmen'))}</dd>"
        # Die Geschichte im Groben (Phase 5, Umbau 05.09.2026 nachts) -- nur,
        # wenn es sie gibt, wie beim Hauptkonflikt.
        + (
            f"<dt>{_t(dt['geschichte'])}</dt><dd>{_t(arbeitsstand['geschichte'])}</dd>"
            if arbeitsstand.get("geschichte")
            else ""
        )
        # Der Hauptkonflikt steht nur da, wenn es einen gibt (05.09.2026): er
        # ist eine moegliche Rahmen-Entscheidung, keine Pflicht -- ein leeres
        # Feld daneben sieht aus wie eine unerledigte Aufgabe.
        + (
            f"<dt>{_t(dt['hauptkonflikt'])}</dt><dd>{_t(arbeitsstand['hauptkonflikt'])}</dd>"
            if arbeitsstand.get("hauptkonflikt")
            else ""
        )
        + f"<dt>{_t(dt['figuren'])}</dt><dd>"
        + (
            f'<ul class="figuren">{figuren_html}</ul>'
            if figuren
            else f'<span class="leer">{html.escape(T._TEXT_NOCH_KEINE)}</span>'
        )
        + "</dd></dl>"
    )


# --- Team-Dashboard (Padua 02.10.2026: in der Sprache des Profils) ----------
#
# Bis Aufgabe 17 blieb das Dashboard fest deutsch. Seit Padua (englisches
# Profil, Team spricht Englisch) laeuft es ueber dieselbe Texttabelle wie die
# Gruppenseite. Deutsch bleibt **byte-gleich** -- die Vergleichsdatei
# ``tests/fixtures/dashboard_de_vorher.html`` ist mit dem Code davor erzeugt.

_TITEL_DASHBOARD = "interview_theater — Dashboard"
_UEBERSCHRIFT_DASHBOARD = "Arbeitsstand aller Gruppen"
_TEXT_STAND = "Stand {zeit}"
_UEBERSCHRIFT_BOT_ZUORDNUNG = "Bot-Zuordnung"
#: Die Spaltenkoepfe der Bot-Zuordnung: Bot, Gruppe, chat_id, letzte Aktivitaet.
_ZUORDNUNG_KOEPFE = ("Bot", "Gruppe", "chat_id", "letzte Aktivität")
#: Die Spaltenkoepfe der Aufruftabelle je Gruppe.
_AUFRUF_KOEPFE = ("Aufruf", "heute", "Fehl", "Median")
_TEXT_KEINE_AUFRUFE = "heute noch keine Modellaufrufe"
_TEXT_AUFNAHMEN = "Aufnahmen — {liste}"
_TEXT_KEINE = "keine"
_TEXT_VERDICHTUNGEN = "Verdichtungen: {anzahl}"
#: Eigene vs. KI-Fragen (Aufgabe 14, ``web_daten.dashboard``/
#: ``gruppe_nach_token``, Schluessel ``fragen_auswertung``) -- dieselbe Zeile
#: auf dem Dashboard und der Gruppenseite (``_fragen_auswertung_html``). Nur
#: sichtbar, wenn ``gesamt`` einen Wert ungleich 0/0 traegt -- eine Zeile
#: "0 eigene, 0 KI" waere Laerm wie "nichts fehlt" bei den Fehlstellen.
_TEXT_FRAGEN_AUSWERTUNG = "Fragen behalten: {eigen} eigene, {ki} KI"
_TEXT_SZENENZAHL = "Szenen: {anzahl}"
_TEXT_ZULETZT = "zuletzt: {zeit}"
_TEXT_INTERVIEWMODUS = "Interviewmodus"
_TEXT_BOT_WEIT = ", bot-weit"
_TEXT_KEINE_GRUPPE_GESCHRIEBEN = "Noch keine Gruppe hat geschrieben."
_TEXT_KEINE_GRUPPE = "— keine Gruppe —"
#: Die Ueberschrift des eingeklappten Technikteils einer Karte (nur mit
#: ``[web] dashboard_log_einklappen``). Ohne Zahl: das sanfte Nachladen
#: oeffnet ``<details>`` am Summary-Text wieder (``_SCROLL_JS``).
_TEXT_LOG = "Log"
#: Das gestaltete Dashboard (P2, Aufgabe 3, nur mit
#: ``[web] dashboard_gestaltet``): Fortschritt je Gruppe, ein Satz, wenn
#: noch nichts steht, und der Hinweis, wenn etwas klemmt. Je Zahl zwei
#: Fassungen (eins/mehr), damit am Beamer kein "1 Vorfälle" steht.
_TEXT_FORTSCHRITT = "Phase {nummer}/{gesamt} · {name}"
_TEXT_NOCH_NICHTS_FESTGELEGT = "Noch nichts festgelegt."
_TEXT_ACHTUNG = "Braucht Aufmerksamkeit"
_TEXT_ACHTUNG_FEHL_EINS = "{anzahl} fehlgeschlagener Modellaufruf in den letzten 2 Stunden"
_TEXT_ACHTUNG_FEHL = "{anzahl} fehlgeschlagene Modellaufrufe in den letzten 2 Stunden"
_TEXT_ACHTUNG_VORFALL_EINS = "{anzahl} Vorfall in den letzten 2 Stunden (zuletzt: {art})"
_TEXT_ACHTUNG_VORFALL = "{anzahl} Vorfälle in den letzten 2 Stunden (zuletzt: {art})"
_TEXT_ACHTUNG_KOSTEN_NAH = "Tagesdeckel fast erreicht ({prozent} %)"
_TEXT_ACHTUNG_KOSTEN_ERREICHT = "Tagesdeckel erreicht – der Bot pausiert bis Mitternacht"
_TEXT_ACHTUNG_STILL_EINS = "Der Bot hat {anzahl} Nachricht seit {minuten} Min. nicht abgeholt"
_TEXT_ACHTUNG_STILL = "Der Bot hat {anzahl} Nachrichten seit {minuten} Min. nicht abgeholt"
#: Ab welchem Anteil am Tagesdeckel das Dashboard warnt.
KOSTEN_WARNSCHWELLE = 0.8
#: Welche Vorfallarten auf dem gestalteten Dashboard ein PROBLEM sind (Review
#: an 2841d83). Alle anderen sind Buchhaltung des Betriebs -- ein verworfenes
#: Echo, ein gekuerzter Kontext, eine wiederholte 5xx, ein Rate-Limit -- und
#: entstehen an einem echten Tag laufend; stuenden sie im Hinweis, waere der
#: Kasten fast dauerhaft an ("Technik nur bei Problemen"). Sie bleiben im
#: eingeklappten Log. Eine Art gehoert hierher, wenn etwas verloren oder
#: ausgefallen ist, worauf die Gruppe wartet, oder wenn die Workshopleitung
#: etwas beheben muss. Begruendung je Art im Bericht zur Aufgabe (Abschnitt
#: "Fix"); ein Test haelt fest, dass jede Art hier wirklich geschrieben wird.
ACHTUNG_VORFAELLE = frozenset({
    # Die Gruppe wartet und bekommt nichts.
    "gespraechszug_fehlgeschlagen",
    "auftragszug_fehlgeschlagen",
    "szene_fehlgeschlagen",
    "szene_abgeschnitten",
    "kurzgeschichte_fehlgeschlagen",
    "szenenfolge_fehlgeschlagen",
    "schaerfung_fehlgeschlagen",
    "stueckpruefung_fehlgeschlagen",
    "stueckpruefung_zu_lang",
    "dramaturgie_fehlgeschlagen",
    "buehnenkarte_fehlgeschlagen",
    "sprachprofil_fehlgeschlagen",
    "sprachstil_fehlgeschlagen",
    "kernzitate_fehlgeschlagen",
    "undo_fehlgeschlagen",
    # Material ist (noch) nicht angekommen.
    "download_fehlgeschlagen",
    "transkription_fehlgeschlagen",
    "verdichtung_fehlgeschlagen",
    # Eine Festlegung der Gruppe wurde erkannt, aber nicht gespeichert.
    "erkenner_anwenden_fehler",
    # Die Workshopleitung muss etwas tun (Konfiguration, Proxy, Kosten).
    "abgeschnitten",
    "kontext_kuerzung_erfolglos",
    "kostendeckel_erreicht",
    "kosten_modell_unbekannt",
    "opus_fallback",
    "dramaturgie_verschlechterung",
})
#: Datum und Uhrzeit auf dem Dashboard (strftime). Deutsch mit dem Trenner
#: " · ", den es immer trug (er stammt aus dem geteilten ``_zeitpunkt``).
_ZEITFORMAT_DASHBOARD = "%d.%m.%Y %H:%M · "
#: Das Dezimalzeichen der Mediandauer: deutsch "5,1 s", englisch "5.1 s".
_DEZIMALZEICHEN = ","

#: Der Ticker-Tab (Padua, 05.10.2026): nur sichtbar, wenn IT_WEB_TICKER_DATEI
#: gesetzt ist -- ohne die Variable bleibt das Dashboard byte-gleich
#: (Dortmund setzt sie nie, siehe ``ticker_html``/``dashboard_html``).
_TEXT_TAB_TICKER = "Ticker"
_TITEL_TICKER = "interview_theater — Ticker"
_UEBERSCHRIFT_TICKER = "Regie-Ticker"
_TEXT_TICKER_AUS = "Ticker aus."
_TEXT_TICKER_LEER = "Noch keine Einträge."
_TEXT_TICKER_STATUS_LETZTES = "Letztes Update: {uhrzeit} Uhr ({alter})"
_TEXT_TICKER_STATUS_NAECHSTES = "Nächstes ~{naechste}"
_TEXT_TICKER_STATUS_STEHT = "⚠ Ticker steht seit {minuten} min"
_TEXT_TICKER_ALTER_GERADE = "gerade eben"
_TEXT_TICKER_ALTER_VOR = "vor {minuten} min"
_TEXT_TICKER_TECHNIK_OK = "● Technik unauffällig"
_TEXT_TICKER_TECHNIK_VERDACHT = "● Technik: Verdacht ({anzahl})"

#: Wie ein Aufnahmestatus auf dem Dashboard heisst -- Schluessel ist der
#: Datenbankwert (``aufnahme.status``, Protokoll), deutsch der Wert selbst
#: (K4). Ein unbekannter Status bleibt als Rohwert stehen.
AUFNAHMESTATUS_BESCHRIFTUNG = {
    "empfangen": "empfangen",
    "laeuft": "laeuft",
    "transkribiert": "transkribiert",
    "fertig": "fertig",
    "fehlgeschlagen": "fehlgeschlagen",
}

#: Wie eine Vorfallart auf dem Dashboard heisst -- Schluessel ist
#: ``vorfall.art`` (``repo.merke_vorfall``), deutsch der Wert selbst (K4).
#: Eine Art, die hier fehlt, bleibt als Rohwert stehen -- kein Fehler.
VORFALLART_BESCHRIFTUNG = {
    "abgeschnitten": "abgeschnitten",
    "auftragszug_fehlgeschlagen": "auftragszug_fehlgeschlagen",
    "denkspur_verworfen": "denkspur_verworfen",
    "denkspur_wiederholt": "denkspur_wiederholt",
    "download_fehlgeschlagen": "download_fehlgeschlagen",
    "dramaturgie_aufruf_fehlgeschlagen": "dramaturgie_aufruf_fehlgeschlagen",
    "dramaturgie_fehlgeschlagen": "dramaturgie_fehlgeschlagen",
    "dramaturgie_verschlechterung": "dramaturgie_verschlechterung",
    "echo_verworfen": "echo_verworfen",
    "echo_wiederholt": "echo_wiederholt",
    "erkenner_anwenden_fehler": "erkenner_anwenden_fehler",
    "erkenner_nachlauf_fehler": "erkenner_nachlauf_fehler",
    "extraktor_fehler": "extraktor_fehler",
    "fenster_verworfen": "fenster_verworfen",
    "festlegung_stand_schon_im_feld": "festlegung_stand_schon_im_feld",
    "geschichte_war_formwahl": "geschichte_war_formwahl",
    "gespraech_systemzeile_erfunden": "gespraech_systemzeile_erfunden",
    "gespraechszug_fehlgeschlagen": "gespraechszug_fehlgeschlagen",
    "http_5xx": "http_5xx",
    "interview_ohne_knopf_offen": "interview_ohne_knopf_offen",
    "journal_extraktor_fehler": "journal_extraktor_fehler",
    "journal_nachlauf_fehler": "journal_nachlauf_fehler",
    "kernzitate_fehlgeschlagen": "kernzitate_fehlgeschlagen",
    "kontext_gekuerzt": "kontext_gekuerzt",
    "kontext_kuerzung_erfolglos": "kontext_kuerzung_erfolglos",
    "kostendeckel_erreicht": "kostendeckel_erreicht",
    "kosten_modell_unbekannt": "kosten_modell_unbekannt",
    "kurzgeschichte_fehlgeschlagen": "kurzgeschichte_fehlgeschlagen",
    "nachpass_abschnittszahl": "nachpass_abschnittszahl",
    "nachpass_fehlgeschlagen": "nachpass_fehlgeschlagen",
    "nachpass_gelaufen": "nachpass_gelaufen",
    "nachpass_reicht_nicht": "nachpass_reicht_nicht",
    "nachpass_verworfen_zitat": "nachpass_verworfen_zitat",
    "rahmen_war_geschichte": "rahmen_war_geschichte",
    "richtung_szenen_unvollstaendig": "richtung_szenen_unvollstaendig",
    "schaerfung_fehlgeschlagen": "schaerfung_fehlgeschlagen",
    "sprachprofil_fehlgeschlagen": "sprachprofil_fehlgeschlagen",
    "sprachstil_fehlgeschlagen": "sprachstil_fehlgeschlagen",
    "stueckpruefung_fehlgeschlagen": "stueckpruefung_fehlgeschlagen",
    "stueckpruefung_zu_lang": "stueckpruefung_zu_lang",
    "szene_abgeschnitten": "szene_abgeschnitten",
    "szene_budget_knapp": "szene_budget_knapp",
    "szene_fehlgeschlagen": "szene_fehlgeschlagen",
    "szene_ohne_zusammenfassung": "szene_ohne_zusammenfassung",
    "szene_prompt_gekuerzt": "szene_prompt_gekuerzt",
    "szenenfolge_fehlgeschlagen": "szenenfolge_fehlgeschlagen",
    "transkription_fehlgeschlagen": "transkription_fehlgeschlagen",
    "ueberschreiben_verhindert": "ueberschreiben_verhindert",
    "undo_fehlgeschlagen": "undo_fehlgeschlagen",
    "undo_nicht_angelegt": "undo_nicht_angelegt",
    "verdichtung_fehlgeschlagen": "verdichtung_fehlgeschlagen",
    "vorschlag_mehrere_arten": "vorschlag_mehrere_arten",
    "web_rate_limit": "web_rate_limit",
    "wiederholung_verworfen": "wiederholung_verworfen",
    "zitat_ungeprueft": "zitat_ungeprueft",
}

#: Wie eine Aufrufart in der Aufruftabelle heisst -- Schluessel ist
#: ``aufruf.art`` (``repo.merke_aufruf``), deutsch der Wert selbst (K4).
AUFRUFART_BESCHRIFTUNG = {
    "gespraech": "gespraech",
    "erkenner": "erkenner",
    "journal": "journal",
    "verdichter": "verdichter",
    "stt": "stt",
    "szene": "szene",
    "prosa": "prosa",
    "szene_nachpass": "szene_nachpass",
    "kurzgeschichte": "kurzgeschichte",
    "kurzgeschichte_nachpass": "kurzgeschichte_nachpass",
    "szenenfolge": "szenenfolge",
    "szenenfelder": "szenenfelder",
    "geschichte": "geschichte",
    "schaerfung": "schaerfung",
    "sprachprofil": "sprachprofil",
    "sprachstil": "sprachstil",
    "kernzitate": "kernzitate",
    "stueckpruefung": "stueckpruefung",
    "dramaturgie_a2": "dramaturgie_a2",
    "dramaturgie_a6": "dramaturgie_a6",
    "dramaturgie_a9": "dramaturgie_a9",
    "dramaturgie_a10": "dramaturgie_a10",
    "dramaturgie_a11": "dramaturgie_a11",
    "dramaturgie_b1": "dramaturgie_b1",
    "dramaturgie_c1": "dramaturgie_c1",
}

#: Szenen ohne gesetzte Form zaehlt ``web_daten._szenen_nach_form`` unter
#: diesem Rohwert -- er steht nicht in ``FORM_BESCHRIFTUNG`` (keine Form,
#: sondern ein Zustand) und bekommt deshalb hier seine Beschriftung (K4).
DASHBOARD_FORM_BESCHRIFTUNG = {
    "offen": "offen",
}


def _beschriftung(tabelle: dict, schluessel) -> str:
    """Die Anzeige eines Protokollwerts aus einer Beschriftungstabelle --
    unbekannt bleibt der Rohwert stehen (kein Fehler, kein Strich)."""
    return tabelle.get(schluessel, schluessel)


def _dashboard_zeit(iso: str | None) -> str:
    """Datum und Uhrzeit fuer das Dashboard, lokale Zeit Europe/Berlin.

    Deutsch zeichengleich mit dem zweiten ``_zeitpunkt`` (dort mit dem
    Trenner " · " und leer, wenn unbekannt) -- das Format kommt aber aus der
    Texttabelle, damit Padua ein eindeutiges ``2026-10-02 12:30`` sieht.
    ``_zeitpunkt`` selbst bleibt unangetastet: die Gruppenseite teilt es."""
    if not iso:
        return ""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=ZoneInfo("UTC"))
        lokal = t.astimezone(ZoneInfo("Europe/Berlin"))
        return lokal.strftime(T._ZEITFORMAT_DASHBOARD)
    except (ValueError, TypeError):
        return ""


def _eingeklappt(summary: str, inhalt: str, einklappen: bool) -> str:
    """``inhalt`` in einem geschlossenen ``<details>`` mit ``summary`` --
    oder unveraendert, wenn nicht eingeklappt wird. Nie ``open``: das
    sanfte Nachladen oeffnet, was jemand aufgeklappt hat, selbst wieder."""
    if not einklappen:
        return inhalt
    return f"<details><summary>{_t(summary)}</summary>{inhalt}</details>"


def _szenenzahl(anzahl: int, formen: list) -> str:
    """"3 Szenen: 2 Dialog, 1 Lied" -- die Szenenzahl mit ihren Formen
    (05.09.2026).

    Eine blosse Zahl sagt am Beamer wenig; die Formen sagen, was fuer ein
    Abend gerade entsteht. Ohne Szenen bleibt es bei der Zahl. Die Form
    kommt roh aus der Datenbank; angezeigt wird ihre Beschriftung
    (``FORM_BESCHRIFTUNG``, ``DASHBOARD_FORM_BESCHRIFTUNG``), deutsch also
    der Rohwert wie bisher, eine unbekannte Form ebenfalls roh."""
    kopf = html.escape(T._TEXT_SZENENZAHL).format(anzahl=f"<b>{anzahl}</b>")
    if not formen:
        return kopf
    return kopf + " — " + ", ".join(f"{n} {_t(_form_dashboard(form))}" for form, n in formen)


def _form_dashboard(form) -> str:
    """Die Beschriftung einer Form auf dem Dashboard, unbekannt roh."""
    if form in T.FORM_BESCHRIFTUNG:
        return T.FORM_BESCHRIFTUNG[form]
    return _beschriftung(T.DASHBOARD_FORM_BESCHRIFTUNG, form)


def _ergebnisse_html(
    kurzformen: list[dict], en: dict | None = None, uebersetzen: bool = False,
) -> str:
    """Je Interview eine Zeile mit den Ergebnissen als Kurzform (N6).

    **Ohne Zitate, ohne Zusammenfassung, ohne Transkript** -- das Dashboard
    haengt am Beamer. Was hier steht, sind Arbeitsergebnisse in hoechstens
    acht Woertern je Thema.

    ``en``/``uebersetzen`` (Karte t_f7770dc4): ohne ``uebersetzen`` oder ohne
    einen Treffer unter ``interview_<i>_<j>`` bleibt eine Kurzform roh --
    escaped wie zuvor, nur je Kurzform statt am ganzen String, was dasselbe
    Ergebnis ergibt, weil ``SUMMARY_TRENNER`` keine HTML-Sonderzeichen hat."""
    en = en or {}
    if not kurzformen:
        return ""
    zeilen = []
    for i, v in enumerate(kurzformen):
        werte = SUMMARY_TRENNER.join(
            _en_oder_original(en, f"interview_{i}_{j}", kurz, uebersetzen)
            for j, kurz in enumerate(v["kurzformen"])
        )
        zeilen.append(f'<li><b>{_t(v["name"], T._TEXT_INTERVIEW)}</b> {werte}</li>')
    return f'<ul class="ergebnisse">{"".join(zeilen)}</ul>'


def _en_oder_original(en: dict, schluessel: str, original: str, uebersetzen: bool) -> str:
    """Der englische Wert eines Segments, wenn der Cache ihn trifft; sonst
    das Original -- dezent markiert (``ux-ausstehend``), aber nur, wenn der
    Profilschalter ueberhaupt an ist (sonst bleibt die Zeile byte-gleich)."""
    text = en.get(schluessel)
    if text:
        return _t(text)
    original_html = _t(original)
    return (
        f'<span class="ux-ausstehend">{original_html}</span>'
        if uebersetzen else original_html
    )


def dashboard_html(daten: dict, praefix: str = VORGABE_PRAEFIX, token: str = "") -> str:
    """Das projizierte Team-Dashboard aus web_daten.dashboard().

    ``praefix`` baut den Link zur Gruppenseite (Birk 04.09.: je Gruppe ein
    Link) -- relativ zum Server, damit er hinter nginx genauso geht wie
    direkt auf Port 8010.

    ``token`` ist der Dashboard-Token aus der Route -- nur damit UND mit
    ``IT_WEB_TICKER_DATEI`` gesetzt erscheint der "Ticker"-Tab (Padua,
    05.10.2026). Ohne Token (Vorgabe) oder ohne die Variable bleibt die
    Seite byte-gleich wie vorher -- Dortmund setzt die Variable nie.

    Mit ``[web] dashboard_log_einklappen`` im Profil (Padua) stehen je Karte
    Zahlen, Vorfaelle und Aufrufe -- und am Ende die Bot-Zuordnung -- in
    einem geschlossenen ``<details>``: am Beamer zaehlt der Arbeitsstand,
    der Technikteil ist fuers Team. Ohne den Schalter bleibt die Seite
    byte-gleich wie zuvor."""
    from interview_theater import uebersetzung, workshop

    einklappen = bool(workshop.aktiv().wert("web.dashboard_log_einklappen", False))
    # P2, Aufgabe 3: die Gestaltung -- ohne den Schalter faellt jeder der
    # folgenden Zweige weg, und die Seite bleibt byte-gleich.
    gestaltet = bool(workshop.aktiv().wert("web.dashboard_gestaltet", False))
    # Karte t_f7770dc4 (Padua): die Gruppenfelder zusaetzlich auf Englisch,
    # aus dem Cache in ``uebersetzung.py`` -- kein Modellaufruf hier. Ohne
    # den Schalter (Dortmund/Vorgabe) bleibt jede Zeile unten byte-gleich.
    uebersetzen = bool(workshop.aktiv().wert("web.dashboard_uebersetzen_en", False))
    karten = []
    for g in daten["gruppen"]:
        titel = _t(g["titel"], _t(T._TEXT_GRUPPE.format(chat_id=g["chat_id"])))
        if g.get("web_token"):
            titel = f'<a href="{praefix}/g/{_t(g["web_token"])}">{titel}</a>'
        marke = (
            f'<span class="marke">{_t(T._TEXT_INTERVIEWMODUS)}</span>'
            if g["interviewmodus_seit"]
            else ""
        )
        aufnahmen = ", ".join(
            f"{_t(_beschriftung(T.AUFNAHMESTATUS_BESCHRIFTUNG, status))}: <b>{anzahl}</b>"
            for status, anzahl in g["aufnahmen"].items()
        ) or f'<span class="leer">{_t(T._TEXT_KEINE)}</span>'
        aufrufe = "".join(
            "<tr><td>{art}</td><td>{anzahl}</td><td>{fehl}</td><td>{median}</td></tr>".format(
                art=_t(_beschriftung(T.AUFRUFART_BESCHRIFTUNG, a["art"])),
                anzahl=a["anzahl"],
                fehl=a["fehlschlaege"],
                median=_sekunden(a["median_ms"]),
            )
            for a in g["aufrufe"]
        )
        aufrufe_html = (
            "<table><tr>"
            + "".join(f"<th>{_t(kopf)}</th>" for kopf in T._AUFRUF_KOEPFE)
            + f"</tr>{aufrufe}</table>"
            if aufrufe
            else f'<p class="leer">{_t(T._TEXT_KEINE_AUFRUFE)}</p>'
        )
        vorfaelle = "".join(
            '<div><span class="art">{art}</span> {detail} '
            '<span class="zeit">{zeit}{botweit}</span></div>'.format(
                art=_t(_beschriftung(T.VORFALLART_BESCHRIFTUNG, v["art"])),
                detail=_t(v["detail"], ""),
                zeit=_t(_dashboard_zeit(v["erstellt_am"]), ""),
                botweit=_t(T._TEXT_BOT_WEIT) if v["bot_weit"] else "",
            )
            for v in g["vorfaelle"]
        )
        vorfaelle_html = (
            f'<div class="vorfaelle">{vorfaelle}</div>' if vorfaelle else ""
        )
        verdichtungen = _t(T._TEXT_VERDICHTUNGEN).format(
            anzahl=f"<b>{g['verdichtungen']}</b>"
        )
        zuletzt = _t(T._TEXT_ZULETZT).format(
            zeit=_t(_dashboard_zeit(g["letzte_aktivitaet"]), "")
        )
        # Eigene vs. KI-Fragen (Aufgabe 14) -- ein zusaetzlicher Span, NUR
        # wenn es ueberhaupt Zahlen gibt (klassische Gruppen ohne
        # A/B-Vergleich bleiben byte-identisch, ``g.get`` liefert dort
        # ``None``, ``_fragen_auswertung_text`` dann ``None``).
        fragen_auswertung_text = _fragen_auswertung_text(g.get("fragen_auswertung"))
        fragen_auswertung_span = (
            f"<span>{fragen_auswertung_text}</span>" if fragen_auswertung_text else ""
        )
        zahlen = (
            '<div class="zahlen">'
            f"<span>{_t(T._TEXT_AUFNAHMEN).format(liste=aufnahmen)}</span>"
            f"<span>{verdichtungen}</span>"
            f'<span>{_szenenzahl(g["szenen"], g.get("szenen_formen") or [])}</span>'
            f"<span>{zuletzt}</span>"
            f"{fragen_auswertung_span}"
            "</div>"
        )
        log = _eingeklappt(T._TEXT_LOG, f"{zahlen}{vorfaelle_html}{aufrufe_html}", einklappen)
        if gestaltet:
            # Karte t_f7770dc4: ohne den Schalter ist ``en`` immer leer, und
            # ``kopf_html`` bleibt das alte ``<h2>{titel}</h2>`` -- byte-gleich.
            en = uebersetzung.englisch(g) if uebersetzen else {}
            hauptthema_en = en.get("hauptthema") if en else None
            kopf_html = (
                f'<h2>{_t(hauptthema_en)}</h2><p class="ux-untertitel">{titel}</p>'
                if hauptthema_en else f"<h2>{titel}</h2>"
            )
            # Fortschritt oben, dann ein Hinweis NUR wenn etwas klemmt, dann
            # der Inhalt. Der Botname wandert in die Bot-Zuordnung (Technik).
            karten.append(
                "<section class=\"karte\">"
                f'<div class="kopf">{kopf_html}{marke}</div>'
                f'{_fortschritt_html(g["arbeitsstand"].get("phase"))}'
                f"{_achtung_html(g)}"
                f"{_dashboard_inhalt_html(g, en, uebersetzen)}"
                + log
                + "</section>"
            )
            continue
        karten.append(
            "<section class=\"karte\">"
            f'<div class="kopf"><h2>{titel}</h2>'
            f'<span class="bot">{_t(g["bot_name"])} {marke}</span></div>'
            f'{_arbeitsstand_html(g["arbeitsstand"], g["figuren"])}'
            f'{_ergebnisse_html(g.get("interview_kurzformen") or [])}'
            + log
            + "</section>"
        )
    gruppen_html = (
        f'<div class="gruppen">{"".join(karten)}</div>'
        if karten
        else f'<p class="leer">{_t(T._TEXT_KEINE_GRUPPE_GESCHRIEBEN)}</p>'
    )

    zuordnung = "".join(
        "<tr><td>{bot}</td><td>{titel}</td><td>{chat}</td><td>{zeit}</td></tr>".format(
            bot=_t(z["bot_name"]),
            titel=_t(z["titel"], _t(T._TEXT_KEINE_GRUPPE)),
            chat=_t(z["chat_id"]),
            zeit=_t(_dashboard_zeit(z["letzte_aktivitaet_am"]), ""),
        )
        for z in daten["bot_zuordnung"]
    )
    zuordnung_tabelle = (
        "<table><tr>"
        + "".join(f"<th>{_t(kopf)}</th>" for kopf in T._ZUORDNUNG_KOEPFE)
        + f"</tr>{zuordnung}</table>"
    )
    zuordnung_html = (
        _eingeklappt(T._UEBERSCHRIFT_BOT_ZUORDNUNG, zuordnung_tabelle, True)
        if einklappen
        else f"<h2>{_t(T._UEBERSCHRIFT_BOT_ZUORDNUNG)}</h2>{zuordnung_tabelle}"
    )
    stand = _t(T._TEXT_STAND).format(zeit=_t(_dashboard_zeit(daten["stand"]), ""))
    css = _CSS_DASHBOARD
    if gestaltet:
        from interview_theater import web_gestalt

        css += web_gestalt.tokens_css() + web_gestalt.css_dashboard()
    tab_ticker_html = (
        f' <a class="tab-ticker" href="{praefix}/dashboard/{_t(token)}/ticker">'
        f"{_t(T._TEXT_TAB_TICKER)}</a>"
        if token and os.environ.get("IT_WEB_TICKER_DATEI", "").strip()
        else ""
    )
    return _seite(
        T._TITEL_DASHBOARD,
        css,
        f'<h1>{_t(T._UEBERSCHRIFT_DASHBOARD)} <span class="stand">{stand}</span>'
        f"{tab_ticker_html}</h1>\n"
        f"{gruppen_html}\n"
        f"{zuordnung_html}",
    )


def _ticker_eintraege(pfad: str) -> list[dict]:
    """Liest ``IT_WEB_TICKER_DATEI`` zeilenweise, neueste zuerst.

    Der Schreiber (``padua-ticker.py``) haengt nur an -- eine Zeile kann
    trotzdem mitten im Schreiben gelesen werden. Fehlt die Datei, ist sie
    nicht lesbar, oder ist eine Zeile kein gueltiges JSON-Objekt mit
    ``zeit``/``text``: die Zeile wird stillschweigend uebersprungen, die
    Seite scheitert nie (``ticker_html``)."""
    try:
        with open(pfad, encoding="utf-8") as datei:
            zeilen = datei.readlines()
    except OSError:
        return []
    eintraege = []
    for zeile in zeilen:
        zeile = zeile.strip()
        if not zeile:
            continue
        try:
            eintrag = json.loads(zeile)
        except ValueError:
            continue
        if not isinstance(eintrag, dict) or "zeit" not in eintrag or "text" not in eintrag:
            continue
        eintraege.append(eintrag)
    eintraege.reverse()
    return eintraege


#: "G1: ..." / "G2: ..." / "G3: ..." am Zeilenanfang (nach einem fuehrenden
#: "•") -- der INHALT-Teil gruppiert sich daran (Addendum 3, 06.10.2026).
_TICKER_GRUPPEN_PRAEFIX = re.compile(r"^(G[123]):\s*(.*)$")


def _ticker_uhrzeit(zeit_iso: str | None) -> str:
    gelesen = web_daten.lies_zeitstempel(zeit_iso)
    if gelesen is None:
        return "—"
    return gelesen.astimezone().strftime("%H:%M")


def _ticker_alter_minuten(zeit_iso: str | None) -> int | None:
    gelesen = web_daten.lies_zeitstempel(zeit_iso)
    if gelesen is None:
        return None
    delta = datetime.now(timezone.utc) - gelesen.astimezone(timezone.utc)
    return max(0, int(delta.total_seconds() // 60))


def _ticker_alter_text(minuten: int | None) -> str:
    if minuten is None:
        return ""
    if minuten < 1:
        return T._TEXT_TICKER_ALTER_GERADE
    return T._TEXT_TICKER_ALTER_VOR.format(minuten=minuten)


#: Ab diesem Alter des neuesten Eintrags gilt der Ticker als stehend --
#: Cron-Takt ist 10 min (padua-ticker-brief.md), 15 min ist ein Takt plus
#: Toleranz, kein Fehlalarm bei einer normal spaeten Minute.
_TICKER_STEHT_MINUTEN = 15
_TICKER_TAKT_MINUTEN = 10


def _ticker_letzter_lauf_iso(ticker_datei: str) -> str | None:
    """Wann der Ticker zuletzt GELAUFEN ist -- die mtime seiner
    ``state.json`` neben ``IT_WEB_TICKER_DATEI`` (er schreibt sie bei jedem
    Lauf, auch wenn es nichts Neues gibt und deshalb KEIN Eintrag entsteht).
    Birk 07.10.2026: "Ticker stuck for 18 min" stand da, obwohl der Ticker
    alle 10 min lief und nur nichts Neues zu melden hatte."""
    try:
        zeit = os.path.getmtime(os.path.join(os.path.dirname(ticker_datei), "state.json"))
    except OSError:
        return None
    return datetime.fromtimestamp(zeit, timezone.utc).isoformat()


def _ticker_status_html(eintraege: list[dict], letzter_lauf_iso: str | None = None) -> str:
    """Statuszeile ueber der Liste: letztes Update, naechstes erwartet, und
    eine Warnung, wenn der neueste Eintrag laenger stillsteht als ein
    Cron-Takt plus Toleranz -- das sagt der Regie "Cron pausiert/kaputt",
    bevor sie es am leeren Bildschirm selbst herausfinden muss."""
    zeit_iso = eintraege[0].get("zeit")
    alter_min = _ticker_alter_minuten(zeit_iso)
    # "steht" misst den letzten LAUF, nicht den letzten Eintrag (ein Lauf
    # ohne neue Daten schreibt keinen Eintrag).
    lauf_min = _ticker_alter_minuten(letzter_lauf_iso) if letzter_lauf_iso else alter_min
    gelesen = web_daten.lies_zeitstempel(zeit_iso)
    naechste = (
        (gelesen + timedelta(minutes=_TICKER_TAKT_MINUTEN)).astimezone().strftime("%H:%M")
        if gelesen else "—"
    )
    teile = [
        f"<span>{_t(T._TEXT_TICKER_STATUS_LETZTES.format(uhrzeit=_ticker_uhrzeit(zeit_iso), alter=_ticker_alter_text(alter_min)))}</span>",
        f"<span>{_t(T._TEXT_TICKER_STATUS_NAECHSTES.format(naechste=naechste))}</span>",
    ]
    if lauf_min is not None and lauf_min > _TICKER_STEHT_MINUTEN:
        teile.append(
            f'<span class="ticker-stale">{_t(T._TEXT_TICKER_STATUS_STEHT.format(minuten=lauf_min))}</span>')
    return f'<div class="ticker-status">{"".join(teile)}</div>'


def _ticker_inhalt_html(text) -> str:
    """Der INHALT-Teil als echte Liste, pro Gruppe gruppiert, wenn die
    Zeilen "G1:"/"G2:"/"G3:"-Praefixe tragen (so liefert sie der Brief);
    Zeilen ohne Praefix (✨/🎬) bleiben eine eigene, ungruppierte Liste."""
    punkte = [z.strip().lstrip("•").strip() for z in str(text or "").splitlines() if z.strip()]
    if not punkte:
        return '<div class="ticker-inhalt"><p class="leer">–</p></div>'
    gruppen: dict[str, list[str]] = {}
    reihenfolge: list[str] = []
    sonstige: list[str] = []
    for p in punkte:
        treffer = _TICKER_GRUPPEN_PRAEFIX.match(p)
        if treffer:
            g, rest = treffer.group(1), treffer.group(2)
            if g not in gruppen:
                gruppen[g] = []
                reihenfolge.append(g)
            gruppen[g].append(rest)
        else:
            sonstige.append(p)
    teile = []
    for g in reihenfolge:
        zeilen = "".join(f"<li>{_t(z)}</li>" for z in gruppen[g])
        teile.append(f"<h3>{_t(g)}</h3><ul>{zeilen}</ul>")
    if sonstige:
        zeilen = "".join(f"<li>{_t(z)}</li>" for z in sonstige)
        teile.append(f"<ul>{zeilen}</ul>")
    return f'<div class="ticker-inhalt">{"".join(teile)}</div>'


def _ticker_technik_html(text) -> str:
    """Der TECHNIK-Teil als eingeklapptes ``<details>`` (nie ``open``): die
    Ampel im ``<summary>`` bleibt auch zugeklappt sichtbar -- gruen ohne
    ⚠-Zeilen, gelb mit Anzahl sonst. ⚠-Zeilen stehen zuerst (so liefert sie
    bereits ``technik_text_mit_einschaetzung`` im Profil-Repo-Skript)."""
    punkte = [z.strip() for z in str(text or "").splitlines() if z.strip()]
    anzahl_warnungen = sum(1 for p in punkte if p.startswith("⚠"))
    if anzahl_warnungen:
        klasse = "ampel-gelb"
        label = T._TEXT_TICKER_TECHNIK_VERDACHT.format(anzahl=anzahl_warnungen)
    else:
        klasse = "ampel-gruen"
        label = T._TEXT_TICKER_TECHNIK_OK
    zeilen = "".join(
        f'<li class="ticker-warnung">{_t(p)}</li>' if p.startswith("⚠") else f"<li>{_t(p)}</li>"
        for p in punkte
    ) or f"<li>{_t(label)}</li>"
    return (
        f'<details class="ticker-technik"><summary class="{klasse}">{_t(label)}</summary>'
        f"<ul>{zeilen}</ul></details>"
    )


def _ticker_eintrag_html(e: dict, neu: bool) -> str:
    """Ein Ticker-Eintrag: neues Format (``inhalt``/``technik`` getrennt)
    oder altes Format (nur ``text``), rueckwaertskompatibel (06.10.2026).

    Der neueste Eintrag (``neu=True``) steht gross und offen als
    ``<article>``; aeltere stehen gedaempft als ``<details>``, auf die
    Kopfzeile (Zeit + Alter) eingeklappt."""
    kopf = (f'<span class="zeit">{_t(_ticker_uhrzeit(e.get("zeit")))}</span> '
            f'<span class="alter">{_t(_ticker_alter_text(_ticker_alter_minuten(e.get("zeit"))))}</span>')
    if e.get("inhalt") or e.get("technik"):
        rumpf = _ticker_inhalt_html(e.get("inhalt")) + _ticker_technik_html(e.get("technik"))
    else:
        rumpf = f'<div class="ticker-inhalt"><p>{_t(e.get("text"))}</p></div>'
    if neu:
        return f'<article class="ticker-eintrag ticker-neu"><div class="ticker-kopf">{kopf}</div>{rumpf}</article>'
    return f'<details class="ticker-eintrag ticker-alt"><summary>{kopf}</summary>{rumpf}</details>'


def ticker_html() -> str:
    """Der Regie-Ticker als eigene Seite (Padua, 05.10.2026, Addendum 3
    06.10.2026): Eintraege aus ``IT_WEB_TICKER_DATEI``, neueste zuerst,
    alle 60 s sanft nachgeladen (voller Neuladebefehl, siehe ``_TICKER_JS``
    -- die Seite steht ohnehin oben, ein Reload haelt die Scrollposition
    automatisch dort).

    PRIMAER ist der Inhalt: er steht gross, offen und als erstes; TECHNIK
    ist je Eintrag ein eingeklapptes Detail mit einer Ampel im Titel.

    Ohne die Variable wird keine Datei angefasst -- die Seite antwortet mit
    einem freundlichen Hinweis statt mit einem Dateizugriff ins Leere."""
    ticker_datei = os.environ.get("IT_WEB_TICKER_DATEI", "").strip()
    if not ticker_datei:
        koerper = (
            f"<h1>{_t(T._UEBERSCHRIFT_TICKER)}</h1>"
            f'<p class="leer">{_t(T._TEXT_TICKER_AUS)}</p>'
        )
    else:
        eintraege = _ticker_eintraege(ticker_datei)
        if eintraege:
            status = _ticker_status_html(eintraege, _ticker_letzter_lauf_iso(ticker_datei))
            liste = "".join(
                _ticker_eintrag_html(e, neu=(i == 0)) for i, e in enumerate(eintraege))
            koerper = (
                f"<h1>{_t(T._UEBERSCHRIFT_TICKER)}</h1>"
                f"{status}"
                f'<div class="ticker-liste">{liste}</div>'
            )
        else:
            koerper = (
                f"<h1>{_t(T._UEBERSCHRIFT_TICKER)}</h1>"
                f'<p class="leer">{_t(T._TEXT_TICKER_LEER)}</p>'
            )
    return _seite(T._TITEL_TICKER, _CSS_DASHBOARD + _CSS_TICKER, koerper,
                  nachladen=False, skript=_TICKER_JS)


#: Eigenes Nachlade-Intervall (60 s statt der zehn des Dashboards, Aufgabe
#: "Padua Regie-Ticker als Webseite"): ein voller Neuladebefehl reicht --
#: der Ticker traegt keine aufklappbaren <details>, deren Zustand das
#: sanfte Nachladen von ``_SCROLL_JS`` sonst erhalten muesste.
_TICKER_JS = "setInterval(function () { location.reload(); }, 60000);"


def _fortschritt_html(phase) -> str:
    """"Act 5/7 · Sharpening" und sieben Segmente (P2, Aufgabe 3).

    Am Beamer ist das die eine Zeile, die man von hinten im Raum lesen
    koennen muss. Die Segmente sind Schmuck (``aria-hidden``), der Text
    traegt die Aussage. Eine ungesetzte Phase gilt wie 1 -- dieselbe
    Anzeigeregel wie in ``_arbeitsstand_html``."""
    nummer = phase or phasen.ERSTE
    gesamt = phasen.LETZTE
    segmente = "".join(
        '<i class="{}"></i>'.format(
            "fertig" if i < nummer else "jetzt" if i == nummer else "offen")
        for i in range(1, gesamt + 1)
    )
    text = T._TEXT_FORTSCHRITT.format(
        nummer=nummer, gesamt=gesamt, name=phasen.kurzname(nummer))
    return (
        f'<div class="ux-fortschritt"><span class="ux-akt">{_t(text)}</span>'
        f'<span class="ux-segmente" aria-hidden="true">{segmente}</span></div>'
    )


def _achtung_html(g: dict) -> str:
    """Der Hinweis, wenn bei einer Gruppe etwas klemmt -- sonst nichts.

    Vier Anlaesse, alle aus Daten, die ``web_daten.dashboard`` liefert:
    fehlgeschlagene Modellaufrufe und Vorfaelle aus ``ACHTUNG_VORFAELLE``,
    beide im selben Fenster (``web_daten.VORFALL_FENSTER``, zwei Stunden),
    Kosten ab ``KOSTEN_WARNSCHWELLE`` des Tagesdeckels (Tag ab Mitternacht
    Ortszeit wie ``kosten``), und Eingaenge im Web-Kanal, die der Bot nicht
    abholt. Die Einzelheiten bleiben im Log; hier steht nur, DASS und WAS."""
    punkte = []
    fehl = g.get("fehlschlaege_fenster") or 0
    if fehl:
        vorlage = T._TEXT_ACHTUNG_FEHL_EINS if fehl == 1 else T._TEXT_ACHTUNG_FEHL
        punkte.append(vorlage.format(anzahl=fehl))
    vorfaelle = [v for v in g.get("vorfaelle") or [] if v.get("art") in ACHTUNG_VORFAELLE]
    if vorfaelle:
        vorlage = (T._TEXT_ACHTUNG_VORFALL_EINS if len(vorfaelle) == 1
                   else T._TEXT_ACHTUNG_VORFALL)
        punkte.append(vorlage.format(
            anzahl=len(vorfaelle),
            art=_beschriftung(T.VORFALLART_BESCHRIFTUNG, vorfaelle[0]["art"])))
    heute = g.get("kosten_heute_chf") or 0
    deckel = g.get("kosten_deckel_chf") or 0
    if deckel > 0 and heute >= deckel:
        punkte.append(T._TEXT_ACHTUNG_KOSTEN_ERREICHT)
    elif deckel > 0 and heute >= KOSTEN_WARNSCHWELLE * deckel:
        punkte.append(T._TEXT_ACHTUNG_KOSTEN_NAH.format(
            prozent=round(100 * heute / deckel)))
    still = g.get("unbeantwortet")
    if still:
        vorlage = (T._TEXT_ACHTUNG_STILL_EINS if still["anzahl"] == 1
                   else T._TEXT_ACHTUNG_STILL)
        punkte.append(vorlage.format(anzahl=still["anzahl"], minuten=still["minuten"]))
    if not punkte:
        return ""
    zeilen = "".join(f"<li>{_t(p)}</li>" for p in punkte)
    return (
        f'<div class="ux-achtung" role="status"><b>{_t(T._TEXT_ACHTUNG)}</b>'
        f"<ul>{zeilen}</ul></div>"
    )


def _dashboard_inhalt_html(g: dict, en: dict | None = None, uebersetzen: bool = False) -> str:
    """Was die Gruppe hat -- und nur das (P2, Aufgabe 3).

    Gegenueber ``_arbeitsstand_html`` fehlen: die Phase (steht im
    Fortschritt), der Leitfaden (er ist aus den Fragen gebaut, die schon
    dastehen) und jedes leere Feld (ein Strich je Feld ist am Beamer
    Rauschen). Reihenfolge der Geschichte nach: Setting, Geschichte,
    Figuren, Interviewergebnisse, dann das Material davor. Kernthema und
    Hauptkonflikt nur, wenn gesetzt. Kein Zitat, kein Transkript -- die
    Ergebnisse sind die Kurzformen wie bisher.

    ``en``/``uebersetzen`` (Karte t_f7770dc4): ohne den Profilschalter (oder
    ohne einen Treffer im Cache) bleibt jedes Feld roh wie zuvor; mit Treffer
    steht die englische Fassung, sonst das Original dezent markiert
    (``ux-ausstehend``, ``web_gestalt.css_dashboard``)."""
    en = en or {}
    stand = g["arbeitsstand"]
    dt = T.ARBEITSSTAND_BESCHRIFTUNG
    teile = []
    # ``dd.kurz`` kappt das CSS auf wenige Zeilen (``line-clamp``): eine
    # Karte im Spaetstand muss am Beamer in 1080 px passen (Review an
    # 2841d83). Der volle Text steht auf der Gruppenseite.
    kurz = '<dd class="kurz">'
    for feld in ("rahmen", "geschichte"):
        if stand.get(feld):
            wert = _en_oder_original(en, feld, stand[feld], uebersetzen)
            teile.append(f"<dt>{_t(dt[feld])}</dt>{kurz}{wert}</dd>")
    if g["figuren"]:
        # Nur die Namen: zehn Figuren mit Beschreibung sind am Beamer eine
        # halbe Karte.
        figuren = SUMMARY_TRENNER.join(
            f'<b>{_en_oder_original(en, f"figur_{i}", f["name"], uebersetzen)}</b>'
            for i, f in enumerate(g["figuren"]))
        teile.append(
            f'<dt>{_t(dt["figuren"])}</dt><dd class="figuren">{figuren}</dd>')
    ergebnisse = _ergebnisse_html(g.get("interview_kurzformen") or [], en, uebersetzen)
    if ergebnisse:
        # Birk 06.10.2026 14:20: nach dem Zusammenfuehren 20-37 Interviews je
        # Gruppe -- im line-clamp von ``dd.kurz`` waren nur 1-3 sichtbar ("...").
        # Eigene Klasse ohne Kappung, wie ``dd.fragen-voll``.
        teile.append(f'<dt>{_t(T._UEBERSCHRIFT_INTERVIEWS)}</dt><dd class="interviews-voll">{ergebnisse}</dd>')
    for feld in ("kernthema", "hauptkonflikt", "begriffe"):
        if stand.get(feld):
            wert = _en_oder_original(en, feld, stand[feld], uebersetzen)
            teile.append(f"<dt>{_t(dt[feld])}</dt>{kurz}{wert}</dd>")
    # Fast-Track 06.10.2026 ("Regie-Dashboard: alle ausgewaehlten Fragen"):
    # ``auswahl.dashboard_fragen`` liefert ALLE ausgewaehlten Fragen (auch
    # waehrend die Gruppe noch sortiert), geclustert nach Begriff, numeriert
    # wie im Chat -- ``dd.fragen-voll`` traegt deshalb bewusst KEIN
    # ``line-clamp`` (anders als ``kurz``), das waere hier Verstuemmelung
    # statt Kuerzung.
    fragen_dashboard_html = _fragen_dashboard_html(g, en, uebersetzen)
    if fragen_dashboard_html:
        teile.append(f"<dt>{_t(dt['fragen'])}</dt>{fragen_dashboard_html}")
    leer = (
        "" if teile
        else f'<p class="noch-nichts">{_t(T._TEXT_NOCH_NICHTS_FESTGELEGT)}</p>'
    )
    return f'<dl>{"".join(teile)}</dl>{leer}'


#: Trennzeichen der Kurzformen in einer Summary-Zeile. Der Mittelpunkt, weil
#: die Ergebnisse gleichrangig nebeneinanderstehen ("Pfannkuchen mit
#: Schokolade und Banane · Punkerin im autonomen Zentrum").
SUMMARY_TRENNER = " · "


def _szene_summary(s: dict) -> str:
    """Die zusammengeklappte Zeile einer Szene: Nummer, Titel, Form, Ort, Wer.

    Genau so viel, dass die Gruppe die Szene wiedererkennt, ohne aufzuklappen
    -- und genau die Felder, die sie entschieden hat."""
    stuecke = []
    if s["nummer"] is not None:
        stuecke.append(_t(T._TEXT_SZENE_NR.format(nummer=s["nummer"])))
    if s.get("titel"):
        stuecke.append(_t(s["titel"]))
    if s.get("form"):
        stuecke.append(_t(_form_anzeige(s["form"])))
    if s.get("ort"):
        stuecke.append(_t(s["ort"]))
    if s.get("figuren"):
        stuecke.append(_t(", ".join(s["figuren"])))
    return SUMMARY_TRENNER.join(stuecke) or _t(T._TEXT_SZENE)


def fassungslink(szene_id, nummer: int) -> str:
    """Die Adresse einer Fassung: derselbe Pfad, nur mit Query und Anker.

    Rein serverseitig und ohne JavaScript (07.09.2026): ein ``<a href="?…">``
    behaelt das Token in der URL -- es steht im Pfad, nicht in der Query --,
    und das sanfte Nachladen holt ``location.href`` samt Query, die Auswahl
    bleibt also ueber den Austausch des ``<body>`` hinweg stehen. Der Anker
    bringt den Browser zurueck an die Szene, statt an den Seitenanfang.

    Liefert die rohe Adresse; ins Attribut geht sie durch ``_t`` wie jeder
    andere Wert auch (aus ``&`` wird ``&amp;``) -- die Regel "alles maskiert"
    gilt ohne Ausnahme, auch fuer das, was der Code selbst gebaut hat."""
    return f"?szene={int(szene_id)}&fassung={int(nummer)}#szene-{int(szene_id)}"


#: Wie die Fassungsleiste heisst, wenn sie vorgelesen wird -- als Konstante,
#: damit Test und Chat-Knopf denselben Wortlaut pruefen koennen, ohne ihn
#: abzuschreiben. Bis zum 07.09.2026 war das die Beschriftung des
#: aufklappbaren Blocks, den die Leiste abgeloest hat; der Wortlaut bleibt,
#: damit die Gruppe dieselbe Sache unter demselben Namen wiederfindet.
TEXT_FASSUNGEN = "Frühere Fassungen"


def _fassungen_html(s: dict, fassungen: list[dict] | None, gewaehlt: int | None) -> str:
    """Die Fassungen einer Szene: **umschalten**, nicht aufklappen (07.09.2026).

    Eine Leiste mit einer Nummer je Fassung -- die gewaehlte ist markiert und
    kein Link mehr --, darunter der Text genau dieser Fassung und, wenn es eine
    Vorgaengerin gibt, ein Link auf sie. Bei einer einzigen Fassung gibt es
    nichts umzuschalten: dann steht hier nichts und ``_szene_html`` zeigt den
    Volltext wie bisher.

    **Read-only.** Kein Formular, kein POST, kein Schreibweg von aussen: eine
    frueherer Fassung wieder in Kraft zu setzen ist eine Entscheidung der
    Gruppe und gehoert in den Chat, wo die Knoepfe darunter haengen."""
    if not fassungen or len(fassungen) < 2:
        return ""
    aktuelle = next(
        (f["nummer"] for f in fassungen if f.get("aktuell")), fassungen[-1]["nummer"]
    )
    nummern = [f["nummer"] for f in fassungen]
    if gewaehlt not in nummern:
        gewaehlt = aktuelle
    knoepfe = []
    for f in fassungen:
        marke = _t(str(f["nummer"]))
        if f["nummer"] == aktuelle:
            marke += " ●"
        if f["nummer"] == gewaehlt:
            knoepfe.append(f'<span class="fassung aktiv" aria-current="true">{marke}</span>')
        else:
            titel = f["beschriftung"] or T._TEXT_FASSUNG_NR.format(nummer=f["nummer"])
            knoepfe.append(
                f'<a class="fassung" href="{_t(fassungslink(s["id"], f["nummer"]))}" '
                f'title="{_t(titel)}">{marke}</a>'
            )
    zeigt = next(f for f in fassungen if f["nummer"] == gewaehlt)
    kopf = T._TEXT_N_FASSUNGEN.format(anzahl=len(fassungen))
    stuecke = [T._TEXT_FASSUNG_VON.format(nummer=zeigt["nummer"], gesamt=len(fassungen))]
    if zeigt["beschriftung"]:
        stuecke.append(zeigt["beschriftung"])
    if zeigt.get("aktuell"):
        stuecke.append(T._TEXT_DIE_AKTUELLE)
    # ``_zeitpunkt`` liefert einen PRAEFIX samt Trenner (siehe dort) -- er
    # steht deshalb vorn und wird nicht angehaengt, sonst endet die Zeile auf
    # einem Mittelpunkt ohne Fortsetzung.
    zeile = _zeitpunkt(zeigt["erstellt_am"]) + SUMMARY_TRENNER.join(stuecke)
    zurueck = ""
    if zeigt["nummer"] > nummern[0]:
        vorige = nummern[nummern.index(zeigt["nummer"]) - 1]
        zurueck = (
            f'<p class="zeit"><a href="{_t(fassungslink(s["id"], vorige))}">'
            f"{_t(T._TEXT_VORIGE_FASSUNG.format(nummer=vorige))}</a></p>"
        )
    return (
        f'<dl><dt>{_t(kopf)}</dt></dl>'
        # Die Leiste ist eine Navigation und braucht einen Namen, wenn sie
        # vorgelesen wird: die Nummern allein sagen nichts. Derselbe Wortlaut
        # wie am Chat-Knopf (``TEXT_FASSUNGEN``).
        f'<nav class="fassungen" aria-label="{html.escape(T.TEXT_FASSUNGEN)}">'
        f'{"".join(knoepfe)}</nav>'
        f'<p class="zeit">{_t(zeile)}</p>'
        f'<div class="volltext">{_t(zeigt["volltext"])}</div>'
        f"{zurueck}"
    )


def _szene_html(
    s: dict,
    figuren: list[dict] | None = None,
    fassungen: list[dict] | None = None,
    gewaehlt: int | None = None,
) -> str:
    """Eine Szene als aufklappbarer Block: Summary-Zeile, darin alle Felder
    der Planung und danach der Volltext (05.09.2026).

    Aufklappbar, weil eine Gruppenseite mit sechs ausgeschriebenen Szenen auf
    dem Handy nicht mehr zu ueberblicken ist -- und weil die Planung das ist,
    was die Gruppe im Gespraech braucht, nicht der ganze Text.

    Mit ``figuren`` (der Figurenliste der Gruppe) wird die Planung
    **bearbeitbar**: Titel, Form, Ort, Zeit, Anlass, was passiert, was anders
    ist, Ton und die Besetzung. Der **Volltext bleibt Anzeige** -- er entsteht
    aus einem Modellauf und wird im Chat abgenommen ("Passt" / "Passt, aber
    anders"); eine Textbox daneben waere ein zweiter, stiller Schreibweg an
    genau der Stelle, an der die Regie-Notiz haengt.

    Mit ``fassungen`` (zwei oder mehr) tritt an die Stelle des einen Volltexts
    die **Fassungsansicht**: umschalten und ein Link zurueck auf die vorige
    (``_fassungen_html``). ``gewaehlt`` ist die Nummer aus der URL; ohne sie
    steht die aktuelle da."""
    if figuren is None:
        felder = "".join(
            "<dt>{label}</dt><dd>{wert}</dd>".format(
                label=_t(T.SZENENFELD_BESCHRIFTUNG.get(label, label)),
                wert=_t(_form_anzeige(s[feld]) if feld in ("form", "form_vorschlag") else s[feld]),
            )
            for feld, label in web_daten.SZENENFELDER
            if s.get(feld)
        )
        if s.get("figuren"):
            felder = (
                f"<dt>{_t(T._TEXT_WER)}</dt><dd>{_t(', '.join(s['figuren']))}</dd>" + felder
            )
    else:
        formen = list(web_schreiben.FORMEN)
        jetzige = (s.get("form") or "").strip()
        if jetzige and jetzige not in formen:
            # Eine Szene aus der Zeit der sechs Formen ("stumm") oder eine
            # frei formulierte behaelt ihre Angabe -- sie steht als erste
            # Option da, statt stumm auf "offen" zurueckzufallen.
            formen.insert(0, jetzige)
        stile_liste = list(web_schreiben.STILE)
        jetziger_stil = (s.get("stil") or "").strip()
        if jetziger_stil and jetziger_stil not in stile_liste:
            # Wie bei der Form: ein Slug aus einer aelteren Fassung bleibt
            # sichtbar, statt stumm auf "ohne" zurueckzufallen.
            stile_liste.insert(0, jetziger_stil)
        feldnamen = web_schreiben.T.SZENENFELDER
        felder = (
            f"<dt>{_t(feldnamen['titel'])}</dt><dd>"
            + _textfeld("szene_titel", s.get("titel"), s["id"])
            + f"</dd><dt>{_t(T._TEXT_WER)}</dt><dd>"
            + _mehrfachauswahl(
                "szene_figuren",
                [(f["id"], f["name"]) for f in figuren],
                s.get("figur_ids") or [],
                s["id"],
            )
            + f"</dd><dt>{_t(feldnamen['form'])}</dt><dd>"
            + _dropdown(
                "szene_form",
                [(f, _form_anzeige(f).capitalize()) for f in formen],
                jetzige,
                s["id"],
                leer=T._TEXT_OFFEN,
            )
            # Der Vorschlag des Bots steht daneben und bleibt Anzeige
            # (06.09.2026): bestaetigt ist allein ``form``, und wer hier
            # waehlt, bestaetigt gerade selbst. Ihn editierbar zu machen
            # hiesse, den Vorschlag zur zweiten Entscheidung zu machen.
            + (
                f'<div class="zeit">'
                f'{_t(T._TEXT_VORSCHLAG.format(form=_form_anzeige(s["form_vorschlag"])))}</div>'
                if s.get("form_vorschlag")
                else ""
            )
            # Der Stil je Szene (06.09.2026, Birk 12:50) -- dasselbe Element
            # wie die Form und derselbe Wertevorrat wie der Knopf im Chat.
            # Die Beschriftung nennt die Vorlage, wie im Menue: wer waehlt,
            # soll wissen, woher das Mass kommt.
            + f"</dd><dt>{_t(feldnamen['stil'])}</dt><dd>"
            + _dropdown(
                "szene_stil",
                [
                    (slug, web_schreiben.T.STIL_BESCHRIFTUNG.get(slug, slug))
                    for slug in stile_liste
                ],
                jetziger_stil,
                s["id"],
                leer=T._TEXT_OHNE_STIL,
            )
            + "</dd>"
            + "".join(
                f"<dt>{_t(label)}</dt><dd>"
                + _textfeld(f"szene_{feld}", s.get(feld), s["id"], zeilen=2)
                + "</dd>"
                for feld, label in feldnamen.items()
                if feld not in ("titel", "form", "stil")
            )
        )
    if s.get("kurzbeschreibung"):
        felder += f"<dt>{_t(T._TEXT_KURZ)}</dt><dd>{_t(s['kurzbeschreibung'])}</dd>"
    # Read-only: die Zusammenfassung kommt vom Szenen-Modell und beschreibt
    # genau die gespeicherte Fassung -- ein Formularfeld waere eine Einladung,
    # sie vom Text abweichen zu lassen.
    if s.get("zusammenfassung"):
        felder += f"<dt>{_t(T._TEXT_ZUSAMMENFASSUNG)}</dt><dd>{_t(s['zusammenfassung'])}</dd>"
    inhalt = f"<dl>{felder}</dl>" if felder else ""
    inhalt += _schaerfungen_html(s.get("schaerfungen"))
    # Die Geschichte (Phase 6) steht ueber dem Theatertext: sie ist die
    # Vorlage, aus der er entsteht (06.09.2026, 10:30). Beide read-only.
    if s.get("prosa"):
        inhalt += (
            f'<dl><dt>{_t(T._TEXT_ALS_GESCHICHTE)}</dt></dl>'
            f'<div class="volltext">{_t(s["prosa"])}</div>'
        )
    # Ab zwei Fassungen tritt die Umschaltung an die Stelle des einen
    # Volltexts (07.09.2026) -- sonst stuende der aktuelle Text zweimal auf
    # der Seite, einmal als "der Text" und einmal als "Fassung N".
    fassungsblock = _fassungen_html(s, fassungen, gewaehlt)
    if fassungsblock:
        inhalt += fassungsblock
    elif s.get("volltext"):
        inhalt += f'<div class="volltext">{_t(s["volltext"])}</div>'
    elif not s.get("prosa"):
        inhalt += f'<p class="leer">{_t(T._TEXT_GEPLANT)}</p>'
    # ``id`` und ``open``: der Link aus der Uebersicht springt an die Szene,
    # und die aufgeschlagene Fassung soll dabei sichtbar sein statt hinter
    # einem zugeklappten <details> zu liegen.
    anker = f' id="szene-{int(s["id"])}"' if s.get("id") is not None else ""
    offen = " open" if fassungsblock and gewaehlt is not None else ""
    return (
        f'<details class="szene"{anker}{offen}>'
        f"<summary>{_szene_summary(s)}</summary>{inhalt}</details>"
    )


def _szenenuebersicht_html(zeilen: list[dict]) -> str:
    """Die kompakte Szenenliste ueber den aufklappbaren Bloecken
    (06.09.2026, Birk: *"nachdem Szene 1,2,3 schon definiert sind, sollten
    die da auch dargestellt werden"*).

    Eine Zeile je Szene: Nummer, Titel mit Kurzbeschreibung, Form (bzw. der
    Vorschlag, solange sie nicht bestaetigt ist), Stil und der Umfang von
    Prosa und Volltext. **Der Text selbst steht hier nicht** -- nur seine
    Zeichenzahl; die Fassung liest man im Block darunter.

    Read-only, wie das Dashboard: hier wird nichts bearbeitet, die
    Formularfelder stehen weiter in ``_szene_html``."""
    if not zeilen:
        return ""
    reihen = []
    for z in zeilen:
        nummer = "—" if z["nummer"] is None else str(z["nummer"])
        titel = _t(z["titel"], T._TEXT_OHNE_TITEL)
        if z["kurz"]:
            titel += f'<div class="zeit">{_t(z["kurz"])}</div>'
        if z["form"]:
            form = _t(_form_anzeige(z["form"]))
        elif z["form_vorschlag"]:
            vorschlag = T._TEXT_ALS_VORSCHLAG.format(form=_form_anzeige(z["form_vorschlag"]))
            form = f'<span class="vorschlag">{_t(vorschlag)}</span>'
        else:
            form = "—"
        umfang = []
        if z["prosa_zeichen"]:
            umfang.append(T._TEXT_UMFANG_PROSA.format(zeichen=z["prosa_zeichen"]))
        if z["volltext_zeichen"]:
            umfang.append(T._TEXT_UMFANG_TEXT.format(zeichen=z["volltext_zeichen"]))
        # Die Zahlen entstehen hier und nicht in der Datenbank -- sie gehen
        # trotzdem durch ``_t``, damit die Regel "alles maskiert" ohne
        # Ausnahme gilt; das ``<br>`` dazwischen ist unser eigenes Markup.
        umfang_html = "<br>".join(_t(t) for t in umfang) or _t(T._TEXT_KEIN_TEXT)
        # Der Zaehler (07.09.2026): eine Zeile je Szene sagt, wie viele
        # Fassungen es gibt, und ist zugleich der Weg dorthin. Bei einer
        # einzigen Fassung gibt es nichts umzuschalten -- dann keine Zahl.
        anzahl = z.get("fassungen") or 0
        if anzahl > 1 and z.get("id") is not None:
            fassungen_html = (
                f'<a href="{_t(fassungslink(z["id"], anzahl))}">'
                f"{_t(T._TEXT_N_FASSUNGEN.format(anzahl=anzahl))}</a>"
            )
        else:
            fassungen_html = "—"
        reihen.append(
            f'<tr><td class="nr">{_t(nummer)}</td><td>{titel}</td>'
            f"<td>{form}</td><td>{_t(z['stil'])}</td>"
            f'<td class="umfang">{umfang_html}</td>'
            f'<td class="umfang">{fassungen_html}</td></tr>'
        )
    koepfe = "".join(f"<th>{_t(k)}</th>" for k in T._UEBERSICHT_KOEPFE)
    return (
        f'<table class="uebersicht"><thead><tr>{koepfe}'
        "</tr></thead><tbody>"
        + "".join(reihen)
        + "</tbody></table>"
    )


def _vorspann_html(d: dict | None) -> str:
    """Der Vorspann ganz oben auf der Gruppenseite (07.09.2026).

    Derselbe Inhalt wie im Chat und im Textbuch, aus derselben Quelle
    (``web_daten.gruppe_nach_token`` ruft ``vorspann.daten``): wo und wann,
    worum es geht, welche Form, welche Szenen, wer vorkommt. **Read-only** --
    geaendert werden Setting, Konflikt, Format und Figuren weiter unten im
    Arbeitsstand; hier steht die Zusammenschau, die ein Aussenstehender
    zuerst braucht.

    Ist nichts festgelegt, steht hier nichts: eine Ueberschrift ueber einem
    Gedankenstrich waere ein Hinweis auf etwas, das die Gruppe nicht
    vermisst."""
    if not d or vorspann.ist_leer(d):
        return ""
    teile = []
    for kopf, feld in (
        (vorspann.T._UEBERSCHRIFT_WO_UND_WANN, "rahmen"),
        (vorspann.T._UEBERSCHRIFT_WORUM, "hauptkonflikt"),
        (vorspann.T._UEBERSCHRIFT_FORM, "format"),
    ):
        if d[feld]:
            teile.append(f"<h3>{_t(kopf)}</h3><p>{_t(d[feld])}</p>")
    if d["szenen"]:
        anzahl = len(d["szenen"])
        # Die Nummern kommen aus der Datenbank und muessen nicht bei 1
        # anfangen -- deshalb eine <ul> mit ausgeschriebener Nummer und keine
        # <ol>, die eine eigene, falsche Zaehlung darueberlegte.
        zeilen = "".join(
            "<li>{nr}. {titel}{form}</li>".format(
                nr=_t("—" if s["nummer"] is None else str(s["nummer"])),
                titel=_t(s["titel"], T._TEXT_OHNE_TITEL),
                form=(
                    f' <span class="zeit">({_t(_form_anzeige(s["form"]))})</span>'
                    if s["form"] else ""
                ),
            )
            for s in d["szenen"]
        )
        kopf = (
            vorspann.T._UEBERSCHRIFT_EINE_SZENE if anzahl == 1
            else vorspann.T._UEBERSCHRIFT_SZENEN
        ).format(anzahl=anzahl)
        teile.append(f"<h3>{_t(kopf)}</h3><ul>{zeilen}</ul>")
    if d["figuren"]:
        zeilen = "".join(
            "<li><b>{name}</b>{rest}</li>".format(
                name=_t(f["name"]),
                rest=f" — {_t(f['beschreibung'])}" if f["beschreibung"] else "",
            )
            for f in d["figuren"]
        )
        teile.append(f"<h3>{_t(vorspann.T._UEBERSCHRIFT_FIGUREN)}</h3><ul>{zeilen}</ul>")
    return f'<section class="vorspann">{"".join(teile)}</section>'


def _begriffe_html(begriffe: list[str] | None) -> str:
    """Die Kernbegriffe eines Interviews als Chips (06.09.2026).

    Sie stehen aufgeklappt ganz oben, vor der Zusammenfassung: die Frage
    \"worum geht es hier\" beantwortet der Begriff schneller als ein Absatz.
    Keine Begriffe heisst keine Zeile -- ein leerer Kasten waere ein Hinweis
    auf etwas, das die Gruppe nicht vermisst (sie hat vielleicht noch keine
    Begriffe festgelegt).

    Read-only: die Zuordnung entsteht beim Verdichten, nicht hier."""
    begriffe = [b for b in (begriffe or []) if b]
    if not begriffe:
        return ""
    chips = "".join(f'<span class="begriff">{_t(b)}</span>' for b in begriffe)
    return f'<div class="begriffe">{chips}</div>'


def _interview_html(v: dict) -> str:
    """Ein Interview als aufklappbarer Block (N6).

    **Die Summary-Zeile sind die Ergebnisse, nicht der Fliesstext**: je Thema
    die Kurzform, mit Mittelpunkten verbunden. Aufgeklappt steht je Thema das
    Belegzitat (nur geprueft, SPEC § 5) und darunter die Zusammenfassung.

    Bis dahin stand die ganze Verdichtung als Absatz da, und wer wissen
    wollte, was in fuenf Interviews steckt, musste fuenf Absaetze lesen."""
    kurzformen = [t["kurz"] for t in v["themen"] if t.get("kurz")]
    # Interview-Nummer statt Aufnahmename (Birk 05.09.: der Name ist ein
    # Klarname oder der Telegram-Name dessen, der das Handy hielt).
    summary = _t(v.get("bezeichnung") or v["name"], T._TEXT_INTERVIEW)
    if kurzformen:
        summary += SUMMARY_TRENNER + SUMMARY_TRENNER.join(_t(k) for k in kurzformen)
    # Je Aspekt eine Unterueberschrift (die Kurzform), darunter die
    # Erklaerung (das Ergebnis in einem Satz) und das Belegzitat -- so, wie
    # Birk es am 05.09. am Dashboard vermisst hat: "pro Interview alle
    # destillierten Aspekte als Unterueberschrift mit Verdichtung,
    # Erklaerung, Zitat".
    themen = "".join(
        '<div class="thema"><h4>{kurz}</h4><p>{thema}</p>{zitat}</div>'.format(
            kurz=_t(t.get("kurz") or t["thema"]),
            thema=_t(t["thema"]),
            zitat=f"<blockquote>{_zitat(t['zitat'])}</blockquote>" if t["zitat"] else "",
        )
        for t in v["themen"]
    )
    inhalt = (
        f'<p class="zeit">{_zeitpunkt(v.get("beginn"))}{_umfang(v["teile"], v["dauer_sekunden"])}</p>'
        + _begriffe_html(v.get("begriffe"))
        + (
            f'<p class="zusammenfassung">{_t(v["zusammenfassung"], "")}</p>{themen}'
            if v["zusammenfassung"]
            else f'<p class="leer">{_t(T._TEXT_NICHT_VERDICHTET)}</p>'
        )
    )
    return (
        f'<details class="verdichtung"><summary>{summary}</summary>{inhalt}</details>'
    )


# --- Der Buehne-Inhalt (Phase 4, nur Web, 02.10.2026) ----------------------
#
# EIN Render-Zweig, EIN Panel-Element (``#buehne-panel``) -- seit dem Merge
# von Karte W wandert er unveraendert in deren Tab-Leiste
# (``web_vereint.seite``, Tab "buehne", nur in Phase 4): diese Funktionen
# bauen nur noch den Panel-INHALT, die Tab-Mechanik selbst lebt dort.

def _buehne_status_text(daten: dict) -> str | None:
    """Die EINE Statuszeile ueber der Tafel -- genau diese Prioritaet, kein
    weiteres Signal (Task 1, Padua CoThinker-Tab clean, 03.10.2026):

    1. "thinking" -- NICHT implementiert. Die Erzeugungssperre
       (``brainstorm._LAEUFT``) lebt im Speicher des BOT-Prozesses; der
       Webserver oeffnet nur eine read-only DB-Verbindung und sieht sie
       strukturell nicht (dieselbe Grenze wie beim Szenenlauf-Lock, docs/agents/weboberflaeche.md
       "Die Phasenuebersicht"). Eine Zeitstempel-Heuristik waere ein
       geratener Zustand, der wie ein gemessener aussieht -- deshalb bleibt
       das hier eine dokumentierte Luecke fuer die separate, noch
       unzusammengefuehrte Karte ``cothinker_status.py``.
    2. "listening": eine Aufnahme dieser Gruppe laeuft gerade oder wartet auf
       Transkription (``aufnahme.status in ('empfangen', 'laeuft')`` --
       gesetzt von ``web_daten.gruppe_nach_token`` ueber
       ``_aufnahmen_nach_status``). Eigener Wortlaut, bewusst OHNE "hört zu"
       -- das ist der Zustand aus Schritt 3, nicht dieser.
    3. "nothing to add yet": die juengste Buehnenkarte war ein bewusstes
       Schweigen (``buehnenkarte.schweigen = 1``) -- dieselbe Erkennung wie
       vor diesem Umbau, nur das Rendering aendert sich.
    4. sonst: ``None`` -- keine Zeile, nie ein leeres ``<p>``."""
    if daten.get("buehne_aufnahme_laeuft"):
        return _t(T._TEXT_BUEHNE_AUFNAHME_LAEUFT)
    karten = daten.get("buehnenkarten") or []
    if karten and karten[0]["schweigen"]:
        return _t(T._TEXT_BUEHNE_HOERT_ZU)
    return None


def _buehne_alterszeile(erstellt_am: str | None) -> str:
    """Eine gedaempfte Alterszeile INNERHALB der Tafel -- NUR wenn die
    juengste Karte aelter als 5 Minuten ist. Unter 5 Minuten gibt es dieses
    Element im DOM gar nicht (Vertrag), kein leeres ``<span>``.

    Keine Bibliothek fuer relative Zeit: eine Minutenzahl reicht (Brief:
    "do not reinvent an elaborate relative-time library for '2 min ago'")."""
    gelesen = web_daten.lies_zeitstempel(erstellt_am) if erstellt_am else None
    if gelesen is None:
        return ""
    minuten = int((datetime.now(timezone.utc) - gelesen).total_seconds() // 60)
    if minuten < 5:
        return ""
    text = _t(T._TEXT_BUEHNE_ALTER.format(minuten=minuten))
    return f'<span class="buehne-alter">{text}</span>'


def _begriffsboard_html(eintraege: list[dict]) -> str:
    """Das Begriffsboard im CoThinker-Tab (Phase 1, Karte t_4517d4ad, D9):
    eine Liste in ``begriffsboard.sortiert``-Ordnung, die Top 5 mit
    ``data-top="1"``. Seit der Design-Erweiterung (Karte t_cb2c4678,
    04.10.2026, Birk: "nicht bloss funktional") zeigt eine Zeile NUR noch
    den Begriff -- Begruendung, Zitat und Doppelbedeutung bleiben in der
    Datenbank, stehen aber ohne ``<details>``/``<summary>`` in der Anzeige.
    Rang, Trennlinie zum Rest und die stille Kursivschrift fuer
    ``status="verworfen"`` haengen allein an den vorhandenen ``data-*``
    Attributen -- ``web_gestalt.css_buehne()`` macht daraus das Bild. Kein
    Zitat (``web_daten.begriffsboard`` laesst es weg), kein ``style=``,
    kein ``on…=`` (CSP).

    Eine Schärfungskette (``vorgaenger``, Karte t_cb2c4678) steht
    durchgestrichen hinter dem Begriff, der jüngste zuerst, und als
    ``data-vorgaenger`` am ``<li>`` -- für die FLIP-Zuordnung im Browser
    (``ladeBuehne()`` in ``web_vereint._VEREINT_JS``)."""
    from interview_theater import begriffsboard as _begriffsboard

    if not eintraege:
        return (
            '<div id="buehne-panel" data-ansicht="begriffsboard">'
            f'<p class="buehne-leer">{_t(T._TEXT_BOARD_LEER)}</p></div>'
        )
    oben = {_begriffsboard.schluessel(e["begriff"]) for e in _begriffsboard.top(eintraege)}
    zeilen = []
    for eintrag in _begriffsboard.sortiert(eintraege):
        begriff = html.escape(eintrag["begriff"], quote=True)
        top_merkmal = (' data-top="1"'
                       if _begriffsboard.schluessel(eintrag["begriff"]) in oben else "")
        kette = eintrag.get("vorgaenger") or []
        vorgaenger_merkmal = (
            f' data-vorgaenger="{html.escape(kette[-1], quote=True)}"' if kette else ""
        )
        # Der juengste Vorgaenger steht direkt neben dem neuen Begriff (D2,
        # Karte t_cb2c4678); der Pfeil kommt aus dem CSS
        # (``web_gestalt.css_buehne``), nie aus einem style-Attribut.
        vorgaenger_html = (
            '<span class="vorgaenger">'
            + " ".join(f"<del>{html.escape(v)}</del>" for v in reversed(kette))
            + "</span>"
            if kette else ""
        )
        zeilen.append(
            f'<li data-begriff="{begriff}" data-status="{html.escape(eintrag["status"])}" '
            f'data-zustimmung="{int(eintrag["zustimmung"])}" '
            f'data-nennungen="{int(eintrag["nennungen"])}"{vorgaenger_merkmal}{top_merkmal}>'
            f'<span class="begriff">{html.escape(eintrag["begriff"])}</span>'
            f'{vorgaenger_html}</li>'
        )
    return (
        '<div id="buehne-panel" data-ansicht="begriffsboard">'
        f'<ol class="begriffsboard">{"".join(zeilen)}</ol></div>'
    )


def _fragenuebersicht_html(eintraege: list[dict]) -> str:
    """Die Fragenuebersicht im CoThinker-Tab (Phase 2, Birk 05.10.2026):
    je Begriff eine Zeile mit den bisher gesetzten Fragen, in der
    Reihenfolge der Begriffe (``roadmap.fragenuebersicht``). Ein Begriff
    ohne Frage traegt ``data-offen="1"`` und eine leise Zeile -- **keine
    Soll-Zahl** ("0/3"): wie viele Fragen es werden, entscheidet die Gruppe.
    Das Bild macht ``web_gestalt.css_buehne()``; kein ``style=``, kein
    ``on…=`` (CSP)."""
    if not eintraege:
        return (
            '<div id="buehne-panel" data-ansicht="fragen">'
            f'<p class="buehne-leer">{_t(T._TEXT_FRAGEN_UEBERSICHT_LEER)}</p></div>'
        )
    zeilen = []
    for eintrag in eintraege:
        fragen = eintrag.get("fragen") or []
        if fragen:
            inhalt = (
                '<ul class="fragen">'
                + "".join(f"<li>{html.escape(f)}</li>" for f in fragen)
                + "</ul>"
            )
        else:
            inhalt = f'<p class="fragen-offen">{_t(T._TEXT_FRAGEN_UEBERSICHT_OFFEN)}</p>'
        offen = "" if fragen else ' data-offen="1"'
        # Die letzte Gruppe ohne Begriff (``begriff == ""``, Fragen ohne
        # erkennbaren Begriff, ``roadmap.fragenuebersicht``) traegt keinen
        # leeren Kopf -- die Zeilen stehen mit ihrem eigenen Vorsatz da.
        kopf = (f'<span class="begriff">{html.escape(eintrag["begriff"])}</span>'
                if eintrag["begriff"] else "")
        zeilen.append(
            f'<li data-begriff="{html.escape(eintrag["begriff"], quote=True)}"{offen}>'
            f'{kopf}{inhalt}</li>'
        )
    return (
        '<div id="buehne-panel" data-ansicht="fragen">'
        f'<h2 class="fragen-kopf">{_t(T._TEXT_FRAGEN_UEBERSICHT_KOPF)}</h2>'
        f'<ol class="fragenuebersicht">{"".join(zeilen)}</ol></div>'
    )


def _auswahlliste_html(daten: dict, liste: str) -> str:
    """Die Auswahlliste im CoThinker (Padua Phase 2, 05.10.2026) --
    generisch ueber ``liste`` (heute nur ``"fragen"``, Daten aus
    ``auswahl.fragen_liste``). Je Eintrag drei Knoepfe ✓/✗/✎ mit
    ``aria-pressed``; ein zweiter Tipp auf den gedrueckten Knopf nimmt die
    Entscheidung zurueck (das macht ``web_vereint._AUSWAHL_JS``). Kein
    ``k:<id>``-Knopf: der Tipp ist ein Feldwert (``chat/auswahl``). Alles
    maskiert, kein ``style=``, kein ``on…=`` (CSP)."""
    zaehler = daten.get("zaehler") or {}
    kopf = T._TEXT_AUSWAHL_ZAEHLER.format(
        **{k: int(zaehler.get(k) or 0) for k in ("ja", "nein", "schaerfen", "offen")}
    )
    knoepfe = (("ja", "✓", T._TEXT_AUSWAHL_JA), ("nein", "✗", T._TEXT_AUSWAHL_NEIN),
               ("schaerfen", "✎", T._TEXT_AUSWAHL_SCHAERFEN))
    herkunft = {"eigen": T._TEXT_AUSWAHL_EIGEN, "ki": T._TEXT_AUSWAHL_KI}
    teile = [
        f'<div id="buehne-panel" data-ansicht="auswahl" '
        f'data-liste="{html.escape(liste, quote=True)}">',
        f'<p class="auswahl-zaehler">{html.escape(kopf)}</p>',
    ]
    for gruppe in daten.get("gruppen") or []:
        if gruppe.get("titel"):
            teile.append(f'<h3 class="auswahl-titel">{html.escape(gruppe["titel"])}</h3>')
        zeilen = []
        for eintrag in gruppe.get("eintraege") or []:
            zustand = eintrag.get("zustand") or ""
            marke = herkunft.get(eintrag.get("herkunft") or "")
            marke_html = f' <span class="herkunft">{html.escape(marke)}</span>' if marke else ""
            reihe = "".join(
                f'<button type="button" class="auswahl-knopf" data-wert="{wert}" '
                f'aria-pressed="{"true" if wert == zustand else "false"}" '
                f'aria-label="{html.escape(name, quote=True)}">{zeichen}</button>'
                for wert, zeichen, name in knoepfe
            )
            zeilen.append(
                f'<li data-nummer="{int(eintrag["nummer"])}" '
                f'data-zustand="{html.escape(zustand or "offen", quote=True)}">'
                f'<span class="auswahl-text">{html.escape(eintrag.get("text") or "")}'
                f'{marke_html}</span>'
                f'<span class="auswahl-knoepfe">{reihe}</span></li>'
            )
        if zeilen:
            teile.append(f'<ul class="auswahl">{"".join(zeilen)}</ul>')
    teile.append(
        f'<button type="button" class="auswahl-fertig">'
        f'{html.escape(T._TEXT_AUSWAHL_FERTIG)}</button></div>'
    )
    return "".join(teile)


def _schaerfungsliste_html(daten: dict) -> str:
    """Die Schaerfungs-Sortierliste im CoThinker (Padua Phase 5, 07.10.2026,
    Birk: "der 'Show more'-Knopf ist unsinnig, besser eine Auswahl wie bei
    den Begriffen -- Yes/No-Knopf, alle als Uebersicht zum Durchscrollen").

    Dieselbe Bauweise wie ``_auswahlliste_html`` (``#buehne-panel
    data-ansicht="auswahl"``, ``ul.auswahl`` mit ``.auswahl-knopf``/
    ``.auswahl-fertig``) -- dieselbe Browser-Logik (``web_vereint._AUSWAHL_JS``)
    bedient beide Listen ueber ``data-liste``. Nur zwei Knoepfe (Yes/No,
    keine dritte "Umformulieren"-Option wie bei den Fragen) und reichere
    Zeilen: Zusammenfassung, Interview-Nummer, das volle gepruefte Zitat,
    die Begruendung -- alles, was bis zu diesem Umbau auf den seitenweisen
    Chat-Karten stand, jetzt auf einmal zum Durchscrollen."""
    zaehler = daten.get("zaehler") or {}
    kopf = T._TEXT_SCHAERFUNGSLISTE_ZAEHLER.format(
        **{k: int(zaehler.get(k) or 0) for k in ("ja", "nein", "offen")}
    )
    knoepfe = (("ja", "✓", T._TEXT_SCHAERFUNGSLISTE_JA), ("nein", "✗", T._TEXT_SCHAERFUNGSLISTE_NEIN))
    teile = [
        '<div id="buehne-panel" data-ansicht="auswahl" data-liste="schaerfung">',
        f'<p class="schaerfung-erklaerung">{html.escape(T._TEXT_SCHAERFUNGSLISTE_ERKLAERUNG)}</p>',
        f'<p class="auswahl-zaehler">{html.escape(kopf)}</p>',
    ]
    for gruppe in daten.get("gruppen") or []:
        if gruppe.get("art") == "szene":
            titel = T._TEXT_SCHAERFUNGSLISTE_SZENE.format(nummer=gruppe["nummer"])
            if gruppe.get("titel"):
                titel += f": {gruppe['titel']}"
        else:
            titel = gruppe.get("name") or ""
        anzahl = len(gruppe.get("eintraege") or [])
        teile.append(
            f'<h3 class="auswahl-titel">{html.escape(titel)}'
            f' <span class="herkunft">· {html.escape(T._TEXT_SCHAERFUNGSLISTE_ANZAHL.format(anzahl=anzahl))}</span></h3>'
        )
        zeilen = []
        for eintrag in gruppe.get("eintraege") or []:
            zustand = eintrag.get("zustand") or ""
            reihe = "".join(
                f'<button type="button" class="auswahl-knopf" data-wert="{wert}" '
                f'aria-pressed="{"true" if wert == zustand else "false"}" '
                f'aria-label="{html.escape(name, quote=True)}">{zeichen}</button>'
                for wert, zeichen, name in knoepfe
            )
            interview = eintrag.get("interview") or ""
            interview_html = (
                f' <span class="herkunft">{html.escape(interview)}</span>' if interview else ""
            )
            begruendung = (eintrag.get("begruendung") or "").strip()
            begruendung_html = (
                f'<p class="schaerfung-verbindung">→ {html.escape(begruendung)}</p>'
                if begruendung else ""
            )
            zeilen.append(
                f'<li data-nummer="{int(eintrag["id"])}" '
                f'data-zustand="{html.escape(zustand or "offen", quote=True)}">'
                f'<span class="auswahl-text">'
                f'{begruendung_html}'
                f'<blockquote class="schaerfung-zitat">'
                f'„{html.escape(eintrag.get("zitat") or "")}“</blockquote>'
                f'<span class="schaerfung-quelle">{html.escape(eintrag.get("titel") or "")}{interview_html}</span>'
                f'</span>'
                f'<span class="auswahl-knoepfe">{reihe}</span></li>'
            )
        if zeilen:
            teile.append(f'<ul class="auswahl">{"".join(zeilen)}</ul>')
    teile.append(
        f'<button type="button" class="auswahl-fertig">'
        f'{html.escape(T._TEXT_SCHAERFUNGSLISTE_FERTIG)}</button></div>'
    )
    return "".join(teile)


#: Die EINE sichere Markdown-Teilmenge einer Buehnenkarte (Birk 06.10.2026,
#: Live-Test P4: das Modell schreibt ``**fett**``/``*kursiv*``/``- Punkte``,
#: die Tafel zeigte das bisher roh -- Sternchen sichtbar, keine Absaetze).
#: Maskiert IMMER zuerst (``html.escape``), wendet DANACH nur diese zwei
#: Ersetzungen auf eine bereits maskierte Zeile an -- nie umgekehrt, sonst
#: waere ein woertliches ``<script>`` im Kartentext ein XSS-Weg. Fett vor
#: kursiv: sonst fraesse die Kursiv-Regel die Sternpaare der Fett-Regel an.
#: Dieselbe Teilmenge, dieselbe Reihenfolge wie ``buehneMarkdown`` in
#: ``web_vereint._VEREINT_JS`` (Browser-Verlauf, bisher ``textContent``).
_BUEHNE_FETT = re.compile(r"\*\*([^*]+)\*\*")
_BUEHNE_KURSIV = re.compile(r"\*([^*]+)\*")
#: Eine Zeile, die GENAU EIN Fett-Paar ist und nichts sonst -- das wird eine
#: Blockueberschrift, keine Flieszeile (Brief: "a line that is only a bold
#: label"). ``[^*]+`` im Inneren verhindert einen Treffer bei zwei Fett-
#: Spannen auf derselben Zeile.
_BUEHNE_UEBERSCHRIFT = re.compile(r"^\*\*([^*]+)\*\*$")


def _buehne_inline(zeile: str) -> str:
    """Fett/kursiv auf einer bereits HTML-maskierten Zeile."""
    zeile = _BUEHNE_FETT.sub(r"<strong>\1</strong>", zeile)
    return _BUEHNE_KURSIV.sub(r"<em>\1</em>", zeile)


def _buehne_markdown(text: str) -> str:
    """Rendert eine Buehnenkarte als kleine HTML-Teilmenge statt als
    Rohtext mit ``white-space: pre-wrap`` (siehe ``_CSS_BUEHNE``, die Regel
    ist mit diesem Umbau raus). Leerzeilen trennen Absaetze, ``- ``/``• ``
    leitet eine Aufzaehlung ein (fortlaufende Treffer werden zu EINER
    ``<ul>``), eine Zeile aus genau einem ``**Label**`` wird eine
    Blockueberschrift -- alles andere ein ``<p>``."""
    bloecke: list[str] = []
    liste: list[str] = []

    def schliesse_liste() -> None:
        if liste:
            bloecke.append("<ul>" + "".join(f"<li>{z}</li>" for z in liste) + "</ul>")
            liste.clear()

    for rohzeile in html.escape(text or "").split("\n"):
        zeile = rohzeile.strip()
        if not zeile:
            schliesse_liste()
            continue
        aufzaehlung = re.match(r"^(?:-|•)\s+(.+)$", zeile)
        if aufzaehlung:
            liste.append(_buehne_inline(aufzaehlung.group(1)))
            continue
        schliesse_liste()
        ueberschrift = _BUEHNE_UEBERSCHRIFT.match(zeile)
        if ueberschrift:
            bloecke.append(f'<p class="buehne-ueberschrift"><strong>{ueberschrift.group(1)}</strong></p>')
            continue
        bloecke.append(f"<p>{_buehne_inline(zeile)}</p>")
    schliesse_liste()
    return "".join(bloecke)


def _buehne_html(daten: dict) -> str:
    """Die CoThinker-Tafel: GENAU EINE Karte auf einmal, mit Browser-
    seitiger Verlaufsnavigation (Task 1, Padua CoThinker-Tab clean,
    03.10.2026 -- Portierung aus ``cothinker/stage/stage.py``s ``verlauf``/
    ``pos``/``male``/``zeige``/``blaettern``/``verlaufUebernehmen``, siehe
    ``_VEREINT_JS`` fuer die Browserseite und den Report fuer die
    Abweichungen).

    Ersetzt die gestapelte Kartenliste samt Stueckkarte-Streifen: Setting,
    Figuren, Geschichte und die freien Festlegungen stehen bereits im
    Stand-Tab (``_stueckkarte_html``, ``_festlegungen_html``) -- eine dritte
    Kopie in diesem Panel war genau die Duplikation, die der Umbau
    beseitigt.

    **Der Vertrag** (Task-1-Brief, bindend fuer ``_VEREINT_JS``/Task 2):
    jeder Baustein faellt weg, wenn sein Inhalt leer waere -- niemals eine
    leere Statuszeile, niemals ein leerer Nav-Platzhalter, niemals eine
    zweite sichtbare Karte. Gerufen von ``web_vereint.seite`` (Tab "buehne",
    Sichtbarkeit ueber ``hidden``) UND von ``web_vereint.sende_teil`` fuer
    jeden Poll-Takt -- eine Renderfunktion, eine Quelle fuer beide.

    Eine Schweigen-Zeile (``buehnenkarte.schweigen = 1``) ist keine Karte --
    sie traegt leeren Text und zaehlt nirgends mit (gleiche Erkennung wie
    vor diesem Umbau, siehe ``_buehne_status_text``)."""
    if daten.get("begriffsboard_zeigen"):
        # Phase 1 (Karte t_4517d4ad): der CoThinker zeigt das Begriffsboard
        # statt der Buehnenkarten -- eine Renderfunktion fuer Seite UND Poll.
        return _begriffsboard_html(daten.get("begriffsboard") or [])
    if daten.get("auswahlliste"):
        # Phase 2 unter Padua, sobald eine Auswahl steht: sortieren statt
        # nur ansehen (05.10.2026).
        return _auswahlliste_html(daten["auswahlliste"], liste="fragen")
    if daten.get("schaerfungsliste"):
        # Phase 5 unter Padua, sobald das Mapping gelaufen ist (07.10.2026,
        # "Show more" war unsinnig): Yes/No-Sortierliste statt Seite fuer
        # Seite im Chat.
        return _schaerfungsliste_html(daten["schaerfungsliste"])
    if daten.get("szenenkarten") is not None:
        # Phase 6 unter Padua mit Karten (Birk 07.10.2026 ~19:25).
        return _szenenkarten_html(daten["szenenkarten"])
    if daten.get("fragenuebersicht_zeigen"):
        # Phase 2 (Birk, 05.10.2026): was je Begriff an Fragen steht.
        return _fragenuebersicht_html(daten.get("fragenuebersicht") or [])
    karten = daten.get("buehnenkarten") or []
    # ``karten`` kommt NEUESTE ZUERST (web_daten.buehnenkarten, ORDER BY id
    # DESC) -- fuer die Tafel reicht das erste echte Element, fuer den
    # JSON-Datenbaustein unten wird die Reihenfolge umgedreht.
    echte_neueste_zuerst = [k for k in karten if not k["schweigen"]]

    teile = []
    status = _buehne_status_text(daten)
    if status:
        teile.append(f'<p id="buehne-status">{status}</p>')

    if echte_neueste_zuerst:
        neueste = echte_neueste_zuerst[0]
        # Die kleine Markdown-Teilmenge (``_buehne_markdown``, Birk
        # 06.10.2026) statt rohem Text -- dieselbe Funktion, die die JS beim
        # Zurueckblaettern per ``buehneMarkdown`` aufruft (siehe dort): SSR
        # und Client-Rendering sehen damit gleich aus.
        text = _buehne_markdown(neueste["text"] or "")
        alter = _buehne_alterszeile(neueste["erstellt_am"])
        teile.append(f'<div id="buehne-tafel">{text}{alter}</div>')

    if len(echte_neueste_zuerst) >= 2:
        # Der Inhalt kommt NIE vom Server -- ``_VEREINT_JS`` fuellt ihn aus
        # dem JSON-Baustein unten, genau wie CoThinkers ``male()`` die
        # ``#verlauf``-Leiste komplett selbst besitzt. Deshalb ist ein
        # leerer Platzhalter hier sicher: der erste Skriptlauf ersetzt ihn
        # sofort.
        teile.append('<div id="buehne-nav"></div>')

    if echte_neueste_zuerst:
        aeltest_zuerst = list(reversed(echte_neueste_zuerst))
        # ``zurueck_text``/``neu_praefix`` kommen RAW (nicht durch ``_t()``
        # HTML-escaped) in die JSON-Nutzlast -- ``_t()`` ist in diesem Modul
        # die HTML-Maskierung, keine Uebersetzung (die leistet ``T``/
        # ``_TEXT_*`` bereits). Eine zusaetzliche HTML-Maskierung vor
        # ``json.dumps`` wuerde doppelt maskieren, sobald die JS ihrerseits
        # vor dem Einfuegen in ``innerHTML`` escaped (siehe Report). Die
        # Lokalisierung selbst ist damit trotzdem vollstaendig: beide Werte
        # kommen aus ``T``, also schon in der aktiven Sprache.
        payload = {
            "karten": [
                {"id": k["id"], "text": k["text"] or ""} for k in aeltest_zuerst
            ],
            "zurueck_text": T._TEXT_BUEHNE_ZURUECK,
            "neu_praefix": T._TEXT_BUEHNE_NEU_PRAEFIX,
        }
        # ``</`` wird entschaerft (``<\/``), damit eine Karte, deren Text
        # woertlich ``</script`` enthaelt, dieses Skript-Element nicht
        # vorzeitig beendet -- der Tokenizer des Browsers reagiert auf die
        # rohen Bytes, nicht auf die JSON-Maskierung innerhalb der Anfuehrungszeichen.
        # ``\/`` ist eine gueltige JSON-Escape-Sequenz (dekodiert zu ``/``),
        # derselbe Weg wie ``web_vereint._js_text`` und das inline
        # ``.replace("</", "<\\/")`` in ``web_chat.py``.
        teile.append(
            '<script type="application/json" id="buehne-verlauf-daten">'
            + json.dumps(payload, ensure_ascii=True).replace("</", "<\\/")
            + "</script>"
        )

    if not status and not echte_neueste_zuerst:
        teile.append(f'<p class="buehne-leer">{_t(T._TEXT_BUEHNE_LEER)}</p>')

    status_html = _cothinker_status_html(daten.get("cothinker_status"))
    return f'{status_html}<div id="buehne-panel">{"".join(teile)}</div>'


def _journal_html(eintraege: list[dict]) -> str:
    """Die Journalzeilen -- herausgeloest aus ``gruppe_koerper`` (Werkbank,
    03.10.2026), Zeichen fuer Zeichen dieselben."""
    return "".join(
        '<div class="eintrag"><span class="art">{art}</span>{text} '
        '<span class="zeit">{zeit}</span></div>'.format(
            art=_t(T.JOURNALART_BESCHRIFTUNG.get(e["art"], e["art"])),
            text=_t(e["text"]),
            zeit=_zeitpunkt(e["erstellt_am"]),
        )
        for e in eintraege
    ) or f'<p class="leer">{_t(T._TEXT_NICHTS_NOTIERT)}</p>'


def _recherche_html(eintraege: list[dict]) -> str:
    """Die Recherchekarten -- herausgeloest wie ``_journal_html`` (Karte
    t_c5117c91). Eigener Abschnitt, unabhaengig von den sieben Phasen."""
    if not eintraege:
        return f'<p class="leer">{_t(T._TEXT_RECHERCHE_LEER)}</p>'
    return "".join(
        '<div class="eintrag"><p class="frage">{frage}</p><p>{text}</p>{quellen}</div>'.format(
            frage=_t(e["frage"]),
            text=_t(e["ergebnis_text"]),
            quellen=(
                f'<p class="quellen">'
                f'{_t(T._TEXT_RECHERCHE_QUELLEN.format(quellen=", ".join(e["quellen"])))}'
                "</p>" if e.get("quellen") else ""
            ),
        )
        for e in eintraege
    )


def _wb_status_text(status: str) -> str:
    from interview_theater import roadmap

    return {
        roadmap.ERLEDIGT: T._TEXT_STATUS_ERLEDIGT,
        roadmap.OFFEN: T._TEXT_STATUS_OFFEN,
        roadmap.SPAETER: T._TEXT_STATUS_SPAETER,
    }[status]


def _wb_zeilentext(z: dict) -> str:
    """Aufgaben tragen ihren Text schon (``phasentexte.beschriftung``),
    Detailzeilen werden hier beschriftet -- ``roadmap`` bleibt textfrei."""
    from interview_theater import roadmap

    if z["art"] == "aufgabe":
        return z["text"] or ""
    vorlage = {
        "diskussion": T._TEXT_WB_DISKUSSION,
        "interview": (T._TEXT_WB_INTERVIEW_FERTIG if z["status"] == roadmap.ERLEDIGT
                      else T._TEXT_WB_INTERVIEW_OFFEN),
        "prosa": T._TEXT_WB_PROSA,
        "gesamttext": T._TEXT_WB_GESAMTTEXT,
        "ueberarbeitet": T._TEXT_WB_UEBERARBEITET,
        "form": T._TEXT_WB_FORM,
        "sprechweise": T._TEXT_WB_SPRECHWEISE,
    }[z["kennung"]]
    text = vorlage.format(bezug="" if z.get("bezug") is None else z["bezug"])
    if z.get("titel"):
        text += SUMMARY_TRENNER + z["titel"]
    return text


def _wb_zeile_html(z: dict) -> str:
    """Eine Attributzeile: Punkt (Form + Farbe + aria-label), Text, und bei
    einer laufenden Aufgabe das Wort 'running' -- keine eigene Farbe."""
    status = z["status"]
    laeuft = (
        f' <span class="wb-laeuft">{_t(T._TEXT_WERKBANK_LAEUFT)}</span>'
        if z.get("laeuft") else ""
    )
    return (
        f'<li class="wb-zeile wb-{status}" data-kennung="{_t(z["kennung"])}">'
        f'<span class="wb-punkt wb-{status}" role="img" '
        f'aria-label="{_t(_wb_status_text(status))}"></span>'
        f"<span>{_t(_wb_zeilentext(z))}</span>{laeuft}</li>"
    )


def _cothinker_status_html(status: dict | None) -> str:
    """Die Statuszeile UEBER dem Buehne-Panel (CoThinker-Statuszeile,
    03.10.2026) -- leer, wenn gerade nichts zu zeigen ist (``status`` ist
    ``None``: ausserhalb Phase 4, oder eine Gruppe, die diesen Zustand noch
    nie erreicht hat).

    Die tickende Dauer selbst steht NIE hier: ``data-seit`` traegt den
    rohen ISO-Zeitstempel, Javascript (``web_vereint._VEREINT_JS``)
    berechnet die Differenz jede Sekunde neu und schreibt sie ins anfangs
    leere ``.co-dauer``-Element -- sonst aenderte sich dieser HTML-String
    jede Sekunde und ``web_vereint.py``s ``ladeBuehne()`` taeuschte sich bei
    jedem Poll eine echte Aenderung vor und tauschte das ganze Panel
    unnoetig aus.

    Die Texte werden bei jedem Aufruf frisch ueber ``T._TEXT_COTHINKER_*``
    aufgeloest statt ueber ein beim Modulimport eingefrorenes Dict: der
    Webdienst laeuft fuer alle Gruppen in einem Prozess, und
    ``sprache.code()`` haengt am aktiven Profil (dieselbe Begruendung wie
    bei ``web_gestalt._mikrotexte``)."""
    if not status:
        return ""
    zustand = status["zustand"]
    seit = status.get("seit") or ""
    tickt = zustand in cothinker_status.TICKT
    texte = {
        cothinker_status.ZUSTAND_DENKT: T._TEXT_COTHINKER_DENKT,
        cothinker_status.ZUSTAND_TRANSKRIBIERT: T._TEXT_COTHINKER_TRANSKRIBIERT,
        cothinker_status.ZUSTAND_HOERT: T._TEXT_COTHINKER_HOERT,
        cothinker_status.ZUSTAND_SCHWEIGT: T._TEXT_COTHINKER_SCHWEIGT,
    }
    text = _t(texte.get(zustand, zustand))
    tickt_attr = ' data-tickt="1"' if tickt else ""
    return (
        f'<div id="cothinker-status" class="co-status co-{html.escape(zustand)}" '
        f'data-zustand="{html.escape(zustand)}" data-seit="{html.escape(seit)}">'
        f'<span class="co-icon" aria-hidden="true"></span>'
        f'<span class="co-text">{text}</span>'
        f'<span class="co-dauer"{tickt_attr}></span>'
        f'</div>'
    )


def _buehnenkarte_html(karte: dict, erste: bool) -> str:
    klasse = "karte" if erste else "karte alt"
    text = html.escape(karte["text"] or "").replace("\n", "<br>")
    return (
        f'<div class="{klasse}">{text}'
        f'<span class="zeit">{_zeitpunkt(karte["erstellt_am"])}</span></div>'
    )


def _auch_vereinbart_html(daten: dict, szenen_anzahl: str | None) -> str:
    """Freie Festlegungen und die Szenenzahl -- read-only, OHNE eigene
    Ueberschrift (Birk 06.10.2026: 'Also agreed' war ueberfluessig, die
    Sektion soll direkt unter den anderen Kategorien von Phase 4 stehen,
    als Teil derselben Liste statt eines eigenen Blocks)."""
    zeilen = []
    if szenen_anzahl:
        zeilen.append(
            '<div class="festlegung"><span class="marke">{marke}</span>'
            "<span>{wert}</span></div>".format(
                marke=_t(T._STUECKKARTE_SZENENANZAHL), wert=_t(szenen_anzahl))
        )
    if daten.get("festlegungen"):
        zeilen.append(_festlegungen_html(daten, None))
    return "".join(zeilen)


def _wb_inhalt_html(nummer: int, daten: dict, werkbank: dict) -> str:
    """Was unter den Punkten einer Phase steht -- read-only, aus denselben
    Bausteinen wie die bisherige Gruppenseite (keine zweite Formatierung):
    1 die Begriffe (und ``begriffe_detail``, wenn es sie gibt), 2 Fragen,
    A/B-Zeile und Leitfaden (``pre.leitfaden`` liest der Interview-Modus),
    3 die Verdichtungen wie bisher, 4 Setting, Geschichte, Figuren,
    Szenenkoepfe und "Also agreed", 6 die Dramaturgie-Pruefung, 7 die
    Sprechanteile. Keine Szenen-Volltexte -- die stehen im Script-Tab."""
    stand = daten["arbeitsstand"]
    dt = T.ARBEITSSTAND_BESCHRIFTUNG
    teile: list[str] = []
    if nummer == 1:
        if (stand.get("begriffe") or "").strip():
            teile.append(f"<p>{_t(stand['begriffe'])}</p>")
        detail = werkbank.get("begriffe_detail") or []
        if detail:
            teile.append('<dl class="wb-begriffe">' + "".join(
                f"<dt>{_t(b['begriff'])}</dt>"
                + (f"<dd>{_t(b['begruendung'])}</dd>" if b["begruendung"] else "")
                + (f'<dd class="zeit">{_t(b["doppelbedeutung"])}</dd>'
                   if b["doppelbedeutung"] else "")
                for b in detail
            ) + "</dl>")
    elif nummer == 2:
        if (stand.get("fragen") or "").strip():
            teile.append(_fragen_html(stand["fragen"]))
        teile.append(_fragen_auswertung_html(daten.get("fragen_auswertung")))
        leitfaden = _leitfaden_html(stand, daten.get("web_token"))
        if leitfaden:
            teile.append(f"<dl>{leitfaden}</dl>")
    elif nummer == 3:
        teile.append("".join(_interview_html(v) for v in daten["interviews"]))
    elif nummer == 4:
        zeilen = [
            f"<dt>{_t(dt[feld])}</dt><dd>{_t(stand[feld])}</dd>"
            for feld in ("rahmen", "format", "geschichte")
            if (stand.get(feld) or "").strip()
        ]
        # Birk 07.10.2026 ~16:30: das Format und die Formen, die der
        # Formberater fuer die Gruppe nachgeschlagen hat, standen nirgends
        # auf der Workbench.
        if daten.get("formen_nah"):
            zeilen.append(f"<dt>{_t(dt['formen_nah'])}</dt><dd>{_t(daten['formen_nah'])}</dd>")
        zeilen.append(_altbestand_html(stand))
        if daten["figuren"]:
            figuren = "".join(
                "<li><b>{name}</b>{rest}</li>".format(
                    name=_t(f["name"]),
                    rest=(f" — {_t(vorspann.erster_satz(f.get('beschreibung')))}"
                          if (f.get("beschreibung") or "").strip() else ""),
                )
                for f in daten["figuren"]
            )
            zeilen.append(f'<dt>{_t(dt["figuren"])}</dt><dd><ul class="figuren">{figuren}</ul></dd>')
        if daten["szenen"] and daten["szenen"][0].get("verdichtet") is not None:
            zeilen.append(
                f"<dt>{_t(T._UEBERSCHRIFT_SZENEN)}</dt>"
                f"<dd>{_wb_szenen_verdichtet_html(daten['szenen'])}</dd>"
            )
        elif daten["szenen"]:
            # Birk 07.10.2026 15:00: je Szene auch, was darin passiert --
            # nur Titel sagte der Gruppe nicht, ob ihre Beschreibung
            # gespeichert ist. Leere Beschreibung -> nur der Titel wie bisher.
            szenen = "".join(
                "<li><b>{nr}. {titel}</b>{rest}</li>".format(
                    nr=_t("—" if s["nummer"] is None else str(s["nummer"])),
                    titel=_t(s.get("titel"), T._TEXT_OHNE_TITEL),
                    rest=(f" — {_t((s.get('was_passiert') or s.get('kurzbeschreibung') or '').strip())}"
                          if (s.get("was_passiert") or s.get("kurzbeschreibung") or "").strip() else ""),
                )
                for s in daten["szenen"]
            )
            zeilen.append(f"<dt>{_t(T._UEBERSCHRIFT_SZENEN)}</dt><dd><ul>{szenen}</ul></dd>")
        if any(zeilen):
            teile.append(f"<dl>{''.join(zeilen)}</dl>")
        # Die Szenenzahl nur, solange es noch keine Szenen gibt -- sonst
        # steht dieselbe Information doppelt (Birk 07.10.2026 15:00).
        teile.append(_auch_vereinbart_html(
            daten, None if daten["szenen"] else werkbank.get("szenen_anzahl")))
    elif nummer == 6:
        teile.append(_dramaturgie_html(daten.get("dramaturgie")))
    elif nummer == 7:
        teile.append(_sprechanteile_html(daten.get("sprechanteile")))
    inhalt = "".join(t for t in teile if t)
    return f'<div class="wb-inhalt">{inhalt}</div>' if inhalt else ""


def werkbank_koerper(daten: dict) -> str:
    """Der Arbeitsstand als reine Statusansicht (Padua, 03.10.2026, Karte
    t_49e7354c) -- statt ``gruppe_koerper``, wenn das Profil
    ``[web] workbench_bearbeitbar = false`` setzt.

    EINE Achse: die sieben Phasen in Reihenfolge, je ein ``<details>`` mit
    Zaehler, darunter die Attribute mit einem Punkt aus drei Formen
    (``roadmap.werkbank``). Aufgeklappt ist allein die aktuelle Phase. Kein
    Formular, kein Knopf, kein Nonce: geaendert wird im Chat. Keine
    Phasenanzeige, kein Probenansicht- und kein Chat-Link -- die Kopfleiste
    der Seite zeigt die Phase (Birk: "die Anzeige der aktuellen Phase ist
    doppelt")."""
    werkbank = daten.get("werkbank") or {}
    titel = daten["titel"] or T._TEXT_GRUPPE.format(chat_id=daten["chat_id"])
    bloecke = []
    for phase in werkbank.get("phasen") or []:
        zahl = T._TEXT_WERKBANK_ZAHL.format(erledigt=phase["erledigt"], gesamt=phase["gesamt"])
        haken = (
            ' <span class="wb-fertig" aria-hidden="true">✓</span>' if phase["fertig"] else ""
        )
        offen = " open" if phase["aktiv"] else ""
        zeilen = "".join(_wb_zeile_html(z) for z in phase["zeilen"])
        bloecke.append(
            f'<details class="wb-phase" data-wb-phase="{phase["nummer"]}"{offen}>'
            f'<summary><span class="wb-name">{_t(phase["bezeichnung"])}</span>{haken}'
            f'<span class="wb-zahl">{_t(zahl)}</span></summary>'
            f'<ul class="wb-zeilen">{zeilen}</ul>'
            f"{_wb_inhalt_html(phase['nummer'], daten, werkbank)}"
            "</details>"
        )
    journal = (
        '<details class="wb-journal"><summary>'
        f"{_t(T._UEBERSCHRIFT_WEG)}{SUMMARY_TRENNER}"
        f"{_t(T._TEXT_JOURNAL.format(anzahl=len(daten['journal'])))}</summary>"
        f"{_journal_html(daten['journal'])}</details>"
    )
    recherche = (
        '<details class="wb-recherche"><summary>'
        f"{_t(T._UEBERSCHRIFT_RECHERCHE)}</summary>"
        f"{_recherche_html(werkbank.get('recherche') or [])}</details>"
    )
    return (
        f"<h1>{_t(titel)}</h1>\n"
        '<div id="stand-inhalt" class="werkbank">\n'
        f'<p class="wb-hinweis">{_t(T._TEXT_WERKBANK_HINWEIS)}</p>\n'
        + "\n".join(bloecke)
        + f"\n{journal}\n{recherche}\n</div>\n"
    )


def gruppe_koerper(
    daten: dict,
    nonce_wert: str | None = None,
    token: str | None = None,
    praefix: str = VORGABE_PRAEFIX,
    fassungswahl: dict[int, int] | None = None,
) -> str:
    """Der Rumpf der Gruppenseite -- ohne die Klammer aus ``_seite``.

    Herausgeloest fuer die vereinte Seite (30.09.2026, Karte W): dort steht
    dieser Rumpf als eines von drei Panels in EINEM Dokument. ``gruppe_html``
    ruft ihn und haengt die Klammer davor -- die Einzelseite bleibt damit
    Zeichen fuer Zeichen, was sie war (``tests/test_web_koerper.py``)."""
    from interview_theater import workshop

    if not workshop.workbench_bearbeitbar():
        # Padua (03.10.2026): reine Statusansicht. Der Nonce wird hier nicht
        # gebraucht -- auf der vereinten Seite steht er im Chat-Panel.
        return werkbank_koerper(daten)

    fassungen = daten.get("fassungen") or {}
    fassungswahl = fassungswahl or {}
    szenen = "".join(
        _szene_html(
            s,
            daten["figuren"] if nonce_wert else None,
            fassungen.get(s.get("id")),
            fassungswahl.get(s.get("id")),
        )
        for s in daten["szenen"]
    ) or f'<p class="leer">{_t(T._TEXT_KEINE_SZENE)}</p>'
    # Die Uebersicht steht VOR den aufklappbaren Bloecken (06.09.2026, Birk)
    # und dupliziert sie nicht: dort die Zusammenfassung in einer Zeile je
    # Szene, darunter die Planung mit ihren Formularfeldern.
    uebersicht = _szenenuebersicht_html(daten.get("szenenuebersicht") or [])

    verdichtungen_html = "".join(
        _interview_html(v) for v in daten["interviews"]
    ) or f'<p class="leer">{_t(T._TEXT_KEIN_INTERVIEW_NOCH)}</p>'

    journal = _journal_html(daten["journal"])

    titel = daten["titel"] or T._TEXT_GRUPPE.format(chat_id=daten["chat_id"])
    stand = (
        _bearbeiten_html(daten, nonce_wert)
        if nonce_wert
        else _arbeitsstand_html(
            daten["arbeitsstand"], daten["figuren"], mit_stimmen=True,
            token=daten.get("web_token"),
        )
    )
    # Der Vorspann steht GANZ OBEN (07.09.2026): er ist die Antwort auf die
    # Frage, die jemand hat, der die Seite zum ersten Mal aufmacht -- wo
    # spielt das, worum geht es, wer sind die dreizehn Namen weiter unten.
    kopf = _vorspann_html(daten.get("vorspann"))
    if kopf:
        kopf = f"<h2>{_t(T._UEBERSCHRIFT_UEBERBLICK)}</h2>{kopf}\n"
    return (
        f"<h1>{_t(titel)}</h1>\n"
        f"{_chat_link(token, daten.get('kanal'))}"
        f'<div id="stand-inhalt">\n'
        f"{kopf}"
        # „Was noch fehlt" ist dieselbe Datenlage in der anderen Richtung
        # (06.09.2026). Seit P2, Aufgabe 3 steht es VOR dem Arbeitsstand:
        # es ist das, was die Gruppe als Naechstes tut, und unter den
        # Formularen (vier Felder je Figur) kam man am Telefon erst nach
        # zwei Bildschirmen dort an. Fehlt nichts, fehlt auch der Abschnitt.
        f"{_fehlstellen_html(daten.get('fehlstellen'))}\n"
        f"<h2>{_t(T._UEBERSCHRIFT_ARBEITSSTAND)}</h2>"
        f"{stand}\n"
        # Eigene vs. KI-Fragen (Aufgabe 14) -- dieselbe Zeile wie auf dem
        # Dashboard, nichts, solange der A/B-Vergleich fuer diese Gruppe nie
        # lief.
        f"{_fragen_auswertung_html(daten.get('fragen_auswertung'))}\n"
        # Die Stueckkarte (02.10.2026) steht direkt ueber den freien
        # Festlegungen -- zusammen zeigen beide, was feststeht und was
        # daneben noch gilt.
        f"<h2>{_t(T._UEBERSCHRIFT_STUECKKARTE)}</h2>"
        f"{_stueckkarte_html(daten)}\n"
        # Direkt hinter dem Arbeitsstand -- an derselben Stelle wie im
        # Prompt (kontext._REIHENFOLGE): was die Gruppe auf ihrer Seite
        # liest, soll da stehen, wo das Modell es auch liest.
        f"<h2>{_t(T._UEBERSCHRIFT_FESTLEGUNGEN)}</h2>"
        f"{_festlegungen_html(daten, nonce_wert)}\n"
        f"<h2>{_t(T._UEBERSCHRIFT_SZENEN)}</h2>{uebersicht}{szenen}\n"
        # Die Sprechanteile stehen unter den Szenen: sie sind eine Zählung
        # über genau diese Texte (06.09.2026). Ohne zählbare Szene fehlt der
        # Abschnitt ganz.
        f"{_sprechanteile_html(daten.get('sprechanteile'))}\n"
        f"{_dramaturgie_html(daten.get('dramaturgie'))}\n"
        f"<h2>{_t(T._UEBERSCHRIFT_INTERVIEWS)}</h2>{verdichtungen_html}\n"
        f"<h2>{_t(T._UEBERSCHRIFT_WEG)}</h2>"
        f"<details><summary>{_t(T._TEXT_JOURNAL.format(anzahl=len(daten['journal'])))}"
        f"</summary>{journal}</details>\n"
        f"</div>\n"
    )


def gruppe_html(
    daten: dict,
    nonce_wert: str | None = None,
    token: str | None = None,
    praefix: str = VORGABE_PRAEFIX,
    fassungswahl: dict[int, int] | None = None,
) -> str:
    """Die Gruppenseite aus web_daten.gruppe_nach_token().

    Ohne ``nonce_wert`` bleibt sie, was sie war: eine Leseansicht. Mit
    ``nonce_wert`` werden Arbeitsstand, Figuren und Szenenplanung zu
    Formularen -- der Nonce ist der Schluessel dazu und steht als verstecktes
    Feld in der Seite (siehe ``nonce``).

    ``fassungswahl`` ist ``{szene_id: nummer}`` aus der Query (``?szene=…&
    fassung=…``). Read-only: eine Auswahl aendert nur, welche Fassung
    angezeigt wird -- sie schreibt nichts und bleibt deshalb in der URL statt
    in der Datenbank."""
    from interview_theater import workshop

    titel = daten["titel"] or T._TEXT_GRUPPE.format(chat_id=daten["chat_id"])
    return _seite(
        T._TITEL_GRUPPENSEITE.format(titel=titel),
        _CSS_GRUPPE,
        gruppe_koerper(daten, nonce_wert, token, praefix, fassungswahl),
        # Padua: die Werkbank ist reine Anzeige, das Speicher-Skript faellt weg.
        bearbeitbar=bool(nonce_wert) and workshop.workbench_bearbeitbar(),
    )


# --- Die Probenansicht ----------------------------------------------------
#
# `/g/<token>/textbuch` (06.09.2026, Birk): das ganze Stueck am Stueck, zum
# Lesen in der Probe und zum Ausdrucken. **Rein lesend** -- kein POST, kein
# Formular, kein Nonce. Der Grund ist derselbe wie beim Dashboard: hier steht
# niemand am Rechner, hier haelt jede Person ihr eigenes Telefon in der Hand
# und spricht laut. Was in der Probe entschieden wird, geht in den Chat oder
# auf die Gruppenseite -- diese Seite soll man anfassen koennen, ohne etwas
# zu veraendern.
#
# Sie laedt sich auch nicht nach: ein Austausch des <body> alle zehn Sekunden
# risse den Rollenfilter und die Schriftgroesse mit, und einen Grund dafuer
# gibt es nicht -- ein Textbuch aendert sich nicht waehrend man es liest.

#: Was in einer Sprecherzeile vor dem Doppelpunkt stehen darf: Versalien,
#: Ziffern, Leerzeichen, Bindestrich, Apostroph. Kein Satzzeichen -- ein Satz
#: mit Doppelpunkt ist keine Replik.
_SPRECHER_VERBOTEN = ",;.!?\"'()[]/"

#: Woerter, die am Zeilenanfang in Versalien mit Doppelpunkt stehen, ohne eine
#: Figur zu sein. Alle aus den echten Szenentexten: der Szenenkopf des
#: Dialog-Regelblocks ("SZENE 1: EINUNDFUENFZIG STUNDEN ca. 10 min") und die
#: Pflichtzeilen des Szenen-Prompts, falls eine davon im Volltext gelandet
#: ist. Ohne diese Liste haette jedes Stueck eine Figur namens "SZENE 1".
_KEINE_SPRECHER = frozenset(
    {"SZENE", "AKT", "BILD", "TITEL", "KURZ", "ZUSAMMENFASSUNG", "ANDERS",
     "ORT", "ZEIT", "ANLASS", "FORM", "PERSONEN", "BESETZUNG", "DAUER"}
)

#: Dasselbe auf Englisch (Karte A1, K5): der englische Szenenprompt laesst
#: "SCENE 1: ..." schreiben. Gelesen wird die Vereinigung. Geprueft wird nur
#: das ERSTE Wort des Namens, deshalb steht neben "DONE DIFFERENTLY" auch
#: "DONE" da (Zusatz zum Plan).
_KEINE_SPRECHER_EN = frozenset(
    {"SCENE", "ACT", "TITLE", "SHORT", "SUMMARY", "CHANGED", "DONE DIFFERENTLY",
     "DONE", "PLACE", "TIME", "OCCASION", "FORM", "CAST", "CHARACTERS", "DURATION"}
)

#: Wie lang der Name vor dem Doppelpunkt hoechstens sein darf. "FRAU MUELLER
#: VON NEBENAN" ist eine Figur, ein halber Satz nicht mehr.
_SPRECHER_MAX = 30


def sprecher_der_zeile(zeile: str, bekannte: set[str] | None = None) -> str | None:
    """Der Sprecher einer Zeile in Versalien, oder None.

    **Defensiv, absichtlich** (Birk, 06.09.2026): der Rollenfilter markiert
    lieber nichts als das Falsche. Erkannt wird die Grundform aus
    ``prompts/szene.md`` -- "Figurennamen in GROSSBUCHSTABEN, danach ein
    Doppelpunkt, dann die Replik" -- also ``LEYLA: Text`` und die im
    Dialog-Regelblock vorgegebene enge Schreibweise ``LEYLA:(steht auf)Text``.
    ``CHOR:`` aus ``formen/chor.md`` faellt von selbst darunter.

    ``bekannte`` (die Figurennamen der Gruppe, in Versalien) ist die eine
    Ausnahme von der Versalien-Regel: schreibt ein Modell ``Leyla:``, gilt die
    Zeile nur dann als Replik, wenn die Gruppe wirklich eine Figur Leyla hat.
    Ein Satz, der zufaellig mit "Name:" beginnt, bleibt damit ein Satz.

    Rueckgabe ist der Name in Versalien -- er ist der Schluessel, unter dem
    der Filter zuordnet, nicht die Schreibweise, die angezeigt wird."""
    kopf, trenner, _rest = zeile.partition(":")
    if not trenner:
        return None
    name = kopf.strip()
    if not (2 <= len(name) <= _SPRECHER_MAX):
        return None
    if not any(z.isalpha() for z in name):
        return None
    if any(z in name for z in _SPRECHER_VERBOTEN):
        return None
    if name.split()[0].upper() in _KEINE_SPRECHER | _KEINE_SPRECHER_EN:
        return None
    if name != name.upper() and name.upper() not in (bekannte or set()):
        return None
    return name.upper()


def _regie(text: str) -> str:
    """Maskiert eine Replik und packt die Regieanweisungen in Klammern in ein
    eigenes ``<span>``.

    Zuerst maskieren, dann suchen: ``html.escape`` erzeugt keine runden
    Klammern, der Ausdruck kann also nichts treffen, was nicht im Original
    stand. Das ``<span>`` ist die Handhabe fuer "Regieanweisungen ausblenden"
    -- ausgeblendet wird per CSS, der Text bleibt im HTML und damit im
    Ausdruck, wenn man den Schalter wieder umlegt."""
    return re.sub(
        r"\(([^()]*)\)",
        lambda treffer: f'<span class="regie">({treffer.group(1)})</span>',
        _t(text, ""),
    )


def szenentext_html(text: str, bekannte: set[str] | None = None) -> tuple[str, list[str]]:
    """Ein Szenentext als HTML, dazu die Sprecher in der Reihenfolge ihres
    ersten Auftritts.

    Zeile fuer Zeile, weil die Szenentexte zeilenweise gebaut sind (eine
    Replik je Zeile, Regie in eigenen Zeilen oder inline). Was nicht als
    Replik erkannt wird, steht trotzdem da -- als Absatz, nur ohne Zuordnung:
    der Ort am Anfang, die Regiezeile dazwischen, die Fortsetzung einer
    umbrochenen Replik. **Nichts wird weggelassen**, sonst waere die
    Probenansicht eine zweite Wahrheit neben dem Textbuch.

    Eine Zeile ohne eigenen Sprecher direkt unter einer Replik gehoert zu
    dieser Replik (umbrochener Absatz) und wird mit ihr hervorgehoben; eine
    Leerzeile beendet die Zugehoerigkeit."""
    stuecke: list[str] = []
    sprecher: list[str] = []
    laufende: str | None = None
    for zeile in text.splitlines():
        blank = zeile.strip()
        if not blank:
            laufende = None
            continue
        name = sprecher_der_zeile(zeile, bekannte)
        if name is not None:
            if name not in sprecher:
                sprecher.append(name)
            laufende = name
            kopf, _trenner, rest = zeile.partition(":")
            stuecke.append(
                f'<p class="replik" data-figur="{_t(name)}">'
                f'<b class="sprecher">{_t(kopf.strip())}:</b> '
                f"{_regie(rest.strip())}</p>"
            )
            continue
        if blank.startswith("(") and blank.endswith(")"):
            # Eine ganze Zeile in Klammern ist eine Regieanweisung fuer sich
            # ("(Pause. Niemand sagt etwas.)") -- sie gehoert keiner Figur und
            # verschwindet mit dem Schalter komplett.
            laufende = None
            stuecke.append(f'<p class="regie regie-zeile">{_t(blank)}</p>')
            continue
        if laufende is not None:
            stuecke.append(
                f'<p class="replik weiter" data-figur="{_t(laufende)}">'
                f"{_regie(blank)}</p>"
            )
            continue
        stuecke.append(f'<p class="prosa">{_regie(blank)}</p>')
    return "".join(stuecke), sprecher


#: Die Angaben einer Szene ueber ihrem Text, in dieser Reihenfolge. Weniger
#: als die Planung auf der Gruppenseite: in der Probe braucht man Ort, Zeit
#: und Anlass, nicht "was anders ist als in der Szene davor".
_PROBE_ANGABEN = (("form", "Form"), ("ort", "Ort"), ("zeit", "Zeit"),
                  ("anlass", "Anlass"))

#: Die uebrigen Planungsfelder -- sie stehen nur unter einer Szene, die noch
#: keinen Text hat. Dort sind sie das, was die Gruppe stattdessen lesen kann.
_TEXT_PLANUNG_MEHR = "+ {anzahl} weitere in der Werkbank"
_PROBE_PLANUNG = (("was_passiert", "Was passiert"), ("was_anders", "Was anders ist"),
                  ("kernsaetze", "Kernsätze"), ("ton", "Ton"))

TEXT_UNGESCHRIEBEN = "Noch nicht geschrieben."

#: Die zwei aufklappbaren Bloecke unter einer Szene (Padua Phasen TEIL 2,
#: Aufgabe 12): die frueheren Fassungen und die Erstfassung vor der Pruefung.
_TEXT_FRUEHERE = "Fruehere Fassungen ({anzahl})"
_TEXT_ERSTE_FASSUNG = "Erste Fassung (vor der Pruefung)"


def _fassungen_bloecke_html(s: dict, aktuell: str) -> str:
    """Fruehere Fassungen und Erstfassung als ``<details>`` -- oder nichts.

    Die Werte kommen ueber die Szene selbst (``_fassungen``, ``_erstentwurf``,
    gesetzt in ``textbuch_koerper``), damit sich die Signatur von
    ``_probe_szene_html`` fuer niemanden aendert. Rein lesend; zugeklappt,
    damit das Stueck am Stueck lesbar bleibt. Die aktuelle Fassung steht
    nicht noch einmal darin."""
    teile = []
    fassungen = s.get("_fassungen") or []
    if len(fassungen) >= 2:
        frueher = [f for f in fassungen if (f.get("volltext") or "").strip() != aktuell]
        if frueher:
            texte = "".join(
                f'<div class="text"><p class="prosa">{_t(f["volltext"])}</p></div>'
                for f in frueher
            )
            teile.append(
                f'<details class="fruehere"><summary>'
                f'{_t(T._TEXT_FRUEHERE.format(anzahl=len(frueher)))}</summary>'
                f"{texte}</details>"
            )
    erst = (s.get("_erstentwurf") or "").strip()
    if erst:
        teile.append(
            f'<details class="erstentwurf"><summary>{_t(T._TEXT_ERSTE_FASSUNG)}</summary>'
            f'<div class="text"><p class="prosa">{_t(erst)}</p></div></details>'
        )
    return "".join(teile)


#: Script-Tab (Birk 07.10.2026 ~17:30, G1: "Wall of Text ohne Umbrueche"):
#: "What happens" und "Key lines" knapp und als Liste. Obergrenzen gelten
#: nur fuer die ANZEIGE -- die Felder bleiben vollstaendig (Prompts).
PLANUNG_PUNKTE_MAX = 6
PLANUNG_PUNKT_ZEICHEN = 160
KERNSAETZE_MAX = 5
KERNSATZ_ZEICHEN = 200


def _kappe(text: str, grenze: int) -> str:
    text = " ".join(text.split())
    if len(text) <= grenze:
        return text
    return text[:grenze].rsplit(" ", 1)[0].rstrip(" ,;:-") + " …"


def _planung_punkte(feld: str, wert: str) -> list[str]:
    """Zerlegt ein Planungsfeld in Listenpunkte: Kernsaetze an ``|``,
    "What happens" an Saetzen und an den ``;``-Anhaengen der uebernommenen
    Interviewstellen (``schaerfung._ergaenze_szene``)."""
    import re as _re

    if feld == "kernsaetze":
        return [t.strip() for t in wert.split("|") if t.strip()]
    # Saetze der Beschreibung bleiben ganz; nur die angehaengte Kette der
    # Interview-Begruendungen (klein beginnend, mit "; " verbunden) wird zu
    # Einzelpunkten -- ein "e.g. a; b; c" im Beschreibungssatz bleibt heil.
    punkte: list[str] = []
    for satz in _re.split(r"(?<!e\.g\.)(?<!i\.e\.)(?<!etc\.)(?<=[.!?])\s+", wert.strip()):
        satz = satz.strip()
        if not satz:
            continue
        if satz[0].islower() and "; " in satz:
            punkte.extend(t.strip() for t in satz.split("; ") if t.strip())
        else:
            punkte.append(satz)
    return punkte


def _planung_wert_html(feld: str, wert: str) -> str:
    """Padua (``prosa_entwurf_aktiv``): Liste mit Obergrenze; sonst wie bisher."""
    from interview_theater import workshop

    if not workshop.prosa_entwurf_aktiv() or feld not in ("was_passiert", "kernsaetze"):
        return _t(wert)
    punkte = _planung_punkte(feld, str(wert))
    if feld == "kernsaetze":
        grenze, zeichen = KERNSAETZE_MAX, KERNSATZ_ZEICHEN
    else:
        grenze, zeichen = PLANUNG_PUNKTE_MAX, PLANUNG_PUNKT_ZEICHEN
    sichtbar = punkte[:grenze]
    items = "".join(
        f"<li>{_t(('“' + _kappe(p, zeichen) + '”') if feld == 'kernsaetze' else _kappe(p, zeichen))}</li>"
        for p in sichtbar
    )
    rest = len(punkte) - len(sichtbar)
    mehr = f'<li class="mehr">{_t(T._TEXT_PLANUNG_MEHR.format(anzahl=rest))}</li>' if rest > 0 else ""
    return f'<ul class="planung-liste">{items}{mehr}</ul>'


def _prosa_absaetze_html(text: str) -> str:
    """Script-Tab (Birk 07.10.2026 ~17:40: "keinerlei Zeilenumbrueche oder
    Paragraphs"): Leerzeile = neuer Absatz, einfacher Umbruch = <br>,
    ``**fett**`` und ``*kursiv*`` wie im Chat, ``NAME:`` am Zeilenanfang fett."""
    import re as _re

    def zeile(z: str) -> str:
        z = _t(z, "")
        z = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", z)
        z = _re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", z)
        z = _re.sub(r"^([A-ZÀ-Ý][A-ZÀ-Ý' .-]{1,30}):", r"<strong>\1:</strong>", z)
        return z

    # Birk 07.10.2026 ~18:05: Interviewzitate sichtbar als solche --
    # Zeilen "> ..." (Prompt formen/prosa im Padua-Profil: "> *Interview
    # quote (N):* ...") werden ein eigener Zitatblock.
    stuecke: list[str] = []
    for a in [a.strip() for a in _re.split(r"\n\s*\n", (text or "").strip()) if a.strip()]:
        if _re.fullmatch(r"-{3,}|\*{3,}|_{3,}", a):
            # Ein Absatz nur aus "---" ist eine Trennlinie (Stage Script G3).
            stuecke.append('<hr class="trenner">')
            continue
        normal: list[str] = []
        for z in a.splitlines():
            if z.lstrip().startswith(">"):
                if normal:
                    stuecke.append(f'<p class="prosa">{"<br>".join(normal)}</p>')
                    normal = []
                stuecke.append(
                    f'<blockquote class="interviewzitat">{zeile(z.lstrip()[1:].strip())}</blockquote>'
                )
            else:
                normal.append(zeile(z))
        if normal:
            stuecke.append(f'<p class="prosa">{"<br>".join(normal)}</p>')
    return "".join(stuecke)


def _probe_szene_html(s: dict, bekannte: set[str]) -> tuple[str, list[str]]:
    """Eine Szene in der Probenansicht: Kopf, Angaben, Besetzung, Text.

    Nicht aufklappbar (anders als auf der Gruppenseite): hier wird das Stueck
    am Stueck gelesen, und ein ``<details>`` waere in der Probe ein Klick vor
    jedem Einsatz -- und im Ausdruck eine zugeklappte Seite.

    Eine Szene ohne Volltext faellt nicht weg, sondern steht als Platzhalter
    mit ihrer Planung da (dieselbe Entscheidung wie in
    ``szenenfolge.textbuch``: ein Textbuch, in dem Szene 4 fehlt, sieht aus
    wie ein Fehler)."""
    if s.get("verdichtet") is not None:
        return _probe_szene_verdichtet_html(s, bekannte)
    kopf = _t(
        T._TEXT_SZENE_NR.format(nummer=s["nummer"])
        if s.get("nummer") is not None else T._TEXT_SZENE
    )
    if s.get("titel"):
        kopf += f" — {_t(s['titel'])}"
    angaben = " · ".join(
        "{label}: {wert}".format(
            label=_t(label),
            wert=_t(_form_anzeige(s[feld]) if feld == "form" else s[feld]),
        )
        for feld, label in T._PROBE_ANGABEN
        if s.get(feld)
    )
    zeilen = [f'<h2 class="szenenkopf">{kopf}</h2>']
    if angaben:
        zeilen.append(f'<p class="angaben">{angaben}</p>')
    if s.get("figuren"):
        zeilen.append(
            f'<p class="besetzung">'
            f'{_t(T._TEXT_BESETZUNG.format(figuren=", ".join(s["figuren"])))}</p>'
        )
    volltext = (s.get("volltext") or "").strip()
    prosa = (s.get("prosa") or "").strip()
    # Die italienische Spiegelung (Birk, Live-Workshop 07.10.2026 ~17:20,
    # Padua-Profilschalter [skript] zweisprachig): nur gesetzt, wenn der
    # Spiegelpass gelaufen ist. Ohne sie bleibt diese ganze Ansicht
    # byte-gleich -- der Zweig unten greift rein datengetrieben.
    prosa_it = (s.get("prosa_it") or "").strip()
    sprecher: list[str] = []
    if volltext:
        koerper, sprecher = szenentext_html(volltext, bekannte)
        zeilen.append(f'<div class="text">{koerper}</div>')
    else:
        planungsfelder = T._PROBE_PLANUNG
        if prosa_it:
            # Kernsaetze sind das italienische Originalzitat -- sie gehoeren
            # zum IT-Block unten, nicht in die sonst englische Planungsliste.
            planungsfelder = [f for f in planungsfelder if f[0] != "kernsaetze"]
        planung = "".join(
            f"<dt>{_t(label)}</dt><dd>{_planung_wert_html(feld, s[feld])}</dd>"
            for feld, label in planungsfelder
            if s.get(feld)
        )
        if not prosa and not prosa_it:
            # P57 Lauf 2 B2: "Noch nicht geschrieben" nur ohne Prosa -- mit
            # Prosa stand es ueber dem vorhandenen Szenentext (Padua 5/6).
            zeilen.append(f'<p class="offen">{_t(T.TEXT_UNGESCHRIEBEN)}</p>')
        if prosa:
            # Die Prosafassung aus Phase 6 ist der eigene Text der Gruppe und
            # kein Material -- sie steht hier, wo sonst nichts stuende, und
            # sagt dazu, dass sie noch keine Szene ist.
            etikett = T._TEXT_ALS_GESCHICHTE_EN if prosa_it else T._TEXT_ALS_GESCHICHTE_DOPPELPUNKT
            zeilen.append(
                f'<p class="angaben">{_t(etikett)}</p><div class="text">'
                f'{_prosa_absaetze_html(prosa)}</div>'
            )
        if prosa_it:
            zeilen.append(
                f'<p class="angaben">{_t(T._TEXT_ALS_GESCHICHTE_IT)}</p><div class="text">'
                f'{_prosa_absaetze_html(prosa_it)}</div>'
            )
            kernsaetze_roh = (s.get("kernsaetze") or "").strip()
            if kernsaetze_roh:
                zeilen.append(
                    f'<p class="angaben">{_t(T._TEXT_KERNSAETZE_IT)}</p>'
                    f'{_prosa_absaetze_html(kernsaetze_roh)}'
                )
        if planung:
            zeilen.append(f'<dl class="planung">{planung}</dl>')
    bloecke = _fassungen_bloecke_html(s, volltext or prosa)
    if bloecke:
        zeilen.append(bloecke)
    return f'<section class="probe-szene">{"".join(zeilen)}</section>', sprecher


#: Script-Tab unter ``[skript] verdichtet`` (Birk 07.10.2026 ~17:45, "Fokus
#: halten. Gut lesbar."): was die Gruppe liest und probt -- der Text. Die
#: Kurzform steht nur, solange es noch keinen Text gibt.
_TEXT_WORUM = "Worum es geht"
_TEXT_STAERKSTE = "Stärkste Zitate"
_TEXT_FASSUNG_EN = "English"
_TEXT_FASSUNG_IT = "Italiano"
_TEXT_ALLE_ZITATE = "Alle übernommenen Zitate ({anzahl})"
ORT_ZEICHEN = 140


def _liste_html(klasse: str, punkte: list[str], zeichen: int) -> str:
    if not punkte:
        return ""
    return f'<ul class="{klasse}">' + "".join(
        f"<li>{_t(_kappe(p, zeichen))}</li>" for p in punkte) + "</ul>"


def _kurzform_punkte(v: dict) -> list[str]:
    """Die Kurzform, sonst die bereinigte Beschreibung der Gruppe in Saetzen
    (Rueckfall, wenn ``szenenkern.verdichte`` noch nicht lief oder scheiterte)."""
    if v.get("kern"):
        return v["kern"][:PLANUNG_PUNKTE_MAX]
    return _planung_punkte("was_passiert", v.get("beschreibung") or "")[:PLANUNG_PUNKTE_MAX]


def _staerkste_zitate(v: dict) -> list[str]:
    if v.get("kernsaetze_kurz"):
        return v["kernsaetze_kurz"][:KERNSAETZE_MAX]
    return [f"“{k}”" for k in (v.get("kernsaetze_eigen") or [])[:KERNSAETZE_MAX]]


_TEXT_PROSA_MATERIAL = "Frueherer Prosaentwurf (Material)"
_TEXT_KARTE_GESPEICHERT = "gespeichert"
_TEXT_KARTE_OFFEN = "noch nicht gespeichert"


def _karte_html(karte: dict, bestaetigt: bool) -> str:
    """Die Szenenkarte im Script-Tab: Typ, worum, wo/wer, Punkte, Zitate im
    Original, offene Fragen -- dieselben Felder wie im Chat."""
    from interview_theater import szenenkarte

    st = szenenkarte.T
    typ = st.TYP_BESCHRIFTUNG.get(karte.get("typ"), karte.get("typ") or "")
    status = T._TEXT_KARTE_GESPEICHERT if bestaetigt else T._TEXT_KARTE_OFFEN
    teile = [f'<p class="karte-typ">{_t(typ)} · {_t(status)}</p>']
    if karte.get("worum"):
        teile.append(f'<p class="karte-worum">{_t(karte["worum"])}</p>')
    angaben = [f"<b>{_t(st._ZEILE_ORT)}</b> {_t(karte['ort'])}" if karte.get("ort") else "",
               f"<b>{_t(st._ZEILE_WER)}</b> {_t(karte['wer'])}" if karte.get("wer") else ""]
    angaben = [a for a in angaben if a]
    if angaben:
        teile.append(f'<p class="karte-angaben">{"<br>".join(angaben)}</p>')
    if karte.get("punkte"):
        teile.append(f'<p class="worum-kopf">{_t(st._ZEILE_PUNKTE)}</p>'
                     + _liste_html("worum-liste", karte["punkte"], 400))
    if karte.get("zitate"):
        zitate = "".join(
            f'<blockquote class="karte-zitat" lang="it">“{_t(z.get("zitat"))}”'
            + (f' <span class="quelle">({_t(z["interview"])})</span>' if z.get("interview") else "")
            + "</blockquote>"
            for z in karte["zitate"]
        )
        teile.append(f'<p class="worum-kopf">{_t(st._ZEILE_ZITATE)}</p>{zitate}')
    if karte.get("fragen"):
        teile.append(f'<p class="worum-kopf">{_t(st._ZEILE_FRAGEN)}</p>'
                     + _liste_html("worum-liste", karte["fragen"], 400))
    return f'<div class="szenenkarte">{"".join(teile)}</div>'


_PARTITUR_MODI = ("microphone", "one_to_one", "collective")
PARTITUR_SPALTEN = {"microphone": "🎤 Mikrofon", "one_to_one": "👂 1:1",
                    "collective": "👥 Kollektiv"}


def _partitur_html(szenen: list[dict]) -> str:
    """G3 (Padua-Phasenumbau, Entwurf Robo 18:10): ein Stueck aus Momenten
    steht oben als Orts-Partitur -- drei Spalten (Mikrofon, 1:1, Kollektiv),
    die Zeit von oben nach unten; ein Moment ohne Modus geht ueber alle drei.
    Nur, wenn die Karten ueberwiegend Momente sind; sonst nichts."""
    karten = [(s, s.get("karte") or {}) for s in szenen]
    momente = [k for _, k in karten if k.get("typ") == "moment"]
    if not momente or len(momente) * 2 <= len(karten):
        return ""
    kopf = "".join(f"<th>{_t(T.PARTITUR_SPALTEN[m])}</th>" for m in _PARTITUR_MODI)
    zeilen = []
    for s, k in karten:
        titel = f"{s.get('nummer')}. {s.get('titel') or ''}".strip()
        zelle = f"<b>{_t(titel)}</b>" + (f"<br>{_t(_kappe(k.get('worum') or '', 120))}"
                                          if k.get("worum") else "")
        modus = k.get("modus") if k.get("typ") == "moment" else None
        if modus in _PARTITUR_MODI:
            zellen = "".join(f'<td class="an">{zelle}</td>' if m == modus else "<td></td>"
                             for m in _PARTITUR_MODI)
        else:
            zellen = f'<td colspan="3" class="ganz">{zelle}</td>'
        zeilen.append(f"<tr>{zellen}</tr>")
    return (f'<section class="probe-szene partitur"><table class="partitur">'
            f"<thead><tr>{kopf}</tr></thead><tbody>{''.join(zeilen)}</tbody></table></section>")


_TEXT_KARTE_ENTSTEHT = "Karte {nummer} entsteht gerade ..."
_TEXT_KARTEN_ALLE = "Alle Karten sind gespeichert. Im Chat geht es weiter zum Stage Script."
_TEXT_KARTE_JA = "Yes, save"
_TEXT_KARTE_BAUEN = "Karte jetzt bauen"
_TEXT_KARTE_VORHERIGE = "Vorherige Karte"
_TEXT_KARTE_NAECHSTE = "Naechste Karte"
_TEXT_KARTE_NOCH_NICHT = "Diese Karte gibt es noch nicht -- sie entsteht, wenn sie dran ist."
_TEXT_KARTE_ZUR_AKTUELLEN = "Zur aktuellen Karte"
_TEXT_KARTE_NEIN = "No, change"
_TEXT_KARTEN_ZAEHLER = "Karte {aktiv} von {gesamt}"


def _szenenkarten_html(liste: list[dict]) -> str:
    """Die Szenenkarten im CoThinker (Padua Phase 6, Birk 07.10.2026 ~19:25
    und ~19:35, verbindlich): Handy-first, schlank.

    Oben die Leiste ``‹ Card k of n ›`` (Pfeile NUR oben -- niemand soll
    scrollen muessen), darunter die GEZEIGTE Karte: zuerst die aktive, gross,
    mit "Yes, save" / "No, change"; jede andere ist nur Ansicht (Status, ein
    Weg zurueck zur aktiven), abgenommen wird allein die aktive. Darunter
    jede Karte als EINE Zeile -- ein Klick zeigt sie. Welche Karte gezeigt
    wird, haelt das Browser-Skript (``web_vereint._AUSWAHL_JS``) ueber das
    Nachladen hinweg fest; ohne Skript bleibt die aktive gezeigt."""
    gesamt = len(liste)
    aktive = next((k for k in liste if k["aktiv"]), None)
    vorlage = T._TEXT_KARTEN_ZAEHLER.replace("{gesamt}", str(gesamt))
    zaehler = vorlage.replace("{aktiv}", str(aktive["nummer"])) if aktive else ""
    teile = [
        f'<div id="buehne-panel" data-ansicht="karten" '
        f'data-aktiv="{int(aktive["nummer"]) if aktive else ""}">',
        '<div class="karten-nav">'
        f'<button type="button" class="karten-pfeil" data-richtung="-1" '
        f'aria-label="{_t(T._TEXT_KARTE_VORHERIGE)}">‹</button>'
        f'<span class="karten-zaehler" data-vorlage="{_t(vorlage)}">{_t(zaehler)}</span>'
        f'<button type="button" class="karten-pfeil" data-richtung="1" '
        f'aria-label="{_t(T._TEXT_KARTE_NAECHSTE)}">›</button></div>',
    ]
    zeilen = []
    for k in liste:
        nummer = int(k["nummer"])
        titel = _t(f'{k["nummer"]}. {k["titel"]}'.strip())
        if k["aktiv"]:
            zustand = "aktiv"
        elif k["bestaetigt"]:
            zustand = "fertig"
        else:
            zustand = "spaeter"
        if k["aktiv"] and k["karte"] is None:
            inhalt = f'<p class="karte-entsteht">{_t(T._TEXT_KARTE_ENTSTEHT.format(nummer=nummer))}</p>'
            # Rettungsweg, falls die Erzeugung nie fertig wurde (Neustart
            # mitten im Lauf): laeuft sie noch, sagt der Bot das nur.
            knoepfe = (
                '<div class="karte-aktionen">'
                f'<button type="button" class="karte-knopf karte-bauen" data-aktion="bauen" '
                f'data-nummer="{nummer}">{_t(T._TEXT_KARTE_BAUEN)}</button></div>'
            )
        elif k["aktiv"]:
            inhalt = _karte_html(k["karte"], False)
            knoepfe = (
                '<div class="karte-aktionen">'
                f'<button type="button" class="karte-knopf karte-ja" data-aktion="ja" '
                f'data-nummer="{nummer}">{_t(T._TEXT_KARTE_JA)}</button>'
                f'<button type="button" class="karte-knopf karte-nein" data-aktion="aendern" '
                f'data-nummer="{nummer}">{_t(T._TEXT_KARTE_NEIN)}</button></div>'
            )
        else:
            inhalt = (_karte_html(k["karte"], k["bestaetigt"]) if k["karte"] is not None
                      else f'<p class="karte-entsteht">{_t(T._TEXT_KARTE_NOCH_NICHT)}</p>')
            knoepfe = (
                f'<p class="karte-nur-ansicht"><button type="button" class="karte-zurueck">'
                f'{_t(T._TEXT_KARTE_ZUR_AKTUELLEN)}</button></p>' if aktive is not None else ""
            )
        haken = "✓ " if k["bestaetigt"] else ""
        gezeigt = " gezeigt" if k["aktiv"] else ""
        aktiv_klasse = " karte-aktiv" if k["aktiv"] else ""
        zeilen.append(
            f'<li class="karte-eintrag {zustand}{aktiv_klasse}{gezeigt}" data-nummer="{nummer}">'
            f'<button type="button" class="karte-zeile">{haken}{titel}</button>'
            f'<div class="karte-koerper"><h3 class="karte-titel">{titel}</h3>{inhalt}{knoepfe}</div>'
            "</li>"
        )
    teile.append(f'<ul class="karten">{"".join(zeilen)}</ul>')
    if aktive is None and liste:
        teile.append(f'<p class="karten-fertig">{_t(T._TEXT_KARTEN_ALLE)}</p>')
    teile.append("</div>")
    return "".join(teile)


_CSS_KARTEN_BUEHNE = """
.karten { list-style: none; margin: 0; padding: 0; }
.karten-zaehler { margin: .2rem 0 .6rem; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: var(--text-leise, #6b6b6b); }
.karten-nav { display: flex; align-items: center; gap: .5rem; margin: .1rem 0 .5rem; }
.karten-nav .karten-zaehler { flex: 1; text-align: center; margin: 0; }
.karten-pfeil { min-width: 2.9rem; min-height: 2.6rem; font: inherit; font-size: 1.4rem; line-height: 1; border-radius: 1.4rem; border: 1px solid var(--rand, #cfc8b6); background: var(--grund-2, transparent); color: var(--text, #1b1b1b); cursor: pointer; }
.karten-pfeil:disabled { opacity: .3; }
.karte-zeile { display: block; width: 100%; text-align: left; font: inherit; color: inherit; background: none; border: 0; border-bottom: 1px solid var(--linie, #ddd8cc); cursor: pointer; padding: .55rem .2rem; font-size: .95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.karte-eintrag.spaeter .karte-zeile { opacity: .45; }
.karte-eintrag.fertig .karte-zeile { color: var(--text-leise, #6b6b6b); }
.karte-koerper { display: none; }
.karte-eintrag.gezeigt .karte-zeile { display: none; }
.karte-eintrag.gezeigt .karte-koerper { display: block; margin: .4rem 0 1rem; padding: .9rem 1rem 1rem; border: 1px solid var(--linie, #ddd8cc); border-radius: .8rem; background: var(--grund-2, transparent); }
.karte-nur-ansicht { margin: 1rem 0 0; }
.karte-zurueck { font: inherit; font-size: .9rem; background: none; border: 0; padding: 0; color: var(--signal, #2f4858); text-decoration: underline; cursor: pointer; }
.karte-titel { margin: 0 0 .35rem; font-size: 1.15rem; line-height: 1.25; }
.karte-koerper .szenenkarte { margin: 0; max-width: none; }
.karte-entsteht { margin: .3rem 0; font-style: italic; color: var(--text-leise, #6b6b6b); }
.karte-aktionen { display: flex; gap: .6rem; margin: 1rem -1rem -1rem; padding: .7rem 1rem calc(1.7rem + env(safe-area-inset-bottom, 0px)); position: sticky; bottom: -1rem; background: var(--grund-2, #1d2026); border-top: 1px solid var(--linie, #ddd8cc); border-radius: 0 0 .8rem .8rem; }
.karte-knopf { flex: 1; min-height: 2.9rem; font: inherit; font-size: 1rem; border-radius: 1.5rem; border: 1px solid var(--rand, #cfc8b6); background: var(--grund, #fff); color: var(--text, #1b1b1b); cursor: pointer; }
.karte-ja { background: var(--signal, #2f4858); border-color: var(--signal, #2f4858); color: var(--auf-signal, #fff); font-weight: 700; }
.karte-knopf:disabled { opacity: .5; }
.karten-fertig { margin: 1rem 0; font-style: italic; }
"""


def css_karten_buehne() -> str:
    """Leer ohne ``[karten] aktiv`` -- dann bleibt die Seite byte-gleich."""
    from interview_theater import workshop

    if not workshop.szenenkarten_aktiv():
        return ""
    return _CSS_KARTEN_BUEHNE + _CSS_TEXTBUCH_LESBAR_KARTE


#: Die Kartenfelder (``_karte_html``) im CoThinker brauchen dieselben Regeln
#: wie im Script-Tab -- dort stehen sie in ``_CSS_TEXTBUCH_LESBAR``.
_CSS_TEXTBUCH_LESBAR_KARTE = """
.szenenkarte { line-height: 1.5; }
.karte-typ { margin: 0 0 .3rem; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: var(--text-leise, #6b6b6b); }
.karte-worum { margin: 0 0 .7rem; font-size: 1.05rem; }
.karte-angaben { margin: 0 0 .7rem; font-size: .9rem; }
.worum-kopf { margin: .5rem 0 .25rem; font-size: .7rem; letter-spacing: .12em; text-transform: uppercase; color: var(--text-leise, #6b6b6b); }
.worum-liste { margin: 0 0 .5rem; padding-left: 1.1rem; }
.worum-liste li { margin: .22rem 0; }
.karte-zitat { margin: .35rem 0 .55rem; padding: .1rem 0 .1rem .8rem; border-left: 2px solid var(--linie, #ddd8cc); font-style: italic; }
.karte-zitat .quelle { font-style: normal; font-size: .82em; color: var(--text-leise, #6b6b6b); }
"""


def _probe_szene_verdichtet_html(s: dict, bekannte: set[str]) -> tuple[str, list[str]]:
    """Eine Szene im Script-Tab, auf das Wesentliche reduziert: Kopf, Ort und
    Besetzung, der Text (EN und IT als eigene Bloecke). "Worum es geht" und
    die staerksten Zitate nur, solange kein Text da ist -- danach stehen die
    Zitate im Text, eine Liste darunter waere Doppelung."""
    v = s.get("verdichtet") or {}
    kopf = _t(
        T._TEXT_SZENE_NR.format(nummer=s["nummer"])
        if s.get("nummer") is not None else T._TEXT_SZENE
    )
    if s.get("titel"):
        kopf += f" — {_t(s['titel'])}"
    angaben = " · ".join(
        _t(_kappe(_form_anzeige(s[feld]) if feld == "form" else str(s[feld]), ORT_ZEICHEN))
        for feld, _ in T._PROBE_ANGABEN
        if s.get(feld) and feld != "form"
    )
    zeilen = [f'<h2 class="szenenkopf">{kopf}</h2>']
    if angaben:
        zeilen.append(f'<p class="angaben">{angaben}</p>')
    if s.get("figuren"):
        zeilen.append(
            f'<p class="besetzung">'
            f'{_t(T._TEXT_BESETZUNG.format(figuren=", ".join(s["figuren"])))}</p>'
        )
    volltext = (s.get("volltext") or "").strip()
    prosa = (s.get("prosa") or "").strip()
    prosa_it = (s.get("prosa_it") or "").strip()
    sprecher: list[str] = []
    volltext_it = (s.get("volltext_it") or "").strip()
    if volltext and "karte" in s:
        # Padua-Phasenumbau: das Stage Script ist kein Dialog im alten Sinn
        # (Ablauf, Anweisungen, Momente) -- dieselbe Lesedarstellung wie die
        # Prosa: Absaetze, **fett**, NAME: fett, Zitatbloecke; EN/IT getrennt.
        if volltext_it:
            zeilen.append(f'<p class="sprache-kopf">{_t(T._TEXT_FASSUNG_EN)}</p>')
        zeilen.append(f'<div class="text" lang="en">{_prosa_absaetze_html(volltext)}</div>')
        if volltext_it:
            zeilen.append(f'<p class="sprache-kopf">{_t(T._TEXT_FASSUNG_IT)}</p>')
            zeilen.append(f'<div class="text" lang="it">{_prosa_absaetze_html(volltext_it)}</div>')
    elif volltext:
        koerper, sprecher = szenentext_html(volltext, bekannte)
        zeilen.append(f'<div class="text">{koerper}</div>')
    elif s.get("karte"):
        # Padua-Phasenumbau (Birk 07.10.2026 ~18:12): bis zum Stage Script
        # steht die Szenenkarte hier; eine fruehere Prosa ist nur Material.
        zeilen.append(_karte_html(s["karte"], s.get("karte_bestaetigt")))
        if prosa:
            zeilen.append(
                f'<details class="fruehere"><summary>{_t(T._TEXT_PROSA_MATERIAL)}</summary>'
                f'<div class="text" lang="en">{_prosa_absaetze_html(prosa)}</div></details>'
            )
    elif prosa:
        if prosa_it:
            zeilen.append(f'<p class="sprache-kopf">{_t(T._TEXT_FASSUNG_EN)}</p>')
        zeilen.append(f'<div class="text" lang="en">{_prosa_absaetze_html(prosa)}</div>')
        if prosa_it:
            zeilen.append(f'<p class="sprache-kopf">{_t(T._TEXT_FASSUNG_IT)}</p>')
            zeilen.append(f'<div class="text" lang="it">{_prosa_absaetze_html(prosa_it)}</div>')
    else:
        zeilen.append(f'<p class="offen">{_t(T.TEXT_UNGESCHRIEBEN)}</p>')
        worum = _liste_html("worum-liste", _kurzform_punkte(v), PLANUNG_PUNKT_ZEICHEN)
        zitate = _liste_html("kernzeilen", _staerkste_zitate(v), KERNSATZ_ZEICHEN)
        if worum or zitate:
            teile = [f'<p class="worum-kopf">{_t(T._TEXT_WORUM)}</p>', worum]
            if zitate:
                teile.append(f'<p class="worum-kopf">{_t(T._TEXT_STAERKSTE)}</p>{zitate}')
            zeilen.append(f'<div class="worum">{"".join(teile)}</div>')
    bloecke = _fassungen_bloecke_html(s, volltext or prosa)
    if bloecke:
        zeilen.append(bloecke)
    return f'<section class="probe-szene">{"".join(zeilen)}</section>', sprecher


#: Lesetypografie fuer Script-Tab und Probenansicht unter ``[skript]
#: verdichtet``: ~65 Zeichen Zeilenlaenge, ruhige Zeilenhoehe, Luft
#: zwischen den Absaetzen, Sprecher fett, Regie kursiv und grau. Ohne
#: Kommentar vor einer Regel (``scope_css``).
_CSS_TEXTBUCH_LESBAR = """
.probe-szene { margin: 0 0 3.2rem; }
.szenenkopf { margin: 2.4rem 0 .5rem; line-height: 1.25; }
.angaben, .besetzung { max-width: 65ch; line-height: 1.45; }
.probe-szene .text { max-width: 65ch; margin-top: 1.1rem; }
.probe-szene .text p { margin: 0 0 1.05em; line-height: 1.68; hyphens: auto; }
.probe-szene .text .sprecher { font-weight: 700; }
.probe-szene .text .regie, .probe-szene .text .regie-zeile { font-style: italic; color: var(--text-leise, #6b6b6b); }
.sprache-kopf { margin: 1.8rem 0 .2rem; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: var(--text-leise, #6b6b6b); }
.worum { max-width: 65ch; margin: .9rem 0 0; padding: .55rem 0 .55rem .9rem; border-left: 2px solid var(--linie, #ddd8cc); font-size: .9rem; line-height: 1.5; color: var(--text-leise, #555); }
.worum-kopf { margin: .2rem 0 .25rem; font-size: .7rem; letter-spacing: .12em; text-transform: uppercase; }
.worum-liste, .kernzeilen { margin: 0 0 .5rem; padding-left: 1.1rem; }
.worum-liste li, .kernzeilen li { margin: .22rem 0; }
.kernzeilen li { font-style: italic; }
.wege .pdf-knopf { display: inline-block; padding: .3rem .95rem; border: 1px solid var(--signal, #6b5a2b); border-radius: 1rem; font-weight: 700; text-decoration: none; }
.szenenkarte { max-width: 65ch; margin: 1rem 0 0; line-height: 1.55; }
.karte-typ { margin: 0 0 .3rem; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: var(--text-leise, #6b6b6b); }
.karte-worum { margin: 0 0 .7rem; font-size: 1.08rem; }
.karte-angaben { margin: 0 0 .7rem; font-size: .9rem; }
.karte-zitat { margin: .35rem 0 .55rem; padding: .1rem 0 .1rem .8rem; border-left: 2px solid var(--linie, #ddd8cc); font-style: italic; }
.partitur { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: .88rem; line-height: 1.4; }
.partitur th { text-align: left; padding: .3rem .4rem; border-bottom: 1px solid var(--linie, #ddd8cc); font-weight: 600; }
.partitur td { vertical-align: top; padding: .45rem .4rem; border-bottom: 1px dotted var(--linie, #ddd8cc); }
.partitur td.an { background: rgba(127, 127, 127, .12); border-radius: .3rem; }
.partitur td.ganz { text-align: center; color: var(--text-leise, #6b6b6b); }
.karte-zitat .quelle { font-style: normal; font-size: .82em; color: var(--text-leise, #6b6b6b); }
"""


def css_textbuch_lesbar() -> str:
    """Leer ohne ``[skript] verdichtet`` -- dann bleibt jede Seite byte-gleich."""
    from interview_theater import workshop

    return _CSS_TEXTBUCH_LESBAR if workshop.skript_verdichtet_aktiv() else ""


_CSS_WERKBANK_KURZ = """
.wb-szenen { list-style: none; padding: 0; margin: 0; }
.wb-szene { margin: 0 0 1.1rem; padding: 0 0 .9rem; border-bottom: 1px solid var(--linie, #ddd8cc); }
.wb-szene:last-child { border-bottom: 0; }
.wb-kern { margin: .3rem 0 .4rem; padding-left: 1.1rem; line-height: 1.45; }
.wb-kern li { margin: .15rem 0; }
.wb-zitate { margin: .3rem 0 .3rem; padding-left: 1.1rem; font-style: italic; font-size: .92em; line-height: 1.45; }
.wb-zitate li { margin: .2rem 0; }
.wb-alle summary { cursor: pointer; font-size: .85em; color: var(--text-leise, #6b6b6b); }
.wb-alle ul { padding-left: 1.1rem; font-size: .88em; line-height: 1.45; }
.wb-alle li { margin: .2rem 0; }
"""


def css_werkbank_kurz() -> str:
    from interview_theater import workshop

    return _CSS_WERKBANK_KURZ if workshop.skript_verdichtet_aktiv() else ""


def _wb_szenen_verdichtet_html(szenen: list[dict]) -> str:
    """Workbench unter ``[skript] verdichtet``: je Szene Titel, Kurzform, die
    staerksten Zitate und aufklappbar ALLE uebernommenen (nur gepruefte)."""
    stuecke = []
    for s in szenen:
        v = s.get("verdichtet") or {}
        kopf = "<b>{nr}. {titel}</b>".format(
            nr=_t("—" if s["nummer"] is None else str(s["nummer"])),
            titel=_t(s.get("titel"), T._TEXT_OHNE_TITEL),
        )
        teile = [kopf, _liste_html("wb-kern", _kurzform_punkte(v), PLANUNG_PUNKT_ZEICHEN),
                 _liste_html("wb-zitate", _staerkste_zitate(v), KERNSATZ_ZEICHEN)]
        alle = v.get("zitate") or []
        if alle:
            punkte = "".join(
                "<li>{z}{q}</li>".format(
                    z=_t("“" + " ".join(str(z["zitat"]).split()) + "”"),
                    q=_t(f" ({z['interview']})") if z.get("interview") else "",
                )
                for z in alle
            )
            teile.append(
                f'<details class="wb-alle"><summary>'
                f'{_t(T._TEXT_ALLE_ZITATE.format(anzahl=len(alle)))}</summary>'
                f"<ul>{punkte}</ul></details>"
            )
        stuecke.append(f'<li class="wb-szene">{"".join(teile)}</li>')
    return f'<ul class="wb-szenen">{"".join(stuecke)}</ul>'


def _rollenleiste_html(sprecher: list[str], figuren: list[dict]) -> str:
    """Die Leiste mit den Figuren des Stuecks -- oder gar nichts.

    **Gar nichts, wenn keine Sprecherzeile erkannt wurde** (Birk, 06.09.2026):
    eine Leiste, die nichts hervorhebt, ist schlimmer als keine. Genau das ist
    der Fall bei einem Stueck, das erst als Geschichte (Phase 6, Prosa)
    dasteht -- dort gibt es keine Repliken, und der Filter haette nichts zu
    tun.

    Gezeigt werden die Sprecher in der Reihenfolge ihres ersten Auftritts, mit
    der Schreibweise aus der Figurenliste, wo es eine gibt ("Leyla" statt
    "LEYLA") -- die steht auch im Link (``#figur=Leyla``), und der soll
    lesbar sein."""
    if not sprecher:
        return ""
    namen = {(f["name"] or "").upper(): f["name"] for f in figuren if f.get("name")}
    knoepfe = [
        '<button type="button" class="rolle" data-figur="" data-name="" '
        f'aria-pressed="true">{_t(T._TEXT_ALLE)}</button>'
    ]
    for name in sprecher:
        anzeige = namen.get(name, name.title())
        knoepfe.append(
            f'<button type="button" class="rolle" data-figur="{_t(name)}" '
            f'data-name="{_t(anzeige)}" aria-pressed="false">{_t(anzeige)}</button>'
        )
    return (
        f'<div class="leiste rollen"><span class="marke">{_t(T._TEXT_ROLLE)}</span>'
        + "".join(knoepfe)
        + "</div>"
    )


_CSS_TEXTBUCH = """
body { background: #fbfaf7; color: #1b1b1b; max-width: 46rem; margin: 0 auto;
       padding: .8rem 1.1rem 4rem; }
h1 { font-size: 1.35rem; margin: 0 0 .2rem; }
.wege { font-size: .85rem; margin: 0 0 .8rem; }
.wege a { color: #6b5a2b; margin-right: .9rem; }
.leiste { display: flex; flex-wrap: wrap; align-items: center; gap: .35rem;
          margin: 0 0 .5rem; }
.leiste .marke { font-size: .72rem; text-transform: uppercase;
                 letter-spacing: .04em; opacity: .55; margin-right: .3rem; }
.leiste button { font: inherit; font-size: .9rem; padding: .35rem .7rem;
                 border: 1px solid #cfc8b6; border-radius: 1rem;
                 background: #fff; color: #1b1b1b; cursor: pointer; }
.leiste button[aria-pressed="true"] { background: #2f4858; border-color: #2f4858;
                                      color: #fff; }
.probe-szene { margin: 0 0 2.2rem; }
.szenenkopf { font-size: 1.15rem; border-bottom: 1px solid #ddd8cc;
              padding-bottom: .2rem; margin: 1.6rem 0 .4rem; }
.angaben, .besetzung { font-size: .85rem; opacity: .7; margin: .1rem 0; }
.offen { font-style: italic; opacity: .6; margin: .6rem 0 .2rem; }
.planung dt { font-size: .74rem; }
.planung-liste { margin: .2rem 0 .6rem 1.1rem; padding: 0; }
.planung-liste li { margin: .15rem 0; }
.planung-liste li.mehr { list-style: none; opacity: .65; font-size: .85em; }
.text { margin-top: .7rem; }
.text p { margin: 0 0 .55rem; }
.interviewzitat { margin: .3rem 0 .7rem; padding: .35rem .8rem; border-left: 3px solid #b8863b; background: rgba(184,134,59,.08); font-style: normal; }
.interviewzitat em:first-child { font-size: .78em; letter-spacing: .03em; text-transform: uppercase; opacity: .75; font-style: normal; display: block; }
.sprecher { letter-spacing: .03em; }
.regie { opacity: .65; font-style: italic; }
/* Der Rollenfilter daempft, er loescht nicht: die Stichworte muss man
   mitlesen koennen, sonst weiss niemand, wann der eigene Einsatz kommt. */
body[data-figur] .replik { opacity: .35; }
body[data-figur] .replik.aktiv { opacity: 1; background: #fff6d9;
                                 border-left: 3px solid #c9b98d;
                                 padding: .15rem .4rem; margin-left: -.4rem; }
body[data-figur] .regie-zeile, body[data-figur] .prosa { opacity: .45; }
body.ohne-regie .regie, body.ohne-regie .regie-zeile { display: none; }
body[data-schrift="gross"] .text { font-size: 1.35rem; line-height: 1.6; }
body[data-schrift="mittel"] .text { font-size: 1.12rem; line-height: 1.55; }
body[data-schrift="klein"] .text { font-size: 1rem; line-height: 1.45; }
/* Der Ausdruck IST das PDF (06.09.2026): keine Abhaengigkeit, kein Dienst,
   kein Layoutprogramm -- der Browser kann das. Deshalb faellt hier alles
   weg, was Bedienung ist, und uebrig bleibt ein Manuskript: Serifenschrift,
   Sprecher fett, je Szene eine neue Seite. */
@media print {
  body { background: #fff; color: #000; max-width: none; margin: 0;
         padding: 0; font-family: Georgia, "Times New Roman", serif;
         font-size: 12pt; line-height: 1.5; }
  .wege, .leiste, .hinweis-druck { display: none !important; }
  .probe-szene { break-after: page; page-break-after: always; }
  .probe-szene:last-child { break-after: auto; page-break-after: auto; }
  .szenenkopf { break-after: avoid; page-break-after: avoid; }
  .replik, .regie-zeile, .prosa { break-inside: avoid; page-break-inside: avoid; }
  /* Im Ausdruck gilt kein Filter: gedruckt wird das ganze Stueck, auch wenn
     am Telefon gerade eine Rolle hervorgehoben ist. */
  body[data-figur] .replik, body[data-figur] .replik.aktiv,
  body[data-figur] .regie-zeile, body[data-figur] .prosa {
        opacity: 1; background: none; border: 0; padding: 0; margin-left: 0; }
  .sprecher { font-weight: 700; }
  .angaben, .besetzung { opacity: 1; font-size: 10pt; }
}
"""

#: Eigene Konstante statt Zusatz zu ``_CSS_TEXTBUCH``: dessen Wortlaut ist
#: im Text-Schnappschuss festgehalten (Dortmund bitgleich).
_CSS_TEXTBUCH_FASSUNGEN = """
details.fruehere, details.erstentwurf { margin: .6rem 0 0; font-size: .92rem; }
details.fruehere summary, details.erstentwurf summary { cursor: pointer;
    font-size: .85rem; opacity: .7; }
details.fruehere .text, details.erstentwurf .text { border-left: 2px solid #ddd8cc;
    padding-left: .6rem; opacity: .8; }
@media print {
  details.fruehere, details.erstentwurf { display: none; }
}
"""

#: Der Zustand der Probenansicht steht im URL-Fragment (``#figur=Leyla&
#: schrift=gross&regie=aus``) und sonst nirgends: kein Server-Roundtrip
#: (die Seite ist statisch), kein localStorage (der Link soll teilbar sein --
#: "so liest sich das mit meiner Rolle"), keine Cookies. Faellt JavaScript
#: aus, bleibt das ganze Stueck lesbar; nur die Leisten wirken dann nicht.
_TEXTBUCH_JS = """
(function () {
  // Die Wurzel, an der der Zustand haengt. Auf der Probenansicht ist das
  // der <body> (er traegt selbst data-textbuch); auf der vereinten Seite
  // (Karte W) das Panel -- sonst faerbte der Rollenfilter auch den Chat.
  var wurzel = document.querySelector('[data-textbuch]') || document.body;
  var lies = function () {
    var s = {};
    location.hash.replace(/^#/, '').split('&').forEach(function (paar) {
      if (!paar) { return; }
      var teile = paar.split('=');
      var k = decodeURIComponent(teile[0].replace(/\\+/g, ' '));
      if (k) { s[k] = decodeURIComponent((teile[1] || '').replace(/\\+/g, ' ')); }
    });
    return s;
  };
  var schreib = function (name, wert) {
    var s = lies();
    if (wert) { s[name] = wert; } else { delete s[name]; }
    var text = Object.keys(s).map(function (k) {
      // Ein Schluessel ohne Wert bleibt ohne Gleichheitszeichen: so
      // ueberlebt '#textbuch' (der Tab der vereinten Seite) einen Klick auf
      // den Rollenfilter, statt zu '#textbuch=' zu werden.
      return s[k] === '' ? encodeURIComponent(k)
        : encodeURIComponent(k) + '=' + encodeURIComponent(s[k]);
    }).join('&');
    // Ueber location.hash, damit der Zurueck-Knopf des Browsers den
    // vorigen Zustand wiederherstellt -- und damit der Link, den jemand
    // kopiert, wirklich der ist, den er gerade sieht.
    location.hash = text ? '#' + text : '';
    wende_an();
  };
  var wende_an = function () {
    var s = lies();
    var figur = (s.figur || '').trim();
    var koerper = wurzel;
    var schluessel = '';
    wurzel.querySelectorAll('.rolle').forEach(function (knopf) {
      var name = knopf.dataset.name || '';
      var passt = figur !== '' && name.toLowerCase() === figur.toLowerCase();
      if (passt) { schluessel = knopf.dataset.figur || ''; }
      knopf.setAttribute('aria-pressed', passt ? 'true' : 'false');
    });
    var alle = wurzel.querySelector('.rolle[data-figur=""]');
    if (alle && !schluessel) { alle.setAttribute('aria-pressed', 'true'); }
    if (schluessel) { koerper.dataset.figur = schluessel; }
    else { delete koerper.dataset.figur; }
    wurzel.querySelectorAll('.replik').forEach(function (p) {
      p.classList.toggle('aktiv', !!schluessel && p.dataset.figur === schluessel);
    });
    var schrift = s.schrift || 'mittel';
    koerper.dataset.schrift = schrift;
    wurzel.querySelectorAll('.schrift').forEach(function (knopf) {
      knopf.setAttribute(
        'aria-pressed', knopf.dataset.schrift === schrift ? 'true' : 'false');
    });
    var ohne = (s.regie || '') === 'aus';
    koerper.classList.toggle('ohne-regie', ohne);
    wurzel.querySelectorAll('.regie-schalter').forEach(function (knopf) {
      knopf.setAttribute('aria-pressed', ohne ? 'true' : 'false');
    });
  };
  document.addEventListener('click', function (ev) {
    var knopf = ev.target.closest ? ev.target.closest('button') : null;
    if (!knopf) { return; }
    if (knopf.classList.contains('rolle')) {
      schreib('figur', knopf.dataset.name || '');
    } else if (knopf.classList.contains('schrift')) {
      schreib('schrift', knopf.dataset.schrift || '');
    } else if (knopf.classList.contains('regie-schalter')) {
      schreib('regie', wurzel.classList.contains('ohne-regie') ? '' : 'aus');
    }
  });
  window.addEventListener('hashchange', wende_an);
  wende_an();
})();
"""


def textbuch_koerper(
    daten: dict, token: str | None = None, praefix: str = VORGABE_PRAEFIX
) -> str:
    """Der Rumpf der Probenansicht -- ohne die Klammer aus ``_seite``.

    Herausgeloest fuer die vereinte Seite (30.09.2026, Karte W), siehe
    ``gruppe_koerper``. Enthaelt **ausschliesslich** Szenentexte und
    Szenenplanung. Kein Interview, kein Journal, kein Belegzitat, keine
    Verdichtung, kein Nachrichtentext -- die Grenze aus docs/agents/weboberflaeche.md
    gilt hier strenger als auf der Gruppenseite, weil
    dieser Link im Probenraum herumgereicht wird."""
    bekannte = {(f["name"] or "").upper() for f in daten["figuren"] if f.get("name")}
    abschnitte = []
    sprecher: list[str] = []
    fassungen = daten.get("fassungen") or {}
    erstentwuerfe = daten.get("erstentwuerfe") or {}
    for s in daten["szenen"]:
        s = {
            **s,
            "_fassungen": fassungen.get(s.get("id")) or [],
            "_erstentwurf": erstentwuerfe.get(s.get("id")),
        }
        html_stueck, gefunden = _probe_szene_html(s, bekannte)
        abschnitte.append(html_stueck)
        for name in gefunden:
            if name not in sprecher:
                sprecher.append(name)
    stueck = "".join(abschnitte) or f'<p class="leer">{_t(T._TEXT_STUECK_LEER)}</p>'
    partitur = _partitur_html(daten["szenen"])
    if partitur:
        stueck = partitur + stueck
    if (daten.get("stage_kopf") or "").strip():
        stueck = (f'<section class="probe-szene stage-kopf">'
                  f'<div class="text">{_prosa_absaetze_html(daten["stage_kopf"])}</div>'
                  f"</section>") + stueck
    titel = daten["titel"] or T._TEXT_GRUPPE.format(chat_id=daten["chat_id"])
    wege = ""
    if token:
        wege = (
            f'<p class="wege"><a href="{_t(praefix, "")}/g/{_t(token)}">'
            f"{_t(T._TEXT_ZUM_ARBEITSSTAND)}</a>"
            f'<a href="{_t(praefix, "")}/g/{_t(token)}/textbuch.md">'
            f"{_t(T._TEXT_TEXTBUCH_MD)}</a>"
            f'<a href="{_t(praefix, "")}/g/{_t(token)}/textbuch.txt">'
            f"{_t(T._TEXT_TEXTBUCH_TXT)}</a>"
            + (f'<a class="pdf-knopf" href="{_t(praefix, "")}/g/{_t(token)}/textbuch.pdf" '
               f'target="_blank" rel="noopener">{_t(T._TEXT_PDF)}</a>' if _pdf_aktiv() else "")
            + "</p>"
        )
    leisten = _rollenleiste_html(sprecher, daten["figuren"]) + (
        f'<div class="leiste"><span class="marke">{_t(T._TEXT_SCHRIFT)}</span>'
        '<button type="button" class="schrift" data-schrift="klein" '
        f'aria-pressed="false">{_t(T._TEXT_SCHRIFT_KLEIN)}</button>'
        '<button type="button" class="schrift" data-schrift="mittel" '
        f'aria-pressed="true">{_t(T._TEXT_SCHRIFT_MITTEL)}</button>'
        '<button type="button" class="schrift" data-schrift="gross" '
        f'aria-pressed="false">{_t(T._TEXT_SCHRIFT_GROSS)}</button>'
        '<button type="button" class="regie-schalter" aria-pressed="false">'
        f"{_t(T._TEXT_REGIE_AUS)}</button></div>"
    )
    kopfzeile = T._TITEL_PROBENANSICHT.format(titel=titel)
    rumpf = (
        f"<h1>{_t(kopfzeile)}</h1>\n"
        f"{wege}{leisten}\n"
        f'<article class="stueck">{stueck}</article>\n'
        f'<p class="hinweis-druck leer">{_t(T._TEXT_DRUCKEN)}</p>'
    )
    # Stempel fuer das Nachladen im Browser (P57 Lauf 3, A1): der Client
    # vergleicht ihn mit dem des Panels und tauscht nur bei Unterschied.
    import hashlib

    stempel = hashlib.sha1(rumpf.encode("utf-8")).hexdigest()[:16]
    return f'<span hidden data-stempel="{stempel}"></span>{rumpf}'


def textbuch_html(
    daten: dict, token: str | None = None, praefix: str = VORGABE_PRAEFIX
) -> str:
    """Die Probenansicht aus ``web_daten.gruppe_nach_token()``.

    Enthaelt **ausschliesslich** Szenentexte und Szenenplanung. Kein
    Interview, kein Journal, kein Belegzitat, keine Verdichtung, kein
    Nachrichtentext -- die Grenze aus docs/agents/weboberflaeche.md gilt hier
    strenger als auf der Gruppenseite, weil dieser Link im Probenraum
    herumgereicht wird."""
    from interview_theater import web_gestalt

    titel = daten["titel"] or T._TEXT_GRUPPE.format(chat_id=daten["chat_id"])
    kopfzeile = T._TITEL_PROBENANSICHT.format(titel=titel)
    return _seite(
        kopfzeile,
        # Gestaltung zuletzt (Karte UX). Die Probenansicht ist eine eigene
        # Seite, also ungescopt -- es gibt hier kein Panel.
        _CSS_TEXTBUCH + _CSS_TEXTBUCH_FASSUNGEN + web_gestalt.css_rahmen() + web_gestalt.css_textbuch()
        + css_textbuch_lesbar(),
        textbuch_koerper(daten, token, praefix),
        nachladen=False,
        skript=_TEXTBUCH_JS,
        koerper_attribute=' data-textbuch=""',
    )
#: Was auf der Leitfaden-Seite steht, solange es keinen gibt. Ruhig und ohne
#: Fehlerton: die Seite ist richtig, der Leitfaden ist nur noch nicht fertig.
TEXT_LEITFADEN_LEER = "Der Leitfaden entsteht in Phase 2."
TEXT_LEITFADEN_ZURUECK = "← zurück zum Arbeitsstand"


def leitfaden_html(daten: dict) -> str:
    """Die Leitfaden-Ansicht ``/g/<token>/leitfaden`` -- das Dokument, das
    eine Sechzehnjährige in der Hand hält, wenn sie eine fremde Person
    anspricht (06.09.2026).

    **Gebaut aus derselben Funktion wie der Chat-Text**
    (``leitfaden.bausteine``, auf der ``leitfaden.aus_feldern`` ebenfalls
    steht): keine zweite Wahrheit, nur ein anderer Satz. Groß, hoher
    Kontrast, jede Frage in einem eigenen Block -- und mit einer
    ``@media print``-Regel, damit man sie ausdrucken kann.

    **Kein Nachladen, kein POST, kein Nonce.** Die Seite bekommt deshalb auch
    nicht den Rahmen der beiden anderen (``_seite``): das sanfte Nachladen
    würde einer Interviewerin mitten im Gespräch den Text unter dem Daumen
    austauschen.

    Steht noch kein Leitfaden, kommt eine ruhige Seite und kein Fehler."""
    from interview_theater import leitfaden, web_gestalt

    titel = daten["titel"] or T._TEXT_GRUPPE.format(chat_id=daten["chat_id"])
    teil = leitfaden.bausteine(daten["arbeitsstand"])
    if teil is None:
        koerper = f'<p class="leer">{html.escape(T.TEXT_LEITFADEN_LEER)}</p>'
    else:
        koerper = _leitfaden_blocks(teil, leitfaden)
    zurueck = (
        f'<a class="zurueck" href="../{_t(daten["token"], "")}">'
        f"{html.escape(T.TEXT_LEITFADEN_ZURUECK)}</a>"
        if daten.get("token")
        else ""
    )
    return (
        "<!doctype html>\n"
        f'<html lang="{html.escape(sprache.code())}"><head><meta charset="utf-8">\n'
        f"{_VIEWPORT_META}\n"
        f"<title>{html.escape(T._TITEL_LEITFADEN.format(titel=titel))}</title>\n"
        f"<style>{_CSS_LEITFADEN + web_gestalt.css_rahmen()}</style></head>\n<body>\n"
        f"<h1>{_t(titel)}</h1>\n{koerper}\n{zurueck}\n"
        "</body></html>\n"
    )


def _leitfaden_blocks(teil: dict, leitfaden) -> str:
    """Eröffnung, dann jede Frage einzeln, dann der Abschluss.

    Die Überschriften sind wortgleich die des Chat-Texts
    (``leitfaden.UEBERSCHRIFT_*``) -- wer beides nebeneinander hält, soll
    dasselbe Dokument erkennen."""
    stuecke = []
    if teil["eroeffnung"]:
        stuecke.append(
            f'<div class="block"><h2>{html.escape(leitfaden.T.UEBERSCHRIFT_EROEFFNUNG)}'
            f'</h2><p class="sagen">{_t(teil["eroeffnung"])}</p></div>'
        )
    stuecke.append(f"<h2>{html.escape(leitfaden.T.UEBERSCHRIFT_FRAGEN)}</h2>")
    for frage in teil["fragen"]:
        block = (
            f'<div class="frage"><span class="nummer">{frage["nummer"]}</span>'
            f'<p>{_t(frage["text"])}</p>'
        )
        if frage["einleitung"]:
            block += (
                f'<div class="vorher">'
                f'{_t(T._TEXT_VORHER_SAGEN.format(text=frage["einleitung"]))}</div>'
            )
        if frage["kern"]:
            block += f'<div class="kern">{_t(T._TEXT_KERN.format(text=frage["kern"]))}</div>'
        stuecke.append(block + "</div>")
    if teil["abschluss"]:
        stuecke.append(
            f'<div class="block"><h2>{html.escape(leitfaden.T.UEBERSCHRIFT_ABSCHLUSS)}'
            f'</h2><p class="sagen">{_t(teil["abschluss"])}</p></div>'
        )
    return "\n".join(stuecke)


def nicht_gefunden_html() -> str:
    """Antwort auf ein unbekanntes Token oder einen unbekannten Pfad.

    Sagt bewusst nichts darueber, ob es Gruppen gibt oder wie ein gueltiges
    Token aussaehe -- und laedt sich, anders als die beiden echten Seiten,
    nicht selbst neu."""
    titel = html.escape(T._TITEL_NICHT_GEFUNDEN)
    return (
        "<!doctype html>\n"
        f'<html lang="{html.escape(sprache.code())}"><head><meta charset="utf-8">'
        f"{_VIEWPORT_META}"
        f"<title>{titel}</title>"
        f"<style>{_CSS_GEMEINSAM}{_CSS_GRUPPE}</style></head>"
        f"<body><h1>{titel}</h1>"
        f"<p>{html.escape(T._TEXT_NICHT_GEFUNDEN)}</p>"
        "</body></html>\n"
    )


def _pfad_ohne_praefix(pfad: str, praefix: str) -> str:
    """Schneidet das nginx-Praefix ab, falls es noch dransteht.

    Ob ``proxy_pass`` das Praefix weiterreicht, haengt an der nginx-Zeile und
    nicht an diesem Code -- beide Formen anzunehmen kostet vier Zeilen und
    spart eine Fehlersuche am Workshopmorgen."""
    praefix = praefix.rstrip("/")
    if praefix and (pfad == praefix or pfad.startswith(praefix + "/")):
        pfad = pfad[len(praefix):]
    return pfad or "/"


def fassungswahl(query: str) -> dict[int, int]:
    """Liest ``?szene=<id>&fassung=<n>`` und liefert ``{szene_id: nummer}``.

    Nur GET, nur Anzeige (07.09.2026): die Auswahl aendert nichts in der
    Datenbank, deshalb steht sie in der URL und nicht in einem Cookie und
    nicht in einem POST. Alles, was keine Zahl ist, faellt weg statt zu einem
    Fehler zu werden -- ein Tippfehler in der Adresszeile soll die Seite nicht
    kosten. Eine Szene, die es nicht gibt, stoert nicht: ``gruppe_html``
    schlaegt die id nur nach.

    Bewusst genau EIN Paar je Aufruf: mehrere gleichzeitig geoeffnete
    Fassungen sind keine Frage, die jemand hat, und jede weitere waere ein
    zweiter Zustand in der URL, den das sanfte Nachladen mitschleppt."""
    try:
        werte = urllib.parse.parse_qs(query or "")
    except ValueError:
        return {}
    try:
        szene_id = int((werte.get("szene") or [""])[0])
        nummer = int((werte.get("fassung") or [""])[0])
    except (TypeError, ValueError):
        return {}
    if nummer < 1:
        return {}
    return {szene_id: nummer}


#: Wie viel Text ein POST hoechstens tragen darf. Ein Szenenfeld ist ein paar
#: Saetze, eine Frageliste ein paar Zeilen -- 64 KiB sind das Vielfache davon
#: und trotzdem klein genug, dass niemand den Prozess mit einem Upload
#: beschaeftigt.
MAX_POST_BYTES = 64 * 1024


def _beantworte_get(handler, db_pfad: str, praefix: str,
                    schluessel: bytes) -> None:
    """Das Routing der Leseansicht: ``/gesund``, ``/`` (Dashboard) und
    ``/g/<token>`` (Gruppenseite), alles andere 404.

    ``handler`` ist die Instanz aus ``mache_handler``; ausgelagert, weil das
    Routing weder von ``self`` noch von der Klasse abhaengt und in einer
    Fabrikfunktion sonst nur schwer zu finden ist."""
    zerlegt = urllib.parse.urlsplit(handler.path)
    pfad = _pfad_ohne_praefix(urllib.parse.unquote(zerlegt.path), praefix)
    if pfad == "/gesund":
        # Ohne Datenbankzugriff: der Health-Check soll sagen, ob der
        # Prozess laeuft, und nicht ueber die Datenbank mit-scheitern.
        handler._antworte(200, "ok", "text/plain; charset=utf-8")
        return
    try:
        dash_token = os.environ.get("IT_WEB_DASHBOARD_TOKEN", "").strip()
        startseite = os.environ.get("IT_WEB_STARTSEITE", "").strip()
        if pfad == "/" and not dash_token:
            handler._antworte(200, dashboard_html(handler._dashboard(), praefix))
        elif pfad == "/" and startseite:
            # Birk 04.10.2026: unter "/" das oeffentliche Wochenprogramm
            # (statische HTML-Datei, bei jedem Aufruf frisch gelesen -- eine
            # Aenderung in der Datei ist sofort live). Die Uebersicht liegt
            # mit Token unter /dashboard/<token>.
            try:
                with open(startseite, encoding="utf-8") as datei:
                    handler._antworte(200, datei.read())
            except OSError:
                handler._antworte(404, "nicht gefunden")
        elif dash_token and pfad.startswith("/dashboard/") and pfad.endswith("/ticker") and hmac.compare_digest(
                pfad[len("/dashboard/"):-len("/ticker")].encode(), dash_token.encode()):
            # Birk 05.10.2026: derselbe Token-Check wie /dashboard/<token>
            # (unten) -- ein falscher Token ist hier genauso 404, nie ein
            # anderer Status.
            handler._antworte(200, ticker_html())
        elif dash_token and pfad.startswith("/dashboard/") and hmac.compare_digest(
                pfad[len("/dashboard/"):].rstrip("/").encode(), dash_token.encode()):
            # Birk 04.10.2026: die Uebersicht traegt die Links zu ALLEN
            # Gruppen -- offen unter "/" war sie ein Generalschluessel. Mit
            # IT_WEB_DASHBOARD_TOKEN liegt sie nur noch unter /dashboard/<token>,
            # "/" antwortet 404 wie jede unbekannte Adresse. Ohne die
            # Variable bleibt alles wie vorher (Dortmund).
            handler._antworte(200, dashboard_html(handler._dashboard(), praefix, dash_token))
        elif pfad.startswith("/g/"):
            _beantworte_gruppenseite(
                handler, db_pfad, pfad, praefix, schluessel, zerlegt.query
            )
        else:
            handler._antworte(404, nicht_gefunden_html())
    except sqlite3.Error as fehler:
        # Typisch: IT_DB zeigt ins Leere, oder die Datei ist noch
        # nicht angelegt. Kurz und ohne Pfade nach aussen, ausfuehrlich
        # ins Log.
        handler.log_error("Datenbankfehler: %s", fehler)
        handler._antworte(
            500,
            f'<!doctype html><html lang="{html.escape(sprache.code())}"><meta charset="utf-8">'
            f"<p>{html.escape(T._TEXT_DB_NICHT_LESBAR)}</p></html>",
        )


#: Die Telefon-Organisationskarten (UX-Knoepfe-Karte, Abschnitt 5) liegen
#: unter ``/g/<token>/static/handys/<name>.png`` -- unter dem Token, damit
#: ``web_chat.weg()`` (die vorhandene BASIS-Umrechnung fuer die vereinte
#: Seite und die Chat-Einzelseite) sie ohne eigenen Mechanismus erreicht.
STATIC_HANDYS_PRAEFIX = "static/handys/"

#: Strikte Positivliste fuer den Dateinamen -- kein Dateisystempfad aus der
#: URL. Ein ``..`` oder ein Schraegstrich im Namen scheitert schon hier,
#: bevor ueberhaupt ein Pfad gebaut wird.
_STATIC_NAME = re.compile(r"^[a-z0-9-]+\.png$")


def _sende_static_bild(handler, unterpfad: str) -> None:
    """Eine Telefon-Organisationskarte unter ``interview_theater/static/handys/``.

    Kein Tokenbezug: der Inhalt ist nicht gruppenspezifisch (erfunden, keine
    PII) -- dieselben sieben Bilder fuer jede Gruppe. ``unterpfad`` muss
    GENAU ``static/handys/<name>.png`` sein; alles andere (fehlende Datei,
    Name ausserhalb der Positivliste) ist 404, nie ein Dateisystemfehler."""
    from pathlib import Path

    name = unterpfad[len(STATIC_HANDYS_PRAEFIX):]
    if not _STATIC_NAME.fullmatch(name):
        handler._antworte(404, nicht_gefunden_html())
        return
    pfad_auf_platte = Path(__file__).resolve().parent / "static" / "handys" / name
    try:
        inhalt = pfad_auf_platte.read_bytes()
    except OSError:
        handler._antworte(404, nicht_gefunden_html())
        return
    handler._antworte_binaer(200, inhalt, "image/png")


def _beantworte_gruppenseite(handler, db_pfad: str, pfad: str,
                             praefix: str, schluessel: bytes,
                             query: str = "") -> None:
    """Alles unter ``/g/<token>``: die Gruppenseite selbst, die Probenansicht
    (``/textbuch``), das Textbuch als Datei und die Leitfaden-Seite.

    Hinter dem Token darf seit der Probenansicht noch etwas stehen
    (06.09.2026). Alles Unbekannte wird 404 und nicht etwa als Teil des Tokens
    gelesen -- sonst haette ``/g/<token>/irgendwas`` dieselbe Seite geliefert
    wie ``/g/<token>``."""
    from interview_theater import leitfaden as leitfaden_modul

    rest = pfad[len("/g/"):].strip("/")
    token, _, unterpfad = rest.partition("/")
    if unterpfad.startswith(STATIC_HANDYS_PRAEFIX):
        _sende_static_bild(handler, unterpfad)
        return
    if unterpfad in ("textbuch.md", "textbuch.txt"):
        _sende_textbuch_datei(handler, db_pfad, token, unterpfad)
        return
    if unterpfad == "textbuch.pdf" and _pdf_aktiv():
        # Padua (Birk 07.10.2026 ~19:35): das Stage Script als PDF, gedruckt
        # aus derselben Probenansicht (``web_pdf``).
        from interview_theater import web_pdf

        daten = handler._gruppe(token)
        if daten is None:
            handler._antworte(404, nicht_gefunden_html())
        else:
            web_pdf.sende(handler, daten, token, praefix)
        return
    if unterpfad == leitfaden_modul.WEB_PFAD:
        daten = _leitfaden_daten(db_pfad, token)
        if daten is None:
            handler._antworte(404, nicht_gefunden_html())
            return
        # Die Leitfaden-Seite verlinkt zurueck auf die Gruppenseite und
        # braucht dafuer ihr Token.
        daten["token"] = token
        handler._antworte(200, leitfaden_html(daten))
        return
    # Der Chat im Browser (30.09.2026, Karte Padua A2) und die vereinte Seite
    # (30.09.2026, Karte W). Nur die Weiche steht hier -- HTML, CSS, JS und
    # Handler liegen in web_chat.py bzw. web_vereint.py, damit diese Datei
    # nicht weiter waechst. Der Import steht in der Funktion, wie bei
    # ``leitfaden`` und ``szenenfolge``: beide Module importieren ihrerseits
    # ``web`` (fuer ``_seite``), und das waere im Modulkopf ein Zyklus.
    from interview_theater import web_chat, web_vereint

    if unterpfad.startswith(web_vereint.TEIL_PFAD + "/"):
        web_vereint.sende_teil(
            handler, db_pfad, token,
            unterpfad[len(web_vereint.TEIL_PFAD) + 1:], praefix, schluessel, query,
        )
        return
    if unterpfad == web_chat.CHAT_PFAD:
        # Ein Schraegstrich am Ende (``/chat/``) bleibt 404 wie bisher
        # (Review-Befund 12, ``web_chat.beantworte_get``): ``rest.strip("/")``
        # oben hat ihn schon verschluckt, deshalb der Blick auf den rohen Pfad.
        if urllib.parse.urlsplit(handler.path).path.endswith("/"):
            handler._antworte(404, nicht_gefunden_html())
            return
        # Abschlussreview I3 gilt weiter: eine Telegram-Gruppe hat keinen Bot,
        # der ``web_post`` liest, und ``/chat`` bleibt dort 404 -- nicht etwa
        # ein Umweg auf die (fuer jede Gruppe gueltige) vereinte Seite.
        lesend = web_daten.oeffne_lesend(db_pfad)
        try:
            ist_web_gruppe = web_daten.web_chat_id_nach_token(lesend, token) is not None
        finally:
            lesend.close()
        if not ist_web_gruppe:
            handler._antworte(404, nicht_gefunden_html())
            return
        # Die Chatansicht ist in der vereinten Seite aufgegangen (Karte W) --
        # zwei Chats nebeneinander waeren zwei Zustaende. Gedruckte Links aus
        # der Zeit von Karte A2 landen im richtigen Tab.
        handler.send_response(302)
        handler.send_header("Location", f"{praefix}/g/{token}#{web_vereint.VORGABE_TAB}")
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        return
    if unterpfad.startswith(web_chat.CHAT_PFAD + "/"):
        web_chat.beantworte_get(
            handler, db_pfad, token,
            unterpfad[len(web_chat.CHAT_PFAD):].strip("/"),
            praefix, schluessel, query,
        )
        return
    if unterpfad not in ("", "textbuch"):
        handler._antworte(404, nicht_gefunden_html())
        return
    if unterpfad == "textbuch":
        daten = handler._gruppe(token)
        if daten is None:
            handler._antworte(404, nicht_gefunden_html())
        else:
            handler._antworte(200, textbuch_html(daten, token, praefix))
        return
    web_vereint.beantworte_seite(handler, db_pfad, token, praefix, schluessel, query)


def _pdf_aktiv() -> bool:
    """Das PDF des Stage Scripts gibt es nur unter ``[karten] aktiv``."""
    from interview_theater import workshop

    return workshop.szenenkarten_aktiv()


_TEXT_PDF = "PDF"
_TEXT_PDF_FEHLER = "Das PDF liess sich gerade nicht erzeugen. Bitte gleich noch einmal versuchen."


def _sende_textbuch_datei(handler, db_pfad: str, token: str, name: str) -> None:
    """Das Textbuch als Datei: ``.md`` und ``.txt``, beide mit demselben
    Inhalt.

    Der Inhalt kommt aus ``szenenfolge.textbuch`` -- **derselben Funktion**,
    die der Knopf "Textbuch als Datei" im Chat benutzt. Eine zweite Fassung
    hier waere eine zweite Wahrheit: die Gruppe haette zwei Textbuecher, die
    sich irgendwann unterscheiden, und niemand wuesste welches gilt.

    Der Import steht in der Funktion und nicht im Modulkopf, wie bei
    ``leitfaden``: ``szenenfolge`` zieht den Szenen-Prompt und damit den halben
    Bot nach, und der Webserver soll ohne das starten koennen, solange niemand
    ein Textbuch abruft. Gelesen wird ueber die read-only geoeffnete
    Verbindung -- ``textbuch`` fragt nur ab (``repo.hole_szenen``,
    ``repo.hole_arbeitsstand``, ``szenenfolge.vorstellung``), es schreibt
    nichts."""
    from interview_theater import szenenfolge

    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        chat_id = web_daten.chat_id_nach_token(conn, token)
        if chat_id is None:
            handler._antworte(404, nicht_gefunden_html())
            return
        inhalt = szenenfolge.textbuch(conn, chat_id)
    finally:
        conn.close()
    typ = (
        "text/markdown; charset=utf-8"
        if name.endswith(".md")
        else "text/plain; charset=utf-8"
    )
    handler._antworte(200, inhalt, typ, dateiname=name)


def _leitfaden_daten(db_pfad: str, token: str) -> dict | None:
    """Nur der Arbeitsstand -- die Leitfaden-Seite laedt weder Szenen noch
    Interviews noch das Journal."""
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        return web_daten.leitfaden_nach_token(conn, token)
    finally:
        conn.close()


def _beantworte_post(handler, db_pfad: str, praefix: str, schluessel: bytes) -> None:
    """Ein geaenderter Parameter der Gruppenseite.

    Die Reihenfolge der Pruefungen ist Absicht: **Pfad, Herkunft, Token, Nonce, Wert** --
    erst 404, dann 403, dann 404 (Token), dann 403 (Nonce), dann 400. Die
    Herkunftspruefung sitzt VOR der Token-Extraktion: sie braucht nur die
    Kopfzeilen, und ein Angriff ueber einen Browser traegt die Merkmale (E-S9).
    Ein unbekanntes Token bekommt dieselbe 404 wie beim GET (die Seite
    verraet ohnehin schon, ob es sie gibt); der Nonce wird erst danach
    geprueft, weil er an das Token gebunden ist und fuer ein Token, das es
    nicht gibt, gar nicht gueltig sein kann.

    **Das Dashboard ist nicht dabei.** ``/`` nimmt kein POST an: es haengt am
    Beamer und ist projiziert, dort soll niemand im Vorbeigehen etwas
    umstellen.

    Mit ``[web] workbench_bearbeitbar = false`` (Padua) antwortet dieser Weg
    immer 403 -- nach Pfad und Herkunft, vor Token und Nonce."""
    pfad = _pfad_ohne_praefix(
        urllib.parse.unquote(urllib.parse.urlsplit(handler.path).path), praefix
    )
    if not pfad.startswith("/g/"):
        schliesse_nach_antwort(handler)
        handler._antworte(404, nicht_gefunden_html())
        return
    if not eigene_herkunft(handler):
        schliesse_nach_antwort(handler)
        handler._fehler(403, T.TEXT_FREMDE_HERKUNFT)
        return
    from interview_theater import web_chat

    rest = pfad[len("/g/"):].strip("/")
    token, _, unterpfad = rest.partition("/")
    if unterpfad == web_chat.CHAT_PFAD or unterpfad.startswith(web_chat.CHAT_PFAD + "/"):
        web_chat.beantworte_post(
            handler, db_pfad, token,
            unterpfad[len(web_chat.CHAT_PFAD):].strip("/"),
            schluessel,
        )
        return
    if unterpfad:
        # Vorher wurde daraus ein Token mit Schraegstrich darin und damit
        # ebenfalls 404 -- jetzt ausdruecklich.
        schliesse_nach_antwort(handler)
        handler._antworte(404, nicht_gefunden_html())
        return
    from interview_theater import workshop

    if not workshop.workbench_bearbeitbar():
        # Padua (03.10.2026): die Werkbank ist reine Anzeige, geaendert wird
        # im Chat. NUR dieser Weg -- die Chat-POSTs oben laufen weiter. Vor
        # dem Lesen des Rumpfes und vor der Token-Suche: es gibt nichts, was
        # hier je wirken duerfte, also auch nichts zu verraten.
        schliesse_nach_antwort(handler)
        handler._fehler(403, T._TEXT_WERKBANK_NUR_LESEN)
        return
    try:
        daten = handler._koerper()
    except ValueError as fehler:
        handler._fehler(400, str(fehler))
        return
    try:
        lesend = web_daten.oeffne_lesend(db_pfad)
        try:
            gruppe = web_daten.gruppe_nach_token(lesend, token)
        finally:
            lesend.close()
        if gruppe is None:
            handler._antworte(404, nicht_gefunden_html())
            return
        if not nonce_gueltig(schluessel, token, daten.get("nonce")):
            handler._fehler(403, T._TEXT_SEITE_VERALTET)
            return
        antwort = handler._schreibe(gruppe["chat_id"], daten)
    except web_schreiben.Fehler as fehler:
        handler._fehler(400, str(fehler))
        return
    except sqlite3.Error as fehler:
        handler.log_error("Datenbankfehler beim Schreiben: %s", fehler)
        handler._fehler(500, T._TEXT_DB_NICHT_BESCHREIBBAR)
        return
    handler._antworte(
        200,
        json.dumps(antwort, ensure_ascii=False),
        "application/json; charset=utf-8",
    )


class _Basishandler(BaseHTTPRequestHandler):
    """Alles am Handler, was die Konfiguration nicht braucht: Antworten,
    Fehler, Anfragerumpf, Logzeile.

    Steht auf Modulebene statt in ``mache_handler``, weil eine Klasse, die
    nichts aus der Fabrik liest, dort nur den Blick auf das verstellt, was
    wirklich je Server verschieden ist."""

    server_version = "interview-theater"
    #: Leer, damit ``version_string()`` nicht "interview-theater
    #: Python/3.11.15" liefert. Gemessen: die Vorgabe der
    #: Standardbibliothek ist ``'Python/3.11.15'`` und stand bis heute im
    #: Server-Header jeder Antwort. Eine Versionsnummer ist der erste
    #: Baustein jedes gezielten Angriffs und der Gruppe voellig gleichgueltig.
    sys_version = ""
    protocol_version = "HTTP/1.1"
    #: HTTP/1.1 haelt die Verbindung offen, und ThreadingHTTPServer bindet
    #: je Verbindung einen Thread. Ohne Zeitlimit blieben die Threads
    #: stiller Browser-Tabs (Beamer, drei Gruppen mit Handy) fuer immer
    #: liegen; nach 30 s ohne neue Anfrage wird die Verbindung geschlossen.
    timeout = 30

    #: Von ``mache_handler`` gesetzt. ``_Basishandler`` liest sie nur fuer
    #: den CSP-Nonce -- die Klasse bleibt sonst konfigurationsfrei.
    schluessel: bytes | None = None
    praefix: str = ""

    def version_string(self) -> str:
        """Nur ``server_version`` -- die Vorlage der Standardbibliothek
        haengt ``' ' + sys_version`` an, auch wenn ``sys_version`` leer ist,
        und der Server-Header truege sonst ein Leerzeichen am Ende."""
        return self.server_version

    def _koerper(self) -> dict:
        """Der JSON-Rumpf der Anfrage. Alles, was hier schiefgeht, ist ein
        Bedienfehler von aussen und wird zu 400, nie zu einem Stacktrace."""
        # Jede Ablehnung hier liegt VOR dem Lesen -- der Koerper bliebe im
        # Socket (``schliesse_nach_antwort``).
        try:
            laenge = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            schliesse_nach_antwort(self)
            raise ValueError(T._TEXT_UNGUELTIG) from None
        if laenge <= 0:
            schliesse_nach_antwort(self)
            raise ValueError(T._TEXT_LEER_ANFRAGE)
        if laenge > MAX_POST_BYTES:
            schliesse_nach_antwort(self)
            raise ValueError(T._TEXT_ZU_LANG)
        try:
            gelesen = json.loads(self.rfile.read(laenge).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError(T._TEXT_UNGUELTIG) from None
        if not isinstance(gelesen, dict):
            raise ValueError(T._TEXT_UNGUELTIG)
        return gelesen

    def _fehler(self, status: int, text: str) -> None:
        """Fehler als Klartext, nicht als JSON: ``_BEARBEITEN_JS`` zeigt
        den Rumpf einer 4xx-Antwort unveraendert neben dem Feld an, und
        die Gruppe soll dort einen Satz lesen, keine geschweifte
        Klammer."""
        self._antworte(status, text, "text/plain; charset=utf-8")

    def _antworte(
        self, status: int, inhalt: str, typ: str = "text/html; charset=utf-8",
        dateiname: str | None = None,
    ) -> None:
        if typ.startswith("text/html"):
            inhalt = mit_nonce(inhalt, self._csp_nonce())
        roh = inhalt.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(roh)))
        if dateiname:
            # Damit das Telefon die Datei ablegt, statt sie im Browser
            # anzuzeigen -- der Weg in die Probe ist "herunterladen und
            # weiterschicken". Der Name kommt aus dem Code, nie aus der
            # URL (keine fremden Zeichen im Header).
            self.send_header(
                "Content-Disposition", f'attachment; filename="{dateiname}"'
            )
        # Der Browser soll bei jedem Neuladen wirklich neu fragen --
        # sonst zeigt der Beamer eine Viertelstunde alte Zahlen.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(roh)

    def _antworte_binaer(self, status: int, inhalt: bytes, typ: str) -> None:
        """Wie ``_antworte``, nur fuer Bytes statt Text -- die
        Telefon-Organisationskarten (UX-Knoepfe-Karte, Abschnitt 5).
        ``inhalt.encode("utf-8")`` in ``_antworte`` wuerde ein PNG
        zerstoeren."""
        self.send_response(status)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(inhalt)))
        # Eine Karte aendert sich nur, wenn der Betreiber den Generator neu
        # laufen laesst -- anders als beim Dashboard darf der Browser sie
        # lange behalten.
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(inhalt)

    def _csp_nonce(self) -> str:
        """Der Nonce dieser Antwort, an das Token der aufgerufenen Seite
        gebunden.

        An das Token, nicht bloss an das Stundenfenster: sonst lernte jeder,
        der das Dashboard im Tailnet oeffnen kann, den Nonce aller
        Gruppenseiten. Ohne Token (Dashboard, /gesund) gilt der leere String
        -- dort gibt es keine Gruppendaten, die eine Einschleusung lohnen."""
        if not self.schluessel:
            return ""
        try:
            pfad = _pfad_ohne_praefix(
                urllib.parse.unquote(urllib.parse.urlsplit(self.path).path),
                self.praefix,
            )
        except Exception:  # noqa: BLE001 -- eine kaputte URL darf hier nichts reissen
            pfad = ""
        token = pfad[len("/g/"):].strip("/").partition("/")[0] if pfad.startswith("/g/") else ""
        return csp_nonce(self.schluessel, token)

    def end_headers(self) -> None:
        """Die **eine** Stelle, an der jede Antwort ihre Kopfzeilen bekommt.

        Nicht in ``_antworte``: ``send_error`` der Standardbibliothek (501
        bei unbekannter Methode, 400 bei kaputter Anfragezeile, 414 bei zu
        langer URI) geht daran vorbei, und genau diese Antworten sind die,
        die niemand von Hand testet."""
        for name, wert in SICHERHEITSKOPFZEILEN:
            self.send_header(name, wert)
        if getattr(self, "verbindung_schliessen", False) and not self.close_connection:
            # ``send_header`` setzt dabei selbst ``close_connection``.
            self.send_header("Connection", "close")
        self.send_header(
            "Content-Security-Policy", CSP_VORLAGE.format(nonce=self._csp_nonce())
        )
        super().end_headers()

    def send_error(self, code, message=None, explain=None) -> None:
        """Die Fehlerseite der Standardbibliothek setzt ``%(message)s`` und
        ``%(explain)s`` in den Koerper (``DEFAULT_ERROR_MESSAGE``). Beide
        kommen aus der Anfrage oder aus dem Innenleben des Servers -- also
        weder das eine noch das andere nach aussen.

        Die Standardbibliothek loggt an dieser Stelle selbst
        (``self.log_error("code %d, message %s", code, message)``) -- das
        geht mit der Ueberschreibung verloren, und genau das waere falsch:
        ohne Logzeile sieht niemand mehr den Sondierungsverkehr (501 bei
        unbekannter Methode, 400 bei kaputter Anfragezeile, 414 bei zu
        langer URI), den diese Haertung gerade abwehrt. Geloggt wird deshalb
        weiterhin, aber nur der Code -- ``message``/``explain`` sind
        angreiferseitiger Text und gehoeren nicht ins Log."""
        self.log_error("code %d", code)
        self.send_response(code)
        roh = _html_500().encode("utf-8")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(roh)))
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(roh)

    def _fuenfhundert(self) -> None:
        """Eine unerwartete Ausnahme: 500 mit festem Kurztext.

        Ohne das bekommt der Browser heute gar keine Antwort -- ``http.server``
        faengt eine Ausnahme aus ``do_GET`` nicht ab, ``socketserver`` schreibt
        den Traceback nach stderr und schliesst die Verbindung
        (gemessen 30.09.2026). Der Traceback bleibt im Log, wo er hingehoert."""
        try:
            self._antworte(500, _html_500())
        except Exception:  # noqa: BLE001 -- die Verbindung ist schon hin
            self.close_connection = True

    def log_message(self, format: str, *args) -> None:
        """Eine Zeile je Anfrage nach stdout (systemd haengt das an
        betrieb/web.log). Ohne Uhrzeit-Klammern der Vorlage, dafuer mit
        ISO-Zeit -- damit die Zeilen zu denen des Bots passen.

        **Das Token wird maskiert und die Query weggeworfen** (30.09.2026):
        es ist das einzige Geheimnis der Gruppenseite, und beim Audio-Upload
        stand der Formular-Nonce in der Query. Ein Log ist das, was man
        weiterschickt, wenn etwas nicht geht."""
        zeile = format % args
        for stueck in zeile.split(" "):
            if "/g/" in stueck or "?" in stueck:
                zeile = zeile.replace(stueck, maskiere_token(stueck))
        print(
            f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} web "
            f"{self.address_string()} {zeile}",
            flush=True,
        )


def mache_handler(
    db_pfad: str, praefix: str = VORGABE_PRAEFIX, schluessel: bytes | None = None
):
    """Baut die Handler-Klasse mit ihrer Konfiguration.

    Als Fabrik statt globaler Variablen, damit ein Test einen zweiten Server
    auf eine andere Datenbank stellen kann. Was die Konfiguration nicht
    braucht, steht in ``_Basishandler``; hier bleibt nur, was ``db_pfad``,
    ``praefix`` oder ``schluessel`` liest.

    ``schluessel`` unterschreibt die Formular-Nonces (siehe ``nonce``). Er
    entsteht beim Start und steht nirgends auf der Platte: ein Neustart macht
    die Nonces offener Seiten ungueltig, die naechste Runde des sanften
    Nachladens holt zehn Sekunden spaeter frische. Ein Test kann ihn
    vorgeben."""
    schluessel = schluessel or secrets.token_bytes(32)

    class Handler(_Basishandler):
        def do_GET(self) -> None:  # noqa: N802 (von BaseHTTPRequestHandler vorgegeben)
            try:
                _beantworte_get(self, db_pfad, praefix, schluessel)
            except Exception:  # noqa: BLE001 -- der Server darf an keiner Anfrage sterben
                self.log_error("Unbehandelte Ausnahme bei GET: %s", traceback.format_exc())
                self._fuenfhundert()

        def do_POST(self) -> None:  # noqa: N802 (von BaseHTTPRequestHandler vorgegeben)
            try:
                _beantworte_post(self, db_pfad, praefix, schluessel)
            except Exception:  # noqa: BLE001
                self.log_error("Unbehandelte Ausnahme bei POST: %s", traceback.format_exc())
                self._fuenfhundert()

        def _schreibe(self, chat_id: int, daten: dict) -> dict:
            """Der eine Schreibvorgang, auf einer eigenen Verbindung.

            ``db.verbinde`` und nicht ``web_daten.oeffne_lesend``: die
            Leseverbindung ist ``mode=ro`` und wuerde jeden Schreibversuch
            abweisen. Die Verbindung wird je Anfrage geoeffnet und wieder
            geschlossen -- WAL und ``busy_timeout`` (5 s) tragen das
            Nebeneinander mit den Bot-Prozessen, wie bei
            ``scripts/begruessen.py``."""
            conn = db.verbinde(db_pfad)
            try:
                return web_schreiben.wende_an(
                    conn,
                    chat_id,
                    str(daten.get("feld") or ""),
                    daten.get("wert"),
                    daten.get("ziel"),
                )
            finally:
                conn.close()

        def _dashboard(self) -> dict:
            conn = web_daten.oeffne_lesend(db_pfad)
            try:
                return web_daten.dashboard(conn)
            finally:
                conn.close()

        def _gruppe(self, token: str) -> dict | None:
            conn = web_daten.oeffne_lesend(db_pfad)
            try:
                return web_daten.gruppe_nach_token(conn, token)
            finally:
                conn.close()

    # Nicht ``schluessel = schluessel`` im Klassenkoerper: eine Zuweisung
    # macht den Namen innerhalb des GANZEN Klassenkoerpers lokal, auch auf
    # der rechten Seite derselben Zeile (``LOAD_NAME`` sieht die Fabrik-
    # variable dann nicht mehr) -- gemessen als ``NameError`` beim Bauen der
    # Klasse. Deshalb die Attribute nachtraeglich setzen, nach der Klasse.
    Handler.schluessel = schluessel
    Handler.praefix = praefix
    return Handler


def lies_bind(wert: str) -> tuple[str, int]:
    """Zerlegt ``IT_WEB_BIND`` in Adresse und Port.

    ``0.0.0.0`` wird abgelehnt: die Gruppenseiten haben kein Login, und der
    Server gehoert ins Tailnet (im Betrieb ``100.75.24.33:8010``), nicht auf
    jede Netzwerkkarte. Ein Tippfehler in einer Env-Datei soll die Interviews
    nicht ins offene Netz stellen."""
    adresse, trenner, port = wert.rpartition(":")
    if not trenner or not port.isdigit():
        raise RuntimeError(f"IT_WEB_BIND muss 'adresse:port' sein, ist: {wert!r}")
    adresse = adresse.strip("[]")
    if adresse in ("0.0.0.0", "::", ""):
        raise RuntimeError(
            "IT_WEB_BIND darf nicht auf allen Adressen lauschen "
            f"(erhalten: {wert!r}) -- die Gruppenseiten haben kein Login. "
            "Tailnet-Adresse oder 127.0.0.1 eintragen."
        )
    return adresse, int(port)


def baue_server(
    db_pfad: str,
    bind: str = VORGABE_BIND,
    praefix: str = VORGABE_PRAEFIX,
    schluessel: bytes | None = None,
):
    """Baut den Server, ohne ihn zu starten (Tests binden auf Port 0)."""
    adresse, port = lies_bind(bind)
    return ThreadingHTTPServer(
        (adresse, port), mache_handler(db_pfad, praefix, schluessel)
    )


def main() -> None:
    db_pfad = os.environ.get("IT_DB")
    if not db_pfad:
        print("Fehlende Umgebungsvariable: IT_DB", file=sys.stderr)
        sys.exit(1)
    bind = os.environ.get("IT_WEB_BIND", VORGABE_BIND)
    praefix = os.environ.get("IT_WEB_PREFIX", VORGABE_PRAEFIX)
    server = baue_server(db_pfad, bind, praefix)
    print(
        f"interview-theater-web hoert auf http://{bind}{praefix or '/'} "
        f"(Datenbank {db_pfad}, read-only)",
        flush=True,
    )
    # Abschlussreview I5: Uploads landen unter IT_AUDIO, und der Web-Bot
    # verweigert jeden Pfad ausserhalb SEINES IT_AUDIO. Steht hier ein anderes
    # Verzeichnis als in betrieb/<gruppe>.env, ist das die Ursache.
    from pathlib import Path

    from interview_theater import web_chat

    print(
        f"interview-theater-web IT_AUDIO={Path(web_chat._audio_verz()).resolve()}",
        flush=True,
    )
    server.serve_forever()


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
# ``__spec__.name`` statt ``__name__``: der Dienst startet mit
# ``python -m interview_theater.web``, dann heisst das Modul ``__main__`` --
# und unter diesem Namen faende die Texttabelle nichts (``["web"]``), die
# Seiten blieben in Padua still deutsch.
T = sprache.Texte(__spec__.name if __spec__ else __name__)


if __name__ == "__main__":
    # Damit ``sprache.text`` das Modul unter seinem Paketnamen findet.
    sys.modules.setdefault("interview_theater.web", sys.modules[__name__])
    main()
