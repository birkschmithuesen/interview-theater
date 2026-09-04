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

## Wie ein Workshop damit abläuft

Der Weg zum fertigen Stück lässt sich grob in acht Stationen beschreiben:

1. Ankommen, erste Begriffe und Assoziationen sammeln
2. Interviewfragen entwickeln
3. Interviews führen
4. Zu einem Kernthema verdichten
5. Figuren entwickeln
6. Hauptkonflikte finden
7. Szenen bauen
8. Szenen feinschleifen

Das ist eine Landkarte, kein Fahrplan. Die Gruppe darf jederzeit abbiegen, zu
einer früheren Station zurückspringen oder eine Entscheidung verwerfen und neu
anfangen. Der Bot widerspricht dem nie mit einem Verweis auf eine Reihenfolge
— es gibt keine, die einzuhalten wäre.

## Was der Bot versteht

Der Bot liest im Chat alles mit und antwortet auf alles. Man muss ihn nicht
besonders ansprechen, nicht erwähnen, nicht anschreiben — jede Nachricht in
der Gruppe erreicht ihn. Der Chat ist ein reines Arbeitswerkzeug mit dem Bot;
die eigentliche Diskussion findet im Raum statt, nicht im Chat.

**Interviews werden gesagt, nicht getippt.** Ein einfacher Satz wie „wir
machen jetzt ein Interview" startet die Aufnahme, „fertig" beendet sie. Alles
dazwischen wird als Material behandelt: transkribiert und zu Kernthemen mit
Belegzitaten verdichtet.

Der Bot merkt sich Begriffe, Kernthema, Figuren und Konflikt von selbst, ohne
dass jemand das eintragen muss. Jede Änderung meldet er kurz im Chat, zum
Beispiel:

> Notiert: Kernthema = Ankommen.
> Falls das nicht stimmt, sagt es mir.

Korrigiert wird durch Widerspruch im Chat — es gibt kein Formular und keine
Bestätigung, auf die gewartet werden müsste. Die Gruppe macht einfach weiter,
und wenn etwas falsch notiert wurde, wird das im nächsten Satz richtiggestellt.

## Die Befehle

Der Bot versteht Sprache, keine Kommandosprache. Für den Fall, dass er etwas
falsch verstanden hat, gibt es sechs Befehle als Notausgang — man braucht sie
nicht, um mit ihm zu arbeiten:

| Befehl | Wirkung |
|---|---|
| `/interview` | Aufnahme von Hand starten |
| `/fertig` | Aufnahme von Hand beenden |
| `/kernthema <Text>` | Kernthema setzen oder korrigieren |
| `/stand` | zeigt, was der Bot sich bisher gemerkt hat |
| `/wortlaut [Name\|aus]` | Originaltranskripte in seinem Gedächtnis mitlesen |
| `/hilfe` | fasst zusammen, wie der Bot funktioniert |

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
