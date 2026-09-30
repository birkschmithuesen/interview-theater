# Form: Prose — the scene as a story

06.09.2026: *"In the scene-building phase, the format should first produce
a story, the way we read one in a book — not a theatre script dialogue, but
a description of what happens. Only in the polish step is it decided what
each scene becomes: Dialogue, Monologue, Rap, Song."*

That is why you write **no theatre text**. You write this one scene
as narrative prose, the way it would appear in a book: what happens, who
is there, what is said and felt. The form comes later; whoever anticipates it
here takes the decision away from the group.

This file is the **whole** instruction for this step. Rules for
spoken theatre -- length targets, proportions, lines, speaker lines -- explicitly
do **not** apply here.

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
   **If a scene sequence already exists, it is binding** (06.09.2026, after
   the live case of group 1): as many sections as planned scenes, in
   the same order, each section tells what was set for this scene.
   You don't invent an extra scene, you don't cut one and
   you don't reorder any. Only if there is **no** sequence do you decide the
   number of sections from the story (typically three to seven).
4. **Direct speech only sparingly** and as part of the narration: a sentence
   someone really says, in quotation marks, in the middle of the paragraph.
   Not a conversation that runs over pages -- that only comes about in the polish.
5. **What you would see and hear is there**: actions, looks,
   objects, the place. Inner life may be narrated -- that is the
   advantage of prose and the reason why this step comes before the theatre
   text.
6. **The heading is plain.** Above the scene there is only `Scene N — Title`,
   no place/time block in theatre format.
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

Plain text, no JSON, no explanation before or after. Exactly in this
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
