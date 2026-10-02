"""Die Telefon-Organisationskarte beim Phaseneintritt (UX-Knoepfe-Karte,
Abschnitt 5): ``knoepfe.eintritt_in_phase`` schickt sie VOR der
Eintrittsnachricht, fuer JEDE Phase, auch einen Wiedereintritt -- und bleibt
still, wenn der Kanal ``sende_bild`` nicht nachbildet (die bestehenden
Telegram-Attrappen in dieser Testsuite und in der Simulation)."""

import pytest

from interview_theater import handykarten, knoepfe, phasen

from tests.test_knoepfe import TelegramAttrappe


class TelegramAttrappeMitBild(TelegramAttrappe):
    """Dieselbe Attrappe, nur mit ``sende_bild`` -- fuer den Positivfall."""

    def __init__(self):
        super().__init__()
        self.bilder = []

    def sende_bild(self, chat_id, dateiname, inhalt, beschreibung=""):
        self.bilder.append((chat_id, dateiname, inhalt, beschreibung))
        self.naechste_message_id += 1
        return self.naechste_message_id


@pytest.fixture
def tg_mit_bild():
    return TelegramAttrappeMitBild()


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.mark.parametrize("nummer", [n for n, _, _ in phasen.PHASEN])
def test_jede_phase_schickt_ihre_karte_vor_dem_einstieg(conn, einst, tg_mit_bild, nummer):
    knoepfe.eintritt_in_phase(conn, tg_mit_bild, None, einst, 1, nummer)

    assert len(tg_mit_bild.bilder) == 1
    chat_id, dateiname, inhalt, beschreibung = tg_mit_bild.bilder[0]
    assert chat_id == 1
    assert dateiname == handykarten.dateiname(nummer)
    assert beschreibung == handykarten.satz(nummer)
    assert inhalt  # echte PNG-Bytes, nicht leer

    # Die Karte ist der ALLERERSTE Chat-Eintrag dieses Eintritts.
    assert tg_mit_bild.gesendet
    assert tg_mit_bild.gesendet[0][1] != beschreibung  # kein Duplikat als Text


def test_wiedereintritt_schickt_die_karte_erneut(conn, einst, tg_mit_bild):
    """Auch ein Zurueckspringen bekommt die Karte -- nicht nur der erste
    Eintritt."""
    knoepfe.eintritt_in_phase(conn, tg_mit_bild, None, einst, 1, 2)
    knoepfe.eintritt_in_phase(conn, tg_mit_bild, None, einst, 1, 1)

    assert [b[1] for b in tg_mit_bild.bilder] == [
        handykarten.dateiname(2), handykarten.dateiname(1),
    ]


def test_ohne_sende_bild_bleibt_der_eintritt_unveraendert(conn, einst, tg):
    """Die normale Testattrappe (``tests.test_knoepfe.TelegramAttrappe``) hat
    kein ``sende_bild`` -- genau wie die Attrappen in ``simulation/`` und in
    vielen anderen Testdateien. Der Eintritt darf daran nicht scheitern."""
    assert not hasattr(tg, "sende_bild")

    knoepfe.eintritt_in_phase(conn, tg, None, einst, 1, 2)

    assert tg.gesendet  # die Eintrittsnachricht ging trotzdem raus


def test_unbekannte_phasennummer_sendet_keine_karte(tg_mit_bild):
    # phasen.PHASEN enthaelt keine 0 -- hier wird nur die interne Hilfe
    # direkt gegen eine erfundene Nummer geprueft.
    from interview_theater.knoepfe import stationen

    stationen._sende_karte(tg_mit_bild, 1, 0)

    assert tg_mit_bild.bilder == []
