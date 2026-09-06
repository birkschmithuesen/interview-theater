"""Die Festlegungen auf der Gruppenseite (06.09.2026) -- ueber echtes HTTP.

**Aufgeklappt, nicht in einem ``<details>``**, und mit Loeschknopf je Zeile.
Beides steht so in der Analyse, und beides ist Pflicht, nicht Kuer: das
Journal ist auf derselben Seite sichtbar und trotzdem unwirksam gewesen
(§ 2.7 "sichtbar, nicht wirksam"), und ohne Loeschknopf erbt die neue
Tabelle den Fehler mit den veralteten Eintraegen (§ 2.5).

Aufbau wie ``tests/test_web_edit.py``: Server auf 127.0.0.1:0 im Thread,
urllib davor, kein Netzzugriff nach draussen. Fixtures synthetisch.
"""

import json
import sqlite3
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, repo, web, web_daten, web_schreiben

SCHLUESSEL = b"testschluessel"


@pytest.fixture
def db_pfad(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Die Ankommenden")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    repo.schreibe_festlegung(
        conn, 1, "figur", "19, arbeitet im Kiosk", bezug="Sevda"
    )
    repo.schreibe_festlegung(conn, 1, "struktur", "Nur eine Szene, erste Folge")
    conn.commit()
    return pfad


@pytest.fixture
def conn(db_pfad):
    return db.verbinde(db_pfad)


@pytest.fixture
def token(conn):
    return repo.stelle_web_token_sicher(conn, 1)


@pytest.fixture
def basis(db_pfad):
    server = web.baue_server(db_pfad, bind="127.0.0.1:0", schluessel=SCHLUESSEL)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def hole(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def sende(basis: str, token: str, feld: str, wert, ziel=None) -> tuple[int, str]:
    rumpf = {
        "nonce": web.nonce(SCHLUESSEL, token),
        "feld": feld, "wert": wert, "ziel": ziel,
    }
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}",
        data=json.dumps(rumpf).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


# --- Lesen -----------------------------------------------------------------


def test_web_daten_liefert_die_festlegungen(conn):
    daten = web_daten.gruppe_nach_token(conn, repo.stelle_web_token_sicher(conn, 1))
    zeilen = daten["festlegungen"]
    assert [z["text"] for z in zeilen] == [
        "19, arbeitet im Kiosk", "Nur eine Szene, erste Folge"
    ]
    assert zeilen[0]["bezug"] == "Sevda"
    assert zeilen[0]["id"]


def test_entfernte_festlegung_steht_nicht_mehr_da(conn):
    repo.entferne_festlegung(conn, 1, "Kiosk")
    daten = web_daten.gruppe_nach_token(conn, repo.stelle_web_token_sicher(conn, 1))
    assert [z["text"] for z in daten["festlegungen"]] == [
        "Nur eine Szene, erste Folge"
    ]


def test_ohne_tabelle_bleibt_die_seite_stehen(tmp_path):
    """Der Webserver migriert nichts -- er liest read-only. Eine Datenbank
    aus der Zeit vor dieser Tabelle darf keine 500 werfen."""
    pfad = str(tmp_path / "alt.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Alt")
    conn.execute("DROP TABLE festlegung")
    conn.commit()
    daten = web_daten.gruppe_nach_token(conn, repo.stelle_web_token_sicher(conn, 1))
    assert daten["festlegungen"] == []


def test_abschnitt_steht_aufgeklappt_auf_der_seite(basis, token):
    _, seite = hole(f"{basis}/g/{token}")
    assert "19, arbeitet im Kiosk" in seite
    assert "Nur eine Szene, erste Folge" in seite
    # Aufgeklappt heisst: nicht in einem <details> wie das Journal.
    abschnitt = seite[seite.index("Weitere Festlegungen"):]
    assert "<details" not in abschnitt[: abschnitt.index("<h2")]


def test_abschnitt_steht_zwischen_arbeitsstand_und_szenen(basis, token):
    _, seite = hole(f"{basis}/g/{token}")
    assert (
        seite.index("<h2>Arbeitsstand</h2>")
        < seite.index("Weitere Festlegungen")
        < seite.index("<h2>Szenen</h2>")
    )


def test_leerer_abschnitt_sagt_es(tmp_path):
    daten = {"festlegungen": []}
    assert "Noch nichts" in web._festlegungen_html(daten, None)


def test_ohne_nonce_kein_loeschknopf():
    """Die Leseansicht (``gruppe_html`` ohne Nonce, z. B. im Dashboard-Pfad)
    zeigt die Festlegungen, aber keinen Knopf."""
    daten = {"festlegungen": [
        {"id": 1, "bereich": "ort", "bezug": None, "text": "der Skatepark"}
    ]}
    seite = web._festlegungen_html(daten, None)
    assert "der Skatepark" in seite
    assert "festlegung_entfernen" not in seite


# --- Loeschen --------------------------------------------------------------


def test_loeschknopf_steht_an_jeder_zeile(basis, token, conn):
    _, seite = hole(f"{basis}/g/{token}")
    assert seite.count('data-feld="festlegung_entfernen"') == 2


def test_loeschen_stempelt_weich_und_journalisiert(basis, token, conn):
    ziel = web_daten.gruppe_nach_token(conn, token)["festlegungen"][0]["id"]
    status, rumpf = sende(basis, token, "festlegung_entfernen", "", ziel=ziel)
    assert status == 200, rumpf
    assert [z["text"] for z in repo.festlegungen(conn, 1)] == [
        "Nur eine Szene, erste Folge"
    ]
    # Weich: die Zeile steht noch da.
    assert conn.execute(
        "SELECT entfernt_am FROM festlegung WHERE id = ?", (ziel,)
    ).fetchone()[0]
    eintraege = repo.journal(conn, 1)
    assert eintraege[-1]["quelle"] == web_schreiben.QUELLE
    assert "19, arbeitet im Kiosk" in eintraege[-1]["text"]


def test_loeschen_einer_fremden_festlegung_geht_nicht(basis, token, conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere")
    fremd = repo.schreibe_festlegung(conn, 2, "ort", "Fremder Ort")
    status, rumpf = sende(basis, token, "festlegung_entfernen", "", ziel=fremd)
    assert status == 400, rumpf
    assert len(repo.festlegungen(conn, 2)) == 1


def test_loeschen_einer_unbekannten_id_geht_nicht(basis, token):
    status, _ = sende(basis, token, "festlegung_entfernen", "", ziel=99999)
    assert status == 400


def test_anlegen_geht_ueber_die_seite_nicht(basis, token):
    """Die Gruppenseite darf nur die aufgezaehlten Parameter
    (``web_schreiben.FELDER``) -- eine Festlegung entsteht im Chat."""
    assert "festlegung_neu" not in web_schreiben.FELDER
    status, _ = sende(basis, token, "festlegung_neu", "irgendwas")
    assert status == 400
