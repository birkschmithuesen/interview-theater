"""Das Skript: Zielzustaende und die datengetriebene Ableitung der
Arbeitsstandfelder einer Phase -- ohne Netz.

Der Kern dieser Datei: ``felder_fuer_phase`` darf **nicht** wissen, wie die
Phase 5 heisst. Sie liest den Kurznamen aus ``phasen.PHASEN`` und die Spalten
aus ``PRAGMA table_info(arbeitsstand)``. Genau das muss auch dann noch
funktionieren, wenn die Phase nach einem Umbau anders heisst -- deshalb wird
sie hier mit einer erfundenen Phasenliste geprueft und nicht nur mit der
heutigen.
"""

import pytest

from interview_theater import phasen, repo, workshop
from simulation import skript


@pytest.fixture
def stand(conn):
    return conn


def test_alle_schritte_haben_eine_bekannte_art():
    for schritt in skript.SCHRITTE:
        assert schritt.art in skript.ARTEN, schritt.schluessel


def test_schluessel_sind_eindeutig():
    schluessel = [s.schluessel for s in skript.SCHRITTE]
    assert len(set(schluessel)) == len(schluessel)


def test_ohne_szene_laesst_genau_den_szenen_schritt_weg():
    voll = {s.schluessel for s in skript.SCHRITTE}
    ohne = {s.schluessel for s in skript.ohne_szene()}
    assert voll - ohne == {"szene"}


def test_schritt_fuer_findet_und_meckert():
    assert skript.schritt_fuer("begriffe").titel
    with pytest.raises(KeyError):
        skript.schritt_fuer("gibtsnicht")


# --- Arbeitsstandfelder einer Phase ---------------------------------------


def test_felder_fuer_phase_findet_rahmen_und_geschichte(conn):
    """Der Stand nach dem Umbau vom 06.09.2026: Phase 4 heisst 'Setting,
    Figuren & Geschichte', und zwei der drei Worte sind Spaltennamen
    (``rahmen`` heisst im Kurznamen 'Setting', deshalb nur ``geschichte``;
    Figuren sind eine eigene Tabelle). Der Simulator ist datengetrieben und
    folgt dem Umbau ohne Anpassung -- genau das ist hier geprueft."""
    assert skript.felder_fuer_phase(conn, 4) == ["geschichte"]


def test_pflichtfeld_ist_das_erste_feld_der_phase(conn):
    """``geschichte`` ist das Pflichtfeld der Phase 4 -- dieselbe Gewichtung
    wie in ``phasen.voraussetzungen`` fuer den Schritt nach 5."""
    assert skript.pflichtfeld_fuer_phase(conn, 4) == "geschichte"


def test_felder_fuer_phase_ignoriert_schluessel_und_buchhaltung(conn):
    for nummer, _, _ in phasen.PHASEN:
        assert "chat_id" not in skript.felder_fuer_phase(conn, nummer)
        assert "phase" not in skript.felder_fuer_phase(conn, nummer)


def _umbenannt(monkeypatch, nummer, neuer_name):
    """Benennt eine Phase um -- am Workshop-Profil, aus dem ``phasen.py``
    seit dem 06.09.2026 liest. Vorher stand die Liste als ``phasen.PHASEN``
    im Modul, und der Test hat sie dort ueberschrieben."""
    liste = tuple(
        (n, neuer_name if n == nummer else name, satz)
        for n, name, satz in phasen.PHASEN
    )
    monkeypatch.setattr(workshop, "phasenliste", lambda profil=None: liste)


def test_felder_fuer_phase_folgt_einer_umbenannten_phase(conn, monkeypatch):
    """Bis zum 05.09.2026 hiess Phase 5 'Hauptkonflikt'. Hiesse eine Phase
    morgen wieder so, faende der Simulator die Spalte ``hauptkonflikt`` --
    ohne dass jemand diese Datei anfasst."""
    _umbenannt(monkeypatch, 5, "Hauptkonflikt")
    assert skript.felder_fuer_phase(conn, 5) == ["hauptkonflikt"]
    assert skript.pflichtfeld_fuer_phase(conn, 5) == "hauptkonflikt"


def test_felder_fuer_phase_ist_leer_wenn_keine_spalte_passt(conn, monkeypatch):
    _umbenannt(monkeypatch, 5, "Weiss der Himmel")
    assert skript.felder_fuer_phase(conn, 5) == []


def test_phase_szenen_wird_ueber_den_namen_gesucht():
    assert skript.phase_szenen() == phasen.nummer_fuer("Szenen")


# --- Zielzustaende --------------------------------------------------------


def test_begriffe_und_fragen(conn):
    schritt = skript.schritt_fuer("begriffe")
    assert not schritt.fertig(conn, 1, {})
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof")
    assert schritt.fertig(conn, 1, {})

    schritt = skript.schritt_fuer("fragen")
    assert not schritt.fertig(conn, 1, {})
    repo.setze_arbeitsstand(conn, 1, "fragen", "Koffer: Was war drin?")
    assert schritt.fertig(conn, 1, {})


def test_figuren_erst_ab_drei(conn):
    schritt = skript.schritt_fuer("figuren")
    for name in ("Meryem", "Ferzan"):
        repo.setze_figur(conn, 1, name, "eine Frau")
        assert not schritt.fertig(conn, 1, {})
    repo.setze_figur(conn, 1, "Aynur", "eine dritte")
    assert schritt.fertig(conn, 1, {})


def test_interviews_zaehlen_verdichtungen(conn):
    schritt = skript.schritt_fuer("interviews")
    merker = {"interviews_soll": 2}
    assert not schritt.fertig(conn, 1, merker)
    for i in range(2):
        aufnahme_id = repo.lege_aufnahme_an(conn, 1, 100 + i, "lang", "text")
        repo.speichere_verdichtung(conn, 1, aufnahme_id, "Zusammenfassung", [])
    assert schritt.fertig(conn, 1, merker)


def test_phase_mitte_prueft_das_pflichtfeld_der_phase(conn):
    """Gesetzte ``geschichte`` genuegt -- der Simulator liest das Pflichtfeld
    aus dem Schema, also zieht er nach dem Umbau vom 05.09.2026 nachts von
    selbst mit."""
    schritt = skript.schritt_fuer("phase_mitte")
    assert not schritt.fertig(conn, 1, {})
    repo.setze_arbeitsstand(conn, 1, "format", "Musical: Dialog, Lied, Rap")
    assert not schritt.fertig(conn, 1, {}), "das Format zaehlt nicht mehr"
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.")
    assert schritt.fertig(conn, 1, {})


def test_phase_mitte_faellt_ohne_feld_auf_die_phase_zurueck(conn, monkeypatch):
    monkeypatch.setattr(skript, "felder_fuer_phase", lambda conn, nummer: [])
    schritt = skript.schritt_fuer("phase_mitte")
    assert not schritt.fertig(conn, 1, {})
    phasen.setze(conn, 1, skript.PHASE_MITTE, "test")
    assert schritt.fertig(conn, 1, {})


def test_szene_braucht_einen_volltext(conn):
    schritt = skript.schritt_fuer("szene")
    repo.lege_szene_an(conn, 1, 1, "Am Bahnhof", "kurz", "")
    assert not schritt.fertig(conn, 1, {})
    repo.lege_szene_an(conn, 1, 2, "In der Kueche", "kurz", "MERYEM: Hallo.")
    assert schritt.fertig(conn, 1, {})


def test_korrektur_verlangt_eine_figur_weniger(conn):
    schritt = skript.schritt_fuer("korrektur")
    repo.setze_figur(conn, 1, "Meryem", "eine Frau")
    repo.setze_figur(conn, 1, "Ferzan", "noch eine")
    merker = {"figuren_vorher": 2}
    assert not schritt.fertig(conn, 1, merker)
    repo.entferne_figur(conn, 1, "Ferzan")
    assert schritt.fertig(conn, 1, merker)


def test_ziel_text_fuellt_die_platzhalter():
    schritt = skript.schritt_fuer("korrektur")
    text = schritt.ziel_text({
        "falscher_name": "Meryem", "richtiger_name": "Rukiye", "figur_weg": "Ayla",
    })
    assert "Meryem" in text and "Rukiye" in text and "Ayla" in text
    assert "{" not in text


# --- Der heutige Phasenstand (30.09.2026) ---------------------------------


def test_das_tag2_skript_faehrt_jede_phase_genau_einmal_an():
    """Sieben Phasen, sechs Phasenschritte (in die erste kommt niemand per
    Knopf). Eine achte Phase soll dieses Skript nicht mitreissen -- deshalb
    gegen ``phasen.PHASEN`` geprueft und nicht gegen eine Zahl."""
    nummern = [s.phase_nummer for s in skript.SCHRITTE_TAG2 if s.art == "phase"]
    assert nummern == [n for n, _k, _b in phasen.PHASEN][1:]


def test_die_konstanten_heissen_wie_die_phasen_heute():
    assert phasen.kurzname(skript.PHASE_SCHAERFUNG).startswith("Schaerfung")
    assert skript.PHASE_SETTING == skript.PHASE_GESCHICHTE
    assert phasen.kurzname(skript.PHASE_SETTING) == phasen.kurzname(4)
    # Die frueheren Namen "Szenentexte"/"Durchlauf" gibt es nicht mehr.
    assert not hasattr(skript, "PHASE_SZENENTEXTE")
    assert not hasattr(skript, "PHASE_DURCHLAUF")
    assert phasen.kurzname(skript.PHASE_PROSA) == phasen.kurzname(6)
    assert phasen.kurzname(skript.PHASE_FEINSCHLIFF) == phasen.kurzname(7)


def test_der_titel_von_phase_mitte_nennt_seine_eigene_phase():
    """``Schritt("phase_mitte", "Phase 5", ...)`` bei ``PHASE_MITTE == 4`` war
    der Befund vom 30.09.2026 -- der Titel steht im Lauf-Protokoll und im
    Bericht, und wer dort "Phase 5" liest, glaubt, Phase 5 sei gemessen."""
    titel = skript.schritt_fuer("phase_mitte").titel
    assert str(skript.PHASE_MITTE) in titel
    assert "Phase 5" not in titel


def test_der_festlegungsschritt_liegt_zwischen_setting_und_geschichte():
    schluessel = [s.schluessel for s in skript.SCHRITTE_TAG2]
    assert schluessel.index("setting") < schluessel.index("festlegungen")
    assert schluessel.index("festlegungen") < schluessel.index("geschichte")


def test_das_ziel_des_festlegungsschritts_nennt_alle_pruefsaetze():
    schritt = skript.schritt_fuer("festlegungen", skript.SCHRITTE_TAG2)
    ziel = schritt.ziel_text({
        "festlegungsproben": skript.festlegungsproben_text(),
    })
    for _bereich, _stichwort, satz in skript.FESTLEGUNGSPROBEN:
        assert satz in ziel


def test_der_festlegungsschritt_ist_erst_fertig_wenn_alles_dauerhaft_liegt(conn):
    from interview_theater import repo

    schritt = skript.schritt_fuer("festlegungen", skript.SCHRITTE_TAG2)
    assert schritt.fertig(conn, 1, {}) is False
    for bereich, _stichwort, satz in skript.FESTLEGUNGSPROBEN:
        repo.schreibe_festlegung(conn, 1, bereich, satz)
    assert schritt.fertig(conn, 1, {}) is True


def test_der_merker_liefert_die_pruefsaetze(conn, einst):
    """``ziel_text`` faellt mit ``KeyError`` aus, wenn der Platzhalter fehlt --
    und zwar mitten im Lauf, nach dem ersten bezahlten Modellaufruf."""
    from simulation import lauf as lauf_modul
    from simulation.attrappe import TelegramAttrappe

    durchlauf = lauf_modul.Lauf(
        conn, TelegramAttrappe(), None, einst, None,
        gezogene=[], seed=1, schritte=[],
    )
    merker = durchlauf._merker()
    assert "festlegungsproben" in merker
    for schritt in skript.SCHRITTE_TAG2:
        schritt.ziel_text(merker)   # darf nicht werfen


def test_skript_schalter_waehlt_die_liste():
    from scripts import simulation as sim

    args = sim.baue_argumente(["--set", "1"])
    assert sim._schritte(args) is skript.SCHRITTE
    args = sim.baue_argumente(["--set", "1", "--skript", "tag2"])
    assert sim._schritte(args) is skript.SCHRITTE_TAG2
    args = sim.baue_argumente(["--set", "1", "--skript", "tag2", "--ohne-szene"])
    assert all(s.art != "szene" for s in sim._schritte(args))


def test_mutation_geht_in_den_mischungsnamen():
    from scripts import simulation as sim

    args = sim.baue_argumente(["--set", "1"])
    assert sim.mischungsname(args) == "set1"
    args = sim.baue_argumente(["--set", "1", "--mutation", "festlegung_verloren"])
    assert sim.mischungsname(args) == "set1-festlegung_verloren"


def test_eine_unbekannte_mutation_wird_vom_parser_abgelehnt():
    from scripts import simulation as sim

    with pytest.raises(SystemExit):
        sim.baue_argumente(["--set", "1", "--mutation", "gibtsnicht"])
