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
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

import httpx

from interview_theater import (
    db, einstellungen, erkenner, erkenner_werkzeuge, repo, sprache, stueck, szene_claude,
    workshop,
)
from scripts import pruefe_prompts as pp

ROH_VERZ = Path("korpus/berichte/ab")
OPUS = "claude-opus-5-5"


#: Synthetischer Stueckstand der Achse A2 (erfundene, neutrale Namen; keine
#: echten Daten). Je Sprache dieselbe Struktur: 3 Szenen, 3 Figuren, Besetzung,
#: Rahmen, Karte je Szene, eine offene Frage in Szene 2 und eine allgemeine.
SZENENSTAND = {
    "de": {
        "rahmen": "Ein Abend am Hafen",
        "szenen": [
            ("Ankunft", "Hafenmole", ("Anna", "Bruno"), "Anna wartet auf ein Schiff."),
            ("Warten", "Wartehalle", ("Bruno", "Clara"), "Bruno und Clara teilen sich eine Bank."),
            ("Abschied", "Dachterrasse", ("Anna", "Clara"), "Clara verabschiedet Anna."),
        ],
        "fragen": [(2, "Wer hat den Brief geschrieben?"), (None, "Wie lang darf das Stück sein?")],
        "kopf": "Szenenstand",
        "zeile": "Szene {n} «{titel}» | Ort: {ort} | Wer: {wer} | Worum: {worum}",
        "fragen_kopf": "Offene Fragen",
        "frage": "Frage {id}{szene}: {text} ({status})",
        "bei": " (Szene {n})",
        "rahmen_zeile": "Rahmen: {rahmen}",
    },
    "en": {
        "rahmen": "An evening at the harbour",
        "szenen": [
            ("Arrival", "Harbour pier", ("Anna", "Bruno"), "Anna waits for a ship."),
            ("Waiting", "Waiting hall", ("Bruno", "Clara"), "Bruno and Clara share a bench."),
            ("Farewell", "Roof terrace", ("Anna", "Clara"), "Clara says goodbye to Anna."),
        ],
        "fragen": [(2, "Who wrote the letter?"), (None, "How long may the play be?")],
        "kopf": "Scene state",
        "zeile": "Scene {n} \"{titel}\" | Place: {ort} | Who: {wer} | About: {worum}",
        "fragen_kopf": "Open questions",
        "frage": "Question {id}{szene}: {text} ({status})",
        "bei": " (scene {n})",
        "rahmen_zeile": "Frame: {rahmen}",
    },
}


def lege_szenenstand(conn, chat_id: int, sprache_: str) -> None:
    """Spielt den synthetischen Stand in eine frische ``chat_id`` -- nur ueber
    die vorhandenen Schreibwege (``stueck``-Werkzeuge, ``repo``-Funktionen),
    deterministisch, ohne SQL."""
    d = SZENENSTAND[sprache_]
    stueck.setze_rahmen(conn, chat_id, rahmen=d["rahmen"])
    for nummer, (titel, ort, wer, worum) in enumerate(d["szenen"], start=1):
        szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
        repo.aktualisiere_szene(conn, szene_id, titel, None, None)
        repo.setze_szenenkarte(conn, szene_id, json.dumps(
            {"worum": worum, "typ": "description", "modus": "none", "punkte": []},
            ensure_ascii=False))
        stueck.setze_ort(conn, chat_id, szene=nummer, ort=ort)
        for name in wer:
            stueck.figur_hinzu(conn, chat_id, name=name, szene=nummer)
    for szene, frage in d["fragen"]:
        stueck.frage_stellen(conn, chat_id, frage=frage, szene=szene)


def szenenstand_text(conn, chat_id: int, sprache_: str) -> str:
    """Der Stand als Textblock fuer den Nutzertext -- aus der Datenbank
    gelesen (nicht aus der Konstante), damit beide Modi dieselben ``frage_id``
    sehen, die ``frage_beantworten`` braucht."""
    d = SZENENSTAND[sprache_]
    zeilen = [d["rahmen_zeile"].format(rahmen=(repo.hole_arbeitsstand(conn, chat_id) or {})["rahmen"] or "")]
    nummer_von = {}
    for s in repo.hole_szenen(conn, chat_id):
        nummer_von[s["id"]] = s["nummer"]
        wer = ", ".join(b["name"] for b in repo.besetzung(conn, s["id"]))
        worum = (json.loads(s["karte"]).get("worum") if s["karte"] else "") or ""
        zeilen.append(d["zeile"].format(n=s["nummer"], titel=s["titel"], ort=s["ort"],
                                        wer=wer, worum=worum))
    fragen = list(repo.offene_fragen(conn, chat_id, None))
    for s in repo.hole_szenen(conn, chat_id):
        fragen += repo.offene_fragen(conn, chat_id, s["id"])
    kopf = [f"{d['kopf']}:"]
    if fragen:
        zeilen.append(f"{d['fragen_kopf']}:")
    for f in sorted(fragen, key=lambda f: f["id"]):
        szene = d["bei"].format(n=nummer_von[f["szene_id"]]) if f["szene_id"] in nummer_von else ""
        zeilen.append("- " + d["frage"].format(id=f["id"], szene=szene, text=f["text"],
                                               status=f["status"]))
    return "\n".join(kopf + zeilen)


def nutzertext_fuer(conn, chat_id: int, fall: dict, szenen: str | None = None) -> str:
    """Derselbe Nutzertext wie ``pruefe_prompts._laufe_erkenner``. Mit
    ``szenen`` (Sprache, Achse A2) haengt der Szenenstand dahinter -- fuer
    beide Modi derselbe Text. Der Live-Erkenner sieht Szenen nicht im
    Nutzertext; das ist eine bewusste Abweichung der Messung."""
    if fall.get("aufnahme"):
        return erkenner.baue_aufnahme_nutzertext(fall["aufnahme"])
    pp._fuelle_arbeitsstand(conn, chat_id, fall.get("arbeitsstand"))
    zeilen = pp._nachrichtenzeilen(fall["nachrichten"])
    vorlauf = None
    if fall.get("vorlauf"):
        vorlauf = pp._nachrichtenzeilen([{"absender": "Bot", "text": fall["vorlauf"]}])[0]
    elif len(zeilen) > 1 and zeilen[0]["ist_bot"]:
        vorlauf, zeilen = zeilen[0], zeilen[1:]
    text = erkenner._baue_nutzertext(conn, chat_id, zeilen, vorlauf)
    if szenen:
        text = szenenstand_text(conn, chat_id, szenen) + "\n\n" + text
    return text


def _filter(fall: dict, geliefert: list[dict]) -> list[dict]:
    geliefert = geliefert[: erkenner.MAX_AENDERUNGEN]
    if fall.get("aufnahme"):
        geliefert = [a for a in geliefert if a.get("art") in erkenner.ARTEN_IN_AUFNAHME]
    return erkenner.waechter_filter(geliefert)


def _leer(modus: str, fall: dict, achse: str = "A") -> dict:
    return {"achse": achse, "modus": modus, "id": fall["id"], "treffer": 0, "fp": 0,
            "fn": len(fall.get("erwartet", [])),
            "aufnahme": bool(fall.get("aufnahme")), "modellaufrufe": 0, "still_fp": 0, "ohne_korpusart": 0,
            "abgelehnt": 0, "abbruch": None, "runden": 0, "eingabe_token": 0,
            "ausgabe_token": 0, "dauer_ms": 0, "fehler": None, "geliefert": [],
            "aufrufe": [], "absicht_treffer": 0, "absicht_fp": 0,
            "absicht_fn": len(fall.get("erwartet", [])), "abgelehnt_gruende": {},
            "werkzeug_erwartet": len(fall.get("erwartet_werkzeuge", [])),
            "werkzeug_treffer": 0}


def _zaehle(zeile: dict, fall: dict, geliefert: list[dict]) -> dict:
    bewertung = pp.vergleiche_erkenner(fall["erwartet"], geliefert)
    zeile.update(treffer=len(bewertung["treffer"]), fp=len(bewertung["ueberzaehlig"]),
                 fn=len(bewertung["fehlend"]), geliefert=geliefert)
    zeile.update(absicht_treffer=zeile["treffer"], absicht_fp=zeile["fp"],
                 absicht_fn=zeile["fn"])
    return zeile


def laufe_json(conn, e, klient, chat_id: int, fall: dict, szenen: str | None = None) -> dict:
    zeile = _leer("json", fall, "A2" if szenen else "A")
    vorher = pp._hoechste_aufruf_id(conn)
    try:
        nutzer = nutzertext_fuer(conn, chat_id, fall, szenen)
        start = time.monotonic()
        try:
            roh = szene_claude.schema(conn, e, klient, chat_id, erkenner.prompt(), nutzer,
                                      erkenner.schema(), "erkenner", timeout=60.0, modell=OPUS)
        finally:
            zeile["dauer_ms"] = int((time.monotonic() - start) * 1000)
        _zaehle(zeile, fall, _filter(fall, roh.get("aenderungen", [])))
    except Exception as fehler:  # noqa: BLE001 -- ein Fall bricht den Lauf nie ab
        zeile["fehler"] = f"{type(fehler).__name__}: {fehler}"
    zeile.update(still_fp=zeile["fp"], runden=1, **repo.aufruf_summe_nach(conn, vorher))
    return zeile


def laufe_tools(conn, e, chat_id: int, fall: dict, szenen: str | None = None) -> dict:
    zeile = _leer("tools", fall, "A2" if szenen else "A")
    vorher = pp._hoechste_aufruf_id(conn)
    try:
        nutzer = nutzertext_fuer(conn, chat_id, fall, szenen)
        start = time.monotonic()
        try:
            generisch, _, lauf, ausfuehrungen = erkenner._werkzeuglauf(conn, e, chat_id, nutzer)
        finally:
            zeile["dauer_ms"] = int((time.monotonic() - start) * 1000)
        uebersetzt = [x for x in (erkenner_werkzeuge.als_aenderung(a) for a in ausfuehrungen)
                      if x is not None]
        _zaehle(zeile, fall, _filter(fall, uebersetzt))
        # Nebenzaehlung: erkannte Absicht, auch wenn das Stueck den Aufruf ablehnte
        absichten = [x for x in (erkenner_werkzeuge.als_absicht(a) for a in ausfuehrungen)
                     if x is not None]
        einmalig = list({(x["art"], x["wert"]): x for x in absichten}.values())
        bew = pp.vergleiche_erkenner(fall["erwartet"], _filter(fall, einmalig))
        zeile.update(absicht_treffer=len(bew["treffer"]), absicht_fp=len(bew["ueberzaehlig"]),
                     absicht_fn=len(bew["fehlend"]))
        gruende: dict[str, int] = {}
        for a in ausfuehrungen:
            if not a.ok:
                gruende[a.fehler or "unbekannt"] = gruende.get(a.fehler or "unbekannt", 0) + 1
        zeile["abgelehnt_gruende"] = gruende
        erwartet_w = list(fall.get("erwartet_werkzeuge", []))
        ohne = sum(1 for a in ausfuehrungen if a.generisch is None and a.ok
                   and a.name not in erkenner_werkzeuge.ART_FUER_WERKZEUG
                   and a.name not in erwartet_w)
        gerufen = [a.name for a in ausfuehrungen if a.ok]
        for name in erwartet_w:           # je erwartetem Namen hoechstens ein Treffer
            if name in gerufen:
                gerufen.remove(name)
                zeile["werkzeug_treffer"] += 1
        zeile.update(
            ohne_korpusart=ohne,
            abgelehnt=sum(1 for a in ausfuehrungen if not a.ok),
            abbruch=lauf.abbruch, runden=lauf.runden,
            aufrufe=[{"name": a.name, "eingabe": a.eingabe, "ok": a.ok, "fehler": a.fehler}
                     for a in ausfuehrungen],
        )
        zeile["still_fp"] = zeile["fp"] + ohne
    except Exception as fehler:  # noqa: BLE001
        zeile["fehler"] = f"{type(fehler).__name__}: {fehler}"
    zeile.update(repo.aufruf_summe_nach(conn, vorher))
    return zeile


def _messkopie_db(pfad: str | None):
    """Frische Datenbank: eine bereits befuellte Datei wird abgelehnt, weil
    ``chat_id = nummer*10 + 1|2`` sich wiederholt und alter Stueckstand sonst
    in den naechsten Fall leckt."""
    if pfad and Path(pfad).exists() and Path(pfad).stat().st_size > 0:
        raise SystemExit(f"--db {pfad}: Datei existiert und ist nicht leer. Die Messung "
                         "braucht eine frische Datenbank (ohne --db wird eine angelegt).")
    pfad = pfad or str(Path(tempfile.mkdtemp(prefix="ab_")) / "korpus.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    return conn


def sichere_sprache(code: str, *, profil_setzen: bool = False, workshop_name: str | None = None) -> None:
    """Wie ``pruefe_prompts.main``: die Korpussprache muss zur Promptsprache
    des aktiven Profils passen, sonst laufen englische Faelle still gegen den
    deutschen Prompt. ``profil_setzen`` (nur der CLI-Einstieg, nie ``main()``
    ohne Absicht -- Prozessspeicher, vgl. 4d822ac) setzt fuer ``en`` das
    Profil selbst."""
    if profil_setzen and code == "en":
        os.environ[workshop.VARIABLE] = workshop_name or "padua-2026"
        workshop.vergiss()
    if sprache.code() != code:
        raise SystemExit(
            f"IT_WORKSHOP={os.environ.get(workshop.VARIABLE)!r} ergibt "
            f"sprache.code()={sprache.code()!r}, nicht {code!r} -- der Korpus "
            "passt nicht zur Promptsprache.")


def lade_faelle(pfad: str, nur: list[str] | None = None) -> list[dict]:
    """Eigene Fallliste im Korpusformat (z. B. ``korpus/ab_a2_de.jsonl``)."""
    faelle = [json.loads(z) for z in Path(pfad).read_text(encoding="utf-8").splitlines()
              if z.strip()]
    return [f for f in faelle if not nur or f["id"] in nur]


def _erkenner(args) -> int:
    e = dataclasses.replace(einstellungen.laden(), szene_anbieter="claude",
                            erkenner_modus="tools", szene_modell=OPUS)
    conn = _messkopie_db(args.db)
    faelle = (lade_faelle(args.faelle, args.nur) if args.faelle
              else pp.lade_korpus("erkenner", args.nur, sprache=args.sprache))
    szenen = args.sprache if args.szenen else None
    modi = ("json", "tools") if args.modus == "beide" else (args.modus,)
    ROH_VERZ.mkdir(parents=True, exist_ok=True)
    aus = Path(args.aus or ROH_VERZ / f"{'A2' if szenen else 'A'}-{args.sprache}-{time.strftime('%Y%m%d-%H%M')}.jsonl")
    klient = httpx.Client(timeout=120.0)
    with aus.open("a", encoding="utf-8") as datei:
        for nummer, fall in enumerate(faelle, start=1):
            for modus in modi:
                chat_id = nummer * 10 + (1 if modus == "json" else 2)
                repo.sichere_gruppe(conn, chat_id, "ab", fall["id"])
                if szenen:
                    lege_szenenstand(conn, chat_id, szenen)
                zeile = (laufe_json(conn, e, klient, chat_id, fall, szenen) if modus == "json"
                         else laufe_tools(conn, e, chat_id, fall, szenen))
                zeile["sprache"] = args.sprache
                datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
                datei.flush()
                print(f"[{nummer}/{len(faelle)}] {modus} {fall['id']}: "
                      f"T{zeile['treffer']} FP{zeile['fp']} FN{zeile['fn']}"
                      + (f" FEHLER {zeile['fehler']}" if zeile["fehler"] else ""), flush=True)
    print(f"Rohdaten: {aus}")
    return 0


# ---------------------------------------------------------------------------
# Bericht (aus den Rohzeilen, ohne Modellaufruf; nur Kennungen und Zahlen)
# ---------------------------------------------------------------------------

BERICHT_AUS = Path("docs/messung/2026-10-ab-pipeline-vs-tools.md")
STANDARD_GRUND = {"A": "Korpus-Rohdaten fehlten", "A2": "Achse A2 (Stückwerkzeuge im Arbeitsstand) nicht gefahren", "B": "Padua-Testsatz fehlte",
                  "C": "Gold-Korpus fehlte"}
C_VARIANTEN = ("pipeline_opus", "pipeline_kimi", "agent_kimi")


def _median(werte: list) -> str:
    return f"{statistics.median(werte):.0f}" if werte else "-"


def _p90(werte: list) -> str:
    if len(werte) < 2:
        return "-"
    return f"{statistics.quantiles(werte, n=10)[-1]:.0f}"


def _kosten_zelle(summe: float) -> str:
    """Aus den Rohzeilen summiert; der Abo-Proxy bucht 0 (kein erfundener Wert)."""
    if not summe:
        return "0 CHF (Abo) — Opus über Abo-Proxy; Rohzeilen buchen kosten_chf=0.0000"
    return f"{summe:.4f} CHF (Summe der Rohzeilen-Felder kosten_chf)"


def _aufrufe_je_werkzeug(zeilen: list[dict]) -> dict[str, dict[str, list[int]]]:
    """Achse -> Werkzeugname -> [Aufrufe, abgelehnt], nur tools-Modus, nur Namen."""
    aus: dict[str, dict[str, list[int]]] = {}
    for z in zeilen:
        if z.get("modus") != "tools" or z.get("achse") not in ("A", "A2", "B"):
            continue
        for a in z.get("aufrufe") or []:
            eintrag = aus.setdefault(z["achse"], {}).setdefault(a["name"], [0, 0])
            eintrag[0] += 1
            eintrag[1] += 0 if a.get("ok") else 1
    return aus


def _werkzeug_tabelle(zeilen: list[dict]) -> list[str]:
    je = _aufrufe_je_werkzeug(zeilen)
    aus = ["### Aufrufe je Werkzeug (tools-Modus)", ""]
    if not je:
        return aus + ["Keine Werkzeugaufrufe in den Rohzeilen.", ""]
    aus += ["| Achse | Werkzeug | Aufrufe | davon abgelehnt |", "|---|---|---|---|"]
    for achse in sorted(je):
        for name, (n, abgelehnt) in sorted(je[achse].items()):
            aus.append(f"| Achse {achse} | {name} | {n} | {abgelehnt} |")
    return aus + [""]


def _nicht_geprueft(zeilen: list[dict]) -> str | None:
    je = _aufrufe_je_werkzeug([z for z in zeilen if z.get("achse") != "A2"])
    if not je:
        return None
    gerufen: dict[str, int] = {}
    for werkzeuge in je.values():
        for name, (n, _) in werkzeuge.items():
            gerufen[name] = gerufen.get(name, 0) + n
    alle = [d["name"] for d in erkenner_werkzeuge.definitionen(())]
    nie = [n for n in alle if not gerufen.get(n)]
    gesamt = sum(gerufen.values())
    generisch = gerufen.get(erkenner_werkzeuge.GENERISCH, 0)
    return (f"- Werkzeuge ohne einen einzigen Aufruf, nicht geprüft: "
            f"{', '.join(nie) if nie else 'keine'}. Die Mess-DB ist leer (keine Szenen), "
            f"und der tools-Modus lief überwiegend über das generische "
            f"`{erkenner_werkzeuge.GENERISCH}` ({generisch} von {gesamt} Aufrufen, "
            f"{100 * generisch / gesamt:.0f} %).")


def _modus_spalte(zeilen: list[dict]) -> dict[str, str]:
    """Kennzahlen EINES Modus (Zeilen schon gefiltert) als Zellen."""
    if not zeilen:
        return {}
    s = lambda k: sum(z.get(k) or 0 for z in zeilen)  # noqa: E731
    treffer, fn = s("treffer"), s("fn")
    abbrueche: dict[str, int] = {}
    for z in zeilen:
        if z.get("abbruch"):
            abbrueche[z["abbruch"]] = abbrueche.get(z["abbruch"], 0) + 1
    dauer = [z["dauer_ms"] for z in zeilen if z.get("dauer_ms")]
    return {
        "Fälle": str(len(zeilen)),
        "Treffer (Summe / erwartet gesamt)": f"{treffer} / {treffer + fn}",
        "FN": str(fn),
        "FP": str(s("fp")),
        "Absicht erkannt, Nebenzählung (Treffer / FP / FN)":
            f"{s('absicht_treffer')} / {s('absicht_fp')} / {s('absicht_fn')}",
        "stille Fehler (still_fp)": f"{s('still_fp')} (davon ohne Korpus-Art: {s('ohne_korpusart')})",
        "abgelehnt (laut)": str(s("abgelehnt")),
        "Abbrüche": (f"{sum(abbrueche.values())} ("
                     + ", ".join(f"{k}: {v}" for k, v in sorted(abbrueche.items())) + ")")
        if abbrueche else "0",
        "Runden (Median)": _median([z["runden"] for z in zeilen if z.get("runden")]),
        "Latenz Median / p90 (ms)": f"{_median(dauer)} / {_p90(dauer)}",
        "Token ein / aus (Summe)": f"{s('eingabe_token')} / {s('ausgabe_token')}",
        "Kosten": _kosten_zelle(sum(z.get("kosten_chf") or 0.0 for z in zeilen)),
        "Modellaufrufe (Summe)": str(s("modellaufrufe")),
        "Fehler (Anzahl)": str(sum(1 for z in zeilen if z.get("fehler"))),
    }


def _a2_werkzeuge(zeilen: list[dict]) -> list[str]:
    """Werkzeugverteilung und Treffer auf erwartete Werkzeugaufrufe (nur A2)."""
    tools = [z for z in zeilen if z.get("modus") == "tools"]
    erwartet = sum(z.get("werkzeug_erwartet") or 0 for z in tools)
    treffer = sum(z.get("werkzeug_treffer") or 0 for z in tools)
    aus = ["### Achse A2: Werkzeugverteilung und erwartete Werkzeugaufrufe", "",
           f"Erwartete Stückwerkzeug-Aufrufe getroffen (tools-Modus, Treffer / erwartet): "
           f"{treffer} / {erwartet}. Der json-Modus hat keine Werkzeuge.", ""]
    aus += _werkzeug_tabelle(zeilen)[2:]
    je = _aufrufe_je_werkzeug(zeilen).get("A2", {})
    nie = [d["name"] for d in erkenner_werkzeuge.definitionen(())
           if d["name"] != erkenner_werkzeuge.GENERISCH and d["name"] not in je]
    if tools:
        aus += [f"Stückwerkzeuge ohne einen Aufruf in A2: {', '.join(nie) if nie else 'keine'}.", ""]
    return aus


def _tabelle_ab(zeilen: list[dict]) -> list[str]:
    spalten = {m: _modus_spalte([z for z in zeilen if z.get("modus") == m])
               for m in ("json", "tools")}
    kennzahlen = list(spalten["json"] or spalten["tools"])
    aus = ["| Kennzahl | json | tools |", "|---|---|---|"]
    for k in kennzahlen:
        aus.append(f"| {k} | {spalten['json'].get(k, '-')} | {spalten['tools'].get(k, '-')} |")
    return aus


def _abschnitt_ab(achse: str, zeilen: list[dict]) -> list[str]:
    aus = []
    for sprache in sorted({z.get("sprache") or "?" for z in zeilen}):
        je = [z for z in zeilen if (z.get("sprache") or "?") == sprache]
        gespraech = [z for z in je if not z.get("aufnahme")]
        aufnahme = [z for z in je if z.get("aufnahme")]
        if gespraech:
            aus += [f"### Achse {achse}, Sprache {sprache}: Gesprächsfälle", ""]
            aus += _tabelle_ab(gespraech) + [""]
        if aufnahme:
            aus += [f"### Achse {achse}, Sprache {sprache}: Aufnahme-Fälle (getrennt)", "",
                    "Live laufen Aufnahmen über Infomaniak, hier über Opus; die Zahlen "
                    "stehen deshalb nicht in der Tabelle der Gesprächsfälle.", ""]
            aus += _tabelle_ab(aufnahme) + [""]
    return aus


def _mittel(zeilen: list[dict]) -> str:
    werte = [z["recall_at_10"] for z in zeilen
             if z.get("recall_at_10") is not None and not z.get("fehler")]
    return f"{sum(werte) / len(werte):.2f} (n={len(werte)})" if werte else "-"


def _abschnitt_c(zeilen: list[dict], b0: dict | None) -> list[str]:
    varianten = [v for v in C_VARIANTEN if any(z.get("variante") == v for z in zeilen)]
    varianten += sorted({z.get("variante") for z in zeilen} - set(C_VARIANTEN))
    gruppen = sorted({z["gruppe"] for z in zeilen})
    aus = ["Recall@10 nach `scripts/zitatauswahl.py`: Mittel über Ziele (je Ziel Anteil der "
           "positiven Pool-Stellen in den Top-10). Zeilen mit Fehler (auch `fallback_kimi`: "
           "Opus-Proxy fiel aus, Kimi sprang ein) werden gezählt, aber nicht gemittelt.", "",
           "| Gruppe | B0 | " + " | ".join(varianten) + " |",
           "|---|---|" + "---|" * len(varianten)]
    for g in gruppen + ["gesamt"]:
        je = [z for z in zeilen if g == "gesamt" or z["gruppe"] == g]
        if b0 is None:
            b0_zelle = "n/a"
        elif g == "gesamt":
            n = sum(v[1] for v in b0.values())
            b0_zelle = (f"{sum(v[0] * v[1] for v in b0.values()) / n:.2f} (n={n})" if n else "-")
        else:
            b0_zelle = f"{b0[g][0]:.2f} (n={b0[g][1]})" if g in b0 else "-"
        aus.append(f"| {g} | {b0_zelle} | "
                   + " | ".join(_mittel([z for z in je if z.get("variante") == v]) for v in varianten)
                   + " |")
    aus += ["", "| Kennzahl | " + " | ".join(varianten) + " |", "|---|" + "---|" * len(varianten)]

    def zeile_(name, f):
        aus.append(f"| {name} | " + " | ".join(
            f([z for z in zeilen if z.get("variante") == v], v) for v in varianten) + " |")

    zeile_("Ziele (Zeilen)", lambda je, v: str(len(je)))
    zeile_("Rückfall auf Kimi (fallback_kimi, nicht gemittelt)",
           lambda je, v: str(sum(1 for z in je if z.get("fehler") == "fallback_kimi")))
    zeile_("andere Fehler (nicht gemittelt)",
           lambda je, v: str(sum(1 for z in je if z.get("fehler") not in (None, "fallback_kimi"))))
    zeile_("Abbrüche", lambda je, v: str(sum(1 for z in je if z.get("abbruch"))))
    zeile_("Runden (Median)", lambda je, v: _median([z["runden"] for z in je if z.get("runden")]))
    zeile_("Latenz Median / p90 (ms)", lambda je, v: (
        f"{_median([z['dauer_ms'] for z in je if z.get('dauer_ms')])} / "
        f"{_p90([z['dauer_ms'] for z in je if z.get('dauer_ms')])}"))
    zeile_("Token ein / aus", lambda je, v: (
        f"{sum(z.get('eingabe_token') or 0 for z in je)} / {sum(z.get('ausgabe_token') or 0 for z in je)}"))

    def chf(je, v):
        summe = sum(z.get("kosten_chf") or 0.0 for z in je)
        return "0 CHF (Abo)" if v == "pipeline_opus" and not summe else f"{summe:.4f} CHF"

    zeile_("Kosten", chf)
    aus.append("")
    return aus


def baue_bericht(zeilen: list[dict], vorbedingungen: dict, kommandos: list[str], *,
                 gruende: dict | None = None, b0: dict | None = None,
                 datum: str | None = None) -> str:
    """Markdown-Bericht aus den Rohzeilen. ``gruende``: Achse -> Grund, falls
    keine Rohzeilen da sind. ``b0``: Gruppe -> (Recall-Mittel, n). Nur
    Kennungen und Zahlen, nie Wortlaut aus den Rohzeilen."""
    gruende = {**STANDARD_GRUND, **(gruende or {})}
    je_achse = {a: [z for z in zeilen if z.get("achse") == a] for a in ("A", "A2", "B", "C")}
    korpus = []
    for a in ("A", "A2", "B"):
        for sprache in sorted({z.get("sprache") or "?" for z in je_achse[a]}):
            ids = {z["id"] for z in je_achse[a] if (z.get("sprache") or "?") == sprache}
            korpus.append(f"Achse {a} ({sprache}): {len(ids)} Fälle")
    ziele = {z["ziel"] for z in je_achse["C"]}
    if ziele:
        korpus.append(f"Achse C: {len(ziele)} Ziele")
    aus = [
        "# Messung 2: Pipeline gegen Agent (Karte t_9b2b33cb)", "",
        f"Stand: {datum or time.strftime('%Y-%m-%d')} · Modell Achse A/B/C-Opus: `{OPUS}` "
        "über den Abo-Proxy · Spec und Vorbedingungen: "
        "`docs/messung/2026-10-ab-vorbedingungen.md`.", "",
        "Korpusgrößen: " + ("; ".join(korpus) if korpus else "keine Rohzeilen") + ".", "",
        "Dieser Bericht ist aus den Rohzeilen (`korpus/berichte/ab/*.jsonl`) erzeugt, "
        "nicht von Hand geschrieben. Er enthält nur Kennungen und Zahlen.", "",
        "## Vorbedingungen", "", "| Schlüssel | Wert |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in sorted(vorbedingungen.items())], "",
        "## Ergebnisse", "",
        "Hinweis zur Nebenzählung: Die Hauptzählung (Treffer/FP/FN) zählt, was das Stück "
        "tatsächlich angenommen hat. Die Nebenzählung „Absicht erkannt“ zählt auch "
        "abgelehnte Werkzeugaufrufe als erkannte Absicht (die Gruppe hätte ihre Absicht "
        "geäußert, das Stück lehnte nur ab). Im json-Modus sind beide Zählungen gleich.", "",
    ]
    for a, titel in (("A", "Achse A: Erkenner-Korpus"), ("B", "Achse B: Padua-Testsatz")):
        aus += [f"## {titel}", ""]
        if je_achse[a]:
            aus += _abschnitt_ab(a, je_achse[a])
        else:
            aus += [f"Achse {a}: 0 — {gruende[a]}", ""]
    aus += ["## Achse A2: Stückwerkzeuge im Arbeitsstand", ""]
    if je_achse["A2"]:
        aus += ["Synthetischer Szenenstand (3 Szenen, 3 Figuren, Besetzung, offene Fragen) "
                "je Fall, im Nutzertext beider Modi gleich; der Live-Erkenner sieht Szenen "
                "nicht im Nutzertext (bewusste Abweichung der Messung).", ""]
        aus += _abschnitt_ab("A2", je_achse["A2"]) + _a2_werkzeuge(je_achse["A2"])
    else:
        aus += [f"Achse A2: 0 — {gruende['A2']}", ""]
    aus += ["## Achse C: Zitatsuche", ""]
    if je_achse["C"]:
        aus += _abschnitt_c(je_achse["C"], b0)
    else:
        aus += [f"Achse C: 0 — {gruende['C']}", ""]
    aus += ["## Werkzeugnutzung", "", *_werkzeug_tabelle(zeilen)]
    aus += [
        "## Messgrenzen", "",
        "Abbildung Werkzeug auf Korpus-Art (`erkenner_werkzeuge.ART_FUER_WERKZEUG`), über die "
        "die Tools-Seite in die Korpus-Sprache zurückübersetzt wird:", "",
        "| Werkzeug | Korpus-Art |", "|---|---|",
        *[f"| {w} | {art} |" for w, art in erkenner_werkzeuge.ART_FUER_WERKZEUG.items()], "",
        "- Zeitgrenzen asymmetrisch wie live: json-Modus Timeout 60 s je Aufruf, tools-Modus "
        f"Gesamtbudget {szene_claude.GESAMT_TIMEOUT_S:.0f} s je Fall (`szene_claude.GESAMT_TIMEOUT_S`).",
        "- Undo: im tools-Modus gibt es keinen Erkenner-Undo-Schnappschuss für Stück-Schritte "
        "(Spec § 3.4); der Vergleich der Rücknehmbarkeit ist deshalb nicht Teil der Zahlen.",
        "- Achse C hat einen Modell-Störfaktor: Pipeline und Agent laufen auf Kimi, die "
        "Opus-Pipeline auf Opus; ein Unterschied kann am Modell oder am Verfahren liegen. "
        "Opus-Zeilen mit Rückfall auf Kimi sind markiert und nicht gemittelt.", "",
        "## Kommandos zum Nachrechnen", "", "```", *kommandos, "```", "",
        "## Was die Messung NICHT zeigt", "",
        "- Live mit Laien: keine Gruppe hat mit dem tools-Modus gearbeitet.",
        "- Gruppenerlebnis: Tempo, Vertrauen, ob die Gruppe die „Notiert:“-Meldungen versteht.",
        "- Gesprächsführung durch einen Agenten: getauscht wurde nur der Erkenner.",
        "- Langzeitstabilität über einen ganzen Workshoptag.",
        "- Undo im tools-Modus deckt Stück-Schritte nicht ab (Spec § 3.4); die Wirkung "
        "fehlender Undo-Knöpfe für Werkzeugschritte ist nicht gemessen.",
        "- Der Szenenkern wird im tools-Modus nicht neu angestoßen.",
        "- Der Padua-Testsatz ist laut Messung 1 (3/27) kein scharfes Gate.",
        "- Aufnahme-Fälle laufen live über Infomaniak, in der Messung über Opus; ihre "
        "Zahlen sind deshalb nur getrennt und mit Vorsicht zu lesen.",
        *([_np] if (_np := _nicht_geprueft(zeilen)) else []), "",
        "Keine Empfehlung. Die Entscheidung trifft Birk (Kriterium 1: bei Gleichstand "
        "zählen Vision/Pflege, das heißt Agent).", "",
    ]
    return "\n".join(aus)


def _b0_aus_dateien(gold_pfad: str, b0_pfad: str, zeilen_c: list[dict]) -> dict | None:
    """B0-Recall je Gruppe (Mittel über Ziele, nur Ziele der C-Zeilen). ``None``,
    wenn Gold oder B0 fehlt."""
    if not (Path(gold_pfad).exists() and Path(b0_pfad).exists()):
        return None
    from scripts import ab_zitate, zitatauswahl as za

    gold = za.lade_gold(gold_pfad)
    ranglisten: dict = {}
    for z in Path(b0_pfad).read_text(encoding="utf-8").splitlines():
        if z.strip():
            ranglisten.update(json.loads(z)["ranglisten"])
    gewollt = {z["ziel"] for z in zeilen_c}
    je_ziel: dict[str, list[dict]] = {}
    for g in za._positiv(gold):
        if g["im_pool"] and za.ziel_schluessel(g) in ranglisten:
            je_ziel.setdefault(za.ziel_schluessel(g), []).append(g)
    summen: dict[str, list[float]] = {}
    for schluessel, golds in je_ziel.items():
        if gewollt and schluessel not in gewollt:
            continue
        r = ab_zitate.recall_at_10(ranglisten[schluessel], golds)
        if r is not None:
            summen.setdefault(golds[0]["gruppe"], []).append(r)
    return {g: (sum(w) / len(w), len(w)) for g, w in summen.items()}


def lade_rohzeilen(pfade) -> list[dict]:
    zeilen = []
    for pfad in pfade:
        p = Path(pfad)
        if not p.is_file():
            continue
        for z in p.read_text(encoding="utf-8").splitlines():
            if z.strip():
                zeilen.append(json.loads(z))
    return zeilen


def _bericht(args) -> int:
    zeilen = lade_rohzeilen(args.roh)
    gruende = {a: g for a, g in (("A", args.achse_a_grund), ("A2", args.achse_a2_grund),
                                 ("B", args.achse_b_grund), ("C", args.achse_c_grund)) if g}
    vor = {"ACHSE_A": "ja" if any(z.get("achse") == "A" for z in zeilen) else "nein",
           "ACHSE_B": "ja" if any(z.get("achse") == "B" for z in zeilen) else "nein",
           "ACHSE_C": "ja" if any(z.get("achse") == "C" for z in zeilen) else "nein"}
    vor["ACHSE_A2"] = "ja" if any(z.get("achse") == "A2" for z in zeilen) else "nein"
    for eintrag in args.vorbedingung:
        k, _, v = eintrag.partition("=")
        vor[k] = v
    b0 = _b0_aus_dateien(args.gold, args.b0, [z for z in zeilen if z.get("achse") == "C"])
    roh = " ".join(args.roh)
    bericht_cmd = (f"uv run --extra dev python -m scripts.ab_pipeline_vs_tools bericht "
                   f"--roh {roh} --aus {args.aus}"
                   + "".join(f' --achse-{a.lower()}-grund "{g}"' for a, g in gruende.items()))
    kommandos = [
        "uv run --extra dev python -m scripts.ab_pipeline_vs_tools erkenner --sprache de --modus beide",
        "uv run --extra dev python -m scripts.ab_pipeline_vs_tools erkenner --sprache en --modus beide",
        "uv run --extra dev python -m scripts.ab_pipeline_vs_tools erkenner --sprache de --modus beide "
        "--szenen --faelle korpus/ab_a2_de.jsonl",
        "uv run --extra dev python -m scripts.ab_pipeline_vs_tools erkenner --sprache en --modus beide "
        "--szenen --faelle korpus/ab_a2_en.jsonl",
        "uv run --extra dev python -m scripts.ab_padua --modus beide",
        "uv run --extra dev python -m scripts.ab_zitate --ohne-modell",
        "uv run --extra dev python -m scripts.ab_zitate --gruppe G1 G2 G3 --kosten-ok",
        bericht_cmd,
    ]
    aus = Path(args.aus)
    aus.parent.mkdir(parents=True, exist_ok=True)
    aus.write_text(baue_bericht(zeilen, vor, kommandos, gruende=gruende, b0=b0), encoding="utf-8")
    print(f"Bericht: {aus}")
    return 0


def baue_argumente(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m scripts.ab_pipeline_vs_tools")
    unter = p.add_subparsers(dest="befehl", required=True)
    b = unter.add_parser("bericht", help="Markdown-Bericht aus den Rohzeilen (kein Modellaufruf)")
    b.add_argument("--roh", nargs="+", required=True)
    b.add_argument("--aus", default=str(BERICHT_AUS))
    for achse in ("a", "a2", "b", "c"):
        b.add_argument(f"--achse-{achse}-grund", help=f"Grund, falls Achse {achse.upper()} fehlt")
    b.add_argument("--vorbedingung", action="append", default=[], metavar="SCHLUESSEL=WERT")
    b.add_argument("--gold", default="korpus/zitatauswahl_gold.jsonl")
    b.add_argument("--b0", default="docs/messung/zitatauswahl/B0.jsonl")
    a = unter.add_parser("erkenner", help="Achse A: Korpus, json gegen tools")
    a.add_argument("--sprache", choices=("de", "en"), default="de")
    a.add_argument("--modus", choices=("json", "tools", "beide"), default="beide")
    a.add_argument("--nur", nargs="*")
    a.add_argument("--szenen", action="store_true",
                   help="Achse A2: synthetischer Szenenstand je Fall, Zeilen mit achse=A2")
    a.add_argument("--faelle", help="eigene Fallliste (Korpusformat) statt korpus/erkenner.jsonl")
    a.add_argument("--db")
    a.add_argument("--aus")
    return p.parse_args(argv)


def main(argv=None, *, profil_setzen: bool = False) -> int:
    args = baue_argumente(argv)
    if args.befehl == "bericht":
        return _bericht(args)
    if args.befehl == "erkenner":
        sichere_sprache(args.sprache, profil_setzen=profil_setzen)
        return _erkenner(args)
    return 2


if __name__ == "__main__":
    sys.exit(main(profil_setzen=True))
