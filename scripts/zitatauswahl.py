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


def rangliste(zuordnungen: list[dict]) -> list[int]:
    """Wie ``schaerfung.offene_stellen``/``web_daten.schaerfungsliste``:
    Staerke absteigend, bei Gleichstand die Listenposition (= Reihenfolge
    des Modells bzw. ``id``); jedes Thema nur einmal (Spec E1)."""
    geordnet = sorted(enumerate(zuordnungen), key=lambda p: (-(p[1].get("staerke") or 0), p[0]))
    aus: list[int] = []
    for _, z in geordnet:
        if z["verdichtung_thema_id"] not in aus:
            aus.append(z["verdichtung_thema_id"])
    return aus


def _positive(gold: list[dict]) -> list[dict]:
    return [g for g in gold if g["polaritaet"] == "positiv"]


def ranglisten_historisch(conn, gold: list[dict]) -> dict[str, list[int]]:
    """B0 (Spec E5): je Gold-Ziel die Zeilen der LETZTEN Runde, in der dieses
    Ziel Zeilen hat -- entfernte eingeschlossen (sie waren in ihrer Runde
    sichtbar)."""
    aus: dict[str, list[int]] = {}
    historie: dict[int, list] = {}
    for g in _positive(gold):
        schluessel = ziel_schluessel(g)
        if schluessel in aus:
            continue
        if g["chat_id"] not in historie:
            historie[g["chat_id"]] = repo.schaerfungen_historie(conn, g["chat_id"])
        spalte = "szene_id" if g["ziel"]["art"] == "szene" else "figur_id"
        zeilen = [dict(z) for z in historie[g["chat_id"]] if z[spalte] == g["ziel"]["id"]]
        if not zeilen:
            aus[schluessel] = []
            continue
        letzte = max(z["runde"] for z in zeilen)
        aus[schluessel] = rangliste([z for z in zeilen if z["runde"] == letzte])
    return aus


def recall_at_k(ranglisten: dict, gold: list[dict], k: int = K) -> dict[str, dict]:
    """Spec E1: je Gruppe und gesamt, nur positive Stellen im Pool. Fehlt die
    Rangliste eines Ziels (``None``/nicht da), zaehlt die Stelle unter ``fehlt``."""
    aus = {gr: {"treffer": 0, "n": 0, "fehlt": 0}
           for gr in sorted({g["gruppe"] for g in gold}) + ["gesamt"]}
    for g in _positive(gold):
        if not g["im_pool"]:
            continue
        liste = ranglisten.get(ziel_schluessel(g))
        for gr in (g["gruppe"], "gesamt"):
            if liste is None:
                aus[gr]["fehlt"] += 1
                continue
            aus[gr]["n"] += 1
            if set(g["thema_ids"]) & set(liste[:k]):
                aus[gr]["treffer"] += 1
    return aus


def negativ_at_k(ranglisten: dict, gold: list[dict], k: int = K) -> dict[str, int]:
    """Verworfene Paare (Spec E3), deren Thema an IHREM Ziel in den Top-k
    steht -- nur an Zielen mit Rangliste (= Gold-Zielen)."""
    aus: dict[str, int] = {"gesamt": 0}
    for g in gold:
        if g["polaritaet"] != "negativ":
            continue
        liste = ranglisten.get(ziel_schluessel(g))
        if not liste:
            continue
        if set(g["thema_ids"]) & set(liste[:k]):
            aus[g["gruppe"]] = aus.get(g["gruppe"], 0) + 1
            aus["gesamt"] += 1
    return aus


def pool_recall(gold: list[dict]) -> dict[str, tuple[int, int]]:
    aus: dict[str, list[int]] = {}
    for g in _positive(gold):
        for gr in (g["gruppe"], "gesamt"):
            aus.setdefault(gr, [0, 0])
            aus[gr][0] += int(g["im_pool"])
            aus[gr][1] += 1
    return {gr: (a, n) for gr, (a, n) in aus.items()}


def haenge_an(zeile: dict, pfad) -> None:
    Path(pfad).parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "a", encoding="utf-8") as f:
        f.write(json.dumps(zeile, ensure_ascii=False, sort_keys=True) + "\n")


def lade_roh(verz=ROH) -> list[dict]:
    """Alle Rohzeilen; Zeilen desselben (variante, lauf, gruppe) -- etwa ein
    Neu-Lauf in mehreren Aufrufen je Ziel -- werden zusammengefuehrt."""
    zusammen: dict[tuple, dict] = {}
    for pfad in sorted(Path(verz).glob("*.jsonl")):
        with open(pfad, encoding="utf-8") as f:
            for roh in f:
                if not roh.strip():
                    continue
                z = json.loads(roh)
                schluessel = (z["variante"], z["lauf"], z["gruppe"])
                ziel = zusammen.setdefault(schluessel, {
                    "variante": z["variante"], "lauf": z["lauf"], "gruppe": z["gruppe"],
                    "ranglisten": {}, "maskiert": {}, "fehler": {}, "dauer_ms": {}})
                for feld in ("ranglisten", "maskiert", "fehler", "dauer_ms"):
                    ziel[feld].update(z.get(feld) or {})
                # Eine spaetere erfolgreiche Wiederholung (``--nur``) hebt den
                # Fehler desselben Ziels in diesem Lauf auf.
                for s, r in (z.get("ranglisten") or {}).items():
                    if r is not None and s not in (z.get("fehler") or {}):
                        ziel["fehler"].pop(s, None)
    return list(zusammen.values())


def laeufe(zeilen: list[dict], gold: list[dict], variante: str, k: int = K) -> dict[int, dict]:
    """Nur vollstaendige Laeufe: jedes Gold-Ziel hat eine Rangliste, kein
    Ziel hat einen Fehler (Spec § 6: ein Lauf mit Fehler zaehlt nicht fuer E7)."""
    noetig = {ziel_schluessel(g) for g in _positive(gold) if g["im_pool"]}
    je_lauf: dict[int, dict] = {}
    for z in zeilen:
        if z["variante"] != variante:
            continue
        l = je_lauf.setdefault(z["lauf"], {"ranglisten": {}, "fehler": {}, "maskiert": 0})
        l["ranglisten"].update(z["ranglisten"])
        l["fehler"].update(z.get("fehler") or {})
        l["maskiert"] += sum((z.get("maskiert") or {}).values())
    aus = {}
    for lauf, l in sorted(je_lauf.items()):
        if l["fehler"] or any(l["ranglisten"].get(s) is None for s in noetig):
            continue
        aus[lauf] = {"recall": recall_at_k(l["ranglisten"], gold, k),
                     "ranglisten": l["ranglisten"], "maskiert": l["maskiert"]}
    return aus


#: Spec E7: so viele Gold-Stellen muss eine Variante im Mittel mehr treffen.
MINDEST_GEWINN = 2


def entscheide(basis: dict[int, dict], variante: dict[int, dict]) -> tuple[bool, list[str]]:
    """Spec E7 -- alle drei Bedingungen, sonst kein Fix."""
    if not basis or not variante:
        return False, ["zu wenige vollstaendige Laeufe"]

    def werte(l, gr):
        return [x["recall"][gr]["treffer"] for x in l.values()]

    def mittel(l, gr):
        w = werte(l, gr)
        return sum(w) / len(w)

    gruende = []
    gewinn = mittel(variante, "gesamt") - mittel(basis, "gesamt")
    if gewinn < MINDEST_GEWINN:
        gruende.append(f"Gewinn {gewinn:+.2f} Stellen < {MINDEST_GEWINN}")
    if min(werte(variante, "gesamt")) < max(werte(basis, "gesamt")):
        gruende.append("schlechtester Variantenlauf unter bestem Basislauf")
    gruppen = sorted(g for g in next(iter(basis.values()))["recall"] if g != "gesamt")
    for gr in gruppen:
        if mittel(variante, gr) < mittel(basis, gr):
            gruende.append(f"{gr} sinkt ({mittel(basis, gr):.2f} -> {mittel(variante, gr):.2f})")
    return not gruende, gruende


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
    for name in ("gold", "pruefe", "historisch"):
        s = sub.add_parser(name)
        s.add_argument("--db", default=str(KOPIE))
        s.add_argument("--gold", default=str(GOLD))
        if name == "gold":
            s.add_argument("--quelle", default=str(QUELLE))
        if name == "historisch":
            s.add_argument("--aus", default=str(ROH / "B0.jsonl"))
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
    if a.befehl == "historisch":
        gold = lade_gold(a.gold)
        fehler = pruefe_gold(conn, gold)
        if fehler:
            print("\n".join(fehler), file=sys.stderr)
            return 1
        ranglisten = ranglisten_historisch(conn, gold)
        if Path(a.aus).exists():
            Path(a.aus).unlink()  # B0 ist deterministisch: neu schreiben statt anhaengen
        for gruppe in sorted({g["gruppe"] for g in gold}):
            eigene = {s: r for s, r in ranglisten.items() if s.startswith(gruppe + ":")}
            haenge_an({"variante": "B0", "lauf": 1, "gruppe": gruppe, "ranglisten": eigene,
                       "maskiert": {}, "fehler": {}, "dauer_ms": {}}, a.aus)
        r = recall_at_k(ranglisten, gold)
        for gr, w in r.items():
            print(f"{gr}: Recall@{K} {w['treffer']}/{w['n']}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
