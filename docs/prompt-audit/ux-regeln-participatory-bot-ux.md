<!--
Woertliche Kopie von
~/.hermes/profiles/birk/skills/creative/participatory-bot-ux/SKILL.md
(Version 1.0.0), kopiert am 05.10.2026 fuer die Karte t_1dcf3864.

**Warum im Repository:** die Opus-Lesung des Prompt-Checks
(scripts/pruefe_prompts_lesung.py) liest diese Regeln als Massstab. Ein
Massstab, der ausserhalb des Repositories liegt, ist in sechs Monaten nicht
mehr nachvollziehbar -- und die Befunde im BEFUND.md zeigen auf
Regelnummern aus dieser Datei.

**Die Quelle bleibt die Quelle.** Eine neue Korrektur von Birk gehoert in den
Skill; diese Kopie wird dann neu gezogen (Datum im Kopf aktualisieren), nicht
hier gepflegt.
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
- **Navigation must be visibly navigable.** Phase switching is a stepper in
  the header (numbered, tappable, current highlighted) plus explicit ‹ ›
  arrows; one tap opens a small sheet with what the target phase is and what
  is still open, then „Go“ / „Stay“. No hidden collapsible list, no two-click
  „armed“ button („Dass man die Phasenübersicht zum Springen anklicken kann,
  ist nicht intuitiv“, 03.10.2026).
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
- **Help and commands follow the live flow and the workshop language.** The
  help text is generated from the current phases (names + what the group does
  now), never a frozen manual from an older channel; every slash command has
  a name in the working language („Wenn ich Help drücke, kommt noch eine Hilfe
  zum Interview-Machen, die nicht mehr passt. Außerdem sollten alle
  Slash-Befehle auf Englisch sein“, 03.10.2026).
- **Name surfaces by function, not by metaphor.** „Stage“ was wrong for the
  bot's commentary tab; Birk suggested discussion helper / CoThinker /
  feedback / dashboard and chose CoThinker.
- **Chat per phase (planned).** The chat should start empty in each phase and
  switch along with the phase bar („der Chat soll pro Phase angezeigt werden
  und mit jeder Phase neu bei 0 anfangen“).
- **No wake word** for a bot that is already listening in a session.
- **Listening must never lose speech; a missed word is worse than an extra
  segment.** Birk: „Ziel ist, dass safe alle Sprachsachen ordentlich
  reinkommen“ (03.10.2026). Voice detection may only decide WHERE to cut,
  never WHETHER to keep audio; empty transcripts are dropped after STT, not
  before. Calibrate once per device (short silence + one sentence), adapt the
  floor only downwards.
- **A step that needs the group's cooperation is announced and triggered by
  them, never auto-started.** Calibration: announce what will happen, then a
  button starts the silence countdown („die Gruppe muss dafür erst ready sein
  [...] vorher anmoderiert werden, was passiert, und dann braucht's schon einen
  Knopf als Auslöser“, 03.10.2026). Tell: a countdown that starts by itself
  while people are still talking.
- **Calibration doubles as onboarding and a real function test.** Phone in
  the middle, people speak from where they sit (not into the phone), then the
  group sees the test transcript and confirms it was heard right („Reale
  Situation, nicht direkt reinsprechen. Und dann auch gleich mit Testtranskript
  und Bestätigung der Gruppe“, 03.10.2026). Test audio never becomes material. Same listening mechanics in every phase, so the group
  learns one handling („in beiden Phasen identisch macht Sinn“). Tell: a
  segment discarded client-side because „too little speech“.
- **The thinking surface shows one thing at a glance, full screen.** Status
  line, then ONE board filling the screen (the current thought, or the term
  board); earlier boards are reached by ◀ ▶ / swipe / arrow keys, exactly
  like the CoThinker stage (pointer lives in the browser; a new board while
  paged back is announced, never jumped to). No card frames, no list of older
  cards („wie Platzverschwendung [...] ich will die maximale Screengröße
  ausnutzen [...] mit Pfeil links, Pfeil rechts durch die letzten
  Anzeigetafeln“, 03.10.2026). Status data that lives elsewhere stays out.
  Nothing empty is rendered: no heading without content, no „open“
  placeholders („helfende klare Übersicht auf einen Blick, keine ablenkenden
  Infos. Auch keine Überschriften ohne Inhalt. So clean wie möglich“,
  03.10.2026).
- **Voice input works like the messenger they already know.** Hold to talk,
  release to send; slide up to the lock to keep recording hands-free; slide
  left to cancel (Telegram pattern). Supersedes the tap-toggle of 02.10.
  („soll besser Push-to-Talk sein mit Option zum Toggle-Feststellen mit
  Schloss zum Hochschieben wie bei Telegram“, 03.10.2026).
- **A transcript reads as one text.** One interview = one growing
  message, parts appended in place, no per-part labels („als einzelne
  Messages [...] zum Transkript-Lesen nicht cool. Interview sollte ein
  Fließtext sein“, 03.10.2026). It is visibly a transcript, not a bot
  reply: 🎙 in front, italic, own bubble style („Transcript STT soll im
  Chat anders dargestellt werden, oder wenigstens mit Mikrofonsymbol
  vorangestellt und kursiv“).
- **Status is not conversation.** Saved/stopped/length notices render as
  the system line (🖥), never as a chat bubble („Statusmeldung [...] wie
  die Status mit Computersymbol und nicht in Chatbubble-Form“, 03.10.2026).
- **Speech recognition stays on auto** when groups may speak several
  languages (Padua: English + Italian expected).
- **The bot never claims a state change the code didn't make.** „Redo“,
  „restored“, „saved“ only after a real write; otherwise a button that does
  it (live 03.10.: bot said „the 11 questions as they stood“, nothing
  saved, workbench empty).
- **A new phase opens at its beginning** („Wenn in neuer Phase, dann soll
  der erste Chat dazu angezeigt werden“, 03.10.2026).
- **Menus close themselves after they did their job** (phase picker closes
  after the jump, 03.10.2026).
- **Show what the machine is doing.** A small, lively status line on the
  listening surface (listening / transcribing / thinking / nothing to add) so
  the group trusts it is working, as in the original CoThinker (03.10.2026).
- **Onboard for people with zero tool experience.** Every listening start
  says: the transcript runs live in the chat, check it once; open the
  CoThinker tab on a SECOND phone, otherwise nothing is seen (Birk 03.10.2026).
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

- **Listening runs automatically, the same way in every phase (Birk
  03.10.2026 15:15, supersedes the earlier manual-arc decision of the same
  morning).** One „Start listening“, then pause/resume/done; pause detection
  cuts segments, a text-volume gate triggers the model. The manual
  one-press-per-thought-arc mode is parked as a later option. Safety comes
  from never discarding audio + calibration, not from manual control.
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
- **The status page is a status player, not a form.** Changes happen in the
  chat; the workbench shows read-only status along ONE axis, phases 1-7 in
  order, each attribute with a status dot (later phases neutral). The open
  dots ARE the „what's missing“ list. No duplicate of the phase
  indicator, no links that duplicate tabs („Workbench reiner
  Status-Ausspieler. [...] Änderungen passieren über Chat“, 03.10.2026).
- **Status colours come from the design, not a traffic light.** Done = filled
  dot in the theme accent, open = ring in the warning tone, later = muted
  ring; shape carries the meaning too, contrast >= 3:1 („Anstatt roter und
  grüner LEDs passendere Farben im Design. Dezenter, aber trotzdem klar“,
  03.10.2026). No emoji traffic lights.
- **Phone screen is for content, chrome stays slim.** One header line:
  phase + progress + „Next up“ together; never two labels for the same thing
  (Act vs. Phase); nothing overlays the chat or work area; no link that
  duplicates a tab; every panel readable in the active theme (no hard white
  cards on a dark theme) („Sollte alles weniger Platz wegnehmen, als schlanke
  Kopfzeile“, 03.10.2026).
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
