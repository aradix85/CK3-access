# Architecture

Seven parts, split where a game patch is most likely to hit.

| | Part | What it is for |
|---|---|---|
| 1 | **The channel** — `dll/channel.cpp` | a few primitives over a pipe; knows nothing about the game |
| 2 | **Derivation** — `tools/ck3/derive.py` | finds every memory offset again at each start |
| 3 | **Visibility** | what of the tree is really on screen, and which window lies on top |
| 4 | **Input** | keys taken before the game sees them; clicks and keys posted inward |
| 5 | **Reading the game** | five independent sources; their disagreement is the test |
| 6 | **Presentation** — `screens/`, `tools/ck3/reading.py`, `tools/ck3/reader.py` | what gets said, in what order, on which key |
| 7 | **Speech** — `tools/nvda/speech.py` | one seam to NVDA, speech and braille together |

**Direction:** installing should end up as one DLL, the NVDA controller client beside it, and a
launch option — no Python. So logic moves into the DLL when a measurement says it pays. Speech and
braille stay outside; receiving keys stays inside.

## 1. The channel

An injected DLL exposing primitives over a named pipe: read memory, walk the widget tree, post a
click, a key, a character or a key combination. It contains no game knowledge and no speech.
- Tested without the game: `tests/test_channel.py` drives every command through the real pipe
  against a fake widget tree, also under AddressSanitizer. The build stops on any warning.
- A limit either grows or announces itself, never silently.
- **The pipe is a workbench, not a product.** A released build is compiled without it; the DLL never
  opens a network connection.

## 2. Derivation

No memory layout is hard-coded. Widget vtables come from the RTTI in the executable; nine field
offsets are derived from the running game and rechecked at each start, and derived again if a check
fails. Between 1.16 and 1.19 one offset moved; nothing downstream noticed.

## 3. Visibility

Every window is built up front and stays in the tree, so being in the tree says nothing. What decides
whether something is drawn:
- **A state byte**, along the parent chain: 0x08 means hidden. On a window, zero means drawn; other
  values are being measured again, since a drawn planner carried 0x20. On a button, low bits mean
  switched off.
- **Alpha** along the parent chain.
- **Clipping** by the nearest scroll area.
- **Geometry:** some windows place drawn buttons outside the drawing area at any resolution, so the
  product must say when a button cannot be reached.

Which drawn window is on top follows sibling draw order. A click needs all of this, or it lands on
whatever lies underneath.

## 4. Input

- **Receiving:** the DLL hooks the game's window procedure and swallows the keys the reader owns.
- **Sending:** mouse and key messages are posted into the process, so the player's screen is never
  taken. The product never sends keys; this is for mapping the interface.
- **A posted click lands on what is topmost at that point.** A click is therefore a measurement: press,
  read what is drawn, put the state back (`tools/ck3/openers.py`).
- **Modifiers:** a posted key carries no modifier state, so `combo` holds the modifier for the game
  while the combination runs. `tools/ck3/modifiers.py` is the measurement with real keys it was
  checked against.

## 5. Reading the game

- **The widget tree** — names, rectangles, text: what is on screen now.
- **The game model** — the same values raw. `tools/ck3/anchor.py` reaches the databases,
  `tools/ck3/model.py` derives the character record, `tools/ck3/numbering.py` maps numbers to keys,
  `tools/ck3/calibrate.py` checks four hundred characters against a save.
- **The `.gui` files** — meaning: which data function fills a widget. `tools/ck3/guimap.py` parses
  them properly, layers and mods merged in load order.
- **The save** — ground truth, valid only for the state that wrote it.
- **The static data files** — `tools/ck3/database.py` and `tools/ck3/mapdata.py`.

Text recognition (`tools/ocr.py`) is a witness, never the product.

**Open a window the way a player does.** The console builds any window but hands over no data context,
so it yields captions without values. **Check the window map against the game**, not the files:
`windowmap.unmapped` lists what the engine built that the map lacks. **The chain** reaches windows that
wait on a state: open one window, press what the files say reaches the target (`openers.py --chain`).

**The tree and the files are joined by structure, not by name** (`tools/ck3/pairing.py`), because most
widgets that show text have no name. Things a line-based gui reader gets wrong: the last definition
wins, also for a second `onclick` in the same block; `block "x"` and `block = "x"` both occur; tooltips
nest without end; and a scroll area draws its scrollbar last whatever the file says.

## 6. Presentation

Not sorted by screen position; one keystroke gives one unit of speech plus braille.
`tools/ck3/reader.py` claims up, down, F12 and Delete and gives every key back on the way out. An event
is noticed through the child count of the layer that holds events.

**Screen files** under `screens/` hold exceptions only, in the game's own format; whatever they do not
name is read in gui-file order, so a stale file costs detail, never the screen. `tools/ck3/screens.py`
checks every reference against the expanded gui tree. Two blocks are applied: `order` and `key`.

## 7. Speech

Two functions: `output(text, mode, braille)` and `failure(where, what, remedy)`.
- **Braille is never optional;** a different braille text needs a reason at the call site.
- The official NVDA controller client, not Tolk. LGPL 2.1: link dynamically, ship unchanged.
- Two modes, replace and queue.
- **Nothing speaks when there is nothing to say.** Only a real fault speaks, as one sentence a player
  can act on. `tools/never_silent.py` is the proof and the gate in front of a beta.

## Deliberately not done

- No decompiling or rebuilding the engine; no redistribution of game files.
- No synthetic input from outside the process.
- No hard-coded addresses, offsets or click positions.
