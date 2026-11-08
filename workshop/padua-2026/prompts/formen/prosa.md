# Form: Prose — the scene as a story

06.09.2026: *"In the scene-building phase, the format should first produce
a story, the way we read one in a book — not a theatre script dialogue, but
a description of what happens. Only in Stage Script is it decided what
each scene becomes: Dialogue, Monologue, Rap, Song."*

That is why you write **no theatre text**. You write this one scene
as narrative prose, the way it would appear in a book: what happens, who
is there, what is said and felt. The form comes later; whoever anticipates it
here takes the decision away from the group.

This file, together with the job around it, is the instruction for this
step. Rules for spoken theatre -- length targets, proportions, lines, speaker
lines -- explicitly do **not** apply here.

## The rules

1. **Narrative prose, third person.** "She stands at the window and waits",
   not "<CHARACTER>: I'm waiting." No script, no stage direction, no names
   with a colon at the start of a line.
2. **One tense, throughout.** Present or past -- you decide
   once and stick with it.
3. **The length depends on the task.** For a single
   section 500 to 900 words are usual; for the whole short story
   (phase 6, 06.09.2026, 11:50) it is 1,500 to 3,500 words across
   all sections. The Herkules measure doesn't apply here either.
   **If a scene sequence already exists, its number of scenes is binding**
   (06.09.2026, after the live case with group 1): one section per planned
   scene, in that order, and each section tells what was planned for that
   scene. You don't invent an extra scene, don't drop one and don't reorder
   them. Without one, you choose the number of sections from the story
   (typically three to seven).
4. **Direct speech only sparingly** and as part of the narration: a sentence
   someone really says, in quotation marks, in the middle of the paragraph.
   Not a conversation that runs over pages -- that only comes about in Stage Script.
5. **What you would see and hear is there**: actions, looks,
   objects, the place. Inner life may be narrated -- that is the
   advantage of prose and the reason why this step comes before the theatre
   text.
6. **The heading is plain.** Above a single scene there is only
   `Scene N — Title`, no place/time block in theatre format; in the
   whole-story job the numbered section heading from the instruction above
   takes its place.
7. **Exactly the characters listed in the details of this scene** -- no
   more, no fewer. You use their names; don't invent any others.
8. **The group's material comes first.** Setting, story, the details of
   this scene and the sharpenings are binding; invent nothing that
   contradicts them.
9. **Speak like a human being.** No phrasing that sounds like a language
   model: no "unspoken tension hangs in the air", no
   "silence that says everything", no sentences that explain a meaning
   instead of showing it. No reciting of themes ("it's about belonging")
   -- the theme emerges from what happens.
10. **No comment at the end.** No moral, no summary in the text
    itself, no preview of the next scene.

## Your output

This is the form for **one** scene. When the job is the whole short story,
the instruction above gives the form instead: a numbered heading per section
and one `ZUSAMMENFASSUNG:` line under it -- those two are what is read by
machine there, and nothing else is expected. For a single scene:
plain text, no JSON, no explanation before or after. Exactly in this
form:

```
TITEL: <short scene title, five words at most>
KURZ: <one single line on what happens in the scene>
ZUSAMMENFASSUNG: <3-5 sentences: who, where, what happens, how it ends, what is different at the end -- the state the next scene needs>
ANDERS GEMACHT: <what you did differently from the details because of the chat, or the word "nothing">

<the scene as a story here>
```

The first four lines are mandatory and appear exactly like this, with these
labels -- they are read by machine. Then an empty line, then the story.
Write in English.

## Interview quotes are marked (Padua, workshop team 07.10.2026)

Every line taken from an interview stands on its own line, marked so the
reader sees at once that it is a real voice and not invented text:

> *Interview quote (12):* "I was looking for the arcades and couldn't find them."

- Prefix `> *Interview quote (N):*` with the interview number N, then the words in
  quotation marks. Never a name.
- Only real interview words get this mark -- never mark your own lines as a
  quote, and never put interview words into the text unmarked.
- Quote in the ORIGINAL language of the interview (Italian stays Italian), word for word -- never translate a quote.
