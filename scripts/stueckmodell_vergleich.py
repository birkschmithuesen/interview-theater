"""Ansichten vorher/nachher (Task 0 gegen Task 17), Karte t_fd88600b.

    uv run --extra dev python -m scripts.stueckmodell_vergleich var/stueckmodell/ansichten-vorher.json var/stueckmodell/ansichten-nachher.json var/stueckmodell/padua-migriert.db.konflikte.json
"""

import json
import sys

from interview_theater import stueck_sicht as sicht

_ORT = ("karte_wo", "werkbank_ort", "prompt_wo")


def _orte(f: dict) -> set[str]:
    return {sicht.normalisiert(f.get(k)) for k in _ORT if (f.get(k) or "").strip()}


def vergleiche(vorher: dict, nachher: dict, konflikte: dict) -> dict:
    im_bericht = {(str(k["chat_id"]), str(k["szene"]), k["art"]) for k in konflikte["konflikte"]}
    gleich, einheitlich, fehler = 0, 0, []
    for chat, szenen in vorher.items():
        for nr, f in szenen.items():
            n = nachher.get(chat, {}).get(nr)
            if n is None:
                fehler.append(f"{chat}/{nr}: Szene fehlt nachher")
                continue
            alt, neu = _orte(f), _orte(n)
            if len(neu) > 1:
                fehler.append(f"{chat}/{nr}: nachher mehrere Orte {sorted(neu)}")
                continue
            ort = next(iter(neu), "")
            if ort and ort not in sicht.normalisiert(n.get("pdf_meta")):
                fehler.append(f"{chat}/{nr}: PDF-Kopf zeigt den Ort nicht")
            if len(alt) <= 1:
                if alt != neu and alt:
                    fehler.append(f"{chat}/{nr}: konsistenter Ort veraendert {alt} -> {neu}")
                else:
                    gleich += 1
            elif (chat, nr, "konflikt_ort") in im_bericht:
                einheitlich += 1
            else:
                fehler.append(f"{chat}/{nr}: Widerspruch ohne Berichtszeile")
            neuer_wer = sicht.normalisiert(n.get("karte_wer"))
            for stueck in sicht.teile_wer(f.get("karte_wer")):
                if sicht.normalisiert(stueck) not in neuer_wer:
                    fehler.append(f"{chat}/{nr}: Text verloren in wer: {stueck!r}")
            if not set(f.get("werkbank_figuren") or []) <= set(n.get("werkbank_figuren") or []):
                fehler.append(f"{chat}/{nr}: Figur aus der Werkbank verloren")
            if (sorted(f.get("fragen") or []) + sorted(f.get("punkte_offen") or [])
                    != sorted(n.get("fragen") or []) + sorted(n.get("punkte_offen") or [])):
                fehler.append(f"{chat}/{nr}: offene Fragen veraendert")
    return {"konsistent_gleich": gleich, "vereinheitlicht": einheitlich, "fehler": fehler}


if __name__ == "__main__":
    lade = lambda p: json.load(open(p, encoding="utf-8"))  # noqa: E731
    r = vergleiche(lade(sys.argv[1]), lade(sys.argv[2]), lade(sys.argv[3]))
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(1 if r["fehler"] else 0)
