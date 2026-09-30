"""Ein unfertiges Profil darf keinen Test umwerfen -- und keinen Bot starten.

E.1 Frage 8 der Analyse: ein halbfertiges Padua-Profil im Baum soll den
Dortmunder Betrieb nicht blockieren. Zugleich (Frage 9) darf niemand
versehentlich einen Bot damit starten. Beides zusammen ist das Feld
``geruest`` in ``profil.toml``: ein Geruest laedt und laesst sich ansehen,
aber ``bot.main`` und ``scripts/pruefe_profil.py`` weisen es ab.
"""

import re

import pytest

from interview_theater import anweisungen, phasen, workshop
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
    """Karte P entfernt die Zeile -- bis dahin startet kein Bot damit."""
    profil = workshop.lade("padua-2026")
    assert profil.geruest()


def test_padua_traegt_nur_platzhalter_fuer_den_inhalt():
    """A1 setzt die Methode (Sprache, Phasen, Formen), Karte P den Inhalt aus
    Birks Vault. Jede Inhaltszeile traegt deshalb den Marker."""
    verz = WURZEL / "padua-2026"
    assert not (verz / "prompts").exists(), "Rahmen-Vorlagen liegen in der Sprachschicht (W1)"
    assert not (verz / "korpus").exists(), "der englische Korpus liegt unter korpus/en/ (D8)"
    text = (verz / "profil.toml").read_text(encoding="utf-8")
    inhalt = [z for z in text.splitlines() if re.match(
        r"^(beschreibung|traeger|ausgeschlossen|auffuehrung|erlaubt|kurzbeschreibung)\s*=", z.strip())]
    # beschreibung (oben), zielgruppe.beschreibung, traeger, orte.beschreibung,
    # orte.ausgeschlossen, auffuehrung, konflikt.erlaubt,
    # konflikt.ausgeschlossen, projekt.kurzbeschreibung
    assert len(inhalt) == 9
    assert all("ANNAHME (Platzhalter A1" in z for z in inhalt), inhalt


def test_padua_phasen_und_formen_englisch():
    profil = workshop.lade("padua-2026")
    assert [n for _, n, _ in workshop.phasenliste(profil)] == [
        "Terms", "Questions", "Interviews", "Setting, Characters & Story",
        "Sharpening", "Scenes as Story", "Polish"]
    assert workshop.form_anzeige(profil) == ("Dialogue", "Monologue", "Chorus", "Song", "Rap")
    assert workshop.formen(profil) == ("dialog", "monolog", "chor", "lied", "rap")


@pytest.mark.parametrize("wort,nummer", [
    # "/phase Characters" steht im englischen _TEXT_PHASE_UMSCHALTEN; die
    # uebrigen nennt der englische Erkenner-Prompt noch aus der alten
    # Phasenliste -- phasen.STICHWOERTER macht die Zuordnung (Review A1).
    ("Characters", 4), ("core theme", 4), ("format", 4), ("setting", 4),
    ("story", 4), ("Terms", 1), ("interview questions", 2),
    ("interviews", 3), ("Sharpening", 5), ("Scenes as Story", 6),
    ("polish", 7),
])
def test_padua_stichwoerter_finden_die_phase(wort, nummer, monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    assert phasen.nummer_fuer(wort) == nummer


def test_padua_systemprompt_ohne_deutsche_reste(monkeypatch):
    """Review A1 (c): Zahlwort, Formnamen und Beispielorte kommen aus dem
    Profil -- im englischen Prompt duerfen dort weder "fuenf" noch
    italienische Orte noch eine leere Traeger-Klammer stehen."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    werte = workshop.platzhalter()
    assert werte["formen_anzahl"] == "five"
    assert werte["formen_liste"] == "Dialogue, Monologue, Chorus, Song, Rap"
    assert werte["zielgruppe_traeger"]
    for prompt in ("system", "szene", "phasen/4", "phasen/6", "formen/chor", "formen/rap"):
        text = anweisungen.hole(prompt)
        assert "{{" not in text, prompt
        assert "()" not in text, prompt
        for wort in ("fuenf", "fermata", "stazione", "Bushaltestelle"):
            assert wort not in text, (prompt, wort)


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
    # Englische Beispielorte: sie stehen in einem englischen Prompt-Satz
    # ("maybe they meet at the bus stop"); ein italienisches Wort dort waere
    # ein Fremdkoerper (Review A1). Karte P kann sie aus dem Vault ersetzen.
    assert tuple(profil.wert("orte.beispiele")) == (
        "bus stop", "piazza", "café", "station")


def test_die_pruefung_weist_ein_geruest_ab(capsys):
    """Der Gate-Weg: scripts/betrieb-start.sh laesst damit keinen Bot los."""
    assert pruefe_profil.pruefe_namen("padua-2026") == 1
    assert "Geruest" in capsys.readouterr().out


def test_die_pruefung_laesst_dortmund_durch(capsys):
    assert pruefe_profil.pruefe_namen("dortmund-2026") == 0
    assert "in Ordnung" in capsys.readouterr().out
