"""Abnahme P3-4 A3 Nachtrag (06.10.2026): der Knopf "Weiter zu Phase N"
(``ART_PHASE``, ``knoepfe.wirkung._wirkung_phase``) ruft ``phasen.setze``
direkt auf und lief bisher NICHT durch ``befehle.wechsle_phase`` -- ein
offenes Interview blieb ueber diesen Weg verwaist stehen (siehe
``befehle.schliesse_offenes_interview_vor_phasenwechsel``, der jetzt
gemeinsame Waechter fuer alle vier Phasenwechselwege).

Harness wiederverwendet statt verdoppelt: ``TelegramAttrappe``/
``LLMAttrappe``/``interview_an`` aus tests/test_befehle_phasenwechsel_interview.py
(system-Flag inklusive), ``_druck`` aus tests/test_knoepfe.py -- dieselbe
Bauart wie tests/test_knoepfe_phasenangebot.py (importiert dort aus
tests/test_knoepfe.py)."""

import pytest

from interview_theater import knoepfe, phasen, repo, workshop
from interview_theater.knoepfe import texte

from tests.test_befehle_phasenwechsel_interview import LLMAttrappe, TelegramAttrappe, interview_an
from tests.test_knoepfe import _druck

CHAT = 1


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def klm():
    return LLMAttrappe()


def _druecke_phasenknopf(conn, tg, klm, einst, chat_id: int, nummer: int) -> None:
    knopf_id = repo.lege_knopf_an(conn, chat_id, texte.ART_PHASE, str(nummer))
    knoepfe.behandle(conn, tg, klm, einst, _druck(f"k:{knopf_id}", chat_id=chat_id))


def test_phasenknopf_ab_4_schliesst_offenes_interview(conn, einst, tg, klm):
    kopf_id = interview_an(conn)
    phasen.setze(conn, CHAT, 3, "befehl")
    assert repo.ist_interviewmodus_an(conn, CHAT) is True
    tg.gesendet.clear()

    _druecke_phasenknopf(conn, tg, klm, einst, CHAT, 4)

    assert phasen.aktuelle(conn, CHAT) == 4
    assert repo.ist_interviewmodus_an(conn, CHAT) is False
    treffer = [(t, s) for _c, t, s in tg.gesendet if "beendet" in t]
    assert treffer, tg.gesendet
    # Kein Web-/Fliesstext-Kanal -- gewoehnliche Nachricht, keine Systemzeile
    # (Gegenprobe mit ``system=True``: Test unten unter Padua-Fliesstext).
    assert all(s is False for _t, s in treffer), treffer


def test_phasenknopf_unter_4_laesst_offenes_interview_unberuehrt(conn, einst, tg, klm):
    kopf_id = interview_an(conn)
    phasen.setze(conn, CHAT, 1, "befehl")
    tg.gesendet.clear()

    _druecke_phasenknopf(conn, tg, klm, einst, CHAT, 2)

    assert phasen.aktuelle(conn, CHAT) == 2
    assert repo.ist_interviewmodus_an(conn, CHAT) is True
    assert not any("beendet" in t for _c, t, _s in tg.gesendet)


def test_phasenknopf_ab_4_unter_padua_fliesstext_meldet_mit_system_true(
    conn, einst, tg, klm, monkeypatch
):
    """Wie oben, aber Padua/Web (``[interview] fliesstext``, tests/
    test_interview_fliesstext.py): die Meldung geht als Systemzeile in
    dieselbe Transkriptblase statt als eigene Chatnachricht."""
    monkeypatch.setattr(workshop, "interview_fliesstext", lambda profil=None: True)
    repo.setze_gruppe_kanal(conn, CHAT, "web")
    kopf_id = interview_an(conn)
    phasen.setze(conn, CHAT, 3, "befehl")
    tg.gesendet.clear()

    _druecke_phasenknopf(conn, tg, klm, einst, CHAT, 4)

    assert repo.ist_interviewmodus_an(conn, CHAT) is False
    treffer = [(t, s) for _c, t, s in tg.gesendet if "beendet" in t]
    assert treffer, tg.gesendet
    assert all(s is True for _t, s in treffer), treffer
