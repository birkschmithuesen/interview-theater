"""Der Einhaengepunkt: Platzhalter, Dateiersatz, Profil im Cache-Schluessel.

Geprueft wird die Mechanik aus ``anweisungen.py`` gegen ein Wegwerf-Profil in
``tmp_path`` -- nicht gegen Dortmund. Was Dortmund betrifft, steht in
``tests/test_profil_bitgleich.py`` und ``tests/profile/test_dortmund.py``.
"""

import pytest

from interview_theater import anweisungen, workshop


@pytest.fixture
def profilbaum(tmp_path, monkeypatch):
    """Ein leeres Profil ``test-2026`` unter ``tmp_path``, eingehaengt."""
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    verz = tmp_path / "test-2026"
    (verz / "prompts").mkdir(parents=True)
    (verz / workshop.DATEI).write_text(
        'beschreibung = "Testprofil"\n'
        '[sprache]\ncode = "it"\nanrede = "voi"\n'
        '[zielgruppe]\nbeschreibung = "Erwachsene"\ntraeger = "Teatro Padova"\n',
        encoding="utf-8",
    )
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield verz
    workshop.vergiss()
    anweisungen._CACHE.clear()


@pytest.fixture(autouse=True)
def ohne_profil(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


def _hinein(profilbaum, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "test-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()


# --- Platzhalter ---------------------------------------------------------

def test_text_ohne_platzhalter_bleibt_zeichengleich():
    """Der Normalfall im Repo heute -- und der Grund, warum der Umbau nichts
    kostet: kein ``{{``, keine Arbeit, kein Unterschied."""
    text = "Ein Prompt mit einer JSON-Klammer { \"a\": 1 } und ohne Platzhalter."
    assert anweisungen.fuelle(text) is text


def test_platzhalter_aus_profil_toml(profilbaum, monkeypatch):
    _hinein(profilbaum, monkeypatch)
    assert anweisungen.fuelle("Die Gruppe sind {{zielgruppe}}.") == "Die Gruppe sind Erwachsene."
    assert anweisungen.fuelle("{{anrede}}") == "voi"


def test_platzhalter_ohne_profil_nimmt_die_vorgabewerte():
    assert anweisungen.fuelle("{{zielgruppe}}") == "junge Frauen zwischen 15 und 18 Jahren"


def test_baustein_datei_wird_platzhalter(profilbaum, monkeypatch):
    (profilbaum / "prompts" / "rahmen.md").write_text(
        "Rahmen fuer {{zielgruppe}}.\n", encoding="utf-8")
    _hinein(profilbaum, monkeypatch)
    assert anweisungen.fuelle("A\n{{rahmen}}\nB") == "A\nRahmen fuer Erwachsene.\nB"


def test_baustein_im_unterverzeichnis_bekommt_unterstrich(profilbaum, monkeypatch):
    (profilbaum / "prompts" / "formen").mkdir()
    (profilbaum / "prompts" / "formen" / "commedia.md").write_text(
        "Regeln.\n", encoding="utf-8")
    _hinein(profilbaum, monkeypatch)
    assert anweisungen.fuelle("{{formen_commedia}}") == "Regeln."


def test_unbekannter_platzhalter_bleibt_stehen_und_wird_geloggt(caplog):
    anweisungen._GEMELDET.clear()
    with caplog.at_level("WARNING"):
        assert anweisungen.fuelle("{{gibtsnicht}}") == "{{gibtsnicht}}"
    assert "gibtsnicht" in caplog.text


def test_baustein_wird_heiss_nachgeladen(profilbaum, monkeypatch):
    datei = profilbaum / "prompts" / "rahmen.md"
    datei.write_text("erste Fassung\n", encoding="utf-8")
    _hinein(profilbaum, monkeypatch)
    assert anweisungen.fuelle("{{rahmen}}") == "erste Fassung"
    datei.write_text("zweite Fassung\n", encoding="utf-8")
    import os
    os.utime(datei, (0, 0))
    assert anweisungen.fuelle("{{rahmen}}") == "zweite Fassung"


# --- Dateiersatz ---------------------------------------------------------

def test_gleichnamige_datei_im_profil_ersetzt_die_repo_datei(profilbaum, monkeypatch):
    (profilbaum / "prompts" / "system.md").write_text(
        "Ganz andere Systemanweisung.\n", encoding="utf-8")
    _hinein(profilbaum, monkeypatch)
    assert anweisungen.hole("system") == "Ganz andere Systemanweisung.\n"


def test_ohne_gleichnamige_datei_gilt_die_repo_datei(profilbaum, monkeypatch):
    _hinein(profilbaum, monkeypatch)
    assert "dramaturgische" in anweisungen.hole("system")


def test_profil_prompt_zeigt_nicht_aus_dem_profil_heraus(profilbaum, monkeypatch):
    _hinein(profilbaum, monkeypatch)
    with pytest.raises(ValueError):
        anweisungen.hole("../../etc/passwd")


# --- Profil-Anweisung in system() ---------------------------------------

def test_profil_anweisung_steht_zwischen_phase_und_regiezettel(profilbaum, monkeypatch, tmp_path):
    (profilbaum / "prompts" / "anweisung.md").write_text(
        "PROFILBLOCK\n", encoding="utf-8")
    db = tmp_path / "betrieb" / "soap.db"
    db.parent.mkdir()
    (db.parent / "zusatz.md").write_text("REGIEZETTEL\n", encoding="utf-8")
    monkeypatch.setenv("IT_DB", str(db))
    _hinein(profilbaum, monkeypatch)
    text = anweisungen.system("gruppe1", 4)
    assert text.index("PROFILBLOCK") > text.index("Aktuelle Phase")
    assert text.index("PROFILBLOCK") < text.index("REGIEZETTEL")


def test_ohne_profil_anweisung_bleibt_die_systemanweisung_wie_sie_war(profilbaum, monkeypatch):
    ohne = anweisungen.system("gruppe1", 4)
    _hinein(profilbaum, monkeypatch)
    assert anweisungen.system("gruppe1", 4) == ohne


# --- Der Cache-Schluessel (D.5 der Analyse) ------------------------------

def test_cache_traegt_das_profil_im_schluessel(tmp_path, monkeypatch):
    """Zwei Profile, ein Prozess, dieselbe Prompt-Datei: der zweite Leser
    darf nicht den Text des ersten bekommen."""
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    for name, inhalt in (("eins-2026", "TEXT EINS"), ("zwei-2026", "TEXT ZWEI")):
        verz = tmp_path / name / "prompts"
        verz.mkdir(parents=True)
        (tmp_path / name / workshop.DATEI).write_text(
            f'beschreibung = "{name}"\n', encoding="utf-8")
        (verz / "system.md").write_text(inhalt + "\n", encoding="utf-8")
    workshop.vergiss()
    anweisungen._CACHE.clear()

    monkeypatch.setenv(workshop.VARIABLE, "eins-2026")
    assert anweisungen.hole("system") == "TEXT EINS\n"
    monkeypatch.setenv(workshop.VARIABLE, "zwei-2026")
    assert anweisungen.hole("system") == "TEXT ZWEI\n"
    monkeypatch.setenv(workshop.VARIABLE, "eins-2026")
    assert anweisungen.hole("system") == "TEXT EINS\n"
    monkeypatch.delenv(workshop.VARIABLE)
    assert "dramaturgische" in anweisungen.hole("system")


def test_cache_schluessel_enthaelt_profilnamen():
    anweisungen._CACHE.clear()
    anweisungen.hole("system")
    assert all(len(s) == 3 and s[0] == workshop.VORGABE_NAME for s in anweisungen._CACHE)
