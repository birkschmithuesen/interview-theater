# Übergabe: Stückmodell (Karte t_fd88600b, Birk 10.10.2026)

Branch `wt/t_fd88600b`, Basis `e6b89b6`, kein Merge, kein Push. Plan:
`docs/superpowers/plans/2026-10-10-stueckmodell.md`. Entscheidungen:
`docs/agents/entscheidungen.md` (Abschnitt „Stückmodell").

Leitsatz: Jede Tatsache über das Stück steht an genau einer Stelle; Werkbank,
Karte, Script-Kopf und PDF lesen von dort ab und tragen nichts Eigenes.

## Aufgaben und Commits

| Task | Inhalt | Commits |
|---|---|---|
| 0 | Messbasis (Kopie read-only, Ansichten-Fakten, Prompt-Schnappschuss vorher) | e6b89b6..a2bf2a4 |
| 1 | Schema: `wer_zusatz`, `szene_figur.rolle/position`, `offene_frage`, `veraltet`, `stueck_aenderung` | 08ffddf |
| 2 | repo-Funktionen Ort/Besetzung/Fragen/Veraltet/Protokoll | 801e2d8 |
| 3 | `stueck_sicht`: die eine Ableitung der Karte | bfcf0e0 |
| 4 | Mutations-Schnittstelle Teil A (Ort, Rahmen, Besetzung, Veraltet, Busy-Gate) | 77a2b92 |
| 5 | `karte_aendern` (Kartentreue, `[OPEN]`-Reinigung, Zitat aus Bestand), Wiederöffnen, Reihenfolge | 558dfcf |
| 6 | Fragen schließen im Modell, `karte_aus_modell`, `pruefe_szene`, Zuschnitt-Test | 37f4e69, 95a6ec3 |
| 7 | Format des Konfliktberichts | 2971ba6 |
| 8 | Datenmigration `db._migriere_stueckmodell` | 2683f5c |
| 9 | Alle Bot-Leser auf die abgeleitete Karte | 3e2ad53 |
| 10 | Web liest die abgeleitete Karte; Padua-Werkbank „Wo · Wer" | b1026cc |
| 11 | Karten-Neubau über `karte_aus_modell`, Klärweg schließt sofort | 30e429f, 4c3e50e |
| 12 | `karten_nachzug` schreibt nur über `stueck`; Zweit-Schreiber entfernt | 51fbc37 |
| 13 | Alle Schreiber von Ort/Besetzung/Karte über `stueck`; Sperre gegen Zweitwege | 8c67e5a, 074da88, ca1e660 |
| 14 | Ja/Nein-Angebot „Szene N passt nicht mehr zu … neu schreiben?" | af5fff8, c486de7 |
| 15 | Szenen-Verbote werden Warnungen; `phasen.warnungen` | 29cb349, 469276a, 83ba3b8 |
| 16 | Abnahme-Mutationstests Probleme 1-4 | 90ed9f0 |
| 17 | Ansichtenvergleich, Wiedergabe der Struktur-Wünsche | d6228ef, 7dbb5d6, d67ceef, f0308cd |
| 18 | Doku, Schnappschuss, Übergabe | dieser Commit |

## Abnahmenachweise

### Migration (Kopie von `betrieb/padua.db`, 14 Szenen, 3 Gruppen)

Zähler: `konflikt_ort` 2, `konflikt_wer` 5, `ort_uebernommen` 5.
- Konflikt Ort (Karte gewinnt, EN gegen IT): Gruppe 1 Szene 1, Gruppe 2 Szene 1.
- Konflikt Besetzung (Vereinigung): Gruppe 1 Szene 3; Gruppe 2 Szene 2, 3, 5;
  Gruppe 3 Szene 1. Eine davon (Stimmen 1-5) hat vorher/nachher gleiche Namen,
  weil die Karte nur eine Teilmenge nannte.
- Ort übernommen (Szene hatte keinen, Karte schon): Gruppe 2 Szene 4;
  Gruppe 3 Szene 1, 3, 5, 6.
- Offene Fragen: live keine vorhanden, also keine überführt (Problem 4 wird
  über Abnahmetests und Wiedergabe nachgewiesen).
- Bericht: `var/stueckmodell/padua-migriert.db.konflikte.md/.json` (nicht
  eingecheckt).

### Ansichtenvergleich vorher/nachher (`scripts.stueckmodell_vergleich`)

14 Szenen: 12 `konsistent_gleich`, 2 `vereinheitlicht` (die beiden
Ort-Konflikte), 0 Fehler, Exit 0. Gleich, wo vorher konsistent; ein Wert, wo
vorher widersprüchlich. `karte_wer` ändert sich in einigen Szenen nur im
Trenner („; " / „ e " zu „, "), ohne Textverlust.

### Wiedergabe der Struktur-Wünsche (`scripts.stueckmodell_wiedergabe`)

`p7audit.json`: 69 Wünsche, davon 13 strukturell (Ort, Figuren, Karten,
offene Fragen), davon 1 nicht anwendbar, also 12 anwendbar.
- Vorher (Audit-Stand): 5 von 12 drin, davon 2 ohne Robo-Hilfe.
- Nachher gegen frische Kopie: **11 von 12 korrekt**, 1 Fehler.
- Der eine Nicht-Treffer (Gruppe 2 Szene 3, Widerspruch „saresti l'ultimo"):
  `pruefe_szene` setzt keinen Veraltet-Vermerk, weil `kartentreue.widersprueche`
  rein wörtlich arbeitet (Verneinungsmarker plus derselbe Wortlaut im Text); das
  Skript sagt nur sinngemäß dasselbe (Paraphrase). Die Kopie trägt zudem schon
  den reparierten Text. Nicht weggerechnet.
- Erster Lauf lieferte nur 5/12; zwei echte Fehler im Stückmodell wurden dabei
  gefunden und behoben (d6228ef): `karte_aendern` kappte vorhandene Punkte auf
  6 Stück und 120 Zeichen (Live-Karten haben 9-13 Punkte); eine Rolle für eine
  bekannte Figur vermerkte den Kopf nicht als veraltet.
- Der Plan-Erzeuger ist eingecheckt (`scripts.stueckmodell_wiedergabe_plan`),
  die Plan-JSON nicht (enthält Szenentext und Figurennamen).

### Mutationstests je Problem (Task 16, `tests/test_stueckmodell_abnahme.py`)

Jede Mutation temporär angewandt, Test rot, dann zurückgesetzt:
- Problem 1 Ort: `karte["ort"]` aus zweiter Spalte statt Ableitung: rot
  (`assert 0 >= 5`, Ansichten zeigen Giftwert).
- Problem 1 Wer: `karte["wer"] = roh.get("wer") or …`: rot (Giftwert in
  „Who:").
- Problem 2: `_ziel_mit_warnung` liefert für abgenommene Karte wieder `None`
  (alte Sperre): rot (`None == 1`).
- Problem 3: `_markiere_script` schreibt `volltext` still um, ohne
  `veraltet`-Zeile: rot (beide Tests, `0 == 1`).
- Problem 4: `karte["fragen"]` aus zweiter Spalte: rot (Giftwert im
  Kartentext).
Anmerkung: Die Mutationen für Problem 2 und 3 sind eigene Wahl des
Umsetzers, vom Plan nicht vorgegeben.

### Prompt-Schnappschuss

`scripts.prompt_schnappschuss` (Padua, 14154 Zeichen) vorher gegen nachher:
`diff` leer, also byte-identisch. SYSTEM-Teil unverändert, keine weitere
Änderung (dieser Plan ändert keine Prompt-Datei). Profilprüfung
`pruefe_profil padua-2026`: in Ordnung.

### Tests

Gezielt (Dokutests, Schnappschuss-Tests, `tests/test_stueck*.py`) siehe
Arbeitsbericht; die volle Suite läuft einmal extern nach diesem Lauf.

## Rollout für Birk

- Die Migration läuft beim nächsten Botstart (`db.initialisiere`),
  idempotent, Bericht in `stueck_aenderung` (Quelle `migration`).
- **Alle Prozesse mit demselben Code gemeinsam neu starten:** die drei
  Padua-Bots, den Web-Dienst `interview-theater-web` UND `padua-test` erst
  alle stoppen, dann zusammen starten, **Bots zuerst** (die Migration läuft
  beim ersten Start), danach den Web-Dienst. Ein alter Prozess nach der
  Migration (a) zeigt Karten ohne Ort/Wer/Fragen (liest das rohe JSON),
  (b) schreibt `szene.ort` direkt ohne Protokoll und Vermerk, (c) löscht mit
  dem alten `repo.setze_szene_figuren` `rolle`/`position` jeder Figur der
  Szene (stiller Datenverlust), und (d) schreibt er `karte.fragen` wieder,
  legt der nächste Start die Fragen nicht doppelt an (Abgleich über den
  normalisierten Text, jeder Status – eine beantwortete Frage bleibt
  beantwortet), setzt aber `szene.ort` auf den alten Kartenwert zurück („Karte
  gewinnt"). Den Neustart macht Birk; Agenten starten oder stoppen nie einen
  Live-Dienst.
- Einmalig vorher eine `VACUUM INTO`-Kopie ziehen (Rückfall).
- **Rückfall = die `VACUUM INTO`-Kopie zurückspielen**; alles seit dem
  Rollout geht verloren. Die Migration ist an Ort und Stelle nicht umkehrbar
  (der alte Code liest Ort/Wer/Fragen nicht mehr aus ihren neuen Stellen).
- Eine von altem Code gestartete Klärrunde (`szene.karte_klaerung` ohne `ids`)
  verwirft `beantworte_frage`; die Antwort geht dann in den normalen Chat.
- `wer_zusatz` wird in der Migration überschrieben, ohne dass das im
  Konfliktbericht auftaucht (`db.py` rund Zeile 1886).

## Bewusste Abweichungen

- Werkbank-Zeile „Wo · Wer" je Szene (Padua zeigte bisher keinen Szenenort).
- Ja auf einen veralteten Kopf schreibt Szene 1 mit neu (der Kopf entsteht nur
  in diesem Lauf).
- `[OPEN]`-Punkte aus dem JSON werden in `stueck_sicht.karte_ansicht`
  herausgefiltert.
- Befunde von `pruefe_szene` sind in der Sprache `T`, nicht der
  Gruppensprache (bestehender Unterschied zu `_grund`).
- Fehlender IT-Text `_PUNKT_OFFEN` ergänzt (`[APERTO] {frage}`).

## Offene Kleinigkeiten (aus dem Review-Protokoll)

- Web: zwei Figuren mit gleichem normalisierten Namen fallen zusammen.
- `szenenkarte.merke_karte_verlauf`: Ausnahme vom dateiweiten Wächtertest.
- Tote „nicht ok"-Zweige im Log von `erkenner`, `prueflauf`, `szene`.
- `szenenkarte.bestaetige` in Phase 7 ruft noch `weiter()`.
- Phasenwarnung erscheint auch bei Rückkehr in eine Phase.
- `pruefe_szene` schreibt bei Wiederholung jedes Mal einen Protokolleintrag.
- `punkte_weg` kann zurückgestellte `[OPEN]`-Punkte nicht entfernen.
- Doppelter `[OPEN]` in einem Aufruf wird zweimal angelegt.
- Frage-Protokoll enthält den Antworttext nicht.
- Keine Busy-Gate-Tests für `figur_*`/`karte_*`.
- `kartentreue` erkennt zitierte Verneinungen nicht.
- `test_phase_7_szene_fuer_szene_aus_der_karte` möglicherweise flaky.

## Offene Entscheidungen für Birk (nicht blockierend)

1. `p5_gate` (`befehle.py`) bleibt eine Sperre: Bestätigungsschritt der
   Übersicht, keine Datenvoraussetzung. Soll auch er zur Warnung werden?
2. `erkenner._ohne_phasensprung_vor_fixierten_figuren` bleibt: Schutz vor
   fehlgelesenem Chat; Klick und `/phase` sind frei. Änderung wäre ein
   Erkenner-Umbau (nicht im Umfang).
3. Freier Chat beantwortet eine Kartenfrage ohne Klärweg: bräuchte die
   Erkenner-Art `frage_beantworten`; Erkenner-Prompt-Änderung gilt nur mit
   FP = 0 im bezahlten Korpuslauf. Folgekarte, natürlicher erster Fall für den
   Prüfweg („Erkenner als Werkzeuge", `t_d99ab13c`).
4. Ja auf „Kopf passt nicht mehr" schreibt Szene 1 mit; ein eigener
   Kopf-Lauf wäre ein neuer Modellaufruf, eigene Karte vorgeschlagen.
5. Rücknahme (Undo) eines Erkennerlaufs stellt `szene.ort`/`szene_figur`
   her, räumt aber `veraltet`-Vermerke nicht weg: möglich ist ein
   überflüssiges Ja/Nein-Angebot, nie eine stille Änderung.
