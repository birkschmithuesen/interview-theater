"""Die Szenen-Uebersicht auf der Gruppenseite (06.09.2026).

Birk am 06.09.: *"Was mir in der Webansicht gefehlt hat, ist eine Uebersicht
ueber die Szenen -- nachdem Szene 1,2,3 schon definiert sind, sollten die da
auch dargestellt werden."*

Gemessen wird beides: die Lesefunktion (``web_daten.szenenuebersicht``, ohne
HTTP, read-only) und die Darstellung (``web._szenenuebersicht_html``). Die
Texte selbst gehoeren NICHT in die Uebersicht -- nur ihre Zeichenzahl.

Alle Daten sind erfunden.
"""

import pytest

from interview_theater import db, repo, web, web_daten


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Die Ankommenden")
    return c


def _szene(conn, nummer, **felder):
    szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
    for feld, wert in felder.items():
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    return szene_id


# --- web_daten -------------------------------------------------------------


def test_uebersicht_ist_sortiert_und_traegt_die_planung(conn):
    _szene(conn, 2, titel="In der Kueche", kurzbeschreibung="Es kippt",
           form="dialog", stil="litanei")
    _szene(conn, 1, titel="Am Steg", was_passiert="Sie warten",
           form_vorschlag="chor")

    zeilen = web_daten.szenenuebersicht(conn, 1)

    assert [z["nummer"] for z in zeilen] == [1, 2]
    assert zeilen[0]["titel"] == "Am Steg"
    assert zeilen[0]["kurz"] == "Sie warten"
    # Ohne bestaetigte Form steht der Vorschlag da.
    assert zeilen[0]["form"] == ""
    assert zeilen[0]["form_vorschlag"] == "chor"
    assert zeilen[1]["form"] == "dialog"
    assert zeilen[1]["stil"] == "litanei"


def test_bestaetigte_form_verdraengt_den_vorschlag(conn):
    _szene(conn, 1, titel="Am Steg", form="chor", form_vorschlag="dialog")

    zeile = web_daten.szenenuebersicht(conn, 1)[0]

    assert zeile["form"] == "chor"
    assert zeile["form_vorschlag"] == ""


def test_uebersicht_zaehlt_zeichen_statt_den_text_zu_dumpen(conn):
    szene_id = _szene(conn, 1, titel="Am Steg")
    repo.aktualisiere_szene(
        conn, szene_id, "Am Steg", None, "MIRA: Da bist du.", None, "Sie stand da.",
    )

    zeile = web_daten.szenenuebersicht(conn, 1)[0]

    assert zeile["prosa_zeichen"] == len("Sie stand da.")
    assert zeile["volltext_zeichen"] == len("MIRA: Da bist du.")
    assert "prosa" not in zeile
    assert "volltext" not in zeile


def test_ohne_szenen_ist_die_uebersicht_leer(conn):
    assert web_daten.szenenuebersicht(conn, 1) == []


def test_kurzbeschreibung_geht_vor_was_passiert(conn):
    _szene(conn, 1, kurzbeschreibung="Eine Zeile", was_passiert="Drei Saetze")

    assert web_daten.szenenuebersicht(conn, 1)[0]["kurz"] == "Eine Zeile"


def test_gruppenseite_liefert_die_uebersicht_mit(conn):
    _szene(conn, 1, titel="Am Steg", form="chor")
    token = repo.hole_gruppe(conn, 1)["web_token"]

    daten = web_daten.gruppe_nach_token(conn, token)

    assert [z["nummer"] for z in daten["szenenuebersicht"]] == [1]
    # Die aufklappbaren Bloecke stehen unveraendert daneben.
    assert [s["nummer"] for s in daten["szenen"]] == [1]


# --- Darstellung -----------------------------------------------------------


def test_darstellung_zeigt_nummer_titel_form_und_umfang():
    html = web._szenenuebersicht_html(
        [
            {
                "nummer": 1, "titel": "Am Steg", "kurz": "Sie warten",
                "form": "", "form_vorschlag": "chor", "stil": "",
                "prosa_zeichen": 1200, "volltext_zeichen": 0,
            }
        ]
    )

    assert "Am Steg" in html
    assert "Sie warten" in html
    assert "chor (Vorschlag)" in html
    assert "Prosa 1200 Z." in html
    assert "Text " not in html


def test_darstellung_ist_bei_leerer_liste_leer():
    assert web._szenenuebersicht_html([]) == ""


def test_darstellung_maskiert_fremde_eingaben():
    html = web._szenenuebersicht_html(
        [
            {
                "nummer": 1, "titel": "<script>x</script>", "kurz": "",
                "form": "", "form_vorschlag": "", "stil": "",
                "prosa_zeichen": 0, "volltext_zeichen": 0,
            }
        ]
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_gruppenseite_stellt_die_uebersicht_den_bloecken_voran(conn):
    _szene(conn, 1, titel="Am Steg", form="chor")
    token = repo.hole_gruppe(conn, 1)["web_token"]
    daten = web_daten.gruppe_nach_token(conn, token)

    seite = web.gruppe_html(daten)

    assert 'class="uebersicht"' in seite
    # Erst die Tabelle, dann der aufklappbare Block.
    assert seite.index('class="uebersicht"') < seite.index('<details class="szene"')
