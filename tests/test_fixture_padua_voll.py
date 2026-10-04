"""Die Padua-Fixture: sieben Gruppen mit realistischem Volumen.

Die Zahlen hier sind keine Wuensche, sondern die Bedingung dafuer, dass der
Prompt-Dump ueberhaupt etwas messen kann (Birk, 05.10.2026 00:40): gegen eine
frische Datenbank zeigt sich keiner der Befunde, die am 06.09.2026 gemessen
wurden.
"""
import pytest

from interview_theater import db, kontext, repo
from scripts import fixture_padua_voll as fix


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "fixture.db"))
    db.initialisiere(verbindung)
    fix.baue_alle(verbindung)
    yield verbindung
    verbindung.close()


def _alle_nachrichten(conn, chat_id):
    """Rueckfall ohne neue Repo-Funktion (``repo.alle_nachrichten`` existiert
    nicht -- siehe AGENTS.md-Fallenkatalog und Schritt 3 des Plans): direktes
    SQL nur hier im Test, nie in ``repo.py``."""
    return conn.execute(
        "SELECT * FROM nachricht WHERE chat_id=? ORDER BY gesendet_am",
        (chat_id,),
    ).fetchall()


def test_jede_phase_hat_eine_gruppe_mit_genug_verlauf(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        nachrichten = _alle_nachrichten(conn, chat_id)
        assert len(nachrichten) >= 34, (phase, len(nachrichten))


def test_jede_gruppe_traegt_systemzeilen_und_ein_transkript_echo(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        texte = [n["text"] for n in _alle_nachrichten(conn, chat_id)]
        assert any(t.startswith("📌 Agreed:") for t in texte), phase
        assert any(t.startswith("Noted:") for t in texte), phase
        assert any("please fix it in the work status" in t for t in texte), phase
        echos = conn.execute(
            "SELECT COUNT(*) FROM nachricht WHERE chat_id=? AND typ=?",
            (chat_id, repo.TYP_TRANSKRIPT),
        ).fetchone()[0]
        assert echos >= 1, phase


def test_mehrere_sprecher_je_gruppe(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        absender = {
            n["absender"] for n in _alle_nachrichten(conn, chat_id)
            if not n["ist_bot"]
        }
        assert len(absender) >= 3, (phase, absender)


def test_arbeitsstand_journal_und_festlegungen_sind_gefuellt(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        stand = repo.hole_arbeitsstand(conn, chat_id)
        assert stand["begriffe"], phase
        if phase >= 2:
            assert stand["fragen"], phase
        if phase >= 4:
            assert stand["rahmen"] and stand["geschichte"], phase
        assert repo.journal(conn, chat_id), phase
        assert repo.festlegungen(conn, chat_id), phase


def test_phase1_hat_diskussionssegmente_und_ein_begriffsboard(conn):
    chat_id = fix.chat_id_fuer(1)
    segmente = conn.execute(
        "SELECT COUNT(*) FROM aufnahme WHERE chat_id=? AND diskussion=1",
        (chat_id,),
    ).fetchone()[0]
    assert segmente >= 2
    board = conn.execute(
        "SELECT COUNT(*) FROM begriffsboard WHERE chat_id=?", (chat_id,)
    ).fetchone()[0]
    assert board >= 1


def test_ab_phase3_gibt_es_ein_verdichtetes_interview(conn):
    for phase in (3, 4, 5, 6, 7):
        chat_id = fix.chat_id_fuer(phase)
        assert repo.verdichtungen(conn, chat_id), phase


def test_das_fenster_schneidet_messbar_und_nicht_nur_nach_anzahl(conn):
    """Die Grenzen werden GEMESSEN, nicht angenommen (Birk 00:40).

    Mindestens eine Gruppe muss am Zeichenbudget schneiden und mindestens
    eine an der weichen Minutengrenze -- sonst ist die Fixture zu brav und
    der BEFUND kann zu den Fenstergrenzen nichts sagen."""
    gruende = set()
    for phase in fix.PHASEN:
        befund = fix.fensterbefund(conn, fix.chat_id_fuer(phase))
        assert befund["im_fenster"] < befund["nachrichten_gesamt"], phase
        assert befund["zeichen_im_fenster"] <= kontext.FENSTER_ZEICHEN
        gruende.add(befund["grund"])
    assert "zeichen" in gruende, gruende
    assert "minuten" in gruende, gruende


def test_fixture_nennt_kein_betriebsverzeichnis():
    """Die Fixture darf keine Betriebsdatei kennen -- auch nicht lesend."""
    import inspect

    quelle = inspect.getsource(fix)
    for wort in ("betrieb/", "soap.db", "IT_DB"):
        assert wort not in quelle, wort
