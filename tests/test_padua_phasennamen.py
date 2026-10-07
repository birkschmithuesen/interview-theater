"""Padua-Phasen umbenannt (Birk 08.10.2026): 5 "Interview Selection",
6 "Scene Cards", 7 "Stage Script".

"Interview Selection" statt Birks "Interviews", weil Phase 3 so heisst. Der
Name enthaelt das "interview" der Phase 3, und ``phasen.nummer_fuer``
prueft Stichwoerter in Nummernfolge -- ``vorrang`` je Phase
(``workshop.phasen_vorrang``) laesst die Wendung vorher treffen. Die
Zuordnungen selbst stehen in ``test_profile_geruest``; hier: Leiste,
Erkenner-Prompt, und dass ein Profil ohne ``vorrang`` unveraendert bleibt.
"""

import pytest

from interview_theater import anweisungen, phasen, roadmap, sprache, web_vereint, workshop

NEU = ["Terms", "Questions", "Interviews", "Frame",
       "Interview Selection", "Scene Cards", "Stage Script"]


def _profil(monkeypatch, name):
    if name is None:
        monkeypatch.delenv(workshop.VARIABLE, raising=False)
    else:
        monkeypatch.setenv(workshop.VARIABLE, name)
    workshop.vergiss()
    sprache.vergiss()
    anweisungen._CACHE.clear()


@pytest.fixture(autouse=True)
def _aufraeumen():
    yield
    workshop.vergiss()
    sprache.vergiss()
    anweisungen._CACHE.clear()


def _lage(phase: int) -> dict:
    return {
        "stand": {}, "figuren": [], "szenen": [], "interviews": [],
        "zuordnungen": 0, "pruefrunde": None, "phase": phase,
        "interviewmodus": False, "tippt": False, "strom": None,
    }


def test_leiste_zeigt_die_neuen_namen(monkeypatch):
    _profil(monkeypatch, "padua-2026")
    daten = roadmap.aus_daten(_lage(6))
    assert [p["name"] for p in daten] == NEU
    html = web_vereint._leiste_html(daten)
    for name in ("Interview Selection", "Scene Cards", "Stage Script"):
        assert name in html
    for alt in ("Prose Draft", "Rewrite", "Stage Version"):
        assert alt not in html


def test_erkenner_nennt_die_phasen_aus_dem_profil(monkeypatch):
    _profil(monkeypatch, "padua-2026")
    text = " ".join(anweisungen.hole("erkenner").split())
    assert ("1 Terms, 2 Questions, 3 Interviews, 4 Frame, 5 Interview "
            "Selection, 6 Scene Cards, 7 Stage Script.") in text
    assert "{{phasen_kurz}}" not in text
    assert "Prose Draft" not in text


def test_padua_check_vor_phase_5_nennt_den_neuen_namen(monkeypatch):
    _profil(monkeypatch, "padua-2026")
    from interview_theater import befehle, knoepfe

    assert knoepfe.basis.T._TEXT_P5_CHECK_OK_KNOPF.endswith("start Interview Selection")
    assert "Interview Selection" in befehle.T._TEXT_P5_CHECK_HINWEIS


def test_vorrang_nur_wo_das_profil_ihn_setzt(monkeypatch):
    _profil(monkeypatch, "padua-2026")
    assert workshop.phasen_vorrang()[5][0] == "interview selection"
    _profil(monkeypatch, "dortmund-2026")
    assert not any(workshop.phasen_vorrang().values())
    _profil(monkeypatch, None)
    assert not any(workshop.phasen_vorrang().values())


@pytest.mark.parametrize("gesagt,erwartet", [
    # Dortmund-Verhalten unveraendert, auch die bekannte Schwaeche: das
    # "geschichte" der Phase 4 steckt in "szenen als geschichte".
    ("wir machen szenen als geschichte", 4),
    ("Szenen als Geschichte", 6), ("interviews", 3), ("schaerfung", 5),
])
def test_dortmund_zuordnung_bleibt(monkeypatch, gesagt, erwartet):
    _profil(monkeypatch, "dortmund-2026")
    assert phasen.nummer_fuer(gesagt) == erwartet
