# Changelog

One item per change, in a line or two: what moved, and why it matters to someone using this. Newest
first, dated the day the work was measured. No release yet — see the entry of 2026-08-23 for what
"first public source" means here.

**This file keeps outcomes, not steps.** A day that is closed is folded into what came out of it,
and an entry a later measurement overturns is taken out rather than left standing with a withdrawal
beside it: git keeps the text, `ARCHITECTURE.md` keeps the reasoning, and `reports/claims.json`
keeps the numbers with the rule they were counted by. A changelog that may never forget only grows.

## 2026-09-19

- `tools/ck3/reading.py`, the generic reading rule, in the half that needs no running game: given
  a harvested window it returns the lines that window says. Four rules, all of them general — a
  widget without text is not a unit, child order is reading order, a repeated container becomes a
  list that says its size and its end, and the game's markup bytes come off. `--speak` sends the
  lines through NVDA. Over the harvest: 1,753 units, 286 of them rows of a list, 22 windows
  carrying a list. The longest single unit is 318 characters, so roughly three sentences.
- `pairing.pairs` takes the expanded tree as an argument. A caller that has already expanded a
  window must hand in that same tree: the nodes handed back belong to the tree that was used, so
  two trees means every lookup on the caller's side misses without saying so.

- Screen files: the presentation layer's tuning lives in data, in the game's own format
  (`key = value`, blocks, `#` comments), one file per screen under `screens/`, read with the gui
  parser the project already has. The first one, `screens/event.screen`, covers the three event
  windows and says what is read first, what stays silent, and how an option reads — with its
  state before its words, and the explain key mapped to what the game puts in the tooltip.
  Nothing is announced on arrival: the count of a list sits against the list it is about.
- `tools/ck3/propose.py` writes a draft screen file for every window straight from the gui files,
  with no harvest and no running game, so a window nobody ever opened gets one too: reading order
  is file order, a repeated container becomes a list, the subject comes from the data context
  inherited, and behind each line stands what it will say. 218 windows, 12,158 texts, 5,150 of
  them rows of a list. Drafts are for correcting, so they are written outside the repository.
- A screen file names no decoration to silence. A widget without text says nothing by itself, and
  text only ever comes out of a text box, so the list of things to keep quiet was doing nothing.
- An option says what it will do to you, in words: the game marks four kinds of consequence per
  option and hands them over as a list — a trait gained or lost, stress up, down or critical, a
  scheme, and death — so they are spoken with the option rather than left inside a tooltip. Gold
  and prestige are not among them; those live in the tooltip only.
- A screen file carries exceptions only. Whatever it does not name is read in the order the gui
  files give, so a file left behind by a patch costs detail and never the screen.
- `tools/ck3/screens.py` checks every reference in a screen file against the expanded gui tree:
  windows, data functions and widget names. Validated by breaking it — an invented data function,
  widget name and window are each reported, while the real file passes. A selector may match more
  than one widget on disk (four in `letter_event` show the description, one per letter layout);
  that is not an error, and the live tree decides which one is on screen.

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
- Three more steps in `tools/never_silent.py`, none of them needing a running game.
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
- `tools/never_silent.py`, the gate in front of a beta: it takes the link away, moves an offset in a
  copy, and counts the silences. No debug mode needed.
- A window can be reached by acting inside another one: `--chain` reads the target's own `visible`
  line to learn what has to happen. That opened the last two closed windows.

## 2026-08-24 – 2026-08-30 — the sweep, and joining the tree to the files

- **The sweep.** 203 of the 218 windows the gui files declare are harvested widget by widget. The
  fifteen refusals are records with a reason: they wait on a state, not on a culture or an era.
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
- **The window reader counts both shapes a window is declared in: 218 where it read 196.** The 22
  it missed are the event windows and confirmation dialogs — the ones a player cannot get past.
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
