# CK3 Access

Screen reader access for **Crusader Kings III**, without OCR.

> **Status: research.** The machinery underneath works; nothing is read aloud during play yet, and
> there is no installable mod. What is missing is the half a player would notice: nothing decides
> *what* to say, in *what order*. Offered as is under the MIT licence, with no promise of support.

The game keeps its whole interface in memory as a widget tree, and it ships the full MSVC RTTI tree,
so that tree can be located and read directly: names, texts, rectangles, visibility. This project
injects a small DLL that reads it and hands the result to NVDA.

**No game files are copied or redistributed.** Everything is read at runtime from the running
process and from files already on your disk.

## What works

- **The channel.** An injected DLL answers about 25 seconds after launch, reads the widget tree, and
  posts mouse and key input from inside the process — it never takes focus off your screen.
- **It survives a patch.** Every offset is derived from the running game and rechecked at each
  start. Against build 1.16.2 one had moved, and it recovered on its own.
- **An event reads end to end** — title, description, options — straight out of memory, checked
  against the localisation files on disk.
- **203 windows have been harvested** widget by widget and paired with the parsed `.gui` files on
  structure, so meaning on disk reaches the nameless widgets: nine in ten of the ones showing text.
- **The tooling never fails silently.** Anything that goes wrong leaves through one exit as a
  sentence saying what failed, where, and what to do — never as an error code or as nothing.
- **Where a county is, from the files alone.** Its neighbours out to three rings, the seas and
  rivers it touches, the de jure titles above it, and the distance, bearing and travel days to
  another one — no save, no running game.
- **The game state is readable without searching:** any character's name, culture, faith, money and
  levies, and which number means which culture, faith, religion or trait, out of the running game
  rather than out of a save. A regression pass holds four hundred characters against the save and
  names the field that disagrees.

All of this holds on 1.19.0.6 with every DLC and five content mods loaded. Every number behind it is
in `reports/claims.json` with the rule it was counted by; `tools/check.py` recomputes them.

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

This gets you to where the tooling can read the running game, which is as far as this repository
goes today.

    pip install -r requirements.txt
    dll\build_channel.bat                       compiles dll\channel.dll
    python tools\paths.py                       prints where it found the game and your saves
    python tools\ck3\start_game.py              starts CK3 with the channel inside it

`start_game.py` returns as soon as the channel answers, about 25 seconds in; the interface needs
several minutes more before there is anything to ask about. From there `tools/ck3/derive.py` derives
the field offsets, `tools/ck3/channel.py` talks to the DLL, and `reports/toolindex.md` lists every
call with its arguments and the shape of what it returns.

Paths are derived, not configured: the game from your Steam library in the registry, the saves from
the Windows shell setting. Override with `CK3_GAME`, `CK3_DOCS` or `CK3_WORK`.

**One part needs no game at all**, so it is the cheapest way to see whether any of this works on
your machine — `tools/ck3/guimap.py` reads the `.gui` and localisation files off disk:

    python -c "from tools.ck3 import guimap; print(len(guimap.files()), 'gui files,', len(guimap.windows()), 'windows')"

**Your antivirus may object.** This starts the game suspended, loads a DLL into it and resumes it —
what an injector does and what malware does. If nothing starts and nothing explains why, check your
antivirus history.

## Repository layout

    dll/        the injected channel (C++ source and build script)
    tools/      derivation, memory reading, gui parsing, input, speech, measurement
    reports/    generated, machine-checked facts about this build

`check_rtti.ps1` is separate from all of it: point it at any Paradox executable and it tells you in
seconds whether this approach could work there — tens of thousands of RTTI type names and a
`CPdxGuiWidget` base class mean yes, nothing means no.

Deliberately absent: anything dumped from the game, which is Paradox's data and which you can
generate yourself; the NVDA controller client binary (`tools/nvda/README.md` says where to get it);
and the maintainer's working notes, which are in Dutch and go stale within a day.

See `ARCHITECTURE.md` for how the pieces fit, `CONTRIBUTING.md` before opening a pull request, and
`CREDITS.md` for whose ideas this stands on.
