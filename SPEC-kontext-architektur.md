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
- **Sprachnachrichten** (immer — sie sind entweder Gesprächsbeitrag oder Material, nie Geplänkel)

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

### 1.4 Gestrichen: die offene Rückfrage-Sequenz

Eine frühere Fassung sah vor, dass eine code-initiierte Rückfrage des Bots („Wer wurde da
interviewt?") die nächste Gruppennachricht zum Auslöser macht, mit Verfall nach zehn Minuten.

**Das ist ersatzlos gestrichen.** Sprachnachrichten lösen ohnehin immer eine Antwort aus, und
das war der Hauptfall. Übrig bliebe ein Zustandsfeld, das ablaufen kann, falsch verbraucht
werden kann und nur im Zusammenspiel mit der Uhr testbar ist — genau die Sorte bewegliches
Teil, die ein Prototyp nicht braucht. Interviews heißen `Interview n` und werden bei Bedarf
mit `/name` umbenannt (§ 8).

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
  wortlaut_modus                  TEXT,     -- NULL=aus, '*'=alle, sonst Aufnahmename
  gruendlich_naechster_zug        INTEGER NOT NULL DEFAULT 0,  -- Modus B einmalig (§ 4.5)
  whisper_stumm_seit              TEXT      -- gesetzt = Ausfall gemeldet (§ 10.4)
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

-- Sprachaufnahmen UND Textimporte. Eine Statusmaschine fuer beides (§ 10).
CREATE TABLE aufnahme (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  message_id      INTEGER NOT NULL,
  name            TEXT,                     -- 'Maria'; Ersatz: 'Interview 3'
  klasse          TEXT NOT NULL,            -- kurz (Gespraechsbeitrag) | lang (Material)
  quelle          TEXT NOT NULL,            -- sprache | text
  audio_pfad      TEXT,                     -- NULL bei quelle='text'
  transkript      TEXT,
  dauer_sekunden  INTEGER,
  status          TEXT NOT NULL,            -- empfangen|transkribiert|fertig|fehlgeschlagen
  fehlertext      TEXT,
  versuche        INTEGER NOT NULL DEFAULT 0,
  empfangen_am    TEXT NOT NULL
);
CREATE INDEX idx_aufnahme_offen ON aufnahme(status);

CREATE TABLE verdichtung (
  id               INTEGER PRIMARY KEY,
  chat_id          INTEGER NOT NULL,
  aufnahme_id      INTEGER NOT NULL,
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

### 4.3 Absichtserkenner

Nachgelagert, nachdem die Bot-Antwort in der Gruppe steht. **Niemand wartet darauf.**
Modell **`google/gemma-4-31B-it`**, erzwungenes Schema, `reasoning_effort: "none"`,
`temperature: 0.2`.

**Er schließt die Lücke, die Teil A offen ließ:** `kontext.py` liest `arbeitsstand`,
`figur` und `journal` in den Prompt, aber vor Teil B schrieb sie niemand. Das Gedächtnis
bestand aus Verdichtungen plus Verlaufsfenster; alles andere war eine leere Hülle, die
korrekt gelesen wurde.

**Kontext:** aktueller Arbeitsstand + die neuen Nachrichten seit dem Wasserzeichen.
Nicht das ganze Journal, nicht die Transkripte.

**Schema — flach, eine Liste:**

```json
{"aenderungen": [{"art": "<enum>", "wert": "..."}]}
```

Kein Objekt mit acht meist leeren Feldern: Strikte Modi kennen keine optionalen Felder,
das Modell müsste jedes Mal alle ausfüllen — und ein Feld, das befüllt werden *will*, ist
ein Halluzinationsanreiz. Die leere Liste ist die natürliche Form von „nichts gefunden"
und lässt sich per Few-Shot zeigen. **Flach** außerdem, weil verschachtelte Schemata bei
kleineren Modellen brechen (Apertus generiert dort bis zum Budgetende).

`art` ∈ `interview_starten` · `interview_beenden` · `interview_benennen` ·
`begriffe_setzen` · `kernthema_setzen` · `hauptkonflikt_setzen` · `figur_setzen` ·
`wortlaut_an` · `wortlaut_aus` · `verworfen` · `entschieden`

`wert` ist immer ein String. Figuren tragen Name und Beschreibung als **ein** String
(`"Maria: Näherin, kam 1998"`), den der Code am ersten Doppelpunkt trennt — das hält das
Schema flach.

**Überschreiben ist der Normalfall, Entfernen kommt später.** Ein neues Kernthema ersetzt
das alte; eine Figur mit bekanntem Namen wird neu beschrieben. Das ist derselbe
Schreibpfad und kostet nichts extra. Weiches Löschen (`entfernt_am`) ist auf nach dem
ersten Workshoptag verschoben.

**Journaleinträge fallen hier mit ab.** `verworfen` und `entschieden` schreiben eine
Journalzeile — kein zusätzlicher Aufruf, keine neue Schemaform, und `kontext.py` liest
die Tabelle bereits. **`vorgeschlagen` bleibt draußen:** dafür müsste das Modell einen
Grund erfinden, wovor die Recherche ausdrücklich warnt. Das ist die Aufgabe des
verdrängungsgetriebenen Journal-Extraktors (§ 4.6).

**Szenen bleiben in Teil B ganz weg.** `kontext.py` liest sie nicht, sie entstehen erst
in der letzten Workshop-Phase, und etwas zu schreiben, das niemand liest, ist Fläche ohne
Nutzen.

**Meldung an die Gruppe — eine je Erkennerlauf.** Nicht eine je Änderung. Kernthema und
Hauptkonflikt bekommen darin je eine eigene Zeile im Wortlaut, Figuren eine
zusammenfassende Zeile mit Namen:

> Notiert: Kernthema = Ankommen · drei Figuren: Maria, Elif, Peter.
> Falls das nicht stimmt, sagt es mir.

- **Nicht auf Bestätigung warten.** Der Ablauf läuft weiter; die Meldung *ist* die
  Korrekturgelegenheit, kein Tor.
- **Gleicher Wert, keine Meldung.** Sonst meldete der Bot bei jedem Zug dasselbe Kernthema.
- **Journaleinträge bleiben still.** Sonst wäre der Chat zugespammt und die Meldungen
  würden überlesen — womit sie ihren Zweck verlören.

**Fehlschlag:** Wasserzeichen bleibt stehen, das Fenster wird beim nächsten Mal
mitgelesen — ein kostenloser Wiederholungsversuch ohne eigene Retry-Logik. Der Gruppe
wird nichts gemeldet, `vorfall` ans Dashboard. **Deckel:** über ~4.000 Token wird das
Wasserzeichen trotzdem vorgerückt und ein `vorfall` `fenster_verworfen` geschrieben.

### 4.3a Modellwahl je Aufruf (gemessen 04.09.2026)

| Aufruf | Modell | Belege |
|---|---|---|
| **Gespräch** | `moonshotai/Kimi-K2.6` | 6/6 valide, 5,1 s, 8/8 Belegzitate wörtlich |
| **Verdichter** | `moonshotai/Kimi-K2.6` | dieselbe Aufgabe: dramaturgisch, mit Zitaten |
| **Absichtserkenner** | `google/gemma-4-31B-it` | 0 Falsch-Positive bei 25 Negativfällen, 30/30 Treffer, 0,75 s. Kimi verpasste `interview_beenden` 3/3 |
| **Journal** (§ 4.6) | `google/gemma-4-31B-it` | einziges kleines Modell mit korrekten Kategorien |

**Nicht verwenden:** `Nemotron-Nano` — 6/27 Falsch-Positive, las „Kindheitsfragen lassen
wir weg" als `kernthema_setzen`. `Apertus` scheitert an verschachtelten Schemata; bei
flachen brauchbar, aber nicht für die Absichtserkennung.

**Kosten sind kein Auswahlkriterium:** ein ganzes Wochenende kostet 1,20 statt 1,41 CHF.
Ausgewählt wird nach Trefferquote.

**🔴 `gemma` hat 28,5 s Kaltstart**, danach unter 1 s. **Beim Workshop-Start warmlaufen
lassen** — sonst wartet die erste Gruppe eine halbe Minute auf die erste Absichtserkennung.

### 4.4 Reasoning-Semantik und robustes Auslesen

**🔴 Bei Infomaniak ist `reasoning_effort` binär.** `"none"` schaltet Reasoning aus, jeder
andere Wert schaltet es an; `low`/`medium`/`high` sind nicht unterscheidbar. **Das Feld
wegzulassen schaltet Reasoning AN** — es gibt keine stille Voreinstellung „aus".

Daraus folgt zwingend: **Das Feld wird immer gesendet, und der Vorgabewert ist `"none"`.**
Eine frühere Fassung von `llm.py` hatte `if reasoning_effort:` — ein leerer Wert ließ das
Feld weg und schaltete Reasoning damit ein. Das ist die Sorte Falle, die nicht abstürzt,
sondern nur still die Latenz verzwanzigfacht und die Trefferquote senkt.

**Reasoning ist überall aus, außer bei `/gruendlich`.** Gemessen: Reasoning hilft bei
Mathematik und Symbolik (0/6 richtig ohne, 5/6 mit), bringt bei extraktiven und
sprachlichen Aufgaben **nichts außer Latenz** (0,6 s gegen 14–16 s bei identischem
Ergebnis). Bei **Klassifikation mit Ausnahmen** — also genau dem Absichtserkenner — bricht
die Trefferquote laut Princeton-Studie um bis zu 36 Prozentpunkte **ein**. Die früher
geäußerte Absicht, den Verdichter auf Reasoning umzustellen, ist damit widerlegt.

**Robustes Auslesen**, in dieser Reihenfolge:

1. **`finish_reason == "length"` → Budgetfehler**, nicht Formatfehler. Ein abgeschnittenes
   Ergebnis ist nie ein gültiges; die Ursache ist `max_tokens`, nicht das Modell.
2. `content`, ersatzweise `message.reasoning`.
3. `json.loads` auf den ganzen Text versuchen.
4. Schlägt das fehl: **die erste Position suchen, ab der der Rest vollständig parst.**
   Nicht blind `text[1:]`. Kimi erzeugt bei aktivem Reasoning ein Präfix-Artefakt (`' {{'`),
   die Antwort dahinter ist aber vollständig und schemakonform — der Präfix ist nicht
   immer genau ein Zeichen lang.

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

## 5. Belegzitat-Verifikation

**Eine Regel:** Kommt das Zitat nach Normalisierung wörtlich im Transkript vor, ja oder nein.

- **Normalisieren**, auf beiden Seiten gleich: Whitespace-Folgen zu einem Leerzeichen,
  typografische Anführungszeichen auf gerade. Sonst nichts.
- **Teilstring-Vergleich.** Trifft er nicht: Vorschlag **ohne** Zitat ausliefern, `vorfall`
  `zitat_ungeprueft`, fertig.
- **Kein Retry. Kein Zerlegen an `[...]`. Keine Reihenfolge- oder Abstandsprüfung.**

**Warum das Regelwerk gestrichen wurde.** Eine frühere Fassung zerlegte Zitate an `[...]`,
prüfte Segmentreihenfolge und einen Höchstabstand von 600 Zeichen und fasste einmal nach.
Das schützte gegen **ein einziges Vorkommnis in neun Messläufen** — und konnte selbst falsch
ablehnen. Ein fälschlich abgewiesenes Zitat ist am Workshoptag genauso schlecht wie ein
zusammengeklebtes: In beiden Fällen steht ein Vorschlag ohne Beleg da. Dazu kommt, dass die
Gruppe ihr eigenes Transkript im Chat sieht und Unstimmigkeiten selbst bemerkt — sie ist die
bessere Prüfinstanz als eine Heuristik mit drei gesetzten Schwellwerten.

Was bleibt, fängt den wichtigen Fall ab: ein Zitat, das **gar nicht** im Transkript steht.
Genau das kann die Gruppe nicht selbst sehen, weil ihr die Behauptung plausibel erscheint.
Alles Feinere kostet mehr Risiko, als es abwehrt.

**Der Gruppe wird nichts gemeldet** (Leitsatz 5) — sie kann es nicht beheben und wartet nicht
darauf.

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

**Reihenfolge: stabil nach vorn, flüchtig nach hinten.** Begründung ist die
Aufmerksamkeitsverteilung des Modells: was am Ende des Prompts steht, wiegt am schwersten,
und das soll das Aktuellste sein — die auslösende Nachricht, dann das kurze Fenster, dann
das Journal. Alles, was sich selten ändert, wandert nach vorn.

> **Kein Caching-Argument.** Eine frühere Fassung begründete diese Reihenfolge zusätzlich mit
> Prompt-Caching. Das ist gestrichen: In den Messläufen gegen Infomaniak steht in **jeder**
> Antwort `prompt_tokens_details: null`. Die API-Dokumentation listet zwar
> `prompt_cache_key` und `cached_tokens`, aber das ist das von OpenAI übernommene Schema und
> kein Beleg, dass der Anbieter die Felder füllt. **Es gibt keinen gemessenen Cache-Treffer.**
> Die Reihenfolge bleibt richtig, aber allein aus dem Grund oben. Siehe § 12.

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

### 7.2 Kürzung

Passt der Prompt nicht ins Budget, greift **eine Regel in zwei Schritten**:

1. **Volltranskripte fliegen ganz raus.**
2. Reicht das nicht, wird das **kurze Fenster von vorn beschnitten**, bis es passt.

Was danach übrig bleibt, ist die **Notbremse**: Systemanweisung + Arbeitsstand + Fenster +
auslösende Nachricht. Die passt immer — **es gibt keinen Zustand, in dem der Bot wegen des
Budgets nicht antwortet.** Das ist der einzige Teil der alten fünfstufigen Leiter, der
wirklich gebraucht wurde.

Jede Kürzung schreibt einen `vorfall`. Das Dashboard zeigt „Gruppe 2, 14:03, gekürzt".

**Nicht** verdichten bei Überschreitung — das wäre ein LLM-Aufruf im kritischen Pfad, ausgelöst
genau dann, wenn ohnehin viel los ist. **Nicht** der Gruppe sagen „ich muss aufräumen" — das
hält den Workshop an und lässt das Werkzeug zerbrechlich wirken.

Kürzen kostet nichts außer dem gekürzten Material — ein Caching-Nachteil, wie eine frühere
Fassung behauptete, ist nicht belegt (§ 6.1).

**Nicht zu verwechseln mit `max_tokens`** (§ 11.3): Die Kürzung begrenzt die *Eingabe*,
`max_tokens` bemisst die *Ausgabe*. Letzteres darf nie knapp gesetzt werden.

---

## 8. Befehle

| Befehl | Wirkung |
|---|---|
| `/merken <text>` | Journaleintrag, `art = entschieden`, `quelle = befehl` |
| `/verworfen <text>` | Journaleintrag, `art = verworfen`, `quelle = befehl` |
| `/kernthema <text>` | **korrigiert** das Kernthema |
| `/konflikt <text>` | korrigiert den Hauptkonflikt |
| `/begriffe <text>` | korrigiert die Begriffe |
| `/figur <name>: <beschreibung>` | legt eine Figur an oder überschreibt sie |
| `/name <alt> <neu>` | benennt eine Aufnahme um (`Interview 2` → `Maria`) |
| `/material <text>` | speist Text als Material ein (§ 10.5) |
| `/wortlaut [name\|aus]` | Volltranskripte mitlesen (klebrig) |
| `/gruendlich` | nächster Zug in Modus B (§ 4.5), einmalig, angekündigt |
| `/stand` | Arbeitsstand ausgeben — **ohne LLM**, direkt aus der DB |
| `/hilfe` | wie man den Bot anspricht, welche Befehle es gibt |

**Die Arbeitsstand-Befehle sind Korrekturweg, nicht Hauptweg.** Gefüllt wird der Arbeitsstand
vom Extraktor (§ 4.3); getippt wird nur, wenn er etwas falsch verstanden hat. Deshalb steht in
jeder Änderungsmeldung des Bots die Einladung dazu — die Gruppe muss die Befehle nicht kennen,
sie werden ihr im Moment des Bedarfs gezeigt.

**Zu `/wortlaut <name>`:** Der Name, nicht die Nummer. Eine Gruppe, die gerade Marias Figur
schreibt, denkt nicht in Aufnahmenummern. Namensabgleich großzügig: Kleinschreibung,
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
   `SELECT * FROM aufnahme WHERE status NOT IN ('fertig','fehlgeschlagen')` → zu Ende
   arbeiten. Denselben Weg nimmt der Nachhol-Arbeiter im laufenden Betrieb (§ 10.3). Der wahrscheinlichste Schadensfall ist banal: um 17:58 kommt ein Interview, um
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

## 10. Sprachverarbeitung und Materialimport

Sprache ist nicht mehr nur Interview-Material. Auch die normale Arbeitskommunikation und
Regieanweisungen laufen per Sprachnachricht. **Das ändert die Latenzanforderung
grundlegend** — und zwar nicht gleichmäßig, sondern gespalten.

### 10.1 Zwei Klassen, unterschieden am Interviewmodus

**Die 45-Sekunden-Schwelle ist gestrichen.** Sie war von Anfang an eine Näherung, und sie
trägt nicht: Ein Interview kann aus fünf Sprachnachrichten bestehen, eine Regieanweisung
länger als eine Minute dauern. **Die Dauer sagt nichts über die Art aus.**

Stattdessen **schaltet die Gruppe den Modus ausdrücklich**:

| Klasse | Wann | Was daraus wird |
|---|---|---|
| **lang** (Material) | Interviewmodus ist an | Transkript + Verdichtung (Schicht 1) |
| **kurz** (Gespräch) | Interviewmodus ist aus | Transkript als Nachricht, löst einen Gesprächszug aus |

Der Modus wird gesetzt durch den Absichtserkenner (`interview_starten` /
`interview_beenden`, also durch normale Sätze wie „wir machen jetzt ein Interview" …
„fertig") **oder** durch `/interview` und `/fertig`. Er steht in
`gruppe.interviewmodus_seit` und überlebt damit den Neustart.

**Keine Rückfrage, wenn der Modus vergessen wird.** Eine frühere Fassung sah vor, dass der
Bot bei einer langen Erzählung außerhalb des Modus nachfragt. Das wurde verworfen: Eine
Rückfrage braucht Zustand, der auf eine Antwort wartet — genau das Konstrukt, das § 1.4
ersatzlos gestrichen hat. Stattdessen zwei zustandsfreie Wege:

1. Erkennt der Absichtserkenner eine längere Erzählung außerhalb des Modus, **weist der
   Bot beiläufig in seiner ohnehin fälligen Antwort darauf hin** („Das klingt nach
   Material — wenn ihr es als Interview festhalten wollt, sagt mir Bescheid"). Keine
   Rückfrage, kein Warten. Die Gruppe reagiert oder nicht.
2. Wichtiger und billiger: **Die Begrüßungsnachricht erklärt, wie Interviews
   funktionieren**, und `/hilfe` wiederholt es.

**Der Rettungsanker ist, dass Rohmaterial immer gespeichert wird** (§ 10.2). Wird der
Modus zu starten vergessen, ist die Sprachnachricht trotzdem da und kann nachträglich
zugeordnet werden. Nichts geht verloren — es ist nur nicht sofort als Material markiert.

### 10.2 Die Datei ist zuerst sicher, dann wird gefragt

**Die Audiodatei wird immer heruntergeladen und mit `status = 'empfangen'` in die Datenbank
geschrieben, bevor Whisper überhaupt gefragt wird.** Das ist die eigentliche Absicherung.
Fällt Whisper aus, liegt das Material trotzdem da und wird nachgeholt (§ 10.3) — es ist keine
Aufnahme verloren, nur noch nicht gelesen.

```
Sprachnachricht
  → Datei herunterladen, aufnahme(status='empfangen', klasse=kurz|lang)
  → [lang] sofortige Empfangsbestätigung an die Gruppe
  → Transkription im Hintergrund
  → status='transkribiert'
  → [kurz] Transkript in dieselbe Nachrichtenzeile, loest Gespraechszug aus
  → [lang] Verdichter (§ 4.2) + Belegzitat-Prüfung (§ 5)
  → status='fertig'
```

**Die Transkription läuft nebenläufig, nie blockierend im Nachrichten-Handler.** Ein
Handler, der auf Whisper wartet, blockiert alles Übrige der Gruppe.

**Die Schwellwerte stammen aus der Messung vom 03.09.2026** (§ 11.3 Punkt 4): 76 Läufe,
Median 2,9 s bei 7 s Audio, 2,8 s bei 30 s, 4,8 s bei 180 s, einziger Ausreißer 8,88 s.

| Konstante | Wert | Begründung aus der Messung |
|---|---:|---|
| `TIPPANZEIGE_AB_S` | 5 | liegt über dem Median, feuert also nur, wenn es wirklich hakt |
| `MELDUNG_AB_S` | 12 | über dem einzigen gemessenen Ausreißer von 8,88 s |
| `BUDGET_KURZ_S` | 45 | kein Lauf über 10 s; 45 s sind großzügig und trotzdem im Gesprächstempo |
| `BUDGET_LANG_S` | 90 | 4,8 s für 180 s Audio gemessen; 90 s decken auch einen schlechten Tag |

Ein früherer Entwurf setzte die Textmeldung auf 8 Sekunden. **Das ist überholt** — sie hätte
bei dem einen gemessenen Ausreißer grundlos gefeuert und die Gruppe beunruhigt, obwohl das
Transkript eine Sekunde später da war.

Weitere Regeln:

- **Bei kurz keine Empfangsbestätigung**, nur die Tippanzeige ab 5 s. Eine Bestätigung auf
  einen Siebensekünder wäre Lärm.
- **Ab `MELDUNG_AB_S` eine kurze Zeile** („Ich hör noch zu, einen Moment") — dann weiter
  arbeiten. Kein Warten, kein Tor.
- **Genau ein sofortiger Wiederholungsversuch** mit neuem Upload. Schlägt auch der fehl oder
  reißt das Zeitbudget, bleibt `status = 'empfangen'` stehen und der Nachhol-Arbeiter
  übernimmt (§ 10.3). Kein Schleifen im heißen Pfad.
- **Nicht schneiden.** Chunking bringt nichts: 6×30 s parallel brauchten 4,22 s gegen 4,84 s
  am Stück. Geschnitten wird ausschließlich, wenn die 25-MB-Grenze es erzwingt.
- **Kein Rate-Limiting** festgestellt — zehn gleichzeitige Uploads gingen alle durch. Der
  Thread-Pool darf also parallel hochladen.

### 10.3 Nachhol-Arbeiter

Ein Arbeiter greift **beim Start und danach alle `NACHHOL_INTERVALL_S = 60` Sekunden** alles
auf, was nicht in einem Endzustand steht (`empfangen`, `transkribiert`). Damit **heilt ein
Whisper-Ausfall sich selbst**, sobald der Dienst zurück ist — niemand muss etwas anstoßen.

Es ist derselbe Mechanismus, der die Nacht zwischen den Workshoptagen überbrückt (§ 9.1
Schritt 3). Ein Mechanismus für zwei Probleme, keine zweite Maschinerie.

**Nachgeholtes löst nie eine Antwort aus.** Eine kurze Aufnahme, die erst zwanzig Minuten
später transkribiert wird, landet als Text im Verlauf, aber der Bot antwortet nicht mehr
darauf — dieselbe Regel wie beim Nachtstau. Die Gruppe ist inzwischen weiter; eine verspätete
Antwort auf einen Zuruf von vorhin stiftet mehr Verwirrung, als sie nützt.

Nach `MAX_VERSUCHE = 5` erfolglosen Anläufen wird eine Aufnahme `fehlgeschlagen`, damit ein
kaputtes Audio nicht bis Sonntagabend im Kreis läuft.

### 10.4 Whisper komplett weg

Pro Gruppe ein Feld `whisper_stumm_seit`.

- Schlägt eine Transkription fehl und das Feld ist leer: **einmalig** eine Zeile — „Ich kann
  gerade nicht hören. Schreibt mir solange, ich sammle die Aufnahmen und hole sie nach." —
  dann Feld setzen und **still bleiben**. Nicht bei jeder weiteren Nachricht wiederholen.
- Gelingt eine Transkription und das Feld ist gesetzt: eine Zeile („Ich kann wieder hören"),
  Feld leeren.
- **Der Rückstau wird nicht beantwortet**, nur transkribiert und abgelegt, damit das Material
  im Kontext steht (§ 10.3).

### 10.5 Textimport als gleichwertiger Weg

`/material <text>` und eine als Dokument geschickte `.txt`-Datei erzeugen eine `aufnahme` mit
`quelle = 'text'` und `status = 'transkribiert'`, die **durch denselben Verdichter läuft** und
dieselben Verdichtungen mit Belegzitaten erzeugt wie eine Sprachaufnahme.

Das deckt zwei Fälle mit einem Weg ab: den **Rückfallweg**, wenn Audio streikt — und den Fall,
dass die Gruppe vorhandenes Recherchematerial einspeisen will, das nie gesprochen wurde.

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

**1. `max_tokens` zu knapp — der stille Durchfall.**
Bei `max_tokens: 3000` fiel ein Aufruf mit Reasoning **still durch**: HTTP 200,
`content: null`, `finish_reason: "length"`. Das Reasoning verbraucht das Ausgabebudget, bevor
der eigentliche Inhalt beginnt.

- **`max_tokens` ≥ 9.000 für jeden Aufruf.**
- **`finish_reason` bei jedem Aufruf prüfen**; `length` ist ein `vorfall` `abgeschnitten`,
  kein leeres Ergebnis zum Durchreichen.
- Kein Fall für die Kürzung (§ 7.2): die begrenzt die Eingabe, hier ist die Ausgabe zu klein.

**2. `reasoning_effort` nur senden, wenn gesetzt.**
Aus der Vorlage `kg/llm.py`: Modelle, die das Feld nicht kennen, lehnen den Request mit
**HTTP 400** ab. Es gehört also nur dann in den Körper, wenn ein Wert konfiguriert ist.

**3. HTTP 502 — Wiederholung mit Backoff.**
In 13 Aufrufen trat einmal HTTP 502 auf; die Wiederholung nach 0,7 Sekunden war sofort
erfolgreich. Bei drei Bots über zwei Tage ist das kein Ausnahmefall.

- **Retry bei 5xx und Timeout: Wartezeiten 0,7 / 1,5 / 3 s mit Jitter.**
- Erfolgreiche Wiederholungen werden **nicht** der Gruppe gemeldet, aber als `vorfall`
  `http_5xx` gezählt.

**4. Whisper-Latenz — gemessen am 03.09.2026.**
76 Läufe über 52 Minuten, **alle erfolgreich**. Median 2,9 s bei 7 s Audio, 2,8 s bei 30 s,
4,8 s bei 180 s. Einziger Ausreißer der gesamten Messung 8,88 s, **kein Lauf über 10 s**.
Kein Rate-Limiting (zehn gleichzeitige Uploads gingen alle durch). Chunking bringt nichts
(6×30 s parallel 4,22 s gegen 4,84 s am Stück).

Damit ist die frühere Sorge entschärft: Beim Realbetrieb der Installation
*Kollektivgedächtnis* (Festival NEW bauhaus, Ende August 2026) war der Server gelegentlich
komplett ausgefallen oder brauchte bis zu 30 Sekunden. Die Nachmessung bestätigt das nicht.
**Die Architektur in § 10 bleibt trotzdem so gebaut, dass sie von diesen Zahlen nicht
abhängt** — Datei zuerst sichern, nebenläufig transkribieren, Zeitbudget, Nachhol-Arbeiter,
einmalige Ausfallmeldung. Die Messung bestimmt nur die Schwellwerte, nicht die Struktur.

**4b. `TS_LLM_URL` muss die volle URL sein.** Gemessen beim Rauchtest am 04.09.2026:
Der Code hängt nichts an. Mit `.../openai/v1` allein antwortet der Server **HTTP 404**;
richtig ist `.../openai/v1/chat/completions`. Steht in `docs/betrieb-env.beispiel`.

**4c. 🔴 Der MIME-Typ beim Upload muss zur Datei passen.** Ein fest verdrahtetes
`audio/ogg` für eine WAV-Datei wird vom Anbieter **mit einer `batch_id` quittiert**, der
Auftrag bleibt danach aber dauerhaft auf `pending` und läuft in die Zeitfrist — 89,7 s
statt 2,0 s. Das ist die schlimmste Sorte Fehler: kein HTTP-Fehler, keine Ablehnung, im
Betrieb nur als „hängt" sichtbar. Telegram liefert Audio nicht nur als `voice`
(ogg/opus), sondern auch als `audio` (m4a, mp3) und als Dokument. Der Typ wird deshalb
aus der Dateiendung abgeleitet (`stt.mime_typ`).

**5. Whisper ist zweistufig und asynchron** (Vorlage
`stt_backends/infomaniak_whisper_backend.py`, gemessen 31.08.2026):

- Absenden: `POST {base}/1/ai/{produkt}/openai/audio/transcriptions`, multipart mit `file`,
  `model=whisper`, `language=de`, `response_format=verbose_json` → `{"batch_id": "..."}`.
  **Nicht** unter `/2/.../openai/v1/` — dort antwortet der Server 404.
- Ergebnis: `GET {base}/1/ai/{produkt}/results/{batch_id}` → `{"status": "success", "data":
  "<JSON-String>"}`. **`data` ist ein String, kein Objekt** und muss ein zweites Mal geparst
  werden.
- Abbruchzustände: `error`, `failed`, `aborted`, `canceled`, `cancelled`. Alles andere heißt
  weiterwarten, begrenzt vom Zeitbudget — die Zwischenzustände sind nicht abschließend
  bekannt, und ein unbekannter Status darf nicht als Fehler durchgehen.
- Grenze: 25 MB pro Datei.

---

## 12. Offene Punkte

- **`KURZ_GRENZE_S = 45`** (§ 10.1) — gesetzt, nicht gemessen. Der erste Wert, an dem zu
  drehen ist, falls Regieanweisungen regelmäßig als Material einsortiert werden oder
  umgekehrt.
- **`LANGSAM_AB_S = 8` und die Zeitbudgets** (§ 10.2) — hängen an der laufenden
  Whisper-Messung (§ 11.3 Punkt 4).
- **Divisor der Token-Schätzung — bestätigt.** Rauchtest gegen die echte API am
  04.09.2026: 983 Zeichen ergaben 337 tatsächliche Prompt-Token, also **2,92**. Der
  angenommene Wert 3 überschätzt damit leicht — die richtige Fehlerrichtung. Kein
  Handlungsbedarf. (Ursprünglicher Punkt:) Divisor der Token-Schätzung — startet bei 3, wird nach den ersten Aufrufen anhand von
  `aufruf.tatsaechliche_token` nachjustiert.
- **Segmentabstand bei `[...]`** — die 600 Zeichen aus § 5.1 sind gesetzt, nicht gemessen.
  Falls die Prüfung am Workshoptag zu viele brauchbare Zitate verwirft, ist das der erste
  Wert, an dem zu drehen ist.
- **Prompt-Caching** — derzeit **unbelegt und deshalb nirgends als Argument verwendet**
  (§ 6.1). Wenn `usage.prompt_tokens_details` bei Infomaniak irgendwann nicht mehr `null`
  liefert, lohnt eine erneute Prüfung: dann könnte der stabile Prompt-Kopf auch Kosten und
  Latenz senken, und die Kürzungsleiter bekäme einen zusätzlichen Abwägungsgrund. Bis dahin
  ist das eine Vermutung, keine Grundlage. Billigster Weg, es zu merken:
  `usage.prompt_tokens_details` bei jedem Aufruf mitloggen und im Dashboard anzeigen, sobald
  es einmal nicht `null` ist.

### Erledigt

- **`GESPRAECH_REASONING`** — entschieden durch die Messung vom 03.09.2026: Modus A
  (erzwungenes Schema, `reasoning_effort: "none"`). Gleiche dramaturgische Substanz bei
  4,5 s statt 33,8 s Latenz. Der zweistufige Weg entfällt. Details und Messwerte in § 4.1;
  das verbleibende Zitatrisiko wird durch § 5 abgefangen.
