"""Misst den englischen Anteil der Bot-Texte ('aus'/'text') in Phase 7 --
gegen eine KOPIE einer Datenbank, NIE gegen die Live-Datenbank
(``betrieb/*.db``, AGENTS.md):

    cp betrieb/padua-test.db /tmp/messung.db
    uv run python -m scripts.miss_italienisch /tmp/messung.db

P7-Audit-Karte, Klasse 5 (Englisch an italienische Gruppen): das
Nachweis-Mittel fuer die Behauptung, dass die Commits a5ab681/b954c37 (drei
Systemzeilen + ein Gespraechsbot-Zusatz) den englischen Anteil auf 0
gebracht haben -- bzw. die Fundstelle, falls nicht. Stoppwortzaehlung
(``interview_theater.sprachmessung``), kein Modellaufruf.

Gibt nur Zahlen und ``chat_id``/``web_post.id`` eines auffaelligen Posts
aus, nie den Nachrichtentext (Datenschutz, AGENTS.md E8)."""

import sqlite3
import sys

from interview_theater import sprachmessung


def _chats_in_phase7(conn) -> list[tuple[int, str | None]]:
    return [
        (r["chat_id"], r["phase_gesetzt_am"])
        for r in conn.execute(
            "SELECT chat_id, phase_gesetzt_am FROM arbeitsstand WHERE phase = 7"
        )
    ]


def miss(conn) -> tuple[int, list[tuple[int, int]]]:
    """(Gesamtzahl der Posts, Liste der als englisch erkannten
    ``(chat_id, web_post.id)``) -- fuer Tests und das CLI gemeinsam."""
    gesamt = 0
    englisch: list[tuple[int, int]] = []
    for chat_id, seit in _chats_in_phase7(conn):
        if not seit:
            continue
        zeilen = conn.execute(
            "SELECT id, text FROM web_post WHERE chat_id = ? AND richtung = 'aus' "
            "AND typ = 'text' AND erstellt_am >= ? AND text IS NOT NULL",
            (chat_id, seit),
        ).fetchall()
        gesamt += len(zeilen)
        for zeile in zeilen:
            if sprachmessung.ist_englisch(zeile["text"]):
                englisch.append((chat_id, zeile["id"]))
    return gesamt, englisch


def main() -> None:
    if len(sys.argv) != 2:
        print("Aufruf: uv run python -m scripts.miss_italienisch <pfad-zur-kopie.db>")
        raise SystemExit(2)
    conn = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    gesamt, englisch = miss(conn)
    anteil = len(englisch) / gesamt if gesamt else 0.0
    print(f"Phase-7 aus/text Posts insgesamt: {gesamt}")
    print(f"Davon englisch erkannt: {len(englisch)} ({anteil:.1%})")
    for chat_id, post_id in englisch:
        print(f"  chat_id={chat_id} web_post.id={post_id}")


if __name__ == "__main__":
    main()
