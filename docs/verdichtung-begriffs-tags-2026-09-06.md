# Kernbegriffe je Verdichtung (06.09.2026)

Interviews/Verdichtungen werden automatisch den **Kernbegriffen der Gruppe**
zugeordnet und auf der Gruppenseite je Interview als Chips angezeigt.

## Entwurfsentscheidung: deterministisch, kein Modellaufruf

Die Zuordnung entsteht durch **Begriffsabgleich** (`interview_theater/begriffe.py`)
gegen **Zusammenfassung und Kernthemen** der Verdichtung — nicht durch einen
eigenen Prompt. Drei Gründe:

1. **Kein zusätzlicher Aufruf am Workshoptag.** Die Zuordnung fällt beim
   Verdichten ab: keine Wartezeit, keine Kosten, kein weiterer Weg, auf dem ein
   Modell etwas über einen interviewten Menschen behaupten kann.
2. **Nachvollziehbar und stabil.** Dieselbe Verdichtung ergibt immer dieselben
   Tags. Ein Modell lieferte je Lauf leicht andere — auf einer Seite, die sich
   während des Workshops mehrfach neu lädt, ist das Rauschen.
3. **Kein Prompt-Risiko.** Ein neuer Prompt hätte einen Korpuslauf gegen das
   echte Modell verlangt (AGENTS.md, „Prompt geändert? → Korpus laufen lassen"),
   der während des laufenden Workshops nicht zu fahren ist.

Der bekannte Preis: ein Interview, das über „Zuhause" spricht, ohne das Wort zu
sagen, bekommt den Tag nicht. Das ist die richtige Richtung des Fehlers — ein
fehlender Tag ist eine Lücke, ein erfundener Tag eine Behauptung.

**Belegzitate und Transkripte gehen NICHT in den Abgleich.** Beides ist der
Wortlaut eines interviewten Menschen; ein Tag daraus abzuleiten hieße, ein
einzelnes hingesagtes Wort zur Aussage des Interviews zu machen.

## Matching-Regeln (`begriffe.py`)

* `zerlege()` trennt `arbeitsstand.begriffe` an `,` `;` `/` Zeilenumbruch `·` `•`,
  entfernt Aufzählungszeichen und Nummerierungen, wirft Dubletten weg und **hält
  den Wortlaut der Gruppe** (der steht so auf der Seite).
* `passt()`: einwortige Begriffe treffen über einen gekürzten Stamm **am
  Wortanfang** (`Liebe` → „Lieben", „Liebesgeschichte", **nicht** „Belieben“ —
  deutsche Komposita hängen hinten an). Mehrwortige Begriffe werden als ganzer
  Teilstring gesucht.
* Normalisierung: Kleinschreibung, Umlaute ausgeschrieben (`ä`→`ae`, `ß`→`ss`),
  Whitespace zusammengezogen. Bewusst arm an Regeln, wie `zitat.py`.
* `MINDESTLAENGE = 4`: kürzere Begriffe („Ich", „EU") matchen gar nicht — sie
  erzeugen im Deutschen zu leicht Zufallstreffer.

## Schema und Migration

Neue Tabelle `verdichtung_begriff` (n:m):

```
id, chat_id, verdichtung_id, aufnahme_id, begriff, quelle, erstellt_am
UNIQUE (verdichtung_id, begriff)
```

* Der Begriff steht als **TEXT**, nicht als id: es gibt keine Begriffstabelle,
  `arbeitsstand.begriffe` ist Freitext, den die Gruppe jederzeit umschreibt.
* Kein `entfernt_am`: die Zeilen sind **abgeleitet**, nicht entschieden.
  Weiches Löschen hält Entscheidungen fest, und eine Zuordnung ist keine.
* Steht in `db.TABELLEN_MIT_CHAT_ID` — die Löschzusage erfasst sie damit.

**Die Migration ist ein `CREATE TABLE IF NOT EXISTS` im `SCHEMA`**, also genau
das bestehende Muster: `db.initialisiere()` fährt `SCHEMA` als `executescript`
und ergänzt danach fehlende Spalten. Eine neue Tabelle braucht deshalb **keinen
`user_version`-Schritt** — `SCHEMA_VERSION` bleibt bei 3, die Phasenmigration
bleibt unangetastet. Der Lauf ist idempotent und rückwärtskompatibel: eine
gewachsene Datenbank bekommt die Tabelle beim nächsten Bot-Start dazu, verliert
nichts und rechnet nichts um.

## Wege der Zuordnung

* **Regelweg:** `verdichter.verdichte()` ruft am Ende `ordne_begriffe_zu()`.
  Kein zweiter Modellaufruf; leere Begriffsliste heißt schlicht: keine Tags.
* **Nachtrag:** `scripts/begriffe_zuordnen.py` (`--trocken`, `--chat-id N`)
  zieht bestehende Verdichtungen nach. **Idempotent** —
  `repo.setze_verdichtung_begriffe` ersetzt die Zeilen einer Verdichtung, statt
  sie zu ergänzen. Es rührt nur `verdichtung_begriff` an; Verdichtungen,
  Transkripte und Arbeitsstand bleiben unberührt. Ausgabe sind **nur Zahlen**,
  nie Inhalte.

## Weboberfläche

`web_daten._begriffe()` liest read-only (mit `OperationalError`-Notbremse: gibt
es die Tabelle zwischen Deploy und Bot-Neustart noch nicht, hat eben keine
Verdichtung Tags — 200, kein 500). `web._begriffe_html()` rendert die Chips
(`.begriffe` / `.begriff`, Sandton und Rundung wie `.art`) aufgeklappt über der
Zusammenfassung. Keine Begriffe heißt keine Zeile. Dashboard bleibt unverändert.

## Tests

`tests/test_begriffe.py` (35): Zerlegung, Matching inkl. Negativfälle, Schema
und Migration gegen eine Alt-Datenbank, Löschzusage, n:m in beide Richtungen,
Ersetz-Semantik, Verdichter-Anbindung mit Aufrufzähler, Idempotenz des Skripts,
Web-Rendering samt HTML-Maskierung und Fallback ohne Tabelle.
