# interview-theater

**A chat bot that helps an amateur theatre group turn its own interviews
into a play** — it transcribes, condenses, remembers what the group
decides, and drafts scene text on request. The group always decides; the
bot never writes a scene or makes a choice on its own, and switches phase
by itself only at the end of a fully approved phase 5 or 6 (see below).

The group interviews people in their own community, talks through what a
play could look like, and gets scene drafts and a judged full read-through
back — all from a chat window, on a phone, in or around a rehearsal room.

```
 Group's phones / laptop              One bot process per group
 ┌──────────────────────┐             ┌──────────────────────────────────┐
 │ Telegram group chat   │◄──────────►│ bot.py: long-poll loop            │
 │   -- or --            │             │  ablauf.py: one reply per turn    │
 │ Web chat (web_chat.py)│◄──SSE/poll─►│  erkenner.py: what changed?       │
 │  same phone, no app   │             │  phasen.py: which station?        │
 └──────────────────────┘             │      │                            │
                                       │      ▼                            │
 Interview audio ──never leaves────►  │ stt.py (Whisper, Switzerland)      │
 the group's own recording             │ llm.py (Kimi, Switzerland)         │
                                       │  -- modellwahl.py routes here --   │
                                       │  Phase 4+, with consent:           │
                                       │ szene_claude.py (Opus, USA)        │
                                       │      │                             │
                                       │      ▼  sqlite3, WAL               │
                                       │ one shared file, repo.py-only SQL  │
                                       └──────────────┬─────────────────────┘
                                                       ▼
                                   web.py: dashboard · group page · script ·
                                   rehearsal view -- read-only except the
                                   group's own editable work state
```

**What it does today, in short:** a group works through seven phases —
collecting terms, writing interview questions, running interviews, inventing
a setting/characters/story, sharpening that story against what people
actually said and drafting it scene by scene as prose, rewriting it, and
choosing a stage form for each scene before a final read-through. Every
decision the group states in plain language gets picked up automatically
("Notiert: ...") — no form to fill in, no command required. The same
conversation works over Telegram or a plain web chat page; a read-only
dashboard, an editable group page, a script view and a printable interview
guide sit next to it. What the group invents in phase 4 ("Frame") is
deliberately built **without** the interview material in view, so the
group recognises its own authorship; the material comes back one phase
later and sharpens, never replaces, what was invented. Detail on every one
of these decisions — and the live incidents that led to them — lives in
`AGENTS.md`.

## The seven phases

1. **Terms** — take in and sort the list of terms collected in the plenary
2. **Questions** — develop interview questions from the terms, down to the
   few the group will actually ask
3. **Interviews** — conduct the interviews and get them summarised with
   word-for-word quotes
4. **Frame** — invent setting, characters and story freely, without the
   interview material
5. **Prose Draft** — sharpen the invented story against checked interview
   passages, then get it drafted scene by scene as prose
6. **Rewrite** — the story you drafted in phase 5 is not written again: it
   is checked, and you read it in the Script tab. You approve it as a whole
   first, then scene by scene; anything you say about the text ("make the
   mother angrier") revises it, and "yes, save" in the chat works just like
   the button
7. **Stage Version** — you get one message listing every scene and answer
   with a form per number in a single reply; then each character gets a way
   of speaking you can approve or change; then each scene is carried over
   into its form, one at a time, for you to approve; and once the last one
   is saved, the whole script gets a final play check

The group can jump between phases at any time by saying so; the bot never
switches phases on its own, only asks once when the material would allow
moving on (`phasen.py`). The deliberate exception: in a profile that runs
the scene-by-scene flow, approving the last open scene of phase 5 moves the
group straight into phase 6, and approving the last scene of phase 6 moves
it into phase 7 — you just pressed "save" on the last piece, so there is
nothing left to ask. Every other phase change still waits for the group to
say so.

**Checked before you read it.** In that same flow, no text reaches you
straight from the writing model. Before a scene or the whole story is
shown, a different model — never the one that wrote it — asks a few pointed
questions about it (does the scene turn, does it stay true to the plan,
does the story hold together, does each character sound like themselves).
Whatever those questions find gets revised, at most twice. If a revision
turns out weaker, it is thrown away and the better version stays; if it
loses a word-for-word interview quote, it is thrown away too. Then a last
language pass tidies length and stock phrasing. If no independent checker
is available, or the check itself breaks down, you get the text unchecked,
with a note saying so. You never get the full text
in the chat — you get a short note, at most three lines on what the check
changed, and buttons; the text itself is in the Script tab (Telegram gets a
link). "Show first draft" points you to the version from before the check,
so you can always see what it changed.

## Two channels, one conversation

**Telegram** is the original channel and stays fully supported — a bot
account in a group chat, voice messages transcribed and echoed back
immediately. **The web chat** (`web_chat.py`, `web_vereint.py`) is a plain
browser page under the group's own link, with the same recognizer, the same
buttons, the same phase flow — useful where installing Telegram isn't an
option. Both run through the identical `bot.py` loop; only the channel
object (`telegram.Telegram` vs. `web_kanal.WebKanal`) differs.

The web page has three tabs — **Chat** (the conversation), **Workbench**
(`Arbeitsstand` in the code's German default — the group's editable work
state: setting, characters, story, scenes) and **Script** (`Textbuch`,
read-only, with a rehearsal-friendly print view and a role filter) — plus,
during phase 4 only, a fourth tab, **Stage** (`Bühne`), a live
brainstorming surface. (Labels shown here are the English translation used
by the Padua profile; a workshop running without it sees the German names.)
A separate rehearsal view and a printable interview guide live at their own
links for sharing outside the chat.

## Workshop profiles

Nothing in this repository is tied to one workshop. Everything specific —
language, phase names and keywords, scene forms, framing text, target
group — lives in `workshop/<name>/` and is selected per bot process with
`IT_WORKSHOP=<name>`. Without the variable, a built-in default profile
reproduces exactly what the first workshop (Dortmund, German, September
2026) ran on. `workshop/padua-2026/` is the English-language profile for a
five-day workshop for third-year acting students at the academy of the
National Theatre of the Veneto Region (Teatro Verdi, Padova), starting
5 October 2026 — same phases, same mechanics, its own wording, and (for
now) the only profile running the two-stage phase 5 flow, the check before
every display and the phase 6/7 flow described above
(`[prosa_entwurf]`, `[prueflauf]` and `[ueberarbeitung]`, each
`aktiv = true`); without them, phases 6 and 7 run as they did in Dortmund.
See
`docs/workshop-profil-umbau-2026-09-06.md` for how a profile is built and
proven not to change the default's output.

## Model choice and privacy

Interview audio, transcripts and every condensation always stay on a Swiss
provider (Infomaniak, open models, no training on user data) — the module
that condenses interviews never even has a code path to anything else
(`interview_theater/modellwahl.py`). Starting with phase 4, with the
operator's switch and the group's explicit, once-asked consent
(`gruppe.szene_usa_bestaetigt_am`, asked right as the group enters phase 4),
both the bot's own conversation turns and later the scene and story writing
can run on Claude Opus over a US proxy instead, because the resulting text
is measurably better — the group is told in plain language what that means
before it is ever asked, and until it answers, every turn keeps running on
Kimi. No raw name of an interviewee ever reaches a model or the chat: every
recording is addressed only as "Interview 1", "Interview 2", and so on. In
workshops that opt into it (`datenschutz.pseudonyme` in the profile — on for
Padua, off for the Dortmund default), group members' own first names are
likewise replaced with "Member 1", "Member 2" throughout the conversation.
Characters are invented by the group in phase 4, before the interview
material comes back into view, not copied from a real person. Every quote
attributed to an interview is checked, word for word, against the actual
transcript before it is allowed into a scene or a summary (`zitat.py`) — an
unverifiable quote is dropped, not kept with a warning flag.

## Operating it

One Python process per group (`systemd` user units, never a manual start —
two manual starts of the same bot collide over Telegram's update offset).
A single, separate web process serves every group's pages. Audio,
transcripts and condensations for a group can be deleted completely and
permanently with `scripts/loeschen.py`; there is deliberately no delete
command in the chat itself. Full operating instructions, environment
variables and the (many, individually measured) operational pitfalls are
in `AGENTS.md`.

## Testing

`pytest` runs the whole suite offline, with fakes standing in for the
speech and language models — including a regression corpus of real and
synthetic conversation snippets that pins down what the intent recognizer
must and must not catch (`korpus/`, in German and English). Two further,
explicitly non-automatic tools cost real API calls: `scripts/pruefe_prompts.py`
re-runs that corpus against the live model after a prompt change, and
`scripts/simulation.py` plays a complete, multi-phase workshop against the
real models with invented participants, judged by a separate model that
never wrote the text it's judging. Neither runs in CI; both are documented
in `AGENTS.md`.

---

For the technical reference — module map, every bindingly-settled design
decision and the measured incident behind it, and the known rough edges —
see [AGENTS.md](AGENTS.md).
