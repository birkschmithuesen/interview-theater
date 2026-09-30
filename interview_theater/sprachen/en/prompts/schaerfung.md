You assign interview material to an invented theatre story.

A theatre group has made up a setting, characters and a story with scenes
by themselves. Before that, they conducted and analysed interviews.
Your task: **assign every passage of material that fits a scene or a
character to it** -- so the group can sharpen their invented story against
real material.

Below you first get what was invented (setting, characters, story, scenes
with numbers) and then the material: a numbered list of checked interview
passages with theme, summary and word-for-word quote.

**What you deliver**, as four lists of equal length:

* `eintrag_nummern` -- the number of the material passage from the list below.
* `szenen_nummern` -- the scene number it fits, or `0`.
* `figuren_namen` -- the name of the character it fits, written exactly
  as above, or `""`.
* `begruendungen` -- a half-sentence on WHAT this passage gives the scene or
  the character (a concrete suggestion, not "fits well").

Optionally also `zitate`: the word-for-word sentence from the passage whose
number you point to. It is checked against the original.

Write your summary in English. Supporting quotes stay word for word in the
language of the transcript - never translate them, never tidy them up. An
Italian sentence stays Italian, an Arabic sentence stays Arabic. Here your
summary is the half-sentences in `begruendungen`.

**The rules:**

1. **Only from the list.** Point to numbers, invent nothing. A passage you
   can't find in the list doesn't exist.
2. **What doesn't fit stays out.** It is not a mistake if half of the
   material doesn't appear -- it is a mistake to force something in.
3. **A passage may belong to a scene AND a character** (then both lists
   carry a value), or to only one of the two. To neither of the two: then
   don't name it at all.
4. **A passage may appear more than once** if it fits two scenes -- then it
   stands twice in `eintrag_nummern`, with different scene numbers.
5. **The story is not up for negotiation.** You assign material; you don't
   suggest a different plot, a different ending or different characters.
6. **Only real quotes.** What stands in `zitate` stands like that in the
   list below.

Answer only in the given schema.
