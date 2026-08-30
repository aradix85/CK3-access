# Contributing

Contributions are welcome, including ones written with an AI assistant — most of this project was.
There is one house rule that matters more than style.

## Bring the measurement

Do not write "this is faster" or "this fixes the offsets". Write what you measured, against what,
and what the number was before and after.

> Click points were 92.5 points off in x (median, 24 words on the main menu, checked against the
> text recogniser). With the scale applied: 0.5.

A claim without a measurement cannot be reviewed, because the reviewer cannot run your machine, your
save, your DLC set or your mods. A number with a counting rule can. The same goes for negative
results: "it does not work" is not reportable; "the window count did not change, but a closed window
keeps its widgets, so the counter could not have shown it" is.

## Before you open a pull request

- **Test it small first, and pick hard cases.** Five items from the known problem cases, not the
  first five on the list. A run that finishes without an error is not a result; a prediction that
  came true is.
- **State the build.** Game version, DLC, mods, and whether debug mode was on.
- **English only.** Names, comments, docstrings, messages, the channel protocol and the keys in
  `reports/` are all English. Mixing a second language back in is how a half-finished rename hides.
- **Derive, do not hard-code.** No memory addresses, field offsets, click coordinates or widget
  positions in source. Derive it and verify it at runtime.
- **Do not add game files.** Nothing belonging to Paradox goes in this repository, ever.
- **Bundle your C++.** A change in `tools/` counts on the next call, but the DLL only enters the
  game at injection, so a running game keeps the old one however often you build. Do the Python
  first, gather the C++ into one round, build once, restart once.

Update `CHANGELOG.md`, and `ARCHITECTURE.md` only when a layer or a boundary moves. Nothing else.

## Before it can be merged: `python tools/check.py`

It recomputes every number in `reports/claims.json` against the disk and verifies that every project
path the documentation names still exists. It has to pass.

A number that carries a decision belongs in `claims.json` with its counting rule — what was counted,
where, and how — rather than in prose. Three counts here were wrong because a folder was not walked,
and nobody could see it because the rule was never written down. If a document repeats one of those
numbers, list it under `quoted_in` and `check.py` will hold the document to it.

On a fresh clone the claims about the executable, the saves and the DLL read as drifted until you
have built the DLL and have the game on disk; that is the tool working. After a rename, also run
`python -m pyflakes tools` — a rename that compiles can still be half done.

## Reporting a problem as a blind user

Include the game version, your DLC and mod list, and what the tool said out loud when it went wrong.
If it fell silent instead, that is the most useful bug report there is — silence is the failure mode
this project worries about most.

## Screen readers other than NVDA

Only NVDA is supported, for an honest reason: the maintainer is blind and cannot test JAWS,
Narrator or anything else. Shipping unverified backends would mean shipping a screen reader that
might go quiet, which is worse than not supporting it. If you use something else and are willing to
test, say so in an issue — adding Prism or SRAL behind the existing speech seam is a small change;
verifying it is the part that needs you.
