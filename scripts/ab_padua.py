"""Messung 2, Achse B: der Padua-Testsatz aus Messung 1, json gegen tools.

Der Testsatz (``padua_testsatz``, echte Padua-Daten, E8) liegt privat unter
``IT_PRIVAT_KORPUS`` und wird ueber ``pruefe_prompts.lade_korpus`` gelesen.
Rohdaten gehen nach ``korpus/berichte/ab/B-*.jsonl`` (gitignored).

Standard ist eine frische Wegwerf-Datenbank: kein Fall des Testsatzes traegt
einen eigenen ``arbeitsstand`` (alle leer), die Chatverlaeufe stehen im Fall
selbst. Eine ``--kopie`` von ``betrieb/padua.db`` (nur lesend, ``VACUUM INTO``)
ist OPTIONAL und nur sinnvoll mit ``--chat-id gN=<chat_id>``: erst dann sehen
die Stueckwerkzeuge die echten Szenen der Gruppe. Achtung: Tools-Aufrufe
schreiben dann in die Kopie und wirken auf spaetere Faelle derselben Gruppe.

Laeuft NIE automatisch. Start (als Modul):
  uv run --extra dev python -m scripts.ab_padua --modus beide
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

import httpx

from interview_theater import db, einstellungen, repo
from scripts import ab_pipeline_vs_tools as ab
from scripts import pruefe_prompts as pp
from scripts import stueckmodell_kopie

TESTSATZ = "padua_testsatz"
SPRACHE = "en"
#: Achse A nutzt nummer*10+1|2; hier ab 100000, damit sich nie etwas ueberschneidet.
CHAT_BASIS = 100000


def lade_testsatz(nur: list[str] | None = None) -> list[dict]:
    """Korpus-Fallformat (``id``, ``nachrichten``, ``arbeitsstand``, ``erwartet``)."""
    return pp.lade_korpus(TESTSATZ, nur, sprache=SPRACHE)


def bereite_kopie_vor(quelle: str, ziel: str) -> None:
    if "padua-test" in Path(quelle).name:
        raise SystemExit("Messung nur auf betrieb/padua.db")
    stueckmodell_kopie.kopiere(quelle, ziel)


def chat_id_fuer(nummer: int, modus: str) -> int:
    return CHAT_BASIS + nummer * 10 + (1 if modus == "json" else 2)


def standard_ausgabe() -> Path:
    return ab.ROH_VERZ / f"B-{time.strftime('%Y%m%d-%H%M')}.jsonl"


def laufe_testsatz(faelle, e, db_pfad: str | None, aus: str, modi=("json", "tools"),
                   kopie: str | None = None, gruppen_chat: dict | None = None) -> None:
    if kopie:
        conn = db.verbinde(kopie)
        db.initialisiere(conn)
    else:
        conn = ab._messkopie_db(db_pfad)
    klient = httpx.Client(timeout=120.0)
    Path(aus).parent.mkdir(parents=True, exist_ok=True)
    with Path(aus).open("a", encoding="utf-8") as datei:
        for nummer, fall in enumerate(faelle, start=1):
            gruppe = (fall.get("herkunft") or {}).get("gruppe")
            for modus in modi:
                chat_id = (gruppen_chat or {}).get(gruppe) or chat_id_fuer(nummer, modus)
                repo.sichere_gruppe(conn, chat_id, "ab", fall["id"])
                zeile = (ab.laufe_json(conn, e, klient, chat_id, fall) if modus == "json"
                         else ab.laufe_tools(conn, e, chat_id, fall))
                zeile.update(achse="B", sprache=SPRACHE, gruppe=gruppe)
                datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
                datei.flush()
                print(f"[{nummer}/{len(faelle)}] {modus} {fall['id']}: "
                      f"T{zeile['treffer']} FP{zeile['fp']} FN{zeile['fn']}"
                      + (f" FEHLER {zeile['fehler']}" if zeile["fehler"] else ""), flush=True)
    print(f"Rohdaten: {aus}")


def baue_argumente(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m scripts.ab_padua")
    p.add_argument("--modus", choices=("json", "tools", "beide"), default="beide")
    p.add_argument("--nur", nargs="*")
    p.add_argument("--db", help="frische Messdatenbank (Vorgabe: temporaer)")
    p.add_argument("--aus")
    p.add_argument("--quelle", default="betrieb/padua.db",
                   help="nur zusammen mit --kopie: Quelle der Kopie (nur lesend)")
    p.add_argument("--kopie", help="OPTIONAL: Kopie von betrieb/padua.db als Messdatenbank")
    p.add_argument("--chat-id", action="append", default=[], metavar="GRUPPE=ID",
                   help="mit --kopie: echte chat_id der Gruppe (z. B. g1=-100123)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = baue_argumente(argv)
    gruppen = {}
    for eintrag in args.chat_id:
        schluessel, _, wert = eintrag.partition("=")
        gruppen[schluessel] = int(wert)
    if gruppen and not args.kopie:
        raise SystemExit("--chat-id nur zusammen mit --kopie")
    if args.kopie:
        bereite_kopie_vor(args.quelle, args.kopie)
    e = dataclasses.replace(einstellungen.laden(), szene_anbieter="claude",
                            erkenner_modus="tools", szene_modell=ab.OPUS)
    modi = ("json", "tools") if args.modus == "beide" else (args.modus,)
    laufe_testsatz(lade_testsatz(args.nur), e, args.db, args.aus or str(standard_ausgabe()),
                   modi, kopie=args.kopie, gruppen_chat=gruppen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
