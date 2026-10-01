"""Eine Web-Gruppe anlegen (30.09.2026, Karte Padua A2).

Eine Gruppe im Web-Kanal hat keine echte Telegram-``chat_id`` -- es gibt
keinen Chat, es gibt einen Link. Ihre chat_id ist deshalb synthetisch
(``repo.WEB_CHAT_ID_BASIS``), und **anlegen muss sie jemand von Hand**: der
Webserver kann es nicht, er oeffnet die Datenbank read-only, und der Bot
legt eine Gruppe nur beim ersten Update an -- das aber kommt erst, wenn
jemand den Link hat.

Kein Modellaufruf, kein Netz, kein Telegram. Und **keine Zeile liest eine
Env-Datei einer Gruppe**: dort stehen echte Zugangsdaten, und ein Skript, das
sie einmal liest, gibt sie irgendwann aus. Ausgegeben wird nur, was neu ist:
die chat_id, der Link und die zwei Zeilen fuer die Env-Datei.

Aufruf::

    IT_DB=<pfad-zur-datenbank> IT_WEB_URL=https://lab.artesmobiles.art/theatersoap \\
      python -m scripts.web_gruppe anlegen gruppe4 --titel "Gruppe D"

Danach die zwei ausgegebenen Zeilen in die Env-Datei dieser Gruppe
uebernehmen und ``systemctl --user restart interview-theater@gruppe4``.
"""

import argparse
import os
import sys

from interview_theater import db, repo

#: Wo die Chatansicht liegt (``web_chat.CHAT_PFAD``). Als Literal, damit das
#: Skript den Webserver nicht importieren muss -- ein Test haelt beide
#: zusammen (tests/test_web_chat.py).
CHAT_PFAD = "chat"


def lege_an(conn, bot_name: str, titel: str, basis_url: str) -> dict:
    """Legt die Gruppe an und liefert alles, was jemand danach braucht.

    ``repo.sichere_gruppe`` erzeugt das Web-Token gleich mit
    (``stelle_web_token_sicher``) -- derselbe Weg wie beim ersten Kontakt
    eines Telegram-Bots, keine zweite Token-Quelle."""
    chat_id = repo.naechste_web_chat_id(conn)
    repo.sichere_gruppe(conn, chat_id, bot_name, titel)
    repo.setze_gruppe_kanal(conn, chat_id, "web")
    token = repo.stelle_web_token_sicher(conn, chat_id)
    basis = (basis_url or "").rstrip("/")
    return {
        "chat_id": chat_id,
        "token": token,
        "url": f"{basis}/g/{token}/{CHAT_PFAD}" if basis and token else None,
        "env": ["IT_KANAL=web", f"IT_WEB_CHAT_ID={chat_id}"],
        "bot_name": bot_name,
        "titel": titel,
    }


def bericht(daten: dict) -> str:
    """Was auf die Konsole geht -- in der Reihenfolge, in der man es braucht:
    erst der Link (den bekommt die Gruppe), dann die Env-Zeilen (die braucht
    der Betrieb), dann der Neustart."""
    zeilen = [
        f"Web-Gruppe angelegt: {daten['titel'] or '(ohne Titel)'} "
        f"(chat_id {daten['chat_id']}, Bot {daten['bot_name']})",
        "",
        "Der Link fuer die Gruppe:",
        f"  {daten['url'] or '(IT_WEB_URL ist nicht gesetzt -- kein Link)'}",
        "",
        f"Diese zwei Zeilen in die Env-Datei von {daten['bot_name']} uebernehmen:",
    ]
    zeilen += [f"  {zeile}" for zeile in daten["env"]]
    zeilen += [
        "",
        f"Danach: systemctl --user restart interview-theater@{daten['bot_name']}",
        "",
        "Der Link IST das Geheimnis (kein Login) -- er geht nur an diese Gruppe.",
        "Ein QR-Code ist nicht Teil dieses Skripts (keine Abhaengigkeit dafuer).",
    ]
    return "\n".join(zeilen)


def main(argv: list | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        prog="python -m scripts.web_gruppe",
        description="Legt eine Gruppe im Web-Kanal an (IT_KANAL=web).",
    )
    zerleger.add_argument("befehl", choices=["anlegen"])
    zerleger.add_argument("bot_name", help="Name des Bots, wie in seiner Env-Datei")
    zerleger.add_argument("--titel", default="", help="Anzeigename der Gruppe")
    argumente = zerleger.parse_args(argv)

    db_pfad = os.environ.get("IT_DB")
    if not db_pfad:
        print("Fehlende Umgebungsvariable: IT_DB", file=sys.stderr)
        return 1

    conn = db.verbinde(db_pfad)
    try:
        db.initialisiere(conn)
        daten = lege_an(
            conn, argumente.bot_name, argumente.titel,
            os.environ.get("IT_WEB_URL", ""),
        )
    finally:
        conn.close()
    print(bericht(daten))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
