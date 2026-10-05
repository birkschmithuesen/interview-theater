# Feedbackloop Padua Phase 1+2 -- Bericht

- Karte: "Padua P1-2 Feedback-Schleife: alle offenen Automatik-Befunde (Simulation + Prompt-Check) fixen bis gruen" (`.cc-card.md`)
- Branch: `wt/robo-fbl`, Stand Runde 1 bis `a3311c9`
- Basis: `origin/main` `61d9f81` (Rebase nach Merge `p1-bleiben`; Inventur lief auf `9780250`)
- Befundliste/Plan: `docs/superpowers/plans/2026-10-05-p12-feedbackloop.md`; Ledger `.superpowers/sdd/progress.md`
- Abnahme: kein "hoch", Prompt-Check ohne Kategorie-a in P1/P2, Suite gruen (`-m "not dortmund"`)

## Runde 1

### Gefixt in Runde 1 (Befund -> Commit)

| Task | Befunde | Commits |
|---|---|---|
| T1 Prompt-Hygiene EN | P1-H3, P1-N3, P1-L2, P1-L3, P1-L4, P2-H1b, P2-M1, P2-M3 (Kopf), P2-N3, AGG-1 (Satz in `system.md`) | `632f9ee`, `b310ce9`, `b03ca18` |
| T2 A/B-Vergleich | P2-H2, P2-H2b/R-3, P2-H3 (Karte), P2-N1 | `76f4cb6`, `310269c` |
| T3 Kontext/Board | P1-L1, P1-L6, AGG-2, R-1 | `0124ddb`, `8f57f6e` |
| T4 Antwortweg | P2-M9 (Echo), P2-M4 (Marker-Leak) | `c63e210`, `c861601` |
| T5 Werkbank P2 | P2-H4 | `5154314` |
| T6 Web-UI P1 | P1-H1b, P1-M3, P1-M4 (P1-M1 nur gemessen) | `083bbaa`, `7cd5550` |
| T7 e2e-Wackler | R-2 (Ursache: BotAttrappe) | `393db5b` |
| T8 Fixture | P1-L7 | `8d8abf8` |
| T9 vormals BLOCKED | P1-M2, P1-N2, P1-L8/P2-N2, P2-M5 | `0db091a` |
| T10 | R-5a (Undo nach Neustart), P2-H3 Rest ("Noted:" doppelt), Freitext im Einzeldurchgang | `351ab13`, `e3718a4`, `b9bc61a`, `a3311c9` |

Volle Suite: zuletzt nach T4 gelaufen (7931 passed, 10 skipped, 644 s); nach T5-T10 nur
gezielte Tests (gruen laut Reports). Volle Suite fuer den Stand `a3311c9` steht noch aus.

### Simulation (handy, Persona giulia, 11 Stationen p12)

Lauf `simulation/browser_laeufe/2026-10-05-handy-giulia-p12/`, Rohbericht
`simulation/berichte/feedbackloop-p12-2026-10-05-r1.md`. Richter roh: 12 hoch / 16 mittel /
8 niedrig. Nach Sichtung (Screenshots, `sim.db`, `schritte.jsonl`) bleiben als Produktbefund:
**2 hoch, 5 mittel, 4 niedrig**; der Rest ist by design (B3/B6), Sim-Artefakt oder liegt in
den separaten Branches B1/B4. Laptop-Lauf (priya) fand in Runde 1 nicht statt.

Wichtig fuer die Einordnung: Die Persona tippte in `p1-kalibrierung` ihre Begriffe in den
Chat, der Bot speicherte sie ("Updated - saved ... Move on?"), die Persona drueckte "Move on"
(Schritt 9, `phase=2` um 13:53:57). Ab da liefen die Stationen `p1-zuhoeren`, `p1-begriffe`,
`p1-uebergang` in Phase 2 -- alle Richter-Befunde "Phase 1, aber Fragen-Durchgang / Phase 2
aktiv" sind deshalb Sim-Zuordnung, kein Produktfehler. Eine echte Diskussion mit "Discussion
done" fand nie statt (Board 0 -> 4 ohne Neuladen bestanden).

**hoch**

| ID | Station | Was | Klasse | Beleg |
|---|---|---|---|---|
| S1 | p2-eigene-fragen .. p2-uebergang | **Sackgasse im Einzeldurchgang.** Frage 11: "Sharpen" gedrueckt -> `_entferne_tastatur` nimmt die ganze Leiste der Karte (auch Accept/Discard) weg, "What do you want to change?" kommt ohne Knoepfe. Jede weitere Nachricht kommt mit unveraenderter Frage zurueck; der T10-Zweig (`knoepfe/fragen.py:937-941`) sendet nur Text, nie wieder die Karte. Frage 12 ist unerreichbar; 9 Persona-Schritte im Kreis; Bot erfindet UI ("Accept 11 below", dann "there is no accept button ... go straight to the next question", "I can't bring up the next question"). Kommentar "Die Karte darueber bleibt die bedienbare" stimmt nicht. | A | `100-…`, `106-…`, `130-…png`; `sim.db` knopf 51/52 nie benutzt, 53 (Sharpen) benutzt; nachricht 55-71 |
| S2 | p2-eigene-fragen, p2-eroeffnung | **Erkenner schreibt eigene Fragen vor dem Vergleich in `fragen`** ("📌 Agreed: Questions ..." msg 21/24). Folgen: Werkbank "Questions ✓ 1 of 3", obwohl der Durchgang bei 11/17 haengt; Border-Frage doppelt (alte + geoeffnete Fassung angehaengt statt ersetzt); widerspricht "Never claim the questions have been saved". | A (mit wt/robo-b4 abstimmen) | `124-…png`; `arbeitsstand.fragen` (5 Zeilen, Border doppelt) |

**mittel**

| ID | Station | Was | Klasse | Beleg |
|---|---|---|---|---|
| S3 | p2-uebergang | Bot erklaert die Reihenfolge als Sperre ("The questions get finished here first, then the interviews come") und die Phasenleiste nur vermutend ("most likely just shows the next station"). Ursache Prompt: `workshop/padua-2026/prompts/phasen/2.md:83-84` "The order is fixed", `system.md` "stations", keine Zeile zum Stepper. | A | `132-…png`, nachricht 73/75 |
| S4 | p2-eigene-fragen, p2-ab-vergleich | Neue eigene Frage waehrend des Durchgangs kann nicht aufgenommen werden; Bot: "keep them on your paper". | B4-Branch | nachricht 57-65, `080-…png` |
| S5 | p1-kalibrierung | Eine Korrektur-Nachricht erzeugt zwei Speicherquittungen mit zwei Undo ("Updated - saved" + "Noted: Corrected: foam -> home ..."). | A | `015-…png`, knopf 3/4, erkenner_lauf 1/2 |
| S6 | p1-eintritt | Raumcheck-Karte und laufender "Listening (0:13)"-Zaehler gleichzeitig. | B1-Branch | `009-…png` |
| S7 | p1-begriffe | Zurueck zu Phase 1 ueber den Stepper: Modal "Go to 1 · Terms / Stay here" ueberdeckt Karte und Eingabe. | B (neu) | Richter p1-begriffe |

**niedrig**

| ID | Station | Was | Klasse | Beleg |
|---|---|---|---|---|
| S8 | mehrere | Gruppentitel "Padua UX-Simulation" (sticky) schneidet die oberste Blase an. | A | `100-…png`, `015-…png` |
| S9 | p1-zuhoeren | "The sense is unchanged." als Erklaerung einer Umformulierung -- vage; Gruppe sieht die Aenderung nicht. | A (Prompt) | nachricht 23/28 |
| S10 | p1-eintritt | "Terms" in der Begruessung unklar -> sofortige Rueckfrage. | A (Text) | nachricht 3-5 |
| S11 | p1-begriffe, p2-eigene-fragen | "✓ Accepted" je Frage ohne ↶. | B (neu) | `035-…png`, `056-…png` |

**Nicht als Produktbefund gezaehlt**
- by design: starrer Einzeltakt/17 Fragen (B3), Aufnahmeknopf P1/P2 (B6), Bot antwortet kurz waehrend des Mithoerens (B2).
- Sim (Karte t_fc2c1bfa): `.phase-knopf[data-phase="1"]` nicht gefunden (Schritt 25) -- Padua rendert mit `phasennav_stepper = true` (`workshop/padua-2026/profil.toml:172`) nur `.stepper-segment[data-phase]`, keine Roadmap-Knoepfe (`web_vereint.py:2018`); `simulation/browser_aktionen.py:47` muss den Stepper kennen. Weiter: Stationen folgen nicht der echten Phase (s. o.); Zaehler "mehrere Fragen pro Nachricht" (16-70 je Station) zaehlt Fragekarten mit (P2-H5); `p1-uebergang` ohne Screenshots; Kalibrierung/Aufnahme stoppt mit Fake-Mikro ("Start listening" erscheint wieder, `015-…png`), nicht weiter untersucht.
- Entwickler-Meta im Chat: 0. Board auf Geraet B: bestanden, ohne Reload.

### Prompt-Check

Dump `docs/prompt-audit/2026-10-05-padua-p12-r1/` (Mechanik + 2 Opus-Lesungen). Vergleich mit
Runde 0 (`docs/prompt-audit/2026-10-05-padua-p12/lesung.json`):

| Phase | a | b | c | d | Summe |
|---|---|---|---|---|---|
| P1 Runde 0 | 3 | 6 | 1 | 5 | 15 |
| P1 Runde 1 | 4 | 4 | 2 | 5 | 15 |
| P2 Runde 0 | 3 | 5 | 1 | 5 | 14 |
| P2 Runde 1 | 4 | 4 | 2 | 5 | 15 |

Alle sechs a-Treffer aus Runde 0 sind weg ("Yes, save"-Zeremonie, FRAGENAUSWAHL "exactly ten",
Szenenform frueh, "three per term"). Die acht neuen (sieben verschiedene Stellen) am Dump geprueft:

| # | Dump:Zeile | Zitat | echt? | Quelle | Fix |
|---|---|---|---|---|---|
| a1 | P1 01:11 | "seven stations" (Nutzerteil "Current phase") | **echt** -- Bot sagt live "station" (nachricht 73) | `sprachen/en/prompts/system.md:7` ff. | "station(s)" -> "phase(s)" im EN-System, Erklaerzeile "appears as Current phase" streichen |
| a2 | P1 01:291 / P2 05:290 | "In Terms and Questions a suggestion saves itself the moment you make it" | **echt** (Wortlaut): stimmt nur fuer die Begriffsliste aus Gruppenaussage; in Padua P2 wird nichts gespeichert (gleicher Prompt: "Never claim the questions have been saved") | `system.md:270` | "In Terms, the corrected list you write from what the group said saves itself ...; in Questions nothing is saved until the one-by-one decisions" |
| a3 | P1 01:372 / P2 05:372 | US-Modell-Frage "when the group enters the scene phase" | **Fehllesung** (beim Eintritt = vor dem ersten Szenenlauf; Bot soll sie ohnehin nie stellen), fuer P1/P2 nur Ballast | `system.md:352` | billig: "just before the scene phase starts" |
| a4 | P1 01:457 | "a message lists the top five as saved" | **by design** (Top-5-Autosave, Birk `d41d40f`) | `workshop/padua-2026/prompts/phasen/1.md:7` | keiner; Ausnahme klaeren (Frage NB1). Fixture-Widerspruch 9 Begriffe vs. "first five" ist Kategorie d |
| a5 | P2 15:15 | "exactly THREE ... for EVERY term" | **by design** (B3: Anzahl nicht reduzieren) | `sprachen/en/prompts/fragen_ki_vorschlag.md:11` | keiner; Ausnahme klaeren (NB1) |
| a6 | P2 05:624 | "You: Changed since - please fix it in the work status" | **Fixture-Artefakt**: Produkttext ist "Changed since." (`texte.toml:58`) und wird von `kontext._SYSTEMANFAENGE_EN` gefiltert; die Fixture schreibt einen erfundenen Wortlaut | `scripts/fixture_padua_voll.py:507` | Fixture auf den echten Wortlaut |
| a7 | P2 05:534 | "Never offer the order as a choice. The order is fixed" | **echt**, P2-relevant (S3) | `workshop/padua-2026/prompts/phasen/2.md:83-84` | "Don't push interviews while questions are being written -- if the group wants to interview now, that is its decision" |

Ergebnis: 3 echte a-Stellen (a1, a2, a7), 1 Fehllesung mit Billig-Fix (a3), 2 by design
(a4, a5), 1 Fixture-Artefakt (a6).

Mechanik: alle "ask whether"-Treffer (P1 Z307/346, P2 Z307/346/469/531) sind Verbote oder
keine Speicher-Rueckfrage -- falsch positiv; "Yes, save" Z289 ist die echte Knopfbeschriftung.
Groesse P1 System 31145 Zeichen (+6029 gegen Basis 02.10.).
**"05-gespraech-phase2: CoThinker im Verlauf erwaehnt, Board-Block fehlt"** -- kein
Produktfehler: `kontext._baue_board`/`_baue_begriffe_detail` laufen seit T3 in jeder Phase
(datengetrieben), aber `scripts/fixture_padua_voll.py:718` legt Diskussion und Board nur fuer
`phase == 1` an. Dieselbe Luecke erzeugt den P2-d-Befund ("From your term discussion:"
versprochen, nicht geliefert). Fix in der Fixture (Board/Diskussion/`begriffe_detail` fuer
alle Phasen), sonst prueft der Check Birks "Der Chat muss immer alles wissen" in P2 nicht.
Weitere Fixture-Artefakte (d/b): P2-Verlauf endet mit "You:" unter "Now:",
"Your three are saved" (`scripts/fixture_padua_voll.py` ~Z. 99-102).

### Offen nach Runde 1 und warum

- S1, S2, S3, S5, S8-S10, a1/a2/a3/a7, Fixture (a6, Board in P2): Klasse A, Runde 2.
- B5 ("[suggested]" in P1/P2 nicht im Prompt, ab P3 nur offen und markiert): entschieden, in Runde 1 nicht gebaut -> Runde 2.
- P1-H2 Rest: `phasen/1.md` sagt noch "say nothing at all" waehrend des Mithoerens; B2 erlaubt einen kurzen Satz -> Prompt-Widerspruch, Runde 2.
- P1-M1 Blasenreihenfolge: braucht Spalte/Sortierschluessel in `aufnahme.py`/`repo.py`/`db.py` (T6 gemessen).
- AGG-1 Rest: Kopfzeilen-Texte "From your term discussion:"/"Why you chose these terms:" in `texte.toml` nicht angefasst.
- T10-Rest: eine im Durchgang verworfene Frage kann der Erkenner aus altem Verlauf wieder anhaengen (keine gespeicherte Verworfen-Menge).
- 18 rote e2e in `tests/e2e/test_web_gestalt_e2e.py` (Fake-Mikro-Timing, auch auf Basis); `web_chat.py:657` ungueltiges Escape `\s` in `_CHAT_JS`.
- `roadmap.fragenuebersicht`: Restzeilen ohne Begriffspraefix unsichtbar; `_fragetext` teilt am ersten ":" (T9 minor).
- B1 (P1-H1, S6) und B4 (P2-H6, S4): separat in `wt/robo-b1`/`wt/robo-b4`, hier nicht angefasst.
- Klasse B offen: R-5b (Undo-Umfang der Abschlussnachricht), AGG-3 (Fliesstext gegen Transkript), neu NB1-NB3 (s. Rueckmeldung).
- Sim-seitig (t_fc2c1bfa): Stepper-Selektor, Stationen an echte Phase koppeln, Fragekarten-Zaehler.

### Kosten bisher

- Simulation handy Runde 1: 0.0425 CHF (Erkenner gemma 0.0342, Journal 0.0013, Whisper 0.0070; Gespraech und KI-Fragen liefen ueber claude-opus-5-5/Proxy, 0 CHF).
- Opus-Lesungen Prompt-Check: 4 Aufrufe ueber den lokalen Proxy, 0 CHF.
- Summe: 0.0425 CHF (harte Grenze 1.50 CHF).

## Runde 2

Stand `fce1392`. Task-Reports `.superpowers/sdd/R2-*-report.md`.

### Gefixt in Runde 2 (Befund -> Commit)

| Task | Befunde | Commits |
|---|---|---|
| R2-1 Sackgasse Einzeldurchgang | S1 (Accept/Discard bleibt nach "Sharpen"; Review: spaete Schaerfung ueberschreibt nicht die naechste Frage, spaet verworfene schickt keine Fehlzeile) | `70bf096`, `0747a69`, `6240c97` |
| R2-3 EN-Prompts | a1 ("stations" -> "phases"), a2 (Autosave-Satz Terms/Questions), a3 (US-Frage "before the scene phase"), a7/S3 (Reihenfolge nicht als Sperre, Zeile zur Phasenleiste), S9 (Schaerfen: konkret nachfragen), S10 (Begruessung erklaert "terms") | `f7490f3` |
| R2-4 Fixture | a6 (echter Wortlaut "Changed since."), Board/Diskussion/`begriffe_detail` in jeder Phase, P2-Verlauf endet mit Gruppenzug | `18560d7` |
| R2-6 Chat-Kante | S8 nur optisch (Maske/Ausblendung oben, `padding-bottom`); echter Fix braucht die Scroll-Logik in `web_chat.py` (Branch `wt/robo-b1`) | `fce1392` |

Nicht gebaut: S2 (Erkenner speichert eigene Fragen vorzeitig; Klasse-B-Entscheidung B4 wird in
`wt/robo-b4` gebaut), S5, B2, B5 (nicht entschieden bzw. nicht dran), P1-M1.

Volle Suite nach Runde 2: **8021 passed, 10 skipped, 0 failed** (650 s, `-m "not dortmund"`).

### Simulation (handy, giulia, 11 Stationen p12)

Lauf `simulation/browser_laeufe/2026-10-05-handy-giulia-p12/` (Runde 2 = `chat_id 7000000000001`
in `sim.db`, Schritte 68-132 in `schritte.jsonl`; die Screenshots 001-131 sind jetzt die von
Runde 2), Rohbericht `simulation/berichte/feedbackloop-p12-2026-10-05-r2.md`. Richter roh:
13 hoch / 21 mittel / 13 niedrig. Nach Sichtung bleiben **2 hoch, 6 mittel, 3 niedrig**.

Ablauf laut `sim.db`: P1 sauber bis zur korrigierten Begriffsliste; um 16:06:22 Phase 2 ueber den
Knopf "Yes, on to the questions" (knopf 64, `phase=2`) -- die Persona wollte laut Begruendung
"Change something" druecken; zwei Sekunden vorher kam die Board-Nachricht (msg 106) mit eigenen
Knoepfen dazu, die Elementnummern haben sich verschoben (Sim). Um **16:07:38 sprang die Gruppe ohne
eigenes Zutun in Phase 3** (s. H1). Ab Station `p2-eigene-fragen` lief die Persona deshalb in
Phase 3 und kreiste ~40 Schritte zwischen Workbench-Zeile "2 · Questions 3 of 3" und dem Sheet
"Go to 2 · Questions / Stay here", ohne je einen der beiden Knoepfe zu druecken.
KI-Vergleich und Einzeldurchgang wurden in Runde 2 **nie erreicht**.

**hoch**

| ID | Station | Was | Klasse | Beleg |
|---|---|---|---|---|
| H1 | p1-begriffe (real P2) | **Redo eines Erkennerlaufs mit eigenen Fragen ueberspringt Phase 2.** Undo/Redo der vom Erkenner gespeicherten eigenen Fragen (lauf 13, S2) -> `_wirkung_redo` sieht `fragen` gesetzt und keine Eroeffnung -> `starte_eroeffnung` -> Autosave der Eroeffnung (`schreibe_eroeffnung_automatisch`) -> `uebergang_nach_speichern` -> Phase 3. KI-Vergleich, Einzeldurchgang und Lead-ins fallen aus; Workbench zeigt "2 · Questions ✓ 3 of 3"; der P2-Prompt-Hinweis "The material would allow phase 3" (Lesung P2 b637) kommt aus derselben Voraussetzung. | A | knopf 71 (redo 13) 16:07:33; msg 119/120/124 und `phase_gesetzt_am` 16:07:38; `interview_theater/knoepfe/wirkung.py:1645-1654`, `knoepfe/fragen.py:1388-1392`, `knoepfe/stationen.py:38-51`; `fragen_herkunft_final` leer |
| S2 | p1-zuhoeren (real P2), weiter in P3 | Erkenner schreibt eigene Fragen vor dem Vergleich in `fragen` ("📌 Agreed: Questions ..."), auch in Phase 3 noch zweimal (msg 143/146). Ausloeser von H1. | B4-Branch | msg 113, 143, 146; `erkenner.py:2106` (`_AUTOSAVE_FELDER_1_2` enthaelt `fragen`) |

**mittel**

| ID | Station | Was | Klasse | Beleg |
|---|---|---|---|---|
| S5 | p1-kalibrierung, p1-zuhoeren | Weiter zwei Quittungen je Korrektur ("Updated – saved ... Move on?" + "Noted: Corrected: foam -> home"); neu "Noted: Removed: Terms" (Feld geleert, weil gleich neu gesetzt) -- die Gruppe fragt "what did you remove?". | A | msg 90/91, 98/99, 104; erkenner_lauf 8/9; `erkenner.py:2160-2168` |
| M1 | p1-begriffe (real P2) | Interner Marker **"ABSCHLUSS:"** steht im Chat (Vorschlag und 📌-Zeile der Eroeffnung). Ursache: EN-Prompts verlangen den deutschen Marker; `_teile_eroeffnung` (`knoepfe/fragen.py:1295`) versteht auch "closing". | A | msg 119, 120; `sprachen/en/texte.toml:550`, `sprachen/en/prompts/system.md:147`, `workshop/padua-2026/prompts/phasen/2.md:126` |
| M2 | p1-begriffe | Undo der automatisch gespeicherten Eroeffnung ist sofort weg (knopf 72 in derselben Sekunde angelegt und verbraucht, beim Phasensprung); das naechste "Undo" der Persona trifft ein altes Begriffs-Undo -> "That's changed since then". Ursache noch zu messen. | A | knopf 72 `erstellt_am = benutzt_am` 16:07:38; knopf 58 16:08:04; msg 129 |
| M3 | p2-* | Workbench: abgeschlossene Phase zeigt nur "3 of 3" (Aufgaben, die Persona liest es als Fragenzahl), keine Fragentexte; Tippen auf die Zeile oeffnet das Sprung-Sheet (S7) statt den Inhalt. | B (neu) | `067-…png`, `097-…png`; `roadmap.werkbank`, `web.py:3317` |
| M4 | p1-zuhoeren | Zwei konkurrierende Angebote fuer denselben Begriffsbeschluss binnen 2 s: Autosave-Liste "Move on?" (Reihenfolge der Gruppe) und Board-Ende "Take these?" (andere Reihenfolge). Laut `d41d40f` ist "Take these" neben eigenen Begriffen gewollt -- die Kollision nicht. | B (neu) | msg 105/106, knopf 64/67 |
| S6 | p1-eintritt, p1-kalibrierung | Kalibrier-Panel und "Listening (…)"-Chip gleichzeitig; Panel schiebt die Eingabe aus dem Bild; erster Schritt sagt nicht "bitte still sein". | B1-Branch | Richter p1-eintritt/-kalibrierung |

**niedrig**

| ID | Station | Was | Klasse | Beleg |
|---|---|---|---|---|
| S8 | mehrere | Oberste Blase weiter angeschnitten, jetzt ausgeblendet; Richter wertet es weiter (p2-eigene-fragen). | B1-Branch (Scroll-JS) | `027-…png` |
| N1 | p1-eintritt | "The room check shows its own result on screen, so I can't judge the volume from here." -- Selbsterklaerung statt Hinweis. | A (Prompt, klein) | msg 83 |
| N2 | p1-zuhoeren | Transkript-Segmente linksbuendig wie Bot-Blasen. | B1 / P1-M1 | Richter p1-zuhoeren |

**Ausserhalb P1/P2 (Folge von H1, Phase 3):** Kimi antwortet einmal deutsch ("Die Interviewphase
laeuft bereits ...", msg 142); "I won't note them myself -- the system records what you decide"
(msg 145) und zwei Zuege spaeter "Your six questions are noted" (msg 148). Fuer die P3-Schleife notiert.

**Nicht als Produktbefund gezaehlt (Sim, Karte t_fc2c1bfa):** Fehlklick in Phase 2 durch
verschobene Elementnummern (s. o.); Persona-Schleife Workbench <-> Sheet ohne Entscheidung;
`.phase-knopf[data-phase="2"]` nicht gefunden (Schritt 125, Padua rendert den Stepper);
Stationen folgen nicht der echten Phase (alle "Phase 3 aktiv, obwohl Phase 2"-Befunde); Zaehler
"mehrere Fragen pro Nachricht" (4-84 je Station) zaehlt Karten und Statuszeilen mit;
`_TEXT_WIEDERKEHR`-Warnung im Bot-Log (Start als `__main__`). Board auf Geraet B: bestanden
ohne Reload. Entwickler-Meta im Chat: 0.

### Stand der Runde-1-Befunde

| ID | Stand | Anmerkung |
|---|---|---|
| S1 | gefixt (Tests), im Lauf **nicht geprueft** | Einzeldurchgang wegen H1 nie erreicht |
| S2 | offen, **verschaerft** | loest jetzt H1 aus (B4-Branch) |
| S3 | gefixt | Prompt-Check ohne "station"-Treffer; Frage kam im Lauf nicht vor |
| S4 | nicht erreicht | B4-Branch |
| S5 | **unveraendert** | dazu "Removed: Terms" |
| S6 | unveraendert | B1-Branch |
| S7 | unveraendert, haeufiger getroffen | jetzt auch ueber die Workbench-Zeile (M3) |
| S8 | teilweise | optisch entschaerft, geometrisch weiter angeschnitten (B1) |
| S9 | gefixt (Prompt), nicht erreicht | kein Schaerfen im Lauf |
| S10 | gefixt | Begruessung erklaert "terms"; Persona fragt trotzdem nach, Bot antwortet sauber (msg 81) |
| S11 | nicht erreicht | -- |

### Prompt-Check

Dump `docs/prompt-audit/2026-10-05-padua-p12-r2/` (Mechanik + 2 Opus-Lesungen).

| Phase | a | b | c | d | Summe |
|---|---|---|---|---|---|
| P1 Runde 1 | 4 | 4 | 2 | 5 | 15 |
| P1 Runde 2 | 2 | 4 | 3 | 5 | 14 |
| P2 Runde 1 | 4 | 4 | 2 | 5 | 15 |
| P2 Runde 2 | 1 | 8 | 1 | 5 | 15 |

Aus Runde 1 weg: a1, a2, a3, a7, a6 (Fixture), "Board-Block fehlt in P2". a5 ("exactly THREE")
wird jetzt als b gefuehrt (by design, B3). Die drei a-Treffer am Dump geprueft:

| Dump:Zeile | Zitat | echt? | Quelle | Fix (nur EN) |
|---|---|---|---|---|
| P1 01:551 | "ranked (the first five are saved as their terms)" | **by design** (Top-5-Autosave, `d41d40f`, = a4 Runde 1), aber der Satz stimmt nicht, sobald die Gruppe eine eigene Liste hat (Runde 2: gespeichert "home, belonging, border, waiting, night shift", Board-Rang anders, `begriffe_board_wert`) | `sprachen/en/texte.toml:974` (`BOARD_KOPF`) | Klammer ersetzen durch "the saved terms are the ones under Terms above" -- keine Zahl im Kopf, kein Widerspruch |
| P1 01:174 | "then one line per scene `Title — one sentence — characters — form`" | **echt** (Widerspruch zu Zeile 66 "form only in phase 7" im selben Prompt), in P1/P2 ohne Wirkung | `sprachen/en/prompts/system.md:154` | "— form" streichen; `szenenfolge.py:278` liest das 4. Feld optional |
| P2 05:95 | "under 500 characters if possible. One question, and two to three options" | **echt** (Pflichtfrage gegen Zeile 187 "at most ONE question ... only when it helps") | `sprachen/en/prompts/system.md:75` | "At most one question -- and if you offer choices, two to three options (see below)." |

Ergebnis: 2 echte a-Stellen (beide `system.md`), 1 by design mit billigem Textfix.
Weitere billige Funde aus der Lesung: c459 Entwicklervermerk "Padua Phase 1+2 card, Task 13" im
Modellkontext (`workshop/padua-2026/prompts/phasen/2.md:3-6`); c569/b647 "work status tab" statt
"Workbench" ist Fixture (`scripts/fixture_padua_voll.py:73`), ebenso die Historie, die mit vier
Bot-Zuegen beginnt (d566/d642). b637 (`_PHASENHINWEIS` waehrend der eigenen Fragen) verschwindet
mit H1-Fix in `phasen.py`. b489 ("say nothing" vs. eine Frage je Nachricht) = B2.
Mechanik: "Yes, save" Z290 ist die echte Knopfbeschriftung, alle "ask whether" (P1 Z311/350,
P2 Z311/350/475/537) wie in Runde 1 falsch positiv. P1 System 31690 Zeichen (+545 gegen Runde 1).

### Offen nach Runde 2 und warum

- H1, S5, M1, M2, N1 und die drei a-Stellen + c459 + Fixture: Klasse A, Runde 3.
- S2/S4: `wt/robo-b4` (B4); H1-Fix muss mit B4 zusammenpassen (gleicher Ausloeser).
- S6, S8-Rest, N2: `wt/robo-b1` (Scroll-/Kalibrier-UI in `web_chat.py`).
- Klasse B offen: S7 (Sheet beim Zuruecknavigieren), M3 (Workbench-Inhalt abgeschlossener Phasen,
  "3 of 3"), M4 (Board "Take these" neben gespeicherter Gruppenliste), S11 (Accepted ohne ↶),
  B2, B5, R-5b, AGG-3, NB1 (Zahl-Ausnahmen a4/a5 ausdruecklich in die Regel).
- P1-M1: braucht Spalte/Sortierschluessel (`aufnahme.py`/`repo.py`/`db.py`), nicht in dieser Schleife.
- Sim (t_fc2c1bfa): Stepper-Selektor, Stationen an echte Phase koppeln, Fragekarten-Zaehler,
  Elementnummern nach spaet eintreffenden Nachrichten neu einlesen, Schleifenbremse fuer Sheets.

### Kosten bisher

- Simulation handy Runde 2: 0.1594 CHF (Erkenner gemma 0.0616, Gespraech Kimi in Phase 3 0.0521,
  Journal 0.0026, Whisper 0.0431; Opus/Proxy 0 CHF).
- Simulation kumuliert: 0.2019 CHF (harte Grenze 1.50 CHF).
- Opus-Lesungen: 8 Aufrufe ueber den lokalen Proxy, 0 CHF.

## Runde 3

Stand `bb2454c`. Task-Reports `.superpowers/sdd/R3-*-report.md`.

### Gefixt in Runde 3 (Befund -> Commit)

| Task | Befunde | Commits |
|---|---|---|
| R3-1 Redo vor dem Durchgang | H1 (`_wirkung_redo` startet die Eroeffnung nur noch mit `fragen_herkunft_final`) | `04e226a` |
| R3-2 EN-Prompts + Marker | a-Treffer Runde 2 (`system.md:75` Pflichtfrage, `system.md:154` "— form", `BOARD_KOPF` ohne Fuenferzahl), c459 (Entwicklervermerk in `phasen/2.md`), M1 (`ABSCHLUSS:` -> `CLOSING:`, `vorschlag.ohne_marker` streicht die Unterzeile, 📌 aus zerlegtem Text) | `bf0a5b3` |
| R3-3 Eine Quittung | S5 (Erkenner haengt Transkriptkorrektur an die Quittung des Zugs; "BEGRIFFE <x>" nimmt nur diesen Begriff, leert nicht mehr das Feld) | `64b27af` |
| R3-4 Undo der Eroeffnung | M2 (`biete_stt_sprache` sendet mit `undo_behalten=True`) | `c246ae5` |
| R3-5 Fixture | c569/b647 ("Workbench" statt "work status tab"), d566/d642 (Historie alterniert) | `bb2454c` |

Nicht gebaut: N1 (kam in Runde 3 nicht wieder vor), S2/S4 (B4), S6/S8/N2 (B1), Klasse B.

Volle Suite nach Runde 3: **8041 passed, 10 skipped, 0 failed** (`-m "not dortmund"`).

### Simulation (handy, giulia, 11 Stationen p12)

Lauf `simulation/browser_laeufe/2026-10-05-handy-giulia-p12/` (Runde 3 = `chat_id 7000000000002`
in `sim.db`, msg 154-234; Screenshots 001-136 sind jetzt die von Runde 3), Rohbericht
`simulation/berichte/feedbackloop-p12-2026-10-05-r3.md`. Richter roh: 9 hoch / 19 mittel /
10 niedrig. Nach Sichtung (Screenshots, `sim.db`, `bot.log`) bleiben **3 hoch, 4 mittel,
3 niedrig** (davon Klasse A: 1 hoch, 2 mittel, 1 niedrig).

Ablauf laut `sim.db`: P1 mit fuenf Sprachsegmenten, die Persona tippt die korrigierte Liste,
**eine** Quittung "Updated – saved ... Move on?" (msg 166, ein Undo knopf 89), "Move on"
(knopf 87) -> Phase 2 um 19:18:17. Eigene Fragen per Chat, der Erkenner speichert sie vorzeitig
(S2, lauf 20-22), Undo/Redo von lauf 20 (19:19:09/19:19:16) **ohne** Phasensprung (H1 bestaetigt
gefixt). Um 19:21:25 schreibt die Gruppe "Then the list is finished for me and we can go to the
interviews"; der Zug antwortet "Own questions done. Next comes the side-by-side comparison"
und legt Karte "Question 1/27" hin (msg 187/188, 19:21:35); **sechs Sekunden spaeter setzt der
Erkenner aus derselben Nachricht `phase_setzen 3`** (msg 189 "Noted: We're now at 3 ·
Interviews", `phase_gesetzt_am` 19:21:41). Der ganze Einzeldurchgang (msg 188-234) lief danach in
Phase 3 -- mit Kimi und dem P3-Prompt statt Opus/P2-Prompt. Eroeffnung/Abschluss nie erreicht.

**hoch**

| ID | Station | Was | Klasse | Beleg |
|---|---|---|---|---|
| H2 | p2-eigene-fragen -> p2-eroeffnung | **Phasenwechsel per Chat mitten im Einzeldurchgang.** Erkenner setzt Phase 3 aus der Nachricht, auf die der Zug gerade den Vergleich gestartet hat. Die Fragekarte laeuft in Phase 3 weiter (Stepper "3 · Interviews", P2 mit ✓, RECORD INTERVIEW), das Gespraech laeuft mit Kimi/P3-Prompt ohne Wissen um den Durchgang: zweimal Deutsch (msg 198, 202), erfundene MINE/YOURS-Vergleiche, "I can't fix the 27 counter myself — that is a system display I don't control" (msg 213), Freitext ersetzt die laufende Karte durch Fragen anderer Begriffe (msg 215/218/220/222: "2/27" springt Noise -> Waiting). Gruppenwunsch war woertlich da (Invariante "Phase setzt die Gruppe"), deshalb Entscheidung noetig: offenen Durchgang beim Phasenwechsel schliessen, pausieren oder den Sprung erst nach dem Durchgang anbieten (Option A: wie R3-3 einen Merker "Zug hat auf diese Nachricht schon den Vergleich gestartet" -> `phase_setzen` faellt weg). | B (neu) | `093-…png`; msg 186-189; knopf 99-159; `aufruf` 123-155 (Kimi) |
| H3 | p2-einzeldurchgang (real P3) | **Erkenner leert `fragen` waehrend des Durchgangs.** "Noted: Removed: Questions" (lauf 24, 19:25:03): `entfernen FRAGEN` loescht alle sieben eigenen Fragen (`erkenner_lauf_schritt` 28: vorher 7 Zeilen, nachher NULL). Der Schutz `knoepfe.einzeln_aktiv` gilt nur fuer `fragen_setzen` (`erkenner.py:636-651`), nicht fuer `entfernen`. Folge: Workbench "2 · Questions 0 of 3" (Richter p2-eroeffnung), Arbeitsstand 205 -> 36 Zeichen im Prompt. Gleiche Fehlerklasse wie S5-"Removed: Terms". | A | msg 217, `bot.log` (arbeitsstand=36 ab 19:25), `erkenner.py:1497`/`1540` |
| S2 | p2-eigene-fragen | Erkenner speichert eigene Fragen vor dem Vergleich ("📌 Agreed: Questions", msg 173/180/183). Erfuellt damit `phasen.voraussetzungen` fuer Phase 3 und macht H2 erst moeglich. | B4-Branch | lauf 20-22 |

**mittel**

| ID | Station | Was | Klasse | Beleg |
|---|---|---|---|---|
| M5 | p2-ab-vergleich (Folge H2) | Ablauf-Erklaerung "So geht ein Interview: Tippt ..." **deutsch** in der EN-App. `erkenner._interviewmodus_texte` liest `knoepfe.TEXT_ABLAUF` am `T` vorbei; der EN-Eintrag existiert (`sprachen/en/texte.toml:83`, Tabelle `knoepfe.texte`). Ausloeser ist ein Chat-Satz ("then we record"), also auch aus P2 erreichbar. | A | msg 204; `erkenner.py:2396` |
| M6 | p2-einzeldurchgang (Folge H2) | Freitext waehrend des Durchgangs ueberschreibt die aktuelle Karte mit einem Modellvorschlag zu einer **anderen** Frage (Gruppe fragt nach Nr. 5, Karte 2 wird Noise, dann Waiting, dann die Frage der Gruppe). Ob das mit P2-Prompt/Opus auch passiert, ist ungeprueft. | A nach H2/B4 (`knoepfe/fragen.py` liegt in B4) | msg 214-222, `fragen_bearbeitet` ",,,1,1" |
| S6 | p1-kalibrierung | Raumcheck-Karte ("Transcribing the test sentence …", Skip) und "Listening (0:53)" + "Discussion done" gleichzeitig. | B1-Branch | `013-…png` |
| S8 | mehrere | Chat laeuft unter den Titel "Padua UX-Simulation", oberste Blase angeschnitten. | B1-Branch | `013-…png`, `093-…png` |

**niedrig**

| ID | Station | Was | Klasse | Beleg |
|---|---|---|---|---|
| N3 | p1-begriffe (real P2) | Undo/Redo wiederholt die ganze Fragenliste ("Undone: I've reverted this. / Questions: ..."), zusammen mit der 📌-Zeile dreimal derselbe Block. | B (zu R-5b) | msg 173/175/177 |
| N4 | p2-eigene-fragen | P2-Eintritt und Zug versprechen "side by side with yours"; der Durchgang zeigt die Fragen je Begriff nacheinander ("(yours)", dann "(AI)"). Persona sucht wiederholt "your version". | A (Text, `texte.toml`/P2-Prompt -- P2-Prompt liegt in B4) | msg 170, 187, 201 |
| N2 | p1-zuhoeren | Transkriptblasen ohne Korrekturmoeglichkeit an der Blase; Kopfbereich ~1/4 der Hoehe. | B1 / P1-M1 | Richter p1-zuhoeren |

**Ausserhalb P1/P2 (fuer die P3-Schleife):** Kimi antwortet in Phase 3 wieder deutsch (zum zweiten
Mal nach Runde 2, msg 142); `fragen_eigene_vorschlag` steht am Ende auf Italienisch (vermutlich ein
Kimi-Block in Phase 3 nach der Sprachwahl "Italiano", nicht gemessen).

**Nicht als Produktbefund gezaehlt:** Richter "hoch" p1-zuhoeren ("kein 📌/↶ fuer die Begriffe")
-- Fehllesung, msg 166 traegt Quittung und Undo (knopf 89). Richter "hoch" p1-kalibrierung ("We
heard … Is that what was said?") -- Raumcheck-Bestaetigung, B1-Branch/by design. "Bot schlaegt eine
fuenfte Frage vor" -- Fehllesung, "And maybe a fifth" schreibt die Persona (msg 197). 27 Fragen im
Durchgang (6 eigene + 21 KI, `fragen_herkunft`) und Einzeltakt: by design (B3). RECORD INTERVIEW /
"3 · Interviews" im Fragenteil: echte Phase 3 (H2). Sim (t_fc2c1bfa): Stationen folgen nicht der
echten Phase (Persona tippt in P3 neue "eigene Fragen", msg 197), Kopfzeile "p1-begriffe nicht
erreicht", `p1-uebergang`/`p2-uebergang` ohne Screenshots, Mehrfachfragen-Zaehler (36-64 je Station)
zaehlt Karten mit. Board auf Geraet B: 0 -> 7 ohne Reload, bestanden (spaeter 0 = P2-Tab-Inhalt,
nicht weiter geprueft). Entwickler-Meta im Chat: 0.

### Stand der frueheren Befunde

| ID | Stand | Anmerkung |
|---|---|---|
| H1 | **gefixt, im Lauf bestaetigt** | Redo knopf 93 um 19:19:16, Phase blieb 2; der spaetere Sprung ist H2 (Chat), nicht Redo |
| S1 | gefixt (Tests), per Knopf **nicht geprueft** | Durchgang erreicht, Accept 6x gedrueckt, Sharpen nie (Persona schrieb Freitext) |
| S2 | offen | B4; jetzt Wegbereiter von H2 |
| S3 | gefixt | kein "order is fixed" mehr im Dump, Frage kam nicht vor |
| S5 | **gefixt, im Lauf bestaetigt** | eine Quittung, ein Undo, kein "Removed: Terms", Begriffe vollstaendig |
| S6, S8 | unveraendert | B1 |
| S7, S9, S11 | nicht erreicht / unveraendert | S11 ("Accepted" ohne ↶) weiter Klasse B |
| S10 | gefixt | Persona fragt nach, Antwort sauber (msg 158) |
| M1, M2 | gefixt (Tests), **nicht erreicht** | Eroeffnung kam wegen H2 nie |
| M3 | unveraendert | Workbench "0 of 3" diesmal durch H3 |
| M4 | nicht erreicht | P1 endete ohne "Discussion done" |
| N1 | nicht wieder aufgetreten | offen gelassen |

### Prompt-Check

Dump `docs/prompt-audit/2026-10-05-padua-p12-r3/` (Mechanik + 2 Opus-Lesungen).

| Phase | a | b | c | d | Summe |
|---|---|---|---|---|---|
| P1 Runde 1 | 4 | 4 | 2 | 5 | 15 |
| P1 Runde 2 | 2 | 4 | 3 | 5 | 14 |
| P1 Runde 3 | 2 | 5 | 2 | 5 | 14 |
| P2 Runde 1 | 4 | 4 | 2 | 5 | 15 |
| P2 Runde 2 | 1 | 8 | 1 | 5 | 15 |
| P2 Runde 3 | 2 | 5 | 3 | 5 | 15 |

Alle drei a-Treffer aus Runde 2 und c459 sind weg (R3-2). Die vier neuen a-Treffer am Dump geprueft
-- **alle vier Saetze standen woertlich schon in den Dumps von Runde 0, 1 und 2** (r1 Z114/520/
594/485, r2 Z115/526/603/491) und wurden dort nicht als a gefuehrt; P1 Z115 fuehrt die P2-Lesung
derselben Runde als **b**. Die Treffer sind also keine Folge der Runde-3-Aenderungen, sondern
Stichproben des Lesers aus einem festen Bestand an Grenzsaetzen in 31-36k Zeichen Prompt.

| Dump:Zeile | Zitat | Urteil | Quelle | Fix |
|---|---|---|---|---|
| P1 01:115 | "You ask first, you suggest afterwards. In EVERY phase: ONE open question" | **echt, schwach**: "EVERY phase" liest sich als Pflichtfrage, auch beim Mithoeren (gegen Regel 4, gegen Z477 "no question at the end") | `sprachen/en/prompts/system.md:95` | "Before you suggest anything, ask one open question about the group's idea -- if there is nothing to suggest, there is nothing to ask." ("In EVERY phase" streichen) |
| P1 01:526 | "It is saved automatically; without a block nothing is saved" | **by design** (Autosave der Gruppenliste, `d41d40f`); Lese-Risiko: der Satz sagt nicht, dass nur Gruppenwortlaut in den Block darf | `workshop/padua-2026/prompts/phasen/1.md:70` (+ `sprachen/en/prompts/phasen/1.md:54`) | billig: Satz davor "Only terms the group said or confirmed go into the block; your own ideas stay in your text." |
| P2 05:599 | "don't say any more that saying 'we're doing an interview now' is enough: the button is the reliable way" | **by design** (Birk 05.09.2026: der Erkenner startet nicht selbst, ein Chat-Satz bringt die Ablauf-Erklaerung mit Knopf); Wortlaut klingt nach "nur der Knopf" (Regel 2) | `workshop/padua-2026/prompts/phasen/2.md:142` (B4-Datei) | nach B4-Merge: "If the group says it, the start button comes by itself; don't explain more." |
| P2 05:486 | "Reformulate cleanly, never invent. If a term's question is rough, ..." | **Fehllesung** fuer Regel 4 (die Gruppe schreibt zuerst, der Bot glaettet nur); beruehrt aber die Fairness des A/B-Vergleichs (geglaettete statt woertliche Gruppenfassung) -> Klasse-B-Frage | `workshop/padua-2026/prompts/phasen/2.md:30` (B4-Datei) | keiner ohne Entscheidung |

Ergebnis: 1 echte (schwache) a-Stelle, 2 by design mit billigem Wortlaut-Fix, 1 Fehllesung.
Die b-Treffer b632 ("The material would allow phase 3") und b651 ("Your three are saved",
Fixture) stehen weiter; b632 ist dieselbe Voraussetzung, die H2 ermoeglicht.
Mechanik: "Yes, save" Z290 echte Knopfbeschriftung, alle "ask whether" (P1 Z311/350, P2
Z311/350/470/532) wie bisher falsch positiv. P1 System 31712 Zeichen (+22 gegen Runde 2),
P2 System 36169.

**Einschaetzung Abnahmekriterium "0 a":** Mit einer einzelnen, nichtdeterministischen Opus-Lesung
je Phase ist "0 a" kein stabiler Endzustand -- jede Runde zieht 1-4 andere Grenzsaetze aus
unveraenderten Prompt-Teilen. Konvergenz waere nur ueber eine Regel erreichbar, z. B.: ein a-Treffer
zaehlt erst, wenn er nach Sichtung als echt gilt (by design/Fehllesung werden mit Begruendung
protokolliert und nicht wieder gezaehlt), oder wenn er in mindestens zwei von drei Lesungen
auftaucht. Das ist eine Entscheidung fuer Birk.

### Offen nach Runde 3 und warum

- Klasse A, Runde 4: H3 (Erkenner-`entfernen FRAGEN` waehrend des Durchgangs) + M5 (`TEXT_ABLAUF`
  am `T` vorbei), beide `erkenner.py`; Prompt P1 Z115 (`system.md:95`) und Klarstellung P1 Z526
  (`padua-2026/prompts/phasen/1.md:70`, `sprachen/en/prompts/phasen/1.md:54`).
- Wartet auf B4-Merge (`knoepfe/fragen.py`, `vorschlag.py`, `workshop/padua-2026/prompts/phasen/2.md`
  sind dort geaendert): S2, S4, M6, N4-Prompttext, P2 Z599-Wortlaut.
- B1: S6, S8, N2.
- Klasse B offen: **H2** (Phasenwechsel per Chat bei offenem Durchgang), P2 Z486 (woertliche oder
  geglaettete Gruppenfassung im Vergleich), N3/R-5b (Umfang von Undo/Redo-Meldungen), S7, M3, M4,
  S11, B2, B5, AGG-3, NB1 und das Abnahmekriterium "0 a" (s. o.).
- P3-Schleife: Kimi antwortet deutsch, italienische `fragen_eigene_vorschlag`.
- Sim (t_fc2c1bfa): Stationen an echte Phase koppeln, Mehrfachfragen-Zaehler, Uebergangs-Screenshots.

### Kosten bisher

- Simulation handy Runde 3: 0.3355 CHF (Erkenner gemma 0.1035, Gespraech Kimi in Phase 3 0.1527,
  Journal 0.0052, Whisper 0.0741; Opus/Proxy 0 CHF).
- Simulation kumuliert: 0.5374 CHF (harte Grenze 1.50 CHF).
- Opus-Lesungen: 12 Aufrufe ueber den lokalen Proxy, 0 CHF.

## Runde 4
