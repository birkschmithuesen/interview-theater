"""Messung 2, Achse C (Karte t_9b2b33cb): Zitatsuche, Pipeline gegen Agent.

Dieselben Gold-Ziele (``korpus/zitatauswahl_gold.jsonl``, Szene/Figur) auf
drei Wegen, gezaehlt mit der unveraenderten Recall@10-Definition aus
``scripts.zitatauswahl`` (je Ziel eine Rangliste von ``verdichtung_thema_id``;
Treffer, wenn ``thema_ids`` die Top-10 schneidet; nur ``positiv`` und
``im_pool``):

- ``pipeline_opus``: die heutige Schaerfung (``schaerfung._mappe_ziel``) ueber
  den Claude-Proxy (Abo, 0 CHF -- faellt der Proxy aus, springt
  ``modellwahl`` auf Kimi und es kostet doch),
- ``pipeline_kimi``: dieselbe Schaerfung auf Kimi (Kontrollzeile, kostet CHF),
- ``agent_kimi``: ein Suchagent (Schema-Schleife, hoechstens ``MAX_RUNDEN``)
  ueber die lokalen Transkripte (kostet CHF).

**Kostet Geld und laeuft nie automatisch.** Ohne ``--kosten-ok`` bricht die
CLI vor jedem Modell- oder DB-Zugriff ab. Der Agent geht nie ueber
``szene_claude`` (Datenschutz, Spec § 4: Transkripte nicht an Dritte).
Rohzeilen tragen nur Kennungen und Zahlen, nie Zitattext; sie gehen nach
``korpus/berichte/ab/C-*.jsonl`` (gitignored).

  uv run --extra dev python -m scripts.zitatauswahl kopie
  uv run --extra dev python -m scripts.ab_zitate --ohne-modell          # 0 CHF
  uv run --extra dev python -m scripts.ab_zitate --gruppe G1 G2 G3 --kosten-ok
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
import time
from pathlib import Path

from interview_theater import kosten, llm, repo, schaerfung, zitat
from scripts import pruefe_prompts as pp
from scripts import zitatauswahl as za

ROH_VERZ = Path("korpus/berichte/ab")
MAX_RUNDEN = 6
TOP_K = za.K
SUCH_TREFFER = 8
FENSTER_ZEICHEN = 400
FEHLER_RUECKFALL = "fallback_kimi"
VARIANTEN = ("pipeline_opus", "pipeline_kimi", "agent_kimi")

AGENT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["aktion", "anfrage", "stellen"],
    "properties": {
        "aktion": {"type": "string", "enum": ["suche", "fertig"]},
        "anfrage": {"type": "string"},
        "stellen": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["aufnahme_id", "zitat"],
            "properties": {"aufnahme_id": {"type": "integer"}, "zitat": {"type": "string"}}}},
    },
}

SYSTEM = (
    "Du suchst in Interview-Transkripten woertliche Stellen, die zu EINEM Ziel "
    "(Szene oder Figur) passen -- nach Ausdruckskraft, nicht nur nach Thema. "
    "Je Runde: aktion='suche' mit einer Suchanfrage (Stichwoerter), oder "
    "aktion='fertig' mit hoechstens 10 Stellen, wortgleich aus den gezeigten "
    "Treffern zitiert, beste zuerst."
)


# ---------------------------------------------------------------------------
# Suche und Zuordnung
# ---------------------------------------------------------------------------


def _texte(conn, chat_id: int) -> dict[int, str]:
    """aufnahme_id -> ganzes Transkript (Interview = Teile zusammengefuegt),
    ueber denselben Leser wie der Gold-Korpus (``zitatauswahl._transkript``)."""
    return {z["id"]: za._transkript(conn, z["id"]) for z in repo.transkripte(conn, chat_id)}


def suche(conn, chat_id: int, anfrage: str, *, texte: dict[int, str] | None = None) -> list[dict]:
    """Lokale Volltextsuche: Fenster um das erste Vorkommen eines Anfragewortes,
    sortiert nach Zahl der getroffenen Woerter, hoechstens ``SUCH_TREFFER``."""
    woerter = {w for w in re.findall(r"\w+", zitat.normalisiere(anfrage).lower()) if len(w) >= 3}
    if not woerter:
        return []
    treffer = []
    for aufnahme_id, text in (texte if texte is not None else _texte(conn, chat_id)).items():
        klein = text.lower()
        stellen = [klein.find(w) for w in woerter]
        stellen = [s for s in stellen if s >= 0]
        if not stellen:
            continue
        start = max(0, min(stellen) - FENSTER_ZEICHEN // 2)
        treffer.append((len(stellen), {"aufnahme_id": aufnahme_id,
                                       "text": text[start:start + FENSTER_ZEICHEN]}))
    treffer.sort(key=lambda p: -p[0])
    return [t for _, t in treffer[:SUCH_TREFFER]]


def thema_fuer(themen, aufnahme_id: int, text: str) -> int | None:
    """Die Verdichtungsthema-Kennung einer zitierten Stelle: dasselbe Verfahren
    wie ``zitatauswahl._positive_stelle`` (Thema derselben Aufnahme, dessen
    Belegzitat die Stelle zu >= ``LOSE_SCHWELLE`` deckt), Pool-Themen vor
    entfernten/ungeprueften, dann hoechste Deckung."""
    beste = None
    for t in themen:
        if t["aufnahme_id"] != aufnahme_id or not t["beleg_zitat"]:
            continue
        deckung = max(za.anteil([text], t["beleg_zitat"]), za.anteil([t["beleg_zitat"]], text))
        if deckung >= za.LOSE_SCHWELLE:
            wertung = (za._im_pool(t), deckung)
            if beste is None or wertung > beste[0]:
                beste = (wertung, t["id"])
    return beste[1] if beste else None


# ---------------------------------------------------------------------------
# Die drei Wege
# ---------------------------------------------------------------------------


def pipeline_top10(klm, conn, e, chat_id: int, ziel: dict, *, ueber_claude: bool) -> list[dict]:
    """Die heutige Schaerfung fuer EIN Ziel. ``ueber_claude=False`` ist die
    Kontrollzeile auf Kimi; dort gilt auch fuer die Zuordnung das
    Gespraechsmodell (``llm_modell``) statt des Erkennermodells (gemma), damit
    Pipeline und Agent dasselbe Modell haben."""
    e = (dataclasses.replace(e, szene_anbieter="claude") if ueber_claude else
         dataclasses.replace(e, szene_anbieter="infomaniak", erkenner_modell=e.llm_modell))
    eintraege = schaerfung._eintraege(conn, chat_id)
    nach_nummer = {x["nummer"]: x for x in eintraege}
    zuordnungen = schaerfung._mappe_ziel(klm, conn, e, chat_id, ziel, eintraege, nach_nummer)
    text = {x["thema_id"]: x for x in eintraege}
    geordnet = sorted(enumerate(zuordnungen), key=lambda p: (-(p[1].get("staerke") or 0), p[0]))
    aus, gesehen = [], set()
    for _, z in geordnet:
        tid = z["verdichtung_thema_id"]
        if tid in gesehen:
            continue
        gesehen.add(tid)
        aus.append({"text": text[tid]["zitat"], "aufnahme_id": text[tid]["aufnahme_id"],
                    "verdichtung_thema_id": tid, "staerke": z["staerke"]})
    return aus[:TOP_K]


def agent_top10(klm, conn, e, chat_id: int, ziel: dict) -> tuple[list[dict], dict]:
    """Schema-Schleife auf Kimi (``e.llm_modell``). Jede Stelle wird mit
    ``zitat.pruefe`` gegen das Transkript ihrer Aufnahme geprueft; ungepruefte
    fallen weg. Der Starttext traegt den Erfundenes-Block UND denselben
    Hintergrund wie die Pipeline (``schaerfung._hintergrund_zeilen``:
    Diskussion, Kernthema, Festlegungen, Verworfenes, Mitgehoertes) -- fair
    verglichen. Nicht dabei ist das Material mit Themen: das ist der
    Unterschied Pipeline/Agent, der Agent muss suchen. Zweite Rueckgabe: ``{"runden", "abbruch", "verworfen_zitat"}``."""
    texte = _texte(conn, chat_id)
    themen = repo.themen_mit_aufnahme(conn, chat_id)
    kopf = "\n".join(schaerfung._erfundenes_zeilen(conn, chat_id)
                     + schaerfung._hintergrund_zeilen(conn, chat_id))
    verlauf = [(kopf + "\n\n" if kopf else "") + f"Ziel: {ziel.get('beschreibung_text') or ziel}"]
    info = {"runden": 0, "abbruch": None, "verworfen_zitat": 0}
    while True:
        if info["runden"] >= MAX_RUNDEN:
            info["abbruch"] = "runden"
            return [], info
        antwort = klm.schema(chat_id, SYSTEM, "\n\n".join(verlauf), AGENT_SCHEMA,
                             "ab_zitatsuche", modell=e.llm_modell)
        info["runden"] += 1
        if antwort.get("aktion") == "suche":
            anfrage = antwort.get("anfrage", "")
            treffer = suche(conn, chat_id, anfrage, texte=texte)
            verlauf.append(f"Suche: {anfrage}\n" + (
                "\n".join(f"[aufnahme {t['aufnahme_id']}] {t['text']}" for t in treffer)
                or "keine Treffer"))
            continue
        stellen = []
        for s in antwort.get("stellen", [])[:TOP_K]:
            try:
                aufnahme_id = int(s.get("aufnahme_id") or 0)
            except (TypeError, ValueError):
                aufnahme_id = 0
            quelle = texte.get(aufnahme_id, "")
            if quelle and zitat.pruefe(s.get("zitat", ""), quelle):
                stellen.append({"text": s["zitat"], "aufnahme_id": aufnahme_id,
                                "verdichtung_thema_id": thema_fuer(themen, aufnahme_id, s["zitat"]),
                                "staerke": TOP_K - len(stellen)})
            else:
                info["verworfen_zitat"] += 1
        return stellen, info


# ---------------------------------------------------------------------------
# Recall (Definition aus scripts.zitatauswahl)
# ---------------------------------------------------------------------------


def rangliste_von(kandidaten: list[dict]) -> list[int]:
    """Wie ``zitatauswahl.rangliste``; Kandidaten ohne Thema-Kennung koennen
    keinen Gold-Treffer erzeugen und fehlen deshalb."""
    return za.rangliste([k for k in kandidaten if k.get("verdichtung_thema_id") is not None])


def recall_at_10(rangliste: list[int], gold_ziel: list[dict]) -> float | None:
    """Anteil der positiven Pool-Stellen dieses Ziels, deren ``thema_ids`` die
    Top-10 schneiden (``zitatauswahl.recall_at_k``). ``None`` ohne solche Stelle."""
    if not gold_ziel:
        return None
    r = za.recall_at_k({za.ziel_schluessel(gold_ziel[0]): rangliste}, gold_ziel, TOP_K)["gesamt"]
    return r["treffer"] / r["n"] if r["n"] else None


def laufe_ziel(klm, conn, e, golds, variante: str) -> dict:
    """Ein Ziel, eine Variante -> eine Rohzeile (nur Kennungen und Zahlen)."""
    golds = [golds] if isinstance(golds, dict) else list(golds)
    g0 = golds[0]
    chat_id = g0["chat_id"]
    zeile = {"achse": "C", "gruppe": g0["gruppe"], "ziel": za.ziel_schluessel(g0),
             "variante": variante, "recall_at_10": None, "rangliste": [], "kandidaten": [],
             "runden": 1, "abbruch": None, "verworfen_zitat": 0, "eingabe_token": 0,
             "ausgabe_token": 0, "dauer_ms": 0, "kosten_chf": 0.0, "fehler": None}
    vorher = pp._hoechste_aufruf_id(conn)
    start = time.monotonic()
    try:
        ziel = next((z for z in schaerfung._ziele(conn, chat_id)
                     if z["art"] == g0["ziel"]["art"] and z["id"] == g0["ziel"]["id"]), None)
        if ziel is None:
            raise LookupError(f"Ziel {zeile['ziel']} nicht in der Datenbank")
        if variante == "agent_kimi":
            kandidaten, info = agent_top10(klm, conn, e, chat_id, ziel)
            zeile.update(runden=info["runden"], abbruch=info["abbruch"],
                         verworfen_zitat=info["verworfen_zitat"])
        else:
            kandidaten = pipeline_top10(klm, conn, e, chat_id, ziel,
                                        ueber_claude=variante == "pipeline_opus")
        zeile["rangliste"] = rangliste_von(kandidaten)[:TOP_K]
        zeile["kandidaten"] = [{"aufnahme_id": k["aufnahme_id"],
                                "verdichtung_thema_id": k["verdichtung_thema_id"],
                                "staerke": k["staerke"]} for k in kandidaten]
        zeile["recall_at_10"] = recall_at_10(zeile["rangliste"], golds)
    except Exception as fehler:  # noqa: BLE001 -- ein Ziel bricht den Lauf nie ab
        zeile["fehler"] = type(fehler).__name__  # nie der Text: kann Modellausgabe/Zitate tragen
    zeile["dauer_ms"] = int((time.monotonic() - start) * 1000)
    zaehlung = repo.aufruf_summe_nach(conn, vorher)
    zeile.update(eingabe_token=zaehlung["eingabe_token"], ausgabe_token=zaehlung["ausgabe_token"])
    if variante != "pipeline_opus":  # Opus laeuft ueber das Abo (CLAUDE_CHF_JE_AUFRUF)
        zeile["kosten_chf"] = kosten.kosten_chf(
            e.llm_modell, zaehlung["eingabe_token"], zaehlung["ausgabe_token"])
    else:
        # modellwahl faellt bei ClaudeFehler/LLMFehler still auf Kimi zurueck
        # (Infomaniak, kostet): jede Nicht-Abo-Zeile seit ``vorher`` ist so ein
        # Rueckfall. Dann zaehlt die Zeile nicht als Opus und die echten
        # Kosten werden aus den aufruf-Zeilen gebucht.
        fremd = repo.aufruf_fremd_nach(conn, vorher, kosten.ABO_MODUS)
        if fremd["aufrufe"]:
            zeile.update(fehler=zeile["fehler"] or FEHLER_RUECKFALL, recall_at_10=None,
                         kosten_chf=fremd["kosten_chf"])
    return zeile


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def ist_deckel_fehler(zeile: dict) -> bool:
    """Brach das Ziel am Tagesdeckel ab? (Die Zeile traegt nur den Typnamen.)"""
    return zeile.get("fehler") == kosten.KostendeckelErreicht.__name__


def _verbinde(pfad: str):
    return za._verbinde(pfad)


def zeige_b0(gold: list[dict], pfad: str | Path) -> dict:
    """Recall@10 der B0-Baseline (0 CHF, nur gelesen)."""
    ranglisten: dict = {}
    for zeile in (json.loads(z) for z in Path(pfad).read_text(encoding="utf-8").splitlines() if z.strip()):
        ranglisten.update(zeile["ranglisten"])
    r = za.recall_at_k(ranglisten, gold)
    for gr, w in r.items():
        print(f"{gr}: Recall@{TOP_K} {w['treffer']}/{w['n']}")
    return r


def baue_argumente(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m scripts.ab_zitate")
    p.add_argument("--gold", default=str(za.GOLD))
    p.add_argument("--db", default=str(za.KOPIE),
                   help="Kopie von betrieb/padua.db (scripts.zitatauswahl kopie)")
    p.add_argument("--gruppe", nargs="*", default=sorted(za.GRUPPEN))
    p.add_argument("--varianten", nargs="*", choices=VARIANTEN, default=list(VARIANTEN))
    p.add_argument("--aus")
    p.add_argument("--b0", default=str(za.ROH / "B0.jsonl"))
    p.add_argument("--kosten-ok", action="store_true",
                   help="Freigabe: Kimi (Infomaniak) kostet CHF. Ohne dieses Flag kein Lauf.")
    p.add_argument("--ohne-modell", action="store_true",
                   help="nur Gold pruefen und B0-Recall zeigen (0 CHF)")
    return p.parse_args(argv)


def _ziele_der_messung(gold: list[dict], gruppen) -> dict[str, list[dict]]:
    """Ziele mit mindestens einer positiven Pool-Stelle, je Ziel alle positiven Zeilen."""
    aus: dict[str, list[dict]] = {}
    for g in za._positiv(gold):
        if g["gruppe"] in gruppen and g["im_pool"]:
            aus.setdefault(za.ziel_schluessel(g), []).append(g)
    return aus


def main(argv=None) -> int:
    a = baue_argumente(argv)
    if not a.ohne_modell and not a.kosten_ok:
        raise SystemExit(
            "Abbruch: der Lauf ruft Kimi (Infomaniak) auf und kostet CHF. Nur mit "
            "ausdruecklicher Freigabe: --kosten-ok. Ohne Modell (0 CHF): --ohne-modell.")
    conn = _verbinde(a.db)
    gold = [g for g in za.lade_gold(a.gold) if g["gruppe"] in a.gruppe]
    if not gold:
        raise SystemExit(f"Abbruch: kein Gold-Eintrag fuer --gruppe {' '.join(a.gruppe)}.")
    fehler = za.pruefe_gold(conn, gold)
    if fehler:
        print("\n".join(fehler), file=sys.stderr)
        return 1
    if Path(a.b0).exists():
        print("B0 (Baseline, historisch):")
        zeige_b0(gold, a.b0)
    if a.ohne_modell:
        return 0

    from interview_theater import einstellungen
    import httpx

    e = einstellungen.laden()
    klm = llm.LLM(e, httpx.Client(timeout=180.0), conn)
    ziele = _ziele_der_messung(gold, set(a.gruppe))
    ROH_VERZ.mkdir(parents=True, exist_ok=True)
    aus = Path(a.aus or ROH_VERZ / f"C-{time.strftime('%Y%m%d-%H%M')}.jsonl")
    ranglisten: dict[str, dict] = {v: {} for v in a.varianten}
    with aus.open("a", encoding="utf-8") as datei:
        for nr, (schluessel, golds) in enumerate(sorted(ziele.items()), start=1):
            for variante in a.varianten:
                zeile = laufe_ziel(klm, conn, e, golds, variante)
                datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
                datei.flush()
                if zeile["fehler"] is None:
                    ranglisten[variante][schluessel] = zeile["rangliste"]
                print(f"[{nr}/{len(ziele)}] {variante} {schluessel}: recall={zeile['recall_at_10']}"
                      + (f" FEHLER {zeile['fehler']}" if zeile["fehler"] else ""), flush=True)
                if ist_deckel_fehler(zeile):
                    print("Tagesdeckel erreicht -- Abbruch.", file=sys.stderr)
                    return 1
    for variante in a.varianten:
        print(f"{variante}:")
        for gr, w in za.recall_at_k(ranglisten[variante], gold).items():
            print(f"  {gr}: Recall@{TOP_K} {w['treffer']}/{w['n']} (ohne Lauf: {w['fehlt']})")
    print(f"Rohdaten: {aus}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("IT_WORKSHOP", "padua-2026")
    sys.exit(main())
