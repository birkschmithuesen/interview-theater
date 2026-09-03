"""Repository-Schicht: einzige Stelle mit SQL ausser db.py (SPEC-kontext-architektur.md).

Alle spaeteren Module greifen ausschliesslich ueber dieses Modul auf die
Datenbank zu. Nach jedem Schreibvorgang wird committet, weil mehrere Threads
dieselbe SQLite-Datei benutzen (global-constraints.md § 3): lange offene
Transaktionen sind hier das Problem, nicht die Commit-Kosten.
"""

import sqlite3
from datetime import datetime, timezone


def _jetzt() -> str:
    """ISO-8601-Zeitstempel in UTC, Sekundengenauigkeit.

    Trotz Unterstrich Teil der oeffentlichen Schnittstelle: andere Module
    rufen repo._jetzt() direkt auf.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sichere_gruppe(conn: sqlite3.Connection, chat_id: int, bot_name: str, titel: str) -> None:
    """Legt die Gruppe an, falls noch unbekannt; aktualisiert sonst Titel/Bot-Name."""
    conn.execute(
        """
        INSERT INTO gruppe (chat_id, bot_name, titel, erste_nachricht_am)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            bot_name = excluded.bot_name,
            titel = excluded.titel
        """,
        (chat_id, bot_name, titel, _jetzt()),
    )
    conn.commit()


def hole_gruppe(conn: sqlite3.Connection, chat_id: int) -> sqlite3.Row | None:
    """Liefert die gruppe-Zeile oder None, wenn unbekannt."""
    return conn.execute(
        "SELECT * FROM gruppe WHERE chat_id = ?", (chat_id,)
    ).fetchone()


def merke_nachricht(
    conn: sqlite3.Connection,
    chat_id: int,
    message_id: int,
    absender: str,
    ist_bot: int,
    typ: str,
    text: str,
    gesendet_am: str,
    unterdrueckt: int = 0,
) -> bool:
    """Speichert eine Nachricht. Liefert True bei Neueinfuegung, False bei Duplikat
    (chat_id, message_id) ist Primaerschluessel, daher INSERT OR IGNORE."""
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO nachricht
            (chat_id, message_id, absender, ist_bot, typ, text, gesendet_am, unterdrueckt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (chat_id, message_id, absender, ist_bot, typ, text, gesendet_am, unterdrueckt),
    )
    conn.commit()
    return cur.rowcount == 1


def unbeantwortete(conn: sqlite3.Connection, chat_id: int) -> list[sqlite3.Row]:
    """Nachrichten, die einen Zug ausloesen sollen: kein Bot, nicht unterdrueckt
    (weder Nachtstau noch Sprachnachricht ohne Transkript) und neuer als das
    Wasserzeichen letzte_beantwortete_message_id."""
    return conn.execute(
        """
        SELECT n.* FROM nachricht n
        JOIN gruppe g ON g.chat_id = n.chat_id
        WHERE n.chat_id = ?
          AND n.ist_bot = 0
          AND n.unterdrueckt = 0
          AND n.message_id > g.letzte_beantwortete_message_id
        ORDER BY n.message_id ASC
        """,
        (chat_id,),
    ).fetchall()


def setze_beantwortet_bis(conn: sqlite3.Connection, chat_id: int, message_id: int) -> None:
    """Setzt das Wasserzeichen letzte_beantwortete_message_id. Bewegt sich nie
    rueckwaerts, sonst wuerden bereits beantwortete Nachrichten erneut einen
    Zug ausloesen (siehe unbeantwortete())."""
    conn.execute(
        """
        UPDATE gruppe SET letzte_beantwortete_message_id = ?
        WHERE chat_id = ? AND letzte_beantwortete_message_id < ?
        """,
        (message_id, chat_id, message_id),
    )
    conn.commit()


def letzte_nachrichten(conn: sqlite3.Connection, chat_id: int, anzahl: int = 200) -> list[sqlite3.Row]:
    """Die letzten `anzahl` Nachrichten der Gruppe in chronologischer Reihenfolge."""
    return conn.execute(
        """
        SELECT * FROM (
            SELECT * FROM nachricht
            WHERE chat_id = ?
            ORDER BY message_id DESC
            LIMIT ?
        )
        ORDER BY message_id ASC
        """,
        (chat_id, anzahl),
    ).fetchall()


def hole_update_id(conn: sqlite3.Connection, bot_name: str) -> int:
    """Liefert die zuletzt verarbeitete getUpdates-Position, 0 wenn unbekannt."""
    row = conn.execute(
        "SELECT letzte_update_id FROM bot_zustand WHERE bot_name = ?", (bot_name,)
    ).fetchone()
    if row is None or row["letzte_update_id"] is None:
        return 0
    return row["letzte_update_id"]


def setze_update_id(conn: sqlite3.Connection, bot_name: str, update_id: int) -> None:
    """Merkt die getUpdates-Position pro Bot-Token (nicht pro Gruppe)."""
    jetzt = _jetzt()
    conn.execute(
        """
        INSERT INTO bot_zustand (bot_name, letzte_update_id, gestartet_am, letzte_aktivitaet_am)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(bot_name) DO UPDATE SET
            letzte_update_id = excluded.letzte_update_id,
            letzte_aktivitaet_am = excluded.letzte_aktivitaet_am
        """,
        (bot_name, update_id, jetzt, jetzt),
    )
    conn.commit()


def merke_vorfall(
    conn: sqlite3.Connection,
    chat_id: int | None,
    bot_name: str | None,
    art: str,
    detail: str,
    stufe: int | None = None,
) -> None:
    """Traegt einen Vorfall ein, der das Dashboard rot faerbt (global-constraints.md
    'Fehlerhaltung')."""
    conn.execute(
        """
        INSERT INTO vorfall (chat_id, bot_name, art, stufe, detail, erstellt_am)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (chat_id, bot_name, art, stufe, detail, _jetzt()),
    )
    conn.commit()


def merke_aufruf(
    conn: sqlite3.Connection,
    chat_id: int | None,
    art: str,
    modus: str | None = None,
    geschaetzte_token: int | None = None,
    tatsaechliche_token: int | None = None,
    antwort_token: int | None = None,
    finish_reason: str | None = None,
    dauer_ms: int | None = None,
    erfolg: int | None = None,
) -> None:
    """Protokolliert einen Sprachmodell-Aufruf zur Selbstkorrektur der Token-Schaetzung
    (global-constraints.md § 4)."""
    conn.execute(
        """
        INSERT INTO aufruf
            (chat_id, art, modus, geschaetzte_token, tatsaechliche_token,
             antwort_token, finish_reason, dauer_ms, erfolg, erstellt_am)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chat_id,
            art,
            modus,
            geschaetzte_token,
            tatsaechliche_token,
            antwort_token,
            finish_reason,
            dauer_ms,
            erfolg,
            _jetzt(),
        ),
    )
    conn.commit()
