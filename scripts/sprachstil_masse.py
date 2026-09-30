"""Mechanische Masse fuer den Sprachstil-Wirkungstest (Padua M1, 30.09.2026).

Reine Funktionen, keine Datenbank, kein Netz, kein Modellaufruf -- die
Bausteine, mit denen `scripts/sprachstil_wirkung.py` (Task 2-4) misst, ob
`figur.sprachstil` (Phase 4) den erzeugten Text tatsaechlich veraendert.

**Zwei Wege zur "Rede" einer Figur**, je nach Textform:

- `direkte_rede`: Prosa (Phase 6, Kurzgeschichte) enthaelt direkte Rede nur
  sparsam, in Anfuehrungszeichen. Eine Rede wird der naechststehenden Figur
  im selben Absatz zugeordnet -- vor oder nach dem Zitat, welcher Name
  naeher am Zitat steht, gewinnt. Ohne zuordenbaren Namen bleibt die Rede
  unter dem Schluessel `None` stehen, statt zu verschwinden.
- `sprecherzeilen`: Theatertext (Feinschliff, Phase 7) traegt Sprecherkoepfe
  ("NAME:"). Angelehnt an die Regel aus `interview_theater/sprecher.py`
  (nur gelesen, nicht veraendert): `sprecher.zerlege` liefert die Zuordnung,
  hier kommt nur das Entfernen der Regieklammern dazu -- eine Regieanweisung
  ist keine gesprochene Sprache und soll die Satz- und Wortmasse nicht
  verfaelschen.

Darauf aufbauend die eigentlichen Masse: Satzlaenge, Wortschatz, die
Jaccard-Aehnlichkeit zweier Wortschaetze, und der Markeranteil einer
Redenliste gegen eine Markerliste. `MARKER` traegt die drei Stile aus
Task 2 (KNAPP, SCHACHTEL, FUELL) -- die Woerter stehen wortgleich im Plan.
"""

from __future__ import annotations

import re

from interview_theater import sprecher

#: Die vier erlaubten Anfuehrungsstile aus dem Plan: deutsch ("„…“"),
#: englisch/ASCII ('"…"'), und Guillemets in beiden Richtungen ("»…«",
#: "«…»"). Je ein Erfassungsblock, nicht verschachtelt -- direkte Rede in
#: Prosa hat keine Anfuehrungszeichen im Anfuehrungszeichen.
_ANFUEHRUNG = re.compile(
    "„([^“]*)“"
    '|"([^"]*)"'
    "|»([^«]*)«"
    "|«([^»]*)»"
)

#: Ein Wort: Buchstaben, Ziffern, Apostroph -- wie in `interview_theater.sprecher`.
_WORT = re.compile(r"[\w'’]+", re.UNICODE)

#: Ein Satzende: `.`, `!` oder `?`, gefolgt von Leerraum. Reicht fuer die
#: kurzen, erfundenen Stiltexte dieser Messkarte -- keine Abkuerzungsliste,
#: kein Sonderfall fuer Ellipsen.
_SATZENDE = re.compile(r"(?<=[.!?])\s+")

#: Regieanweisungen in runden Klammern, wie in `interview_theater.sprecher`.
_KLAMMER = re.compile(r"\([^()]*\)")


def _woerter_in(text: str) -> list[str]:
    """Die Woerter eines Textes, roh (nicht kleingeschrieben)."""
    return _WORT.findall(text or "")


def _namen_klein(namen) -> dict[str, str]:
    """Kleingeschriebener Name -> Schreibweise, wie sie in `namen` stand."""
    return {(n or "").strip().lower(): (n or "").strip() for n in (namen or []) if (n or "").strip()}


def _namen_muster(namen_klein: dict[str, str]) -> re.Pattern | None:
    """Ein Muster, das jeden Namen als ganzes Wort findet -- oder None."""
    if not namen_klein:
        return None
    woerter = sorted(namen_klein, key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(n) for n in woerter) + r")\b", re.IGNORECASE)


def direkte_rede(text: str, namen) -> dict[str | None, list[str]]:
    """Direkte Rede in Prosa, je Figur zugeordnet.

    Ein Zitat (in „…“, "…", »…« oder «…») wird der Figur zugeordnet, deren
    Name im selben Absatz am naechsten am Zitat steht -- davor ("Meryem
    sagt: „…“") oder danach ("„Egal“, sagt Meryem."), welcher Abstand
    kleiner ist, gewinnt. Kein Name in Reichweite -> Schluessel `None`.

    `namen` ist eine Liste oder Menge von Figurennamen in ihrer normalen
    Schreibweise; der Vergleich selbst ist gross-/kleinschreibungsunabhaengig.
    """
    namen_klein = _namen_klein(namen)
    muster = _namen_muster(namen_klein)
    ergebnis: dict[str | None, list[str]] = {}
    for absatz in re.split(r"\n\s*\n", text or ""):
        treffer = list(_ANFUEHRUNG.finditer(absatz))
        for i, fund in enumerate(treffer):
            zitat = next(g for g in fund.groups() if g is not None)
            vorher_start = treffer[i - 1].end() if i > 0 else 0
            nachher_ende = treffer[i + 1].start() if i + 1 < len(treffer) else len(absatz)
            vorher = absatz[vorher_start:fund.start()]
            nachher = absatz[fund.end():nachher_ende]

            name_vorher, abstand_vorher = None, None
            if muster is not None:
                funde_vorher = list(muster.finditer(vorher))
                if funde_vorher:
                    letzter = funde_vorher[-1]
                    name_vorher = namen_klein[letzter.group(1).lower()]
                    abstand_vorher = len(vorher) - letzter.end()

            name_nachher, abstand_nachher = None, None
            if muster is not None:
                fund_nachher = muster.search(nachher)
                if fund_nachher is not None:
                    name_nachher = namen_klein[fund_nachher.group(1).lower()]
                    abstand_nachher = fund_nachher.start()

            if name_vorher is None:
                name = name_nachher
            elif name_nachher is None:
                name = name_vorher
            else:
                name = name_vorher if abstand_vorher <= abstand_nachher else name_nachher

            ergebnis.setdefault(name, []).append(zitat)
    return ergebnis


def sprecherzeilen(text: str, namen=None) -> dict[str, list[str]]:
    """Sprecherzeilen eines Theatertexts, je Figur -- Regieklammern entfernt.

    Nutzt `interview_theater.sprecher.zerlege` fuer die Zuordnung (dieselbe
    Regel wie im Feinschliff: Name am Zeilenanfang, dann Doppelpunkt) und
    entfernt danach, was in runden Klammern steht -- eine Regieanweisung
    ("(dreht sich weg)") ist kein gesprochenes Wort und soll die Satz- und
    Wortmasse nicht verfaelschen.
    """
    namen_klein = set(_namen_klein(namen))
    ergebnis: dict[str, list[str]] = {}
    for name, rede in sprecher.zerlege(text, namen_klein):
        bereinigt = _KLAMMER.sub(" ", rede)
        bereinigt = re.sub(r"\s+", " ", bereinigt).strip()
        if bereinigt:
            ergebnis.setdefault(name, []).append(bereinigt)
    return ergebnis


def saetze(reden: list[str]) -> list[str]:
    """Alle Saetze einer Redenliste, ueber alle Reden hinweg."""
    ergebnis: list[str] = []
    for rede in reden or []:
        for teil in _SATZENDE.split((rede or "").strip()):
            teil = teil.strip()
            if teil:
                ergebnis.append(teil)
    return ergebnis


def mittlere_satzlaenge(reden: list[str]) -> float:
    """Woerter je Satz, gemittelt -- 0.0 ohne einen einzigen Satz."""
    saetze_liste = saetze(reden)
    if not saetze_liste:
        return 0.0
    laengen = [len(_woerter_in(s)) for s in saetze_liste]
    return sum(laengen) / len(laengen)


def wortschatz(reden: list[str]) -> set[str]:
    """Die Menge der kleingeschriebenen Woerter einer Redenliste, ohne
    Satzzeichen und ohne Mehrfachzaehlung."""
    ergebnis: set[str] = set()
    for rede in reden or []:
        ergebnis.update(w.lower() for w in _woerter_in(rede))
    return ergebnis


def jaccard(a: set, b: set) -> float:
    """Jaccard-Aehnlichkeit zweier Mengen: |a UND b| / |a ODER b|.

    Zwei leere Mengen sind 0.0, nicht 1.0 -- eine Figur ohne jede Rede ist
    keinem Wortschatz aehnlich, auch nicht sich selbst."""
    vereinigung = (a or set()) | (b or set())
    if not vereinigung:
        return 0.0
    return len((a or set()) & (b or set())) / len(vereinigung)


def marker_anteil(reden: list[str], marker: list[str]) -> float:
    """Treffer aus `marker` je 100 Woerter in `reden`.

    Jeder Marker zaehlt als ganzes Wort (Wortgrenzen, `\\b`), auch wenn er
    aus mehreren Woertern besteht ("weisst du" ist EIN Treffer). Case-
    insensitiv. Ohne ein einziges Wort in `reden` ist das Ergebnis 0.0,
    nicht eine Division durch null."""
    text = " ".join(reden or [])
    gesamt = len(_woerter_in(text))
    if gesamt == 0:
        return 0.0
    treffer = 0
    for eintrag in marker or []:
        muster = re.compile(r"\b" + re.escape(eintrag) + r"\b", re.IGNORECASE)
        treffer += len(muster.findall(text))
    return 100 * treffer / gesamt


#: Marker je Stil, wortgleich aus dem Plan (Task 2) -- KNAPP hat dort keine
#: eigene Markerliste, sondern zwei Beispielsaetze ("Egal." "Weiter."); die
#: beiden Woerter daraus sind der Marker. SCHACHTEL und FUELL sind dort als
#: Wortlisten benannt und werden hier unveraendert uebernommen.
MARKER: dict[str, list[str]] = {
    "KNAPP": ["egal", "weiter"],
    "SCHACHTEL": [
        "wobei", "insofern", "gewissermassen", "quasi", "de facto", "per se",
        "prinzipiell",
    ],
    "FUELL": ["halt", "irgendwie", "weisst du", "sozusagen", "also"],
}
