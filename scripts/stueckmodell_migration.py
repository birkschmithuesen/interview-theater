"""Stueckmodell-Migration gegen eine KOPIE (Karte t_fd88600b).

    uv run --extra dev python -m scripts.stueckmodell_migration var/stueckmodell/padua-kopie.db var/stueckmodell/padua-migriert.db

Kopiert die Quelle (``VACUUM INTO``, Quelle read-only), migriert NUR die
Kopie (``db.initialisiere`` ruft ``_migriere_stueckmodell``) und
schreibt den Konfliktbericht nach ``<ziel>.konflikte.md`` / ``.json``."""

import collections
import json
import sys


def bericht(conn) -> dict:
    zeilen = conn.execute(
        "SELECT chat_id, art, ziel, vorher, nachher FROM stueck_aenderung "
        "WHERE quelle = 'migration' ORDER BY chat_id, id").fetchall()
    konflikte = [{"chat_id": z[0], "szene": json.loads(z[2]).get("szene"), "art": z[1],
                  "vorher": json.loads(z[3]) if z[3] else None,
                  "nachher": json.loads(z[4]) if z[4] else None} for z in zeilen]
    return {"konflikte": konflikte,
            "zaehler": dict(collections.Counter(k["art"] for k in konflikte))}


def als_markdown(b: dict) -> str:
    zeilen = ["# Stueckmodell-Migration: Konfliktbericht", "",
              "| art | anzahl |", "|---|---|"]
    zeilen += [f"| {a} | {n} |" for a, n in sorted(b["zaehler"].items())]
    zeilen += ["", "| chat_id | szene | art | vorher | nachher |", "|---|---|---|---|---|"]
    zeilen += [f"| {k['chat_id']} | {k['szene']} | {k['art']} | {k['vorher']} | {k['nachher']} |"
               for k in b["konflikte"]]
    return "\n".join(zeilen) + "\n"


def main() -> None:
    from interview_theater import db
    from scripts import stueckmodell_kopie

    quelle, ziel = sys.argv[1], sys.argv[2]
    stueckmodell_kopie.kopiere(quelle, ziel)
    conn = db.verbinde(ziel)
    db.initialisiere(conn)
    b = bericht(conn)
    with open(ziel + ".konflikte.json", "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=1)
    with open(ziel + ".konflikte.md", "w", encoding="utf-8") as f:
        f.write(als_markdown(b))
    print(json.dumps(b["zaehler"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
