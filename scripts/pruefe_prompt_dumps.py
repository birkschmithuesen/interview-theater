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


#: Die Kopfzeilen, die ``erzeuge_prompts._schreibe`` selbst schreibt. Sie sind
#: deutsch ("=== SYSTEM (26943 Zeichen, ~9112 Token) ===") und waeren in jedem
#: englischen Dump ein Falsch-Positiv -- gemessen am 05.10.2026 genau zwei
#: Treffer je Datei, beide aus dieser Zeile.
KOPFZEILEN = ("=== ", "# ")


def teile(text: str) -> tuple[str, str]:
    """(Systemteil, Nutzerteil). Der Trenner ist ``=== NUTZER``, wie in
    ``erzeuge_prompts._schreibe``."""
    stuecke = text.split("=== NUTZER")
    return stuecke[0], (stuecke[1] if len(stuecke) > 1 else "")


def inhaltszeilen(text: str) -> list[tuple[int, str]]:
    """Nummerierte, nicht-leere Zeilen ohne die Kopfzeilen des Dumps.

    Die Nummer ist **1-basiert und auf die Datei bezogen** -- genau die Zahl,
    die die Opus-Lesung spaeter in ihrem Befund nennt, damit das Zitat
    mechanisch geprueft werden kann."""
    ergebnis = []
    for nummer, zeile in enumerate(text.splitlines(), start=1):
        knapp = zeile.strip()
        if not knapp or knapp.startswith(KOPFZEILEN):
            continue
        ergebnis.append((nummer, knapp))
    return ergebnis


#: Deutsche Funktionswoerter, die **kein** englisches Wort sind. Jedes Wort
#: hier ist am 05.10.2026 gegen die vier Dumps von 2026-10-02-padua-p2
#: gemessen worden: null Treffer. Bewusst NICHT in der Liste, weil auch
#: englisch und damit Falsch-Positive: also, was, wie, hier, war, an, in, so,
#: die, hat, man, bei.
DE_STOPWOERTER = frozenset({
    "und", "oder", "nicht", "eine", "einen", "einem", "dass", "sich", "der",
    "das", "den", "dem", "ist", "sind", "wird", "werden", "aber", "auch",
    "noch", "schon", "wenn", "weil", "ihre", "wir", "fuer", "für", "von",
    "zum", "zur", "aus", "ueber", "über", "durch", "ohne", "kann", "soll",
    "muss", "nur", "sehr", "immer", "jede", "jeder", "etwas", "nichts",
    "mehr", "weniger", "zwei", "drei", "vier", "fuenf", "fünf", "steht",
    "gibt", "wurde", "seine", "diese", "dieser", "damit", "dafuer", "dafür",
    "dabei", "dann", "dort", "woerter", "wörter", "zeichen", "deine", "euer",
    "eure", "bitte", "keine", "kein", "vielleicht", "natuerlich", "natürlich",
    "trotzdem", "deshalb", "ausserdem", "außerdem", "korrigiere", "schreibe",
})

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß]+")

#: Was Birks UX-Regeln in einem Prompt verbieten -- je Eintrag Muster und der
#: Satz, der im Bericht daneben steht. Ein Muster ohne Erklaerung ist eine
#: Zahl, die niemand nachrechnen kann.
#:
#: ACHTUNG: "Yes, save"/"No, change it again" sind zugleich die ECHTEN
#: Knopfbeschriftungen (sprachen/en/texte.toml: _TEXT_SPEICHERN_KNOPF /
#: _TEXT_ANDERS_KNOPF). Ein Treffer ist deshalb kein automatischer Fix, sondern
#: eine Frage an Birk -- siehe Task 10.
VERBOTENE_UX = (
    ("Yes, save",
     "Bestaetigungs-Zeremonie: Entscheidungen werden automatisch gespeichert "
     "und mit EINER Systemzeile plus Undo quittiert (UX-Regel 3). Zugleich die "
     "echte Knopfbeschriftung -- vor einem Fix pruefen, siehe BEFUND."),
    ("No, change it again",
     "Wie 'Yes, save': dieselbe Zeremonie, dieselbe Doppelrolle."),
    ("please fix it in the work status",
     "Schiebt die Arbeit zur Gruppe zurueck, statt einen Weg anzubieten "
     "(UX-Regel 3: jedes Speichern hat ein Undo)."),
    ("ask whether",
     "Rueckfrage vor dem Speichern: 'speichern beim ersten Mal, keine "
     "Rueckfrage davor' (AGENTS.md, Haltung 06.09.2026)."),
    ("how many scenes",
     "Zahl und Umfang entscheidet die Gruppe; der Bot schlaegt keine Anzahl "
     "vor (UX-Regel 1)."),
    ("wake word",
     "Kein Weckwort fuer einen Bot, der in der Sitzung ohnehin zuhoert "
     "(UX-Regel 4)."),
)

#: Zeilen, die eine Frageregel aufstellen UND eine Position nennen. Sie werden
#: nebeneinander gedruckt, damit ein Mensch den Widerspruch sieht -- gemessen in
#: sprachen/en/prompts/system.md: Z146 "ends with an open question", Z148
#: "BEFORE the suggestion block", Z151 "that one at the end".
FRAGEREGEL = re.compile(
    r"question.{0,80}?\b(ends?|before|after|first|last)\b"
    r"|\b(ends?|before|after|first|last)\b.{0,80}?question",
    re.IGNORECASE | re.DOTALL,
)


def deutsche_reste(text: str) -> list[tuple[int, str, str]]:
    """(Zeilennummer, Zeile, getroffenes Wort) je deutschem Funktionswort."""
    treffer = []
    for nummer, zeile in inhaltszeilen(text):
        for wort in _WORT.findall(zeile.lower()):
            if wort in DE_STOPWOERTER:
                treffer.append((nummer, zeile, wort))
    return treffer


def verbotene_muster(text: str) -> list[tuple[int, str, str]]:
    """(Zeilennummer, Muster, Erklaerung). **Nur auf den Systemteil anwenden**
    -- im Nutzerteil sind diese Wortlaute Geschichte und kein Promptfehler."""
    treffer = []
    for nummer, zeile in inhaltszeilen(text):
        for muster, erklaerung in VERBOTENE_UX:
            if muster.lower() in zeile.lower():
                treffer.append((nummer, muster, erklaerung))
    return treffer


def frageregel_zeilen(text: str) -> list[tuple[int, str]]:
    return [(n, z) for n, z in inhaltszeilen(text) if FRAGEREGEL.search(z)]


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
