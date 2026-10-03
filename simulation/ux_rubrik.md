<!--
Source: /home/birk/.hermes/profiles/birk/skills/creative/participatory-bot-ux/SKILL.md
(Birk's personal Hermes skill, "participatory-bot-ux", v1.0.0). Copied into the
repo on 2026-10-03 for the Padua browser UX simulation (card t_cf84eaad) so the
phase judge (simulation/browser_judge.py) can read it without reaching outside
the repository. If the source skill changes, re-copy it here by hand.
-->

# Participatory bot UX — Birk's design stance

Use for ANY design decision on a bot or web surface that a group uses together
(interview-theater/Padua, CoThinker, future workshop tools): buttons, phase
flow, when the bot speaks, what gets saved, which model, which screen. Core
idea: free over guided, quiet over chatty.

Every rule below is a correction Birk actually made (interview-theater rework,
02.10.2026, plus earlier bot-UX rules). Before proposing a design, run the
draft through the checklist at the end. If a rule seems to conflict with the
task, say so and ask; do not silently pick.

## 1. The group authors, the bot assists

- **Content comes from the participants.** Bot suggestions are the last
  resort, not the opener (Phase 1 terms: „die Begriffe sollen unbedingt von den
  Teilnehmenden kommen“).
- **Numbers and scope are the group's call.** The bot asks, never proposes a
  count (scene count: „muss von der Gruppe festgelegt werden“).
- **Bot proposals are never saved as decisions.** Only what the group said or
  confirmed is saved.
- **Don't decide things before the phase where they matter.** Scene styles
  (rap, dialogue) were removed from the scene-planning phase because they belong
  later. Tell: a field is filled with a guess because "we're asking anyway".

## 2. Free over guided („Fokus, kein Käfig“)

- **Creative work has no fixed order.** One question after another is
  „kontraintuitiv für kreative Arbeit“. Instead: one good introduction (what is
  set here, and why), all topics at once as a field („Fragenkonsortium“, not a
  question list), then free brainstorming with an overview of fixed vs. open.
- **Leave room for the unasked.** Allow unlimited free, self-titled definitions
  next to the fixed fields.
- **Buttons are shortcuts, never obligations.** Buttons make users feel they
  MUST press them, which makes everything „starrer als nötig“. Free text and
  voice must visibly stay possible: input always active, chips labelled as
  shortcuts, chips grey out once someone types.
- **Buttons only for a storable value**, never under an open question; one
  field per message.
- **Navigation is always open.** Back/forward through phases at any time (phase
  bar). Requirements are a one-line yes/no hint, not a lock. Natural
  transitions ("saved", "interviews done") may still advance automatically.
- **Re-entry is consistent.** Jumping back into a phase gives the same entry as
  the first time.

## 3. Save automatically, always undoable

- Decisions the group states are saved **automatically** (no yes/no ceremony),
  shown as one quiet system line (📌 …) with **↶ Rückgängig**.
- **Every save has an undo.** No exceptions.
- Tell the group once where everything is kept (the Arbeitsstand tab).

## 4. Quiet over chatty — the bot's voice is a maximum, not a duty

- **Less is more.** Feedback sections are optional; often one or two are
  enough. No mandatory question per thought: that is „wieder so 'n Zwang“ and
  feels „gekünstelt“. The bot may say nothing (`NICHTS`).
- **But not too thin either.** „Ich höre“ in 2–3 lines was too little.
  Useful is: current topic, what emerged (in the group's words), real links to
  earlier statements, 2–3 offers, at most one question, what is still open.
- **Don't flood the chat.** Running commentary belongs on a separate surface (a
  stage tab like CoThinker's), never in the chat („langer Wurstchat“). In
  listening/brainstorm mode the bot writes NOTHING in the chat, not even a
  pointer line; a new card shows as a quiet marker on the tab („der Bot sollte
  dann gar nicht im Chat antworten, sondern nur im Stage-Fenster“).
- **Echo what was heard.** Every transcribed voice segment appears in the chat
  as the group's own bubble, right after each segment cut: that is the feedback
  that the bot is listening („das Transcript im Chat anzeigen als Feedback ist
  wichtig“). Display only: it does not trigger a bot reply.
- **Name surfaces by function, not by metaphor.** „Stage“ was wrong for the
  bot's commentary tab; Birk suggested discussion helper / CoThinker /
  feedback / dashboard and chose CoThinker.
- **Chat per phase (planned).** The chat should start empty in each phase and
  switch along with the phase bar („der Chat soll pro Phase angezeigt werden
  und mit jeder Phase neu bei 0 anfangen“).
- **No wake word** for a bot that is already listening in a session.
- **Background listening is a mode of its own: record, no feedback.** When the
  recording only serves as context for later phases (Phase 1 term discussion),
  the phone lies in the middle and runs the whole time: no arc buttons, no
  cards, no comments, only pause/stop/resume; one condensation at the very
  end, extracting what later phases need („es gibt überhaupt gar kein
  Feedback. Das ist einfach nur ein Mitschneiden, damit die KI das
  Hintergrundwissen aus der Diskussion hat“, 03.10.2026). Tell: a
  CoThinker-style card or a bot line appears during a pure context recording.
- **Own ideas first, AI second, then compare openly.** In question
  development the group writes its own questions before the bot proposes any;
  both sets are offered side by side for choosing, and the share of AI vs.
  own questions kept is shown to the plenary (A/B comparison, 03.10.2026).

## 5. Economy of model calls (cost and distraction are the same problem)

- **The group marks the arc, not the machine.** In brainstorm mode there is
  no automatic pause detection as a trigger: the listen button is a toggle,
  one press = one thought arc (speak, hand over to the next person), the last
  person switches it off, and THAT stop triggers exactly one CoThinker card
  („somit ist alles bei manueller Kontrolle“, 03.10.2026). No cards while
  listening; a hard time cap may still cut segments technically for upload/STT,
  never as a trigger. Tell: a card appears mid-sentence or nobody knows why
  one appeared now.
- **Don't react to every pause.** Too many cuts lead to too many calls, and
  that „lenkt von der Diskussion ab“. Gate model calls in CODE, one call at a
  time; prefer an explicit group action (see above) over size/interval/pause
  heuristics.
- Measured anchors (CoThinker reference annotations, 3 sessions): a thought is
  ~50 s / ~600 chars (wide spread), a topic arc ~2.5 min / ~1 900 chars,
  speech ~16 chars/s. A ~1 200-char trigger gives about one card per topic arc.
- **Give the model enough context to be useful**: the full current phase plus
  a summary of earlier phases, not a tight window.

## 6. Reuse measured values, don't invent them

- When a sibling system already tuned a value, take that value (VAD pause
  0.8 s → CoThinker's 2.5 s / 90 s cap / 0.5 s min speech). Mark it as set vs.
  measured. Keep thresholds env-configurable so they can be retuned on the day.

## 7. Surfaces and devices

- **One page, several tabs**, not extra pages/URLs („ein Tab auf dieser
  Seite“).
- **Several phones per group.** Each phase may have a suggested phone layout
  (who holds which tab), shown as a small picture at the phase start.
- Web is primary; secondary channels (Telegram) follow where it is cheap and may
  lag.
- **On the phone the web page must feel like an app.** It fits the screen
  exactly, never scrolls sideways, and does not jump when the keyboard opens
  („die website soll sich immer optimal an die handy bildschirmgröße anpassen
  und sich dann wie eine app anfühlen“, 03.10.2026). Build it as an app shell:
  `100dvh` container, header | scrolling content | input, no `position:fixed`
  footer on a scrolling document, viewport `interactive-widget=resizes-content`
  (+ `visualViewport` fallback for iOS), `overflow-x` clipped, inputs ≥16px.
  Tell: page slides up/down on keyboard open, or wobbles left/right.
  Acceptance: mobile emulation, `scrollWidth <= innerWidth` on every tab, input
  stays visible with focus.

## 8. Model choice follows data sensitivity

Sensitive data (interviews, their condensation) → sovereign model (Kimi /
Infomaniak). Performance-heavy, non-sensitive work (brainstorm sparring,
writing) → frontier model (Opus via subscription), **after explicit consent,
asked BEFORE that phase starts**. Detail: `interview-theater-live-ops` §2a'.

## How Birk decides (process)

- Proposal with a recommendation, max 3 options, one question per turn.
- He decides layout on a clickable draft, not on a description.
- He collects feedback over several turns and says himself when it is done.
- New correction from him on UX → add it here as a rule with his quote, not
  only in the code.

## Checklist before proposing a design

1. Does any content or number come from the bot that the group should author?
2. Is there a fixed order or a mandatory step the group can't skip or leave?
3. Does every save have an undo, and is it automatic where the group already
   decided?
4. Can the user ignore every button and just talk or type?
5. How many model calls per minute does this cause, and what gates them?
6. Does the bot speak only when it adds something, and outside the chat if it
   is commentary?
7. Is a value invented where a measured one exists?
8. New page where a tab would do? On a phone: does it fit, no sideways
   scroll, no jump when the keyboard opens?
9. Does sensitive data reach a non-sovereign model, or does any model switch
   happen without consent beforehand?
