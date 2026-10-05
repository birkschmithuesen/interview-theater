"""Karte t_4517d4ad, Aufgabe 7: begriffe_detail geht in Phase 2 und ab
Phase 4 in den Gespraechs-Prompt, und in den ISOLIERTEN KI-Fragen-Aufruf (D8)."""

import json
import time

import pytest

from interview_theater import db, einstellungen, fragen_ki, kontext, repo, workshop

CHAT = 1
GRUND = "Weil Heimat fuer uns der Ort ist, wo die Oma kocht."
ZITAT = "ZITAT-DARF-NIE-IN-DEN-PROMPT"
EIGENE_FRAGE = "EIGENE-FRAGE-DER-GRUPPE?"


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
    repo.setze_arbeitsstand(c, CHAT, "begriffe", "Heimat, Schule")
    repo.setze_arbeitsstand(c, CHAT, "begriffe_detail", json.dumps([
        {"begriff": "Heimat", "begruendung": GRUND, "zitat": ZITAT, "doppelbedeutung": "Ort und Gefuehl"},
        {"begriff": "Schule", "begruendung": "", "zitat": "", "doppelbedeutung": ""},
    ]))
    return c


@pytest.mark.parametrize("phase", [1, 2, 3, 4, 6])
def test_block_erscheint_in_jeder_phase_ohne_board(conn, phase):
    """R-1 (05.10.2026): bis dahin stand das Detail nur in Phase 2 und ab 4.
    Seit das CoThinker-Board selbst in jeder Phase im Prompt steht (Birk:
    "der Chat muss immer alles wissen"), gilt dieselbe Regel fuer die
    Begriffe, die der Board-Block NICHT zeigt -- ohne Board ueberhaupt (wie
    in dieser Fixture) zeigt er gar nichts, also bleibt das Detail in jeder
    Phase."""
    repo.setze_phase(conn, CHAT, phase)
    block = kontext._baue_begriffe_detail(conn, CHAT)
    assert GRUND in block
    assert ZITAT not in block


def test_block_fehlt_fuer_begriffe_die_das_board_schon_zeigt(conn):
    """Ein Fakt, eine Stelle: zeigt der Board-Block selbst schon die
    Begruendung eines (nicht verworfenen) Begriffs, bleibt NUR die
    Begruendung hier aussen vor. Eine Doppelbedeutung zeigt der Board-Block
    nie (MINOR 3, Review T3) -- die bleibt im Detail-Block stehen, auch fuer
    einen Begriff, der schon auf dem Board steht. Schule ist gar nicht auf
    dem Board und hat ohnehin keine Begruendung/Doppelbedeutung, bleibt also
    komplett aussen vor."""
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps([
        {"begriff": "Heimat", "nennungen": 1, "zustimmung": 1, "begruendung": GRUND,
         "zitat": "", "doppelbedeutung": "", "status": "favorit"},
    ]), "sovereign", 0)
    repo.setze_phase(conn, CHAT, 2)

    block = kontext._baue_begriffe_detail(conn, CHAT)

    assert GRUND not in block, "Heimat-Begruendung steht schon im Board-Block"
    assert "Ort und Gefuehl" in block, "die Doppelbedeutung zeigt der Board-Block nie"
    assert "Schule" not in block, "Schule traegt nichts Zusaetzliches zum Board-Block"


def test_block_ganz_leer_wenn_board_wirklich_alles_zeigt(conn):
    """Ohne Doppelbedeutung traegt ein auf dem Board stehender Begriff nichts
    mehr, was der Board-Block nicht schon zeigt -- der ganze Eintrag faellt
    weg wie bisher."""
    repo.setze_arbeitsstand(conn, CHAT, "begriffe_detail", json.dumps([
        {"begriff": "Heimat", "begruendung": GRUND, "zitat": ZITAT, "doppelbedeutung": ""},
        {"begriff": "Schule", "begruendung": "", "zitat": "", "doppelbedeutung": ""},
    ]))
    repo.lege_begriffsboard_an(conn, CHAT, json.dumps([
        {"begriff": "Heimat", "nennungen": 1, "zustimmung": 1, "begruendung": GRUND,
         "zitat": "", "doppelbedeutung": "", "status": "favorit"},
    ]), "sovereign", 0)
    repo.setze_phase(conn, CHAT, 2)

    block = kontext._baue_begriffe_detail(conn, CHAT)

    assert block == ""


def test_block_traegt_kopf_und_doppelbedeutung(conn):
    repo.setze_phase(conn, CHAT, 2)
    block = kontext._baue_begriffe_detail(conn, CHAT)
    assert block.startswith(kontext.T.BEGRIFFE_DETAIL_KOPF)
    assert "Ort und Gefuehl" in block
    assert "Schule" not in block


def test_ohne_detail_kein_block(conn):
    repo.setze_phase(conn, CHAT, 2)
    repo.setze_arbeitsstand(conn, CHAT, "begriffe_detail", None)
    assert kontext._baue_begriffe_detail(conn, CHAT) == ""


def test_block_steht_direkt_hinter_der_diskussion():
    reihenfolge = list(kontext._REIHENFOLGE)
    assert reihenfolge[reihenfolge.index("diskussion") + 1] == "begriffe_detail"


def test_block_erscheint_im_fertigen_prompt_phase_2(conn, einst):
    repo.setze_phase(conn, CHAT, 2)
    repo.merke_nachricht(conn, CHAT, 1, "Ada", 0, "text", "los", repo._jetzt())
    ausloeser = list(repo.unbeantwortete(conn, CHAT))
    prompt = kontext.baue(conn, CHAT, ausloeser, einst)
    assert GRUND in prompt and ZITAT not in prompt


# -- fragen_ki ---------------------------------------------------------------

def test_nutzertext_nimmt_das_detail_auf():
    text = fragen_ki._nutzertext("Heimat", None, [
        {"begriff": "Heimat", "begruendung": GRUND, "doppelbedeutung": ""},
    ])
    assert GRUND in text


def test_isolierter_ki_fragen_aufruf_sieht_detail_aber_keine_eigene_frage(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "fragen_ab_aktiv", lambda *a, **k: True)
    repo.setze_arbeitsstand(conn, CHAT, "fragen_eigene_vorschlag", EIGENE_FRAGE)

    class KLM:
        nutzer = None

        def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
            KLM.nutzer = nutzer
            return {"antwort": "Heimat: Was vermisst du?"}

    class TG:
        def sende(self, *a, **k):
            return 1

        def sende_mit_knoepfen(self, *a, **k):
            return 1

    fragen_ki.starte(conn, TG(), KLM(), einst, CHAT)
    ende = time.monotonic() + 5
    while KLM.nutzer is None and time.monotonic() < ende:
        time.sleep(0.01)
    assert GRUND in KLM.nutzer
    assert EIGENE_FRAGE not in KLM.nutzer
    assert ZITAT not in KLM.nutzer
