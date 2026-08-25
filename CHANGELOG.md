# Changelog

Dates are the day the work was measured, not the day it was committed.

## 2026-08-25

**The sweep was blind on the left third of the screen and nothing said so.** Coupling the text
recogniser to the widget tree on text and overlap produced a confirmation rate that varied by
position rather than by window: 7 percent in the strip from x 0 to 200, 23 percent from 200 to 400,
then 84, 80, 85, 78, 72 and 64. The debug console had stood open over that area for the whole round.
The tree does not notice a window being covered, so the capture half was worthless exactly where it
mattered most — `character_window` had 0 of its 33 text boxes confirmed. The console is now shut for
the length of every capture, and each record carries how many of its own text boxes the recogniser
read back, so a blind capture shows up in the first ten windows instead of a day later. Same rule,
same 178 windows: **1169 of 1415 confirmed against 1009 of 1416**, median window 88 to 100 percent.

**Two documented quirks of the game were ours.** `strip_markup` matched a markup code up to the next
space, so where two codes stand back to back it ate the separator between them. Over the 1466 texts
in the sweep, 117 came out with words glued together and a colon that is on screen disappeared from
the widget text. Both had been written down as engine behaviour. There is also a second markup byte,
0x16 for icons, which was not stripped at all: 53 texts carry one, 11 distinct icons, `warning_icon`
and `gold_icon` leading. The new rule was judged three ways — 179 texts found literally in the
localisation against 175, 883 text boxes confirmed against 871, and no change on the 1296 texts that
carry no two codes in a row.

**A test with a side effect.** Whether the console was open used to be settled by clicking into its
input field and typing. That is reliable while it stands open and a stray click into the game when it
does not — on this state it opened the character window, and the sweep refused to start because a
window was already open. It now reads the flag byte of `console_window`, which is 0x00 with a
427x838 frame when open and 0x18 with an empty frame when shut, confirmed against the recogniser.

**Field verification needs a loaded game.** On the main menu the position check cannot find the
hundred distinct values it requires, rejects a perfectly good stored derivation, and then spends
seven minutes deriving again only to fail on the same requirement.

**`check.py` now recomputes the quality of a sweep**, not just file sizes: windows opened, text boxes
that should be on screen, and how many of them the recogniser confirmed.

**`tools/ck3/openers.py`: which button opens which window, measured rather than read.** The gui files
say which *view* an onclick opens, but nothing on disk binds a view to a window - the known view
names appear in the 515 files only as texture paths, widget names and tooltip names. So the round
presses the button and watches the drawn set. Of 56 buttons that open a window and do nothing else,
19 could be pressed; 17 opened a window and the state came back every time. The right-hand tab
column is right eight times out of eight; the bottom row is context-dependent and falls through to
the character window. A second pass opens a window first and looks inside it, which is what makes a
name usable - in the whole tree one of them occurs 160 times, inside one window almost never twice -
but it only adds two more buttons: the rest are not one layer down, they are behind chains of
windows. Result in `reports/openers.json`, with the box and the point clicked, because otherwise a
click that landed elsewhere cannot be told from a wrong prediction.


**Attributing a trigger to a widget has exactly one correct rule.** A trigger belongs to the widget
whose name sits one level above it with a `blockoverride` in between - that is template filling, not
a child widget. Taking the nearest named ancestor instead hangs the call on the container around the
button, and the middle of a container is not the button: nine clicks landed on the portrait and one
on the speed bar, which started the clock and moved the state seven months. Requiring the same block
loses all eight main tabs. There are also two mechanisms, `onclick` and `shortcut = "<window>"`, and
reading only one throws away half the buttons.

**A modifier cannot be sent into the game, and the channel is unchanged because of it.** Three
routes, each measured. Posting shift as its own message did nothing — a key message carries no
modifier information, so an application that cares asks separately. Hooking the two functions that
answer that question, `GetKeyState` and `GetAsyncKeyState`, in the executable's import table, and
`GetKeyboardState` alongside them: the hooks demonstrably landed and changed nothing. A counter on
each hook then settled it — a keypress moves none of them. The game reads raw input straight from
the device, which matches the `RegisterRawInputDevices` and `GetRawInputData` it imports. Everything
was reverted, and the DLL is byte for byte back at its previous size. The limit of that measurement
is written down too: only the executable's import table was patched, so a call from another module
would not have been counted. It turned out not to matter — of 705 bindings that use a modifier,
exactly one opens a window, and that window has an ordinary button that was in the click round all
along, skipped because it had no size at that moment.



**`check.py` now verifies bare file names as well, and that closed a real hole.** It only looked at
names with a folder in front of them, so a document could promise a `.bat` on the desktop that
restored the launcher — tested, with an agreement that the user would hear it fail — while no such
file existed and he had never asked for one. Nothing caught it for a month. A name ending in an
extension this project writes now has to exist somewhere under the project, which needs one
convention to be usable: backticks mean the thing exists, and a removed file is named in plain text.
Without that the check reported ten deliberate mentions beside one real problem. 297 names are
verified where 260 were before, and the check was tested by planting the failure it was built for.

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
