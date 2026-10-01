"""Der kostenlose Ersatznachweis (30.09.2026, Karte R).

Kein bezahlter Lauf: die Attrappe liefert einen zu langen, sprachlich
auffaelligen Text, und gemessen wird, dass genau EIN Nachpass folgt und die
Tabelle die Zahlen traegt.
"""

import pytest

from scripts import laengen_probe


def test_die_texte_der_attrappe_sind_alle_auffaellig():
    """Die Probe taugt nur, wenn ihr Material wirklich etwas ausloest -- sonst
    beweist eine leere Tabelle gar nichts."""
    from interview_theater import sprachpass
    for name, text in laengen_probe.TEXTE.items():
        roh = sprachpass.rohzahlen(text, "en")
        assert any(v > 0 for v in roh.values()), name


def test_der_lauf_liefert_eine_zeile_je_szene(tmp_path):
    zeilen = laengen_probe.probe(formen=["dialog", "chor", "rap"], faktor=1.0)
    assert [z["nummer"] for z in zeilen] == [1, 2, 3]
    for z in zeilen:
        assert z["budget"] > 0
        assert z["woerter_vorher"] > 0
        assert z["laeufe"] in (1, 2)


def test_genau_ein_nachpass_je_szene():
    """Der Kostendeckel, kostenlos nachgewiesen: ein Szenenlauf plus
    hoechstens ein Nachpass."""
    zeilen = laengen_probe.probe(formen=["dialog", "dialog"], faktor=1.0)
    assert all(z["laeufe"] <= 2 for z in zeilen), zeilen


def test_die_budgets_sind_nicht_flach():
    zeilen = laengen_probe.probe(formen=["dialog"] * 4, faktor=1.0)
    budgets = [z["budget"] for z in zeilen]
    assert len(set(budgets)) >= 2, budgets


def test_die_tabelle_traegt_jede_spalte():
    zeilen = laengen_probe.probe(formen=["dialog"], faktor=1.0)
    text = laengen_probe.tabelle(zeilen)
    for kopf in ("Szene", "Form", "Budget", "Woerter", "Laeufe"):
        assert kopf in text, kopf


def test_das_skript_nimmt_niemals_IT_DB(monkeypatch):
    """Wie ``scripts/pruefe_prompts.py``: die Betriebsdatenbank wird nicht
    angefasst -- auch nicht lesend."""
    monkeypatch.setenv("IT_DB", "/nicht/vorhanden/soap.db")
    zeilen = laengen_probe.probe(formen=["dialog"], faktor=1.0)
    assert zeilen


def test_es_gibt_keinen_echten_modellaufruf():
    import inspect
    quelle = inspect.getsource(laengen_probe)
    assert "httpx" not in quelle
    assert "IT_LLM_URL" not in quelle


def test_die_probe_laesst_das_profil_des_aufrufers_stehen(monkeypatch):
    """``probe`` setzt ``IT_WORKSHOP`` fuer sich -- und nimmt es danach
    zurueck. Ohne das liefen alle spaeteren Tests desselben Prozesses unter
    Padua (gemessen: rund hundert rote Tests in der Suite)."""
    import os
    from interview_theater import workshop
    monkeypatch.delenv("IT_WORKSHOP", raising=False)
    workshop.vergiss()
    laengen_probe.probe(formen=["dialog"], faktor=1.0)
    assert "IT_WORKSHOP" not in os.environ
    monkeypatch.setenv("IT_WORKSHOP", "dortmund-2026")
    laengen_probe.probe(formen=["dialog"], faktor=1.0)
    assert os.environ["IT_WORKSHOP"] == "dortmund-2026"
