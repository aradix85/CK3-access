r"""Everything the game brings up unasked, per channel, read off disk: an upper bound of what the
reader has to notice, and a test after a patch.

Usage:  python -m tools.ck3.unsolicited

Writes reports\unsolicited.json, per channel what the files say:
- events: the window a player sees each event in, `hidden = yes` left out;
- messages: per message type its place (feed, toast, popup or hidden), whether it pauses by default,
  its group, and how many messages use it;
- interactions the AI can send (an `ai_targets` and a frequency): whether the recipient gets a
  window (`popup_on_receive`) that also pauses (`pause_on_receive`), accepts without being asked
  (`auto_accept`), or else gets an icon in the top bar;
- warnings: the important actions per type, `alert` being an icon of its own in the top bar.
What the engine shows without a file saying so - the end of a war, a succession, a battle's icon -
is not on disk.

The files are script, not gui: `type` is an ordinary key there, and a block can hold a bare list,
so `guimap` does not read them. Only the first level of each entry is read here, which is where
all four channels keep what this needs.
"""
import collections
import json
import os
import re
from collections.abc import Iterator

from tools import paths, terminal
from tools.ck3 import database, guimap

OUT = os.path.join(paths.REPORTS, 'unsolicited.json')
TOKEN = re.compile(r'#[^\n]*|"[^"]*"|[{}=]|[^\s{}="#]+')
# Where an event goes without a `window` of its own (the event types in the events folder); an event
# without a `type` is a character event.
DEFAULT_WINDOW = {'character_event': 'character_event', 'letter_event': 'letter_event',
                  'court_event': 'court_event', 'activity_event': 'activity_window'}

Entry = tuple[str, dict[str, str], set[str]]


def entries(text: str) -> Iterator[Entry]:
    """Every top-level `key = { ... }`: its key, its first-level `key = value` pairs, and the keys of
    its first-level blocks."""
    tokens = [t for t in TOKEN.findall(text) if not t.startswith('#')]
    depth, at, key = 0, 0, ''
    pairs: dict[str, str] = {}
    blocks: set[str] = set()
    while at < len(tokens):
        token = tokens[at]
        if token == '{':
            depth += 1
        elif token == '}':
            depth -= 1
            if depth == 0:
                yield key, pairs, blocks
        elif at + 2 < len(tokens) and tokens[at + 1] == '=':
            value = tokens[at + 2]
            if depth == 0 and value == '{':
                key, pairs, blocks = token, {}, set()
            elif depth == 1:
                if value == '{':
                    blocks.add(token)
                else:
                    pairs[token] = value.strip('"')
                    at += 2
        at += 1


def event_files() -> list[tuple[str, str, str]]:
    """Every event file the engine loads, as (layer, virtual, full). Unlike the databases in
    `common`, the events folder has subfolders, and most events sit in them: the top level alone held
    523 of them (counted 9 November 2026)."""
    layers = [('game', os.path.join(paths.require('GAME'), 'game', 'events'))]
    layers += [('mod', os.path.join(folder, 'events')) for folder in paths.mod_folders()]
    found: list[tuple[str, str, str]] = []
    for layer, base in layers:
        for root, folders, names in os.walk(base):
            folders.sort()
            for name in sorted(names):
                if name.endswith('.txt'):
                    full = os.path.join(root, name)
                    found.append((layer, os.path.relpath(full, base).replace('\\', '/'), full))
    return guimap.last_wins(found)


def read(branch: str) -> Iterator[tuple[str, Entry]]:
    """Every entry of a folder, as the engine merges it, with the file it comes from."""
    for _, virtual, full in event_files() if branch == 'events' else database.files(branch):
        with open(full, encoding='utf-8-sig') as file:
            for entry in entries(file.read()):
                yield virtual, entry


def events() -> dict[str, int]:
    """Window -> how many events a player sees in it."""
    windows: collections.Counter[str] = collections.Counter()
    for _, (key, pairs, _) in read('events'):
        if '.' in key and pairs.get('hidden') != 'yes':
            kind = pairs.get('type', 'character_event')
            windows[pairs.get('window') or DEFAULT_WINDOW.get(kind, kind)] += 1
    return dict(windows.most_common())


def messages() -> dict[str, dict[str, str | bool | int]]:
    """Message type -> its place, whether it pauses by default, its group, and its messages."""
    used = collections.Counter(pairs.get('type', '') for _, (_, pairs, _) in read('messages'))
    return {key: {'display': pairs.get('display', 'feed'), 'auto_pause': pairs.get('auto_pause') == 'yes',
                  'group': pairs.get('group', 'default'), 'messages': used[key]}
            for _, (key, pairs, _) in read('message_filter_types')}


def interactions() -> dict[str, list[str]]:
    """What the recipient of an interaction the AI can send gets, -> the interactions."""
    found: dict[str, list[str]] = collections.defaultdict(list)
    for _, (key, pairs, blocks) in read('character_interactions'):
        if 'ai_targets' not in blocks or not ({'ai_frequency', 'ai_frequency_by_tier'} & (set(pairs) | blocks)):
            continue
        if pairs.get('auto_accept') == 'yes':
            kind = 'accepted without being asked'
        elif pairs.get('popup_on_receive') == 'yes':
            kind = 'a window that pauses' if pairs.get('pause_on_receive') == 'yes' else 'a window'
        else:
            kind = 'an icon in the top bar'
        found[kind].append(key)
    return dict(found)


def warnings() -> dict[str, list[str]]:
    """Important action type -> its actions; an `alert` stands in the top bar, `action` in the list
    of the current situation, `tutorial` only while the tutorial runs."""
    found: dict[str, list[str]] = collections.defaultdict(list)
    for _, (key, pairs, _) in read('important_actions'):
        found[pairs.get('type', 'action')].append(key)
    return dict(found)


def main() -> None:
    shown, kinds, received, actions = events(), messages(), interactions(), warnings()
    with open(OUT, 'w', encoding='utf-8') as file:
        json.dump({'events': shown, 'messages': kinds, 'interactions': received, 'warnings': actions},
                  file, ensure_ascii=False, indent=1)
    print(f'events a player sees: {sum(shown.values())}, in {len(shown)} windows; most: '
          + ', '.join(f'{w} {n}' for w, n in list(shown.items())[:5]))
    places = collections.Counter(str(m['display']) for m in kinds.values())
    pausing = sum(bool(m['auto_pause']) for m in kinds.values())
    print(f'message types: {len(kinds)}, ' + ', '.join(f'{p} {n}' for p, n in places.most_common())
          + f'; pausing by default: {pausing}')
    print('interactions the AI can send: ' + ', '.join(f'{k} {len(v)}' for k, v in received.items()))
    print('warnings: ' + ', '.join(f'{k} {len(v)}' for k, v in actions.items()))
    print(f'written to {OUT}')


if __name__ == '__main__':
    terminal.utf8()
    main()
