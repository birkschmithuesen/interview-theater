"""Betreiberskript: ordnet bestehende Verdichtungen den Kernbegriffen zu.

Ab dem 06.09.2026 faellt die Zuordnung beim Verdichten ab
(``verdichter.ordne_begriffe_zu``). Verdichtungen, die vorher entstanden sind,
haben noch keine Tags -- und wenn eine Gruppe ihre Begriffsliste aendert,
stimmen die alten Tags nicht mehr. Beides holt dieses Skript nach.

Es ist **deterministisch und ohne Modellaufruf** (siehe
``interview_theater/begriffe.py``): es liest Zusammenfassung und Kernthemen
jeder Verdichtung und gleicht sie gegen ``arbeitsstand.begriffe`` ab. Der Lauf
ist **idempotent** -- ``repo.setze_verdichtung_begriffe`` ersetzt die Zeilen
einer Verdichtung, statt sie zu ergaenzen; zweimal laufen aendert nichts.

Er ruehrt **nur** die Tabelle ``verdichtung_begriff`` an: keine Verdichtung,
kein Transkript, kein Arbeitsstand wird geschrieben (AGENTS.md: Verdichtungen
werden nie nachtraeglich geaendert).

Ausgabe **ohne Inhalte**: je Gruppe nur Zahlen. Die Verdichtungen enthalten
echte Lebensgeschichten; ein Betreiberskript, das sie ins Terminal oder in ein
Log schreibt, ist ein Datenleck mit Zeilennummer.

Aufruf:  python scripts/begriffe_zuordnen.py [--trocken] [--chat-id N]
Umgebung: IT_DB (Pflicht)
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import begriffe as begriffsabgleich
from interview_theater import db, repo


def zuordnen(conn, chat_id: int, trocken: bool = False) -> tuple[int, int]:
    """Ordnet alle Verdichtungen einer Gruppe zu.

    Liefert ``(verdichtungen, gesetzte_tags)``. Bei ``trocken`` wird nichts
    geschrieben -- nur gezaehlt."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    liste = begriffsabgleich.zerlege(stand["begriffe"] if stand else None)
    if not liste:
        return 0, 0
    anzahl = tags = 0
    for verdichtung in repo.verdichtungen(conn, chat_id):
        themen = repo.themen_zu(conn, verdichtung["id"])
        treffer = begriffsabgleich.ordne_zu(
            liste,
            begriffsabgleich.texte_der_verdichtung(
                verdichtung["zusammenfassung"], themen
            ),
        )
        anzahl += 1
        tags += len(treffer)
        if not trocken:
            repo.setze_verdichtung_begriffe(
                conn, chat_id, verdichtung["id"], treffer,
                aufnahme_id=verdichtung["aufnahme_id"],
            )
    return anzahl, tags


def main(argv: list[str] | None = None) -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--chat-id", type=int, default=None,
                          help="nur diese Gruppe (Vorgabe: alle)")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur zaehlen, nichts schreiben")
    args = zerleger.parse_args(argv)

    db_pfad = os.environ.get("IT_DB")
    if not db_pfad:
        print("Fehlende Umgebungsvariable: IT_DB", file=sys.stderr)
        return 1

    conn = db.verbinde(db_pfad)
    db.initialisiere(conn)
    gruppen = repo.alle_gruppen(conn)
    if args.chat_id is not None:
        gruppen = [g for g in gruppen if g["chat_id"] == args.chat_id]
    if not gruppen:
        print("Keine passende Gruppe in der Datenbank.")
        return 0
    for gruppe in gruppen:
        anzahl, tags = zuordnen(conn, gruppe["chat_id"], args.trocken)
        # Nur Zahlen -- keine Begriffe, keine Titel aus dem Material.
        print(
            f"Gruppe {gruppe['chat_id']} ({gruppe['bot_name']}): "
            f"{anzahl} Verdichtungen, {tags} Zuordnungen"
            + (" (trocken)" if args.trocken else "")
        )
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
