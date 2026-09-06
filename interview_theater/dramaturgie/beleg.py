"""Schicht 2: die Belegverifikation -- die wichtigste Einzelmassnahme.

**Warum** (Recherche § 4, Zeile "Note ohne Beleg / Halluzinierte Belege").
Ein Judge-LLM kann jede Note begruenden, auch eine falsche: die Begruendung
entsteht nach dem Urteil und rationalisiert es. Das einzige, was sich
mechanisch dagegenstellen laesst, ist die **Zitatpflicht**: der Judge muss
eine woertliche, zusammenhaengende Stelle aus genau dem Text nennen, den er
gesehen hat. Kommt sie dort nicht vor, ist der Befund nichts wert -- egal wie
plausibel er klingt.

**Die Regel, in einem Satz:** kein Treffer → **ein** Retry mit dem Hinweis
"dein Zitat kam im Text nicht vor" → danach ``unsicher: true``, der Score
wird verworfen, und der Befund geht **nicht** an den Schreib-LLM, sondern
ins Log.

**Eine Pruefung, nicht zwei.** Geprueft wird mit ``interview_theater.zitat``
-- derselben Funktion, die schon Verdichter, Kernzitate, Sprachprofil und
Schaerfung benutzen: Whitespace-Folgen zu einem Leerzeichen, typografische
Anfuehrungszeichen auf gerade, dann Teilstring. Eine zweite, grosszuegigere
Normalisierung nur fuer den Judge waere genau der Ort, an dem sich die
Zusage "geprueft" still aufweicht.

**Ein Retry, nicht zwei.** Der zweite Fehlversuch ist ein Befund ueber den
Judge, kein Befund ueber das Stueck. Wer dreimal fragt, bekommt beim dritten
Mal ein Zitat, das zufaellig passt.

**Gegen genau den vorgelegten Text.** ``material`` ist der Text, der im
Prompt zwischen den Markierungen stand -- bei B1 der Szenentext, bei A2 die
Synopsen-Kette, bei C1 die anonymisierte Replikenliste. Nicht das ganze
Stueck: ein Zitat aus einer Szene, die der Judge gar nicht gesehen hat, ist
kein Beleg, sondern ein Zufallstreffer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from interview_theater import zitat

log = logging.getLogger(__name__)

#: Mindestlaenge eines Belegs nach Normalisierung (Recherche § 2, "Gemeinsame
#: Konventionen"). Kuerzer ist kein Zitat, sondern ein Wort -- und ein Wort
#: findet sich in jedem Text.
MINDESTLAENGE = 15

#: Der Hinweis, mit dem der eine Retry laeuft. Er sagt, was falsch war, und
#: nicht, was das Modell antworten soll -- eine Vorgabe des erwarteten
#: Ergebnisses waere die Einladung, es zu erfinden.
HINWEIS = (
    "Dein Zitat kam im Text nicht woertlich vor. Nimm ein zusammenhaengendes "
    "Stueck aus dem Material zwischen den Markierungen, Buchstabe fuer "
    "Buchstabe abgeschrieben, mindestens 15 Zeichen lang. Fuegst du nichts "
    "zusammen und aenderst du nichts, findet die Pruefung es."
)

#: Was im Log steht, wenn auch der Retry nicht traegt.
GRUND_ZU_KURZ = "Beleg kuerzer als 15 Zeichen"
GRUND_FEHLT = "kein Beleg in der Antwort"
GRUND_NICHT_GEFUNDEN = "Beleg kommt im vorgelegten Text nicht woertlich vor"


@dataclass(frozen=True)
class Belegstand:
    """Das Ergebnis der Pruefung.

    ``geprueft`` heisst: das Zitat steht so im vorgelegten Text.
    ``unsicher`` heisst: auch nach dem Retry nicht -- der Score ist verworfen,
    der Befund darf keine Ueberarbeitung ausloesen (Recherche § 4,
    Faustregel)."""

    beleg: str | None
    geprueft: bool
    unsicher: bool
    versuche: int
    grund: str | None = None


def pruefe(beleg: str | None, material: str) -> bool:
    """Steht dieses Zitat woertlich im vorgelegten Text?

    Zwei Bedingungen, in dieser Reihenfolge: lang genug (``MINDESTLAENGE``
    nach Normalisierung) und ``zitat.pruefe``. Die Laengenpruefung steht
    vorn, weil ein Dreiwortzitat den Teilstringvergleich fast immer besteht
    und trotzdem nichts belegt."""
    if not (beleg or "").strip():
        return False
    kern = zitat.normalisiere(beleg).strip("\"'")
    if len(kern) < MINDESTLAENGE:
        return False
    return zitat.pruefe(beleg, material)


def _grund(beleg: str | None, material: str) -> str:
    if not (beleg or "").strip():
        return GRUND_FEHLT
    if len(zitat.normalisiere(beleg).strip("\"'")) < MINDESTLAENGE:
        return GRUND_ZU_KURZ
    return GRUND_NICHT_GEFUNDEN


def hole_mit_beleg(aufruf, material: str, marke: str = "") -> tuple[dict, Belegstand]:
    """Fragt den Judge, prueft den Beleg, wiederholt hoechstens einmal.

    ``aufruf(hinweis)`` bekommt beim ersten Mal ``None`` und beim Retry den
    ``HINWEIS``; es liefert die schon zerlegte Antwort als Dict mit einem
    Schluessel ``beleg``. Was der Aufrufer zurueckbekommt, ist genau eines
    von dreien:

    * Beleg im ersten Anlauf gefunden -- ``geprueft=True``, ``versuche=1``.
    * Beleg erst im Retry gefunden -- ``geprueft=True``, ``versuche=2``.
    * auch dann nicht -- ``geprueft=False``, ``unsicher=True``, und die
      Antwort kommt mit ``score=None`` und ``unsicher=True`` zurueck. **Der
      Score ist damit verworfen**, nicht abgewertet: eine Note ohne Beleg ist
      keine schlechtere Note, sie ist keine.

    ``marke`` steht nur im Log ("b1 Szene 4") und nie im Prompt."""
    antwort = dict(aufruf(None) or {})
    stand = _stand(antwort.get("beleg"), material, versuche=1)
    if stand.geprueft:
        return antwort, stand

    log.info(
        "Dramaturgie-Beleg nicht bestaetigt (%s), %s -- ein Retry",
        marke or "ohne Marke", stand.grund,
    )
    zweite = dict(aufruf(HINWEIS) or {})
    stand = _stand(zweite.get("beleg"), material, versuche=2)
    if stand.geprueft:
        return zweite, stand

    log.warning(
        "Dramaturgie-Befund verworfen (%s): %s -- Score verworfen, "
        "unsicher, geht nicht an den Schreib-LLM",
        marke or "ohne Marke", stand.grund,
    )
    zweite["score"] = None
    zweite["unsicher"] = True
    return zweite, stand


def _stand(beleg, material: str, versuche: int) -> Belegstand:
    text = (beleg or "").strip() or None
    if pruefe(text, material):
        return Belegstand(text, geprueft=True, unsicher=False, versuche=versuche)
    return Belegstand(
        text, geprueft=False, unsicher=versuche > 1, versuche=versuche,
        grund=_grund(text, material),
    )


def darf_an_den_schreiber(befund: dict, figuren=()) -> bool:
    """Die Faustregel aus Recherche § 4, im Code statt im Prompt.

    Ein Judge-Befund darf nur dann eine Ueberarbeitung ausloesen, wenn
    (a) das Zitat verifiziert ist, (b) ``unsicher`` falsch ist und (c) der
    Umbauvorschlag eine Szene adressiert und mindestens einen Figurennamen
    nennt -- "mehr Spannung erzeugen" ist keine Anweisung. Alles andere
    landet im Log fuer Menschen.

    ``figuren`` ist das Figurenverzeichnis der Gruppe. Ohne es bleibt (c)
    auf Szenennummer und nicht-leerem Vorschlag stehen: der Aufrufer, der
    keine Figurenliste hat, soll nicht stillschweigend eine strengere oder
    laxere Regel bekommen, sondern die, die er pruefen kann."""
    if not befund.get("beleg_geprueft"):
        return False
    if befund.get("unsicher"):
        return False
    vorschlag = (befund.get("vorschlag") or "").strip()
    if not vorschlag or befund.get("szene") is None:
        return False
    if figuren:
        return any(
            (name or "").strip() and (name.strip().casefold() in vorschlag.casefold())
            for name in figuren
        )
    return True
