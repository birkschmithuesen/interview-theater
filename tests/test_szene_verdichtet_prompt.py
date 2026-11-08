"""Der schlanke Prosa-Prompt unter ``[skript] verdichtet`` (Birk 07.10.2026
~17:45, Messung Robo G1 Szene 1): Format im Rahmenblock, keine Chat-Dublette
neben dem Phase-5-Gespraech, keine Begruendungskette in "Diese Szene",
Dramen-Aufgabe nur bei dramatischem Format."""

from datetime import datetime, timedelta, timezone

import pytest

from interview_theater import repo, schaerfung, szene, workshop

ZITAT = "Casa non sono le mura, sono le voci."


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    monkeypatch.setattr(workshop, "vollmaterial_phase5_aktiv", lambda *a: True)
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def _lage(conn, format_="Concert performance, post-dramatic, the music never stops"):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Probenraum am Abend")
    repo.setze_arbeitsstand(conn, 1, "format", format_)
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_transkript(conn, kopf_id, ZITAT)
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Z.", [
        {"thema": "Stimmen", "beleg_zitat": ZITAT, "zitat_geprueft": 1}])
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Le voci")
    repo.setze_szenenfeld(conn, szene_id, "was_passiert",
                          "Die vier teilen die Stimmen. traegt die Begruendungskette")
    thema = conn.execute("SELECT id FROM verdichtung_thema").fetchone()["id"]
    repo.lege_schaerfung_an(conn, 1, [{"verdichtung_thema_id": thema, "szene_id": szene_id,
                                       "begruendung": "traegt die Begruendungskette"}])
    schaerfung.uebernimm_stellen(conn, 1, [z["id"] for z in repo.schaerfungen(conn, 1)])
    jetzt = datetime.now(timezone.utc)
    repo.schreibe_journal(conn, 1, "entschieden", "Phase 5 · Prose Draft", "befehl")
    conn.execute("UPDATE journal SET erstellt_am = ?",
                 ((jetzt - timedelta(minutes=5)).isoformat(timespec="seconds"),))
    conn.commit()
    repo.merke_nachricht(conn, 1, 11, "Gruppe", 0, "text", "Bitte mehr Gitarre in Szene 1",
                         jetzt.isoformat(timespec="seconds"))
    return repo.hole_szene(conn, szene_id)


def _text(conn, ziel):
    return szene.baue_nutzertext(conn, 1, "Schreib Szene 1.", ziel)


def test_padua_verdichtet(conn, padua):
    ziel = _lage(conn)
    text = _text(conn, ziel)
    assert "post-dramatic" in text                     # C1 Format
    assert text.count("Bitte mehr Gitarre") == 1       # C2 keine Dublette
    assert "Begruendungskette" not in text             # C3
    assert ZITAT in text                               # Zitat woertlich im Kernpaket
    assert szene.T._AUFGABE_NEUTRAL in text            # C4
    assert "exposition" not in text.lower()


def test_dramatisches_format_behaelt_die_aufgabe(conn, padua):
    ziel = _lage(conn, format_="A theatre play in five scenes")
    text = _text(conn, ziel)
    assert szene.T._AUFGABE_ERSTE in text


def test_ohne_schalter_wie_bisher(conn, monkeypatch):
    monkeypatch.setattr(workshop, "vollmaterial_phase5_aktiv", lambda *a: True)
    ziel = _lage(conn)
    text = _text(conn, ziel)
    assert "post-dramatic" not in text
    assert "Begruendungskette" in text
    assert szene.T._AUFGABE_ERSTE in text
    assert text.count("Bitte mehr Gitarre") == 2
