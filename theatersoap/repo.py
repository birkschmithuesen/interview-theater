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


def lege_aufnahme_an(
    conn: sqlite3.Connection,
    chat_id: int,
    message_id: int,
    klasse: str,
    quelle: str,
    audio_pfad: str | None = None,
    dauer: int | None = None,
) -> int:
    """Legt eine Aufnahme (Sprache oder Textimport) an und vergibt den
    Ersatznamen 'Interview n', wobei n die Anzahl bereits vorhandener
    Aufnahmen dieser Gruppe plus eins ist. Startstatus immer 'empfangen';
    der Aufrufer entscheidet ueber weitere Statusuebergaenge."""
    name = f"Interview {zaehle_aufnahmen(conn, chat_id) + 1}"
    cur = conn.execute(
        """
        INSERT INTO aufnahme
            (chat_id, message_id, name, klasse, quelle, audio_pfad,
             dauer_sekunden, status, empfangen_am)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'empfangen', ?)
        """,
        (chat_id, message_id, name, klasse, quelle, audio_pfad, dauer, _jetzt()),
    )
    conn.commit()
    return cur.lastrowid


def hole_aufnahme(conn: sqlite3.Connection, aufnahme_id: int) -> sqlite3.Row | None:
    """Liefert die aufnahme-Zeile oder None, wenn unbekannt."""
    return conn.execute(
        "SELECT * FROM aufnahme WHERE id = ?", (aufnahme_id,)
    ).fetchone()


def setze_status(
    conn: sqlite3.Connection, aufnahme_id: int, status: str, fehlertext: str | None = None
) -> None:
    """Setzt Status (und ggf. Fehlertext) einer Aufnahme."""
    conn.execute(
        "UPDATE aufnahme SET status = ?, fehlertext = ? WHERE id = ?",
        (status, fehlertext, aufnahme_id),
    )
    conn.commit()


def setze_transkript(conn: sqlite3.Connection, aufnahme_id: int, text: str) -> None:
    """Traegt das Transkript einer Aufnahme ein."""
    conn.execute(
        "UPDATE aufnahme SET transkript = ? WHERE id = ?", (text, aufnahme_id)
    )
    conn.commit()


def setze_aufnahme_name(conn: sqlite3.Connection, aufnahme_id: int, name: str) -> None:
    """Ersetzt den (ggf. automatisch vergebenen) Namen einer Aufnahme."""
    conn.execute(
        "UPDATE aufnahme SET name = ? WHERE id = ?", (name, aufnahme_id)
    )
    conn.commit()


def offene_aufnahmen(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Alle Aufnahmen, deren Status weder 'fertig' noch 'fehlgeschlagen' ist --
    Grundlage dafuer, dass ein Neustart ueber Nacht angefangene Arbeit zu Ende
    bringt (Nachhol-Arbeiter, Aufgabe 8). Ueber alle Gruppen hinweg, absichtlich
    ohne chat_id-Filter."""
    return conn.execute(
        "SELECT * FROM aufnahme WHERE status NOT IN ('fertig', 'fehlgeschlagen') "
        "ORDER BY id ASC"
    ).fetchall()


def zaehle_aufnahmen(conn: sqlite3.Connection, chat_id: int) -> int:
    """Anzahl der Aufnahmen einer Gruppe, unabhaengig vom Status."""
    return conn.execute(
        "SELECT count(*) FROM aufnahme WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]


def speichere_verdichtung(
    conn: sqlite3.Connection,
    chat_id: int,
    aufnahme_id: int,
    zusammenfassung: str,
    themen: list[dict],
) -> int:
    """Speichert eine Verdichtung mit ihren Kernthemen. Wird laut SPEC nie
    aktualisiert -- es gibt bewusst kein aktualisiere_verdichtung(). Jedes
    Element von ``themen`` braucht die Schluessel 'thema', 'beleg_zitat'
    (kann None sein, wenn die Pruefung nach § 5 fehlschlug) und
    'zitat_geprueft' (0 oder 1)."""
    cur = conn.execute(
        """
        INSERT INTO verdichtung (chat_id, aufnahme_id, zusammenfassung, erstellt_am)
        VALUES (?, ?, ?, ?)
        """,
        (chat_id, aufnahme_id, zusammenfassung, _jetzt()),
    )
    verdichtung_id = cur.lastrowid
    for thema in themen:
        conn.execute(
            """
            INSERT INTO verdichtung_thema
                (chat_id, verdichtung_id, thema, beleg_zitat, zitat_geprueft)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                verdichtung_id,
                thema["thema"],
                thema["beleg_zitat"],
                thema["zitat_geprueft"],
            ),
        )
    conn.commit()
    return verdichtung_id


def verdichtungen(conn: sqlite3.Connection, chat_id: int) -> list[sqlite3.Row]:
    """Alle Verdichtungen einer Gruppe, in Entstehungsreihenfolge."""
    return conn.execute(
        "SELECT * FROM verdichtung WHERE chat_id = ? ORDER BY id ASC", (chat_id,)
    ).fetchall()


def themen_zu(conn: sqlite3.Connection, verdichtung_id: int) -> list[sqlite3.Row]:
    """Die Kernthemen einer Verdichtung, in der vom Sprachmodell gelieferten
    Reihenfolge."""
    return conn.execute(
        "SELECT * FROM verdichtung_thema WHERE verdichtung_id = ? ORDER BY id ASC",
        (verdichtung_id,),
    ).fetchall()


def transkripte(
    conn: sqlite3.Connection, chat_id: int, name: str | None = None
) -> list[sqlite3.Row]:
    """Aufnahmen einer Gruppe. Bei gesetztem ``name`` wird grosszuegig gesucht
    (Gross-/Kleinschreibung egal, Teiltreffer genuegt) statt exakt zu
    vergleichen -- die Gruppe tippt Namen nicht immer gleich."""
    zeilen = conn.execute(
        "SELECT * FROM aufnahme WHERE chat_id = ? ORDER BY id ASC", (chat_id,)
    ).fetchall()
    if name is None:
        return zeilen
    gesucht = name.lower()
    return [z for z in zeilen if z["name"] and gesucht in z["name"].lower()]


def hole_nachricht(conn: sqlite3.Connection, chat_id: int, message_id: int) -> sqlite3.Row | None:
    """Liefert eine einzelne Nachrichtenzeile oder None (Aufgabe 8: die
    Aufnahme-Pipeline braucht gesendet_am der urspruenglichen Sprachnachricht,
    um zu entscheiden, ob ein fertiges Transkript noch jung genug ist, um
    einen Gespraechszug auszuloesen)."""
    return conn.execute(
        "SELECT * FROM nachricht WHERE chat_id = ? AND message_id = ?",
        (chat_id, message_id),
    ).fetchone()


def aktualisiere_transkribierte_nachricht(
    conn: sqlite3.Connection, chat_id: int, message_id: int, text: str, unterdrueckt: int
) -> None:
    """Verwandelt die schon vorhandene Sprachnachricht-Zeile (typ='sprache',
    text=NULL) in eine Textnachricht -- per UPDATE, nicht per INSERT, damit im
    Verlauf keine zweite Zeile fuer dieselbe Aeusserung entsteht und die
    Reihenfolge erhalten bleibt (Aufgabe 8, SPEC-kontext-architektur.md
    § 10.2). ``unterdrueckt`` entscheidet der Aufrufer (Nachtstau-Regel bzw.
    Nachgeholtes loest nie eine Antwort aus)."""
    conn.execute(
        "UPDATE nachricht SET text = ?, typ = 'text', unterdrueckt = ? "
        "WHERE chat_id = ? AND message_id = ?",
        (text, unterdrueckt, chat_id, message_id),
    )
    conn.commit()


def zaehle_versuch_hoch(conn: sqlite3.Connection, aufnahme_id: int) -> int:
    """Erhoeht aufnahme.versuche um eins und liefert den neuen Stand (Aufgabe 8,
    Grundlage fuer MAX_VERSUCHE: nach wiederholten Fehlschlaegen soll eine
    Aufnahme irgendwann 'fehlgeschlagen' werden, statt bis Sonntagabend im
    Kreis zu laufen)."""
    conn.execute(
        "UPDATE aufnahme SET versuche = versuche + 1 WHERE id = ?", (aufnahme_id,)
    )
    conn.commit()
    return conn.execute(
        "SELECT versuche FROM aufnahme WHERE id = ?", (aufnahme_id,)
    ).fetchone()["versuche"]


def setze_whisper_stumm_seit(conn: sqlite3.Connection, chat_id: int, wert: str | None) -> None:
    """Setzt oder leert gruppe.whisper_stumm_seit (Aufgabe 8, SPEC § 10.4):
    gesetzt bedeutet, der einmalige Ausfall-Hinweis wurde schon geschickt und
    weitere Fehlschlaege bleiben still, bis die Rueckkehr gemeldet wird."""
    conn.execute(
        "UPDATE gruppe SET whisper_stumm_seit = ? WHERE chat_id = ?", (wert, chat_id)
    )
    conn.commit()


def offene_aufnahmen_fuer_bot(conn: sqlite3.Connection, bot_name: str) -> list[sqlite3.Row]:
    """Wie offene_aufnahmen(), aber auf die Gruppen eingeschraenkt, die dieser
    Bot-Prozess bedient (gruppe.bot_name). Grundlage der Nebenlaeufigkeits-
    Absicherung des Nachhol-Arbeiters (Aufgabe 8, Auftragshinweis 3): es laeuft
    ein Prozess je Gruppe, alle auf derselben SQLite-Datei, und
    offene_aufnahmen() filtert absichtlich nicht nach chat_id (Aufgabe 7).
    Ohne diese Einschraenkung wuerden zwei Prozesse dieselbe Aufnahme
    gleichzeitig zu Whisper hochladen."""
    return conn.execute(
        """
        SELECT a.* FROM aufnahme a
        JOIN gruppe g ON g.chat_id = a.chat_id
        WHERE g.bot_name = ? AND a.status NOT IN ('fertig', 'fehlgeschlagen')
        ORDER BY a.id ASC
        """,
        (bot_name,),
    ).fetchall()


def setze_whisper_stumm_seit_falls_leer(conn: sqlite3.Connection, chat_id: int, wert: str) -> bool:
    """Setzt gruppe.whisper_stumm_seit atomar, aber nur wenn es noch leer war
    (Aufgabe 8, Nachbesserung 'Wichtig 1'). Liefert True, wenn DIESER Aufruf
    das Feld gesetzt hat -- die Grundlage fuer die 'genau einmal'-Zusage, wenn
    mehrere Threads eines Pools gleichzeitig auf denselben Whisper-Ausfall
    stossen: ohne das atomare ``WHERE whisper_stumm_seit IS NULL`` koennten
    zwei Threads beide noch ``NULL`` lesen und beide senden."""
    cur = conn.execute(
        "UPDATE gruppe SET whisper_stumm_seit = ? "
        "WHERE chat_id = ? AND whisper_stumm_seit IS NULL",
        (wert, chat_id),
    )
    conn.commit()
    return cur.rowcount == 1


def leere_whisper_stumm_seit_falls_gesetzt(conn: sqlite3.Connection, chat_id: int) -> bool:
    """Spiegelbild zu setze_whisper_stumm_seit_falls_leer: leert das Feld
    atomar, aber nur wenn es gesetzt war. Liefert True, wenn DIESER Aufruf es
    geleert hat."""
    cur = conn.execute(
        "UPDATE gruppe SET whisper_stumm_seit = NULL "
        "WHERE chat_id = ? AND whisper_stumm_seit IS NOT NULL",
        (chat_id,),
    )
    conn.commit()
    return cur.rowcount == 1


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
