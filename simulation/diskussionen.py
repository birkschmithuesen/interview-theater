"""Gesprochene Diskussionsskripte der Simulation (Karte t_fc2c1bfa, Punkt 4).

Neben dem langen Skript sprechen Gruppen live knapp: "Home. Because …" —
zusammen weniger Zeichen als die alte Board-Schwelle (600). `knapp` endet mit
einer Pause laenger als der VAD-Schnitt (2,5 s), sodass das Ende-Segment beim
Druck auf "Discussion done" leer ist (Birks Nachtrag D). `verhoerer` traegt
einen absichtlich falschen Begriff mit Kontextsatz; das Board soll ihn
korrigieren.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ORDNER = Path(__file__).resolve().parent / "diskussion"
_SPRECHER = re.compile(r"^\s*[A-Z]:\s*")


@dataclass(frozen=True)
class Diskussion:
    name: str
    datei: Path
    erwartete_begriffe: tuple[str, ...]
    verhoerer: dict[str, str] = field(default_factory=dict)
    ende_pause_s: float = 0.0

    def text(self) -> str:
        zeilen = [_SPRECHER.sub("", z).strip() for z in self.datei.read_text(encoding="utf-8").splitlines()]
        return " ".join(z for z in zeilen if z)

    def zeichen(self) -> int:
        return len(self.text())


DISKUSSIONEN: dict[str, Diskussion] = {
    "lang": Diskussion("lang", ORDNER / "p1-diskussion.txt",
                       ("home", "border", "waiting", "noise", "night shift", "belonging", "language")),
    "knapp": Diskussion("knapp", ORDNER / "p1-knapp.txt",
                        ("home", "border", "waiting", "noise", "language"), ende_pause_s=8.0),
    "verhoerer": Diskussion("verhoerer", ORDNER / "p1-verhoerer.txt",
                            ("night shift", "belonging", "language", "waiting"),
                            verhoerer={"night shed": "night shift"}),
    "nachtrag": Diskussion("nachtrag", ORDNER / "p1-nachtrag.txt", ("noise",), ende_pause_s=8.0),
    # Padua live-reif, Phase 3+4 (Karte t_92f99911, Task 2): Interviews
    # (knapp unter/ueber aufnahme.MINDEST_WOERTER) und ein Brainstorm-Bogen
    # (ueber brainstorm.VORGABE_MIN_ZEICHEN_BEI_ABSCHLUSS).
    "interview-kurz": Diskussion("interview-kurz", ORDNER / "p3-interview-kurz.txt",
                                 ("station",), ende_pause_s=3.0),
    "interview-gemischt": Diskussion("interview-gemischt", ORDNER / "p3-interview-gemischt.txt",
                                     ("bench", "cousin", "waiting"), ende_pause_s=3.0),
    "brainstorm-bogen": Diskussion("brainstorm-bogen", ORDNER / "p4-brainstorm-bogen.txt",
                                   ("bench", "cafe", "cousin", "bag"), ende_pause_s=3.0),
}
