"""Die vereinte Gruppenseite: drei Tabs, eine Phasenuebersicht, ein Strom
(30.09.2026, Karte W).

**Warum es dieses Modul gibt.** ``web.py`` traegt schon Dashboard,
Gruppenseite, Probenansicht und Leitfaden; ``web_chat.py`` (Karte A2) den
Chat. Was hier dazukommt -- die Klammer um alle drei, die Phasenleiste und
der SSE-Kanal -- gehoert in keins von beiden, und beide sind Hotspots
mehrerer Karten. Also ein eigenes Modul, das von ``web.py`` nur ueber
Routing-Zeilen erreicht wird.

**Der Strom ist die einzige Ausnahme von A2s "kein SSE".** Fuer alles andere
bleibt der Poll aus ``web_chat``; hier geht es um Teiltexte im
Zehntelsekunden-Takt, und dafuer ist ein Poll je Delta das falsche Werkzeug.
Faellt ``EventSource`` aus, zeigt der Poll die fertige Nachricht wie heute --
Streaming ist eine Zutat, keine Bedingung.

Kein Modellaufruf, kein ``repo``: read-only ueber ``web_daten``, wie der
Rest der Leseseite.
"""

import html
import json
import re
import time
import urllib.parse

from interview_theater import sprache, web, web_daten

#: Der Unterpfad unter ``/g/<token>/chat/``.
STROM_PFAD = "strom"

#: Unter welchem Pfad ein einzelnes Panel frisch geholt wird
#: (``/g/<token>/teil/<name>``).
TEIL_PFAD = "teil"

#: Derselbe Takt wie das sanfte Nachladen der Einzelseite.
NACHLADEN_MS = web.NEULADEN_SEKUNDEN * 1000

#: Welche Panels/Ausschnitte sich nachladen lassen. Der Chat NICHT: er hat
#: seinen eigenen Poll (Karte A2), und das Textbuch aendert sich nicht,
#: waehrend man es liest. ``roadmap`` kam in Fix-Runde 1 dazu (Review-Befund
#: 2): sie sitzt ausserhalb jedes Panels (immer sichtbar, unabhaengig vom
#: Tab) und blieb nach einem Phasenklick sonst bis zum vollen Neuladen auf
#: dem alten Stand.
_TEILE = ("stand", "roadmap")

#: Die drei Panels. Reihenfolge = Reihenfolge der Tableiste.
TABS = ("chat", "stand", "textbuch")

#: Ohne Fragment steht der Chat vorn: dort wird gearbeitet, die anderen
#: beiden sind Nachschlagewerke.
VORGABE_TAB = "chat"

#: Wie oft der Server nach neuem Text sieht -- derselbe Takt, in dem der Bot
#: schreibt (``strom.INTERVALL_S``). Schneller zu pollen faende nichts,
#: langsamer machte den Strom ruckelig.
STROM_TAKT_S = 0.15

#: Eine Kommentarzeile alle 15 s haelt die Verbindung durch Proxys am Leben,
#: die stille Verbindungen nach 30-60 s schliessen.
STROM_KEEPALIVE_S = 15.0

#: Nach fuenf Minuten wird die Verbindung geschlossen, auch wenn noch etwas
#: laeuft. ``ThreadingHTTPServer`` bindet je Verbindung einen Thread; der
#: Browser verbindet sich von selbst neu (das ist EventSource eingebaut), und
#: ein Reconnect auf eine fertige Zeile liefert sofort das Ende.
STROM_MAX_S = 300.0

#: Der Zustand einer Zeile, solange der Bot an ihr schreibt
#: (= ``repo.STROM_LAEUFT``; ``repo`` wird hier bewusst nicht importiert).
_LAEUFT = "laeuft"


def _kopf(handler) -> None:
    """Die Kopfzeilen eines Ereignisstroms.

    ``protocol_version`` ist ``HTTP/1.1`` (``web._Basishandler``), und dieser
    Antwort fehlt die ``Content-Length``: ohne ``Connection: close`` wartete
    der Browser auf einen weiteren Request auf derselben Verbindung.
    ``X-Accel-Buffering: no`` ist fuer nginx -- ohne das puffert der
    Reverse-Proxy den ganzen Strom zu einem Block (ANNAHME 6)."""
    handler.close_connection = True
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("X-Accel-Buffering", "no")
    handler.send_header("Connection", "close")
    handler.end_headers()


def _schicke(handler, daten: dict) -> bool:
    """Ein Ereignis. ``False``, wenn der Browser weg ist -- dann endet der
    Strom still (kein Vorfall: ein zugeklappter Tab ist kein Fehler)."""
    try:
        handler.wfile.write(
            f"data: {json.dumps(daten, ensure_ascii=False)}\n\n".encode("utf-8")
        )
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False
    return True


def _lebt(handler) -> bool:
    try:
        handler.wfile.write(b": ping\n\n")
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False
    return True


def _nach(query: str) -> int:
    try:
        werte = urllib.parse.parse_qs(query or "")
    except ValueError:
        return 0
    roh = (werte.get("nach") or ["0"])[0]
    return int(roh) if roh.isdigit() else 0


def _lies(db_pfad: str, funktion, *argumente):
    """Eine Abfrage auf einer frischen read-only Verbindung: eine ueber
    Minuten offen gehaltene Leseverbindung saehe wegen der WAL-Momentaufnahme
    den Fortschritt des Bots gar nicht."""
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        return funktion(conn, *argumente)
    finally:
        conn.close()


_REGEL = re.compile(r"([^{}]+)\{([^{}]*)\}")
_KOMMENTAR = re.compile(r"/\*.*?\*/", re.S)


def scope_css(css: str, scope: str) -> str:
    """Schraenkt jede Regel einer Panel-CSS auf das Panel ein.

    **Warum zur Laufzeit und nicht von Hand** (Plan-Kopf, Abweichung 4):
    gemessen am 30.09.2026 kollidieren ``_CSS_GRUPPE`` und ``_CSS_TEXTBUCH``
    in ``body`` und ``h1``, und ``.leiste`` heisst in ``_CSS_TEXTBUCH`` die
    Rollenleiste und in ``_CSS_CHAT`` die Knopfleiste. Die Konstanten
    umzuschreiben haette die drei Einzelseiten mit veraendert -- dieser Weg
    laesst sie Zeichen fuer Zeichen stehen.

    ``body`` wird zum Scope selbst (auch mit Anhang: ``body[data-figur] x``
    → ``<scope>[data-figur] x``), alles andere bekommt ihn als Vorfahren.
    ``@media``-Bloecke bleiben stehen, ihr Inhalt wird eingeschraenkt.

    ``_KOMMENTAR`` wird bewusst NICHT angewandt -- Kommentare bleiben im
    ausgelieferten CSS stehen (sie enthalten keine geschweiften Klammern und
    stoeren den Regex-Lauf nicht)."""
    def eine(treffer: re.Match) -> str:
        selektoren = treffer.group(1).strip()
        koerper = treffer.group(2)
        neu = ", ".join(_ein_selektor(s.strip(), scope)
                        for s in selektoren.split(",") if s.strip())
        return f"{neu} {{{koerper}}}"

    ergebnis = []
    rest = css
    while True:
        block = re.search(r"@media[^{]*\{", rest)
        if block is None:
            ergebnis.append(_REGEL.sub(eine, rest))
            break
        ergebnis.append(_REGEL.sub(eine, rest[:block.start()]))
        tiefe, i = 1, block.end()
        while i < len(rest) and tiefe:
            tiefe += {"{": 1, "}": -1}.get(rest[i], 0)
            i += 1
        ergebnis.append(block.group(0))
        ergebnis.append(_REGEL.sub(eine, rest[block.end():i - 1]))
        ergebnis.append("}")
        rest = rest[i:]
    return "".join(ergebnis)


def _ein_selektor(selektor: str, scope: str) -> str:
    if selektor == "body" or selektor.startswith("body[") or \
            selektor.startswith("body."):
        return scope + selektor[len("body"):]
    if selektor.startswith("body "):
        return f"{scope} {selektor[len('body '):]}"
    if selektor == "*":
        return f"{scope} *"
    return f"{scope} {selektor}"


_TEXT_TAB = {
    "chat": "Chat", "stand": "Arbeitsstand", "textbuch": "Textbuch",
    # UX-Knoepfe-Karte, Abschnitt 5 (02.10.2026): der Buehne-Tab aus
    # feat/brainstorm-vad wandert hier ein -- sichtbar nur in Phase 4
    # (siehe ``seite()``), deshalb steht er in TABS nie fest, nur bedingt.
    "buehne": "Bühne",
}

#: Nur Struktur, kaum Gestaltung -- die UX-Karte gestaltet im Grossen. Die
#: Phasenleiste bekam in Fix-Runde 1 (Aufgabe 16) trotzdem ein Mindestmass:
#: ohne jedes CSS blieb sie beim Browser-Vorgabestil haengen (nummerierte
#: Liste, Aufzaehlungspunkte, ~20px hohe Knoepfe als Tapflaeche, keine
#: Hervorhebung der aktiven Phase) und spannte auf dem Laptop ueber die volle
#: Breite, waehrend die Panels (ueber ``_CSS_GRUPPE``/``_CSS_TEXTBUCH``) auf
#: 44rem zentriert sind -- derselbe Wert hier, aus demselben Grund.
_CSS_VEREINT = """
.tabs { position: sticky; top: 0; z-index: 5; display: flex; gap: .3rem;
        padding: .3rem 0; background: inherit; }
.tabs button { flex: 1; font: inherit; min-height: 2.8rem; border-radius: .6rem;
               border: 1px solid #c9c4b8; background: #fff; }
.tabs button[aria-selected="true"] { font-weight: 600; border-width: 2px; }
.panel[hidden] { display: none; }
.blase.vorlaeufig { opacity: .85; white-space: pre-wrap; }
.blase.vorlaeufig::after { content: '▍'; animation: blinken 1s steps(2) infinite; }
.blase.vorlaeufig.fertig::after { content: none; }
@keyframes blinken { 50% { opacity: 0; } }
@media (prefers-reduced-motion: reduce) {
  /* Der Text erscheint trotzdem stueckweise -- das ist Information, keine
     Animation. Nur der Cursor hoert auf zu blinken. */
  .blase.vorlaeufig::after { animation: none; }
}
/* Die Phasenleiste -- auf derselben Breite wie die Panels, damit der
   Uebergang zum Stand-Panel darunter nicht springt. */
.roadmap { max-width: 44rem; margin: 0 auto .6rem; }
.roadmap summary { cursor: pointer; padding: .6rem .3rem; min-height: 44px;
                   display: flex; align-items: center; font-weight: 600; }
/* Weder Nummern noch Punkte -- die Nummer steht schon im Knopftext
   ("N · Name"), ein zweites "1." davor waere eine doppelte Wahrheit. */
.roadmap ol.phasen, .roadmap ul.aufgaben { list-style: none; margin: 0; padding: 0; }
.roadmap li.phase { margin: .5rem 0; padding: .3rem .4rem; border-radius: .5rem; }
/* Die aktive Phase sichtbar markiert -- sonst sieht die Liste nach sieben
   gleichen Zeilen aus, und "wo stehen wir" ist genau die Frage der Karte. */
.roadmap li.phase.aktiv { background: #eef3ea; border: 1px solid #b9cdae; }
/* Knopf (klickbare Gruppe) und Span (Telegram-Gruppe, AGENTS.md
   "Abschlussreview I3") sehen gleich aus -- nur eines davon ist ein Knopf. */
.roadmap .phase-knopf, .roadmap .phase-name {
  display: flex; align-items: center; width: 100%; min-height: 44px;
  box-sizing: border-box; font: inherit; font-weight: 600; text-align: left;
  padding: .4rem .6rem; border-radius: .4rem;
}
.roadmap .phase-knopf { border: 1px solid #c9c4b8; background: #fff; cursor: pointer; }
.roadmap .phase-knopf[data-sicher="1"] { background: #fff3cf; border-color: #d8a93b; }
.roadmap .phase-name { border: none; background: transparent; padding-left: .2rem; }
/* UX-Knoepfe Abschnitt 4: nach vorn mit fehlender Voraussetzung steht neben
   dem (bewaffneten) Phasenknopf ein zweiter, kleiner Knopf fuer "Nein" --
   verborgen, solange keine Rueckfrage offen ist. */
.roadmap .phase-kopfzeile { display: flex; align-items: stretch; gap: .3rem; }
.roadmap .phase-kopfzeile .phase-knopf { flex: 1 1 auto; }
.roadmap .phase-abbrechen {
  flex: 0 0 auto; min-height: 44px; min-width: 44px; font: inherit;
  border: 1px solid #c9c4b8; border-radius: .4rem; background: #fff; cursor: pointer;
}
/* Eine Aufgabenzeile loest einen Klick aus (Sprung zu Tab + Feld) --
   sie soll auch danach aussehen. */
.roadmap li.aufgabe { display: flex; align-items: center; gap: .4rem;
                      min-height: 2.4rem; padding: .15rem .4rem .15rem 1.1rem;
                      cursor: pointer; border-radius: .3rem; }
.roadmap li.aufgabe:hover { background: #f1efe7; }
"""

#: Hoechstens ein Verbindungsaufbau zum Strom je drei Sekunden -- derselbe
#: Abstand, den EventSource von sich aus nimmt, aber nur, solange es einen
#: Anlass gibt (Tippanzeige, neue Blase, laufende Zeile).
STROM_OEFFNEN_MIN_MS = 3000

#: Der Rueckfall-Takt: einmal je halbe Minute wird nachgesehen, ob etwas
#: laeuft, auch ohne Anlass (ein Lauf, der ohne Tippanzeige beginnt).
#: Ein solcher Blick kostet eine Anfrage, die sofort endet.
STROM_NACHSEHEN_MS = 30000

#: Wie lange eine fertige Blase hoechstens auf ihre Nachricht wartet. Kommt
#: sie nicht (geloescht, Poll haengt), faellt die Blase trotzdem weg -- die
#: Wahrheit ist der Poll, nicht der Strom.
STROM_WARTEN_MAX_MS = 60000

_STROM_JS = """
(function () {
  // Der laufende Text (Karte W). EventSource statt Poll: es geht um
  // Teiltexte im Zehntelsekunden-Takt, und dafuer waere ein Poll je Delta
  // das falsche Werkzeug. Faellt EventSource aus (altes Geraet, puffernder
  // Proxy), passiert hier gar nichts -- der Nachrichten-Poll aus Karte A2
  // liefert die fertige Antwort wie bisher.
  if (!window.EventSource) { return; }
  var verlauf = document.getElementById('verlauf');
  if (!verlauf) { return; }
  var BASIS = '__BASIS__';
  var OEFFNEN_MIN_MS = __OEFFNEN_MIN_MS__;
  var NACHSEHEN_MS = __NACHSEHEN_MS__;
  var WARTEN_MAX_MS = __WARTEN_MAX_MS__;

  // Je Stromzeile EINE Blase: pro Gruppe koennen mehrere Zeilen zugleich
  // laufen (ein Gespraechszug neben einem Szenenlauf). Schluessel ist die
  // id der Zeile (daten.id), nie eine globale Variable.
  var blasen = {};     // strom-id -> {el, wartetAuf, frist}
  var laufend = {};    // strom-id -> true, solange der Server 'laeuft' meldet
  var erledigt = {};   // strom-id -> true: ihr Ende ist schon verarbeitet
  var hoechste = 0;    // die hoechste je gesehene strom-id
  var quelle = null;
  var zuletzt = 0;     // Zeitpunkt des letzten Verbindungsaufbaus
  var geplant = null;

  var weg = function (id) {
    var b = blasen[id];
    if (!b) { return; }
    if (b.frist) { clearTimeout(b.frist); }
    if (b.el.parentNode) { b.el.parentNode.removeChild(b.el); }
    delete blasen[id];
  };
  var untenDran = function () {
    // Nur mitscrollen, wenn der Chat vorn ist und man schon unten war --
    // sonst zoege der Strom das Arbeitsstand-Panel mit oder risse eine
    // Leserin aus dem Verlauf weiter oben.
    if (verlauf.offsetParent === null) { return false; }
    return window.innerHeight + window.scrollY >= document.body.scrollHeight - 120;
  };
  var zeige = function (id, text) {
    var unten = untenDran();
    var b = blasen[id];
    if (!b) {
      var leer = verlauf.querySelector('p.leer');
      if (leer && leer.parentNode) { leer.parentNode.removeChild(leer); }
      var el = document.createElement('div');
      el.className = 'blase bot text vorlaeufig';
      el.dataset.strom = id;
      verlauf.appendChild(el);
      b = blasen[id] = { el: el, wartetAuf: null, frist: null };
    }
    // textContent, nicht das HTML-Feld: der Teiltext ist roher Modelltext,
    // und gefiltert wird serverseitig (web_chat.sichere_html) -- erst die
    // FERTIGE Nachricht geht durch den Filter.
    b.el.textContent = text;
    if (unten) { window.scrollTo(0, document.body.scrollHeight); }
  };
  // Steht die Nachricht, auf die eine fertige Blase wartet, im Verlauf, faellt
  // die Blase weg -- vorher nicht, sonst blitzt eine Luecke auf.
  var pruefe = function () {
    Object.keys(blasen).forEach(function (id) {
      var ziel = blasen[id].wartetAuf;
      if (ziel && verlauf.querySelector('.blase[data-id="' + ziel + '"]')) { weg(id); }
    });
  };

  var ereignis = function (ev) {
    var daten;
    try { daten = JSON.parse(ev.data); } catch (e) { return; }
    if (!daten || typeof daten.id !== 'number') { return; }
    if (daten.id > hoechste) { hoechste = daten.id; }
    // ``nach=`` liefert fertige Zeilen unter Umstaenden erneut -- ein
    // zweites Ende legt keine Blase mehr an.
    if (erledigt[daten.id]) { return; }
    if (daten.zustand === 'laeuft') {
      laufend[daten.id] = true;
      // Eine leere Blase zeigt nichts, was die Tippanzeige nicht schon sagt.
      if (daten.text) { zeige(daten.id, daten.text); }
      return;
    }
    erledigt[daten.id] = true;
    delete laufend[daten.id];
    if (daten.zustand === 'fertig' && daten.post_id && blasen[daten.id]) {
      // Die Blase bleibt stehen, bis der Poll die richtige Nachricht gebracht
      // hat (post_id = data-id ihrer Blase).
      if (daten.text) { zeige(daten.id, daten.text); }
      var b = blasen[daten.id];
      b.wartetAuf = daten.post_id;
      b.el.classList.add('fertig');
      var id = daten.id;
      b.frist = setTimeout(function () { weg(id); }, WARTEN_MAX_MS);
      pruefe();
      return;
    }
    // 'abgebrochen' (oder fertig ohne Nachricht): ersatzlos weg, kein halber
    // Text bleibt stehen. Eine Zeile, die nie eine Blase hatte, bekommt
    // auch jetzt keine -- ihre Nachricht bringt der Poll.
    weg(daten.id);
  };

  var schliesse = function () {
    if (quelle) { quelle.close(); quelle = null; }
  };
  var oeffne = function () {
    if (quelle) { return; }
    var warte = zuletzt + OEFFNEN_MIN_MS - Date.now();
    if (warte > 0) {
      if (!geplant) {
        geplant = setTimeout(function () { geplant = null; oeffne(); }, warte);
      }
      return;
    }
    zuletzt = Date.now();
    // Ab der aeltesten Zeile, die hier noch laeuft -- sonst erfuehre die
    // Ansicht das Ende einer Zeile nie, die waehrend einer Luecke endete.
    // Sonst ab der naechsten unbekannten: Altes kommt nicht noch einmal.
    var offen = Object.keys(laufend).map(Number);
    var nach = offen.length ? Math.min.apply(null, offen)
                            : (hoechste ? hoechste + 1 : 0);
    var bekam = false;
    quelle = new EventSource(BASIS + 'chat/__STROM__' + (nach ? '?nach=' + nach : ''));
    quelle.onmessage = function (ev) { bekam = true; ereignis(ev); };
    quelle.onerror = function () {
      // Der Server schliesst den Strom, sobald nichts mehr laeuft (und
      // spaetestens nach fuenf Minuten). EventSource verbaende sich dann von
      // selbst alle ~3 s neu -- fuer immer. Also zu, und nur dann neu, wenn
      // hier noch eine Zeile laeuft (Netzluecke, Fuenf-Minuten-Grenze).
      schliesse();
      if (!bekam) {
        // Eine frische Verbindung schickt jede Zeile ab ``nach`` mindestens
        // einmal. Kam nichts, gibt es die Zeilen nicht mehr (oder das Netz
        // ist weg): nicht weiter darauf warten -- die fertige Nachricht
        // bringt der Poll, und ohne diese Bremse liefe hier ein Neuaufbau
        // alle drei Sekunden ohne Ende.
        Object.keys(laufend).forEach(function (id) { weg(id); });
        laufend = {};
      }
      if (Object.keys(laufend).length) { oeffne(); }
    };
  };

  // Wann der Strom (wieder) aufgeht: der A2-Poll ist der Anlass. Er haengt
  // neue Blasen an und schreibt die Tippanzeige -- beides sieht ein
  // MutationObserver, ohne dass ``web_chat`` etwas davon wissen muss.
  // Die eigene, vorlaeufige Blase zaehlt dabei nicht.
  new MutationObserver(function (aenderungen) {
    pruefe();
    var neu = aenderungen.some(function (a) {
      return Array.prototype.some.call(a.addedNodes, function (n) {
        return n.nodeType === 1 && !n.classList.contains('vorlaeufig');
      });
    });
    if (neu) { oeffne(); }
  }).observe(verlauf, { childList: true });
  var tippt = document.getElementById('tippt');
  if (tippt) {
    new MutationObserver(function () {
      if (tippt.textContent) { oeffne(); }
    }).observe(tippt, { childList: true, characterData: true, subtree: true });
  }
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) { oeffne(); }
  });
  setInterval(function () { if (!document.hidden) { oeffne(); } }, NACHSEHEN_MS);
  oeffne();
})();
"""


def _strom_js(basis: str) -> str:
    """``_STROM_JS`` mit Basis, Pfad und Takten -- dieselbe
    Platzhalter-Bauart wie ``_VEREINT_JS``."""
    return (
        _STROM_JS.replace("__BASIS__", basis)
        .replace("__STROM__", STROM_PFAD)
        .replace("__OEFFNEN_MIN_MS__", str(STROM_OEFFNEN_MIN_MS))
        .replace("__NACHSEHEN_MS__", str(STROM_NACHSEHEN_MS))
        .replace("__WARTEN_MAX_MS__", str(STROM_WARTEN_MAX_MS))
    )


def _js_text(text: str) -> str:
    """Ein Nutzertext als JS-Ausdruck, nicht als roher Text fuer ein
    Platzhalter-Literal (Fix-Runde Abschluss, Befund 1): ``json.dumps`` legt
    die eigenen Anfuehrungszeichen und die Maskierung mit an, ``</`` wird
    zusaetzlich entschaerft, damit kein Text ein ``<script>`` beendet --
    derselbe Weg wie ``web_chat._js()`` (``__TEXTE__``). Ein Platzhalter, der
    so eingesetzt wird, steht im Skript **ohne** umschliessende
    Anfuehrungszeichen (``__X__.irgendwas``, nicht ``'__X__'``)."""
    return json.dumps(text, ensure_ascii=True).replace("</", "<\\/")

_VEREINT_JS = """
(function () {
  var TABS = __TABS__;
  var VORGABE = '__VORGABE__';
  // Die Basis aller Endpunkte dieser Seite: sie liegt unter /g/<token>, die
  // Endpunkte eine Ebene tiefer. Jedes IIFE deklariert sie selbst -- sie
  // teilen keinen Gueltigkeitsbereich.
  var BASIS = '__BASIS__';
  // Die Basis des Nachlade-Endpunkts: /g/<token>/teil/.
  var BASIS_TEIL = '__BASIS_TEIL__';
  // Der Tab steht als BLOSSES Wort im Fragment (#chat, #stand, #textbuch) --
  // damit ein geteilter Rollenlink dieselbe Form hat wie auf der
  // Probenansicht: #textbuch&figur=Leyla.
  var lies = function () {
    var teile = location.hash.replace(/^#/, '').split('&');
    for (var i = 0; i < teile.length; i++) {
      if (TABS.indexOf(teile[i]) >= 0) { return teile[i]; }
    }
    return VORGABE;
  };
  var zeige = function (name) {
    TABS.forEach(function (tab) {
      var panel = document.getElementById('tab-' + tab);
      if (panel) { panel.hidden = tab !== name; }
      var knopf = document.querySelector('.tabs button[data-tab="' + tab + '"]');
      if (knopf) { knopf.setAttribute('aria-selected', tab === name ? 'true' : 'false'); }
    });
    document.body.dataset.tab = name;
  };
  var setze = function (name) {
    var teile = location.hash.replace(/^#/, '').split('&').filter(function (t) {
      return t && TABS.indexOf(t) < 0;
    });
    // Ueber location.hash, damit die Zurueck-Taste des Handys den vorigen
    // Tab wiederherstellt -- und damit ein kopierter Link der ist, den man
    // gerade sieht. Umgeschaltet wird NUR ueber hidden: ein Seitenwechsel
    // riesse Aufnahme, halb getippte Nachricht und laufenden Strom mit.
    location.hash = '#' + [name].concat(teile).join('&');
  };
  // Fix-Runde 1, Review-Befund 1: ein 403 heisst fast immer "Nonce
  // abgelaufen" -- einmal auffrischen (ueber den leichten Stand-Ausschnitt,
  // kein kompletter Chat-Poll noetig), dann genau EIN zweiter Versuch.
  // Derselbe Grundsatz wie ``web_chat.postJson``, nur ohne dessen Scope.
  function friskeNonce() {
    // Ueber DOMParser gelesen, nicht per Textsuche nach dem Attribut: eine
    // Regex mit dem woertlichen Attributnamen stuende als Text im
    // ausgelieferten Skript und waere damit ein ZWEITES "id=nonce" auf der
    // Seite (Review der Fix-Runde, Gegenprobe zu
    // ``test_nur_eine_nonce_id_in_der_vereinten_seite``).
    return fetch(BASIS_TEIL + 'stand' + location.search, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (text) {
        if (!text) { return null; }
        var quelle = new DOMParser().parseFromString(text, 'text/html')
          .getElementById('nonce');
        if (!quelle) { return null; }
        var feld = document.getElementById('nonce');
        if (feld) { feld.value = quelle.value; }
        return quelle.value;
      })
      .catch(function () { return null; });
  }
  function sendePhase(phase, zweiter) {
    return fetch(BASIS + 'chat/phase', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nonce: (document.getElementById('nonce') || {}).value || '',
        nummer: parseInt(phase.dataset.phase, 10),
        bestaetigt: 1
      })
    }).then(function (r) {
      if (r.status === 403 && !zweiter) {
        return friskeNonce().then(function () { return sendePhase(phase, true); });
      }
      return r;
    });
  }
  var fehlerTakt = null;
  function zeigeFehler(satz) {
    var feld = document.getElementById('fehler');
    if (!feld) { return; }
    feld.textContent = satz || __FEHLER_NETZ__;
    feld.hidden = false;
    if (fehlerTakt) { clearTimeout(fehlerTakt); }
    fehlerTakt = setTimeout(function () { feld.hidden = true; feld.textContent = ''; }, 8000);
  }
  // Ein neu "bewaffneter" Knopf (zweiter Klick wechselt die Phase)
  // entwaffnet jeden anderen -- zwei offene Rueckfragen waeren nicht mehr
  // eindeutig zuzuordnen (Fix-Runde 1, Review-Befund 3).
  function entwaffneAlle(ausser) {
    document.querySelectorAll('.phase-knopf[data-sicher="1"]').forEach(function (b) {
      if (b === ausser) { return; }
      b.removeAttribute('data-sicher');
      if (b.dataset.beschriftung) { b.textContent = b.dataset.beschriftung; }
      var abbrechen = document.querySelector(
        '.phase-abbrechen[data-phase="' + b.dataset.phase + '"]');
      if (abbrechen) { abbrechen.hidden = true; }
    });
  }
  // UX-Knoepfe Abschnitt 4 (02.10.2026): die Rueckfrage steht nur noch,
  // wenn ``data-bereit="0"`` ist -- und nennt dann, was fehlt, statt
  // generisch "Wirklich zu X?" zu fragen. Ein zweiter Klick auf denselben
  // Knopf ist das Ja, der kleine ``.phase-abbrechen`` daneben das Nein.
  function bewaffne(phase) {
    phase.setAttribute('data-sicher', '1');
    phase.dataset.beschriftung = phase.textContent;
    phase.textContent = __FEHLT__.replace('{was}', phase.dataset.fehlt);
    var abbrechen = document.querySelector(
      '.phase-abbrechen[data-phase="' + phase.dataset.phase + '"]');
    if (abbrechen) { abbrechen.hidden = false; }
  }
  function springe(phase) {
    phase.disabled = true;
    sendePhase(phase).then(function (r) {
      phase.disabled = false;
      // Entwaffnen und die Beschriftung zuruecksetzen -- Erfolg, Fehler
      // und Netzausfall gleich (Fix-Runde 1, Review-Befund 3): ein
      // Knopf, der nach einem Fehlschlag auf der Rueckfrage stehen bleibt,
      // laedt zum blinden zweiten Klick ein. Im freien Fall (zurueck, oder
      // nach vorn mit erfuellter Voraussetzung) war der Knopf nie
      // bewaffnet -- dann ist hier nichts zurueckzusetzen.
      phase.removeAttribute('data-sicher');
      if (phase.dataset.beschriftung) { phase.textContent = phase.dataset.beschriftung; }
      var abbrechen = document.querySelector(
        '.phase-abbrechen[data-phase="' + phase.dataset.phase + '"]');
      if (abbrechen) { abbrechen.hidden = true; }
      if (r && r.ok) {
        // Ein sofortiger Versuch -- er zeigt die neue Phase aber NICHT
        // zuverlaessig: der POST legt hier nur den Eingang ab, der Bot
        // verarbeitet ihn erst danach (eigener Prozess, eigener Takt).
        // Massgeblich bleibt der naechste periodische Takt unten
        // (hoechstens __NACHLADEN_MS__ ms), der dieselbe Funktion ruft.
        ladeRoadmap();
        setze('chat');   // die Eintrittsnachricht kommt im Chat an
        return;
      }
      // Fehlschlag: KEIN Tab-Wechsel, und der Server-Satz steht im
      // Fehlerfeld (Review-Befund 1) -- derselbe Weg wie beim Senden
      // einer Chatnachricht (``web_chat.fehlerAus``), nur ohne dessen
      // Scope.
      if (r) {
        r.text().then(function (satz) { zeigeFehler((satz || '').trim()); },
                     function () { zeigeFehler(''); });
      } else {
        zeigeFehler('');
      }
    }).catch(function () {
      phase.disabled = false;
      phase.removeAttribute('data-sicher');
      if (phase.dataset.beschriftung) { phase.textContent = phase.dataset.beschriftung; }
      var abbrechen = document.querySelector(
        '.phase-abbrechen[data-phase="' + phase.dataset.phase + '"]');
      if (abbrechen) { abbrechen.hidden = true; }
      zeigeFehler('');
    });
  }
  document.addEventListener('click', function (ev) {
    var phase = ev.target.closest ? ev.target.closest('.phase-knopf') : null;
    if (phase) {
      if (phase.getAttribute('data-sicher') === '1') {
        // Zweiter Klick auf die Rueckfrage: Ja.
        springe(phase);
        return;
      }
      var aktiv = document.querySelector('.phase.aktiv .phase-knopf');
      var jetzige = aktiv ? parseInt(aktiv.dataset.phase, 10) : NaN;
      var ziel = parseInt(phase.dataset.phase, 10);
      var bereit = phase.dataset.bereit !== '0';
      entwaffneAlle(null);
      // Zurueck ist immer frei, nach vorn mit erfuellter Voraussetzung
      // ebenso -- ein Klick IST die Entscheidung der Gruppe (UX-Knoepfe
      // Abschnitt 4): kein Sofortsprung nur fuer eine fehlende
      // Voraussetzung nach vorn, dort fragt ``bewaffne`` konkret nach.
      if (bereit || (!isNaN(jetzige) && ziel <= jetzige)) {
        springe(phase);
      } else {
        bewaffne(phase);
      }
      return;
    }
    var abbrechen = ev.target.closest ? ev.target.closest('.phase-abbrechen') : null;
    if (abbrechen) {
      // Nein: die Rueckfrage wieder einklappen, ohne zu senden.
      entwaffneAlle(null);
      return;
    }
    var knopf = ev.target.closest ? ev.target.closest('.tabs button') : null;
    if (knopf) { setze(knopf.dataset.tab); return; }
    // Ein Klick auf eine Aufgabe der Roadmap springt zu ihrer Stelle --
    // Tab wechseln und, wo es ein Feld gibt, dorthin scrollen. Er setzt
    // KEINE Phase (AGENTS.md: Datenstand ist nicht Absicht).
    var ziel = ev.target.closest ? ev.target.closest('[data-ziel-tab]') : null;
    if (!ziel) { return; }
    setze(ziel.dataset.zielTab);
    var feld = ziel.dataset.zielFeld;
    if (!feld) { return; }
    var stelle = document.querySelector('[data-feld="' + feld + '"]');
    if (stelle && stelle.scrollIntoView) { stelle.scrollIntoView({block: 'center'}); }
  });
  window.addEventListener('hashchange', function () { zeige(lies()); });
  // Nachgeladen wird NUR das Stand-Panel, NUR wenn es vorn ist, und nur mit
  // denselben zwei Sperren wie bisher: Fokus in einem Feld oder eine
  // ungespeicherte Aenderung halten es an (Brief 05.09. abends). Der <body>
  // wird nie getauscht -- daran haengen Recorder, Eingabefeld und Strom.
  var wirdBearbeitet = function () {
    var aktiv = document.activeElement;
    if (aktiv && aktiv.closest && aktiv.closest('.feld')) { return true; }
    return !!document.querySelector('.feld[data-schmutzig="1"]');
  };
  var laeuft = false;
  // Browser-serialisiert vs. Browser-serialisiert: ``panel.innerHTML`` legt
  // der Browser beim Setzen in seiner eigenen Form ab (Attributreihenfolge,
  // Anfuehrungszeichen, ...); der roh vom Server geholte Text ist das nie.
  // Ein Vergleich roh-gegen-DOM faende deshalb NIE Gleichheit, und der
  // Austausch liefe auf jedem Takt -- wie ``web._SCROLL_JS`` (web.py) wird
  // darum per ``DOMParser`` auf dieselbe Form normalisiert, bevor verglichen
  // wird, und der Vergleichswert (``panelLetzter``) kommt beim ersten Blick
  // aus derselben, schon browser-serialisierten Quelle: ``panel.innerHTML``.
  var panelLetzter = null;
  var offene = function (panel) {
    var s = {};
    panel.querySelectorAll('details[open] > summary').forEach(function (el) {
      s[el.textContent.trim()] = true;
    });
    return s;
  };
  // Die Roadmap sitzt AUSSERHALB jedes Panels (immer sichtbar, unabhaengig
  // vom Tab) -- deshalb ein eigener Ausschnitt statt einer Abhaengigkeit
  // vom Stand-Panel-Gate (Fix-Runde 1, Review-Befund 2). Sie teilt sich den
  // Takt mit dem Stand-Panel (derselbe ``setInterval`` unten), nicht dessen
  // Sichtbarkeits- und Bearbeitet-Sperren -- die Roadmap hat keine
  // Eingabefelder.
  var roadmapLaeuft = false;
  // Wie ``panelLetzter``: beim ersten Blick aus der schon
  // browser-serialisierten Live-DOM gesetzt, NICHT erst aus der ersten
  // Antwort -- sonst waere die erste Antwort nie gleich (``null``) und
  // ``ladeRoadmap`` tauschte beim allerersten Takt immer, auch ohne
  // Aenderung (Fix-Runde 2, Review-Befund 1 Teil 2).
  var roadmapLetzter = null;
  function ladeRoadmap() {
    var aktuell = document.getElementById('roadmap');
    if (!aktuell) { return; }
    if (roadmapLetzter === null) { roadmapLetzter = aktuell.outerHTML; }
    if (roadmapLaeuft || document.hidden) { return; }
    // Steht ein Knopf gerade mitten im Request (disabled), wuerde ein
    // Austausch jetzt seine laufende Antwort auf einen verwaisten Knoten
    // treffen lassen -- harmlos (die Antwort wirkt dann einfach nicht mehr
    // sichtbar), aber unnoetig: der naechste Takt reicht.
    if (aktuell.querySelector('.phase-knopf:disabled')) { return; }
    roadmapLaeuft = true;
    // Keine ``location.search`` hier -- die Roadmap kennt keine Fassungswahl,
    // anders als das Stand-Panel.
    fetch(BASIS_TEIL + 'roadmap', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (text) {
        if (!text) { return; }
        var doc = new DOMParser().parseFromString(text, 'text/html');
        var frisch = doc.body ? doc.body.firstElementChild : null;
        var neu = frisch ? frisch.outerHTML : null;
        if (!neu || neu === roadmapLetzter) { return; }
        var ziel = document.getElementById('roadmap');
        if (!ziel) { return; }
        // ``ziel`` IST das <details> -- anders als beim Stand-Panel gibt es
        // hier keine verschachtelten <details>, deren offener Zustand sich
        // per Summary-Text wiederfinden liesse (``offene()`` passt hier
        // nicht: sie sucht nur unter Nachkommen, nie am Element selbst).
        // Stattdessen direkt die eigene ``open``-Eigenschaft sichern und
        // zuruecksetzen (Fix-Runde 2, Review-Befund 1 Teil 1) -- sonst
        // klappt die aufgeklappte Liste bei jedem Takt lautlos wieder zu.
        var warOffen = ziel.open;
        // Ein gerade "bewaffneter" Knopf (zweiter Klick wechselt die Phase)
        // ueberlebt den Austausch -- sonst entwaffnet ein Nachladen
        // mitten in der Rueckfrage lautlos, und der naechste Klick trifft
        // ins Leere (Review-Befund 2/3 zusammen).
        var bewaffnet = ziel.querySelector('.phase-knopf[data-sicher="1"]');
        var bewaffneteNummer = bewaffnet ? bewaffnet.dataset.phase : null;
        ziel.outerHTML = neu;
        roadmapLetzter = neu;
        var neues = document.getElementById('roadmap');
        if (!neues) { return; }
        neues.open = warOffen;
        if (bewaffneteNummer) {
          var wiederKnopf = neues.querySelector(
            '.phase-knopf[data-phase="' + bewaffneteNummer + '"]');
          // Ueber ``bewaffne`` statt dieselben drei Zeilen zu wiederholen --
          // sie liest ``data-fehlt`` dabei frisch aus dem neu geladenen
          // Ausschnitt: hat sich die Luecke seit dem letzten Takt
          // geschlossen, aendert sich auch der Hinweistext.
          if (wiederKnopf) { bewaffne(wiederKnopf); }
        }
      })
      .catch(function () {})
      .finally(function () { roadmapLaeuft = false; });
  }
  setInterval(function () {
    // Im selben Takt wie das Stand-Panel (Review-Befund 2), aber ohne
    // dessen Gate: die Roadmap ist immer sichtbar, gleich welcher Tab vorn
    // ist.
    ladeRoadmap();
    var panel = document.getElementById('tab-stand');
    if (!panel) { return; }
    if (panelLetzter === null) { panelLetzter = panel.innerHTML; }
    if (panel.hidden || laeuft || document.hidden || wirdBearbeitet()) {
      return;
    }
    laeuft = true;
    // ``location.search`` reicht die gewaehlte Fassung weiter
    // (``?szene=<id>&fassung=<n>``, ``web.fassungswahl``) -- sonst spraenge
    // ein offen gelesener alter Text beim naechsten Takt auf den aktuellen
    // zurueck.
    fetch(BASIS_TEIL + 'stand' + location.search, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        if (!html) { return; }
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var neu = doc.body ? doc.body.innerHTML : null;
        if (!neu || neu === panelLetzter) { return; }
        var zustand = offene(panel);
        var y = window.scrollY;
        panel.innerHTML = neu;
        panelLetzter = neu;
        panel.querySelectorAll('details > summary').forEach(function (el) {
          if (zustand[el.textContent.trim()]) { el.parentElement.setAttribute('open', ''); }
        });
        window.scrollTo(0, y);
      })
      .catch(function () {})
      .finally(function () { laeuft = false; });
  }, __NACHLADEN_MS__);
  zeige(lies());
})();
"""


def _tabs_html(aktiv: str, tabs=TABS) -> str:
    knoepfe = "".join(
        f'<button type="button" role="tab" data-tab="{tab}" '
        f'aria-selected="{"true" if tab == aktiv else "false"}">'
        f"{T._TEXT_TAB[tab]}</button>"
        for tab in tabs
    )
    return f'<nav class="tabs" role="tablist">{knoepfe}</nav>'


_TEXT_PHASE_UNGUELTIG = "Diese Phase gibt es nicht."
_TEXT_PHASE_UNBESTAETIGT = "Bitte einmal bestätigen."
_TEXT_PHASE_WECHSELN = "Zu dieser Phase wechseln"
#: UX-Knoepfe Abschnitt 4 (02.10.2026): ersetzt die vorherige, generische
#: Rueckfrage "Wirklich zu {bezeichnung}?" vor JEDEM Klick. Zurueck ist jetzt
#: immer frei, nach vorn ebenso, solange die Materiallage es hergibt --
#: diese Zeile steht nur noch, wenn etwas Konkretes fehlt ("{was}" =
#: ``roadmap.fehlt``, ueber Komma, falls mehr als ein Punkt offen ist).
_TEXT_PHASE_FEHLT_HINWEIS = "{was} fehlt noch – trotzdem weiter?"
#: Der kleine Knopf neben der Rueckfrage -- das Nein zum Ja des zweiten
#: Klicks auf ``_TEXT_PHASE_FEHLT_HINWEIS``.
_TEXT_PHASE_ABBRECHEN = "Nein"
#: Fix-Runde 1, Review-Befund 1: der Netzfehler-Satz beim Phasenklick --
#: wortgleich mit ``web_chat._TEXT_FEHLER_NETZ``, aber als eigene Konstante,
#: weil die beiden JS-IIFEs keinen Gueltigkeitsbereich teilen und
#: ``web_vereint`` nicht in ``web_chat`` greift.
_TEXT_PHASE_FEHLER_NETZ = "Keine Verbindung — das ist nicht angekommen."
_ZEICHEN = {"erledigt": "✅", "offen": "⬜", "laeuft": "⏳"}
# Knapp (Test: ``test_die_leiste_steht_auf_der_seite_und_ist_knapp``): die
# Phasenzahl steht als Bruch da ("1/7"), nicht als "1 von 7" -- zugeklappt
# ist das die EINE Zeile, die die Karte vorsieht.
_TEXT_ROADMAP_KOPF = "Phase {nummer}/{gesamt} · {name} — {erledigt}/{gesamt_aufgaben}"


def phase_post(handler, db_pfad: str, token: str, chat_id: int,
               schluessel: bytes) -> None:
    """``POST /g/<token>/chat/phase`` -- ein Klick auf eine Phase.

    Der Webserver **setzt nichts**: er legt den Klick als gewoehnlichen
    Eingang ab (derselbe ``WEB_TYP_BEFEHL`` wie der Aufnahme-Umschalter aus
    Karte A2), und der Bot fuehrt ihn ueber ``befehle.wechsle_phase`` aus.
    Zwei Gruende: der Webserver hat kein ``klm``, und
    ``knoepfe.eintritt_in_phase`` stoesst Modellarbeit in Threads an.

    Reihenfolge der Pruefungen wie ueberall: Token (im Aufrufer), Nonce,
    Wert -- erst 403, dann 400. **Ohne ``bestaetigt`` passiert nichts**: ein
    Fehlgriff auf dem Telefon soll keine Phase kosten."""
    from interview_theater import phasen, repo, web_chat

    daten = web_chat._koerper_oder_400(handler, token, schluessel)
    if daten is None:
        return
    if not daten.get("bestaetigt"):
        handler._fehler(400, T._TEXT_PHASE_UNBESTAETIGT)
        return
    nummern = {n for n, _name, _satz in phasen.PHASEN}
    roh = daten.get("nummer")
    if not isinstance(roh, int) or isinstance(roh, bool) or roh not in nummern:
        handler._fehler(400, T._TEXT_PHASE_UNGUELTIG)
        return
    with web_chat.schreibend(db_pfad) as conn:
        message_id = repo.lege_web_post_an(
            conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_BEFEHL,
            text=f"/phaseklick {roh}",
        )
    web_chat._angenommen(handler, {"message_id": message_id})


def _leiste_html(roadmapdaten: list[dict], klickbar: bool = True) -> str:
    """Die Phasenuebersicht: zugeklappt eine Zeile, aufgeklappt die volle Liste.

    **Platzierung** (Kartentext: "an geeigneter Stelle anbringen"): ganz oben,
    ueber der Tableiste, und zugeklappt genau **eine** Zeile hoch. Auf einem
    Telefon (390×844) ist der Chat die Arbeitsflaeche -- eine dauerhaft
    aufgeklappte Liste mit sieben Phasen und fuenfzehn Aufgaben naehme ein
    Drittel des Bildschirms fuer etwas, das man dreimal am Tag braucht.
    ``<details>`` statt eines Schalters, damit es **ohne JavaScript**
    funktioniert -- dasselbe Element, das die Gruppenseite schon benutzt.

    Ein Klick auf eine **Phase** schaltet um (ueber den Chat-Weg, Aufgabe 13);
    ein Klick auf eine **Aufgabe** springt nur zu ihrer Stelle (Tab + Feld)
    und setzt nichts.

    **Zurueck ist immer frei, nach vorn nur mit Hinweis bei fehlender
    Voraussetzung** (UX-Knoepfe Abschnitt 4, 02.10.2026): das JS entscheidet
    anhand ``data-phase`` (Ziel gegen die aktive Phase) und ``data-bereit``,
    ob ein Klick sofort sendet oder erst die Frage "<data-fehlt> fehlt noch
    -- trotzdem weiter?" am selben Knopf zeigt (zweiter Klick = Ja, der
    kleine ``phase-abbrechen``-Knopf daneben = Nein). Das ersetzt die
    vorherige Rueckfrage "Wirklich zu X?" vor JEDEM Klick -- diese Karte
    ersetzt zugleich die Angebote "Weiter zu Phase N" im Chat
    (``knoepfe.biete_phase_proaktiv`` bleibt fuer Telegram, siehe dort).

    ``klickbar`` ist ``False`` fuer eine Gruppe ohne Web-Kanal (Telegram):
    dort ist jeder ``/chat/*``-Weg 404 (kein Bot, der ``web_post`` liest,
    AGENTS.md "Abschlussreview I3"), ein Knopf waere also toter Code auf der
    Seite. Die Uebersicht selbst -- Phase, Fortschritt, Sprungziele -- bleibt
    stehen, nur ohne Knopf und ohne ``data-phase``.

    **Kein eigenes Nonce-Feld** (Fix-Runde 1, Review-Befund 4: der fruehere
    Parameter ``nonce_wert`` brauchte niemand): das Stand-Panel traegt das
    einzige ``id="nonce"`` der Seite (geteilt mit dem Chat), und das haelt der
    Chat-Poll alle zwei bis zehn Sekunden frisch -- unabhaengig vom
    sichtbaren Panel, nur ``document.hidden`` verlangsamt ihn. Ein zweites,
    eigenes Nonce-Feld liefe dagegen nur beim Laden der Seite frisch und
    stuende nach einer Stunde (dem Nonce-Fenster) mit einem 403 da. Scheitert
    ein Klick trotzdem mit 403 (Chat-Poll noch nicht gelaufen), holt
    ``friskeNonce()`` im JS einmal ``teil/stand`` und liest den frischen Wert
    direkt aus der Antwort -- derselbe Fall wie bei ``web_chat.postJson``,
    nur ohne die ganze Chat-Antwort zu brauchen."""
    if not roadmapdaten:
        return ""
    aktiv = next((p for p in roadmapdaten if p["aktiv"]), roadmapdaten[0])
    kopf = T._TEXT_ROADMAP_KOPF.format(
        nummer=aktiv["nummer"], gesamt=len(roadmapdaten), name=aktiv["name"],
        erledigt=aktiv["erledigt"], gesamt_aufgaben=aktiv["gesamt"],
    )
    zeilen = []
    for phase in roadmapdaten:
        aufgaben = "".join(
            f'<li class="aufgabe {a["zustand"]}" '
            f'data-ziel-tab="{a["ziel"]["tab"]}"'
            + (f' data-ziel-feld="{html.escape(a["ziel"]["feld"], quote=True)}"'
               if a["ziel"].get("feld") else "")
            + f'>{_ZEICHEN[a["zustand"]]} {html.escape(a["text"])}</li>'
            for a in phase["aufgaben"]
        )
        if klickbar:
            # UX-Knoepfe Abschnitt 4: ``bereit``/``fehlt`` gehen roh als
            # data-Attribute mit -- das JS entscheidet daraus, ob ein Klick
            # sofort springt (zurueck, oder nach vorn mit erfuellter
            # Voraussetzung) oder erst den Hinweis zeigt. Fehlt das Feld
            # (eine Fixture ohne die neuen ``lage``-Schluessel), gilt
            # "bereit" -- derselbe Rueckfall wie ``roadmap.bereit`` selbst.
            fehlt_text = ", ".join(phase.get("fehlt") or ())
            phasenkopf = (
                f'<div class="phase-kopfzeile">'
                f'<button type="button" class="phase-knopf" '
                f'data-phase="{phase["nummer"]}" '
                f'data-bezeichnung="{html.escape(phase["bezeichnung"], quote=True)}" '
                f'data-bereit="{"0" if phase.get("bereit") is False else "1"}" '
                f'data-fehlt="{html.escape(fehlt_text, quote=True)}" '
                f'title="{html.escape(T._TEXT_PHASE_WECHSELN, quote=True)}">'
                f'{html.escape(phase["bezeichnung"])}</button>'
                f'<button type="button" class="phase-abbrechen" '
                f'data-phase="{phase["nummer"]}" hidden '
                f'aria-label="{html.escape(T._TEXT_PHASE_ABBRECHEN, quote=True)}">'
                f'✕</button>'
                f'</div>'
            )
        else:
            phasenkopf = (
                f'<span class="phase-name">{html.escape(phase["bezeichnung"])}</span>'
            )
        zeilen.append(
            f'<li class="phase{" aktiv" if phase["aktiv"] else ""}">'
            f'{phasenkopf}'
            f'<ul class="aufgaben">{aufgaben}</ul></li>'
        )
    return (
        f'<details class="roadmap" id="roadmap">'
        f'<summary>{html.escape(kopf)}</summary>'
        f'<ol class="phasen">{"".join(zeilen)}</ol>'
        f'</details>\n'
    )


def seite(daten, chatdaten, roadmapdaten, nonce_wert, token, praefix,
          segment_ms, fassungswahl=None, chat_vorhanden=True) -> str:
    """Die vereinte Gruppenseite: Chat, Arbeitsstand und Textbuch als drei
    Panels in EINEM Dokument.

    **Ohne das sanfte Nachladen** (``web._seite(..., nachladen=False)``): es
    tauscht ``document.body.innerHTML`` alle zehn Sekunden aus, und mitten in
    einer Aufnahme, einer halb getippten Nachricht oder einem laufenden Strom
    waere das ein Datenverlust. Nachgeladen wird gezielt: der Chat per Poll
    (A2), das Stand-Panel ueber ``/g/<token>/teil/stand`` (Aufgabe 12).

    ``chat_vorhanden`` ist ``False`` fuer eine Telegram-Gruppe (kein
    Web-Kanal, AGENTS.md "Abschlussreview I3"): das Chat-Panel samt seinem
    Tab und Skript (``eingabe``, ``interview``, ``ptt``, ``web_chat._js()``)
    faellt dann ganz weg -- ein POST oder Poll dorthin wuerde ohnehin 404
    liefern (``web_chat._gruppe_oder_404`` prueft denselben Web-Kanal), und
    was die Gruppe dort eintippen wuerde, ginge spurlos verloren. Start-Tab
    ist dann ``stand``; ein Fragment ``#chat`` faellt automatisch darauf
    zurueck, weil ``TABS`` im Skript ohne ``chat`` ankommt und ``lies()`` in
    ``_VEREINT_JS`` jedes unbekannte Wort auf ``VORGABE`` abbildet."""
    from interview_theater import web, web_chat

    titel = daten["titel"] or f"Gruppe {daten['chat_id']}"
    tabs = TABS if chat_vorhanden else tuple(t for t in TABS if t != "chat")
    # UX-Knoepfe-Karte, Abschnitt 5 (02.10.2026): der Buehne-Tab aus
    # feat/brainstorm-vad, jetzt als echter Tab statt des frueheren
    # verschachtelten "Chat · Buehne"-Umschalters im Stand-Panel. Sichtbar
    # NUR in Phase 4 -- ausserhalb davon steht der Knopf gar nicht in
    # ``tabs``, und ``lies()`` in ``_VEREINT_JS`` faellt fuer ein
    # mitgebrachtes ``#buehne`` (z. B. ein alter Link) automatisch auf
    # ``VORGABE`` zurueck, weil es dort nicht mehr in ``TABS`` steht --
    # derselbe Mechanismus wie beim fehlenden "chat"-Tab ohne Web-Kanal.
    phase4 = (daten.get("arbeitsstand") or {}).get("phase") == 4
    if phase4:
        tabs = tabs + ("buehne",)
    vorgabe = VORGABE_TAB if chat_vorhanden else "stand"
    panels = {
        "stand": web.gruppe_koerper(daten, nonce_wert, token, praefix, fassungswahl),
        "textbuch": web.textbuch_koerper(daten, token, praefix),
    }
    if phase4:
        panels["buehne"] = web._buehne_html(daten)
    if chat_vorhanden:
        # ``mit_nonce=False``: das Stand-Panel traegt sein ``id="nonce"``
        # schon (``_bearbeiten_html``), mit demselben Wert -- ein zweites
        # Element mit derselben id waere ungueltiges HTML.
        # ``mit_gruppenlink=False`` (Fix-Runde 1): der Link fuehrt sonst auf
        # die Seite, auf der er selbst steht (``/g/<token>`` -> ``<token>``).
        panels["chat"] = web_chat.chat_koerper(
            chatdaten, nonce_wert, token, segment_ms,
            basis=f"{token}/", mit_nonce=False, mit_gruppenlink=False,
        )
    koerper = [_leiste_html(roadmapdaten, klickbar=chat_vorhanden),
              _tabs_html(vorgabe, tabs)]
    for tab in tabs:
        # ``data-textbuch`` ist die Wurzel, an der ``_TEXTBUCH_JS`` seinen
        # Zustand ablegt: im gemeinsamen Dokument darf der Rollenfilter nicht
        # am ``<body>`` haengen, sonst faerbte er auch den Chat.
        zusatz = ' data-textbuch=""' if tab == "textbuch" else ""
        verborgen = "" if tab == vorgabe else " hidden"
        koerper.append(
            f'<section class="panel panel-{tab}" id="tab-{tab}" role="tabpanel"'
            f'{zusatz}{verborgen}>\n{panels[tab]}\n</section>'
        )
    css = (
        _CSS_VEREINT
        + scope_css(web._CSS_GRUPPE, ".panel-stand")
        + scope_css(web._CSS_TEXTBUCH + web._CSS_TEXTBUCH_FASSUNGEN, ".panel-textbuch")
    )
    if chat_vorhanden:
        css += scope_css(web_chat._CSS_CHAT, ".panel-chat")
    if phase4:
        css += scope_css(web._CSS_BUEHNE, ".panel-buehne")
    # web_chat._js() und nicht die rohe Konstante _CHAT_JS: sie traegt
    # unersetzte Platzhalter (__POLL_MS__ usw., siehe web_chat._js()-Docstring)
    # -- nur _js() liefert lauffaehiges Skript (Abweichung vom Plan-Kopf-
    # Beispiel, das die Konstante direkt anhaengt).
    skript = (
        _VEREINT_JS.replace("__TABS__", json.dumps(list(tabs)))
        .replace("__VORGABE__", vorgabe)
        .replace("__BASIS__", f"{token}/")
        .replace("__BASIS_TEIL__", f"{token}/{TEIL_PFAD}/")
        .replace("__NACHLADEN_MS__", str(NACHLADEN_MS))
        # Fix-Runde Abschluss, Befund 1: als JSON-Wert einsetzen, nicht als
        # roher Text in ein einfach gequotetes Literal -- die englische
        # Fassung traegt einen Apostroph ("didn't go through") und brach dort
        # das ganze <script> ab. Derselbe Weg wie ``web_chat._js()``
        # (``__TEXTE__``), ``</`` maskiert, damit kein Text das Skript-Tag
        # beendet.
        .replace("__FEHLT__", _js_text(T._TEXT_PHASE_FEHLT_HINWEIS))
        .replace("__FEHLER_NETZ__", _js_text(T._TEXT_PHASE_FEHLER_NETZ))
        + web._TEXTBUCH_JS
    )
    if chat_vorhanden:
        skript += web_chat._js()
        # Der Strom nur mit Chat: fuer eine Gruppe ohne Web-Kanal ist
        # ``/chat/*`` 404, ein EventSource liefe dort ins Leere.
        skript += _strom_js(f"{token}/")
    return web._seite(
        f"{titel} — interview-theater", css, "\n".join(koerper),
        bearbeitbar=True, nachladen=False, skript=skript,
    )


def _roadmap_html(db_pfad: str, token: str) -> str | None:
    """Die Phasenuebersicht frisch gerendert -- fuer ``teil/roadmap``
    (Fix-Runde 1, Review-Befund 2). ``None``, wenn es die Gruppe nicht gibt.

    ``klickbar`` haengt wie auf der ganzen Seite am Web-Kanal
    (``beantworte_seite``): eine Telegram-Gruppe bekommt auch beim
    Nachladen keine toten Knoepfe. Geprueft wird mit
    ``web_chat_id_nach_token`` -- der leichten Abfrage, die nur die
    chat_id zum Token mit ``kanal = 'web'`` holt -- und nicht mit
    ``web_chatzustand`` (Fix-Runde 2, Review-Befund 3): der baut den
    ganzen Chat-Poll (Verlauf, Aenderungen, Antworten) zusammen, den
    dieser Ausschnitt gar nicht braucht."""
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        daten = web_daten.gruppe_nach_token(conn, token)
        if daten is None:
            return None
        chat_vorhanden = web_daten.web_chat_id_nach_token(conn, token) is not None
        roadmapdaten = web_daten.roadmap(conn, daten["chat_id"])
    finally:
        conn.close()
    return _leiste_html(roadmapdaten, klickbar=chat_vorhanden)


def sende_teil(handler, db_pfad: str, token: str, name: str, praefix: str,
              schluessel: bytes, query: str) -> None:
    """``GET /g/<token>/teil/<stand|roadmap>`` -- nur der Rumpf eines
    Ausschnitts.

    Der Ersatz fuer das sanfte Nachladen der Einzelseite: dort tauscht
    ``web._SCROLL_JS`` den ganzen ``<body>``, hier nur dieser eine
    Ausschnitt. Alles andere -- Chat, Aufnahme, Strom, halb getipptes Feld --
    bleibt stehen.

    ``stand`` traegt den frischen Nonce mit, wie beim sanften Nachladen: er
    steht IM Rumpf (``web.nonce``), nicht daran. ``roadmap`` (Fix-Runde 1)
    hat keinen eigenen Nonce -- sie braucht keinen, siehe ``_leiste_html``."""
    if name not in _TEILE:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    if name == "roadmap":
        rumpf = _roadmap_html(db_pfad, token)
        if rumpf is None:
            handler._antworte(404, web.nicht_gefunden_html())
            return
        handler._antworte(200, rumpf)
        return
    daten = handler._gruppe(token)
    if daten is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    handler._antworte(200, web.gruppe_koerper(
        daten, web.nonce(schluessel, token), token, praefix,
        web.fassungswahl(query),
    ))


def beantworte_seite(handler, db_pfad: str, token: str, praefix: str,
                     schluessel: bytes, query: str) -> None:
    """``GET /g/<token>``: die vereinte Seite aus drei Panels.

    Ohne Web-Kanal (``chatdaten is None``) faellt das Chat-Panel ganz weg --
    die beiden anderen tragen die Seite weiter (Telegram-Gruppen haben
    keinen Bot, der ``web_post`` liest, siehe ``web_daten.web_chat_id_nach_token``)."""
    from interview_theater import web, web_chat

    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        daten = web_daten.gruppe_nach_token(conn, token)
        chatdaten = web_daten.web_chatzustand(conn, token)
        roadmapdaten = (
            web_daten.roadmap(conn, daten["chat_id"]) if daten else [])
    finally:
        conn.close()
    if daten is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return
    chat_vorhanden = chatdaten is not None
    if not chat_vorhanden:
        # Eine Gruppe ohne Web-Kanal hat keinen Chatzustand -- der Platzhalter
        # wird nur fuer die Signatur gebraucht, ``seite()`` baut daraus mit
        # ``chat_vorhanden=False`` kein Panel.
        chatdaten = {"titel": daten["titel"], "nachrichten": [], "letzte": 0,
                     "interviewmodus": False, "tippt": False, "antworten": {}}
    for nachricht in chatdaten["nachrichten"]:
        nachricht["html"] = web_chat.sichere_html(nachricht["text"])
    handler._antworte(200, seite(
        daten, chatdaten, roadmapdaten, web.nonce(schluessel, token), token,
        praefix, web_chat._segment_ms(), web.fassungswahl(query),
        chat_vorhanden=chat_vorhanden,
    ))


def sende_strom(handler, db_pfad: str, token: str, query: str) -> None:
    """``GET /g/<token>/chat/strom`` -- die Teiltexte der laufenden Aufrufe.

    Pro Gruppe koennen **mehrere** Zeilen zugleich laufen (ein Prosalauf und
    ein Gespraechszug, Befund aus Aufgabe 7). Deshalb liefert der Strom
    Ereignisse **je Zeile** -- jedes traegt seine ``id`` -- fuer alle Zeilen ab
    ``web_daten.web_stromanfang``, und er endet erst, wenn keine davon mehr
    laeuft (oder der Browser weg ist, oder nach ``STROM_MAX_S``). Eine Zeile,
    die waehrend der Verbindung beginnt, kommt mit.

    Ein Ereignis geht raus, wenn sich Text, Zustand oder ``post_id`` einer
    Zeile geaendert haben; das Ende einer Zeile kommt genau einmal."""
    from interview_theater import web

    chat_id = _lies(db_pfad, web_daten.web_chat_id_nach_token, token)
    if chat_id is None:
        handler._antworte(404, web.nicht_gefunden_html())
        return

    _kopf(handler)
    anfang = _lies(db_pfad, web_daten.web_stromanfang, chat_id, _nach(query))
    if anfang is None:
        return
    gesendet: dict[int, tuple] = {}
    letztes_lebenszeichen = time.monotonic()
    ende = time.monotonic() + STROM_MAX_S
    while time.monotonic() < ende:
        zeilen = _lies(db_pfad, web_daten.web_stromzeilen, chat_id, anfang)
        for zeile in zeilen:
            stand = (zeile["text"], zeile["zustand"], zeile["post_id"])
            if gesendet.get(zeile["id"]) == stand:
                continue
            if not _schicke(handler, zeile):
                return
            gesendet[zeile["id"]] = stand
            letztes_lebenszeichen = time.monotonic()
        if not any(zeile["zustand"] == _LAEUFT for zeile in zeilen):
            return
        if time.monotonic() - letztes_lebenszeichen >= STROM_KEEPALIVE_S:
            if not _lebt(handler):
                return
            letztes_lebenszeichen = time.monotonic()
        time.sleep(STROM_TAKT_S)


#: Die Nutzertexte in der Sprache des Profils (Karte A1). Nachgeschlagen wird
#: zur Aufrufzeit, nie beim Import: ein Web-Prozess bedient mehrere Gruppen.
T = sprache.Texte(__name__)
