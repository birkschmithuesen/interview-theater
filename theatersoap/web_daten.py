"""Lesezugriffe der Weboberflaeche: Verbindung rein, Dicts raus.

Reine Funktionen ohne HTTP -- ``theatersoap/web.py`` macht daraus HTML, die
Tests koennen dieselben Daten ohne Server pruefen.

**Warum hier SQL steht, obwohl repo.py sonst die einzige SQL-Schicht ist.**
Die Weboberflaeche haengt an einer eigenen, read-only geoeffneten Verbindung
(``file:...?mode=ro``, siehe oeffne_lesend) und darf grundsaetzlich nichts
schreiben -- der einzige Schreibweg bleibt der Chat
(NACHTRAG-weboberflaeche-und-sprache.md N1). Die Anfragen durch repo.py zu
fuehren hiesse, den modulweiten Schreib-Lock des Bots (``repo._LOCK``) fuer
Leseanfragen zu nehmen, die den Bot nichts angehen: ein projiziertes
Dashboard, das sich alle 10 s neu laedt, wuerde damit Gespraechszuege
ausbremsen. Ausserdem laeuft der Webserver in einem eigenen Prozess, in dem
repo._LOCK ohnehin nichts gegen die Bot-Prozesse ausrichtet -- dafuer sorgen
WAL und busy_timeout.

Alle Werte kommen so heraus, wie sie in der Datenbank stehen (Zeitstempel als
ISO-8601-Text in UTC); Formatierung und Maskierung sind Sache von web.py.
"""

import sqlite3
import statistics
from datetime import datetime, timedelta, timezone

#: Wie weit das Dashboard bei Vorfaellen zurueckschaut. Zwei Stunden, weil das
#: Dashboard den laufenden Workshop-Block zeigen soll und nicht die Historie
#: -- was von gestern rot leuchtet, verstellt den Blick auf das, was gerade
#: kaputt ist.
VORFALL_FENSTER = timedelta(hours=2)


def oeffne_lesend(pfad: str) -> sqlite3.Connection:
    """Oeffnet die Betriebsdatenbank read-only.

    ``mode=ro`` (URI-Modus) laesst SQLite jeden Schreibversuch abweisen, statt
    sich darauf zu verlassen, dass dieses Modul keinen enthaelt.

    Betriebsfalle: eine WAL-Datenbank read-only zu oeffnen funktioniert nur,
    solange die Datei ueberhaupt existiert -- ein Tippfehler in TS_DB gibt
    hier ``unable to open database file`` und nicht etwa eine leere Seite.
    web.py faengt das ab und antwortet mit 500.
    """
    conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def lies_zeitstempel(wert: str | None) -> datetime | None:
    """Liest einen ISO-Zeitstempel aus der Datenbank, tolerant.

    Alles, was repo._jetzt() geschrieben hat, ist UTC mit Zeitzonenangabe.
    Aeltere oder von Hand eingetragene Zeilen koennen die Zone weglassen --
    die gelten dann als UTC, weil eine Zeile auf dem Dashboard falsch
    einsortiert besser ist als ein Absturz beim Projizieren."""
    if not wert:
        return None
    try:
        gelesen = datetime.fromisoformat(wert)
    except ValueError:
        return None
    if gelesen.tzinfo is None:
        return gelesen.replace(tzinfo=timezone.utc)
    return gelesen


def _arbeitsstand(conn: sqlite3.Connection, chat_id: int) -> dict:
    """Die vier Arbeitsstandfelder, immer als Dict -- auch wenn die Gruppe
    noch keine einzige Entscheidung getroffen hat und die Zeile fehlt."""
    zeile = conn.execute(
        "SELECT * FROM arbeitsstand WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return {
        "begriffe": zeile["begriffe"] if zeile else None,
        "kernthema": zeile["kernthema"] if zeile else None,
        "kernthema_begruendung": zeile["kernthema_begruendung"] if zeile else None,
        "hauptkonflikt": zeile["hauptkonflikt"] if zeile else None,
        "geaendert_am": zeile["geaendert_am"] if zeile else None,
    }


def _figuren(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    return [
        {"name": z["name"], "beschreibung": z["beschreibung"]}
        for z in conn.execute(
            "SELECT name, beschreibung FROM figur WHERE chat_id = ? ORDER BY id ASC",
            (chat_id,),
        )
    ]


def _aufnahmen_nach_status(conn: sqlite3.Connection, chat_id: int) -> dict[str, int]:
    return {
        z["status"]: z["anzahl"]
        for z in conn.execute(
            "SELECT status, count(*) AS anzahl FROM aufnahme WHERE chat_id = ? "
            "GROUP BY status ORDER BY status",
            (chat_id,),
        )
    }


def _letzte_aktivitaet(conn: sqlite3.Connection, chat_id: int) -> str | None:
    """gesendet_am der juengsten Nachricht (nach message_id, wie
    repo.letzte_nachricht_zeit -- Telegram vergibt sie aufsteigend)."""
    zeile = conn.execute(
        "SELECT gesendet_am FROM nachricht WHERE chat_id = ? "
        "ORDER BY message_id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()
    return zeile["gesendet_am"] if zeile else None


def _vorfaelle(
    conn: sqlite3.Connection, chat_id: int, bot_name: str | None, jetzt: datetime
) -> list[dict]:
    """Vorfaelle der letzten zwei Stunden fuer diese Gruppe.

    Bot-weite Vorfaelle (``chat_id IS NULL``, z. B. ein Whisper-Ausfall)
    gehoeren zu der Gruppe, die dieser Bot bedient -- ein Prozess je Gruppe,
    deshalb ist die Zuordnung ueber bot_name eindeutig. Ohne diese Regel
    stuenden sie entweder nirgends oder bei allen Gruppen."""
    zeilen = conn.execute(
        """
        SELECT art, stufe, detail, erstellt_am, chat_id
        FROM vorfall
        WHERE chat_id = ? OR (chat_id IS NULL AND bot_name IS ?)
        ORDER BY id DESC
        LIMIT 200
        """,
        (chat_id, bot_name),
    ).fetchall()
    grenze = jetzt - VORFALL_FENSTER
    ergebnis = []
    for z in zeilen:
        zeitpunkt = lies_zeitstempel(z["erstellt_am"])
        if zeitpunkt is None or zeitpunkt < grenze:
            continue
        ergebnis.append(
            {
                "art": z["art"],
                "stufe": z["stufe"],
                "detail": z["detail"],
                "erstellt_am": z["erstellt_am"],
                "bot_weit": z["chat_id"] is None,
            }
        )
    return ergebnis


def _aufrufe_heute(conn: sqlite3.Connection, chat_id: int, jetzt: datetime) -> list[dict]:
    """Je Aufrufart: Anzahl, Fehlschlaege und Median-Dauer des laufenden Tages.

    'Heute' ist der UTC-Tag -- die Zeitstempel stehen so in der Datenbank
    (repo._jetzt), und die Tagesgrenze liegt damit um 02:00 Ortszeit, also
    weit weg von den Workshopzeiten. Median statt Mittelwert, weil ein
    einzelner Ausreisser (gemessen: 8,3 s bei sonst unter 1 s) den Mittelwert
    kippt und dann Alarm auf dem Beamer suggeriert, wo keiner ist."""
    tag = jetzt.astimezone(timezone.utc).date().isoformat()
    zeilen = conn.execute(
        "SELECT art, dauer_ms, erfolg, erstellt_am FROM aufruf WHERE chat_id = ?",
        (chat_id,),
    ).fetchall()
    je_art: dict[str, dict] = {}
    for z in zeilen:
        if not (z["erstellt_am"] or "").startswith(tag):
            continue
        eintrag = je_art.setdefault(z["art"], {"art": z["art"], "anzahl": 0,
                                               "fehlschlaege": 0, "_dauern": []})
        eintrag["anzahl"] += 1
        if z["erfolg"] == 0:
            eintrag["fehlschlaege"] += 1
        if z["dauer_ms"] is not None:
            eintrag["_dauern"].append(z["dauer_ms"])
    ergebnis = []
    for eintrag in sorted(je_art.values(), key=lambda e: e["art"]):
        dauern = eintrag.pop("_dauern")
        eintrag["median_ms"] = round(statistics.median(dauern)) if dauern else None
        ergebnis.append(eintrag)
    return ergebnis


def bot_zuordnung(conn: sqlite3.Connection) -> list[dict]:
    """Welcher Bot bedient welche Gruppe, und wann war er zuletzt aktiv
    (SPEC-kontext-architektur.md § 9.4).

    Auch Bots ohne Gruppe kommen mit: genau der Fall 'Bot laeuft, ist aber in
    keiner Gruppe' bzw. 'zwei Bots in derselben Gruppe' soll auf dem
    Dashboard sofort auffallen statt spaeter raetselhaft zu sein."""
    zeilen = [
        {
            "bot_name": z["bot_name"],
            "chat_id": z["chat_id"],
            "titel": z["titel"],
            "letzte_aktivitaet_am": z["letzte_aktivitaet_am"],
            "gestartet_am": z["gestartet_am"],
        }
        for z in conn.execute(
            """
            SELECT g.chat_id, g.titel, g.bot_name,
                   b.letzte_aktivitaet_am, b.gestartet_am
            FROM gruppe g
            LEFT JOIN bot_zustand b ON b.bot_name = g.bot_name
            ORDER BY g.bot_name, g.chat_id
            """
        )
    ]
    bekannte = {z["bot_name"] for z in zeilen}
    for z in conn.execute("SELECT * FROM bot_zustand ORDER BY bot_name"):
        if z["bot_name"] in bekannte:
            continue
        zeilen.append(
            {
                "bot_name": z["bot_name"],
                "chat_id": None,
                "titel": None,
                "letzte_aktivitaet_am": z["letzte_aktivitaet_am"],
                "gestartet_am": z["gestartet_am"],
            }
        )
    return zeilen


def dashboard(conn: sqlite3.Connection, jetzt: datetime | None = None) -> dict:
    """Alle Gruppen fuer das projizierte Team-Dashboard.

    Bewusst ohne jeden Nachrichtentext und ohne Transkripte: die Seite haengt
    am Beamer, und in den Interviews stehen Lebensgeschichten. Was hier
    steht, sind Arbeitsergebnisse, Zahlen und Vorfaelle.

    ``jetzt`` ist nur fuer die Tests da (Vorfallfenster, Tagesgrenze)."""
    jetzt = jetzt or datetime.now(timezone.utc)
    gruppen = []
    for z in conn.execute("SELECT * FROM gruppe ORDER BY titel IS NULL, titel, chat_id"):
        chat_id = z["chat_id"]
        gruppen.append(
            {
                "chat_id": chat_id,
                "titel": z["titel"],
                "bot_name": z["bot_name"],
                "interviewmodus_seit": z["interviewmodus_seit"],
                "arbeitsstand": _arbeitsstand(conn, chat_id),
                "figuren": _figuren(conn, chat_id),
                "aufnahmen": _aufnahmen_nach_status(conn, chat_id),
                "verdichtungen": conn.execute(
                    "SELECT count(*) FROM verdichtung WHERE chat_id = ?", (chat_id,)
                ).fetchone()[0],
                "szenen": conn.execute(
                    "SELECT count(*) FROM szene WHERE chat_id = ?", (chat_id,)
                ).fetchone()[0],
                "letzte_aktivitaet": _letzte_aktivitaet(conn, chat_id),
                "vorfaelle": _vorfaelle(conn, chat_id, z["bot_name"], jetzt),
                "aufrufe": _aufrufe_heute(conn, chat_id, jetzt),
            }
        )
    return {
        "gruppen": gruppen,
        "bot_zuordnung": bot_zuordnung(conn),
        "stand": jetzt.isoformat(timespec="seconds"),
    }


def _szenen(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """Die Szenen der Gruppe, nach ``nummer``.

    Die Tabelle ist heute leer -- Szenen entstehen in der letzten
    Workshop-Phase, ein paralleler Zweig baut das Schreiben. Die Ansicht
    steht trotzdem, damit die Gruppenseite an dem Tag nichts mehr braucht.
    Zeilen ohne Nummer landen hinten statt vorn (NULL sortiert in SQLite
    sonst zuerst)."""
    return [
        {
            "nummer": z["nummer"],
            "titel": z["titel"],
            "kurzbeschreibung": z["kurzbeschreibung"],
            "volltext": z["volltext"],
            "geaendert_am": z["geaendert_am"],
        }
        for z in conn.execute(
            "SELECT * FROM szene WHERE chat_id = ? "
            "ORDER BY nummer IS NULL, nummer ASC, id ASC",
            (chat_id,),
        )
    ]


def _verdichtungen(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """Verdichtungen je Interview mit ihren Kernthemen.

    Ein Belegzitat wird nur gezeigt, wenn es die Pruefung bestanden hat
    (``zitat_geprueft = 1``, SPEC § 5). Ein ungeprueftes Zitat waere genau
    das, wogegen das Belegzitat-Prinzip antritt: ein Satz in
    Anfuehrungszeichen, den vielleicht niemand gesagt hat. Das Thema bleibt
    stehen, das Zitat faellt weg."""
    ergebnis = []
    for z in conn.execute(
        """
        SELECT v.id, v.zusammenfassung, v.erstellt_am, a.name AS aufnahme_name
        FROM verdichtung v
        LEFT JOIN aufnahme a ON a.id = v.aufnahme_id
        WHERE v.chat_id = ?
        ORDER BY v.id ASC
        """,
        (chat_id,),
    ):
        themen = [
            {
                "thema": t["thema"],
                "zitat": t["beleg_zitat"] if t["zitat_geprueft"] == 1 else None,
            }
            for t in conn.execute(
                "SELECT thema, beleg_zitat, zitat_geprueft FROM verdichtung_thema "
                "WHERE verdichtung_id = ? ORDER BY id ASC",
                (z["id"],),
            )
        ]
        ergebnis.append(
            {
                "aufnahme": z["aufnahme_name"],
                "zusammenfassung": z["zusammenfassung"],
                "erstellt_am": z["erstellt_am"],
                "themen": themen,
            }
        )
    return ergebnis


def _journal(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    return [
        {"art": z["art"], "text": z["text"], "quelle": z["quelle"],
         "erstellt_am": z["erstellt_am"]}
        for z in conn.execute(
            "SELECT art, text, quelle, erstellt_am FROM journal "
            "WHERE chat_id = ? ORDER BY id ASC",
            (chat_id,),
        )
    ]


def gruppe_nach_token(conn: sqlite3.Connection, token: str | None) -> dict | None:
    """Die Leseansicht einer Gruppe, adressiert ueber ihr Web-Token.

    Liefert None, wenn das Token unbekannt ist -- der Aufrufer antwortet
    darauf mit 404 und verraet nicht, ob es ueberhaupt Gruppen gibt. Ein
    leeres Token wird gar nicht erst gesucht: sonst traefe ``/g/`` jede
    Gruppe, deren Spalte noch leer steht.

    Ohne Volltranskripte -- dafuer gibt es /wortlaut im Chat, und eine URL
    ohne Login ist nicht der Ort fuer die Rohaufnahme eines Interviews."""
    if not token:
        return None
    zeile = conn.execute(
        "SELECT * FROM gruppe WHERE web_token = ?", (token,)
    ).fetchone()
    if zeile is None:
        return None
    chat_id = zeile["chat_id"]
    return {
        "chat_id": chat_id,
        "titel": zeile["titel"],
        "bot_name": zeile["bot_name"],
        "interviewmodus_seit": zeile["interviewmodus_seit"],
        "arbeitsstand": _arbeitsstand(conn, chat_id),
        "figuren": _figuren(conn, chat_id),
        "szenen": _szenen(conn, chat_id),
        "verdichtungen": _verdichtungen(conn, chat_id),
        "journal": _journal(conn, chat_id),
    }
