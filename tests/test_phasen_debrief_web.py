"""Die Phasen-Debriefs auf der Gruppenseite (Task 5, Karte phasen-debrief).

Spiegelt ``tests/test_festlegung_web.py`` fuer den Abschnitt "So arbeitet
ihr": Lesen (``web_daten._phasen_debriefs``), Rendern (``web.
_phasen_debrief_html``) und den Streichen-Weg (``web_schreiben.
_entferne_phasen_debrief``) -- ueber echtes HTTP wie dort.

Ein Unterschied zu den Festlegungen ist Absicht und wird mitgetestet: der
Abschnitt zeigt bei Leere **gar nichts** (kein Satz wie "Noch nichts
festgehalten"), und der Loeschweg zielt auf die **Phase**, nicht auf eine id
(``phasen_debrief`` hat ``UNIQUE (chat_id, phase)``, keine fuer den Knopf
stabile id noetig).
"""

import json
import sqlite3
import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import db, kontext, repo, web, web_daten, web_schreiben

SCHLUESSEL = b"testschluessel"


@pytest.fixture
def db_pfad(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Die Ankommenden")
    repo.merke_phasen_debrief(conn, 1, 1, "Die Gruppe sammelt schnell.", "gemma")
    repo.merke_phasen_debrief(conn, 1, 2, "Fragen entstehen im Gespraech.", "gemma")
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


# --- Lesen -------------------------------------------------------------


def test_web_daten_liefert_die_phasen_debriefs(conn):
    daten = web_daten.gruppe_nach_token(conn, repo.stelle_web_token_sicher(conn, 1))
    zeilen = daten["phasen_debriefs"]
    assert [z["phase"] for z in zeilen] == [1, 2]
    assert zeilen[0]["text"] == "Die Gruppe sammelt schnell."


def test_gestrichener_debrief_steht_nicht_mehr_da(conn):
    repo.entferne_phasen_debrief(conn, 1, 1)
    daten = web_daten.gruppe_nach_token(conn, repo.stelle_web_token_sicher(conn, 1))
    assert [z["phase"] for z in daten["phasen_debriefs"]] == [2]


def test_ohne_tabelle_bleibt_die_seite_stehen(tmp_path):
    """Der Webserver migriert nichts -- er liest read-only. Eine Datenbank
    aus der Zeit vor dieser Tabelle darf keine 500 werfen."""
    pfad = str(tmp_path / "alt.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Alt")
    conn.execute("DROP TABLE phasen_debrief")
    conn.commit()
    daten = web_daten.gruppe_nach_token(conn, repo.stelle_web_token_sicher(conn, 1))
    assert daten["phasen_debriefs"] == []


# --- Rendern -------------------------------------------------------------


def test_leerer_abschnitt_zeigt_gar_nichts():
    """Anders als bei den Festlegungen: kein Platzhaltersatz, der Abschnitt
    faellt komplett weg (wie _sprechanteile_html/_dramaturgie_html)."""
    assert web._phasen_debrief_html({"phasen_debriefs": []}, None) == ""
    assert web._phasen_debrief_html({}, "nonce") == ""


def test_ohne_nonce_kein_streichknopf():
    daten = {"phasen_debriefs": [{"phase": 3, "text": "Ein Rueckblick."}]}
    seite = web._phasen_debrief_html(daten, None)
    assert "Ein Rueckblick." in seite
    assert "phasen_debrief_streichen" not in seite


def test_mit_nonce_steht_der_streichknopf_da():
    daten = {"phasen_debriefs": [{"phase": 3, "text": "Ein Rueckblick."}]}
    seite = web._phasen_debrief_html(daten, "nonce")
    assert 'data-feld="phasen_debrief_streichen"' in seite
    assert 'data-ziel="3"' in seite


def test_text_wird_maskiert():
    daten = {"phasen_debriefs": [{"phase": 1, "text": "<script>alert(1)</script>"}]}
    seite = web._phasen_debrief_html(daten, None)
    assert "<script>" not in seite
    assert "&lt;script&gt;" in seite


def test_abschnitt_steht_zwischen_festlegungen_und_szenen(basis, token):
    _, seite = hole(f"{basis}/g/{token}")
    assert "Die Gruppe sammelt schnell." in seite
    assert (
        seite.index("Weitere Festlegungen")
        < seite.index("So arbeitet ihr")
        < seite.index("<h2>Szenen</h2>")
    )


# --- Streichen -------------------------------------------------------------


def test_streichknopf_steht_an_jeder_karte(basis, token):
    _, seite = hole(f"{basis}/g/{token}")
    assert seite.count('data-feld="phasen_debrief_streichen"') == 2


def test_streichen_stempelt_weich_und_journalisiert(basis, token, conn):
    status, rumpf = sende(basis, token, "phasen_debrief_streichen", "", ziel=1)
    assert status == 200, rumpf
    assert [z["phase"] for z in repo.phasen_debriefs(conn, 1)] == [2]
    # Weich: die Zeile steht noch da, nur geloescht=1.
    assert conn.execute(
        "SELECT geloescht FROM phasen_debrief WHERE chat_id = 1 AND phase = 1"
    ).fetchone()[0]
    eintraege = repo.journal(conn, 1)
    assert eintraege[-1]["quelle"] == web_schreiben.QUELLE
    assert "Phase 1" in eintraege[-1]["text"]


def test_streichen_einer_fremden_gruppen_phase_geht_nicht(basis, token, conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Andere")
    repo.merke_phasen_debrief(conn, 2, 5, "Fremder Rueckblick.", "gemma")
    conn.commit()
    status, rumpf = sende(basis, token, "phasen_debrief_streichen", "", ziel=5)
    assert status == 400, rumpf
    assert [z["phase"] for z in repo.phasen_debriefs(conn, 2)] == [5]


def test_streichen_einer_unbekannten_phase_geht_nicht(basis, token):
    status, _ = sende(basis, token, "phasen_debrief_streichen", "", ziel=99)
    assert status == 400


def test_streichen_eines_ungueltigen_werts_geht_nicht(basis, token):
    status, _ = sende(basis, token, "phasen_debrief_streichen", "", ziel="abc")
    assert status == 400


def test_anlegen_geht_ueber_die_seite_nicht(basis, token):
    """Die Gruppenseite darf nur die aufgezaehlten Parameter
    (``web_schreiben.FELDER``) -- ein Debrief entsteht beim Phasenwechsel."""
    assert "phasen_debrief_neu" not in web_schreiben.FELDER
    status, _ = sende(basis, token, "phasen_debrief_neu", "irgendwas")
    assert status == 400


# --- Ende-zu-Ende: wirkt auch im Prompt-Block ------------------------------


def test_streichen_ueber_die_seite_wirkt_im_debrief_block(basis, token, conn):
    """Was auf der Gruppenseite gestrichen wird, verschwindet auch aus
    ``kontext.baue_debrief_block`` -- demselben Weg, den Task 4 fuer
    ``repo.entferne_phasen_debrief`` direkt schon absichert
    (``tests/test_phasen_debrief_kontext.py::
    test_geloeschter_debrief_faellt_aus_dem_block``). Hier zaehlt der Weg
    *ueber die Seite* (``web_schreiben`` -> ``repo``)."""
    vorher = kontext.baue_debrief_block(conn, 1)
    assert "Die Gruppe sammelt schnell." in vorher

    status, rumpf = sende(basis, token, "phasen_debrief_streichen", "", ziel=1)
    assert status == 200, rumpf

    nachher = kontext.baue_debrief_block(conn, 1)
    assert "Die Gruppe sammelt schnell." not in nachher
    assert "Fragen entstehen im Gespraech." in nachher
