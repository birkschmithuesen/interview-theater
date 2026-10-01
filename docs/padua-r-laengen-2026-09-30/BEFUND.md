# Befund: Laengen-Rhythmus je Szene und Sprachpass (Karte R)

Stand 30.09.2026. Dieses Dokument haelt fest, **woran die Rahmenwerte
geeicht sind** und **was ein Lauf tatsaechlich geliefert hat**. Die Tabellen
unter "Simulationslauf" und "Einzel-Szenenlauf" fuellt Aufgabe 21 bzw. 22.

Alles Material in diesem Dokument ist **erfunden** oder aggregiert: kein
Transkript, kein Klarname, kein Belegzitat aus einem echten Interview.

## 1. Eichung der Rahmenwerte

Die Startwerte der Karte sind **Vorschlaege und ungemessen**. Sie stehen in
`workshop/padua-2026/profil.toml` unter `[laengen.rahmen]` und sind ohne
Codeaenderung aenderbar. Woran sie zu messen sind:

| Quelle | Wie gemessen | Woerter je Szene/Abschnitt |
|---|---|---|
| Herkules.exe, Textbuch (im Repo: `interview_theater/prompts/formen/dialog.md`) | im Regelblock als Zielwert genannt | 700-1500, Median 1400; neun Szenen rund 12.300 |
| Herkules.exe, Repliken (`docs/stilvorlagen/2026-09-06/analyse.md`) | Median je Replik | 8 Woerter |
| Dortmund Gruppe 1, Textbuch **v2** (06.09.2026, 19:08, Phase-6-Prosa, drei Abschnitte) | Architekt, 30.09.2026; Abschnittskoerper nach der Ueberschrift, Tokens `\w+('\w+)?`, Markdown entfernt | "Am Steg" (chor) **825**, "Elf Grad" (dialog) **802**, "Fronten" (rap) **603** |
| Dortmund Gruppe 1, Textbuch **v1** (06.09.2026, 14:09, vier erhaltene Abschnitte) | ebenso | **794 / 309 / 317 / 293** |

**Der Befund an diesen Zahlen -- zwei Saetze, und beide tragen die Karte:**

1. **v2 ist flach.** 825 / 802 / 603 Woerter, drei verschiedene Formen
   (chor / dialog / rap), und trotzdem praktisch eine Laenge. Genau dagegen ist
   der Rhythmus-Wuerfel gebaut. v1 war ungleich (794 / 309 / 317 / 293) -- der
   Unterschied zwischen v1 und v2 ist also nicht die Geschichte, sondern die
   Glaettung.
2. **Die Startwerte der Karte liegen schon bei etwa einem Viertel.** Dialog
   200-450 gegen Herkules 700-1500 und gegen Dortmund v2 (802 fuer die
   Dialogszene). Der Faktor 0,25 obendrauf ergibt **50-110 Woerter** je
   Dialogszene -- rund eine Minute Buehnenzeit.
   **Das ist OFFENE FRAGE 1 an Birk:** sind die Startwerte der Normalfall oder
   schon die Instagram-Laenge? Beide Antworten sind eine Zeile TOML.

**Was die Formen betrifft:** die Karte nennt Chor/Lied 80-200, Rap 120-250,
Dialog 200-450. **Monolog nennt sie nicht** -- hier steht 150-350 als
Vorschlag (OFFENE FRAGE 4). Gegen Dortmund v2 gemessen sind alle vier Rahmen
deutlich kuerzer als das, was dort entstand; die Rangfolge (Chor kuerzer als
Dialog) deckt sich dagegen **nicht** mit v2, wo die Chorszene die laengste war
-- ein weiteres Zeichen fuer die Glaettung.

## 2. Gedankenstriche: der Anker

Dortmund v2 hatte **einen** Gedankenstrich in **2.230** Woertern (Architekt,
30.09.2026) -- also **0,45 je 1.000**. Der Grenzwert
`sprachpass.gedankenstriche_je_1000 = 6.0` liegt damit gut dreizehnmal
darueber: er trifft die Inflation und nicht den einzelnen Strich. Die drei
anderen Grenzwerte (je 1.000: `nicht_sondern` 2,0, `adjektiv_dreier` 2,0; je
Text: `fazitsatz` 1) sind **ungemessen** -- sie stehen im Profil und sind ohne
Code aenderbar.

## 3. Was die Zaehler an erfundenem Material finden

Gefahren am 01.10.2026 mit `uv run python -m scripts.laengen_probe --markdown`
(dazu `--formen dialog,dialog,dialog,dialog` und `--faktor 0.25`). Es war eine
**Attrappe** statt eines Modells, die Datenbank eine Wegwerf-Datei -- der Lauf
hat **nichts gekostet**. Seed ist die `chat_id` 1 der Probe.

Jede Form einmal, Faktor 1:

| Szene | Form | Budget | Woerter vorher | Woerter nachher | Zaehler vorher | Zaehler nachher | Laeufe |
|---|---|---|---|---|---|---|---|
| 1 | dialog | 450 | 730 | 8 | geda=3 | - | 2 (szene,szene_nachpass) |
| 2 | chor | 100 | 729 | 8 | nich=1 | - | 2 (szene,szene_nachpass) |
| 3 | rap | 120 | 726 | 8 | adje=1 | - | 2 (szene,szene_nachpass) |
| 4 | lied | 200 | 728 | 8 | fazi=1 | - | 2 (szene,szene_nachpass) |
| 5 | monolog | 190 | 730 | 8 | geda=3 | - | 2 (szene,szene_nachpass) |

Viermal dieselbe Form -- der Rhythmus ist nicht flach (450 / 250 / 200 / 450):

| Szene | Form | Budget | Woerter vorher | Woerter nachher | Zaehler vorher | Zaehler nachher | Laeufe |
|---|---|---|---|---|---|---|---|
| 1 | dialog | 450 | 730 | 8 | geda=3 | - | 2 (szene,szene_nachpass) |
| 2 | dialog | 250 | 729 | 8 | nich=1 | - | 2 (szene,szene_nachpass) |
| 3 | dialog | 200 | 726 | 8 | adje=1 | - | 2 (szene,szene_nachpass) |
| 4 | dialog | 450 | 728 | 8 | fazi=1 | - | 2 (szene,szene_nachpass) |

Faktor 0,25 ("Kuerzer/Instagram") -- dieselben Formen, rund ein Viertel:

| Szene | Form | Budget | Woerter vorher | Woerter nachher | Zaehler vorher | Zaehler nachher | Laeufe |
|---|---|---|---|---|---|---|---|
| 1 | dialog | 110 | 730 | 8 | geda=3 | - | 2 (szene,szene_nachpass) |
| 2 | chor | 30 | 729 | 8 | nich=1 | - | 2 (szene,szene_nachpass) |
| 3 | rap | 30 | 726 | 8 | adje=1 | - | 2 (szene,szene_nachpass) |
| 4 | lied | 50 | 728 | 8 | fazi=1 | - | 2 (szene,szene_nachpass) |
| 5 | monolog | 50 | 730 | 8 | geda=3 | - | 2 (szene,szene_nachpass) |

Lesart: jede Szene bekommt **genau einen** Nachpass (`Laeufe = 2`), jedes der
vier Sprachmuster loest ihn aus, und nach dem Nachpass findet kein Zaehler
mehr etwas. "Woerter vorher" zaehlt die rohe Modellantwort samt Kopfzeilen,
"Woerter nachher" den gespeicherten Volltext -- die Attrappe antwortet im
Nachpass absichtlich kurz und sauber; den Fehlschlagfall (zu lang,
Zitatverlust) zeigen die Tests in `tests/test_nachpass*.py`.

## 4. Simulationslauf Padua

(Fuellt Aufgabe 21. Tabelle: Szene | Form | Budget | Wortzahl erster Lauf |
nach Kuerzung | Sprachpass-Zaehler vorher/nachher; dazu Kosten und Laeufe je
Szene.)

## 5. Einzel-Szenenlauf Phase 7

(Fuellt Aufgabe 22. Derselbe Tabellenkopf, plus ein Vorher/Nachher-Auszug von
hoechstens zehn Zeilen.)

## 6. Kosten

(Fuellt Aufgabe 21/22 aus der Tabelle `aufruf`, getrennt nach `art`:
`szene`, `kurzgeschichte`, `szene_nachpass`, `kurzgeschichte_nachpass`.)
