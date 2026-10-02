# Befund: Padua-Prompts Phase 1 und Phase 6 (Karte P, 01.10.2026)

Prüfauftrag Birk (Karte P, E10): die **vollständig arrangierten** Prompts
zweier Phasen unter `IT_WORKSHOP=padua-2026` lesen — Verhaltensanweisung,
deutsche Reste, Widersprüche, Länge — und eine fehlende oder verstreute
Verhaltensanweisung als Vorschlag einbauen.

## Wie die Dumps entstehen

`python -m scripts.erzeuge_prompts_padua docs/prompt-audit/2026-09-30-padua`
(hängt `padua-2026` selbst ein). Das Skript öffnet **keine** bestehende
Datenbank: es baut eine Wegwerf-DB im Temp-Verzeichnis mit zwei erfundenen
Gruppen — eine in Phase 1 (Begriffsliste kommt an), eine in Phase 6 (Setting,
drei Figuren, Geschichte, drei Abschnitte Prosa). Interviewmaterial der
zweiten Gruppe: `simulation/interviews/set1/2-ferzan-bahnhof.md` (frei
erfunden). `IT_DB` zeigt dabei auf die Wegwerf-DB, damit kein Regie-Zettel
aus `betrieb/zusatz*.md` in den Dump rutscht. Vornamen im Verlauf (Giulia,
Marco, Luca) erscheinen dank E8 als „Member 1/2".

| Datei | Was ans Modell geht | Pfad im Code |
|---|---|---|
| `01-gespraech-phase1.txt` | Gesprächszug Phase 1 | `anweisungen.system(bot, 1)` + `kontext.baue` |
| `02-gespraech-phase6.txt` | Gesprächszug Phase 6 | `anweisungen.system(bot, 6)` + `kontext.baue` |
| `03-kurzgeschichte-phase6.txt` | der Prosalauf der Phase 6 (Knopf „Write the story", mit Regie-Notiz) | `kurzgeschichte.systemanweisung` + `baue_nutzertext` |
| `04-szene-prosa-phase6.txt` | Einzelszene als Prosa (Phase 6, „Rewrite scene 2") | `szene.systemanweisung("prosa")` + `baue_nutzertext` |

Der Commit `7f7d137` hält den Stand **vor** dem Vorschlag fest, `de88a0b`
den Stand danach — `git diff 7f7d137 de88a0b -- docs/prompt-audit/2026-09-30-padua/`
zeigt genau den eingefügten Block.

## a) Grundlegende Verhaltensanweisung

### Gesprächsprompt (01, 02) — vorhanden, aber verstreut und für Padua falsch adressiert

Die Bestandteile sind alle da, nur an sieben Stellen über 370 Zeilen verteilt
(Quelle `interview_theater/sprachen/en/prompts/system.md`):

| Bestandteil | Stelle |
|---|---|
| **Rolle** | `system.md:1-3` — „You are the dramaturgical companion of an **amateur theatre group** … not the director … The group makes the decisions." |
| **Ton** | `system.md:180-185` („Offer, don't prescribe", „Keep it short"), `system.md:351-352` („Write in English, in short, natural sentences") |
| **Was er nie tut** | `system.md:156` (nichts erfinden), `:303` (nie „I have saved"), `:354-358` (keine Vornamen, keine echten Namen), `:369ff.` („What you do NOT say") |
| **Wie er fragt** | `system.md:72-80` (erst fragen, dann Varianten der Gruppenidee), `:146` (höchstens eine Frage, am Ende) |

Urteil: **vollständig, aber verstreut** — und an einer Stelle für Padua
**falsch**: die Rolle in `system.md:1` spricht von einer *amateur theatre
group*. In Padua sitzen Schauspielstudierende im dritten Jahr einer
Theaterakademie (Vault: „14 Studierende, ein 3. Jahrgang", „bewusst
dramaturgisch/regie-orientiert"). Ein Bot, der ihnen erklärt, was eine
Szene oder ein Monolog ist, verliert sie in der ersten Stunde. Dazu kommt:
die Arbeitssprache ist Englisch, für die meisten nicht die Muttersprache —
davon steht nirgends etwas; `system.md:351` sagt nur „Write in English".
Die Profilwerte korrigieren das **nicht**: `{{zielgruppe}}` landet im
Rahmenblock („Who performs"), nicht in der Rolle, und der Satz davor bleibt
„amateur".

`system.md` gehört der Sprachschicht (Karte A1) und gilt für jedes englische
Profil — ihn umzuschreiben wäre eine Entscheidung über Padua hinaus. Der
Vorschlag steht deshalb dort, wo AGENTS.md ihn vorsieht: als
**Profil-Anweisung** (`workshop/padua-2026/prompts/anweisung.md`), die
`anweisungen.system()` (`interview_theater/anweisungen.py:347-370`) hinter
die Phasenanweisung jedes Gesprächsprompts hängt. Das Ende des Prompts wiegt
am schwersten (SPEC § 6.1) — genau richtig für eine Korrektur der Rolle.

### Der Vorschlag (eingebaut, zur Abnahme)

```
## Who you are talking to in this workshop

The group are acting students in professional training, not an amateur group: talk to them the way a dramaturg talks to colleagues -- direct, precise, in plain English (for most of them it is not their first language), without explaining basic theatre terms. You are their dramaturgical sparring partner: you suggest and push back, but the play, its themes and every decision belong to them. You never invent what is not in the material or the chat, never name a real person, and never claim to have saved anything. You ask at most one open question per message, at the end -- and when you offer options, they are variants of the group's own idea, not yours.
```

Warum genau dieser Text, Satz für Satz:

1. **Rolle + Ton, Padua-spezifisch.** Überschreibt „amateur" aus
   `system.md:1`, ohne `system.md` anzufassen. „Plain English … not their
   first language" ist der einzige Hinweis auf Nicht-Muttersprachler im
   ganzen Prompt. **ANNAHME (unbelegt):** dass die meisten keine
   Muttersprachler sind, schließe ich aus „Akademie in Padua" + „Sprache
   Englisch (auch die Präsentation)"; der Vault sagt es nicht wörtlich.
2. **Wer entscheidet.** Wiederholt `system.md:1-3` bewusst am Ende, weil
   „sparring partner … push back" für Studierende sonst als „der Bot hat
   eine eigene Agenda" gelesen werden könnte.
3. **Was er nie tut** — die drei Verbote mit gemessenem Schaden
   (erfundene Zitate, echte Namen/E8, behauptete Schreibvorgänge), an einer
   Stelle gebündelt statt an vier.
4. **Wie er fragt** — und löst dabei Widerspruch c1 (unten) in Richtung der
   jüngeren Regel auf: Varianten der Gruppenidee, nicht „ONE thing".

Vorher/nachher (Ende des Systemteils von `01-gespraech-phase1.txt`):

Vorher (`7f7d137`, 25 732 Zeichen Systemtext):

```
Result of the phase: the list of terms is in the progress. It is finished
exactly then -- after that, it's on to the questions.

=== NUTZER (393 Zeichen, ~131 Token) ===
```

Nachher (`de88a0b`, 26 467 Zeichen Systemtext, +735 Zeichen ≈ +245 Token):

```
Result of the phase: the list of terms is in the progress. It is finished
exactly then -- after that, it's on to the questions.

<!-- VORSCHLAG zur Abnahme -->
## Who you are talking to in this workshop

The group are acting students in professional training, not an amateur group: …

=== NUTZER (393 Zeichen, ~131 Token) ===
```

Die Zeile `<!-- VORSCHLAG zur Abnahme -->` setzt nur das Dump-Skript
(`scripts/erzeuge_prompts_padua.py`, `_markiere`); der Bot bekommt sie nicht,
und `anweisung.md` trägt sie nicht (Test
`test_padua_haengt_seine_verhaltensanweisung_an_jeden_gespraechsprompt`).
Dortmund bekommt die Datei nicht und bleibt bitgleich
(`tests/test_profil_bitgleich.py` grün).

### Prosaprompts (03, 04) — Rolle ja, Verhaltensanweisung im engeren Sinn nein, und das ist richtig so

`03`: „You are writing the short story of a theatre play." (`sprachen/en/texte.toml:1101`,
`kurzgeschichte.ANWEISUNG`). `04` hat gar keine Rollenzeile, sondern beginnt
mit dem Regelblock `formen/prosa.md`. Beide sind **Schreibaufträge ohne
Gesprächspartner** — Ton gegenüber der Gruppe, Frageweise, Anrede gibt es
dort nicht. Was ein Verhalten ist (nichts erfinden, keine Moral, keine
KI-Floskeln), steht in `formen/prosa.md` Regeln 8–10 und in
`theater-tells.md`. Die Profil-Anweisung erreicht diese Läufe **nicht**
(`anweisungen.system()` wird dort nicht gerufen) — gewollt, sie redet über
die Gruppe, nicht über den Text. Kein Vorschlag nötig; die eigentlichen
Probleme dieser beiden Prompts sind Widersprüche (c4–c6).

## b) Deutsche Reste

Wortsuche über alle vier Dumps (Liste typischer deutscher Wörter, Umlaute,
deutsche Datumsform):

| Rest | Wo | Einordnung |
|---|---|---|
| `VORSCHLAG BEGRIFFE:` … zwölf Markerzeilen, dazu `Ende:` und `ABSCHLUSS:` | 01/02, `system.md` Suggestion-Block | **Absicht:** Maschinenmarker, `vorschlag.py` liest genau diese Wörter. Aber: das Modell muss deutsche Labels in eine englische Antwort schreiben; `Ende:` ist leicht mit einem englischen „End:" zu verwechseln → prüfen, ob `vorschlag.py` englische Aliasse bekommen soll. |
| `ZUSAMMENFASSUNG:`, `TITEL:`, `KURZ:`, `ANDERS GEMACHT:` | 03/04 | **Absicht:** Parser-Labels. `kurzgeschichte.zerlege` liest auch `Summary:`, `szene.py` auch `TITLE` — der Prompt verlangt trotzdem die deutsche Form. Funktioniert, liest sich für ein englisches Modell fremd. |
| `/aufnahme`, `/stand`, `/kernthema`, `/stueck rahmen`, `/auswerten`, `/phase`, `/hilfe`, `/wortlaut`, `/figur`, `/szene`, `/interview`, `/fertig` | 01/02, `system.md:209-237` | Deutsche Befehlsnamen — englische Aliasse sind Annahme A4, nicht gebaut. Der Bot nennt sie nur auf Nachfrage. |
| „Herkules measure", „Herkules.exe" | 02 (`phasen/6.md:10`), 03/04 (`formen/prosa.md`, `theater-tells.md`) | Kein Deutsch, aber ein interner Eigenname ohne Erklärung; die Padua-Gruppe kennt Herkules nur aus der Demo an Tag 1. |
| Datumsangaben `06.09.2026`, `05.09.2026 12:25` | 01 (7×), 02 (10×), 03/04 (3×) | Deutsche Datumsform und Dortmunder Betriebsgeschichte („measured on the test evening", „live case of group 1") im Prompt — für das Modell Rauschen, kein Verhalten. |
| Beispielnamen „Nadia, Ines, Karim", „Lena" | 01/02 (`system.md:309`), 03/04 (`theater-tells.md`) | Dortmunder Beispielfiguren; laut Audit 06.09. werden Beispielnamen nachgeplappert. |

Kein deutscher Fließtextsatz in keinem der vier Dumps.

## c) Widersprüche zwischen Blöcken

> **Abgelöst am 01.10.2026:** c1–c10 sind entschieden und umgesetzt — was blieb, was ging und mit welchem Code-Beleg, steht in `docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md`. Der Abschnitt unten bleibt als Stand von vorher stehen.
>
> - **c1** bleibt: zwei bis drei Optionen (`en/system.md:67`, `:74-76`), Winkel-Regel nur in `anweisung.md`; geht: „Suggest ONE thing" und „variants of the SAME idea" — Birks Punkt 7, `anweisungen.py:368-370`.
> - **c2** bleibt: „scene sequence suggestion", „still without a form" (`en/system.md:38`, `:17`); geht: „form … already settled" (`en/phasen/6.md:34`, dazu `:45-46`, `:80-81`) — `kurzgeschichte.py:174`, `szenenfolge.py:313-317`. **Gesamtreview-Nachtrag (02.10.2026):** `en/system.md:39-40` „A scene without a form is not written" galt uneingeschraenkt und widersprach Phase 6 (`szene.py:685-693`: `form` ist dort kein Pflichtfeld) — umformuliert zu „is not written as a theatre text; in phase 6 it is first told as a story, without a form".
> - **c3** bleibt: USA-Frage beim Eintritt in Phase 6 (`en/system.md:378`); geht: „asked by the scene run" als einzige Antwort (`:322`, jetzt beide Wege) — `knoepfe/stationen.py:171-189`, `szene.py:2488-2496`.
> - **c4** bleibt: EINE Kurzgeschichte in einem Lauf; geht: „scene by scene" (`en/phasen/6.md:4`) — `kurzgeschichte.py:72-82`, `szene.py:2241-2246`.
> - **c5** (**vorlaeufig**) bleibt: Abschnittszahl wählt das Modell, Szenenfolge ist Anregung (`texte.toml:1116-1119`); geht: „If a scene sequence already exists, it is binding" (`en/formen/prosa.md:28`) — `kurzgeschichte.py:79-82`, `:168-186`. Nicht zurueckgenommen, aber offen: siehe Restspannung 6 im Gesamtreview-Befund (`2026-10-01-padua-fix/BEFUND.md`).
> - **c6** bleibt: „Your output" gilt der Einzelszene, der Ganz-Lauf folgt `ANWEISUNG`; geht: „Exactly in this form" für jeden Auftrag und „whole instruction" (`en/formen/prosa.md:13-14`) — `kurzgeschichte.py:137-165`, `:235-248`, `szene.py:351-354`.
> - **c7** bleibt: Tells als Sprachhygiene auch für Prosa; geht: „not in prose, not in an essay" (`en/theater-tells.md:7`) — `szene.py:338-343`, `kurzgeschichte.py:246-248`.
> - **c8** bleibt: „we're still on the core theme" (`en/system.md:50`, Phase 4); geht: Kernpaket „from the core theme" (`texte.toml:848` → „story") und „station 5" (`en/system.md:44` → 4) — `kontext.py:469-472`, `phasen.toml:35-36`.
> - **c9** bleibt: der Figurenhinweis; geht: „No question about a character's way of speaking" ohne Ausnahme (`en/phasen/6.md:67`) — `kontext.py:788-798`, `:583-590`; `texte.toml:926/934` gehört M1-Fix.
> - **c10** entfällt durch Birks Punkt 3: „projected backgrounds" ist aus dem Profil, „Places" neu formuliert — `profil.toml` `[orte]`.

1. **„ONE thing" gegen „two to three options"** (01/02): `system.md:67-68`
   „Suggest ONE thing, not three to choose from" — sieben Zeilen später
   `system.md:75` „flesh it out into two to three options". Der Vorschlag
   (Satz 4) entscheidet für die zweite, jüngere Regel.
2. **Form je Szene** (01/02): `system.md:37-40` „Every scene has a form … It
   is already in the scene sequence suggestion", und `phasen/6.md:34` „The
   form for each scene is already settled — it was decided with the story" —
   gegen die Phase-6-Einleitung aus `phasentexte.toml` („No stage text, no
   form yet; that comes in the polish") und `formen/prosa.md:13` („The form
   comes later"). In Phase 6 sagt der Prompt also zugleich „Form steht fest"
   und „Form kommt erst in Phase 7".
3. **Wer die USA-Frage stellt** (01/02): `system.md:322` „The question about
   the US model is asked by the scene run … before the first scene" gegen
   `system.md:369ff.` „the bot asks that question when entering the scene
   phase, with two buttons". Stand der Code-Doku (AGENTS.md): beim Eintritt
   in Phase 6 — der erste Absatz ist veraltet.
4. **Szenenweise gegen am Stück** (02): `phasen/6.md:4` „Now the texts are
   written -- scene by scene" gegen `phasen/6.md:63` „Phase 6 writes ONE
   short story in one go".
5. **Abschnittszahl frei gegen bindend** (03): `kurzgeschichte.ANWEISUNG`
   „You choose the number of sections yourself … A scene sequence is a
   suggestion, not a requirement" gegen `formen/prosa.md:28` „If a scene
   sequence already exists, it is binding". Im Dump existiert eine
   Szenenfolge — das Modell bekommt beide Sätze.
6. **Zwei Ausgabeformate in einem Prompt** (03): `ANWEISUNG` verlangt
   `1. Title` + `ZUSAMMENFASSUNG:` je Abschnitt; der angehängte
   `formen/prosa.md` („This file is the **whole** instruction", Abschnitt
   „Your output") verlangt `TITEL:/KURZ:/ZUSAMMENFASSUNG:/ANDERS GEMACHT:`
   und „Scene N — Title". Der Parser verzeiht beides, das Modell muss raten.
7. **Tells für Bühnendialog im Prosalauf** (03/04): `theater-tells.md` sagt
   selbst „not in prose", Tell 11 verbietet „Narrative prose in the scene
   text" — angehängt an einen Auftrag, der Prosa verlangt.
8. **Kernthema als Grundlage** (02): der Kopf des Kernpakets
   (`texte.toml:840`) „Characters and scenes come from the core theme" —
   das Kernthema ist seit dem Phasen-Umbau keine Station mehr, und die
   Padua-Gruppe hat keins. Verwandt: `system.md:44` („framing decision in
   station 5") und `:50` („we're still on the core theme").
9. **Sprechweise** (02, 04): `phasen/6.md` „No question about a character's
   way of speaking" gegen den Figurenhinweis im Nutzertext („These characters
   are still missing the interview they speak from … ONE sentence about it").
   In 04 steht „Their way of speaking isn't backed by interviews yet"
   (`texte.toml:926`), obwohl jede Figur einen `sprachstil` hat — der
   Einzelszenenweg liest nur `sprachprofil`.
10. **Klein, vom Profil verursacht:** „Where it is shown: … in front of
    AI-generated projected backgrounds" neben „The scenes need no set" —
    kein echter Widerspruch (Projektion ist kein Bühnenbild), aber ein
    Satz, den Birk abnehmen sollte. Und „Places: places from everyday life"
    (Dopplung in `rahmen-kurz.md`, gilt genauso für Dortmund).

Nicht widersprüchlich: Anrede („you", als Gruppe) und Register (informell,
kurz) sind in allen Blöcken gleich; der Vorschlag hält beides.

## d) Länge

Gesprächsprompts nach `kontext.schaetze` (Zeichen ÷ 3), Prosaprompts nach
`szene.SZENE_ZEICHEN_JE_TOKEN` (÷ 1,9, gemessen an deutscher Prosa — für
Englisch eher zu vorsichtig).

| Dump | System | Nutzer | Gesamt Zeichen | ≈ Token |
|---|---|---|---|---|
| 01 Gespräch Phase 1 (vorher) | 25 732 | 393 | 26 125 | 8 708 (÷3) |
| 01 Gespräch Phase 1 (nachher) | 26 467 | 393 | 26 860 | 8 953 (÷3) |
| 02 Gespräch Phase 6 (vorher) | 29 946 | 2 421 | 32 367 | 10 789 (÷3) |
| 02 Gespräch Phase 6 (nachher) | 30 681 | 2 421 | 33 102 | 11 034 (÷3) |
| 03 Kurzgeschichte Phase 6 | 12 145 | 1 433 | 13 578 | 7 146 (÷1,9) |
| 04 Einzelszene Prosa Phase 6 | 11 034 | 2 535 | 13 569 | 7 142 (÷1,9) |

Der Systemteil macht in beiden Gesprächsprompts über 90 % aus; der Vorschlag
kostet ~245 Token je Zug. Die Nutzertexte sind klein, weil die Wegwerf-DB
einen kurzen Verlauf hat — im Betrieb wächst der Nutzertext bis zur Grenze
`kontext.ZEICHEN_GRENZE_VORGABE` (24 000).

## Was Birk entscheidet

- Den Wortlaut der Profil-Anweisung (oben) — und ob „not their first
  language" stimmt.
- Die `ANNAHME (unbelegt)`-Zeilen in `workshop/padua-2026/profil.toml`
  (Spielorte, ausgeschlossene Orte, Ort der Werkschau, Beispielorte,
  Konfliktrahmen, Konflikt-Ausschlüsse).
- Ob die Widersprüche c2–c9 vor dem 05.10. in der Sprachschicht bereinigt
  werden (c2 und c4 stehen nachgeprüft gleichlautend in
  `interview_theater/prompts/phasen/6.md:4,34,63`, betreffen also Dortmund
  mit — außerhalb dieser Karte).
