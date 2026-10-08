"""Padua Quickfix 08.10.2026 (Befund G1, web_post 2390-2394): nach "No,
change" auf einer Stage-Script-Szene nahm der Bot die naechste Nachricht
blind als neue Aenderungsnotiz -- auch wenn sie erkennbar eine FRAGE war
("did you create szene 1 already sfinakl script?"). Die Gruppe bekam eine
neu geschriebene Szene statt einer Antwort auf ihre Frage.

``stagescript.aendere`` ist der EINE Weg, ueber den sowohl der Knopf-Pfad
(``ablauf._szene_hat_vorfahrt`` -> ``ueberarbeitung.ueberarbeite``) als auch
der Erkenner-Pfad in Phase 7/Kartenprofil neu schreiben -- hier sitzt die
Klaerung. Kein Netz, kein Modell: eine Nachricht an ein Modell waere ein
Mutant, der durch die Spione unten sichtbar wird."""

import json

import pytest

from interview_theater import repo, stagescript, szenenfolge

from test_stagescript import _karten
from test_szenenkarte import TG, padua  # noqa: F401


@pytest.fixture(autouse=True)
def _regienotiz_leer():
    """Prozessspeicher wie ``szenenfolge._regienotiz_erwartet`` ueberlebt den
    Test (kein DB-Zustand) -- Chat 1 wird auch anderswo benutzt (siehe
    ``conftest._web_grenze_leer`` fuer dasselbe Problem)."""
    szenenfolge.nimm_regienotiz(1)
    yield
    szenenfolge.nimm_regienotiz(1)


@pytest.fixture
def tg():
    return TG()


class LLMSpion:
    """Zaehlt jeden Modellaufruf -- eine Klaerung darf ihn nie ausloesen."""

    def __init__(self):
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe.append({"art": art, "nutzer": nutzer})
        return {"text": "NEU GESCHRIEBEN", "kopf": ""}


def _bereite_offene_szene(conn):
    """Szene 1 ist geschrieben, aber nicht abgenommen -- der "No, change"-
    Zustand, den ``_wirkung_szene_anders`` / ``ueberarbeitung.ueberarbeite``
    antreffen."""
    ids = _karten(conn)
    repo.setze_stagescript(conn, ids[0], "EMMA: Home alone.", None)
    return ids


def test_frage_wird_nicht_neu_geschrieben(conn, einst, padua, tg):
    """Die reale G1-Nachricht: eine Frage nach dem Stand, keine Notiz."""
    ids = _bereite_offene_szene(conn)
    klm = LLMSpion()

    ergebnis = stagescript.aendere(
        conn, tg, klm, einst, 1,
        "did you create szene 1 already sfinakl script?", nummer=1)

    assert ergebnis is None
    assert klm.aufrufe == []
    assert repo.hole_szene(conn, ids[0])["volltext"] == "EMMA: Home alone."
    # Stand (ja/nein) + Rueckfrage, was sich aendern soll -- Italienisch wie
    # jede andere Statuszeile aus ``stagescript.py`` (Morgen-Auftrag 4).
    assert any("scena 1" in t and "già" in t for t in tg.texte)
    assert any("Cosa deve cambiare" in t for t in tg.texte)


def test_italienische_frage_wird_nicht_neu_geschrieben(conn, einst, padua, tg):
    """Dieselbe Frage auf Italienisch -- die Gruppen G1-G3 schreiben in
    Phase 6/7 italienisch (Morgen-Auftrag 4)."""
    ids = _bereite_offene_szene(conn)
    klm = LLMSpion()

    ergebnis = stagescript.aendere(
        conn, tg, klm, einst, 1, "la scena 1 è già pronta?", nummer=1)

    assert ergebnis is None
    assert klm.aufrufe == []
    assert repo.hole_szene(conn, ids[0])["volltext"] == "EMMA: Home alone."


def test_echte_aenderung_schreibt_weiterhin_neu(conn, einst, padua, tg):
    """Mutationsprobe: eine echte Regie-Notiz darf nicht ploetzlich auch
    blockiert werden."""
    ids = _bereite_offene_szene(conn)
    klm = LLMSpion()

    faden = stagescript.aendere(
        conn, tg, klm, einst, 1, "weniger regieanweisungen, reduziere um 80%", nummer=1)
    faden.join(5)

    aufrufe = [a for a in klm.aufrufe if a["art"] == stagescript.ART]
    assert len(aufrufe) == 1
    assert "weniger regieanweisungen" in aufrufe[0]["nutzer"]
    assert repo.hole_szene(conn, ids[0])["volltext"] == "NEU GESCHRIEBEN"


def test_annulla_beendet_ohne_neu_zu_schreiben(conn, einst, padua, tg):
    ids = _bereite_offene_szene(conn)
    klm = LLMSpion()

    ergebnis = stagescript.aendere(conn, tg, klm, einst, 1, "annulla", nummer=1)

    assert ergebnis is None
    assert klm.aufrufe == []
    assert repo.hole_szene(conn, ids[0])["volltext"] == "EMMA: Home alone."
    assert any("non cambio la scena 1" in t for t in tg.texte)


@pytest.mark.parametrize("notiz", ["skip", "cancel", "Skip.", "CANCEL!"])
def test_weitere_abbruch_woerter(conn, einst, padua, tg, notiz):
    ids = _bereite_offene_szene(conn)
    klm = LLMSpion()

    ergebnis = stagescript.aendere(conn, tg, klm, einst, 1, notiz, nummer=1)

    assert ergebnis is None
    assert klm.aufrufe == []
    assert repo.hole_szene(conn, ids[0])["volltext"] == "EMMA: Home alone."


def test_aenderungsmodus_bleibt_offen_nach_klaerung(conn, einst, padua, tg):
    """Nach der Klaerung soll die naechste Nachricht WEITERHIN als
    Regie-Notiz gelten -- der Modus ist nicht zu Ende, nur die Frage war
    keine Notiz. Mutant: ohne das erneute ``erwarte_regienotiz`` bleibt die
    naechste Nachricht ungebunden."""
    from interview_theater import szenenfolge

    _bereite_offene_szene(conn)
    klm = LLMSpion()

    stagescript.aendere(conn, tg, klm, einst, 1, "did you write it yet?", nummer=1)

    assert szenenfolge.nimm_regienotiz(1) == 1


def test_leere_notiz_gilt_als_unklar(conn, einst, padua, tg):
    ids = _bereite_offene_szene(conn)
    klm = LLMSpion()

    ergebnis = stagescript.aendere(conn, tg, klm, einst, 1, "   ", nummer=1)

    assert ergebnis is None
    assert klm.aufrufe == []
    assert repo.hole_szene(conn, ids[0])["volltext"] == "EMMA: Home alone."
