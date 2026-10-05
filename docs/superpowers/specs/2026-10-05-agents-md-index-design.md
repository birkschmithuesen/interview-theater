# AGENTS.md: vom Archiv zum Index — Design

Stand 2026-10-05 · Auftrag Birk (Padua-Fabrik-Forensik) · Status: beauftragt.

## Problem (gemessen)

- `AGENTS.md` = 255 kB / 3.707 Zeilen. Claude Code lädt sie als
  `instructions`-Anhang in den Controller UND in jeden Subagenten.
  Folge: jeder Subagent startet mit ~131 k Tokens (cothinker mit 14 kB:
  ~20 k). Hochgerechnet ≈ 4,8 von 10,5 Mrd Claude-Code-Tokens der Padua-Woche
  (29.09.–05.10.) ≈ 46 %.
- Gewachsen 147 kB (29.09.) → 251 kB (05.10.); 46 Commits auf die Datei in
  6 Tagen — jede Karte hängt ihre Übergabe an.
- 5 Kapitel doppelt (`Die Fallen` Z. 1270/2170, `Wo SPEC und Code
  auseinanderlaufen` 1366/2278, `Starten und testen` 1395/2325,
  `Weboberfläche` 1505/2438, `Was bewusst fehlt` 1802/3521), ab Z. 2076
  (`## Workshop-Profil`) offenbar ein zweiter, älterer/neuerer Durchlauf.
- Ein großer Teil ist Entscheidungshistorie („Bindende Entwurfsentscheidungen"
  Z. 227–1121 ≈ 900 Zeilen), nicht Arbeitsanweisung.

## Ziel

`AGENTS.md` ≤ 25 kB: was ein Agent in JEDER Aufgabe braucht. Alles andere
nach `docs/agents/` (nur bei Bedarf gelesen), verlinkt aus einem Index.

## Inhalt der neuen AGENTS.md (Richtwert)

1. Ein Absatz: was das Projekt ist, Dortmund eingefroren / Padua aktiv.
2. Aufbau + Modulkarte, verdichtet (eine Zeile je Modul).
3. Harte Invarianten, die beim Ändern brechen (je eine Zeile + Verweis):
   Datenschutz/E8, Sprachschicht `T`, bitgleich-Tests, kein Modellaufruf wo
   Zusagen das verbieten, Kosten, Live-Dienste nie anfassen.
4. Starten und testen: das Suite-Kommando, Marker, e2e-venv, Testinstanz.
5. Die wichtigsten Fallen (Top ~10, je 2 Zeilen), Rest verlinkt.
6. Index `docs/agents/*.md` mit einer Zeile „lies das, wenn du … anfasst".
7. Regel für Folgearbeit: Übergaben/Nachweise einer Karte gehören in
   `docs/agents/<thema>.md` oder `docs/handoffs/`, **nie** an AGENTS.md
   anhängen.
8. Pflicht-Fallen aus der CC-Forensik 05.10. (je eine Zeile im Index):
   - Testkommando: `uv run python -m pytest -q -m "not dortmund" --ignore=tests/e2e`
     (volle Suite ~7,5 min; e2e nur gezielt, eigenes venv `it-webtest`).
   - Eigene Diagnoseskripte immer als `uv run python -m <modul>` starten —
     direkter Dateiaufruf → `ModuleNotFoundError` (Repo-Root fehlt in sys.path).
   - `simulation/claude.py`: `TIMEOUT_S=120` hart — lange Modellaufrufe
     scheitern daran, nicht am Netz.
   - Nur gezielte Tests während der Arbeit, die volle Suite einmal am Ende.

## Umzug

- `docs/agents/entscheidungen.md` — „Bindende Entwurfsentscheidungen"
  (vollständig, unverändert im Wortlaut, nur dedupliziert).
- `docs/agents/dramaturgie-pruefung.md`, `weboberflaeche.md`,
  `workshop-profil.md`, `fallen.md` (vollständig), `spec-abweichungen.md`,
  `was-bewusst-fehlt.md`.
- Doppelte Kapitel: beide Fassungen vergleichen, jüngere/vollständigere
  behalten, Unterschiede im Commit-Text nennen. Nichts ersatzlos löschen —
  jede entfernte Zeile ist in genau einer Zieldatei auffindbar.

## Abnahme

1. `wc -c AGENTS.md` ≤ 25.000.
2. **Verlustfreiheit:** Skript `scripts/pruefe_agents_umzug.py` (deterministisch):
   jeder nicht-leere Absatz der alten Datei (Stand vor dem Umbau, per
   `git show <base>:AGENTS.md`) ist in AGENTS.md oder `docs/agents/**`
   wiederzufinden (normalisierter Textvergleich); Ausnahme nur für die
   Dubletten, als Liste im Bericht. Positivkontrolle: ein absichtlich
   entfernter Absatz macht das Skript rot.
3. Test `tests/test_agents_md_groesse.py`: AGENTS.md > 25.000 Bytes → rot.
   Mutant: Grenze verdoppelt / Datei aufgebläht → Test rot.
4. Alle Verweise „AGENTS.md" in Tests/Code/Doku zeigen auf die Stelle, wo der
   Inhalt jetzt liegt (grep-Liste im Bericht).
5. Volle Suite grün (Kommando + letzte Zeile zitieren).
6. Messung: erster Call eines Claude-Code-Subagenten in diesem Repo nachher
   (aus dem eigenen Lauf-Transkript) — Zielwert < 40 k Tokens.

## Nicht in Scope

Inhaltliche Änderung an Entscheidungen oder Code. Nur Umzug + Verdichtung.
