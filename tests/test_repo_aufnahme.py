"""Repo-Ergaenzungen aus Aufgabe 7: Aufnahmen und Verdichtungen.

Eigene Datei statt Erweiterung von test_repo.py, weil Letzteres eine
vorhandene Testdatei ist (Aufgabe-7-Auftrag: nicht anfassen).
"""

import pytest
from interview_theater import db, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


def test_lege_aufnahme_an_vergibt_ersatznamen_nur_an_interviews(conn):
    """'Interview n' ist die laufende INTERVIEWnummer der Gruppe (§ 10.6),
    kein Nachrichtenzaehler: ein Gespraechsbeitrag (kurz) und ein Teil
    bekommen gar keinen Namen und verschieben die Zaehlung nicht."""
    kurz = repo.lege_aufnahme_an(conn, 1, 100, "kurz", "sprache", audio_pfad="a.ogg")
    erstes = repo.lege_aufnahme_an(conn, 1, 101, "lang", "sprache")
    teil = repo.lege_aufnahme_an(conn, 1, 102, "teil", "sprache", audio_pfad="b.ogg",
                                 teil_von=erstes)
    zweites = repo.lege_aufnahme_an(conn, 1, 103, "lang", "sprache")

    assert repo.hole_aufnahme(conn, kurz)["name"] is None
    assert repo.hole_aufnahme(conn, teil)["name"] is None
    assert repo.hole_aufnahme(conn, erstes)["name"] == "Interview 1"
    assert repo.hole_aufnahme(conn, zweites)["name"] == "Interview 2"


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


def test_setze_status_ohne_fehlertext_ueberschreibt_vorhandenen_fehlertext(conn):
    """Der urspruengliche Testname behauptete einen Schutz vor versehentlichem
    Loeschen, den setze_status gar nicht bietet: der Parameter fehlertext wird
    IMMER geschrieben (Vorgabe None), es gibt keine Sonderbehandlung, die einen
    vorhandenen Fehlertext beim naechsten Statuswechsel erhaelt. Dieser Test
    belegt das tatsaechliche Verhalten statt eines nie geprueften Anspruchs."""
    aid = repo.lege_aufnahme_an(conn, 1, 301, "kurz", "sprache")
    repo.setze_status(conn, aid, "fehlgeschlagen", fehlertext="Whisper nicht erreichbar")
    repo.setze_status(conn, aid, "transkribiert")
    zeile = repo.hole_aufnahme(conn, aid)
    assert zeile["status"] == "transkribiert"
    assert zeile["fehlertext"] is None, "fehlertext wird ohne Angabe auf None ueberschrieben"


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


# ---------------------------------------------------------------------------
# Ein Interview ist eine Einheit (§ 10.6, Nachtrag 05.09.2026)
# ---------------------------------------------------------------------------

def test_laufendes_interview_findet_nur_den_offenen_kopf(conn):
    assert repo.laufendes_interview(conn, 1) is None

    kopf = repo.lege_interview_an(conn, 1)
    assert repo.laufendes_interview(conn, 1)["id"] == kopf

    repo.setze_interview_beendet(conn, kopf)
    assert repo.laufendes_interview(conn, 1) is None, "beendet heisst nicht mehr laufend"


def test_teile_zusammenfuegen_in_reihenfolge_mit_leerzeile(conn):
    kopf = repo.lege_interview_an(conn, 1)
    for i, text in enumerate(["erster Teil", "zweiter Teil", "dritter Teil"]):
        teil = repo.lege_aufnahme_an(conn, 1, 500 + i, "teil", "sprache", teil_von=kopf)
        repo.setze_transkript(conn, teil, text)

    assert repo.zusammengefuegtes_transkript(conn, kopf) == (
        "erster Teil\n\nzweiter Teil\n\ndritter Teil"
    )
    assert [repo.teil_nummer(conn, t["id"]) for t in repo.hole_teile(conn, kopf)] == [1, 2, 3]


def test_zusammengefuegtes_transkript_faellt_auf_den_kopf_zurueck(conn):
    """Textimporte und alle Aufnahmen aus der Zeit vor dem Nachtrag tragen ihr
    Transkript am Kopf selbst -- ohne Teile gilt genau das."""
    kopf = repo.lege_aufnahme_an(conn, 1, 600, "lang", "text")
    repo.setze_transkript(conn, kopf, "Recherchematerial im Wortlaut")

    assert repo.zusammengefuegtes_transkript(conn, kopf) == "Recherchematerial im Wortlaut"


def test_hat_offene_teile_bis_jeder_teil_in_einem_endzustand_ist(conn):
    kopf = repo.lege_interview_an(conn, 1)
    teil = repo.lege_aufnahme_an(conn, 1, 700, "teil", "sprache", teil_von=kopf)
    assert repo.hat_offene_teile(conn, kopf) is True

    repo.setze_status(conn, teil, "fehlgeschlagen")
    assert repo.hat_offene_teile(conn, kopf) is False, "endgueltig gescheitert ist auch durch"


def test_offene_aufnahmen_lassen_ein_laufendes_interview_liegen(conn):
    """Ein laufendes Interview ist keine liegengebliebene Arbeit: der
    Nachhol-Arbeiter darf es nicht mitten im Satz verdichten. Beendet und
    unverdichtet gehoert es dagegen aufgegriffen -- ueber die zweite
    Abfrage."""
    kopf = repo.lege_interview_an(conn, 1)
    offene = [z["id"] for z in repo.offene_aufnahmen_fuer_bot(conn, "gruppe1")]

    assert kopf not in offene
    assert repo.beendete_offene_interviews(conn, "gruppe1") == []

    repo.setze_interview_beendet(conn, kopf)
    assert [z["id"] for z in repo.beendete_offene_interviews(conn, "gruppe1")] == [kopf]


def test_transkripte_liefert_keine_teile(conn):
    kopf = repo.lege_interview_an(conn, 1)
    repo.lege_aufnahme_an(conn, 1, 800, "teil", "sprache", teil_von=kopf)

    assert [z["id"] for z in repo.transkripte(conn, 1)] == [kopf]
    assert repo.zaehle_interviews(conn, 1) == 1
    assert repo.zaehle_aufnahmen(conn, 1) == 2, "gezaehlt werden sie trotzdem"
