"""Messung 2 (Karte t_9b2b33cb): Pipeline gegen Agent auf denselben Daten.

Achse A: der Erkenner-Korpus (korpus/erkenner.jsonl, korpus/en/erkenner.jsonl)
einmal ueber den heutigen JSON-Weg (Opus fuellt das Schema), einmal im
Tools-Modus (Opus ruft die Stueckwerkzeuge). Beide ueber den Abo-Proxy
(0 CHF). Gezaehlt wird mit dem unveraenderten
``pruefe_prompts.vergleiche_erkenner`` -- die Tools-Seite wird dafuer in die
Korpus-Sprache zurueckuebersetzt (``erkenner_werkzeuge.als_aenderung``,
Spec § 2.3).

Laeuft NIE automatisch. Start (als Modul):
  uv run --extra dev python -m scripts.ab_pipeline_vs_tools erkenner --sprache de --modus beide
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import tempfile
import time
from pathlib import Path

import httpx

from interview_theater import db, einstellungen, erkenner, erkenner_werkzeuge, repo, szene_claude
from scripts import pruefe_prompts as pp

ROH_VERZ = Path("korpus/berichte/ab")
OPUS = "claude-opus-5-5"


def nutzertext_fuer(conn, chat_id: int, fall: dict) -> str:
    """Derselbe Nutzertext wie ``pruefe_prompts._laufe_erkenner``."""
    if fall.get("aufnahme"):
        return erkenner.baue_aufnahme_nutzertext(fall["aufnahme"])
    pp._fuelle_arbeitsstand(conn, chat_id, fall.get("arbeitsstand"))
    zeilen = pp._nachrichtenzeilen(fall["nachrichten"])
    vorlauf = None
    if fall.get("vorlauf"):
        vorlauf = pp._nachrichtenzeilen([{"absender": "Bot", "text": fall["vorlauf"]}])[0]
    elif len(zeilen) > 1 and zeilen[0]["ist_bot"]:
        vorlauf, zeilen = zeilen[0], zeilen[1:]
    return erkenner._baue_nutzertext(conn, chat_id, zeilen, vorlauf)


def _filter(fall: dict, geliefert: list[dict]) -> list[dict]:
    geliefert = geliefert[: erkenner.MAX_AENDERUNGEN]
    if fall.get("aufnahme"):
        geliefert = [a for a in geliefert if a.get("art") in erkenner.ARTEN_IN_AUFNAHME]
    return erkenner.waechter_filter(geliefert)


def _leer(modus: str, fall: dict) -> dict:
    return {"achse": "A", "modus": modus, "id": fall["id"], "treffer": 0, "fp": 0,
            "fn": len(fall.get("erwartet", [])), "still_fp": 0, "ohne_korpusart": 0,
            "abgelehnt": 0, "abbruch": None, "runden": 0, "eingabe_token": 0,
            "ausgabe_token": 0, "dauer_ms": 0, "fehler": None, "geliefert": [],
            "aufrufe": []}


def _zaehle(zeile: dict, fall: dict, geliefert: list[dict]) -> dict:
    bewertung = pp.vergleiche_erkenner(fall["erwartet"], geliefert)
    zeile.update(treffer=len(bewertung["treffer"]), fp=len(bewertung["ueberzaehlig"]),
                 fn=len(bewertung["fehlend"]), geliefert=geliefert)
    return zeile


def laufe_json(conn, e, klient, chat_id: int, fall: dict) -> dict:
    zeile = _leer("json", fall)
    start = time.monotonic()
    vorher = pp._hoechste_aufruf_id(conn)
    try:
        nutzer = nutzertext_fuer(conn, chat_id, fall)
        roh = szene_claude.schema(conn, e, klient, chat_id, erkenner.prompt(), nutzer,
                                  erkenner.schema(), "erkenner", timeout=60.0, modell=OPUS)
        _zaehle(zeile, fall, _filter(fall, roh.get("aenderungen", [])))
    except Exception as fehler:  # noqa: BLE001 -- ein Fall bricht den Lauf nie ab
        zeile["fehler"] = f"{type(fehler).__name__}: {fehler}"
    gemessen = pp._aufruf_nach(conn, vorher)
    zeile.update(still_fp=zeile["fp"], runden=1,
                 eingabe_token=gemessen["eingabe_token"],
                 ausgabe_token=gemessen["ausgabe_token"],
                 dauer_ms=int((time.monotonic() - start) * 1000))
    return zeile


def laufe_tools(conn, e, chat_id: int, fall: dict) -> dict:
    zeile = _leer("tools", fall)
    start = time.monotonic()
    try:
        nutzer = nutzertext_fuer(conn, chat_id, fall)
        generisch, _, lauf, ausfuehrungen = erkenner._werkzeuglauf(conn, e, chat_id, nutzer)
        uebersetzt = [x for x in (erkenner_werkzeuge.als_aenderung(a) for a in ausfuehrungen)
                      if x is not None]
        _zaehle(zeile, fall, _filter(fall, uebersetzt))
        ohne = sum(1 for a in ausfuehrungen if a.generisch is None and a.ok
                   and a.name not in erkenner_werkzeuge.ART_FUER_WERKZEUG)
        zeile.update(
            ohne_korpusart=ohne,
            abgelehnt=sum(1 for a in ausfuehrungen if not a.ok),
            abbruch=lauf.abbruch, runden=lauf.runden,
            eingabe_token=lauf.eingabe_token, ausgabe_token=lauf.ausgabe_token,
            aufrufe=[{"name": a.name, "eingabe": a.eingabe, "ok": a.ok, "fehler": a.fehler}
                     for a in ausfuehrungen],
        )
        zeile["still_fp"] = zeile["fp"] + ohne
        zeile["dauer_ms"] = lauf.dauer_ms
    except Exception as fehler:  # noqa: BLE001
        zeile["fehler"] = f"{type(fehler).__name__}: {fehler}"
        zeile["dauer_ms"] = int((time.monotonic() - start) * 1000)
    return zeile


def _messkopie_db(pfad: str | None):
    pfad = pfad or str(Path(tempfile.mkdtemp(prefix="ab_")) / "korpus.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    return conn


def _erkenner(args) -> int:
    e = dataclasses.replace(einstellungen.laden(), szene_anbieter="claude",
                            erkenner_modus="tools", szene_modell=OPUS)
    conn = _messkopie_db(args.db)
    faelle = pp.lade_korpus("erkenner", args.nur, sprache=args.sprache)
    modi = ("json", "tools") if args.modus == "beide" else (args.modus,)
    ROH_VERZ.mkdir(parents=True, exist_ok=True)
    aus = Path(args.aus or ROH_VERZ / f"A-{args.sprache}-{time.strftime('%Y%m%d-%H%M')}.jsonl")
    klient = httpx.Client(timeout=120.0)
    with aus.open("a", encoding="utf-8") as datei:
        for nummer, fall in enumerate(faelle, start=1):
            for modus in modi:
                chat_id = nummer * 10 + (1 if modus == "json" else 2)
                repo.sichere_gruppe(conn, chat_id, "ab", fall["id"])
                zeile = (laufe_json(conn, e, klient, chat_id, fall) if modus == "json"
                         else laufe_tools(conn, e, chat_id, fall))
                zeile["sprache"] = args.sprache
                datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
                datei.flush()
                print(f"[{nummer}/{len(faelle)}] {modus} {fall['id']}: "
                      f"T{zeile['treffer']} FP{zeile['fp']} FN{zeile['fn']}"
                      + (f" FEHLER {zeile['fehler']}" if zeile["fehler"] else ""), flush=True)
    print(f"Rohdaten: {aus}")
    return 0


def baue_argumente(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m scripts.ab_pipeline_vs_tools")
    unter = p.add_subparsers(dest="befehl", required=True)
    a = unter.add_parser("erkenner", help="Achse A: Korpus, json gegen tools")
    a.add_argument("--sprache", choices=("de", "en"), default="de")
    a.add_argument("--modus", choices=("json", "tools", "beide"), default="beide")
    a.add_argument("--nur", nargs="*")
    a.add_argument("--db")
    a.add_argument("--aus")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = baue_argumente(argv)
    if args.befehl == "erkenner":
        return _erkenner(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
