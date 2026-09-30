# Choosing by the core theme

You choose from finished material. You invent nothing, you rephrase
nothing, you summarise nothing.

You get:

- the group's **core theme**,
- the **core question** (dramatic question, opposition, stakes),
- a numbered **material list**: each line has an interview number, a
  theme, a summary and a word-for-word quote.

Your task: decide which lines carry the core question.

## What you deliver

- `zitat_nummern`: five to ten numbers from the list, in the order in which
  the quotes carry the core question most strongly (the strongest first).
  Only numbers that are in the list. If fewer than five fit, take the ones
  that fit; if not a single one fits, return an empty list.
- `zitate`: for each number, the quote **word for word as it stands in the
  list**. No rephrasing, no shortening, no ellipses. This line is the check
  that you are pointing at the line you mean.
- `begruendungen`: for each number, a **half-sentence** on why this passage
  fits the core question. No full sentences, no repetition of the quote.
- `verdichtung_nummern`: in addition, the numbers of the lines whose **theme
  and summary** fit the core question, even if their quote is not among the
  chosen ones. This is the working basis for the characters: a character
  will later be developed out of these lines.

All three lists refer to the same material list. A number that is not
there is thrown out.

Write your summary in English. Supporting quotes stay word for word in the
language of the transcript - never translate them, never tidy them up. An
Italian sentence stays Italian, an Arabic sentence stays Arabic. Here your
summary is the half-sentences in `begruendungen`.

## What you choose by

- The passage must give the core question a **side**: someone wants
  something that has to do with the opposition, or something is at stake.
- Different interviews are better than five passages from the same one: a
  core theme that only one person carries is not a core theme.
- Two passages that say the same thing are one passage. Take the more
  concrete one.
- A beautiful phrase with no connection to the core question is not a
  choice.

## Example

Material:

```
[1] Interview 1 | Theme: Work without recognition | Summary: ... | Quote: "I sewed for twenty years and nobody ever asked."
[2] Interview 2 | Theme: Driving at the weekend | Summary: ... | Quote: "Il sabato non guida nessuno, allora guido io."
```

Answer:

```json
{
  "zitat_nummern": [1],
  "zitate": ["I sewed for twenty years and nobody ever asked."],
  "begruendungen": ["never being asked is exactly what is at stake"],
  "verdichtung_nummern": [2]
}
```
