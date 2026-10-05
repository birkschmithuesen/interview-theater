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
