"""Die Persona, die den Browser bedient (Padua-UX-Simulation, 2026-10-03):
ein Opus-Aufruf je Schritt, Bild + Elementliste herein, genau eine Aktion
als JSON heraus. Vier Personas: eine zurueckhaltende Schauspielstudentin,
die lieber tippt als klickt, eine klickfreudige Gegenstimme, und seit dem
Abnahmelauf Phase 1-2 (04.10.2026) Giulia (kreativ, antwortet dem Bot im
Charakter) und Priya (Erstnutzerin ohne Push-to-talk, fragt lieber nach als
zu raten).
"""

from __future__ import annotations

PERSONEN: dict[str, str] = {
    "student": (
        "You are a 23-year-old acting student in an English-language "
        "theatre workshop (your own English is B2). You are impatient "
        "with long forms and prefer typing full sentences over tapping "
        "buttons, but you will tap a button when it is clearly the "
        "fastest way forward or when free text would not be understood "
        "(choosing a phase, confirming a scene's form, agreeing to a "
        "consent question). You read the screen before acting, and you "
        "get mildly annoyed by a repeated or confusing prompt -- say so "
        "in your reasoning when it happens."
    ),
    "clicker": (
        "You are a 19-year-old acting student who taps everything in "
        "sight before reading it closely. You prefer a button over "
        "typing whenever one exists, even for an open question, and you "
        "are quick to tap 'something else' or the first suggestion "
        "rather than composing your own text."
    ),
    "giulia": (
        "You are Giulia, a 23-year-old acting student in Padua taking part in an "
        "English-language theatre workshop (your English is B2). You are creative "
        "and impatient with forms, you bring your own ideas, you sometimes "
        "contradict a suggestion and then change your mind. You prefer typing "
        "full sentences over tapping buttons, but you tap a button when it is "
        "clearly the fastest way forward. When the bot asks your group a "
        "question, you answer it in character instead of walking away."
    ),
    "priya": (
        "You are Priya, taking part in a theatre workshop. You have never used a "
        "chatbot for group work and you have never used push-to-talk. Your "
        "English is hesitant: short, simple sentences, now and then a small "
        "mistake. You read everything on the screen before you act. When you "
        "are not sure what a button does, you do not guess -- you ask the bot in "
        "a short message. When the bot asks you something, you answer it."
    ),
}

_SYSTEM_RAHMEN = """\
{persona}

You are testing a web app for a theatre workshop by actually using it, one \
step at a time. You will be shown a screenshot and a list of the visible \
controls. Reply with EXACTLY ONE JSON object describing your next action, \
nothing else, no markdown fence. Schema:

{{"type": "click" | "type_send" | "tab" | "phase" | "ptt" | "wait" | "done_phase" | "done_station",
 "element_id": <id from the control list below, required for "click">,
 "text": <string, required for "type_send">,
 "name": <tab name, required for "tab">,
 "nummer": <phase number, required for "phase">,
 "duration_ms": <integer, optional for "wait">,
 "offene_fragen": <optional list of short strings: what a first-time user would still wonder about on this screen; [] if nothing>,
 "begruendung": <one sentence, your in-character reason, always required>}}

Use "done_station" (or "done_phase") once you believe the current goal is complete.
Use "wait" only if the bot appears to still \
be working (a typing indicator or a growing message) and nothing else useful \
is visible yet.
"""


def _elemente_text(elemente: list[dict]) -> str:
    zeilen = []
    for e in elemente:
        teile = [f"id={e['id']}", e["art"], repr(e.get("text", ""))]
        for schluessel in ("tab", "phase", "placeholder", "value"):
            if e.get(schluessel):
                teile.append(f"{schluessel}={e[schluessel]}")
        zeilen.append(" ".join(teile))
    return "\n".join(zeilen) if zeilen else "(no visible controls)"


def baue_nutzertext(elemente: list[dict], phasenziel: str,
                    verlaufszeilen: list[str]) -> str:
    verlauf = "\n".join(verlaufszeilen[-8:]) or "(nothing said yet)"
    return (
        f"Current phase goal: {phasenziel}\n\n"
        f"Recent chat:\n{verlauf}\n\n"
        f"Visible controls:\n{_elemente_text(elemente)}"
    )


def offene_fragen(aktion: dict) -> list[str]:
    """Bereinigte Rueckfragen aus einer Aktion: hoechstens 5, nicht leer,
    je auf 200 Zeichen gekappt -- was eine Erstnutzerin auf dem Bildschirm
    noch nicht verstanden hat."""
    roh = aktion.get("offene_fragen") if isinstance(aktion, dict) else None
    if not isinstance(roh, list):
        return []
    return [f.strip()[:200] for f in roh if isinstance(f, str) and f.strip()][:5]


def naechste_aktion(client, persona_name: str, bild_png: bytes,
                    elemente: list[dict], phasenziel: str,
                    verlaufszeilen: list[str],
                    hinweis: str | None = None) -> dict:
    """Ein Opus-Aufruf (``client.json_objekt``, mit Bild) -> eine Aktion.

    Liefert bei kaputtem JSON oder einem Modellfehler eine ``wait``-Aktion
    statt zu werfen -- ein Schritt, der nichts tut, kostet nur Zeit; ein
    abgebrochener Lauf kostet den ganzen Rest der Phase. ``hinweis`` haengt
    eine zusaetzliche Zeile an den Nutzertext (z. B. eine Rueckfrage des
    Bots, die beantwortet werden soll)."""
    system = _SYSTEM_RAHMEN.format(persona=PERSONEN[persona_name])
    nutzer = baue_nutzertext(elemente, phasenziel, verlaufszeilen)
    if hinweis:
        nutzer += f"\n\n{hinweis}"
    try:
        aktion = client.json_objekt(system, nutzer, art="browser_persona",
                                    bilder=[bild_png])
    except Exception:
        return {"type": "wait", "duration_ms": 2000,
                "begruendung": "(model error, waiting)"}
    if not isinstance(aktion, dict) or "type" not in aktion:
        return {"type": "wait", "duration_ms": 2000,
                "begruendung": "(no valid action JSON)"}
    return aktion
