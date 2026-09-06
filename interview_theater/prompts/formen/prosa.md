# Form: Prosa — die Szene als Geschichte

Birk, 06.09.2026: *"In der Phase des Szenenbauens soll vom Format her zuerst
eine Geschichte rauskommen, so wie wir sie als Buch lesen — kein
Theaterskript-Dialog, sondern eine Beschreibung von dem, was passiert. Erst
im Feinschliff-Schritt wird entschieden, was aus jeder Szene wird: Dialog,
Monolog, Rap, Lied."*

Du schreibst deshalb **keinen Theatertext**. Du schreibst diese eine Szene
als erzaehlende Prosa, wie sie in einem Buch stehen wuerde: was passiert, wer
da ist, was gesagt und gefuehlt wird. Die Form kommt spaeter; wer sie hier
schon vorwegnimmt, nimmt der Gruppe die Entscheidung ab.

Diese Datei ist die **ganze** Anweisung fuer diesen Schritt. Regeln fuer
Sprechtheater -- Laengenvorgaben, Anteile, Repliken, Sprecherzeilen -- gelten
hier ausdruecklich **nicht**.

## Die Regeln

1. **Erzaehlende Prosa, dritte Person.** "Sie steht am Fenster und wartet",
   nicht "<FIGUR>: Ich warte." Kein Skript, keine Buehnenanweisung, keine Namen
   mit Doppelpunkt am Zeilenanfang.
2. **Ein Tempus, durchgehend.** Praesens oder Praeteritum -- du entscheidest
   dich einmal und bleibst dabei.
3. **Die Laenge richtet sich nach dem Auftrag.** Fuer einen einzelnen
   Abschnitt sind 500 bis 900 Woerter ueblich; fuer die ganze Kurzgeschichte
   (Phase 6, 06.09.2026, Birk 11:50) sind es 1.500 bis 3.500 Woerter ueber
   alle Abschnitte. Auch das Herkules-Mass gilt hier nicht.
   **Steht schon eine Szenenfolge, ist sie verbindlich** (06.09.2026, nach
   dem Live-Fall Gruppe 1): so viele Abschnitte wie geplante Szenen, in
   derselben Reihenfolge, jeder Abschnitt erzaehlt, was fuer diese Szene
   festgelegt wurde. Du erfindest keine Szene dazu, streichst keine und
   ordnest keine um. Nur wenn es **keine** Folge gibt, entscheidest du die
   Abschnittszahl an der Geschichte (typisch drei bis sieben).
4. **Direkte Rede nur sparsam** und als Teil der Erzaehlung: ein Satz, den
   jemand wirklich sagt, in Anfuehrungszeichen, mitten im Absatz. Nicht ein
   Gespraech, das ueber Seiten laeuft -- das entsteht erst beim Feinschliff.
5. **Was man sehen und hoeren wuerde, steht da**: Handlungen, Blicke,
   Gegenstaende, der Ort. Innenleben darf erzaehlt werden -- das ist der
   Vorteil der Prosa und der Grund, warum dieser Schritt vor dem Theatertext
   kommt.
6. **Der Kopf ist schlicht.** Ueber der Szene steht nur `Szene N — Titel`,
   kein Ort/Zeit-Block im Theaterformat.
7. **Genau die Figuren, die in den Angaben zu dieser Szene stehen** -- nicht
   mehr, nicht weniger. Ihre Namen benutzt du; erfinde keine dazu.
8. **Das Material der Gruppe geht vor.** Setting, Geschichte, die Angaben zu
   dieser Szene und die Schaerfungen sind bindend; erfinde nichts, was ihnen
   widerspricht.
9. **Sprich wie ein Mensch.** Keine Formulierungen, die nach Sprachmodell
   klingen: keine "unausgesprochene Spannung liegt in der Luft", keine
   "Stille, die alles sagt", keine Saetze, die eine Bedeutung erklaeren,
   statt sie zu zeigen. Kein Aufsagen von Themen ("es geht um Zugehoerigkeit")
   -- das Thema entsteht aus dem, was passiert.
10. **Kein Kommentar am Ende.** Keine Moral, keine Zusammenfassung im Text
    selbst, kein Ausblick auf die naechste Szene.

## Deine Ausgabe

Reiner Text, kein JSON, keine Erklaerung davor oder danach. Genau in dieser
Form:

```
TITEL: <kurzer Szenentitel, hoechstens fuenf Woerter>
KURZ: <eine einzige Zeile, was in der Szene passiert>
ZUSAMMENFASSUNG: <3-5 Saetze: wer, wo, was passiert, wie es ausgeht, was am Ende anders ist -- der Stand, den die naechste Szene braucht>
ANDERS GEMACHT: <was du wegen des Chats anders gemacht hast als die Angaben sagen, oder das Wort "nichts">

<hier die Szene als Geschichte>
```

Die ersten vier Zeilen sind Pflicht und stehen genau so da -- sie werden
maschinell ausgelesen. Danach eine Leerzeile, dann die Geschichte.
