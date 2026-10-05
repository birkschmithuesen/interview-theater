"""Einmaliger, deterministischer Umzug der alten AGENTS.md nach docs/agents/
(Spec docs/superpowers/specs/2026-10-05-agents-md-index-design.md).

Schneidet ``git show cb200e4:AGENTS.md`` nach festen Zeilenbereichen. Bei
doppelten Kapiteln steht die juengere Fassung voll in der Zieldatei, von der
aelteren nur die Absaetze, deren normalisierter Text in der juengeren fehlt --
unter einer eigenen Ueberschrift, damit sie von Hand eingeordnet oder als
Dublette in docs/agents/umzug-dubletten.txt eingetragen werden.

Bleibt als Nachweis im Repo; ein zweiter Lauf ueberschreibt die Handarbeit.

    uv run --extra dev python -m scripts.agents_umzug_aufteilen
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.pruefe_agents_umzug import BASIS, absaetze, normalisiere

WURZEL = Path(__file__).resolve().parent.parent
ZIEL = WURZEL / "docs" / "agents"

# datei: (titel, behalten, aelter) -- Bereiche 1-basiert, inklusive
PLAN: dict[str, tuple[str, tuple[int, int], tuple[int, int] | None]] = {
    "aufbau.md": ("Aufbau, Modulkarte, Dortmund-Stand", (1, 226), None),
    "entscheidungen.md": ("Bindende Entwurfsentscheidungen", (227, 1121), None),
    "dramaturgie-pruefung.md": ("Die Dramaturgie-Pruefung", (1122, 1269), None),
    "fallen.md": ("Die Fallen", (2170, 2277), (1270, 1365)),
    "spec-abweichungen.md": ("Wo SPEC und Code auseinanderlaufen", (2278, 2324), (1366, 1394)),
    "starten-und-testen.md": ("Starten und testen", (2325, 2437), (1395, 1504)),
    "weboberflaeche.md": ("Weboberflaeche", (2438, 3324), (1505, 1599)),
    "korpus-und-simulation.md": ("Korpus und Simulation", (3325, 3520), (1600, 1801)),
    "was-bewusst-fehlt.md": ("Was bewusst fehlt", (3521, 3707), (1802, 2075)),
    "workshop-profil.md": ("Workshop-Profil", (2076, 2169), None),
}

KOPF = ("> Ausgelagert aus `AGENTS.md` am 05.10.2026 (Stand `{basis}`, Zeilen {bereiche}).\n"
        "> Wortlaut unveraendert; Index und Kurzfassung stehen in `AGENTS.md`.\n")


def _zeilen(text: str, von: int, bis: int) -> str:
    return "\n".join(text.splitlines()[von - 1:bis])


def pruefe_abdeckung(gesamtzeilen: int) -> None:
    bereiche = []
    for _, behalten, aelter in PLAN.values():
        bereiche.append(behalten)
        if aelter:
            bereiche.append(aelter)
    bereiche.sort()
    erwartet = 1
    for von, bis in bereiche:
        if von != erwartet:
            raise SystemExit(f"Luecke/Ueberlappung bei Zeile {erwartet} (naechster Bereich {von}-{bis})")
        erwartet = bis + 1
    if erwartet != gesamtzeilen + 1:
        raise SystemExit(f"Bereiche enden bei {erwartet - 1}, Datei hat {gesamtzeilen} Zeilen")


def baue(alt: str, titel: str, behalten: tuple[int, int],
         aelter: tuple[int, int] | None) -> str:
    bereiche = f"{behalten[0]}–{behalten[1]}"
    if aelter:
        bereiche += f" und {aelter[0]}–{aelter[1]}"
    teile = [f"# {titel}\n", KOPF.format(basis=BASIS, bereiche=bereiche),
             _zeilen(alt, *behalten)]
    if aelter:
        vorhanden = normalisiere(_zeilen(alt, *behalten))
        rest = [a for _, a in absaetze(_zeilen(alt, *aelter))
                if normalisiere(a) not in vorhanden]
        if rest:
            teile.append(f"\n## NUR IN DER AELTEREN FASSUNG (Z. {aelter[0]}–{aelter[1]}) — EINORDNEN ODER ALS DUBLETTE EINTRAGEN\n")
            teile.append("\n\n".join(rest))
    return "\n".join(teile).rstrip() + "\n"


def main() -> int:
    alt = subprocess.run(["git", "show", f"{BASIS}:AGENTS.md"], cwd=WURZEL,
                         check=True, capture_output=True, text=True).stdout
    pruefe_abdeckung(len(alt.splitlines()))
    ZIEL.mkdir(parents=True, exist_ok=True)
    for datei, (titel, behalten, aelter) in PLAN.items():
        (ZIEL / datei).write_text(baue(alt, titel, behalten, aelter), encoding="utf-8")
        print(f"{datei}: geschrieben")
    return 0


if __name__ == "__main__":
    sys.exit(main())
