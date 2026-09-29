# Kalibrierung der Kontextgrenzen gegen die heutigen Prompts

Stand 30.09.2026, Padua K (Task 2), nach dem Merge von `feat/kontext-3-5`
(`daed9aa`). Gemessen wird, **wie viel Platz die Prompts heute brauchen**, und
das gegen jede Budget- und Grenzkonstante aus `interview_theater/kontext.py`
und `interview_theater/szene.py`. **Keine Konstante wurde geändert.** Das
Anpassen ist Task 3. Die Empfehlungen stehen am Ende.

> **Ersetzt ältere Zahlen.** Die Werte vom 06.09. in
> `docs/prompt-audit/2026-09-06/kontext-3-5-bericht.md` gelten nicht mehr.
> Dasselbe gilt für die Prosa zu Block 1 in `SPEC-kontext-architektur.md`
> § 6.2 („23.010–28.018 Zeichen“). Beide stammen aus der Zeit vor dem
> Prompt-Umbau auf main (sieben Phasen, Phasentexte, Workshop-Profil). Die
> gültigen Zahlen stehen in diesem Dokument. Die historischen Dokumente
> bleiben unverändert.

## Was gemessen wurde, womit und woran

**Werkzeug:** `scripts/kalibriere_kontext.py` (neu, Test
`tests/test_kalibriere_kontext.py`). Es geht **denselben Weg wie
`kontext.baue`**:

1. `_baue_fenster_eintraege`
2. `_bloecke`
3. `_systemgroesse`
4. `_kuerze_auf_budget`

Vor der Kürzung hält eine Kopie der Blöcke den **Rohbedarf** fest. Der Test
prüft, dass die Zahl „nach Kürzung“ zeichengleich mit dem Rückgabewert von
`kontext.baue` ist. Das Skript braucht kein Netz, ruft kein Modell auf und
liest keine Betriebs-DB. Es gibt nur Zahlen aus.

Der Szenenlauf wird über `szene.baue_nutzertext` und `szene.systemanweisung`
je Form gemessen, die Prosa über `kurzgeschichte.*`. Dabei ist
`IT_SZENE_TOKEN_MAX` weit gesetzt, damit der ungekürzte Rohbedarf sichtbar
wird.

`scripts/erzeuge_prompts.py` taugt dafür nicht. Es läuft gegen eine Kopie der
Test-DB, und die enthält Kopien echter Gruppen. Die Plan-Vorgabe „keine
Produktionsdaten“ schließt das aus.

**Aufruf (exakt so gelaufen):**

    python3.11 -m scripts.kalibriere_kontext
    python3.11 -m scripts.kalibriere_kontext --nur-system --profil dortmund-2026

**Datenlagen.** Beide liegen in einer Wegwerf-SQLite im Speicher:

- **Spätstand**: die geteilte Fixture `tests/fixture_spaetstand.py`. Das ist
  dieselbe Gruppe wie in `tests/test_prompt_audit.py` und
  `scripts/kontext_recall.py`:
  - Phase 6, vier Figuren, vier Szenen, ein gewuchertes Journal
  - 400 kurze Nachrichten zu je ~80 Zeichen, ein Interview
  - Sie ist *klein*: das Fenster trägt nur 1.597 Zeichen.
- **Vollast**: dieselbe Fixture, aufgefüllt bis an die Deckel, die der Code
  selbst setzt. Das ist der realistische schlechteste Fall, kein künstlicher
  Ausreißer:
  - **Fenster:** 30 frische Nachrichten (Mensch 200 Z., Bot 1.000 Z.), damit
    ist das Fenster voll. Vorbild ist die Messung vom 06.09.: 20 echte
    Nachrichten ergaben 6.454 Token ≈ 19.400 Zeichen
    (`docs/kontext-audit-2026-09-06.md`, C.3). Das Fenster füllt
    `FENSTER_ZEICHEN` im Spätstand also real.
  - **Festlegungen:** 20 Stück zu je ~110 Zeichen.
  - **Journal:** 12 weitere Einträge zu je ~180 Zeichen.
  - **Verdichtungen:** fünf Stück (eine je Interview), mit je acht Themen.
  - **Szenen:** Szene 1 hat 8.000+ Zeichen und liegt damit über
    `SZENE_ZEICHEN_MAX`. Die Szenen 2–7 haben je 5.349 Zeichen (die längste
    gemessene Szene). Szene 8 ist geplant.
  - **Figuren:** je fünf Zitate.
- **Vollast phasengerecht**: dieselbe Vollast-DB. Vor der Kürzung werden aber
  die Blöcke geleert, die im regulären Ablauf in dieser Phase keine Daten
  haben (`PHASENGERECHT` im Skript):
  - 1–2: kein Material, keine Szene
  - 3: dazu die Verdichtungen
  - 4: kein Material, dafür Festlegungen
  - 5–6: Kernpaket, aber noch kein Theatertext
  - 7: der Szenenblock
  - Die Kürzung selbst läuft unverändert. **Diese Tabelle ist die Grundlage
    für die Empfehlungen.** Die ungefilterte Vollast ist die Obergrenze, etwa
    für eine Gruppe, die mit fertigen Szenen nach Phase 3 zurückgeht.

**Weitere Einstellungen der Messung:**

- **Token:** geschätzt mit `kontext._ZEICHEN_JE_TOKEN` = 3, für den
  Szenenlauf mit `szene.SZENE_ZEICHEN_JE_TOKEN` = 1,9.
- **Bot:** `gruppe4`.
- **Profil:** das Vorgabeprofil. Mit `--profil dortmund-2026` sind alle sieben
  Systemgrößen zeichengleich (bitgleich, wie `tests/test_profil_bitgleich.py`
  zusichert). `workshop/padua-2026` ist ein Gerüst (`geruest = true`) und
  startet keinen Bot, deshalb wurde es nicht gemessen.

**Reserve** heißt immer: Budget − gemessen. Ein negativer Wert bedeutet, dass
die Grenze **schon heute** überschritten ist, also schneidet die Kürzung.

## 1. Systemanweisung je Phase

Gegen `SYSTEM_ZEICHEN_MAX` (Testdeckel) und den Platz, den `gesamtgrenze()`
dem Körper noch lässt:

| Phase | System (Z.) | ~Token ÷3 | SYSTEM_ZEICHEN_MAX | Reserve | Körperraum unter gesamtgrenze() (40.000) | Anteil an ZEICHEN_GRENZE (24.000) |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 26.085 | 8.695 | 36.000 | +9.915 | 13.915 | 58 % |
| 2 | 33.676 | 11.225 | 36.000 | **+2.324** | **6.324** | **26 %** |
| 3 | 27.598 | 9.199 | 36.000 | +8.402 | 12.402 | 52 % |
| 4 | 33.064 | 11.021 | 36.000 | **+2.936** | **6.936** | **29 %** |
| 5 | 26.883 | 8.961 | 36.000 | +9.117 | 13.117 | 55 % |
| 6 | 30.014 | 10.004 | 36.000 | +5.986 | 9.986 | 42 % |
| 7 | 29.389 | 9.796 | 36.000 | +6.611 | 10.611 | 44 % |

**Nicht mitgemessen: was zur Laufzeit noch angehängt wird.** Die
Profil-Anweisung (`workshop/<name>/prompts/anweisung.md`) und der
Regie-Zettel (`zusatz.md` und `zusatz.<bot>.md` neben `IT_DB`) hängen hinter
die Systemanweisung (`anweisungen.system`).

- Heute trägt **kein** Profil eine `anweisung.md`, sie tragen also 0 Zeichen
  bei.
- Den Regie-Zettel liest das Skript bewusst nicht, weil er ohne `IT_DB` nicht
  gesucht wird und Betriebsdaten sind.
- Jedes Zeichen darin geht **eins zu eins vom Körperraum ab**. In Phase 2
  bleiben heute 6.324 Zeichen. Ein Regie-Zettel von 2.000 Zeichen ließe dem
  Körper 4.324.
- `SYSTEM_ZEICHEN_MAX` sieht davon nichts: es ist ein Test gegen die
  Repo-Dateien, keine Laufzeitgrenze.

## 2. Gesprächs-Prompt, Fixture Spätstand

| Phase | Körper roh | Reserve Körper (24.000) | Gesamt roh (Sys+Körper) | Reserve gesamt (40.000) | Reserve ZIEL (Token) | Körper nach Kürzung | gekürzt | Fenster Einträge vor→nach (Min 6) | Fenster Zeichen vor→nach |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | 3.845 | +20.155 | 29.930 | +10.070 | +18.719 | 3.845 | nein | 20→20 | 1.597→1.597 |
| 2 | 3.855 | +20.145 | 37.531 | **+2.469** | +18.715 | 3.855 | nein | 20→20 | 1.597→1.597 |
| 3 | 3.555 | +20.445 | 31.153 | +8.847 | +18.815 | 3.555 | nein | 20→20 | 1.597→1.597 |
| 4 | 3.281 | +20.719 | 36.345 | +3.655 | +18.907 | 3.281 | nein | 20→20 | 1.597→1.597 |
| 5 | 4.515 | +19.485 | 31.398 | +8.602 | +18.495 | 4.515 | nein | 20→20 | 1.597→1.597 |
| 6 | 4.498 | +19.502 | 34.512 | +5.488 | +18.501 | 4.498 | nein | 20→20 | 1.597→1.597 |
| 7 | 4.459 | +19.541 | 33.848 | +6.152 | +18.514 | 4.459 | nein | 20→20 | 1.597→1.597 |

In der kleinen Fixture wird nirgends gekürzt, deshalb ist die Suite grün.
Phase 2 steht mit 1.597 Zeichen Fenster aber schon 2.469 Zeichen vor der
Gesamtgrenze.

## 3. Gesprächs-Prompt, Vollast phasengerecht (Grundlage der Empfehlungen)

| Phase | Körper roh | Reserve Körper (24.000) | Gesamt roh (Sys+Körper) | Reserve gesamt (40.000) | Reserve ZIEL (Token) | Körper nach Kürzung | gekürzt | Fenster Einträge vor→nach (Min 6) | Fenster Zeichen vor→nach | aus dem Fenster gekürzt, davon im Extraktor-Abschnitt |
|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| 1 | 13.844 | +10.156 | 39.929 | +71 | +15.386 | 13.844 | nein | 19→19 | 11.912→11.912 | – |
| 2 | 13.865 | +10.135 | 47.541 | **−7.541** | +15.379 | 5.588 | ja | 19→6 | 11.912→3.635 | 13 Eintr. / 8.277 Z. (~2.758 Tok.), 1 |
| 3 | 20.126 | +3.874 | 47.724 | **−7.724** | +13.292 | 11.849 | ja | 19→6 | 11.912→3.635 | 13 Eintr. / 8.277 Z. (~2.758 Tok.), 1 |
| 4 | 16.252 | +7.748 | 49.316 | **−9.316** | +14.583 | 6.763 | ja | 19→**4** | 11.912→2.423 | 15 Eintr. / 9.489 Z. (~3.162 Tok.), 1 |
| 5 | 17.578 | +6.422 | 44.461 | **−4.461** | +14.141 | 12.937 | ja | 19→12 | 11.912→7.271 | 7 Eintr. / 4.641 Z. (~1.546 Tok.), 1 |
| 6 | 17.589 | +6.411 | 47.603 | **−7.603** | +14.137 | 9.312 | ja | 19→6 | 11.912→3.635 | 13 Eintr. / 8.277 Z. (~2.758 Tok.), 1 |
| 7 | 23.623 | **+377** | 53.012 | **−13.012** | +12.126 | 10.138 | ja | 19→**4** | 11.912→2.423 | 15 Eintr. / 9.489 Z. (~3.162 Tok.), 1 |

**Befund:**

- **In sechs von sieben Phasen schneidet allein die Gesamtgrenze.** Die
  Körpergrenze hätte in keiner Phase gegriffen. Der Körper allein liegt
  überall unter 24.000.
- Die Gesamtgrenze kürzt das Fenster auf 4–12 Einträge. In den Phasen 4
  und 7 bleiben 4 Einträge und damit **weniger als
  `FENSTER_MIN_NACHRICHTEN` = 6**.
- **Die Kürzung kennt die Untergrenze nicht.** Sie steht nur in
  `waehle_fenster`. `_kuerze_auf_budget` beschneidet das Fenster bis auf
  null, bevor Journal, Festlegungen und Verdichtungen drankommen.
- **Was die Kürzung aus dem Fenster nimmt, journalisiert niemand.** Der
  Journal-Extraktor rechnet „verdrängt“ gegen `waehle_fenster`, also gegen
  das *ungekürzte* Fenster. Von 7–15 gekürzten Einträgen liegt je **genau
  einer** in seinem Abschnitt. Dieser eine ist die Randnachricht, weil der
  Extraktor den Auslöser mitzählt. Der Rest steht danach weder im Prompt
  noch im Journal: gemessen 1.546 bis 3.162 Token Gesprächsverlauf je Zug.
  Das liegt klar über `journal.SCHWELLE_VERDRAENGUNG` = 600 Token, also über
  der Menge, die der Extraktor für journalwürdig hält.

**Was eine Grenze bräuchte, damit phasengerecht nicht gekürzt wird:**
System + Körper roh, maximal **53.012 Zeichen (Phase 7)**. Das sind ≈ 17.700
Token ÷3, weit unter Kimis Fenster.

## 4. Gesprächs-Prompt, Vollast mit allen Blöcken in jeder Phase (Obergrenze)

| Phase | Körper roh | Reserve Körper (24.000) | Gesamt roh | Reserve gesamt (40.000) | Reserve ZIEL (Token) | Körper nach Kürzung | gekürzt | Fenster vor→nach | Fenster Zeichen vor→nach |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | 29.731 | −5.731 | 55.816 | −15.816 | +10.090 | 13.821 | ja | 19→**0** | 11.912→0 |
| 2 | 29.588 | −5.588 | 63.264 | −23.264 | +10.138 | 3.508 | ja | 19→**0** | 11.912→0 |
| 3 | 29.151 | −5.151 | 56.749 | −16.749 | +10.283 | 12.256 | ja | 19→**0** | 11.912→0 |
| 4 | 22.764 | +1.236 | 55.828 | −15.828 | +12.412 | 6.854 | ja | 19→**0** | 11.912→0 |
| 5 | 23.930 | +70 | 50.813 | −10.813 | +12.024 | 12.869 | ja | 19→8 | 11.912→4.847 |
| 6 | 23.792 | +208 | 53.806 | −13.806 | +12.070 | 9.095 | ja | 19→2 | 11.912→1.211 |
| 7 | 23.623 | +377 | 53.012 | −13.012 | +12.126 | 10.138 | ja | 19→4 | 11.912→2.423 |

Hier ist die Leiter vollständig zu sehen. In den Phasen 1–4 fällt das
Fenster **ganz** weg. In Phase 2 bleiben vom Körper 3.508 Zeichen:
Verdichtungen, Journal und Festlegungen sind geopfert. Nur hier (Phasen 1–3,
Material **und** Szene gleichzeitig) reißt auch die Körpergrenze
(29.731 > 24.000).

## 5. Blöcke gegen `BUDGETS` (Vollast, größter Rohwert über alle Phasen)

| Block | BUDGETS (Token) | ~Zeichen (×3) | max. roh gemessen (Z.) | in Phase | Reserve (Z.) | durchgesetzt von |
|---|---:|---:|---:|---|---:|---|
| system | 9.000 | 27.000 | 33.676 | 2 | **−6.676** | `SYSTEM_ZEICHEN_MAX` (Test) / `gesamtgrenze()` |
| verdichtungen | 3.000 | 9.000 | 6.536 | 1 | +2.464 | nur Kürzungsleiter |
| transkripte | 5.000 | 15.000 | 0 | – | +15.000 | nur Kürzungsleiter (Wortlaut-Schalter aus) |
| kernpaket | 2.000 | 6.000 | 1.668 | 5 | +4.332 | nur Kürzungsleiter |
| arbeitsstand | 1.200 | 3.600 | 985 | 4 | +2.615 | nur Kürzungsleiter |
| festlegungen | 800 | 2.400 | 2.370 | 1 | +30 | `_baue_festlegungen` (20 Zeilen + Budget) — der Deckel greift |
| phasenhinweis | 50 | 150 | 279 | 2 | −129 | nur Kürzungsleiter |
| figurenhinweis | 100 | 300 | 586 | 5 | −286 | nur Kürzungsleiter |
| szene | 2.000 | 6.000 | 6.042 | 1 | −42 | `SZENE_ZEICHEN_MAX` = 6.000 (+ Kopfzeile) — der Deckel greift |
| journal | 1.500 | 4.500 | 1.422 | 1 | +3.078 | `JOURNAL_EINTRAEGE` = 8 Zeilen |
| fenster | 8.000 | 24.000 | 11.912 | 1 | +12.088 | `FENSTER_ZEICHEN` = 12.000 (Budget historisch) |
| ausloeser | 300 | 900 | 215 | 1 | +685 | nur Kürzungsleiter |

Die negativen Werte bei `phasenhinweis`, `figurenhinweis` und `szene` sind
dokumentarisch (Kopfzeile bzw. fester Hinweistext) und werden nirgends
durchgesetzt. `system` = 9.000 ist der Wert vom 06.09. und liegt heute
2.225 Token unter dem Maximum.

Nicht belegt: `REISSLEINE` = 40.000 Token wird von keinem Codepfad gelesen.
`ZIEL` = 20.000 Token (= 60.000 Zeichen) bindet nie vor der Körpergrenze
(24.000 Zeichen ≈ 8.000 Token). Seine Reserve liegt in jeder Messung über
+10.000 Token.

## 6. Szenenlauf (`szene.py`)

Die Budgets:

- **Claude:** `SZENE_TOKEN_MAX_CLAUDE` = (200.000 − 32.000) × 0,75 = 126.000.
- **Infomaniak:** `SZENE_TOKEN_MAX_INFOMANIAK` = (249.984 − 200.000) × 0,75
  = 37.488.

Beide prüft `baue_nutzertext` **nur gegen den Nutzertext**. Der
Eingaberaum des Anbieters muss aber System **und** Nutzer fassen:

- **Claude:** 200.000 − `szene_claude.MAX_TOKENS` 32.000 = 168.000.
- **Infomaniak:** 249.984 − `szene.MAX_TOKENS` 200.000 = 49.984.

**Fixture Spätstand** (Ziel Szene 4, ungekürzt):

| Form | System (Z.) | Nutzer (Z.) | Nutzer Tok. ÷1,9 | System+Nutzer Tok. | Reserve Budget Claude (nur Nutzer) | Reserve Budget Infomaniak (nur Nutzer) | Reserve Eingaberaum Claude (Sys+Nutzer) | Reserve Eingaberaum Infomaniak (Sys+Nutzer) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dialog | 31.557 | 4.502 | 2.369 | 18.978 | +123.631 | +35.119 | +149.022 | +31.006 |
| monolog | 24.709 | 4.502 | 2.369 | 15.374 | +123.631 | +35.119 | +152.626 | +34.610 |
| chor | 25.997 | 4.502 | 2.369 | 16.052 | +123.631 | +35.119 | +151.948 | +33.932 |
| lied | 25.869 | 4.502 | 2.369 | 15.984 | +123.631 | +35.119 | +152.016 | +34.000 |
| rap | 25.836 | 4.502 | 2.369 | 15.967 | +123.631 | +35.119 | +152.033 | +34.017 |
| prosa (Phase 6) | 12.785 | 726 | 382 | 7.111 | +125.618 | +37.106 | +160.889 | +42.873 |

**Vollast** (Ziel Szene 8, sieben Vorszenen im Volltext, ungekürzt):

| Form | System (Z.) | Nutzer (Z.) | Nutzer Tok. ÷1,9 | System+Nutzer Tok. | Reserve Budget Claude (nur Nutzer) | Reserve Budget Infomaniak (nur Nutzer) | Reserve Eingaberaum Claude (Sys+Nutzer) | Reserve Eingaberaum Infomaniak (Sys+Nutzer) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dialog | 31.557 | 54.188 | 28.520 | 45.128 | +97.480 | +8.968 | +122.872 | **+4.856** |
| monolog | 24.709 | 54.188 | 28.520 | 41.524 | +97.480 | +8.968 | +126.476 | +8.460 |
| chor | 25.997 | 54.188 | 28.520 | 42.202 | +97.480 | +8.968 | +125.798 | +7.782 |
| lied | 25.869 | 54.188 | 28.520 | 42.135 | +97.480 | +8.968 | +125.865 | +7.849 |
| rap | 25.836 | 54.188 | 28.520 | 42.117 | +97.480 | +8.968 | +125.883 | +7.867 |
| prosa (Phase 6) | 12.785 | 1.121 | 590 | 7.318 | +125.410 | +36.898 | +160.682 | +42.666 |

**Befund Infomaniak:**

- Die Dialog-Systemanweisung allein sind 31.557 Z. ≈ **16.609 Token**. Der
  Sicherheitsabschlag von 25 % auf 49.984 sind nur 12.496 Token. Er soll
  laut Kommentar an `BUDGET_RESERVE` „die Systemanweisung“ auffangen und
  kann das nicht mehr.
- Ein Nutzertext genau am Budget (37.488) plus die Dialog-Anweisung ergibt
  54.097 Token. Das liegt **4.113 Token über** dem Eingaberaum
  (`max_total_tokens`), und die API antwortet mit HTTP 400 (Falle 4).
  Die Kürzungsleiter des Szenenlaufs springt in diesem Fall gar nicht erst
  an.
- Schon die Vollast ohne Kürzung hat nur noch 4.856 Token (≈ 10 %) Luft.
- Die Prosa (Phase 6) ist klein und unkritisch.
- Claude hat in allen Fällen reichlich Reserve.

`SZENE_ZEICHEN_JE_TOKEN` = 1,9 wurde nicht neu gemessen, das ginge nur mit
`count_tokens` über das Netz. Die Rechnung übernimmt den Wert vom 06.09.

## Wo die Reserve knapp ist (Kurzfassung)

1. **`gesamtgrenze()` = 40.000** ist die einzige Grenze, die heute
   realistisch schneidet: in 6 von 7 Phasen, um 4.461 bis 13.012 Zeichen.
   Dabei drückt sie das Fenster unter `FENSTER_MIN_NACHRICHTEN` und erzeugt
   einen Verlust, den der Journal-Extraktor nicht sieht.
2. **`SYSTEM_ZEICHEN_MAX` = 36.000**: Phase 2 hat noch +2.324, Phase 4
   +2.936.
3. **`SZENE_TOKEN_MAX_INFOMANIAK` = 37.488**: am Budget liegt die Summe
   rechnerisch über dem Eingaberaum (−4.113 Token mit Dialog-Anweisung).
4. **`ZEICHEN_GRENZE_VORGABE` = 24.000**: phasengerecht nur in Phase 7 knapp
   (+377), sonst ≥ +3.874.

## Folgerungen für Task 3 (je Grenze mit dem Messwert, der sie trägt)

**Ändern:**

- **`GESAMT_ZEICHEN_GRENZE_VORGABE` 40.000 → 60.000**
  (= `SYSTEM_ZEICHEN_MAX` + `ZEICHEN_GRENZE_VORGABE`).
  - Grund: der phasengerechte Höchstbedarf ist 53.012 (Phase 7). 60.000
    lassen davon +6.988 Reserve. Schon heute fehlen bis zu 13.012.
  - Mit dieser Herleitung greift die Gesamtgrenze erst, wenn die Anweisung
    über ihren Testdeckel hinaus wächst, etwa durch Regie-Zettel oder
    Profil-Anweisung zur Laufzeit. Das ist der Fall, für den sie gebaut
    wurde (Befund C.1).
- **Szenenlauf Infomaniak: System in die Budgetprüfung aufnehmen**, oder
  gleichwertig das Nutzerbudget um die Systemanweisung senken. Für Dialog
  wären das 37.488 − 16.609 = 20.879 Token.
  - Grund: ein Nutzertext am heutigen Budget ergibt mit Dialog-Anweisung
    54.097 > 49.984 Token.

**Dokumentarisch nachziehen:**

- `BUDGETS["system"]` 9.000 → auf den gemessenen Höchstwert 11.225 Token
  (Phase 2).
- `phasenhinweis`/`figurenhinweis`: gemessen 93 bzw. 195 Token.

**Keine Konstante, aber derselbe Befund:** `_kuerze_auf_budget` kürzt das
Fenster unter `FENSTER_MIN_NACHRICHTEN` (bis auf 0), und der Verlust ist für
den Journal-Extraktor unsichtbar. Mit 60.000 tritt das phasengerecht nicht
mehr auf. In der Obergrenzen-Vollast (Abschnitt 4) bleibt es ein Verhalten
der Leiter.

**Bleiben (genug Reserve oder der Deckel wirkt wie gewollt):**

| Konstante | Wert | Messwert | Reserve |
|---|---:|---:|---:|
| `ZEICHEN_GRENZE_VORGABE` | 24.000 | 23.623 (phasengerecht, max.) | +377 |
| `SYSTEM_ZEICHEN_MAX` | 36.000 | 33.676 (Phase 2) | +2.324 |
| `FENSTER_ZEICHEN` | 12.000 | 11.912 | voll, wie gewollt |
| `FENSTER_NACHRICHTEN` | 20 | – | – |
| `FENSTER_MIN_NACHRICHTEN` | 6 | – | – |
| `SZENE_ZEICHEN_MAX` | 6.000 | Szenenblock 6.042 mit Kopfzeile | Deckel greift |
| `SZENE_ZEICHEN_NOTFALL` | 2.000 | – | – |
| `BUDGETS["festlegungen"]` | 800 | 2.370 von 2.400 Zeichen | Deckel greift |
| `JOURNAL_EINTRAEGE` | 8 | 1.422 Zeichen | – |
| `journal.SCHWELLE_VERDRAENGUNG` | 600 | – | – |
| `SZENE_TOKEN_MAX_CLAUDE` | 126.000 | max. 28.520 | +97.480 |
| `SZENE_ZEICHEN_JE_TOKEN` | 1,9 | offline nicht nachmessbar | – |

`ZIEL` (20.000 Token) bindet nie vor der Körpergrenze, `REISSLEINE` wird
nicht gelesen. Beide sind unschädlich und kein Kalibrierungsgegenstand.
