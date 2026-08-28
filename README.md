# CK3 Access

Screen reader access for **Crusader Kings III**, without OCR.

The game keeps its whole interface in memory as a widget tree, and it ships the full MSVC RTTI
tree, so that tree can be located and read directly: names, texts, rectangles, visibility. This
project injects a small DLL that reads it and hands the result to NVDA.

**No game files are copied or redistributed.** Everything is read at runtime from the running
process and from files already on your disk.

## Status: research, not yet playable

There is **no installable mod**, and nothing is read aloud to you during play. What exists is the
machinery underneath:

- The DLL injects and answers about 25 seconds after launch. Mouse and key input is posted from
  inside the process, so it never takes focus off your screen.
- Nine memory field offsets are re-derived and re-verified at **every start**, so a patch does not
  break it. Tested against 1.16.2: one had moved, and it recovered on its own.
- An event window can be read and answered end to end — title, description, options — straight out
  of memory, checked against the localisation files on disk.
- The game state is reachable without searching: from a global in the executable to any character in
  four reads. A regression pass holds four hundred of them against the save and names the field that
  disagrees; it runs clean on three game states differing in era, faith, government and mod set.
- 178 windows have been harvested widget by widget. **A window only carries its data when it is
  opened the way a player opens it**; built from the console it has its shape and its captions and
  nothing else.
- The `.gui` files are parsed rather than grepped, and that expansion is paired with the live tree
  on structure, so meaning on disk reaches the three widgets in four that carry no name.
- All of this holds on 1.19.0.6 with every DLC and five content mods loaded.

Every number behind these claims is in `reports/claims.json` with the rule it was counted by, and
`tools/check.py` recomputes them.

What is missing is the half a player would notice: nothing decides *what* to say, in *what order*.

Text recognition (`tools/ocr.py`, `tools/boxreader.py`) is a measuring instrument here, not the way
the game gets read — it checks what comes out of memory against what is actually drawn.

## Requirements

- Windows, Crusader Kings III (developed against **1.19.0.6**)
- **NVDA.** No other screen reader is supported yet — see `CONTRIBUTING.md` if you can help test
  one. `tools/nvda/addon/` puts NVDA in sleep mode while the game has focus, so it neither talks
  over the tool nor holds the keys it needs; speech and braille still arrive.
- Python 3.11+ and the packages in `requirements.txt`
- Visual Studio Build Tools (MSVC, x64) to compile the DLL

## Running it

Nothing to install and nothing to play. This gets you to where the tooling can read the running
game, which is as far as this repository goes today.

    pip install -r requirements.txt
    dll\build_channel.bat                       compiles dll\channel.dll
    python tools\paths.py                       prints where it found the game and your saves
    python tools\ck3\start_game.py              starts CK3 with the channel inside it

`start_game.py` returns as soon as the channel answers, about 25 seconds in; the game's interface
needs several minutes more before there is anything to ask about. From there `tools/ck3/derive.py`
derives the field offsets, `tools/ck3/channel.py` talks to the DLL, and `reports/toolindex.md`
lists every call with its arguments and the shape of what it returns.

Paths are derived, not configured: the game from your Steam library in the registry, the saves from
the Windows shell setting. Override with `CK3_GAME`, `CK3_DOCS` or `CK3_WORK`.

**One part needs no game running at all**, so it is the cheapest way to see whether any of this
works on your machine — `tools/ck3/guimap.py` reads the `.gui` and localisation files off disk:

    python -c "from tools.ck3 import guimap; print(len(guimap.files()), 'gui files,', len(guimap.windows()), 'windows')"

**Your antivirus may object.** This starts the game suspended, loads a DLL into it and resumes it —
what an injector does and what malware does, so an unsigned one can be flagged or silently blocked.
If nothing starts and nothing explains why, check your antivirus history. Adding an exclusion needs
administrator rights and is your decision.

## Support and guarantees

None. A personal project by a blind player who wants to play this game, offered as is under the MIT
licence. Bug reports are welcome, fixes more so, but no support is promised.

## Repository layout

    dll/        the injected channel (C++ source and build script)
    tools/      derivation, memory reading, gui parsing, input, speech, measurement
    reports/    generated, machine-checked facts about this build

`check_rtti.ps1` in the root is separate from all of it: point it at any Paradox executable and it
tells you in seconds whether this whole approach could work there — tens of thousands of RTTI type
names and a `CPdxGuiWidget` base class mean yes, nothing means no.

`tools/check.py` recomputes every number in `reports/claims.json` and checks that every path the
documentation names still exists. It measures *this* installation, so on a fresh clone some lines
read as drifted until you have built the DLL and have the game on disk.

Deliberately absent: anything dumped from the game, which is Paradox's data and which you can
generate yourself; the NVDA controller client binary (`tools/nvda/README.md` says where to get it);
and the maintainer's working notes, which are in Dutch and go stale within a day.

See `ARCHITECTURE.md` for how the pieces fit, `CONTRIBUTING.md` before opening a pull request, and
`CREDITS.md` for whose ideas this stands on.
