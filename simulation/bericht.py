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
    """Je Szene die drei Noten und den Satz des Richters -- und darunter den
    **vollstaendigen** Text.

    Ungekuerzt, mit Absicht: bei ``--set birk`` sind drei Szenen in drei
    Formen (Dialog, Lied, Rap) das eigentliche Ergebnis des Laufs, und eine
    Vorschau von sechs Zeilen sagt ueber ein Lied nichts. Die Berichte sind
    ohnehin gitignored."""
    if not ergebnis.szenen:
        return ["", "Kein Szenentext in diesem Lauf (`--ohne-szene` oder gescheitert)."]

    zeilen = []
    for szene in ergebnis.szenen:
        urteil = szene.get("urteil") or {}
        kopf = f"### Szene {szene['nummer']}: {szene['titel']}"
        if szene.get("form"):
            kopf += f" — Form: {szene['form']}"
        zeilen += ["", kopf, ""]
        for name in richter.SZENEN_KRITERIEN:
            wert = urteil.get(name)
            zeilen.append(f"- {name}: {'–' if wert is None else wert}")
        if urteil.get("satz"):
            zeilen.append(f"- {urteil['satz']}")
        zeilen += ["", "```", szene["volltext"].strip(), "```"]
    return zeilen


def _abschnittsnoten(ergebnis, schritte) -> dict[str, int]:
    """Schluessel -> Notensumme des Abschnitts. Ein nicht bewerteter
    Abschnitt bekommt -1 und steht damit ganz oben: dass der Richter dort
    ausgefallen ist, ist selbst ein Befund."""
    noten = {}
    for schritt in schritte:
        summe = richter.summe(ergebnis.urteile.get(schritt.schluessel, {}))
        noten[schritt.schluessel] = summe if summe is not None else -1
    return noten


def schlechteste_antworten(ergebnis, schritte, treffer: dict | None = None) -> list[str]:
    """Die fuenf schlechtesten Bot-Antworten im Wortlaut -- **immer**.

    Im ersten echten Lauf war dieser Abschnitt leer, obwohl in der Tabelle
    ``behauptete_schreibvorgaenge = 1`` stand und ein Abschnitt eine 7 bekam:
    der Richter hatte das Feld "schlechteste Antwort" freigelassen, weil er
    den Lauf insgesamt in Ordnung fand. Damit war die Zahl in der Tabelle
    unbelegt, und der Prompt-Pfleger konnte nichts daraus ableiten.

    Deshalb kommen die Kandidaten jetzt aus drei Quellen, in dieser Rangfolge:

    1. Antworten mit einem **mechanischen Treffer** (``treffer``): behauptete
       Schreibvorgaenge, Echo, Namensanrede, erfundene Zitate. Sie sind
       nachweisbar falsch, unabhaengig von jeder Note.
    2. Die vom Richter je Abschnitt benannte schlechteste Antwort, sortiert
       nach der Notensumme des Abschnitts.
    3. Wenn das nicht fuenf ergibt: die laengsten Antworten aus den
       schlechtesten Abschnitten -- die laengste Antwort eines schwachen
       Abschnitts ist die, in der am meisten schiefgehen konnte."""
    treffer = treffer or {}
    noten = _abschnittsnoten(ergebnis, schritte)
    titel_fuer = {s.schluessel: s.titel for s in schritte}
    kandidaten: list[tuple[int, int, str, str, str]] = []
    gesehen: set[str] = set()

    def dazu(rang: int, note: int, schluessel: str, text: str, grund: str) -> None:
        nackt = (text or "").strip()
        if not nackt or nackt in gesehen:
            return
        gesehen.add(nackt)
        kandidaten.append((rang, note, titel_fuer.get(schluessel, schluessel),
                           nackt, grund))

    # 1. mechanische Treffer
    for zug in ergebnis.zuege:
        for text in zug.bot:
            grund = treffer.get(text)
            if grund:
                dazu(0, noten.get(zug.schritt, 0), zug.schritt, text,
                     f"mechanisch: {grund}")

    # 2. was der Richter benannt hat
    for schritt in schritte:
        urteil = ergebnis.urteile.get(schritt.schluessel, {})
        dazu(1, noten.get(schritt.schluessel, 0), schritt.schluessel,
             urteil.get("schlechteste_antwort", ""),
             urteil.get("begruendung", "") or "vom Richter als schwaechste benannt")

    # 3. auffuellen aus den schlechtesten Abschnitten
    fuellung = sorted(
        (
            (noten.get(z.schritt, 0), -len(t), z.schritt, t)
            for z in ergebnis.zuege for t in z.bot if t.strip()
        ),
        key=lambda k: (k[0], k[1]),
    )
    for note, _, schluessel, text in fuellung:
        if len(kandidaten) >= SCHLECHTESTE:
            break
        dazu(2, note, schluessel, text,
             f"laengste Antwort im schwaechsten Abschnitt (Note {note})")

    if not kandidaten:
        return ["", "Der Bot hat in diesem Lauf keine einzige Antwort geschickt."]

    kandidaten.sort(key=lambda k: (k[0], k[1]))
    zeilen = []
    for _, note, titel, antwort, begruendung in kandidaten[:SCHLECHTESTE]:
        zeilen += ["", f"**{titel}** (Abschnittsnote {note})", "",
                   "> " + antwort.replace("\n", "\n> "), ""]
        if begruendung:
            zeilen.append(f"Warum: {begruendung}")
    return zeilen


# ---------------------------------------------------------------------------
# Referenzvergleich: echter Chat gegen Simulation (--set birk)
# ---------------------------------------------------------------------------


def referenzvergleich(ergebnis, zahlen: dict, schritte, referenz: dict) -> list[str]:
    """Was der Bot gebraucht hat, neben dem, was er am 04.09. wirklich
    gebraucht hat.

    Nur bei ``--set birk``: es ist der einzige Lauf, zu dem es einen echten
    Chatverlauf gibt. Die beiden Spalten sind bewusst **nicht** deckungsgleich
    beschriftet -- die Abschnitte des echten Chats sind die Strecken zwischen
    zwei Notiert-Zeilen, die Schritte der Simulation sind die Schritte des
    Skripts. Was sich vergleichen laesst, ist die Groessenordnung: braucht
    der Bot heute mehr Nachrichten als damals, ist etwas schlechter
    geworden."""
    if not referenz:
        return []

    je_schritt: dict[str, int] = {}
    for zug in ergebnis.zuege:
        je_schritt[zug.schritt] = je_schritt.get(zug.schritt, 0) + len(zug.beitraege)

    abschnitte = referenz.get("nachrichten_je_abschnitt") or []
    hand = referenz.get("handzaehlung") or {}

    zeilen = [
        "", "## Referenzvergleich: echter Probelauf 04.09. gegen Simulation", "",
        "**Nachrichten bis zum Zielzustand.** Soll: nicht mehr als Birk "
        "gebraucht hat.", "",
        "| Schritt | Stimm-Nachrichten (Simulation) |",
        "|---|---|",
    ]
    for schritt in schritte:
        zeilen.append(f"| {schritt.titel} | {je_schritt.get(schritt.schluessel, 0)} |")
    zeilen.append(f"| **Summe** | **{sum(je_schritt.values())}** |")
    zeilen += [
        "",
        f"Echter Chat: {referenz.get('nachrichten_gesamt', 0)} Nachrichten von "
        f"Birk in {referenz.get('abschnitte', 0)} Abschnitten zwischen den "
        f"Notiert-Zeilen ({', '.join(str(a) for a in abschnitte)}).",
        "",
        "**Verhalten des Bots.**", "",
        "| Kennzahl | echt (mechanisch) | echt (Handzaehlung Birk) | Simulation |",
        "|---|---|---|---|",
        f"| Rueckfragen | {referenz.get('rueckfragen', 0)} | "
        f"{hand.get('rueckfragen', '–')} | {zahlen.get('bot_rueckfragen', 0)} |",
        f"| Echo | {referenz.get('echo', 0)} | {hand.get('echo', '–')} | "
        f"{zahlen.get('echo', 0)} |",
        f"| behauptete Schreibvorgaenge | "
        f"{referenz.get('behauptete_schreibvorgaenge', 0)} | "
        f"{hand.get('behauptete_schreibvorgaenge', '–')} | "
        f"{zahlen.get('behauptete_schreibvorgaenge', 0)} |",
        "",
        "Die beiden echten Spalten zaehlen verschieden: mechanisch ist eine "
        "Rueckfrage eine Bot-Nachricht, die auf ein Fragezeichen endet; Birks "
        "Handzaehlung vom 05.09. meint die Stellen, an denen der Bot haette "
        "machen sollen statt zu fragen. Die Simulationsspalte ist mechanisch "
        "gezaehlt und deshalb mit der ersten vergleichbar, nicht mit der "
        "zweiten.",
    ]

    if referenz.get("kernthema"):
        zeilen += [
            "", "**Kernthema.** Sollwert zum Vergleich, keine Vorgabe -- das "
            "damalige Kernthema ist nirgends in den Prompt gegangen.", "",
            f"- damals: {referenz['kernthema']}",
            f"- diesmal: {zahlen.get('kernthema') or '(nicht im Arbeitsstand)'}",
        ]
    if referenz.get("figuren"):
        zeilen += [
            "", "**Figuren.**", "",
            f"- damals: {', '.join(referenz['figuren'])}",
            f"- diesmal: {', '.join(zahlen.get('figuren') or []) or '(keine)'}",
        ]
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
        f"- Modelle Bot: {kopfdaten['llm_modell']} (Gespraech, Verdichter, "
        f"Szene), {kopfdaten['erkenner_modell']} (Erkenner, Journal)",
        f"- Modell Simulation: {kopfdaten['sim_modell']} (Stimmen, Richter, "
        "Abonnement -- kostet je Aufruf nichts)",
        f"- git-HEAD: {kopfdaten['git']}",
        f"- Dauer: {zahlen['dauer_s']:.0f} s, Kosten Bot {zahlen['chf_bot']:.4f} CHF "
        f"({zahlen['aufrufe']} Aufrufe, Preise Stand {kopfdaten['preise_stand']}); "
        f"Simulation {zahlen['sim_aufrufe']} Aufrufe, "
        f"{zahlen['sim_token_ein']}/{zahlen['sim_token_aus']} Token ein/aus",
        "",
        "## Kennzahlen",
        "",
    ]
    zeilen += kennzahlen_tabelle(zahlen)
    zeilen += referenzvergleich(ergebnis, zahlen, schritte, kopfdaten.get("referenz") or {})
    zeilen += ["", "## Noten des Richters", ""]
    zeilen += noten_tabelle(ergebnis, schritte)
    zeilen += ["", "## Die Szenen", ""]
    zeilen += szenen_noten(ergebnis)
    zeilen += ["", "## Die schlechtesten Bot-Antworten", ""]
    zeilen += schlechteste_antworten(
        ergebnis, schritte,
        kennzahlen.mechanische_treffer(
            ergebnis.zuege, [p.name for p in ergebnis.personen]
        ),
    )
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
        "sim_modell": kopfdaten["sim_modell"],
        "noten_median": statistics.median(noten) if noten else None,
        "noten_summe": sum(noten) if noten else None,
        # ``szene`` ist die zuletzt geschriebene -- die Form, in der
        # verlauf.jsonl seit dem ersten Lauf eine Szene fuehrt, damit alte
        # Zeilen mit neuen vergleichbar bleiben. ``szenen`` daneben fuehrt
        # alle, seit --set birk drei schreiben laesst.
        "szene": {k: ergebnis.szenen_urteil.get(k) for k in richter.SZENEN_KRITERIEN},
        "szenen": [
            {"nummer": s["nummer"], "form": s.get("form", ""),
             "zeichen": len(s["volltext"]),
             **{k: (s.get("urteil") or {}).get(k) for k in richter.SZENEN_KRITERIEN}}
            for s in ergebnis.szenen
        ],
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
