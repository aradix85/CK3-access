# Changelog

One line per change: what changed and why. Dates are the day the work was measured.
Numbers live in `reports/claims.json`, where they can be recomputed; they are not repeated here.

## 2026-08-26

- `tools/ck3/guimap.py`: a parser for the `.gui` format, a table of every template, and an
  expansion that resolves inheritance, `using` mixins and named slots. A window now expands into
  the widget tree the engine would build, off disk, with no game running.
- Three things about that format that a line-based reader gets wrong: `type` and `template` are
  both global, `block "x"` and `block = "x"` both occur, and load order decides which definition
  wins, so sorting the file list loses a mod that redefines a vanilla template.
- A tooltip contains widgets that have tooltips of their own, without end. The engine builds one
  only on hover, so the expansion stops at the second level instead of following the circle.
- The harvest sorted each widget's children by memory address, destroying the only copy of the
  engine's child order — the thing that decides which of two drawn widgets is on top. Fixed; every
  widget now records its own sibling index. The old harvest could not be repaired and was re-run.
- With order preserved, the tree on disk and the tree in memory line up child by child. That is what
  lets the meaning in the gui files be attached to a live window; see `ARCHITECTURE.md`, section 6,
  for why addressing widgets by name does not reach far enough on its own.
- A text box outside the drawing area no longer counts as a recognition failure. A window built by
  `GUI.CreateWidget` is not laid out where a player would see it, so part of it hangs over the edge.
- Window map corrected: `load_info` is a template name a line reader mistook for a window, and
  `colorpicker_window` cannot be created because its block sits inside a type definition.
- `paths.py` derives the folders of the enabled mods, because the engine merges them with its own
  files and a reader that skips them is looking at a game nobody is running.

## 2026-08-25

- The sweep was blind on the left third of the screen: the debug console stood open over it for the
  whole round and the widget tree does not notice a window being covered. The console is now shut
  for the length of every capture, and each record carries how many of its own text boxes the
  recogniser read back, so a blind capture shows up within ten windows instead of a day later.
- `strip_markup` matched a markup code up to the next space, so two codes back to back lost their
  separator; and a second markup byte, `0x16` for icons, was not stripped at all. Both had been
  written down as quirks of the game and were ours.
- Whether the console is open is read from the flag byte of `console_window`. The old test clicked
  into its input field, which opens a window in the game when the console is not there.
- Field verification needs a loaded game: on the main menu the position check cannot find the
  distinct values it requires and rejects a good stored derivation.
- `check.py` recomputes the quality of a sweep, not just file sizes.
- `tools/ck3/openers.py`: which button opens which window, measured by pressing it and watching the
  drawn set. Nothing on disk binds a view name to a window, so it cannot be read.
- A trigger belongs to the widget whose name sits one level above it with a `blockoverride` between;
  and there are two mechanisms, `onclick` and `shortcut`, so reading one throws away half the
  buttons. Getting this wrong sends clicks to the container around the button.
- A modifier key cannot be posted into the game: it reads raw input straight from the device. Three
  routes measured, all reverted, and nothing in the product needs it. See `ARCHITECTURE.md`.
- `check.py` verifies bare file names too, which needs one convention: backticks mean the thing
  exists, and a removed file is named in plain text. It was closing a real hole — the documentation
  had promised a recovery file that did not exist.

## 2026-08-24

- Everything public is English: names, comments, messages, the channel protocol, report keys.
- Alpha and the window flag are derived instead of hard-coded. They cannot be read out of one
  snapshot, so the derivation changes the state: open a window and require both to move and return.
- The position offset was derived from a full memory scan, which also sees dead widget objects
  carrying stale coordinates. It is re-derived from the live tree now and verified at every start.
- Scrolled lists are a third visibility mechanism: a row scrolled out of view keeps alpha 1.0.
- A missing scale is a hard stop instead of defaulting to 1.0, which silently misplaced everything
  under a scaled container.
- `tools/ck3/harvest.py`, phase 1 of the sweep: open each window, record the subtree with every
  field, capture it, read it back, close it, check the state returns. Resumable, with four stop
  conditions. Two traps: `GUI.CreateWidget` builds a new window object beside the parked one of the
  same name, and a window opened that way carries its labels but not its data.
- An event creates a new window object rather than flipping a parked one, so nothing can watch a
  fixed address for it; a cheap poll with an expensive check behind it is enough.
- Hovering cannot be provoked from outside the process. That settles that the game does not see our
  cursor — not that tooltips live outside the widget tree.
- Housekeeping: `requirements.txt`, build and start instructions, the antivirus warning an injector
  owes its users, and reports scrubbed of game text and of one machine's paths.

## 2026-08-23 — first public source

Not a release: there is no installable mod and nothing is spoken during normal play. What is here
is the machinery, measured on Crusader Kings III 1.19.0.6 with all DLC and five content mods.

- Injected channel answers about 25 seconds after launch; the interface exists a few minutes later.
- Seven memory field offsets are derived from the running process at every start and re-verified.
  On build 1.16.2 one of them had moved and it re-derived itself.
- Visibility solved: a window flag says whether a window is drawn, and sibling draw order says which
  of several drawn windows is on top.
- Screen geometry solved, including the five windows that scale a full-screen container; whether the
  centring correction applies on an axis is read from the game's own `.gui` files.
- Mouse and keyboard input is posted into the process, so the game never needs focus.
- An event can be read and answered end to end, across all three event window types, matching the
  localisation files on disk character for character — including text from a content mod.
- The developer console can be driven through the channel, which allows any window to be
  instantiated for mapping. Research tooling only; the product never requires debug mode.
- `reports/windows.json`: which window opens along which route, and what the engine says when it
  will not.
