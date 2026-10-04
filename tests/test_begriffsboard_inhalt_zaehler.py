"""Karte t_2b9d2cbe: Zaehler und Falldaten der Begriffsboard-Messung -- offline."""

import pytest

from interview_theater import begriffsboard
from scripts import begriffsboard_inhalt_zaehler as z


def _fall(**kw):
    basis = dict(name="t", beschreibung="", sprache_gesprochen="de",
                 segmente=("a", "b"), soll=(("Heimat",), ("KI-Roboter", "KI Roboter")),
                 varianten=("Roboter",), meta=("Gepäck",), mit_grund=("Heimat",))
    basis.update(kw)
    return z.Fall(**basis)


TRANSKRIPT = ("der erste Gepäck ist Heimat. Heimat, weil meine Oma jeden Sonntag kocht. "
              "Roboter. nicht einfach Roboter, ein KI-Roboter.")


def _e(begriff, begruendung="", zitat="", doppelbedeutung="", status="kandidat"):
    return {"begriff": begriff, "nennungen": 1, "zustimmung": 0, "begruendung": begruendung,
            "zitat": zitat, "doppelbedeutung": doppelbedeutung, "status": status}


# -- Falldaten ----------------------------------------------------------------

def test_drei_erfundene_faelle_laden():
    faelle = z.lade_erfundene()
    assert [f.name for f in faelle] == list(z.ERFUNDEN)
    assert any(f.sprache_gesprochen != "en" for f in faelle)  # D5: deutsch bei EN-Profil


@pytest.mark.parametrize("fall", z.lade_erfundene(), ids=lambda f: f.name)
def test_falldaten_sind_im_transkript_belegt(fall):
    transkript = begriffsboard.schluessel("\n\n".join(fall.segmente))
    assert len(fall.segmente) >= 2                      # Lauf hat zwei Schritte
    for gruppe in fall.soll:
        assert any(begriffsboard.schluessel(a) in transkript for a in gruppe), gruppe
    for wort in fall.varianten + fall.meta + fall.mit_grund:
        assert begriffsboard.schluessel(wort) in transkript, wort


# -- sprache_von --------------------------------------------------------------

@pytest.mark.parametrize("text, erwartet", [
    ("Die Gruppe will den Ort, an dem die Oma kocht.", "de"),
    ("The group wants the place where the grandmother cooks.", "en"),
    ("Heimat", ""),
    ("", ""),
    ("Größe", "de"),
])
def test_sprache_von(text, erwartet):
    assert z.sprache_von(text) == erwartet


# -- zaehle -------------------------------------------------------------------

def test_sauberes_board_zaehlt_null():
    board = [
        _e("Heimat", "The grandmother cooks there every Sunday.",
           "weil meine Oma jeden Sonntag kocht"),
        _e("KI-Roboter"),
    ]
    zahl = z.zaehle(board, TRANSKRIPT, _fall(), "en")
    assert {k: zahl[k] for k in z.ZAEHLER} == dict.fromkeys(z.ZAEHLER, 0)
    assert zahl["eintraege"] == 2
    assert zahl["begruendungen_belegt"] == 1


def test_fehlerbilder_werden_gezaehlt():
    board = [
        _e("Heimat", "Wird als Begriff gesammelt.", "der erste Gepäck ist Heimat"),
        _e("Gepäck"),
        _e("Roboter", "Ist in KI-Roboter aufgegangen.", status="verworfen"),
        _e("heimat"),
    ]
    zahl = z.zaehle(board, TRANSKRIPT, _fall(), "en")
    assert zahl["fuell_begruendungen"] == 1        # "Wird als Begriff gesammelt."
    assert zahl["begruendung_ohne_beleg"] == 2     # Ansage-Zitat + Roboter ohne Zitat
    assert zahl["meta_begriffe"] == 1              # Gepäck
    assert zahl["dubletten"] == 3                  # 2. Heimat + Variante Roboter + Merge-Spur
    assert zahl["sprache_ungleich_profil"] == 2    # zwei deutsche Begruendungen ("wird"/"als", "ist")
    assert zahl["begriffe_fehlend"] == 1           # KI-Roboter fehlt
    assert zahl["begruendungen_belegt"] == 0


def test_summe_addiert_je_schluessel():
    assert z.summe([{"a": 1, "b": 0}, {"a": 2, "b": 3}]) == {"a": 3, "b": 3}


def test_tabelle_enthaelt_jeden_zaehler_und_arm():
    messung = {"arm": "vorher", "modell": "kimi", "runde": 0,
               "faelle": {"t": {"laeufe": 3, "fehler": 0,
                                "roh": dict.fromkeys(z.ZAEHLER + z.INFO, 1),
                                "validiert": dict.fromkeys(z.ZAEHLER + z.INFO, 0)}}}
    text = z.tabelle([messung])
    for name in z.ZAEHLER:
        assert name in text
    assert "vorher" in text and "kimi" in text
