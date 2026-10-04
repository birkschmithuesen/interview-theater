"""Karte t_4517d4ad, Aufgabe 2: der reine Kern des Begriffsboards (D3, D4)."""

import pytest

from interview_theater import begriffsboard

TRANSKRIPT = (
    "Wir reden ueber Heimat. Heimat ist fuer mich, wo meine Oma kocht. "
    "Und Grenze, eine Grenze kann auch im Kopf sein. Mut fehlt uns manchmal."
)


def _zeile(**kw):
    basis = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 1,
             "begruendung": "Kam zweimal vor.", "zitat": "wo meine Oma kocht",
             "doppelbedeutung": "", "status": "kandidat"}
    basis.update(kw)
    return basis


# -- D3: Validierung ---------------------------------------------------------

def _pruefe_erfundener_begriff_fliegt_raus():
    ergebnis = begriffsboard.validiere(
        [_zeile(), _zeile(begriff="Freiheit", zitat="")], TRANSKRIPT,
    )
    assert [e["begriff"] for e in ergebnis] == ["Heimat"]


def test_erfundener_begriff_fliegt_raus():
    _pruefe_erfundener_begriff_fliegt_raus()


def test_mutant_ohne_transkriptpruefung_faellt_durch(monkeypatch):
    """D3-Mutant: wer die Transkriptpruefung entfernt, muss den Test oben rot
    machen -- sonst prueft er nichts."""
    monkeypatch.setattr(begriffsboard, "_steht_im_transkript", lambda begriff, transkript: True)
    with pytest.raises(AssertionError):
        _pruefe_erfundener_begriff_fliegt_raus()


def test_begriff_wird_normalisiert_und_casefold_gefunden():
    ergebnis = begriffsboard.validiere([_zeile(begriff="  heimat ")], TRANSKRIPT)
    assert ergebnis[0]["begriff"] == "heimat"


def test_unbelegtes_zitat_wird_leer_begruendung_bleibt():
    ergebnis = begriffsboard.validiere(
        [_zeile(zitat="Heimat ist alles fuer uns")], TRANSKRIPT,
    )
    assert ergebnis[0]["zitat"] == ""
    assert ergebnis[0]["begruendung"] == "Kam zweimal vor."


def test_belegtes_zitat_bleibt():
    assert begriffsboard.validiere([_zeile()], TRANSKRIPT)[0]["zitat"] == "wo meine Oma kocht"


@pytest.mark.parametrize("roh, erwartet", [(7, 2), (-9, -2), ("1", 1), ("viel", 0), (None, 0)])
def test_zustimmung_wird_geklemmt(roh, erwartet):
    assert begriffsboard.validiere([_zeile(zustimmung=roh)], TRANSKRIPT)[0]["zustimmung"] == erwartet


@pytest.mark.parametrize("roh, erwartet", [(-3, 0), ("4", 4), (2.9, 2), ("x", 0)])
def test_nennungen_ganzzahlig_nicht_negativ(roh, erwartet):
    assert begriffsboard.validiere([_zeile(nennungen=roh)], TRANSKRIPT)[0]["nennungen"] == erwartet


@pytest.mark.parametrize("status, erwartet", [
    ("favorit", "favorit"), ("VERWORFEN", "verworfen"), ("top", "kandidat"), (None, "kandidat"),
])
def test_status(status, erwartet):
    assert begriffsboard.validiere([_zeile(status=status)], TRANSKRIPT)[0]["status"] == erwartet


def test_dubletten_nach_normalisiertem_begriff():
    ergebnis = begriffsboard.validiere(
        [_zeile(), _zeile(begriff="HEIMAT", nennungen=9)], TRANSKRIPT,
    )
    assert len(ergebnis) == 1
    assert ergebnis[0]["nennungen"] == 2


def test_liste_ist_gedeckelt():
    roh = [_zeile(begriff=w) for w in TRANSKRIPT.replace(".", "").replace(",", "").split()]
    assert len(begriffsboard.validiere(roh * 3, TRANSKRIPT)) <= begriffsboard.HOECHSTENS


@pytest.mark.parametrize("roh", [None, "kaputt", {"board": []}, [1, "x", None]])
def test_kaputte_eingaben_geben_leere_liste(roh):
    assert begriffsboard.validiere(roh, TRANSKRIPT) == []


def test_begriff_mit_listentrenner_fliegt_raus():
    """Ein Begriff mit Komma wuerde beim Speichern (``begriffe.zerlege``) in
    zwei zerfallen."""
    assert begriffsboard.validiere([_zeile(begriff="Heimat, Grenze")], TRANSKRIPT) == []


def test_fehlende_felder_werden_aufgefuellt():
    ergebnis = begriffsboard.validiere([{"begriff": "Mut"}], TRANSKRIPT)
    assert ergebnis == [{"begriff": "Mut", "nennungen": 0, "zustimmung": 0,
                         "begruendung": "", "zitat": "", "doppelbedeutung": "",
                         "status": "kandidat"}]


# -- D4: Sortierung und Top 5 -----------------------------------------------

def _e(begriff, status="kandidat", zustimmung=0, nennungen=0):
    return {"begriff": begriff, "status": status, "zustimmung": zustimmung,
            "nennungen": nennungen, "begruendung": "", "zitat": "", "doppelbedeutung": ""}


def test_sortierung_status_dann_zustimmung_dann_nennungen_dann_begriff():
    eintraege = [
        _e("Zebra", "kandidat", 2, 1),
        _e("Apfel", "verworfen", 2, 9),
        _e("Mut", "favorit", -1, 0),
        _e("Birne", "kandidat", 2, 1),
        _e("Kiwi", "kandidat", 2, 5),
        _e("Dorf", "kandidat", 1, 9),
    ]
    assert [e["begriff"] for e in begriffsboard.sortiert(eintraege)] == [
        "Mut", "Kiwi", "Birne", "Zebra", "Dorf", "Apfel",
    ]


def test_top_fuenf_ohne_verworfene():
    eintraege = [_e(f"B{i}", "kandidat", 0, i) for i in range(7)] + [_e("X", "verworfen", 2, 99)]
    oben = begriffsboard.top(eintraege)
    assert len(oben) == 5
    assert all(e["status"] != "verworfen" for e in oben)
    assert [e["begriff"] for e in oben] == ["B6", "B5", "B4", "B3", "B2"]


def test_lies_ist_defensiv():
    assert begriffsboard.lies(None) == []
    assert begriffsboard.lies("{kaputt") == []
    assert begriffsboard.lies('{"a": 1}') == []
    assert begriffsboard.lies('[{"begriff": "Mut", "status": "favorit"}, {"x": 1}]') == [
        {"begriff": "Mut", "nennungen": 0, "zustimmung": 0, "begruendung": "",
         "zitat": "", "doppelbedeutung": "", "status": "favorit"},
    ]


# -- D7: Detail-Abgleich -----------------------------------------------------

def test_detail_fuer_gleicht_casefold_ab_und_haelt_die_reihenfolge_der_gruppe():
    board = [_zeile(begriff="Heimat", doppelbedeutung="Ort und Gefuehl"), _zeile(begriff="Mut")]
    detail = begriffsboard.detail_fuer(board, "mut, HEIMAT, Schule")
    assert [d["begriff"] for d in detail] == ["mut", "HEIMAT", "Schule"]
    assert detail[1] == {"begriff": "HEIMAT", "begruendung": "Kam zweimal vor.",
                         "zitat": "wo meine Oma kocht", "doppelbedeutung": "Ort und Gefuehl"}
    assert detail[2] == {"begriff": "Schule", "begruendung": "", "zitat": "", "doppelbedeutung": ""}


def test_detail_zeilen_ohne_zitat_und_nur_mit_inhalt():
    detail = [
        {"begriff": "Heimat", "begruendung": "Wo die Oma kocht.", "zitat": "ZITAT", "doppelbedeutung": "Ort"},
        {"begriff": "Schule", "begruendung": "", "zitat": "", "doppelbedeutung": ""},
        {"begriff": "Grenze", "begruendung": "", "zitat": "", "doppelbedeutung": "im Kopf"},
    ]
    zeilen = begriffsboard.detail_zeilen(detail)
    assert len(zeilen) == 2
    assert "Heimat" in zeilen[0] and "Wo die Oma kocht." in zeilen[0] and "Ort" in zeilen[0]
    assert "Grenze" in zeilen[1] and "im Kopf" in zeilen[1]
    assert not any("ZITAT" in z for z in zeilen)
    assert not any("Schule" in z for z in zeilen)
