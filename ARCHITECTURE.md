# Architecture

Four layers, deliberately separated. The boundaries are where the maintenance cost lives, so they
are drawn where a game patch is most likely to hit.

## 1. The channel — `dll/channel.cpp`

A DLL injected into `ck3.exe`. It exposes a handful of primitives over a named pipe: read memory,
read many addresses at once, walk the widget tree from a root, post a mouse click, post a key, post
a character. That is all. It does **not** know what a county is, and it contains no speech.

**Why it stays thin.** Every change to the DLL costs a game restart of several minutes. While the
interface is still being mapped, that is the most expensive second in the project. Logic that can
live in Python lives in Python.

**One rule for anything added here:** a limit either grows or announces itself, never silently. The
costliest bug in this project was a tree walk that stopped at 20,000 nodes and dropped children
without a word, which made "that is not in the tree" unreliable for weeks.

## 2. Derivation — `tools/ck3/derive.py`

Nothing about memory layout is hard-coded. On every start, the widget vtables are located through
the RTTI tree in the executable, and nine field offsets are derived from the running process and
re-verified: parent, children, count, position, size, name and text, which come out of a single
reading of memory, plus alpha and the window flag, which do not. Those last two are ordinary
numbers whose meaning only shows when the state changes, so they are derived by changing it —
opening a window and requiring that both flip there and back while a window that stays shut does
not move. If verification fails, everything is derived again.

This is the layer that survives patches. Field offsets move between builds; between 1.16 and 1.19
one of the seven layout offsets moved and the other six did not. Nothing downstream needs to care.

Screen geometry lives here too: five windows scale a full-screen container, and whether the
centring correction applies on an axis is read from `parentanchor` in the game's own `.gui` files
rather than from a table maintained here.

## 3. Visibility — which of it is actually on screen

The game builds every window up front and keeps them all in the tree, so "it is in the tree" says
nothing about whether a player can see it. Three separate mechanisms decide that, and all three are
needed before a single word can honestly be read out:

- **A window flag** on the window object says whether it is drawn at all. Alpha alone does not:
  windows sit at alpha 1 without being drawn, and a window lying over another leaves the alpha of
  what is underneath untouched.
- **Alpha along the whole parent chain**, not on the widget itself. A text box can report alpha 1
  while an ancestor sits at 0, and then there is nothing there.
- **Sibling draw order** decides which of several drawn windows is on top. Siblings are drawn in
  list order, so the path of sibling indices from the root ranks them. Without this the tooling
  reads the wrong event when two are stacked, which is not a hypothetical: it happened.

## 4. Input — posted inward, and taken before the game sees it

Two directions, and only the first one belongs to the product.

**Receiving.** The DLL hooks the game's window procedure and can swallow keys before the game acts
on them. That is how the finished thing has to work: the reader owns the arrow keys, and vanilla
keeps the rest. A system-wide hook from Python could do it too, but it would see every key on the
machine and need its own rules for when not to interfere; a hook in the game's own window procedure
sees only what was meant for the game, and that filter comes free.

**Sending.** Mouse and key messages are posted into the process, so the game never needs focus and
the player's screen stays theirs. The product does not do this; it is how the game gets driven while
the interface is still being mapped.

**A posted click lands on whatever is topmost at that point, not on the widget you aimed at.** The
tree tells you a widget is drawn and where it is; it does not tell you what is drawn over it. So a
click is a measurement with a witness, never an assumption: press, read the drawn set, put the state
back, and record the point along with the result. `tools/ck3/openers.py` works that way.

**A modifier key cannot be sent inward, and that is a Windows boundary rather than a gap here.** A
key message carries no modifier information, and this game asks for the state through raw input,
straight from the device, where posted messages never arrive. Measured by hooking `GetKeyState`,
`GetAsyncKeyState` and `GetKeyboardState` with a counter on each: a keypress moves none of them. The
hooks were reverted. Note the limit — only the executable's import table was patched, so a call from
another loaded module would not have been counted.

Nothing needs it: of 705 bindings that use a modifier, exactly one opens a window, and that window
has an ordinary button. If it is ever required, three routes remain — hooking `GetRawInputData` and
answering a self-posted `WM_INPUT`, locating the engine's own key table in memory, or `SendInput`,
which works but takes the foreground and therefore the screen.

**Receiving is complete; sending is a research convenience.** The product never sends a key — it
intercepts one and acts on it itself. The asymmetry above therefore does not touch the product.



## 5. Reading the game

Three independent sources, and their disagreement is the test.

- **The widget tree** gives structure, names, rectangles and text — what is on screen right now.
- **The `.gui` files** give meaning: which data function fills a widget, which localisation key it
  carries, which tooltip hangs on it. `tools/ck3/guimap.py` parses the format properly rather than
  matching lines: the three layers plus the active mods are merged in load order, every `type` and
  `template` is collected into one global table, and a window is expanded with inheritance, `using`
  mixins and named slots resolved. This runs off disk with no game in sight.
- **The save file** (uncompressed, plain text) gives the ground truth to check against.
- **Optical character recognition** exists only as a witness, never as the product. If the tree says
  a word is at x=262 and the recogniser reads it at x=262, the geometry is right.

Nothing is copied from any of them.

**The first two are joined by structure, not by name.** `tools/ck3/pairing.py` lays the expanded
tree from disk against the harvested tree on class and child order, so the meaning in the files can
be attached to a widget that carries no name — and three widgets in four carry none. Names are kept
out of the alignment on purpose, which leaves them free to score it: they come out right 98.4 per
cent of the time. The alignment has to allow a template row on disk to become many live rows,
because that is what a data model does, and a widget on disk that the game never built.

**Three things about the gui format that a line-based reader gets wrong.** Load order carries
meaning, because the last definition of a template wins — sorting the file list loses a mod that
redefines a vanilla template. `block "x"` and `block = "x"` both occur. And a tooltip contains
widgets that have tooltips of their own, without end: the engine builds one only when the pointer
arrives, so on disk the definition is allowed to be circular and the expansion has to stop there.

## 6. Presentation — not built yet

What gets spoken, in what order, and what is left out. This is the layer that decides whether the
result is usable, and it is the one place where measurement cannot answer the question.

Two rules are fixed: output is not sorted by screen position (that is a sighted reader's order), and
one keystroke produces one unit of speech plus braille.

**A third rule was fixed and has since been withdrawn.** It said a widget is addressed by name. The
intent stands — an index among siblings breaks the moment a mod adds a row inside a vanilla window —
but only about a quarter of the widgets that carry text have a name, and a name is not unique within
a window either.

What replaces it: the engine builds a widget's children in the order the `.gui` file lists them and
keeps them in that order, so the expanded tree from disk can be aligned with the live tree
structurally, anchored on the names that are there. Every unnamed text box has a named ancestor,
usually one or two steps up. Building that alignment is the next piece of work.

**That order lives in exactly one place.** The channel walks each child list in the engine's own
order and the tree reader keeps the lines that way; the parent offset says who the parent is and
never in which place. A pass that sorts the children destroys the only copy — which has happened.

## Speech — `tools/nvda/speech.py`

One function: text, braille text, mode. Behind it, the official NVDA controller client. Keeping
that seam thin is deliberate: swapping in an abstraction layer such as Prism or SRAL to support
other screen readers should be a day's work, not a rebuild.

## What is deliberately not done

- No decompiling or rebuilding the engine. Reading memory and reading data files is ordinary
  modding; rebuilding the engine is not, and it would put every accessibility mod for these games
  at risk.
- No redistribution of game files.
- No driving the game from outside with synthetic input at the OS level. Input is posted into the
  process, so the game never needs focus and the player's screen stays theirs.
- No hard-coded memory addresses, field offsets or click positions. All three are derived.
