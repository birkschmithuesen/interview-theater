"""Repo-Ergaenzungen aus Aufgabe 7: Aufnahmen und Verdichtungen.

Eigene Datei statt Erweiterung von test_repo.py, weil Letzteres eine
vorhandene Testdatei ist (Aufgabe-7-Auftrag: nicht anfassen).
"""

import pytest
from theatersoap import db, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def test_lege_aufnahme_an_vergibt_hochzaehlende_ersatznamen(conn):
    a1 = repo.lege_aufnahme_an(conn, 1, 100, "kurz", "sprache", audio_pfad="a.ogg")
    a2 = repo.lege_aufnahme_an(conn, 1, 101, "lang", "sprache", audio_pfad="b.ogg")
    assert repo.hole_aufnahme(conn, a1)["name"] == "Interview 1"
    assert repo.hole_aufnahme(conn, a2)["name"] == "Interview 2"


def test_lege_aufnahme_an_speichert_alle_felder(conn):
    aid = repo.lege_aufnahme_an(conn, 1, 200, "lang", "sprache",
                                  audio_pfad="pfad.ogg", dauer=87)
    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["chat_id"] == 1
    assert zeile["message_id"] == 200
    assert zeile["klasse"] == "lang"
    assert zeile["quelle"] == "sprache"
    assert zeile["audio_pfad"] == "pfad.ogg"
    assert zeile["dauer_sekunden"] == 87
    assert zeile["status"] == "empfangen"
    assert zeile["versuche"] == 0
    assert zeile["empfangen_am"] is not None


def test_lege_aufnahme_an_ohne_audio_bei_textquelle(conn):
    aid = repo.lege_aufnahme_an(conn, 1, 201, "kurz", "text")
    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["quelle"] == "text"
    assert zeile["audio_pfad"] is None


def test_hole_aufnahme_liefert_none_wenn_unbekannt(conn):
    assert repo.hole_aufnahme(conn, 9999) is None


def test_setze_status_und_fehlertext(conn):
    aid = repo.lege_aufnahme_an(conn, 1, 300, "kurz", "sprache")
    repo.setze_status(conn, aid, "fehlgeschlagen", fehlertext="Whisper nicht erreichbar")
    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["status"] == "fehlgeschlagen"
    assert zeile["fehlertext"] == "Whisper nicht erreichbar"


def test_setze_status_ohne_fehlertext_loescht_ihn_nicht_versehentlich(conn):
    aid = repo.lege_aufnahme_an(conn, 1, 301, "kurz", "sprache")
    repo.setze_status(conn, aid, "transkribiert")
    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["status"] == "transkribiert"
    assert zeile["fehlertext"] is None


def test_setze_transkript(conn):
    aid = repo.lege_aufnahme_an(conn, 1, 400, "kurz", "sprache")
    repo.setze_transkript(conn, aid, "Hallo, hier ist das Transkript.")
    assert repo.hole_aufnahme(conn, aid)["transkript"] == "Hallo, hier ist das Transkript."


def test_setze_aufnahme_name(conn):
    aid = repo.lege_aufnahme_an(conn, 1, 500, "lang", "sprache")
    repo.setze_aufnahme_name(conn, aid, "Maria")
    assert repo.hole_aufnahme(conn, aid)["name"] == "Maria"


def test_offene_aufnahmen_schliesst_fertig_und_fehlgeschlagen_aus(conn):
    offen1 = repo.lege_aufnahme_an(conn, 1, 600, "kurz", "sprache")
    offen2 = repo.lege_aufnahme_an(conn, 1, 601, "kurz", "sprache")
    fertig = repo.lege_aufnahme_an(conn, 1, 602, "kurz", "sprache")
    gescheitert = repo.lege_aufnahme_an(conn, 1, 603, "kurz", "sprache")
    repo.setze_status(conn, offen2, "transkribiert")
    repo.setze_status(conn, fertig, "fertig")
    repo.setze_status(conn, gescheitert, "fehlgeschlagen", fehlertext="kaputt")

    ids = {z["id"] for z in repo.offene_aufnahmen(conn)}
    assert ids == {offen1, offen2}


def test_zaehle_aufnahmen(conn):
    repo.sichere_gruppe(conn, 2, "gruppe1", "Zweite Testgruppe")
    repo.lege_aufnahme_an(conn, 1, 700, "kurz", "sprache")
    repo.lege_aufnahme_an(conn, 1, 701, "kurz", "sprache")
    repo.lege_aufnahme_an(conn, 2, 702, "kurz", "sprache")
    assert repo.zaehle_aufnahmen(conn, 1) == 2
    assert repo.zaehle_aufnahmen(conn, 2) == 1


def test_speichere_verdichtung_und_themen_zu(conn):
    aid = repo.lege_aufnahme_an(conn, 1, 800, "lang", "sprache")
    vid = repo.speichere_verdichtung(
        conn, 1, aid, "Eine kurze Zusammenfassung.",
        [
            {"thema": "Ankommen", "beleg_zitat": "Ich bin hier angekommen", "zitat_geprueft": 1},
            {"thema": "Abschied", "beleg_zitat": None, "zitat_geprueft": 0},
        ],
    )
    themen = repo.themen_zu(conn, vid)
    assert [t["thema"] for t in themen] == ["Ankommen", "Abschied"]
    assert themen[0]["beleg_zitat"] == "Ich bin hier angekommen"
    assert themen[0]["zitat_geprueft"] == 1
    assert themen[1]["beleg_zitat"] is None
    assert themen[1]["zitat_geprueft"] == 0
    assert all(t["chat_id"] == 1 for t in themen)


def test_verdichtungen_liefert_alle_fuer_chat_in_reihenfolge(conn):
    a1 = repo.lege_aufnahme_an(conn, 1, 900, "lang", "sprache")
    a2 = repo.lege_aufnahme_an(conn, 1, 901, "lang", "sprache")
    v1 = repo.speichere_verdichtung(conn, 1, a1, "Erste Zusammenfassung.", [])
    v2 = repo.speichere_verdichtung(conn, 1, a2, "Zweite Zusammenfassung.", [])
    assert [v["id"] for v in repo.verdichtungen(conn, 1)] == [v1, v2]


def test_transkripte_ohne_namen_liefert_alle(conn):
    repo.lege_aufnahme_an(conn, 1, 1000, "lang", "sprache")
    repo.lege_aufnahme_an(conn, 1, 1001, "lang", "sprache")
    assert len(repo.transkripte(conn, 1)) == 2


def test_transkripte_mit_namen_gross_klein_und_teiltreffer(conn):
    aid = repo.lege_aufnahme_an(conn, 1, 1100, "lang", "sprache")
    repo.setze_aufnahme_name(conn, aid, "Maria Schmidt")
    repo.lege_aufnahme_an(conn, 1, 1101, "lang", "sprache")  # bleibt "Interview 2"

    treffer = repo.transkripte(conn, 1, name="maria")
    assert [t["id"] for t in treffer] == [aid]

    treffer_teil = repo.transkripte(conn, 1, name="SCHMIDT")
    assert [t["id"] for t in treffer_teil] == [aid]

    assert repo.transkripte(conn, 1, name="niemand") == []
