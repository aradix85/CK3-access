# Architecture

Seven parts, split where a game patch is most likely to hit.

| | Part | What it is for |
|---|---|---|
| 1 | **The channel** — `dll/channel.cpp` | a few primitives over a pipe; knows nothing about the game |
| 2 | **Derivation** — `tools/ck3/derive.py` | finds every memory offset again at each start |
| 3 | **Visibility** | which of the tree is really on screen; four mechanisms, all needed |
| 4 | **Input** | keys taken before the game sees them; clicks posted inward |
| 5 | **Reading the game** | five independent sources, and their disagreement is the test |
| 6 | **Presentation** | what gets said and in what order — not built yet |
| 7 | **Speech** — `tools/nvda/speech.py` | one seam to NVDA, speech and braille together |

**Where this is heading, because it decides where new code belongs.** Installing has to end up
meaning one DLL, the NVDA controller client beside it, and a launch option: no Python, no paths. So
the logic moves inside the DLL eventually. Move something inward when a measurement says it pays,
and keep tuning in a data file rather than in C++. Two things never move: speech and braille stay
outside, receiving keys stays inside.

## 1. The channel — `dll/channel.cpp`

A DLL injected into `ck3.exe`, exposing a handful of primitives over a named pipe: read memory, read
many addresses at once, walk the widget tree from a root, post a click, a key, a character. That is
all. It does not know what a county is, and it contains no speech.

Python on the other side is fast enough, and that is measured: re-checking the derivation once took
122 seconds, nearly all of it the Python side polling in fixed steps, and a growing wait made it 3
seconds without a line of C++. Two rules keep it there: let the DLL walk the tree and return a
compact answer rather than raw bytes, and react to keys and events instead of walking the tree every
frame.

**The pipe is a workbench, not a product.** It answers anything that can open it, and the primitives
add up to remote control plus arbitrary memory reads — right for mapping an interface, wrong to
ship, and in multiplayer a cheating tool. A released build carries no pipe. The DLL never opens a
network connection.

**One rule for anything added here:** a limit either grows or announces itself, never silently. The
costliest bug in this project was a tree walk that stopped at 20,000 nodes and dropped children
without a word.

## 2. Derivation — `tools/ck3/derive.py`

Nothing about memory layout is hard-coded. At every start the widget vtables are located through the
RTTI tree in the executable, and nine field offsets are derived from the running process and
re-verified. Seven — parent, children, count, position, size, name, text — come out of one read.
Alpha and the window flag do not: their meaning only shows when the state changes, so they are
derived by opening a window and requiring both to flip there and back while a window that stays shut
does not move. If verification fails, everything is derived again.

This is the layer that survives patches: between 1.16 and 1.19 one of the seven moved and the other
six did not. Nothing downstream needs to care.

## 3. Visibility — which of it is actually on screen

Every window is built up front and kept in the tree, so "it is in the tree" says nothing about
whether a player can see it. Four mechanisms decide that, and all four are needed:

- **A window flag** says whether a window is drawn at all. Alpha does not: windows sit at alpha 1
  without being drawn.
- **Alpha along the whole parent chain**, not on the widget itself.
- **Clipping.** A row scrolled past the end of its list keeps alpha 1 and a rectangle; what decides
  it is the frame of the nearest scroll area above it.
- **Geometry.** A widget can be laid outside the drawing area entirely — four tabs side by side at
  x1555 to x1690 on a screen 1600 wide, all at alpha 1, one of them visible.

Sibling draw order is a separate question and answers a different one: which of several drawn
windows is on top. Without it the tooling reads the wrong event when two are stacked.

Anything that clicks needs the flag as well as the alpha: a widget can pass every alpha and geometry
test and still sit inside a shut window, and the click then lands on the map.

## 4. Input — posted inward, and taken before the game sees it

**Receiving.** The DLL hooks the game's window procedure and can swallow keys before the game acts
on them. That is how the finished thing has to work: the reader owns the arrow keys, vanilla keeps
the rest. A hook in the game's own window procedure sees only what was meant for the game, and that
filter comes free.

**Sending.** Mouse and key messages are posted into the process, so the game never needs focus and
the player's screen stays theirs. The product does not do this; it is how the game gets driven while
the interface is being mapped.

**A posted click lands on whatever is topmost at that point, not on the widget you aimed at.** So a
click is a measurement with a witness, never an assumption: press, read the drawn set, put the state
back, record the point with the result. `tools/ck3/openers.py` works that way. What "topmost" means
is measured: the last-drawn button that carries an action of its own. A layout container catches
nothing, and a button with no action passes the click on to what is under it — ten of ten on the
ledger's category tabs, each of which is covered completely by such a button.

**A modifier key cannot be sent inward** — a key message carries no modifier state and the game
reads that through raw input. Nothing needs it: of 705 bindings using a modifier, one opens a
window, and that window has an ordinary button.

## 5. Reading the game

Five independent sources, and their disagreement is the test.

### The five sources

- **The widget tree** — structure, names, rectangles and text: what is on screen right now.
- **The game model in memory** — the same values raw, plus what no open window is showing.
  `tools/ck3/anchor.py` walks from a global in the executable to a database of the game state;
  `tools/ck3/model.py` derives what sits where inside a character record. No offset is written
  down. `tools/ck3/calibrate.py` holds four hundred characters against a save and names the field
  that disagrees. `tools/ck3/numbering.py` does the same walk for the culture, faith, religion and
  trait databases.
- **The `.gui` files** — meaning: which data function fills a widget, which localisation key it
  carries. `tools/ck3/guimap.py` parses the format properly rather than matching lines, merging the
  three engine layers and the active mods in load order. Needs no game running.
- **The save file**, plain text once uncompressed — the ground truth to check against. Two limits:
  a save belongs to the state that wrote it, so the numbering of cultures and faiths is read out of
  the running game instead; and the levies and military power are recomputed around loading, so the
  answer key has to be a save written from the state now loaded.
- **The static data files** — the de jure hierarchy, traits, and the map itself.
  `tools/ck3/database.py` reads them the way the engine merges them, so a number out of memory
  becomes the name a player sees; `tools/ck3/mapdata.py` turns the province image and the title
  nesting into where a county is, what it borders and how far away it lies.

Optical character recognition sits beside these as a witness, never as the product: if the tree says
a word is at x=262 and the recogniser reads it there, the geometry is right.

### Getting a window open, which decides how much the first source holds

**A window has to be opened the way a player opens it, or the first source is half empty.** The
console builds any window on demand, which makes coverage independent of who is playing, but it
hands over shape and captions and no data context: 6.6 text boxes per window against 23.7 through a
shortcut and 32.8 through a click. None of the twelve `GUI.` console commands takes a context, so
there is no way around it. Structure is collected the cheap way and data the slow way, and
`tools/ck3/harvest.py` knows all three routes.

**A fourth route reaches what no single action opens: the chain.** Some windows wait on a state
rather than on a button — a variable another window sets — so they are reached by opening one window
and acting inside it. `tools/ck3/openers.py`, behind `--chain`, reads the target's own `visible`
line to learn what has to happen, aligns the open window against the files to find the widget that
does it, and presses it only when it can say which widget it means. That is what the last two
closed windows needed.

### Joining the tree to the files

**The first two sources are joined by structure, not by name.** `tools/ck3/pairing.py` lays the
expanded tree from disk against the harvested tree on class and child order, so meaning reaches a
widget carrying no name — more than nine in ten of the ones that show text. Names are kept out of
the alignment on purpose, which leaves them free to score it: 98.4 per cent land right. One template
row on disk has to be allowed to become many live rows.

**Four things about the gui format that a line-based reader gets wrong.** Load order carries
meaning, because the last definition of a template wins. The same last-wins rule applies inside a
block: `onclick` may be written twice, and only the second one fires. `block "x"` and `block = "x"`
both occur. And a tooltip contains widgets with tooltips of their own, without end, so the expansion
has to stop there.

**And one thing the engine does that no file says.** A scroll area draws its scrollbar last whatever
the order on disk, so an alignment that runs on child order has to move it there first. Until that
was found, every list declared the other way round lost its whole content: 67 texts, and with them
the buttons that switch the ledger between its eleven categories.

## 6. Presentation — not built yet

What gets spoken, in what order, and what is left out. This decides whether the result is usable,
and it is the one place measurement cannot answer the question.

Two rules are fixed: output is not sorted by screen position, which is a sighted reader's order; and
one keystroke produces one unit of speech plus braille. It belongs in data rather than in code.

**A third rule was fixed and has since been withdrawn: addressing a widget by name.** The intent
stands, since an index among siblings breaks the moment a mod adds a row inside a vanilla window,
but only about a fifth of the widgets that carry text have a name, and a name is not unique within a
window either. The structural alignment in section 5 replaces it.

**Draw order lives in exactly one place.** The channel walks each child list in the engine's own
order and the tree reader keeps the lines that way; the parent offset never says in which place. A
pass that sorts the children destroys the only copy.

## 7. Speech — `tools/nvda/speech.py`

One function: text, braille text, mode. **Braille is never optional** — a seam a caller can forget a
channel in loses that channel eventually. Behind it, the official NVDA controller client rather than
Tolk. **It is LGPL 2.1, so it must be linked dynamically and shipped unchanged.**

Two modes, replace and queue. Priority-with-resume was rejected: it interrupts and then carries on
with the old sentence. Keeping the seam thin is deliberate — swapping in Prism or SRAL for other
screen readers should be a day's work.

**A failure has its own exit beside that one.** `failure(where, what, remedy)` turns a failure into
one sentence a player can act on — no error code, no path, no exclamation mark without words —
because a tester who hears nothing cannot report anything at all. It is the one place in the seam
allowed to swallow: it writes the sentence out before it speaks it, so an exit that cannot reach
NVDA still cannot lose the message. Everywhere else a failure breaks where it happens.
`tools/never_silent.py` is the proof, and it is the gate in front of a beta.

**And a keystroke that produces nothing says so.** `answering(where)` counts the sentences that
leave the seam around a block and speaks when the count did not move — an exception on its way out
counts as silence as well, and is left to carry on. Silence is the failure a blind tester cannot
report.

## What is deliberately not done

- No decompiling or rebuilding the engine. Reading memory and data files is ordinary modding;
  rebuilding the engine would put every accessibility mod for these games at risk.
- No redistribution of game files.
- No driving the game from outside with synthetic input at the OS level.
- No hard-coded memory addresses, field offsets or click positions. All three are derived.
