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


def test_einleitungen_fehlt_ohne_weiche_fassung(monkeypatch):
    """Feedbackloop P1-2, P2-H4: Padua schaltet ``[fragen_weich] aktiv`` ab
    -- das Profil-Prompt liefert nie eine weiche Fassung, also darf die
    Werkbank "Einleitungen" nicht als vierte Aufgabe mitzaehlen (sonst
    bleibt der Kreis "Questions x of 4" fuer immer leer)."""
    from interview_theater import workshop

    monkeypatch.setattr(workshop, "fragen_weich_aktiv", lambda *a, **k: False)
    liste = roadmap.werkbank(_lage(phase=2, stand={"begriffe": "x"}), 2)
    zwei = _phase(liste, 2)
    assert [z["kennung"] for z in zwei["zeilen"]] == ["fragen", "eroeffnung", "abschluss"]
    assert zwei["gesamt"] == 3


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


# -- Padua-Phasenumbau: Szenenkarten / Stage Script (Birk 08.10.2026) -------
#
# Workbench-Checkliste P6/P7 passt nicht zum neuen Ablauf: unter
# ``[karten] aktiv`` (``workshop.szenenkarten_aktiv``) zeigt Phase 6
# ("Scene Cards") einen Punkt je Szenenkarte statt der alten Prosa-Aufgaben,
# Phase 7 ("Stage Script") einen Punkt je Skript.


def test_phase_6_zeigt_eine_karte_je_szene_unter_karten(monkeypatch):
    from interview_theater import workshop

    monkeypatch.setattr(workshop, "szenenkarten_aktiv", lambda *a, **k: True)
    lage = _lage(phase=6, szenen=[
        {"nummer": 1, "titel": "Arrival", "karte_bestaetigt_am": "2026-10-08T10:00:00+00:00"},
        {"nummer": 2, "titel": "Farewell", "karte": "{}"},
        {"nummer": 3, "titel": "Silence"},
    ])
    liste = roadmap.werkbank(lage, 6)
    phase6 = _phase(liste, 6)
    assert [z["kennung"] for z in phase6["zeilen"]] == ["karte_1", "karte_2", "karte_3"]
    assert all(z["art"] == "aufgabe" for z in phase6["zeilen"])
    assert [z["text"] for z in phase6["zeilen"]] == [
        "Karte 1 · Arrival", "Karte 2 · Farewell", "Karte 3 · Silence",
    ]
    eins = _zeile(liste, 6, "karte_1")
    assert (eins["status"], eins["laeuft"]) == (roadmap.ERLEDIGT, False)
    zwei = _zeile(liste, 6, "karte_2")
    assert (zwei["status"], zwei["laeuft"]) == (roadmap.OFFEN, True)
    drei = _zeile(liste, 6, "karte_3")
    assert (drei["status"], drei["laeuft"]) == (roadmap.OFFEN, False)
    assert (phase6["erledigt"], phase6["gesamt"]) == (1, 3)


def test_phase_6_keine_alten_prosa_punkte_unter_karten(monkeypatch):
    from interview_theater import workshop

    monkeypatch.setattr(workshop, "szenenkarten_aktiv", lambda *a, **k: True)
    lage = _lage(phase=6, stand={"gesamttext_fixiert_am": "2026-10-03T10:00:00+00:00"},
                 szenen=[{"nummer": 1, "ueberarbeitung_bestaetigt_am": "x"}])
    kennungen = [z["kennung"] for z in _phase(roadmap.werkbank(lage, 6), 6)["zeilen"]]
    assert "szenentexte" not in kennungen
    assert "gesamttext" not in kennungen
    assert "ueberarbeitet" not in kennungen


def test_phase_7_zeigt_ein_script_je_szene_unter_karten(monkeypatch):
    from interview_theater import workshop

    monkeypatch.setattr(workshop, "szenenkarten_aktiv", lambda *a, **k: True)
    lage = _lage(phase=7, szenen=[
        {"nummer": 1, "titel": "Arrival", "volltext": "Text"},
        {"nummer": 2, "titel": "Farewell"},
    ])
    liste = roadmap.werkbank(lage, 7)
    phase7 = _phase(liste, 7)
    assert [z["kennung"] for z in phase7["zeilen"]] == ["script_1", "script_2"]
    assert [z["text"] for z in phase7["zeilen"]] == ["Skript 1 · Arrival", "Skript 2 · Farewell"]
    assert _zeile(liste, 7, "script_1")["status"] == roadmap.ERLEDIGT
    assert _zeile(liste, 7, "script_2")["status"] == roadmap.OFFEN
    assert (phase7["erledigt"], phase7["gesamt"]) == (1, 2)


def test_phase_7_keine_alten_form_sprechweise_punkte_unter_karten(monkeypatch):
    from interview_theater import workshop

    monkeypatch.setattr(workshop, "szenenkarten_aktiv", lambda *a, **k: True)
    lage = _lage(phase=7, szenen=[{"nummer": 1, "form": "dialog"}],
                 figuren=[{"name": "Nadia", "sprachstil": "x"}])
    kennungen = [z["kennung"] for z in _phase(roadmap.werkbank(lage, 7), 7)["zeilen"]]
    assert kennungen == ["script_1"]


def test_phase_7_skriptkopf_punkt_wenn_gebraucht(monkeypatch):
    from interview_theater import workshop

    monkeypatch.setattr(workshop, "szenenkarten_aktiv", lambda *a, **k: True)
    karte_instructions = '{"typ": "instructions"}'
    lage = _lage(phase=7, szenen=[
        {"nummer": 1, "titel": "A", "karte": karte_instructions},
        {"nummer": 2, "titel": "B", "karte": karte_instructions},
    ])
    kennungen = [z["kennung"] for z in _phase(roadmap.werkbank(lage, 7), 7)["zeilen"]]
    assert kennungen == ["script_1", "script_2", "skriptkopf"]
    assert _zeile(roadmap.werkbank(lage, 7), 7, "skriptkopf")["status"] == roadmap.OFFEN

    lage["stand"]["stage_kopf"] = "Versuchsanordnung ..."
    assert _zeile(roadmap.werkbank(lage, 7), 7, "skriptkopf")["status"] == roadmap.ERLEDIGT


def test_phase_7_kein_skriptkopf_punkt_ohne_mehrheit_anweisungen(monkeypatch):
    from interview_theater import workshop

    monkeypatch.setattr(workshop, "szenenkarten_aktiv", lambda *a, **k: True)
    lage = _lage(phase=7, szenen=[
        {"nummer": 1, "titel": "A", "karte": '{"typ": "description"}'},
    ])
    kennungen = [z["kennung"] for z in _phase(roadmap.werkbank(lage, 7), 7)["zeilen"]]
    assert kennungen == ["script_1"]


def test_ohne_karten_schalter_bleiben_phase_6_und_7_wie_vorher():
    """Dortmund-Gegenprobe: ohne ``[karten] aktiv`` bleiben die alten
    Punkte stehen -- unveraendert gegenueber
    ``test_phase_6_gesamttext_und_ueberarbeitung``/
    ``test_phase_7_form_und_sprechweise``."""
    lage_6 = _lage(phase=6, stand={"gesamttext_fixiert_am": "x"},
                   szenen=[{"nummer": 1, "ueberarbeitung_bestaetigt_am": "x"}])
    kennungen_6 = [z["kennung"] for z in _phase(roadmap.werkbank(lage_6, 6), 6)["zeilen"]]
    assert kennungen_6 == ["szenentexte", "gesamttext", "ueberarbeitet"]

    lage_7 = _lage(phase=7, szenen=[{"nummer": 1, "form": "dialog"}],
                   figuren=[{"name": "Nadia"}])
    kennungen_7 = [z["kennung"] for z in _phase(roadmap.werkbank(lage_7, 7), 7)["zeilen"]]
    assert kennungen_7 == ["stueckpruefung", "form", "sprechweise"]


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
