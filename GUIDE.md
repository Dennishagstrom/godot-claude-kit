# Working with Claude Code on your game

TL;DR: play, write what you saw as a numbered list, hand it to `/godot-round`, test by
hand, `/clear`, repeat. Ask for many things at once rather than one at a time, start
fresh sessions instead of endless ones, and say when you're leaving. The kit does the
rest. Read this once; it takes ten minutes and saves you days and a lot of usage.

Sections: 1 The loop · 2 Writing tasks · 3 What costs usage · 4 While it works ·
5 When something goes wrong · 6 Cheat sheet

The numbers here come from a real co-op game built almost entirely by Claude Code. The
why behind each piece of the kit is in [STRATEGY.md](STRATEGY.md).

## 1. The loop

```
/godot-start  →  play  →  numbered list  →  /godot-round  →  play what changed  →  /clear  →  play ...
```

1. **Start once** with `/godot-start` (new project) or `/godot-analyse` (existing one).
   The interview is worth doing properly: agents build what `docs/design.md` says, and a
   vague idea gets you a different game from every agent.
2. **Play** the game for 15–30 minutes, with friends if it's multiplayer. Write down
   everything that felt wrong, broken or missing. Don't fix as you go.
3. **Hand over the whole list** in one message: `/godot-round` followed by the list.
   Claude plans it (which tasks can run side by side), tells you how long it will take,
   runs up to three agents at once, reviews every branch, merges, and runs all tests.
4. **Play what changed.** The final report lists what to check by hand (feel, looks).
   Tests catch broken code; only you can tell whether it's fun.
5. **`/clear`** and start the next loop. The round doc in `docs/rounds/` holds
   everything the next session needs.

One small fix ("make the jump a bit higher") doesn't need a round: just ask.

## 2. Writing tasks

The agent knows only what you write and what the docs say. Two lines of detail save it a
long search.

| Weak | Strong |
|---|---|
| "combat is buggy" | "3. Arrows pass through enemies when they stand close to a wall. Every time, both classes." |
| "map is bad" | "7. The map doesn't help: I can't see where I've been or where the exit is." |
| "fix the lag" | "2. As the client, my character slides after I let go of A/D. Fine on the host." |

- **What you saw, what you expected, where, how often.** "Host or client?" matters a
  lot in multiplayer.
- **Number the points.** You can then say "take 1, 3 and 5", and every commit and
  report points back to your number.
- **Say what you don't want** ("don't change the art style", "no new menus").
- **Decide or delegate.** Some points are design questions. Claude asks them all at
  once with a recommendation. Answer them, or say "your call".
- **Screenshots:** drag them into the terminal, or give the path.

## 3. What costs usage

Usage limits are the real budget. These habits made the biggest difference, measured:

| Habit | Why it costs | Do instead |
|---|---|---|
| One endless session | Every message re-sends the whole history | `/clear` after each round; the handoff in `docs/rounds/` carries over |
| "continue" after a long break with big agents still open | Their cache has gone cold, so everything is re-read at full price: once ~60 % of a usage window in one message | A fresh session: "read the last round doc and go on" |
| The biggest model for everything | A big file split: ~135–190k tokens on Sonnet, ~280–390k on Opus, same result | `/godot-round` picks Sonnet for mechanical work by itself |
| "Find all the bugs in the project" | ~250k tokens for one sweep | `/godot-analyse` (a script, about a second) and playtests; sweeps only before a big playtest |
| Huge scripts | An agent reads a file before editing it: a 2000-line script is 20–30k tokens every time | The kit keeps scripts under 800 lines and flags the big ones |
| Ten small messages | Every agent pays to load the project | One list, batched into a few agents |
| A long CLAUDE.md | It loads on every turn of every agent | The kit keeps it under 5 KB; details live in `docs/` |

Waiting costs time, not tokens. The kit runs tests in parallel and only the ones your
change touches. The full suite runs once per round.

## 4. While it works

- **Keep using your PC.** Everything runs headless (no windows) unless you allow it. The
  round asks once (`/godot-windows on|off` changes it).
- **Leaving? Say so.** "I'm going to bed, do it all" makes the round take design
  decisions itself instead of waiting for you. It lists them as "Decisions (override
  any)" at the top of the round doc. Changing one in the morning is a small task.
- **Ask anything mid-round**: "how far along are we?", "how long until it's done?".
  You get done / not done, what's running and when it ends.
- **Don't edit the same files** while agents work on them. Play, or write the next list.
- **Want a build for friends?** "make a release zip" (module `build-release`). On a Mac,
  `--mac` gives an app you can double-click. The export templates download in seconds,
  because only what's needed is fetched.

## 5. When something goes wrong

- **"Why did that take so long?"** Ask it. The answer usually names a fixable cause (a
  flaky test, a check that ran too late), and the round doc records it so the next round
  avoids it. This is how the kit got faster: almost every rule in it started as that
  question.
- **"Remember this"**: Claude Code keeps memories per project. A correction you give
  twice should become one ("always ask before opening windows", "UI sounds must be soft").
- **It broke something that worked:** ask for a test that covers it. Tests are the only
  memory that agents can't ignore.
- **Results look wrong but tests are green:** say exactly what you saw (section 2).
  "It looks off" gets a guess; "the cart floats 20 cm above the deck" gets a fix.
- **The project feels slow to work in:** run `/godot-analyse` again. It measures the
  project and suggests what to fix first.
- **Machine problems** (Godot not found, Blender, Windows): `/godot-doctor`.

## 6. Cheat sheet

| You want | Type |
|---|---|
| A new game, set up right | `/godot-start <your idea>` |
| Check an existing project | `/godot-analyse`, then `/godot-analyse apply 1,3` |
| A list of fixes and features | `/godot-round <numbered list>` |
| One small change | just ask |
| Start fresh after a round | `/clear` |
| Allow or block game windows | `/godot-windows on` / `off` |
| Is my machine ready? | `/godot-doctor` |
| A build for friends | "make a release zip" |
| See what changed in the kit | [CHANGELOG.md](CHANGELOG.md) |
