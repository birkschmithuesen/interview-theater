"""Die reine Diff-Logik der Ruecknahme (Karte U, 01.10.2026).

Kein SQL, keine Datenbank, kein Netz: zwei Dicts rein, Schritte raus. Genau
das ist der Punkt der Aufteilung -- die Entscheidung, WAS zurueckgenommen
wird, ist hier pruefbar, ohne eine Datenbank zu bauen.
"""

import ast
import inspect
import pathlib

from interview_theater import ruecknahme


def test_verfolgt_traegt_die_inhaltstabellen_und_nicht_die_gruppe():
    assert set(ruecknahme.VERFOLGT) == {
        "arbeitsstand", "figur", "szene", "szene_figur", "festlegung",
    }
    assert "gruppe" not in ruecknahme.VERFOLGT, "USA-Einwilligung: eigene Knoepfe"
    assert "journal" not in ruecknahme.VERFOLGT, "nur-anhaengend (AGENTS.md)"


def test_die_phasenbuchhaltung_und_zeitstempel_stehen_aussen_vor():
    aussen = ruecknahme.AUSSEN["arbeitsstand"]
    assert {"phase", "phase_angeboten", "phase_gesetzt_am", "geaendert_am"} <= aussen
    assert "kernthema" not in aussen


def test_spaeter_geschriebene_felder_stehen_aussen_vor():
    """Was erst ein anderer, spaeterer Lauf schreibt, wird nie verglichen --
    sonst scheiterte ein Kernthema-Undo an einem Sprachprofil, das ein Thread
    danach geschrieben hat."""
    assert {"sprachprofil", "zitate", "geprueft_am"} <= ruecknahme.AUSSEN["figur"]
    assert {"volltext", "prosa", "form", "stil"} <= ruecknahme.AUSSEN["szene"]


def test_plan_nimmt_material_nur_mit_transkript_korrektur():
    ohne = ruecknahme.plan(["kernthema_setzen", "figur_setzen"])
    assert set(ohne) == set(ruecknahme.VERFOLGT)

    mit = ruecknahme.plan(["kernthema_setzen", "transkript_korrigieren"])
    assert set(mit) == set(ruecknahme.VERFOLGT) | set(ruecknahme.MATERIAL)
    assert mit["aufnahme"] == (("id",), ("transkript",))


def test_plan_liest_die_spalten_aus_dem_schema_und_nicht_aus_einer_liste():
    """Eine neue Spalte in db.SCHEMA wird automatisch verfolgt."""
    from interview_theater import db

    soll = {
        name for name, _ in db._tabellenspalten_aus_schema()["figur"]
    } - ruecknahme.AUSSEN["figur"] - {"id"}
    assert set(ruecknahme.plan(["figur_setzen"])["figur"][1]) == soll


def test_schluessel_von_szene_figur_ist_zusammengesetzt():
    assert ruecknahme.SCHLUESSEL["szene_figur"] == ("szene_id", "figur_id")
    assert ruecknahme.SCHLUESSEL["arbeitsstand"] == ("chat_id",)


def test_geaenderte_spalte_wird_ein_schritt():
    vorher = {"arbeitsstand": {'{"chat_id": 1}': {"kernthema": None, "rahmen": "Bahnhof"}}}
    nachher = {"arbeitsstand": {'{"chat_id": 1}': {"kernthema": "Ankommen", "rahmen": "Bahnhof"}}}

    schritte = ruecknahme.schritte(vorher, nachher)

    assert len(schritte) == 1
    s = schritte[0]
    assert s["tabelle"] == "arbeitsstand"
    assert s["art"] == "geaendert"
    # Nur die geaenderte Spalte, nicht die ganze Zeile: sonst schriebe die
    # Ruecknahme ueber etwas, das dieser Lauf nie angefasst hat.
    assert s["vorher"] == {"kernthema": None}
    assert s["nachher"] == {"kernthema": "Ankommen"}


def test_unveraenderte_zeile_wird_kein_schritt():
    gleich = {"figur": {'{"id": 3}': {"name": "Mira", "beschreibung": "laut"}}}
    assert ruecknahme.schritte(gleich, dict(gleich)) == []


def test_neue_zeile_wird_angelegt_schritt():
    schritte = ruecknahme.schritte(
        {"figur": {}},
        {"figur": {'{"id": 3}': {"name": "Mira", "beschreibung": "laut"}}},
    )
    assert [(s["art"], s["vorher"]) for s in schritte] == [("angelegt", None)]
    assert schritte[0]["schluessel"] == {"id": 3}


def test_verschwundene_zeile_wird_geloescht_schritt():
    schritte = ruecknahme.schritte(
        {"szene_figur": {'{"figur_id": 3, "szene_id": 7}':
                         {"chat_id": 1, "szene_id": 7, "figur_id": 3}}},
        {"szene_figur": {}},
    )
    assert [(s["art"], s["nachher"]) for s in schritte] == [("geloescht", None)]
    assert schritte[0]["vorher"]["figur_id"] == 3


def test_schritte_sind_stabil_sortiert():
    """Zwei Laeufe ueber denselben Diff liefern dieselbe Reihenfolge -- sonst
    waere der Rundreise-Test in Aufgabe 9 vom dict-Zufall abhaengig."""
    vorher = {"figur": {'{"id": 2}': {"name": "A"}, '{"id": 1}': {"name": "B"}}}
    nachher = {"figur": {'{"id": 2}': {"name": "A2"}, '{"id": 1}': {"name": "B2"}}}
    einmal = [(s["tabelle"], s["schluessel"]) for s in ruecknahme.schritte(vorher, nachher)]
    assert einmal == sorted(einmal, key=lambda p: (p[0], sorted(p[1].items())))


def test_gleich_ueberlebt_den_typwechsel_zwischen_zahl_und_text():
    """``figuren_anzahl`` kommt als int aus erkenner.figurenzahl_aus und als
    str aus einem Knopf -- ein Typwechsel darf keine Aenderung sein."""
    assert ruecknahme.gleich(4, 4)
    assert ruecknahme.gleich(None, None)
    assert not ruecknahme.gleich(None, "")
    assert not ruecknahme.gleich("Ankommen", "ankommen")


def test_verweise_kommen_aus_dem_schema():
    """Die Tabellen, die auf eine figur oder szene zeigen -- hergeleitet, nicht
    aufgezaehlt: eine spaeter dazukommende referenzierende Tabelle faellt hier
    auf, bevor sie Waisen erzeugt.

    Pruefkommando: grep -n "figur_id\\|szene_id" interview_theater/db.py
    """
    assert set(ruecknahme.verweise()) == {
        ("szene_figur", "szene_id", "szene"),
        ("szene_figur", "figur_id", "figur"),
        ("schaerfung", "szene_id", "szene"),
        ("schaerfung", "figur_id", "figur"),
        ("szenenfassung", "szene_id", "szene"),
    }


def test_ruecknahme_enthaelt_kein_sql():
    """Die Schichtzusage: alles SQL steht in repo.py. Hier stehen reine
    Funktionen -- ``db`` wird importiert, aber nur fuer die Spaltenliste
    (db._tabellenspalten_aus_schema), nicht fuer eine Abfrage."""
    quelle = pathlib.Path(inspect.getfile(ruecknahme)).read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    aufrufe = {
        ast.unparse(k.func)
        for k in ast.walk(baum)
        if isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
    }
    assert not {a for a in aufrufe if a.endswith((".execute", ".executemany",
                                                  ".executescript", ".commit"))}
    assert "conn" not in {
        a.arg for k in ast.walk(baum)
        if isinstance(k, ast.arguments) for a in k.args
    }


def test_ruecknahme_traegt_keinen_nutzertext():
    """Die Wortlaute stehen in knoepfe/texte.py (K1 aus Karte A1) -- dieses
    Modul ist Logik und kommt ohne ``sprache.Texte`` aus."""
    quelle = pathlib.Path(inspect.getfile(ruecknahme)).read_text(encoding="utf-8")
    assert "sprache.Texte" not in quelle
    # ZEILEN_OHNE_UNDO ist keine Wortlaut-Konstante, sondern eine Liste von
    # Erkenner-arten (plan-kopf.md, Entscheidung E.1) -- der Name traegt
    # zufaellig dasselbe Praefix wie die verbotenen Text-Konstanten.
    assert not [
        n for n in dir(ruecknahme)
        if n.lstrip("_").startswith(("TEXT", "MELDUNG", "ZEILE", "ANTWORT"))
        and n != "ZEILEN_OHNE_UNDO"
    ]
