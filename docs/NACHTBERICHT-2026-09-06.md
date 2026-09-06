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

## 03:20 — Simulation gelaufen, Flow-Fixes 1–5 live
- `feat/simulation-tag2` gemergt (main = `751fc69`), Suite **1605 grün**. Simulator kann jetzt Knöpfe drücken und fährt alle 8 Phasen; Stimmen PII-frei aus Tag-1-Material (Test gegen echte DB grün: kein Transkript-Wortlaut, keine Namen).
- 4 Läufe (tag1-gruppe1, tag1-gruppe2, regie, gruppe1 nachher): **alle erreichen Phase 8** (gestern max. 6). Nachher-Lauf: Arbeitsstand 5/5, Fragen je Bot-Nachricht 0,87, Phasenwechsel 3/5 proaktiv, 1/16 Schritte gescheitert (vorher 4). Regie-Lauf schrieb 3 Szenen, Form je Szene bestätigt, Exposition 2/2 erfüllt. Kosten Bot 1,64 CHF.
- Flow-Fixes umgesetzt: Begrüßung fordert nicht die eben gesendete Liste; Form ist Vorschlag statt gesetzt (auch Erkenner-Pfad); Phase 8 behauptet nichts Falsches; Leitfaden einmal; 10 Fragen-Knöpfe verschwinden nach der Wahl. Simulator-Bug (USA-Angebot ohne Knöpfe) gefixt.
- Einzel-Neustarts aller vier Bots + Web: aktiv, 200 OK, /gesund ok (je ein 502 von Telegram-getUpdates bei g1/g3 — Telegram-seitig, selbstheilend).
- Offen → läuft als letzter Delegate (feat/sim-rest): Phasenangebot erneuern auf „weiter"/`/stand`/nach Änderung; Bot erfindet keine Szenentexte („zeig Szene N" → Szene-ansehen). Punkt 8 (Meta-Feedback ist kein Inhalt) braucht Korpuslauf → morgen früh, wenn Zeit.
- Skill `interview-theater-live-ops` aktualisiert (§ 2c Stand 06.09., Pitfall Parallel-Agenten/Worktrees/Claude-Code-Allowlist/Wasserzeichen-Falle beim Test-DB-Reset).

## 03:50 — ABSCHLUSS der Nachtschicht (Zustandsbericht für 07:30)

### 1. Läuft alles?
- Units `interview-theater@gruppe1/2/3/4` + `interview-theater-web`: **aktiv**, 4 Bot-Prozesse, nur 200 OK, keine Tracebacks, `/gesund` ok, Dashboard + Gruppenseite von außen geprüft.
- main **`e40cc5e`**, 93 Commits seit gestern Abend, Suite **1630 grün** (1 Skip = Playwright-E2E ohne venv; im Web-Lauf 16 grün).
- Echte Gruppen: Phase 3 · Interviews, Daten unverändert (soap.db auf Schema user_version 2 migriert). Testgruppe: Phase 7, Rahmen „Vier Freundinnen im Nordkiez", Szene 1 neu geplant (Kiosk, Dialog).
- Wache-Crons `it-nacht-wache` (30 min) und `it-nacht-aufwecker` (45 min) haben nichts gemeldet.

### 2. Neu seit gestern Abend
- Acht Phasen „erst erfinden, dann schärfen": 4 Setting & Figuren (ohne Material) → 5 Geschichte (Bogen, Ende, Szenen mit Form-Vorschlag) → 6 Schärfung (Interviews werden auf Szenen/Figuren gemappt, Runden) → 7 Szenentexte → 8 Durchlauf.
- Phasenrahmen im Chat: „▶️ Phase N von 8 · Name" + Einleitung + Checkliste; „✅ … abgeschlossen" + alle Parameter + „Weiter zu …"; `/stand` aus derselben Quelle; Angebot kommt auf „weiter"/`/stand`/nach Änderung wieder.
- Fragen: 10 Vorschläge als Knöpfe → genau 3 → Sensibilitätsprüfung mit Einleitungen → Eröffnung/Abschluss → Leitfaden (`/leitfaden`, Knopf, beim Interviewstart einmal, Web).
- Form je Szene: nur Vorschlag mit Begründung, Gruppe bestätigt per Knopf; Dialog Normalfall, Szene 1 nie Monolog/Lied.
- Interaktion: speichern beim ersten Mal (Notiert-Zeile trägt die Leiste), Grundleiste überschreibt nie still, Wiederholungsfilter, Gesprächs-Bot schweigt bei Aufträgen/Szenenläufen, eine Frage je Nachricht, Systemzeilen kurz, „Bin wieder da" nur nach >30 min mit richtiger Phase.
- Prompts: Kontextfenster chronologisch (20 Nachrichten/30 min), harte Grenze 24 000 Zeichen, Dedupe (jeder Fakt einmal), Rahmenblock 15–18 J./öffentliche Orte, keine Beispiel-Eigennamen, Regie ≤ 20 %, Herkules-Maß fürs Textbuch, Aufgabe der Szene (Exposition/Mitte/Ende), Geschichte als bindende Vorgabe; 21 Prompt-Dumps + 41 Prompt-Tests.
- Szenen: „Neu schreiben" ohne alte Vorlage, chronologisch erzwungen, Vorszenen als Volltext, USA-Knopf startet den Auftrag, `/szene 1` meint Szene 1, Emoji-Arbeitsanzeige, Bot erfindet keine Szenentexte („zeig Szene 2" → echter Text).
- Web: Gruppenseite editierbar (Phase, Begriffe, Fragen, Leitfaden-Felder, Setting, Geschichte, Figuren, Szenenfelder inkl. Form), jede Änderung im Journal `quelle='web'`, Token + Nonce; Dashboard read-only.
- Betrieb: `scripts.interviews_uebernehmen` (Interviews aller Gruppen in eine), Simulator auf 8 Phasen + Knöpfe mit PII-freien Tag-1-Stimmen — alle 4 Läufe erreichen Phase 8 (gestern max. 6).
- Doku: AGENTS.md (7 neue Absätze), HANDOFF (f), Skill `interview-theater-live-ops` § 2c, Analysen `docs/analyse-workshop-tag1-…`, `docs/analyse-interaktion-testgruppe-…`, `docs/prompt-audit/2026-09-06/`, Vault `form-urban-dance.md`.

### 3. Nicht fertig / Risiken
- Erkenner-Prompt unverändert (Korpuslauf ~15 min steht aus): „Meta-Feedback ist kein Inhalt" und `geschichte_setzen` per Sprache fehlen — Knöpfe/Marker decken es.
- Phase 4–8 nur in Testgruppe + Simulation gefahren, nie mit echten Menschen; USA-Frage morgen erstmals live.
- Web-Edit + Chat schreiben aus zwei Prozessen (letzter gewinnt, beides im Journal).
- Zwei 502 von Telegram-getUpdates um 03:12 (g1, g3) — Telegram-seitig, selbstheilend.
- Test-Bot-Reset-Falle (Wasserzeichen) dokumentiert im Skill.

### 4. Birk vor 13:30 prüfen/entscheiden
1. In der Testgruppe Szene 1 „Neu schreiben" (Kiosk-Dialog) und einmal Phase 4→5 durchklicken — die acht Einleitungstexte stehen in `interview_theater/phasentexte.py` (Wortlaut unten), bitte gegenlesen.
2. Klarnamen: darf der Bot Vornamen aus dem Chat ansprechen? (heute ja; 23 % der Bot-Texte Tag 1)
3. Korpuslauf freigeben (`PY -m scripts.pruefe_prompts erkenner --bericht`, 15 min) — dann Erkenner-Prompt für Meta-Feedback/Geschichte.

### 5. Interviews zusammenführen (wenn nur eine Gruppe weitermacht)
1. Alle Interviews beendet, Interviewmodus aus (Skript verweigert sonst).
2. `set -a; . ./betrieb/gruppe<ziel>.env; set +a; PY -m scripts.interviews_uebernehmen <ziel_chat> <quelle1> <quelle2>` → Zählung prüfen.
3. Dasselbe mit `--ja` → Backup automatisch, Journal + Chat-Zeile „Ab jetzt liegen hier auch Interview 4–9". Kein Neustart nötig.

### Die acht Einleitungstexte (Wortlaut, `phasentexte.py`)
1 Begriffe — „Hier kommt eure Begriffsliste aus dem Plenum zu mir. Ihr schickt sie getippt oder als Sprachnachricht, so wie sie bei euch an der Wand steht. Ich halte sie fest, ordne sie und frage nach, wo ein Begriff noch zu gross ist. Am Ende stehen die Kernbegriffe, mit denen ihr weiterarbeitet."
2 Fragen — „Aus euren Begriffen werden jetzt die Interviewfragen. Ich schlage euch zehn vor, ihr tippt genau drei davon an. Danach schauen wir, welche Frage heikel ist und was ihr vorher dazu sagt, und womit ihr ein Gespraech anfangt und aufhoert. Am Ende habt ihr einen Leitfaden zum Mitnehmen."
3 Interviews — „Jetzt fuehrt ihr die Interviews. Den Leitfaden habt ihr dabei, aufgenommen wird ueber euer Handy: Aufnahme starten, so viele Sprachnachrichten schicken wie noetig, und ich tippe alles mit. Sagt ihr mir, dass ein Interview fertig ist, fasse ich zusammen, was darin steckt."
4 Setting & Figuren — „Ab hier wird erfunden. Ihr denkt euch aus, worin euer Stueck spielt — Ort, Zeit, Anlass — und wer darin vorkommt. Die Interviews bleiben dabei absichtlich zu; sie kommen spaeter dazu und schaerfen, was ihr jetzt baut. Am Ende steht euer Setting und eine Figurenliste, die ihr abgenommen habt."
5 Geschichte — „Jetzt die Geschichte, im Groben: was passiert und wie es ausgeht. Kein Wortlaut, sondern der Bogen — und dazu die Szenenfolge mit Titel, einem Satz, den Figuren und einem Vorschlag fuer die Form. Auch das erfindet ihr frei, ohne Material."
6 Schaerfung — „Jetzt kommen die Interviews zurueck. Ich lege neben jede Szene und jede Figur die Stellen aus euren Aufnahmen, die dazu passen, mit dem woertlichen Zitat. Eure Geschichte aendert sich dadurch nicht, sie wird genauer. Ihr entscheidet Vorschlag fuer Vorschlag und koennt noch eine Runde drehen."
7 Szenentexte — „Jetzt werden die Texte geschrieben, Szene fuer Szene. Zuerst bestaetigt ihr die Form — Dialog, Monolog, Chor, Lied oder Rap —, dann schreibe ich die Szene, und ihr sagt mir, was anders werden soll. So lange, bis sie sitzt. Am Ende steht zu jeder Szene ein Text."
8 Durchlauf — „Alle Szenen stehen. Hier seht ihr euer Textbuch am Stueck, koennt es euch als Datei schicken lassen und einzelne Szenen noch einmal aufmachen. Wir achten auf die Uebergaenge und darauf, was sich beim Sprechen sperrig anfuehlt."

Kosten Nacht: Claude Code (Web) ~$44 API; Delegates und Simulations-Richter über Abo-Proxy; Bot-Simulation 1,64 CHF Infomaniak.

## 08:45 — Szenen-Zusammenfassung/Budget/Chat-Block live (main `2e55239`, 1649 grün)
- Jede Szene liefert `Zusammenfassung:` + `Anders gemacht:` (Journal-Eintrag bei Abweichung); Szenenlauf bekommt den Chat seit der letzten Fassung; Kürzungsleiter älteste Szene → Zusammenfassung … nie Rahmen/Aufgabe/Angaben.
- **Budget gemessen, nicht gesetzt**: echter Szenen-Prompt = 1,9 Zeichen/Token (count_tokens), nicht 3. Claude-Pfad 126 000 Token Eingabe (Fenster 200k − 32k Ausgabe), Infomaniak-Pfad 37 488 (max_total 249 984 − 200k max_tokens). Normalbetrieb ~15 % des Claude-Budgets. Abgeschnittene Antworten (`stop_reason=max_tokens`) sind jetzt Fehler + Vorfall, kein Halbtext.
- Einzel-Neustarts aller vier + Web: aktiv, 200 OK, /gesund ok, Spalte migriert.
- Läuft noch: Opus-Messung (1M + Thinking, Texte fertig, Richter läuft), Kontext-Audit (Fable).
