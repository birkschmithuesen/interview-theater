"""Einen kompletten Workshop simulieren und bewerten.

**Kein Test, laeuft nie automatisch, kostet Geld** -- wie
``scripts/pruefe_prompts.py`` und ``scripts/rauchtest.py``. Die Testsuite
prueft alles daran, was ohne Netz pruefbar ist (``tests/test_simulation*.py``);
dieses Skript ist das Gegenstueck und laesst den echten Bot gegen echte
Modelle laufen.

**Wozu.** ``pruefe_prompts`` misst einzelne Prompts an einzelnen Faellen.
Was es nicht misst, ist der Zusammenhang: ob eine Gruppe mit diesem Bot in
einem halben Tag von einer Begriffsliste zu einem Szenentext kommt, ob
Zustimmungen ankommen, ob der Bot behauptet, etwas notiert zu haben, das
nirgends steht. Genau das faehrt dieses Skript ab -- neun Schritte, drei
simulierte Teilnehmerinnen, fuenf Interviews, danach ein Richter.

Aufruf::

    set -a; . ./betrieb/gruppe1.env; set +a
    PY=$(ls -d ~/.local/share/uv/python/cpython-3.11*/bin/python3 | head -1)
    $PY -m scripts.simulation --set 1 --seed 7 --bericht
    $PY -m scripts.simulation --mix 1,2,3 --seed 3
    $PY -m scripts.simulation --set 1 --seed 1 --ohne-szene --bericht
    $PY -m scripts.simulation --alle          # drei Laeufe, Sets 1-3

**Zwei Modelle.** Der Bot laeuft ueber Infomaniak (``interview_theater/llm.py``,
Env aus ``betrieb/gruppe1.env``) -- er ist der Prueflung. Die Stimmen und der
Richter laufen ueber Claude Opus am lokalen Proxy
(``simulation/claude.py``, ``IT_SIM_URL``/``IT_SIM_MODELL``): ein Prueflung,
der seine eigenen Teilnehmerinnen spielt und sich anschliessend selbst
benotet, misst vor allem sich selbst.

**Wegwerf-Datenbank.** ``IT_DB`` wird ueberschrieben -- sowohl im
``Einstellungen``-Objekt als auch in der Umgebung. Das zweite ist nicht
Vorsicht, sondern Absicht: ``anweisungen.zusatz_verzeichnis()`` sucht den
Regie-Zettel ``zusatz.md`` **neben der Datenbank**. Ein Lauf soll die
Prompts des Repositories messen, nicht die Notiz, die heute Vormittag jemand
fuer den laufenden Workshop danebengelegt hat.

**Sequenziell.** Infomaniak antwortet auf parallele Aufrufe mit 429/5xx
(AGENTS.md 'Die Fallen'); bei 429 wartet dieses Skript ``PAUSE_429_S``
Sekunden und wiederholt denselben Aufruf, wie ``pruefe_prompts``.
"""

import argparse
import os
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from interview_theater import db, einstellungen, llm
from scripts.pruefe_prompts import PREISE_CHF_JE_MIO_TOKEN, PREISE_STAND
from simulation import (
    bericht, birk, claude, kennzahlen, lauf, material, richter, skript,
)
from simulation.attrappe import TelegramAttrappe

#: Wartezeit nach HTTP 429, bevor derselbe Aufruf wiederholt wird -- derselbe
#: Wert und derselbe Schalter wie in ``scripts/pruefe_prompts.py``.
PAUSE_429_S = float(os.environ.get("IT_PRUEFE_PAUSE_429_S", "45"))

#: So oft wird ein Aufruf nach 429 wiederholt.
VERSUCHE_429 = 3

#: Zeitbudget des HTTP-Klienten. Grosszuegig, weil der Szenenlauf sein
#: eigenes, laengeres Budget mitbringt (``szene.TIMEOUT_S``) und alles andere
#: hier ohnehin sequenziell laeuft.
TIMEOUT_S = 180.0


class LLMMitPause:
    """Legt eine Wartezeit um jeden Modellaufruf, wenn Infomaniak drosselt.

    Ein Simulationslauf sind einige hundert Aufrufe hintereinander -- deutlich
    mehr als ein Korpuslauf, und damit deutlich sicherer im 429-Bereich
    (gemessen 04.09.2026: ab rund 50 Aufrufen in Folge). Ohne diese Huelle
    wuerde ein einzelnes 429 einen Schritt als gescheitert vermerken und den
    ganzen Lauf entwerten.

    Alles andere reicht sie unveraendert durch: ``llm.LLM`` hat seine eigene
    Wiederholung fuer 5xx und Transportfehler, und die soll hier nicht
    doppelt laufen."""

    def __init__(self, klm, pause: float = PAUSE_429_S, versuche: int = VERSUCHE_429):
        self._klm = klm
        self._pause = pause
        self._versuche = versuche

    def _mit_pause(self, aufruf, *args, **kwargs):
        for versuch in range(self._versuche):
            try:
                return aufruf(*args, **kwargs)
            except Exception as fehler:  # noqa: BLE001
                if "429" not in str(fehler) or versuch == self._versuche - 1:
                    raise
                print(f"  429 -- warte {self._pause} s", file=sys.stderr, flush=True)
                time.sleep(self._pause)
        raise RuntimeError("unerreichbar")  # pragma: no cover

    def schema(self, *args, **kwargs):
        return self._mit_pause(self._klm.schema, *args, **kwargs)

    def prosa(self, *args, **kwargs):
        return self._mit_pause(self._klm.prosa, *args, **kwargs)


#: Die Werte, die ``--set`` annehmen darf: die drei erfundenen Sets und das
#: eine echte. ``birk`` ist kein viertes Set, sondern ein anderer Lauf -- eine
#: Person statt drei, echtes Material, ein eigenes Skript.
SET_WAHL = ("1", "2", "3", birk.NAME)


def ist_birk(args) -> bool:
    return args.set == birk.NAME


def mischungsname(args) -> str:
    """Wie der Lauf in Dateinamen und Verlauf heisst."""
    if ist_birk(args):
        return birk.NAME
    if args.set:
        return f"set{args.set}"
    if args.mix:
        return "mix" + "-".join(str(n) for n in args.mix)
    return "alle15"


def _mix(text: str | None) -> list[int] | None:
    if not text:
        return None
    nummern = [int(t.strip()) for t in text.split(",") if t.strip()]
    unbekannt = [n for n in nummern if n not in material.SETS]
    if unbekannt:
        raise SystemExit(f"unbekannte Sets in --mix: {unbekannt}")
    return nummern


def baue_argumente(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m scripts.simulation",
        description="Einen kompletten Workshop simulieren und bewerten. "
                    "Kostet Geld, laeuft nie automatisch.",
    )
    p.add_argument("--set", choices=SET_WAHL,
                   help="alle Interviews eines Sets, oder 'birk' fuer den "
                        "Probelauf auf echten Daten")
    p.add_argument("--mix", help="Kommaliste von Sets, je Set 1-2 Interviews")
    p.add_argument("--seed", type=int, default=1,
                   help="macht Auswahl, Besetzung und Reihenfolge reproduzierbar")
    p.add_argument("--ohne-szene", action="store_true",
                   help="den Szenen-Schritt auslassen (spart den Reasoning-Lauf)")
    p.add_argument("--bericht", nargs="?", const="", default=None,
                   help="Markdown-Bericht schreiben; ohne Pfad nach "
                        "simulation/berichte/<datum>-<mischung>-<seed>.md. "
                        "Transkript und verlauf.jsonl entstehen immer.")
    p.add_argument("--alle", action="store_true",
                   help="vier Laeufe hintereinander: Sets 1-3 und birk")
    args = p.parse_args(argv)
    args.mix = _mix(args.mix)
    if args.set and args.mix:
        raise SystemExit("--set und --mix schliessen sich aus")
    if ist_birk(args) and args.ohne_szene:
        # Die drei Szenen SIND dieser Lauf: an ihnen wird gemessen, ob der Bot
        # eine Formvorgabe (Dialog, Lied, Rap) durchhaelt. Ein --set birk ohne
        # sie waere ein Lauf, der zehn Minuten spart und nichts misst.
        raise SystemExit(
            "--set birk und --ohne-szene schliessen sich aus: die drei Szenen "
            "sind der Zweck dieses Laufs."
        )
    return args


def _schritte(args):
    grund = skript.SCHRITTE_BIRK if ist_birk(args) else skript.SCHRITTE
    return skript.ohne_szene(grund) if args.ohne_szene else grund


def aufstellung(args) -> dict:
    """Wer spricht, welches Material, welches Skript -- die drei Dinge, in
    denen sich ``--set birk`` von allen anderen Laeufen unterscheidet.

    An einer Stelle statt an dreien: der Lauf selbst soll nichts von diesem
    Sonderfall wissen muessen, er bekommt nur Interviews, Personen und ein
    Skript."""
    if not ist_birk(args):
        return {
            "gezogene": material.waehle(
                ein_set=int(args.set) if args.set else None,
                mix=args.mix, seed=args.seed,
            ),
            "personen": None,
            "begriffsliste": None,
            "fragenliste": None,
            "referenz": {},
        }

    if not birk.vorhanden():
        raise SystemExit(
            f"--set birk braucht das Material unter {birk.verzeichnis()} "
            "(oder IT_SIM_BIRK auf ein anderes Verzeichnis setzen)."
        )
    return {
        "gezogene": [birk.lade()],
        "personen": [birk.person()],
        "begriffsliste": birk.begriffe(),
        "fragenliste": birk.fragen(),
        "referenz": birk.referenz(),
    }


def einen_lauf(args, e, klient, mischung: str, sim=None) -> dict:
    """Ein Lauf von Anfang bis Bericht. Liefert die Kennzahlen."""
    aufbau = aufstellung(args)
    gezogene = aufbau["gezogene"]
    schritte = _schritte(args)
    altes_db = os.environ.get("IT_DB")

    with tempfile.TemporaryDirectory(prefix="interview_theater-simulation-") as verzeichnis:
        db_pfad = str(Path(verzeichnis) / "simulation.db")
        # Beides: das Einstellungsobjekt UND die Umgebung -- der Regie-Zettel
        # wird neben der Datenbank gesucht (siehe Moduldocstring). Am Ende
        # wieder zurueckgesetzt, damit ``--alle`` und ein Testlauf die
        # Umgebung nicht dauerhaft veraendern.
        os.environ["IT_DB"] = db_pfad
        e = replace(e, db_pfad=db_pfad, audio_verz=str(Path(verzeichnis) / "audio"))
        conn = db.verbinde(db_pfad)
        db.initialisiere(conn)

        tg = TelegramAttrappe()
        klm = LLMMitPause(llm.LLM(e, klient, conn))
        # Der Simulationsklient wird je Lauf frisch angelegt, wenn keiner
        # hereingereicht wurde: seine Statistik gehoert zu genau diesem Lauf.
        sim = sim or claude.Claude()

        print(f"\n=== {mischung}, Seed {args.seed}, "
              f"{len(gezogene)} Interviews, {len(schritte)} Schritte ===", flush=True)
        print("Interviews: " + ", ".join(i.kennung for i in gezogene), flush=True)

        durchlauf = lauf.Lauf(
            conn, tg, klm, e, sim, gezogene=gezogene, seed=args.seed,
            schritte=schritte, personen=aufbau["personen"],
            begriffsliste=aufbau["begriffsliste"],
            fragenliste=aufbau["fragenliste"],
        )
        ergebnis = durchlauf.fahre()

        print("  -> Richter", flush=True)
        lauf.bewerte(sim, ergebnis, schritte)

        zahlen = kennzahlen.sammle(
            conn, lauf.CHAT_ID, ergebnis.zuege, gezogene,
            [p.name for p in ergebnis.personen],
            richter.markierte_zustimmungen(ergebnis.urteile),
            ergebnis.schritte, e, PREISE_CHF_JE_MIO_TOKEN, ergebnis.dauer_s,
            notausgaenge=ergebnis.notausgaenge,
            sim_statistik=sim.statistik.als_dict(),
        )

        kopfdaten = {
            "kennung": bericht.kennung(mischung, args.seed),
            "mischung": mischung,
            "seed": args.seed,
            "git": bericht.git_head(),
            "llm_modell": e.llm_modell,
            "erkenner_modell": e.erkenner_modell,
            "sim_modell": sim.modell,
            "preise_stand": PREISE_STAND,
            "referenz": aufbau["referenz"],
        }
        # Transkript und Verlaufszeile entstehen immer: das eine ist die
        # Datei, in die man schaut, wenn eine Zahl ueberrascht, das andere
        # der Vergleichsmassstab zum naechsten Lauf. Der Bericht selbst geht
        # nur auf Wunsch in eine Datei -- gedruckt wird er ohnehin.
        pfade = bericht.schreibe(
            ergebnis, zahlen, schritte, kopfdaten,
            lauf.protokoll(ergebnis, schritte),
            bericht_datei=args.bericht is not None,
            ziel=args.bericht or None,
        )
        print()
        print(bericht.baue(ergebnis, zahlen, schritte, kopfdaten))
        print(f"Transkript: {pfade['lauf']}")
        if pfade.get("bericht"):
            print(f"Bericht:    {pfade['bericht']}")
        print(f"Verlauf:    {pfade['verlauf']}")

        conn.close()
        if altes_db is None:
            os.environ.pop("IT_DB", None)
        else:
            os.environ["IT_DB"] = altes_db
        return zahlen


def main(argv=None) -> int:
    args = baue_argumente(argv)
    e = einstellungen.laden()

    laeufe = []
    if args.alle:
        # birk laeuft immer mit: es ist das einzige Set auf echten Daten und
        # damit das einzige, dessen Zahlen sich mit einem echten Chatverlauf
        # vergleichen lassen.
        for wahl in (*sorted(material.SETS), birk.NAME):
            laeufe.append(replace_args(args, ein_set=str(wahl)))
    else:
        laeufe.append(args)

    with httpx.Client(timeout=TIMEOUT_S) as klient:
        for einzeln in laeufe:
            # Je Lauf ein eigener Simulationsklient: seine Statistik gehoert
            # in die Verlaufszeile genau dieses Laufs, nicht in die Summe von
            # dreien.
            sim = claude.Claude()
            try:
                einen_lauf(einzeln, e, klient, mischungsname(einzeln), sim=sim)
            finally:
                sim.schliesse()
    return 0


def replace_args(args, ein_set: str):
    """Eine Kopie der Argumente mit anderem Set -- fuer ``--alle``.

    ``argparse.Namespace`` ist bewusst veraenderlich; eine Kopie statt einer
    Mutation, damit der zweite Lauf nicht die Argumente des ersten sieht.
    ``--ohne-szene`` faellt fuer birk weg statt den Lauf abzubrechen: in
    ``--alle`` soll ein gemeinsamer Schalter die drei erfundenen Sets billig
    halten duerfen, ohne den einen Lauf zu entwerten, der ohne Szenen nichts
    misst."""
    kopie = argparse.Namespace(**vars(args))
    kopie.set = ein_set
    kopie.mix = None
    kopie.alle = False
    if ein_set == birk.NAME:
        kopie.ohne_szene = False
    return kopie


if __name__ == "__main__":
    sys.exit(main())
