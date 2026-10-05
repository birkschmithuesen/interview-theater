"""Die Agenten-Doku als ein Text: AGENTS.md (Index) plus docs/agents/**.

Seit dem Umzug vom 05.10.2026 steht der Volltext unter docs/agents/; Tests,
die pruefen, dass die Doku etwas nennt, lesen beides.
"""

from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent


def agents_doku() -> str:
    teile = [(WURZEL / "AGENTS.md").read_text(encoding="utf-8")]
    for datei in sorted((WURZEL / "docs" / "agents").rglob("*.md")):
        teile.append(datei.read_text(encoding="utf-8"))
    return "\n\n".join(teile)
