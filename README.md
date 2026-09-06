# interview-theater

Ein Werkzeug, mit dem eine Theatergruppe aus eigenen Interviews ein Stück
entwickelt. Die Gruppe arbeitet dafür in einem Telegram-Gruppenchat mit einem
Bot, der mitschreibt, ordnet und Vorschläge macht — die Entscheidungen trifft
immer die Gruppe.

## Was das Werkzeug tut

Die Gruppe führt Interviews miteinander und schickt sie als Sprachnachricht in
den Chat. Von dort aus geht die Arbeit weiter: Das Material wird
transkribiert und zu Kernthemen mit wörtlichen Belegzitaten verdichtet. Dann
erfindet die Gruppe ihr Stück — Setting, Figuren, Geschichte — und schärft es
anschließend an dem, was in den Interviews wirklich gesagt wurde. Daraus
werden Szenen, erst als Geschichte, dann als Text.

Der Bot begleitet diesen Weg. Er schlägt vor, ordnet ein, hält fest, was
entschieden wurde — er entscheidet aber nichts selbst. Jeder Vorschlag ist ein
Angebot zum Reagieren, keine Vorgabe.

Das Werkzeug ist nicht an einen bestimmten Workshop gebunden. Es entstand
für einen zweitägigen Workshop mit einem Migrantinnenverein in Dortmund
(September 2026, drei Kleingruppen) und ist so gebaut, dass es für jede
Gruppe, jedes Thema und jede Dauer funktioniert — der nächste Einsatz ist ein
dreiwöchiger Workshop in Padua. Wo es im Betrieb Erfahrungen aus Dortmund
gibt, stehen sie in `docs/` als Referenz, nicht als Voraussetzung.

## Wie ein Workshop damit abläuft

Der Weg zum fertigen Stück lässt sich in sieben Stationen beschreiben:

1. **Begriffe** — die im Plenum gesammelte Begriffsliste aufnehmen und ordnen
2. **Fragen** — aus den Begriffen zehn Interviewfragen entwickeln, drei davon
   auswählen, heikle Fragen weicher fassen und daraus einen Gesprächsleitfaden
   bekommen (Eröffnung, Fragen, Abschluss)
3. **Interviews** — Interviews führen, das Material verdichten
4. **Setting, Figuren & Geschichte** — frei erfinden: worin es spielt, wer
   vorkommt, was passiert und wie es endet
5. **Schärfung** — die erfundene Geschichte am eigenen Interviewmaterial
   schärfen: der Bot legt die belegten Stellen neben die Szenen und Figuren,
   die Gruppe übernimmt, was passt
6. **Szenen als Geschichte** — jede Szene erst einmal als Prosa erzählen: was
   passiert, noch ohne Form
7. **Feinschliff** — je Szene die Form wählen (Dialog, Monolog, Chor, Lied,
   Rap), die Geschichte in diese Form übersetzen lassen und das ganze Stück
   noch einmal prüfen

Die Begriffe entstehen **im Raum, nicht im Chat**: gesammelt wird im Plenum,
auf Zetteln oder an der Wand. Was der Bot bekommt, ist die fertige Liste —
getippt, von einem Foto abgetippt oder als Sprachnachricht.

**Erst erfinden, dann schärfen.** Setting, Figuren und Geschichte macht die
Gruppe an Station 4 *ohne* das Interviewmaterial — bewusst. Als der Bot dort
noch alle Verdichtungen vor sich hatte, schlug er nichts anderes vor als die
Interviews, und das Ergebnis war eine Nacherzählung, in der die Gruppe ihren
eigenen Anteil nicht wiedererkannte. Erst an Station 5 kommt das Material
dazu und legt sich *neben* das Erfundene, statt es zu ersetzen.

**Die Form kommt zuletzt.** An Station 6 wird jede Szene als Geschichte
erzählt; erst im Feinschliff entscheidet die Gruppe je Szene, ob daraus ein
Dialog, ein Monolog, ein Chor, ein Lied oder ein Rap wird. Der Bot schlägt
eine Form vor und begründet sie, gewählt wird sie per Knopf — und ohne diesen
Druck schreibt er nichts.

**Es muss nicht immer einen Konflikt geben.** Nicht jede Szene braucht einen —
es kann ein Lied sein, ein Chor oder eine harmonische Szene. Der Bot fragt
danach und nimmt ein Nein als Antwort.

Das ist überhaupt eine Landkarte, kein Fahrplan. Die Gruppe darf jederzeit
abbiegen, zu einer früheren Station zurückspringen oder eine Entscheidung
verwerfen und neu anfangen. Der Bot widerspricht dem nie mit einem Verweis auf
eine Reihenfolge — es gibt keine, die einzuhalten wäre.

**Umgeschaltet wird nur, wenn die Gruppe es sagt.** Der Bot springt nie von
selbst weiter, auch wenn das Material die nächste Station hergäbe: dass eine
Verdichtung fertig ist, heißt nicht, dass keine drei Interviews mehr kommen.
Er fragt stattdessen im Gespräch nach („Kommen noch Interviews, oder fangen
wir mit dem Stück an?") — einmal, nicht bei jeder Nachricht. Die Antwort
genügt, ein Befehl ist nicht nötig.

**Die Station ist der Fokus des Bots, nicht die Grenze der Gruppe.** Wer in
Phase 2 nach Figuren fragt, bekommt welche; die Phase zieht danach einfach
nach.

## Was der Bot versteht

Der Bot liest im Chat alles mit und antwortet auf alles. Man muss ihn nicht
besonders ansprechen, nicht erwähnen, nicht anschreiben — jede Nachricht in
der Gruppe erreicht ihn. Der Chat ist ein reines Arbeitswerkzeug mit dem Bot;
die eigentliche Diskussion findet im Raum statt, nicht im Chat.

**Interviews werden gesagt, nicht getippt.** Ein einfacher Satz wie „wir
machen jetzt ein Interview" startet die Aufnahme, „fertig" beendet sie. Alles
dazwischen wird als Material behandelt: transkribiert und zu Kernthemen mit
Belegzitaten verdichtet.

### So läuft ein Interview

Ein Interview ist **ein** Interview — auch wenn es aus fünf Sprachnachrichten
besteht. Das ist der Normalfall: einmal starten, so oft aufnehmen wie nötig,
einmal beenden.

1. **„wir machen jetzt ein Interview"** (oder `/interview`). Der Bot sagt „Ich
   zeichne jetzt auf."
2. **Sprecht.** Nach jeder Sprachnachricht schickt der Bot ihr Transkript
   wörtlich in den Chat:

   > Interview 1, Teil 3:
   > Wir sind damals im November angekommen, mit zwei Koffern …

   Damit könnt ihr sofort mitlesen, ob angekommen ist, was gesagt wurde —
   solange die Person, die erzählt, noch neben euch sitzt. Kommentiert wird
   nichts, zusammengefasst auch nicht. So viele Sprachnachrichten, wie ihr
   wollt; Pausen dazwischen sind egal.
3. **„fertig"** (oder `/fertig`). Jetzt fügt der Bot alle Teile zusammen und
   sagt euch, was er darin hört:

   > Interview 1 ist durch. Was ich darin höre:
   > Eine Erzählung vom Ankommen im November …
   >
   > Kernthemen:
   > - Drei Monate auf die Papiere gewartet: „wir haben drei Monate auf die Papiere gewartet"
   > - Die Kinder haben beim Amt übersetzt: „meine Tochter hat für mich geredet"
   >
   > Stimmt das so? Sonst sagt es mir.

   **Stehen eure Interviewfragen fest, geht der Bot sie der Reihe nach
   durch:** je Frage, was darauf geantwortet wurde, danach höchstens zwei
   Beobachtungen darüber hinaus. Er bleibt dabei nah an dem, was gesagt
   wurde — „Pfannkuchen mit Schokolade und Banane", nicht „Erinnerung an
   familiäre Esskultur".

   **Jedes Thema braucht ein wörtliches Zitat.** Findet der Bot keines,
   lässt er das Thema weg, statt eines zu behaupten — und findet er zu gar
   keinem eines, sagt er das. Stimmt etwas nicht, sagt es einfach — der Bot
   arbeitet weiter, es wartet nichts auf eine Antwort.

Eine sehr kurze Aufnahme wertet der Bot **nicht** aus: aus drei Sätzen lässt
sich kein Interview verdichten, ohne etwas zu erfinden. Er sagt dann, wie
lang sie war und wie viele Wörter er gehört hat. Soll er es trotzdem tun,
genügt `/auswerten`.

Geht eine Sprachnachricht unterwegs verloren, sagt der Bot, welchen Teil ihr
noch einmal schicken sollt. Hakt es beim Zuhören, holt er es später nach und
schickt das Transkript dann — nichts geht verloren.

Der Bot merkt sich Begriffe, Interviewfragen, Setting, Figuren und Geschichte
von selbst, ohne dass jemand das eintragen muss. Jede Änderung meldet er in
einer Zeile im Chat, zum Beispiel:

> Notiert:
> Setting: Ein Wartezimmer, spätnachmittags

Korrigiert wird durch Widerspruch im Chat — es gibt kein Formular und keine
Bestätigung, auf die gewartet werden müsste. Die Gruppe macht einfach weiter,
und wenn etwas falsch notiert wurde, wird das im nächsten Satz richtiggestellt.

## Die Befehle

Der Bot versteht Sprache, keine Kommandosprache. Für den Fall, dass er etwas
falsch verstanden hat, gibt es Befehle als Notausgang — man braucht sie
nicht, um mit ihm zu arbeiten. Im Menü stehen diese acht:

| Befehl | Wirkung |
|---|---|
| `/aufnahme` | Interview starten — und nochmal, um es zu beenden |
| `/auswerten [Nummer]` | ein Interview doch noch verdichten, das der Bot als zu kurz übergangen hat |
| `/phase [Nummer\|Name]` | zeigt, an welcher der sieben Stationen ihr gerade arbeitet — oder schaltet um, auch zurück |
| `/kernthema <Text>` | Kernthema setzen oder korrigieren, `/kernthema aus` nimmt es wieder weg |
| `/stueck` | zeigt das Setting des Stücks — oder setzt es (`/stueck rahmen <Text>`) |
| `/szene <Auftrag>` | eine Szene ausschreiben lassen (dauert ein paar Minuten), `/szene <Nummer> entfernen` nimmt eine wieder weg |
| `/stand` | zeigt, was der Bot sich bisher gemerkt hat |
| `/hilfe` | fasst zusammen, wie der Bot funktioniert |

Dazu fünf, die er versteht, aber nicht anbietet: `/interview` und `/fertig`
(Aufnahme nur an, nur aus), `/figur <Name> entfernen` (eine Figur wieder
herausnehmen), `/wortlaut [Name|aus]` (Originaltranskripte im Gedächtnis des
Bots mitlesen) und `/leitfaden` (den Gesprächsleitfaden noch einmal zeigen).

Auch das Wegnehmen geht im Gespräch: „die Figur Peter kannst du wieder
rausnehmen" genügt. **Aufnahmen und Transkripte kann der Bot nicht löschen** —
das macht das Workshop-Team von Hand, vollständig und mit Rückfrage.

## Was vorher zu klären ist

Die Teilnehmerinnen sprechen in den Interviews über ihr eigenes Leben. Das
verdient eine ernsthafte Vorklärung, bevor die erste Aufnahme läuft.

- **Sprachaufnahmen und Transkripte werden gespeichert.** Die Aufnahmen laufen
  technisch über Telegram, ein Dienst mit Sitz außerhalb der EU — das gehört
  den Teilnehmerinnen klar benannt, nicht verschwiegen.
- **Spracherkennung und Sprachmodell laufen über einen Schweizer Anbieter**
  mit offenen Modellen, der nicht mit den Daten der Nutzenden trainiert.
- **Es braucht eine Einwilligung zu Beginn** — kurz, mündlich, aber
  ausdrücklich — und eine **Löschzusage, die auch eingehalten werden kann**:
  Das gesamte Material einer Gruppe lässt sich vollständig löschen, auf
  Wunsch jederzeit.

Am besten wird das am Workshop-Morgen in fünf Minuten angesprochen, bevor
irgendjemand zum ersten Mal aufnimmt — nicht nebenbei irgendwann im Verlauf
des Tages.

## Was das Werkzeug nicht tut

Es schreibt kein Stück. Es schlägt Settings, Figuren, Geschichten und
Szenenideen vor und belegt sie, sobald es ums Schärfen geht, mit wörtlichen
Zitaten aus den Interviews — nachprüfbar, nicht behauptet. Was daraus wird,
entscheidet ausschließlich die Gruppe.

Getestet wird das nicht nur an echten Workshops: ein Simulator lässt
erfundene Personen einen kompletten Ablauf durchspielen, damit sich Fehler
wie „ein Interview aus fünf Sprachnachrichten wird als fünf Interviews
behandelt" schon vor dem nächsten Termin zeigen, statt erst währenddessen.

---

Für technische Details, den Aufbau des Codes und Betriebshinweise siehe
[AGENTS.md](AGENTS.md).
