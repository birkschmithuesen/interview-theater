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
