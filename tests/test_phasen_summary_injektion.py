"""Injektion der Phasen-Summary in die Prompt-Bausteine, die bisher den
Rohdump des Phase-5-Gesprachs trugen (Karte t_1bc96848): ``szene.py``
(``p5_gespraech_block``, der zentrale Umschalter), ``entwurf.py``
(Uebersicht/Logline), ``schaerfung.py`` (Matcher-Hintergrund) und
``szenenkarte.py`` (Konzeptkarten-Erzeugung) rufen alle dieselbe Funktion.

Geprueft wird: solange Phase 5 die AKTUELLE Phase ist (oder kein Summary
vorliegt, oder der Profilschalter aus ist), bleibt es beim vollen Wortlaut
-- ist Phase 5 ABGESCHLOSSEN und ein Summary gespeichert, tritt es an die
Stelle des Wortlauts. Dortmund (Profilschalter aus) ist in keinem Fall
betroffen.
"""

import pytest

from interview_theater import entwurf, phasen, repo, schaerfung, szene, szenenkarte, workshop


@pytest.fixture(autouse=True)
def mitgehoert_voll(monkeypatch):
    """``_p5_gespraech_text`` liefert nur unter diesem Schalter ueberhaupt
    etwas -- in jedem Test hier an, wie in tests/test_szene.py."""
    monkeypatch.setattr(workshop, "vollmaterial_phase5_aktiv", lambda *a, **k: True)


def _schreibe_phase5_chat(conn, chat_id=1):
    repo.schreibe_journal(
        conn, chat_id, "entschieden", "Phase 5 · Prose Draft", quelle="test",
    )
    seit = repo.phase_eintritt_zeitpunkt(conn, chat_id, "Phase 5")
    repo.merke_nachricht(conn, chat_id, 201, "Gruppe", 0, "text",
                         "Let's use interview 3 for the kitchen scene.", seit)


# ---------------------------------------------------------------------------
# szene.p5_gespraech_block: der zentrale Umschalter
# ---------------------------------------------------------------------------


def test_p5_gespraech_block_ist_der_rohdump_ohne_profilschalter(conn, monkeypatch):
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: False)
    _schreibe_phase5_chat(conn)
    repo.setze_phase(conn, 1, 6)
    repo.speichere_phasen_summary(conn, 1, 5, "Decided: a kitchen scene.")

    block = szene.p5_gespraech_block(conn, 1)

    assert "Let's use interview 3" in block
    assert "Decided: a kitchen scene." not in block


def test_p5_gespraech_block_bleibt_rohdump_solange_phase_5_aktuell_ist(conn, monkeypatch):
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: True)
    _schreibe_phase5_chat(conn)
    repo.setze_phase(conn, 1, 5)
    repo.speichere_phasen_summary(conn, 1, 5, "Decided: a kitchen scene.")

    block = szene.p5_gespraech_block(conn, 1)

    assert "Let's use interview 3" in block
    assert "Decided: a kitchen scene." not in block


def test_p5_gespraech_block_nutzt_das_summary_nach_abgeschlossener_phase_5(conn, monkeypatch):
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: True)
    _schreibe_phase5_chat(conn)
    repo.setze_phase(conn, 1, 6)
    repo.speichere_phasen_summary(conn, 1, 5, "Decided: a kitchen scene.")

    block = szene.p5_gespraech_block(conn, 1)

    assert block == "Decided: a kitchen scene."
    assert "Let's use interview 3" not in block


def test_p5_gespraech_block_faellt_ohne_gespeichertes_summary_auf_rohdump_zurueck(
    conn, monkeypatch,
):
    """Noch keine Summary erzeugt (Race, Fehlschlag): kein Absturz, kein
    leerer Prompt -- der Rohdump bleibt die Verteidigungslinie."""
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: True)
    _schreibe_phase5_chat(conn)
    repo.setze_phase(conn, 1, 6)

    block = szene.p5_gespraech_block(conn, 1)

    assert "Let's use interview 3" in block


# ---------------------------------------------------------------------------
# entwurf.py, schaerfung.py, szenenkarte.py rufen denselben Umschalter
# ---------------------------------------------------------------------------


def test_entwurf_voll_bloecke_nutzt_p5_gespraech_block(conn, monkeypatch):
    monkeypatch.setattr(workshop, "vollmaterial_phase5_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(szene, "p5_gespraech_block",
                        lambda conn_, chat_id, ueber_claude=False: "STUB-SUMMARY")

    bloecke = entwurf._voll_bloecke(conn, 1)

    assert any("STUB-SUMMARY" in b for b in bloecke)


def test_schaerfung_hintergrund_nutzt_p5_gespraech_block(conn, monkeypatch):
    monkeypatch.setattr(workshop, "vollmaterial_phase5_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(szene, "p5_gespraech_block",
                        lambda conn_, chat_id, ueber_claude=False: "STUB-SUMMARY")

    zeilen = schaerfung._hintergrund_voll_zeilen(conn, 1, repo.hole_arbeitsstand(conn, 1))

    assert any("STUB-SUMMARY" in z for z in zeilen)


def test_szenenkarte_baue_nutzertext_nutzt_p5_gespraech_block(conn, monkeypatch):
    monkeypatch.setattr(workshop, "vollmaterial_phase5_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(szene, "p5_gespraech_block",
                        lambda conn_, chat_id, ueber_claude=False: "STUB-SUMMARY")
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    zeile = repo.hole_szene(conn, szene_id)

    text = szenenkarte.baue_nutzertext(conn, 1, zeile)

    assert "STUB-SUMMARY" in text


# ---------------------------------------------------------------------------
# Dortmund/Vorgabe: der Profilschalter wirkt dort nie
# ---------------------------------------------------------------------------


def test_dortmund_pfad_bleibt_unberuehrt_auch_mit_gespeichertem_summary(conn, monkeypatch):
    """Ohne IT_WORKSHOP (eingebautes Vorgabeprofil) ist
    ``workshop.phasen_summary_aktiv`` false -- ein gespeichertes Summary
    (z. B. aus einem frueheren Padua-Lauf derselben DB) darf trotzdem nie
    einsickern."""
    assert workshop.phasen_summary_aktiv() is False
    _schreibe_phase5_chat(conn)
    repo.setze_phase(conn, 1, 6)
    repo.speichere_phasen_summary(conn, 1, 5, "Decided: a kitchen scene.")

    block = szene.p5_gespraech_block(conn, 1)

    assert "Let's use interview 3" in block
    assert "Decided: a kitchen scene." not in block
