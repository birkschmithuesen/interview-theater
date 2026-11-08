"""Tests fuer scripts/phasen_summary_nachtrag.py (Karte t_1bc96848, Teil 2):
traegt das Phasen-Summary fuer Gruppen nach, die Phasen abgeschlossen haben,
bevor der Mechanismus (interview_theater.phasen_summary) existierte.

Reine DB-Tests gegen eine frische Testdatenbank unter ``tmp_path`` -- nie
gegen eine Betriebsdatenbank. Das Sprachmodell ist eine Attrappe
(``KLMAttrappe``, derselbe Aufbau wie tests/test_phasen_summary.py).
"""

import pytest

import scripts.phasen_summary_nachtrag as skript
from interview_theater import db, phasen, phasen_summary, repo


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
            "discarded": [],
            "offene_punkte": [],
        }
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, modell=None):
        self.aufrufe.append({"chat_id": chat_id, "art": art})
        return self.antwort


def _setze_phase_journal(conn, chat_id, phase):
    """Wie in tests/test_phasen_summary.py: schreibt den Journaleintrag, den
    ``phasen.setze`` beim Eintritt in eine Phase schreibt."""
    repo.setze_phase(conn, chat_id, phase)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Phase {phasen.bezeichnung(phase)}",
        quelle="test",
    )


@pytest.fixture(autouse=True)
def keine_echten_netzaufrufe(monkeypatch):
    """Ein Testlauf darf nie ins Netz -- ``main`` baut sonst einen echten
    ``httpx.Client``/``llm.LLM``. Beide Stellen werden in den einzelnen
    Tests gezielt durch Attrappen ersetzt; hier nur die Grundabsicherung,
    falls ein Test das vergisst."""
    monkeypatch.setattr(skript.einstellungen, "laden", lambda: (_ for _ in ()).throw(
        AssertionError("echte Einstellungen waeren im Test ein Netzzugriff")
    ))


def _erlaube_attrappe(monkeypatch, einst, klm):
    monkeypatch.setattr(skript.einstellungen, "laden", lambda: einst)
    monkeypatch.setattr(skript.llm, "LLM", lambda e, klient, conn: klm)


# ---------------------------------------------------------------------------
# plane(): reine Leseabfrage, nie Netz, nie Schreibzugriff
# ---------------------------------------------------------------------------


def test_plane_ohne_phase_listet_abgeschlossene_phasen_ohne_summary(conn):
    _setze_phase_journal(conn, 1, 4)
    _setze_phase_journal(conn, 1, 5)  # aktuelle Phase jetzt 5

    plan = skript.plane(conn, 1, None)

    phasen_nummern = sorted(e["phase"] for e in plan)
    assert phasen_nummern == [p for p in phasen_nummern if p < 5]
    assert 4 in phasen_nummern
    assert 5 not in phasen_nummern  # 5 ist die aktuelle, nicht abgeschlossen
    assert all(not e["hat_bereits_summary"] for e in plan)


def test_plane_ohne_phase_laesst_phasen_mit_vorhandenem_summary_weg(conn):
    _setze_phase_journal(conn, 1, 4)
    _setze_phase_journal(conn, 1, 5)
    repo.speichere_phasen_summary(conn, 1, 4, "schon da")

    plan = skript.plane(conn, 1, None)

    assert 4 not in [e["phase"] for e in plan]


def test_plane_mit_phase_erzwingt_genau_diese_phase_auch_mit_summary(conn):
    _setze_phase_journal(conn, 1, 4)
    _setze_phase_journal(conn, 1, 5)
    repo.speichere_phasen_summary(conn, 1, 4, "schon da")

    plan = skript.plane(conn, 1, 4)

    assert [e["phase"] for e in plan] == [4]
    assert plan[0]["hat_bereits_summary"] is True


def test_plane_traegt_die_quellgroesse_in_zeichen(conn):
    _setze_phase_journal(conn, 1, 4)
    _setze_phase_journal(conn, 1, 5)
    seit = repo.phase_eintritt_zeitpunkt(conn, 1, "Phase 4")
    repo.merke_nachricht(conn, 1, 101, "Gruppe", 0, "text",
                         "We set it in a kitchen.", seit)

    plan = skript.plane(conn, 1, 4)

    erwartet = len(phasen_summary.baue_nutzertext(conn, 1, 4))
    assert plan[0]["quelle_zeichen"] == erwartet
    assert erwartet > 0


# ---------------------------------------------------------------------------
# main(): Trockenlauf vs. --ja
# ---------------------------------------------------------------------------


def test_main_trockenlauf_schreibt_nichts(tmp_path, conn, einst, monkeypatch, capsys):
    _setze_phase_journal(conn, 1, 4)
    _setze_phase_journal(conn, 1, 5)
    conn.close()
    _erlaube_attrappe(monkeypatch, einst, KLMAttrappe())

    rc = skript.main(["--db", str(tmp_path / "t.db"), "--chat", "1"])

    assert rc == 0
    ausgabe = capsys.readouterr().out
    assert "Phase 4" in ausgabe or "4" in ausgabe
    nachlese = db.verbinde(str(tmp_path / "t.db"))
    assert repo.hole_phasen_summary(nachlese, 1, 4) is None


def test_main_mit_ja_schreibt_summary(tmp_path, conn, einst, monkeypatch):
    _setze_phase_journal(conn, 1, 4)
    _setze_phase_journal(conn, 1, 5)
    # Phasen 1-3 schon nachgetragen -- nur Phase 4 fehlt noch.
    for frueher in (1, 2, 3):
        repo.speichere_phasen_summary(conn, 1, frueher, "schon da")
    conn.close()
    klm = KLMAttrappe()
    _erlaube_attrappe(monkeypatch, einst, klm)

    rc = skript.main(["--db", str(tmp_path / "t.db"), "--chat", "1", "--ja"])

    assert rc == 0
    assert len(klm.aufrufe) == 1
    nachlese = db.verbinde(str(tmp_path / "t.db"))
    text = phasen_summary.hole_text(nachlese, 1, 4)
    assert text is not None
    assert "kitchen" in text


def test_main_mit_ja_ohne_phase_erzeugt_bei_wiederholung_keine_dubletten(
    tmp_path, conn, einst, monkeypatch,
):
    _setze_phase_journal(conn, 1, 4)
    _setze_phase_journal(conn, 1, 5)
    conn.close()
    _erlaube_attrappe(monkeypatch, einst, KLMAttrappe())

    erster_rc = skript.main(["--db", str(tmp_path / "t.db"), "--chat", "1", "--ja"])
    zweiter_rc = skript.main(["--db", str(tmp_path / "t.db"), "--chat", "1", "--ja"])

    assert erster_rc == zweiter_rc == 0
    nachlese = db.verbinde(str(tmp_path / "t.db"))
    zeilen = nachlese.execute(
        "SELECT COUNT(*) FROM phasen_summary WHERE chat_id = 1 AND phase = 4"
    ).fetchone()[0]
    assert zeilen == 1


def test_main_mit_phase_schreibt_auch_wenn_schon_vorhanden(
    tmp_path, conn, einst, monkeypatch,
):
    _setze_phase_journal(conn, 1, 4)
    _setze_phase_journal(conn, 1, 5)
    repo.speichere_phasen_summary(conn, 1, 4, "alt")
    conn.close()
    _erlaube_attrappe(monkeypatch, einst, KLMAttrappe())

    rc = skript.main(["--db", str(tmp_path / "t.db"), "--chat", "1",
                      "--phase", "4", "--ja"])

    assert rc == 0
    nachlese = db.verbinde(str(tmp_path / "t.db"))
    zeilen = nachlese.execute(
        "SELECT COUNT(*) FROM phasen_summary WHERE chat_id = 1 AND phase = 4"
    ).fetchone()[0]
    assert zeilen == 2  # bewusster Nachtrag/Ersatz -- das aeltere bleibt stehen


def test_main_ohne_plan_ruft_nie_das_modell(tmp_path, conn, einst, monkeypatch):
    """Keine abgeschlossene Phase ohne Summary: main() darf gar nicht erst
    versuchen, einstellungen.laden()/llm.LLM aufzurufen (die Fixture
    keine_echten_netzaufrufe wuerde das sofort als Fehler zeigen)."""
    conn.close()

    rc = skript.main(["--db", str(tmp_path / "t.db"), "--chat", "1", "--ja"])

    assert rc == 0
