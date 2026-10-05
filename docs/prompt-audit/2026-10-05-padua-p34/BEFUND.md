# Prompt-Check Padua, Phase 3+4 -- BEFUND

Datum: 05.10.2026. Plan: `docs/superpowers/plans/2026-10-05-padua-p34.md`,
Task 6. Branch: `wt/robo-p34` (App-Commit `db47b40`). Profil: `padua-2026`.
Dumps, Mechanik und Lesung entstanden vor dem Simulationslauf; Dump und
Mechanik sind lokal und kostenlos, die Lesung lief ueber den Proxy (Abo).

```
uv run --extra dev python -m scripts.erzeuge_prompts_padua_voll docs/prompt-audit/2026-10-05-padua-p34 --scope p34
uv run --extra dev python -m scripts.pruefe_prompt_dumps docs/prompt-audit/2026-10-05-padua-p34 --basis - --nach docs/prompt-audit/2026-10-05-padua-p34/mechanik.md
uv run --extra dev python -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-p34 --phase 3 --trocken
uv run --extra dev python -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-p34 --phase 3
cp docs/prompt-audit/2026-10-05-padua-p34/lesung.json docs/prompt-audit/2026-10-05-padua-p34/lesung-phase3.json
uv run --extra dev python -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-p34 --phase 4
```

`lesung.json` ist die Lesung Phase 4 (identisch mit `lesung-phase4.json`);
`lesung-unsicher.jsonl` ist leer -- jeder Lesungsbefund liess sich an
Datei:Zeile im Dump festmachen.

## 1. Scope

Zehn Inventareintraege der Phasen 3 und 4 (`--scope p34`):

| Datei | art | Phase | weg / Modell | quelle | system | nutzer |
|---|---|---|---|---|---|---|
| 06-gespraech-phase3 | gespraech | 3 | infomaniak / Kimi-K2.6 | abgefangen | 30874 | 14199 |
| 07-gespraech-phase4 | gespraech | 4 | claude / opus | abgefangen | 36029 | 2609 |
| 10-erkenner-verlauf | erkenner | 4 | infomaniak / gemma-4 | abgefangen | 31460 | 2261 |
| 11-erkenner-aufnahme | erkenner | 3 | infomaniak / gemma-4 | abgefangen | 31460 | 2294 |
| 12-journal | journal | 4 | infomaniak / gemma-4 | abgefangen | 4892 | 3543 |
| 16-verdichter | verdichter | 3 | infomaniak / Kimi-K2.6 | abgefangen | 3204 | 2436 |
| 17-buehnenkarte | brainstorm_karte | 4 | claude / opus | abgefangen | 2168 | 1019 |
| 18-szenenfolge | szenenfolge | 4 | claude / opus | abgefangen | 7531 | 1857 |
| 19-geschichte | geschichte | 4 | claude / opus | gebaut | 10234 | 1203 |
| 20-szenenfelder | szenenfelder | 4 | claude / opus | gebaut | 496 | 2050 |

Phase 3 bleibt auf Infomaniak (Datenschutz), Phase 4 laeuft ueber Opus --
so auch im Simulationslauf beobachtet (`aufruf.modus`).

## 2. Mechanik (`mechanik.md`)

- Groessen: alle zehn `neu` (keine Basis fuer P3/P4).
- Token-Anteil Gespraech: Phase 3 system 10273 / status 246 / verlauf 4321 /
  material 160; Phase 4 system 11991 / status 518 / verlauf 311 / material 37.
- **Deutsche Reste:** echt nur `17-buehnenkarte.txt:49ff` -- die
  Nutzertext-Ueberschriften `Begriffe und Fragen (Phase 1-3):`,
  `Stueckkarte:`, `Figuren:`, `Geschichte:`, `Mitschnitt des Brainstormings
  bisher:` sind hartcodiertes Deutsch (`interview_theater/buehnenkarte.py:95-99`,
  Feldnamen aus `repo.py:2424`) in einem sonst englischen Prompt. `NICHTS`
  (Z45) ist das maschinenlesbare Schweige-Wort, kein Rest. Die uebrigen
  Treffer sind Fixture-Zitate (deutsche Interviewtexte in 06/16) oder
  Bezeichner (`wortlaut_aus`, `an_den_bot`).
- **UX-Muster:** `Yes, save` (Knopfbeschriftung) und `ask whether` in
  `system.md`; `how many scenes` in 07 Z510 und 10 Z202 -- alle in geteilten
  Systemtexten, Bewertung siehe Lesung.
- **Verbotene Reste:** `Mira` in 10/11 ist ein Beispielname im
  Erkenner-Systemprompt (Z276-289), kein Gruppendatum.
- **Verlauf Phase 3:** `Bot-Zeilen=0` im Gespraechs-Dump -- die Fixture
  enthaelt fuer Phase 3 nur Gruppenzuege; nicht im Live-Lauf nachgeprueft.

## 3. Lesung Phase 3 (`lesung-phase3.json`, 15 Befunde)

| # | Kat. | Datei:Zeile | Kern | Klasse |
|---|---|---|---|---|
| L3-1 | a | 06:290 | "a suggestion saves itself" (Begriffe/Fragen) widerspricht "Bot proposals are never saved" | B -- Padua-Autosave P1/2 ist Birks Entscheidung, P1/2 bleibt unveraendert |
| L3-2 | a | 11:340 | Erkenner: "worked-out version counts even without a nod" | B -- Erkenner-Prompt, nur mit Korpuslauf FP=0 |
| L3-3 | a | 11:403 | Erkenner beschreibt "Interview 2, part 3"-Etiketten, die es nicht mehr gibt | B -- Erkenner-Prompt (Korpus) |
| L3-4 | a | 06:173 | Szenenzeile mit `— form` im geteilten `system.md` | B -- geteilter Systemprompt (Paralleler Worktree robo-fbl) |
| L3-5 | b | 06:501 vs 480 | Phase 3: "ask almost nothing" und "Ask first, then suggest" im selben Abschnitt | **A** -- deckt sich mit dem Lauf (Kimi stellt in Phase 3 bis zu vier Fragen je Nachricht) |
| L3-6 | b | 06:470 vs 255/262 | "button is under the bot's messages" vs "press the button below is always wrong"; Name "Start interview" | **A** -- deckt sich mit dem Lauf (Bot nennt "Start interview", der Web-Knopf heisst "Record interview") |
| L3-7 | b | 06:546 | Phasenhinweis fragt in Phase 3 nach dem Weitergehen, Phasenregel verbietet Vorschlaege nach dem Interview | B -- ob angeboten wird, ist Produktentscheidung |
| L3-8 | b | 16:5 | Verdichter nennt die Gruppe "Amateur actors" | B -- Wortlaut |
| L3-9 | b | 06:96 | "One question" vs "at most ONE question" | B -- geteilter Systemprompt |
| L3-10 | c | 06:280 | tote Slash-Befehle in der Befehlsliste | B -- geteilter Systemprompt, niedrig |
| L3-11 | d | 06:331 | "repeat nothing from your last three messages", aber keine Bot-Zuege im Verlauf | C -- Fixture ohne Bot-Zuege (siehe 2.) |
| L3-12 | d | 06:536 | Arbeitsstand nennt keine Interviewzahl / keinen Aufnahmestatus | B -- Kontextaufbau |
| L3-13 | d | 06:549 | Journal widerspricht Festlegung | C -- Fixture-Daten |
| L3-14 | d | 06:550 | "[suggested]" steht im Status-Block | B -- Kontextaufbau (`kontext.py`, robo-fbl) |
| L3-15 | d | 11:724 | Erkenner-Aufnahme ohne Progress-Block | B -- Erkenner (Korpus) |

## 4. Lesung Phase 4 (`lesung-phase4.json`, 15 Befunde)

| # | Kat. | Datei:Zeile | Kern | Klasse |
|---|---|---|---|---|
| L4-1 | b | 18:29 | Szenenfolge-Dump traegt "Current phase: 6 · Rewrite" | C -- vermutlich Treiber-Artefakt des Dumps (Kontext aus Phase 6), nicht live nachgeprueft |
| L4-2 | b | 18:19 | Szenenfolge: "form is mandatory" vs "No forms in this phase" | B -- geteilter Szenenfolge-Prompt, in Padua P4 nur auf Anfrage |
| L4-3 | a | 20:59 | Szenenfelder machen eine nur vorgeschlagene Szene 4 bindend | C -- Fixture (Szene 4 steht als Zeile in der DB) |
| L4-4 | b | 20:40 | "already been written and stands" fuer die Szenenfolge | B -- niedrig |
| L4-5 | b | 18:49 | Szenenfolge erwaehnt Schaerfungen/Interviewstellen | B -- geteilter Prompt |
| L4-6 | b | 07:638 | Phasenhinweis-Beispiel "Are more interviews coming" auch in Phase 4 | **A** -- `_PHASENHINWEIS` (`sprachen/en/texte.toml:972`) ist phasenunabhaengig, das Beispiel passt nur zu 3→4 |
| L4-7 | b | 07:150 | "twelve markers", SZENENFOLGE/SZENE fehlen in der Liste | B -- geteilter `system.md:130` |
| L4-8 | b | 18:26, 19:34, 20:17 | Pflicht-Schlussfrage in den Nebenprompts | B -- Wortlaut |
| L4-9 | b | 19:223 | "which scenes" vs "NO scene sequence in this step" | B -- niedrig |
| L4-10 | a | 17:8 | CoThinker-Prompt nennt die Flaeche "stage" | **A** -- Name der App ist CoThinker (UX-Regel 4), zusammen mit den deutschen Ueberschriften aus 2. |
| L4-11 | d | 07:664 | unter "Now:" steht die eigene Bot-Zeile | C -- Treiber/Fixture (live loest eine Gruppennachricht den Zug aus) |
| L4-12 | d | 12:144 | Dubletten im Journal-Auszug | C -- Fixture |
| L4-13 | d | 10:769 | Erkenner-Progress ohne Story/Szenen | B -- Erkenner-Kontext (Korpus) |
| L4-14 | d | 10:743 | Systemzeilen (📌, Noted) im Erkenner-Auszug | B -- Erkenner-Kontext (Korpus) |
| L4-15 | d | 07:648 | abgeschnittene Statuszeile "Changed since -" als "You:"-Zeile | B -- Kontextaufbau (`kontext.py`, robo-fbl) |

## 5. Loecher

- Phase-3-Verlauf ohne Bot-Zuege (Fixture): die Wiederholungsregel
  (06:331) laesst sich mit diesem Dump nicht pruefen.
- 19/20 sind `gebaut`, nicht abgefangen -- ihr Kontext ist nachgestellt.
- Kein Erkenner-Korpuslauf in diesem Task: alle Erkenner-Befunde (L3-2,
  L3-3, L3-15, L4-13, L4-14) bleiben B, bis Birk einen Korpuslauf freigibt.
- Geteilte Prompts (`system.md`, Szenenfolge) werden in diesem Plan nicht
  angefasst (paralleler Worktree `robo-fbl`); Padua-Korrekturen gehoeren in
  neue Dateien `workshop/padua-2026/prompts/phasen/3.md`/`4.md`.
