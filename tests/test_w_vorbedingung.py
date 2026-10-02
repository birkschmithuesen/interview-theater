"""Worauf Karte W steht: die Flaeche der Karten A1 (Sprache) und A2 (Web-Kanal).

Kein Feature-Test -- ein **Abbruchkriterium**. Karte W wird headless
umgesetzt: faellt hier etwas aus, soll die Umsetzung stehenbleiben und das
melden, statt A1 oder A2 nachzubauen. Zwei Fassungen von ``web_kanal.py``
waeren teurer als ein Wartetag.

Der Test bleibt danach stehen: er ist die Liste der Namen, auf die W sich
stuetzt, und faellt auf, wenn eine spaetere Karte einen davon umbenennt.
"""

import pytest

from interview_theater import db, phasentexte, repo, sprache, web_chat, web_daten, web_kanal


@pytest.mark.parametrize("name", [
    "lege_web_post_an", "RICHTUNG_EIN", "WEB_TYP_BEFEHL", "hole_gruppe",
    "hole_arbeitsstand", "hole_szenen", "figuren", "verdichtungen",
])
def test_repo_traegt_was_w_braucht(name):
    assert hasattr(repo, name), f"repo.{name} fehlt -- Karte A2 nicht gemergt?"


@pytest.mark.parametrize("name", [
    "CHAT_PFAD", "_CHAT_JS", "_POSTWEGE", "chat_html", "_blase_html",
    "beantworte_get", "beantworte_post", "_sende_zustand",
])
def test_web_chat_traegt_was_w_braucht(name):
    assert hasattr(web_chat, name), f"web_chat.{name} fehlt -- Karte A2 nicht gemergt?"


@pytest.mark.parametrize("name", ["web_chatzustand", "web_chatverlauf", "oeffne_lesend",
                                  "chat_id_nach_token", "gruppe_nach_token"])
def test_web_daten_traegt_was_w_braucht(name):
    assert hasattr(web_daten, name)


def test_web_kanal_ist_die_kanalklasse():
    assert hasattr(web_kanal, "WebKanal")
    for name in ("sende", "sende_mit_knoepfen", "hole_updates", "tippt"):
        assert hasattr(web_kanal.WebKanal, name), name


def test_die_tippanzeige_hat_ihre_spalte(tmp_path):
    """``gruppe.web_tippt_bis`` (A2) -- die Roadmap liest sie fuer 'laeuft'."""
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 7_000_000_000_001, "gruppe1", "X")
    assert "web_tippt_bis" in repo.hole_gruppe(conn, 7_000_000_000_001).keys()


def test_die_sprachschicht_steht():
    """Karte A1: ``T = sprache.Texte(__name__)`` und die Beschriftungstabelle
    der Phasenparameter, aus der die Roadmap ihre Woerter nimmt."""
    assert hasattr(sprache, "Texte")
    assert hasattr(phasentexte, "PARAMETER_BESCHRIFTUNG")
    assert hasattr(phasentexte, "_beschriftung")
