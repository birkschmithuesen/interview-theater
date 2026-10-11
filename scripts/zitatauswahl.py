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
import os
import re
import sys
import time
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


def maskiere(text: str, fragmente_: list[str]) -> tuple[str, int]:
    """Spec E6: jedes Gold-Fragment (ab drei Woertern) im Text durch ``[…]``
    ersetzen, Gross-/Kleinschreibung und Satzzeichen dazwischen egal."""
    anzahl = 0
    for f in sorted(set(fragmente_), key=len, reverse=True):
        worte = _woerter(f)
        if len(worte) < 3:
            continue
        muster = r"(?<!\w)" + r"\W+".join(re.escape(w) for w in worte) + r"(?!\w)"
        text, n = re.subn(muster, "[…]", text, flags=re.IGNORECASE)
        anzahl += n
    return text, anzahl


def nutzertext_maskiert(conn, chat_id: int, eintraege: list[dict], ziel: dict,
                        fragmente_: list[str]) -> tuple[str, int]:
    """Derselbe Nutzertext wie ``schaerfung._baue_nutzertext_ziel`` (ohne
    Fragmente bitgleich, Test), aber Gold-Fragmente im Nicht-Material-Teil
    maskiert -- die Materialliste bleibt unangetastet."""
    from interview_theater import schaerfung

    kopf = schaerfung._erfundenes_zeilen(conn, chat_id)
    hintergrund = schaerfung._hintergrund_zeilen(conn, chat_id)
    if hintergrund:
        kopf.append("")
        kopf.extend(hintergrund)
    kopf.append("")
    kopf.append(schaerfung.T._ZIEL_ZEILE.format(beschreibung=ziel["beschreibung_text"]))
    kopf.append("")
    text_kopf, anzahl = maskiere("\n".join(kopf), fragmente_)
    material = schaerfung._material_zeilen(eintraege, woerter=schaerfung.PROMPT_ZITAT_WOERTER)
    return text_kopf + "\n" + "\n".join(material), anzahl


def einstellungen_messung(db_pfad: str):
    """Einstellungen ohne Umgebung: nur der Claude-Pfad ist echt; Kimi-Felder
    sind Platzhalter, damit ein versehentlicher Kimi-Aufruf scheitert statt
    zu kosten."""
    from interview_theater import einstellungen, szene_claude

    return einstellungen.Einstellungen(
        bot_token="-", bot_name="messung-zitatauswahl", db_pfad=db_pfad,
        audio_verz="var/zitatauswahl/audio", llm_url="-", llm_key="-", llm_modell="-",
        stt_basis="-", stt_produkt="-", erkenner_modell="-",
        szene_anbieter="claude", schaerfung_modell=szene_claude.MODELL_VORGABE,
    )


def neu_lauf(conn, e, klient, gold: list[dict], gruppe: str, system: str, *,
             nur: list[str] | None = None, eintraege: list[dict] | None = None) -> dict:
    """B1/I-a/I-b (Spec E5): je Gold-Ziel der Gruppe EIN Schema-Aufruf ueber
    den Proxy, seriell, ohne Rueckfall. ``eintraege`` erlaubt I-b eine
    veraenderte Materialliste; sonst ``schaerfung._eintraege``."""
    from interview_theater import schaerfung, szene_claude

    positiv = [g for g in _positive(gold) if g["gruppe"] == gruppe]
    if not positiv:
        raise SystemExit(f"keine Gold-Stellen fuer {gruppe}")
    chat_id = positiv[0]["chat_id"]
    if eintraege is None:
        eintraege = schaerfung._eintraege(conn, chat_id)
    nach_nummer = {x["nummer"]: x for x in eintraege}
    alle_fragmente = [f for g in _positive(gold) for f in g["fragmente"]]
    ziele = {(z["art"], z["id"]): z for z in schaerfung._ziele(conn, chat_id)}
    zeile = {"gruppe": gruppe, "ranglisten": {}, "maskiert": {}, "fehler": {}, "dauer_ms": {}}
    for schluessel in sorted({ziel_schluessel(g) for g in positiv}):
        if nur and schluessel not in nur:
            continue
        _, art, zid = schluessel.split(":")
        ziel = ziele.get((art, int(zid)))
        if ziel is None:
            zeile["ranglisten"][schluessel] = None
            zeile["fehler"][schluessel] = "Ziel fehlt in der Kopie"
            continue
        nutzer, anzahl = nutzertext_maskiert(conn, chat_id, eintraege, ziel, alle_fragmente)
        zeile["maskiert"][schluessel] = anzahl
        start = time.monotonic()
        try:
            ergebnis = szene_claude.schema(
                conn, e, klient, chat_id, system, nutzer, schaerfung.ZIEL_SCHEMA,
                f"messung_zitatauswahl_{art}_{zid}", timeout=schaerfung.CLAUDE_TIMEOUT_S,
                wartezeiten=schaerfung.CLAUDE_WARTEZEITEN, modell=e.schaerfung_modell,
            )
            zeile["ranglisten"][schluessel] = rangliste(
                schaerfung.werte_aus(ergebnis, ziel, nach_nummer))
        except Exception as fehler:  # Spec § 6: notieren, nicht ersetzen
            zeile["ranglisten"][schluessel] = None
            zeile["fehler"][schluessel] = f"{type(fehler).__name__}: {fehler}"[:300]
        zeile["dauer_ms"][schluessel] = int((time.monotonic() - start) * 1000)
    return zeile


def eintraege_mit_frage(conn, chat_id: int) -> list[dict]:
    """I-b (Task 8) -- nur nach Birks Freigabe des Datenflusses (Spec E8)."""
    raise SystemExit("I-b ist gesperrt: Datenschutz-Gate (Spec E8) nicht freigegeben")


VARIANTEN = ("B0", "B1", "I-a", "I-b")

FORMAT_DOKU = """\
Datei: `korpus/zitatauswahl_gold.jsonl` -- eine JSON-Zeile je Stelle, UTF-8,
sortiert nach `id`. Leser: `scripts.zitatauswahl.lade_gold(pfad)`.
Treffer-Regel: `scripts.zitatauswahl.trifft(kandidat, gold)`.

| Feld | Bedeutung |
|---|---|
| `id` | `G1-1` (positiv, Gruppe-Karte) bzw. `G1-n-0286` (negativ, kleinste `schaerfung.id`) |
| `gruppe` | `G1` / `G2` / `G3` |
| `chat_id` | 7000000000000 / …001 / …002 |
| `polaritaet` | `positiv` (im Stueck, Plakat) / `negativ` (`nein` an diesem Ziel, nie `ja`, nirgends positiv) |
| `ziel` | `{"art": "szene"|"figur", "nummer", "id", "titel"}` -- `id` = `szene.id`/`figur.id` in padua.db |
| `frage` | Interviewfrage laut Plakat (EN, nur positiv) |
| `wortlaut` | Plakatwortlaut, Auslassungen ` … ` (nur positiv) |
| `fragmente` | Teile zwischen den Auslassungen im Originalwortlaut des Transkripts; jedes besteht `zitat.pruefe` (nur positiv) |
| `aufnahme_id` | Interview (Kopf), in dem die Stelle steht |
| `verdichtung_thema_id` | das Thema im Pool (`repo.gepruefte_themen`), sonst `null` |
| `thema_ids` | alle Themen derselben Stelle (auch aus entfernten Verdichtungen) |
| `im_pool` | ob eines davon im Pool der Schaerfung steht |
| `schaerfung_ids` | nur negativ: die `nein`-Zeilen |
| `quelle` | positiv: entities-Commit, Datei, Karte, Label; negativ: Tabelle |

**Recall@10** (Spec E1) gilt **je Ziel**: eine positive Stelle im Pool ist
getroffen, wenn eines ihrer `thema_ids` unter den ersten 10 verschiedenen
Themen der Rangliste IHRES Ziels steht. Sortiert wird wie im Betrieb:
`(-staerke, runde, Reihenfolge des Modells)`. Gemittelt wird mikro, je Gruppe
und gesamt. Fuer Kandidaten ohne Thema-Kennung (Agent) gilt `trifft`: alle
`fragmente` stehen im Kandidatentext.
"""

DISKREPANZEN = """\
Positiv sind nur die Karten der drei Gruppenplakate (hermes-entities `3fa1f46`,
`### cards: quotes`, "Variante A: nur Zitate, die im Stueck landen"):
G1 5, G2 5, G3 6.

- Kommentar 1402 (hermes-dev, t_56f8d856) nennt "G2 8 Stellen". Plakat G2 hat
  5; die Notizzeile "Int. 9, 13, 29, 21, 38" stammt aus einer frueheren
  Fassung. Das Prozessplakat (`01_prozess.md`, "Nicht doppelt zu den
  Gruppenplakaten") illustriert nur und belegt keine Verwendung im Stueck --
  nicht im Korpus.
- Kommentar 1402 nennt "L'unione fa la forza" einen generischen
  Erstvorschlag; das Plakat G2 Karte 2 verwendet die Stelle. Massgeblich ist
  der Plakatstand; 1402 ist nur Quelle der Hypothesen.
- `entfernt_am` ist nicht "verworfen" (G1-4 ist positiv und hat nur
  entfernte Zeilen). Negativ ist nur `nein` ohne `ja` (Spec F7.3).
- Hypothese (d) "nachgeladenes Material nie im Pool" ist fuer den Pool
  widerlegt (Queer-Viertel, lingua del santo stehen geprueft im Pool); es
  stand in der Rangliste zu weit hinten.

Volle Begruendung: `docs/superpowers/specs/2026-10-11-zitatauswahl-gold-recall-design.md`.
"""

KOMMANDOS = """\
Alle Kommandos im Haupt-Checkout ausfuehren (dort liegt `betrieb/padua.db`;
im Worktree gibt es kein `betrieb/`, dort `kopie --quelle <haupt-checkout>/betrieb/padua.db`).

```
uv run --extra dev python -m scripts.zitatauswahl kopie
uv run --extra dev python -m scripts.zitatauswahl kopie --quelle <haupt-checkout>/betrieb/padua.db
uv run --extra dev python -m scripts.zitatauswahl gold --db var/zitatauswahl/padua-kopie.db
uv run --extra dev python -m scripts.zitatauswahl pruefe --db var/zitatauswahl/padua-kopie.db
uv run --extra dev python -m scripts.zitatauswahl historisch --db var/zitatauswahl/padua-kopie.db
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante B1 --lauf 1 --gruppe G1
uv run --extra dev python -m scripts.zitatauswahl neu --db var/zitatauswahl/padua-kopie.db --variante I-a --lauf 1 --gruppe G1 --prompt docs/messung/zitatauswahl/prompt-I-a.md
uv run --extra dev python -m scripts.zitatauswahl bericht
uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider -n 2 tests/test_zitatauswahl.py
```

(`neu` je Variante fuer `--lauf 1 2 3` und `--gruppe G1 G2 G3`; Mutationstest:
`test_mutation_*` in `tests/test_zitatauswahl.py`. Rohergebnisse:
`docs/messung/zitatauswahl/*.jsonl`. Kopie und Proxy: Spec E5.)
"""

GRENZEN = """\
- n = 15 Stellen im Pool (G3-3 "Mara Venier" liegt ausserhalb, Hypothese c);
  eine Stelle sind 6,7 Prozentpunkte. Deshalb die Schwelle E7 (mindestens zwei
  Stellen, keine Ueberlappung der Laeufe, keine Gruppe schlechter).
- B0 ist verzerrt: die Gruppen haben aus den sichtbaren Top-5 gewaehlt.
  Verglichen wird nur Neu-Lauf gegen Neu-Lauf.
- Die Kopie zeigt den Stand vom 11.10.2026, nicht den zur Zeit der Schaerfung
  (07./08.10.); Gold-Fragmente im Nicht-Material-Teil sind maskiert (Spalte
  "maskiert", Spec E6).
- Der Pool selbst (ein Beleg je Thema, `verdichter.py`) ist nicht Gegenstand
  dieser Karte.
- Proxy-Timeout: G1:szene:2 (182 Themen) braucht etwa 180-350 s; in B1 Lauf 2
  liefen drei Versuche in den Timeout, der vierte gelang. `lade_roh` hebt die
  Fehlerzeilen durch die erfolgreiche Wiederholung auf.
- I-a Lauf 3 ist ungueltig: G1:szene:2 (Szene mit ~182 Themen) endete dort
  sechsmal im Proxy-Timeout (je ~370 s = 2 Versuche a CLAUDE_TIMEOUT_S 180 s);
  der Betriebs-Timeout von 180 s je Versuch reicht bei dieser Szene oft nicht.
  Es gibt daher nur 2 gueltige I-a-Laeufe (B1: 3). Die Spanne 9–9 stuetzt sich
  auf zwei Laeufe und ist schwaecher belegt als die B1-Spanne.
- E7-Entscheidung I-a gegen B1, die drei Bedingungen mit Zahlen: (1) Gewinn
  mindestens zwei Stellen: erfuellt, 6,0 -> 9,0 von 15 (+3,0); (2) keine
  Ueberlappung der Laeufe: erfuellt, B1 5–7 gegen I-a 9–9, I-a-Minimum 9
  liegt ueber dem B1-Maximum 7; (3) keine Gruppe schlechter: **verletzt**,
  G3 sinkt von 1,67 auf 1,50 (G1 0,3 -> 3,0; G2 4,0 -> 4,5). I-a wird
  deshalb nicht uebernommen; die Betriebs-Prompts (EN und DE) bleiben
  unveraendert.
- Die Live-DB liegt im Haupt-Checkout unter `betrieb/padua.db`; im Worktree
  wurde die Kopie mit `python -m scripts.stueckmodell_kopie
  <haupt-checkout>/betrieb/padua.db var/zitatauswahl/padua-kopie.db` erzeugt.
- I-b: nicht gemessen (Datenschutz-Gate nicht freigegeben).
"""


def _zahl(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _zeile_variante(gruppe: str, variante: str, l: dict, l5: dict, gold: list[dict]) -> str | None:
    if not l:
        return None
    t = [x["recall"][gruppe]["treffer"] for x in l.values()]
    n = next(iter(l.values()))["recall"][gruppe]["n"]
    t5 = [x["recall"][gruppe]["treffer"] for x in l5.values()]
    neg = [negativ_at_k(x["ranglisten"], gold).get(gruppe, 0) for x in l.values()]
    mittel = sum(t) / len(t)
    spanne = f"{min(t)}–{max(t)}" if len(t) > 1 else str(t[0])
    zehn = f"{t[0]}/{n}" if len(t) == 1 else f"{_zahl(mittel)}/{n} ({spanne})"
    fuenf = _zahl(sum(t5) / len(t5)) if t5 else "–"
    return (f"| {gruppe} | {variante} | {zehn} | {fuenf} | {_zahl(sum(neg) / len(neg))} "
            f"| {len(l)} | {sum(x['maskiert'] for x in l.values())} |")


def _rang(liste: list[int] | None, themen: list[int]) -> str:
    if liste is None:
        return "?"
    for i, t in enumerate(liste, start=1):
        if t in themen:
            return str(i)
    return "–"


def schreibe_bericht(gold: list[dict], zeilen: list[dict], pfad=BERICHT) -> str:
    gruppen = sorted({g["gruppe"] for g in gold})
    l10 = {v: laeufe(zeilen, gold, v) for v in VARIANTEN}
    l5 = {v: laeufe(zeilen, gold, v, k=5) for v in VARIANTEN}
    ia_ok, ia_gruende = entscheide(l10["B1"], l10["I-a"])
    ib_basis = "I-a" if ia_ok else "B1"
    ib_ok, ib_gruende = entscheide(l10[ib_basis], l10["I-b"])

    def entscheidung(name, basis, ok, gruende):
        if not l10[name]:
            return f"- {name}: nicht gemessen (keine vollstaendigen Laeufe)."
        if ok:
            return f"- {name} gegen {basis}: **uebernommen** -- alle drei Bedingungen E7 erfuellt."
        return f"- {name} gegen {basis}: **nicht uebernommen** -- " + "; ".join(gruende) + "."

    entscheidungen = [entscheidung("I-a", "B1", ia_ok, ia_gruende),
                      entscheidung("I-b", ib_basis, ib_ok, ib_gruende)]
    if not l10["I-b"]:
        entscheidungen[1] = ("- I-b: nicht gemessen (Datenschutz-Gate nicht freigegeben). "
                             "Die Sperre `eintraege_mit_frage` bleibt stehen.")
    fix = [n for n, ok in (("I-a", ia_ok), ("I-b", ib_ok)) if ok and l10[n]]

    pos = _positive(gold)
    neg = [g for g in gold if g["polaritaet"] == "negativ"]
    pool = pool_recall(gold)
    z = ["# Messung Zitatauswahl InScribe (Padua, Oktober 2026)", "",
         "Karte `t_2349e9a8` / Umsetzung `t_2f905d2c`. Erzeugt mit "
         "`python -m scripts.zitatauswahl bericht`; Spec: "
         "`docs/superpowers/specs/2026-10-11-zitatauswahl-gold-recall-design.md`.", "",
         "## Kurzfassung", ""]

    def gesamt(v):
        l = l10[v]
        if not l:
            return "nicht gemessen"
        t = [x["recall"]["gesamt"]["treffer"] for x in l.values()]
        n = next(iter(l.values()))["recall"]["gesamt"]["n"]
        return f"{_zahl(sum(t) / len(t))}/{n}"
    z.append("Recall@10 gesamt: " + " · ".join(f"{v} {gesamt(v)}" for v in VARIANTEN) + ".")
    z.append("")
    z.append(f"Fix: **{', '.join(fix)}** uebernommen." if fix
             else "Fix: **keiner** -- keine Intervention erfuellt die Schwelle E7.")
    z += ["", "## Gold-Korpus", "",
          f"Positiv {len(pos)} (im Pool {sum(g['im_pool'] for g in pos)}), negativ {len(neg)}. "
          + " · ".join(f"{gr}: positiv {pool[gr][1]}, im Pool {pool[gr][0]}, negativ "
                       f"{sum(1 for g in neg if g['gruppe'] == gr)}" for gr in gruppen) + ".",
          "", "### Format", "", FORMAT_DOKU, "### Herkunft und Diskrepanzen", "", DISKREPANZEN,
          "## Ergebnisse je Gruppe", "",
          "Recall@10: Mittel/n (min–max ueber Laeufe); Recall@5 = sichtbare Liste; "
          "Negativ@10 = verworfene Paare in den Top-10 (Mittel).", "",
          "| Gruppe | Variante | Recall@10 | Recall@5 | Negativ@10 | Laeufe | maskiert |",
          "|---|---|---|---|---|---|---|"]
    for gr in gruppen + ["gesamt"]:
        for v in VARIANTEN:
            zeile = _zeile_variante(gr, v, l10[v], l5[v], gold)
            if zeile:
                z.append(zeile)
    z += ["", "Pool-Recall (Obergrenze, Hypothese c): "
          + " · ".join(f"{gr} {pool[gr][0]}/{pool[gr][1]}" for gr in gruppen + ["gesamt"]) + ".",
          "", "## Rang jeder Gold-Stelle", "",
          "Rang des ersten Gold-Themas in der Rangliste des Ziels, je Lauf (`–` = nicht in der Liste, "
          "`?` = Fehler).", "",
          "| Stelle | Ziel | " + " | ".join(VARIANTEN) + " |",
          "|---|---|" + "---|" * len(VARIANTEN)]
    for g in pos:
        zellen = []
        for v in VARIANTEN:
            r = [_rang(x["ranglisten"].get(ziel_schluessel(g)), g["thema_ids"]) for x in l10[v].values()]
            zellen.append("/".join(r) if r else "")
        im = "" if g["im_pool"] else " (nicht im Pool)"
        z.append(f"| {g['id']}{im} | Szene {g['ziel']['nummer']} | " + " | ".join(zellen) + " |")
    z += ["", "## Entscheidungen (E7)", "", *entscheidungen, "",
          "## Kommandos zum Nachrechnen", "", KOMMANDOS, "## Grenzen", "", GRENZEN]
    text = "\n".join(z)
    Path(pfad).parent.mkdir(parents=True, exist_ok=True)
    Path(pfad).write_text(text, encoding="utf-8")
    return text


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
    n = sub.add_parser("neu")
    n.add_argument("--db", default=str(KOPIE))
    n.add_argument("--gold", default=str(GOLD))
    n.add_argument("--variante", required=True, choices=["B1", "I-a", "I-b"])
    n.add_argument("--lauf", type=int, required=True)
    n.add_argument("--gruppe", required=True, choices=sorted(GRUPPEN))
    n.add_argument("--nur", nargs="*", default=None, help="nur diese Ziel-Schluessel, z. B. G2:szene:5")
    n.add_argument("--prompt", default=None, help="Kandidat-Prompt statt schaerfung.prompt()")
    n.add_argument("--mit-frage", action="store_true", help="nur I-b (Task 8)")
    n.add_argument("--aus", default=None)
    b = sub.add_parser("bericht")
    b.add_argument("--gold", default=str(GOLD))
    b.add_argument("--roh", default=str(ROH))
    b.add_argument("--aus", default=str(BERICHT))
    a = p.parse_args(argv)

    if a.befehl == "kopie":
        from scripts import stueckmodell_kopie

        if "padua-test" in Path(a.quelle).name:
            raise SystemExit("Messung nur auf betrieb/padua.db")
        stueckmodell_kopie.kopiere(a.quelle, a.ziel)
        print(f"Kopie: {a.ziel}")
        return 0

    if a.befehl == "bericht":
        schreibe_bericht(lade_gold(a.gold), lade_roh(a.roh), a.aus)
        print(f"Bericht: {a.aus}")
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
    if a.befehl == "neu":
        import httpx

        from interview_theater import schaerfung

        # Profil nur hier setzen (nicht beim Import): Padua-Prompt und -Texte.
        os.environ.setdefault("IT_WORKSHOP", "padua-2026")
        gold = lade_gold(a.gold)
        fehler = pruefe_gold(conn, gold)
        if fehler:
            print("\n".join(fehler), file=sys.stderr)
            return 1
        if a.nur:
            bekannt = {ziel_schluessel(g) for g in _positive(gold) if g["gruppe"] == a.gruppe}
            unbekannt = sorted(set(a.nur) - bekannt)
            if unbekannt:
                print(f"--nur: kein Gold-Ziel in {a.gruppe}: {', '.join(unbekannt)} "
                      f"(bekannt: {', '.join(sorted(bekannt))})", file=sys.stderr)
                return 2
        system = Path(a.prompt).read_text(encoding="utf-8") if a.prompt else schaerfung.prompt()
        eintraege = None
        if a.mit_frage:
            eintraege = eintraege_mit_frage(conn, GRUPPEN[a.gruppe])
        e = einstellungen_messung(a.db)
        with httpx.Client(timeout=schaerfung.CLAUDE_TIMEOUT_S) as klient:
            zeile = neu_lauf(conn, e, klient, gold, a.gruppe, system, nur=a.nur, eintraege=eintraege)
        zeile.update(variante=a.variante, lauf=a.lauf)
        haenge_an(zeile, a.aus or ROH / f"{a.variante}.jsonl")
        for s, r in sorted(zeile["ranglisten"].items()):
            print(s, "FEHLER " + zeile["fehler"][s] if r is None else f"{len(r)} Stellen",
                  f"maskiert {zeile['maskiert'].get(s, 0)}", f"{zeile['dauer_ms'].get(s, 0)} ms")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
