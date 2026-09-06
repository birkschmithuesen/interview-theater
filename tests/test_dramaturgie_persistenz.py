"""Persistenz und Ausgabe der Dramaturgie-Pruefung.

Geprueft wird: die Migration ist additiv (eine alte Datenbank laeuft durch,
ohne Umnummerierung und ohne Datenverlust), die Tabelle haengt an der
Loeschzusage, die Gruppenseite zeigt die Befunde read-only und **ohne
Belegzitat**, und das Skript verweigert den Dienst auf der
Betriebsdatenbank.
"""

import sqlite3

import pytest
from interview_theater import db, repo, web, web_daten

BEFUNDE = [
    {
        "pruefung": "b1", "quelle": "judge", "schwere": "hoch", "szene": 2,
        "figur": None, "text": "Szene 2 endet, wie sie anfaengt.",
        "beleg": "MIRA: Lass den Koffer stehen.", "beleg_geprueft": True,
        "vorschlag": "Szene 2: Lass Jonas den Koffer oeffnen.",
    },
    {
        "pruefung": "sprechanteil", "quelle": "mechanik", "schwere": "hart",
        "szene": None, "figur": "Pola",
        "text": "Pola spricht 12 von 4200 Woertern.",
    },
]


# --- Migration ------------------------------------------------------------


def test_alte_datenbank_bekommt_die_tabelle_ohne_datenverlust(tmp_path):
    """Eine Datenbank aus der Zeit davor: Schema anlegen, Tabelle wieder
    fallen lassen, Daten hineinschreiben, neu initialisieren."""
    pfad = str(tmp_path / "alt.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Testgruppe")
    conn.execute("DROP TABLE dramaturgie_befund")
    conn.commit()
    repo.setze_figur(conn, 1, "Mira", "Mira ist erfunden.")
    szene_id = repo.lege_szene_an(conn, 1, 1, "Am Bahnsteig", "sie treffen sich", None)
    phase_vorher = repo.hole_phase(conn, 1)
    conn.close()

    zweite = db.verbinde(pfad)
    db.initialisiere(zweite)

    # Die Tabelle ist da ...
    assert repo.letzte_dramaturgie_runde(zweite, 1) == 0
    # ... und nichts ist umnummeriert oder verloren.
    assert repo.hole_phase(zweite, 1) == phase_vorher
    assert [f["name"] for f in repo.figuren(zweite, 1)] == ["Mira"]
    assert repo.hole_szene(zweite, szene_id)["nummer"] == 1
    assert zweite.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION


def test_zweimal_initialisieren_ist_gefahrlos(conn):
    repo.lege_dramaturgie_befunde_an(conn, 1, BEFUNDE, runde=1)
    db.initialisiere(conn)
    assert len(repo.dramaturgie_befunde(conn, 1)) == 2


def test_die_tabelle_haengt_an_der_loeschzusage(conn):
    assert "dramaturgie_befund" in db.TABELLEN_MIT_CHAT_ID
    repo.lege_dramaturgie_befunde_an(conn, 1, BEFUNDE, runde=1)

    db.loesche_gruppe(conn, 1)

    assert repo.dramaturgie_befunde(conn, 1) == []


# --- repo -----------------------------------------------------------------


def test_befunde_werden_mit_runde_gespeichert(conn):
    assert repo.lege_dramaturgie_befunde_an(conn, 1, BEFUNDE, runde=1) == 2
    assert repo.lege_dramaturgie_befunde_an(conn, 1, BEFUNDE[:1], runde=2) == 1

    assert repo.letzte_dramaturgie_runde(conn, 1) == 2
    assert len(repo.dramaturgie_befunde(conn, 1, runde=1)) == 2
    assert len(repo.dramaturgie_befunde(conn, 1)) == 3


def test_beleg_geprueft_wird_nie_erraten(conn):
    repo.lege_dramaturgie_befunde_an(conn, 1, BEFUNDE, runde=1)
    zeilen = repo.dramaturgie_befunde(conn, 1)

    geprueft = {z["pruefung"]: z["beleg_geprueft"] for z in zeilen}
    assert geprueft["b1"] == 1
    # Ohne das Feld ist es 0 -- auch wenn ein Beleg dastuende.
    assert geprueft["sprechanteil"] == 0


def test_befund_ohne_pflichtfeld_faellt_weg(conn):
    unvollstaendig = [
        {"pruefung": "", "text": "x", "quelle": "judge"},
        {"pruefung": "b1", "text": "  ", "quelle": "judge"},
        {"pruefung": "b1", "text": "x", "quelle": ""},
    ]

    assert repo.lege_dramaturgie_befunde_an(conn, 1, unvollstaendig) == 0


def test_ein_befund_ist_ueber_seine_id_wiederfindbar(conn):
    repo.lege_dramaturgie_befunde_an(conn, 1, BEFUNDE, runde=1)
    zeile = repo.dramaturgie_befunde(conn, 1)[0]

    assert repo.hole_dramaturgie_befund(conn, 1, zeile["id"])["pruefung"] == "b1"
    assert repo.hole_dramaturgie_befund(conn, 2, zeile["id"]) is None


# --- Bewertungen (die Datenbankform der Bilanz) ---------------------------

BEWERTUNGEN = [
    {"pruefung": "b1", "szene": 1, "score": 0},
    {"pruefung": "b1", "szene": 2, "score": 2},
    {"pruefung": "a2", "szene": None, "score": 1},
]


def test_bewertungen_werden_mit_runde_gespeichert(conn):
    assert repo.lege_dramaturgie_bewertungen_an(conn, 1, BEWERTUNGEN, runde=1) == 3
    assert repo.lege_dramaturgie_bewertungen_an(conn, 1, BEWERTUNGEN[:1], runde=2) == 1

    assert len(repo.dramaturgie_bewertungen(conn, 1, runde=1)) == 3
    assert len(repo.dramaturgie_bewertungen(conn, 1)) == 4


def test_auch_die_erfuellte_frage_steht_da(conn):
    """Der Kern des Erfolgsmasses: ein Score 2 erzeugt keinen Befund, aber
    sehr wohl eine Bewertung -- sonst waere sein Absturz in der naechsten
    Runde nicht zu sehen."""
    repo.lege_dramaturgie_bewertungen_an(conn, 1, BEWERTUNGEN, runde=1)

    scores = {
        (z["pruefung"], z["szene"]): z["score"]
        for z in repo.dramaturgie_bewertungen(conn, 1, runde=1)
    }
    assert scores[("b1", 2)] == 2
    assert scores[("a2", None)] == 1


def test_bewertung_ohne_score_faellt_weg(conn):
    """Ein verworfener Score (kein bestaetigtes Belegzitat) ist keine Note --
    er darf die Bilanz nicht mitrechnen."""
    unvollstaendig = [
        {"pruefung": "b1", "szene": 1, "score": None},
        {"pruefung": "", "szene": 1, "score": 2},
    ]

    assert repo.lege_dramaturgie_bewertungen_an(conn, 1, unvollstaendig) == 0


def test_die_bewertungstabelle_haengt_an_der_loeschzusage(conn):
    assert "dramaturgie_bewertung" in db.TABELLEN_MIT_CHAT_ID
    repo.lege_dramaturgie_bewertungen_an(conn, 1, BEWERTUNGEN, runde=1)

    db.loesche_gruppe(conn, 1)

    assert repo.dramaturgie_bewertungen(conn, 1) == []


def test_alte_datenbank_bekommt_die_bewertungstabelle(tmp_path):
    pfad = str(tmp_path / "alt.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Testgruppe")
    conn.execute("DROP TABLE dramaturgie_bewertung")
    conn.commit()
    conn.close()

    zweite = db.verbinde(pfad)
    db.initialisiere(zweite)

    assert repo.dramaturgie_bewertungen(zweite, 1) == []


# --- Gruppenseite ---------------------------------------------------------


@pytest.fixture
def seite(conn, tmp_path):
    """Die Gruppenseite, gelesen wie im Betrieb: eigene Verbindung, read-only."""
    repo.lege_dramaturgie_befunde_an(conn, 1, BEFUNDE, runde=1)
    token = repo.stelle_web_token_sicher(conn, 1)
    conn.commit()
    ro = sqlite3.connect(f"file:{conn.execute('PRAGMA database_list').fetchone()[2]}"
                         "?mode=ro", uri=True)
    ro.row_factory = sqlite3.Row
    daten = web_daten.gruppe_nach_token(ro, token)
    return daten, web.gruppe_html(daten)


def test_die_gruppenseite_zeigt_die_letzte_runde(seite):
    daten, html = seite

    assert daten["dramaturgie"]["runde"] == 1
    assert "Dramaturgie-Prüfung" in html
    assert "Szene 2 endet, wie sie anfaengt." in html
    assert "Pola spricht 12 von 4200 Woertern." in html


def test_die_gruppenseite_zeigt_kein_belegzitat(seite):
    daten, html = seite

    assert all("beleg" not in b for b in daten["dramaturgie"]["befunde"])
    assert "Lass den Koffer stehen" not in html


def test_ohne_lauf_fehlt_der_abschnitt_ganz(conn):
    token = repo.stelle_web_token_sicher(conn, 1)
    conn.commit()
    daten = web_daten.gruppe_nach_token(conn, token)

    assert daten["dramaturgie"] == {}
    assert "Dramaturgie-Prüfung" not in web.gruppe_html(daten)


def test_ohne_tabelle_gibt_es_keinen_fehler(conn):
    conn.execute("DROP TABLE dramaturgie_befund")
    conn.commit()

    assert web_daten.dramaturgie(conn, 1) == {}


def test_die_gruppenseite_nimmt_dafuer_kein_post_entgegen():
    """Die Befunde sind read-only -- entschieden wird im Chat."""
    from interview_theater import web_schreiben

    assert not any("dramaturgie" in f for f in web_schreiben.FELDER)


# --- Das Skript -----------------------------------------------------------


def test_das_skript_verweigert_die_betriebsdatenbank(tmp_path, monkeypatch):
    from scripts import dramaturgie_pruefen

    betrieb = tmp_path / "soap.db"
    betrieb.write_text("")
    monkeypatch.setenv("IT_DB", str(betrieb))

    with pytest.raises(SystemExit) as fehler:
        dramaturgie_pruefen._pruefe_pfad(str(betrieb))

    assert "Betriebsdatenbank" in str(fehler.value)


def test_das_skript_nimmt_eine_kopie(tmp_path, monkeypatch):
    from scripts import dramaturgie_pruefen

    betrieb = tmp_path / "soap.db"
    betrieb.write_text("")
    kopie = tmp_path / "kopie.db"
    kopie.write_text("")
    monkeypatch.setenv("IT_DB", str(betrieb))

    dramaturgie_pruefen._pruefe_pfad(str(kopie))  # kein SystemExit


def test_der_bericht_nennt_richter_aufrufe_und_prompt_versionen():
    from interview_theater.dramaturgie import fanout
    from scripts import dramaturgie_pruefen

    ergebnis = fanout.Ergebnis(
        runde=1, befunde=list(BEFUNDE), aufrufe=18,
        richter=fanout.Richter("claude", "claude-opus-5"),
    )

    text = dramaturgie_pruefen.bericht(1, ergebnis, [], 42.0)

    assert "claude-opus-5" in text
    assert "Modellaufrufe: 18" in text
    assert fanout.version("b1") in text
