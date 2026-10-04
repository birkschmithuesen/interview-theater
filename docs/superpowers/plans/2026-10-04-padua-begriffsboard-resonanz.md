# Padua Begriffsboard: eigene Bewertungs-Analyseschicht (Resonanz + fokussierte Analyse) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Kanban: Plan-Karte t_6b16382e, Ausführung auf Karte t_9258d2e9, Branch `wt/t_9258d2e9` (eigener Worktree `.worktrees/t_9258d2e9`, Basis `main` 69a6b0a), danach eine [Review]- und eine [Merge]-Karte nach `main`. Alle Pfade in diesem Plan sind repo-relativ.

**Goal:** Die Rangfolge des Begriffsboards (Phase 1, Padua) bekommt eine zweite, vom Board-Modell unabhängige Bewertung — die im Code gezählte **Resonanz** der Gruppe auf jeden Begriff —, und eine fokussierte **Analyse-Schicht** (ein Modellaufruf für „Wunsch-Stärke" und „Verhörer nach Sinn") wird gebaut und gegen das echte Modell gemessen, aber nicht live geschaltet.

**Architecture:** Zwei neue Module unter `interview_theater/`: `begriffsboard_resonanz.py` (reine Funktionen, kein Modell, keine Datenbank) zählt Zustimmungs- und Ablehnungsphrasen unmittelbar um jede Nennung eines Boardbegriffs; `begriffsboard.sortiert()` rechnet daraus additiv einen Bonus von höchstens ±1 auf `zustimmung`. `begriffsboard_analyse.py` kapselt EINEN strengen Schema-Aufruf (`wunsch` je Begriff + Liste `verhoerer`), den nur ein neues, bezahltes Rauchtest-Skript ruft. Ein Messlauf **vor** dem Einbau entscheidet per Gate, ob die Resonanz überhaupt eingebaut wird.

**Tech Stack:** Python 3.11, Standardbibliothek (`re`, `json`, `statistics`, `argparse`, `tempfile`), `httpx` (nur im Rauchtest), SQLite, pytest.

## Global Constraints

Bindende Architekten-Entscheidungen (Karte, nicht neu verhandeln):

- **D1 Was gemessen wird:** ein deterministisches Signal „Resonanz" ohne Modell. Je Boardbegriff: seine Nennungen im Transkript (casefold, dieselbe Normalisierung wie `begriffsboard.schluessel()`, an Wortgrenzen), danach das Fenster direkt **nach** jeder Nennung (Rest des Segments und Anfang des nächsten, begrenzt auf `FENSTER_NACH` = 120 Zeichen) auf Zustimmungsphrasen („yes", „exactly", „i agree", „agreed", „right,", „that's it", „let's go with", „love that", …) und Ablehnungsphrasen („i don't think", „rather not", „not sure about", „no,", …). Ergebnis je Begriff: ganze Zahl `resonanz` = Zustimmungen minus Ablehnungen, geklemmt auf −3…3. **Warum:** Beleg aus den eigenen Worten der Gruppe, nachrechenbar, kostet nichts, null Latenz, und unabhängig vom Modell, das das Board schreibt — sie kann dessen eine Nebenbei-Zahl `zustimmung` korrigieren, statt sie zu wiederholen. **Ehrliche Grenzen:** keine Sprechertrennung (eine Sprecherin kann zu sich selbst „yes" sagen); STT setzt Satzzeichen unzuverlässig; ein vom Modell umformulierter Begriff steht nicht wörtlich im Transkript (dann `resonanz` = 0, harmlos).
- **D2** Idee 1 (Segmentserie/Prosodie) wird **nicht** gebaut (Begründung im Abschnitt „Abwägung").
- **D3** Idee 3 (eigener fokussierter Modellaufruf) wird als EINE kombinierte Funktion gebaut (D7), aber **nicht** in den Live-Pfad gehängt. Gemessen wird sie als Arm im neuen Rauchtest (`--modell` vergleicht Modelle), mit Trefferquote je Fall sowie gemessenen Token ein/aus und Latenz je Aufruf. Ein zweiter Live-Aufruf ist **Birks** Entscheidung (Geld, Modellwahl) — der Plan endet mit den Zahlen.
- **D4 Einbau additiv und dünn:** neues Modul `interview_theater/begriffsboard_resonanz.py` (reine Funktionen, kein `conn`). `_lauf_einmal` rechnet die Resonanz je validiertem Eintrag gegen das **ganze** Transkript und speichert sie als dünnes, codegeführtes Feld `resonanz` (nur vorhanden, wenn ≠ 0; nie im `SCHEMA`, nie als Anweisung ans Modell). `_eintrag`/`lies` lesen es defensiv. `sortiert()` sortiert nach Status-Rang → `wunsch` → `zustimmung` → `nennungen` → `schluessel`, mit `wunsch` = `zustimmung` + `bonus(resonanz)`, `bonus` ∈ {−1, 0, +1}. Ein Eintrag ohne `resonanz` sortiert exakt wie heute. **Keine UI-Änderung** (Entscheidung dieses Plans: kein `data-resonanz` — es gäbe keinen Leser, und `web._begriffsboard_html` ändert die Parallelkarte t_cb2c4678 gerade; der Raum sieht nur die Reihenfolge). Kein Transkripttext im Boardeintrag (AGENTS.md „Drei Grenzen") — `resonanz` ist eine ganze Zahl.
- **D5 Phrasenlisten** liegen dort, wo das Repo sprachabhängige **Parser-Wortlisten** hält: als Modulkonstante `{"de": …, "en": …}`, gewählt über `sprache.je_sprache` (Muster: `interview_theater/sprachpass.py:157-180`, `interview_theater/befehle.py:75,121`). `sprachen/en/texte.toml` ist für sichtbare Texte (`sprache.Texte`) und bleibt unberührt. Ein `"de"`-Schlüssel ist Pflicht, weil `sprache.je_sprache` (`interview_theater/sprache.py:70-74`) ohne ihn mit `KeyError` scheitert; die DE-Liste ist ungemessen (Dortmund eingefroren, das Board läuft nur mit `diskussion.aktiv`).
- **D6 Messen zuerst, mit Gate.** Neues Skript `scripts/rauchtest_begriffsboard_resonanz.py` (das bestehende `scripts/rauchtest_begriffsboard.py` wird **nicht** geändert), Kopf „Kein Test, laeuft nie automatisch, kostet Geld", EN, Profil `padua-2026`, echter Board-Prompt. Fälle (nur erfunden): (a) Rezenz-Fall aus dem bestehenden Skript, (b) eine Stimme wiederholt X spät und oft ohne Resonanz, die Gruppe einigt sich mit „yes, exactly" auf Y → Y vor X, (c) ein spät ausdrücklich abgelehnter Begriff („no, not the garden") steht nicht auf Platz 1, (d) Negativkontrolle ohne Resonanzphrasen → Reihenfolge mit Resonanz = ohne. Arme: nur Modell (heutiges `sortiert`), Modell + Resonanz (neues `sortiert`), fokussierter Zweitaufruf. 5 Wiederholungen je Fall, harter Deckel vorab gedruckt. **Gate:** besteht der Arm „nur Modell" (b) **und** (c) in ≥ 4/5 Läufen, stoppt die Ausführung vor D4 und meldet „Praemisse widerlegt: Rezenz-Fix reicht fuer diese Faelle" — ein gültiges Ergebnis.
- **D7 Verhörer (Birk, 04.10. ~16:40):** Ranking-Beleg ist zählbar → D1, ohne Modell. Verhörer-Plausibilität ist semantisch → braucht ein Modell. Die einzige modellgestützte Zusatzschicht ist EIN kombinierter Aufruf `analysiere(...)` in `interview_theater/begriffsboard_analyse.py` mit EINEM strengen Schema: (i) je Boardbegriff `wunsch` −2…2, (ii) Liste `verhoerer` aus `{lesart_falsch, lesart_richtig, begruendung_kurz}`, entschieden nach Sinn, nicht nach Zahl. Gegenprobe: eine Nur-Verhörer-Variante desselben Prompts auf den Verhörer-Fällen; billigster Arm zuerst: ein **Prompt-only**-Arm (Board-Prompt mit „Sinn zuerst" statt Mehrheitsregel, **nur** als String im Skript, nie in den Prompt-Dateien). Fälle (e) falsche Lesart häufiger, Kontext stützt die seltene, (f) Kontrolle: häufige Lesart ist auch die richtige → kein Umkippen, (g) Kontrolle: zwei echt verschiedene, ähnlich klingende Begriffe bleiben zwei. Deutsch antwortende Modelle („Wetter") werden akzeptiert wie in `_finde`, der Sprachfund wird **nicht** mitgelöst. Nur Modelle, die in der Umgebung schon konfiguriert sind. **Nicht** Teil dieser Karte: Live-Verdrahtung des Zweitaufrufs, Änderung der committeten Mehrheitsregel in den Prompt-Dateien. Gate Verhörer: besteht „nur Modell" (e) in ≥ 4/5, meldet der Bericht „Verhoerer: Mehrheitsregel scheitert in diesem Fall nicht, kein Zusatzaufruf noetig". Das D6-Gate entscheidet **nur** über D4; `analysiere` und die Messarme werden in jedem Fall gebaut.

Projektregeln (AGENTS.md, Karte):

- **Dortmund eingefroren** (AGENTS.md ganz oben): Abnahme nur Suite grün mit `-m "not dortmund"`, `pruefe_profil padua-2026` grün, `scripts/pruefe_sprache.py padua-2026` ohne Treffer. Keine neuen Profilschalter (das Board läuft ohnehin nur unter `diskussion.aktiv`). Nichts Dortmund-Spezifisches löschen; ein Test, der **nur** wegen Dortmund rot wird, bekommt `@pytest.mark.dortmund`.
- **Parallelkarte t_cb2c4678** (Branch `wt/t_cb2c4678`, Plan `docs/superpowers/plans/2026-10-04-padua-begriffsboard-ranking-schaerfung.md` dort) ändert dieselbe Datei: `validiere(roh, transkript, bisher)`, Schemafeld `vorheriger_begriff`, dünnes Feld `vorgaenger`, FLIP-Ranking in `web_vereint.py`. Ihr Befund gilt hier ebenso: `tests/test_begriffsboard.py:100-104` und `:136-143` vergleichen die Eintragsform **wörtlich** mit sieben Schlüsseln → codegeführte Felder sind **dünn** (nur vorhanden, wenn nicht Vorgabe). Solange t_cb2c4678 nicht in `main` ist, bleiben die Eingriffe in `interview_theater/begriffsboard.py` minimal: nur `_eintrag`, `sortiert`, eine Zeile in `_nutzertext` und zwei Zeilen in `_lauf_einmal`; die Logik steht im neuen Modul.
- Branch `wt/t_9258d2e9`, **kein Merge nach main, kein Push** (ein Push auf origin/main ist ≤ 5 min später live). Nie den Haupt-Arbeitsbaum anfassen. Ein Commit je Aufgabe, nur die genannten Dateien `git add <pfad>` (nie `git add -A`; `.suite.log` und `korpus/berichte/*` bleiben ungetrackt). Commit-Nachrichten enden mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Interpreter: `PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`. Suite-Befehl, immer bis zum Ende abgewartet (im Hintergrund starten ist erlaubt, Abbrechen oder Vergessen nicht):
  `$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > .suite.log 2>&1; echo EXIT $?`
- TDD: jede Codeaufgabe zuerst ein roter Test mit genauem Befehl und erwarteter Fehlermeldung, dann grün.
- Nie `.env` oder `betrieb/` lesen. Nur erfundenes Material in Tests und Rauchtestfällen. Prompts: nur Negativbeispiele (AGENTS.md).
- **Der Rauchtest kostet Geld** und läuft genau in Aufgabe 4, mit dem vorab gedruckten Deckel. Zugangsdaten kommen aus der Umgebung wie beim bestehenden Rauchtest und werden nie ausgegeben.
- Code-Bezeichner deutsch wie im Repo, Kommentare mit ae/oe/ue wie im umgebenden Code; die Prompt-Texte des Analyse-Moduls sind englisch (Padua).

```bash
PY=/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3
```

---

## Abwägung (für die Akte — warum genau diese Schicht)

**Ausgangslage, belegt.** `begriffsboard.sortiert()` (`interview_theater/begriffsboard.py:137-144`) ordnet nach Status-Rang → `zustimmung` → `nennungen` → Begriff. `zustimmung` (−2…2) schätzt das Board-Modell im selben Schema-Aufruf nebenbei (`_lauf_einmal`, `interview_theater/begriffsboard.py:337-367`: ein `modellwahl.aufruf_schema`, dann `validiere(..., transkript)`, dann `repo.lege_begriffsboard_an`). Seit 69a6b0a richtet der Prompt `zustimmung` auf „Rezenz statt Häufigkeit" aus (`interview_theater/sprachen/en/prompts/begriffsboard.md`, Feld `zustimmung`), verprobt in `scripts/rauchtest_begriffsboard.py::rezenz_statt_haeufigkeit`. Das ist ein einzelnes Modellurteil — und genau dort entsteht der neue Fehlerfall: **was zuletzt und oft gesagt wurde, sieht für diese eine Zahl wie Einigkeit aus**, auch wenn es eine einzelne Stimme war, während die Gruppe sich vorher ausdrücklich auf etwas anderes geeinigt hat (Fall b).

**Idee 2 (Konsens-Phrasen) wird gebaut — D1.** Was die Gruppe auf eine Nennung *antwortet*, ist der direkteste Beleg, den ein Transkript ohne Sprechertrennung trägt. Zählen kostet nichts, ist bei jedem Lauf gleich, und es ist ein vom Board-Modell **unabhängiger** Zeuge: gleich schlechte Modelllaune kann es nicht zweimal einbringen. Der Bonus ist bewusst klein (±1 auf einer Skala −2…2, danach bleibt `zustimmung` der Gleichstandsbrecher): Resonanz verschiebt um eine Stufe, sie überstimmt das Modell nicht.

**Idee 1 (Segmentserie/Prosodie) wird nicht gebaut — D2.** Das Transkript trägt keine Prosodie (Whisper liefert Text), und „wie viele Segmente in Folge betrafen denselben Begriff" ist ein Häufigkeitsmaß über die Zeit — genau die Größe, die der Rezenz-Fix bewusst abwertet. Eine Serie misst, dass *gesprochen* wurde, nicht, dass *zugestimmt* wurde; in Fall (b) wäre sie ein Argument **für** den falschen Begriff.

**Idee 3 (eigener Analyseaufruf) wird gebaut und gemessen, nicht verdrahtet — D3/D7.** Ein fokussierter Aufruf kann, was keine Wortliste kann: den *Sinn* prüfen. Für das Ranking ist das ein Zusatz zu D1, für Verhörer (Birks Einwand: die häufiger wiederholte, aber inhaltlich falsche Lesart schlägt heute die seltene richtige, weil die Mehrheitsregel im Board-Prompt Kontext nur bei 2:2 entscheiden lässt) ist es die einzige Lösung. **Ein Aufruf statt zwei:** in beiden Fragen ist die Eingabe dasselbe Transkript, und das dominiert die Token (die Boardliste sind ein paar Dutzend Wörter) — zwei getrennte Aufrufe zahlten das Transkript zweimal, hätten zwei Latenzen und zwei Prompt-Präfixe statt eines cachebaren. **Gegenargument:** ein kombinierter Prompt kann den Fokus verdünnen. Das entscheidet nicht dieser Plan, sondern die Messung: Arm E (Nur-Verhörer-Variante desselben Prompts) läuft auf denselben Verhörer-Fällen wie Arm C (kombiniert). **Billigster Arm zuerst:** Arm D (nur der Board-Prompt mit „Sinn zuerst") kostet gar keinen Zusatzaufruf — erreicht er das Gate, braucht es für Verhörer keinen.

**Modellkandidaten (was der Code heute schon ansprechen kann).** Alle Infomaniak-Modelle laufen über denselben Client `llm.LLM.schema(..., modell=...)` (`interview_theater/llm.py:208-257`), dieselbe URL und denselben Schlüssel. Konfiguriert sind zwei: `IT_LLM_MODELL` (`einstellungen.llm_modell`, im Betrieb Kimi K2.6 — das Board-Modell) und `IT_MODELL_ERKENNER` (`einstellungen.erkenner_modell`, Vorgabe `google/gemma-4-31B-it`, `interview_theater/einstellungen.py:76`). Das Skript spricht sie über die Aliase `gespraech` und `erkenner` an. Weitere Modelle mit Preis in `kosten.PREISE_CHF_JE_MIO_TOKEN` (`interview_theater/kosten.py:48-57`: Mistral-Small, Ministral, Qwen, Apertus, Nemotron) wären mit `--modell <name>` erreichbar, werden in dieser Karte aber **nicht** gefahren. ANNAHME: diese Modelle sind unter demselben Schlüssel freigeschaltet — nachzupruefen: Birk, im Infomaniak-Konto, bevor jemand `--modell mistralai/...` startet. Der Claude-Weg (`modellwahl.konversation_ueber_claude`, Abo, 0 CHF) wird nicht gemessen: ANNAHME: Claude ordnet in diesen Fällen mindestens so gut wie Kimi — nachzupruefen: einmal derselbe Rauchtest über den Proxy, falls Birk den Zweitaufruf über Claude erwägt.

**Kosten und Latenz (a-priori, bis Aufgabe 4 die gemessenen Zahlen liefert).** Ein Boardlauf startet frühestens alle `begriffsboard.min_zeichen()` = 600 neue Zeichen (`interview_theater/begriffsboard.py:229-238`) **und** frühestens 90 s nach dem letzten (`brainstorm.VORGABE_MIN_ABSTAND_S`, `interview_theater/brainstorm.py:22`, über `soll_laufen` → `brainstorm.soll_reagieren`). Für eine Diskussion von 45 min mit ANNAHME 780 Zeichen/min (≈ 130 gesprochene Wörter × 6 Zeichen; nachzupruefen: Birk, an den `aufnahme`-Zeilen mit `diskussion = 1` einer echten Padua-Sitzung, Zeichen ÷ Minuten) sind das 35 100 Zeichen → min(58, 30) = **30 Aufrufe**, jeder mit dem Transkript bis dahin (es wächst bis zur Grenze `VORGABE_TRANSKRIPT_ZEICHEN` = 200 000, die hier nicht erreicht wird). Eingabe gesamt ≈ 30 × Systemprompt + 1 170 × (1+…+30) Zeichen ≈ 634 000 Zeichen ≈ 158 000 Token (ANNAHME 0,25 Token je Zeichen für Englisch; das Skript misst den echten Wert aus `aufruf.tatsaechliche_token`). Mit den Preisen aus `kosten.py` (Stand 04.09.2026): ein zweiter Aufruf je Boardlauf kostete auf **gemma** ≈ 0,04 CHF je Diskussion (0,20/0,40 CHF je Mio Token), auf **Kimi** ≈ 0,12 CHF (0,60/3,00). Latenz: der Zweitaufruf läuft wie der Boardlauf im eigenen Thread, niemand wartet darauf; die Bühne zeigt den neuen Stand um die Dauer eines Aufrufs später, wenn er seriell nach dem Boardlauf liefe. Die gemessenen Zahlen ersetzen diese Schätzung in `docs/begriffsboard-resonanz/BERICHT.md` (Aufgabe 4/9).

**Budget des Rauchtests (D7).** Wiederholungen 5. Kimi (`gespraech`): Arm `board` 7 Fälle × 5 = 35, `prompt_nur` 3 × 5 = 15, `analyse` 6 × 5 = 30, `verhoerer` 3 × 5 = 15 → 95. Gemma (`erkenner`): `analyse` 30 + `verhoerer` 15 → 45. Zusammen **140 Aufrufe**. Arm B (Modell + Resonanz) braucht **keinen** Aufruf: er wird aus denselben `board`-Antworten offline gerechnet (Aufgabe 7). **Kartendeckel 200**: 140 plus Luft für genau eine Wiederholung des Gate-Arms (35) nach einem Transportausfall; das Skript zählt alle bisherigen Aufrufe in seiner Rohdatei mit und bricht **vor** dem ersten Aufruf ab, wenn bisher + geplant > 200.

---

## Dateiübersicht

| Datei | Aufgabe | Was |
|---|---|---|
| `interview_theater/begriffsboard_analyse.py` (neu) | 2 | `anweisung`, `nutzertext`, `SCHEMA`, `SCHEMA_VERHOERER`, `schema_fuer`, `art_fuer`, `validiere`, `analysiere` — kein Aufrufer im Live-Pfad |
| `tests/test_begriffsboard_analyse.py` (neu) | 2 | Schema, Prompt, Validierung, Aufruf, „kein Live-Aufrufer" |
| `scripts/rauchtest_begriffsboard_resonanz.py` (neu) | 3 | Fälle a–g, Arme, Deckel, Rohdatei, Auswertung, Hochrechnung, Gates |
| `tests/test_rauchtest_begriffsboard_resonanz.py` (neu) | 3 | alles Reine des Skripts, ohne Netz |
| `docs/begriffsboard-resonanz/BERICHT.md` (neu) | 4, 7, 9 | Zahlen, Gates, Entscheidungsvorlage für Birk |
| `docs/begriffsboard-resonanz/rauchtest-tabellen.md` (neu) | 4, 7 | die vom Skript erzeugten Tabellen (nur Zahlen) |
| `interview_theater/begriffsboard_resonanz.py` (neu) | 5 | `PHRASEN`, `resonanz_je_begriff`, `trage_ein`, `lies_wert`, `bonus`, `wunsch` |
| `tests/test_begriffsboard_resonanz.py` (neu) | 5 | reine Zählung, Fenster, Grenzen, die drei Rauchtest-Transkripte |
| `interview_theater/begriffsboard.py` | 6 | `_eintrag` (dünnes `resonanz`), `sortiert` (Schlüssel `wunsch`), `_nutzertext` (ohne `resonanz`), `_lauf_einmal` (`trage_ein`) |
| `tests/test_begriffsboard_resonanz_lauf.py` (neu) | 6 | Sortierung unverändert ohne Resonanz, mit Resonanz, Lauf speichert, Nutzertext, Web unverändert |
| `AGENTS.md` | 8 | Modultabelle, Schichten, „Wo man anfängt", Übergaben |

**Nicht** angefasst: `scripts/rauchtest_begriffsboard.py`, `interview_theater/prompts/begriffsboard.md`, `interview_theater/sprachen/en/prompts/begriffsboard.md` (die Mehrheitsregel bleibt, wie sie ist), `interview_theater/sprachen/en/texte.toml`, `web.py`, `web_daten.py`, `web_vereint.py`, `db.py`, `repo.py`, `tests/test_begriffsboard.py` (bleibt Zeichen für Zeichen).

---

### Task 0: Vorbedingungen prüfen (kein Code)

**Files:** keine.

**Interfaces:**
- Produces: die Gewissheit, dass 69a6b0a (Rezenz-Fix + `scripts/rauchtest_begriffsboard.py`) im Branch ist; die Entscheidung „t_cb2c4678 schon in main → main mergen" oder „nicht → minimal in `begriffsboard.py` arbeiten"; die Gewissheit, ob Zugangsdaten für Aufgabe 4 in der Umgebung liegen.

- [ ] **Step 1: 69a6b0a ist im Branch**

```bash
git merge-base --is-ancestor 69a6b0a HEAD && echo ok
git show main:interview_theater/sprachen/en/prompts/begriffsboard.md | grep -c RIGHT
git ls-tree main scripts/ | grep -c rauchtest_begriffsboard
```

Expected: `ok`, dann `1`, dann `1`. Fehlt eines: STOPP, Karte blockieren („69a6b0a fehlt im Branch").

- [ ] **Step 2: Parallelkarte t_cb2c4678**

```bash
git log --oneline main | grep -c "t_cb2c4678"
```

Expected (Stand Planung 04.10.2026): `0` → weiter auf dem Stand von `main`, und `interview_theater/begriffsboard.py` wird nur an den in Aufgabe 6 genannten Stellen geändert. Ist die Zahl > 0: zuerst `git status --short` (Expected: leer), dann `git merge --no-edit main` (Expected: kein Konflikt; bei Konflikt `git merge --abort` und Karte mit der Konfliktausgabe blockieren). Nach einem Merge gilt in Aufgabe 6 der Abschnitt „Falls t_cb2c4678 schon gemergt ist".

- [ ] **Step 3: Zugangsdaten für den bezahlten Lauf (ohne sie auszugeben)**

```bash
$PY -c "from interview_theater import einstellungen as e; s = e.laden(); print('zugang', bool(s.llm_url and s.llm_key and s.llm_modell), s.llm_modell, s.erkenner_modell)"
```

Expected: `zugang True <gespraechsmodell> <erkennermodell>`, z. B. `zugang True moonshotai/Kimi-K2.6 google/gemma-4-31B-it`. ANNAHME: die Ausführungsumgebung trägt die `IT_*`-Variablen bereits — nachzupruefen: genau dieser Befehl. Bricht er mit `RuntimeError: Fehlende Umgebungsvariable(n)` ab oder druckt `zugang False`: **nicht** `betrieb/` lesen oder sourcen. Dann laufen die Aufgaben 1–3 und 8–9 normal, Aufgabe 4 wird als „ausstehend: bezahlter Lauf durch Birk, Befehle siehe Aufgabe 4" in `BERICHT.md` vermerkt, und die Aufgaben 5–7 entfallen (ohne Messung kein Einbau — genau der Fehler, den die Karte vermeiden will).

Kein Commit.

---

### Task 1: Ausgangsstand messen (kein Code)

**Files:** keine (`.suite.log` wird nicht committet).

- [ ] **Step 1: Suite bis zum Ende**

```bash
$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > .suite.log 2>&1; echo EXIT $?
tail -3 .suite.log
```

Dauer 5–15 min; im Hintergrund starten erlaubt, auf das Ende warten, nicht abbrechen. Expected: `EXIT 0` und eine Zeile `N passed, M skipped, K deselected …` ohne `failed`. Diese Zeile wörtlich als **Baseline** für den Abschlussbericht notieren. Ist der Baseline-Lauf schon rot: die roten Testnamen notieren (`grep -E "^FAILED" .suite.log`), sie gelten im Abschluss als vorbestehend, und nichts davon wird in dieser Karte repariert.

- [ ] **Step 2: Profil und Sprache**

```bash
$PY -m scripts.pruefe_profil padua-2026; echo EXIT $?
$PY -m scripts.pruefe_sprache padua-2026 > /tmp/t9258_sprache_vorher.log 2>&1; echo EXIT $?; tail -3 /tmp/t9258_sprache_vorher.log
```

Expected: beide `EXIT 0` (`scripts/pruefe_profil.py:389-407` endet mit dem Rückgabewert von `pruefe_namen`; `scripts/pruefe_sprache.py` endet laut Modulkopf „Exit 0 nur ohne Treffer").

Kein Commit.

---

### Task 2: Analyse-Modul `begriffsboard_analyse` (D3/D7, nicht live)

**Files:**
- Create: `interview_theater/begriffsboard_analyse.py`
- Test: `tests/test_begriffsboard_analyse.py`

**Interfaces:**
- Consumes: `begriffsboard.schluessel(text) -> str`, `begriffsboard._ganzzahl(wert) -> int` (`interview_theater/begriffsboard.py:62-77`); `klm.schema(chat_id, system, nutzer, schema, art, modell=None) -> dict` (`interview_theater/llm.py:208`).
- Produces:
  - `TEILE = ("wunsch", "verhoerer")`, `ART = "begriffsboard_analyse"`, `ART_VERHOERER = "begriffsboard_verhoerer"`
  - `anweisung(teile=TEILE) -> str` (nur `TEILE` oder `("verhoerer",)`, sonst `ValueError`)
  - `nutzertext(transkript: str, board: list[dict]) -> str`
  - `SCHEMA`, `SCHEMA_VERHOERER: dict`; `schema_fuer(teile) -> dict`; `art_fuer(teile) -> str`
  - `validiere(roh, transkript: str, board: list[dict]) -> {"wunsch": dict[str, int], "verhoerer": list[dict]}` — `wunsch` nach `begriffsboard.schluessel` des Begriffs
  - `analysiere(klm, transkript, board, *, modell=None, teile=TEILE, chat_id=None) -> dict` (Form wie `validiere`)

- [ ] **Step 1: Failing test schreiben** — `tests/test_begriffsboard_analyse.py`:

```python
"""Karte t_9258d2e9, Aufgabe 2: die fokussierte Analyse-Schicht (D3/D7).
Nicht live -- nur der Rauchtest ruft sie."""

import pathlib
import re

import pytest

from interview_theater import begriffsboard_analyse as analyse

TRANSKRIPT = (
    "The whether in our story should change all the time. First sun, then heavy rain.\n\n"
    "And a storm at the end. The whether gets worse and worse, wind and thunder."
)
BOARD = [{"begriff": "whether", "zitat": "GEHEIMES ZITAT", "begruendung": "GEHEIME BEGRUENDUNG"},
         {"begriff": "Storm"}]


def _alle_objekte(knoten):
    if isinstance(knoten, dict):
        if knoten.get("type") == "object":
            yield knoten
        for wert in knoten.values():
            yield from _alle_objekte(wert)


@pytest.mark.parametrize("schema", [analyse.SCHEMA, analyse.SCHEMA_VERHOERER])
def test_schema_ist_streng(schema):
    objekte = list(_alle_objekte(schema))
    assert objekte
    for objekt in objekte:
        assert objekt["additionalProperties"] is False
        assert set(objekt["required"]) == set(objekt["properties"])


def test_schema_felder():
    assert analyse.SCHEMA["required"] == ["wunsch", "verhoerer"]
    assert analyse.SCHEMA_VERHOERER["required"] == ["verhoerer"]
    paar = analyse.SCHEMA["properties"]["verhoerer"]["items"]["properties"]
    assert set(paar) == {"lesart_falsch", "lesart_richtig", "begruendung_kurz"}


def test_anweisung_kombiniert_und_nur_verhoerer():
    beide = analyse.anweisung()
    nur = analyse.anweisung(("verhoerer",))
    assert "wunsch" in beide and "verhoerer" in beide
    assert "verhoerer" in nur and "wunsch" not in nur
    assert "Not like this:" in beide and "Not like this:" in nur
    assert "not by count" in beide


def test_anweisung_kennt_nur_zwei_varianten():
    with pytest.raises(ValueError):
        analyse.anweisung(("wunsch",))


def test_schema_und_art_je_variante():
    assert analyse.schema_fuer(analyse.TEILE) is analyse.SCHEMA
    assert analyse.schema_fuer(("verhoerer",)) is analyse.SCHEMA_VERHOERER
    assert analyse.art_fuer(analyse.TEILE) == "begriffsboard_analyse"
    assert analyse.art_fuer(("verhoerer",)) == "begriffsboard_verhoerer"


def test_nutzertext_traegt_transkript_und_nur_begriffe():
    text = analyse.nutzertext(TRANSKRIPT, BOARD)
    assert TRANSKRIPT in text
    assert "- whether" in text and "- Storm" in text
    assert "GEHEIM" not in text


def test_validiere_wunsch_nur_fuer_boardbegriffe_und_geklemmt():
    roh = {"wunsch": [{"begriff": "STORM", "wunsch": 9}, {"begriff": "whether", "wunsch": "-5"},
                      {"begriff": "Freiheit", "wunsch": 2}, {"begriff": "storm", "wunsch": -1}, "kaputt"],
           "verhoerer": []}
    assert analyse.validiere(roh, TRANSKRIPT, BOARD)["wunsch"] == {"storm": 2, "whether": -2}


def test_validiere_verhoerer():
    roh = {"wunsch": [], "verhoerer": [
        {"lesart_falsch": " whether ", "lesart_richtig": "weather", "begruendung_kurz": "Rain, sun and storm. " * 30},
        {"lesart_falsch": "whether", "lesart_richtig": "weather", "begruendung_kurz": "doppelt"},
        {"lesart_falsch": "sunshine", "lesart_richtig": "sun", "begruendung_kurz": "steht nicht im Transkript"},
        {"lesart_falsch": "storm", "lesart_richtig": "STORM", "begruendung_kurz": "gleich"},
        {"lesart_falsch": "", "lesart_richtig": "rain", "begruendung_kurz": "leer"},
        "kaputt",
    ]}
    paare = analyse.validiere(roh, TRANSKRIPT, BOARD)["verhoerer"]
    assert [(p["lesart_falsch"], p["lesart_richtig"]) for p in paare] == [("whether", "weather")]
    assert len(paare[0]["begruendung_kurz"]) <= analyse.BEGRUENDUNG_MAX


@pytest.mark.parametrize("roh", [None, "kaputt", [], {"wunsch": "x", "verhoerer": None}])
def test_validiere_kaputt_ist_leer(roh):
    assert analyse.validiere(roh, TRANSKRIPT, BOARD) == {"wunsch": {}, "verhoerer": []}


class _KLM:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art, **zusatz):
        self.aufrufe.append((chat_id, system, nutzer, schema, art, zusatz))
        return self.antwort


def test_analysiere_ruft_einmal_mit_modell_und_validiert():
    klm = _KLM({"wunsch": [{"begriff": "storm", "wunsch": 1}], "verhoerer": []})
    ergebnis = analyse.analysiere(klm, TRANSKRIPT, BOARD, modell="google/gemma-4-31B-it")
    assert ergebnis == {"wunsch": {"storm": 1}, "verhoerer": []}
    ((chat_id, system, nutzer, schema, art, zusatz),) = klm.aufrufe
    assert chat_id is None and schema is analyse.SCHEMA and art == analyse.ART
    assert zusatz == {"modell": "google/gemma-4-31B-it"}
    assert system == analyse.anweisung() and nutzer == analyse.nutzertext(TRANSKRIPT, BOARD)


def test_analysiere_ohne_modell_ohne_zusatz_und_nur_verhoerer():
    klm = _KLM({"verhoerer": []})
    analyse.analysiere(klm, TRANSKRIPT, BOARD, teile=("verhoerer",))
    ((_, _, _, schema, art, zusatz),) = klm.aufrufe
    assert schema is analyse.SCHEMA_VERHOERER and art == analyse.ART_VERHOERER and zusatz == {}


def test_kein_live_aufrufer():
    """D3: nicht in den Live-Pfad gehaengt -- nur der Rauchtest ruft es."""
    paket = pathlib.Path(__file__).resolve().parent.parent / "interview_theater"
    treffer = [p.name for p in paket.rglob("*.py")
               if p.name != "begriffsboard_analyse.py"
               and re.search(r"begriffsboard_analyse", p.read_text(encoding="utf-8"))]
    assert treffer == []
```

- [ ] **Step 2: Test laufen lassen, er muss scheitern**

Run: `$PY -m pytest tests/test_begriffsboard_analyse.py -q -p no:cacheprovider`
Expected: FAIL beim Sammeln mit `ImportError: cannot import name 'begriffsboard_analyse' from 'interview_theater'`.

- [ ] **Step 3: Modul schreiben** — `interview_theater/begriffsboard_analyse.py`:

```python
"""Die fokussierte Analyse-Schicht des Begriffsboards (Karte t_9258d2e9,
04.10.2026) -- EIN Modellaufruf, zwei Fragen:

(i) ``wunsch`` je Boardbegriff (-2..2): wie stark will die Gruppe ihn JETZT?
(ii) ``verhoerer``: welche Woerter sind STT-Verhoerer -- entschieden nach dem
     Sinn des Gespraechs, nicht nach der Zahl der Nennungen (Birks Einwand
     vom 04.10.2026 gegen die Mehrheitsregel im Board-Prompt).

**Nicht im Live-Pfad.** Gerufen wird es nur von
``scripts/rauchtest_begriffsboard_resonanz.py``; ob ein zweiter Live-Aufruf
kommt und mit welchem Modell, entscheidet Birk (Geld, Modellwahl).
``tests/test_begriffsboard_analyse.py::test_kein_live_aufrufer`` haelt das
fest.

**Warum EIN Aufruf fuer beide Fragen.** Die Eingabe ist in beiden Faellen
dasselbe Transkript, und das dominiert die Token. Zwei getrennte Aufrufe
zahlten es zweimal, haetten zwei Latenzen und zwei Prompt-Praefixe. Das
Gegenargument -- ein kombinierter Prompt verduennt den Fokus -- misst der
Rauchtest mit der Variante ``teile=("verhoerer",)``.

**Die Anweisung ist englisch und eine Modul-Konstante** (wie
``sprechweise.ANWEISUNG``): die Schicht ist Padua-only und nicht live. Wird
sie verdrahtet, gehoert sie in die Sprachschicht (deutsche Konstante plus
``sprachen/en/texte.toml``). Kein Zitat und keine Begruendung des Boards im
Nutzertext -- nur Transkript und Begriffe."""

from __future__ import annotations

from interview_theater import begriffsboard

TEILE = ("wunsch", "verhoerer")
_NUR_VERHOERER = ("verhoerer",)
ART = "begriffsboard_analyse"
ART_VERHOERER = "begriffsboard_verhoerer"
WUNSCH_MIN = -2
WUNSCH_MAX = 2
#: Obergrenzen gegen Modellgeschwaetz -- ein Verhoerer ist ein Wort oder
#: eine kurze Wendung, die Begruendung ein Satz.
LESART_MAX = 60
BEGRUENDUNG_MAX = 200

_KOPF = (
    "You analyse a group discussion for a theatre workshop. The group talks "
    "freely about which terms matter to them for their play. The transcript "
    "comes from automatic speech recognition: there are no speaker names, "
    "punctuation is unreliable, and similar-sounding words are sometimes "
    "misheard. You receive the transcript and the list of terms currently on "
    "the group's board -- nothing else.\n\nReturn JSON with these fields:"
)
_TEIL_WUNSCH = (
    "\n\n- wunsch: one object per term on the board list, with begriff (the "
    "term exactly as listed) and wunsch from -2 (the group clearly does not "
    "want it) to 2 (the group clearly wants it). Judge how strongly the group "
    "wants the term at the END of the transcript, by what the others do with "
    "it: picking it up, building on it, agreeing to it -- or doubting, "
    "dropping, replacing it. One voice repeating a term while the others move "
    "on is not agreement."
)
_TEIL_VERHOERER = (
    "\n\n- verhoerer: speech-recognition mishearings. When a word in the "
    "transcript sounds (almost) like another word, and only the other word "
    "makes sense in what the group is talking about, add an object with "
    "lesart_falsch (the spelling as written in the transcript), "
    "lesart_richtig (the spelling that fits the conversation) and "
    "begruendung_kurz (one short sentence naming the context that decides). "
    "Decide by meaning, not by count: a mishearing that occurs more often is "
    "still a mishearing, and a rarer spelling can be the right one. If "
    "nothing was misheard, verhoerer is []."
)
_NICHT_KOPF = "\n\nNot like this:"
_NICHT_WUNSCH = "\n- No entry in wunsch for a term that is not on the board list."
_NICHT_VERHOERER = (
    "\n- No pair in verhoerer whose two spellings do not sound alike."
    "\n- No pair when both words make sense in the conversation and the group "
    "means two different things."
    "\n- No pair decided only because one spelling occurs more often."
)
_NICHT_SCHLUSS = (
    "\n- No description of individual speakers."
    "\n- No text outside the JSON."
)

_TRANSKRIPT_KOPF = "TRANSCRIPT:"
_BOARD_KOPF = "TERMS ON THE BOARD:"

#: Jedes Objekt mit additionalProperties: false und vollem required -- sonst
#: lehnt der Anbieter den erzwungenen Modus ab (wie ``begriffsboard.SCHEMA``).
_VERHOERER_LISTE = {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["lesart_falsch", "lesart_richtig", "begruendung_kurz"],
        "properties": {
            "lesart_falsch": {"type": "string"},
            "lesart_richtig": {"type": "string"},
            "begruendung_kurz": {"type": "string"},
        },
    },
}
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["wunsch", "verhoerer"],
    "properties": {
        "wunsch": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["begriff", "wunsch"],
                "properties": {
                    "begriff": {"type": "string"},
                    "wunsch": {"type": "integer"},
                },
            },
        },
        "verhoerer": _VERHOERER_LISTE,
    },
}
SCHEMA_VERHOERER = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verhoerer"],
    "properties": {"verhoerer": _VERHOERER_LISTE},
}


def _pruefe_teile(teile) -> tuple[str, ...]:
    teile = tuple(teile)
    if teile not in (TEILE, _NUR_VERHOERER):
        raise ValueError(f"teile muss {TEILE} oder {_NUR_VERHOERER} sein, ist: {teile}")
    return teile


def anweisung(teile=TEILE) -> str:
    """Die Systemanweisung -- kombiniert oder nur die Verhoerer-Frage. Die
    Nur-Verhoerer-Fassung ist derselbe Text ohne die Wunsch-Teile."""
    mit_wunsch = _pruefe_teile(teile) == TEILE
    return (
        _KOPF
        + (_TEIL_WUNSCH if mit_wunsch else "")
        + _TEIL_VERHOERER
        + _NICHT_KOPF
        + (_NICHT_WUNSCH if mit_wunsch else "")
        + _NICHT_VERHOERER
        + _NICHT_SCHLUSS
    )


def schema_fuer(teile=TEILE) -> dict:
    return SCHEMA if _pruefe_teile(teile) == TEILE else SCHEMA_VERHOERER


def art_fuer(teile=TEILE) -> str:
    return ART if _pruefe_teile(teile) == TEILE else ART_VERHOERER


def nutzertext(transkript: str, board: list[dict]) -> str:
    """Transkript vorn (waechst nur hinten an, Praefix cache-stabil), dann
    NUR die Begriffe -- kein Zitat, keine Begruendung, keine Zahl."""
    begriffe = [str(e.get("begriff")).strip() for e in board
                if isinstance(e, dict) and str(e.get("begriff") or "").strip()]
    return (f"{_TRANSKRIPT_KOPF}\n{transkript}\n\n{_BOARD_KOPF}\n"
            + "\n".join(f"- {b}" for b in begriffe))


def _einzeilig(wert) -> str:
    return " ".join(str(wert or "").split())


def validiere(roh, transkript: str, board: list[dict]) -> dict:
    """Die Modellantwort in feste Form. ``wunsch`` nur fuer Begriffe der
    Boardliste (Schluessel ``begriffsboard.schluessel``, erste Nennung gilt),
    geklemmt. Ein Verhoerer nur, wenn beide Lesarten nicht leer, kurz und
    verschieden sind und die FALSCHE im Transkript steht (sonst behauptet
    das Modell einen Hoerfehler, den es nie gab)."""
    roh = roh if isinstance(roh, dict) else {}
    erlaubt = {begriffsboard.schluessel(e.get("begriff")) for e in board if isinstance(e, dict)}
    erlaubt.discard("")
    wunsch: dict[str, int] = {}
    for zeile in roh.get("wunsch") if isinstance(roh.get("wunsch"), list) else []:
        if not isinstance(zeile, dict):
            continue
        k = begriffsboard.schluessel(zeile.get("begriff"))
        if k not in erlaubt or k in wunsch:
            continue
        wunsch[k] = min(WUNSCH_MAX, max(WUNSCH_MIN, begriffsboard._ganzzahl(zeile.get("wunsch"))))
    text = begriffsboard.schluessel(transkript)
    verhoerer: list[dict] = []
    gesehen: set[tuple[str, str]] = set()
    for zeile in roh.get("verhoerer") if isinstance(roh.get("verhoerer"), list) else []:
        if not isinstance(zeile, dict):
            continue
        falsch = _einzeilig(zeile.get("lesart_falsch"))
        richtig = _einzeilig(zeile.get("lesart_richtig"))
        kf, kr = begriffsboard.schluessel(falsch), begriffsboard.schluessel(richtig)
        if (not kf or not kr or kf == kr or len(falsch) > LESART_MAX
                or len(richtig) > LESART_MAX or kf not in text or (kf, kr) in gesehen):
            continue
        gesehen.add((kf, kr))
        verhoerer.append({
            "lesart_falsch": falsch,
            "lesart_richtig": richtig,
            "begruendung_kurz": _einzeilig(zeile.get("begruendung_kurz"))[:BEGRUENDUNG_MAX],
        })
    return {"wunsch": wunsch, "verhoerer": verhoerer}


def analysiere(klm, transkript: str, board: list[dict], *, modell: str | None = None,
               teile=TEILE, chat_id: int | None = None) -> dict:
    """EIN Schema-Aufruf, Reasoning aus (``klm.schema`` laesst es auf
    "none"). ``modell`` nur mitgeben, wenn gesetzt -- ein Testdouble darf
    eine schmalere Signatur haben (wie ``modellwahl.aufruf_schema``)."""
    zusatz = {"modell": modell} if modell is not None else {}
    roh = klm.schema(chat_id, anweisung(teile), nutzertext(transkript, board),
                     schema_fuer(teile), art_fuer(teile), **zusatz)
    return validiere(roh, transkript, board)
```

- [ ] **Step 4: Test laufen lassen, er muss bestehen**

Run: `$PY -m pytest tests/test_begriffsboard_analyse.py -q -p no:cacheprovider`
Expected: `16 passed` (12 Testfunktionen, zwei davon parametrisiert mit 2 bzw. 4 Fällen), kein `failed`.

- [ ] **Step 5: Nachbartests unverändert**

Run: `$PY -m pytest tests/test_begriffsboard.py tests/test_begriffsboard_lauf.py -q -p no:cacheprovider -m "not dortmund"`
Expected: `… passed`, kein `failed`.

- [ ] **Step 6: Commit**

```bash
git add interview_theater/begriffsboard_analyse.py tests/test_begriffsboard_analyse.py
git commit -m "Begriffsboard: fokussierte Analyse-Schicht (wunsch + verhoerer), nicht live (t_9258d2e9, Aufgabe 2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Rauchtest-Skript `rauchtest_begriffsboard_resonanz` (offline getestet)

**Files:**
- Create: `scripts/rauchtest_begriffsboard_resonanz.py`
- Test: `tests/test_rauchtest_begriffsboard_resonanz.py`

**Interfaces:**
- Consumes: `begriffsboard.lies`, `begriffsboard.sortiert`, `begriffsboard.schluessel`, `begriffsboard._nutzertext`, `begriffsboard.SCHEMA`, `begriffsboard.VORGABE_MIN_ZEICHEN`, `begriffsboard.VORGABE_TRANSKRIPT_ZEICHEN`; `brainstorm.VORGABE_MIN_ABSTAND_S`; `kosten.PREISE_CHF_JE_MIO_TOKEN`; aus Aufgabe 2 `begriffsboard_analyse.anweisung/nutzertext/schema_fuer/art_fuer/validiere/TEILE`; `scripts.rauchtest_begriffsboard.FAELLE["rezenz_statt_haeufigkeit"]["transkript"]`; optional (ab Aufgabe 5) `begriffsboard_resonanz.trage_ein(eintraege, transkript, *, code)` und `.resonanz_je_begriff(begriffe, transkript, *, code) -> dict[str, int]`.
- Produces (von Aufgabe 4/5/7 benutzt): `FAELLE` (Schlüssel `a_rezenz`, `b_konsens`, `c_abgelehnt`, `d_kontrolle`, `e_verhoerer`, `f_kontrolle_mehrheit`, `g_zwei_begriffe`), `transkript(fall) -> str`, `auftraege(arme, faelle, wiederholungen) -> list[tuple[str, str, int]]`, `prompt_nur(system) -> str`, `bewerte(zeile, resonanz_modul=None) -> dict[str, bool | None]`, `tabelle(zeilen, resonanz_modul=None)`, `gate_ranking(t, modell) -> str`, `gate_verhoerer(t, modell) -> str`, `hochrechnung(...) -> dict`, `bericht(zeilen, resonanz_modul=None) -> str`, `main(argv=None) -> int`; Konstanten `TEXT_PRAEMISSE_WIDERLEGT`, `TEXT_PRAEMISSE_BESTAETIGT`, `TEXT_VERHOERER_REICHT`, `TEXT_VERHOERER_SCHEITERT`.

Arm-Kürzel im Bericht: **A** = `board`, nur Modell (heutiges `sortiert`) · **B** = `board`, Modell + Resonanz (dieselben Antworten, offline) · **C** = `analyse` (beide Fragen) · **D** = `prompt_nur` · **E** = `verhoerer` (Analyse nur Verhörer).

Entscheidungen dieser Aufgabe: Bewertet wird die Boardantwort über `begriffsboard.lies` (Form wie im Betrieb, aber **ohne** Transkriptprüfung) — sonst fiele ein deutsch antwortendes Modell („Ozean") in den Rangfällen durch und der Sprachfund würde als Rangfehler gezählt. Die Analyse-Arme bekommen je Fall eine **feste** Boardliste (`board_analyse`), damit Arm C nicht an der Varianz von Arm A hängt; bei (e) ist das die Liste, die die Mehrheitsregel erzeugen würde (nur „whether"). Begriffe werden an **Wortgrenzen** verglichen („night" steckt nicht in „knight").

- [ ] **Step 1: Failing test schreiben** — `tests/test_rauchtest_begriffsboard_resonanz.py`:

```python
"""Karte t_9258d2e9, Aufgabe 3: alles Reine am bezahlten Rauchtest -- ohne Netz."""

import json
import pathlib
import types

import pytest

from interview_theater import begriffsboard, einstellungen
from scripts import rauchtest_begriffsboard_resonanz as rt

EN_PROMPT = (pathlib.Path(__file__).resolve().parent.parent
             / "interview_theater/sprachen/en/prompts/begriffsboard.md").read_text(encoding="utf-8")


def _e(begriff, zustimmung=0, nennungen=1, status="kandidat"):
    return {"begriff": begriff, "nennungen": nennungen, "zustimmung": zustimmung,
            "begruendung": "", "zitat": "", "doppelbedeutung": "", "status": status}


def _zeile(fall, arm, antwort, modell="m", fehler=None, **mehr):
    basis = {"fall": fall, "arm": arm, "modell": modell, "antwort": antwort, "fehler": fehler,
             "system_zeichen": 3000, "nutzer_zeichen": 1000, "eingabe_token": 1000,
             "ausgabe_token": 200, "dauer_ms": 1500, "kosten_chf": 0.001}
    basis.update(mehr)
    return basis


def test_sieben_faelle_und_ihre_arme():
    assert list(rt.FAELLE) == ["a_rezenz", "b_konsens", "c_abgelehnt", "d_kontrolle",
                               "e_verhoerer", "f_kontrolle_mehrheit", "g_zwei_begriffe"]
    assert all("board" in f["arme"] for f in rt.FAELLE.values())


def test_fall_a_ist_der_bestehende_rezenzfall():
    from scripts.rauchtest_begriffsboard import FAELLE as ALT
    assert rt.transkript("a_rezenz") == ALT["rezenz_statt_haeufigkeit"]["transkript"]


@pytest.mark.parametrize("arm, anzahl", [("board", 35), ("prompt_nur", 15),
                                         ("analyse", 30), ("verhoerer", 15)])
def test_geplante_aufrufe_je_arm(arm, anzahl):
    assert len(rt.auftraege([arm], set(), 5)) == anzahl


def test_unbekannter_arm():
    with pytest.raises(SystemExit):
        rt.auftraege(["quatsch"], set(), 5)


def test_trocken_ruft_nichts(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(einstellungen, "laden", lambda: (_ for _ in ()).throw(AssertionError("Netz!")))
    roh = tmp_path / "roh.jsonl"
    assert rt.main(["--arme", "board,prompt_nur,analyse,verhoerer", "--modell", "gespraech",
                    "--roh", str(roh), "--trocken"]) == 0
    assert "Geplant: 95 bezahlte Aufrufe" in capsys.readouterr().out
    assert not roh.exists()


def test_deckel_bricht_vor_dem_ersten_aufruf_ab(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(einstellungen, "laden", lambda: (_ for _ in ()).throw(AssertionError("Netz!")))
    roh = tmp_path / "roh.jsonl"
    roh.write_text("{}\n" * 170, encoding="utf-8")
    assert rt.main(["--arme", "board", "--modell", "gespraech", "--roh", str(roh)]) == 3
    assert "ABBRUCH" in capsys.readouterr().out


def test_prompt_nur_ersetzt_nur_die_mehrheitsregel():
    variante = rt.prompt_nur(EN_PROMPT)
    assert "Decide by majority" not in variante
    assert rt.VARIANTE_SINN_ZUERST in variante
    assert variante.startswith(EN_PROMPT[:EN_PROMPT.index("Decide by majority")])
    assert variante.endswith(EN_PROMPT[EN_PROMPT.index("Not like this:"):])


def test_prompt_nur_meldet_einen_geaenderten_prompt():
    with pytest.raises(ValueError):
        rt.prompt_nur("You keep the term board.")


def test_eingabe_board_ist_der_produktive_nutzertext():
    system, nutzer, schema, art = rt.eingabe("board", "b_konsens", EN_PROMPT)
    assert system == EN_PROMPT and schema is begriffsboard.SCHEMA
    assert nutzer == begriffsboard._nutzertext(rt.transkript("b_konsens"), [])
    assert art == "rauchtest_resonanz_board"


@pytest.mark.parametrize("reihe, erwartet", [(["ocean", "garden"], True), (["garden", "ocean"], False),
                                             (["Ozean", "Garten"], True), (["ocean"], False)])
def test_pruefe_reihe_rezenz(reihe, erwartet):
    assert rt.pruefe_reihe("a_rezenz", [_e(b) for b in reihe]) is erwartet


@pytest.mark.parametrize("reihe, erwartet", [(["station", "garden"], True), (["garden", "station"], False),
                                             (["station"], True)])
def test_pruefe_reihe_abgelehnt(reihe, erwartet):
    assert rt.pruefe_reihe("c_abgelehnt", [_e(b) for b in reihe]) is erwartet


@pytest.mark.parametrize("fall, begriffe, erwartet", [
    ("e_verhoerer", ["weather", "rain"], True),
    ("e_verhoerer", ["Wetter"], True),
    ("e_verhoerer", ["whether", "weather"], False),
    ("e_verhoerer", ["whether"], False),
    ("f_kontrolle_mehrheit", ["flower", "flour"], True),
    ("f_kontrolle_mehrheit", ["flour"], False),
    ("g_zwei_begriffe", ["knight", "night"], True),
    ("g_zwei_begriffe", ["Ritter", "Nacht"], True),
    ("g_zwei_begriffe", ["knight"], False),
    ("g_zwei_begriffe", ["knight at night"], False),
])
def test_pruefe_board_verhoerer(fall, begriffe, erwartet):
    assert rt.pruefe_board_verhoerer(fall, [_e(b) for b in begriffe]) is erwartet


@pytest.mark.parametrize("fall, paare, erwartet", [
    ("e_verhoerer", [("whether", "weather")], True),
    ("e_verhoerer", [("whether", "Wetter")], True),
    ("e_verhoerer", [], False),
    ("e_verhoerer", [("whether", "weather"), ("weather", "whether")], False),
    ("f_kontrolle_mehrheit", [], True),
    ("f_kontrolle_mehrheit", [("flour", "flower")], True),
    ("f_kontrolle_mehrheit", [("flower", "flour")], False),
    ("g_zwei_begriffe", [], True),
    ("g_zwei_begriffe", [("night", "knight")], False),
    ("g_zwei_begriffe", [("knight", "night")], False),
])
def test_pruefe_verhoerer(fall, paare, erwartet):
    v = [{"lesart_falsch": f, "lesart_richtig": r, "begruendung_kurz": ""} for f, r in paare]
    assert rt.pruefe_verhoerer(fall, v) is erwartet


def test_pruefe_analyse_rangfaelle():
    assert rt.pruefe_analyse("b_konsens", {"wunsch": {"lighthouse": 2, "motorbike": 1}, "verhoerer": []}) is True
    assert rt.pruefe_analyse("b_konsens", {"wunsch": {"lighthouse": 1, "motorbike": 1}, "verhoerer": []}) is False
    assert rt.pruefe_analyse("c_abgelehnt", {"wunsch": {"garden": -1, "station": 1}, "verhoerer": []}) is True
    assert rt.pruefe_analyse("c_abgelehnt", {"wunsch": {"station": 1}, "verhoerer": []}) is False


def test_bewerte_board_ohne_resonanzmodul():
    antwort = {"board": [_e("motorbike", 1, 6), _e("lighthouse", 2, 5)]}
    assert rt.bewerte(_zeile("b_konsens", "board", antwort)) == {"A": True, "B": None}


def test_bewerte_fehler_ist_durchgefallen():
    assert rt.bewerte(_zeile("b_konsens", "board", None, fehler="LLMFehler: x")) == {"A": False, "B": None}
    assert rt.bewerte(_zeile("e_verhoerer", "analyse", None, fehler="x")) == {"C": False}


def test_bewerte_kontrolle_d_ohne_aussage_fuer_a():
    antwort = {"board": [_e("river", 1, 3), _e("bridge", 1, 3)]}
    assert rt.bewerte(_zeile("d_kontrolle", "board", antwort))["A"] is None


def test_bewerte_b_mit_stub_modul():
    stub = types.SimpleNamespace(
        trage_ein=lambda eintraege, transkript, *, code=None: None,
        resonanz_je_begriff=lambda begriffe, transkript, *, code=None: {b.casefold(): 0 for b in begriffe},
    )
    antwort = {"board": [_e("river", 1, 3), _e("bridge", 1, 3)]}
    assert rt.bewerte(_zeile("d_kontrolle", "board", antwort), stub) == {"A": None, "B": True}
    assert rt.bewerte(_zeile("e_verhoerer", "board", {"board": [_e("weather")]}), stub) == {"A": True, "B": None}


def test_bewerte_analyse_validiert_gegen_die_feste_boardliste():
    antwort = {"wunsch": [], "verhoerer": [
        {"lesart_falsch": "whether", "lesart_richtig": "weather", "begruendung_kurz": "rain"}]}
    assert rt.bewerte(_zeile("e_verhoerer", "analyse", antwort)) == {"C": True}
    assert rt.bewerte(_zeile("e_verhoerer", "verhoerer", {"verhoerer": []})) == {"E": False}
    assert rt.bewerte(_zeile("e_verhoerer", "prompt_nur", {"board": [_e("weather")]})) == {"D": True}


def _gatezeilen(ok_b, ok_c, ok_e=5):
    zeilen = []
    for fall, ok in (("b_konsens", ok_b), ("c_abgelehnt", ok_c)):
        gut = {"board": [_e("lighthouse", 2), _e("motorbike", 1)]} if fall == "b_konsens" \
            else {"board": [_e("station", 2), _e("garden", -1)]}
        schlecht = {"board": [_e("motorbike", 2), _e("lighthouse", 1)]} if fall == "b_konsens" \
            else {"board": [_e("garden", 2), _e("station", 1)]}
        zeilen += [_zeile(fall, "board", gut if i < ok else schlecht) for i in range(5)]
    zeilen += [_zeile("e_verhoerer", "board", {"board": [_e("weather" if i < ok_e else "whether")]})
               for i in range(5)]
    return zeilen


def test_gate_ranking_widerlegt_bei_vier_von_fuenf():
    t = rt.tabelle(_gatezeilen(4, 5))
    assert rt.gate_ranking(t, "m") == rt.TEXT_PRAEMISSE_WIDERLEGT


def test_gate_ranking_bestaetigt_bei_drei_von_fuenf():
    t = rt.tabelle(_gatezeilen(5, 3))
    assert rt.gate_ranking(t, "m") == rt.TEXT_PRAEMISSE_BESTAETIGT


def test_gate_verhoerer():
    assert rt.gate_verhoerer(rt.tabelle(_gatezeilen(5, 5, 4)), "m") == rt.TEXT_VERHOERER_REICHT
    assert rt.gate_verhoerer(rt.tabelle(_gatezeilen(5, 5, 2)), "m") == rt.TEXT_VERHOERER_SCHEITERT


def test_hochrechnung_45_minuten():
    h = rt.hochrechnung(system_zeichen=3000, token_je_zeichen=0.25, ausgabe_token=500, preis=(0.60, 3.00))
    assert h["aufrufe"] == 30
    assert h["eingabe_token"] in (158512, 158513)
    assert h["ausgabe_token"] == 15000
    assert h["chf"] == pytest.approx(0.1401, abs=1e-4)
    assert rt.hochrechnung(system_zeichen=3000, token_je_zeichen=0.25, ausgabe_token=500,
                           preis=None)["chf"] is None


def test_bericht_traegt_tabellen_gates_und_keine_transkripte():
    text = rt.bericht(_gatezeilen(5, 5))
    for kopf in ("## Trefferquote", "## Messwerte", "## Hochrechnung", "## Gates"):
        assert kopf in text
    assert rt.TEXT_PRAEMISSE_WIDERLEGT in text
    for fall in rt.FAELLE:
        assert rt.transkript(fall)[:40] not in text


def test_auswerten_ohne_aufruf(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(einstellungen, "laden", lambda: (_ for _ in ()).throw(AssertionError("Netz!")))
    roh = tmp_path / "roh.jsonl"
    roh.write_text("".join(json.dumps(z) + "\n" for z in _gatezeilen(5, 5)), encoding="utf-8")
    ziel = tmp_path / "tabellen.md"
    assert rt.main(["--auswerten", "--roh", str(roh), "--bericht", str(ziel)]) == 0
    assert "## Gates" in ziel.read_text(encoding="utf-8")
```

- [ ] **Step 2: Test laufen lassen, er muss scheitern**

Run: `$PY -m pytest tests/test_rauchtest_begriffsboard_resonanz.py -q -p no:cacheprovider`
Expected: FAIL beim Sammeln mit `ImportError: cannot import name 'rauchtest_begriffsboard_resonanz' from 'scripts'` (oder `ModuleNotFoundError: No module named 'scripts.rauchtest_begriffsboard_resonanz'`).

- [ ] **Step 3: Skript schreiben** — `scripts/rauchtest_begriffsboard_resonanz.py`:

```python
"""Rauchtest der Resonanz- und Analyse-Schicht des Begriffsboards (Karte
t_9258d2e9, Plan docs/superpowers/plans/2026-10-04-padua-begriffsboard-resonanz.md).

**Kein Test, laeuft nie automatisch, kostet Geld.** Braucht echte
Zugangsdaten (IT_LLM_URL, IT_LLM_KEY, IT_LLM_MODELL, ...) in der Umgebung und
Netzzugriff. Seine ``aufruf``-Zeilen landen in einer Wegwerf-Datenbank, nie
in ``IT_DB``.

Sieben erfundene Faelle (EN, Profil padua-2026), vier Aufrufarten:

- ``board``: der echte Board-Prompt -- ausgewertet als Arm A (nur Modell,
  ``sortiert`` ohne Resonanz) UND, ohne weiteren Aufruf, als Arm B (Modell +
  Resonanz), sobald ``interview_theater/begriffsboard_resonanz.py`` existiert.
- ``prompt_nur`` (Arm D): derselbe Prompt, die Mehrheitsregel fuer Verhoerer
  durch "Sinn zuerst" ersetzt -- NUR hier, nie in den Prompt-Dateien.
- ``analyse`` (Arm C): ``begriffsboard_analyse`` mit beiden Fragen.
- ``verhoerer`` (Arm E): ``begriffsboard_analyse`` nur mit der Verhoerer-Frage.

Jeder Aufruf wird eine Zeile in ``--roh`` (JSONL unter korpus/berichte/,
gitignored: dort stehen vollstaendige Modellantworten). ``--auswerten``
rechnet alles daraus, ohne einen Aufruf. Das Kartenbudget ``--deckel``
(Vorgabe 200) zaehlt die Zeilen dort mit: das Skript bricht VOR dem ersten
Aufruf ab, wenn bisher + geplant darueber laegen.

Aufruf:
    python -m scripts.rauchtest_begriffsboard_resonanz --arme board --modell gespraech --trocken
    python -m scripts.rauchtest_begriffsboard_resonanz --arme board,prompt_nur,analyse,verhoerer --modell gespraech
    python -m scripts.rauchtest_begriffsboard_resonanz --arme analyse,verhoerer --modell erkenner
    python -m scripts.rauchtest_begriffsboard_resonanz --auswerten --bericht docs/begriffsboard-resonanz/rauchtest-tabellen.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interview_theater import begriffsboard, brainstorm, kosten  # noqa: E402
from interview_theater import begriffsboard_analyse as analyse  # noqa: E402
from scripts.rauchtest_begriffsboard import FAELLE as _FAELLE_ALT  # noqa: E402

ROH_VORGABE = "korpus/berichte/begriffsboard_resonanz_roh.jsonl"
DECKEL_VORGABE = 200
WIEDERHOLUNGEN_VORGABE = 5
#: 4 von 5 (D6): ab diesem Anteil gilt ein Fall als bestanden.
SCHWELLE = 0.8
ARME = ("board", "prompt_nur", "analyse", "verhoerer")
#: Nur die zwei Modelle, die die Umgebung schon konfiguriert (Plan, D7).
MODELL_ALIAS = {"gespraech": "llm_modell", "erkenner": "erkenner_modell"}

TEXT_PRAEMISSE_WIDERLEGT = "Praemisse widerlegt: Rezenz-Fix reicht fuer diese Faelle"
TEXT_PRAEMISSE_BESTAETIGT = "Praemisse bestaetigt: Arm A scheitert an (b) oder (c) -- D4 (Resonanz) wird gebaut"
TEXT_VERHOERER_REICHT = "Verhoerer: Mehrheitsregel scheitert in diesem Fall nicht, kein Zusatzaufruf noetig"
TEXT_VERHOERER_SCHEITERT = "Verhoerer: Mehrheitsregel scheitert in (e) -- Arme D/C/E entscheiden, Zahlen an Birk"

#: Wortlisten fuer die Pruefung -- englisch UND die deutsche Antwort, die
#: das Modell trotz EN-Prompt manchmal gibt (Sprachfund, NICHT Teil dieser
#: Karte; wie ``_finde`` im bestehenden Rauchtest).
OZEAN, GARTEN = ("ocean", "ozean"), ("garden", "garten")
LEUCHTTURM, MOTORRAD = ("lighthouse", "leuchtturm"), ("motorbike", "motorrad")
BAHNHOF = ("station", "bahnhof")
WETTER, OB = ("weather", "wetter"), ("whether",)
BLUME = ("flower", "blume")
RITTER, NACHT = ("knight", "ritter"), ("night", "nacht")

FAELLE = {
    "a_rezenz": {
        "segmente": [_FAELLE_ALT["rezenz_statt_haeufigkeit"]["transkript"]],
        "arme": {"board", "analyse"},
        "board_analyse": ["garden", "ocean"],
    },
    "b_konsens": {
        "segmente": [
            "What about a lighthouse? A lighthouse at the edge of town, like the one "
            "from the school trip.",
            "Yes, exactly, the lighthouse. I agree, the lighthouse feels like us. "
            "Let's go with the lighthouse.",
            "I still think the motorbike. The motorbike is cool. A motorbike, a loud "
            "motorbike racing down the street. The motorbike again, the motorbike.",
        ],
        "arme": {"board", "analyse"},
        "board_analyse": ["lighthouse", "motorbike"],
    },
    "c_abgelehnt": {
        "segmente": [
            "Maybe the garden. A garden behind the house, with old trees.",
            "The garden could work. And what about the station, the old train "
            "station at night?",
            "Yes, the station. I like that.",
            "No, not the garden. I don't think the garden works for us, it is too quiet.",
        ],
        "arme": {"board", "analyse"},
        "board_analyse": ["garden", "station"],
    },
    "d_kontrolle": {
        "segmente": [
            "We talked about the river and the bridge. The river runs through the old "
            "part of town.",
            "The bridge is where people meet in the evening. The river is loud in spring.",
            "The bridge and the river, both from our neighbourhood.",
        ],
        "arme": {"board"},
        "board_analyse": ["river", "bridge"],
    },
    "e_verhoerer": {
        "segmente": [
            "The whether in our story should change all the time. First sun, then "
            "heavy rain.",
            "And a storm at the end. The whether gets worse and worse, wind and thunder.",
            "The weather is like the mood of the family. When the whether turns, they fight.",
        ],
        "arme": {"board", "prompt_nur", "analyse", "verhoerer"},
        # Was die Mehrheitsregel (3:1) heute auf dem Board liesse.
        "board_analyse": ["whether", "rain", "storm"],
    },
    "f_kontrolle_mehrheit": {
        "segmente": [
            "Flowers everywhere on stage. The flower stall of the grandmother is the "
            "centre of it.",
            "She sells one flower to every customer, a red flower for each person.",
            "At the end she gives her last flour to the boy, the last flower she has.",
        ],
        "arme": {"board", "prompt_nur", "analyse", "verhoerer"},
        "board_analyse": ["flower", "flour", "grandmother"],
    },
    "g_zwei_begriffe": {
        "segmente": [
            "I want a knight in the story, a knight in old armour who is lost in our city.",
            "And everything happens at night. The night is when the city feels different.",
            "So the knight walks through the city at night, and nobody believes him.",
        ],
        "arme": {"board", "prompt_nur", "analyse", "verhoerer"},
        "board_analyse": ["knight", "night", "city"],
    },
}
RANGFAELLE = ("a_rezenz", "b_konsens", "c_abgelehnt")
VERHOERFAELLE = ("e_verhoerer", "f_kontrolle_mehrheit", "g_zwei_begriffe")
OBEN_UNTEN = {"a_rezenz": (OZEAN, GARTEN), "b_konsens": (LEUCHTTURM, MOTORRAD)}

#: Die Mehrheitsregel im EN-Board-Prompt, Anfang und Ende woertlich
#: (``interview_theater/sprachen/en/prompts/begriffsboard.md``).
_MEHRHEIT_ANFANG = "Decide by majority:"
_MEHRHEIT_ENDE = "deletes a real\nterm."
VARIANTE_SINN_ZUERST = (
    "Decide by meaning first: look at what the group is talking about around "
    "each of the two spellings. Keep as ``begriff`` the reading that makes "
    "sense in that conversation, even if the other spelling occurs more often "
    "in the transcript -- a mishearing that repeats is still a mishearing. "
    "Drop the other reading entirely, add both mention counts into the "
    "remaining entry and note the correction briefly in ``begruendung``. Only "
    "when both readings make equal sense, keep the spelling with the higher "
    "count; if the count is tied as well, keep both separate for now rather "
    "than guessing -- a wrong call here deletes a real\nterm."
)

#: Hochrechnung (Plan, Abschnitt "Kosten und Latenz"). ANNAHME: ~130
#: gesprochene Woerter je Minute x ~6 Zeichen.
REFERENZ_MINUTEN = 45
ZEICHEN_JE_MINUTE = 780


def transkript(fall: str) -> str:
    """Wie ``repo.diskussion_transkript``: Segmente mit Leerzeile verbunden."""
    return "\n\n".join(FAELLE[fall]["segmente"])


def auftraege(arme, faelle, wiederholungen: int) -> list[tuple[str, str, int]]:
    for arm in arme:
        if arm not in ARME:
            raise SystemExit(f"Unbekannter Arm: {arm} (erlaubt: {', '.join(ARME)})")
    return [(arm, fall, w) for arm in arme for fall in FAELLE
            if (not faelle or fall in faelle) and arm in FAELLE[fall]["arme"]
            for w in range(1, wiederholungen + 1)]


def prompt_nur(system: str) -> str:
    """Arm D: die Mehrheitsregel durch "Sinn zuerst" ersetzt, sonst Zeichen
    fuer Zeichen der echte Prompt. Fehlt der Anker, ist der Prompt geaendert
    worden -- dann lieber kein Aufruf als ein Vergleich gegen etwas anderes."""
    anfang = system.find(_MEHRHEIT_ANFANG)
    ende = system.find(_MEHRHEIT_ENDE, anfang if anfang >= 0 else 0)
    if anfang < 0 or ende < 0:
        raise ValueError("Mehrheitsregel im Board-Prompt nicht gefunden -- Prompt geaendert?")
    return system[:anfang] + VARIANTE_SINN_ZUERST + system[ende + len(_MEHRHEIT_ENDE):]


def eingabe(arm: str, fall: str, board_prompt: str) -> tuple[str, str, dict, str]:
    """(system, nutzer, schema, art) eines Aufrufs."""
    tr = transkript(fall)
    if arm == "board":
        return board_prompt, begriffsboard._nutzertext(tr, []), begriffsboard.SCHEMA, "rauchtest_resonanz_board"
    if arm == "prompt_nur":
        return (prompt_nur(board_prompt), begriffsboard._nutzertext(tr, []), begriffsboard.SCHEMA,
                "rauchtest_resonanz_prompt_nur")
    teile = analyse.TEILE if arm == "analyse" else ("verhoerer",)
    board = [{"begriff": b} for b in FAELLE[fall]["board_analyse"]]
    return analyse.anweisung(teile), analyse.nutzertext(tr, board), analyse.schema_fuer(teile), analyse.art_fuer(teile)


# -- Pruefung (rein) ----------------------------------------------------------

def _wort(namen, text) -> bool:
    t = str(text or "").casefold()
    return any(re.search(r"(?<!\w)" + re.escape(n.casefold()) + r"(?!\w)", t) for n in namen)


def _indizes(eintraege: list[dict], namen) -> set[int]:
    return {i for i, e in enumerate(eintraege) if _wort(namen, e.get("begriff"))}


def _rang(reihe: list[dict], namen) -> int | None:
    treffer = _indizes(reihe, namen)
    return min(treffer) if treffer else None


def pruefe_reihe(fall: str, reihe: list[dict]) -> bool | None:
    """Rangfaelle (a, b, c) an einer ``sortiert``-Reihe."""
    if fall in OBEN_UNTEN:
        oben, unten = OBEN_UNTEN[fall]
        ro, ru = _rang(reihe, oben), _rang(reihe, unten)
        return ro is not None and ru is not None and ro < ru
    if fall == "c_abgelehnt":
        return bool(reihe) and not _wort(GARTEN, reihe[0].get("begriff"))
    return None


def pruefe_board_verhoerer(fall: str, eintraege: list[dict]) -> bool | None:
    """Verhoerer-Faelle (e, f, g) an einer Boardantwort (Arme A und D)."""
    if fall == "e_verhoerer":
        return bool(_indizes(eintraege, WETTER)) and not _indizes(eintraege, OB)
    if fall == "f_kontrolle_mehrheit":
        return bool(_indizes(eintraege, BLUME))
    if fall == "g_zwei_begriffe":
        return any(i != j for i in _indizes(eintraege, RITTER) for j in _indizes(eintraege, NACHT))
    return None


def pruefe_verhoerer(fall: str, paare: list[dict]) -> bool | None:
    """Verhoerer-Faelle an der ``verhoerer``-Liste (Arme C und E)."""
    if fall == "e_verhoerer":
        return (any(_wort(OB, p["lesart_falsch"]) and _wort(WETTER, p["lesart_richtig"]) for p in paare)
                and not any(_wort(WETTER, p["lesart_falsch"]) for p in paare))
    if fall == "f_kontrolle_mehrheit":
        return not any(_wort(BLUME, p["lesart_falsch"]) for p in paare)
    if fall == "g_zwei_begriffe":
        return not any((_wort(RITTER, p["lesart_falsch"]) and _wort(NACHT, p["lesart_richtig"]))
                       or (_wort(NACHT, p["lesart_falsch"]) and _wort(RITTER, p["lesart_richtig"]))
                       for p in paare)
    return None


def pruefe_analyse(fall: str, ergebnis: dict) -> bool | None:
    """Arm C: Rangfaelle am ``wunsch``, Verhoerer-Faelle an ``verhoerer``."""
    w = ergebnis["wunsch"]
    if fall in OBEN_UNTEN:
        oben, unten = OBEN_UNTEN[fall][0][0], OBEN_UNTEN[fall][1][0]
        return oben in w and unten in w and w[oben] > w[unten]
    if fall == "c_abgelehnt":
        return "garden" in w and "station" in w and w["garden"] < w["station"]
    return pruefe_verhoerer(fall, ergebnis["verhoerer"])


def _ohne_resonanz(eintraege: list[dict]) -> list[dict]:
    return [{k: v for k, v in e.items() if k != "resonanz"} for e in eintraege]


def bewerte(zeile: dict, resonanz_modul=None) -> dict[str, bool | None]:
    """Eine Rohzeile -> {Arm-Kuerzel: bestanden}. ``None`` heisst "ohne
    Aussage" (Kontrolle d fuer Arm A, Arm B ohne Resonanzmodul oder auf den
    Verhoerer-Faellen) und zaehlt nicht in die Quote."""
    fall, arm, antwort = zeile["fall"], zeile["arm"], zeile.get("antwort")
    tr = transkript(fall)
    if arm in ("analyse", "verhoerer"):
        kuerzel = "C" if arm == "analyse" else "E"
        if not isinstance(antwort, dict):
            return {kuerzel: False}
        board = [{"begriff": b} for b in FAELLE[fall]["board_analyse"]]
        ergebnis = analyse.validiere(antwort, tr, board)
        urteil = pruefe_analyse(fall, ergebnis) if arm == "analyse" else pruefe_verhoerer(fall, ergebnis["verhoerer"])
        return {kuerzel: bool(urteil)}
    roh = antwort.get("board") if isinstance(antwort, dict) else None
    eintraege = begriffsboard.lies(json.dumps(roh if isinstance(roh, list) else []))
    if arm == "prompt_nur":
        return {"D": bool(pruefe_board_verhoerer(fall, eintraege)) if antwort is not None else False}
    reihe_a = begriffsboard.sortiert(_ohne_resonanz(eintraege))
    if fall in RANGFAELLE:
        a = bool(pruefe_reihe(fall, reihe_a)) if antwort is not None else False
    elif fall in VERHOERFAELLE:
        a = bool(pruefe_board_verhoerer(fall, eintraege)) if antwort is not None else False
    else:
        a = None
    if resonanz_modul is None or fall in VERHOERFAELLE:
        return {"A": a, "B": None}
    if antwort is None:
        return {"A": a, "B": False}
    mit = _ohne_resonanz(eintraege)
    resonanz_modul.trage_ein(mit, tr, code="en")
    reihe_b = begriffsboard.sortiert(mit)
    if fall in RANGFAELLE:
        b = bool(pruefe_reihe(fall, reihe_b))
    else:  # d_kontrolle: ohne Resonanzphrasen muss die Reihenfolge gleich bleiben
        werte = resonanz_modul.resonanz_je_begriff([e["begriff"] for e in eintraege], tr, code="en")
        b = ([begriffsboard.schluessel(e["begriff"]) for e in reihe_b]
             == [begriffsboard.schluessel(e["begriff"]) for e in reihe_a]
             and all(v == 0 for v in werte.values()))
    return {"A": a, "B": b}


def tabelle(zeilen: list[dict], resonanz_modul=None) -> dict[tuple[str, str, str], list[bool]]:
    t: dict[tuple[str, str, str], list[bool]] = {}
    for zeile in zeilen:
        for kuerzel, urteil in bewerte(zeile, resonanz_modul).items():
            if urteil is not None:
                t.setdefault((kuerzel, zeile["fall"], zeile["modell"]), []).append(bool(urteil))
    return t


def bestanden(t, kuerzel: str, fall: str, modell: str) -> bool:
    liste = t.get((kuerzel, fall, modell), [])
    return len(liste) >= WIEDERHOLUNGEN_VORGABE and sum(liste) >= SCHWELLE * len(liste)


def gate_ranking(t, modell: str) -> str:
    """D6: besteht Arm A (b) UND (c) in >= 4/5, wird D4 nicht gebaut."""
    if bestanden(t, "A", "b_konsens", modell) and bestanden(t, "A", "c_abgelehnt", modell):
        return TEXT_PRAEMISSE_WIDERLEGT
    return TEXT_PRAEMISSE_BESTAETIGT


def gate_verhoerer(t, modell: str) -> str:
    return TEXT_VERHOERER_REICHT if bestanden(t, "A", "e_verhoerer", modell) else TEXT_VERHOERER_SCHEITERT


# -- Messwerte und Hochrechnung -----------------------------------------------

def _mittel(werte) -> float:
    werte = list(werte)
    return statistics.mean(werte) if werte else 0.0


def messwerte(zeilen: list[dict]) -> dict[tuple[str, str], dict]:
    gruppen: dict[tuple[str, str], list[dict]] = {}
    for zeile in zeilen:
        gruppen.setdefault((zeile["arm"], zeile["modell"]), []).append(zeile)
    ergebnis = {}
    for schluessel, zs in gruppen.items():
        mit_token = [z for z in zs if z.get("eingabe_token")]
        ergebnis[schluessel] = {
            "aufrufe": len(zs),
            "fehler": sum(1 for z in zs if z.get("fehler")),
            "eingabe_token": _mittel(z["eingabe_token"] for z in mit_token),
            "ausgabe_token": _mittel(z.get("ausgabe_token") or 0 for z in mit_token),
            "dauer_ms_mittel": _mittel(z.get("dauer_ms") or 0 for z in zs),
            "dauer_ms_max": max((z.get("dauer_ms") or 0 for z in zs), default=0),
            "kosten_chf": sum(z.get("kosten_chf") or 0.0 for z in zs),
            "system_zeichen": _mittel(z.get("system_zeichen") or 0 for z in zs),
            "token_je_zeichen": _mittel(
                z["eingabe_token"] / max(1, (z.get("system_zeichen") or 0) + (z.get("nutzer_zeichen") or 0))
                for z in mit_token),
        }
    return ergebnis


def hochrechnung(*, system_zeichen: float, token_je_zeichen: float, ausgabe_token: float,
                 preis: tuple[float, float] | None, minuten: int = REFERENZ_MINUTEN,
                 zeichen_je_minute: int = ZEICHEN_JE_MINUTE) -> dict:
    """Ein Aufruf je Boardlauf, eine Diskussion von ``minuten``: Laeufe =
    min(Zeichen / 600, Sekunden / 90) (``begriffsboard.VORGABE_MIN_ZEICHEN``,
    ``brainstorm.VORGABE_MIN_ABSTAND_S``), jeder mit dem Transkript bis dahin
    (gedeckelt auf ``VORGABE_TRANSKRIPT_ZEICHEN``). ``preis`` je Mio Token
    (ein/aus) aus ``kosten.PREISE_CHF_JE_MIO_TOKEN``; ohne Preis kein Betrag."""
    zeichen = minuten * zeichen_je_minute
    aufrufe = max(1, min(zeichen // begriffsboard.VORGABE_MIN_ZEICHEN,
                         (minuten * 60) // brainstorm.VORGABE_MIN_ABSTAND_S))
    schritt = zeichen / aufrufe
    eingabe_zeichen = sum(system_zeichen + min(begriffsboard.VORGABE_TRANSKRIPT_ZEICHEN, schritt * k)
                          for k in range(1, aufrufe + 1))
    eingabe_token = eingabe_zeichen * token_je_zeichen
    gesamt_aus = aufrufe * ausgabe_token
    chf = None if preis is None else (eingabe_token * preis[0] + gesamt_aus * preis[1]) / 1_000_000
    return {"aufrufe": int(aufrufe), "eingabe_token": round(eingabe_token),
            "ausgabe_token": round(gesamt_aus), "chf": None if chf is None else round(chf, 4)}


def bericht(zeilen: list[dict], resonanz_modul=None) -> str:
    """Nur Zahlen -- kein Transkript, keine Modellantwort."""
    t = tabelle(zeilen, resonanz_modul)
    m = messwerte(zeilen)
    aus = [
        "# Rauchtest Begriffsboard-Resonanz (Karte t_9258d2e9)", "",
        f"Aufrufe in der Rohdatei: {len(zeilen)} · Resonanzmodul: "
        f"{'vorhanden' if resonanz_modul is not None else 'nicht gebaut'}", "",
        "## Trefferquote je Fall x Arm x Modell", "",
        "Arme: A nur Modell (heutiges sortiert) · B Modell + Resonanz (offline aus denselben "
        "Antworten) · C Analyse beide Fragen · D Board-Prompt 'Sinn zuerst' · E Analyse nur Verhoerer", "",
        "| Fall | Arm | Modell | bestanden |", "|---|---|---|---|",
    ]
    for kuerzel, fall, modell in sorted(t, key=lambda k: (k[1], k[0], k[2])):
        liste = t[(kuerzel, fall, modell)]
        aus.append(f"| {fall} | {kuerzel} | {modell} | {sum(liste)}/{len(liste)} |")
    aus += ["", "## Messwerte je Aufrufart x Modell", "",
            "| Aufruf | Modell | Aufrufe | Fehler | Eingabe-Token Mittel | Ausgabe-Token Mittel "
            "| Latenz ms Mittel / Max | Kosten CHF Summe |",
            "|---|---|---|---|---|---|---|---|"]
    for (arm, modell), w in sorted(m.items()):
        aus.append(f"| {arm} | {modell} | {w['aufrufe']} | {w['fehler']} | {w['eingabe_token']:.0f} "
                   f"| {w['ausgabe_token']:.0f} | {w['dauer_ms_mittel']:.0f} / {w['dauer_ms_max']} "
                   f"| {w['kosten_chf']:.4f} |")
    aus += ["", f"## Hochrechnung: ein Aufruf je Boardlauf, Diskussion von {REFERENZ_MINUTEN} min", "",
            f"ANNAHME {ZEICHEN_JE_MINUTE} Zeichen/min; Token je Zeichen gemessen; Preise "
            f"kosten.PREISE_CHF_JE_MIO_TOKEN (Stand {kosten.PREISE_STAND}).", "",
            "| Aufruf | Modell | Laeufe | Eingabe-Token | Ausgabe-Token | CHF |", "|---|---|---|---|---|---|"]
    for (arm, modell), w in sorted(m.items()):
        h = hochrechnung(system_zeichen=w["system_zeichen"], token_je_zeichen=w["token_je_zeichen"],
                         ausgabe_token=w["ausgabe_token"], preis=kosten.PREISE_CHF_JE_MIO_TOKEN.get(modell))
        chf = "kein Preis" if h["chf"] is None else f"{h['chf']:.4f}"
        aus.append(f"| {arm} | {modell} | {h['aufrufe']} | {h['eingabe_token']} | {h['ausgabe_token']} | {chf} |")
    aus += ["", "## Gates", ""]
    for modell in sorted({k[2] for k in t if k[0] == "A"}):
        aus.append(f"- Ranking ({modell}): {gate_ranking(t, modell)}")
        aus.append(f"- Verhoerer ({modell}): {gate_verhoerer(t, modell)}")
    return "\n".join(aus) + "\n"


# -- Rohdatei, Lauf, Aufruf ----------------------------------------------------

def lies_roh(pfad: str) -> list[dict]:
    p = Path(pfad)
    if not p.is_file():
        return []
    return [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines() if z.strip()]


def zaehle_roh(pfad: str) -> int:
    p = Path(pfad)
    return sum(1 for z in p.read_text(encoding="utf-8").splitlines() if z.strip()) if p.is_file() else 0


def _resonanz_modul():
    try:
        from interview_theater import begriffsboard_resonanz
    except ImportError:
        return None
    return begriffsboard_resonanz


def _git_kopf() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "?"


def modellname(alias: str, einst) -> str:
    return getattr(einst, MODELL_ALIAS[alias]) if alias in MODELL_ALIAS else alias


def _ein_aufruf(conn, klm, board_prompt: str, arm: str, fall: str, modell: str,
                wiederholung: int, kopf: str) -> dict:
    system, nutzer, schema, art = eingabe(arm, fall, board_prompt)
    vorher = conn.execute("SELECT max(id) AS m FROM aufruf").fetchone()["m"] or 0
    antwort = fehler = None
    start = time.monotonic()
    try:
        antwort = klm.schema(None, system, nutzer, schema, art, modell=modell)
    except Exception as ausnahme:  # noqa: BLE001 -- ein Fehlschlag ist ein Messwert
        fehler = f"{type(ausnahme).__name__}: {ausnahme}"[:300]
    wand_ms = int((time.monotonic() - start) * 1000)
    # Wie scripts/pruefe_prompts._aufruf_nach: llm.LLM._anfrage bucht im
    # ``finally``, also auch bei Fehlschlag.
    gebucht = conn.execute(
        "SELECT tatsaechliche_token, antwort_token, dauer_ms, kosten_chf FROM aufruf "
        "WHERE id > ? ORDER BY id DESC LIMIT 1", (vorher,),
    ).fetchone()
    return {
        "zeit": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kopf": kopf,
        "arm": arm, "fall": fall, "modell": modell, "wiederholung": wiederholung,
        "system_zeichen": len(system), "nutzer_zeichen": len(nutzer),
        "antwort": antwort, "fehler": fehler,
        "eingabe_token": (gebucht["tatsaechliche_token"] or 0) if gebucht else 0,
        "ausgabe_token": (gebucht["antwort_token"] or 0) if gebucht else 0,
        "dauer_ms": (gebucht["dauer_ms"] or wand_ms) if gebucht else wand_ms,
        "kosten_chf": (gebucht["kosten_chf"] or 0.0) if gebucht else 0.0,
    }


def _laufe(plan, modelle, roh_pfad: str) -> int:
    import httpx

    from interview_theater import anweisungen, db, einstellungen, llm, sprache, workshop

    os.environ["IT_WORKSHOP"] = "padua-2026"
    workshop.vergiss()
    sprache.vergiss()
    einst = einstellungen.laden()
    board_prompt = anweisungen.hole("begriffsboard")
    kopf = _git_kopf()
    Path(roh_pfad).parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rauchtest-resonanz-") as verzeichnis:
        conn = db.verbinde(str(Path(verzeichnis) / "wegwerf.db"))
        db.initialisiere(conn)
        try:
            with httpx.Client(timeout=120.0) as klient:
                klm = llm.LLM(einst, klient, conn)
                for alias in modelle:
                    modell = modellname(alias, einst)
                    for arm, fall, w in plan:
                        zeile = _ein_aufruf(conn, klm, board_prompt, arm, fall, modell, w, kopf)
                        with open(roh_pfad, "a", encoding="utf-8") as datei:
                            datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
                        zustand = f"FEHLER {zeile['fehler']}" if zeile["fehler"] else "ok"
                        print(f"{arm} {fall} {modell} #{w}: {zustand} ({zeile['dauer_ms']} ms)", flush=True)
        finally:
            conn.close()
    print(bericht(lies_roh(roh_pfad), _resonanz_modul()))
    return 0


def _argumente(argv):
    p = argparse.ArgumentParser(description="Rauchtest Begriffsboard-Resonanz (kostet Geld)")
    p.add_argument("--arme", default="board", help=f"Komma-Liste aus {', '.join(ARME)}")
    p.add_argument("--modell", default="gespraech", help="Komma-Liste: gespraech, erkenner")
    p.add_argument("--faelle", default="", help="Komma-Liste aus FAELLE, leer = alle")
    p.add_argument("--wiederholungen", type=int, default=WIEDERHOLUNGEN_VORGABE)
    p.add_argument("--roh", default=ROH_VORGABE)
    p.add_argument("--deckel", type=int, default=DECKEL_VORGABE)
    p.add_argument("--trocken", action="store_true", help="nur planen, kein Aufruf")
    p.add_argument("--auswerten", action="store_true", help="nur die Rohdatei auswerten, kein Aufruf")
    p.add_argument("--bericht", default="", help="Tabellen zusaetzlich in diese Datei schreiben")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _argumente(argv)
    if args.auswerten:
        text = bericht(lies_roh(args.roh), _resonanz_modul())
        print(text)
        if args.bericht:
            Path(args.bericht).parent.mkdir(parents=True, exist_ok=True)
            Path(args.bericht).write_text(text, encoding="utf-8")
        return 0
    arme = [a for a in args.arme.split(",") if a]
    modelle = [m for m in args.modell.split(",") if m]
    faelle = {f for f in args.faelle.split(",") if f}
    plan = auftraege(arme, faelle, args.wiederholungen)
    geplant = len(plan) * len(modelle)
    bisher = zaehle_roh(args.roh)
    print(f"Geplant: {geplant} bezahlte Aufrufe ({len(plan)} je Modell x {len(modelle)} Modell(e)); "
          f"bisher in {args.roh}: {bisher}; Deckel: {args.deckel}")
    if bisher + geplant > args.deckel:
        print("ABBRUCH: das Kartenbudget wuerde ueberschritten -- kein Aufruf.")
        return 3
    if args.trocken:
        return 0
    return _laufe(plan, modelle, args.roh)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Test laufen lassen, er muss bestehen**

Run: `$PY -m pytest tests/test_rauchtest_begriffsboard_resonanz.py -q -p no:cacheprovider`
Expected: Zählzeile `N passed` ohne `failed` und ohne `error` (jede Testfunktion aus Step 1 einmal je Parametrisierung).

- [ ] **Step 5: Trockenlauf von Hand (kein Aufruf, keine Zugangsdaten nötig)**

Run: `$PY -m scripts.rauchtest_begriffsboard_resonanz --arme board,prompt_nur,analyse,verhoerer --modell gespraech --trocken --roh /tmp/t9258_trocken.jsonl`
Expected: genau eine Zeile `Geplant: 95 bezahlte Aufrufe (95 je Modell x 1 Modell(e)); bisher in /tmp/t9258_trocken.jsonl: 0; Deckel: 200`, Exit 0, die Datei `/tmp/t9258_trocken.jsonl` existiert danach nicht.

- [ ] **Step 6: Commit**

```bash
git add scripts/rauchtest_begriffsboard_resonanz.py tests/test_rauchtest_begriffsboard_resonanz.py
git commit -m "Rauchtest Begriffsboard-Resonanz: Faelle a-g, Arme A-E, Kartendeckel, Auswertung offline (t_9258d2e9, Aufgabe 3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Bezahlter Messlauf und Gate (VOR jedem Einbau)

Nur mit `zugang True` aus Aufgabe 0, Step 3. Sonst: `BERICHT.md` mit dem Abschnitt „Ausstehend" (Step 5) anlegen, committen, die Aufgaben 5–7 entfallen.

**Files:**
- Create: `docs/begriffsboard-resonanz/rauchtest-tabellen.md` (vom Skript erzeugt, nur Zahlen)
- Create: `docs/begriffsboard-resonanz/BERICHT.md`
- Nicht committet: `korpus/berichte/begriffsboard_resonanz_roh.jsonl` (gitignored, `.gitignore:32`)

**Interfaces:**
- Consumes: Aufgabe 3 (`main`, Gates).
- Produces: die Gate-Entscheidung „D4 bauen ja/nein" für die Aufgaben 5–7; die Rohdatei, aus der Aufgabe 7 Arm B ohne Aufruf rechnet.

- [ ] **Step 1: Rohdatei ist ignoriert und leer**

```bash
git check-ignore -q korpus/berichte/begriffsboard_resonanz_roh.jsonl && echo ignoriert
test -e korpus/berichte/begriffsboard_resonanz_roh.jsonl && echo VORHANDEN || echo leer
```

Expected: `ignoriert`, dann `leer`. Steht `VORHANDEN` da: nicht löschen; die Zeilen zählen ins Kartenbudget, das Skript rechnet sie mit (im Bericht vermerken).

- [ ] **Step 2: Lauf 1 — Kimi, alle vier Aufrufarten (95 Aufrufe)**

```bash
$PY -m scripts.rauchtest_begriffsboard_resonanz --arme board,prompt_nur,analyse,verhoerer --modell gespraech --trocken
$PY -m scripts.rauchtest_begriffsboard_resonanz --arme board,prompt_nur,analyse,verhoerer --modell gespraech > /tmp/t9258_lauf1.log 2>&1; echo EXIT $?
tail -40 /tmp/t9258_lauf1.log
```

Der Lauf dauert ~15–30 min: im Hintergrund starten, bis zum Ende abwarten, währenddessen keinen zweiten bezahlten Lauf starten. Expected: Trockenlauf druckt `Geplant: 95 bezahlte Aufrufe …; bisher in korpus/berichte/begriffsboard_resonanz_roh.jsonl: 0; Deckel: 200`; danach `EXIT 0`, je Aufruf eine Zeile `<arm> <fall> <modell> #<n>: ok (… ms)` oder `FEHLER …`, am Ende der Bericht mit `## Gates`. `wc -l korpus/berichte/begriffsboard_resonanz_roh.jsonl` → `95`.

- [ ] **Step 3: Lauf 2 — gemma, nur Analyse-Arme (45 Aufrufe)**

```bash
$PY -m scripts.rauchtest_begriffsboard_resonanz --arme analyse,verhoerer --modell erkenner --trocken
$PY -m scripts.rauchtest_begriffsboard_resonanz --arme analyse,verhoerer --modell erkenner > /tmp/t9258_lauf2.log 2>&1; echo EXIT $?
wc -l korpus/berichte/begriffsboard_resonanz_roh.jsonl
```

Expected: `Geplant: 45 bezahlte Aufrufe …; bisher …: 95; Deckel: 200`, `EXIT 0`, danach `140 korpus/berichte/begriffsboard_resonanz_roh.jsonl`. Gemma braucht beim ersten Aufruf ~28 s Kaltstart (AGENTS.md, Falle 5) — der erste Messwert ist deshalb ein Ausreißer; `dauer_ms_max` im Bericht entsprechend kommentieren.

- [ ] **Step 4: Tabellen schreiben und Gates ablesen**

```bash
$PY -m scripts.rauchtest_begriffsboard_resonanz --auswerten --bericht docs/begriffsboard-resonanz/rauchtest-tabellen.md > /dev/null; echo EXIT $?
grep -E "^- (Ranking|Verhoerer)" docs/begriffsboard-resonanz/rauchtest-tabellen.md
grep -c "Resonanzmodul: nicht gebaut" docs/begriffsboard-resonanz/rauchtest-tabellen.md
```

Expected: `EXIT 0`; zwei Gate-Zeilen für das Kimi-Modell, z. B. `- Ranking (moonshotai/Kimi-K2.6): Praemisse bestaetigt: …` bzw. `… Praemisse widerlegt: Rezenz-Fix reicht fuer diese Faelle` und `- Verhoerer (…): …`; dann `1`. Steht ein Fall mit mehr als einem Fehler (`FEHLER` in den Logs, Spalte „Fehler" > 0) im Gate-Arm A für (b) oder (c): **einmal** `--arme board --faelle b_konsens,c_abgelehnt --modell gespraech` nachfahren (10 Aufrufe, Deckel prüft das Skript), dann Step 4 wiederholen. Das Gate gilt dann über alle Zeilen (≥ 4/5 als Anteil).

- [ ] **Step 5: `docs/begriffsboard-resonanz/BERICHT.md` anlegen**

Inhalt (Zahlen aus `rauchtest-tabellen.md` eintragen, **keine** Modellantworten, **keine** Transkripte zitieren):

```markdown
# Begriffsboard: Resonanz-Schicht und fokussierte Analyse — Messbericht (Karte t_9258d2e9)

Stand: <Datum, Uhrzeit>, Commit <git rev-parse --short HEAD>, Modelle: <gespraech>, <erkenner>.
Rohdaten: korpus/berichte/begriffsboard_resonanz_roh.jsonl (gitignored, <N> Zeilen). Tabellen: rauchtest-tabellen.md.

## Gate Ranking (D6)
Arm A (nur Modell, heutiges sortiert): (b) <x>/5, (c) <y>/5, Regression (a) <z>/5.
Ergebnis: <wörtlich die Gate-Zeile>.
Folge: <"Aufgaben 5–7 werden gebaut" | "Aufgaben 5–7 entfallen (Praemisse widerlegt)">.

## Gate Verhörer (D7)
Arm A (e) <x>/5 → <wörtlich die Gate-Zeile>.
Arm D (Prompt 'Sinn zuerst'): (e) <..>/5, (f) <..>/5, (g) <..>/5.
Arm C (Analyse kombiniert) je Modell: (e)/(f)/(g) …; Arm E (nur Verhörer) je Modell: …
Kombiniert gegen getrennt: <ein Satz, was C gegen E zeigt>.

## Kosten und Latenz (gemessen)
<Tabelle "Messwerte" und "Hochrechnung" aus rauchtest-tabellen.md übernommen>

## Ausstehend
<nur falls kein Zugang: "Bezahlter Lauf ausstehend (Zugangsdaten nicht in der Umgebung). Befehle: Aufgabe 4, Steps 2–4 des Plans.">
```

- [ ] **Step 6: Prüfen und committen**

```bash
grep -c "## Gate Ranking" docs/begriffsboard-resonanz/BERICHT.md
git add docs/begriffsboard-resonanz/BERICHT.md docs/begriffsboard-resonanz/rauchtest-tabellen.md
git commit -m "Begriffsboard-Resonanz: Messlauf vor dem Einbau, Gates (t_9258d2e9, Aufgabe 4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Expected: `1`; Commit mit genau zwei Dateien (`git show --stat HEAD | tail -1` → `2 files changed`).

**Gate:** Lautet die Ranking-Zeile `Praemisse widerlegt: Rezenz-Fix reicht fuer diese Faelle`, **weiter mit Aufgabe 8** (5–7 entfallen; das ist ein gültiges Ergebnis). Sonst weiter mit Aufgabe 5.

---

### Task 5: Resonanz-Modul `begriffsboard_resonanz` (D1, D5)

Nur bei Gate „Praemisse bestaetigt".

**Files:**
- Create: `interview_theater/begriffsboard_resonanz.py`
- Test: `tests/test_begriffsboard_resonanz.py`

**Interfaces:**
- Consumes: `begriffsboard.schluessel`, `begriffsboard._ganzzahl`; `sprache.je_sprache`, `sprache.code`, `sprache.DEUTSCH`; für die Tests `scripts.rauchtest_begriffsboard_resonanz.transkript`.
- Produces (Aufgabe 6 und das Skript benutzen sie):
  - `FENSTER_NACH = 120`, `FENSTER_DAVOR = 25`, `RESONANZ_MIN = -3`, `RESONANZ_MAX = 3`, `BONUS_AB = 2`
  - `PHRASEN: dict[str, dict[str, tuple[str, ...]]]` mit den Schlüsseln `ja`, `ja_satzzeichen`, `nein`, `nein_satzzeichen`, `nein_davor`, `artikel` je Sprache
  - `resonanz_je_begriff(begriffe: list[str], transkript: str, *, code: str | None = None) -> dict[str, int]` (Schlüssel `begriffsboard.schluessel(begriff)`)
  - `trage_ein(eintraege: list[dict], transkript: str, *, code: str | None = None) -> None` (setzt `resonanz` nur ≠ 0, entfernt sie sonst)
  - `lies_wert(roh) -> int` (geklemmt, Unsinn → 0)
  - `bonus(resonanz: int) -> int` ∈ {−1, 0, 1}
  - `wunsch(eintrag: dict) -> int` = `_ganzzahl(zustimmung) + bonus(lies_wert(resonanz))`

**Die Zahlen, begründet.** `FENSTER_NACH` = 120 Zeichen ≈ gut 20 gesprochene Wörter, 6–8 s: die unmittelbare Antwort im selben oder am Anfang des nächsten Segments (`repo.diskussion_transkript` verbindet Segmente mit Leerzeile, nach `schluessel` ein Leerzeichen). Weiter hinten antwortet die Gruppe schon auf etwas anderes; das Fenster endet außerdem an der nächsten Nennung **irgendeines** Boardbegriffs — einschließlich der Verneinung direkt davor („No, not the garden" gehört zu „garden", nicht zum vorigen Begriff). `FENSTER_DAVOR` = 25 Zeichen trägt die **direkte** Verneinung vor einer Nennung („no, not the garden", „instead of the garden") — sie ist das eindeutigste Ablehnungssignal, und das Beispiel der Karte selbst steht so (Verneinung **vor** dem Begriff); D1 nennt das Fenster danach, dieses Fenster davor ist eine additive Präzisierung. Klemme ±3: drei unabhängige Signale sind in einem Workshopgespräch viel, mehr bringt keine neue Information. `BONUS_AB` = 2: ein einzelnes „yes" kann Füllwort oder die Sprecherin selbst sein (keine Sprechertrennung) — erst zwei Signale in dieselbe Richtung verschieben um eine Stufe. ANNAHME: diese Werte trennen auch echte Padua-Diskussionen — nachzupruefen: Birk, nach dem nächsten Live-Test `resonanz` je Begriff im CoThinker-JSON (`begriffsboard.json`) gegen den eigenen Eindruck der Diskussion; die drei Rauchtest-Transkripte unten sind die einzige Messung dieser Karte.

**Bewusst nicht in den Listen:** „no" ohne folgendes Satzzeichen („no idea"), „right"/„sure"/„okay" ohne Satzzeichen („the right place"), „great"/„nice" („a great garden" beschreibt), DE „ja" ohne Satzzeichen (Füllwort: „das ist ja schön").

- [ ] **Step 1: Failing test schreiben** — `tests/test_begriffsboard_resonanz.py`:

```python
"""Karte t_9258d2e9, Aufgabe 5: die gezaehlte Resonanz (D1, D5) -- ohne
Modell, ohne Datenbank."""

import pytest

from interview_theater import begriffsboard_resonanz as res
from scripts import rauchtest_begriffsboard_resonanz as rt


def _r(begriffe, text, code="en"):
    return res.resonanz_je_begriff(begriffe, text, code=code)


def test_ja_genau_nach_der_nennung():
    assert _r(["lighthouse"], "We could use the lighthouse. Yes, exactly, the lighthouse.") == {"lighthouse": 2}


def test_fenster_endet_an_der_naechsten_nennung():
    assert _r(["garden", "ocean"], "The garden. The ocean, yes, exactly.") == {"garden": 0, "ocean": 2}


def test_verneinung_davor_gehoert_zum_folgenden_begriff():
    assert _r(["garden"], "Maybe the garden. No, not the garden.") == {"garden": -1}
    assert _r(["station", "garden"], "Yes, the station. I like that. No, not the garden.") == {
        "station": 1, "garden": -1}


def test_satzzeichenwoerter_nur_mit_satzzeichen():
    assert _r(["garden"], "The garden is the right place.") == {"garden": 0}
    assert _r(["garden"], "The garden. Right, that's it.") == {"garden": 2}
    assert _r(["garden"], "The garden. No idea why.") == {"garden": 0}


def test_klemme():
    assert _r(["garden"], "The garden. Yes yes yes yes yes.") == {"garden": 3}
    assert _r(["garden"], "The garden. I don't think so, rather not, no way, I don't like it.") == {"garden": -3}


def test_typografischer_apostroph_wie_gerader():
    assert _r(["garden"], "The garden. I don’t think so.") == {"garden": -1}


def test_wortgrenzen():
    assert _r(["garden"], "Gardening is fun. Yes.") == {"garden": 0}
    assert _r(["garden"], "We cannot the garden.") == {"garden": 0}


def test_fehlender_begriff_ist_null():
    assert _r(["AI robot"], "We want a robot that talks back. Yes!") == {"ai robot": 0}


def test_eingeschlossene_nennung_zaehlt_einmal():
    assert _r(["station", "train station"], "The train station. Yes.") == {"station": 0, "train station": 1}


def test_deutsche_liste():
    assert _r(["Garten"], "Der Garten. Genau, stimmt.", code="de") == {"garten": 2}
    assert _r(["Garten"], "Nein, nicht der Garten.", code="de") == {"garten": -1}


def test_aktive_sprache_ohne_code(monkeypatch):
    from interview_theater import sprache
    monkeypatch.setattr(sprache, "code", lambda: "en")
    assert res.resonanz_je_begriff(["garden"], "The garden. Yes, exactly.") == {"garden": 2}


def test_jede_sprache_hat_alle_listen():
    for code in ("de", "en"):
        assert set(res.PHRASEN[code]) == {"ja", "ja_satzzeichen", "nein", "nein_satzzeichen",
                                          "nein_davor", "artikel"}


# -- Die Rauchtest-Transkripte: hier wird die Fensterwahl gemessen ------------

def test_fall_b_konsens():
    assert _r(["lighthouse", "motorbike"], rt.transkript("b_konsens")) == {"lighthouse": 3, "motorbike": 0}


def test_fall_c_abgelehnt():
    assert _r(["garden", "station"], rt.transkript("c_abgelehnt")) == {"garden": -2, "station": 2}


def test_fall_d_kontrolle_ohne_phrasen():
    werte = _r(["river", "bridge", "old part of town", "neighbourhood"], rt.transkript("d_kontrolle"))
    assert set(werte.values()) == {0}


# -- Eintrag, Bonus, Wunsch ----------------------------------------------------

def test_trage_ein_ist_duenn_und_traegt_nur_eine_zahl():
    eintraege = [{"begriff": "lighthouse", "zustimmung": 1}, {"begriff": "Motorbike", "resonanz": 3}]
    res.trage_ein(eintraege, rt.transkript("b_konsens"), code="en")
    assert eintraege == [{"begriff": "lighthouse", "zustimmung": 1, "resonanz": 3}, {"begriff": "Motorbike"}]


@pytest.mark.parametrize("roh, erwartet", [(7, 3), (-9, -3), ("2", 2), ("x", 0), (None, 0)])
def test_lies_wert(roh, erwartet):
    assert res.lies_wert(roh) == erwartet


@pytest.mark.parametrize("resonanz, erwartet", [(-3, -1), (-2, -1), (-1, 0), (0, 0), (1, 0), (2, 1), (3, 1)])
def test_bonus(resonanz, erwartet):
    assert res.bonus(resonanz) == erwartet


def test_wunsch():
    assert res.wunsch({"zustimmung": 1}) == 1
    assert res.wunsch({"zustimmung": 1, "resonanz": 2}) == 2
    assert res.wunsch({"zustimmung": "x", "resonanz": -3}) == -1
```

- [ ] **Step 2: Test laufen lassen, er muss scheitern**

Run: `$PY -m pytest tests/test_begriffsboard_resonanz.py -q -p no:cacheprovider`
Expected: FAIL beim Sammeln mit `ImportError: cannot import name 'begriffsboard_resonanz' from 'interview_theater'`.

- [ ] **Step 3: Modul schreiben** — `interview_theater/begriffsboard_resonanz.py`:

```python
"""Resonanz im Begriffsboard (Karte t_9258d2e9, 04.10.2026): wie die Gruppe
auf einen Begriff ANTWORTET -- gezaehlt, nicht geschaetzt.

**Warum.** ``zustimmung`` (-2..2) schaetzt das Board-Modell im selben Aufruf
nebenbei; seit dem Rezenz-Fix (69a6b0a) gewichtet es das Zuletzt-Gesagte.
Eine Stimme, die einen Begriff spaet und oft wiederholt, sieht fuer diese
eine Zahl aus wie Einigkeit. Die Resonanz zaehlt stattdessen, was
UNMITTELBAR auf eine Nennung folgt ("yes, exactly", "I agree", "let's go
with") und was ihr direkt widerspricht ("not the ...", "I don't think").
Beleg aus den Worten der Gruppe, nachrechenbar, kostenlos, ohne Latenz --
und unabhaengig vom Modell, das das Board schreibt: sie kann dessen eine
Zahl korrigieren, statt sie zu wiederholen. ``begriffsboard.sortiert``
rechnet daraus hoechstens eine Stufe (``bonus``).

**Ehrliche Grenzen.** Keine Sprechertrennung (anonymisiert, AGENTS.md "Drei
Grenzen") -- ein "yes" kann die Sprecherin zu sich selbst sagen. STT setzt
Satzzeichen unzuverlaessig: die Woerter, die NUR mit folgendem Satzzeichen
zaehlen ("right,", "no,"), fallen ohne Satzzeichen weg (die harmlose
Richtung). Ein Begriff, den das Modell umformuliert hat, steht nicht
woertlich im Transkript: dann 0 -- es bleibt die Ordnung von heute.

**Kein Modellaufruf, keine Datenbank, kein Transkripttext im Ergebnis** --
eine ganze Zahl je Begriff. Die Wortlisten folgen der Repo-Konvention fuer
Parser (``sprache.je_sprache``, wie ``sprachpass.py``); die deutsche Liste
ist ungemessen (das Board laeuft nur unter ``diskussion.aktiv``, Padua)."""

from __future__ import annotations

import re

from interview_theater import begriffsboard, sprache

#: Zeichen NACH einer Nennung, in denen ihre Antwort gesucht wird: gut 20
#: gesprochene Woerter. Das Fenster endet frueher an der naechsten Nennung
#: eines Boardbegriffs (samt dessen Verneinung davor). Begruendung im Plan.
FENSTER_NACH = 120
#: Zeichen VOR einer Nennung fuer die direkte Verneinung ("no, not the garden").
FENSTER_DAVOR = 25
RESONANZ_MIN = -3
RESONANZ_MAX = 3
#: Ab so vielen Signalen in eine Richtung verschiebt die Resonanz um eine
#: Stufe -- ein einzelnes "yes" kann Fuellwort oder Selbstgespraech sein.
BONUS_AB = 2

_SATZZEICHEN = r"[,.!?;:]"

#: Je Sprache, casefold, nach ``zitat.normalisiere`` (gerade Apostrophe).
#: ``ja``/``nein``: zaehlen ueberall im Fenster danach, an Wortgrenzen.
#: ``ja_satzzeichen``/``nein_satzzeichen``: nur mit direkt folgendem
#: Satzzeichen. ``nein_davor``: direkt VOR der Nennung, ein ``artikel``
#: dazwischen erlaubt, optional mit vorangestelltem "no,".
PHRASEN: dict[str, dict[str, tuple[str, ...]]] = {
    "de": {
        "ja": ("genau", "stimmt", "einverstanden", "auf jeden fall", "das ist es",
               "nehmen wir", "gefaellt mir", "gefällt mir", "finde ich gut", "bin dafuer",
               "bin dafür", "unbedingt"),
        "ja_satzzeichen": ("ja", "richtig", "klar", "okay", "ok"),
        "nein": ("ich weiss nicht", "ich weiß nicht", "lieber nicht", "eher nicht",
                 "finde ich nicht gut", "gefaellt mir nicht", "gefällt mir nicht",
                 "auf keinen fall", "bin dagegen"),
        "nein_satzzeichen": ("nein", "noe", "nö"),
        "nein_davor": ("nicht", "kein", "keine", "keinen", "statt", "anstatt"),
        "artikel": ("der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem"),
    },
    "en": {
        "ja": ("yes", "yeah", "yep", "exactly", "agreed", "i agree", "absolutely",
               "definitely", "that's it", "let's go with", "let's take", "let's do",
               "love that", "love it", "i like that", "i like it", "sounds good",
               "good idea", "perfect"),
        "ja_satzzeichen": ("right", "true", "sure", "okay", "ok"),
        "nein": ("i don't think", "i do not think", "rather not", "not sure about",
                 "i don't like", "i don't want", "let's not", "no way", "too boring"),
        "nein_satzzeichen": ("no", "nah", "nope"),
        "nein_davor": ("not", "no", "no more", "rather than", "instead of",
                       "anything but", "forget", "forget about", "drop"),
        "artikel": ("the", "a", "an", "this", "that", "our"),
    },
}

_MUSTER: dict[str, tuple[re.Pattern, re.Pattern]] = {}


def _alternativen(phrasen) -> str:
    """Laengste zuerst: "i don't like" vor "i", "no more" vor "no"."""
    return "|".join(re.escape(p) for p in sorted(set(phrasen), key=len, reverse=True))


def _muster(code: str | None) -> tuple[re.Pattern, re.Pattern]:
    if code is None:
        schluessel, p = sprache.code(), sprache.je_sprache(PHRASEN)
    else:
        schluessel, p = code, PHRASEN.get(code, PHRASEN[sprache.DEUTSCH])
    if schluessel not in _MUSTER:
        signal = re.compile(
            r"(?<!\w)(?:"
            rf"(?P<nein>{_alternativen(p['nein'])})"
            rf"|(?P<ja>{_alternativen(p['ja'])})"
            rf"|(?P<nein_sz>{_alternativen(p['nein_satzzeichen'])})(?={_SATZZEICHEN})"
            rf"|(?P<ja_sz>{_alternativen(p['ja_satzzeichen'])})(?={_SATZZEICHEN})"
            r")(?!\w)"
        )
        davor = re.compile(
            rf"(?:(?<!\w)(?:{_alternativen(p['nein_satzzeichen'])}){_SATZZEICHEN}\s*)?"
            rf"(?<!\w)(?:{_alternativen(p['nein_davor'])})\s+"
            rf"(?:(?:{_alternativen(p['artikel'])})\s+)?$"
        )
        _MUSTER[schluessel] = (signal, davor)
    return _MUSTER[schluessel]


def _nennungen(schluessel_liste: list[str], text: str) -> list[tuple[int, int, str]]:
    """Alle Nennungen an Wortgrenzen, nach Position; eine Nennung, die in
    einer laengeren steckt ("station" in "train station"), zaehlt nicht."""
    treffer = []
    for k in schluessel_liste:
        for m in re.finditer(r"(?<!\w)" + re.escape(k) + r"(?!\w)", text):
            treffer.append((m.start(), m.end(), k))
    treffer.sort(key=lambda t: (t[0], t[0] - t[1]))
    ergebnis: list[tuple[int, int, str]] = []
    ende = -1
    for anfang, schluss, k in treffer:
        if anfang < ende:
            continue
        ergebnis.append((anfang, schluss, k))
        ende = schluss
    return ergebnis


def resonanz_je_begriff(begriffe: list[str], transkript: str, *,
                        code: str | None = None) -> dict[str, int]:
    """Je Begriff (Schluessel ``begriffsboard.schluessel``) Zustimmungen
    minus Ablehnungen um seine Nennungen, geklemmt. Ein Begriff, der nicht
    woertlich im Transkript steht, bekommt 0."""
    text = begriffsboard.schluessel(transkript)
    schluessel_liste = list(dict.fromkeys(
        k for k in (begriffsboard.schluessel(b) for b in begriffe) if k))
    signal, davor = _muster(code)
    nennungen = _nennungen(schluessel_liste, text)
    summe = dict.fromkeys(schluessel_liste, 0)
    zonenanfang: list[int] = []
    vorher_ende = 0
    for anfang, schluss, k in nennungen:
        m = davor.search(text, max(vorher_ende, anfang - FENSTER_DAVOR), anfang)
        if m:
            summe[k] -= 1
            zonenanfang.append(m.start())
        else:
            zonenanfang.append(anfang)
        vorher_ende = schluss
    for i, (_, schluss, k) in enumerate(nennungen):
        grenze = zonenanfang[i + 1] if i + 1 < len(nennungen) else len(text)
        ende = max(schluss, min(schluss + FENSTER_NACH, grenze))
        for m in signal.finditer(text, schluss, ende):
            summe[k] += 1 if (m.group("ja") or m.group("ja_sz")) else -1
    return {k: max(RESONANZ_MIN, min(RESONANZ_MAX, v)) for k, v in summe.items()}


def trage_ein(eintraege: list[dict], transkript: str, *, code: str | None = None) -> None:
    """Setzt ``resonanz`` an jedem Eintrag -- duenn: nur bei != 0, sonst wird
    ein alter Wert entfernt. Allein der Code schreibt das Feld."""
    werte = resonanz_je_begriff([e.get("begriff") or "" for e in eintraege], transkript, code=code)
    for eintrag in eintraege:
        wert = werte.get(begriffsboard.schluessel(eintrag.get("begriff")), 0)
        if wert:
            eintrag["resonanz"] = wert
        else:
            eintrag.pop("resonanz", None)


def lies_wert(roh) -> int:
    return max(RESONANZ_MIN, min(RESONANZ_MAX, begriffsboard._ganzzahl(roh)))


def bonus(resonanz: int) -> int:
    if resonanz >= BONUS_AB:
        return 1
    if resonanz <= -BONUS_AB:
        return -1
    return 0


def wunsch(eintrag: dict) -> int:
    """Der Sortierwert: die Modellzahl plus hoechstens eine Stufe Resonanz.
    Ohne ``resonanz`` genau ``zustimmung`` -- die Ordnung von heute."""
    return begriffsboard._ganzzahl(eintrag.get("zustimmung")) + bonus(lies_wert(eintrag.get("resonanz")))
```

- [ ] **Step 4: Test laufen lassen, er muss bestehen**

Run: `$PY -m pytest tests/test_begriffsboard_resonanz.py -q -p no:cacheprovider`
Expected: Zählzeile `N passed` ohne `failed` und ohne `error`. Scheitert einer der drei Rauchtest-Fälle (`test_fall_b_konsens`, `test_fall_c_abgelehnt`, `test_fall_d_kontrolle_ohne_phrasen`), ist die Fensterwahl falsch und **nicht** die Erwartung: dann das Fenster nach systematic-debugging untersuchen, nicht die Zahl im Test anpassen.

- [ ] **Step 5: Commit**

```bash
git add interview_theater/begriffsboard_resonanz.py tests/test_begriffsboard_resonanz.py
git commit -m "Begriffsboard: Resonanz gezaehlt statt geschaetzt (Fenster nach/vor jeder Nennung, EN/DE-Listen) (t_9258d2e9, Aufgabe 5)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Resonanz in `begriffsboard.py` einbauen (D4)

Nur bei Gate „Praemisse bestaetigt".

**Files:**
- Modify: `interview_theater/begriffsboard.py` — `_eintrag` (`:80-99`), `sortiert` (`:137-144`), `_nutzertext` (`:250-258`), `_lauf_einmal` (`:356-358`)
- Test: `tests/test_begriffsboard_resonanz_lauf.py`

**Interfaces:**
- Consumes: aus Aufgabe 5 `begriffsboard_resonanz.trage_ein`, `.lies_wert`, `.wunsch`.
- Produces: Boardeinträge mit dünnem `resonanz: int` (gespeichert in `begriffsboard.json`, gelesen von `lies`), `sortiert`-Schlüssel `(rang, -wunsch, -zustimmung, -nennungen, schluessel)`. Keine neue Funktion, keine geänderte Signatur.

Import-Richtung: `begriffsboard_resonanz` importiert `begriffsboard` oben; `begriffsboard` importiert `begriffsboard_resonanz` deshalb **lokal in der Funktion** — die im ganzen Repo übliche Auflösung eines Zyklus (AGENTS.md, „Modulkarte").

- [ ] **Step 1: Failing test schreiben** — `tests/test_begriffsboard_resonanz_lauf.py`:

```python
"""Karte t_9258d2e9, Aufgabe 6: die Resonanz im Board (D4) -- additiv,
duenn, und ohne Resonanz exakt die Ordnung von heute."""

import json
import random
import time

import pytest

from interview_theater import begriffsboard, db, einstellungen, repo, sprache, web, workshop

CHAT = 1


def _alter_schluessel(e):
    """Der Sortierschluessel vor dieser Karte, woertlich."""
    return (begriffsboard._RANG.get(e.get("status"), begriffsboard._RANG["kandidat"]),
            -begriffsboard._ganzzahl(e.get("zustimmung")),
            -begriffsboard._ganzzahl(e.get("nennungen")),
            begriffsboard.schluessel(e.get("begriff")))


def test_ohne_resonanz_sortiert_es_wie_vorher():
    zufall = random.Random(7)
    for _ in range(300):
        eintraege = [{"begriff": f"B{zufall.randrange(40)}",
                      "status": zufall.choice(begriffsboard.STATUS + ("quatsch",)),
                      "zustimmung": zufall.randint(-2, 2), "nennungen": zufall.randint(0, 5)}
                     for _ in range(zufall.randint(0, 12))]
        assert begriffsboard.sortiert(eintraege) == sorted(eintraege, key=_alter_schluessel)


def _e(begriff, status="kandidat", zustimmung=0, nennungen=0, **mehr):
    return dict({"begriff": begriff, "status": status, "zustimmung": zustimmung,
                 "nennungen": nennungen, "begruendung": "", "zitat": "", "doppelbedeutung": ""}, **mehr)


def test_resonanz_hebt_um_eine_stufe_und_zustimmung_bricht_den_gleichstand():
    eintraege = [_e("Laut", zustimmung=1, nennungen=5),
                 _e("Leise", zustimmung=1, resonanz=2),
                 _e("Stark", zustimmung=2)]
    assert [e["begriff"] for e in begriffsboard.sortiert(eintraege)] == ["Stark", "Leise", "Laut"]


def test_negative_resonanz_senkt_um_eine_stufe():
    eintraege = [_e("Garten", zustimmung=2, resonanz=-2), _e("Bahnhof", zustimmung=1, nennungen=0)]
    assert [e["begriff"] for e in begriffsboard.sortiert(eintraege)] == ["Garten", "Bahnhof"]
    eintraege = [_e("Garten", zustimmung=1, nennungen=9, resonanz=-2), _e("Bahnhof", zustimmung=1)]
    assert [e["begriff"] for e in begriffsboard.sortiert(eintraege)] == ["Bahnhof", "Garten"]


def test_status_bleibt_zuerst():
    eintraege = [_e("Oben", "kandidat", 2, resonanz=3), _e("Fav", "favorit", -2, resonanz=-3)]
    assert [e["begriff"] for e in begriffsboard.sortiert(eintraege)] == ["Fav", "Oben"]


def test_lies_liest_resonanz_duenn_und_defensiv():
    assert begriffsboard.lies('[{"begriff": "Mut", "resonanz": 7}]')[0]["resonanz"] == 3
    assert "resonanz" not in begriffsboard.lies('[{"begriff": "Mut", "resonanz": "x"}]')[0]
    assert "resonanz" not in begriffsboard.lies('[{"begriff": "Mut", "resonanz": 0}]')[0]


def test_nutzertext_schickt_keine_resonanz_ans_modell():
    text = begriffsboard._nutzertext("Hallo Mut", [_e("Mut", resonanz=3)])
    assert '"Mut"' in text and "resonanz" not in text


def test_web_zeigt_keine_zahl_aus_der_resonanz(monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    ohne = web._begriffsboard_html([_e("Mut", zustimmung=1, nennungen=2)])
    mit = web._begriffsboard_html([_e("Mut", zustimmung=1, nennungen=2, resonanz=3)])
    assert ohne == mit


# -- Der Lauf speichert die Resonanz -------------------------------------------

@pytest.fixture
def einst(tmp_path):
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, CHAT, "gruppe1", "Testgruppe")
    return c


class _KLM:
    def __init__(self, board):
        self._board = board

    def schema(self, chat_id, system, nutzer, schema, art, modell=None, bei_teil=None):
        return {"board": self._board}


def _warte_bis(bedingung, timeout=5.0):
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if bedingung():
            return
        time.sleep(0.01)
    assert bedingung(), "Bedingung nie eingetreten"


def test_lauf_speichert_resonanz_nur_wo_sie_nicht_null_ist(conn, einst, monkeypatch):
    monkeypatch.setattr(workshop, "diskussion_aktiv", lambda *a, **k: True)
    monkeypatch.setattr(sprache, "code", lambda: "en")
    aid = repo.lege_aufnahme_an(conn, CHAT, 10, "kurz", "sprache", status="transkribiert",
                                diskussion=True, schnittgrund="pause")
    repo.setze_transkript(conn, aid, "We talk about home. Home, yes, exactly. Home is where grandma cooks.")
    repo.setze_status(conn, aid, "fertig")
    klm = _KLM([_e("Home", zustimmung=1, nennungen=3), _e("grandma", zustimmung=0, nennungen=1)])
    assert begriffsboard.starte(conn, klm, einst, CHAT) is True
    _warte_bis(lambda: repo.letztes_begriffsboard(conn, CHAT) is not None)
    _warte_bis(lambda: not begriffsboard.laeuft(CHAT))
    gespeichert = {e["begriff"]: e for e in json.loads(repo.letztes_begriffsboard(conn, CHAT)["json"])}
    assert gespeichert["Home"]["resonanz"] == 2
    assert "resonanz" not in gespeichert["grandma"]
```

- [ ] **Step 2: Test laufen lassen, er muss scheitern**

Run: `$PY -m pytest tests/test_begriffsboard_resonanz_lauf.py -q -p no:cacheprovider`
Expected: FAIL. `test_ohne_resonanz_sortiert_es_wie_vorher` und `test_status_bleibt_zuerst` bestehen schon (die Ordnung ist heute so); ebenso `test_web_zeigt_keine_zahl_aus_der_resonanz` (das Web zeigt `resonanz` heute schon nicht). Scheitern müssen genau diese fünf: `test_resonanz_hebt_um_eine_stufe_und_zustimmung_bricht_den_gleichstand` (`AssertionError`, heute `['Stark', 'Laut', 'Leise']`), `test_negative_resonanz_senkt_um_eine_stufe` (`AssertionError`, heute `['Garten', 'Bahnhof']` im zweiten Fall), `test_lies_liest_resonanz_duenn_und_defensiv` (`KeyError: 'resonanz'`), `test_nutzertext_schickt_keine_resonanz_ans_modell` (`AssertionError`, `"resonanz"` steht im Board-JSON) und `test_lauf_speichert_resonanz_nur_wo_sie_nicht_null_ist` (`KeyError: 'resonanz'`).

- [ ] **Step 3: `_eintrag` — dünnes `resonanz` lesen** (`interview_theater/begriffsboard.py:80-99`). Ersetze die Funktion durch:

```python
def _eintrag(zeile) -> dict | None:
    """Eine Zeile in die feste Form -- ohne Transkriptpruefung (die macht
    ``validiere``). None, wenn sie keinen brauchbaren Begriff traegt.
    ``resonanz`` (Karte t_9258d2e9) steht nur da, wenn sie nicht 0 ist: ein
    Board ohne Resonanz bleibt Zeichen fuer Zeichen, wie es war."""
    if not isinstance(zeile, dict):
        return None
    teile = begriffe_modul.zerlege(" ".join(str(zeile.get("begriff") or "").split()))
    if len(teile) != 1:
        # Leer, oder ein Listentrenner im Begriff: er zerfiele beim
        # Speichern (``begriffe.zerlege``) in zwei.
        return None
    status = str(zeile.get("status") or "").strip().casefold()
    eintrag = {
        "begriff": teile[0],
        "nennungen": max(0, _ganzzahl(zeile.get("nennungen"))),
        "zustimmung": min(ZUSTIMMUNG_MAX, max(ZUSTIMMUNG_MIN, _ganzzahl(zeile.get("zustimmung")))),
        "begruendung": str(zeile.get("begruendung") or "").strip(),
        "zitat": str(zeile.get("zitat") or "").strip(),
        "doppelbedeutung": str(zeile.get("doppelbedeutung") or "").strip(),
        "status": status if status in STATUS else "kandidat",
    }
    from interview_theater import begriffsboard_resonanz  # lokal: es importiert dieses Modul

    resonanz = begriffsboard_resonanz.lies_wert(zeile.get("resonanz"))
    if resonanz:
        eintrag["resonanz"] = resonanz
    return eintrag
```

- [ ] **Step 4: `sortiert` — Schlüssel `wunsch`** (`:137-144`). Ersetze durch:

```python
def sortiert(eintraege: list[dict]) -> list[dict]:
    """DIE Sortierung (D4) -- fuer die Webansicht UND den Top-5-Vorschlag.
    Status zuerst; dann ``wunsch`` = ``zustimmung`` plus hoechstens eine
    Stufe gezaehlter Resonanz (``begriffsboard_resonanz.wunsch``, Karte
    t_9258d2e9); ``zustimmung`` bricht den Gleichstand. Ohne ``resonanz``
    ist ``wunsch`` gleich ``zustimmung`` -- die Ordnung von vorher."""
    from interview_theater import begriffsboard_resonanz  # lokal: es importiert dieses Modul

    return sorted(eintraege, key=lambda e: (
        _RANG.get(e.get("status"), _RANG["kandidat"]),
        -begriffsboard_resonanz.wunsch(e),
        -_ganzzahl(e.get("zustimmung")),
        -_ganzzahl(e.get("nennungen")),
        schluessel(e.get("begriff")),
    ))
```

- [ ] **Step 5: `_nutzertext` — keine Resonanz ans Modell** (`:250-258`). Ersetze die `return`-Anweisung durch:

```python
    # ``resonanz`` geht nicht ans Modell (Karte t_9258d2e9): sie soll seine
    # ``zustimmung`` korrigieren, nicht von ihm uebernommen werden.
    ohne = [{k: v for k, v in e.items() if k != "resonanz"} for e in sortiert(board)]
    return (
        f"{T._TRANSKRIPT_KOPF}\n{transkript}\n\n"
        f"{T._BOARD_KOPF}\n{json.dumps(ohne, ensure_ascii=False)}"
    )
```

- [ ] **Step 6: `_lauf_einmal` — Resonanz eintragen** (direkt nach `neu = validiere(...)`, `:358`). Füge ein:

```python
    from interview_theater import begriffsboard_resonanz  # lokal: es importiert dieses Modul

    # Resonanz (Karte t_9258d2e9): im Code gezaehlt, gegen das GANZE
    # Transkript, nie vom Modell -- duenn, nur wenn != 0.
    begriffsboard_resonanz.trage_ein(neu, transkript)
```

**Falls t_cb2c4678 schon gemergt ist** (Aufgabe 0, Step 2): `_eintrag` endet dort bereits mit `eintrag = {...}`, dem `vorgaenger`-Block und `return eintrag` — dann nur die vier `resonanz`-Zeilen (Import, `lies_wert`, `if`, Zuweisung) vor `return eintrag` einfügen, nichts anderes umbauen; und die `trage_ein`-Zeilen stehen hinter dem dort dreizeiligen `validiere(..., bisher=bisher)`. Beim späteren Merge **ohne** vorherigen Merge entstehen genau diese zwei Konfliktstellen; Auflösung: beide dünnen Felder behalten (`vorgaenger`-Block und `resonanz`-Block hintereinander vor `return eintrag`).

- [ ] **Step 7: Test laufen lassen, er muss bestehen**

Run: `$PY -m pytest tests/test_begriffsboard_resonanz_lauf.py tests/test_begriffsboard_resonanz.py -q -p no:cacheprovider`
Expected: alle `passed`, kein `failed`.

- [ ] **Step 8: Alle Begriffsboard-Tests unverändert grün**

Run: `$PY -m pytest tests/test_begriffsboard.py tests/test_begriffsboard_lauf.py tests/test_begriffsboard_web.py tests/test_begriffsboard_vorschlag.py tests/test_begriffsboard_mithoeren.py tests/test_begriffsboard_einstieg.py tests/test_begriffe_detail_wege.py -q -p no:cacheprovider -m "not dortmund"`
Expected: `… passed`, kein `failed`; `git diff --stat HEAD -- tests/test_begriffsboard.py` ist leer.

- [ ] **Step 9: Commit**

```bash
git add interview_theater/begriffsboard.py tests/test_begriffsboard_resonanz_lauf.py
git commit -m "Begriffsboard: Resonanz duenn speichern, sortiert nach wunsch (zustimmung + Resonanzstufe) (t_9258d2e9, Aufgabe 6)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Arm B offline auswerten (0 Aufrufe)

Nur bei Gate „Praemisse bestaetigt" und nach Aufgabe 6.

**Files:**
- Modify: `docs/begriffsboard-resonanz/rauchtest-tabellen.md` (neu erzeugt)
- Modify: `docs/begriffsboard-resonanz/BERICHT.md` (Abschnitt „Arm B")

**Interfaces:**
- Consumes: Rohdatei aus Aufgabe 4, `begriffsboard_resonanz` (Aufgabe 5), neues `sortiert` (Aufgabe 6).

- [ ] **Step 1: Auswerten ohne Aufruf**

```bash
wc -l korpus/berichte/begriffsboard_resonanz_roh.jsonl
$PY -m scripts.rauchtest_begriffsboard_resonanz --auswerten --bericht docs/begriffsboard-resonanz/rauchtest-tabellen.md > /dev/null; echo EXIT $?
wc -l korpus/berichte/begriffsboard_resonanz_roh.jsonl
grep -c "Resonanzmodul: vorhanden" docs/begriffsboard-resonanz/rauchtest-tabellen.md
grep -E "^\| (a_rezenz|b_konsens|c_abgelehnt|d_kontrolle) \| B \|" docs/begriffsboard-resonanz/rauchtest-tabellen.md
```

Expected: vorher und nachher dieselbe Zeilenzahl (kein Aufruf), `EXIT 0`, `1`, und vier Zeilen der Form `| b_konsens | B | <modell> | x/5 |` (für `d_kontrolle` muss die Quote `5/5` sein — sonst trägt ein Kontrolltranskript eine Phrase oder `trage_ein` verändert die Ordnung ohne Signal: dann ist das ein Fehler in Aufgabe 5/6, nicht im Bericht).

- [ ] **Step 2: `BERICHT.md` ergänzen** — neuer Abschnitt direkt nach „Gate Ranking":

```markdown
## Arm B: Modell + Resonanz (offline aus denselben Antworten)
(a) <..>/5 · (b) <..>/5 · (c) <..>/5 · (d) Kontrolle <..>/5.
Gegenüber Arm A: <ein Satz je Fall, wo B gewinnt, verliert oder gleich bleibt>.
Grenze: B kann das Modell nur um eine Stufe korrigieren — liegt die Modellzahl für X zwei Stufen über Y, bleibt X vorn (so gewollt, D4).
```

- [ ] **Step 3: Commit**

```bash
git add docs/begriffsboard-resonanz/rauchtest-tabellen.md docs/begriffsboard-resonanz/BERICHT.md
git commit -m "Begriffsboard-Resonanz: Arm B offline ausgewertet (t_9258d2e9, Aufgabe 7)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Expected: `git show --stat HEAD | tail -1` → `2 files changed`.

---

### Task 8: AGENTS.md und Abschluss-Prüfung

**Files:**
- Modify: `AGENTS.md` (Modultabelle nach der Zeile `begriffsboard.py`; Schicht „Fachlogik" in der Modulkarte; Tabelle „Wo man anfängt"; neuer Übergabe-Block am Ende von „Was bewusst fehlt", nach dem Block „Die Übergaben der Karte t_4517d4ad")

- [ ] **Step 1: Modultabelle** — direkt unter der Zeile `| \`begriffsboard.py\` | … |` einfügen (die zweite Zeile nur, wenn Aufgabe 5 gebaut wurde):

```markdown
| `begriffsboard_analyse.py` | Die fokussierte Analyse-Schicht des Begriffsboards (04.10.2026, Karte t_9258d2e9): **ein** Schema-Aufruf mit zwei Fragen — `wunsch` je Boardbegriff (−2…2) und `verhoerer` (STT-Hörfehler nach Sinn, nicht nach Zahl). **Nicht live**: Aufrufer ist allein `scripts/rauchtest_begriffsboard_resonanz.py` (Test `test_kein_live_aufrufer`); ob ein zweiter Live-Aufruf kommt und mit welchem Modell, entscheidet Birk (`docs/begriffsboard-resonanz/BERICHT.md`). EN-Anweisung als Modulkonstante |
| `begriffsboard_resonanz.py` | Die gezählte Resonanz (04.10.2026, Karte t_9258d2e9): Zustimmungs-/Ablehnungsphrasen im Fenster nach (120 Zeichen) und direkt vor (25) jeder Nennung eines Boardbegriffs, geklemmt −3…3, dünn als `resonanz` am Eintrag; `begriffsboard.sortiert` nimmt `wunsch` = `zustimmung` + höchstens eine Stufe. **Kein Modell, keine Datenbank, kein Transkripttext im Ergebnis**; Wortlisten je Sprache über `sprache.je_sprache` |
```

- [ ] **Step 2: Modulkarte, Schicht „Fachlogik"** — in der Zeile `| **Fachlogik** | … \`begriffsboard.py\` · …` hinter `\`begriffsboard.py\`` einfügen: `` · `begriffsboard_resonanz.py` · `begriffsboard_analyse.py` `` (die Resonanz nur, wenn gebaut).

- [ ] **Step 3: „Wo man anfängt"** — neue Zeile unter der Begriffsboard-Zeile (nur, wenn Aufgabe 6 gebaut wurde):

```markdown
| Warum steht ein Begriff im Board oben? | `begriffsboard.sortiert` → `begriffsboard_resonanz.wunsch` → `resonanz_je_begriff` |
```

- [ ] **Step 4: Übergaben** — am Ende von „Was bewusst fehlt" anfügen:

```markdown
Die Übergaben der Karte t_9258d2e9 (Begriffsboard-Resonanz, 04.10.2026) —
offen, jeweils mit Grund:

- **Der fokussierte Zweitaufruf ist gebaut und gemessen, nicht verdrahtet.**
  `begriffsboard_analyse.analysiere` hat keinen Live-Aufrufer; die Zahlen
  (Trefferquote je Fall × Arm × Modell, Token, Latenz, Hochrechnung je
  Diskussion) stehen in `docs/begriffsboard-resonanz/BERICHT.md`. Live ja/nein
  und welches Modell: Birk (Geld, Modellwahl).
- **Die Mehrheitsregel für Verhörer im Board-Prompt ist unverändert.** Arm D
  des Rauchtests misst „Sinn zuerst" nur als String im Skript; eine Änderung
  an `prompts/begriffsboard.md`/`sprachen/en/prompts/begriffsboard.md` ist
  Birks Entscheidung auf Grundlage des Berichts.
- **Resonanz-Fenster ungemessen an echten Diskussionen** (nur, wenn gebaut):
  120/25 Zeichen und der Bonus ab zwei Signalen sind an drei erfundenen
  Transkripten geprüft (`tests/test_begriffsboard_resonanz.py`), nicht an
  Schüler-Diskussionen. Die deutsche Phrasenliste ist ungemessen.
- **Keine Sprechertrennung**: ein „yes" kann die Sprecherin zu sich selbst
  sagen — die Resonanz verschiebt deshalb höchstens um eine Stufe.
- **Sprachfund nicht gelöst**: das Board-Modell antwortet im EN-Board
  manchmal deutsch („weather" → „Wetter"); der Rauchtest akzeptiert beides,
  behoben ist es nicht (eigene Karte).
- `scripts/rauchtest_begriffsboard_resonanz.py` — **kein Test, läuft nie
  automatisch, kostet Geld**; Kartendeckel über die Rohdatei
  `korpus/berichte/begriffsboard_resonanz_roh.jsonl` (gitignored).
```

Ist das Gate „Praemisse widerlegt" ausgefallen, statt des Punkts „Resonanz-Fenster …" diesen Punkt einsetzen: `**Resonanz (D4) nicht gebaut**: der Messlauf vor dem Einbau ergab „Praemisse widerlegt: Rezenz-Fix reicht fuer diese Faelle" (Bericht, Abschnitt „Gate Ranking"). Der Plan für den Einbau steht in docs/superpowers/plans/2026-10-04-padua-begriffsboard-resonanz.md, Aufgaben 5–7.`

- [ ] **Step 5: Abschluss-Suite bis zum Ende**

```bash
$PY -m pytest -q -p no:cacheprovider --ignore=tests/e2e -m "not dortmund" > .suite.log 2>&1; echo EXIT $?
tail -3 .suite.log
```

Expected: `EXIT 0`; die Zählzeile hat gegenüber der Baseline aus Aufgabe 1 **mehr** `passed` (Aufgaben 2, 3, und ggf. 5, 6) und kein `failed`. Vorbestehende rote Tests aus Aufgabe 1 dürfen rot bleiben, neue nicht.

- [ ] **Step 6: Profil und Sprache**

```bash
$PY -m scripts.pruefe_profil padua-2026; echo EXIT $?
$PY -m scripts.pruefe_sprache padua-2026 > /tmp/t9258_sprache_nachher.log 2>&1; echo EXIT $?; tail -3 /tmp/t9258_sprache_nachher.log
```

Expected: beide `EXIT 0`.

- [ ] **Step 7: Commit**

```bash
git add AGENTS.md
git commit -m "AGENTS.md: Begriffsboard-Resonanz und Analyse-Schicht, Uebergaben (t_9258d2e9, Aufgabe 8)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Expected: `git show --stat HEAD | tail -1` → `1 file changed`.

---

### Task 9: Entscheidungsvorlage für Birk — „Zweitaufruf live ja/nein, welches Modell" (kein Code)

**Files:**
- Modify: `docs/begriffsboard-resonanz/BERICHT.md` (Schlussabschnitt)

Der Coder entscheidet hier **nichts** und verdrahtet nichts; er stellt die gemessenen Zahlen zusammen.

- [ ] **Step 1: Schlussabschnitt anfügen**

```markdown
## Entscheidung für Birk

1. **Ranking:** <"Resonanz eingebaut (Arm B …/5 gegen Arm A …/5 in (b)/(c))" | "Praemisse widerlegt, nichts eingebaut">.
   Reicht das, oder soll zusätzlich `wunsch` aus dem Zweitaufruf (Arm C: (a) …, (b) …, (c) … je Modell) in die Sortierung?
2. **Verhörer:** <Gate-Zeile>. Optionen, billigste zuerst:
   - Prompt „Sinn zuerst" statt Mehrheitsregel (Arm D: (e) …/5, (f) …/5, (g) …/5) — kein Zusatzaufruf, aber Prompt-Änderung (Korpus-/Rauchtestlauf danach).
   - Zweitaufruf kombiniert (Arm C) mit <Modell>: (e)/(f)/(g) …; Kosten je 45-min-Diskussion <CHF> (Hochrechnung), Latenz Mittel <ms>.
   - Zweitaufruf nur Verhörer (Arm E): (e)/(f)/(g) …; Kosten <CHF>.
3. **Empfehlung aus den Zahlen** (ein Satz, als Vorschlag markiert): <…>.
4. **Nicht gemessen:** Claude-Weg; weitere Infomaniak-Modelle (Mistral-Small, Ministral, Qwen) — `--modell <name>`, erst nach Freigabe im Konto.

| Arm | Modell | (a) | (b) | (c) | (d) | (e) | (f) | (g) | Eingabe-Token Ø | Latenz ms Ø | CHF je 45-min-Diskussion |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | … | | | | – | | | | | | |
| B | … | | | | | – | – | – | – | – | 0 |
| C | … | | | | – | | | | | | |
| D | … | – | – | – | – | | | | | | |
| E | … | – | – | – | – | | | | | | |
```

Leere Zellen mit den Werten aus `rauchtest-tabellen.md` füllen; „–" heißt „Arm läuft auf diesem Fall nicht". Ohne Zugang (Aufgabe 0) bleibt die Tabelle leer mit dem Satz „Messung ausstehend".

- [ ] **Step 2: Prüfen und committen**

```bash
grep -c "## Entscheidung für Birk" docs/begriffsboard-resonanz/BERICHT.md
grep -c "| A |" docs/begriffsboard-resonanz/BERICHT.md
git add docs/begriffsboard-resonanz/BERICHT.md
git commit -m "Begriffsboard-Resonanz: Entscheidungsvorlage fuer Birk (Zweitaufruf live, Modell) (t_9258d2e9, Aufgabe 9)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git log --oneline main..HEAD
```

Expected: `1`, `1` (bzw. mehr, falls mehrere Modelle eine A-Zeile haben); im Log die Commits der Aufgaben 2–9 (ohne die entfallenen), kein Merge nach `main`, kein Push.

- [ ] **Step 3: Kartenbericht** — in die Karte t_9258d2e9 schreiben: Baseline- und Schluss-Zählzeile der Suite (Aufgaben 1/8), beide `EXIT 0` von `pruefe_profil`/`pruefe_sprache`, die zwei Gate-Zeilen wörtlich, die Zahl der bezahlten Aufrufe (`wc -l korpus/berichte/begriffsboard_resonanz_roh.jsonl`) und die Summe `Kosten CHF` aus `rauchtest-tabellen.md`, und den Satz „Entscheidung Zweitaufruf live/Modell und Mehrheitsregel: Birk, siehe docs/begriffsboard-resonanz/BERICHT.md".

---

## Abdeckung der Karte (Selbstprüfung)

| Anforderung | Aufgabe |
|---|---|
| Was zusätzlich gemessen wird und warum robuster (D1, D2, D3, D7 abgewogen) | Abschnitt „Abwägung", 5 |
| Verprobung gegen das echte Modell nach Vorbild `rauchtest_begriffsboard.py`, Fälle a–g, Arme A–E, Wiederholungen, Deckel vorab | 3, 4 |
| Frühes Messen vor dem Einbau mit Gate (b)+(c) ≥ 4/5 | 4 |
| Resonanz additiv und dünn, `sortiert`-Grundgerüst bleibt, Eintrag ohne Resonanz sortiert wie heute | 5, 6 |
| Kombinierte Analyse `analysiere` + Nur-Verhörer-Variante + Prompt-only-Arm | 2, 3 |
| Token/Latenz gemessen, Kosten-Hochrechnung | 3, 4, 9 |
| Modellkandidaten aus dem Code, nur konfigurierte Modelle gefahren | Abwägung, 4 |
| Live-Verdrahtung und Prompt-Mehrheitsregel = Birk | 9, 8 (Übergaben) |
| Bestehende Begriffsboard-Tests grün, Suite `-m "not dortmund"`, `pruefe_profil padua-2026`, `pruefe_sprache` 0 | 1, 6, 8 |
| Sprachfund nicht mitgelöst | 3 (Prüfung akzeptiert „Wetter"), 8 |
| Parallelkarte t_cb2c4678: minimaler Eingriff, Konfliktstellen benannt | 0, 6 |
