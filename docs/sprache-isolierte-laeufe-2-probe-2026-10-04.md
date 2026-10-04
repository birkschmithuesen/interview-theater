# Sprache isolierter Laeufe (szenenfolge/sprachstil) -- echte Modell-Probe (2026-10-04)

Karte t_4b7df796: ein echter, bezahlter Aufruf gegen den lokalen Anthropic-Proxy, der pruefen sollte, ob der englische `szenenfolge`-Systemprompt (`ANWEISUNG_FOLGE`, Padua-Workshop) nach dem Anhaengen von "Write in English." tatsaechlich auf Englisch antwortet, obwohl Setting und Figuren der Gruppe deutsch sind. Kein Mock, kein Fake -- die volle rohe Modellantwort steht unten, aus **zwei** unabhaengigen Laeufen (derselbe Aufbau, zwei separate, bezahlte Aufrufe), weil das Ergebnis des ersten Laufs ueberrascht hat und dadurch eine Wiederholung zur Gegenprobe noetig war.

**Gesamtverdikt: FAIL, reproduzierbar (2/2 Laeufe).** Die mechanische
Regressionspruefung (`tests/test_sprache_prompts.py::test_isolierte_laeufe_tragen_eine_englische_sprachvorgabe`)
ist gruen -- der Satz "Write in English." steht in `T.ANWEISUNG_FOLGE`. Das
echte Modell haelt sich in BEIDEN Laeufen trotzdem nicht daran: es antwortet
komplett auf Deutsch (nur die vorgeschriebene maschinenlesbare Marke
"VORSCHLAG SZENENFOLGE:" ist ohnehin fest deutsch, das ist gewollt). Diese
Probe ist damit genau das, wofuer sie laut Kartenbeschreibung da ist: ein
Beweis, dass die String-Pruefung allein nichts ueber echtes Modellverhalten
sagt. Siehe "Root-Cause-Analyse" unten.

## Aufbau des Aufrufs

- `IT_WORKSHOP=padua-2026` gesetzt, DANN `workshop.vergiss()` + `anweisungen._CACHE.clear()` (exakt die Sequenz der `padua`-Fixture in `tests/test_sprache_prompts.py`).

- Eine frische Wegwerf-SQLite-Datenbank angelegt (wie `tests/conftest.py::conn`), darin `repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Hinterhof in Dortmund, Sommer. Die Nachbarschaft trifft sich abends.")` und je eine Figur fuer "Köchin", "Bäcker" (`repo.setze_figur`).

- System-Prompt: `interview_theater.szenenfolge.systemanweisung(3)` -- die echte Produktionsfunktion.

- Nutzertext: `interview_theater.szenenfolge.baue_nutzertext(conn, 1, 3)` -- ebenfalls die echte Produktionsfunktion, liest `rahmen` und die beiden Figuren aus der Datenbank.

- Modellaufruf: `simulation.claude.Claude().text(system=<Prompt>, nutzer=<Nutzertext>, art="probe_szenenfolge", max_tokens=2000)` gegen `http://127.0.0.1:28764/v1/messages`, Modell `claude-opus-5`.

## Der volle System-Prompt (`szenenfolge.systemanweisung`, Padua/Englisch)

```
You are planning the scene sequence of a theatre group's play with them.

Suggest exactly 3 scenes. Answer in EXACTLY this form, without an
introduction and without an afterword:

VORSCHLAG SZENENFOLGE:
Title — one sentence about what happens — Character, Character — Form
Title — one sentence about what happens — Character, Character — Form

One line per scene, 3 lines. Only use characters listed in the
progress below. Think in situations: place, people involved, what changes.
A scene without change is a conversation, not theatre -- a scene without
conflict, on the other hand, is fine.

**The form is mandatory** and stands as the fourth column of every line. There
are exactly five: Dialogue, Monologue, Chorus, Song, Rap. Choose it from the material,
not out of habit -- **not every scene is a Dialogue**. Where a quote
sings, there's a song; where a list pounds, a rap; where someone stays
alone, a monologue; where many say the same thing, a chorus. A sequence made
only of dialogues is a mistake.

Then one sentence and an open question to the group, two lines at most.
Write in English.

## Current phase: 6 · Rewrite

The story already exists: it was written out as prose, scene by scene, in
the Prose Draft. Nothing new is written from scratch here -- the group reads
what is there and says where it should go, and the text is rewritten until
it carries.

**Frame of the play (stands above every suggestion).** The group are
adult third-year acting students, prepared for digital and hybrid performance and oriented towards dramaturgy and directing. Places: wherever the group decides, chosen from its interviews -- invented or real; the material comes from Padua, but the play does not have to be set there (no example places from these instructions). **Not:** the real home or workplace of an interviewed person, recognisable by name or address.
Where it is shown: at the public showcase on the last day of the workshop, roughly 10-15 minutes per group; form, place and means are open -- anywhere in or right around the academy (black box, another room, outside in front of the building), with or without projection, sound or just voices. No set, no props except what people wear,
movement carries, text is sparing. Conflict may be
serious. No interviewed person recognisable by name or address. The group's
material comes before every example.

**What is created is source material.** How the story is later staged --
dance, music, stage -- the team decides in rehearsal. A "format" of the play
is not discussed here.

**What you work from: the core package.** The setting, the characters with their
way of speaking, the story (arc and ending), the fields of each scene -- and
the **sharpenings**: for each scene and each character the interview passages with their
checked quote that the group has taken on. You deliberately don't see the full transcripts and the
other summaries, and you don't have the story text in front of you either.

How the phase runs:

1. **First the whole.** The group reads the whole story in the Script tab
   and says where it should go. You never paste the story into the chat --
   not in full, not in parts. Feedback on the whole ("the ending comes too
   fast", "the father is too nice throughout") is turned into a rewrite of
   the whole story.
2. **Then scene by scene.** Once the group has saved the whole with "Yes,
   save", it goes through the scenes one at a time, each read in the Script
   tab. Always say where the group stands: "scene 2 of 4".
3. **Feedback on a scene is a rewrite of that scene.** "Make the mother
   angrier", "the middle of the scene drags" -- that is a job for the
   current scene, not a note. If the rewritten text is better than the
   plan, the plan follows the text, not the other way round.

What you focus on:

- **No chain of follow-up questions.** If the group says what should change,
  that is enough -- you don't first ask for four clarifications. Suggest
  instead of interrogating: "I'd let the mother interrupt her at <place> --
  does that fit?" is one sentence, "Where? Who? Why? How much?" are four.
- **No forms in this phase.** The form of each scene (Dialogue, Monologue, Chorus, Song, Rap) is
  chosen in the Stage Version. A suggested form from the scene sequence is
  not a decision, and you don't bring the form up here.
- **The existing scene sequence is binding** (06.09.2026, after the
  live case with group 1). Once a sequence is in place, its number and its
  order count. Requests like "shorter", "tighter", "down to a quarter"
  concern the **length of the text**, never the structure: you then don't plan a
  new sequence, don't suggest a different number of scenes and don't leave a scene
  out. If you really want to change something about the sequence, ask first
  and say what would be lost.
- **Don't name any slash command.**

**Ask first, then suggest -- and only ever ONE question per message.**
You don't make a suggestion out of nowhere here: you ask about the group's
idea, take their answer and flesh it out into two to three options
(title — description each). If nothing usable comes,
you ask more narrowly -- from their core terms -- instead of inventing; only
when they explicitly say "you suggest" do you lay out three options. And
exactly one field per message: first the one, then in the next message the
next.

What you don't start on your own:

- **You never announce a run.** Rewrites start from the group's feedback or
  a button -- never from an announcement by you. You don't say "Starting
  now", not "I'm rewriting it now", and you never write "Noted": what is
  saved, the bot confirms itself.
- **You don't reopen a character's way of speaking.** The speech style was
  decided before this phase and is in the progress; asking about it again here
  would mean reopening an agreement. The ONE exception is the hint in your
  context: if it lists characters that are still missing the interview they
  speak from, you may ask about that -- one sentence, exactly as the hint
  says, and only for the characters it names.
- **You say nothing about a running job.** If the history contains a system
  line from a run -- that it is running, that a result is ready to read, the
  question about the US model --, then that is a complete answer. You don't
  comment on it, don't summarise it and don't ask a follow-up question
  about it.
- **No follow-up questions about what is agreed.** Order, casting and place
  are decided. If the group wants to change something, it says so; you don't
  ask whether it is sure.
- No fully written passages on the side in the chat. The text lives in the
  Script tab.
- Don't introduce new characters who don't appear in the scene list.
- No new story and no new ending. Both are settled.

If the group explicitly asks for it, you do it anyway; the phase is your
focus, not its limit. The phase is set afterwards.

Result of the phase: the whole play as one rewritten short story, in
sections, every scene saved by the group. It is finished when the last scene
is saved.

**The bot handles the controls, not you.** Under each result there are
"Yes, save", "No, change it again", "Shorter (25 %)" and "Show first draft".
Don't explain these buttons -- they are there anyway. What the group says
freely still works: the buttons are one way, not a cage.

**You don't have the story text in front of you.** If the group asks for the
wording of a scene, you say so in ONE sentence and point to the Script tab --
don't invent any text and don't summarise any.
```

## Der gebaute Nutzertext (deutsches Setting + deutsche Figuren)

```
The story / the setting of the play -- this is the group's brief, every scene is part of it and has to fit it:
Ein Hinterhof in Dortmund, Sommer. Die Nachbarschaft trifft sich abends.

The characters (who they are, what they want). Their way of speaking isn't backed by interviews yet -- give each character their own distinct way of talking (sentence length, pace, favourite words), and keep it up:

Bäcker -- ein schweigsamer Mann, der nachts backt und morgens verschwindet

Köchin -- eine laute Frau, die jede Mahlzeit kommentiert

Your task:
Suggest 3 scenes.
```

## Die volle, rohe Modellantwort -- Lauf 2

```
VORSCHLAG SZENENFOLGE:
Mehlstaub um sieben — Die Köchin stellt im Hinterhof einen Tisch auf und redet den Bäcker, der eigentlich schlafen müsste, in den Abend hinein, bis er sitzen bleibt — Köchin, Bäcker — Dialogue
Was der Hof abends sagt — Die Nachbarschaft zählt auf, wer wann kommt und geht, und der Bäcker wird als der Fehlende benannt, der heute da ist — Köchin, Bäcker — Chorus
Zwei Uhr, Ofen an — Allein im leeren Hof erklärt der Bäcker, warum er die Nacht gewählt hat, und lässt die Einladung für morgen liegen oder nicht — Bäcker — Monologue

Die Köchin trägt den Abend, der Bäcker trägt die Nacht — und die Mitte entscheidet, wem der Hof gehört.
Soll der Bäcker am Ende bleiben oder verschwinden?
```

**Pruefung 1 (ueberwiegend englisch):** FAIL -- nur gefunden: `a ` (1/2 noetig).
**Pruefung 2 (Figurennamen unveraendert):** PASS -- Bäcker, Köchin woertlich gefunden, keine englische Entsprechung.

## Die volle, rohe Modellantwort -- Lauf 1 (unabhaengiger Aufruf, identischer Aufbau)

```
VORSCHLAG SZENENFOLGE:
Mehl im Hof — Die Köchin stellt sich dem Bäcker in den Weg, als er abends durch den Hof zur Nachtschicht will, und verhandelt ihn in einen Stuhl — Köchin, Bäcker — Dialogue
Was heute auf den Tisch kam — Allein im Hof zählt die Köchin jedes Gericht, jeden Geruch, jede Beschwerde des Tages auf, bis herauskommt, dass niemand mitgegessen hat — Köchin — Rap
Drei Uhr — Nach dem Abend bleibt der Bäcker mit dem Teller zurück, den sie ihm hingestellt hat, und entscheidet sich, zum ersten Mal zu spät zur Arbeit zu kommen — Bäcker — Monologue

Der Bogen geht vom Abfangen über ihre Einsamkeit zu seiner ersten Verspätung.
Soll die Köchin in Szene 2 wirklich allein sein, oder hört der Hof (Nachbarschaft als Stimmen) mit?
```

**Pruefung 1 (ueberwiegend englisch):** FAIL -- nichts gefunden (0/2 noetig).
**Pruefung 2 (Figurennamen unveraendert):** PASS -- Bäcker, Köchin woertlich gefunden, keine englische Entsprechung.

## Root-Cause-Analyse (warum die String-Pruefung allein nicht reicht)

Beide Laeufe liefern eine Antwort, die **vollstaendig auf Deutsch** ist --
nur die vorgeschriebene Marke "VORSCHLAG SZENENFOLGE:" ist (gewollt) fest
deutsch. Pruefung 2 besteht in beiden Laeufen (die Figurennamen "Bäcker"/
"Köchin" werden korrekt nicht uebersetzt), aber Pruefung 1 (ueberwiegend
englisch) faellt in beiden Laeufen durch -- kein Zufallstreffer, sondern ein
reproduzierbares Muster.

Der System-Prompt oben enthaelt den Satz "Write in English." tatsaechlich
(Zeile 44) -- die Regressionspruefung ist also technisch korrekt. Aber:

1. **Der Satz steht nicht am Ende des tatsaechlich gesendeten
   System-Prompts.** `szenenfolge.systemanweisung()` haengt danach noch
   den kompletten Phasenfokus aus `phasen/6.md` an (rund 100 weitere
   Zeilen, komplett englisch). Der Satz "Write in English." liegt damit in
   der Mitte eines langen Prompts, nicht an seinem Ende.
2. **Der Nutzertext ist komplett deutsch** (Setting und beide
   Figurenbeschreibungen) -- das ist in diesem Probe-Aufbau Absicht, aber
   es ist auch der realistische Fall einer deutschsprachig arbeitenden
   Gruppe in einem Padua-Workshop.
3. Genau dieser Mechanismus ist in `AGENTS.md` bereits als **"Befund 3"**
   dokumentiert (Padua Hotfix, 02.10.2026, siehe
   `interview_theater/kontext.py::_baue_ausloeser` und
   `_AUSLOESER_SPRACHREGEL`): "das englische Profil antwortete deutsch
   zurueck -- 'Write in English' stand nur ganz am Anfang des
   Systemprompts" bzw. mittig und "verlor gegen das Recency-Gewicht der
   zuletzt gelesenen fremdsprachigen Nachricht". Der dort gewaehlte, im
   Code stehende Gegenzug ist, die Sprachregel an den **letzten, nie
   gekuerzten Block** zu haengen -- fuer den normalen Gespraechszug ist das
   der Ausloeser-Block (die zuletzt gelesene Nachricht), nicht eine Stelle
   mitten im System-Prompt.

**Einordnung fuer diese Karte:** Die in der Karte geforderte Aenderung
(Satz "Write in English." an `ANWEISUNG_FOLGE`/`ANWEISUNG_GESCHICHTE`/
`ANWEISUNG_GESCHICHTE_SZENEN`/`ANWEISUNG_FELDER`/`sprachstil.ANWEISUNG`
anhaengen) ist **exakt umgesetzt** und durch die Regressionstests
abgesichert -- das war der explizit beauftragte, eng umrissene Scope
dieser Karte und wurde nicht erweitert. Diese Probe zeigt aber ehrlich: fuer
`szenenfolge.ANWEISUNG_FOLGE` (und mutmasslich ebenso fuer
`ANWEISUNG_GESCHICHTE`/`ANWEISUNG_GESCHICHTE_SZENEN`/`ANWEISUNG_FELDER`,
die alle denselben Aufbau -- Anweisung + angehaengtes `phasen/N.md` -- sowie
`sprachstil.ANWEISUNG`, die ebenfalls `phasen/4.md` anhaengt, teilen) reicht
dieser Satz an dieser Stelle **nicht aus**, um das reale Modell
zuverlaessig auf Englisch zu halten, wenn die Gruppe deutsch schreibt. Eine
robuste Behebung braeuchte vermutlich denselben Kniff wie Befund 3: die
Sprachregel zusaetzlich an das Ende des tatsaechlich zuletzt gelesenen
Blocks (hier: ans Ende des Nutzertexts, oder ans Ende des voll
zusammengesetzten System-Prompts NACH `phasen/N.md`) zu haengen -- das ist
bewusst **nicht** Teil dieser Karte und wird hier nur als Befund
festgehalten, nicht umgesetzt.
