r"""Phase 0 of the sweep: which window can be opened by which route?

Writes reports\windows.json: per window, whether GUI.CreateWidget produces it, whether a shortcut
opens it, and if not, what the engine says about it. Runs on a loaded, paused game started with
-debug_mode.

Usage:  python -m tools.ck3.windowmap <pid> [<count> | <window> <window> ...]
        python -m tools.ck3.windowmap <pid> --keys
        python -m tools.ck3.windowmap <pid> --modified-keys
        python -m tools.ck3.windowmap --window-keys

A count or a list of window names makes it a trial run, and a trial run writes its result beside
the map instead of over it. `--keys` runs only the key round, needs no -debug_mode, and adds the
windows it opens to the map as shortcut routes without changing anything else in it.
`--modified-keys` does the same for the bindings with a modifier, posted through the channel's
`combo`, so the foreground is never taken. `--window-keys` needs no game: it reads off disk which
keys every window declares and which of them only change the view.
"""
import collections
import functools
import json
import os
import pathlib
import re
import sys
import time
from collections.abc import Callable
from typing import TypedDict

from tools import paths, terminal
from tools.ck3 import channel, derive, memory, vtablemap

OUT = os.path.join(paths.REPORTS, 'windows.json')
# The keys a round presses on a bare screen. The F row, plus every binding in shortcuts.shortcuts
# without a modifier whose name says it can bring something up there: situations 0, character
# finder C, find title V, plagues P, legends L, message settings M, outliner Q, intent N, the action
# list Tab and the encyclopedia F10. Left out by name, because they move the clock, the camera or
# the map rather than open anything: pause, the speed keys, zoom, go to capital, map modes, army
# orders, the barbershop and ruler designer keys, the editors, and the mouse buttons. A key bound
# only inside a window does nothing on a bare screen; that is the chain's work.
KEYS = {112: 'F1', 113: 'F2', 114: 'F3', 115: 'F4', 116: 'F5',
        117: 'F6', 118: 'F7', 119: 'F8', 120: 'F9', 121: 'F10',
        48: '0', 67: 'C', 86: 'V', 80: 'P', 76: 'L', 77: 'M', 81: 'Q', 78: 'N', 9: 'TAB'}
# The bindings with a modifier that a round presses on a bare screen: every one a widget in hud.gui
# declares that brings something up. Left out by name: open_capital, which moves the camera, and
# the two notification bindings, which change the notifications they act on. Every other binding
# with a modifier lives inside a window or is a map mode. The keys come from shortcuts.shortcuts, so a
# patch that rebinds one is followed. They go in through the channel's `combo`, which holds the
# modifier for the game; a posted key alone carries no modifier state (`tools\ck3\modifiers.py`).
MODIFIED = ('ledger_window', 'hud_faith', 'hud_personal_beliefs', 'hud_culture', 'activity_shortcut',
            'government_hud', 'domicile', 'war_view', 'college_of_cardinals')
# The pause `combo` leaves after every step when a combination is posted, so the game takes each
# step in a frame of its own. Assumed, not measured: a paused game on this laptop draws well over
# ten frames a second.
COMBO_PAUSE = 100
# What a key inside a window does is what its widget's onclick calls, and some of those change the
# game rather than the view: Alt+C accepts an interaction, Alt+1 in the court window is a mass
# prisoner action, Alt+R in the army window splits an army. So this lists what may be pressed, and
# everything else is listed for a person to decide - an unknown call is never pressed by default.
# The top-level calls below were read from the onclicks of every binding in every window on
# 2 October 2026; each only switches a tab, a filter, a fold, a map mode, or opens or shuts a view.
VIEW_ONLY = re.compile(r'^(?:(?:Get)?VariableSystem\.(?:Set|Clear|Toggle|SetOrToggle)|SetMapMode'
                       r'|OpenGameView|ToggleGameView|CharacterWindow\.SetTab|MyRealmWindow\.SetActiveTab'
                       r'|MyRealmWindow\.ResetMapMode|SetContestInfoTab|\w+Window\.SetTraditionCategory'
                       r'|LedgerListFilter\.SetCurrentFilter|PdxGuiFoldOut\.(?:Fold|Unfold)'
                       r'|InteractionEffectsDescription\.Show\w+|CouncilWindow\.Set\w*Council'
                       r'|TenetWindow\.Toggle|ReligionWindow\.Close|RiteWindow\.Close'
                       r'|InventoryView\.ClearSelectedSlot|BarbershopBackgroundCategory\.ToggleTextSearch'
                       r'|Activity\.OpenActivityView|TravelPlanner\.OpenTravelOptionSelectionWindow'
                       r'|PdxGuiTriggerAllAnimations|PlaySfxEvent|CloseGameView|OpenFromViewHistory'
                       r'|OpenGameViewData|ToggleGameViewData|PdxGuiTabs\.SetTab'
                       r'|\w+\.(?:Close|Hide|CloseAndDeselect|CloseSubwindows|NavigateBack)'
                       r'|\w+\.(?:Set\w*Tab|SetActiveTab|Open\w*Tab|SetShow\w+)'
                       r'|BattleSummaryWindow\.(?:OnShow\w+|RestoreSort)|CultureWindow\.HideReformationMode'
                       r'|CharacterLifestyleWindow\.OpenLifestyle|EpidemicsWindow\.ClearFocusedEpidemic'
                       r'|DiarchyWindow\.ToggleAvailableDiarchs)$')


class Binding(TypedDict):
    """One shortcut a widget declares, filed under the window it sits in (`window_bindings`)."""
    binding: str
    keys: str | None
    widget: str | None
    calls: list[str]
    view_only: bool


class OnDisk(TypedDict):
    """A window as the gui files declare it (`windows_on_disk`)."""
    file: str
    shape: str
    console: bool


class Route(TypedDict, total=False):
    """One window of `reports\\windows.json`, or a click route that `harvest.click_routes` builds
    from `reports\\openers.json`: what `harvest.open_window` and `close_window` go by. Phase 0 writes
    the declaration, the shortcut and the console round; a click route carries the button, the
    point it was found at, and the window to open first with the key that opens it."""
    file: str | None
    shape: str
    console: bool
    shortcut: str | None
    created: bool | None
    drawn: bool
    message: str
    cleaned_up: bool | None
    nodes_added: int
    seconds: float
    reason: str
    click: list[int] | bool
    button: str
    first: tuple[str, str]


class WindowMap(TypedDict):
    """`reports\\windows.json` as a whole."""
    measured: str
    exe: str
    windows: dict[str, Route]


# One press of `shortcut_round`: its name, the action, and whether it goes in a second time.
Press = tuple[str, Callable[[], object], bool]


def shortcut_file() -> dict[str, str]:
    """Binding -> its keys as `game/gui/shortcuts.shortcuts` spells them, empty for a binding
    without keys. Read at every call, so a patch that rebinds a key is followed."""
    text = pathlib.Path(os.path.join(paths.require('GAME'), 'game', 'gui', 'shortcuts.shortcuts')).read_text(encoding='utf-8-sig')
    return dict(re.findall(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"', text, re.MULTILINE))


def window_bindings() -> dict[str, list[Binding]]:
    """Window -> every shortcut its widgets declare, with what pressing it calls. Disk only.

    Each window is expanded the way `guimap.window` expands it, and a binding is filed under the
    innermost window it sits in, because a window inside another is an object of its own. What sits
    under a `tooltipwidget` is left out: a tooltip is built when the pointer arrives and its keys do
    nothing until then. A shortcut may be a name the gui computes - `[Concatenate('tab_', ...)]` -
    and then `binding` is that expression and `keys` is None; which numbers it reaches depends on
    how many rows the live window has.

    Every row says `view_only`: True when every onclick of the widget is a call `VIEW_ONLY` lets
    through, so a round can press it without changing the game.
    """
    from tools.ck3 import guimap
    bound = shortcut_file()
    table, local, known, _root = guimap.tables()
    out: collections.defaultdict[str, list[Binding]] = collections.defaultdict(list)

    def walk(node: guimap.Node, window: str, top: bool) -> None:
        if node['type'] == 'tooltipwidget':
            return
        names = [v.strip('"') for k, v in node['attrs'] if k == 'name' and v is not None]
        if names and names[0] in known and not top:
            window = names[0]
        clicks = [v for k, v in node['attrs'] if k == 'onclick' and v is not None]
        calls = [m.group(1) for m in (re.match(r'\s*"?\[\s*([A-Za-z_][\w.]*)', c) for c in clicks) if m]
        for key, value in node['attrs']:
            if key == 'shortcut' and value is not None:
                binding = value.strip('"')
                out[window].append({'binding': binding, 'keys': bound.get(binding),
                                    'widget': names[0] if names else None, 'calls': calls,
                                    'view_only': bool(calls) and all(VIEW_ONLY.match(c) for c in calls)})
        for child in node['children']:
            walk(child, window, False)

    for window in sorted(known):
        tree, _ = guimap.window(window, table, local, known)
        walk(tree, window, True)
    return dict(out)


def window_keys_plan() -> None:
    """Print what a key round inside the windows would press, and what it leaves to a person.

    Counted once per window, binding and calls: a row template repeated down a list declares the
    same key on every row, and counting rows made the pin key 828 instead of one per window.
    """
    found = window_bindings()
    pairs = {(window, r['binding'], r['keys'], tuple(r['calls']), r['view_only'])
             for window, rows in found.items() for r in rows}
    modified = [p for p in pairs if p[2] is None or re.search(r'alt|ctrl|shift', p[2], re.IGNORECASE)]
    print(f'{len(found)} windows, {len(pairs)} keys in them; view only {int(sum(p[4] for p in pairs))}, left to a person {int(sum(not p[4] for p in pairs))}; with a modifier or '
          f'computed {len(modified)}, of those view only {int(sum(p[4] for p in modified))}')
    left = collections.Counter((binding, keys or 'computed', ' '.join(calls) or 'no onclick')
                               for _, binding, keys, calls, view in pairs if not view)
    # Most windows first, and a tie in alphabetical order: the counts come out of a set, whose
    # order Python changes from run to run, so without it two runs print the same lines shuffled.
    for (binding, keys, calls), count in sorted(left.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {int(count):3d} windows  {binding[:28]!s:<28} {keys!s:<12} {calls[:80]}")


def presses_for(rows: list[Binding], bound: dict[str, str], numbers: int = 3) -> list[tuple[str, str]]:
    """(binding, keys) to press in one window: every view-only row, once.

    A computed name stands for a family - `[Concatenate('tab_', ...)]` reaches tab_1, tab_2 and on
    as far as the live window has rows - so it becomes its first `numbers` bindings that have a key.
    A quoted piece that is a binding itself, as in `[Select_CString(..., 'tab_3', 'tab_2')]`, is
    taken as it is.
    """
    out: list[tuple[str, str]] = []
    for row in rows:
        if not row['view_only']:
            continue
        if not row['binding'].startswith('['):
            names = [row['binding']]
        else:
            names = []
            for piece in re.findall(r"'([A-Za-z_][A-Za-z0-9_]*)'", row['binding']):
                if piece in bound:
                    names.append(piece)
                else:
                    family = sorted((int(n[len(piece):]), n) for n in bound
                                    if n.startswith(piece) and n[len(piece):].isdigit())
                    names += [n for _, n in family[:numbers]]
        for name in names:
            if bound.get(name) and (name, bound[name]) not in out:
                out.append((name, bound[name]))
    return out


def shown_texts(game: 'Game', name: str, text_classes: set[int]) -> tuple[str, ...] | None:
    """The texts of window `name` that are on the screen now, in draw order; None if it is not drawn.

    A text counts when `derive.shown` says it is drawn: no 0x08 from it up to the root, the bit the
    game sets on what a `visible` condition hides - and a tab hides its neighbours that way - and
    no byte on the way that cannot be read. Text is read only on a text class, because the text
    field of anything else reads its neighbour in memory.
    """
    from tools.ck3 import harvest
    nodes = game.tree()
    candidates = [a for a, k in nodes.items() if k[6] == name and k[0] in game.window_classes]
    drawn = list(derive.shown(nodes, candidates))
    if not drawn:
        return None
    if len(drawn) > 1:
        raise SystemExit(f'{len(drawn)} drawn windows are called {name}; which one to read is not decided')
    texts = [a for a, _, _ in harvest.subtree(nodes, drawn[0])
             if nodes[a][0] in text_classes and nodes[a][7]]
    visible = derive.shown(nodes, texts)
    return tuple(derive.strip_markup(nodes[a][7]) for a in texts if a in visible)


def window_keys_round(game: 'Game', names: list[str]) -> dict[str, str | list[tuple[str, str, str]]]:
    """Open each window along its route, press every key in it that only changes the view, and say
    per key what happened: the texts on screen changed, another window opened, the window shut, or
    nothing. The state is put back after every key and must come back after every window.

    What it measures is the window's own text, not the set of drawn windows, because a tab opens
    nothing - a round that watched windows only would call every tab key dead. A key that leaves
    the text unchanged may still act (a fold that hides no text, a map mode behind the window), so
    `nothing` here means no text moved, not that the key is unbound.
    """
    from tools.ck3 import harvest
    with open(OUT, encoding='utf-8') as file:
        windows: dict[str, Route] = json.load(file)['windows']
    bound = {n: k for n, k in shortcut_file().items() if k.strip()}
    plan = window_bindings()
    base = vtablemap.module_base(game.pid)
    text_classes = {base + v for name in derive.TEXT_CLASSES
                    for v in memory.vtables_by_name(name) or []}

    def drawn_texts(name: str) -> tuple[str, ...]:
        """The texts of a window that stands open: just opened, or still there after a key."""
        texts = shown_texts(game, name, text_classes)
        if texts is None:
            raise SystemExit(f'{name} stands open and is not drawn')
        return texts

    _, _, baseline = game.state()
    out: dict[str, str | list[tuple[str, str, str]]] = {}
    for name in names:
        row = windows[name]
        nodes, _ = harvest.open_window(game, name, row, baseline)
        if nodes is None:
            out[name] = 'did not open'
            print(f'{name}: did not open')
            continue
        time.sleep(1.0)
        before = drawn_texts(name)
        results: list[tuple[str, str, str]] = []
        for binding, keys in presses_for(plan.get(name, []), bound):
            try:
                press(keys)
            except KeyError:
                results.append((binding, keys, 'no key code for this spelling'))
                continue
            time.sleep(1.4)
            _, _, drawn = game.state()
            after = shown_texts(game, name, text_classes)
            opened = sorted(drawn - baseline - {name})
            if after is None:
                what = 'shut the window'
            elif opened:
                what = 'opened ' + ', '.join(opened)
            elif after != before:
                what = f'changed the text: {len(after)} lines, was {len(before)}'
            else:
                what = 'nothing'
            results.append((binding, keys, what))
            print(f'  {name[:24]!s:<24} {keys!s:<14} {binding[:16]!s:<16} {what}')
            for _ in range(3):
                if not drawn - baseline - {name}:
                    break
                channel.ask('sendkey 27')
                time.sleep(1.2)
                _, _, drawn = game.state()
            if name not in drawn:
                nodes, _ = harvest.open_window(game, name, row, baseline)
                if nodes is None:
                    raise SystemExit(f'{name} did not open again after {keys}')
                time.sleep(1.0)
            before = drawn_texts(name)
        out[name] = results
        if not harvest.close_window(game, row, baseline):
            raise SystemExit(f'after {name} the state did not come back; shut it by hand')
        if not harvest.paused(game):
            raise SystemExit(f'after {name} the clock is running; pause the game by hand')
    return out


def modified_keys() -> dict[str, tuple[str, list[int], int]]:
    """Binding -> (spelling, modifier keys, key) for every name in `MODIFIED`, as the file binds it."""
    from tools.ck3 import modifiers
    bound = shortcut_file()
    out = {}
    for name in MODIFIED:
        *held, key = bound[name].lower().split('+')
        code = 0x6F + int(key[1:]) if re.fullmatch(r'f\d{1,2}', key) else ord(key.upper())
        out[name] = ('+'.join(held + [key.upper()]), [modifiers.MODIFIERS[m] for m in held], code)
    return out


# Keys the shortcut file spells by name, as virtual keys. A letter, a digit and F1 to F24 follow
# from their spelling; these do not.
NAMED_KEYS = {'TAB': 9, 'BACKSPACE': 8, 'RETURN': 13, 'ESCAPE': 27, 'SPACE': 32, 'HOME': 36,
              'END': 35, 'PAGE_UP': 33, 'PAGE_DOWN': 34, 'LEFT': 37, 'UP': 38, 'RIGHT': 39,
              'DOWN': 40, '-': 0xBD, '=': 0xBB}


def key_of(key: str) -> int:
    """The virtual key for one key as the shortcut file or the map spells it: F1, c, 0, BACKSPACE.
    A spelling it does not know raises KeyError, and the caller says which."""
    key = key.upper()
    if re.fullmatch(r'F\d{1,2}', key):
        return 0x6F + int(key[1:])
    if re.fullmatch(r'[A-Z0-9]', key):
        return ord(key)
    return NAMED_KEYS[key]


def press(spelling: str) -> None:
    """Press a key as the map spells it - `F1`, or a combination such as `shift+F1` - from inside.

    A combination goes through the channel's `combo`, which holds the modifier for the game; a
    posted key alone carries no modifier state. Since 2 October 2026 the map carries six windows
    whose only key is a combination, and pressing those as a plain key was a lookup that failed.
    """
    from tools.ck3 import modifiers
    *held, key = spelling.lower().split('+')
    code = key_of(key)
    if held:
        channel.ask(f"combo {int(COMBO_PAUSE)} {' '.join(str(c) for c in [modifiers.MODIFIERS[m] for m in held] + [code])}")
    else:
        channel.ask(f'sendkey {int(code)}')


def windows_on_disk() -> dict[str, OnDisk]:
    """Every window the gui files declare, with the path the console wants and how it is declared.

    **The enumeration comes from `guimap.windows`, not from a second reader here.** This one used
    to match lines for `window = { name = ... }`, which is one of three shapes a window is declared
    in: on 20 September 2026 it counted 197 where the parser counted 265, so a round run from it
    would have written a map worse than the one it replaced. One reader, one answer.

    **Only one of those three shapes has a console route, and saying so is the point of this.**
    `GUI.CreateWidget` looks a widget up by name in a file and finds only what is declared there at
    depth zero. A window declared through a type of its own, or as a block inside another window,
    answers `could not find widget` - which is a property of the route and not of the window.
    Writing that down as `created: False` produces a map claiming a third of the windows do not
    exist, and overwrites one that knew better. So the shape is decided here, before anything is
    pressed, and the windows without a console route are never tried.

    The engine merges the three layers into one virtual folder: `game/gui/x.gui`,
    `clausewitz/gui/x.gui` and `jomini/gui/x.gui` are all called `gui/x.gui` as far as the console
    is concerned. Measured 23 August 2026: with the layer name in front it fails with "could not
    find description", without it the window comes up. `guimap` already hands over that virtual
    path, so nothing has to be stripped here.
    """
    from tools.ck3 import guimap
    rows = guimap.files()
    known = guimap.windows(rows)
    top_level: set[str] = set()
    for _, _, full in rows:
        for entry in guimap.read(full):
            if entry['key'] != 'window' or not entry['body']:
                continue
            for inner in entry['body']:
                if inner['key'] == 'name' and inner['value']:
                    top_level.add(inner['value'])
                    break
    out: dict[str, OnDisk] = {}
    for name, (virtual, entry) in known.items():
        shape = ('top level' if name in top_level else
                 'type definition' if entry['key'] != 'window' else
                 'nested window block')
        out[name] = {'file': virtual, 'shape': shape, 'console': name in top_level}
    return out


def classes(pid: int) -> set[int]:
    base = vtablemap.module_base(pid)
    return {base + v for v in (memory.vtables_by_name('Window') or [])}


class Game:
    """The actions on the running game, each with the measurement that says whether it landed."""

    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.fields, _ = derive.fields_for(pid)
        derive.configure_channel(self.fields)
        self.window_classes = classes(pid)
        self.root, _ = derive.quick_root(self.fields, pid)
        self.field: int | None = None        # address of console_edit
        # The click point of that field; it does not change while the game runs.
        self.pos: tuple[int, int] | None = None

    def tree(self) -> derive.Nodes:
        """The root is looked up once. Looking it up every round cost fifty seconds per window
        on 23 August 2026; with the root remembered it is a few."""
        return derive.widgets(self.root)

    def state(self, nodes: derive.Nodes | None = None) -> tuple[derive.Nodes, collections.Counter[str], set[str]]:
        """(the tree, number of instances per widget name, names of what is drawn).

        Count all widgets and not just the window class: a created widget of another class
        otherwise counted as a failure, which produced four false failures on 23 August 2026.
        """
        nodes = nodes if nodes is not None else self.tree()
        windows = [a for a, k in nodes.items() if k[0] in self.window_classes]
        counts = collections.Counter(k[6] for k in nodes.values() if k[6])
        drawn = {nodes[a][6] for a in derive.shown(nodes, windows) if nodes[a][6]}
        return nodes, counts, drawn

    def console_open(self, nodes: derive.Nodes | None = None) -> bool:
        """Is the console on screen? From the flag byte of `console_window`.

        Measured 25 August 2026 by pressing the key twice with the recogniser watching: open, the
        window sits at 20,31 with a frame of 427x838 and its flag byte reads 0x00, and the screen
        carries the console's own output; shut, the frame is 0x0 and the byte reads 0x18. So the
        ordinary rule decides it after all (`derive.shown`) - what does not work is asking `state()`,
        because that only looks at widgets of the `Window` class and `console_window` is not one.
        That is the whole reason this used to be judged by typing into it.
        """
        nodes = nodes if nodes is not None else self.tree()
        address = next((a for a, k in nodes.items() if k[6] == 'console_window'), None)
        if address is None:
            return False
        return bool(derive.shown(nodes, [address]))

    def field_text(self, address: int) -> str:
        """The text of one widget, without walking the tree - a single channel question.

        The writing test first did this with a full tree walk, and at 83,000 nodes that cost over
        two seconds per attempt, four times per window. This way it is one read.
        """
        chunk = derive.read(address, derive.CHUNK)
        if chunk is None:
            return ''
        return derive._cstring(chunk, self.fields['text']) or ''

    def set_console(self, on: bool, nodes: derive.Nodes | None = None) -> derive.Nodes:
        """Open or close the console, and prove it with the flag byte before typing anything.

        The order matters and it cost a round to learn. This used to test by clicking into the
        input field and typing a character - reliable while the console stands open, and a stray
        click into the game when it does not. Measured 25 August 2026: with the console shut that
        click lands on the portrait at the bottom left and opens `character_window`, after which
        the harvest refuses to start because a window is already open before the round. So the
        flag decides whether it is open, and typing only ever confirms a console that is there.
        """
        nodes = nodes if nodes is not None else self.tree()
        self.field = next((a for a, k in nodes.items() if k[6] == 'console_edit'), None)
        for _ in range(3):
            if self.console_open(nodes) == on and (not on or self._captures_input()):
                return nodes
            channel.ask('sendkey 192')
            time.sleep(1.4)
            nodes = self.tree()
            self.field = next((a for a, k in nodes.items() if k[6] == 'console_edit'), None)
        raise SystemExit('the console does not %s' % ('open' if on else 'close'))

    def input_field(self) -> int:
        """The address of `console_edit`, as `set_console` last found it."""
        if self.field is None:
            raise SystemExit('the console input field is not in the tree; open the console first')
        return self.field

    def _captures_input(self) -> bool:
        """Does a character really land in the input field? Clicks into it and tries."""
        field = self.input_field()
        if self.pos is None:
            nodes = self.tree()
            scales = derive.scales_for(list(nodes))
            x, y = derive.screen_pos(nodes, field, scales)
            b, h = derive.screen_size(nodes, field, scales)
            self.pos = (int(x + b / 2), int(y + h / 2))
        click_x, click_y = self.pos
        channel.ask(f'mouse {int(click_x)} {int(click_y)} 1')
        time.sleep(0.4)
        channel.ask(f"sendchar {ord('#')}")
        time.sleep(0.4)
        ok = '#' in self.field_text(field)
        channel.ask('sendkey 8')
        return ok

    def command(self, text: str, nodes: derive.Nodes | None = None) -> list[str]:
        """Types a console command and returns whatever error.log added afterwards.

        **Check that the text really is in the input field before you send Enter.** Without that
        check this routine typed eleven commands into the game on 23 August 2026 because the
        console was shut, and reported "no message" eleven times - a command that never arrives
        looks like a command that does not work.
        """
        if self.field is None:
            self.set_console(True, nodes)
        for _ in range(len(self.field_text(self.input_field())) + 4):
            channel.ask('sendkey 8')
        for char in text:
            channel.ask(f'sendchar {ord(char)}')
        time.sleep(0.35)
        present = self.field_text(self.input_field())
        if text[-14:] not in present:
            # Focus lost: establish it once more, and otherwise stop hard.
            self.set_console(True)
            for char in text:
                channel.ask(f'sendchar {ord(char)}')
            time.sleep(0.35)
            present = self.field_text(self.input_field())
            if text[-14:] not in present:
                raise SystemExit(f'the console does not catch the input; field holds {present[:60]!r}')
        log = paths.require('ERROR_LOG')
        size = os.path.getsize(log)
        channel.ask('sendkey 13')
        time.sleep(1.6)
        with open(log, 'rb') as file:
            file.seek(size)
            fresh = file.read().decode('utf-8', 'replace')
        return [r.strip() for r in fresh.splitlines() if r.strip()]


def shortcut_round(game: Game, presses: list[Press] | None = None) -> dict[str, str]:
    """Which shortcut opens which window? One key per test, and every window shut again.

    **Start from a verified empty state.** If something was still open it becomes the baseline and
    the first key reports "no change" - that happened on 23 August 2026 with F1, which kept four of
    the nine keys out of the file.

    `presses` is a list of (name, press, twice); without it the round posts the keys in `KEYS`. A
    press with `twice` goes in a second time whether a window opened or not: alt+t is also
    toggle_event_shortcuts, which no widget declares, so a toggle nobody can see goes back with it.
    """
    out: dict[str, str] = {}
    if presses is None:
        presses = [(name, functools.partial(channel.ask, f'sendkey {int(code)}'), False)
                   for code, name in sorted(KEYS.items())]
    # Only with -debug_mode is there a console to shut; a round without it has nothing to do here.
    if game.console_open():
        game.set_console(False)
    for _ in range(4):
        _, _, open_now = game.state()
        if not open_now:
            break
        print('  closing first: {}'.format(', '.join(sorted(open_now))))
        channel.ask('sendkey 27')
        time.sleep(1.6)
    _, _, baseline = game.state()
    if baseline:
        print('  NOTE: did not start empty, still open: {}'.format(', '.join(sorted(baseline))))
    # Imported here because harvest imports this module.
    from tools.ck3.harvest import paused
    for name, press, twice in presses:
        press()
        time.sleep(1.8)
        _, _, now_drawn = game.state()
        added = now_drawn - baseline
        for window in added:
            out[window] = name
        # **Put back means: the same windows drawn and the clock still standing.** Not the same
        # number of widgets - the round of 1 September 2026 stopped after three keys because zoom
        # builds widgets and never takes them down, while it opens no window at all.
        restored = now_drawn
        if added or twice:
            press()
            time.sleep(1.4)
            _, _, restored = game.state()
        for _ in range(3):
            if restored == baseline:
                break
            channel.ask('sendkey 27')
            time.sleep(1.4)
            _, _, restored = game.state()
        if restored != baseline:
            # **This used to take the new state as the baseline and carry on.** That is how
            # the round of 20 September 2026 continued with the search filter window standing
            # open, and a contaminated state makes every measurement after it worthless. The
            # state coming back is the most important stop condition this project has, so it
            # stops rather than adapts.
            raise SystemExit('after {} the state did not come back; still drawn: {}. '
                             'Shut it by hand before starting again'.format(name, ', '.join(sorted(restored - baseline))))
        if not paused(game):
            raise SystemExit(f'after {name} the clock is running. Pause the game by hand; a running '
                             'clock makes the state unrepeatable')
        print(f"  {name!s:<10} {', '.join(sorted(added)) or 'no change'}")
    return out


def create_round(game: Game, windows: dict[str, OnDisk], limit: int | None = None) -> dict[str, Route]:
    """Try every window with GUI.CreateWidget, and clean up immediately.

    Cleaning up is not tidiness: without it the tree worked itself up from 84,000 to 145,000 nodes
    on 23 August 2026, with 167 windows drawn at once, after which every scan got slower and "which
    window is on top" became meaningless. `GUI.ClearWidgets` puts it back completely and leaves the
    real interface intact - measured, F1 worked fine afterwards.
    """
    out: dict[str, Route] = {}
    names = sorted(windows)[:limit] if limit else sorted(windows)
    nodes, counts, drawn = game.state(game.set_console(True))
    previous = len(nodes)
    for i, window in enumerate(names, 1):
        path = windows[window]['file']
        started = time.time()
        messages = game.command(f'GUI.CreateWidget {path} {window}', nodes)
        nodes, after_count, after_drawn = game.state()
        added = after_count.get(window, 0) - counts.get(window, 0)
        row: Route = {'file': path,
               'created': added > 0,
               'drawn': window in (after_drawn - drawn),
               # Keep whole messages and do not filter: an empty message on a failure is
               # itself a finding, and it disappears if you sieve on a word.
               'message': ' | '.join(m[-160:] for m in messages)[:400]}
        if added > 0:
            before_cleanup = len(nodes)
            game.command('GUI.ClearWidgets', nodes)
            nodes, counts, drawn = game.state()
            # Compare against the state from just before this window, not against a fixed
            # baseline: the latter made the flag cumulative, so 56 windows reported "not
            # cleaned up" while the real drift was two nodes per window.
            row['cleaned_up'] = len(nodes) <= previous + 40
            row['nodes_added'] = len(nodes) - previous
            if not row['cleaned_up']:
                print(f'  NOTE: {window} left {int(len(nodes) - previous)} nodes behind (was {int(before_cleanup)}, now {len(nodes)})')
        else:
            counts, drawn = after_count, after_drawn
            row['cleaned_up'] = None
            row['nodes_added'] = len(nodes) - previous
        previous = len(nodes)
        row['seconds'] = round(time.time() - started, 1)
        out[window] = row
        print(f"{int(i):3d}/{len(names)} {row['seconds']:5.1f}s {window[:40]!s:<40} created {row['created']!s:<5} drawn {row['drawn']!s:<5} cleaned up {row['cleaned_up']!s:<5} {row['message'][-50:]}")
    return out


def unmapped(pid: int, game: Game | None = None) -> tuple[list[str], collections.Counter[str], list[str]]:
    """Which windows the running game built that the map on disk does not know.

    **This is the closed test, and it exists because the open one failed twice.** Listing the
    shapes a window can be declared in finds only the shapes somebody thought of, and a window the
    map has never seen cannot refuse: it is missing from the count rather than reported as a
    problem. The engine builds every window up front and keeps it in the tree, so the live tree is
    the complete list and anything in it that `guimap.windows` lacks is a real miss.

    Measured 20 September 2026 on the Nobatia state, before the type-declared shape was counted:
    272 window objects under 206 names, of which 31 were unknown - the character filter, the
    ledger's filter, the vassal filters, the situation participant lists.

    Returns (missing, live names, names the map has that this state did not build). That third one
    is not a fault: a window for another government or another era simply is not there.
    """
    from tools.ck3 import guimap
    game = game or Game(pid)
    nodes = game.tree()
    live = collections.Counter(node[6] for node in nodes.values()
                               if node[0] in game.window_classes and node[6])
    known = guimap.windows()
    return (sorted(n for n in live if n not in known), live,
            sorted(n for n in known if n not in live))


def keys_only(pid: int, modified: bool = False) -> None:
    """Only the key round, and add what it finds to the map without touching anything else in it.

    Runs without -debug_mode. A key that opens a window becomes that window's shortcut route in
    `reports\\windows.json`; a window that already has one keeps it, and nothing is removed - a
    key that finds nothing this time says something about this state, not about the window.
    With `modified` it presses the bindings in `MODIFIED` through the channel's `combo`, which
    posts them and holds the modifier for the game, so the foreground stays the player's; what the
    game asked about the keyboard meanwhile is printed after the round.
    """
    game = Game(pid)
    if not modified:
        found = shortcut_round(game)
    else:
        channel.ask('count')
        presses: list[Press] = [
            (spelling, functools.partial(channel.ask, f"combo {int(COMBO_PAUSE)} {' '.join(str(c) for c in held + [code])}"), True)
            for spelling, held, code in modified_keys().values()]
        found = shortcut_round(game, presses)
        print('the game asked meanwhile:', ' | '.join(
            line for line in channel.ask('count').split('\n') if line.startswith(('count', 'asked'))))
    with open(OUT, encoding='utf-8') as file:
        result: WindowMap = json.load(file)
    added = []
    for window, key in sorted(found.items()):
        if window not in result['windows']:
            raise SystemExit(f'{window} opened on {key} and the map does not know it; run '
                             'windowmap.unmapped first')
        if not result['windows'][window].get('shortcut'):
            result['windows'][window]['shortcut'] = key
            added.append(f'{window} on {key}')
    with open(OUT, 'w', encoding='utf-8') as file:
        json.dump(result, file, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"windows with a key: {len(found)}, new in the map: {len(added)}{(' - ' + ', '.join(added)) if added else ''}")


def main() -> None:
    if sys.argv[1:] == ['--window-keys']:
        window_keys_plan()
        return
    pid = int(sys.argv[1])
    rest = sys.argv[2:]
    if rest[:1] == ['--window-keys']:
        # A trial names its windows, and writes beside the map rather than into it.
        found = window_keys_round(Game(pid), rest[1:])
        target = os.path.join(paths.WORK, 'window_keys_trial.json')
        with open(target, 'w', encoding='utf-8') as file:
            json.dump(found, file, ensure_ascii=False, indent=1)
        print(f'written: {target}')
        return
    if rest == ['--keys']:
        keys_only(pid)
        return
    if rest == ['--modified-keys']:
        keys_only(pid, modified=True)
        return
    limit = int(rest[0]) if rest and rest[0].isdigit() else None
    chosen = [name for name in rest if not name.isdigit()]
    windows = windows_on_disk()
    with_console = {name: row for name, row in windows.items() if row['console']}
    if chosen:
        # **A trial run names its windows.** Taking the first five of the list takes the five
        # easiest, which is how a round of ten once finished without a complaint while all ten
        # had failed. The hard cases go in by hand.
        missing = [name for name in chosen if name not in with_console]
        if missing:
            raise SystemExit('no console route for: {}'.format(', '.join(missing)))
        with_console = {name: with_console[name] for name in chosen}
    print(f"windows on disk: {len(windows)}, of which {int(sum(1 for r in windows.values() if r['console']))} have a console route; trying {len(with_console)}")

    game = Game(pid)
    print('shortcuts:')
    shortcuts = shortcut_round(game)
    print(f'windows with a shortcut: {len(shortcuts)}')

    print('GUI.CreateWidget:')
    created = create_round(game, with_console, limit)

    game.set_console(False)
    mapped: dict[str, Route] = {}
    for name, row in windows.items():
        out: Route = {'file': row['file'], 'shape': row['shape'], 'console': row['console'],
                      'shortcut': shortcuts.get(name)}
        if name in created:
            out.update(created[name])
        elif not row['console']:
            # Not a failure and not written down as one: the route does not exist for this shape.
            out['created'] = None
            out['reason'] = ('declared as a {}, so GUI.CreateWidget cannot find it - '
                             'it looks only at the top level of a file'.format(row['shape']))
        mapped[name] = out
    result: WindowMap = {'measured': time.strftime('%Y-%m-%d %H:%M'), 'exe': derive.build_key(), 'windows': mapped}
    target = os.path.abspath(OUT if not (chosen or limit) else os.path.join(paths.WORK, 'windows_trial.json'))
    if chosen or limit:
        print('a trial run does not overwrite the map; writing the trial beside it')
    with open(target, 'w', encoding='utf-8') as file:
        json.dump(result, file, ensure_ascii=False, indent=1, sort_keys=True)

    ok = sum(1 for v in mapped.values() if v.get('created'))
    drawn = sum(1 for v in mapped.values() if v.get('drawn'))
    no_route = sum(1 for v in mapped.values() if not v['console'])
    print(f'\ncreated {int(ok)}, of those drawn {int(drawn)}, with shortcut {len(shortcuts)}, no console route {int(no_route)}, out of {len(windows)}')
    print(f'written: {target}')


if __name__ == '__main__':
    terminal.utf8()
    main()
