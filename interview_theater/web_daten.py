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

import json
import sqlite3
import statistics
from datetime import datetime, timedelta, timezone

#: Der Vorspann ist die eine Ausnahme von "kein Import aus dem Botcode": das
#: Modul kennt keine Datenbank und keinen Lock (``vorspann.daten`` nimmt
#: Dicts), und genau darum darf die Regel "ein Fakt hat eine Stelle" hier
#: gelten -- Chat, Textbuch und Gruppenseite schneiden dieselbe
#: Figurenbeschreibung sonst dreimal verschieden.
from interview_theater import vorspann

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
        "fragen_weich": _feld(zeile, "fragen_weich"),
        "interview_eroeffnung": _feld(zeile, "interview_eroeffnung"),
        "interview_abschluss": _feld(zeile, "interview_abschluss"),
        "kernthema": zeile["kernthema"] if zeile else None,
        "kernthema_begruendung": zeile["kernthema_begruendung"] if zeile else None,
        "format": _feld(zeile, "format"),
        "rahmen": _feld(zeile, "rahmen"),
        # Die zweistufige Kernthema-Arbeit (05.09.2026): die Richtung ist
        # Stufe 1, die Kernfrage Stufe 3. Beide fehlten hier, solange die
        # Weboberflaeche nur die fertige Formulierung anzeigte -- seit die
        # Gruppenseite sie aendern laesst, muessen sie herauskommen, sonst
        # steht im Formular ein leeres Feld ueber einem gesetzten Wert.
        "kernthema_richtung": _feld(zeile, "kernthema_richtung"),
        "kernfrage": _feld(zeile, "kernfrage"),
        # Die Geschichte im Groben (Phase 5, Umbau 05.09.2026 nachts).
        "geschichte": _feld(zeile, "geschichte"),
        # Wann die Figurenliste abgenommen wurde (06.09.2026). Steht auf der
        # Seite nirgends -- das Fehlstellen-Register braucht es, weil es eine
        # Voraussetzung der naechsten Phase ist (``phasen.voraussetzungen``).
        "figuren_fixiert_am": _feld(zeile, "figuren_fixiert_am"),
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
            # Die id geht seit der Bearbeitung auf der Gruppenseite mit
            # (05.09.2026 abends): das Formular adressiert eine Figur ueber
            # ihre id, nie ueber ihren Namen -- sonst waere ein Umbenennen
            # kein Umbenennen, sondern eine zweite Figur.
            "id": z["id"],
            "name": z["name"],
            "beschreibung": z["beschreibung"],
            "sprachprofil": _feld(z, "sprachprofil"),
            "zitate": [s.strip() for s in zitate.split(ZITAT_TRENNER) if s.strip()],
            "quelle": quelle,
            "quelle_aufnahme_id": quelle_id,
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
    # Der Formvorschlag des Bots (06.09.2026) -- er steht neben der Form, weil
    # die Gruppe an der Seite sehen soll, was vorgeschlagen und was
    # bestaetigt wurde. Bestaetigt ist allein ``form``.
    ("form_vorschlag", "Form (Vorschlag)"),
    # Die Stilvorlage je Szene (06.09.2026, Birk 12:50) -- der Slug aus
    # ``prompts/stile/``; die lesbare Beschriftung macht ``web.py``.
    ("stil", "Stil"),
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


def _szene_figur_ids(conn: sqlite3.Connection, szene_id: int) -> list[int]:
    """Wie ``_szene_figuren``, nur die ids -- die Mehrfachauswahl auf der
    Gruppenseite markiert damit die besetzten Figuren, ohne ueber Namen
    vergleichen zu muessen (zwei Figuren duerfen gleich heissen)."""
    try:
        return [
            z["figur_id"]
            for z in conn.execute(
                "SELECT sf.figur_id FROM szene_figur sf JOIN figur f ON f.id = sf.figur_id "
                f"WHERE sf.szene_id = ? AND f.{_NICHT_ENTFERNT} ORDER BY f.id ASC",
                (szene_id,),
            )
        ]
    except sqlite3.OperationalError:
        return []


def schaerfungen(conn: sqlite3.Connection, chat_id: int) -> dict:
    """Welche Interviewstellen bei der Schärfung welcher Szene und welcher
    Figur zugeordnet wurden (Phase 6, Umbau 05.09.2026 nachts).

    Liefert ``{"szene": {id: [kurz, …]}, "figur": {id: [kurz, …]}}`` --
    **nur die Kurzform** eines ``verdichtung_thema``, nie sein Belegzitat und
    nie die Begründung des Schärfungslaufs. Die Kurzform ist das, was schon
    heute am Beamer steht (``_interview_kurzformen``): höchstens acht Wörter
    Arbeitsergebnis. Ein Belegzitat wäre ein Satz aus einem Interview auf
    einer Seite ohne Login -- genau die Grenze, die nicht verhandelbar ist.

    Fehlt die Tabelle noch (Datenbank aus der Zeit vor dem Umbau), ist das
    Ergebnis leer statt ein Fehler: der Webserver migriert nichts."""
    ergebnis: dict[str, dict[int, list[str]]] = {"szene": {}, "figur": {}}
    try:
        zeilen = conn.execute(
            "SELECT s.szene_id, s.figur_id, t.kurz, t.thema "
            "FROM schaerfung s JOIN verdichtung_thema t "
            "  ON t.id = s.verdichtung_thema_id "
            f"WHERE s.chat_id = ? AND s.{_NICHT_ENTFERNT} ORDER BY s.id ASC",
            (chat_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return ergebnis
    for z in zeilen:
        # Fehlt die Kurzform (Verdichtung aus der Zeit davor), bleibt die
        # Zeile weg -- lieber ein Zähler weniger als ein ganzer Themensatz.
        kurz = (_feld(z, "kurz") or "").strip()
        if not kurz:
            continue
        for schluessel, spalte in (("szene", "szene_id"), ("figur", "figur_id")):
            ziel = _feld(z, spalte)
            if ziel is None:
                continue
            eintraege = ergebnis[schluessel].setdefault(ziel, [])
            if kurz not in eintraege:
                eintraege.append(kurz)
    return ergebnis


def _fruehere_fassungen(conn: sqlite3.Connection, szene_id: int) -> list[dict]:
    """Die **frueheren** Fassungen einer Szene, juengste zuerst -- ohne die
    aktuelle (06.09.2026).

    Die letzte Zeile in ``szenenfassung`` ist der Text, der oben auf der
    Seite ohnehin steht; sie ein zweites Mal aufzuklappen waere Doppelung.
    Bleibt nichts uebrig, fehlt der Block ganz.

    Fehlt die Tabelle noch (Datenbank aus der Zeit davor), ist das Ergebnis
    leer statt ein Fehler: der Webserver migriert nichts."""
    try:
        zeilen = conn.execute(
            "SELECT * FROM szenenfassung WHERE szene_id = ? "
            "ORDER BY nummer ASC, id ASC",
            (szene_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [
        {
            "nummer": z["nummer"],
            "volltext": z["volltext"],
            "zusammenfassung": z["zusammenfassung"],
            "anders_gemacht": z["anders_gemacht"],
            "erstellt_am": z["erstellt_am"],
        }
        for z in reversed(zeilen[:-1])
    ]


def _szenen(
    conn: sqlite3.Connection, chat_id: int, geschaerft: dict | None = None
) -> list[dict]:
    """Die Szenen der Gruppe, nach ``nummer`` -- seit dem 05.09.2026 samt
    ihrer Planung: Form, Ort, Zeit, Anlass, Besetzung, Handlung, Bewegung,
    Kernsaetze, Ton.

    Die Planung steht auf der Gruppenseite gleichberechtigt neben dem Text:
    eine Szene ist zuerst eine Entscheidung der Gruppe und erst danach ein
    Szenentext, und was sie entschieden hat, soll sie nachlesen koennen --
    auch bevor der Text existiert.

    Zeilen ohne Nummer landen hinten statt vorn (NULL sortiert in SQLite
    sonst zuerst)."""
    je_szene = (geschaerft or schaerfungen(conn, chat_id))["szene"]
    szenen = []
    for z in conn.execute(
        f"SELECT * FROM szene WHERE chat_id = ? AND {_NICHT_ENTFERNT} "
        "ORDER BY nummer IS NULL, nummer ASC, id ASC",
        (chat_id,),
    ):
        eintrag = {
            # Die zugeordneten Interviewstellen als Kurzformen (Phase 6) --
            # read-only, ohne Zitat.
            "schaerfungen": je_szene.get(z["id"], []),
            # id und figur_ids seit der Bearbeitung auf der Gruppenseite
            # (05.09.2026 abends): das Formular adressiert eine Szene ueber
            # ihre id, und die Mehrfachauswahl braucht die ausgewaehlten
            # Figuren als ids, nicht als Namen.
            "id": z["id"],
            "nummer": z["nummer"],
            "titel": z["titel"],
            "kurzbeschreibung": z["kurzbeschreibung"],
            # Read-only auf der Gruppenseite (06.09.2026): das Modell schreibt
            # sie, die Gruppe liest sie -- es gibt kein Formularfeld dafuer.
            "zusammenfassung": _feld(z, "zusammenfassung"),
            "volltext": z["volltext"],
            # Die Prosafassung (Phase 6, 06.09.2026): read-only auf der
            # Gruppenseite -- sie ist die Vorlage, die der Feinschliff in
            # eine Form uebersetzt, und wird nicht von Hand gepflegt.
            "prosa": _feld(z, "prosa"),
            "geaendert_am": z["geaendert_am"],
            "figuren": _szene_figuren(conn, z["id"]),
            "figur_ids": _szene_figur_ids(conn, z["id"]),
            # Die frueheren Fassungen (06.09.2026) -- read-only, aufklappbar,
            # ohne die aktuelle. Leere Liste heisst: kein Block.
            "fassungen": _fruehere_fassungen(conn, z["id"]),
        }
        for feld, _ in SZENENFELDER:
            eintrag[feld] = _feld(z, feld)
        szenen.append(eintrag)
    return szenen


def szenenuebersicht(
    conn: sqlite3.Connection,
    chat_id: int,
    szenen: list[dict] | None = None,
    fassungen: dict[int, list[dict]] | None = None,
) -> list[dict]:
    """Die kompakte Szenen-Uebersicht der Gruppenseite (06.09.2026, Birk:
    *"Was mir in der Webansicht gefehlt hat, ist eine Uebersicht ueber die
    Szenen -- nachdem Szene 1,2,3 schon definiert sind, sollten die da auch
    dargestellt werden."*).

    Je Szene eine Zeile: Nummer, Titel, eine kurze Beschreibung, die Form
    (und der Formvorschlag, solange sie noch nicht bestaetigt ist), der Stil
    und **die Zeichenzahl** von Prosa und Volltext. Die Texte selbst stehen
    hier bewusst NICHT: die Uebersicht soll auf einen Blick sagen, was
    festgelegt ist und was schon geschrieben wurde -- den Text zeigt der
    aufklappbare Block darunter.

    Sortiert nach Nummer, Zeilen ohne Nummer hinten. Read-only wie alles in
    diesem Modul."""
    zeilen = szenen if szenen is not None else _szenen(conn, chat_id)
    if fassungen is None:
        fassungen = szenenfassungen(conn, chat_id, zeilen)
    uebersicht = []
    for s in zeilen:
        form = (s.get("form") or "").strip()
        uebersicht.append(
            {
                # Die id traegt die Uebersicht seit der Fassungsansicht
                # (07.09.2026): der Zaehler ist ein Link auf genau diese Szene.
                "id": s.get("id"),
                "fassungen": len(fassungen.get(s.get("id")) or []),
                "nummer": s.get("nummer"),
                "titel": (s.get("titel") or "").strip(),
                # Die Kurzbeschreibung zuerst; hat die Szene keine, sagt
                # ``was_passiert``, worum es geht. Beides sind Felder der
                # Planung, keine Modellausgabe.
                "kurz": (s.get("kurzbeschreibung") or s.get("was_passiert") or "").strip(),
                "form": form,
                # Der Vorschlag steht nur da, solange die Gruppe die Form
                # noch nicht bestaetigt hat -- danach waere er eine zweite,
                # widersprechende Angabe.
                "form_vorschlag": (
                    "" if form else (s.get("form_vorschlag") or "").strip()
                ),
                "stil": (s.get("stil") or "").strip(),
                "prosa_zeichen": len((s.get("prosa") or "")),
                "volltext_zeichen": len((s.get("volltext") or "")),
            }
        )
    return uebersicht


#: Trennzeichen zwischen zwei Fassungen im Altfeld
#: ``szene.fruehere_fassungen`` -- muss mit ``szenenfolge.FASSUNGSTRENNER``
#: uebereinstimmen (Test). Wie ``ZITAT_TRENNER`` bewusst hier noch einmal und
#: nicht importiert: ``web_daten`` haengt an keiner Schreibschicht.
FASSUNGSTRENNER = "\n\n----- fruehere Fassung -----\n\n"


def szenenfassungen(
    conn: sqlite3.Connection, chat_id: int, szenen: list[dict] | None = None
) -> dict[int, list[dict]]:
    """Die Fassungen je Szene, aelteste zuerst -- ``{szene_id: [Fassung, …]}``.

    Drei Quellen, in dieser Reihenfolge zusammengelegt, weil eine Datenbank
    aus dem laufenden Betrieb alle drei gleichzeitig enthalten kann:

    1. das **Altfeld** ``szene.fruehere_fassungen`` (bis 06.09.2026 der
       einzige Ort; ein Textblock mit ``FASSUNGSTRENNER``),
    2. die Tabelle **``szenenfassung``** (seit 06.09.2026, eine Zeile je
       Fassung mit Nummer und Zeitpunkt; beschriftet wird sie mit der Zeile
       ``Anders gemacht:`` des Laufs, der sie geschrieben hat -- das ist der
       Satz, an dem die Gruppe sie wiedererkennt),
    3. der **aktuelle** ``szene.volltext``.

    Doppelt vorhandene Texte zaehlen einmal (verglichen wird der getrimmte
    Text): ``repo.hebe_fassung_auf`` schreibt beim Nachruesten in beide
    Quellen, und eine Fassung, die zweimal in der Liste stuende, waere fuer die
    Gruppe ein Fehler und kein Verlauf. Danach wird von 1 an durchgezaehlt --
    die Nummer in der Ansicht ist die Nummer in der Liste, nicht die aus der
    Tabelle, sonst zeigte ein Link nach dem Nachruesten auf die falsche
    Fassung.

    Fehlt die Tabelle oder die Spalte noch (Datenbank aus der Zeit davor,
    Deploy vor dem Bot-Neustart), ist das Ergebnis kleiner statt ein Fehler:
    der Webserver migriert nichts."""
    zeilen = szenen if szenen is not None else _szenen(conn, chat_id)
    je_szene: dict[int, list[sqlite3.Row]] = {}
    try:
        for z in conn.execute(
            "SELECT szene_id, nummer, anders_gemacht, volltext, erstellt_am "
            "FROM szenenfassung WHERE chat_id = ? ORDER BY nummer ASC, id ASC",
            (chat_id,),
        ):
            je_szene.setdefault(z["szene_id"], []).append(z)
    except sqlite3.OperationalError:
        je_szene = {}
    altfeld: dict[int, str] = {}
    try:
        altfeld = {
            z["id"]: (z["fruehere_fassungen"] or "")
            for z in conn.execute(
                "SELECT id, fruehere_fassungen FROM szene WHERE chat_id = ?",
                (chat_id,),
            )
        }
    except sqlite3.OperationalError:
        altfeld = {}

    ergebnis: dict[int, list[dict]] = {}
    for s in zeilen:
        szene_id = s.get("id")
        gesammelt: list[dict] = []

        def _dazu(text, beschriftung, erstellt_am=None):
            text = (text or "").strip()
            if not text or any(f["volltext"] == text for f in gesammelt):
                return
            gesammelt.append(
                {
                    "beschriftung": (beschriftung or "").strip(),
                    "volltext": text,
                    "erstellt_am": erstellt_am,
                }
            )

        for stueck in (altfeld.get(szene_id) or "").split(FASSUNGSTRENNER):
            _dazu(stueck, "")
        for z in je_szene.get(szene_id, []):
            _dazu(z["volltext"], z["anders_gemacht"], z["erstellt_am"])
        aktuell = (s.get("volltext") or "").strip()
        _dazu(aktuell, "")

        fassungen = []
        for nummer, f in enumerate(gesammelt, start=1):
            f = dict(f, nummer=nummer, zeichen=len(f["volltext"]))
            # "Die aktuelle" ist die, die in ``szene.volltext`` steht -- nicht
            # einfach die letzte: eine Szene kann Fassungen im Archiv haben und
            # gerade gar keinen Volltext.
            f["aktuell"] = bool(aktuell) and f["volltext"] == aktuell
            fassungen.append(f)
        if fassungen:
            ergebnis[szene_id] = fassungen
    return ergebnis


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


def _begriffe(conn: sqlite3.Connection, verdichtung_id: int) -> list[str]:
    """Die zugeordneten Kernbegriffe einer Verdichtung (06.09.2026) -- in der
    Reihenfolge, in der sie gesetzt wurden, und das ist die Reihenfolge der
    Begriffsliste der Gruppe.

    Die ``OperationalError``-Notbremse wie ueberall hier: die Weboberflaeche
    oeffnet read-only und migriert nichts. Zwischen einem Deploy und dem
    Neustart des Bots gibt es die Tabelle vielleicht noch gar nicht -- dann
    hat eben keine Verdichtung Tags, und die Seite steht trotzdem."""
    try:
        return [
            z["begriff"]
            for z in conn.execute(
                "SELECT begriff FROM verdichtung_begriff "
                "WHERE verdichtung_id = ? ORDER BY id ASC",
                (verdichtung_id,),
            )
        ]
    except sqlite3.OperationalError:
        return []


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


def _hat_teil_transkript(conn: sqlite3.Connection, kopf_id: int, mit_teilen: bool) -> bool:
    """Hat mindestens ein Teil dieses Interviews ein Transkript?

    Das Gegenstueck zu ``repo.zusammengefuegtes_transkript`` fuer die
    read-only Seite: ein Interview-Kopf traegt seit § 10.6 oft selbst keinen
    Text, sondern nur seine Teile."""
    if not mit_teilen:
        return False
    zeile = conn.execute(
        "SELECT 1 FROM aufnahme WHERE teil_von = ? "
        f"AND {_NICHT_ENTFERNT} AND trim(coalesce(transkript, '')) <> '' LIMIT 1",
        (kopf_id,),
    ).fetchone()
    return zeile is not None


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

    # 06.09.2026 14:00 (Birk): chronologisch nach dem BEGINN der Aufnahme
    # (fruehester Teil; ohne Teile der Kopf selbst) -- nicht nach id: ein
    # nachtraeglich getrenntes Interview bekommt eine hoehere id als ein
    # spaeter aufgenommenes, und die Nummer stimmt dann nicht mehr.
    def _beginn(z):
        if mit_teilen:
            erster = conn.execute(
                f"SELECT min(empfangen_am) AS t FROM aufnahme WHERE teil_von = ? AND {_NICHT_ENTFERNT}",
                (z["id"],),
            ).fetchone()
            if erster and erster["t"]:
                return erster["t"]
        return z["empfangen_am"] or ""

    zeilen = sorted(zeilen, key=_beginn)
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
                # Fuer das Fehlstellen-Register (06.09.2026): dieselben zwei
                # Bedingungen wie in ``aufnahme.unausgewertete_interviews``.
                # Beide gehen nicht in die Anzeige ein -- sie stehen hier,
                # damit ``_offene_interviews`` sie nicht ein zweites Mal
                # abfragen muss.
                "beendet": bool(_feld(z, "beendet_am"))
                or z["status"] in ("fertig", "transkribiert"),
                "hat_transkript": bool((z["transkript"] or "").strip())
                or _hat_teil_transkript(conn, z["id"], mit_teilen),
                "teile": teile,
                "beginn": _beginn(z),
                "dauer_sekunden": teile_dauer if teile else z["dauer_sekunden"],
                "zusammenfassung": verdichtung["zusammenfassung"] if verdichtung else None,
                "erstellt_am": verdichtung["erstellt_am"] if verdichtung else None,
                "themen": _themen(conn, verdichtung["id"]) if verdichtung else [],
                # Die Kernbegriffe der Gruppe, die dieses Interview traegt
                # (06.09.2026): n:m, deterministisch zugeordnet, als Tags auf
                # der Gruppenseite. Ohne Verdichtung gibt es nichts zuzuordnen.
                "begriffe": _begriffe(conn, verdichtung["id"]) if verdichtung else [],
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


def _festlegungen(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """Die geltenden Festlegungen, aelteste zuerst -- dieselbe Reihenfolge
    wie im Prompt (``kontext._baue_festlegungen``).

    **Mit der id**, anders als beim Journal: an ihr haengt der Loeschknopf.
    Eine veraltete Festlegung, die niemand abraeumen kann, waere genau der
    Fehler, den diese Tabelle beheben soll (Analyse § 2.5).

    Fehlt die Tabelle noch (Datenbank aus der Zeit davor), ist das Ergebnis
    leer statt ein Fehler: der Webserver migriert nichts, er liest
    read-only."""
    try:
        zeilen = conn.execute(
            "SELECT id, bereich, bezug, text, quelle, erstellt_am FROM festlegung "
            f"WHERE chat_id = ? AND {_NICHT_ENTFERNT} ORDER BY id ASC",
            (chat_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [
        {"id": z["id"], "bereich": z["bereich"], "bezug": z["bezug"],
         "text": z["text"], "quelle": z["quelle"], "erstellt_am": z["erstellt_am"]}
        for z in zeilen
    ]


#: Woher die Dropdowns auf der Gruppenseite ihre Vorschlaege nehmen: aus der
#: Tabelle ``knopf``, also aus genau dem, was der Bot der Gruppe im Chat schon
#: einmal zur Auswahl gestellt hat (``knoepfe._AUSWAHLMARKER``). Das ist die
#: Zusage hinter der Bearbeitung: im Dropdown steht nichts, was die Gruppe
#: nicht ohnehin gelesen hat -- kein Transkript, kein Nachrichtentext, kein
#: ungepruefter Satz aus einem Interview.
#:
#: ``kernthema_richtung`` steht neben ``richtung``, weil die Knopf-Art einmal
#: so hiess; eine alte Datenbank soll ihre Richtungen nicht verlieren.
KNOPFARTEN = {
    "kernthema": ("kernthema",),
    "kernthema_richtung": ("richtung", "kernthema_richtung"),
    "rahmen": ("rahmen",),
}

#: Wie viele frueher angebotene Werte ein Dropdown hoechstens zeigt. Birk:
#: "Die Auswahl soll klein und sinnvoll bleiben." Zwoelf ist die Grenze, ab
#: der eine Liste auf dem Telefon zum Scrollen wird.
MAX_VORSCHLAEGE = 12


def angebotene_werte(
    conn: sqlite3.Connection, chat_id: int, feld: str
) -> list[str]:
    """Alle Werte, die der Gruppe zu diesem Feld je als Knopf angeboten
    wurden -- neueste zuerst, ohne Dubletten, hoechstens ``MAX_VORSCHLAEGE``.

    Rein lesend, wie alles hier. Ein unbekanntes Feld liefert eine leere
    Liste statt eines Fehlers: das Formular soll dann ein Textfeld ohne
    Dropdown zeigen und nicht die Seite mitreissen. Fehlt die Tabelle noch
    (Datenbank aus der Zeit vor den Knoepfen), ebenso."""
    arten = KNOPFARTEN.get(feld)
    if not arten:
        return []
    platzhalter = ", ".join("?" * len(arten))
    try:
        zeilen = conn.execute(
            f"SELECT wert FROM knopf WHERE chat_id = ? AND art IN ({platzhalter}) "
            "ORDER BY id DESC",
            (chat_id, *arten),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    gesehen: dict[str, None] = {}
    for z in zeilen:
        wert = (z["wert"] or "").strip()
        if wert and wert not in gesehen:
            gesehen[wert] = None
        if len(gesehen) >= MAX_VORSCHLAEGE:
            break
    return list(gesehen)


def interviewliste(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """Die nicht entfernten Interviews als ``[{"id", "bezeichnung"}]``.

    Fuer die Interview-Zuordnung einer Figur. **Nur Nummer und id** -- nie
    der Aufnahmename (der ist oft ein Klarname, Birk 05.09.) und schon gar
    nicht ein Stueck Transkript: das Dropdown steht auf einer Seite ohne
    Login."""
    try:
        zeilen = conn.execute(
            f"SELECT id, empfangen_am FROM aufnahme WHERE chat_id = ? AND klasse = 'lang' "
            f"AND teil_von IS NULL AND {_NICHT_ENTFERNT} ORDER BY id ASC",
            (chat_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    def _beginn(z):
        erster = conn.execute(
            f"SELECT min(empfangen_am) AS t FROM aufnahme WHERE teil_von = ? AND {_NICHT_ENTFERNT}",
            (z["id"],),
        ).fetchone()
        return (erster["t"] if erster and erster["t"] else None) or z["empfangen_am"] or ""

    zeilen = sorted(zeilen, key=_beginn)
    return [
        {"id": z["id"], "bezeichnung": f"Interview {nummer}"}
        for nummer, z in enumerate(zeilen, start=1)
    ]


def bearbeitbares(conn: sqlite3.Connection, chat_id: int) -> dict:
    """Alles, was die Formulare der Gruppenseite an Auswahlmoeglichkeiten
    brauchen -- in einem Rutsch, damit ``web.py`` nicht sechsmal einzeln
    nachfragt.

    Ohne Kernthema und Kernthema-Richtung seit dem Phasen-Umbau: die beiden
    sind keine Station mehr und stehen auf der Seite nur noch read-only, wenn
    sie gesetzt sind. ``angebotene_werte`` kennt sie weiter (``KNOPFARTEN``)
    -- eine Gruppe aus der Zeit davor soll ihre Vorschläge nicht verlieren,
    falls die Station je zurückkommt."""
    return {
        "rahmen": angebotene_werte(conn, chat_id, "rahmen"),
        "interviews": interviewliste(conn, chat_id),
    }


def chat_id_nach_token(conn: sqlite3.Connection, token: str | None) -> int | None:
    """Die ``chat_id`` zu einem Web-Token, oder None.

    Die kleine Schwester von ``gruppe_nach_token`` fuer die Wege, die nur
    wissen muessen, WELCHE Gruppe gemeint ist -- der Textbuch-Download
    (``/g/<token>/textbuch.md``) baut seinen Inhalt aus
    ``szenenfolge.textbuch`` und braucht die halbe Gruppenseite dafuer nicht.
    Dieselben zwei Vorsichtsmassnahmen wie dort: ein leeres Token wird gar
    nicht erst gesucht (sonst traefe ``/g/`` jede Gruppe mit leerer Spalte),
    und eine fehlende Spalte ``web_token`` ist ein None und kein Fehler --
    die Migration laeuft im Bot, nicht hier."""
    if not token:
        return None
    try:
        zeile = conn.execute(
            "SELECT chat_id FROM gruppe WHERE web_token = ?", (token,)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return zeile["chat_id"] if zeile else None


def web_chat_id_nach_token(conn: sqlite3.Connection, token: str | None) -> int | None:
    """Die ``chat_id`` zu einem Web-Token -- aber NUR fuer eine Gruppe im
    Web-Kanal (``gruppe.kanal = 'web'``), sonst None (Abschlussreview I3).

    Die Chatansicht (``/g/<token>/chat``) gibt es nur dort: eine
    Telegram-Gruppe hat keinen Bot, der ``web_post`` liest -- was sie im
    Browser schriebe, laege ungelesen in der Tabelle, und niemand saehe es.
    Gruppenseite, Probenansicht und Leitfaden bleiben fuer jede Gruppe
    (``chat_id_nach_token``). Eine fehlende Spalte ``kanal`` (Bot noch nicht
    migriert) heisst: keine Web-Gruppe."""
    if not token:
        return None
    try:
        zeile = conn.execute(
            "SELECT chat_id FROM gruppe WHERE web_token = ? AND kanal = 'web'",
            (token,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return zeile["chat_id"] if zeile else None


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
    # Einmal lesen, zweimal verwendet: die Szenen bekommen ihre Zuordnungen
    # gleich mit, die Figuren hier daneben. Auf dem Dashboard steht davon
    # nichts -- ``_figuren`` bleibt deshalb unveraendert.
    geschaerft = schaerfungen(conn, chat_id)
    figuren = _figuren(conn, chat_id)
    for f in figuren:
        f["schaerfungen"] = geschaerft["figur"].get(f["id"], [])
    szenen = _szenen(conn, chat_id, geschaerft)
    fassungen = szenenfassungen(conn, chat_id, szenen)
    stand = _arbeitsstand(conn, chat_id)
    return {
        "chat_id": chat_id,
        "titel": zeile["titel"],
        # Das Token geht mit, damit die Seite auf ihre Unterseiten verlinken
        # kann (``/g/<token>/leitfaden``) -- relativ, also ohne zu wissen, ob
        # nginx das Praefix durchreicht.
        "web_token": token,
        "bot_name": zeile["bot_name"],
        # Der Kanal (Abschlussreview I3): nur eine Web-Gruppe bekommt den
        # Link in die Chatansicht. Fehlt die Spalte noch, ist es Telegram.
        "kanal": _feld(zeile, "kanal") or "telegram",
        "interviewmodus_seit": zeile["interviewmodus_seit"],
        "arbeitsstand": stand,
        # Was die Gruppe festgelegt hat und wofuer es kein Feld gibt
        # (06.09.2026). Steht auf der Seite aufgeklappt, nicht in einem
        # <details> wie das Journal: sichtbar war das Journal auch, und
        # gewirkt hat es trotzdem nicht.
        "festlegungen": _festlegungen(conn, chat_id),
        # Der Vorspann (07.09.2026): dieselben Werte wie im Chat und im
        # Textbuch, aus derselben Funktion -- ``vorspann.daten`` nimmt Dicts
        # und kennt keine Datenbank, deshalb darf ``web_daten`` es rufen,
        # ohne read-only zu verlassen oder ``repo`` zu importieren.
        "vorspann": vorspann.daten(
            stand["rahmen"], stand["hauptkonflikt"], stand["format"],
            szenen, figuren,
        ),
        "figuren": figuren,
        "szenen": szenen,
        # Die kompakte Uebersicht steht vor den aufklappbaren Bloecken
        # (06.09.2026, Birk) -- dieselben Zeilen, nur zusammengefasst; kein
        # zweiter Lesevorgang.
        "szenenuebersicht": szenenuebersicht(conn, chat_id, szenen, fassungen),
        # Die Fassungen je Szene (07.09.2026) -- read-only wie alles hier.
        "fassungen": fassungen,
        "interviews": _interviews(conn, chat_id),
        "journal": _journal(conn, chat_id),
        "bearbeitbares": bearbeitbares(conn, chat_id),
        "schaerfungen": geschaerft,
        "stueckpruefung": stueckpruefung(conn, chat_id),
        # Was noch fehlt (06.09.2026) -- leere Liste heisst: der Abschnitt
        # bleibt weg, nicht "nichts fehlt".
        "fehlstellen": fehlstellen(conn, chat_id),
        # Wie viel jede Figur spricht (06.09.2026) -- ``szenen: 0`` heisst:
        # keine Szene war zaehlbar, der Abschnitt bleibt weg.
        "sprechanteile": sprechanteile(conn, chat_id),
        # Die Dramaturgie-Pruefung (06.09.2026) -- leeres Dict heisst: es gab
        # noch keinen Lauf, der Abschnitt bleibt weg. Belegzitate stehen NIE
        # darin, die Gruppenseite ist oeffentlich erreichbar.
        "dramaturgie": dramaturgie(conn, chat_id),
        # Der Buehne-Tab (Phase 4, nur Web, 02.10.2026) -- read-only wie der
        # Rest dieser Funktion. Die Karten tragen NIE ein Belegzitat (Phase 4
        # ist interview-frei), siehe buehnenkarte.py/db.py.
        "buehnenkarten": buehnenkarten(conn, chat_id),
        "stueckkarte_felder": stueckkarte_felder(conn, chat_id, figuren, stand),
    }


def buehnenkarten(
    conn: sqlite3.Connection, chat_id: int, hoechstens: int = 10,
) -> list[sqlite3.Row]:
    """Das read-only Gegenstueck zu ``repo.buehnenkarten`` (Buehne-Tab der
    Gruppenseite) -- NEUESTE ZUERST, wie dort. Fehlt die Tabelle noch
    (Deploy vor Bot-Neustart), ist die Liste leer statt ein Fehler."""
    try:
        return conn.execute(
            "SELECT * FROM buehnenkarte WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, hoechstens),
        ).fetchall()
    except sqlite3.OperationalError:
        return []


def stueckkarte_felder(
    conn: sqlite3.Connection, chat_id: int,
    figuren: list[dict] | None = None, arbeitsstand: dict | None = None,
) -> list[tuple[str, str | None]]:
    """Dieselben drei festen Felder wie ``repo.stueckkarte_felder``
    (Setting, Figuren, Geschichte) -- read-only. ``figuren``/``arbeitsstand``
    duerfen mitgegeben werden, wenn der Aufrufer (``gruppe_nach_token``) sie
    ohnehin schon gelesen hat: kein zweiter Lesevorgang fuer dieselbe
    Zeile."""
    stand = arbeitsstand if arbeitsstand is not None else _arbeitsstand(conn, chat_id)
    namen_liste = figuren if figuren is not None else _figuren(conn, chat_id)
    namen = [f["name"] for f in namen_liste]
    return [
        ("Setting", stand.get("rahmen") or None),
        ("Figuren", ", ".join(namen) if namen else None),
        ("Geschichte", stand.get("geschichte") or None),
    ]


def sprechanteile(conn: sqlite3.Connection, chat_id: int) -> dict:
    """Wie viel jede Figur spricht (``interview_theater/sprecher.py``) --
    reine Zaehlung ueber die Szenentexte, kein Modellaufruf.

    Wie beim Leitfaden und beim Fehlstellen-Register bleibt der Zusammenbau
    in seinem Modul: ``sprecher.anteile`` kennt nur Dicts und haengt an
    keiner Schreibschicht. Ohne zaehlbare Szene ist ``szenen`` 0 -- dann
    zeigt die Seite den Abschnitt gar nicht."""
    from interview_theater import sprecher

    return sprecher.anteile(_szenen(conn, chat_id), _figuren(conn, chat_id))


def _offene_interviews(conn: sqlite3.Connection, chat_id: int) -> list[str]:
    """Die Bezeichnungen der Interviews, die beendet sind und Material haben,
    aber noch keine Verdichtung -- das read-only Gegenstueck zu
    ``aufnahme.unausgewertete_interviews``.

    Dieselben drei Bedingungen (beendet, Transkript da, keine Verdichtung),
    nur ohne ``repo``: der Webserver hat die Schreibschicht nicht. Fehlt eine
    Spalte noch (Datenbank aus der Zeit davor), ist die Liste leer statt ein
    Fehler."""
    offen = []
    for eintrag in _interviews(conn, chat_id):
        if eintrag["zusammenfassung"]:
            continue
        if not eintrag.get("beendet"):
            continue
        if not eintrag.get("hat_transkript"):
            continue
        offen.append(eintrag["bezeichnung"])
    return offen


def fehlstellen(conn: sqlite3.Connection, chat_id: int) -> list[dict]:
    """Was der Gruppe noch fehlt (``interview_theater/fehlstellen.py``) --
    aus der read-only geoeffneten Verbindung.

    ``fehlstellen`` selbst haengt an keiner Schreibschicht, solange nur
    ``aus_daten`` gerufen wird: die reine Funktion kennt Dicts, keine
    Verbindung. Dasselbe Muster wie beim Leitfaden (``leitfaden.aus_feldern``)
    -- ein Zusammenbau, zwei Aufrufer, damit auf der Gruppenseite nichts
    anderes steht als im Chat."""
    from interview_theater import fehlstellen as modul, phasen

    stand = _arbeitsstand(conn, chat_id)
    verdichtet = any(e["zusammenfassung"] for e in _interviews(conn, chat_id))
    return modul.aus_daten(
        stand,
        _figuren(conn, chat_id),
        _szenen(conn, chat_id),
        stand.get("phase") or phasen.ERSTE,
        hat_verdichtung=verdichtet,
        offene_interviews=_offene_interviews(conn, chat_id),
    )


def leitfaden_nach_token(conn: sqlite3.Connection, token: str | None) -> dict | None:
    """Nur, was die Leitfaden-Ansicht braucht: Titel und die fuenf Felder,
    aus denen ``leitfaden.bausteine`` ihn setzt.

    Bewusst nicht ``gruppe_nach_token``: die Seite steht auf einem Telefon in
    der Hand einer Sechzehnjaehrigen, waehrend sie eine fremde Person
    anspricht -- sie soll Szenen, Interviews und Journal weder laden noch
    ausliefern. Weniger Daten heisst hier auch weniger, was auf dieser Seite
    stehen kann.

    None bei unbekanntem Token, wie ueberall: der Aufrufer antwortet mit
    404 und verraet nicht, ob es Gruppen gibt."""
    if not token:
        return None
    try:
        zeile = conn.execute(
            "SELECT chat_id, titel FROM gruppe WHERE web_token = ?", (token,)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if zeile is None:
        return None
    return {
        "chat_id": zeile["chat_id"],
        "titel": zeile["titel"],
        "arbeitsstand": _arbeitsstand(conn, zeile["chat_id"]),
    }


def stueckpruefung(conn: sqlite3.Connection, chat_id: int) -> dict:
    """Die letzte Pruefrunde des ganzen Stuecks (Phase 7, 06.09.2026) --
    **read-only**, wie alles auf dieser Seite.

    Liefert ``{"runde": N, "befunde": [{frage, bewertung, begruendung,
    vorschlag, szene_nummer}, …]}`` oder ``{}``, wenn noch keine Runde
    gelaufen ist. Der Befund ist ein Urteil ueber den EIGENEN Text der
    Gruppe -- kein Interviewmaterial, kein Zitat; er darf deshalb stehen, wo
    die Kurzformen stehen.

    Fehlt die Tabelle noch (Datenbank aus der Zeit davor), ist das Ergebnis
    leer statt ein Fehler: der Webserver migriert nichts."""
    try:
        zeilen = conn.execute(
            "SELECT * FROM stueckpruefung WHERE chat_id = ? "
            f"AND {_NICHT_ENTFERNT} ORDER BY runde ASC, id ASC",
            (chat_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    if not zeilen:
        return {}
    runde = max(z["runde"] for z in zeilen)
    return {
        "runde": runde,
        "befunde": [
            {
                "frage": z["frage"],
                "bewertung": z["bewertung"],
                "begruendung": z["begruendung"],
                "vorschlag": z["vorschlag"],
                "szene_nummer": z["szene_nummer"],
            }
            for z in zeilen if z["runde"] == runde
        ],
    }


def dramaturgie(conn: sqlite3.Connection, chat_id: int) -> dict:
    """Die Befunde der letzten Dramaturgie-Runde (06.09.2026) --
    **read-only**, wie alles auf dieser Seite.

    Liefert ``{"runde": N, "befunde": [{pruefung, szene, figur, schwere, text,
    vorschlag, quelle}, …]}`` oder ``{}``, wenn noch keine Runde gelaufen ist.

    **Ohne Belegzitat**, und zwar ohne jedes -- nicht nur ohne ungepruefte.
    Die Grenze auf dieser Seite lautet "kein Belegzitat ohne
    ``zitat_geprueft = 1``" (AGENTS.md, Weboberflaeche); hier faellt das
    Zitat ganz weg, weil es der Nachweis fuer den Code ist und nicht der Text
    fuer die Gruppe. Was auf der Seite steht, ist der Befund -- dass er
    belegt ist, ist die Zusage dahinter.

    Fehlt die Tabelle noch (Datenbank aus der Zeit davor), ist das Ergebnis
    leer statt ein Fehler: der Webserver migriert nichts."""
    try:
        zeilen = conn.execute(
            "SELECT * FROM dramaturgie_befund WHERE chat_id = ? "
            f"AND {_NICHT_ENTFERNT} ORDER BY runde ASC, id ASC",
            (chat_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    if not zeilen:
        return {}
    runde = max(z["runde"] for z in zeilen)
    return {
        "runde": runde,
        "befunde": [
            {
                "pruefung": z["pruefung"],
                "szene": z["szene"],
                "figur": z["figur"],
                "schwere": z["schwere"],
                "text": z["text"],
                "vorschlag": z["vorschlag"],
                "quelle": z["quelle"],
            }
            for z in zeilen if z["runde"] == runde
        ],
    }


# --- Der Web-Chat (30.09.2026, Karte Padua A2) -----------------------------

#: Wie viele Nachrichten die Chatansicht hoechstens auf einmal traegt. Ein
#: Workshoptag sind einige hundert; mehr als das braucht niemand auf einem
#: Telefon, und der Poll holt ohnehin nur das Neue (``nach``).
CHAT_GRENZE = 200

#: Was NICHT im Chat steht: der Umschalter-Druck, der als Slash-Text in den
#: Bot geht. Slash-Befehle werden nicht beworben (AGENTS.md) -- beworben wird
#: der Knopf, und der steht schon da.
_CHAT_VERBORGEN = ("befehl",)


def web_chatverlauf(conn, chat_id: int, nach: int = 0, grenze: int = CHAT_GRENZE) -> list:
    """Der Chatverlauf einer Web-Gruppe ab ``nach`` (exklusiv), aelteste zuerst.

    Geliefert wird genau das, was die Ansicht braucht -- **und der Dateipfad
    ist nicht dabei.** Er ist eine Serverinnerei, und die Seite ist ohne Login
    erreichbar (dieselbe Grenze wie 'kein Volltranskript auf der
    Gruppenseite')."""
    zeilen = conn.execute(
        "SELECT id, richtung, typ, text, knoepfe, dauer, dateiname, erstellt_am "
        "FROM web_post WHERE chat_id = ? AND id > ? AND geloescht_am IS NULL "
        f"AND typ NOT IN ({','.join('?' * len(_CHAT_VERBORGEN))}) "
        "AND typ != 'knopf' "
        "ORDER BY id ASC LIMIT ?",
        (chat_id, nach, *_CHAT_VERBORGEN, grenze),
    ).fetchall()
    return [
        {
            "id": int(z["id"]),
            "von": "bot" if z["richtung"] == "aus" else "gruppe",
            "typ": z["typ"],
            "text": z["text"],
            "knoepfe": _web_knoepfe(z["knoepfe"]),
            "dauer": z["dauer"],
            "dateiname": z["dateiname"],
            "zeit": z["erstellt_am"],
        }
        for z in zeilen
    ]


def _web_knoepfe(roh) -> list:
    """Dieselbe Deutung wie ``repo.web_knoepfe`` -- hier eigens, weil
    ``web_daten`` bewusst nicht von ``repo`` abhaengt (der Webserver soll
    keinen Schreibpfad importieren, siehe Moduldocstring)."""
    if not roh:
        return []
    try:
        gelesen = json.loads(roh)
    except (TypeError, ValueError):
        return []
    return [list(eintrag) for eintrag in gelesen if len(eintrag) == 2]


def web_chataenderungen(conn, chat_id: int, seit: int | None) -> tuple[list, int]:
    """Was sich an schon gelieferten Zeilen geaendert hat -- ``(zeilen, stand)``.

    ``WebKanal.aendere_text`` (die wechselnden Arbeitszeilen),
    ``entferne_knoepfe`` und ``loesche_nachrichten`` aendern Zeilen, deren id
    der Browser laengst hat; der Poll ueber ``nach`` saehe das nie. Jede
    solche Aenderung setzt ``web_post.aenderung`` (``repo``), und hier wird
    gefragt: alles mit einem Zaehler ueber ``seit``.

    ``stand`` ist der Wert, den der Browser beim naechsten Poll als ``seit``
    mitschickt. Er kommt aus DERSELBEN Abfrage wie die Zeilen: jede spaetere
    Aenderung bekommt einen hoeheren Wert, also geht nichts verloren. Ohne
    ``seit`` (Seitenaufbau) gibt es keine Zeilen, nur den Stand -- die Seite
    zeigt ohnehin schon den aktuellen Text.

    Eine Datenbank ohne die Spalte (der Webserver migriert nichts) liefert
    ``([], 0)`` statt eines Fehlers."""
    try:
        if seit is None:
            zeile = conn.execute(
                "SELECT COALESCE(MAX(aenderung), 0) AS stand FROM web_post "
                "WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
            return [], int(zeile["stand"])
        zeilen = conn.execute(
            "SELECT id, richtung, typ, text, knoepfe, dauer, dateiname, "
            "geloescht_am, aenderung FROM web_post "
            "WHERE chat_id = ? AND aenderung > ? "
            f"AND typ NOT IN ({','.join('?' * len(_CHAT_VERBORGEN))}) "
            "AND typ != 'knopf' ORDER BY aenderung ASC LIMIT ?",
            (chat_id, seit, *_CHAT_VERBORGEN, CHAT_GRENZE),
        ).fetchall()
    except sqlite3.OperationalError:
        return [], 0
    stand = max([seit, *(int(z["aenderung"]) for z in zeilen)])
    return [
        {
            "id": int(z["id"]),
            "von": "bot" if z["richtung"] == "aus" else "gruppe",
            "typ": z["typ"],
            "text": z["text"],
            "knoepfe": _web_knoepfe(z["knoepfe"]),
            "dauer": z["dauer"],
            "dateiname": z["dateiname"],
            "geloescht": z["geloescht_am"] is not None,
        }
        for z in zeilen
    ], stand


def web_chatzustand(conn, token: str, nach: int = 0,
                    seit: int | None = None) -> dict | None:
    """Alles, was der Browser bei einem Poll braucht -- oder None bei
    unbekanntem Token.

    Ein Aufruf statt vier: der Browser fragt alle zwei Sekunden, und vier
    Anfragen je Takt waeren bei drei Gruppen mit je zwei Telefonen
    sechsunddreissig Anfragen in der Minute fuer dieselbe Antwort.

    ``seit`` ist der Aenderungsstand des letzten Polls
    (``web_chataenderungen``); ``geaendert`` traegt, was sich an schon
    gelieferten Zeilen getan hat, ``aenderung`` den neuen Stand.

    Nur fuer Web-Gruppen (``web_chat_id_nach_token``, Abschlussreview I3)."""
    chat_id = web_chat_id_nach_token(conn, token)
    if chat_id is None:
        return None
    gruppe = conn.execute(
        "SELECT titel, interviewmodus_seit, web_tippt_bis FROM gruppe WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    # Der Aenderungsstand VOR dem Verlauf (Re-Review G): eine Aenderung
    # zwischen den beiden Abfragen steht dann entweder schon im Verlauf oder
    # kommt beim naechsten Poll -- verloren geht sie nicht.
    geaendert, stand_aenderung = web_chataenderungen(conn, chat_id, seit)
    nachrichten = web_chatverlauf(conn, chat_id, nach)
    letzte = nachrichten[-1]["id"] if nachrichten else nach
    # Phase wie web_daten.py:107 -- repo-frei, fehlende Spalte = None.
    stand = conn.execute(
        "SELECT * FROM arbeitsstand WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return {
        "chat_id": chat_id,
        "titel": gruppe["titel"] if gruppe else None,
        "phase": _feld(stand, "phase"),
        # Fuer den kontextabhaengigen Platzhalter im Eingabefeld
        # (UX-Knoepfe-Karte, Abschnitt 1) -- der Text selbst steht in
        # web_chat.py, hier nur der Rohwert, read-only wie der Rest.
        "fragen_aktuell": _feld(stand, "fragen_aktuell"),
        "interviewmodus": bool(gruppe and gruppe["interviewmodus_seit"]),
        "tippt": _tippt_noch(gruppe["web_tippt_bis"] if gruppe else None),
        "nachrichten": nachrichten,
        "letzte": letzte,
        "antworten": _web_antworten(conn, chat_id),
        "geaendert": geaendert,
        "aenderung": stand_aenderung,
        "segment_ms": None,   # setzt der HTML-Bau, nicht der Poll
    }


def _tippt_noch(bis_iso) -> bool:
    """Gilt die Tippanzeige noch? ``WebKanal.tippt`` setzt sie auf
    ``jetzt + TIPPT_GUELTIG_S``; ist der Zeitpunkt vorbei, schreibt gerade
    niemand mehr (und ein abgebrochener Lauf laesst sie nicht stehen)."""
    zeitpunkt = lies_zeitstempel(bis_iso)
    if zeitpunkt is None:
        return False
    return zeitpunkt > datetime.now(timezone.utc)


def _web_antworten(conn, chat_id: int) -> dict:
    """Die ``answerCallbackQuery``-Texte der letzten Knopfdruecke, nach
    Druck-id. In Telegram ist das die kleine Blase ueber dem Knopf; im
    Browser zeigt sie die Seite kurz unter der Leiste an."""
    zeilen = conn.execute(
        "SELECT id, antwort FROM web_post WHERE chat_id = ? AND typ = 'knopf' "
        "AND antwort IS NOT NULL ORDER BY id DESC LIMIT 5",
        (chat_id,),
    ).fetchall()
    return {str(int(z["id"])): z["antwort"] for z in zeilen}


def web_leiste(conn, chat_id: int, message_id: int) -> list | None:
    """Die Leiste, die gerade unter dieser Nachricht in DIESER Gruppe haengt --
    oder None, wenn es die Nachricht nicht gibt.

    Unterschied zwischen ``None`` und ``[]``: die Nachricht gibt es nicht
    gegen die Nachricht hat keine Knoepfe (mehr). Der Aufrufer antwortet auf
    beides mit 400, aber im Log soll der Unterschied stehen.

    ``chat_id`` in der Bedingung: dieselbe Datenbank traegt alle Gruppen des
    Workshops, und ein weitergegebener Link darf nie in fremde Daten
    schreiben (dieselbe Regel wie ``knoepfe.behandle``)."""
    zeile = conn.execute(
        "SELECT knoepfe FROM web_post WHERE id = ? AND chat_id = ? "
        "AND richtung = 'aus' AND geloescht_am IS NULL",
        (message_id, chat_id),
    ).fetchone()
    if zeile is None:
        return None
    return _web_knoepfe(zeile["knoepfe"])


def web_ausgangsdatei(conn, chat_id: int, post_id: int) -> dict | None:
    """Die Datei zu einer ``sende_datei``-Zeile (Textbuch-Export) -- Pfad und
    Name, oder None. Der Pfad bleibt serverseitig; die Route liefert den
    Inhalt aus, nicht den Ort."""
    zeile = conn.execute(
        "SELECT datei, dateiname FROM web_post WHERE id = ? AND chat_id = ? "
        "AND typ = 'datei' AND geloescht_am IS NULL",
        (post_id, chat_id),
    ).fetchone()
    if zeile is None or not zeile["datei"]:
        return None
    return {"pfad": zeile["datei"], "dateiname": zeile["dateiname"] or "datei"}
