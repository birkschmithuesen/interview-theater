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
import contextlib
import logging
import os
import sys
import tempfile
import threading
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from interview_theater import db, einstellungen, kontext, llm
from scripts.pruefe_prompts import PREISE_CHF_JE_MIO_TOKEN, PREISE_STAND
from simulation import (
    bericht, birk, claude, kennzahlen, lauf, material, richter, skript, stoerung,
    tag1,
)
from simulation.attrappe import TelegramAttrappe

log = logging.getLogger(__name__)

#: Wartezeit nach HTTP 429, bevor derselbe Aufruf wiederholt wird -- derselbe
#: Wert und derselbe Schalter wie in ``scripts/pruefe_prompts.py``.
PAUSE_429_S = float(os.environ.get("IT_PRUEFE_PAUSE_429_S", "45"))

#: So oft wird ein Aufruf nach 429 wiederholt.
VERSUCHE_429 = 3

#: Zeitbudget des HTTP-Klienten. Grosszuegig, weil der Szenenlauf sein
#: eigenes, laengeres Budget mitbringt (``szene.TIMEOUT_S``) und alles andere
#: hier ohnehin sequenziell laeuft.
TIMEOUT_S = 180.0

#: Auf diesen Wert setzt ``--fenster-klein`` das Fensterbudget des
#: Kontextaufbaus (``kontext.FENSTER_ZEICHEN``, in ZEICHEN seit dem Umbau vom
#: 06.09.2026). Der Journal-Extraktor laeuft nur, wenn etwas aus dem
#: Fenster faellt (``journal.berechne_verdraengten_abschnitt``) -- bei den
#: regulaeren 12.000 Zeichen faellt in einem Simulationslauf selten etwas
#: heraus, und der Extraktor bliebe ungemessen. 4.500 Zeichen (~1.500 Token)
#: sind klein genug, dass Verdraengung schon im Interviewteil eintritt, und
#: gross genug, dass der Bot noch ein Gespraech fuehren kann.
FENSTER_KLEIN = 4500


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
SET_WAHL = ("1", "2", "3", birk.NAME) + tag1.SETS


def ist_birk(args) -> bool:
    return args.set == birk.NAME


def ist_tag1(args) -> bool:
    """Ob dieser Lauf eines der Sets aus dem echten Tag 1 faehrt.

    Sie unterscheiden sich in vier Dingen von allen anderen: eine Stimme
    statt drei, das Skript der acht Phasen (``skript.SCHRITTE_TAG2``), eine
    Begriffs- und Fragenrichtung aus dem echten Tag -- und ein
    Referenzblock, der aus Aggregaten besteht statt aus einem Chatverlauf."""
    return args.set in tag1.SETS


def mischungsname(args) -> str:
    """Wie der Lauf in Dateinamen und Verlauf heisst."""
    if ist_birk(args):
        return birk.NAME
    if ist_tag1(args):
        return args.set
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
    p.add_argument("--stoerung", choices=stoerung.ARTEN,
                   help="dreimal in Folge diesen Fehler werfen -- der Bericht "
                        "zeigt, was die Gruppe daraufhin liest und ob es "
                        "danach weitergeht")
    p.add_argument("--stoerung-ab", type=int, default=stoerung.AB_ZUG_VORGABE,
                   metavar="N", help="ab welchem Zug die Stoerung greift "
                                     f"(Vorgabe {stoerung.AB_ZUG_VORGABE})")
    p.add_argument("--pause", action="store_true",
                   help=f"nach Schritt {lauf.PAUSE_NACH_SCHRITT} eine Nacht "
                        "einlegen (Chat zurueckdatieren) und die "
                        "Wiederkehr-Zeile messen")
    p.add_argument("--parallel", type=int, default=1, metavar="N",
                   help="N Laeufe gleichzeitig in Threads gegen denselben "
                        "Anbieter -- misst, wie oft er dabei drosselt")
    p.add_argument("--fenster-klein", action="store_true",
                   help="kontext.FENSTER_ZEICHEN auf "
                        f"{FENSTER_KLEIN} setzen, damit Verdraengung eintritt "
                        "und der Journal-Extraktor ueberhaupt laeuft")
    p.add_argument("--alle", action="store_true",
                   help="vier Laeufe hintereinander: Sets 1-3 und birk")
    p.add_argument("--echte-db", metavar="PFAD",
                   help="in DIESE Datenbank schreiben statt in eine Wegwerf-DB "
                        "(z. B. betrieb/soap.db) -- die Gruppe erscheint dann auf "
                        "Dashboard und Gruppenseite. Vorher leeren.")
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
    if ist_tag1(args):
        grund = skript.SCHRITTE_TAG2
    elif ist_birk(args):
        grund = skript.SCHRITTE_BIRK
    else:
        grund = skript.SCHRITTE
    return skript.ohne_szene(grund) if args.ohne_szene else grund


def aufstellung(args) -> dict:
    """Wer spricht, welches Material, welches Skript -- die drei Dinge, in
    denen sich ``--set birk`` von allen anderen Laeufen unterscheidet.

    An einer Stelle statt an dreien: der Lauf selbst soll nichts von diesem
    Sonderfall wissen muessen, er bekommt nur Interviews, Personen und ein
    Skript."""
    if not ist_birk(args):
        if ist_tag1(args):
            # Ein tag1-Lauf zieht seine Transkripte aus dem thematisch
            # naechsten ERFUNDENEN Set. Aus Tag 1 kommen Stimme, Begriffe und
            # Fragenrichtung -- nie das Material.
            return {
                "gezogene": material.waehle(
                    ein_set=tag1.interviewset(args.set), mix=None, seed=args.seed,
                )[:tag1.INTERVIEWS_JE_LAUF],
                "personen": [tag1.person(args.set)],
                "begriffsliste": tag1.begriffe(args.set),
                "fragenliste": tag1.fragen(args.set),
                "referenz": tag1.referenz(args.set),
            }
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


@contextlib.contextmanager
def wegwerf_umgebung():
    """Ein Wegwerf-Verzeichnis, das fuer die Dauer aller Laeufe als ``IT_DB``
    gilt.

    ``IT_DB`` wird ueberschrieben -- sowohl im ``Einstellungen``-Objekt als
    auch in der Umgebung. Das zweite ist nicht Vorsicht, sondern Absicht:
    ``anweisungen.zusatz_verzeichnis()`` sucht den Regie-Zettel ``zusatz.md``
    **neben der Datenbank**. Ein Lauf soll die Prompts des Repositories
    messen, nicht die Notiz, die heute Vormittag jemand fuer den laufenden
    Workshop danebengelegt hat.

    Ein Verzeichnis fuer alle Laeufe, nicht eines je Lauf: bei ``--parallel``
    laufen zwei Gruppen in Threads, und zwei Threads, die sich abwechselnd
    ``IT_DB`` umsetzen, wuerden einander den Pfad unter den Fuessen
    wegziehen. Die Datenbanken selbst bleiben getrennt (eine Datei je Lauf),
    nur der Regie-Zettel-Ort ist gemeinsam -- und der ist in beiden Faellen
    leer."""
    altes = os.environ.get("IT_DB")
    with tempfile.TemporaryDirectory(prefix="interview_theater-simulation-") as ordner:
        os.environ["IT_DB"] = str(Path(ordner) / "simulation.db")
        try:
            yield Path(ordner)
        finally:
            if altes is None:
                os.environ.pop("IT_DB", None)
            else:
                os.environ["IT_DB"] = altes


def einen_lauf(args, e, klient, mischung: str, sim=None, ordner=None) -> dict:
    """Ein Lauf von Anfang bis Bericht. Liefert die Kennzahlen."""
    aufbau = aufstellung(args)
    gezogene = aufbau["gezogene"]
    schritte = _schritte(args)

    with contextlib.ExitStack() as stapel:
        if ordner is None:
            ordner = stapel.enter_context(wegwerf_umgebung())
        if getattr(args, "echte_db", None):
            # Birk 05.09.: "Lasse die echte Datenbank befuellt und auch das
            # Dashboard und die Webseiten inline, die will ich checken."
            # Der Lauf schreibt in die Betriebs-DB -- die Gruppe erscheint
            # dort wie eine echte, mit Token und Gruppenseite. Vorher leeren
            # ist Sache des Betreibers (scripts/loeschen.py).
            db_pfad = args.echte_db
            e = replace(e, db_pfad=db_pfad)
        else:
            db_pfad = str(Path(ordner) / f"{mischung}-{args.seed}.db")
            e = replace(e, db_pfad=db_pfad, audio_verz=str(Path(ordner) / "audio"))
        conn = db.verbinde(db_pfad)
        db.initialisiere(conn)

        tg = TelegramAttrappe()
        klm = llm.LLM(e, klient, conn)
        stoer = None
        if args.stoerung:
            stoer = stoerung.StoerungsLLM(klm, args.stoerung, args.stoerung_ab)
            klm = stoer
        klm = LLMMitPause(klm)
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
            stoerung=stoer, pause=args.pause,
        )
        ergebnis = durchlauf.fahre()

        print("  -> Richter", flush=True)
        lauf.bewerte(sim, conn, ergebnis, schritte)

        zahlen = kennzahlen.sammle(
            conn, lauf.CHAT_ID, ergebnis.zuege, gezogene,
            [p.name for p in ergebnis.personen],
            richter.markierte_zustimmungen(ergebnis.urteile),
            ergebnis.schritte, e, PREISE_CHF_JE_MIO_TOKEN, ergebnis.dauer_s,
            notausgaenge=ergebnis.notausgaenge,
            sim_statistik=sim.statistik.als_dict(),
            journal_urteil=ergebnis.journal_urteil,
            stoerung=stoer.bericht() if stoer else None,
            wiederkehr_zeilen=ergebnis.wiederkehr if args.pause else None,
            tg=tg,
            knopfdruecke=ergebnis.knopfdruecke,
            phasen_proaktiv=ergebnis.phasen_proaktiv,
            phasen_selbst=ergebnis.phasen_selbst,
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
        return zahlen


@contextlib.contextmanager
def fenster_klein(an: bool):
    """Setzt ``kontext.FENSTER_ZEICHEN`` herunter und danach zurueck.

    Ein Modulwert und kein Argument: das Budget wird an zwei Stellen gelesen
    (``kontext.baue`` und ``journal.berechne_verdraengten_abschnitt``), und
    beide muessten dasselbe Argument durchgereicht bekommen, damit die
    Verdraengung, die der Kontextaufbau erzeugt, auch die ist, die der
    Extraktor sieht. Seit dem 06.09.2026 lesen beide ueber
    ``kontext.fenster_grenzen()`` denselben Modulwert -- das Zurueckstellen
    hier wirkt damit auf beide."""
    if not an:
        yield
        return
    alt = kontext.FENSTER_ZEICHEN
    kontext.FENSTER_ZEICHEN = FENSTER_KLEIN
    try:
        yield
    finally:
        kontext.FENSTER_ZEICHEN = alt


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
    elif args.parallel > 1:
        # Dieselbe Mischung, verschiedene Seeds: zwei Gruppen am selben
        # Nachmittag arbeiten am selben Material, nicht an demselben Skript
        # mit derselben Besetzung. Der Seed ist das Einzige, was sie
        # unterscheidet -- und die Frage ist ohnehin nicht, was sie sagen,
        # sondern wie oft der Anbieter drosselt.
        laeufe = [replace_args(args, seed=args.seed + n)
                  for n in range(args.parallel)]
    else:
        laeufe.append(args)

    with httpx.Client(timeout=TIMEOUT_S) as klient, \
            fenster_klein(args.fenster_klein), wegwerf_umgebung() as ordner:
        if args.parallel > 1 and not args.alle:
            _parallel(laeufe, e, klient, ordner)
        else:
            for einzeln in laeufe:
                # Je Lauf ein eigener Simulationsklient: seine Statistik
                # gehoert in die Verlaufszeile genau dieses Laufs, nicht in
                # die Summe von dreien.
                sim = claude.Claude()
                try:
                    einen_lauf(einzeln, e, klient, mischungsname(einzeln),
                               sim=sim, ordner=ordner)
                finally:
                    sim.schliesse()
    return 0


def _parallel(laeufe, e, klient, ordner) -> None:
    """Mehrere Laeufe gleichzeitig, je einer in einem Thread.

    **Nur beim Netzlauf sinnvoll.** Gemessen wird nicht der Bot, sondern der
    Anbieter: Infomaniak antwortet auf parallele Aufrufe mit 429/5xx
    (AGENTS.md 'Die Fallen'), und wenn am Montag drei Gruppen gleichzeitig
    arbeiten, ist genau das die Frage. Der Bericht jedes Laufs zaehlt seine
    eigenen Vorfaelle.

    Jeder Thread bekommt seinen eigenen Simulationsklienten und seine eigene
    Datenbankdatei; geteilt wird nur der ``httpx.Client`` (der ist
    thread-sicher) und das Verzeichnis, in dem der Regie-Zettel gesucht
    wird."""
    fehler: list[BaseException] = []

    def einer(einzeln):
        sim = claude.Claude()
        try:
            einen_lauf(einzeln, e, klient, mischungsname(einzeln), sim=sim,
                       ordner=ordner)
        except BaseException as f:  # noqa: BLE001 -- im Thread, sonst lautlos
            log.exception("Paralleler Lauf fehlgeschlagen")
            fehler.append(f)
        finally:
            sim.schliesse()

    threads = [threading.Thread(target=einer, args=(einzeln,))
               for einzeln in laeufe]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if fehler:
        raise fehler[0]


def replace_args(args, ein_set: str | None = None, seed: int | None = None):
    """Eine Kopie der Argumente mit anderem Set oder Seed -- fuer ``--alle``
    und ``--parallel``.

    ``argparse.Namespace`` ist bewusst veraenderlich; eine Kopie statt einer
    Mutation, damit der zweite Lauf nicht die Argumente des ersten sieht.
    ``--ohne-szene`` faellt fuer birk weg statt den Lauf abzubrechen: in
    ``--alle`` soll ein gemeinsamer Schalter die drei erfundenen Sets billig
    halten duerfen, ohne den einen Lauf zu entwerten, der ohne Szenen nichts
    misst."""
    kopie = argparse.Namespace(**vars(args))
    kopie.alle = False
    kopie.parallel = 1
    if seed is not None:
        kopie.seed = seed
    if ein_set is not None:
        kopie.set = ein_set
        kopie.mix = None
        if ein_set == birk.NAME:
            kopie.ohne_szene = False
    return kopie


if __name__ == "__main__":
    sys.exit(main())
