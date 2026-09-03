# Brainstorming-Auftrag: Theater-Soap-Bot — Kontext- und Gedächtnis-Architektur

Du führst mit mir (Hermes, im Auftrag von Birk Schmithuesen / ArtesMobiles) eine
**Design-Brainstorming-Session**. Ziel dieser Session ist **kein Code**, sondern
eine belastbare Spezifikation für die Kontext-/Gedächtnis-Architektur eines
Telegram-Chatbots. Die Umsetzung folgt danach in einer eigenen Phase.

## Was gebaut wird (Gesamtbild)

Ein Telegram-Bot, mit dem Laienschauspielerinnen in Kleingruppen aus eigenen
Interviews ein Theaterstück entwickeln. Ersteinsatz: Workshop in Dortmund am
**05.+06.09.2026** (zwei Tage, ~9,25 h Nettoarbeitszeit), danach Padua
(21.09.–09.10.2026) und ein monatlicher Serienbetrieb.

**Bereits entschieden — nicht mehr zur Diskussion stellen:**

- **Telegram** als Interface. Pro Kleingruppe ein eigener Bot (eigener Token),
  ~3 Gruppen à 3–4 Personen. Gleicher Code, mehrfach gestartet.
- **Eine gemeinsame SQLite** (WAL) für alle Bots, Zustand pro `chat_id`
  geschlüsselt.
- **Infomaniak** als Anbieter (CH): Whisper V3 für Sprache→Text,
  Kimi K2.6 als LLM. OpenAI-kompatibler Endpunkt.
- **Jede Gruppe arbeitet nur mit ihrem eigenen Material** — kein gemeinsamer Pool.
- **Verdichtungen werden NICHT nachträglich aktualisiert.** Was beim Einlesen
  eines Interviews an Zusammenfassung + Kernthemen entsteht, bleibt so stehen.
- **Ein read-only Dashboard** (Workshop-Team, ein Rechner, projiziert) liest
  dieselbe SQLite. Nicht Teil dieser Brainstorming-Session, aber es liest mit.
- **Keine Phasen-Zustandsmaschine.** Die 8 Workshop-Phasen sind Struktur im
  Workshop, nicht im Code; der Bot moderiert sie im Gespräch. Die Gruppe darf
  jederzeit abbiegen (Guidance ohne Bevormundung).

## Ablauf, den der Bot begleitet

1. Begriffssammlung im Plenum (analog, ohne Bot)
2. Jede Gruppe wählt bis zu 5 Begriffe (analog)
3. **Gruppe tippt ihre Begriffe in den Chat** → gemeinsam Interviewfragen
   entwickeln (erster Bot-Einsatz)
4. Interviews führen (Sprachnachrichten in den Gruppenchat; Anzahl offen,
   die Gruppe sagt, wann Schluss ist)
5. Alle Interviews zu einem Kernthema verdichten
6. Charakterentwicklung
7. Hauptkonflikte + Szenenentwicklung
8. Szenen-Feinschliff bis zum finalen Text

Nach mehreren Phasen kommen die Gruppen im Plenum zusammen und präsentieren
ihren Stand.

## DAS THEMA DIESER SESSION

**Was wandert bei jedem LLM-Aufruf in den Kontext, und wie wird verhindert,
dass das Kontextfenster gesprengt wird?**

Mein bisheriger Vorschlag (Ausgangspunkt, ausdrücklich zur Kritik gestellt —
zerpflück ihn, wenn er nicht trägt):

- **Schicht 1 — Materialstapel:** pro Interview liegen Volltranskript UND
  Verdichtung in der DB. In den Prompt geht normalerweise nur die Verdichtung.
  Das Volltranskript nur gezielt, wenn es um die konkrete Sprache einer Person
  geht (Szenentext).
- **Schicht 2 — Arbeitsstand:** die getroffenen Entscheidungen (Begriffe,
  Kernthema, Figuren, Hauptkonflikt) als strukturierte Felder. Geht immer mit.
  Vorteil: die Gruppe kann eine Entscheidung revidieren, weil sie ein
  DB-Feld ist und nicht eine Aussage im Verlauf.
- **Schicht 3 — kurzes Gedächtnis:** die letzten N Nachrichten des Chats.

**Konkret zu klären (Birks Fragen, wörtlich):**

1. Wie wird gemanagt, was in den System-Prompt wandert?
2. Wie wird überwacht, dass das Kontextfenster nicht gesprengt wird?
3. **Ist es wirklich richtig, nur die letzten Nachrichten aus dem Chatverlauf
   zu injizieren — oder braucht es zusätzlich eine Zusammenfassung dessen, was
   davor war?** (Das ist die Kernfrage.)

## Rahmenbedingungen, die die Antwort beeinflussen

- **Gruppenchat, nicht 1:1.** 3–4 Personen reden durcheinander, dazwischen
  Bot-Antworten. Der Verlauf wächst deutlich schneller als in einem Einzelchat,
  und nicht jede Nachricht ist an den Bot gerichtet.
- **Zwei Tage mit Unterbrechung.** Samstag 18:00 Ende, Sonntag 12:00 weiter.
  Über Nacht Prozess-Neustart möglich. Was am Samstag entschieden wurde, muss
  Sonntag noch da sein.
- **Grobe Größenordnung:** ein 5-Minuten-Interview ≈ 700 Wörter ≈ 1.000 Token.
  Bei 5 Interviews 5.000 Token nur Material. Chatverlauf über zwei Tage grob
  geschätzt 20.000–30.000 Token. Kimi K2.6 hat ein großes Fenster, es reißt
  nicht sofort — aber teuer, langsam und unscharf wird es lange vorher.
- **🔴 Gemessene Einschränkung des Modells (aus einem Vorprojekt, Repo
  `kollektivgedaechtnis`, Datei `kg/llm.py`):** Kimi K2.6 liefert valides
  JSON bei erzwungenem Schema nur mit `reasoning_effort: "none"` — ohne das
  Feld 0/5 valide Antworten, mit `"low"` 0/8, mit `"none"` 8/8. Zwei
  Fehlerbilder bei HTTP 200: Inhalt beginnt mit `{{` statt `{`, oder der Text
  steht in `message.reasoning` und `content` ist `null`.
  **Das heißt: strukturierte Ausgabe und "Modell denkt nach" schließen sich
  bei diesem Modell praktisch aus.** Eine parallele Messung läuft gerade, ob
  die dramaturgische Qualität darunter leidet. Deine Architektur sollte mit
  beiden Ausgängen umgehen können.
- Es gibt **keinen Verlass auf ein zweites Modell**; alles läuft über
  Infomaniak.

## Was ich von dir will

Führe mich durch die offenen Entwurfsentscheidungen — eine Frage nach der
anderen, mit Optionen und einer klaren Empfehlung. Ich erwarte, dass du
mindestens diese Punkte adressierst, gern auch weitere, die dir auffallen:

- Wie sieht der Kontext-Zusammenbau pro Aufruf konkret aus (welche Teile, in
  welcher Reihenfolge, welches Budget je Teil)?
- Wird der Chatverlauf verdichtet — und wenn ja, wann wird das ausgelöst
  (Nachrichtenzahl? Tokenzahl? Phasenwechsel?) und was passiert mit dem
  Original?
- Wie wird das Token-Budget gemessen, bevor der Aufruf rausgeht? Was passiert,
  wenn das Budget überschritten würde — hart kürzen, verdichten, oder der
  Gruppe sagen „ich muss aufräumen"?
- Braucht es unterschiedliche Kontext-Zusammenstellungen je nach Aufgabe
  (Interviewfragen entwickeln vs. Figuren vs. Szenentext)? Oder ist ein
  einziger Zusammenbau robuster?
- Wie kommt der Bot nach einem Neustart (Nacht zwischen den Workshoptagen)
  wieder in einen sinnvollen Zustand?
- Wie wird verhindert, dass Gruppen-Nebengespräche („ich hol mir Kaffee") den
  Kontext verwässern?
- Welche Fehlerfälle sind am Workshop-Tag wahrscheinlich, und was ist jeweils
  das Verhalten, das den Workshop NICHT anhält?

**Wichtig zur Haltung:** Der Workshop ist übermorgen. Ein einfacher Entwurf,
der sicher läuft, schlägt einen eleganten, der noch nie unter Last stand.
Wenn dir etwas an meinem Vorschlag zu kompliziert vorkommt, sag es.

Ergebnis dieser Session soll eine Spezifikation sein, die anschließend als
Bauplan taugt.
