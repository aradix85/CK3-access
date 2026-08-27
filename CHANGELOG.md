# Changelog

One line per change: what changed and why. Dates are the day the work was measured. Numbers live in
`reports/claims.json`, where they can be recomputed; the reasoning lives in `ARCHITECTURE.md`.

## 2026-08-27

- `tools/ck3/pairing.py`: pairs the tree expanded off disk with the tree the game built, on class
  and child order, so meaning in the gui files reaches the widgets that carry no name.
- Names are kept out of that alignment and used to score it instead: 98.4 per cent land right.
- The alignment needs four moves, not two: one template row on disk becomes as many live rows as
  there are records behind it, and a widget can sit on disk that the game never built.
- `DEFAULT_TEXT` is counted apart — where a widget carries it the code sets the text, so the files
  cannot say what will stand there.
- A button carries its own caption and the engine hangs a text box under it to draw it, so the box
  is absent from the file and the widget above answers for it.
- Two more things a localisation value can hold: a quote of another key, written `$OTHER_KEY$`, and
  an icon token the game draws in place of the text. Both were being read as plain sentences.
- With those three modelled, every plain key the alignment points at matches what was on screen.
- No window is gated behind an expansion: expanded over all 196, not one window block carries a
  `HasDlcFeature` check. They all sit on the `visible` of a widget deeper down, so a missing
  expansion takes away parts of a window and never the window.
- `tools/check.py` counts those checks and the distinct features, cheaply, so a patch that changes
  how the game gates content shows up.
- `tools/ck3/database.py`: reads the game's own databases the way the engine merges them, so a
  culture, faith or trait key can be turned into the name a player sees, off disk.
- A faith is not a top-level key — it hangs inside a religion under `faiths`, and there is no
  `religions` folder at all, so a line reader looking at column zero finds none of them.
- The gui parser now accepts an unnamed block inside a block. No gui file does that; the script
  files do, and one grammar reads both rather than two parsers drifting apart.
- All 463 culture keys also resolve in the localisation files, which is what says the reader read
  the right part of the file.
- Which number means which key is read from a save, not guessed: the engine writes all three lists
  into it and a save needs no running game.
- The engine does not number by one rule. Cultures follow the file order exactly, all 463 of them.
  Faiths do not, but fall into place, all 237, once grouped per religion in the engine's religion
  order — and where that religion order comes from is not known. Traits agree to number 300 and
  then diverge where the mods add theirs.

## 2026-08-26

- `tools/nvda/addon/`: puts NVDA in sleep mode while the game has focus, so the reader is not
  talked over and keeps the keys it needs; speech and braille still arrive.
- `tools/ck3/guimap.py`: parses the `.gui` format and expands a window into the widget tree the
  engine would build, with inheritance, `using` mixins and named slots resolved, off disk.
- Three format traps a line-based reader falls into: `type` and `template` are both global,
  `block "x"` and `block = "x"` both occur, and load order decides which definition wins.
- The expansion stops at a tooltip inside a tooltip: the engine builds one only on hover, so on
  disk that definition is allowed to be circular.
- The harvest sorted children by memory address and destroyed the engine's child order, which
  decides what is drawn on top; every widget now records its sibling index and the sweep was re-run.
- With that order kept, the two trees line up child by child — the measurement the alignment rests on.
- A text box outside the drawing area is no longer a recognition failure: a window built by
  `GUI.CreateWidget` is not laid out where a player would see it.
- Window map corrected: `load_info` is a template a line reader mistook for a window, and
  `colorpicker_window` cannot be created from the console.
- `paths.py` derives the enabled mods' folders, because the engine merges them and a reader that
  skips them is looking at a game nobody is running.

## 2026-08-25

- A whole sweep was blind on the left third of the screen: the debug console stood open over it and
  the tree does not notice a covered window. The console is now shut for the length of every
  capture, and each record says how many of its own text boxes the recogniser read back.
- `strip_markup` lost the separator between two markup codes back to back, and never stripped
  `0x16` for icons; both had been written down as quirks of the game and were ours.
- Whether the console is open is read from the flag byte of `console_window`, not by clicking into
  its input field, which opens a game window when the console is not there.
- Field verification needs a loaded game: on the main menu the position check rejects a good
  stored derivation.
- `check.py` recomputes the quality of a sweep, not just file sizes.
- `tools/ck3/openers.py`: which button opens which window, measured by pressing it, because nothing
  on disk binds a view name to a window.
- A trigger belongs to the widget one level above it with a `blockoverride` between, and there are
  two mechanisms — reading only `onclick` and not `shortcut` throws away half the buttons.
- A modifier key cannot be posted into the game, which reads raw input straight from the device;
  nothing in the product needs it. See `ARCHITECTURE.md`.
- `check.py` verifies bare file names too, on one convention: backticks mean the thing exists, and
  a removed file is named in plain text. It closed a real hole — the documentation had promised a
  recovery file that did not exist.

## 2026-08-24

- Everything public is English: names, comments, messages, the channel protocol, report keys.
- Alpha and the window flag are derived rather than hard-coded, by changing the state: open a
  window and require both to move and return.
- The position offset is re-derived from the live tree, because a full memory scan also sees dead
  widget objects carrying stale coordinates.
- Scrolled lists are a third visibility mechanism: a row scrolled out of view keeps alpha 1.0.
- A missing scale is a hard stop instead of a default of 1.0, which silently misplaced everything
  under a scaled container.
- `tools/ck3/harvest.py`, phase 1 of the sweep: open each window, record the subtree, capture it,
  read it back, close it, check the state returns. Resumable, with four stop conditions.
- Two traps in that phase: `GUI.CreateWidget` builds a new window beside the parked one of the same
  name, and a window opened that way carries its labels but not its data.
- An event creates a new window object rather than flipping a parked one, so nothing can watch a
  fixed address for it.
- Hovering cannot be provoked from outside the process. That settles that the game does not see our
  cursor — not that tooltips live outside the widget tree.
- Housekeeping: `requirements.txt`, build and start instructions, the antivirus warning an injector
  owes its users, and reports scrubbed of game text and of one machine's paths.

## 2026-08-23 — first public source

Not a release: there is no installable mod and nothing is spoken during normal play. What is here
is the machinery, measured on Crusader Kings III 1.19.0.6 with all DLC and five content mods.

- Injected channel answers about 25 seconds after launch; the interface exists a few minutes later.
- Seven memory field offsets are derived from the running process at every start and re-verified;
  on build 1.16.2 one had moved and it re-derived itself.
- Visibility solved: a window flag says whether a window is drawn, and sibling draw order says
  which of several drawn windows is on top.
- Screen geometry solved, including the five windows that scale a full-screen container.
- Mouse and keyboard input is posted into the process, so the game never needs focus.
- An event can be read and answered end to end, across all three event window types, matching the
  localisation files character for character — including text from a content mod.
- The developer console can be driven through the channel, so any window can be instantiated for
  mapping. Research tooling only; the product never requires debug mode.
- `reports/windows.json`: which window opens along which route, and what the engine says when it
  will not.
