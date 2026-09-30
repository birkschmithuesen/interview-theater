"""Jede Repo-Prompt-Datei hat eine englische Fassung mit gleicher Struktur (D4).

``NOCH_OFFEN`` schrumpft mit jeder Uebersetzungsaufgabe (18-21) und ist am
Ende leer. Ein Name darf dort nur stehen, solange es die englische Datei noch
nicht gibt -- ``test_noch_offen_ist_ehrlich`` haelt das fest.
"""

import re
from pathlib import Path

import pytest

from interview_theater import anweisungen, sprache, workshop

REPO = anweisungen._VERZEICHNIS
EN = sprache.VERZEICHNIS / "en" / "prompts"


def _namen(wurzel: Path) -> set[str]:
    if not wurzel.is_dir():
        return set()
    return {str(p.relative_to(wurzel).with_suffix("")).replace("\\", "/")
            for p in wurzel.rglob("*.md")}


REPO_NAMEN = _namen(REPO)

#: Noch nicht uebersetzt. Am Anfang alle 38; Aufgabe 21 leert die Menge.
NOCH_OFFEN = set(REPO_NAMEN) - {
    # Aufgabe 18: das Gespraech.
    "system", "phasen/1", "phasen/2", "phasen/3", "phasen/4", "phasen/5",
    "phasen/6", "phasen/7", "rahmen", "rahmen-kurz", "rahmen-knapp", "projekt",
}

#: Inhaltsbausteine (W1): ihre deutsche Fassung traegt Dortmund-Inhalt
#: woertlich, die englische ist eine generische Vorlage aus Profilwerten.
INHALTSBAUSTEINE = {"rahmen", "rahmen-kurz", "rahmen-knapp", "projekt"}

_PLATZ = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")


def _struktur(text: str) -> tuple[int, int, int]:
    """Ueberschriften, Code-Zaeune, JSON-Beispielzeilen -- was eine
    Uebersetzung nicht verlieren darf (Few-Shots im Erkenner: 21)."""
    return (
        len(re.findall(r"(?m)^#{1,6} ", text)),
        len(re.findall(r"(?m)^```", text)),
        len(re.findall(r'(?m)^\{"', text)),
    )


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


def test_jede_repo_datei_hat_eine_englische_fassung():
    fehlend = sorted(REPO_NAMEN - _namen(EN) - NOCH_OFFEN)
    assert fehlend == []


def test_noch_offen_ist_ehrlich():
    assert sorted(NOCH_OFFEN & _namen(EN)) == [], "uebersetzt, aber noch in NOCH_OFFEN"


def test_keine_englische_datei_ohne_repo_gegenstueck():
    assert sorted(_namen(EN) - REPO_NAMEN) == []


@pytest.mark.parametrize("name", sorted(REPO_NAMEN - INHALTSBAUSTEINE))
def test_gleiche_platzhalter_und_struktur(name):
    en = EN / f"{name}.md"
    if not en.is_file():
        pytest.skip("noch nicht uebersetzt")
    deutsch = (REPO / f"{name}.md").read_text(encoding="utf-8")
    englisch = en.read_text(encoding="utf-8")
    assert set(_PLATZ.findall(englisch)) == set(_PLATZ.findall(deutsch))
    assert _struktur(englisch) == _struktur(deutsch)


@pytest.mark.parametrize("name", sorted(INHALTSBAUSTEINE))
def test_inhaltsbausteine_nutzen_nur_profilwerte(name):
    en = EN / f"{name}.md"
    if not en.is_file():
        pytest.skip("noch nicht uebersetzt")
    bekannt = set(workshop.platzhalter())
    assert set(_PLATZ.findall(en.read_text(encoding="utf-8"))) <= bekannt


def test_deutsch_liest_nie_die_sprachschicht(monkeypatch, tmp_path):
    """Dortmund bleibt bitgleich: bei code == 'de' gibt es keine Schicht."""
    assert anweisungen.sprach_verzeichnis() is None


def test_englisch_liest_die_sprachschicht(monkeypatch, tmp_path):
    schicht = tmp_path / "en" / "prompts"
    schicht.mkdir(parents=True)
    (schicht / "journal.md").write_text("Answer in English.", encoding="utf-8")
    monkeypatch.setattr(sprache, "VERZEICHNIS", tmp_path)
    monkeypatch.setattr(sprache, "code", lambda: "en")
    assert anweisungen.hole("journal") == "Answer in English."
    # Wo es keine englische Datei gibt, gilt weiter das Repo.
    assert anweisungen.hole("verdichter") == (REPO / "verdichter.md").read_text(encoding="utf-8")


def test_profil_schlaegt_sprachschicht(monkeypatch, tmp_path):
    schicht = tmp_path / "sprachen" / "en" / "prompts"
    schicht.mkdir(parents=True)
    (schicht / "journal.md").write_text("From the language layer.", encoding="utf-8")
    profil = tmp_path / "workshops" / "englisch-test"
    (profil / "prompts").mkdir(parents=True)
    (profil / "profil.toml").write_text(
        'beschreibung = "t"\n[sprache]\ncode = "en"\nanrede = "you"\n'
        '[zielgruppe]\nbeschreibung = "x"\n', encoding="utf-8")
    (profil / "prompts" / "journal.md").write_text("From the profile.", encoding="utf-8")
    monkeypatch.setattr(sprache, "VERZEICHNIS", tmp_path / "sprachen")
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path / "workshops"))
    monkeypatch.setenv(workshop.VARIABLE, "englisch-test")
    workshop.vergiss()
    assert anweisungen.hole("journal") == "From the profile."


def test_bausteine_aus_der_sprachschicht(monkeypatch, tmp_path):
    schicht = tmp_path / "en" / "prompts"
    schicht.mkdir(parents=True)
    (schicht / "rahmen.md").write_text("FRAME for {{zielgruppe}}", encoding="utf-8")
    monkeypatch.setattr(sprache, "VERZEICHNIS", tmp_path)
    monkeypatch.setattr(sprache, "code", lambda: "en")
    assert anweisungen.platzhalter()["rahmen"] == "FRAME for {{zielgruppe}}"


def test_formenliste_oder_je_sprache(monkeypatch):
    workshop.vergiss()
    assert " oder " in workshop.platzhalter()["formen_liste_oder"]
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert " or " in workshop.platzhalter()["formen_liste_oder"]


def test_ueberschrift_des_regiezettels_ueber_die_tabelle(monkeypatch):
    assert anweisungen.T.UEBERSCHRIFT == anweisungen.UEBERSCHRIFT
    monkeypatch.setattr(sprache, "code", lambda: "en")
    assert "Additional instruction" in anweisungen.T.UEBERSCHRIFT


# --- Aufgabe 18: das Gespraech auf Englisch (system, phasen/1-7, Rahmen) ---

@pytest.fixture
def padua(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()


def test_e8_steht_im_englischen_gespraechsprompt(padua):
    text = " ".join(anweisungen.hole("system").split())
    assert "Never address anyone by their first name." in text
    assert "Characters always carry invented names." in text


@pytest.mark.parametrize("nummer", range(1, 8))
def test_englische_phasen_sind_fokus_kein_kaefig(padua, nummer):
    text = " ".join(anweisungen.hole(f"phasen/{nummer}").split())
    assert "What you don't start on your own:" in text
    assert "the phase is your focus, not its limit" in text


@pytest.mark.parametrize("nummer", range(1, 8))
def test_englische_phasen_bewerben_keinen_befehl(padua, nummer):
    assert not re.search(r"(?<![\w/])/[a-z]{3,}", anweisungen.hole(f"phasen/{nummer}"))


def test_padua_systemanweisung_ohne_offenen_platzhalter(padua):
    for phase in range(1, 8):
        assert "{{" not in anweisungen.system("gruppe1", phase)
