# Contributing

Contributions are welcome, including ones written with an AI assistant.

## Bring the measurement

Don't write "this is faster" or "this fixes the offsets". Write what you measured, against what, and
the number before and after — and the worst case beside the median. A negative result needs the same:
say why your check could have seen the effect.

## How the code is written

The same for Python and C++:
- **KISS, lean, DRY, YAGNI.** No boilerplate, no fallbacks, no backwards compatibility.
- **No defensive programming:** let it break where the fault is. The exceptions are the boundaries
  where outside input enters, and code that runs inside the game process.
- **Modular:** what belongs together stays together, one file per group of functions.
- **A script only defines when it is loaded;** its work starts under `if __name__ == '__main__':`.

## Before you open a pull request

- **Test small first, on hard cases.** A run without errors is not a result; a prediction that came
  true is.
- **State the build:** game version, DLC, mods, debug mode on or off.
- **English only**, in names, comments, messages and the channel protocol.
- **Derive, don't hard-code** memory addresses, field offsets or click positions.
- **No game files**, ever.
- **Bundle your C++:** the DLL only enters the game at injection. Do the Python first, build once, run
  `tests/test_channel.py`, then restart the game.
- Update `CHANGELOG.md` in one line per change, at most 180 characters and twelve lines a day;
  `ARCHITECTURE.md` only when a part or a boundary moves.
- After changing a tool, run `python -m tools.toolindex`, so `reports/toolindex.md` lists its calls.

## Checks that must pass

`python -m tools.check`, `python -m pytest`, `python -m ruff check .` and `python -m mypy`. `check.py`
checks that every path, channel command and script start named in the documents exists and that the
changelog stays short, then recomputes every number in `reports/claims.json`; `tests/test_loading.py`
reports a script that does work when it is loaded.
A number that carries a decision belongs in `claims.json` with its counting rule.

Don't name a script `test_*.py` unless pytest should collect it: scripts under `tools/` that are run by
hand may speak through NVDA.

The claims stop at the first input your machine lacks: the game on disk, its Documents folder, a
built DLL, the save one claim names, or a harvest of your own (`python -m tools.ck3.harvest <pid>`;
its console route needs `-debug_mode`).

## Reporting a problem as a blind user

Open an issue on GitHub. Include the game version, your DLC and mods, your NVDA version and whether
the sleep-mode add-on is installed, and what the tool said when it went wrong. If it fell silent
instead, say so — that is the most useful report there is.

## Other screen readers

Only NVDA is supported, because the maintainer cannot test anything else. If you use another screen
reader and can test, open an issue: adding Prism or SRAL behind the speech seam is a small change.
