"""Was faehrt die Simulation wirklich? -- der Abdeckungszensus.

**Kein Test, kostet nichts, braucht kein Netz.** Er erzeugt die Tabelle, die
in ``docs/simulation-gegenpruefung-2026-09-30.md`` steht: welche der heutigen
Phasen (``phasen.PHASEN``) ein Skript ansteuert, woran es dort seinen
Zielzustand prueft, und was von den Inventaren (``erkenner.ARTEN``,
``knoepfe.texte.ART_*``) dabei ueberhaupt vorkommen kann.

**Warum erzeugt und nicht abgeschrieben.** Eine Abdeckungstabelle von Hand
ist nach dem naechsten Phasenumbau falsch, ohne dass es jemand merkt -- genau
der Fehler, den dieser Zensus an der Simulation selbst nachweist
(``simulation/README.md`` behauptete am 30.09.2026 neun Schritte, es waren
zehn; und "Phase 5 = Format & Rahmen", die es seit dem 06.09. nicht mehr
gibt).

Aufruf::

    PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
    $PY -m scripts.simulation_abdeckung
    $PY -m scripts.simulation_abdeckung --db /tmp/gegenpruefung-basis-1.db

Mit ``--db`` kommen zwei Abschnitte dazu, die sich nur an einem gefahrenen
Lauf ablesen lassen: welche Knopfarten angeboten und welche gedrueckt wurden
(``knopf.art`` / ``benutzt_am``) und welche Modellwege ueberhaupt gelaufen
sind (``aufruf.art``). Beides read-only.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, erkenner, phasen  # noqa: E402
from interview_theater.knoepfe import texte  # noqa: E402
from simulation import skript  # noqa: E402

#: Die drei Skriptlisten, die es gibt. Aus ``skript`` geholt, nicht kopiert.
SKRIPTE = {
    "schritte": skript.SCHRITTE,
    "tag2": skript.SCHRITTE_TAG2,
    "birk": skript.SCHRITTE_BIRK,
}

#: Eine Phasennummer im Titel eines Schritts ("Phase 4: Setting ...").
_TITEL_PHASE = re.compile(r"\bPhase\s+(\d+)")


def phase_je_schritt(schritte) -> dict[str, int | None]:
    """Welche Phase ein Schritt bespielt -- **abgeleitet, nicht hinterlegt**.

    Die ``art='phase'``-Schritte sind die Marken: was zwischen zwei von ihnen
    liegt, gehoert zur Phase des vorangegangenen. Vor dem ersten gilt
    ``phasen.ERSTE`` -- ein Workshop beginnt dort, auch wenn niemand es sagt.

    Ein Skript ohne Phasenschritte (``skript.SCHRITTE``) bekommt damit
    ueberall dieselbe Nummer, und genau das ist die Aussage: es steuert die
    Phasen nicht an."""
    laufend = phasen.ERSTE
    ergebnis: dict[str, int | None] = {}
    for schritt in schritte:
        if schritt.art == "phase" and schritt.phase_nummer:
            laufend = schritt.phase_nummer
        ergebnis[schritt.schluessel] = laufend
    return ergebnis


def titelphasen(schritte) -> list[dict]:
    """Je Schritt: welche Phasennummer sein **Titel** nennt und welche ihm das
    Skript zuordnet.

    Ein Unterschied ist ein Befund und kein Schoenheitsfehler: der Titel ist
    das, was im Lauf-Protokoll und im Bericht steht, und wer dort "Phase 5"
    liest, glaubt, Phase 5 sei gemessen worden."""
    zuordnung = phase_je_schritt(schritte)
    zeilen = []
    for schritt in schritte:
        treffer = _TITEL_PHASE.search(schritt.titel or "")
        genannt = int(treffer.group(1)) if treffer else None
        zugeordnet = zuordnung[schritt.schluessel]
        zeilen.append({
            "schluessel": schritt.schluessel,
            "titel": schritt.titel,
            "titel_phase": genannt,
            "zugeordnet": zugeordnet,
            "stimmt": genannt is None or genannt == zugeordnet,
        })
    return zeilen


def phasentabelle(conn, schritte) -> list[dict]:
    """Je Phase eine Zeile: Kurzname, Arbeitsstandfelder, Pflichtfeld, die
    Schritte, die dort spielen, und woran sie ihren Zielzustand pruefen.

    Die Pruefung kommt aus ``schritt.fertig.__name__`` -- der Funktionsname
    ist die einzige Beschreibung, die nicht auseinanderlaufen kann."""
    zuordnung = phase_je_schritt(schritte)
    zeilen = []
    for nummer, kurz, _beschreibung in phasen.PHASEN:
        eigene = [s for s in schritte if zuordnung[s.schluessel] == nummer]
        zeilen.append({
            "nummer": nummer,
            "kurzname": kurz,
            "felder": skript.felder_fuer_phase(conn, nummer),
            "pflichtfeld": skript.pflichtfeld_fuer_phase(conn, nummer),
            "schritte": [s.schluessel for s in eigene],
            "pruefungen": [getattr(s.fertig, "__name__", "?") for s in eigene],
            "gefahren": bool(eigene),
        })
    return zeilen


def inventar() -> dict:
    """Die zwei Listen, gegen die sich Abdeckung ueberhaupt messen laesst."""
    return {
        "erkenner_arten": sorted(erkenner.ARTEN),
        "erkenner_in_aufnahme": sorted(erkenner.ARTEN_IN_AUFNAHME),
        "knopfarten": sorted(
            getattr(texte, name) for name in dir(texte) if name.startswith("ART_")
        ),
    }


#: Behauptungen der Doku, je mit der Pruefung, die sie heute bestaetigen oder
#: widerlegen wuerde. Drei Zustaende: die Zeichenfolge steht da und die
#: Behauptung stimmt; sie steht da und stimmt nicht; sie steht nicht mehr da
#: (bereinigt). Der dritte Zustand ist der Grund fuer diese Liste -- nach
#: Aufgabe 7 dieses Plans soll sie leer laufen, und das soll man sehen.
BEHAUPTUNGEN: tuple[tuple[str, str, object], ...] = (
    ("simulation/README.md", "neun Schritte", lambda: len(skript.SCHRITTE) == 9),
    ("simulation/skript.py", "Neun Schritte", lambda: len(skript.SCHRITTE) == 9),
    ("simulation/skript.py", "die neun Schritte",
     lambda: len(skript.SCHRITTE) == 9),
    ("tests/test_simulation_durchlauf.py", "neun Schritte",
     lambda: len(skript.SCHRITTE) == 9),
    ("simulation/README.md", "Format & Rahmen",
     lambda: phasen.kurzname(5) == "Format & Rahmen"),
    ("simulation/README.md", "acht Phasen", lambda: len(phasen.PHASEN) == 8),
    ("simulation/skript.py", "acht Phasen", lambda: len(phasen.PHASEN) == 8),
    ("simulation/skript.py", '"Phase 5"', lambda: skript.PHASE_MITTE == 5),
    ("simulation/skript.py", "PHASE_SZENENTEXTE",
     lambda: phasen.kurzname(skript.PHASE_SZENENTEXTE).startswith("Szenentexte")),
    ("simulation/kennzahlen.py", "Pflichtfeld der Phase 5",
     lambda: skript.PHASE_MITTE == 5),
)


def praemissenpruefung(wurzel, behauptungen=BEHAUPTUNGEN) -> list[dict]:
    """Jede Behauptung gegen den Code -- und gegen die Datei, in der sie
    steht."""
    ergebnis = []
    for datei, text, pruefung in behauptungen:
        pfad = Path(wurzel) / datei
        zeilen: list[int] = []
        if pfad.exists():
            for nummer, zeile in enumerate(
                pfad.read_text(encoding="utf-8").splitlines(), 1
            ):
                if text in zeile:
                    zeilen.append(nummer)
        stimmt = bool(pruefung())
        if not zeilen:
            status = "bereinigt"
        elif stimmt:
            status = "gefunden_richtig"
        else:
            status = "gefunden_falsch"
        ergebnis.append({"datei": datei, "text": text, "zeilen": zeilen,
                         "stimmt": stimmt, "status": status})
    return ergebnis


def knopfarten_aus_db(conn) -> list[dict]:
    """Je Knopfart: wie oft angeboten, wie oft gedrueckt. Read-only."""
    return [
        {"art": z["art"], "angeboten": z["angeboten"], "gedrueckt": z["gedrueckt"]}
        for z in conn.execute(
            "SELECT art, count(*) AS angeboten, "
            "sum(CASE WHEN benutzt_am IS NOT NULL THEN 1 ELSE 0 END) AS gedrueckt "
            "FROM knopf GROUP BY art ORDER BY art"
        )
    ]


def laeufe_aus_db(conn) -> dict[str, int]:
    """Welche Modellwege ueberhaupt gelaufen sind (``aufruf.art``)."""
    return {
        z["art"]: z["n"]
        for z in conn.execute(
            "SELECT art, count(*) AS n FROM aufruf GROUP BY art ORDER BY art"
        )
    }


def _ja(wert: bool) -> str:
    return "ja" if wert else "**nein**"


def als_markdown(conn, wurzel, db=None) -> str:
    zeilen = ["# Abdeckung der Simulation (erzeugt, nicht abgeschrieben)", ""]
    zeilen += [
        f"- Phasen laut `phasen.PHASEN`: {len(phasen.PHASEN)}",
        f"- Schritte: `SCHRITTE` {len(skript.SCHRITTE)}, "
        f"`SCHRITTE_TAG2` {len(skript.SCHRITTE_TAG2)}, "
        f"`SCHRITTE_BIRK` {len(skript.SCHRITTE_BIRK)}",
        f"- `skript.PHASE_MITTE` = {skript.PHASE_MITTE} "
        f"(`{phasen.kurzname(skript.PHASE_MITTE)}`), "
        f"`skript.phase_szenen()` = {skript.phase_szenen()}",
        "",
        "## Phasen je Skript",
        "",
    ]
    for name, schritte in SKRIPTE.items():
        zeilen += [f"### `{name}` ({len(schritte)} Schritte)", "",
                   "| Phase | Kurzname | gefahren | Schritte | Pruefung | Pflichtfeld |",
                   "|---|---|---|---|---|---|"]
        for z in phasentabelle(conn, schritte):
            zeilen.append(
                f"| {z['nummer']} | {z['kurzname']} | {_ja(z['gefahren'])} | "
                f"{', '.join(z['schritte']) or '-'} | "
                f"{', '.join(f'`{p}`' for p in z['pruefungen']) or '-'} | "
                f"{z['pflichtfeld'] or '-'} |"
            )
        falsch = [z for z in titelphasen(schritte) if not z["stimmt"]]
        zeilen += [""]
        if falsch:
            zeilen.append("Titel, die eine andere Phase nennen als die Zuordnung:")
            zeilen += [
                f"- `{z['schluessel']}`: Titel \"{z['titel']}\" nennt Phase "
                f"{z['titel_phase']}, zugeordnet ist {z['zugeordnet']}"
                for z in falsch
            ]
        else:
            zeilen.append("Kein Titel widerspricht seiner Phasenzuordnung.")
        zeilen.append("")

    zeilen += ["## Praemissenpruefung", "",
               "| Datei | Behauptung | Zeilen | heute | Status |", "|---|---|---|---|---|"]
    for z in praemissenpruefung(wurzel):
        zeilen.append(
            f"| `{z['datei']}` | {z['text']} | "
            f"{', '.join(str(n) for n in z['zeilen']) or '-'} | "
            f"{'stimmt' if z['stimmt'] else 'stimmt nicht'} | {z['status']} |"
        )

    inv = inventar()
    zeilen += ["", "## Inventar", "",
               f"- `erkenner.ARTEN`: {len(inv['erkenner_arten'])} "
               f"({', '.join(inv['erkenner_arten'])})",
               f"- davon aus einer Aufnahme erlaubt: "
               f"{', '.join(inv['erkenner_in_aufnahme'])}",
               f"- `knoepfe.texte.ART_*`: {len(inv['knopfarten'])}", ""]

    if db is not None:
        zeilen += ["## Knopfarten im gefahrenen Lauf", "",
                   "| Knopfart | angeboten | gedrueckt |", "|---|---|---|"]
        for z in knopfarten_aus_db(db):
            zeilen.append(f"| {z['art']} | {z['angeboten']} | {z['gedrueckt']} |")
        zeilen += ["", "## Modellwege im gefahrenen Lauf", "",
                   "| `aufruf.art` | Anzahl |", "|---|---|"]
        for art, n in laeufe_aus_db(db).items():
            zeilen.append(f"| {art} | {n} |")
        zeilen.append("")
    return "\n".join(zeilen) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.simulation_abdeckung",
        description="Die Abdeckungstabelle der Simulation aus dem Code erzeugen. "
                    "Kein Netz, kein Modell, keine Kosten.",
    )
    p.add_argument("--db", help="Lauf-Datenbank, read-only, fuer Knopf- und "
                               "Aufruf-Abdeckung")
    args = p.parse_args(argv)
    wurzel = Path(__file__).resolve().parent.parent
    ordner = tempfile.mkdtemp(prefix="abdeckung-")
    leer = db.verbinde(str(Path(ordner) / "schema.db"))
    db.initialisiere(leer)
    lauf_conn = None
    if args.db:
        import sqlite3
        lauf_conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        lauf_conn.row_factory = sqlite3.Row
    print(als_markdown(leer, wurzel, lauf_conn), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
