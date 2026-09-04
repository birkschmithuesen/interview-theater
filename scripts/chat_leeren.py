"""Betreiberskript: setzt eine Gruppe auf null -- Telegram-Chat UND Datenbank.

Fuer den Start eines Workshops nach einem Probelauf: die Frauen sollen einen
leeren Chat vorfinden. Zwei Schritte, in dieser Reihenfolge:

1. Alle Nachrichten, die der Bot kennt (Tabelle ``nachricht``), per
   ``deleteMessages`` aus dem Telegram-Chat loeschen. Braucht Admin-Rechte
   des Bots. Was der Bot nie gesehen hat (vor seinem Eintritt), bleibt;
   Telegram-Servicezeilen ("X hat den Bot hinzugefuegt") ebenfalls.
2. ``db.loesche_gruppe`` + Audioverzeichnis -- exakt wie ``loeschen.py``.

Aufruf (Env der Gruppe vorher laden, der Bot-Token bestimmt, welche Gruppe):
    set -a; . ./betrieb/gruppe1.env; set +a
    python scripts/chat_leeren.py <chat_id> [--ja]

Ohne ``--ja`` wird interaktiv gefragt.
"""

import shutil
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, einstellungen  # noqa: E402
from interview_theater.telegram import Telegram  # noqa: E402


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(f"Aufruf: {sys.argv[0]} <chat_id> [--ja]")
        sys.exit(1)
    chat_id = int(args[0])
    einst = einstellungen.laden()

    conn = db.verbinde(einst.db_pfad)
    db.initialisiere(conn)
    gruppe = conn.execute("SELECT bot_name, titel FROM gruppe WHERE chat_id = ?", (chat_id,)).fetchone()
    if gruppe is None:
        print(f"Gruppe {chat_id} ist in der Datenbank unbekannt.")
        sys.exit(1)
    if gruppe["bot_name"] != einst.bot_name:
        print(f"Gruppe {chat_id} gehoert {gruppe['bot_name']}, geladen ist {einst.bot_name} -- falsche Env.")
        sys.exit(1)
    ids = [r[0] for r in conn.execute(
        "SELECT message_id FROM nachricht WHERE chat_id = ? ORDER BY message_id", (chat_id,)
    )]
    print(f"{gruppe['titel']!r} ({chat_id}): {len(ids)} bekannte Nachrichten im Chat, Bot {einst.bot_name}")

    if "--ja" not in sys.argv:
        if input("Chat leeren UND Datenbank/Audio der Gruppe loeschen? [ja/NEIN] ").strip().lower() != "ja":
            print("Abgebrochen.")
            return

    with httpx.Client(timeout=30) as klient:
        tg = Telegram(einst.bot_token, klient)
        geloescht = 0
        for i in range(0, len(ids), 100):
            geloescht += tg.loesche_nachrichten(chat_id, ids[i:i + 100])
        print(f"Telegram: {geloescht} Nachrichten zum Loeschen uebergeben.")

    db.loesche_gruppe(conn, chat_id)
    conn.close()
    audio_verz = Path(einst.audio_verz) / str(chat_id)
    if audio_verz.exists():
        shutil.rmtree(audio_verz)
    print(f"Gruppe {chat_id} auf null gesetzt.")


if __name__ == "__main__":
    main()
