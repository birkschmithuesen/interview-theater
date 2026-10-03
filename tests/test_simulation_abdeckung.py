"""Der Abdeckungszensus -- ohne Netz, ohne Modell.

Er erzeugt die Tabelle, die im Ergebnisbericht steht. Getestet wird deshalb
nicht nur, dass er laeuft, sondern dass er die Befunde **aus dem Code** zieht:
eine Tabelle, die man abschreiben koennte, braeuchte diesen Test nicht.
"""

import tempfile
from pathlib import Path

import pytest

from interview_theater import db, erkenner, phasen, repo
from interview_theater.knoepfe import texte
from scripts import simulation_abdeckung as abdeckung
from simulation import skript


@pytest.fixture
def leer():
    """Ein frisches Schema -- ``felder_fuer_phase`` liest ``PRAGMA
    table_info(arbeitsstand)``, also braucht der Zensus eine Verbindung."""
    ordner = tempfile.mkdtemp(prefix="abdeckung-")
    conn = db.verbinde(str(Path(ordner) / "t.db"))
    db.initialisiere(conn)
    return conn


def test_alle_drei_skripte_sind_erfasst():
    assert set(abdeckung.SKRIPTE) == {"schritte", "tag2", "birk", "padua"}
    assert abdeckung.SKRIPTE["tag2"] is skript.SCHRITTE_TAG2
    assert abdeckung.SKRIPTE["padua"] is skript.SCHRITTE_PADUA


def test_padua_faehrt_die_phasen_5_bis_7_mit_benannten_pruefungen(leer):
    """Die Phasen 5, 6 und 7 haben im Padua-Skript eigene Schritte, und jede
    Pruefung traegt einen sprechenden Namen -- der Zensus liest
    ``fertig.__name__``."""
    zeilen = {z["nummer"]: z for z in abdeckung.phasentabelle(leer, skript.SCHRITTE_PADUA)}
    assert "entwurf" in zeilen[5]["schritte"]
    assert {"gesamt6", "szenen6"} <= set(zeilen[6]["schritte"])
    assert {"formen7", "sprechweisen7", "buehne7", "pruefung7"} <= set(zeilen[7]["schritte"])
    assert "_fertig_pruefung7" in zeilen[7]["pruefungen"]
    assert all(z["stimmt"] for z in abdeckung.titelphasen(skript.SCHRITTE_PADUA))
    text = abdeckung.als_markdown(leer, Path(abdeckung.__file__).resolve().parent.parent)
    assert "### `padua`" in text
    assert "`SCHRITTE_PADUA`" in text


def test_phase_je_schritt_folgt_den_phasenschritten():
    """In ``SCHRITTE_TAG2`` setzt jeder ``art='phase'``-Schritt die laufende
    Phase; die Schritte danach gehoeren zu ihr."""
    zuordnung = abdeckung.phase_je_schritt(skript.SCHRITTE_TAG2)
    assert zuordnung["begriffe"] == phasen.ERSTE
    assert zuordnung["fragen"] == 2
    assert zuordnung["interviews"] == 3
    assert zuordnung["setting"] == 4
    assert zuordnung["geschichte"] == 4
    assert zuordnung["schaerfung"] == 5
    assert zuordnung["szene1"] == 6


def test_ein_skript_ohne_phasenschritte_ordnet_nichts_zu():
    """Der eigentliche Befund an ``SCHRITTE``: es gibt dort keinen
    ``art='phase'``-Schritt, also bleibt jeder Schritt nach dem ersten
    unzugeordnet -- ausser dem ersten, der per Definition in der ersten Phase
    liegt."""
    zuordnung = abdeckung.phase_je_schritt(skript.SCHRITTE)
    assert set(zuordnung.values()) == {phasen.ERSTE}


def test_titelphasen_findet_einen_widerspruch():
    """Der Befund vom 30.09.2026 war ``Schritt("phase_mitte", "Phase 5", ...)``
    bei ``skript.PHASE_MITTE == 4`` -- der Titel nannte eine andere Phase als
    die Pruefung. Seit Aufgabe 7 ist der Titel nachgezogen; der Mechanismus
    wird deshalb an einem gebauten Schritt geprueft."""
    falsch = skript.Schritt("x", "Phase 5: irgendwas", "ziel", lambda *a: True)
    zeile = abdeckung.titelphasen([falsch])[0]
    assert zeile["titel_phase"] == 5
    assert zeile["zugeordnet"] == phasen.ERSTE
    assert zeile["stimmt"] is False


def test_der_titel_von_phase_mitte_nennt_heute_phase_mitte():
    zeilen = {z["schluessel"]: z for z in abdeckung.titelphasen(skript.SCHRITTE)}
    assert zeilen["phase_mitte"]["titel_phase"] == skript.PHASE_MITTE


def test_phasentabelle_nennt_pruefung_und_pflichtfeld(leer):
    zeilen = {z["nummer"]: z for z in abdeckung.phasentabelle(leer, skript.SCHRITTE_TAG2)}
    assert set(zeilen) == {n for n, _k, _b in phasen.PHASEN}
    assert zeilen[4]["kurzname"] == phasen.kurzname(4)
    assert zeilen[4]["pflichtfeld"] == skript.pflichtfeld_fuer_phase(leer, 4)
    assert zeilen[4]["gefahren"] is True
    # Die Pruefung kommt aus dem Funktionsnamen, nicht aus einer Liste.
    assert "_fertig_setting" in zeilen[4]["pruefungen"]


def test_phasentabelle_meldet_ungefahrene_phasen(leer):
    zeilen = {z["nummer"]: z for z in abdeckung.phasentabelle(leer, skript.SCHRITTE)}
    assert zeilen[phasen.LETZTE]["gefahren"] is False
    assert zeilen[phasen.LETZTE]["schritte"] == []


def test_inventar_zaehlt_die_beiden_arten_listen():
    inv = abdeckung.inventar()
    assert inv["erkenner_arten"] == sorted(erkenner.ARTEN)
    assert len(inv["knopfarten"]) == len([n for n in dir(texte) if n.startswith("ART_")])


def test_praemissenpruefung_kennt_drei_zustaende(tmp_path):
    """gefunden+falsch, gefunden+richtig, bereinigt -- alle drei muessen
    unterscheidbar sein, sonst liest der Bericht eine bereinigte Datei wie
    eine korrekte Behauptung."""
    (tmp_path / "a.md").write_text("Zeile eins\nneun Schritte hier\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("nichts davon\n", encoding="utf-8")
    behauptungen = (
        ("a.md", "neun Schritte", lambda: False),
        ("a.md", "Zeile eins", lambda: True),
        ("b.md", "neun Schritte", lambda: False),
    )
    ergebnis = abdeckung.praemissenpruefung(tmp_path, behauptungen)
    assert [z["status"] for z in ergebnis] == [
        "gefunden_falsch", "gefunden_richtig", "bereinigt",
    ]
    assert ergebnis[0]["zeilen"] == [2]


def test_die_eingebauten_behauptungen_treffen_heute_zu(tmp_path):
    """Kein Wunschzettel: jede Behauptung in ``BEHAUPTUNGEN`` muss auf eine
    Datei zeigen, die es gibt, und ihre Pruefung muss aufrufbar sein."""
    wurzel = Path(abdeckung.__file__).resolve().parent.parent
    for datei, text, pruefung in abdeckung.BEHAUPTUNGEN:
        assert (wurzel / datei).exists(), datei
        assert isinstance(pruefung(), bool)
        assert text


def test_knopfarten_aus_db_trennt_angeboten_von_gedrueckt(leer):
    repo.sichere_gruppe(leer, 1, "gruppe1", "Testgruppe")
    eins = repo.lege_knopf_an(leer, 1, texte.ART_PHASE, "2")
    repo.lege_knopf_an(leer, 1, texte.ART_PHASE, "3")
    repo.beanspruche_knopf(leer, eins)
    zeilen = {z["art"]: z for z in abdeckung.knopfarten_aus_db(leer)}
    assert zeilen[texte.ART_PHASE]["angeboten"] == 2
    assert zeilen[texte.ART_PHASE]["gedrueckt"] == 1


def test_laeufe_aus_db_zaehlt_je_art(leer):
    repo.sichere_gruppe(leer, 1, "gruppe1", "Testgruppe")
    repo.merke_aufruf(leer, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    repo.merke_aufruf(leer, 1, "szenenfolge", "A", 0, 10, 10, "stop", 1, 1)
    repo.merke_aufruf(leer, 1, "schaerfung", "A", 0, 10, 10, "stop", 1, 1)
    assert abdeckung.laeufe_aus_db(leer) == {"schaerfung": 1, "szenenfolge": 2}


def test_als_markdown_traegt_die_drei_tabellen(leer):
    text = abdeckung.als_markdown(leer, Path(abdeckung.__file__).resolve().parent.parent)
    assert "## Phasen je Skript" in text
    assert "## Praemissenpruefung" in text
    assert "## Inventar" in text
    assert phasen.kurzname(4) in text
