"""Tests fuer die Ablage-Schicht des Phasen-Debriefs (Karte phasen-debrief,
Teil 1): Tabelle ``phasen_debrief`` und die vier Repo-Funktionen.

Dieses Modul prueft ausschliesslich die Speicherung -- kein Modellaufruf,
keine Anbindung an ``phasen.py`` oder ``bot.py``. Das kommt in spaeteren
Aufgaben dazu, die auch an diesem Testmodul weiterschreiben.
"""

import pytest

from interview_theater import db, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    repo.sichere_gruppe(c, 2, "gruppe2", "Zweite Gruppe")
    return c


def test_schema_legt_phasen_debrief_mit_erwarteten_spalten_an(conn):
    spalten = {z["name"] for z in conn.execute("PRAGMA table_info(phasen_debrief)")}
    assert spalten == {
        "id", "chat_id", "phase", "text", "erstellt_am", "modell", "geloescht",
    }


def test_loesche_gruppe_entfernt_nur_die_eigenen_zeilen(conn):
    repo.merke_phasen_debrief(conn, 1, 1, "Text Gruppe 1", "gemma")
    repo.merke_phasen_debrief(conn, 2, 1, "Text Gruppe 2", "gemma")
    db.loesche_gruppe(conn, 1)
    assert repo.phasen_debriefs(conn, 1) == []
    assert len(repo.phasen_debriefs(conn, 2)) == 1


def test_merken_und_lesen_im_rundlauf(conn):
    repo.merke_phasen_debrief(conn, 1, 1, "Die Gruppe hat drei Begriffe notiert.", "gemma")
    zeilen = repo.phasen_debriefs(conn, 1)
    assert len(zeilen) == 1
    zeile = zeilen[0]
    assert zeile["chat_id"] == 1
    assert zeile["phase"] == 1
    assert zeile["text"] == "Die Gruppe hat drei Begriffe notiert."
    assert zeile["modell"] == "gemma"
    assert zeile["geloescht"] == 0
    assert zeile["erstellt_am"]


def test_erneutes_verlassen_derselben_phase_ersetzt_den_text(conn):
    repo.merke_phasen_debrief(conn, 1, 2, "Erster Durchlauf durch Phase 2.", "gemma")
    repo.merke_phasen_debrief(conn, 1, 2, "Zweiter Durchlauf durch Phase 2.", "gemma")
    zeilen = repo.phasen_debriefs(conn, 1)
    assert len(zeilen) == 1
    assert zeilen[0]["text"] == "Zweiter Durchlauf durch Phase 2."


def test_entfernen_blendet_aus_und_ein_neuer_lauf_bringt_es_zurueck(conn):
    repo.merke_phasen_debrief(conn, 1, 3, "Urspruenglicher Text.", "gemma")
    repo.entferne_phasen_debrief(conn, 1, 3)
    assert repo.phasen_debriefs(conn, 1) == []

    repo.merke_phasen_debrief(conn, 1, 3, "Neuer Text nach erneutem Verlassen.", "gemma")
    zeilen = repo.phasen_debriefs(conn, 1)
    assert len(zeilen) == 1
    assert zeilen[0]["geloescht"] == 0
    assert zeilen[0]["text"] == "Neuer Text nach erneutem Verlassen."


def test_phasen_debriefs_sortiert_nach_phase(conn):
    repo.merke_phasen_debrief(conn, 1, 3, "Phase drei", "gemma")
    repo.merke_phasen_debrief(conn, 1, 1, "Phase eins", "gemma")
    repo.merke_phasen_debrief(conn, 1, 2, "Phase zwei", "gemma")
    assert [z["phase"] for z in repo.phasen_debriefs(conn, 1)] == [1, 2, 3]


def test_nachrichten_zwischen_schliesst_transkript_echo_aus_und_liefert_beide_seiten(conn):
    repo.merke_nachricht(conn, 1, 1, "Ada", 0, "text", "vorher", "2026-09-05T09:00:00")
    repo.merke_nachricht(conn, 1, 2, "Ada", 0, "text", "im Fenster", "2026-09-05T10:00:00")
    repo.merke_nachricht(conn, 1, 3, "Bot", 1, "text", "Antwort im Fenster", "2026-09-05T10:05:00")
    repo.merke_nachricht(
        conn, 1, 4, "Ada", 0, repo.TYP_TRANSKRIPT, "ein Transkript-Echo",
        "2026-09-05T10:06:00",
    )
    repo.merke_nachricht(conn, 1, 5, "Ada", 0, "text", "nachher", "2026-09-05T12:00:00")

    zeilen = repo.nachrichten_zwischen(
        conn, 1, "2026-09-05T09:30:00", "2026-09-05T11:00:00"
    )

    assert [z["message_id"] for z in zeilen] == [2, 3]
    assert [z["text"] for z in zeilen] == ["im Fenster", "Antwort im Fenster"]


def test_nachrichten_zwischen_ist_chronologisch_nach_message_id(conn):
    repo.merke_nachricht(conn, 1, 5, "Ada", 0, "text", "fuenf", "2026-09-05T10:00:05")
    repo.merke_nachricht(conn, 1, 3, "Bot", 1, "text", "drei", "2026-09-05T10:00:03")
    repo.merke_nachricht(conn, 1, 4, "Ada", 0, "text", "vier", "2026-09-05T10:00:04")

    zeilen = repo.nachrichten_zwischen(
        conn, 1, "2026-09-05T09:00:00", "2026-09-05T11:00:00"
    )

    assert [z["message_id"] for z in zeilen] == [3, 4, 5]


def test_erste_nachricht_am_liefert_das_fruehste_datum(conn):
    repo.merke_nachricht(conn, 1, 1, "Ada", 0, "text", "zuerst", "2026-09-05T09:00:00")
    repo.merke_nachricht(conn, 1, 2, "Bo", 0, "text", "danach", "2026-09-05T10:00:00")
    assert repo.erste_nachricht_am(conn, 1) == "2026-09-05T09:00:00"


def test_erste_nachricht_am_ist_none_fuer_eine_leere_gruppe(conn):
    assert repo.erste_nachricht_am(conn, 2) is None
