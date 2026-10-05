# Invarianten-Abnahme der Padua-Browsersimulation: cb200e4 und gefixter Stand

- Datum: 05.10.2026
- Harness: Branch `wt/robo-sim`. Die Läufe vorher und nachher liefen mit `551e61f`.
  Der erste Lauf vorher lief noch mit `eb1de44`; seine Prüfung war nachweislich fehlerhaft (siehe unten).
- App vorher: `cb200e4` (Worktree `.worktrees/sim-cb200e4`, `--app-wurzel`).
- App nachher: dieser Branch. Unter `interview_theater/` ist der Code
  identisch mit `9780250` (`git diff 9780250 551e61f -- interview_theater` ist leer).
- Aufruf je Lauf: `--stationen invarianten --geraet handy --persona student --bericht`.
- Env: Padua-Testumgebung (`betrieb/padua-test.env`, nicht gelesen). Die Simulation überschreibt
  `IT_DB`, `IT_KANAL=web`, `IT_WEB_URL` und `IT_WORKSHOP=padua-2026`.
- Code-Vorgaben entfernt (nach dem `source` gelöscht): `IT_BEGRIFFSBOARD_MIN_ZEICHEN`,
  `IT_BEGRIFFSBOARD_MIN_ABSTAND_S`. Beide Apps laufen damit mit ihren Code-Vorgaben:
  cb200e4 mit 600 Zeichen, nachher mit 100 Zeichen und 20 s.
- Laufordner (ungetrackt, `simulation/browser_laeufe/`):
  - Lauf 1, vorher, alte Prüfung, nur zur Information: `2026-10-05-handy-student-invarianten-125111`
  - **vorher**, gewertet: `2026-10-05-handy-student-invarianten-131718`
  - **nachher**, gewertet: `2026-10-05-handy-student-invarianten-132856`

## Vergleich (`browser_abnahme vergleich`)

– = nicht gemeldet; nicht prüfbar = Prüfung konnte nicht laufen. Die Tabelle
unten stammt aus dem Lauf und kennt „nicht prüfbar“ noch nicht: Ihre „–“ bei
„Leeres Ende-Segment“, „Chat kennt Board nicht“ und „Raumcheck domainweit“
heißen nicht „behoben“ (siehe unten).

| Befund | vorher (cb200e4) | nachher (551e61f) | erwartet |
|---|---|---|---|
| Board-Schwelle (Board leer bzw. liest Transkript nicht) | gemeldet (hoch) | gemeldet (hoch) | vorher gemeldet, nachher weg |
| Leeres Ende-Segment (Stille nach Discussion done) | – | – | vorher gemeldet, nachher weg |
| Werkbank leer / Phase 2 gesperrt | gemeldet (hoch) | gemeldet (hoch) | vorher gemeldet, nachher weg |
| Chat kennt Board nicht | – | – | vorher gemeldet, nachher weg |
| Chat kennt Transkript nicht | gemeldet (hoch) | – | vorher gemeldet, nachher weg |
| Raumcheck domainweit | – | – | vorher gemeldet, nachher weg |

Restbefunde nachher:
- stille_nach_ende

Restbefunde hoch nachher: 1

Abnahme erfüllt: nein — vorher fehlt: stille_nach_leerem_ende, chat_kennt_board_nicht, raumcheck_domainweit; nachher noch da: board_leer_nach_ende, werkbank_leer_phase2_gesperrt

## Warum die Abnahme scheitert: eine gemeinsame Ursache in beiden Ständen

Dasselbe passierte vorher und nachher. Die Persona schloss den Raumcheck in
`p1-kalibrierung` nicht ab: Das Budget von 6 Schritten war aufgebraucht.
Nachher drückte sie zuletzt „try again“, weil das Transkript verstümmelt war
(„What dad waiting?“). Damit stand kein Raumcheck-Cache im Speicher. Nach jedem
Browser-Neustart (eine Diskussion je Station) startete „Start listening“
deshalb erneut den Raumcheck. Der VAD wurde nie aktiv: `rede_ms` ist bei allen
Segmenten leer, und es gab weder `pause`- noch `ende`-Schnitte. Der Harness
drückte nach WAV-Dauer + 5 s „Discussion done“.

`web_chat.beendeDiskussion` setzt `_grund = 'ende'` nur, wenn
`sitzung.vadAktiv` gilt. Das ist an cb200e4 und am gefixten Stand gleich. Das
letzte Segment ging also ohne `ende` hinaus. Der Server schloss die Diskussion
nie ab. Folgen in **beiden** Ständen:

- kein Boardlauf (0 Zeilen in `begriffsboard`),
- keine Bot-Nachricht nach dem Ende,
- keine Werkbank-Begriffe.

Die Befunde nachher sind echt: Eine Gruppe, die „Discussion done“ drückt,
während der Raumcheck offen ist, bekommt genau das zu sehen. Sie zeigen aber
nicht Birks Board-Schwelle. Den Schwellen-Fix kann dieser Lauf deshalb weder
bestätigen noch widerlegen. Weil das Board in beiden Ständen leer blieb, waren
auch „Chat kennt Board nicht“ und der Verhörer-Check nicht prüfbar. Ohne
bestätigte Messung gab es keine `vad_*`-Schlüssel, also war auch „Raumcheck
domainweit“ nicht prüfbar. Diese Zeilen fehlen in vorher.

Die Ursache liegt teils am Werkzeug, teils an der App:

- **Werkzeug:** Das Persona-Budget für `p1-kalibrierung` (6 Schritte) war zu
  klein, und das Fertig-Prädikat (eine Kalibrier-Aufnahme genügt) war zu
  schwach. Es meldete die Station als erreicht, ohne dass der Raumcheck
  bestätigt war.
- **App:** Das verlorene `ende` ohne VAD ist ein echter App-Fehler. Geprüft ist
  das am HEAD `web_chat.py:2908` und an cb200e4 `:2871`
  (`if (letzter && sitzung.vadAktiv)`). Live trifft das jede Gruppe, die den
  Raumcheck überspringt. Dazu ist der Boardlauf mitten in der Diskussion
  gesperrt, weil er einen `pause`-Schnitt verlangt (`brainstorm.py:85`).

Belegt umgesetzt ist nachher: **Chat kennt Transkript**. Vorher standen von 2
sichtbaren Transkriptblasen 0 im Gesprächsprompt, nachher liegt kein Befund vor.

## Kosten

| Lauf | Bot (`aufruf.kosten_chf`, Infomaniak) | Opus-Proxy (Persona-Schritte / Richter Phase / Richter Erklärung) |
|---|---|---|
| 125111 (vorher, alte Prüfung) | 0.0511 CHF | 32 / 6 / 6 |
| 131718 (vorher) | 0.0363 CHF | 13 / 6 / 6 |
| 132856 (nachher) | 0.0268 CHF | 13 / 4 / 3 |
| **Summe** | **0.1142 CHF** | **≈ 89 Aufrufe** |

Die Opus-Zahlen sind aus `schritte.jsonl` und `ergebnis.json` gezählt.
Persona-Entscheidungen `done_station` und JSON-Wiederholungen schreiben keinen
Schritt; die Zahlen sind deshalb Untergrenzen. Die Bot-Seite rief für
`gespraech` und `fragen_ki_vorschlag` ebenfalls `claude-opus-5-5` über den
Proxy auf (siehe `modelle` in `ergebnis.json`); diese Aufrufe sind im
CHF-Betrag nicht enthalten. Whisper ist ebenfalls nicht in `aufruf` erfasst.

## Richter: Onboarding-Checkliste (p1-eintritt)

- vorher (131718), Note 2:
  - hoch: Die Begrüßung endet mit „The buttons below show you the way.“ statt mit einem ersten Schritt.
  - hoch: Das Zwei-Handy-Setup wird nicht erklärt; der CoThinker-Tab fehlt beim Einstieg.
  - hoch: Es fehlt der Hinweis auf die Raumgeräuschmessung.
  - mittel: Kein Satz „warum“ je Begriff.
  - mittel: Die Einführung ist ein langer Block.
- nachher (132856), Note 4:
  - hoch: Der CoThinker-Tab fehlt beim Eintritt und erscheint erst nach dem ersten Austausch.
  - mittel: Das Zwei-Handy-Setup ist nicht sichtbar erklärt; die Gruppe bringt es selbst ein.
    Die Bot-Zeilen „Phone A lies in the middle … Phone B shows the CoThinker“ stehen aber in der Begrüßung.
  - mittel: Die Phase „Terms“ musste erst erfragt werden.
  - Die Punkte Raumcheck-Hinweis und Button-Satz werden nachher nicht mehr gemeldet.
- `p1-kalibrierung` und `p1-zuhoeren` haben nachher keine Richternote (`note` = null). Einen
  `pruefung_gescheitert:nachbereitung` gab es nicht.

## Verhörer (Skript: night shed → night shift; beobachtet: foam → home)

Der geskriptete Verhörer der Station `p1-zuhoeren-2` ist „night shed → night shift“
(`diskussionen.DISKUSSIONEN["verhoerer"]`). Die Invariante `verhoerer_nicht_korrigiert` braucht
ein Board. Vorher und nachher war das Board leer, „night shed → night shift“ war also **nicht
prüfbar** (leeres Board). Die Beobachtungen unten zu foam → home betreffen einen ungeplanten
Verhörer aus der Spracherkennung, nicht das Skript.

- Lauf 1 (125111, cb200e4): Das Board trug „home“ mit dem Zitat „feeling of foam“. Das
  Board-Modell hatte den Verhörer also schon korrigiert; kein Befund.
- Nachher (132856): Der Chat-Bot fragte auf die Wissensfrage selbst nach („foam“ gemeint als
  „home“?). Die Gruppe bestätigte, und „home“ steht in der Werkbank. Der Richter wertet die
  Rückfrage mitten im Zuhören als „hoch“, weil sie den stillen Modus bricht.

## Kam nach jeder der drei Diskussionen eine Bot-Nachricht?

| Station | vorher (131718) | nachher (132856) |
|---|---|---|
| p1-zuhoeren (knapp) | nein. Nur die Zwischenmeldung „still typing up the voice message“ zum Segment davor | nein |
| p1-zuhoeren-2 (verhoerer) | nein. Wieder nur die Zwischenmeldung | nein |
| p1-zuhoeren-3 (nachtrag) | nein. Davor „I can't listen right now …“ und „I can listen again.“ | nein |

Lauf 1 (125111, alte Prüfung, cb200e4) zum Vergleich:

- Bei `p1-zuhoeren` kam nur die Zwischenmeldung. Nach dem Persona-Klick mit leerem
  Ende-Segment folgten 3,5 min Stille. Aufnahme 7 hat `status = fehlgeschlagen`
  („leeres Transkript“), das ist genau Birks Live-Fall.
- Bei `p1-zuhoeren-2` kam die Antwort „The discussion is over. On your term board: …“.

## Risiko (a): Raumcheck nach dem Neustart

Bestätigt.

- Lauf 1: Die Persona übersprang den Raumcheck in `p1-kalibrierung`. Danach erschien er bei
  jedem „Start listening“ nach einem Browser-Neustart wieder, und die Persona übersprang ihn
  jedes Mal.
- Läufe 131718 und 132856: Der Raumcheck wurde nicht bestätigt, es gab also keine
  `vad_*`-Schlüssel im localStorage. `gruppe.kalibrierung_modus` war in allen drei Läufen leer.
- Folge, siehe oben: „Discussion done“ bei offenem Raumcheck verliert das Ende.

## Harness-Korrekturen in diesem Auftrag

1. `eb1de44`: Laufordner absolut an Web, Bot und Prompt-Abzug übergeben. Bei `--app-wurzel`
   liefen sie mit `cwd` im anderen Checkout und hätten dort eine fremde, leere `sim.db` geöffnet.
   Behoben vor dem ersten bezahlten Lauf.
2. `551e61f`, nach Lauf 1, weil der Lauf falsch meldete:
   - Ein leeres Ende-Segment mit `fehlgeschlagen` zählt jetzt als leeres Ende.
   - Die Zwischenmeldung zählt nicht mehr als Antwort auf das Ende.
   - Neu ist `board_nicht_nachgezogen`: Das Board liest ungelesenes Transkript hinter
     `bis_aufnahme_id` nach dem Ende nicht. Der Schlüssel gehört zur Zeile Board.
   - Diskussionsstationen enden mit dem Ende der Diskussion. In Lauf 1 drückte die Persona
     danach „Take these“; das führte nach Phase 2 und leerte den CoThinker.
   - Das Ziel für den Raumcheck verlangt jetzt den ganzen Check.

## Offene Punkte

1. **App, auch am gefixten Stand:**
   - `beendeDiskussion` verliert `ende`, wenn der VAD nicht aktiv ist, etwa bei offenem
     Raumcheck. Folge: kein Abschluss, kein Board, kein Vorschlag, Stille.
   - Ohne bestätigten Raumcheck startet jede neue Zuhör-Sitzung den Raumcheck neu.
   - Entscheidung nötig. Die Frage: Soll der Harness vor „Discussion done“ den Raumcheck
     abschließen oder überspringen? Das wäre ein Szenario-Fix, der diesen echten Befund nicht
     wegdefinieren darf. Oder ist das App-Verhalten zu fixen?
2. **Neuer Lauf nötig:** Die Board-Schwelle, das leere Ende-Segment, „Chat kennt Board“,
   „Raumcheck domainweit“ und der Verhörer sind am gefixten Stand **nicht belegt**: Sie waren
   wegen Punkt 1 nicht prüfbar. Belegen kann sie nur ein neuer Paarlauf (vorher und nachher)
   mit abgeschlossenem Raumcheck. Das Budget dieses Auftrags (je ein Lauf, eine Wiederholung)
   ist aufgebraucht.
3. **Richter-Befunde nachher, beide „hoch“:**
   - Der Bot schreibt während des Zuhörens in den Chat (Zwischenmeldung, Rückfrage foam/home).
   - Der Knopf zeigt „Start listening“, obwohl schon Segmente da sind; der Aufnahmezustand ist
     nicht erkennbar.
4. **Werkzeug:** Die Budgets für `p1-kalibrierung` (6) reichen für einen vollständigen
   Raumcheck mit verstümmeltem Testsatz nicht.
5. App-Fehler (eigene Karte, Birk entscheidet): Ende-Signal geht ohne aktiven VAD verloren
   (web_chat.py beendeDiskussion; ebenso :2805/:3033/:3085 und pegelAn-Abbruch :1783) – Gruppe
   ohne Raumcheck bekommt kein Board und keine Antwort.
6. Harness gehärtet nach dem Lauf: nicht_pruefbar, ende_nicht_angekommen,
   raumcheck_nicht_bestaetigt – noch nicht in einem bezahlten Lauf erprobt. Dazu: Budget
   `p1-kalibrierung` 6 → 10, und die Zeile „Leeres Ende-Segment“ zählt nachher auch
   `stille_nach_ende`.
