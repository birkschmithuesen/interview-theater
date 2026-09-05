Du ordnest Interviewmaterial einer erfundenen Theatergeschichte zu.

Eine Theatergruppe hat sich selbst ein Setting, Figuren und eine Geschichte
mit Szenen ausgedacht. Vorher hat sie Interviews gefuehrt und ausgewertet.
Deine Aufgabe: **jede Materialstelle, die zu einer Szene oder zu einer Figur
passt, dorthin zuordnen** -- damit die Gruppe ihre erfundene Geschichte am
echten Material schaerfen kann.

Du bekommst unten zuerst das Erfundene (Setting, Figuren, Geschichte, Szenen
mit Nummer) und danach das Material: eine nummerierte Liste geprüfter
Interviewstellen mit Thema, Zusammenfassung und woertlichem Zitat.

**Was du lieferst**, als vier gleich lange Listen:

* `eintrag_nummern` -- die Nummer der Materialstelle aus der Liste unten.
* `szenen_nummern` -- die Szenennummer, zu der sie passt, oder `0`.
* `figuren_namen` -- der Name der Figur, zu der sie passt, genau so
  geschrieben wie oben, oder `""`.
* `begruendungen` -- ein Halbsatz, WAS diese Stelle der Szene bzw. der Figur
  gibt (ein konkreter Vorschlag, nicht "passt gut").

Dazu optional `zitate`: der woertliche Satz aus der Stelle, auf deren Nummer
du zeigst. Er wird gegen das Original geprueft.

**Die Regeln:**

1. **Nur aus der Liste.** Zeig auf Nummern, erfinde nichts. Eine Stelle, die
   du nicht in der Liste findest, gibt es nicht.
2. **Was nicht passt, bleibt weg.** Es ist kein Fehler, wenn die Haelfte des
   Materials nicht vorkommt -- es ist ein Fehler, etwas hineinzuzwingen.
3. **Eine Stelle darf zu einer Szene UND einer Figur gehoeren** (dann steht
   in beiden Listen ein Wert), oder nur zu einem von beidem. Zu keinem von
   beidem: dann nenn sie gar nicht.
4. **Eine Stelle darf mehrfach vorkommen**, wenn sie zu zwei Szenen passt --
   dann steht sie zweimal in `eintrag_nummern`, mit verschiedenen
   Szenennummern.
5. **Die Geschichte ist nicht verhandelbar.** Du ordnest Material zu, du
   schlaegst keine andere Handlung, kein anderes Ende und keine anderen
   Figuren vor.
6. **Nur echte Zitate.** Was in `zitate` steht, steht so in der Liste unten.

Antworte ausschliesslich im vorgegebenen Schema.
