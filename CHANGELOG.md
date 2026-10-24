# Changelog

Outcomes, newest day first. No release yet.

## 2026-10-24
- Save games stay out of the repository.
- The marriage window and its candidate filter are harvested on Ghur played, from a free spouse slot in the character window. 250 windows.
- A chain step passes on every data context a widget sets, not only the last, so the files lead to the filter button of the marriage candidates.
- The religion and rite panels of the faith window no longer open for a player in 1.20; the Rites tab of Faith Details holds their lists.
- A running feast on Ghur played gives the activity's guest list, intent choice and log, harvested along the chain from the activity window.
- A destination icon on the map takes a posted click: the feast planner chose the capital that way.
- python -m tools.ck3.missing lists every window without a player record, grouped by how a player gets there; tools.check flags it when stale.
- The node editor, the particle editor and the gui search count as developer windows now.
- tools.ck3.missing also lists the windows a player reaches whose keys no key round has pressed yet.

## 2026-10-23
- The hostage exchange is harvested on Harold, through the war overview's peace terms; `tools/ck3/hand.py` takes a step that only presses inside the open window.
- A widget counts as on screen for a click when its middle is in the drawing area, and a named widget is pressed where the chain step found it, not as the first of its name.
- The chain round on Harold adds the court scene editor, the title election and the title window.
- Saru: the migration with a target and its list of those involved, and the Silk Road with its catalysts. Andronikos: the heir designation and the house aspiration.
- Rimbert: the council's tenet and doctrine choice and the travel entourage. A new Chinese state gives the merit pool and the dynastic cycle's catalysts. 249 windows.
- `tools/ck3/hand.py` picks a row by the text it shows (`call@text`) and keeps the record of a window on the way that a player route already made.
- `windowmap --window-keys` takes a window's one press as `name=key` or `name=button:x`; a harvest says yes when the game asks whether a plan may go.
- A window lying over the one being pressed has its own scale asked for before its rectangle is compared.
- Design: the player's Enter will click the widget the reader stands on, only after checking it is still drawn, on top and switched on.

## 2026-10-22
- The harvest holds 239 windows, along shortcuts, clicks, chains, the console and presses by hand (`tools/ck3/hand.py`), and waits until a window's layout has settled.
- The war overview, the college of cardinals, the royal court (Shift+F2), the domicile and the administration window are harvested along their keys, the migration by hand.
- A chain step shows a hidden button by pressing the tab that declares its hiding condition, and reaches a state through a call that opens on the same object.
- A chain step clicks the reachable point nearest a button's middle; the chain round and the key round also start from a window a chain opens.
- The window map counts an instance of a window type outside a `types` block as a window the console can make, so 234 of the 282 windows have a console route.
- A window type used in one place takes its `visible` rule from there; where one window holds several lists, the data context picks the filter button.
- A gui attribute is read as the last one a widget carries, as the game does: an instance's own name and text override its type's.
- The pairing reads `raw_text` as well as `text`, pairs the widgets an activity or a decision inserts by file name, and scores itself: 0.960 over the harvest.
- The keys inside 40 windows are measured and kept in `reports/window_keys.json`, each window opened along a key, a click or a chain and measured once open.
- That round presses sub-tabs after every tab and a toggle twice, and never a mouse button or a key another widget of the window acts on.
- The click map no longer counts hidden buttons as covering what lies under them; a cut text on a widget that is not a text box is no longer reported lost.
- One README holds the whole project, NVDA setup included; the NVDA add-on is gone; `check.py` keeps this changelog short.

## 2026-10-21 — CK3 1.20.1.1 and 1.20.1.2
- Checked against 1.20.1.1 and 1.20.1.2 on disk and in the game: field offsets, game model, numbering and window map hold; moved globals derive again by themselves.
- The numbering reads all six databases from the running game again, faiths where 1.20 keeps them; where the player is kept carries its own build key.
- The harvest is redone on 1.20.1.2 with every widget's state byte; each round starts from the bare screen and puts it back, and skips a window with no route.
- A start that must derive the memory layout again says why it takes minutes, and the reader asks the player to press F1 twice instead of sending the key.
- When the game ends while the reader runs, the reader stops without a word; "no window to read" is said only in answer to a key.
- `quit_game` shuts the console first, answers yes to the game's own question, also quits from a bookmark's setup screen, and says whether the exit save was written.
- A question goes to the channel once, so a click, a key or a scan cannot run twice; `tree` reports an unreadable parent, position or size as a loss.
- Paths come from the registry and Steam alone, and the build finds MSVC through vswhere: no path of one machine is written anywhere. The DLL is two source files.
- `derive.py` is three layers without a cycle, and `guimap` expands every window without a silent hole, a window declared as a type only once.
- A click and a shortcut fire every onclick of a block, in order; the holding view opens with Alt+S.
- `derive.tooltip_root` finds the game's tooltip in milliseconds instead of a 21-second scan; the move-camp planner opens from the camp's map icon.
- ruff and clang-tidy enforce the rules against silent or blind catches and dead code; `tests/test_loading.py` fails on a script that does work when it is loaded.

## 2026-10-06
- mypy runs fully strict over every module and every test.
- A toast counts as showing only when `derive.shown` says so, and a real toast is read the moment it appears; the game's message log keeps it.
- The game's tooltips can be read: the pointer moves the game's hover point, and the text stands in roots outside the widget tree.
- The text classes are named once, in `derive`, and the gui tables are built once, in `guimap.tables`.
- Reading a harvested window that was never opened says so in a sentence.

## 2026-10-04
- Fifteen modules and five tests hold all of mypy's strict flags, unchanged in what they do.
- A harvested window record has a type of its own; `windowmap --window-keys` prints its plan in the same order every run.
- The recheck at every start reads only the fields it tests, so a root just before unreadable memory no longer fails a good derivation.
- `reports/model.json` is read and written in one place, `anchor`; `never_silent` no longer takes over the NVDA client when it is imported.
- A start finds the widget tree in 2 to 10 seconds instead of 80: `scan` and `find` skip the DLL's own thread stacks and write-combined memory, and say so.
- Every new derivation checks that each widget of the tree is in the full scan.
- `restore_launcher` acts only when started.

## 2026-10-03
- Alt+A opens the activity window; each of the nine combinations the modifier key round presses opens a window.
- Only state bit 0x08 hides; 0x20 lets the mouse through, so the activity planner is read and clicked. One rule, in `derive.shown`.
- Tooling brought up to date (OpenVINO 2026.4, onnx 1.23, pytest 9.1, ruff 0.16, Build Tools 18.10.2, LLVM 23); text recognition unchanged.
- No check is switched off for convenience: pytest fails on any warning and lists every skip, and the DLL builds with every check of clang-tidy and MSVC on.
- The DLL reads numbers strictly: digits only, no sign, nothing too big for its field.
- `tools` is a package: scripts start from the project folder as `python -m tools.ck3.start_game`, and `check.py` reports any other start.
- On a machine marked with `.tools-required` the channel test fails, rather than skips, when MSVC or clang-tidy is missing.
- A missing game or documents folder stops with a sentence; the game is found through the Steam libraries in the registry, or `CK3_GAME`.
- guimap, database, screens, propose and derive carry real types, with their output unchanged; a read that must succeed goes through `derive.read_known`.
- The channel's one retry is tested without a game, and the channel test tolerates someone holding ctrl, shift or alt.
- The game model holds on a state begun and played on 1.20: 400 characters, all 19 fields agree with the save.
- Removed two unused tools.

## 2026-10-02
- `combo`: shift, ctrl and alt combinations are posted from inside, without taking focus; shift+1 answers an event.
- windowmap's `--modified-keys` and `--window-keys`: key rounds with modifiers and inside windows; keys that act on the game are never pressed.
- The game starts without taking the foreground.
- The DLL has no default field offsets, and the channel refuses malformed commands.
- The DLL is tested without the game (`tests/test_channel.py`), also under AddressSanitizer; the build stops on any warning; pytest runs clang-tidy.
- `count`: an instrument for what the game asks Windows about the keyboard.

## 2026-10-01 — CK3 1.20 "Crozier"
- Checked against 1.20.0.3 on disk and in the game: 282 named windows, field offsets unchanged.
- The tree walk no longer drops a widget silently; on 1.20 it had lost the decisions window.
- The character record length is measured at every start; characters carry a rite.

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
- Injected channel; field offsets derived at every start; visibility and screen geometry; input posted from inside; events read and answered.
- The console is driven through the channel.
