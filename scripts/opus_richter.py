#!/usr/bin/env python3
"""Blindrichter: bewertet die sechs Szenentexte in gemischter Reihenfolge,
ohne die Varianten-Labels zu kennen. Ein Aufruf, Opus, ohne thinking-Parameter.
"""
import json, os, random, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
from opus_messung import call, OUT

RICHTER = """Du bewertest sechs Entwuerfe fuer DIESELBE Theaterszene. Alle sechs
stammen von demselben Modell mit demselben Auftrag; sie unterscheiden sich nur in
einer technischen Einstellung, die du nicht kennst und nicht erraten sollst.

Der Auftrag lautete: Schreib Szene 1 eines Stuecks, das eine Gruppe junger Frauen
(15-18, Migrantinnenverein Dortmund) aus eigenen Interviews entwickelt. Szene 1 ist
eine Dialogszene am Kiosk. Ihre Aufgabe ist EXPOSITION: Wer sind die Figuren, wie
stehen sie zueinander, warum sind sie hier, worum geht es. Rahmen: altersgerechte,
lebensnahe oeffentliche Orte; kein Club, kein Alkohol, keine Drogen; Sprache der
Gruppe, keine Literatursprache.

Bewerte JEDEN Entwurf einzeln nach diesen Kriterien, je 1-5 (5 = am besten):
- aufgabe: Ist die Exposition geleistet? Weiss ich am Ende, wer wer ist, wie sie
  zueinander stehen, warum sie hier sind, worum es geht?
- rahmen: Rahmen-Treue (Ort, Alter, keine verbotenen Motive, Figurenzahl handhabbar)
- sprache: Sprachlichkeit -- klingt es nach diesen jungen Frauen oder nach
  Dramaturgen-Deutsch? Sind die Repliken sprechbar?
- gesamt: dein Gesamturteil fuer die Buehnentauglichkeit dieses Entwurfs

Nenne zusaetzlich fuer jeden Entwurf in "notiz" EINEN Satz: was ihn traegt oder
was ihm fehlt.

Sag am Ende in "rangfolge" die Kennungen von bester zu schlechtester, und in
"unterschied" einen kurzen Absatz: Gibt es ueberhaupt einen belastbaren
Qualitaetsunterschied zwischen den sechs, oder liegen sie im Rauschen? Sei ehrlich,
wenn du keinen siehst -- "kein Unterschied erkennbar" ist ein zulaessiges Ergebnis
und wertvoller als ein erfundener.

Antworte AUSSCHLIESSLICH mit JSON:
{"urteile": [{"kennung":"E1","aufgabe":n,"rahmen":n,"sprache":n,"gesamt":n,"notiz":"..."}, ...],
 "rangfolge": ["E?", ...], "unterschied": "..."}
"""

def main():
    dateien = sorted(glob.glob(f"{OUT}/texte/*-lauf*.txt"))
    dateien = [d for d in dateien if ".thinking." not in d]
    assert len(dateien) == 6, dateien
    rnd = random.Random(20260906)
    rnd.shuffle(dateien)
    zuordnung, teile = {}, []
    for i, d in enumerate(dateien, 1):
        k = f"E{i}"
        zuordnung[k] = os.path.basename(d)
        teile.append(f"===== ENTWURF {k} =====\n{open(d, encoding='utf-8').read().strip()}")
    json.dump(zuordnung, open(f"{OUT}/richter_zuordnung.json", "w"),
              ensure_ascii=False, indent=1)
    print("Zuordnung (dem Richter NICHT gezeigt):", zuordnung, flush=True)

    r = call({"model": "claude-opus-5", "max_tokens": 8000,
              "system": RICHTER,
              "messages": [{"role": "user", "content": "\n\n".join(teile)}]}, timeout=900)
    txt = "\n".join(c.get("text", "") for c in (r.get("body") or {}).get("content", [])
                    if c.get("type") == "text")
    open(f"{OUT}/richter_roh.txt", "w", encoding="utf-8").write(txt)
    print("STATUS", r["status"], "DAUER", r["dauer_s"], flush=True)
    print(txt)


if __name__ == "__main__":
    main()
