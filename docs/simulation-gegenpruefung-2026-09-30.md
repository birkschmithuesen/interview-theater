# Gegenpruefung der User-Simulation, 30.09.2026

**Frage** (Birk): prueft `simulation/` sinnvoll — faengt sie echte Fehler?

**Verfahren:** die zwei belegten Dortmunder Fehler vom 06.09.2026 per
Mutation wieder einbauen und messen, ob Kennzahlen oder Richter sie melden.
Mutation ueber `simulation/mutation.py` (Monkey-Patch aus `simulation/`
heraus), Produktivcode unangetastet.

**Basis:** `d8deb6c`, Suite 2768 passed / 1 skipped.

**PII:** keine Echtdaten. Gefahren wurden ausschliesslich die erfundenen Sets
1–3 (`simulation/interviews/`); `--set birk` und die tag1-Sets sind bewusst
NICHT gelaufen — ihr Material ist aus echten Interviews abgeleitet und hat am
US-Modell der Simulationsseite nichts zu suchen. In diesem Bericht stehen nur
Zahlen: keine Modellantwort, kein Chatverlauf, kein Belegzitat. Die
Laufberichte selbst sind gitignored.

---

## 0. Urteil

<!-- Nach Aufgabe 12 zu fuellen. Zwei Urteile, nicht eines. -->

**Urteil A — die Simulation, wie sie auf `d8deb6c` war:** …

**Urteil B — die Simulation nach dieser Karte:** …

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

<!-- Aus /tmp/abdeckung-vorher.md uebernehmen: die drei Phasentabellen. -->

### Was der Verdacht traf und was nicht

<!-- Die Tabelle "Praemissenpruefung" aus /tmp/abdeckung-vorher.md, dazu die
     zwei Befunde, die der Verdacht nicht nennt. -->

### Nach der Korrektur

<!-- Die Praemissenpruefung aus /tmp/abdeckung-nachher.md: alles "bereinigt". -->

### Knoepfe und Modellwege im gefahrenen Lauf

<!-- python -m scripts.simulation_abdeckung --db <Basislauf-DB>, Abschnitte
     "Knopfarten im gefahrenen Lauf" und "Modellwege im gefahrenen Lauf". -->

---

## 2. Fehler 1: 22 von 42 Festlegungen verloren

**Quelle:** `docs/analyse-phase4-datenverlust-2026-09-06.md` § 0, § 2.7, § 3.
**Fix:** `e56a892`, `bbe301e`, `36030ff` (07.09.2026).
**Mutiert wurde** die Hauptursache — es gibt kein Fach fuer eine Festlegung,
die in kein Feld passt (`repo.schreibe_festlegung` → `None`). Warum diese und
nicht die Menuezeile oder die Platzhalterfiguren: siehe Abschnitt 6.

**Deterministischer Nachweis, dass die Mutation greift:**
`tests/test_simulation_mutation.py::test_mutiert_schreibt_auch_der_erkenner_nichts`
— <!-- passed/failed --> .

| Kennzahl | Basis (Seed 1) | mutiert (Seed 1) | Soll | erkannt? |
|---|---|---|---|---|
| `festlegungen` | | | > 0 | |
| `festlegungsproben_erhalten` | | | alle | |
| `festlegungsproben_nur_journal` | | | 0 | |
| `festlegungsproben_nirgends` | | | 0 | |
| Schritt `festlegungen` gescheitert | | | nein | |
| **vorher vorhandene Kennzahlen** | | | | |
| `zustimmungen_gespeichert` | | | alle | |
| `behauptete_schreibvorgaenge` | | | 0 | |
| `journal_je_art` (`vorgeschlagen`) | | | – | |
| `nachrichten_je_festlegung_median` | | | <= 2 | |
| `arbeitsstand_vollstaendig` | | | voll | |

**Protokoll:** gefunden / nicht gefunden — woran:

<!-- Ein Absatz. "Woran" heisst: welche Kennzahl, welcher Wert, und ob eine
     der VORHER vorhandenen sich mitbewegt hat. -->

---

## 3. Fehler 2: aus 3 Szenen wurden 6

**Quelle:** `docs/analyse-phase5-chaos-2026-09-06.md` § 4, § B.
**Fix:** `3ae76ab`, `c9af872` (30.09.2026); davor schon
`repo.gleiche_szenenfolge_ab` (06.09.2026).
**Mutiert wurde** `szenenfolge.szenen_der_richtung` → `[]`.

**Zu beachten bei der Deutung:** seit `repo.gleiche_szenenfolge_ab` entfernt
ein Szenenfolge-Lauf keine Szene mehr. Der Schaden hat heute eine andere
Gestalt als am 06.09.: nicht „drei weg, sechs neu", sondern „Titel 1–3
ueberschrieben, 4–6 dazu" (`titel` steht nicht in
`repo.GESCHUETZTE_SZENENFELDER`) — plus 110 s Wartezeit. Die Kennzahl misst
beide Gestalten.

**Deterministischer Nachweis:**
`tests/test_simulation_mutation.py::test_mutiert_verliert_die_richtung_ihre_szenen_und_startet_den_lauf`
— <!-- passed/failed --> .

| Kennzahl | Basis (Seed 1) | mutiert (Seed 1) | Soll | erkannt? |
|---|---|---|---|---|
| `szenenfolge_nach_richtung` | | | 0 | |
| `szenen_aus_richtung` | | | ja | |
| `szenen_neuaufbauten` | | | 0 | |
| `szenen_form_verloren` | | | 0 | |
| `szenen_aktiv` | | | – | |
| `szenenfolge_laeufe` | | | – | |
| **vorher vorhandene Kennzahlen** | | | | |
| `szenen_gesamt` (`formlage`) | | | – | |
| `form_bestaetigt` / `form_gesetzt_ohne_vorschlag` | | | 0 gesetzt | |
| `rahmen_ueberschrieben` | | | 0 | |
| `dauer_s`, `chf_bot` | | | – | |
| `vorfaelle` | | | – | |

**Protokoll:** gefunden / nicht gefunden — woran:

<!-- Ein Absatz. -->

---

## 4. Die Laeufe

| # | Set | Seed | Skript | Schalter | Mutation | Dauer | `chf_bot` | `phase_erreicht` |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | tag2 | `--ohne-szene` | – | | | |
| 2 | 1 | 2 | tag2 | `--ohne-szene` | – | | | |
| 3 | 1 | 1 | tag2 | `--ohne-szene` | `festlegung_verloren` | | | |
| 4 | 1 | 1 | tag2 | `--ohne-szene` | `richtung_ohne_szenen` | | | |

Summe: <!-- CHF --> von 10 CHF freigegeben.

---

## 5. Plausibilitaet des Richters

Vorher festgelegt: die **Streuung** ist `|noten_summe(Lauf 1) −
noten_summe(Lauf 2)|` — zwei unmutierte Laeufe, verschiedene Seeds, sonst
alles gleich. „Bewertet schlechter" heisst: die Notensumme des mutierten
Laufs liegt **unter** der des Basislaufs mit demselben Seed, **und** die
Differenz ist groesser als diese Streuung. Alles innerhalb der Streuung ist
nicht deutbar und wird so benannt.

| Grösse | Lauf 1 (Seed 1) | Lauf 2 (Seed 2) | Streuung | Lauf 3 (mut. 1) | Lauf 4 (mut. 2) |
|---|---|---|---|---|---|
| `noten_summe` | | | | | |
| `noten_median` | | | | | |
| `geht_auf_gesagtes_ein` (Mittel) | | | | | |
| `bietet_an_statt_vorzuschreiben` | | | | | |
| `phase_transparent` | | | | | |
| `korrektur_angenommen` | | | | | |
| nicht bewertete Abschnitte | | | | | |

Je Abschnitt, Lauf 1 gegen Lauf 3 und Lauf 4:

<!-- Tabelle Abschnitt x Notensumme, aus verlauf.jsonl bzw. den
     Berichtsdateien. Keine Begruendungstexte -- die sind Modellausgabe. -->

**Urteil zur Plausibilitaet:** …

---

## 6. Was diese Karte nicht gemessen hat

- **Ursache (b) von Fehler 1** — „eine Menuezeile ist keine Geschichte"
  (`3290d70`): als eigene Mutation nicht gefahren, weil Fehler 2 dieselbe
  Wurzel praeziser trifft.
- **Ursache (c) von Fehler 1** — Platzhalterfiguren, die beim Nachbenennen
  eine zweite Zeile anlegen (`repo.fuehre_figur_zusammen`): ohne Modell nicht
  zuverlaessig ausloesbar, ob eine simulierte Stimme nachbenennt, entscheidet
  das Gespraechsmodell. **Gehoert in eine eigene Karte.**
- **Der Szenenweg** (`--ohne-szene` in allen vier Laeufen): kein Szenentext
  ist geschrieben worden, also sagt dieser Bericht nichts ueber
  `szene_stimmt_zur_planung`, `stimmen_unterscheidbar`, `form_eingehalten`
  oder `exposition_erfuellt`. Beide Fehler liegen vor dem Schreiben.
- **Die Phasen 6 und 7** in der Tiefe: der Lauf erreicht sie, schreibt aber
  nichts.
- **`--set birk` und die tag1-Sets:** aus Datenschutzgruenden nicht gefahren.
- **`--parallel`, `--stoerung`, `--pause`, `--fenster-klein`:** nicht Teil
  dieser Frage.

---

## 7. Was daraus folgt

<!-- Nach Aufgabe 12: hoechstens fuenf Punkte, jeder mit einer Datei oder
     einem Kennzahlnamen. Keine Wunschliste. -->
