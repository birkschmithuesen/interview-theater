"""Sieben erfundene Padua-Gruppen, eine je Phase, in einer Wegwerf-Datenbank.

**Warum mit Volumen** (Birk, 05.10.2026 00:40): ein Prompt-Dump gegen eine
frische Datenbank zeigt keinen der Befunde, die am 06.09.2026 gemessen wurden
(52 k Zeichen Nutzertext, dieselbe Zusammenfassung 11x). Jede Gruppe hier traegt
deshalb >= 34 Zuege mit mehreren Sprechern, Bot-Antworten, Systemzeilen
(📌 / "Noted:" / "Changed since") und einem Transkript-Echo, dazu gefuellten
Arbeitsstand bis zu ihrer Phase, Journal und Festlegungen.

Alles ist **erfunden**. Das Interviewmaterial kommt aus
``simulation/interviews/set1`` (ebenfalls erfunden, gehoert ins Repository);
das Betriebsverzeichnis mit den echten Gruppen wird nie geoeffnet.

Die Zeitstempel sind absichtlich ungleich verteilt: die Haelfte der Zuege liegt
mehr als ``kontext.FENSTER_MINUTEN`` vor dem letzten, damit die weiche
Minutengrenze wirklich greift und ``fensterbefund`` etwas zu messen hat.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from interview_theater import kontext, repo

BASIS = datetime(2026, 10, 5, 8, 0, 0, tzinfo=timezone.utc)
PHASEN = (1, 2, 3, 4, 5, 6, 7)

#: Weit oberhalb jedes Telegram-Bereichs und oberhalb von
#: ``repo.WEB_CHAT_ID_BASIS`` -- eine Fixture-chat_id soll mit keiner echten
#: Gruppe kollidieren, auch nicht in einer Entwicklungs-Datenbank.
CHAT_ID_BASIS = 9_100_000_000_000

INTERVIEW = Path("simulation/interviews/set1/2-ferzan-bahnhof.md")

#: Je Gruppe gleich: Ankunft, Technik, Alltag. 30 Zeilen.
#:
#: Reihenfolge seit P1-L7 (lesung.json 05.10., Fund Kategorie d, Datei
#: ``01-gespraech-phase1``, Zeile 529): das Fenster (``kontext.FENSTER_NACHRICHTEN
#: = 20``) schnitt hier so, dass es mit einer verwaisten Bot-Antwort begann
#: ("In the Workbench...", die Frage davor war schon abgeschnitten), gefolgt
#: von acht Zuegen reinem Rauschen (Handy schlaeft ein, "is anyone writing
#: this down") -- der Pruefer las das faelschlich als Produktbefund zur
#: Fensterbildung. Deshalb liegt das inhaltsfreie Rauschen jetzt GESCHLOSSEN
#: am Anfang (dort, wo das Fenster ohnehin abschneidet) und die informativen
#: InScribe-Saetze stehen am Ende, in sich abgeschlossen -- keine Antwort ohne
#: ihre Frage im selben Fenster (gemessen in ``fensterbefund``/Testfall
#: "test_fenster_beginnt_nicht_mit_verwaistem_rauschen").
#:
#: Runde-2-Befund (c569/b647 und d566/d642, lesung.json 05.10.): die vier
#: InScribe-Erklaersaetze zu Transkript/CoThinker/Sprache/Workshopdauer
#: standen ohne eine einzige Gruppen-Nachricht dazwischen direkt
#: hintereinander -- eine echte Gruppe fragt zwischendurch, sie bekommt nicht
#: vier Bot-Zuege am Stueck. Jetzt hat jede der vier Antworten ihre eigene
#: Frage davor. Dieselbe Lesung fand "In the work status tab..." -- die
#: Fixture erfand den Namen; die Oberflaeche nennt dieselbe Sache ueberall
#: "Workbench" (``sprachen/en/texte.toml``, ``stand = "Workbench"``).
_GRUNDVERLAUF = (
    ("Giulia", "ok we are all here, three phones on the table"),
    ("Marco", "the wifi in this room is terrible btw"),
    ("Giulia", "it works, just slow"),
    ("Chiara", "who is holding the second phone?"),
    ("Marco", "me"),
    ("Chiara", "can we talk in Italian sometimes?"),
    ("Giulia", "good"),
    ("Luca", "sorry i'm late, what did i miss"),
    ("Chiara", "nothing, we just started"),
    ("Marco", "do we have to finish this today?"),
    ("Giulia", "ok let's keep going"),
    ("Chiara", "my phone went to sleep"),
    ("Marco", "mine too, annoying"),
    ("Luca", "is anyone writing this down"),
    ("Chiara", "the bot is"),
    ("Marco", "right"),
    ("Giulia", "ok"),
    ("Chiara", "does the transcript show up somewhere?"),
    ("InScribe", "Good. The transcript runs live in the chat - check it once."),
    ("Marco", "and if i close that tab?"),
    ("InScribe", "Then you see the CoThinker tab. Nothing is lost if you close it."),
    ("Luca", "can it understand italian too?"),
    ("InScribe", "Yes. The recording understands both; I answer in English."),
    ("Giulia", "is today the only day we do this?"),
    ("InScribe", "No. The workshop runs five days; today is the first."),
    ("Luca", "wait, where do i see what we already decided?"),
    ("InScribe", "In the Workbench. Everything saved is there."),
    ("Luca", "ah ok"),
    ("Giulia", "ok can we go on"),
    ("InScribe", "Of course. Go ahead."),
)

#: Je Phase acht Zeilen, die zu ihrer Arbeit gehoeren.
_JE_PHASE = {
    1: (
        ("Giulia", "here is our wall: arrival, waiting, strangers, home, noise, "
                   "trust, belonging, the city at night, family"),
        ("Marco", "we also had 'language' but we weren't sure"),
        ("Chiara", "i think 'waiting' is the strongest one"),
        ("Luca", "waiting is boring on stage though"),
        ("Chiara", "not if you show what people do while waiting"),
        ("InScribe", "Then 'waiting' carries two meanings for you: the empty "
                     "time, and what fills it."),
        ("Giulia", "yes exactly"),
        ("Marco", "can we keep nine terms or is that too many?"),
    ),
    2: (
        ("Giulia", "we wrote our own questions first, here they are"),
        ("Giulia", "1. what do you remember about your first day here / "
                   "2. where did you wait the longest / "
                   "3. when did a place start to feel like yours"),
        ("Luca", "question 2 sounds like a job interview"),
        ("Chiara", "i like it, it's concrete"),
        ("InScribe", "Your three are saved. Do you want to see mine next to them?"),
        ("Marco", "yes show us"),
        ("Luca", "but we decide, right"),
        ("InScribe", "You decide. Mine are only there to compare."),
        # P2-Fixture-Artefakt (Runde 1, lesung.json): dieser Verlauf endete
        # bisher mit der InScribe-Zeile darueber -- ``repo.letzte_nachrichten``
        # (die Grundlage des Ausloesers, den
        # ``erzeuge_prompts_padua_voll._gespraech`` an ``ablauf.antworte``
        # gibt) nahm dann den BOT als Ausloeser, und der Dump zeigte unter
        # "## Now" einen "You: ..."-Zug, als haette der Bot sich selbst
        # angestossen. Eine echte Gruppe loest ihren naechsten Zug immer mit
        # einer eigenen Nachricht aus -- deshalb steht hier jetzt die Antwort
        # der Gruppe auf den Satz davor.
        ("Marco", "ok, show us yours then"),
    ),
    3: (
        ("Giulia", "we are at the station, it's loud"),
        ("Marco", "first interview done, 11 minutes"),
        ("InScribe", "I have it. The summary comes in a moment."),
        ("Chiara", "the man spoke about his broken bag the whole time"),
        ("Luca", "that was the best part honestly"),
        ("Giulia", "can we do one more before lunch"),
        ("Marco", "the opening line worked, people stopped"),
        ("Chiara", "one woman said no, that's fine"),
    ),
    4: (
        ("Giulia", "setting: the railway station, a wet november evening"),
        ("Marco", "three figures: Samir who just arrived, Elena at the cafe, "
                  "Tommaso the late cousin"),
        ("Chiara", "Elena should be annoyed first, not kind"),
        ("Luca", "and the bag opens in the hall, socks everywhere"),
        ("InScribe", "So the story ends with him laughing for the first time here."),
        ("Giulia", "yes"),
        ("Marco", "how many scenes do we need?"),
        ("InScribe", "That is yours to decide. Say a number and I will plan with it."),
    ),
    5: (
        ("Giulia", "ok three scenes: the bench, the cafe, socks on the floor"),
        ("Chiara", "scene 2 needs the loudspeaker line from the interview"),
        ("Marco", "which one"),
        ("Chiara", "the one about not understanding a single word"),
        ("InScribe", "That line is verified against the recording, so it can "
                     "stay verbatim."),
        ("Luca", "good, don't smooth it"),
        ("Giulia", "Elena speaks dry and short, questions instead of statements"),
        ("Marco", "Tommaso talks too fast and apologises twice"),
    ),
    6: (
        ("InScribe", "Here is your story in three sections. Tell me what should "
                     "change."),
        ("Giulia", "we like it. but Elena is too quiet in part 2"),
        ("Luca", "yes she should say something to him, not just watch"),
        ("Giulia", "can she be a bit rude at first? like annoyed"),
        ("Chiara", "and part 3 is too long"),
        ("Marco", "cut it by a quarter"),
        ("InScribe", "I will keep the three sections and their titles and "
                     "shorten inside them."),
        ("Giulia", "ok go"),
    ),
    7: (
        ("Giulia", "scene 1 dialogue, scene 2 dialogue, scene 3 chorus"),
        ("Luca", "chorus for the socks? really"),
        ("Chiara", "yes it's funnier with everyone talking at once"),
        ("InScribe", "Then scene 3 is a chorus. I have the forms for all three."),
        ("Marco", "how does Samir speak on stage?"),
        ("Chiara", "short sentences, he corrects himself, drops into his first "
                   "language"),
        ("Giulia", "Elena dry, Tommaso fast"),
        ("Marco", "when do we see the whole script?"),
    ),
}

#: Phase 3 allein, angehaengt ans Ende ihres Verlaufs: die Gruppe liest das
#: Transkript Satz fuer Satz nach und diskutiert jede Stelle. Nur hier, weil
#: die weiche Minutengrenze gegen die harte Zeichengrenze (§ 6.2 Block 7)
#: gemessen werden soll -- die Gruppe braucht EINE Stelle, an der das
#: Zeichenbudget wirklich sprengt, nicht alle sieben (Testfall "zeichen").
_LANGE_TRANSKRIPTDISKUSSION = (
    ("Marco", "ok before we move on I want to read the whole bag passage back "
              "to everyone slowly, because I think we are skipping past the "
              "one detail that actually carries the scene, which is that he "
              "says he had money, a little, but did not know how to ask -- "
              "that is not about being poor, it is about not having the words "
              "or the nerve, and I think that is a completely different play "
              "than the one about a broken zipper, so let's not lose it under "
              "the socks joke before we have even written anything down"),
    ("Chiara", "right, and the kiosk line matters too -- he says he rehearsed "
               "ordering coffee in his head like a child, practiced the whole "
               "sentence, and then never went up to the counter, he just sat "
               "back down, and I keep thinking about how many times a day "
               "that probably happens to someone in a new country and nobody "
               "ever sees it happen because it looks like nothing, it looks "
               "like a man sitting on a bench doing absolutely nothing at all"),
    ("Luca", "the loudspeaker bit is the one I keep coming back to though, "
             "the part where he says everything was loud and the announcer "
             "talked and he understood not one single word except numbers, "
             "platform numbers, and that the worst part was not the strange "
             "language itself but that everyone else clearly knew where they "
             "were going and he was the one thing in the whole hall that was "
             "standing still while the rest of the world moved through it"),
    ("Giulia", "and then straight after that he goes to the pigeons, which "
               "nobody expected, he says pigeons were inside the station "
               "under the roof and that he found that funny because at home "
               "pigeons stay outside, and here they sit up in the hall making "
               "noise and nobody even looks up, and he says he looked up, he "
               "says he looked up for twenty minutes just because of the "
               "pigeons, which is such a small strange thing to hold onto"),
    ("Marco", "I think the pigeons are the hinge of the whole piece honestly, "
              "because everything before that is him being invisible, being "
              "the one person standing still, not understanding, not asking, "
              "not eating, and then this one moment where he is doing "
              "something nobody else in that station is doing, he is looking "
              "up, he is noticing something they stopped noticing years ago, "
              "and that is the first time in the transcript he sounds proud "
              "of something instead of just surviving the three hours"),
    ("Chiara", "and we should not soften the cousin's entrance either, the "
               "jacket detail, where he says he did not recognise him at "
               "first because he had a different jacket on than in the photo, "
               "a grey one, that is such a small practical detail but it "
               "tells you how long it had actually been since they last saw "
               "each other in person, long enough that a jacket is a strange "
               "new fact about a person you are supposed to already know"),
    ("Luca", "then the bag opens and he laughs, and he says it himself, that "
             "was the first time he laughed here, which is the line we keep "
             "saying we want to end on, and I agree, but I think it only "
             "lands if we have made the waiting heavy enough first, the "
             "coffee he never ordered, the announcements he never understood, "
             "the pigeons nobody else looked at, all of that has to be felt "
             "before the socks on the floor get to be funny instead of sad"),
    ("Giulia", "ok so can we agree the order in the scene plan should follow "
               "roughly what he actually told us, bench first, the kiosk he "
               "never reaches, the noise and the pigeons together since they "
               "are both about the hall itself, then the cousin, then the bag, "
               "and we keep every one of those beats even if we compress the "
               "time on stage, because cutting any one of them flattens him "
               "into just 'the guy who waited', which is not what this was"),
    ("Marco", "agreed, and can we also note down literally now, before we "
              "forget again like last time, that the bench he mentions at the "
              "very end does not exist anymore, they rebuilt that part of the "
              "station with metal seats you cannot lie down on, and he still "
              "checks when he passes through whether it is there, I think "
              "that last beat belongs at the very end of our piece too, not "
              "cut for time, because it is the only moment he talks about now"),
    ("Chiara", "one more thing on the socks, because I do not want us to play "
               "it purely as slapstick -- he says the bag opened naturally, "
               "of course, like it was always going to, and that detail of "
               "resignation mixed with relief is different from a pratfall, "
               "it is closer to something finally being allowed to happen "
               "after three hours of holding it together with his foot"),
    ("Luca", "fine by me, I just do not want three hours of waiting to read "
             "as passive on stage, he is doing something the whole time, he "
             "is rehearsing, he is listening for numbers, he is watching "
             "pigeons, he is holding a bag shut with his foot, that is a "
             "person working extremely hard at looking like he is doing "
             "nothing, and that is the thing an actor can actually play"),
    ("Giulia", "good, let's write all of that down properly before we start "
               "on scene text, because if we lose this level of detail now we "
               "will just reinvent a generic waiting scene later and nobody "
               "will remember why the bench, the kiosk, the pigeons and the "
               "jacket all mattered this much to us this afternoon"),
    ("Marco", "can we also talk about the money line again for a second, "
              "because he says it twice in slightly different ways, first "
              "that he had a little money, then later that it was never "
              "about the money at all, and I think that contradiction is the "
              "actual content of the scene, not a detail we smooth over -- "
              "he is telling us the economic excuse and the real reason in "
              "the same breath, and a stage version that picks only one of "
              "them is already simplifying something he deliberately left "
              "complicated when he told it to us at the station"),
    ("Chiara", "and the apology line from the cousin, the double sorry, bus, "
               "no idea, was egal then -- that whole sentence is three "
               "separate excuses stacked on top of each other without "
               "waiting to see if the first one even landed, which tells you "
               "everything about how that relationship normally runs, he is "
               "used to arriving late and talking fast enough that nobody "
               "gets a chance to actually be angry at him before he has "
               "already moved on to the next thing, and Samir just absorbs it"),
    ("Luca", "I keep thinking about hadi were too, the one phrase he uses in "
             "his own language right there in the middle of an English "
             "sentence, come on then, and how that is the first time in the "
             "whole transcript that anyone speaks to him in a way that does "
             "not require translation, does not require rehearsal, does not "
             "require standing still and listening for a number -- it is the "
             "one line in three hours that just arrives instead of having to "
             "be worked for, and I think the scene should mark that somehow"),
    ("Giulia", "ok, writing all of this down: money contradiction, double "
               "apology, the untranslated line, bench that is gone now, "
               "jacket that is new, pigeons looked at for twenty minutes, "
               "coffee rehearsed and never ordered, platform numbers as the "
               "only words that land -- that is the whole material, and none "
               "of it is decoration, every single one of those is doing "
               "actual work in the story he told us, so none of it gets cut "
               "just because a scene draft runs long on a first pass"),
    ("Marco", "last thing from me: when he says he sat there and was the "
              "only thing that stood still while everyone else clearly knew "
              "where they were going, I think that line does double duty, it "
              "is about the station and it is about the five days we have "
              "left here, because right now we also do not fully know where "
              "we are going with this piece, and maybe that is allowed to be "
              "true on stage too instead of pretending we arrived with a "
              "finished map of the whole story before we even started talking"),
    ("Chiara", "agreed, and I want the socks moment to carry all of this "
               "weight quietly rather than loudly -- not a big slapstick "
               "beat played for a laugh and then forgotten, but the one "
               "physical release after three hours of a body being asked to "
               "hold still, hold a bag shut with a foot, hold a sentence "
               "unsaid at a kiosk counter, hold a whole language unopened -- "
               "when it finally opens it should feel like all of that letting "
               "go at once, and the laugh should feel earned rather than cute"),
    ("Luca", "fine, so: bench, kiosk, platform numbers, pigeons twenty "
             "minutes, jacket, double apology, hadi were, socks -- eight "
             "beats, in that order, nothing added that is not already in "
             "what he told us, nothing cut because it felt slow, and we "
             "build the actual scene text from exactly this list tomorrow "
             "morning before anyone's memory of today's detail starts to "
             "fade into a vaguer, smoother, less true version of what we "
             "actually heard him say while we were sitting right there with him"),
    ("Giulia", "one more pass before we stop: who is actually on stage for "
               "each beat, because the bench and the kiosk are Samir alone, "
               "nobody else needs to be there for either of those, the "
               "pigeons can stay his alone too or we can let Elena notice him "
               "noticing them from across the hall without a word passing "
               "between them, and only the jacket, the apology and the socks "
               "need the cousin physically present, which means the first "
               "half of the scene can run as a near-solo before anyone else "
               "even enters the space, and that shape alone tells the actor "
               "how long he is genuinely by himself before help arrives"),
    ("Marco", "if Elena is watching from across the hall without speaking, "
              "we need to decide now whether she already suspects something "
              "about him or whether she is simply bored behind a counter "
              "that nobody is visiting, because those are two very different "
              "silences to play, one is curiosity building toward the moment "
              "she finally says something to him later, and the other is "
              "just the ordinary tiredness of a job where you wipe the same "
              "spot on a counter because there is nothing else to do with "
              "your hands, and I think we actually want both at once, in "
              "that order, boredom first and then something starts to shift"),
    ("Chiara", "on pacing, I do not want the three hours compressed into "
               "something that reads as five minutes of impatient fidgeting, "
               "I want actual dead air on stage, real unfilled seconds where "
               "the audience starts to feel the waiting rather than just "
               "being told about it, because that is the entire point of the "
               "interview, it was not eventful, it was long and empty and "
               "full of small private rituals, and if we rush through it for "
               "the sake of runtime we have thrown away the one thing that "
               "made this story worth telling in the first place this morning"),
    ("Luca", "agreed on the dead air, but we should anchor it with at least "
             "one visible repeated action so the audience has something to "
             "track across the silence, the foot against the broken bag "
             "feels right for that, we can let him adjust it two or three "
             "times across the scene, small and almost unconscious, so when "
             "the bag finally does open near the end it does not feel random "
             "but like the one thing he was quietly managing the entire time "
             "without ever naming it out loud to anyone, including himself"),
    ("Giulia", "writing that down too: near-solo opening, Elena's silence in "
               "two stages, real dead air anchored by the foot against the "
               "bag, cousin entering only for jacket, apology and socks -- "
               "that is a full staging note on top of the eight content "
               "beats from before, and I think between the two of them we "
               "finally have enough to start drafting actual lines tomorrow "
               "instead of talking about the interview in circles for a "
               "fourth day running without anything written down on a page"),
    ("Marco", "last practical note before we lose the light in this room: "
              "can whoever is closest to a working phone please record this "
              "whole exchange as a voice memo too, not just rely on the "
              "transcript the bot is already keeping, because I want to hear "
              "the order we said things in, not just the content, in case "
              "the sequence we argued our way into matters as much as the "
              "beats themselves once we are actually standing in the room "
              "trying to block this with our bodies instead of with words"),
    ("Chiara", "fine, recording started, and for the record I still think "
               "we are underselling the kiosk moment, a man who rehearses an "
               "entire sentence in his head and then sits back down without "
               "saying it is, to me, the saddest and funniest single image "
               "in the whole interview, and if the play only remembers one "
               "thing from today let it be that one, the sentence that was "
               "ready and never spoken, because that is this entire piece "
               "in miniature, readiness with nowhere yet to go, held in a "
               "body on a bench, which is exactly where we should end tonight"),
    ("Luca", "before we actually stop, I want to go back once more to the "
             "phrase he used about everyone else knowing where they were "
             "going, because I think we have been reading it only as "
             "loneliness, and it is also, underneath that, a kind of quiet "
             "envy, not of any one destination but of the certainty itself, "
             "of having somewhere specific enough in your head that your "
             "body can just walk there without thinking, and he does not "
             "have that yet in this city, not the station, not the kiosk, "
             "not even the cousin's address really, and that absence of a "
             "destination is maybe the actual subject hiding under all the "
             "waiting, more than the waiting itself, which is just its shape"),
    ("Giulia", "that is a good distinction and I think it changes how the "
               "ending should land, because if the subject is not having "
               "anywhere specific to walk to yet, then the laugh at the end "
               "cannot be a destination either, it cannot resolve into "
               "him suddenly knowing where he belongs, it has to stay a "
               "laugh that happens in the middle of still not knowing, on a "
               "bench that will later not even exist anymore, which is "
               "almost crueller and truer at once than any tidy homecoming "
               "beat we were quietly tempted to write for him earlier today"),
    ("Marco", "right, so the last image should not be relief exactly, it "
              "should be that specific kind of laughing that happens when "
              "your body finally gets to do something after holding still "
              "for so long, a release with no destination attached to it, "
              "socks on a wet floor, two men who have not seen each other "
              "in years picking them up while strangers walk past not even "
              "noticing, and underneath all of it the quiet fact that the "
              "bench this happened on is already, even as we talk about it "
              "now today, something that technically no longer exists for "
              "anyone else to go back and check against what he told us"),
    ("Chiara", "ok, I think we are actually done talking for today then, "
               "eight content beats, the staging shape for who enters when, "
               "the note about dead air and the foot against the bag, and "
               "now this last thing about the missing destination sitting "
               "underneath the whole piece instead of just being about "
               "waiting in general, which is a much better, much more "
               "specific thing to hand to an actor than 'play a man who is "
               "waiting', because now Samir has an actual engine for every "
               "single choice he makes across the whole scene tomorrow"),
    ("Giulia", "one very last thing because I do not want to lose it "
               "overnight either -- when he talked about the bench not "
               "existing anymore, he did not sound angry about it, he "
               "sounded almost amused, like the city had quietly agreed "
               "with him that the old version of that waiting should not be "
               "possible for the next person, metal seats you cannot lie "
               "down on, and I think that detail belongs right at the very "
               "end of our piece, after the laugh, after the socks, as the "
               "actual final beat, him today, now, checking a spot that is "
               "gone, which turns the whole thing from a memory into "
               "something closer to a small quiet monument he carries around"),
    ("Marco", "agreed, final beat confirmed then: the bench checked today "
              "and found gone, after everything else, nothing added after "
              "that line, no closing statement, no music cue explained, "
              "just that one fact sitting there at the end for the audience "
              "to carry out of the room with them, the same way he seems to "
              "carry it, lightly, almost amused, not bitter about a place "
              "that stopped existing the way it did when it mattered most "
              "to him, which is the most honest ending this material could "
              "possibly give us without inventing a single word he never "
              "actually said to us this afternoon at that same real station"),
    ("Luca", "and let's write the stage direction for that final beat now "
             "while it is still fresh, not tomorrow: he walks past, slows, "
             "looks at where the bench was, the metal seats catch the light "
             "wrong for sitting, he does not sit, he does not need to "
             "anymore, he just looks for a second longer than a passerby "
             "would, then keeps walking, lights down, nothing spoken, we "
             "trust the audience with that silence the same way the "
             "interview trusted us with three hours of his, and that trust "
             "is exactly the thing we almost lost by rushing to a tidy "
             "ending before we slowed down enough today to actually listen"),
    ("Giulia", "ok, truly last note, because I can see everyone packing up "
               "already and I do not want this to vanish into tomorrow's "
               "rush: whoever writes the first draft of the bench beat "
               "should rewatch how long twenty real minutes of looking up at "
               "pigeons actually feels in a room before deciding how many "
               "seconds of that to put on stage, because our instinct will "
               "be to cut it down to something polite and quick, four or "
               "five seconds that read as 'a little pause', and that is "
               "exactly the instinct we should resist tonight -- the whole "
               "point of today was that he gave twenty real minutes to "
               "something nobody else even noticed was there in that hall, "
               "and a stage version that is only polite about that number "
               "has quietly already started lying about the actual shape of "
               "the thing he told us this afternoon while we sat and listened"),
    ("Marco", "and genuinely truly last from me this time, I promise: "
              "someone should also write down, separately from the scene "
              "notes, the exact words he used for the kiosk, the bench, the "
              "pigeons and the jacket, in his own order, before we start "
              "paraphrasing them into our own language over the next five "
              "days without noticing we are doing it, because every time we "
              "retell a true story to each other it gets a little smoother, "
              "a little more like a story and a little less like the thing "
              "that actually happened to a specific tired man on a specific "
              "wet evening at a specific station that most of the people who "
              "will eventually watch this have also probably stood in once "
              "themselves without ever once thinking about it afterward at "
              "all, which is exactly the thing we are now being asked to fix"),
    ("Chiara", "ok, I will type it all up properly tonight from the "
               "transcript the bot kept, word for word, no paraphrase, and "
               "send it to everyone before breakfast so we all start "
               "tomorrow from the same exact wording instead of five "
               "slightly different memories of what he said, because I "
               "already noticed just now that two of us quoted the "
               "loudspeaker line slightly differently to each other five "
               "minutes apart, and if that drift happens inside one "
               "afternoon between four people who were all sitting right "
               "there listening to the same man at the same bench, it will "
               "absolutely happen again and again across five more days of "
               "rehearsal unless one clean written version exists somewhere "
               "that nobody has to reconstruct from memory under pressure "
               "the night before we actually have to show this to someone"),
    ("Luca", "good, and once that clean version exists, can we also agree "
             "nobody adds a line to his mouth that is not already in it, no "
             "matter how good it sounds in the room tomorrow, because the "
             "whole reason any of this afternoon mattered is that it was "
             "his, specifically, not a type, not a composite of three "
             "interviews we half remember, and the moment we let one "
             "invented line slip in because it scans better than what he "
             "actually said, we have quietly started writing a different, "
             "easier, more generic play instead of the harder, stranger, "
             "more specific one he actually handed us this afternoon at "
             "that station without knowing any of us would still be "
             "talking about his pigeons three hours later back in this room, "
             "and that distinction, between what he actually said and what "
             "we later decided he must have meant, is worth losing a little "
             "sleep over tonight rather than discovering it on stage in "
             "front of an audience five days from now when it is far too "
             "late to go back and ask him which version was actually true"),
)

#: Die drei Systemzeilen, mit genau den Wortlauten, die der Code schreibt
#: (``erkenner._ZEILE_FESTGELEGT`` / ``_TEXT_NOTIERT_ZEILE`` /
#: ``_ANTWORT_UNDO_GEAENDERT``, englische Fassung aus ``sprachen/en/texte.toml``).
#: Sie stehen hier woertlich und nicht per Import: die Fixture soll den Dump
#: nicht von der Sprachschicht abhaengig machen, und der Pruefer muss sie im
#: VERLAUF finden koennen, ohne dass eine Textaenderung ihn blind macht.
#:
#: Die dritte Zeile war bis zum Fund a6 (Prompt-Check Runde 1, lesung.json
#: 05.10.2026) erfunden ("Changed since - please fix it in the work status")
#: -- ein Wortlaut, den das Produkt nie schreibt und den
#: ``kontext._SYSTEMANFAENGE_EN`` deshalb NICHT filterte, sodass er
#: faelschlich als "You: ..."-Zug im Verlauf des Dumps auftauchte. Der echte
#: Wortlaut ist exakt ``_ANTWORT_UNDO_GEAENDERT`` = "Changed since." -- nur
#: dieser wird gefiltert (``_ist_systemzeile``).
_SYSTEMZEILEN = (
    "📌 Agreed: Setting - A railway station in a northern Italian city",
    "Noted:\nterms: arrival, waiting, strangers, noise, belonging",
    "Changed since.",
)

#: ``arbeitsstand.begriffe_detail`` (``roadmap.begriffe_detail``): Begruendung
#: und Doppelbedeutung je Begriff, nicht nur die, die das Board schon zeigt
#: (``kontext._baue_begriffe_detail``) -- "waiting" traegt dieselbe
#: Doppelbedeutung wie im Board-Eintrag (``_diskussion``, dort nicht
#: ausgegeben), "belonging" steht gar nicht auf dem Board und braucht hier
#: seine einzige Begruendung.
_BEGRIFFE_DETAIL_PHASE1 = json.dumps([
    {"begriff": "waiting", "begruendung": "everybody waited for something",
     "doppelbedeutung": "empty time and what fills it"},
    {"begriff": "belonging", "begruendung": "you can wait and still belong",
     "doppelbedeutung": ""},
], ensure_ascii=False)

#: Die Arbeitsstandfelder je Phase, additiv: Phase N bekommt alles von 1..N.
_STAND_JE_PHASE = {
    1: (("begriffe", "arrival, waiting, strangers, noise, belonging, home, "
                     "trust, family, the city at night"),
        ("begriffe_detail", _BEGRIFFE_DETAIL_PHASE1)),
    2: (("fragen", "1. What do you remember about your first day here?\n"
                   "2. Where did you wait the longest in your life?\n"
                   "3. When did a strange place start to feel like yours?"),
        ("interview_eroeffnung",
         "Hi, we are acting students from the academy. Do you have ten minutes "
         "for three questions?"),
        ("interview_abschluss",
         "Thank you. Your answers stay anonymous and become material for a "
         "fictional play.")),
    3: (),
    4: (("rahmen", "A railway station in a northern Italian city, one wet "
                   "November evening. A young man has just arrived and waits "
                   "for a cousin who does not come."),
        ("geschichte",
         "Samir waits on a bench with two bags, one of them broken. He "
         "rehearses how to order a coffee and never goes. The woman at the "
         "station cafe notices him. When his cousin finally arrives, the broken "
         "bag opens in the middle of the hall - and for the first time Samir "
         "laughs here.")),
    5: (),
    6: (),
    7: (),
}

_FIGUREN = (
    ("Samir", "just arrived, wants to arrive without asking anyone",
     "Short sentences, corrects himself, drops into his first language."),
    ("Elena", "runs the station cafe, sees everyone and says little",
     "Dry, practical, questions instead of statements."),
    ("Tommaso", "the cousin, late, embarrassed, overly cheerful",
     "Talks fast, apologises twice, jokes to cover it."),
)

_SZENEN = (
    (1, "The bench", "Samir waits and rehearses his order.", ("Samir",),
     "The hall smelled of wet coats. Samir held the broken bag shut with his "
     "foot and counted the trains he did not understand."),
    (2, "The cafe", "Elena watches him not coming in.", ("Samir", "Elena"),
     "Elena had wiped the same spot on the counter three times. The boy on the "
     "bench had looked at her menu for an hour."),
    (3, "Socks on the floor", "Tommaso arrives, the bag opens.",
     ("Samir", "Tommaso", "Elena"),
     "Tommaso came in running, said sorry twice and took the wrong bag. It "
     "opened. Socks everywhere. Samir laughed before he could stop himself."),
)

#: (bereich, bezug, text) -- ``repo.schreibe_festlegung`` nimmt die drei in
#: der Reihenfolge (bereich, text, bezug); siehe ``baue()`` unten.
_FESTLEGUNGEN = (
    ("form", None, "One episode, the first of a series - not a closed play."),
    ("stil", None, "At most one page per scene from now on."),
)

#: Journal-Eintraege je Stufe, additiv wie ``_STAND_JE_PHASE``: Phase N
#: bekommt alles von 1..N. Seit P1-L7 (lesung.json, Fund Kategorie d,
#: ``01-gespraech-phase1`` Zeile 524): die Geschichte/Szenen-Eintraege
#: standen bisher auch in Phase 1 im Journal, wo sie dem Arbeitsstand
#: widersprechen und mit mehr Gewicht als die Begriffsliste erscheinen --
#: sie stehen jetzt erst, sobald die Geschichte tatsaechlich im Arbeitsstand
#: steht (ab Phase 6, siehe ``_JE_PHASE[6]``: "Here is your story in three
#: sections"). Phase 1 bekommt einen eigenen, phasengerechten Eintrag, der
#: zum dortigen Gespraech passt (siehe ``_JE_PHASE[1]``: "waiting carries
#: two meanings").
_JOURNAL_JE_PHASE = {
    1: (("entschieden",
         "Term 'waiting' carries two meanings: the empty time, and what "
         "fills it.", "journal"),),
    6: (("entschieden", "Story as short story: 3 sections", "szene"),
        ("vorgeschlagen",
         "A fourth scene on the platform - not decided", "journal")),
}


def chat_id_fuer(phase: int) -> int:
    return CHAT_ID_BASIS + phase


def _iso(minuten: float) -> str:
    return (BASIS + timedelta(minutes=minuten)).isoformat(timespec="seconds")


#: Minutenschritt des weit auseinanderliegenden Teils in ``_zeitpunkte``.
#: Gemessen (nicht geraten) gegen die tatsaechliche Zeilenzahl dieser Fixture:
#: mit 5 oder 10 Minuten liegt die aelteste der letzten zwanzig Nachrichten
#: noch keine 30 Minuten vor der juengsten, und ``kontext.FENSTER_MINUTEN``
#: schneidet nie. Erst ab 25 liegt dieser Abstand zuverlaessig darueber
#: (siehe ``fensterbefund`` / Testfall "minuten").
_ZEITSCHRITT_MINUTEN = 25.0

#: Groesse des dichten (0.5-Minuten-Schritt) Teils am Ende -- knapp unter
#: ``kontext.FENSTER_NACHRICHTEN`` (20), nicht die halbe Zeilenzahl: R3-5
#: (feedbackloop-p12-2026-10-05.md, Runde 3) fuegte der Fixture zusaetzliche
#: Zuege hinzu (vier Fragen vor den vier InScribe-Antworten, damit die
#: Historie nicht mit vier Bot-Zuegen in Folge beginnt) und ein Split auf
#: Zeilenhaelfte haette dann fuer JEDE Gruppe mehr als zwanzig dichte Zuege
#: am Ende ergeben -- die letzten zwanzig Nachrichten laegen dann alle unter
#: 10 Minuten auseinander und ``minuten`` als Fenstergrund waere fuer KEINE
#: Gruppe mehr erreichbar. Mit einer festen Groesse hier bleibt mindestens
#: ein weit auseinanderliegender Zug unter den letzten zwanzig, unabhaengig
#: davon, wie viele Zuege insgesamt dazukommen.
_HINTEN_ANZAHL = 19


def _zeitpunkte(anzahl: int) -> list[float]:
    """Minutenversaetze fuer ``anzahl`` Zuege -- vorne weit, hinten dicht.

    Der vordere Teil liegt in ``_ZEITSCHRITT_MINUTEN``-Schritten (deutlich
    mehr als ``kontext.FENSTER_MINUTEN`` vor dem Ende), der hintere (hoechstens
    ``_HINTEN_ANZAHL`` Zuege) in halben Minuten. Damit greift die weiche
    Minutengrenze, ohne dass das Fenster leer wird (``FENSTER_MIN_NACHRICHTEN``)."""
    hinten_anzahl = min(_HINTEN_ANZAHL, anzahl)
    vorne_anzahl = anzahl - hinten_anzahl
    vorne = [i * _ZEITSCHRITT_MINUTEN for i in range(vorne_anzahl)]
    start = vorne[-1] + _ZEITSCHRITT_MINUTEN if vorne else 0.0
    hinten = [start + i * 0.5 for i in range(hinten_anzahl)]
    return vorne + hinten


def _verlauf(conn, chat_id: int, phase: int) -> None:
    zeilen = list(_GRUNDVERLAUF) + list(_JE_PHASE[phase])
    # Die drei Systemzeilen dazwischen, als Bot-Zeilen (typ='text') -- genau
    # so, wie ``repo.merke_bot_zeile`` sie im Betrieb ablegt.
    for i, text in enumerate(_SYSTEMZEILEN):
        zeilen.insert(8 + i * 7, ("InScribe", text))
    if phase == 3:
        # Nur hier: die Zeichengrenze soll an EINER Stelle wirklich
        # schneiden, nicht an allen sieben (Testfall "zeichen").
        zeilen += list(_LANGE_TRANSKRIPTDISKUSSION)
    versaetze = _zeitpunkte(len(zeilen))
    for i, ((absender, text), versatz) in enumerate(zip(zeilen, versaetze)):
        repo.merke_nachricht(
            conn, chat_id, 1000 + i, absender, int(absender == "InScribe"),
            "text", text, _iso(versatz),
        )
    # Das Transkript-Echo: typ='transkript', faellt aus allen drei Fenstern
    # (repo.TYP_TRANSKRIPT) und muss trotzdem in der Datenbank stehen -- der
    # Pruefer prueft, dass es NICHT im Verlaufsblock auftaucht.
    repo.merke_nachricht(
        conn, chat_id, 1000 + len(zeilen), "InScribe", 1, repo.TYP_TRANSKRIPT,
        "🎙 Interview 1\n\nthree hours on that bench and nothing to eat",
        _iso(versaetze[-1] + 0.25),
    )


def _material(conn, chat_id: int) -> int:
    """Ein verdichtetes Interview aus dem erfundenen Simulationsmaterial."""
    roh = INTERVIEW.read_text(encoding="utf-8")
    transkript = roh.split("---", 2)[2].strip()
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, 5, "lang", "text", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, transkript)
    zitate = (
        "Ich habe drei Stunden auf dieser Bank gesessen und nichts gegessen.",
        "Der Lautsprecher hat geredet und ich habe kein einziges Wort verstanden.",
    )
    # Harte Zusicherung: ein unbelegtes Zitat waere im Dump ein erfundenes
    # Zitat -- genau das, was ``zitat.pruefe`` ueberall verhindert.
    assert all(z in transkript for z in zitate), "Interviewmaterial passt nicht"
    repo.speichere_verdichtung(
        conn, chat_id, aufnahme_id,
        "The interviewee remembers his first day: three hours on a station "
        "bench with a broken bag, waiting for a cousin, too unsure to buy "
        "food, unable to understand the announcements.",
        [
            {"thema": "waiting", "beleg_zitat": zitate[0], "zitat_geprueft": 1,
             "kurz": "three hours on the bench"},
            {"thema": "noise", "beleg_zitat": zitate[1], "zitat_geprueft": 1,
             "kurz": "the loudspeaker"},
        ],
    )
    return aufnahme_id


def _diskussion(conn, chat_id: int) -> None:
    """Drei Hintergrund-Segmente plus ein Begriffsboard.

    Gerufen fuer JEDE Phase (``baue``), nicht nur Phase 1: eine Gruppe, die
    Phase 2 oder spaeter erreicht hat, hat die Diskussion und das Board aus
    Phase 1 bereits hinter sich, und ``kontext._baue_board``/
    ``_baue_begriffe_detail`` lesen datengetrieben in jeder Phase (Birk,
    05.10.2026: "Der Chat muss immer alles wissen"). Bisher legte die Fixture
    das nur fuer Phase 1 an, wodurch der Pruefer in Phase 2 faelschlich
    "Board-Block fehlt" meldete (lesung.json, 05.10.2026)."""
    texte = (
        "we keep coming back to waiting. everybody waited for something",
        "and noise. the station is never quiet, you cannot think",
        "belonging is the hard one. you can wait and still belong",
    )
    letzte = 0
    for i, text in enumerate(texte):
        aufnahme_id = repo.lege_aufnahme_an(
            conn, chat_id, 200 + i, "kurz", "web", status="fertig",
            diskussion=True)
        repo.setze_transkript(conn, aufnahme_id, text)
        letzte = aufnahme_id
    board = [
        # Begruendung seit P1-L7 (lesung.json: Kategorie b, "No begruendung
        # that only says the term was named, collected or suggested" --
        # "the group returns to it twice" war genau so eine blosse
        # Erwaehnung, kein Grund) auf den Grund der Gruppe selbst gestellt,
        # woertlich aus ``texte[0]``.
        {"begriff": "waiting", "nennungen": 4, "zitat": texte[0],
         "begruendung": "everybody waited for something",
         "doppelbedeutung": "empty time and what fills it"},
        {"begriff": "noise", "nennungen": 2, "zitat": texte[1],
         "begruendung": "named as the thing that blocks thinking",
         "doppelbedeutung": ""},
    ]
    repo.lege_begriffsboard_an(
        conn, chat_id, json.dumps(board, ensure_ascii=False), "claude", letzte)


def baue(conn, phase: int) -> int:
    chat_id = chat_id_fuer(phase)
    repo.sichere_gruppe(conn, chat_id, "padua1", f"Padua group phase {phase}")
    for stufe in range(1, phase + 1):
        for feld, wert in _STAND_JE_PHASE.get(stufe, ()):
            repo.setze_arbeitsstand(conn, chat_id, feld, wert)
    if phase >= 4:
        repo.setze_arbeitsstand(conn, chat_id, "figuren_fixiert_am", _iso(0))
    repo.setze_phase(conn, chat_id, phase)

    if phase >= 3:
        _material(conn, chat_id)
    _diskussion(conn, chat_id)

    if phase >= 4:
        figuren = {}
        for name, beschreibung, stil in _FIGUREN:
            repo.setze_figur(conn, chat_id, name, beschreibung)
            figur_id = repo.hole_figur(conn, chat_id, name)["id"]
            repo.setze_figur_sprachstil(conn, figur_id, stil)
            figuren[name] = figur_id
        for nummer, titel, kurz, besetzung, prosa in _SZENEN:
            szene_id = repo.lege_szene_an(conn, chat_id, nummer, titel, kurz, None)
            # Ab Phase 5 steht Prosa, ab Phase 7 dazu ein Buehnentext --
            # ``phasen.voraussetzungen`` verlangt in 7 Prosa fuer JEDE Szene.
            if phase >= 5:
                repo.aktualisiere_szene(conn, szene_id, titel, kurz, None, prosa=prosa)
            if phase >= 7:
                repo.aktualisiere_szene(
                    conn, szene_id, titel, kurz,
                    f"SAMIR: {prosa.split('.')[0]}.\nELENA: And?",
                    prosa=prosa,
                )
                repo.setze_szenenfeld(conn, szene_id, "form", "dialog")
            repo.setze_szenenfeld(conn, szene_id, "ort", "the railway station")
            repo.setze_szenenfeld(conn, szene_id, "zeit", "a wet November evening")
            repo.setze_szenenfeld(conn, szene_id, "anlass", "an arrival nobody meets")
            repo.setze_szenenfeld(conn, szene_id, "was_passiert", kurz)
            repo.setze_szene_figuren(
                conn, chat_id, szene_id, [figuren[n] for n in besetzung])

    for bereich, bezug, text in _FESTLEGUNGEN:
        # Signatur ist (conn, chat_id, bereich, text, bezug=None, quelle=...)
        # -- NICHT (bereich, bezug, text); verifiziert gegen repo.py.
        repo.schreibe_festlegung(conn, chat_id, bereich, text, bezug)
    for stufe in range(1, phase + 1):
        for art, text, quelle in _JOURNAL_JE_PHASE.get(stufe, ()):
            repo.schreibe_journal(conn, chat_id, art, text, quelle=quelle)
    _verlauf(conn, chat_id, phase)
    return chat_id


def baue_alle(conn) -> dict[int, int]:
    return {phase: baue(conn, phase) for phase in PHASEN}


def fensterbefund(conn, chat_id: int) -> dict:
    """Was ``kontext.waehle_fenster`` an dieser Gruppe wirklich abschneidet.

    Der ``grund`` ist die Regel, die zuerst gegriffen hat -- in der Reihenfolge,
    in der ``waehle_fenster`` sie anwendet: Anzahl, dann Zeichen, dann die
    weiche Minutengrenze. Er geht in den BEFUND, damit die Fenstergrenzen
    gemessen und nicht angenommen sind (Birk 00:40)."""
    alle = [
        dict(zeile) for zeile in conn.execute(
            "SELECT * FROM nachricht WHERE chat_id=? AND typ='text' "
            "ORDER BY gesendet_am, message_id", (chat_id,),
        )
    ]
    grenzen = kontext.fenster_grenzen()
    fenster = kontext.waehle_fenster(alle)
    zeichen = sum(len(kontext.sprecherzeile(n)) + 1 for n in fenster)
    if not alle:
        grund = "keine"
    elif len(fenster) == len(alle):
        grund = "keine"
    elif len(alle) > grenzen["nachrichten"] and len(fenster) == grenzen["nachrichten"]:
        grund = "nachrichten"
    elif zeichen > grenzen["zeichen"] - kontext._FENSTER_POOL:
        grund = "zeichen"
    else:
        grund = "minuten"
    return {
        "nachrichten_gesamt": len(alle),
        "im_fenster": len(fenster),
        "zeichen_im_fenster": zeichen,
        "grund": grund,
        # Seit P1-L7: das erste Fensterglied woertlich, damit ein Test
        # messen kann, dass es kein verwaister Satz ohne seine Frage ist
        # (lesung.json, Fund Kategorie d, "01-gespraech-phase1" Zeile 529).
        "erste_zeile_text": fenster[0]["text"] if fenster else "",
    }
