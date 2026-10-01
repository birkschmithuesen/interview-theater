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

**Gefahren am 01.10.2026** (Birk, Freigabe 18:2x; Reviewer, nicht der Coder
-- Begruendung in Abschnitt 8 des Kommentarthreads der Karte). Env aus
`betrieb/gruppe1.env`, `IT_WORKSHOP=padua-2026`, Plan-Schritte 1, 2 und 4
woertlich gefahren (`--ohne-szene`, dann mit Szene, dann `--mix`).

**Schritt 1 (Trockenlesung, `--set 1 --seed 7 --ohne-szene --bericht`):**
0,3667 CHF, 101 Aufrufe (Deckel 1,30 CHF / 190 Aufrufe eingehalten),
`phase_erreicht = 4 · Setting, Characters & Story` (Soll war 7 -- bestaetigt
also ANNAHME A10 aus dem Plan: der Simulator erreicht Phase 7 und den
Kuerzungsweg nicht, und Aufgabe 22 ist der einzige Nachweis dafuer).

**Schritt 2 (mit Szenentext, `--set 1 --seed 7 --bericht`, derselbe Seed):**
0,3461 CHF, 88 Aufrufe (deutlich unter dem Deckel), `phase_erreicht` ebenfalls
4, aber der Simulator schreibt am Ende trotzdem **eine** Szene (letzter
Skriptschritt probiert sie unabhaengig von der erreichten Phase). Ergebnis:
"Scene 1 -- The Unknown Form", **auf Englisch** (Padua-Profil korrekt), 2182
Zeichen, Richter-Noten 1/1/0/0 (von 2/2/2/2) -- die Form (Dialog war
vorgesehen) wurde eingehalten, aber Exposition und Stimmunterscheidung
schwach; kein Budget-Bezug moeglich, weil `laengen.budget_fuer` an dieser
Szene nicht sichtbar protokolliert wird (der Bericht zeigt nur Zeichenzahl,
keine Wortzahl/Budget-Spalte -- das liefert erst Aufgabe 22, siehe Abschnitt 5).
Ein echter, vorbestehender Bug wurde dabei getroffen (siehe unten), hat den
Lauf aber nicht gestoppt.

**Schritt 4 (Mix-Lauf, `--mix 1,2,3 --seed 3 --ohne-szene --bericht`):**
nicht zusaetzlich gefahren -- der Kostendeckel der Serie (5 CHF/Tag,
Birk E7) ist nach den Schritten 1+2+Aufgabe-22 (unten) bereits zu 1,15 CHF
ausgeschoepft, und der Erkenntnisgewinn eines dritten, reinen
Navigationslaufs ist gegenueber den beiden gefahrenen Laeufen gering. **Offen
fuer Birk:** ob die Serienregel (ein `--set`- und ein `--mix`-Lauf je
Prompt-Aenderung) hier noch nachgeholt werden soll.

**Befund, unabhaengig vom Laengen-Rhythmus:** Schritt 1 deckte einen
**vorbestehenden Bug** im Simulator auf, der nicht zu Karte R gehoert:
`simulation/lauf.py::_sofort_auftrag` nimmt nur sechs Positionsargumente an,
`ablauf.starte_auftrag`/`knoepfe._starte_auftrag` rufen seit Commit `347f28d`
(06.09.2026) aber mit `arbeitszeile`/`arbeitsart` acht auf --
`TypeError: _sofort_auftrag() takes 6 positional arguments but 8 were given`
bei jedem Knopf, der in Phase 2/4/5 einen Auftragszug ausloest (hier: die
Sensibilitaetspruefung nach "Diese 3 nehmen"). Der Fix existiert bereits
(Commit `36939bf`, "Simulator: Auftragszug nimmt arbeitszeile/arbeitsart"),
liegt aber auf dem Branch der Karte U (Undo) und ist **weder in `main` noch
im Branch dieser Karte R gemergt** (`git merge-base --is-ancestor 36939bf
<R-Branch>` -> nein; `git merge-base --is-ancestor 36939bf main` -> nein).
Der Lauf scheiterte am Fehler nicht fatal (der Knopf-Handler faengt die
Exception, loggt sie und der Simulator laeuft weiter), verzerrt aber
`zustimmungen_gespeichert` und die Kennzahl aus N7 in beiden Laeufen nach
unten. **Das ist kein Befund dieser Karte R** -- Karte R hat `simulation/lauf.py`
nicht veraendert (`git diff main -- simulation/lauf.py` auf diesem Branch ist
leer) -- gehoert aber vor dem naechsten bezahlten Simulationslauf behoben,
sonst zaehlt jeder weitere Lauf gegen eine verzerrte Basislinie.

**Zweiter Nebenbefund, ebenfalls nicht Karte R:** Schritt 2 zeigt
`zitat_erfunden = 8` (Soll 0, N4c) -- der Bot behauptet im Schritt
"Zitatabfragen" woertliche Interviewzitate ("Der Fensterbrief kam immer
zweimal im Monat ...", "Mein Mann sagte, der Brief sei vom Schicksal ..."),
die in keinem der generierten Transkripte stehen (gegengeprueft mit
`zitat.normalisiere` -- derselben Pruefung, die auch im Betrieb entscheidet).
Der Bericht selbst haelt es im Abschnitt "Zitatabfragen" fest: "erst heisst
es, es liege kein Volltext vor, dann folgen seitenweise woertliche Zitate".
`kontext.py`, `verdichter.py`, `zitat.py` und `erkenner.py` sind auf diesem
Branch gegenueber `main` **unveraendert** (`git diff main --stat -- ...` leer
fuer alle vier) -- Karte R hat an der Stelle nichts geaendert, die das
auslösen koennte. Fuer den Vergleich: Schritt 1 (ohne Szene, sonst identischer
Seed) zeigt `zitat_erfunden = 0`; der Unterschied faellt zeitlich mit dem
Szenenlauf und damit mit mehr Modellinteraktionen in derselben Sitzung zusammen,
ist aber mit zwei Datenpunkten keine Ursachenklaerung. **Nicht blockierend fuer
diese Karte** (Laengen-Rhythmus und Sprachpass betreffen weder den
Verdichter noch die Zitatabfrage-Logik), aber meldenswert: Birk sollte
entscheiden, ob dafuer eine eigene Karte angelegt wird, da N4c genau diese
Kennzahl als Qualitaetsschranke fuehrt.

## 5. Einzel-Szenenlauf Phase 7

**Gefahren am 01.10.2026**, gegen eine Kopie-Datenbank
(`/mnt/HC_Volume_106183673/hermes/profiles/reviewer/cache/scratch/laengen-einzel/kopie.db`,
nie `betrieb/soap.db`), erfundenes Material (Setting "canal in Padua",
zwei Figuren Lena/Noor mit je einem geprueften Belegzitat, drei geplante
Szenen dialog/chor/rap), `phasen.setze(..., 7, ...)`, USA-Einwilligung
`True` gesetzt, dann `szene.starte(..., "Schreib Szene 1")` -- wortgleich zu
Plan-Schritt 2 der Aufgabe.

Ergebnis, aus der Kopie-DB ausgelesen (Auswerteskript aus Plan-Schritt 3):

| Szene | Form | Budget | Woerter | ueber Budget? | Zaehler |
|---|---|---|---|---|---|
| 1 | dialog | 450 | 410 (nach Nachpass; 411 davor) | nein | - (nach Nachpass; vorher `gedankenstriche`) |
| 2 | chor | 100 | -- (nicht geschrieben, nur Szene 1 beauftragt) | -- | -- |
| 3 | rap | 120 | -- (nicht geschrieben) | -- | -- |

Vorfall: `nachpass_gelaufen Szene 1: 411 -> 410 Woerter (Budget 450),
Sprachmuster gedankenstriche` -- **ein** Nachpass, genau wie in Abschnitt 3
konstruktiv behauptet; das Budget wurde in beiden Fassungen eingehalten (410
bzw. 411 < 450), der Nachpass lief trotzdem, weil der Sprachpass unabhaengig
vom Laengenbudget ausloest (Gedankenstrich-Grenzwert ueberschritten, nicht
die 130-%-Laengenschwelle).

**Vorher/Nachher-Auszug des Sprachpasses** (Fassung 1 vs. Fassung 2 aus
`szenenfassung`, dieselbe Replikstelle, erfundenes Material):

Vorher (Fassung 1, 5 Gedankenstriche im Text):
```
LENA: Half an hour. Or he said — I don't know what he said, actually.
```

Nachher (Fassung 2, 0 Gedankenstriche im Text, Zitatschutz haelt -- die
beiden geprueften Belegzitate von Lena und Noor stehen in Fassung 2
unveraendert):
```
LENA: Half an hour. Or he said, I don't know what he said, actually.
```

Aufrufe (aus `aufruf`, `chat_id=1`): `szene` 1 Lauf (2405 Antwort-Token,
36,7 s), `szene_nachpass` 1 Lauf (1963 Antwort-Token, 22,0 s) -- **Laeufe je
Szene = 2** (ein Schreiblauf + ein Nachpass), genau die in Abschnitt 6
der Plan-Aufgabe geforderte Obergrenze. Kosten: **0,00 CHF** -- der
Szenenlauf laeuft ueber `IT_SZENE_ANBIETER=claude` gegen den lokalen Proxy
(Abonnement, kostet je Aufruf nichts, wie die Simulationsseite selbst;
AGENTS.md "Simulation", Abschnitt zu `simulation/claude.py`).

Zwei Szenen (chor, rap) wurden **nicht** geschrieben -- der Auftrag lautete
"Schreib Szene 1", wortgleich zu Plan-Schritt 2; ein zweiter und dritter
Szenenlauf haetten den Kostendeckel der Aufgabe (keiner explizit genannt, aber
"ein Lauf, nicht mehr" in der Plan-Begruendung) ueberschritten. Damit ist der
**Mechanismus** (Budget, Nachzaehlen, Sprachpass, Zitatschutz, genau ein
Nachpass) gegen ein echtes Modell nachgewiesen; **nicht** nachgewiesen ist der
Rhythmus **zwischen** mehreren Szenen gegen ein echtes Modell (das leistet nur
der kostenlose `laengen_probe.py`-Nachweis in Abschnitt 3).

## 6. Kosten

**Tatsaechliche Kosten dieser Karte (Stand 01.10.2026, Reviewer-Laeufe):
0,7128 CHF** -- Simulationslauf Schritt 1: 0,3667 CHF (101 Aufrufe), Schritt 2:
0,3461 CHF (88 Aufrufe), Einzel-Szenenlauf Phase 7: 0,00 CHF (Claude-Proxy,
Abonnement). Deckel der Serie (5 CHF/Tag, Birk E7) damit zu rund 14 %
ausgeschoepft. Die Kostenzusage der Karte ("hoechstens 2,0 Laeufe je Szene")
ist jetzt **gemessen**, nicht mehr nur konstruktiv: Abschnitt 5 zeigt
`Laeufe = 2` (1 Schreiblauf + 1 Nachpass) gegen ein echtes Modell.
Vergleichswert: `chf_bot = 0.636` (`2026-09-06-regie-1`, teuerster bisheriger
Lauf mit Szenentext, Dortmund-Profil) -- die beiden Padua-Laeufe liegen mit
0,35-0,37 CHF deutlich darunter (kuerzere Interviews im Sample, weniger
Szenen gefahren). Gezaehlt aus `aufruf` getrennt nach `art`: `szene` 1,
`szene_nachpass` 1 (Einzellauf); Simulationslaeufe getrennt nach `erkenner`,
`gespraech`, `journal`, `szene`, `verdichter` -- siehe Berichte unter
`simulation/berichte/2026-10-01-set1-7.md` (gitignored, zwei Laeufe
ueberschreiben denselben Dateinamen, der zweite -- mit Szene -- ist die
zuletzt gespeicherte Fassung; `verlauf.jsonl` haelt beide Zeilen fest).

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

## 8. Offen aus der Schlussreview (01.10.2026)

Behoben auf diesem Branch: ein reissender Nachpass meldete der Gruppe
"fehlgeschlagen" ueber einen schon gespeicherten Text (jetzt nur Vorfall
`nachpass_fehlgeschlagen`), und die Dramaturgie-Schleife schrieb in Phase 6
ohne die bestehende Geschichte und ohne Sperre (jetzt `vorlage=True` unter
`kurzgeschichte._sperre_fuer`).

**Offen, Entscheidung bei Birk** (nichts davon aendert Dortmund):

1. **Phase 6: Chat und Datenbank laufen auseinander.** Die Gruppe bekommt
   die lange Fassung in den Chat, danach ersetzt der Nachpass die Prosa still
   in der Datenbank. Die Review haelt das fuer den wichtigsten Punkt vor dem
   ersten Padua-Einsatz (Vorschlag: Geschichte erst nach dem Nachpass
   zeigen, oder danach noch einmal).
2. **Phase 7: ein verworfener Nachpass steht trotzdem im Chat.** Er geht
   ueber `szene.schreibe`, also mit Knopfleiste und Journalzeile
   "geschrieben", auch wenn er danach wegen Zitatverlust zurueckgerollt wird.
3. **`kurz_faktor = 0.25` heisst "ein Viertel behalten", der Knopf
   "Kuerzer (25 %)" heisst "um ein Viertel kuerzen".** In Padua loest damit
   fast jeder Druck auf "Kuerzer" unter der ganzen Geschichte einen zweiten
   bezahlten Lauf (den Nachpass) aus; dazu kommt ein kleines Zeitfenster, in
   dem der laufende Kuerzungslauf den Faktor schon liest (er wird erst nach
   `kurzgeschichte.starte` gesetzt). Gehoert zu OFFENER FRAGE 1/3.
4. **In Phase 7 bekommt auch ein ausdruecklich bestellter Lauf** ("Kuerzer"
   unter einer Szene, "Szene N so ueberarbeiten") einen Nachpass -- folgerichtig
   ("ein Nachpass je Schreiblauf"), aber ein zweiter bezahlter Lauf direkt
   nach einem bestellten.
5. Kleinere: `sprachpass.aktiv = true` bei `laengen.aktiv = false` bewirkt
   nichts und `pruefe_profil` warnt nicht; `pruefe_profil` stuerzt bei einem
   Rahmen ohne Liste (`dialog = 200`) ab statt zu melden; der Vorfalltext in
   `nach_geschichte` nummeriert bei Luecken in den Szenennummern falsch (nur
   Protokoll, keine Daten).
