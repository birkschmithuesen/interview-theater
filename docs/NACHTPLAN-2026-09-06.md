# Nachtplan 05./06.09.2026 — Orchestrator-Session (Hermes, Profil birk)

Ziel 07:30: kompletter Zustandsbericht an Birk (Telegram), vier Bots + Web-Unit
laufen auf main mit allen Features, Tests grün, Simulation gelaufen, Flow-Fixes drin.

## Baustellen (Stand 00:45)
| # | Was | Wo | Agent | Stand |
|---|-----|----|-------|-------|
| 1 | Phasen-Umbau 4–8 (Setting→Geschichte→Schärfung→Szenentexte→Durchlauf), Form je Szene bestätigen | main (Hauptbaum, uncommitted) | sa-0-629d103e / deleg_aa1cece7 | läuft, 2 Commits drin |
| 2 | Web-Interface editierbar | /tmp/it-webedit feat/web-edit | Claude Code, FERTIG | 7 Commits, E2E 13 grün; muss an Phasen-Umbau angepasst werden (Kernthema→Geschichte) |
| 3 | Import-Skript interviews_uebernehmen | /tmp/it-import feat/interviews-uebernehmen | FERTIG | 17 Tests grün |
| 4 | Interaktion (speichern beim 1. Mal, Grundleiste-Wert, proaktiv Phase, Wiederholungsfilter, Fenster chronologisch, Gesprächszug schweigt bei Auftrag, Birks Chat-Feedback) | /tmp/it-interaktion feat/interaktion | sa-0-d996419e / deleg_ef603ddf | wartet auf #1-Commit |
| 5 | Leitfaden (10 Fragen MC → 3 wählen → Sensibilität → Eröffnung → Leitfaden) | /tmp/it-leitfaden feat/interviewleitfaden | sa-0-06575cbd / deleg_24a16fa7 | läuft |
| 6 | Prompt-Audit (Dubletten, 52k→Grenze, Phasenquelle, System-Prompts schlank, Prompt-Tests) | /tmp/it-prompts feat/prompt-audit | sa-0-0405efa9 / deleg_e8c65ed1 | wartet auf #1-Commit |

## Merge-Reihenfolge (jede Stufe: fetch, merge, volle Suite grün, push)
1 → 4 → 6 → 5 → 2 (Web nachziehen: Kernthema-Dropdown raus, Geschichte/Setting rein, E2E erneut) → 3.
Dann: Neustart gruppe1..4 + interview-theater-web EINZELN (nie verkettet), Health: 4 Prozesse, 200 OK, /gesund ok, Web von außen per browser_exec.
Dann: Simulation (scripts.simulation) mit Stimmen aus echtem Material Tag 1 + Testgruppe → Bericht → Flow-Fix-Delegate → nochmal Suite + Neustart.
Dann: Skill interview-theater-live-ops patchen (Import-Skript, neue Phasen, Web-Edit, Neu-schreiben, Emoji), HANDOFF (f) aktualisieren, Bericht schreiben.

## Regeln
- Hauptbaum nur committen, wenn #1 fertig; uncommittete Arbeit anderer NIE verwerfen.
- Vor jedem Neustart: keine Aufnahme läuft, Interviewmodus aus (soap.db + test.db).
- Echte Gruppen (soap.db) nicht anfassen außer Neustart. Testgruppe: test.db.
- Bericht-Datei: docs/NACHTBERICHT-2026-09-06.md fortlaufend schreiben (Cron liest sie 07:15).
- Bei Hänger eines Agenten (>45 min ohne Commit im Worktree): steer, dann stop + selbst fertigstellen.

## Wache
- Cron `it-nacht-wache` alle 30 min: Units, Tests, Branch-Alter, Worktree-Uncommitted → Telegram nur bei Problem.
- Cron `it-nacht-bericht` 07:15 einmalig: Bericht ausliefern (Datei + Kurzfassung).
