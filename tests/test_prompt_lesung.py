"""Die Opus-Lesung: Nummerierung, Zitatwache, Kappung -- alles offline.

Der echte Lauf kostet 0 CHF (Abo-Proxy) und wird vom Controller gefahren
(Task 9). Hier laeuft nur ein Fake-Klient: kein Netz, keine Zufaelligkeit.
"""
from pathlib import Path

import pytest

from scripts import pruefe_prompts_lesung as lesung

DUMP = """# 07-gespraech-phase4
# art=gespraech phase=4 weg=claude modell=claude-opus-5 quelle=abgefangen
=== SYSTEM (10 Zeichen, ~3 Token) ===
Every suggestion message ends with an open question to the group.
At most ONE question per message -- and that one at the end.

=== NUTZER (5 Zeichen, ~2 Token) ===
Member 1: ok
"""


class KlientAttrappe:
    """Liefert vorbereitete Antworten in Reihenfolge und zaehlt die Aufrufe."""

    def __init__(self, antworten):
        self._antworten = list(antworten)
        self.aufrufe = []

    def json_objekt(self, system, nutzer, art="sim", max_tokens=None,
                    bilder=None):
        self.aufrufe.append((system, nutzer))
        return self._antworten.pop(0)


def test_nummeriere_setzt_eins_basierte_nummern_vor_jede_zeile():
    text = lesung.nummeriere("eins\nzwei\n")
    assert text.splitlines()[0].startswith("1| eins")
    assert text.splitlines()[1].startswith("2| zwei")


def test_zeilenfenster_nimmt_nachbarzeilen_mit():
    fenster = lesung.zeilenfenster(DUMP, 4, fenster=1)
    assert "Every suggestion message" in fenster
    assert "At most ONE question" in fenster


def test_pruefe_befund_nimmt_ein_woertliches_zitat_an():
    befund = {"kategorie": "a", "datei": "07-gespraech-phase4", "zeile": 4,
              "zitat": "ends with an open question", "regel": "4",
              "vorschlag": "weg damit"}
    assert lesung.pruefe_befund(befund, {"07-gespraech-phase4": DUMP})


def test_pruefe_befund_lehnt_ein_erfundenes_zitat_ab():
    befund = {"kategorie": "a", "datei": "07-gespraech-phase4", "zeile": 4,
              "zitat": "always end with three questions", "regel": "4",
              "vorschlag": "x"}
    assert not lesung.pruefe_befund(befund, {"07-gespraech-phase4": DUMP})


def test_pruefe_befund_lehnt_eine_unbekannte_datei_ab():
    befund = {"kategorie": "a", "datei": "gibt-es-nicht", "zeile": 1,
              "zitat": "x", "regel": "4", "vorschlag": "x"}
    assert not lesung.pruefe_befund(befund, {"07-gespraech-phase4": DUMP})


def test_kappe_nimmt_zehn_aus_abc_und_fuenf_aus_d():
    befunde = (
        [{"kategorie": "a", "zitat": f"a{i}"} for i in range(8)]
        + [{"kategorie": "b", "zitat": f"b{i}"} for i in range(8)]
        + [{"kategorie": "d", "zitat": f"d{i}"} for i in range(9)]
    )
    gekappt = lesung.kappe(befunde)
    assert sum(1 for b in gekappt if b["kategorie"] in "abc") == 10
    assert sum(1 for b in gekappt if b["kategorie"] == "d") == 5


def test_lies_phase_prueft_zitate_und_wiederholt_genau_einmal():
    klient = KlientAttrappe([
        {"befunde": [{"kategorie": "a", "datei": "07-gespraech-phase4",
                      "zeile": 4, "zitat": "erfunden", "regel": "4",
                      "vorschlag": "x"}]},
        {"befunde": [{"kategorie": "a", "datei": "07-gespraech-phase4",
                      "zeile": 4, "zitat": "ends with an open question",
                      "regel": "4", "vorschlag": "x"}]},
    ])
    geprueft, unsicher = lesung.lies_phase(
        klient, 4, {"07-gespraech-phase4": DUMP}, "REGELN", "RUBRIK")
    assert len(klient.aufrufe) == 2, "genau ein Retry"
    assert len(geprueft) == 1
    assert not unsicher
    assert "did not appear" in klient.aufrufe[1][1]


def test_lies_phase_verwirft_nach_dem_retry():
    klient = KlientAttrappe([
        {"befunde": [{"kategorie": "a", "datei": "07-gespraech-phase4",
                      "zeile": 4, "zitat": "erfunden", "regel": "4",
                      "vorschlag": "x"}]},
        {"befunde": [{"kategorie": "a", "datei": "07-gespraech-phase4",
                      "zeile": 4, "zitat": "auch erfunden", "regel": "4",
                      "vorschlag": "x"}]},
    ])
    geprueft, unsicher = lesung.lies_phase(
        klient, 4, {"07-gespraech-phase4": DUMP}, "REGELN", "RUBRIK")
    assert geprueft == []
    assert len(unsicher) == 1


def test_lies_phase_fragt_nicht_nach_wenn_alles_belegt_ist():
    klient = KlientAttrappe([
        {"befunde": [{"kategorie": "c", "datei": "07-gespraech-phase4",
                      "zeile": 5, "zitat": "At most ONE question",
                      "regel": "veraltet", "vorschlag": "x"}]},
    ])
    geprueft, unsicher = lesung.lies_phase(
        klient, 4, {"07-gespraech-phase4": DUMP}, "REGELN", "RUBRIK")
    assert len(klient.aufrufe) == 1
    assert len(geprueft) == 1


def test_nutzertext_nennt_die_nummerierten_dumps_regeln_und_rubrik():
    text, gekappt = lesung.nutzertext(
        4, {"07-gespraech-phase4": DUMP}, "DIE-REGELN", "DIE-RUBRIK")
    assert "DIE-REGELN" in text and "DIE-RUBRIK" in text
    assert "07-gespraech-phase4" in text
    assert "4| Every suggestion message" in text
    assert gekappt is False


def test_nutzertext_kappt_und_sagt_es(monkeypatch):
    monkeypatch.setattr(lesung, "ZEICHEN_MAX", 200)
    text, gekappt = lesung.nutzertext(
        4, {"a": DUMP, "b": DUMP, "c": DUMP}, "R", "U")
    assert gekappt is True
    assert "truncated" in text


def test_die_anweisung_ist_eine_modulkonstante_und_keine_prompt_datei():
    """Kein neuer Prompt unter interview_theater/prompts/ -- diese Lesung ist
    ein Werkzeug des Audits, kein Bot-Verhalten."""
    assert len(lesung.ANWEISUNG) > 400
    assert not Path("interview_theater/prompts/lesung.md").exists()
