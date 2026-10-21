# Tool index - calls and the shape of what they return

Generated from the source by `tools\toolindex.py`. **Read this before writing a
script**, and generate it again once you have changed the tools.
The *returns* column is here because that is where the mistakes were: a function that
returns a pair, passed on as one thing, costs a run.

## boxreader.py
*Reads one known box on the NPU. Two to three times faster than the same route on the CPU.*

| call | returns | does |
|---|---|---|
| `warm_up()` | nothing | Compiling costs a few seconds; after that it sits in the model cache. |
| `read_box_conf(screenshot, x, y, width, height)` | 2-tuple | Returns (text, confidence) of one box. |

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
| `gui_templates(scope)` | value | Templates in the merged set. `type` and `template` are global, `local_type` and |
| `gui_windows()` | value | - |
| `ledger_buildings(what)` | value | What a building box in the ledger can actually do when it is clicked. |
| `gui_dlc(what)` | value | How the gui set gates content behind an expansion, counted over the merged files. |
| `database_entries(kind, what)` | value | Entries of one of the game's databases, merged the way the engine merges them. |
| `cultures_numbered(save)` | value | Cultures whose number in this save is their place in the file order. |
| `ignored(relative)` | value | Does `.gitignore` exclude this path? The same question `git init` asks. |
| `repo_files()` | value | Counts what a `git init` would take into the repo: everything .gitignore does not exclude. |
| `unseen_texts(what)` | value | Texts in the harvest that are in the tree but not on the screen. |
| `document_paths()` | 2-tuple | Every project path named in a document, checked against the disk. |
| `mod_windows(part)` | value | Windows in the map whose gui file is not part of the game itself. |
| `harvest_total(part, field)` | value | A number summed over the harvest records: how big the round was, and how good. |
| `map_layer(what)` | value | A count of the static map layer, recomputed from the game files. |
| `shortcuts(what)` | value | How many key bindings the game defines, counted by kind. |
| `shortcut_words(what)` | value | How far a shortcut can be given a meaning from disk alone. |
| `quoted_numbers(claims, measured)` | 3-tuple | Claims that a document repeats, checked against the file that repeats them. |
| `script_runs()` | 2-tuple | How the documents and the scripts themselves say to start a script, checked against the package. |
| `scripts()` | value | Every Python file of the tools and the tests. |
| `loading_work(files)` | value | Every statement at the top level of these files that does work as the file is loaded. |
| `main(all_of_them)` | value | The checks that need nothing but this repository first, then the claims, which stop at the |

## never_silent.py
*The proof behind the beta gate: a failure speaks instead of falling silent.*

| call | returns | does |
|---|---|---|
| `field_moved(pid, fields)` | nothing | Move an offset in a copy of the derivation and let the ordinary start path trip over it. |
| `main()` | nothing | The field step needs a game with the channel inside it, and a save loaded. |

## ocr.py
*Reads the text on screen, with positions attached.*

| call | returns | does |
|---|---|---|
| `read_image(screenshot)` | list of value | Returns a list of (x, y, width, height, text) in the points of this image. |
| `read_screen()` | value | Returns a list of (x, y, width, height, text) in screen points. |

## paths.py
*The single place paths come from.*

| call | returns | does |
|---|---|---|
| `registry_value(branch, key, field, view=0)` | value of NoneType | One value from the registry, or None when the key or the value is not there. |
| `mod_folders()` | list of value | The folders of the mods that are switched on, in load order. |
| `require(name)` | value | Return a path, or stop with a sentence saying what needs to happen. |

## restore_launcher.py
*Restores launcher-settings.json to the original from before the injector.*

| call | returns | does |
|---|---|---|
| `main()` | nothing | - |

## terminal.py
*What a script prints, readable whatever the game holds.*

| call | returns | does |
|---|---|---|
| `utf8()` | nothing | UTF-8 out, an unprintable character replaced rather than fatal, and a line at a time. |

## toolindex.py
*Writes reports\toolindex.md: every call a script needs, read from the source.*

| call | returns | does |
|---|---|---|
| `first_line(text)` | value | The first line of a docstring, which `ast.get_docstring` has already cleaned. |
| `signature(node)` | value | - |
| `return_shape(node)` | str of value | The shape of what comes out, because that is what the mistakes were about. |
| `files()` | iterator | - |
| `main()` | nothing | - |

## windowgrab.py
*Grabs an image of the game window without it having to be in the foreground.*

| call | returns | does |
|---|---|---|
| `window_of(pid)` | 3-tuple | The largest visible window of that process, with its outer size. |
| `client_size(hwnd)` | 2-tuple | The drawing area inside the window, without title bar and border. |
| `borders(hwnd)` | 2-tuple | Where the drawing area starts inside the window: title bar and border. |
| `grab(pid)` | 3-tuple | Returns (image, width, height) of the game window's drawing area. |

## ck3\anchor.py
*The anchor into the game model: from the exe to a database of the game state, without searching.*

| call | returns | does |
|---|---|---|
| `load_model()` | value | - |
| `store_model(model)` | nothing | - |
| `vtables(pid, name=CLASS)` | list | Every vtable address of the class carrying exactly this RTTI name. |
| `is_ref_database(address)` | bool of value | Does this address carry a believable TPdxRefDatabase? A table, and counts that are not |
| `find_objects(pid, name=CLASS, valid=is_ref_database)` | value | Every believable object of this class, in the order memory gives them. |
| `derive_global(pid, name=CLASS, valid=is_ref_database)` | 2-tuple | The offset of the global variable pointing at one of those objects. |
| `object_of(pid, name=CLASS, valid=is_ref_database)` | value | The object, from the stored offset or else derived again. |
| `database(pid)` | value | The character database. |

## ck3\calibrate.py
*Calibration - does what we read out of the game match what the save says?*

| call | returns | does |
|---|---|---|
| `text_boxes(nodes)` | list | The addresses of the text boxes, found through the vtable that touches the localization files. |
| `test_ocr(pid, nodes, addresses)` | 4-tuple | Reads every text box actually on screen and puts it beside the widget text. |
| `main(pid, count=400, *, save=None)` | nothing | - |

## ck3\channel.py
*Talks to the channel inside the DLL.*

| call | returns | does |
|---|---|---|
| `alive()` | bool | Is the link there? Asked without speaking, for a caller that expects it to be gone. |
| `close()` | nothing | - |
| `ask(command, timeout=60.0, errors_ok=False)` | value | Asks the channel one question and returns the answer as text. |
| `read(address, count)` | NoneType of value | Raw bytes, or None where the game holds nothing readable. Any other refusal of the DLL - a |
| `read_known(address, count)` | value | `read` for an address the caller knows the game holds: unreadable there is a fault, and it |
| `readmany(addresses, count)` | value | Raw bytes per address, in as few questions as both limits allow; an address where the game |
| `field_for(addresses, offset, width=1)` | dict | One field of many objects, as a whole number, keyed by the object. |

## ck3\database.py
*Reads the game's own databases off disk: which key sits at which place, and what it is called.*

| call | returns | does |
|---|---|---|
| `files(branch)` | value | Every file of one database the engine has loaded, in load order, as (layer, virtual, full). |
| `entries(kind)` | list | The keys of one database in the order the files give them, as (key, layer, file). |
| `named(kind, localization=None)` | value | Key -> the sentence a player sees, for every entry that has one. |
| `main()` | nothing | - |
| `culture_numbers(text)` | dict | Number -> culture, as the save of a state gives them. |

## ck3\derive.py
*Derives the field offsets of a widget object from the running game, through the channel.*

| call | returns | does |
|---|---|---|
| `build_key()` | value | How you tell it is still the same build. If the exe changes, everything lapses. |
| `scan(from_address, to_address)` | 2-tuple | Address -> vtable, and what the scan left out. Both come from the vtable comparison and do |
| `skips(answer)` | value | What a scan or find left out. The DLL skips the stacks of its own threads, where copies of |
| `skipped(*searches)` | value | What one or more searches left out, summed, as a clause; empty when nothing was. |
| `tree(root)` | value | - |
| `chunks_of(addresses)` | 2-tuple | Raw bytes per object. Unreadable ones are skipped and counted, not hidden. |
| `children_from_parents(chunks, f_parent, addresses)` | value | - |
| `gui_text()` | value | Every gui file the engine loads, as one text: what the name prediction looks names up in. |
| `localization_text()` | value | Every sentence the localization gives, as one text: what the text prediction looks in. |
| `window_classes_of(pid)` | set | Where the vtables of every class with Window in its name are loaded in this run. |
| `derive_all(pid)` | 2-tuple | Derive every field from a full scan. Expensive, so once per build. The widgets the scan found |
| `all_in_scan(nodes, scanned, left_out)` | nothing | Every widget of the tree has to be in the full scan, or the scan missed some. |
| `visibility_fields(fields, named, player)` | value | Derive the two visibility offsets by toggling a window and watching what moves. |
| `position_from_tree(pid, fields)` | 3-tuple | Derive the position field a second time, from the live tree instead of the scan. |
| `store(fields)` | nothing | - |
| `stored()` | NoneType of value | - |
| `tooltip_root(pid, fields, root)` | value | The root outside the tree that holds the tooltip being shown, found without a scan. |
| `to_root(address, f_parent)` | 2-tuple | Up until the parent is no longer a widget. `tree` on a non-widget returns nothing, and that |
| `quick_root(fields, pid)` | 2-tuple | From seed widgets up to the roots, then return the largest tree. |
| `verify(fields, root, nodes, pid)` | value | Recheck the stored derivation against the game running right now, with predictions that are |
| `fields_for(pid, recheck=True, player=False)` | 3-tuple | The path walked at every start: the derivation, the root of the tree, and what happened. |
| `configure_channel(fields)` | nothing | Hands the derived offsets to the DLL. The DLL knows nothing about CK3; all knowledge about |
| `regions(pid)` | value | The memory regions of the game, asked for from the outside. |
| `seed_batches(pid)` | iterator | Per piece of memory the addresses found, and what the scan of that piece left out, until |

## ck3\guimap.py
*Reads the meaning out of the gui files: which widget shows what.*

| call | returns | does |
|---|---|---|
| `tokens(text)` | value | The file as a flat list of (kind, text, line). Comments and whitespace are dropped here so |
| `parse(text)` | value | A gui file as a list of entries. An entry is a key with at most one of a value and a body. |
| `files(with_mods=True)` | value | Every gui file the engine has loaded, **in load order**, as (layer, virtual path, disk path). |
| `last_wins(found)` | value | Of the files at one virtual path, the last in load order, which replaces the rest whole. |
| `read(path)` | value | - |
| `walk(nodes)` | iterator | Every entry in a parsed file, at any depth. |
| `type_table(rows=None)` | 2-tuple | Every template the engine knows, as name -> definition. |
| `build(key, body, scope, templates, overrides=None, depth=0, in_tooltip=False, above=())` | value | One widget, fully expanded: inherited defaults, mixed-in templates, slots filled. |
| `attribute(node, key)` | value of NoneType | The value of the first attribute with this key, or None when the widget has none. |
| `windows(rows=None, table=None)` | value | Every window on disk, as name -> (virtual path, its entry). |
| `root_finder(table)` | value | Type name -> the end of its inheritance chain, remembered, because the walk repeats itself |
| `tables()` | 4-tuple | Everything a window is expanded with, built once. |
| `window(name, table=None, local=None, known=None)` | value | A window resolved into a widget tree. A file that does not fit the grammar raises GuiError. |
| `decision_widget(name, table, local)` | value | The own gui of a decision, resolved into a widget tree like a window. |
| `localization()` | value | Key -> sentence, from the localization files of the game and of the active mods. |
| `strip_style(text)` | value | The style markup as it is written in the localization files: `#weak ... #!`. |

## ck3\harvest.py
*Phase 1 of the sweep: harvest one window at a time, raw.*

| call | returns | does |
|---|---|---|
| `free_memory()` | value | Free physical memory in gigabytes, straight from Windows. |
| `game_date(nodes)` | value of NoneType | The date the game is showing, from the widget that carries it. |
| `paused(game)` | value | Is the clock standing still? Measured, not assumed - a running clock makes the round |
| `subtree(nodes, root)` | value | Every widget below this window, breadth first, with the depth and the sibling index kept. |
| `widget_record(nodes, address, depth, index, scales, classes, flags, alphas)` | dict | One widget, with every field this project can read - also the ones nothing uses yet. |
| `capture(pid, name)` | dict | The window as pixels, plus everything the recogniser reads in it, with positions. |
| `confirmed(tree, lines, size)` | 3-tuple | (text boxes that should be on screen, how many the recogniser reads back, how many lie |
| `click_routes(windows)` | value | Window -> the button that opens it, from `reports\openers.json`. |
| `open_window(game, name, row, baseline)` | 2-tuple | Open one window along the route phase 0 found for it, and prove it is drawn. |
| `close_window(game, row, baseline)` | bool | Shut it again and wait until the state before it is back. Anything left open contaminates |
| `drawn_one(nodes, candidates, name)` | value | Of several window objects carrying the same name, the one that is actually drawn. |
| `record_window(game, name, nodes, header, route, attempts, file, started)` | dict | Everything this project can read of one drawn window, plus a capture. It stays open. |
| `harvest(game, name, row, baseline, header)` | 2-tuple | One window, from opening to the state coming back. Returns the record, or a reason. |
| `stop_checks(pid, player, player_name, before)` | nothing | The three conditions asked before every window: memory, the channel, and the player. |
| `chain_step(game, route, source, source_row, windows, baseline, header, tables)` | 2-tuple | One chain route from one of its sources: open the source along its own route, press what |
| `chain_round(game, pid, windows, wanted, baseline, header, player, player_name)` | nothing | Every chain route the files offer from a window this round can open by itself. |
| `main()` | nothing | - |

## ck3\inject.py
*Starts a program suspended and loads our DLL into it before it runs its first line of code.*

| call | returns | does |
|---|---|---|
| `start_with_dll(exe_path, dll_path, arguments)` | value | Starts exe_path suspended, loads dll_path into it, resumes the process. Returns the pid. |

## ck3\mapdata.py
*The static map layer: where a county is, what it borders, and how far away things are.*

| call | returns | does |
|---|---|---|
| `province_colours()` | value | Colour -> province number, from `definition.csv`. The colour is the only link between the |
| `province_image()` | value | The map as province numbers, one per pixel. |
| `centres(numbers=None)` | dict | Province number -> (x, y), the mean of its pixels. |
| `touching(numbers=None)` | value | Every pair of provinces whose pixels lie next to each other. |
| `special_links()` | value | The connections the image cannot show: straits and ferries from `adjacencies.csv`. |
| `province_kinds()` | value | Province number -> what it is, from `default.map`: sea, lake, river, impassable. |
| `titles()` | value | Title key -> what it is, what land sits under it, which title it calls its capital, the de |
| `main()` | nothing | - |

## ck3\memory.py
*What the executable says about the game's classes, and the Windows calls that read its memory.*

| call | returns | does |
|---|---|---|
| `image_size()` | value | How far the exe reaches once it is loaded, from its own header (SizeOfImage): the end of |
| `widget_vtables()` | dict | Vtable RVAs of every class descending from CPdxGuiWidget, taken from the exe. |
| `vtables_by_name(part)` | value | Vtable RVAs of classes whose RTTI name contains `part`, case sensitive. |
| `type_name_count()` | value | How many RTTI type names the exe contains. |

## ck3\model.py
*The character record laid out: which offset carries what, derived rather than written down.*

| call | returns | does |
|---|---|---|
| `to_fixed(text)` | value | A decimal from the save as the whole number the game keeps: the point moved five places. |
| `forms(text)` | value | Every byte form this value could be kept in, named. Six of them, and naming them is the |
| `value_of(chunk, offset, form)` | value | - |
| `stored()` | value | - |
| `block_table(address)` | 2-tuple | Where each block of a database starts, and how many of its slots are filled. |
| `records_for(pid, handles)` | 2-tuple | The bytes of each character's record, keyed by handle, with the wrong ones left out. |
| `answer_key(save_path)` | value | What the save says about every landed character, as the text the save writes. |
| `string_at(chunk, offset)` | NoneType of value | An MSVC string laid out in place: characters, then length, then capacity. |
| `long_string_at(chunk, offset)` | NoneType of 2-tuple | (address, length) of a string too long to sit in the record, or None. |
| `names_of(records, offset)` | value | The name of every record, following the pointer for the long ones in one bulk read. |
| `derive_all(pid, rows)` | 6-tuple | Every offset, found by laying the save beside the memory of the running game. |
| `build(pid, rows, against)` | value | Derive and fold the result into the model, keeping the offsets relative to the handle |
| `sample_slots(pid, wanted=200)` | 2-tuple | Slots spread over the whole database, with what their record says about itself. |
| `check(pid, wanted=400)` | list of value | Does the stored derivation still hold against the game running right now? |
| `character(pid, handle)` | value | Every field of one character: the scalars from the record, the rest through the pointers. |
| `derive_player(pid, number)` | value | Where the module keeps the handle of the character being played, derived against a save. |
| `player(pid)` | 2-tuple | The handle of the character being played, and the name that goes with it. |
| `compare(pid, save_path, count=400)` | 5-tuple | Every derived field of many characters, laid beside the save. The regression test. |
| `main()` | nothing | - |

## ck3\modifiers.py
*Do system-level keys reach the game when it is in front? The first step of the modifier round.*

| call | returns | does |
|---|---|---|
| `bring(hwnd)` | value | The foreground, from a process that does not have it: only with the input queues joined. |
| `held(vk)` | value | - |
| `counted()` | value | What the game asked since the previous `count`, which also starts the next interval. |
| `drawn_after(game, wanted)` | value | - |
| `back_to(game, baseline, first_key)` | value | Shut what opened with posted keys, and prove the state is back. |
| `main(pid)` | nothing | - |

## ck3\numbering.py
*Which number means which culture, faith, religion or trait - read from the running game.*

| call | returns | does |
|---|---|---|
| `on_disk(kind)` | value of set | Every key of this database as the files give it, mods merged in the engine's own order. |
| `keys(pid, kind)` | value | Number -> key, from the running game. Disk is used to prove the reading, never to make it. |
| `derive_layout(pid, kind)` | value | Where the key sits in a record of this database, kept under the key of this exe. |
| `main(pid)` | nothing | - |

## ck3\onscreen.py
*What of the widget tree is on screen, and where: the state byte and alpha that decide whether a*

| call | returns | does |
|---|---|---|
| `window_size(pid)` | value | The drawing area of the game window, live from Windows. |
| `use_screen(pid)` | value | Publish the drawing area of this run, because it is not a property of the build. |
| `drawing_area()` | value | - |
| `use_fields(alpha, flag)` | nothing | Publish the two visibility offsets for this build, as the derivation holds them. |
| `flags_for(addresses)` | value | The state byte of many objects. It is a bit pattern, and only `HIDDEN` decides what is drawn. |
| `alphas_for(addresses)` | dict | The alpha of many objects, the way `flags_for` reads the state byte. One that cannot be read |
| `shown(nodes, addresses)` | dict | Of `addresses`, the ones nothing hides, each with its own state byte. |
| `scales_for(addresses)` | value | Per widget (own scale, scale from above). The two sit next to each other, so one read round. |
| `screen_pos(nodes, address, scales)` | 2-tuple | The place on screen: the own position plus that of every parent, with the scale applied. |
| `scale_anchors()` | value | Per scaled container, by its own name or the nearest name above it: does the centring |
| `screen_size(nodes, address, scales)` | 2-tuple | The size as it is drawn: the own size times the own scale times the scale from above. |
| `is_visible(nodes, address)` | bool | Alpha is a property of the whole parent chain: if one ancestor sits at 0 you see nothing, |
| `is_clipped(nodes, address, scales, classes)` | value of bool | Is this widget scrolled out of view inside a list? |

## ck3\openers.py
*Which button opens which window? Clicks them and writes `reports\openers.json`.*

| call | returns | does |
|---|---|---|
| `buttons_on_disk()` | value | Every widget that opens a window when pressed, with how it does it. |
| `live_record(game, pid, window, address=None, nodes=None)` | 4-tuple | The widgets of the window that is drawn right now, in the shape the harvest writes them and |
| `goal_of(target, known)` | 3-tuple | What has to happen before `target` is drawn: a view opens, or a variable is set. |
| `reaches(value, goal)` | value of bool | Does this onclick reach the goal? Setting a variable counts, clearing it does not. |
| `fires_for(source, goal)` | 2-tuple | Every call this disk block fires, split into the ones that reach `goal` and the rest. |
| `chain_routes(start, tables)` | value | Which windows can be reached by acting inside a window a player can already open. Disk only. |
| `draw_order(record)` | value | Address -> its path of sibling numbers from the window down, which is the drawing order. |
| `clickable_map(record, acting)` | value | The buttons of a window that can handle a click, with their draw order. |
| `lands_on(buttons, point)` | value | Which widget handles a click at this point. |
| `reachable_point(buttons, widget_address, rect)` | value of NoneType | A point on this widget that a click really reaches, or None if it is covered everywhere. |
| `spots_for_goal(game, pid, window, goal, tables)` | 6-tuple | Every widget of an open window that the files say reaches `goal`, aligned rather than guessed. |
| `press_toward(game, window, goal, tables)` | 3-tuple | In `window`, open, press the first widget that reaches `goal` and a click can reach. |
| `trigger_spots(row, named, nodes)` | value of list | Where the click for this row could land: the widget itself, or its nameless children. |
| `on_screen(address, nodes, scales, classes)` | str of value of NoneType | Why this widget cannot be clicked, or None when it can. |
| `window_above(address, chain, nodes, scales)` | value of NoneType | A drawn window later in the tree whose rectangle holds this widget's middle, or None. |
| `press(address, nodes, scales, classes, row=None)` | value of NoneType | Click the middle of a widget, but only if it is really on screen. |
| `back_to(game, target)` | value | Shut whatever opened, until `target` is drawn again. |
| `subtree_of(nodes, window)` | value | The addresses under the drawn window object of that name. Every window is built up front, |
| `try_button(game, row, address, nodes, scales, classes, floor, date, number, total, where, fallback=None)` | str of value | Press one button, record what opened, and put the state back. |
| `main()` | nothing | - |
| `chain(pid, window, target)` | nothing | One chain step by hand: in `window`, already open, find what brings `target` up, press the |

## ck3\pairing.py
*Pairs the widget tree on disk with the widget tree the game actually built.*

| call | returns | does |
|---|---|---|
| `widget_children(node, root)` | value | The children of a node that can reach the live tree, in file order. |
| `align_row(disk, live, root)` | value | Two rows of children laid against each other on class and order alone. |
| `live_tree(record)` | 2-tuple | The harvest is a flat list with an address and a parent address; this is it as a tree. |
| `pairs(window, table, local, known, root, record=None, disk_tree=None)` | value | Every live widget of one window with its source on disk, and the data context it inherits. |
| `text_source(source, localization)` | str of value | What fills this widget: a key, a data function, both, or a placeholder. |
| `developer_window(name, path)` | value | Is this window the developers' own tooling rather than something a player opens? |
| `bare_number(text)` | bool of value | A text that is only a number. This is the case the origin question exists for: `150` |
| `unexplained(count, kind, context, built, developer)` | nothing | The texts the gui files do not predict, split the way the decision needed them. |
| `sweep()` | 3-tuple | Every harvested window paired, as one tally. About twenty seconds for 204 windows (measured |
| `main()` | nothing | - |

## ck3\place.py
*From a character in the running game to a place on the map.*

| call | returns | does |
|---|---|---|
| `main(pid)` | nothing | Walk the chain and let it fail: the player, the coverage, and what memory holds extra. |

## ck3\propose.py
*A first draft of a screen file, from what the gui files alone can already decide.*

| call | returns | does |
|---|---|---|
| `texts(node, context=(), inside=None, out=None)` | value | Every text a window holds, in file order, with its subject and the list it sits in. |
| `says(value, localization)` | value | What this text will say: the sentence behind a key, or the function that fills it. |
| `draft(window, table, local, known, localization)` | 2-tuple | One window as a screen file to correct. |
| `comment(sentence, subject)` | value | The part a human reads. One line, so a long sentence is cut rather than wrapped. |
| `main()` | nothing | - |

## ck3\quit_game.py
*Shuts the game down the way a player does, and never any other way.*

| call | returns | does |
|---|---|---|
| `ready(pid)` | 2-tuple | The root of the running game's tree and its window classes, with everything `look` and |
| `look(root, pid, window_classes)` | 4-tuple | The tree of this moment, with what is drawn, where it is, and what class each node is. |
| `press(nodes, scales, classes, name)` | value of NoneType | Click the widget with this name that is really on screen. Returns None, or why not. |
| `listed(drawn)` | value | - |
| `escape_to(root, pid, window_classes, menus)` | 4-tuple | Escape until one of `menus` is drawn, and what is drawn then; stop if it does not come. |
| `exit_save_since(moment)` | value | - |
| `gone()` | bool | Wait until the channel stops answering, which is the game being gone. It asks `alive`, |
| `quit_game(pid)` | nothing | - |

## ck3\reader.py
*The key loop: one unit per keystroke.*

| call | returns | does |
|---|---|---|
| `gui_tables()` | value | The templates of every gui file, once. Three seconds, and they do not change while it runs. |
| `toast_text(pid, containers, above)` | value | The text of the toast that is showing now, or None when none is. |
| `keys_waiting(answer)` | list | - |
| `loop(reader)` | nothing | Every key the game receives comes past here, swallowed or not, because the hook sits in the |
| `give_back()` | nothing | The game gets every key back. This runs before anything is said about why. |
| `main()` | nothing | - |

## ck3\reading.py
*The generic reading rule: a window as the sentences that come out of it.*

| call | returns | does |
|---|---|---|
| `models(node, chain=(), out=None)` | value | Per widget on disk, the data models of the repeated containers above it, outermost first. |
| `live_order(by_parent, top)` | value | The live widgets depth first in child order - the order the game draws them in. |
| `words_of(word)` | value | A name in the game's spelling as words: GetSoldierCount -> soldier count, MAACap -> MAA cap. |
| `name_of(model)` | value | A data function as a word for the player: GetOptions -> options, GetGold|0 -> gold. |
| `fills(source)` | NoneType of value | The data function the gui file puts in this widget, if it puts one there. |
| `on_screen(node, by_address, area)` | bool | Is this widget actually drawn, or only present in the tree? |
| `expansion(window, table, local, known)` | value | The window as the gui files describe it, expanded once and then kept. |
| `words_table()` | value | The localisation, read once. Over a thousand files, so not per keystroke. |
| `explanation(address, by_address, source_of, localization)` | value of NoneType | The tooltip the gui files predict here: the nearest one up the chain. |
| `rows_of(node, by_address, source_of)` | value | The row this unit stands in, per list around it, outermost first, as live addresses. |
| `units(window, tables, record, area)` | value | Every unit this window says, in order, each with the list it belongs to. |
| `screen_rules()` | value | Per window, what a screen file adds on top of the reading rule. |
| `in_order(window, found)` | value | The units with what a screen file names first, first. Stable, so the rest keeps its order. |
| `state_word(state)` | value | `unavailable` in front of a line whose button the game has switched off, or nothing. |
| `spoken(unit)` | value | One unit as it is said. |
| `joined(found)` | value | A bare number and the label beside it under the same parent are one unit, label first. |
| `sentences(found, window)` | value | The units as the lines a player hears: each one what it says, and what explains it. |
| `read(window, tables=None)` | value | One harvested window as the lines it says. |
| `live(pid, window=None, game=None, tables=None)` | 2-tuple | The window that is on top in the running game, as the lines it says. |
| `main()` | nothing | - |

## ck3\savegame.py
*Reads the game state from a save file - the answer key for searching in memory.*

| call | returns | does |
|---|---|---|
| `newest_readable_save()` | value | The newest save that was stored as text. |
| `named(save)` | value | A save by its path, or by any part of its file name in the save folder. |
| `is_text(content)` | value | - |
| `unpack(path)` | value | The game state as text. The header before the zip differs in length per save, so it is |
| `block(text, build_key)` | NoneType of value | The content between the braces of `key={ ... }`, with braces counted so that nested |
| `character_index(text)` | dict | Character number -> where its block starts, in one pass. |
| `player(text)` | value | The character number of the player. |

## ck3\screens.py
*The screen files: what the product says about a screen, and in which order.*

| call | returns | does |
|---|---|---|
| `read(path)` | value | One screen file, parsed. |
| `references(nodes)` | 3-tuple | What a screen file points at: its windows, its data functions, its widget names. |
| `window_contents(node, text, names)` | nothing | Every attribute value and every widget name below this node. |
| `check(folder=SCREENS)` | value | Every screen file against the gui files as they are on disk right now. |
| `main()` | nothing | - |

## ck3\start_game.py
*Starts CK3 with the channel inside it, in one action.*

| call | returns | does |
|---|---|---|
| `start(timeout=60.0, arguments='')` | 2-tuple | Arguments are passed on to the game; `-debug_mode` opens the console. That flag belongs to |

## ck3\states.py
*Play states: wait until a game is up, save it, type into the console, play someone else.*

| call | returns | does |
|---|---|---|
| `wait(pid)` | str | 'game' once a game is on screen, 'menu' on the main menu, 'setup' on the setup screen of a |
| `save(pid, suffix='')` | value | Save through the pause menu; the name of the new save comes back. |
| `console(pid, command)` | value | Type one command into the console and shut it again, with the checks of |
| `holder(save_name, title)` | value | The running number of whoever holds the title, out of a save of that game. |
| `new(pid, title)` | 2-tuple | From the setup screen: start at random, play the holder of the title, save. Both saves. |
| `main()` | nothing | - |

## ck3\vtablemap.py
*Hands the vtables of the widget classes to the channel, where the game has loaded them.*

| call | returns | does |
|---|---|---|
| `module_base(number)` | value | Where ck3.exe is loaded. The vtable addresses from the exe are relative to it. |
| `vtables()` | value | Vtable RVAs of the widget classes, from the exe as it is on disk right now. |
| `configure(number)` | 2-tuple | - |

## ck3\widgettree.py
*The widget tree of the running game, as the channel walks it: every widget with its place, its*

| call | returns | does |
|---|---|---|
| `widgets(root)` | value | The whole tree with fields attached: address -> (vtable, x, y, width, height, parent, name, text). |
| `strip_markup(text)` | value | Strips the game's markup codes; those do not appear in the localization files. |
| `class_map(pid, addresses)` | dict | Address -> class name, through the vtable. `addresses` is a dict {address: vtable}, not a list. |

## ck3\windowmap.py
*Phase 0 of the sweep: which window can be opened by which route?*

| call | returns | does |
|---|---|---|
| `shortcut_file()` | value | Binding -> its keys as `game/gui/shortcuts.shortcuts` spells them, empty for a binding |
| `window_bindings()` | value | Window -> every shortcut its widgets declare, with what pressing it calls. Disk only. |
| `window_keys_plan()` | nothing | Print what a key round inside the windows would press, and what it leaves to a person. |
| `presses_for(rows, bound)` | value | (binding, keys) to press in one window: every view-only row, once. |
| `shown_texts(game, name, text_classes)` | NoneType of value | The texts of window `name` that are on the screen now, in draw order; None if it is not drawn. |
| `window_keys_round(game, names)` | value | Open each window along its route, press every key in it that only changes the view, and say |
| `modified_keys()` | value | Binding -> (spelling, modifier keys, key) for every name in `MODIFIED`, as the file binds it. |
| `key_of(key)` | value | The virtual key for one key as the shortcut file or the map spells it: F1, c, 0, BACKSPACE. |
| `press(spelling)` | nothing | Press a key as the map spells it - `F1`, or a combination such as `shift+F1` - from inside. |
| `windows_on_disk()` | value | Every window the gui files declare, with the path the console wants and how it is declared. |
| `shortcut_round(game, presses=None)` | value | Which shortcut opens which window? One key per test, and every window shut again. |
| `create_round(game, windows, limit=None)` | value | Try every window with GUI.CreateWidget, and clean up immediately. |
| `unmapped(pid, game=None)` | 3-tuple | Which windows the running game built that the map on disk does not know. |
| `keys_only(pid, modified=False)` | nothing | Only the key round, and add what it finds to the map without touching anything else in it. |
| `main()` | nothing | - |

## nvda\check_speech_by_ear.py
*Speech layer checked by ear. It announces itself; you need not read along.*

| call | returns | does |
|---|---|---|
| `main()` | nothing | - |

## nvda\speech.py
*Thin seam to NVDA. Everything the user needs to hear passes through here.*

| call | returns | does |
|---|---|---|
| `client()` | value | - |
| `nvda_running()` | value | - |
| `silence()` | nothing | - |
| `output(text, mode=REPLACE, braille=None)` | nothing | Speak, and write to the braille display in the same breath. |
| `failure(where, what, remedy)` | value | The exit for a failure: one sentence carrying where, what, and what to do now. |

