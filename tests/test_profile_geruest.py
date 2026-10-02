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


def test_padua_ist_kein_geruest_mehr():
    """Karte P hat den Inhalt aus dem Vault gefuellt und die Zeile gestrichen."""
    profil = workshop.lade("padua-2026")
    assert not profil.geruest()
    assert profil.fehlende_pflichtfelder() == []


def test_padua_hat_keine_unbelegte_annahme_mehr():
    """Karte P-Fix: Birk hat die sechs ANNAHME-Angaben am 01.10.2026
    abgenommen -- seitdem traegt jede ihre Entscheidung statt ihrer Annahme.

    Vorher hielt dieser Test fest, dass die Markierung **da** ist (Karte P);
    jetzt haelt er fest, dass sie **weg** ist und keine Wertzeile sie noch
    traegt. Die Entscheidungen: /mnt/.../padua-fabrik/entscheidungen-p.md,
    der Nachweis docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md."""
    verz = WURZEL / "padua-2026"
    assert not (verz / "korpus").exists(), "der englische Korpus liegt unter korpus/en/ (D8)"
    text = (verz / "profil.toml").read_text(encoding="utf-8")
    assert "Platzhalter A1" not in text
    annahmen = [z for z in text.splitlines()
                if "# ANNAHME (unbelegt):" in z and "=" in z.split("#", 1)[0]]
    assert annahmen == [], annahmen
    assert "Birk 01.10.2026" in text


def test_padua_traegt_birks_abgenommene_werte():
    """Die sieben Entscheidungen vom 01.10.2026 als Zusicherung -- sie stehen
    sonst nur in einem Kommentar."""
    profil = workshop.lade("padua-2026")
    orte = profil.wert("orte.beschreibung")
    assert "Venice" not in orte and "Venedig" not in orte
    assert "the group decides" in orte
    auffuehrung = profil.wert("orte.auffuehrung")
    assert "Teatro Verdi" not in auffuehrung
    assert "projected backgrounds" not in auffuehrung
    assert "black box" in auffuehrung
    assert profil.wert("konflikt.erlaubt") == ""
    assert profil.wert("konflikt.ausgeschlossen") == (
        "No interviewed person recognisable by name or address")
    assert profil.wert("orte.ausgeschlossen") == (
        "the real home or workplace of an interviewed person, "
        "recognisable by name or address",)
    assert "Teatro Verdi" not in profil.wert("zielgruppe.traeger")
    assert "Venice" not in profil.wert("projekt.kurzbeschreibung")


def test_padua_haengt_seine_verhaltensanweisung_an_jeden_gespraechsprompt(monkeypatch):
    """Karte P: die Profil-Anweisung steht in jeder Phase hinter der
    Phasenanweisung -- und nur unter Padua, nie unter Dortmund."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    anweisung = anweisungen.hole(anweisungen.PROFIL_ANWEISUNG).strip()
    assert "VORSCHLAG" not in anweisung, "die Abnahme-Marke gehoert nur in den Dump"
    for phase in range(1, 8):
        assert anweisungen.system("padua1", phase).endswith(anweisung), phase
    monkeypatch.setenv(workshop.VARIABLE, "dortmund-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    assert anweisung not in anweisungen.system("gruppe1", 1)
    assert not (WURZEL / "dortmund-2026" / "prompts" / "anweisung.md").exists()


def test_padua_phasen_und_formen_englisch():
    profil = workshop.lade("padua-2026")
    assert [n for _, n, _ in workshop.phasenliste(profil)] == [
        "Terms", "Questions", "Interviews", "Frame",
        "Prose Draft", "Rewrite", "Stage Version"]
    assert workshop.form_anzeige(profil) == ("Dialogue", "Monologue", "Chorus", "Song", "Rap")
    assert workshop.formen(profil) == ("dialog", "monolog", "chor", "lied", "rap")


@pytest.mark.parametrize("wort,nummer", [
    # "/phase Characters" steht im englischen _TEXT_PHASE_UMSCHALTEN; die
    # uebrigen nennt der englische Erkenner-Prompt noch aus der alten
    # Phasenliste -- phasen.STICHWOERTER macht die Zuordnung (Review A1).
    ("Characters", 4), ("core theme", 4), ("format", 4), ("setting", 4),
    ("story", 4), ("Frame", 4), ("Terms", 1), ("interview questions", 2),
    ("interviews", 3),
    # Alte Namen bleiben gueltig (Padua Phasen TEIL 1, 03.10.2026) --
    # ausser "Scenes as Story": das war NIE ein eigenes Stichwort von Phase
    # 6, sondern traf nur ueber den Exaktname-Treffer in nummer_fuer, weil
    # es Phase 6s NAME war. Seit Phase 6 "Rewrite" heisst, faellt die
    # Phrase auf den Stichwort-Durchgang zurueck -- und dort gewinnt Phase
    # 4s VORBESTEHENDES Stichwort "story" (Substring von "scenes as
    # story"), weil nummer_fuer Phasen aufsteigend prueft und beim ersten
    # Treffer zurueckgibt, nicht beim spezifischsten. Phase 4s "story" vor
    # diesem Umbau nicht anzutasten (gemeinsamer Code, auch von Dortmund
    # genutzt) wiegt hier schwerer als diese eine zusammengesetzte
    # Alt-Phrase -- kein Nutzer tippt "Scenes as Story" ohnehin als
    # natuerlichen Satz. Gefunden und entschieden waehrend Task-1-Ausfuehrung
    # (Padua Phasen TEIL 1, 03.10.2026); keine Aenderung an
    # phasen.nummer_fuer oder an Phase 4s Stichwoertern.
    ("Sharpening", 5), ("polish", 7),
    # Neue Namen (Padua Phasen TEIL 1, 03.10.2026):
    ("Prose Draft", 5), ("prose", 5), ("Rewrite", 6), ("Stage Version", 7),
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
    # Keine Beispielorte mehr (Birk 01.10.2026, Punkt 4): im englischen
    # Prompt steht "<place>". Die **leere Liste** steht ausdruecklich da --
    # ein geloeschter Schluessel wuerde ueber workshop._vereinige die
    # deutschen Vorgabewerte ("Bushaltestelle" ...) erben.
    assert profil.wert("orte.beispiele") == ()
    assert "beispiele" in profil.werte["orte"], "der Schluessel bleibt stehen"


def test_die_pruefung_laesst_padua_durch(capsys):
    """Karte P: pruefe_profil padua-2026 ist gruen."""
    assert pruefe_profil.pruefe_namen("padua-2026") == 0
    assert "in Ordnung" in capsys.readouterr().out


def test_die_pruefung_laesst_dortmund_durch(capsys):
    assert pruefe_profil.pruefe_namen("dortmund-2026") == 0
    assert "in Ordnung" in capsys.readouterr().out


def test_die_pruefung_sieht_die_englische_schicht(monkeypatch):
    """Karte P-Fix: unter einem englischen Profil prueft pruefe_profil die
    **wirksame** Prompt-Ebene.

    Bis dahin las ``_prompt_texte`` nur Repo und Profil. Unter
    ``sprache.code = "en"`` gilt fuer jede Datei mit englischer Fassung aber
    diese (``anweisungen._roh``): die deutsche wurde gegen Platzhalter
    geprueft, die sie nie einsetzt, und die englische gar nicht."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    texte = pruefe_profil._prompt_texte()
    dateien = [s for s in texte if s.startswith(("prompts/", "sprache/", "profil/"))]
    namen = [s.split("/", 1)[1] for s in dateien]
    assert "system.md" in namen
    # Genau EINE Ebene je Dateiname -- sonst prueft der Pruefer eine Datei,
    # die unter diesem Profil niemand liest.
    assert len(namen) == len(set(namen)), sorted(
        n for n in namen if namen.count(n) > 1)
    system = next(t for s, t in texte.items() if s.endswith("/system.md"))
    assert "<place>" in system, "die englische Fassung, nicht die deutsche"
    assert "{{ort_beispiel" not in system
