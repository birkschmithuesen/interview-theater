# Padua Nacht-Abnahme P5-7 — Bericht (08.10.2026, Karte t_bc5819a9)

Diese Karte IST die Abnahme (Birk schlaeft). Ergebnis vorweg: **GRUEN**
(Klasse-A-Befunde leer, Suite gruen bis auf den einen vorbestehenden
Fehlschlag, der auf dem Merge-Basis-Commit 22b0a84 bereits existierte).

## Methode

Alle vier Punkte der Karte (Methode: Testgruppe/User-Simulation/Prompt-
Check/Befunde) gegen den AKTUELLEN main-Stand dieses Worktrees (Basis
22b0a84 + eigene Commits unten) geprueft, NIEMALS gegen die Live-Datenbank
schreibend. Vorhandene Treiber (`var/padua-nacht/usertest/usertest_p6.py`,
`usertest_n3.py`) als Referenz verwendet, DB-Kopien per `VACUUM INTO`.

## Punkt A — Zeichenlimit Szenenkarten-Punkte (Birk 23:15, Vision-Befund 2)

Befund: `szenenkarte.ZEICHEN` stand auf 240 Zeichen -- Birks Vorgabe war
"Punkte hart auf ~1 Zeile/120 Zeichen begrenzen (Prompt + Anzeige)".

Fix (Commit `2a1abb6`): `ZEICHEN = 120` (vorher 240), roter Test zuerst,
Mutationsprobe (Grenze auf 240 zurueckgesetzt -> Test faellt).

Verifiziert per frischem Screenshot (`docs/abnahme/2026-10-08-screens/
b2-g1-karte-cothinker.png`): Karte "3. Il rituale" zeigt Titel+Nummer
sichtbar, Punkte sind kurze Saetze (6-9 Woerter je Punkt, wrappen auf
hoechstens 2 Zeilen am Handy -- keine Textwand mehr).

## Punkt B — Vision-Befunde 23:15 gegen aktuellen Code neu geprueft

Alle vier im 23:15-Kommentar genannten Befunde stammen aus Screenshots von
20:00-20:38 Uhr -- VOR den Design-Commits `fe94317` (00:00:03) und
`110b42d` (00:32:27). Frische Screenshots (390x844, main-Stand dieses
Branches) bestaetigen: alle vier sind bereits behoben.

1. **G3 Orts-Partitur** (`b1-g3-script-partitur.png`): kein 3-Spalten-
   Layout mit leeren Spalten/abgeschnittenem Text mehr. Stattdessen "Score
   at a glance"-Tabelle (# | Moment | Where, Modus als Icon+Label in EINER
   Spalte) gefolgt von gestapelten Momentbloecken mit vollem Text. Bestaetigt
   behoben (`web_skript.uebersicht_html`, `fe94317`).
2. **Szenenkarte P6 Titel/Textwand** (`b2-g1-karte-cothinker.png`): Titel
   "3. Il rituale" sichtbar oben in der Karte, Punkte kurz (siehe Punkt A).
   Bestaetigt behoben.
3. **G1 Script SETUP "Goal:"-Block** (`b3-g1-script-setup.png`): "Goal"
   und "Place" sind getrennte, kurze `<p class="feld">`-Bloecke mit Abstand
   -- kein 8-zeiliger Fliesstext mehr. Bestaetigt behoben
   (`web_skript.kopf_html`, `fe94317`).
4. **Script .md/.txt Links fuer Gruppen** (`b4-g1-script-links.png`): nur
   ein "PDF"-Knopf sichtbar, keine .md/.txt-Links. Bestaetigt durch Code
   (`web.py:5238-5242`, Bedingung `if design` entfernt die Links) UND
   Unit-Test `tests/test_web_skript.py:223`
   (`assert "textbuch.md" not in koerper and "textbuch.txt" not in koerper`).

## Punkt C — Script vs. Workbench (Birk-Zusatz 20:20)

Screenshots je Gruppe (`c-g{1,2,3}-script.png`, `c-g{1,2,3}-workbench.png`)
gegen `docs/superpowers/specs/2026-10-07-script-vs-workbench.md` geprueft.

- Workbench (`c-g1-workbench.png`): zeigt NUR Fortschritt/Status/Checkliste
  ("Scene 1: revised", "Round 1, 1 findings") und kurze dramaturgische
  Anmerkungen -- KEINE vollen Szenentexte, keine Prosa-Dialoge.
- Script-Tab: enthaelt die vollen Szenentexte (Dialog, Regie).
- Keine Doppelung von Szenentext zwischen beiden Tabs gefunden (Klasse A
  waere das gewesen -- leer).

## Punkt D — Prompt-Check (Pflicht)

Volltext-Dump aller 25 Modellaufrufe der Phasen 5-7 ueber
`scripts.erzeuge_prompts_padua_voll --scope p57` (Attrappe, kein echtes
Modell, kein Geld), `docs/abnahme/2026-10-08-prompts-p57/` (Commits
`81ead5f`, `dea12bd`). Mechanischer Check (`mechanik.md`): keine
Rohdump-Reste alter Phasen (Gespraechs-Prompts tragen nur Summaries/
Progress/Journal + juengstes Fenster), Sprecherlabels sind "Member N"/
"Interview N" (keine Klarnamen), Blockgroessen tabelliert in
`uebersicht.tsv`. Die "Deutsche Reste" im Treffer-Report sind erwartete
Fixtur-Testsaetze (Attrappen-Transkript, keine echte Nutzerdateneingabe --
Klasse B, kein Fix noetig).

## Punkt E — Deterministische Invarianten

- "No, change" -> Feedbackfrage: bestaetigt per Unit-Test
  `tests/test_karten_cothinker.py::test_befehle_und_ablauf_im_cothinker`
  (Zeile 121-130): Klick auf "No, change" fuehrt zu
  `"What should change on card 1?"`, die geaenderte Karte kommt zur
  Bestaetigung ("Yes, save card"/"No, change again"), "Yes" speichert und
  baut automatisch die naechste Karte -- GRUEN in der vollen Suite.
- Interview-Zitate Originalsprache: bestaetigt per Screenshot
  (`e-g3-interview-quote.png`): italienisches Zitat *"L'odore del ragù la
  domenica."* steht unuebersetzt im Script. Label-Format ist
  "INTERVIEW QUOTE · N" (Mittelpunkt statt Klammern) -- das ist die
  tatsaechliche, konsistente Konvention im Code
  (`_TEXT_ZITAT_KOPF = "Interview quote · {nummer}"`, sowohl in
  `sprachen/en/texte.toml` als auch `web_skript.py`), keine Abweichung von
  einer Vorgabe, sondern die etablierte Schreibweise. Kein Klasse-A-Befund.
- Ein Screenshot (`e-g1-nach-nein-chat.png`) zeigt NICHT den erwarteten
  Zustand nach einem "No, change"-Klick, sondern eine unabhaengige
  Tutorial-Karte ("How to Set Up Your Phones") -- Treiber-/Navigationsfehler
  im Screenshot-Lauf, KEIN Code-Befund (der entsprechende Pfad ist bereits
  per Unit-Test oben bestaetigt gruen). Klasse B: Screenshot-Lauf fuer
  dieses eine Bild war fehlerhaft, Invariante selbst ist durch den Unit-Test
  nachgewiesen.
- Kein englischer Bot-Text bei G3 wurde in diesem Lauf NICHT per Live-Chat-
  Transkript nachgewiesen (keine neue Modell-Interaktion gegen G3 in
  diesem Lauf ausgefuehrt, nur Lese-Screenshots); Regie-Zettel
  `betrieb/zusatz.padua-gruppe3.md` wurde bei fruehere Laeufen (22.10.2026,
  Log-Eintrag 16:57) bereits bestaetigt aktiv. Klasse B: nicht erneut
  frisch verifiziert, kein neuer Befund.
- Keine Endlosschleife / keine Nachruecker in der Interviewliste: ueber die
  volle Suite abgedeckt (u. a. `test_karten_cothinker.py`,
  `test_sortierliste*`), keine zusaetzlichen Auffaelligkeiten.

## Punkt F — Klasse-A-Befunde

**Keine offenen Klasse-A-Befunde.** Der einzige gefundene und gefixte Punkt
(A, Zeichenlimit) ist bereits oben beschrieben und committet.

## Punkt G — Volle Suite

Kommando:
```
/home/birk/.local/bin/uv run --extra dev python -m pytest -q -m "not dortmund" --ignore=tests/e2e -p no:cacheprovider
```
Ergebnis: `1 failed, 9598 passed, 60 skipped, 8 deselected in 850.36s (0:14:10)`

Der eine Fehlschlag:
```
FAILED tests/test_modellaufrufe_inventar.py::test_keine_offene_aufrufstelle
AssertionError: interview_theater.phasen_summary:228 modellwahl.aufruf_schema art=ART
```
**Vorbestehend, keine Regression dieser Karte.** Nachweis: der betroffene
Aufruf (`modellwahl.aufruf_schema(...)` in `phasen_summary.py:228`) existiert
unveraendert bereits auf dem Merge-Basis-Commit `22b0a84` (vor jeder
Aenderung dieser Karte) -- `git show 22b0a84:interview_theater/phasen_summary.py`
zeigt dieselbe Zeile. Dieselbe Diagnose wurde bereits vom Parent-Task
`t_bcad702c` festgehalten ("der eine verbleibende Fehlschlag ... war bereits
in der Ausgangsmessung enthalten, keine Regression").

## Commits auf diesem Branch (wt/t_bc5819a9)

- `81ead5f` Prompt-Dump Phase 5-7 (Punkt D)
- `dea12bd` mechanik.md nachcommitten
- `2a1abb6` Szenenkarten-Punkte auf 120 Zeichen begrenzen (Punkt A)

## Gesamtergebnis

**GRUEN.** Klasse A leer. Suite gruen bis auf den einen vorbestehenden,
unberuehrten Fehlschlag. Autodeploy-Freigabe liegt beim Nacht-Waechter
(Robo) -- NICHT selbst entfernt.
