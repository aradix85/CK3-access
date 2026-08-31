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
| `channel_commands()` | value | Every command the DLL accepts, read out of its dispatch chain. |
| `channel_names()` | 2-tuple | Command names the documents claim, checked against the DLL - both directions. |
| `gui_merged(with_mods)` | value | Gui files as the engine sees them: the three layers merged, mods on top. |
| `gui_templates(scope)` | value | Templates in the merged set. `type` and `template` are global, `local_type` is not. |
| `gui_windows()` | value | - |
| `gui_dlc(what)` | value | How the gui set gates content behind an expansion, counted over the merged files. |
| `guimap_files()` | value | - |
| `database_entries(kind, what, save=None)` | value | Entries of one of the game's databases, merged the way the engine merges them. |
| `gamestate_mb(part)` | value | - |
| `repo_files()` | value | Counts what a `git init` would take into the repo: everything .gitignore does not exclude. |
| `document_paths()` | 2-tuple | Every project path named in a document, checked against the disk. |
| `mod_windows(part)` | value | Windows in the map whose gui file is not part of the game itself. |
| `harvest_total(part, field)` | value | A number summed over the harvest records: how big the round was, and how good. |
| `quoted_numbers(claims)` | 2-tuple | Claims that a document repeats, checked against the file that repeats them. |
| `main(all_of_them)` | value | - |

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
| `mod_folders()` | value of list | The folders of the mods that are switched on, in load order. |
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
*The anchor into the game model: from the exe to a database of the game state, without searching.*

| call | returns | does |
|---|---|---|
| `vtables(pid, name=CLASS)` | list | Every vtable address of the class carrying exactly this RTTI name. |
| `is_ref_database(address)` | value of bool | Does this address carry a believable TPdxRefDatabase? A table, and counts that are not |
| `find_objects(pid, name=CLASS, valid=is_ref_database)` | value | Every believable object of this class, in the order memory gives them. |
| `derive_global(pid, name=CLASS, valid=is_ref_database, tries=4)` | 2-tuple | The offset of the global variable pointing at one of those objects. |
| `object_of(pid, name=CLASS, valid=is_ref_database)` | value | The object, from the stored offset or else derived again. |
| `database(pid)` | value | The character database. |
| `size(pid, db=None)` | 2-tuple | How many blocks, and therefore how many character slots, this game state has. |

## ck3\calibrate.py
*Calibration - does what we read out of the game match what the save says?*

| call | returns | does |
|---|---|---|
| `save_named(save=None)` | value | The path of the save that serves as the answer key. |
| `text_boxes(nodes)` | list | The addresses of the text boxes, found through the vtable that touches the localization files. |
| `test_ocr(pid, nodes, addresses)` | 4-tuple | Reads every text box actually on screen and puts it beside the widget text. |
| `main(pid, count=400, save=None)` | nothing | - |

## ck3\channel.py
*Talks to the channel inside the DLL.*

| call | returns | does |
|---|---|---|
| `close()` | nothing | - |
| `ask(command, timeout=60.0, errors_ok=False)` | value | Asks the channel one question and returns the answer as text. |

## ck3\database.py
*Reads the game's own databases off disk: which key sits at which place, and what it is called.*

| call | returns | does |
|---|---|---|
| `files(branch)` | value | Every file of one database the engine has loaded, in load order, as (layer, virtual, full). |
| `entries(kind)` | value | The keys of one database in the order the files give them, as (key, layer, file). |
| `named(kind, localization=None)` | value | Key -> the sentence a player sees, for every entry that has one. |
| `main()` | nothing | - |
| `numbering(kind, text=None)` | dict of value | Number -> key, taken from the save rather than guessed from the file order. |

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

## ck3\guimap.py
*Reads the meaning out of the gui files: which widget shows what.*

| call | returns | does |
|---|---|---|
| `tokens(text)` | value | The file as a flat list of (kind, text, line). Comments and whitespace are dropped here so |
| `parse(text)` | value | A gui file as a list of entries. An entry is a key with at most one of a value and a body. |
| `files(with_mods=True)` | value | Every gui file the engine has loaded, **in load order**, as (layer, virtual path, disk path). |
| `read(path)` | value | - |
| `type_table(rows=None)` | 2-tuple | Every template the engine knows, as name -> definition. |
| `build(key, body, templates, overrides=None, depth=0, in_tooltip=False)` | value of dict | One widget, fully expanded: inherited defaults, mixed-in templates, slots filled. |
| `windows(rows=None)` | value | Every window on disk, as name -> (virtual path, its entry). |
| `window(name, table=None, local=None, known=None)` | 2-tuple | A window resolved into a widget tree, with a Templates carrying what went wrong. |
| `localization(language='english')` | value | Key -> sentence, from the localization files of the game and of the active mods. |
| `widgets(node, path=(), context=())` | nothing | One row per widget that carries a name, with where its content comes from. |
| `strip_style(text)` | value | The style markup as it is written in the localization files: `#weak ... #!`. |

## ck3\harvest.py
*Phase 1 of the sweep: harvest one window at a time, raw.*

| call | returns | does |
|---|---|---|
| `free_memory()` | value | Free physical memory in gigabytes, straight from Windows. |
| `game_date(nodes)` | NoneType of value | The date the game is showing, from the widget that carries it. |
| `paused(game, seconds=6.0)` | value | Is the clock standing still? Measured, not assumed - a running clock makes the round |
| `subtree(nodes, root)` | value | Every widget below this window, breadth first, with the depth and the sibling index kept. |
| `widget_record(nodes, address, depth, index, scales, classes, flags, alphas)` | dict | One widget, with every field this project can read - also the ones nothing uses yet. |
| `alphas_for(addresses)` | value | Alpha of many widgets in as few channel questions as possible, the way flags_for does it. |
| `capture(pid, name)` | dict | The window as pixels, plus everything the recogniser reads in it, with positions. |
| `confirmed(tree, lines, size)` | 3-tuple | (text boxes that should be on screen, how many the recogniser reads back, how many lie |
| `click_routes(windows)` | value | Window -> the button that opens it, from `reports\openers.json`. |
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

## ck3\model.py
*The character record laid out: which offset carries what, derived rather than written down.*

| call | returns | does |
|---|---|---|
| `to_fixed(text)` | value | A decimal from the save as the whole number the game keeps: the point moved five places. |
| `forms(text)` | value | Every byte form this value could be kept in, named. Six of them, and naming them is the |
| `value_of(chunk, offset, form)` | value | - |
| `stored()` | value | - |
| `readmany(addresses, count)` | value | Raw bytes per address, in questions whose answer stays under 32 kB. |
| `records_for(pid, handles)` | 2-tuple | The bytes of each character's record, keyed by handle, with the wrong ones left out. |
| `answer_key(save_path, handles=None)` | value | What the save says about every landed character, as the text the save writes. |
| `string_at(chunk, offset)` | value of NoneType | An MSVC string laid out in place: characters, then length, then capacity. |
| `long_string_at(chunk, offset)` | 2-tuple of NoneType | (address, length) of a string too long to sit in the record, or None. |
| `names_of(records, offset)` | value | The name of every record, following the pointer for the long ones in one bulk read. |
| `derive_all(pid, rows, block_bytes=1024)` | 6-tuple | Every offset, found by laying the save beside the memory of the running game. |
| `build(pid, rows, block_bytes=1024, against=None)` | value | Derive and fold the result into the model, keeping the offsets relative to the handle |
| `sample_slots(pid, wanted=200)` | 2-tuple | Slots spread over the whole database, with what their record says about itself. |
| `check(pid, wanted=400)` | value of list | Does the stored derivation still hold against the game running right now? |
| `character(pid, handle, records=None)` | value | Every field of one character: the scalars from the record, the rest through the pointers. |
| `derive_player(pid, number)` | value | Where the module keeps the handle of the character being played, derived against a save. |
| `player(pid)` | 2-tuple | The handle of the character being played, and the name that goes with it. |
| `main()` | nothing | - |
| `compare(pid, save_path, count=400)` | 5-tuple | Every derived field of many characters, laid beside the save. The regression test. |

## ck3\numbering.py
*Which number means which culture, faith, religion or trait - read from the running game.*

| call | returns | does |
|---|---|---|
| `on_disk(kind)` | set | Every key of this database as the files give it, mods merged in the engine's own order. |
| `keys(pid, kind)` | value | Number -> key, from the running game. Disk is used to prove the reading, never to make it. |
| `derive_layout(pid, kind)` | value | Where the key sits in a record of this database, kept under the key of this exe. |
| `main(pid)` | nothing | - |

## ck3\openers.py
*Which button opens which window? Clicks them and writes `reports\openers.json`.*

| call | returns | does |
|---|---|---|
| `buttons_on_disk()` | value | Every widget that opens a window when pressed, with how it does it. |
| `live_record(game, pid, window)` | 4-tuple | The window that is drawn right now, in the shape the harvest writes and the pairing reads. |
| `goal_of(target, known=None)` | 3-tuple | What has to happen before `target` is drawn: a view opens, or a variable is set. |
| `reaches(value, goal)` | bool of value | Does this onclick reach the goal? Setting a variable counts, clearing it does not. |
| `fires_for(source, goal)` | 2-tuple | The call this disk block really fires, split into the one that reaches `goal` and the rest. |
| `draw_order(record)` | value | Address -> its path of sibling numbers from the window down, which is the drawing order. |
| `clickable_map(record, acting=None)` | value | The buttons of a window that can handle a click, with their draw order. |
| `lands_on(buttons, point)` | value | Which widget handles a click at this point. |
| `reachable_point(buttons, widget_address, rect, step=6)` | NoneType of value | A point on this widget that a click really reaches, or None if it is covered everywhere. |
| `gui_tables()` | 4-tuple | The expansion tables, read once. Building them walks 563 files, so a sweep that rebuilds |
| `spots_for_goal(game, pid, window, goal, tables=None)` | 6-tuple | Every widget of an open window that the files say reaches `goal`, aligned rather than guessed. |
| `trigger_spots(row, named, nodes)` | list of value | Where the click for this row could land: the widget itself, or its nameless children. |
| `on_screen(address, nodes, scales, classes)` | NoneType of str | Why this widget cannot be clicked, or None when it can. |
| `press(address, nodes, scales, classes, row)` | NoneType of value | Click the middle of a widget, but only if it is really on screen. |
| `back_to(game, baseline, tries=4)` | value of bool | Shut whatever opened. Escape only when something is open, or it opens the pause menu. |
| `subtree_of(nodes, window)` | value of NoneType | The addresses under the drawn window object of that name, or None. |
| `try_button(game, row, address, nodes, scales, classes, floor, date, number, total, where, fallback=None)` | value of str | Press one button, record what opened, and put the state back. |
| `main()` | nothing | - |
| `chain(pid, window, target, press_it=True)` | value | One chain step: open `window`, find what brings `target` up inside it, press it, put it back. |

## ck3\pairing.py
*Pairs the widget tree on disk with the widget tree the game actually built.*

| call | returns | does |
|---|---|---|
| `root_finder(table)` | value | Type name -> the end of its inheritance chain, remembered, because the walk repeats itself |
| `attribute(node, key)` | NoneType of value | - |
| `widget_children(node, root)` | value | The children of a node that can reach the live tree, in file order. |
| `align_row(disk, live, root)` | value | Two rows of children laid against each other on class and order alone. |
| `live_tree(record)` | 2-tuple | The harvest is a flat list with an address and a parent address; this is it as a tree. |
| `pairs(window, table, local, known, root, record=None)` | value | Every live widget of one window with its source on disk, and the data context it inherits. |
| `text_source(source, localization)` | value of str | What fills this widget: a key, a data function, both, or a placeholder. |
| `sweep()` | 3-tuple | Every harvested window paired, as one tally. Takes about three minutes. |
| `main()` | nothing | - |

## ck3\savegame.py
*Reads the game state from a save file - the answer key for searching in memory.*

| call | returns | does |
|---|---|---|
| `newest_save()` | value | - |
| `newest_readable_save()` | value | The newest save that was stored as text. |
| `is_text(content)` | value | - |
| `unpack(path=None)` | value | The game state as text. The header before the zip differs in length per save, so it is |
| `block(text, build_key, start_at=0)` | value of NoneType | The content between the braces of `key={ ... }`, with braces counted so that nested |
| `character_index(text)` | dict | Character number -> where its block starts, in one pass. |
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
| `output(text, mode=REPLACE, braille=None)` | nothing | Speak and write to the braille display. braille=None means: the same text. |

