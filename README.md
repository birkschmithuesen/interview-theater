# interview-theater

Ein Werkzeug, mit dem eine Theatergruppe aus eigenen Interviews ein Stück
entwickelt. Die Gruppe arbeitet dafür in einem Telegram-Gruppenchat mit einem
Bot, der mitschreibt, ordnet und Vorschläge macht — die Entscheidungen trifft
immer die Gruppe.

## Was das Werkzeug tut

Die Gruppe führt Interviews miteinander und schickt sie als Sprachnachricht in
den Chat. Von dort aus geht die Arbeit weiter: Das Material wird
transkribiert und zu Kernthemen verdichtet, aus den Kernthemen entstehen
Figuren, aus den Figuren ein Konflikt, aus dem Konflikt Szenentext.

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

Der Weg zum fertigen Stück lässt sich grob in acht Stationen beschreiben:

1. **Begriffe** — die im Plenum gesammelte Begriffsliste aufnehmen und ordnen
2. **Fragen** — aus den Begriffen Interviewfragen entwickeln
3. **Interviews** — Interviews führen, das Material verdichten
4. **Kernthema** — aus den Verdichtungen das Kernthema herausschälen
5. **Figuren** — Figuren aus dem Material entwickeln
6. **Hauptkonflikt** — den Hauptkonflikt benennen
7. **Szenen** — die Szenenfolge entwerfen und die Szenentexte schreiben
8. **Durchlauf** — Durchlauf und Feinschliff vor der Aufführung

Die Begriffe entstehen **im Raum, nicht im Chat**: gesammelt wird im Plenum,
auf Zetteln oder an der Wand. Was der Bot bekommt, ist die fertige Liste —
getippt, von einem Foto abgetippt oder als Sprachnachricht.

**Figuren und Hauptkonflikt sind gleichwertig.** Ob eine Gruppe erst die
Figuren baut und dann den Konflikt benennt oder umgekehrt, entscheidet sie
selbst; der Bot bietet beides an und empfiehlt die Figuren, weil das der
häufigere Weg ist — mehr nicht.

Das ist überhaupt eine Landkarte, kein Fahrplan. Die Gruppe darf jederzeit
abbiegen, zu einer früheren Station zurückspringen oder eine Entscheidung
verwerfen und neu anfangen. Der Bot widerspricht dem nie mit einem Verweis auf
eine Reihenfolge — es gibt keine, die einzuhalten wäre.

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

Der Bot merkt sich Begriffe, Interviewfragen, Kernthema, Figuren und Konflikt
von selbst, ohne dass jemand das eintragen muss. Jede Änderung meldet er kurz im Chat, zum
Beispiel:

> Notiert: Kernthema = Ankommen.
> Falls das nicht stimmt, sagt es mir.

Korrigiert wird durch Widerspruch im Chat — es gibt kein Formular und keine
Bestätigung, auf die gewartet werden müsste. Die Gruppe macht einfach weiter,
und wenn etwas falsch notiert wurde, wird das im nächsten Satz richtiggestellt.

## Die Befehle

Der Bot versteht Sprache, keine Kommandosprache. Für den Fall, dass er etwas
falsch verstanden hat, gibt es zehn Befehle als Notausgang — man braucht sie
nicht, um mit ihm zu arbeiten:

| Befehl | Wirkung |
|---|---|
| `/interview` | Aufnahme von Hand starten |
| `/fertig` | Aufnahme von Hand beenden |
| `/auswerten [Nummer]` | ein Interview doch noch verdichten, das der Bot als zu kurz übergangen hat |
| `/phase [Nummer\|Name]` | zeigt, an welcher der acht Stationen ihr gerade arbeitet — oder schaltet um, auch zurück |
| `/kernthema <Text>` | Kernthema setzen oder korrigieren, `/kernthema aus` nimmt es wieder weg |
| `/figur <Name> entfernen` | eine Figur wieder herausnehmen |
| `/szene <Auftrag>` | eine Szene ausschreiben lassen (dauert ein paar Minuten), `/szene <Nummer> entfernen` nimmt eine wieder weg |
| `/stand` | zeigt, was der Bot sich bisher gemerkt hat |
| `/wortlaut [Name\|aus]` | Originaltranskripte in seinem Gedächtnis mitlesen |
| `/hilfe` | fasst zusammen, wie der Bot funktioniert |

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

Es schreibt kein Stück. Es schlägt Kernthemen, Figuren, Konflikte und
Szenenideen vor und belegt diese Vorschläge, wo möglich, mit wörtlichen
Zitaten aus den Interviews — nachprüfbar, nicht behauptet. Was daraus wird,
entscheidet ausschließlich die Gruppe.

---

Für technische Details, den Aufbau des Codes und Betriebshinweise siehe
[AGENTS.md](AGENTS.md).
