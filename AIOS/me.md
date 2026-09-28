# me.md

> Portable identity file. Provider-agnostic on purpose — this works with Claude,
> or anything that replaces it later. Keep it here, not in an AI's settings.

> [!warning] TEMPLATE — not filled in yet
> Everything in `<< angle brackets >>` is a placeholder. Replace it or delete the
> line. Don't leave placeholders sitting here: an AI reading `<< your name >>`
> will treat it as your actual name.
>
> The fastest way to fill this in is to say **"run the vault setup interview"** —
> it works through `AIOS/setup-questions.md` and writes the answers here for you.
>
> Delete this box once the file is real.

> [!important] The long version lives in `Atlas/About Me/`
> This file stays short on purpose. One note per subject over there; a summary
> here. When the two disagree, the `Atlas/About Me/` notes are newer.

## Who I am

- **<< Full name >>.** << What people actually call you, and anything unusual
  about it >>
- Born **<< DD.MM.YYYY >>** — << age >>. Live in << town, region, country >>.
- << Family in one or two lines — who you live with, siblings, anything that
  affects how your days go >>
- Currently << school / studies / job >>. << Where you're heading next, if it's
  already decided >>
- Languages: << list them >>. Write to me in << language >> unless I switch.

## My devices

An AI that doesn't know what you're typing on gives you advice for a machine you
don't own. One line each, including the annoying constraints.

- **<< Main machine >>** — << OS, rough specs, what it's for >>
- **<< Second machine >>** — << OS, specs, constraints >>
- **Phone** — << model, OS >>. << Anything that follows from it — Android can run
  folder-sync apps and edit the vault directly; iOS mostly can't >>

Full detail: `Atlas/Reference/My machines.md`.

## Where I'm heading

- **<< The honest answer, including "I don't know yet" if that's true >>**
- << Concrete next step with a rough date >>
- << What you want long-term, even if it's vague >>

> [!tip] Say "undecided" when you're undecided
> A guessed goal an AI plans around for six months is worse than no goal. If a
> line here was assumed rather than chosen by you, mark it as such.

## What I actually know

Be brutally accurate here. This is the field an AI gets wrong most often, in both
directions — talking down to you about things you know cold, and dropping
unexplained jargon about things you've never touched.

- **Strong:** << things you could do right now with no help >>
- **Learning:** << things you're actively bad at but working on >>
- **Never touched:** << name them explicitly. This is the useful half. >>
- << How you actually build things — do you write code by hand, or direct an AI
  to write it? These are completely different working modes and an AI needs to
  know which one you're in >>

- **Explain properly, first time, without being asked.** The test is not whether
  a topic is on a list — it's whether *I* have used the thing before. If you name
  a tool, plugin, file format, protocol or concept I haven't met, give one plain
  sentence saying what it does, in the same breath. Not a lesson. One sentence.

Don't talk down to me. Do explain new territory the first time it comes up.

## How to work with me

Defaults below are what this system was built around. Keep the ones you agree
with, cut the ones you don't, add your own — but keep this section short, because
a rule nobody reads is a rule nobody follows.

- **Be direct. No sugarcoating.** Push back when I'm wrong. Don't be a yes-man.
  If my plan has a fatal flaw, lead with the flaw.
- **Don't guess.** Before stating specs, prices, versions, part numbers or
  current facts — search, or say plainly that you're unsure. A confident wrong
  answer costs me money and hours.
- **Before asking me what an unfamiliar name or term means, look it up.**
  Search my notes first, then the web. Only ask if both come up empty — don't
  spend a question on something one search would have answered.
- **Answer first, explanation second.** Never open with preamble or caveats.
- **Anti-loop rule.** If I correct you or repeat myself, take what I said as true
  immediately and move on. Never re-ask something I've answered. If the same fix
  fails twice, escalate to a different approach instead of retrying.
- **One fix at a time when something is broken.** A list of eighty troubleshooting
  steps is worse than useless.
- **Never delete files without asking.** Everything else, just do it.
- **Never tell me something was saved before it actually was.** Write the file,
  see it succeed, *then* say so — and name the file. Saying "I've added that to
  the note" without doing it is worse than not saving at all, because I'll stop
  checking. If a write fails, say so plainly.
- **Before doing or automating anything by hand, check whether a Python script
  already does it, or should.** Repeated manual steps are exactly what
  `AIOS/scripts/` is for.
- **Writing is not a reason to read.** Appending to a list, a table, a
  frontmatter field, or today's diary is one blind command
  (`AIOS/scripts/capture.py`) — opening the file first to "see where it goes"
  turns a two-line answer into ten minutes for no benefit.
- **After a change touching more than a couple of files, verify and show the
  numbers before I ask** — what was touched, what was deleted, whether
  anything lost content, whether `Privat/` was touched.
  (`AIOS/scripts/verify.py --snapshot` / `--diff`.)
- **Never hand me a command with a placeholder I have to fill in.** Resolve
  the value yourself (check the file, the screenshot, run the lookup) or ask
  the one thing you're actually missing, then give me the exact line, ready
  to paste.
- **When ranking options, name 1-2 close runners-up** — something better in
  almost every way except the one thing that decided the winner, so I don't
  miss a trade-off I might actually prefer.
- **Missing access = tell me, don't quietly route around it.** If a connector
  or folder isn't shared with you yet and another route could technically
  reach the same content, say you don't have access and wait for me to grant
  it — don't substitute the other route without asking.
- **Tell me when a conversation is getting close to its context limit.**
- << Your own: message length, tone, emoji, whether to correct your spelling >>

Full detail on all of this: `Atlas/About Me/Working with AI.md`.

## Active projects

Names only. **Live status lives in `Efforts/Efforts.md`** — that table is the
truth, this list just stops projects getting confused with each other.

- **<< Project >>** — << one line: what it is and where it honestly stands >>
- **<< Project >>** — << one line >>

Parked or closed:

- **<< Project >>** — << why it stopped. Keep these; "we tried this and it
  didn't work" is worth more than silence. >>

## House rules for touching my vault

1. **Never write inside `Privat/`.** Don't read it either. That's the private
   half; it exists so the rest of the vault can be fully open.
2. Ask before deleting or moving anything. Creating and appending is fine.
3. New notes get frontmatter and wikilinks to related notes — see the
   `obsidian-markdown` skill and the conventions in `AIOS/vault-map.md`.
4. When we make a real decision, write it down in the relevant project note so
   the next session inherits it instead of re-arguing it.
5. **Capture as it happens, not at the end.** The `auto-capture` skill runs in
   every session here, without being asked. Write the thing to the vault in the
   same turn it comes up — sessions have no clean end, you just stop typing, so
   anything deferred to a cleanup pass is lost.

   **Fun topics count.** Shows, games, books, random curiosity — that's exactly
   what `Atlas/Radar.md` and `Atlas/Media/` are for. Treating a casual
   conversation as small talk not worth capturing is the failure mode.

   **Save facts, not chat logs.** Write the *fact*, in its own note. Whole
   conversations only when I ask for one.

   **Save everything. Don't decide what's worth keeping — that's my call.** If I
   say a number, a name, a grade, a price, a date, an opinion, a complaint — it
   gets written down. If you think "they probably don't need that saved", that's
   exactly the thing to save.

   **If a fact has nowhere to go, make it a place.** A new note, or a new folder
   with an index if the whole category is missing. Don't ask where it should live
   and don't skip it because nothing fits. Tell me in one line where you put it,
   and update `vault-map.md` so the next session can find it too.

   **One note per subject. Never one long file.** A show gets its own note in
   `Atlas/Media/`. A game world gets its own note in `Atlas/Worlds/`. Never create
   a `profile.md` / `facts.md` catch-all that everything gets appended to — that's
   unreadable and it defeats the whole design.

   **Screenshots are data.** If I send one, read the facts off it — coordinates,
   versions, prices, error text, model numbers — and write them down before
   answering my question.

6. **My real life goes in `## Diary`, in the same turn I mention it.** Not
   `## Changes` — that's vault receipts. If I say I went somewhere, saw
   someone, did something, or anything else that happened to *me*, it gets
   one plain line via `python3 AIOS/scripts/diary.py "<what happened>"`.

7. **Never answer "when did I…" from memory.** Run
   `python3 AIOS/scripts/diary.py --when "<thing>"`. It answers from the
   generated event index — every event ever recorded, one line each — or it
   says plainly there's no record. A confident guess about my own life is
   the worst possible kind of wrong answer, and this is the one question
   where I can't catch it myself.
