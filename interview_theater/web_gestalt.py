"""Die Gestaltung der Weboberflaeche: Tokens, Komponenten-CSS, Effekt-JS
(01.10.2026, Karte Padua UX).

**Warum ein eigenes Modul.** ``web.py``, ``web_chat.py`` (A2) und
``web_vereint.py`` (W) sind Hotspots -- an allen dreien arbeiten parallel
andere Karten. Gestaltung ist die einzige Schicht, die man vollstaendig
herausloesen kann: sie liest kein SQL, ruft kein Modell, kennt keinen
Endpunkt und aendert kein Markup. Eingehaengt wird sie an fuenf Zeilen
(vier in ``web_vereint.seite``, je eine in ``web.textbuch_html`` und
``web.leitfaden_html``).

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
    "warn", "auf-warn", "rec", "auf-rec",
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
    Paar("signal", "grund-3", "gewaehlter Tab, gedrueckter Filter", 3.0),
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
    "#interview",
    "#interview::before",
    "#pegel span",
    ".tabs button",
    ".phase-knopf",
    ".blase.vorlaeufig::after",   # Karte W
    "#tippt::after",              # Karte W
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
        "#ux-rec-zeile { display: none !important; }\n"
        ".sprecher { color: #000 !important; font-weight: 700; }\n"
        ".regie, .regie-zeile, .angaben, .besetzung { "
        "color: #333 !important; opacity: 1 !important; }\n"
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

#: Gefuellt in Aufgabe 6.
_TABS_A = ""
_TABS_B = ""
#: Gefuellt in Aufgabe 7.
_ROADMAP = ""
#: Gefuellt in Aufgabe 9.
_MOMENTE_A = ""
_MOMENTE_B = ""
_BELOHNUNG = ""
#: Gefuellt in Aufgabe 5 (Chat) und 8 (Aufnahmeknoepfe).
_CHAT_A = ""
_CHAT_B = ""
#: Gefuellt in Aufgabe 6.
_STAND = ""
#: Gefuellt in Aufgabe 10.
_SKRIPT_A = ""
_SKRIPT_B = ""
