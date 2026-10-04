"""Karte t_4b7df796 (Padua Sprache-Probe, 2026-10-04): ein echter, bezahlter
Modellaufruf, der beweist, dass der englische ``szenenfolge``-Systemprompt
(``ANWEISUNG_FOLGE``) wirklich auf Englisch antwortet, obwohl Setting und
Figuren der Gruppe auf Deutsch stehen -- und dass die deutschen
Figurennamen dabei nicht uebersetzt werden.

Nach demselben Muster wie ``scripts/probe_fragen_ki_sprache.py`` (dort fuer
``fragen_ki_vorschlag``): derselbe lokale Anthropic-Proxy, dasselbe Modell
(``claude-opus-5``), dieselbe Ehrlichkeitspflicht -- schlaegt der Aufruf
fehl, steht der echte Fehler im Markdown, nie ein erfundenes Ergebnis.

Anders als ``fragen_ki._nutzertext`` (rein, kein ``conn``) braucht
``szenenfolge.baue_nutzertext`` eine echte Datenbankverbindung (``_material``
liest Rahmen, Figuren & Co. aus ``szene.py``). Dieses Skript legt dafuer
eine Wegwerf-SQLite-Datenbank an (wie ``tests/conftest.py::conn``), setzt
ein deutsches Setting und zwei deutsche Figurennamen (echte deutsche
Woerter, nicht blosse Vornamen -- "Baecker"/"Koechin" waeren uebersetzbar,
anders als "Mira") und ruft dann den echten Produktionsweg
(``szenenfolge.systemanweisung`` + ``szenenfolge.baue_nutzertext``) auf.

Aufruf:
    python -m scripts.probe_sprache_isolierte_laeufe_2
"""

from __future__ import annotations

import os
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

# IT_WORKSHOP MUSS gesetzt sein, bevor irgendetwas aus
# interview_theater.anweisungen/workshop/sprache geladen wird -- das waehlt
# die englische Prompt-/Textschicht unter interview_theater/sprachen/en/.
os.environ["IT_WORKSHOP"] = "padua-2026"

from interview_theater import anweisungen, db, repo, szenenfolge, workshop  # noqa: E402
from simulation import claude  # noqa: E402

ZIEL = (
    Path(__file__).resolve().parent.parent
    / "docs" / "sprache-isolierte-laeufe-2-probe-2026-10-04.md"
)

CHAT_ID = 1
ANZAHL_SZENEN = 3
RAHMEN = "Ein Hinterhof in Dortmund, Sommer. Die Nachbarschaft trifft sich abends."
FIGUREN = [
    ("Bäcker", "ein schweigsamer Mann, der nachts backt und morgens verschwindet"),
    ("Köchin", "eine laute Frau, die jede Mahlzeit kommentiert"),
]
ERWARTETE_FIGUREN = {name for name, _ in FIGUREN}
ENGLISCHE_STOPWOERTER = ("the", "you", "what", "when", "your", "a ")


def _baue_nutzertext_und_system() -> tuple[str, str, Path]:
    """Exakt die Sequenz der ``padua``-Fixture in
    ``tests/test_sprache_prompts.py`` (workshop.vergiss() + Cache leeren),
    dann eine frische Wegwerf-Datenbank wie ``tests/conftest.py::conn``, mit
    deutschem Setting und zwei deutschen Figuren."""
    workshop.vergiss()
    anweisungen._CACHE.clear()

    tmp_dir = tempfile.mkdtemp(prefix="it_probe_szenenfolge_")
    db_pfad = str(Path(tmp_dir) / "probe.db")
    conn = db.verbinde(db_pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT_ID, "probe-bot", "Probegruppe")
    repo.setze_arbeitsstand(conn, CHAT_ID, "rahmen", RAHMEN)
    for name, beschreibung in FIGUREN:
        repo.setze_figur(conn, CHAT_ID, name, beschreibung)

    system_prompt = szenenfolge.systemanweisung(ANZAHL_SZENEN)
    nutzertext = szenenfolge.baue_nutzertext(conn, CHAT_ID, ANZAHL_SZENEN)
    conn.close()
    return system_prompt, nutzertext, Path(db_pfad)


def _pruefe_englisch(antwort: str) -> tuple[bool, list[str]]:
    tief = antwort.lower()
    gefunden = [wort for wort in ENGLISCHE_STOPWOERTER if wort in tief]
    return len(gefunden) >= 2, gefunden


def _pruefe_figuren(antwort: str) -> tuple[bool, list[str], list[str]]:
    """Jede der beiden deutschen Figuren muss woertlich (mit Umlaut) in der
    Antwort stehen -- nicht als "Baker"/"Cook" oder sonst uebersetzt."""
    gefunden = [name for name in ERWARTETE_FIGUREN if name in antwort]
    uebersetzungen_verdacht = [
        wort for wort in ("Baker", "Cook", "baker", "cook") if wort in antwort
    ]
    bestanden = set(gefunden) == ERWARTETE_FIGUREN
    return bestanden, gefunden, uebersetzungen_verdacht


def _schreibe_erfolg(system_prompt: str, nutzertext: str, antwort: str) -> None:
    englisch_ok, englische_treffer = _pruefe_englisch(antwort)
    figuren_ok, gefundene_figuren, uebersetzungsverdacht = _pruefe_figuren(antwort)

    gesamt_verdikt = "PASS" if englisch_ok and figuren_ok else "FAIL"

    teile = []
    teile.append(
        f"# Sprache isolierter Laeufe (szenenfolge/sprachstil) -- "
        f"echte Modell-Probe ({datetime.now(timezone.utc).date()})\n"
    )
    teile.append(
        "Karte t_4b7df796: ein einziger, echter und bezahlter Aufruf gegen "
        "den lokalen Anthropic-Proxy, der beweist, dass der englische "
        "`szenenfolge`-Systemprompt (`ANWEISUNG_FOLGE`, Padua-Workshop) "
        "tatsaechlich auf Englisch antwortet, obwohl Setting und Figuren "
        "der Gruppe deutsch sind -- OHNE die deutschen Figurennamen zu "
        "uebersetzen. Kein Mock, kein Fake -- die volle rohe Modellantwort "
        "steht unten.\n"
    )
    teile.append(f"**Gesamtverdikt: {gesamt_verdikt}**\n")

    teile.append("## Aufbau des Aufrufs\n")
    teile.append(
        "- `IT_WORKSHOP=padua-2026` gesetzt, DANN `workshop.vergiss()` + "
        "`anweisungen._CACHE.clear()` (exakt die Sequenz der `padua`-Fixture "
        "in `tests/test_sprache_prompts.py`).\n"
    )
    figurenliste = ", ".join(f'"{n}"' for n in ERWARTETE_FIGUREN)
    teile.append(
        "- Eine frische Wegwerf-SQLite-Datenbank angelegt (wie "
        "`tests/conftest.py::conn`), darin `repo.setze_arbeitsstand(conn, "
        f'1, "rahmen", "{RAHMEN}")` und je eine Figur fuer '
        f"{figurenliste} "
        "(`repo.setze_figur`).\n"
    )
    teile.append(
        "- System-Prompt: `interview_theater.szenenfolge.systemanweisung"
        f"({ANZAHL_SZENEN})` -- die echte Produktionsfunktion.\n"
    )
    teile.append(
        "- Nutzertext: `interview_theater.szenenfolge.baue_nutzertext(conn, "
        f"1, {ANZAHL_SZENEN})` -- ebenfalls die echte Produktionsfunktion, "
        "liest `rahmen` und die beiden Figuren aus der Datenbank.\n"
    )
    teile.append(
        "- Modellaufruf: `simulation.claude.Claude().text(system=<Prompt>, "
        "nutzer=<Nutzertext>, art=\"probe_szenenfolge\", max_tokens=2000)` "
        f"gegen `{claude.url()}`, Modell `{claude.modell()}`.\n"
    )

    teile.append("## Der volle System-Prompt (`szenenfolge.systemanweisung`, Padua/Englisch)\n")
    teile.append("```\n" + system_prompt.strip() + "\n```\n")

    teile.append("## Der gebaute Nutzertext (deutsches Setting + deutsche Figuren)\n")
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

    teile.append("## Pruefung 2: deutsche Figurennamen unveraendert (nicht uebersetzt)\n")
    teile.append(
        f"Gesucht wurde der woertliche String (mit Umlaut) fuer jede der beiden "
        f"Figuren {sorted(ERWARTETE_FIGUREN)} -- sowie, als Verdachtsproben, ob "
        "die englischen Entsprechungen \"Baker\"/\"Cook\" stattdessen auftauchen.\n"
    )
    if figuren_ok:
        teile.append(
            f"**PASS** -- beide Figuren woertlich gefunden: "
            f"{', '.join(sorted(gefundene_figuren))}.\n"
        )
    else:
        teile.append(
            f"**FAIL** -- woertlich gefunden: {', '.join(sorted(gefundene_figuren)) or '(keine)'} "
            f"({len(gefundene_figuren)}/2).\n"
        )
    if uebersetzungsverdacht:
        teile.append(
            f"**Verdacht auf Uebersetzung:** gefunden: {', '.join(uebersetzungsverdacht)}\n"
        )
    else:
        teile.append("Keine englische Entsprechung (\"Baker\"/\"Cook\") in der Antwort gefunden.\n")

    ZIEL.write_text("\n".join(teile), encoding="utf-8")
    print(f"Geschrieben: {ZIEL}")
    print(f"Verdikt: {gesamt_verdikt}")


def _schreibe_fehler(system_prompt: str | None, nutzertext: str | None, fehler: BaseException) -> None:
    teile = []
    teile.append(
        f"# Sprache isolierter Laeufe (szenenfolge/sprachstil) -- "
        f"echte Modell-Probe ({datetime.now(timezone.utc).date()})\n"
    )
    teile.append(
        "Karte t_4b7df796: der Versuch eines echten, bezahlten Aufrufs gegen "
        "den lokalen Anthropic-Proxy fuer den englischen `szenenfolge`-"
        "Systemprompt (Padua-Workshop).\n"
    )
    teile.append("**Gesamtverdikt: PROBE FAILED -- kein Ergebnis, kein erfundener Ersatz.**\n")
    teile.append(
        "Diese Datei dokumentiert ehrlich einen fehlgeschlagenen Versuch. Kein "
        "Modellresultat wurde erzeugt oder simuliert -- ein echter Fehler "
        "statt eines plausibel aussehenden, aber erfundenen Erfolgs.\n"
    )

    if system_prompt is not None:
        teile.append("## Der volle System-Prompt (`szenenfolge.systemanweisung`, Padua/Englisch)\n")
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
        system_prompt, nutzertext, _db_pfad = _baue_nutzertext_und_system()
        klient = claude.Claude()
        try:
            antwort = klient.text(
                system=system_prompt,
                nutzer=nutzertext,
                art="probe_szenenfolge",
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
