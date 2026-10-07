"""Der Phasenwechsel stoesst die Summary-Erzeugung der VERLASSENEN Phase an
-- an jeder Stelle, die ``phasen.setze`` erfolgreich aufruft und ein
Sprachmodell kennt (Karte t_1bc96848): ``befehle.wechsle_phase``, der Knopf
"Weiter zu Phase N" (``knoepfe.wirkung._wirkung_phase``), "Ja, speichern"
(``knoepfe.stationen.uebergang_nach_speichern``), der automatische Sprung
5->6 (``entwurf.bestaetige_szene``), der automatische Sprung 6->7
(``ueberarbeitung.schliesse_6_ab``) und ein Phasenwunsch im freien Chat
(``erkenner.laufe``).

Gemessen wird nur, DASS ``phasen_summary.starte_wenn_aktiv`` mit der
richtigen (chat_id, verlassene Phase) aufgerufen wird -- die Erzeugung
selbst ist in tests/test_phasen_summary.py gemessen. ``starte_wenn_aktiv``
ist dabei durchgehend eine Attrappe: ein echter Aufruf braucht ein
Sprachmodell und laeuft in einem Thread, das ist hier nicht die Frage.
"""

import pytest

from interview_theater import (
    befehle, entwurf, erkenner, knoepfe, phasen, phasen_summary, repo, ueberarbeitung,
)

from test_knoepfe import TelegramAttrappe, _druck


class KLMSentinel:
    """Steht nur dafuer, dass ueberhaupt ein Sprachmodell da ist --
    ``starte_wenn_aktiv`` ist in jedem Test hier eine Attrappe und ruft es
    nie wirklich auf."""


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture(autouse=True)
def aufgezeichnet(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(
        phasen_summary, "starte_wenn_aktiv",
        lambda conn, klm, e, chat_id, phase: aufrufe.append((chat_id, phase)),
    )
    return aufrufe


def test_wechsle_phase_meldet_die_verlassene_phase(conn, einst, tg, aufgezeichnet):
    repo.setze_phase(conn, 1, 2)
    befehle.wechsle_phase(conn, tg, KLMSentinel(), einst, 1, 3, quelle="befehl")
    assert (1, 2) in aufgezeichnet


def test_wechsle_phase_ruft_nichts_auf_ohne_aenderung(conn, einst, tg, aufgezeichnet):
    repo.setze_phase(conn, 1, 3)
    befehle.wechsle_phase(conn, tg, KLMSentinel(), einst, 1, 3, quelle="befehl")
    assert aufgezeichnet == []


def test_knopf_weiter_zu_phase_meldet_die_verlassene_phase(conn, einst, tg, aufgezeichnet):
    repo.setze_phase(conn, 1, 2)
    knoepfe.biete_phase(conn, tg, 1, "Weiter?", 3)
    daten = tg.knoepfe[-1][2][0][1]
    knoepfe.behandle(conn, tg, KLMSentinel(), einst, _druck(daten))
    assert (1, 2) in aufgezeichnet


def test_ja_speichern_meldet_die_verlassene_phase(conn, einst, tg, aufgezeichnet, monkeypatch):
    repo.setze_phase(conn, 1, 2)
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Heimat, Grenze")
    monkeypatch.setattr(phasen, "naechste_moegliche", lambda conn_, chat_id: 3)
    from interview_theater.knoepfe import stationen

    monkeypatch.setattr(stationen, "eintritt_in_phase", lambda *a, **k: None)

    stationen.uebergang_nach_speichern(conn, tg, KLMSentinel(), einst, 1)

    assert (1, 2) in aufgezeichnet


def test_entwurf_bestaetige_szene_meldet_phase_5_als_verlassen(
    conn, einst, tg, aufgezeichnet, monkeypatch,
):
    repo.setze_phase(conn, 1, 5)
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    monkeypatch.setattr(entwurf, "erste_offene_szene", lambda conn_, chat_id: None)
    monkeypatch.setattr(knoepfe, "eintritt_in_phase", lambda *a, **k: None)

    entwurf.bestaetige_szene(conn, tg, KLMSentinel(), einst, 1, 1)

    assert (1, 5) in aufgezeichnet


def test_ueberarbeitung_schliesse_6_ab_meldet_phase_6_als_verlassen(
    conn, einst, tg, aufgezeichnet, monkeypatch,
):
    repo.setze_phase(conn, 1, 6)
    from interview_theater import knoepfe as knoepfe_modul

    monkeypatch.setattr(knoepfe_modul, "eintritt_in_phase", lambda *a, **k: None)

    ueberarbeitung.schliesse_6_ab(conn, tg, KLMSentinel(), einst, 1)

    assert (1, 6) in aufgezeichnet


def test_erkenner_phase_setzen_im_chat_meldet_die_verlassene_phase(
    conn, einst, tg, aufgezeichnet,
):
    repo.setze_phase(conn, 1, 2)
    repo.merke_nachricht(conn, 1, 1, "Gruppe", 0, "text", "Let's move to phase 3",
                         repo._jetzt())

    class KLMAttrappe:
        def schema(self, chat_id, system, nutzer, schema, art, modell=None,
                  temperature=None):
            return {"aenderungen": [{"art": "phase_setzen", "wert": "3"}]}

    erkenner.laufe(KLMAttrappe(), tg, conn, einst, 1)

    assert (1, 2) in aufgezeichnet
