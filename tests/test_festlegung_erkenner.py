"""Die Erkenner-Art ``festlegung_setzen`` (06.09.2026).

Der Regelweg in die Auffangtabelle. Sie ist die Antwort auf den Befund aus
``docs/analyse-phase4-datenverlust-2026-09-06.md`` § 3: fuer jede relevante
Angabe ausserhalb des festen Slot-Rasters gab es kein Feld -- nur einen
``journal``-Eintrag, der aus dem Prompt faellt.

Fixtures synthetisch.
"""

import pytest

from interview_theater import db, erkenner, repo


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


class Umgebung:
    bot_name = "gruppe1"


def _wende(conn, wert):
    return erkenner.wende_an(
        conn, Umgebung(), 1, [{"art": "festlegung_setzen", "wert": wert}]
    )


def test_art_ist_bekannt():
    assert "festlegung_setzen" in erkenner.ARTEN
    assert "festlegung_setzen" in erkenner.SCHEMA["properties"]["aenderungen"][
        "items"]["properties"]["art"]["enum"]


def test_gilt_nicht_aus_einer_aufnahme():
    """Was eine interviewte Person erzaehlt, ist Material und nie eine
    Absicht der Gruppe (AGENTS.md, Korpusfaelle n12/n26)."""
    assert "festlegung_setzen" not in erkenner.ARTEN_IN_AUFNAHME


def test_bereich_bezug_und_text(conn):
    wirklich = _wende(conn, "figur/Kassandra: 19 Jahre, Schauspielerin")
    assert wirklich == [
        {
            "art": "festlegung_setzen",
            "wert": "[figur/Kassandra] 19 Jahre, Schauspielerin",
            "bereich": "figur",
            "bezug": "Kassandra",
            "text": "19 Jahre, Schauspielerin",
        }
    ]
    zeile = repo.festlegungen(conn, 1)[0]
    assert (zeile["bereich"], zeile["bezug"], zeile["quelle"]) == (
        "figur", "Kassandra", "erkenner"
    )


def test_ohne_bezug(conn):
    _wende(conn, "struktur: Nur eine Szene, die erste Folge einer Serie")
    zeile = repo.festlegungen(conn, 1)[0]
    assert zeile["bereich"] == "struktur"
    assert zeile["bezug"] is None


def test_ohne_bereich_landet_es_in_sonstiges(conn):
    """Ein Wert ohne Doppelpunkt ist kein Fehler, sondern der haeufigste
    Fall von "passt in kein Fach": lieber in ``sonstiges`` als verloren."""
    _wende(conn, "Die Szenentexte sollen kurz sein, hoechstens eine Seite")
    zeile = repo.festlegungen(conn, 1)[0]
    assert zeile["bereich"] == "sonstiges"
    assert zeile["text"] == "Die Szenentexte sollen kurz sein, hoechstens eine Seite"


def test_unbekannter_bereich_wird_sonstiges_und_bleibt_erhalten(conn):
    _wende(conn, "dramaturgie: Das Ende bleibt offen")
    zeile = repo.festlegungen(conn, 1)[0]
    assert zeile["bereich"] == "sonstiges"
    assert zeile["text"] == "Das Ende bleibt offen"


def test_leerer_wert_wirkt_nicht(conn):
    assert _wende(conn, "   ") == []
    assert repo.festlegungen(conn, 1) == []


def test_bereich_ohne_text_wirkt_nicht(conn):
    assert _wende(conn, "struktur:") == []
    assert repo.festlegungen(conn, 1) == []


def test_dieselbe_festlegung_zweimal_meldet_nur_einmal(conn):
    _wende(conn, "gruppe/die Coolen: definieren sich ueber Herkunft und Geld")
    zweite = _wende(conn, "gruppe/die Coolen: definieren sich ueber Herkunft und Geld")
    assert zweite == []
    assert len(repo.festlegungen(conn, 1)) == 1


def test_was_schon_im_arbeitsstand_steht_wird_verworfen(conn):
    """Risiko 2 der Analyse (\"Doppelte Wahrheit\"): steht das Setting
    sowohl in ``arbeitsstand.rahmen`` als auch als Festlegung, widersprechen
    sich beide irgendwann. Abgefangen wird das hier in der Auswertung --
    genauso wie ``_ist_geschichte`` den Fehler in umgekehrter Richtung
    abfaengt."""
    repo.setze_arbeitsstand(
        conn, 1, "rahmen", "Am Kanal im Sommer, nachmittags nach der Schule"
    )
    assert _wende(conn, "ort: Am Kanal im Sommer") == []
    assert repo.festlegungen(conn, 1) == []
    vorfaelle = [
        z["art"] for z in conn.execute("SELECT art FROM vorfall WHERE chat_id = 1")
    ]
    assert "festlegung_stand_schon_im_feld" in vorfaelle


def test_eine_echte_ergaenzung_zum_setting_bleibt(conn):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal im Sommer")
    assert _wende(conn, "ort: dazu der Skatepark an der Bruecke")
    assert len(repo.festlegungen(conn, 1)) == 1


def test_meldung_nennt_die_festlegung_mit_bezug():
    meldung = erkenner.baue_meldung(
        [
            {
                "art": "festlegung_setzen",
                "wert": "[figur/Kassandra] 19 Jahre",
                "bereich": "figur",
                "bezug": "Kassandra",
                "text": "19 Jahre",
            }
        ]
    )
    assert meldung == "Notiert:\nFestgehalten (Kassandra): 19 Jahre"


def test_meldung_ohne_bezug():
    meldung = erkenner.baue_meldung(
        [
            {
                "art": "festlegung_setzen",
                "wert": "[struktur] Nur eine Szene",
                "bereich": "struktur",
                "bezug": None,
                "text": "Nur eine Szene",
            }
        ]
    )
    assert meldung == "Notiert:\nFestgehalten: Nur eine Szene"


def test_entfernen_nimmt_eine_festlegung_zurueck(conn):
    """Weiches Loeschen ueber dieselbe art wie alles andere (N3) -- ohne
    diesen Weg erbt die neue Tabelle den alten Fehler: ein Eintrag ueber
    einen laengst zurueckgenommenen zweiten Spielort, den nie jemand
    abraeumt."""
    _wende(conn, "ort: Zweiter Ort ist die Schule")
    wirklich = erkenner.wende_an(
        conn, Umgebung(), 1,
        [{"art": "entfernen", "wert": "Festlegung: Schule"}],
    )
    assert wirklich == [
        {"art": "entfernen", "wert": "Festlegung: Zweiter Ort ist die Schule"}
    ]
    assert repo.festlegungen(conn, 1) == []


def test_entfernen_ohne_treffer_wirkt_nicht(conn):
    assert erkenner.wende_an(
        conn, Umgebung(), 1,
        [{"art": "entfernen", "wert": "Festlegung: Bahnhof"}],
    ) == []
