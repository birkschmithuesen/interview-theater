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
#: dem alten Stand. ``buehne`` kam am 02.10.2026 dazu (Birk, Root-Cause-Fix):
#: der Tab selbst steht jetzt immer im Dokument (nur ``hidden`` je nach
#: Phase), und sein Inhalt -- neue Karten aus dem Brainstorm -- soll sich
#: aktualisieren, WAEHREND er offen ist, nicht erst nach einem Neuladen.
_TEILE = ("stand", "roadmap", "buehne", "textbuch")
#: ``textbuch`` kam mit P57 Lauf 2 (A1) dazu: das Panel wurde nur beim
#: Seitenaufbau gerendert und zeigte neue Szenenprosa erst nach einem
#: vollen Neuladen ("Not written yet" trotz geschriebener Szene).

#: Die drei Panels. Reihenfolge = Reihenfolge der Tableiste. ``buehne`` steht
#: NICHT fest hier drin (anders als seit 02.10.2026 im gerenderten Markup):
#: dieselbe Konstante geht als ``__TABS__`` auch ins Hash-Routing des Skripts
#: (``lies()``/``setze()``), und ein mitgebrachtes ``#buehne`` auf einer
#: Telegram-Seite (kein Web-Kanal, aber immer ein CoThinker-Tab) soll genauso
#: funktionieren wie auf der Web-Seite -- ``seite()`` haengt ihn dort fest an.
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
    # Umbenannt zu "CoThinker" (Birk, 02.10.2026, Padua-Feedback b): nur die
    # sichtbare Beschriftung -- der interne Schluessel ``buehne`` bleibt
    # unveraendert (Routen, Tests, CSS-Klassen haengen daran).
    "buehne": "CoThinker",
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
/* Der unaufdringliche Marker fuer eine neue CoThinker-Karte (Birk,
   Feedback b, 02.10.2026): ein Punkt, kein Text, keine Zahl -- das Oeffnen
   des Tabs raeumt ihn weg (siehe ``zeige()`` in ``_VEREINT_JS``). */
.tabs button[data-neu="1"] { position: relative; }
.tabs button[data-neu="1"]::after {
  content: ""; position: absolute; top: .35rem; right: .35rem;
  width: .5rem; height: .5rem; border-radius: 50%; background: #a8201a;
}
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


def _css_schale(gewaehlt: str) -> str:
    """Mobile-App-Shell, Nachbesserung 03.10.2026 (Birk, Handytest 09:19 --
    woertlich: "die website auf dem handy rutscht hoch und runter, wenn
    sich unten tastatur oeffnet ... auch nach rechts ist platz und es
    rutscht hin und her ... soll sich immer optimal an die handy
    bildschirmgroesse anpassen und sich dann wie eine app anfuehlen").

    Angehaengt als LETZTER Block der zusammengebauten CSS in ``seite()`` --
    gleiche oder hoehere Spezifitaet als jede Regel davor (``_CSS_VEREINT``,
    die gescopten Panel-CSS, ``css_rahmen()`` mit ``_TABS_A``/``_TABS_B``,
    ``css_chat()``), gewinnt also unabhaengig von deren Reihenfolge -- ohne
    eine einzige Zeile davon anzufassen (sie bleiben Zeichen fuer Zeichen
    stehen, auch fuer die Tests, die ihren Wortlaut pruefen).

    ``<body>`` wird die EINE Flex-Spalte der Seite: Phasenleiste und Tabs
    bleiben feste Kopf-/Fusszeilen (``order`` traegt die A/B-Abweichung oben
    vs. unten), das sichtbare Panel ist der einzige Teil, der waechst und
    selbst scrollt (``.panel``) -- fuer den Chat gilt das NUR fuer
    ``.verlauf``: ``.fuss`` wird ein gewoehnliches letztes Flex-Kind statt
    eines ``position: fixed``-Elements ueber dem Dokument. Genau DAS war
    der Grund fuer das Rutschen -- eine Tastatur aendert auf dem Telefon den
    SICHTBAREN Ausschnitt, nicht das Dokument, und ein ``position:
    fixed``-Fuss haengt in Safari beim Auf- und Zuklappen der Tastatur eine
    Bewegung nach, statt sich sofort mitzuverschieben. Ohne Dokument-Scroll
    (``overflow: hidden`` auf ``html``/``body``) gibt es fuer die Tastatur
    nichts mehr zu verschieben.

    **Eine Ausnahme bleibt bewusst stehen:** der Interview-Modus
    (``web_gestalt.css_interview()``) braucht den Fuss weiterhin als echten
    Vollbild-Overlay (``position: fixed``) -- waehrend einer Aufnahme steht
    kein Textfeld im Fokus (``.zeile`` ist dort ausgeblendet), die
    Tastatur-Falle greift also gar nicht, und das Vollbild ist dort Absicht
    (Uhr, Pegel, Stopp-Knopf gross und allein). ``html:not([data-ux-interview="1"])``
    haelt die neue Regel deshalb aus genau diesem einen Zustand heraus,
    statt mit ihm um dieselbe Eigenschaft (``position``) zu kaempfen.

    **Das seitliche Padding wandert von ``body`` zu den einzelnen
    Kopf-/Inhaltselementen** (Browserlauf 03.10.2026, Regression gefangen
    von ``tests/e2e/test_web_gestalt_e2e.py::
    test_die_eingabezeile_passt_aufs_telefon`` -- derselbe Fehler, den jener
    Test schon einmal belegt hat: "Senden" halb ausserhalb des Bildes).
    Grund: ``.fuss`` war als ``position: fixed`` Element am VIEWPORT
    verankert und ignorierte das Padding von ``body`` komplett -- seine
    eigene, schon vorhandene Breite (``.7rem`` aus ``_CSS_CHAT``) war die
    EINZIGE seitliche Einruekung. Jetzt, als gewoehnliches Flex-Kind,
    LAEGE ``.fuss`` zusaetzlich INNERHALB von ``body``s Padding -- macht
    aus ``.7rem + 1.2rem`` auf jeder Seite genug, um die Knopfreihe auf
    einem 390px-Telefon zu sprengen. Deshalb bekommt ``body`` hier nur noch
    sein OBERES Padding, und Roadmap/Tabs/Panel tragen ihr seitliches
    Padding selbst -- ausser ``.panel-chat``, das es wieder auf Null setzt
    und an seine Kinder (``h1``, ``.verlauf``, ``.tippt``) weitergibt, damit
    ``.fuss`` padding-frei bleibt und wieder genau seine alte, eigene
    Breite bekommt.

    **Zwei weitere Regressionen, am echten Browser gefangen (Browserlauf
    03.10.2026), nicht am CSS-Text zu sehen:**

    1. ``margin: 0`` auf ``.panel``: die gescopten Panel-CSS (``web.
       _CSS_GRUPPE``/``_CSS_TEXTBUCH``/``web_chat._CSS_CHAT``) setzen auf
       ihrem jeweiligen ``body`` -- hier zu ``.panel-stand``/``.panel-
       textbuch``/``.panel-chat`` geworden -- ``margin: 0 auto``, fuer die
       Standalone-Seiten richtig (Zentrieren ueber ``max-width``). Ein
       Flex-Kind mit automatischen Seitenraendern wird vom
       Stretch-Algorithmus NICHT mehr auf die Breite des Elters
       gestreckt, sondern ueber seinen eigenen Inhalt bemessen -- gemessen
       lief ``.panel-chat`` so auf 405px statt 390px hinaus, weil seine
       breiteste Zeile (Eingabefeld plus zwei Knoepfe) mehr Raum wollte,
       als der Bildschirm hatte, und die automatischen Raender daraus
       keine Grenze mehr machten.
    2. ``min-width: 0`` auf ``.zeile`` und dem Eingabefeld: als
       ``position: fixed`` zwang ``left: 0; right: 0`` den Fuss auf exakt
       die Viewport-Breite, UNABHAENGIG vom Platzbedarf seiner Kinder --
       ein ``<input>`` schrumpfte darin zuverlaessig, weil der Rahmen
       selbst keinen Spielraum liess. Als gewoehnliches Flex-Kind gilt das
       nicht mehr von selbst: ``<input>`` hat einen eigenen, vom Browser
       vorgegebenen Mindestinhalt (``min-width: auto``), der ohne
       ``min-width: 0`` Vorrang vor ``flex-shrink`` bekommt und die ganze
       Zeile -- und mit ihr Panel, Verlauf und Fuss -- ueber die
       Telefonbreite hinaus aufblaeht.

    Beide Regressionen waren an rein textlichen CSS-Tests unsichtbar und
    nur am echten, gerenderten Layout zu finden; Belege und Zahlen stehen
    in ``docs/ux-padua/BERICHT.md``, Abschnitt „Mobile-App-Shell,
    Nachbesserung 03.10.".

    **Kopfzeilen-Karte (03.10.2026), zwei weitere Nachbesserungen hier,
    gemessen am echten Chromium, nicht am CSS-Text:**

    1. ``.roadmap`` bekommt hier zusaetzlich ``width: 100%; margin: 0``.
       ``_CSS_VEREINT``s ``.roadmap { max-width: 44rem; margin: 0 auto .6rem; }``
       zentriert das Element sonst ueber automatische Seitenraender --
       zusammen mit ``align-items: stretch`` auf ``body`` (oben) sizt der
       Browser ein Flex-Kind mit Auto-Raendern dann nicht mehr auf die
       verfuegbare Breite, sondern auf seinen eigenen Inhalt: sobald die
       neue, geflexte Kopfzeile (``.roadmap-kopf`` + Fortschrittslichter +
       "Next up") mehr Platz wollte als der Bildschirm hatte, wuchs
       ``.roadmap`` selbst ueber 390px hinaus statt dass seine Kinder
       schrumpften -- gemessen 624px breit auf einem 390px-Geraet, "Next
       up" dabei komplett ausserhalb des sichtbaren Bereichs.
    2. ``.roadmap summary`` verliert hier ihr ``padding: .6rem .3rem`` aus
       ``_CSS_VEREINT`` (vor der einzeiligen, geflexten Kopfzeile bemessen)
       und bekommt stattdessen die feste Hoehe ``var(--tippflaeche)``
       (44px, dasselbe Tippziel-Mass wie ueberall sonst). Mit dem alten
       Polster plus der ohnehin 44px hohen Tastflaeche (``.roadmap >
       summary`` aus ``_ROADMAP``) kam Kopf + Tableiste zusammen auf gemessen
       ueber 110px statt der verlangten 96px.

    **Feedbackloop P1-M3 (05.10.2026):** der Padua-Stepper (``header.
    phasenav``, ``css_stepper()``) ist eine ANDERE Kopfzeile als
    ``.roadmap`` (das ``<details>`` aus ``_leiste_html``) und fehlte hier
    ganz -- ohne die Flex-Item-Regeln oben blieb sein eigenes ``position:
    sticky`` aus ``_STEPPER`` wirkungslos (``body`` scrollt seit dieser
    Karte gar nicht mehr), aber er zaehlte auch nicht als fester Kopf im
    Flex-Layout. Jetzt bekommt er dieselbe Behandlung wie ``.roadmap``
    (flex-item, volle Breite, kein Rand) und ``position: static`` statt
    des wirkungslosen ``sticky``.

    **Feedbackloop S8 (05.10.2026):** ``web_chat._CHAT_JS`` haengt
    ``.verlauf`` nach jedem Poll/Stream-Ereignis per
    ``verlauf.scrollTop = verlauf.scrollHeight`` ans Ende (``nachUnten()``,
    nicht angefasst -- parallele Karte). Traf das Scroll-Ende mitten in
    einer Blase, endete die sichtbare Liste GENAU an der polsterlosen
    oberen Kante von ``.verlauf`` -- direkt unter dem Gruppentitel, der
    selbst ``position: static`` ist und gar nichts ueberlappt (gemessen per
    Playwright: ein gewoehnliches Flex-Geschwister OBERHALB von
    ``.verlauf``). Zwei Kandidaten wurden gemessen und verworfen, bevor
    diese Regel entstand: ``scroll-padding-top`` wirkt nur auf
    ``scrollIntoView``/Scroll-Snap, nicht auf eine direkte
    ``scrollTop``-Zuweisung (ohne Wirkung gemessen); ``scroll-snap-type`` +
    ``scroll-snap-align`` griff bei derselben Zuweisung ebenfalls nicht
    (Chromium rastet nur bei nutzergefuehrtem/animiertem Scrollen ein, nicht
    beim synchronen Setzen der Eigenschaft -- gemessen, keine Verschiebung).
    Ein festes ``padding-bottom`` (``web_gestalt._CHAT_A``/``_CHAT_B``)
    verschiebt die Bodenkante zwar um sich selbst, schneidet aber bei
    anderer Blasenlaenge/Gesamthoehe trotzdem irgendeine Blase an -- content-
    abhaengig, kein Beweis fuer den allgemeinen Fall (gemessen mit laengerem
    Fuelltext). Die einzige Regel, die UNABHAENGIG von Blasenlaenge und
    Scrollstand wirkt, ist eine Ausblendung am oberen Rand selbst: eine
    Maske faerbt den obersten Streifen von ``.verlauf`` weich zum
    Hintergrund aus, WAS AUCH IMMER dort gerade steht -- keine harte
    Schnittkante mehr, die wie ein ueberlappender Titel aussieht, sondern
    ein erkennbarer, blasenlaengen-unabhaengiger Scroll-Hinweis (dasselbe
    Verfahren wie ein "mehr oben"-Schatten in jeder Listen-UI). Kein
    ``url()``, keine Fremdquelle -- ein reiner CSS-Gradient, von der
    bestehenden CSP (``style-src 'nonce-…'``, kein ``img-src``) nicht
    betroffen."""
    tabs_reihenfolge = "order: 5;" if gewaehlt == "a" else "order: 1;"
    return f"""
html {{ height: 100%; overflow-x: hidden; }}
body {{ display: flex; flex-direction: column; align-items: stretch;
        margin: 0 auto; padding: 1rem 0 0; overflow: hidden;
        height: 100vh; height: 100dvh; height: var(--vh, 100dvh); }}
.roadmap, header.phasenav {{ flex: 0 0 auto; order: 0; min-width: 0;
            width: 100%; margin: 0;
            padding-left: 1.2rem; padding-right: 1.2rem; }}
.roadmap summary {{ padding-top: 0; padding-bottom: 0;
                    min-height: auto; height: var(--tippflaeche); }}
header.phasenav {{ position: static; }}
.tabs {{ position: static; flex: 0 0 auto; min-width: 0; {tabs_reihenfolge}
         padding-left: 1.2rem; padding-right: 1.2rem;
         padding-bottom: calc(.3rem + env(safe-area-inset-bottom)); }}
.panel {{ flex: 1 1 auto; order: 2; min-width: 0; min-height: 0; margin: 0;
          overflow-y: auto; overflow-x: hidden; overscroll-behavior: contain;
          -webkit-overflow-scrolling: touch;
          padding-left: 1.2rem; padding-right: 1.2rem; padding-bottom: 1rem; }}
.panel-chat {{ display: flex; flex-direction: column; overflow-y: hidden;
               padding-left: 0; padding-right: 0; padding-bottom: 0; }}
.panel-chat > h1, .panel-chat > p, .panel-chat .tippt {{
  padding-left: 1.2rem; padding-right: 1.2rem;
}}
.panel-chat .verlauf {{ flex: 1 1 auto; min-width: 0; min-height: 0;
                        overflow-y: auto; overflow-x: hidden;
                        overscroll-behavior: contain;
                        -webkit-overflow-scrolling: touch;
                        padding-left: 1.2rem; padding-right: 1.2rem;
                        -webkit-mask-image:
                          linear-gradient(to bottom, transparent, black 1rem);
                        mask-image:
                          linear-gradient(to bottom, transparent, black 1rem); }}
html:not([data-ux-interview="1"]) .panel-chat .fuss {{
  position: static; flex: 0 0 auto; min-width: 0;
  left: auto; right: auto; top: auto; bottom: auto;
  margin-left: 0; margin-right: 0;
  padding-bottom: calc(.8rem + env(safe-area-inset-bottom));
}}
.zeile {{ min-width: 0; }}
.zeile input {{ font-size: 16px; touch-action: manipulation; min-width: 0; }}
.zeile button, .tabs button, .leiste button,
#interview, #ptt, #senden, #diskussion {{ touch-action: manipulation; }}
"""


#: Setzt ``--vh`` aus dem ``visualViewport`` (iOS Safari ignoriert
#: ``interactive-widget=resizes-content`` und veraendert nur ihn, nicht die
#: Layout-Groesse) -- der Fallback ``100dvh`` in ``_css_schale`` greift
#: ueberall sonst sofort, bevor dieses Skript ueberhaupt laeuft. CSSOM
#: (``style.setProperty``), kein ``style=``-Attribut (AGENTS.md, CSP ohne
#: ``'unsafe-inline'``).
_VH_JS = """
(function () {
  var wurzel = document.documentElement;
  function setze() {
    var h = window.visualViewport ? window.visualViewport.height : window.innerHeight;
    wurzel.style.setProperty('--vh', h + 'px');
  }
  setze();
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', setze);
  } else {
    window.addEventListener('resize', setze);
  }
})();
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
    //
    // Mobile-App-Shell (03.10.2026): ``verlauf`` scrollt seit dieser Karte
    // IN SICH selbst (``.panel-chat .verlauf { overflow-y: auto }`` aus
    // ``web_vereint._css_schale``), nicht mehr das Dokument -- deshalb
    // zaehlt seine eigene ``scrollTop``/``scrollHeight``, nicht die des
    // Fensters.
    if (verlauf.offsetParent === null) { return false; }
    return verlauf.clientHeight + verlauf.scrollTop >= verlauf.scrollHeight - 120;
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
    if (unten) { verlauf.scrollTop = verlauf.scrollHeight; }
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
  // CoThinker-Root-Cause-Fix (Birk 02.10.2026): ``buehne`` steht jetzt IMMER
  // in TABS (das Panel existiert immer im Dokument, nur ``hidden`` je nach
  // Phase) -- ``lies()`` muss den alten Rueckfall deshalb selbst nachbauen,
  // nicht mehr ueber ein fehlendes Array-Element: ein mitgebrachtes
  // ``#buehne`` (alter Link) ausserhalb Phase 4 (oder Phase 1 mit
  // Begriffsboard) faellt weiterhin auf VORGABE zurueck, genau wie zuvor.
  // Karte t_4517d4ad: der CoThinker steht in Phase 4 (Buehnenkarten) UND in
  // Phase 1, wenn das Profil das Begriffsboard faehrt (``#roadmap`` traegt
  // dann ``data-begriffsboard="1"``, gesetzt von ``_leiste_html``).
  // Birk 05.10.2026: mit demselben Merkmal auch Phase 2 (Fragenuebersicht).
  function istCoThinkerPhase() {
    var rm = document.getElementById('roadmap');
    if (!rm) { return false; }
    var p = rm.dataset.aktivePhase;
    return p === '4' || ((p === '1' || p === '2') && rm.dataset.begriffsboard === '1');
  }
  var lies = function () {
    var teile = location.hash.replace(/^#/, '').split('&');
    for (var i = 0; i < teile.length; i++) {
      if (TABS.indexOf(teile[i]) >= 0) {
        if (teile[i] === 'buehne' && !istCoThinkerPhase()) { continue; }
        return teile[i];
      }
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
    if (name === 'textbuch' && typeof ladeTextbuch === 'function') { ladeTextbuch(); }
    // Der unaufdringliche Marker (Birk, Feedback b) gilt nur, solange der
    // Tab nicht vorn ist -- ein Oeffnen raeumt ihn weg, kein zweiter Weg.
    if (name === 'buehne') {
      var buehneKnopf = document.querySelector('.tabs button[data-tab="buehne"]');
      if (buehneKnopf) { delete buehneKnopf.dataset.neu; }
      // Beim Oeffnen sofort frisch holen, nicht bis zum naechsten Takt
      // (bis zu NACHLADEN_MS) einen veralteten Stand zeigen.
      if (typeof ladeBuehne === 'function') { ladeBuehne(); }
    }
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
        // Teil B: nach einem erfolgreichen Sprung schliesst sich das Menue
        // selbst -- auf dem Handy nimmt es sonst Platz weg, den niemand
        // mehr braucht. VOR ``ladeRoadmap()``: die Funktion sichert
        // ``ziel.open`` (= ``warOffen``) und stellt es nach dem Austausch
        // wieder her -- faellt die Zeile hier weg, kaeme das Menue beim
        // naechsten Takt wieder offen zurueck.
        var roadmap = document.getElementById('roadmap');
        if (roadmap) roadmap.open = false;
        // Birk 07.10.2026: die Antwort auf einen Phasenklick (Rueckfrage,
        // Werkbank-Uebersicht vor Phase 5, Wiederherstellungs-Zeile) steht im
        // CHAT -- also den Chat-Tab nach vorn holen, sonst wird sie aus der
        // Werkbank heraus uebersehen.
        if (document.querySelector('.tabs button[data-tab="chat"]')) {
          location.hash = '#chat';
        }
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
    // Teil B: ein Tap ausserhalb des Menues klappt es zu -- aber NIE ein
    // Klick auf die ``<summary>`` oder einen Knopf/eine Aufgabe DARIN, die
    // haben ihre eigene Logik weiter unten. Kein ``return`` danach: ein
    // Klick auf einen Tab-Knopf soll das Menue schliessen UND den Tab
    // wechseln.
    var roadmapOffen = document.getElementById('roadmap');
    if (roadmapOffen && roadmapOffen.open && !ev.target.closest('#roadmap')) {
      roadmapOffen.open = false;
    }
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
      // Teil B: "Stay here" schliesst auch das Menue selbst.
      var roadmapNein = document.getElementById('roadmap');
      if (roadmapNein) { roadmapNein.open = false; }
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
    // CoThinker-Root-Cause-Fix (Birk 02.10.2026): Tab-Knopf UND Panel
    // folgen der frisch geladenen Phase -- unabhaengig davon, wie die
    // Gruppe in Phase 4 (oder Phase 1 mit Begriffsboard) eingetreten ist
    // (Chat, Phasenleiste-Klick, "Ja speichern"). KEIN automatischer
    // Tab-Wechsel beim Erscheinen (Birk: "no surprise jumps") -- nur beim
    // VERLASSEN der CoThinker-Phase, waehrend der Buehne-Tab gerade vorn
    // ist, faellt die Seite auf VORGABE zurueck, weil ihr Panel sonst leer
    // verborgen vorn staende.
    var buehnePanel = document.getElementById('tab-buehne');
    var buehneKnopf = document.querySelector('.tabs button[data-tab="buehne"]');
    if (buehnePanel && buehneKnopf) {
      var p4 = istCoThinkerPhase();
      buehneKnopf.hidden = !p4;
      if (!p4) {
        buehnePanel.hidden = true;
        delete buehneKnopf.dataset.neu;
        if (document.body.dataset.tab === 'buehne') { setze(VORGABE); }
      }
    }
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
        // Mobile-App-Shell (03.10.2026): ``panel`` ist seit dieser Karte
        // selbst der Scroll-Container (``.panel { overflow-y: auto }``),
        // nicht mehr das Dokument -- die Fassung wird also an seiner
        // eigenen ``scrollTop`` gesichert, nicht an ``window.scrollY``.
        var y = panel.scrollTop;
        panel.innerHTML = neu;
        panelLetzter = neu;
        panel.querySelectorAll('details > summary').forEach(function (el) {
          if (zustand[el.textContent.trim()]) { el.parentElement.setAttribute('open', ''); }
        });
        panel.scrollTop = y;
      })
      .catch(function () {})
      .finally(function () { laeuft = false; });
  }, __NACHLADEN_MS__);
  // -- CoThinker-Panel: Live-Aktualisierung + unaufdringlicher Marker ------
  //
  // Birk, Feedback b (02.10.2026): der Bot "antwortet" im Brainstorm-Modus
  // NICHT im Chat -- eine neue Karte zeigt sich nur hier. Offen zeigt sich
  // eine neue Karte sofort (derselbe Takt wie Stand/Roadmap); geschlossen
  // reicht ein Punkt am Tab-Knopf (``data-neu``), kein Text, keine Zahl.
  //
  // Task 1 (Padua CoThinker-Tab clean, 03.10.2026): die Tafel bekam dazu
  // einen Browser-seitigen Verlauf (◀/▶), portiert aus
  // cothinker/stage/stage.py (SCRIPT, "verlauf"/"pos"/"male"/"zeige"/
  // "blaettern"/"verlaufUebernehmen"). EIN Grundsatz traegt die ganze
  // Portierung: der Zeiger in den Verlauf (``buehnePos``) lebt NUR hier im
  // Browser, nie auf dem Server, nie in einer DB-Spalte. Wer zurueckblaettert
  // und waehrenddessen eine neue Karte verpasst, wird nicht automatisch
  // dorthin verschoben -- nur die Navigationsleiste bekommt einen "neu:"-
  // Hinweis (``male()``s Regel). Anders als bei CoThinker gibt es hier aber
  // keine zweite "live"-Quelle neben dem Verlauf: "aktuell" (``pos===null``)
  // UND "die neueste Karte der Liste" sind bei uns dasselbe, es gibt also
  // kein eigenes ``letzte``-Objekt zu pflegen.
  //
  // Die fuenf reinen Funktionen unten (``buehneEscape``/``buehneVorschau``/
  // ``buehneBlaettern``/``buehneUebernehmen``/``buehneNavHtml``) haben KEINE
  // Abhaengigkeit zu DOM oder den ``buehne*``-Variablen -- absichtlich, damit
  // tests/test_buehne_nav_js.py sie woertlich herausloesen und unter Node
  // einzeln aufrufen kann (wie test_web_vereint_js_syntax.py es mit dem
  // ganzen <script>-Block tut, hier nur je Funktion).
  var buehneLetzter = null;
  // Fix 05.10.2026 (Auswahlliste, Padua): ``gen`` zaehlt die fertigen
  // Tipp-POSTs, ``unterwegs`` die laufenden (gepflegt von ``_AUSWAHL_JS``).
  // Eine Panel-Antwort, deren Anfrage VOR dem letzten fertigen Tipp lief,
  // ist veraltet und wird verworfen -- sonst klappt die Zeile zurueck.
  // ``gesehen`` laesst ``holePanel`` ``buehneLetzter`` mitfuehren.
  var buehneTakt = window.buehneTakt = {
    gen: 0, unterwegs: 0,
    gesehen: function (html) { buehneLetzter = html; }
  };
  var buehneVerlauf = [];
  var buehnePos = null;
  var buehneBasis = '';
  var buehneZurueckText = '';
  var buehneNeuPraefix = '';

  function buehneEscape(s) {
    return String(s).replace(/[&<>"']/g, function (z) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[z];
    });
  }

  // Dieselbe sichere Markdown-Teilmenge wie ``web._buehne_inline``/
  // ``_buehne_markdown`` (Birk 06.10.2026) -- Fett vor Kursiv auf einer
  // bereits maskierten Zeile, sonst fraesse Kursiv die Fett-Sternpaare an.
  function buehneInline(zeile) {
    zeile = zeile.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
    return zeile.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');
  }

  // buehneMarkdown-Aequivalent zu ``web._buehne_markdown``: IMMER zuerst
  // maskieren (``buehneEscape``), erst danach die vier Regeln -- ein
  // woertliches ``<script>`` im Kartentext bleibt so Text, nie Markup.
  function buehneMarkdown(text) {
    var bloecke = [];
    var liste = [];
    function schliesseListe() {
      if (liste.length) {
        bloecke.push('<ul>' + liste.map(function (z) { return '<li>' + z + '</li>'; }).join('') + '</ul>');
        liste = [];
      }
    }
    var zeilen = buehneEscape(text || '').split('\\n');
    for (var i = 0; i < zeilen.length; i++) {
      var zeile = zeilen[i].trim();
      if (!zeile) { schliesseListe(); continue; }
      var aufzaehlung = zeile.match(/^(?:-|•)\\s+(.+)$/);
      if (aufzaehlung) { liste.push(buehneInline(aufzaehlung[1])); continue; }
      schliesseListe();
      var ueberschrift = zeile.match(/^\\*\\*([^*]+)\\*\\*$/);
      if (ueberschrift) {
        bloecke.push('<p class="buehne-ueberschrift"><strong>' + ueberschrift[1] + '</strong></p>');
        continue;
      }
      bloecke.push('<p>' + buehneInline(zeile) + '</p>');
    }
    schliesseListe();
    return bloecke.join('');
  }

  function buehneVorschau(text) {
    var t = (text || '').replace(/\\s+/g, ' ').trim();
    return t.length > 40 ? t.slice(0, 40) + '…' : t;
  }

  // blaettern-Aequivalent: ``verlauf`` ist AELTESTE ZUERST (wie der
  // JSON-Baustein es liefert), "aktuell" ist sowohl ``pos===null`` als auch
  // (gleichbedeutend) der letzte Index -- ein Schritt, der dort landet,
  // wird deshalb zu ``null`` normalisiert statt den Index zu behalten.
  function buehneBlaettern(verlauf, pos, schritt) {
    if (!verlauf || verlauf.length < 2) { return (pos === undefined) ? null : pos; }
    var ziel = ((pos === null || pos === undefined) ? verlauf.length - 1 : pos) + schritt;
    if (ziel < 0) { ziel = 0; }
    if (ziel > verlauf.length - 1) { ziel = verlauf.length - 1; }
    return (ziel === verlauf.length - 1) ? null : ziel;
  }

  // verlaufUebernehmen-Aequivalent: der Leser folgt der CONTENT-id, nicht
  // dem Index -- faellt sie aus einer gedeckelten Liste heraus, wird die
  // AELTESTE verbliebene Position gehalten (CoThinkers Regel), nie ans Ende
  // gesprungen: ein Sprung waere der unerwartete Ortswechsel, den die ganze
  // Portierung vermeiden soll. ``basis`` ruehrt diese Funktion bewusst
  // nicht an -- das macht nur ``buehneZeige`` beim Umschalten selbst.
  function buehneUebernehmen(verlauf, pos, neuerVerlauf) {
    var hier = (pos !== null && pos !== undefined && verlauf && verlauf[pos])
      ? verlauf[pos].id : null;
    var neu = Array.isArray(neuerVerlauf) ? neuerVerlauf : [];
    var neuePos = pos;
    if (pos !== null && pos !== undefined) {
      var gefunden = -1;
      for (var i = 0; i < neu.length; i++) {
        if (neu[i].id === hier) { gefunden = i; break; }
      }
      neuePos = (gefunden >= 0) ? gefunden : (neu.length ? 0 : null);
    }
    return { verlauf: neu, pos: neuePos };
  }

  // male()-Aequivalent, nur der Text/die Markup-Zeichenkette -- das Einsetzen
  // ins DOM macht ``buehneNavRender()``. ``verlauf``/``pos`` wie oben,
  // ``basis`` ist die id, die beim Verlassen von "aktuell" galt (vgl.
  // CoThinkers ``zeige()``), ``zurueckText``/``neuPraefix`` kommen bereits
  // lokalisiert vom Server (siehe ``web._buehne_html``).
  function buehneNavHtml(verlauf, pos, basis, zurueckText, neuPraefix) {
    var n = verlauf ? verlauf.length : 0;
    if (n < 2) { return ''; }
    var i = (pos === null || pos === undefined) ? n - 1 : pos;
    var text = '<span class="zaehler">' + (i + 1) + '/' + n + '</span>';
    if (pos !== null && pos !== undefined) {
      text += ' <a href="#" data-v="live">' + buehneEscape(zurueckText) + '</a>';
      // Ein NEUER Stand waehrend des Zurueckblaetterns wird GEMELDET, nie
      // angesprungen -- das waere genau die "unexpected displacement", die
      // die Referenz ausdruecklich verbietet.
      if (basis && verlauf[n - 1] && verlauf[n - 1].id !== basis) {
        text += ' <span class="neu">' + buehneEscape(neuPraefix)
          + buehneEscape(buehneVorschau(verlauf[n - 1].text)) + '</span>';
      }
    }
    return (
      '<button type="button" data-v="zurueck"' + (i <= 0 ? ' disabled' : '') + '>◀</button>'
      + '<button type="button" data-v="vor"' + (i >= n - 1 ? ' disabled' : '') + '>▶</button>'
      + text
    );
  }

  function buehneNavRender() {
    var el = document.getElementById('buehne-nav');
    if (!el) { return; }
    el.innerHTML = buehneNavHtml(
      buehneVerlauf, buehnePos, buehneBasis, buehneZurueckText, buehneNeuPraefix
    );
  }

  // zeige()-Aequivalent: setzt die Tafel direkt aus dem Client-Verlauf --
  // ``innerHTML`` aus ``buehneMarkdown`` (Birk 06.10.2026, vorher
  // ``textContent`` mit rohem Modelltext samt sichtbaren Sternchen), die
  // einzige Stelle, die Markup einfuegt, und die maskiert IMMER zuerst.
  // "aktuell" (``i===null``) liest dabei die NEUESTE Karte des Verlaufs --
  // bei uns dieselbe Quelle wie die naechste Serverantwort, es gibt kein
  // zweites ``letzte``-Objekt.
  function buehneZeige(i) {
    if (i !== null && buehnePos === null) {
      var letzte = buehneVerlauf.length ? buehneVerlauf[buehneVerlauf.length - 1] : null;
      buehneBasis = letzte ? letzte.id : '';
    }
    if (i === null) { buehneBasis = ''; }
    buehnePos = i;
    var tafel = document.getElementById('buehne-tafel');
    if (tafel) {
      var eintrag = (i === null)
        ? (buehneVerlauf.length ? buehneVerlauf[buehneVerlauf.length - 1] : null)
        : buehneVerlauf[i];
      if (eintrag) { tafel.innerHTML = buehneMarkdown(eintrag.text || ''); }
    }
    buehneNavRender();
  }

  function buehneAktiv() {
    // Phase 4 (oder Phase 1 mit Begriffsboard).
    return istCoThinkerPhase() && document.body.dataset.tab === 'buehne';
  }

  function buehneLiesDaten(doc) {
    var el = doc.getElementById('buehne-verlauf-daten');
    if (!el) { return null; }
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  // Anfangszustand: aus dem bereits ausgelieferten Dokument lesen, nicht
  // erst auf den ersten Poll warten -- sonst zeigt die Nav-Leiste beim
  // ersten Rendern noch nichts, obwohl der Server schon Verlauf mitgab.
  (function () {
    var anfang = buehneLiesDaten(document);
    if (anfang) {
      buehneVerlauf = Array.isArray(anfang.karten) ? anfang.karten : [];
      buehneZurueckText = anfang.zurueck_text || '';
      buehneNeuPraefix = anfang.neu_praefix || '';
    }
    buehneNavRender();
  })();

  // Ein gemeinsamer Tipp-Schutz fuer Pfeiltasten -- noch ohne Vorbild in
  // dieser Datei (anders als web_chat.py's PTT-Code gibt es hier keine
  // ``tippt()``-Funktion zum Wiederverwenden), deshalb neu, aber nach
  // demselben Muster: Pfeiltasten sollen kein Eingabefeld unterbrechen.
  function tippt() {
    var el = document.activeElement;
    if (!el) { return false; }
    var tag = (el.tagName || '').toUpperCase();
    return tag === 'INPUT' || tag === 'TEXTAREA' || !!el.isContentEditable;
  }

  document.addEventListener('click', function (ev) {
    if (!buehneAktiv()) { return; }
    var t = ev.target && ev.target.closest ? ev.target.closest('#buehne-nav [data-v]') : null;
    if (!t) { return; }
    var was = t.getAttribute('data-v');
    if (was === 'zurueck') { buehneZeige(buehneBlaettern(buehneVerlauf, buehnePos, -1)); }
    else if (was === 'vor') { buehneZeige(buehneBlaettern(buehneVerlauf, buehnePos, 1)); }
    else if (was === 'live') { buehneZeige(null); }
    else { return; }
    ev.preventDefault();
  });

  document.addEventListener('keydown', function (ev) {
    if (!buehneAktiv()) { return; }
    if (ev.metaKey || ev.ctrlKey || ev.altKey || ev.shiftKey) { return; }
    if (tippt()) { return; }
    if (ev.key === 'ArrowLeft') { buehneZeige(buehneBlaettern(buehneVerlauf, buehnePos, -1)); }
    else if (ev.key === 'ArrowRight') { buehneZeige(buehneBlaettern(buehneVerlauf, buehnePos, 1)); }
    else { return; }
    ev.preventDefault();
  });

  // Wischen -- nur ueber der Tafel selbst, nur mit einem Finger, Schwelle
  // 40px (kein Swipe-Helfer im Repo vorhanden, bewusst minimal gehalten).
  (function () {
    var startX = null;
    var SCHWELLE = 40;
    document.addEventListener('touchstart', function (ev) {
      var t = ev.target && ev.target.closest ? ev.target.closest('#buehne-tafel') : null;
      startX = (buehneAktiv() && t && ev.touches && ev.touches.length === 1)
        ? ev.touches[0].clientX : null;
    }, { passive: true });
    document.addEventListener('touchend', function (ev) {
      if (startX === null) { return; }
      var x0 = startX;
      startX = null;
      if (!buehneAktiv()) { return; }
      var endX = (ev.changedTouches && ev.changedTouches.length)
        ? ev.changedTouches[0].clientX : null;
      if (endX === null) { return; }
      var delta = endX - x0;
      if (Math.abs(delta) < SCHWELLE) { return; }
      buehneZeige(buehneBlaettern(buehneVerlauf, buehnePos, delta < 0 ? 1 : -1));
    }, { passive: true });
  })();

  // -- Begriffsboard: Live-Ranking ohne Springen (Karte t_cb2c4678) -------
  //
  // ladeBuehne() tauscht das ganze Panel (panel.innerHTML = neu). Damit die
  // Liste dabei nicht springt, misst bbMerke() die alten Zeilen UNMITTELBAR
  // davor und bbSpiele() spielt UNMITTELBAR danach FLIP: jede Zeile startet
  // optisch an ihrer alten Stelle und gleitet an die neue. Zuordnung ueber
  // data-begriff, fuer einen geschaerften Begriff ueber data-vorgaenger.
  // Seit der Design-Erweiterung gibt es kein aufklappbares "Warum" mehr --
  // bbMerke/bbSpiele muessen keinen Auf-/Zu-Zustand mehr tragen. Ohne
  // ol.begriffsboard (Phase 4, Buehnenkarten) tun beide nichts. Bewegung
  // nur per CSSOM (CSP) und nie bei prefers-reduced-motion: reduce.
  var BB_DAUER_MS = 320;

  function bbSchluessel(text) {
    return String(text || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  }

  // Je neuem Eintrag der Schluessel der alten Zeile, von der er kommt, oder
  // null (neu). Erst ueber den eigenen Begriff, dann ueber den juengsten
  // Vorgaenger -- nur, wenn diese alte Zeile nicht schon vergeben ist.
  function bbZuordnung(alt, neu) {
    var frei = {};
    alt.forEach(function (b) { frei[bbSchluessel(b)] = true; });
    var erst = neu.map(function (n) {
      var k = bbSchluessel(n.begriff);
      if (frei[k]) { frei[k] = false; return k; }
      return null;
    });
    return erst.map(function (k, i) {
      if (k !== null) { return k; }
      var v = bbSchluessel(neu[i].vorgaenger);
      if (v && frei[v]) { frei[v] = false; return v; }
      return null;
    });
  }

  // FLIP "Invert": alte Lage minus neue, je neuem Eintrag; null ohne alte Lage.
  function bbVersatz(altLagen, quellen, neuLagen) {
    return quellen.map(function (q, i) {
      if (q === null || !altLagen || typeof altLagen[q] !== 'number') { return null; }
      return altLagen[q] - neuLagen[i];
    });
  }

  function bbMerke(panel) {
    var ol = panel.querySelector('ol.begriffsboard');
    if (!ol) { return null; }
    var vorher = { alt: [], lagen: {} };
    Array.prototype.forEach.call(ol.children, function (li) {
      var b = li.getAttribute('data-begriff');
      var k = bbSchluessel(b);
      vorher.alt.push(b);
      vorher.lagen[k] = li.getBoundingClientRect().top;
    });
    return vorher;
  }

  function bbSpiele(panel, vorher) {
    if (!vorher) { return; }
    var ol = panel.querySelector('ol.begriffsboard');
    if (!ol) { return; }
    var lis = Array.prototype.slice.call(ol.children);
    var quellen = bbZuordnung(vorher.alt, lis.map(function (li) {
      return { begriff: li.getAttribute('data-begriff'),
               vorgaenger: li.getAttribute('data-vorgaenger') };
    }));
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }
    var versatz = bbVersatz(vorher.lagen, quellen, lis.map(function (li) {
      return li.getBoundingClientRect().top;
    }));
    lis.forEach(function (li, i) {
      if (quellen[i] === null) { li.style.opacity = '0'; }
      else if (versatz[i]) { li.style.transform = 'translateY(' + versatz[i] + 'px)'; }
    });
    ol.getBoundingClientRect();   // Startlage festschreiben (Reflow)
    requestAnimationFrame(function () {
      lis.forEach(function (li) {
        li.style.transition = 'transform ' + BB_DAUER_MS + 'ms ease, opacity '
          + BB_DAUER_MS + 'ms ease';
        li.style.transform = '';
        li.style.opacity = '';
      });
      setTimeout(function () {
        lis.forEach(function (li) { li.style.transition = ''; });
      }, BB_DAUER_MS + 50);
    });
  }

  function ladeBuehne() {
    // Phase 4 (oder Phase 1 mit Begriffsboard).
    if (!istCoThinkerPhase()) { return; }
    var panel = document.getElementById('tab-buehne');
    if (!panel) { return; }
    if (buehneLetzter === null) { buehneLetzter = panel.innerHTML; }
    var taktGen = buehneTakt.gen;
    fetch(BASIS_TEIL + 'buehne', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (text) {
        if (text === null) { return; }
        if (buehneTakt.gen !== taktGen || buehneTakt.unterwegs > 0) { return; }
        var doc = new DOMParser().parseFromString(text, 'text/html');
        var neu = doc.body ? doc.body.innerHTML : null;
        if (!neu || neu === buehneLetzter) { return; }
        // Bug Birk Live-Test 04.10.2026 ("CoThinker leer bis Reload"):
        // ``buehneLetzter`` stand frueher VOR dieser Weiche -- ein Stand, der
        // bei verborgenem Panel ankam, galt damit als "schon gezeigt", und
        // nach dem Oeffnen fand jeder weitere Takt ``neu === buehneLetzter``
        // und tauschte nie. ``buehneLetzter`` heisst "steht im Panel", wird
        // also NUR gesetzt, wenn wirklich eingesetzt wurde.
        if (!panel.hidden) {
          buehneLetzter = neu;
          // Der Verlaufszeiger lebt NUR im Browser (s.o.): ein frischer
          // Serverstand bringt nur mit, was neu dazukam, verschiebt ``pos``
          // aber nie selbst (``buehneUebernehmen``).
          var daten = buehneLiesDaten(doc);
          if (daten) {
            var uebernommen = buehneUebernehmen(buehneVerlauf, buehnePos, daten.karten);
            buehneVerlauf = uebernommen.verlauf;
            buehnePos = uebernommen.pos;
            buehneZurueckText = daten.zurueck_text || buehneZurueckText;
            buehneNeuPraefix = daten.neu_praefix || buehneNeuPraefix;
          }
          if (buehnePos === null) {
            // "Aktuell": komplett ersetzen -- sicher, weil
            // buehneNavRender() den (absichtlich leeren) Nav-Platzhalter
            // sofort danach selbst fuellt (siehe web._buehne_html). Das
            // Begriffsboard (Phase 1) gleitet dabei per FLIP an seine neue
            // Ordnung, statt zu springen (bbMerke/bbSpiele, oben).
            var bbVorher = bbMerke(panel);
            panel.innerHTML = neu;
            bbSpiele(panel, bbVorher);
          }
          // Zurueckgeblaettert (``buehnePos !== null``): Status und Tafel
          // bleiben UNANGETASTET stehen -- nur die Navigationsleiste bekommt
          // ggf. den "neu:"-Hinweis. Das ist die eine Verhaltensregel, auf
          // der die ganze Karte steht.
          buehneNavRender();
          return;
        }
        // Verborgen: nur der Punkt am Tab-Knopf, kein Inhalt vorab tauschen
        // (der naechste Oeffnen-Takt holt ohnehin frisch, siehe oben).
        var knopf = document.querySelector('.tabs button[data-tab="buehne"]');
        if (knopf) { knopf.dataset.neu = '1'; }
      })
      .catch(function () {});
  }
  setInterval(ladeBuehne, __NACHLADEN_MS__);
  // -- Textbuch-Tab nachladen (P57 Lauf 2, A1) ------------------------------
  //
  // Das Panel wurde nur beim Seitenaufbau gerendert: neue Szenenprosa
  // erschien erst nach vollem Neuladen. Geholt wird nur bei sichtbarem Tab
  // (und sofort beim Oeffnen, siehe zeige()). Rollenfilter/Schrift stehen
  // am Panel bzw. im Hash und werden nach dem Tausch ueber ``hashchange``
  // neu angewendet (die Knoepfe selbst sind frisch gerendert).
  // Verglichen wird NICHT mit dem ersten Abruf, sondern mit dem Stempel
  // (Hash des Rumpfes, vom Server in ``textbuch_koerper`` gesetzt): die
  // Seite wurde evtl. vor der Szene gebaut. Wer den ersten Abruf nur
  // "merkt", zeigt den veralteten Aufbau-Stand weiter (P57 Lauf 3, A1).
  function textbuchStempel(wurzel) {
    var el = wurzel ? wurzel.querySelector('[data-stempel]') : null;
    return el ? el.getAttribute('data-stempel') : null;
  }
  function ladeTextbuch() {
    var panel = document.getElementById('tab-textbuch');
    if (!panel || panel.hidden || document.hidden) { return; }
    fetch(BASIS_TEIL + 'textbuch', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (text) {
        if (!text) { return; }
        var doc = new DOMParser().parseFromString(text, 'text/html');
        var neu = doc.body ? doc.body.innerHTML : null;
        if (!neu || panel.hidden) { return; }
        var stempel = textbuchStempel(doc.body);
        if (!stempel || stempel === textbuchStempel(panel)) { return; }
        var y = panel.scrollTop;
        panel.innerHTML = neu;
        panel.scrollTop = y;
        window.dispatchEvent(new Event('hashchange'));
      })
      .catch(function () {});
  }
  setInterval(ladeTextbuch, __NACHLADEN_MS__);
  // -- CoThinker-Statuszeile: die tickende Dauer -------------------------
  //
  // Karte CoThinker-Statuszeile (03.10.2026): der Server schreibt nie eine
  // Sekundenzahl ins HTML (siehe ``web._cothinker_status_html``), nur
  // ``data-seit``/``data-tickt`` als Attribute -- sonst saehe ``ladeBuehne``
  // oben bei jedem Poll einen neuen HTML-String und tauschte das Panel
  // unnoetig aus. EIN globaler Takt fuers ganze Dokument, nicht je
  // ``ladeBuehne()``-Lauf neu registriert (das liefe sonst nach jedem
  // Panel-Tausch als zusaetzlicher, nie wieder geloeschter Timer weiter).
  function formatiereDauer(sekunden) {
    sekunden = Math.max(0, Math.floor(sekunden));
    var min = Math.floor(sekunden / 60);
    var sek = sekunden % 60;
    return min + ':' + String(sek).padStart(2, '0');
  }
  function tickeCothinkerStatus() {
    document.querySelectorAll('.co-dauer[data-tickt="1"]').forEach(function (el) {
      var zeile = el.closest('#cothinker-status');
      if (!zeile) { return; }
      var seit = zeile.getAttribute('data-seit');
      if (!seit) { return; }
      var start = new Date(seit).getTime();
      if (isNaN(start)) { return; }
      var sek = (Date.now() - start) / 1000;
      el.textContent = ' · ' + formatiereDauer(sek);
    });
  }
  setInterval(tickeCothinkerStatus, 1000);
  zeige(lies());
})();
"""

#: Padua-Stepper (BINDING ADDITION, Birk 03.10.2026 23:10): bewusst eine
#: EIGENE, abgeschlossene IIFE statt eines zusaetzlichen Listeners innerhalb
#: von ``_VEREINT_JS`` -- ``_VEREINT_JS`` ist bei JEDEM Profil im Skript,
#: Dortmund eingeschlossen (``tests/test_web_vereint_bitgleich.py``
#: vergleicht Byte fuer Byte), und selbst ein zur Laufzeit nie treffender
#: Selektor haette als TEXT trotzdem in Dortmunds ``<script>`` gestanden.
#: ``sendePhase``/``friskeNonce``/``zeigeFehler`` aus ``_VEREINT_JS``
#: liegen in DEREN eigenem Funktionsrumpf (Closure) und sind von aussen
#: nicht erreichbar -- diese Funktionen stehen deshalb hier noch einmal,
#: kleiner (kein zweiter Wiederholungszaehler noetig, ``ladeStepper``
#: braucht keine ``.open``/``data-sicher``-Pflege, die es im
#: Stepper-Markup gar nicht gibt). Angehaengt wird dieser Block NUR, wenn
#: ``web.phasennav_stepper`` an ist (siehe ``seite()``) -- der erste
#: Zeile prueft trotzdem zusaetzlich zur Laufzeit, ob das Markup wirklich
#: da ist, als zweite, billige Absicherung.
_STEPPER_JS = """
(function () {
  if (!document.querySelector('.phasenav')) { return; }
  var BASIS = '__BASIS__';
  var BASIS_TEIL = '__BASIS_TEIL__';

  function friskeNonce() {
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
    feld.textContent = satz || __SHEET_FEHLER_NETZ__;
    feld.hidden = false;
    if (fehlerTakt) { clearTimeout(fehlerTakt); }
    fehlerTakt = setTimeout(function () { feld.hidden = true; feld.textContent = ''; }, 8000);
  }
  function ladeStepper() {
    fetch(BASIS_TEIL + 'roadmap', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (text) {
        if (!text) { return; }
        var doc = new DOMParser().parseFromString(text, 'text/html');
        var frisch = doc.body ? doc.body.firstElementChild : null;
        var ziel = document.getElementById('roadmap');
        if (frisch && ziel) { ziel.outerHTML = frisch.outerHTML; }
      })
      .catch(function () {});
  }

  var sheetOffenFuer = null;
  function zeigeHinweisEinmal() {
    var hinweis = document.getElementById('stepper-hinweis');
    if (!hinweis) { return; }
    try {
      if (localStorage.getItem('it_stepper_hinweis_gesehen')) { return; }
    } catch (e) { return; }
    hinweis.hidden = false;
  }
  zeigeHinweisEinmal();
  function verbergeHinweis() {
    var hinweis = document.getElementById('stepper-hinweis');
    if (hinweis) { hinweis.hidden = true; }
    try { localStorage.setItem('it_stepper_hinweis_gesehen', '1'); } catch (e) {}
  }
  // Oeffnen: Tap auf ein Segment ODER einen der Pfeile.
  function oeffneSheet(quelle) {
    var sheet = document.getElementById('phasensheet');
    if (!sheet || !quelle) { return; }
    sheetOffenFuer = quelle;
    document.getElementById('phasensheet-titel').textContent = quelle.dataset.bezeichnung || '';
    document.getElementById('phasensheet-satz').textContent = quelle.dataset.satz || '';
    var bereit = quelle.dataset.bereit !== '0';
    document.getElementById('phasensheet-status').textContent = bereit
      ? __SHEET_STATUS_BEREIT__
      : __SHEET_STATUS_OFFEN__.replace('{was}', quelle.dataset.fehlt || '');
    document.getElementById('phasensheet-los').textContent =
      __SHEET_GEHE_ZU__.replace('{bezeichnung}', quelle.dataset.bezeichnung || '');
    sheet.hidden = false;
    verbergeHinweis();
  }
  // Schliessen auf drei Wegen (Birk, Nachtrag): "Hier bleiben", Tap auf
  // den abgedunkelten Hintergrund, und -- in oeffneSheet()s Aufrufer
  // unten -- nach einem erfolgreichen "Weiter zu".
  function schliesseSheet() {
    var sheet = document.getElementById('phasensheet');
    if (sheet) { sheet.hidden = true; }
    sheetOffenFuer = null;
  }
  document.addEventListener('click', function (ev) {
    var segment = ev.target.closest ? ev.target.closest('.stepper-segment') : null;
    if (segment && segment.dataset.phase) { oeffneSheet(segment); return; }
    var pfeilKnopf = ev.target.closest
      ? ev.target.closest('.phasenav-zurueck, .phasenav-vor') : null;
    if (pfeilKnopf && pfeilKnopf.tagName === 'BUTTON') { oeffneSheet(pfeilKnopf); return; }
    if (ev.target.closest && ev.target.closest('#phasensheet-bleib')) {
      schliesseSheet(); return;
    }
    if (ev.target.closest && ev.target.closest('.sheet-hintergrund')) {
      schliesseSheet(); return;
    }
    var los = ev.target.closest ? ev.target.closest('#phasensheet-los') : null;
    if (los && sheetOffenFuer) {
      var phase = sheetOffenFuer;
      los.disabled = true;
      sendePhase(phase).then(function (r) {
        los.disabled = false;
        if (r && r.ok) {
          schliesseSheet();
          ladeStepper();
          return;
        }
        if (r) {
          r.text().then(function (satz) { zeigeFehler((satz || '').trim()); },
                       function () { zeigeFehler(''); });
        } else {
          zeigeFehler('');
        }
      }).catch(function () { los.disabled = false; zeigeFehler(''); });
    }
  });
})();
"""


#: Die Auswahlliste im CoThinker (Padua Phase 2, 05.10.2026): eine eigene,
#: nur unter ``workshop.diskussion_aktiv()`` angehaengte IIFE -- wie
#: ``_STEPPER_JS``, damit Dortmunds Skript Zeichen fuer Zeichen bleibt.
#: Ein Tipp setzt sofort ``data-zustand``/``aria-pressed`` und den Zaehler
#: (optimistisch), schickt ``chat/auswahl`` und holt danach das Panel neu.
#: Ein Tipp auf den schon gedrueckten Knopf schickt ``""`` (Rueckgaengig).
#: Tauscht ``ladeBuehne`` (``_VEREINT_JS``) das Panel, waehrend ein Tipp
#: unterwegs ist, setzt ein ``MutationObserver`` die offenen Tipps wieder
#: auf -- der Takt ueberschreibt nichts, was noch nicht angekommen ist.
#: Keine Textliterale: Zaehlerzeile und Fehlersatz kommen als Platzhalter.
_AUSWAHL_JS = """
(function () {
  var BASIS = '__BASIS__';
  var BASIS_TEIL = '__BASIS_TEIL__';
  var ZAEHLER = __AUSWAHL_ZAEHLER__;
  var FEHLER_NETZ = __AUSWAHL_FEHLER_NETZ__;
  var FEHLER_UNGUELTIG = __AUSWAHL_FEHLER_UNGUELTIG__;
  var TAKT = window.buehneTakt || { gen: 0, unterwegs: 0, gesehen: function () {} };
  var unterwegs = {};
  var anzahlUnterwegs = 0;

  function friskeNonce() {
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
  function sende(weg, nutzlast, zweiter) {
    var koerper = { nonce: (document.getElementById('nonce') || {}).value || '' };
    Object.keys(nutzlast).forEach(function (k) { koerper[k] = nutzlast[k]; });
    return fetch(BASIS + weg, {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(koerper)
    }).then(function (r) {
      if (r.status === 403 && !zweiter) {
        return friskeNonce().then(function () { return sende(weg, nutzlast, true); });
      }
      return r;
    });
  }
  var fehlerTakt = null;
  function zeigeFehler(text) {
    var feld = document.getElementById('fehler');
    if (!feld) { return; }
    feld.textContent = text || FEHLER_NETZ;
    feld.hidden = false;
    if (fehlerTakt) { clearTimeout(fehlerTakt); }
    fehlerTakt = setTimeout(function () { feld.hidden = true; feld.textContent = ''; }, 8000);
  }
  function zaehle(panel) {
    var feld = panel.querySelector('.auswahl-zaehler');
    if (!feld) { return; }
    var n = { ja: 0, nein: 0, schaerfen: 0, offen: 0 };
    panel.querySelectorAll('ul.auswahl li[data-nummer]').forEach(function (li) {
      var z = li.getAttribute('data-zustand');
      n[n.hasOwnProperty(z) ? z : 'offen'] += 1;
    });
    feld.textContent = ZAEHLER.replace(/\\{(ja|nein|schaerfen|offen)\\}/g,
      function (_g, k) { return String(n[k]); });
  }
  function setze(li, wert) {
    li.setAttribute('data-zustand', wert || 'offen');
    li.querySelectorAll('.auswahl-knopf').forEach(function (k) {
      k.setAttribute('aria-pressed', k.getAttribute('data-wert') === wert ? 'true' : 'false');
    });
  }
  function wendeUnterwegsAn() {
    var panel = document.getElementById('buehne-panel');
    if (!panel || panel.getAttribute('data-ansicht') !== 'auswahl') { return; }
    Object.keys(unterwegs).forEach(function (nummer) {
      var li = panel.querySelector('li[data-nummer="' + nummer + '"]');
      if (li && li.getAttribute('data-zustand') !== (unterwegs[nummer] || 'offen')) {
        setze(li, unterwegs[nummer]);
      }
    });
    zaehle(panel);
  }
  function holePanel() {
    var tab = document.getElementById('tab-buehne');
    if (!tab) { return; }
    var gen = TAKT.gen;
    fetch(BASIS_TEIL + 'buehne', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (text) {
        if (text === null || anzahlUnterwegs > 0 || TAKT.gen !== gen) { return; }
        var doc = new DOMParser().parseFromString(text, 'text/html');
        if (!doc.body) { return; }
        TAKT.gesehen(doc.body.innerHTML);
        if (doc.body.innerHTML !== tab.innerHTML) {
          tab.innerHTML = doc.body.innerHTML;
        }
      })
      .catch(function () {});
  }
  var tab = document.getElementById('tab-buehne');
  if (tab && window.MutationObserver) {
    new MutationObserver(function () {
      if (anzahlUnterwegs > 0) { wendeUnterwegsAn(); }
    }).observe(tab, { childList: true });
  }
  document.addEventListener('click', function (ev) {
    var ziel = ev.target && ev.target.closest ? ev.target : null;
    if (!ziel) { return; }
    var knopf = ziel.closest('#buehne-panel[data-ansicht="auswahl"] .auswahl-knopf');
    if (knopf) {
      ev.preventDefault();
      var panel = knopf.closest('#buehne-panel');
      var li = knopf.closest('li[data-nummer]');
      if (!li) { return; }
      var nummer = parseInt(li.getAttribute('data-nummer'), 10);
      var wert = knopf.getAttribute('aria-pressed') === 'true'
        ? '' : knopf.getAttribute('data-wert');
      setze(li, wert);
      zaehle(panel);
      unterwegs[nummer] = wert;
      anzahlUnterwegs += 1;
      TAKT.unterwegs = anzahlUnterwegs;
      sende('chat/auswahl', { liste: panel.getAttribute('data-liste'), nummer: nummer, wert: wert })
        .then(function (r) {
          if (!r.ok) { zeigeFehler(r.status === 400 ? FEHLER_UNGUELTIG : ''); }
          else if (wert === 'schaerfen' && document.querySelector('.tabs button[data-tab="chat"]')) {
            location.hash = '#chat';
          }
        })
        .catch(function () { zeigeFehler(); })
        .then(function () {
          anzahlUnterwegs -= 1;
          TAKT.unterwegs = anzahlUnterwegs;
          TAKT.gen += 1;
          if (unterwegs[nummer] === wert) { delete unterwegs[nummer]; }
          if (anzahlUnterwegs === 0) { holePanel(); }
        });
      return;
    }
    var fertig = ziel.closest('#buehne-panel[data-ansicht="auswahl"] .auswahl-fertig');
    if (fertig) {
      ev.preventDefault();
      if (fertig.disabled) { return; }
      fertig.disabled = true;
      var liste = fertig.closest('#buehne-panel').getAttribute('data-liste');
      sende('chat/auswahl_fertig', { liste: liste })
        .then(function (r) {
          fertig.disabled = false;
          if (!r.ok) { zeigeFehler(); return; }
          if (document.querySelector('.tabs button[data-tab="chat"]')) {
            location.hash = '#chat';
          }
        })
        .catch(function () { fertig.disabled = false; zeigeFehler(); });
    }
  });
})();
"""


def _tabs_html(aktiv: str, tabs=TABS, phase4: bool = True) -> str:
    """``phase4=False`` haengt ein ``hidden`` an den CoThinker-Knopf, damit
    die Seite schon beim ersten Rendern (vor jedem Poll-Takt) stimmt --
    derselbe Zustand, den ``_VEREINT_JS`` danach bei jedem Takt aus
    ``#roadmap``s ``data-aktive-phase`` neu herstellt."""
    knoepfe = "".join(
        f'<button type="button" role="tab" data-tab="{tab}" '
        f'aria-selected="{"true" if tab == aktiv else "false"}"'
        f'{" hidden" if tab == "buehne" and not phase4 else ""}>'
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
#: Padua-Stepper (BINDING ADDITION, Birk 03.10.2026 23:10): das
#: Bottom-Sheet je angetippter Phase. Deutsch bleibt die Vorgabe fuer
#: ``sprache.Texte``, auch wenn dieser Zweig nur unter dem Padua/
#: Englisch-Profil je gerendert wird -- siehe die englischen Eintraege in
#: ``sprachen/en/texte.toml``.
_TEXT_SHEET_STATUS_OFFEN = "Noch offen: {was}"
_TEXT_SHEET_STATUS_BEREIT = "Bereit"
_TEXT_SHEET_GEHE_ZU = "Weiter zu {bezeichnung}"
_TEXT_SHEET_BLEIBE = "Hier bleiben"
_TEXT_STEPPER_HINWEIS = "Auf eine Phase tippen, um zu wechseln."
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


_TEXT_AUSWAHL_UNGUELTIG = "Diese Auswahl geht nicht."
#: Welche Liste ein Tipp in der Auswahlliste schreibt (Padua Phase 2,
#: 05.10.2026): Listenname -> Name der ``repo``-Funktion
#: ``(conn, chat_id, nummer, wert) -> bool``. Als Name, nicht als Objekt:
#: ``repo`` wird hier wie ueberall in diesem Modul erst im Aufruf geladen.
_AUSWAHL_SCHREIBER = {"fragen": "setze_fragen_entscheidung"}
#: Die erlaubten Werte eines Tipps -- ``""`` ist "wieder offen" (Rueckgaengig).
_AUSWAHL_WERTE = ("ja", "nein", "schaerfen", "")


def auswahl_post(handler, db_pfad: str, token: str, chat_id: int,
                 schluessel: bytes) -> None:
    """``POST /g/<token>/chat/auswahl`` -- ein Tipp auf ✓/✗/✎ in der
    Auswahlliste des CoThinkers. Anders als der Phasenklick schreibt der
    Webserver hier SELBST: es ist ein Feldwert wie ``web_schreiben``, kein
    Knopf ``k:<id>`` und kein Modellaufruf. Nonce zuerst (403), dann Wert
    (400); ``False`` aus dem Schreiber (Nummer ausserhalb der Liste) ist
    ebenfalls 400.

    Stift ✎ (``wert == "schaerfen"``, Karte t_269062e2, 06.10.2026): unter
    Padua (``workshop.diskussion_aktiv()``, derselbe Schalter wie die
    Klickliste selbst) legt der Webserver zusaetzlich den versteckten
    Befehl ``/schaerfen N`` an -- wie ``auswahl_fertig_post`` den Befehl
    ``/sortiert``. Nicht beim Rueckgaengig-Tipp (``wert == ""``): nur das
    SETZEN von "schaerfen" ist eine Uebergabe in den Chat, das Loeschen
    sendet nichts."""
    from interview_theater import repo, web_chat, workshop

    daten = web_chat._koerper_oder_400(handler, token, schluessel)
    if daten is None:
        return
    schreiber = _AUSWAHL_SCHREIBER.get(daten.get("liste"))
    nummer = daten.get("nummer")
    wert = daten.get("wert")
    if (schreiber is None or not isinstance(nummer, int) or isinstance(nummer, bool)
            or nummer < 1 or not isinstance(wert, str) or wert not in _AUSWAHL_WERTE):
        handler._fehler(400, T._TEXT_AUSWAHL_UNGUELTIG)
        return
    with web_chat.schreibend(db_pfad) as conn:
        geschrieben = getattr(repo, schreiber)(conn, chat_id, nummer, wert)
        if geschrieben and wert == "schaerfen" and workshop.diskussion_aktiv():
            repo.lege_web_post_an(
                conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_BEFEHL,
                text=f"/schaerfen {nummer}",
            )
    if not geschrieben:
        handler._fehler(400, T._TEXT_AUSWAHL_UNGUELTIG)
        return
    handler._antworte(
        200, json.dumps({"ok": True}), "application/json; charset=utf-8",
    )


def auswahl_fertig_post(handler, db_pfad: str, token: str, chat_id: int,
                        schluessel: bytes) -> None:
    """``POST /g/<token>/chat/auswahl_fertig`` -- "Fertig sortiert". Wie
    ``phase_post``: der Webserver legt nur den versteckten Befehl
    ``/sortiert`` als Eingang ab, der Bot schliesst die Sortierung ab
    (offene zaehlen als behalten, dann ggf. Umformulieren im Chat)."""
    from interview_theater import repo, web_chat

    daten = web_chat._koerper_oder_400(handler, token, schluessel)
    if daten is None:
        return
    if daten.get("liste") not in _AUSWAHL_SCHREIBER:
        handler._fehler(400, T._TEXT_AUSWAHL_UNGUELTIG)
        return
    with web_chat.schreibend(db_pfad) as conn:
        message_id = repo.lege_web_post_an(
            conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_BEFEHL,
            text="/sortiert",
        )
    web_chat._angenommen(handler, {"message_id": message_id})


def start_post(handler, db_pfad: str, token: str, chat_id: int,
               schluessel: bytes) -> None:
    """``POST /g/<token>/chat/start`` -- der erste Seitenaufruf einer
    frischen Web-Gruppe (Pflichtpunkt 2, Fix 1 von 2, 04.10.2026). Legt
    ``/start`` nur an, solange der Chat noch leer ist
    (``repo.hat_bot_nachricht``) -- das macht den zweiten Aufruf
    wirkungslos, ohne dass der Bot zur Pruefzeit laufen muss."""
    from interview_theater import repo, web_chat

    if web_chat._koerper_oder_400(handler, token, schluessel) is None:
        return
    message_id = None
    with web_chat.schreibend(db_pfad) as conn:
        if not repo.hat_bot_nachricht(conn, chat_id):
            message_id = repo.lege_web_post_an(
                conn, chat_id, repo.RICHTUNG_EIN, repo.WEB_TYP_BEFEHL,
                text="/start",
            )
    web_chat._angenommen(handler, {"message_id": message_id})


def _board_merkmal() -> str:
    """``data-begriffsboard="1"`` am ``#roadmap``, wenn das Profil das
    Begriffsboard faehrt (Karte t_4517d4ad) -- HINTER ``data-aktive-phase``,
    damit ``tests/test_web_vereint.py`` dessen Regex unveraendert findet.
    Ohne Profil: nichts, Dortmund bleibt byte-gleich."""
    from interview_theater import workshop

    return ' data-begriffsboard="1"' if workshop.diskussion_aktiv() else ""


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
    docs/agents/weboberflaeche.md "Abschlussreview I3"), ein Knopf waere also toter Code auf der
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
        # ``data-aktive-phase`` (Birk 02.10.2026, Bühne-Root-Cause-Fix): die
        # Phase steht hier schon serverseitig fest -- das JS liest sie bei
        # jedem Roadmap-Takt, um den CoThinker-Tab (Button + Panel) ein-
        # und auszublenden, OHNE auf ein volles Neuladen zu warten.
        f'<details class="roadmap" id="roadmap" data-aktive-phase="{aktiv["nummer"]}"'
        f'{_board_merkmal()}>'
        f'<summary><span class="roadmap-kopf">{html.escape(kopf)}</span></summary>'
        f'<ol class="phasen">{"".join(zeilen)}</ol>'
        f'</details>\n'
    )


def _stepper_html(roadmapdaten: list[dict], klickbar: bool = True) -> str:
    """Padua-Stepper (BINDING ADDITION, Birk 03.10.2026 23:10): sieben
    nummerierte Segmente statt eines zugeklappten ``<details>``, Pfeile
    links/rechts der aktiven Phase, ein Tap oeffnet das Bottom-Sheet statt
    der Zwei-Klick-Bewaffnung aus ``_leiste_html``. Nur gerendert, wenn
    ``workshop.aktiv().wert("web.phasennav_stepper")`` wahr ist -- der
    Aufrufer (``seite()``) entscheidet, ``_leiste_html`` bleibt fuer
    Dortmund vollstaendig unangetastet.

    ``id="roadmap"`` und ``data-aktive-phase`` bleiben wie bei
    ``_leiste_html``: ``_VEREINT_JS``s ``istPhase4()`` und
    ``ladeRoadmap()``s ``/teil/roadmap``-Tausch zielen beide auf
    ``#roadmap`` -- derselbe Anker traegt beide Markup-Formen, ohne dass
    die Tausch-Logik wissen muss, welche gerade steht (ein ``<header>``
    hat kein ``.open``, das Zuruecksetzen von ``neues.open`` danach ist
    dort ein wirkungsloses, aber ungefaehrliches No-Op)."""
    if not roadmapdaten:
        return ""
    aktiv = next((p for p in roadmapdaten if p["aktiv"]), roadmapdaten[0])
    idx = roadmapdaten.index(aktiv)
    vorherige = roadmapdaten[idx - 1] if idx > 0 else None
    naechste = roadmapdaten[idx + 1] if idx + 1 < len(roadmapdaten) else None

    segmente = []
    for phase in roadmapdaten:
        zustand = (
            "erledigt" if phase["nummer"] < aktiv["nummer"]
            else "aktiv" if phase["nummer"] == aktiv["nummer"]
            else "kommend"
        )
        marke = "✓" if zustand == "erledigt" else str(phase["nummer"])
        if klickbar:
            fehlt_text = ", ".join(phase.get("fehlt") or ())
            segmente.append(
                f'<li class="stepper-segment {zustand}" data-phase="{phase["nummer"]}" '
                f'data-bezeichnung="{html.escape(phase["bezeichnung"], quote=True)}" '
                f'data-satz="{html.escape(phase.get("satz") or "", quote=True)}" '
                f'data-bereit="{"0" if phase.get("bereit") is False else "1"}" '
                f'data-fehlt="{html.escape(fehlt_text, quote=True)}" '
                f'role="button" tabindex="0" '
                f'aria-label="{html.escape(phase["bezeichnung"], quote=True)}">'
                f'<span class="stepper-marke">{marke}</span></li>'
            )
        else:
            segmente.append(
                f'<li class="stepper-segment {zustand}">'
                f'<span class="stepper-marke">{marke}</span></li>'
            )

    def pfeil(ziel, richtung, css_klasse):
        if ziel is None:
            return f'<span class="{css_klasse}" aria-hidden="true"></span>'
        pfeilzeichen = "‹ " if richtung == -1 else " ›"
        text = (f"{pfeilzeichen}{html.escape(ziel['name'])}" if richtung == -1
                else f"{html.escape(ziel['name'])}{pfeilzeichen}")
        if not klickbar:
            return f'<span class="{css_klasse}">{text}</span>'
        fehlt_text = ", ".join(ziel.get("fehlt") or ())
        return (
            f'<button type="button" class="{css_klasse}" '
            f'data-phase="{ziel["nummer"]}" '
            f'data-bezeichnung="{html.escape(ziel["bezeichnung"], quote=True)}" '
            f'data-satz="{html.escape(ziel.get("satz") or "", quote=True)}" '
            f'data-bereit="{"0" if ziel.get("bereit") is False else "1"}" '
            f'data-fehlt="{html.escape(fehlt_text, quote=True)}">'
            f'{text}</button>'
        )

    if klickbar:
        sheet = (
            '<div class="sheet" id="phasensheet" hidden role="dialog" '
            'aria-modal="true" aria-labelledby="phasensheet-titel">'
            '<div class="sheet-hintergrund"></div>'
            '<div class="sheet-inhalt">'
            '<h3 id="phasensheet-titel"></h3>'
            '<p id="phasensheet-satz"></p>'
            '<p id="phasensheet-status"></p>'
            '<div class="sheet-knoepfe">'
            '<button type="button" id="phasensheet-los"></button>'
            f'<button type="button" id="phasensheet-bleib">'
            f'{html.escape(T._TEXT_SHEET_BLEIBE)}</button>'
            '</div></div></div>'
        )
        hinweis = (
            f'<p class="stepper-hinweis" id="stepper-hinweis" hidden>'
            f'{html.escape(T._TEXT_STEPPER_HINWEIS)}</p>'
        )
    else:
        sheet = ""
        hinweis = ""

    return (
        f'<header class="phasenav" id="roadmap" data-stepper="1" '
        f'data-aktive-phase="{aktiv["nummer"]}"'
        # Bug (Birk Live-Test 04.10.2026): der Stepper ist der ZWEITE
        # Renderer von #roadmap (siehe _leiste_html oben) -- der haengt
        # _board_merkmal() schon an, dieser hier tat es nicht. Ohne das
        # Attribut findet istCoThinkerPhase() (_VEREINT_JS) in Phase 1
        # kein data-begriffsboard und versteckt den CoThinker-Tab, egal
        # ob das Profil das Begriffsboard faehrt.
        f'{_board_merkmal()}>'
        f'<ol class="stepper" role="list">{"".join(segmente)}</ol>'
        f'<div class="phasenav-zeile">'
        f'{pfeil(vorherige, -1, "phasenav-zurueck")}'
        f'<span class="phasenav-aktuell">{html.escape(aktiv["bezeichnung"])}</span>'
        f'{pfeil(naechste, 1, "phasenav-vor")}'
        f'</div>'
        f'<p id="ux-naechstes" hidden></p>'
        f'{hinweis}'
        f'</header>\n{sheet}'
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
    Web-Kanal, docs/agents/weboberflaeche.md "Abschlussreview I3"): das Chat-Panel samt seinem
    Tab und Skript (``eingabe``, ``interview``, ``ptt``, ``web_chat._js()``)
    faellt dann ganz weg -- ein POST oder Poll dorthin wuerde ohnehin 404
    liefern (``web_chat._gruppe_oder_404`` prueft denselben Web-Kanal), und
    was die Gruppe dort eintippen wuerde, ginge spurlos verloren. Start-Tab
    ist dann ``stand``; ein Fragment ``#chat`` faellt automatisch darauf
    zurueck, weil ``TABS`` im Skript ohne ``chat`` ankommt und ``lies()`` in
    ``_VEREINT_JS`` jedes unbekannte Wort auf ``VORGABE`` abbildet."""
    from interview_theater import web, web_chat, web_gestalt
    from interview_theater import workshop

    # Padua (03.10.2026, read-only Werkbank): ohne Formulare traegt das
    # Stand-Panel auch kein ``id="nonce"``-Feld mehr -- dann steht es im Chat.
    werkbank_bearbeitbar = workshop.workbench_bearbeitbar()

    stepper_aktiv = workshop.aktiv().wert("web.phasennav_stepper", False)
    titel = daten["titel"] or f"Gruppe {daten['chat_id']}"
    tabs = TABS if chat_vorhanden else tuple(t for t in TABS if t != "chat")
    # CoThinker-Root-Cause-Fix (Birk 02.10.2026): der Tab steht JETZT IMMER
    # im Dokument -- vorher nur bei ``phase4`` serverseitig gerendert, so
    # dass eine Gruppe, die WAEHREND die Seite offen ist in Phase 4 eintritt
    # (Chat, Phasenleiste, "Ja speichern"), den Tab nie bekam, bis jemand von
    # Hand neu laedt (derselbe Fehler umgekehrt beim Verlassen von Phase 4).
    # Sichtbarkeit kommt jetzt allein aus ``hidden`` (siehe unten) und wird
    # von ``_VEREINT_JS`` bei jedem Roadmap-Takt aus ``#roadmap``s
    # ``data-aktive-phase`` neu gesetzt -- kein Tab-Wechsel von Serverseite,
    # kein Neuladen noetig. Eine Telegram-Gruppe (kein Web-Kanal) bekommt den
    # Tab ebenso: die Buehne haengt an der Phase, nicht am Kanal (wie bisher).
    tabs = tabs + ("buehne",)
    phase = (daten.get("arbeitsstand") or {}).get("phase")
    # Der CoThinker-Tab ist sichtbar in Phase 4 -- und in Phase 1, wenn das
    # Profil das Begriffsboard faehrt (Karte t_4517d4ad). Derselbe Zustand,
    # den ``istCoThinkerPhase()`` im Browser bei jedem Takt neu herstellt.
    # Seit 05.10.2026 (Birk) auch Phase 2: die Fragenuebersicht je Begriff.
    phase4 = phase == 4 or (phase in (1, 2) and workshop.diskussion_aktiv())
    vorgabe = VORGABE_TAB if chat_vorhanden else "stand"
    panels = {
        "stand": web.gruppe_koerper(daten, nonce_wert, token, praefix, fassungswahl),
        "textbuch": web.textbuch_koerper(daten, token, praefix),
        # Immer gebaut, nicht nur in Phase 4 (s.o.) -- leer bleibt es nicht
        # teurer als vorher: ``_buehne_html`` liest nur, was ``daten``
        # ohnehin schon traegt (``buehnenkarten``/``stueckkarte_felder``).
        "buehne": web._buehne_html(daten),
    }
    if chat_vorhanden:
        # ``mit_nonce=False``: das Stand-Panel traegt sein ``id="nonce"``
        # schon (``_bearbeiten_html``), mit demselben Wert -- ein zweites
        # Element mit derselben id waere ungueltiges HTML. In Padua
        # (read-only Werkbank) steht es nur hier.
        # ``mit_gruppenlink=False`` (Fix-Runde 1): der Link fuehrt sonst auf
        # die Seite, auf der er selbst steht (``/g/<token>`` -> ``<token>``).
        panels["chat"] = web_chat.chat_koerper(
            chatdaten, nonce_wert, token, segment_ms,
            basis=f"{token}/", mit_nonce=not werkbank_bearbeitbar,
            mit_gruppenlink=False,
        )
    kopf_html = (
        _stepper_html(roadmapdaten, klickbar=chat_vorhanden)
        if stepper_aktiv
        else _leiste_html(roadmapdaten, klickbar=chat_vorhanden)
    )
    koerper = [kopf_html, _tabs_html(vorgabe, tabs, phase4=phase4)]
    for tab in tabs:
        # ``data-textbuch`` ist die Wurzel, an der ``_TEXTBUCH_JS`` seinen
        # Zustand ablegt: im gemeinsamen Dokument darf der Rollenfilter nicht
        # am ``<body>`` haengen, sonst faerbte er auch den Chat.
        zusatz = ' data-textbuch=""' if tab == "textbuch" else ""
        # Der Buehne-Tab ist zusaetzlich zur Tab-Logik ausserhalb Phase 4
        # IMMER verborgen -- ``vorgabe`` zeigt nie auf ihn (er steht nicht in
        # VORGABE_TAB-Kandidaten), diese zweite Bedingung verhindert nur,
        # dass ein veralteter ``vorgabe``-Wert (koennte nie "buehne" sein,
        # aber robust bleibt robust) ihn vorzeitig zeigt.
        verborgen = (
            " hidden" if tab == "buehne" and not phase4
            else "" if tab == vorgabe else " hidden"
        )
        koerper.append(
            f'<section class="panel panel-{tab}" id="tab-{tab}" role="tabpanel"'
            f'{zusatz}{verborgen}>\n{panels[tab]}\n</section>'
        )
    css = (
        _CSS_VEREINT
        + web.CSS_COTHINKER_KEYFRAMES
        + scope_css(web._CSS_GRUPPE, ".panel-stand")
        + scope_css(web._CSS_TEXTBUCH + web._CSS_TEXTBUCH_FASSUNGEN, ".panel-textbuch")
        + scope_css(web._CSS_BUEHNE, ".panel-buehne")
    )
    if chat_vorhanden:
        css += scope_css(web_chat._CSS_CHAT, ".panel-chat")
    # Gestaltung zuletzt (Karte UX): gleiche Spezifitaet, spaetere Position --
    # und dieselbe Einschraenkung wie die Quellen darueber, sonst waere
    # ``#interview`` schwaecher als ``.panel-chat #interview``.
    css += web_gestalt.css_rahmen()
    if chat_vorhanden:
        css += scope_css(web_gestalt.css_chat(), ".panel-chat")
        # P2, Aufgabe 2: der Interview-Modus -- ungescopt (er blendet auch
        # Phasenleiste und Tabs aus), aber nur, wo es einen Chat gibt.
        css += web_gestalt.css_interview()
    css += scope_css(web_gestalt.css_stand(), ".panel-stand")
    if not werkbank_bearbeitbar:
        css += scope_css(web_gestalt.css_werkbank(), ".panel-stand")
    css += scope_css(web_gestalt.css_buehne(), ".panel-buehne")
    css += scope_css(web_gestalt.css_textbuch(), ".panel-textbuch")
    # Mobile-App-Shell (03.10.2026) zuletzt von allem: sie gewinnt gegen
    # ``_TABS_A``/``_TABS_B``/``_CSS_CHAT`` per Spezifitaet oder Reihenfolge,
    # ohne eine Zeile davon anzufassen (siehe Docstring von ``_css_schale``).
    css += _css_schale(web_gestalt.entwurf())
    # Padua-Stepper: NICHT in css_rahmen() (das muesste fuer Dortmund
    # byte-gleich bleiben, siehe tests/test_web_vereint_bitgleich.py) --
    # eine eigene, nur hier bedingt angehaengte Funktion.
    if stepper_aktiv:
        css += web_gestalt.css_stepper()
    # web_chat._js() und nicht die rohe Konstante _CHAT_JS: sie traegt
    # unersetzte Platzhalter (__POLL_MS__ usw., siehe web_chat._js()-Docstring)
    # -- nur _js() liefert lauffaehiges Skript (Abweichung vom Plan-Kopf-
    # Beispiel, das die Konstante direkt anhaengt).
    skript = (
        # Zuerst: ohne dieses Skript faellt iOS Safari auf den
        # ``100dvh``-Fallback aus ``_css_schale`` zurueck, solange die
        # Tastatur offen ist -- sichtbar als derselbe Rutscher, den die
        # Karte beheben soll.
        _VH_JS
        + _VEREINT_JS.replace("__TABS__", json.dumps(list(tabs)))
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
    # Padua-Stepper (BINDING ADDITION): eine eigene, nur hier bedingt
    # angehaengte IIFE (siehe ``_STEPPER_JS``-Docstring-Kommentar) --
    # Dortmunds Skript bleibt dadurch Zeichen fuer Zeichen unberuehrt.
    if stepper_aktiv:
        skript += (
            _STEPPER_JS
            .replace("__BASIS__", f"{token}/")
            .replace("__BASIS_TEIL__", f"{token}/{TEIL_PFAD}/")
            .replace("__SHEET_FEHLER_NETZ__", _js_text(T._TEXT_PHASE_FEHLER_NETZ))
            .replace("__SHEET_STATUS_BEREIT__", _js_text(T._TEXT_SHEET_STATUS_BEREIT))
            .replace("__SHEET_STATUS_OFFEN__", _js_text(T._TEXT_SHEET_STATUS_OFFEN))
            .replace("__SHEET_GEHE_ZU__", _js_text(T._TEXT_SHEET_GEHE_ZU))
        )
    # Die Auswahlliste im CoThinker (Padua Phase 2): nur mit Chat (die
    # Wege liegen unter ``/chat/*``) und nur unter dem Profil -- Dortmunds
    # Skript bleibt unberuehrt, wie beim Stepper.
    if chat_vorhanden and workshop.diskussion_aktiv():
        skript += (
            _AUSWAHL_JS
            .replace("__BASIS__", f"{token}/")
            .replace("__BASIS_TEIL__", f"{token}/{TEIL_PFAD}/")
            .replace("__AUSWAHL_ZAEHLER__", _js_text(web.T._TEXT_AUSWAHL_ZAEHLER))
            .replace("__AUSWAHL_FEHLER_NETZ__", _js_text(T._TEXT_PHASE_FEHLER_NETZ))
            .replace("__AUSWAHL_FEHLER_UNGUELTIG__", _js_text(T._TEXT_AUSWAHL_UNGUELTIG))
        )
    # ``chat_vorhanden`` durchreichen (UX-Fix an Aufgabe 8): Baustein 3
    # (``_JS_AUFNAHME``) nennt Elemente, die nur im Chat-Panel existieren
    # (u.a. ``#warteschlange``) -- bei einer Telegram-Gruppe (kein Chat-
    # Panel, siehe ``tests/test_web_vereint.py::
    # test_telegram_gruppe_hat_kein_chat_panel``) darf dieser Marker nicht
    # einmal im Quelltext stehen.
    skript += web_gestalt.skript(chat_vorhanden=chat_vorhanden)  # Karte UX: Effekte, zuletzt
    return web._seite(
        f"{titel} — interview-theater", css, "\n".join(koerper),
        bearbeitbar=werkbank_bearbeitbar, nachladen=False, skript=skript,
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
    dieser Ausschnitt gar nicht braucht.

    Padua-Stepper: dieselbe Weiche wie in ``seite()`` -- der Tausch bei
    ``ladeRoadmap()`` muss dieselbe Markup-Form liefern, die beim ersten
    Laden schon stand, sonst ersetzt ein Stepper sich selbst durch ein
    ``<details>`` oder umgekehrt."""
    from interview_theater import workshop

    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        daten = web_daten.gruppe_nach_token(conn, token)
        if daten is None:
            return None
        chat_vorhanden = web_daten.web_chat_id_nach_token(conn, token) is not None
        roadmapdaten = web_daten.roadmap(conn, daten["chat_id"])
    finally:
        conn.close()
    if workshop.aktiv().wert("web.phasennav_stepper", False):
        return _stepper_html(roadmapdaten, klickbar=chat_vorhanden)
    return _leiste_html(roadmapdaten, klickbar=chat_vorhanden)


def sende_teil(handler, db_pfad: str, token: str, name: str, praefix: str,
              schluessel: bytes, query: str) -> None:
    """``GET /g/<token>/teil/<stand|roadmap|buehne>`` -- nur der Rumpf eines
    Ausschnitts.

    Der Ersatz fuer das sanfte Nachladen der Einzelseite: dort tauscht
    ``web._SCROLL_JS`` den ganzen ``<body>``, hier nur dieser eine
    Ausschnitt. Alles andere -- Chat, Aufnahme, Strom, halb getipptes Feld --
    bleibt stehen.

    ``stand`` traegt den frischen Nonce mit, wie beim sanften Nachladen: er
    steht IM Rumpf (``web.nonce``), nicht daran. ``roadmap`` (Fix-Runde 1)
    hat keinen eigenen Nonce -- sie braucht keinen, siehe ``_leiste_html``.
    ``buehne`` (02.10.2026, Birk) ebenso: reines Lesen, kein Formular."""
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
    if name == "buehne":
        handler._antworte(200, web._buehne_html(daten))
        return
    if name == "textbuch":
        # Reines Lesen, kein Formular, kein Nonce (P57 Lauf 2, A1).
        handler._antworte(200, web.textbuch_koerper(daten, token, praefix))
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
