"""Opus liest die Prompt-Dumps einer Phase gegen Birks UX-Regeln.

Aufruf (Karte t_1dcf3864, 05.10.2026)::

    python3.11 -m scripts.pruefe_prompts_lesung \\
        docs/prompt-audit/2026-10-05-padua-voll

**Kein Test, laeuft nie automatisch** -- aber es kostet **nichts**: der Lauf
geht ueber ``simulation/claude.py`` an den lokalen Proxy, und der laeuft auf
einem Abonnement (dieselbe Trennlinie wie in der Simulation: der Pruefling
laeuft bei Infomaniak, die Pruefinstanz bei Opus). Sieben Aufrufe, einer je
Phase, **seriell**.

**Jedes Zitat wird mechanisch geprueft** (``zitat.pruefe``, dieselbe Funktion
wie bei Verdichter, Kernzitaten, Sprachprofil, Schaerfung und Dramaturgie --
keine zweite, groesszuegigere Normalisierung). Ein Judge kann jede Note
begruenden, auch eine falsche: die Begruendung entsteht nach dem Urteil, und
die Zitatpflicht ist das einzige mechanische Gegenmittel. Faellt ein Zitat
durch, gibt es **einen** Retry mit dem Hinweis; danach ist der Befund
``unsicher``, landet in ``lesung-unsicher.jsonl`` und geht nicht in den BEFUND.
"""

from __future__ import annotations

import json
from pathlib import Path

from interview_theater import zitat
from scripts import prompt_inventar as inv

REGELN = Path("docs/prompt-audit/ux-regeln-participatory-bot-ux.md")
RUBRIK = Path("simulation/ux_rubrik.md")

#: Kappe fuer (a), (b) und (c) ZUSAMMEN, und fuer (d) eigens. So ist der
#: Kartentext gebaut; gekappt wird NACH der Zitatpruefung, sonst verdraengt ein
#: unbelegter Befund einen belegten.
KAPPE_ABC = 10
KAPPE_D = 5

#: Ein Zitat darf ueber einen Zeilenumbruch gehen -- die Prompt-Dateien sind
#: auf 80 Zeichen umbrochen. Geprueft wird gegen ein Fenster um die genannte
#: Zeile.
FENSTER_ZEILEN = 2

#: Obergrenze des Nutzertexts je Phase. Phase 7 traegt rund zwoelf Dumps;
#: 240.000 Zeichen sind grob 80.000 Token und passen ins Opus-Fenster.
#: ANNAHME: ungemessen -- ``nutzertext`` sagt im Text, wenn es gekappt hat,
#: und der BEFUND nennt jede gekappte Phase.
ZEICHEN_MAX = 240_000

KATEGORIEN = ("a", "b", "c", "d")

#: Die Leseanweisung. **Modulkonstante und keine Prompt-Datei**: das ist ein
#: Werkzeug des Audits, kein Bot-Verhalten -- eine Datei unter
#: ``interview_theater/prompts/`` wuerde vom Profil-Lader, vom
#: Platzhalter-Check und vom Dortmund-Schnappschuss mitgezogen.
ANWEISUNG = """You read the actual prompts of a theatre workshop bot and look
for contradictions. You are given, for ONE workshop phase: the bot's UX rules,
a UX rubric, and every prompt the bot really sends in that phase (system part
and user part), with 1-based line numbers.

Report findings in four categories:
  a = prompt contradicts a UX rule
  b = prompt contradicts another prompt (or itself)
  c = dead or outdated text (names a button, phase, command or mechanic that
      no longer exists in the prompts you were given)
  d = context structure: how the USER part is built -- chat history (how many
      turns, cut where, who speaks, do bot lines, system lines and transcript
      echoes go along, duplicates), the saved work status (complete?
      unambiguously named? saved vs. only proposed? counters phrased as a
      quota?), summaries (do they duplicate the history? outdated? order and
      weight sensible?), sections and order (context -> status -> history ->
      "Now"), reminder lines in the right place.

Rules you must follow:
- Every finding quotes the prompt VERBATIM, and names the file and the line
  number the quote starts on. A quote that is not literally in the dump is
  worthless; do not paraphrase, do not fix spelling, do not translate.
- At most 10 findings across a, b and c together, and at most 5 for d. Rank by
  how much the group would notice.
- No finding without a concrete proposal. "Improve the wording" is not a
  proposal; "delete line 146, it contradicts line 151" is.
- Judge only what you were given. Do not assume code, buttons or phases that
  are not in these dumps.

Answer with JSON only, no prose around it:
{"befunde": [{"kategorie": "a"|"b"|"c"|"d", "datei": "<dump name without
.txt>", "zeile": <int>, "zitat": "<verbatim>", "regel": "<rule or the other
place>", "vorschlag": "<what to change>"}]}
"""

_HINWEIS_RETRY = (
    "Your quote did not appear at the line you named. These findings are "
    "dropped unless you quote the dump verbatim. Here they are again -- give "
    "the same findings with the exact wording from the numbered lines, or "
    "leave them out:\n"
)


def nummeriere(text: str) -> str:
    """1-basierte Zeilennummern vor jede Zeile -- ``N| <zeile>``.

    Dieselbe Zaehlung wie ``pruefe_prompt_dumps.inhaltszeilen``: so zeigt ein
    Befund auf dieselbe Zeile, die der mechanische Pruefer meldet."""
    return "\n".join(
        f"{nummer}| {zeile}"
        for nummer, zeile in enumerate(text.splitlines(), start=1)
    )


def zeilenfenster(text: str, zeile: int, fenster: int = FENSTER_ZEILEN) -> str:
    alle = text.splitlines()
    von = max(0, int(zeile) - 1 - fenster)
    bis = min(len(alle), int(zeile) + fenster)
    return "\n".join(alle[von:bis])


def nutzertext(phase: int, dumps: dict[str, str], regeln: str,
               rubrik: str) -> tuple[str, bool]:
    kopf = [
        f"# UX RULES\n{regeln}",
        f"# UX RUBRIC\n{rubrik}",
        f"# PHASE {phase} -- every prompt the bot sends here",
    ]
    teile = []
    gekappt = False
    rest = ZEICHEN_MAX
    for name in sorted(dumps):
        stueck = f"\n## FILE {name}\n{nummeriere(dumps[name])}\n"
        if len(stueck) > rest:
            gekappt = True
            continue
        rest -= len(stueck)
        teile.append(stueck)
    if gekappt:
        teile.append(
            "\n(NOTE: some dumps of this phase were truncated for length. "
            "Judge only what is above.)\n"
        )
    return "\n".join(kopf + teile), gekappt


def pruefe_befund(befund: dict, dumps: dict[str, str]) -> bool:
    """Steht das Zitat woertlich an der genannten Stelle?

    ``zitat.pruefe`` -- keine zweite Normalisierung. Fehlt die Datei oder die
    Zeile, ist der Befund nicht pruefbar und damit nicht verwendbar."""
    text = dumps.get(str(befund.get("datei") or ""))
    if not text:
        return False
    try:
        zeile = int(befund.get("zeile") or 0)
    except (TypeError, ValueError):
        return False
    if zeile <= 0:
        return False
    wortlaut = str(befund.get("zitat") or "").strip()
    if not wortlaut:
        return False
    return zitat.pruefe(wortlaut, zeilenfenster(text, zeile))


def kappe(befunde: list[dict]) -> list[dict]:
    abc = [b for b in befunde if b.get("kategorie") in ("a", "b", "c")]
    d = [b for b in befunde if b.get("kategorie") == "d"]
    return abc[:KAPPE_ABC] + d[:KAPPE_D]


def lies_phase(klient, phase: int, dumps: dict[str, str], regeln: str,
               rubrik: str) -> tuple[list[dict], list[dict]]:
    """Ein Aufruf, hoechstens ein Retry. Liefert ``(geprueft, unsicher)``."""
    text, _gekappt = nutzertext(phase, dumps, regeln, rubrik)
    antwort = klient.json_objekt(ANWEISUNG, text, art=f"lesung-phase{phase}")
    befunde = list((antwort or {}).get("befunde") or [])
    geprueft = [b for b in befunde if pruefe_befund(b, dumps)]
    offen = [b for b in befunde if b not in geprueft]
    if offen:
        nach = klient.json_objekt(
            ANWEISUNG,
            f"{text}\n\n{_HINWEIS_RETRY}{json.dumps(offen, ensure_ascii=False)}",
            art=f"lesung-phase{phase}-retry",
        )
        zweite = list((nach or {}).get("befunde") or [])
        neu = [b for b in zweite if pruefe_befund(b, dumps)]
        geprueft = geprueft + neu
        # ``unsicher`` ist, was nach dem Retry noch unbelegt ist -- es geht ins
        # Log und nie in den BEFUND. Ein verworfener Befund ist kein
        # schwaecherer Befund, sondern keiner (dieselbe Regel wie bei
        # dramaturgie/beleg.py). KEIN Rueckfall auf das alte ``offen``: wenn
        # der Retry alles auflöst (``zweite`` deckt sich mit ``neu``), ist
        # ``unsicher`` leer -- ein ``or offen`` wuerde hier faelschlich den
        # laengst aufgeloesten Vor-Retry-Befund wieder einsetzen (gemessen,
        # Task 8: genau dieser Fall liess den ersten Testlauf rot werden).
        offen = [b for b in zweite if b not in neu]
    return kappe(geprueft), offen


def _dumps_je_phase(ordner: Path) -> dict[int, dict[str, str]]:
    je_phase: dict[int, dict[str, str]] = {}
    for eintrag in inv.INVENTAR:
        pfad = ordner / f"{eintrag.datei}.txt"
        if not pfad.exists():
            continue
        je_phase.setdefault(eintrag.phase, {})[eintrag.datei] = pfad.read_text(
            encoding="utf-8")
    return je_phase


def main() -> None:
    import argparse

    zerleger = argparse.ArgumentParser(description="Opus-Lesung der Dumps")
    zerleger.add_argument("ordner")
    zerleger.add_argument("--phase", type=int, default=None)
    zerleger.add_argument(
        "--trocken", action="store_true",
        help="nur zaehlen, was gelesen WUERDE -- kein Modellaufruf",
    )
    argumente = zerleger.parse_args()

    ordner = Path(argumente.ordner)
    je_phase = _dumps_je_phase(ordner)
    regeln = REGELN.read_text(encoding="utf-8")
    rubrik = RUBRIK.read_text(encoding="utf-8")
    phasen = ([argumente.phase] if argumente.phase
              else sorted(je_phase))

    if argumente.trocken:
        for phase in phasen:
            text, gekappt = nutzertext(phase, je_phase.get(phase, {}),
                                       regeln, rubrik)
            print(f"phase={phase} dumps={len(je_phase.get(phase, {}))} "
                  f"zeichen={len(text)} gekappt={'ja' if gekappt else 'nein'}")
        return

    from simulation.claude import Claude

    klient = Claude()
    alle: list[dict] = []
    unsicher: list[dict] = []
    try:
        for phase in phasen:
            geprueft, offen = lies_phase(
                klient, phase, je_phase.get(phase, {}), regeln, rubrik)
            for befund in geprueft:
                befund["phase"] = phase
            for befund in offen:
                befund["phase"] = phase
            alle.extend(geprueft)
            unsicher.extend(offen)
            print(f"phase={phase} befunde={len(geprueft)} "
                  f"unsicher={len(offen)}")
    finally:
        klient.schliesse()

    (ordner / "lesung.json").write_text(
        json.dumps(alle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    (ordner / "lesung-unsicher.jsonl").write_text(
        "".join(json.dumps(b, ensure_ascii=False) + "\n" for b in unsicher),
        encoding="utf-8")
    print(f"gesamt: {len(alle)} Befunde, {len(unsicher)} unsicher")


if __name__ == "__main__":
    main()
