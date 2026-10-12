"""Wiedergabe der Struktur-Wuensche aus p7audit.json gegen die MIGRIERTE
Kopie (Karte t_fd88600b). Jeder Wunsch ist ein Werkzeugaufruf der
Mutations-Schnittstelle -- derselbe Aufruf, den ein spaeterer Agent machte.

    uv run --extra dev python -m scripts.stueckmodell_wiedergabe --db var/stueckmodell/padua-migriert.db --audit /mnt/HC_Volume_106183673/hermes/profiles/birk/var/padua-nacht/p7audit.json --plan var/stueckmodell/wiedergabe.json

Der Plan (``wiedergabe.json``) ist eine Liste je ``post_id``: ``ausgang``
stellt den Stand VOR dem Wunsch wieder her (Quelle ``script``: kein
Veraltet-Vermerk), ``aufrufe`` ist der Wunsch (Quelle ``wiedergabe``),
``erwartet`` prueft die Ansichten (``karte``, ``pdf``, ``werkbank`` mit
``enthaelt`` / ``enthaelt_nicht`` als Text oder Liste, ``veraltet`` mit
optionalem ``grund`` und ``anzahl`` (Zeilen der Szene), ``frage_offen`` /
``frage_zu``, ``speichern_gesperrt``)."""

from __future__ import annotations


import argparse
import json
import os
import re

_STRUKTUR_ZIEL = re.compile(r"karte|rahmen|figur|reihenfolge", re.I)


def struktur(audit: list[dict]) -> list[dict]:
    return [a for a in audit if _STRUKTUR_ZIEL.search(a.get("ziel") or "")
            or "karte" in (a.get("fehlerklasse") or "").lower()]


def _chat_id(conn, gruppe: str) -> int:
    nr = gruppe.strip().upper().lstrip("G")
    return conn.execute("SELECT chat_id FROM gruppe WHERE bot_name = ?",
                        (f"padua-gruppe{nr}",)).fetchone()[0]


def _liste(wert) -> list[str]:
    return [] if wert is None else [wert] if isinstance(wert, str) else list(wert)


def _pruefe(conn, chat_id: int, e: dict, frage_ids: dict) -> str | None:
    from interview_theater import repo, stueck, szenenkarte, web, web_daten

    s = next((z for z in repo.hole_szenen(conn, chat_id)
              if z["nummer"] == e.get("szene") and not z["entfernt_am"]), None)
    art = e["ansicht"]
    if art == "veraltet":
        if e.get("szene") is None:
            zeilen = [v for v in repo.offene_veraltet(conn, chat_id) if v["ansicht"] == "kopf"]
        else:
            zeilen = [v for v in repo.offene_veraltet(conn, chat_id)
                      if v["szene_id"] == (s["id"] if s else None)]
        if not any((e.get("grund") or "") in v["grund"] for v in zeilen):
            return f"kein Veraltet-Vermerk {e}"
        if "anzahl" in e and len(zeilen) != e["anzahl"]:
            return f"{len(zeilen)} Veraltet-Zeilen statt {e['anzahl']} ({e})"
        return None
    if art in ("frage_offen", "frage_zu"):
        f = repo.hole_offene_frage(conn, frage_ids[e["frage"]])
        offen = f["status"] in ("offen", "vertagt")
        return None if offen == (art == "frage_offen") else f"Frage-Status {f['status']}"
    if art == "speichern_gesperrt":
        return None if stueck.karte(conn, s)["fragen"] else "Karte ohne offene Frage"
    token = repo.stelle_web_token_sicher(conn, chat_id)
    daten = web_daten.gruppe_nach_token(conn, token)
    text = {"karte": lambda: szenenkarte.karte_text(stueck.karte(conn, s), s, chat_id),
            "pdf": lambda: web.textbuch_html(daten, token),
            "werkbank": lambda: json.dumps([z for z in daten["szenen"] if z["nummer"] == e.get("szene")],
                                           ensure_ascii=False)}[art]()
    if art == "pdf":
        # der Szenenabschnitt allein (sonst trifft jeder Ort in einer anderen Szene)
        teile = [t for t in text.split('<h2 class="szenenkopf">')[1:]
                 if re.search(rf"(?:Scene|Scena|Szene)\s+{e.get('szene')}\b", t[:200], re.I)]
        text = teile[0] if teile else ""
        if e.get("zeile"):   # nur eine Zeile des Abschnitts, z. B. die Besetzung
            m = re.search(rf'<p class="{e["zeile"]}">(.*?)</p>', text, re.S)
            text = m.group(1) if m else ""
    import html as htmllib
    roh = htmllib.unescape(text)
    for muss in _liste(e.get("enthaelt")):
        if muss.lower() not in roh.lower():
            return f"{art} S{e.get('szene')} ohne {muss!r}"
    for darf_nicht in _liste(e.get("enthaelt_nicht")):
        if darf_nicht.lower() in roh.lower():
            return f"{art} S{e.get('szene')} enthaelt noch {darf_nicht!r}"
    return None


def _text_schritt(conn, chat_id: int, a: dict) -> None:
    """Kein Werkzeug: die Prosa einer Szene auf den Stand VOR dem Wunsch
    zuruecksetzen (die Kopie traegt den Endstand nach den Robo-Patches;
    es gibt bewusst kein Werkzeug, das Prosa still umschreibt)."""
    from interview_theater import repo

    z = next(z for z in repo.hole_szenen(conn, chat_id)
             if z["nummer"] == a["szene"] and not z["entfernt_am"])
    en, it = z["volltext"] or "", z["volltext_it"]
    if a.get("ersetze"):
        en = en.replace(a["ersetze"], a.get("durch", ""))
        it = it.replace(a["ersetze"], a.get("durch", "")) if it else it
    if a.get("anhaengen"):
        en = en.rstrip() + "\n" + a["anhaengen"]
    repo.setze_stagescript_beide(conn, z["id"], en, it)


def spiele(conn, audit: list[dict], plan: list[dict]) -> dict:
    from interview_theater import stueck

    je_post = {p["post_id"]: p for p in plan}
    eintraege = struktur(audit)
    ergebnis = {"struktur": len(eintraege), "nicht_anwendbar": [], "vorher_drin": 0,
                "vorher_automatisch": 0, "nachher_korrekt": 0, "fehler": []}
    frage_ids: dict[str, int] = {}
    for a in eintraege:
        p = je_post.get(a["post_id"])
        if p is None or p.get("nicht_anwendbar"):
            ergebnis["nicht_anwendbar"].append(a["post_id"])
            continue
        if a["status"] == "DRIN":
            ergebnis["vorher_drin"] += 1
            if "robo" not in (a.get("beleg") or "").lower():
                ergebnis["vorher_automatisch"] += 1
        chat_id = _chat_id(conn, p["gruppe"])
        for quelle, schritte in (("script", p.get("ausgang", [])), ("wiedergabe", p.get("aufrufe", []))):
            for schritt in schritte:
                argumente = dict(schritt["argumente"])
                if schritt["werkzeug"] == "text_aendern":
                    _text_schritt(conn, chat_id, argumente)
                    continue
                if "frage_ref" in argumente:
                    argumente["frage_id"] = frage_ids[argumente.pop("frage_ref")]
                r = getattr(stueck, schritt["werkzeug"])(conn, chat_id, quelle=quelle, **argumente)
                if schritt.get("merke_frage"):
                    frage_ids[schritt["merke_frage"]] = r.frage_id
                if not r.ok:
                    ergebnis["fehler"].append(f"{a['post_id']}: {schritt['werkzeug']} -> {r.fehler}")
        fehler = [f for f in (_pruefe(conn, chat_id, e, frage_ids) for e in p["erwartet"]) if f]
        if fehler:
            ergebnis["fehler"] += [f"{a['post_id']}: {f}" for f in fehler]
        else:
            ergebnis["nachher_korrekt"] += 1
    return ergebnis


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--audit", required=True)
    p.add_argument("--plan", required=True)
    a = p.parse_args()
    os.environ.setdefault("IT_WORKSHOP", "padua-2026")
    from interview_theater import db

    conn = db.verbinde(a.db)
    r = spiele(conn, json.load(open(a.audit, encoding="utf-8")),
               json.load(open(a.plan, encoding="utf-8")))
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
