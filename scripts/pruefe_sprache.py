"""Findet deutsche Saetze in allem, was ein Profil erzeugt (Karte A1, D10).

Die Abnahme (3) der Karte: mit ``padua-2026`` enthaelt **kein** Chat-,
Knopf- oder Prompttext mehr einen deutschen Satz -- mechanisch geprueft,
nicht gelesen. Positivkontrolle: gegen ``dortmund-2026`` muss der Pruefer
anschlagen, sonst prueft er nichts.

Zwei Signale, casefold, an Wortgrenzen:

* ``STOPPWOERTER`` -- deutsche Funktionswoerter, die weder englisch noch
  italienisch sind,
* ``UI_WOERTER`` -- deutsche Inhaltswoerter aus Knopf- und Systemzeilen
  ("Ja, speichern", "Notiert:"), die kein Funktionswort tragen (W2),

dazu Umlaute/ß als eigenes Signal. Ausgenommen: Protokoll-Token (Woerter
nur aus Grossbuchstaben, snake_case, ``{…}``/``{{…}}``-Platzhalter) und
``ERLAUBT`` (Formnamen als Datenbankwerte, Stil-Slugs, erfundene Namen).

Aufruf::

    python -m scripts.pruefe_sprache --dateien <pfad> [<pfad> ...]
    python -m scripts.pruefe_sprache --schluessel <modul>[,<modul> ...]
    python -m scripts.pruefe_sprache <profil> [--quelle prompts,texte,durchlauf,web]   # ab Aufgabe 30

Exit 0 nur ohne Treffer.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from interview_theater.repo import FESTLEGUNG_BEREICHE

#: Deutsche Funktionswoerter (Brief D10) plus einige, die in Knopftexten
#: tragen. Keins davon ist ein englisches oder italienisches Wort.
STOPPWOERTER = frozenset({
    "und", "nicht", "ist", "ihr", "euch", "wir", "ich", "mit", "fuer", "für",
    "auf", "eine", "einen", "noch", "schon", "auch", "oder", "wenn", "dass",
    "sich", "werden", "bitte", "jetzt", "hier", "sind", "habt", "eure",
    "euer", "uns", "kein", "keine", "nichts", "dann", "weil", "aber", "zum",
    "zur", "beim", "ueber", "über", "wird", "seid", "wollt", "koennt",
    "könnt", "sagt", "mir", "dir", "du", "dein", "deine",
})

#: Deutsche Inhaltswoerter aus Knopf- und Systemzeilen, die ohne
#: Funktionswort stehen (W2). Kuratiert aus knoepfe/texte.py, befehle.py,
#: aufnahme.py, erkenner.baue_meldung und web.py; keins ist ein englisches
#: Wort.
UI_WOERTER = frozenset({
    "ja", "nein", "speichern", "gespeichert", "notiert", "weiter", "zurueck",
    "zurück", "fertig", "aufnahme", "aufnahmen", "auswerten", "ausgewertet",
    "begriffe", "fragen", "figur", "figuren", "szene", "szenen", "geschichte",
    "kurzgeschichte", "textbuch", "fassung", "fassungen", "leitfaden",
    "eroeffnung", "eröffnung", "abschluss", "einleitung", "einleitungen",
    "verdichtung", "kernthema", "stueck", "stück", "passt", "anders", "neu",
    "schreiben", "zeigen", "ansehen", "kuerzer", "kürzer", "hinweis",
    "schweiz", "bereit", "laeuft", "läuft", "beendet", "gruppe",
    "feinschliff", "schaerfung", "schärfung", "sprechanteile",
    "probenansicht", "arbeitsstand", "festlegung", "festlegungen", "stand",
    "hilfe", "starten", "beenden", "interviewpartnerin", "sprachnachricht",
    "sprachnachrichten", "zusammenfassung", "transkript", "knopf", "knoepfe",
    "knöpfe", "vorschlag", "runde", "entfernt", "zurueckgenommen",
    "zurückgenommen", "uebernommen", "übernommen", "abgeschlossen",
})

#: Woerter, die in englischen Texten legitim stehen: Formnamen als
#: Datenbankwerte (``szene.form``), Stil-Slugs, Profil-Beispielorte (Padua,
#: italienisch), und die Namen der Phasen, soweit sie Protokoll sind.
ERLAUBT = frozenset({
    "dialog", "monolog", "chor", "lied", "rap", "prosa",
    "herkules", "schlagabtausch", "litanei",
    "fermata", "piazza", "bar", "stazione",
})

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß]+")
_UMLAUT = re.compile(r"[äöüÄÖÜß]")

#: Formwerte einer Szene (szene.FORMEN, Review Aufgabe 14: "die Formwerte
#: dialog/monolog/chor/lied/rap"). Hier als eigene, statische Kopie und
#: nicht ueber ``szene.FORMEN`` importiert: dieser Wert haengt am aktiven
#: Workshop-Profil (PEP 562, Modul-``__getattr__``), der Pruefer laeuft aber
#: profil-unabhaengig und baut die Regex einmal beim Import.
_FORMWERTE = frozenset({"dialog", "monolog", "chor", "lied", "rap"})

#: Argumentwoerter, die im Text direkt hinter einem Slash-Befehl als Teil
#: der Befehlssyntax gelten (Annahme A4: Befehlsnamen und Argumentwoerter
#: bleiben deutsch, ``/hilfe`` darf sie nennen) und deshalb NICHT als
#: deutscher Flusstext gezaehlt werden. Bewusst eine GESCHLOSSENE Menge
#: (Review zu Aufgabe 14): das fruehere Muster liess JEDES kleingeschriebene
#: Wort hinter einem Befehl als Argument durchgehen und verschluckte damit
#: ganze Saetze -- gemessen: "Tippt /aufnahme und dann sprecht ihr los."
#: und "/hilfe zeigt dir alles, was geht" ergaben 0 Treffer statt "ihr"
#: bzw. "dir". Jedes Wort unten ist am Code von ``befehle.py`` ermittelt,
#: nicht geraten:
#:   "aus"                    -- ``rest.lower() == "aus"`` in
#:                                _befehl_stueck/_befehl_kernthema/
#:                                _befehl_wortlaut
#:   "rahmen", "format"       -- Schluessel von ``befehle._STUECK_FELDER``
#:   "entfernen", "entferne",
#:   "loeschen", "löschen",
#:   "weg", "raus"            -- ``befehle._ENTFERNEN_WOERTER``
#:                                (``/figur <name> entfernen``,
#:                                ``/festlegung weg <suchwort>``)
#:   "ort", "zeit", "anlass",
#:   "figuren", "form"        -- Szenenfelder aus ``szene.FELD_ALIASE``, ueber
#:                                ``befehle._setze_szenenfeld`` geparst
#:                                (``/szene <n> ort|zeit|anlass|figuren
#:                                <text>``, ``/szene <n> form <...>``)
#:   "usa", "ja", "j", "yes",
#:   "nein", "n", "no"        -- ``befehle._SZENE_USA``/``_SZENE_USA_LEER``
#:                                (``/szene usa ja|nein``)
#:   "auto"                   -- ``befehle._SPRACHWERT`` (``/sprache auto``)
#: Dazu die fuenf Formwerte (oben) und die Festlegungsbereiche aus
#: ``repo.FESTLEGUNG_BEREICHE`` -- importiert statt dupliziert, damit ein
#: neuer Bereich den Pruefer nicht stillschweigend uebergeht.
ARGUMENTWOERTER = frozenset({
    "aus", "rahmen", "format",
    "entfernen", "entferne", "loeschen", "löschen", "weg", "raus",
    "ort", "zeit", "anlass", "figuren", "form",
    "usa", "ja", "j", "yes", "nein", "n", "no",
    "auto",
}) | _FORMWERTE | frozenset(FESTLEGUNG_BEREICHE)

#: Laengstes Wort zuerst, damit z. B. "figuren" vor "figur" probiert wird
#: (nur fuer Lesbarkeit/Effizienz -- die Regex-Engine backtrackt ohnehin
#: ueber die Alternation, siehe Wortgrenzen-Lookahead unten).
_ARGWORT = "|".join(re.escape(w) for w in sorted(ARGUMENTWOERTER, key=len, reverse=True))

#: Was vor dem Pruefen herausgenommen wird: Platzhalter, snake_case-Namen
#: (Erkenner-Arten, JSON-Schluessel, Feldnamen), Woerter nur aus
#: Grossbuchstaben (Protokoll-Marker wie VORSCHLAG FRAGENAUSWAHL:, BEFUND:),
#: URLs und Dateipfade. Dazu die Syntax eines Slash-Befehls (Annahme A4:
#: Befehlsnamen und Argumentwoerter bleiben deutsch, ``/hilfe`` darf sie
#: nennen): der Name samt direkt folgender Argumente aus ``ARGUMENTWOERTER``,
#: ``a|b``-Alternativen daraus und ``<…>``/``[…]``-Platzhalter (deren Inhalt
#: bleibt ungeprueft -- er ist per Definition Beispieltext, kein Flusstext).
#: Grenze, bewusst: nur ein Wort aus der geschlossenen Menge direkt hinter
#: einem Befehl gilt als Argument, kein beliebiges kleingeschriebenes Wort
#: (Review Aufgabe 14) -- sonst verschluckt die Regex den ganzen Satz danach.
_AUSSEN_VOR = re.compile(
    r"(?<![\w/])/[a-z]+(?:[ ]+(?:<[^<>\n]*>|\[[^\[\]\n]*\]|"
    rf"(?:{_ARGWORT})(?:\|(?:{_ARGWORT}))*)(?![\w]))*"
    r"|\{\{[a-z0-9_]+\}\}|\{[A-Za-z0-9_!:>< .]*\}"
    r"|\b[a-z]+(?:_[a-z0-9]+)+\b"
    r"|\b[A-ZÄÖÜ]{2,}(?:[ _][A-ZÄÖÜ]{2,})*\b"
    r"|https?://\S+|\b[\w./-]+\.(?:md|toml|py|txt|json|jsonl)\b"
)


@dataclass(frozen=True)
class Treffer:
    quelle: str
    wort: str
    ausschnitt: str


def deutsche_treffer(quelle: str, text: str) -> list[Treffer]:
    """Jedes deutsche Signal in ``text``, mit Ausschnitt."""
    gesaeubert = _AUSSEN_VOR.sub(lambda t: " " * len(t.group(0)), text or "")
    treffer = []
    for wort in _WORT.finditer(gesaeubert):
        roh = wort.group(0)
        klein = roh.casefold()
        if klein in ERLAUBT:
            continue
        if klein in STOPPWOERTER or klein in UI_WOERTER:
            zeichen = klein
        elif _UMLAUT.search(roh):
            zeichen = _UMLAUT.search(roh).group(0)
        else:
            continue
        anfang = max(0, wort.start() - 30)
        ausschnitt = " ".join(text[anfang:wort.end() + 30].split())
        treffer.append(Treffer(quelle, zeichen, ausschnitt))
    return treffer


_SKRIPT_STIL = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def nur_text(html: str) -> str:
    """Der lesbare Text einer HTML-Seite: ohne ``<script>``/``<style>``, ohne
    Tags, Entitaeten dekodiert -- geprueft wird, was man liest, nicht CSS
    und JavaScript (Aufgabe 17)."""
    import html as html_modul

    ohne = _SKRIPT_STIL.sub(" ", html or "")
    return html_modul.unescape(_TAG.sub(" ", ohne))


def pruefe_dateien(pfade: list[Path]) -> list[Treffer]:
    treffer = []
    for pfad in pfade:
        treffer += deutsche_treffer(str(pfad), Path(pfad).read_text(encoding="utf-8"))
    return treffer


def _blaetter(wert, pfad: str):
    if isinstance(wert, str):
        yield pfad, wert
    elif isinstance(wert, dict):
        for k, v in wert.items():
            if k in ("slug", "command"):
                continue
            yield from _blaetter(v, f"{pfad}.{k}")
    elif isinstance(wert, (list, tuple)):
        for i, v in enumerate(wert):
            yield from _blaetter(v, f"{pfad}[{i}]")


def pruefe_schluessel(module: list[str], sprachcode: str = "en") -> list[Treffer]:
    """Die Werte der Tabelle fuer ``module`` (leer = alle) -- genau das, was
    ``sprache.text`` zur Laufzeit liefert. Schluessel werden nicht geprueft:
    Beschriftungstabellen (K4) haben deutsche Schluessel."""
    from interview_theater import sprache

    sprache.vergiss()
    tabelle = sprache.tabelle(sprachcode)
    treffer = []
    for modul in module or sorted(tabelle):
        for name, wert in tabelle.get(modul, {}).items():
            for pfad, text in _blaetter(wert, f"{modul}.{name}"):
                treffer += deutsche_treffer(pfad, text)
    return treffer


def _ausgabe(treffer: list[Treffer]) -> int:
    for t in treffer:
        print(f"{t.quelle}: {t.wort!r} in: {t.ausschnitt}")
    print(f"{len(treffer)} Treffer")
    return 1 if treffer else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.pruefe_sprache")
    p.add_argument("profil", nargs="?")
    p.add_argument("--dateien", nargs="+", type=Path)
    p.add_argument("--schluessel")
    args = p.parse_args(argv)
    if args.dateien:
        return _ausgabe(pruefe_dateien(args.dateien))
    if args.schluessel is not None:
        module = [m.strip() for m in args.schluessel.split(",") if m.strip()]
        return _ausgabe(pruefe_schluessel(module))
    p.error("--dateien, --schluessel oder (ab Aufgabe 30) ein Profilname")
    return 2


if __name__ == "__main__":
    sys.exit(main())
