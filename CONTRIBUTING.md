# Contributing

Contributions are welcome, including ones written with an AI assistant. Most of this project was.
There is one house rule that matters more than style, and it applies to humans and assistants
equally.

## Bring the measurement

Do not write "this is faster" or "this fixes the offsets". Write what you measured, against what,
and what the number was before and after.

> Click points were 92.5 points off in x (median, 24 words on the main menu, checked against the
> text recogniser). With the scale applied: 0.5.

A claim without a measurement cannot be reviewed, because the reviewer cannot run your machine,
your save, your DLC set or your mods. A number with a counting rule can.

The same applies to negative results. "It does not work" is not reportable; "the window count did
not change, but a closed window keeps its widgets, so the counter could not have shown it" is.

## Before you open a pull request

- **Test it small first, and pick hard cases.** Five items chosen from the known problem cases, not
  the first five on the list. A run that finishes without an error message is not a result; a
  prediction that came true is.
- **State the build.** Game version, DLC, mods, and whether debug mode was on. All of those change
  what you see.
- **Derive, do not hard-code.** No memory addresses, field offsets, click coordinates or widget
  positions in source. If you need one, derive it and verify it at runtime.
- **Do not add game files.** Nothing belonging to Paradox goes in this repository, ever.

## What to update

Two files, and no more than that:

- `CHANGELOG.md` — one line per change: what changed and why.
- `ARCHITECTURE.md` — only when a layer or a boundary moves.

## Before it can be merged: `python tools/check.py`

The house rule above has a mechanical half. `check.py` recomputes every number in
`reports/claims.json` against the disk and verifies that every project path named in the
documentation still exists, and it has to pass.

A number that carries a decision belongs in `claims.json` with its counting rule — what was counted,
where, and how — rather than in prose. Prose ages; a number that can be recomputed does not. The
counting rule matters as much as the number: three counts in this project were wrong because a
folder was not walked, and nobody could see it because the rule was never written down.

Two things to expect. `check.py` measures *this* installation, so on a fresh clone the claims about
the executable, the saves and the DLL will read as drifted until you have built the DLL and have the
game on disk; that is the tool working, not failing. And if you rename anything, run
`python -m pyflakes tools` afterwards — a rename that compiles can still be half done, and that has
cost this project real time.

`check.py` also verifies every file name the documentation mentions, including bare names with no
folder in front of them. The convention that makes that work: **backticks mean the thing exists.**
Name a file that was removed in plain text instead.


The maintainer keeps separate working notes, in Dutch, which are not part of this repository. You
do not need them, and nothing in a pull request should depend on them.

## Reporting a problem as a blind user

Include the game version, your DLC and mod list, and what the tool said out loud when it went
wrong. If it fell silent instead of saying something, that is the most useful bug report there is —
silence is the failure mode this project is most worried about.

## Screen readers other than NVDA

Only NVDA is supported, for an honest reason: the maintainer is blind and has no way to test JAWS,
Narrator or anything else. Shipping backends nobody has verified would mean shipping a screen
reader that might go quiet, which is worse than not supporting it.

If you use something else and are willing to test, say so in an issue. Adding Prism or SRAL behind
the existing speech seam is a small change; verifying it is the part that needs you.
