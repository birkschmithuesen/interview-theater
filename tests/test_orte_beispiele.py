"""Beispielorte und Projektbeschreibung kommen aus dem Profil (A.2, A.6).

Zwei verschiedene Dinge, die in der Analyse unter "Ort" und
"Beispiel-Material" laufen:

* **Beispielorte** -- "vielleicht treffen sie sich an der Bushaltestelle",
  "(Bushaltestelle, frueher Abend.)" in einem Layoutbeispiel. Das sind nicht
  die Orte des Stuecks (die nennt die Gruppe, ausdruecklich), sondern
  Beispiele *im Prompt*. Sie stehen als Liste im Profil, und die Prompts
  greifen mit ``{{ort_beispiel_1}}`` darauf zu.
* **Die Projektbeschreibung** -- "ein Theaterstueck ueber das Leben der
  Menschen in der Dortmunder Nordstadt ... Theater im Depot". Das ist die
  Angabe, die sich zwischen zwei Einsatzorten als Erstes aendert, und sie
  steht an zwei Stellen: lang in ``phasen/2.md`` (was die Workshopleitung
  den Gruppen erklaert hat) und kurz im Auftrag fuer den Eroeffnungstext
  (``knoepfe.ANWEISUNG_EROEFFNUNG``).
"""

import pytest

from interview_theater import anweisungen, knoepfe, workshop

#: Prompts, in denen ein Beispielort vorkommt, mit dem Platzhalter.
ORTE_IM_PROMPT = {
    "system": "ort_beispiel_1",
    "szene": "ort_beispiel_2",
    "phasen/6": "ort_beispiel_1",
    "formen/chor": "ort_beispiel_1",
    "formen/rap": "ort_beispiel_4",
}


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


@pytest.fixture
def anderer_ort(tmp_path, monkeypatch):
    verz = tmp_path / "padua-test"
    (verz / "prompts").mkdir(parents=True)
    (verz / workshop.DATEI).write_text(
        'beschreibung = "Test"\n'
        '[orte]\nbeispiele = ["fermata", "piazza", "bar", "stazione"]\n'
        '[projekt]\nkurzbeschreibung = "uno spettacolo su Padova"\n',
        encoding="utf-8",
    )
    (verz / "prompts" / "projekt.md").write_text(
        "   Facciamo uno spettacolo.\n", encoding="utf-8")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "padua-test")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    return verz


@pytest.mark.parametrize("prompt,platzhalter", sorted(ORTE_IM_PROMPT.items()))
def test_der_prompt_setzt_einen_beispielort_ein(prompt, platzhalter):
    roh = anweisungen._roh(prompt)
    assert "{{" + platzhalter + "}}" in roh
    assert "{{" not in anweisungen.hole(prompt)


def test_ein_anderes_profil_bringt_andere_beispielorte(anderer_ort):
    assert "an der fermata" in anweisungen.hole("system")
    assert "Bushaltestelle" not in anweisungen.hole("system")
    assert "(stazione, seit zwei Stunden.)" in anweisungen.hole("formen/rap")


def test_die_projektbeschreibung_steht_in_phasen_2():
    text = anweisungen.hole("phasen/2")
    assert "{{" not in text
    assert "Theater im Depot" in text
    assert "Dortmunder Nordstadt" in text


def test_ein_anderes_profil_bringt_eine_andere_projektbeschreibung(anderer_ort):
    text = anweisungen.hole("phasen/2")
    assert "Facciamo uno spettacolo." in text
    assert "Dortmunder Nordstadt" not in text


def test_der_eroeffnungsauftrag_nennt_das_projekt_aus_dem_profil(anderer_ort):
    text = anweisungen.fuelle(knoepfe.ANWEISUNG_EROEFFNUNG)
    assert "uno spettacolo su Padova" in text
    assert "Dortmunder Nordstadt" not in text
    assert "{{" not in text


def test_kein_beispielort_steht_noch_ausgeschrieben_im_prompt():
    """Kein Rueckfall: die vier Beispielorte duerfen in den Rohdateien nicht
    mehr stehen. ``erkenner.md`` ist ausgenommen -- dort sind es gemessene
    Few-Shots, die nach A.6 der Analyse zur Sprache und nicht zum Ort
    gehoeren; dasselbe gilt fuer die Negativliste ``theater-tells.md`` und
    die Handwerksbeispiele in ``formen/lied.md`` und ``formen/monolog.md``."""
    ausgenommen = {"erkenner.md", "theater-tells.md", "lied.md", "monolog.md",
                   "journal.md", "projekt.md"}
    for pfad in anweisungen._VERZEICHNIS.rglob("*.md"):
        if pfad.name in ausgenommen:
            continue
        text = pfad.read_text(encoding="utf-8")
        assert "Bushaltestelle" not in text, pfad
        assert "Dortmunder Nordstadt" not in text, pfad


def test_platzhalter_fuer_die_beispielorte():
    werte = workshop.platzhalter()
    assert werte["ort_beispiel_1"] == "Bushaltestelle"
    assert werte["ort_beispiel_4"] == "Bahnhof"
    assert werte["orte_beispiele"] == "Bushaltestelle, Schulhof, Kiosk, Bahnhof"
