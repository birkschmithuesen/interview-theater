"""Datenbankschema und Verbindungsaufbau (SPEC-kontext-architektur.md § 3.1)."""

import re
import sqlite3

# Woertlich aus SPEC-kontext-architektur.md § 3.1 uebernommen, nur um
# "IF NOT EXISTS" ergaenzt, damit initialisiere() gefahrlos mehrfach laufen kann.
SCHEMA = """
-- Pro Bot-Token, nicht pro Gruppe: die getUpdates-Position
CREATE TABLE IF NOT EXISTS bot_zustand (
  bot_name              TEXT PRIMARY KEY,
  letzte_update_id      INTEGER,
  gestartet_am          TEXT,
  letzte_aktivitaet_am  TEXT
);

CREATE TABLE IF NOT EXISTS gruppe (
  chat_id                         INTEGER PRIMARY KEY,
  bot_name                        TEXT NOT NULL,
  titel                           TEXT,
  erste_nachricht_am              TEXT,
  -- Antwort- und Extraktionsstand
  letzte_beantwortete_message_id  INTEGER DEFAULT 0,
  letzte_extrahierte_message_id   INTEGER DEFAULT 0,
  -- Journal-Extraktor-Wasserzeichen (Verdraengung statt jedem Zug, siehe journal.py)
  letzte_journalisierte_message_id INTEGER DEFAULT 0,
  -- Schalter
  wortlaut_modus                  TEXT,     -- NULL=aus, '*'=alle, sonst Aufnahmename
  szene_usa_bestaetigt_am         TEXT,     -- gesetzt = Gruppe hat dem US-Modell fuer Szenen zugestimmt (05.09.)
  szene_usa_angeboten_am          TEXT,     -- gesetzt = der Bot hat den Wechsel schon vorgeschlagen
  szene_usa_offener_auftrag       TEXT,     -- der Szenenauftrag, der auf die Antwort wartet
  gruendlich_naechster_zug        INTEGER NOT NULL DEFAULT 0,  -- Modus B einmalig (§ 4.5)
  whisper_stumm_seit              TEXT,     -- gesetzt = Ausfall gemeldet (§ 10.4)
  interviewmodus_seit             TEXT,     -- gesetzt = Interviewmodus an (teil-b.md Aufgabe 5, § 10.1)
  -- Zufallstoken fuer die Gruppenseite /g/<token> der Weboberflaeche
  -- (NACHTRAG-weboberflaeche-und-sprache.md N1-B): kein Login, wer die URL
  -- hat, sieht die Gruppe. Erzeugt der Bot (repo.stelle_web_token_sicher),
  -- weil der Webserver die Datenbank read-only oeffnet.
  web_token                       TEXT
);

CREATE TABLE IF NOT EXISTS nachricht (
  chat_id        INTEGER NOT NULL,
  message_id     INTEGER NOT NULL,
  telegram_user  INTEGER,
  absender       TEXT,                      -- Vorname oder 'Bot'
  ist_bot        INTEGER NOT NULL DEFAULT 0,
  -- text|sprache|foto|sticker|sonstiges|transkript
  -- 'transkript' ist das Echo eines Interview-Teils, das der Bot zur
  -- Kontrolle in den Chat schreibt (§ 10.6). Es wird gespeichert wie jede
  -- andere Nachricht, geht aber weder ins Erkenner- noch ins
  -- Gespraechsfenster: Interviewinhalt ist nicht Gruppenabsicht.
  typ            TEXT NOT NULL,
  text           TEXT,
  gesendet_am    TEXT NOT NULL,             -- ISO 8601
  unterdrueckt   INTEGER NOT NULL DEFAULT 0,-- 1 = nie Antwort auslösen (Nachtstau)
  PRIMARY KEY (chat_id, message_id)
);
CREATE INDEX IF NOT EXISTS idx_nachricht_zeit ON nachricht(chat_id, message_id);

-- Sprachaufnahmen UND Textimporte. Eine Statusmaschine fuer beides (§ 10).
--
-- Ein Interview ist eine Einheit (Nachtrag 05.09.2026, § 10.6): der KOPF
-- (klasse='lang', teil_von NULL) traegt Name, zusammengefuegtes Transkript
-- und Verdichtung, jede einzelne Sprachnachricht dazu ist ein TEIL
-- (klasse='teil', teil_von = id des Kopfes) mit eigener Audiodatei und
-- eigenem Transkript. Additiv: bestehende Zeilen haben teil_von NULL und
-- bleiben damit je ein eigenstaendiges Interview mit Transkript am Kopf.
CREATE TABLE IF NOT EXISTS aufnahme (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  message_id      INTEGER NOT NULL,
  name            TEXT,                     -- 'Maria'; Ersatz: 'Interview 3'
  klasse          TEXT NOT NULL,            -- kurz (Gespraechsbeitrag) | lang (Interview-Kopf) | teil (eine Sprachnachricht darin)
  quelle          TEXT NOT NULL,            -- sprache | text
  audio_pfad      TEXT,                     -- NULL bei quelle='text' und beim Kopf
  transkript      TEXT,
  dauer_sekunden  INTEGER,
  status          TEXT NOT NULL,            -- laeuft|empfangen|transkribiert|fertig|fehlgeschlagen
  fehlertext      TEXT,
  versuche        INTEGER NOT NULL DEFAULT 0,
  empfangen_am    TEXT NOT NULL,
  -- Gesetzt = diese Zeile ist ein Teil des Interviews mit dieser id.
  teil_von        INTEGER,
  -- Gesetzt = die Gruppe hat "fertig" gesagt. Ein Kopf mit beendet_am und
  -- status='laeuft' wartet nur noch darauf, dass seine Teile durch sind
  -- (aufnahme.schliesse_ab, aufgegriffen vom Nachhol-Arbeiter).
  beendet_am      TEXT,
  -- Gesetzt = weich geloescht (N5, 05.09.2026). Die Material-Sperre gilt fuer
  -- Aufnahmen der Gruppe, die Inhalt tragen; ein halluziniertes oder
  -- versehentliches Interview ist entfernbar, wenn die Gruppe es sagt. Die
  -- Audiodatei bleibt auf der Platte -- die Loeschzusage erfuellt weiterhin
  -- allein scripts/loeschen.py.
  entfernt_am     TEXT
);
-- Bewusst KEIN Index auf teil_von: initialisiere() faehrt erst das ganze
-- SCHEMA und ergaenzt danach fehlende Spalten -- ein Index auf eine Spalte,
-- die es in einer Alt-Datenbank noch nicht gibt, liesse den Start mit
-- "no such column: teil_von" scheitern, bevor die Migration ueberhaupt
-- laeuft. Ein Workshop-Wochenende bringt Dutzende Aufnahmen, keine
-- Millionen.
CREATE INDEX IF NOT EXISTS idx_aufnahme_offen ON aufnahme(status);

CREATE TABLE IF NOT EXISTS verdichtung (
  id               INTEGER PRIMARY KEY,
  chat_id          INTEGER NOT NULL,
  aufnahme_id      INTEGER NOT NULL,
  zusammenfassung  TEXT NOT NULL,
  erstellt_am      TEXT NOT NULL,
  -- Gesetzt = weich geloescht (N5): faellt mit dem Interview, zu dem sie
  -- gehoert. Geaendert wird eine Verdichtung weiterhin nie -- ausser durch
  -- eine Transkriptkorrektur, die dieselbe Ersetzung ueberall vornimmt.
  entfernt_am      TEXT
);

CREATE TABLE IF NOT EXISTS verdichtung_thema (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  verdichtung_id  INTEGER NOT NULL,
  thema           TEXT NOT NULL,
  -- Dasselbe Ergebnis in höchstens acht Wörtern (N3/N6): die Kurzform, aus
  -- der die Summary-Zeile je Interview auf der Gruppenseite und die eine
  -- Zeile je Interview auf dem Dashboard entstehen. Additiv; fehlt sie,
  -- zeigen beide Ansichten `thema`.
  kurz            TEXT,
  beleg_zitat     TEXT,                     -- NULL, wenn Prüfung nach § 5 fehlschlug
  zitat_geprueft  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS arbeitsstand (
  chat_id                INTEGER PRIMARY KEY,
  begriffe               TEXT,
  -- Die Interviewfragen als eine Liste in einem Feld (Phase 2, Korrektur vom
  -- 04.09.2026 abends): Fragen formulieren und Interviews fuehren sind zwei
  -- Arbeiten. Additiv wie phase -- eine bestehende Datenbank bekommt die
  -- Spalte ueber _migriere_fehlende_spalten.
  fragen                 TEXT,
  kernthema              TEXT,
  kernthema_begruendung  TEXT,
  -- Phase 5 heisst seit dem 05.09.2026 "Format & Rahmen" (Birk: "Es muss
  -- nicht immer einen Konflikt geben -- es kann ein Lied sein oder eine
  -- harmonische Liebesszene. Das Ganze wird vermutlich ein Musical.").
  -- ``format``: was entsteht und welche Formen vorkommen duerfen, als ein
  -- Text ("Musical: Dialog, Lied, Rap"). ``rahmen``: worin es spielt --
  -- Ort(e), Zeit, Anlass, roter Faden.
  format                 TEXT,
  rahmen                 TEXT,
  -- Bleibt als OPTIONALES Feld: ein durchgehender Konflikt ist eine
  -- Rahmen-Entscheidung, keine Pflicht. Gesetzt wird er weiter ueber
  -- hauptkonflikt_setzen; /stand und Web zeigen ihn nur, wenn er dasteht.
  hauptkonflikt          TEXT,
  -- Die Arbeitsphase 1-7 (interview_theater/phasen.py). NULL = noch nie gesetzt
  -- und gilt dann wie 1. Gesetzt wird sie ausschliesslich von der Gruppe
  -- (phase_setzen, /phase) -- nie still erraten, und seit dem 05.09.2026 auch
  -- nicht mehr vom Bot selbst (SPEC § 0 Leitsatz 3, Nachtrag).
  -- Alt-Datenbanken tragen hier noch die achtstufige Nummerierung; sie wird
  -- einmalig umgerechnet, siehe _migriere_phasennummern.
  phase                  INTEGER,
  -- Zuletzt angebotene Phase: verhindert, dass der Hinweisblock in
  -- kontext.baue jeden Zug erneut nach demselben Wechsel fragt.
  phase_angeboten        INTEGER,
  geaendert_am           TEXT
);

-- Das Sprachprofil (05.09.2026, Birk: "das ist das Wichtigste") ist der
-- Grund, warum sich zwei Figuren im Szenentext hoerbar unterscheiden:
-- ``sprachprofil`` ist die Analyse (Satzlaenge, Fuellwoerter, Abbrueche,
-- Dialekt/Fremdsprache, Tempo -- 3-5 Zeilen), ``zitate`` sind 3-5 woertliche
-- Saetze aus dem Interview, `|`-getrennt, die als Few-Shots fuer die
-- Sprechweise in den Szenen-Prompt gehen. ``quelle_aufnahme_id`` haelt fest,
-- aus welchem Interview beides stammt -- die Zuordnung schlaegt der Bot vor,
-- die Gruppe nickt sie ab (Erkenner-art figur_quelle_setzen).
CREATE TABLE IF NOT EXISTS figur (
  id                  INTEGER PRIMARY KEY,
  chat_id             INTEGER NOT NULL,
  name                TEXT NOT NULL,
  beschreibung        TEXT,
  beleg_zitat         TEXT,
  sprachprofil        TEXT,
  zitate              TEXT,
  quelle_aufnahme_id  INTEGER,
  geaendert_am        TEXT,
  entfernt_am         TEXT                  -- gesetzt = weich geloescht (N3)
);

-- Eine Szene ist seit dem 05.09.2026 zuerst eine PLANUNG und erst danach ein
-- Text (Birk, Ping-Pong 04.09. abends). Die Felder unten sind das, was die
-- Gruppe entscheidet, bevor geschrieben wird; der Bot schlaegt sie alle vor
-- (auch die Form), durchgesetzt wird nichts.
--
-- Pflicht fuer den Szenen-Aufruf sind form, ort, figuren und was_passiert
-- (szene.PFLICHTFELDER, Sperre in T5); der Rest ist optional. Es gibt
-- bewusst KEIN Feld "Funke" und keinen Konflikt je Szene -- eine Szene darf
-- ein Lied sein.
CREATE TABLE IF NOT EXISTS szene (
  id                INTEGER PRIMARY KEY,
  chat_id           INTEGER NOT NULL,
  nummer            INTEGER,
  titel             TEXT,
  kurzbeschreibung  TEXT,                   -- eine Zeile, geht immer mit
  -- Dialog | Lied | Rap | Monolog | Chor | stumm (frei, aber diese Namen
  -- bevorzugt). Entscheidet, welcher Formen-Block in den Szenen-Prompt geht
  -- (prompts/formen/<form>.md).
  form              TEXT,
  ort               TEXT,
  zeit              TEXT,                   -- Tageszeit, "danach", "am nächsten Morgen"
  anlass            TEXT,                   -- warum sind sie hier
  was_passiert      TEXT,                   -- 1-3 Sätze Handlung
  was_anders        TEXT,                   -- was am Ende anders ist als am Anfang
  kernsaetze        TEXT,                   -- Sätze, die wörtlich vorkommen sollen
  ton               TEXT,                   -- Register: leise, komisch, harmonisch, hitzig
  volltext          TEXT,                   -- nur die zuletzt geänderte Szene geht mit
  geaendert_am      TEXT NOT NULL,
  entfernt_am       TEXT                    -- gesetzt = weich geloescht (N3)
);
CREATE INDEX IF NOT EXISTS idx_szene_aktuell ON szene(chat_id, geaendert_am DESC);

-- Wer in einer Szene vorkommt: nur Figuren aus dem Arbeitsstand, deshalb eine
-- Verknuepfung und keine Namensliste in einem Textfeld. Eine weich geloeschte
-- Figur verschwindet damit von selbst aus jeder Szene (repo.szene_figuren
-- filtert ueber figur.entfernt_am), ohne dass irgendwo aufgeraeumt werden
-- muesste.
CREATE TABLE IF NOT EXISTS szene_figur (
  chat_id    INTEGER NOT NULL,
  szene_id   INTEGER NOT NULL,
  figur_id   INTEGER NOT NULL,
  PRIMARY KEY (szene_id, figur_id)
);

CREATE TABLE IF NOT EXISTS journal (
  id                INTEGER PRIMARY KEY,
  chat_id           INTEGER NOT NULL,
  art               TEXT NOT NULL,          -- vorgeschlagen|verworfen|entschieden|offen
  text              TEXT NOT NULL,
  quelle            TEXT NOT NULL,          -- extraktor|befehl
  bis_message_id    INTEGER,
  erstellt_am       TEXT NOT NULL,
  -- Weiches Loeschen (NACHTRAG-weboberflaeche-und-sprache.md N3): das Journal
  -- bleibt nur-anhaengend, ein zurueckgenommener Eintrag wird nicht geloescht,
  -- sondern hier gestempelt -- und ein neuer Eintrag "Zurueckgenommen: ..."
  -- haelt den Weg sichtbar.
  entfernt_am       TEXT
);
CREATE INDEX IF NOT EXISTS idx_journal_chat ON journal(chat_id, id);

-- Inline-Knoepfe (05.09.2026, interview_theater/knoepfe.py).
--
-- Warum eine eigene Tabelle: Telegram begrenzt `callback_data` auf 64 Bytes.
-- Ein Kernthema-Vorschlag ist regelmaessig laenger als das -- also traegt der
-- Knopf nur seine eigene id (`k:<id>`, hoechstens 21 Bytes), und der
-- eigentliche Wert steht hier. Damit steht ausserdem KEIN Inhalt der Gruppe
-- in einem Feld, das ueber Telegram-Buttons hin- und herwandert.
--
-- `benutzt_am` ist die Idempotenz-Sperre: der Druck wird per
-- `UPDATE ... WHERE benutzt_am IS NULL` beansprucht, und nur wer diesen einen
-- UPDATE gewinnt, fuehrt die Wirkung aus. Zweimal tippen (oder zwei Leute
-- gleichzeitig) legt damit nichts doppelt an.
CREATE TABLE IF NOT EXISTS knopf (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER NOT NULL,
  art          TEXT NOT NULL,            -- kernthema|aufnahme|phase|format|
                                          -- szenenform|szene_usa
  wert         TEXT,                     -- Kernthema-Volltext, Phasennummer,
                                          -- Format, "<nr>:<form>" bzw. ja|nein
  erstellt_am  TEXT NOT NULL,
  benutzt_am   TEXT                      -- gesetzt = schon gedrueckt
);
CREATE INDEX IF NOT EXISTS idx_knopf_chat ON knopf(chat_id, id);

-- Was das Dashboard rot färbt
CREATE TABLE IF NOT EXISTS vorfall (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER,                     -- NULL bei bot-weiten Vorfällen
  bot_name     TEXT,
  art          TEXT NOT NULL,               -- kuerzung|fenster_verworfen|extraktor_fehler|
                                            -- zitat_ungeprueft|http_5xx|abgeschnitten|…
  stufe        INTEGER,
  detail       TEXT,
  erstellt_am  TEXT NOT NULL
);

-- Selbstkorrektur der Token-Schätzung
CREATE TABLE IF NOT EXISTS aufruf (
  id                     INTEGER PRIMARY KEY,
  chat_id                INTEGER,
  art                    TEXT NOT NULL,     -- gespraech|verdichter|extraktor
  modus                  TEXT,              -- A|B
  geschaetzte_token      INTEGER,
  tatsaechliche_token    INTEGER,           -- usage.prompt_tokens
  antwort_token          INTEGER,
  finish_reason          TEXT,
  dauer_ms               INTEGER,
  erfolg                 INTEGER,
  erstellt_am            TEXT NOT NULL
);
"""

# Alle Tabellen mit chat_id -- Grundlage der Loeschzusage (§ 3, global-constraints.md).
TABELLEN_MIT_CHAT_ID = (
    "gruppe",
    "nachricht",
    "aufnahme",
    "verdichtung",
    "verdichtung_thema",
    "arbeitsstand",
    "figur",
    "szene",
    "szene_figur",
    "journal",
    "knopf",
    "vorfall",
    "aufruf",
)


def verbinde(pfad: str) -> sqlite3.Connection:
    """Baut eine Verbindung mit den projektweiten PRAGMAs auf (global-constraints.md § 3)."""
    conn = sqlite3.connect(pfad, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


#: Zeilenanfaenge, die keine Spalte sind, sondern eine Tabellen-Constraint
#: (z. B. ``PRIMARY KEY (chat_id, message_id)`` in ``nachricht``) -- die
#: Migration unten darf so eine Zeile nicht als fehlende Spalte missverstehen
#: und per ALTER TABLE anzulegen versuchen.
_KEINE_SPALTE_PRAEFIXE = ("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "CONSTRAINT")


def _tabellenspalten_aus_schema() -> dict[str, list[tuple[str, str]]]:
    """Liest Tabellen- und Sollspalten direkt aus SCHEMA statt aus einem
    zweiten, von Hand gepflegten Katalog -- der koennte sonst aus dem Tritt
    geraten, sobald jemand nur SCHEMA aendert. Liefert je Tabelle eine Liste
    aus (Spaltenname, Rest-Definition-fuer-ALTER-TABLE)."""
    ergebnis: dict[str, list[tuple[str, str]]] = {}
    for tabelle, koerper in re.findall(
        r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", SCHEMA, re.DOTALL
    ):
        spalten = []
        for zeile in koerper.splitlines():
            zeile = zeile.split("--", 1)[0].strip().rstrip(",")
            if not zeile or zeile.upper().startswith(_KEINE_SPALTE_PRAEFIXE):
                continue
            name, _, definition = zeile.partition(" ")
            spalten.append((name, definition.strip()))
        ergebnis[tabelle] = spalten
    return ergebnis


def _migriere_fehlende_spalten(conn: sqlite3.Connection) -> None:
    """Ergaenzt in einer schon bestehenden Datenbank Spalten, die im SCHEMA
    seither hinzugekommen sind (z. B. gruppe.interviewmodus_seit, teil-b.md
    Aufgabe 5) -- per ``ALTER TABLE ... ADD COLUMN``, allgemein anhand eines
    Vergleichs Soll- (SCHEMA) gegen Ist-Spalten (``PRAGMA table_info``), nicht
    als Einzelfall fuer genau eine Spalte. Ohne das braeche jede Datenbank,
    die vor einer Schemaerweiterung angelegt wurde -- schon vorhandene Spalten
    werden stillschweigend uebersprungen."""
    for tabelle, spalten in _tabellenspalten_aus_schema().items():
        vorhandene = {zeile[1] for zeile in conn.execute(f"PRAGMA table_info({tabelle})")}
        for name, definition in spalten:
            if name in vorhandene:
                continue
            conn.execute(f"ALTER TABLE {tabelle} ADD COLUMN {name} {definition}")
    conn.commit()


#: Schemastand dieser Codefassung, gespeichert in ``PRAGMA user_version``.
#: ``0`` ist eine Datenbank aus der Zeit vor der Umnummerierung der
#: Arbeitsphasen (05.09.2026). Bewusst SQLites eingebauter Zaehler und keine
#: eigene Tabelle: er kostet keine Zeile, keine Migration und kein Schema.
SCHEMA_VERSION = 1

#: Acht Phasen wurden sieben (Birk, 05.09.2026): Kernthema und Figuren sind
#: EINE Phase geworden, alles darueber rutscht um eins nach unten. 1-4 bleiben,
#: wo sie sind -- aus alt 4 (Kernthema) wird das neue 4 (Kernthema & Figuren),
#: aus alt 5 (Figuren) ebenfalls. Alt -> neu, siehe
#: interview_theater/phasen.py.
PHASEN_UMNUMMERIERUNG = {5: 4, 6: 5, 7: 6, 8: 7}


def _migriere_phasennummern(conn: sqlite3.Connection) -> None:
    """Rechnet gespeicherte Phasennummern einmalig auf das siebenstufige
    Modell um (PHASEN_UMNUMMERIERUNG).

    Betrifft ``arbeitsstand.phase`` und ``arbeitsstand.phase_angeboten``:
    ohne diesen Schritt saehe eine Gruppe, die abends bei "8 · Durchlauf"
    aufgehoert hat, am naechsten Morgen eine Phasennummer, die es nicht mehr
    gibt -- und der Prompt-Zusatz dazu fehlte ersatzlos.

    Ein einziges UPDATE je Spalte mit CASE, damit die Umrechnung nicht ueber
    mehrere Schritte kaskadiert (5 -> 4, danach 6 -> 5 wuerde sonst die
    gerade geschriebenen Zeilen wieder anfassen, sobald jemand die Tabelle
    einmal umsortiert).

    Das Journal bleibt unberuehrt: dort steht, was die Gruppe damals
    entschieden hat ("Phase 5 · Figuren"), und das ist auch nach der
    Umnummerierung wahr -- ein Journal wird nur angehaengt, nie umgeschrieben
    (AGENTS.md)."""
    if conn.execute("PRAGMA user_version").fetchone()[0] >= SCHEMA_VERSION:
        return
    faelle = " ".join(f"WHEN {alt} THEN {neu}" for alt, neu in PHASEN_UMNUMMERIERUNG.items())
    betroffen = ", ".join(str(alt) for alt in PHASEN_UMNUMMERIERUNG)
    for spalte in ("phase", "phase_angeboten"):
        conn.execute(
            f"UPDATE arbeitsstand SET {spalte} = CASE {spalte} {faelle} END "
            f"WHERE {spalte} IN ({betroffen})"
        )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def initialisiere(conn: sqlite3.Connection) -> None:
    """Legt das Schema an, falls noch nicht vorhanden, ergaenzt in einer schon
    vorhandenen Datenbank fehlende Spalten (siehe _migriere_fehlende_spalten)
    und rechnet einmalig die Phasennummern um (_migriere_phasennummern).

    Reihenfolge: erst die Spalten, dann ihr Inhalt -- ``phase_angeboten``
    koennte in einer sehr alten Datenbank noch gar nicht existieren."""
    conn.executescript(SCHEMA)
    conn.commit()
    _migriere_fehlende_spalten(conn)
    _migriere_phasennummern(conn)


def loesche_gruppe(conn: sqlite3.Connection, chat_id: int) -> None:
    """Loescht alle Datensaetze einer Gruppe (Loeschzusage). Das Audioverzeichnis
    liegt ausserhalb der Datenbank und wird von scripts/loeschen.py entfernt."""
    for tabelle in TABELLEN_MIT_CHAT_ID:
        conn.execute(f"DELETE FROM {tabelle} WHERE chat_id = ?", (chat_id,))
    conn.commit()
