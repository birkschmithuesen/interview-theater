"""Bericht und Verlaufszeile eines Laufs.

Drei Dateien entstehen je Lauf:

* ``simulation/laeufe/<datum>-<mischung>-<seed>.md`` -- das ganze Transkript,
  Schritt fuer Schritt. Das ist die Datei, die man liest, wenn eine Zahl im
  Bericht ueberrascht.
* ``simulation/berichte/<datum>-<mischung>-<seed>.md`` -- die
  Kennzahlen-Tabelle, die Noten des Richters, die fuenf schlechtesten
  Bot-Antworten im Wortlaut und drei Saetze, was daraus folgen koennte.
* ``simulation/berichte/verlauf.jsonl`` -- eine Zeile je Lauf, damit sich
  zwei Prompt-Staende vergleichen lassen.

Die drei Saetze am Ende (``ableitung``) kommen **ohne Modell** zustande: sie
sind Regeln ueber den Zahlen, nachlesbar und immer gleich. Ein Modell haette
hier die Aufgabe, ueber die Arbeit eines Modells zu urteilen, das gerade ein
Modell bewertet hat -- drei Stufen Interpretation ueber einer Messung, und
niemand koennte mehr sagen, woher ein Satz kommt.
"""

from __future__ import annotations

import json
import statistics
import subprocess
from datetime import date
from pathlib import Path

from simulation import kennzahlen, richter

WURZEL = Path(__file__).resolve().parent
LAEUFE = WURZEL / "laeufe"
BERICHTE = WURZEL / "berichte"
VERLAUF = BERICHTE / "verlauf.jsonl"

#: So viele Bot-Antworten stehen im Bericht im Wortlaut.
SCHLECHTESTE = 5


def git_head() -> str:
    """Der aktuelle Commit, kurz -- die Zeile in ``verlauf.jsonl`` ist ohne
    ihn wertlos: sie soll sagen, welcher Prompt-Stand diese Zahlen erzeugt
    hat. Leerer String, wenn kein Git zur Hand ist."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=WURZEL.parent, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        return ""


def kennung(mischung: str, seed: int, tag: str | None = None) -> str:
    """``<datum>-<mischung>-<seed>`` -- der Name beider Dateien eines Laufs."""
    return f"{tag or date.today().isoformat()}-{mischung}-{seed}"


# ---------------------------------------------------------------------------
# Tabelle
# ---------------------------------------------------------------------------


def _anteil(teil: int, gesamt: int) -> str:
    if not gesamt:
        return "– (kein Fall)"
    return f"{teil}/{gesamt} ({teil / gesamt:.0%})"


def _urteil(ist, soll, gut: bool) -> str:
    return "ok" if gut else "**daneben**"


def kennzahlen_tabelle(zahlen: dict) -> list[str]:
    """Die Kennzahlen als Markdown-Tabelle: Wert, Sollwert, Urteil.

    Der Sollwert steht daneben, weil eine nackte Zahl nichts sagt: dass der
    Median einer Bot-Antwort 612 Zeichen betraegt, ist erst dann eine
    Aussage, wenn danebensteht, dass unter 700 das Ziel war."""
    stand = zahlen["arbeitsstand_vollstaendig"]
    zeilen = [
        "| Kennzahl | Wert | Soll | |",
        "|---|---|---|---|",
    ]

    def zeile(name, wert, soll, gut):
        zeilen.append(f"| {name} | {wert} | {soll} | {_urteil(wert, soll, gut)} |")

    zeile("phase_erreicht", zahlen["phase_erreicht_name"],
          f"{zahlen['phase_soll']} · Szenen",
          zahlen["phase_erreicht"] >= zahlen["phase_soll"])
    zeile("arbeitsstand_vollstaendig",
          f"{sum(stand.values())}/{len(stand)} ("
          + ", ".join(f"{k}={v}" for k, v in stand.items()) + ")",
          f"{len(stand)}/{len(stand)}",
          sum(stand.values()) == len(stand))
    zeile("zustimmungen_gespeichert",
          _anteil(zahlen["zustimmungen_gespeichert"], zahlen["zustimmungen"]),
          "alle",
          zahlen["zustimmungen_gespeichert"] == zahlen["zustimmungen"])
    zeile("verdichtungen", zahlen["verdichtungen"], zahlen["interviews_soll"],
          zahlen["verdichtungen"] >= zahlen["interviews_soll"])
    zeile("zitate_geprueft", _anteil(zahlen["zitate_geprueft"], zahlen["themen"]),
          "alle", zahlen["zitate_geprueft"] == zahlen["themen"])
    zeile("zitate_soll gefunden",
          _anteil(zahlen["zitate_soll_gefunden"], zahlen["zitate_soll"]),
          "moeglichst viele",
          zahlen["zitate_soll_gefunden"] * 2 >= zahlen["zitate_soll"])
    zeile("echo", zahlen["echo"], 0, zahlen["echo"] == 0)
    zeile("rueckfragen_vor_szene", zahlen["rueckfragen_vor_szene"],
          f"<= {kennzahlen.SOLL_RUECKFRAGEN_VOR_SZENE}",
          zahlen["rueckfragen_vor_szene"] <= kennzahlen.SOLL_RUECKFRAGEN_VOR_SZENE)
    zeile("behauptete_schreibvorgaenge", zahlen["behauptete_schreibvorgaenge"], 0,
          zahlen["behauptete_schreibvorgaenge"] == 0)
    zeile("namensanrede", zahlen["namensanrede"], 0, zahlen["namensanrede"] == 0)
    zeile("laenge_bot (Median Zeichen)", zahlen["laenge_bot"],
          f"< {kennzahlen.SOLL_LAENGE_BOT}",
          zahlen["laenge_bot"] < kennzahlen.SOLL_LAENGE_BOT)
    zeile("notausgaenge", zahlen["notausgaenge"], 0, zahlen["notausgaenge"] == 0)
    zeile("Schritte gescheitert", len(zahlen["schritte_gescheitert"]) or "keine", 0,
          not zahlen["schritte_gescheitert"])
    return zeilen


# ---------------------------------------------------------------------------
# Noten
# ---------------------------------------------------------------------------


def noten_tabelle(ergebnis, schritte) -> list[str]:
    zeilen = [
        "| Schritt | " + " | ".join(richter.KRITERIEN) + " | Summe | Satz |",
        "|---" * (len(richter.KRITERIEN) + 3) + "|",
    ]
    for schritt in schritte:
        urteil = ergebnis.urteile.get(schritt.schluessel, {})
        noten = [urteil.get(k) for k in richter.KRITERIEN]
        summe = richter.summe(urteil)
        zeilen.append(
            f"| {schritt.titel} | "
            + " | ".join("–" if n is None else str(n) for n in noten)
            + f" | {'–' if summe is None else summe} | "
            + (urteil.get("satz") or "").replace("|", "/").replace("\n", " ")
            + " |"
        )
    return zeilen


def szenen_noten(ergebnis) -> list[str]:
    if not ergebnis.szenen_urteil:
        return ["", "Kein Szenentext in diesem Lauf (`--ohne-szene` oder gescheitert)."]
    urteil = ergebnis.szenen_urteil
    zeilen = ["", "**Szene**", ""]
    for name in richter.SZENEN_KRITERIEN:
        wert = urteil.get(name)
        zeilen.append(f"- {name}: {'–' if wert is None else wert}")
    if urteil.get("satz"):
        zeilen.append(f"- {urteil['satz']}")
    return zeilen


def schlechteste_antworten(ergebnis, schritte) -> list[str]:
    """Die fuenf schlechtesten Bot-Antworten im Wortlaut.

    Ausgewaehlt ueber die Notensumme des Abschnitts, aus dem sie stammen: der
    Richter nennt je Abschnitt seine schlechteste Antwort, und die
    schlechtesten Abschnitte stehen oben. Wortlaut, nicht Zusammenfassung --
    wer einen Prompt nachzieht, braucht den Satz, der danebenging."""
    kandidaten = []
    for schritt in schritte:
        urteil = ergebnis.urteile.get(schritt.schluessel, {})
        antwort = (urteil.get("schlechteste_antwort") or "").strip()
        if not antwort:
            continue
        summe = richter.summe(urteil)
        kandidaten.append((
            summe if summe is not None else -1, schritt.titel, antwort,
            urteil.get("begruendung", ""),
        ))
    kandidaten.sort(key=lambda k: k[0])
    if not kandidaten:
        return ["", "Der Richter hat keine Antwort als schlechteste benannt."]

    zeilen = []
    for _, titel, antwort, begruendung in kandidaten[:SCHLECHTESTE]:
        zeilen += ["", f"**{titel}**", "", "> " + antwort.replace("\n", "\n> "), ""]
        if begruendung:
            zeilen.append(f"Warum: {begruendung}")
    return zeilen


# ---------------------------------------------------------------------------
# Drei Saetze, ohne Modell
# ---------------------------------------------------------------------------

_FALLBACK = (
    "Nichts an den Zahlen sticht heraus -- der naechste Lauf sollte mit einer "
    "anderen Mischung laufen, damit sich das bestaetigen kann."
)


def ableitung(zahlen: dict) -> list[str]:
    """Drei Saetze, was aus den Zahlen folgen koennte -- Regeln, kein Modell.

    Die Reihenfolge der Regeln ist eine Rangfolge der Schaeden: eine
    behauptete, aber nicht erfolgte Speicherung ist schlimmer als eine zu
    lange Antwort, weil die Gruppe im ersten Fall im Vertrauen weiterarbeitet
    und im zweiten nur scrollt."""
    stand = zahlen["arbeitsstand_vollstaendig"]
    fehlend = [k for k, v in stand.items() if not v]
    saetze = []

    if zahlen["behauptete_schreibvorgaenge"]:
        saetze.append(
            f"{zahlen['behauptete_schreibvorgaenge']} Bot-Antworten behaupten eine "
            "Speicherung, ohne dass der Erkenner im selben Zug etwas notiert hat -- "
            "der Gespraechs-Prompt sollte das Speichern dem Erkenner ueberlassen "
            "und selbst nur vorschlagen."
        )
    if zahlen["zustimmungen"] and zahlen["zustimmungen_gespeichert"] < zahlen["zustimmungen"]:
        verpasst = zahlen["zustimmungen"] - zahlen["zustimmungen_gespeichert"]
        saetze.append(
            f"{verpasst} von {zahlen['zustimmungen']} Zustimmungen der Gruppe haben "
            "keine Notiert-Zeile ausgeloest -- das ist der Fall aus N7, und die "
            "Zustimmungsbeispiele im Erkenner-Prompt sind die Stelle, an der man "
            "nachlegt."
        )
    if fehlend:
        saetze.append(
            "Am Ende fehlen im Arbeitsstand: " + ", ".join(fehlend)
            + " -- dort steht der Bot entweder zu frueh still oder er fragt nicht "
            "nach, ob er es festhalten soll."
        )
    if zahlen["verdichtungen"] < zahlen["interviews_soll"]:
        saetze.append(
            f"Nur {zahlen['verdichtungen']} von {zahlen['interviews_soll']} "
            "Interviews wurden verdichtet -- der Bot hoert das Ende eines "
            "Interviews nicht, was am Erkenner-Prompt haengt, nicht am Verdichter."
        )
    if zahlen["zitate_soll"] and zahlen["zitate_soll_gefunden"] * 2 < zahlen["zitate_soll"]:
        saetze.append(
            f"Nur {zahlen['zitate_soll_gefunden']} von {zahlen['zitate_soll']} "
            "vorgesehenen Zitaten sind als Beleg aufgetaucht -- der Verdichter "
            "greift zu Saetzen, die die Gruppe nicht wiedererkennt."
        )
    if zahlen["echo"]:
        saetze.append(
            f"{zahlen['echo']} Antworten spiegeln die Gruppe zurueck, statt etwas "
            "Eigenes zu sagen -- die Echo-Sperre greift, der Prompt aber noch nicht."
        )
    if zahlen["laenge_bot"] >= kennzahlen.SOLL_LAENGE_BOT:
        saetze.append(
            f"Der Median einer Bot-Antwort liegt bei {zahlen['laenge_bot']} Zeichen "
            "-- auf einem Handy sind das mehrere Bildschirme, und die Gruppe liest "
            "davon den ersten."
        )
    if zahlen["namensanrede"]:
        saetze.append(
            f"{zahlen['namensanrede']} Antworten reden eine Teilnehmerin mit Namen "
            "an -- der Bot spricht zur Gruppe, nicht zu einer Person darin."
        )
    if zahlen["rueckfragen_vor_szene"] > kennzahlen.SOLL_RUECKFRAGEN_VOR_SZENE:
        saetze.append(
            f"Vor dem Szenenauftrag kamen {zahlen['rueckfragen_vor_szene']} "
            "Rueckfragen -- eine ist eine Klaerung, mehrere sind ein Verhoer."
        )

    while len(saetze) < 3:
        saetze.append(_FALLBACK)
    return saetze[:3]


# ---------------------------------------------------------------------------
# Zusammenbau
# ---------------------------------------------------------------------------


def baue(ergebnis, zahlen: dict, schritte, kopfdaten: dict) -> str:
    """Der Markdown-Bericht."""
    zeilen = [
        f"# Simulationslauf {kopfdaten['kennung']}",
        "",
        f"- Mischung: {kopfdaten['mischung']}, Seed {kopfdaten['seed']}",
        "- Interviews: " + ", ".join(i.kennung for i in ergebnis.gezogene),
        "- Stimmen: " + ", ".join(f"{p.name} ({p.profil})" for p in ergebnis.personen),
        f"- Modelle: {kopfdaten['llm_modell']} (Gespraech, Verdichter, Szene, "
        f"Stimmen), {kopfdaten['erkenner_modell']} (Erkenner, Journal, Richter)",
        f"- git-HEAD: {kopfdaten['git']}",
        f"- Dauer: {zahlen['dauer_s']:.0f} s, Kosten Bot {zahlen['chf_bot']:.4f} CHF, "
        f"Simulation {zahlen['chf_simulation']:.4f} CHF "
        f"({zahlen['aufrufe']} Aufrufe, Preise Stand {kopfdaten['preise_stand']})",
        "",
        "## Kennzahlen",
        "",
    ]
    zeilen += kennzahlen_tabelle(zahlen)
    zeilen += ["", "## Noten des Richters", ""]
    zeilen += noten_tabelle(ergebnis, schritte)
    zeilen += szenen_noten(ergebnis)
    zeilen += ["", "## Die schlechtesten Bot-Antworten", ""]
    zeilen += schlechteste_antworten(ergebnis, schritte)
    zeilen += ["", "## Was der Prompt-Pfleger daraus ableiten koennte", ""]
    zeilen += [f"{i}. {satz}" for i, satz in enumerate(ableitung(zahlen), 1)]
    if zahlen["zitate_soll_vermisst"]:
        zeilen += ["", "<details><summary>Nicht gefundene Soll-Zitate</summary>", ""]
        zeilen += [f"- {z}" for z in zahlen["zitate_soll_vermisst"]]
        zeilen += ["", "</details>"]
    return "\n".join(zeilen) + "\n"


def verlaufszeile(zahlen: dict, ergebnis, kopfdaten: dict) -> dict:
    """Eine Zeile fuer ``verlauf.jsonl``: die Kennzahlen, der git-HEAD und
    die Notensumme des Richters. Flach genug, dass ``jq`` damit arbeitet."""
    noten = [
        richter.summe(u) for u in ergebnis.urteile.values()
        if richter.summe(u) is not None
    ]
    return {
        "kennung": kopfdaten["kennung"],
        "mischung": kopfdaten["mischung"],
        "seed": kopfdaten["seed"],
        "git": kopfdaten["git"],
        "llm_modell": kopfdaten["llm_modell"],
        "erkenner_modell": kopfdaten["erkenner_modell"],
        "noten_median": statistics.median(noten) if noten else None,
        "noten_summe": sum(noten) if noten else None,
        "szene": {k: ergebnis.szenen_urteil.get(k) for k in richter.SZENEN_KRITERIEN},
        **{k: v for k, v in zahlen.items() if k != "zitate_soll_vermisst"},
    }


def schreibe(ergebnis, zahlen: dict, schritte, kopfdaten: dict,
             protokoll_text: str, bericht_datei: bool = True,
             ziel: str | Path | None = None) -> dict[str, Path | None]:
    """Schreibt Transkript, Verlaufszeile und -- auf Wunsch -- den Bericht.

    Transkript und Verlaufszeile entstehen **immer**: das eine ist die Datei,
    in die man schaut, wenn eine Zahl ueberrascht, das andere der
    Vergleichsmassstab zum naechsten Lauf. Ein Lauf, der Geld gekostet hat,
    soll beides hinterlassen, auch wenn niemand an ``--bericht`` gedacht
    hat."""
    LAEUFE.mkdir(parents=True, exist_ok=True)
    BERICHTE.mkdir(parents=True, exist_ok=True)

    lauf_pfad = LAEUFE / f"{kopfdaten['kennung']}.md"
    lauf_pfad.write_text(
        f"# Lauf {kopfdaten['kennung']}\n\n{protokoll_text}", encoding="utf-8"
    )

    bericht_pfad = None
    if bericht_datei:
        bericht_pfad = Path(ziel) if ziel else BERICHTE / f"{kopfdaten['kennung']}.md"
        bericht_pfad.parent.mkdir(parents=True, exist_ok=True)
        bericht_pfad.write_text(
            baue(ergebnis, zahlen, schritte, kopfdaten), encoding="utf-8"
        )

    with VERLAUF.open("a", encoding="utf-8") as datei:
        datei.write(json.dumps(
            verlaufszeile(zahlen, ergebnis, kopfdaten), ensure_ascii=False
        ) + "\n")

    return {"lauf": lauf_pfad, "bericht": bericht_pfad, "verlauf": VERLAUF}
