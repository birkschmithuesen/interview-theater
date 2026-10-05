"""Verlustfreiheit des AGENTS.md-Umzugs (Spec docs/superpowers/specs/
2026-10-05-agents-md-index-design.md, Abnahme 2).

Jeder nicht-leere Absatz der alten AGENTS.md (``git show <basis>:AGENTS.md``)
muss nach Normalisierung in der neuen AGENTS.md oder unter
``docs/agents/**/*.md`` stehen. Die einzige Ausnahme sind Absaetze aus einem
doppelt vorhandenen ``## ``-Kapitel, deren alte Startzeile in
``docs/agents/umzug-dubletten.txt`` steht -- sie werden im Bericht gelistet.

Kein Modell, kein Netz. Exit 0 = GRUEN, 1 = ROT.

    uv run --extra dev python -m scripts.pruefe_agents_umzug
    uv run --extra dev python -m scripts.pruefe_agents_umzug --ohne-agents-md
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

BASIS = "0680d20"
AUSNAHMEN = Path("docs/agents/umzug-dubletten.txt")
WURZEL = Path(__file__).resolve().parent.parent


@dataclass
class Bericht:
    gesamt: int = 0
    fehlend: list[tuple[int, str]] = field(default_factory=list)
    dubletten: list[tuple[int, str]] = field(default_factory=list)
    ungueltige_ausnahmen: list[int] = field(default_factory=list)

    @property
    def gruen(self) -> bool:
        return not self.fehlend and not self.ungueltige_ausnahmen


def absaetze(text: str) -> list[tuple[int, str]]:
    """Durch Leerzeilen getrennte Bloecke mit ihrer 1-basierten Startzeile."""
    ergebnis: list[tuple[int, str]] = []
    start, block = 0, []
    for nr, zeile in enumerate(text.splitlines(), start=1):
        if zeile.strip():
            if not block:
                start = nr
            block.append(zeile)
        elif block:
            ergebnis.append((start, "\n".join(block)))
            block = []
    if block:
        ergebnis.append((start, "\n".join(block)))
    return ergebnis


def normalisiere(text: str) -> str:
    """Leerraum zusammenziehen, Ueberschriftsebene (#) ignorieren."""
    zeilen = [re.sub(r"^#+\s*", "", z.strip()) for z in text.splitlines()]
    return re.sub(r"\s+", " ", " ".join(zeilen)).strip()


def doppelte_kapitel_zeilen(text: str) -> set[int]:
    """Zeilennummern, die in einem ``## ``-Kapitel liegen, dessen Titel
    mehr als einmal vorkommt."""
    zeilen = text.splitlines()
    titel_je_zeile: list[str | None] = []
    aktuell: str | None = None
    for zeile in zeilen:
        if zeile.startswith("## "):
            aktuell = zeile[3:].strip()
        titel_je_zeile.append(aktuell)
    anzahl: dict[str, int] = {}
    for zeile in zeilen:
        if zeile.startswith("## "):
            anzahl[zeile[3:].strip()] = anzahl.get(zeile[3:].strip(), 0) + 1
    return {nr for nr, t in enumerate(titel_je_zeile, start=1)
            if t is not None and anzahl.get(t, 0) > 1}


def pruefe(alt: str, neu: str, ausnahmen: set[int]) -> Bericht:
    bericht = Bericht()
    neu_norm = normalisiere(neu)
    doppelt = doppelte_kapitel_zeilen(alt)
    starts = {nr for nr, _ in absaetze(alt)}
    bericht.ungueltige_ausnahmen = sorted(
        nr for nr in ausnahmen if nr not in starts or nr not in doppelt)
    for nr, absatz in absaetze(alt):
        bericht.gesamt += 1
        if normalisiere(absatz) in neu_norm:
            continue
        if nr in ausnahmen and nr in doppelt:
            bericht.dubletten.append((nr, absatz))
        else:
            bericht.fehlend.append((nr, absatz))
    return bericht


def lies_ausnahmen(pfad: Path) -> set[int]:
    if not pfad.exists():
        return set()
    zahlen: set[int] = set()
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        kern = zeile.split("#", 1)[0].strip()
        if kern:
            zahlen.add(int(kern))
    return zahlen


def _neuer_text(wurzel: Path, ohne_agents_md: bool) -> str:
    teile = [] if ohne_agents_md else [(wurzel / "AGENTS.md").read_text(encoding="utf-8")]
    for datei in sorted((wurzel / "docs" / "agents").rglob("*.md")):
        teile.append(datei.read_text(encoding="utf-8"))
    return "\n\n".join(teile)


def _kurz(text: str) -> str:
    einzeilig = normalisiere(text)
    return einzeilig if len(einzeilig) <= 90 else einzeilig[:87] + "..."


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--basis", default=BASIS)
    ap.add_argument("--wurzel", type=Path, default=WURZEL)
    ap.add_argument("--alt-datei", type=Path)
    ap.add_argument("--ohne-agents-md", action="store_true",
                    help="nur docs/agents/** als Ziel zaehlen")
    args = ap.parse_args(argv)
    if args.alt_datei:
        alt = args.alt_datei.read_text(encoding="utf-8")
    else:
        alt = subprocess.run(["git", "show", f"{args.basis}:AGENTS.md"],
                             cwd=args.wurzel, check=True, capture_output=True,
                             text=True).stdout
    bericht = pruefe(alt, _neuer_text(args.wurzel, args.ohne_agents_md),
                     lies_ausnahmen(args.wurzel / AUSNAHMEN))
    print(f"Absaetze alt: {bericht.gesamt}, Dubletten (Ausnahme): "
          f"{len(bericht.dubletten)}, fehlend: {len(bericht.fehlend)}, "
          f"ungueltige Ausnahmen: {len(bericht.ungueltige_ausnahmen)}")
    for nr, absatz in bericht.dubletten:
        print(f"DUBLETTE Z. {nr}: {_kurz(absatz)}")
    for nr in bericht.ungueltige_ausnahmen:
        print(f"UNGUELTIGE AUSNAHME Z. {nr} (kein Absatzanfang in doppeltem Kapitel)")
    for nr, absatz in bericht.fehlend:
        print(f"FEHLT Z. {nr}: {_kurz(absatz)}")
    print("GRUEN" if bericht.gruen else "ROT")
    return 0 if bericht.gruen else 1


if __name__ == "__main__":
    sys.exit(main())
