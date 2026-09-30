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


# --- Mutation 2: die Richtungswahl verliert ihre Szenen --------------------
#
# Die Zeile ist wortgleich die aus tests/test_geschichte.py (RICHTUNG_MIT_SZENEN)
# -- hier absichtlich wiederholt und nicht importiert: dieser Test soll noch
# gelten, wenn dort jemand die Beispielzeile aendert.

RICHTUNG = (
    "Nacht am Kanal — Mira stellt sich, Pal gesteht, am Ende bleiben beide. "
    "Szene 1: Ankunft am Steg. Szene 2: Das Gestaendnis. "
    "Szene 3: Der Morgen danach."
)


class LLMAttrappe:
    """Zaehlt, ob ein Szenenfolge-Lauf angestossen wurde, und was er sah."""

    def __init__(self, antwort=""):
        self.antwort = antwort
        self.aufrufe = 0
        self.arten: list[str] = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.aufrufe += 1
        self.arten.append(art)
        return self.antwort


@pytest.fixture
def erfunden(conn):
    """Der Stand nach Phase 4: Begriffe, Setting, zwei Figuren, Phase 4."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Bahnhof, Winter")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Treppenhaus, nachts")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    repo.setze_figur(conn, 1, "Pal", "haelt an seiner Route fest")
    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", "2026-09-05T23:00:00")
    phasen.setze(conn, 1, 4, "test")
    return conn


def _druecke_richtung(conn, tg, einst, klm, zeile=RICHTUNG):
    knoepfe._wirke(
        conn, tg, klm, einst,
        {"art": knoepfe.ART_GESCHICHTE_SPEICHERN,
         "wert": f"weiter{knoepfe.TRENNER}{zeile}"},
        1,
    )


def test_heute_traegt_die_richtung_ihre_szenen_und_startet_keinen_lauf(
        erfunden, einst):
    conn = erfunden
    tg = TelegramAttrappe()
    klm = LLMAttrappe()
    _druecke_richtung(conn, tg, einst, klm)

    titel = [(s["nummer"], s["titel"]) for s in repo.hole_szenen(conn, 1)]
    assert titel == [
        (1, "Ankunft am Steg"), (2, "Das Gestaendnis"), (3, "Der Morgen danach"),
    ]
    assert klm.aufrufe == 0, "kein zweiter, teurer Folge-Lauf"


def test_mutiert_verliert_die_richtung_ihre_szenen_und_startet_den_lauf(
        erfunden, einst):
    """Der Zustand vor 3ae76ab: keine Szene aus der Zeile, die ganze Zeile im
    Arbeitsstand, und danach ein frischer Szenenfolge-Vorschlag."""
    conn = erfunden
    tg = TelegramAttrappe()
    klm = LLMAttrappe(
        "VORSCHLAG SZENENFOLGE:\n"
        "Am Steg — sie treffen sich — Mira — Dialog\n"
        "Im Flur — sie streiten — Mira, Pal — Dialog\n"
        "Am Morgen — alle gehen — Mira, Pal — Chor\n"
        "Der Kanal — Pal allein — Pal — Monolog\n"
        "Die Bank — Mira wartet — Mira — Monolog\n"
        "Das Ende — beide bleiben — Mira, Pal — Dialog"
    )
    with mutation.aktiv("richtung_ohne_szenen"):
        _druecke_richtung(conn, tg, einst, klm)
        # Der Lauf haengt in einem Thread; auf die Vorschlagssperre warten ist
        # derselbe Weg wie in tests/test_geschichte.py.
        szenenfolge._sperre_fuer(1).acquire(timeout=10)
        szenenfolge._sperre_fuer(1).release()

    assert repo.hole_szenen(conn, 1) == []
    assert "Szene 1" in repo.hole_arbeitsstand(conn, 1)["geschichte"]
    assert klm.aufrufe == 1
    assert klm.arten == [szenenfolge.ART]


def test_mutiert_bleibt_die_reine_formwahl_die_formwahl(erfunden, einst):
    """Die Praezedenz von 3290d70 darf die Mutation nicht mitreissen: eine
    Zeile, die NUR Formen ueber Szenen verteilt, ging schon vor 3ae76ab in
    ``_uebernimm_formwahl``. Eine Mutation, die auch das kaputt macht, wuerde
    zwei Fehler auf einmal messen."""
    conn = erfunden
    tg = TelegramAttrappe()
    with mutation.aktiv("richtung_ohne_szenen"):
        _druecke_richtung(
            conn, tg, einst, LLMAttrappe(),
            "Szene 1: Chor mit Dance. Szene 2: Dialog mit Einschueben. "
            "Szene 3: Rap eskaliert.",
        )
    arten = [z["art"] for z in conn.execute(
        "SELECT art FROM vorfall WHERE chat_id = 1 ORDER BY id"
    )]
    assert "geschichte_war_formwahl" in arten


def test_nach_dem_block_traegt_die_richtung_wieder_ihre_szenen(erfunden, einst):
    conn = erfunden
    with mutation.aktiv("richtung_ohne_szenen"):
        pass
    _druecke_richtung(conn, TelegramAttrappe(), einst, LLMAttrappe())
    assert len(repo.hole_szenen(conn, 1)) == 3
