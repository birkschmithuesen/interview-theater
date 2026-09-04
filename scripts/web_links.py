"""Betreiberskript: gibt fuer jede Gruppe die URL ihrer Gruppenseite aus.

Die Gruppenseite (NACHTRAG-weboberflaeche-und-sprache.md N1-B) hat kein Login,
der Zugang ist das Zufallstoken in der URL. Am Workshoptag braucht das
Team genau eine Liste: welche Gruppe bekommt welchen Link.

Erzeugt fehlende Token dabei gleich mit (repo.stelle_web_token_sicher) --
sinnvoll fuer Gruppen aus der Zeit vor der Weboberflaeche, die sonst erst bei
der naechsten eingehenden Nachricht eine Adresse bekaemen.

Aufruf: python scripts/web_links.py
Umgebung: IT_DB (Pflicht), IT_WEB_URL (Vorgabe siehe unten)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, repo

#: Der Weg von aussen (docs/HANDOFF.md (e)): nginx auf herkules leitet
#: /theatersoap/ an den Server auf Port 8010 weiter.
VORGABE_URL = "https://lab.artesmobiles.art/theatersoap"


def main() -> None:
    db_pfad = os.environ.get("IT_DB")
    if not db_pfad:
        print("Fehlende Umgebungsvariable: IT_DB", file=sys.stderr)
        sys.exit(1)
    basis = os.environ.get("IT_WEB_URL", VORGABE_URL).rstrip("/")

    conn = db.verbinde(db_pfad)
    db.initialisiere(conn)
    gruppen = repo.alle_gruppen(conn)
    if not gruppen:
        print("Noch keine Gruppe in der Datenbank.")
        return
    for gruppe in gruppen:
        token = repo.stelle_web_token_sicher(conn, gruppe["chat_id"])
        titel = gruppe["titel"] or f"Gruppe {gruppe['chat_id']}"
        print(f"{titel}  ({gruppe['bot_name']})\n  {basis}/g/{token}")
    conn.close()


if __name__ == "__main__":
    main()
