"""Betreiberskript: wertet das UX-Ereignis-Logging einer Gruppe aus
(Karte t_10a31406, 06.10.2026).

Liest, was ``web_vereint._UX_JS`` ueber ``POST /g/<token>/chat/ereignis``
gesammelt hat (``repo.hole_ux_ereignisse``), dazu die Zeitachse der
``web_post``-Zeilen (``repo.web_post_fuer_auswertung``, nie der Text) --
und schreibt einen Markdown-Bericht nach stdout: Phasen-Funnel
(betreten -> erste Aktion -> weiter), Verweildauer je Tab, die haeufigsten
toten/Rage-Tipps, Zeit von einer Bot-Frage zur naechsten Gruppenantwort,
Aufnahme-Abbrueche und JS-Fehler.

**Kein Freitext in der Ausgabe** -- die einzige Ausnahme ist die
JS-Fehlermeldung (``extra.msg``), die laut Karte ausdruecklich erwuenscht
ist ("JS errors ... with message + line"); jeder andere ``extra``-Schluessel
ist ohnehin durch ``repo.UX_EXTRA_FELDER`` auf Zahlen begrenzt.

Aufruf: python -m scripts.ux_auswertung --chat <id> [--tag YYYY-MM-DD]
Umgebung: IT_DB (Pflicht)
"""

import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import db, repo


def funnel_je_phase(ereignisse: list[dict]) -> dict[int, dict[str, int]]:
    """Je Phase: wie viele Geraete sie betreten haben (``entered``), wie
    viele dort eine erste Aktion zeigten (``first_action``: ``klick``/
    ``rage_klick``), wie viele spaeter eine HOEHERE Phase erreichten
    (``done`` -- ein Naeherungswert fuer "weitergekommen", kein direkter
    Phasenabschluss)."""
    geraete_je_phase: dict[int, set] = {}
    for e in ereignisse:
        phase = e.get("phase")
        if phase is None:
            continue
        geraete_je_phase.setdefault(phase, set()).add(e["geraet"])
    hoechste_phase_je_geraet: dict[str, int] = {}
    for e in ereignisse:
        phase = e.get("phase")
        if phase is None:
            continue
        geraet = e["geraet"]
        if phase > hoechste_phase_je_geraet.get(geraet, -1):
            hoechste_phase_je_geraet[geraet] = phase
    ergebnis = {}
    for phase, geraete in sorted(geraete_je_phase.items()):
        aktion = {
            e["geraet"] for e in ereignisse
            if e.get("phase") == phase and e["typ"] in ("klick", "rage_klick")
        }
        weiter = {g for g in geraete if hoechste_phase_je_geraet.get(g, phase) > phase}
        ergebnis[phase] = {
            "entered": len(geraete),
            "first_action": len(geraete & aktion),
            "done": len(weiter),
        }
    return ergebnis


def tab_verweildauer(ereignisse: list[dict]) -> dict[str, dict[str, int]]:
    """Je Tab (``ziel`` eines ``tab_wechsel``-Ereignisses): Summe und Anzahl
    der ``dauer_ms``-Werte, die beim Wechsel WEG von diesem Tab anfallen --
    das Client-JS traegt die Verweildauer des VORIGEN Tabs am Ereignis des
    naechsten (siehe ``web_vereint._UX_JS``, Kommentar zu ``melde``)."""
    ergebnis: dict[str, dict[str, int]] = {}
    voriges_ziel = None
    for e in ereignisse:
        if e["typ"] != "tab_wechsel":
            continue
        dauer = e.get("dauer_ms")
        if dauer is not None and voriges_ziel is not None:
            eintrag = ergebnis.setdefault(voriges_ziel, {"summe_ms": 0, "n": 0})
            eintrag["summe_ms"] += dauer
            eintrag["n"] += 1
        voriges_ziel = e["ziel"]
    return ergebnis


def top_tote_tipps(ereignisse: list[dict], n: int = 10) -> list[tuple[str, int]]:
    """Die haeufigsten Ziele von Rage-/toten Tipps."""
    zaehler = Counter(e["ziel"] for e in ereignisse if e["typ"] == "rage_klick")
    return zaehler.most_common(n)


def abbrueche(ereignisse: list[dict]) -> int:
    """Wie oft eine Aufnahme abgebrochen wurde (``typ == 'abbruch'``)."""
    return sum(1 for e in ereignisse if e["typ"] == "abbruch")


def js_fehler_liste(ereignisse: list[dict], n: int = 20) -> list[tuple[str, int]]:
    """Die haeufigsten JS-Fehlermeldungen -- die einzige Stelle, an der
    ``extra.msg`` als Text auftaucht (vom Laufzeitsystem, nie von der
    Gruppe getippt, siehe ``repo.UX_EXTRA_FELDER``)."""
    zaehler = Counter(
        e.get("extra", {}).get("msg") or "(ohne Meldung)"
        for e in ereignisse if e["typ"] == "js_fehler"
    )
    return zaehler.most_common(n)


def antwortzeiten_bot_zu_gruppe(posts: list[dict]) -> list[float]:
    """Sekunden von jeder Bot-Ausgabe (``richtung == 'aus'``) bis zur
    NAECHSTEN Gruppennachricht (``richtung == 'ein'``) -- nur die erste
    Antwort je Bot-Zeile zaehlt, damit eine Serie von Rueckfragen nicht
    mehrfach dieselbe Wartezeit eintraegt. Liest ausschliesslich Zeitpunkt
    und Richtung (``repo.web_post_fuer_auswertung``), nie den Text."""
    deltas = []
    letzte_aus: str | None = None
    for p in posts:
        if p["richtung"] == "aus":
            letzte_aus = p["erstellt_am"]
        elif p["richtung"] == "ein" and letzte_aus is not None:
            delta = (
                datetime.fromisoformat(p["erstellt_am"])
                - datetime.fromisoformat(letzte_aus)
            ).total_seconds()
            if delta >= 0:
                deltas.append(delta)
            letzte_aus = None
    return deltas


def _sekunden_lesbar(sekunden: float) -> str:
    if sekunden < 60:
        return f"{sekunden:.0f}s"
    return f"{sekunden // 60:.0f}m {sekunden % 60:.0f}s"


def bericht(chat_id: int, ereignisse: list[dict], posts: list[dict]) -> str:
    """Der vollstaendige Markdown-Bericht -- reine Funktion, kein SQL
    (die Daten kommen schon fertig aus ``repo``)."""
    zeilen = [f"# UX-Auswertung Gruppe {chat_id}", ""]
    zeilen.append(f"{len(ereignisse)} Ereignisse, "
                  f"{len({e['geraet'] for e in ereignisse})} Geraete.")
    zeilen.append("")

    zeilen.append("## Phasen-Funnel (betreten -> erste Aktion -> weiter)")
    funnel = funnel_je_phase(ereignisse)
    if funnel:
        zeilen.append("| Phase | betreten | erste Aktion | weiter |")
        zeilen.append("|---|---|---|---|")
        for phase, werte in funnel.items():
            zeilen.append(
                f"| {phase} | {werte['entered']} | {werte['first_action']} | "
                f"{werte['done']} |"
            )
    else:
        zeilen.append("Keine Daten.")
    zeilen.append("")

    zeilen.append("## Verweildauer je Tab")
    dauer = tab_verweildauer(ereignisse)
    if dauer:
        zeilen.append("| Tab | Summe | Besuche | Schnitt |")
        zeilen.append("|---|---|---|---|")
        for tab, werte in sorted(dauer.items(), key=lambda t: -t[1]["summe_ms"]):
            schnitt = werte["summe_ms"] / werte["n"] / 1000 if werte["n"] else 0
            zeilen.append(
                f"| {tab} | {_sekunden_lesbar(werte['summe_ms'] / 1000)} | "
                f"{werte['n']} | {_sekunden_lesbar(schnitt)} |"
            )
    else:
        zeilen.append("Keine Daten.")
    zeilen.append("")

    zeilen.append("## Haeufigste tote/Rage-Tipps")
    tipps = top_tote_tipps(ereignisse)
    if tipps:
        for ziel, n in tipps:
            zeilen.append(f"- `{ziel}`: {n}×")
    else:
        zeilen.append("Keine.")
    zeilen.append("")

    zeilen.append("## Zeit von Bot-Frage zu Gruppenantwort")
    deltas = antwortzeiten_bot_zu_gruppe(posts)
    if deltas:
        deltas_sortiert = sorted(deltas)
        mitte = deltas_sortiert[len(deltas_sortiert) // 2]
        zeilen.append(
            f"{len(deltas)} Antworten, Median {_sekunden_lesbar(mitte)}, "
            f"Schnitt {_sekunden_lesbar(sum(deltas) / len(deltas))}."
        )
    else:
        zeilen.append("Keine Daten.")
    zeilen.append("")

    zeilen.append("## Abbrueche")
    zeilen.append(f"{abbrueche(ereignisse)} abgebrochene Aufnahmen.")
    zeilen.append("")

    zeilen.append("## JS-Fehler")
    fehler = js_fehler_liste(ereignisse)
    if fehler:
        for msg, n in fehler:
            zeilen.append(f"- `{msg}`: {n}×")
    else:
        zeilen.append("Keine.")
    zeilen.append("")

    return "\n".join(zeilen) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chat", type=int, required=True, help="chat_id der Gruppe")
    parser.add_argument("--tag", help="nur dieser Tag, Format YYYY-MM-DD")
    argumente = parser.parse_args()

    db_pfad = os.environ.get("IT_DB")
    if not db_pfad:
        print("Fehlende Umgebungsvariable: IT_DB", file=sys.stderr)
        sys.exit(1)

    seit = bis = None
    if argumente.tag:
        tag = datetime.strptime(argumente.tag, "%Y-%m-%d")
        seit = tag.isoformat()
        bis = (tag + timedelta(days=1)).isoformat()

    conn = db.verbinde(db_pfad)
    db.initialisiere(conn)
    ereignisse = repo.hole_ux_ereignisse(conn, argumente.chat, seit, bis)
    posts = repo.web_post_fuer_auswertung(conn, argumente.chat, seit, bis)
    conn.close()

    print(bericht(argumente.chat, ereignisse, posts), end="")


if __name__ == "__main__":
    main()
