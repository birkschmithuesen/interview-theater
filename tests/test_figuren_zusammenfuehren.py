"""B3 aus der Phase-4-Analyse: Platzhalterfiguren beim Nachbenennen weich
loeschen -- und den Sprachstil retten.

Der gemessene Fall (§ 2.4): ``figur`` enthielt 16 Zeilen statt 10, keine
weich geloescht, darunter drei Paare mit **wortgleicher Beschreibung** --
je ein Platzhalter ("Nebenfigur Outsider 1") und die spaeter nachbenannte
Figur. Der Folgeschaden ist der eigentliche: die im Chat muehsam
erarbeiteten Sprachstile hingen an den **Platzhaltern**, die benannten
Figuren hatten ``sprachstil`` NULL. Und ``szene_figur`` verwies gemischt auf
beide Seiten -- eine Szene mit sechs Figuren fuehrte neun Zuordnungen.

Deshalb wird zusammengefuehrt und nicht geloescht: **der Stil wandert auf
den Namen**, der Platzhalter bekommt ``entfernt_am``.

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


BESCHREIBUNG = "laesst sich nichts gefallen, redet zurueck"


def _platzhalter(conn, name=BESCHREIBUNG and "Nebenfigur Outsider 1"):
    repo.setze_figur(conn, 1, name, BESCHREIBUNG)
    zeile = repo.hole_figur(conn, 1, name)
    repo.setze_figur_sprachstil(conn, zeile["id"], "Knapp: 'Lass mal.'")
    return repo.hole_figur(conn, 1, name)


# --- Der Platzhalter-Begriff ----------------------------------------------


@pytest.mark.parametrize(
    "name", ["Nebenfigur Outsider 1", "Nebenfigur Cool 3", "Figur 2",
             "Hauptfigur A", "Platzhalter 1"],
)
def test_platzhaltername_wird_erkannt(name):
    assert repo.ist_platzhaltername(name)


@pytest.mark.parametrize("name", ["Sara", "Yasmin", "Frau Reinhardt", "Emre"])
def test_ein_echter_name_ist_kein_platzhalter(name):
    assert not repo.ist_platzhaltername(name)


# --- Das Zusammenfuehren selbst -------------------------------------------


def test_der_sprachstil_wandert_auf_den_namen(conn):
    alt = _platzhalter(conn)
    repo.setze_figur(conn, 1, "Sara", BESCHREIBUNG)
    neu = repo.hole_figur(conn, 1, "Sara")
    repo.fuehre_figur_zusammen(conn, 1, alt["id"], neu["id"])
    assert repo.hole_figur(conn, 1, "Sara")["sprachstil"] == "Knapp: 'Lass mal.'"


def test_der_platzhalter_wird_weich_geloescht(conn):
    alt = _platzhalter(conn)
    repo.setze_figur(conn, 1, "Sara", BESCHREIBUNG)
    repo.fuehre_figur_zusammen(conn, 1, alt["id"], repo.hole_figur(conn, 1, "Sara")["id"])
    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Sara"]
    # Weich: die Zeile steht noch da, mit Stempel.
    assert conn.execute(
        "SELECT entfernt_am FROM figur WHERE id = ?", (alt["id"],)
    ).fetchone()[0]


def test_ein_gesetztes_feld_des_ziels_wird_nicht_ueberschrieben(conn):
    alt = _platzhalter(conn)
    repo.setze_figur(conn, 1, "Sara", BESCHREIBUNG)
    neu = repo.hole_figur(conn, 1, "Sara")
    repo.setze_figur_sprachstil(conn, neu["id"], "Eigener Stil")
    repo.fuehre_figur_zusammen(conn, 1, alt["id"], neu["id"])
    assert repo.hole_figur(conn, 1, "Sara")["sprachstil"] == "Eigener Stil"


def test_szenenzuordnungen_wandern_mit(conn):
    """``szene_figur`` verwies live gemischt auf beide Seiten -- eine Szene
    mit sechs Figuren fuehrte neun Zuordnungen."""
    alt = _platzhalter(conn)
    repo.setze_figur(conn, 1, "Sara", BESCHREIBUNG)
    neu = repo.hole_figur(conn, 1, "Sara")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szene_figuren(conn, 1, szene_id, [alt["id"]])
    repo.fuehre_figur_zusammen(conn, 1, alt["id"], neu["id"])
    assert [f["id"] for f in repo.szene_figuren(conn, szene_id)] == [neu["id"]]


def test_doppelte_zuordnung_wird_nicht_zur_dublette(conn):
    alt = _platzhalter(conn)
    repo.setze_figur(conn, 1, "Sara", BESCHREIBUNG)
    neu = repo.hole_figur(conn, 1, "Sara")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szene_figuren(conn, 1, szene_id, [alt["id"], neu["id"]])
    repo.fuehre_figur_zusammen(conn, 1, alt["id"], neu["id"])
    assert [f["id"] for f in repo.szene_figuren(conn, szene_id)] == [neu["id"]]


def test_fremde_gruppe_wird_nicht_angefasst(conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere")
    alt = _platzhalter(conn)
    repo.setze_figur(conn, 2, "Sara", BESCHREIBUNG)
    fremd = repo.hole_figur(conn, 2, "Sara")
    assert repo.fuehre_figur_zusammen(conn, 1, alt["id"], fremd["id"]) is None
    assert len(repo.figuren(conn, 1)) == 1


# --- Der Erkennerweg -------------------------------------------------------


def test_nachbenennen_fuehrt_automatisch_zusammen(conn):
    _platzhalter(conn)
    erkenner.wende_an(
        conn, Umgebung(), 1,
        [{"art": "figur_setzen", "wert": f"Sara: {BESCHREIBUNG}"}],
    )
    figuren = repo.figuren(conn, 1)
    assert [f["name"] for f in figuren] == ["Sara"]
    assert figuren[0]["sprachstil"] == "Knapp: 'Lass mal.'"


def test_journal_haelt_das_zusammenfuehren_fest(conn):
    _platzhalter(conn)
    erkenner.wende_an(
        conn, Umgebung(), 1,
        [{"art": "figur_setzen", "wert": f"Sara: {BESCHREIBUNG}"}],
    )
    texte = [z["text"] for z in repo.journal(conn, 1)]
    assert any("Nebenfigur Outsider 1" in t and "Sara" in t for t in texte)


def test_zwei_echte_figuren_werden_nicht_zusammengefuehrt(conn):
    """Nur ein **Platzhalter** wird eingeschmolzen. Zwei benannte Figuren mit
    zufaellig gleicher Beschreibung sind zwei Figuren -- sie zu verschmelzen
    naehme der Gruppe eine, und das waere derselbe stille Verlust in der
    anderen Richtung."""
    repo.setze_figur(conn, 1, "Yasmin", BESCHREIBUNG)
    erkenner.wende_an(
        conn, Umgebung(), 1,
        [{"art": "figur_setzen", "wert": f"Sara: {BESCHREIBUNG}"}],
    )
    assert {f["name"] for f in repo.figuren(conn, 1)} == {"Yasmin", "Sara"}


def test_andere_beschreibung_fuehrt_nicht_zusammen(conn):
    _platzhalter(conn)
    erkenner.wende_an(
        conn, Umgebung(), 1,
        [{"art": "figur_setzen", "wert": "Sara: programmiert, sagt wenig"}],
    )
    assert len(repo.figuren(conn, 1)) == 2


def test_platzhalter_ohne_beschreibung_bleibt_stehen(conn):
    """Ohne Beschreibung gibt es kein Signal, welcher Platzhalter gemeint
    ist -- geraten wird nicht."""
    repo.setze_figur(conn, 1, "Nebenfigur Cool 1", "")
    erkenner.wende_an(
        conn, Umgebung(), 1,
        [{"art": "figur_setzen", "wert": "Obed: mag Musik"}],
    )
    assert len(repo.figuren(conn, 1)) == 2


# --- Das Reparaturskript ---------------------------------------------------


def test_skript_findet_die_paare_und_schreibt_trocken_nichts(conn):
    from scripts import figuren_aufraeumen

    _platzhalter(conn)
    repo.setze_figur(conn, 1, "Sara", BESCHREIBUNG)
    paare = figuren_aufraeumen.finde_paare(conn, 1)
    assert len(paare) == 1
    assert paare[0][0]["name"] == "Nebenfigur Outsider 1"
    assert paare[0][1]["name"] == "Sara"

    assert figuren_aufraeumen.raeume_auf(conn, 1, trocken=True) == 1
    assert len(repo.figuren(conn, 1)) == 2


def test_skript_fuehrt_zusammen_und_ist_idempotent(conn):
    from scripts import figuren_aufraeumen

    _platzhalter(conn)
    repo.setze_figur(conn, 1, "Sara", BESCHREIBUNG)
    assert figuren_aufraeumen.raeume_auf(conn, 1, trocken=False) == 1
    figuren = repo.figuren(conn, 1)
    assert [f["name"] for f in figuren] == ["Sara"]
    assert figuren[0]["sprachstil"] == "Knapp: 'Lass mal.'"
    assert figuren_aufraeumen.raeume_auf(conn, 1, trocken=False) == 0
