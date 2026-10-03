"""Die Gestaltung der Weboberflaeche: Tokens, Komponenten-CSS, Effekt-JS
(01.10.2026, Karte Padua UX).

**Warum ein eigenes Modul.** ``web.py``, ``web_chat.py`` (A2) und
``web_vereint.py`` (W) sind Hotspots -- an allen dreien arbeiten parallel
andere Karten. Gestaltung ist die einzige Schicht, die man vollstaendig
herausloesen kann: sie liest kein SQL, ruft kein Modell, kennt keinen
Endpunkt und aendert kein Markup. Eingehaengt wird sie an sieben Zeilen
(fuenf in ``web_vereint.seite`` -- Rahmen-CSS, drei gescopte Bloecke,
Effekt-JS --, je eine in ``web.textbuch_html`` und ``web.leitfaden_html``).

**Birks Richtung, woertlich:** "bisschen matrix style cool, unterhaltend,
technoisch, theater". Uebersetzt in vier Leitplanken -- Terminal (dunkler
Grund, Monospace, Phosphor als Signal, Text, der sich aufbaut), Theater
(sieben Akte statt sieben Phasen, Vorhang/Glitch am Wechsel, das Textbuch
als Manuskript gesetzt), unterhaltend (kleine Belohnungen, Humor in den
englischen Mikrotexten -- nie im Bot-Text), technoid (jeder Zustand
sichtbar: Pegel, Uhr, Cursor, Warteschlange). Die Begruendung je
Entscheidung steht in ``docs/ux-padua/BERICHT.md``.

**Zwei Entwuerfe, ein Satz Tokennamen.** ``docs/ux-padua/entwurf-a.html``
("Terminal zuerst") und ``entwurf-b.html`` ("Buehne zuerst") sind die
klickbaren Muster, an denen Birk entschieden hat. Umgesetzt ist der
gewaehlte; der andere ist ein Tausch von ``VORGABE_ENTWURF`` (oder
``IT_UX_ENTWURF``) -- alle Regeln unten lesen nur Tokennamen, und die vier
Komponenten-Abweichungen (Tab-Ort, Knopfform, Akt-Moment, Skript-Satz)
haengen an derselben Wahl.

**Drei harte Grenzen, die im Code stehen und nicht im Kommentar:**

1. **Kein Webfont.** Die CSP aus Karte S hat ``default-src 'none'`` und
   kein ``font-src``; ein ``@font-face`` waere geblockt, auch mit
   ``data:``-URL. Also System-Stacks (``--schrift-*``).
2. **Kein ``style="…"``-Attribut, kein ``on…=``-Handler.** Dynamische
   Werte gehen ueber CSSOM (``el.style.setProperty``), was unter
   ``style-src 'nonce-…'`` erlaubt ist -- ``setAttribute('style', …)``
   waere es nicht.
3. **``@keyframes`` und ``@media`` NUR in ``css_rahmen()``.** Die anderen
   drei CSS-Funktionen laufen beim Aufrufer durch
   ``web_vereint.scope_css``, und dessen Regex machte aus dem Rumpf eines
   ``@keyframes`` (``50% { … }``) eine gescopte Regel ``.panel-chat 50%``.

Oberflaechen-Schicht. Importiert **nichts** aus dem Projekt ausser
``sprache`` (A1) -- nicht ``web``, nicht ``web_vereint``, nicht
``web_chat``: die Richtung zeigt von dort hierher.
"""

import json
import os
import re
from typing import NamedTuple

from interview_theater import sprache

#: Die zwei Entwuerfe aus ``docs/ux-padua/``.
ENTWUERFE = ("a", "b")

#: Welcher gilt, solange die Umgebung nichts anderes sagt. Gesetzt in
#: Aufgabe 1 Schritt 5 aus ``docs/ux-padua/ENTWUERFE.md``.
VORGABE_ENTWURF = "b"

#: Die Umgebungsvariable, die umschaltet. Gelesen wird sie hier und nicht
#: in ``einstellungen.py``: das ist die Konfiguration des BOTS, und diese
#: Karte gehoert zum Webdienst, der seine Werte (``IT_DB``,
#: ``IT_WEB_BIND``) ebenfalls direkt aus ``os.environ`` liest.
UMGEBUNG = "IT_UX_ENTWURF"

#: Welche Tokens Farben sind -- der Kontrasttest rechnet nur mit diesen.
FARBTOKENS = frozenset({
    "grund", "grund-2", "grund-3", "linie", "rand",
    "text", "text-leise", "signal", "signal-tief", "auf-signal",
    "warn", "auf-warn", "rec", "auf-rec", "vorhang-1", "vorhang-2",
})

#: System-Schriftstacks. Kein Webfont (siehe Modulkopf).
_MONO = ('ui-monospace, "SFMono-Regular", Menlo, Consolas, '
         '"Liberation Mono", monospace')
_SERIF = 'ui-serif, Georgia, "Times New Roman", "Liberation Serif", serif'
_SANS = '-apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif'

#: DER Block, der einen Entwurf ausmacht. Gleiche Schluessel, andere Werte.
#:
#: Die Farbwerte sind nicht gegriffen: jedes Paar in ``KONTRAST`` unten ist
#: gerechnet, und ``tests/test_web_gestalt_tokens.py`` rechnet es bei jedem
#: Lauf nach. Zwei Werte weichen bewusst von den HTML-Entwuerfen ab, weil
#: die dort gewaehlten die 3:1-Grenze fuer Komponentenraender rissen:
#: ``rand`` gibt es in den Entwuerfen gar nicht (dort traegt ``linie``
#: beides), und ``b.rec`` ist von ``#8e1c22`` (2.12 : 1 auf dem Grund) auf
#: ``#c0362c`` (3.45 : 1) angehoben.
TOKENS: dict[str, dict[str, str]] = {
    # -- A: Terminal zuerst -- Phosphor auf Schwarzblau, Monospace als
    #    Grundschrift, Tableiste unten am Daumen, breite Aufnahmetaste.
    "a": {
        "grund": "#05070a",
        "grund-2": "#0c1116",
        "grund-3": "#131b22",
        "linie": "#23303a",
        "rand": "#54697a",
        "text": "#cfe3d6",
        "text-leise": "#8fa398",
        "signal": "#6ef7a5",
        "signal-tief": "#1b3a2a",
        "auf-signal": "#05070a",
        "warn": "#ffc857",
        "auf-warn": "#05070a",
        "rec": "#b3251f",
        "auf-rec": "#ffffff",
        "radius": ".35rem",
        "radius-gross": ".5rem",
        "tippflaeche": "2.75rem",
        "rec-hoehe": "4.25rem",
        "tabs-hoehe": "3.4rem",
        "schrift-lesen": _MONO,
        "schrift-tech": _MONO,
        "schrift-skript": _SERIF,
        "takt-schnell": "90ms",
        "takt-moment": "520ms",
        "vorhang-1": "#1b3a2a",   # A: unbenutzt, aber gesetzt
        "vorhang-2": "#0c1116",
    },
    # -- B: Buehne zuerst -- Amber auf Samtschwarz, Serife fuer alles
    #    Gelesene, Aktleiste und Tabs oben, runder Scheinwerferknopf.
    "b": {
        "grund": "#120f10",
        "grund-2": "#1c1719",
        "grund-3": "#262022",
        "linie": "#3a3134",
        "rand": "#75656a",
        "text": "#f0e6d8",
        "text-leise": "#a79c90",
        "signal": "#f0b24a",
        "signal-tief": "#3a2a13",
        "auf-signal": "#120f10",
        "warn": "#7fd6a0",
        "auf-warn": "#120f10",
        "rec": "#c0362c",
        "auf-rec": "#ffffff",
        "radius": ".7rem",
        "radius-gross": "1.1rem",
        "tippflaeche": "2.75rem",
        "rec-hoehe": "4.75rem",
        "tabs-hoehe": "0rem",
        "schrift-lesen": _SANS,
        "schrift-tech": _MONO,
        "schrift-skript": _SERIF,
        "takt-schnell": "90ms",
        "takt-moment": "560ms",
        "vorhang-1": "#2a0f14",   # B: der Samt des Vorhangs
        "vorhang-2": "#3a161c",
    },
}


class Paar(NamedTuple):
    """Ein Text/Grund-Paar mit seiner WCAG-Schwelle.

    ``mindest`` ist 4.5 fuer Fliesstext (AA) und 3.0 fuer grosse Schrift
    und fuer Grenzen von Bedienelementen (WCAG 1.4.11)."""

    vorn: str
    hinten: str
    zweck: str
    mindest: float


#: Jedes Paar, das die Gestaltung wirklich uebereinanderlegt. Wer eine
#: Farbkombination hinzufuegt, traegt sie HIER ein -- sonst prueft sie
#: niemand.
#:
#: ``--linie`` steht bewusst nicht darin: das ist die Haarlinie zwischen
#: zwei Listenzeilen, nicht die Grenze eines Bedienelements. Wo ein Rand
#: einen Zustand traegt, steht ``--rand``.
KONTRAST: tuple[Paar, ...] = (
    Paar("text", "grund", "Fliesstext auf dem Seitengrund", 4.5),
    Paar("text", "grund-2", "Fliesstext in Blase, Karte, Eingabefeld", 4.5),
    Paar("text", "grund-3", "Fliesstext auf gehobener Flaeche", 4.5),
    Paar("text", "signal-tief", "Text in der Blase der Gruppe", 4.5),
    Paar("text-leise", "grund", "Nebentext, Zeitangaben, Hinweise", 4.5),
    Paar("text-leise", "grund-2", "Nebentext in der Blase", 4.5),
    Paar("signal", "grund", "Signalfarbe als Text und Rahmen", 4.5),
    Paar("signal", "grund-2", "Signalfarbe in der Blase", 4.5),
    Paar("auf-signal", "signal", "Text auf gefuellter Signalflaeche", 4.5),
    Paar("warn", "grund", "laufender Zustand (Uhr, aktiver Akt)", 4.5),
    Paar("warn", "grund-2", "laufender Zustand in der Karte", 4.5),
    Paar("auf-warn", "warn", "Text auf gefuellter Warnflaeche", 4.5),
    Paar("auf-rec", "rec", "Text auf dem laufenden Aufnahmeknopf", 4.5),
    Paar("rec", "grund", "Rahmen des ruhenden Aufnahmeknopfes", 3.0),
    Paar("rand", "grund", "Grenze eines Bedienelements", 3.0),
    Paar("rand", "grund-2", "Grenze eines Bedienelements in der Karte", 3.0),
    Paar("signal", "grund-3", "gewaehlter Tab, gedrueckter Filter; Vorfallart als Text im Dashboard-Log", 4.5),
    Paar("warn", "grund-3", "pausierter Aufnahmeknopf", 4.5),
    Paar("text-leise", "grund-3", "Aufgabe der Aktfolge unter dem Finger", 4.5),
)


def entwurf() -> str:
    """Der aktive Entwurf: ``IT_UX_ENTWURF``, sonst ``VORGABE_ENTWURF``.

    Ein unbekannter Wert faellt auf die Vorgabe zurueck statt zu werfen:
    ein Tippfehler in einer Env-Datei soll am Workshoptag keine ungestylte
    Seite ergeben."""
    wert = (os.environ.get(UMGEBUNG) or "").strip().lower()
    return wert if wert in ENTWUERFE else VORGABE_ENTWURF


def tokens_css(name: str | None = None) -> str:
    """Der Tokenblock als ``:root``-Regel."""
    tokens = TOKENS[name or entwurf()]
    zeilen = "\n".join(f"  --{k}: {v};" for k, v in tokens.items())
    return ":root {\n" + zeilen + "\n}\n"


def _kanal(wert: float) -> float:
    """Ein sRGB-Kanal (0..1) linearisiert, WCAG 2.x."""
    return wert / 12.92 if wert <= 0.04045 else ((wert + 0.055) / 1.055) ** 2.4


def _leuchtdichte(farbe: str) -> float:
    roh = farbe.lstrip("#")
    r, g, b = (int(roh[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _kanal(r) + 0.7152 * _kanal(g) + 0.0722 * _kanal(b)


def kontrastverhaeltnis(vorderfarbe: str, hintergrund: str) -> float:
    """Das WCAG-Kontrastverhaeltnis zweier Hexfarben, 1.0 bis 21.0.

    Ausgerechnet und nicht geschaetzt: die Oberflaeche liegt auf einem
    Telefon in einem Probenraum, und "sieht dunkel genug aus" ist kein
    Mass."""
    eins, zwei = _leuchtdichte(vorderfarbe), _leuchtdichte(hintergrund)
    hell, dunkel = max(eins, zwei), min(eins, zwei)
    return (hell + 0.05) / (dunkel + 0.05)


# -- Mikrotexte der Oberflaeche ---------------------------------------------
#
# Die deutsche Fassung steht hier und IST die deutsche Tabelle (A1); die
# englische steht in ``sprachen/en/texte.toml``. Keiner dieser Texte geht
# in einen Prompt oder in eine Chatnachricht -- es sind Beschriftungen.
#
# Sachlich auf Deutsch, augenzwinkernd auf Englisch: "Mic is hot." ist ein
# Studiowitz und traegt dort; "Das Mikrofon ist heiss." waere in Dortmund
# Denglisch. Genau dafuer gibt es zwei Tabellen.

#: Die vier Zustaende des Aufnahmeknopfes -- die zweite Zeile NEBEN dem
#: Knopf. Der Knopftext selbst gehoert Karte A2.
#: Umlaute wie die Beschriftungen von A2 daneben (``web_chat``:
#: "Aufnahme läuft — …"). Gestoppt wird ueber "■ Beenden", nicht ueber den
#: runden Knopf -- der ist waehrend der Aufnahme nur Anzeige. P2, Aufgabe 2:
#: der Ruhetext nennt den Stopp nicht mehr. Er verwies auf einen Knopf, den
#: es im Ruhezustand nicht gibt; seit dem Interview-Modus ist "Beenden" nach
#: dem Start der eine grosse Knopf auf dem Schirm und braucht keine Ansage.
_TEXT_REC_RUHT = "Einmal tippen zum Starten."
_TEXT_REC_STARTET = "Das Mikrofon wird freigegeben …"
_TEXT_REC_LAEUFT = "Aufnahme läuft."
_TEXT_REC_LAEDT = "Die letzten Stücke gehen noch raus."
#: P2, Aufgabe 2: die Pause ist kein Laufen. Bis dahin stand waehrend einer
#: Pause "Aufnahme läuft." neben einer stehenden Uhr -- ein falscher
#: Zustand, und genau falsche Zustaende kosteten in Dortmund die 14 Drucke.
_TEXT_REC_PAUSIERT = "Pausiert – nichts wird aufgenommen."
#: Die Kopfzeile des zugeklappten Leitfadens im Interview-Modus.
_TEXT_LEITFADEN = "Leitfaden"

#: Die Akt-Marke in der zugeklappten Uebersicht. Sie steht VOR dem Text
#: von Karte W ("Phase 3 von 7 · Interviews — 1/3"), nicht statt ihm.
_TEXT_AKT_KOPF = "Akt {nummer}/{gesamt}"

#: Die zweite Kopfzeile unter der Aktzeile (P2, Aufgabe 2, Punkt 2): was
#: als Naechstes kommt. ``{was}`` ist die erste noch nicht erledigte Aufgabe
#: der aktiven Phase, wortgleich aus der Aktfolge von Karte W -- oder, wenn
#: die Phase durch ist, ``_TEXT_NAECHSTE_PHASE``.
_TEXT_NAECHSTES = "Als Nächstes: {was}"
_TEXT_NAECHSTE_PHASE = "Phase {bezeichnung}"

#: Die zwei Belohnungen. Klein, einmal, und sie verschwinden von selbst.
_TEXT_BELOHNUNG_AKT = "Akt abgeschlossen."
_TEXT_BELOHNUNG_AKT_SATZ = "{akt} steht. Weiter."
_TEXT_BELOHNUNG_AUFNAHME = "Interview ist drin."
_TEXT_BELOHNUNG_AUFNAHME_SATZ = "Aufgenommen und auf dem Weg zur Auswertung."


T = sprache.Texte(__name__)


#: Die Namen der eigenen ``@keyframes``. Als Liste, damit ein Test sie
#: gegen das CSS haelt: eine unbenutzte Animation ist toter Code, eine
#: undefinierte ein stiller Ausfall.
KEYFRAMES = ("ux-blinken", "ux-puls", "ux-auftritt", "ux-glitch", "ux-vorhang")

#: Jeder Selektor, den der reduced-motion-Block stilllegt -- die eigenen
#: UND die aus A2/W. Die aus A2/W stehen hier, weil sie GESCOPT und damit
#: spezifischer sind als alles in diesem Modul.
BEWEGT = (
    "#ux-vorhang",
    "#ux-ansage",
    "#ux-belohnung",
    '#ux-vorhang[data-an="1"]',
    '#ux-belohnung[data-an="1"]',
    "#interview",
    "#interview::before",
    "#pegel span",
    ".tabs button",
    ".phase-knopf",
    ".blase.vorlaeufig::after",   # Karte W
    "#tippt::after",              # Karte W
    '#tippt[data-ux-denkt="1"]::after',
    '#interview[data-ux-zustand="startet"]::before',
    '#interview[data-ux-zustand="laeuft"]::before',
    # P2, Aufgabe 2: der Interview-Modus legt selbst still -- und steht
    # deshalb hier (jede Regel mit ``animation:`` gehoert in den Block).
    'html[data-ux-interview="1"] #pegel span',
    'html[data-ux-interview="1"] #ux-rec-zeile',
    'html[data-ux-interview="1"] #interview[data-ux-zustand]',
    'html[data-ux-interview="1"] #interview::before',
    '#ux-belohnung[data-art="aufnahme"]',
)


def _ruhig_block() -> str:
    """Der eine ``@media (prefers-reduced-motion: reduce)``-Block.

    **Die einzige Stelle mit ``!important``** in diesem Modul. Grund: er
    muss auch gescopte Regeln aus A2/W schlagen
    (``.panel-chat .blase.vorlaeufig::after``), und die sind spezifischer
    als jeder ungescopte Selektor hier.

    Der Text des Stroms baut sich weiterhin stueckweise auf -- das ist
    Information, keine Animation (Karte W, Aufgabe 14). Still wird nur,
    was blinkt, pulst, gleitet oder einfliegt. **Kein Zustand haengt an
    einer Animation**: jeder steht zusaetzlich im Text."""
    selektoren = ",\n".join(BEWEGT)
    return (
        "@media (prefers-reduced-motion: reduce) {\n"
        f"{selektoren} {{\n"
        "  animation: none !important;\n"
        "  transition: none !important;\n"
        "}\n"
        "#ux-vorhang { display: none !important; }\n"
        "}\n"
    )


def _druck_block() -> str:
    """Der Ausdruck bleibt ein helles Manuskript.

    Die Probenansicht setzt seit dem 06.09.2026 ein Manuskript
    (``web._CSS_TEXTBUCH``, ``@media print``). Dieses Modul faerbt die
    Seite dunkel und steht im ``<style>`` DANACH -- ohne diesen Block
    kaeme ein schwarzes Blatt aus dem Drucker. Die Farben sind hier
    bewusst roh und nicht aus Tokens: der Ausdruck ist nicht
    themenfaehig, er ist immer hell.

    **Jede innere Regel bleibt einzeilig** (Schlusstklammer nie direkt
    nach einem Zeilenumbruch): ``test_keine_rohe_hexfarbe_ausserhalb_
    des_tokenblocks`` schneidet den Block mit ``@media\\s+print\\s*\\{.*?
    \\n\\}`` heraus, und dieses Muster ist nicht gierig -- es endet beim
    ERSTEN ``\\n}``. Eine mehrzeilige innere Regel haette diese Klammer
    vor der des ``@media``-Blocks, der Schnitt waere zu kurz, und die
    restlichen Hexfarben (``#000``, ``#333``) blieben unentdeckt im
    geprueften Text stehen."""
    return (
        "@media print {\n"
        'body, .panel-textbuch { background: #fff !important; '
        'color: #000 !important; '
        'font-family: ui-serif, Georgia, "Times New Roman", serif !important; }\n'
        "#ux-vorhang, #ux-ansage, #ux-belohnung, .tabs, .roadmap, .fuss,\n"
        "#ux-naechstes,\n"
        "#ux-rec-zeile { display: none !important; }\n"
        ".sprecher { color: #000 !important; font-weight: 700; }\n"
        ".regie, .regie-zeile, .angaben, .besetzung { "
        "color: #333 !important; opacity: 1 !important; }\n"
        "h1, h2, a, .leer, .zurueck { color: #000 !important; }\n"
        ".block, .frage, .frage .vorher { border-color: #000 !important; }\n"
        "}\n"
    )


def css_rahmen(name: str | None = None) -> str:
    """Alles Ungescopte: Tokens, Seitenrahmen, Tabs, Roadmap, die beiden
    Momente, die Keyframes, reduced-motion und der Druck.

    Wird auf der vereinten Seite **und** auf der Probenansicht
    ausgeliefert. Enthaelt deshalb nichts, was nur in einem Panel Sinn
    ergibt."""
    gewaehlt = name or entwurf()
    return "".join((
        tokens_css(gewaehlt),
        _BASIS,
        _TABS_A if gewaehlt == "a" else _TABS_B,
        _ROADMAP,
        _MOMENTE_A if gewaehlt == "a" else _MOMENTE_B,
        _BELOHNUNG,
        _KEYFRAMES_CSS,
        _ruhig_block(),
        _druck_block(),
    ))


def css_interview(name: str | None = None) -> str:
    """Der Interview-Modus (P2, Aufgabe 2) -- UNGESCOPT, weil er auch
    Phasenleiste und Tableiste ausblendet, aber nur auf Seiten MIT Chat:
    ``web_vereint.seite`` haengt ihn hinter ``css_chat`` an. Die
    Probenansicht und Telegram-Gruppen bekommen ihn nicht (dort darf kein
    Chat-Markername stehen, ``test_telegram_gruppe_hat_kein_chat_panel``).
    Ohne ``@keyframes``/``@media`` -- die bleiben in ``css_rahmen()``; was er
    stilllegt, steht in ``BEWEGT``. Fuer beide Entwuerfe gleich."""
    return _INTERVIEW


def css_chat(name: str | None = None) -> str:
    """Was IM Chat-Panel liegt. Der Aufrufer scopt das auf
    ``.panel-chat`` -- deshalb hier kein ``@keyframes``, kein ``@media``
    und kein ``body``."""
    return _CHAT_A if (name or entwurf()) == "a" else _CHAT_B


def css_stand(name: str | None = None) -> str:
    """Was IM Arbeitsstand-Panel liegt. Fuer beide Entwuerfe gleich: es
    ist eine Leseflaeche, und die Tokens tragen den Unterschied."""
    return _STAND


def css_textbuch(name: str | None = None) -> str:
    """Was IM Textbuch-Panel liegt -- und, ungescopt, auf der
    Probenansicht ``/g/<token>/textbuch``."""
    return _SKRIPT_A if (name or entwurf()) == "a" else _SKRIPT_B


def css_dashboard(name: str | None = None) -> str:
    """Das Team-Dashboard ``/`` (P2, Aufgabe 3) -- nur mit
    ``[web] dashboard_gestaltet``, eingehaengt an EINER Stelle in
    ``web.dashboard_html`` (zusammen mit ``tokens_css``).

    Bewusst NICHT ``css_rahmen()``: das Dashboard hat keinen Chat, keine
    Aktfolge, keinen Vorhang und keinen Druck -- es haengt am Beamer und
    laedt alle zehn Sekunden nach. Deshalb auch **keine Bewegung** (eine
    Animation startete bei jedem Nachladen neu) und kein ``@media``: die
    Schrift waechst ueber ``clamp()`` mit der Breite, vom Telefon bis zum
    Beamer. Fuer beide Entwuerfe gleich, die Tokens tragen den
    Unterschied."""
    return _DASHBOARD


#: Der Seitenrahmen. ``body`` steht hier und nicht im gescopten Teil: es
#: gibt genau einen, und auf der Probenansicht gibt es gar kein Panel.
#:
#: Die eine ``transition`` traegt den Vertrag aus Aufgabe 3 von Anfang an;
#: der Rest des Aufnahmeknopfes kommt in Aufgabe 8.
_BASIS = """
body {
  background: var(--grund);
  color: var(--text);
  font-family: var(--schrift-lesen);
  font-size: 1rem;
  line-height: 1.5;
  max-width: 46rem;
  margin: 0 auto;
  -webkit-text-size-adjust: 100%;
}
h1 { font-size: 1.05rem; letter-spacing: .05em; color: var(--signal); }
h2 { color: var(--text-leise); border-bottom: 1px solid var(--linie); }
a { color: var(--signal); }
::selection { background: var(--signal); color: var(--auf-signal); }
:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }
.leer { color: var(--text-leise); }
#interview { transition: background var(--takt-schnell) linear,
                         transform var(--takt-schnell) linear; }
/* Der Leitfaden (``web._CSS_LEITFADEN``) bekommt nur diesen Rahmen. Er war
   fuer weisses Papier gesetzt: Ueberschriften ueber ``opacity: .65``
   gedaempft (3.6:1 auf dem dunklen Grund), Trennlinien schwarz und damit
   unsichtbar (Review an 834edbf, Rundgang). */
h2 { opacity: 1; }
.zurueck { opacity: 1; color: var(--text-leise); }
.block, .frage { border-top-color: var(--rand); }
.frage .vorher { border-left-color: var(--signal); }
"""

#: Das Dashboard (P2, Aufgabe 3). Ueberschreibt ``web._CSS_DASHBOARD`` --
#: gleiche Spezifitaet, spaetere Position. ``em`` statt ``rem`` in den
#: Karten, damit alles mit der Grundschrift des ``body`` waechst.
_DASHBOARD = """
body { background: var(--grund); color: var(--text);
       font-family: var(--schrift-lesen); line-height: 1.45;
       font-size: clamp(1rem, .5rem + .7vw, 1.35rem);
       max-width: none; margin: 0; padding: clamp(.75rem, 1.4vw, 2rem); }
h1 { font-family: var(--schrift-skript); font-weight: 600; color: var(--signal);
     font-size: 1.45em; letter-spacing: .02em; margin: 0 0 .7em; }
h1 .stand { font-family: var(--schrift-tech); font-size: .5em; font-weight: 400;
            color: var(--text-leise); opacity: 1; letter-spacing: 0;
            display: inline-block; white-space: nowrap; }
.gruppen { gap: 1em; grid-template-columns: repeat(auto-fit, minmax(min(100%, 21em), 1fr)); }
.karte { background: var(--grund-2); border: 1px solid var(--linie);
         border-radius: var(--radius-gross); padding: .9em 1em 1em; }
.kopf { border-bottom: 1px solid var(--linie); padding-bottom: .45em;
        margin-bottom: .55em; align-items: center; }
.karte h2 { font-family: var(--schrift-skript); font-weight: 600;
            font-size: 1.4em; line-height: 1.15; color: var(--text); }
.karte h2 a { color: var(--text); text-decoration: none; }
.karte h2 a:hover, .karte h2 a:focus-visible { color: var(--signal);
            text-decoration: underline; }
a { color: var(--signal); }
:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }
.marke { font-size: .72em; font-weight: 600; padding: .2em .6em;
         border-radius: 1em; background: var(--rec); color: var(--auf-rec);
         white-space: nowrap; }
.ux-fortschritt { display: flex; flex-direction: column; gap: .35em;
                  margin: 0 0 .8em; }
.ux-akt { font-family: var(--schrift-tech); font-size: .9em; color: var(--signal);
          letter-spacing: .03em; }
.ux-segmente { display: flex; gap: .3em; }
.ux-segmente i { flex: 1 1 0; height: .5em; border-radius: 1em;
                 background: var(--grund-3); border: 1px solid var(--rand); }
.ux-segmente i.fertig { background: var(--signal); border-color: var(--signal); }
.ux-segmente i.jetzt { background: var(--warn); border-color: var(--warn); }
.ux-achtung { margin: 0 0 .9em; padding: .55em .75em;
              border: 1px solid var(--rand); border-left: .35em solid var(--rec);
              border-radius: var(--radius); background: var(--grund-3);
              color: var(--text); }
/* Die Marke traegt das Signal, nicht der Rand: ``--rec`` erreicht auf den
   dunklen Flaechen keine 3:1, ``--auf-rec`` auf ``--rec`` schon. */
.ux-achtung b { display: inline-block; font-family: var(--schrift-tech);
                font-size: .78em; letter-spacing: .08em; text-transform: uppercase;
                background: var(--rec); color: var(--auf-rec);
                padding: .1em .5em; border-radius: var(--radius); }
.ux-achtung ul { margin: .25em 0 0; padding-left: 1.1em; font-size: .92em; }
dl { margin: 0; }
dt { font-family: var(--schrift-tech); font-size: .68em; letter-spacing: .1em;
     text-transform: uppercase; color: var(--text-leise); opacity: 1;
     margin-top: .75em; }
dt:first-child { margin-top: 0; }
dd { margin: .1em 0 0; }
ul { padding-left: 1.1em; }
/* Am Beamer muss eine Karte im Spaetstand in 1080 px passen (Review an
   2841d83): lange Felder auf wenige Zeilen gekappt, der volle Text steht
   auf der Gruppenseite. Figuren nur mit Namen, in einer Zeile mit Trenner. */
dd.kurz { display: -webkit-box; -webkit-box-orient: vertical;
          -webkit-line-clamp: 3; line-clamp: 3; overflow: hidden; }
dd.figuren { display: -webkit-box; -webkit-box-orient: vertical;
             -webkit-line-clamp: 3; line-clamp: 3; overflow: hidden; }
dd.figuren b { font-weight: 600; }
dd.kurz ul.fragen li { margin: 0; }
.ergebnisse { margin: 0; font-size: 1em; }
.ergebnisse li { margin-bottom: .2em; }
.fragen { margin: 0; padding-left: 1.1em; }
.noch-nichts { color: var(--text-leise); font-style: italic; margin: .2em 0 0; }
.leer { color: var(--text-leise); opacity: 1; }
.zeit { color: var(--text-leise); opacity: 1; }
details { margin-top: .9em; font-size: .78em; }
details > summary { cursor: pointer; color: var(--text-leise);
                    font-family: var(--schrift-tech); letter-spacing: .05em; }
th { color: var(--text-leise); opacity: 1; }
th, td { border-bottom-color: var(--linie); }
.vorfaelle { background: var(--grund-3); border-left-color: var(--rec); }
/* Signal auf grund-3 als TEXT -- in ``KONTRAST`` mit 4.5 gefuehrt. */
.vorfaelle .art { color: var(--signal); }
"""

#: Keyframes -- ALLE hier, nie im gescopten Teil (siehe Modulkopf).
_KEYFRAMES_CSS = """
@keyframes ux-blinken { 50% { opacity: 0; } }
@keyframes ux-puls { 50% { opacity: .35; } }
@keyframes ux-auftritt { from { opacity: 0; transform: translateY(.6rem); } }
@keyframes ux-glitch {
  0% { opacity: 0; transform: translateY(0); }
  20% { opacity: 1; transform: translateY(-.4rem); }
  45% { opacity: .85; transform: translateY(.3rem); }
  70% { opacity: 1; transform: translateY(-.15rem); }
  100% { opacity: 0; transform: translateY(0); }
}
@keyframes ux-vorhang {
  0% { transform: translateY(-101%); }
  45% { transform: translateY(0); }
  55% { transform: translateY(0); }
  100% { transform: translateY(-101%); }
}
"""

#: Tableiste, Entwurf A: UNTEN, am Daumen. Auf einem Telefon im Stehen
#: ist das untere Drittel die einzige Flaeche, die eine Hand erreicht --
#: und die Gruppe wechselt oft zwischen Chat und Textbuch.
#:
#: Die Leiste liegt UNTER dem Fuss des Chats, deshalb bekommt der Fuss
#: ``bottom: var(--tabs-hoehe)``. In B ist dieses Token ``0rem``, und
#: dieselbe Regel kostet dort nichts.
_TABS_A = """
.tabs { position: fixed; left: 0; right: 0; bottom: 0; z-index: 7;
        margin: 0 auto; max-width: 46rem; height: var(--tabs-hoehe);
        display: flex; background: var(--grund-3);
        border-top: 1px solid var(--linie); }
.tabs button { flex: 1; min-height: var(--tabs-hoehe); border: 0;
               background: transparent; color: var(--text-leise);
               font-family: var(--schrift-tech); font-size: .8rem;
               letter-spacing: .08em; text-transform: uppercase; }
.tabs button[aria-selected="true"] { color: var(--signal);
                                     background: var(--grund-2);
                                     box-shadow: inset 0 2px 0 var(--signal); }
.tabs button { transition: color var(--takt-schnell) linear; }
.fuss { bottom: var(--tabs-hoehe); z-index: 6; }
body { padding-bottom: calc(var(--tabs-hoehe) + 12.5rem); }
body:not([data-tab="chat"]) .fuss { display: none; }
"""

#: Tableiste, Entwurf B: OBEN, unter der Aktleiste -- zusammen ein
#: Programmzettel. Der Fuss traegt dort den runden Aufnahmeknopf und
#: braucht die ganze untere Kante fuer sich.
_TABS_B = """
.tabs { position: sticky; top: 0; z-index: 7; display: flex; gap: .2rem;
        padding: 0 .55rem; background: var(--grund);
        border-bottom: 1px solid var(--linie); }
.tabs button { flex: 1; min-height: var(--tippflaeche); border: 0;
               border-bottom: 3px solid transparent; background: transparent;
               color: var(--text-leise);
               font-family: var(--schrift-skript); font-size: 1rem;
               padding: .35rem .2rem .45rem; }
.tabs button[aria-selected="true"] { color: var(--signal);
                                     border-bottom-color: var(--signal); }
.tabs button { transition: color var(--takt-schnell) linear; }
.fuss { bottom: var(--tabs-hoehe); z-index: 6; }
body { padding-bottom: 13rem; }
body:not([data-tab="chat"]) .fuss { display: none; }
/* B: die sieben Akte als Reihe von Buehnenlichtern statt als ein
   Balken. Dieselbe Zahl, andere Metapher.

   Praefix ``.roadmap``: ``_ROADMAP`` (unten, gilt fuer beide Entwuerfe,
   steht in ``css_rahmen()`` NACH diesem Block) definiert dieselben
   Selektoren ``#ux-balken``/``#ux-balken i`` roh, ohne Praefix. Bei
   gleicher Spezifitaet gewinnt in CSS die spaetere Regel -- also
   ``_ROADMAP``, unabhaengig davon, was hier steht. Das ``.roadmap``
   davor hebt die Spezifitaet von (0,1,0,0) auf (0,1,1,0) und gewinnt
   damit gegen die unpraefixierten Regeln unten, GLEICH welche Reihenfolge
   ``css_rahmen()`` waehlt. ``.roadmap`` ist die Wurzel-Klasse der
   Phasenuebersicht (``<details class="roadmap" id="roadmap">``,
   ``web_vereint.py``) -- ``#ux-balken`` haengt als Kind von ``summary``
   darunter, der Nachfahren-Selektor passt also wirklich. */
.roadmap #ux-balken { display: flex; gap: .28rem; height: .5rem;
             background: none; border: 0; }
.roadmap #ux-balken i { flex: 1; width: auto; border-radius: .25rem;
               background: var(--grund-3); border: 1px solid var(--linie); }
/* ``data-stand`` setzt ``_JS_FORTSCHRITT`` je Licht -- ohne diese zwei
   Regeln sehen alle drei Zustaende gleich aus. ``offen`` braucht keine
   eigene Regel: die Basisregel oben trifft ihn schon, und die beiden
   Attribut-Selektoren hier sind spezifischer, aber nur fuer ihren
   jeweiligen Wert -- sie ueberschreiben ``offen`` nicht. */
.roadmap #ux-balken i[data-stand="fertig"] { background: var(--signal);
               border-color: var(--signal); }
.roadmap #ux-balken i[data-stand="aktiv"] { background: var(--warn);
               border-color: var(--warn); }
/* Abschluss-Review, Befund 1: dieselbe Kollision wie bei #ux-balken oben
   (Kommentar darueber), diesmal an zwei Selektoren, die beim ersten Fix
   uebersehen wurden. ``_ROADMAP`` definiert ``.roadmap > summary`` und
   ``.phase-knopf`` ERNEUT, mit exakt derselben Spezifitaet wie hier -- bei
   Gleichstand gewinnt die spaetere Regel, also ``_ROADMAP``, unabhaengig
   von der Reihenfolge in ``css_rahmen()``. Zwei Selektoren, zwei Formen,
   weil beide schon anders zu ``.roadmap`` stehen:
   - ``.roadmap > summary`` hat ``.roadmap`` bereits als Kind-Kombinator-
     Praefix -- ein zusaetzlicher NACHFAHREN-Praefix (``.roadmap .roadmap >
     summary``) gaebe es im Markup nie, weil es nur ein ``.roadmap``-Element
     gibt (``<details class="roadmap" id="roadmap">``). Die Klassen-
     Verdopplung ``.roadmap.roadmap`` hebt die Spezifitaet von (0,1,1,0) auf
     (0,2,1,0), ohne den getroffenen Knoten zu aendern.
   - ``.phase-knopf`` steht dagegen OHNE jeden Praefix und kommt im Markup
     immer als Nachfahre von ``.roadmap`` vor (einzige Erzeugungsstelle:
     ``web_vereint.roadmapleiste_html``, der Knopf steht innerhalb von
     ``<details class="roadmap">``) -- hier passt derselbe Nachfahren-
     Praefix wie bei ``#ux-balken``, von (0,1,0,0) auf (0,2,0,0). Zusaetzlich
     wichtig: ``_ROADMAP`` setzt bei ``.phase-knopf`` ``font: inherit``
     (Shorthand) -- das setzt ``font-family`` explizit zurueck, nicht nur
     implizit durch spaetere Reihenfolge. */
.roadmap.roadmap > summary { font-family: var(--schrift-skript); font-size: .95rem; }
.roadmap .phase-knopf { font-family: var(--schrift-skript); }
"""
#: Die Phasenuebersicht als Aktfolge. Fuer beide Entwuerfe dieselbe
#: Struktur -- die Tokens und die zwei Abweichungen unten tragen den
#: Unterschied.
#:
#: **Zugeklappt eine Zeile** (Karte W): sieben Akte mit ihren Aufgaben
#: naehmen am Telefon ein Drittel des Bildschirms fuer etwas, das man
#: dreimal am Tag braucht. Aufgeklappt bekommt die Liste
#: ``max-height: 58vh`` -- sonst schiebt sie am Telefon die Tableiste aus
#: dem Bild (gemessen am Entwurf, Screenshot ``entwurf-b-handy-akte.png``
#: vor der Nachbesserung).
_ROADMAP = """
header { position: sticky; top: 0; z-index: 4; background: var(--grund);
         border-bottom: 1px solid var(--linie); padding: .5rem .75rem; }
.roadmap > summary { list-style: none; cursor: pointer;
                     min-height: var(--tippflaeche); display: flex;
                     align-items: center; gap: .5rem; color: var(--signal);
                     font-family: var(--schrift-tech); font-size: .9rem;
                     letter-spacing: .04em; }
.roadmap > summary::-webkit-details-marker { display: none; }
.phasen { list-style: none; margin: .4rem 0 .2rem; padding: 0;
          max-height: 58vh; overflow-y: auto; }
.phase { border-left: 2px solid var(--linie); padding: 0 0 .35rem .55rem;
         margin: 0 0 .35rem; }
.phase.aktiv { border-left-color: var(--warn); }
.phase-knopf { display: block; width: 100%; text-align: left; font: inherit;
               min-height: var(--tippflaeche); background: var(--grund-2);
               color: var(--text); border: 1px solid var(--rand);
               border-radius: var(--radius); padding: .45rem .6rem;
               transition: background var(--takt-schnell) linear; }
.phase.aktiv .phase-knopf { border-color: var(--warn); color: var(--warn); }
.phase-knopf[data-sicher="1"] { background: var(--warn); color: var(--auf-warn);
                                border-color: var(--warn); font-weight: 700; }
/* Browserlauf 03.10.2026: ``web_vereint._CSS_VEREINT`` setzt die Flaechen
   der Liste HELL und mit ``.roadmap``-Praefix -- (0,2,0) und mehr, also
   staerker als die rohen Regeln oben. Ergebnis im Bild: weisse
   Phasenknoepfe mit heller Schrift, unlesbar, in beiden Farbschemata.
   Hier nur FARBEN, gleich stark praefixiert und spaeter im Dokument; die
   Schrift bleibt bei den Regeln oben und bei ``_TABS_B`` (ein ``font:``
   hier wuerde die Skriptschrift aus B wieder zuruecksetzen). */
.roadmap .phase-knopf { background: var(--grund-2); color: var(--text);
                        border-color: var(--rand); }
.roadmap .phase.aktiv .phase-knopf { border-color: var(--warn);
                                     color: var(--warn); }
.roadmap .phase-knopf[data-sicher="1"] { background: var(--warn);
                                         color: var(--auf-warn);
                                         border-color: var(--warn); }
.roadmap li.phase.aktiv { background: transparent; border: 0;
                          border-left: 2px solid var(--warn); border-radius: 0; }
.roadmap .phase-abbrechen { background: var(--grund-2); color: var(--text);
                            border-color: var(--rand); }
.roadmap li.aufgabe:hover { background: var(--grund-3); }
/* Im Chat-Tab steht unten der feste Fuss, waehrend einer Aufnahme rund
   ein Drittel des Telefons hoch. Mit 58vh schob die offene Aktfolge die
   Tableiste darunter, und sie lag ueber Uhr und Pegel (Browserlauf
   03.10.2026, 390x844). Die Liste scrollt in sich. */
body[data-tab="chat"] .roadmap .phasen { max-height: 30vh; }
.aufgaben { list-style: none; margin: .3rem 0 0; padding: 0 0 0 .1rem;
            font-size: .88rem; }
.aufgabe { min-height: var(--tippflaeche); display: flex; align-items: center;
           gap: .45rem; cursor: pointer; color: var(--text-leise); }
.aufgabe.erledigt { color: var(--signal); }
.aufgabe.laeuft { color: var(--warn); }
#ux-balken { flex: 1; height: .4rem; background: var(--grund-3);
             border: 1px solid var(--linie); border-radius: var(--radius); }
#ux-balken i { display: block; height: 100%; width: var(--fortschritt, 0%);
               background: var(--signal); }
.ux-akt { color: var(--warn); letter-spacing: .1em; margin-right: .4rem; }
/* P2, Aufgabe 2, Punkt 2: "Als Naechstes: ..." direkt unter der Aktzeile,
   ueber der Tableiste -- auf jedem Tab im ersten Blick. Eine Zeile, leise,
   die Sache selbst in der Textfarbe; zu lang wird abgeschnitten statt
   umgebrochen (die Tableiste darf nicht wandern). */
#ux-naechstes { max-width: 44rem; margin: -.35rem auto .45rem;
                padding: 0 .3rem; font-size: .9rem; line-height: 1.35;
                color: var(--text-leise); white-space: nowrap;
                overflow: hidden; text-overflow: ellipsis; }
#ux-naechstes[hidden] { display: none; }
#ux-naechstes b { color: var(--text); font-weight: 600; }
"""
#: Der Aktwechsel, Entwurf A: ein Glitch. Scanlines springen, der Aktname
#: steht in Versalien darueber. ``pointer-events: none``, damit ein
#: haengendes Skript die Bedienung nicht blockiert.
_MOMENTE_A = """
#ux-vorhang { position: fixed; inset: 0; z-index: 9; pointer-events: none;
              opacity: 0; background: repeating-linear-gradient(to bottom,
                rgba(110, 247, 165, .30) 0 2px, rgba(5, 7, 10, .92) 2px 5px); }
#ux-vorhang[data-an="1"] { animation: ux-glitch var(--takt-moment) steps(6) 1; }
#ux-ansage { position: fixed; inset: 0; z-index: 10; display: grid;
             place-items: center; pointer-events: none; }
#ux-ansage[hidden] { display: none; }
#ux-ansage b { font-family: var(--schrift-tech); font-size: 1.5rem;
               letter-spacing: .3em; text-transform: uppercase;
               color: var(--signal); background: var(--grund);
               border: 1px solid var(--signal); padding: .8rem 1.2rem; }
"""

#: Der Aktwechsel, Entwurf B: ein Vorhang. Er faellt von oben und geht
#: wieder hoch -- dieselbe Dauer, andere Metapher.
_MOMENTE_B = """
#ux-vorhang { position: fixed; inset: 0; z-index: 9; pointer-events: none;
              transform: translateY(-101%);
              background: repeating-linear-gradient(to right,
                var(--vorhang-1) 0 1.1rem, var(--vorhang-2) 1.1rem 2.2rem); }
#ux-vorhang[data-an="1"] { animation: ux-vorhang var(--takt-moment) ease-in-out 1; }
#ux-ansage { position: fixed; inset: 0; z-index: 10; display: grid;
             place-items: center; pointer-events: none; }
#ux-ansage[hidden] { display: none; }
#ux-ansage b { font-family: var(--schrift-skript); font-size: 1.7rem;
               letter-spacing: .12em; color: var(--signal);
               background: var(--grund);
               border-top: 1px solid var(--signal);
               border-bottom: 1px solid var(--signal); padding: .7rem 1.4rem;
               /* Mobile-App-Shell (03.10.2026): 100% des eigenen, schon
                  auf den sichtbaren Bereich geklammerten Elternkastens
                  (#ux-ansage { inset: 0 }) -- 100vw zaehlt auf dem Telefon
                  gelegentlich breiter als der sichtbare Ausschnitt
                  (Scrollbar-Kompensation, Rundung) und war Teil des
                  seitlichen Wackelns aus Birks Befund. */
               max-width: calc(100% - 1.5rem); text-align: center; }
"""

#: Die Belohnung: klein, einmal, verschwindet von selbst.
#:
#: ``aria-live="polite"`` statt ``alert``: sie unterbricht nichts. Und
#: sie liegt UEBER dem Fuss, nicht darin -- der Fuss gehoert dem
#: Aufnahmeknopf, und ein Kasten, der ihn verschiebt, waere genau die
#: Art Bewegung, die man beim Tippen nicht will.
_BELOHNUNG = """
#ux-belohnung { position: fixed; left: .75rem; right: .75rem; z-index: 8;
                bottom: calc(var(--tabs-hoehe) + 13.5rem);
                margin: 0 auto; max-width: 44rem;
                background: var(--grund-2); border: 1px solid var(--signal);
                border-left: 4px solid var(--signal);
                border-radius: var(--radius-gross); padding: .6rem .7rem; }
#ux-belohnung[hidden] { display: none; }
#ux-belohnung b { color: var(--signal); letter-spacing: .05em; }
#ux-belohnung p { margin: .2rem 0 0; font-size: .9rem; color: var(--text-leise); }
#ux-belohnung[data-an="1"] { animation: ux-auftritt 260ms ease-out 1; }
#ux-belohnung[data-art="aufnahme"] { animation: none; }
"""
#: Der Interview-Modus (P2, Aufgabe 2). Gilt, solange ``_JS_INTERVIEW``
#: ``data-ux-interview="1"`` an ``<html>`` setzt -- also nur, waehrend
#: DIESES Telefon ein Interview aufnimmt (laufend oder pausiert), nie bei
#: Push-to-Talk.
#:
#: Uebrig bleiben Uhr, Pegel, Zustandszeile, Warteschlange/Fehler/Anhalt
#: (das ist Information: dort steht, wenn das Netz weg ist) und die
#: Stopp-Leiste. Weg sind Phasenleiste, Tabs, Chatverlauf, Eingabezeile,
#: Akt-Moment, Belohnung. Der runde Knopf ist waehrend der Aufnahme ohnehin
#: nur Anzeige (A2) und lud mit seinem Stopp-Quadrat zum Tippen ein, ohne
#: etwas zu tun -- hier schrumpft er zur ruhigen Aufnahmelampe (rot, in der
#: Pause in der Warnfarbe ``var(--warn)``: A amber, B gruen), ohne Puls und ohne Zeiger-Ereignisse. Er bleibt im DOM und
#: sichtbar: sein Name traegt Zustand und Zeit fuer Vorleseprogramme.
#: **Ein Hauptknopf**: "Beenden", gross, rot, unten am Daumen; "Pause"
#: darueber und kleiner.
#:
#: Ungescopt (``css_interview()``) und mit ``html[...]`` davor: die
#: gescopten Regeln aus A2/W (``.panel-chat #interview``) waeren sonst
#: spezifischer. ``#tab-chat`` wird erzwungen sichtbar -- der Tab haengt am
#: Fragment, und ein Zurueck-Wischen auf ``#stand`` haette sonst den Stopp
#: samt Tableiste weggenommen. ``#interview[data-ux-zustand]`` hebt die
#: Lampe auf (1,2,1): B setzt die Groesse des laufenden Kreises gescopt mit
#: (1,2,0), die Pause-Flaeche aus ``_CHAT_FLAECHEN`` mit (1,3,0). (Kein
#: CSS-Kommentar vor einer Regel mit ``animation:`` -- der Test in
#: ``test_web_gestalt_css`` liest ihn als Teil des Selektors.)
_INTERVIEW = """
#ux-leitfaden { display: none; }
html[data-ux-interview="1"] .panel:not(#tab-chat),
html[data-ux-interview="1"] #roadmap,
html[data-ux-interview="1"] #ux-naechstes,
html[data-ux-interview="1"] .tabs,
html[data-ux-interview="1"] #ux-belohnung,
html[data-ux-interview="1"] #ux-vorhang,
html[data-ux-interview="1"] #ux-ansage,
html[data-ux-interview="1"] .panel-chat h1,
html[data-ux-interview="1"] #verlauf,
html[data-ux-interview="1"] #tippt,
html[data-ux-interview="1"] #brainstorm,
html[data-ux-interview="1"] #brainstorm-aktionen,
html[data-ux-interview="1"] .zeile { display: none; }
html[data-ux-interview="1"] #tab-chat { display: block; }
html[data-ux-interview="1"] body .fuss { display: flex; top: 0; bottom: 0;
    flex-direction: column; flex-wrap: nowrap; justify-content: flex-end;
    align-items: stretch; gap: 1rem; padding: 1rem 1rem 1.5rem;
    border-top: 0; overflow-y: auto; }
html[data-ux-interview="1"] #ux-leitfaden:not([hidden]) { display: block;
    margin-bottom: auto; flex: 0 1 auto; min-height: 0; overflow-y: auto;
    background: var(--grund-2); border: 1px solid var(--rand);
    border-radius: var(--radius); padding: 0 .8rem; }
html[data-ux-interview="1"] #ux-leitfaden summary {
    min-height: var(--tippflaeche); display: flex; align-items: center;
    cursor: pointer; color: var(--text); font-family: var(--schrift-tech);
    letter-spacing: .06em; list-style: none; }
html[data-ux-interview="1"] #ux-leitfaden summary::-webkit-details-marker {
    display: none; }
html[data-ux-interview="1"] #ux-leitfaden summary::before { content: "\\25B8";
    display: inline-block; width: 1.1em; color: var(--warn); }
html[data-ux-interview="1"] #ux-leitfaden[open] summary::before {
    content: "\\25BE"; }
html[data-ux-interview="1"] .ux-leitfaden-text { white-space: pre-wrap;
    color: var(--text); font-family: var(--schrift-skript);
    font-size: 1.05rem; line-height: 1.5; padding: 0 0 .7rem; }
html[data-ux-interview="1"] #uhr { flex: 0 0 auto; font-size: 3.4rem;
    line-height: 1.1; text-align: center; }
html[data-ux-interview="1"] #pegel { flex: 0 0 auto; height: .9rem;
    min-width: 0; }
html[data-ux-interview="1"] #pegel span { transition: none; animation: none; }
html[data-ux-interview="1"] #ux-rec-zeile { flex: 0 0 auto; margin: 0;
    text-align: center; font-size: 1.25rem; animation: none; }
html[data-ux-interview="1"] #interview[data-pausiert="1"] + #ux-rec-zeile {
    color: var(--warn); }
html[data-ux-interview="1"] #warteschlange,
html[data-ux-interview="1"] #fehler,
html[data-ux-interview="1"] .angehalten { flex: 0 0 auto; }
/* Die Warteschlange ist im Interview die eine Meldung, die zaehlt ("Keine
   Verbindung -- 2 offen"): lesbar statt Kleingedrucktes. */
html[data-ux-interview="1"] #warteschlange { font-size: .95rem;
    text-align: center; }
html[data-ux-interview="1"] #interview[data-ux-zustand] { flex: 0 0 auto;
    align-self: center;
    width: 1.3rem; height: 1.3rem; min-height: 0; padding: 0; border: 0;
    border-radius: 50%; background: var(--rec); font-size: 0;
    pointer-events: none; animation: none; transition: none; }
html[data-ux-interview="1"] #interview[data-ux-zustand][data-pausiert="1"] {
    background: var(--warn); }
html[data-ux-interview="1"] #interview::before { display: none;
    animation: none; transition: none; }
html[data-ux-interview="1"] #interview-aktionen:not([hidden]) {
    display: flex; flex-direction: column; gap: .75rem; margin: 0; }
html[data-ux-interview="1"] #interview-pause {
    min-height: var(--tippflaeche); }
html[data-ux-interview="1"] #interview-beenden { min-height: 4.5rem;
    font-size: 1.3rem; font-weight: 700; background: var(--rec);
    color: var(--auf-rec); border-color: var(--rec);
    border-radius: var(--radius-gross); }
"""

#: Die Flaechen, die ``web_chat._CSS_CHAT`` HELL setzt -- fuer beide
#: Entwuerfe gleich, deshalb einmal hier und an ``_CHAT_A``/``_CHAT_B``
#: angehaengt.
#:
#: Browserlauf 03.10.2026: A2 ist hell und schaltet nur unter
#: ``prefers-color-scheme: dark`` um; ein Telefon im hellen Modus bekam
#: das weisse Chat-Panel mit der hellen Schrift der Gestaltung -- die
#: Bot-Blase war unlesbar, "Pause"/"Beenden" weisse Kaesten. Jede Regel
#: hier hat dieselbe Spezifitaet wie ihr Gegenstueck in A2 und steht
#: spaeter im Dokument. ``body`` wird beim Scopen zu ``.panel-chat``
#: selbst (``web_vereint.scope_css``).
_CHAT_FLAECHEN = """
body { background: var(--grund); color: var(--text); }
/* Am Laptop lief der feste Fuss ueber die ganze Breite, waehrend Chat
   und Tabs auf 46rem zentriert stehen -- Uhr links aussen, Knoepfe
   rechts aussen. Dieselbe Breite wie ``body`` in ``_BASIS``. */
.fuss { max-width: 46rem; margin: 0 auto; }
.zeile input { min-width: 0; }
.interview-aktionen button, .angehalten button {
    background: var(--grund-2); color: var(--text);
    border: 1px solid var(--rand); border-radius: var(--radius);
    min-height: var(--tippflaeche); white-space: nowrap; }
.leiste.ueberholt button { border-color: var(--linie); color: var(--text-leise); }
#interview[data-laeuft="1"][data-pausiert="1"] { background: var(--grund-3);
    border-color: var(--warn); color: var(--warn); }
#brainstorm { background: var(--grund-2); color: var(--text);
              border-color: var(--rand); }
#brainstorm[data-laeuft="1"] { background: var(--rec); color: var(--auf-rec);
                               border-color: var(--rec); }
#brainstorm[data-laeuft="1"][data-pausiert="1"] { background: var(--grund-3);
    border-color: var(--warn); color: var(--warn); }
"""
#: Der Chat, Entwurf A: Terminal. Monospace, Phosphor als Rahmenfarbe der
#: Bot-Blase, eine Kennzeile `bot ~ $` darueber. Die Blase der Gruppe
#: sitzt rechts auf einer tiefen Signalflaeche.
#:
#: Der Denk-Cursor (``#tippt[data-ux-denkt="1"]::after``) steht am Ende --
#: ``_JS_DENKT`` setzt nur das Attribut, die Regel dazu gehoert ins Panel,
#: nicht in ``_BASIS`` (Aufgabe 8 ergaenzt dort noch den Aufnahmeknopf).
_CHAT_A = """
.verlauf { display: flex; flex-direction: column; gap: .5rem; }
.blase { padding: .5rem .65rem; max-width: 92%; font-size: 1rem;
         border-radius: var(--radius-gross); overflow-wrap: anywhere; }
.blase.bot { background: var(--grund-2); border: 1px solid var(--linie);
             border-left: 2px solid var(--signal); align-self: flex-start; }
.blase.bot::before { content: "bot ~ $"; display: block; font-size: .72rem;
                     letter-spacing: .1em; color: var(--text-leise);
                     font-family: var(--schrift-tech); }
.blase.gruppe { background: var(--signal-tief); border: 1px solid var(--rand);
                align-self: flex-end; }
/* Kursiv traegt "Sprachnachricht"; leise Schrift auf der Gruppenblase
   (--signal-tief) kam nur auf 4.1:1 (Rundgang, Review an 834edbf). */
.blase.sprache { color: var(--text); font-style: italic; }
.blase q { display: block; margin: .5rem 0; padding-left: .7rem;
           border-left: 2px solid var(--warn); color: var(--warn);
           font-family: var(--schrift-skript); font-style: italic;
           quotes: none; }
.blase.vorlaeufig { border-left-color: var(--warn); }
.blase.vorlaeufig::after { color: var(--signal); }
.leiste { display: flex; flex-direction: column; gap: .35rem;
          align-self: flex-start; width: 92%; }
.leiste button { text-align: left; min-height: var(--tippflaeche);
                 padding: .5rem .65rem; background: var(--grund-2);
                 color: var(--text); border: 1px solid var(--signal);
                 border-radius: var(--radius); font: inherit; }
.leiste button::before { content: "> "; color: var(--signal); }
.leiste button:disabled { opacity: .4; }
.quittung { font-size: .82rem; color: var(--text-leise); align-self: flex-start; }
#tippt { min-height: 1.3em; font-size: .85rem; color: var(--text-leise);
         letter-spacing: .05em; font-family: var(--schrift-tech); }
#tippt[data-ux-denkt="1"]::after { content: "\\258D";
                                   animation: ux-blinken 1s steps(2) infinite; }

/* -- Knopf 1: Interview (Umschalter) --------------------------------
   Volle Breite, eigene Zeile, Rot. Der wichtigste Knopf der Oberflaeche
   (Dortmund Tag 1: 13 von 20 Aufnahmen leer, ein Knopf 14x in 93 s
   gedrueckt) -- also die groesste Flaeche, die der Fuss hergibt, und ein
   Zustand, der im TEXT steht und nicht nur in der Farbe. */
#interview { width: 100%; min-height: var(--rec-hoehe);
             border-radius: var(--radius-gross);
             border: 2px solid var(--rec); background: var(--grund-2);
             color: var(--text); font: inherit; font-size: 1.05rem;
             letter-spacing: .1em; text-transform: uppercase;
             display: flex; align-items: center; justify-content: center;
             gap: .5rem; }
/* Die Lampe: ein Punkt, kein Bild -- kein url(), keine CSP-Frage. */
#interview::before { content: ""; width: .85rem; height: .85rem;
                     border-radius: 50%; background: var(--rec); }
/* Rueckmeldung unter 100 ms: CSS, kein Netz, kein Promise. */
#interview:active { transform: scale(.985); }
#interview[data-ux-zustand="startet"] { border-color: var(--warn);
                                        color: var(--warn); }
#interview[data-ux-zustand="startet"]::before { background: var(--warn);
    animation: ux-puls .7s ease-in-out infinite; }
#interview[data-ux-zustand="laeuft"] { background: var(--rec);
    color: var(--auf-rec); border-color: var(--rec);
    min-height: calc(var(--rec-hoehe) + .75rem); }
#interview[data-ux-zustand="laeuft"]::before { background: var(--auf-rec);
    animation: ux-puls 1.1s ease-in-out infinite; }
#interview[data-ux-zustand="laedt"] { border-color: var(--warn);
                                      color: var(--warn); }
#interview[data-ux-zustand="laedt"]::before { background: var(--warn); }
#interview[aria-busy="true"] { cursor: progress; }
/* Die zweite Zeile steht NEBEN dem Knopf, nie darin: ``_CHAT_JS`` setzt
   dort ``textContent`` (Befund 2 an Karte A2). */
#ux-rec-zeile { text-align: center; font-size: .76rem;
                color: var(--text-leise); margin-top: -.2rem; }
/* P2, Aufgabe 2: vorher ``var(--rec)`` -- als Text nur 3.45:1 (B) auf dem
   Grund, unter AA. Der laufende Zustand steht im Wortlaut und in der Uhr. */
#interview[data-ux-zustand="laeuft"] + #ux-rec-zeile { color: var(--text); }

/* -- Knopf 2: Push-to-Talk (halten) ---------------------------------
   Andere Form (Kreis), anderer Ort (in der Eingabezeile), andere Farbe
   (Signal statt Rot), anderes Verb (halten statt tippen). A2 blendet ihn
   aus, solange ein Interview laeuft -- zwei Mikrofone gleichzeitig sind
   keine Bedienung. */
#ptt { width: var(--tippflaeche); min-width: var(--tippflaeche);
       height: var(--tippflaeche); border-radius: 50%;
       border: 1px dashed var(--signal); background: var(--grund-2);
       color: var(--signal); font-size: 1.15rem; touch-action: none; }
#ptt[data-haelt="1"] { background: var(--signal); color: var(--auf-signal);
                       border-style: solid; }

/* -- Messwerk: Uhr, Pegel, Warteschlange ---------------------------- */
#uhr { font-family: var(--schrift-tech); font-variant-numeric: tabular-nums;
       font-size: 1.35rem; color: var(--warn); }
#pegel { height: .55rem; background: var(--grund-3);
         border: 1px solid var(--linie); border-radius: var(--radius);
         overflow: hidden; }
#pegel span { display: block; height: 100%; background: var(--rec);
              transition: width var(--takt-schnell) linear; }
#warteschlange { font-size: .78rem; color: var(--warn); min-height: 1.1em;
                 font-family: var(--schrift-tech); }
.fuss { background: var(--grund); border-top: 1px solid var(--linie); }
.zeile input { background: var(--grund-2); color: var(--text);
               border: 1px solid var(--rand); border-radius: var(--radius);
               min-height: var(--tippflaeche); }
#senden { background: var(--signal); color: var(--auf-signal); border: 0;
          border-radius: var(--radius); min-width: var(--tippflaeche);
          min-height: var(--tippflaeche); font-weight: 700; }
""" + _CHAT_FLAECHEN

#: Der Chat, Entwurf B: Buehne. Serifenfreie Leseschrift, weiche Formen,
#: keine Kennzeile -- Bot und Gruppe unterscheiden sich wie Repliken.
_CHAT_B = """
.verlauf { display: flex; flex-direction: column; gap: .6rem; }
.blase { padding: .6rem .8rem; max-width: 90%; font-size: 1.0625rem;
         border-radius: var(--radius-gross); overflow-wrap: anywhere; }
.blase.bot { background: var(--grund-2); border: 1px solid var(--linie);
             align-self: flex-start; border-bottom-left-radius: .3rem; }
.blase.gruppe { background: var(--signal-tief); border: 1px solid var(--rand);
                align-self: flex-end; border-bottom-right-radius: .3rem; }
/* Kursiv traegt "Sprachnachricht"; leise Schrift auf der Gruppenblase
   (--signal-tief) kam nur auf 4.1:1 (Rundgang, Review an 834edbf). */
.blase.sprache { color: var(--text); font-style: italic; }
.blase q { display: block; margin: .55rem 0; padding-left: .7rem;
           border-left: 3px solid var(--signal); color: var(--signal);
           font-family: var(--schrift-skript); font-style: italic;
           font-size: 1.15rem; quotes: none; }
.blase.vorlaeufig { border-style: dashed; }
.blase.vorlaeufig::after { color: var(--signal);
                           font-family: var(--schrift-tech); }
.leiste { display: flex; flex-direction: column; gap: .4rem;
          align-self: flex-start; width: 90%; }
.leiste button { text-align: left; min-height: var(--tippflaeche);
                 padding: .55rem .8rem; background: var(--grund-2);
                 color: var(--text); border: 1px solid var(--signal);
                 border-radius: var(--radius);
                 font-family: var(--schrift-skript); font-size: 1.05rem; }
.leiste button:disabled { opacity: .4; }
.quittung { font-size: .85rem; color: var(--text-leise); align-self: flex-start; }
#tippt { min-height: 1.3em; font-size: .8rem; color: var(--text-leise);
         letter-spacing: .06em; text-transform: uppercase;
         font-family: var(--schrift-tech); }
#tippt[data-ux-denkt="1"]::after { content: "\\258D";
                                   animation: ux-blinken 1s steps(2) infinite; }

/* -- Knopf 1: Interview als Scheinwerfer ---------------------------- */
#interview { width: var(--rec-hoehe); height: var(--rec-hoehe);
             border-radius: 50%; border: 3px solid var(--rec);
             background: var(--grund-2); color: var(--text); font: inherit;
             font-family: var(--schrift-tech); font-size: .66rem;
             letter-spacing: .03em; text-transform: uppercase;
             display: flex; flex-direction: column; align-items: center;
             justify-content: center; gap: .15rem; padding: 0 .2rem; }
/* letter-spacing .03em statt .1em: "AUFNEHMEN" stiess bei .1em am Handy
   an den Ring (Abnahme-Bild nach dem Review an 834edbf). */
#interview::before { content: ""; width: 1.1rem; height: 1.1rem;
                     border-radius: 50%; background: var(--rec); }
#interview:active { transform: scale(.95); }
#interview[data-ux-zustand="startet"] { border-color: var(--warn); }
#interview[data-ux-zustand="startet"]::before { background: var(--warn);
    animation: ux-puls .7s ease-in-out infinite; }
#interview[data-ux-zustand="laeuft"] { background: var(--rec);
    color: var(--auf-rec); border-color: var(--auf-rec);
    width: calc(var(--rec-hoehe) + 1.1rem);
    height: calc(var(--rec-hoehe) + 1.1rem); }
#interview[data-ux-zustand="laeuft"]::before { background: var(--auf-rec);
    border-radius: .2rem; animation: ux-puls 1.1s ease-in-out infinite; }
#interview[data-ux-zustand="laedt"] { border-color: var(--warn);
                                      color: var(--warn); }
#interview[data-ux-zustand="laedt"]::before { background: var(--warn); }
#interview[aria-busy="true"] { cursor: progress; }
/* Neben dem Knopf statt darunter: sonst nimmt der Fuss ein Drittel des
   Telefons (gemessen am Entwurf vor der Nachbesserung). */
.fuss { flex-direction: row; flex-wrap: wrap; align-items: center;
        gap: .5rem .9rem; background: var(--grund);
        border-top: 1px solid var(--linie); }
#ux-rec-zeile { flex: 1; font-family: var(--schrift-skript);
                font-size: 1.1rem; color: var(--text); }
/* P2, Aufgabe 2: vorher ``var(--rec)`` -- als Text nur 3.45:1 (B) auf dem
   Grund, unter AA. Der laufende Zustand steht im Wortlaut und in der Uhr. */
#interview[data-ux-zustand="laeuft"] + #ux-rec-zeile { color: var(--text); }

/* -- Knopf 2: Push-to-Talk als Pille -------------------------------- */
#ptt { min-width: 3.5rem; min-height: var(--tippflaeche);
       border-radius: 1.4rem; border: 1px dashed var(--signal);
       background: var(--grund-2); color: var(--signal);
       font-family: var(--schrift-tech); font-size: .76rem;
       letter-spacing: .06em; text-transform: uppercase;
       touch-action: none; padding: 0 .7rem; }
#ptt[data-haelt="1"] { background: var(--signal); color: var(--auf-signal);
                       border-style: solid; font-weight: 700; }

/* -- Messwerk ------------------------------------------------------- */
#uhr { font-family: var(--schrift-tech); font-variant-numeric: tabular-nums;
       font-size: 1.4rem; color: var(--signal); }
#pegel { height: .6rem; background: var(--grund-3);
         border: 1px solid var(--linie); border-radius: 1rem;
         overflow: hidden; }
#pegel span { display: block; height: 100%; background: var(--rec);
              transition: width var(--takt-schnell) linear; }
#warteschlange { font-family: var(--schrift-tech); font-size: .78rem;
                 color: var(--signal); min-height: 1.1em; }
.zeile input { background: var(--grund-2); color: var(--text);
               border: 1px solid var(--rand); border-radius: 1.4rem;
               min-height: var(--tippflaeche); }
#senden { background: var(--signal); color: var(--auf-signal); border: 0;
          border-radius: 1.4rem; min-height: var(--tippflaeche);
          padding: 0 1rem; font-weight: 700; }
/* Die Beschriftung schreibt ``_CHAT_JS`` ("Interview laeuft · 0:03"),
   und A2 setzt sie bei ``data-laeuft="1"`` auf 1.15rem -- im Kreis ragte
   sie links und rechts hinaus (Browserlauf 03.10.2026). Kleingeschrieben
   war sie unlesbar und zeigte eine andere Sekunde als ``#uhr`` daneben
   (Review an 834edbf). Laeuft die Aufnahme, ist sie deshalb nur noch fuer
   Vorleseprogramme da: ``font-size: 0`` laesst den Text im Knopf (und damit
   seinen Namen), das Stopp-Quadrat (``::before``, in rem) bleibt. Zeit und
   Zustand stehen gross in ``#uhr`` und ``#ux-rec-zeile``. In der Pause
   bleibt sie sichtbar, klein und umbrechend: dort ist "pausiert" die
   Information, die sonst nirgends steht. */
#interview[data-laeuft="1"] { font-size: .62rem; letter-spacing: .02em;
    line-height: 1.15; min-height: 0; padding: .35rem; overflow: hidden;
    white-space: normal; text-align: center; overflow-wrap: anywhere; }
#interview[data-laeuft="1"]:not([data-pausiert="1"]) { font-size: 0;
    letter-spacing: 0; }
/* Der Fuss ist hier eine umbrechende ZEILE: ohne volle Breite nahm die
   Eingabezeile ihre Inhaltsbreite, und "Senden" stand am Handy halb
   ausserhalb des Bildes (Browserlauf 03.10.2026). */
.zeile { flex: 1 1 100%; min-width: 0; }
/* Uhr und Pegel teilen sich die erste Zeile, wie im Entwurf; ohne Breite
   schrumpfte der Pegel in der Zeile auf einen Strich. */
#pegel { flex: 1 1 calc(100% - 7rem); min-width: 4rem; }
/* Meldungen ueber der Knopfzeile bekommen eine eigene Zeile: am Laptop
   stand die Warteschlange sonst links neben dem Kreis und schob den
   Hinweistext darunter (Review an 834edbf, Akte-Bild). Leer kostet sie
   keine Zeile. */
#warteschlange, #fehler, .angehalten { flex: 1 1 100%; }
#warteschlange:empty { display: none; }
""" + _CHAT_FLAECHEN
#: Der Arbeitsstand: eine Karte je Feld. Die Formulare der Gruppenseite
#: (``web._rahmen``, ``_textfeld``, ``_dropdown``) bleiben, wie sie sind --
#: gestaltet werden nur Flaeche, Rand und Beschriftung.
_STAND = """
body { background: var(--grund); color: var(--text); }
/* Review an 834edbf, Rundgang ueber alle sichtbaren Texte: ``web._CSS_GRUPPE``
   setzt die Eingabefelder mit ``.feld``-Praefix WEISS bei geerbter (heller)
   Schrift -- 1.23:1, die Werte der Gruppe waren unlesbar. Dazu der weisse
   Kasten um den Szenentext und Daempfung ueber ``opacity`` statt Farbe. */
.feld select, .feld input[type=text], .feld textarea {
    background: var(--grund-3); color: var(--text); border-color: var(--rand); }
.szene .volltext { background: var(--grund-2); border-color: var(--linie); }
.leer, .zeit { opacity: 1; color: var(--text-leise); }
.zeit a { color: var(--signal); }
[data-feld] { background: var(--grund-2); border: 1px solid var(--linie);
              border-radius: var(--radius); padding: .55rem .65rem;
              margin: 0 0 .5rem; }
dt { font-family: var(--schrift-tech); font-size: .72rem; letter-spacing: .1em;
     text-transform: uppercase; color: var(--text-leise); opacity: 1; }
dd { margin: .15rem 0 0; }
input[type="text"], textarea, select { font: inherit; color: var(--text);
     background: var(--grund-3); border: 1px solid var(--rand);
     border-radius: var(--radius); min-height: var(--tippflaeche);
     padding: .45rem .6rem; width: 100%; }
button { font: inherit; min-height: var(--tippflaeche);
         background: var(--grund-3); color: var(--text);
         border: 1px solid var(--rand); border-radius: var(--radius);
         padding: .4rem .8rem; }
blockquote { border-left: 2px solid var(--warn); color: var(--warn);
             font-family: var(--schrift-skript); font-style: italic; }
.art { background: var(--grund-3); color: var(--text-leise);
       border-radius: 1rem; }
details > summary { min-height: var(--tippflaeche); display: flex;
                    align-items: center; cursor: pointer; }
/* P2, Aufgabe 3 -- Zweck: die Seite gehoert der Gruppe und der Diskussion
   im Plenum, 100 % Inhalt. Am Beamer waechst die Schrift mit der Breite
   (``clamp`` statt einer Medienabfrage -- die wuerde hier gescopt). */
#stand-inhalt { font-size: clamp(1rem, .8rem + .35vw, 1.2rem); }
/* Die Abschnittsueberschriften ("Where we are", "Scenes", ...) gliedern die
   Seite -- aus ``_BASIS`` kamen sie in ``--text-leise`` und damit leiser als
   der Text darunter (Review an 2841d83). Jetzt in Textfarbe, mit Gewicht
   und in der Serife der Buehne. */
h2 { color: var(--text); font-family: var(--schrift-skript); font-weight: 700;
     font-size: 1.3em; letter-spacing: .01em; border-bottom-color: var(--rand); }
/* Die Speichern-Knoepfe waren helle Sandflaechen aus ``_CSS_GRUPPE`` -- je
   Figur vier davon, die lautesten Flaechen der Seite. Jetzt ruhig: Rand
   und Signalfarbe, der Inhalt der Felder ist das Helle. */
.feld button { background: transparent; color: var(--signal);
               border: 1px solid var(--rand); border-radius: var(--radius);
               min-height: var(--tippflaeche); }
.feld button:hover, .feld button:focus-visible { border-color: var(--signal); }
.feld button[disabled] { color: var(--text-leise); opacity: 1; }
.feld .hinweis { color: var(--text-leise); opacity: 1; }
.feld .hinweis.schlecht { color: var(--signal); }
.figur { border-top-color: var(--linie); }
.figur [data-feld] { margin-bottom: .3rem; }
/* Der Weg zur Probenansicht: deutlich, aber kein heller Fleck. */
.probenansicht a { background: var(--grund-2); color: var(--signal);
                   border: 1px solid var(--rand); border-radius: var(--radius); }
/* Auf der vereinten Seite IST der Chat ein Tab -- der Link "Chat mit dem
   Bot" fuehrte per 302 zurueck auf dieselbe Seite. Nur ausgeblendet: die
   Einzelseite ``gruppe_html`` behaelt ihn. */
p:has(> a[href$="/chat"]) { display: none; }
/* Die Festlegungen: ihre Zeilenregeln stehen in ``web._CSS_LEITFADEN``
   und kamen hier nie an -- die Bereichsmarke klebte am Text
   ("stilEvery scene ..."). */
.festlegung { display: flex; flex-wrap: wrap; align-items: baseline;
              gap: .1rem .6rem; padding: .35rem 0;
              border-top: 1px solid var(--linie); }
.festlegung:first-child { border-top: none; }
.festlegung .marke { font-family: var(--schrift-tech); font-size: .72rem;
                     letter-spacing: .08em; text-transform: uppercase;
                     color: var(--text-leise); opacity: 1; }
.festlegung .feld { flex: 0 0 auto; margin: 0; }
.festlegung [data-feld] { padding: 0; border: 0; background: none; margin: 0; }
/* Was noch fehlt: die Arbeitsliste, deshalb mit Signalstrich. */
ul.fehlstellen { border-left-color: var(--signal); }
/* Die Stueckkarte: eine Checkliste, keine Aufzaehlung -- das Offene leiser. */
ul.stueckkarte { list-style: none; padding-left: 0; }
ul.stueckkarte li { margin: .2rem 0; }
ul.stueckkarte li.offen { color: var(--text-leise); }
table.anteile th, table.anteile td, table.uebersicht td { border-bottom-color: var(--linie); }
"""
#: Was ``web._CSS_TEXTBUCH`` fuer helles Papier gesetzt hat und auf dem
#: dunklen Grund zu blass wird (Review an 834edbf): ein dunkles Ocker fuer
#: die Wege (~2.8:1), Daempfung ueber ``opacity`` statt ueber eine Farbe
#: (``.leer``, ``.offen``, ``.regie``, ``.marke``) -- ``opacity`` auf
#: ``--text-leise`` faellt unter 4.5 --, und eine HELLE Flaeche unter der
#: hervorgehobenen Replik des Rollenfilters. Fuer beide Entwuerfe gleich.
#: Gedaempft wird hier ueber die Farbe; der Rollenfilter darf weiter ueber
#: ``opacity`` daempfen, das ist dort die Aussage ("nicht deine Zeile").
#:
#: Die hervorgehobene Replik wird nur UMGEFAERBT, der Filter selbst bleibt
#: bei ``_CSS_TEXTBUCH`` (``test_der_rollenfilter_bleibt_unangetastet``:
#: kein ``data-figur`` hier). Die vierfache Klasse ist dieselbe Technik wie
#: ``.roadmap.roadmap`` oben: (0,4,0) schlaegt ``body[data-figur] .replik
#: .aktiv`` (0,3,1) auf der Probenansicht, und gescopt (0,5,0) die
#: Panel-Fassung (0,4,0) -- ohne den Knoten zu aendern, den sie trifft.
_SKRIPT_FLAECHEN = """
.wege a { color: var(--signal); }
.leer, .offen, .regie, .leiste .marke { opacity: 1; color: var(--text-leise); }
.replik.aktiv.aktiv.aktiv.aktiv { background: var(--grund-2);
                                  border-left-color: var(--signal); }
"""

#: Das Textbuch, Entwurf A: Terminal-Kopf, Manuskript-Koerper. Der
#: Sprechername steht IN der Zeile (Monospace, Signalfarbe), die Replik
#: daneben in der Skriptschrift.
_SKRIPT_A = """
body { background: var(--grund); color: var(--text); }
""" + _SKRIPT_FLAECHEN + """
.szenenkopf { font-family: var(--schrift-tech); font-size: .8rem;
              letter-spacing: .12em; text-transform: uppercase;
              color: var(--text-leise); border-bottom: 1px solid var(--linie);
              padding-bottom: .25rem; }
.angaben, .besetzung { font-family: var(--schrift-tech); font-size: .8rem;
                       color: var(--text-leise); opacity: 1; }
.text, .probe-szene { font-family: var(--schrift-skript); font-size: 1.12rem;
                      line-height: 1.55; }
.replik { margin: 0 0 .55rem; }
.sprecher { font-family: var(--schrift-tech); font-size: .92rem;
            letter-spacing: .08em; color: var(--signal); font-weight: 400; }
.regie { font-style: italic; color: var(--text-leise); }
.regie-zeile { font-style: italic; color: var(--text-leise); margin: 0 0 .7rem; }
.prosa { margin: 0 0 .6rem; }
.rollen button, .leiste button { min-height: var(--tippflaeche);
    padding: .35rem .7rem; border: 1px solid var(--rand); border-radius: 1.2rem;
    background: var(--grund-2); color: var(--text); font-size: .85rem; }
.leiste button[aria-pressed="true"] { background: var(--signal);
    color: var(--auf-signal); border-color: var(--signal); font-weight: 700; }
"""

#: Das Textbuch, Entwurf B: Manuskript. Der Sprechername steht auf einer
#: EIGENEN Zeile darueber -- die Form eines gedruckten Textbuchs.
_SKRIPT_B = """
body { background: var(--grund); color: var(--text); }
""" + _SKRIPT_FLAECHEN + """
.szenenkopf { font-family: var(--schrift-skript); font-size: 1.25rem;
              color: var(--signal); border-bottom: 1px solid var(--linie);
              padding-bottom: .3rem; }
.angaben, .besetzung { font-family: var(--schrift-tech); font-size: .78rem;
                       color: var(--text-leise); opacity: 1; }
.text, .probe-szene { font-family: var(--schrift-skript); font-size: 1.15rem;
                      line-height: 1.62; }
.replik { margin: 0 0 .6rem; }
.sprecher { display: block; font-family: var(--schrift-tech); font-size: .88rem;
            letter-spacing: .1em; color: var(--signal); font-weight: 400; }
.regie { font-style: italic; color: var(--text-leise); }
.regie-zeile { font-style: italic; color: var(--text-leise); margin: 0 0 .8rem; }
.prosa { margin: 0 0 .65rem; }
.rollen button, .leiste button { min-height: var(--tippflaeche);
    padding: .35rem .8rem; border: 1px solid var(--rand); border-radius: 1.4rem;
    background: var(--grund-2); color: var(--text);
    font-family: var(--schrift-tech); font-size: .82rem; letter-spacing: .06em; }
.leiste button[aria-pressed="true"] { background: var(--signal);
    color: var(--auf-signal); border-color: var(--signal); font-weight: 700; }
"""


#: Das Effekt-JavaScript. Vanilla, ES5-nah wie ``_BEARBEITEN_JS`` und
#: ``_CHAT_JS`` -- kein Build, kein Framework.
#:
#: **Es aendert kein Markup von A2/W.** Was die Gestaltung zusaetzlich
#: braucht, legt es selbst an (``#ux-rec-zeile``, ``#ux-balken``,
#: ``#ux-vorhang``, ``#ux-ansage``, ``#ux-belohnung``) -- alles mit dem
#: Praefix ``ux-``, damit im Fehlerfall klar ist, wem es gehoert.
#:
#: **Es schreibt nie in ``#interview.textContent``**: das tut ``_CHAT_JS``
#: (Karte A2, Befund 2 im Plan-Kopf), und zwei Schreiber auf einem Knoten
#: sind ein Fehler, der erst im Workshop auffaellt.
#:
#: Faellt es aus, bleibt die Seite vollstaendig bedienbar: jeder Zustand,
#: den es zeigt, hat schon eine textliche Entsprechung aus A2/W.
_GESTALT_JS = """
(function () {
  'use strict';
  var RUHIG = window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var TAKT_MOMENT = __TAKT_MOMENT__;
  var MOMENT = '__MOMENT__';
  var TEXTE = __TEXTE__;
  var el = function (id) { return document.getElementById(id); };
  // Die Bausteine kommen in den Aufgaben 5 bis 9. Ohne sie tut dieses
  // Skript nichts -- und genau das soll es dann auch tun.
  __BAUSTEINE__
})();
"""


#: Baustein 1: der Denk-Zustand.
#:
#: ``#tippt`` traegt seit Karte A2 den Text ("schreibt ..."); diese Zeile
#: macht daraus eine Terminalzeile mit Cursor. Sie liest nur, ob dort
#: etwas steht -- den Text setzt weiterhin ``_CHAT_JS``.
#:
#: **Warum ein MutationObserver und kein Intervall:** der Zustand wechselt
#: hoechstens alle zwei Sekunden (Polltakt), und ein Intervall, das
#: nichts findet, laeuft trotzdem -- auf einem Telefon, das in der Tasche
#: liegt, den ganzen Workshop lang.
_JS_DENKT = """
  (function denkt() {
    var feld = el('tippt');
    if (!feld) { return; }
    var pruefe = function () {
      feld.dataset.uxDenkt = (feld.textContent || '').trim() ? '1' : '0';
    };
    new MutationObserver(pruefe).observe(
      feld, { childList: true, characterData: true, subtree: true });
    pruefe();
  })();
"""


#: Baustein 2: der Fortschritt in der zugeklappten Aktzeile.
#:
#: Gerechnet aus dem, was ohnehin im DOM steht -- **kein neuer Schluessel
#: im Zustands-Poll und kein SQL**. In A ist das EIN Balken (Breite ueber
#: ``--fortschritt``), in B sind es sieben Lichter (je eins je Akt, mit
#: ``data-stand``). Beides derselbe Code, weil beides aus denselben zwei
#: Zahlen faellt.
#:
#: Die Zahl 7 steht nirgends: ``phasen.PHASEN`` hat sich seit dem
#: 04.09.2026 dreimal geaendert, und eine feste Sieben waere beim
#: naechsten Mal falsch.
_JS_FORTSCHRITT = """
  (function fortschritt() {
    var erste = el('roadmap');
    if (!erste) { return; }
    // Karte W tauscht die Aktfolge nach einem Phasenklick per outerHTML
    // aus (/teil/roadmap) -- Akt-Marke und Lichter waren danach weg
    // (Review an 834edbf, im Akte-Bild sichtbar). Deshalb: dekorieren,
    // und jede neue #roadmap im selben Elternknoten erneut dekorieren.
    // Der Vergleich in W laeuft gegen den Server-Text, nicht gegen das
    // DOM -- das erneute Dekorieren loest also keinen Tausch aus.
    var eltern = erste.parentNode;
    var dekoriere = function () {
      var roadmap = el('roadmap');
      if (!roadmap || roadmap.querySelector('#ux-balken')) { return; }
      schmuecke(roadmap);
    };
    if (eltern) {
      new MutationObserver(dekoriere).observe(eltern, { childList: true });
    }
    dekoriere();

    function schmuecke(roadmap) {
    var summary = roadmap.querySelector('summary');
    var phasen = roadmap.querySelectorAll('.phase');
    if (!summary || !phasen.length) { return; }

    var balken = document.createElement('span');
    balken.id = 'ux-balken';
    if (MOMENT === 'vorhang') {           // Entwurf B: ein Licht je Akt
      for (var i = 0; i < phasen.length; i++) {
        var licht = document.createElement('i');
        var knoten = phasen[i];
        licht.dataset.stand = knoten.classList.contains('aktiv') ? 'aktiv'
          : (knoten.querySelector('.aufgabe:not(.erledigt)') ? 'offen' : 'fertig');
        balken.appendChild(licht);
      }
    } else {                              // Entwurf A: ein Balken
      balken.appendChild(document.createElement('i'));
      var alle = roadmap.querySelectorAll('.aufgabe').length;
      var fertig = roadmap.querySelectorAll('.aufgabe.erledigt').length;
      balken.style.setProperty('--fortschritt',
        (alle ? Math.round(fertig * 100 / alle) : 0) + '%');
    }
    summary.appendChild(balken);

    // Die Akt-Beschriftung VOR den Text von Karte W, nicht statt ihm:
    // dort steht "Phase 3 von 7 · Interviews — 1/3", und das ist die
    // Wahrheit aus der Datenbank.
    var aktiv = roadmap.querySelector('.phase.aktiv');
    if (aktiv && TEXTE.akt_kopf) {
      var marke = document.createElement('b');
      marke.className = 'ux-akt';
      marke.textContent = TEXTE.akt_kopf
        .replace('{nummer}', (Array.prototype.indexOf.call(phasen, aktiv) + 1))
        .replace('{gesamt}', phasen.length);
      summary.insertBefore(marke, summary.firstChild);
    }
    }
  })();
"""


#: Baustein 2b: was als Naechstes kommt (P2, Aufgabe 2, Punkt 2).
#:
#: Birk: "die wichtigen sachen auf einen blick". Wo die Gruppe steht, sagt
#: die Aktzeile; was als Naechstes kommt, stand nur in der zugeklappten
#: Aktfolge. Diese Zeile holt es darunter -- ueber der Tableiste, also auf
#: jedem Tab im ersten Blick.
#:
#: **Nur aus dem DOM, wie ``_JS_FORTSCHRITT``**: die erste noch nicht
#: erledigte Aufgabe der aktiven Phase (offen oder laufend -- wortgleich,
#: ohne das Zeichen davor); ist die Phase durch, die naechste Phase; gibt
#: es keine, steht nichts da (eine Zeile "nichts mehr" waere Laerm). Kein
#: neuer Schluessel, kein Endpunkt. Die Zeile steht NEBEN ``#roadmap``,
#: nicht darin: Karte W tauscht ``#roadmap`` per ``outerHTML`` aus
#: (/teil/roadmap), ein Kind darin waere danach weg. Nach dem Tausch rechnet
#: der Beobachter am Elternknoten die Zeile neu. Text nur ueber
#: ``textContent``. Im Interview blendet ``_INTERVIEW`` sie aus.
_JS_NAECHSTES = """
  (function naechstes() {
    var erste = el('roadmap');
    if (!erste || !erste.parentNode || !TEXTE.naechstes) { return; }
    var eltern = erste.parentNode;
    var zeile = document.createElement('p');
    zeile.id = 'ux-naechstes';
    zeile.hidden = true;
    eltern.insertBefore(zeile, erste.nextSibling);
    var zuletzt = null;

    var name = function (phase) {
      var k = phase.querySelector('.phase-knopf, .phase-name');
      return k ? (k.dataset.bezeichnung || k.textContent || '').trim() : '';
    };
    var was = function (roadmap) {
      var aktiv = roadmap.querySelector('.phase.aktiv');
      if (!aktiv) { return ''; }
      var offen = aktiv.querySelector('.aufgabe:not(.erledigt)');
      if (offen) {
        return (offen.textContent || '').trim().replace(/^\\S+\\s+/, '');
      }
      var folgende = aktiv.nextElementSibling;
      while (folgende && !folgende.classList.contains('phase')) {
        folgende = folgende.nextElementSibling;
      }
      var bez = folgende ? name(folgende) : '';
      return bez ? (TEXTE.naechste_phase || '{bezeichnung}')
        .replace('{bezeichnung}', bez) : '';
    };
    var rechne = function () {
      var roadmap = el('roadmap');
      var sache = roadmap ? was(roadmap) : '';
      if (sache === zuletzt) { return; }
      zuletzt = sache;
      while (zeile.firstChild) { zeile.removeChild(zeile.firstChild); }
      zeile.hidden = !sache;
      if (!sache) { return; }
      var teile = TEXTE.naechstes.split('{was}');
      zeile.appendChild(document.createTextNode(teile[0] || ''));
      var b = document.createElement('b');
      b.textContent = sache;
      zeile.appendChild(b);
      zeile.appendChild(document.createTextNode(teile.slice(1).join('')));
      zeile.title = zeile.textContent;
    };
    new MutationObserver(rechne).observe(eltern, { childList: true });
    rechne();
  })();
"""


#: Baustein 3: die vier Zustaende des Aufnahmeknopfes.
#:
#: **Der wichtigste Teil dieser Karte.** Karte A2 kennt nur an/aus; die
#: beiden Uebergaenge (Mikrofonfreigabe laeuft, Segmente werden noch
#: hochgeladen) sind fuer die Gruppe genau die Momente, in denen sie
#: nachdrueckt -- und in Dortmund ist daraus ein Knopf geworden, der 14x
#: in 93 Sekunden gedrueckt wurde.
#:
#: Abgeleitet wird aus dem, was schon im DOM steht:
#:   ruht     -- data-interview="0" und die Warteschlange ist leer
#:   startet  -- gedrueckt, data-interview noch "0" -- oder schon "1",
#:               aber ``#uhr`` noch verborgen (Mikrofon kommt erst)
#:   laeuft   -- data-interview="1" und ``#uhr`` sichtbar (oder Pause)
#:   laedt    -- gerade auf "0" gewechselt, Warteschlange nicht leer
#: **Kein neuer Schluessel im Zustands-Poll, kein SQL.**
#:
#: **Diese Funktion faengt keinen Druck ab.** Dass ``_CHAT_JS`` waehrend
#: eines Uebergangs weiter auf Klicks reagiert, ist ein Logikbefund an
#: Karte A2 (Plan-Kopf, Befund 1) und gehoert dorthin. Hier wird er nur
#: SICHTBAR: aria-busy, cursor: progress, und ein Text, der sagt, was
#: gerade laeuft. Ein stopPropagation hier waere die stille Reparatur,
#: die der Plan verbietet -- und sie wuerde das Problem verstecken,
#: statt es zu loesen.
_JS_AUFNAHME = """
  (function aufnahme() {
    var knopf = el('interview');
    var fuss = el('fuss');
    var warte = el('warteschlange');
    if (!knopf || !fuss) { return; }

    // Die zweite Zeile NEBEN dem Knopf: _CHAT_JS setzt dort textContent.
    var zeile = document.createElement('div');
    zeile.id = 'ux-rec-zeile';
    knopf.parentNode.insertBefore(zeile, knopf.nextSibling);
    knopf.setAttribute('aria-describedby', 'ux-rec-zeile');

    var gedrueckt = 0;
    var zustand = null;

    var setze = function (neu) {
      // Farbe allein traegt keinen Zustand: der Text sagt ihn auch. Die
      // Pause bleibt im Attribut "laeuft" (der Modus ist an), bekommt aber
      // ihren eigenen Satz -- vorher stand dort "Aufnahme laeuft."
      // neben einer stehenden Uhr (P2, Aufgabe 2).
      var satz = (neu === 'laeuft' && knopf.dataset.pausiert === '1')
        ? TEXTE.rec_pausiert : TEXTE['rec_' + neu];
      if (zeile.textContent !== (satz || '')) { zeile.textContent = satz || ''; }
      if (neu === zustand) { return; }
      zustand = neu;
      knopf.dataset.uxZustand = neu;
      knopf.setAttribute('aria-busy',
        (neu === 'startet' || neu === 'laedt') ? 'true' : 'false');
    };

    var uhr = el('uhr');
    var lies = function () {
      var an = fuss.dataset.interview === '1';
      var laden = !!(warte && (warte.textContent || '').trim());
      // data-interview="1" setzt _CHAT_JS schon beim Druck, BEVOR das
      // Mikrofon da ist (Browserlauf 03.10.2026). "laeuft" erst, wenn die
      // Uhr steht -- sie geht erst mit dem Recorder an -- oder wenn das
      // Telefon eine Pause zeigt (dann laeuft hier nichts, aber der Modus
      // ist an, wie bisher).
      var nimmt = !uhr || !uhr.hidden || knopf.dataset.pausiert === '1';
      if (an && nimmt) { setze('laeuft'); return; }
      if (an) { setze('startet'); return; }
      if (laden) { setze('laedt'); return; }
      // Nach dem Druck bleibt "startet" stehen, bis der Poll den Modus
      // meldet -- bei einer Mikrofonfreigabe sind das leicht zwei
      // Sekunden, und genau da wurde in Dortmund nachgedrueckt.
      if (gedrueckt && Date.now() - gedrueckt < 20000) { setze('startet'); return; }
      setze('ruht');
    };

    knopf.addEventListener('click', function () {
      // Kein Abfangen dieses Klicks in irgendeiner Form: _CHAT_JS muss
      // ihn weiterhin unveraendert sehen (Befund 1).
      gedrueckt = (fuss.dataset.interview === '1') ? 0 : Date.now();
      lies();
    });

    new MutationObserver(function () {
      if (fuss.dataset.interview === '1') { gedrueckt = 0; }
      lies();
    }).observe(fuss, { attributes: true, attributeFilter: ['data-interview'] });
    new MutationObserver(lies).observe(
      knopf, { attributes: true, attributeFilter: ['data-pausiert'] });
    if (uhr) {
      new MutationObserver(lies).observe(
        uhr, { attributes: true, attributeFilter: ['hidden'] });
    }

    if (warte) {
      new MutationObserver(lies).observe(
        warte, { childList: true, characterData: true, subtree: true });
    }
    lies();
  })();
"""


#: Baustein 4: der Aktwechsel und die zwei Belohnungen.
#:
#: **Der Moment haengt sich AN den Klick von Karte W, er ersetzt ihn
#: nicht.** Kein preventDefault, kein stopPropagation -- sonst faellt der
#: Vorhang vor eine leere Buehne, weil der POST nie rausgeht.
#:
#: **Keine Belohnung braucht einen Serverschluessel.** Beide fallen aus
#: dem DOM: der Aktwechsel aus dem bestaetigenden Druck, das fertige
#: Interview aus dem Wechsel von ``data-interview`` samt leerer
#: Warteschlange. Eine dritte ("Szene fertig") ist bewusst NICHT gebaut --
#: sie muesste aus einem Blasentext erraten werden, und Raten ist genau
#: das, was dieses Projekt anderswo abgeschafft hat.
_JS_MOMENT = """
  (function momente() {
    var vorhang = document.createElement('div');
    vorhang.id = 'ux-vorhang';
    vorhang.setAttribute('aria-hidden', 'true');
    var ansage = document.createElement('div');
    ansage.id = 'ux-ansage';
    ansage.setAttribute('aria-hidden', 'true');
    ansage.hidden = true;
    var name = document.createElement('b');
    ansage.appendChild(name);
    var kasten = document.createElement('div');
    kasten.id = 'ux-belohnung';
    kasten.hidden = true;
    kasten.setAttribute('aria-live', 'polite');
    var kopf = document.createElement('b');
    var satz = document.createElement('p');
    kasten.appendChild(kopf);
    kasten.appendChild(satz);
    document.body.appendChild(vorhang);
    document.body.appendChild(ansage);
    document.body.appendChild(kasten);

    var belohnungTakt = null;
    // ``art`` traegt, WOFUER belohnt wird: nur der Aktwechsel darf
    // auftreten, die Bestaetigung nach einem Interview kommt ruhig
    // (P2, Aufgabe 2: Effekte nur beim Phasenwechsel).
    var belohne = function (titel, text, art) {
      if (!titel) { return; }
      kasten.dataset.art = art || '';
      kopf.textContent = titel;
      satz.textContent = text || '';
      kasten.hidden = false;
      kasten.dataset.an = '1';
      if (belohnungTakt) { clearTimeout(belohnungTakt); }
      belohnungTakt = setTimeout(function () {
        kasten.hidden = true;
        kasten.dataset.an = '0';
      }, 4200);
    };

    var moment = function (titel) {
      name.textContent = titel || '';
      if (RUHIG) {
        // Kein Effekt -- die Ansage allein, und die bleibt lesbar stehen.
        ansage.hidden = false;
        setTimeout(function () { ansage.hidden = true; }, 900);
        return;
      }
      vorhang.dataset.an = '1';
      setTimeout(function () { ansage.hidden = false; },
                 MOMENT === 'vorhang' ? Math.round(TAKT_MOMENT * 0.35) : 0);
      setTimeout(function () {
        vorhang.dataset.an = '0';
        ansage.hidden = true;
      }, TAKT_MOMENT + 40);
    };

    // Der ZWEITE Druck auf einen Akt-Knopf: Karte W hat beim ersten die
    // Rueckfrage hineingeschrieben (data-sicher="1").
    document.addEventListener('click', function (ev) {
      var knopf = ev.target.closest ? ev.target.closest('.phase-knopf') : null;
      if (!knopf || knopf.dataset.sicher !== '1') { return; }
      var vorher = document.querySelector('.phase.aktiv .phase-knopf');
      moment(knopf.dataset.bezeichnung || '');
      if (vorher && vorher !== knopf) {
        belohne(TEXTE.belohnung_akt, (TEXTE.belohnung_akt_satz || '')
          .replace('{akt}', (vorher.dataset.bezeichnung || '')), 'akt');
      }
    });

    // Ein Interview ist eingetroffen: data-interview 1 -> 0, und die
    // Warteschlange ist leer.
    var fuss = el('fuss');
    var warte = el('warteschlange');
    if (!fuss) { return; }
    var lief = fuss.dataset.interview === '1';
    var pruefe = function () {
      var an = fuss.dataset.interview === '1';
      var laden = !!(warte && (warte.textContent || '').trim());
      if (lief && !an && !laden) {
        belohne(TEXTE.belohnung_aufnahme, TEXTE.belohnung_aufnahme_satz,
                'aufnahme');
        lief = false;
      }
      if (an) { lief = true; }
    };
    new MutationObserver(pruefe).observe(
      fuss, { attributes: true, attributeFilter: ['data-interview'] });
    if (warte) {
      new MutationObserver(pruefe).observe(
        warte, { childList: true, characterData: true, subtree: true });
    }
  })();
"""


#: Baustein 5: der Interview-Modus (P2, Aufgabe 2).
#:
#: Birk: "interviews sauber durchfuehren ohne ablenkung". Das Telefon liegt
#: im Interview oft vor der interviewten Person -- also zeigt es dann nur
#: Zustand, Dauer, Pegel und Stopp. Das Skript setzt dafuer EIN Attribut an
#: die Wurzel (``html[data-ux-interview="1"]``), den Rest macht das CSS in
#: ``_INTERVIEW``.
#:
#: **Woran ein laufendes Interview zu erkennen ist** -- nur am DOM, das
#: ``_CHAT_JS`` ohnehin schreibt: ``#fuss[data-interview="1"]`` UND ``#uhr``
#: sichtbar. ``data-interview`` allein reicht nicht: es steht schon beim
#: Druck auf "1" (Mikrofon kommt erst) und auch dann, wenn ein ANDERES
#: Telefon den Modus haelt -- dort bleibt ``#uhr`` verborgen. Push-to-Talk
#: fasst beides nie an (es schaltet keinen Modus und keine Uhr), und auch
#: "Brainstorm" (Phase 4) laesst ``data-interview`` auf "0". Die Pause
#: bleibt Interview: die Uhr steht, ist aber sichtbar.
#:
#: **Wake Lock**: ``navigator.wakeLock`` nur, wenn es ihn gibt; jede
#: Ablehnung wird geschluckt (Akku-Sparmodus, kein Fokus, alte Browser).
#: Freigegeben beim Stopp, bei jedem Ende des Modus (auch Mikrofonfehler:
#: dann versteckt ``_CHAT_JS`` die Uhr) und bei ``visibilitychange`` ->
#: hidden; zurueck im Bild wird er neu angefordert, solange das Interview
#: laeuft. **Er haelt nur den Bildschirm an** -- dass die Aufnahme bei
#: gesperrtem Telefon weiterlaeuft, kann er nicht versprechen (Bericht,
#: Punkt 5).
#:
#: **Der Leitfaden** steht schon auf der Seite (``pre.leitfaden`` im
#: Arbeitsstand, ``web._leitfaden_html``) -- kein neuer Endpunkt, keine
#: neuen Daten. Er wird beim Eintritt in den Modus als Text kopiert
#: (``textContent``, nie HTML) und liegt zugeklappt bereit.
_JS_INTERVIEW = """
  (function interviewModus() {
    var fuss = el('fuss');
    var uhr = el('uhr');
    if (!fuss || !uhr) { return; }
    var wurzel = document.documentElement;
    var will = false;
    var sperre = null;      // null, 'unterwegs' oder das WakeLockSentinel
    var anfrage = 0;

    var leitfaden = document.createElement('details');
    leitfaden.id = 'ux-leitfaden';
    leitfaden.hidden = true;
    var titel = document.createElement('summary');
    titel.textContent = TEXTE.leitfaden || '';
    var inhalt = document.createElement('div');
    inhalt.className = 'ux-leitfaden-text';
    leitfaden.appendChild(titel);
    leitfaden.appendChild(inhalt);
    fuss.insertBefore(leitfaden, fuss.firstChild);

    var fuelle = function () {
      var quelle = document.querySelector('pre.leitfaden');
      var text = quelle ? (quelle.textContent || '').trim() : '';
      inhalt.textContent = text;
      leitfaden.open = false;
      leitfaden.hidden = !text;
    };

    var lass = function (s) {
      if (!s || !s.release) { return; }
      try {
        var r = s.release();
        if (r && r.catch) { r.catch(function () {}); }
      } catch (e) { /* schon frei */ }
    };
    var gibFrei = function () {
      anfrage++;
      var s = sperre;
      sperre = null;
      if (s && s !== 'unterwegs') { lass(s); }
    };
    var halte = function () {
      if (!will || sperre || document.hidden) { return; }
      if (!('wakeLock' in navigator) || !navigator.wakeLock ||
          !navigator.wakeLock.request) { return; }
      var nr = ++anfrage;
      sperre = 'unterwegs';
      try {
        Promise.resolve(navigator.wakeLock.request('screen')).then(function (s) {
          if (nr !== anfrage) { lass(s); return; }
          sperre = s || null;
          if (s && s.addEventListener) {
            s.addEventListener('release', function () {
              if (sperre === s) { sperre = null; }
            });
          }
        }, function () { if (nr === anfrage) { sperre = null; } });
      } catch (e) { sperre = null; }
    };

    var pruefe = function () {
      var an = fuss.dataset.interview === '1' && !uhr.hidden;
      if (an === will) { return; }
      will = an;
      if (an) {
        fuelle();
        wurzel.setAttribute('data-ux-interview', '1');
        halte();
      } else {
        wurzel.removeAttribute('data-ux-interview');
        leitfaden.hidden = true;
        gibFrei();
      }
    };

    new MutationObserver(pruefe).observe(
      fuss, { attributes: true, attributeFilter: ['data-interview'] });
    new MutationObserver(pruefe).observe(
      uhr, { attributes: true, attributeFilter: ['hidden'] });
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) { gibFrei(); } else { halte(); }
    });
    window.addEventListener('pagehide', gibFrei);
    pruefe();
  })();
"""


def skript(name: str | None = None, *, chat_vorhanden: bool = True) -> str:
    """Das Effekt-JS mit eingesetzten Werten.

    Platzhalter statt f-String: das Skript ist voll mit geschweiften
    Klammern. Dieselbe Bauart wie ``web_chat._js()`` (Karte A2).

    **UX-Fix an Aufgabe 8:** ``chat_vorhanden=False`` laesst Baustein 3
    (``_JS_AUFNAHME``) weg. Er nennt Elemente, die es nur im Chat-Panel
    gibt (u.a. ``#warteschlange``, ``#interview``, ``#ptt``) -- bei einer
    Telegram-Gruppe (kein Web-Kanal, kein Chat-Panel) rendert
    ``web_vereint.seite`` dieses Panel gar nicht, und dann darf dessen
    Markernamen nicht einmal im ausgelieferten ``<script>`` stehen
    (``tests/test_web_vereint.py::test_telegram_gruppe_hat_kein_chat_panel``
    prueft genau das als Teilstring-Suche). Die Bausteine 1 und 2
    (Denk-Zustand, Fortschritt) bleiben immer drin: sie fragen selbst erst
    ``el('tippt')``/``el('roadmap')`` ab und tun bei Fehlanzeige nichts."""
    gewaehlt = name or entwurf()
    takt = TOKENS[gewaehlt]["takt-moment"].removesuffix("ms")
    bausteine = (_BAUSTEINE if chat_vorhanden
                 else (_JS_DENKT + _JS_FORTSCHRITT + _JS_NAECHSTES))
    return (
        _GESTALT_JS
        .replace("__TAKT_MOMENT__", takt)
        .replace("__MOMENT__", "glitch" if gewaehlt == "a" else "vorhang")
        .replace("__TEXTE__", json.dumps(_mikrotexte(), ensure_ascii=False))
        .replace("__BAUSTEINE__", bausteine)
    )


#: Baustein 1 (Denk-Zustand, Aufgabe 5), Baustein 2 (Fortschritt, Aufgabe 7),
#: Baustein 3 (Aufnahmeknoepfe, Aufgabe 8) und Baustein 4 (Momente,
#: Aufgabe 9) -- alle vier Bausteine sind damit gefuellt.
#: Baustein 5 (Interview-Modus, P2 Aufgabe 2) haengt am Chat-Panel wie
#: Baustein 3 und faellt ohne Chat deshalb mit ihm weg. Baustein 2b
#: ("Als Naechstes", P2 Aufgabe 2) braucht nur ``#roadmap`` und bleibt.
_BAUSTEINE = (_JS_DENKT + _JS_FORTSCHRITT + _JS_NAECHSTES + _JS_AUFNAHME
              + _JS_MOMENT + _JS_INTERVIEW)


def _mikrotexte() -> dict[str, str]:
    """Die Kurztexte, die das Skript in den DOM schreibt.

    Sie gehen als JSON ins Skript, statt als Literal darin zu stehen --
    nur so laufen sie ueber ``T`` (A1) und sind uebersetzbar. Ein Literal
    im JS waere in Padua Deutsch; genau das ist Befund 2 an Karte A2.

    Gelesen wird zur AUFRUFZEIT: der Webdienst laeuft einmal fuer alle
    Gruppen, und ``sprache.code()`` haengt am aktiven Profil."""
    return {
        "rec_ruht": T._TEXT_REC_RUHT,
        "rec_startet": T._TEXT_REC_STARTET,
        "rec_laeuft": T._TEXT_REC_LAEUFT,
        "rec_laedt": T._TEXT_REC_LAEDT,
        "rec_pausiert": T._TEXT_REC_PAUSIERT,
        "leitfaden": T._TEXT_LEITFADEN,
        "akt_kopf": T._TEXT_AKT_KOPF,
        "naechstes": T._TEXT_NAECHSTES,
        "naechste_phase": T._TEXT_NAECHSTE_PHASE,
        "belohnung_akt": T._TEXT_BELOHNUNG_AKT,
        "belohnung_akt_satz": T._TEXT_BELOHNUNG_AKT_SATZ,
        "belohnung_aufnahme": T._TEXT_BELOHNUNG_AUFNAHME,
        "belohnung_aufnahme_satz": T._TEXT_BELOHNUNG_AUFNAHME_SATZ,
    }
