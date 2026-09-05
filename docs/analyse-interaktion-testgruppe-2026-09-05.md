# Interaktionsanalyse Testgruppe, 05.09.2026

Datenquelle: `betrieb/test.db` (read-only), chat_id `-5257292234`. Workshopleiter
allein im Chat, Phasen 1→6 durchgespielt. Alles Folgende ist gezählt, nicht
geschätzt; das Auswertungsskript steht am Ende dieser Datei.

## 1. Kernzahlen

| Größe | Wert |
| --- | --- |
| Nachrichten gesamt | 104 (59 Bot, 45 Mensch) |
| Bot-Zeichen gesamt | 30 674 — Median 415, Maximum 2 434 |
| Bot-Nachrichten mit Fragezeichen | 38 von 59 = **64 %**, 161 Fragezeichen |
| „Notiert:"-Zeilen | 13, davon **13** mit „Falls das nicht stimmt, sagt es mir." |
| Knöpfe angeboten / gedrückt | 74 / 25 = **34 %** |
| Vorschlagsknöpfe (rahmen, kernthema, richtung) angeboten / gedrückt | 23 / **0** |
| Journal-Einträge (= Speicherungen) | 6 in 5 Stunden |
| Nachrichten je Speicherung (Ziel ≤ 2) | 21 / 24 / 8 / 26 / 5 / 19 — **Median 20** |
| Bot-Wiederholungen (Wortmenge > 60 % in voriger Bot-Nachricht) | 4 von 59 |
| Mensch-Wiederholungen (Jaccard > 0,5 zwischen zwei Birk-Nachrichten) | 21 Paare, praktisch alle „Erstelle mir drei Fragen über X" |
| Überschriebene Felder | `rahmen` 1× still überschrieben (21:37 → 21:50) |

**Der Befund in einem Satz:** Nicht die Bot-Nachrichten wiederholen sich (nur
4 von 59) — die *Arbeit* wiederholt sich. Zwischen zwei Speicherungen liegen
im Median 20 Nachrichten, weil der Bot vor jedem Ablegen rückfragt statt
abzulegen, und in 64 % seiner Nachrichten mindestens eine Frage stellt.

## 2. Chronologie nach Phasen

### Phase 1 · Begriffe (13:41 – 14:09)

- 13:41 Birk gibt die Begriffe. 13:55 Bot notiert sie (1 108 Zeichen Begrüßung
  + eigene Notiert-Nachricht). Der Wert steht sofort — **das ist der gute Fall.**
- 14:02 – 14:09: sieben Anläufe „Erstelle mir drei Fragen über X". Der Bot
  antwortet jedes Mal mit einer Meta-Betrachtung über die Struktur der Fragen
  („da sehe ich ein Muster", „bei Spaß würde ich absichtlich ausbrechen") statt
  mit den drei Fragen. Birk stellt dieselbe Bitte sechsmal.
- 14:08 Birk: „Kannst du das auf der Webseite speichern" → der Bot antwortet
  „Ich kann nichts speichern -- das passiert automatisch, wenn ihr auf die
  Knöpfe tippt", **obwohl er selbst gerade einen Vorschlagsblock hätte
  anhängen können**, und fragt stattdessen, ob er einen anhängen soll. 14:09
  Birk: „Ja" → der Bot fragt erneut, ob er einen anhängen soll (mid −280).
- Erste Journal-Zeile: 14:09, nach **21 Nachrichten**.

### Phase 3 · Interviews (14:21 – 20:54)

- Zwei leere „Interview N hatte keine Aufnahme"-Zeilen wortgleich hintereinander
  (14:21, Jaccard 1,0).
- 16:39 und 20:52: **wortgleiche** „Bin wieder da"-Zeile mit **falscher Phase**
  („Wir sind bei 1 · Begriffe", tatsächlich Phase 3) und dem überflüssigen
  „Wenn ihr weitermachen wollt, sagt mir Bescheid".

### Phase 4 · Setting & Figuren (21:34 – 21:47)

- 21:37 Birk liefert den ganzen Rahmen in einer Nachricht (614 Zeichen: vier
  Freundinnen, Nordkiez, Liebeskummer, Rassismus, Streit). Der Bot antwortet
  mit 768 Zeichen Belehrung („das ist ein klarer Rahmen, kein Kernthema") plus
  drei Richtungsvorschlägen plus einer Frage — und speichert erst danach.
- 21:42 Birk: „das haben wir doch gesagt. du hast es als rahmen interpretiert
  aber anzahl von figuren steckte drin" — die Figurenzahl stand seit 21:37 im
  Text, wurde nicht gelesen.
- 21:42 Notiert „drei Figuren: Leyla, Cemre, Aylin" → 21:43 Birk: „Wieso nur
  drei Figuren notiert? Wir wollten doch vier." → 21:43 Notiert „eine Figur:
  Zeynep". Zwei Meldungen für eine Entscheidung.
- 21:44 – 21:47: viermal dieselbe Interview-Zuordnungsfrage in Folge
  (mid 130, 132, 134, 142), jedes Mal mit derselben angehängten Figurenliste.

### Phase 6 · Szenen (21:48 – 21:54)

- 21:48 `/phase 6`. 21:49 der Bot bietet drei **Rahmen**-Vorschläge an
  (Szenenbilder, mid 144). Grundleiste darunter.
- **21:50 der Schaden:** „Gefällt uns, weiter" unter mid 144 schreibt
  `rahmen = "Leyla checkt ihr Handy auf dem Schulhof, die anderen beobachten
  sie von weitem"` und **überschreibt den Rahmen von 21:37** (vier Freundinnen
  im Nordkiez) stillschweigend. Journal-Zeile j5 ist der einzige Beleg.
- 21:50 mid 148 (1 303 Zeichen, **13 Fragezeichen**): der Bot fängt in Phase 6
  bei Phase 1 an — „Also: Rassismus, Liebe, Spaß, Streit … Ich würde aus diesen
  vier Begriffen Interviewfragen entwickeln". Birk: „wo ist du? es müsste jetzt
  szenen geschrieben werden."
- 21:51 Birk: „schreib nicht immer so viel zusammenfassung". 21:52 der Bot
  wiederholt die Notiert-Szenenfolge wortgleich (mid 151 == mid 154).
- 21:52 mid 156: die Figuren-Zuordnungsfrage zum fünften Mal, direkt vor dem
  Szenenauftrag.

## 3. Die zehn schlimmsten Stellen

| # | Zeit | Bot-Text (gekürzt) | Ursache | Fix |
| --- | --- | --- | --- | --- |
| 1 | 21:50 | *(kein Text — „Gefällt uns, weiter" unter einem Szenenbild-Vorschlag)* | **Code**: `knoepfe._ERSTER_ALS_WERT["rahmen"]` speichert die erste Zeile jeder `VORSCHLAG RAHMEN:`-Liste, egal ob `rahmen` schon gesetzt ist | (b) Leiste nur für Blöcke der offenen Art; gesetztes Feld ohne `aenderung_offen` wird nicht überschrieben |
| 2 | 21:50 | „Also: Rassismus, Liebe, Spaß, Streit … Ich würde aus diesen vier Begriffen Interviewfragen entwickeln" (13 ?) | **Prompt/Kontext**: kein Verbot, über abgeschlossene Phasen zu reden | (a)+(d) system.md: „Steht etwas im Arbeitsstand, frag nie erneut danach" |
| 3 | 21:44–21:52 | 5× „Leyla könnte wie Interview 1 sprechen -- passt das?" + Figurenliste | **Kontext**: `_baue_figurenhinweis` hat keinen Merkposten, steht in jedem Zug | (d) Wiederholungsfilter + Hinweis nur alle N Züge |
| 4 | 14:02–14:09 | 6× Meta-Antwort statt der drei erbetenen Fragen | **Prompt**: Regieanteil, kein „liefere, was erbeten wurde" | (a) Prompt-Regel „liefern statt kommentieren" |
| 5 | 21:37 | 768 Zeichen „das ist ein klarer Rahmen, kein Kernthema -- aber er trägt eins in sich…" vor dem Speichern | **Prompt**: belehren vor ablegen | (a) sofort speichern, eine Zeile bestätigen |
| 6 | 16:39 / 20:52 | „Bin wieder da. Wir sind bei 1 · Begriffe. Wenn ihr weitermachen wollt, sagt mir Bescheid" (falsche Phase, 2× wortgleich) | **Code**: `bot._TEXT_WIEDERKEHR`, `PAUSE_GRENZE_STUNDEN = 2` | (f) Schwelle 30 min ab letzter Nachricht, Phase aus `phasen.aktuelle`, Schlusssatz raus |
| 7 | 13×  | „Falls das nicht stimmt, sagt es mir." unter **jeder** Notiert-Zeile | **Code**: `erkenner.baue_meldung` | (e) raus — die Grundleiste sagt es bereits |
| 8 | 21:42/21:43 | „Notiert: drei Figuren" → „Notiert: eine Figur: Zeynep" | **Code/Prompt**: Figurenzahl aus Birks Rahmentext nicht gelesen | (a) Arbeitsstand-Regel; Figurenzahl aus dem Rahmen übernehmen |
| 9 | 21:52 | Notiert-Szenenfolge wortgleich zweimal (mid 151 == mid 154) | **Code**: kein Wiederholungsfilter | (d) `ablauf.antworte` verwirft Antworten > 60 % Deckung |
| 10 | 21:53 | „Ich schreibe die Szene aus, das dauert eine Minute - ihr könnt derweil weiterarbeiten." | **Code**: `_TEXT_*`-Systemzeilen mit Beiwerk | (e) Systemzeilen auf max. 2 Sätze, kein „ihr könnt derweil" |

## 4. Knopfnutzung

```
anders            7 angeboten,  6 gedrückt   ← Grundleiste wird benutzt
eigene            7 angeboten,  6 gedrückt
speichern         7 angeboten,  6 gedrückt
aufnahme          8 angeboten,  7 gedrückt
rahmen           11 angeboten,  0 gedrückt   ← Auswahlknöpfe: nie
kernthema         6 angeboten,  0 gedrückt
richtung          6 angeboten,  0 gedrückt
phase             9 angeboten,  0 gedrückt   ← der Weg weiter: nie
szene_usa         2 angeboten,  0 gedrückt
stand/hilfe       4 angeboten,  0 gedrückt
```

Zwei Befunde: die **Grundleiste funktioniert** (drei von drei Knöpfen ~86 %
Nutzung), die **Auswahllisten nicht** (0 von 23). Und der Phasenknopf wurde nie
gedrückt — er hing als vierter Knopf unter langen Texten. Deshalb Fix (c): die
Phasenfrage als eigene, kurze Nachricht, sobald alles gespeichert ist.

## 5. Was das für die Fixes heißt

- (a) **Speichern beim ersten Mal.** Median 20 Nachrichten je Speicherung ist
  die Zahl, die auf ≤ 2 muss. Der Hebel ist der Prompt, nicht der Code: der
  Erkenner speichert bereits sofort, der Gesprächs-Bot redet nur davor.
- (b) **Falscher Wert.** Ein einziger, aber teurer Fall. Reproduzierbar als
  Test aus j5.
- (c) **Proaktive Phasenmeldung.** 9 Phasenknöpfe, 0 Drücke — als Anhang wirkt
  der Knopf nicht.
- (d) **Wiederholungsfilter.** Der 60-%-Filter (`ablauf.ist_wiederholung`,
  Mindestlänge 12 inhaltstragende Wörter) fängt am Testkorpus **3 von 65**
  Bot-Nachrichten: die verdoppelte Fragen-Notiz (14:03), die doppelte
  „Bin wieder da"-Zeile (20:52) und den verdoppelten Szenenfolge-Block
  (21:50). Einschränkung, ehrlich: der Filter sitzt in `ablauf.antworte` und
  greift damit nur bei **Gesprächsantworten** — die drei genannten Fälle sind
  Systemzeilen bzw. Notiert-Zeilen und laufen an ihm vorbei. Er ist die
  Versicherung gegen ein Modell, das sich wiederholt; die Systemzeilen sind
  durch (e) und (f) direkt entschärft. Die größere Wirkung kommt aus der
  Prompt-Regel.
- (e) **Systemzeilen.** 13 × „Falls das nicht stimmt" = 13 überflüssige Zeilen
  in 104 Nachrichten.
- (f) **„Bin wieder da".** Zweimal falsch, zweimal wortgleich.

## 6. Auswertungsskript

```python
import sqlite3, re, collections
c = sqlite3.connect('file:betrieb/test.db?mode=ro', uri=True)
c.row_factory = sqlite3.Row
CID = -5257292234
rows = [dict(r) for r in c.execute(
    "select message_id,ist_bot,typ,text,gesendet_am from nachricht "
    "where chat_id=? order by gesendet_am", (CID,))]

def wm(t):   return {w for w in re.findall(r"\w+", (t or '').lower()) if len(w) > 3}
def jac(a,b):
    A,B = wm(a), wm(b);  return len(A&B)/len(A|B) if A|B else 0.0
def cont(a,b):                       # Anteil von a, der in b steckt
    A,B = wm(a), wm(b);  return len(A&B)/len(A) if A else 0.0

bot = [r for r in rows if r['ist_bot']]
print(sum(1 for i,r in enumerate(bot) if i and cont(r['text'], bot[i-1]['text']) > 0.6))
```

Nachrichten je Speicherung, Knopfnutzung und die Feld-Überschreibung kommen aus
`journal` bzw. `knopf` derselben Datenbank (Abfragen im Fließtext oben).

---

# Nachtrag 06.09.2026, 00:35 (Birks Zusätze)

Der Analysezeitraum reicht bis **00:35 CEST** (die DB speichert UTC; 22:32 UTC
= 00:32 CEST). Es kamen 28 weitere Nachrichten dazu, Phase 6, vier
Szenendurchläufe.

## 7. Birks Feedback im Chat als Anforderungsliste

Birk hat fünfmal direkt an den Bot geschrieben, was anders sein soll. Jeder
Satz ist eine Anforderung:

| Zeit | Feedback (wörtlich) | Umsetzung |
| --- | --- | --- |
| 21:50 | „wo ist du? es müsste jetzt szenen geschrieben werden. wir habengerade die reihenfolge festgelegt" | **Fix (3)** Kontextfenster: der Bot las den Vormittag als Gegenwart. Chronologie + 20-Nachrichten-/30-Minuten-Grenze. Zusätzlich system.md „Steht etwas im Arbeitsstand, frag nie erneut danach." |
| 21:51 | „schreib nicht immer so viel zusammenfassung, sondern nur die wichtigen fragen." | **Fix (a)** system.md: „Wiederhole nichts, was in deinen letzten drei Nachrichten oder im Journal steht. Keine Zusammenfassung des Standes, außer auf `/stand`." + **Fix (d)** Wiederholungsfilter im Code. |
| 21:52 | „Stell immer nur eine Frage auf einmal. Hier müsste kein großes Menu / Buttons sein, osndernnur sprahcantwort" | **Teilweise.** Umgesetzt: system.md „Eine Frage je Nachricht, höchstens. Sind es zwei, streichst du die schwächere." — Zahlenbeleg: 161 Fragezeichen in 59 Bot-Nachrichten. **Nicht umgesetzt:** „keine Buttons bei Szenenaufträgen". Begründung: die Grundleiste ist der einzige Weg, der am Testabend nachweislich funktioniert hat (86 % Nutzung gegen 0 % bei den Auswahllisten); sie ersatzlos zu streichen würde das Speichern wieder unsicher machen. Was stattdessen wegfällt, sind die **Auswahllisten** über der Leiste — 0 von 23 gedrückt. Das ist eine eigene Entscheidung für Birk, kein Fix, den ein Agent allein trifft. |
| 21:53 | „Du wiederholfst dich. das enzige was hier wichtig ist, ist das US-Modell zu wählen udn das du dann szene 1 schreist und ausgibst" | **Fix (2)** `ablauf.ist_auftrag`: löst eine Nachricht einen Auftrag aus, schweigt der Gesprächs-Bot. |
| 22:27 | „Du hast nicht auf meine Frage geantwortet und das was du hier schreibst doppelt sich überall. Die ganzen Zeilen sind doppelt." | **Fix (3)** — das Doppeln der Zeilen ist eine direkte Folge des rückwärts sortierten Fensters, in dem jede Notiert-Zeile und jedes „Bin wieder da" mehrfach stand. Systemzeilen sind jetzt aus dem Fenster gefiltert. |

## 8. Muster „Gesprächs-Bot redet parallel zu einem Auftrag"

Gezählt: **14 Fälle**, in denen eine Gesprächsantwort unmittelbar (≤ 1 min,
derselbe Auslöser) vor einer Systemzeile stand. Sie zerfallen in zwei Gruppen:

- **2 echte Doppelungen** (21:53 mid 160 vor dem USA-Hinweis; **00:30 mid 189**
  „Birk, klar -- Szene 1 neu. Eine Frage dazu: … Soll der Typ wirklich
  kommen?" eine Sekunde vor „Ich schreibe die Szene aus"). Hier hat der Bot
  einen Auftrag kommentiert statt ihn auszuführen — **Fix (2)**.
- **12 Notiert-Zeilen** nach einer Gesprächsantwort. Die sind bauartbedingt:
  der Erkenner läuft absichtlich *nach* dem Zug, damit er die Bot-Antwort
  mitliest. Sie sind kein Fehler, solange die Gesprächsantwort den Wert nicht
  auch noch nacherzählt — genau das verbietet jetzt die system.md-Regel
  „Nennt die Gruppe einen Wert, ist er gesetzt … du wiederholst ihn nicht im
  Text: die Notiert-Zeile zeigt ihn ohnehin."

`ablauf.ist_auftrag` fängt am Testkorpus **1** Nachricht („neu schreiben").
Die Liste ist bewusst eng gehalten: eine fälschlich unterdrückte Antwort ist
teurer als eine überflüssige. „Schreib Szene 1. Stell immer nur eine Frage auf
einmal." (21:52) fällt bewusst **nicht** darunter — die Regieanweisung darin
darf nicht verlorengehen.

## 9. Kontextfenster (der schwerste Befund)

Gemessen: der Nutzertext eines Zuges hatte **52 000 Zeichen**, das Fenster
reichte ~700 Zeilen bis in den Vormittag zurück — und stand **rückwärts**
darin.

**Ursache, verifiziert:** `repo.letzte_nachrichten` sortiert
`ORDER BY message_id ASC`. Die aus Gruppe 1 übernommene Historie trägt aber
**negative, absteigend vergebene** message_ids (45 Stück, von −256 abwärts):

```
message_id ASC liefert:   -319 (20:52) → -318 (16:39) → -308 (14:33) → …
gesendet_am liefert:      -256 (13:15) → -258 (13:41) → -259 (13:55) → …
```

Die älteste Nachricht steht damit *zuletzt*, die jüngste *zuerst*. Deshalb
antwortete Kimi um 21:50 in Phase 6: „Das ist Tag 1 und wir stehen erst am
Anfang. Also: Rassismus, Liebe, Spaß, Streit." — der Vormittag stand oben im
Fenster und sah nach Gegenwart aus.

**Fix (3):** `kontext._baue_fenster_eintraege` sortiert nach `gesendet_am`,
begrenzt auf `FENSTER_NACHRICHTEN = 20` **oder** `FENSTER_MINUTEN = 30` (was
kleiner ist) und filtert Systemzeilen (`_SYSTEMANFAENGE`: „Bin wieder da",
„Notiert:", „Aufnahme läuft", USA-Hinweis, „Ich schreibe die Szene aus" …).
Bezugspunkt der Zeitgrenze ist die auslösende Nachricht, nicht `jetzt` — damit
ein Nachlauf dasselbe Fenster sieht wie der Livezug.

## 10. Nicht gefixt: `arbeitsstand.phase = 7`

Die Testgruppe steht auf `phase = 7`, `phase_angeboten = 8`, während das
Journal als letzten Phaseneintrag „Phase 6 · Szenen" (21:48, Quelle `befehl`)
führt und die Gruppe an Szene 1 arbeitete. Das passt zur Umnummerierung des
Phasen-Umbaus (`db.PHASEN_SCHEMA`: 6 → 7, 7 → 8) — die Gruppe war in der alten
Zählung in 6 und ist mitgewandert, während die Journal-Zeile den alten Text
behielt. **Nicht in diesem Branch angefasst**: liegt im Zuständigkeitsbereich
des Phasen-Umbaus. Der Phasen-Agent sollte prüfen, ob die Migration auch die
Journal-Texte bzw. den Wert für Gruppen mitziehen muss, die zum
Migrationszeitpunkt mitten in Phase 6 standen.
