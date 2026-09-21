# Changelog

One item per change, in a line or two: what moved, and why it matters to someone using this. Newest
first, dated the day the work was measured. No release yet — see the entry of 2026-08-23 for what
"first public source" means here.

**This file keeps outcomes, not steps.** A day that is closed is folded into what came out of it,
and an entry a later measurement overturns is taken out rather than left standing with a withdrawal
beside it: git keeps the text, `ARCHITECTURE.md` keeps the reasoning, and `reports/claims.json`
keeps the numbers with the rule they were counted by. A changelog that may never forget only grows.

## 2026-09-21

- **A widget the game hides says nothing and is not clicked.** A `visible` condition that does not
  hold leaves the widget in the tree with its alpha up and sets 0x08 in its state byte. Over seven
  windows 2777 of 2784 such widgets carry that condition on themselves or an ancestor, and the text
  recogniser read back none of 79 hidden boxes that passed every other test, against 208 of 214
  shown ones. The reading rule, the click check, the recogniser score and `check.py` all ask it now;
  in the character finder it takes away half the text, such as "No matching Characters for current
  filter" while characters are listed.
- **Seventeen windows open on a key without a modifier, eight more than the F row.**
  `windowmap.py --keys` pressed the ten bindings that can open something on a bare screen and put
  the state and the clock back after each: C opens the character finder with its filter, P the
  epidemics, V find title, F10 the encyclopedia, L the legends, M the message settings and 0 the
  situations.
- **A harvest along shortcut, click and chain runs without debug mode.** It clicks where the live
  tree puts a button now rather than at a point measured at another resolution, treats a window as
  open whichever copy of its name is drawn, and presses a shortcut once when closing instead of
  toggling against Escape.
- **The chain round: `openers.chain_routes` and `harvest.py --chain`.** From the windows a round can
  open itself, every button the files say reaches another window, every source tried in turn. It
  recorded the culture window, the ledger filter and the activity host window, and it measured
  which window stands behind six views whose name is no window name - `faith` is `faith_window`,
  among others - which is written nowhere on disk.
- **Every window with a player route on the test state was harvested again, so that its record
  carries the state byte**, and a second chain round said of every route that failed why: six
  buttons hidden by the game, eight with no live widget carrying the call, three off the screen, and
  no stray click. The first two live refusals of a hidden button point at a click route that names
  the wrong widget. Where a window has both, a shortcut now goes before a click.
- **A button under another window is not clicked.** A window later in the tree is drawn on top, and
  a click on a button whose middle lies inside such a window's rectangle is refused as covered. That
  stands in for the rule the modding wiki gives - a visible widget that is not `alwaystransparent`,
  inside its window unless that allows outside children - and it predicted both cases measured: a
  full-screen event caught a click meant for the event beneath it, and a see-through icon of an event
  let a click on the HUD through. Loading from the main menu and quitting from the pause menu still
  work with it.
- **A toast is said when it appears.** The game shows one toast at a time in one widget that is
  always in the tree, and a toast arriving is the hidden bit leaving that widget's state byte, so
  the reader asks one question a round and says the visible text of that small subtree between the
  lines, without moving the place you stand on. Found and silent on the test state; a real toast
  has not been heard yet.
- **A list is announced once, with the number of its rows, and a list inside a row is folded into
  it.** A row is the live widget under the list widget, so the name and value of one entry count
  once: the character window has 5 skills, not 10 units. One visible inner row is said after the
  outer row - "New Heir, Toast" in the message settings, where the reader used to announce fourteen
  lists of one - more are said as a count, and a list of one row is not announced at all. Over the
  25 windows with a player route, announcements went from 124 to 42 lines and every visible unit is
  still said.
- The window count in the harvest is 205, and every count over it now says how many texts are on
  the screen rather than how many widgets carry text: the encyclopedia holds 2344 texts, all of
  them under alpha zero until an article is chosen.

## 2026-09-20

- **An event reads out loud, live** — the description as one unit, the options with their count and an
  end line, then the character on screen with their opinion. That is the requirement this project
  exists for. When two events stack under the same name, draw order decides which one is read.
- **A window reads out one unit per keystroke.** `tools/ck3/reading.py` turns a window into lines,
  from a harvested record or from the running game, and `tools/ck3/reader.py` hands them out: up and
  down step, F12 switches the reader off and on, Delete reads what explains the line you are on. Four
  keys and no more until somebody has listened to them. It needs no watcher over the windows — the
  hook reports every key the game receives, so a key that is not the reader's means the screen may
  have changed — and an event announces itself through the child counts of the seventeen layers under
  the root, one of which holds nothing but events. A reader that fails gives the keys back before it
  says so, so silence has one meaning: the end of a list.
- **The reading rule says only what is on the screen:** a rectangle outside the drawing area, a row
  clipped inside its scroll area, or an ancestor at alpha zero takes a line out — 172 of 1753 texts over
  the harvest, 48 of 82 in the worst window. Content the game stacks under itself at alpha 1 is not yet
  separated, and a list longer than its frame now ends where the frame does.
- **A bare number says what it is**, named after the data function that fills it: 89 reads as gold
  89. 153 of 169 bare numbers in the harvest get a label that way. A bare number and the label beside
  it under the same parent are one line, label first.
- **A button the game has switched off says so before its words.** The byte the window flag sits at is
  one state byte: on a window zero means drawn, on a button the low bits mean it cannot be used.
  Crossed against the files over three windows and 6906 widgets, no widget carries those bits without
  an `enabled` condition on itself or an ancestor.
- **A line carries what explains it.** The explain key reads the tooltip the gui files put on the
  widget, looked for up the chain; of the 350 lines that reach one, 190 resolve to a sentence, and
  where the sentence has gaps the tool says the game is adding something up instead of reading holes.
- **Screen files are applied, not only checked.** `order` decides which lines come first — the
  character window opens with your own name — and `key` is said once against the line that counts a
  list. `list`, `state` and `explain` are deliberately left unwired, and the file says why. A screen
  file names no decoration to silence: a widget without text says nothing by itself.
- **The window map holds all 265 windows and is checked against the game rather than the files.** Two
  ways of declaring a window had been missed. `windowmap.unmapped` compares what the engine built
  against the map; on the feudal, administrative, landless and Nobatia states nothing is missing. Of the
  189 windows declared at the top level of a file, 189 were created and 177 drawn; the other 76 carry
  the reason their shape has no console route. The round stops when the state does not come back, and
  a trial run takes window names rather than a count.
- **What a player types is readable**, and it sits where ordinary widget text sits.
- **A window reads in about three seconds instead of fourteen**, measured rather than guessed: most of
  it was the executable's RTTI parsed again for every read.
- `tools/ck3/quit_game.py` shuts the game down the way a player does, clicking only the copy of a
  button that is really on screen, with no fallback that kills it. A clean exit no longer announces a
  failure: `channel.alive` asks for the link without speaking.
- `tools/ck3/propose.py` writes a draft screen file for every window straight from the gui files, and
  `tools/ck3/screens.py` checks every reference in a screen file against the expanded gui tree.
- `check.py` no longer fails on a clone over working notes that `.gitignore` keeps out.

## 2026-09-16

- An empty result stays quiet. A keystroke that turns up nothing says nothing, and the wrapper
  that used to speak on every empty handler is gone along with the counter under it. Only a real
  fault speaks, through `failure`. A sentence at every end of a list is noise you hear again on
  every list.
- The speech seam is two functions, `output` and `failure`, and 82 lines shorter. What went with
  the wrapper: a three-class sink hierarchy replaced by one swappable module attribute, which is
  all Python needs to let a test put a recorder in the client's place.
- The beta gate is two steps instead of five, both of them a real failure path. The three that
  exercised the detector against handlers written to make it fire proved nothing about the
  product. It needs no screen reader now, so it talks over nobody, and it checks that braille
  arrived beside every spoken sentence — the one defect measured in the Fallout 4 accessibility
  mod, and invisible to anyone who only listens.
- First tests and first lint configuration: `pytest` over `tests/`, `ruff` over everything, both
  configured in `pyproject.toml`. Five tests on the seam, validated by breaking it — dropping
  braille fails two, dropping the failure sentence fails three.
- tools/nvda/test_speech.py is now `tools/nvda/check_speech_by_ear.py`. Under the old name pytest
  collected it, and importing it runs it, so a test run would have started speaking.
- A braille text may differ from the spoken one, as the exception it was meant to be, with the
  reason at the call site.

## 2026-09-13

- The map layer is done. The two windows still hanging off it are not open work but a measured
  property of the game: neither the move-domicile planner nor the holding view can be opened by
  anything this project can drive.
- The ledger's building button is the case worth knowing, because the file reads like a working
  route: it carries two onclicks, the first opening the holding view and the second not, and only
  the second fires. Clicking three of them in a running game drew nothing, as the expansion had
  already said it would.
- `check.py` gained `ledger_buildings`, which counts that off disk with no game running. For a
  button with two onclicks, ask the expansion what survives before starting the game.

## 2026-09-01

- `tools/ck3/mapdata.py`, the static map layer: where a county is, what it borders, how far and
  how long away another one is, and the de jure titles above it. Disk only, nothing cached.
- Province centres and adjacency come out of `provinces.png` itself — every pixel resolves to a
  province or the build stops. 12750 provinces, 3448 counties with neighbours.
- Distance is approximate on purpose: a fitted projection measured worse than a fixed scale on
  counties it had not seen. Travel days come from a save's own `travel_plans`.
- Any title now resolves to the county under it: a barony through its province, a county is one,
  and anything above through the capital it names on disk. 17577 of 17620 titles land, the rest
  being titular titles that name no capital, and every `realm_capital` in three saves resolves.
- The model derives a nineteenth field, `realm_capital`, which is the title a character calls its
  seat. Going from that number to the title's key is arithmetic on the database blocks rather than
  a scan, checked over three hundred slots against the save.
- The pairing splits the texts the gui files cannot foretell: 631 of 1754, of which 417 inherit
  a data context. Of the 470 in windows a player opens, four are a bare number.
- That withdraws the reason for chasing those origins before the reading layer: a text with no
  source on disk is almost always a caption that names itself.
- Whether a widget can be clicked is judged against the drawing area of the running game rather
  than the 1600x900 that stood in the code. On this machine's 1920x1200 that constant refused 8995
  named widgets out of hand, among them over half the text the recogniser reads back off the
  screen, each with the word "off screen" that reads like a measurement.
- Titles join the numbering read out of the running game, as a third shape: a database whose
  record carries no key but a pointer to the object that does. Where that pointer sits and where
  the key sits behind it are derived, not written down. All 17620 titles the files carry come out
  of it, and the 819 the game holds beyond them are the save's own dynamic templates.
- What a key may look like is now taken from the files rather than written by hand. That test had
  been wrong four times - `yi`, `RICE_hafsa`, `d_al-qays`, `b_ka'abir` - and each time it threw
  away a perfect reading while looking exactly like a moved offset.
- `tools/ck3/place.py` walks the whole chain in one call: a character, the title it calls its
  seat, that title's key from the running game, and the county the files put under it.

## 2026-08-31

- `speech.failure(where, what, remedy)`: one exit for a failure — where, what, what to do now —
  written out before it is spoken, so an exit that cannot reach NVDA still cannot lose the message.
- `tools/never_silent.py`, the gate in front of a beta: it takes the link away and moves an offset in
  a copy, and each has to be heard. No debug mode needed.
- A window can be reached by acting inside another one: `--chain` reads the target's own `visible`
  line to learn what has to happen. That opened the last two closed windows.

## 2026-08-24 – 2026-08-30 — the sweep, and joining the tree to the files

- **The sweep.** 203 windows are harvested widget by widget. The fifteen refusals are records with a
  reason: they wait on a state, not on a culture or an era.
- **A window has to be opened the way a player opens it**, or the record holds captions and no
  data: 6.6 text boxes per window through the console, 23.7 through a shortcut, 32.8 through a
  click. `harvest.py` knows all the routes; `openers.py` measures which button opens which window
  by pressing it, because nothing on disk binds a view name to a window.
- **`pairing.py` joins the two trees on structure rather than name**, so meaning reaches the
  widgets carrying none — more than nine in ten of those showing text. Names stay out of the
  alignment and score it instead: 98.4 per cent land right.
- **`guimap.py` parses the gui format properly** and expands a window off disk, three engine layers
  and active mods merged in load order — which carries meaning, since the last definition wins.
- **`model.py` derives the character record instead of writing it down**, and checks itself at
  start-up on predictions that fail if an offset moved. `calibrate.py` holds four hundred
  characters against a save and names the field that disagrees. Seven fields are recomputed around
  loading, so the save a state was loaded *from* is not a valid answer key for them.
- **Numbers become names without a save.** `database.py` reads the game's own databases the way the
  engine merges them; `numbering.py` takes the numbering out of the running game, because memory
  carries the numbering of the save that was loaded — against another state, 2 of 237 faiths are
  right.
- **`model.player` reads the played character out of the running game**, and the harvest asks
  before every window: a state moved to another character looks perfectly normal from the tree.
- **Visibility got its remaining mechanisms**, all derived rather than hard-coded, and anything
  that clicks needs the nearest window ancestor to be drawn — not just alpha and size.
- **Draw order lives in one place and was nearly lost:** the harvest sorted children by address and
  destroyed the engine's order. Every widget now records its sibling index.
- **No window is gated behind an expansion:** a missing DLC takes away parts of a window, never the
  window.
- **Braille is no longer optional** in the speech seam, and `tools/nvda/addon/` puts NVDA in sleep
  mode while the game has focus, so the reader is not talked over and keeps the keys it needs.
- **Everything public is English**, and `check.py` grew two teeth: a number a public document
  quotes is held to the measured value, and a bare file name in backticks has to exist.
- **A modifier key cannot be posted into the game**, and **hovering cannot be provoked from outside
  the process** — which settles that the game does not see our cursor, not that tooltips live
  outside the widget tree.

## 2026-08-23 — first public source

Not a release: there is no installable mod and nothing is spoken during normal play. What is here is
the machinery, measured on Crusader Kings III 1.19.0.6 with all DLC and five content mods.

- The injected channel answers about twenty seconds after launch; the interface exists some minutes
  later.
- Seven memory field offsets are derived from the running process at every start and re-verified (two
  more followed a day later); on build 1.16.2 one had moved and it re-derived itself.
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
