"""Die fuenfzehn Interviewtranskripte einmal erzeugen -- mit Opus, ueber den
Simulationsklienten.

**Das Ergebnis ist das Artefakt, nicht dieses Skript.** Die Dateien unter
``simulation/interviews/set{1,2,3}/`` liegen im Repository und werden dort
gelesen; dieses Skript hat sie einmal geschrieben und wird danach nur noch
gebraucht, wenn jemand eine Datei ersetzen will. Es laeuft deshalb **nie
automatisch** und ist kein Test.

**Warum ueberhaupt ein Modell.** Fuenfzehn Transkripte gesprochener Sprache
von Hand zu schreiben, ergibt fuenfzehn Mal dieselbe Stimme -- die der
Person, die sie geschrieben hat. Der Verdichter soll aber an Material
gemessen werden, das auseinandergeht: eine, die in Halbsaetzen spricht, eine,
die ausholt, eine, die den Satz dreimal neu anfaengt.

**Namen und Motive stehen fest** (``BESETZUNG``). Nur Themen,
Sprachmerkmale, Soll-Zitate und der Text kommen aus dem Modell. Das ist kein
halber Auftrag, sondern der Grund, aus dem sich zwei Laeufe ueberhaupt
vergleichen lassen: ``--set 1 --seed 1`` zieht dieselben fuenf Dateien wie
letzte Woche, und wenn eine Zahl sich aendert, liegt es am Prompt und nicht
an einer neu erfundenen Meryem.

**Mechanisch geprueft, nicht geglaubt** (``pruefe``): Wortzahl 250-450, jedes
Soll-Zitat woertlich im Text, Umschrift statt Umlauten, Dialogform. Faellt
eine Pruefung durch, geht der Fehler als Text zurueck ins Modell -- bis zu
``VERSUCHE`` Mal. Danach bricht das Skript fuer diese Datei ab und laesst die
alte stehen: eine halbfertige Datei waere schlimmer als eine alte.

Aufruf::

    PY=$(ls -d ~/.local/share/uv/python/cpython-3.11*/bin/python3 | head -1)
    $PY -m simulation.erzeuge_interviews            # alle fuenfzehn
    $PY -m simulation.erzeuge_interviews --set 3    # nur ein Set
    $PY -m simulation.erzeuge_interviews --nur 2-sevil-erste-liebe
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from interview_theater import zitat

from simulation import claude, material

#: So oft wird eine Datei hoechstens neu angefordert, bevor das Skript sie
#: aufgibt und die alte stehen laesst.
VERSUCHE = 4

#: Ausgabebudget. Ein Transkript von 450 Woertern plus Kopf liegt bei rund
#: 1.200 Token; der Rest ist Luft fuer einen Anlauf, der zu lang geraet und
#: sich selbst korrigiert.
MAX_TOKENS = 4000

#: Art dieses Aufrufs in der Statistik des Simulationsklienten.
ART = "interview"

#: Die feste Besetzung: (Set, Dateikennung, Name, Motiv). Namen und Motive
#: sind Vorgabe, nicht Erfindung des Modells -- siehe Moduldocstring.
BESETZUNG = (
    (1, "1-meryem-koffer", "Meryem", "der Koffer, mit dem sie gekommen ist"),
    (1, "2-ferzan-bahnhof", "Ferzan", "der Bahnhof am Ankunftstag"),
    (1, "3-aynur-winter", "Aynur", "der erste Winter hier"),
    (1, "4-ljiljana-papiere", "Ljiljana", "Papiere, Aemter, Warten"),
    (1, "5-halina-nachbarin", "Halina", "die erste Nachbarin"),
    (2, "1-fatma-erster-job", "Fatma", "der erste Job"),
    (2, "2-zeynep-mutter", "Zeynep", "ihre Mutter"),
    (2, "3-amina-kinder", "Amina", "ihre Kinder"),
    (2, "4-danijela-sprache", "Danijela", "die Sprache lernen"),
    (2, "5-guelsuen-stolz", "Guelsuen", "worauf sie stolz ist"),
    (3, "1-nadia-kueche", "Nadia", "die Kueche, ein Gericht"),
    (3, "2-sevil-erste-liebe", "Sevil", "die erste Liebe"),
    (3, "3-elvira-fernweh", "Elvira", "Fernweh, ein Sehnsuchtsort"),
    (3, "4-ayla-kleidung", "Ayla", "Kleidung, was sie traegt"),
    (3, "5-marisol-fotos", "Marisol", "Fotos, Bilder von frueher"),
)

#: Der Name der Interviewerin in allen fuenfzehn Transkripten. Eine feste
#: Person, weil es im Workshop auch eine ist -- und weil der Verdichter dann
#: lernen kann, ihre Fragen NICHT fuer Material zu halten.
INTERVIEWERIN = "Leyla"

_SYSTEM = (
    "Du schreibst erfundene Interviewtranskripte fuer eine Testsammlung. Sie "
    "dienen dazu, einen Verdichter zu messen: ein Programm, das aus einem "
    "Transkript Kernthemen und woertliche Belegzitate zieht.\n\n"
    "Die Transkripte sind FREI ERFUNDEN. Keine Zeile darf aus einem echten "
    "Interview stammen, kein Name eine reale Person meinen. Trotzdem sollen "
    "sie klingen wie gesprochene Sprache und nicht wie geschriebene: "
    "Abbrueche, Neuansaetze, 'halt', 'so', 'weisst du', Saetze, die in der "
    "Mitte kippen. Keine Literatur, keine Pointen, kein Bogen.\n\n"
    "Die Frauen haben eine Migrationsgeschichte. Sie sind verschieden: "
    "verschiedene Herkunft, verschiedenes Alter, verschiedene Art zu "
    "sprechen. Kein Elend-Ton und keine Heldinnengeschichte -- Leute, die "
    "erzaehlen, wie es war.\n\n"
    "UMSCHRIFT: schreibe ae, oe, ue, ss statt ä, ö, ü, ß. Das ganze Projekt "
    "ist so geschrieben."
)

_AUFTRAG = """Schreibe EIN Interviewtranskript.

Set {nummer} kreist um: {themenkreis}.
Diese Interviewte heisst {name}. Ihr Motiv: {motiv}.
Die Interviewerin heisst {interviewerin}.

Form: Dialog, jede Replik in einer eigenen Zeile, Sprecherin davor mit
Doppelpunkt ("{interviewerin}: ..." / "{name}: ..."). Zwischen den Repliken
eine Leerzeile. {interviewerin} fragt kurz und selten -- drei bis fuenf Mal
im ganzen Transkript; der Text gehoert {name}.

Laenge: {min}-{max} Woerter, gezaehlt ueber das ganze Transkript inklusive
Sprecherzeilen. Ziel sind rund {ziel}.

Liefere ein einziges JSON-Objekt, ohne Text davor oder danach, ohne
Code-Zaun. Genau diese Felder:
- "themen": 3 bis 4 Stichwoerter, je EIN Wort oder zwei ohne Komma
  (sie werden im Simulator zu Begriffen an der Wand, also konkret:
  "Koffer", "Warten", "Kopfkissen" -- nicht "Identitaet")
- "sprachmerkmale": 3 Stichwoerter, woran man IHRE Sprechweise erkennt
  ("kurze Saetze", "Abbrueche", "polnische Einsprengsel")
- "zitate_soll": GENAU 3 Saetze, die WOERTLICH und ZEICHENGENAU so im
  Transkript stehen. Waehle Saetze, die ein guter Verdichter als Belegzitat
  finden MUSS: konkret, sinnlich, ohne Sprechernamen davor, 5-15 Woerter,
  ein vollstaendiger Satz aus einer Replik von {name}.
- "transkript": der Dialog als ein Text mit Zeilenumbruechen

{rueckmeldung}"""

_RUECKMELDUNG = (
    "ACHTUNG, der vorige Versuch war fehlerhaft. Behebe genau das:\n{fehler}"
)

#: Woerter, die im Transkript stehen muessen, damit es nach gesprochener und
#: nicht nach geschriebener Sprache klingt. Eines genuegt -- die Pruefung ist
#: ein Netz gegen glatte Prosa, kein Stilhandbuch.
_MUENDLICH = ("halt", "so was", "weisst du", "also", "ja", "irgendwie", "ne")

_UMLAUTE = "äöüßÄÖÜ"


def _falte(text: str) -> str:
    """Kleinschreibung ohne diakritische Zeichen -- fuer den Vergleich, ob ein
    Soll-Zitat im Text steht, wenn es nur an einem Akzent scheitert."""
    ohne = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(ohne.lower().split())


def pruefe(daten: dict, name: str) -> list[str]:
    """Alle mechanischen Pruefungen an einem Modellergebnis. Leere Liste
    heisst: die Datei darf geschrieben werden.

    Dieselben Pruefungen wie in ``tests/test_simulation_material.py`` -- hier,
    damit eine kaputte Datei gar nicht erst entsteht, und dort, damit sie auch
    dann auffiele, wenn jemand eine von Hand nachtraegt."""
    fehler = []
    transkript = (daten.get("transkript") or "").strip()
    if not transkript:
        return ["Feld 'transkript' ist leer."]

    woerter = len(transkript.split())
    if not material.WOERTER_MIN <= woerter <= material.WOERTER_MAX:
        fehler.append(
            f"Das Transkript hat {woerter} Woerter, verlangt sind "
            f"{material.WOERTER_MIN}-{material.WOERTER_MAX}."
        )

    zitate = daten.get("zitate_soll") or []
    if len(zitate) != 3:
        fehler.append(f"'zitate_soll' hat {len(zitate)} Eintraege, verlangt sind 3.")
    gefaltet = _falte(transkript)
    # Geprueft mit ``zitat.pruefe`` -- genau der Funktion, die im Betrieb
    # entscheidet, ob ein Belegzitat stehen bleibt. Eine mildere Pruefung hier
    # (Kleinschreibung, Akzente weg) liesse Zitate durch, die die Kennzahl
    # ``zitate_soll`` anschliessend nie findet: der Verdichter kann nur
    # zitieren, was buchstabengenau dasteht.
    for satz in zitate:
        if not zitat.pruefe(str(satz), transkript):
            fehler.append(
                f"Das Soll-Zitat {satz!r} steht NICHT zeichengenau im Transkript "
                "(Gross-/Kleinschreibung und Satzzeichen zaehlen mit)."
            )

    for feld, wie_viele in (("themen", 3), ("sprachmerkmale", 3)):
        werte = daten.get(feld) or []
        if len(werte) < wie_viele:
            fehler.append(f"'{feld}' hat nur {len(werte)} Eintraege, noetig sind {wie_viele}.")
        if any("," in str(w) for w in werte):
            fehler.append(f"'{feld}' darf keine Kommas enthalten (Listenform im Kopf).")

    umlaute = sorted({z for z in transkript if z in _UMLAUTE})
    if umlaute:
        fehler.append(
            "Umschrift verlangt: im Transkript stehen noch " + ", ".join(umlaute)
        )

    if not re.search(rf"^{re.escape(name)}\s*:", transkript, re.MULTILINE):
        fehler.append(f"Keine Replik von {name} (Zeile '{name}: ...') gefunden.")
    if not re.search(rf"^{re.escape(INTERVIEWERIN)}\s*:", transkript, re.MULTILINE):
        fehler.append(f"Keine Frage von {INTERVIEWERIN} gefunden.")

    if not any(w in gefaltet for w in _MUENDLICH):
        fehler.append(
            "Der Text klingt geschrieben, nicht gesprochen -- kein einziges "
            "Fuellwort (halt, also, weisst du, irgendwie)."
        )
    return fehler


def _kopf(name: str, nummer: int, daten: dict) -> str:
    """Der Frontmatter-Kopf, genau in der Form, die ``material._lies_kopf``
    liest: einzeilige Listen in eckigen Klammern, Soll-Zitate als
    ``- ``-Zeilen. Die Trennung ist kein Stil: ganze Saetze enthalten Kommas,
    und eine Liste, die am Komma trennt, risse jedes Zitat in Stuecke."""
    zeilen = [
        "---",
        f"name: {name}",
        f"set: {nummer}",
        "themen: [" + ", ".join(str(t).strip() for t in daten["themen"]) + "]",
        "sprachmerkmale: ["
        + ", ".join(str(s).strip() for s in daten["sprachmerkmale"]) + "]",
        "zitate_soll:",
    ]
    zeilen += [f"  - {str(z).strip()}" for z in daten["zitate_soll"]]
    zeilen.append("---")
    return "\n".join(zeilen)


def erzeuge_eine(sim, nummer: int, kennung: str, name: str, motiv: str) -> str | None:
    """Fordert ein Transkript an, prueft es, wiederholt bei Fehlern. Liefert
    den Dateiinhalt oder None, wenn alle Versuche gescheitert sind."""
    rueckmeldung = ""
    for versuch in range(1, VERSUCHE + 1):
        auftrag = _AUFTRAG.format(
            nummer=nummer, themenkreis=material.SETS[nummer], name=name,
            motiv=motiv, interviewerin=INTERVIEWERIN,
            min=material.WOERTER_MIN, max=material.WOERTER_MAX,
            ziel=(material.WOERTER_MIN + material.WOERTER_MAX) // 2,
            rueckmeldung=rueckmeldung,
        )
        try:
            daten = sim.json_objekt(_SYSTEM, auftrag, ART, max_tokens=MAX_TOKENS)
        except claude.ClaudeFehler as fehler:
            print(f"    Versuch {versuch}: {fehler}", flush=True)
            rueckmeldung = _RUECKMELDUNG.format(fehler=str(fehler))
            continue

        fehler = pruefe(daten, name)
        if not fehler:
            return _kopf(name, nummer, daten) + "\n" + daten["transkript"].strip() + "\n"
        print(f"    Versuch {versuch}: " + "; ".join(fehler), flush=True)
        rueckmeldung = _RUECKMELDUNG.format(
            fehler="\n".join(f"- {f}" for f in fehler)
        )
    return None


def baue_argumente(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m simulation.erzeuge_interviews",
        description="Die fuenfzehn Interviewtranskripte mit Opus erzeugen. "
                    "Laeuft nie automatisch; das Ergebnis wird committet.",
    )
    p.add_argument("--set", type=int, choices=sorted(material.SETS),
                   help="nur die fuenf Dateien dieses Sets")
    p.add_argument("--nur", action="append", default=[],
                   help="nur diese Dateikennung (mehrfach moeglich)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = baue_argumente(argv)
    sim = claude.Claude()
    gescheitert = []
    try:
        for nummer, kennung, name, motiv in BESETZUNG:
            if args.set and nummer != args.set:
                continue
            if args.nur and kennung not in args.nur:
                continue
            pfad = material.VERZEICHNIS / f"set{nummer}" / f"{kennung}.md"
            print(f"  -> {pfad.relative_to(material.VERZEICHNIS.parent)}", flush=True)
            inhalt = erzeuge_eine(sim, nummer, kennung, name, motiv)
            if inhalt is None:
                gescheitert.append(kennung)
                print("     GESCHEITERT -- alte Datei bleibt stehen", flush=True)
                continue
            pfad.parent.mkdir(parents=True, exist_ok=True)
            pfad.write_text(inhalt, encoding="utf-8")
            geprueft = material.lade(pfad)
            print(f"     {geprueft.woerter} Woerter, "
                  f"{len(geprueft.zitate_soll)} Soll-Zitate", flush=True)
    finally:
        sim.schliesse()
        print("\n" + str(sim.statistik.als_dict()), flush=True)

    if gescheitert:
        print("Gescheitert: " + ", ".join(gescheitert), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
