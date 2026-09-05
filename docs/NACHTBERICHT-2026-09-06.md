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
