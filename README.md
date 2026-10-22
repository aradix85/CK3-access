# CK3 Access

Screen reader access for **Crusader Kings III**, read from the game's memory rather than by OCR.

> **Status: research.** The machinery works and a window can be stepped through with the arrow keys,
> but there is no installable mod yet. MIT licence, no promise of support.

The game keeps its interface in memory as a widget tree and ships full MSVC RTTI, so the tree can be
found and read directly. An injected DLL reads it; Python turns it into speech and braille through
NVDA. No game files are copied or redistributed.

## What works

- **An injected research channel** reads the widget tree and posts mouse and key input, combinations
  included, from inside the process to map the interface — it never takes focus.
- **It survives patches:** every memory offset is derived from the running game and rechecked at start.
- **Events are read aloud live**, with the key that answers them.
- **282 windows are mapped**, checked against what the running game builds; 239 were harvested on
  1.20.1.2 and joined to the `.gui` files.
- **A reader** hands out one unit per keystroke, speech and braille together. Switched-off buttons say
  so, hidden widgets stay silent, and every failure is spoken.
- **A map layer from the files alone:** neighbours, de jure titles, distance, bearing, travel days.
- **The game state is readable** without searching, checked against a save.

Tested on Crusader Kings III 1.20.1.2 without mods, and NVDA 2026.2.

## Requirements

- Windows and the Steam version of Crusader Kings III
- NVDA, with its controller client and the add-on (below)
- Python 3.11+ and `requirements.txt`
- Visual Studio Build Tools (MSVC, x64); LLVM optional, for clang-tidy

## NVDA

**The controller client** is how the reader speaks and writes braille, and it is not in this
repository. Download `nvda_<version>_controllerClient.zip` from `download.nvaccess.org/releases/stable/`
and put the 64-bit `nvdaControllerClient.dll` next to `tools/nvda/speech.py`; its licence is already
there. `tools/nvda/check_speech_by_ear.bat` then checks by ear that it speaks.

**The add-on** in `tools/nvda/addon/` puts NVDA to sleep while the game has focus, so NVDA does not
report the game window as well; the reader keeps speaking. Copy that folder to
`%APPDATA%\nvda\addons\ck3Access\`, or to `userConfig\addons\ck3Access\` of a portable NVDA, and
restart NVDA. NVDA+Shift+S switches sleep mode by hand.

## Running it

From the project folder; the tools are a package and start as modules.

    pip install -r requirements.txt
    dll\build_channel.bat                       compiles dll\channel.dll
    python -m tools.paths                       prints where it found the game and your saves
    python -m tools.ck3.start_game              starts CK3 with the channel inside it
    python -m tools.ck3.reader <pid>            the reader, on the game start_game started

The channel answers within seconds; the game needs minutes more to load. `start_game` passes its
arguments to the game, so `-loadsave=<save>` loads a save directly, named without `.ck3`. In the
reader, up and down step through the window, Delete explains the current line, and F12 turns the
reader off and on. Paths come from the registry; override with `CK3_GAME`, `CK3_DOCS` or `CK3_WORK`.
`reports/toolindex.md` lists every call. Your antivirus may object to the injector.

## Layout

    dll/        the injected channel (C++ source and build script)
    tools/      derivation, memory reading, gui parsing, input, speech, measurement
    reports/    generated, machine-checked facts about this build
    screens/    screen files: what the reader says first, and which key acts on a row
    tests/      pytest, including the DLL driven through its real pipe without the game

Report a problem as a GitHub issue; `CONTRIBUTING.md` says what helps. See also `ARCHITECTURE.md`
and `CREDITS.md`.
