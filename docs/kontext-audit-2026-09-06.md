# Kontext-Management-Audit, 06.09.2026

Auftrag Birk, 06.09. 05:10: *„Das ganze Kontext-Management nochmal untersuchen …
prüfe, ob wir jetzt die bestmögliche Version haben. Du kannst auf den
hermes-agent-Code zugreifen und die Mechaniken vergleichen."*

Grundlage: Knowledge (`gedaechtnis-extraktion-agenten.md`),
`SPEC-kontext-architektur.md`, die Pläne, der Ist-Code auf `main` (HEAD
`dadf866`), **eigene Messungen** gegen Kopien von `betrieb/test.db` und
`betrieb/soap.db` (nur lesend, nur Aggregate), und der hermes-agent-Code unter
`/mnt/HC_Volume_106183673/hermes/hermes-agent` (read-only).

Reine Analyse. Kein Betriebscode geändert. Zwei parallele Agenten
(`feat/szenen-zusammenfassung`, `feat/opus-messung`) sind nicht angefasst.

**Kurzurteil vorab: Nein, das ist noch nicht die bestmögliche Version.** Die
drei gemeldeten Fehler von heute Nacht sind behoben. Aber die Messung am
Ist-Stand hat **vier neue, teils größere Befunde** gefunden, die alle dieselbe
Wurzel haben wie die alten: *ein Budget, das nur einen Teil des Prompts
bemisst, und Schwellen, die nicht mehr zu der Größe passen, gegen die sie
gesetzt wurden.*

---

## A. Soll (Knowledge + Spec + Plan) vs. Ist (Code heute)

### A.1 Die Tabelle je Mechanik

| # | Mechanik | Soll (Spec/Knowledge) | Ist (Code, `dadf866`) | Status |
|---|---|---|---|---|
| 1 | **Kurzes Fenster** | § 2 Schicht 3: „die letzten ~8.000 Token Chatverlauf", § 6.2 Block 7: „in Token statt Nachrichten bemessen — im Gruppenchat können ‚N Nachrichten' vier Redebeiträge oder vierzig Sekunden Geplänkel sein" | `FENSTER_NACHRICHTEN = 20` **und** `FENSTER_MINUTEN = 30`, kleinere Grenze gilt. Kein Tokenmaß. (`kontext.py:635,645`, `b727f09`) | **abweichend, bewusst** — die Spec-Begründung gegen Nachrichtenzählung ist nie widerlegt, nur überstimmt. Siehe C.2: das Fenster ist jetzt regelmäßig **leer**. |
| 2 | **Verdrängung → Journal** | § 2b, Knowledge § 2.1 Schule B: append-only Faktenextraktion, ausgelöst wenn ein Abschnitt aus dem Fenster fällt | `journal.berechne_verdraengten_abschnitt` rechnet gegen `kontext.BUDGETS["fenster"] = 8000` Token — also gegen das **alte, nicht mehr geltende** Fenster (`journal.py:150`) | **abweichend, unbemerkt** — die Kopplung wurde beim Fensterumbau (`b727f09`, 00:39) nicht nachgezogen. Gemessen in C.3. **Der wichtigste neue Befund.** |
| 3 | **Verdichtung (Material)** | § 2 Schicht 1: Verdichtung je Interview, wird **nie** aktualisiert | `verdichter.py`, `repo.verdichtungen`; append-only eingehalten | **erfüllt** |
| 4 | **Schichten** (Arbeitsstand / Journal / Verdichtung / Kernpaket) | § 2: vier Schichten, klare Zuständigkeit | Alle vier da; das **Kernpaket** ist eine fünfte, in der Spec nicht vorgesehene Schicht (`ecc7e61`, 05.09. 22:24) mit Phasenfilter | **erweitert über Spec hinaus** — sinnvoll, aber nirgends spezifiziert; die Spec kennt keinen Phasenfilter für Materialzugang. |
| 5 | **Budget / Kürzung** | § 6.2: Zielgröße ~20.000 Token, Reißleine 40.000, Block-Budgets je Block (System 900, Fenster 8.000 …). § 7.2: zwei Schritte — Transkripte raus, dann Fenster von vorn | `ZIEL=20_000`, `REISSLEINE=40_000` (**nirgends benutzt** — kein Codepfad liest sie), harte `ZEICHEN_GRENZE_VORGABE = 24_000`, vierstufige Kürzung (`4e0f309`). `BUDGETS` ist ausdrücklich „rein dokumentarisch" (`kontext.py:54-64`) | **teilweise erfüllt, mit Loch** — die Kürzung bemisst **nur den Körper**, nicht die Systemanweisung, und sie kann ihr Ziel **nicht garantiert erreichen** (C.4). |
| 6 | **Dedupe** | Knowledge § 2.6: semantische Dopplung vermeiden, „No Within-Response Duplication" | Vier Stellen: Kernpaket-Zusammenfassungen (`kontext.py:305-312`), `ohne_kernpaket_felder` (`:417`), Journal-Dedupe (`:607`), Journal auf 8 Einträge (`:589`) | **erfüllt** (heute Nacht gebaut, `4e0f309`). Die Prompt-Audit-Tests halten es fest. |
| 7 | **Phasen-Filter** | Spec § 0 Leitsatz 3: „Phasenbewusstsein ist ein Nebenprodukt der Materiallage, kein Zustand"; Nachtrag: Phase steuert Fokus, **nicht Informationszugang** | `material_erlaubt()` / `kernpaket_erlaubt()` steuern genau den Informationszugang über die gespeicherte Phase (`kontext.py:380-401`) | **Spec widersprochen, bewusst** — der Umbau vom 05.09. nachts (`21286ab`) kehrt den Leitsatz um. Gut begründet (Erfindungsphasen 4/5), aber die Spec sagt heute das Gegenteil dessen, was der Code tut. |
| 8 | **Szenen-Continuity** | Plan Teil B / § 6.2 Block 5: die eine zuletzt geänderte Szene im Volltext | `kontext._baue_szene` (Gesprächspfad) **und** `szene._continuity_text` (Szenenpfad, alle früheren Szenen im Volltext, gedeckelt über `CONTINUITY_ZEICHEN_MAX`) | **erfüllt** im Szenenpfad; im Gesprächspfad ist der Szenenblock **von der Kürzung ausgenommen** und damit ein unbegrenzter Wachstumspfad (C.4). |
| 9 | **Vorfall-Sichtbarkeit** | § 7.2: „Jede Kürzung schreibt einen `vorfall`" | `repo.merke_vorfall(..., "kontext_gekuerzt", ...)` mit Vorher/Nachher-Zahlen (`kontext.py:915`) | **erfüllt** — aber es gibt **kein Gegenstück** für „Kürzung hat ihr Ziel verfehlt" und keines für den Journal-Extraktor, der nie läuft. Verlust ist sichtbar, *ausbleibende Mechanik* nicht. |
| 10 | **Rolling Summary** | Spec § 2 + Knowledge § 3: **bewusst nicht** (Drift über zwei Tage) | nicht gebaut | **erfüllt (als Nicht-Bau)** — die Begründung trägt weiterhin. Siehe B.2. |
| 11 | **Selbstkorrektur des Divisors** | § 7.1: `geschaetzte_token` und echte `usage.prompt_tokens` in Tabelle `aufruf`, Divisor nachjustierbar, „Das Dashboard zeigt die Drift" | Spalte `prompt_tokens` existiert **nicht** in `aufruf` (gemessen gegen `soap.db`: `no such column: prompt_tokens`) | **nie gebaut** — der einzige Rückkopplungspfad zwischen Schätzung und Wirklichkeit fehlt. Die Spec hält den Divisor 2,92 aus einem einzelnen Rauchtest für „bestätigt" (§ 12). |

### A.2 Warum die drei gemessenen Fehler trotz Spec passiert sind

Die Frage aus dem Auftrag, mit Belegen. **Alle drei sind Implementierungs- plus
Testlücken, keine Spec-Lücken** — die Spec war in allen drei Punkten richtig.

**(a) 52.361 Zeichen — Implementierungslücke, verstärkt durch eine Maßeinheits-Lücke.**

Die Spec nennt in § 6.2 für Block 7 ein Budget von 8.000 Token und begründet es
ausführlich („Warum 8.000 und nicht 2.500"). Der Code hat dieses Budget nie
durchgesetzt und sagt das sogar wörtlich in seinem eigenen Kommentar
(`kontext.py:54-57`, vor dem Umbau identisch): *„Budgets in Token je Block
(SPEC § 6.2) — rein dokumentarisch, wie in keinem der Blöcke einzeln
durchgesetzt."* Der Kommentar begründet das mit einer plausiblen Überlegung
(ein Block, der schon beim Bauen gestutzt wird, versteckt die Fälle, die die
Kürzung zeigen soll) — und übersieht dabei, dass es **damit gar keine
Fenstergrenze mehr gab**, nur noch die Gesamtgrenze `ZIEL`.

Der zweite Teil ist die Maßeinheit: `ZIEL = 20.000` Token, gemessen als
Zeichen ÷ 3. 52.361 Zeichen sind nach dieser Rechnung 17.453 Token, also
**unter** ZIEL. Der Prompt war formal in Ordnung. Die Spec fordert 8.000 Token
fürs Fenster, der Code prüfte 20.000 Token für alles zusammen — die 8.000
existierten nur als Zahl in `BUDGETS` und als Satz im Kommentar.

Testlücke dazu: Es gab bis `b727f09` (06.09. 00:39) **keinen einzigen Test**,
der eine Obergrenze des Gesprächs-Prompts geprüft hätte.
`tests/test_kontext_fenster.py` ist am 06.09. 00:39 entstanden,
`test_prompt_audit.py::test_gespraech_haelt_die_harte_zeichengrenze` am
06.09. 01:03. Beide Tests wurden **nach** dem Vorfall geschrieben, nicht vorher.

**(b) Rückwärtiger Verlauf — reine Implementierungslücke, mit einer versteckten Annahme.**

`repo.letzte_nachrichten` sortiert `ORDER BY message_id` (`repo.py:314,317`).
Das ist für selbst empfangene Telegram-Nachrichten korrekt und war es jahrelang.
Die übernommene Gruppenhistorie trägt jedoch **negative, absteigend vergebene**
`message_id`s (gemessen: `min(message_id) = -319`, `max = 197` in derselben
Gruppe). Aufsteigend sortiert stehen diese Nachrichten damit **nach** ihrer
eigenen Zeitordnung falsch. Die Spec sagt zu Sortierung nichts — sie musste
auch nichts sagen, weil „chronologisch" selbstverständlich ist. Die Lücke ist,
dass der Code eine **Stellvertretergröße** (id) für die eigentliche Größe (Zeit)
benutzte, und dass der Import negativer ids diese Stellvertretung brach, ohne
dass irgendwo eine Zusicherung stand.

Behoben in `b727f09`: `roh.sort(key=lambda n: n["gesendet_am"])` mit dem
Kommentar *„die Uhrzeit lügt nicht"* (`kontext.py:706`).

**Aber die Wurzel steht noch:** `repo.letzte_nachrichten` sortiert weiterhin
nach `message_id` und **wählt auch nach `message_id` aus** (`LIMIT` auf der
DESC-Sortierung). Bei negativen ids kann der Pool damit die zeitlich jüngsten
Nachrichten gar nicht enthalten. Solange `_FENSTER_POOL = 1000` größer ist als
der ganze Verlauf, fällt das nicht auf. Bei einer Gruppe mit mehr als 1000
Nachrichten fällt es auf — und dann still. Ebenso rechnet
`journal.extrahiere` mit `max(n["message_id"] …)` als Wasserzeichen
(`journal.py:217`), was bei negativen ids den falschen Punkt markiert.

**(c) Journal-Extraktor lief an Tag 1 0× — Spec-Lücke *und* Testlücke.**

Die Spec beschreibt in § 2 das Journal ausführlich und begründet es
überzeugend (drei Dinge, die nirgends sonst stehen). Sie sagt aber **nirgends,
wie oft der Extraktor laufen soll oder muss**. Der Auslöser („bei Verdrängung")
stammt aus dem Modul-Docstring von `journal.py`, nicht aus der Spec. Damit gab
es keine Zusicherung, gegen die man hätte testen können.

Die Testlücke ist präziser benennbar: `tests/test_journal.py` hat sechs Tests
für `berechne_verdraengten_abschnitt` — alle mit **synthetischen** Nachrichten,
die so konstruiert sind, dass die Schwelle gerissen wird
(`test_verdraengter_abschnitt_ueber_schwelle_loest_aus_und_liefert_nur_ihn`).
Kein Test fragt: *läuft das bei einem realistischen Workshopverlauf je an?*
Gemessen (C.3): bei allen drei echten Betriebsgruppen von Tag 1 lautet die
Antwort **nein**, und zwar mit deutlichem Abstand.

Das ist der klassische Fall, den die Knowledge in § 2.8 indirekt beschreibt:
die Tests prüfen die Mechanik, nicht die Verteilung, gegen die sie laufen soll.

---

## B. Vergleich mit hermes-agent

Gelesen: `agent/context_engine.py` (489 Z.), `agent/context_compressor.py`
(7.858 Z.), `agent/native_compaction.py` (345), `agent/memory_manager.py`
(1.291), `agent/context_breakdown.py` (360),
`scripts/micro_compaction_report.py`, `evals/compaction/`.

Vorbemerkung zur Vergleichbarkeit: Hermes komprimiert eine **wachsende
Nachrichtenliste** gegen ein Modellfenster. Wir **bauen** einen Prompt bei
jedem Zug aus einer Datenbank neu zusammen. Das ist ein grundlegend anderes
Problem — unser Prompt kann nicht „vollaufen". Übertragbar sind deshalb nicht
die Algorithmen, sondern die **Disziplinen**: wie misst man, was schützt man,
wie macht man Verlust sichtbar.

| Mechanik | Hermes macht X | Wir machen Y | Bewertung | Übertragbar? |
|---|---|---|---|---|
| **Wann komprimieren** | `should_compress_info()` gibt `(bool, reason)` zurück — nicht nur „ja/nein", sondern **warum nicht**, wenn über der Schwelle und trotzdem blockiert (`cooldown:<s>`, `ineffective`). Kommentar: *„Without this signal an over-threshold session fails opaquely."* (`context_compressor.py:3221-3252`) | Kürzung läuft still, wenn `_zu_lang()`. Kein Grund-Rückgabewert. Wenn die Kürzung ihr Ziel **verfehlt**, merkt das niemand — der `vorfall` wird trotzdem geschrieben, mit Zahlen, die zeigen dass es nicht gereicht hat, aber ohne Kennzeichnung | Hermes hat hier eine Lektion, die uns exakt trifft: wir haben genau den „fails opaquely"-Fall (C.4) | **Ja, billig.** Zweiter Vorfalltyp `kontext_kuerzung_erfolglos`, wenn nach der Kürzung noch über der Grenze. ~20 Zeilen. |
| **Anti-Thrashing** | Wenn die letzten zwei Kompressionen je <10 % gespart haben, wird ausgesetzt — sonst Endlosschleife | Nicht nötig: unsere Kürzung ist einmalig je Zug, nicht iterativ über eine Sitzung | Kein Problem bei uns | Nein. |
| **Was bleibt geschützt** | Head (System + erster Austausch) + **token-budgetierter Tail** statt fester Nachrichtenzahl. Explizit: *„Token-budget tail protection instead of fixed message count"* (`context_compressor.py:13`). Lean Tail: 2,5 % des Fensters, Boden 10K, Deckel 25K Token (`:726-727`) | Geschützt: Kernpaket, Arbeitsstand, Hinweise, **aktuelle Szene**, Auslöser. Fenster ist **nachrichtenbemessen** (20), nicht tokenbemessen | **Hermes hat genau die Entscheidung getroffen, die unsere eigene Spec § 6.2 fordert und unser Code seit `b727f09` verlassen hat.** Und Hermes hat sie *in die Gegenrichtung* gelernt: von Nachrichtenzahl zu Tokenbudget | **Ja, und es ist unsere eigene Spec.** Siehe Auftrag 2. |
| **Geschützt ≠ unbegrenzt** | Der geschützte Tail hat einen **Deckel** (`LEAN_TAIL_CAP_TOKENS = 25_000`) und innerhalb des Tails werden alte Tool-Ergebnisse zu Zeigern degradiert (`_LEAN_TAIL_KEEP_TOOL_ROUNDS = 6`) — Kommentar: *„This is what lets the tail budget actually bind"* (`:735-739`) | Unser Szenenblock ist geschützt **und ungedeckelt**. Gemessen: bei einer großen Szene bleibt der Prompt nach vollständiger Kürzung bei 105.988 Zeichen — 4,4× über der Grenze | Das ist derselbe Fehler, den Hermes explizit benannt und behoben hat | **Ja, wichtig.** Auftrag 3. |
| **Wie die Zusammenfassung erzeugt wird** | Map-Reduce über Chunks (`_LEAN_DIGEST_CHUNK_CHARS = 72_000`, max 28 Chunks), mit einer harten Regel im Prompt: *„PRESERVE EXACTLY: PR/issue numbers, file paths, function/symbol names, commands, error messages, SHAs, URLs, version numbers, counts. Never paraphrase an identifier."* (`:841`) | Journal-Extraktor, append-only, 5 Few-Shots davon 2 leer, `vorgeschlagen` only. Kein Rolling Summary (bewusst) | Unsere Entscheidung gegen Rolling Summary steht — Hermes' Drift-Problem („Zusammenfassungen von Zusammenfassungen") ist bei uns durch append-only vermieden. **Aber die Identifier-Regel fehlt uns**, und die Knowledge § 2.4 fordert sie genau so (Graphiti: „NEVER generalize ‚Gamecube' zu ‚gaming console'") | **Teilweise.** Rolling Summary: nein. Identifier-Regel in `prompts/journal.md`: prüfen. |
| **Anker-Index** | Mechanisch (nicht per LLM) extrahierte exakte Bezeichner als eigener Block, 7.000 Zeichen Budget (`_LEAN_ANCHOR_HEADING`, `:862-863`) — die Zusammenfassung darf halluzinieren, der Ankerblock nicht | Unser Äquivalent ist der **Arbeitsstand**: mechanisch aus der DB, nie vom Modell geschrieben. Plus Belegzitat-Verifikation (§ 5) | **Wir sind hier gleich gut oder besser** — unser Arbeitsstand ist strukturiert statt regex-extrahiert, und die Zitatprüfung ist serverseitig | Nein, haben wir. |
| **Verlust sichtbar machen** | `context_breakdown.py`: Live-Aufschlüsselung der nächsten Anfrage nach Kategorie (System-Tiers, Tool-Schemata, Rules, Skills, MCP, Memory, Conversation) für UI-Anzeige, mit demselben Char/4-Heuristik wie die Kompressionsschwelle, *„so numbers align with compression thresholds"* | `kontext.umriss()` gibt exakt das — Token je Block, Gesamt, gekürzt ja/nein — aber **nur wenn `protokoll` übergeben wird**, und das passiert *„im Betrieb nie"* (`kontext.py:829`) | **Wir haben das Werkzeug und schalten es im Betrieb ab.** Das ist der billigste offene Gewinn im ganzen Audit | **Ja, sehr billig.** Auftrag 1. |
| **Micro-Compaction** | Laufende Verkleinerung einzelner Tool-Ausgaben zwischen den großen Kompressionen; der Report misst **Occupancy** (wie voll das Fenster gehalten wird), nicht gesparte Token — *„Net tokens saved … is the least interesting figure"* | Kein Äquivalent. Brauchen wir auch nicht: wir haben keine Tool-Ausgaben, und der Prompt wird je Zug neu gebaut | Nicht anwendbar | Nein. |
| **Evals** | `evals/compaction/`: nimmt echte Transkripte, erzeugt Faktenfragen aus der **wegkomprimierten Region**, fährt mehrere Policies, fragt ein frisches Modell nur mit dem Post-Kompressions-Kontext ab und bewertet gegen Gold. Ergebnis: Scorecard *Recall vs. behaltene Token*. Plus eine „Region-scoping tripwire" | Wir messen **Prompt-Größe und Dubletten** (`test_prompt_audit.py`, 20+ Tests) — also die Form, nie den **Recall**. Kein Test fragt: „kann das Modell nach der Kürzung noch beantworten, was vor der Kürzung im Fenster stand?" | **Die größte konzeptionelle Lücke.** Hermes' Kernaussage — miss, was Kompression an *Erinnerung* kostet, nicht was sie an Token spart — haben wir nicht übernommen | **Ja, aber teuer.** Eine kleine Fassung ist machbar (Auftrag 5), nach dem Workshop. |
| **Schwellen-Kopplung** | `native_compaction`: die Server-Schwelle wird *„clamped safely below the local compressor's trigger"* — die zweite Schwelle wird **aus der ersten abgeleitet**, nicht danebengesetzt | `journal.SCHWELLE_VERDRAENGUNG = 2000` und `BUDGETS["fenster"] = 8000` stehen neben `FENSTER_NACHRICHTEN = 20`, ohne Ableitung. Beim Fensterumbau lief das auseinander | **Genau unser Befund C.3.** Hermes leitet ab, wir setzen daneben | **Ja.** Auftrag 2 löst es mit. |
| **Sanitizing am Modell-Ausgang** | `sanitize_memory_context()`: Redaction erzwungen, URL-Credentials raus, Head/Tail-Truncation mit Marker — an der Egress-Grenze zum LLM | Wir haben die PII-Disziplin **im Datenmodell** (nie Aufnahmename ins Modell, `interviewbezeichnung()`; Web schreibt nie Material; Transkripte nur mit `/wortlaut`) | Anderer Ansatz, für unseren Fall besser: wir lassen es gar nicht erst entstehen, statt es am Ausgang zu filtern | Nein, unser Weg ist hier der richtige. |

### B.2 Was hermes-agent hat, das wir bewusst NICHT wollen

Vollständigkeitshalber, damit die Liste oben nicht als Wunschzettel gelesen wird:

- **Rolling/rekursive Zusammenfassung.** Knowledge § 3 und Spec § 2 begründen die
  Ablehnung; Hermes' eigener Code zeigt den Aufwand, der nötig ist, damit sie nicht
  driftet (Anti-Thrashing, iterative Summary-Updates, Fallback-Ketten, Cooldowns —
  mehrere tausend Zeilen). Für zwei Workshoptage ist das die falsche Rechnung.
- **Native Server-Compaction.** An gpt-5.6 und direkte OpenAI-Routen gebunden. Für
  uns ausgeschlossen — nicht technisch, sondern durch die Sovereignty-Regel (E).
- **Plugin-fähige Context-Engine.** Ein Austauschpunkt für etwas, das wir einmal
  bauen und nie austauschen.

---

## C. Messung am Ist-Stand

Alle Zahlen erzeugt am 06.09.2026 gegen **Kopien** von `betrieb/test.db` bzw.
`betrieb/soap.db` (`mode=ro` bzw. Kopie nach `/tmp`), mit
`scripts/erzeuge_prompts.py` und eigenen Messskripten. Keine Transkripte, keine
Nachrichtentexte, keine Namen in diesem Bericht.

### C.1 Prompt-Größen je Pfad

Aus `scripts/erzeuge_prompts.py` gegen die Test-DB im Spätstand (Phase 7):

| Pfad | System (Zeichen) | Nutzer (Zeichen) | Gesamt (Token, ÷3) |
|---|---:|---:|---:|
| `01-gespraech` | 26.365 | 8.810 | **11.724** |
| `02-gespraech-erstkontakt` | 23.354 | 10.060 | 11.137 |
| `03-auftragszug-*` (4 Varianten) | 26.365 | ~22.930 | **~16.430** |
| `04-erkenner` | 31.066 | 8.949 | 13.338 |
| `06-verdichter` | 3.259 | 961 | 1.406 |
| `07-journal` | 5.070 | 7.055 | 4.041 |
| `11-szenenfolge` | 6.094 | 7.241 | 4.444 |
| `13-szene-dialog` | 31.183 | 7.428 | **12.870** |
| `14-feldvorschlag` | 26.365 | 22.953 | 16.439 |

**Befund C.1: Die Systemanweisung ist der größte Block im Prompt und wird von
keiner Grenze erfasst.**

Spec § 6.2 Block 1 setzt für die Systemanweisung **900 Token**. Gemessen:

| Phase | System (Zeichen) | System (Token, ÷3) | Faktor über Spec-Budget |
|---|---:|---:|---:|
| 1 | 23.354 | 7.784 | 8,6× |
| 2 | 28.018 | 9.339 | **10,4×** |
| 3 | 24.867 | 8.289 | 9,2× |
| 4 | 26.096 | 8.698 | 9,7× |
| 5 | 25.891 | 8.630 | 9,6× |
| 6 | 24.202 | 8.067 | 9,0× |
| 7 | 26.365 | 8.788 | 9,8× |

Im gemessenen Gesprächszug: **26.365 Zeichen System gegen 8.810 Zeichen Körper**
— drei Viertel des Prompts sind die Anweisung. Die harte Grenze
`ZEICHEN_GRENZE_VORGABE = 24.000` prüft `_zusammen(bloecke)`, also **nur den
Körper** (`kontext.py:883`). Die Systemanweisung ist von jeder Messung und jeder
Kürzung ausgenommen — und allein schon größer als die gesamte Grenze.

Das ist kein akuter Fehler (Kimi hat 256K Fenster), aber es heißt: **die Zahl,
die wir als „unser Budget" führen, beschreibt ein Viertel des Prompts.** Wer
`ZEICHEN_GRENZE` auf 24.000 liest und glaubt, der Prompt sei ~8.000 Token groß,
irrt um den Faktor 4,4.

### C.2 Was das Fenster jetzt enthält — und wann es leer ist

Gemessen an der Test-DB (129 Nachrichten, 13:15–23:56, 100 nach Systemfilter):

```
Auslöser = jüngste Nachricht (eine Bot-Nachricht, 23:56):
  FENSTER: 0 Einträge, 0 Zeichen
  Körper gesamt: 8.810 Zeichen / 2.936 Token
  Blöcke: kernpaket 260, arbeitsstand 391, figurenhinweis 195,
          szene 1.783, journal 283, fenster 0, ausloeser 19
```

**Befund C.2: Das Fenster ist im gemessenen Zug vollständig leer.**

Ursache: die 20 Kandidaten liegen zwischen 21:53 und 22:32, der Auslöser um
23:56. Die 30-Minuten-Grenze (Bezugspunkt: der Auslöser) schneidet **alle 20**
weg. Der Bot antwortet in diesem Zug mit Arbeitsstand, Kernpaket, Journal und
Szene — **ohne einen einzigen Satz Gesprächsverlauf**.

Das ist die Kehrseite von `b727f09`: `FENSTER_MINUTEN = 30` ist nicht als
Untergrenze abgesichert. Nach jeder Pause über 30 Minuten — Mittagspause,
Nacht, ein Ortswechsel, eine Probe — sieht der Bot beim ersten Zug danach
**keinen Verlauf**. Genau der Fall, für den § 6.2 die Pausenmarkierung
(`[Pause: 18 Stunden]`) erfunden hat: die kann nie erscheinen, weil das, was
vor der Pause lag, vorher schon weggefiltert wurde.

Zum Vergleich mit einem Menschen-Auslöser (der jüngsten Nachricht der Gruppe):

```
  FENSTER: 4.801 Token, Körper 23.187 Zeichen, gekürzt: True
```

Hier greift die Kürzung — der Körper lag vor der Kürzung bei 25.736 Zeichen und
wurde auf 23.187 gebracht. Das funktioniert wie gebaut.

**Zwischenurteil:** Das Fenster ist heute entweder leer (nach Pause) oder
knapp unter der Grenze. Der Zwischenzustand „genau richtig" ist schmal, und er
hängt an einer Zeitdifferenz, nicht an Inhalt.

### C.3 Journal-Extraktor: die Kopplung ist gebrochen

**Befund C.3 — der wichtigste des Audits.**

`journal.berechne_verdraengten_abschnitt()` rechnet mit
`kontext.BUDGETS["fenster"] = 8000` Token (`journal.py:150`). Das reale Fenster
ist seit `b727f09` **20 Nachrichten / 30 Minuten**.

Gemessen an der Test-DB:

```
reales Fenster (letzte 20 Nachrichten):   6.454 Token
Verdrängungsrechnung nimmt an:            8.000 Token
In 8.000 Token passen:                       31 Nachrichten
Real im Fenster:                             20 Nachrichten
```

Der Extraktor hält also **31 Nachrichten für „noch im Fenster"**, während der
Gesprächs-Prompt nur 20 sieht. Die Nachrichten 21–31 sind aus dem Prompt
verschwunden, gelten für den Extraktor aber noch als anwesend — sie werden
**nie journalisiert und stehen nirgends mehr**. Das ist ein Loch von rund 11
Nachrichten breit, das mit jedem Zug mitwandert.

Und der Auslöser springt an den echten Betriebsgruppen von Tag 1 **überhaupt
nicht** an. Gemessen gegen `betrieb/soap.db` (nur Aggregate):

| Gruppe | Nachrichten | Verlauf gesamt (Token) | verdrängter Abschnitt | Extraktor läuft |
|---|---:|---:|---:|---|
| …2879 | 66 | 6.342 | 0 | **nein** |
| …9310 | 52 | 4.780 | 0 | **nein** |
| …6099 | 48 | 4.671 | 0 | **nein** |

Alle drei liegen mit ihrem **gesamten Tagesverlauf** unter dem
Fensterbudget von 8.000 Token. Es kann per Konstruktion nichts verdrängt
werden. Bestätigt durch die Wasserzeichen: `letzte_journalisierte_message_id`
steht bei allen drei Gruppen auf **0** — bei Maximal-`message_id` 94, 79 bzw.
322. Der Extraktor hat an Tag 1 **kein einziges Mal** ein Wasserzeichen
vorgerückt.

Und im Journal der Betriebs-DB steht entsprechend:

```
BETRIEB Journal nach Quelle: knopf/entschieden 1, regie/entschieden 3
```

**Vier Einträge insgesamt, kein einziger aus dem Extraktor, kein einziger
`vorgeschlagen`.** Die gesamte Kategorie, für die dieser Mechanismus gebaut
wurde und für die die Knowledge-Recherche § 6–8 die Prompts entworfen hat,
ist an Tag 1 leer geblieben.

Zur Kontrolle die Test-DB (die einen längeren, dichteren Verlauf trägt):

```
Test-DB Journal: extraktor/vorgeschlagen 4, szene/entschieden 5,
                 regie/entschieden 3, knopf/entschieden 2,
                 befehl/entschieden 1, erkenner/entschieden 1
unjournalisiert: 61 Nachrichten / 10.497 Token -> verdrängt 19 -> läuft: ja
```

Dort springt er an — aber erst, nachdem sich **61 unjournalisierte Nachrichten
(10.497 Token)** angesammelt haben. Die Vermutung aus dem Auftrag („er springt
jetzt entweder ständig oder nie an") trifft also die zweite Hälfte: **er
springt viel zu spät an oder gar nicht.**

**Antwort auf „landen Entscheidungen aus Freitext irgendwo?"** — Teilweise, und
nicht auf dem geplanten Weg. Was ankommt, kommt von **Knöpfen und Befehlen**
(`quelle = knopf/regie/befehl/szene`), also aus mechanisch eindeutigen
Ereignissen. Was der Erkenner aus Freitext liest, ist genau **ein** Eintrag in
der Test-DB (`erkenner/entschieden 1`) und **null** im Betrieb. Freitext-
Entscheidungen landen im Wesentlichen **nirgends** — sie stehen im Chat, bis
sie aus dem Fenster fallen, und dann sind sie weg.

Das deckt sich mit dem Befund in `AGENTS.md` (Z. 80–84): der Erkenner ist
zuverlässig, *wenn er das ganze Gespräch sieht (3/3)* — live sieht er ein
Fenster von 1–3 Nachrichten und schrieb im entscheidenden Moment
`entschieden` (Journalnotiz) statt `kernthema_setzen` (Arbeitsstand). Beide
Extraktionswege — Erkenner (zu kurzes Fenster) und Journal-Extraktor (zu
später Auslöser) — verfehlen dieselbe Sache aus entgegengesetzten Richtungen.

### C.4 Wann die Kürzung greift — und wann sie ihr Ziel verfehlt

Künstlich aufgebläht (Szenen-Volltext vervielfacht, gegen eine Kopie):

**Szene ×8:**
```
vorher 61.863 Zeichen -> nach Kürzung 44.056 Zeichen  (Grenze 24.000)
Blöcke danach: kernpaket 260, arbeitsstand 391, figurenhinweis 195,
               szene 13.826, ausloeser 9
               fenster 0, journal 0, verdichtungen 0
Vorfall: "Nutzertext von 61863 auf 44056 Zeichen gekuerzt
          (Grenze 24000, Ziel 20000 Token)"
```

**Szene ×20:**
```
nach vollständiger Kürzung: 105.988 Zeichen  — 81.988 Zeichen ÜBER der Grenze
Blöcke danach: kernpaket 260, arbeitsstand 391, figurenhinweis 195,
               szene 34.470, ausloeser 9
```

**Befund C.4: Die Kürzung opfert Fenster, Journal und Verdichtungen
vollständig — und erreicht ihr Ziel trotzdem nicht.**

Die Kürzungsleiter hat vier Stufen (Transkripte, Fenster, Journal,
Verdichtungen). Alle vier laufen durch, alles Opferbare ist geopfert, und der
Prompt ist immer noch 4,4× zu groß, weil der **Szenenblock von der Kürzung
ausgenommen** ist (`kontext.py:896-898`: *„Nie angetastet: Kernpaket,
Arbeitsstand, Hinweise, aktuelle Szene und die auslösende Nachricht"*).

Zwei Folgen:

1. **Der Bot verliert bei einer langen Szene seinen gesamten Gesprächsverlauf
   und sein Journal** — genau in Phase 6/7, wo die Gruppe an Szenen arbeitet
   und Korrekturen zuruft. Er behält die Szene, die er ohnehin gerade schreibt,
   und verliert das, was die Gruppe dazu gesagt hat. Das ist die Umkehrung der
   gewünschten Priorität.
2. **Der Vorfall meldet die Kürzung als erfolgt**, ohne zu vermerken, dass sie
   ihr Ziel verfehlt hat. Auf dem Dashboard steht „gekürzt", nicht „reicht
   nicht". Das ist exakt der Fall, für den hermes-agent
   `should_compress_info()` mit Grund-Rückgabe gebaut hat (*„Without this
   signal an over-threshold session fails opaquely."*).

Wie realistisch? `CONTINUITY_ZEICHEN_MAX` deckelt den Szenenpfad, aber
`kontext._baue_szene` (Gesprächspfad) hat **keinen Deckel** — er nimmt
`szene["volltext"]` wie er ist. Eine überarbeitete Szene mit 6.000 Wörtern
oder ein Modell-Ausrutscher genügt. Bei ×8 (44K Zeichen) ist der Prompt noch
funktionsfähig, aber Fenster und Journal sind weg — das passiert schon bei
einer ungewöhnlich langen, nicht bei einer absurden Szene.

### C.5 Der Divisor und die fehlende Rückkopplung

Spec § 7.1 verspricht: jeder Aufruf schreibt `geschaetzte_token` und die echte
`usage.prompt_tokens` in `aufruf`, *„Nach zwanzig Aufrufen am Samstagvormittag
ist das echte Verhältnis bekannt und der Divisor anpassbar. Das Dashboard zeigt
die Drift."*

Gemessen gegen `betrieb/soap.db`:
```
select ... from aufruf ...  ->  no such column: prompt_tokens
```

**Die Spalte existiert nicht.** Der Rückkopplungspfad ist nie gebaut worden.
Der Divisor 3 ruht auf einem einzigen Rauchtest vom 04.09. (983 Zeichen → 337
Token = 2,92, § 12 „bestätigt"). Für deutsche Texte mit Namen, Zahlen und
Telegram-Formatierung ist eine einzelne Messung dünn — und weil unsere harte
Grenze in **Zeichen** gesetzt ist, hängt die Übersetzung dieser Grenze in
Token, die wir dem Modell zumuten, allein an dieser einen Zahl.

Nicht dringend (die Zeichengrenze wirkt auch mit falschem Divisor), aber die
Spec behauptet eine Selbstkorrektur, die es nicht gibt.

### C.6 Vorfälle im Betrieb

```
BETRIEB: http_5xx 13, zitat_ungeprueft 1
TEST:    http_5xx 13
```

Kein einziger `kontext_gekuerzt` — konsistent damit, dass die harte Grenze erst
seit `4e0f309` (06.09. 01:03) existiert und die Betriebsgruppen ohnehin klein
sind. Kein `journal_extraktor_fehler` — der Extraktor ist nie gelaufen, also
konnte er auch nicht scheitern. **Die Vorfall-Tabelle zeigt Fehler, aber keine
ausbleibende Mechanik.** Ein Mechanismus, der nie läuft, ist im Dashboard nicht
von einem unterscheidbar, der läuft und nichts findet.

---

## D. Urteil: Haben wir die bestmögliche Version?

**Nein.** Wir haben eine deutlich bessere Version als vor zwölf Stunden — die
drei gemeldeten Fehler sind echt behoben, und die Fixes sind richtig gebaut
(chronologisch nach `gesendet_am`, harte Grenze, Dedupe an vier Stellen,
Prompt-Audit-Tests). Aber die Reparatur war **lokal an den gemeldeten
Symptomen** und hat die gemeinsame Ursache nicht getroffen: *Grenzen, die nur
einen Teil des Prompts bemessen, und Schwellen, die nebeneinander statt
voneinander abgeleitet gesetzt sind.*

Der Fensterumbau hat einen Fehler behoben und dabei zwei neue Zustände erzeugt
(leeres Fenster nach Pause C.2, gebrochene Extraktor-Kopplung C.3), weil die
Konstante geändert wurde, ohne den zu suchen, der von ihr abhängt.

### Die fünf Aufträge, priorisiert

#### VOR dem Workshop (13:30) — zusammen ≤ 2 h, gering riskant

---

**Auftrag 1 — Umriss im Betrieb mitschreiben (Sichtbarkeit vor Reparatur)**

*Warum zuerst:* Am Workshoptag ist die wichtigste Fähigkeit, einen Fehler
**sehen** zu können, während er passiert. `kontext.umriss()` liefert genau das
und ist gebaut — es wird nur nicht gerufen (`kontext.py:829`: „im Betrieb nie
gesetzt"). hermes-agent hat dafür ein eigenes Modul (`context_breakdown.py`)
gebaut; wir müssen einen Parameter durchreichen.

*Was:* In `bot.py` beim Gesprächszug eine Liste an `kontext.baue(...,
protokoll=...)` übergeben und das Ergebnis als Zeile in `aufruf` oder als
Log-Zeile schreiben (Token je Block, gesamt, gekürzt ja/nein). Zusätzlich einen
zweiten Vorfalltyp `kontext_kuerzung_erfolglos`, wenn nach der Kürzung noch
über der Grenze (C.4) — hermes-agents `should_compress_info`-Lektion, 5 Zeilen.

*Aufwand:* 45 min. *Risiko:* sehr gering — rein additiv, kein Pfad ändert sich.
*Test:* `test_prompt_audit.py`: ein Zug schreibt eine Umriss-Zeile mit allen
Blocknamen; ein künstlich zu großer Prompt schreibt `kontext_kuerzung_erfolglos`.

---

**Auftrag 2 — Fenster tokenbemessen, Extraktor daran koppeln, Untergrenze**

*Warum:* Löst C.2 und C.3 in einem Griff, und stellt Spec § 6.2 wieder her
(„in Token statt Nachrichten bemessen"). hermes-agent hat dieselbe Entscheidung
in dieselbe Richtung getroffen (Token-Budget statt fester Nachrichtenzahl,
`context_compressor.py:13`) und leitet die zweite Schwelle aus der ersten ab
(`native_compaction`).

*Was, konkret:*
1. `FENSTER_ZEICHEN = 12_000` (≈ 4.000 Token) als **primäres** Maß einführen;
   das Fenster wird von hinten gefüllt, bis das Budget voll ist.
2. `FENSTER_NACHRICHTEN = 20` bleibt als Obergrenze; `FENSTER_MINUTEN = 30`
   wird zu einer **weichen** Grenze mit Untergrenze: mindestens die letzten
   `FENSTER_MIN_NACHRICHTEN = 6` Nachrichten bleiben **immer** im Fenster, auch
   wenn sie älter als 30 Minuten sind. Damit kann das Fenster nie leer sein und
   die Pausenmarkierung funktioniert wieder wie in § 6.2 vorgesehen.
3. `journal.berechne_verdraengten_abschnitt` rechnet nicht mehr gegen
   `BUDGETS["fenster"]`, sondern **gegen genau dasselbe Maß, das
   `_baue_fenster_eintraege` benutzt** — am besten, indem `kontext` eine
   Funktion `fenster_grenzen()` exportiert, die beide lesen. Eine Quelle, wie
   bei den Fakten im Prompt.
4. `SCHWELLE_VERDRAENGUNG` von 2.000 auf **600 Token** senken (bezog sich auf
   ein 8.000er Fenster; bei einem 4.000er ist 2.000 die Hälfte des Fensters).

*Aufwand:* 60–75 min. *Risiko:* mittel-gering — berührt zwei Module, aber beide
haben Tests. **Nicht parallel zum Szenen-Agenten mergen**, der am Prompt-Budget
arbeitet: erst dessen Branch, dann dieser.
*Test:* (a) Fenster nach 18 h Pause enthält ≥ 6 Nachrichten und eine
Pausenzeile; (b) ein Regressionstest, der `fenster_grenzen()` in
`kontext._baue_fenster_eintraege` und `journal.berechne_verdraengten_abschnitt`
vergleicht und fehlschlägt, wenn sie auseinanderlaufen (die Testlücke, die C.3
verursacht hat); (c) gegen eine Fixture mit dem Volumen von Tag 1 (≈ 60
Nachrichten / 6.000 Token) muss der Extraktor **mindestens einmal** anspringen.

---

#### NACH dem Workshop

---

**Auftrag 3 — Szenenblock deckeln, Kürzung garantiert wirksam machen**

*Warum:* C.4. Der einzige unbegrenzte Wachstumspfad im Gesprächs-Prompt, und
die Kürzung kann ihr Ziel heute nicht garantieren. hermes-agent hat genau
diesen Fehler benannt und behoben (`LEAN_TAIL_CAP_TOKENS`, plus Demotion
*innerhalb* des geschützten Tails: *„This is what lets the tail budget actually
bind"*).

*Was:* `SZENE_ZEICHEN_MAX` (Vorschlag 6.000) in `kontext._baue_szene`; bei
Überschreitung Anfang + Schluss der Szene mit Auslassungsmarke, wie
`szene._gekuerzter_volltext` es bereits kann. Zusätzlich: eine fünfte
Kürzungsstufe, die den Szenenblock kürzt, **bevor** Journal und Verdichtungen
fallen — die Reihenfolge in `kontext.py:889-898` ist heute falsch herum, weil
sie den größten Block schützt und die kleinsten opfert.

*Aufwand:* 1,5 h. *Risiko:* mittel — ändert, was der Bot in Phase 6/7 sieht.
Nicht vor dem Workshop.
*Test:* Prompt mit ×20-Szene bleibt nach Kürzung **unter** der Grenze; Fenster
und Journal überleben eine überlange Szene.

---

**Auftrag 4 — Systemanweisung in die Messung aufnehmen**

*Warum:* C.1. Drei Viertel des Prompts sind heute unbemessen; die Zahl, die wir
„Budget" nennen, beschreibt ein Viertel. Nicht akut (256K Fenster), aber jede
weitere Budget-Entscheidung ruht auf einer falschen Grundlage, und Phase 2
liegt mit 9.339 Token 10,4× über dem Spec-Budget.

*Was:* (a) `zeichengrenze()` und `_zu_lang()` messen System **+** Körper, mit
entsprechend angehobener Grenze (Vorschlag 40.000 Zeichen gesamt, davon
Körper ≤ 24.000). (b) Ein Test, der je Phase die Systemgröße festhält und bei
Überschreitung von z. B. 30.000 Zeichen fehlschlägt — damit `prompts/phasen/*.md`
und `system.md` nicht unbemerkt weiterwachsen. (c) Spec § 6.2 Block 1 von 900
auf den realen Wert korrigieren oder die Anweisung kürzen; die Diskrepanz von
Faktor 10 gehört aufgelöst, nicht fortgeschrieben.

*Aufwand:* 1 h. *Risiko:* gering. *Test:* wie beschrieben.

---

**Auftrag 5 — Recall-Messung statt nur Größenmessung**

*Warum:* Die größte konzeptionelle Lücke gegenüber hermes-agent (B, letzte
Zeile). Unsere 20+ Prompt-Audit-Tests messen **Form** (Größe, Dubletten,
Reihenfolge) — keiner misst, **was das Modell nach der Kürzung noch weiß**.
Hermes' `evals/compaction/` erzeugt Faktenfragen aus der wegkomprimierten
Region und bewertet Recall gegen Token. Genau diese Frage haben wir nie
gestellt, und genau sie hätte C.2 und C.3 vor dem Einsatz gefunden.

*Was, klein geschnitten:* Ein Skript `scripts/kontext_recall.py`, das gegen
eine Fixture-DB (a) einen Prompt vor und nach der Kürzung erzeugt, (b) 10
mechanisch ableitbare Faktenfragen aus dem **weggefallenen** Teil stellt
(„welches Kernthema wurde gesetzt", „welche Figur hat Quelle-Interview N" —
alles Dinge, die im Arbeitsstand stehen und deshalb *überleben müssten*), und
(c) ausgibt, welche davon der Post-Kürzungs-Kontext noch beantwortbar macht.
**Ohne LLM in der ersten Fassung** — reine Textprüfung „steht die Antwort noch
im Prompt". Das findet 80 % der Fälle und kostet nichts.

*Aufwand:* 3–4 h. *Risiko:* keins (kein Betriebscode). Als
Regressionsschutz für jede künftige Budgetänderung.

---

### Nicht empfohlen

- **Rolling Summary / Verdichtung des Verlaufs.** Spec § 2 und Knowledge § 3
  begründen die Ablehnung; hermes-agents Code zeigt, was an Absicherung nötig
  wäre, damit es nicht driftet. Bleibt richtig.
- **Tokenizer einführen.** § 7.1 bleibt gültig. Die Zeichengrenze ist das
  robustere Maß, solange sie *alles* misst (Auftrag 4).
- **Wichtigkeits-Score fürs Journal.** Knowledge § 2.2 findet keinen Beleg;
  wir geben ohnehin alle Einträge mit.

---

## E. Birks Frage: „Hätten wir hermes-agent als Instanz nehmen sollen?"

**Nein — und die heutigen Fehler sind kein Gegenargument.**

1. **Die Sovereignty-Regel schließt es aus.** Der Bot verarbeitet Rohmaterial
   von Laiendarstellerinnen: Sprachaufnahmen, Transkripte, Erlebnisse aus
   Interviews. Für diese Daten gilt: keine US-Cloud. Der Bot läuft deshalb auf
   Infomaniak (CH), und die USA-Einwilligung ist ein **eigener Knopf** mit
   eigenem Datenfeld (`AGENTS.md` Z. 87), das die Weboberfläche nie ändern darf
   (Z. 714). hermes-agent als Laufzeit hätte den Verlauf durch eine
   Compaction-Kette geschickt, die an ein Sprachmodell unserer Wahl geht —
   technisch lösbar, aber die Trennlinie „Rohdaten CH, Szenen mit Einwilligung
   Opus" wäre kein Datenmodell mehr, sondern eine Konfigurationszusage. Wir
   haben sie heute im Schema.

2. **Multi-Gruppen.** Hermes' Kontext-Engine kennt eine Sitzung. Wir fahren
   drei bis vier Telegram-Gruppen gleichzeitig aus **einer** SQLite, mit
   getrennten Wasserzeichen, Phasen und Journalen je `chat_id`. Das ist keine
   Sitzung mit mehreren Nutzern, das sind mehrere Werkstücke.

3. **Telegram-Gruppen sind kein Agentenlauf.** Wir haben keine Tool-Ausgaben,
   kein Rollenwechselproblem, keine Tool-Call-Paare — die Hälfte von
   `context_compressor.py` (7.858 Zeilen) löst Probleme, die wir gar nicht
   haben. Unsere Aufgabe ist umgekehrt: aus einer Datenbank je Zug einen
   frischen Prompt **bauen**, nicht eine wachsende Liste **schrumpfen**.

4. **Deterministische Garantien.** Unser Prompt ist bei gleichem DB-Stand
   bitgleich reproduzierbar — deshalb konnte ich dieses Audit überhaupt messen
   (`scripts/erzeuge_prompts.py` gegen eine Kopie). Eine Compaction-Kette mit
   LLM-Zusammenfassungen ist das nicht. Für ein Werkzeug, das an einem
   Workshoptag ohne Netz-zum-Debuggen funktionieren muss, ist Reproduzierbarkeit
   mehr wert als Cleverness.

5. **Was es gebracht hätte, ehrlich:** Die drei Nachtfehler wären so nicht
   passiert — Hermes bemisst den Tail in Token (nicht in Nachrichten),
   sortiert nie nach einer Stellvertreter-id, und macht die Zusammensetzung
   des Prompts sichtbar (`context_breakdown.py`). **Das sind aber genau die
   drei Disziplinen, die wir jetzt in ≤ 2 h nachziehen können** (Aufträge 1
   und 2) — nicht die Laufzeit, sondern die Sorgfalt. Der Preis wären
   Sovereignty, Multi-Gruppen und Testbarkeit gewesen: ein schlechter Tausch
   für drei Fehler, die eine Nachmittagsschicht kosten.

**Fazit:** Die richtige Lehre ist nicht „falsche Laufzeit", sondern *„wir haben
die Messdisziplin nicht mitgebaut"*. Hermes' wertvollster Beitrag zu diesem
Projekt ist nicht sein Code, sondern seine `evals/compaction/`-Frage: **miss,
was die Kürzung an Erinnerung kostet, nicht was sie an Token spart.** Die
haben wir nie gestellt. Auftrag 5 stellt sie.
