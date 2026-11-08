"""Baut den Wiedergabe-Plan fuer ``scripts.stueckmodell_wiedergabe`` aus der
migrierten Kopie und dem Audit (Karte t_fd88600b, Task 17).

    uv run --extra dev python -m scripts.stueckmodell_wiedergabe_plan \\
        --db var/stueckmodell/padua-migriert.db \\
        --audit <p7audit.json> --aus var/stueckmodell/wiedergabe.json

Der Plan enthaelt Szenentext und Figurennamen der Padua-Gruppen und wird
deshalb NICHT eingecheckt (nur dieser Erzeuger).
"""
from __future__ import annotations

import argparse
import json
import sqlite3


def baue_plan(db: str, audit_pfad: str) -> list:
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    with open(audit_pfad, encoding="utf-8") as f:
        audit = {a["post_id"]: a for a in json.load(f)}
    def szene(g, n):
        return c.execute("select * from szene where chat_id=? and nummer=? and entfernt_am is null", (7000000000000 + g - 1, n)).fetchone()
    def punkt(g, n, anfang):
        k = json.loads(szene(g, n)["karte"])
        return next(p for p in k["punkte"] if p.startswith(anfang))
    S = lambda w, **a: {"werkzeug": w, "argumente": a}
    plan = []
    rahmen = c.execute("select rahmen from arbeitsstand where chat_id=7000000000000").fetchone()[0]
    orte = {n: szene(1, n)["ort"] for n in (1, 2, 3)}
    aus1 = [S("setze_ort", szene=n, ort="Sala prove") for n in (1, 2, 3)]
    auf1 = [S("setze_rahmen", rahmen=rahmen)] + [S("setze_ort", szene=n, ort=orte[n]) for n in (1, 2, 3)]
    erw1 = [{"ansicht": a, "szene": n, "enthaelt": "sala riunioni"} for n in (1, 2, 3) for a in ("karte", "pdf", "werkbank")]
    erw1 += [{"ansicht": "veraltet", "szene": n} for n in (1, 2, 3)]
    plan.append({"post_id": 2402, "gruppe": "G1", "ausgang": aus1, "aufrufe": auf1, "erwartet": erw1})
    plan.append({"post_id": 2412, "gruppe": "G1", "ausgang": [], "aufrufe": auf1,
                 "erwartet": erw1[:9] + [{"ansicht": "veraltet", "szene": n, "anzahl": 1} for n in (1, 2, 3)]})
    p3 = punkt(1, 3, "Tutti si alzano")
    plan.append({"post_id": 2420, "gruppe": "G1", "ausgang": [S("karte_aendern", szene=3, punkte_weg=[p3])],
                 "aufrufe": [S("karte_aendern", szene=3, punkte_hinzu=[p3])],
                 "erwartet": [{"ansicht": "karte", "szene": 3, "enthaelt": p3}]})
    n4 = audit[2424]["nachzug_vorschlag"]
    plan.append({"post_id": 2424, "gruppe": "G1", "ausgang": [],
                 "aufrufe": [S("karte_aendern", szene=3, punkte_hinzu=[n4])],
                 "erwartet": [{"ansicht": "karte", "szene": 3, "enthaelt": n4}, {"ansicht": "veraltet", "szene": 3}]})
    frage = "Dove sta Giona durante il rituale: dal centro del tavolo o dentro il cerchio? (da confermare)"
    plan.append({"post_id": 2439, "gruppe": "G1", "ausgang": [],
                 "aufrufe": [dict(S("frage_stellen", szene=3, frage=frage), merke_frage="giona")],
                 "erwartet": [{"ansicht": "frage_offen", "frage": "giona"}, {"ansicht": "speichern_gesperrt", "szene": 3}]})
    plan.append({"post_id": 2440, "gruppe": "G1", "ausgang": [],
                 "aufrufe": [S("frage_beantworten", frage_ref="giona", antwort="Giona resta nel buco al centro e da lì spiega e guida il rituale.")],
                 "erwartet": [{"ansicht": "frage_zu", "frage": "giona"}, {"ansicht": "karte", "szene": 3, "enthaelt_nicht": frage},
                              {"ansicht": "veraltet", "szene": 3}]})
    ausf, aufr = [], []
    fr = {1: "(moderatrice)", 2: "(Chicca) già seduta al tavolo", 3: "(Chicca)", 5: "(Chicca)"}
    for n in (1, 2, 3, 5):
        ausf.append(S("figur_aus_szene", name="Francesca", szene=n))
        aufr.append(S("figur_hinzu", name="Francesca", szene=n, rolle=fr[n]))
    for n in (2, 3, 5):
        ausf.append(S("figur_aus_szene", name="Anna", szene=n))
        aufr.append(S("figur_hinzu", name="Anna", szene=n, rolle="(Arlecchino)"))
    erw7 = []
    for n in (2, 3, 5):
        erw7.append({"ansicht": "karte", "szene": n, "enthaelt": ["Francesca (Chicca", "Anna (Arlecchino)"]})
        erw7.append({"ansicht": "pdf", "szene": n, "zeile": "besetzung", "enthaelt": ["Francesca", "Anna"]})
    erw7 += [{"ansicht": "karte", "szene": 1, "enthaelt": "Francesca (moderatrice)"},
             {"ansicht": "pdf", "szene": 1, "zeile": "besetzung", "enthaelt": "Francesca"},
             {"ansicht": "veraltet", "szene": None}]
    plan.append({"post_id": 2534, "gruppe": "G2", "ausgang": ausf, "aufrufe": aufr, "erwartet": erw7})
    p8 = punkt(2, 4, "Quando tutti sono al tavolo")
    plan.append({"post_id": 2563, "gruppe": "G2", "ausgang": [S("karte_aendern", szene=4, punkte_weg=[p8])],
                 "aufrufe": [S("karte_aendern", szene=4, punkte_hinzu=[p8])],
                 "erwartet": [{"ansicht": "karte", "szene": 4, "enthaelt": p8}]})
    o9 = "Ordine di arrivo: Pietro, Silvio, il babbano, Francesco"
    plan.append({"post_id": 2594, "gruppe": "G2", "ausgang": [],
                 "aufrufe": [S("karte_aendern", szene=3, punkte_hinzu=[o9]), S("karte_aendern", szene=4, punkte_hinzu=[o9])],
                 "erwartet": [{"ansicht": "karte", "szene": s, "enthaelt": o9} for s in (3, 4)]
                             + [{"ansicht": "veraltet", "szene": s} for s in (3, 4)]})
    plan.append({"post_id": None, "gruppe": "G2", "ausgang": [S("text_aendern", szene=3, anhaengen="È rimasta una sedia. Saresti l'ultimo.")], "aufrufe": [S("pruefe_szene", szene=3)],
                 "erwartet": [{"ansicht": "veraltet", "szene": 3, "grund": "saresti l'ultimo"}]})
    plan.append({"post_id": 2314, "gruppe": "G3", "nicht_anwendbar": True})
    q12 = "OBBLIGATORIO: Do you want to know how events will affect you?"
    plan.append({"post_id": 2318, "gruppe": "G3", "ausgang": [S("text_aendern", szene=5, ersetze="Do you want to know how events will affect you?", durch="")], "aufrufe": [S("karte_aendern", szene=5, punkte_hinzu=[q12])],
                 "erwartet": [{"ansicht": "veraltet", "szene": 5, "grund": "mandatory point missing"}]})
    voci = [f"Voce {i}" for i in (1, 3, 5)]
    p13 = punkt(3, 4, "✔ Voce 2 riporta")
    n13 = "Le parti sono divise tra tutte e cinque le voci: Voce 1, Voce 2, Voce 3, Voce 4, Voce 5."
    plan.append({"post_id": 2572, "gruppe": "G3",
                 "ausgang": [S("figur_aus_szene", name=v, szene=4) for v in voci],
                 "aufrufe": [S("figur_hinzu", name=v, szene=4) for v in voci]
                             + [S("karte_aendern", szene=4, punkte_weg=[p13], punkte_hinzu=[n13])],
                 "erwartet": [{"ansicht": "werkbank", "szene": 4, "enthaelt": [f"Voce {i}" for i in range(1, 6)]},
                              {"ansicht": "karte", "szene": 4, "enthaelt": [f"Voce {i}" for i in range(1, 6)]}]})
    return plan


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--audit", required=True)
    p.add_argument("--aus", required=True)
    a = p.parse_args(argv)
    plan = baue_plan(a.db, a.audit)
    with open(a.aus, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    print(len(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
