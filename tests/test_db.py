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


def test_interviews_fertig_wunsch_spalte_existiert_und_ist_schreibbar(conn):
    """Der Merkposten fuer den Web-Knopf "Interviews fertig" (02.10.2026):
    additiv nachgeruestete Spalte im Arbeitsstand, ueber denselben einen
    Schreibweg wie alles andere dort (repo.setze_arbeitsstand)."""
    db._migriere_fehlende_spalten(conn)
    spalten = {z[1] for z in conn.execute("PRAGMA table_info(arbeitsstand)")}
    assert "interviews_fertig_wunsch_seit" in spalten
    repo.setze_arbeitsstand(conn, 1, "interviews_fertig_wunsch_seit", "2026-10-02T12:00:00+00:00")
    assert repo.hole_arbeitsstand(conn, 1)["interviews_fertig_wunsch_seit"] == "2026-10-02T12:00:00+00:00"


def test_geschichte_uebersicht_und_entwurf_bestaetigt_spalten_existieren(conn):
    """Padua Phasen TEIL 1 (03.10.2026): die Uebersicht aus Stufe A des
    zweistufigen Phase-5-Entwurfs (arbeitsstand) und die Abnahme eines
    Szenen-Prosaentwurfs in Stufe B (szene) -- beide additiv nachgeruestet,
    ueber denselben Schreibweg wie alles andere im Arbeitsstand bzw. ueber
    den eigenen Zeitstempel-Setter fuer die Szene."""
    db._migriere_fehlende_spalten(conn)
    arbeitsstand_spalten = {z[1] for z in conn.execute("PRAGMA table_info(arbeitsstand)")}
    szene_spalten = {z[1] for z in conn.execute("PRAGMA table_info(szene)")}
    assert "geschichte_uebersicht" in arbeitsstand_spalten
    assert "geschichte_uebersicht_szenen" in arbeitsstand_spalten
    assert "geschichte_uebersicht_fixiert_am" in arbeitsstand_spalten
    assert "entwurf_bestaetigt_am" in szene_spalten

    repo.setze_arbeitsstand(conn, 1, "geschichte_uebersicht", "Logline. Setting. Figuren.")
    repo.setze_arbeitsstand(conn, 1, "geschichte_uebersicht_szenen", "Szene 1: ...\nSzene 2: ...")
    repo.setze_arbeitsstand(conn, 1, "geschichte_uebersicht_fixiert_am", "2026-10-03T12:00:00+00:00")
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["geschichte_uebersicht"] == "Logline. Setting. Figuren."
    assert stand["geschichte_uebersicht_szenen"] == "Szene 1: ...\nSzene 2: ..."
    assert stand["geschichte_uebersicht_fixiert_am"] == "2026-10-03T12:00:00+00:00"

    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    assert conn.execute(
        "SELECT entwurf_bestaetigt_am FROM szene WHERE id = ?", (szene_id,)
    ).fetchone()[0] is None
    repo.setze_szene_entwurf_bestaetigt(conn, szene_id, "2026-10-03T12:05:00+00:00")
    assert conn.execute(
        "SELECT entwurf_bestaetigt_am FROM szene WHERE id = ?", (szene_id,)
    ).fetchone()[0] == "2026-10-03T12:05:00+00:00"


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
# Phasennummern-Migration (db._migriere_phasennummern), drei Stufen
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
    """Eine Datenbank aus der Zeit vor ALLEN Umbauten (``user_version = 0``)
    laeuft durch alle drei Tabellen: erst acht -> sieben (Kernthema und
    Figuren sind eine Phase geworden, 04.09.), dann sieben -> acht (erst
    erfinden, dann schaerfen, 05.09. nachts), dann acht -> sieben (Setting,
    Figuren und Geschichte sind eine Station, 06.09.). Ohne diesen Schritt
    saehe eine Gruppe, die abends bei '8 · Durchlauf' aufgehoert hat, am
    naechsten Morgen eine Nummer, die es nicht mehr gibt.

    **Die Kette 1 -> 3 ist der eigentliche Punkt** (06.09.2026): eine
    Datenbank, die alle drei Umbauten verpasst hat, darf nicht auf halbem
    Weg stehenbleiben."""
    c = _alte_phasen_db(tmp_path)

    db.initialisiere(c)

    gelesen = {
        z["chat_id"]: (z["phase"], z["phase_angeboten"])
        for z in c.execute("SELECT * FROM arbeitsstand ORDER BY chat_id")
    }
    assert gelesen == {
        1: (3, 4),      # 1-3 bleiben, wo sie sind
        2: (4, 4),      # alt 5 (Figuren) -> 4 -> 4 -> 4
        3: (4, 6),      # alt 6 (Hauptkonflikt) -> 5 -> 5 -> 4
        4: (6, 7),      # alt 7 (Szenen) -> 6 -> 7 -> 6 (Szenentexte)
        5: (7, None),   # alt 8 (Durchlauf) -> 7 -> 8 -> 7, NULL bleibt NULL
    }
    assert c.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION


def _siebenstufige_db(tmp_path, name="sieben.db"):
    """Eine Datenbank auf dem Stand vom 05.09.2026 tagsueber: sieben Phasen,
    ``user_version`` auf 1. Sie darf NUR noch durch die zweite Tabelle."""
    c = db.verbinde(str(tmp_path / name))
    db.initialisiere(c)
    for chat_id, phase, angeboten in ((1, 3, 4), (2, 5, 6), (3, 6, 7), (4, 7, None)):
        repo.sichere_gruppe(c, chat_id, "gruppe1", f"Gruppe {chat_id}")
        c.execute(
            "UPDATE arbeitsstand SET phase = ?, phase_angeboten = ? WHERE chat_id = ?",
            (phase, angeboten, chat_id),
        ) if c.execute(
            "SELECT 1 FROM arbeitsstand WHERE chat_id = ?", (chat_id,)
        ).fetchone() else c.execute(
            "INSERT INTO arbeitsstand (chat_id, phase, phase_angeboten) VALUES (?, ?, ?)",
            (chat_id, phase, angeboten),
        )
    c.execute("PRAGMA user_version = 1")
    c.commit()
    return c


def test_der_zweite_und_dritte_umbau_laufen_nacheinander(tmp_path):
    """Eine Datenbank vom 05.09.2026 tagsueber (``user_version = 1``) laeuft
    noch durch ZWEI Tabellen: erst PHASEN_UMNUMMERIERUNG_2 (6 -> 7, 7 -> 8),
    dann PHASEN_UMNUMMERIERUNG_3 (5 -> 4, 6 -> 5, 7 -> 6, 8 -> 7)."""
    c = _siebenstufige_db(tmp_path)

    db.initialisiere(c)

    gelesen = {
        z["chat_id"]: (z["phase"], z["phase_angeboten"])
        for z in c.execute("SELECT * FROM arbeitsstand ORDER BY chat_id")
    }
    assert gelesen == {
        1: (3, 4),
        2: (4, 6),      # 5 -> 5 -> 4, das Angebot 6 -> 7 -> 6
        3: (6, 7),      # alt 6 (Szenen) -> 7 -> 6 (Szenentexte)
        4: (7, None),   # alt 7 (Durchlauf) -> 8 -> 7
    }
    assert c.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION


def test_eine_migrierte_gruppe_steht_auf_einer_gueltigen_phase(tmp_path):
    """Die Probe: zu jedem migrierten Wert gibt es einen Kurznamen und eine
    Phasendatei -- sonst faellt ``anweisungen.system`` ueber eine fehlende
    ``phasen/N.md``."""
    c = _siebenstufige_db(tmp_path)

    db.initialisiere(c)

    for z in c.execute("SELECT phase FROM arbeitsstand"):
        assert phasen.kurzname(z["phase"]), z["phase"]
        assert z["phase"] <= phasen.LETZTE


def test_jede_umgerechnete_nummer_ist_eine_gueltige_phase(tmp_path):
    """Die Probe aufs Ganze: nach der Migration gibt es zu jedem gespeicherten
    Wert auch einen Kurznamen -- sonst stuende auf der Gruppenseite eine nackte
    Zahl und ``anweisungen.system`` fiele ueber eine fehlende
    ``phasen/8.md``."""
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

    assert c.execute(
        "SELECT phase FROM arbeitsstand WHERE chat_id = 5"
    ).fetchone()[0] == 7
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


#: ``aufnahme`` und ``web_post``, wie sie vor der Karte "Mithoeren SICHER"
#: (03.10.2026) aussahen -- ohne ``rede_ms``. Hart hinterlegt statt aus
#: SCHEMA abgeleitet, aus demselben Grund wie ``_ALTE_GRUPPE_TABELLE`` oben:
#: der Test soll eine ECHTE Alt-Datenbank nachruesten, unabhaengig davon,
#: wie SCHEMA sich kuenftig weiterentwickelt.
_ALTE_AUFNAHME_UND_WEB_POST = """
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
  empfangen_am    TEXT NOT NULL,
  teil_von        INTEGER,
  beendet_am      TEXT,
  entfernt_am     TEXT,
  uebernommen_von TEXT,
  uebernommen_am  TEXT,
  schnittgrund    TEXT,
  brainstorm      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE web_post (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id           INTEGER NOT NULL,
  richtung          TEXT NOT NULL,
  typ               TEXT NOT NULL,
  text              TEXT,
  knoepfe           TEXT,
  daten             TEXT,
  bezug_message_id  INTEGER,
  antwort           TEXT,
  dauer             INTEGER,
  datei             TEXT,
  mime              TEXT,
  dateiname         TEXT,
  geloescht_am      TEXT,
  erstellt_am       TEXT NOT NULL,
  aenderung         INTEGER,
  schnittgrund      TEXT,
  brainstorm        INTEGER NOT NULL DEFAULT 0,
  bild              TEXT
);
"""


def test_rede_ms_spalte_existiert_frisch_und_wird_nachgeruestet(tmp_path):
    """Kanban-Karte Mithoeren SICHER (03.10.2026): ``redeMs`` faehrt als
    Diagnose-Metadatum mit (Aufgabe 1b) -- additiv auf ``aufnahme`` UND
    ``web_post``, nachgeruestet ueber dieselbe generische Migration wie
    ``schnittgrund``/``brainstorm``."""
    frisch = db.verbinde(str(tmp_path / "frisch.db"))
    db.initialisiere(frisch)
    assert "rede_ms" in [r[1] for r in frisch.execute("PRAGMA table_info(aufnahme)")]
    assert "rede_ms" in [r[1] for r in frisch.execute("PRAGMA table_info(web_post)")]

    alt = db.verbinde(str(tmp_path / "alt.db"))
    alt.executescript(_ALTE_AUFNAHME_UND_WEB_POST)
    alt.execute(
        "INSERT INTO aufnahme (chat_id, message_id, klasse, quelle, status, empfangen_am) "
        "VALUES (1, 10, 'kurz', 'sprache', 'empfangen', '2026-10-03T10:00:00+00:00')"
    )
    alt.execute(
        "INSERT INTO web_post (chat_id, richtung, typ, erstellt_am) "
        "VALUES (1, 'ein', 'sprache', '2026-10-03T10:00:00+00:00')"
    )
    alt.commit()
    assert "rede_ms" not in [r[1] for r in alt.execute("PRAGMA table_info(aufnahme)")], \
        "Testannahme: die Spalte fehlt wirklich"

    db.initialisiere(alt)  # darf nicht krachen, obwohl beide Tabellen schon existieren

    assert "rede_ms" in [r[1] for r in alt.execute("PRAGMA table_info(aufnahme)")]
    assert "rede_ms" in [r[1] for r in alt.execute("PRAGMA table_info(web_post)")]
    zeile = alt.execute("SELECT * FROM aufnahme WHERE chat_id = 1").fetchone()
    assert zeile["klasse"] == "kurz", "Migration darf keine Daten verlieren"
    assert zeile["rede_ms"] is None


#: ``aufnahme`` und ``web_post`` wie vor der Kalibrierungskarte (03.10.2026,
#: Task 2) -- ohne ``kalibrierung``. Dieselbe Begruendung wie bei
#: ``_ALTE_AUFNAHME_UND_WEB_POST``: eine echte Alt-Datenbank nachruesten,
#: unabhaengig von SCHEMAs weiterer Entwicklung.
_ALTE_AUFNAHME_UND_WEB_POST_OHNE_KALIBRIERUNG = _ALTE_AUFNAHME_UND_WEB_POST.replace(
    "  brainstorm      INTEGER NOT NULL DEFAULT 0\n);",
    "  brainstorm      INTEGER NOT NULL DEFAULT 0,\n  rede_ms         INTEGER\n);",
).replace(
    "  bild              TEXT\n);",
    "  bild              TEXT,\n  rede_ms           INTEGER\n);",
)


def test_kalibrierung_spalten_existieren_frisch_und_werden_nachgeruestet(tmp_path):
    """Task 2 (Button-gated Kalibrierung): ``kalibrierung`` faehrt additiv auf
    ``aufnahme`` UND ``web_post`` mit, dieselbe Migration wie ``rede_ms``.
    ``gruppe.kalibrierung_modus`` ist die dritte additive Spalte dieser
    Karte."""
    frisch = db.verbinde(str(tmp_path / "frisch.db"))
    db.initialisiere(frisch)
    assert "kalibrierung" in [r[1] for r in frisch.execute("PRAGMA table_info(aufnahme)")]
    assert "kalibrierung" in [r[1] for r in frisch.execute("PRAGMA table_info(web_post)")]
    assert "kalibrierung_modus" in [r[1] for r in frisch.execute("PRAGMA table_info(gruppe)")]

    alt = db.verbinde(str(tmp_path / "alt.db"))
    alt.executescript(_ALTE_AUFNAHME_UND_WEB_POST_OHNE_KALIBRIERUNG)
    alt.execute(
        "INSERT INTO aufnahme (chat_id, message_id, klasse, quelle, status, empfangen_am) "
        "VALUES (1, 10, 'kurz', 'sprache', 'empfangen', '2026-10-03T10:00:00+00:00')"
    )
    alt.execute(
        "INSERT INTO web_post (chat_id, richtung, typ, erstellt_am) "
        "VALUES (1, 'ein', 'sprache', '2026-10-03T10:00:00+00:00')"
    )
    alt.commit()
    assert "kalibrierung" not in [r[1] for r in alt.execute("PRAGMA table_info(aufnahme)")], \
        "Testannahme: die Spalte fehlt wirklich"

    db.initialisiere(alt)  # darf nicht krachen, obwohl beide Tabellen schon existieren

    assert "kalibrierung" in [r[1] for r in alt.execute("PRAGMA table_info(aufnahme)")]
    assert "kalibrierung" in [r[1] for r in alt.execute("PRAGMA table_info(web_post)")]
    zeile = alt.execute("SELECT * FROM aufnahme WHERE chat_id = 1").fetchone()
    assert zeile["klasse"] == "kurz", "Migration darf keine Daten verlieren"
    assert zeile["kalibrierung"] == 0


def test_migration_ergaenzt_die_gruppenweiten_kalibrierungswerte_ohne_datenverlust(tmp_path):
    """Karte 'keine Kalibrierung in Phase 3/4' (05.10.2026): die drei
    Messwerte plus Zeitstempel fahren additiv auf ``gruppe`` mit, dieselbe
    generische Migration wie ``interviewmodus_seit``/``web_token`` oben --
    eine Datenbank von vor dieser Karte kennt sie nicht."""
    pfad = str(tmp_path / "alt.db")
    c = db.verbinde(pfad)
    c.executescript(_ALTE_GRUPPE_TABELLE)
    c.execute(
        "INSERT INTO gruppe (chat_id, bot_name, titel) VALUES (3, 'gruppe1', 'Dritte Gruppe')"
    )
    c.commit()
    vorher = [r[1] for r in c.execute("PRAGMA table_info(gruppe)")]
    for spalte in ("kalibrierung_boden", "kalibrierung_rede",
                   "kalibrierung_schwelle", "kalibrierung_gemessen_am"):
        assert spalte not in vorher, "Testannahme: die Spalte fehlt wirklich"

    db.initialisiere(c)

    nachher = [r[1] for r in c.execute("PRAGMA table_info(gruppe)")]
    for spalte in ("kalibrierung_boden", "kalibrierung_rede",
                   "kalibrierung_schwelle", "kalibrierung_gemessen_am"):
        assert spalte in nachher

    zeile = c.execute("SELECT * FROM gruppe WHERE chat_id = 3").fetchone()
    assert zeile["titel"] == "Dritte Gruppe", "Migration darf keine Daten verlieren"
    assert zeile["kalibrierung_boden"] is None
    assert zeile["kalibrierung_rede"] is None
    assert zeile["kalibrierung_schwelle"] is None
    assert zeile["kalibrierung_gemessen_am"] is None


def test_migration_ist_ein_no_op_wenn_alle_spalten_schon_da_sind(conn):
    """Ein zweiter initialisiere()-Lauf auf einer schon aktuellen Datenbank
    darf nicht krachen (kein ALTER TABLE auf eine schon vorhandene Spalte)."""
    db.initialisiere(conn)  # zweiter Lauf, darf keine Ausnahme werfen
    spalten = [r[1] for r in conn.execute("PRAGMA table_info(gruppe)")]
    assert "interviewmodus_seit" in spalten


def test_echo_message_id_spalte_existiert_frisch_und_wird_nachgeruestet(tmp_path):
    """Karte t_ea994c7f: die web_post-id der EINEN Transkriptblase steht am
    Interview-Kopf -- additiv, ueber die generische Migration."""
    frisch = db.verbinde(str(tmp_path / "frisch.db"))
    db.initialisiere(frisch)
    assert "echo_message_id" in [r[1] for r in frisch.execute("PRAGMA table_info(aufnahme)")]

    alt = db.verbinde(str(tmp_path / "alt.db"))
    alt.executescript(_ALTE_AUFNAHME_UND_WEB_POST)
    alt.execute(
        "INSERT INTO aufnahme (chat_id, message_id, klasse, quelle, status, empfangen_am) "
        "VALUES (1, 10, 'lang', 'sprache', 'laeuft', '2026-10-04T10:00:00+00:00')"
    )
    alt.commit()
    assert "echo_message_id" not in [r[1] for r in alt.execute("PRAGMA table_info(aufnahme)")]

    db.initialisiere(alt)

    assert "echo_message_id" in [r[1] for r in alt.execute("PRAGMA table_info(aufnahme)")]
    zeile = alt.execute("SELECT * FROM aufnahme WHERE chat_id = 1").fetchone()
    assert zeile["klasse"] == "lang", "Migration darf keine Daten verlieren"
    assert zeile["echo_message_id"] is None


def test_echo_message_id_lesen_und_setzen(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    kopf = repo.lege_interview_an(c, 1)

    assert repo.echo_message_id(c, kopf) is None
    repo.setze_echo_message_id(c, kopf, 4711)
    assert repo.echo_message_id(c, kopf) == 4711
    assert repo.echo_message_id(c, 99999) is None


def test_client_job_id_spalte_existiert_frisch_und_wird_nachgeruestet(tmp_path):
    """Karte t_e2b0e489 (kein Aufnahmeverlust am Handy): die Client-Job-Id
    faehrt additiv auf ``web_post`` mit -- derselbe Weg wie ``rede_ms``/
    ``kalibrierung``. Der Unique-Index ist der serverseitige Duplikatschutz
    fuer ein Segment, das der Browser (IndexedDB-Warteschlange) nach einem
    Neuladen erneut hochlaedt."""
    frisch = db.verbinde(str(tmp_path / "frisch.db"))
    db.initialisiere(frisch)
    assert "client_job_id" in [r[1] for r in frisch.execute("PRAGMA table_info(web_post)")]

    alt = db.verbinde(str(tmp_path / "alt.db"))
    alt.executescript(_ALTE_AUFNAHME_UND_WEB_POST)
    alt.execute(
        "INSERT INTO web_post (chat_id, richtung, typ, erstellt_am) "
        "VALUES (1, 'ein', 'sprache', '2026-10-06T10:00:00+00:00')"
    )
    alt.commit()
    assert "client_job_id" not in [r[1] for r in alt.execute("PRAGMA table_info(web_post)")], \
        "Testannahme: die Spalte fehlt wirklich"

    db.initialisiere(alt)  # darf nicht krachen, obwohl die Tabelle schon existiert

    assert "client_job_id" in [r[1] for r in alt.execute("PRAGMA table_info(web_post)")]
    zeile = alt.execute("SELECT * FROM web_post WHERE chat_id = 1").fetchone()
    assert zeile["typ"] == "sprache", "Migration darf keine Daten verlieren"
    assert zeile["client_job_id"] is None


def test_client_job_id_ist_je_chat_eindeutig(conn):
    """Zwei Uploads derselben Client-Job-Id fuer denselben Chat duerfen nicht
    beide eine Zeile anlegen -- der Unique-Index ist die letzte Verteidigung,
    falls ``web_chat._audio`` den Dublettencheck je einmal uebersieht."""
    conn.execute(
        "INSERT INTO web_post (chat_id, richtung, typ, erstellt_am, client_job_id) "
        "VALUES (1, 'ein', 'sprache', '2026-10-06T10:00:00+00:00', 'job-1')"
    )
    conn.commit()
    with pytest.raises(db.sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO web_post (chat_id, richtung, typ, erstellt_am, client_job_id) "
            "VALUES (1, 'ein', 'sprache', '2026-10-06T10:05:00+00:00', 'job-1')"
        )

    # Eine andere Gruppe darf dieselbe Client-Job-Id haben (die Id ist nur
    # ein Zufallswert des Browsers, keine global eindeutige Kennung), und
    # NULL (alte Clients ohne Job-Id) darf beliebig oft vorkommen.
    conn.execute(
        "INSERT INTO web_post (chat_id, richtung, typ, erstellt_am, client_job_id) "
        "VALUES (2, 'ein', 'sprache', '2026-10-06T10:05:00+00:00', 'job-1')"
    )
    conn.execute(
        "INSERT INTO web_post (chat_id, richtung, typ, erstellt_am) "
        "VALUES (1, 'ein', 'sprache', '2026-10-06T10:06:00+00:00')"
    )
    conn.execute(
        "INSERT INTO web_post (chat_id, richtung, typ, erstellt_am) "
        "VALUES (1, 'ein', 'sprache', '2026-10-06T10:07:00+00:00')"
    )
    conn.commit()


def test_loeschen_raeumt_die_gruppe(conn):
    conn.execute("INSERT INTO gruppe (chat_id, bot_name) VALUES (42, 'g1')")
    conn.execute("INSERT INTO nachricht (chat_id, message_id, typ, gesendet_am) "
                 "VALUES (42, 1, 'text', '2026-09-05T10:00:00')")
    conn.commit()
    db.loesche_gruppe(conn, 42)
    assert conn.execute("SELECT count(*) FROM nachricht").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM gruppe").fetchone()[0] == 0
