# Prompt-Check P34, Runde 2 (05.10.2026, nach den Fixes A1-A7)

Runde 1 bleibt unverändert eine Ebene höher (`../BEFUND.md`, `../mechanik.md`,
`../lesung-phase3.json`, `../lesung-phase4.json`).

## Kommandos

```
uv run --extra dev python -m scripts.erzeuge_prompts_padua_voll docs/prompt-audit/2026-10-05-padua-p34/runde2 --scope p34
uv run --extra dev python -m scripts.pruefe_prompt_dumps docs/prompt-audit/2026-10-05-padua-p34/runde2 --basis - --nach docs/prompt-audit/2026-10-05-padua-p34/runde2/mechanik.md
```

Lesung (einmal, nur der geänderte Phase-3-Dump): Dump allein in einen
Hilfsordner (`--nur 06-gespraech-phase3`), dann
`scripts.pruefe_prompts_lesung <hilfsordner> --phase 3` (trocken: 1 Dump,
74.991 Zeichen, nicht gekappt). **Abgebrochen:** der Retry-Aufruf lieferte
kein gültiges JSON (`ClaudeFehler: Antwort ist kein JSON-Objekt`), es wurde
nichts geschrieben. 2 Opus-Aufrufe verbraucht; nicht wiederholt (Vorgabe:
höchstens eine Lesung). Der Hilfsordner ist nicht eingecheckt (Dublette von
`06-gespraech-phase3.txt`).

## Mechanik gegen Runde 1 (Unterschiede)

- `06-gespraech-phase3`: system 31.040 -> 30.863 Zeichen. Frageregeln: die
  Zeile "Ask first, then suggest -- and only ever ONE question per message"
  ist weg; neu ist die Vorrangregel (Z495) und "After an interview, or between
  two interviews, ask **no question** by" (Z501) -- der Widerspruch aus
  Runde 1 (A4) ist im Dump aufgelöst. Deutsche Reste nur noch die zwei
  deutschen Beispielsätze im Sprechweise-Block (Z529/Z530, wie Runde 1).
- `17-buehnenkarte`: die Abschnittsköpfe sind jetzt englisch (Brainstorm
  transcript so far, Characters, Piece card, Questions, Setting, Story,
  Terms); der deutsche Rest "Begriffe und Fragen (Phase 1-3):" ist weg. Bleibt:
  Z45 "NICHTS" (das Schweigen-Token, gewollt).
- `07-gespraech-phase4`: nutzer +1 Zeichen, sonst gleich.
- Alle übrigen Dumps: Befundzeilen unverändert (236 Zeilen in beiden Läufen).
