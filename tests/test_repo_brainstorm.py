"""Repo-Schicht des Brainstorm-Modus (Phase 4, nur Web, 02.10.2026)."""

import pytest
from interview_theater import db, repo

CHAT = 1


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


def _lege_segment_an(conn, message_id: int, transkript: str, schnittgrund: str) -> int:
    aufnahme_id = repo.lege_aufnahme_an(
        conn, CHAT, message_id, "kurz", "sprache",
        schnittgrund=schnittgrund, brainstorm=True,
    )
    conn.execute(
        "UPDATE aufnahme SET transkript = ? WHERE id = ?", (transkript, aufnahme_id),
    )
    conn.commit()
    return aufnahme_id


def test_brainstorm_stand_ist_leer_ohne_segmente(conn):
    stand = repo.brainstorm_stand(conn, CHAT)
    assert stand == {
        "unreagierte_zeichen": 0,
        "sekunden_seit_letzter_reaktion": None,
        "letzter_schnittgrund": None,
    }


def test_brainstorm_stand_zaehlt_zeichen_und_nennt_den_juengsten_schnittgrund(conn):
    _lege_segment_an(conn, 1, "Erster Gedanke.", "cap")
    _lege_segment_an(conn, 2, "Zweiter Gedanke, etwas laenger.", "pause")
    stand = repo.brainstorm_stand(conn, CHAT)
    assert stand["unreagierte_zeichen"] == len("Erster Gedanke.") + len(
        "Zweiter Gedanke, etwas laenger."
    )
    assert stand["letzter_schnittgrund"] == "pause"
    assert stand["sekunden_seit_letzter_reaktion"] is None


def test_markiere_brainstorm_reaktion_setzt_zeichen_auf_den_rest_zurueck(conn):
    erste_id = _lege_segment_an(conn, 1, "Erster Gedanke.", "pause")
    repo.markiere_brainstorm_reaktion(conn, CHAT, erste_id)
    _lege_segment_an(conn, 2, "Danach Gesagtes.", "pause")
    stand = repo.brainstorm_stand(conn, CHAT)
    assert stand["unreagierte_zeichen"] == len("Danach Gesagtes.")
    assert stand["sekunden_seit_letzter_reaktion"] is not None
    assert stand["sekunden_seit_letzter_reaktion"] >= 0


def test_hoechste_brainstorm_aufnahme_id_ignoriert_andere_klassen(conn):
    assert repo.hoechste_brainstorm_aufnahme_id(conn, CHAT) == 0
    repo.lege_aufnahme_an(conn, CHAT, 1, "kurz", "sprache")   # kein Brainstorm
    assert repo.hoechste_brainstorm_aufnahme_id(conn, CHAT) == 0
    zweite_id = _lege_segment_an(conn, 2, "Text", "pause")
    assert repo.hoechste_brainstorm_aufnahme_id(conn, CHAT) == zweite_id


def test_entfernte_segmente_zaehlen_nicht_mit(conn):
    eins = _lege_segment_an(conn, 1, "Weg damit.", "pause")
    conn.execute("UPDATE aufnahme SET entfernt_am = ? WHERE id = ?", ("2026-10-02T10:00:00", eins))
    conn.commit()
    stand = repo.brainstorm_stand(conn, CHAT)
    assert stand["unreagierte_zeichen"] == 0
    assert stand["letzter_schnittgrund"] is None


def test_brainstorm_transkript_haengt_chronologisch_an(conn):
    _lege_segment_an(conn, 1, "Erstens.", "pause")
    _lege_segment_an(conn, 2, "Zweitens.", "cap")
    assert repo.brainstorm_transkript(conn, CHAT) == "Erstens.\n\nZweitens."


def test_brainstorm_transkript_ist_leer_ohne_segmente(conn):
    assert repo.brainstorm_transkript(conn, CHAT) == ""


def test_brainstorm_transkript_laesst_nicht_brainstorm_segmente_weg(conn):
    repo.lege_aufnahme_an(conn, CHAT, 1, "kurz", "sprache")
    conn.execute(
        "UPDATE aufnahme SET transkript = ? WHERE message_id = 1", ("Normaler Beitrag.",),
    )
    conn.commit()
    _lege_segment_an(conn, 2, "Brainstorm-Gedanke.", "pause")
    assert repo.brainstorm_transkript(conn, CHAT) == "Brainstorm-Gedanke."


def test_buehnenkarte_anlegen_und_lesen_neueste_zuerst(conn):
    repo.lege_buehnenkarte_an(conn, CHAT, "Erste Karte", "infomaniak")
    repo.lege_buehnenkarte_an(conn, CHAT, "Zweite Karte", "claude")
    karten = repo.buehnenkarten(conn, CHAT)
    assert [k["text"] for k in karten] == ["Zweite Karte", "Erste Karte"]
    assert karten[0]["modell"] == "claude"


def test_buehnenkarten_hoechstens_begrenzt(conn):
    for i in range(5):
        repo.lege_buehnenkarte_an(conn, CHAT, f"Karte {i}", "infomaniak")
    assert len(repo.buehnenkarten(conn, CHAT, hoechstens=2)) == 2


def test_eine_andere_gruppe_sieht_nichts(conn):
    repo.sichere_gruppe(conn, CHAT + 1, "gruppe2", "Andere")
    _lege_segment_an(conn, 1, "Nur fuer gruppe1.", "pause")
    repo.lege_buehnenkarte_an(conn, CHAT, "Nur fuer gruppe1", "infomaniak")
    assert repo.brainstorm_stand(conn, CHAT + 1)["unreagierte_zeichen"] == 0
    assert repo.brainstorm_transkript(conn, CHAT + 1) == ""
    assert repo.buehnenkarten(conn, CHAT + 1) == []
