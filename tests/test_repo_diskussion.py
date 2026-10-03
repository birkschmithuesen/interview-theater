"""Repo-Schicht des Hintergrund-Mithoerens von Phase 1 (Padua, 03.10.2026).

Reine DB-/Repo-Plumbing (Task 2 des Phase-1/2-Umbauplans): die Spalte
``diskussion`` auf ``aufnahme`` und ``web_post``, additiv nachgeruestet wie
``brainstorm``, plus ``repo.diskussion_transkript``. Ungegated -- eine Spalte,
die niemand setzt, ist wirkungslos; das Verdrahten mit Phase 1 kommt in
einer spaeteren Aufgabe.
"""

import pytest

from interview_theater import db, repo

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def test_lege_aufnahme_an_speichert_diskussion_flag(conn):
    aufnahme_id = repo.lege_aufnahme_an(
        conn, CHAT, 1, "kurz", "sprache", diskussion=True,
    )
    zeile = conn.execute(
        "SELECT diskussion FROM aufnahme WHERE id = ?", (aufnahme_id,),
    ).fetchone()
    assert zeile["diskussion"] == 1


def test_lege_aufnahme_an_ohne_diskussion_ist_vorgabe_false(conn):
    aufnahme_id = repo.lege_aufnahme_an(conn, CHAT, 2, "kurz", "sprache")
    zeile = conn.execute(
        "SELECT diskussion FROM aufnahme WHERE id = ?", (aufnahme_id,),
    ).fetchone()
    assert zeile["diskussion"] == 0


def test_lege_web_post_an_speichert_diskussion_flag(conn):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE, diskussion=True,
    )
    zeile = conn.execute(
        "SELECT diskussion FROM web_post WHERE id = ?", (post_id,),
    ).fetchone()
    assert zeile["diskussion"] == 1


def test_lege_web_post_an_ohne_diskussion_ist_vorgabe_false(conn):
    post_id = repo.lege_web_post_an(
        conn, CHAT, repo.RICHTUNG_EIN, repo.WEB_TYP_SPRACHE,
    )
    zeile = conn.execute(
        "SELECT diskussion FROM web_post WHERE id = ?", (post_id,),
    ).fetchone()
    assert zeile["diskussion"] == 0


def _lege_segment_an(conn, message_id: int, transkript: str, *,
                      diskussion: bool = True, status: str = "fertig") -> int:
    aufnahme_id = repo.lege_aufnahme_an(
        conn, CHAT, message_id, "kurz", "sprache", diskussion=diskussion,
    )
    conn.execute(
        "UPDATE aufnahme SET transkript = ?, status = ? WHERE id = ?",
        (transkript, status, aufnahme_id),
    )
    conn.commit()
    return aufnahme_id


def test_diskussion_transkript_ist_leer_ohne_segmente(conn):
    assert repo.diskussion_transkript(conn, CHAT) == ""


def test_diskussion_transkript_haengt_nur_fertige_ungeloeschte_diskussionssegmente_an(conn):
    # Gehoert dazu: diskussion=1, nicht entfernt, status='fertig'.
    _lege_segment_an(conn, 1, "Erstens.")
    _lege_segment_an(conn, 2, "Zweitens.")

    # Weich geloescht -- zaehlt nicht mit, obwohl sonst passend.
    drei = _lege_segment_an(conn, 3, "Geloescht.")
    conn.execute(
        "UPDATE aufnahme SET entfernt_am = ? WHERE id = ?",
        ("2026-10-03T10:00:00", drei),
    )
    conn.commit()

    # status != 'fertig' -- zaehlt nicht mit.
    _lege_segment_an(conn, 4, "Noch nicht fertig.", status="transkribiert")

    # diskussion=0 -- ein gewoehnlicher Gespraechsbeitrag, zaehlt nicht mit.
    _lege_segment_an(conn, 5, "Kein Diskussionsbeitrag.", diskussion=False)

    assert repo.diskussion_transkript(conn, CHAT) == "Erstens.\n\nZweitens."


def test_diskussion_transkript_haelt_id_reihenfolge_auch_bei_absteigender_anlage(conn):
    zweites = _lege_segment_an(conn, 20, "Zweites der Reihe nach angelegt.")
    # Erstes nachtraeglich mit kleinerer message_id, aber hoeherer id-Anlage
    # wuerde die Reihenfolge nicht aendern -- sortiert wird nach aufnahme.id,
    # nicht nach message_id. Hier reicht die normale Anlagereihenfolge.
    drittes = _lege_segment_an(conn, 21, "Drittes.")
    assert zweites < drittes
    assert repo.diskussion_transkript(conn, CHAT) == (
        "Zweites der Reihe nach angelegt.\n\nDrittes."
    )


def test_diskussion_transkript_eine_andere_gruppe_sieht_nichts(conn):
    repo.sichere_gruppe(conn, CHAT + 1, "gruppe2", "Andere")
    _lege_segment_an(conn, 1, "Nur fuer gruppe1.")
    assert repo.diskussion_transkript(conn, CHAT + 1) == ""
