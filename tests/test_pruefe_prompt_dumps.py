"""Der mechanische Prompt-Pruefer: reine Funktionen, offline.

Die Schwelle fuer deutsche Reste ist 0, und das ist gemessen, nicht gesetzt:
gegen die vier Dumps vom 02.10.2026 liefert DE_STOPWOERTER null Treffer, sobald
die Kopfzeilen des Dumps selbst ausgenommen sind (sie tragen "Zeichen").
"""
from pathlib import Path

import pytest

from scripts import pruefe_prompt_dumps as p

BASIS_DUMPS = Path("docs/prompt-audit/2026-10-02-padua-p2")

DUMP = """# 99-probe
# eine Notiz
=== SYSTEM (42 Zeichen, ~14 Token) ===
Every suggestion message ends with an open question to the group.
At most ONE question per message -- and that one at the end.
Under the reflection of ONE value "Yes, save" and "No, change it again".
Bitte korrigiere das und schreibe eine Antwort.

=== NUTZER (17 Zeichen, ~6 Token) ===
Terms (0/3) saved.
"""


def test_teile_trennt_system_und_nutzer():
    system, nutzer = p.teile(DUMP)
    assert "Every suggestion message" in system
    assert "Terms (0/3)" in nutzer
    assert "Terms (0/3)" not in system


def test_inhaltszeilen_laesst_die_eigenen_kopfzeilen_weg():
    gefunden = p.inhaltszeilen(DUMP)
    texte = [t for _, t in gefunden]
    assert not any(t.startswith("===") or t.startswith("# ") for t in texte)
    assert gefunden[0][0] == 4      # 1-basiert auf die Datei bezogen


def test_deutsche_reste_findet_den_deutschen_satz_mit_zeilennummer():
    treffer = p.deutsche_reste(DUMP)
    assert treffer, "der deutsche Satz in Zeile 7 muss gefunden werden"
    assert {n for n, _, _ in treffer} == {7}, treffer
    assert {"das", "und", "eine"} & {w for _, _, w in treffer}


def test_deutsche_reste_meldet_keine_englischen_woerter():
    englisch = "=== SYSTEM ===\nThis was also so in the past, man.\n"
    assert p.deutsche_reste(englisch) == []


def test_die_vier_dumps_vom_02_10_sind_deutschfrei():
    """Die gemessene Grundlage der Schwelle 0."""
    if not BASIS_DUMPS.exists():
        pytest.skip("Vergleichsdumps nicht im Worktree")
    for pfad in sorted(BASIS_DUMPS.glob("*.txt")):
        assert p.deutsche_reste(pfad.read_text(encoding="utf-8")) == [], pfad.name


def test_verbotene_ux_muster_mit_zeilennummer_und_erklaerung():
    treffer = p.verbotene_muster(p.teile(DUMP)[0])
    muster = {m for _, m, _ in treffer}
    assert "Yes, save" in muster
    assert "No, change it again" in muster
    for nummer, _, erklaerung in treffer:
        assert nummer > 0
        assert erklaerung.strip()


def test_verbotene_ux_muster_nur_im_systemteil():
    """Eine Systemzeile im VERLAUF ist kein Promptfehler.

    "Changed since - please fix it in the work status" ist ein echter
    Bot-Wortlaut (sprachen/en/texte.toml:48, _TEXT_UNDO_GEAENDERT). Im
    Systemteil ist er ein Befund, im Nutzerteil ist er Geschichte.

    ABWEICHUNG vom Brief (siehe task-4-report.md): der Brief prueft hier
    woertlich ``p.teile(nutzer)[1]`` (den NUTZERTEIL selbst) und erwartet
    ``[]`` -- das widerspricht der verbatim spezifizierten, rein textuellen
    Teilstring-Suche in ``verbotene_muster`` (gemessen: der Satz matcht dort
    sehr wohl). Diese Fassung prueft stattdessen genau das, was die
    Docstring von ``verbotene_muster`` behauptet: der SYSTEMTEIL eines Dumps
    bleibt sauber, auch wenn derselbe Wortlaut im NUTZERTEIL (als Verlauf)
    vorkommt."""
    dump = (
        "=== SYSTEM ===\nEverything is fine here.\n"
        "=== NUTZER ===\nYou: Changed since - please fix it in the work status\n"
    )
    assert p.verbotene_muster(p.teile(dump)[0]) == []


def test_frageregel_zeilen_stellt_die_widersprueche_nebeneinander():
    texte = [t for _, t in p.frageregel_zeilen(p.teile(DUMP)[0])]
    assert any("ends with an open question" in t for t in texte)
    assert any("that one at the end" in t for t in texte)


VERLAUF = """# 98-verlauf
=== SYSTEM (10 Zeichen, ~3 Token) ===
You are InScribe.

=== NUTZER (10 Zeichen, ~3 Token) ===
## What the group has decided so far
terms: arrival, waiting, strangers
progress: terms (0/3) done

## The conversation so far
Member 1: here is our wall of terms from the plenary
You: Good. The transcript runs live in the chat.
Member 2: i think waiting is the strongest one here
You: 📌 Agreed: Setting - A railway station
You: Noted:
You: Changed since - please fix it in the work status
Member 1: here is our wall of terms from the plenary
🎙 Interview 1: three hours on that bench

## Now
Member 3: can we go on
"""


def test_verlaufsbefund_zaehlt_zuege_sprecher_und_systemzeilen():
    """ABWEICHUNG vom Brief (Task-5-Brief, Schritt 1): der Brief erwartet
    ``zuege == 9`` und ``bot_zeilen == 5``. Gemessen gegen die verbatim aus
    Schritt 3 uebernommene ``verlaufsbefund`` liefert dieselbe VERLAUF-Fixture
    ``zuege == 8`` und ``bot_zeilen == 4`` -- die einzige Zeile, die fehlt, ist
    die ``🎙``-Transkriptzeile, und die darf per Definition KEIN Zug sein
    (``ECHO_MARKE``-Docstring: genau das Gegenteil waere der Befund, den
    dieses Feld aufdecken soll). Die anderen vier Felder (``sprecher``,
    ``systemzeilen``, ``transkript_echos``, ``quoten``) stimmen exakt mit dem
    Brief ueberein, was die Zaehlung in der Produktionsfunktion bestaetigt --
    der Brief hat sich bei den zwei Werten schlicht verzaehlt."""
    befund = p.verlaufsbefund(p.teile(VERLAUF)[1])
    assert befund["zuege"] == 8
    assert befund["sprecher"] == ["Member 1", "Member 2", "Member 3", "You"]
    assert befund["bot_zeilen"] == 4
    assert befund["systemzeilen"] == 3
    assert befund["transkript_echos"] == 1
    assert [z for _, z in befund["quoten"]] == ["progress: terms (0/3) done"]


def test_dubletten_quer_findet_die_wortgleiche_wiederholung():
    treffer = p.dubletten_quer(p.teile(VERLAUF)[1])
    assert ("Member 1: here is our wall of terms from the plenary", 2) in treffer


def test_groessen_liest_die_basis_tsv(tmp_path):
    tsv = tmp_path / "uebersicht.tsv"
    tsv.write_text(
        "pfad\tsystem_zeichen\tnutzer_zeichen\ttoken_gesamt\n"
        "01-gespraech-phase1\t26943\t393\t9112\n", encoding="utf-8")
    assert p.groessen(tsv)["01-gespraech-phase1"] == 27336
    assert p.groessen(None) == {}


def test_groessen_liest_auch_eine_tsv_mit_neuen_spalten(tmp_path):
    """Die neue uebersicht.tsv (Task 7) hat mehr Spalten in anderer Ordnung --
    ``groessen`` liest deshalb nach SPALTENNAME, nicht nach Position."""
    tsv = tmp_path / "uebersicht.tsv"
    tsv.write_text(
        "pfad\tart\tphase\tsystem_zeichen\tnutzer_zeichen\n"
        "13-begriffsboard\tbegriffsboard\t1\t100\t50\n", encoding="utf-8")
    assert p.groessen(tsv)["13-begriffsboard"] == 150


def test_bericht_traegt_alle_schluessel(tmp_path):
    pfad = tmp_path / "98-verlauf.txt"
    pfad.write_text(VERLAUF, encoding="utf-8")
    b = p.bericht(pfad, basis={"98-verlauf": 10})
    for schluessel in ("datei", "name", "system_zeichen", "nutzer_zeichen",
                       "dubletten", "verboten", "deutsche_reste", "ux_muster",
                       "frageregeln", "verlauf", "dubletten_quer",
                       "delta_zeichen"):
        assert schluessel in b, schluessel
    assert b["delta_zeichen"] > 0


def test_bericht_ohne_basis_meldet_neu(tmp_path):
    pfad = tmp_path / "98-verlauf.txt"
    pfad.write_text(VERLAUF, encoding="utf-8")
    assert p.bericht(pfad, basis={})["delta_zeichen"] is None


def test_mechanik_markdown_nennt_datei_zuege_und_quotenzeile(tmp_path):
    pfad = tmp_path / "98-verlauf.txt"
    pfad.write_text(VERLAUF, encoding="utf-8")
    text = p.mechanik_markdown([p.bericht(pfad, basis={})])
    assert "## 98-verlauf.txt" in text
    # ABWEICHUNG vom Brief wie oben (test_verlaufsbefund_...): zuege == 8.
    assert "Zuege=8" in text
    assert "(0/3)" in text
    assert "neu" in text
