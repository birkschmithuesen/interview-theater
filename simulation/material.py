"""Die erfundenen Interviewtranskripte laden, pruefen und mischen.

Fuenfzehn Dateien in drei Sets (``simulation/interviews/set{1,2,3}/*.md``),
je 250-450 Woerter gesprochenes Deutsch mit A:/B:-Wechsel. Frei erfunden --
keine Zeile stammt aus einem echten Interview.

Jede Datei traegt einen Kopf mit fuenf Feldern:

``name``            wie das Interview im Workshop heisst ("Meryem")
``set``             1, 2 oder 3
``themen``          die Motive darin -- daraus leitet der Lauf Begriffe und
                    Fragen ab, damit die Kette Begriffe -> Fragen ->
                    Interviews stimmig ist
``sprachmerkmale``  woran man die Sprechweise erkennt (kurze Saetze,
                    Abbrueche, tuerkische Einsprengsel, ...)
``zitate_soll``     drei Saetze, die **woertlich** im Text stehen und die ein
                    guter Verdichter als Belegzitat finden muss. Sie sind der
                    Sollwert der Kennzahl ``zitate_soll`` (``kennzahlen.py``)

Der Kopf wird mit einem eigenen, winzigen Parser gelesen (``_lies_kopf``) und
nicht mit PyYAML: das Projekt haengt bewusst nur an ``httpx``, und die fuenf
Felder sind einfach genug, dass ein Parser dafuer kuerzer ist als die
Begruendung einer neuen Abhaengigkeit.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

VERZEICHNIS = Path(__file__).resolve().parent / "interviews"

#: Die drei Themenkreise. Der Text ist die Ueberschrift des Sets im Bericht.
SETS = {
    1: "Ankommen",
    2: "Arbeit und Familie",
    3: "Koerper und Bilder",
}

#: So viele Interviews fuehrt ein Lauf.
PRO_LAUF = 5

#: Grenzen der Wortzahl je Datei -- von ``tests/test_simulation_material.py``
#: geprueft. Unter 250 Woertern bekommt der Verdichter zu wenig Stoff (und
#: unter ``aufnahme.MINDEST_WOERTER`` wuerde er gar nicht erst gerufen), ueber
#: 450 wird der Szenen-Prompt mit fuenf Interviews unnoetig teuer.
WOERTER_MIN = 250
WOERTER_MAX = 450

#: Die Felder des Kopfes, die jede Datei haben muss.
PFLICHTFELDER = ("name", "set", "themen", "sprachmerkmale", "zitate_soll")

_TRENNER = "---"


@dataclass(frozen=True)
class Interview:
    """Ein erfundenes Transkript samt Kopf."""

    kennung: str            # Dateiname ohne Endung, z. B. "1-meryem"
    name: str
    nummer: int             # Set-Nummer
    themen: tuple[str, ...]
    sprachmerkmale: tuple[str, ...]
    zitate_soll: tuple[str, ...]
    transkript: str

    @property
    def woerter(self) -> int:
        return len(self.transkript.split())

    def teile(self, anzahl: int = 1) -> list[str]:
        """Zerlegt das Transkript in ``anzahl`` Stuecke -- fuer die
        Interviews, die als **zwei** Textimporte hereinkommen (Skript-Schritt
        3). Geschnitten wird an einer Leerzeile oder, wenn es keine gibt, an
        einem Zeilenumbruch; nie mitten in einer Replik."""
        if anzahl <= 1:
            return [self.transkript]
        zeilen = self.transkript.splitlines()
        schnitt = max(1, len(zeilen) // anzahl)
        stuecke = []
        for i in range(anzahl):
            ab = i * schnitt
            bis = len(zeilen) if i == anzahl - 1 else (i + 1) * schnitt
            stueck = "\n".join(zeilen[ab:bis]).strip()
            if stueck:
                stuecke.append(stueck)
        return stuecke or [self.transkript]


def _lies_wert(text: str) -> str | list[str]:
    """Ein einzeiliger Kopfwert: ``[a, b, c]`` wird zur Liste, alles andere
    zum String."""
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        return [t.strip().strip("\"'") for t in text[1:-1].split(",") if t.strip()]
    return text.strip("\"'")


def _lies_kopf(roh: str, pfad: Path) -> tuple[dict, str]:
    """Trennt den Kopf zwischen zwei ``---``-Zeilen vom Transkript.

    Zwei Listenformen, und die zweite ist kein Luxus: ``[a, b, c]`` in einer
    Zeile fuer kurze Stichwoerter, und Zeilen mit ``- `` darunter fuer die
    Soll-Zitate. Ganze Saetze enthalten Kommas, und eine Liste, die am Komma
    trennt, wuerde jedes Zitat in Stuecke reissen -- lautlos, und der Test
    'Zitat steht woertlich im Text' waere ploetzlich rot."""
    zeilen = roh.splitlines()
    if not zeilen or zeilen[0].strip() != _TRENNER:
        raise ValueError(f"{pfad}: kein Kopf (erste Zeile ist kein '---')")
    try:
        ende = next(i for i, z in enumerate(zeilen[1:], 1) if z.strip() == _TRENNER)
    except StopIteration:
        raise ValueError(f"{pfad}: Kopf wird nie geschlossen ('---' fehlt)") from None

    kopf: dict = {}
    offen: str | None = None
    for zeile in zeilen[1:ende]:
        if not zeile.strip():
            continue
        if zeile.lstrip().startswith("- "):
            if offen is None:
                raise ValueError(f"{pfad}: Listenzeile ohne Schluessel: {zeile!r}")
            kopf[offen].append(zeile.lstrip()[2:].strip().strip("\"'"))
            continue
        schluessel, trenner, wert = zeile.partition(":")
        if not trenner:
            raise ValueError(f"{pfad}: Kopfzeile ohne Doppelpunkt: {zeile!r}")
        schluessel = schluessel.strip()
        if not wert.strip():
            kopf[schluessel] = []
            offen = schluessel
            continue
        kopf[schluessel] = _lies_wert(wert)
        offen = None
    return kopf, "\n".join(zeilen[ende + 1:]).strip()


def lade(pfad: Path) -> Interview:
    """Liest eine Interviewdatei und prueft ihren Kopf auf Vollstaendigkeit.

    Die Pruefung steht hier und nicht nur im Test: eine Datei mit fehlendem
    ``zitate_soll`` wuerde sonst einen ganzen bezahlten Lauf durchlaufen und
    erst im Bericht als stille Null auffallen."""
    kopf, transkript = _lies_kopf(pfad.read_text(encoding="utf-8"), pfad)
    fehlend = [f for f in PFLICHTFELDER if not kopf.get(f)]
    if fehlend:
        raise ValueError(f"{pfad}: fehlende Kopffelder: {', '.join(fehlend)}")
    if not transkript:
        raise ValueError(f"{pfad}: kein Transkript unter dem Kopf")
    return Interview(
        kennung=pfad.stem,
        name=str(kopf["name"]),
        nummer=int(kopf["set"]),
        themen=tuple(kopf["themen"]),
        sprachmerkmale=tuple(kopf["sprachmerkmale"]),
        zitate_soll=tuple(kopf["zitate_soll"]),
        transkript=transkript,
    )


def lade_set(nummer: int) -> list[Interview]:
    """Alle Interviews eines Sets, nach Dateinamen sortiert."""
    verzeichnis = VERZEICHNIS / f"set{nummer}"
    if not verzeichnis.is_dir():
        raise ValueError(f"unbekanntes Set: {nummer}")
    return [lade(p) for p in sorted(verzeichnis.glob("*.md"))]


def lade_alle() -> list[Interview]:
    """Alle fuenfzehn Interviews, Set fuer Set."""
    return [i for nummer in sorted(SETS) for i in lade_set(nummer)]


def _verteile(anzahl_sets: int, gesamt: int, zufall: random.Random) -> list[int]:
    """Wie viele Interviews je Set bei ``--mix``: je 1-2, in Summe ``gesamt``.

    Erst jedem Set eines, dann die Reste auf zufaellig gewaehlte Sets
    verteilen -- so bleibt die Zusage "je Set 1-2" eingehalten, ohne dass
    eine feste Aufteilung wie [2,2,1] jeden Lauf gleich aussehen liesse."""
    if not 1 <= gesamt <= 2 * anzahl_sets:
        raise ValueError(
            f"{gesamt} Interviews lassen sich nicht auf {anzahl_sets} Sets "
            "zu je 1-2 verteilen"
        )
    verteilung = [1] * anzahl_sets
    reihenfolge = list(range(anzahl_sets))
    zufall.shuffle(reihenfolge)
    for i in reihenfolge[: gesamt - anzahl_sets]:
        verteilung[i] = 2
    return verteilung


def waehle(
    *,
    ein_set: int | None = None,
    mix: list[int] | None = None,
    seed: int = 0,
    anzahl: int = PRO_LAUF,
) -> list[Interview]:
    """Die fuenf Interviews eines Laufs -- reproduzierbar aus ``seed``.

    Drei Wege, wie das Skript sie beschreibt:

    * ``ein_set``: die fuenf Interviews dieses Sets, Reihenfolge gemischt.
    * ``mix``: je Set 1-2 Interviews (``_verteile``), in Summe ``anzahl``.
    * sonst: ``anzahl`` aus allen fuenfzehn.

    Derselbe Seed ergibt dieselbe Auswahl UND dieselbe Reihenfolge -- ohne
    das waere ein zweiter Lauf nach einer Prompt-Aenderung nicht mit dem
    ersten vergleichbar, und genau dafuer gibt es den Simulator."""
    zufall = random.Random(seed)
    if ein_set is not None:
        gezogen = lade_set(ein_set)
        zufall.shuffle(gezogen)
        return gezogen[:anzahl]
    if mix:
        gezogen = []
        for nummer, wie_viele in zip(mix, _verteile(len(mix), anzahl, zufall)):
            aus_set = lade_set(nummer)
            zufall.shuffle(aus_set)
            gezogen.extend(aus_set[:wie_viele])
        zufall.shuffle(gezogen)
        return gezogen
    alle = lade_alle()
    zufall.shuffle(alle)
    return alle[:anzahl]


# ---------------------------------------------------------------------------
# Begriffe und Fragen aus den Themen der gezogenen Interviews
# ---------------------------------------------------------------------------

#: So viele Begriffe wirft die Gruppe ein (Skript-Schritt 1).
BEGRIFFE_MIN = 3
BEGRIFFE_MAX = 5


def begriffe(gezogene: list[Interview], zufall: random.Random) -> list[str]:
    """Drei bis fuenf Begriffe aus den Themen der gezogenen Interviews.

    Ohne Dubletten und in gemischter Reihenfolge: die Themenlisten der
    Interviews ueberschneiden sich absichtlich (fuenf Interviews eines Sets
    kreisen um dieselbe Sache), und eine Begriffsliste, in der 'Koffer'
    zweimal steht, waere die erste Ungereimtheit, die eine Gruppe dem Bot
    ankreiden wuerde."""
    gesehen: list[str] = []
    for interview in gezogene:
        for thema in interview.themen:
            if thema not in gesehen:
                gesehen.append(thema)
    zufall.shuffle(gesehen)
    anzahl = min(len(gesehen), zufall.randint(BEGRIFFE_MIN, BEGRIFFE_MAX))
    return gesehen[:anzahl]


#: Muster der Fragen, die die Gruppe aus einem Begriff entwickelt. Die Form
#: "Thema: Frage?" ist die, die ``erkenner.fragen_setzen`` erwartet und die
#: die Gruppenseite fett setzen kann (``scripts/pruefe_prompts.fragen_ohne_thema``).
FRAGE_MUSTER = "{begriff}: Was faellt dir zu {begriff} als Erstes ein?"


def fragenvorschlag(begriffsliste: list[str]) -> str:
    """Eine Frageliste, wie die Gruppe sie im Kopf hat, bevor der Bot sie
    formuliert -- als Zielbeschreibung fuer die Stimmen, nicht als Text, den
    sie abschreiben sollen."""
    return "\n".join(FRAGE_MUSTER.format(begriff=b) for b in begriffsliste)
