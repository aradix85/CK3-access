r"""Phase 0 of the sweep: which window can be opened by which route?

Writes reports\windows.json: per window, whether GUI.CreateWidget produces it, whether a shortcut
opens it, and if not, what the engine says about it. Runs on a loaded, paused game started with
-debug_mode.

Usage:  python tools\ck3\windowmap.py <pid> [<count>]
"""
import collections
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import derive
import vtablemap
import memory
import paths
import channel

GAME = paths.GAME
ERROR_LOG = paths.ERROR_LOG
OUT = os.path.join(paths.REPORTS, 'windows.json')
KEYS = {112: 'F1', 113: 'F2', 114: 'F3', 115: 'F4', 116: 'F5',
           117: 'F6', 118: 'F7', 119: 'F8', 120: 'F9'}


def windows_on_disk():
    """Every `window = { name = ... }` in the gui files, with the path the console wants.

    Read with `utf-8-sig`: some of the files start with a byte order mark right before
    `window = {`, and on those the first line was recognised as nothing, silently - `court_window`,
    `decisions_view` and `activity_list` went missing that way, while their shortcut opens them fine.
    """
    found = {}
    for root, _, files in os.walk(GAME):
        for name in files:
            if not name.endswith('.gui'):
                continue
            full_path = os.path.join(root, name)
            rel = os.path.relpath(full_path, GAME).replace('\\', '/')
            # The engine merges the three layers into one virtual folder: `game/gui/x.gui`,
            # `clausewitz/gui/x.gui` and `jomini/gui/x.gui` are all called `gui/x.gui` as far
            # as the console is concerned. Measured 23 August 2026: with the layer name in front
            # it fails with "could not find description", without it the window comes up.
            parts = rel.split('/')
            if parts[0] in ('game', 'clausewitz', 'jomini'):
                rel = '/'.join(parts[1:])
            lines = open(full_path, encoding='utf-8-sig', errors='replace').read().splitlines()
            depth, wait_for = 0, None
            for line in lines:
                strip_markup = line.split('#')[0]
                if re.match(r'\s*window\s*=\s*\{', strip_markup):
                    wait_for = depth
                m = re.match(r'\s*name\s*=\s*"([\w.]+)"\s*$', strip_markup)
                if m and wait_for is not None and depth == wait_for + 1:
                    found.setdefault(m.group(1), rel)
                    wait_for = None
                depth += strip_markup.count('{') - strip_markup.count('}')
    return found


def classes(pid):
    base = vtablemap.module_base(pid)
    return {base + v for v in (memory.vtables_by_name('Window') or [])}


class Game(object):
    """The actions on the running game, each with the measurement that says whether it landed."""

    def __init__(self, pid):
        self.pid = pid
        self.fields, _ = derive.fields_for(pid)
        derive.configure_channel(self.fields)
        self.window_classes = classes(pid)
        self.root, _ = derive.quick_root(self.fields, pid)
        self.field = None        # address of console_edit
        self.pos = None        # click point of that field; does not change while the game runs

    def tree(self):
        """The root is looked up once. Looking it up every round cost fifty seconds per window
        on 23 August 2026; with the root remembered it is a few."""
        return derive.widgets(self.root)

    def state(self, nodes=None):
        """(number of instances per widget name, names of what is drawn).

        Count all widgets and not just the window class: a created widget of another class
        otherwise counted as a failure, which produced four false failures on 23 August 2026.
        """
        nodes = nodes if nodes is not None else self.tree()
        windows = [a for a, k in nodes.items() if k[0] in self.window_classes]
        flags = derive.flags_for(windows)
        counts = collections.Counter(k[6] for k in nodes.values() if k[6])
        drawn = {nodes[a][6] for a in windows
                    if flags.get(a, 0xFF) == 0x00 and nodes[a][6]}
        return nodes, counts, drawn

    def console_open(self, nodes):
        return any(k[6] == 'console_edit' for k in nodes.values()) and \
               'console_window' in self.state(nodes)[2]

    def field_text(self, address):
        """The text of one widget, without walking the tree - a single channel question.

        The writing test first did this with a full tree walk, and at 83,000 nodes that cost over
        two seconds per attempt, four times per window. This way it is one read.
        """
        chunk = derive.read(address, derive.CHUNK)
        if chunk is None:
            return ''
        return derive._cstring(chunk, self.fields['text']) or ''

    def set_console(self, on, nodes=None):
        """Open or close the console, and test it by typing rather than by looking.

        This used to be judged from the window flag of `console_window`. That does not work: the
        widget is not always in the window class, after which the routine concluded "already open",
        pressed nothing and typed into the void. Measured 23 August 2026 - the console itself is
        reliable, the measurement was not.
        """
        nodes = nodes if nodes is not None else self.tree()
        self.field = next((a for a, k in nodes.items() if k[6] == 'console_edit'), None)
        if not on:
            if self.field is not None and self._captures_input():
                channel.ask('sendkey 192')
                time.sleep(1.2)
                nodes = self.tree()
            return nodes
        for _ in range(3):
            if self.field is not None and self._captures_input():
                return nodes
            channel.ask('sendkey 192')
            time.sleep(1.4)
            nodes = self.tree()
            self.field = next((a for a, k in nodes.items() if k[6] == 'console_edit'), None)
        raise SystemExit('the console does not open')

    def _captures_input(self):
        """Does a character really land in the input field? Clicks into it and tries."""
        if self.pos is None:
            nodes = self.tree()
            scales = derive.scales_for(list(nodes))
            x, y = derive.screen_pos(nodes, self.field, scales)
            b, h = derive.screen_size(nodes, self.field, scales)
            self.pos = (int(x + b / 2), int(y + h / 2))
        channel.ask('mouse %d %d 1' % self.pos)
        time.sleep(0.4)
        channel.ask('sendchar %d' % ord('#'))
        time.sleep(0.4)
        ok = '#' in self.field_text(self.field)
        channel.ask('sendkey 8')
        return ok

    def command(self, text, nodes=None):
        """Types a console command and returns whatever error.log added afterwards.

        **Check that the text really is in the input field before you send Enter.** Without that
        check this routine typed eleven commands into the game on 23 August 2026 because the
        console was shut, and reported "no message" eleven times - a command that never arrives
        looks like a command that does not work.
        """
        nodes = self.set_console(True, nodes) if self.field is None else nodes
        for _ in range(len(self.field_text(self.field)) + 4):
            channel.ask('sendkey 8')
        for char in text:
            channel.ask('sendchar %d' % ord(char))
        time.sleep(0.35)
        present = self.field_text(self.field)
        if text[-14:] not in present:
            # Focus lost: establish it once more, and otherwise stop hard.
            self.set_console(True)
            for char in text:
                channel.ask('sendchar %d' % ord(char))
            time.sleep(0.35)
            present = self.field_text(self.field)
            if text[-14:] not in present:
                raise SystemExit('the console does not catch the input; field holds %r' % present[:60])
        size = os.path.getsize(ERROR_LOG)
        channel.ask('sendkey 13')
        time.sleep(1.6)
        with open(ERROR_LOG, 'rb') as file:
            file.seek(size)
            fresh = file.read().decode('utf-8', 'replace')
        return [r.strip() for r in fresh.splitlines() if r.strip()]


def shortcut_round(game):
    """Which shortcut opens which window? One key per test, and every window shut again.

    **Start from a verified empty state.** If something was still open it becomes the baseline and
    the first key reports "no change" - that happened on 23 August 2026 with F1, which kept four of
    the nine keys out of the file.
    """
    out = {}
    game.set_console(False)
    for _ in range(4):
        _, _, open_now = game.state()
        if not open_now:
            break
        print('  closing first: %s' % ', '.join(sorted(open_now)))
        channel.ask('sendkey 27')
        time.sleep(1.6)
    _, _, baseline = game.state()
    if baseline:
        print('  NOTE: did not start empty, still open: %s' % ', '.join(sorted(baseline)))
    for code, name in sorted(KEYS.items()):
        channel.ask('sendkey %d' % code)
        time.sleep(1.8)
        _, _, now_drawn = game.state()
        added = now_drawn - baseline
        for window in added:
            out[window] = name
        if added:
            channel.ask('sendkey %d' % code)
            time.sleep(1.4)
            _, _, restored = game.state()
            if restored != baseline:
                print('  NOTE after %s: state did not return (%s)'
                      % (name, ', '.join(sorted(restored)) or 'leeg'))
                baseline = restored
        print('  %-4s %s' % (name, ', '.join(sorted(added)) or 'no change'))
    return out


def create_round(game, windows, limit=None):
    """Try every window with GUI.CreateWidget, and clean up immediately.

    Cleaning up is not tidiness: without it the tree worked itself up from 84,000 to 145,000 nodes
    on 23 August 2026, with 167 windows drawn at once, after which every scan got slower and "which
    window is on top" became meaningless. `GUI.ClearWidgets` puts it back completely and leaves the
    real interface intact - measured, F1 worked fine afterwards.
    """
    out = {}
    names = sorted(windows)[:limit] if limit else sorted(windows)
    nodes, counts, drawn = game.state(game.set_console(True))
    previous = len(nodes)
    for i, window in enumerate(names, 1):
        path = windows[window]
        started = time.time()
        messages = game.command('GUI.CreateWidget %s %s' % (path, window), nodes)
        nodes, after_count, after_drawn = game.state()
        added = after_count.get(window, 0) - counts.get(window, 0)
        row = {'file': path,
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
                print('  NOTE: %s left %d nodes behind (was %d, now %d)'
                      % (window, len(nodes) - previous, before_cleanup, len(nodes)))
        else:
            counts, drawn = after_count, after_drawn
            row['cleaned_up'] = None
            row['nodes_added'] = len(nodes) - previous
        previous = len(nodes)
        row['seconds'] = round(time.time() - started, 1)
        out[window] = row
        print('%3d/%d %5.1fs %-40s created %-5s drawn %-5s cleaned up %-5s %s'
              % (i, len(names), row['seconds'], window[:40], row['created'],
                 row['drawn'], row['cleaned_up'], row['message'][-50:]))
    return out


def main():
    pid = int(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    windows = windows_on_disk()
    print('windows on disk: %d' % len(windows))

    game = Game(pid)
    print('shortcuts:')
    shortcuts = shortcut_round(game)
    print('windows with a shortcut: %d' % len(shortcuts))

    print('GUI.CreateWidget:')
    created = create_round(game, windows, limit)

    game.set_console(False)
    result = {'measured': time.strftime('%Y-%m-%d %H:%M'),
                'exe': derive.build_key(),
                'windows': {name: dict(created.get(name, {'file': path}),
                                        shortcut=shortcuts.get(name))
                             for name, path in windows.items()}}
    target = os.path.abspath(OUT)
    with open(target, 'w', encoding='utf-8') as file:
        json.dump(result, file, ensure_ascii=False, indent=1, sort_keys=True)

    ok = sum(1 for v in result['windows'].values() if v.get('created'))
    drawn = sum(1 for v in result['windows'].values() if v.get('drawn'))
    print('\ncreated %d, of those drawn %d, with shortcut %d, out of %d windows'
          % (ok, drawn, len(shortcuts), len(windows)))
    print('written: %s' % target)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    main()
