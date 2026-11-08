"""Die Bedarfsliste je Gruppe aus einer JSON-Datei einspielen (Birk
08.10.2026 ~13:45, Padua: Raum/Requisiten/Technik/Kostuem/zu organisieren).

**Idempotent:** ein erneuter Lauf ersetzt nur die noch UNERLEDIGTEN Punkte
einer Gruppe -- erledigte (abgehakte) bleiben unberuehrt (``repo.
ersetze_unerledigte_bedarf_punkte``). Ohne ``--ja`` nur ein Bericht, was ein
Lauf AENDERN wuerde, keine Schreibwirkung.

JSON-Form (Schluessel = chat_id als Text). Ein Punkt ist ein blosser Text
oder ein Objekt mit einem Download (Nachtrag 1, 08.10.2026 ~13:50)::

    {
      "7000000000001": {
        "sektionen": [
          {"name": "Props", "punkte": [
            "Big wooden table",
            {"text": "Floor plan", "datei": "floor-plan.pdf"}
          ]}
        ]
      }
    }

Ein ``datei``-Verweis braucht ``--dateien <verzeichnis>`` -- von dort wird
die Datei nach ``betrieb/bedarf/<chat_id>/<datei>`` kopiert (nicht in git,
siehe ``web.BEDARF_DATEIEN_VERZ``). Fehlt ``--dateien`` oder die Quelldatei,
bricht der Lauf VOR jeder Schreibwirkung ab -- keine Gruppe bekommt nur die
Haelfte eines Seed-Laufs.

Aufruf::

    uv run --extra dev python -m scripts.bedarf_seed --db betrieb/padua.db \\
      --json /pfad/zu/bedarf-seed.json --dateien /pfad/zu/dateien --ja
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from interview_theater import db, repo
from interview_theater.web import BEDARF_DATEIEN_VERZ


def _punkt_aus_json(punkt):
    """Ein JSON-Punkt (Text oder ``{"text":..., "datei":...}``) als das, was
    ``repo.ersetze_unerledigte_bedarf_punkte`` erwartet: ein blosser Text
    oder ``(text, datei)``."""
    if isinstance(punkt, dict):
        return (punkt["text"], punkt.get("datei"))
    return punkt


def _sektionen_aus_json(gruppe: dict) -> list[tuple[str, list]]:
    return [
        (sektion["name"], [_punkt_aus_json(p) for p in sektion.get("punkte") or []])
        for sektion in gruppe.get("sektionen") or []
    ]


def _dateiverweise(sektionen: list[tuple[str, list]]) -> list[str]:
    """Alle in ``sektionen`` referenzierten Dateinamen, in der Reihenfolge
    ihres ersten Auftretens -- Grundlage der Vorab-Pruefung (Nachtrag 1)."""
    gesehen: list[str] = []
    for _sektion, punkte in sektionen:
        for punkt in punkte:
            if isinstance(punkt, tuple) and punkt[1]:
                if punkt[1] not in gesehen:
                    gesehen.append(punkt[1])
    return gesehen


def main(argv: list | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        prog="python -m scripts.bedarf_seed",
        description="Spielt die Bedarfsliste je Gruppe aus einer JSON-Datei ein.",
    )
    zerleger.add_argument("--db", required=True, help="Pfad zur Datenbank")
    zerleger.add_argument("--json", required=True, help="Pfad zur Seed-Datei")
    zerleger.add_argument(
        "--dateien", default=None,
        help="Quellverzeichnis der Downloads (noetig, wenn ein Punkt 'datei' trägt)",
    )
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

    sektionen_je_gruppe = {
        int(chat_id_text): _sektionen_aus_json(gruppe)
        for chat_id_text, gruppe in seed.items()
    }

    # Vorab-Pruefung ueber ALLE Gruppen, VOR jeder Schreibwirkung (Nachtrag
    # 1): eine fehlende Quelldatei einer Gruppe darf nicht dazu fuehren, dass
    # eine andere Gruppe schon halb geschrieben ist.
    alle_dateiverweise = [
        (chat_id, datei)
        for chat_id, sektionen in sektionen_je_gruppe.items()
        for datei in _dateiverweise(sektionen)
    ]
    if alle_dateiverweise and not argumente.dateien:
        print(
            "Die Seed-Datei nennt 'datei'-Verweise, aber --dateien fehlt.",
            file=sys.stderr,
        )
        return 1
    fehlende = []
    if argumente.dateien:
        quellverz = Path(argumente.dateien)
        for _chat_id, datei in alle_dateiverweise:
            if not (quellverz / datei).is_file():
                fehlende.append(datei)
    if fehlende:
        print(
            f"Quelldatei(en) nicht gefunden in {argumente.dateien}: "
            f"{', '.join(fehlende)}",
            file=sys.stderr,
        )
        return 1

    conn = db.verbinde(argumente.db)
    try:
        db.initialisiere(conn)
        for chat_id, sektionen in sektionen_je_gruppe.items():
            neu = sum(len(punkte) for _, punkte in sektionen)
            vorher = repo.bedarf(conn, chat_id)
            erledigt_erhalten = sum(1 for p in vorher if p["erledigt_am"])
            ersetzt = len(vorher) - erledigt_erhalten
            if argumente.ja:
                if argumente.dateien:
                    quellverz = Path(argumente.dateien)
                    for datei in _dateiverweise(sektionen):
                        ziel = Path(BEDARF_DATEIEN_VERZ) / str(chat_id) / datei
                        ziel.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(quellverz / datei, ziel)
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
