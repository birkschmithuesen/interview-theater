"""Tests fuer die Recall-Messung (``scripts/kontext_recall.py``, Auftrag 5).

Der Sinn des Skripts ist, dass es **faellt**, wenn eine Budgetaenderung mehr
Erinnerung kostet als gedacht. Damit es das kann, muss es selbst stimmen: die
Fragen muessen aus dem weggefallenen Teil kommen (sonst misst es eine
Tautologie), und die geschuetzten Felder muessen die Kuerzung ueberleben.
"""

import pytest

from interview_theater import db, kontext, repo
from scripts import kontext_recall
from tests.fixture_spaetstand import baue_spaetstand


@pytest.fixture
def spaetstand(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    return baue_spaetstand(conn)


def test_zehn_fragen_werden_abgeleitet(spaetstand):
    """Zehn mechanisch abgeleitete Faktenfragen, keine erfundenen."""
    fragen = kontext_recall.fragen(spaetstand, 1)
    assert len(fragen) == 10
    assert all(f["antwort"] for f in fragen)
    assert all(len(f["antwort"]) >= 12 for f in fragen)


def test_fragen_kommen_auch_aus_dem_weggefallenen_teil(spaetstand):
    """hermes-agents ``evals/compaction`` fragt ausdruecklich nach der
    wegkomprimierten Region. Fragte das Skript nur nach dem Geschuetzten,
    saehe es immer 10/10 und wuerde nie etwas finden."""
    fragen = kontext_recall.fragen(spaetstand, 1)
    verdraengt = [f for f in fragen if f["kategorie"] == "verdraengt"]
    assert verdraengt, "keine Frage aus dem weggefallenen Teil"
    # Und sie stehen vorn -- sie sind der Zweck, nicht die Zugabe.
    assert fragen[0]["kategorie"] == "verdraengt"


def test_geschuetzte_felder_ueberleben_die_kuerzung(spaetstand):
    """Kernthema, Kernfrage, Rahmen, Geschichte, Begriffe, Figuren: alles
    Dinge, die im Arbeitsstand stehen und deshalb ueberleben *muessen*."""
    ergebnis = kontext_recall.messe(spaetstand, 1)
    geschuetzt = [z for z in ergebnis["zeilen"] if z["kategorie"] != "verdraengt"]
    assert geschuetzt
    verloren = [z["frage"] for z in geschuetzt if z["vorher"] and not z["nachher"]]
    assert not verloren, f"geschuetzte Fakten durch die Kuerzung verloren: {verloren}"


def test_ueberlange_szene_kostet_keinen_geschuetzten_fakt(spaetstand):
    """Der Fall aus Befund C.4: eine 20-fache Szene. Vor Auftrag 3 draengte
    sie Fenster, Journal und Verdichtungen vollstaendig aus dem Prompt --
    und riss die Grenze trotzdem. Jetzt darf sie keinen Arbeitsstand-Fakt
    mehr kosten."""
    s = repo.hole_szenen(spaetstand, 1)[0]
    text = "\n".join(
        f"LEYLA: Ein ausgeschriebener Satz mitten in der Szene, Zeile {i}."
        for i in range(20 * 200)
    )
    repo.aktualisiere_szene(spaetstand, s["id"], s["titel"], s["kurzbeschreibung"], text)

    ergebnis = kontext_recall.messe(spaetstand, 1)

    geschuetzt = [z for z in ergebnis["zeilen"] if z["kategorie"] != "verdraengt"]
    assert all(z["nachher"] for z in geschuetzt if z["vorher"])
    assert ergebnis["nachher_zeichen"] <= kontext.zeichengrenze()
    assert ergebnis["gesamt_nachher"] <= kontext.gesamtgrenze()


def test_bericht_traegt_keine_antworttexte(spaetstand):
    """Kein Nachrichtentext, kein Transkript, kein Wortlaut im Bericht --
    er wird committet (AGENTS.md, dieselbe Regel wie fuer die Prompt-Dumps)."""
    ergebnis = kontext_recall.messe(spaetstand, 1)
    text = kontext_recall.bericht(ergebnis)
    for frage in kontext_recall.fragen(spaetstand, 1):
        assert frage["antwort"] not in text, (
            f"Antworttext steht im Bericht: {frage['frage']}"
        )
    assert "Ein laengerer Gespraechsbeitrag" not in text


def test_messung_ist_reproduzierbar(spaetstand):
    """Zweimal derselbe DB-Stand, zweimal dieselbe Tabelle -- sonst taugt sie
    nicht als Regressionsschutz."""
    a = kontext_recall.messe(spaetstand, 1)
    b = kontext_recall.messe(spaetstand, 1)
    assert a["zeilen"] == b["zeilen"]
    assert a["nachher_zeichen"] == b["nachher_zeichen"]
