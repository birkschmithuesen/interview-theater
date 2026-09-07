"""Die Dramaturgie-Pruefung: feinkoernige Befunde statt einer Gesamtnote.

Drei Schichten, von unten nach oben, jede fuer sich nuetzlich:

1. ``mechanik`` -- deterministische Checks ueber die vorhandenen Szenendaten.
   Kein Modellaufruf, kein Netz, reine Funktionen (``conn`` rein, Befunde
   raus).
2. ``beleg`` -- die Belegverifikation ueber ``interview_theater.zitat``:
   ein Judge-Zitat, das im vorgelegten Text nicht woertlich vorkommt, kostet
   den Score. Ein Retry, dann ``unsicher``.
3. ``fanout`` -- sieben Judge-Fragen (B1, A2, A6, A9, A10, A11, C1), je ein
   Aufruf, je eine Frage, mit einem anderen Modell als dem, das die Szenen
   geschrieben hat.
4. ``bilanz`` / ``schleife`` -- die Rueckkopplung (07.09.2026): die Auftraege
   aus Schicht 3 ueber den bestehenden Schreibpfad ausfuehren, noch einmal
   pruefen und die **Scores je Frage und Szene** zwischen den Runden
   vergleichen. Nicht die Zahl der Befunde: ein guter Text erzeugt zu Recht
   keine. Faellt ein Score, hat die Ueberarbeitung geschadet, und die
   Schleife bricht ab.

**Der bestehende Stueck-Judge (``interview_theater.stueckpruefung``) bleibt.**
Er liest das ganze Stueck und gibt sechs Noten; diese Ebene hier gibt keine
Note, sondern Befunde mit Szenennummer und Belegzitat. Beide laufen
unabhaengig voneinander und schreiben in getrennte Tabellen.

Grundlage: ``docs/recherche-story-qualitaet-2026-09-06.md``.
"""
