"""Schicht 4a: das Erfolgsmass zwischen zwei Runden.

Geprueft wird vor allem die Entscheidung, die dieses Modul traegt: verglichen
werden **Scores je Frage und Szene**, nicht Befunde. Dazu die drei Ausgaenge
(gestiegen, gefallen, gleich), die Sichtbarkeit des Schadens, und dass eine
Frage ohne Score in einer der beiden Runden gar nicht erst verglichen wird.
"""

from interview_theater import db, repo
from interview_theater.dramaturgie import bilanz


def _b(pruefung, szene, score):
    return {"pruefung": pruefung, "szene": szene, "score": score}


# --- Die drei Ausgaenge ---------------------------------------------------


def test_gestiegener_score_ist_besser():
    ergebnis = bilanz.baue([_b("b1", 1, 0)], [_b("b1", 1, 2)], von=1, nach=2)

    assert [v.richtung for v in ergebnis.vergleiche] == [bilanz.BESSER]
    assert not ergebnis.geschadet


def test_gefallener_score_heisst_die_ueberarbeitung_hat_geschadet():
    ergebnis = bilanz.baue([_b("a9", 3, 2)], [_b("a9", 3, 0)], von=1, nach=2)

    assert [v.richtung for v in ergebnis.vergleiche] == [bilanz.SCHLECHTER]
    assert ergebnis.geschadet


def test_gleicher_score_ist_keine_wirkung():
    ergebnis = bilanz.baue([_b("c1", 2, 1)], [_b("c1", 2, 1)], von=1, nach=2)

    assert [v.richtung for v in ergebnis.vergleiche] == [bilanz.GLEICH]
    assert not ergebnis.geschadet


def test_ein_schaden_wird_nicht_gegen_drei_erfolge_verrechnet():
    """"Drei besser, einer schlechter" ist kein Erfolg, sondern beides -- und
    der Schaden steht in einer Szene, die die Gruppe schon gut fand."""
    vorher = [_b("b1", 1, 0), _b("b1", 2, 0), _b("b1", 3, 0), _b("a9", 1, 2)]
    nachher = [_b("b1", 1, 2), _b("b1", 2, 2), _b("b1", 3, 2), _b("a9", 1, 0)]

    ergebnis = bilanz.baue(vorher, nachher, von=1, nach=2)

    assert len(ergebnis.besser) == 3
    assert len(ergebnis.schlechter) == 1
    assert ergebnis.geschadet


# --- Was NICHT verglichen wird --------------------------------------------


def test_die_zahl_der_befunde_ist_kein_mass():
    """Der gefaehrliche Fall: der Text wird schlechter, der Judge findet fuer
    seinen Befund kein Belegzitat mehr, es gibt also weniger Befunde -- und
    trotzdem sagt die Bilanz "schlechter", weil sie Scores vergleicht."""
    ergebnis = bilanz.baue([_b("b1", 1, 2)], [_b("b1", 1, 1)], von=1, nach=2)

    assert ergebnis.geschadet


def test_eine_frage_ohne_score_in_einer_runde_wird_nicht_verglichen():
    """Ein fehlender Score heisst "nicht gemessen", nicht "ganz schlecht" --
    sonst wuerde ein nicht bestaetigtes Belegzitat als Verschlechterung
    gelesen."""
    ergebnis = bilanz.baue(
        [_b("b1", 1, 2), _b("a2", None, 2)], [_b("b1", 1, 2)], von=1, nach=2
    )

    assert [(v.pruefung, v.szene) for v in ergebnis.vergleiche] == [("b1", 1)]


def test_die_stueckfragen_haben_keine_szene():
    ergebnis = bilanz.baue([_b("a2", None, 1)], [_b("a2", None, 2)], von=1, nach=2)

    (vergleich,) = ergebnis.vergleiche
    assert vergleich.szene is None
    assert "Szene" not in vergleich.adresse


def test_score_none_faellt_heraus():
    ergebnis = bilanz.baue([_b("b1", 1, None)], [_b("b1", 1, 0)], von=1, nach=2)

    assert ergebnis.vergleiche == ()


# --- Lesbarkeit -----------------------------------------------------------


def test_die_bilanz_nennt_frage_szene_vorher_und_nachher():
    ergebnis = bilanz.baue(
        [_b("b1", 1, 0), _b("a9", 2, 2)], [_b("b1", 1, 2), _b("a9", 2, 0)],
        von=1, nach=2,
    )

    text = ergebnis.als_text()
    assert "Bilanz Runde 1 -> 2:" in text
    assert "A9 Fokus, Szene 2: 2 -> 0 (schlechter)" in text
    assert "B1 Wendung, Szene 1: 0 -> 2 (besser)" in text
    assert "1 besser, 0 gleich, 1 schlechter." in text


def test_der_schaden_steht_zuerst():
    ergebnis = bilanz.baue(
        [_b("b1", 1, 0), _b("c1", 1, 2)], [_b("b1", 1, 2), _b("c1", 1, 0)],
        von=1, nach=2,
    )

    assert ergebnis.vergleiche[0].richtung == bilanz.SCHLECHTER


def test_ohne_gemeinsame_frage_sagt_die_bilanz_das():
    ergebnis = bilanz.baue([], [_b("b1", 1, 2)], von=1, nach=2)

    assert "nichts vergleichbar" in ergebnis.als_text()


def test_die_bezeichnung_kommt_aus_dem_prompt_dateinamen():
    assert bilanz.bezeichnung("a10") == "Materialtreue"
    assert bilanz.bezeichnung("c1") == "Stimme"
    # Eine Pruefung ohne Prompt (Mechanik) bleibt ihr Schluessel.
    assert bilanz.bezeichnung("sprechanteil") == "SPRECHANTEIL"


# --- Aus der Datenbank ----------------------------------------------------


def test_die_bilanz_wird_aus_den_gespeicherten_scores_gerechnet(conn):
    repo.lege_dramaturgie_bewertungen_an(
        conn, 1, [_b("b1", 1, 0), _b("a2", None, 2)], runde=1
    )
    repo.lege_dramaturgie_bewertungen_an(
        conn, 1, [_b("b1", 1, 2), _b("a2", None, 1)], runde=2
    )

    ergebnis = bilanz.aus_datenbank(conn, 1, von=1, nach=2)

    richtungen = {v.pruefung: v.richtung for v in ergebnis.vergleiche}
    assert richtungen == {"b1": bilanz.BESSER, "a2": bilanz.SCHLECHTER}
    assert ergebnis.geschadet


def test_die_bilanz_bleibt_bei_der_gruppe(conn):
    """Dieselbe Grenze wie ueberall: eine Messung gehoert zu einer chat_id."""
    repo.lege_dramaturgie_bewertungen_an(conn, 1, [_b("b1", 1, 0)], runde=1)
    repo.lege_dramaturgie_bewertungen_an(conn, 1, [_b("b1", 1, 2)], runde=2)

    assert bilanz.aus_datenbank(conn, 2, von=1, nach=2).vergleiche == ()
    assert "dramaturgie_bewertung" in db.TABELLEN_MIT_CHAT_ID
