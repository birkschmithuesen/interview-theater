# Nachtbericht interview-theater — 06.09.2026 (fortlaufend)

Plan: `docs/NACHTPLAN-2026-09-06.md`. Jeder Eintrag mit Uhrzeit; der Aufwecker-Cron
liest die letzte Zeile.

## 00:50 — Start Nachtschicht
- Bots: gruppe1–3 auf `b9148b7` (Format noch drin), gruppe4 (Test) auf `cdb8086`; alle aktiv.
- Fertig auf Branches: feat/web-edit (Web editierbar, E2E 13 grün), feat/interviews-uebernehmen (17 Tests).
- Läuft: Phasen-Umbau (main), Interaktion, Leitfaden, Prompt-Audit (Branches).
- Wache: Cron it-nacht-wache (30 min, still bei ok), it-nacht-aufwecker (45 min), it-nacht-bericht (07:30).

## 01:05 — Merge-Kette Stufe 1–4 durch
- main = `4895c88`: Phasen-Umbau (8 Phasen, Schärfung, Form-Bestätigung je Szene) + Interaktion (`feat/interaktion`, 9 Commits) + Leitfaden (`feat/interviewleitfaden`, 5 Commits, ein Konflikt in knoepfe._speichere gelöst: `_FELD_FUER` + Bestätigungsprüfung) + Import-Skript (`feat/interviews-uebernehmen`). Volle Suite **1420 grün**. AGENTS.md um drei Absätze ergänzt (Haltung, Fragenauswahl/Leitfaden, Neu schreiben/Arbeitsanzeige).
- Web-Branch: origin/main gemergt (Konflikt web_daten gelöst), Claude Code passt jetzt an die 8 Phasen an (Geschichte/Leitfaden editierbar, Kernthema raus, E2E erneut) — läuft.
- Prompt-Audit (`feat/prompt-audit`) läuft noch.
- Bots noch NICHT neu gestartet (gruppe1–3 auf b9148b7, gruppe4 auf cdb8086) — Neustart nach Prompt-Audit + Web.

## 01:20 — Prompt-Audit gemergt, ALLE VIER BOTS auf main
- main = `c47039f` (+ Prompt-Audit `feat/prompt-audit`: harte Nutzertext-Grenze 24 000 Zeichen, Dedupe, 21 Prompt-Dumps, 41 Prompt-Tests). Volle Suite **1459 grün**.
- Neustart einzeln gruppe4 → 1 → 2 → 3 (nichts lief). Alle aktiv, 4 Prozesse, nur 200 OK, keine neuen Tracebacks. soap.db migriert auf user_version 2 (Phasen unverändert 3/3/3); test.db Phase 7 (= Szenentexte, korrekt aus alt 6).
- Web-Dashboard von außen erreichbar (browser_exec, Stand 01:18), noch alter Web-Code (Web-Unit startet nach Web-Merge).
- Offen: Web-Branch (Claude Code passt an 8 Phasen an), dann Simulation.

## 01:35 — Web-Interface live
- `feat/web-edit` gemergt (main = `d209121`), Suite **1524 grün**. Web-Unit neu gestartet, /gesund ok; Gruppenseite Gruppe#1 von außen geprüft (browser_exec): Phase-Dropdown 1–8, 7 Textareas (Begriffe, Fragen, Einleitungen, Eröffnung, Abschluss, Setting, Geschichte), Figuren/Szenen-Formulare, Leitfaden read-only, KEIN Transkript im HTML. Jede Web-Änderung → Journal quelle='web'. Claude-Code-Kosten Web gesamt ~$44.
- Läuft: Phasenrahmen (Eintritts-/Abschlussnachricht je Phase, Jinja-Bewertung) auf feat/phasenrahmen.
- Nächster Schritt: Simulation mit echtem Material (Stimmen aus Tag 1 + Testgruppe), dann Flow-Fix.

## 02:00 — Phasenrahmen live; alle Units auf main `d36db79`
- `feat/phasenrahmen` gemergt: Eintrittsnachricht je Phase („▶️ Phase N von 8 · Name", Einleitung, Checkliste ✅/⬜, Einstiegsknöpfe), Abschlussnachricht („✅ … abgeschlossen" + Parameter + „Weiter zu …" · „Noch etwas aendern"), /stand aus denselben Zeilen. Suite **1571 grün**. Jinja (Fundusbot) geprüft: nicht installiert, Empfehlung „später, unkritische Pfade" in `docs/prompt-audit/2026-09-06/jinja-inspiration.md`.
- Einzel-Neustarts gruppe4/1/2/3 + Web: alle aktiv, 4 Prozesse, 200 OK, /gesund ok, keine Tracebacks.
- Läuft: Simulation (Simulator auf 8 Phasen + Knöpfe, PII-freie Stimmen aus Tag-1-Material, 3–4 Läufe, Flow-Fixes) auf feat/simulation-tag2.
- Danach: Skill `interview-theater-live-ops` + HANDOFF (f) aktualisieren, Bericht finalisieren.
