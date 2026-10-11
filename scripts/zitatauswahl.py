"""Messung der Zitatauswahl (Karte t_2349e9a8, Umsetzung t_2f905d2c).

Misst, ob die Schaerfung (``schaerfung.py``) die Stellen nach vorn bringt,
die in Padua tatsaechlich im Stueck gelandet sind: Recall@10 JE ZIEL (Spec E1),
gegen den Gold-Korpus ``korpus/zitatauswahl_gold.jsonl``.

Kommandos (Reihenfolge; Bericht: docs/messung/2026-10-zitatauswahl.md):

    uv run --extra dev python -m scripts.zitatauswahl kopie
    uv run --extra dev python -m scripts.zitatauswahl gold --db var/zitatauswahl/padua-kopie.db
    uv run --extra dev python -m scripts.zitatauswahl pruefe --db var/zitatauswahl/padua-kopie.db
    uv run --extra dev python -m scripts.zitatauswahl historisch --db var/zitatauswahl/padua-kopie.db
    uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante B1 --lauf 1 --gruppe G1
    uv run --extra dev python -m scripts.zitatauswahl bericht

Quelle der Live-DB nur read-only (``stueckmodell_kopie.kopiere``, VACUUM INTO).
Neu-Laeufe nur ueber den Claude-Proxy (0 CHF), nie ueber Kimi/gemma.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

from interview_theater import repo, zitat

GRUPPEN = {"G1": 7000000000000, "G2": 7000000000001, "G3": 7000000000002}
QUELLE = Path("korpus/zitatauswahl_quelle.toml")
GOLD = Path("korpus/zitatauswahl_gold.jsonl")
ROH = Path("docs/messung/zitatauswahl")
BERICHT = Path("docs/messung/2026-10-zitatauswahl.md")
LIVE_DB = Path("betrieb/padua.db")
KOPIE = Path("var/zitatauswahl/padua-kopie.db")
K = 10
#: Anteil der 4-Wort-Fenster einer Plakatstelle, der in einem Belegzitat
#: stehen muss, damit das Thema als dieselbe Stelle gilt (Sondierung
#: 11.10.2026: echte Paare 0,59-1,0, sonst 0).
LOSE_SCHWELLE = 0.5


def _woerter(text: str) -> list[str]:
    return re.findall(r"\w+", (text or "").lower())


def fragmente(wortlaut: str) -> list[str]:
    """Die Teile einer Plakatstelle zwischen den Auslassungen (``…``)."""
    teile = (wortlaut or "").strip().strip("«»\"").split("…")
    return [t.strip().strip("«»\" .,") for t in teile if t.strip().strip("«»\" .,")]


def verankere(fragment: str, transkript: str) -> str | None:
    """Die Stelle im Transkript mit derselben Wortfolge wie das Fragment
    (klein, ohne Satzzeichen) -- im ORIGINALWORTLAUT des Transkripts, damit
    ``zitat.pruefe`` sie danach exakt findet. ``None``, wenn es sie nicht gibt."""
    gesucht = _woerter(fragment)
    if not gesucht or not transkript:
        return None
    treffer = list(re.finditer(r"\w+", transkript))
    worte = [m.group(0).lower() for m in treffer]
    n = len(gesucht)
    for i in range(len(worte) - n + 1):
        if worte[i:i + n] == gesucht:
            return transkript[treffer[i].start():treffer[i + n - 1].end()]
    return None


def anteil(fragmente_: list[str], text: str) -> float:
    """Anteil der 4-Wort-Fenster der Fragmente, die in ``text`` vorkommen
    (kuerzere Fragmente: das ganze Fragment als ein Fenster)."""
    ziel = " " + " ".join(_woerter(text)) + " "
    fenster = []
    for f in fragmente_:
        w = _woerter(f)
        fenster += [" " + " ".join(w[i:i + 4]) + " " for i in range(max(1, len(w) - 3))]
    return sum(f in ziel for f in fenster) / len(fenster) if fenster else 0.0


def _transkript(conn, aufnahme_id: int) -> str:
    zeile = repo.hole_aufnahme(conn, aufnahme_id)
    if zeile is None:
        return ""
    return (zeile["transkript"] or "") or repo.zusammengefuegtes_transkript(conn, aufnahme_id)


def _im_pool(thema) -> bool:
    return (thema is not None and thema["zitat_geprueft"] == 1
            and thema["verdichtung_entfernt_am"] is None and bool(thema["beleg_zitat"]))


def lade_quelle(pfad=QUELLE) -> list[dict]:
    with open(pfad, "rb") as f:
        daten = tomllib.load(f)
    commit = daten.get("quelle_commit", "")
    return [dict(k, quelle_commit=commit) for k in daten["karte"]]


def _positive_stelle(conn, karte: dict, chat_id: int) -> dict:
    fr = fragmente(karte["wortlaut"])
    aufnahme_id, anker = None, []
    for aufnahme in repo.transkripte(conn, chat_id):
        text = _transkript(conn, aufnahme["id"])
        kandidat = [verankere(f, text) for f in fr]
        if fr and all(kandidat):
            aufnahme_id, anker = aufnahme["id"], kandidat
            break
    if aufnahme_id is None:
        raise ValueError(f"{karte['id']}: Wortlaut steht in keinem Transkript der Gruppe")
    themen = [t for t in repo.themen_mit_aufnahme(conn, chat_id)
              if t["aufnahme_id"] == aufnahme_id
              and anteil(anker, t["beleg_zitat"] or "") >= LOSE_SCHWELLE]
    im_pool = [t["id"] for t in themen if _im_pool(t)]
    szene = next((s for s in repo.hole_szenen(conn, chat_id) if s["nummer"] == karte["szene"]), None)
    if szene is None:
        raise ValueError(f"{karte['id']}: Szene {karte['szene']} fehlt")
    return {
        "id": karte["id"], "gruppe": karte["gruppe"], "chat_id": chat_id,
        "polaritaet": "positiv",
        "ziel": {"art": "szene", "nummer": szene["nummer"], "id": szene["id"],
                 "titel": szene["titel"] or ""},
        "frage": karte["frage"], "wortlaut": karte["wortlaut"], "fragmente": anker,
        "aufnahme_id": aufnahme_id,
        "verdichtung_thema_id": im_pool[0] if im_pool else None,
        "thema_ids": [t["id"] for t in themen], "im_pool": bool(im_pool),
        "quelle": {"repo": "hermes-entities", "commit": karte.get("quelle_commit", ""),
                   "datei": karte["datei"], "karte": karte["karte"], "label": karte["label"]},
    }


def _negative(conn, gruppe: str, chat_id: int, positiv_themen: set[int]) -> list[dict]:
    """Spec F7.3: ein Paar (Thema, Ziel) mit mindestens einem ``nein``, ohne
    ``ja`` an diesem Ziel, und das Thema ist nirgends positiv. Nur Kennungen."""
    themen = {t["id"]: t for t in repo.themen_mit_aufnahme(conn, chat_id)}
    paare: dict[tuple, dict] = {}
    for z in repo.schaerfungen_historie(conn, chat_id):
        art, zid = ("szene", z["szene_id"]) if z["szene_id"] is not None else ("figur", z["figur_id"])
        p = paare.setdefault((z["verdichtung_thema_id"], art, zid), {"ja": False, "nein": []})
        if z["entscheidung"] == "ja":
            p["ja"] = True
        elif z["entscheidung"] == "nein":
            p["nein"].append(z["id"])
    szenen = {s["id"]: s for s in repo.hole_szenen(conn, chat_id)}
    figuren = {f["id"]: f for f in repo.figuren(conn, chat_id)}
    aus = []
    for (thema_id, art, zid), p in paare.items():
        if not p["nein"] or p["ja"] or thema_id in positiv_themen:
            continue
        if art == "szene" and zid in szenen:
            ziel = {"art": "szene", "nummer": szenen[zid]["nummer"], "id": zid,
                    "titel": szenen[zid]["titel"] or ""}
        elif art == "figur" and zid in figuren:
            ziel = {"art": "figur", "nummer": None, "id": zid, "titel": figuren[zid]["name"]}
        else:
            continue
        thema = themen.get(thema_id)
        aus.append({
            "id": f"{gruppe}-n-{min(p['nein']):04d}", "gruppe": gruppe, "chat_id": chat_id,
            "polaritaet": "negativ", "ziel": ziel,
            "aufnahme_id": thema["aufnahme_id"] if thema is not None else None,
            "verdichtung_thema_id": thema_id, "thema_ids": [thema_id],
            "im_pool": _im_pool(thema), "schaerfung_ids": sorted(p["nein"]),
            "quelle": {"tabelle": "schaerfung", "entscheidung": "nein"},
        })
    return aus


def baue_gold(conn, quelle: list[dict], gruppen: dict[str, int]) -> list[dict]:
    positiv = [_positive_stelle(conn, k, gruppen[k["gruppe"]]) for k in quelle]
    gold = list(positiv)
    for gruppe in sorted({k["gruppe"] for k in quelle}):
        themen = {t for g in positiv if g["gruppe"] == gruppe for t in g["thema_ids"]}
        gold += _negative(conn, gruppe, gruppen[gruppe], themen)
    return sorted(gold, key=lambda g: g["id"])


def pruefe_gold(conn, gold: list[dict]) -> list[str]:
    """Jeder Fehler eine Zeile ``<id>: <grund>``; leer = gueltig (Spec § 6)."""
    fehler = []
    for g in gold:
        chat_id = g["chat_id"]
        themen = {t["id"]: t for t in repo.themen_mit_aufnahme(conn, chat_id)}
        if g["polaritaet"] == "positiv":
            aufnahme = repo.hole_aufnahme(conn, g["aufnahme_id"])
            if aufnahme is None or aufnahme["chat_id"] != chat_id:
                fehler.append(f"{g['id']}: Aufnahme {g['aufnahme_id']} gehoert nicht zur Gruppe")
                continue
            text = _transkript(conn, g["aufnahme_id"])
            for f in g["fragmente"]:
                if not zitat.pruefe(f, text):
                    fehler.append(f"{g['id']}: Fragment nicht im Transkript: {f[:40]!r}")
        for t in g["thema_ids"]:
            if t not in themen:
                fehler.append(f"{g['id']}: Thema {t} gibt es in dieser Gruppe nicht")
        pool = [t for t in g["thema_ids"] if _im_pool(themen.get(t))]
        if bool(pool) != g["im_pool"] or (g["verdichtung_thema_id"] is not None
                                          and g["verdichtung_thema_id"] not in g["thema_ids"]):
            fehler.append(f"{g['id']}: im_pool/verdichtung_thema_id passen nicht zu den Themen")
        if g["ziel"]["art"] == "szene":
            szene = next((s for s in repo.hole_szenen(conn, chat_id) if s["id"] == g["ziel"]["id"]), None)
            if szene is None or szene["nummer"] != g["ziel"]["nummer"]:
                fehler.append(f"{g['id']}: Szene {g['ziel']['nummer']} (id {g['ziel']['id']}) passt nicht")
    return fehler


def lade_gold(pfad=GOLD) -> list[dict]:
    with open(pfad, encoding="utf-8") as f:
        return [json.loads(z) for z in f if z.strip()]


def schreibe_gold(gold: list[dict], pfad=GOLD) -> None:
    Path(pfad).parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as f:
        for g in sorted(gold, key=lambda g: g["id"]):
            f.write(json.dumps(g, ensure_ascii=False, sort_keys=True) + "\n")


def ziel_schluessel(zeile: dict) -> str:
    return f"{zeile['gruppe']}:{zeile['ziel']['art']}:{zeile['ziel']['id']}"


def trifft(kandidat: dict, gold: dict) -> bool:
    """Spec E4, verbindlich auch fuer Messung 2: gleiche Thema-Kennung, oder --
    traegt der Kandidat keine -- alle Fragmente stehen in seinem Text."""
    if kandidat.get("verdichtung_thema_id") is not None:
        return kandidat["verdichtung_thema_id"] in gold["thema_ids"]
    text = kandidat.get("text") or ""
    return bool(gold.get("fragmente")) and all(zitat.pruefe(f, text) for f in gold["fragmente"])


def _verbinde(pfad: str):
    from interview_theater import db

    if Path(pfad).resolve() == LIVE_DB.resolve() or "padua-test" in Path(pfad).name:
        raise SystemExit(f"Messung nur auf einer Kopie, nicht auf {pfad}")
    return db.verbinde(pfad)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.zitatauswahl")
    sub = p.add_subparsers(dest="befehl", required=True)
    k = sub.add_parser("kopie")
    k.add_argument("--quelle", default=str(LIVE_DB))
    k.add_argument("--ziel", default=str(KOPIE))
    for name in ("gold", "pruefe"):
        s = sub.add_parser(name)
        s.add_argument("--db", default=str(KOPIE))
        s.add_argument("--gold", default=str(GOLD))
        if name == "gold":
            s.add_argument("--quelle", default=str(QUELLE))
    a = p.parse_args(argv)

    if a.befehl == "kopie":
        from scripts import stueckmodell_kopie

        if "padua-test" in Path(a.quelle).name:
            raise SystemExit("Messung nur auf betrieb/padua.db")
        stueckmodell_kopie.kopiere(a.quelle, a.ziel)
        print(f"Kopie: {a.ziel}")
        return 0

    conn = _verbinde(a.db)
    if a.befehl == "gold":
        gold = baue_gold(conn, lade_quelle(a.quelle), GRUPPEN)
        fehler = pruefe_gold(conn, gold)
        if fehler:
            print("\n".join(fehler), file=sys.stderr)
            return 1
        schreibe_gold(gold, a.gold)
        pos = [g for g in gold if g["polaritaet"] == "positiv"]
        for gruppe in sorted(GRUPPEN):
            p_ = [g for g in pos if g["gruppe"] == gruppe]
            n_ = [g for g in gold if g["gruppe"] == gruppe and g["polaritaet"] == "negativ"]
            print(f"{gruppe}: positiv {len(p_)} (im Pool {sum(g['im_pool'] for g in p_)}), negativ {len(n_)}")
        return 0
    if a.befehl == "pruefe":
        fehler = pruefe_gold(conn, lade_gold(a.gold))
        if fehler:
            print("\n".join(fehler), file=sys.stderr)
            return 1
        print("Gold-Korpus gueltig")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
