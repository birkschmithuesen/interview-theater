"""Repo-Schicht der Bedarfsliste (Birk 08.10.2026 ~13:45, Padua): eine
Abhakliste je Gruppe (Raum/Requisiten/Technik/Kostuem/zu organisieren),
angezeigt in der read-only Werkbank. Weich entfernbar wie Recherche
(``entfernt_am``), aber nicht Teil der "Nur anhaengen"-Tabellen -- ein Punkt
darf ersetzt werden (``scripts/bedarf_seed.py``)."""

import pytest
from interview_theater import db, repo

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def test_bedarf_punkt_tabelle_hat_chat_id_und_steht_in_der_loeschliste(conn):
    spalten = [r[1] for r in conn.execute("PRAGMA table_info(bedarf_punkt)")]
    assert "chat_id" in spalten
    assert "bedarf_punkt" in db.TABELLEN_MIT_CHAT_ID


def test_bedarf_ist_leer_ohne_punkte(conn):
    assert repo.bedarf(conn, CHAT) == []


def test_bedarf_liefert_sektions_und_reihenfolgetreu(conn):
    conn.execute(
        "INSERT INTO bedarf_punkt (chat_id, sektion, text, reihenfolge, erstellt_am) "
        "VALUES (?, 'Props', 'Chair', 2, '2026-10-08T12:00:00+00:00')",
        (CHAT,),
    )
    conn.execute(
        "INSERT INTO bedarf_punkt (chat_id, sektion, text, reihenfolge, erstellt_am) "
        "VALUES (?, 'Props', 'Table', 1, '2026-10-08T12:00:00+00:00')",
        (CHAT,),
    )
    conn.commit()
    punkte = repo.bedarf(conn, CHAT)
    assert [p["text"] for p in punkte] == ["Table", "Chair"]


def test_bedarf_anderer_gruppe_bleibt_unsichtbar(conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere Gruppe")
    conn.execute(
        "INSERT INTO bedarf_punkt (chat_id, sektion, text, reihenfolge, erstellt_am) "
        "VALUES (2, 'Props', 'Chair', 1, '2026-10-08T12:00:00+00:00')",
    )
    conn.commit()
    assert repo.bedarf(conn, CHAT) == []


def test_bedarf_entfernte_punkte_bleiben_unsichtbar(conn):
    conn.execute(
        "INSERT INTO bedarf_punkt (chat_id, sektion, text, reihenfolge, erstellt_am, entfernt_am) "
        "VALUES (?, 'Props', 'Chair', 1, '2026-10-08T12:00:00+00:00', '2026-10-08T12:05:00+00:00')",
        (CHAT,),
    )
    conn.commit()
    assert repo.bedarf(conn, CHAT) == []


def test_setze_bedarf_erledigt_setzt_zeitstempel(conn):
    cur = conn.execute(
        "INSERT INTO bedarf_punkt (chat_id, sektion, text, reihenfolge, erstellt_am) "
        "VALUES (?, 'Props', 'Chair', 1, '2026-10-08T12:00:00+00:00')",
        (CHAT,),
    )
    conn.commit()
    punkt_id = cur.lastrowid

    getroffen = repo.setze_bedarf_erledigt(conn, CHAT, punkt_id, True)

    assert getroffen is True
    punkte = repo.bedarf(conn, CHAT)
    assert punkte[0]["erledigt_am"] is not None


def test_setze_bedarf_erledigt_zurueck_loescht_zeitstempel(conn):
    cur = conn.execute(
        "INSERT INTO bedarf_punkt (chat_id, sektion, text, reihenfolge, erstellt_am, erledigt_am) "
        "VALUES (?, 'Props', 'Chair', 1, '2026-10-08T12:00:00+00:00', '2026-10-08T12:05:00+00:00')",
        (CHAT,),
    )
    conn.commit()
    punkt_id = cur.lastrowid

    getroffen = repo.setze_bedarf_erledigt(conn, CHAT, punkt_id, False)

    assert getroffen is True
    punkte = repo.bedarf(conn, CHAT)
    assert punkte[0]["erledigt_am"] is None


def test_setze_bedarf_erledigt_unbekannte_id_liefert_false(conn):
    assert repo.setze_bedarf_erledigt(conn, CHAT, 9999, True) is False


def test_setze_bedarf_erledigt_fremde_gruppe_liefert_false(conn):
    """Eine chat_id, die nicht zum Punkt gehoert, trifft nichts -- das ist
    die Grundlage der 404-Antwort im Web-Chat-Weg (fremde Gruppe darf einen
    Punkt weder lesen noch abhaken)."""
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere Gruppe")
    cur = conn.execute(
        "INSERT INTO bedarf_punkt (chat_id, sektion, text, reihenfolge, erstellt_am) "
        "VALUES (2, 'Props', 'Chair', 1, '2026-10-08T12:00:00+00:00')",
    )
    conn.commit()
    punkt_id = cur.lastrowid

    assert repo.setze_bedarf_erledigt(conn, CHAT, punkt_id, True) is False
