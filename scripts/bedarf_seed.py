"""Die Bedarfsliste je Gruppe aus einer JSON-Datei einspielen (Birk
08.10.2026 ~13:45, Padua: Raum/Requisiten/Technik/Kostuem/zu organisieren).

**Idempotent:** ein erneuter Lauf ersetzt nur die noch UNERLEDIGTEN Punkte
einer Gruppe -- erledigte (abgehakte) bleiben unberuehrt (``repo.
ersetze_unerledigte_bedarf_punkte``). Ohne ``--ja`` nur ein Bericht, was ein
Lauf AENDERN wuerde, keine Schreibwirkung.

JSON-Form (Schluessel = chat_id als Text)::

    {
      "7000000000001": {
        "sektionen": [
          {"name": "Props", "punkte": ["Big wooden table", "Six chairs"]},
          {"name": "Tech", "punkte": ["Wireless mic"]}
        ]
      }
    }

Aufruf::

    uv run --extra dev python -m scripts.bedarf_seed --db betrieb/padua.db \\
      --json /pfad/zu/bedarf-seed.json --ja
"""

import argparse
import json
import sys
from pathlib import Path

from interview_theater import db, repo


def _sektionen_aus_json(gruppe: dict) -> list[tuple[str, list[str]]]:
    return [
        (sektion["name"], list(sektion.get("punkte") or []))
        for sektion in gruppe.get("sektionen") or []
    ]


def main(argv: list | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        prog="python -m scripts.bedarf_seed",
        description="Spielt die Bedarfsliste je Gruppe aus einer JSON-Datei ein.",
    )
    zerleger.add_argument("--db", required=True, help="Pfad zur Datenbank")
    zerleger.add_argument("--json", required=True, help="Pfad zur Seed-Datei")
    zerleger.add_argument(
        "--ja", action="store_true",
        help="Tatsaechlich schreiben (sonst nur ein Bericht, keine Wirkung)",
    )
    argumente = zerleger.parse_args(argv)

    try:
        seed = json.loads(Path(argumente.json).read_text(encoding="utf-8"))
    except (OSError, ValueError) as fehler:
        print(f"Seed-Datei nicht lesbar: {fehler}", file=sys.stderr)
        return 1

    conn = db.verbinde(argumente.db)
    try:
        db.initialisiere(conn)
        for chat_id_text, gruppe in seed.items():
            chat_id = int(chat_id_text)
            sektionen = _sektionen_aus_json(gruppe)
            neu = sum(len(punkte) for _, punkte in sektionen)
            vorher = repo.bedarf(conn, chat_id)
            erledigt_erhalten = sum(1 for p in vorher if p["erledigt_am"])
            ersetzt = len(vorher) - erledigt_erhalten
            if argumente.ja:
                angelegt = repo.ersetze_unerledigte_bedarf_punkte(conn, chat_id, sektionen)
                print(
                    f"chat_id {chat_id}: {ersetzt} unerledigte(r) Punkt(e) ersetzt, "
                    f"{erledigt_erhalten} erledigte(r) erhalten, {angelegt} neu angelegt."
                )
            else:
                print(
                    f"chat_id {chat_id}: wuerde {ersetzt} unerledigte(n) Punkt(e) ersetzen, "
                    f"{erledigt_erhalten} erledigte(n) erhalten, {neu} neu anlegen. "
                    "(--ja zum Ausfuehren)"
                )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
