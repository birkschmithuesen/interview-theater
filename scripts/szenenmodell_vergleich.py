"""Szenenmodell-Vergleich (Padua M2, 30.09.2026): claude-opus-5 gegen
claude-opus-5-5 -- schreiben beide Modelle einen anderen Szenentext auf
GENAU demselben Prompt?

Messkarte, kein Feature -- ``interview_theater/`` wird hier nur gelesen und
aufgerufen, nie geaendert. Nur erfundene Daten (``scripts/sprachstil_wirkung``,
Padua-Set), nie ``betrieb/soap.db`` oder echte Interviews.

**Der Weg, fest, nicht neu verhandelt.** Phase 7 (Feinschliff), Szene 1,
Form "Dialog", Variante "B" (kein Sprachstil) aus
``scripts/sprachstil_wirkung``. Der Prompt entsteht ueber
``sprachstil_wirkung.baue_db(pfad, "B", phase=7)`` +
``sprachstil_wirkung.szene_prompt(conn)`` -- also ``szene.systemanweisung()``
und ``szene.baue_nutzertext()``, genau der Weg aus ``szene.schreibe``. Die
Prosavorlage bleibt die feste ``sprachstil_wirkung.PROSA[1]`` (NICHT
``setze_vorlage`` aus einem echten Prosa-Lauf) -- damit ist der Prompt fuer
beide Modelle byte-identisch, und ``token_budget()`` haengt nicht vom
Modellnamen ab (nur davon, ob ``szene_anbieter == "claude"``), also aendert
sich am Prompt nichts, wenn ``e.szene_modell`` das eine oder das andere
Modell ist. Der Prompt wird deshalb genau EINMAL gebaut (``baue_prompt``)
und fuer beide Modelle wiederverwendet.

**Eigener Aufruf statt ``szene_claude.prosa``.** ``szene_claude.prosa`` wirft
bei ``stop_reason != "end_turn"`` und verwirft den Text -- fuer die Messung
wird aber genau der Fall gebraucht: Text UND ``stop_reason``, auch wenn die
Antwort abgeschnitten war. ``_rufe`` ist deshalb ein Zwilling von
``szene_claude.prosa`` mit demselben Koerper (``model``, ``max_tokens`` =
``szene_claude.MAX_TOKENS``, ``system``, ``messages``), demselben Timeout
(``szene.TIMEOUT_S``) und denselben Wartezeiten (``szene_claude.WARTEZEITEN``)
bei 429/5xx/Transportfehler -- andere 4xx geben sofort auf. Ein Fehler wird
im JSON als ``status: "fehler"`` mit ``fehler``-Text festgehalten, nie
geworfen: ein einzelner gescheiterter Lauf soll die anderen nicht mitreissen.

**Seriell, nie parallel** (AGENTS.md Falle 8: Infomaniak drosselt
Parallelitaet mit 429/5xx, und der Proxy hier ist keine Ausnahme). Die
Reihenfolge ist je Lauf verschraenkt -- Lauf 1 opus-5, Lauf 1 opus-5-5,
Lauf 2 opus-5, ... -- damit eine Tageszeit oder Proxylast nicht einem Modell
allein anhaengt.

**Das Workshop-Profil.** ``workshop/padua-2026/`` ist ein Geruest
(``geruest = true``) -- noch kein fertiges Profil. Der Vergleich laeuft
deshalb bewusst gegen das eingebaute Vorgabeprofil (Dortmund-Werte) und
setzt ``IT_WORKSHOP`` nicht selbst; ist die Variable in der Umgebung
trotzdem gesetzt, bricht das Skript ab, statt zwei nicht vergleichbare
Prompts zu bauen. Der aktive Profilname (``workshop.name()``) steht in jedem
Lauf-JSON und wird bei ``pfad`` mit ausgegeben.

Unterbefehle:
    pfad     baut den Prompt (kein Netz), schreibt ``prompt.txt``, druckt
             SHA-256, Zeichenzahlen und Profilnamen.
    lauf     echte Aufrufe gegen den lokalen Anthropic-Proxy, seriell,
             verschraenkt. Vorhandene Laeufe mit ``status == "ok"`` werden
             uebersprungen (Wiederaufnahme); vor dem ersten Aufruf wird
             geprueft, dass alle vorhandenen Laeufe zum selben Prompt
             gehoeren.
    tabelle  kein Netz: liest ``laeufe/*.json``, druckt eine Markdown-Tabelle
             (Modell, Lauf, Zeichen, Sekunden, Ausgabe-Token, stop_reason,
             Status) plus je Modell Mittelwert/Min/Max von Zeichen und
             Sekunden, dazu mechanische Zaehlungen je Lauf (Sprecherzeilen,
             die Pflichtzeilen ``Zusammenfassung:``/``Anders gemacht:``) und
             schreibt ``auswertung.json``.

Aufruf:
    python -m scripts.szenenmodell_vergleich pfad [--ausgabe DIR]
    python -m scripts.szenenmodell_vergleich lauf [--n 3]
        [--modell M ...] [--lauf i ...] [--ausgabe DIR]
    python -m scripts.szenenmodell_vergleich tabelle [--ausgabe DIR]

**Kein Test in diesem Modul selbst, ``lauf`` laeuft nie automatisch und
kostet Abo-Zeit am Proxy** -- wie ``scripts/sprachstil_wirkung.py``. Getestet
wird in ``tests/test_szenenmodell_vergleich.py`` ausschliesslich ueber
``httpx.MockTransport``, nie gegen den echten Proxy.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

import httpx

from interview_theater import szene, szene_claude, sprecher, workshop
from scripts.sprachstil_wirkung import (
    CHAT_ID, als_datei, baue_db, einstellungen_szene, szene_prompt, _sha,
)

WURZEL = Path(__file__).resolve().parent.parent
AUSGABE = WURZEL / "docs" / "szenenmodell-vergleich-2026-09-30"

#: Lokaler Anthropic-Proxy, Abo, kein Authorization-Header.
URL = "http://127.0.0.1:28764/v1/messages"

#: Referenz, Kandidat -- in dieser Reihenfolge auch bei der Verschraenkung.
MODELLE = ("claude-opus-5", "claude-opus-5-5")

#: n Vorgabe (Anzahl Laeufe je Modell).
N_VORGABE = 3


# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------


def profilname() -> str:
    """Der Name des aktiven Workshop-Profils -- oder ein Abbruch, wenn
    ``IT_WORKSHOP`` gesetzt ist: der Vergleich ist auf das eingebaute
    Vorgabeprofil festgelegt (``workshop/padua-2026`` ist noch ein Geruest),
    zwei Prompt-Varianten unter verschiedenen Profilen waeren nicht
    vergleichbar."""
    wert = (os.environ.get(workshop.VARIABLE) or "").strip()
    if wert:
        raise RuntimeError(
            f"{workshop.VARIABLE}={wert!r} ist gesetzt -- der Szenenmodell-"
            f"Vergleich ist auf das eingebaute Vorgabeprofil festgelegt "
            f"(workshop/padua-2026 ist noch ein Geruest). Variable entfernen "
            f"und erneut versuchen."
        )
    return workshop.name()


# ---------------------------------------------------------------------------
# Der Prompt -- einmal gebaut, fuer beide Modelle wiederverwendet
# ---------------------------------------------------------------------------


def baue_prompt() -> tuple[str, str]:
    """(System, Nutzer) des Feinschliff-Laufs -- Phase 7, Szene 1, Form
    "Dialog", Variante "B" (kein Sprachstil), Prosavorlage = die feste
    ``sprachstil_wirkung.PROSA[1]``. Byte-identisch fuer jedes Modell, weil
    ``szene.token_budget`` nur von ``szene_anbieter == "claude"`` abhaengt,
    nie vom konkreten Modellnamen."""
    e = einstellungen_szene()
    with tempfile.TemporaryDirectory() as ordner:
        conn = baue_db(Path(ordner) / "szene-B.db", "B", phase=7, e=e)
        try:
            return szene_prompt(conn, e)
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Der Aufruf -- Zwilling von szene_claude.prosa, wirft nie
# ---------------------------------------------------------------------------


def _rufe(klient: httpx.Client, modell: str, system: str, nutzer: str) -> dict:
    """Ein Aufruf an den Claude-Proxy, seriell mit den Wartezeiten aus
    ``szene_claude.WARTEZEITEN`` bei 429/5xx/Transportfehler. Anders als
    ``szene_claude.prosa`` wirft dies hier nie -- jeder Ausgang (Erfolg,
    abgeschnitten, HTTP-Fehler) wird als Dict zurueckgegeben."""
    koerper = {
        "model": modell,
        "max_tokens": szene_claude.MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": nutzer}],
    }
    headers = {"content-type": "application/json", "anthropic-version": szene_claude.API_VERSION}
    ergebnis: dict = {
        "status": "fehler", "text": "", "zeichen": 0, "dauer_s": 0.0,
        "stop_reason": None, "eingabe_token": None, "ausgabe_token": None,
        "versuche": 0,
    }
    letzter: str | None = None
    for versuch in range(len(szene_claude.WARTEZEITEN) + 1):
        ergebnis["versuche"] = versuch + 1
        start = time.monotonic()
        try:
            antwort = klient.post(URL, headers=headers, json=koerper, timeout=szene.TIMEOUT_S)
        except httpx.TransportError as fehler:
            ergebnis["dauer_s"] = round(time.monotonic() - start, 1)
            letzter = f"{type(fehler).__name__}: {fehler}"
            if versuch < len(szene_claude.WARTEZEITEN):
                time.sleep(szene_claude.WARTEZEITEN[versuch])
                continue
            ergebnis["fehler"] = letzter
            return ergebnis

        ergebnis["dauer_s"] = round(time.monotonic() - start, 1)
        code = antwort.status_code
        # 429/5xx: Wartezeiten, dann aufgeben. Andere 4xx: sofort aufgeben.
        if code == 429 or code >= 500:
            letzter = f"HTTP {code}"
            if versuch < len(szene_claude.WARTEZEITEN):
                time.sleep(szene_claude.WARTEZEITEN[versuch])
                continue
            ergebnis["fehler"] = letzter
            return ergebnis
        if code >= 400:
            ergebnis["fehler"] = f"HTTP {code}"
            return ergebnis

        try:
            daten = antwort.json()
        except ValueError as fehler:
            ergebnis["fehler"] = f"ungueltiges JSON: {fehler}"
            return ergebnis

        teile = [b.get("text") or "" for b in (daten.get("content") or [])
                 if isinstance(b, dict) and b.get("type") == "text"]
        text = "\n".join(teile).strip()
        nutzung = daten.get("usage") or {}
        ergebnis.update(
            text=text, zeichen=len(text),
            stop_reason=daten.get("stop_reason"),
            eingabe_token=nutzung.get("input_tokens"),
            ausgabe_token=nutzung.get("output_tokens"),
        )
        # Status "ok" nur bei nicht-leerem Text -- ein stop_reason != end_turn
        # bleibt "ok" mit Text, der Bericht (Tabelle) bewertet es.
        if text:
            ergebnis["status"] = "ok"
        else:
            ergebnis["fehler"] = f"keine Textbloecke (stop_reason={ergebnis['stop_reason']})"
        return ergebnis

    ergebnis["fehler"] = letzter or "kein Versuch durchgefuehrt"  # unerreichbar, Sicherheitsnetz
    return ergebnis


def _ein_lauf(klient: httpx.Client, modell: str, i: int, system: str, nutzer: str,
              sha: str, profil: str) -> dict:
    satz = {
        "modell": modell, "lauf": i, "url": URL, "chat_id": CHAT_ID,
        "zeitpunkt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "profil": profil, "prompt_sha256": sha,
        "system_zeichen": len(system), "nutzer_zeichen": len(nutzer),
    }
    satz.update(_rufe(klient, modell, system, nutzer))
    return satz


def _lade(pfad: Path) -> dict | None:
    try:
        return json.loads(pfad.read_text())
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Mechanische Zaehlungen fuer die Tabelle -- kein Modellaufruf
# ---------------------------------------------------------------------------


def _mechanik(text: str) -> dict:
    """Sprecherzeilen und die beiden Pflichtzeilen (``ZUSAMMENFASSUNG:``,
    ``ANDERS GEMACHT:``) -- ueber dieselben Funktionen, die der Bot selbst
    nutzt (``szene.zerlege``, ``sprecher.zerlege``), nicht nachgebaut."""
    _titel, _kurz, zusammenfassung, anders, volltext = szene.zerlege(text or "")
    return {
        "sprecherzeilen": len(sprecher.zerlege(volltext)),
        "zusammenfassung_vorhanden": zusammenfassung is not None,
        "anders_gemacht_vorhanden": anders is not None,
    }


def _zeile(satz: dict) -> dict:
    m = _mechanik(satz.get("text") or "")
    return {
        "modell": satz.get("modell"), "lauf": satz.get("lauf"),
        "status": satz.get("status"), "zeichen": satz.get("zeichen", 0),
        "dauer_s": satz.get("dauer_s"),
        "eingabe_token": satz.get("eingabe_token"), "ausgabe_token": satz.get("ausgabe_token"),
        "stop_reason": satz.get("stop_reason"),
        **m,
    }


def _stat(werte: list[float]) -> dict | None:
    werte = [w for w in werte if w is not None]
    if not werte:
        return None
    return {"mittel": round(statistics.mean(werte), 1), "min": round(min(werte), 1),
            "max": round(max(werte), 1)}


# ---------------------------------------------------------------------------
# Unterbefehle
# ---------------------------------------------------------------------------


def befehl_pfad(a) -> int:
    try:
        profil = profilname()
    except RuntimeError as fehler:
        print(fehler, file=sys.stderr)
        return 1
    ausgabe = Path(a.ausgabe)
    ausgabe.mkdir(parents=True, exist_ok=True)
    system, nutzer = baue_prompt()
    (ausgabe / "prompt.txt").write_text(als_datei(system, nutzer))
    print(f"Profil: {profil}")
    print(f"SHA-256: {_sha(system, nutzer)}")
    print(f"System: {len(system)} Zeichen")
    print(f"Nutzer: {len(nutzer)} Zeichen")
    print(f"Ausgabe: {ausgabe / 'prompt.txt'}")
    return 0


def befehl_lauf(a) -> int:
    try:
        profil = profilname()
    except RuntimeError as fehler:
        print(fehler, file=sys.stderr)
        return 1

    ausgabe = Path(a.ausgabe)
    laeufe = ausgabe / "laeufe"
    laeufe.mkdir(parents=True, exist_ok=True)

    system, nutzer = baue_prompt()
    sha = _sha(system, nutzer)

    # Pflicht: derselbe Prompt fuer alle Laeufe -- vorhandene Laeufe mit
    # einem anderen Hash zeigen einen Stand, der nicht mehr vergleichbar ist.
    for pfad in sorted(laeufe.glob("*.json")):
        alt = _lade(pfad)
        if alt and alt.get("prompt_sha256") and alt["prompt_sha256"] != sha:
            print(f"{pfad.name}: prompt_sha256 weicht vom aktuellen Prompt ab -- "
                  f"abgebrochen (alte und neue Laeufe waeren nicht vergleichbar)",
                  file=sys.stderr)
            return 1

    modelle = a.modell or list(MODELLE)
    laufnummern = a.lauf or list(range(1, a.n + 1))
    auftraege = [(i, m) for i in laufnummern for m in modelle]

    fehlend: list[tuple[str, int]] = []
    with httpx.Client(timeout=szene.TIMEOUT_S) as klient:
        for i, modell in auftraege:
            ziel = laeufe / f"{modell}-{i}.json"
            alt = _lade(ziel)
            if alt and alt.get("status") == "ok":
                print(f"{ziel.name}: vorhanden (ok), uebersprungen")
                continue
            print(f"{ziel.name}: laeuft ...", flush=True)
            satz = _ein_lauf(klient, modell, i, system, nutzer, sha, profil)
            ziel.write_text(json.dumps(satz, ensure_ascii=False, indent=2) + "\n")
            print(f"{ziel.name}: {satz['status']} {satz.get('dauer_s', 0)} s, "
                  f"{satz.get('zeichen', 0)} Zeichen, stop_reason={satz.get('stop_reason')}",
                  flush=True)
            if satz["status"] != "ok":
                fehlend.append((modell, i))

    return 1 if fehlend else 0


def befehl_tabelle(a) -> int:
    ausgabe = Path(a.ausgabe)
    dateien = sorted((ausgabe / "laeufe").glob("*.json"))
    saetze = [s for s in (_lade(p) for p in dateien) if s]

    reihenfolge = {m: i for i, m in enumerate(MODELLE)}
    saetze.sort(key=lambda s: (reihenfolge.get(s.get("modell"), 99), s.get("lauf", 0)))
    zeilen_daten = [_zeile(s) for s in saetze]

    z: list[str] = []
    z.append("| Modell | Lauf | Zeichen | Sekunden | Ausgabe-Token | stop_reason | Status |")
    z.append("|---|---|---|---|---|---|---|")
    for zl in zeilen_daten:
        z.append(f"| {zl['modell']} | {zl['lauf']} | {zl['zeichen']} | {zl['dauer_s']} | "
                 f"{zl['ausgabe_token']} | {zl['stop_reason']} | {zl['status']} |")

    je_modell: dict = {}
    modelle_vorhanden = sorted({zl["modell"] for zl in zeilen_daten},
                               key=lambda m: reihenfolge.get(m, 99))
    z.append("")
    z.append("| Modell | n | Zeichen Mittel | Zeichen Min | Zeichen Max | "
             "Sekunden Mittel | Sekunden Min | Sekunden Max |")
    z.append("|---|---|---|---|---|---|---|---|")
    for modell in modelle_vorhanden:
        eigene = [zl for zl in zeilen_daten if zl["modell"] == modell]
        sz = _stat([zl["zeichen"] for zl in eigene])
        ss = _stat([zl["dauer_s"] for zl in eigene])
        je_modell[modell] = {"n": len(eigene), "zeichen": sz, "sekunden": ss}
        if sz and ss:
            z.append(f"| {modell} | {len(eigene)} | {sz['mittel']} | {sz['min']} | "
                     f"{sz['max']} | {ss['mittel']} | {ss['min']} | {ss['max']} |")
        else:
            z.append(f"| {modell} | {len(eigene)} | -- | -- | -- | -- | -- | -- |")

    z.append("")
    z.append("| Modell | Lauf | Sprecherzeilen | Zusammenfassung: | Anders gemacht: |")
    z.append("|---|---|---|---|---|")
    for zl in zeilen_daten:
        z.append(f"| {zl['modell']} | {zl['lauf']} | {zl['sprecherzeilen']} | "
                 f"{'ja' if zl['zusammenfassung_vorhanden'] else 'nein'} | "
                 f"{'ja' if zl['anders_gemacht_vorhanden'] else 'nein'} |")

    text = "\n".join(z) + "\n"
    print(text)

    ausgabe.mkdir(parents=True, exist_ok=True)
    (ausgabe / "auswertung.json").write_text(json.dumps({
        "erzeugt_von": "python -m scripts.szenenmodell_vergleich tabelle",
        "modelle": list(MODELLE),
        "laeufe": zeilen_daten,
        "je_modell": je_modell,
    }, ensure_ascii=False, indent=2) + "\n")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    unter = ap.add_subparsers(dest="befehl", required=True)

    p = unter.add_parser("pfad", help="Prompt bauen und schreiben (kein Netz)")
    p.add_argument("--ausgabe", default=str(AUSGABE))
    p.set_defaults(fn=befehl_pfad)

    p = unter.add_parser("lauf", help="echte Laeufe gegen den Claude-Proxy (seriell, kostet Abo-Zeit)")
    p.add_argument("--n", type=int, default=N_VORGABE)
    p.add_argument("--modell", action="append", choices=list(MODELLE),
                   help="nur dieses Modell (mehrfach), Vorgabe: beide")
    p.add_argument("--lauf", type=int, action="append", help="nur diese Laufnummer(n), mehrfach")
    p.add_argument("--ausgabe", default=str(AUSGABE))
    p.set_defaults(fn=befehl_lauf)

    p = unter.add_parser("tabelle", help="Markdown-Tabelle + auswertung.json (kein Netz)")
    p.add_argument("--ausgabe", default=str(AUSGABE))
    p.set_defaults(fn=befehl_tabelle)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
