"""AGENTS.md bleibt ein Index (Spec 2026-10-05-agents-md-index-design, Abnahme 3).

Claude Code laedt AGENTS.md in den Controller UND in jeden Subagenten. Bei
255 kB startete jeder Subagent mit ~131 k Tokens. Uebergaben und Nachweise
einer Karte gehoeren nach docs/agents/<thema>.md oder docs/handoffs/, nie an
AGENTS.md.
"""

from pathlib import Path

GRENZE = 25_000
AGENTS = Path(__file__).resolve().parent.parent / "AGENTS.md"


def test_die_grenze_ist_die_aus_der_spec():
    assert GRENZE == 25_000, "Grenze nicht anheben -- Inhalt nach docs/agents/ verschieben"


def test_agents_md_bleibt_unter_der_grenze():
    groesse = AGENTS.stat().st_size
    assert groesse <= GRENZE, (
        f"AGENTS.md hat {groesse} Bytes (> {GRENZE}). Uebergaben/Nachweise "
        "gehoeren nach docs/agents/<thema>.md oder docs/handoffs/.")
