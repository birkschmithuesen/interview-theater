"""Die Phasenbewertung durch Opus (Padua-UX-Simulation, 2026-10-03): je
Phase eine Note 1-5 und bis zu fuenf Befunde, gegen die Checkliste aus
``simulation/ux_rubrik.md``.

Dazu die Erklaernote je Station (Pflichtpunkt 1, 04.10.2026,
``bewerte_erklaerung``): bewertet, ob das, was der Bot an genau dieser
Station sagt, eine gute Erklaerung fuer eine Erstnutzerin ist. Das Zitat,
das die Note begruendet, wird mechanisch gegen den vorgelegten Bot-Text
geprueft -- derselbe Posten wie ``interview_theater.dramaturgie.beleg``:
ein Judge kann jede Note begruenden, auch eine falsche, und die Begruendung
entsteht erst nach dem Urteil. Ein Retry, nicht zwei (derselbe Grund: der
zweite Fehlversuch ist ein Befund ueber den Judge, kein zweiter Versuch, es
richtig zu erraten)."""

from __future__ import annotations

from pathlib import Path

from interview_theater import zitat

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


_SYSTEM_ERKLAERUNG = """\
You are a strict UX reviewer for a participatory group-bot interface. Judge \
ONE thing: is what the bot just said to the group, at this one station of a \
workshop run, a good explanation? Rate it 1-5 (5 = excellent) against these \
six criteria:

- understandable for a first-time user with no tool experience
- short
- makes you want to continue
- says what happens now and what the group does
- no jargon
- no developer-meta

Reply with EXACTLY ONE JSON object, no markdown fence:

{{"note_erklaerung": <integer 1-5>, \
"schwaechstes_zitat": <the single weakest sentence or phrase, copied \
letter for letter from the bot texts below -- the exact substring that \
makes the explanation worse, not a paraphrase>, \
"vorschlag": <one sentence: how the bot could say it better>}}
"""

#: Der Hinweis, mit dem der eine Retry laeuft -- sagt, was falsch war, nicht
#: was geantwortet werden soll (sonst waere es die Einladung, es zu
#: erfinden). Gleicher Posten wie ``dramaturgie/beleg.py``s ``HINWEIS``.
_HINWEIS_ZITAT = (
    "Your quote does not occur in the bot texts. Copy a contiguous piece, "
    "letter for letter, from the bot texts above."
)


def _rufe_erklaerung(client, nutzer: str, art: str = "browser_erklaerung") -> dict:
    try:
        ergebnis = client.json_objekt(_SYSTEM_ERKLAERUNG, nutzer, art=art)
    except Exception:
        return {}
    return ergebnis if isinstance(ergebnis, dict) else {}


def bewerte_erklaerung(client, station: str, bot_texte: list[str]) -> dict:
    """Die Erklaernote einer Station (Pflichtpunkt 1): wie verstaendlich ist
    das, was der Bot an dieser Station gesagt hat.

    ``bot_texte`` sind die Texte der Bot-Blasen, die an dieser Station neu
    dazugekommen sind (Systemzeilen zaehlen mit -- auch sie erklaeren der
    Gruppe etwas). Ohne einen einzigen neuen Bot-Text gibt es nichts zu
    beurteilen und **keinen** Modellaufruf.

    Das Zitat wird mechanisch gegen genau diese Texte geprueft
    (``interview_theater.zitat.pruefe`` -- dieselbe Normalisierung wie
    ueberall sonst im Projekt, keine zweite, grossuegigere). Kein Treffer ->
    ein Retry mit Hinweis -> danach bleibt die Note stehen, das Zitat wird
    leer und ``zitat_unbelegt`` steht auf ``True`` (anders als bei
    ``dramaturgie/beleg.py``, das dort die ganze Note verwirft -- hier bleibt
    die Note, nur ihr Beleg gilt nicht mehr als gesichert)."""
    if not bot_texte:
        return {"note_erklaerung": None, "schwaechstes_zitat": "", "vorschlag": ""}

    material = "\n\n".join(bot_texte)
    nutzer = f"Station: {station}\n\nBot texts (in order of appearance):\n\n{material}"

    erste = _rufe_erklaerung(client, nutzer)
    if zitat.pruefe(erste.get("schwaechstes_zitat") or "", material):
        return {"note_erklaerung": erste.get("note_erklaerung"),
                "schwaechstes_zitat": (erste.get("schwaechstes_zitat") or "").strip(),
                "vorschlag": erste.get("vorschlag") or ""}

    zweite = _rufe_erklaerung(client, f"{nutzer}\n\n{_HINWEIS_ZITAT}")
    if zitat.pruefe(zweite.get("schwaechstes_zitat") or "", material):
        return {"note_erklaerung": zweite.get("note_erklaerung"),
                "schwaechstes_zitat": (zweite.get("schwaechstes_zitat") or "").strip(),
                "vorschlag": zweite.get("vorschlag") or ""}

    return {"note_erklaerung": zweite.get("note_erklaerung"),
            "schwaechstes_zitat": "", "vorschlag": zweite.get("vorschlag") or "",
            "zitat_unbelegt": True}
