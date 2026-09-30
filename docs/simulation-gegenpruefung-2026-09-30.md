# Gegenpruefung der User-Simulation, 30.09.2026

**Frage** (Birk): prueft `simulation/` sinnvoll — faengt sie echte Fehler?

**Verfahren:** die zwei belegten Dortmunder Fehler vom 06.09.2026 per
Mutation (`simulation/mutation.py`, Monkey-Patch, Produktivcode unangetastet)
wieder einbauen und messen, ob Kennzahlen oder Richter sie melden.

**Basis:** `d8deb6c`, Suite 2768 passed / 1 skipped. Gefahren wurde auf
`36939bf` (Suite 2842 passed / 1 skipped).

**PII:** nur die erfundenen Sets 1–3; `--set birk` und die tag1-Sets bewusst
NICHT (aus echten Interviews abgeleitet, gehoeren nicht ans US-Modell der
Simulationsseite). Hier stehen nur Zahlen — keine Modellantwort, kein
Chatverlauf, kein Belegzitat; die Laufberichte sind gitignored.

---

## 0. Urteil

**Urteil A — die Simulation, wie sie auf `d8deb6c` war: prueft teilweise.**
Fehler 1 meldet die schon vorhandene Kennzahl `nachrichten_je_festlegung_median`
(Basis Seed 1 2.0, im Soll <= 2; mutiert Seed 1 3.0, ausserhalb). Fehler 2
meldet keine vorhandene Kennzahl, der Pfad wurde nicht erreicht; belegt ist er
nur deterministisch. Einschraenkung: der unmutierte Seed 2 lag bei 2.5, also
ebenfalls ausserhalb des Solls — das Signal ist schwach und nicht spezifisch.
Ein Wirkzusammenhang ist plausibel (die Kennzahl misst Nachrichten je
Notiert-Zeile, eine verlorene Festlegung erzeugt keine); den Verlust selbst
benennt erst die neue Kennzahl `festlegungsproben_erhalten`. Dazu als
Tatsache: auf `d8deb6c`
hatte `simulation/lauf.py:_sofort_auftrag` seit `347f28d` (06.09.2026) die
alte Signatur (6 statt 8 Parameter); jeder Knopf mit Auftragszug (Phasen 2,
4, 5) scheiterte im Simulator mit `TypeError` (behoben in `36939bf`), und
`--set 1|2|3` fuhr ohnehin `SCHRITTE` ohne einen Phasenschritt.

**Urteil B — die Simulation nach dieser Karte: prueft teilweise.**
Fehler 1 wird im mutierten Lauf mechanisch gemeldet
(`festlegungsproben_nur_journal` 0 → 2, `festlegungsproben_erhalten` 3/3 →
0/3), im unmutierten Lauf mit demselben Seed stehen beide im Soll. Fehler 2
ist nur durch den deterministischen Nachweis belegt: der Lauf hat den Pfad
(Richtungswahl) in keinem der fuenf Laeufe erreicht.

### Das Kriterium, vor den Laeufen festgelegt

| Urteil | Bedingung |
|---|---|
| **prueft sinnvoll** | Beide Fehler werden im mutierten Lauf von mindestens einer **mechanischen** Kennzahl ausserhalb ihres Sollwerts gemeldet — und im unmutierten Lauf mit demselben Seed ist dieselbe Kennzahl im Soll. |
| **prueft teilweise** | Einer der beiden wird so gemeldet; der andere nur durch den deterministischen Nachweis (`tests/test_simulation_mutation.py`), weil der Lauf den Pfad nicht erreicht hat oder die Kennzahl in beiden Armen gleich stand. |
| **prueft nicht** | Keiner der beiden wird im Lauf gemeldet. |

Fuer **Urteil A** zaehlen ausschliesslich die Kennzahlen und Richternoten, die
es auf `d8deb6c` schon gab — die in Aufgabe 4–6 gebauten sind fuer A
ausdruecklich ausgenommen. Sonst beantwortete der Bericht die Frage nach dem
Zustand vor der Arbeit mit dem Ergebnis der Arbeit.

**Der Richter zaehlt fuer keines der beiden Urteile als Nachweis** — nur als
Plausibilitaetsprobe (Abschnitt 5). Grund: zwei Laeufe sind keine Verteilung,
und seine Noten schwanken zwischen zwei Laeufen ohne jede Aenderung
(`simulation/kennzahlen.py`-Kopf: „die Noten des Richters schwanken zwischen
zwei Laeufen, diese Zahlen nicht").

---

## 1. Abdeckung: welche Phase faehrt das Skript, und woran prueft es

Erzeugt mit `python -m scripts.simulation_abdeckung` — nicht abgeschrieben.
Stand vor der Karte (`d8deb6c`-Code): 7 Phasen, `SCHRITTE` 10,
`SCHRITTE_TAG2` 15, `SCHRITTE_BIRK` 11; `skript.PHASE_MITTE` = 4.

`schritte` (10 Schritte) und `birk` (11 Schritte) haengen **alle** Schritte an
Phase 1 — die Phasen 2–7 werden dort nie per Phasenschritt gefahren:

| Phase | Kurzname | `schritte` | `birk` | `tag2` | Pflichtfeld |
|---|---|---|---|---|---|
| 1 | Begriffe | ja (alle 10) | ja (alle 11) | begriffe | begriffe |
| 2 | Fragen | **nein** | **nein** | phase2, fragen | fragen |
| 3 | Interviews | **nein** | **nein** | phase3, interviews | - |
| 4 | Setting, Figuren & Geschichte | **nein** | **nein** | phase4, setting, geschichte | geschichte |
| 5 | Schaerfung | **nein** | **nein** | phase5, schaerfung | - |
| 6 | Szenen als Geschichte | **nein** | **nein** | phase6, szene1, zitate | geschichte |
| 7 | Feinschliff | **nein** | **nein** | phase7, stand | - |

`phase_mitte` heisst in `schritte` „Phase 5", in `birk` „Phase 4:
Geschichte" — zugeordnet ist beide Male Phase 1.

### Was der Verdacht traf und was nicht

Zehn Behauptungen, alle heute falsch; acht standen noch im Code:

| Behauptung | Fundstellen (Zeilen) | Status |
|---|---|---|
| neun Schritte | `simulation/README.md` 4, 66; `simulation/skript.py` 3; `tests/test_simulation_durchlauf.py` 1 | gefunden_falsch |
| acht Phasen | `simulation/README.md` 243; `simulation/skript.py` 541, 550 | gefunden_falsch |
| "Phase 5" / PHASE_SZENENTEXTE | `simulation/skript.py` 336 / 561, 700 | gefunden_falsch |
| Pflichtfeld der Phase 5 | `simulation/kennzahlen.py` 551 | gefunden_falsch |
| die neun Schritte; Format & Rahmen | `simulation/skript.py`; `simulation/README.md` | bereinigt |

Schwerer wiegen zwei Befunde, die der Verdacht nicht nennt: (1) `--set 1|2|3`
fuhr `SCHRITTE` — ohne `art='phase'`-Schritt, ohne `setting`, `geschichte`,
`schaerfung`; beide Fehler liegen genau dort. (2) Die Modellaufrufe der Phasen
4–6 liefen in Daemon-Threads ausserhalb von `lauf.einfaedig()`.

**Nach der Korrektur** (Zensus nach Aufgabe 7): alle zehn Zeilen
**bereinigt**; `SCHRITTE_TAG2` hat 16 Schritte (Phase 4: `phase4, setting,
festlegungen, geschichte`), faehrbar fuer Sets 1–3 ueber `--skript tag2`.

### Knoepfe und Modellwege im gefahrenen Lauf

Lauf 1 (Basis, Seed 1), Knopfarten je `angeboten/gedrueckt`:

| Knopfart | a/g | Knopfart | a/g | Knopfart | a/g |
|---|---|---|---|---|---|
| aufnahme | 10/5 | leitfaden | 5/0 | speichern | 12/11 |
| durchlauf_szene | 3/0 | noch_nicht | 6/0 | sprechanteile | 1/0 |
| eigene | 14/12 | phase | 11/4 | szene_usa | 2/0 |
| figur_name | 3/0 | schaerfung_keine | 1/0 | textbuch | 1/0 |
| figur_name_menu | 5/1 | schaerfung_stelle | 2/0 | transkript | 5/1 |
| figuren_anzahl_menu | 3/2 | schaerfung_szene | 1/0 | zusammenfassung | 5/3 |
| figuren_namen_menu | 3/2 | | | | |

In Lauf 1 kamen 19 der 83 `ART_*`-Knopfarten vor, ueber alle fuenf Laeufe 37;
`richtung` und `geschichte_speichern` in **keinem** Lauf. Modellwege Lauf 1
(`aufruf.art`, 122 Aufrufe): erkenner 49, gespraech 47, journal 19, verdichter
6, schaerfung 1. In keinem Lauf: `szenenfolge`, `kurzgeschichte`; `szene` nur
in Lauf 2 (2, trotz `--ohne-szene`), `sprachstil` nur in Lauf 4/5 (3/1).
`gedrueckt` = `knopf.benutzt_am IS NOT NULL` (41); `knoepfe_gedrueckt` zaehlt
die Druecke der Stimmen (17) — zwei verschiedene Zaehlungen.

---

## 2. Fehler 1: 22 von 42 Festlegungen verloren

**Quelle:** `docs/analyse-phase4-datenverlust-2026-09-06.md` § 0, § 2.7, § 3.
**Fix:** `e56a892`, `bbe301e`, `36030ff` (07.09.2026).
**Mutiert wurde** die Hauptursache — es gibt kein Fach fuer eine Festlegung,
die in kein Feld passt (`repo.schreibe_festlegung` → `None`). Warum diese und
nicht die Menuezeile oder die Platzhalterfiguren: siehe Abschnitt 6.

**Deterministischer Nachweis, dass die Mutation greift:**
`tests/test_simulation_mutation.py::test_mutiert_schreibt_auch_der_erkenner_nichts`
— passed (Datei: 13 passed).

| Kennzahl | Basis (Seed 1) | mutiert (Seed 1) | Soll | erkannt? | Basis Seed 2 |
|---|---|---|---|---|---|
| `festlegungen` (Tabellenzeilen) | 5 | 0 | > 0 ¹ | ja (Soll verletzt, Basis im Soll) | 15 |
| `festlegungsproben_erhalten` | 3/3 | 0/3 | alle | ja (Soll verletzt, Basis im Soll) | 1/3 |
| `festlegungsproben_nur_journal` | 0 | 2 | 0 | ja (Soll verletzt, Basis im Soll) | 0 |
| `festlegungsproben_nirgends` | 0 | 1 | 0 | ja (Soll verletzt, Basis im Soll) | 2 |
| Schritt `festlegungen` gescheitert | nein | ja | nein | ja (Soll verletzt, Basis im Soll) | ja |
| **vorher vorhandene Kennzahlen** | | | | | |
| `zustimmungen_gespeichert` | 12/24 | 11/23 | alle | nein (beide gleich) ² | 17/22 |
| `behauptete_schreibvorgaenge` | 11 | 3 | 0 | nein (beide gleich) ² | 4 |
| `journal_je_art` (`vorgeschlagen`) | 23 | 30 | – | nein (beide gleich) ² | 36 |
| `nachrichten_je_festlegung_median` | 2.0 | 3.0 | <= 2 | ja (Soll verletzt, Basis im Soll) ³ | 2.5 |
| `arbeitsstand_vollstaendig` | 3/5 | 3/5 | voll | nein (beide gleich) | 3/5 |

¹ Soll aus dem Geruest; `simulation/bericht.py` fuehrt die Zeile informativ.
In Verlaufszeilen vor dem 30.09. bedeutet `festlegungen` Notiert-Abschnitte.
² Gleiches Soll-Urteil in beiden Armen (beide ausserhalb bzw. kein Soll).
³ Meldung nach dem Kriterium. Einschraenkung: der unmutierte Seed 2 steht mit
2.5 ebenfalls ausserhalb des Solls, das Signal ist schwach und nicht
spezifisch; ein Wirkzusammenhang ist plausibel (eine verlorene Festlegung
erzeugt keine Notiert-Zeile).

Die Zeilen oberhalb von „vorher vorhanden" (auch der Schritt `festlegungen`)
sind neu und zaehlen nicht fuer Urteil A. `_erhalten`/`_nirgends` stehen auch
im unmutierten Seed 2 ausserhalb des Solls (Abschnitt 7, Punkt 2);
`_nur_journal` steht in allen vier nicht auf Fehler 1 mutierten Laeufen bei 0.

**Protokoll:**

> **Fehler 1: gefunden.** Woran: `festlegungsproben_nur_journal` stand im Basislauf bei 0 (Soll 0) und im mutierten Lauf bei 2; `festlegungsproben_erhalten` bei 3/3 (Soll alle) und 0/3. Von den auf `d8deb6c` vorhandenen Kennzahlen bewegte sich `nachrichten_je_festlegung_median` aus dem Soll: Basis Seed 1 2.0 (Soll <= 2), mutiert Seed 1 3.0 — ein schwaches, nicht spezifisches Signal, denn der unmutierte Seed 2 lag mit 2.5 ebenfalls ausserhalb.

---

## 3. Fehler 2: aus 3 Szenen wurden 6

**Quelle:** `docs/analyse-phase5-chaos-2026-09-06.md` § 4, § B.
**Fix:** `3ae76ab`, `c9af872` (30.09.2026); davor schon
`repo.gleiche_szenenfolge_ab` (06.09.2026).
**Mutiert wurde** `szenenfolge.szenen_der_richtung` → `[]`.

**Zu beachten:** seit `repo.gleiche_szenenfolge_ab` entfernt ein
Szenenfolge-Lauf keine Szene mehr; der Schaden heisst heute „Titel 1–3
ueberschrieben, 4–6 dazu" (`titel` nicht in `repo.GESCHUETZTE_SZENENFELDER`)
plus 110 s Wartezeit. Die Kennzahl misst beide Gestalten.

**Deterministischer Nachweis:**
`tests/test_simulation_mutation.py::test_mutiert_verliert_die_richtung_ihre_szenen_und_startet_den_lauf`
— passed. Dazu `tests/test_simulation_kennzahlen.py` (`szenenlage` mutiert
gegen unmutiert am echten Knopfweg): passed.

| Kennzahl | Basis (Seed 1) | mutiert (Seed 1) | Soll | erkannt? |
|---|---|---|---|---|
| `szenenfolge_nach_richtung` | 0 | 0 | 0 | nicht messbar (Pfad nicht erreicht) |
| `szenen_aus_richtung` | nein | nein | ja | nicht messbar (Pfad nicht erreicht) |
| `szenen_neuaufbauten` | 0 | 0 | 0 | nicht messbar (Pfad nicht erreicht) |
| `szenen_form_verloren` | 0 | 0 | 0 | nicht messbar (Pfad nicht erreicht) |
| `szenen_aktiv` | 3 | 4 | – | nicht messbar (Pfad nicht erreicht) |
| `szenenfolge_laeufe` | 0 | 0 | – | nicht messbar (Pfad nicht erreicht) |
| **vorher vorhandene Kennzahlen** | | | | |
| `szenen_gesamt` (`formlage`) | 3 | 4 | – | nicht messbar (Pfad nicht erreicht) |
| `form_bestaetigt` / `form_gesetzt_ohne_vorschlag` | 0 / 0 | 0 / 0 | 0 gesetzt | nicht messbar (Pfad nicht erreicht) |
| `rahmen_ueberschrieben` | 0 | 0 | 0 | nicht messbar (Pfad nicht erreicht) |
| `dauer_s`, `chf_bot` | 921.6 / 0.5759 | 1254.2 / 0.5406 | – | nicht messbar (Pfad nicht erreicht) |
| `vorfaelle` (Summe) | 4 | 1 | – | nicht messbar (Pfad nicht erreicht) |

Lauf 5 (Seed 3, mutiert) ebenso. In allen fuenf Laeufen:
`arbeitsstand.geschichte` leer, `aufruf.art = 'szenenfolge'` 0, Schritt
`geschichte` gescheitert; die Szenen (2–5 je Lauf) legte der Erkenner ueber
`szene_planen` an.

**Protokoll:**

> **Fehler 2: nicht messbar.** Woran: `szenenfolge_nach_richtung` stand im Basislauf bei 0 (Soll 0) und im mutierten Lauf bei 0 — gedrueckt wurden 0 von 0 Richtungs-Knoepfen (in 2 Laeufen mit dieser Mutation, 5 Laeufen insgesamt). Von den auf `d8deb6c` vorhandenen Kennzahlen bewegte sich keine.

---

## 4. Die Laeufe

Alle auf `36939bf`, Set 1, `--skript tag2 --ohne-szene`.

| # | Set | Seed | Skript | Schalter | Mutation | Dauer | `chf_bot` | `phase_erreicht` |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | tag2 | `--ohne-szene` | – | 921.6 s | 0.5759 | 7 |
| 2 | 1 | 2 | tag2 | `--ohne-szene` | – | 1024.8 s | 0.6317 | 7 |
| 3 | 1 | 1 | tag2 | `--ohne-szene` | `festlegung_verloren` | 1276.5 s | 0.5231 | 7 |
| 4 | 1 | 1 | tag2 | `--ohne-szene` | `richtung_ohne_szenen` | 1254.2 s | 0.5406 | 7 |
| 5 | 1 | 3 | tag2 | `--ohne-szene` | `richtung_ohne_szenen` | 1154.2 s | 0.5482 | 7 |

Lauf 5 ist der Reservelauf (Aufgabe 11), nur der mutierte Arm: er erreichte
die Richtungswahl nicht, ein Basisarm Seed 3 haette nichts beigetragen. Dazu
zwei abgebrochene Teillaeufe ohne Verlaufszeile (Phase 2 am Simulatorfehler;
Phase 1–3 nach voruebergehendem Proxy-Ausfall, 24 Bot-Aufrufe), zusammen
geschaetzt <= 0.15 CHF.

Summe: 2.8195 CHF gemessen, mit Teillaeufen <= ca. 2.97 CHF von 10 CHF
freigegeben. Kein Einzellauf ueber 1.10 CHF.

---

## 5. Plausibilitaet des Richters

Vorher festgelegt: die **Streuung** ist `|noten_summe(Lauf 1) −
noten_summe(Lauf 2)|` — zwei unmutierte Laeufe, verschiedene Seeds, sonst
alles gleich. „Bewertet schlechter" heisst: die Notensumme des mutierten
Laufs liegt **unter** der des Basislaufs mit demselben Seed, **und** die
Differenz ist groesser als diese Streuung. Alles innerhalb der Streuung ist
nicht deutbar und wird so benannt.

| Grösse | Lauf 1 (Seed 1) | Lauf 2 (Seed 2) | Streuung | Lauf 3 (mut. 1) | Lauf 4 (mut. 2) | Lauf 5 (mut. 2, Seed 3) |
|---|---|---|---|---|---|---|
| `noten_summe` | 86 | 93 | 7 | 89 | 91 | 82 |
| `noten_median` | 6.5 | 6 | 0.5 | 7.0 | 6 | 5.5 |
| `geht_auf_gesagtes_ein` (Mittel) | 1.21 | 1.40 | 0.19 | 1.29 | 1.20 | 1.21 |
| `bietet_an_statt_vorzuschreiben` | 1.64 | 1.80 | 0.16 | 1.79 | 1.87 | 1.93 |
| `phase_transparent` | 1.64 | 1.53 | 0.11 | 1.64 | 1.47 | 1.29 |
| `korrektur_angenommen` | 1.64 | 1.47 | 0.17 | 1.64 | 1.53 | 1.43 |
| nicht bewertete Abschnitte | 1 | 0 | – | 1 | 0 | 1 |
| Abschnitte ohne Nachricht, trotzdem 8/8 | 1 | 2 | – | 3 | 0 | 0 |

Je Abschnitt (Notensumme 0–8), Lauf 1 gegen Lauf 3 und Lauf 4, Lauf 2 und 5
zum Vergleich:

| Abschnitt | L1 | L3 | L4 | L2 | L5 |
|---|---|---|---|---|---|
| Phase 1: Begriffe | 5 | 6 | 6 | 6 | 8 |
| Weiter zu Phase 2 | – | 7 | 7 | 7 | 7 |
| Phase 2: drei Fragen waehlen | 3 | 5 | 4 | 5 | 5 |
| Weiter zu Phase 3 | 8 | 7 | 8 | 8 | 6 |
| Phase 3: Interviews | 4 | 5 | 4 | 5 | 5 |
| Weiter zu Phase 4 | 7 | 7 | 7 | 8 | 8 |
| Phase 4: Setting und Figuren | 6 | 4 | 5 | 4 | 5 |
| Phase 4: was in kein Feld passt | 5 | 5 | 4 | 7 | 6 |
| Phase 4: Geschichte im Groben | 5 | 4 | 5 | 5 | 4 |
| Weiter zu Phase 5 | 7 | 8 | 6 | 6 | 6 |
| Phase 5: am Material schaerfen | 8 | 8 | 6 | 4 | 5 |
| Weiter zu Phase 6 | 7 | 8 | 6 | 8 | 4 |
| Zitatabfragen | 7 | – | 8 | 4 | 5 |
| Weiter zu Phase 7 | 6 | 7 | 7 | 8 | – |
| /stand | 8 | 8 | 8 | 8 | 8 |

**Urteil zur Plausibilitaet:** nicht deutbar. `festlegung_verloren`: Delta
86 − 89 = −3 (mutiert **ueber** Basis); `richtung_ohne_szenen` Seed 1: 86 − 91
= −5, ebenfalls darueber; Seed 3 ohne Basislauf. Im Abschnitt, in dem Fehler 1
wirkt („was in kein Feld passt"), stehen beide bei 5. Die Summen beruhen auf 14
oder 15 bewerteten Abschnitten, leere erhalten die Vollnote.

---

## 6. Was diese Karte nicht gemessen hat

- **Ursache (b) von Fehler 1** („eine Menuezeile ist keine Geschichte",
  `3290d70`): nicht eigens mutiert, Fehler 2 trifft dieselbe Wurzel praeziser.
- **Ursache (c) von Fehler 1** (Platzhalterfiguren,
  `repo.fuehre_figur_zusammen`): ob eine Stimme nachbenennt, entscheidet das
  Gespraechsmodell. **Gehoert in eine eigene Karte.**
- **Fehler 2 im Lauf:** Pfad in keinem der fuenf Laeufe erreicht.
- **Der Szenenweg und die Tiefe der Phasen 6/7** (`--ohne-szene` in allen
  fuenf Laeufen): nichts ueber `szene_stimmt_zur_planung`,
  `stimmen_unterscheidbar`, `form_eingehalten`, `exposition_erfuellt`.
- **`--set birk`, tag1-Sets** (Datenschutz) und **`--parallel`, `--stoerung`,
  `--pause`, `--fenster-klein`** (nicht Teil der Frage): nicht gefahren.

---

## 7. Was daraus folgt

1. **Eigene Karte (Produktivcode):** in Phase 4 kommt die Geschichte als
   Fliesstext statt als Vorschlagsblock mit Knoepfen —
   `arbeitsstand_vollstaendig.geschichte` = 0 in 5/5 Laeufen, `richtung`/
   `geschichte_speichern` nie angeboten. Solange das so ist, bleibt Fehler 2
   im Lauf unmessbar. Anzusehen: `interview_theater/prompts/phasen/4.md`,
   `interview_theater/vorschlag.py`.
2. **`simulation/kennzahlen.py` (`festlegungslage`):**
   `festlegungsproben_nirgends` trennt „nie gesagt" nicht von „gesagt und
   verloren" (unmutierter Seed 2: 1/3 erhalten, Schritt `festlegungen`
   gescheitert). Die Probe gehoert gegen die Stimmbeitraege abgeglichen.
3. **`simulation/richter.py`:** 3 von 75 Abschnitten nicht bewertet
   (JSON-Fehler), 6 leere Abschnitte mit Vollnote; `noten_summe` ist so ueber
   Laeufe nicht vergleichbar.
4. **`scripts/simulation.py` (`_schritte`):** `--skript auto` faehrt fuer
   `--set 1|2|3` weiter `SCHRITTE` ohne Phasen 2–7 — ohne `--skript tag2`
   misst ein Lauf keinen der beiden Fehler.
5. **`scripts/simulation_abdeckung.py --db`** nach jedem Lauf: 37 von 83
   Knopfarten kamen in fuenf Laeufen vor — ohne die Zahl faellt ein nie
   angefahrener Pfad nicht auf.
