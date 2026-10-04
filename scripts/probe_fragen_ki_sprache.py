"""Task 6 (Padua Phasen-Sprache-Probe, 2026-10-04): ein echter, bezahlter
Modellaufruf, der beweist, dass der englische ``fragen_ki_vorschlag``-Prompt
wirklich auf Englisch antwortet und die deutschen Begriffe dabei nicht
uebersetzt.

Die vier vorangehenden Aufgaben (Tasks 1-5) haben bei vier isolierten
Prompts eine explizite "Write in English"-Zeile ergaenzt und Regressionstests
geschrieben, die nur die STRING-Praesenz dieser Zeile pruefen -- nicht, ob
ein echtes Modell sich wirklich daran haelt. Dieses Skript ist der echte
Beleg, einmal, fuer ``fragen_ki_vorschlag`` (der Prompt, den die Task-Spec
fuer diese Probe nennt).

Kein Mock, kein Fake: ein echter POST gegen den lokalen Anthropic-Proxy via
``simulation.claude.Claude`` -- derselbe Klient, den die Simulationsseite
nutzt. Schlaegt der Aufruf fehl, wird der echte Fehler ins Markdown
geschrieben, niemals ein erfundenes Ergebnis (Ehrlichkeitspflicht aus der
Task-Spec).

Aufruf:
    python -m scripts.probe_fragen_ki_sprache
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

# IT_WORKSHOP MUSS gesetzt sein, bevor irgendetwas aus
# interview_theater.anweisungen/workshop geladen wird -- das waehlt die
# englische Prompt-Ebene unter interview_theater/sprachen/en/prompts/.
os.environ["IT_WORKSHOP"] = "padua-2026"

from interview_theater import anweisungen, workshop  # noqa: E402
from interview_theater import fragen_ki  # noqa: E402
from simulation import claude  # noqa: E402

ZIEL = Path(__file__).resolve().parent.parent / "docs" / "sprache-isolierte-laeufe-probe-2026-10-04.md"

BEGRIFFE = "Apfel, Arbeit, Liebe"
ERWARTETE_BEGRIFFE = {"Apfel", "Arbeit", "Liebe"}
ENGLISCHE_STOPWOERTER = ("the", "you", "what", "when", "your", "a ")


def _lade_system_prompt() -> str:
    # Exakt die Sequenz aus der ``padua``-Fixture in
    # tests/test_sprache_prompts.py: workshop.vergiss() + Cache leeren, DANN
    # erst laden.
    workshop.vergiss()
    anweisungen._CACHE.clear()
    return anweisungen.hole("fragen_ki_vorschlag")


def _pruefe_englisch(antwort: str) -> tuple[bool, list[str]]:
    tief = antwort.lower()
    gefunden = [wort for wort in ENGLISCHE_STOPWOERTER if wort in tief]
    return len(gefunden) >= 2, gefunden


def _pruefe_begriffe(antwort: str) -> tuple[bool, list[str], list[str]]:
    """Jede nicht-leere Zeile wird am ersten ': ' geteilt; der Praefix vor
    dem Doppelpunkt muss (nach Trim) einer der drei deutschen Begriffe sein
    -- unveraendert, nicht uebersetzt."""
    unveraendert: list[str] = []
    verletzungen: list[str] = []
    for zeile in antwort.splitlines():
        zeile = zeile.strip()
        if not zeile or ": " not in zeile:
            continue
        praefix, _, _ = zeile.partition(": ")
        praefix = praefix.strip()
        if praefix in ERWARTETE_BEGRIFFE:
            if praefix not in unveraendert:
                unveraendert.append(praefix)
        else:
            verletzungen.append(zeile)
    alle_gefunden = set(unveraendert) == ERWARTETE_BEGRIFFE
    bestanden = alle_gefunden and not verletzungen
    return bestanden, unveraendert, verletzungen


def _schreibe_erfolg(system_prompt: str, nutzertext: str, antwort: str) -> None:
    englisch_ok, englische_treffer = _pruefe_englisch(antwort)
    begriffe_ok, unveraendert, verletzungen = _pruefe_begriffe(antwort)

    gesamt_verdikt = "PASS" if englisch_ok and begriffe_ok else "FAIL"

    teile = []
    teile.append(f"# Sprache isolierter Laeufe -- echte Modell-Probe ({datetime.now(timezone.utc).date()})\n")
    teile.append(
        "Task 6 der SDD-Reihe \"Sprache isolierter Laeufe\": ein einziger, "
        "echter und bezahlter Aufruf gegen den lokalen Anthropic-Proxy, der "
        "beweist, dass der englische `fragen_ki_vorschlag`-Prompt (Padua-"
        "Workshop) tatsaechlich auf Englisch antwortet, OHNE die deutschen "
        "Begriffe zu uebersetzen. Kein Mock, kein Fake -- die volle rohe "
        "Modellantwort steht unten.\n"
    )
    teile.append(f"**Gesamtverdikt: {gesamt_verdikt}**\n")

    teile.append("## Aufbau des Aufrufs\n")
    teile.append(
        "- `IT_WORKSHOP=padua-2026` gesetzt, DANN `workshop.vergiss()` + "
        "`anweisungen._CACHE.clear()` + `anweisungen.hole(\"fragen_ki_vorschlag\")` "
        "(exakt die Sequenz der `padua`-Fixture in `tests/test_sprache_prompts.py`).\n"
    )
    teile.append(
        f"- Nutzertext gebaut mit `interview_theater.fragen_ki._nutzertext(\"{BEGRIFFE}\", None)` "
        "-- die echte, bereits isolierte Produktionsfunktion.\n"
    )
    teile.append(
        "- Modellaufruf: `simulation.claude.Claude().text(system=<Prompt>, "
        "nutzer=<Nutzertext>, art=\"probe_fragen_ki\", max_tokens=2000)` gegen "
        f"`{claude.url()}`, Modell `{claude.modell()}`.\n"
    )

    teile.append("## Der volle System-Prompt (`fragen_ki_vorschlag`, Padua/Englisch)\n")
    teile.append("```\n" + system_prompt.strip() + "\n```\n")

    teile.append("## Der gebaute Nutzertext\n")
    teile.append("```\n" + nutzertext.strip() + "\n```\n")

    teile.append("## Die volle, rohe Modellantwort\n")
    teile.append("```\n" + antwort + "\n```\n")

    teile.append("## Pruefung 1: Antwort ueberwiegend englisch\n")
    teile.append(
        f"Gesucht wurden mindestens 2 von {list(ENGLISCHE_STOPWOERTER)} "
        "(klein geschrieben, Teilstring-Suche in der klein geschriebenen Antwort).\n"
    )
    if englisch_ok:
        teile.append(
            f"**PASS** -- gefunden: {', '.join(englische_treffer)} "
            f"({len(englische_treffer)}/{len(ENGLISCHE_STOPWOERTER)} der gesuchten Woerter).\n"
        )
    else:
        teile.append(
            f"**FAIL** -- nur gefunden: {', '.join(englische_treffer) or '(keines)'} "
            f"({len(englische_treffer)}/2 noetig).\n"
        )

    teile.append("## Pruefung 2: Begriffe unveraendert (nicht uebersetzt)\n")
    teile.append(
        "Jede nicht-leere Zeile wurde am ersten `': '` geteilt; der Teil vor "
        f"dem Doppelpunkt muss exakt einer von {sorted(ERWARTETE_BEGRIFFE)} sein "
        "(Apfel/Arbeit/Liebe, NICHT Apple/Work/Love).\n"
    )
    if begriffe_ok:
        teile.append(
            f"**PASS** -- {len(unveraendert)}/3 Begriffe unveraendert gefunden: "
            f"{', '.join(sorted(unveraendert))}.\n"
        )
    else:
        teile.append(
            f"**FAIL** -- unveraendert gefunden: {', '.join(sorted(unveraendert)) or '(keine)'} "
            f"({len(unveraendert)}/3). "
        )
        if verletzungen:
            teile.append(
                "Zeilen, deren Praefix vor dem Doppelpunkt NICHT einer der drei "
                "deutschen Begriffe war:\n```\n" + "\n".join(verletzungen) + "\n```\n"
            )

    ZIEL.write_text("\n".join(teile), encoding="utf-8")
    print(f"Geschrieben: {ZIEL}")
    print(f"Verdikt: {gesamt_verdikt}")


def _schreibe_fehler(system_prompt: str | None, nutzertext: str | None, fehler: BaseException) -> None:
    teile = []
    teile.append(f"# Sprache isolierter Laeufe -- echte Modell-Probe ({datetime.now(timezone.utc).date()})\n")
    teile.append(
        "Task 6 der SDD-Reihe \"Sprache isolierter Laeufe\": der Versuch eines "
        "echten, bezahlten Aufrufs gegen den lokalen Anthropic-Proxy fuer den "
        "englischen `fragen_ki_vorschlag`-Prompt (Padua-Workshop).\n"
    )
    teile.append("**Gesamtverdikt: PROBE FAILED -- kein Ergebnis, kein erfundener Ersatz.**\n")
    teile.append(
        "Diese Datei dokumentiert ehrlich einen fehlgeschlagenen Versuch. Kein "
        "Modellresultat wurde erzeugt oder simuliert -- die Honesty-Pflicht der "
        "Task-Spec verlangt genau das: ein echter Fehler statt eines "
        "plausibel aussehenden, aber erfundenen Erfolgs.\n"
    )

    if system_prompt is not None:
        teile.append("## Der volle System-Prompt (`fragen_ki_vorschlag`, Padua/Englisch)\n")
        teile.append("```\n" + system_prompt.strip() + "\n```\n")
    if nutzertext is not None:
        teile.append("## Der gebaute Nutzertext\n")
        teile.append("```\n" + nutzertext.strip() + "\n```\n")

    teile.append("## Probe failed\n")
    teile.append(f"Fehlertyp: `{type(fehler).__name__}`\n")
    teile.append("Fehlertext:\n```\n" + str(fehler) + "\n```\n")
    teile.append("Vollstaendiger Traceback:\n```\n" + traceback.format_exc() + "\n```\n")

    ZIEL.write_text("\n".join(teile), encoding="utf-8")
    print(f"Geschrieben (Fehlerfall): {ZIEL}")


def main() -> None:
    system_prompt: str | None = None
    nutzertext: str | None = None
    try:
        system_prompt = _lade_system_prompt()
        nutzertext = fragen_ki._nutzertext(BEGRIFFE, None)
        klient = claude.Claude()
        try:
            antwort = klient.text(
                system=system_prompt,
                nutzer=nutzertext,
                art="probe_fragen_ki",
                max_tokens=2000,
            )
        finally:
            klient.schliesse()
        if not antwort or not antwort.strip():
            raise claude.ClaudeFehler("Leere Antwort vom Modell erhalten (kein Text im Response-Body).")
        _schreibe_erfolg(system_prompt, nutzertext, antwort)
    except BaseException as fehler:  # noqa: BLE001 -- bewusst alles einfangen, ehrlich dokumentieren
        _schreibe_fehler(system_prompt, nutzertext, fehler)
        raise


if __name__ == "__main__":
    main()
