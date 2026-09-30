"""Schaerfung und Szenenfolge laufen nie gleichzeitig (30.09.2026, C7).

Der gemessene Fall steht in docs/analyse-phase5-chaos-2026-09-06.md
Abschnitt 2: 13:53:42 Schaerfung, 13:54:10 Szenenfolge fertig, 13:54:20
naechste Schaerfung, 13:54:37 Szenenspeicherung. Zwei Fragestraenge in
demselben Chatfenster.

Drei Nachweise, alle deterministisch (Events, keine Schlafzeiten) und ohne
Netz:

(a) der zweite Auftrag startet KEINEN zweiten Modellaufruf, solange der erste
    laeuft,
(b) er laeuft nach dem Ende des ersten GENAU EINMAL,
(c) die Gruppe bekommt sofort eine freundliche Wartemeldung.
"""

import threading

import pytest

from interview_theater import (
    phasen, repo, schaerfung, szenenfolge, vorschlagssperre,
)

from test_knoepfe import TelegramAttrappe
from test_schaerfung import ZITAT_A, _interview


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture(autouse=True)
def frische_sperre():
    """Kein Zustand aus einem frueheren Test -- das Register lebt im Modul."""
    vorschlagssperre.vergiss(1)
    yield
    vorschlagssperre.vergiss(1)


class BlockierendesLLM:
    """Ein Modell, das beim ersten Aufruf haengt, bis der Test es loslaesst.

    Es zaehlt ausserdem, wie viele Aufrufe GLEICHZEITIG im Modell stehen --
    das ist der Nachweis (a). Ein Zaehler und nicht eine Messung von Zeit:
    ein Test, der ueber Zeit argumentiert, ist auf einer langsamen Maschine
    ein Falschalarm."""

    def __init__(self):
        self.haltestelle = threading.Event()
        self.drin = threading.Event()
        self.arten = []
        self.gleichzeitig_max = 0
        self._gleichzeitig = 0
        self._zaehlschutz = threading.Lock()

    def _betrete(self, art):
        with self._zaehlschutz:
            self._gleichzeitig += 1
            self.gleichzeitig_max = max(self.gleichzeitig_max, self._gleichzeitig)
            self.arten.append(art)
        self.drin.set()

    def _verlasse(self):
        with self._zaehlschutz:
            self._gleichzeitig -= 1

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self._betrete(art)
        try:
            assert self.haltestelle.wait(timeout=10), "Test hat nie losgelassen"
            return "VORSCHLAG SZENENFOLGE:\nAm Steg — sie treffen sich — Mira — Dialog"
        finally:
            self._verlasse()

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None):
        self._betrete(art)
        try:
            assert self.haltestelle.wait(timeout=10), "Test hat nie losgelassen"
            return {
                "eintrag_nummern": [1], "szenen_nummern": [1],
                "figuren_namen": [""], "begruendungen": ["passt zu Szene 1"],
                "zitate": [ZITAT_A],
            }
        finally:
            self._verlasse()


@pytest.fixture
def lage(conn):
    """Der Stand beim Eintritt in Phase 5: ein ausgewertetes Interview, eine
    Figur, eine Szene, eine Geschichte."""
    _interview(conn, ZITAT_A, [
        {"thema": "Arbeit ohne Anerkennung", "beleg_zitat": ZITAT_A,
         "zitat_geprueft": 1},
    ], name="A")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Treppenhaus, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Im Treppenhaus")
    phasen.setze(conn, 1, 5, "test")
    return conn


def test_schaerfung_wartet_auf_die_laufende_szenenfolge(lage, tg, einst):
    """(a) + (b) + (c) in einem Ablauf -- sie gehoeren zusammen, weil sie
    dieselbe Sekunde beschreiben."""
    conn = lage
    klm = BlockierendesLLM()

    folge = szenenfolge.starte_geschichte_szenen(conn, tg, klm, einst, 1)
    assert folge is not None
    assert klm.drin.wait(timeout=10), "der Szenenfolge-Lauf kam nicht ins Modell"

    vorher = len(tg.texte)
    ergebnis = schaerfung.starte(conn, tg, klm, einst, 1)

    # (a) kein zweiter Modellaufruf, solange der erste steht
    assert klm.gleichzeitig_max == 1
    assert "schaerfung" not in klm.arten
    assert ergebnis == schaerfung.GEMERKT

    # (c) die Wartemeldung steht sofort im Chat
    assert schaerfung.TEXT_GEMERKT in tg.texte[vorher:]

    # (b) nach dem Ende des ersten laeuft sie genau einmal
    klm.haltestelle.set()
    folge.join(timeout=10)
    assert not folge.is_alive()
    # Die nachgeholte Schaerfung laeuft in ihrem eigenen Thread; auf ihr Ende
    # wird ueber dieselbe Sperre gewartet, die sie haelt.
    assert szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()
    assert klm.arten.count("schaerfung") == 1
    assert repo.schaerfungen(conn, 1)


def test_szenenfolge_wartet_auf_die_laufende_schaerfung(lage, tg, einst):
    """Die andere Richtung -- und die ist der Live-Fall: die Schaerfung lief
    aus dem Phaseneintritt, die Szenenfolge kam von der Richtungswahl."""
    conn = lage
    klm = BlockierendesLLM()

    schaerfung_thread = schaerfung.starte(conn, tg, klm, einst, 1)
    assert schaerfung_thread not in (None, schaerfung.GEMERKT)
    assert klm.drin.wait(timeout=10), "die Schaerfung kam nicht ins Modell"

    vorher = len(tg.texte)
    assert szenenfolge.starte_geschichte_szenen(conn, tg, klm, einst, 1) is None
    assert klm.gleichzeitig_max == 1
    assert szenenfolge.ART not in klm.arten
    assert szenenfolge._TEXT_GEMERKT in tg.texte[vorher:]

    klm.haltestelle.set()
    schaerfung_thread.join(timeout=10)
    assert szenenfolge._sperre_fuer(1).acquire(timeout=10)
    szenenfolge._sperre_fuer(1).release()
    assert klm.arten.count(szenenfolge.ART) == 1


def test_die_sperre_haelt_den_szenenlauf_nicht_auf(lage, tg, einst):
    """Die neue Sperre koppelt NUR Schaerfung und Szenenfolge.

    Ein Szenenlauf, der an einem Schaerfungslauf haengt, waere genau die
    gemeinsame Sperre, gegen die AGENTS.md warnt ('eine gemeinsame Sperre
    wuerde den Gespraechszug am Szenenlauf haengen lassen')."""
    from interview_theater import szene

    conn = lage
    klm = BlockierendesLLM()
    schaerfung_thread = schaerfung.starte(conn, tg, klm, einst, 1)
    assert klm.drin.wait(timeout=10)
    # Die Sperre des Szenenlaufs ist frei, obwohl die Schaerfung laeuft.
    assert szene._sperre_fuer(1).acquire(blocking=False)
    szene._sperre_fuer(1).release()
    assert vorschlagssperre.laeuft(1) is True
    klm.haltestelle.set()
    schaerfung_thread.join(timeout=10)


# --- Sperr-Leck: ein Fehler VOR thread.start() darf die Sperre nicht --------
# --- fuer die Prozesslaufzeit belegen (30.09.2026) --------------------------
#
# Vorher lagen Prompt-/Nutzertextbau (``systemanweisung*``, ``baue_nutzertext*``,
# ``ANWEISUNG_FELDER.format``, Thread-Konstruktion) NACH einem erfolgreichen
# ``nimm()``, aber VOR dem ``try``, der bis dahin nur ``thread.start()``
# umschloss. Warf einer dieser Aufrufe, blieb die Sperre fuer die
# Prozesslaufzeit belegt: jeder weitere Vorschlagslauf dieser Gruppe (und mit
# der GEMEINSAMEN Sperre auch der jeweils andere Modultyp) landete nur noch
# auf dem Merkplatz, nie mehr im Modell.


def test_ein_fehler_vor_thread_start_gibt_die_sperre_bei_szenenfolge_frei(
    conn, tg, einst, monkeypatch
):
    """``starte_geschichte_szenen`` wertet ``baue_nutzertext_geschichte`` als
    Thread-Argument aus, also NACH dem ``nimm`` -- genau die Stelle des
    Sperr-Lecks. Mit dem Fix steht das in ``try: ... except BaseException:
    vorschlagssperre.gib_frei(chat_id); raise``, die Sperre ist danach frei."""

    def kaputt(*a, **k):
        raise RuntimeError("Nutzertext kaputt")

    monkeypatch.setattr(szenenfolge, "baue_nutzertext_geschichte", kaputt)

    with pytest.raises(RuntimeError):
        szenenfolge.starte_geschichte_szenen(conn, tg, object(), einst, 1)

    assert vorschlagssperre.laeuft(1) is False
    # Und die Gruppe ist nicht dauerhaft blockiert: ein zweiter Versuch (ohne
    # die Mutation) bekommt die Sperre wieder.
    assert vorschlagssperre.nimm(1) is True
    vorschlagssperre.gib_frei(1)


def test_ein_fehler_vor_thread_start_gibt_die_sperre_bei_schaerfung_frei(
    conn, tg, einst, monkeypatch
):
    """Dieselbe Wache gilt in ``schaerfung.starte``: auch der Thread-Aufbau
    selbst steht dort jetzt unter dem ``try``, nicht nur ``thread.start()``."""

    def kaputter_thread(*a, **k):
        raise RuntimeError("Thread-Bau kaputt")

    monkeypatch.setattr(schaerfung.threading, "Thread", kaputter_thread)

    with pytest.raises(RuntimeError):
        schaerfung.starte(conn, tg, object(), einst, 1)

    assert vorschlagssperre.laeuft(1) is False
    assert vorschlagssperre.nimm(1) is True
    vorschlagssperre.gib_frei(1)
