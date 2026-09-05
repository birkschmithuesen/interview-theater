"""Misst die erzeugten Prompt-Dumps: Dubletten, Bloecke, verbotene Reste.

Aufruf::

    python -m scripts.pruefe_prompt_dumps docs/prompt-audit/2026-09-06
"""

import re
import sys
from collections import Counter
from pathlib import Path

#: Saetze/Zeilen ab dieser Laenge zaehlen als Dublette, wenn sie zweimal
#: vorkommen -- kuerzere Zeilen ("Ja.", "Szene 2") wiederholen sich legitim.
DUBLETTE_AB = 80

#: Was in keinem Prompt mehr stehen darf.
VERBOTEN = (
    "Kessel", "Mira", "Pola", "Pal ",
    "Kernthema & Figuren",
    "sieben Stationen",
    "Phase 7 · Durchlauf",
    "6. Szenen ",
)


def zeilen(text: str) -> list[str]:
    return [z.strip() for z in text.splitlines() if z.strip()]


def bericht(pfad: Path) -> dict:
    roh = pfad.read_text(encoding="utf-8")
    teile = roh.split("=== NUTZER")
    system = teile[0]
    nutzer = teile[1] if len(teile) > 1 else ""
    lang = [z for z in zeilen(roh) if len(z) >= DUBLETTE_AB]
    dubletten = {z: n for z, n in Counter(lang).items() if n > 1}
    verboten = [w for w in VERBOTEN if w in roh]
    return {
        "datei": pfad.name,
        "system_zeichen": len(system),
        "nutzer_zeichen": len(nutzer),
        "dubletten": dubletten,
        "verboten": verboten,
    }


def main() -> None:
    ordner = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/prompt-audit/2026-09-06")
    for pfad in sorted(ordner.glob("*.txt")):
        b = bericht(pfad)
        print(f"\n## {b['datei']}  system={b['system_zeichen']} nutzer={b['nutzer_zeichen']}")
        if b["verboten"]:
            print(f"   VERBOTEN: {b['verboten']}")
        for zeile, n in sorted(b["dubletten"].items(), key=lambda p: -p[1]):
            print(f"   {n}x  {zeile[:110]}")


if __name__ == "__main__":
    main()
