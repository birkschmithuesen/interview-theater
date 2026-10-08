"""Klasse 3 der P7-Audit-Karte: Beschluesse aus dem Phase-7-Chat ueber eine
Figur (Rolle, Tarngeschichte, neuer Fakt) wandern bisher nur ins Script der
gerade besprochenen Szene, nicht in ``figur.beschreibung`` oder die Karten
der Folgeszenen.

Live-Fall (Gruppe 2, 08.10.2026): die Gruppe legte im P7-Chat fest, dass
Chicca eine Kommunikations-Diplomandin ist und Anna Schauspielstudentin am
Verdi -- der Erkenner haette das als "Deciso (Chicca): ..." notiert, aber
weder ``figur.beschreibung`` noch die Karten der noch offenen Folgeszenen
(3, 4, 5) erfuhren davon.

Fixtures synthetisch, am Wortlaut des echten Falls orientiert."""

import json

import pytest

from interview_theater import db, erkenner, phasen, repo, szenenkarte


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    phasen.setze(c, 1, 7, "test")
    return c


class Umgebung:
    bot_name = "gruppe1"


def _wende(conn, wert):
    return erkenner.wende_an(
        conn, Umgebung(), 1, [{"art": "festlegung_setzen", "wert": wert}]
    )


def _lege_szene_mit_karte_an(conn, nummer: int, figur_ids: list[int],
                             punkte: list[str] | None = None,
                             fertig: bool = False) -> int:
    szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
    repo.setze_szene_figuren(conn, 1, szene_id, figur_ids)
    karte = {
        "typ": "description", "modus": "none", "worum": "x", "ort": "x",
        "wer": "x", "punkte": punkte or [], "zitate": [], "fragen": [],
    }
    repo.setze_szenenkarte(conn, szene_id, json.dumps(karte, ensure_ascii=False))
    if fertig:
        repo.setze_szene_fertig(conn, szene_id, True)
    return szene_id


def _karte(conn, szene_id: int) -> dict:
    zeile = repo.hole_szene(conn, szene_id)
    return szenenkarte.karte_von(zeile)


def test_haengt_an_figur_beschreibung_an(conn):
    repo.setze_figur(conn, 1, "Chicca", "22 anni, studentessa.")

    _wende(conn, "figur/Chicca: diplomanda in scienze della comunicazione")

    figur = repo.hole_figur(conn, 1, "Chicca")
    assert figur["beschreibung"] == (
        "22 anni, studentessa.\ndiplomanda in scienze della comunicazione"
    )


def test_setzt_hakenpunkt_auf_offene_folgeszene_mit_der_figur(conn):
    repo.setze_figur(conn, 1, "Chicca", "")
    chicca_id = repo.hole_figur(conn, 1, "Chicca")["id"]
    szene_id = _lege_szene_mit_karte_an(conn, 3, [chicca_id])

    _wende(conn, "figur/Chicca: diplomanda in scienze della comunicazione")

    karte = _karte(conn, szene_id)
    assert karte["punkte"] == [
        "Deciso (Chicca): diplomanda in scienze della comunicazione",
    ]
    verlauf = repo.karte_verlauf(conn, 1, szene_id)
    assert verlauf[-1]["ausloeser"] == szenenkarte.AUSLOESER_AENDERUNG


def test_laesst_bereits_gespeicherte_szene_unberuehrt(conn):
    repo.setze_figur(conn, 1, "Chicca", "")
    chicca_id = repo.hole_figur(conn, 1, "Chicca")["id"]
    gespeichert_id = _lege_szene_mit_karte_an(conn, 1, [chicca_id], fertig=True)

    _wende(conn, "figur/Chicca: diplomanda in scienze della comunicazione")

    assert _karte(conn, gespeichert_id)["punkte"] == []


def test_laesst_szene_ohne_die_figur_unberuehrt(conn):
    repo.setze_figur(conn, 1, "Chicca", "")
    repo.setze_figur(conn, 1, "Anna", "")
    chicca_id = repo.hole_figur(conn, 1, "Chicca")["id"]
    anna_id = repo.hole_figur(conn, 1, "Anna")["id"]
    nur_anna_id = _lege_szene_mit_karte_an(conn, 4, [anna_id])
    _lege_szene_mit_karte_an(conn, 3, [chicca_id])

    _wende(conn, "figur/Chicca: diplomanda in scienze della comunicazione")

    assert _karte(conn, nur_anna_id)["punkte"] == []


def test_widerspruch_auf_derselben_karte_wird_ersetzt_nicht_verdoppelt(conn):
    """Der echte Fall: 'Safeword spricht Anna statt Chicca' ersetzt eine
    fruehere, jetzt falsche Festlegung auf derselben Karte -- kein
    Duplikat, derselbe Hakenpunkt in neuer Fassung."""
    repo.setze_figur(conn, 1, "Chicca", "")
    chicca_id = repo.hole_figur(conn, 1, "Chicca")["id"]
    alter_punkt = "Deciso (Chicca): dice la safeword «paperella»"
    szene_id = _lege_szene_mit_karte_an(conn, 4, [chicca_id], punkte=[alter_punkt])

    _wende(conn, "figur/Chicca: non dice piu la safeword, lo fa Anna")

    karte = _karte(conn, szene_id)
    assert karte["punkte"] == [
        "Deciso (Chicca): non dice piu la safeword, lo fa Anna",
    ]
    verlauf = repo.karte_verlauf(conn, 1, szene_id)
    assert verlauf[-1]["ausloeser"] == szenenkarte.AUSLOESER_AENDERUNG


def test_unbekannter_bezug_bleibt_folgenlos(conn):
    repo.setze_figur(conn, 1, "Chicca", "")
    chicca_id = repo.hole_figur(conn, 1, "Chicca")["id"]
    szene_id = _lege_szene_mit_karte_an(conn, 3, [chicca_id])

    _wende(conn, "figur/Francesca: non esiste nessuna tesi")

    assert _karte(conn, szene_id)["punkte"] == []
    assert repo.hole_figur(conn, 1, "Chicca")["beschreibung"] == ""


def test_nur_in_phase_7(conn):
    phasen.setze(conn, 1, 4, "test")
    repo.setze_figur(conn, 1, "Chicca", "")
    chicca_id = repo.hole_figur(conn, 1, "Chicca")["id"]
    szene_id = _lege_szene_mit_karte_an(conn, 3, [chicca_id])

    _wende(conn, "figur/Chicca: diplomanda in scienze della comunicazione")

    assert _karte(conn, szene_id)["punkte"] == []
    assert repo.hole_figur(conn, 1, "Chicca")["beschreibung"] == ""
