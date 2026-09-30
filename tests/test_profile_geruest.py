"""Ein unfertiges Profil darf keinen Test umwerfen -- und keinen Bot starten.

E.1 Frage 8 der Analyse: ein halbfertiges Padua-Profil im Baum soll den
Dortmunder Betrieb nicht blockieren. Zugleich (Frage 9) darf niemand
versehentlich einen Bot damit starten. Beides zusammen ist das Feld
``geruest`` in ``profil.toml``: ein Geruest laedt und laesst sich ansehen,
aber ``bot.main`` und ``scripts/pruefe_profil.py`` weisen es ab.
"""

import pytest

from interview_theater import anweisungen, workshop
from scripts import pruefe_profil

WURZEL = workshop._PAKET.parent / "workshop"

#: Jedes Profil, das im Baum liegt.
NAMEN = sorted(p.name for p in WURZEL.iterdir() if (p / workshop.DATEI).is_file())


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


def test_es_gibt_mindestens_dortmund_und_padua():
    assert "dortmund-2026" in NAMEN
    assert "padua-2026" in NAMEN


@pytest.mark.parametrize("name", NAMEN)
def test_jedes_profil_im_baum_laedt(name):
    """Auch das Geruest -- sonst waere schon das Danebenliegen ein Fehler."""
    profil = workshop.lade(name)
    assert profil.name == name
    assert workshop.formen(profil), "ein Formen-Katalog ist immer da"
    assert workshop.phasenliste(profil), "eine Phasenliste ist immer da"


@pytest.mark.parametrize("name", NAMEN)
def test_jedes_profil_hat_ein_liesmich(name):
    text = (WURZEL / name / "LIESMICH.md").read_text(encoding="utf-8")
    assert "eigenstaendig" in text or "eigenständig" in text or "Eigenschaft" in text
    assert len(text) > 500


@pytest.mark.parametrize("name", NAMEN)
def test_jedes_profil_erzeugt_vollstaendige_prompts(name, monkeypatch):
    """Kein Platzhalter bleibt stehen -- auch nicht im Geruest, das die
    fehlenden Werte aus der Vorgabe erbt."""
    monkeypatch.setenv(workshop.VARIABLE, name)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    for prompt in ("system", "szene", "phasen/2", "phasen/4", "phasen/6"):
        assert "{{" not in anweisungen.hole(prompt), (name, prompt)


def test_padua_ist_ein_geruest():
    profil = workshop.lade("padua-2026")
    assert profil.geruest()
    assert profil.fehlende_pflichtfelder(), (
        "ein Geruest hat leere Pflichtfelder -- sonst waere es keins")


def test_dortmund_ist_kein_geruest():
    profil = workshop.lade("dortmund-2026")
    assert not profil.geruest()
    assert profil.fehlende_pflichtfelder() == []


def test_padua_traegt_seine_eigene_sprache_und_orte():
    """Birks Entscheidung vom 29.09.2026: Padua laeuft auf Englisch, die
    Interviewsprache erkennt Whisper selbst (E5), und kein Prompt sieht einen
    Vornamen (E8)."""
    profil = workshop.lade("padua-2026")
    assert profil.wert("sprache.code") == "en"
    assert profil.wert("sprache.anrede") == "you"
    assert profil.wert("sprache.whisper") == "auto"
    assert profil.wert("datenschutz.pseudonyme") is True
    assert tuple(profil.wert("orte.beispiele")) == (
        "fermata", "piazza", "bar", "stazione")


def test_padua_bringt_keinen_italienischen_inhalt_mit():
    """Den schreibt spaeter ein Mensch. Was jetzt dastuende, waere eine
    maschinelle Uebersetzung -- und ein italienischer Prompt ist ein eigener
    Text, keine Uebersetzung (Teil C der Analyse)."""
    verz = WURZEL / "padua-2026"
    assert not (verz / "prompts").exists()
    assert not (verz / "korpus").exists()
    profil = workshop.lade("padua-2026")
    for feld in ("zielgruppe.beschreibung", "orte.beschreibung",
                 "orte.auffuehrung", "projekt.kurzbeschreibung"):
        assert profil.wert(feld) == "", feld


def test_die_pruefung_weist_ein_geruest_ab(capsys):
    """Der Gate-Weg: scripts/betrieb-start.sh laesst damit keinen Bot los."""
    assert pruefe_profil.pruefe_namen("padua-2026") == 1
    assert "Geruest" in capsys.readouterr().out


def test_die_pruefung_laesst_dortmund_durch(capsys):
    assert pruefe_profil.pruefe_namen("dortmund-2026") == 0
    assert "in Ordnung" in capsys.readouterr().out
