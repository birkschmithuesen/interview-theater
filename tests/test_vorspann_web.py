"""Der Vorspann auf der Gruppenseite (07.09.2026).

Zwei Dinge werden gemessen: dass ``web_daten`` dieselben Werte liefert wie der
Chat (eine Quelle, ``vorspann.daten``) und dass ``web`` sie ganz oben
darstellt -- read-only, mit maskierten Fremdeingaben.

Alle Namen und Texte sind erfunden.
"""

import pytest

from interview_theater import db, repo, vorspann, web, web_daten


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Die Ankommenden")
    return c


@pytest.fixture
def token(conn):
    return repo.hole_gruppe(conn, 1)["web_token"]


def _stueck(conn):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Hinterhof, Juli, abends")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "Bleiben oder gehen")
    repo.setze_arbeitsstand(conn, 1, "format", "Musical: Dialog, Lied")
    repo.setze_figur(conn, 1, "Mira", "haelt den Laden zusammen seit Jahren zeigt das")
    repo.setze_figur(conn, 1, "Jonas", "kommt zu spaet.")
    repo.setze_figur(conn, 1, "Karim", "war mal dabei")
    repo.entferne_figur(conn, 1, "Karim")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Am Steg")
    repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")


# --- web_daten -------------------------------------------------------------


def test_gruppenseite_liefert_den_vorspann_mit(conn, token):
    _stueck(conn)

    daten = web_daten.gruppe_nach_token(conn, token)

    d = daten["vorspann"]
    assert d["rahmen"] == "Ein Hinterhof, Juli, abends"
    assert d["hauptkonflikt"] == "Bleiben oder gehen"
    assert d["format"] == "Musical: Dialog, Lied"
    assert d["szenen"] == [{"nummer": 1, "titel": "Am Steg", "form": "Dialog"}]
    assert [f["name"] for f in d["figuren"]] == ["Mira", "Jonas"]
    assert d["figuren"][0]["beschreibung"] == "haelt den Laden zusammen seit Jahren"


def test_web_und_chat_lesen_denselben_vorspann(conn, token):
    """Ein Fakt hat eine Stelle: der Vorspann der Gruppenseite ist Zeichen
    fuer Zeichen der aus dem Chat."""
    _stueck(conn)

    aus_web = web_daten.gruppe_nach_token(conn, token)["vorspann"]
    aus_chat = vorspann.aus_datenbank(conn, 1)

    assert aus_web == aus_chat


def test_leere_gruppe_bekommt_einen_leeren_vorspann(conn, token):
    daten = web_daten.gruppe_nach_token(conn, token)

    assert vorspann.ist_leer(daten["vorspann"])


# --- Darstellung -----------------------------------------------------------


def test_darstellung_zeigt_rahmen_szenen_und_besetzung():
    d = vorspann.daten(
        "Ein Hinterhof", "Bleiben oder gehen", "Musical",
        [{"nummer": 1, "titel": "Am Steg", "form": "Dialog"}],
        [{"name": "Mira", "beschreibung": "wartet"}],
    )

    seite = web._vorspann_html(d)

    assert "<h3>Wo und wann</h3><p>Ein Hinterhof</p>" in seite
    assert "<h3>Worum es geht</h3><p>Bleiben oder gehen</p>" in seite
    assert "<h3>Form</h3><p>Musical</p>" in seite
    assert "1 Szene<" in seite
    assert "1. Am Steg" in seite
    assert "<h3>Wer vorkommt</h3>" in seite
    assert "<b>Mira</b> — wartet" in seite


def test_darstellung_ist_bei_leerem_vorspann_leer():
    assert web._vorspann_html(vorspann.daten("", "", "", [], [])) == ""
    assert web._vorspann_html(None) == ""


def test_darstellung_maskiert_fremde_eingaben():
    d = vorspann.daten(
        "<script>x</script>", "", "", [],
        [{"name": "<b>Mira", "beschreibung": "<i>wartet"}],
    )

    seite = web._vorspann_html(d)

    assert "<script>" not in seite
    assert "&lt;script&gt;" in seite
    assert "&lt;b&gt;Mira" in seite


def test_vorspann_steht_ganz_oben_auf_der_seite(conn, token):
    _stueck(conn)
    daten = web_daten.gruppe_nach_token(conn, token)

    seite = web.gruppe_html(daten)

    assert 'class="vorspann"' in seite
    assert seite.index('class="vorspann"') < seite.index("<h2>Arbeitsstand</h2>")
    assert seite.index('class="vorspann"') < seite.index("<h2>Szenen</h2>")
    # Die entfernte Figur steht auch hier nicht.
    assert "Karim" not in seite


def test_ohne_arbeitsstand_bleibt_die_seite_wie_bisher(conn, token):
    daten = web_daten.gruppe_nach_token(conn, token)

    seite = web.gruppe_html(daten)

    assert 'class="vorspann"' not in seite
    assert "<h2>Überblick</h2>" not in seite


def test_der_vorspann_bleibt_read_only(conn, token):
    """Kein Formularfeld im Vorspann: geaendert wird weiter unten, im
    Arbeitsstand -- zwei Eingabefelder fuer denselben Wert waeren zwei
    Wahrheiten."""
    _stueck(conn)
    daten = web_daten.gruppe_nach_token(conn, token)

    seite = web.gruppe_html(daten, nonce_wert="n")
    block = seite[seite.index('class="vorspann"'):seite.index("<h2>Arbeitsstand</h2>")]

    assert "<input" not in block
    assert "<textarea" not in block
    assert "<button" not in block
