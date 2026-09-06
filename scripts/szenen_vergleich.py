"""Szenen-Vergleich: EINE Szene mit festen Feldern, vier Modelle.

Birk 05.09. frueh: "mache als Vergleich auch einen Lauf mit Mistral, einen
mit dem Schweizer Modell und manuell auch einen mit Opus."

Wegwerf-DB aus Birks Testinterview (interview-birk.md): Kernthema, Format,
drei Figuren mit Sprachprofil (ein echter gemma-Aufruf je Figur, aus dem
einen Interview), Szene 1 mit denselben Feldern wie Simulationslauf birk-4.
Dann derselbe Prompt (szene.systemanweisung + szene.baue_nutzertext) an:

  kimi      moonshotai/Kimi-K2.6           Infomaniak, Reasoning an (Betrieb)
  mistral   mistralai/Mistral-Small-4-119B  Infomaniak
  apertus   swiss-ai/Apertus-v1.5-70B       Infomaniak
  opus      claude-opus-5                   lokaler Proxy (Abo)

Ausgabe: ein Markdown mit den vier Texten hintereinander, gleicher Prompt,
und der Prompt selbst als Anhang. Kein Richter -- Birk liest.

Aufruf (Env aus betrieb/gruppe1.env geladen):
    python -m scripts.szenen_vergleich [--nur kimi,opus] [--ausgabe PFAD]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import httpx

from interview_theater import aufnahme, db, einstellungen, llm, repo, sprachprofil, szene
from simulation import claude

MATERIAL = Path("/mnt/HC_Volume_106183673/projekte/interview-theater-material/birk-test/interview-birk.md")
CHAT_ID = -1000000009

MODELLE = {
    "kimi": "moonshotai/Kimi-K2.6",
    "mistral": "mistralai/Mistral-Small-4-119B-2603",
    "apertus": "swiss-ai/Apertus-v1.5-70B",
    "opus": "claude-opus-5",
}
#: max_tokens je Modell -- Apertus lehnt 200k ab (max_total_tokens kleiner,
#: gemessen 05.09.: 60k geht). Deckel, kein Ziel.
MAX_TOKENS_JE_MODELL = {"apertus": 60_000}

FIGUREN = [
    ("Mira", "Die Sammlerin: Hawaii im Kopf, Strand, Palmen, Pina Colada -- Bilder von ueberall, fragt nicht, woher."),
    ("Pola", "Die Erinnernde: Punkerin mit Piercings aus dem autonomen Zentrum, hat gepogt und getanzt."),
    ("Pal", "Die Zoegernde: macht Pfannkuchen mit Schokolade und Banane, zuletzt vor drei Monaten; prueft, was ihr gehoert."),
]

SZENE_1 = {
    "form": "Dialog",
    "ort": "Polizeikessel auf einer Palästina-Demo",
    "zeit": "Nachmittag, seit zwei Stunden eingekesselt",
    "anlass": "Die drei kennen sich nicht, stehen zufaellig nebeneinander im Kessel",
    "was_passiert": "Mira sagt, Trumps Riviera-Idee fuer Gaza waere eigentlich schoen, nur halt ohne Vertreibung. Pola zerreisst das. Daraus wird Streit, Pal steht dazwischen.",
    "was_anders": "Am Ende wissen die drei voneinander, dass sie ein Bild im Kopf tragen, das nicht ihres ist -- und gehen zusammen weg, ohne dass einer gewonnen hat.",
    "kernsaetze": "Eigentlich schön. Nur halt ohne Vertreibung.",
    "ton": "hitzig, dann leiser",
}


def _lies_material() -> tuple[dict, str]:
    text = MATERIAL.read_text()
    kopf, koerper = text.split("\n---\n", 1)[0], text.split("\n---\n", 1)[1]
    fragen = re.findall(r'^\s+- "(.*)"$', kopf, re.M)
    begriffe = re.search(r'^begriffe: "(.*)"$', kopf, re.M).group(1)
    return {"fragen": fragen, "begriffe": begriffe}, koerper.strip()


def _bereite_db(e, klm, ordner: str, conn):
    repo.sichere_gruppe(conn, CHAT_ID, e.bot_name, "Vergleich")
    meta, transkript = _lies_material()
    repo.setze_arbeitsstand(conn, CHAT_ID, "begriffe", meta["begriffe"])
    repo.setze_arbeitsstand(conn, CHAT_ID, "fragen", "\n".join(meta["fragen"]))
    repo.setze_arbeitsstand(conn, CHAT_ID, "kernthema",
                            "Woher kommen die Bilder, an die wir uns erinnern -- eigene oder fremde?")
    repo.setze_arbeitsstand(conn, CHAT_ID, "format", "Musical: Dialog, Lied, Rap")
    repo.setze_phase(conn, CHAT_ID, 6)
    aufnahme_id = aufnahme.importiere_text(conn, e, CHAT_ID, 1, transkript, name="Birk")
    for name, beschreibung in FIGUREN:
        repo.setze_figur(conn, CHAT_ID, name, beschreibung)
    figuren = repo.figuren(conn, CHAT_ID)
    for f in figuren:
        repo.setze_figur_quelle(conn, f["id"], aufnahme_id)
        sprachprofil.erstelle(klm, conn, e, f["id"])   # ein gemma-Aufruf je Figur
    sz_id = repo.lege_szene_an(conn, CHAT_ID, 1, "Der Kessel", None, None)
    for feld, wert in SZENE_1.items():
        repo.setze_szenenfeld(conn, sz_id, feld, wert)
    repo.setze_szene_figuren(conn, CHAT_ID, sz_id, [f["id"] for f in figuren])
    return conn, sz_id


def _ziel(conn, sz_id):
    for z in repo.hole_szenen(conn, CHAT_ID):
        if z["id"] == sz_id:
            return z
    raise SystemExit("Szene nicht gefunden")


def _schreibe_infomaniak(klm, e, system: str, nutzer: str, modell: str, kurz: str) -> tuple[str, float, dict]:
    import dataclasses
    start = time.monotonic()
    e2 = dataclasses.replace(e, llm_modell=modell)
    klm2 = llm.LLM(e2, klm._klient, klm._conn)
    text = klm2.prosa(None, system, nutzer, "szene_vergleich",
                      max_tokens=MAX_TOKENS_JE_MODELL.get(kurz, szene.MAX_TOKENS),
                      timeout=szene.TIMEOUT_S)
    return text, time.monotonic() - start, {}


def _schreibe_opus(system: str, nutzer: str) -> tuple[str, float, dict]:
    sim = claude.Claude()
    start = time.monotonic()
    text = sim.text(system, nutzer, "szene_vergleich", max_tokens=16_000)
    return text, time.monotonic() - start, {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur", default=",".join(MODELLE))
    ap.add_argument("--ausgabe", default=None)
    a = ap.parse_args(argv)
    gewaehlt = [m.strip() for m in a.nur.split(",") if m.strip()]

    e = einstellungen.laden()
    with tempfile.TemporaryDirectory() as ordner, httpx.Client() as klient:
        conn = db.verbinde(str(Path(ordner) / "vergleich.db"))
        db.initialisiere(conn)
        klm = llm.LLM(e, klient, conn)
        conn, sz_id = _bereite_db(e, klm, ordner, conn)
        ziel = _ziel(conn, sz_id)
        system = szene.systemanweisung(ziel["form"])
        nutzer = szene.baue_nutzertext(conn, CHAT_ID, "Schreib Szene 1.", ziel)

        ergebnisse = []
        for kurz in gewaehlt:
            modell = MODELLE[kurz]
            print(f"-> {kurz} ({modell})", flush=True)
            try:
                if kurz == "opus":
                    text, dauer, _ = _schreibe_opus(system, nutzer)
                else:
                    text, dauer, _ = _schreibe_infomaniak(klm, e, system, nutzer, modell, kurz)
                titel, kurzb, _fassung, _anders, volltext = szene.zerlege(text)
                ergebnisse.append((kurz, modell, dauer, titel, kurzb, volltext or text))
                print(f"   {dauer:.0f} s, {len(text)} Zeichen", flush=True)
            except Exception as fehler:  # noqa: BLE001
                ergebnisse.append((kurz, modell, 0.0, None, None, f"FEHLER: {fehler}"))
                print(f"   FEHLER: {fehler}", flush=True)

    figuren_text = "\n".join(
        f"- **{f['name']}** -- {f['sprachprofil'] or '(kein Profil)'}\n  Zitate: {f['zitate']}"
        for f in repo.figuren(conn, CHAT_ID)
    ) if False else ""

    aus = [f"# Szenen-Vergleich: vier Modelle, ein Prompt -- {time.strftime('%Y-%m-%d %H:%M')}\n",
           "Szene 1 aus Birks Testinterview, Felder wie Simulationslauf birk-4, Figuren Mira/Pola/Pal mit Sprachprofil aus dem einen Interview.",
           "Gleicher Systemprompt (szene.md + formen/dialog.md + theater-tells.md), gleicher Nutzertext. Kein Richter.\n"]
    for kurz, modell, dauer, titel, kurzb, volltext in ergebnisse:
        aus.append(f"\n---\n\n## {kurz} -- `{modell}` -- {dauer:.0f} s\n")
        if titel:
            aus.append(f"**{titel}** -- {kurzb}\n")
        aus.append("```\n" + volltext.strip() + "\n```\n")
    aus.append("\n---\n\n## Anhang: der Nutzertext, den alle vier bekommen haben\n\n```\n" + nutzer + "\n```\n")
    pfad = Path(a.ausgabe or f"/mnt/HC_Volume_106183673/projekte/interview-theater-material/ergebnis/szenen-vergleich-{time.strftime('%H%M')}.md")
    pfad.write_text("\n".join(aus))
    print("Ausgabe:", pfad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
