"""Lesezugriffe der Weboberflaeche: Verbindung rein, Dicts raus.

Reine Funktionen ohne HTTP -- ``interview_theater/web.py`` macht daraus HTML, die
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
    solange die Datei ueberhaupt existiert -- ein Tippfehler in IT_DB gibt
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


def _feld(zeile: sqlite3.Row | None, name: str):
    """Liest eine Spalte, die es vielleicht noch nicht gibt.

    Die Weboberflaeche oeffnet read-only und migriert nichts -- die Spalten
    legt der Bot an (``db.initialisiere``). Zwischen einem Deploy und dem
    Neustart des Bots kann der Webserver also auf eine Datenbank ohne die
    neue Spalte sehen; ``sqlite3.Row`` wirft dann IndexError. Eine fehlende
    Spalte ist hier kein Fehler, sondern schlicht 'noch kein Wert'."""
    if zeile is None:
        return None
    try:
        return zeile[name]
    except IndexError:
        return None


def _arbeitsstand(conn: sqlite3.Connection, chat_id: int) -> dict:
    """Die Arbeitsstandfelder, immer als Dict -- auch wenn die Gruppe noch
    keine einzige Entscheidung getroffen hat und die Zeile fehlt.

    ``phase`` kommt roh heraus (``None``, solange keine gesetzt wurde) --
    dass eine ungesetzte Phase wie 1 gilt, ist eine Anzeigeregel und steht
    in ``web.py``, nicht hier.

    ``phase``, ``fragen``, ``format`` und ``rahmen`` gehen ueber ``_feld``:
    alle sind nachtraeglich dazugekommen, und der Webserver sieht die
    Datenbank read-only -- zwischen einem Deploy und dem Neustart des Bots
    kann die Spalte noch fehlen."""
    zeile = conn.execute(
        "SELECT * FROM arbeitsstand WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return {
        "phase": _feld(zeile, "phase"),
        "begriffe": zeile["begriffe"] if zeile else None,
        "fragen": _feld(zeile, "fragen"),
        # Die Verfeinerungsebene der Fragen (06.09.2026): Einleitungen zu
        # heiklen Fragen, Eroeffnung und Abschluss. Alle drei ueber ``_feld``,
        # weil sie nachtraeglich dazugekommen sind und der Webserver die
        # Datenbank read-only sieht -- zwischen Deploy und Bot-Neustart kann
        # die Spalte noch fehlen.
        "frage_einleitungen": _feld(zeile, "frage_einleitungen"),
        "interview_eroeffnung": _feld(zeile, "interview_eroeffnung"),
        "interview_abschluss": _feld(zeile, "interview_abschluss"),
        "kernthema": zeile["kernthema"] if zeile else None,
        "kernthema_begruendung": zeile["kernthema_begruendung"] if zeile else None,
        "format": _feld(zeile, "format"),
        "rahmen": _feld(zeile, "rahmen"),
        "hauptkonflikt": zeile["hauptkonflikt"] if zeile else None,
        "geaendert_am": zeile["geaendert_am"] if zeile else None,
    }


#: Weiches Loeschen (NACHTRAG N3): entfernte Zeilen bleiben in der Datenbank
#: stehen, aber aus jeder Ansicht draussen -- die Weboberflaeche zeigt, was
#: gilt, nicht die Historie. Als Konstante, damit die vier Abfragen unten
#: nicht auseinanderlaufen.
_NICHT_ENTFERNT = "entfernt_am IS NULL"


#: Trennzeichen zwischen den Zitaten einer Figur (``figur.zitate``) -- muss
#: mit ``repo.ZITAT_TRENNER`` uebereinstimmen. Bewusst hier noch einmal und
#: nicht importiert: ``web_daten`` haengt an keiner Schreibschicht, und ein
#: Import von ``repo`` zoege dessen modulweiten Lock in den Webprozess.
ZITAT_TRENNER = " | "


def _figuren(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """Die Figuren der Gruppe -- seit dem 05.09.2026 samt Sprachprofil,
    woertlichen Zitaten und dem Interview, aus dem sie stammen.

    Die Zitate sind geprueft, bevor sie gespeichert werden
    (``sprachprofil.erstelle``), stehen hier also unter derselben Zusage wie
    die Belegzitate der Verdichtungen: kein Satz in Anfuehrungszeichen, den
    niemand gesagt hat.

    Alle drei Spalten gehen ueber ``_feld``: sie sind nachtraeglich
    dazugekommen, und der Webserver sieht die Datenbank read-only."""
    figuren = []
    try:
        zeilen = conn.execute(
            f"SELECT * FROM figur WHERE chat_id = ? AND {_NICHT_ENTFERNT} ORDER BY id ASC",
            (chat_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    for z in zeilen:
        quelle_id = _feld(z, "quelle_aufnahme_id")
        quelle = None
        if quelle_id is not None:
            # "Interview 2", nie der Aufnahmename (Klarname / Telegram-Name).
            from interview_theater import kontext
            quelle = kontext.interviewbezeichnung(conn, chat_id, quelle_id) or None
        zitate = _feld(z, "zitate") or ""
        figuren.append({
            "name": z["name"],
            "beschreibung": z["beschreibung"],
            "sprachprofil": _feld(z, "sprachprofil"),
            "zitate": [s.strip() for s in zitate.split(ZITAT_TRENNER) if s.strip()],
            "quelle": quelle,
        })
    return figuren


def _aufnahmen_nach_status(conn: sqlite3.Connection, chat_id: int) -> dict[str, int]:
    return {
        z["status"]: z["anzahl"]
        for z in conn.execute(
            f"SELECT status, count(*) AS anzahl FROM aufnahme WHERE chat_id = ? "
            f"AND {_NICHT_ENTFERNT} GROUP BY status ORDER BY status",
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


def _szenen_nach_form(conn: sqlite3.Connection, chat_id: int) -> list[tuple[str, int]]:
    """Wie viele Szenen es je Form gibt -- Grundlage der Dashboard-Zeile
    "3 Szenen: 2 Dialog, 1 Lied" (05.09.2026).

    Eine blosse Zahl sagt am Beamer wenig; die Formen sagen, was fuer ein
    Abend da gerade entsteht. Szenen ohne gesetzte Form zaehlen als "offen":
    sie sind noch nicht geplant, und das ist der Zustand, den man auf dem
    Dashboard sehen will."""
    gezaehlt: dict[str, int] = {}
    for z in conn.execute(
        f"SELECT * FROM szene WHERE chat_id = ? AND {_NICHT_ENTFERNT}", (chat_id,)
    ):
        form = (_feld(z, "form") or "").strip() or "offen"
        gezaehlt[form] = gezaehlt.get(form, 0) + 1
    return sorted(gezaehlt.items(), key=lambda paar: (-paar[1], paar[0]))


def _interview_kurzformen(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """Je Interview eine Zeile fuers Dashboard: Name plus die Ergebnisse als
    Kurzform (N6).

    **Ohne Zitate und ohne Zusammenfassung** -- das Dashboard haengt am
    Beamer, und in den Interviews stehen Lebensgeschichten. Was hier steht,
    sind Arbeitsergebnisse in hoechstens acht Woertern je Thema
    ("Pfannkuchen mit Schokolade und Banane · Punkerin im autonomen
    Zentrum")."""
    ergebnis = []
    for nummer, z in enumerate(conn.execute(
        f"SELECT id, name FROM aufnahme WHERE chat_id = ? AND klasse = 'lang' "
        f"AND {_NICHT_ENTFERNT} ORDER BY id ASC",
        (chat_id,),
    ).fetchall(), start=1):
        verdichtung = conn.execute(
            f"SELECT id FROM verdichtung WHERE aufnahme_id = ? AND {_NICHT_ENTFERNT} "
            "ORDER BY id DESC LIMIT 1",
            (z["id"],),
        ).fetchone()
        if verdichtung is None:
            continue
        kurzformen = [t["kurz"] for t in _themen(conn, verdichtung["id"]) if t["kurz"]]
        if kurzformen:
            # Beamer: "Interview 2", nie der Aufnahmename (Birk 05.09.).
            ergebnis.append({"name": f"Interview {nummer}", "kurzformen": kurzformen})
    return ergebnis


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
                "web_token": _feld(z, "web_token"),
                "interviewmodus_seit": z["interviewmodus_seit"],
                "arbeitsstand": _arbeitsstand(conn, chat_id),
                "figuren": _figuren(conn, chat_id),
                "aufnahmen": _aufnahmen_nach_status(conn, chat_id),
                "verdichtungen": conn.execute(
                    f"SELECT count(*) FROM verdichtung WHERE chat_id = ? AND {_NICHT_ENTFERNT}",
                    (chat_id,),
                ).fetchone()[0],
                "szenen": conn.execute(
                    f"SELECT count(*) FROM szene WHERE chat_id = ? AND {_NICHT_ENTFERNT}",
                    (chat_id,),
                ).fetchone()[0],
                "szenen_formen": _szenen_nach_form(conn, chat_id),
                "interview_kurzformen": _interview_kurzformen(conn, chat_id),
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


#: Die Planungsfelder einer Szene (05.09.2026), in der Reihenfolge, in der
#: sie auf der Gruppenseite stehen. Wie in ``szene.FELDNAMEN``, nur fuer die
#: Anzeige -- ``web_daten`` importiert nichts aus dem Schreibpfad.
SZENENFELDER = (
    ("form", "Form"),
    ("ort", "Ort"),
    ("zeit", "Zeit"),
    ("anlass", "Anlass"),
    ("was_passiert", "Was passiert"),
    ("was_anders", "Was anders ist"),
    ("kernsaetze", "Kernsätze"),
    ("ton", "Ton"),
)


def _szene_figuren(conn: sqlite3.Connection, szene_id: int) -> list[str]:
    """Die Namen der Figuren einer Szene. Weich geloeschte Figuren fallen
    heraus (wie in ``repo.szene_figuren``); fehlt die Tabelle noch, ist die
    Besetzung schlicht leer."""
    try:
        return [
            z["name"]
            for z in conn.execute(
                "SELECT f.name FROM szene_figur sf JOIN figur f ON f.id = sf.figur_id "
                f"WHERE sf.szene_id = ? AND f.{_NICHT_ENTFERNT} ORDER BY f.id ASC",
                (szene_id,),
            )
        ]
    except sqlite3.OperationalError:
        return []


def _szenen(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """Die Szenen der Gruppe, nach ``nummer`` -- seit dem 05.09.2026 samt
    ihrer Planung: Form, Ort, Zeit, Anlass, Besetzung, Handlung, Bewegung,
    Kernsaetze, Ton.

    Die Planung steht auf der Gruppenseite gleichberechtigt neben dem Text:
    eine Szene ist zuerst eine Entscheidung der Gruppe und erst danach ein
    Szenentext, und was sie entschieden hat, soll sie nachlesen koennen --
    auch bevor der Text existiert.

    Zeilen ohne Nummer landen hinten statt vorn (NULL sortiert in SQLite
    sonst zuerst)."""
    szenen = []
    for z in conn.execute(
        f"SELECT * FROM szene WHERE chat_id = ? AND {_NICHT_ENTFERNT} "
        "ORDER BY nummer IS NULL, nummer ASC, id ASC",
        (chat_id,),
    ):
        eintrag = {
            "nummer": z["nummer"],
            "titel": z["titel"],
            "kurzbeschreibung": z["kurzbeschreibung"],
            "volltext": z["volltext"],
            "geaendert_am": z["geaendert_am"],
            "figuren": _szene_figuren(conn, z["id"]),
        }
        for feld, _ in SZENENFELDER:
            eintrag[feld] = _feld(z, feld)
        szenen.append(eintrag)
    return szenen


def _themen(conn: sqlite3.Connection, verdichtung_id: int) -> list[dict]:
    """Die Kernthemen einer Verdichtung.

    Ein Belegzitat wird nur gezeigt, wenn es die Pruefung bestanden hat
    (``zitat_geprueft = 1``, SPEC § 5). Ein ungeprueftes Zitat waere genau
    das, wogegen das Belegzitat-Prinzip antritt: ein Satz in
    Anfuehrungszeichen, den vielleicht niemand gesagt hat. Das Thema bleibt
    stehen, das Zitat faellt weg."""
    return [
        {
            "thema": t["thema"],
            # Die Kurzform (N3/N6) ist das, was in die Summary-Zeile je
            # Interview geht -- hoechstens acht Woerter. Fehlt sie (eine
            # Verdichtung aus der Zeit davor), zeigt die Ansicht das Thema.
            "kurz": _feld(t, "kurz") or t["thema"],
            "zitat": t["beleg_zitat"] if t["zitat_geprueft"] == 1 else None,
        }
        for t in conn.execute(
            "SELECT * FROM verdichtung_thema "
            "WHERE verdichtung_id = ? ORDER BY id ASC",
            (verdichtung_id,),
        )
    ]


def _teile_zahlen(conn: sqlite3.Connection, aufnahme_id: int) -> tuple[int, int | None]:
    """Anzahl der Teile eines Interviews und ihre Gesamtdauer in Sekunden
    (§ 10.6). Ohne Teile ``(0, None)`` -- dann gilt die Dauer am Kopf selbst
    (Textimport oder eine Aufnahme aus der Zeit vor dem Nachtrag)."""
    zeile = conn.execute(
        f"SELECT count(*) AS anzahl, sum(dauer_sekunden) AS dauer FROM aufnahme "
        f"WHERE teil_von = ? AND {_NICHT_ENTFERNT}",
        (aufnahme_id,),
    ).fetchone()
    return (zeile["anzahl"] or 0), zeile["dauer"]


def _interviews(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """Die Interviews der Gruppe -- je Interview eine Zeile mit Name, Dauer,
    Teile-Zahl und, sobald es sie gibt, der Verdichtung samt Belegzitaten
    (§ 10.6).

    Ein Interview ist eine Einheit: die einzelnen Sprachnachrichten
    (``teil_von`` gesetzt) tauchen hier nicht als eigene Eintraege auf, und
    ein Gespraechsbeitrag (Klasse *kurz*) ist gar kein Interview.

    Ein Interview ohne Verdichtung faellt trotzdem nicht unter den Tisch: die
    Gruppe soll sehen, dass die Aufnahme da ist, auch wenn die Auswertung noch
    laeuft oder misslungen ist.

    Die ``OperationalError``-Notbremse: die Weboberflaeche oeffnet read-only
    und migriert nichts (siehe ``_feld``). Zwischen einem Deploy und dem
    Neustart des Bots kann ``teil_von`` also noch fehlen -- dann gilt jede
    Aufnahme der Klasse *lang* als ein Interview ohne Teile, was fuer eine
    Datenbank aus dieser Zeit genau richtig ist."""
    try:
        zeilen = conn.execute(
            f"SELECT * FROM aufnahme WHERE chat_id = ? AND klasse = 'lang' "
            f"AND teil_von IS NULL AND {_NICHT_ENTFERNT} ORDER BY id ASC",
            (chat_id,),
        ).fetchall()
        mit_teilen = True
    except sqlite3.OperationalError:
        zeilen = conn.execute(
            f"SELECT * FROM aufnahme WHERE chat_id = ? AND klasse = 'lang' "
            f"AND {_NICHT_ENTFERNT} ORDER BY id ASC",
            (chat_id,),
        ).fetchall()
        mit_teilen = False

    ergebnis = []
    for nummer, z in enumerate(zeilen, start=1):
        teile, teile_dauer = _teile_zahlen(conn, z["id"]) if mit_teilen else (0, None)
        verdichtung = conn.execute(
            f"SELECT id, zusammenfassung, erstellt_am FROM verdichtung "
            f"WHERE aufnahme_id = ? AND {_NICHT_ENTFERNT} ORDER BY id DESC LIMIT 1",
            (z["id"],),
        ).fetchone()
        ergebnis.append(
            {
                "name": z["name"],
                # Anzeige ohne Klarnamen (Birk 05.09.): "Interview 2".
                "bezeichnung": f"Interview {nummer}",
                "status": z["status"],
                "teile": teile,
                "dauer_sekunden": teile_dauer if teile else z["dauer_sekunden"],
                "zusammenfassung": verdichtung["zusammenfassung"] if verdichtung else None,
                "erstellt_am": verdichtung["erstellt_am"] if verdichtung else None,
                "themen": _themen(conn, verdichtung["id"]) if verdichtung else [],
            }
        )
    return ergebnis


def _journal(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    return [
        {"art": z["art"], "text": z["text"], "quelle": z["quelle"],
         "erstellt_am": z["erstellt_am"]}
        for z in conn.execute(
            "SELECT art, text, quelle, erstellt_am FROM journal "
            f"WHERE chat_id = ? AND {_NICHT_ENTFERNT} ORDER BY id ASC",
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
    try:
        zeile = conn.execute(
            "SELECT * FROM gruppe WHERE web_token = ?", (token,)
        ).fetchone()
    except sqlite3.OperationalError:
        # Spalte fehlt noch: die Migration laeuft im Bot, nicht hier
        # (read-only). Bis der Bot mit neuem Code laeuft, gibt es keine
        # Gruppenseite -- 404, nicht 500.
        return None
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
        "interviews": _interviews(conn, chat_id),
        "journal": _journal(conn, chat_id),
    }
