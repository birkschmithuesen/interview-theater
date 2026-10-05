"""Die Werkbank-Sicht der Roadmap (Padua, 03.10.2026): je Phase ihre
Attribute mit drei Zustaenden -- erledigt, offen, spaeter.

Dieselbe ``lage`` wie ``roadmap.aus_daten``; keine zweite Wunschliste: die
Aufgabenzeilen SIND ``roadmap.AUFGABEN``, die Detailzeilen lesen nur, was in
``lage`` steht."""

import json

import pytest

from interview_theater import phasen, roadmap


def _lage(**abweichung) -> dict:
    grund = {
        "stand": {}, "figuren": [], "szenen": [], "interviews": [],
        "zuordnungen": 0, "pruefrunde": None, "phase": 1,
        "interviewmodus": False, "tippt": False, "strom": None,
    }
    grund.update(abweichung)
    return grund


def _phase(liste, nummer):
    return next(p for p in liste if p["nummer"] == nummer)


def _zeile(liste, nummer, kennung, bezug=None):
    for z in _phase(liste, nummer)["zeilen"]:
        if z["kennung"] == kennung and (bezug is None or z["bezug"] == bezug):
            return z
    raise AssertionError(f"{nummer}/{kennung}/{bezug} nicht gefunden")


# -- Grundform ---------------------------------------------------------------


def test_sieben_phasen_in_reihenfolge():
    assert [p["nummer"] for p in roadmap.werkbank(_lage(), 1)] == \
        [n for n, _, _ in phasen.PHASEN]


def test_die_aufgabenzeilen_sind_die_aufgaben_der_roadmap():
    """Keine zweite Liste: Kennung und Text kommen aus ``aus_daten``."""
    werkbank = roadmap.werkbank(_lage(), 1)
    for p in roadmap.aus_daten(_lage()):
        aufgaben = [z for z in _phase(werkbank, p["nummer"])["zeilen"]
                    if z["art"] == "aufgabe"]
        assert [(z["kennung"], z["text"]) for z in aufgaben] == \
            [(a["kennung"], a["text"]) for a in p["aufgaben"]]


def test_nur_die_aktuelle_phase_ist_aktiv():
    assert [p["nummer"] for p in roadmap.werkbank(_lage(phase=5), 5) if p["aktiv"]] == [5]


# -- die drei Zustaende ------------------------------------------------------


def test_erledigt():
    liste = roadmap.werkbank(_lage(stand={"begriffe": "Heimat, Arbeit"}), 1)
    assert _zeile(liste, 1, "begriffe")["status"] == roadmap.ERLEDIGT


def test_offen_in_der_aktuellen_und_in_frueheren_phasen():
    liste = roadmap.werkbank(_lage(phase=3), 3)
    assert _zeile(liste, 2, "fragen")["status"] == roadmap.OFFEN
    assert _zeile(liste, 3, "interviews")["status"] == roadmap.OFFEN


def test_nach_der_aktuellen_phase_ist_nichts_offen_sondern_spaeter():
    """Mutationsprobe: wer den Zweig ``nummer > aktuelle_phase`` entfernt,
    macht diesen Test rot."""
    liste = roadmap.werkbank(_lage(phase=3), 3)
    for p in liste:
        if p["nummer"] > 3:
            assert {z["status"] for z in p["zeilen"]} == {roadmap.SPAETER}, p["nummer"]


def test_erledigt_gilt_auch_in_einer_spaeteren_phase():
    liste = roadmap.werkbank(_lage(stand={"rahmen": "Bahnhof, nachts"}), 1)
    assert _zeile(liste, 4, "setting")["status"] == roadmap.ERLEDIGT


def test_laeuft_ist_offen_mit_vermerk():
    liste = roadmap.werkbank(_lage(phase=3, interviewmodus=True), 3)
    zeile = _zeile(liste, 3, "interviews")
    assert zeile["status"] == roadmap.OFFEN
    assert zeile["laeuft"] is True
    assert _zeile(liste, 2, "fragen")["laeuft"] is False


def test_zaehler_und_fertig():
    liste = roadmap.werkbank(_lage(phase=2, stand={"begriffe": "x"}), 2)
    eins, zwei = _phase(liste, 1), _phase(liste, 2)
    assert (eins["erledigt"], eins["gesamt"], eins["fertig"]) == (1, 1, True)
    assert (zwei["erledigt"], zwei["gesamt"], zwei["fertig"]) == (0, 4, False)


# -- Detailzeilen ------------------------------------------------------------


def test_ohne_diskussionsangabe_keine_zeile():
    zeilen = _phase(roadmap.werkbank(_lage(), 1), 1)["zeilen"]
    assert [z["kennung"] for z in zeilen] == ["begriffe"]


@pytest.mark.parametrize("da", [True, False])
def test_diskussion_ist_kein_schritt_der_gruppe(da):
    """Birk, 05.10.2026: die Diskussionsverdichtung laeuft still im
    Hintergrund -- keine Zeile in Phase 1, weder offen noch erledigt, und sie
    zaehlt nicht im Fortschritt."""
    eins = _phase(roadmap.werkbank(_lage(diskussion=da), 1), 1)
    assert [z["kennung"] for z in eins["zeilen"]] == ["begriffe"]
    assert eins["gesamt"] == 1


def test_je_interview_eine_zeile():
    lage = _lage(phase=3, interviews=[
        {"bezeichnung": "Interview 1", "zusammenfassung": "Sie erzaehlt."},
        {"bezeichnung": "Interview 2", "zusammenfassung": None},
    ])
    liste = roadmap.werkbank(lage, 3)
    assert _zeile(liste, 3, "interview", "Interview 1")["status"] == roadmap.ERLEDIGT
    assert _zeile(liste, 3, "interview", "Interview 2")["status"] == roadmap.OFFEN


def test_phase_5_je_szene_prosa():
    lage = _lage(phase=5, szenen=[
        {"nummer": 1, "titel": "Ankunft", "prosa": "Sie kommt an."},
        {"nummer": 2, "titel": "Abschied", "prosa": None},
    ])
    liste = roadmap.werkbank(lage, 5)
    eins = _zeile(liste, 5, "prosa", 1)
    assert (eins["status"], eins["titel"]) == (roadmap.ERLEDIGT, "Ankunft")
    assert _zeile(liste, 5, "prosa", 2)["status"] == roadmap.OFFEN


def test_phase_6_gesamttext_und_ueberarbeitung():
    lage = _lage(phase=6, stand={"gesamttext_fixiert_am": "2026-10-03T10:00:00+00:00"},
                 szenen=[{"nummer": 1, "ueberarbeitung_bestaetigt_am": "2026-10-03T10:00:00+00:00"},
                         {"nummer": 2}])
    liste = roadmap.werkbank(lage, 6)
    assert _zeile(liste, 6, "gesamttext")["status"] == roadmap.ERLEDIGT
    assert _zeile(liste, 6, "ueberarbeitet", 1)["status"] == roadmap.ERLEDIGT
    assert _zeile(liste, 6, "ueberarbeitet", 2)["status"] == roadmap.OFFEN


def test_phase_7_form_und_sprechweise():
    lage = _lage(phase=7,
                 szenen=[{"nummer": 1, "form": "dialog"}, {"nummer": 2, "form": None}],
                 figuren=[{"name": "Nadia", "sprachstil": "Knapp: Ja."}, {"name": "Tomas"}])
    liste = roadmap.werkbank(lage, 7)
    assert _zeile(liste, 7, "form", 1)["status"] == roadmap.ERLEDIGT
    assert _zeile(liste, 7, "form", 2)["status"] == roadmap.OFFEN
    assert _zeile(liste, 7, "sprechweise", "Nadia")["status"] == roadmap.ERLEDIGT
    assert _zeile(liste, 7, "sprechweise", "Tomas")["status"] == roadmap.OFFEN


# -- der Haken fuer begriffe_detail (Karte t_4517d4ad) ------------------------


@pytest.mark.parametrize("stand", [None, {}, {"begriffe_detail": None},
                                   {"begriffe_detail": "{kaputt"},
                                   {"begriffe_detail": '{"a": 1}'}])
def test_begriffe_detail_fehlt_oder_kaputt(stand):
    assert roadmap.begriffe_detail(stand) == []


def test_begriffe_detail_liest_die_liste_ohne_zitat():
    roh = json.dumps([
        {"begriff": "Heimat", "begruendung": "kam dreimal", "zitat": "z",
         "doppelbedeutung": "Ort und Gefuehl"},
        {"begriff": ""},
        "quatsch",
    ])
    assert roadmap.begriffe_detail({"begriffe_detail": roh}) == [
        {"begriff": "Heimat", "begruendung": "kam dreimal",
         "doppelbedeutung": "Ort und Gefuehl"},
    ]
