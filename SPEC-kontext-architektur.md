# Spezifikation: Kontext- und Gedächtnis-Architektur

**Theater-Soap-Bot** · Stand 03.09.2026 · Ersteinsatz Workshop Dortmund 05.+06.09.2026

Diese Spezifikation deckt die Kontext- und Gedächtnis-Architektur ab: was bei jedem
LLM-Aufruf in den Kontext wandert, wie das Budget überwacht wird, wie der Zustand
einen Neustart überlebt und wie sich das System bei Fehlern verhält.

Nicht Teil dieser Spezifikation: das Dashboard (liest nur mit), die Whisper-Anbindung
im Detail, das Deployment.

---

## 0. Leitsätze

Fünf Sätze, aus denen sich fast jede Detailentscheidung unten ableiten lässt:

1. **Beim Empfangen großzügig, beim Zusammenbauen streng.** Etwas nicht aufzunehmen ist
   unumkehrbar; etwas aufzunehmen und nicht in den Prompt zu legen kostet Kilobyte.
2. **Wir bemessen nicht gegen das Fenster des Modells, sondern gegen ein Qualitätsbudget.**
   Der Grund zu kürzen ist Schärfe, nicht Kapazität.
3. **Phasenbewusstsein ist ein Nebenprodukt der Materiallage, kein Zustand.** Es gibt keine
   Phasen-Zustandsmaschine; der Prompt wächst mit dem, was in der DB steht.
4. **Kein Aufruf im kritischen Pfad, der nicht sein muss.** Nebenaufgaben laufen
   nachgelagert und ins Leere: Fehlschlag heißt fehlender Eintrag, nicht angehaltener Workshop.
5. **Die Gruppe erfährt von einem Fehler nur, wenn sie ihn beheben kann oder wenn sie
   gerade darauf wartet.** Alles andere geht ans Dashboard.

---

## 1. Empfangen, Antworten, In-den-Prompt-legen

Drei getrennte Entscheidungen. Diese Trennung ist die Grundlage der gesamten Architektur.

### 1.1 Empfangen

**Privacy Mode bei BotFather ausgeschaltet.** Der Bot empfängt jede Nachricht der Gruppe.
Ohne das erreichen Sprachnachrichten den Bot nur als Reply — Sprachnachrichten haben in
Telegram keine Bildunterschrift, sie können nicht `@`-erwähnt werden. Ein Interview, das
verlorengeht, weil jemand unter Stress nicht auf „Antworten" getippt hat, ist der teuerste
Fehler im System.

**Alles wird roh gespeichert**, unabhängig von Typ und Adressat: Text, Sprache, Fotos,
Sticker, Bot-Antworten, Bearbeitungen. Nicht unterstützte Typen werden als Zeile im Log
vermerkt und lösen nichts aus — sie dürfen unter keinen Umständen einen Absturz auslösen.

**Datenschutz:** Die Teilnehmerinnen werden zu Beginn eingeführt, es gibt eine Löschzusage.
Siehe § 9.3 zum Löschweg.

### 1.2 Antworten

Der Bot antwortet auf:

- **Reply** auf eine seiner eigenen Nachrichten
- **`@botname`-Erwähnung**
- **`/`-Befehle**
- **Sprachnachrichten** (immer — sie sind Material, nie Geplänkel)
- **eine offene Rückfrage-Sequenz**, die er selbst eröffnet hat (§ 1.4)

Auf alles andere antwortet er nicht. In seiner **allerersten Nachricht in der Gruppe**
schreibt der Bot selbst hin, wie man ihn anspricht — damit das Workshop-Team es nicht
erklären muss.

### 1.3 Sammeln statt parallel arbeiten

Läuft für eine `chat_id` bereits ein Gesprächsaufruf, werden eingehende Nachrichten normal
geloggt, lösen aber **nichts** aus. Kommt die Antwort zurück, wird alles seither Aufgelaufene
**als ein einziger nächster Zug** behandelt.

Umsetzung: eine Sperre pro `chat_id`. Der auslösende Block ist ohnehin definiert als
„alles seit `letzte_beantwortete_message_id`", das Sammeln fällt damit fast von selbst heraus.

Ohne diese Sperre startet jede Nachricht ihren eigenen Aufruf: drei parallele Anfragen, drei
teils widersprüchliche Antworten in zufälliger Reihenfolge, und ein Extraktor-Wasserzeichen,
das sich verheddert. Das ist der wahrscheinlichste Weg, wie der Bot am Samstagvormittag
chaotisch wirkt.

**Vorbeugend:** Solange ein Aufruf läuft, alle 4 Sekunden `sendChatAction("typing")`.
Nach 10 Sekunden zusätzlich eine kurze Zeile („einen Moment, ich denke nach"). Die meiste
Ungeduld entsteht daraus, dass gar nichts passiert.

### 1.4 Offene Rückfrage-Sequenz

Laien nutzen die Reply-Funktion selten. Stellt der Bot eine Rückfrage, muss die nächste
Nachricht als Antwort zählen dürfen.

**Deterministisch, ohne LLM.** Das Merkmal wird ausschließlich bei **code-initiierten**
Rückfragen gesetzt — nicht bei Fragen, die das Modell formuliert:

| Rückfrage | Gesetzt bei |
|---|---|
| `interview_name` — „Wer wurde da interviewt?" | nach erfolgreicher Transkription |
| `interviews_fertig` — „War das das letzte Interview?" | nach der n-ten Verdichtung (optional, § 10) |

Regeln:

- Feld `gruppe.offene_rueckfrage` + `rueckfrage_gestellt_am`.
- **Verfall nach 10 Minuten.**
- **Verbrauch durch die nächste menschliche Nachricht** in der Gruppe — danach wird das Feld
  in jedem Fall geleert.
- Ist die Nachricht ein `/`-Befehl, gilt sie nicht als Antwort; die Sequenz bleibt bis zum
  Verfall stehen.
- **Die Rückfrage wird nie wiederholt.** Passt die Antwort nicht (z. B. kein plausibler Name),
  bleibt der Ersatzname `Interview n` stehen und der Bot arbeitet stillschweigend weiter.
  Ein Bot, der zweimal dasselbe fragt, nervt mehr, als ein unbenanntes Interview kostet.

**Abschaltbarer Zusatzschalter, standardmäßig AUS:** `SEQUENZ_BEI_FRAGEZEICHEN`. Wenn an,
öffnet jede Bot-Antwort, die mit `?` endet, ein 2-Minuten-Fenster. Erhöht die Geschmeidigkeit,
riskiert aber, dass der Bot auf „ok cool" antwortet. Nicht am Workshoptag erstmals erproben.

---

## 2. Die Gedächtnisschichten

| Schicht | Inhalt | Wird aktualisiert? |
|---|---|---|
| **1 — Material** | Volltranskript + Verdichtung je Interview | Verdichtung **nie** |
| **2 — Arbeitsstand** | Begriffe, Kernthema, Figuren, Konflikt, Szenen | ja, jederzeit revidierbar |
| **2b — Journal** | Vorgeschlagen / Verworfen / Entschieden / Offen | **nur anhängen** |
| **3 — Kurzes Fenster** | die letzten ~2.500 Token Chatverlauf | rollt von selbst |

**Warum das Journal (2b) existiert.** Drei Dinge stehen im Chatverlauf, aber in keiner
anderen Schicht — und alle drei sind zeitlich weit weg und inhaltlich zentral:

1. **Verworfenes.** „Die Frage hatten wir schon, zu privat." Ohne Journal schlägt der Bot um
   16:00 nochmal vor, was um 11:00 abgelehnt wurde — der Moment, in dem eine Gruppe das
   Vertrauen verliert.
2. **Entwürfe in der Schwebe.** Sechs vorgeschlagene Interviewfragen, seit zwanzig Minuten
   diskutiert, nichts entschieden. Keine Entscheidung, also nicht in Schicht 2 — und aus dem
   kurzen Fenster längst rausgerollt.
3. **Das Warum hinter Entscheidungen.** Schicht 2 hält fest, *dass* das Kernthema X ist.
   Warum, braucht der Bot zwei Phasen später bei den Figuren.

**Warum kein Rolling Summary.** Eine periodische Neuverdichtung des Verlaufs bräuchte einen
LLM-Aufruf zu unvorhersehbaren Zeitpunkten (neuer Fehlerpunkt genau unter Volllast), würde
Zusammenfassungen von Zusammenfassungen erzeugen (Drift über zwei Tage) und widerspricht der
Regel, dass Verdichtungen nicht nachträglich angefasst werden. Ein Journaleintrag kostet
15–30 Token; 40 Einträge über zwei Tage sind ~1.000 Token und müssen nie aufgeräumt werden.

**Konsequenz für das kurze Fenster: kein Relevanzfilter nötig.** Das Fenster umfasst nur
wenige Minuten. „Ich hol mir Kaffee" ist darin harmlos, weil es Teil des laufenden Gesprächs
ist und nicht stundenlang mitgeschleppt wird. Verwässerung wird durch Kürze des Fensters plus
Selektivität des Journals verhindert, nicht durch einen Filter, der raten muss.

---

## 3. Datenbank

Eine gemeinsame SQLite für alle Bots. **Beim Verbindungsaufbau zwingend:**

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
```

WAL allein reicht nicht. Ohne `busy_timeout` wirft SQLite bei gleichzeitigem Schreiben
sofort `SQLITE_BUSY` statt kurz zu warten — der klassische stille Killer bei mehreren
Prozessen auf einer Datei, und er tritt genau dann auf, wenn alle drei Gruppen gleichzeitig
arbeiten.

**Jede Tabelle außer `bot_zustand` hat `chat_id`.** Kein Ableiten über Umwege, keine Tabelle
ohne. Das macht die Löschzusage zu einem `DELETE … WHERE chat_id = ?` je Tabelle.

### 3.1 Schema

```sql
-- Pro Bot-Token, nicht pro Gruppe: die getUpdates-Position
CREATE TABLE bot_zustand (
  bot_name              TEXT PRIMARY KEY,
  letzte_update_id      INTEGER,
  gestartet_am          TEXT,
  letzte_aktivitaet_am  TEXT
);

CREATE TABLE gruppe (
  chat_id                         INTEGER PRIMARY KEY,
  bot_name                        TEXT NOT NULL,
  titel                           TEXT,
  erste_nachricht_am              TEXT,
  -- Antwort- und Extraktionsstand
  letzte_beantwortete_message_id  INTEGER DEFAULT 0,
  letzte_extrahierte_message_id   INTEGER DEFAULT 0,
  -- Schalter
  wortlaut_modus                  TEXT,     -- NULL=aus, '*'=alle, sonst Interviewname
  gruendlich_naechster_zug        INTEGER NOT NULL DEFAULT 0,  -- Modus B einmalig (§ 4.5)
  offene_rueckfrage               TEXT,     -- NULL | 'interview_name' | 'interviews_fertig'
  rueckfrage_kontext_id           INTEGER,  -- z.B. interview.id
  rueckfrage_gestellt_am          TEXT
);

CREATE TABLE nachricht (
  chat_id        INTEGER NOT NULL,
  message_id     INTEGER NOT NULL,
  telegram_user  INTEGER,
  absender       TEXT,                      -- Vorname oder 'Bot'
  ist_bot        INTEGER NOT NULL DEFAULT 0,
  typ            TEXT NOT NULL,             -- text|sprache|foto|sticker|sonstiges
  text           TEXT,
  gesendet_am    TEXT NOT NULL,             -- ISO 8601
  unterdrueckt   INTEGER NOT NULL DEFAULT 0,-- 1 = nie Antwort auslösen (Nachtstau)
  PRIMARY KEY (chat_id, message_id)
);
CREATE INDEX idx_nachricht_zeit ON nachricht(chat_id, message_id);

CREATE TABLE interview (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  message_id      INTEGER NOT NULL,
  name            TEXT,                     -- 'Maria'; Ersatz: 'Interview 3'
  audio_pfad      TEXT,
  transkript      TEXT,
  dauer_sekunden  INTEGER,
  status          TEXT NOT NULL,            -- empfangen|transkribiert|verdichtet|fehlgeschlagen
  fehlertext      TEXT,
  versuche        INTEGER NOT NULL DEFAULT 0,
  empfangen_am    TEXT NOT NULL
);
CREATE INDEX idx_interview_offen ON interview(status);

CREATE TABLE verdichtung (
  id               INTEGER PRIMARY KEY,
  chat_id          INTEGER NOT NULL,
  interview_id     INTEGER NOT NULL,
  zusammenfassung  TEXT NOT NULL,
  erstellt_am      TEXT NOT NULL
);

CREATE TABLE verdichtung_thema (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  verdichtung_id  INTEGER NOT NULL,
  thema           TEXT NOT NULL,
  beleg_zitat     TEXT,                     -- NULL, wenn Prüfung nach § 5 fehlschlug
  zitat_geprueft  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE arbeitsstand (
  chat_id                INTEGER PRIMARY KEY,
  begriffe               TEXT,
  kernthema              TEXT,
  kernthema_begruendung  TEXT,
  hauptkonflikt          TEXT,
  geaendert_am           TEXT
);

CREATE TABLE figur (
  id            INTEGER PRIMARY KEY,
  chat_id       INTEGER NOT NULL,
  name          TEXT NOT NULL,
  beschreibung  TEXT,
  beleg_zitat   TEXT,
  geaendert_am  TEXT
);

CREATE TABLE szene (
  id                INTEGER PRIMARY KEY,
  chat_id           INTEGER NOT NULL,
  nummer            INTEGER,
  titel             TEXT,
  kurzbeschreibung  TEXT,                   -- eine Zeile, geht immer mit
  volltext          TEXT,                   -- nur die zuletzt geänderte Szene geht mit
  geaendert_am      TEXT NOT NULL
);
CREATE INDEX idx_szene_aktuell ON szene(chat_id, geaendert_am DESC);

CREATE TABLE journal (
  id                INTEGER PRIMARY KEY,
  chat_id           INTEGER NOT NULL,
  art               TEXT NOT NULL,          -- vorgeschlagen|verworfen|entschieden|offen
  text              TEXT NOT NULL,
  quelle            TEXT NOT NULL,          -- extraktor|befehl
  bis_message_id    INTEGER,
  erstellt_am       TEXT NOT NULL
);
CREATE INDEX idx_journal_chat ON journal(chat_id, id);

-- Was das Dashboard rot färbt
CREATE TABLE vorfall (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER,                     -- NULL bei bot-weiten Vorfällen
  bot_name     TEXT,
  art          TEXT NOT NULL,               -- kuerzung|fenster_verworfen|extraktor_fehler|
                                            -- zitat_ungeprueft|http_5xx|abgeschnitten|…
  stufe        INTEGER,
  detail       TEXT,
  erstellt_am  TEXT NOT NULL
);

-- Selbstkorrektur der Token-Schätzung
CREATE TABLE aufruf (
  id                     INTEGER PRIMARY KEY,
  chat_id                INTEGER,
  art                    TEXT NOT NULL,     -- gespraech|verdichter|extraktor
  modus                  TEXT,              -- A|B
  geschaetzte_token      INTEGER,
  tatsaechliche_token    INTEGER,           -- usage.prompt_tokens
  antwort_token          INTEGER,
  finish_reason          TEXT,
  dauer_ms               INTEGER,
  erfolg                 INTEGER,
  erstellt_am            TEXT NOT NULL
);
```

---

## 4. Die drei Prompts

Das ganze System hat **drei** Prompts, nicht einen pro Phase. Zwei davon sind winzig und
stehen außerhalb des Gesprächs. Nur einer ist qualitätskritisch.

### 4.1 Gesprächs-Prompt

**Entschieden nach Messung vom 03.09.2026: `GESPRAECH_REASONING = "none"`, erzwungenes Schema
wo strukturierte Ergebnisse anfallen (Modus A).**

Messaufbau: Kimi K2.6 über Infomaniak, erfundenes Interview-Transkript (~350 Wörter), Aufgabe
„drei Hauptkonflikte mit Titel, Beschreibung und Belegzitat", je 3–4 Läufe.

| | **Modus A** (Schema, `none`) | **Modus B** (Prosa, `medium`) |
|---|---|---|
| Valide Antworten | 3/3 | 4/4 |
| Latenz | **4,5 s** | 33,8 s |
| Belegzitate wörtlich | 7/9 (2/9 mit `[...]` gekürzt, **0/9 erfunden**) | 12/12 |
| Gefundene Konfliktachsen | dieselben drei | dieselben drei |

**Modus A ist nicht thematisch flacher.** Er findet dieselben Achsen und formuliert Titel und
Beschreibungen, die den Konflikt als Konflikt fassen. Der Unterschied liegt nicht in der
Substanz, sondern in drei Nebenpunkten:

1. **Konsistenz über Läufe** — ein A-Lauf von dreien fiel in Zitatdisziplin und
   Beschreibungstiefe ab.
2. **Zitatgenauigkeit** — derselbe Lauf klebte mit `[...]` zwei weit auseinanderliegende
   Interviewstellen zusammen.
3. **Sprachliche Textur** — B formuliert relationaler, A analytischer.

**Ausschlaggebend ist die Latenz.** 33,8 Sekunden wären im Gruppenchat keine Bedenkzeit,
sondern eine Gesprächspause, in der drei Leute nachfragen, ob der Bot noch lebt — genau die
Situation, gegen die § 1.3 gebaut ist. Gleiche Substanz bei 7,5-fachem Tempo entscheidet die
Frage.

**Der zweistufige Weg entfällt.** Erst freier Text, dann ein zweiter Aufruf zum
In-Struktur-Gießen ist nicht nötig; A liefert beides in einem Aufruf.

**Das einzige gemessene Risiko von A ist die Zitatdisziplin — und die wird serverseitig
abgefangen (§ 5), nicht durch Modellvertrauen.** Punkt 1 und 3 der Abweichungsliste sind
Nebenpunkte; Punkt 2 ist ein echtes Risiko, aber ein billig prüfbares.

Freier Fließtext bleibt das Format der eigentlichen Chat-Antwort. Wo dabei dramaturgische
Artefakte anfallen (Konflikte, Figuren, Kernthemen mit Zitat), werden sie im selben Aufruf
über das Schema mitgeliefert und in den Arbeitsstand geschrieben.

Detaillierter Kontext-Aufbau: § 6.

### 4.2 Verdichter

Läuft **einmal je Interview** auf dem frischen Transkript. Kennt den Chatverlauf nicht.
Erzwungenes Schema, `reasoning_effort: "none"`.

```json
{
  "zusammenfassung": "3-5 Sätze",
  "kernthemen": [
    {"thema": "kurz", "beleg_zitat": "wörtlich aus dem Transkript"}
  ]
}
```

**Belegzitate sind Pflicht, nicht Zierde.** Erstens sieht die Gruppe sofort, wenn das Modell
etwas hineingelesen hat, was nicht da war. Zweitens braucht der Bot sie später ohnehin: ein
Konfliktvorschlag mit Beleg ist Dramaturgie, einer ohne ist ein Automat. Der Prompt weist
ausdrücklich an, nur wörtlich vorkommende Passagen zu zitieren; **jedes Zitat durchläuft
zusätzlich die Prüfung nach § 5.**

Das Ergebnis wird **nie aktualisiert.**

### 4.3 Extraktor

Nachgelagert, nachdem die Bot-Antwort bereits in der Gruppe steht. **Niemand wartet darauf.**
Erzwungenes Schema, `reasoning_effort: "none"`.

```json
{
  "eintraege": [
    {"art": "vorgeschlagen|verworfen|entschieden|offen", "text": "eine knappe Zeile"}
  ]
}
```

- **Auslöser:** nach jeder Bot-Antwort, über alles seit `letzte_extrahierte_message_id`.
  Zusätzlich als Netz ein Token-Schwellwert (1.500), falls die Gruppe lange untereinander
  redet, ohne den Bot anzusprechen.
- **Die leere Liste ist der ausdrückliche Normalfall.** Der Prompt sagt das explizit. Ein
  Extraktor, der immer etwas liefern *muss*, erfindet Bedeutung in „ich hol mir Kaffee"
  hinein — das wäre Verwässerung durch die Hintertür.
- **Fehlschlag:** Wasserzeichen bleibt stehen, das Fenster wird beim nächsten Mal
  mitgelesen — ein kostenloser Wiederholungsversuch ohne eigene Retry-Logik. Nichts wird
  der Gruppe gemeldet, eine Zeile ins Log.
- **Deckel:** Überschreitet das unbearbeitete Fenster ~4.000 Token, wird das Wasserzeichen
  trotzdem vorgerückt und das Fenster fallengelassen — plus **`vorfall`-Eintrag
  `fenster_verworfen`**, damit das Workshop-Team es im Dashboard sieht, ohne im Log zu graben.

### 4.4 Defensives Parsen (alle Schema-Prompts)

Erste Messung (Vorprojekt `kollektivgedaechtnis`, `kg/llm.py`): valides JSON bei erzwungenem
Schema nur mit `reasoning_effort: "none"` — ohne das Feld 0/5, mit `"low"` 0/8, mit `"none"`
8/8. Zwei Fehlerbilder trotz HTTP 200:

1. Inhalt beginnt mit `{{` statt `{`
2. Text steht in `message.reasoning`, `content` ist `null`

**In der Messung vom 03.09.2026 trat `{{` in keinem einzigen der Aufrufe auf.** Die Reparatur
bleibt trotzdem drin: sie kostet zwei Zeilen, und ein Fehlerbild, das man einmal gesehen hat,
verschwindet nicht dadurch, dass es beim zweiten Messen ausblieb.

```
inhalt = antwort.choices[0].message.content
if not inhalt: inhalt = antwort.choices[0].message.reasoning
if not inhalt: -> Fehlschlag
inhalt = inhalt.strip()
if inhalt.startswith("{{"): inhalt = inhalt[1:]
# ersten vollständigen {...}-Block extrahieren, dann json.loads
```

Schlägt es fehl: kein Eintrag, keine Meldung an die Gruppe, `vorfall`-Eintrag.

### 4.5 Modus B als bewusste Eskalation

Modus B (freier Prosatext, `reasoning_effort: "medium"`) bleibt verfügbar für die **wenigen
Momente, in denen Tiefe vor Tempo geht** — Szenentext-Entwurf und finale Konfliktverdichtung.
Dort ist B relationaler formuliert und in der Zitatdisziplin fehlerfrei (12/12), und eine
halbe Minute Wartezeit ist vertretbar, wenn die Gruppe weiß, worauf sie wartet.

- **Ausgelöst durch `/gruendlich`**, nicht durch Aufgabenerkennung — es gibt keinen
  Klassifikator und keine Zustandsmaschine (§ 6.1). Der Bot darf den Befehl von sich aus
  anbieten, wenn es um Szenentext geht.
- **Einmalig, nicht klebrig.** Der Schalter gilt für den nächsten Zug und wird danach
  zurückgesetzt. 34 Sekunden pro Zug wären als Dauerzustand quälend.
- **Angekündigt.** Vor dem Aufruf eine kurze Zeile: „Ich nehme mir dafür mehr Zeit — das
  dauert etwa eine halbe Minute." Ohne Ankündigung ist die Latenz ein Defekt, mit
  Ankündigung eine Zusage.
- **`max_tokens` ≥ 9.000 zwingend** (§ 11.3).
- `aufruf.modus` hält fest, welcher Modus lief — damit im Dashboard sichtbar ist, ob
  `/gruendlich` überhaupt genutzt wurde.

---

## 5. Belegzitat-Verifikation (Pflicht)

**Kein Belegzitat geht an die Gruppe, bevor es gegen das Transkript geprüft wurde.** Das gilt
für den Verdichter (§ 4.2) und für jedes Zitat, das der Gesprächs-Prompt in einem Vorschlag
mitliefert.

Begründung: Die Messung zeigt, dass Modus A **nichts erfindet** (0/9 frei erfundene Zitate),
aber **kürzt** (2/9 mit `[...]`) und in einem Lauf zwei weit auseinanderliegende Stellen
zusammenklebte. Ein Zitat ist der Beleg, an dem die Gruppe die Behauptung prüft — ein
ungenaues Zitat ist schlimmer als keins, weil es Prüfbarkeit vortäuscht. Die Prüfung ist ein
Teilstring-Vergleich und kostet nichts.

### 5.1 Verfahren

1. **Normalisieren**, auf beiden Seiten gleich: Whitespace-Folgen zu einem Leerzeichen,
   typografische Anführungszeichen (`„ " " ' ' »«`) auf gerade, Bindestrich-Varianten
   vereinheitlichen, Groß-/Kleinschreibung beibehalten (sonst wird die Prüfung zu lasch).
2. **Teilstring-Vergleich** gegen das normalisierte Transkript.
3. **Bei `[...]`**: am Auslassungszeichen aufteilen und **jedes Segment einzeln** prüfen.
   Segmente unter 15 Zeichen werden verworfen statt geprüft — kurze Fragmente treffen
   zufällig.
4. **Zusätzlich bei `[...]`**: die Segmente müssen im Transkript **in derselben Reihenfolge**
   vorkommen und dürfen **höchstens 600 Zeichen** auseinanderliegen. Ohne diese Regel besteht
   genau der gemessene Fehler die Prüfung — zwei je für sich wörtliche Segmente von weit
   auseinanderliegenden Stellen, zu einer scheinbaren Aussage verschweißt.

### 5.2 Verhalten bei Fehlschlag

1. **Genau ein Retry** desselben Aufrufs, mit dem Hinweis im Prompt, dass wörtlich zitiert
   werden muss und Auslassungen unzulässig sind.
2. Schlägt auch der fehl: **Vorschlag ohne Zitat ausliefern, nicht den Vorschlag verwerfen.**
   Die dramaturgische Substanz stimmt laut Messung auch dann; nur der Beleg fehlt. Ein
   Vorschlag ohne Beleg ist schwächer als einer mit — aber gar kein Vorschlag hält die Gruppe
   auf, und das ist die teurere Sorte Fehler.
3. `verdichtung_thema.beleg_zitat = NULL`, `zitat_geprueft = 0`.
4. **`vorfall`-Eintrag `zitat_ungeprueft`** mit dem verworfenen Zitat im Detailfeld. Das
   Workshop-Team sieht im Dashboard, wo der Bot ohne Beleg unterwegs war.
5. **Der Gruppe wird nichts gemeldet** (Leitsatz 5) — sie kann es nicht beheben und wartet
   nicht darauf.

---

## 6. Zusammenbau des Gesprächs-Prompts

### 6.1 Prinzip

**Ein einziger Zusammenbau, datengetrieben statt aufgabengetrieben.** Jeder Block wird
weggelassen, solange er leer ist. Am Samstagvormittag gibt es Begriffe und sonst nichts —
also enthält der Prompt Begriffe und sonst nichts. Sonntag existieren Kernthema und vier
Figuren — die stehen drin. Der Prompt wächst entlang des Workshops, **ohne dass irgendwo eine
Phase erkannt, gespeichert oder umgeschaltet wird.**

Warum nicht je Aufgabe ein eigener Zusammenbau: dafür müsste der Code wissen, welche Aufgabe
läuft — also über eine Phasen-Zustandsmaschine (ausgeschlossen) oder eine LLM-Klassifikation
im kritischen Pfad (neuer Fehlerpunkt, der die Antwort blockiert). Teuerster Weg zum
kleinsten Gewinn. Biegt die Gruppe ab, ändert sich die Materiallage und der Prompt folgt
automatisch — es gibt keinen Zustand, der ihr widersprechen kann.

**Reihenfolge: stabil nach vorn, flüchtig nach hinten.** Vorn, weil Prompt-Caching nur einen
byteweise identischen Präfix wiedererkennt. Hinten, weil das Modell dem Ende des Prompts das
meiste Gewicht gibt. Beide Interessen zeigen in dieselbe Richtung.

### 6.2 Blöcke und Budgets

Zielgröße Normalfall **~10.000 Token**, Reißleine **20.000**. Weit unter Kimis Fenster — und
genau darum funktioniert es.

| # | Block | Budget | Ändert sich | Entfällt wenn |
|---|---|---:|---|---|
| 1 | **Systemanweisung** | 900 | nie | – |
| 2 | **Verdichtungen** (mit Belegzitaten) | 3.000 | je Interview 1× | keine Interviews |
| 3 | **Volltranskripte** | 5.000 | nie | `/wortlaut` aus (Normalfall) |
| 4 | **Arbeitsstand** (Begriffe, Kernthema + Begründung, Figuren, Konflikt, Szenenliste) | 1.200 | je Entscheidung | Feld leer |
| 5 | **Aktuelle Szene im Volltext** | 1.500 | oft | keine Szene |
| 6 | **Journal** (ältestes zuerst) | 1.500 | alle paar Züge | leer |
| 7 | **Kurzes Fenster** (von hinten gefüllt) | 2.500 | jede Nachricht | – |
| 8 | **Auslösende Nachricht(en)** | 300 | immer | – |

Normalfall ohne `/wortlaut`: **~9.600 Token.** Mit: ~14.600.

**Zu Block 3.** Volltranskripte lassen sich nicht datengetrieben schalten — sie existieren ab
Samstagmittag dauerhaft, gebraucht werden sie nur beim Szenen-Feinschliff. Automatisch
mitgenommen wären sie 5.000 Token Dauerlast, die bis Sonntag jede Antwort unschärfer macht.
Deshalb der klebrige Schalter `/wortlaut` (§ 8). Die Systemanweisung sagt dem Bot, dass er
diesen Schalter kennt und von sich aus anbieten soll, wenn die Gruppe nach dem Originalton
fragt.

**Zu Block 5.** Fertige Szenentexte sind lang — sechs Szenen à 800 Wörter wären 6.000 Token
Dauerlast. Block 4 hält deshalb nur Szenentitel plus je eine Zeile; Block 5 die **eine
zuletzt geänderte Szene** im Volltext:
`SELECT … FROM szene WHERE chat_id=? ORDER BY geaendert_am DESC LIMIT 1`.
Wieder datengetrieben, kein Zustand: woran die Gruppe zuletzt gearbeitet hat, ist die Szene,
um die es gerade geht — springt sie zurück, folgt der Prompt automatisch.

**Zu Block 6.** Läuft praktisch nie über. Falls doch, wird nicht das Älteste gestrichen,
sondern nach Rang: `entschieden` und `verworfen` bleiben, `offen` und `vorgeschlagen` fallen
zuerst. Fünf Zeilen Code, die den einzigen unbegrenzt wachsenden Pfad im System zumachen.

**Zu Block 7.** Gefüllt von hinten, in Token statt Nachrichten bemessen — im Gruppenchat
können „N Nachrichten" vier Redebeiträge oder vierzig Sekunden Geplänkel sein. Jede Zeile
mit Sprechername vorangestellt, Bot-Antworten eingeschlossen.

**Pausenmarkierung.** Überschreitet der Abstand zwischen zwei Nachrichten im Fenster
**60 Minuten**, wird eine Zeile eingeschoben: `[Pause: 18 Stunden]`. Eine Zeitdifferenz und
ein String — der Bot begrüßt die Gruppe danach von selbst angemessen, ohne einprogrammiertes
Begrüßungsverhalten. Fängt Mittagspause und Übernachtung gleichermaßen ab.

### 6.3 Inhalt der Systemanweisung

Rolle (dramaturgischer Begleiter für Laienschauspielerinnen), Ton, die acht Workshop-Phasen
**als Beschreibung, nicht als Zustand** (die Gruppe darf jederzeit abbiegen), sowie diese
Regeln:

- Nichts erfinden, was nicht im Material steht; Vorschläge nach Möglichkeit mit Belegzitat.
- **Zitate strikt wörtlich, keine Auslassungen mit `[...]`** — sie werden serverseitig
  geprüft (§ 5) und fliegen sonst raus.
- Guidance ohne Bevormundung: anbieten, nicht vorschreiben.
- Kennt `/wortlaut`, `/merken`, `/verworfen`, `/stand`, `/gruendlich` und darf sie anbieten.
- Weiß, dass Verdichtungen nicht nachträglich geändert werden.

---

## 7. Token-Budget: Messung und Kürzung

### 7.1 Messung

**Kein Tokenizer.** Zwei Tage vor dem Workshop keine Abhängigkeit, die sich für Kimi nicht
sauber verifizieren lässt. Stattdessen **Zeichen ÷ 3**. Für deutsche Texte mit ihren langen
Komposita überschätzt das die Tokenzahl leicht — die richtige Fehlerrichtung: lieber zu früh
kürzen als zu spät.

**Selbstkorrektur:** Jeder Aufruf schreibt `geschaetzte_token` und die tatsächliche
`usage.prompt_tokens` aus der API-Antwort in die Tabelle `aufruf`. Nach zwanzig Aufrufen am
Samstagvormittag ist das echte Verhältnis bekannt und der Divisor anpassbar. Das Dashboard
zeigt die Drift.

### 7.2 Kürzungsleiter

Bei Überschreitung wird **hart gekürzt, still, nach fester Rangfolge** — von oben abgearbeitet,
bis es passt:

1. Volltranskripte auf das zuletzt angeforderte Interview reduzieren
2. Kurzes Fenster auf 1.500 Token stutzen
3. Belegzitate aus den Verdichtungen streichen, Zusammenfassungen behalten
4. Journal nach Rang beschneiden
5. **Notbremse:** nur Systemanweisung + Arbeitsstand + Fenster + auslösende Nachricht

**Stufe 5 passt immer. Es gibt keinen Zustand, in dem der Bot wegen des Budgets nicht
antwortet.**

Jede gezogene Stufe schreibt einen `vorfall` mit Stufennummer. Das Dashboard zeigt
„Gruppe 2, 14:03, Stufe 2 gezogen", und das Team weiß, wo es hinschauen muss.

**Nicht** verdichten bei Überschreitung — das wäre ein LLM-Aufruf im kritischen Pfad, ausgelöst
genau dann, wenn ohnehin viel los ist. **Nicht** der Gruppe sagen „ich muss aufräumen" — das
hält den Workshop an und lässt das Werkzeug zerbrechlich wirken.

Kürzen ab Stufe 3 verändert den Cache-Präfix und macht das Caching für diesen Aufruf wertlos.
Das ist der richtige Preis: es passiert selten, und Schärfe schlägt Cache.

**Nicht zu verwechseln mit `max_tokens`** (§ 11.3): Die Kürzungsleiter begrenzt die *Eingabe*,
`max_tokens` bemisst die *Ausgabe*. Letzteres darf nie knapp gesetzt werden.

---

## 8. Befehle

| Befehl | Wirkung |
|---|---|
| `/merken <text>` | Journaleintrag, `art = entschieden`, `quelle = befehl` |
| `/verworfen <text>` | Journaleintrag, `art = verworfen`, `quelle = befehl` |
| `/wortlaut` | Volltranskripte **aller** Interviews an (klebrig) |
| `/wortlaut <name>` | nur dieses Interview (klebrig) |
| `/wortlaut aus` | aus |
| `/gruendlich` | nächster Zug in Modus B (§ 4.5), einmalig, angekündigt |
| `/stand` | Bot gibt den Arbeitsstand aus — **ohne LLM**, direkt aus der DB |
| `/hilfe` | wie man den Bot anspricht, welche Befehle es gibt |

**Zu `/merken` und `/verworfen`:** Nicht als Hauptmechanismus gedacht — Laienschauspielerinnen,
die zum ersten Mal ein Interview führen, tippen keine Slash-Befehle. Als Handbremse für das,
was der Extraktor übersehen hat, kosten sie zwanzig Zeilen Code, brauchen kein LLM und sind
das Werkzeug, mit dem sich etwas festnageln lässt.

**Zu `/wortlaut <name>`:** Der Name, nicht die Nummer. Eine Gruppe, die gerade Marias Figur
schreibt, denkt nicht in Interviewnummern. Namensabgleich großzügig: Kleinschreibung,
Teiltreffer. Bei Mehrdeutigkeit oder Nichttreffer zählt der Bot die vorhandenen Namen auf,
statt zu raten. Klebrig und in der DB, damit der Schalter den Neustart überlebt.

**Zu `/stand`:** Nach der Nacht besonders nützlich, und die Gruppe kann jederzeit prüfen, was
der Bot für den aktuellen Stand hält. Kein LLM-Aufruf, kann nicht fehlschlagen.

**Kein Löschbefehl im Chat.** Löschen ist ein Betreiberskript (§ 9.3), nicht etwas, das
jemand versehentlich in die Gruppe tippt.

---

## 9. Neustart und Betrieb

Der Zustand des Bots wird **nirgends gehalten, sondern abgeleitet** — aus Verdichtungen,
Arbeitsstand, Journal, Nachrichtenlog, Schaltern und Wasserzeichen. Ein frisch gestarteter
Prozess baut Sonntag 12:00 exakt denselben Prompt wie der alte um 18:00, weil der Prompt eine
Funktion der DB ist und nicht des Prozesses. Das ist der Ertrag des datengetriebenen
Zusammenbaus.

### 9.1 Startroutine

1. **`bot_zustand.letzte_update_id` lesen**, Long Polling ab diesem Offset fortsetzen. Steht
   der Offset nur im RAM, wird nach dem Neustart entweder alles nochmal verarbeitet oder es
   fehlt. Telegram hält unabgeholte Updates **24 Stunden** vor — die Nacht von 18:00 bis 12:00
   liegt mit 18 Stunden innerhalb der Frist, aber ohne viel Luft.
2. **Nachtstau verarbeiten:** alles, was während des Stillstands eintrudelte, wird ins Log
   geschrieben, aber mit `unterdrueckt = 1`, wenn es älter als 15 Minuten ist. Es löst also
   keine Antwort aus, steht aber im kurzen Fenster und kann vom Bot aufgegriffen werden, sobald
   die Gruppe wieder anfängt. *Beim Empfangen großzügig, beim Antworten streng — dieselbe
   Trennung wie in § 1, nur auf der Zeitachse.* Vierzehn Stunden später auf eine Nachtnachricht
   zu reagieren, wäre verwirrend.
3. **Angefangene Arbeit aufgreifen:**
   `SELECT * FROM interview WHERE status NOT IN ('verdichtet','fehlgeschlagen')` → zu Ende
   arbeiten. Der wahrscheinlichste Schadensfall ist banal: um 17:58 kommt ein Interview, um
   18:00 klappt der Rechner zu. Ohne diesen Schritt fehlt das Interview am Sonntag **unsichtbar** —
   keine Fehlermeldung, es ist einfach weg. Eine Spalte und eine Abfrage beim Hochfahren; die
   billigste Versicherung im ganzen Entwurf.
4. **Begrüßung nur bei langer Pause:** Ist die letzte Aktivität der Gruppe über **2 Stunden**
   her, eine kurze Zeile. Nach einem Absturz um 14:03 mit dreißig Sekunden Ausfall still
   weiterarbeiten — eine Meldung wäre nur Beunruhigung.

### 9.2 Doppelverarbeitung

`update_id` und `(chat_id, message_id)` als Primärschlüssel, `INSERT OR IGNORE`. Damit kann
ein Absturz mitten in der Verarbeitung nichts doppelt einfügen, egal wie oft Telegram
nachliefert. Eine Zeile Schema, die eine ganze Klasse von Rätseln verhindert.

### 9.3 Löschweg

Betreiberskript, kein Chatbefehl. Je Tabelle mit `chat_id` ein `DELETE`, dazu das
Audioverzeichnis der Gruppe. Vollständig, weil keine Tabelle ohne `chat_id` auskommt.

### 9.4 Prozessaufsicht

- **Jedes Update in `try/except`.** Eine unbehandelte Ausnahme in einem Handler darf niemals
  den Bot töten. Fehler ins Log, weitermachen.
- **Automatischer Neustart** (`systemd Restart=always` oder eine Schleife). Zusammen mit § 9.1
  Schritt 3 ist ein Absturz damit ein Ereignis von zwanzig Sekunden.
- **Gruppenzuordnung sichtbar machen:** Beim Start protokolliert jeder Bot, welche `chat_id`s
  er kennt; das Dashboard zeigt die Zuordnung. Landet Bot 2 versehentlich in Gruppe 1,
  antworten dort zwei Bots — sofort sichtbar statt später rätselhaft.

---

## 10. Interview-Pipeline

```
Sprachnachricht empfangen
  → Datei herunterladen, status='empfangen', Empfangsbestätigung an die Gruppe
  → Whisper V3 → transkript, status='transkribiert'
  → Rückfrage "Wer wurde da interviewt?" (§ 1.4), Ersatzname 'Interview n'
  → Verdichter (§ 4.2) → verdichtung + verdichtung_thema
  → Belegzitat-Verifikation (§ 5)
  → status='verdichtet'
```

- Die **Empfangsbestätigung kommt sofort** („Kommt an, ich höre durch — dauert einen Moment").
  Ohne sie hält die Gruppe den Bot für tot und schickt nochmal.
- Die **Namensrückfrage kommt nach der Transkription**, nicht davor — sonst blockiert sie das
  Einlesen.
- Anzahl der Interviews offen; die Gruppe sagt, wann Schluss ist. Kein Zählwerk im Code.

---

## 11. Fehlerverhalten

### 11.1 Die Gruppe muss es erfahren

| Fall | Verhalten |
|---|---|
| **Transkription schlägt fehl** | 2 Versuche, dann: „Die Aufnahme von Maria konnte ich nicht verstehen — schickt sie bitte nochmal." Audio bleibt liegen, `status='fehlgeschlagen'`, `vorfall`. Nur die Gruppe kann das beheben, und ein still verlorenes Interview ist der teuerste Fehler im System. |
| **Gesprächsaufruf schlägt endgültig fehl** | Retry nach § 11.3, dann eine kurze ehrliche Zeile: „Bei mir hakt gerade etwas — fragt nochmal." Sie warten ja. |
| **Infomaniak komplett weg** | Einmalig: „Mein Sprachmodell ist gerade nicht erreichbar. Ich schreibe alles mit und melde mich, sobald es geht." Danach still, Wiederholung im Hintergrund, bei Rückkehr eine Zeile. **Den Rückstau nicht abarbeiten** — die Gruppe hat inzwischen analog weitergemacht, drei nachgereichte Antworten wären Chaos. Nichts geht verloren, alles steht im Log. |
| **Lange Sprachnachricht** | Sofortige Empfangsbestätigung (§ 10). |
| **`/wortlaut <name>` findet nichts** | Vorhandene Namen auflisten, nicht raten. |
| **`/gruendlich` läuft** | Ankündigung vor dem Aufruf (§ 4.5) — sonst wirkt die Latenz wie ein Defekt. |

### 11.2 Nur das Dashboard erfährt es

Kürzungsleiter gezogen (mit Stufe) · Extraktor-Fenster über 4.000 Token fallengelassen ·
Extraktor liefert ungültiges JSON · **Belegzitat-Prüfung fehlgeschlagen (§ 5.2)** ·
**HTTP 5xx mit erfolgreicher Wiederholung** · **`finish_reason: length`** · Schätzung und
`usage.prompt_tokens` driften auseinander · Sticker, Fotos, Videos (Zeile im Log, keine
Reaktion, **kein Absturz**) · bearbeitete Nachrichten (als neue Zeile loggen, Original stehen
lassen).

### 11.3 Gemessene Betriebsfallen

Beide in der Messung vom 03.09.2026 tatsächlich aufgetreten. Beide sind Betriebsfehler, keine
Modellfehler — und beide sind billig zu schließen.

**1. `max_tokens` zu knapp — der stille Durchfall.**
Bei `max_tokens: 3000` fiel ein Aufruf mit Reasoning **still durch**: HTTP 200,
`content: null`, `finish_reason: "length"`. Kein Fehler, keine Ausnahme, nur eine leere
Antwort. Das Reasoning verbraucht das Ausgabebudget, bevor der eigentliche Inhalt beginnt.

- **`max_tokens` ≥ 9.000 für jeden Aufruf**, zwingend für jeden Aufruf mit Reasoning
  (Modus B, § 4.5).
- **`finish_reason` bei jedem Aufruf prüfen** und in `aufruf.finish_reason` schreiben. Ist er
  `length`, ist das ein `vorfall` `abgeschnitten` — nicht ein leeres Ergebnis, das kommentarlos
  durchgereicht wird.
- Das ist ausdrücklich **kein** Fall für die Kürzungsleiter (§ 7.2): die begrenzt die Eingabe,
  hier ist die Ausgabe zu klein bemessen.

**2. HTTP 502 — Wiederholung mit Backoff.**
In 13 Aufrufen trat einmal HTTP 502 auf; die Wiederholung nach 0,7 Sekunden war sofort
erfolgreich. Bei drei Bots über zwei Tage ist das kein Ausnahmefall, sondern eine
Regelmäßigkeit.

- **Retry bei 5xx und Timeout: 3 Versuche, exponentieller Backoff ab 0,7 s** (0,7 / 1,5 / 3 s),
  mit etwas Jitter.
- Erfolgreiche Wiederholungen werden **nicht** der Gruppe gemeldet, aber als `vorfall`
  `http_5xx` gezählt — häufen sie sich, will das Team es sehen.
- Erst wenn alle Versuche scheitern, greift § 11.1.

---

## 12. Offene Punkte

- **`SEQUENZ_BEI_FRAGEZEICHEN`** — standardmäßig aus, § 1.4. Frühestens nach dem ersten
  Workshoptag erproben.
- **Divisor der Token-Schätzung** — startet bei 3, wird nach den ersten Aufrufen anhand von
  `aufruf.tatsaechliche_token` nachjustiert.
- **Segmentabstand bei `[...]`** — die 600 Zeichen aus § 5.1 sind gesetzt, nicht gemessen.
  Falls die Prüfung am Workshoptag zu viele brauchbare Zitate verwirft, ist das der erste
  Wert, an dem zu drehen ist.

### Erledigt

- **`GESPRAECH_REASONING`** — entschieden durch die Messung vom 03.09.2026: Modus A
  (erzwungenes Schema, `reasoning_effort: "none"`). Gleiche dramaturgische Substanz bei
  4,5 s statt 33,8 s Latenz. Der zweistufige Weg entfällt. Details und Messwerte in § 4.1;
  das verbleibende Zitatrisiko wird durch § 5 abgefangen.
