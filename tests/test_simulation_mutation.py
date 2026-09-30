"""Die zwei Dortmunder Fehler wieder einbauen -- und nachweisen, dass sie
wirklich wieder da sind.

**Warum dieser Test der teuerste Teil der Karte ist.** Ein Mutationslauf
gegen das echte Modell kostet Geld. Greift die Mutation nicht, misst der Lauf
nichts und das Geld ist weg. Diese Tests laufen **vor** jedem bezahlten Lauf
und ohne Netz: sie pruefen den beobachtbaren Zustand vor dem Fix, so wie ihn
die beiden Analysen belegen -- nicht die Abwesenheit einer Funktion.
"""

import pytest

from interview_theater import knoepfe, kontext, phasen, repo, szenenfolge, vorschlagssperre
from simulation import mutation

from test_szenenfolge import TelegramAttrappe


@pytest.fixture(autouse=True)
def freie_vorschlagssperre():
    """Die mutierte Richtungswahl startet ``starte_geschichte_szenen``
    wirklich (chat_id=1) -- kein Zustand aus einem frueheren Test soll die
    gemeinsame Vorschlagssperre besetzt lassen."""
    vorschlagssperre.vergiss(1)
    yield
    vorschlagssperre.vergiss(1)


PROBE = "Das Stueck ist nur EINE Szene, die erste Folge einer Serie."


def test_alle_arten_haben_eine_beschreibung():
    assert set(mutation.BESCHREIBUNG) == set(mutation.ARTEN)
    assert all(mutation.BESCHREIBUNG[a].strip() for a in mutation.ARTEN)


def test_ohne_art_wird_nichts_angefasst():
    vorher = repo.schreibe_festlegung
    with mutation.aktiv(None) as aktiv:
        assert aktiv is None
        assert repo.schreibe_festlegung is vorher


def test_eine_unbekannte_mutation_bricht_ab():
    with pytest.raises(SystemExit):
        with mutation.aktiv("gibtsnicht"):
            pass


# --- Mutation 1: die Auffangtabelle gab es nicht --------------------------


def test_heute_landet_eine_festlegung_in_der_tabelle_und_im_prompt(conn):
    neu = repo.schreibe_festlegung(conn, 1, "struktur", PROBE)
    assert neu is not None
    assert [z["text"] for z in repo.festlegungen(conn, 1)] == [PROBE]
    assert "nur EINE Szene" in kontext._baue_festlegungen(conn, 1)


def test_mutiert_landet_sie_nirgends(conn):
    """Der Zustand vor ``e56a892``: kein Eintrag, kein Prompt-Block, und der
    Aufrufer bekommt dasselbe ``None`` wie bei einer Dublette -- also keine
    Notiert-Zeile."""
    with mutation.aktiv("festlegung_verloren"):
        assert repo.schreibe_festlegung(conn, 1, "struktur", PROBE) is None
        assert repo.festlegungen(conn, 1) == []
        assert kontext._baue_festlegungen(conn, 1) == ""


def test_mutiert_schreibt_auch_der_erkenner_nichts(conn, einst):
    """Ueber den Produktivpfad, nicht ueber ``repo`` direkt: der Erkenner
    ruft ``repo.schreibe_festlegung`` als Modulattribut, also greift der
    Monkey-Patch."""
    from interview_theater import erkenner

    aenderung = [{"art": "festlegung_setzen", "wert": f"struktur: {PROBE}"}]
    with mutation.aktiv("festlegung_verloren"):
        wirkliche = erkenner.wende_an(conn, einst, 1, list(aenderung))
    assert wirkliche == []
    assert repo.festlegungen(conn, 1) == []

    wirkliche = erkenner.wende_an(conn, einst, 1, list(aenderung))
    assert [a["art"] for a in wirkliche] == ["festlegung_setzen"]
    assert len(repo.festlegungen(conn, 1)) == 1


def test_nach_dem_block_ist_der_originalzustand_wieder_da(conn):
    with mutation.aktiv("festlegung_verloren"):
        pass
    assert repo.schreibe_festlegung(conn, 1, "struktur", PROBE) is not None


def test_verschachtelte_mutationen_stellen_erst_am_ende_zurueck(conn):
    mutiert = None
    with mutation.aktiv("festlegung_verloren"):
        mutiert = repo.schreibe_festlegung
        with mutation.aktiv("festlegung_verloren"):
            assert repo.schreibe_festlegung is mutiert
        assert repo.schreibe_festlegung is mutiert
    assert repo.schreibe_festlegung is not mutiert


def test_auch_nach_einer_ausnahme_ist_der_originalzustand_wieder_da(conn):
    """Bricht ein Lauf im Block ab, darf der Betriebscode nicht mutiert
    zurueckbleiben -- sonst liefe der naechste Test (oder Lauf) still mit
    dem Fehler weiter."""
    original = repo.schreibe_festlegung
    with pytest.raises(RuntimeError):
        with mutation.aktiv("festlegung_verloren"):
            assert repo.schreibe_festlegung is not original
            raise RuntimeError("Abbruch mitten im Lauf")
    assert repo.schreibe_festlegung is original
    assert repo.schreibe_festlegung(conn, 1, "struktur", PROBE) is not None
