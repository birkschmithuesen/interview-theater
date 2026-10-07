"""Tests fuer die Phasen-Summary (Karte t_1bc96848, Padua): ein knappes,
automatisiert erzeugtes Summary je Phase, das nur das Beschlossene traegt --
nicht den vollen Chatverlauf. Gemessen werden: der Nutzertextbau (Chat seit
Phaseneintritt, Journal ohne Navigationszeilen, Werkbank-Schnappschuss), die
Zusammensetzung des fertigen Texts samt Laengendeckel, der Thread-Start
(Profilschalter, Sperre je Phase) und die Ablage/der Lesezugriff ueber
``repo``.

Kein Netzzugriff: das Sprachmodell ist eine Attrappe.
"""

import threading
import time

import pytest

from interview_theater import db, phasen, phasen_summary, repo, workshop


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


@pytest.fixture
def einst(tmp_path):
    from interview_theater import einstellungen

    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
        erkenner_modell="gemma",
    )


class KLMAttrappe:
    """Liefert eine feste Schema-Antwort und merkt jeden Aufruf."""

    def __init__(self, antwort=None):
        self.antwort = antwort or {
            "entscheidungen": ["The setting is a kitchen at night."],
            "discarded": ["A sign reading CLOSED."],
            "offene_punkte": ["How the scene ends."],
        }
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None):
        self.aufrufe.append({
            "system": system, "nutzer": nutzer, "schema": schema, "art": art,
        })
        return self.antwort


@pytest.fixture(autouse=True)
def padua_aus(monkeypatch):
    """Vorgabe in jedem Test: der Profilschalter ist AUS (Dortmund-Stand) --
    einzelne Tests schalten ihn gezielt ein."""
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: False)


def _setze_phase_journal(conn, chat_id, phase):
    """Schreibt den Journaleintrag, den ``phasen.setze`` beim Eintritt in
    eine Phase schreibt -- ohne den echten Phasenwechsel-Mechanismus noetig
    zu machen (die Tests hier pruefen nur das Summary-Modul)."""
    repo.setze_phase(conn, chat_id, phase)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Phase {phasen.bezeichnung(phase)}",
        quelle="test",
    )


# ---------------------------------------------------------------------------
# Nutzertextbau
# ---------------------------------------------------------------------------


def test_baue_nutzertext_enthaelt_chat_seit_phaseneintritt(conn):
    _setze_phase_journal(conn, 1, 4)
    seit = repo.phase_eintritt_zeitpunkt(conn, 1, "Phase 4")
    repo.merke_nachricht(conn, 1, 101, "Gruppe", 0, "text",
                         "We set it in a kitchen.", seit)
    repo.merke_nachricht(conn, 1, 102, "Bot", 1, "text",
                         "Got it, a kitchen it is.", seit)

    text = phasen_summary.baue_nutzertext(conn, 1, 4)

    assert "Gruppe: We set it in a kitchen." in text
    assert "Du: Got it, a kitchen it is." in text


def test_baue_nutzertext_laesst_nachrichten_vor_dem_phaseneintritt_weg(conn):
    repo.merke_nachricht(conn, 1, 100, "Gruppe", 0, "text",
                         "Earlier, unrelated chat.", "2020-01-01T00:00:00+00:00")
    _setze_phase_journal(conn, 1, 4)
    seit = repo.phase_eintritt_zeitpunkt(conn, 1, "Phase 4")
    repo.merke_nachricht(conn, 1, 101, "Gruppe", 0, "text",
                         "During the phase.", seit)

    text = phasen_summary.baue_nutzertext(conn, 1, 4)

    assert "During the phase." in text
    assert "Earlier, unrelated chat." not in text


def test_baue_nutzertext_enthaelt_journal_ohne_phasenzeilen(conn):
    _setze_phase_journal(conn, 1, 4)
    repo.schreibe_journal(conn, 1, "entschieden", "Setting: a kitchen", quelle="erkenner")
    repo.schreibe_journal(conn, 1, "verworfen", "A sign reading CLOSED", quelle="erkenner")

    text = phasen_summary.baue_nutzertext(conn, 1, 4)

    assert "Setting: a kitchen" in text
    assert "A sign reading CLOSED" in text
    # Die reine Phasen-Navigationszeile selbst ist kein Inhalt (sie wuerde
    # das Summary nur mit sich selbst fuellen, siehe Moduldocstring).
    assert text.count("Phase 4") <= 1  # nur der Kopf "Phase: Phase 4 ..."


def test_baue_nutzertext_enthaelt_werkbank_schnappschuss(conn):
    _setze_phase_journal(conn, 1, 4)
    repo.setze_arbeitsstand(conn, 1, "rahmen", "A kitchen, late at night.")
    repo.setze_figur(conn, 1, "Mira", "wants to be heard")

    text = phasen_summary.baue_nutzertext(conn, 1, 4)

    assert "Setting: A kitchen, late at night." in text
    assert "Mira" in text


def test_baue_nutzertext_ist_knapp_ohne_jedes_material(conn):
    _setze_phase_journal(conn, 1, 4)
    text = phasen_summary.baue_nutzertext(conn, 1, 4)
    assert "Phase: Phase 4" in text


# ---------------------------------------------------------------------------
# Textzusammenbau und Laengendeckel
# ---------------------------------------------------------------------------


def test_baue_text_traegt_alle_drei_abschnitte():
    ergebnis = {
        "entscheidungen": ["Decided one."],
        "discarded": ["Dropped one."],
        "offene_punkte": ["Open one."],
    }
    text = phasen_summary.baue_text(ergebnis, 4)
    assert "Decided one." in text
    assert "Dropped one." in text
    assert "Open one." in text
    assert "Decided:" in text
    assert "Discarded:" in text
    assert "Open:" in text


def test_baue_text_laesst_leere_abschnitte_weg():
    text = phasen_summary.baue_text(
        {"entscheidungen": ["X"], "discarded": [], "offene_punkte": []}, 4,
    )
    assert "Discarded:" not in text
    assert "Open:" not in text


def test_baue_text_kappt_auf_max_zeichen():
    riesig = [f"Entry number {i} with some more words to pad it out." for i in range(200)]
    text = phasen_summary.baue_text(
        {"entscheidungen": riesig, "discarded": [], "offene_punkte": []}, 4,
    )
    assert len(text) <= phasen_summary.MAX_ZEICHEN + 10  # Rundung am Zeilenumbruch


def test_max_zeichen_ist_ein_zehntel_des_gemessenen_rohdumps():
    """Dokumentiert die Begruendung der Konstante (Moduldocstring): 1.500 ist
    rund ein Zehntel des gemessenen Phase-5-Rohdumps (16.710 Zeichen,
    docs/handoffs/ zur Karte)."""
    assert phasen_summary.MAX_ZEICHEN == 1500
    assert phasen_summary.MAX_ZEICHEN < 16_710 / 5


# ---------------------------------------------------------------------------
# Modellaufruf
# ---------------------------------------------------------------------------


def test_erzeuge_ruft_modellwahl_mit_dem_schema(conn, einst, monkeypatch):
    _setze_phase_journal(conn, 1, 4)
    monkeypatch.setattr(phasen_summary.szene_claude, "ist_aktiv", lambda e, c, cid: False)
    klm = KLMAttrappe()

    ergebnis = phasen_summary.erzeuge(klm, conn, einst, 1, 4)

    assert klm.aufrufe[0]["art"] == phasen_summary.ART
    assert klm.aufrufe[0]["schema"] == phasen_summary.SCHEMA
    assert ergebnis["entscheidungen"] == ["The setting is a kitchen at night."]


# ---------------------------------------------------------------------------
# Thread-Start: Profilschalter, Sperre, Ablage
# ---------------------------------------------------------------------------


def test_starte_wenn_aktiv_tut_nichts_ohne_profilschalter(conn, einst):
    klm = KLMAttrappe()
    assert phasen_summary.starte_wenn_aktiv(conn, klm, einst, 1, 4) is None
    assert repo.hole_phasen_summary(conn, 1, 4) is None


def test_starte_wenn_aktiv_tut_nichts_ohne_modell(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: True)
    assert phasen_summary.starte_wenn_aktiv(conn, None, einst, 1, 4) is None


def test_starte_wenn_aktiv_tut_nichts_ohne_phase(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: True)
    klm = KLMAttrappe()
    assert phasen_summary.starte_wenn_aktiv(conn, klm, einst, 1, None) is None


def test_starte_wenn_aktiv_erzeugt_und_speichert_das_summary(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(phasen_summary.szene_claude, "ist_aktiv", lambda e, c, cid: False)
    _setze_phase_journal(conn, 1, 4)
    klm = KLMAttrappe()

    thread = phasen_summary.starte_wenn_aktiv(conn, klm, einst, 1, 4)
    assert thread is not None
    thread.join(timeout=5)

    text = phasen_summary.hole_text(conn, 1, 4)
    assert text is not None
    assert "kitchen" in text


def test_starte_wenn_aktiv_laeuft_nie_zweimal_parallel_fuer_dieselbe_phase(
    conn, einst, monkeypatch,
):
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: True)
    sperre = phasen_summary._sperre_fuer(1, 4)
    sperre.acquire()
    try:
        assert phasen_summary.starte_wenn_aktiv(conn, KLMAttrappe(), einst, 1, 4) is None
    finally:
        sperre.release()


def test_ein_fehlschlag_speichert_keinen_vorfall_blockiert_aber_nicht(
    conn, einst, monkeypatch,
):
    """Kein Summary ist ein akzeptabler Fehlerfall: ein scheiterndes Modell
    darf den Thread nicht mit einer Ausnahme beenden und muss die Sperre
    wieder freigeben."""
    monkeypatch.setattr(workshop, "phasen_summary_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(phasen_summary.szene_claude, "ist_aktiv", lambda e, c, cid: False)
    _setze_phase_journal(conn, 1, 4)

    class KaputtesKLM:
        def schema(self, *a, **k):
            raise RuntimeError("boom")

    thread = phasen_summary.starte_wenn_aktiv(conn, KaputtesKLM(), einst, 1, 4)
    thread.join(timeout=5)

    assert phasen_summary.hole_text(conn, 1, 4) is None
    # Die Sperre ist wieder frei -- ein zweiter Lauf fuer dieselbe Phase darf
    # sofort starten.
    sperre = phasen_summary._sperre_fuer(1, 4)
    assert sperre.acquire(blocking=False)
    sperre.release()


# ---------------------------------------------------------------------------
# Ablage und Lesezugriff (repo)
# ---------------------------------------------------------------------------


def test_repo_hole_phasen_summary_liefert_das_juengste(conn):
    repo.speichere_phasen_summary(conn, 1, 4, "erstes Summary")
    time.sleep(0.01)
    repo.speichere_phasen_summary(conn, 1, 4, "zweites Summary")

    zeile = repo.hole_phasen_summary(conn, 1, 4)
    assert zeile["text"] == "zweites Summary"


def test_repo_phasen_summaries_liefert_je_phase_das_juengste_aufsteigend(conn):
    repo.speichere_phasen_summary(conn, 1, 5, "P5 alt")
    repo.speichere_phasen_summary(conn, 1, 4, "P4")
    repo.speichere_phasen_summary(conn, 1, 5, "P5 neu")

    zeilen = repo.phasen_summaries(conn, 1)
    assert [z["phase"] for z in zeilen] == [4, 5]
    assert [z["text"] for z in zeilen] == ["P4", "P5 neu"]


def test_bloecke_bis_liefert_nur_fruehere_phasen(conn):
    repo.speichere_phasen_summary(conn, 1, 4, "P4 summary")
    repo.speichere_phasen_summary(conn, 1, 5, "P5 summary")

    bloecke = phasen_summary.bloecke_bis(conn, 1, 5)
    assert bloecke == ["P4 summary"]

    bloecke_alle = phasen_summary.bloecke_bis(conn, 1, 6)
    assert bloecke_alle == ["P4 summary", "P5 summary"]


def test_hole_text_ist_none_ohne_summary(conn):
    assert phasen_summary.hole_text(conn, 1, 4) is None


def test_phasen_summary_tabelle_traegt_chat_id():
    assert "phasen_summary" in db.TABELLEN_MIT_CHAT_ID
