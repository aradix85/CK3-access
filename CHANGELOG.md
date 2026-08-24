# Changelog

Dates are the day the work was measured, not the day it was committed.

## 2026-08-24

**Everything public is English.** 22 Python files and 749 lines of C++: names, comments, messages,
the channel protocol, the keys in `reports/`. The pipe is now `\\.\pipe\ck3_access`.

**Two more derived fields.** Alpha and the window flag were constants nothing rechecked. They cannot
be derived from one reading of memory, so the derivation changes the state instead: open a window,
require one byte to go to zero and one float to 1.0, both to return on closing, and a window that
stays shut to move on neither. Six seconds, and it lands on the values that were hard-coded.

**Position was derived from the wrong population.** A full memory scan also sees widget objects that
hang off the live tree, and those keep stale coordinates, so the offset came out differently per
game state and nothing noticed. It is re-derived from the tree now (eight seconds), and `verify`
checks it at every start.

**Scrolled lists are a third visibility mechanism.** A row scrolled out of view keeps alpha 1.0.
`derive.is_clipped` decides it on the box of the nearest scroll area.

**A missing scale is a hard stop.** It used to default to 1.0, which put everything under a scaled
container 110 points off. Main menu with the scale in play: 16 of 21 text boxes confirmed against
the recogniser, and no remaining error is geometric.

**`tools/ck3/harvest.py`, phase 1 of the sweep.** Per window: open it, wait for the flag, record the
subtree with every field, capture it, run the recogniser over it, close it, check the state comes
back. Four stop conditions, resumable. 178 windows and 68,146 widgets in an hour. Two traps worth
knowing: `GUI.CreateWidget` builds a *new* window object while the parked one keeps its name, so the
drawn one has to be picked explicitly; and a window opened from the console carries its fixed labels
but not its data, because it has no data context.

**An event creates a new window object** rather than flipping a parked one, so nothing can watch a
fixed address for it. Reading the flag of a few windows costs a millisecond, so a cheap poll with an
expensive check behind it is enough.

**Hovering cannot be provoked from outside the process.** Posted mouse messages, `SetCursorPos` with
the game in front and behind, a 24-point grid, `SendInput` at device level: the tree never moves and
no hover highlight is drawn, while clicks and keys keep working. That settles that the game does not
see our cursor - not that tooltips live outside the widget tree.

**Housekeeping.** `requirements.txt`; a README section on building the DLL and starting the game;
the antivirus warning an injector owes its users; visibility and input added to `ARCHITECTURE.md`;
`check.py` also verifies that every path named in the documentation exists. Reports no longer carry
the game's own text or one machine's paths.

## 2026-08-23 — first public source

Not a release. There is no installable mod and nothing is spoken during normal play. What is here
is the machinery, and every claim below was measured on Crusader Kings III **1.19.0.6** with all 29
DLC and five content mods loaded.

### Reading the game

- Injected channel answers ~25 seconds after launch; the main menu is readable about four minutes in.
- Seven memory field offsets are derived from the running process at every start and re-verified.
  Verification took 1.2 to 17.9 seconds across four runs — it fluctuates, so nothing depends on it
  being fast. Tested on build 1.16.2: one of the seven had moved, and it re-derived itself.
- Widget tree: 2,437 nodes on the main menu (0.04 s), ~83,000 in a loaded game (~2.3 s).
- Visibility solved: a window flag says whether a window is drawn; sibling draw order says which of
  several drawn windows is on top. The stacking rule was verified against a stack of five event
  windows, with a screenshot as an independent witness.
- Screen geometry solved, including the five windows that scale a full-screen container. Whether
  the centring correction applies on an axis is read from `parentanchor` in the game's own `.gui`
  files. Median error against the text recogniser: 0.5 points, worst 18.5, over 24 words.

### Driving the game

- Mouse clicks and keystrokes are posted into the process; the game never needs focus.
- An event can be read and answered end to end. Six in a row, across `character_event`,
  `fullscreen_event` and `letter_event`. Title, description and options come out of memory and match
  the localisation files on disk character for character — including text from a content mod.
- The developer console can be driven through the channel, which allows any window to be
  instantiated on demand for mapping purposes. Research tooling only; debug mode is never required
  by the product.

### Mapping

- `reports/windows.json`: 197 windows found on disk, 196 opened on demand, 177 drawn, 9 reachable
  by function key, all 196 cleaned up afterwards. Regenerate with `tools/ck3/windowmap.py`.
- `reports/claims.json`: numbers with counting rules, re-checked against disk by
  `tools/check.py`.

### Speech

- NVDA speech and braille work, through the official controller client. The client DLL is not
  included in this repository; download it from `download.nvaccess.org` (see `tools/nvda/`).

### Not done

No presentation layer — nothing decides what to say or in what order. No installer, no launcher
hook, no support for screen readers other than NVDA.
