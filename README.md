# CK3 Access

Screen reader access for **Crusader Kings III**, without OCR.

The game keeps its entire interface in memory as a tree of widgets, and it ships the full MSVC RTTI
tree, so that tree can be located and read directly: names, texts, rectangles, visibility. This
project injects a small DLL that reads it and hands the result to NVDA.

**No game files are copied or redistributed.** Everything is read at runtime from the running
process and from files already on your disk. Nothing belonging to Paradox is shipped.

## Status: research, not yet playable

Be clear-eyed about this before you download anything. There is **no installable mod yet** and
nothing is read aloud to you during normal play. What exists is the machinery underneath, and it is
measured rather than assumed:

- The DLL injects and answers within ~25 seconds of launch.
- Nine memory field offsets are re-derived from the running game at **every start** and re-checked,
  so a patch does not break it. Tested against 1.16.2: one had moved, and it recovered on its own.
- An event window can be read and answered end to end — title, description and options straight out
  of memory, an option chosen by clicking a computed point, verified against the localisation files
  on disk.
- Mouse and keyboard input is posted from inside the process, so it never steals focus.
- Nearly every window in the game can be created on demand, and 178 have been harvested with every
  widget's name, class, rectangle, sibling index and visibility (`reports/windows.json`).
- The `.gui` files are parsed rather than grepped (`tools/ck3/guimap.py`): templates, inheritance
  and named slots are resolved, so a window expands into the widget tree the engine would build.
- That expansion is paired with the live tree on class and child order (`tools/ck3/pairing.py`), so
  the meaning on disk reaches widgets carrying no name — three in four of them. Names are kept out
  of the alignment and used to score it afterwards: they come out right 98.4 per cent of the time.
  Nine in ten of the texts on screen now have a place in a gui file, and every plain localisation
  key the alignment points at matches what was actually displayed.
- Which button opens which window is measured by pressing it, because it cannot be read off disk
  (`reports/openers.json`).
- All of the above still holds on 1.19.0.6 with every DLC and five content mods loaded.

Every number behind these claims is in `reports/claims.json` with the rule it was counted by, and
`tools/check.py` recomputes them.

What is missing is the half a player would notice: nothing decides *what* to say, in *what order*.
That layer does not exist yet.

Text recognition is in here too (`tools/ocr.py`, `tools/boxreader.py`), but as a measuring
instrument: it reads the screen independently so that what comes out of memory can be checked
against what is actually drawn. It is not how the game gets read.

## Requirements

- Windows, Crusader Kings III (developed against **1.19.0.6**)
- **NVDA**. Other screen readers are not supported yet — see CONTRIBUTING if you can help test one.
  `tools/nvda/addon/` is a small add-on that puts NVDA in sleep mode while the game has focus, so
  the reader is not talked over and keeps the keys it needs. Sleep mode does not gate the controller
  client, so speech and braille still arrive.
- Python 3.11+ and the packages in `requirements.txt` (`pip install -r requirements.txt`)
- Visual Studio Build Tools (MSVC, x64) to compile the DLL

## Running it

There is nothing to install and nothing to play yet. What follows gets you to the point where the
tooling can read the running game — that is as far as this repository goes today.

    pip install -r requirements.txt
    dll\build_channel.bat                       compiles dll\channel.dll
    python tools\paths.py                       prints where it found the game and your saves
    python tools\ck3\start_game.py              starts CK3 with the channel inside it

`start_game.py` prints the process id and returns as soon as the channel answers, which is about 25
seconds after launch. The game itself needs several minutes more before its interface exists, so
give it that time before asking anything about widgets. From there, `tools/ck3/derive.py` derives
the field offsets, `tools/ck3/channel.py` talks to the DLL, and `reports/toolindex.md` lists every
call with its arguments and the shape of what it returns.

Paths are derived, not configured: the game comes from your Steam library in the registry and the
save folder from the Windows shell setting, so a second drive or a relocated Documents folder works.
Override with `CK3_GAME`, `CK3_DOCS` or `CK3_WORK` if you need to.

**One part needs no game running at all.** `tools/ck3/guimap.py` reads the `.gui` and localisation
files straight off your disk, so it is the cheapest place to see whether this repository does
anything useful on your machine:

    python -c "from tools.ck3 import guimap; print(len(guimap.files()), 'gui files,', len(guimap.windows()), 'windows')"

On this machine that prints 563 gui files and 196 windows, and `reports/claims.json` carries both
numbers with the rule they were counted by.

**Your antivirus may object, and you need to know that up front.** This starts the game suspended,
loads a DLL into it and resumes it. That is what an injector does and what malware does, so an
unsigned injector can be flagged, quarantined or silently blocked. If something does not start and
nothing explains why, check your antivirus history first. Adding an exclusion needs administrator
rights and is your decision, not this tool's.

## Support and guarantees

None. This is a personal project by a blind player who wants to play this game. It is offered as
is, under the MIT licence. Bug reports are welcome, fixes more so, but no support is promised and
no schedule is implied.

## Repository layout

    dll/        the injected channel (C++ source and build script)
    tools/      Python: derivation, memory reading, gui parsing, input, speech, measurement
    reports/    generated, machine-checked facts about this build

`tools/check.py` recomputes every number in `reports/claims.json` against the disk and checks that
every path named in the documentation still exists. It measures *this* installation, so on a fresh
clone some lines will read as drifted until you have built the DLL and pointed it at your own game.

Three things are deliberately **not** in this repository. Dumps generated from the game (data
types, effects, triggers) and the RTTI type list extracted from the executable: that is Paradox's
data, and you can generate it yourself with the game's own debug commands. The NVDA controller
client binary — see `tools/nvda/README.md` for where to get it. And the maintainer's working
notes, which are in Dutch, written for AI sessions, and go stale within a day; what matters from
them is in `ARCHITECTURE.md` and `CONTRIBUTING.md`.

See `ARCHITECTURE.md` for how the pieces fit, `CONTRIBUTING.md` before opening a pull request, and
`CREDITS.md` for whose ideas this stands on.
