"""Schicht 4a: das Erfolgsmass -- ist der Text durch die Ueberarbeitung
besser geworden?

**Nicht die Zahl der Befunde.** Das ist die eine Entscheidung, um die es in
diesem Modul geht. Ein Befund entsteht nur, wo etwas schieflaeuft
(``fanout._befund_aus``: "Score 2 ist kein Befund"), und ein guter Text
erzeugt deshalb zu Recht keinen. Wer Befunde zaehlt, misst drei Dinge auf
einmal und kann sie nicht trennen:

* Der Text wurde besser -- weniger Befunde.
* Der Text war schon gut -- auch weniger Befunde.
* Der Text wurde schlechter, und der Judge fand fuer seinen Befund kein
  Belegzitat mehr, weil die Stelle umgeschrieben wurde -- **ebenfalls**
  weniger Befunde. Genau der gefaehrliche Fall saehe aus wie ein Erfolg.

Verglichen werden deshalb die **Scores je Frage und Szene**
(``dramaturgie_bewertung``, siehe ``fanout._merke``): dieselbe Frage, dieselbe
Adresse, zwei Runden. Drei Ausgaenge, und alle drei sind eine Aussage:

* gestiegen -> **besser**
* gefallen -> **die Ueberarbeitung hat geschadet**. Das ist der Befund, wegen
  dem es diese Schicht gibt: er muss sichtbar sein und bricht die Schleife ab
  (``schleife.schliesse``).
* gleich -> keine Wirkung; die Runde hat Geld gekostet und nichts bewegt.

**Verglichen wird nur, was in beiden Runden gemessen wurde.** Eine Frage, die
in einer Runde keinen bestaetigten Beleg hatte, hat dort keinen Score -- und
ein fehlender Score ist keine Null. Sie faellt aus der Bilanz heraus, statt
als Verschlechterung zu erscheinen.
"""

from __future__ import annotations

from dataclasses import dataclass

from interview_theater.dramaturgie import fanout

#: Die drei Ausgaenge eines Vergleichs, in der Reihenfolge, in der sie in der
#: Bilanz stehen: **zuerst der Schaden**. Eine Zeile, die eine Gruppe zu
#: sehen bekommt, faengt mit dem an, was sie zurueckdrehen will.
SCHLECHTER = "schlechter"
BESSER = "besser"
GLEICH = "gleich"

_RANG = {SCHLECHTER: 0, BESSER: 1, GLEICH: 2}


def bezeichnung(pruefung: str) -> str:
    """Der lesbare Name einer Frage, aus dem Dateinamen ihres Prompts.

    ``dramaturgie/a9_fokus`` -> ``Fokus``. Aus **einer** Quelle und nicht aus
    einer zweiten Liste daneben: eine Frage, die umbenannt wird, ohne dass
    ihre Beschriftung mitgeht, faellt sonst niemandem auf."""
    pfad = fanout.PROMPTS.get(pruefung)
    if not pfad:
        return pruefung.upper()
    _, _, name = pfad.rpartition("/")
    _, _, wort = name.partition("_")
    return (wort or name).replace("_", " ").capitalize()


@dataclass(frozen=True)
class Vergleich:
    """Eine Frage an einer Adresse, vorher und nachher.

    ``szene`` ist ``None``, wo die Frage dem ganzen Stueck galt (A2, A6,
    A11)."""

    pruefung: str
    szene: int | None
    vorher: int
    nachher: int

    @property
    def richtung(self) -> str:
        if self.nachher > self.vorher:
            return BESSER
        if self.nachher < self.vorher:
            return SCHLECHTER
        return GLEICH

    @property
    def adresse(self) -> str:
        name = f"{self.pruefung.upper()} {bezeichnung(self.pruefung)}"
        return name if self.szene is None else f"{name}, Szene {self.szene}"

    def zeile(self) -> str:
        return (
            f"{self.adresse}: {self.vorher} -> {self.nachher} ({self.richtung})"
        )


#: Kopf und Fuss der Bilanz. Sie sagen die beiden Runden und die drei Zahlen
#: -- mehr braucht niemand, um zu entscheiden, ob eine dritte Runde sinnvoll
#: waere.
KOPF = "Bilanz Runde {von} -> {nach}:"
FUSS = "{besser} besser, {gleich} gleich, {schlechter} schlechter."
OHNE_VERGLEICH = (
    "Bilanz Runde {von} -> {nach}: nichts vergleichbar - in einer der beiden "
    "Runden gab es zu keiner Frage einen Score mit bestaetigtem Belegzitat."
)


@dataclass(frozen=True)
class Bilanz:
    """Was zwei Runden voneinander unterscheidet -- klein und lesbar."""

    von: int
    nach: int
    vergleiche: tuple[Vergleich, ...] = ()

    def _nach_richtung(self, richtung: str) -> list[Vergleich]:
        return [v for v in self.vergleiche if v.richtung == richtung]

    @property
    def besser(self) -> list[Vergleich]:
        return self._nach_richtung(BESSER)

    @property
    def schlechter(self) -> list[Vergleich]:
        return self._nach_richtung(SCHLECHTER)

    @property
    def gleich(self) -> list[Vergleich]:
        return self._nach_richtung(GLEICH)

    @property
    def geschadet(self) -> bool:
        """Hat die Ueberarbeitung **irgendwo** geschadet?

        Ein einziger gefallener Score genuegt. Nicht verrechnet mit den
        gestiegenen: "drei besser, einer schlechter" ist kein Erfolg, sondern
        ein Erfolg und ein Schaden, und der Schaden steht in einer Szene, die
        die Gruppe schon gut fand."""
        return bool(self.schlechter)

    def zeilen(self) -> list[str]:
        if not self.vergleiche:
            return [OHNE_VERGLEICH.format(von=self.von, nach=self.nach)]
        return (
            [KOPF.format(von=self.von, nach=self.nach)]
            + [f"- {v.zeile()}" for v in self.vergleiche]
            + [FUSS.format(
                besser=len(self.besser), gleich=len(self.gleich),
                schlechter=len(self.schlechter),
            )]
        )

    def als_text(self) -> str:
        return "\n".join(self.zeilen())


def _scores(bewertungen) -> dict[tuple[str, int | None], int]:
    """Adresse -> Score. Bei zwei Zeilen zur selben Adresse gewinnt die
    spaetere: die Reihenfolge aus ``repo.dramaturgie_bewertungen`` ist die,
    in der gemessen wurde."""
    ergebnis: dict[tuple[str, int | None], int] = {}
    for b in bewertungen:
        pruefung = (fanout._feld(b, "pruefung") or "").strip()
        score = fanout._feld(b, "score")
        if not pruefung or score is None:
            continue
        szene = fanout._feld(b, "szene")
        ergebnis[(pruefung, None if szene is None else int(szene))] = int(score)
    return ergebnis


def baue(vorher, nachher, von: int = 0, nach: int = 0) -> Bilanz:
    """Die Bilanz aus zwei Listen von Bewertungen (Dicts oder DB-Zeilen).

    **Nur gemeinsame Adressen.** Was in einer der beiden Runden fehlt, wird
    nicht als 0 unterstellt: ein fehlender Score heisst "nicht gemessen" und
    nicht "ganz schlecht"."""
    links, rechts = _scores(vorher), _scores(nachher)
    gemeinsam = [
        Vergleich(pruefung, szene, links[(pruefung, szene)], rechts[(pruefung, szene)])
        for (pruefung, szene) in links
        if (pruefung, szene) in rechts
    ]
    gemeinsam.sort(key=lambda v: (
        _RANG.get(v.richtung, 9),
        v.szene if v.szene is not None else -1,
        v.pruefung,
    ))
    return Bilanz(von=von, nach=nach, vergleiche=tuple(gemeinsam))


def aus_datenbank(conn, chat_id: int, von: int, nach: int) -> Bilanz:
    """Dieselbe Bilanz aus den gespeicherten Scores.

    Die Bilanz wird **nicht** als eigene Zeile abgelegt, sondern aus den
    Bewertungen beider Runden gerechnet: aus zwei Messungen laesst sich der
    Vergleich jederzeit neu bilden, aus einem abgelegten Vergleich nie wieder
    die Messung."""
    from interview_theater import repo

    return baue(
        repo.dramaturgie_bewertungen(conn, chat_id, runde=von),
        repo.dramaturgie_bewertungen(conn, chat_id, runde=nach),
        von=von, nach=nach,
    )
