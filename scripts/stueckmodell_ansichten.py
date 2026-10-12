"""Was jede Ansicht je Szene ueber Ort, Besetzung und offene Fragen zeigt
(Karte t_fd88600b) -- gelesen ueber die Ansichten selbst, nicht ueber die
Spalten: Script-Tab/PDF (``web.textbuch_html``), CoThinker-Karte
(``web._szenenkarten_html``), Werkbank-Daten (``web_daten``), Szenen-Prompt
(``stagescript.baue_nutzertext``).

Laeuft VOR (Task 0) und NACH (Task 17) dem Umbau gegen dieselbe Kopie;
``scripts.stueckmodell_vergleich`` legt beide nebeneinander.

    uv run --extra dev python -m scripts.stueckmodell_ansichten --db var/stueckmodell/padua-kopie.db --aus var/stueckmodell/ansichten-vorher.json
"""

from __future__ import annotations


import argparse
import html as htmllib
import json
import os
import re

_TAG = re.compile(r"<[^>]+>")
_NUMMER = re.compile(r"(?:Scene|Scena|Szene)\s+(\d+)", re.I)


def _text(fragment: str | None) -> str:
    return " ".join(htmllib.unescape(_TAG.sub(" ", fragment or "")).split())


def _erstes(muster: str, text: str) -> str:
    treffer = re.search(muster, text, re.S)
    return _text(treffer.group(1)) if treffer else ""


def _nach_label(zeile: str, label: str) -> str:
    teile = [t.strip() for t in re.split(r"<br\s*/?>", zeile)]
    for t in teile:
        t = _text(t)
        if t.lower().startswith(label.lower()):
            return t[len(label):].strip(" :")
    return ""


def _prompt_zeile(prompt: str, label: str) -> str:
    for zeile in prompt.splitlines():
        z = zeile.replace("**", "").strip()
        if z.lower().startswith(label.lower()):
            return z[len(label):].strip(" :")
    return ""


def fakten(conn, chat_id: int) -> dict[str, dict]:
    from interview_theater import repo, stagescript, szenenkarte, web, web_daten

    token = repo.stelle_web_token_sicher(conn, chat_id)
    daten = web_daten.gruppe_nach_token(conn, token)
    t = szenenkarte._T(chat_id)
    ergebnis: dict[str, dict] = {}
    pdf = web.textbuch_html(daten, token)
    for stueck in pdf.split('<h2 class="szenenkopf">')[1:]:
        nr = _NUMMER.search(stueck[:200])
        if not nr:
            continue
        e = ergebnis.setdefault(nr.group(1), {})
        e["pdf_meta"] = _erstes(r'<p class="meta">(.*?)</p>', stueck)
        e["pdf_besetzung"] = _erstes(r'<p class="besetzung">(.*?)</p>', stueck)
    karten = web._szenenkarten_html(web_daten.szenenkarten(conn, chat_id), chat_id)
    for stueck in re.split(r'<li class="karte-eintrag', karten)[1:]:
        nr = re.search(r'data-nummer="(\d+)"', stueck)
        if not nr:
            continue
        e = ergebnis.setdefault(nr.group(1), {})
        angaben = re.search(r'<p class="karte-angaben">(.*?)</p>', stueck, re.S)
        e["karte_wo"] = _nach_label(angaben.group(1), t._ZEILE_ORT) if angaben else ""
        e["karte_wer"] = _nach_label(angaben.group(1), t._ZEILE_WER) if angaben else ""
    for s in daten["szenen"]:
        if s.get("nummer") is None:
            continue
        e = ergebnis.setdefault(str(s["nummer"]), {})
        e["werkbank_ort"] = (s.get("ort") or "").strip()
        e["werkbank_figuren"] = list(s.get("figuren") or [])
        karte = s.get("karte") or {}
        e["fragen"] = list(karte.get("fragen") or [])
        e["punkte_offen"] = [p for p in karte.get("punkte") or [] if "[OPEN" in p.upper()]
    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] is None or s["entfernt_am"]:
            continue
        prompt = stagescript.baue_nutzertext(conn, chat_id, s)
        e = ergebnis.setdefault(str(s["nummer"]), {})
        e["prompt_wo"] = _prompt_zeile(prompt, t._ZEILE_ORT)
        e["prompt_wer"] = _prompt_zeile(prompt, t._ZEILE_WER)
    return ergebnis


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--aus", required=True)
    p.add_argument("--profil", default="padua-2026")
    a = p.parse_args()
    os.environ.setdefault("IT_WORKSHOP", a.profil)
    from interview_theater import db

    conn = db.verbinde(a.db)
    gruppen = [z[0] for z in conn.execute("SELECT chat_id FROM gruppe ORDER BY chat_id")]
    alles = {str(c): fakten(conn, c) for c in gruppen}
    with open(a.aus, "w", encoding="utf-8") as f:
        json.dump(alles, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"{sum(len(v) for v in alles.values())} Szenen aus {len(alles)} Gruppen -> {a.aus}")


if __name__ == "__main__":
    main()
