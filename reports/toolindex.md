# Tool index - calls and the shape of what they return

Generated from the source by `tools\toolindex.py`. **Read this before writing a
script**, and generate it again once you have changed the tools.
The *returns* column is here because that is where the mistakes were: a function that
returns a pair, passed on as one thing, costs a run.

## boxreader.py
*Reads one known box on the NPU. Two to three times faster than the same route on the CPU.*

| call | returns | does |
|---|---|---|
| `warm_up(device='NPU')` | nothing | Compiling costs a few seconds; after that it sits in the model cache. |
| `read_box_conf(screenshot, x, y, width, height, margin=0)` | 2-tuple | Returns (text, confidence) of one box. |
| `read_box(screenshot, x, y, width, height, margin=0)` | value | Text only. Same call as `ocr.read_box`. |

## check.py
*Recomputes the checkable numbers in the documentation and reports what has drifted.*

| call | returns | does |
|---|---|---|
| `bytes_of(part)` | value | - |
| `lines_of(part)` | value | - |
| `files_in(part, pattern)` | value | - |
| `json_field(part, *keys)` | value | - |
| `json_keys(part, *skip)` | value | - |
| `type_names_in_exe()` | value | - |
| `widget_vtables()` | value | - |
| `gamestate_mb(part)` | value | - |
| `repo_files()` | value | Counts what a `git init` would take into the repo: everything .gitignore does not exclude. |
| `document_paths()` | 2-tuple | Every project path named in a document, checked against the disk. |
| `mod_windows(part)` | value | Windows in the map whose gui file is not part of the game itself. |
| `main(all_of_them)` | value | - |

## docsearch.py
*Two things: search by subject, and report where the working document repeats itself.*

| call | returns | does |
|---|---|---|
| `files()` | nothing | The maintainer's working notes, which are not part of this repository. On a clone this finds |
| `summary(path)` | value | - |
| `strip_markup(text)` | value | - |

## ocr.py
*Reads the text on screen, with positions attached.*

| call | returns | does |
|---|---|---|
| `warm_up()` | nothing | Pay the startup cost at a moment when nobody is waiting. |
| `read_image(screenshot)` | value of list | Returns a list of (x, y, width, height, text) in the points of this image. |
| `read_box(screenshot, x, y, width, height, margin=2)` | value of str | Reads one box whose position is already known from the widget tree. |
| `read_screen(box=None)` | list | Returns a list of (x, y, width, height, text) in screen points. |

## paths.py
*The single place paths come from.*

| call | returns | does |
|---|---|---|
| `require(name)` | value | Return a path, or stop with a sentence saying what needs to happen. |

## restore_launcher.py
*Restores launcher-settings.json to the original from before the injector.*

| call | returns | does |
|---|---|---|
| `sha256(path)` | value | - |

## screenshot.py
*Captures the screen or a crop of it, small enough to read back.*

| call | returns | does |
|---|---|---|
| `capture(path=DEFAULT, box=None, scale=0.5, quality=60)` | 2-tuple | box is (left, top, right, bottom) in screen points, or None for the whole screen. |
| `diff(box=None, pause=0.4)` | 2-tuple | Captures the same crop twice and counts how many pixels changed. |

## toolindex.py
*Writes reports\toolindex.md: every call a script needs, read from the source.*

| call | returns | does |
|---|---|---|
| `first_line(text)` | str of value | - |
| `signature(node)` | value | - |
| `return_shape(node)` | value of str | The shape of what comes out, because that is what the mistakes were about. |
| `files()` | nothing | - |

## windowgrab.py
*Grabs an image of the game window without it having to be in the foreground.*

| call | returns | does |
|---|---|---|
| `window_of(pid)` | 3-tuple of bool | The largest visible window of that process, with its outer size. |
| `client_size(hwnd)` | 2-tuple | The drawing area inside the window, without title bar and border. |
| `borders(hwnd)` | 2-tuple | Where the drawing area starts inside the window: title bar and border. |
| `grab(pid)` | 3-tuple | Returns (image, width, height) of the game window's drawing area. |

## ck3\anchor.py
*The anchor into the game model: from the exe to a character, without searching.*

| call | returns | does |
|---|---|---|
| `vtable(pid)` | value | The address of the character database's vtable in the running game. |
| `find_database(pid)` | value | Find the database by searching memory for its vtable. |
| `derive_global(pid)` | 2-tuple | The offset of the global variable pointing at the database. |
| `database(pid)` | value | The database object, from the stored offset or else derived again. |
| `character(pid, number, db=None)` | 2-tuple | The fields of character N, computed rather than searched for. |
| `size(pid, db=None)` | 2-tuple | How many blocks, and therefore how many character slots, this game state has. |

## ck3\calibrate.py
*Calibration - does what we read out of the game match what the save says?*

| call | returns | does |
|---|---|---|
| `answer_key()` | value | - |
| `test_model(key_sheet, pid, numbers)` | 4-tuple | Reads characters through the anchor and puts every field beside the save. |
| `text_boxes(nodes)` | list | The addresses of the text boxes, found through the vtable that touches the localization files. |
| `test_ocr(pid, nodes, addresses)` | 4-tuple | Reads every text box actually on screen and puts it beside the widget text. |
| `main(pid, count=400, step=97)` | nothing | - |

## ck3\channel.py
*Talks to the channel inside the DLL.*

| call | returns | does |
|---|---|---|
| `close()` | nothing | - |
| `ask(command, timeout=60.0, errors_ok=False)` | value | Asks the channel one question and returns the answer as text. |

## ck3\derive.py
*Derives the field offsets of a widget object from the running game, through the channel.*

| call | returns | does |
|---|---|---|
| `window_size(pid)` | value | The drawing area of the game window, live from Windows. |
| `build_key()` | value | How you tell it is still the same build. If the exe changes, everything lapses. |
| `read(address, count)` | value | - |
| `scan(from_address, to_address)` | value | Address -> vtable. Both come from the vtable comparison and do not depend on the field |
| `tree(root)` | value | - |
| `use_fields(fields)` | nothing | Publish the two visibility offsets for this build. |
| `flags_for(addresses)` | value | The window flag of many objects in as few channel questions as possible. |
| `is_drawn(nodes, address, flags, window_classes)` | bool | Is this widget really on screen? |
| `widgets(root)` | value | The whole tree with fields attached: address -> (vtable, x, y, width, height, parent, name, text). |
| `scales_for(addresses)` | value | Per widget (own scale, scale from above). The two sit next to each other, so one read round. |
| `screen_pos(nodes, address, scales, anchors=None)` | 2-tuple | The place on screen: the own position plus that of every parent, with the scale applied. |
| `scale_anchors()` | value | Per window: does the centring correction apply in x, and in y? Read from the gui files. |
| `screen_size(nodes, address, scales)` | 2-tuple | The size as it is drawn: the own size times the own scale times the scale from above. |
| `is_visible(nodes, address)` | bool | Alpha is a property of the whole parent chain: if one ancestor sits at 0 you see nothing, |
| `is_clipped(nodes, address, scales, classes)` | bool of value | Is this widget scrolled out of view inside a list? |
| `chunks_of(addresses)` | 2-tuple | Raw bytes per object. Unreadable ones are skipped and counted, not hidden. |
| `children_from_parents(chunks, f_parent, addresses)` | value | - |
| `gui_text()` | value | - |
| `localization_text()` | value | - |
| `strip_markup(text)` | value | Strips the game's markup codes; those do not appear in the localization files. |
| `class_map(pid, addresses)` | dict | Address -> class name, through the vtable. `addresses` is a dict {address: vtable}, not a list. |
| `derive_all(pid)` | value | Derive every field from a full scan. Expensive, so once per build. |
| `visibility_fields(pid, fields, root, key=112, subject='character_window', control='council_window')` | value of dict | Derive the two visibility offsets by toggling a window and watching what moves. |
| `position_from_tree(pid, fields, nodes=1000)` | value | Derive the position field a second time, from the live tree instead of the scan. |
| `store(fields)` | nothing | - |
| `stored()` | value of NoneType | - |
| `to_root(address, f_parent)` | 2-tuple | Up until the parent is no longer a widget. `tree` on a non-widget returns nothing, and that |
| `quick_root(fields, pid, at_least=500, ample=1500, samples=40)` | 2-tuple | From seed widgets up to the roots, then return the largest tree. |
| `verify(fields, root, nodes, pid)` | value | Recheck the stored derivation against the game running right now. Three predictions, all |
| `fields_for(pid)` | 2-tuple | The path walked at every start. |
| `configure_channel(fields)` | nothing | Hands the derived offsets to the DLL. The DLL knows nothing about CK3; all knowledge about |
| `regions(pid)` | value | The memory regions of the game, asked for from the outside. |
| `seed_batches(pid, chunk=67108864)` | nothing | Per piece of memory the addresses found, until the caller finds a usable one. |

## ck3\harvest.py
*Phase 1 of the sweep: harvest one window at a time, raw.*

| call | returns | does |
|---|---|---|
| `free_memory()` | value | Free physical memory in gigabytes, straight from Windows. |
| `game_date(nodes)` | NoneType of value | The date the game is showing, from the widget that carries it. |
| `paused(game, seconds=6.0)` | value | Is the clock standing still? Measured, not assumed - a running clock makes the round |
| `subtree(nodes, root)` | value | Every widget below this window, breadth first, with the depth kept. |
| `widget_record(nodes, address, depth, scales, classes, flags, alphas)` | dict | One widget, with every field this project can read - also the ones nothing uses yet. |
| `alphas_for(addresses)` | value | Alpha of many widgets in as few channel questions as possible, the way flags_for does it. |
| `capture(pid, name)` | dict | The window as pixels, plus everything the recogniser reads in it, with positions. |
| `open_window(game, name, row, baseline)` | 2-tuple | Open one window along the route phase 0 found for it, and prove it is drawn. |
| `close_window(game, name, row, baseline, limit=12)` | bool | Shut it again and wait until the state before it is back. Anything left open contaminates |
| `drawn_one(candidates, name)` | value | Of several window objects carrying the same name, the one that is actually drawn. |
| `harvest(game, name, row, baseline, header)` | 2-tuple | One window, from opening to the state coming back. Returns the record, or a reason. |
| `main()` | nothing | - |

## ck3\inject.py
*Starts a program suspended and loads our DLL into it before it runs its first line of code.*

| call | returns | does |
|---|---|---|
| `start_with_dll(exe_path, dll_path, arguments='')` | value | Starts exe_path suspended, loads dll_path into it, resumes the process. Returns the pid. |

## ck3\memory.py
*Reads the interface of a running CK3 out of process memory.*

| call | returns | does |
|---|---|---|
| `widget_vtables()` | value of NoneType | Vtable RVAs of every class descending from CPdxGuiWidget, taken from the exe. |
| `vtables_by_name(part)` | value of NoneType | Vtable RVAs of classes whose RTTI name contains `part` - NOTE: case sensitive. |
| `screen_size()` | 2-tuple | - |
| `type_name_count()` | value | How many RTTI type names the exe contains. |

## ck3\savegame.py
*Reads the game state from a save file - the answer key for searching in memory.*

| call | returns | does |
|---|---|---|
| `newest_save()` | value | - |
| `newest_readable_save()` | value | The newest save that was stored as text. |
| `is_text(content)` | value | - |
| `unpack(path=None)` | value | The game state as text. The header before the zip differs in length per save, so it is |
| `block(text, build_key, start_at=0)` | value of NoneType | The content between the braces of `key={ ... }`, with braces counted so that nested |
| `numbers(content, prefix='', depth=0)` | value | Every whole number in a block, with its path as the name. Whole numbers only, because that |
| `player(text)` | value | The character number of the player. |

## ck3\start_game.py
*Starts CK3 with the channel inside it, in one action.*

| call | returns | does |
|---|---|---|
| `start(timeout=60.0, arguments='')` | 2-tuple | Arguments are passed on to the game; `-debug_mode` opens the console. That flag belongs to |

## ck3\textfield.py
*Finds, per widget class, where the displayed text sits inside the object.*

| call | returns | does |
|---|---|---|
| `normalize(text)` | value | The recogniser does not read perfectly. Compare in lower case without odd characters. |
| `capture(pid, root)` | 3-tuple | Image and tree back to back, or you are comparing two different moments. |
| `screen_boxes(full)` | value | Screen position per widget, summed along the parent chain within the same tree. |
| `candidates(boxes, ox, oy, ob, oh, largest=400.0)` | list | Widgets covering the spot of a screen line, smallest first. |
| `text_offsets(address, needle)` | value of list | Offsets in this object where `needle` sits as a C++ string. |
| `search(pid, root, output)` | value | - |

## ck3\vtablemap.py
*Derives the vtables of the widget classes and hands them to the channel.*

| call | returns | does |
|---|---|---|
| `module_base(number)` | value | Where ck3.exe is loaded. The vtable addresses from the exe are relative to it. |
| `vtables()` | value | Vtable RVAs of the widget classes, from the exe as it is on disk right now. |
| `configure(number)` | 2-tuple | - |

## ck3\windowmap.py
*Phase 0 of the sweep: which window can be opened by which route?*

| call | returns | does |
|---|---|---|
| `windows_on_disk()` | value | Every `window = { name = ... }` in the gui files, with the path the console wants. |
| `classes(pid)` | set | - |
| `shortcut_round(game)` | value | Which shortcut opens which window? One key per test, and every window shut again. |
| `create_round(game, windows, limit=None)` | value | Try every window with GUI.CreateWidget, and clean up immediately. |
| `main()` | nothing | - |

## nvda\speech.py
*Thin seam to NVDA. Everything the user needs to hear passes through here.*

| call | returns | does |
|---|---|---|
| `nvda_running()` | value | - |
| `silence()` | nothing | - |
| `speak(text, mode=REPLACE, braille=None)` | nothing | - |

