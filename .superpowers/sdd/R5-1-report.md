# R5-1 – H4, M7 (Erkenner, Padua)

Nur Code in `interview_theater/erkenner.py`, keine Prompts.

## H4 – Szenen-Sperrtext in Phase 2

Ursache (sim.db msg 334-339): der Erkenner las in Phase 2 zwei Nachrichten
nacheinander als `szene_schreiben` (334 "write me the opening and the closing
now", 337 "No, the scene can wait ... just write them"). Jeder Lauf ging ueber
`_starte_szene` -> `szene.starte` -> Sperrtext "For Scene 1 we still need ...
(phase 4)". "Zweimal" = zwei Erkennerlaeufe auf zwei Nachrichten, keine
doppelte Zustellung.

Fix: neue Tabelle `erkenner.AB_PHASE_ARTEN` (Untergrenze, gleiche Wache
`_ist_phasenpassend` wie `PHASEN_SPEZIFISCHE_ARTEN`): `szene_schreiben` und
`szene_kuerzen` erst ab Phase 4. Davor still verworfen (nur Log), keine
Meldung, kein Lauf; der Rest desselben Laufs (z. B. Festlegung) wirkt weiter.
Untergrenze statt Tupel, damit sie bis zur letzten Phase jedes Profils gilt.
Dortmund und Padua haben dieselbe Nummerierung (1-3 Begriffe/Fragen/
Interviews, ab 4 Setting/Frame mit Szenenfolge) -- kein Profilschalter.

## M7 – zwei Quittungen bei Korrektur + Festlegung

`_haenge_an_zugquittung` haengt jetzt `transkript_korrigieren` UND
`festlegung_setzen` (`_AN_ZUGQUITTUNG`) an den Lauf der schon gezeigten
"Updated – saved ... Move on?"-Quittung. Ein Undo nimmt Liste, Korrektur und
Festlegung zurueck. Alles andere (z. B. Phasenwunsch) meldet weiter selbst.

## Tests

- neu `tests/test_erkenner_szene_phase.py` (11; ohne Fix 6 rot, inkl. Repro
  msg 334/337 mit echtem `szene.starte`: zwei Sperrtexte).
- `tests/test_begriffe_korrektur_eine_quittung.py` +3 (Repro lauf 27/28 und
  29/30, ohne Fix 2 rot; Gegenprobe Phasenwunsch).
- `tests/test_erkenner.py`: 5 bestehende `laufe`-Tests fuer Szene/Kuerzung
  liefen in der Vorgabephase 1 -> setzen jetzt Phase 6.
- Gezielt gruen: test_erkenner*, test_begriffe*, test_szene*, test_undo*,
  test_redo_knopf, test_knoepfe_struktur, test_phasen*, test_kuerzung,
  test_teil2_abschlussreview, test_flow_abdeckung, test_entwurf, test_korpus,
  test_sprache_prompts, test_simulation_lauf/birk, test_flow_audit_lauf,
  test_ablauf, test_bot, test_p2_livefix, test_festlegung_erkenner,
  test_autosave_phase1_2, test_profil_bitgleich, test_fixture_padua_voll
  (1069 + 482 passed).

## Offen / Hinweise

- Der Erkenner-Prompt liefert weiter `szene_schreiben` fuer "write the
  opening" -- jetzt nur folgenlos; Prompt-Aenderung braucht den FP=0-Lauf.
- M10 (Eroeffnung/Abschluss nicht in `interview_eroeffnung`/`_abschluss`)
  unberuehrt (Klasse B).
- Mit M7 erscheint der Festlegungstext nicht mehr als eigene Zeile im Chat;
  nur "Undone: ..." nennt ihn. Der Zug hat ihn in seiner Antwort meist schon
  aufgenommen (msg 259), garantiert ist das nicht.
- Merker bleibt Prozessspeicher (wie R3-3); liegen mehrere unextrahierte
  Nachrichten im Stapel, haengt auch eine Festlegung aus einer frueheren
  Nachricht an die Zugquittung.
