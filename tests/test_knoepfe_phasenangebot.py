"""Proaktiv zur naechsten Phase (06.09.2026, Birk nach der Testgruppe).

Der Befund vom Testabend: neun angebotene Phasenknoepfe, **null Druecke**.
Sie hingen alle als vierter Knopf unter langen Gespraechstexten. Seitdem ist
das Angebot eine eigene, kurze Nachricht -- "<Was steht>. Weiter zu
<Phase>?" mit zwei Knoepfen --, verschickt in dem Moment, in dem die
Voraussetzung gespeichert wird.

Geprueft wird genau das, was daran garantiert ist: sofort, einmal, kurz.
"""

import pytest

from interview_theater import knoepfe, phasen, repo

from tests.test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


def test_angebot_kommt_sobald_die_voraussetzung_steht(conn, tg):
    """Begriffe gespeichert -> Phase 2 ist moeglich -> das Angebot steht da."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Rassismus, Liebe, Spaß, Streit")

    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is True

    _, text, leiste = tg.knoepfe[-1]
    assert "Weiter zu" in text and text.endswith("?")
    assert [b for b, _ in leiste] == [
        f"Weiter zu {phasen.knopfbezeichnung(2)}", "Noch etwas aendern",
    ]


def test_angebot_ist_eine_eigene_kurze_nachricht(conn, tg):
    """Keine Anhaengsel an lange Texte: hoechstens zwei Saetze."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Rassismus, Liebe")

    knoepfe.biete_phase_proaktiv(conn, tg, 1)

    _, text, _ = tg.knoepfe[-1]
    assert len(text) < 120
    assert text.count(".") + text.count("?") <= 2


def test_angebot_kommt_nur_einmal_je_stufe(conn, tg):
    """Der Merkposten ``arbeitsstand.phase_angeboten`` -- aus einem Angebot
    soll kein Draengeln werden."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Rassismus, Liebe")

    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is True
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is False
    assert len(tg.knoepfe) == 1


def test_ohne_moegliche_stufe_bleibt_es_still(conn, tg):
    """Nichts gespeichert, nichts angeboten."""
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is False
    assert tg.gesendet == []


def test_das_angebot_verschluckt_den_prompt_hinweis_nicht_doppelt(conn, tg):
    """EIN Angebot je Stufe, nicht zwei aus zwei Kanaelen: hat der
    Gespraechs-Prompt den Hinweis schon getragen, schweigt die Nachricht."""
    from interview_theater import kontext

    repo.setze_arbeitsstand(conn, 1, "begriffe", "Rassismus, Liebe")
    assert kontext._baue_phasenhinweis(conn, 1) != ""

    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is False


def test_noch_nicht_bleibt_in_der_phase(conn, tg):
    """"Noch nicht" schaltet nicht um und schreibt nichts."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Rassismus, Liebe")
    knoepfe.biete_phase_proaktiv(conn, tg, 1)
    noch_nicht = [
        daten for _, daten in tg.knoepfe[-1][2]
        if repo.hole_knopf(conn, int(daten.split(":")[1]))["art"]
        == knoepfe.ART_NOCH_NICHT
    ][0]

    knoepfe.behandle(conn, tg, None, None, _druck(noch_nicht))

    assert phasen.aktuelle(conn, 1) == 1


def test_weiter_knopf_schaltet_um(conn, tg):
    """Die Gegenprobe: der linke Knopf tut, was draufsteht."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Rassismus, Liebe")
    knoepfe.biete_phase_proaktiv(conn, tg, 1)
    weiter = [
        daten for _, daten in tg.knoepfe[-1][2]
        if repo.hole_knopf(conn, int(daten.split(":")[1]))["art"]
        == knoepfe.ART_PHASE
    ][0]

    knoepfe.behandle(conn, tg, None, None, _druck(weiter))

    assert phasen.aktuelle(conn, 1) == 2
