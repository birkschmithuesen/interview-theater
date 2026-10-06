"""Das Regie-Dashboard zeigt die Gruppenfelder zusaetzlich auf Englisch
(Padua, Karte t_f7770dc4): Hauptthema als Kartenueberschrift, jedes Feld aus
dem Cache (``uebersetzung.py``), Original dezent markiert, solange die
Uebersetzung noch aussteht. Dortmund bleibt bitgleich
(``tests/test_web_dashboard_en.py::test_deutsch_byte_gleich_wie_vorher``)."""

import copy

import pytest

from interview_theater import uebersetzung, web, workshop
from test_web_dashboard_en import DATEN, _profil


@pytest.fixture(autouse=True)
def _frisch():
    yield
    workshop.vergiss()


@pytest.fixture
def padua(monkeypatch):
    _profil(monkeypatch, "padua-2026")


def _karten(html: str) -> list[str]:
    import re

    return re.findall(r'<section class="karte[^"]*">.*?</section>', html, flags=re.S)


def _mit_cache() -> dict:
    """DATEN, erste Gruppe mit einem passenden Uebersetzungscache."""
    daten = copy.deepcopy(DATEN)
    gruppe = daten["gruppen"][0]
    hash_ = uebersetzung.quelle_hash(
        gruppe["arbeitsstand"], gruppe["figuren"], gruppe["interview_kurzformen"],
    )
    gruppe["uebersetzung"] = {
        "quelle_hash": hash_,
        "felder": {
            "hauptthema": "Belonging (EN)",
            "rahmen": "EN bridge at night",
            "geschichte": "EN two friends meet",
            "kernthema": "EN belonging",
            "hauptkonflikt": "EN stay or leave",
            "begriffe": "EN bridge, market, rain",
            "fragen": "Home: EN where do you feel at home?\nWork: EN what do you do all day?",
            "figur_0": "EN Mira",
            "figur_1": "EN Luca",
            "interview_0_0": "EN fishing at dawn",
            "interview_0_1": "EN a lost key",
            "interview_1_0": "EN the old bakery",
        },
    }
    return daten


# --- Schalter nur Padua, Vorgabe/Dortmund aus ---------------------------------


def test_uebersetzen_nur_im_profil_gesetzt(monkeypatch):
    for profil, erwartet in ((None, False), ("dortmund-2026", False), ("padua-2026", True)):
        _profil(monkeypatch, profil)
        assert workshop.aktiv().wert("web.dashboard_uebersetzen_en") is erwartet


# --- Treffer: Ueberschrift und Felder aus dem Cache ---------------------------


def test_zeigt_hauptthema_als_ueberschrift_und_titel_als_unterzeile(padua):
    erste = _karten(web.dashboard_html(_mit_cache()))[0]
    assert "<h2>Belonging (EN)</h2>" in erste
    assert (
        '<p class="ux-untertitel">'
        '<a href="/theatersoap/g/tok123">Team Canal</a></p>'
    ) in erste


def test_zeigt_englische_felder_aus_dem_cache(padua):
    erste = _karten(web.dashboard_html(_mit_cache()))[0]
    for erwartet in ("EN bridge at night", "EN two friends meet", "EN belonging",
                      "EN stay or leave", "EN bridge, market, rain",
                      "EN fishing at dawn", "EN a lost key", "EN Mira", "EN Luca"):
        assert erwartet in erste, erwartet
    # Das Original steht nicht mehr roh da.
    assert "a bridge at night" not in erste
    assert "<span class=\"ux-ausstehend\">" not in erste


def test_zeigt_englische_fragen_aus_dem_cache(padua):
    erste = _karten(web.dashboard_html(_mit_cache()))[0]
    assert "EN where do you feel at home?" in erste
    assert "EN what do you do all day?" in erste
    assert "Where do you feel at home?" not in erste
    assert "What do you do all day?" not in erste


# --- Fallback: Original dezent markiert, solange der Cache fehlt -------------


def test_ohne_cache_zeigt_original_dezent_markiert(padua):
    erste = _karten(web.dashboard_html(DATEN))[0]
    # Keine Unterzeile ohne Hauptthema -- die Ueberschrift bleibt die alte.
    assert '<h2><a href="/theatersoap/g/tok123">Team Canal</a></h2>' in erste
    assert "ux-untertitel" not in erste
    assert '<span class="ux-ausstehend">a bridge at night</span>' in erste
    assert '<span class="ux-ausstehend">two friends meet on the bridge</span>' in erste
    assert '<b><span class="ux-ausstehend">Mira</span></b>' in erste


def test_veralteter_cache_gilt_als_ausstehend(padua):
    """Ein Cache, dessen Hash nicht mehr zur aktuellen Quelle passt (die
    Gruppe hat seit der letzten Uebersetzung weitergeschrieben), zeigt das
    Original -- nicht die veraltete englische Fassung."""
    daten = _mit_cache()
    daten["gruppen"][0]["uebersetzung"]["quelle_hash"] = "veraltet"
    erste = _karten(web.dashboard_html(daten))[0]
    assert "EN bridge at night" not in erste
    assert '<span class="ux-ausstehend">a bridge at night</span>' in erste


# --- Ohne den Profilschalter: byte-gleich, kein Marker ------------------------


@pytest.mark.parametrize("profil", [None, "dortmund-2026"])
def test_ohne_schalter_kein_marker_auch_mit_cache_in_den_daten(monkeypatch, profil):
    """Dortmund/Vorgabe ignorieren einen (hypothetischen) Cache-Eintrag
    komplett -- das ist der eigentliche Beweis fuer 'nur Padua'. Da
    ``gestaltet`` hier aus ist, laeuft das sowieso ueber den alten Zweig;
    die Probe steht trotzdem fuer den Fall, dass irgendwann ``gestaltet``
    ohne den Uebersetzungsschalter aktiv waere."""
    _profil(monkeypatch, profil)
    html = web.dashboard_html(_mit_cache())
    assert "ux-ausstehend" not in html
    assert "ux-untertitel" not in html
    assert "EN bridge at night" not in html


def test_dashboard_inhalt_html_ohne_cache_ist_byte_gleich_zur_vorherigen_form():
    """``_dashboard_inhalt_html`` ohne ``en``/``uebersetzen`` (Vorgabewerte)
    verhaelt sich wie vor dieser Karte -- die Dortmund-Bitgleich-Zusage haengt
    nicht nur am Profilschalter, sondern auch an dieser Funktionssignatur."""
    g = copy.deepcopy(DATEN["gruppen"][0])
    mit_default = web._dashboard_inhalt_html(g)
    mit_explizit_aus = web._dashboard_inhalt_html(g, {}, False)
    assert mit_default == mit_explizit_aus
    assert "ux-ausstehend" not in mit_default
