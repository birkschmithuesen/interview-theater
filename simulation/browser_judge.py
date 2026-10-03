"""Die Phasenbewertung durch Opus (Padua-UX-Simulation, 2026-10-03): je
Phase eine Note 1-5 und bis zu fuenf Befunde, gegen die Checkliste aus
``simulation/ux_rubrik.md``."""

from __future__ import annotations

from pathlib import Path

RUBRIK_PFAD = Path(__file__).resolve().parent / "ux_rubrik.md"


def lies_rubrik() -> str:
    return RUBRIK_PFAD.read_text(encoding="utf-8")


_SYSTEM = """\
You are a strict UX reviewer for a participatory group-bot interface, \
judging ONE phase of a workshop run from screenshots and mechanical \
counters. Use the checklist below as your rubric. Reply with EXACTLY ONE \
JSON object, no markdown fence:

{{"note": <integer 1-5, 5 = excellent>,
 "befunde": [{{"text": <one sentence>, "schwere": "niedrig" | "mittel" | "hoch", \
"screenshot": <a filename from the list below, or null>}}]}}

At most 5 entries in "befunde", most severe first. Empty list if nothing is wrong.

Checklist:
{rubrik}
"""


def bewerte_phase(client, phase_nummer: int, phase_name: str,
                  screenshots: list[bytes], screenshot_namen: list[str],
                  zaehler: dict) -> dict:
    system = _SYSTEM.format(rubrik=lies_rubrik())
    nutzer = (
        f"Phase {phase_nummer}: {phase_name}\n\n"
        f"Screenshots (in order): {', '.join(screenshot_namen) or '(none)'}\n\n"
        f"Mechanical counters for this phase:\n{zaehler}"
    )
    try:
        ergebnis = client.json_objekt(system, nutzer, art="browser_judge",
                                      bilder=screenshots or None)
    except Exception:
        return {"note": None, "befunde": []}
    if not isinstance(ergebnis, dict):
        return {"note": None, "befunde": []}
    ergebnis.setdefault("note", None)
    ergebnis.setdefault("befunde", [])
    return ergebnis
