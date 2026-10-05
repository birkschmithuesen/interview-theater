# AGENTS.md vom Archiv zum Index — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `AGENTS.md` von 258 kB auf ≤ 25.000 Bytes verkleinern, ohne einen Absatz zu verlieren: der Volltext zieht nach `docs/agents/`, AGENTS.md wird ein Index.

**Architecture:** Ein deterministisches Prüfskript (`scripts/pruefe_agents_umzug.py`) vergleicht jeden Absatz der alten Datei (`git show cb200e4:AGENTS.md`) mit AGENTS.md + `docs/agents/**/*.md`. Ein deterministisches Aufteilskript (`scripts/agents_umzug_aufteilen.py`) schneidet die alte Datei nach Zeilenbereichen in Zieldateien und legt bei doppelten Kapiteln die jüngere Fassung voll und von der älteren nur die abweichenden Absätze ab; diese Reste werden von Hand aufgelöst. Danach wird AGENTS.md neu geschrieben (verdichtet), ein Größentest wacht darüber.

**Tech Stack:** Python 3.11 (Standardbibliothek), pytest, git.

**Spec (bindend):** `docs/superpowers/specs/2026-10-05-agents-md-index-design.md`

## Global Constraints

- Basis-Commit für „alte AGENTS.md": `cb200e4` (HEAD von `wt/fabrik-a` vor dem Umbau). Alte Datei: 258.485 Bytes, 3.707 Zeilen.
- `wc -c AGENTS.md` ≤ 25.000 (Ziel ~20.000, Luft für Folgearbeit).
- Keine inhaltliche Änderung an Entscheidungen oder Code. Nur Umzug + Verdichtung. In `.py`-Dateien nur Kommentare/Docstrings anfassen, nie Laufzeit-Strings.
- Nichts ersatzlos löschen: jede alte Zeile ist in genau einer Zieldatei auffindbar; Ausnahme nur Dubletten, gelistet in `docs/agents/umzug-dubletten.txt`.
- Sprache der Doku: Deutsch, Stil wie bisher.
- Eine Bash-Anweisung je Aufruf. Kein `cd`, kein `&&`/`;`, kein `$VAR`, keine Schleifen, keine Pfade außerhalb des Worktrees.
- Eigene Skripte immer `uv run --extra dev python -m scripts.<modul>`.
- Gezielte Tests: `uv run --extra dev python -m pytest -q -p no:cacheprovider <dateien>`. Die volle Suite läuft NUR im Abschluss (Task 5), nicht in den Tasks.
- Nie Live-Dienste (`interview-theater@*`, `*-web`) anfassen, nicht `main`, nicht pushen, nicht mergen. Commit nach jedem Task auf `wt/fabrik-a`.
- Commit-Nachrichten enden mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

### Task 1: Prüfskript Verlustfreiheit

**Files:**
- Create: `scripts/pruefe_agents_umzug.py`
- Test: `tests/test_pruefe_agents_umzug.py`

**Interfaces:**
- Produces: `uv run --extra dev python -m scripts.pruefe_agents_umzug [--basis SHA] [--wurzel PFAD] [--alt-datei PFAD] [--ohne-agents-md]`, Exit 0 = grün, 1 = rot, letzte Ausgabezeile `GRUEN` bzw. `ROT`. Funktionen `absaetze(text) -> list[tuple[int, str]]`, `normalisiere(text) -> str`, `doppelte_kapitel_zeilen(text) -> set[int]`, `pruefe(alt, neu, ausnahmen) -> Bericht`, `lies_ausnahmen(pfad) -> set[int]`.
- Ausnahmendatei `docs/agents/umzug-dubletten.txt`: je Zeile eine alte Zeilennummer (Absatzanfang), `#` leitet Kommentar ein, leere Zeilen erlaubt.

- [ ] **Step 1: Failing tests schreiben** — `tests/test_pruefe_agents_umzug.py`:

```python
"""Das Pruefskript des AGENTS.md-Umzugs (Spec 2026-10-05, Abnahme 2)."""

import subprocess
import sys
from pathlib import Path

from scripts import pruefe_agents_umzug as p

ALT = """# Titel

Erster Absatz,
zweite Zeile.

## Doppelt

Alte Fassung eines Satzes.

## Einmalig

Ein Absatz, der nur hier steht.

## Doppelt

Neue Fassung eines Satzes.
"""


def test_absaetze_tragen_ihre_startzeile():
    assert p.absaetze(ALT)[:2] == [(1, "# Titel"), (3, "Erster Absatz,\nzweite Zeile.")]


def test_normalisiere_glaettet_leerraum_und_ueberschriftsebene():
    assert p.normalisiere("### Kopf\n  a   b\n") == p.normalisiere("# Kopf a b")


def test_doppelte_kapitel_werden_erkannt():
    zeilen = p.doppelte_kapitel_zeilen(ALT)
    assert 8 in zeilen and 16 in zeilen
    assert 12 not in zeilen and 3 not in zeilen


def test_alles_umgezogen_ist_gruen():
    b = p.pruefe(ALT, ALT, set())
    assert b.gruen and not b.fehlend


def test_fehlender_absatz_ist_rot():
    neu = ALT.replace("Ein Absatz, der nur hier steht.", "")
    b = p.pruefe(ALT, neu, set())
    assert not b.gruen
    assert b.fehlend == [(12, "Ein Absatz, der nur hier steht.")]


def test_dublette_mit_ausnahme_ist_gruen_und_wird_gelistet():
    neu = ALT.replace("Alte Fassung eines Satzes.", "")
    b = p.pruefe(ALT, neu, {8})
    assert b.gruen
    assert b.dubletten == [(8, "Alte Fassung eines Satzes.")]


def test_ausnahme_ausserhalb_doppelter_kapitel_ist_ungueltig():
    neu = ALT.replace("Ein Absatz, der nur hier steht.", "")
    b = p.pruefe(ALT, neu, {12})
    assert not b.gruen
    assert 12 in b.ungueltige_ausnahmen


def test_lies_ausnahmen_ignoriert_kommentare(tmp_path):
    d = tmp_path / "a.txt"
    d.write_text("# Kopf\n\n1288  # Fallen, aeltere Fassung\n1300\n", encoding="utf-8")
    assert p.lies_ausnahmen(d) == {1288, 1300}


def test_cli_positivkontrolle(tmp_path):
    """Ein absichtlich entfernter Absatz macht das Skript rot (Exit 1)."""
    alt = tmp_path / "alt.md"
    alt.write_text(ALT, encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Index\n", encoding="utf-8")
    (tmp_path / "docs" / "agents").mkdir(parents=True)
    ziel = tmp_path / "docs" / "agents" / "alles.md"
    ziel.write_text(ALT, encoding="utf-8")
    befehl = [sys.executable, "-m", "scripts.pruefe_agents_umzug",
              "--wurzel", str(tmp_path), "--alt-datei", str(alt)]
    wurzel = Path(__file__).resolve().parent.parent
    gruen = subprocess.run(befehl, cwd=wurzel, capture_output=True, text=True)
    assert gruen.returncode == 0, gruen.stdout
    assert gruen.stdout.strip().splitlines()[-1] == "GRUEN"
    ziel.write_text(ALT.replace("Ein Absatz, der nur hier steht.", ""), encoding="utf-8")
    rot = subprocess.run(befehl, cwd=wurzel, capture_output=True, text=True)
    assert rot.returncode == 1
    assert rot.stdout.strip().splitlines()[-1] == "ROT"
    assert "Z. 12" in rot.stdout
```

- [ ] **Step 2: Tests laufen lassen, rot erwarten**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_pruefe_agents_umzug.py`
Expected: FAIL (`ImportError`/`cannot import name 'pruefe_agents_umzug'`).

- [ ] **Step 3: Skript schreiben** — `scripts/pruefe_agents_umzug.py`:

```python
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

BASIS = "cb200e4"
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
```

- [ ] **Step 4: Tests grün**

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_pruefe_agents_umzug.py`
Expected: 9 passed.

- [ ] **Step 5: Gegen den Ist-Stand laufen lassen (muss trivial GRUEN sein, AGENTS.md ist noch alt)**

Run: `uv run --extra dev python -m scripts.pruefe_agents_umzug`
Expected: letzte Zeile `GRUEN`, `fehlend: 0`.

- [ ] **Step 6: Commit**

```bash
git add scripts/pruefe_agents_umzug.py tests/test_pruefe_agents_umzug.py
git commit -m "AGENTS.md-Umzug: Pruefskript Verlustfreiheit (Spec 2026-10-05, Abnahme 2)"
```

---

### Task 2: Volltext nach docs/agents/ aufteilen und Dubletten auflösen

**Files:**
- Create: `scripts/agents_umzug_aufteilen.py`
- Create (vom Skript erzeugt, dann von Hand bereinigt): `docs/agents/aufbau.md`, `entscheidungen.md`, `dramaturgie-pruefung.md`, `fallen.md`, `spec-abweichungen.md`, `starten-und-testen.md`, `weboberflaeche.md`, `korpus-und-simulation.md`, `was-bewusst-fehlt.md`, `workshop-profil.md`
- Create: `docs/agents/umzug-dubletten.txt`
- AGENTS.md bleibt in diesem Task UNVERÄNDERT.

**Interfaces:**
- Consumes: `scripts.pruefe_agents_umzug` (Task 1), Flag `--ohne-agents-md`.
- Produces: die zehn Zieldateien unter `docs/agents/` (Namen oben, Task 3 verlinkt sie genau so) und `docs/agents/umzug-dubletten.txt`.

Zeilenbereiche der alten Datei (`git show cb200e4:AGENTS.md`, 1-basiert, inklusive; gemessen an den `## `-Überschriften). „behalten" = jüngere, vollständigere Fassung (die zweite); „älter" = erste Fassung, von der nur abweichende Absätze übernommen werden:

| Zieldatei | behalten | älter |
|---|---|---|
| `aufbau.md` | 1–226 (Titel, Intro, Dortmund-Absatz, Aufbau, Modulkarte) | — |
| `entscheidungen.md` | 227–1121 | — |
| `dramaturgie-pruefung.md` | 1122–1269 | — |
| `fallen.md` | 2170–2277 | 1270–1365 |
| `spec-abweichungen.md` | 2278–2324 | 1366–1394 |
| `starten-und-testen.md` | 2325–2437 | 1395–1504 |
| `weboberflaeche.md` | 2438–3324 | 1505–1599 |
| `korpus-und-simulation.md` | 3325–3520 | 1600–1801 |
| `was-bewusst-fehlt.md` | 3521–3707 | 1802–2075 |
| `workshop-profil.md` | 2076–2169 | — |

- [ ] **Step 1: Bereiche verifizieren** (Fakten vom 05.10. 08:40 können sich bewegt haben)

Run: `git show cb200e4:AGENTS.md` ist die Quelle; prüfe mit `grep -n "^## " AGENTS.md` (AGENTS.md ist in diesem Task noch identisch mit cb200e4 — bestätige mit `git diff --stat cb200e4 -- AGENTS.md`, erwartet: leer), dass die Überschriften auf den Zeilen 13, 40, 142, 227, 1122, 1270, 1366, 1395, 1505, 1802, 2076, 2170, 2278, 2325, 2438, 3521 stehen und `### Prompt geändert` auf 1600 und 3325. Weicht etwas ab: Tabelle im Skript anpassen und das im Report nennen.

- [ ] **Step 2: Aufteilskript schreiben** — `scripts/agents_umzug_aufteilen.py`:

```python
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
```

Achtung bei `_zeilen`: der Rest-Absatz aus `absaetze(...)` trägt Zeilennummern relativ zum Ausschnitt; für `umzug-dubletten.txt` braucht es die **alte, absolute** Zeilennummer = relative Nummer + `aelter[0]` − 1. Die Ausgabe des Prüfskripts (Step 4) nennt sie ohnehin absolut.

- [ ] **Step 3: Skript laufen lassen**

Run: `uv run --extra dev python -m scripts.agents_umzug_aufteilen`
Expected: zehn Zeilen `…: geschrieben`, kein `SystemExit`.

Run: `uv run --extra dev python -m scripts.pruefe_agents_umzug --ohne-agents-md`
Expected: `GRUEN`, `fehlend: 0` (alles steht noch wörtlich da, nur die Rest-Abschnitte sind roh).

- [ ] **Step 4: Rest-Abschnitte von Hand auflösen** — in jeder Datei mit Überschrift `## NUR IN DER AELTEREN FASSUNG …`: für jeden Absatz darunter entscheiden:
  - (a) **Eigener Inhalt**, der in der jüngeren Fassung fehlt (z. B. in `was-bewusst-fehlt.md` die Punkte „Phase 6 ist EINE Kurzgeschichte", „Der Prosa-Lauf startet nur aus einem Knopf", „Was fehlt, steht neben dem, was dasteht" usw.; in `weboberflaeche.md` evtl. nichts): Absatz **wörtlich** an die passende Stelle im Haupttext verschieben (Reihenfolge der alten Datei beibehalten, wo möglich).
  - (b) **Ältere Variante** eines Absatzes, den die jüngere Fassung in neuerer Form trägt (z. B. Falle 7 ohne Web-Kanal-Satz, „Wer einen elften Befehl anhängt" vs. „vierzehnten"): Absatz löschen und seine **alte absolute Startzeile** in `docs/agents/umzug-dubletten.txt` eintragen, mit Kommentar, welcher Absatz ihn ersetzt.
  - Ist der Rest-Abschnitt leer, die Überschrift löschen. Am Ende darf keine Datei mehr `NUR IN DER AELTEREN FASSUNG` enthalten.
  - Format `docs/agents/umzug-dubletten.txt`:

```text
# Dubletten des AGENTS.md-Umzugs (Spec 2026-10-05). Je Zeile: alte Startzeile
# (git show cb200e4:AGENTS.md) eines Absatzes aus der aelteren Fassung eines
# doppelten Kapitels, der in der juengeren Fassung in neuerer Form steht.
# Gelesen von scripts/pruefe_agents_umzug.py.
1350  # Falle 7 (aeltere Fassung) -> fallen.md, Falle 7 mit Web-Kanal-Satz
```
  (die Zeile `1350` ist nur ein Formatbeispiel — echte Nummern aus der Prüfskript-Ausgabe nehmen.)

- [ ] **Step 5: Prüfen**

Run: `uv run --extra dev python -m scripts.pruefe_agents_umzug --ohne-agents-md`
Expected: letzte Zeile `GRUEN`; die `DUBLETTE Z. …`-Zeilen sind genau die eingetragenen.

Run: `grep -rn "NUR IN DER AELTEREN FASSUNG" docs/agents`
Expected: keine Ausgabe (Exit 1).

- [ ] **Step 6: Commit** — die Commit-Nachricht nennt je Kapitel die Unterschiede zwischen den Fassungen (Spec: „Unterschiede im Commit-Text nennen"): welche Absätze aus der älteren Fassung eingeordnet wurden (a) und welche als Dubletten entfielen (b), je mit alter Zeilennummer.

```bash
git add scripts/agents_umzug_aufteilen.py docs/agents
git commit -F <nachrichtendatei-im-worktree>
```
(Nachricht in eine Datei im Worktree schreiben, z. B. `.git-msg-task2.txt`, nach dem Commit löschen; nicht committen.)

---

### Task 3: Neue AGENTS.md (≤ 25 kB), Größentest, Doku-Tests umstellen

**Files:**
- Rewrite: `AGENTS.md`
- Create: `tests/test_agents_md_groesse.py`
- Create: `tests/agents_doku.py`
- Modify: `tests/test_doku_laengen.py:14` (Lesestelle), `tests/test_web_betrieb_doku.py:35,41,51,57` (Lesestellen)

**Interfaces:**
- Consumes: die zehn Dateien unter `docs/agents/` aus Task 2 (Namen: `aufbau.md`, `entscheidungen.md`, `dramaturgie-pruefung.md`, `fallen.md`, `spec-abweichungen.md`, `starten-und-testen.md`, `weboberflaeche.md`, `korpus-und-simulation.md`, `was-bewusst-fehlt.md`, `workshop-profil.md`), Prüfskript aus Task 1.
- Produces: `tests.agents_doku.agents_doku() -> str` (AGENTS.md + alle `docs/agents/**/*.md`, AGENTS.md zuerst). Kapitel→Datei-Tabelle in AGENTS.md, auf die Task 4 verweist.

- [ ] **Step 1: Größentest schreiben (rot)** — `tests/test_agents_md_groesse.py`:

```python
"""AGENTS.md bleibt ein Index (Spec 2026-10-05-agents-md-index-design, Abnahme 3).

Claude Code laedt AGENTS.md in den Controller UND in jeden Subagenten. Bei
255 kB startete jeder Subagent mit ~131 k Tokens. Uebergaben und Nachweise
einer Karte gehoeren nach docs/agents/<thema>.md oder docs/handoffs/, nie an
AGENTS.md.
"""

from pathlib import Path

GRENZE = 25_000
AGENTS = Path(__file__).resolve().parent.parent / "AGENTS.md"


def test_die_grenze_ist_die_aus_der_spec():
    assert GRENZE == 25_000, "Grenze nicht anheben -- Inhalt nach docs/agents/ verschieben"


def test_agents_md_bleibt_unter_der_grenze():
    groesse = AGENTS.stat().st_size
    assert groesse <= GRENZE, (
        f"AGENTS.md hat {groesse} Bytes (> {GRENZE}). Uebergaben/Nachweise "
        "gehoeren nach docs/agents/<thema>.md oder docs/handoffs/.")
```

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_agents_md_groesse.py`
Expected: 1 failed (`AGENTS.md hat 258485 Bytes`), 1 passed.

- [ ] **Step 2: Hilfsfunktion für Doku-Tests** — `tests/agents_doku.py`:

```python
"""Die Agenten-Doku als ein Text: AGENTS.md (Index) plus docs/agents/**.

Seit dem Umzug vom 05.10.2026 steht der Volltext unter docs/agents/; Tests,
die pruefen, dass die Doku etwas nennt, lesen beides.
"""

from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent


def agents_doku() -> str:
    teile = [(WURZEL / "AGENTS.md").read_text(encoding="utf-8")]
    for datei in sorted((WURZEL / "docs" / "agents").rglob("*.md")):
        teile.append(datei.read_text(encoding="utf-8"))
    return "\n\n".join(teile)
```

In `tests/test_doku_laengen.py` Zeile 14 ersetzen durch:

```python
from tests.agents_doku import agents_doku

AGENTS = agents_doku()
```
(Import oben zu den anderen Imports; Docstring-Satz „ein Mensch, der AGENTS.md liest" → „ein Mensch, der AGENTS.md und docs/agents/ liest".)

In `tests/test_web_betrieb_doku.py` die vier `agents = _lies("AGENTS.md")` durch `agents = agents_doku()` ersetzen und `from tests.agents_doku import agents_doku` importieren. `_lies` bleibt für die anderen Dateien.

- [ ] **Step 3: AGENTS.md neu schreiben** — Deutsch, Stil der alten Datei, Ziel ~20.000 Bytes, harte Grenze 25.000. Gliederung (Spec „Inhalt der neuen AGENTS.md"):

  1. `# AGENTS.md` + ein Absatz: was das Projekt ist (Telegram-/Web-Bot für partizipative Theater-Workshops, ein Prozess je Gruppe, gemeinsame SQLite im WAL-Modus, Zustand vollständig in der DB), Primärquelle SPEC, „bei Widerspruch gilt der Code".
  2. `## 🔴 Dortmund eingefroren seit 04.10.2026 — Abnahme nur noch an Padua` — verdichtet auf das Handlungsrelevante: nur Padua-Bots live; Abnahme = Suite grün mit `-m "not dortmund"`, `pruefe_profil padua-2026`, Prompt-Snapshot nur Padua; Tag `dortmund-2026-final` (SHA `2e552399749311f3787b375fa4df7d1e30e4097d`); `@pytest.mark.dortmund` statt Anpassen; Fixtures `*dortmund*`/`*vorgabe*` nicht neu erzeugen; neue Funktionen nur Padua, keine neuen Schalter, bestehende bleiben bis Aufräumen ab 10.10.2026; nicht anfassen: `betrieb/gruppe1-4.env`, Dortmund-Daten in `betrieb/soap.db`, Dortmund-Code. Verweis auf `docs/agents/aufbau.md` für den Wortlaut.
  3. `## Modulkarte` — **diese Überschrift muss wörtlich so heißen** (`tests/test_doku_laengen.py` schneidet ab `## Modulkarte`). Die vier Schichten als Tabelle (Ablage/Dienste/Fachlogik/Oberfläche, Modulnamen wie in `docs/agents/aufbau.md`), darunter je Modul **eine** Zeile `` `modul.py` — Zuständigkeit in ≤ 1 Satz `` für alle Module der alten Tabelle (inkl. `laengen.py`, `sprachpass.py`, `nachpass.py`, `web_kanal.py`, `web_chat.py`, `knoepfe/`, `dramaturgie/`), die Regel „lokaler Import in der Funktion löst Zyklen auf", SQL nur in `repo.py`/`db.py` (Ausnahme `web_daten.py`, read-only). Die „Wo man anfängt"-Tabelle auf die 8 wichtigsten Fragen verdichten. Verweis: Volltext `docs/agents/aufbau.md`.
  4. `## Harte Invarianten` — je eine Zeile + Verweis auf die Zieldatei: Datenschutz/E8 (keine Klarnamen, Grenzen der Weboberfläche: kein Nachrichtentext/Transkript aufs Dashboard, kein Volltranskript auf der Gruppenseite, kein Belegzitat ohne `zitat_geprueft = 1`; `IT_WEB_BIND` nie `0.0.0.0`); Sprachschicht `T` (`sprache.py`, `sprachen/<code>/texte.toml`, Deutsch bleibt Python-Konstante); bitgleich-Tests (nur Padua bindend); die drei Knopf-Zusagen (`callback_data` < 64 Bytes `k:<id>`, kein Modellaufruf in Knopf-Handlern und Slash-Befehlen — Threads, Idempotenz über `repo.beanspruche_knopf`); Kostendeckel (`kosten.py`, 5 CHF/Gruppe/Tag, `IT_KOSTEN_DECKEL_CHF`); Journal/Verdichtung/Szenenfassung nur anhängen, weiches Löschen (`entfernt_am`), Material ohne Entfernungspfad; jede Tabelle außer `bot_zustand` hat `chat_id`; Schema nur additiv migrieren; Phase setzt allein die Gruppe; `setze_szene_usa` nimmt bool; Erkenner-Prompt-Änderung nur mit FP = 0 (Korpuslauf kostet Geld, nie automatisch); kein CSS-Kommentar direkt vor einer Regel in `_BUEHNE` (`scope_css`); CSP: kein `style="…"`/`on…=`; **Live-Dienste (`interview-theater@*`, `interview-theater-*-web`) nie starten/stoppen/neu starten aus einem Arbeitsauftrag**. Verweise auf `docs/agents/entscheidungen.md`, `weboberflaeche.md` usw.
  5. `## Starten und testen` — Suite-Kommando wörtlich `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider` (dauert ~10 min), Marker `dortmund` (in `pyproject.toml`), e2e: `tests/e2e/` mit Playwright, ohne Playwright übersprungen; systemd-User-Units statt Handstart (`docs/interview-theater@.service`, `scripts/betrieb-start.sh`), Testinstanz `scripts/test_uebernehmen.py` → `docs/testgruppe-padua.md`; Skripte, die Geld kosten (`rauchtest`, `pruefe_prompts`, `simulation`, `dramaturgie_pruefen`) laufen nie automatisch. Verweis `docs/agents/starten-und-testen.md`, `korpus-und-simulation.md`.
  6. `## Die wichtigsten Fallen` — die acht Fallen aus `docs/agents/fallen.md` je in ≤ 2 Zeilen (URL inkl. `/chat/completions`; Whisper `/1/ai/…` zweistufig, `data` doppelt parsen; MIME aus Endung; `reasoning_effort` immer senden, `"none"` = aus, Ausnahme `szene.py`; Modellwahl gemma/Kimi, nie Nemotron; SQLite + Threads → `repo._LOCK` RLock; nie denselben Bot zweimal starten / zwei Bots in eine Gruppe / zwei Prozesse mit derselben `IT_WEB_CHAT_ID`; Infomaniak drosselt mit 429/5xx → seriell). Plus zwei weitere aus der Praxis: Prompts werden heiß nachgeladen, TOML-Profile nur beim Start; Dortmund-Tests → Marker statt Anpassung. Verweis `docs/agents/fallen.md`.
  7. `## Index: docs/agents/` — Tabelle mit **allen zehn** Dateien, je eine Zeile „lies das, wenn du … anfasst", z. B. `entscheidungen.md` — „wenn du Verhalten änderst, das eine bindende Entscheidung berührt (Knöpfe, Phasen, Interviews, Erkenner, Kürzen, Undo, Länge/Nachpass, Kosten, Prüflauf, Begriffsboard)". Darunter eine Tabelle **„Kapitel der alten AGENTS.md → jetzt"**: jede alte `## `-/`### `-Überschrift (Dortmund, Aufbau, Modulkarte, Bindende Entwurfsentscheidungen, Die Dramaturgie-Prüfung, Die Fallen, Wo SPEC und Code auseinanderlaufen, Starten und testen, Weboberfläche und ihre `###`-Unterkapitel, Prompt geändert? → Korpus laufen lassen, Simulation, Was bewusst fehlt, Workshop-Profil) → Zieldatei. Damit bleiben alte Verweise „AGENTS.md, Abschnitt X" in einem Schritt auflösbar.
  8. `## Regel für Folgearbeit` — wörtlich sinngemäß: „Übergaben, Nachweise und Entscheidungsgeschichte einer Karte gehören nach `docs/agents/<thema>.md` oder `docs/handoffs/` — **nie an AGENTS.md anhängen**. AGENTS.md trägt nur, was ein Agent in jeder Aufgabe braucht; `tests/test_agents_md_groesse.py` wird bei mehr als 25.000 Bytes rot." Plus: die Doku-Tests lesen `tests.agents_doku.agents_doku()`.

  Pflicht-Stichwörter, die die Doku-Tests im **Gesamttext** suchen, stehen bereits in `docs/agents/`; zusätzlich muss AGENTS.md ab `## Modulkarte` die Zeichenketten `` `laengen.py` ``, `` `sprachpass.py` ``, `` `nachpass.py` `` enthalten.

- [ ] **Step 4: Größe und Tests**

Run: `wc -c AGENTS.md`
Expected: Zahl ≤ 25000.

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_agents_md_groesse.py tests/test_doku_laengen.py tests/test_web_betrieb_doku.py tests/test_pruefe_agents_umzug.py`
Expected: alle grün.

Run: `uv run --extra dev python -m scripts.pruefe_agents_umzug`
Expected: letzte Zeile `GRUEN`.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md tests/test_agents_md_groesse.py tests/agents_doku.py tests/test_doku_laengen.py tests/test_web_betrieb_doku.py
git commit -m "AGENTS.md vom Archiv zum Index: <N> Bytes statt 258485, Volltext unter docs/agents/"
```

---

### Task 4: Verweise auf AGENTS.md nachziehen

**Files (nur Kommentare/Docstrings/Doku-Prosa):**
- Modify: Fundstellen von `AGENTS.md` in `interview_theater/**/*.py`, `interview_theater/sprachen/en/texte.toml`, `tests/**/*.py`, `scripts/*.py`, `simulation/*.py`, `simulation/flow_erwartungen.toml`, `README.md`, `pyproject.toml`, `docs/HANDOFF.md`.
- NICHT anfassen (Archiv, historischer Stand): `docs/superpowers/**`, datierte Berichte unter `docs/` (`docs/*-2026-*.md`, `docs/prompt-audit/**`, `docs/padua-r-laengen-2026-09-30/**`, `docs/begriffsboard-*/**`), `simulation/laeufe/**`, `docs/agents/**` (ist der verschobene Wortlaut; Verlustfreiheit!).

**Interfaces:**
- Consumes: die Tabelle „Kapitel der alten AGENTS.md → jetzt" in AGENTS.md (Task 3), Zieldateien aus Task 2.

- [ ] **Step 1: Liste holen**

Run: `grep -rn "AGENTS.md" interview_theater tests scripts simulation README.md pyproject.toml docs/HANDOFF.md --include=*.py --include=*.toml --include=*.md`
(ohne `simulation/laeufe` auswerten.)

- [ ] **Step 2: Je Fundstelle entscheiden**
  - Steht der zitierte Inhalt (Abschnittsname, Zitat, Fallennummer) weiterhin in AGENTS.md (Dortmund-Absatz, Modulkarte, harte Invarianten, Fallen-Kurzfassung, Starten und testen): unverändert lassen.
  - Sonst `AGENTS.md` durch den Pfad der Zieldatei ersetzen, Abschnittsname behalten, z. B. `AGENTS.md, Falle 3` → `docs/agents/fallen.md, Falle 3`; `AGENTS.md 'Der Web-Kanal'` → `docs/agents/weboberflaeche.md 'Der Web-Kanal'`; „Bindende Entwurfsentscheidungen"/„Haltung 06.09.2026" → `docs/agents/entscheidungen.md`.
  - Ohne erkennbaren Abschnitt („siehe AGENTS.md"): per `grep -n` im zitierten Stichwort klären, wo es steht; ist es nicht klar, unverändert lassen (die Kapiteltabelle löst es auf) und in der Ausnahmeliste des Reports nennen.
  - **Nur** Kommentare, Docstrings, Markdown-Prosa. Steht `AGENTS.md` in einem Laufzeit-String (z. B. in `texte.toml` als Wert, in einer Nutzer-Meldung, in einem Prompt): nicht ändern, im Report nennen.
  - `tests/test_web_betrieb_doku.py`/`test_doku_laengen.py` sind seit Task 3 auf `agents_doku()` umgestellt; nur ihre Docstrings ggf. anpassen.

- [ ] **Step 3: Gezielte Tests** — die geänderten Testdateien plus die Doku-/Bitgleich-Wächter:

Run: `uv run --extra dev python -m pytest -q -p no:cacheprovider tests/test_agents_md_groesse.py tests/test_doku_laengen.py tests/test_web_betrieb_doku.py tests/test_pruefe_agents_umzug.py tests/test_sprache_bitgleich.py tests/test_sprache_texte.py tests/test_knoepfe_struktur.py`
Expected: alle grün. Zusätzlich jede geänderte `tests/*.py`-Datei einzeln mitlaufen lassen (nur Dateien, die im Diff stehen: `git diff --name-only`).

Run: `uv run --extra dev python -m scripts.pruefe_agents_umzug`
Expected: `GRUEN`.

- [ ] **Step 4: Commit** — Nachricht nennt Anzahl geänderter Verweise und die bewusst belassenen.

```bash
git add -u interview_theater tests scripts simulation README.md pyproject.toml docs/HANDOFF.md
git commit -m "Verweise auf AGENTS.md zeigen auf docs/agents/ (Spec 2026-10-05, Abnahme 4)"
```

---

### Task 5: Abnahme (Controller, keine Subagent-Implementierung)

- [ ] `wc -c AGENTS.md` → ≤ 25000 (Abnahme 1).
- [ ] `uv run --extra dev python -m scripts.pruefe_agents_umzug` → `GRUEN` (Abnahme 2); Dublettenliste aus der Ausgabe in den Bericht.
- [ ] Positivkontrolle: einen Absatz aus `docs/agents/fallen.md` mit dem Edit-Werkzeug entfernen → Prüfskript `ROT` mit `FEHLT Z. …`; danach `git checkout -- docs/agents/fallen.md`.
- [ ] Mutanten Größentest: (a) `GRENZE = 50_000` → `test_die_grenze_ist_die_aus_der_spec` rot; (b) 30 kB an AGENTS.md anhängen → `test_agents_md_bleibt_unter_der_grenze` rot; je danach `git checkout --` (Abnahme 3).
- [ ] `grep -rn "AGENTS.md" …` (Liste aus Task 4) und `grep -rln "docs/agents/" …` in den Bericht (Abnahme 4).
- [ ] Volle Suite einmal, Vordergrund, Timeout 900000: `uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider` (Abnahme 5). Baseline vor dem Umbau: `1 failed, 7764 passed, 9 skipped, 4 deselected` — der eine rote Test (`tests/test_knoepfe_navigation.py::test_interviews_fertig_springt_direkt_wenn_alles_verdichtet`) war schon vor jeder Änderung rot.
- [ ] Messung: erster Assistant-Eintrag eines nach Task 3 gestarteten Subagenten in `~/.claude/projects/<projekt>/<session>/subagents/*.jsonl` — `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`; Vergleich mit einem vor Task 3 gestarteten (Abnahme 6, Ziel < 40 k).
- [ ] Abschließendes Review des ganzen Branches (ein Reviewer-Subagent).
