# Changelog

One item per change: what changed and why, in a line or two. Newest first, dated the day the work
was measured. No release yet — see the entry of 2026-08-23 for what "first public source" means here.

The numbers live in `reports/claims.json`, where `tools/check.py` recomputes them; the reasoning
lives in `ARCHITECTURE.md`. This file says only what moved.

## 2026-08-31

- A chain step no longer has to aim at a view. `--chain <window> <target>` reads the target's own
  `visible` line and takes the condition from there: a view that opens, a variable that must hold
  a value, or one that must merely exist. Tested on disk without the game — one candidate for each
  of `houses_list` and `knight_permissions`, with the twin that sets the variable back and the call
  that clears it both refused.

## 2026-08-30

- A scroll area draws its scrollbar last whatever the file says; the pairing now moves it there
  before aligning. Paired texts 1517 to 1584, data context 1245 to 1311, unexplained 204 to 137,
  strict test still 562 of 562. No harvest was rerun.
- `tools/ck3/openers.py` takes a chain step: `--chain <window> <view>` aligns the window that is
  open now and returns the widgets whose block carries the call that opens that view.
- A block may write `onclick` twice and only the second fires — the same last-wins rule that
  decides which mod redefines a template.
- What catches a click is the last-drawn button with an action of its own; a container catches
  nothing and a button without an action passes it on. An entry of the same day claiming the
  opposite is withdrawn: it rested on one case in an empty list, against ten that disagree.
- The ledger cannot open the holding view, and that is the game: no onclick above a county name,
  and the pinned rows need a pin at alpha zero that appears on hover.
- The rule that picks a nameless child of a namebearing button holds where it could have failed:
  on an administrative state one of the four government tabs is on screen and opens its window.
- `model.player` reads the played character out of the running game — a handle, kept in six places
  inside the module, derived against a save and rechecked at every start.
- The harvest has a fifth stop condition: the player. It goes in every record header and is asked
  before every window, because a state moved to another character looks normal from the tree.
- The administration and domicile windows are in the main harvest with the record of the route a
  player takes, so the pairing reads the rich version instead of the console one.
- Five widget names in the decision detail view come from a file a decision names itself, with
  `widget = { gui = ... }` in `common/decisions`. 58 such names, and a file exists for all 58.
- A button whose name sits one level up is a click target too: the namebearer answers for it and the
  geometry test picks which of its nameless children is on screen. 74 rows where there were 56.
- The window reader counts both shapes a window is declared in: 218 where it read 196. The 22 new
  ones are the scheme conclusions, the event windows and the confirmation dialogs, and all 22 are
  now harvested.
- A window declared through a type of its own is expanded under that type instead of under `window`.
  Built as a plain window it came out as two nodes against 283 live ones.

## 2026-08-29

- `tools/ck3/numbering.py`: which number means which culture, faith, religion or trait, read out of
  the running game instead of out of a save.
- Reading it from a save is not slightly wrong but almost entirely: memory carries the numbering of
  the save that was loaded, and against another state 2 of 237 faiths come out right.
- `tools/ck3/anchor.py` reaches any database of the game state, not only the character store: the
  class name and the test for a believable address are arguments now.
- `readmany` bounds the number of addresses per question as well as the size of the answer; asking
  for 32 bytes each used to put over a thousand addresses in one command, which the DLL refuses.
- Twenty numbers a document repeats are now held to the measured value where three were: the gui
  files per layer, the localisation files, the harvested windows, the cultures and faiths, the
  merged gui set and its templates.
- `tools/ck3/model.py`: the character record's layout is derived instead of written down — eighteen
  fields, reproducing at the same offsets the three that had been measured by hand.
- That derivation is checked at start-up without a save, on four predictions that fail if an offset
  moved; shown to fail before it was trusted, by shifting three offsets on purpose.
- Seven fields are recomputed around loading, so the save a state was loaded *from* is not a valid
  answer key for them. `calibrate.py` reports those apart from a genuinely moved offset.
- The record holds the name *key* (`SU_rI_`, not `Sūrī`), and a name over fifteen characters sits
  behind a pointer; with both handled, names match the save 400 out of 400.
- `calibrate.py` covers eighteen fields where it covered three, by using `model.py`; `anchor.character`
  is gone, because two modules knew the same record layout.
- `tools/ck3/savegame.py` takes the save folder from `tools/paths.py` instead of a spelled-out path,
  which broke on a redirected or non-English Documents folder.
- The claim about the engine's culture numbering names the save it rests on, instead of taking
  whichever save was newest and measuring something other than its own counting rule.
- `ARCHITECTURE.md`: what the pipe is for. It is a workbench — a released build carries none, and
  the DLL never opens a network connection.
- `tools/check.py` asserts that a number a public document quotes is still the measured one: a claim
  names the files that repeat it under `quoted_in`. `README.md` could keep yesterday's count and
  nothing here would say so.
- `CHANGELOG.md` is one line per change again. It had grown into a measurement diary, which is worth
  keeping but belongs in `ARCHITECTURE.md` and in the claims, not in a list of what moved.
- `ARCHITECTURE.md` opens with an index of its seven parts, and counts them correctly — speech is a
  part with its own rule, and the heading said six.
- `requirements.txt` pointed at the wrong section for the recognition setup.
- `CONTRIBUTING.md` says the two rules it was missing: everything public is English, and a number a
  public document quotes belongs in `quoted_in`.

## 2026-08-28

- `tools/ck3/harvest.py` takes a third route: `--click` opens a window the way a player does, from
  `reports/openers.json`, with the console shut because two of those buttons sit under it.
- Measured over the whole harvest: 7.4 text boxes per window through the console, 23.7 through a
  shortcut, 36.3 through a click. Seven windows re-harvested that way went from 55 to 254.
- A window that fails to open now has the state put back before the next one starts, because a
  miss opens something often enough to poison the rest of the round.
- `tools/ck3/openers.py` no longer skips a button whose name several widgets carry: the copies are
  narrowed to the ones really drawn, which leaves exactly one for two of the fourteen.
- Clicking now requires the nearest window ancestor to be drawn, not just alpha and size — all three
  widgets named `create_faith` pass the alpha test from inside a window that is shut.
- The ledger opens on a click after all: not on `ledger_shortcut`, which has no size, but on a
  second widget carrying the window's own name. That window went from 4 text boxes to 78.
- `tools/ck3/calibrate.py` fetches the character database once instead of per character: four
  hundred characters went from thirteen minutes to about one.
- `tools/ck3/calibrate.py` takes the save as an argument, because held against the wrong save every
  field disagrees at once, which reads exactly like a shifted offset.
- The game model regression pass runs clean on three states differing in era, faith, government and
  mod set.
- `tools/ck3/savegame.py` builds a character-number index in one pass; a lookup used to scan the
  whole game state, and a calibration round asks for hundreds.
- `tools/ck3/pairing.py` writes the leftover texts per window, so the share sitting in the
  developers' own tools stays recomputable.
- The last two Dutch remnants are gone from the code, rebuilt and smoke-tested; the launcher
  fallback is now `launcher-settings.original.json`, with `tools/restore_launcher.py` beside it.
- `.gitignore` kept that fallback out under its old name only, so the rename would have published a
  machine-specific file. `tools/check.py` caught it on the file count.
- `README.md` and `ARCHITECTURE.md` were missing the game model: it is a source in its own right
  beside the widget tree, and section 5 counted four sources where there are five.

## 2026-08-27

- `tools/ck3/pairing.py`: pairs the tree expanded off disk with the tree the game built, on class
  and child order, so meaning in the gui files reaches the widgets that carry no name.
- Names are kept out of that alignment and used to score it instead: 98.4 per cent land right.
- The alignment needs four moves, not two — one template row on disk becomes as many live rows as
  there are records behind it, and a widget can sit on disk that the game never built.
- Three things a localisation value can hold that were being read as plain sentences: a quote of
  another key (`$OTHER_KEY$`), an icon token, and `DEFAULT_TEXT` where the code sets the text.
- A button carries its own caption and the engine hangs a text box under it, so that box is absent
  from the file and the widget above answers for it.
- `tools/ck3/database.py`: reads the game's own databases the way the engine merges them, so a
  culture, faith or trait number becomes the name a player sees — off disk, no game running.
- Which number means which key is read from a save rather than guessed, because the engine does not
  number by one rule: cultures follow file order, faiths only once grouped per religion, traits
  diverge where mods add theirs.
- All 463 culture keys also resolve in the localisation files, which is what says the reader read
  the right part of the file.
- A faith is not a top-level key but sits inside a religion, and there is no `religions` folder at
  all, so a line reader looking at column zero finds none of them.
- The gui parser accepts an unnamed block inside a block: no gui file does that, the script files
  do, and one grammar reads both rather than two parsers drifting apart.
- No window is gated behind an expansion: expanded over all 196, not one window block carries a
  `HasDlcFeature` check, so a missing expansion takes away parts of a window and never the window.
- `tools/check.py` counts those checks and the distinct features, so a patch that changes how the
  game gates content shows up.
- `tools/nvda/speech.py`: braille is no longer optional, and the call is named `output` rather than
  `speak`, since speaking is half of what it does.

## 2026-08-26

- `tools/nvda/addon/`: puts NVDA in sleep mode while the game has focus, so the reader is not talked
  over and keeps the keys it needs; speech and braille still arrive.
- `tools/ck3/guimap.py`: parses the `.gui` format and expands a window into the tree the engine
  would build, with inheritance, `using` mixins and named slots resolved, off disk.
- Three format traps a line-based reader falls into: `type` and `template` are both global,
  `block "x"` and `block = "x"` both occur, and load order decides which definition wins.
- The expansion stops at a tooltip inside a tooltip, which on disk is allowed to be circular because
  the engine builds one only on hover.
- The harvest sorted children by memory address and destroyed the engine's child order, which
  decides what is drawn on top. Every widget now records its sibling index and the sweep was re-run.
- With that order kept, the two trees line up child by child — the measurement the alignment rests
  on.
- A text box outside the drawing area is no longer counted as a recognition failure: a window built
  from the console is not laid out where a player would see it.
- Window map corrected: `load_info` is a template a line reader mistook for a window, and
  `colorpicker_window` cannot be created from the console.
- `tools/paths.py` derives the enabled mods' folders, because the engine merges them and a reader
  that skips them is looking at a game nobody is running.

## 2026-08-25

- `tools/ck3/openers.py`: which button opens which window, measured by pressing it, because nothing
  on disk binds a view name to a window.
- A trigger belongs to the widget one level above it with a `blockoverride` between, and there are
  two mechanisms — reading only `onclick` and not `shortcut` throws away half the buttons.
- A whole sweep was blind on the left third of the screen, because the debug console stood open over
  it and the tree does not notice a covered window. The console is now shut for every capture, and
  each record says how many of its own text boxes the recogniser read back.
- `strip_markup` ate the separator between two markup codes back to back and never stripped the icon
  code; both had been written down as quirks of the game and were ours.
- Whether the console is open is read from the flag byte of `console_window`, not by clicking into
  its input field — which opens a game window when the console is not there.
- Field verification needs a loaded game: on the main menu the position check rejects a good stored
  derivation.
- A modifier key cannot be posted into the game, which reads raw input straight from the device.
  Nothing in the product needs it; see `ARCHITECTURE.md`, section 4.
- `tools/check.py` verifies bare file names too, on one convention: backticks mean the thing exists,
  and a removed file is named in plain text. It closed a real hole — the documentation had promised
  a recovery file that did not exist.

## 2026-08-24

- Everything public is English: names, comments, messages, the channel protocol, report keys.
- Alpha and the window flag are derived rather than hard-coded, by changing the state: open a window
  and require both to move and return while a window that stays shut does not.
- The position offset is re-derived from the live tree, because a full memory scan also sees dead
  widget objects carrying stale coordinates.
- Scrolled lists are a third visibility mechanism: a row scrolled out of view keeps alpha 1.0.
- A missing scale is a hard stop instead of a default of 1.0, which silently misplaced everything
  under a scaled container.
- `tools/ck3/harvest.py`, phase 1 of the sweep: open each window, record the subtree, capture it,
  read it back, close it, check the state returns. Resumable, with four stop conditions.
- Two traps in that phase: the console builds a new window beside the parked one of the same name,
  and a window opened that way carries its labels but not its data.
- An event creates a new window object rather than flipping a parked one, so nothing can watch a
  fixed address for it.
- Hovering cannot be provoked from outside the process. That settles that the game does not see our
  cursor — not that tooltips live outside the widget tree.
- Housekeeping: `requirements.txt`, build and start instructions, the antivirus warning an injector
  owes its users, and reports scrubbed of game text and of one machine's paths.

## 2026-08-23 — first public source

Not a release: there is no installable mod and nothing is spoken during normal play. What is here is
the machinery, measured on Crusader Kings III 1.19.0.6 with all DLC and five content mods.

- The injected channel answers about 25 seconds after launch; the interface exists a few minutes
  later.
- Seven memory field offsets are derived from the running process at every start and re-verified; on
  build 1.16.2 one had moved and it re-derived itself.
- Visibility solved: a window flag says whether a window is drawn, and sibling draw order says which
  of several drawn windows is on top.
- Screen geometry solved, including the five windows that scale a full-screen container.
- Mouse and keyboard input is posted into the process, so the game never needs focus.
- An event can be read and answered end to end, across all three event window types, matching the
  localisation files character for character — including text from a content mod.
- The developer console can be driven through the channel, so any window can be instantiated for
  mapping. Research tooling only; the product never requires debug mode.
- `reports/windows.json`: which window opens along which route, and what the engine says when it
  will not.
