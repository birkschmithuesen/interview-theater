# Kontext-Aufträge 3–5: Messbericht

06.09.2026, Branch `feat/kontext-3-5`, Grundlage
`docs/kontext-audit-2026-09-06.md` Abschnitt D (Aufträge 3, 4, 5).

Alle Zahlen erzeugt gegen die Spätstand-Fixture
(`tests/fixture_spaetstand.py`, dieselbe Gruppe wie
`tests/test_prompt_audit.py`) und gegen eine **Kopie** von `betrieb/test.db`
nach `/tmp`. **Keine** Nachrichtentexte, Transkripte, Namen oder
Antworttexte in diesem Bericht — nur Zahlen und ja/nein.

Vergleichsstand „vorher" ist `origin/main` @ `9d00b98`, ausgecheckt in einem
zweiten Worktree und mit demselben Skript gemessen.

---

## 1. Auftrag 3 — Szenenblock gedeckelt, Kürzungsreihenfolge korrigiert

`kontext.SZENE_ZEICHEN_MAX = 6.000` Zeichen (Anfang 40 % + Schluss, dazwischen
`[... Mittelteil der Szene ausgelassen ...]`, geschnitten an Zeilengrenzen).
Neue Leiter: Transkripte → **Szenenblock auf 2.000** → Fenster → Journal →
Verdichtungen → **Szenenblock auf den ausgerechneten Restplatz**.

### Blocklängen vorher / nachher (Spätstand-Fixture, Phase 7)

| Szene | Körper vorher | Körper nachher | Gesamt vorher | Gesamt nachher |
|---|---:|---:|---:|---:|
| ×1 (normal)  |   4.899 |   4.899 |  31.264 |  31.264 |
| ×8           | 107.343 |  10.965 | 133.708 |  37.330 |
| ×20          | 265.743 |  10.965 | 292.108 |  37.330 |

Grenzen: Körper 24.000 Zeichen, Gesamt 40.000 Zeichen.

### Was in den Blöcken passiert (Token, ÷3)

| Szene | Stand | szene | fenster | journal |
|---|---|---:|---:|---:|
| ×8  | vorher  | 34.863 | **0** | **0** |
| ×8  | nachher |  2.021 |   532 |   182 |
| ×20 | vorher  | 87.663 | **0** | **0** |
| ×20 | nachher |  2.021 |   532 |   182 |

**Der Befund C.4 in einer Zeile:** vorher war bei ×20 alles Opferbare
geopfert — Fenster 0, Journal 0, Verdichtungen 0 — und der Prompt lag
trotzdem bei 265.743 Zeichen Körper, also 11× über der Grenze. Nachher liegt
er bei 10.965 Zeichen, und Fenster **und** Journal stehen unverändert da. Die
Umkehrung der Priorität aus dem Audit ist damit aufgehoben: der Bot behält
jetzt, was die Gruppe zur Szene gesagt hat, statt den Text, den er ohnehin
gerade schreibt.

Die normale Szene (×1) ist **bitgleich** unverändert — der Deckel greift erst
über 6.000 Zeichen. Die längste Szene der Testgruppe liegt darunter.

### Test-Zusicherungen (`tests/test_kontext.py`, 6 neu)

- kurze Szene unangetastet, keine Auslassungsmarke
- überlange Szene: Anfang **und** Schluss stehen drin, Marke dazwischen
- `_gekuerzte_szene` gegen vier Grenzen (200 / 1.000 / 6.000 / 20.000) plus
  Einzeiler-Rückfall (Modell-Ausrutscher ohne Zeilenumbrüche)
- **×20-Szene bleibt nach Kürzung unter Grenze UND unter `ZIEL`**
- **Fenster und Journal überleben eine überlange Szene** (Textmarken)

---

## 2. Auftrag 4 — Systemanweisung in die Messung aufgenommen

`gesamtgrenze()` = 40.000 Zeichen für System + Körper (Env
`IT_PROMPT_ZEICHEN_GESAMT`), geprüft in `kontext.baue._zu_lang()`. Die
Körpergrenze (24.000) und `ZIEL` (20.000 Token) bleiben daneben stehen.

### Systemgröße je Phase (gemessen, Zeichen / Token ÷3)

| Phase | Zeichen | Token | Grenze `SYSTEM_ZEICHEN_MAX` = 30.000 |
|---:|---:|---:|---|
| 1 | 23.354 | 7.784 | ok |
| 2 | 28.018 | 9.339 | ok (engster Fall, 93 % ausgeschöpft) |
| 3 | 24.867 | 8.289 | ok |
| 4 | 26.096 | 8.698 | ok |
| 5 | 25.891 | 8.630 | ok |
| 6 | 24.202 | 8.067 | ok |
| 7 | 26.365 | 8.788 | ok |
| 8 | 23.010 | 7.670 | ok |

Als Test je Phase fixiert
(`test_systemanweisung_bleibt_je_phase_unter_ihrer_grenze`, 8 Parametrisierungen)
plus je Phase ein Test „System + Körper ≤ Gesamtgrenze"
(`test_system_plus_koerper_bleiben_unter_der_gesamtgrenze`, 8 Parametrisierungen).

### Wirkung auf den echten Pfad (Kopie von `betrieb/test.db`, Phase 7)

| | vorher (`origin/main`) | nachher |
|---|---:|---:|
| System | 26.365 | 26.365 |
| Körper | 23.187 | **13.545** |
| Gesamt | **49.552** (über 40.000) | **39.910** (unter 40.000) |

Der Prompt lag im Betrieb also bereits **9.552 Zeichen über** der Zahl, die
wir uns jetzt setzen — unbemerkt, weil keine Grenze ihn maß. Er ist damit
nicht kaputt gewesen (Kimi hat 256K), aber die Zahl, die wir „unser Budget"
nannten, beschrieb ein Viertel.

Spec § 6.2 Block 1 von 900 auf 9.000 Token korrigiert, mit der Herleitung und
beiden Bremsen; § 7.2 auf die neue sechsstufige Leiter und die drei Maße
umgeschrieben. `kontext.BUDGETS["system"]` von 900 auf 9.000,
`BUDGETS["szene"]` von 1.500 auf 2.000 (der Notfall-Deckel).

---

## 3. Auftrag 5 — Recall-Messung ohne LLM

`scripts/kontext_recall.py`. Zehn mechanisch aus der Datenbank abgeleitete
Faktenfragen, Prüfung durch reine Textsuche: *steht die Antwort noch im
Prompt?* Kein Modellaufruf, deterministisch, damit als Test tauglich.

**Die Fragen kommen zuerst aus dem weggefallenen Teil** — sonst misst die
Tabelle, dass das Geschützte geschützt ist, und das ist eine Tautologie
(genau der Fehler, den hermes-agents `evals/compaction` durch das
Region-Scoping vermeidet). Kategorie `verdraengt`: der Anfang des Verlaufs,
die Mitte des Verlaufs, ein älterer Journaleintrag, die Mitte der aktuellen
Szene. Kontrollgruppe: Arbeitsstand, Figuren, Szene, Journal.

### Fixture, Normalfall (`--fixture`)

| Frage | Bereich | vorher | nachher |
|---|---|---|---|
| Was wurde ganz am Anfang gesagt? | verdraengt | NEIN | NEIN |
| Was wurde in der Mitte des Verlaufs gesagt? | verdraengt | NEIN | NEIN |
| Was stand in einem älteren Journaleintrag? | verdraengt | ja | ja |
| Welches Kernthema hat die Gruppe gesetzt? | arbeitsstand | ja | ja |
| Wie lautet die Kernfrage? | arbeitsstand | ja | ja |
| In welchem Rahmen spielt das Stück? | arbeitsstand | ja | ja |
| Wie lautet die Geschichte? | arbeitsstand | ja | ja |
| Welche Begriffe hat die Gruppe gesammelt? | arbeitsstand | ja | ja |
| Welche Figuren hat die Gruppe? | figuren | ja | ja |
| Was will die erste Figur? | figuren | ja | ja |

**Recall 8/10 nach Kürzung (vorher 8/10)** — Körper 4.899 → 4.638 Zeichen.

Die zwei `NEIN` sind kein Fehler der Kürzung: der Verlaufsanfang steht schon
**vor** jeder Kürzung nicht mehr im Prompt, weil das Fenster
nachrichten-/zeitbemessen ist. Das ist der Befund C.2/C.3 des Audits, den
Aufträge 1+2 behandeln — die Recall-Messung macht ihn sichtbar, statt ihn zu
verschweigen.

### Fixture mit ×20-Szene (`--fixture 20`, der Fall C.4)

| Frage | Bereich | vorher | nachher |
|---|---|---|---|
| Was wurde ganz am Anfang gesagt? | verdraengt | NEIN | NEIN |
| Was wurde in der Mitte des Verlaufs gesagt? | verdraengt | NEIN | NEIN |
| Was stand in einem älteren Journaleintrag? | verdraengt | ja | ja |
| Was steht in der Mitte der aktuellen Szene? | verdraengt | NEIN | NEIN |
| Welches Kernthema hat die Gruppe gesetzt? | arbeitsstand | ja | ja |
| Wie lautet die Kernfrage? | arbeitsstand | ja | ja |
| In welchem Rahmen spielt das Stück? | arbeitsstand | ja | ja |
| Wie lautet die Geschichte? | arbeitsstand | ja | ja |
| Welche Begriffe hat die Gruppe gesammelt? | arbeitsstand | ja | ja |
| Welche Figuren hat die Gruppe? | figuren | ja | ja |

**Recall 7/10 (vorher 7/10)** — Körper 10.965 → 10.704 Zeichen, Gesamt 37.069.

Das eine zusätzliche `NEIN` ist der **bezahlte Preis** des Deckels: die Mitte
einer 20-fachen Szene steht nicht mehr im Prompt. Das ist die Absicht — dafür
stehen Anfang und Schluss der Szene, das Fenster und das Journal noch da, und
der Prompt hält seine Grenze. Auf `origin/main` stand dieselbe Szenenmitte
zwar im Prompt, aber um den Preis von Fenster = 0, Journal = 0 und 292.108
Zeichen Gesamtgröße.

### Test-DB-Kopie (`/tmp/…`, Kopie von `betrieb/test.db`)

| Frage | Bereich | vorher | nachher |
|---|---|---|---|
| Was wurde ganz am Anfang gesagt? | verdraengt | NEIN | NEIN |
| Was wurde in der Mitte des Verlaufs gesagt? | verdraengt | ja | ja |
| Welche Begriffe hat die Gruppe gesammelt? | arbeitsstand | ja | ja |
| Was steht im ältesten Journaleintrag? | journal | ja | ja |
| Was steht im jüngsten Journaleintrag? | journal | ja | ja |

**Recall 4/5 (vorher 4/5).** Weniger als zehn Fragen, weil die Gruppe zum
Zeitpunkt der Messung in Phase 3 stand und noch keine Szenen und keine
gesetzte Kernfrage hatte — Fragen ohne Datengrundlage fallen weg, statt
konstant „nein" zu melden. Die DB ist live und driftet zwischen Kopien;
eine frühere Kopie desselben Tages stand auf Phase 7.

**Kein einziger geschützter Fakt geht durch die Kürzung verloren** — auf
keinem der drei Pfade, auch nicht bei der ×20-Szene. Das ist die Zusicherung,
die vorher niemand geprüft hat.

### Tests (`tests/test_kontext_recall.py`, 6 neu)

zehn Fragen abgeleitet · Fragen aus dem weggefallenen Teil kommen zuerst ·
geschützte Felder überleben · ×20-Szene kostet keinen geschützten Fakt und
hält beide Grenzen · Bericht trägt keine Antworttexte · Messung ist
reproduzierbar.

---

## 4. Was sich für den Bot ändert

1. Bei einer Szene über 6.000 Zeichen sieht der Bot Anfang und Schluss statt
   des ganzen Textes — mit sichtbarer Auslassungsmarke, damit er die Lücke
   nicht selbst füllt.
2. Bei Platznot fliegt zuerst die Szene, nicht mehr der Gesprächsverlauf.
   In Phase 6/7 heißt das: er hört wieder, was die Gruppe zuruft.
3. Der Prompt hält jetzt **garantiert** unter beiden Grenzen — vorher konnte
   die Kürzung ihr Ziel verfehlen und meldete das nicht.
4. Die Kürzung wird häufiger greifen als bisher, weil die Gesamtgrenze
   (40.000) im Betrieb schon heute gerissen wird (gemessen 49.552).
5. Der Vorfall `kontext_gekuerzt` trägt jetzt zusätzlich Systemgröße und
   Gesamtgrenze.
