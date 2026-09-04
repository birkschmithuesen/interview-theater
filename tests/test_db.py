import pytest
from interview_theater import db, phasen, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "test.db"))
    db.initialisiere(c)
    return c


def test_pragmas_sind_gesetzt(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_jede_tabelle_ausser_bot_zustand_hat_chat_id(conn):
    """Grundlage der Loeschzusage: keine Tabelle ohne chat_id."""
    tabellen = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    assert "gruppe" in tabellen
    for tabelle in tabellen:
        if tabelle == "bot_zustand":
            continue
        spalten = [r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")]
        assert "chat_id" in spalten, f"{tabelle} hat kein chat_id"


def test_alle_tabellen_stehen_in_der_loeschliste(conn):
    tabellen = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert tabellen - {"bot_zustand"} == set(db.TABELLEN_MIT_CHAT_ID)


def test_gruppe_hat_interviewmodus_seit_spalte(conn):
    """teil-b.md Aufgabe 5, SPEC § 10.1: Grundlage von aufnahme.klasse_fuer()."""
    spalten = [r[1] for r in conn.execute("PRAGMA table_info(gruppe)")]
    assert "interviewmodus_seit" in spalten


def test_gruppe_hat_web_token_spalte(conn):
    """Weboberflaeche (NACHTRAG N1-B): Zugang zur Gruppenseite laeuft ueber
    gruppe.web_token, es gibt kein Login."""
    spalten = [r[1] for r in conn.execute("PRAGMA table_info(gruppe)")]
    assert "web_token" in spalten


#: Die 'gruppe'-Tabelle, wie sie vor Aufgabe 5 aussah -- ohne
#: interviewmodus_seit. Fuer den Migrationstest unten bewusst hier hart
#: hinterlegt statt aus db.SCHEMA abgeleitet: der Test soll pruefen, dass
#: initialisiere() eine ECHTE Alt-Datenbank nachruestet, unabhaengig davon,
#: wie sich SCHEMA künftig weiterentwickelt.
_ALTE_GRUPPE_TABELLE = """
CREATE TABLE gruppe (
  chat_id                         INTEGER PRIMARY KEY,
  bot_name                        TEXT NOT NULL,
  titel                           TEXT,
  erste_nachricht_am              TEXT,
  letzte_beantwortete_message_id  INTEGER DEFAULT 0,
  letzte_extrahierte_message_id   INTEGER DEFAULT 0,
  wortlaut_modus                  TEXT,
  gruendlich_naechster_zug        INTEGER NOT NULL DEFAULT 0,
  whisper_stumm_seit              TEXT
);
"""


def test_migration_ergaenzt_fehlende_spalte_ohne_datenverlust(tmp_path):
    """Aufgabe 5, Auftragstest: initialisiere() muss auf einer Datenbank
    durchlaufen, der interviewmodus_seit fehlt (jede vor heute angelegte
    Datenbank) -- und darf dabei keine vorhandenen Daten verlieren. Die
    Migration ist allgemein (Soll- gegen Ist-Spalten, siehe
    db._migriere_fehlende_spalten), nicht auf genau diese eine Spalte
    zugeschnitten."""
    pfad = str(tmp_path / "alt.db")
    c = db.verbinde(pfad)
    c.executescript(_ALTE_GRUPPE_TABELLE)
    c.execute(
        "INSERT INTO gruppe (chat_id, bot_name, titel) VALUES (1, 'gruppe1', 'Testgruppe')"
    )
    c.commit()
    spalten_vorher = [r[1] for r in c.execute("PRAGMA table_info(gruppe)")]
    assert "interviewmodus_seit" not in spalten_vorher, "Testannahme: die Spalte fehlt wirklich"

    db.initialisiere(c)  # darf nicht krachen, obwohl 'gruppe' schon (alt) existiert

    spalten_nachher = [r[1] for r in c.execute("PRAGMA table_info(gruppe)")]
    assert "interviewmodus_seit" in spalten_nachher

    zeile = c.execute("SELECT * FROM gruppe WHERE chat_id = 1").fetchone()
    assert zeile["titel"] == "Testgruppe", "Migration darf keine Daten verlieren"
    assert zeile["bot_name"] == "gruppe1"
    assert zeile["interviewmodus_seit"] is None

    # Die nachgeruestete Spalte ist auch wirklich benutzbar.
    c.execute("UPDATE gruppe SET interviewmodus_seit = ? WHERE chat_id = 1", ("2026-09-05T10:00:00+00:00",))
    c.commit()
    assert c.execute(
        "SELECT interviewmodus_seit FROM gruppe WHERE chat_id = 1"
    ).fetchone()[0] == "2026-09-05T10:00:00+00:00"


def test_migration_ergaenzt_web_token_ohne_datenverlust(tmp_path):
    """Weboberflaeche: dieselbe Migration muss auch die neueste Spalte
    nachruesten -- eine Datenbank vom ersten Workshoptag kennt web_token
    nicht, ihre Nachrichten muessen den Nachruestlauf trotzdem ueberleben."""
    pfad = str(tmp_path / "alt.db")
    c = db.verbinde(pfad)
    c.executescript(_ALTE_GRUPPE_TABELLE)
    c.execute(
        "INSERT INTO gruppe (chat_id, bot_name, titel) VALUES (7, 'gruppe1', 'Gruppe Sieben')"
    )
    c.commit()
    assert "web_token" not in [r[1] for r in c.execute("PRAGMA table_info(gruppe)")], \
        "Testannahme: die Spalte fehlt wirklich"

    db.initialisiere(c)

    zeile = c.execute("SELECT * FROM gruppe WHERE chat_id = 7").fetchone()
    assert zeile["titel"] == "Gruppe Sieben", "Migration darf keine Daten verlieren"
    assert zeile["web_token"] is None, "nachgeruestet, aber noch nicht gefuellt"


#: Arbeitsstand, Figur, Szene und Journal, wie sie vor dem 04.09.2026
#: aussahen -- ohne phase/phase_angeboten und ohne entfernt_am. Wieder hart
#: hinterlegt, aus demselben Grund wie _ALTE_GRUPPE_TABELLE oben.
_ALTE_TABELLEN = """
CREATE TABLE arbeitsstand (
  chat_id                INTEGER PRIMARY KEY,
  begriffe               TEXT,
  kernthema              TEXT,
  kernthema_begruendung  TEXT,
  hauptkonflikt          TEXT,
  geaendert_am           TEXT
);
CREATE TABLE figur (
  id            INTEGER PRIMARY KEY,
  chat_id       INTEGER NOT NULL,
  name          TEXT NOT NULL,
  beschreibung  TEXT,
  beleg_zitat   TEXT,
  geaendert_am  TEXT
);
CREATE TABLE szene (
  id                INTEGER PRIMARY KEY,
  chat_id           INTEGER NOT NULL,
  nummer            INTEGER,
  titel             TEXT,
  kurzbeschreibung  TEXT,
  volltext          TEXT,
  geaendert_am      TEXT NOT NULL
);
CREATE TABLE journal (
  id                INTEGER PRIMARY KEY,
  chat_id           INTEGER NOT NULL,
  art               TEXT NOT NULL,
  text              TEXT NOT NULL,
  quelle            TEXT NOT NULL,
  bis_message_id    INTEGER,
  erstellt_am       TEXT NOT NULL
);
"""


def test_migration_ergaenzt_phase_und_entfernt_am_ohne_datenverlust(tmp_path):
    """Phasen (Brief A1) und weiches Loeschen (N3): eine Datenbank vom ersten
    Workshoptag kennt weder ``arbeitsstand.phase`` noch ``entfernt_am``. Ihre
    Figuren, Szenen und Journalzeilen muessen den Nachruestlauf ueberstehen --
    und danach als 'nicht entfernt' gelten, nicht als verschwunden."""
    c = db.verbinde(str(tmp_path / "alt.db"))
    c.executescript(_ALTE_TABELLEN)
    c.execute(
        "INSERT INTO arbeitsstand (chat_id, kernthema) VALUES (1, 'Ankommen')"
    )
    c.execute("INSERT INTO figur (chat_id, name, beschreibung) VALUES (1, 'Maria', 'Naeherin')")
    c.execute(
        "INSERT INTO szene (chat_id, nummer, titel, volltext, geaendert_am) "
        "VALUES (1, 1, 'Am Bahnhof', 'MARIA: Hier.', '2026-09-04T10:00:00+00:00')"
    )
    c.execute(
        "INSERT INTO journal (chat_id, art, text, quelle, erstellt_am) "
        "VALUES (1, 'entschieden', 'Kernthema ist Ankommen', 'erkenner', "
        "'2026-09-04T10:00:00+00:00')"
    )
    c.commit()
    for tabelle, spalte in (
        ("arbeitsstand", "phase"), ("figur", "entfernt_am"),
        ("szene", "entfernt_am"), ("journal", "entfernt_am"),
    ):
        vorhanden = [r[1] for r in c.execute(f"PRAGMA table_info({tabelle})")]
        assert spalte not in vorhanden, f"Testannahme: {tabelle}.{spalte} fehlt wirklich"

    db.initialisiere(c)

    stand = c.execute("SELECT * FROM arbeitsstand WHERE chat_id = 1").fetchone()
    assert stand["kernthema"] == "Ankommen", "Migration darf keine Daten verlieren"
    assert stand["phase"] is None and stand["phase_angeboten"] is None

    for tabelle in ("figur", "szene", "journal"):
        zeile = c.execute(f"SELECT * FROM {tabelle} WHERE chat_id = 1").fetchone()
        assert zeile["entfernt_am"] is None, tabelle

    # Und die alten Zeilen sind ueber repo weiterhin sichtbar -- das Filtern
    # nach 'entfernt_am IS NULL' darf sie nicht verschlucken.
    assert [f["name"] for f in repo.figuren(c, 1)] == ["Maria"]
    assert len(repo.hole_szenen(c, 1)) == 1
    assert len(repo.journal(c, 1)) == 1


# ---------------------------------------------------------------------------
# Acht Phasen wurden sieben (05.09.2026, db._migriere_phasennummern)
# ---------------------------------------------------------------------------


def _alte_phasen_db(tmp_path, name="acht.db"):
    """Eine Datenbank mit der achtstufigen Nummerierung: fuenf Gruppen, je
    eine Phase, ``user_version`` noch auf 0."""
    c = db.verbinde(str(tmp_path / name))
    db.initialisiere(c)
    for chat_id, phase, angeboten in (
        (1, 3, 4), (2, 5, 6), (3, 6, 7), (4, 7, 8), (5, 8, None),
    ):
        repo.sichere_gruppe(c, chat_id, "gruppe1", f"Gruppe {chat_id}")
        c.execute(
            "INSERT INTO arbeitsstand (chat_id, phase, phase_angeboten) VALUES (?, ?, ?)",
            (chat_id, phase, angeboten),
        )
    c.execute("PRAGMA user_version = 0")
    c.commit()
    return c


def test_phasennummern_werden_einmalig_umgerechnet(tmp_path):
    """Kernthema und Figuren sind eine Phase geworden, also rutscht alles
    darueber um eins herunter (db.PHASEN_UMNUMMERIERUNG). Ohne diesen Schritt
    saehe eine Gruppe, die abends bei '8 · Durchlauf' aufgehoert hat, am
    naechsten Morgen eine Nummer, die es nicht mehr gibt."""
    c = _alte_phasen_db(tmp_path)

    db.initialisiere(c)

    gelesen = {
        z["chat_id"]: (z["phase"], z["phase_angeboten"])
        for z in c.execute("SELECT * FROM arbeitsstand ORDER BY chat_id")
    }
    assert gelesen == {
        1: (3, 4),      # 1-3 bleiben, wo sie sind
        2: (4, 5),      # alt 5 (Figuren) -> neu 4 (Kernthema & Figuren)
        3: (5, 6),      # alt 6 (Hauptkonflikt) -> neu 5
        4: (6, 7),      # alt 7 (Szenen) -> neu 6
        5: (7, None),   # alt 8 (Durchlauf) -> neu 7, NULL bleibt NULL
    }


def test_jede_umgerechnete_nummer_ist_eine_gueltige_phase(tmp_path):
    """Die Probe aufs Ganze: nach der Migration gibt es zu jedem gespeicherten
    Wert auch einen Kurznamen -- sonst stuende auf der Gruppenseite eine nackte
    Zahl und ``anweisungen.system`` fiele ueber eine fehlende ``phasen/8.md``."""
    c = _alte_phasen_db(tmp_path)

    db.initialisiere(c)

    for z in c.execute("SELECT phase FROM arbeitsstand"):
        assert phasen.kurzname(z["phase"]), z["phase"]


def test_die_umrechnung_laeuft_nicht_zweimal(tmp_path):
    """``PRAGMA user_version`` ist der Merkposten. Ohne ihn wuerde jeder
    Prozessstart erneut umrechnen und eine Gruppe in Phase 7 Schritt fuer
    Schritt bis auf 4 herunterschieben."""
    c = _alte_phasen_db(tmp_path)

    db.initialisiere(c)
    db.initialisiere(c)
    db.initialisiere(c)

    assert c.execute("SELECT phase FROM arbeitsstand WHERE chat_id = 5").fetchone()[0] == 7
    assert c.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION


def test_eine_neue_datenbank_ist_sofort_auf_dem_aktuellen_stand(tmp_path):
    c = db.verbinde(str(tmp_path / "neu.db"))

    db.initialisiere(c)

    assert c.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION


def test_das_journal_wird_nicht_umgeschrieben(tmp_path):
    """Im Journal steht, was die Gruppe damals entschieden hat -- und 'Phase
    5 · Figuren' war am 04.09. wahr. Ein Journal wird nur angehaengt, nie
    umgeschrieben (AGENTS.md)."""
    c = _alte_phasen_db(tmp_path)
    repo.schreibe_journal(c, 1, "entschieden", "Phase 5 · Figuren", "befehl")

    db.initialisiere(c)

    assert repo.journal(c, 1)[-1]["text"] == "Phase 5 · Figuren"


#: Die 'aufnahme'-Tabelle, wie sie vor dem 05.09.2026 aussah -- ohne
#: teil_von und beendet_am. Hart hinterlegt, aus demselben Grund wie
#: _ALTE_GRUPPE_TABELLE.
_ALTE_AUFNAHME_TABELLE = """
CREATE TABLE aufnahme (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  message_id      INTEGER NOT NULL,
  name            TEXT,
  klasse          TEXT NOT NULL,
  quelle          TEXT NOT NULL,
  audio_pfad      TEXT,
  transkript      TEXT,
  dauer_sekunden  INTEGER,
  status          TEXT NOT NULL,
  fehlertext      TEXT,
  versuche        INTEGER NOT NULL DEFAULT 0,
  empfangen_am    TEXT NOT NULL
);
CREATE TABLE verdichtung (
  id               INTEGER PRIMARY KEY,
  chat_id          INTEGER NOT NULL,
  aufnahme_id      INTEGER NOT NULL,
  zusammenfassung  TEXT NOT NULL,
  erstellt_am      TEXT NOT NULL
);
"""


def test_migration_macht_aus_jeder_alten_lang_aufnahme_ein_interview(tmp_path):
    """§ 10.6, Migration: eine Datenbank aus der Zeit vor dem Nachtrag kennt
    weder ``teil_von`` noch ``beendet_am``. Ihre Aufnahmen der Klasse *lang*
    werden dadurch je zu einem Interview mit genau einem Teil -- ihrem
    eigenen Transkript, das ``zusammengefuegtes_transkript`` weiterhin
    liefert. Nichts geht verloren, die Verdichtungen bleiben."""
    c = db.verbinde(str(tmp_path / "alt.db"))
    c.executescript(_ALTE_AUFNAHME_TABELLE)
    c.execute(
        "INSERT INTO aufnahme (chat_id, message_id, name, klasse, quelle, transkript, "
        "dauer_sekunden, status, empfangen_am) VALUES "
        "(1, 14, 'Interview 6', 'lang', 'sprache', 'Ich bin 1998 gekommen.', 120, "
        "'fertig', '2026-09-04T20:00:00+00:00')"
    )
    c.execute(
        "INSERT INTO verdichtung (chat_id, aufnahme_id, zusammenfassung, erstellt_am) "
        "VALUES (1, 1, 'Erzaehlung vom Ankommen', '2026-09-04T20:01:00+00:00')"
    )
    c.commit()
    vorhanden = [r[1] for r in c.execute("PRAGMA table_info(aufnahme)")]
    assert "teil_von" not in vorhanden, "Testannahme: die Spalte fehlt wirklich"

    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")

    zeile = repo.hole_aufnahme(c, 1)
    assert zeile["name"] == "Interview 6"
    assert zeile["teil_von"] is None and zeile["beendet_am"] is None
    assert repo.zusammengefuegtes_transkript(c, 1) == "Ich bin 1998 gekommen."
    assert [a["id"] for a in repo.transkripte(c, 1)] == [1]
    assert len(repo.verdichtungen(c, 1)) == 1

    # Und die Zaehlung geht dort weiter, wo die alte Datenbank aufgehoert hat.
    assert repo.hole_aufnahme(c, repo.lege_interview_an(c, 1))["name"] == "Interview 2"


def test_migration_ist_ein_no_op_wenn_alle_spalten_schon_da_sind(conn):
    """Ein zweiter initialisiere()-Lauf auf einer schon aktuellen Datenbank
    darf nicht krachen (kein ALTER TABLE auf eine schon vorhandene Spalte)."""
    db.initialisiere(conn)  # zweiter Lauf, darf keine Ausnahme werfen
    spalten = [r[1] for r in conn.execute("PRAGMA table_info(gruppe)")]
    assert "interviewmodus_seit" in spalten


def test_loeschen_raeumt_die_gruppe(conn):
    conn.execute("INSERT INTO gruppe (chat_id, bot_name) VALUES (42, 'g1')")
    conn.execute("INSERT INTO nachricht (chat_id, message_id, typ, gesendet_am) "
                 "VALUES (42, 1, 'text', '2026-09-05T10:00:00')")
    conn.commit()
    db.loesche_gruppe(conn, 42)
    assert conn.execute("SELECT count(*) FROM nachricht").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM gruppe").fetchone()[0] == 0
