"""Interview-Mapping gegen verworfene Ideen (Birk 07.10.2026 ~17:45, G2: das
Schild war verworfen, die Zuordnung hing trotzdem daran). Unter
``[skript] verdichtet`` bekommt der Matcher die ``verworfen``-Zeilen des
Journals als ausdrueckliches Nicht-Ziel, und die Ziel-Beschreibung traegt
keine Begruendungen frueherer Runden mehr."""

import pytest

from interview_theater import repo, schaerfung, workshop

SCHILD = "the sign 'vuoi fare due chiacchiere?' -- Arlecchino is the only lure"


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()


def _lage(conn):
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_transkript(conn, kopf_id, "Mi siedo solo al tavolo.")
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    repo.speichere_verdichtung(conn, 1, kopf_id, "Z.", [
        {"thema": "Disagio", "beleg_zitat": "Mi siedo solo al tavolo.", "zitat_geprueft": 1}])
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "inizio")
    # Altbestand: eine Begruendung frueherer Runde haengt noch an.
    repo.setze_szenenfeld(conn, szene_id, "was_passiert",
                          "Francesca sits alone at the bar table. the sign lures passers-by")
    thema = conn.execute("SELECT id FROM verdichtung_thema").fetchone()["id"]
    repo.lege_schaerfung_an(conn, 1, [{"verdichtung_thema_id": thema, "szene_id": szene_id,
                                       "begruendung": "the sign lures passers-by"}])
    conn.execute("UPDATE schaerfung SET uebernommen_am = '2026-10-07T14:00:00'")
    conn.commit()
    repo.schreibe_journal(conn, 1, "verworfen", SCHILD, "befehl")


def _ziel_und_text(conn):
    ziel = [z for z in schaerfung._ziele(conn, 1) if z["art"] == "szene"][0]
    return ziel, schaerfung._baue_nutzertext_ziel(conn, 1, [], ziel)


def test_padua_verworfen_im_hintergrund_nicht_im_ziel(conn, padua):
    _lage(conn)
    ziel, text = _ziel_und_text(conn)
    assert "sign" not in ziel["beschreibung_text"]
    assert "cartello" not in ziel["beschreibung_text"]
    assert SCHILD in text
    assert schaerfung.T._HINTERGRUND_VERWORFEN.split("{text}")[0].strip() in text


def test_ohne_schalter_unveraendert(conn):
    _lage(conn)
    ziel, text = _ziel_und_text(conn)
    assert "the sign lures" in ziel["beschreibung_text"]
    assert SCHILD not in text
