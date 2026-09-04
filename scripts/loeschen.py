"""Betreiberskript: loescht eine Gruppe vollstaendig (Datenbank und Audiodateien).

Erfuellt die Loeschzusage gegenueber den Teilnehmerinnen (siehe
NACHTRAG-weboberflaeche-und-sprache.md, Abschnitt N3: Material ist nicht per
Fliesstext loeschbar, sondern nur ueber dieses Skript).

Aufruf: python scripts/loeschen.py <chat_id>
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, einstellungen


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Aufruf: {sys.argv[0]} <chat_id>")
        sys.exit(1)

    try:
        chat_id = int(sys.argv[1])
    except ValueError:
        print(f"chat_id muss eine Zahl sein, erhalten: {sys.argv[1]!r}")
        sys.exit(1)

    einst = einstellungen.laden()

    antwort = input(
        f"Gruppe {chat_id} inklusive aller Aufnahmen unwiderruflich loeschen? [ja/NEIN] "
    )
    if antwort.strip().lower() != "ja":
        print("Abgebrochen.")
        return

    conn = db.verbinde(einst.db_pfad)
    db.initialisiere(conn)
    db.loesche_gruppe(conn, chat_id)
    conn.close()

    audio_verz = Path(einst.audio_verz) / str(chat_id)
    if audio_verz.exists():
        shutil.rmtree(audio_verz)
        print(f"Audioverzeichnis geloescht: {audio_verz}")
    else:
        print(f"Kein Audioverzeichnis vorhanden: {audio_verz}")

    print(f"Gruppe {chat_id} geloescht.")


if __name__ == "__main__":
    main()
