"""Kosten-Auswertung EINES Browserlaufs (Task 2, BRIEF p57): Summe und eine
Tabelle art/modell/modus/anzahl/CHF aus ``aufruf`` in ``<laufordner>/sim.db``.

Ersetzt die bisherigen Hand-Zeilen mit dem ``sqlite3``-CLI (siehe
``simulation/berichte/padua-p34-2026-10-05.md``, Abschnitt "Kosten je
Lauf") -- das CLI steht auf diesem Host gar nicht zur Verfuegung
(AGENTS.md, Risiko-Liste: "Kein ``sqlite3``-CLI auf dem Host ->
Lesezugriffe ueber Python"). ``zeilen()``/``summe()`` sind die reinen,
getesteten Funktionen; ``main()`` ist der duenne CLI-Wrapper fuer
``python -m simulation.lauf_kosten <laufordner>``.

Liest IMMER read-only (``mode=ro``, wie ``browser_lauf._kosten_bisher``):
dieses Werkzeug wertet nur aus, es schreibt nie in eine ``sim.db``, auch
nicht in die eines noch laufenden Prozesses."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from simulation import browser_invarianten as inv


def zeilen(db_pfad: str) -> list[dict]:
    """Eine Zeile je (art, modell, modus): Anzahl Aufrufe und Summe CHF,
    absteigend nach Kosten. Fehlt die ``aufruf``-Tabelle (eine Datenbank, in
    der nie ein Modell gerufen wurde), ist das Ergebnis eine leere Liste
    statt ein Fehler -- wie ``browser_lauf._kosten_bisher``."""
    try:
        conn = inv.oeffne_lesend(db_pfad)
    except sqlite3.OperationalError:
        return []
    try:
        gefunden = conn.execute(
            "SELECT art, COALESCE(modell, '?') AS modell, "
            "COALESCE(modus, '?') AS modus, COUNT(*) AS anzahl, "
            "COALESCE(SUM(kosten_chf), 0) AS chf FROM aufruf "
            "GROUP BY art, modell, modus ORDER BY chf DESC, art ASC"
        ).fetchall()
        return [dict(z) for z in gefunden]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def summe(db_pfad: str) -> float:
    """Σ ``kosten_chf`` ueber ALLE Zeilen dieser ``sim.db`` -- dieselbe Summe
    wie ``browser_lauf._kosten_bisher``, hier als eigene, von
    ``browser_lauf`` unabhaengige Funktion (dieses Modul liest NACH dem
    Lauf, ``browser_lauf`` WAEHREND)."""
    return sum(z["chf"] for z in zeilen(db_pfad))


def baue_tabelle(db_pfad: str) -> str:
    """Markdown-Tabelle art/modell/modus/anzahl/CHF plus Summenzeile --
    bewusst immer mit Kopf und Summenzeile, auch ohne eine einzige
    Aufruf-Zeile (``anzahl``/``chf`` dann 0), damit ein Bericht nie auf
    einen fehlenden Abschnitt stoesst."""
    daten = zeilen(db_pfad)
    kopf = "| art | modell | modus | anzahl | CHF |\n|---|---|---|---|---|\n"
    rumpf = "".join(
        f"| {z['art']} | {z['modell']} | {z['modus']} | {z['anzahl']} | {z['chf']:.4f} |\n"
        for z in daten
    )
    fuss = (
        f"| **Summe** | | | **{sum(z['anzahl'] for z in daten)}** | "
        f"**{summe(db_pfad):.4f}** |\n"
    )
    return kopf + rumpf + fuss


def main() -> None:
    if len(sys.argv) != 2:
        print("Aufruf: python -m simulation.lauf_kosten <laufordner>", file=sys.stderr)
        raise SystemExit(1)
    db_pfad = str(Path(sys.argv[1]) / "sim.db")
    print(baue_tabelle(db_pfad))


if __name__ == "__main__":
    main()
