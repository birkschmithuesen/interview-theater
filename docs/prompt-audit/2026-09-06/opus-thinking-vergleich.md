# Thinking-Vergleich für den Szenenlauf (`claude-opus-5`) — Messung

**Datum:** 06.09.2026 · **Messer:** Subagent (Worktree `/tmp/it-messung`, Branch `feat/opus-messung`)
**Modell:** `claude-opus-5` über `hermes-anthropic-proxy` (Abo-OAuth)
**Prompt:** der reale Szenen-Prompt aus `13-szene-dialog.txt`
(`szene.systemanweisung('dialog')` + `baue_nutzertext`, Testgruppe, Szene 1)
— System 31.183 Zeichen / 10.394 Token, Nutzer 3.175 Zeichen / 1.058 Token,
gemessen **17.711 Eingabe-Token** inkl. Overhead.
**Skripte:** `scripts/opus_messung.py`, `scripts/opus_richter.py`
**Texte + Rohdaten:** `opus-thinking-texte/` (nur erfundene Figuren)
**Belegstatus:** [M] gemessen · [Q] Anbieterdoku

---

## 0. Das wichtigste Ergebnis zuerst

**Der Betriebsklient schreibt Szenen nicht „ohne Thinking". Er denkt bereits —
4.288 bzw. 5.193 Denk-Token im Lauf ohne jeden `thinking`-Parameter** [M].

`claude-opus-5` führt laut Anthropic-Doku **„Thinking: Adaptive", „Default
effort: high"** [Q, platform.claude.com/docs/en/models/overview]. Adaptives
Denken ist bei diesem Modell **nicht abschaltbar über das Weglassen des
Parameters** — Weglassen heißt „Modell entscheidet", und das Modell entscheidet
sich bei einem 17k-Token-Dramaturgie-Auftrag jedes Mal fürs Denken.

Damit ist die Frage „Thinking an oder aus für den Szenenlauf?" **falsch
gestellt**. Sie lautet richtig: „Lohnt es, das ohnehin laufende adaptive Denken
durch ein festes Budget zu ersetzen?" Antwort unten: **nein.**

---

## 1. Parameter-Akzeptanz [M]

| Variante | Syntax | Status |
|---|---|---|
| a — ohne | kein `thinking`-Feld | **200** — denkt trotzdem (adaptive default) |
| b — enabled 8k | `thinking: {"type":"enabled","budget_tokens":8000}` | **200** — akzeptiert |
| c — adaptive | `thinking: {"type":"adaptive"}` | **200** — akzeptiert |

Bemerkenswert: Die Wissensdatei notiert in § 1.2, dass `type:"enabled"` auf den
neuesten Modellen **mit HTTP 400 abgelehnt** werde. Für `claude-opus-5` über
diesen Proxy gilt das **nicht** — die alte Budget-Syntax wird angenommen und
wirkt (höchster Denk-Token-Verbrauch aller drei Varianten). Das ist eine
Korrektur an der bisherigen Annahme.

`usage.output_tokens_details.thinking_tokens` wird in allen Varianten sauber
ausgewiesen; Denk-Token sind in `output_tokens` **enthalten**.

---

## 2. Mechanische Messwerte — 6 Läufe, je 2 pro Variante [M]

| Variante | Dauer ⌀ | Eingabe-Tok | Ausgabe-Tok ⌀ | davon Denken ⌀ | Denkanteil | stop_reason |
|---|---:|---:|---:|---:|---:|---|
| **a — ohne** (Betrieb) | **117,6 s** | 17.711 | 8.146 | **4.740** | 58 % | end_turn |
| **b — enabled 8k** | **121,7 s** | 17.711 | 8.681 | **5.673** | 65 % | end_turn |
| **c — adaptive** | **111,6 s** | 17.711 | 7.512 | **4.244** | 57 % | end_turn |

Einzelläufe: a 111,4 / 123,7 s · b 105,8 / 137,5 s · c 119,7 / 103,4 s.

**Die Streuung innerhalb einer Variante (bis 32 s) ist größer als der Abstand
zwischen den Varianten (10 s).** Bei n=2 pro Zelle ist der Latenzunterschied
statistisch nicht vorhanden. Kein Lauf lief in `max_tokens` (32.000) — der
tatsächliche Verbrauch liegt bei einem Viertel davon.

### Textmaße (mechanisch gezählt)

| Variante | Zeichen ⌀ | Sprechzeilen ⌀ | Regiezeilen ⌀ | **Regie-Anteil** | Replik ⌀ Wörter | Replik max | Figuren |
|---|---:|---:|---:|---:|---:|---:|---:|
| a — ohne | 5.829 | 106,0 | 13,5 | **11,2 %** | 7,1 | 47 | 4 |
| b — enabled 8k | 4.957 | 99,5 | 9,5 | **8,7 %** | 6,5 | 52 | 4 |
| c — adaptive | 5.464 | 109,0 | 11,0 | **9,3 %** | 6,8 | 44 | 4 |

- **Regie-Anteil ≤ 20 %:** von allen sechs Läufen eingehalten (8,3–13,0 %).
  Keine Variante fällt durch, keine ist auffällig besser.
- **Repliklänge:** ⌀ 6,5–7,1 Wörter, überall kurz und sprechbar; Ausreißer nach
  oben (44–52 Wörter) ist in allen Varianten je eine Aylin-Schachtelsatz-Replik
  — ein Figurenmerkmal aus dem Prompt, kein Fehler.
- **Figurenzahl:** überall 4 (Leyla, Cemre, Zeynep, Aylin). Rahmen-treu.
  (`TITEL`/`KURZ` sind Formatzeilen, keine Figuren — aus der Zählung genommen.)

---

## 3. Blindes Richterurteil [M]

Ein Aufruf, `claude-opus-5`, eigener Richter-Prompt, die sechs Texte in
gemischter Reihenfolge als E1–E6, Labels versteckt, Zuordnung erst nach dem
Urteil aufgelöst (`richter_zuordnung.json`, Seed 20260906). Kriterien aus
`prompts/szene.md`.

| Kennung | war in Wahrheit | aufgabe | rahmen | sprache | gesamt |
|---|---|---:|---:|---:|---:|
| E1 | **a — ohne**, Lauf 2 | 5 | 4 | 5 | **5** |
| E2 | **a — ohne**, Lauf 1 | 4 | 4 | 4 | **4** |
| E3 | c — adaptive, Lauf 1 | 4 | 4 | 4 | **4** |
| E4 | b — enabled 8k, Lauf 2 | 4 | 4 | 4 | **4** |
| E5 | c — adaptive, Lauf 2 | 5 | 4 | 5 | **4** |
| E6 | b — enabled 8k, Lauf 1 | 4 | 3 | 5 | **5** |

**Rangfolge des Richters: E1 > E6 > E5 > E4 > E2 > E3**
→ aufgelöst: **ohne > enabled8k > adaptive > enabled8k > ohne > adaptive**.

Die Varianten sind über die Rangfolge **vollständig durchmischt**. Jede Variante
stellt einen Text in der oberen und einen in der unteren Hälfte. Mittelwerte:
gesamt a 4,5 · b 4,5 · c 4,0 — bei n=2 bedeutungslos.

Der Richter selbst, unaufgefordert und ohne die Varianten zu kennen:

> „Es gibt einen Unterschied, aber er ist schmal. Alle sechs sind offensichtlich
> dasselbe Gerüst […] **Ganze Repliken sind wortgleich.** […] zwischen E2, E3
> und E4 würde ich nicht behaupten, dass ich mehr als Rauschen sehe."

Was er als trennend benennt — Konkretheit des zitierten Chat-Satzes, wie viel
Grundinformation nebenbei mitläuft, ob die genannten Uhrzeiten wirklich 51
Stunden ergeben — verteilt sich quer über die Varianten, nicht entlang von
ihnen.

### Ein Befund, der nicht zur Thinking-Frage gehört, aber wichtig ist

Der Richter monierte, alle sechs spielten auf dem Schulhof statt am Kiosk.
**Das ist ein Fehler meines Richter-Prompts, nicht der Texte:** die Szenenangabe
im echten Prompt lautet `Ort: Schulhof` (Zeile 654), der Kiosk kommt nur in der
Ortsliste des Rahmens vor. Die Texte sind rahmentreu; ich hatte den Richter
falsch gebrieft. Sein Rechen-Check („ergeben die Uhrzeiten 51 Stunden?") ist
davon unberührt und bleibt gültig — er ist ein brauchbares Qualitätsmaß für
künftige Läufe.

---

## 4. Deutung vor dem Hintergrund der Wissensdatei

`reasoning-stufen-entscheidungshilfe.md` § 0.1 / § 3.1: *Reasoning hilft massiv
bei Mathematik, Logik und symbolischer Manipulation — und fast gar nicht bei
Wissens-, Sprach- und Extraktionsaufgaben.*

Szenenschreiben ist eine Sprach-/Kreativaufgabe. **Die Messung bestätigt die
Kernthese:** zusätzliches, erzwungenes Denkbudget (8.000 statt der adaptiven
~4.700) erzeugte 933 mehr Denk-Token und keinen erkennbaren Qualitätsgewinn —
weder mechanisch (Regie-Anteil, Repliklänge, Figurenzahl alle im grünen Bereich
und untereinander ununterscheidbar) noch im Blindurteil.

**Kein Widerspruch zur Kernthese.** § 0 der Wissensdatei bleibt unverändert.

Zwei Präzisierungen liefert die Messung aber:

1. **§ 2.3 („Latenz ist der Preis", Faktor 4–23×) gilt hier nicht.** Der Faktor
   zwischen „ohne" und „mit Budget" ist **1,03** — weil die Basis bereits denkt.
   Die dort gemessenen Faktoren stammen aus einer Welt mit echtem Aus-Zustand
   (Infomaniak `reasoning_effort: "none"`). Bei Anthropics 5er-Reihe gibt es
   diesen Aus-Zustand nicht mehr; der Latenzpreis ist bereits bezahlt, bevor man
   einen Parameter setzt.
2. **§ 1.2 (`type:"enabled"` werde auf neuen Modellen mit 400 abgelehnt)
   trifft auf `claude-opus-5` über diesen Kanal nicht zu** — beide Syntaxen
   liefern 200.

---

## 5. Empfehlung für den Betrieb

**Am Szenenlauf nichts ändern: `szene_claude.py` soll weiterhin keinen
`thinking`-Parameter setzen.** [M-gestützt]

Begründung:

- Das Modell denkt ohnehin adaptiv (~4.700 Token) — der Nutzen ist bereits
  eingesammelt.
- `budget_tokens: 8000` kostet ~930 zusätzliche Ausgabe-Token pro Szene, also
  Abo-Kontingent, und bringt messbar nichts.
- Explizit `{"type":"adaptive"}` zu setzen ist zwar die zukunftsfeste Syntax,
  ändert aber am Verhalten nichts gegenüber dem Weglassen (111,6 s vs. 117,6 s
  liegt im Rauschen) — es wäre reine Kosmetik im Betriebscode und damit nach
  der Regel „kein Betriebscode ändern ohne Grund" nicht gerechtfertigt.
- **Der Hebel für Szenenqualität liegt nicht am Reasoning-Regler.** Die sechs
  Texte teilen wortgleiche Repliken; was sie unterscheidet, entscheidet der
  Prompt (welcher Chat-Satz wörtlich vorliegt, wie präzise die Szenenangabe
  ist), nicht die Denkmenge. Das deckt sich mit § 4.4 der Wissensdatei.

**Wenn die Szenenlatenz je zum Problem wird** (aktuell ~2 Minuten pro Szene):
Der einzige echte Hebel wäre `output_config: {effort: "low"|"medium"}`, das laut
Doku [Q] das adaptive Denken *nach unten* regelt („at lower effort settings it
may skip thinking entirely on easy inputs") — Default ist `high`. Das wurde hier
**nicht gemessen** und wäre die nächste sinnvolle Messung, wenn Wartezeit
drückt. Erwartung [P]: spürbar schneller, Qualität nach obigem Befund kaum
schlechter — aber ungeprüft.

**Zum Kontextbudget** (aus `opus-1m-messung.md`): reales Eingabefenster für
`claude-opus-5` über diesen Proxy = **1.000.000 Token** [M]. Der Szenen-Prompt
nutzt davon 17.711 = **1,8 %**. Eine Budget-Grenze im Klienten muss nicht am
Modell ausgerichtet werden, sondern am Abo-Kontingent und daran, dass Auswahl
schlägt Menge.

---

## 6. Grenzen dieser Messung — ehrlich

- **n = 2 pro Variante.** Das reicht, um „kein großer Effekt" zu zeigen, nicht,
  um einen kleinen auszuschließen. Ein Effekt in der Größenordnung ±0,5
  Richterpunkte wäre hier unsichtbar.
- **Ein Richter, ein Aufruf.** Kein Mehrfach-Urteil, keine Reihenfolge-Rotation.
- **Ein Prompt, eine Szene, eine Form** (Dialog). Für Chor/Lied/Rap ungeprüft.
- Der Richter wurde von mir zum Ort falsch gebrieft (§ 3), was seine
  Rahmen-Bewertung leicht nach unten zieht — **gleichmäßig über alle sechs**,
  der Vergleich bleibt gültig.
- `output_config.effort` ungetestet — die vermutlich interessanteste Stellschraube.
