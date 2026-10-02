"""Der Rahmenblock steht einmal und wird eingesetzt -- generisch geprueft.

Bis zum 06.09.2026 stand der Block "Rahmen des Stuecks" fuenfmal in den
Prompts, in drei Fassungen: lang in ``system.md`` und ``szene.md``, kurz in
``phasen/4.md`` und ``phasen/6.md``, knapp in ``phasen/5.md``. Jetzt steht
jede Fassung genau einmal als Baustein (``prompts/rahmen*.md``) und wird
ueber einen Platzhalter eingesetzt.

Dieser Test prueft **Struktur**, nicht Wortlaut: dass der Block da ist, dass
er nicht leer ist, dass er in allen fuenf Prompts ankommt und dass die
Zielgruppe aus dem Profil kommt. Was Dortmund inhaltlich zusichert -- "15 und
18", "Migrantinnenverein" -- steht in ``tests/profile/test_dortmund.py``
(D.1 der Analyse: zweistufig, damit keine Zusicherung verloren geht).
"""

from pathlib import Path

import pytest

from interview_theater import anweisungen, workshop

#: Die Prompts, in denen der Rahmen ankommen muss, mit dem Baustein, den sie
#: einsetzen.
EINSATZ = {
    "system": "rahmen",
    "szene": "rahmen",
    "phasen/4": "rahmen_kurz",
    "phasen/5": "rahmen_knapp",
    "phasen/6": "rahmen_kurz",
}

#: Die Bausteindateien im Repo, die dabei gebraucht werden.
BAUSTEINE = ("rahmen", "rahmen-kurz", "rahmen-knapp")

WURZEL = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


@pytest.mark.parametrize("name", BAUSTEINE)
def test_der_baustein_ist_da_und_nicht_leer(name):
    text = anweisungen.hole(name)
    assert text.strip()
    assert "Rahmen des Stuecks" in text


@pytest.mark.parametrize("prompt,baustein", sorted(EINSATZ.items()))
def test_der_prompt_setzt_den_baustein_ein(prompt, baustein):
    """Die Rohdatei traegt den Platzhalter, der fertige Prompt den Text."""
    roh = anweisungen._roh(prompt)
    assert "{{" + baustein + "}}" in roh, f"{prompt}.md setzt {baustein} nicht ein"
    fertig = anweisungen.hole(prompt)
    assert "{{" not in fertig
    assert "Rahmen des Stuecks" in fertig


def test_der_rahmen_nennt_die_zielgruppe_aus_dem_profil():
    zielgruppe = workshop.platzhalter()["zielgruppe"]
    assert zielgruppe
    assert zielgruppe in anweisungen.hole("rahmen")


def test_eine_andere_zielgruppe_wirkt_ohne_dateiaenderung(tmp_path, monkeypatch):
    """Der Sinn der Uebung: ein Profil aendert den Rahmen, ohne dass jemand
    eine Prompt-Datei anfasst."""
    verz = tmp_path / "padua-test"
    verz.mkdir()
    (verz / workshop.DATEI).write_text(
        'beschreibung = "Test"\n'
        '[zielgruppe]\nbeschreibung = "Jugendliche zwischen 12 und 14 Jahren"\n'
        'traeger = "Teatro Padova"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "padua-test")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    text = anweisungen.hole("system")
    assert "Jugendliche zwischen 12 und 14 Jahren" in text
    assert "Teatro Padova" in text
    assert "15 und 18" not in text


@pytest.mark.parametrize("name", BAUSTEINE)
def test_dortmund_traegt_denselben_baustein_wie_das_repo(name):
    """Das Profil dortmund-2026 fuehrt die Bausteine mit -- damit der
    Ersatzweg im Betrieb wirklich benutzt wird und nicht nur in Tests. Beide
    Fassungen muessen zeichengleich sein, sonst waere "mit Variable" etwas
    anderes als "ohne"."""
    repo = (WURZEL / "interview_theater" / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    profil = (WURZEL / "workshop" / "dortmund-2026" / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    assert profil == repo


def test_der_block_steht_nur_noch_einmal_im_repo():
    """Kein Rueckfall in die Duplikation: ausser den Bausteinen darf keine
    Prompt-Datei den Block noch ausgeschrieben tragen."""
    verz = anweisungen._VERZEICHNIS
    erlaubt = {f"{n}.md" for n in BAUSTEINE}
    for pfad in verz.rglob("*.md"):
        if pfad.name in erlaubt:
            continue
        text = pfad.read_text(encoding="utf-8")
        assert "Migrantinnenverein" not in text, pfad
        assert "zwischen 15 und 18" not in text, pfad


# --- Karte P-Fix: der Konfliktrahmen darf leer sein (Birk, Punkt 5) -------

def test_konfliktrahmen_als_strich_und_als_klammer():
    """Gesetzt: der Teilsatz steht mit seinem Satzzeichen. Leer: er ist weg.

    Die Vorlagen (``sprachen/en/prompts/rahmen*.md``) koennen nicht rechnen --
    deshalb rechnet ``workshop.platzhalter()``. Ohne das stuende in einem
    englischen Padua-Prompt "conflict may be serious -- ." bzw.
    "Conflict may be serious ()."."""
    werte = workshop.platzhalter()
    erlaubt = werte["konflikt_erlaubt"]
    assert erlaubt, "das Vorgabeprofil hat einen Konfliktrahmen"
    assert werte["konflikt_erlaubt_strich"] == f" -- {erlaubt}"
    assert werte["konflikt_erlaubt_klammer"] == f" ({erlaubt})"


def test_leerer_konfliktrahmen_laesst_nichts_uebrig(tmp_path, monkeypatch):
    verz = tmp_path / "padua-test"
    verz.mkdir()
    (verz / workshop.DATEI).write_text(
        'beschreibung = "Test"\n'
        '[zielgruppe]\nbeschreibung = "students"\n'
        '[konflikt]\nerlaubt = ""\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "padua-test")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    werte = workshop.platzhalter()
    assert werte["konflikt_erlaubt"] == ""
    assert werte["konflikt_erlaubt_strich"] == ""
    assert werte["konflikt_erlaubt_klammer"] == ""


def test_englischer_rahmen_ohne_konfliktrahmen(tmp_path, monkeypatch):
    """Padua laesst den Konfliktrahmen leer -- dann steht im Prompt
    "conflict may be serious." und sonst nichts (Karte P-Fix, Punkt 5)."""
    from interview_theater import sprache

    verz = tmp_path / "padua-test"
    verz.mkdir()
    (verz / workshop.DATEI).write_text(
        'beschreibung = "Test"\n'
        '[sprache]\ncode = "en"\nanrede = "you"\n'
        '[zielgruppe]\nbeschreibung = "students"\ntraeger = "an academy"\n'
        '[konflikt]\nerlaubt = ""\nausgeschlossen = "No glorification"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(workshop.BASIS_VARIABLE, str(tmp_path))
    monkeypatch.setenv(workshop.VARIABLE, "padua-test")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    assert sprache.code() == "en"
    for name in ("rahmen", "rahmen-kurz"):
        roh = anweisungen.hole(name)
        # Whitespace zusammenziehen: in rahmen-kurz.md faellt der
        # Zeilenumbruch mitten in den Satz ("Conflict may be\nserious.").
        text = " ".join(roh.split())
        assert "conflict may be serious." in text.lower(), name
        assert "serious --" not in text, name
        assert "()" not in roh, name
        assert "{{" not in roh, name
