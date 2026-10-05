# T1 Report: Prompt-Hygiene EN (Padua P1-2 Feedback-Schleife, Runde 1)

Datum: 05.10.2026. Branch `wt/robo-fbl`. Befunde laut
`docs/superpowers/plans/2026-10-05-p12-feedbackloop.md`, Zeile "T1":
P1-H3, P1-N3, P1-L2, P1-L3, P1-L4, P2-H1b, P2-M1, P2-M3 (nur Kopf), P2-N3,
AGG-1. Beleg: `docs/prompt-audit/2026-10-05-padua-p12/BEFUND.md` +
`lesung.json`.

Geaenderte Dateien:
- `interview_theater/sprachen/en/prompts/system.md`
- `workshop/padua-2026/prompts/anweisung.md`
- `workshop/padua-2026/prompts/phasen/1.md`
- `workshop/padua-2026/prompts/phasen/2.md`

Tests ergaenzt/angepasst:
- `tests/test_phasen_prompts_teil2.py` (neue Tests + einen bestehenden
  Test an die neue Zaehlung angepasst)
- `tests/test_padua_phase1_prompt.py`
- `tests/test_padua_phase2_prompt.py`
- `tests/test_sprache_prompts.py`

## Je Befund

**P1-H3 -- Telegram-Bedienung statt Web-App.** `system.md` erklaerte
Markdown-Verhalten mit "Telegram shows them raw" und beschrieb die
tatsaechlichen Bedienelemente der Web-App gar nicht. Geprueft, ob Padua
noch ueber Telegram laeuft: `docs/agents/weboberflaeche.md:329-342` ("Der
Web-Kanal: derselbe Bot ohne Telegram", "Telegram bleibt Plan B") und
`docs/testgruppe-padua.md` (entfernt `IT_BOT_TOKEN`, spricht von "Resten
aus der Telegram-Zeit") legen nahe, dass die laufenden Padua-Gruppen den
Web-Kanal nutzen, nicht Telegram -- ohne `betrieb/*padua*.env` einsehen zu
koennen (nicht im Worktree) also nicht hart beweisbar. Deshalb kanalneutral
formuliert: "Telegram" ersatzlos durch "The chat" ersetzt (funktioniert in
beiden Kanaelen) und ein neuer Absatz "**The app the group uses.**" mit den
echten Bedienelementen ergaenzt (Labels aus `texte.toml` uebernommen:
"Start listening", "Discussion done", Tabs "Chat"/"Workbench"/"CoThinker").
Enthaelt zugleich die Regel aus P1-N3.

**P1-N3 -- "Stay quiet for 2 seconds" erklaert Aufnahmetechnik.** Das ist
Modelltext, keine Code-Zeile, deshalb kein Code-Fund. Im selben neuen
Absatz wie P1-H3 steht jetzt: "never explain the mechanics behind them --
not a pause it is waiting for, not a countdown, not how a recording is cut
into segments."

**P1-L2 -- "amateur theatre group" vs. "acting students in professional
training".** `system.md` Zeile 1 sagte "an amateur theatre group";
`workshop/padua-2026/prompts/anweisung.md` (direkt danach geladen) sagt
"not an amateur group". Fix: "amateur" aus `system.md` entfernt (die
Profildatei bleibt die praezisere, workshopspezifische Beschreibung), statt
die generische Basis-Datei mit Padua-Wortlaut zu ueberladen.

**P1-L3 -- "ask at most one open question per message, at the end" vs.
"never a mandatory close, only when it helps".** Fix in
`workshop/padua-2026/prompts/anweisung.md:3`: "at the end" ersetzt durch
"and only when it helps -- never as a closing line", passend zu `system.md`
und zur Phase-1-Datei.

**P1-L4 -- Stationen 5/6 doppelt (Prosa) + toter Format-Satz.**
(a) Station 5 ("Prose Draft ... write it scene by scene as prose") und
Station 6 ("Rewrite -- tell each scene as prose") behaupteten wortgleich
dieselbe Handlung. Laut Modul-Doku (`entwurf.py` = Phase 5, zweistufig
Uebersicht+Szenen-Prosa; `phasen/6.md` = Ueberarbeitung der bereits
geschriebenen Prosa, "Nothing new is written from scratch here") ist
Station 6 eine Revision, kein zweiter Schreiblauf. Fix: Station 6 jetzt
"go through the prose scenes again with the group's feedback, still
without a form". (b) Unter `/play setting` stand ein toter Satz zu einem
nicht mehr angebotenen "format" der Auffuehrung -- entfernt, der Satz zur
Form blieb ebenfalls weg (siehe P2-M1).

**P2-H1b -- Marker-Katalog widerspricht sich selbst.** `system.md` listete
`VORSCHLAG FRAGENAUSWAHL:` (Zehn-Fragen-Katalog mit Multiple-Choice) und
`VORSCHLAG FRAGEN:`, die Padua in Phase 2 nie schreibt (eigene Fragen zuerst
+ A/B-Vergleich statt Zehner-Katalog, bestaetigt durch Volltextlesung von
`workshop/padua-2026/prompts/phasen/2.md` -- kein Vorkommen von
"FRAGENAUSWAHL" dort). Das Schaerfen EINER Frage in Phase 2 verlangt aber
den bisher nicht gelisteten Marker `VORSCHLAG FRAGE:`
(`workshop/padua-2026/prompts/phasen/2.md:106`,
`interview_theater/knoepfe/basis.py:553-559`: `uebernimm_schaerfung`). Fix:
FRAGENAUSWAHL/FRAGEN-Eintraege entfernt, FRAGE-Eintrag ergaenzt, Zaehlung
"thirteen" -> "twelve" (nachgezaehlt: 12 Marker stehen jetzt im Katalog).
Nur die EN-Datei geaendert (nur Padua liest EN).

**P2-M1 -- Szenenform zu frueh im Prompt.** Station 4 versprach "(with a
suggested form for each scene)", und der Absatz "Every scene has a form"
behauptete, die Form sei "already in the scene sequence suggestion,
visible in the scene introduction and can be changed with a button" --
noch bevor Station 7 ("choose the form for each scene") erreicht ist. Fix:
den Klammerzusatz in Station 4 gestrichen, den Absatz umformuliert auf
"but only once the group reaches station 7"; dabei auch den fehlerhaften
Verweis "in phase 6" (statt 5+6) auf "in stations 5 and 6" korrigiert. Das
Zeilenformat von `VORSCHLAG GESCHICHTE:` (mit Form-Feld) **unveraendert**
gelassen -- der Parser der Szenenfolge/Phase 4 ist nicht Teil dieser Karte
(Plan-Vorgabe "bleibt").

**P2-M3 (nur Kopf) -- doppelte Phasen-Ueberschrift.** `## Current phase: 1
- Terms` bzw. `## Current phase: 2 - Questions` am Dateianfang duplizierte
wortgleich eine separat gebaute Statuszeile im Nutzerteil (kontext.py,
nicht Teil dieser Karte). Fix: beide Ueberschriften zu "## What this phase
is about" geaendert -- die Phasennummer/-name bleibt alleinige Aufgabe der
Statuszeile. Der "[suggested]"-Journal-Teil von P2-M3 (Frage B5) ist NICHT
angefasst -- Klasse B, nicht mein Auftrag.

**P2-N3 -- toter Verweis "VORSCHLAG FRAGEN WEICH".** Dieser Marker wird in
Padua nirgends geschrieben (die weiche Fassung ist fuer dieses Profil
abgeschaltet); die Regel zum Schaerfen einer Frage
(`workshop/padua-2026/prompts/phasen/2.md`) nannte ihn trotzdem explizit
als Ausschluss. Fix: Satz "No softer versions, no sensitivity check, no
`VORSCHLAG FRAGEN WEICH:` block - ..." entfernt, nur die positive Regel
"The group words its questions itself." blieb stehen.

**AGG-1 (offener Teil) -- Diskussions-/Begriffe-Detail-Block unerklaert.**
Der Board-Kopf ist laut BEFUND.md schon selbsterklaerend (vorige Karte,
`7fc6334`). Offen war ein Satz zu den Kopfzeilen "From your term
discussion:" und "Why you chose these terms:" (`texte.toml:960f`, nicht
Teil dieser Karte -- nur `system.md` durfte angefasst werden). Fix: im
Absatz "You know everything the group has done" zwei Saetze ergaenzt, die
beide Kopfzeilen woertlich zitieren und einordnen.

## Nicht angefasst (ausserhalb des Auftrags)

- `interview_theater/sprachen/en/texte.toml` (`DISKUSSION_KOPF`,
  `BEGRIFFE_DETAIL_KOPF`, parallele Session) -- AGG-1 ist deshalb nur
  "teils" geschlossen, der Kopfzeilen-Wortlaut selbst bleibt unveraendert.
- `interview_theater/diskussion.py:96` (deutscher Rest "Das Transkript der
  Diskussion:") -- gehoert laut BEFUND.md Abschnitt 9 einer anderen Karte
  (`texte.toml`-Besitz).
- P2-H1 (Zahl/Form der KI-Fragen), P2-M3 "[suggested]"-Journal (Frage B5):
  Klasse B, nicht entschieden.
- `interview_theater/sprachen/en/prompts/phasen/2.md` (die GETEILTE,
  nicht-Padua-spezifische Basis-Phase-2-Datei) -- bewusst nicht angefasst,
  Padua liest ausschliesslich die eigene
  `workshop/padua-2026/prompts/phasen/2.md`-Fassung (Dateiersatz,
  `anweisungen._profil_pfad`); die geteilte Datei betraf nicht Padua.

## Tests

Neu/angepasst (TDD: erst den bereits bestehenden Test
`test_system_en_marker_katalog_nennt_eigene_fragen` auf die neue Zaehlung
umgeschrieben und `test_phase2_ohne_toten_verweis_auf_fragen_weich` initial
mit einer falschen Whitespace-Annahme laufen lassen -- beide liefen rot,
dann korrigiert):

- `tests/test_phasen_prompts_teil2.py`: 8 neue Tests
  (`test_system_en_beschreibt_die_web_app_statt_telegram`,
  `test_system_en_erklaert_nie_aufnahmetechnik`,
  `test_system_en_ist_keine_amateurgruppe`,
  `test_system_en_stationen_5_6_nicht_doppelt_prosa`,
  `test_system_en_play_ohne_toten_format_satz`,
  `test_system_en_form_erst_in_station_7`,
  `test_system_en_marker_katalog_ohne_fragenauswahl`,
  `test_system_en_erklaert_diskussion_und_begriffe_detail_koepfe`) plus
  1 angepasster Bestandstest.
- `tests/test_padua_phase1_prompt.py`: 1 neuer Test
  (`test_phase1_kopf_nicht_doppelt_mit_der_statuszeile`).
- `tests/test_padua_phase2_prompt.py`: 2 neue Tests
  (`test_phase2_kopf_nicht_doppelt_mit_der_statuszeile`,
  `test_phase2_ohne_toten_verweis_auf_fragen_weich`).
- `tests/test_sprache_prompts.py`: 1 neuer Test
  (`test_padua_anweisung_fragt_nicht_zwingend_am_satzende`).

### Befehle und Ergebnis

```
uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider \
  tests/test_phasen_prompts_teil2.py tests/test_padua_phase1_prompt.py \
  tests/test_padua_phase2_prompt.py tests/test_sprache_prompts.py
-> 148 passed
```

Breiterer Lauf (alle Dateien, die `system.md`/Padua-Phasen/Profil-Mechanik
beruehren, plus die Audit-Werkzeug-Tests aus BEFUND.md Abschnitt 12 --
keine volle Suite, wie vorgegeben):

```
uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider \
  tests/test_phasen_prompts_teil2.py tests/test_padua_phase1_prompt.py tests/test_padua_phase2_prompt.py \
  tests/test_sprache_prompts.py tests/test_profil_bitgleich.py tests/test_anweisungen_profil.py \
  tests/test_anweisungen.py tests/test_befehle_englisch_in_prompts.py tests/test_befehle.py \
  tests/test_en_frage_regel_widerspruchsfrei.py tests/test_flow_fixes_0609_nacht.py \
  tests/test_formen_katalog.py tests/test_kein_foto_angebot.py tests/test_profile_geruest.py \
  tests/test_prompt_audit.py tests/test_pruefe_profil.py tests/test_rahmen.py \
  tests/test_sprache_bitgleich.py tests/test_fixture_padua_voll.py tests/test_mitschnitt.py \
  tests/test_modellaufrufe_inventar.py tests/test_pruefe_prompt_dumps.py tests/test_prompt_lesung.py
-> 547 passed, 15 warnings (pre-existing DeprecationWarning in web_chat.py, unrelated)
```

`test_profil_bitgleich.py` (Dortmund-Bitgleich) lief unverandert gruen --
erwartbar, weil nur EN-/Padua-Dateien angefasst wurden, keine deutschen
Basis- oder Dortmund-Dateien.

```
uv run --extra dev python -m scripts.pruefe_profil padua-2026
-> padua-2026: in Ordnung
```

Zusaetzlich zur Verifikation (nicht Teil der vorgegebenen Testbefehle, aber
kostenlos/lokal laut BEFUND.md): Prompt-Dumps + Mechanik-Check neu erzeugt
(`scripts.erzeuge_prompts_padua_voll`, `scripts.pruefe_prompt_dumps`) gegen
einen Wegwerf-Ordner (danach nicht committet) -- keine neuen mechanischen
Treffer durch meine Aenderungen (kein "Telegram", kein "FRAGENAUSWAHL"
mehr; die einzigen verbleibenden Mechanik-Treffer sind die schon in
BEFUND.md Abschnitt 6 manuell widerlegten Faelle plus der bekannte,
blockierte deutsche Rest in `14-diskussion-verdichtung.txt` aus
`diskussion.py`).

## Offene Punkte

- AGG-1 bleibt "teils" offen: die Kopfzeilen-Texte selbst (`texte.toml`)
  sind nicht Teil dieser Karte.
- Die Kanal-Frage bei P1-H3 (Telegram vs. Web) ist nicht hart belegt --
  `betrieb/*padua*.env` liegt nicht im Worktree. Die gewaehlte, neutrale
  Formulierung ("the chat") macht die Antwort unabhaengig vom Ergebnis
  richtig.
- Keine der zehn Karten beruehrt `erkenner.py`, `knoepfe/basis.py`,
  `knoepfe/texte.py`, `sprachen/en/texte.toml`, `simulation/` oder
  deutsche Prompt-/Textdateien.

## Fix-Abschnitt: Review-Fund nach dem ersten Durchgang (05.10.2026)

**Fund (Review):** `interview_theater/sprachen/en/prompts/system.md:80-83`
(Fassung nach dem ersten Durchgang) behauptete: '"Start listening" starts
the background listening AND the mic check in one step -- there is no
separate check button'. Das ist falsch und nahm zudem die offene
Klasse-B-Frage B1/P1-H1 vorweg.

**Verifiziert:**
- `interview_theater/sprachen/en/texte.toml:1913`:
  `_TEXT_KALIBRIERUNG_START_KNOPF = "Start measuring"` -- ein eigener
  Knopftext.
- `interview_theater/web_chat.py:2521-2540`
  (`kalEntscheideOderStarte`): prueft zuerst einen Tages-Cache
  (`kalibrierungCacheLesen`, Schluessel ueber `kalDatum`); nur wenn kein
  Cache vorliegt UND die Kalibrierung aktiv ist, ruft sie
  `kalibrierungStarte(sitzung)` auf.
- `interview_theater/web_chat.py:2188-2201` (`kalibrierungStarte`): zeigt
  eine eigene Karte (`kalZeigePanel`) mit dem Text
  `TEXT.kal_ankuendigung` und darunter dem Knopf `kalStartKnopf` (Label
  "Start measuring") -- ein zweiter, separater Start-Vorgang mit eigenen
  Schritten (5s Stillemessung, dann ein Testsatz), nicht Teil eines
  einzigen "Start listening"-Schritts.
- Das deckt sich mit dem schon vorher im Plan erfassten Befund **P1-H1**
  ("Raumcheck-Karte + laufende Aufnahme gleichzeitig, zwei
  Start-Bedienelemente") -- Klasse **B**, Birk entscheidet (Frage B1).
  Mein Satz durfte das nicht vorwegnehmen.

**Fix:** Den Satz in `system.md` ersetzt:
- Vorher: '"Start listening" starts the background listening AND the mic
  check in one step -- there is no separate check button; "Discussion
  done" ends it.'
- Nachher: '"Start listening" starts the background listening;
  "Discussion done" ends it. The first time on a given day, a short room
  check may appear first, with its own button -- you may name it if the
  group asks, but never explain how it measures (a few seconds of
  silence, then a test sentence).'

Beschreibt nur, was heute tatsaechlich passiert (Tages-Cache, eigene
Karte, eigener Knopf), ohne B1 zu entscheiden; die Regel "nie die Technik
erklaeren" (P1-N3) bleibt erhalten und auf den Raumcheck ausgeweitet.

**Test (TDD):** neuer Test
`tests/test_phasen_prompts_teil2.py::test_system_en_behauptet_keinen_mikro_check_in_einem_schritt`
prueft, dass die falsche Behauptung fehlt und die neue Formulierung
steht. Gegen den Stand VOR diesem Fix (Commit `f341831`) lief er rot
(verifiziert durch Nachbau des alten Dateiinhalts via
`git show f341831:interview_theater/sprachen/en/prompts/system.md` und
Pruefen der drei Teilstrings in Python: `mic check in one step` und
`there is no separate check button` waren True, `a short room check may
appear first` war False).

### Befehle und Ergebnis

```
uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider \
  tests/test_phasen_prompts_teil2.py tests/test_padua_phase1_prompt.py \
  tests/test_padua_phase2_prompt.py tests/test_sprache_prompts.py
-> 149 passed
```

```
uv run --extra dev python -m scripts.pruefe_profil padua-2026
-> padua-2026: in Ordnung
```

```
uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider \
  tests/test_profil_bitgleich.py tests/test_sprache_bitgleich.py
-> 23 passed (Dortmund-Bitgleich unveraendert gruen -- kein Dortmund-/Basis-Datei angefasst)
```

Erweiterter Lauf (gleiche Dateiliste wie im ersten Durchgang, plus der
neue Test):

```
-> 548 passed, 15 warnings (vorher 547 + 1 neuer Test)
```

Kein Padua-Prompt-Snapshot-Test existiert (`test_profil_bitgleich.py`
bindet nur Dortmund) -- deshalb keine Snapshot-Regenerierung noetig;
`pruefe_profil padua-2026` ist die vorgegebene Padua-Pruefung und ist
gruen.

**Commit:** siehe Git-Log, Nachfolgecommit zu `f341831` in diesem
Worktree.
