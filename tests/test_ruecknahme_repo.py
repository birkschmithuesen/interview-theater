"""Die Ablage der Ruecknahme: Schema, Schnappschuss, Speichern, die eine
Transaktion (Karte U, 01.10.2026).

Kein Netz, kein Modell -- die Schicht darunter ist SQLite.
"""

import json

import pytest

from interview_theater import db, repo


def test_beide_tabellen_stehen_im_schema(conn):
    """Additiv per CREATE TABLE IF NOT EXISTS, wie jede Tabelle hier."""
    vorhandene = {
        zeile[0]
        for zeile in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {"erkenner_lauf", "erkenner_lauf_schritt"} <= vorhandene


def test_beide_tabellen_tragen_chat_id_und_stehen_in_der_loeschzusage(conn):
    """Jede Tabelle ausser bot_zustand hat chat_id -- daran haengt
    db.loesche_gruppe (AGENTS.md)."""
    for tabelle in ("erkenner_lauf", "erkenner_lauf_schritt"):
        spalten = {z[1] for z in conn.execute(f"PRAGMA table_info({tabelle})")}
        assert "chat_id" in spalten, tabelle
        assert tabelle in db.TABELLEN_MIT_CHAT_ID, tabelle


def test_loeschen_einer_gruppe_nimmt_die_laeufe_mit(conn):
    conn.execute(
        "INSERT INTO erkenner_lauf (chat_id, meldung, erstellt_am) "
        "VALUES (1, 'Kernthema: X', '2026-10-01T10:00:00')"
    )
    lauf_id = conn.execute("SELECT id FROM erkenner_lauf").fetchone()[0]
    conn.execute(
        "INSERT INTO erkenner_lauf_schritt "
        "(chat_id, lauf_id, tabelle, schluessel, art, vorher, nachher, erstellt_am) "
        "VALUES (1, ?, 'arbeitsstand', ?, 'geaendert', ?, ?, '2026-10-01T10:00:00')",
        (lauf_id, json.dumps({"chat_id": 1}), json.dumps({"kernthema": None}),
         json.dumps({"kernthema": "X"})),
    )
    conn.commit()

    db.loesche_gruppe(conn, 1)

    assert conn.execute("SELECT count(*) FROM erkenner_lauf").fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM erkenner_lauf_schritt"
    ).fetchone()[0] == 0


def test_eine_altdatenbank_ohne_die_tabellen_laeuft_durch(tmp_path):
    """db.initialisiere ist additiv: eine Datenbank, die vor dieser Aenderung
    entstanden ist, bekommt die Tabellen beim Start -- ohne
    SCHEMA_VERSION-Schritt, weil nichts umgedeutet wird."""
    pfad = str(tmp_path / "alt.db")
    alt = db.verbinde(pfad)
    alt.executescript(db.SCHEMA)
    alt.execute("DROP TABLE erkenner_lauf")
    alt.execute("DROP TABLE erkenner_lauf_schritt")
    # Eine echte Altdatenbank hat die Phasennummern-Migration laengst
    # durchlaufen (jede Betriebsdatenbank seit dem 06.09.2026 steht auf
    # SCHEMA_VERSION); nur die beiden neuen Tabellen fehlen ihr noch.
    alt.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION}")
    alt.commit()
    version_vorher = alt.execute("PRAGMA user_version").fetchone()[0]
    alt.close()

    neu = db.verbinde(pfad)
    db.initialisiere(neu)

    vorhandene = {
        z[0] for z in neu.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"erkenner_lauf", "erkenner_lauf_schritt"} <= vorhandene
    assert neu.execute("PRAGMA user_version").fetchone()[0] == version_vorher
    assert db.SCHEMA_VERSION == 3, "keine Erhoehung: es wird nichts umgedeutet"
