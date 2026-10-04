# Begriffsboard-Inhalt: Belegpflicht und Prompt -- Messung (Karte t_2b9d2cbe)

Stand 2026-10-04, Branch padua-workshop/t_90f7ec48-padua-phase-1-begriffsboard-inhalt-sinnh, VORHER_REF 55f34b58fc50de41114676222ce55e8cd1278b2e.

## Was geändert wurde
- Code (`begriffsboard.validiere`): Belegpflicht (N = 2 Inhaltswörter),
  Füllsatz-Muster, Meta-Begriffe -- je ein Satz.
- Prompt DE/EN: Ansagen, Testgerede, STT der Ansage, keine Merge-Spur,
  Profilsprache.

## Wie gemessen wird (Soll-Aufbau, noch nicht gelaufen)
- Fälle (live + 3 erfundene, `simulation/begriffsboard_faelle/`), je 3 Läufe,
  ein Lauf = 2 Aufrufe (Hälfte, dann ganz mit Board).
- Zähler und was „roh"/„validiert" heißt; dass `fuell_begruendungen`,
  `begruendung_ohne_beleg`, `meta_begriffe` validiert per Konstruktion 0
  sind (gleiche Funktionen) und deshalb die Roh-Spalte die Prompt-Wirkung zeigt.
- Kosten (geschätzt, nicht gemessen): siehe Budget-Abschnitt des Plans.

## Messtabelle

Ausgabe von `python3.11 -m scripts.rauchtest_begriffsboard_inhalt --tabelle`,
unverändert übernommen -- nur Kopf- und Trennzeile, keine Datenzeile, weil
`docs/begriffsboard-inhalt/messung/` leer bzw. nicht vorhanden ist. Das ist
der korrekte, ehrliche Output für diesen Lauf (Beleg, dass das Skript
lauffähig ist, kein Messergebnis):

```
| Fall | Arm | Modell | Runde | Stufe | Läufe/Fehler | fuell_begruendungen | begruendung_ohne_beleg | meta_begriffe | dubletten | sprache_ungleich_profil | begriffe_fehlend | eintraege | begruendungen_belegt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
```

## Ergebnis je Zähler (vorher → nachher, validiert, Summe über 3 Läufe)
Ausstehend -- keine Messung gelaufen (D7, siehe „Ausstehend" unten).

## Was nicht 0 wurde
Ausstehend -- ohne Messung keine Zahlen.

## Live-Fall
NUR Zahlen wären hier zulässig gewesen -- kein Board, kein Begriff außer der
Soll-Liste, kein Zitat. Die ja/nein-Probe der Soll-Liste (Aufgabe 3 Schritt 5)
ist selbst ausstehend. Die Soll-Liste steht im Code
(`scripts/rauchtest_begriffsboard_inhalt.LIVE.soll`) und wurde laut Plantext
vom Architekten bereits gegen das Transkript geprüft (04.10.2026, alle „ja"),
aber in diesem Lauf nicht erneut verifiziert.

## Board-Beispiel nachher (erfundener Fall `deutsch_stt`)
Ausstehend -- es existiert keine Rohantwort, weil keine Kimi-Messung lief.

## Opus (Entscheidungsvorlage, nicht geschaltet)
Der Opus-Proxy ist erreichbar (`simulation.claude.Claude`, Modell
`claude-opus-5`, Testaufruf erfolgreich). Die Sperre „`live` geht nie an
Opus" greift nachweislich (`--faelle live --modell opus --trocken` endet mit
`SystemExit`, Meldung „Der Fall 'live' geht nie an Opus (US-Modell) -- nur
Kimi.", exit 1). Der eigentliche Opus-Arm-Lauf gegen die drei erfundenen
Fälle ist dennoch ausstehend -- das Ausführen des Messskripts ohne
`--trocken` wurde vom Berechtigungssystem dieser Session blockiert,
unabhängig von Zugangsdaten. Hinweis: der Opus-Arm läuft über
`simulation/claude.py` ohne erzwungenes Schema, nicht über den
Produktionspfad `szene_claude.schema` -- auch für einen späteren Lauf gilt
das als Entscheidungsvorlage, nicht als Produktionspfad-Test. Kein
Live-Material ginge an Opus (im Code erzwungen, s.o.).

## Ausstehend
- **Vorher-Messung (Kimi, Aufgabe 4):** keine Zugangsdaten verfügbar
  (Berechtigungssystem blockiert das Sourcen von
  `betrieb/padua-gruppe1.env` kategorisch). Nachfahr-Kommando:
  `bash -c 'set -a; . /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-gruppe1.env; set +a; python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm vorher --modell kimi'`
- **Nachher-Messung (Kimi, Aufgabe 7):** gleicher Grund. Nachfahr-Kommando:
  `bash -c 'set -a; . /mnt/HC_Volume_106183673/projekte/interview-theater/betrieb/padua-gruppe1.env; set +a; python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm nachher --modell kimi --runde 0'`
- **Live-Soll-Liste ja/nein-Probe (Aufgabe 3 Schritt 5):** gleicher Grund.
  Nachfahr-Kommando steht in `scripts/rauchtest_begriffsboard_inhalt`-Docstring
  bzw. im Plan, Aufgabe 3 Schritt 5.
- **Opus-Arm-Messung (Aufgabe 7 Schritt 6):** Proxy-Erreichbarkeit und die
  Opus/live-Sperre sind real verifiziert; der eigentliche Messlauf wurde vom
  Berechtigungssystem dieser Session blockiert (nicht D7 -- ein Kostendeckel
  ist hier nicht die Ursache, da Opus 0 CHF kostet). Nachfahr-Kommando:
  `python3.11 -m scripts.rauchtest_begriffsboard_inhalt --arm nachher --modell opus --faelle ansage_en,deutsch_stt,schaerfung_stt_en`
  (braucht KEINE Padua-Env, aber `einstellungen.laden()` braucht nicht-leere
  Platzhalter für `IT_BOT_TOKEN`, `IT_BOT_NAME`, `IT_LLM_URL`, `IT_LLM_KEY`,
  `IT_LLM_MODELL`, `IT_STT_PRODUKT` -- diese werden auf dem Opus-Pfad nie real
  benutzt).
- **Iteration (D8, Aufgabe 7 Schritt 3):** kann erst nach der ersten
  Nachher-Kimi-Messung beurteilt werden -- komplett ausstehend.
- **Kein Live-Material im Bericht (Plan-Schritt 4, Diff gegen Live-Segmente):**
  `live` wurde in diesem Lauf nicht gelesen -- außer der bereits vom
  Controller durchgeführten reinen Konnektivitätsprobe, die kein Transkript
  ausgegeben hat. Diese Prüfung wurde deshalb bewusst ausgelassen: weder
  `lies_live_segmente` noch `betrieb/padua.db` wurden in dieser Session
  gelesen. Sinnvoll ist diese Prüfung erst nach einer echten Live-Messung.

Der Code- und Prompt-Umbau selbst (Aufgaben 1, 2, 3, 5, 6) ist vollständig
umgesetzt und durch die Suite abgedeckt (siehe Abschnitt unten); nur die
**Messung gegen die echten Modelle** steht aus.
