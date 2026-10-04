"""Rauchtest fuer die Synonym-/STT-Verhoerer-Zusammenfuehrung im Begriffsboard
(Birk Live-Test 04.10.2026, Prompt-Ergaenzung ohne vorherigen echten
Modelllauf -- dieser Test holt das nach, siehe Skill-Notiz).

**Kein Test, laeuft nie automatisch, kostet Geld.** Braucht echte
Zugangsdaten (IT_LLM_URL, IT_LLM_KEY, IT_LLM_MODELL) und Netzzugriff.

Drei gezielte Faelle, EN (Padua-Sprache), gegen den tatsaechlichen
``begriffsboard``-System-Prompt:
1. Phonetische STT-Verwechslung, klare Mehrheit (3:1) -- soll zusammengefuehrt
   werden, die seltenere Lesart faellt komplett weg.
2. Echte Synonym-/Schaerfungs-Entwicklung (kein STT-Fehler) -- soll ebenfalls
   zusammengefuehrt werden, mit Prosa-Spur in ``begruendung``.
3. Zwei echte, eigenstaendige Begriffe, die nur thematisch nah klingen --
   MUESSEN getrennt bleiben (Negativfall gegen Overmerging).

Aufruf:
    python -m scripts.rauchtest_begriffsboard
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from interview_theater import anweisungen, begriffsboard, db, einstellungen, llm, sprache, workshop

FAELLE = {
    "stt_phonetisch": {
        "beschreibung": (
            "Phonetische STT-Verwechslung: 'whether' (1x, falsch erkannt) vs. "
            "'weather' (3x, richtig) -- klare Mehrheit, soll zusammengefuehrt werden."
        ),
        "transkript": (
            "A: I keep thinking about the weather in this story -- the weather "
            "should decide how the characters feel.\n"
            "B: Yes, the weather is the whole mood of the piece.\n"
            "A: Right, whether changes everything about how they act.\n"
            "B: The weather at the start should be completely different from "
            "the weather at the end.\n"
        ),
        "erwartet_begriffe_enthalten_eins_von": ["weather", "wetter"],
        "erwartet_begriffe_fehlen": ["whether"],
        "erwartet_nennungen_min": {},
    },
    "synonym_schaerfung": {
        "beschreibung": (
            "Echte Entwicklung: 'robot' (zuerst) -> 'AI robot' (praeziser, "
            "spaeter) -- kein STT-Fehler, soll trotzdem zusammengefuehrt werden."
        ),
        "transkript": (
            "A: I think we need a robot character.\n"
            "B: What kind of robot?\n"
            "A: Like an AI robot, something that talks back and makes its own "
            "decisions.\n"
            "B: An AI robot is much more interesting than a normal robot.\n"
        ),
        "erwartet_begriffe_enthalten": ["AI robot"],
        "erwartet_begriffe_fehlen": ["robot"],
        "erwartet_nennungen_min": {"AI robot": 3},
    },
    "negativ_eigenstaendig": {
        "beschreibung": (
            "Negativfall: 'street' und 'rules' klingen nicht aehnlich und "
            "sind inhaltlich eigenstaendig -- MUESSEN getrennt bleiben."
        ),
        "transkript": (
            "A: The street where I grew up is important to me.\n"
            "B: And we need to talk about the rules in our community too.\n"
            "A: The street is where everything happened as a child.\n"
            "B: The rules are what held the family together.\n"
        ),
        # "rules" darf wortgleich ODER als "rules in our community" erfasst
        # sein (Schema erlaubt 1-3 Woerter) -- geprueft wird deshalb per
        # Teilstring, nicht per exaktem Abgleich.
        "erwartet_begriffe_enthalten_teilstring": ["street", "rules"],
        "erwartet_begriffe_fehlen": [],
        "erwartet_nennungen_min": {},
    },
    "rezenz_statt_haeufigkeit": {
        "beschreibung": (
            "Rezenz-Test (Birk 04.10.2026): 'garden' faellt frueh und wird "
            "dreimal wiederholt, dann nie wieder angesprochen. 'ocean' faellt "
            "erst spaet, nur einmal, aber als klare, bekraeftigte Entscheidung "
            "-- zustimmung soll fuer 'ocean' HOEHER sein als fuer 'garden', "
            "obwohl 'garden' mehr nennungen hat."
        ),
        "transkript": (
            "A: I keep thinking the garden is where we should set this.\n"
            "B: Yes, the garden, definitely the garden.\n"
            "A: The garden really is the right place.\n"
            "B: Although... actually, thinking about it more, I think the "
            "ocean is what we really want. The feeling of the ocean is "
            "exactly right for this story.\n"
            "A: Yes, the ocean. That's it. Let's go with the ocean.\n"
        ),
        "erwartet_zustimmung_hoeher": (("ocean", "ozean"), ("garden", "garten")),
    },
    "mehrheit_widerspricht_kontext": {
        "beschreibung": (
            "Konflikt-Test (Birk 04.10.2026): die STT-fehlerhafte Lesart "
            "'knight' kommt durch wiederholte Fehlerkennung oefter vor (3x) "
            "als die richtige 'night' (1x), aber nur 'night' ergibt in JEDEM "
            "Satz Sinn -- 'knight' waere grammatisch/inhaltlich Unsinn. "
            "Kontextplausibilitaet soll hier die Mehrheit ueberstimmen."
        ),
        "transkript": (
            "A: I think the whole scene should happen at knight, like late, "
            "when everyone is asleep.\n"
            "B: Yes, knight time, that's when the fear really comes out.\n"
            "A: Definitely knight -- the darkness is the whole point.\n"
            "B: Actually I said night, like the time of day, not a person in "
            "armor. Night is when the story needs to happen.\n"
        ),
        "erwartet_begriffe_enthalten_eins_von": ["night", "nacht"],
        "erwartet_begriffe_fehlen": ["knight", "ritter"],
    },
}


def _finde(board, namen) -> dict | None:
    """Findet den ersten Boardeintrag, dessen Begriff EINEN der gegebenen
    Namen (case-insensitiv) als Teilstring enthaelt -- das Modell antwortet
    trotz EN-System-Prompt manchmal auf Deutsch (beobachtet 04.10.2026), die
    Pruefung soll sprachunabhaengig funktionieren."""
    for e in board:
        b = e["begriff"].lower()
        if any(n.lower() in b for n in namen):
            return e
    return None


def _pruefe(name: str, fall: dict, board: list[dict]) -> list[str]:
    befunde = []
    begriffe = {e["begriff"] for e in board}
    begriffe_lower = {b.lower() for b in begriffe}
    for namen_a, namen_b in ([fall["erwartet_zustimmung_hoeher"]] if "erwartet_zustimmung_hoeher" in fall else []):
        treffer_a = _finde(board, namen_a)
        treffer_b = _finde(board, namen_b)
        if treffer_a is None or treffer_b is None:
            befunde.append(f"FEHLT: '{namen_a}' oder '{namen_b}' nicht im Board ({sorted(begriffe)})")
        elif treffer_a.get("zustimmung", 0) <= treffer_b.get("zustimmung", 0):
            befunde.append(
                f"REZENZ NICHT BERUECKSICHTIGT: '{treffer_a['begriff']}' (zustimmung={treffer_a.get('zustimmung')}) "
                f"nicht hoeher als '{treffer_b['begriff']}' (zustimmung={treffer_b.get('zustimmung')})"
            )
    for soll in fall.get("erwartet_begriffe_enthalten", []):
        if soll.lower() not in begriffe_lower:
            befunde.append(f"FEHLT: '{soll}' nicht im Board ({sorted(begriffe)})")
    for soll in fall.get("erwartet_begriffe_enthalten_teilstring", []):
        if not any(soll.lower() in b for b in begriffe_lower):
            befunde.append(f"FEHLT (auch als Teilstring): '{soll}' nicht im Board ({sorted(begriffe)})")
    einer_von = fall.get("erwartet_begriffe_enthalten_eins_von", [])
    if einer_von and not any(
        any(n.lower() in b for b in begriffe_lower) for n in einer_von
    ):
        befunde.append(f"FEHLT: keines von {einer_von} im Board ({sorted(begriffe)})")
    for soll_nicht in fall.get("erwartet_begriffe_fehlen", []):
        if soll_nicht.lower() in begriffe_lower:
            befunde.append(f"NICHT ZUSAMMENGEFUEHRT: '{soll_nicht}' steht noch als eigene Zeile ({sorted(begriffe)})")
    for begriff, min_nennungen in fall.get("erwartet_nennungen_min", {}).items():
        treffer = [e for e in board if e["begriff"].lower() == begriff.lower()]
        if treffer and treffer[0].get("nennungen", 0) < min_nennungen:
            befunde.append(
                f"NENNUNGEN ZU NIEDRIG: '{begriff}' hat {treffer[0].get('nennungen')}, "
                f"erwartet >= {min_nennungen} (Zaehlungen nicht addiert?)"
            )
    return befunde


def main() -> None:
    einst = einstellungen.laden()
    conn = db.verbinde(einst.db_pfad)
    db.initialisiere(conn)
    sprache.vergiss()
    workshop.vergiss()

    import os
    os.environ["IT_WORKSHOP"] = "padua-2026"
    workshop.vergiss()
    sprache.vergiss()

    system_prompt = anweisungen.hole("begriffsboard")
    print(f"System-Prompt-Laenge: {len(system_prompt)} Zeichen (EN erwartet)")
    print(f"Enthaelt 'mishear'/'phonetic': {'mishear' in system_prompt.lower() or 'phonetic' in system_prompt.lower()}")
    print()

    gesamt_befunde = {}
    with httpx.Client(timeout=90.0) as klient:
        klm = llm.LLM(einst, klient, conn)
        for name, fall in FAELLE.items():
            print(f"--- Fall: {name} ---")
            print(fall["beschreibung"])
            nutzer = (
                f"TRANSCRIPT SO FAR:\n{fall['transkript']}\n\n"
                f"BOARD SO FAR:\n[]"
            )
            ergebnis = klm.schema(
                None, system_prompt, nutzer, begriffsboard.SCHEMA,
                "rauchtest_begriffsboard",
            )
            board = ergebnis.get("board", []) if isinstance(ergebnis, dict) else []
            print(f"Board-Antwort: {json.dumps(board, ensure_ascii=False, indent=2)}")
            befunde = _pruefe(name, fall, board)
            gesamt_befunde[name] = befunde
            if befunde:
                print("BEFUNDE:")
                for b in befunde:
                    print(f"  - {b}")
            else:
                print("OK -- entspricht der Erwartung.")
            print()

    print("=== Zusammenfassung ===")
    fehlgeschlagen = 0
    for name, befunde in gesamt_befunde.items():
        status = "FAIL" if befunde else "OK"
        if befunde:
            fehlgeschlagen += 1
        print(f"{status}: {name} ({len(befunde)} Befund/e)")
    print(f"\n{len(FAELLE) - fehlgeschlagen}/{len(FAELLE)} Faelle wie erwartet.")

    conn.close()


if __name__ == "__main__":
    main()
