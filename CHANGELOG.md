# Changelog

One item per change, in a line or two: what moved, and why it matters to someone using this. Newest
first, dated the day the work was measured. No release yet — see the entry of 2026-08-23 for what
"first public source" means here.

**This file keeps outcomes, not steps.** A day that is closed is folded into what came out of it,
and an entry a later measurement overturns is taken out rather than left standing with a withdrawal
beside it: git keeps the text, `ARCHITECTURE.md` keeps the reasoning, and `reports/claims.json`
keeps the numbers with the rule they were counted by. A changelog that may never forget only grows.

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
- `speech.answering(where)`: a block that has to produce a sentence and says so when it does
  not. An exception counts as silence too, and is left to carry on.
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

- **The sweep.** 203 of the 218 windows the gui files declare are harvested widget by widget, with
  a capture and the recogniser's reading beside each one. The fifteen refusals are records with a
  reason, not gaps: they wait on a state, not on a culture or an era.
- **A window has to be opened the way a player opens it**, or the record holds captions and no data:
  6.6 text boxes per window through the console against 23.7 through a shortcut and 32.8 through a
  click. `tools/ck3/harvest.py` knows all the routes; `tools/ck3/openers.py` measures which button
  opens which window by pressing it, because nothing on disk binds a view name to a window.
- **`tools/ck3/pairing.py` joins the two trees on structure rather than on name**, so meaning in the
  gui files reaches the widgets that carry none — more than nine in ten of the ones showing text.
  Names stay out of the alignment and score it instead: 98.4 per cent land right.
- **`tools/ck3/guimap.py` parses the gui format properly** and expands a window into the tree the
  engine would build, off disk, with the three engine layers and the active mods merged in load
  order. Load order carries meaning: the last definition of a template wins.
- **`tools/ck3/model.py` derives the character record instead of writing it down** — eighteen
  fields, reproducing at the same offsets the three that had been measured by hand — and checks
  itself at start-up on four predictions that fail if an offset moved. `tools/ck3/calibrate.py`
  holds four hundred characters against a save and names the field that disagrees.
- **Seven fields are recomputed around loading**, so the save a state was loaded *from* is not a
  valid answer key for them; `calibrate.py` reports those apart from a genuinely moved offset.
- **Numbers become names without a save.** `tools/ck3/database.py` reads the game's own databases
  the way the engine merges them — all 463 culture keys also resolve in the localisation files,
  which is what says the reader read the right part — and `tools/ck3/numbering.py` takes the
  numbering out of the running game, because memory carries the numbering of the save that was
  loaded and against another state 2 of 237 faiths come out right.
- **`model.player` reads the played character out of the running game**, kept in six places inside
  the module; the harvest asks before every window, because a state moved to another character
  looks perfectly normal from the tree.
- **Visibility got its remaining two mechanisms.** Alpha and the window flag are derived by changing
  the state rather than hard-coded; a row scrolled out of its list keeps alpha 1.0; and anything
  that clicks needs the nearest window ancestor to be drawn, not just alpha and size.
- **Draw order lives in one place and was nearly lost:** the harvest sorted children by address and
  destroyed the engine's order, which decides what is drawn on top. Every widget now records its
  sibling index, and with that kept the two trees line up child by child.
- **A capture is taken with the console shut**, after a whole sweep came out blind on the left third
  of the screen with nothing to say so; each record now carries how many of its own text boxes the
  recogniser read back.
- **The window reader counts both shapes a window is declared in: 218 where it read 196.** The 22 it
  had missed are the scheme conclusions, the event windows and the confirmation dialogs — the ones a
  player cannot get past.
- **No window is gated behind an expansion.** Over all of them, not one window block carries a DLC
  check: a missing expansion takes away parts of a window, never the window.
- **`tools/nvda/speech.py`: braille is no longer optional**, and the call is `output` rather than
  `speak`, since speaking is half of what it does. `tools/nvda/addon/` puts NVDA in sleep mode while
  the game has focus, so the reader is not talked over and keeps the keys it needs.
- **Everything public is English** — names, comments, messages, the channel protocol, report keys.
- **`tools/check.py` grew two teeth:** a number a public document quotes is held to the measured
  value, and a bare file name in backticks has to exist. The second closed a real hole — the
  documentation promised a recovery file that was never there.
- **A modifier key cannot be posted into the game**, which reads raw input from the device. Nothing
  in the product needs one; see `ARCHITECTURE.md`, section 4.
- **Hovering cannot be provoked from outside the process.** That settles that the game does not see
  our cursor — not that tooltips live outside the widget tree.

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
