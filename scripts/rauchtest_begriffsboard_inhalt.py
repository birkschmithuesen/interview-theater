"""Messung: Begriffsboard-Inhalt vorher/nachher (Karte t_2b9d2cbe).

**Kein Test, laeuft nie automatisch, kostet Geld** (Kimi ueber Infomaniak).
Braucht die Padua-Env (IT_LLM_URL, IT_LLM_KEY, IT_LLM_MODELL):

    set -a; . /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-gruppe1.env; set +a
    python3.11 -m scripts.rauchtest_begriffsboard_inhalt --trocken
    python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm vorher --modell kimi
    python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm nachher --modell kimi --runde 0
    python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm nachher --modell opus --faelle ansage_en,deutsch_stt,schaerfung_stt_en
    python3.11 -m scripts.rauchtest_begriffsboard_inhalt --tabelle

Grenzen, die im Code stehen und nicht im Kommentar:
- Der Fall ``live`` liest das Transkript zur Laufzeit read-only
  (``file:...?mode=ro``) und schreibt es NIE in eine Datei; seine
  Rohantworten werden nicht gespeichert (``roh_pfad`` -> None).
- ``live`` geht nie an Opus (``pruefe_auswahl``): kein US-Modell fuer
  Live-Material.
- ``aufruf``-Zeilen gehen in eine Wegwerf-DB (tempfile), nie in betrieb/.
- ``vorher`` ist der Stand aus ``VORHER_REF`` (Prompt, SCHEMA, validiere,
  _nutzertext per ``git show``) -- reproduzierbar ohne Schalter im
  Produktivcode.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import math
import os
import sqlite3
import subprocess
import sys
import tempfile
import types
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from interview_theater import anweisungen, begriffsboard, db, einstellungen, llm, repo, sprache, workshop  # noqa: E402
from scripts import begriffsboard_inhalt_zaehler as zaehler  # noqa: E402

VORHER_REF = "55f34b58fc50de41114676222ce55e8cd1278b2e"
LIVE_DB_VORGABE = "/mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua.db"
LIVE_CHAT_ID = 7_000_000_000_000
LAEUFE_VORGABE = 3
#: 4 Faelle x 3 Laeufe x 2 Aufrufe = 24, plus Luft fuer Wiederholungen.
MAX_AUFRUFE = 30
#: ~0,015 CHF je Kimi-Aufruf geschaetzt (kosten.PREISE_CHF_JE_MIO_TOKEN) x 24
#: = 0,36 CHF; der Deckel liegt beim Doppelten.
BUDGET_CHF = 0.75
EN_PROMPT = "interview_theater/sprachen/en/prompts/begriffsboard.md"
MESS_VERZ = WURZEL / "docs" / "begriffsboard-inhalt" / "messung"
ROH_VERZ = WURZEL / "docs" / "begriffsboard-inhalt" / "roh"
ART = "messung_begriffsboard_inhalt"

#: Soll-Liste des Live-Falls (nur Begriffe, kein Transkript). Vor dem ersten
#: Vorher-Lauf gegen das Transkript geprueft und danach NICHT mehr geaendert.
LIVE = zaehler.Fall(
    name="live",
    beschreibung="Live-Diskussion Padua Gruppe 1 (DE gesprochen, EN-Profil), read-only",
    sprache_gesprochen="de",
    segmente=(),
    # Vom Architekten festgelegt (04.10.2026): Begriffe des Kimi-Boards v2,
    # jeder per ja/nein-Probe als im Transkript stehend bestaetigt -- das
    # Transkript selbst hat dabei niemand gelesen (Kartenregel: kein US-Modell).
    soll=(
        ("Cappuccino",),
        ("Espresso",),
        ("Tiramisu",),
        ("Restaurantroboter",),
        ("Alice Hotel",),
        ("Rolle",),
        ("Strasse", "Straße"),
        ("Tuch",),
        ("gemaltes Bild",),
        ("Biennale",),
        ("KI",),
        ("Seemöwen", "Tauben", "Geier"),
        ("Strand", "Urlaub am Strand"),
    ),
    varianten=("Kiranesu", "Strandheiz", "K.U. Roboter"),
    meta=("Begriff", "Gepäck", "Gepaeck", "Betreff", "Test", "Mikrofon"),
    mit_grund=(),
)

OPUS_ZUSATZ = ("\n\nReply with a single JSON object that matches this JSON schema, "
               "and nothing else:\n{schema}")


@dataclasses.dataclass(frozen=True)
class Stand:
    name: str
    system: str
    schema: dict
    validiere: object
    nutzertext: object


def _git_show(ref: str, pfad: str) -> str:
    return subprocess.run(["git", "-C", str(WURZEL), "show", f"{ref}:{pfad}"],
                          check=True, capture_output=True, text=True).stdout


def stand_vorher(ref: str = VORHER_REF) -> Stand:
    # Eigenes Modulobjekt unter dem echten Namen: sprache.Texte(__name__)
    # findet so dieselben Texte. NICHT in sys.modules eingetragen.
    mod = types.ModuleType("interview_theater.begriffsboard")
    quelle = _git_show(ref, "interview_theater/begriffsboard.py")
    exec(compile(quelle, f"begriffsboard@{ref[:7]}", "exec"), mod.__dict__)
    return Stand("vorher", anweisungen.fuelle(_git_show(ref, EN_PROMPT)), mod.SCHEMA,
                 mod.validiere, mod._nutzertext)


def stand_nachher() -> Stand:
    return Stand("nachher", anweisungen.hole("begriffsboard"), begriffsboard.SCHEMA,
                 begriffsboard.validiere, begriffsboard._nutzertext)


def pruefe_auswahl(faelle: list[str], modell: str) -> None:
    if modell == "opus" and "live" in faelle:
        raise SystemExit("Der Fall 'live' geht nie an Opus (US-Modell) -- nur Kimi.")
    unbekannt = set(faelle) - set(zaehler.ERFUNDEN) - {"live"}
    if unbekannt:
        raise SystemExit(f"Unbekannte Faelle: {sorted(unbekannt)}")


def lies_live_segmente(pfad: str, chat_id: int) -> list[str]:
    conn = sqlite3.connect(f"file:{Path(pfad).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [s for s in repo.diskussion_transkript(conn, chat_id).split("\n\n") if s.strip()]
    finally:
        conn.close()


def roh_pfad(fall_name: str, arm: str, modell: str, runde: int, lauf: int) -> Path | None:
    if fall_name == "live":
        return None
    return ROH_VERZ / f"{fall_name}-{arm}-{modell}-r{runde}-l{lauf}.json"


def _validiere(stand: Stand, roh: list, transkript: str, bisher: list) -> list:
    if "bisher" in inspect.signature(stand.validiere).parameters:  # nach t_cb2c4678
        return stand.validiere(roh, transkript, bisher=bisher)
    return stand.validiere(roh, transkript)


def ein_lauf(rufe, stand: Stand, fall: zaehler.Fall, profil: str):
    """Zwei Aufrufe wie im fortlaufenden Betrieb: erst die erste Haelfte der
    Segmente mit leerem Board, dann alles mit dem validierten Board."""
    haelfte = math.ceil(len(fall.segmente) / 2)
    erst = "\n\n".join(fall.segmente[:haelfte])
    ganz = "\n\n".join(fall.segmente)
    bisher = _validiere(stand, rufe(stand, stand.nutzertext(erst, [])), erst, [])
    roh = rufe(stand, stand.nutzertext(ganz, bisher))
    validiert = _validiere(stand, roh, ganz, bisher)
    roh_board = begriffsboard.lies(json.dumps(roh, ensure_ascii=False))
    zahlen = {"roh": zaehler.zaehle(roh_board, ganz, fall, profil),
              "validiert": zaehler.zaehle(validiert, ganz, fall, profil)}
    return zahlen, roh, validiert


def _board_aus(ergebnis) -> list:
    board = ergebnis.get("board") if isinstance(ergebnis, dict) else None
    return board if isinstance(board, list) else []


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--arm", choices=("vorher", "nachher"), default="nachher")
    p.add_argument("--modell", choices=("kimi", "opus"), default="kimi")
    p.add_argument("--faelle", default=",".join(("live",) + zaehler.ERFUNDEN))
    p.add_argument("--laeufe", type=int, default=LAEUFE_VORGABE)
    p.add_argument("--runde", type=int, default=0)
    p.add_argument("--live-db", default=LIVE_DB_VORGABE)
    p.add_argument("--trocken", action="store_true")
    p.add_argument("--tabelle", action="store_true")
    a = p.parse_args(argv)

    if a.tabelle:
        messungen = [json.loads(f.read_text()) for f in sorted(MESS_VERZ.glob("*.json"))]
        print(zaehler.tabelle(messungen))
        return 0

    faelle_namen = [f for f in a.faelle.split(",") if f]
    pruefe_auswahl(faelle_namen, a.modell)
    os.environ["IT_WORKSHOP"] = "padua-2026"
    workshop.vergiss()
    sprache.vergiss()
    profil = sprache.code()

    faelle: list[zaehler.Fall] = []
    for name in faelle_namen:
        if name == "live":
            faelle.append(dataclasses.replace(
                LIVE, segmente=tuple(lies_live_segmente(a.live_db, LIVE_CHAT_ID))))
        else:
            faelle.append(zaehler.lade_fall(zaehler.FAELLE_VERZ / f"{name}.toml"))

    stand = stand_vorher() if a.arm == "vorher" else stand_nachher()
    if a.arm == "nachher":
        datei = anweisungen.fuelle((WURZEL / EN_PROMPT).read_text(encoding="utf-8")).strip()
        if datei != stand.system.strip():
            raise SystemExit("anweisungen.hole('begriffsboard') liefert unter padua-2026 nicht "
                             f"{EN_PROMPT} -- Profil pruefen, Messung abgebrochen.")

    aufrufe_geplant = len(faelle) * a.laeufe * 2
    print(f"Profil {profil}, Arm {a.arm}, Modell {a.modell}, Runde {a.runde}, "
          f"VORHER_REF {VORHER_REF[:12]}, Aufrufe geplant {aufrufe_geplant}")
    for f in faelle:
        print(f"  Fall {f.name}: {len(f.segmente)} Segmente, "
              f"{len(''.join(f.segmente))} Zeichen, {len(f.soll)} Soll-Gruppen")
    if a.trocken:
        for v in ("IT_LLM_URL", "IT_LLM_KEY", "IT_LLM_MODELL"):
            print(f"  {v}: {'ja' if os.environ.get(v) else 'nein'}")
        return 0
    if a.modell == "kimi" and aufrufe_geplant > MAX_AUFRUFE:
        raise SystemExit(f"{aufrufe_geplant} Aufrufe > MAX_AUFRUFE={MAX_AUFRUFE}")

    import httpx

    tmp = tempfile.mkdtemp(prefix="begriffsboard-messung-")
    tmp_db = str(Path(tmp) / "wegwerf.db")
    os.environ["IT_DB"] = tmp_db
    einst = dataclasses.replace(einstellungen.laden(), db_pfad=tmp_db)
    if a.modell == "kimi" and "kimi" not in (einst.llm_modell or "").casefold():
        raise SystemExit(f"IT_LLM_MODELL={einst.llm_modell} ist nicht Kimi -- Padua-Env laden.")
    conn = db.verbinde(tmp_db)
    db.initialisiere(conn)
    zaehl = {"aufrufe": 0}

    def kosten() -> float:
        return float(conn.execute("SELECT COALESCE(SUM(kosten_chf), 0) FROM aufruf").fetchone()[0])

    with httpx.Client(timeout=180.0) as klient:
        klm = llm.LLM(einst, klient, conn)
        claude = None
        if a.modell == "opus":
            from simulation.claude import Claude
            claude = Claude(klient)

        def rufe(st: Stand, nutzer: str) -> list:
            if a.modell == "kimi" and (zaehl["aufrufe"] >= MAX_AUFRUFE or kosten() >= BUDGET_CHF):
                raise SystemExit(f"Budget erreicht: {zaehl['aufrufe']} Aufrufe, {kosten():.3f} CHF")
            zaehl["aufrufe"] += 1
            if a.modell == "kimi":
                return _board_aus(klm.schema(None, st.system, nutzer, st.schema, ART))
            return _board_aus(claude.json_objekt(
                st.system, nutzer + OPUS_ZUSATZ.format(schema=json.dumps(st.schema)), art=ART))

        ergebnis = {"arm": a.arm, "modell": a.modell if a.modell == "opus" else einst.llm_modell,
                    "runde": a.runde, "vorher_ref": VORHER_REF,
                    "datum": datetime.now().isoformat(timespec="seconds"), "faelle": {}}
        for fall in faelle:
            roh_z, val_z, fehler = [], [], 0
            for lauf in range(1, a.laeufe + 1):
                try:
                    zahlen, roh, validiert = ein_lauf(rufe, stand, fall, profil)
                except SystemExit:
                    raise
                except Exception as fehler_obj:  # ein gescheiterter Lauf reisst die Messung nicht mit
                    print(f"  {fall.name} Lauf {lauf}: FEHLER {type(fehler_obj).__name__}")
                    fehler += 1
                    continue
                roh_z.append(zahlen["roh"])
                val_z.append(zahlen["validiert"])
                pfad = roh_pfad(fall.name, a.arm, a.modell, a.runde, lauf)
                if pfad is not None:
                    pfad.parent.mkdir(parents=True, exist_ok=True)
                    pfad.write_text(json.dumps({"roh": roh, "validiert": validiert},
                                               ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  {fall.name} Lauf {lauf}: roh {zahlen['roh']} | validiert {zahlen['validiert']}")
            ergebnis["faelle"][fall.name] = {"laeufe": len(roh_z), "fehler": fehler,
                                             "roh": zaehler.summe(roh_z),
                                             "validiert": zaehler.summe(val_z)}
        ergebnis["aufrufe"] = zaehl["aufrufe"]
        ergebnis["kosten_chf"] = round(kosten(), 4)

    MESS_VERZ.mkdir(parents=True, exist_ok=True)
    ziel = MESS_VERZ / (f"{datetime.now():%Y-%m-%d}-{a.arm}-{a.modell}-r{a.runde}.json")
    ziel.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Geschrieben: {ziel.relative_to(WURZEL)} ({ergebnis['aufrufe']} Aufrufe, "
          f"{ergebnis['kosten_chf']} CHF)")
    print(zaehler.tabelle([ergebnis]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
