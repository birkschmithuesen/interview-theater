"""Schicht 1: mechanische Pruefung der Szenendaten -- ohne jeden Modellaufruf.

**Warum es das zuerst gibt** (Recherche § 5, Umsetzungsreihenfolge § 6). Ein
grosser Teil dessen, was an einem LLM-geschriebenen Stueck peinlich ist, ist
reine Buchhaltung: eine Figur heisst in Szene 2 "Leyla" und in Szene 5
"Layla", jemand spricht, der gar nicht auf der Besetzungsliste steht, eine
Spielerin hat im ganzen Stueck vier Zeilen. Das sind genau die Fehler, die
Jugendliche beim ersten Lesen bemerken -- und sie kosten keinen einzigen
Modellaufruf, wenn man nachzaehlt statt zu fragen.

**Reine Funktionen.** ``conn`` und ``chat_id`` rein, eine Liste ``Befund``
raus. Kein Schreiben, kein Netz, kein Modell, keine Zeitabhaengigkeit.

**Kein Urteil, nur Befunde.** Ein ``Befund`` traegt keine Note und keine
Prozentzahl -- er sagt in einem deutschen Satz, was dasteht, mit Szene und
Figur daneben. Was daraus folgt, entscheidet die Gruppe.

**Das Sprecherzeilen-Parsing ist der kritische Punkt** und deshalb defensiv:
erkennt ``repliken()`` in einer Szene keine Sprecherzeilen (Lied ohne
Sprecherangabe, Prosafassung, Chorzeilen ohne Marker), liefern **alle**
sprecherabhaengigen Checks fuer diese Szene gar keinen Befund -- lieber kein
Befund als ein falscher. Ein falscher Befund kostet Vertrauen, ein fehlender
nur eine Gelegenheit.
"""

from __future__ import annotations

import difflib
import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from interview_theater import repo

log = logging.getLogger(__name__)

#: Die drei Schweregrade dieser Schicht. ``hart`` = im Text nachweisbar
#: falsch, ``verdacht`` = plausibel falsch, muss aber jemand ansehen,
#: ``hinweis`` = auffaellig, nicht falsch.
SCHWEREN = ("hart", "verdacht", "hinweis")

_SCHWERE_RANG = {"hart": 0, "verdacht": 1, "hinweis": 2}


@dataclass(frozen=True)
class Befund:
    """Ein einzelner Befund. Keine Note, keine Prozentzahl.

    ``text`` ist ein Satz auf Deutsch, den die Gruppe ohne Erklaerung liest.
    ``szene`` und ``figur`` sind die Adresse -- eines von beiden darf fehlen
    (der Sprechanteil einer Figur haengt an keiner einzelnen Szene, die
    Formverteilung an keiner einzelnen Figur)."""

    pruefung: str
    schwere: str
    text: str
    szene: int | None = None
    figur: str | None = None

    def als_dict(self) -> dict:
        """Die Form, in der ``repo.lege_dramaturgie_befunde_an`` sie nimmt."""
        return {
            "pruefung": self.pruefung,
            "schwere": self.schwere,
            "text": self.text,
            "szene": self.szene,
            "figur": self.figur,
            "quelle": "mechanik",
        }


@dataclass(frozen=True)
class Replik:
    """Eine erkannte Sprecherzeile: wer, was, in welcher Zeile der Szene."""

    label: str
    text: str
    zeile: int


@dataclass(frozen=True)
class Kandidat:
    """Ein Tschechow-Kandidat: ein Wort, das in einer Szene mehrfach vorkommt
    und danach nie wieder. ``satz`` ist die Stelle, an der es steht -- sie
    geht als Kontext in den A6-Aufruf (Schicht 3)."""

    wort: str
    szene: int
    anzahl: int
    satz: str = ""


# ---------------------------------------------------------------------------
# Sprecherzeilen erkennen
# ---------------------------------------------------------------------------

#: Label, die keine Figur sind, aber eine Sprecherzeile eroeffnen. Sie zaehlen
#: fuer den Wortanteil nicht mit und werden nie als Geisterfigur gemeldet --
#: "CHOR" steht in keinem Figurenverzeichnis und gehoert trotzdem dorthin
#: (``prompts/formen/chor.md``).
KOLLEKTIV = frozenset({"chor", "alle", "beide", "gruppe", "ensemble", "chorus"})

#: Zeilenanfaenge, die wie eine Sprecherzeile aussehen (Wort + Doppelpunkt),
#: aber Struktur sind: Szenenkopf, die Kopfzeilen der Modellantwort
#: (``szene.zerlege``), Planungsfelder, Formmarker aus ``prompts/formen/``.
_STRUKTUR = frozenset({
    "szene", "titel", "kurz", "kurzbeschreibung", "zusammenfassung",
    "anders gemacht", "anders", "ort", "zeit", "anlass", "form", "figuren",
    "ton", "was passiert", "was anders", "kernsaetze", "kernsätze", "regie",
    "pause", "ende", "dauer", "personen", "besetzung", "akt", "bild",
    "prolog", "epilog", "vorspiel", "nachspiel", "musik", "licht", "video",
})

#: Formmarker aus ``prompts/formen/lied.md`` und ``rap.md``. Sie sind keine
#: Sprecher -- steht ein Name in Klammern dahinter (``STROPHE (MIRA)``), ist
#: DER der Sprecher des folgenden Blocks.
_MARKER = frozenset({
    "strophe", "refrain", "hook", "bridge", "intro", "outro", "vers",
    "part", "chorus", "pre-chorus", "prechorus", "coda", "zwischenspiel",
    "instrumental", "beat", "teil",
})

#: ``STROPHE (MIRA)`` / ``HOOK (ALLE)`` -- Marker mit Sprecherangabe.
_MARKER_MIT_NAME = re.compile(r"^([^()\d]{1,20}?)\s*\(([^()]{1,40})\)\s*$")

#: Inline-Regie in einer Replik: ``MIRA:(sieht nicht auf)Replik.``
_INLINE_REGIE = re.compile(r"\([^()]*\)")

_MARKDOWN = "*#`>_-— \t"


def _schluessel(wort: str) -> str:
    """Vergleichsform eines Namens: NFC, ohne Rand, klein."""
    return unicodedata.normalize("NFC", (wort or "")).strip().casefold()


def _nackt(zeile: str) -> str:
    """Die Zeile ohne Markdown-Beiwerk -- das Modell setzt Sprechernamen gern
    fett (``**MIRA:** ...``), und daran soll das Erkennen nicht scheitern."""
    return zeile.strip().strip(_MARKDOWN).strip()


def _grundwort(label: str) -> str:
    """Das Label auf sein erstes Wort ohne Ziffern und Zeichen reduziert --
    ``"SZENE 3"`` wird ``"szene"``, ``"ANDERS GEMACHT"`` bleibt zweiwortig."""
    ohne = re.sub(r"[\d.,;!?/]+", " ", label)
    ohne = _INLINE_REGIE.sub(" ", ohne)
    return " ".join(ohne.split()).casefold()


def _ist_versal(text: str) -> bool:
    """Steht der Text in Versalien? (Alle Formen-Regelbloecke schreiben
    Sprechernamen in Grossbuchstaben.) Ziffern und Zeichen zaehlen nicht mit."""
    buchstaben = [z for z in text if z.isalpha()]
    return bool(buchstaben) and all(z.isupper() for z in buchstaben)


def _label_form_ok(label: str) -> bool:
    """Sieht das, was vor dem Doppelpunkt steht, ueberhaupt wie ein Name aus?

    Hoechstens vier Woerter, hoechstens 40 Zeichen, mindestens ein Buchstabe,
    keine Satzzeichen ausser Bindestrich/Punkt/Apostroph und dem, was in einer
    Klammer steht (``MIRA (leise):``). Ein Satz mit Doppelpunkt mittendrin
    faellt damit heraus."""
    ohne_regie = _INLINE_REGIE.sub(" ", label).strip()
    if not ohne_regie or len(ohne_regie) > 40:
        return False
    if len(ohne_regie.split()) > 4:
        return False
    if not any(z.isalpha() for z in ohne_regie):
        return False
    return all(z.isalpha() or z in " -.'’/&" for z in ohne_regie)


def _labelname(label: str) -> str:
    """Der Name aus einem Label, ohne Regieklammer und Randzeichen."""
    return " ".join(_INLINE_REGIE.sub(" ", label).replace(".", " ").split())


def _ohne_regie(text: str) -> str:
    """Die Replik ohne Inline-Regieanweisung -- ``(sieht nicht auf)`` ist
    nicht gesprochen und darf im Wortanteil nicht mitzaehlen."""
    return " ".join(_INLINE_REGIE.sub(" ", text or "").split())


def repliken(text: str, figuren=()) -> list[Replik]:
    """Alle erkannten Sprecherzeilen einer Szene, in Reihenfolge.

    **Zwei Durchgaenge, und der zweite laeuft nur, wenn der erste nichts
    findet.** Streng zuerst: nur Label in Versalien (so schreiben es alle
    Regelbloecke unter ``prompts/formen/``). Findet das nichts, wird ein
    zweiter Durchgang versucht, der ``Name:`` auch klein akzeptiert -- aber
    nur, wenn der Name im uebergebenen Figurenverzeichnis steht, und **nur in
    der Doppelpunkt-Form**. Die Blockformen (Rap, Lied) bleiben dem strengen
    Durchgang vorbehalten: in einer Prosafassung stuende sonst "Mira." als
    eigene Zeile und alles danach waere ihre Replik.

    Erkannt werden vier Formen, alle aus ``prompts/formen/``:

    * ``MIRA: Replik.`` und ``MIRA:(sieht nicht auf)Replik.`` (Dialog,
      Monolog, Chor)
    * ``CHOR: Wir warten seit zwei Stunden hier.`` (Chor)
    * ``STROPHE (MIRA)`` / ``HOOK (ALLE)`` mit den folgenden Zeilen als Block
      (Lied)
    * ``MIRA`` allein auf einer Zeile in Versalien mit den folgenden Zeilen
      als Block (Rap)

    Regieanweisungen (Zeile beginnt mit ``(``) beenden einen Block und sind
    nie eine Replik. Findet sich nichts, ist das Ergebnis leer -- und die
    Aufrufer liefern dann fuer diese Szene **keinen** Befund."""
    gefunden = _repliken_durchgang(text, erlaubt=None)
    if gefunden:
        return gefunden
    namen = {_schluessel(n) for n in figuren if (n or "").strip()}
    namen |= KOLLEKTIV
    if not namen:
        return []
    return _repliken_durchgang(text, erlaubt=namen)


def _repliken_durchgang(text: str, erlaubt) -> list[Replik]:
    """Ein Durchgang. ``erlaubt=None`` heisst "nur Versalien"; eine Menge von
    Vergleichsschluesseln heisst "auch klein, aber nur diese Namen"."""
    ergebnis: list[Replik] = []
    block: str | None = None
    for nummer, roh in enumerate((text or "").splitlines(), start=1):
        zeile = _nackt(roh)
        if not zeile:
            block = None
            continue
        if zeile.startswith("("):
            block = None
            continue

        kopf, trenner, rest = zeile.partition(":")
        if trenner and _label_form_ok(kopf):
            name = _labelname(kopf)
            if _grundwort(kopf) not in _STRUKTUR and _erlaubt(name, erlaubt):
                ergebnis.append(Replik(name, _ohne_regie(rest), nummer))
                block = None
                continue

        if erlaubt is None:
            treffer = _MARKER_MIT_NAME.match(zeile)
            if treffer and _grundwort(treffer.group(1)) in _MARKER:
                name = _labelname(treffer.group(2))
                block = name if _erlaubt(name, erlaubt) else None
                continue

            if _grundwort(zeile) in _MARKER:
                block = None
                continue

            if not trenner and _label_form_ok(zeile) \
                    and _grundwort(zeile) not in _STRUKTUR:
                name = _labelname(zeile)
                if _erlaubt(name, erlaubt):
                    block = name
                    continue

        if block is not None:
            inhalt = _ohne_regie(zeile)
            if inhalt:
                ergebnis.append(Replik(block, inhalt, nummer))
    return ergebnis


def _erlaubt(name: str, erlaubt) -> bool:
    if erlaubt is None:
        return _ist_versal(name)
    return _schluessel(name) in erlaubt


# ---------------------------------------------------------------------------
# Die Szenendaten, auf denen alles laeuft
# ---------------------------------------------------------------------------


@dataclass
class Szenenlage:
    """Alles, was die Checks aus der Datenbank brauchen -- einmal gelesen.

    ``texte`` je Szenennummer, ``repliken`` je Szenennummer (leer, wo nichts
    erkannt wurde), ``besetzung`` je Szenennummer aus ``szene_figur``."""

    figuren: list[str] = field(default_factory=list)
    nummern: list[int] = field(default_factory=list)
    texte: dict[int, str] = field(default_factory=dict)
    formen: dict[int, str] = field(default_factory=dict)
    repliken: dict[int, list[Replik]] = field(default_factory=dict)
    besetzung: dict[int, list[str]] = field(default_factory=dict)

    def mit_sprechern(self) -> list[int]:
        """Die Szenen, in denen ueberhaupt Sprecherzeilen erkannt wurden."""
        return [n for n in self.nummern if self.repliken.get(n)]

    def figur_fuer(self, label: str) -> str | None:
        """Der Verzeichnisname zu einem Sprecherlabel, oder None."""
        schluessel = _schluessel(label)
        for name in self.figuren:
            if _schluessel(name) == schluessel:
                return name
        return None


def _szenentext(zeile) -> str:
    """Der Text einer Szene: der Theatertext, sonst die Prosafassung.

    Die Prosafassung (Phase 6) hat keine Sprecherzeilen -- ``repliken()``
    liefert dort nichts, und genau das ist gewollt: die sprecherabhaengigen
    Checks schweigen, die textabhaengigen (Tschechow, Erwaehnung) laufen
    trotzdem."""
    for feld in ("volltext", "prosa"):
        try:
            wert = (zeile[feld] or "").strip()
        except (IndexError, KeyError):
            continue
        if wert:
            return wert
    return ""


def lies(conn, chat_id: int) -> Szenenlage:
    """Liest Figuren, Szenen, Texte und Besetzungen einmal ein."""
    figuren = [f["name"] for f in repo.figuren(conn, chat_id) if (f["name"] or "").strip()]
    lage = Szenenlage(figuren=figuren)
    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] is None:
            continue
        nummer = int(s["nummer"])
        text = _szenentext(s)
        lage.nummern.append(nummer)
        lage.texte[nummer] = text
        lage.formen[nummer] = (s["form"] or "").strip()
        lage.repliken[nummer] = repliken(text, figuren)
        lage.besetzung[nummer] = [
            f["name"] for f in repo.szene_figuren(conn, s["id"])
            if (f["name"] or "").strip()
        ]
    lage.nummern.sort()
    return lage


# ---------------------------------------------------------------------------
# Die Checks
# ---------------------------------------------------------------------------

#: Ab welcher Aehnlichkeit ein unbekanntes Sprecherlabel als **Variante**
#: einer bekannten Figur gilt und nicht als Geisterfigur. ``difflib``, nicht
#: Levenshtein: Standardbibliothek, keine neue Abhaengigkeit. 0,8 trifft
#: "Leyla"/"Layla" (0,8) und "Mira"/"Miriam" (0,8) und laesst "Mira"/"Jonas"
#: (0,0) in Ruhe.
AEHNLICHKEIT = 0.8

#: Wortanteil, unter dem eine Figur gemeldet wird -- nicht als Note, sondern
#: als Zahl im Satz ("34 von 5.800 Woertern"). Recherche § 5.2: fuer eine
#: Laiengruppe ist das der praktisch wichtigste Befund.
SPRECHANTEIL_SCHWELLE = 0.03

#: Wie viele Tschechow-Kandidaten hoechstens gemeldet werden. Die Heuristik
#: rauscht (siehe ``tschechow_kandidaten``); eine Liste, die niemand liest,
#: ist keine Hilfe.
KANDIDATEN_MAX = 8


def namensstabilitaet(lage: Szenenlage) -> list[Befund]:
    """Sprecherlabel, die einer Figur **aehneln**, ohne sie zu sein.

    Der gemessene Fehlermodus: dasselbe Modell schreibt in Szene 2 "Leyla"
    und in Szene 5 "Layla". Fuer eine Gruppe, die den Text laut liest, ist
    das ein kaputter Text; fuer ein Programm ist es ein Wortvergleich."""
    if not lage.figuren:
        return []
    befunde: list[Befund] = []
    gesehen: set[tuple[str, str]] = set()
    for nummer in lage.mit_sprechern():
        for replik in lage.repliken[nummer]:
            if _schluessel(replik.label) in KOLLEKTIV:
                continue
            if lage.figur_fuer(replik.label) is not None:
                continue
            nah = difflib.get_close_matches(
                _schluessel(replik.label),
                [_schluessel(n) for n in lage.figuren],
                n=1, cutoff=AEHNLICHKEIT,
            )
            if not nah:
                continue
            figur = next(n for n in lage.figuren if _schluessel(n) == nah[0])
            if (replik.label, figur) in gesehen:
                continue
            gesehen.add((replik.label, figur))
            befunde.append(Befund(
                "namensstabilitaet", "hart",
                f"In Szene {nummer} spricht „{replik.label}“ - im "
                f"Figurenverzeichnis steht „{figur}“. Einer von "
                "beiden Namen ist falsch geschrieben.",
                szene=nummer, figur=figur,
            ))
    return befunde


def geisterfiguren(lage: Szenenlage) -> list[Befund]:
    """Zwei Richtungen: ein Sprecher ohne Figurenzeile (Fehler) und eine
    Figur, die nirgends spricht und nirgends vorkommt (Warnung)."""
    befunde: list[Befund] = []
    bekannt = {_schluessel(n) for n in lage.figuren} | KOLLEKTIV
    aehnlich = [_schluessel(n) for n in lage.figuren]
    gesehen: set[str] = set()
    for nummer in lage.mit_sprechern():
        for replik in lage.repliken[nummer]:
            schluessel = _schluessel(replik.label)
            if schluessel in bekannt or schluessel in gesehen:
                continue
            if difflib.get_close_matches(schluessel, aehnlich, n=1, cutoff=AEHNLICHKEIT):
                continue  # das meldet namensstabilitaet, nicht dieser Check
            gesehen.add(schluessel)
            befunde.append(Befund(
                "geisterfigur", "hart",
                f"In Szene {nummer} spricht „{replik.label}“ - "
                "diese Figur gibt es in eurem Figurenverzeichnis nicht.",
                szene=nummer, figur=replik.label,
            ))

    if not lage.texte:
        return befunde
    for name in lage.figuren:
        spricht = any(
            _schluessel(r.label) == _schluessel(name)
            for nummer in lage.mit_sprechern() for r in lage.repliken[nummer]
        )
        if spricht:
            continue
        erwaehnt = any(_erwaehnt(name, text) for text in lage.texte.values())
        if erwaehnt:
            continue
        befunde.append(Befund(
            "figur_ohne_auftritt", "hinweis",
            f"„{name}“ steht im Figurenverzeichnis, spricht aber in "
            "keiner Szene und wird in keiner erwaehnt.",
            figur=name,
        ))
    return befunde


def _erwaehnt(name: str, text: str) -> bool:
    """Kommt der Name als eigenes Wort im Text vor? Gross-/Kleinschreibung
    egal, weil ein Sprecherlabel in Versalien steht und eine Erwaehnung im
    Satz nicht."""
    if not (name or "").strip():
        return False
    return re.search(rf"(?<!\w){re.escape(name.strip())}(?!\w)", text or "",
                     re.IGNORECASE) is not None


def besetzungsabgleich(lage: Szenenlage) -> list[Befund]:
    """Planung gegen Text, in beide Richtungen.

    ``verdacht`` und nicht ``hart``, in beide Richtungen: die Besetzung ist
    ein **Planungsfeld** (``szene_figur``), der Szenentext ist das Ergebnis.
    Welches von beiden nachgezogen gehoert, weiss nur die Gruppe -- oft ist
    es die Planung."""
    befunde: list[Befund] = []
    for nummer in lage.mit_sprechern():
        besetzung = lage.besetzung.get(nummer) or []
        if not besetzung:
            continue
        sprecher = {
            _schluessel(r.label) for r in lage.repliken[nummer]
            if _schluessel(r.label) not in KOLLEKTIV
        }
        for name in besetzung:
            if _schluessel(name) not in sprecher:
                befunde.append(Befund(
                    "besetzung_stumm", "verdacht",
                    f"{name} steht in der Besetzung von Szene {nummer}, "
                    "spricht dort aber keine Zeile.",
                    szene=nummer, figur=name,
                ))
        geplant = {_schluessel(n) for n in besetzung}
        for label in dict.fromkeys(
            r.label for r in lage.repliken[nummer]
            if _schluessel(r.label) not in KOLLEKTIV
        ):
            if _schluessel(label) in geplant:
                continue
            if lage.figur_fuer(label) is None:
                continue  # das meldet geisterfiguren
            befunde.append(Befund(
                "besetzung_fremd", "verdacht",
                f"{label} spricht in Szene {nummer}, steht dort aber nicht in "
                "der Besetzung.",
                szene=nummer, figur=label,
            ))
    return befunde


def erstauftritt_register(lage: Szenenlage) -> list[Befund]:
    """Je Figur die Szene des ersten Auftritts -- und ob sie vorher schon
    beim Namen genannt wird.

    Kein harter Fehler: eine Figur, von der geredet wird, bevor sie auftritt,
    ist ein altes und gutes dramaturgisches Mittel. Aber sie ist auch der
    haeufigste Ort, an dem eine Figur Wissen hat, das sie nicht haben kann
    (Recherche A5) -- deshalb eine Verdachtszeile."""
    befunde: list[Befund] = []
    for name in lage.figuren:
        erste = None
        for nummer in lage.mit_sprechern():
            if any(_schluessel(r.label) == _schluessel(name)
                   for r in lage.repliken[nummer]):
                erste = nummer
                break
        if erste is None:
            continue
        frueher = [
            n for n in lage.nummern
            if n < erste and _erwaehnt(name, lage.texte.get(n, ""))
        ]
        if not frueher:
            continue
        befunde.append(Befund(
            "erstauftritt", "verdacht",
            f"{name} wird schon in Szene {frueher[0]} beim Namen genannt, "
            f"spricht aber erst in Szene {erste} zum ersten Mal - prueft, ob "
            "dort erklaert ist, woher man sie kennt.",
            szene=frueher[0], figur=name,
        ))
    return befunde


#: Woerter, die zwar grossgeschrieben vorkommen, aber nie ein "aufgeladenes
#: Element" sind: Satzanfaenge, Anreden, Zeitwoerter ohne Gegenstandscharakter.
#: Bewusst KURZ gehalten -- eine lange Liste wuerde genau die Gegenstaende
#: verschlucken, um die es geht.
_TSCHECHOW_STOPP = frozenset({
    "aber", "also", "auch", "dann", "dass", "denn", "doch", "eine", "einen",
    "einer", "eines", "erst", "haben", "hatte", "heute", "hier", "immer",
    "jetzt", "kann", "komm", "kommt", "mehr", "musst", "nein", "nicht",
    "nichts", "noch", "nur", "oder", "schon", "sein", "sich", "sind", "sonst",
    "und", "vielleicht", "warum", "weil", "wenn", "wieder", "wirklich",
    "willst", "wollen", "dieses", "diese", "dieser", "jedes", "jede", "jeder",
    "alles", "etwas", "irgendwas", "okay", "danke", "bitte", "genau",
})

_WORT = re.compile(r"(?<!\w)([A-ZÄÖÜ][a-zäöüß]{3,})(?!\w)")


def tschechow_kandidaten(lage: Szenenlage) -> list[Kandidat]:
    """Woerter, die in einer Szene mehrfach vorkommen und danach nie wieder.

    **Das ist eine Heuristik, und sie rauscht.** Ohne Wortartenerkennung
    (spaCy waere eine neue Abhaengigkeit und ist ausdruecklich ausgeschlossen)
    laesst sich im Deutschen ein Gegenstand nicht von einem beliebigen
    Substantiv unterscheiden: die Sprache schreibt **alle** Substantive gross,
    und am Satzanfang steht ohnehin jedes Wort gross. Was hier herauskommt,
    ist deshalb eine **Kandidatenliste**, keine Befundliste -- gedacht als
    Eingabe fuer den A6-Aufruf (Schicht 3), der entscheidet, ob ein Kandidat
    ueberhaupt "aufgeladen" war. Erwartungswert nach Erfahrung mit
    Wortlisten dieser Art: ein knappes Drittel Treffer, der Rest Rauschen.

    Gefiltert wird nur, was sicher kein Kandidat ist: Figurennamen,
    Kollektivlabel, Woerter unter vier Buchstaben, Versalien (Sprecherzeilen),
    und eine kurze Stoppwortliste fuer Satzanfaenge."""
    verboten = {_schluessel(n) for n in lage.figuren} | KOLLEKTIV | _TSCHECHOW_STOPP
    letzte: dict[str, int] = {}
    zaehler: dict[int, Counter] = {}
    for nummer in lage.nummern:
        gefunden = Counter()
        for wort in _WORT.findall(lage.texte.get(nummer, "")):
            if _schluessel(wort) in verboten:
                continue
            gefunden[wort] += 1
            letzte[_schluessel(wort)] = nummer
        zaehler[nummer] = gefunden

    if len(lage.nummern) < 2:
        return []
    kandidaten: list[Kandidat] = []
    for nummer in lage.nummern[:-1]:
        for wort, anzahl in zaehler[nummer].items():
            if anzahl < 2 or letzte.get(_schluessel(wort)) != nummer:
                continue
            kandidaten.append(Kandidat(
                wort, nummer, anzahl, _satz_mit(lage.texte.get(nummer, ""), wort),
            ))
    kandidaten.sort(key=lambda k: (-k.anzahl, k.szene, k.wort))
    return kandidaten[:KANDIDATEN_MAX]


def _satz_mit(text: str, wort: str) -> str:
    """Der erste Satz, in dem das Wort steht -- Kontext fuer den A6-Aufruf."""
    for stueck in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
        gestrafft = " ".join(stueck.split())
        if gestrafft and re.search(rf"(?<!\w){re.escape(wort)}(?!\w)", gestrafft):
            return gestrafft[:200]
    return ""


def tschechow_befunde(lage: Szenenlage) -> list[Befund]:
    """Die Kandidatenliste als Befunde -- ``hinweis``, nie mehr."""
    return [
        Befund(
            "tschechow", "hinweis",
            f"„{k.wort}“ kommt in Szene {k.szene} {k.anzahl}-mal vor "
            "und danach in keiner Szene mehr.",
            szene=k.szene,
        )
        for k in tschechow_kandidaten(lage)
    ]


#: Die Formen, die keine Sprechszene sind. ``szene.FORMEN`` ist die Quelle
#: der Namen; ``dialog`` ist der Normalfall (``prompts/formen/dialog.md``).
_NICHT_DIALOG = ("monolog", "chor", "lied", "rap")

#: Die Vorschlagsregel aus dem Szenen-Prompt (AGENTS.md, "Die Form je Szene
#: ist ein Vorschlag"): Szene 1 nie Monolog oder Lied.
_ERSTE_VERBOTEN = ("monolog", "lied")

#: Klumpung: so viele Nicht-Dialog-Szenen hintereinander sind zu viele.
KLUMPUNG = 3


def _formklasse(form: str) -> str:
    wert = _schluessel(form)
    for name in _NICHT_DIALOG:
        if name in wert:
            return name
    return "dialog" if wert else ""


def formverteilung(lage: Szenenlage) -> list[Befund]:
    """Wie viele Szenen je Form, wo sie klumpen, und die drei Regeln aus dem
    Szenen-Prompt: Dialog ist der Normalfall, hoechstens eine Nicht-Dialog-
    Szene je drei, Szene 1 nie Monolog oder Lied.

    Nur **bestaetigte** Formen (``szene.form``), nie ``form_vorschlag``: ein
    Vorschlag ist keine Entscheidung (AGENTS.md)."""
    mit_form = [n for n in lage.nummern if _formklasse(lage.formen.get(n, ""))]
    if not mit_form:
        return []
    befunde: list[Befund] = []
    klassen = {n: _formklasse(lage.formen[n]) for n in mit_form}

    erste = min(lage.nummern)
    if klassen.get(erste) in _ERSTE_VERBOTEN:
        befunde.append(Befund(
            "form_regel", "hart",
            f"Szene {erste} ist ein {lage.formen[erste]}. Die erste Szene "
            "soll nie ein Monolog oder ein Lied sein - sie muss zeigen, wer "
            "da ist und worum es geht.",
            szene=erste,
        ))

    nicht_dialog = [n for n in mit_form if klassen[n] != "dialog"]
    erlaubt = max(1, len(mit_form) // 3)
    if len(nicht_dialog) > erlaubt:
        namen = ", ".join(f"Szene {n}" for n in nicht_dialog)
        befunde.append(Befund(
            "form_regel", "hinweis",
            f"Von {len(mit_form)} Szenen mit gewaehlter Form sind "
            f"{len(nicht_dialog)} keine Dialogszene ({namen}). Die Regel im "
            "Szenen-Prompt ist hoechstens eine Nicht-Dialog-Szene je drei.",
        ))

    lauf: list[int] = []
    for n in mit_form:
        if klassen[n] != "dialog":
            lauf.append(n)
            continue
        if len(lauf) >= KLUMPUNG:
            befunde.append(_klumpung(lauf))
        lauf = []
    if len(lauf) >= KLUMPUNG:
        befunde.append(_klumpung(lauf))
    return befunde


def _klumpung(lauf: list[int]) -> Befund:
    namen = ", ".join(f"Szene {n}" for n in lauf)
    return Befund(
        "formverteilung", "hinweis",
        f"{namen} sind hintereinander keine Dialogszenen. Drei Nicht-Dialog-"
        "Szenen am Stueck halten die Handlung an.",
        szene=lauf[0],
    )


def sprechanteile(lage: Szenenlage) -> list[Befund]:
    """Der Wortanteil je Figur ueber das ganze Stueck.

    **Der praktisch wichtigste Befund fuer eine Laiengruppe** (Recherche
    § 5.2): eine Spielerin mit vier Zeilen ist ein Problem, das im Chat
    niemand sieht und am Probenabend jeder. Im Text steht die **Zahl**, nicht
    der Anteil -- "34 von 5.800 Woertern" ist nachpruefbar, "0,6 %" ist eine
    Note."""
    szenen = lage.mit_sprechern()
    if not szenen or not lage.figuren:
        return []
    woerter: Counter = Counter()
    for nummer in szenen:
        for replik in lage.repliken[nummer]:
            if _schluessel(replik.label) in KOLLEKTIV:
                continue
            name = lage.figur_fuer(replik.label)
            if name is None:
                continue
            woerter[name] += len(replik.text.split())
    gesamt = sum(woerter.values())
    if gesamt < 1:
        return []
    befunde = []
    for name in lage.figuren:
        anzahl = woerter.get(name, 0)
        if anzahl / gesamt >= SPRECHANTEIL_SCHWELLE:
            continue
        befunde.append(Befund(
            "sprechanteil", "hart",
            f"{name} spricht im ganzen Stueck {anzahl} von {gesamt} Woertern. "
            "Das ist zu wenig fuer eine Rolle, die jemand spielen soll.",
            figur=name,
        ))
    return befunde


# ---------------------------------------------------------------------------
# Alles auf einmal
# ---------------------------------------------------------------------------

#: Die Checks in fester Reihenfolge -- Name und Funktion. Ein weiterer Check
#: braucht eine Zeile hier und sonst nichts.
CHECKS = (
    ("namensstabilitaet", namensstabilitaet),
    ("geisterfiguren", geisterfiguren),
    ("besetzungsabgleich", besetzungsabgleich),
    ("erstauftritt_register", erstauftritt_register),
    ("tschechow", tschechow_befunde),
    ("formverteilung", formverteilung),
    ("sprechanteile", sprechanteile),
)


def pruefe_alles(conn, chat_id: int) -> list[Befund]:
    """Alle mechanischen Checks, sortiert nach Schwere, dann Szene.

    Rein lesend. Ein einzelner Check, der an unerwarteten Daten scheitert,
    darf die uebrigen nicht mitreissen -- der Nutzen dieser Schicht ist, dass
    sie **immer** laeuft."""
    lage = lies(conn, chat_id)
    befunde: list[Befund] = []
    for name, funktion in CHECKS:
        try:
            befunde.extend(funktion(lage))
        except Exception:  # noqa: BLE001 -- ein Check reisst die anderen nicht mit
            log.exception("Mechanik-Check %s gescheitert, chat_id=%s", name, chat_id)
    befunde.sort(key=lambda b: (
        _SCHWERE_RANG.get(b.schwere, 9),
        b.szene if b.szene is not None else 10_000,
        b.pruefung,
    ))
    return befunde
