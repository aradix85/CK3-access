# Architecture

Six parts, deliberately separated. The boundaries are drawn where the maintenance cost lives — that
is, where a game patch is most likely to hit.

**Where this is heading, because it decides where new code belongs.** For a real user, installing
has to mean putting down one DLL, the NVDA controller client beside it, and a launch option in
Steam: no Python, no environment, no paths. So the logic moves inside the DLL in the end. It is
thin today because the interface is still being mapped and every DLL change costs a game restart of
several minutes. Move something inward when a measurement says it pays or when distribution demands
it, not before, and keep tuning in a data file the DLL reads rather than in C++ so it can be
changed without recompiling.

**Two things never move inward.** Speech and braille stay outside: moving them wins under a
per-mille and costs NVDA's library inside the game process plus a game thread waiting on another
program. And receiving keys stays inside — see section 4.

## 1. The channel — `dll/channel.cpp`

A DLL injected into `ck3.exe`. It exposes a handful of primitives over a named pipe: read memory,
read many addresses at once, walk the widget tree from a root, post a mouse click, post a key, post
a character. That is all. It does **not** know what a county is, and it contains no speech.

**Python on the other side is fast enough, and that is measured rather than hoped.** NVDA is itself
a Python program that handles every keystroke on the machine; this side sends one question down a
pipe and turns a few kilobytes into text, orders of magnitude under the tenth of a second a screen
reader may cost. Two rules keep it there: let the DLL walk the tree and return a compact answer
rather than raw bytes, and react to keys and events instead of walking the whole tree every frame.

**Measure before making the DLL faster.** Re-checking the derivation once took 122 seconds, and
nearly all of it was the Python side polling in ten-millisecond steps; a growing wait made it 3
seconds without a line of C++. A multi-minute restart for a second and a half is a bad trade.

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
key message carries no modifier information, and this game reads the state through raw input, where
posted messages never arrive — measured by counting calls to `GetKeyState`, `GetAsyncKeyState` and
`GetKeyboardState`, none of which a posted keypress moves. Nothing needs it: of 705 bindings that
use a modifier, exactly one opens a window, and that window has an ordinary button. It does not
touch the product either, which never sends a key — it intercepts one and acts on it itself.

If it is ever needed, three routes remain: hook `GetRawInputData` and answer a self-posted
`WM_INPUT`; find the engine's own key table in memory by taking two snapshots while the key is held
and watching which byte flips; or `SendInput`, which certainly works but takes the foreground and
therefore the player's screen. Note the limit on the measurement above — only the executable's
import table was patched, so a call from another loaded module would not have been counted.

## 5. Reading the game

Four independent sources, and their disagreement is the test.

- **The widget tree** gives structure, names, rectangles and text — what is on screen right now.
- **The `.gui` files** give meaning: which data function fills a widget, which localisation key it
  carries, which tooltip hangs on it. `tools/ck3/guimap.py` parses the format properly rather than
  matching lines: the three layers plus the active mods are merged in load order, every `type` and
  `template` is collected into one global table, and a window is expanded with inheritance, `using`
  mixins and named slots resolved. This runs off disk with no game in sight.
- **The save file** (uncompressed, plain text) gives the ground truth to check against.
- **The game's static data files** — province positions and adjacency, the de jure hierarchy,
  building types, traits — give everything that does not change during a game, and so give
  distances, compass directions and title chains without any reverse engineering at all.
  `tools/ck3/database.py` reads the culture, faith, religion and trait databases the way the engine
  merges them, so a number out of memory becomes the name a player sees. The map side of this layer
  is not built yet.
- **Optical character recognition** exists only as a witness, never as the product. If the tree says
  a word is at x=262 and the recogniser reads it at x=262, the geometry is right.

Nothing is copied from any of them.

**The first two are joined by structure, not by name.** `tools/ck3/pairing.py` lays the expanded
tree from disk against the harvested tree on class and child order, so the meaning in the files can
be attached to a widget that carries no name — and three widgets in four carry none. Names are kept
out of the alignment on purpose, which leaves them free to score it: they come out right 98.4 per
cent of the time. The alignment has to allow a template row on disk to become many live rows,
because that is what a data model does, and a widget on disk that the game never built.

**The save file is also where the numbering comes from.** A number in memory where the game means a
culture or a faith is an index into a database the engine loaded, and the engine writes those lists
into every save. That is read rather than derived, because it is not one rule: cultures come out in
exactly the file order, all 463 of them, while faiths are grouped per religion and traits diverge
where mods add theirs. A rule that holds for one database and not the next is worth knowing about
before it is trusted.

**Three things about the gui format that a line-based reader gets wrong.** Load order carries
meaning, because the last definition of a template wins — sorting the file list loses a mod that
redefines a vanilla template. `block "x"` and `block = "x"` both occur. And a tooltip contains
widgets that have tooltips of their own, without end: the engine builds one only when the pointer
arrives, so on disk the definition is allowed to be circular and the expansion has to stop there.

## 6. Presentation — not built yet

What gets spoken, in what order, and what is left out. This is the layer that decides whether the
result is usable, and it is the one place where measurement cannot answer the question.

Two rules are fixed: output is not sorted by screen position (that is a sighted reader's order), and
one keystroke produces one unit of speech plus braille. It belongs in data rather than in code —
this is the layer that changes most and the one a user will want to tune for herself.

**A third rule was fixed and has since been withdrawn.** It said a widget is addressed by name. The
intent stands — an index among siblings breaks the moment a mod adds a row inside a vanilla window —
but only a quarter of the widgets that carry text have a name, and a name is not unique within a
window either. The structural alignment in section 5 replaces it, anchored on the names that are
there: every unnamed text box has a named ancestor a step or two up.

**That order lives in exactly one place.** The channel walks each child list in the engine's own
order and the tree reader keeps the lines that way; the parent offset says who the parent is and
never in which place. A pass that sorts the children destroys the only copy — which has happened.

## Speech — `tools/nvda/speech.py`

One function: text, braille text, mode. **Braille is never optional**: leave it out and the spoken
text goes to the display, because there is no call that only speaks. A seam that lets a caller
forget one channel loses that channel eventually, which is how the Fallout 4 accessibility mod
ended up with a braille backend it never called. Behind it, the official NVDA controller client
rather than Tolk, which passes plain text only and has not been updated in years; the official
client also
carries braille, SSML with prosody and pauses, symbol level and priority. **It is LGPL 2.1, so it
must be linked dynamically and shipped unchanged — do not bake it in statically.**

Two modes are enough, replace and queue. Priority-with-resume was considered and rejected: it
interrupts and then carries on with the old sentence, which feels as though nothing happened.

Keeping that seam thin is deliberate: swapping in an abstraction layer such as Prism or SRAL to
support other screen readers should be a day's work, not a rebuild.

## What is deliberately not done

- No decompiling or rebuilding the engine. Reading memory and reading data files is ordinary
  modding; rebuilding the engine is not, and it would put every accessibility mod for these games
  at risk.
- No redistribution of game files.
- No driving the game from outside with synthetic input at the OS level. Input is posted into the
  process, so the game never needs focus and the player's screen stays theirs.
- No hard-coded memory addresses, field offsets or click positions. All three are derived.
