import json

from interview_theater import db, repo
from simulation import browser_mitschnitt as m

CHAT = 7_000_000_000_777


def _db(tmp_path):
    pfad = str(tmp_path / "sim.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "bot", "Testgruppe")
    conn.commit()
    conn.close()
    return pfad


def test_datenstand_liest_den_leeren_arbeitsstand(tmp_path):
    pfad = _db(tmp_path)
    stand = m.datenstand(pfad, CHAT)
    assert stand["journal_anzahl"] == 0
    assert stand["szenen_anzahl"] == 0


def test_unterschied_findet_ein_neu_gesetztes_feld(tmp_path):
    pfad = _db(tmp_path)
    vorher = m.datenstand(pfad, CHAT)
    conn = db.verbinde(pfad)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe", "Ankommen, Arbeit")
    conn.commit()
    conn.close()
    nachher = m.datenstand(pfad, CHAT)
    diff = m.unterschied(vorher, nachher)
    assert diff["arbeitsstand_geaendert"]["begriffe"] == "Ankommen, Arbeit"


def test_mitschnitt_schreibt_eine_jsonl_zeile(tmp_path):
    aufzeichner = m.Mitschnitt(tmp_path / "lauf1", "lauf1", "handy")
    vor = aufzeichner.screenshot_pfad(1, "vor")
    nach = aufzeichner.screenshot_pfad(1, "nach")
    vor.write_bytes(b"x")
    nach.write_bytes(b"y")
    aufzeichner.schritt(
        phase=1, screenshot_vorher=vor, screenshot_nachher=nach,
        elemente=[{"id": 0}], aktion={"type": "wait"}, begruendung="warte",
        antwort={"sekunden": 1.2, "ohne_hinweis": False}, db_diff={},
    )
    zeilen = (tmp_path / "lauf1" / "schritte.jsonl").read_text().splitlines()
    assert len(zeilen) == 1
    zeile = json.loads(zeilen[0])
    assert zeile["phase"] == 1
    assert zeile["begruendung"] == "warte"
    assert zeile["antwort_sekunden"] == 1.2


def test_datenstand_zaehlt_kalibrierung_und_diskussion(tmp_path):
    from interview_theater import db, repo
    from simulation import browser_mitschnitt as m
    pfad = str(tmp_path / "d.db")
    conn = db.verbinde(pfad); db.initialisiere(conn)
    repo.sichere_gruppe(conn, 7_000_000_000_777, "g", "G"); conn.commit(); conn.close()
    stand = m.datenstand(pfad, 7_000_000_000_777)
    assert stand["kalibrierung_aufnahmen"] == 0
    assert stand["diskussion_aufnahmen"] == 0
    assert "kalibrierung_modus" in stand


def test_schritt_schreibt_die_station(tmp_path):
    import json
    from simulation import browser_mitschnitt as m
    ms = m.Mitschnitt(tmp_path, "l", "handy")
    ms.schritt(phase=1, screenshot_vorher=tmp_path / "a.png",
               screenshot_nachher=tmp_path / "b.png", elemente=[], aktion={},
               begruendung="", antwort={}, db_diff={}, station="p1-eintritt")
    assert json.loads(ms.jsonl_pfad.read_text())["station"] == "p1-eintritt"
