"""Die aggregierte Padua-Fixture: mehrere Sessions je Strang auf EINEM chat_id.

Die Zahlen und Pruefungen hier sind keine Wuensche, sondern der Beleg fuer die
vier verifizierten Tatsachen aus dem Kartentext (t_97f605c7): Ersetzen vs.
Anhaengen bei der Diskussionsverdichtung, "nur der juengste Board-Stand zaehlt"
bei ``begriffe_detail``, Anhaengen bei den Interview-Verdichtungen, und
monotones Wachstum des Brainstorm-Transkripts.
"""
import json

import pytest

from interview_theater import db, repo
from scripts import fixture_padua_aggregiert as fix


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "fixture_aggregiert.db"))
    db.initialisiere(verbindung)
    yield verbindung
    verbindung.close()


# --------------------------------------------------------------------------
# Strang 1: Diskussion
# --------------------------------------------------------------------------


def test_diskussion_verdichtung_wird_ersetzt_nicht_angehaengt(conn):
    chat_id = fix.chat_id_fuer("diskussion")
    sessions = fix.baue_diskussion_sessions(conn, chat_id, 5)

    zeilen = conn.execute(
        "SELECT COUNT(*) FROM diskussion_verdichtung WHERE chat_id=?",
        (chat_id,),
    ).fetchone()[0]
    assert zeilen == 1

    gespeichert = repo.diskussion_verdichtung_text(conn, chat_id)
    assert gespeichert == sessions[-1]["verdichtung_text"]
    assert gespeichert != sessions[0]["verdichtung_text"]


def test_begriffsboard_haengt_an_aber_detail_spiegelt_nur_juengsten_stand(conn):
    chat_id = fix.chat_id_fuer("diskussion")
    fix.baue_diskussion_sessions(conn, chat_id, 5)

    board_zeilen = conn.execute(
        "SELECT COUNT(*) FROM begriffsboard WHERE chat_id=?", (chat_id,),
    ).fetchone()[0]
    assert board_zeilen == 5

    stand = repo.hole_arbeitsstand(conn, chat_id)
    # "arrival" steht in Session 1+2 im Arbeitsstand UND im Board; ab
    # Session 3 fuehrt das Board es nicht mehr, aber die Begriffsliste
    # behaelt es (additiv). Zeigt begriffe_detail trotzdem nichts mehr fuer
    # "arrival", spiegelt es wirklich nur den juengsten Board-Stand.
    assert "arrival" in stand["begriffe"]
    detail = json.loads(stand["begriffe_detail"])
    nach_begriff = {e["begriff"]: e for e in detail}
    assert nach_begriff["arrival"]["begruendung"] == ""
    assert nach_begriff["arrival"]["zitat"] == ""
    # "language" kam erst in Session 5 dazu und steht im juengsten Board --
    # sein Detail ist dagegen gefuellt.
    assert nach_begriff["language"]["begruendung"] != ""


def test_begriffe_detail_folgt_der_aktuellen_begriffsliste(conn):
    """detail_fuer liefert genau einen Eintrag je Begriff der aktuellen
    Liste, in deren Reihenfolge -- auch fuer Begriffe ohne Boardzeile."""
    chat_id = fix.chat_id_fuer("diskussion")
    fix.baue_diskussion_sessions(conn, chat_id, 5)
    stand = repo.hole_arbeitsstand(conn, chat_id)
    detail = json.loads(stand["begriffe_detail"])
    erwartet = ["arrival", "waiting", "noise", "belonging", "trust", "language"]
    assert [e["begriff"] for e in detail] == erwartet


def test_genau_eine_diskussionssession_ist_die_fabrikation(conn):
    chat_id = fix.chat_id_fuer("diskussion")
    sessions = fix.baue_diskussion_sessions(conn, chat_id, 5)

    fabriziert = [s for s in sessions if s["fabrikation"]]
    assert len(fabriziert) == 1
    session = fabriziert[0]
    wort = session["fabrikationswort"]
    assert wort

    for s in sessions:
        assert wort not in s["transkript_bisher"], s["session"]
    assert wort in session["verdichtung_text"]


def test_diskussion_hat_genug_segmente_fuer_fuenf_sessions(conn):
    chat_id = fix.chat_id_fuer("diskussion")
    fix.baue_diskussion_sessions(conn, chat_id, 5)
    segmente = conn.execute(
        "SELECT COUNT(*) FROM aufnahme WHERE chat_id=? AND diskussion=1",
        (chat_id,),
    ).fetchone()[0]
    assert segmente == 10  # 2 je Session * 5 Sessions


# --------------------------------------------------------------------------
# Strang 2: Interviews
# --------------------------------------------------------------------------


def test_interview_verdichtungen_haengen_an(conn):
    chat_id = fix.chat_id_fuer("interviews")
    fix.baue_interview_sessions(conn, chat_id, 5)
    assert len(repo.verdichtungen(conn, chat_id)) == 5


def test_genau_ein_interview_ist_die_fabrikation(conn):
    chat_id = fix.chat_id_fuer("interviews")
    sessions = fix.baue_interview_sessions(conn, chat_id, 5)

    fabriziert = [s for s in sessions if s["fabrikation"]]
    assert len(fabriziert) == 1
    session = fabriziert[0]
    assert session["session"] not in (1, 5)  # nicht erstes, nicht letztes

    wort = session["fabrikationswort"]
    assert wort
    assert wort not in session["transkript"]
    assert wort in session["zusammenfassung"]


def test_jedes_interview_hat_geprueftes_belegzitat(conn):
    chat_id = fix.chat_id_fuer("interviews")
    sessions = fix.baue_interview_sessions(conn, chat_id, 5)
    for session in sessions:
        themen = conn.execute(
            "SELECT beleg_zitat FROM verdichtung_thema WHERE verdichtung_id=?",
            (session["verdichtung_id"],),
        ).fetchall()
        assert themen
        for zeile in themen:
            assert zeile["beleg_zitat"] in session["transkript"]


def test_interviews_zyklisch_ueber_die_fuenf_dateien(conn):
    chat_id = fix.chat_id_fuer("interviews")
    sessions = fix.baue_interview_sessions(conn, chat_id, 5)
    transkripte = {s["session"]: s["transkript"] for s in sessions}
    # Fuenf unterschiedliche Transkripte -- kein Interview wiederholt sich
    # bei anzahl=5.
    assert len(set(transkripte.values())) == 5


# --------------------------------------------------------------------------
# Strang 3: Brainstorm
# --------------------------------------------------------------------------


def test_brainstorm_transkript_waechst_strikt_monoton(conn):
    chat_id = fix.chat_id_fuer("brainstorm")
    sessions = fix.baue_brainstorm_sessions(conn, chat_id, 5)
    zeichen = [s["brainstorm_transkript_zeichen"] for s in sessions]
    assert zeichen == sorted(zeichen)
    assert len(set(zeichen)) == len(zeichen)  # strikt, keine Gleichstaende


def test_brainstorm_karten_werden_persistiert(conn):
    chat_id = fix.chat_id_fuer("brainstorm")
    sessions = fix.baue_brainstorm_sessions(conn, chat_id, 5)
    assert all(s["karte_persistiert"] for s in sessions)
    karten = conn.execute(
        "SELECT COUNT(*) FROM buehnenkarte WHERE chat_id=?", (chat_id,),
    ).fetchone()[0]
    assert karten == 5


def test_genau_eine_brainstormsession_ist_die_fabrikation(conn):
    chat_id = fix.chat_id_fuer("brainstorm")
    sessions = fix.baue_brainstorm_sessions(conn, chat_id, 5)

    fabriziert = [s for s in sessions if s["fabrikation"]]
    assert len(fabriziert) == 1
    session = fabriziert[0]
    assert session["session"] not in (1, 5)

    wort = session["fabrikationswort"]
    assert wort
    transkript = repo.brainstorm_transkript(conn, chat_id)
    assert wort not in transkript

    karten = conn.execute(
        "SELECT text FROM buehnenkarte WHERE chat_id=? ORDER BY id ASC",
        (chat_id,),
    ).fetchall()
    gefunden = [k for k in karten if wort in k["text"]]
    assert len(gefunden) == 1


def test_brainstorm_phase_ist_vier(conn):
    chat_id = fix.chat_id_fuer("brainstorm")
    fix.baue_brainstorm_sessions(conn, chat_id, 5)
    assert repo.hole_phase(conn, chat_id) == 4


# --------------------------------------------------------------------------
# baue_alle
# --------------------------------------------------------------------------


def test_baue_alle_liefert_drei_straenge_mit_fuenf_sessions(conn):
    ergebnis = fix.baue_alle(conn)
    assert set(ergebnis.keys()) == {"diskussion", "interviews", "brainstorm"}
    for strang, daten in ergebnis.items():
        assert daten["chat_id"] == fix.chat_id_fuer(strang)
        assert len(daten["sessions"]) == 5


def test_chat_ids_kollidieren_nicht_mit_fixture_padua_voll():
    from scripts import fixture_padua_voll as voll

    aggregiert_ids = {fix.chat_id_fuer(s) for s in ("diskussion", "interviews",
                                                     "brainstorm")}
    voll_ids = {voll.chat_id_fuer(p) for p in voll.PHASEN}
    assert aggregiert_ids.isdisjoint(voll_ids)
    assert all(i > repo.WEB_CHAT_ID_BASIS for i in aggregiert_ids)


def test_fixture_nennt_kein_betriebsverzeichnis():
    """Wie test_fixture_padua_voll.py: keine Betriebsdatei, auch nicht lesend."""
    import inspect

    quelle = inspect.getsource(fix)
    for wort in ("betrieb/", "soap.db", "IT_DB"):
        assert wort not in quelle, wort
