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

from interview_theater import phasen, repo
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


def test_felder_fuer_phase_folgt_einer_umbenannten_phase(conn, monkeypatch):
    """Bis zum 05.09.2026 hiess Phase 5 'Hauptkonflikt'. Hiesse eine Phase
    morgen wieder so, faende der Simulator die Spalte ``hauptkonflikt`` --
    ohne dass jemand diese Datei anfasst."""
    umbenannt = tuple(
        (n, "Hauptkonflikt" if n == 5 else name, satz)
        for n, name, satz in phasen.PHASEN
    )
    monkeypatch.setattr(phasen, "PHASEN", umbenannt)
    assert skript.felder_fuer_phase(conn, 5) == ["hauptkonflikt"]
    assert skript.pflichtfeld_fuer_phase(conn, 5) == "hauptkonflikt"


def test_felder_fuer_phase_ist_leer_wenn_keine_spalte_passt(conn, monkeypatch):
    umbenannt = tuple(
        (n, "Weiss der Himmel" if n == 5 else name, satz)
        for n, name, satz in phasen.PHASEN
    )
    monkeypatch.setattr(phasen, "PHASEN", umbenannt)
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
