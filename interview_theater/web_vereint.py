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

import json
import re
import time
import urllib.parse

from interview_theater import web, web_daten

#: Der Unterpfad unter ``/g/<token>/chat/``.
STROM_PFAD = "strom"

#: Unter welchem Pfad ein einzelnes Panel frisch geholt wird
#: (``/g/<token>/teil/<name>``).
TEIL_PFAD = "teil"

#: Derselbe Takt wie das sanfte Nachladen der Einzelseite.
NACHLADEN_MS = web.NEULADEN_SEKUNDEN * 1000

#: Welche Panels sich nachladen lassen. Der Chat NICHT: er hat seinen eigenen
#: Poll (Karte A2), und das Textbuch aendert sich nicht, waehrend man es liest.
_TEILE = ("stand",)

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


_TEXT_TAB = {"chat": "Chat", "stand": "Arbeitsstand", "textbuch": "Textbuch"}

#: Nur Struktur, keine Gestaltung -- die UX-Karte gestaltet (Kartentext).
_CSS_VEREINT = """
.tabs { position: sticky; top: 0; z-index: 5; display: flex; gap: .3rem;
        padding: .3rem 0; background: inherit; }
.tabs button { flex: 1; font: inherit; min-height: 2.8rem; border-radius: .6rem;
               border: 1px solid #c9c4b8; background: #fff; }
.tabs button[aria-selected="true"] { font-weight: 600; border-width: 2px; }
.panel[hidden] { display: none; }
"""

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
  document.addEventListener('click', function (ev) {
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
  setInterval(function () {
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
        f"{_TEXT_TAB[tab]}</button>"
        for tab in tabs
    )
    return f'<nav class="tabs" role="tablist">{knoepfe}</nav>'


def _leiste_html(roadmapdaten, nonce_wert: str) -> str:
    """Wird in Aufgabe 13 gefuellt."""
    return ""


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
    vorgabe = VORGABE_TAB if chat_vorhanden else "stand"
    panels = {
        "stand": web.gruppe_koerper(daten, nonce_wert, token, praefix, fassungswahl),
        "textbuch": web.textbuch_koerper(daten, token, praefix),
    }
    if chat_vorhanden:
        # ``mit_nonce=False``: das Stand-Panel traegt sein ``id="nonce"``
        # schon (``_bearbeiten_html``), mit demselben Wert -- ein zweites
        # Element mit derselben id waere ungueltiges HTML.
        panels["chat"] = web_chat.chat_koerper(
            chatdaten, nonce_wert, token, segment_ms,
            basis=f"{token}/", mit_nonce=False,
        )
    koerper = [_leiste_html(roadmapdaten, nonce_wert), _tabs_html(vorgabe, tabs)]
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
        + scope_css(web._CSS_TEXTBUCH, ".panel-textbuch")
    )
    if chat_vorhanden:
        css += scope_css(web_chat._CSS_CHAT, ".panel-chat")
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
        + web._TEXTBUCH_JS
    )
    if chat_vorhanden:
        skript += web_chat._js()
    return web._seite(
        f"{titel} — interview-theater", css, "\n".join(koerper),
        bearbeitbar=True, nachladen=False, skript=skript,
    )


def sende_teil(handler, db_pfad: str, token: str, name: str, praefix: str,
              schluessel: bytes, query: str) -> None:
    """``GET /g/<token>/teil/stand`` -- nur der Rumpf des Stand-Panels.

    Der Ersatz fuer das sanfte Nachladen der Einzelseite: dort tauscht
    ``web._SCROLL_JS`` den ganzen ``<body>``, hier nur dieses eine Panel.
    Alles andere -- Chat, Aufnahme, Strom, halb getipptes Feld -- bleibt
    stehen.

    Der frische Nonce kommt mit, wie beim sanften Nachladen: er steht IM
    Rumpf (``web.nonce``), nicht daran."""
    if name not in _TEILE:
        handler._antworte(404, web.nicht_gefunden_html())
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
