# CK3 Access

Screen reader access for **Crusader Kings III**, read from the game's memory rather than by OCR.

> **Status: research.** The machinery works and a window can be stepped through with the arrow keys,
> but there is no installable mod yet. MIT licence (`LICENSE`), no promise of support.

The game keeps its interface in memory as a widget tree and ships full MSVC RTTI, so the tree can be
found and read directly. An injected DLL reads it; Python turns it into speech and braille through
NVDA. No game files are copied or redistributed.

## 1. What works

- **An injected research channel** reads the widget tree and posts mouse and key input, combinations
  included, from inside the process to map the interface — it never takes focus.
- **It survives patches:** every memory offset is derived from the running game and rechecked at start.
- **Events are read aloud live**, with the key that answers them.
- **282 windows are mapped**, checked against what the running game builds; 252 were harvested on
  1.20.1.2 and joined to the `.gui` files. Which ones a player's route has not reached yet, and how
  a player gets to each, `python -m tools.ck3.missing` writes to `reports/missing.json`.
- **A reader** hands out one unit per keystroke, speech and braille together. Switched-off buttons say
  so, hidden widgets stay silent, and every failure is spoken.
- **A map layer from the files alone:** neighbours, de jure titles, distance, bearing, travel days.
- **The game state is readable** without searching, checked against a save.

Tested on Crusader Kings III 1.20.1.2 without mods, and NVDA 2026.2.

## 2. Requirements

- Windows and the Steam version of Crusader Kings III
- NVDA, with its controller client (section 3)
- Python 3.11+ and `requirements.txt`
- Visual Studio Build Tools (MSVC, x64); LLVM optional, for clang-tidy

## 3. NVDA

**The controller client** is how the reader speaks and writes braille, and it is not in this
repository. Download `nvda_<version>_controllerClient.zip` from `download.nvaccess.org/releases/stable/`
and put the 64-bit `nvdaControllerClient.dll` next to `tools/nvda/speech.py`; its licence is already
there. `tools/nvda/check_speech_by_ear.bat` then checks by ear that it speaks.

If NVDA's own announcements get in the way in the game window, NVDA+Shift+S puts NVDA to sleep there;
the reader keeps speaking through the controller client.

## 4. Running it

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

## 5. Reporting a problem

Open an issue on GitHub. Include the game version, your DLC and mods, your NVDA version and whether
NVDA was in sleep mode, and what the tool said when it went wrong. If it fell silent
instead, say so — that is the most useful report there is.

Only NVDA is supported, because the maintainer cannot test anything else. If you use another screen
reader and can test, open an issue: adding Prism or SRAL behind the speech seam is a small change.

## 6. How it works

Seven parts, 6.1 to 6.7 below, split where a game patch is most likely to hit.

| | Part | What it is for |
|---|---|---|
| 6.1 | **The channel** — `dll/channel.cpp`, `dll/input.cpp`, `dll/channel.h`, `tools/ck3/channel.py` | a few primitives over a pipe; knows nothing about the game |
| 6.2 | **Derivation** — `tools/ck3/derive.py` | derives the memory offsets and rechecks them at each start |
| 6.3 | **Visibility** — `tools/ck3/widgettree.py`, `tools/ck3/onscreen.py` | the widget tree, what of it is really on screen, and which window lies on top |
| 6.4 | **Input** | keys taken before the game sees them; clicks and keys posted inward |
| 6.5 | **Reading the game** | five independent sources; their disagreement is the test |
| 6.6 | **Presentation** — `screens/`, `tools/ck3/reading.py`, `tools/ck3/reader.py` | what gets said, in what order, on which key |
| 6.7 | **Speech** — `tools/nvda/speech.py` | one seam to NVDA, speech and braille together |

**Direction:** installing should end up as one DLL with the NVDA controller client and the screen files
beside it — no Python, no paths to fill in. So logic moves into the DLL when a measurement says it
pays. Speech and braille stay outside; receiving keys stays inside.

### 6.1 The channel

An injected DLL exposing primitives over a named pipe: read memory, walk the widget tree, post a
click, a key, a character or a key combination. It contains no game knowledge and no speech.
- Tested without the game: `tests/test_channel.py` drives every command through the real pipe
  against a fake widget tree, also under AddressSanitizer. The build stops on any warning.
- A limit either grows or announces itself, never silently.
- **The pipe is a workbench, not a product.** The player build will be compiled without it; the DLL
  never opens a network connection.

### 6.2 Derivation

No memory layout is hard-coded. Widget vtables come from the RTTI in the executable; nine field
offsets are derived from the running game and rechecked at each start, and derived again if a check
fails.

### 6.3 Visibility

Every window is built up front and stays in the tree, so being in the tree says nothing. What decides
whether something is drawn:
- **A state byte**, along the parent chain: only 0x08 hides (`onscreen.shown`). 0x20 means the widget
  lets the mouse through, so a drawn window carrying it never catches a click. 0x02 means switched
  off, inherited from where `enabled` is false.
- **Alpha** along the parent chain.
- **Scrolling decides nothing for the reader:** what lies in a scroll area that is on screen is read,
  also a row scrolled out of view, because a player can scroll to it. Long character lists build only
  the rows in view, so the rest of those is not read yet.
- **Geometry:** some windows place drawn buttons outside the drawing area at any resolution, where no
  player can reach them, so the product must say so.

Which drawn window is on top follows sibling draw order. A click needs all of this, or it lands on
whatever lies underneath.

### 6.4 Input

- **Receiving:** the DLL hooks the game's window procedure and swallows the keys the reader owns.
- **Acting:** Enter on the line the reader stands on will click that widget, through the same checks
  a research click passes (`openers.press_toward`); not built yet.
- **Sending:** mouse and key messages are posted into the process to map the interface, so the
  player's screen is never taken.
- **A posted click lands on what is topmost at that point.** A click is therefore a measurement: press,
  read what is drawn, put the state back (`tools/ck3/openers.py`).
- **Modifiers:** a posted key carries no modifier state, so `combo` holds the modifier for the game
  while the combination runs.
- **Hovering:** the game shows the tooltip of whatever lies under its own hover point. That point
  follows the real pointer only while the game is in front, and then moving the pointer is enough;
  posted mouse messages never move it. The tooltip's text stands in `_tooltip_root_`, a root outside
  the widget tree that keeps its last text, so `onscreen.shown` decides which text is current.
  `derive.tooltip_root` reaches it without a scan, through the engine's own list of layer roots.
  For now the explain key reads the tooltip the gui files predict.

### 6.5 Reading the game

- **The widget tree** — names, rectangles, text: what is on screen now.
- **The game model** — the same values raw. `tools/ck3/anchor.py` reaches the databases,
  `tools/ck3/model.py` derives the character record, `tools/ck3/numbering.py` maps numbers to keys,
  `tools/ck3/calibrate.py` checks four hundred characters against a save.
- **The `.gui` files** — meaning: which data function fills a widget. `tools/ck3/guimap.py` parses
  them properly, layers and mods merged in load order.
- **The save** — ground truth, valid only for the state that wrote it.
- **The static data files** — `tools/ck3/database.py` and `tools/ck3/mapdata.py`.

Text recognition (`tools/ocr.py`) is a witness, never the product.

**Open a window the way a player does.** The console builds a window without its data context, so it
yields captions without values; a key, a click, a chain of presses the gui files describe
(`openers.chain`), or presses named by hand (`tools/ck3/hand.py`) give the values. **Check the window
map against the game**, not the files: `windowmap.unmapped` lists what the engine built that the map
lacks.

**The tree and the files are joined by structure, not by name** (`tools/ck3/pairing.py`), because most
widgets that show text have no name. `guimap` is the only gui reader and follows the engine's rules,
among them that every `onclick` of a block fires, in order, on a click and on a shortcut alike.

### 6.6 Presentation

Not sorted by screen position; one keystroke gives one unit of speech plus braille.
`tools/ck3/reader.py` claims up, down, F12 and Delete and gives every key back on the way out. An event
is noticed through the child count of the layer that holds events.

**Screen files** under `screens/` hold exceptions only, in the game's own format; whatever they do not
name is read in gui-file order, so a stale file costs detail, never the screen. `tools/ck3/screens.py`
checks every reference against the expanded gui tree. Two blocks are applied: `order` and `key`.

### 6.7 Speech

Two functions: `output(text, mode, braille)` and `failure(where, what, remedy)`.
- **Braille is never optional;** a different braille text needs a reason at the call site.
- The official NVDA controller client, not Tolk, loaded as its own DLL (its licence in section 8).
- Two modes, replace and queue.
- **Nothing speaks when there is nothing to say.** Only a real fault speaks, as one sentence a player
  can act on. `tools/never_silent.py` is the proof and the gate in front of a beta.
- **The game ending is not a fault.** A link that breaks and stays shut is `channel.Gone`, and the
  reader stops on it without a word, whether the game was closed or crashed.

### 6.8 Deliberately not done

- No decompiling or rebuilding the engine; no redistribution of game files.
- The product sends no keys. It clicks only on the player's own Enter, on the widget the reader
  stands on, after checking that the widget is still drawn, on top and switched on; it may move the
  pointer, to read a tooltip or to point at a place on the map. `tools/ck3/modifiers.py` presses real
  keys, as a measurement only.
- No hard-coded addresses, offsets or click positions.

## 7. Contributing

Contributions are welcome, including ones written with an AI assistant.

### 7.1 Bring the measurement

Don't write "this is faster" or "this fixes the offsets". Write what you measured, against what, and
the number before and after — and the worst case beside the median. A negative result needs the same:
say why your check could have seen the effect.

### 7.2 How the code is written

The same for Python and C++:
- **KISS, lean, DRY, YAGNI.** No boilerplate, no fallbacks, no backwards compatibility.
- **No defensive programming:** let it break where the fault is. The exceptions are the boundaries
  where outside input enters, and code that runs inside the game process.
- **Modular:** what belongs together stays together, one file per group of functions.
- **A script only defines when it is loaded;** its work starts under `if __name__ == '__main__':`.

### 7.3 Before you open a pull request

- **Test small first, on hard cases.** A run without errors is not a result; a prediction that came
  true is.
- **State the build:** game version, DLC, mods, debug mode on or off.
- **English only**, in names, comments, messages and the channel protocol.
- **Derive, don't hard-code** memory addresses, field offsets or click positions.
- **No game files**, ever.
- **Bundle your C++:** the DLL only enters the game at injection. Do the Python first, build once, run
  `tests/test_channel.py`, then restart the game.
- Update `CHANGELOG.md` in one line per change, at most 180 characters and twelve lines a day; section 6
  only when a part or a boundary moves.
- After changing a tool, run `python -m tools.toolindex`, so `reports/toolindex.md` lists its calls.

### 7.4 Checks that must pass

`python -m tools.check`, `python -m pytest`, `python -m ruff check .` and `python -m mypy`. `check.py`
checks that every path, channel command and script start named in the documents exists and that the
changelog stays short, then recomputes every number in `reports/claims.json`; `tests/test_loading.py`
reports a script that does work when it is loaded. A number that carries a decision belongs in
`claims.json` with its counting rule.

Don't name a script `test_*.py` unless pytest should collect it: scripts under `tools/` that are run by
hand may speak through NVDA.

The claims stop at the first input your machine lacks: the game on disk, its Documents folder, a
built DLL, the save one claim names, or a harvest of your own (`python -m tools.ck3.harvest <pid>`;
its console route needs `-debug_mode`).

### 7.5 Layout

    dll/        the injected channel (C++ source and build script)
    tools/      derivation, memory reading, gui parsing, input, speech, measurement
    reports/    generated, machine-checked facts about this build
    screens/    screen files: what the reader says first, and which key acts on a row
    tests/      pytest, including the DLL driven through its real pipe without the game

## 8. Credits

This project stands on other people's work and ideas.

- **rashad** (`github.com/rashadnaqeeb`) described the non-OCR approach for CK3 publicly in June 2026: a
  DLL that reads the widget classes through the RTTI the game ships, with addresses re-derived after
  each patch. The idea is his; the code here is not.
- **tfigment** — the Crusader Kings III cheat table on FearLess Cheat Engine (thread 13576): the first
  public map of where this game keeps things in memory, and the technique of reaching a global through
  a wildcard instruction search. Nothing from the table is copied.
- **KeinNiemand** — LargePageInjectorMods (`github.com/KeinNiemand/LargePageInjectorMods`): loading a
  DLL into a Paradox game through `launcher-settings.json`, one of two routes the player version may
  take.
- **The CK3 Wiki**, the Interface page for modders (`ck3.paradoxwikis.com/Interface`): draw order,
  layers, and what `alwaystransparent` and `allow_outside` do to a click.
- **noxsidereum** (skyretk) and **d3dev** (`d3_tooltips`) — worked examples of reading RTTI and
  tooltip text from memory.
- **Agami** (`github.com/Agamidae`) — the CK3 OCR-Support mod. Her choices about what each screen reads
  out, in what order, are the design reference here. Her mod carries no licence, so none of her code is
  used.
- **NVDA** (`github.com/nvaccess/nvda`) and its controller client, LGPL 2.1. Its header and licence
  are in `tools/nvda/`, its DLL is not; a release ships the DLL unchanged, with
  `tools/nvda/license_nvda_controllerclient.txt`.
- **Paradox Interactive** — Crusader Kings III and its engine. No Paradox files are included.
- **The Accessible Crusades Discord** and `github.com/Molitvan/blind-accessible-games-list`, where this
  work is found, tested and argued about — and where the line "read the game, never rebuild it" comes
  from.
- Built with **Claude** (Anthropic) as a working partner throughout.
