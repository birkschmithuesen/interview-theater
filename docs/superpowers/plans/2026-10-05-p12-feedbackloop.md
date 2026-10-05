# Plan: Padua P1-2 Feedback-Schleife -- Befundliste (Inventur, Runde 0)

Stand 05.10.2026, Branch `wt/robo-fbl`, Basis main `9780250` (live, robo/p1-livefix
und robo/p2-livefix gemergt). Karte: `.cc-card.md`. Nur Inventur, kein Code geaendert.

## Ziel

Alle automatisch gefundenen, offenen Befunde zu Phase 1+2 (Abnahme-Bericht
`simulation/berichte/abnahme-p12-2026-10-04.md`, Prompt-Check
`docs/prompt-audit/2026-10-05-padua-p12/` BEFUND.md + lesung.json, aggregierter
BEFUND aus `.worktrees/t_pc_aggregiert`, Robo-Nachtrag) in Runden abarbeiten:
Lauf -> Befunde -> Klasse-A-Fix mit Test -> Nachlauf, max. 5 Runden, bis kein
"hoch" mehr offen ist und der Prompt-Check keinen Kategorie-a-Treffer in P1/P2 hat.

Status: FIXED = schon im Code; A = klarer Fix; B = Birk entscheidet;
BLOCKED = braucht `interview_theater/erkenner.py`, `knoepfe/basis.py`,
`knoepfe/texte.py`, `sprachen/en/texte.toml` (parallele Session) oder `simulation/`
(andere Karte).

## Pruefkommandos je Runde

**Prompt-Check (Dump + Mechanik kostenlos, rein lokal, kein Modell, kein Netz):**

```
uv run --extra dev python -m scripts.erzeuge_prompts_padua_voll docs/prompt-audit/<datum>-padua-p12-rN
uv run --extra dev python -m scripts.pruefe_prompt_dumps docs/prompt-audit/<datum>-padua-p12-rN \
  --nach docs/prompt-audit/<datum>-padua-p12-rN/mechanik.md
```

- Erzeuger: ohne `--nur` genau die fuenf P1/P2-Dumps (`SCOPE_P1_P2`: 01-gespraech-phase1,
  05-gespraech-phase2, 13-begriffsboard, 14-diskussion-verdichtung, 15-fragen-ki), Fixture-DB
  in tmp, `IT_WORKSHOP=padua-2026` setzt das Skript selbst, Mitschnitt-Double statt Modell.
  Schreibt `<ordner>/*.txt` + `uebersicht.tsv`. Geprueft 05.10.: laeuft in ~10 s.
- Mechanik: liest `<ordner>/*.txt`, schreibt `mechanik.md`, Exit immer 0; `--basis -`
  schaltet den Groessenvergleich ab.

**Opus-Lesung (Modellaufruf ueber den lokalen Claude-Proxy, Abo, 0 CHF je Aufruf):**

```
uv run --extra dev python -m scripts.pruefe_prompts_lesung docs/prompt-audit/<datum>-padua-p12-rN --phase 1
uv run --extra dev python -m scripts.pruefe_prompts_lesung docs/prompt-audit/<datum>-padua-p12-rN --phase 2
```

Je Phase 1 Aufruf (+ hoechstens 1 Retry), ~3-4 min (TIMEOUT_S 280, 32k Ausgabe).
Schreibt `lesung.json` + `lesung-unsicher.jsonl`. `--trocken` zaehlt nur, ohne Aufruf.

**Browser-Simulation P1-2 (kostet Geld: echte Bot-Modellkette Infomaniak + Whisper;
Persona/Richter ueber Claude-Proxy):**

```
env -u IT_WORKSHOP IT_SIM_ENV=<pfad zur Test-Env> /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python \
  -m simulation.browser_lauf --geraet handy --persona giulia --stationen p12 --bericht
env -u IT_WORKSHOP IT_SIM_ENV=<pfad zur Test-Env> /mnt/HC_Volume_106183673/venvs/it-webtest/bin/python \
  -m simulation.browser_lauf --geraet laptop --persona priya --stationen p12 --bericht
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m simulation.browser_abnahme bericht \
  --lauf simulation/browser_laeufe/<datum>-handy-giulia-p12 --lauf simulation/browser_laeufe/<datum>-laptop-priya-p12 \
  --ausgabe simulation/berichte/feedbackloop-p12-<datum>-rN.md
/mnt/HC_Volume_106183673/venvs/it-webtest/bin/python -m simulation.browser_abnahme kosten <sim.db> ...
```

- Env: `--env-datei <datei>` oder `IT_SIM_ENV`; Python liest sie nie, sie wird nur im
  Bot-Kindprozess per `source` geladen (Plan 2026-10-04-padua-abnahme-p12-browser.md nennt
  `betrieb/padua-test.env`; der Agent liest sie nicht). Der Lauf startet eigenen Web- und
  Bot-Prozess auf freiem 127.0.0.1-Port mit Wegwerf-`sim.db` -- Live bleibt unberuehrt.
- Stationen: `p12` ist das einzige (und kleinste) Set, 11 Stationen (p1-start, p1-eintritt,
  p1-kalibrierung, p1-zuhoeren, p1-begriffe, p1-uebergang, p2-eigene-fragen, p2-ab-vergleich,
  p2-einzeldurchgang, p2-eroeffnung, p2-uebergang); keine Teilauswahl. Kleinste Runde =
  nur ein Geraet (handy).
- Ausgabe: `simulation/browser_laeufe/<datum>-<geraet>-<persona>-p12/` (ergebnis.json,
  sim.db, Logs, Screenshots); Bericht separat ueber `browser_abnahme bericht` (modellfrei).
- Kosten: 04.10. je Geraet 32-57 Bot-Aufrufe, zusammen 0.124 CHF; Erwartung je Runde
  (beide Geraete) ~0.35 CHF, harte Grenze 1.50 CHF gesamt. Geraete nacheinander, nie parallel.
- `simulation/` wird von dieser Karte NICHT geaendert.

## Befundliste

Prio h/m/n = hoch/mittel/niedrig.

### Phase 1

| ID | P | Befund | Status | Beleg / geplanter Fix (Dateien, Test) |
|---|---|---|---|---|
| P1-H1 | h | Raumcheck-Karte + laufende Aufnahme gleichzeitig, zwei Start-Bedienelemente ("Start listening" + "Start measuring") | B | `web_chat.py:2601-2632` startet die Aufnahme bewusst SOFORT, Kalibrierung laeuft in der Sitzung (Frage B1) |
| P1-H1b | h | "Tap once to start." bleibt neben "Discussion done"/"Listening" stehen | A | Zeile `#ux-rec-zeile` aus `web_gestalt.py:1772-1828` gehoert zum Interview-Knopf; verbergen, wenn `#interview` verborgen ist oder eine Diskussion laeuft. `web_gestalt.py`; `tests/test_web_gestalt_js.py` |
| P1-H2 | h | Bot schreibt beim Zuhoeren in den Chat (Antworten auf getippte Fragen, Mikro-Tipps) | B | Prompt sagt schon "say nothing" (`workshop/padua-2026/prompts/phasen/1.md:14-16`); serverseitig kennt der Bot keinen "Mithoeren laeuft"-Zustand (Frage B2). Teil "Bot behauptet, Sprachnachrichten ohne Text" FIXED `7fc6334` |
| P1-H3 | h | Bot erklaert Telegram-Bedienung (Mikro halten, wischen) statt Web-App; "no separate mic check button that I know of" | A | `sprachen/en/prompts/system.md:68` "Telegram shows them raw"; keine Beschreibung der Web-Bedienelemente. Fix: "The chat shows them raw", plus kurzer Absatz "The app the group uses" (Start listening = Raumcheck + Mithoeren, Discussion done, Mikro-Knopf zum Sprechen, Tabs Chat/Workbench/CoThinker; nie Technik wie Segmentschnitt/Pausen erklaeren). `system.md` (EN, nur Padua liest EN); `tests/test_padua_phase1_prompt.py` |
| P1-M1 | m | Transkript-Blasen falsche Reihenfolge (0:10 ueber 0:09), "foam"/"home" doppelt; Laptop ein Textblock | A | Ursache erst messen (Sortierschluessel der Mitgehoert-Blasen in `web_chat.py`/`web_daten.py`; Doppel vermutlich Kalibrier-Testschnitt + Diskussionssegment ueber dieselbe Stelle). Textwand haengt am Segmentschnitt der Sim-Audiodatei (BLOCKED simulation/) |
| P1-M2 | m | Undo als roher "Undone:"/"Redone:"-Block | BLOCKED | `texte.toml:53,61` + Undo-Weg `knoepfe/basis.py` |
| P1-M3 | m | Handy-Kopfbereich zu hoch, Tab-Unterstrich abgeschnitten, untere Leiste/Eingabe abgeschnitten | A | App-Shell-CSS `web_vereint.py`/`web_gestalt.py` (Kopf kompakter bei <= 430 px, Eingabezeile fix). Test: `tests/e2e/test_web_chat_e2e.py` (390 px: `#eingabe` im Viewport) |
| P1-M4 | m | Pegelbalken ohne Skala | A (Optik) | Zielmarke "laut genug" in `kalZeigeBalken` (`web_chat.py:2122`) als Strich, ohne neuen Text; Beschriftung = neuer Text -> BLOCKED texte.toml. Test: `tests/test_web_gestalt_js.py`-Muster |
| P1-N1 | n | "Abkürzung:" deutsch | FIXED | `7f2f8e9`, EN `texte.toml:1874` "Shortcut:" |
| P1-N2 | n | Platzhalter abgeschnitten ("... or tap a shortc") | BLOCKED | kuerzerer EN-Text in `texte.toml` (`<input>` bricht nicht um, `web_chat.py:3879`) |
| P1-N3 | n | "Stay quiet for 2 seconds" schiebt Technik auf die Gruppe | A | Modelltext, kein Code-Text; Regel "nie Aufnahmetechnik erklaeren" im Absatz aus P1-H3 |
| P1-N4 | n | Aufnahmeknopf P1 ("Start listening") vs. P2 (Mikro-Kreis) uneinheitlich | B | verschiedene Funktionen (Mithoeren vs. Sprechen-Taste), Frage B6 |
| P1-L1 | m | Prompt: Phasenhinweis "Ask ... whether the group wants to go there yet" widerspricht "Don't ask what comes next" | A | `kontext._baue_phasenhinweis` (`kontext.py:1000`) in Phase 1 nicht anhaengen -- die Abschlussnachricht fragt schon "Shall we move on?". `kontext.py`; `tests/test_kontext.py`. Wortlaut `_PHASENHINWEIS` liegt in texte.toml:970 (BLOCKED) |
| P1-L2 | m | Prompt: "amateur theatre group" vs. "acting students in professional training" | A | `system.md:1`; Test in `tests/test_phasen_prompts_teil2.py` |
| P1-L3 | m | Prompt: "ask at most one open question per message, at the end" vs. "no question at the end" | A | `workshop/padua-2026/prompts/anweisung.md:3` auf "only when it helps, never as a closing line" |
| P1-L4 | n | Prompt: Stationen 5/6 doppelt (Prosa), toter Satz zum "format" | A | `system.md:16-18`, `:235-238` |
| P1-L5 | m | Prompt: Handover-Absatz | FIXED | `a084daa` |
| P1-L6 | n | Kontext: Systemzeilen ("Changed since", "Undone:", "📌 Agreed:", "Question N/M") stehen als "You:"-Zug im Verlauf | A | `kontext._SYSTEMANFAENGE_EN` (`kontext.py:1401`) um die EN-Anfaenge ergaenzen. `tests/test_kontext_fenster.py` |
| P1-L7 | n | Fixture-Artefakte (Rauschen im Verlauf, Board-Beispiel "returns to it twice", Spaetphasen-Journal in Phase 1) | A (n) | nur `scripts/fixture_padua_voll.py` + `tests/test_fixture_padua_voll.py`; kein Produktfehler |
| P1-L8 | n | "Das Transkript der Diskussion:" deutsch im Nutzerteil | BLOCKED | Rezept BEFUND p12 Abschnitt 9: `diskussion.py:96` + `texte.toml` |

### Phase 2

| ID | P | Befund | Status | Beleg / geplanter Fix |
|---|---|---|---|---|
| P2-H1 | h | Fragen-Kaefig "Question 1/27" mit Accept/Discard je Frage, Zaehler 1/27-1/42, "Please say yes or no", Uebergang "alle 23 fertig machen?" | B | Ursache `sprachen/en/prompts/fragen_ki_vorschlag.md:15` "exactly THREE ... for EVERY term" (9 Begriffe = 27 KI-Fragen + eigene) und Einzeldurchgang `knoepfe/fragen.py:611-679` (Frage B3) |
| P2-H1a | h | Prompt-Reste "three per term", "more than three -> keep the best" | FIXED | `9763e56`; Padua `phasen/2.md:48-51` nennt keine Zahl mehr |
| P2-H1b | h | Prompt: `VORSCHLAG FRAGENAUSWAHL:` "exactly ten ... taps three" im Katalog (in Padua nicht genutzt) | A | `system.md:113-120`: FRAGENAUSWAHL/FRAGEN streichen, `VORSCHLAG FRAGE:` aufnehmen, Zahl anpassen (nur EN = nur Padua). `tests/test_phasen_prompts_teil2.py` (Marker-Katalog-Test anpassen) |
| P2-H2 | h | A/B-Vergleich verliert KI-Fragen: exakter Praefix "<Begriff>: " | A | `knoepfe/fragen.py:297-314` `_zeilen_je_begriff`: Kopf normalisieren (Anfuehrungszeichen, Artikel, Whitespace), Praefix-/Enthalten-Abgleich, laengster Treffer gewinnt; KI-Prompt `fragen_ki_vorschlag.md:39-42` "copy the term exactly as given". Leerer Vergleich darf nicht in `_TEXT_FRAGEN_KEINE_AUSWAHL` laufen. `tests/test_fragen_eigene_ki.py`, `tests/test_p2_livefix.py` |
| P2-H2b | h | KI-Fragen-Lauf beim Eintritt gescheitert -> "Yes, suggest some" kann nicht nachholen | A | `knoepfe/fragen.py:_eigene_fertig`: ist `fragen_ki_vorschlag` leer und kein Lauf aktiv (`fragen_ki.versuche_start`), `fragen_ki.starte` anstossen (eigener Thread, kein Modell im Knopf). `knoepfe/fragen.py`, `knoepfe/wirkung.py` (klm/e durchreichen); `tests/test_fragen_ki.py` |
| P2-H3 | h | Dubletten: Frage 8 dreimal als Karte, "Noted:"-Block doppelt | A (Repro zuerst) | Karte: Repro-Test fuer `_zeige_frage`-Mehrfachaufruf (Schaerfen + Freitext, `nimm_offene_frage_text` `fragen.py:776`). "Noted:"-Doppel stammt vermutlich aus Erkenner + Vorschlagsblock -> wenn Erkenner: BLOCKED |
| P2-H4 | h | Werkbank "2 · Questions 0 of 4" obwohl Fragen da | A | `roadmap.py:108-122`: "Fragen" laeuft (`_LAEUFT`), sobald `fragen_eigene_vorschlag`/`fragen_auswahl` steht; "Einleitungen" ausblenden, wenn `_weich_aktiv()` falsch (Padua: weich aus, Kreis wird nie voll). `roadmap.py`; `tests/test_roadmap_werkbank.py`, `tests/test_roadmap.py` |
| P2-H5 | h | Mehrfachfragen je Nachricht (8-56 je Station) | BLOCKED | Zaehler der Sim zaehlt die Fragekarten ("Question N/M" + Interviewfrage) mit (simulation/); Modellregel steht schon in `system.md:151-162` |
| P2-H6 | h | Bot ueberschreibt Gruppeninhalt (gestrichenes "working" zurueck, zwei eigene Fragen weg) | B | `fragen.py:471-489` `uebernimm_eigene` ersetzt `fragen_eigene_vorschlag` jedes Mal durch die vom Modell neu geschriebene Gesamtliste (Frage B4) |
| P2-K | h | Zweite bestaetigte Frage ueberschreibt die erste | FIXED | `f777d4e` |
| P2-M1 | m | Szenenformen zu frueh im Prompt ("suggested form for each scene", "Every scene has a form") | A | `system.md:13-15`, `:41-45`, `:238`: Form erst in Station 7. Format von `VORSCHLAG GESCHICHTE:` (`:137-138`, "— form") bleibt (Parser `szenenfolge`, Phase 4 ausserhalb Scope) |
| P2-M2 | m | Prompt-Widersprueche: amateur (=P1-L2), Frage am Ende (=P1-L3), "never claim saved" vs. "Your three are saved" | A / Fixture | letzteres ist eine Fixture-Verlaufszeile (P1-L7) |
| P2-M3 | m | Nutzerteil: "[suggested]"-Journal, Statuszeilen als Bot-Zug, Phase doppelt | A / B | Statuszeilen = P1-L6; Phase-Kopf doppelt: `## Current phase` in `workshop/padua-2026/prompts/phasen/{1,2}.md:1` -> "## What this phase is about" (n); "[suggested]" im Journal Frage B5 |
| P2-M4 | m | Marker "VORSCHLAG EIGENE FRAGEN:" leakt in den Chat | A | `vorschlag.ohne_marker` (`vorschlag.py:204`) entfernt nur Markerzeilen am Zeilenanfang; Inline-Nennung `VORSCHLAG <ART>:` im Fliesstext ebenfalls tilgen. `tests/test_vorschlag.py` |
| P2-M5 | m | Accept/Discard/Sharpen ohne Erklaerung | BLOCKED | Text `_TEXT_GEGENUEBERSTELLUNG_BEREIT` texte.toml:234 |
| P2-M6 | m | Beschwerden im Einzeldurchgang ohne sichtbare Reaktion | B | Teil von B3 (Freitext waehrend des Durchgangs) |
| P2-M7 | m | "eigene Fragen zuerst" nicht erkennbar | FIXED (Nachlauf) | `7f2f8e9` Rueckfrage vor KI-Fragen; im Nachlauf pruefen |
| P2-M8 | m | Uebergang zu Phase 3 unklar | B | mit B3 |
| P2-M9 | m | Echo-Antworten (live 3x, `echo_verworfen`/`echo_wiederholt`) | A | `ablauf.py:1371` prueft `ist_echo` auf dem Text MIT Vorschlagsblock; in Phase 2 steht die diktierte Frage zwingend im `VORSCHLAG EIGENE FRAGEN:`-Block -> Fehlalarm, zweiter Anlauf. Fix: `ist_echo(vorschlag.ohne_bloecke(text))`. `ablauf.py`, `vorschlag.py`; `tests/test_ablauf.py` |
| P2-N1 | n | "What do you want to change?" doppelt (Blase + Label) | A | `knoepfe/fragen.py:720-721` sendet den Text UND gibt ihn als Knopf-Antwort zurueck; Rueckgabe leeren. `tests/test_fragen_weich.py`-Umfeld bzw. neuer Test |
| P2-N2 | n | "Das Transkript der Diskussion" | BLOCKED | = P1-L8 |
| P2-N3 | n | toter Verweis "VORSCHLAG FRAGEN WEICH" | A | `workshop/padua-2026/prompts/phasen/2.md:107-110` nur positive Regel; `tests/test_padua_phase2_prompt.py` |

### Aggregiert und Robo-Nachtrag

| ID | P | Befund | Status | Beleg / geplanter Fix |
|---|---|---|---|---|
| AGG-1 | m | Diskussions-/Board-/Begriffe-Detail-Block im Systemprompt nicht erklaert | teils FIXED | `7fc6334`: `system.md:27-30` + Board-/Mitgehoert-Kopf erklaeren sich. Offen (A): ein Satz in `system.md` zu "From your term discussion:" und "Why you chose these terms:" (Kopfzeilen selbst in texte.toml:960-961, BLOCKED) |
| AGG-2 | m | `begriffsboard.schreibe_detail` liest nur die juengste Boardzeile; Begriff verliert Begruendung | A | `begriffsboard.py:756-773`: je Begriff die juengste Boardzeile MIT diesem Begriff (auch verworfen) aus dem Verlauf nehmen; neue Lesefunktion in `repo.py`. `tests/test_begriffe_detail_wege.py` |
| R-1 | m | gespeicherter, im Board verworfener Begriff verliert Begruendung im Prompt | A | gleicher Fix wie AGG-2, plus `kontext._baue_begriffe_detail` (`kontext.py:965`) zeigt Detail auch in Phase 1/3, wenn Board es nicht traegt. `tests/test_kontext_mitgehoert.py` |
| R-2 | m | e2e `test_seite_im_interviewmodus_geladen` wackelt (~1/5) | A | Ursache suchen (Warte-/Poll-Bedingung), `tests/e2e/test_web_chat_e2e.py` |
| R-3 | m | KI-Fragen-Lauf scheitert -> Knopf kann nicht nachholen | A | = P2-H2b |
| R-4 | m | nach "Change something" springt Auto-Speichern sofort in Phase 2 | BLOCKED | parallele Session (Erkenner), nicht unsere |
| R-5 | m | Undo nach Bot-Neustart fehlt in der Abschlussnachricht; Undo nur letztes Auto-Speichern | BLOCKED | `knoepfe/basis.py` / Undo-Weg |
| AGG-3 | n | Fliesstext von Verdichtung/Zusammenfassung/Buehnenkarte nie gegen Transkript geprueft | B | aggregierter BEFUND, Entscheidungsfrage (Vorfall ja/nein) -- nicht P1/2-blockierend |

Birks Live-Befunde (nur Nachlauf pruefen, nicht doppelt fixen): Board-Schwelle `e2b1e91`,
Raumcheck-Cache `62da0ae`, Begruessung `6c879c9`, leeres Ende-Segment `a852d59`,
Top-5-Autosave `d41d40f`, Begruendung einfordern `ce8f206`, Phase-1-Werte `026d36f`,
Chat kennt Board/Mitgehoertes `7fc6334`, Handy-Karten `4bbd7e3`/`9780250`,
P2 K/L/M/N `f777d4e`/`dc0859e`/`9763e56`/`7f2f8e9`. Alle FIXED.

## Zaehlung (Runde 0)

| Prio | FIXED | A | B | BLOCKED |
|---|---|---|---|---|
| hoch | 2 (P2-H1a, P2-K) | 7 (P1-H1b, P1-H3, P2-H1b, P2-H2, P2-H2b, P2-H3, P2-H4) | 4 (P1-H1, P1-H2, P2-H1, P2-H6) | 1 (P2-H5) |
| mittel | 2 (P1-L5, P2-M7) | 15 (P1-M1, P1-M3, P1-M4, P1-L1-3, P2-M1-4, P2-M9, AGG-1 Rest, AGG-2, R-1, R-2) | 2 (P2-M6, P2-M8) + B5 | 4 (P1-M2, P2-M5, R-4, R-5) |
| niedrig | 1 (P1-N1) | 6 (P1-N3, P1-L4, P1-L6, P1-L7, P2-N1, P2-N3) | 2 (P1-N4, AGG-3) | 3 (P1-N2, P1-L8, P2-N2 = P1-L8) |

## Runde 1: unabhaengige Fix-Tasks (Dateien kollisionsfrei)

| Task | Befunde | Dateien | Tests |
|---|---|---|---|
| T1 Prompt-Hygiene EN | P1-H3, P1-N3, P1-L2, P1-L3, P1-L4, P2-H1b, P2-M1, P2-M3 (Kopf), P2-N3, AGG-1 | `interview_theater/sprachen/en/prompts/system.md`, `workshop/padua-2026/prompts/anweisung.md`, `workshop/padua-2026/prompts/phasen/1.md`, `.../phasen/2.md` | `tests/test_phasen_prompts_teil2.py`, `tests/test_padua_phase1_prompt.py`, `tests/test_padua_phase2_prompt.py`, `tests/test_sprache_prompts.py`; Padua-Prompt-Snapshot/`test_profil_bitgleich.py` nachziehen; `pruefe_profil padua-2026` |
| T2 A/B-Vergleich robust | P2-H2, P2-H2b/R-3, P2-H3 (Karte), P2-N1 | `interview_theater/knoepfe/fragen.py`, `interview_theater/knoepfe/wirkung.py`, `interview_theater/fragen_ki.py`, `interview_theater/sprachen/en/prompts/fragen_ki_vorschlag.md` (nur Praefix-Satz, NICHT die Anzahl) | `tests/test_fragen_eigene_ki.py`, `tests/test_fragen_ki.py`, `tests/test_p2_livefix.py`, `tests/test_knoepfe_struktur.py` |
| T3 Kontext + Board-Detail | P1-L1, P1-L6, AGG-2, R-1 | `interview_theater/kontext.py`, `interview_theater/begriffsboard.py`, `interview_theater/repo.py` | `tests/test_kontext.py`, `tests/test_kontext_fenster.py`, `tests/test_kontext_mitgehoert.py`, `tests/test_begriffe_detail_wege.py` |
| T4 Antwortweg | P2-M9, P2-M4 | `interview_theater/ablauf.py`, `interview_theater/vorschlag.py` | `tests/test_ablauf.py`, `tests/test_vorschlag.py` |
| T5 Werkbank P2 | P2-H4 | `interview_theater/roadmap.py` (ggf. `phasentexte.py` "What it takes"-Zeile) | `tests/test_roadmap.py`, `tests/test_roadmap_werkbank.py` |
| T6 Web-UI Phase 1 | P1-H1b, P1-M3, P1-M4, P1-M1 (Messung) | `interview_theater/web_gestalt.py`, `interview_theater/web_vereint.py`, `interview_theater/web_chat.py` (nur JS/CSS, keine neuen Texte) | `tests/test_web_gestalt_js.py`, `tests/test_web_gestalt_css.py`, `tests/e2e/test_web_chat_e2e.py` |
| T7 e2e-Flake | R-2 | `tests/e2e/test_web_chat_e2e.py` (nur falls Produktursache: Absprache mit T6) | 10x wiederholt gruen |
| T8 Fixture (n) | P1-L7 | `scripts/fixture_padua_voll.py` | `tests/test_fixture_padua_voll.py`, `tests/test_erzeuge_prompts_padua_voll.py` |

Kollisionen: T2 und T4 beruehren `vorschlag.py` nicht gemeinsam (nur T4). T3 und T5 teilen
keine Datei. T6/T7 nur ueber `tests/e2e/` -- T7 nach T6 oder eng abgestimmt. Keine Task
beruehrt `erkenner.py`, `knoepfe/basis.py`, `knoepfe/texte.py`, `sprachen/en/texte.toml`,
`simulation/`. Deutsche Prompt-/Textdateien bleiben unangetastet.

Nach Runde 1: Prompt-Check (alle drei Schritte) + ein Simulationslauf handy, dann laptop;
volle Suite einmal (`-m "not dortmund"`); Bericht `simulation/berichte/feedbackloop-p12-<datum>.md`.

## Birks Antworten (05.10. 13:10-13:35, via Robo) — GELTEN AB RUNDE 2

**Robo 13:20 (15-Uhr-Deploy, Birk):** B1 (P1-H1 Raumcheck) und B4 (P2-H6 eigene Fragen) werden SEPARAT gebaut (Branches wt/robo-b1, wt/robo-b4) — in dieser Schleife NICHT anfassen. Runde 1 wird um 13:20 als Zwischenstand (bis e7e4ecc) fuer den Deploy abgezweigt; weiterarbeiten wie geplant.

**Neu einsortieren:** B1 (P1-H1) und B4 (P2-H6) sind jetzt Klasse A -> in Runde 2 fixen, mit Test.
P1-H2 -> mittel, nur Prompt-Widerspruch. P2-H1, P1-N4 -> by design (kein Befund mehr). B5 -> Klasse A.

## B1 (P1-H1) Raumcheck — entschieden 05.10. ~13:10
Birk (Voice): "es soll zuerst die Kalibrierung stattfinden, ordentlich kalibriert werden, Uhr und
Beispielsprache. Und dann soll erst die inhaltliche ... Diskussion beginnen."
=> Ablauf: "Start listening" startet ZUERST den Raumcheck (Ruhemessung + Sprechprobe), sauber und
vollstaendig. Erst danach beginnt die eigentliche Diskussionsaufnahme; die Diskussionsuhr zaehlt
erst ab da. Kein gleichzeitiges Aufnehmen waehrend der Kalibrierung, kein zweiter Startknopf.
Unbestaetigt (Voice): "Uhr" vermutlich = "Ruhe" (Ruhemessung). Beide Lesarten fuehren zum selben
Ablauf.

## B2 (P1-H2) Tippen beim Mithoeren — entschieden 05.10. ~13:15
Birk: "eigentlich egal, das wird eh nicht vorkommen, aber ... der Bot kann dann auch kurz antworten
parallel ... wenn er mit 'nem zweiten Handy tippt, passt das."
=> Getippte Nachricht waehrend laufender Diskussion: Bot antwortet KURZ (ein Satz), parallel zur
Aufnahme. Kein Schweigezwang, keine Mikro-/Technik-Tipps. Niedrige Prioritaet (kommt selten vor):
Befund P1-H2 auf "mittel" herabstufen; nur den Prompt-Widerspruch ("say nothing" vs. Antwort)
aufloesen, keinen neuen Server-Zustand bauen.

## B3 (P2-H1/M6/M8) KI-Fragen Phase 2 — entschieden 05.10. ~13:20
Birk: "dabei bleiben. Jede Frage einzeln, Accept oder Decline ... das muss bei jeder geredet werden.
Das soll so bleiben."
=> Einzelabfrage je Frage mit Accept/Discard BLEIBT (bewusste Designentscheidung: die Gruppe soll
ueber jede Frage sprechen). NICHT auf Uebersichtsliste/Mehrfachauswahl umbauen, Anzahl nicht
reduzieren. P2-H1 ist damit kein Befund mehr ("by design"). Weiter fixen darf man nur die echten
Fehler drumherum: Dubletten, schwankender Zaehler (1/29, 1/28, 1/42), "Please say yes or no"-Kaefig-
Ton, verlorene KI-Fragen im A/B-Vergleich.

## B4 (P2-H6) Eigene Fragen additiv — entschieden 05.10. ~13:25
Birk: "Ja, das passt so."
=> Eigene Fragen der Gruppe werden vom CODE angehaengt, nicht vom Modell neu geschrieben. Aendern
oder Loeschen einer bestehenden Frage nur auf ausdrueckliche Ansage der Gruppe. Formulierungen der
Gruppe bleiben wortgleich (kein gestrichenes Wort wieder einsetzen). Klasse A, mit Test.

## B5 (P2-M3) "[suggested]"-Journaleintraege — entschieden 05.10. ~13:30
Birk: "Ja, das passt, aber ... es muss als Vorschlag von der KI praesentiert werden. Und wenn darauf
nicht eingegangen wurde, dann wurde es ja eher abgelehnt ... dann kaeme es auch eigentlich weg."
=> Phase 1+2: [suggested]-Eintraege nicht im Prompt.
=> Ab Phase 3: nur als KI-Vorschlag gekennzeichnet ("suggested by you, not decided by the group"),
und nur solange er offen ist. Ist die Gruppe darueber hinweggegangen, ohne ihn aufzugreifen, gilt er
als abgelehnt und faellt aus dem Prompt. Operationalisierung (Robo, von Birk nicht im Detail
bestaetigt): ein Vorschlag bleibt nur, bis die Gruppe nach ihm weitergeschrieben hat, ohne ihn
aufzugreifen (naechster Gruppenzug) -- danach raus. Im Journal selbst (DB) bleibt er erhalten, nur der
Prompt laesst ihn weg.

## B6 (P1-N4) Aufnahmeknopf P1 vs P2 — entschieden 05.10. ~13:35
Birk: "passt so ... Funktionalitaet ist ja auch unterschiedlich ... das eine ist ein Toggle und das
andere ist Push to Talk."
=> Bewusst verschieden lassen (P1 "Start listening" = Toggle, P2 Mikro = Push-to-Talk halten,
hochschieben sperrt). Kein Befund mehr ("by design").

## AGG-3 (Fliesstext gegen Transkript pruefen) — offen, nicht gefragt
Nicht entscheidungsreif fuer P1-2; als offen im Bericht fuehren.

## Fragen an Birk (Klasse B) — beantwortet, siehe oben

- **B1 (P1-H1):** Soll "Start listening" die Ruhemessung direkt starten (kein zweiter Knopf
  "Start measuring") und die Diskussionsuhr erst nach dem Raumcheck zaehlen -- oder bleibt
  "Aufnahme laeuft sofort, Kalibrierung parallel", nur klarer beschriftet?
- **B2 (P1-H2):** Wenn die Gruppe waehrend des Mithoerens tippt: antwortet der Bot (kurz)
  oder schweigt er bis "Discussion done"?
- **B3 (P2-H1/M6/M8):** Wie viele KI-Fragen und in welcher Form? Vorschlag: KI hoechstens
  eine Frage je Begriff (oder nur fuer Begriffe ohne eigene Frage), Ueberblicksliste mit
  Mehrfachauswahl statt "Question 1/27" einzeln; Uebergang zu Phase 3 jederzeit moeglich.
- **B4 (P2-H6):** Eigene Fragen additiv fuehren (Code haengt an, Aendern/Loeschen nur auf
  ausdrueckliche Ansage), statt die Liste jedes Mal vom Modell neu schreiben zu lassen?
- **B5 (P2-M3):** "[suggested]"-Journaleintraege im Prompt behalten (als Vorschlag markiert)
  oder in P1/P2 weglassen?
- **B6 (P1-N4):** Aufnahmeknopf P1 ("Start listening") und P2 (Mikro-Taste) optisch
  angleichen oder bewusst verschieden lassen?
- **AGG-3:** Fliesstext von Verdichtung/Zusammenfassung/Buehnenkarte als Vorfall gegen
  das Transkript pruefen (Empfehlung aggregierter BEFUND) -- ja/nein?
