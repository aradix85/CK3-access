# Contributing

Contributions are welcome, including ones written with an AI assistant.

## Bring the measurement

Don't write "this is faster" or "this fixes the offsets". Write what you measured, against what, and
the number before and after — and the worst case beside the median. A negative result needs the same:
say why your check could have seen the effect.

## Before you open a pull request

- **Test small first, on hard cases.** A run without errors is not a result; a prediction that came
  true is.
- **State the build:** game version, DLC, mods, debug mode on or off.
- **English only**, in names, comments, messages and the channel protocol.
- **Derive, don't hard-code** memory addresses, field offsets or click positions.
- **No game files**, ever.
- **Bundle your C++:** the DLL only enters the game at injection. Do the Python first, build once, run
  `tests/test_channel.py`, then restart the game.
- Update `CHANGELOG.md` in one line per change; `ARCHITECTURE.md` only when a part or a boundary moves.

## Checks that must pass

`python -m tools.check`, `python -m pytest`, `python -m ruff check .` and `python -m mypy`. `check.py`
recomputes every number in `reports/claims.json` and checks that every path the documents name exists.
A number that carries a decision belongs in `claims.json` with its counting rule.

Don't name a script `test_*.py` unless pytest should collect it: scripts under `tools/` that are run by
hand may speak through NVDA.

On a fresh clone some claims read as drifted until you have built the DLL and have the game on disk,
and claims over the harvest measure nothing until you run a harvest of your own. The maintainer's
working notes are not part of the repository and nothing should depend on them.

## Reporting a problem as a blind user

Include the game version, your DLC and mods, and what the tool said when it went wrong. If it fell
silent instead, say so — that is the most useful report there is.

## Other screen readers

Only NVDA is supported, because the maintainer cannot test anything else. If you use another screen
reader and can test, open an issue: adding Prism or SRAL behind the speech seam is a small change.
