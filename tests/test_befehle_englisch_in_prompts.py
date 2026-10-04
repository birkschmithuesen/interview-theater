import re
from pathlib import Path

import pytest

from interview_theater import sprache

WURZEL = Path(__file__).resolve().parent.parent

#: Jedes Vorkommen eines deutschen Befehlsworts nach einem Schraegstrich.
#: "/interview" und "/phase" fehlen bewusst (gleiches Wort beide Sprachen,
#: kein Befund). "/phaseklick" hat kein EN-Pendant und wird in keiner der
#: vier Dateien erwaehnt (Stand Task 1-4-Recherche) -- die Wortgrenze
#: `\b` am Ende verhindert trotzdem, dass ein Treffer auf "phase" faelschlich
#: auch "/phaseklick" einschliesst (pruefe das mit dem Positivtest-Fall
#: unten, falls du unsicher bist).
#: Das negative Lookbehind `(?<!\w)` vor dem Schraegstrich verhindert einen
#: falschen Treffer in Pfadangaben wie "interview_theater/sprache.py" (ein
#: Entwicklerkommentar, kein Befehl) -- ohne es traefe "/sprache\b" dort,
#: weil "y" vor dem Punkt kein Wortzeichen ist und der Schluss-\b passt.
DEUTSCHE_BEFEHLE = re.compile(
    r"(?<!\w)/(aufnahme|fertig|auswerten|kernthema|stueck|figur|szene|stand|"
    r"wortlaut|hilfe|leitfaden|festlegung|sprache)\b"
)

DATEIEN = [
    sprache.VERZEICHNIS / "en" / "texte.toml",
    sprache.VERZEICHNIS / "en" / "prompts" / "system.md",
    sprache.VERZEICHNIS / "en" / "prompts" / "erkenner.md",
    WURZEL / "workshop" / "padua-2026" / "profil.toml",
]


def test_positivkontrolle_erkennt_einen_deutschen_befehl(tmp_path):
    attrappe = tmp_path / "x.md"
    attrappe.write_text("Use /aufnahme to start.", encoding="utf-8")
    assert DEUTSCHE_BEFEHLE.search(attrappe.read_text(encoding="utf-8"))


@pytest.mark.parametrize("pfad", DATEIEN, ids=[str(p) for p in DATEIEN])
def test_keine_deutschen_befehle_im_englischen_profil(pfad):
    text = pfad.read_text(encoding="utf-8")
    treffer = DEUTSCHE_BEFEHLE.findall(text)
    assert treffer == [], f"{pfad}: {treffer}"
