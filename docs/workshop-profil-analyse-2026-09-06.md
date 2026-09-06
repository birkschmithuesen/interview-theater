# Was an diesem Repo „Dortmund" ist — Analyse für ein einhängbares Workshop-Profil

**Datum:** 06.09.2026 · **Branch:** `docs/workshop-profil` · **Basis:** `main` @ `f908b68`
**Auftrag (Birk, 06.09. 09:00):** Bestimmen, welche Teile des Projekts individuell für
genau diesen Workshop sind (Altersgruppe, Ortsvorgabe, Format …). Ziel: das Repo ist
zuerst generisch und bekommt einen Teil — z. B. `workshop/` mit Unterordnern —, der sich
dynamisch einhängt und alles individualisiert, sodass Padua ganz andere Angaben machen
kann, **ohne das Repo zu ändern und ohne dass Dortmund sich ändert.**

**Dieses Dokument baut nichts um.** Es ist die Grundlage für eine Brainstorming-Session
mit Claude Code (Teil E). Kein Betriebscode wurde angefasst; einzige Beigabe ist
`scripts/inventar_workshop.py`, ein reines Analyseskript ohne Betriebswirkung.

**Messgrundlage:** `python scripts/inventar_workshop.py` (Musterkatalog, acht Kategorien,
Suchbereiche Prompts/Code/Tests/Simulation/Skripte/Doku, ohne `betrieb/`, `prompt-audit/`,
`__pycache__`, Laufberichte).

## 0. Zahlen zuerst

**1217 Fundstellen** insgesamt. Verteilung nach Kategorie und Ort:

| Kategorie | gesamt | Prompts | Paketcode | Tests | Simulation | Skripte |
|---|---:|---:|---:|---:|---:|---:|
| Modelle-Recht (USA/Schweiz, Anbieter) | 398 | 5 | 154 | 102 | 20 | 23 |
| Ort (Dortmund, Bushaltestelle, Kiosk …) | 266 | 30 | 35 | 192 | 13 | 12 |
| Beispiel-Material (Koffer, Nordkiez, erste Liebe) | 208 | 17 | 18 | 161 | 20 | 4 |
| Format-Form (Herkules, Textbuch, fünf Formen) | 200 | 40 | 87 | 50 | — | 4 |
| Betrieb-Namen (theatersoap, lab.artesmobiles) | 56 | — | 5 | 23 | 2 | 11 |
| Zielgruppe (15–18, junge Frauen, Migrantinnen) | 40 | 10 | 15 | 3 | 11 | 3 |
| Rahmen-Dramaturgie (Rahmen des Stücks, Bühnenbild) | 36 | 22 | 25 | 8 | — | 3 |
| Sprache (auf Deutsch, `"language": "de"`) | 13 | 8 | 9 | 2 | — | 2 |

Lesart: **Zielgruppe und Sprache sind zahlenmäßig klein, aber teuer** — sie stehen an
wenigen, sehr zentralen Stellen (jede Prompt-Datei, ein STT-Feld) und ziehen den ganzen
Korpus nach sich. **Ort und Beispiel-Material sind zahlenmäßig groß, aber billig** — der
Löwenanteil steckt in Tests und Few-Shots, wo es Testdaten sind, keine Vorgaben.

Die restlichen ~330 Fundstellen liegen in Doku (`AGENTS.md` 27, `docs/HANDOFF.md` 24,
`SPEC-kontext-architektur.md` 18, `docs/recherche-urban-dance-…` 37,
`docs/analyse-workshop-tag1-…` 25) — Historie, kein Umbauziel.

---

# A. Inventar

Legende **Bindung**: `P` = Prompt-Markdown (hot-reload), `C` = hart im Code, `T` = Test,
`D` = Doku/Betrieb. **Vorschlag**: `generisch` = bleibt Kern, `Profil` = gehört ins
Workshop-Profil, `param` = parametrisieren (Kern liest einen Wert aus dem Profil).

## A.1 Zielgruppe (Alter, Geschlecht, Verein)

| Datei | Zeile | Fundstelle (≤80 Z.) | Bindung | Vorschlag |
|---|---:|---|---|---|
| `prompts/system.md` | 30–31 | „Die Gruppe sind junge Frauen zwischen 15 und 18 Jahren (Migrantinnenverein Dortmund)" | P | **Profil** |
| `prompts/szene.md` | 21–22 | wortgleich derselbe Block | P | **Profil** |
| `prompts/phasen/4.md` | 15–16 | „Rahmen des Stuecks … junge Frauen zwischen 15 und 18 Jahren" | P | **Profil** |
| `prompts/phasen/5.md` | 18–19 | dito | P | **Profil** |
| `prompts/phasen/6.md` | 13–14 | dito | P | **Profil** |
| `prompts/phasen/7.md` | 7–8 | dito | P | **Profil** |
| `phasentexte.py` | 55–58 | „Zielgruppe sind junge Frauen zwischen 15 und 18 …, angesprochen mit ‚ihr'" | C (Kommentar) + alle 8 Einleitungen im Duktus | **Profil** (Wortlaut) |
| `leitfaden.py` | 5–8 | „Die Gruppe sind junge Frauen zwischen 15 und 18; sie sprechen auf der Strasse oder im Verein …" | C (Docstring) | Profil-Notiz |
| `db.py` | 252 | „Die Interviews fuehren 15-18-Jaehrige mit FREMDEN Personen" | C (Schema-Kommentar) | generisch (Begründung, kein Wert) |
| `tests/test_anweisungen.py` | 226–232 | `for stichwort in ("15 und 18", "Bushaltestelle", "Halle", "Buehnenbild")` | **T (hart)** | **umbauen → Profilwerte** |
| `tests/test_phasentexte.py` | 58–68 | „Die Gruppe sind junge Frauen zwischen 15 und 18 … `" Sie " not in text`" | T | param (Anrede) |
| `simulation/stimmen/tag1-gruppe1..3.md` | 1 | „Du bist eine Sechzehnjaehrige aus Gruppe A eines Theaterworkshops" | D | **Profil** |
| `simulation/tag1.py` | 3 | „drei echte Gruppen (Sechzehnjaehrige) und eine …" | C | Profil-Daten |
| `simulation/skript.py` | 558 | „ohne Eroeffnung geht keine Sechzehnjaehrige auf eine fremde Person zu" | C (Kommentar) | generisch |
| `simulation/stimmen/dilan.md` | 10 | „Migrantinnengeschichte, an der sich das Publikum waermt" | D | **Profil** |

**Die Formulierung steht sechsmal wortgleich in Prompts.** Genau das ist der Ansatzpunkt:
ein Textbaustein, sechsfach dupliziert — der klassische Kandidat für ein Profil-Fragment,
das an sechs Stellen eingesetzt wird.

## A.2 Ort (Spielorte, Aufführungsort, Stadt)

| Datei | Zeile | Fundstelle | Bindung | Vorschlag |
|---|---:|---|---|---|
| `prompts/system.md` | 32–37 | „Schulhof, Strasse, oeffentlicher Platz, Bushaltestelle, Kiosk, Bahnhof … **Nicht:** Club, Disko, Alkohol" | P | **Profil** |
| `prompts/system.md` | 35–36 | „Wo es gezeigt wird: auf einem oeffentlichen Platz oder in einer grossen Halle" | P | **Profil** |
| `prompts/system.md` | 156, 312 | „vielleicht treffen sie sich an der Bushaltestelle" (Beispiel im Fließtext) | P | Profil-Beispiel |
| `prompts/szene.md` | 23–29, 128–129 | Ortsliste + „Streit auf dem Schulhof … am Kiosk" | P | **Profil** |
| `prompts/phasen/4,5,6,7.md` | je 15–22 | Ortsliste, viermal wortgleich | P | **Profil** |
| `prompts/phasen/7.md` | 39 | „Ich wuerde Szene 1 an der Bushaltestelle ansetzen" | P | Profil-Beispiel |
| `prompts/formen/chor.md` | 32 | `(Bushaltestelle, frueher Abend.)` — Layoutbeispiel | P | Profil-Beispiel |
| `prompts/formen/rap.md` | 48 | `(Bahnhof, seit zwei Stunden.)` | P | Profil-Beispiel |
| `knoepfe.py` | 862–863 | Kommentar „Vier Freundinnen im Nordkiez … Leyla checkt ihr Handy auf dem Schulhof" | C (Kommentar) | generisch |
| `befehle.py` | 110 | Hilfetext „/szene Szene 2: Maria kommt am Bahnhof an und trifft Elif" | C | param (Beispiel) |
| `scripts/fuelle_pruef_db.py` | 28, 60 | „Vier Freundinnen leben im Nordkiez in Dortmund …" | C (Fixture) | generisch (Testdaten) |
| `tests/test_knoepfe_ueberschreiben.py` | 6, 33 | derselbe Nordkiez-Satz als Fixture | T | generisch |
| `tests/test_prompt_audit.py` | 80 | derselbe Satz | T | generisch |
| `docs/entwurfsgeschichte.md` | 15 | „Workshop am 05. und 06.09.2026 in Dortmund, mit einem Migrantinnenverein" | D | generisch (Historie) |

**Wichtig:** „Dortmund" als Wort steht **in keinem einzigen Prompt außer `system.md` L31
und `szene.md` L22**. Die Ortsbindung läuft fast vollständig über die *Beispielorte*
(Bushaltestelle/Kiosk/Schulhof), nicht über den Stadtnamen — das ist die gute Nachricht.

## A.3 Sprache

| Datei | Zeile | Fundstelle | Bindung | Vorschlag |
|---|---:|---|---|---|
| `stt.py` | 128–129 | `"model": "whisper", "language": "de"` | **C (hart)** | **param** |
| `prompts/system.md` | 345 | „Schreibe auf Deutsch, in kurzen, natuerlichen Saetzen" | P | **Profil** |
| `prompts/szene.md` | 222 | „Deutsch. Kommen in den Zitaten andere Sprachen vor …" | P | **Profil** |
| `prompts/journal.md` | 23, 58 | „ein deutscher Satz von 8 bis 20 Woertern"; „Antworte auf Deutsch" | P | **Profil** |
| `prompts/verdichter.md` | 32, 59 | „kein Soziologendeutsch"; „Schreibe auf Deutsch, da die Interviews auf Deutsch gefuehrt werden" | P | **Profil** |
| `prompts/erkenner.md` | 337 | „Antworte auf Deutsch, ausschliesslich mit dem JSON-Objekt" | P | **Profil** |
| `prompts/sprachprofil.md` | 48 | „Deutsch. Kommen im Transkript andere Sprachen vor …" | P | **Profil** |
| `prompts/formen/lied.md` | 29 | „nicht ploetzlich alle in Hochdeutsch singen: Fuellwoerter, Dialekt …" | P | **Profil** |
| `prompts/theater-tells.md` | 44, 95 | „Alle Figuren sprechen dasselbe Deutsch"; „Kein Wort Deutsch …" | P | **Profil** |
| `korpus/erkenner.jsonl` | alle 136 | Few-Shot-Dialoge auf Deutsch (Sara, Mert, Ayse …) | D | **Profil je Sprache** |
| `korpus/journal.jsonl` / `verdichter.jsonl` / `sprachprofil.jsonl` | 22/7/5 | dito | D | **Profil je Sprache** |
| `phasen.py` | 112–137 | `STICHWOERTER` = deutsche Wörter (`begriffe`, `figuren`, `schaerfen` …) | **C (hart)** | **Profil** |
| `szene.py` | 229–237 | `FORM_STICHWOERTER` = deutsche Wörter (`gesungen`, `sprechgesang`, `reim`) | **C (hart)** | **Profil** |
| `ablauf.py` | 277–287 | `_AUFTRAGSFORMEN` — deutsche Regex-Auftragsmuster | **C (hart)** | **Profil** |
| `phasentexte.py` | 60–115 | alle acht Einleitungen, deutscher Fließtext | **C (hart)** | **Profil** |
| `knoepfe.py` | 111 `_TEXT_*`-Konstanten (258 Verwendungen) | sämtliche Knopf- und Meldungstexte deutsch | **C (hart)** | **Profil** |
| `leitfaden.py` | 36–46 | „Euer Leitfaden fuers Interview:", „So fangt ihr an:" | C | **Profil** |
| `phasen.py` | 80–101, 188 | Phasennamen „Begriffe/Fragen/…"; `MELDUNG` | **C (hart)** | **Profil** |

Siehe Teil C — das ist der schwerste Sonderfall.

## A.4 Format / Formen / Textbuch-Maß

| Datei | Zeile | Fundstelle | Bindung | Vorschlag |
|---|---:|---|---|---|
| `szene.py` | 223 | `FORMEN = ("dialog", "monolog", "chor", "lied", "rap")` | **C (hart)** | **Profil (Katalog)** |
| `web_schreiben.py` | 70 | zweite, absichtlich gespiegelte Kopie derselben Tupel | **C (hart, doppelt!)** | **Profil** |
| `szenenfolge.py` | 75 | `FORM_VORGABE = "dialog"` | C | param |
| `szenenfolge.py` | 98–104 | „Es gibt genau fuenf: Dialog, Monolog, Chor, Lied, Rap" (Prompt im Code!) | **C (hart)** | **Profil** |
| `szenenfolge.py` | 140–147 | dieselbe Fünf-Formen-Regel im Geschichte-Prompt + „Höchstens EINE Nicht-Dialog-Szene je drei Szenen" | **C (hart)** | **Profil** |
| `prompts/phasen/5.md` | 43, 80 | „eine von fuenf — Dialog, Monolog, Chor, Lied, Rap"; „Die fuenfte Spalte ist die Begruendung der Form" | P | **Profil** |
| `prompts/phasen/7.md` | 42 | „Die Form je Szene steht schon (Dialog, Monolog, Chor, Lied, Rap)" | P | **Profil** |
| `prompts/system.md` | 61–64 | „Jede Szene hat eine Form — genau eine von fuenf" | P | **Profil** |
| `phasentexte.py` | 104 | Einleitung Phase 7: „bestaetigt ihr die Form — Dialog, Monolog, Chor, Lied oder Rap" | **C (hart)** | **Profil** |
| `prompts/formen/dialog.md` | 1, 15–16 | „Textbuch nach Herkules-Maß"; „Herkules.exe: neun Szenen, rund 12.300 Woerter" | P | **Profil** |
| `prompts/formen/dialog.md` | 25, 29, 36, 40, 44 | „700 bis 1500 Woerter"; „80 % Sprechtext, maximal 20 % Regie"; „mindestens fuenf Repliken"; „im Mittel acht Woerter"; „jede dritte Replik ist eine Frage. Gemessen 32 %" | P | **Profil (Messwerte)** |
| `prompts/formen/dialog.md` | 8, 92 | „Regie und Choreografin arbeiten damit in der Probe" | P | **Profil** |
| `prompts/formen/dialog.md` | 135 | „Tanzvokabular. Popping, Locking, House, Krump …" (Negativliste) | P | **Profil** |
| `prompts/formen/{chor,lied,monolog,rap}.md` | je 3–10 | „dieselbe Layout-Konvention wie `dialog.md` (Textbuch nach Herkules-Maß)" | P | **Profil** |
| `prompts/system.md` | 38–41 · `szene.md` 29–32 · `phasen/7.md` 18 | „Zuerst entsteht ein Textbuch (Sprechtheater-Form nach Herkules-Maß); wie es inszeniert wird — Tanz, Musik, Buehne — entscheidet das Team" | P | **Profil** |
| `szene.py` | 1214–1254 | `_AUFGABE_ERSTE/_MITTE/_LETZTE` — Exposition/Mitte/Ende | C | generisch |
| `szenenfolge.py` | 64, 68 | `ANZAHL_VORGABE = 5`, `ANZAHL_MOEGLICH = (3,4,5,6)` | C | **param** |
| `AGENTS.md` | 46 | „genau fünf: `dialog`, `monolog`, `chor`, `lied`, `rap`" | D | Profil-Doku |
| `tests/test_anweisungen.py` | 236–300 | prüft Herkules-Zahlen, „Choreografin", „Sprechtheater-Textbuch", Negativliste (Krump/Cypher) wortwörtlich | **T (hart)** | → Profil-Test |
| `tests/test_szene.py` | 934 | „ein Sprechtheater-Textbuch (gemessen am Herkules.exe-Textbuch)" | T | → Profil-Test |
| `tests/test_knoepfe.py` 525 · `test_knoepfe_navigation.py` 457 | `assert not any("Urban Dance" in t …)` | T | generisch |

**`FORMEN` steht an zwei Orten im Code** (`szene.py` 223 und `web_schreiben.py` 70) plus
mindestens fünfmal ausgeschrieben in Prompts/Prompt-Konstanten. Das ist die härteste
Kopplung im Repo (siehe Kurzfassung).

## A.5 Rahmen / Dramaturgie des Stücks

| Datei | Zeile | Fundstelle | Bindung | Vorschlag |
|---|---:|---|---|---|
| `prompts/system.md` | 20–47 | Abschnitt **„## Rahmen des Stuecks"** (Wer spielt / Wo es spielt / Wo gezeigt / Was drin sein darf) | P | **Profil (ein Block)** |
| `prompts/szene.md` | 19–33 | derselbe Block, zweite Kopie | P | **Profil** |
| `prompts/phasen/4,5,6,7.md` | je 13–25 | derselbe Block, verkürzt, vier weitere Kopien | P | **Profil** |
| `prompts/system.md` | 42–44 | „Keine Gewaltverherrlichung"; „Konfliktstoff darf ernst sein — Familie, Erwartungen, Zugehoerigkeit" | P | **Profil** |
| `prompts/formen/dialog.md` | 142 | „**Buehnenbild und Requisiten** ueber das hinaus, was Menschen am Koerper tragen" | P | **Profil** |
| `prompts/system.md` | 1–19 | „zweitaegigen Theaterworkshop"; die acht Stationen | P | param (Dauer) / generisch (Stationen) |
| `prompts/system.md` | 49–53 | „Phase 1 ist eine Uebergabe: die Begriffe sind im Raum gesammelt worden" | P | generisch |
| `prompts/phasen/2.md` | 88–99 | Sensible Themen (Familie, Herkunft, Religion, Gewalt, Flucht, Diskriminierung); „Theaterprojekt im Verein" | P | **Profil** |
| `db.py` | 248–262 | Schemakommentar zu `frage_einleitungen`, „Interviews mit FREMDEN Personen" | C | generisch |
| `phasen.py` | 80–101 | acht Phasen mit Namen und Sätzen | C | generisch (Mechanik) + **Profil (Wortlaut)** |
| `phasentexte.py` | 60–115 | acht Einleitungen im Chat-Wortlaut | C | **Profil** |
| `leitfaden.py` | 36–46 | Überschriften des Interviewleitfadens | C | **Profil** |
| `tests/test_anweisungen.py` | 224–232 | `assert "Rahmen des Stuecks" in text` für 5 Prompt-Namen | **T (hart)** | → Profil-Test |

## A.6 Beispiel-Material (Few-Shots, Fixtures)

| Datei | Zeile | Fundstelle | Bindung | Vorschlag |
|---|---:|---|---|---|
| `prompts/erkenner.md` | 357, 454–556, 649 | Few-Shots: „Koffer, Bahnhof, Brief, Nachbarin", Namen Sara/Mert/Ayse/Elif/Maria | P (Few-Shot!) | **Profil je Sprache** |
| `prompts/journal.md` | 78 | „die Szene mit dem Koffer von gestern war echt stark" | P | **Profil je Sprache** |
| `prompts/formen/lied.md` | 18, 49 · `monolog.md` 18 | „Der Koffer steht seit dreissig Jahren …" | P | Profil-Beispiel |
| `prompts/phasen/2.md` | 20–21 | „Eine Frage zu ‚erste Liebe' …" | P | Profil-Beispiel |
| `prompts/theater-tells.md` | 130–159 | Negativbeispiele „aus dem Interview-Theater-Projekt (Herkules.exe, 2026)" mit Meryem/Elif/Maria | P | **Profil** |
| `korpus/*.jsonl` | 170 Zeilen | vollständiger Regressionskorpus, deutsch, mit Dortmund-nahen Themen | D | **Profil je Sprache** |
| `simulation/stimmen/*.md` | 8 Dateien | Personas: Sechzehnjährige Gruppe A/B/C, Dilan, Gülten, Halyna, Birk, Regie | D | **Profil** |
| `simulation/interviews/set1..3` | — | Interview-Sets für Simulationsläufe | D | **Profil** |
| `tests/test_*` | 161 Treffer | Nordkiez/Koffer/Bahnhof als Testdaten | T | generisch (Fixtures) |

**Wichtiges Detail:** `tests/test_anweisungen.py` L206–221 verbietet Beispiel-Eigennamen in
allen Prompts **außer `erkenner.md`** — dort sind sie gemessene Few-Shots. Ein
Sprachwechsel bricht also genau die eine Datei, die von der Anti-Nachplapper-Regel
ausgenommen ist und deren Few-Shots teuer gemessen wurden.

## A.7 Betriebsnamen (Bots, Web, Units)

| Datei | Zeile | Fundstelle | Bindung | Vorschlag |
|---|---:|---|---|---|
| `einstellungen.py` | 19 | `"IT_WEB_URL": "https://lab.artesmobiles.art/theatersoap"` | C (Default) | **param, Default leeren** |
| `web.py` | 58–62 | `VORGABE_PRAEFIX = "/theatersoap"` + Kommentar „Historischer Name aus dem ersten Einsatz" | C | **param** |
| `scripts/web_links.py` | 24–25 | `VORGABE_URL = "https://lab.artesmobiles.art/theatersoap"` | C | **param** |
| `docs/betrieb-env.beispiel` | 38 | `IT_WEB_URL=https://lab.artesmobiles.art/theatersoap` | D | Profil-Beispiel |
| `docs/interview-theater@.service` | 7–13 | `WorkingDirectory=%h/projekte/interview-theater`, Log je `%i` | D | generisch |
| `docs/HANDOFF.md` | 475 | Units `gruppe1/2/3` ↔ `@theatersoap1/2/3_bot`, Chat-IDs | D | Profil-Doku |
| `tests/test_web.py` | 266–270, 386–400, 433 | `/theatersoap`-Pfad hart in 7 Assertions | **T (hart)** | → param |
| `tests/{test_bot,test_ablauf,test_befehle,test_begruessen}.py` | je 1–2 | `web_url="https://lab.test/theatersoap"` | T | generisch (Fixture) |
| `tests/e2e/test_web_edit_e2e.py` | 183 | `"IT_WEB_PREFIX": "/theatersoap"` | T | generisch |
| `tests/test_simulation_birk.py` | 34 | `quelle: theatersoap1_bot` | T | generisch |
| `betrieb/gruppe{1..4}.env` | — | je Gruppe eigener Bot-Token/Name (**nicht gelesen**) | D | **hier hängt IT_WORKSHOP ein** |

Gut: der Bot-Name kommt schon aus `IT_BOT_NAME`, die DB aus `IT_DB`, das Web-Präfix aus
`IT_WEB_PREFIX`. **Der Betriebsteil ist bereits weitgehend profilfähig** — nur die
Vorgabewerte tragen „theatersoap"/„artesmobiles".

## A.8 Modelle und Rechtsvorgaben

| Datei | Zeile | Fundstelle | Bindung | Vorschlag |
|---|---:|---|---|---|
| `szene.py` | 123–130 | `_TEXT_WARNUNG_USA`: „Modell von Anthropic (USA) … Alles andere bleibt in der Schweiz" | **C (hart)** | **Profil (Rechtstext)** |
| `szene.py` | 132–145 | `_TEXT_ANGEBOT_USA` (Einwilligungsdialog, 8 Sätze) | **C (hart)** | **Profil** |
| `szene.py` | 145–163 | `_TEXT_USA_JA/_NEIN/_ERINNERUNG/_KEINE_ANTWORT`, `USA_ERINNERUNGEN_MAX = 2` | C | Profil (Text) + generisch (Mechanik) |
| `einstellungen.py` | 15, 16, 23–25, 49–52 | `gemma-4-31B-it`, `api.infomaniak.com`, `IT_SZENE_ANBIETER=infomaniak`, `claude-opus-5` | C (Defaults) | param — **schon Env** |
| `befehle.py` | 52–63, 620–640 | `/szene usa ja|nein`, `_SZENE_USA`-Regex | C | Profil (Wortlaut) + generisch (Mechanik) |
| `knoepfe.py` | 58–59, 348–353, 1506–1524 | `ART_SZENE_USA`, „Nein, Schweiz", `biete_szene_usa` | C | Profil (Text) |
| `erkenner.py` | 117, 946–957, 1207–1210 | Änderungsart `szene_usa`, Quittungszeilen | C | generisch (Mechanik) |
| `prompts/erkenner.md` | 148 | Few-Shot „Modell — von Anthropic, in den USA … Sagt ja oder" | P | **Profil** |
| `db.py` | 29–31, 428–430 | Spalten `szene_usa_bestaetigt_am / _angeboten_am / _offener_auftrag` | C (Schema) | generisch |
| `stt.py` | 128–129 | Infomaniak-Whisper, `language: de` | C | param |
| `docs/betrieb-env.beispiel` | 41–49 | „claude: Opus über den lokalen Proxy … Nur dieser eine Aufruf geht in die USA" | D | Profil-Doku |

**Rechtsvorgabe = Text + Schwelle, Mechanik = generisch.** Die Einwilligung ist ein
sauber isolierter Mechanismus (Angebot → Erkenner → DB-Spalte → Warnung vor jeder Szene);
nur die *Formulierung* („Schweiz", „Anthropic", „USA") ist Dortmund-spezifisch. Für Padua
(Italien, EU) könnte die Antwort sogar lauten: kein USA-Angebot, weil der Träger es
untersagt — dann ist das Profil-Feld `einwilligung: aus` und der ganze Zweig verschwindet.

---

# B. Schichtenmodell — generischer Kern vs. Workshop-Profil

## B.1 Der generische Kern (bleibt, wo er ist)

Diese Teile funktionieren für **jede** Zielgruppe, jeden Ort, jedes Format:

| Kern | Wo | Warum generisch |
|---|---|---|
| Ablaufmaschine acht Phasen | `phasen.py` (Nummerierung, `setze`, `nummer_fuer`), `ablauf.py` | Die *Mechanik* (Phase halten, springen, Journal schreiben) ist inhaltsfrei |
| Gedächtnis / Kontextfenster | `kontext.py` (Dedupe, 24 000-Zeichen-Grenze, 20 Nachrichten/30 min) | reine Ökonomie |
| Repository & Schema | `db.py`, `repo.py` | Felder sind Slots, keine Werte (Ausnahme: `szene_usa_*`, s. u.) |
| Knopf-Mechanik | `knoepfe.py` (Anlegen, Leiste abnehmen, Idempotenz) — **nicht die Texte** | Interaktionsmuster |
| Erkenner-Mechanik | `erkenner.py` (JSON-Schema, `ARTEN`, Anwendung, Quittung) — **nicht Prompt/Korpus** | Vertrag Modell↔Code |
| Aufnahme/STT-Pipeline | `aufnahme.py`, `stt.py` — **außer `language`** | Transport |
| Web | `web.py`, `web_daten.py`, `web_schreiben.py` — **außer Präfix und `FORMEN`** | Rendering |
| Simulation-Mechanik | `simulation/lauf.py`, `skript.py`, `kennzahlen.py`, `richter.py` — **nicht Stimmen/Sets** | Testrahmen |
| Prompt-Zusammensetzung | `anweisungen.py` (Hot-Reload, Pfadprüfung, Reihenfolge) | **der Einhängepunkt** |
| Szenen-Aufruf | `szene.py` Aufrufweg, Sperre, Aufgabe-der-Szene-Blöcke | Position ≠ Inhalt |
| Prompt-Audit | `scripts/erzeuge_prompts.py`, `tests/test_prompt_audit.py` | Regeln (keine Dubletten, Grenze) gelten immer |

## B.2 Das Profil (wird eingehängt)

| Profil-Element | Datenform | Pflegt | Heutige Fundstelle |
|---|---|---|---|
| Zielgruppe (Alter, Anrede, Trägerkontext) | `profil.yaml` → Feld `zielgruppe` | Birk/Nina | `system.md` 30, ×6 dupliziert |
| Orte (Spielorte-Positivliste, Negativliste, Aufführungsort) | `profil.yaml` → `orte` | Birk/Nina | `system.md` 32–37, ×5 |
| „Rahmen des Stücks" als ganzer Prompt-Block | `prompts/rahmen.md` (Overlay) | Birk | `system.md` 20–47 + 5 Kopien |
| Sprache (Prompt-Sprache, `whisper.language`, Anrede) | `profil.yaml` → `sprache: {code, anrede}` | Birk | `stt.py` 129, ×9 Prompts |
| Formen-Katalog | `formen.yaml` + `formen/<name>.md` | Birk/Choreografin | `szene.py` 223, `web_schreiben.py` 70, `szenenfolge.py` 98/140 |
| Textbuch-Maß (Wörter, Regie-%, Repliklänge, Fragenanteil) | `profil.yaml` → `textbuch_mass` (Zahlen) + `formen/dialog.md` | Birk | `formen/dialog.md` 15–44 |
| Phasentexte-Wortlaut (8 Einleitungen) | `phasentexte.yaml` | Birk/Nina | `phasentexte.py` 60–115 |
| Phasennamen + Stichwörter | `phasen.yaml` | Birk | `phasen.py` 80–137 |
| Knopf- und Meldungstexte | `texte.yaml` (111 Schlüssel) | Birk | `knoepfe.py` `_TEXT_*` |
| Leitfaden-Bausteine | `texte.yaml` | Nina | `leitfaden.py` 36–46 |
| Beispiel-Themen / Few-Shots | `prompts/`-Overlays (erkenner/journal/verdichter) | Birk | `erkenner.md` 340–660 |
| Erkenner-Korpus | `korpus/*.jsonl` je Profil | Birk | `korpus/` |
| Bot-/Web-Namen | Env (`IT_BOT_NAME`, `IT_WEB_URL`, `IT_WEB_PREFIX`) — **schon so** | Betrieb | `einstellungen.py` 19, `web.py` 62 |
| Modell-/Rechtsvorgaben (Einwilligungstext, an/aus) | `profil.yaml` → `einwilligung` + `texte.yaml` | Birk | `szene.py` 123–163 |
| Simulations-Personas | `simulation/stimmen/*.md`, `interviews/set*` je Profil | Birk | `simulation/` |
| Sensible Themen (Interview-Ethik) | `profil.yaml` → `sensible_themen` | Nina | `phasen/2.md` 88 |

## B.3 Der Einhängemechanismus (Vorschlag)

**Der einzige heutige Einhängepunkt ist `anweisungen.system()`** — Basis → `phasen/N.md`
→ `zusatz.md` → `zusatz.<bot>.md`, alles mit mtime-Hot-Reload. Diese Funktion ist bereits
genau die richtige Stelle; sie bekommt eine Schicht dazwischen:

```
Basis (Repo-Default)
  → Phase (Repo-Default, ggf. Profil-Overlay)
    → PROFIL-OVERLAY (neu: workshop/<name>/prompts/…)
      → zusatz.md            (Regie-Zettel, alle Bots)
        → zusatz.<bot>.md    (Regie-Zettel, ein Bot)
```

Auswahl über **eine** Umgebungsvariable, die je `betrieb/gruppeN.env` gesetzt wird:

```
IT_WORKSHOP=dortmund-2026     # gruppe1/2/3/4.env
IT_WORKSHOP=padua-2026        # spätere Envs, gleicher Server, gleicher Baum
```

Weil die Env schon heute je Gruppe geladen wird (`set -a; . ./betrieb/gruppe1.env; set +a`),
können **zwei Workshops parallel auf einem Server** laufen, ohne dass sich etwas ins Gehege
kommt — vorausgesetzt, kein Profil-Zustand landet in Modul-Globals (siehe D.5).

**Fallback ist der Schlüssel zur Bitgleichheit:** fehlt `IT_WORKSHOP`, gilt der
Repo-Default = das heutige Dortmund. `workshop/dortmund-2026/` wird zunächst *leer*
angelegt (nur `profil.yaml` mit den Werten, die schon im Repo stehen); erst wenn ein Test
beweist, dass Profil-gerendert == Repo-Default, wandert Inhalt tatsächlich hinüber.

---

# C. Sonderfall Sprache — Padua ist Italienisch

Sprache ist **nicht** ein Profil-Feld unter vielen. Sie ist die Achse, an der die meisten
gemessenen Artefakte hängen. Was konkret bricht:

| Was | Wo | Warum es bricht | Aufwand |
|---|---|---|---|
| Prompt-Sprache (9 Dateien) | `system/szene/journal/verdichter/erkenner/sprachprofil/lied/theater-tells` | „Schreibe auf Deutsch" → das Modell antwortet deutsch | **mittel** — Übersetzung + Review durch Muttersprachler:in |
| **Erkenner-Korpus (136 Fälle)** | `korpus/erkenner.jsonl` | Gemessene FP=0-Zusicherung gilt nur für diese Sätze in dieser Sprache | **hoch** — neu erheben, nicht übersetzen |
| Erkenner-Few-Shots | `prompts/erkenner.md` 340–660 (~320 Zeilen) | Sie sind der Vertrag; auf Italienisch neu belegen | **hoch** |
| Whisper-Sprache | `stt.py` 129 `"language": "de"` | Deutsch-Whisper auf italienisches Audio = Kauderwelsch | **niedrig** — ein Parameter |
| Phasen-Stichwörter | `phasen.py` 112–137 | „figuren", „schaerfen" trifft nie in einem it. Chat | **niedrig** — Datentabelle |
| Formen-Stichwörter | `szene.py` 229–237 | „gesungen", „reim" | **niedrig** |
| Auftragsmuster | `ablauf.py` 277–287 | deutsche Regex („schreib uns", „mach mal") | **niedrig-mittel** |
| Alle Chat-Texte | `knoepfe.py` (111 `_TEXT_*`), `phasentexte.py` (8), `leitfaden.py`, `phasen.MELDUNG`, `befehle.py` | die Gruppe liest sie | **hoch (Menge)** — aber mechanisch |
| Anti-Nachplapper-Wortlisten | `tests/test_anweisungen.py` 212, `test_phasentexte.py` 66, `test_prompt_audit.py` 43 | Verbotene Namen sind deutsch/dortmundisch; italienische Beispielnamen fehlen | **niedrig** — Liste ins Profil |
| Simulation-Stimmen | `simulation/stimmen/*.md` (8) | Personas schreiben deutsch | **mittel** |
| Richter-Prompt | `prompts/richter.md` | bewertet deutsche Bot-Sprache | **mittel** |
| Sprachprofil-Regel | `prompts/sprachprofil.md` 48 | „Deutsch. Kommen im Transkript andere Sprachen vor …" — die Regel ist *für* Mehrsprachigkeit gebaut, nur der Anker ist deutsch | **niedrig** |
| Doku/AGENTS | überall | deutsch, bleibt deutsch (Arbeitssprache des Teams) | **keiner** |

**Realistischer Weg (Empfehlung):**

1. **Übersetzte Prompt-Sets je Profil**, nicht ein mehrsprachiger Prompt. Ein Prompt, der
   „antworte in der Sprache X" sagt, verliert Idiomatik in genau den Teilen, die zählen
   (Duktus, „ihr"-Anrede, kurze Sätze). Ein italienisches Set ist ein eigener Text.
2. **Eigener Korpus je Sprache.** `korpus/` wird zu `workshop/<name>/korpus/`; die
   Untergrenzen aus `tests/test_korpus.py` (`MIN_ERKENNER = 70`, `MIN_ERKENNER_NEGATIV = 28`)
   gelten dann je Profil. Für Padua heißt das: **~70 italienische Erkennerfälle vorab
   erheben** — planbar aus Simulationsläufen mit italienischen Personas, aber es ist Arbeit
   vor dem Workshop, nicht währenddessen.
3. **Anrede als eigenes Feld.** Deutsch „ihr" ↔ italienisch „voi"; die Test-Assertion
   `" Sie " not in text` muss profilabhängig werden.
4. **Sprache ≠ Ort.** Padua kann italienische Prompts mit *anderen* Beispielorten haben
   (piazza, fermata, bar) — das sind zwei getrennte Profil-Felder, nicht eins.

**Grobe Schätzung Padua:** Prompts übersetzen ~1–2 Tage; Chat-Texte ~1 Tag (mechanisch);
Korpus ~2–3 Tage (der teure Posten); Simulation-Personas ~0,5 Tage. **≈ 5–7 Personentage
Inhalt**, zusätzlich zum Umbau der Mechanik.

---

# D. Risiken und Fallen beim Umbau

**D.1 Tests, die Profilwerte hart prüfen.** Mindestens 15 Testdateien. Die härtesten:

- `tests/test_anweisungen.py` 224–232: `for stichwort in ("15 und 18", "Bushaltestelle",
  "Halle", "Buehnenbild")` über fünf Prompt-Namen. Der Test hat recht (der Rahmen *muss*
  in den Prompt), prüft aber den Dortmund-Wortlaut. → muss gegen das *aktive Profil*
  prüfen, nicht gegen Literale.
- `tests/test_anweisungen.py` 236–300: sieben Tests auf den Herkules-Block
  („700 bis 1500 Woerter", „Choreografin", Negativliste Krump/Cypher/[BEWEGUNG]).
- `tests/test_phasentexte.py` 58–68: Anti-Nachplapper + Anrede.
- `tests/test_web.py` 266–270, 386–400, 433: `/theatersoap` in sieben Assertions.
- `tests/test_korpus.py` 26–55: Mindestzahlen des Korpus — sie müssen je Profil gelten,
  sonst blockiert ein halbfertiges Padua-Profil die Dortmund-Suite.

**Falle:** Wer diese Tests „profilfähig" macht, indem er die Literale durch
Profil-Lookups ersetzt, verliert die Zusicherung. Richtig ist ein **zweistufiger Test**:
(a) generisch — „das aktive Profil liefert einen nicht-leeren Rahmenblock, und der steht in
allen fünf Prompts"; (b) profil-spezifisch — `tests/profile/test_dortmund_2026.py` prüft
weiterhin „15 und 18" und die Herkules-Zahlen.

**D.2 Prompt-Audit-Fixtures.** `tests/test_prompt_audit.py` erzeugt echte Prompts gegen
eine Fixture-DB und prüft drei Regeln (keine Dublette >80 Z., Zeichengrenze, keine
Fremdnamen). `FREMDE_NAMEN = ("Kessel", "Mira", "Pola", "Pal ")` ist eine
Dortmund-Historie. → Liste ins Profil, Regel bleibt generisch.

**D.3 Golden Files sind schon da.** `docs/prompt-audit/2026-09-06/` enthält **21
Prompt-Dumps** (`01-gespraech.txt` … `14-feldvorschlag.txt`) plus `uebersicht.tsv` mit
Zeichen-/Tokenzahlen je Pfad. Das ist der fertige Beweisapparat für „Dortmund bleibt
bitgleich": nach jedem Umbauschritt `scripts/erzeuge_prompts.py` mit
`IT_WORKSHOP=dortmund-2026` laufen lassen und byteweise gegen diese 21 Dateien
diffen. **Vorsicht:** `erzeuge_prompts.py` hat eine `_entschaerfe()`-Stufe — der Vergleich
muss auf derselben Stufe stattfinden wie die abgelegten Dumps, sonst rauscht der Diff.

**D.4 Migrationen.** Das Schema (`db.py`, `user_version 2`) trägt Workshop-Semantik nur in
Kommentaren und in den drei `szene_usa_*`-Spalten. **Kein Schema-Umbau nötig** — ein
Profil ist Konfiguration, kein Datenmodell. Falls jemand `profil` als Spalte in `gruppe`
vorschlägt: nicht nötig, die Env je Prozess reicht und ist rückstandsfrei.

**D.5 Hot-Reload und Modul-Globals.** `anweisungen.py` cached nach *Name*
(`_CACHE[schluessel]`), nicht nach Profil. Läuft ein Prozess je Gruppe (heute so), ist das
egal — aber sobald zwei Profile in **einem** Prozess vorkämen (Web-Dienst!), liefert der
Cache den falschen Text. → Cache-Schlüssel muss `(profil, name)` werden, bevor irgendetwas
Profilabhängiges hot-reloadet. Der Web-Dienst liest heute nur `soap.db` und rendert
`FORMEN` aus `web_schreiben.py` — der ist der erste echte Mehrprofil-Kandidat.

**D.6 Zwei Workshops parallel.** Technisch heute schon möglich: eigene `.env`, eigene DB,
eigener Bot, eigene Unit-Instanz (`interview-theater@gruppeN`). Was fehlt, ist die
Trennung der **geteilten** Ressourcen: der Web-Dienst (eine Instanz, ein Präfix, eine DB)
und die Prompt-Dateien im Paket. → Web braucht entweder eine Instanz je Workshop
(anderes Präfix, andere DB) oder eine Profil-Spalte pro Gruppe. Empfehlung: **zweite
Web-Instanz**, kostet nichts und hält die Isolation sauber.

**D.7 Der Regie-Zettel-Konflikt.** `zusatz.md` liegt neben der DB und steht *nach* allem.
Wenn das Profil-Overlay davor kommt, kann ein Regie-Zettel weiter alles überstimmen —
gut so. Aber: die heutige Überschrift lautet „Zusaetzliche Anweisung fuer diesen
Workshop:". Bei einem echten Profil-Mechanismus wird der Satz irreführend (das Profil *ist*
jetzt „dieser Workshop"). → umformulieren zu „Anweisung für heute:".

**D.8 Doppelte `FORMEN`.** `szene.py` 223 und `web_schreiben.py` 70 tragen dieselbe Tupel;
`web_schreiben.py` 60 dokumentiert die Spiegelung ausdrücklich. Ein Profil-Formenkatalog
muss beide bedienen, sonst zeigt die Weboberfläche eine andere Formenliste als der Chat.

**D.9 Vault-Verweise.** `~/vault/30-Entities/artesmobiles/projekte/dortmund-workshop/`
existiert (`deck/ deliverables/ meetings/ notes/ dortmund-workshop.md tool-konzept.md`).
Nach der ArtesMobiles-Ablage-Karte ist ein zweiter Einsatzort eine **Show** unter
`projekte/<produktion>/shows/<YYYY-MM-ort>/`, kein neues Projekt. Padua gehört also
voraussichtlich unter `shows/2026-xx-padua/` desselben Projekts — das sollte die
Namensgebung der Profile spiegeln (`dortmund-2026`, `padua-2026`).

**D.10 Der Rückwärtsgang.** Jede Zeile, die aus dem Repo ins Profil wandert, ist eine
Zeile, die beim nächsten `git pull` nicht mehr mitkommt. Wer heute `system.md` im
laufenden Workshop bearbeitet (Hot-Reload!), bearbeitet danach `workshop/dortmund-2026/
prompts/system.md`. Das ist eine **Verhaltensänderung für Birk am Workshoptag** und muss
in `AGENTS.md` und `docs/HANDOFF.md` stehen, bevor der erste Schritt ausgerollt wird.

---

# E. Startpaket für die Brainstorming-Session mit Claude Code

## E.1 Zehn Fragen, die die Session entscheiden muss

**1. YAML-Werte oder Markdown-Overlays — oder beides?**
*Empfehlung: beides, sauber getrennt.* Zahlen und Listen (Alter, Formen, Textbuch-Maß,
Sprache) nach `profil.yaml`; zusammenhängende Prosa (Rahmenblock, Formen-Regelblöcke)
als Markdown-Overlay. Wer Prosa in YAML presst, bekommt unlesbare Blockskalare; wer
Zahlen in Markdown lässt, kann sie nicht validieren.

**2. Overlay-Strategie: Datei ersetzen oder Platzhalter füllen?**
*Empfehlung: Platzhalter im Repo-Prompt (`{{rahmen}}`), gefüllt aus dem Profil.* Ganze
Dateien zu ersetzen heißt, dass jede Verbesserung am generischen Prompt für Padua verloren
geht. Platzhalter halten Kern und Profil getrennt. Kompromiss: Ersetzen *erlauben*
(Datei gleichen Namens im Profil gewinnt), Platzhalter als Normalfall.

**3. Ein Profil je Gruppe oder je Server?**
*Empfehlung: je Prozess, über `IT_WORKSHOP` in `betrieb/gruppeN.env`.* Das ist die
feinste sinnvolle Körnung, kostet nichts und erlaubt eine Testgruppe mit abweichendem
Profil. Der Web-Dienst bekommt eine eigene Instanz je Workshop.

**4. Wie wird der Formen-Katalog erweitert (Padua: Commedia? Coro?)?**
*Empfehlung: `formen.yaml` listet Namen + Stichwörter, `formen/<name>.md` liefert den
Regelblock; der Kern liest die Liste, `FORMEN` verschwindet als Literal.* Die „genau
fünf"-Formulierung in `system.md`/`phasen/5.md`/`szenenfolge.py` wird zu „genau
{{formen_anzahl}}: {{formen_liste}}". Der Fallback (`dialog`) wird Profil-Feld
`form_vorgabe`.

**5. Was passiert mit den 111 `_TEXT_*`-Konstanten (258 Verwendungen) in `knoepfe.py`?**
*Empfehlung: **nicht** im ersten Anlauf anfassen.* Deutsche Knopftexte sind ein
Sprachproblem, kein Dortmund-Problem — für einen zweiten deutschsprachigen Workshop
irrelevant. Erst wenn Padua konkret wird, ein `texte.yaml` mit Schlüsseln einführen, und
dann in einem Rutsch. Bis dahin: **Sprache ist Schritt 7, nicht Schritt 1.**

**6. Wie geht man mit Test-Fixtures um, die Dortmund-Werte prüfen?**
*Empfehlung: zweistufig (siehe D.1).* Generische Tests prüfen Struktur („Rahmenblock
vorhanden, nicht leer, in fünf Prompts"), profil-spezifische Tests unter `tests/profile/`
prüfen Werte. Der Dortmund-Profiltest ist die Kopie der heutigen Assertions — dann
verliert man keine Zusicherung.

**7. Golden Files: Diff auf Prompt-Ebene oder auf Verhaltens-Ebene?**
*Empfehlung: beides, aber Prompt-Diff zuerst.* `docs/prompt-audit/2026-09-06/` (21 Dumps)
ist byteweise vergleichbar und schnell. Verhalten (Simulationsläufe) ist teuer und
nicht-deterministisch — als Nachlauf, nicht als Gate.

**8. Wo lebt der Erkenner-Korpus?**
*Empfehlung: `korpus/` bleibt Repo-Default (= Dortmund/Deutsch), Profile dürfen ihn
ersetzen (`workshop/<name>/korpus/`).* Die Untergrenzen in `test_korpus.py` gelten nur
für Profile, die einen eigenen Korpus mitbringen — sonst blockiert ein leeres Padua-Profil
die Suite.

**9. Wie werden Profile validiert, bevor ein Bot damit startet?**
*Empfehlung: `scripts/pruefe_profil.py <name>` — Pflichtfelder da, Formen-Dateien
vorhanden, Platzhalter alle auflösbar, Korpus-Mindestzahlen (falls eigener Korpus).*
Läuft in `scripts/betrieb-start.sh` vor dem Bot-Start; ein kaputtes Profil darf keinen
409-artigen Halbstart erzeugen. **Fehlerbild am Workshoptag ist die teuerste Währung.**

**10. Wer pflegt Profile — mit oder ohne Code-Kenntnis?**
*Empfehlung: `profil.yaml` muss ohne Python lesbar/änderbar sein (Nina, Birk im Zug);
Markdown-Overlays ebenso.* Kein Profil-Element darf Python sein. Wenn eine Anpassung Code
braucht, ist sie im falschen Layer.

## E.2 Skizze der Zielstruktur

```
workshop/
  dortmund-2026/
    profil.yaml            # zielgruppe, orte, sprache, textbuch_mass,
                           # einwilligung, sensible_themen, form_vorgabe,
                           # szenen_anzahl_vorgabe/moeglich, anrede
    formen.yaml            # dialog, monolog, chor, lied, rap (+Stichwörter)
    phasen.yaml            # Namen, Sätze, Stichwörter der acht Stationen
    phasentexte.yaml       # die acht Chat-Einleitungen im Wortlaut
    texte.yaml             # (später) Knopf-/Meldungstexte, Leitfaden-Bausteine
    prompts/
      rahmen.md            # der Block "## Rahmen des Stuecks"
      formen/
        dialog.md          # Herkules-Regelblock mit den gemessenen Zahlen
        monolog.md chor.md lied.md rap.md
      erkenner-beispiele.md   # (später) Few-Shots je Sprache
    korpus/                # (optional; sonst Repo-Default)
    simulation/
      stimmen/*.md
      interviews/set1..3
    LIESMICH.md            # was dieses Profil eigenständig macht

  padua-2026/
    profil.yaml            # sprache: it, anrede: voi, orte: piazza/fermata/bar,
                           # zielgruppe: <anderes Alter>, einwilligung: <?>,
                           # textbuch_mass: <anderes Vorbild oder dasselbe>
    formen.yaml            # z.B. dialogo, monologo, coro, canzone, rap, commedia
    prompts/…              # italienische Fassungen
    korpus/…               # italienische Erkennerfälle (~70)
    simulation/stimmen/…   # italienische Personas
```

Auswahl: `IT_WORKSHOP=dortmund-2026` in `betrieb/gruppe1.env` usw.
Ohne Variable: Repo-Default = heutiges Verhalten.

## E.3 Aufwandsliste in Schritten (jeder einzeln ausrollbar)

Leitplanke für **jeden** Schritt: `IT_WORKSHOP=dortmund-2026` und *ohne* Variable erzeugen
**bitgleiche** Prompts gegen `docs/prompt-audit/2026-09-06/` (21 Dumps). Test dafür:
`tests/test_profil_bitgleich.py` — „Profil dortmund-2026 erzeugt identische Prompts wie
der Repo-Default".

| # | Schritt | Inhalt | Aufwand | Risiko |
|---:|---|---|---|---|
| 0 | **Golden-File-Gate** | `tests/test_profil_bitgleich.py`, das die 21 Dumps gegen frisch erzeugte Prompts diffed. Läuft *vor* jedem weiteren Schritt. | 0,5 d | niedrig |
| 1 | **Profil-Lader** | `interview_theater/profil.py`: `IT_WORKSHOP` lesen, `workshop/<name>/profil.yaml` laden, leeres Profil = Repo-Default. Nichts verwendet es noch. + `scripts/pruefe_profil.py` | 0,5 d | niedrig |
| 2 | **Rahmenblock zentralisieren** | Der Block „## Rahmen des Stuecks" steht 6× dupliziert. Zuerst *im Repo* zu einer Quelle machen (`prompts/rahmen.md`, per Platzhalter in system/szene/phasen 4–7 eingesetzt). **Noch kein Profil.** Golden Files müssen bitgleich bleiben. | 1 d | **mittel** — 6 Dateien, Whitespace |
| 3 | **Rahmen ins Profil** | `workshop/dortmund-2026/prompts/rahmen.md` = heutiger Wortlaut; Kern nimmt Profil-Fassung, wenn vorhanden. Test D.1-zweistufig. | 0,5 d | niedrig |
| 4 | **Formen-Katalog** | `formen.yaml`; `szene.FORMEN` und `web_schreiben.FORMEN` lesen daraus; „genau fünf" in `system.md`/`phasen/5.md`/`szenenfolge.py` → Platzhalter. | 1,5 d | **hoch** — doppelte Konstante, Web+Chat müssen gleich bleiben |
| 5 | **Textbuch-Maß** | Zahlen aus `formen/dialog.md` nach `profil.yaml`, Regelblock als Profil-Overlay. `tests/test_anweisungen.py` 236–300 → `tests/profile/test_dortmund_2026.py`. | 1 d | mittel |
| 6 | **Phasentexte + Phasennamen** | `phasentexte.yaml`, `phasen.yaml`; `phasentexte.EINLEITUNGEN` und `phasen.PHASEN/STICHWOERTER` lesen daraus. | 1 d | mittel |
| 7 | **Sprache als Feld** | `profil.yaml → sprache.code` steuert `stt.py` `language`; Anrede-Feld; Anti-Nachplapper-Wortlisten ins Profil. | 0,5 d | niedrig |
| 8 | **Betriebsnamen entdortmunden** | Defaults in `einstellungen.py` 19, `web.py` 62, `scripts/web_links.py` 25 leeren bzw. neutralisieren; `tests/test_web.py` parametrisieren. Envs tragen die echten Werte (tun sie schon). | 0,5 d | niedrig |
| 9 | **Einwilligung/Recht** | `szene._TEXT_*USA*` → `texte.yaml`; `einwilligung: {aktiv, herkunft, ziel}` im Profil; Mechanik bleibt. | 1 d | mittel |
| 10 | **Korpus + Simulation profilfähig** | `korpus/` und `simulation/stimmen|interviews` je Profil auflösbar; `test_korpus.py`-Mindestzahlen nur für eigene Korpora. | 1 d | mittel |
| 11 | **Zweite Web-Instanz** | Web-Dienst je Workshop (Präfix, DB, Unit); Cache-Schlüssel `(profil, name)` in `anweisungen.py`. | 0,5 d | mittel |
| 12 | **Chat-Texte (nur wenn Padua kommt)** | 111 `_TEXT_*`-Konstanten nach `texte.yaml`. Groß, mechanisch, allein für Mehrsprachigkeit. | 2–3 d | **hoch (Menge)** |
| 13 | **Padua-Profil anlegen** | Inhalte: Prompts it., Korpus ~70 Fälle, Personas. Kein Kern-Code. | 5–7 d Inhalt | inhaltlich |

**Summe Mechanik (0–11): ≈ 9,5 Personentage.** Schritt 12 nur bei Mehrsprachigkeit
(+2–3 d). Schritt 13 ist Inhalt, kein Code.

**Reihenfolge-Empfehlung:** 0 → 1 → 2 → 3 → 8 → 4 → 5 → 6 → 7 → 9 → 10 → 11.
Schritt 8 früh, weil er billig und risikoarm ist und sofort Nutzen zeigt; Schritt 4
(Formen) ist der gefährlichste und sollte nicht der erste Profil-Schritt sein.

## E.4 Was die Session **nicht** entscheiden muss

- Das Datenmodell (D.4: kein Schema-Umbau).
- Die Prompt-Zusammensetzungsreihenfolge (`anweisungen.system()` ist richtig, sie bekommt
  nur eine Schicht dazwischen).
- Ob es eine Profil-Vererbung gibt (nein — zwei Profile, kein Framework).

---

## Anhang: Reproduktion

```
python scripts/inventar_workshop.py          # Zusammenfassung
python scripts/inventar_workshop.py --tsv    # jede Fundstelle, TSV
```

Das Skript ist reine Analyse: es wird von keinem Betriebsmodul importiert, öffnet keine
Datenbank und liest keine `betrieb/`-Datei.
