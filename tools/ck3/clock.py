r"""Let the clock run, and record what the game shows of its own accord.

Usage:
    python -m tools.ck3.clock <pid> <speed> <minutes> [--try] [--war] [<window> ...]

Some windows open on no key and no click: the game shows them as a war ends or a ruler dies, and a
request the AI sends comes in as an icon in the top bar, a row of `diplomatic_items` under
`ingame_topbar`, whose window opens only on a click on that icon (`DiplomaticItem.OnClick`, read
in hud_notification_templates.gui and hud.gui, 4 November 2026). A watcher on windows alone does
not see such a request: eight game years on Harold brought no window up while that row grew and
shrank again (4 November 2026).

So this runs the clock at `speed` for at most `minutes` of wall time and stops it for whatever
comes up. An icon in the top bar is clicked, and the window it brings up is recorded with whether
the clock was still running when the icon came. A window the game shows by itself is recorded when
it has no record from a player route yet. Then every window beyond the bare screen is answered -
an event with its first option, a request with its reject button, which takes its icon away - and
the rest is shut with Escape (`harvest.close_window`); an icon its window leaves standing, as the
result of a war does, goes with a right click. An event holds the date with the clock
running until it is answered, so answering is what keeps the date moving.

**Whether the clock runs is read off the bar at the bottom**, not off the date: `pause_play_icons`
holds the pause icon, drawn while the clock runs, and the play icon, drawn while it stands
(`[Or(IsPausedByEvent, IsManuallyPaused)]` in hud.gui); one space turned each round and the date
moved with it (measured 5 November 2026 on Harold). **When this ends, however it ends, the clock
is stopped by hand** (`stopped_by_hand`), so that answering what stands does not start it.

**A window it records into the harvest gets its keys pressed where it stands** (`windowmap.
keys_in_place`), Escape last, and the answer goes into `reports\window_keys.json`: such a window
cannot be opened again for the key round (decided 7 November 2026).

With `--try` the records go to the work folder and not into the harvest: a request the console
made proves this watcher, and the record of a request has to come from the AI itself. It stops
when the player is at war, unless `--war` says the round is meant to run through one; and with
windows named, once each of them is recorded, also one that has a record from a player route
already, which goes aside as `hand` does.
"""
import json
import os
import pathlib
import sys
import time

from tools import paths, terminal
from tools.ck3 import channel, guimap, harvest, model, onscreen, openers, widgettree, windowmap

# What answers a window: the first option of an event, and the reject button of a request, or its
# acknowledge button where the request needs no answer (read in the four interaction_*notification
# gui files, 5 November 2026), and the confirm button of a message shown as a popup (read in
# window_message_popup.gui). When a message was left to the Escape that puts the state back, a
# letter stood afterwards and the round stopped there (measured 7 November 2026 on Harold).
ANSWERS = ('EventOption.Select', 'CharacterInteractionNotificationWindow.Reject',
           'CharacterInteractionNotificationWindow.Acknowledge', 'MessagePopup.Close')
SPACE = 32
# Seconds the clock may stand with nothing open before it is started again. An event stops it
# before its window is drawn - three rounds of a second or more saw it stopped and no window -
# and while the event stands a space does not start it (measured 5 November 2026 on Harold). How
# long the clock stood before a window came is printed with that window.
IDLE = 20


def running(nodes: widgettree.Nodes) -> bool:
    """Is the clock running? The first child of `pause_play_icons` is the pause icon, drawn only
    while it runs."""
    bar = next(a for a, k in nodes.items() if k[6] == 'pause_play_icons')
    return bool(onscreen.shown(nodes, [next(a for a, k in nodes.items() if k[5] == bar)]))


def stopped_by_hand(nodes: widgettree.Nodes) -> bool:
    """Is the clock stopped the way a space stops it? An event stops it as well, but only until it
    is answered: with this tool gone and an event standing, answering it let the clock run eight
    months (measured 5 November 2026 on Harold). The icon drawn while it stands by hand is the second
    child of the widget two levels above `tutorial_highlight_bottom_right_bar`: a space turned it on
    and off, also with an event standing, which kept the clock stopped (measured the same day).

    **A message that pauses shows the same icon**, with nothing pressed, and that pause is not by
    hand: shutting the message starts the clock, and so does a space while it stands. A message that
    comes while the clock already stands by hand leaves it standing when it shuts (measured
    7 November 2026 on Harold)."""
    named = next(a for a, k in nodes.items() if k[6] == 'tutorial_highlight_bottom_right_bar')
    bar = nodes[nodes[named][5]][5]
    return bool(onscreen.shown(nodes, [[a for a, k in nodes.items() if k[5] == bar][1]]))


def set_clock(game: windowmap.Game, on: bool, baseline: set[str] | None = None) -> None:
    """Start the clock, or stop it by hand, and prove it on the bar at the bottom. A space is
    given three seconds to show: one second was once too short, so the next space turned the clock
    back again (measured 5 November 2026 on Harold).

    **Starting gives way to a window that comes up beyond `baseline`:** an answer can bring an
    event a second or more later, which stops the clock before it is drawn and keeps a space from
    starting it; after a rejected request an event stood up that way (measured the same day). The
    caller's next round answers it."""

    def done() -> bool:
        nodes, _, drawn = game.state()
        if on and baseline is not None and drawn - baseline:
            return True
        return running(nodes) if on else stopped_by_hand(nodes)

    for _ in range(3):
        if done():
            return
        channel.ask(f'sendkey {SPACE}')
        for _ in range(6):
            time.sleep(0.5)
            if done():
                return
    raise SystemExit(f"the clock does not {'start' if on else 'stop'}; drawn: {', '.join(sorted(game.state()[2]))}")


def at_war(nodes: widgettree.Nodes) -> bool:
    """Is the player at war? The button that raises all armies is drawn while they are and have
    raised none (`[And( Character.IsAtWar, Not(Character.HasRaisedRegiments))]`, read in hud.gui),
    and this raises none. On the day a letter was answered with its first option a faction took
    Harold to war, and the clock ran eighteen months of it, until he lost England, with no window to
    say so (measured 5 November 2026). **The button is not drawn in the diplomatic map mode either**,
    which the character window's diplomacy button switches on: there this said no war while Harold
    was at war (measured 7 November 2026)."""
    button = [a for a, k in nodes.items() if k[6] == 'tutorial_highlight_raise_troops']
    return bool(onscreen.shown(nodes, button))


def icons_in(nodes: widgettree.Nodes, row: str) -> list[int]:
    """Every `action_icon` drawn in one row of the top bar, left to right: `diplomatic_items` for
    the requests, `alert_items` for the warnings in front of them, which name their icons the same."""
    rows = {a for a, k in nodes.items() if k[6] == row}
    icons = []
    for address, node in nodes.items():
        if node[6] != 'action_icon':
            continue
        above = node[5]
        while above in nodes and above not in rows:
            above = nodes[above][5]
        if above in rows:
            icons.append(address)
    drawn = onscreen.shown(nodes, icons)
    return [a for a in icons if a in drawn]


def request_icons(game: windowmap.Game, nodes: widgettree.Nodes) -> list[int]:
    """The icons of the requests that a click could reach. Each grows from nothing as it comes in,
    so one still growing is left for the next round."""
    icons = icons_in(nodes, 'diplomatic_items')
    if not icons:
        return []
    scales = onscreen.scales_for(list(nodes))
    classes = widgettree.class_map(game.pid, {a: k[0] for a, k in nodes.items()})
    return [a for a in icons if openers.on_screen(a, nodes, scales, classes) is None]


def inside(nodes: widgettree.Nodes, address: int) -> bool:
    """Does the middle of this widget lie within the frame of every ancestor that cuts off its
    children (`onscreen.CLIPS`)? Past that frame the game may still draw a little - one warning past
    the edge of the top bar looked whole on the screen - so this errs on the side of out of reach."""
    scales = onscreen.scales_for(list(nodes))
    x, y = middle(nodes, address)
    chain = []
    above = nodes[address][5]
    while above in nodes:
        chain.append(above)
        above = nodes[above][5]
    flags = onscreen.flags_for(chain)
    for clipping in chain:
        if flags[clipping] & onscreen.CLIPS:
            cx, cy = onscreen.screen_pos(nodes, clipping, scales)
            cw, ch = onscreen.screen_size(nodes, clipping, scales)
            if not (cx <= x < cx + cw and cy <= y < cy + ch):
                return False
    return True


def middle(nodes: widgettree.Nodes, address: int) -> tuple[int, int]:
    scales = onscreen.scales_for(list(nodes))
    x, y = onscreen.screen_pos(nodes, address, scales)
    width, height = onscreen.screen_size(nodes, address, scales)
    return int(x + width / 2), int(y + height / 2)


def click(game: windowmap.Game, right: bool = False) -> tuple[widgettree.Nodes, set[str]]:
    """Click the first request icon, or with `right` take it away with a right click: the tree
    then, and the windows that came up. Done when a window came up or the icons grew fewer. The icon
    is asked anew, for the bar builds its icons anew, and between the round that saw them and the
    click a request can run out: once an icon was gone by then, address and all (measured
    5 November 2026 on Harold).

    **A right click takes away an icon its window left standing**, as a player does: a war ending
    shows its result in a window that only shuts, and the icon stayed for two months until a right
    click took it away (`DiplomaticItem.OnRightClick`; measured 5 November 2026 on Harold, twice).

    **The warnings stand in front of the requests, in one widget with `scissor`**, and enough of
    them push a request past what is drawn: with thirteen warnings the request stood at x 1379,
    under the resources, and a click there opened nothing; a right click on a warning took it away
    and brought the request 72 points nearer (`GUIAlertItem.OnRightClick`; measured 5 November 2026
    on Harold). A request with its middle at 1163 was out of reach too, and once a click on a
    request icon brought up the military view, whose button sits among the resources. So while its
    middle lies past the frame of that widget, 720 wide from x 401 (`inside`), the first warning
    goes, as a player clears the bar to reach a request; inside it, a click that brings nothing up
    while the icon stands is a fault."""
    while True:
        nodes, _, before = game.state()
        icons = request_icons(game, nodes)
        if not icons:
            return nodes, set()
        if not inside(nodes, icons[0]):
            warnings = icons_in(nodes, 'alert_items')
            if not warnings:
                raise SystemExit('a request icon lies past the edge of the top bar, and no warning stands in front of it')
            wx, wy = middle(nodes, warnings[0])
            channel.ask(f'rmouse {wx} {wy}')
            time.sleep(1.5)
            if len(icons_in(game.tree(), 'alert_items')) != len(warnings) - 1:
                raise SystemExit(f'a right click on the first warning, at {wx},{wy}, did not take it away')
            print('   a request lay past the edge of the top bar; took the first warning away')
            continue
        x, y = middle(nodes, icons[0])
        channel.ask(f"{'rmouse' if right else 'mouse'} {x} {y}")
        time.sleep(1.5)
        nodes, _, drawn = game.state()
        if drawn - before or len(request_icons(game, nodes)) < len(icons):
            return nodes, drawn - before
        raise SystemExit(f'a click on the request icon at {x},{y} brought up nothing, and the icon stands')



def option(game: windowmap.Game, window: str,
           tables: guimap.Tables) -> tuple[openers.Goal, openers.Spot, tuple[int, int]] | None:
    """The first answer in `window` that a click reaches, or None. An option the game has switched
    off is no spot (`openers.reachable_spots`): the first option a click reached in "A Vision in
    the Night" asked for learning 12, and five presses on it answered nothing (measured 5 November
    2026 on Harold)."""
    for call in ANSWERS:
        goal = openers.Goal('call', call)
        reachable = openers.reachable_spots(game, window, goal, tables)[1]
        if reachable:
            return goal, *reachable[0]
    return None


def answer(game: windowmap.Game, baseline: set[str], tables: guimap.Tables) -> None:
    """Answer every window beyond the bare screen, and shut what an answer leaves standing.

    **An answer can bring the next event up**, in the same window or another, a second or more
    later: an event answered on Harold stood again as `character_event`, and another answer brought
    a `letter_event` (measured 5 November 2026). So this goes on until two looks two seconds apart
    find nothing an answer reaches, twenty rounds at most."""
    idle = 0
    for _ in range(20):
        standing = sorted(game.state()[2] - baseline)
        if not standing or idle == 2:
            break
        answered = False
        for window in standing:
            found = option(game, window, tables)
            if found and openers.press_spot(game, *found) is None:
                print(f'   {window}: {found[0].name}')
                answered = True
                break
        idle = 0 if answered else idle + 1
        time.sleep(2.0)
    if not harvest.close_window(game, {'click': True}, baseline):
        raise SystemExit(f"the state did not come back: {', '.join(sorted(game.state()[2] - baseline))} still drawn")


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    pid, speed, minutes = int(sys.argv[1]), sys.argv[2], float(sys.argv[3])
    out = paths.WORK if '--try' in sys.argv else harvest.OUT
    war = '--war' in sys.argv
    goals = [a for a in sys.argv[4:] if not a.startswith('--')]
    game = windowmap.Game(pid)
    openers.game_classes = game.window_classes
    if running(game.tree()):
        raise SystemExit('the clock is running: pause the game first')
    tables = guimap.tables()
    windows: dict[str, windowmap.Route] = json.loads(pathlib.Path(harvest.MAP).read_text(encoding='utf-8'))['windows']
    # Escape shuts no event, so one standing at the start would count as the bare screen.
    drawn = game.bare()
    baseline = {window for window in drawn if option(game, window, tables) is None}
    answer(game, baseline, tables)
    player = model.player(pid)[0]
    recorded: set[str] = set()

    def record(window: str, nodes: widgettree.Nodes, route: str, started: float) -> None:
        header = harvest.header(game, baseline)
        if header['player'] != player:
            # Around the end of a war the six places disagreed once and agreed again at the next
            # question (measured 4 November 2026 on Harold).
            time.sleep(1.0)
            header = harvest.header(game, baseline)
            if header['player'] != player:
                raise SystemExit(f"the player is no longer {int(player)} but {header['player_name']} ({int(header['player'])})")
        found = harvest.record_window(game, window, nodes, header, route, 1,
                                       (windows.get(window) or {}).get('file'), started, [])
        path = os.path.join(out, window + '.json')
        if out == harvest.OUT and os.path.exists(path):
            aside = os.path.join(paths.PROJECT, 'harvest-{}-{}replaced'.format(
                time.strftime('%Y-%m-%d'), '' if harvest.player_record(window) else 'console-'))
            os.makedirs(aside, exist_ok=True)
            os.replace(path, os.path.join(aside, window + '.json'))
        pathlib.Path(path).write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding='utf-8')
        recorded.add(window)
        print(f"{window}: {int(found['widgets'])} widgets, {int(found['confirmed'])}/{int(found['boxes'])} "
              f'text boxes confirmed; {route}')
        if out == harvest.OUT:
            windowmap.store_window_keys(pid, {window: windowmap.keys_in_place(game, window)})

    def wanted(window: str) -> bool:
        return window not in recorded and (out != harvest.OUT or window in goals
                                           or not harvest.player_record(window))

    # Icons standing before the clock runs did not come while it ran, and are said so: the icon of a
    # war the console ended stood there, and the first round said it came with the clock running,
    # while a war that ends with the clock running stops it (measured 7 November 2026 on Harold).
    earlier = len(request_icons(game, game.tree()))
    windowmap.press(speed)
    deadline = time.time() + minutes * 60
    stood: float | None = None          # since when the clock has stood with nothing open
    try:
        set_clock(game, True, baseline)
        while time.time() < deadline and not (goals and not any(wanted(goal) for goal in goals)):
            if harvest.free_memory() < harvest.FREE_MEMORY_FLOOR:
                raise SystemExit(f'{harvest.free_memory():.1f} GB free, below the floor of {harvest.FREE_MEMORY_FLOOR:.1f}')
            channel.ask('hello')
            nodes, _, drawn = game.state()
            if not war and at_war(nodes):
                raise SystemExit(f'{harvest.game_date(nodes)}: the player is at war; end it, or run with --war')
            icons = request_icons(game, nodes)
            standing = len(icons_in(nodes, 'diplomatic_items'))
            fresh = drawn - baseline
            if not icons and not fresh:
                if running(nodes):
                    stood = None
                elif stood is None:
                    stood = time.time()
                elif time.time() - stood > IDLE:
                    print(f'{harvest.game_date(nodes)}: the clock stood {IDLE} seconds with nothing open; started again')
                    set_clock(game, True, baseline)
                    stood = None
                continue
            date, ran = harvest.game_date(nodes), running(nodes)
            came = (f"the clock {'running' if ran else 'stopped'} as it came" if not (icons and earlier)
                    else 'standing before the clock ran')
            waited = f', {time.time() - stood:.1f} seconds after it stopped' if stood else ''
            stood = None
            set_clock(game, False)
            started = time.time()
            print(f"{date}: {len(icons)} request icons, windows {', '.join(sorted(fresh)) or 'none'}, {came}{waited}")
            for window in sorted(fresh):
                if wanted(window):
                    record(window, game.tree(), f'clock: the game showed it on {date}', started)
            if icons:
                nodes, opened = click(game)
                print(f"   the icon brought up {', '.join(sorted(opened)) or 'nothing, and went'}")
                for window in sorted(opened):
                    if wanted(window):
                        record(window, nodes, f'clock: DiplomaticItem.OnClick on an icon in the top bar on {date}, {came}',
                               started)
                earlier = max(0, earlier - 1)
            answer(game, baseline, tables)
            if icons and len(icons_in(game.tree(), 'diplomatic_items')) == standing:
                click(game, right=True)
            set_clock(game, True, baseline)
    finally:
        # A message standing now would hold the clock with the icon of a stop by hand, and the next
        # thing to shut it would start the clock (`stopped_by_hand`): shut what stands, then stop.
        answer(game, baseline, tables)
        set_clock(game, False)
        print(f"stopped on {harvest.game_date(game.tree())}; recorded {', '.join(sorted(recorded)) or 'nothing'} into {out}")


if __name__ == '__main__':
    terminal.utf8()
    main()
