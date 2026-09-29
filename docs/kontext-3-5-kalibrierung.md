# Kalibrierung der Kontextgrenzen gegen die heutigen Prompts

Stand 30.09.2026, Padua K (Task 2), nach dem Merge von `feat/kontext-3-5`
(`daed9aa`). Gemessen wird, **wie viel Platz die Prompts heute brauchen**, und
das gegen jede Budget- und Grenzkonstante aus `interview_theater/kontext.py`
und `interview_theater/szene.py`. Die Abschnitte 1–6 sind die Messung
**vor** jeder Änderung (Stand `ce16518`, Gesamtgrenze 40.000, Szenenbudget
nur gegen den Nutzertext). Was Task 3 daraufhin geändert hat und wie die
Reserven danach nachgemessen aussehen, steht am Ende unter
[„Anpassungen (Task 3)“](#anpassungen-task-3).

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

**`transkripte` ist der einzige Block, der in der Vollast nicht bis an
seinen Deckel gefüllt ist** (0 statt bis zu 15.000 Z.): der
Wortlaut-Schalter (`/wortlaut`, `gruppe.wortlaut_modus`) steht in beiden
Fixturen (Spätstand wie Vollast) auf aus, also liefert `_baue_transkripte`
nichts, egal wie viel Interviewmaterial da wäre. Das ist hier bewusst NICHT
nachgezogen: `_kuerze_auf_budget` schneidet Volltranskripte laut eigenem
Docstring als **ersten** Schritt der Kürzungsleiter („der größte einzelne
Brocken"), noch vor Journal, Festlegungen und Verdichtungen. Ein voll
gefüllter `transkripte`-Block würde also nur zeigen, was ohnehin als
Erstes wieder verschwindet — eine ungenutzte Reserve an der Stelle, die am
wenigsten schützenswert ist, ändert an den knappen Stellen (`system`,
Infomaniak-Szenenbudget, Gesamtgrenze) nichts.

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

**Die Systemanweisung hängt seit dem Stil-Umbau (06.09.2026) auch vom Stil
ab** (`szene.systemanweisung(form, stil)`, `stile.py`): ein Stilblock hängt
bis zu 5.484 Zeichen an (`stile.regelblock("schlagabtausch")`, nach Abzug
des Kopfkommentars der Prompt-Datei; `litanei` 5.038, `herkules` 375). Die
Gruppe wählt den Stil frei — unabhängig vom Vorschlag
(`stile.VORSCHLAG`, der für `dialog` z. B. `herkules` nahelegt, das kleinste
der drei Stilblätter). Gemessen wird deshalb je Form das **größte** System
über alle Stile (inklusive `stil=None`, kein Stil gewählt), aus der echten
Liste `stile.STILE`: das ist der Wert, der im Betrieb tatsächlich vorkommen
kann, nicht nur der vorgeschlagene. Bei `prosa` wirkt kein Stil
(`systemanweisung` hängt ihn nur bei `form != prosa` an), die Prosa-Zeile
bleibt deshalb unverändert.

**Fixture Spätstand** (Ziel Szene 4, ungekürzt, je Form das größte System
über alle Stile):

| Form | Stil (größtes System) | System (Z.) | Nutzer (Z.) | Nutzer Tok. ÷1,9 | System+Nutzer Tok. | Reserve Budget Claude (nur Nutzer) | Reserve Budget Infomaniak (nur Nutzer) | Reserve Eingaberaum Claude (Sys+Nutzer) | Reserve Eingaberaum Infomaniak (Sys+Nutzer) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dialog | schlagabtausch | 37.043 | 4.502 | 2.369 | 21.865 | +123.631 | +35.119 | +146.135 | +28.119 |
| monolog | schlagabtausch | 30.195 | 4.502 | 2.369 | 18.261 | +123.631 | +35.119 | +149.739 | +31.723 |
| chor | schlagabtausch | 31.483 | 4.502 | 2.369 | 18.939 | +123.631 | +35.119 | +149.061 | +31.045 |
| lied | schlagabtausch | 31.355 | 4.502 | 2.369 | 18.872 | +123.631 | +35.119 | +149.128 | +31.112 |
| rap | schlagabtausch | 31.322 | 4.502 | 2.369 | 18.854 | +123.631 | +35.119 | +149.146 | +31.130 |
| prosa (Phase 6) | – | 12.785 | 726 | 382 | 7.111 | +125.618 | +37.106 | +160.889 | +42.873 |

**Vollast** (Ziel Szene 8, sieben Vorszenen im Volltext, ungekürzt, je Form
das größte System über alle Stile):

| Form | Stil (größtes System) | System (Z.) | Nutzer (Z.) | Nutzer Tok. ÷1,9 | System+Nutzer Tok. | Reserve Budget Claude (nur Nutzer) | Reserve Budget Infomaniak (nur Nutzer) | Reserve Eingaberaum Claude (Sys+Nutzer) | Reserve Eingaberaum Infomaniak (Sys+Nutzer) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dialog | schlagabtausch | 37.043 | 54.188 | 28.520 | 48.016 | +97.480 | +8.968 | +119.984 | **+1.968** |
| monolog | schlagabtausch | 30.195 | 54.188 | 28.520 | 44.412 | +97.480 | +8.968 | +123.588 | +5.572 |
| chor | schlagabtausch | 31.483 | 54.188 | 28.520 | 45.090 | +97.480 | +8.968 | +122.910 | +4.894 |
| lied | schlagabtausch | 31.355 | 54.188 | 28.520 | 45.022 | +97.480 | +8.968 | +122.978 | +4.962 |
| rap | schlagabtausch | 31.322 | 54.188 | 28.520 | 45.005 | +97.480 | +8.968 | +122.995 | +4.979 |
| prosa (Phase 6) | – | 12.785 | 1.121 | 590 | 7.318 | +125.410 | +36.898 | +160.682 | +42.666 |

**Der größte Szenen-Systemprompt insgesamt ist `(dialog, schlagabtausch)`
mit 37.043 Zeichen** — nicht `dialog` allein (31.557 Z., der Wert vom
06.09. ohne Stil) und nicht der vorgeschlagene Stil für Dialog
(`herkules`, nur 375 Z. zusätzlich). Diese Kombination trägt jede folgende
Rechnung in diesem Abschnitt.

**Befund Infomaniak:**

- Die größte Szenen-Systemanweisung (`dialog` + `schlagabtausch`) sind
  37.043 Z. ≈ **19.496 Token** (`int(37043 / 1,9)`). Der Sicherheitsabschlag
  von 25 % auf 49.984 sind nur 12.496 Token. Er soll laut Kommentar an
  `BUDGET_RESERVE` „die Systemanweisung“ auffangen und deckt damit nicht
  einmal zwei Drittel dieses Werts.
- Ein Nutzertext genau am Budget (37.488) plus diese Systemanweisung ergibt
  56.984 Token. Das liegt **7.000 Token über** dem Eingaberaum
  (`max_total_tokens` = 49.984), und die API antwortet mit HTTP 400
  (Falle 4). Die Kürzungsleiter des Szenenlaufs springt in diesem Fall gar
  nicht erst an.
- Schon die Vollast ohne Kürzung hat mit dieser Kombination nur noch 1.968
  Token (≈ 4 %) Luft im Eingaberaum — knapper als die 4.856 Token (≈ 10 %),
  die ohne Stil sichtbar waren.
- Die Prosa (Phase 6) ist klein und unkritisch, weil ihr `systemanweisung`
  nie einen Stilblock anhängt.
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
   rechnerisch über dem Eingaberaum (−7.000 Token mit der größten
   Systemanweisung, `dialog` + Stil `schlagabtausch`).
4. **`ZEICHEN_GRENZE_VORGABE` = 24.000**: phasengerecht nur in Phase 7 knapp
   (+377), sonst ≥ +3.874. Sie bleibt trotz der knappen Phase-7-Reserve
   unangetastet, weil sie eine **weiche** Kürzungsgrenze ist: schneidet sie,
   trimmt die Kürzungsleiter Verlauf, Journal und Festlegungen schrittweise
   (`_kuerze_auf_budget`) — das Gespräch geht weiter, nur mit weniger
   Material im Prompt. Anders als beim Infomaniak-Szenenbudget oben, wo ein
   Überschreiten HTTP 400 auslöst, ist ein knappes `ZEICHEN_GRENZE_VORGABE`
   also kein Ausfall, sondern der Normalfall, für den die Leiter gebaut ist.

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
  gleichwertig das Nutzerbudget um die größte Systemanweisung senken —
  gemessen über alle (Form, Stil)-Paare, nicht nur `dialog` ohne Stil, denn
  die Gruppe wählt Form und Stil unabhängig voneinander. Das Maximum ist
  `(dialog, schlagabtausch)` mit 37.043 Z. ≈ 19.496 Token; damit wären das
  37.488 − 19.496 ≈ **17.992 Token**.
  - Grund: ein Nutzertext am heutigen Budget ergibt mit dieser
    Systemanweisung 56.984 > 49.984 Token.

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
| `ZEICHEN_GRENZE_VORGABE` | 24.000 | 23.623 (phasengerecht, max.) | +377, weiche Kürzungsgrenze (s. o.) |
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

## Anpassungen (Task 3)

Stand 30.09.2026, Padua K (Task 3). Zwei Grenzen geändert, je ein eigener
Commit mit dem Messwert in der Botschaft. Danach neu gemessen mit
demselben Aufruf wie oben (`python3.11 -m scripts.kalibriere_kontext`).
Das Skript hat dafür zwei Änderungen bekommen: die Spaltenköpfe lesen die
geltenden Grenzen statt „(24.000)“/„(40.000)“ fest zu drucken, und die
Szenentabelle zeigt zusätzlich den Nutzertext so, wie der Lauf ihn unter dem
Infomaniak-Budget **mit** Abzug der Systemanweisung baut.

### Geändert

| Grenze | alt → neu | Messwert, der es verlangt hat | Reserve danach (nachgemessen) |
|---|---|---|---|
| `kontext.GESAMT_ZEICHEN_GRENZE_VORGABE` (`gesamtgrenze()`, Env `IT_PROMPT_ZEICHEN_GESAMT`) | 40.000 → **60.000** Zeichen | System + Körper roh, Vollast phasengerecht, bis **53.012** (Phase 7); 40.000 schnitt in 6 von 7 Phasen um 4.461–13.012 und drückte das Fenster in Phase 4 und 7 auf 4 Einträge (< `FENSTER_MIN_NACHRICHTEN` 6) | phasengerecht **+6.988** (Phase 7, 13 %) bis +20.329; **in keiner Phase gekürzt**, Fenster überall 19→19 |
| Szenenlauf: Budgetprüfung des Nutzertexts (`szene.nutzer_budget`, neu) | Nutzertext allein gegen `token_budget()` → **System + Nutzertext** gegen `token_budget()`; der Nutzertext bekommt `token_budget − schaetze_token(systemanweisung(form, stil))` | größte Szenen-Systemanweisung `(dialog, schlagabtausch)` **37.043 Z. ≈ 19.496 Token**; Nutzertext am Infomaniak-Budget 37.488 + diese Anweisung = 56.984 Token > Raum 49.984 → HTTP 400 | Vollast Szene 8, Infomaniak: Nutzertext 54.188 → 33.118 Z. gekürzt (Stufe 1, Vorszenen 1–3 als Zusammenfassung), System + Nutzer **36.926 Token** ≤ 37.488, Reserve zum Eingaberaum **+13.058** (vorher ungekürzt +1.968, am Budget −7.000) |

**Zur Gesamtgrenze.** 60.000 ist nicht „knapp über dem letzten Lauf“,
sondern strukturell hergeleitet: `SYSTEM_ZEICHEN_MAX` (36.000) +
`ZEICHEN_GRENZE_VORGABE` (24.000). Solange beide Teilgrenzen halten, kann die
Gesamtgrenze nicht reißen; sie greift erst, wenn die Anweisung zur Laufzeit
über ihren Testdeckel wächst (Regie-Zettel, Profil-`anweisung.md`) — der
Fall aus Befund C.1, für den sie gebaut ist. Der Wert steht als Zahl im
Code; `test_prompt_audit.py::test_gesamtgrenze_ist_system_plus_koerper` hält
die Herleitung fest, damit ein angehobener `SYSTEM_ZEICHEN_MAX` die
Gesamtgrenze nicht still mitzieht. SPEC § 6.2/§ 7 nachgezogen.

**Zum Szenenbudget.** Gewählt wurde die Rechnung mit der **tatsächlichen**
Anweisung des Laufs statt einer neuen Konstante (37.488 − 19.496 = 17.992):
die Konstante veraltete mit dem nächsten wachsenden Stilblatt, die Rechnung
schiebt sich mit. Der Eingriff sitzt an einer Stelle: `schreibe()` baut die
Anweisung jetzt **vor** dem Nutzertext und gibt sie an
`baue_nutzertext(…, system=…)`, die Kürzungsleiter kürzt gegen den
verkleinerten Raum (unverändert in ihrer Reihenfolge), und der Vorfall
`szene_prompt_gekuerzt` nennt den Abzug. Folgen:

- `token_budget()` und `IT_SZENE_TOKEN_MAX` meinen jetzt die **ganze
  Eingabe inklusive Systemanweisung**. Das ist dieselbe Größe, die
  `_pruefe_budget` nach dem Lauf ohnehin mit den echten Eingabe-Token des
  Anbieters vergleicht — Schätzung und Messung bemessen jetzt dasselbe.
  Dokumentiert im Docstring, in `AGENTS.md` und in
  `docs/betrieb-env.beispiel`.
- **Claude-Pfad:** dieselbe Lücke (die 126.000 = (200.000 − 32.000) × 0,75
  zogen die Anweisung ebenfalls nicht ab), dieselbe Rechnung greift, weil
  der Code für beide Pfade derselbe ist. Folgenlos in der Messung: Vollast
  System + Nutzer 48.016 Token, Reserve zum Budget **+77.984**, keine Kürzung.
- `stueckpruefung.pruefe` misst aus demselben Grund `system + nutzer` gegen
  `token_budget()` (ihre Anweisung hat nur 2.435 Zeichen, also praktisch
  folgenlos, aber sonst bemäße dieselbe Zahl an zwei Stellen zwei
  verschiedene Dinge).
- Aufrufer ohne `system` (Skripte, ältere Tests) bekommen das alte Verhalten
  (kein Abzug).
- Tests: `test_systemanweisung_geht_vom_budget_des_nutzertexts_ab` (eine
  große Anweisung verkleinert den Raum so, dass System + Nutzer ≤ Budget
  bleibt, wo es ohne Abzug gerissen wäre),
  `test_nutzer_budget_zieht_die_systemanweisung_ab`,
  `test_schreibe_gibt_die_systemanweisung_ins_budget`.

### Nachmessung Gesprächs-Prompt (Gesamtgrenze 60.000)

Vollast phasengerecht:

| Phase | Körper roh | Gesamt roh | Reserve gesamt (60.000) | gekürzt | Fenster vor→nach |
|---|---:|---:|---:|---|---|
| 1 | 13.586 | 39.671 | +20.329 | nein | 19→19 |
| 2 | 13.584 | 47.260 | +12.740 | nein | 19→19 |
| 3 | 20.126 | 47.724 | +12.276 | nein | 19→19 |
| 4 | 15.979 | 49.043 | +10.957 | nein | 19→19 |
| 5 | 17.578 | 44.461 | +15.539 | nein | 19→19 |
| 6 | 17.589 | 47.603 | +12.397 | nein | 19→19 |
| 7 | 23.623 | 53.012 | **+6.988** | nein | 19→19 |

Vollast mit allen Blöcken in jeder Phase (Obergrenze):

| Phase | Körper roh | Gesamt roh | Reserve gesamt (60.000) | Reserve Körper (24.000) | gekürzt | Fenster vor→nach | aus dem Fenster gekürzt / davon im Extraktor-Abschnitt |
|---|---:|---:|---:|---:|---|---|---|
| 1 | 29.731 | 55.816 | +4.184 | −5.731 | ja | 19→16 | 3 Eintr. / 2.217 Z. (~738 Tok.) / 1 |
| 2 | 29.588 | 63.264 | −3.264 | −5.588 | ja | 19→16 | 3 Eintr. / 2.217 Z. (~738 Tok.) / 1 |
| 3 | 29.151 | 56.749 | +3.251 | −5.151 | ja | 19→17 | 2 Eintr. / 1.212 Z. (~403 Tok.) / 1 |
| 4 | 22.491 | 55.555 | +4.445 | +1.509 | nein | 19→19 | – |
| 5 | 23.930 | 50.813 | +9.187 | +70 | nein | 19→19 | – |
| 6 | 23.792 | 53.806 | +6.194 | +208 | nein | 19→19 | – |
| 7 | 23.623 | 53.012 | +6.988 | +377 | nein | 19→19 | – |

In den Phasen 1–3 schneidet jetzt die **Körpergrenze** (Material und
Szenentext gleichzeitig, siehe Abschnitt 4), in Phase 2 zusätzlich die
Gesamtgrenze (−3.264, weil dort die größte Anweisung, 33.676, auf den
größten Körper trifft). Vorher fiel das Fenster in diesen Phasen auf 0.

**Messrauschen, keine Folge der Änderung:** in den Phasen 1, 2 und 4 liegt
„Körper roh“ um 258–273 Zeichen unter den Werten aus Abschnitt 3/4. Das ist
genau der Phasenhinweis (256/279/271 Z.): ob er im Prompt steht, entscheidet
`phasen.offenes_angebot` über `repo.neues_material_seit(phase_gesetzt_am)`,
und in der Fixture fallen Phasenwechsel und Materialzeitstempel in dieselbe
Sekunde. Mit derselben Fixture in einem getrennten Lauf gegen 40.000 und
60.000 gemessen sind die Rohwerte zeichengleich (13.844 in Phase 1 beide
Male). Die Grenzänderung ändert Rohbedarf nicht, nur die Kürzung.

### Nachmessung Szenenlauf (System zählt mit)

Vollast (Ziel Szene 8, sieben Vorszenen), je Form das größte System über
alle Stile, Lauf so gebaut wie im Betrieb (Infomaniak, `system=` übergeben):

| Form | System Tok. | Nutzer Z. ungekürzt → im Lauf | System + Nutzer Tok. im Lauf | Reserve Budget 37.488 | Reserve Eingaberaum 49.984 |
|---|---:|---|---:|---:|---:|
| dialog (schlagabtausch) | 19.496 | 54.188 → 33.118 | 36.926 | +562 | +13.058 |
| monolog (schlagabtausch) | 15.892 | 54.188 → 38.150 | 35.970 | +1.518 | +14.014 |
| chor (schlagabtausch) | 16.570 | 54.188 → 38.150 | 36.648 | +840 | +13.336 |
| lied (schlagabtausch) | 16.502 | 54.188 → 38.150 | 36.580 | +908 | +13.404 |
| rap (schlagabtausch) | 16.485 | 54.188 → 38.150 | 36.563 | +925 | +13.421 |
| prosa (Phase 6) | 6.728 | 1.121 (eigener Weg, `kurzgeschichte`) | 7.318 | +30.170 | +42.666 |

Die Reserve zum Budget ist klein, weil die Leiter bis ans Budget auffüllt
(so gebaut); die Reserve, die vor HTTP 400 schützt, ist die zum
Eingaberaum: **+13.058 Token im schlechtesten Fall**, das ist der
unangetastete 25-%-Abschlag (12.496) plus die 562 Token, die die Leiter
unter dem Budget übrig lässt. Kürzung in
Stufe 1 (Vorszenen als Zusammenfassung: 1–3 bei Dialog, 1–2 sonst); die
jüngsten Vorszenen bleiben im Volltext.

### Unverändert (je ein Satz Begründung)

| Konstante | Wert | Warum nicht geändert |
|---|---:|---|
| `SYSTEM_ZEICHEN_MAX` | 36.000 | Kein Laufzeit-Limit, sondern ein Stolperdraht gegen Promptwachstum (Test je Phase): gemessen 33.676 (Phase 2, +2.324); ein Test, der rot wird, wenn `system.md`/`phasen/*.md` weiterwachsen, ist das gewollte Signal — ihn vorsorglich anzuheben hieße, das Signal abzuschalten. War in dieser Kalibrierung selbst keine Änderung: 30.000 → 36.000 geschah bereits im Merge `daed9aa`, ausgelöst durch dieselbe gemessene Systemanweisung (33.676 Zeichen, Phase 2); in Task 3 bewusst nicht weiter angehoben (Stolperdraht). |
| `ZEICHEN_GRENZE_VORGABE` | 24.000 | Weiche Kürzungsgrenze: phasengerecht max. 23.623 (+377) schneidet nicht; reißt sie, trimmt die Leiter und das Gespräch läuft weiter — kein Ausfall wie beim Szenenbudget. |
| `SZENE_TOKEN_MAX_INFOMANIAK` / `_CLAUDE` | 37.488 / 126.000 | Die Konstanten sind richtig hergeleitet (Raum × 0,75); falsch war, wogegen gemessen wurde — das behebt `nutzer_budget`. |
| `BUDGET_RESERVE` | 0,75 | Bleibt der Abschlag für Tokenisierungsschwankung und Formatierung; seine frühere Zusatzaufgabe (Systemanweisung) ist jetzt explizit abgezogen, er ist dadurch nicht kleiner, sondern ehrlicher. |
| `FENSTER_ZEICHEN` | 12.000 | Füllt sich wie gewollt (11.912). |
| `FENSTER_NACHRICHTEN` / `FENSTER_MIN_NACHRICHTEN` | 20 / 6 | Nach der Änderung A in keiner Messung mehr unterschritten (min. 16 Einträge). |
| `SZENE_ZEICHEN_MAX` / `_NOTFALL` | 6.000 / 2.000 | Der Deckel greift wie gewollt (Block 6.042 mit Kopfzeile). |
| `BUDGETS["festlegungen"]`, `JOURNAL_EINTRAEGE` | 800 / 8 | Deckel greifen wie gewollt (2.370 von 2.400 Z.; 1.422 Z.). |
| `journal.SCHWELLE_VERDRAENGUNG` | 600 | Keine Messung spricht dagegen; siehe offener Punkt unten. |
| `SZENE_ZEICHEN_JE_TOKEN` | 1,9 | Offline nicht nachmessbar (braucht `count_tokens` übers Netz). |
| `BUDGETS["system"]`, `["phasenhinweis"]`, `["figurenhinweis"]` | 9.000 / 50 / 100 | Rein dokumentarisch, von keinem Codepfad durchgesetzt; eine Anpassung wäre kosmetisch. |
| `ZIEL` / `REISSLEINE` | 20.000 / 40.000 Token | `ZIEL` bindet nie vor der Körpergrenze, `REISSLEINE` wird nicht gelesen. |

### Offene Punkte (kein Konstantenproblem, bewusst nicht behoben)

1. **Die Kürzungsleiter kennt `FENSTER_MIN_NACHRICHTEN` nicht, und was sie
   aus dem Fenster nimmt, journalisiert niemand.** `_kuerze_auf_budget`
   schneidet das Fenster notfalls bis auf 0, und der Journal-Extraktor
   rechnet „verdrängt“ gegen das ungekürzte `waehle_fenster`. Nach
   Änderung A nachgemessen: **phasengerecht tritt es nicht mehr auf** (in
   keiner Phase gekürzt). In der Obergrenzen-Vollast (alle Blöcke in jeder
   Phase) bleibt es in den Phasen 1–3: das Fenster fällt auf **16–17**
   Einträge (nicht mehr unter das Minimum von 6, vorher auf 0), aus dem
   Fenster fallen 2–3 Einträge = **403–738 Token** je Zug, davon liegt je
   genau **einer** im Extraktor-Abschnitt. Der Rest (bis ~738 Token, also
   über `SCHWELLE_VERDRAENGUNG` = 600) steht dann weder im Prompt noch im
   Journal. Das ist ein Verhalten der Leiter, keine Grenze; es zu beheben
   (Untergrenze in der Leiter, oder der Extraktor rechnet gegen das
   gekürzte Fenster) ist eine eigene Aufgabe.
2. **Szenenbudget bei sehr großer Anweisung.** Wüchse eine
   Szenen-Systemanweisung allein über das Budget (heute 19.496 von 37.488
   Token), bliebe dem Nutzertext 0; die Leiter kürzt dann bis zum Ende und
   meldet „REICHT IMMER NOCH NICHT“ — der Lauf geht trotzdem raus. Heute
   weit entfernt; ein Stolperdraht wie `SYSTEM_ZEICHEN_MAX` für die
   Szenenanweisung existiert nicht.
