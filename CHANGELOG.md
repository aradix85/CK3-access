# Changelog

Outcomes, newest first. No release yet.

## 2026-10-21 — CK3 1.20.1.1 and 1.20.1.2
- Every round starts from the bare screen, measured as the state where Escape opens the pause menu, so windows 1.20 always draws no longer count as open; the harvest no longer keeps its own list of them.
- Shutting what a press opened sends Escape only while something more is open, so it no longer flips the pause menu; the window key round checks after every key that the state came back.
- The chain round and the chain step by hand press through one function, `openers.press_toward`.
- `tree` reports a widget whose parent, position or size cannot be read as lost, instead of a widget at 0,0 under no parent; the DLL has one definition of a readable page.
- `derive.fields_for` returns the root of the tree with the derivation, so no caller searches for it again; visibility is left out only where the tree has no character window, as on the main menu, and any other failure stops.
- `derive.verify` shares its thresholds with the derivation and checks the scale offset, which is not derived.
- The size of the module comes from the exe's header instead of a guessed 96 MB.
- `states.console` types through `windowmap.Game.command`, which proves the console open and the text in the field; a second attempt empties the field first.
- `harvest.subtree` has no depth limit; parameters nobody passed are gone.
- `derive.py` is three layers without a cycle: reading memory in `channel.py` (`read`, `readmany`, `field_for`, one loop where `model` had its own), the widget tree in `widgettree.py`, and what is drawn and where in `onscreen.py`; `derive.py` keeps the derivation.
- `guimap` reads `local_template` and looks a local name up in the file it is written in, so the culture, hybridisation and ledger windows get their innovation tooltips.
- `guimap` stops a widget that comes back inside itself with the same slots filled, instead of cutting the dynasty tree and the struggle window off at a fixed depth; a `using` nothing defines and a tree past that depth now stop with a GuiError.
- A window declared as a type is expanded once instead of twice over.
- A question goes to the channel once: a reply that comes too late is no longer asked again, so a click, a key or a scan cannot run twice.
- `find` and `findin` see a match that ends exactly with a region or with the stretch searched; `mouse`, `sendkey` and `sendchar` say so when the game window refuses a message; `mouse` is a left click and refuses a point that does not fit a window message; wildcards in `find` and the limit on `tree`, which nothing used, are gone.
- The DLL is two files: `dll/channel.cpp` for the pipe and memory, `dll/input.cpp` for keys and clicks.
- Saving through the pause menu answers yes to the game's own question, as quitting does, through one shared Escape loop.
- Faiths are read only where 1.20 keeps them; a save gives the culture numbering and no other.
- Paths come from the registry and the Steam client alone: no guessed Documents folder, and an override that points nowhere stops instead of giving way.
- The derivation reads the scale anchors, the gui text and the localization through `guimap`, mods included, and each scaled container carries its own anchor.
- An alpha or a state byte that cannot be read counts as not drawn in the harvest and the click map, as in `derive.shown`.
- The exe's class tree is read once per run: a class looked up by name in 0.03 s instead of 9.4.
- `check.py` checks the documents before the claims and measures each claim once; check_rtti.ps1 is gone, `memory.type_name_count` does the same.
- `never_silent` keeps the step that needs the game; the link taken away is a test without one.
- Dead code, parameters nobody passed and the defaults they hid are gone across the tools, and the docstrings say what the code does.
- ruff and clang-tidy enforce the rules for code: sixteen ruff rules and twelve clang-tidy checks for silent or blind catches and dead code, each seen to fire on a planted fault; seven silent catches, two lost causes and nine unused names fixed, and the registry is read in one place (`paths.registry_value`).
- On 1.20.1.2 all nineteen fields of the game model agree with a save written from the loaded state.
- Checked against 1.20.1.2 on disk and in the game: ck3.exe is 2048 bytes larger and the gui carries one expansion check fewer; the nine field offsets, the game model, where the player is kept, the numbering and the window map hold, and the globals that moved were derived again by themselves.
- The window map's drawn flags of sixteen windows are measured again with today's rule: eleven windows the console builds are drawn while carrying 0x20, among them the planners and the holding view, which the rule before 3 October had called not drawn.
- `GUI.CreateWidget` finds a window at any depth of a file except inside a `types` block, so six nested windows have a console route too: 204 in all.
- The modifier key round also presses Alt+S, which opens the holding view, and Shift+F2, which opens the royal court for a ruler who has one.
- When the game ends while the reader runs, closed or crashed, the reader stops without a word: a link that breaks and stays shut is `channel.Gone`, noticed at once instead of after the timeout.
- "No window to read" is said only in answer to a key: a game shutting down clears its windows seconds before it ends.
- `CONTRIBUTING.md` says how the code is written, for Python and C++ alike; `ARCHITECTURE.md` says that every onclick fires and that the game ending is no fault.
- Every script only defines when it is loaded, and `check.py` reports one that does more.
- An activity's own events, shown in the activity window, hold the date until they are answered; Enter and a click start a hunt alike.
- The DLL build and the channel test find MSVC through vswhere (`dll\vcvars.bat`) instead of a path on one machine.
- `states.wait` recognises the setup screen of a bookmark and says `setup`; `quit_game` also shuts the game from there.
- A click and a shortcut both fire every onclick of a block, in order; `openers` and `check.py` had counted only the last, and the holding view opens with Alt+S.
- `openers` reads the gui files through `guimap`, and now also finds the legends button, whose name has no quotes.
- What the tree walk loses is named with the widgets above it, so a text cut short says where it is.
- `quit_game` answers yes when Escape raises the game's own question, and says whether the game wrote its exit save.
- Checked against 1.20.1.1 on disk and in the game: still 282 windows, none behind an expansion; the nine field offsets unchanged; the game model agrees with a save on every field that survives a load; the game builds no window the map lacks. One named shortcut and 38 gui templates more.
- Starting the game no longer says the link is gone while it waits for the channel; a channel that never answers is said once.
- `derive.tooltip_root` finds the root that holds the game's tooltip in milliseconds instead of a 21-second scan, through the engine's own list of layer roots; a fixed tooltip key reads as the gui and localization files say.
- The numbering reads from the running game again on 1.20, all six databases, checked on two states against their saves; the hegemony tier is a title tier, and a character is placed on the map again.
- Where the player is kept carries its own build key, so places from an older build are never taken for this one.
- The move-camp planner opens: with the game in front, the pointer on the camp's map icon draws its quick buttons, and the move button opens `window_move_domicile`.

## 2026-10-06
- mypy runs fully strict over every module and every test.
- A toast counts as showing only when `derive.shown` says so, and only text boxes give it words; the key round asks `derive.shown` too. A real toast, called up through the console, is read the moment it appears, and the game's message log keeps it.
- The game's tooltips can be read: with the game in front, moving the pointer moves the game's hover point, and the text stands in roots outside the widget tree, where `derive.shown` tells the current text from a stale one. Not yet used by the reader.
- The text classes are named once, in `derive`, and the gui tables are built once, in `guimap.tables`.
- Reading a harvested window that was never opened says so in a sentence.

## 2026-10-04
- harvest, openers, windowmap, modifiers, quit_game, states, mapdata, pairing, never_silent, check, anchor, model, numbering, calibrate, place and five tests hold all of mypy's strict flags; each does what it did before.
- A harvested window record has a type of its own; `windowmap --window-keys` prints its plan in the same order every run.
- The recheck at every start reads only the fields it tests; it had turned down a good derivation when the tree's root lay just before unreadable memory.
- `reports/model.json` is read and written in one place, anchor; never_silent no longer takes over the NVDA client when it is imported.
- A start finds the widget tree in 2 to 10 seconds instead of 80: `scan` and `find` skip the DLL's own thread stacks and write-combined memory, report what they skipped, and the channel test fails on either.
- Every new derivation checks that each widget of the tree is in the full scan.
- `restore_launcher` acts only when started.

## 2026-10-03
- Alt+A opens the activity window; each of the nine combinations the modifier key round presses opens a window.
- Only state bit 0x08 hides; 0x20 lets the mouse through, so the activity planner is read and its buttons clicked. One rule, in `derive.shown`; 0x02 marks a switched-off widget and its contents.
- Tooling brought up to date (OpenVINO 2026.4, onnx 1.23, pytest 9.1, ruff 0.16, Build Tools 18.10.2, LLVM 23); text recognition unchanged on the harvest captures.
- No check is switched off for convenience: pytest fails on any warning and lists every skip, and the DLL builds with no check of clang-tidy or MSVC switched off.
- The DLL reads numbers strictly: digits only, no sign, nothing too big for its field.
- `tools` is a package: scripts start from the project folder as `python -m tools.ck3.start_game`, and `check.py` reports any other start.
- On a machine marked with `.tools-required` the channel test fails, rather than skips, when MSVC or clang-tidy is missing.
- A missing game or documents folder stops with a sentence; the game is found through the Steam libraries in the registry, or `CK3_GAME`.
- guimap, database, screens, propose and derive carry real types, with their output unchanged; a read that must succeed goes through `derive.read_known`.
- The channel's one retry is tested without a game, and the channel test tolerates someone holding ctrl, shift or alt.
- The game model holds on a state begun and played on 1.20: 400 characters, all 19 fields agree with the save.
- Removed two unused tools; the code no longer refers to the maintainer's private notes.

## 2026-10-02
- `combo`: shift, ctrl and alt combinations are posted from inside, without taking focus; shift+1 answers an event.
- windowmap's `--modified-keys` and `--window-keys`: key rounds with modifiers and inside windows; keys that act on the game are never pressed.
- The game starts without taking the foreground.
- The tree walk reports everything it loses; the DLL has no default field offsets; the channel refuses malformed commands.
- The DLL is tested without the game (`tests/test_channel.py`), also under AddressSanitizer; the build stops on any warning; pytest runs clang-tidy.
- `count`: an instrument for what the game asks Windows about the keyboard.

## 2026-10-01 — CK3 1.20 "Crozier"
- Checked against 1.20.0.3 on disk and in the game: 282 named windows, field offsets unchanged.
- The tree walk no longer drops a widget silently; on 1.20 it had lost the decisions window.
- The character record length is measured at every start; characters carry a rite.
- Content mods switched off: the project waits on one publisher.

## 2026-09-21
- Widgets the game hides are neither read nor clicked, and a button covered by another window is not clicked.
- Seventeen windows open on a plain key.
- Harvests along shortcut, click and chain need no debug mode.
- A toast is announced when it appears; a list is announced once with its row count, and a list inside a row folds into the row.

## 2026-09-20
- An event is read aloud live, the requirement this project exists for.
- `reader.py`: one unit per keystroke on up and down; F12 toggles, Delete explains the current line.
- The reading rule says only what is on screen; bare numbers get a label from their data function; switched-off buttons say so.
- Screen files are applied (`order`, `key`); `propose.py` drafts them, `screens.py` checks them.
- The window map is checked against the running game (`windowmap.unmapped`).
- `quit_game.py` shuts the game down the way a player does.

## 2026-09-16
- Empty results stay silent; only a real fault speaks, through `speech.failure`.
- First tests and lint configuration (`pytest`, `ruff`).

## 2026-09-13
- Map layer done.

## 2026-09-01
- `mapdata.py`: where a county is, its neighbours, distance, bearing, travel days, the de jure chain.
- Any title resolves to the county under it; `place.py` goes from a character to a place.
- The drawing area comes from the running game instead of a constant.

## 2026-08-31
- `speech.failure` and `tools/never_silent.py`, the gate in front of a beta.
- `openers.chain` reaches windows that wait on a state.

## 2026-08-24 – 2026-08-30
- The first harvest: opening a window the way a player does gives values, the console only captions.
- `guimap.py` parses the gui format; `pairing.py` joins it to the live tree on structure.
- `model.py` and `calibrate.py` derive and check the character record; `numbering.py` reads the numbering from the running game.
- Braille is not optional; an NVDA add-on puts NVDA to sleep while the game has focus.
- Everything public is in English.

## 2026-08-23 — first public source
- Injected channel; field offsets derived at every start; visibility and screen geometry; input posted from inside; events read and answered; the console driven through the channel.
