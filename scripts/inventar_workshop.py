"""Inventarskript: findet workshop-spezifische Fundstellen im Repo.

REIN ANALYTISCH -- keine Betriebswirkung, wird von keinem Bot importiert.
Grundlage fuer ``docs/workshop-profil-analyse-2026-09-06.md``.

Aufruf:  python scripts/inventar_workshop.py [--tsv]

Es sucht nach Mustern, die einen Bezug zu GENAU DIESEM Workshop haben
(Dortmund 05./06.09.2026, Migrantinnenverein, 15-18 Jahre, Deutsch,
Herkules-Maß, fuenf Formen, theatersoap-Handles) und ordnet jede Fundstelle
einer Kategorie zu. Die Kategorien entsprechen den Spalten der Inventartabelle
im Analysedokument.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent

#: Kategorie -> Regex. Reihenfolge zaehlt: die erste passende Kategorie gewinnt.
MUSTER: list[tuple[str, re.Pattern[str]]] = [
    ("Zielgruppe", re.compile(
        r"15 und 18|15-18|15–18|junge Frauen|Sechzehnjaehrige|Migrantinnen"
        r"|Maedchen|altersgerecht", re.I)),
    ("Ort", re.compile(
        r"Dortmund|Nordkiez|Schulhof|Bushaltestelle|Kiosk|Bahnhof"
        r"|oeffentlicher Platz|grossen Halle", re.I)),
    ("Sprache", re.compile(
        r"auf Deutsch|Schreibe auf Deutsch|\"language\": \"de\"|Hochdeutsch"
        r"|deutscher Satz|Soziologendeutsch", re.I)),
    ("Format-Form", re.compile(
        r"Herkules|Urban Dance|Tanztheater|Choreografin|Dialog, Monolog"
        r"|FORMEN =|Sprechtheater|Textbuch", re.I)),
    ("Rahmen-Dramaturgie", re.compile(
        r"Rahmen des Stuecks|Theaterprojekt im Verein|zweitaegig"
        r"|Buehnenbild|Requisiten|Gewaltverherrlichung", re.I)),
    ("Beispiel-Material", re.compile(
        r"Koffer|Bahnhof|Nachbarin|Vier Freundinnen|erste Liebe|Rassismus", re.I)),
    ("Betrieb-Namen", re.compile(
        r"theatersoap|lab\.artesmobiles|gruppe[1-4]\.env|Theatersoap", re.I)),
    # Wortgrenzen, sonst trifft "USA" in "Aussage" und "gemma" in "Dilemma".
    ("Modelle-Recht", re.compile(
        r"\bUSA\b|\bAnthropic\b|\bInfomaniak\b|\binfomaniak\b|\bSchweiz\b"
        r"|claude-opus|\bKimi\b|\bgemma\b|szene_usa|IT_SZENE_ANBIETER", re.I)),
]

#: Wo gesucht wird.
BEREICHE = [
    ("interview_theater/prompts", "*.md"),
    ("interview_theater", "*.py"),
    ("scripts", "*.py"),
    ("simulation", "*.py"),
    ("simulation/stimmen", "*.md"),
    ("tests", "*.py"),
    ("docs", "*"),
    (".", "*.md"),
]

AUSSCHLUSS = re.compile(r"__pycache__|/\.git/|betrieb/|prompt-audit|/laeufe/|/berichte/")


def durchsuche() -> list[tuple[str, int, str, str]]:
    treffer: list[tuple[str, int, str, str]] = []
    gesehen: set[tuple[str, int]] = set()
    for teil, glob in BEREICHE:
        basis = WURZEL / teil
        if not basis.exists():
            continue
        for pfad in sorted(basis.rglob(glob)):
            if not pfad.is_file() or AUSSCHLUSS.search(str(pfad)):
                continue
            rel = str(pfad.relative_to(WURZEL))
            try:
                zeilen = pfad.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for nummer, zeile in enumerate(zeilen, 1):
                if (rel, nummer) in gesehen:
                    continue
                for kategorie, regex in MUSTER:
                    if regex.search(zeile):
                        gesehen.add((rel, nummer))
                        treffer.append((rel, nummer, kategorie, zeile.strip()[:80]))
                        break
    return treffer


def main() -> int:
    treffer = durchsuche()
    tsv = "--tsv" in sys.argv
    if tsv:
        for rel, nummer, kategorie, text in treffer:
            print(f"{rel}\t{nummer}\t{kategorie}\t{text}")
    else:
        nach_kategorie = Counter(k for _, _, k, _ in treffer)
        nach_datei = Counter(d for d, _, _, _ in treffer)
        print(f"Fundstellen gesamt: {len(treffer)}\n")
        print("Je Kategorie:")
        for kategorie, anzahl in nach_kategorie.most_common():
            print(f"  {anzahl:5d}  {kategorie}")
        print("\nDie 25 dichtesten Dateien:")
        for datei, anzahl in nach_datei.most_common(25):
            print(f"  {anzahl:5d}  {datei}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
