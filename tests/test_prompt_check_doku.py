"""Die drei Dokustellen des Prompt-Checks nennen die echten Befehle.

Eine Doku, die einen Befehl nennt, den es nicht gibt, ist schlimmer als keine:
sie kostet am Workshoptag die Zeit, die man braucht, um ihr nicht zu glauben.
"""
from pathlib import Path

README = Path("simulation/README.md")
VORLAGEN = Path("docs/flow-audit/vorlagen.md")
AGENTS = Path("AGENTS.md")

BEFEHLE = (
    "scripts.erzeuge_prompts_padua_voll",
    "scripts.pruefe_prompt_dumps",
    "scripts.pruefe_prompts_lesung",
)


def test_readme_hat_den_abschnitt_und_alle_drei_befehle():
    text = README.read_text(encoding="utf-8")
    assert "## Der Prompt-Check" in text
    for befehl in BEFEHLE:
        assert befehl in text, befehl
    assert "0 CHF" in text


def test_vorlagen_haben_den_abnahmeschritt_mit_passregel():
    text = VORLAGEN.read_text(encoding="utf-8")
    assert "## Abnahme- und END-Schritt: Prompt-Check" in text
    for befehl in BEFEHLE:
        assert befehl in text, befehl
    assert "t_0b702d1d" in text or "Eigentuemer" in text
    assert "docs/prompt-audit/" in text


def test_agents_nennt_die_drei_neuen_skripte():
    text = AGENTS.read_text(encoding="utf-8")
    for skript in ("scripts/erzeuge_prompts_padua_voll.py",
                   "scripts/pruefe_prompts_lesung.py",
                   "scripts/prompt_inventar.py"):
        assert skript in text, skript


def test_jeder_genannte_skriptpfad_existiert():
    for datei in (README, VORLAGEN, AGENTS):
        text = datei.read_text(encoding="utf-8")
        for befehl in BEFEHLE:
            if befehl in text:
                pfad = Path(befehl.replace(".", "/") + ".py")
                assert pfad.exists(), (datei.name, pfad)
