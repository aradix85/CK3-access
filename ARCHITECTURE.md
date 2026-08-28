# Architecture

Six parts, separated where the maintenance cost lives — that is, where a game patch is most likely
to hit.

**Where this is heading, because it decides where new code belongs.** For a real user, installing
has to mean one DLL, the NVDA controller client beside it, and a launch option in Steam: no Python,
no paths. So the logic moves inside the DLL in the end. It is thin today because the interface is
still being mapped and every DLL change costs a multi-minute restart. Move something inward when a
measurement says it pays, not before, and keep tuning in a data file the DLL reads rather than in
C++.

**Two things never move inward.** Speech and braille stay outside: moving them wins under a
per-mille and costs NVDA's library inside the game process. Receiving keys stays inside — section 4.

## 1. The channel — `dll/channel.cpp`

A DLL injected into `ck3.exe`, exposing a handful of primitives over a named pipe: read memory, read
many addresses at once, walk the widget tree from a root, post a click, post a key, post a
character. That is all. It does **not** know what a county is, and it contains no speech.

**Python on the other side is fast enough, and that is measured.** NVDA is itself a Python program
handling every keystroke on the machine; this side sends one question down a pipe and turns a few
kilobytes into text. Two rules keep it there: let the DLL walk the tree and return a compact answer
rather than raw bytes, and react to keys and events instead of walking the tree every frame.

**Measure before making the DLL faster.** Re-checking the derivation once took 122 seconds, nearly
all of it the Python side polling in fixed steps; a growing wait made it 3 seconds without a line of
C++.

**One rule for anything added here:** a limit either grows or announces itself, never silently. The
costliest bug in this project was a tree walk that stopped at 20,000 nodes and dropped children
without a word.

## 2. Derivation — `tools/ck3/derive.py`

Nothing about memory layout is hard-coded. At every start the widget vtables are located through the
RTTI tree in the executable, and nine field offsets are derived from the running process and
re-verified. Seven — parent, children, count, position, size, name, text — come out of a single read
of memory. Alpha and the window flag do not: their meaning only shows when the state changes, so
they are derived by changing it, opening a window and requiring both to flip there and back while a
window that stays shut does not move. If verification fails, everything is derived again.

This is the layer that survives patches: between 1.16 and 1.19 one of the seven moved and the other
six did not. Nothing downstream needs to care.

Screen geometry lives here too. Five windows scale a full-screen container, and whether the centring
correction applies on an axis is read from `parentanchor` in the game's own `.gui` files rather than
from a table maintained here.

## 3. Visibility — which of it is actually on screen

The game builds every window up front and keeps them all in the tree, so "it is in the tree" says
nothing about whether a player can see it. Three mechanisms decide that, and all three are needed
before a single word can honestly be read out:

- **A window flag** says whether a window is drawn at all. Alpha does not: windows sit at alpha 1
  without being drawn.
- **Alpha along the whole parent chain**, not on the widget itself. A text box can report alpha 1
  while an ancestor sits at 0, and then there is nothing there.
- **Sibling draw order** decides which of several drawn windows is on top. Siblings are drawn in
  list order, so the path of sibling indices from the root ranks them. Without this the tooling
  reads the wrong event when two are stacked, which is not hypothetical.

Anything that clicks needs the flag as well as the alpha: a widget can pass every alpha and geometry
test and still sit inside a window that is shut, and the click then lands on the map.

## 4. Input — posted inward, and taken before the game sees it

**Receiving.** The DLL hooks the game's window procedure and can swallow keys before the game acts
on them. That is how the finished thing has to work: the reader owns the arrow keys, and vanilla
keeps the rest. A system-wide hook from Python would see every key on the machine and need its own
rules for when not to interfere; a hook in the game's own window procedure sees only what was meant
for the game, and that filter comes free.

**Sending.** Mouse and key messages are posted into the process, so the game never needs focus and
the player's screen stays theirs. The product does not do this; it is how the game gets driven while
the interface is still being mapped.

**A posted click lands on whatever is topmost at that point, not on the widget you aimed at.** The
tree says a widget is drawn and where; it does not say what is drawn over it. So a click is a
measurement with a witness, never an assumption: press, read the drawn set, put the state back, and
record the point along with the result. `tools/ck3/openers.py` works that way.

**A modifier key cannot be sent inward, and that is a Windows boundary rather than a gap here.** A
key message carries no modifier information, and this game reads the state through raw input, where
posted messages never arrive. Nothing needs it: of 705 bindings that use a modifier, exactly one
opens a window, and that window has an ordinary button. It does not touch the product either, which
never sends a key — it intercepts one and acts on it itself.

## 5. Reading the game

Four independent sources, and their disagreement is the test.

- **The widget tree** — structure, names, rectangles and text: what is on screen right now.
- **The `.gui` files** — meaning: which data function fills a widget, which localisation key it
  carries, which tooltip hangs on it. `tools/ck3/guimap.py` parses the format properly rather than
  matching lines, merging the three engine layers and the active mods in load order and expanding a
  window with inheritance, `using` mixins and named slots resolved. This needs no game running.
- **The save file**, plain text once uncompressed — the ground truth to check against, and where the
  engine's own numbering of cultures, faiths and traits is written down.
- **The static data files** — province positions and adjacency, the de jure hierarchy, traits — hold
  everything that does not change during a game, with no reverse engineering at all.
  `tools/ck3/database.py` reads them the way the engine merges them, so a number out of memory
  becomes the name a player sees. The map side of this is not built yet.

Optical character recognition sits beside these as a witness, never as the product: if the tree says
a word is at x=262 and the recogniser reads it there, the geometry is right. Nothing is copied from
any of them.

**A window has to be opened the way a player opens it, or the first source is half empty.** The
console builds any window on demand, which is what makes coverage independent of who is playing, but
it hands over the shape and the captions and no data context: 7.4 text boxes per window against 23.7
through a shortcut and 36.3 through a click. None of the twelve console commands supplies a context.
So structure is collected the cheap way and data the slow way, and `tools/ck3/harvest.py` knows all
three routes.

**The first two sources are joined by structure, not by name.** `tools/ck3/pairing.py` lays the
expanded tree from disk against the harvested tree on class and child order, so meaning reaches a
widget carrying no name — three in four carry none. Names are kept out of the alignment on purpose,
which leaves them free to score it: 98.4 per cent land right. The alignment has to allow one
template row on disk to become many live rows, because that is what a data model does.

**Numbering is read rather than derived, because it is not one rule:** cultures come out in exactly
the file order, faiths only once grouped per religion, traits diverge where mods add theirs.

**Three things about the gui format that a line-based reader gets wrong.** Load order carries
meaning, because the last definition of a template wins — sorting the file list loses a mod that
redefines a vanilla template. `block "x"` and `block = "x"` both occur. And a tooltip contains
widgets that have tooltips of their own, without end: the engine builds one only on hover, so on
disk the definition is allowed to be circular and the expansion has to stop there.

## 6. Presentation — not built yet

What gets spoken, in what order, and what is left out. This decides whether the result is usable,
and it is the one place where measurement cannot answer the question.

Two rules are fixed: output is not sorted by screen position, which is a sighted reader's order; and
one keystroke produces one unit of speech plus braille. It belongs in data rather than in code —
this is the layer that changes most and the one a user will want to tune for herself.

**A third rule was fixed and has since been withdrawn.** It said a widget is addressed by name. The
intent stands, since an index among siblings breaks the moment a mod adds a row inside a vanilla
window, but only a quarter of the widgets that carry text have a name, and a name is not unique
within a window either. The structural alignment in section 5 replaces it.

**Draw order lives in exactly one place.** The channel walks each child list in the engine's own
order and the tree reader keeps the lines that way; the parent offset says who the parent is and
never in which place. A pass that sorts the children destroys the only copy — which has happened.

## Speech — `tools/nvda/speech.py`

One function: text, braille text, mode. **Braille is never optional** — leave it out and the spoken
text goes to the display, because a seam a caller can forget one channel in loses that channel
eventually. Behind it, the official NVDA controller client rather than Tolk, which passes plain text
only and has not been updated in years. **It is LGPL 2.1, so it must be linked dynamically and
shipped unchanged — do not bake it in statically.**

Two modes are enough, replace and queue. Priority-with-resume was rejected: it interrupts and then
carries on with the old sentence, which feels as though nothing happened. Keeping the seam thin is
deliberate — swapping in an abstraction layer such as Prism or SRAL for other screen readers should
be a day's work, not a rebuild.

## What is deliberately not done

- No decompiling or rebuilding the engine. Reading memory and reading data files is ordinary
  modding; rebuilding the engine is not, and it would put every accessibility mod for these games
  at risk.
- No redistribution of game files.
- No driving the game from outside with synthetic input at the OS level.
- No hard-coded memory addresses, field offsets or click positions. All three are derived.
