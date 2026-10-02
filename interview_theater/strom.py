"""Der Strom: was ein Modell schreibt, waehrend es schreibt (30.09.2026, Karte W).

**Warum es dieses Modul gibt.** Der Gespraechszug laeuft ueber ``LLM.schema``
mit dem Schema ``{"antwort": string}`` (ablauf.SCHEMA) -- was beim Streamen
ankommt, ist also kein Text, sondern ein wachsender JSON-Praefix. ``json.loads``
scheitert daran bis zum letzten Zeichen. ``wert_aus_praefix`` liest den
bisherigen Wert heraus, mit allem, was ein abgeschnittener JSON-String an
Halbheiten mitbringt: ein Backslash ohne Folgezeichen, eine halbe
``\\uXXXX``-Folge, ein High-Surrogate ohne sein Low-Surrogate.

**Kein Prompt aendert sich dafuer.** Das Response-Format bleibt, wie es ist --
der Regressionskorpus (``korpus/``) gilt unveraendert weiter.

**Was sichtbar wird, ist schon gesaeubert** (Entscheidung D): ``sichtbar``
nimmt die VORSCHLAG-Markerzeilen heraus, und zwar auch die gerade erst halb
getippte -- sonst stuende fuer einen Augenblick ``VORSCHLAG BEGR`` im Chat.

**Die Drosselung liegt hier und nicht im Kanal**, damit sie einen Test hat,
der ohne Datenbank auskommt: ``Senke`` bekommt drei Rueckrufe (anlegen,
schreiben, beenden) und eine Uhr.

Schicht Dienste: nur ``vorschlag`` und Standardbibliothek, keine Datenbank,
kein ``repo``.
"""

import time

from interview_theater import vorschlag

#: Wie oft der laufende Text hoechstens in die Datenbank geschrieben wird.
#: **Ein** Wert und nicht zwei (Plan-Kopf, Abweichung 1): eine zweite Regel
#: "oder je N Zeichen" haette den Takt aufgehoben, weil ein schnelles Modell
#: N Zeichen in wenigen Millisekunden liefert. 0,15 s heisst hoechstens
#: ~7 winzige UPDATEs je Sekunde und laufendem Zug -- gegen die Schreiblast
#: eines Gespraechszugs (Nachricht, Aufruf, Journal) faellt das nicht ins
#: Gewicht, und die WAL-Datenbank hat ``busy_timeout = 5000``.
INTERVALL_S = 0.15

_EINFACH = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
            "n": "\n", "r": "\r", "t": "\t"}
_HEX = "0123456789abcdefABCDEF"
_LEERRAUM = " \t\r\n"

#: Das erste Wort jeder Markerzeile (``vorschlag.py``). Hier steht es, um die
#: ANGEFANGENE Zeile zu erkennen -- ``vorschlag.ohne_marker`` kennt nur die
#: fertige.
_MARKERWORT = "VORSCHLAG"


def wert_aus_praefix(praefix: str, feld: str = "antwort") -> str:
    """Der bisherige Wert von ``feld`` aus einem unvollstaendigen JSON-Text.

    Leerer String, solange der Wert noch nicht angefangen hat -- nicht
    ``None``: der Aufrufer schreibt das Ergebnis in eine Blase, und "noch
    nichts" ist dort ein leerer Text."""
    marke = f'"{feld}"'
    i = praefix.find(marke)
    if i < 0:
        return ""
    j = i + len(marke)
    n = len(praefix)
    while j < n and praefix[j] in _LEERRAUM:
        j += 1
    if j >= n or praefix[j] != ":":
        return ""
    j += 1
    while j < n and praefix[j] in _LEERRAUM:
        j += 1
    if j >= n or praefix[j] != '"':
        return ""
    return _ohne_halbes_paar(_zeichen(praefix, j + 1))


def _zeichen(text: str, i: int) -> str:
    """Die Zeichen eines JSON-Strings ab ``i`` bis zum schliessenden
    Anfuehrungszeichen oder bis zum Ende des Praefix.

    Jede Halbheit am Ende faellt weg statt zu werfen: ein Backslash ohne
    Folgezeichen, eine halbe ``\\uXXXX``-Folge. Beim naechsten Stueck ist sie
    vollstaendig und kommt dann mit."""
    aus: list[str] = []
    n = len(text)
    while i < n:
        z = text[i]
        if z == '"':
            break
        if z != "\\":
            aus.append(z)
            i += 1
            continue
        if i + 1 >= n:
            break
        k = text[i + 1]
        if k in _EINFACH:
            aus.append(_EINFACH[k])
            i += 2
            continue
        if k == "u":
            roh = text[i + 2:i + 6]
            if len(roh) < 4 or any(c not in _HEX for c in roh):
                break
            aus.append(chr(int(roh, 16)))
            i += 6
            continue
        break
    return "".join(aus)


def _ohne_halbes_paar(text: str) -> str:
    """Surrogatpaare zusammensetzen, einzeln stehende wegwerfen.

    Ein einzelnes High-Surrogate laesst sich nicht nach UTF-8 kodieren -- es
    wuerde den ``json.dumps`` der SSE-Nutzlast sprengen, und ein Emoji, das
    eine Zehntelsekunde spaeter vollstaendig ankommt, ist den Absturz nicht
    wert."""
    aus: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        z = text[i]
        if "\ud800" <= z <= "\udbff":
            if i + 1 < n and "\udc00" <= text[i + 1] <= "\udfff":
                aus.append(chr(0x10000 + (ord(z) - 0xD800) * 0x400
                               + (ord(text[i + 1]) - 0xDC00)))
                i += 2
            else:
                i += 1
            continue
        if "\udc00" <= z <= "\udfff":
            i += 1
            continue
        aus.append(z)
        i += 1
    return "".join(aus)


def _faengt_marker_an(zeile: str) -> bool:
    """Koennte aus dieser Zeile noch eine Markerzeile werden?"""
    wort = zeile.strip().upper()
    if not wort:
        return False
    return _MARKERWORT.startswith(wort) or wort.startswith(_MARKERWORT)


def sichtbar(text: str) -> str:
    """Der Teiltext, wie die Gruppe ihn sehen darf: ohne Markerzeilen -- auch
    ohne die gerade erst angefangene."""
    kopf, trenner, letzte = text.rpartition("\n")
    if not trenner:
        return "" if _faengt_marker_an(text) else (vorschlag.ohne_marker(text) or "")
    if _faengt_marker_an(letzte):
        text = kopf
    return vorschlag.ohne_marker(text) or ""


class Senke:
    """Nimmt den bisherigen Text entgegen und schreibt ihn gedrosselt weg.

    Drei Rueckrufe statt einer Datenbank, damit dieses Modul in der
    Dienste-Schicht bleibt und der Test ohne SQLite auskommt:

    * ``beginne() -> int`` legt eine Stromzeile an und liefert ihre id,
    * ``schreibe(id, text)`` schreibt den bisherigen **sichtbaren** Text,
    * ``beende(id, zustand, post_id)`` schliesst sie ab.

    Angelegt wird erst beim ersten Stueck: ein Aufruf, der sofort scheitert,
    soll keine leere Blase hinterlassen."""

    def __init__(self, beginne, schreibe, beende, *,
                 intervall_s: float = INTERVALL_S, uhr=time.monotonic) -> None:
        self._beginne = beginne
        self._schreibe = schreibe
        self._beende = beende
        self._intervall_s = intervall_s
        self._uhr = uhr
        self._id: int | None = None
        self._zuletzt = 0.0
        self._offen = ""

    @property
    def strom_id(self) -> int | None:
        return self._id

    def __call__(self, text: str) -> None:
        text = sichtbar(text)
        if self._id is None:
            self._id = self._beginne()
            self._schreibe(self._id, text)
            self._zuletzt = self._uhr()
            self._offen = ""
            return
        if text == self._offen:
            return
        # Epsilon gegen Gleitkomma-Rundung: ``1000.0 + 0.15 - 1000.0`` liefert
        # 0.14999999999997726, nicht 0.15 -- ohne Toleranz bliebe der Takt bei
        # exakt INTERVALL_S verspaetet aus (siehe Test
        # ``test_nach_dem_takt_wird_wieder_geschrieben``).
        if self._uhr() - self._zuletzt < self._intervall_s - 1e-9:
            self._offen = text
            return
        self._schreibe(self._id, text)
        self._zuletzt = self._uhr()
        self._offen = ""

    def _spuele(self) -> None:
        if self._id is not None and self._offen:
            self._schreibe(self._id, self._offen)
            self._offen = ""

    def neu(self) -> None:
        """Ein zweiter Modellaufruf zum selben Zug (``_ohne_echo``,
        ``_ohne_denkspur``): die bisherige Zeile wird verworfen und eine neue
        begonnen -- angehaengt wuerde die verworfene Antwort sichtbar bleiben."""
        self.abbruch()

    def abbruch(self) -> None:
        if self._id is None:
            return
        self._beende(self._id, "abgebrochen", None)
        self._id = None
        self._offen = ""

    def fertig(self, post_id: int | None = None) -> None:
        if self._id is None:
            return
        self._spuele()
        self._beende(self._id, "fertig", post_id)
        self._id = None


def senke(tg, chat_id: int, art: str):
    """Die Senke des Kanals -- oder ``None``, wenn er keine hat.

    **Die eine Stelle**, an der ein Callsite nach Streaming fragt (Entscheidung
    C). ``telegram.Telegram`` bekommt nichts dazu und liefert deshalb ``None``;
    ``web_kanal.WebKanal`` liefert eine Senke, die in ``web_strom`` schreibt."""
    holen = getattr(tg, "strom", None)
    return holen(chat_id, art) if callable(holen) else None


def schliesse(tg, chat_id: int, post_id: int | None = None, *, senke=None) -> None:
    """Der Strom dieses Zuges ist zu Ende und die Nachricht steht.

    **Welcher Strom** (Fix-Runde 1, Befund 1): mit ``senke`` genau dieser --
    so schliessen Szenen- und Prosalauf, die ihre Senke selbst halten. Ohne
    ``senke`` der, den **dieser Thread** fuer diese Gruppe geoeffnet hat
    (``ablauf.antworte``, ``auftragszug``). Nie "der eine der Gruppe": ein
    Szenenlauf und ein Gespraechszug laufen im Betrieb gleichzeitig."""
    _abschluss(tg, chat_id, post_id=post_id, abgebrochen=False, senke=senke)


def verwirf(tg, chat_id: int, *, senke=None) -> None:
    """Der Zug ist gescheitert oder die Antwort wurde verworfen -- die
    vorlaeufige Blase verschwindet, ohne dass eine Nachricht an ihre Stelle
    tritt. ``senke`` wie bei ``schliesse``."""
    _abschluss(tg, chat_id, post_id=None, abgebrochen=True, senke=senke)


def _abschluss(tg, chat_id: int, *, post_id: int | None, abgebrochen: bool,
               senke=None) -> None:
    fertig = getattr(tg, "strom_abschluss", None)
    if callable(fertig):
        if senke is None:
            fertig(chat_id, post_id=post_id, abgebrochen=abgebrochen)
        else:
            fertig(chat_id, post_id=post_id, abgebrochen=abgebrochen, senke=senke)
        return
    # Ein Kanal ohne Verzeichnis, aber mit einer Senke in der Hand: sie
    # selbst abschliessen, damit keine Zeile offen bleibt.
    if senke is not None:
        if abgebrochen:
            senke.abbruch()
        else:
            senke.fertig(post_id)
