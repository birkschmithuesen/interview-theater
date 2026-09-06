# Simulation

Ein kompletter Workshop, gefahren gegen den echten Bot-Code und die echten
Modelle. Drei simulierte Teilnehmerinnen arbeiten sich durch neun Schritte --
Begriffe, Fragen, fuenf Interviews, Kernthema, Figuren, Phase 5 (Format &
Rahmen), eine Szene,
eine Korrektur, `/stand` --, danach bewertet ein Richter den Verlauf nach
einer festen Metrik.

```
set -a; . ./betrieb/gruppe1.env; set +a
PY=$(ls -d ~/.local/share/uv/python/cpython-3.11*/bin/python3 | head -1)
$PY -m scripts.simulation --set 1 --seed 7 --bericht
$PY -m scripts.simulation --mix 1,2,3 --seed 3
$PY -m scripts.simulation --set 1 --seed 1 --ohne-szene    # ohne Reasoning-Lauf
$PY -m scripts.simulation --set birk --bericht             # echtes Material, ~10 min
$PY -m scripts.simulation --alle                           # Sets 1-3 und birk
```

**Kostet Geld, laeuft nie automatisch** -- wie `scripts/pruefe_prompts.py`.
Die Testsuite deckt alles ab, was ohne Netz pruefbar ist
(`tests/test_simulation*.py`).

## Zwei Modelle, eine Trennlinie

**Der Bot ist der Prueflung und laeuft ueber Infomaniak** -- Gespraech,
Erkenner, Verdichter, Journal, Sprachprofil, Szene, alles wie im Betrieb
(`interview_theater/llm.py`, Env aus `betrieb/gruppe1.env`).

**Die Simulation laeuft ueber Claude Opus** an einem lokalen Proxy
(`simulation/claude.py`): die Stimmen, der Richter und die einmalige
Erzeugung der fuenfzehn Interviewdatensaetze. Anthropic-Messages-Format,
kein Authorization-Header (den setzt der Proxy), kein erzwungener
Schema-Modus -- der Richter wird um reines JSON gebeten und mit genau einem
Reparaturversuch gelesen.

| Env | Vorgabe |
|---|---|
| `IT_SIM_URL` | `http://127.0.0.1:28764/v1/messages` |
| `IT_SIM_MODELL` | `claude-opus-5` |

Die Trennlinie ist der Grund, aus dem die Zahlen etwas bedeuten: ein
Prueflung, der zugleich seine eigenen Teilnehmerinnen spielt und sich
anschliessend selbst benotet, misst vor allem sich selbst. Nebenwirkung, aber
keine unwichtige: die Simulationsseite laeuft ueber ein Abonnement und kostet
je Aufruf nichts -- die Kostenzeile im Bericht ist damit genau das, was ein
echter Workshoptag zahlen wuerde.

## Warum nicht ueber Telegram

Telegram liefert Bot-Nachrichten nie an andere Bots (Bot-FAQ). Ein Testbot,
der den Theaterbot bespielt, ist damit ausgeschlossen. Der Simulator faehrt
deshalb **denselben Codepfad wie der Live-Bot** im selben Prozess --
`bot.verarbeite_update`, `bot._zug_und_erkenner` -- nur mit einer
Telegram-Attrappe statt Netz und einer Wegwerf-Datenbank statt `IT_DB`.
Interviews kommen als Text (`aufnahme.importiere_text`, § 10.5); der
Whisper-Weg ist getrennt getestet und wuerde einen Lauf nur teurer und
langsamer machen.

## Die Teile

| Datei | Zustaendigkeit |
|---|---|
| `scripts/simulation.py` | Aufruf, Wegwerf-DB, 429-Pause, Bericht |
| `lauf.py` | der Durchlauf: Updates bauen, Zug fahren, Interviews importieren |
| `skript.py` | die neun Schritte: Ziel und Zielzustand je Schritt |
| `claude.py` | der Klient der Simulationsseite (Opus am lokalen Proxy) |
| `stimmen.py` + `stimmen/*.md` | drei Personen (Guelten, Dilan, Halyna) und Birk |
| `tag1.py` + `stimmen/tag1-*.md`, `stimmen/regie.md` | die vier Sets aus dem echten Tag 1 -- **PII-frei abgeleitet** |
| `birk.py` | `--set birk`: echtes Material, echte Stimme, Referenzzahlen |
| `material.py` + `interviews/set{1,2,3}/*.md` | 15 erfundene Transkripte, Mischung per Seed |
| `erzeuge_interviews.py` | hat die 15 Transkripte einmal geschrieben (Opus) |
| `attrappe.py` | Telegram ohne Netz |
| `kennzahlen.py` | die mechanischen Zahlen -- kein Modell |
| `richter.py` + `interview_theater/prompts/richter.md` | die Noten (Opus) |
| `bericht.py` | Markdown-Bericht, Transkript, `verlauf.jsonl` |

## Was ein Lauf hinterlaesst

* `simulation/laeufe/<datum>-<mischung>-<seed>.md` -- das Transkript
* `simulation/berichte/<datum>-<mischung>-<seed>.md` -- Kennzahlen, Noten,
  die fuenf schlechtesten Bot-Antworten, drei Saetze zur Ableitung
* `simulation/berichte/verlauf.jsonl` -- eine Zeile je Lauf, mit git-HEAD

Transkript und Bericht sind gitignored (sie enthalten vollstaendige
Modellantworten), `verlauf.jsonl` nicht: sie ist der Vergleichsmassstab
zwischen zwei Prompt-Staenden.

## Wer da schreibt: drei Personen, keine Sprachstile

Bis zum 05.09.2026 standen hier drei Schreibweisen -- knapp, ausschweifend,
skeptisch. Das war die falsche Abstraktion: eine Schreibweise hat keinen
Grund, und ohne Grund wird jede Stimme in jedem Schritt gleich kooperativ.
Jetzt sind es drei Menschen mit Alter, Bildungsweg, Technikvertrautheit und
einem eigenen Ziel im Workshop:

| Person | wer sie ist | Ziel | Gewicht |
|---|---|---|---|
| **Guelten, 58** | mit 19 aus Anatolien, Hausmeisterin, tippt mit einem Finger | ihre Geschichte soll vorkommen, ihr Name nicht | 3 |
| **Dilan, 24** | hier geboren, Soziale Arbeit, kennt ChatGPT und testet den Bot | das Stueck soll politisch sein | 5 |
| **Halyna, 41** | seit 2022 aus Charkiw, Ingenieurin, sehr genau | es soll handwerklich stimmen | 4 |

Das **Gewicht** ist die relative Haeufigkeit, mit der jemand zu Wort kommt:
wer dem Computer am wenigsten traut, schreibt am seltensten. Eine Gruppe, in
der alle drei gleich viel schreiben, gibt es nicht -- und ein Bot, der nur an
einer solchen gemessen wird, sieht nie den Fall, dass eine Teilnehmerin seit
zwanzig Nachrichten nichts gesagt hat. Der `--seed` variiert nur noch, wer
wann spricht; die Besetzung selbst ist fest.

## `--set birk`: das einzige Set auf echten Daten

Die drei erfundenen Sets messen den Bot an Material, das eigens dafuer
geschrieben wurde. `--set birk` misst ihn an dem, was am 04.09.2026 wirklich
passiert ist: dem duennen Testinterview (drei kurze Antworten, drei
Textimporte), **einer** Stimme, kalibriert auf Birks echte Nachrichten, und
einem Chatverlauf als Messlatte daneben.

**Gemessen wird die Navigation, nicht der Text.** Aus drei kurzen Antworten
laesst sich kein Szenentext ableiten, der etwas ueber Sprachqualitaet sagt.
Die Frage ist: Wie natuerlich fuehrt der Bot durch die Phasen, wenn eine
echte Person so knapp schreibt? Der Bericht stellt deshalb neben jede Zahl
die aus dem echten Chat -- Nachrichten je Abschnitt, Rueckfragen, Echo,
unbelegte „notiert"-Behauptungen. Soll: nicht mehr als damals.

Der Lauf schreibt **drei Szenen in drei Formen** -- Dialog, Lied, Rap. Ob der
Bot eine Formvorgabe durchhaelt, die nicht Dialog heisst, ist das eigentliche
Experiment; deshalb ist `--ohne-szene` hier verboten und der Lauf dauert rund
zehn Minuten. Alle drei Texte stehen **vollstaendig** im Bericht, mit je einer
Note fuer „stimmt zur Planung / Stimmen unterscheidbar / Form eingehalten".

Das Material liegt **ausserhalb des Repositories** (echte Daten einer echten
Person): `IT_SIM_BIRK` zeigt darauf, Vorgabe ist
`…/interview-theater-material/birk-test/`. Fehlt es, bricht `--set birk` mit
einer Meldung ab; die Tests bauen sich ein eigenes Verzeichnis in `tmp_path`
und laufen auch ohne.

## Was der Bot weiss: Journal, Kontextaufbau, Zitatabfragen

Der Simulator misst nicht nur den Gespraechs-Bot, sondern auch die zwei
Hintergrundwege, die entscheiden, **was er ueberhaupt weiss**.

**Journal.** Am Ende steht im Bericht, wie viele Eintraege je Art
entstanden sind, wie viele davon der Richter im Chat wiederfindet (Soll:
alle), welche Vorschlaege der Gruppe im Journal fehlen und ob zwei Eintraege
dieselbe Sache sagen. Der Journal-Extraktor laeuft aber nur bei
**Verdraengung** aus dem Gespraechsfenster, und ein Simulationslauf ist dafuer
zu kurz. Dann steht im Bericht „Journal nicht ausgeloest" statt einer Null --
eine Null waere die Behauptung, er habe nichts gefunden, dabei ist er gar
nicht gefragt worden. Wer ihn messen will:

```
$PY -m scripts.simulation --set 1 --seed 1 --fenster-klein --ohne-szene
```

**Kontextaufbau.** `kontext.baue(..., protokoll=list)` schreibt je Prompt
mit, welcher Block mit wie vielen geschaetzten Token darin stand (das
Argument ist rein additiv, der Betrieb setzt es nie). Der Bericht zeigt je
Block Median, Maximum und **in wie vielen Zuegen er leer war** — die
interessanteste Spalte: ein Block, der immer leer war, ist entweder unnoetig
oder haette dasein sollen. Dazu die Prompts ueber `kontext.ZIEL` und die mit
Kuerzung. Und bei den fuenf schwaechsten Antworten urteilt der Richter am
Block-Umriss, ob dem Bot **Information gefehlt** hat, die in der Datenbank
stand (`information_lag_vor`, 2 = alles war da).

**Zitatabfragen** sind ein eigener Skript-Schritt: eine Stimme fragt nach
allen Zitaten eines Interviews, eine nach einer bestimmten Stelle, eine nach
dem ganzen Text. Die drei sind verschieden schwer, weil verschieden viel
davon im Prompt steht — Verdichtungen immer, Volltranskripte nur mit
`/wortlaut`. Mechanisch geprueft wird `zitat_erfunden` (Soll 0): jede
laengere Anfuehrung in einer Antwort auf diese Fragen muss Teilstring eines
Transkripts sein. Nur in diesen Zuegen, nicht ueber den ganzen Lauf — der Bot
setzt auch eigene Vorschlaege in Anfuehrungszeichen, und die stehen
naturgemaess in keinem Transkript.

## Drei Dinge, die man wissen sollte

**Der Simulator laeuft einfaedig.** `lauf.einfaedig()` ersetzt
`szene.starte`, `aufnahme.starte_abschluss` und `aufnahme.starte_auswertung`
durch synchrone Aufrufe. Im Betrieb geben die an Threads ab, weil dort
niemand warten soll; hier muss jede Wirkung in der Datenbank stehen, bevor
der naechste Schritt seinen Zielzustand prueft.

**Ein Schritt darf scheitern.** Ist der Zielzustand nach sechs
Stimm-Nachrichten nicht erreicht, wird das vermerkt und der Lauf geht
weiter. Bekommt der Bot das Ende eines Interviews nicht mit, schliesst der
Simulator es selbst ab (`notausgaenge` im Bericht) -- sonst waere ein Lauf mit
einem tauben Erkenner ab Schritt 3 wertlos und trotzdem bezahlt.

**Alles ist datengetrieben.** Die Phasen kommen aus `phasen.PHASEN`, die
Arbeitsstandfelder aus `PRAGMA table_info(arbeitsstand)`, das Wort
"Notiert:" aus `erkenner.baue_meldung`. Der Simulator soll einen Umbau an
Phasen, Feldern und Formulierungen ueberleben, ohne dass jemand ihn
nachzieht.

## Die Interviews erweitern

Eine Datei je Interview, Kopf zwischen zwei `---`-Zeilen:

```
---
name: Meryem
set: 1
themen: [Koffer, Ankommen, Warten]
sprachmerkmale: [kurze Saetze, Abbrueche, tuerkische Einsprengsel]
zitate_soll:
  - Ein Koffer und eine Tuete mit Brot
  - ...
---
Leyla: Erzaehl mal, was hattest du dabei?

Meryem: Ein Koffer und eine Tuete mit Brot. ...
```

250 bis 450 Woerter, gesprochenes Deutsch, zwei Sprecherinnen im Wechsel,
Umschrift statt Umlauten. Die drei `zitate_soll` muessen **woertlich** im
Text stehen (`tests/test_simulation_material.py` prueft das mit derselben
Funktion, die im Betrieb ueber Belegzitate entscheidet) -- sie sind der
Sollwert der Kennzahl `zitate_soll`.

Geschrieben hat sie einmal `simulation/erzeuge_interviews.py` mit Opus; das
**Ergebnis** ist das Artefakt, nicht das Skript. Namen und Motive stehen dort
fest (`BESETZUNG`) -- sonst zoege `--set 1 --seed 1` nach einer Neuerzeugung
andere Dateien, und zwei Laeufe waeren nicht mehr vergleichbar. Eine einzelne
Datei ersetzen:

```
$PY -m simulation.erzeuge_interviews --nur 2-sevil-erste-liebe
```

Alles darin ist frei erfunden. Kein Satz stammt aus einem echten Interview.

## Die vier Sets aus dem echten Tag 1 (06.09.2026)

```
$PY -m scripts.simulation --set tag1-gruppe1 --bericht
$PY -m scripts.simulation --set tag1-gruppe2 --bericht
$PY -m scripts.simulation --set tag1-gruppe3 --bericht
$PY -m scripts.simulation --set regie --bericht
```

Vier Stimmen, abgeleitet aus dem, was am 05./06.09. wirklich passiert ist:
drei Gruppen Sechzehnjaehriger und die Testgruppe (Regie). Sie fahren das
Skript der **acht Phasen** (`skript.SCHRITTE_TAG2`), nicht das der neun
Schritte -- und sie **druecken Knoepfe**: jede Stimme sieht je Zug die
antippbaren Knopftexte und entscheidet, ob sie `KNOPF: <Text>` antwortet
oder frei schreibt.

| Set | Begriffe der echten Gruppe | Antwortstil |
|---|---|---|
| `tag1-gruppe1` | Trauma, Macht, Stereotype, Massenkontrolle | sehr kurz, drueckt schnell, liest lange Nachrichten nicht zu Ende |
| `tag1-gruppe2` | Liebe, Freundschaft, Mord, Depression | lehnt Vorschlaege oft ab, prueft nach, ob gespeichert wurde |
| `tag1-gruppe3` | Rassismus, Liebe, Spass, Streit | bestaetigt fast alles, drueckt auch mal den falschen Knopf |
| `regie` | (Testgruppe) | knapp und imperativ, Meta-Feedback ueber den Bot, testet Kanten |

**Was aus Tag 1 kommt und was nicht.** Aus den echten Daten stammen: die
Begriffslisten (`arbeitsstand.begriffe` -- die Gruppen haben sie selbst als
Stueckthema gesetzt), die Themen als **Stichwort** (nicht als Zusammenfassung,
nicht als Zitat), und Verhaltensmuster als **Aggregat** (Anzahl Nachrichten,
Medianlaenge, Knoepfe angeboten gegen gedrueckt). Bei `regie` zusaetzlich
Birks eigene Saetze als Stil-Beispiele -- er ist ihr Autor.

**Nie darin**: `aufnahme.transkript` (Lebensgeschichten Minderjaehriger),
Telegram-Usernamen, Klarnamen, Nachrichtentexte der Teilnehmerinnen im
Wortlaut. Beide Betriebsdatenbanken werden ausschliesslich
`sqlite3.connect('file:…?mode=ro', uri=True)` geoeffnet.
`tests/test_simulation_tag1.py` prueft gegen die echte Datenbank, dass keine
Achtwortfolge aus einem Transkript und kein Absendername in `tag1.py` oder
den Steckbriefen steht -- und ueberspringt sich, wenn die Datenbank fehlt.

**Die Interviews bleiben erfunden.** Ein tag1-Lauf zieht zwei Transkripte
aus dem thematisch naechsten Set unter `interviews/` (`tag1.INTERVIEWSET`).
Zwei statt fuenf: die echten Gruppen brachten an Tag 1 je EINE Verdichtung
zustande, und ein Lauf mit fuenf sauberen Interviews misst einen Nachmittag,
den es nicht gab.

**Der Referenzblock** im Bericht stellt neben jede Zahl die aus Tag 1 --
aber nur Aggregate, keinen Chatverlauf (`tag1.referenz`). Die
aufschlussreichste Zeile ist die letzte: an Tag 1 wurden 25 Phasenknoepfe
angeboten und **null** gedrueckt.

### Die Kennzahlen des Knopf-Umbaus

Dazugekommen am 06.09., alle mechanisch: Nachrichten bis zum Speichern
(Soll <= 2), Fragen je Bot-Nachricht (Soll <= 1), Wiederholungsquote,
"Bot redet parallel zum Auftrag" (Soll 0), Knoepfe angeboten gegen
gedrueckt, Phasenwechsel proaktiv gegen `/phase`-Notweg, Form je Szene
bestaetigt statt gesetzt, Rahmen/Geschichte mehrfach geschrieben,
`kontext_gekuerzt`. Dazu ein viertes Szenenkriterium beim Richter:
`exposition_erfuellt` -- nur bei Szene 1 eine echte Frage (wer, wie
zueinander, warum hier, worum).
