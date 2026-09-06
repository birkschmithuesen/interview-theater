"""Die Fassungsuebersicht auf der Gruppenseite (07.09.2026).

Der Auftrag in vier Punkten, und genau die werden gemessen: **eine Zeile je
Szene mit dem Zaehler**, **umschalten** statt aufklappen, von der aktuellen
Fassung ein **Link auf die vorige**, und **read-only** -- kein Schreibweg von
aussen.

Dazu die Rueckwaertskompatibilitaet: eine Szene, deren Fassungen noch im
Altfeld ``szene.fruehere_fassungen`` stehen, wird genauso angezeigt.

Alle Texte sind erfunden.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, szenenfolge, web, web_daten


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Die Ankommenden")
    return c


@pytest.fixture
def token(conn):
    return repo.hole_gruppe(conn, 1)["web_token"]


def _szene_mit_fassungen(conn, texte, nummer=1):
    szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Steg")
    repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")
    for text in texte:
        repo.lege_szenenfassung_an(conn, 1, szene_id, text, "Dialog")
    repo.aktualisiere_szene(conn, szene_id, "Am Steg", None, texte[-1], None)
    return szene_id


# --- Lesen -----------------------------------------------------------------


def test_fassungen_werden_durchgezaehlt_und_die_aktuelle_markiert(conn):
    szene_id = _szene_mit_fassungen(conn, ["eins", "zwei", "drei"])

    je_szene = web_daten.szenenfassungen(conn, 1)

    fassungen = je_szene[szene_id]
    assert [f["nummer"] for f in fassungen] == [1, 2, 3]
    assert [f["volltext"] for f in fassungen] == ["eins", "zwei", "drei"]
    assert [f["aktuell"] for f in fassungen] == [False, False, True]
    assert fassungen[0]["beschriftung"] == "Dialog"


def test_altfeld_wird_mitgelesen(conn):
    """Rueckwaertskompatibel: eine Szene aus der Zeit vor der Tabelle hat ihre
    Fassungen als einen Textblock in ``fruehere_fassungen``."""
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    conn.execute(
        "UPDATE szene SET fruehere_fassungen = ?, volltext = ? WHERE id = ?",
        ("alt eins" + szenenfolge.FASSUNGSTRENNER + "alt zwei", "neu", szene_id),
    )
    conn.commit()

    fassungen = web_daten.szenenfassungen(conn, 1)[szene_id]

    assert [f["volltext"] for f in fassungen] == ["alt eins", "alt zwei", "neu"]
    assert [f["nummer"] for f in fassungen] == [1, 2, 3]


def test_derselbe_text_in_beiden_quellen_zaehlt_einmal(conn):
    """``repo.hebe_fassung_auf`` schreibt beim Nachruesten in Feld UND Tabelle
    -- doppelt darf das nicht in der Liste landen."""
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.aktualisiere_szene(conn, szene_id, "Am Steg", None, "erste", None)
    repo.hebe_fassung_auf(conn, szene_id)

    fassungen = web_daten.szenenfassungen(conn, 1)[szene_id]

    assert [f["volltext"] for f in fassungen] == ["erste"]


def test_ohne_text_gibt_es_keine_fassungen(conn):
    repo.stelle_szene_sicher(conn, 1, 1)

    assert web_daten.szenenfassungen(conn, 1) == {}


def test_fehlende_tabelle_ist_kein_fehler(conn):
    """Der Webserver migriert nichts: fehlt die Tabelle, faellt er auf das
    Altfeld zurueck, statt eine 500 zu liefern."""
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.aktualisiere_szene(conn, szene_id, "Am Steg", None, "nur der Volltext", None)
    conn.execute("DROP TABLE szenenfassung")
    conn.commit()

    fassungen = web_daten.szenenfassungen(conn, 1)[szene_id]

    assert [f["volltext"] for f in fassungen] == ["nur der Volltext"]


def test_der_zaehler_steht_in_der_szenenuebersicht(conn):
    _szene_mit_fassungen(conn, ["eins", "zwei", "drei"])

    zeile = web_daten.szenenuebersicht(conn, 1)[0]

    assert zeile["fassungen"] == 3
    assert zeile["id"] is not None


def test_gruppenseite_liefert_die_fassungen_mit(conn, token):
    szene_id = _szene_mit_fassungen(conn, ["eins", "zwei"])

    daten = web_daten.gruppe_nach_token(conn, token)

    assert [f["nummer"] for f in daten["fassungen"][szene_id]] == [1, 2]


# --- Darstellung -----------------------------------------------------------


def test_zeile_je_szene_zeigt_den_zaehler_als_link():
    html = web._szenenuebersicht_html(
        [
            {
                "id": 7, "fassungen": 3, "nummer": 1, "titel": "Am Steg",
                "kurz": "", "form": "Dialog", "form_vorschlag": "", "stil": "",
                "prosa_zeichen": 0, "volltext_zeichen": 40,
            }
        ]
    )

    assert "3 Fassungen" in html
    assert 'href="?szene=7&amp;fassung=3#szene-7"' in html or "?szene=7&fassung=3" in html


def test_eine_einzige_fassung_bekommt_keinen_zaehler():
    html = web._szenenuebersicht_html(
        [
            {
                "id": 7, "fassungen": 1, "nummer": 1, "titel": "Am Steg",
                "kurz": "", "form": "", "form_vorschlag": "", "stil": "",
                "prosa_zeichen": 0, "volltext_zeichen": 40,
            }
        ]
    )

    assert "Fassung" not in html.split("<tbody>")[1]


def _fassungen(*texte):
    return [
        {
            "nummer": i,
            "beschriftung": "Dialog",
            "volltext": t,
            "erstellt_am": None,
            "zeichen": len(t),
            "aktuell": i == len(texte),
        }
        for i, t in enumerate(texte, start=1)
    ]


def test_umschalten_zeigt_genau_eine_fassung():
    s = {"id": 7, "nummer": 1, "titel": "Am Steg", "volltext": "drei"}
    fassungen = _fassungen("eins", "zwei", "drei")

    seite = web._szene_html(s, None, fassungen, 2)

    assert "3 Fassungen" in seite
    assert "zwei" in seite
    # Die anderen Texte stehen NICHT daneben -- umschalten, nicht aufklappen.
    assert "eins" not in seite
    assert ">drei<" not in seite


def test_ohne_auswahl_steht_die_aktuelle_da():
    s = {"id": 7, "nummer": 1, "titel": "Am Steg", "volltext": "drei"}

    seite = web._szene_html(s, None, _fassungen("eins", "zwei", "drei"), None)

    assert "drei" in seite
    assert "die aktuelle" in seite


def test_von_der_aktuellen_fuehrt_ein_link_auf_die_vorige():
    s = {"id": 7, "nummer": 1, "titel": "Am Steg", "volltext": "drei"}

    seite = web._szene_html(s, None, _fassungen("eins", "zwei", "drei"), None)

    assert "vorige Fassung" in seite
    assert "?szene=7&amp;fassung=2#szene-7" in seite


def test_die_erste_fassung_hat_keine_vorgaengerin():
    s = {"id": 7, "nummer": 1, "titel": "Am Steg", "volltext": "drei"}

    seite = web._szene_html(s, None, _fassungen("eins", "zwei", "drei"), 1)

    assert "vorige Fassung" not in seite


def test_eine_einzige_fassung_schaltet_nicht_um():
    s = {"id": 7, "nummer": 1, "titel": "Am Steg", "volltext": "eins"}

    seite = web._szene_html(s, None, _fassungen("eins"), None)

    assert "Fassungen" not in seite
    assert "eins" in seite


def test_unbekannte_nummer_faellt_auf_die_aktuelle_zurueck():
    s = {"id": 7, "nummer": 1, "titel": "Am Steg", "volltext": "drei"}

    seite = web._szene_html(s, None, _fassungen("eins", "zwei", "drei"), 99)

    assert "Fassung 3 von 3" in seite


def test_fassungstexte_werden_maskiert():
    s = {"id": 7, "nummer": 1, "titel": "Am Steg", "volltext": "<script>x</script>"}
    fassungen = _fassungen("alt", "<script>x</script>")

    seite = web._szene_html(s, None, fassungen, None)

    assert "<script>" not in seite
    assert "&lt;script&gt;" in seite


def test_die_gewaehlte_szene_steht_aufgeklappt_da():
    s = {"id": 7, "nummer": 1, "titel": "Am Steg", "volltext": "drei"}

    seite = web._szene_html(s, None, _fassungen("eins", "zwei", "drei"), 2)

    assert 'id="szene-7"' in seite
    assert "<details class=\"szene\" id=\"szene-7\" open>" in seite


# --- Query und Route -------------------------------------------------------


def test_query_wird_gelesen():
    assert web.fassungswahl("szene=7&fassung=2") == {7: 2}


@pytest.mark.parametrize(
    "query", ["", "szene=7", "fassung=2", "szene=x&fassung=2", "szene=7&fassung=0",
              "szene=7&fassung=abc"],
)
def test_unbrauchbare_query_wird_verworfen(query):
    assert web.fassungswahl(query) == {}


def test_die_kopfzeile_endet_nicht_auf_einem_trenner(conn, token):
    """``_zeitpunkt`` ist ein Praefix mit Trenner -- angehaengt endete die
    Zeile auf ' · ' ohne Fortsetzung."""
    szene_id = _szene_mit_fassungen(conn, ["eins", "zwei"])
    daten = web_daten.gruppe_nach_token(conn, token)

    seite = web.gruppe_html(daten, None, {szene_id: 1})

    zeile = seite.split('<p class="zeit">')[1].split("</p>")[0]
    assert "Fassung 1 von 2" in zeile
    assert not zeile.rstrip().endswith("·")


def test_seite_zeigt_die_gewaehlte_fassung(conn, token):
    szene_id = _szene_mit_fassungen(conn, ["eins", "zwei", "drei"])
    daten = web_daten.gruppe_nach_token(conn, token)

    seite = web.gruppe_html(daten, None, {szene_id: 1})

    assert "Fassung 1 von 3" in seite
    assert "3 Fassungen" in seite


# --- Read-only -------------------------------------------------------------


@pytest.fixture
def basis(tmp_path, conn):
    """Ein laufender Server auf derselben Datenbank."""
    server = web.baue_server(str(tmp_path / "t.db"), "127.0.0.1:0", "/theatersoap")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_die_fassungsansicht_schreibt_nichts(basis, token, conn):
    szene_id = _szene_mit_fassungen(conn, ["eins", "zwei", "drei"])
    vorher = [
        (z["nummer"], z["volltext"]) for z in repo.szenenfassungen(conn, szene_id)
    ]

    with urllib.request.urlopen(f"{basis}/g/{token}?szene={szene_id}&fassung=1") as a:
        seite = a.read().decode("utf-8")

    assert "Fassung 1 von 3" in seite
    assert [
        (z["nummer"], z["volltext"]) for z in repo.szenenfassungen(conn, szene_id)
    ] == vorher
    assert repo.hole_szene(conn, szene_id)["volltext"] == "drei"


def test_es_gibt_keinen_schreibweg_auf_eine_fassung(basis, token, conn):
    """Read-only heisst read-only: keiner der Felder aus ``web_schreiben``
    heisst 'fassung', und ein POST darauf ist ein Bedienfehler (400)."""
    from interview_theater import web_schreiben

    assert not any("fassung" in feld for feld in web_schreiben.FELDER)

    rumpf = json.dumps(
        {"feld": "szene_fassung", "wert": "1", "ziel": 1, "nonce": "x"}
    ).encode("utf-8")
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}", data=rumpf,
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage)

    assert fehler.value.code in (400, 403)


def test_das_trennzeichen_stimmt_mit_szenenfolge_ueberein():
    assert web_daten.FASSUNGSTRENNER == szenenfolge.FASSUNGSTRENNER
