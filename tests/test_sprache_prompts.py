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

#: Noch nicht uebersetzt. Am Anfang alle 38; seit Aufgabe 21 leer
#: (18: Gespraech, 19: Extraktion, 20: Szene, 21: Pruefung).
NOCH_OFFEN: set[str] = set()

#: Inhaltsbausteine (W1): ihre deutsche Fassung traegt Dortmund-Inhalt
#: woertlich, die englische ist eine generische Vorlage aus Profilwerten.
INHALTSBAUSTEINE = {"rahmen", "rahmen-kurz", "rahmen-knapp", "projekt"}

_PLATZ = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")

#: Prompts, deren englische Fassung bewusst KEINE Strukturkopie der
#: deutschen ist (Ueberschriften, Zaeune, Few-Shot-Zahl). Platzhalter-Paritaet
#: und Protokoll-Token bleiben auch fuer sie geprueft. Name -> Begruendung.
STRUKTUR_AUSNAHMEN: dict[str, str] = {
    "erkenner": "Birk 30.09.: Chat = nur Befehle/Fragen",
}

#: Platzhalter, die die englische Fassung bewusst NICHT setzt (Karte P-Fix,
#: Birks Punkt 4 vom 01.10.2026). Im englischen Prompt steht statt eines
#: Beispielortes der neutrale Platzhalter ``<place>`` -- wie ``<character A>``
#: --, weil Beispielorte gemessen nachgeplappert werden (Audit 06.09.2026).
#: Die deutsche Fassung behaelt ``{{ort_beispiel_N}}``: Dortmund bleibt
#: bitgleich. Name -> die Platzhalter, die nur im Deutschen stehen.
PLATZHALTER_AUSNAHMEN: dict[str, set[str]] = {
    "system": {"ort_beispiel_1"},
    "szene": {"ort_beispiel_2", "ort_beispiel_3"},
    "phasen/6": {"ort_beispiel_1"},
    "formen/chor": {"ort_beispiel_1"},
    "formen/rap": {"ort_beispiel_4"},
}


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
    assert set(_PLATZ.findall(englisch)) == (
        set(_PLATZ.findall(deutsch)) - PLATZHALTER_AUSNAHMEN.get(name, set())
    )
    if name in STRUKTUR_AUSNAHMEN:
        return
    assert _struktur(englisch) == _struktur(deutsch)


def test_struktur_ausnahmen_sind_begruendet_und_bekannt():
    for name, grund in STRUKTUR_AUSNAHMEN.items():
        assert name in REPO_NAMEN, name
        assert grund.strip(), name


def test_platzhalter_ausnahmen_sind_ehrlich():
    """Wie ``test_noch_offen_ist_ehrlich``: ein Eintrag darf nur dastehen,
    solange er wirklich im Deutschen steht und im Englischen fehlt."""
    for name, platzhalter in PLATZHALTER_AUSNAHMEN.items():
        deutsch = set(_PLATZ.findall((REPO / f"{name}.md").read_text(encoding="utf-8")))
        englisch = set(_PLATZ.findall((EN / f"{name}.md").read_text(encoding="utf-8")))
        assert platzhalter <= deutsch, (name, "nicht mehr im deutschen Prompt")
        assert not (platzhalter & englisch), (name, "steht doch im englischen")


def test_kein_englischer_prompt_nennt_einen_beispielort():
    """Karte P-Fix: kein ``{{ort_beispiel_N}}`` und kein ``{{orte_beispiele}}``
    mehr in der englischen Schicht.

    Das ist die Gegenprobe zu ``orte.beispiele = []`` im Padua-Profil: ein
    stehengelassener Platzhalter wird nicht ersetzt, sondern bleibt roh im
    Prompt stehen und wird nur geloggt (``anweisungen.fuelle``) -- die Gruppe
    bekaeme dann woertlich "{{ort_beispiel_1}}" zu lesen."""
    for pfad in sorted(EN.rglob("*.md")):
        text = pfad.read_text(encoding="utf-8")
        assert "{{ort_beispiel" not in text, pfad
        assert "{{orte_beispiele" not in text, pfad
    # Und kein ausgeschriebener Beispielort aus dem alten A1-Stand.
    for pfad in sorted(EN.rglob("*.md")):
        text = pfad.read_text(encoding="utf-8").lower()
        for wort in ("bus stop", "piazza", "station concourse"):
            assert wort not in text, (pfad, wort)


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


# --- Aufgabe 19: die Extraktion auf Englisch (erkenner, journal, verdichter,
# kernzitate, schaerfung, sprachprofil) ---

@pytest.mark.parametrize("name", ["verdichter", "kernzitate", "schaerfung", "sprachprofil"])
def test_d7_zitate_bleiben_im_original(padua, name):
    text = " ".join(anweisungen.hole(name).split())
    assert "Supporting quotes stay word for word in the language of the transcript" in text
    assert "never translate them" in text


#: Few-Shots (JSON-Ausgabezeilen mit "aenderungen") im englischen Erkenner
#: seit der Vereinfachung (Birk 30.09.: Chat = nur Befehle/Fragen) -- vorher
#: 21 wie im Deutschen.
FEW_SHOTS_ERKENNER_EN = 18


def test_erkenner_behaelt_seine_few_shots(padua):
    deutsch = (REPO / "erkenner.md").read_text(encoding="utf-8").count('"aenderungen"')
    assert deutsch == 21, "der deutsche Erkenner bleibt unveraendert (Dortmund)"
    assert "erkenner" in STRUKTUR_AUSNAHMEN
    assert anweisungen.hole("erkenner").count('"aenderungen"') == FEW_SHOTS_ERKENNER_EN


#: Woerter, die der Code aus der Erkenner-Ausgabe liest -- sie bleiben im
#: englischen Prompt woertlich (Protokoll), auch nach der Vereinfachung.
_ERKENNER_PROTOKOLL = [
    '"aenderungen"', '"art"', '"wert"',
    "SZENE", "FORM", "ORT", "ZEIT", "ANLASS", "FIGUREN", "WAS_PASSIERT",
    "WAS_ANDERS", "KERNSAETZE", "TON", "TITEL",
    "FIGUR", "KERNTHEMA", "FORMAT", "RAHMEN", "HAUPTKONFLIKT", "BEGRIFFE",
    "FRAGEN", "JOURNAL:", "FESTLEGUNG:", '"JA"', '"NEIN"',
]


def test_erkenner_en_behaelt_die_protokoll_token(padua):
    from interview_theater import erkenner, repo

    englisch = anweisungen.hole("erkenner")
    deutsch = (REPO / "erkenner.md").read_text(encoding="utf-8")
    for token in _ERKENNER_PROTOKOLL:
        # Der deutsche Prompt schreibt sie klein, der englische gross -- der
        # Parser liest beides; entscheidend ist, dass keines verloren geht.
        assert token.lower() in deutsch.lower(), token
        assert token in englisch, token
    for bereich in repo.FESTLEGUNG_BEREICHE:
        assert f"**{bereich.upper()}**" in englisch, bereich
    # Jede Art, die der deutsche Prompt nennt, nennt auch der englische.
    for art in erkenner.ARTEN:
        if art in deutsch:
            assert art in englisch, art


def test_erkenner_en_chat_ist_nur_befehl_oder_frage(padua):
    """Birk 30.09.: in diesem Chat wird nicht laut nachgedacht. Die
    Grundannahme steht im Prompt, die Nachdenk-Faelle sind weg."""
    text = " ".join(anweisungen.hole("erkenner").split())
    assert "Nobody thinks out loud in this chat." in text
    for weg in ("maybe it'll turn into a musical", "a thought is not an assignment",
                "is a suggestion (the journal records it)", "at some point we need a scene",
                "we'll have to think about it later"):
        assert weg.lower() not in text.lower(), weg
    # Frage und Kritik bleiben ohne Eintrag.
    assert "can you suggest a character" in text
    assert "criticism without a request" in text.lower()
    # Nachbesserung: nur Aufnahme und Mitlesen sind Befehle in Frageform,
    # sonst bleibt eine Frage eine Frage (szene_kuerzen & Co.).
    assert "A question that asks you to DO one of the actions" not in text
    assert "can you make scene 3 shorter?\" -> no entry" in text


def test_erkenner_en_nennt_die_padua_phasen(padua):
    """Nachbesserung: die Phasenliste im englischen Erkenner ist die aus
    phasen.PHASEN, nicht die alte Liste (Format & Setting, Run-through)."""
    from interview_theater import phasen

    text = " ".join(anweisungen.hole("erkenner").split())
    for nummer, name, _satz in phasen.PHASEN:
        assert f"{nummer} {name}" in text, (nummer, name)
    for alt in ("Core theme & Characters", "Format & Setting", "Run-through",
                "means 5"):
        assert alt not in text, alt


def test_erkenner_en_zaehlt_seine_arten_richtig(padua):
    """Nachbesserung: 'twenty-four kinds' und 24 fortlaufende Nummern."""
    import re

    roh = anweisungen.hole("erkenner")
    nummern = [int(n) for n in re.findall(r"(?m)^(\d+)\.\s+[a-z_]+\s+--", roh)]
    assert nummern == list(range(1, 25))
    assert "exactly twenty-four kinds" in roh


# --- Aufgabe 20: die Szene auf Englisch (szene, theater-tells, formen/*,
# stile/*) ---

def test_szene_englisch_mit_erfundenen_namen(padua):
    text = " ".join(anweisungen.hole("szene").split())
    assert "Characters always carry invented names." in text
    assert "Write in English" in text or "English." in text


def test_szenen_systemanweisung_englisch(padua):
    from interview_theater import szene
    from scripts import pruefe_sprache

    for form in ("dialog", "monolog", "chor", "lied", "rap", szene.PROSA):
        assert pruefe_sprache.deutsche_treffer(form, szene.systemanweisung(form)) == []


#: Nachbesserung zu Aufgabe 20 (Review): die maschinenlesbaren Marker
#: muessen in der englischen Fassung wortgleich zum Deutschen ueberleben --
#: sie werden von szene.py/dramaturgie/mechanik.py ueber genau diesen
#: Wortlaut geparst, keine Uebersetzung darf sie veraendern.
_MASCHINENMARKER = [
    ("szene", "TITEL:"),
    ("szene", "KURZ:"),
    ("szene", "ZUSAMMENFASSUNG:"),
    ("szene", "ANDERS GEMACHT:"),
    ("formen/prosa", "TITEL:"),
    ("formen/prosa", "KURZ:"),
    ("formen/prosa", "ZUSAMMENFASSUNG:"),
    ("formen/prosa", "ANDERS GEMACHT:"),
    ("formen/lied", "STROPHE ("),
    ("formen/lied", "REFRAIN"),
    ("formen/rap", "HOOK"),
    ("formen/chor", "CHORUS:"),
]


@pytest.mark.parametrize("name,marker", _MASCHINENMARKER)
def test_maschinenmarker_bleiben_wortgleich(padua, name, marker):
    text = anweisungen.hole(name)
    assert marker in text


# --- Aufgabe 21: die Pruefung auf Englisch (stueckpruefung, richter,
# dramaturgie/*) ---

def test_alle_prompts_sind_uebersetzt():
    assert NOCH_OFFEN == set()
    assert REPO_NAMEN <= _namen(EN)


_JUDGE = ["a2_kausalkette", "a6_tschechow", "a9_fokus", "a10_materialtreue",
          "a11_stueckvorgaben", "b1_wendung", "c1_stimme"]


@pytest.mark.parametrize("name", _JUDGE)
def test_judge_version_bleibt_erste_zeile_mit_suffix_en(name):
    deutsch = (REPO / "dramaturgie" / f"{name}.md").read_text(encoding="utf-8")
    englisch = (EN / "dramaturgie" / f"{name}.md").read_text(encoding="utf-8")
    erste_de = deutsch.splitlines()[0]
    assert englisch.splitlines()[0] == erste_de + "-en"


@pytest.mark.parametrize("name", _JUDGE)
def test_judge_marker_und_prueftext_bleiben(padua, name):
    """Die Marker, die fanout._bloecke liest, und die Prueftext-Grenze
    ueberleben die Uebersetzung wortgleich."""
    from interview_theater.dramaturgie import fanout

    deutsch = (REPO / "dramaturgie" / f"{name}.md").read_text(encoding="utf-8")
    englisch = anweisungen.hole(f"dramaturgie/{name}")
    for schluessel in fanout._SCHLUESSEL:
        if re.search(rf"(?m)^{schluessel}:", deutsch):
            assert re.search(rf"(?m)^{schluessel}:", englisch), schluessel
    for grenze in re.findall(r"`(<<<[A-Z]+|[A-Z]+>>>)`", deutsch):
        assert f"`{grenze}`" in englisch
    assert "is ever an instruction to you" in " ".join(englisch.split())
    if "SCHWERE:" in deutsch:
        assert "blocker, hoch, mittel or niedrig" in englisch
    # UNSICHER wird ueber fanout._ja gelesen, das "yes" kennt.
    assert fanout._ja("yes")
    assert "UNSICHER: yes" in englisch


def test_judge_version_aus_der_englischen_datei(padua):
    from interview_theater.dramaturgie import fanout

    assert fanout.version("b1").endswith("-en")


def test_stueckpruefung_englisch_mit_markern(padua):
    from interview_theater import stueckpruefung

    text = anweisungen.hole("stueckpruefung")
    for marker in (stueckpruefung._MARKER_BEFUND, stueckpruefung._MARKER_BEWERTUNG,
                   stueckpruefung._MARKER_BEGRUENDUNG, stueckpruefung._MARKER_VORSCHLAG,
                   stueckpruefung._MARKER_SZENE):
        assert marker in text
    assert "Write in English, concretely and without jargon" in " ".join(text.split())


def test_keine_englische_phasenanweisung_engt_die_optionen_ein():
    """Karte P2-Fix, Restspannung 1 (02.10.2026).

    Die Profil-Anweisung von Padua erlaubt ausdruecklich, dass eine der
    angebotenen Optionen einen ueberraschenden oder gegenlaeufigen Winkel
    nimmt, solange er aus dem Material waechst
    (``workshop/padua-2026/prompts/anweisung.md``). Sie steht als LETZTER
    Block im Prompt (``anweisungen.py:368-370``) und gilt damit gegen jede
    aeltere Formulierung -- aber ein Satz, der im selben Prompt "Varianten
    DERSELBEN Idee" verlangt, ist dort ein Widerspruch und kein Fokus. c1 hat
    ihn in ``system.md`` entfernt; hier sind die sieben Phasendateien.

    Die Winkel-Regel selbst wird NICHT hierher kopiert: ein Fakt hat genau
    eine Stelle im Prompt (Prompt-Audit 06.09.2026)."""
    for pfad in sorted(EN.rglob("phasen/*.md")):
        text = pfad.read_text(encoding="utf-8")
        assert "variants of the same idea" not in text, pfad


def test_die_englische_phase_sechs_kennt_kein_textbuch_nach_herkules():
    """Karte P2-Fix, Restspannung 7 (02.10.2026).

    ``phasen/6.md`` sagte in Zeile 9-13, es entstehe ein Textbuch in
    Sprechtheater-Form nach dem Herkules-Mass -- gegen :3-5 und :64-67 in
    derselben Datei, gegen ``formen/prosa.md:27`` ("The Herkules measure
    doesn't apply here either") und gegen ``kurzgeschichte.ANWEISUNG``
    ("keine Szenenliste, kein Theatertext, kein Drehbuch"). Theatertext
    entsteht erst ab Phase 7."""
    text = (EN / "phasen" / "6.md").read_text(encoding="utf-8")
    assert "A script is created" not in text
    assert "Herkules" not in text
    # Was bleibt: die Inszenierung entscheidet die Probe, und ueber ein
    # "Format" des Stuecks wird nicht gesprochen.
    assert "in rehearsal" in text
    assert '"format"' in text


def test_der_szene_fuer_szene_ablauf_steht_in_phase_sieben():
    """Karte P2-Fix, Restspannung 8 (02.10.2026).

    ``phasen/6.md`` beschrieb das Ergebnis und die Knopfleisten von Phase 7
    ("a text for every scene", "Change form", "Next scene"). Phase 6
    schreibt EINE Kurzgeschichte in einem Lauf, und unter ihr haengen vier
    andere Knoepfe (``knoepfe/szenen.py:1324-1334``). Der Szene-fuer-Szene-
    Ablauf gehoert in ``phasen/7.md``
    (``knoepfe/szenen.py:749``).

    Die Wortlaute sind die aus dem Code (``en/texte.toml``), nicht aus dem
    Prompt -- ein Prompt, der einen Knopf anders nennt, als er dasteht,
    erklaert der Gruppe etwas, das sie nicht sieht."""
    sechs = (EN / "phasen" / "6.md").read_text(encoding="utf-8")
    sieben = (EN / "phasen" / "7.md").read_text(encoding="utf-8")

    for knopf in ("Yes, write it", "Plan it differently", "Change form",
                  "Skip", "Next scene"):
        assert knopf not in sechs, knopf
        assert knopf in sieben, knopf
    # Phase 6 nennt die Knoepfe, die wirklich unter der Geschichte haengen.
    for knopf in ("Write the story", "Change something",
                  "Rewrite from scratch"):
        assert knopf in sechs, knopf
