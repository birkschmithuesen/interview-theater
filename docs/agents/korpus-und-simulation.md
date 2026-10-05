# Korpus und Simulation

> Ausgelagert aus `AGENTS.md` am 05.10.2026 (Stand `cb200e4`, Zeilen 3325–3520 und 1600–1801).
> Wortlaut unveraendert; Index und Kurzfassung stehen in `AGENTS.md`.

### Prompt geändert? → Korpus laufen lassen

Die fünf Prompts werden heiß nachgeladen, also ändert sie jemand **während**
des Workshops. Der Regressionskorpus unter `korpus/` ist das Gegenmittel gegen
den Blindflug: 150 Absichtserkenner-Fälle (davon 53 Negativfälle; darunter
11 aus einer laufenden Aufnahme — `aufnahme` statt `nachrichten`, N1 —, und
20 mit `zustimmung: true` markiert, N7; Stand 30.09.2026, alle `art`-Werte
mindestens zweimal, `szene_planen` mit Szenenbezug), 22 Journal-Abschnitte
(davon 11 leere), 7 erfundene Interviewtranskripte — darunter einer, dessen
Sollwert **null** Kernthemen sind (der Live-Fall aus dem Probelauf, N2) —
und 5 Sprachprofil-Fälle (T3, eine je Sprechweise: kurze Sätze mit
Selbstkorrektur, Code-Switching, „man"-Distanz, Reihungen, Rückfragen), alle
mit Sollwert.

(Stand 30.09.2026 nachgemessen — die Zahlen davor waren seit dem 05.09. nicht
mitgewachsen. Wer Fälle ergänzt, zählt mit
`python3.11 -c "import json; f=[json.loads(l) for l in open('korpus/erkenner.jsonl') if l.strip()]; print(len(f), sum(1 for x in f if not x['erwartet']))"`
nach, statt zu schätzen.)

Seit dem 30.09.2026 dazu `szene_kuerzen` mit `sk01`/`sk02` (positiv, beide
`zustimmung: true`) und `sk03`–`sk05` (negativ) — die Art liegt direkt neben
n20, n27 und fl04, und
`tests/test_korpus.py::test_erkenner_haelt_die_laengengrenzfaelle` hält deren
Sollwerte fest.

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m scripts.pruefe_prompts erkenner             # nach einer Änderung an erkenner.md
python -m scripts.pruefe_prompts alle --bericht       # vollständig, mit Markdown-Bericht
python -m scripts.pruefe_prompts erkenner --nur e18-verworfen-kindheitsfragen
python -m scripts.pruefe_prompts erkenner --modell <anderes>   # Modellvergleich
```

**Kein Test, läuft nie automatisch, kostet Rappen** — wie `rauchtest.py`. Rund
70 Aufrufe für `alle`, sequenziell (Infomaniak liefert bei Parallelität
429/5xx). Der Lauf schreibt seine `aufruf`- und `vorfall`-Zeilen in eine
Wegwerf-Datenbank, nie in `IT_DB`.

> **Die Regel: eine Änderung am Erkenner-Prompt gilt nur, wenn FP = 0 bleibt.**
> Null Falsch-Positive bei 25 Negativfällen ist die Zahl, die den Erkenner
> qualifiziert und die acht nicht gebauten Befehle begründet hat (SPEC § 4.3a,
> § 8.1). Genau das ist deshalb der Exit-Code: das Skript endet mit 1, sobald
> der Erkenner auch nur ein Falsch-Positiv liefert.
>
> **Was FP heißt, hat sich am 05.09.2026 gedreht (N7) — die Zahl nicht.** Ein
> Falsch-Positiv ist jetzt: ein Eintrag, dem im Abschnitt **kein konkreter
> Vorschlag und keine Zustimmung** vorausgeht. Ein Eintrag *nach* einer
> Zustimmung ist keiner mehr, auch wenn sie beiläufig war („passt", „nehmen
> wir", „das können wir so fix machen"). Grund: seit es weiches Löschen und
> `transkript_korrigieren` gibt, ist ein falscher Eintrag billig — ein Satz der
> Gruppe nimmt ihn zurück —, ein fehlender teuer: die Website bleibt leer, der
> Bot weiß nichts davon, und die Gruppe muss alles noch einmal sagen. Im
> Probelauf stimmte sie dreimal zu (Fragen, Kernthema, drei Figuren), und
> dreimal blieb der Arbeitsstand leer. **Das Prüfskript rechnet dafür nicht
> anders — es sind die Sollwerte im Korpus, die sich gedreht haben.** Daneben
> steht seither eine zweite Kennzahl (nicht im Exit-Code): **Falsch-Negative in
> Zustimmungsfällen**, Korpusfeld `zustimmung`, soll ebenfalls 0.
>
> Zwei Arten bleiben auf „im Zweifel kein Eintrag" kalibriert:
> `szene_schreiben` (kostet zwei Minuten Wartezeit und eine unbestellte
> Nachricht) und `entfernen` (nimmt etwas weg).

Berichte landen in `korpus/berichte/` und sind **gitignored**: sie enthalten
vollständige Modellantworten. Der Korpus selbst ist frei erfunden und gehört
ins Repository.

**Die Zahlen des Laengen-Rhythmus und des Sprachpasses sind kein Prompt.**
Sie stehen in `workshop/padua-2026/profil.toml` (`[laengen]`,
`[laengen.rahmen]`, `[sprachpass]`). Eine Aenderung dort braucht **keinen**
Korpuslauf und **keinen** Neustart des Webdienstes, aber einen Neustart des
Bots: die TOML wird nur beim Start gelesen (siehe "Workshop-Profil").

### Simulation: ein ganzer Workshop gegen die echten Modelle

Der Korpus misst einzelne Prompts an einzelnen Fällen. Was er **nicht** misst,
ist der Zusammenhang: ob eine Gruppe mit diesem Bot von einer Begriffsliste zu
einem Szenentext kommt, ob Zustimmungen ankommen, ob der Bot behauptet, etwas
notiert zu haben, das nirgends steht. Genau dafür gibt es
`scripts/simulation.py` (Details in [simulation/README.md](simulation/README.md)).

Simulierte Teilnehmerinnen arbeiten sich durch die Schritte einer
Skriptliste. `skript.SCHRITTE` ist der Ablauf vom 05.09.2026 und die
Messlatte der damaligen Verlaufszeilen (zehn Schritte, keine Phasenwechsel);
`skript.SCHRITTE_TAG2` faehrt die heutigen **sieben** Phasen, und seit dem
30.09.2026 waehlt der Schalter `--skript tag2` es auch fuer die erfundenen
Sets 1–3 — vorher war es an `--set tag1-*` gebunden, und damit fuhr kein
erfundenes Set die Phasen 4 bis 7 ueberhaupt an. Gefahren wird **derselbe Codepfad wie im Betrieb**
(`bot.verarbeite_update`, `bot._zug_und_erkenner`), nur mit einer
Telegram-Attrappe statt Netz und einer Wegwerf-Datenbank statt `IT_DB`. Der
Umweg über Telegram ist gar nicht möglich: Telegram liefert Bot-Nachrichten
nie an andere Bots (Bot-FAQ). Interviews kommen als Text
(`aufnahme.importiere_text`, § 10.5), kein Whisper.

**Zwei Modelle, eine Trennlinie.** Alles, was der Bot tut, läuft über
Infomaniak — er ist der Prüfling. Alles, was Simulation ist (die Stimmen, der
Richter, die einmalige Erzeugung der fünfzehn Interviewdatensätze), läuft über
**Claude Opus** an einem lokalen Proxy (`simulation/claude.py`,
`IT_SIM_URL`/`IT_SIM_MODELL`, Anthropic-Messages-Format, kein
Authorization-Header). Ohne diese Trennung würde der Prüfling seine eigenen
Teilnehmerinnen spielen und sich anschließend selbst benoten. Die
Simulationsseite läuft über ein Abonnement und kostet je Aufruf nichts — die
Kostenzeile im Bericht ist deshalb genau das, was ein Workshoptag zahlen
würde.

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m scripts.simulation --set 1 --seed 7 --bericht
python -m scripts.simulation --mix 1,2,3 --seed 3
python -m scripts.simulation --set 1 --seed 1 --ohne-szene   # ohne Reasoning-Lauf
python -m scripts.simulation --set birk --bericht            # echtes Material, ~10 min
python -m scripts.simulation --alle                          # Sets 1-3 und birk
```

**Die Stimmen sind Personen, keine Sprachstile** (Gülten 58, Dilan 24,
Halyna 41 — Steckbriefe in `simulation/stimmen/*.md`, je mit einem eigenen
Ziel im Workshop). Wer dem Computer am wenigsten traut, schreibt am
seltensten; der `--seed` variiert nur, wer wann spricht.

**`--set birk` ist die Messlatte:** das einzige Set auf echten Daten (Birks
Testinterview vom 04.09., eine Stimme, kalibriert auf seinen echten
Chatverlauf). Gemessen wird die **Navigation**, nicht der Text — der Bericht
stellt neben jede Zahl die aus dem echten Chat. Der Lauf schreibt drei Szenen
in drei Formen (Dialog, Lied, Rap) und verbietet deshalb `--ohne-szene`. Das
Material liegt außerhalb des Repositories (`IT_SIM_BIRK`).

**Was sie misst.** Mechanisch, ohne Modell: erreichte Phase, Vollständigkeit
des Arbeitsstands, Anteil der Zustimmungen, nach denen wirklich eine
Notiert-Zeile kam (die Kennzahl aus N7), Verdichtungen und geprüfte
Belegzitate, Echo (`ablauf.ist_echo`), Rückfragen vor dem Szenenauftrag,
**behauptete Schreibvorgänge** (Bot sagt „notiert", ohne dass der Erkenner
etwas geschrieben hat — Soll 0), Namensanrede, Medianlänge der Bot-Antworten
(Soll < 700 Zeichen), Kosten und Dauer. Dazu bewertet ein Richter (Opus)
jeden Abschnitt mit 0/1/2 auf vier Kriterien und jeden Szenentext auf drei
weitere.

**Und die zwei Hintergrundwege, die entscheiden, was der Bot weiß.** Das
**Journal**: Einträge je Art, wie viele davon der Richter im Chat
wiederfindet, welche Vorschläge fehlen, Doppeleinträge — und ob der Extraktor
überhaupt lief (er läuft nur bei Verdrängung; sonst steht „Journal nicht
ausgelöst" statt einer Null, `--fenster-klein` provoziert sie). Der
**Kontextaufbau**: `kontext.baue(..., protokoll=list)` schreibt je Prompt mit,
welcher Block mit wie vielen Token drin stand; der Bericht zeigt die
Verteilung, die Prompts über `ZIEL`, die mit Kürzung — und bei den fünf
schwächsten Antworten urteilt der Richter am Block-Umriss, ob dem Bot
Information gefehlt hat, die in der DB stand. Dazu ein Skript-Schritt
**Zitatabfragen** mit der mechanischen Kennzahl `zitat_erfunden` (Soll 0).

Dazu seit dem 30.09.2026 die zwei Kennzahlen der Gegenpruefung, beide
mechanisch: **`festlegungsproben_erhalten`** (Soll: alle — von drei
Pruefsaetzen, die in kein Arbeitsstandfeld passen, muss jeder dauerhaft
liegen; das Journal zaehlt dabei **nicht**, es wird auf acht Zeilen gekappt)
und **`szenenfolge_nach_richtung`** (Soll 0 — nach einer gedrueckten
Geschichte-Richtung darf kein frischer Szenenfolge-Vorschlag laufen, er
ueberschreibt die Titel der Gruppe und kostet 110 s; in den Laeufen vom
30.09.2026 konnte sie noch nie anschlagen, weil die Richtungswahl in keinem
Lauf erreicht wurde). Beide sind entstanden, weil die Simulation die zwei
belegten Dortmunder Fehler vom 06.09.2026 vorher nicht benennen konnte; was
sie heute findet und was nicht, steht in
`docs/simulation-gegenpruefung-2026-09-30.md`.
`simulation/mutation.py` baut sie auf Knopfdruck wieder ein
(`--mutation`) — per Monkey-Patch aus `simulation/` heraus, kein
Produktivcode und keine Weiche darin; `tests/test_simulation_mutation.py`
haelt fest, dass die Mutation den Fehler wirklich erzeugt, und muss vor jedem
bezahlten Lauf gruen sein.

**Kein Test, läuft nie automatisch, kostet Geld** — wie `pruefe_prompts.py`
und `rauchtest.py`, nur eine Größenordnung mehr: ein voller Lauf sind einige
hundert Aufrufe, grob 0,20–0,60 CHF für den Bot (die Stimmen und der Richter
laufen über das Abonnement und kosten nichts), dazu ein Szenenlauf mit
Reasoning (2–4 Minuten, der teuerste Einzelposten — `--ohne-szene` spart
ihn). Sequenziell; bei 429 wartet das Skript und wiederholt, wie
`pruefe_prompts`.

> **Die Regel: nach jeder Prompt-Änderung ein Lauf mit `--set` und einer mit
> `--mix`.** Der erste hält den Themenkreis fest und macht zwei Läufe
> vergleichbar; der zweite mischt drei Themenkreise und zeigt, was nur an
> einem Set hing. Beide mit demselben Seed wie beim letzten Mal, sonst
> vergleicht man Besetzungen statt Prompts.

Transkript (`simulation/laeufe/`) und Bericht (`simulation/berichte/`) sind
**gitignored** — sie enthalten vollständige Modellantworten. Die eine
Ausnahme ist `simulation/berichte/verlauf.jsonl`: eine Zeile je Lauf mit allen
Kennzahlen und dem git-HEAD, der Vergleichsmaßstab zwischen zwei
Prompt-Ständen. Die fünfzehn Interviewtranskripte unter
`simulation/interviews/` sind frei erfunden und gehören ins Repository —
geschrieben hat sie einmal `simulation/erzeuge_interviews.py` mit Opus, das
**Ergebnis** ist das Artefakt, nicht das Skript.

Der Simulator ist **datengetrieben** gebaut: Phasen aus `phasen.PHASEN`,
Arbeitsstandfelder aus `PRAGMA table_info(arbeitsstand)`, das Wort „Notiert:"
aus `erkenner.baue_meldung`. Ein Umbau an Phasen oder Feldern soll ihn nicht
mitreißen — wer trotzdem etwas anpassen muss, findet die Stellen in
`simulation/skript.py`.

Beim Erweitern: `wert` im Erkenner-Korpus ist der **Kern** der Sache
(`"Meryem"`, `"Mutter gegen Tochter"`), nicht der erwartete Wortlaut —
verglichen wird als Teilstring in beide Richtungen, ein leerer `wert` prüft
allein die `art`. `erwartet[].text` im Journal-Korpus ist ein
**Muss-Stichwort-Set**, mit `|` getrennt (`"sechs|fragen"`), ebenfalls kein
Wortlaut. `tests/test_korpus.py` prüft Form und Mindestbesetzung mit, ohne
Netz.

### Invarianten der Browser-Simulation

**Zweck:** Die Padua-Browsersimulation (`simulation/browser_lauf.py`) soll
Live-Symptome finden, ohne dass jemand sie wegerklärt. Nach jeder Station
laufen deterministische Prüfungen (`simulation/browser_invarianten.py`,
`browser_pruefhaken.py`), ohne Modell. Jede Verletzung ist ein Befund `hoch`
mit der Ursache `App oder Werkzeug – ungeklaert`.
**Befund-Schlüssel:** `board_leer_nach_ende`, `board_nicht_nachgezogen`,
`board_beobachter_leer`, `stille_nach_leerem_ende`, `stille_nach_ende`,
`werkbank_leer_phase2_gesperrt`, `chat_kennt_board_nicht`,
`chat_nennt_board_nicht`, `chat_kennt_transkript_nicht`,
`raumcheck_domainweit`, `verhoerer_nicht_korrigiert` (mittel),
`p2_fragen_fehlen`, `station_nicht_erreicht:<station>`. Dazu kommt
`pruefung_gescheitert:<haken>`: Das Werkzeug ist gescheitert, nicht die App.
**Lauf:** `--stationen invarianten` (zwei Gruppen, drei gesprochene
Diskussionen, Wissensfrage). `--app-wurzel <checkout>` startet Web, Bot und
Prompt-Abzug aus einem anderen Stand, z. B. cb200e4. Danach vergleicht
`python -m simulation.browser_abnahme vergleich --vorher <lauf> --nachher
<lauf> --ausgabe <md>` die sechs Abnahmezeilen. Bericht und Ergebnis vom
05.10.2026: `simulation/berichte/sim-invarianten-2026-10-05.md`.
**Symptomregel:** Ein Symptom gilt als App-Fehler, bis das Gegenteil belegt
ist. Ändert sich ein Befund, muss das an der Prüfung liegen und mit einem Test
belegt sein. Der Schlüssel wird nie still gestrichen.
