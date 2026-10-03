"""Padua Phasen TEIL 2: Speicher fuer Erstfassung, Abnahmen und das
Protokoll jedes Prueflaufs."""

from interview_theater import db, repo


def _szene(conn, chat_id=1, nummer=1):
    return repo.stelle_szene_sicher(conn, chat_id, nummer)


def test_erstentwurf_zeigt_auf_eine_fassung(conn):
    sid = _szene(conn)
    repo.haenge_szenenfassung_an(conn, 1, sid, "Erste Fassung.")
    repo.haenge_szenenfassung_an(conn, 1, sid, "Zweite Fassung.")
    erste = repo.szenenfassungen(conn, sid)[0]
    repo.setze_szene_erstentwurf(conn, sid, erste["nummer"])
    assert repo.erstentwurf_text(conn, sid) == "Erste Fassung."
    assert repo.letzte_szenenfassung(conn, sid)["volltext"] == "Zweite Fassung."


def test_ohne_erstentwurf_kein_text(conn):
    sid = _szene(conn)
    assert repo.erstentwurf_text(conn, sid) is None
    assert repo.letzte_szenenfassung(conn, sid) is None


def test_ueberarbeitung_bestaetigt_und_arbeitsstandfelder(conn):
    sid = _szene(conn)
    repo.setze_szene_ueberarbeitung_bestaetigt(conn, sid)
    assert repo.hole_szene(conn, sid)["ueberarbeitung_bestaetigt_am"]
    repo.setze_arbeitsstand(conn, 1, "gesamttext_fixiert_am", "2026-10-03T10:00:00")
    repo.setze_arbeitsstand(conn, 1, "sprechweisen_fixiert_am", "2026-10-03T10:00:00")
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["gesamttext_fixiert_am"] and stand["sprechweisen_fixiert_am"]


def test_prueflauf_protokoll(conn):
    rid = repo.lege_prueflauf_an(
        conn, 1, phase=6, ziel="szene", szene_nummer=2, fragen="b1,a10",
        runden=2, ueberarbeitungen=1, auftraege_je_runde="2,0",
        zweite_runde_mit_auftraegen=False, grund="keine_auftraege",
        verworfen=None, dauer_ms=1234,
    )
    zeilen = repo.prueflaeufe(conn, 1)
    assert [z["id"] for z in zeilen] == [rid]
    assert zeilen[0]["zweite_runde_mit_auftraegen"] == 0
    assert zeilen[0]["auftraege_je_runde"] == "2,0"


def test_prueflauf_gehoert_zum_loeschweg():
    assert "prueflauf" in db.TABELLEN_MIT_CHAT_ID


def test_letzte_runde_zaehlt_auch_bewertungen(conn):
    repo.lege_dramaturgie_bewertungen_an(
        conn, 1, [{"pruefung": "b1", "szene": 1, "score": 2}], runde=4)
    assert repo.letzte_dramaturgie_runde(conn, 1) == 4
