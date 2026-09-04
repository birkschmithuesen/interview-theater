"""Repository-Schicht: einzige Stelle mit SQL ausser db.py (SPEC-kontext-architektur.md).

Alle spaeteren Module greifen ausschliesslich ueber dieses Modul auf die
Datenbank zu. Nach jedem Schreibvorgang wird committet, weil mehrere Threads
dieselbe SQLite-Datei benutzen (global-constraints.md § 3): lange offene
Transaktionen sind hier das Problem, nicht die Commit-Kosten.

**Nachbesserung nach Aufgabe 10:** ``db.verbinde()`` oeffnet mit
``check_same_thread=False`` und reicht EINE ``sqlite3.Connection`` an alle
Threads des Prozesses durch (Poll-Schleife, 8er-Pool, Nachhol-Thread --
inzwischen auch jeder Gespraechszug aus ``ablauf.bearbeite``, der ueber den
Pool laeuft). ``check_same_thread=False`` hebt nur die
Thread-Zugehoerigkeitspruefung auf, macht das ``sqlite3``-Modul aber NICHT
sicher gegen gleichzeitige ``execute``/``commit``-Aufrufe auf demselben
Verbindungsobjekt -- die interne Transaktionsbuchhaltung ist nicht
synchronisiert. WAL und ``busy_timeout`` (global-constraints.md § 3) loesen
nur die Dateisperre ZWISCHEN Prozessen, nicht diese Racebedingung INNERHALB
eines Prozesses; beobachtet als sporadisches ``sqlite3.OperationalError:
cannot commit - no transaction is active`` bzw. ``SystemError`` unter
mehreren gleichzeitigen Schreibern.

Der Fix bleibt bewusst klein und laesst ``db.py`` unangetastet: ein
modulweiter ``_LOCK`` (siehe ``_gesperrt`` unten) serialisiert jede
Repo-Funktion, lesend wie schreibend, gegen jede andere. ``threading.RLock``
statt ``threading.Lock``, weil ``lege_aufnahme_an`` innerhalb desselben
Threads ``zaehle_aufnahmen`` aufruft -- mit einem einfachen ``Lock`` wuerde
sich der Thread beim zweiten ``acquire`` selbst blockieren (Selbst-Deadlock).
"""

import secrets
import sqlite3
import threading
from datetime import datetime, timezone

#: Serialisiert saemtliche Repo-Funktionen gegeneinander (siehe Moduldocstring
#: oben). RLock, nicht Lock: repo-interne Aufrufe (aktuell nur
#: lege_aufnahme_an -> zaehle_aufnahmen) laufen sonst in einen
#: Selbst-Deadlock.
_LOCK = threading.RLock()


def _gesperrt(fn):
    """Dekoriert eine Repo-Funktion so, dass ihr gesamter Rumpf unter
    ``_LOCK`` laeuft -- funktional dasselbe wie ``with _LOCK:`` als erste
    Zeile jeder Funktion, nur ohne 34 Funktionsruempfe von Hand neu
    einzuruecken (und damit ohne das Risiko, dabei eine Einrueckung falsch zu
    setzen)."""
    def wrapper(*args, **kwargs):
        with _LOCK:
            return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def _jetzt() -> str:
    """ISO-8601-Zeitstempel in UTC, Sekundengenauigkeit.

    Trotz Unterstrich Teil der oeffentlichen Schnittstelle: andere Module
    rufen repo._jetzt() direkt auf. Beruehrt die Datenbank nicht und braucht
    deshalb kein _gesperrt."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _jetzt_genau() -> str:
    """Wie _jetzt(), aber mikrosekundengenau -- ausschliesslich fuer
    ``szene.geaendert_am``.

    Dieses eine Feld ist nicht nur Buchhaltung, sondern eine Sortierung, an
    der eine Entscheidung haengt: welche Szene als 'die aktuelle' in den
    Gespraechs-Prompt wandert (hole_letzte_szene, SPEC § 6.2 Block 5).
    Sekundengenau waeren zwei Schreibvorgaenge in derselben Sekunde nicht
    unterscheidbar, und die zweitbeste Sortierung (``id DESC``) faellt genau
    dann falsch aus, wenn eine AELTERE Szene ueberarbeitet wird -- dann hat
    die gemeinte Szene die kleinere id.

    ISO-8601 sortiert auch gemischt lexikographisch korrekt ('...:00+00:00'
    vor '...:00.5+00:00', weil '+' < '.'), die Umstellung braucht also keine
    Migration -- und in die Tabelle ``szene`` hat ohnehin noch nie jemand
    geschrieben."""
    return datetime.now(timezone.utc).isoformat()


@_gesperrt
def sichere_gruppe(conn: sqlite3.Connection, chat_id: int, bot_name: str, titel: str) -> None:
    """Legt die Gruppe an, falls noch unbekannt; aktualisiert sonst Titel/Bot-Name.

    Nimmt seit der Weboberflaeche ausserdem das Web-Token mit (siehe
    stelle_web_token_sicher): der Webserver liest read-only und kann keines
    erzeugen, also muss der Bot es tun -- und das hier ist die eine Stelle,
    die bei jeder eingehenden Nachricht jeder Gruppe laeuft."""
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
    stelle_web_token_sicher(conn, chat_id)


#: Laenge des Zufallstokens fuer /g/<token>. 24 Bytes ergeben 32 Zeichen
#: base64url -- nicht ratbar, aber noch abtippbar, falls jemand die URL vom
#: Beamer abschreiben muss.
WEB_TOKEN_BYTES = 24


@_gesperrt
def gruppenseite_url(conn: sqlite3.Connection, chat_id: int, basis: str) -> str | None:
    """Die URL der Leseansicht dieser Gruppe, oder None ohne Basis/Token.
    Der Bot nennt sie in der Begruessung und in /stand -- die Gruppe soll
    den Link nicht vom Workshop-Team abschreiben muessen."""
    if not basis:
        return None
    token = stelle_web_token_sicher(conn, chat_id)
    return f"{basis}/g/{token}" if token else None


def stelle_web_token_sicher(conn: sqlite3.Connection, chat_id: int) -> str | None:
    """Liefert das Web-Token der Gruppe und erzeugt es beim ersten Bedarf.

    Der Webserver oeffnet die Datenbank read-only
    (``interview_theater/web_daten.py``), deshalb entsteht das Token hier im
    Schreibpfad des Bots. Das ``WHERE web_token IS NULL`` macht das Setzen
    atomar: laufen zwei Bot-Prozesse gleichzeitig durch, gewinnt einer, und
    beide lesen danach dasselbe Token. Liefert None, wenn es die Gruppe nicht
    gibt (kein Grund, dafuer eine Zeile anzulegen)."""
    zeile = conn.execute(
        "SELECT web_token FROM gruppe WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    if zeile is None:
        return None
    if zeile["web_token"]:
        return zeile["web_token"]
    conn.execute(
        "UPDATE gruppe SET web_token = ? WHERE chat_id = ? AND web_token IS NULL",
        (secrets.token_urlsafe(WEB_TOKEN_BYTES), chat_id),
    )
    conn.commit()
    return conn.execute(
        "SELECT web_token FROM gruppe WHERE chat_id = ?", (chat_id,)
    ).fetchone()["web_token"]


@_gesperrt
def alle_gruppen(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Alle Gruppen ueber alle Bots hinweg, aeltester Eintrag zuerst --
    Grundlage von ``scripts/web_links.py`` (eine Zeile je Gruppe mit ihrer
    Web-URL). Anders als gruppen_fuer_bot() bewusst ohne bot_name-Filter: das
    Betreiberskript laeuft neben allen Bot-Prozessen, nicht in einem."""
    return conn.execute("SELECT * FROM gruppe ORDER BY chat_id ASC").fetchall()


@_gesperrt
def hole_gruppe(conn: sqlite3.Connection, chat_id: int) -> sqlite3.Row | None:
    """Liefert die gruppe-Zeile oder None, wenn unbekannt."""
    return conn.execute(
        "SELECT * FROM gruppe WHERE chat_id = ?", (chat_id,)
    ).fetchone()


@_gesperrt
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


#: Das Transkript-Echo eines Interview-Teils, das der Bot zur Kontrolle in den
#: Chat schreibt (§ 10.6). Es steht in ``nachricht`` wie jede andere Nachricht
#: -- Empfangen und In-den-Prompt-legen sind zwei Entscheidungen (SPEC § 1) --,
#: gehoert aber in kein Fenster: der Absichtserkenner wuerde Interviewinhalt
#: als Gruppenabsicht lesen (Korpusfaelle n12/n26: "das ist mein Kernthema"
#: sagt die interviewte Person, nicht die Gruppe), und im Gespraechsfenster
#: verdoppelte es Material, das ohnehin als Verdichtung im Prompt steht.
TYP_TRANSKRIPT = "transkript"

#: Als SQL-Bedingung, damit die drei Fenster-Abfragen nie auseinanderlaufen.
_OHNE_TRANSKRIPT_ECHO = f"n.typ != '{TYP_TRANSKRIPT}'"


@_gesperrt
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


@_gesperrt
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


@_gesperrt
def unextrahierte(conn: sqlite3.Connection, chat_id: int) -> list[sqlite3.Row]:
    """Nachrichten seit dem Extraktions-Wasserzeichen letzte_extrahierte_message_id
    (SPEC-kontext-architektur.md § 4.3): der Kontext des Absichtserkenners.

    Anders als unbeantwortete() fast ungefiltert -- weder ist_bot noch
    unterdrueckt schraenken ein. Der Erkenner soll den ganzen
    Gespraechsausschnitt seit der letzten Erkennung sehen, auch
    Bot-Bestaetigungen ('Ich zeichne jetzt auf') und Nachtstau-Zeilen,
    nicht nur das, was einen Gespraechszug ausgeloest haette.

    Die einzige Ausnahme sind die Transkript-Echos (``typ='transkript'``,
    siehe TYP_TRANSKRIPT): was die interviewte Person erzaehlt, ist keine
    Aenderungsabsicht der Gruppe."""
    return conn.execute(
        f"""
        SELECT n.* FROM nachricht n
        JOIN gruppe g ON g.chat_id = n.chat_id
        WHERE n.chat_id = ?
          AND n.message_id > g.letzte_extrahierte_message_id
          AND {_OHNE_TRANSKRIPT_ECHO}
        ORDER BY n.message_id ASC
        """,
        (chat_id,),
    ).fetchall()


@_gesperrt
def setze_extrahiert_bis(conn: sqlite3.Connection, chat_id: int, message_id: int) -> None:
    """Setzt das Wasserzeichen letzte_extrahierte_message_id. Bewegt sich nie
    rueckwaerts (analog setze_beantwortet_bis) -- ein Absichtserkenner-Lauf,
    der auf einem veralteten Snapshot lief, darf ein inzwischen weiter
    vorgerueckes Wasserzeichen nicht zuruecksetzen."""
    conn.execute(
        """
        UPDATE gruppe SET letzte_extrahierte_message_id = ?
        WHERE chat_id = ? AND letzte_extrahierte_message_id < ?
        """,
        (message_id, chat_id, message_id),
    )
    conn.commit()


@_gesperrt
def letzte_nachrichten(conn: sqlite3.Connection, chat_id: int, anzahl: int = 200) -> list[sqlite3.Row]:
    """Die letzten `anzahl` Nachrichten der Gruppe in chronologischer
    Reihenfolge -- die Grundlage des Gespraechsfensters (kontext.baue).

    Ohne die Transkript-Echos (siehe TYP_TRANSKRIPT): ein Interview steht als
    Verdichtung im Prompt, nicht als Rohtext im Verlaufsfenster, wo es das
    Fenster fuellen und die Aeusserungen der interviewten Person mit denen der
    Gruppe vermischen wuerde."""
    return conn.execute(
        f"""
        SELECT * FROM (
            SELECT n.* FROM nachricht n
            WHERE n.chat_id = ?
              AND {_OHNE_TRANSKRIPT_ECHO}
            ORDER BY n.message_id DESC
            LIMIT ?
        )
        ORDER BY message_id ASC
        """,
        (chat_id, anzahl),
    ).fetchall()


@_gesperrt
def hole_update_id(conn: sqlite3.Connection, bot_name: str) -> int:
    """Liefert die zuletzt verarbeitete getUpdates-Position, 0 wenn unbekannt."""
    row = conn.execute(
        "SELECT letzte_update_id FROM bot_zustand WHERE bot_name = ?", (bot_name,)
    ).fetchone()
    if row is None or row["letzte_update_id"] is None:
        return 0
    return row["letzte_update_id"]


@_gesperrt
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


@_gesperrt
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


#: Status, in denen an einer Aufnahme nichts mehr zu tun ist. ``laeuft``
#: gehoert dazu, obwohl es kein Endzustand ist: ein Interview-Kopf mit diesem
#: Status sammelt gerade noch Teile ein: der Nachhol-Arbeiter darf ihn nicht
#: als liegengebliebene Arbeit aufgreifen und verdichten (§ 10.6). Beendete
#: Koepfe holt ``beendete_offene_interviews`` gesondert.
_NICHTS_ZU_TUN = ("fertig", "fehlgeschlagen", "laeuft")


@_gesperrt
def lege_aufnahme_an(
    conn: sqlite3.Connection,
    chat_id: int,
    message_id: int,
    klasse: str,
    quelle: str,
    audio_pfad: str | None = None,
    dauer: int | None = None,
    teil_von: int | None = None,
    status: str = "empfangen",
) -> int:
    """Legt eine Aufnahme (Sprache oder Textimport) an.

    Ein Interview-Kopf (``klasse='lang'``) bekommt den Ersatznamen
    'Interview n', wobei n die **laufende Interviewnummer** dieser Gruppe ist
    -- nicht die Zahl aller Aufnahmen (Nachtrag 05.09.2026): ein Interview aus
    fuenf Sprachnachrichten ist ein Interview, und ein Zuruf zwischendurch
    verschiebt die Zaehlung nicht. Teile (``klasse='teil'``) und
    Gespraechsbeitraege (``klasse='kurz'``) bekommen gar keinen Namen: der
    Teil traegt den Namen seines Kopfes, und ein Zuruf ist kein Interview, das
    man beim Namen nennen koennte.

    Startstatus 'empfangen', beim Interview-Kopf 'laeuft'; der Aufrufer
    entscheidet ueber weitere Statusuebergaenge."""
    name = f"Interview {zaehle_interviews(conn, chat_id) + 1}" if klasse == "lang" else None
    cur = conn.execute(
        """
        INSERT INTO aufnahme
            (chat_id, message_id, name, klasse, quelle, audio_pfad,
             dauer_sekunden, status, empfangen_am, teil_von)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (chat_id, message_id, name, klasse, quelle, audio_pfad, dauer, status,
         _jetzt(), teil_von),
    )
    conn.commit()
    return cur.lastrowid


@_gesperrt
def lege_interview_an(conn: sqlite3.Connection, chat_id: int) -> int:
    """Legt den Kopf eines Interviews an (§ 10.6): eine Aufnahme ohne Audio,
    die Name, zusammengefuegtes Transkript und Verdichtung traegt und mit
    ``status='laeuft'`` auf ihre Teile wartet.

    ``message_id = 0``, weil der Kopf an keiner einzelnen Nachricht haengt --
    er entsteht aus dem Moment, in dem die Gruppe den Interviewmodus
    einschaltet, und lebt weiter ueber alle Sprachnachrichten hinweg, die
    danach kommen."""
    return lege_aufnahme_an(conn, chat_id, 0, "lang", "sprache", status="laeuft")


@_gesperrt
def laufendes_interview(conn: sqlite3.Connection, chat_id: int) -> sqlite3.Row | None:
    """Der Interview-Kopf, der gerade Teile einsammelt, oder None.

    Der juengste gewinnt: sollte durch einen Fehlschlag je ein zweiter Kopf
    entstanden sein, gehoert die naechste Sprachnachricht zu dem, den die
    Gruppe gerade meint."""
    return conn.execute(
        "SELECT * FROM aufnahme WHERE chat_id = ? AND klasse = 'lang' "
        "AND teil_von IS NULL AND status = 'laeuft' AND beendet_am IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()


@_gesperrt
def setze_interview_beendet(conn: sqlite3.Connection, aufnahme_id: int) -> None:
    """Stempelt ``beendet_am`` -- die Gruppe hat "fertig" gesagt. Der Status
    bleibt zunaechst 'laeuft': erst wenn alle Teile durch sind, wird
    zusammengefuegt und verdichtet (aufnahme.schliesse_ab)."""
    conn.execute(
        "UPDATE aufnahme SET beendet_am = ? WHERE id = ? AND beendet_am IS NULL",
        (_jetzt(), aufnahme_id),
    )
    conn.commit()


@_gesperrt
def hole_teile(conn: sqlite3.Connection, aufnahme_id: int) -> list[sqlite3.Row]:
    """Die Teile eines Interviews in Eingangsreihenfolge (``id ASC``)."""
    return conn.execute(
        "SELECT * FROM aufnahme WHERE teil_von = ? ORDER BY id ASC", (aufnahme_id,)
    ).fetchall()


@_gesperrt
def teil_nummer(conn: sqlite3.Connection, teil_id: int) -> int:
    """Die laufende Nummer eines Teils innerhalb seines Interviews (1-basiert)
    -- das, was im Chat-Echo als 'Teil 3' steht."""
    zeile = conn.execute("SELECT teil_von FROM aufnahme WHERE id = ?", (teil_id,)).fetchone()
    if zeile is None or zeile["teil_von"] is None:
        return 1
    return conn.execute(
        "SELECT count(*) FROM aufnahme WHERE teil_von = ? AND id <= ?",
        (zeile["teil_von"], teil_id),
    ).fetchone()[0]


@_gesperrt
def hat_offene_teile(conn: sqlite3.Connection, aufnahme_id: int) -> bool:
    """True, solange ein Teil dieses Interviews noch in Arbeit ist (weder
    'fertig' noch 'fehlgeschlagen'). Solange das gilt, wird nicht verdichtet
    -- sonst fehlte im Transkript ausgerechnet der Teil, an dem Whisper gerade
    haengt."""
    zeile = conn.execute(
        "SELECT 1 FROM aufnahme WHERE teil_von = ? "
        "AND status NOT IN ('fertig', 'fehlgeschlagen') LIMIT 1",
        (aufnahme_id,),
    ).fetchone()
    return zeile is not None


#: Leerzeile zwischen zwei Teilen im zusammengefuegten Transkript -- die
#: Sprachnachrichten sind Abschnitte desselben Gespraechs, keine getrennten
#: Interviews.
TEIL_TRENNER = "\n\n"


@_gesperrt
def zusammengefuegtes_transkript(conn: sqlite3.Connection, aufnahme_id: int) -> str:
    """Das ganze Interview als ein Text: die Transkripte aller Teile in
    Reihenfolge, durch eine Leerzeile getrennt.

    Ohne Teile faellt es auf das Transkript am Kopf selbst zurueck -- so
    bleiben Textimporte (§ 10.5) und alle Aufnahmen aus der Zeit vor dieser
    Aenderung lesbar, ohne dass irgendetwas migriert werden muesste."""
    teile = [z["transkript"] for z in hole_teile(conn, aufnahme_id) if z["transkript"]]
    if teile:
        return TEIL_TRENNER.join(teile)
    zeile = conn.execute(
        "SELECT transkript FROM aufnahme WHERE id = ?", (aufnahme_id,)
    ).fetchone()
    return (zeile["transkript"] if zeile else None) or ""


@_gesperrt
def dauer_gesamt(conn: sqlite3.Connection, aufnahme_id: int) -> int | None:
    """Die Gesamtdauer eines Interviews in Sekunden: die Summe seiner Teile,
    ersatzweise die Dauer am Kopf selbst (Textimport oder eine Aufnahme aus
    der Zeit vor § 10.6).

    Gebraucht fuer die Zeile, mit der ein sehr kurzes Interview abgelehnt
    wird ("Interview 3 ist sehr kurz (4 s, 10 Woerter)", Nachtrag N2): die
    Gruppe soll an der Zahl erkennen, welche Aufnahme gemeint ist."""
    zeile = conn.execute(
        "SELECT sum(dauer_sekunden) AS dauer FROM aufnahme WHERE teil_von = ?",
        (aufnahme_id,),
    ).fetchone()
    if zeile is not None and zeile["dauer"]:
        return zeile["dauer"]
    eigene = conn.execute(
        "SELECT dauer_sekunden FROM aufnahme WHERE id = ?", (aufnahme_id,)
    ).fetchone()
    return eigene["dauer_sekunden"] if eigene else None


@_gesperrt
def hole_aufnahme(conn: sqlite3.Connection, aufnahme_id: int) -> sqlite3.Row | None:
    """Liefert die aufnahme-Zeile oder None, wenn unbekannt."""
    return conn.execute(
        "SELECT * FROM aufnahme WHERE id = ?", (aufnahme_id,)
    ).fetchone()


@_gesperrt
def setze_status(
    conn: sqlite3.Connection, aufnahme_id: int, status: str, fehlertext: str | None = None
) -> None:
    """Setzt Status (und ggf. Fehlertext) einer Aufnahme."""
    conn.execute(
        "UPDATE aufnahme SET status = ?, fehlertext = ? WHERE id = ?",
        (status, fehlertext, aufnahme_id),
    )
    conn.commit()


@_gesperrt
def setze_transkript(conn: sqlite3.Connection, aufnahme_id: int, text: str) -> None:
    """Traegt das Transkript einer Aufnahme ein."""
    conn.execute(
        "UPDATE aufnahme SET transkript = ? WHERE id = ?", (text, aufnahme_id)
    )
    conn.commit()


@_gesperrt
def setze_aufnahme_name(conn: sqlite3.Connection, aufnahme_id: int, name: str) -> None:
    """Ersetzt den (ggf. automatisch vergebenen) Namen einer Aufnahme."""
    conn.execute(
        "UPDATE aufnahme SET name = ? WHERE id = ?", (name, aufnahme_id)
    )
    conn.commit()


@_gesperrt
def loese_aus_interview(conn: sqlite3.Connection, aufnahme_id: int) -> None:
    """Macht aus einem Interview-Teil einen Gespraechsbeitrag (Nachtrag N4):
    ``klasse='kurz'``, ``teil_von`` zurueck auf NULL.

    Der Fall: die Gruppe spricht mitten im Interviewmodus eine Nachricht an
    den BOT ein ("zeig mir die Verdichtungen"), nicht an die interviewte
    Person. Ohne diesen Weg landete sie als Teil im Interviewtranskript und
    spaeter in der Verdichtung -- und beantwortet wuerde sie nie.

    Nur diese beiden Felder: die Audiodatei, das Transkript und die
    Nachrichtenzeile bleiben, wo sie sind. Zurueckdrehen laesst sich das nicht
    -- der Erkennerlauf, der hierher fuehrt, ist deshalb auf 'im Zweifel
    Material' kalibriert (prompts/erkenner.md)."""
    conn.execute(
        "UPDATE aufnahme SET klasse = 'kurz', teil_von = NULL WHERE id = ?",
        (aufnahme_id,),
    )
    conn.commit()


@_gesperrt
def offene_aufnahmen(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Alle Aufnahmen, an denen noch Arbeit offen ist -- Grundlage dafuer, dass
    ein Neustart ueber Nacht angefangene Arbeit zu Ende bringt
    (Nachhol-Arbeiter, Aufgabe 8). Ueber alle Gruppen hinweg, absichtlich
    ohne chat_id-Filter.

    Ein laufendes Interview (``status='laeuft'``) gehoert nicht dazu: es
    sammelt gerade noch Teile ein (siehe _NICHTS_ZU_TUN)."""
    return conn.execute(
        f"SELECT * FROM aufnahme WHERE status NOT IN {_NICHTS_ZU_TUN} ORDER BY id ASC"
    ).fetchall()


@_gesperrt
def zaehle_aufnahmen(conn: sqlite3.Connection, chat_id: int) -> int:
    """Anzahl der Aufnahmen einer Gruppe, unabhaengig vom Status -- alle
    Zeilen, also auch Teile und Gespraechsbeitraege."""
    return conn.execute(
        "SELECT count(*) FROM aufnahme WHERE chat_id = ?", (chat_id,)
    ).fetchone()[0]


@_gesperrt
def zaehle_interviews(conn: sqlite3.Connection, chat_id: int) -> int:
    """Anzahl der Interviews einer Gruppe -- nur die Koepfe, unabhaengig vom
    Status. Grundlage der Namensvergabe 'Interview n' (lege_aufnahme_an)."""
    return conn.execute(
        "SELECT count(*) FROM aufnahme WHERE chat_id = ? AND klasse = 'lang' "
        "AND teil_von IS NULL",
        (chat_id,),
    ).fetchone()[0]


@_gesperrt
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
    'zitat_geprueft' (0 oder 1); 'kurz' (die Kurzform aus N3/N6) ist
    optional und faellt sonst auf 'thema' zurueck."""
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
                (chat_id, verdichtung_id, thema, kurz, beleg_zitat, zitat_geprueft)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                verdichtung_id,
                thema["thema"],
                thema.get("kurz") or thema["thema"],
                thema["beleg_zitat"],
                thema["zitat_geprueft"],
            ),
        )
    conn.commit()
    return verdichtung_id


@_gesperrt
def verdichtungen(conn: sqlite3.Connection, chat_id: int) -> list[sqlite3.Row]:
    """Alle Verdichtungen einer Gruppe, in Entstehungsreihenfolge."""
    return conn.execute(
        "SELECT * FROM verdichtung WHERE chat_id = ? ORDER BY id ASC", (chat_id,)
    ).fetchall()


@_gesperrt
def hole_verdichtung(conn: sqlite3.Connection, verdichtung_id: int) -> sqlite3.Row | None:
    """Eine einzelne Verdichtung -- Grundlage der Rueckmeldung in den Chat,
    wenn ein Interview durch ist (aufnahme._verdichtungstext)."""
    return conn.execute(
        "SELECT * FROM verdichtung WHERE id = ?", (verdichtung_id,)
    ).fetchone()


@_gesperrt
def verdichtung_zu_aufnahme(
    conn: sqlite3.Connection, aufnahme_id: int
) -> sqlite3.Row | None:
    """Die (juengste) Verdichtung einer Aufnahme, oder None, solange keine
    existiert.

    Grundlage von ``/auswerten`` (Nachtrag N2): ein Interview, das schon
    ausgewertet ist, wird nicht ein zweites Mal verdichtet -- das waere ein
    zweiter bezahlter Aufruf und eine zweite Verdichtung derselben Aufnahme
    im Prompt."""
    return conn.execute(
        "SELECT * FROM verdichtung WHERE aufnahme_id = ? ORDER BY id DESC LIMIT 1",
        (aufnahme_id,),
    ).fetchone()


@_gesperrt
def themen_zu(conn: sqlite3.Connection, verdichtung_id: int) -> list[sqlite3.Row]:
    """Die Kernthemen einer Verdichtung, in der vom Sprachmodell gelieferten
    Reihenfolge."""
    return conn.execute(
        "SELECT * FROM verdichtung_thema WHERE verdichtung_id = ? ORDER BY id ASC",
        (verdichtung_id,),
    ).fetchall()


@_gesperrt
def transkripte(
    conn: sqlite3.Connection, chat_id: int, name: str | None = None
) -> list[sqlite3.Row]:
    """Aufnahmen einer Gruppe -- **ohne die Teile** eines Interviews
    (``teil_von IS NULL``, § 10.6): nach aussen ist ein Interview eine
    Einheit, und wer hier zaehlt, benennt oder auflistet, meint diese Einheit
    und nicht die fuenf Sprachnachrichten, aus denen sie besteht.

    Bei gesetztem ``name`` wird grosszuegig gesucht (Gross-/Kleinschreibung
    egal, Teiltreffer genuegt) statt exakt zu vergleichen -- die Gruppe tippt
    Namen nicht immer gleich."""
    zeilen = conn.execute(
        "SELECT * FROM aufnahme WHERE chat_id = ? AND teil_von IS NULL ORDER BY id ASC",
        (chat_id,),
    ).fetchall()
    if name is None:
        return zeilen
    gesucht = name.lower()
    return [z for z in zeilen if z["name"] and gesucht in z["name"].lower()]


@_gesperrt
def hole_nachricht(conn: sqlite3.Connection, chat_id: int, message_id: int) -> sqlite3.Row | None:
    """Liefert eine einzelne Nachrichtenzeile oder None (Aufgabe 8: die
    Aufnahme-Pipeline braucht gesendet_am der urspruenglichen Sprachnachricht,
    um zu entscheiden, ob ein fertiges Transkript noch jung genug ist, um
    einen Gespraechszug auszuloesen)."""
    return conn.execute(
        "SELECT * FROM nachricht WHERE chat_id = ? AND message_id = ?",
        (chat_id, message_id),
    ).fetchone()


@_gesperrt
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


@_gesperrt
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


@_gesperrt
def setze_whisper_stumm_seit(conn: sqlite3.Connection, chat_id: int, wert: str | None) -> None:
    """Setzt oder leert gruppe.whisper_stumm_seit (Aufgabe 8, SPEC § 10.4):
    gesetzt bedeutet, der einmalige Ausfall-Hinweis wurde schon geschickt und
    weitere Fehlschlaege bleiben still, bis die Rueckkehr gemeldet wird."""
    conn.execute(
        "UPDATE gruppe SET whisper_stumm_seit = ? WHERE chat_id = ?", (wert, chat_id)
    )
    conn.commit()


@_gesperrt
def offene_aufnahmen_fuer_bot(conn: sqlite3.Connection, bot_name: str) -> list[sqlite3.Row]:
    """Wie offene_aufnahmen(), aber auf die Gruppen eingeschraenkt, die dieser
    Bot-Prozess bedient (gruppe.bot_name). Grundlage der Nebenlaeufigkeits-
    Absicherung des Nachhol-Arbeiters (Aufgabe 8, Auftragshinweis 3): es laeuft
    ein Prozess je Gruppe, alle auf derselben SQLite-Datei, und
    offene_aufnahmen() filtert absichtlich nicht nach chat_id (Aufgabe 7).
    Ohne diese Einschraenkung wuerden zwei Prozesse dieselbe Aufnahme
    gleichzeitig zu Whisper hochladen."""
    return conn.execute(
        f"""
        SELECT a.* FROM aufnahme a
        JOIN gruppe g ON g.chat_id = a.chat_id
        WHERE g.bot_name = ? AND a.status NOT IN {_NICHTS_ZU_TUN}
        ORDER BY a.id ASC
        """,
        (bot_name,),
    ).fetchall()


@_gesperrt
def beendete_offene_interviews(conn: sqlite3.Connection, bot_name: str) -> list[sqlite3.Row]:
    """Interviews, die die Gruppe fuer beendet erklaert hat, deren Teile aber
    noch nicht alle durch waren (§ 10.6) -- die zweite Haelfte des
    Nachhol-Arbeiters.

    Sie stehen weiter auf ``status='laeuft'`` und werden deshalb von
    ``offene_aufnahmen_fuer_bot`` bewusst nicht mitgeliefert: dort wuerde ein
    noch unvollstaendiges Interview verdichtet. Hier werden sie gesondert
    aufgegriffen, und ``aufnahme.schliesse_ab`` entscheidet, ob es schon
    soweit ist."""
    return conn.execute(
        """
        SELECT a.* FROM aufnahme a
        JOIN gruppe g ON g.chat_id = a.chat_id
        WHERE g.bot_name = ? AND a.klasse = 'lang' AND a.teil_von IS NULL
          AND a.status = 'laeuft' AND a.beendet_am IS NOT NULL
        ORDER BY a.id ASC
        """,
        (bot_name,),
    ).fetchall()


@_gesperrt
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


@_gesperrt
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


#: Die einzigen Felder, die ein Korrekturbefehl (SPEC § 8: /kernthema,
#: /konflikt, /begriffe) oder der Extraktor im Arbeitsstand setzen duerfen.
#: ``fragen`` ist seit dem 04.09.2026 abends dabei (die Frageliste aus Phase 2,
#: Erkenner-art ``fragen_setzen``).
_ARBEITSSTAND_FELDER = (
    "begriffe", "fragen", "kernthema", "kernthema_begruendung", "hauptkonflikt",
)


@_gesperrt
def hole_arbeitsstand(conn: sqlite3.Connection, chat_id: int) -> sqlite3.Row | None:
    """Liefert die arbeitsstand-Zeile einer Gruppe oder None, solange noch
    keine einzige Entscheidung getroffen wurde (Aufgabe 9, Schicht 2)."""
    return conn.execute(
        "SELECT * FROM arbeitsstand WHERE chat_id = ?", (chat_id,)
    ).fetchone()


@_gesperrt
def setze_arbeitsstand(
    conn: sqlite3.Connection, chat_id: int, feld: str, wert: str | None
) -> None:
    """Setzt (oder ueberschreibt) genau ein Feld des Arbeitsstands.

    Nur die vier Felder aus _ARBEITSSTAND_FELDER duerfen so gesetzt werden --
    alles andere ist ein Programmierfehler, kein Bedienfehler, daher
    ValueError statt eines stillen No-Ops. ``feld`` landet nur nach dieser
    Pruefung im SQL-Text, ist also nie ein Injection-Risiko.

    ``wert=None`` leert das Feld -- so wird ein Arbeitsstandfeld "entfernt"
    (NACHTRAG-weboberflaeche-und-sprache.md N3). Ein Zeitstempel wie bei
    Figuren und Szenen braucht es hier nicht: das Feld hat nur einen Wert,
    und der Weg dorthin steht im Journal."""
    if feld not in _ARBEITSSTAND_FELDER:
        raise ValueError(f"unbekanntes Arbeitsstand-Feld: {feld!r}")
    conn.execute(
        f"""
        INSERT INTO arbeitsstand (chat_id, {feld}, geaendert_am)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            {feld} = excluded.{feld},
            geaendert_am = excluded.geaendert_am
        """,
        (chat_id, wert, _jetzt()),
    )
    conn.commit()


@_gesperrt
def hole_phase(conn: sqlite3.Connection, chat_id: int) -> int | None:
    """Die gespeicherte Arbeitsphase (1-7) oder None, wenn noch keine gesetzt
    wurde (interview_theater/phasen.py, SPEC § 0 Leitsatz 3 Nachtrag).

    Liefert absichtlich den rohen Wert samt None -- 'noch nie gesetzt' ist
    etwas anderes als 'ausdruecklich auf 1 gesetzt', auch wenn der Bot beides
    gleich behandelt (``phasen.aktuelle``)."""
    zeile = conn.execute(
        "SELECT phase FROM arbeitsstand WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return zeile["phase"] if zeile else None


@_gesperrt
def setze_phase(conn: sqlite3.Connection, chat_id: int, nummer: int) -> None:
    """Setzt die Arbeitsphase. Anlegen oder ueberschreiben, wie
    setze_arbeitsstand -- nur mit einer eigenen Funktion, weil ``phase``
    INTEGER ist und nicht zu den vier Textfeldern gehoert, die ein
    Korrekturbefehl setzen darf."""
    conn.execute(
        """
        INSERT INTO arbeitsstand (chat_id, phase, geaendert_am)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            phase = excluded.phase,
            geaendert_am = excluded.geaendert_am
        """,
        (chat_id, nummer, _jetzt()),
    )
    conn.commit()


@_gesperrt
def hole_phase_angeboten(conn: sqlite3.Connection, chat_id: int) -> int | None:
    """Die zuletzt angebotene Phase (siehe setze_phase_angeboten)."""
    zeile = conn.execute(
        "SELECT phase_angeboten FROM arbeitsstand WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return zeile["phase_angeboten"] if zeile else None


@_gesperrt
def setze_phase_angeboten(conn: sqlite3.Connection, chat_id: int, nummer: int) -> None:
    """Merkt, welchen Phasenwechsel der Bot der Gruppe zuletzt angeboten hat.

    Ohne dieses Feld stuende der Hinweisblock aus ``kontext.baue`` in jedem
    Zug erneut im Prompt, und der Bot boete denselben Wechsel jedes Mal von
    Neuem an -- ein Angebot, das sich alle zwei Minuten wiederholt, ist
    Draengeln. Es ist kein Wartezustand: der Bot laeuft weiter, egal ob die
    Gruppe antwortet."""
    conn.execute(
        """
        INSERT INTO arbeitsstand (chat_id, phase_angeboten, geaendert_am)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            phase_angeboten = excluded.phase_angeboten,
            geaendert_am = excluded.geaendert_am
        """,
        (chat_id, nummer, _jetzt()),
    )
    conn.commit()


@_gesperrt
def figuren(conn: sqlite3.Connection, chat_id: int) -> list[sqlite3.Row]:
    """Alle noch vorhandenen Figuren einer Gruppe, in Entstehungsreihenfolge
    (Aufgabe 9). Weich geloeschte Figuren (``entfernt_am`` gesetzt, N3)
    bleiben in der Tabelle stehen, aber aus jeder Ansicht und aus jedem
    Prompt draussen."""
    return conn.execute(
        "SELECT * FROM figur WHERE chat_id = ? AND entfernt_am IS NULL ORDER BY id ASC",
        (chat_id,),
    ).fetchall()


@_gesperrt
def entferne_figur(conn: sqlite3.Connection, chat_id: int, name: str) -> str | None:
    """Entfernt eine Figur weich (NACHTRAG N3) und liefert ihren gespeicherten
    Namen zurueck, oder None, wenn es sie nicht (mehr) gibt.

    Namensvergleich wie in setze_figur: getrimmt und kleingeschrieben, aber
    kein Teiltreffer -- 'Peter' soll nicht 'Peters Mutter' loeschen. Nicht
    gefunden ist kein Fehler, sondern ein stilles No-Op: die Gruppe soll fuer
    einen Namen, den sie nur beilaeufig genannt hat, keine Fehlermeldung
    bekommen."""
    name = name.strip()
    zeile = conn.execute(
        "SELECT id, name FROM figur "
        "WHERE chat_id = ? AND lower(trim(name)) = ? AND entfernt_am IS NULL",
        (chat_id, name.lower()),
    ).fetchone()
    if zeile is None:
        return None
    conn.execute(
        "UPDATE figur SET entfernt_am = ? WHERE id = ?", (_jetzt(), zeile["id"])
    )
    conn.commit()
    return zeile["name"]


@_gesperrt
def setze_figur(conn: sqlite3.Connection, chat_id: int, name: str, beschreibung: str) -> None:
    """Legt eine Figur an oder ueberschreibt ihre Beschreibung, wenn der Name
    schon existiert (SPEC § 8: /figur legt an oder ueberschreibt; teil-b.md
    Aufgabe 3: der Absichtserkenner ruft dies ebenso auf). Vergleich nach
    Trimmen und Kleinschreibung, damit ' maria ' und 'Maria' dieselbe Figur
    treffen -- weder die Gruppe noch das Modell tippen Namen immer gleich,
    aber ein Figurenname ist trotzdem eine bewusste Entscheidung, kein
    Tippfehler-Suchproblem wie bei transkripte() (dort genuegt ein
    Teiltreffer, hier nicht)."""
    name = name.strip()
    beschreibung = (beschreibung or "").strip()
    vorhanden = conn.execute(
        "SELECT id FROM figur WHERE chat_id = ? AND lower(trim(name)) = ?",
        (chat_id, name.lower()),
    ).fetchone()
    jetzt = _jetzt()
    if vorhanden:
        conn.execute(
            "UPDATE figur SET beschreibung = ?, geaendert_am = ? WHERE id = ?",
            (beschreibung, jetzt, vorhanden["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO figur (chat_id, name, beschreibung, geaendert_am) VALUES (?, ?, ?, ?)",
            (chat_id, name, beschreibung, jetzt),
        )
    conn.commit()


@_gesperrt
def lege_szene_an(
    conn: sqlite3.Connection,
    chat_id: int,
    nummer: int | None,
    titel: str | None,
    kurzbeschreibung: str | None,
    volltext: str | None,
) -> int:
    """Legt eine Szene an und liefert die neue id (SPEC § 3.1, § 6.2 Block 4/5).

    Anders als eine Verdichtung darf eine Szene ausdruecklich geaendert werden
    -- deshalb gibt es hier, im Unterschied zu ``speichere_verdichtung``, ein
    Gegenstueck ``aktualisiere_szene``. Ein Szenentext ist ein Entwurf, der
    ueberarbeitet wird; eine Verdichtung ist ein Befund, der stehen bleibt."""
    cur = conn.execute(
        """
        INSERT INTO szene (chat_id, nummer, titel, kurzbeschreibung, volltext, geaendert_am)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (chat_id, nummer, titel, kurzbeschreibung, volltext, _jetzt_genau()),
    )
    conn.commit()
    return cur.lastrowid


@_gesperrt
def aktualisiere_szene(
    conn: sqlite3.Connection,
    szene_id: int,
    titel: str | None,
    kurzbeschreibung: str | None,
    volltext: str | None,
) -> None:
    """Ueberschreibt eine Szene vollstaendig und setzt ``geaendert_am`` neu.

    ``geaendert_am`` ist nicht bloss Buchhaltung: es entscheidet, welche Szene
    als 'die aktuelle' in den Gespraechs-Prompt wandert (hole_letzte_szene,
    SPEC § 6.2 Block 5). Wer eine Szene ueberarbeitet, macht sie damit
    automatisch wieder zur aktuellen -- genau das datengetriebene Verhalten,
    das § 6.1 beschreibt."""
    conn.execute(
        """
        UPDATE szene SET titel = ?, kurzbeschreibung = ?, volltext = ?, geaendert_am = ?
        WHERE id = ?
        """,
        (titel, kurzbeschreibung, volltext, _jetzt_genau(), szene_id),
    )
    conn.commit()


@_gesperrt
def hole_szenen(conn: sqlite3.Connection, chat_id: int) -> list[sqlite3.Row]:
    """Alle Szenen einer Gruppe, nach Szenennummer sortiert (SPEC § 6.2 Block 4:
    die Szenenliste im Arbeitsstand). Eine Szene ohne Nummer sortiert in SQLite
    nach vorn -- im Normalbetrieb vergibt ``interview_theater.szene`` immer eine, der
    Fall bleibt nur als Datenbankmoeglichkeit bestehen."""
    return conn.execute(
        "SELECT * FROM szene WHERE chat_id = ? AND entfernt_am IS NULL "
        "ORDER BY nummer ASC, id ASC",
        (chat_id,),
    ).fetchall()


@_gesperrt
def entferne_szene(conn: sqlite3.Connection, chat_id: int, nummer: int) -> int | None:
    """Entfernt die Szene mit dieser Nummer weich (NACHTRAG N3) und liefert
    ihre Nummer zurueck, oder None, wenn es sie nicht (mehr) gibt.

    Gibt es (durch eine Nummernvergabe von Hand) mehrere Szenen mit derselben
    Nummer, trifft es die zuletzt geaenderte -- das ist die, die die Gruppe
    gerade vor Augen hat (dieselbe Regel wie hole_letzte_szene)."""
    zeile = conn.execute(
        "SELECT id, nummer FROM szene "
        "WHERE chat_id = ? AND nummer = ? AND entfernt_am IS NULL "
        "ORDER BY geaendert_am DESC, id DESC LIMIT 1",
        (chat_id, nummer),
    ).fetchone()
    if zeile is None:
        return None
    conn.execute(
        "UPDATE szene SET entfernt_am = ? WHERE id = ?", (_jetzt(), zeile["id"])
    )
    conn.commit()
    return zeile["nummer"]


@_gesperrt
def hole_letzte_szene(conn: sqlite3.Connection, chat_id: int) -> sqlite3.Row | None:
    """Die zuletzt geaenderte Szene einer Gruppe, oder None (SPEC § 6.2 Block 5,
    dort woertlich als ``ORDER BY geaendert_am DESC LIMIT 1`` vorgegeben).

    ``geaendert_am`` ist hier mikrosekundengenau (``_jetzt_genau``, siehe
    dort): sekundengenau waeren zwei Schreibvorgaenge derselben Sekunde nicht
    unterscheidbar. ``id DESC`` bleibt als letzter Notnagel dahinter."""
    return conn.execute(
        "SELECT * FROM szene WHERE chat_id = ? AND entfernt_am IS NULL "
        "ORDER BY geaendert_am DESC, id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()


@_gesperrt
def journal(conn: sqlite3.Connection, chat_id: int) -> list[sqlite3.Row]:
    """Alle noch geltenden Journaleintraege einer Gruppe, aeltester zuerst
    (SPEC § 6.2 zu Block 6). Das Journal ist nur-anhaengend -- es gibt
    bewusst kein aktualisiere_journal(); auch das weiche Loeschen (N3) aendert
    keinen Text, es stempelt ``entfernt_am`` und haengt eine neue Zeile
    'Zurueckgenommen: ...' an (siehe entferne_journal)."""
    return conn.execute(
        "SELECT * FROM journal WHERE chat_id = ? AND entfernt_am IS NULL ORDER BY id ASC",
        (chat_id,),
    ).fetchall()


@_gesperrt
def entferne_journal(conn: sqlite3.Connection, chat_id: int, suchtext: str) -> str | None:
    """Entfernt einen Journaleintrag weich und liefert seinen Text zurueck,
    oder None, wenn keiner passt.

    Gesucht wird grosszuegig (Teiltreffer, Gross-/Kleinschreibung egal, wie
    ``transkripte``): die Gruppe sagt 'nimm die Kindheitsfragen wieder raus',
    nicht den vollen Eintragstext samt Begruendung. Passen mehrere, trifft es
    den juengsten -- der ist der wahrscheinlich gemeinte."""
    suchtext = suchtext.strip()
    if not suchtext:
        return None
    # Der Teiltreffer wird in Python gebildet, nicht als LIKE-Muster: ein '%'
    # oder '_' im Suchtext waere dort ein Platzhalter und truebe etwas ganz
    # anderes (dieselbe Ueberlegung wie in transkripte()).
    gesucht = suchtext.lower()
    zeile = next(
        (
            z
            for z in conn.execute(
                "SELECT id, text FROM journal "
                "WHERE chat_id = ? AND entfernt_am IS NULL ORDER BY id DESC",
                (chat_id,),
            )
            if gesucht in (z["text"] or "").lower()
        ),
        None,
    )
    if zeile is None:
        return None
    conn.execute(
        "UPDATE journal SET entfernt_am = ? WHERE id = ?", (_jetzt(), zeile["id"])
    )
    conn.commit()
    return zeile["text"]


@_gesperrt
def schreibe_journal(
    conn: sqlite3.Connection,
    chat_id: int,
    art: str,
    text: str,
    quelle: str,
    bis_message_id: int | None = None,
) -> int:
    """Haengt einen Journaleintrag an (art: vorgeschlagen|verworfen|
    entschieden|offen; quelle: extraktor|befehl). Liefert die neue id."""
    cur = conn.execute(
        """
        INSERT INTO journal (chat_id, art, text, quelle, bis_message_id, erstellt_am)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (chat_id, art, text, quelle, bis_message_id, _jetzt()),
    )
    conn.commit()
    return cur.lastrowid


@_gesperrt
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


@_gesperrt
def setze_interviewmodus(conn: sqlite3.Connection, chat_id: int, wert: str | None) -> None:
    """Setzt oder leert gruppe.interviewmodus_seit (teil-b.md Aufgabe 5, SPEC
    § 10.1): ein Zeitstempel bedeutet 'Modus an', NULL bedeutet 'Modus aus'.
    Ueberlebt einen Neustart, weil es in der Datenbank steht -- anders als
    ein Prozessspeicher-Flag. Wird sowohl vom Absichtserkenner (art
    interview_starten/interview_beenden) als auch spaeter von /interview und
    /fertig aufgerufen."""
    conn.execute(
        "UPDATE gruppe SET interviewmodus_seit = ? WHERE chat_id = ?", (wert, chat_id)
    )
    conn.commit()


@_gesperrt
def ist_interviewmodus_an(conn: sqlite3.Connection, chat_id: int) -> bool:
    """Liefert True, wenn der Interviewmodus dieser Gruppe an ist (teil-b.md
    Aufgabe 5) -- Grundlage von aufnahme.klasse_fuer(). Eine unbekannte
    Gruppe zaehlt als 'Modus aus', analog zu den anderen Schaltern."""
    gruppe = hole_gruppe(conn, chat_id)
    return gruppe is not None and gruppe["interviewmodus_seit"] is not None


@_gesperrt
def hat_bot_nachricht(conn: sqlite3.Connection, chat_id: int) -> bool:
    """Liefert True, wenn diese Gruppe schon mindestens eine Bot-Nachricht
    hat (teil-b.md Aufgabe 7) -- Grundlage dafuer, dass ``bot.erstkontakt``
    die Begruessung genau einmal je Gruppe schickt."""
    zeile = conn.execute(
        "SELECT 1 FROM nachricht WHERE chat_id = ? AND ist_bot = 1 LIMIT 1", (chat_id,)
    ).fetchone()
    return zeile is not None


@_gesperrt
def letzte_nachricht_zeit(conn: sqlite3.Connection, chat_id: int) -> str | None:
    """Liefert ``gesendet_am`` der zeitlich juengsten Nachricht einer Gruppe
    (gleich welcher Art), oder None ohne jede Nachricht -- Grundlage fuer
    ``bot.begruessung_faellig`` (teil-b.md Aufgabe 7)."""
    zeile = conn.execute(
        "SELECT gesendet_am FROM nachricht WHERE chat_id = ? "
        "ORDER BY message_id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()
    return zeile["gesendet_am"] if zeile else None


@_gesperrt
def gruppen_fuer_bot(conn: sqlite3.Connection, bot_name: str) -> list[sqlite3.Row]:
    """Alle Gruppen dieses Bot-Prozesses (teil-b.md Aufgabe 7) -- Grundlage
    fuer die Wiederkehr-Begruessung beim Neustart nach einer langen Pause."""
    return conn.execute(
        "SELECT * FROM gruppe WHERE bot_name = ?", (bot_name,)
    ).fetchall()


@_gesperrt
def setze_wortlaut_modus(conn: sqlite3.Connection, chat_id: int, wert: str | None) -> None:
    """Setzt oder leert gruppe.wortlaut_modus (SPEC § 8 /wortlaut, teil-b.md
    Aufgabe 3): NULL=aus, '*'=alle, sonst ein Aufnahmename. Wird sowohl vom
    /wortlaut-Befehl als auch vom Absichtserkenner (art wortlaut_an/
    wortlaut_aus) aufgerufen."""
    conn.execute(
        "UPDATE gruppe SET wortlaut_modus = ? WHERE chat_id = ?", (wert, chat_id)
    )
    conn.commit()


@_gesperrt
def unjournalisierte(conn: sqlite3.Connection, chat_id: int) -> list[sqlite3.Row]:
    """Nachrichten seit dem Journal-Wasserzeichen letzte_journalisierte_message_id
    (interview_theater/journal.py) -- der Kandidatenpool, aus dem der
    Journal-Extraktor den tatsaechlich verdraengten Abschnitt herausrechnet.

    Wie unextrahierte() gefiltert: weder ist_bot noch unterdrueckt schraenken
    ein, die Transkript-Echos (TYP_TRANSKRIPT) fallen weg -- damit
    journal.berechne_verdraengten_abschnitt() dieselbe Nachrichtenfolge sieht
    wie kontext.baue() beim Fensteraufbau."""
    return conn.execute(
        f"""
        SELECT n.* FROM nachricht n
        JOIN gruppe g ON g.chat_id = n.chat_id
        WHERE n.chat_id = ?
          AND n.message_id > g.letzte_journalisierte_message_id
          AND {_OHNE_TRANSKRIPT_ECHO}
        ORDER BY n.message_id ASC
        """,
        (chat_id,),
    ).fetchall()


@_gesperrt
def setze_journalisiert_bis(conn: sqlite3.Connection, chat_id: int, message_id: int) -> None:
    """Setzt das Wasserzeichen letzte_journalisierte_message_id. Bewegt sich
    nie rueckwaerts (analog setze_extrahiert_bis) -- rueckt nur bis zum Ende
    des tatsaechlich verarbeiteten verdraengten Abschnitts vor, nicht bis zum
    Ende aller unjournalisierten Nachrichten (der Rest steht noch im Fenster
    und ist noch nicht verdraengt)."""
    conn.execute(
        """
        UPDATE gruppe SET letzte_journalisierte_message_id = ?
        WHERE chat_id = ? AND letzte_journalisierte_message_id < ?
        """,
        (message_id, chat_id, message_id),
    )
    conn.commit()
