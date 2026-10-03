# Changelog

Outcomes, newest first. No release yet.

## 2026-10-03
- Alt+A opens the activity window, so all nine HUD key combinations open a window.
- Only state bit 0x08 hides; 0x20 lets the mouse through, so the activity planner is now read and its buttons clicked. One rule, in `derive.shown`; 0x02 marks a switched-off widget and its contents.
- Tooling brought up to date: OpenVINO 2026.4 (recognition unchanged on the harvest captures), onnx 1.23, pytest 9.1, pyflakes 4; ruff 0.16 with its rule selection written out, since its default grew. Build Tools 18.10.2 and LLVM 23: `tests/test_channel.py` finds clang-tidy through LLVM's uninstall entry, and the 24 findings of its new signed-bitwise check are fixed rather than switched off.
- No check is switched off for convenience: pytest fails on any warning and lists every skip, which exposed unclosed files in `tools/paths.py` and the channel test, now closed; clang-tidy's enum-size check is on again and satisfied.
- The DLL reads numbers strictly - digits only, no sign, nothing too big for its field - and builds with no check of clang-tidy or MSVC switched off.
- The game model holds on a state begun and played on 1.20: 400 characters, all 19 fields agree with the save.
- The game is found through the Steam libraries in the registry only; set `CK3_GAME` otherwise.
- Removed two unused tools; the code no longer refers to the maintainer's private notes.

## 2026-10-02
- `combo`: shift, ctrl and alt combinations are posted from inside, without taking focus; shift+1 answers an event.
- `windowmap.py --modified-keys` and `--window-keys`: key rounds with modifiers and inside windows. Keys that act on the game are never pressed.
- Of the 241 named shortcuts, 192 are declared by a widget, 41 only under a computed name, and 8 nowhere.
- The game starts without taking the foreground.
- The tree walk reports everything it loses; the DLL has no default field offsets; the channel refuses malformed commands. `call` and `waitchange` removed.
- The DLL is tested without the game (`tests/test_channel.py`), also under AddressSanitizer; the build stops on any warning; pytest runs clang-tidy.
- `count`: an instrument for what the game asks Windows about the keyboard.
- The numbering of cultures, faiths, religions and rites does not read on 1.20 yet.

## 2026-10-01 — CK3 1.20 "Crozier"
- Checked against 1.20.0.3 on disk and in the game: 282 named windows, field offsets unchanged.
- The tree walk no longer drops a widget silently; on 1.20 it had lost the decisions window.
- The character record length is measured at every start.
- Characters carry a rite; faiths moved to a folder of their own, and `database.py` reads both forms.
- Content mods switched off: the project waits on one publisher.

## 2026-09-21
- Widgets the game hides (state bit 0x08) are neither read nor clicked.
- Seventeen windows open on a plain key.
- Harvests along shortcut, click and chain need no debug mode; `harvest.py --chain` walks chain routes.
- A button covered by another window is not clicked.
- A toast is announced when it appears (no real toast heard yet).
- A list is announced once with its row count; a list inside a row folds into the row.

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
- Map layer done. The holding view and the move-domicile planner cannot be opened by any route.

## 2026-09-01
- `mapdata.py`: where a county is, its neighbours, distance, bearing, travel days, the de jure chain.
- Any title resolves to the county under it; `place.py` goes from a character to a place.
- The drawing area comes from the running game instead of a constant.

## 2026-08-31
- `speech.failure` and `tools/never_silent.py`, the gate in front of a beta.
- `openers.py --chain` reaches windows that wait on a state.

## 2026-08-24 – 2026-08-30
- 203 windows harvested; opening a window the way a player does gives values, the console only captions.
- `guimap.py` parses the gui format; `pairing.py` joins it to the live tree on structure.
- `model.py` and `calibrate.py` derive and check the character record; `numbering.py` reads the numbering from the running game.
- Braille is not optional; an NVDA add-on puts NVDA to sleep while the game has focus.
- Everything public is in English.

## 2026-08-23 — first public source
- Injected channel; field offsets derived at every start; visibility and screen geometry; input posted from inside; events read and answered; the console driven through the channel.
