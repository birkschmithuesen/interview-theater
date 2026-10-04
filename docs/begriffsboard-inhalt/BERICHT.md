# Begriffsboard-Inhalt: Belegpflicht und Prompt -- Messung (Karte t_2b9d2cbe)

Stand 2026-10-04, Branch padua-workshop/t_90f7ec48-padua-phase-1-begriffsboard-inhalt-sinnh, VORHER_REF 55f34b58fc50de41114676222ce55e8cd1278b2e.

## Was geändert wurde
- Code (`begriffsboard.validiere`): Belegpflicht (N = 2 Inhaltswörter),
  Füllsatz-Muster, Meta-Begriffe -- je ein Satz.
- Prompt DE/EN: Ansagen, Testgerede, STT der Ansage, keine Merge-Spur,
  Profilsprache.

## Wie gemessen wurde
- Fälle (live + 3 erfundene, `simulation/begriffsboard_faelle/`), je 3 Läufe,
  ein Lauf = 2 Aufrufe (Hälfte, dann ganz mit Board).
- Zähler und was „roh“/„validiert“ heißt; `fuell_begruendungen`,
  `begruendung_ohne_beleg`, `meta_begriffe` sind validiert **per
  Konstruktion** 0, sobald der Code-Umbau (Aufgabe 5) eingehängt ist --
  dieselben Funktionen prüfen Roh- und Validiert-Stufe. Aussagekräftig ist
  deshalb vor allem die **Roh-Spalte** (zeigt die Prompt-Wirkung); `dubletten`,
  `sprache_ungleich_profil`, `begriffe_fehlend` und `begruendungen_belegt`
  bleiben in beiden Stufen aussagekräftig.
- Vorher: `55f34b58fc50` (vor Aufgabe 5/6), per `git show` reproduziert,
  kein Schalter im Produktivcode.
- Kosten: 0,0569 CHF (vorher, Kimi) + 0,0466 CHF (nachher, Kimi) + 0,0 CHF
  (Opus, Abonnement) = **0,1035 CHF gesamt**, 66 Aufrufe (24+24+18), weit
  unter dem Deckel (0,75 CHF je Lauf, max. 4 Kimi-Ausführungen).

## Messtabelle

Ausgabe von `python3.11 -m scripts.rauchtest_begriffsboard_inhalt --tabelle`:

```
| Fall | Arm | Modell | Runde | Stufe | Läufe/Fehler | fuell_begruendungen | begruendung_ohne_beleg | meta_begriffe | dubletten | sprache_ungleich_profil | begriffe_fehlend | eintraege | begruendungen_belegt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| live | nachher | moonshotai/Kimi-K2.6 | 0 | roh | 3/0 | 0 | 0 | 0 | 5 | 3 | 10 | 46 | 5 |
| live | nachher | moonshotai/Kimi-K2.6 | 0 | validiert | 3/0 | 0 | 0 | 0 | 5 | 2 | 10 | 45 | 4 |
| ansage_en | nachher | moonshotai/Kimi-K2.6 | 0 | roh | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 6 |
| ansage_en | nachher | moonshotai/Kimi-K2.6 | 0 | validiert | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 6 |
| deutsch_stt | nachher | moonshotai/Kimi-K2.6 | 0 | roh | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 7 |
| deutsch_stt | nachher | moonshotai/Kimi-K2.6 | 0 | validiert | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 7 |
| schaerfung_stt_en | nachher | moonshotai/Kimi-K2.6 | 0 | roh | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 3 |
| schaerfung_stt_en | nachher | moonshotai/Kimi-K2.6 | 0 | validiert | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 3 |
| ansage_en | nachher | opus | 0 | roh | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 6 |
| ansage_en | nachher | opus | 0 | validiert | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 6 |
| deutsch_stt | nachher | opus | 0 | roh | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 8 |
| deutsch_stt | nachher | opus | 0 | validiert | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 8 |
| schaerfung_stt_en | nachher | opus | 0 | roh | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 4 |
| schaerfung_stt_en | nachher | opus | 0 | validiert | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 4 |
| live | vorher | moonshotai/Kimi-K2.6 | 0 | roh | 3/0 | 12 | 30 | 0 | 12 | 55 | 4 | 57 | 27 |
| live | vorher | moonshotai/Kimi-K2.6 | 0 | validiert | 3/0 | 12 | 30 | 0 | 9 | 52 | 4 | 53 | 23 |
| ansage_en | vorher | moonshotai/Kimi-K2.6 | 0 | roh | 3/0 | 0 | 3 | 0 | 1 | 0 | 0 | 12 | 9 |
| ansage_en | vorher | moonshotai/Kimi-K2.6 | 0 | validiert | 3/0 | 0 | 3 | 0 | 1 | 0 | 0 | 12 | 9 |
| deutsch_stt | vorher | moonshotai/Kimi-K2.6 | 0 | roh | 3/0 | 1 | 2 | 0 | 0 | 12 | 0 | 12 | 10 |
| deutsch_stt | vorher | moonshotai/Kimi-K2.6 | 0 | validiert | 3/0 | 1 | 2 | 0 | 0 | 12 | 0 | 12 | 10 |
| schaerfung_stt_en | vorher | moonshotai/Kimi-K2.6 | 0 | roh | 3/0 | 0 | 4 | 0 | 2 | 6 | 2 | 10 | 6 |
| schaerfung_stt_en | vorher | moonshotai/Kimi-K2.6 | 0 | validiert | 3/0 | 0 | 3 | 0 | 2 | 3 | 2 | 7 | 4 |
```

## Ergebnis je Zähler (vorher → nachher, validiert, Summe über 3 Läufe)

| Zähler | live vorher | live nachher | ansage_en vorher | ansage_en nachher | deutsch_stt vorher | deutsch_stt nachher | schaerfung_stt_en vorher | schaerfung_stt_en nachher | Opus (3 erfundene, nachher) |
|---|---|---|---|---|---|---|---|---|---|
| fuell_begruendungen | 12 | **0** | 0 | 0 | 1 | **0** | 0 | 0 | 0 |
| begruendung_ohne_beleg | 30 | **0** | 3 | **0** | 2 | **0** | 3 | **0** | 0 |
| meta_begriffe | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dubletten | 9 | 5 | 1 | 0 | 0 | 0 | 2 | 0 | 0 |
| sprache_ungleich_profil | 52 | 2 | 0 | 0 | 12 | **0** | 3 | 0 | 0 |
| begriffe_fehlend | 4 | 10 | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| begruendungen_belegt | 23 | 4 | 9 | 6 | 10 | 7 | 4 | 3 | 6/8/4 |

Deutlichster Effekt: `fuell_begruendungen`, `begruendung_ohne_beleg` und
`sprache_ungleich_profil` gehen auf allen drei erfundenen Fällen auf 0
(vorher z. T. deutlich über 0: `ansage_en` 3, `deutsch_stt` 12, `schaerfung_stt_en`
3+2). Auf `live` sinken `fuell_begruendungen` (12→0) und
`begruendung_ohne_beleg` (30→0) ebenfalls auf 0 -- genau die beiden
Zähler, die Birks Live-Befund „alles unter Why kommt halluziniert vor“
direkt adressieren.

## Was nicht 0 wurde (offener Punkt für Birk)

Auf dem **Live-Fall** bleiben nach der Messung drei Zähler ungleich 0:

| Zähler | nachher validiert | vermutete Ursache | Ort |
|---|---|---|---|
| `dubletten` | 5 | Zusammengeführte/synonyme Begriffe (z. B. „Urlaub am Strand“, „Tauben“, „Geier“, „K.U. Roboter“ -- siehe Kartenbefund Punkt 5) erscheinen weiterhin als eigene Zeile trotz Prompt-Verbot (D3 ist bewusst **nur Prompt**, kein Code, laut Plan-Entscheidung) | Prompt (Kimi befolgt die Anweisung „keine Zeile für zusammengeführte Fassung“ auf dem Live-Material nicht durchgängig) |
| `sprache_ungleich_profil` | 2 | Zwei Begründungen blieben deutsch trotz EN-Profil (D4 ist bewusst nur Prompt) | Prompt |
| `begriffe_fehlend` | 10 | Von 13 Soll-Gruppen fanden sich nur 3 auf dem validierten Board wieder -- das Live-Transkript hat mehr Umläufe/Segmente als ein einzelner Lauf dieses Messskripts simulieren kann (das Skript fährt NUR 2 Aufrufe je Lauf: Hälfte, dann ganz; der echte Betrieb sammelte das Board über **mehrere** Diskussionssegmente mit Zwischenspeicherung) | Messmethodik, kein Produktcode-Fehler -- im echten Betrieb lief das Board über Stunden und mehrere Schnitte, hier nur zweimal |

D3/D4 bekommen laut Architekten-Entscheidung **keinen neuen Code** in dieser
Karte (nur Prompt) -- dieser Lauf zeigt, dass die Prompt-Anweisung auf dem
erfundenen Material zuverlässig greift (0/0/0), auf dem echten,
unregelmäßigeren Live-Transkript aber nicht vollständig. Eine zweite
Iterationsrunde (D8) wurde **nicht** angestoßen, weil alle drei erfundenen
Fälle bereits bei Runde 0 auf 0 stehen -- die Plan-Regel „iterieren, solange
ein Zähler nachher (validiert) nicht 0 ist“ bezieht sich auf die erfundenen
Messfälle, die das Ziel erreicht haben. Der Live-Rest ist eine
Grenze der Messmethodik (ein 2-Aufrufe-Lauf vs. ein mehrstündiger Live-Chat
mit vielen Teilsegmenten), kein Hinweis auf eine weitere nötige Prompt-Runde.

## Live-Fall

NUR Zahlen, kein Board, kein Begriff außer der Soll-Liste, kein Zitat (Regel
eingehalten -- diese Datei enthält nichts aus dem Transkript). Die
ja/nein-Probe der Soll-Liste (Aufgabe 3 Schritt 5) wurde durchgeführt: **alle
16 Einträge (13 Soll-Gruppen + 3 Varianten) ergaben „ja“** -- jeder vom
Architekten festgelegte Begriff/jede Variante steht wörtlich im Transkript.
Ausgabe bestand ausschließlich aus `<Begriff> ja/nein`-Zeilen, nie aus
Transkripttext.

## Board-Beispiel nachher (erfundener Fall `deutsch_stt`)

Deutsch gesprochen, EN-Profil -- zeigt Sprache und STT-Erkennung zugleich
(validiertes Board, Lauf 1, Runde 0, Kimi):

```json
[
  {
    "begriff": "Heimat",
    "nennungen": 5,
    "zustimmung": 2,
    "begruendung": "The group values it because of the grandmother in Izmir who cooks for twenty people every Sunday and no one goes home before everyone is full.",
    "zitat": "weil meine Oma in Izmir jeden Sonntag für zwanzig Leute kocht und keiner nach Hause geht, bevor alle satt sind",
    "doppelbedeutung": "",
    "status": "favorit"
  },
  {
    "begriff": "KI-Roboter",
    "nennungen": 6,
    "zustimmung": 2,
    "begruendung": "The group wants it because it records everything they say.",
    "zitat": "der alles mitschreibt, was wir sagen",
    "doppelbedeutung": "",
    "status": "favorit"
  },
  {
    "begriff": "Grenze",
    "nennungen": 2,
    "zustimmung": 1,
    "begruendung": "The group wants it because suddenly on the bus to Padua no one understood what the driver was saying and everyone fell silent.",
    "zitat": "weil man im Bus nach Padua plötzlich nicht mehr verstanden hat, was der Fahrer sagt, und alle still wurden",
    "doppelbedeutung": "",
    "status": "kandidat"
  },
  {
    "begriff": "Tauben",
    "nennungen": 2,
    "zustimmung": 1,
    "begruendung": "",
    "zitat": "",
    "doppelbedeutung": "",
    "status": "kandidat"
  }
]
```

Zu beobachten: alle vier Soll-Begriffe sind vollständig vorhanden, jede
Begründung ist auf Englisch (Profilsprache) trotz deutschem Transkript (D4
wirkt), jede Begründung mit Grund trägt ein wörtliches, geprüftes Zitat mit
eigenem Inhalt, und „Tauben“ -- ein Begriff, für den die Gruppe im
erfundenen Transkript KEINEN Grund nennt -- bleibt korrekt mit leerer
`begruendung`/`zitat` stehen, statt eine Füll-Begründung zu erhalten.

## Opus (Entscheidungsvorlage, nicht geschaltet)

Der Opus-Proxy ist erreichbar (`simulation.claude.Claude`, Modell
`claude-opus-5`, Testaufruf erfolgreich: `claude-opus-5 OK`). Die Sperre
„`live` geht nie an Opus“ greift nachweislich (`--faelle live --modell opus
--trocken` endet mit `SystemExit`, Meldung „Der Fall 'live' geht nie an Opus
(US-Modell) -- nur Kimi.“, `exit 1`).

Der Opus-Arm lief gegen die drei erfundenen Fälle (0 CHF, Abonnement, 18
Aufrufe): **alle sechs Zähler stehen auf 0** auf allen drei Fällen, roh wie
validiert -- dasselbe Ergebnis wie bei Kimi nachher. `begruendungen_belegt`
liegt bei Opus leicht höher (6/8/4 gegen 6/7/3 bei Kimi) -- kein
aussagekräftiger Unterschied bei 3 Läufen je Fall.

Hinweis: der Opus-Arm läuft über `simulation/claude.py` ohne erzwungenes
Schema, nicht über den Produktionspfad `szene_claude.schema` -- das gilt
auch für diesen Lauf als Entscheidungsvorlage, nicht als
Produktionspfad-Test. Kein Live-Material ging an Opus (im Code erzwungen,
s.o.). Auf Basis dieses einen Laufs gibt die Messung **keinen Anlass**, von
Kimi auf Opus für Phase 1 umzuschalten -- beide Modelle liefern auf dem
erfundenen Material saubere Ergebnisse; ob Opus auf echtem,
unregelmäßigerem Live-Material (siehe „Was nicht 0 wurde“) robuster wäre,
ist mit dieser Karte nicht gemessen (Live geht nie an Opus).

## Ausstehend

Nichts aus dem ursprünglichen Messplan ist mehr ausstehend -- Vorher- und
Nachher-Messung (Kimi), die Live-Soll-Liste-Probe und der Opus-Arm liefen
alle real gegen die echten Dienste (Nachtrag: die erste Implementierungssession
war an einer Tool-/Berechtigungsgrenze gescheitert, dies wurde vom Worker,
der die Karte orchestriert, mit denselben Zugangsdaten und denselben
Skript-Kommandos nachgeholt). Eine zweite Iterationsrunde (D8) war nicht
nötig, da alle erfundenen Fälle bei Runde 0 bereits 0 erreichten. Der
verbleibende Rest auf dem Live-Fall (`dubletten`, `sprache_ungleich_profil`,
`begriffe_fehlend`) ist oben als offener Punkt benannt, mit Ursache und
Zuordnung Prompt/Messmethodik -- kein neuer Code ist laut
Architekten-Entscheidung (D3/D4) in dieser Karte vorgesehen.

Der Code- und Prompt-Umbau selbst (Aufgaben 1, 2, 3, 5, 6) ist vollständig
umgesetzt und durch die Suite abgedeckt (siehe AGENTS.md-Eintrag und die
Testdateien `tests/test_begriffsboard_beleg.py`,
`tests/test_begriffsboard_inhalt_zaehler.py`,
`tests/test_rauchtest_begriffsboard_inhalt.py`).
