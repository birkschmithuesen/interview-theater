"""Repo-Schicht der Internet-Recherche (Karte t_c5117c91): speichern, lesen,
weich entfernen -- wie Journal/Verdichtungen nie hart geloescht (AGENTS.md
"Nur anhaengen")."""

import pytest
from interview_theater import db, repo

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def test_recherche_tabelle_hat_chat_id_und_steht_in_der_loeschliste(conn):
    spalten = [r[1] for r in conn.execute("PRAGMA table_info(recherche)")]
    assert "chat_id" in spalten
    assert "recherche" in db.TABELLEN_MIT_CHAT_ID


def test_hole_recherchen_ist_leer_ohne_eintrag(conn):
    assert repo.hole_recherchen(conn, CHAT) == []


def test_speichere_und_hole_recherche(conn):
    quellen = [{"titel": "Example", "url": "https://example.org/a"}]
    recherche_id = repo.speichere_recherche(
        conn, CHAT, "When was X founded?", "X was founded in 1990 (Example, https://example.org/a).",
        quellen,
    )
    gefunden = repo.hole_recherchen(conn, CHAT)
    assert len(gefunden) == 1
    assert gefunden[0]["id"] == recherche_id
    assert gefunden[0]["frage"] == "When was X founded?"
    assert gefunden[0]["quellen"] == quellen


def test_recherchen_anderer_gruppe_bleiben_unsichtbar(conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere Gruppe")
    repo.speichere_recherche(conn, 2, "Andere Frage?", "Antwort.", [])
    assert repo.hole_recherchen(conn, CHAT) == []


def test_entferne_recherche_ist_weich(conn):
    recherche_id = repo.speichere_recherche(conn, CHAT, "Frage?", "Antwort.", [])

    gefunden = repo.entferne_recherche(conn, CHAT, recherche_id)

    assert gefunden is True
    assert repo.hole_recherchen(conn, CHAT) == []
    # Weich: die Zeile steht noch in der Datenbank, nur entfernt_am ist gesetzt.
    zeile = conn.execute(
        "SELECT entfernt_am FROM recherche WHERE id = ?", (recherche_id,)
    ).fetchone()
    assert zeile["entfernt_am"] is not None


def test_entferne_recherche_unbekannte_id_liefert_false(conn):
    assert repo.entferne_recherche(conn, CHAT, 9999) is False
