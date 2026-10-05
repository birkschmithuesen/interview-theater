"""Karte t_cb2c4678, Teil 2, und Birks Entscheidung vom 05.10.2026.

Bis 04.10.2026 (Birk 14:50, "Zwischenstand und Endstand muessen nicht
anders behandelt werden") hing der Ende-Schnitt ("Discussion done") wie ein
Pausenschnitt an der Board-Schwelle (600 Zeichen). Live am 05.10.2026
(Gruppe 2: 298 Zeichen, kein Lauf) ersetzt: nach "Discussion done" laeuft
das Board IMMER, sobald es ungelesenes Transkript gibt -- ohne Schwelle, ohne
Mindestabstand. Zwischenlaeufe behalten ihre Regel. Laeuft gerade ein Lauf,
wird nach ihm neu entschieden. Nur erfundenes Material."""

import inspect
import threading
import time

import pytest

from interview_theater import (aufnahme, begriffsboard, brainstorm, db,
                               einstellungen, repo, workshop)
from interview_theater import diskussion

CHAT = 1
KURZ = "Heimat und Grenze."
LANG = "Heimat und Grenze und Mut. " * 12   # 324 Zeichen
HEIMAT = {"begriff": "Heimat", "nennungen": 2, "zustimmung": 2, "begruendung": "Weil Heimat.",
          "zitat": "", "doppelbedeutung": "", "status": "favorit"}
GRENZE = dict(HEIMAT, begriff="Grenze", begruendung="Weil Grenze.", status="kandidat")


@pytest.fixture(autouse=True)
def aktiv(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(diskussion, "starte", lambda *a, **k: None)
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ABSTAND_S", "1")


@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


class _TG:
    def __init__(self):
        self.gesendet, self.mit_knoepfen, self._id = [], [], 900

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self._id += 1
        return self._id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        mid = self.sende(chat_id, text)
        self.mit_knoepfen.append((chat_id, text, list(knoepfe_)))
        return mid

    # Wie ``tests/test_begriffsboard_vorschlag.py::_TG`` -- falls der
    # Vorschlagsweg sie beruehrt.
    def beantworte_knopf(self, callback_query_id, text=""):
        pass

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    def tippt(self, chat_id):
        pass


class _KLM:
    """Liefert der Reihe nach ``boards``; der erste Aufruf wartet auf ``halt``."""

    def __init__(self, *boards, halt=None):
        self.boards, self.halt, self.aufrufe = list(boards), halt, 0

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        self.aufrufe += 1
        if self.halt is not None and self.aufrufe == 1:
            self.halt.wait(5)
        return {"board": self.boards.pop(0) if self.boards else []}


def _zeile(conn, message_id, schnittgrund, text=KURZ):
    aid = repo.lege_aufnahme_an(conn, CHAT, message_id, "kurz", "sprache", status="transkribiert",
                                diskussion=True, schnittgrund=schnittgrund)
    repo.setze_transkript(conn, aid, text)
    # ``diskussion_transkript`` liest nur status='fertig' -- normalerweise
    # setzt ``_diskussion_abschliessen`` das; fuer eine Zeile, die direkt an
    # ``begriffsboard.starte`` geht (ohne den Weg ueber ``_kurz_abschliessen``
    # zu nehmen), muss der Test es selbst tun, sonst liest der Lauf ein
    # leeres Transkript und ruft nie ein Modell.
    repo.setze_status(conn, aid, "fertig")
    repo.merke_nachricht(conn, CHAT, message_id, "Gruppe", 0, "sprache", None, repo._jetzt(), 1)
    return repo.hole_aufnahme(conn, aid)


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


def test_soll_laufen_kennt_keinen_abschluss_mehr():
    assert list(inspect.signature(begriffsboard.soll_laufen).parameters) == ["conn", "chat_id"]


def test_ende_schnitt_laeuft(conn, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")
    _zeile(conn, 10, "ende")
    assert begriffsboard.soll_laufen(conn, CHAT) is True


def _pruefe_ende_laeuft_ohne_schwelle(conn, einst):
    """Ende-Schnitt mit 18 Zeichen: unter der Board-Schwelle (1000) UND unter
    der Abschluss-Schwelle des Brainstorms (1000) -- der Lauf kommt trotzdem,
    und danach der Vorschlag mit seinem Board."""
    klm, tg = _KLM([HEIMAT]), _TG()
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, _zeile(conn, 20, "ende"),
                                aufnahme._kein_zug, False)
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    assert klm.aufrufe == 1
    assert "1. Heimat" in tg.mit_knoepfen[0][1]


def test_ende_laeuft_ohne_schwelle(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "1000")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "1000")
    _pruefe_ende_laeuft_ohne_schwelle(conn, einst)


def test_mutant_mit_der_regel_vom_04_10_faellt_durch(conn, einst, monkeypatch):
    """Mutant: wer die Regel vom 04.10.2026 zurueckbringt (Ende-Schnitt wie
    ein Pausenschnitt an ``min_zeichen``), muss den Test oben rot machen."""
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "1000")

    def regel_vom_04_10(conn_, chat_id):
        stand = repo.begriffsboard_stand(conn_, chat_id)
        return brainstorm.soll_reagieren(
            unreagierte_zeichen=stand["unreagierte_zeichen"],
            sekunden_seit_letzter_reaktion=float("inf"),
            letzter_schnittgrund="pause", ist_abschluss=False,
            min_zeichen_override=begriffsboard.min_zeichen(),
        )

    monkeypatch.setattr(begriffsboard, "soll_laufen", regel_vom_04_10)
    with pytest.raises(AssertionError):
        _pruefe_ende_laeuft_ohne_schwelle(conn, einst)


def test_mutant_mit_dem_alten_abschlusszweig_faellt_durch(conn, einst, monkeypatch):
    """Mutant: der noch aeltere Zweig (``ist_abschluss=True`` mit
    ``min_zeichen_bei_abschluss``) macht den Test oben ebenfalls rot."""
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "1000")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "1000")

    def alter_zweig(conn_, chat_id):
        stand = repo.begriffsboard_stand(conn_, chat_id)
        return brainstorm.soll_reagieren(
            unreagierte_zeichen=stand["unreagierte_zeichen"],
            sekunden_seit_letzter_reaktion=0.0,
            letzter_schnittgrund="ende", ist_abschluss=True,
        )

    monkeypatch.setattr(begriffsboard, "soll_laufen", alter_zweig)
    with pytest.raises(AssertionError):
        _pruefe_ende_laeuft_ohne_schwelle(conn, einst)


def test_ende_ignoriert_den_mindestabstand_ein_pausenschnitt_nicht(conn, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "10")
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ABSTAND_S", "3600")
    a = _zeile(conn, 30, "pause")
    repo.lege_begriffsboard_an(conn, CHAT, "[]", "sovereign", a["id"])
    _zeile(conn, 31, "pause")
    assert begriffsboard.soll_laufen(conn, CHAT) is False   # gleich nach einem Lauf
    _zeile(conn, 32, "ende")
    assert begriffsboard.soll_laufen(conn, CHAT) is True    # am Ende: nichts mehr aufschieben


def test_vorschlag_wartet_auf_den_laufenden_lauf_und_zeigt_dessen_board(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "1000")   # fuer Zwischenlaeufe zu wenig
    _zeile(conn, 40, "pause")
    halt = threading.Event()
    klm, tg = _KLM([HEIMAT], halt=halt), _TG()
    assert begriffsboard.starte(conn, klm, einst, CHAT) is True
    _warte_bis(lambda: klm.aufrufe == 1)
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, _zeile(conn, 41, "ende"),
                                aufnahme._kein_zug, False)
    time.sleep(0.1)
    assert tg.gesendet == [] and tg.mit_knoepfen == []       # noch nicht: es laeuft einer
    halt.set()
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    assert "1. Heimat" in tg.mit_knoepfen[0][1]
    # Seit 05.10.2026: der kurze Rest des Ende-Segments wird nach dem
    # laufenden Lauf trotzdem gelesen (zweiter Lauf, liefert hier nichts --
    # ein leeres Ergebnis ersetzt kein volles Board).
    assert klm.aufrufe == 2


def test_rest_ueber_der_schwelle_wird_nach_dem_laufenden_lauf_gelesen(conn, einst, monkeypatch):
    monkeypatch.setenv("IT_BEGRIFFSBOARD_MIN_ZEICHEN", "100")
    _zeile(conn, 50, "pause", LANG)
    halt = threading.Event()
    klm, tg = _KLM([HEIMAT], [HEIMAT, GRENZE], halt=halt), _TG()
    assert begriffsboard.starte(conn, klm, einst, CHAT) is True
    _warte_bis(lambda: klm.aufrufe == 1)
    aufnahme._kurz_abschliessen(conn, tg, klm, einst, _zeile(conn, 51, "ende", LANG),
                                aufnahme._kein_zug, False)
    halt.set()
    _warte_bis(lambda: len(tg.mit_knoepfen) == 1)
    assert klm.aufrufe == 2
    assert "Grenze" in tg.mit_knoepfen[0][1]


def test_merke_falls_laeuft():
    gerufen = []
    assert begriffsboard.merke_falls_laeuft(99, lambda: gerufen.append(1)) is False
    assert begriffsboard.nimm_oder_merke(99, None) is True
    assert begriffsboard.merke_falls_laeuft(99, lambda: gerufen.append(2)) is True
    begriffsboard._rufe(begriffsboard.beende(99))
    assert gerufen == [2]
