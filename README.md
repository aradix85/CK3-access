# CK3 Access

Screen reader access for **Crusader Kings III**, without OCR.

> **Status: research.** The machinery works and a window can be stepped through with the arrow keys,
> but there is no installable mod yet. MIT licence, no promise of support.

The game keeps its interface in memory as a widget tree and ships full MSVC RTTI, so the tree can be
found and read directly. An injected DLL reads it; Python turns it into speech and braille through
NVDA. No game files are copied or redistributed.

## What works

- **An injected channel** reads the widget tree and posts mouse and key input, combinations included,
  from inside the process — it never takes focus.
- **It survives patches:** every memory offset is derived from the running game and rechecked at start.
- **Events are read aloud live** and can be answered.
- **282 windows are mapped**, checked against what the running game builds; 205 have been harvested and
  joined to the `.gui` files.
- **A reader** hands out one unit per keystroke, speech and braille together. Switched-off buttons say
  so, hidden widgets stay silent, and every failure is spoken.
- **A map layer from the files alone:** neighbours, de jure titles, distance, bearing, travel days.
- **The game state is readable** without searching, checked against a save.

Developed on 1.19.0.6, checked on 1.20.0.3. Every number that carries a decision is in
`reports/claims.json` with its counting rule; `tools/check.py` recomputes them.

## Requirements

- Windows and Crusader Kings III
- NVDA, with the add-on in `tools/nvda/addon/` (it puts NVDA to sleep while the game has focus)
- Python 3.11+ and `requirements.txt`
- Visual Studio Build Tools (MSVC, x64); LLVM optional, for clang-tidy

## Running it

    pip install -r requirements.txt
    dll\build_channel.bat                       compiles dll\channel.dll
    python tools\paths.py                       prints where it found the game and your saves
    python tools\ck3\start_game.py              starts CK3 with the channel inside it

The channel answers within seconds; the game needs minutes more to load. `-loadsave=<save>` loads a
save directly. Paths come from the registry; override with `CK3_GAME`, `CK3_DOCS` or `CK3_WORK`.
`reports/toolindex.md` lists every call. Your antivirus may object to the injector.

## Layout

    dll/        the injected channel (C++ source and build script)
    tools/      derivation, memory reading, gui parsing, input, speech, measurement
    reports/    generated, machine-checked facts about this build
    screens/    screen files: what the reader says first, and which key acts on a row
    tests/      pytest, including the DLL driven through its real pipe without the game

`check_rtti.ps1` tells in seconds whether this approach could work for another Paradox executable.
The NVDA controller client is not included (`tools/nvda/README.md`).

See `ARCHITECTURE.md`, `CONTRIBUTING.md` and `CREDITS.md`.
