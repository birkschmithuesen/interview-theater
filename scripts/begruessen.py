"""Betreiberskript: schickt einer Gruppe die Erstkontakt-Begruessung aktiv.

Im Regelbetrieb entsteht die Begruessung erst, wenn die erste Teilnehmerin
etwas in die Gruppe schreibt (``bot.verarbeite_update`` -> ``erstkontakt``).
Am Workshoptag ist das die falsche Reihenfolge: der Chat soll die Frauen
schon begruesst haben, wenn sie hineinschauen -- mit Link zur Gruppenseite
und den Einstiegsknoepfen.

Dieses Skript nimmt genau denselben Codeweg (``bot.erstkontakt``), damit
Text, Link und Knoepfe identisch zum Betrieb sind. Es legt die Gruppenzeile
mit dem Bot der geladenen Env an und erzeugt das Web-Token, damit der Link
sicher drinsteht.

Idempotent: gibt es zu der Gruppe schon eine Bot-Nachricht, wird nichts
gesendet ("schon begruesst"). Und weil ``erstkontakt`` die gesendete
Nachricht ueber ``repo.merke_nachricht`` mitschreibt, schickt der laufende
Bot sie beim naechsten Update nicht noch einmal.

Aufruf (Env der Gruppe vorher laden, der Bot-Token bestimmt die Gruppe):
    set -a; . ./betrieb/gruppe1.env; set +a
    python -m scripts.begruessen <chat_id>
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import bot, db, einstellungen, repo  # noqa: E402
from interview_theater.telegram import Telegram  # noqa: E402


def begruesse(conn, tg, e, chat_id: int) -> bool:
    """Der eigentliche Vorgang, ohne Netz-/Env-Aufbau -- so testbar.

    Liefert True, wenn gesendet wurde, False bei 'schon begruesst'.
    """
    if repo.hat_bot_nachricht(conn, chat_id):
        return False
    repo.sichere_gruppe(conn, chat_id, e.bot_name, "")
    repo.stelle_web_token_sicher(conn, chat_id)
    bot.erstkontakt(conn, tg, e, chat_id)
    return repo.hat_bot_nachricht(conn, chat_id)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(f"Aufruf: {sys.argv[0]} <chat_id>")
        sys.exit(1)
    chat_id = int(args[0])
    e = einstellungen.laden()

    conn = db.verbinde(e.db_pfad)
    db.initialisiere(conn)

    # Gehoert die Gruppe schon einem anderen Bot, ist die falsche Env geladen
    # -- dann wuerde die Begruessung aus dem falschen Chat kommen (analog
    # scripts/chat_leeren.py).
    zeile = conn.execute("SELECT bot_name FROM gruppe WHERE chat_id = ?", (chat_id,)).fetchone()
    if zeile is not None and zeile["bot_name"] and zeile["bot_name"] != e.bot_name:
        print(f"Gruppe {chat_id} gehoert {zeile['bot_name']}, geladen ist {e.bot_name} -- falsche Env.")
        sys.exit(1)

    with httpx.Client(timeout=30.0) as klient:
        tg = Telegram(e.bot_token, klient)
        gesendet = begruesse(conn, tg, e, chat_id)
    conn.close()
    print(f"Gruppe {chat_id}: begruesst." if gesendet else f"Gruppe {chat_id}: schon begruesst, nichts gesendet.")


if __name__ == "__main__":
    main()
