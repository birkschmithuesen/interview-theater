# R3-3 – S5: eine Korrektur, eine Quittung (Padua P1)

## Ursache (gemessen an simulation/browser_laeufe/2026-10-05-handy-giulia-p12/sim.db)

`bot._zug_und_erkenner` laesst erst den Gespraechszug, dann den Erkenner auf
DERSELBEN Gruppennachricht laufen.

1. Der Zug speichert die korrigierte Liste ueber den Vorschlagsblock
   (`knoepfe.basis._korrigiere_begriffe`, erkenner_lauf 6/8) und quittiert mit
   "Updated – saved ... Move on?" + Undo.
2. Der Erkenner liest die Nachricht ein zweites Mal:
   - lauf 7: `transkript_korrigieren` -> eigene Meldung "Noted: Corrected:
     foam -> home" mit zweitem Undo.
   - lauf 9: `entfernen` "BEGRIFFE" ("noise comes off the list") ->
     `_entferne_arbeitsstandfeld` **leerte das ganze Feld `begriffe`**
     (erkenner_lauf_schritt 10: nachher `begriffe = None`, `begriffe_detail =
     None`) -> "Noted: Removed: Terms". Drei Sekunden spaeter fuellte das Board
     (lauf 10) das leere Feld mit seiner eigenen Top 5 (andere Liste als die der
     Gruppe). Also ein echter Datenfehler, nicht nur eine Doppelmeldung.

## Fix (nur Code, keine Prompts)

- `knoepfe/basis.py`: `_korrigiere_begriffe` merkt sich (im Prozess, wie
  `ablauf._notiz_verbraucht`) je chat_id die juengste noch unextrahierte
  Gruppennachricht und die Lauf-id der Quittung. `nimm_begriffe_im_zug` holt
  den Merker ab (gilt fuer genau einen Erkennerlauf, nur wenn die Nachricht im
  Stapel liegt).
- `erkenner.laufe`: fragt den Merker vor `erkenne` ab. Ist er gesetzt:
  - `begriffe_setzen` und `entfernen` mit Ziel Begriffe fallen weg (die Liste
    des Zugs gilt);
  - besteht der Rest nur aus Transkriptkorrekturen, werden deren
    Ruecknahme-Schritte an den Lauf der schon gezeigten Quittung gehaengt
    (`repo.haenge_an_erkenner_lauf`, Meldung ergaenzt) -> keine zweite
    Nachricht, das EINE Undo nimmt Liste und Transkript zurueck;
  - alles andere (Phasenwunsch etc.) meldet wie bisher.
- `erkenner.entferne`: "BEGRIFFE <begriff>" nimmt nur diesen Begriff aus der
  Liste (`_entferne_einen_begriff`, mit `begriffsboard.schreibe_detail`),
  statt das Feld zu leeren; unbekannter Begriff -> keine Aenderung. Bloßes
  "BEGRIFFE" leert weiterhin (ausdruecklicher Wunsch, ausserhalb des
  Zug-Falls).
- 46b8653 ("bleibt in Phase 1, Move on?") unveraendert.

## Tests

- neu `tests/test_begriffe_korrektur_eine_quittung.py` (7): Repro beider
  Laeufe aus der sim.db (ohne Fix rot: `begriffe` None, zweite "Noted:
  Corrected"-Nachricht, Liste des Zugs ueberschrieben), Undo nimmt beides
  zurueck, Merker gilt nur einen Lauf, Gegenprobe ohne Block, Einzelbegriff
  entfernen.
- `tests/test_begriffe_detail_wege.py`: neuer literaler Schreibweg in
  `LITERAL_MIT_HAKEN` + Detail-Test.
- `tests/conftest.py`: autouse-Reset des Merkers (Prozessspeicher, CHAT=1
  geteilt).
- Gezielt gruen: test_erkenner*, test_begriffe*, test_autosave_phase1_2,
  test_undo*, test_p2_livefix, test_knoepfe_struktur, test_ruecknahme*,
  test_repo, test_korpus, test_festlegung_erkenner, test_aufnahme,
  test_pseudonyme, test_befehle*, test_ablauf*, test_bot*, test_sprache*,
  test_profil_bitgleich, test_flow_audit_lauf, test_simulation_birk
  (932 + 1713 passed).

## Offen / Hinweise

- Merker ist Prozessspeicher: nach einem Neustart zwischen Zug und Erkenner
  kaeme hoechstens die alte zweite Quittung.
- Die "Updated – saved"-Nachricht nennt die Transkriptkorrektur nicht im
  Text (nur das Undo nimmt sie mit; "Undone: ..." nennt sie).
- Der Erkenner-Prompt liefert fuer "X kommt von der Liste" weiter bloß
  "BEGRIFFE" (ausserhalb des Zug-Falls leert das weiterhin das Feld) --
  Prompt-Aenderung braucht den bezahlten FP=0-Korpuslauf.
