# Sprache isolierter Laeufe -- echte Modell-Probe (2026-10-04)

Task 6 der SDD-Reihe "Sprache isolierter Laeufe": ein einziger, echter und bezahlter Aufruf gegen den lokalen Anthropic-Proxy, der beweist, dass der englische `fragen_ki_vorschlag`-Prompt (Padua-Workshop) tatsaechlich auf Englisch antwortet, OHNE die deutschen Begriffe zu uebersetzen. Kein Mock, kein Fake -- die volle rohe Modellantwort steht unten.

**Gesamtverdikt: PASS**

## Aufbau des Aufrufs

- `IT_WORKSHOP=padua-2026` gesetzt, DANN `workshop.vergiss()` + `anweisungen._CACHE.clear()` + `anweisungen.hole("fragen_ki_vorschlag")` (exakt die Sequenz der `padua`-Fixture in `tests/test_sprache_prompts.py`).

- Nutzertext gebaut mit `interview_theater.fragen_ki._nutzertext("Apfel, Arbeit, Liebe", None)` -- die echte, bereits isolierte Produktionsfunktion.

- Modellaufruf: `simulation.claude.Claude().text(system=<Prompt>, nutzer=<Nutzertext>, art="probe_fragen_ki", max_tokens=2000)` gegen `http://127.0.0.1:28764/v1/messages`, Modell `claude-opus-5`.

## Der volle System-Prompt (`fragen_ki_vorschlag`, Padua/Englisch)

```
You develop interview questions for a theatre workshop project -- in the
background, BEFORE the group has written its own questions. You only see the
group's terms and, if there is one, a short digest of an earlier discussion
-- no chat history, no own questions from the group, no working state. You
never get to see what the group has already written themselves: this run is
deliberately isolated, so that a clean A/B comparison between your questions
and the group's own ones is possible at the end. Write your questions as if
the group's own questions didn't exist yet -- because you genuinely don't
know them.

Write exactly THREE open, experience-oriented interview questions for EVERY
term -- "Tell me about the day when ..." instead of "What do you think
about ...". A question that can be answered with yes or no is not one yet.

**The term itself appears in the question.** A question about "home" that
never says "home" is a question about something else. Whoever reads the
question later must understand what it's about without the heading.

**Don't assume an experience the person may never have had.** "When did you
first see Hawaii" assumes she was there or imagined it -- instead ask so
that anyone can answer: "What's the first thing that comes to mind when you
hear Hawaii -- and where does that image come from?"

**Each question stands on its own.** No question may point at another
linguistically (no "and then?", no "in that moment", no "that person") --
each one must be understandable read aloud on its own, as if it were the
first.

If there is a digest of an earlier discussion, use it only as additional
background -- which themes, positions, and tensions already came up --,
never as a template you copy word for word. If there isn't one (the normal
case), write the questions from the terms alone -- that is not a
shortcoming, and you never mention its absence.

Output ONLY the questions, as one block, ordered by term (all three for the
first term first, then the three for the second ...), one question per
line, in the format "Term: Question" -- no heading, no numbering, no comment
before or after, no marker word:

Write in English. Never translate the term itself, even though you answer in
English -- keep it exactly as given, in whichever language it was, so the
later comparison with the group's own questions still matches by term.

Home: Tell me about a place where you felt at home for the first time.
Home: What did you take with you the last time you moved -- and why exactly
that?
Home: When did you last feel like a stranger in a place that was supposed
to be yours?
```

## Der gebaute Nutzertext

```
The group's terms:
- Apfel
- Arbeit
- Liebe
```

## Die volle, rohe Modellantwort

```
Apfel: Tell me about a time you ate an Apfel and still remember exactly where you were sitting.
Apfel: What's the first thing that comes to mind when you hear the word Apfel -- and where does that image come from?
Apfel: Describe the last Apfel that passed through your hands -- where did it come from, and what happened to it?

Arbeit: Tell me about the first Arbeit you were ever paid for -- how did the day go?
Arbeit: Describe a moment when your Arbeit felt completely pointless to you.
Arbeit: When did someone last ask you what your Arbeit is -- and what did you answer?

Liebe: Tell me about a day when someone showed you Liebe without saying a word.
Liebe: What was the first thing you ever learned about Liebe, and who taught it to you?
Liebe: Describe a situation in which the word Liebe felt too big or wrong to you.
```

## Pruefung 1: Antwort ueberwiegend englisch

Gesucht wurden mindestens 2 von ['the', 'you', 'what', 'when', 'your', 'a '] (klein geschrieben, Teilstring-Suche in der klein geschriebenen Antwort).

**PASS** -- gefunden: the, you, what, when, your, a  (6/6 der gesuchten Woerter).

## Pruefung 2: Begriffe unveraendert (nicht uebersetzt)

Jede nicht-leere Zeile wurde am ersten `': '` geteilt; der Teil vor dem Doppelpunkt muss exakt einer von ['Apfel', 'Arbeit', 'Liebe'] sein (Apfel/Arbeit/Liebe, NICHT Apple/Work/Love).

**PASS** -- 3/3 Begriffe unveraendert gefunden: Apfel, Arbeit, Liebe.
