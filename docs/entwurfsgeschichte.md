# Entwurfsgeschichte

Wie dieses Werkzeug zu dem wurde, was es ist. Festgehalten, weil eine Entscheidung ohne
ihre verworfenen Alternativen willkürlich wirkt — und weil die späteren Korrekturen
zeigen, wo die frühen Annahmen falsch waren.

Alle inhaltlichen Entscheidungen stammen von **Birk Schmithuesen** (ArtesMobiles). Die
Vorüberlegungen entstanden in einer Brainstorming-Session zwischen ihm und dem
Hermes-Agenten; die Umsetzung folgte danach.

---

## Das Vorhaben

**Workshop am 05. und 06.09.2026 in Dortmund**, mit einem Migrantinnenverein. Zehn
Laienschauspielerinnen in drei Kleingruppen entwickeln aus **eigenen Interviews** ein
Theaterstück.

Der Ablauf in Phasen: gemeinsame Begriffssammlung im Plenum · Begriffe je Gruppe ·
Interviewfragen entwickeln · Interviews führen · Verdichtung zu Kernthemen ·
Figurenentwicklung · Hauptkonflikt · Szenen · Feinschliff.

**Netto stehen dafür 9,25 Stunden zur Verfügung.** Diese Zahl erklärt fast jede
Entscheidung über Latenz und Bedienbarkeit weiter unten: Alles, was die Gruppe aufhält,
kostet einen messbaren Anteil des gesamten Workshops.

**Das Werkzeug soll über diesen Workshop hinaus taugen** — ein weiterer Workshop in Padua
(21.09.–09.10.2026) und ein monatlicher Serienbetrieb sind vorgesehen. Daraus folgt eine
harte Regel: **keine workshop-spezifischen Sonderwege.** Was nur in Dortmund funktioniert,
ist ein Konstruktionsfehler, keine Abkürzung.

---

## Grundhaltungen

### Datensouveränität, ehrlich benannt

**Infomaniak in der Schweiz** statt eines US-Anbieters, offene Modelle, kein Training auf
Kundendaten. Das gilt für Spracherkennung (Whisper) und Sprachmodell.

**Telegram ist der bewusst akzeptierte Bruch in der Kette.** Das Rohaudio läuft darüber,
also außerhalb der EU. Diese Entscheidung wurde getroffen, weil die Kleingruppen autonom
arbeiten können müssen und Telegram das einzige Werkzeug ist, das alle schon auf dem
Telefon haben.

**Konsequenz für die Außendarstellung:** Das Werkzeug darf nicht als „vollständig souverän"
verkauft werden. Der Bruch wird benannt, nicht verschwiegen — in `README.md` und im
Einwilligungsgespräch zu Beginn jedes Workshops.

### Der Bot moderiert, er entscheidet nicht

Birks Formulierung: ein *„gutes Gewicht zwischen Guidance und Offenheit"*. Die Gruppe hat
die Entscheidung über den kreativen Ablauf. Der Bot schlägt vor und moderiert; seine
Vorschläge sind **Andockpunkte zum Reagieren**, keine Vorgaben.

Daraus folgt technisch, dass es **keine Phasen-Zustandsmaschine** gibt. Die acht Stationen
sind eine Beschreibung, kein Ablaufplan. Die Gruppe darf jederzeit abbiegen, zurückspringen
oder verwerfen — und es gibt keinen gespeicherten Zustand, der ihr widersprechen könnte.

### Belegzitate als Prinzip

Ein Vorschlag wird mit dem **wörtlichen Zitat** ausgeliefert, an dem er hängt. Nachprüfbar
statt behauptet. Ein Konfliktvorschlag mit Beleg ist Dramaturgie; einer ohne ist ein
Automat.

Serverseitig geprüft: Kommt das Zitat nach Normalisierung nicht wörtlich im Transkript vor,
wird der Vorschlag **ohne** Zitat ausgeliefert — nie verworfen, aber auch nie mit einem
erfundenen Beleg.

### Verdichtungen werden nie überschrieben

Was beim Einlesen eines Interviews an Zusammenfassung und Kernthemen entsteht, bleibt so
stehen. Kein nachträgliches Umschreiben.

---

## Architekturentscheidungen und die verworfenen Alternativen

### Fünf Prozesse statt eines Multi-Chat-Bots

**Gewählt:** ein eigener Bot-Prozess je Kleingruppe, eigener Telegram-Token, gleicher Code
mehrfach gestartet, gemeinsame SQLite mit WAL.

**Verworfen:** ein Prozess, der alle Gruppen bedient und intern nach `chat_id` trennt.

**Begründung:** Physische Isolation kann nicht versagen. Eine Verwechslung zwischen zwei
Gruppen wäre der Fehler mit dem größten Schaden — die Frauen sprechen über ihr eigenes
Leben, und Material der einen Gruppe darf nie bei der anderen landen. Eine Trennung, die
aus einem `WHERE chat_id = ?` besteht, ist eine Zeile Code von einem Fehler entfernt; eine
Trennung, die aus getrennten Prozessen besteht, ist es nicht.

Ergänzend: **Jede Gruppe arbeitet nur mit ihrem eigenen Material.** Kein gemeinsamer Pool.

### Journal statt laufender Zusammenfassung

**Gewählt:** eine wachsende Liste knapper Einträge, die **nie umgeschrieben** werden.

**Verworfen:** eine laufende Zusammenfassung des Chatverlaufs, die periodisch neu erzeugt
wird (der Lehrbuchansatz).

**Begründung, in drei Teilen:** Eine Zusammenfassung von Zusammenfassungen **driftet** über
zwei Tage. Sie bräuchte einen zusätzlichen Modellaufruf zu unvorhersehbaren Zeitpunkten —
also einen neuen Fehlerpunkt genau unter Volllast. Und sie widerspricht der Regel, dass
Verdichtungen nicht nachträglich angefasst werden.

**Der wertvollste Teil des Journals ist das Verworfene.** Ein Bot, der um 16 Uhr nochmal
vorschlägt, was um 11 Uhr abgelehnt wurde, verliert das Vertrauen der Gruppe. Genau diese
Information steht in keiner anderen Schicht: nicht im Arbeitsstand (dort steht nur der
Stand, nicht der Weg) und nicht mehr im Verlaufsfenster (dort ist sie längst
herausgerollt).

Die Einsicht dahinter, die den Entwurf umgestellt hat: Das Problem war nie „der Verlauf ist
zu lang", sondern **„das Wichtige liegt in der falschen Schicht"**. Verdichten heilt das
Symptom durch Informationsverlust; Mitschreiben heilt die Ursache.

---

## Die Korrekturen — wo frühe Annahmen falsch waren

Diese sechs Punkte sind aufschlussreicher als die ursprünglichen Entwürfe, weil sie zeigen,
was sich erst im Kontakt mit der Wirklichkeit herausstellte.

### 1. Der Bot antwortet auf jede Nachricht

**Ursprünglich:** Der Bot antwortet nur auf Reply, `@`-Erwähnung, `/`-Befehl oder
Sprachnachricht. Begründung war, dass in einem Gruppenchat mit vier Personen nicht jede
Nachricht an den Bot gerichtet ist.

**Korrigiert von Birk:** *„die gruppe ist ein reines interface zu dem bot. es macht mehr
sinn, dass er auf alles antwortet. die frauen diskutieren nicht untereinander in der
gruppe, das machen sie live mouth to mouth."*

Die ursprüngliche Annahme war die eines gewöhnlichen Gruppenchats. Hier gibt es aber gar
kein Nebengespräch, das man heraussortieren müsste — die Frauen stehen im selben Raum.

### 2. Der Interviewmodus ist mechanisch, nicht nach Dauer

**Ursprünglich:** Sprachnachrichten unter 45 Sekunden gelten als Gesprächsbeitrag, längere
als Interview-Material.

**Korrigiert:** Die Gruppe schaltet den Modus ausdrücklich („wir machen jetzt ein
Interview" … „fertig").

**Begründung:** Ein Interview kann aus fünf kurzen Sprachnachrichten bestehen, eine
Regieanweisung länger als eine Minute dauern. **Die Dauer sagt nichts über die Art aus.**
Die 45 Sekunden waren eine Näherung, die niemand gemessen hatte.

### 3. Der Arbeitsstand füllt sich von selbst

**Ursprünglich:** Slash-Befehle schreiben den Arbeitsstand, das Modell nie. Begründung war
die Fehlerrichtung — ein Modell, das selbst schreibt, füllt den Arbeitsstand mit
unbestätigten Entwürfen.

**Korrigiert von Birk:** *„Begriff eintippen ist keine Option. Das soll automatisiert
gehen."*

Die neue Regel: **Der Absichtserkenner schreibt, der Bot meldet jede Änderung, Befehle
korrigieren.** Die Absicherung ist die Meldung („Notiert: Kernthema = Ankommen. Falls das
nicht stimmt, sagt es mir"), **nicht** eine Bestätigungsabfrage — es wird nicht gewartet,
der Ablauf läuft weiter, die Meldung *ist* die Korrekturgelegenheit.

Der Fehler in der alten Überlegung: Ein Arbeitsstand, der nur durch Zeremonie gefüllt wird,
bleibt leer. Die Gruppe steht im Raum, spielt und spricht — niemand tippt `/kernthema`
mitten in einer Probe.

### 4. Löschen und Korrigieren muss per Fließtext gehen

**Begründung:** Die beiden geplanten Weboberflächen sind **read-only**. Der Chat ist damit
der einzige Schreibweg — also muss er auch der Rückweg sein. Ein Werkzeug, in das man nur
hinein-, aber nicht herauskommt, ist unbrauchbar.

**Grenze, bewusst gezogen:** Der **Arbeitsstand** ist frei überschreib- und entfernbar.
**Material** — Audio, Transkripte, Verdichtungen — ist **nicht** per Fließtext löschbar. „Das
können wir löschen" ist im Gespräch zu leicht falsch verstanden, und der Schaden ist
unumkehrbar. Dafür bleibt das Betreiberskript.

**Gebaut am 04.09.2026** (Erkenner-art `entfernen`, `/figur … entfernen`,
`/szene … entfernen`, `/kernthema aus`), und zwar als *weiches* Löschen: entfernte
Figuren, Szenen und Journalzeilen bekommen einen Zeitstempel und verschwinden aus jeder
Ansicht, aber nicht aus der Datenbank. Die Grenze zum Material steht doppelt — der Prompt
weist Löschwünsche für Aufnahmen ab und verweist ans Team, und der Code kennt gar keinen
Weg dorthin.

### 5. Verworfen: „Tag 1 und Tag 2"

Ein Zwischenentwurf wollte den Journal-Extraktor auf nach dem ersten Workshoptag
verschieben, mit dem Argument, sein Nutzen entstehe erst, wenn viel verworfen wurde.

**Birk hat widersprochen:** *„das ganze projekt ist auch ein prototyp fuer ein
interview-theater tool, das unabhaengig von dem workshop funktioniert. also die logik tag 1
und tag 2 gefaellt mir nicht. es sollte immer alles funktionieren."*

Er hat recht: Eine Funktion, die erst am zweiten Tag greift, ist ein Konstruktionsfehler,
keine Priorisierung. Der Extraktor wurde daraufhin doch gebaut.

### 6. Phasen doch als Zustand — aber hörbar

**Ursprünglich** (Leitsatz 3): „Phasenbewusstsein ist ein Nebenprodukt der Materiallage,
kein Zustand." Es sollte keine Phasen-Zustandsmaschine geben; der Prompt wächst mit dem,
was in der Datenbank steht, und kann der Gruppe deshalb nie widersprechen.

**Entschieden von Birk am 04.09.2026:** Die Phase wird ein gespeichertes Feld — aber eines,
das **sichtbar und korrigierbar** ist. Und der Bot soll den Wechsel **proaktiv** anbieten
oder vollziehen, statt zu warten, bis jemand ihn nennt.

Beides zusammen ergibt die Regel, an der jetzt alles hängt: **Die Phase wird nur hörbar
gesetzt** — von der Gruppe (ein Satz im Chat, oder `/phase`) oder vom Bot mit Meldung.
Nie still. Zurückspringen geht jederzeit, auch von 8 nach 5.

Der eigentliche Punkt: Verworfen war nie *Wissen* über die Phase, verworfen war das
**stille Raten**. Ein Zustand, den niemand ausgesprochen hat, kann der Gruppe
widersprechen, ohne dass sie es merkt — der Bot arbeitet dann an Figuren, während die
Gruppe längst wieder beim Kernthema ist, und keine der beiden Seiten weiß, warum es
hakt. Ein ausgesprochener Zustand hat dieses Problem nicht: er steht im Chat, und ein
Halbsatz korrigiert ihn.

Der automatische Sprung folgt deshalb genau dem Muster, das sich beim Arbeitsstand schon
bewährt hatte (Korrektur 3): **schalten, melden, weiterlaufen** — „Notiert: Kernthema =
Ankommen · wir sind damit bei 4 · Hauptkonflikt. Falls nicht, sagt es mir." Kein
Wartezustand, keine Ja/Nein-Frage. Eine Rückfrage würde die Arbeit anhalten, bis jemand
antwortet; die Meldung *ist* die Korrekturgelegenheit. Widerspricht die Gruppe, greift der
Erkenner das als `phase_setzen` auf und schaltet zurück — derselbe Weg wie bei jeder
anderen Notiz.

Was ausdrücklich **nicht** dazugehört: die Phase steuert den **Fokus** des Bots (je Phase
eine Prompt-Datei — worauf er achtet, was er dort nicht tut), **nicht** seinen
Informationszugang. Die datengetriebenen Blöcke sind unverändert geblieben. Eine Phase,
die dem Bot Material vorenthält, wäre wieder die Zustandsmaschine, die Leitsatz 3
verworfen hat.

---

## Der Weg von außen

Für die beiden geplanten Weboberflächen (Team-Dashboard, projiziert; plus eine Leseansicht
je Gruppe unter `/g/<token>`) steht der Zugang bereits:

**`https://lab.artesmobiles.art/interview_theater/`** über nginx auf *herkules*, per Tailnet an
den vServer auf Port 8010. Zertifikat vorhanden, von einem Handy über Mobilfunk geprüft.

Die Oberflächen selbst sind **noch nicht gebaut**.

---

## Offene Grundsatzfrage: eigenständiger Dienst oder Hermes-Skill?

Nicht entschieden. Beide Seiten mit ihren Argumenten:

**Als eigenständiger Python-Dienst weiterleben** — der heutige Zustand.

- *Dafür:* Berechenbarkeit. Der Ablauf ist Code, nicht Prompt: Was passiert, steht fest und
  ist mit 270 Tests abgesichert. Ein Fehler ist reproduzierbar. Die Latenz ist knapp, weil
  nur die Modellaufrufe Zeit kosten, die wirklich gebraucht werden. Der Prompt-Ballast ist
  minimal — jeder Aufruf bekommt genau seinen Kontext.
- *Dagegen:* Jede Änderung braucht einen Entwicklungszyklus. Das Werkzeug lernt nichts aus
  seinem Einsatz; was im Workshop auffällt, muss jemand von Hand einbauen.

**In den Hermes-Agenten portieren** — Skills statt Code.

- *Dafür:* Selbstverbesserung. Ein Skill lässt sich zwischen zwei Workshops anpassen, ohne
  Codeänderung und ohne Testlauf. Die dramaturgische Führung — der eigentliche Wert — ist
  ohnehin Prompt und nicht Logik. Neue Fähigkeiten (Recherche, Bildgenerierung, andere
  Datenquellen) kämen ohne Neubau dazu.
- *Dagegen:* Deutlich größerer Prompt-Ballast und weniger Berechenbarkeit. Die harten
  Garantien dieses Entwurfs — kein Zustand, der der Gruppe widerspricht; Material geht nie
  verloren; die Kürzung antwortet immer — sind heute Code und ließen sich als Anweisung
  nicht gleichwertig zusichern. Bei zehn Teilnehmerinnen, die über ihr eigenes Leben
  sprechen, ist Verlässlichkeit kein Komfort.

**Ein möglicher Mittelweg**, der hier nur benannt und nicht bewertet wird: die harten
Garantien (Speichern, Löschen, Budget, Nebenläufigkeit) bleiben Code, die dramaturgische
Führung wandert in Skills.
