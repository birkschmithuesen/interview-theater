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

## 7. Mutationsnachweis

Gefahren am 01.10.2026 (Aufgabe 19), kostenlos. Je Regel eine Mutation am
Quelltext, danach jeder genannte Test **einzeln**, danach `git checkout` der
Datei. Vor jeder Mutation liefen die genannten Tests gruen; nach jeder war
die Datei wieder sauber (`git diff --quiet HEAD`), und `git status
--porcelain` war am Ende leer bis auf die `.cc-*`-Dateien des Laufs.

| # | Regel | Mutation | Rot | Gruen geblieben (und warum das kein Loch ist) |
|---|---|---|---|---|
| 1 | Der Wuerfel ist nie flach | `workshop.VORGABE_WERTE["laengen"]["muster"]`: alle vier Eintraege `["mittel","mittel","mittel"]` | ✅ `test_laengen.py::test_jedes_muster_traegt_mindestens_zwei_verschiedene_stufen`, ✅ `test_laengen_budget.py::test_kein_muster_der_vorgabe_ist_flach` | `test_laengen_budget.py::test_eine_folge_aus_einer_form_ist_nicht_flach` -- **zu Recht**: `laengen.muster_liste` wirft flache Muster heraus und faellt auf `MUSTER_RUECKFALL` zurueck. Die Regel haelt also auch unter der Mutation, nur ein zweites Netz faengt sie |
| 2 | Dasselbe Seed liefert dasselbe Muster | `muster_fuer`: `random.randrange(len(liste))` | ✅ `test_dasselbe_seed_liefert_dasselbe_muster`, ✅ `test_dasselbe_seed_liefert_dasselbe_budget` | -- |
| 3 | Das Muster wird zyklisch gelesen | `stufe_fuer`: `min(n - 1, len(muster) - 1)` | ✅ `test_das_muster_wird_zyklisch_gelesen` | -- |
| 4 | Faktor 0,25 | `_aus_stufe`: `* float(faktor)` gestrichen | ✅ `test_der_faktor_verkuerzt_alle_budgets`, ✅ `test_laengen_faktor.py::test_der_faktor_wirkt_auf_das_naechste_budget` | -- |
| 5 | Die 130-%-Schwelle | `zu_lang`: `* nachzaehl_schwelle(profil)` gestrichen | ✅ `test_zu_lang_greift_erst_ab_der_schwelle` | -- |
| 6 | Genau EIN Lauf | `nachpass.nach_szene`: im Zweig "nach dem Nachpass noch zu lang" ein zweites `szene_modul.schreibe(...)` | ✅ `test_nachpass.py::test_zwei_zu_lange_ergebnisse_ergeben_trotzdem_einen_lauf` | `test_laengen_aus.py::test_padua_haengt_genau_einen_lauf_an` -- **zu Recht**: dort ist die zweite Antwort der Attrappe kurz, der Zweig wird nie betreten. Der erste Test faehrt genau diesen Zweig |
| 7 | Der Grenzwert des Zaehlers | `sprachpass.ueberschreitungen`: `>=` -> `>` und Grenzwert-Vergleich `> 1000` (meldet nie) | ✅ `test_sprachpass_notiz.py::test_ab_der_grenze_wird_gemeldet`, ✅ `test_nachpass.py::test_nur_sprache_ohne_laenge_laeuft_auch` | -- |
| 8 | Der Zitatschutz | `nach_szene`: `if verloren:` -> `if False:` | ✅ `test_ein_veraendertes_zitat_verwirft_den_lauf` | -- |
| 9 | Der Zitatschutz auch in Phase 6 | `nach_geschichte`: `if verloren:` -> `if False:` | ✅ `test_nachpass_prosa.py::test_ein_verlorenes_zitat_wird_verworfen` | -- |
| 10 | Die Abschnittszahl-Wache | `nach_geschichte`: `if len(abschnitte) != anzahl:` -> `if False:` | ✅ `test_eine_andere_abschnittszahl_wird_verworfen`, ✅ `test_bei_verwerfen_wird_nichts_geschrieben` | -- |
| 11 | Dortmund ist aus | `VORGABE_WERTE["laengen"]["aktiv"]`: `True` | ✅ `test_laengen.py::test_die_vorgabe_hat_den_schalter_aus`, ✅ `test_laengen_aus.py::test_ein_szenenlauf_bleibt_ein_aufruf`, ✅ `::test_kein_laengenblock_im_prompt` | -- |
| 12 | Dortmunds Prosa-Prompt bleibt zeichengleich | `kurzgeschichte.ZEILE_GESAMTLAENGE`: `1.500` -> `1.400` | ✅ `test_laengen_prosa.py::test_die_ersetzbare_zeile_steht_wirklich_in_der_anweisung` | `test_ohne_budget_ist_die_systemanweisung_zeichengleich` -- **zu Recht**: `ANWEISUNG` traegt die Zeile woertlich, die Mutation trifft nur die Konstante, mit der ersetzt wird. Dortmunds Text bleibt also tatsaechlich zeichengleich (der SHA stimmt); kaputt ist die Ersetzung fuer Padua, und genau die meldet der andere Test |
| 13 | Die deutsche Negativliste bleibt unberuehrt | `prompts/theater-tells.md`: ein Buchstabe gross | ✅ `test_sprachpass_prompt.py::test_die_deutsche_liste_bleibt_unberuehrt`, ✅ `test_profil_bitgleich.py` (2 rot) | -- |
| 14 | Der Laengenblock wird nie gekuerzt | `szene._REIHENFOLGE`: `"laenge"` gestrichen | ✅ `test_laengen_szene.py::test_der_laengenblock_steht_direkt_hinter_der_aufgabe`, ✅ `::test_mit_profil_steht_das_budget_im_nutzertext` | -- |
| 15 | Kein Modellaufruf im Befund | `nachpass.befund`: Zeile `klm = None` | ✅ `test_nachpass.py::test_der_befund_ruft_kein_modell` | -- |

**Ergebnis:** jede der 15 Regeln ist von mindestens einem Test bewacht, der
unter ihrer Mutation rot wird. Drei der im Plan genannten Tests blieben
gruen; bei allen dreien ist das das richtige Verhalten (Spalte rechts), kein
fehlender Waechter -- deshalb kam kein Test dazu.
