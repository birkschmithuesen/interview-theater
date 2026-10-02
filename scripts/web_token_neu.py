"""Betreiberskript: gibt einer Gruppe ein neues Web-Token. Der alte Link ist
danach sofort tot.

**Wozu.** Der Gruppenlink hat kein Login -- das Token IST das Geheimnis. Es
wandert in der Probe von Hand zu Hand (siehe die Probenansicht in AGENTS.md),
landet in einem Screenshot, auf einem Foto von der Leinwand, in einem
weitergeleiteten Chat. Bis zum 30.09.2026 gab es dagegen nichts.

**Kein Chat-Befehl.** Rotieren heisst, dass jedes Telefon im Raum seinen Link
verliert; das ist eine Betreiberhandlung mit Ansage, keine, die aus einer
Nachricht folgt -- wie ``scripts/loeschen.py``.

**Kein Neustart noetig.** Der Webserver haelt kein Token im Speicher: jede
Anfrage oeffnet ihre eigene read-only Verbindung
(``web.py`` ``Handler._gruppe``, ``web_daten.chat_id_nach_token``). Die
naechste Anfrage mit dem alten Link bekommt 404.

Aufruf::

    IT_DB=betrieb/soap.db python -m scripts.web_token_neu <chat_id>          # Trockenlauf
    IT_DB=betrieb/soap.db python -m scripts.web_token_neu <chat_id> --ja     # wirklich

Umgebung: ``IT_DB`` (Pflicht), ``IT_WEB_URL`` (Vorgabe wie
``scripts/web_links.py``).
"""

import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, repo

#: Derselbe Vorgabewert wie in scripts/web_links.py -- eine zweite Zahl waere
#: eine zweite Wahrheit.
VORGABE_URL = "https://lab.artesmobiles.art/theatersoap"

#: Der Journaltext. **Ohne Token**, weder altes noch neues: das Journal geht
#: in den Gespraechs-Prompt (kontext._baue_journal) und steht auf der
#: Gruppenseite. Ein Geheimnis gehoert in keines von beidem.
TEXT_JOURNAL = "Zugangslink der Gruppenseite erneuert (Betreiber)."


def _backup(db_pfad: str) -> str | None:
    """Kopie der Datenbank neben das Original, wie
    ``scripts/interviews_uebernehmen.py``. Eine Rotation ist nicht
    umkehrbar: ohne Backup ist der alte Link weg, auch wenn er noch
    gebraucht wuerde."""
    quelle = Path(db_pfad)
    if not quelle.is_file():
        return None
    ziel = quelle.with_name(f"{quelle.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(quelle, ziel)
    return str(ziel)


def main(argumente: list[str] | None = None) -> None:
    argumente = sys.argv[1:] if argumente is None else argumente
    wirklich = "--ja" in argumente
    stellen = [a for a in argumente if not a.startswith("-")]
    if len(stellen) != 1 or not stellen[0].lstrip("-").isdigit():
        print("Aufruf: python -m scripts.web_token_neu <chat_id> [--ja]", file=sys.stderr)
        sys.exit(2)
    chat_id = int(stellen[0])

    db_pfad = os.environ.get("IT_DB")
    if not db_pfad:
        print("Fehlende Umgebungsvariable: IT_DB", file=sys.stderr)
        sys.exit(1)
    basis = os.environ.get("IT_WEB_URL", VORGABE_URL).rstrip("/")

    conn = db.verbinde(db_pfad)
    db.initialisiere(conn)
    try:
        gruppe = repo.hole_gruppe(conn, chat_id)
        if gruppe is None:
            print(f"Keine Gruppe mit chat_id {chat_id}.", file=sys.stderr)
            sys.exit(1)
        titel = gruppe["titel"] or f"Gruppe {chat_id}"

        if not wirklich:
            # Das ALTE Token wird nicht ausgegeben -- es ist noch gueltig.
            print(f"Trockenlauf. Mit --ja bekaeme '{titel}' ({gruppe['bot_name']}) "
                  f"einen neuen Zugangslink; der bisherige waere sofort tot.")
            print("Kein Backup, keine Aenderung.")
            return

        sicherung = _backup(db_pfad)
        if sicherung:
            print(f"Backup: {sicherung}")
        neu = repo.erneuere_web_token(conn, chat_id)
        repo.schreibe_journal(conn, chat_id, "entschieden", TEXT_JOURNAL, quelle="skript")
        print(f"{titel}  ({gruppe['bot_name']})")
        print(f"  {basis}/g/{neu}")
        print("Der bisherige Link ist ab sofort 404. Kein Neustart noetig.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
