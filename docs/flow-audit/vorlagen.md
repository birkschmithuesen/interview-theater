# Flow-Audit -- Klasse-B-Befunde (02.10.2026)

Gefunden von `simulation/flow_audit.py` (Schicht 1) und bestätigt von
`scripts/flow_audit_lauf.py` (Schicht 2, Persona-Lauf). Nicht behoben --
jeder Fix braucht entweder eine neue Erkenner-Art (mit Korpuslauf, FP=0,
AGENTS.md "Prompt geändert? → Korpus laufen lassen") oder Birks Entscheidung
zum Wortlaut. Sortiert nach Schwere.

1. **Phase 5, Schärfung per Chat (Anlass dieser Karte).** Zustimmung/Änderung
   zu einem Schärfungsvorschlag per Chat ("ja, nimm die Zeile für Szene 1")
   schreibt nichts -- kein Erkenner-Intent, nur `ART_SCHAERFUNG_*`-Knöpfe
   wirken. Fix: neue Art `schaerfung_entscheidung` + Korpusfälle.

2. **Phase 7, inhaltliches Szenen-Feedback per Chat.** "Mach die Mutter
   wütender" löst keine Überarbeitung aus -- nur der Knopf "Passt, aber
   anders" (`ART_SZENE_ANDERS`). Ein Lauf zeigte zusätzlich "Noted: ..."
   ohne Schreibvorgang. Fix: neue Art mit Regie-Notiz + Korpusfälle.

3. **Phase 6, DE+EN: Prompt nennt noch den alten Pro-Szene-Trigger.** Der
   Absatz "sag einfach 'schreib uns Szene 3'" (und EN "write us scene 3")
   steht neben der korrekten Beschreibung des EINEN Kurzgeschichte-Laufs --
   Rest der alten Phase-6-Fassung vor dem Umbau zu `kurzgeschichte.py`.
   Braucht Birks Entscheidung zum Wortlaut, kein Ein-Zeilen-Fix.
