"""The key loop: one unit per keystroke.

`reading.py` says what a window says; this says when. The DLL hooks the game's own window
procedure, so a key the reader claims is taken before the game acts on it and every key it does
not claim still reaches the game untouched. That is what makes the arrows claimable at all: in
vanilla they are bound to the interface, so without swallowing them the game would move with
every step.

Three keys, and deliberately no more until these have been listened to:

  up, down   one unit back or forward, spoken and brailled in the same breath;
  F12        the reader off and on again. A tool that owns your arrow keys has to be able to hand
             them back, and F12 is the one key in the F row that `shortcuts.shortcuts` binds to
             nothing - F10 is the encyclopedia and F11 the screenshot.

A fourth came on 20 September 2026 once there was something for it to say:

  delete     what the game would show if you could hover on the line you are standing on. Of the
             keys you can find without looking, only F12, Insert, Delete, End and K carry no
             named action in the game's own shortcuts, and F12 was taken.

Two silences, both of them decided rather than forgotten. Nothing is said at the ends of the list:
an arrow that cannot go anywhere produces nothing, because a sentence at every end of a list is
noise heard on every list. And nothing is announced on arrival beyond the first line of what is
there - the game is shown as bare as it is.

The one thing this may never do is fall over quietly. It owns the arrows, so a reader that dies
without a word leaves a keyboard that half works in a game that will not say why. So the keys go
back to the game first and the failure is spoken second, and that order is the point of it.

An event is the one thing that arrives without a keystroke, so it gets the one piece of machinery
here: the layers under the root count their own children, and an event is a new window object
added to one of them (`brief\\stand.md`). Reading those counts is a single question, and one of
the layers is called `events` and stands empty until one comes in. Nothing is polled that the
engine does not already keep.

A toast is the other one, and it is cheaper still. The game shows one at a time in one widget that is
always in the tree, `toast_container_widget` in `hud_notification_templates.gui`, whose `visible` is
"the toast handler has a message" - so a toast arrives as 0x08 leaving that widget's state byte, one
question a round. Its text is read from that small subtree only, and said between the lines: a toast
is not a window, so the place you stand on does not move. Decided with the player on 21 September
2026, in place of first finding out whether the message log keeps toasts.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'nvda'))

import channel
import derive
import guimap
import memory
import pairing
import reading
import speech
import windowmap

UP, DOWN, TOGGLE, EXPLAIN = 38, 40, 123, 46
POLL = 400          # milliseconds the DLL waits for a key before answering with nothing


def gui_tables():
    """The templates of every gui file, once. Three seconds, and they do not change while it runs.

    The localisation is warmed here for the same reason: it is 1173 files, and paid at the first
    keystroke it would be five seconds of silence on the first window rather than on the start.
    The widget classes come out of the executable and cost three seconds the first time, so they
    are warmed here too.
    """
    rows = guimap.files()
    table, local = guimap.type_table(rows)
    known = guimap.windows(rows)
    reading.words_table()
    memory.widget_vtables()
    return table, local, known, pairing.root_finder(table)


class Reader(object):
    """Where the reader stands: which window, which line, and whether it is listening at all."""

    def __init__(self, pid):
        self.pid = pid
        self.game = windowmap.Game(pid)
        self.tables = gui_tables()
        self.on = False
        self.lines = []
        self.at = 0
        tree = derive.widgets(self.game.root)
        self.layers = {a: (n[6] or '-') for a, n in tree.items() if n[5] == self.game.root}
        self.counted = self.counts()
        self.toasts = [a for a, n in tree.items() if n[6] == 'toast_container_widget']
        self.toast_said = None

    def counts(self):
        """How many children each layer holds. One question, so it may be asked every round.

        This is what notices an event. An event does not flip a window that is already there, it
        builds a new object (`brief\\stand.md`), so no list of windows we hold can contain it -
        but whatever it is added to counts its own children, in the very field the tree walk runs
        on. One of these layers is called `events` and stands empty until one arrives.
        """
        return derive.field_for(self.layers, self.game.fields['count'], 4)

    def toast(self):
        """The text of the toast that is showing now, or None when none is.

        Shown means no 0x08 on the container, and only the texts with no hidden ancestor inside it
        count: the same container holds a default, a contest and a contract variant, and only one
        of them is visible at a time.
        """
        flags = derive.flags_for(self.toasts)
        showing = [a for a in self.toasts if not flags.get(a, 0x08) & 0x08]
        if not showing:
            return None
        texts = []
        for container in showing:
            nodes = derive.widgets(container)
            hidden = derive.flags_for(list(nodes))
            for address, node in nodes.items():
                walk, gone = address, False
                while walk in nodes:
                    gone = gone or bool(hidden.get(walk, 0) & 0x08)
                    walk = nodes[walk][5]
                text = derive.strip_markup(node[7] or '').strip()
                if text and not gone and text not in texts:
                    texts.append(text)
        return ', '.join(texts) or None

    def claim(self):
        """Tell the DLL which keys to keep from the game. The list is replaced, not added to.

        F12 is claimed even when the reader is off, because otherwise there is nothing left to
        switch it back on with. It costs the game nothing: it binds F12 to nothing.
        """
        codes = [TOGGLE] + ([UP, DOWN, EXPLAIN] if self.on else [])
        channel.ask('swallow ' + ' '.join(str(code) for code in codes))

    def refresh(self):
        """Read whatever is on top, and stand at the top of it.

        Starting at the top rather than where you were is deliberate: a remembered place points
        into a list that may since be sorted differently or a row shorter, and then it points at
        the wrong thing without saying so.

        **A window the files do not describe is spoken, not raised.** The game is external input
        here: it can draw something the gui reader has no expansion for, and on 20 September 2026
        it did - the character filter, which the window map had never counted. A traceback is
        nothing to a player, and falling silent is worse, because the arrows are ours and the game
        will not answer them either.
        """
        try:
            window, lines = reading.live(self.pid, game=self.game, tables=self.tables)
        except guimap.GuiError as trouble:
            self.lines, self.at = [], 0
            speech.failure('the reader', 'it does not know this window: %s' % trouble,
                           'close it and open another screen, and report the name')
            return None
        self.lines, self.at = lines, 0
        self.counted = self.counts()
        if window is None:
            speech.failure('the reader', 'there is no window open for it to read',
                           'open one with F1 and it will speak')
            return None
        if lines:
            speech.output(lines[0]['say'])
        return window

    def move(self, step):
        """One unit further, or nothing at all at the ends."""
        goal = self.at + step
        if not self.lines or goal < 0 or goal >= len(self.lines):
            return
        self.at = goal
        speech.output(self.lines[goal]['say'])

    def explain(self):
        """What the game would show on hover here, when it is a sentence and not a sum.

        **A tooltip hangs on the button and not on the text inside it**, so this looks up the
        chain; measured over the harvest on 20 September 2026, one unit in five has one that way
        and two hundred of those sit one single level up. Where the sentence has gaps in it the
        game is adding something up, and that is `brief\\taken.md`, taak 10 subtaak f - so it says
        that rather than reading out a skeleton full of holes.
        """
        if not self.lines:
            return
        found = self.lines[self.at]['explain']
        speech.output(found if found else 'no explanation here that is not a sum')

    def toggle(self):
        self.on = not self.on
        self.claim()
        speech.output('on' if self.on else 'off')
        if self.on:
            self.refresh()


def keys_waiting(answer):
    return [int(line.split('\t')[1]) for line in answer.split('\n') if line.startswith('key\t')]


def loop(reader):
    """Every key the game receives comes past here, swallowed or not, because the hook sits in the
    game's own window procedure and reports before it decides.

    That is what makes a watcher over the windows unnecessary: the screen does not change by itself
    because somebody pressed something, so a key that is not ours means what we are holding may be
    stale, and the answer is to read again.

    An event is the exception, because it arrives while nobody touches anything. That is what the
    layer counts are for, and they cost one question a round.

    The race that looks like it is here is not: every window is built up front and kept in the
    tree, so opening one only flips its flag, and the walk of the tree that precedes the flag read
    takes seconds. By the time we ask, the game has long since answered.
    """
    while True:
        pressed = keys_waiting(channel.ask('waitkey %d' % POLL, timeout=POLL / 1000.0 + 30))
        for code in pressed:
            if code == TOGGLE:
                reader.toggle()
            elif not reader.on:
                continue
            elif code == UP:
                reader.move(-1)
            elif code == DOWN:
                reader.move(1)
            elif code == EXPLAIN:
                reader.explain()
            else:
                reader.refresh()
        if not reader.on:
            continue
        said = reader.toast()
        if said and said != reader.toast_said:
            speech.output(said)
        reader.toast_said = said
        now = reader.counts()
        if now != reader.counted:
            moved = sorted(reader.layers[a] for a in now if now[a] != reader.counted.get(a))
            print('layer changed: %s' % ', '.join(moved), flush=True)
            reader.refresh()


def give_back():
    """The game gets every key back. This runs before anything is said about why."""
    channel.ask('swallow')
    channel.ask('keys off')


def main():
    pid = int(sys.argv[1])
    reader = Reader(pid)
    channel.ask('keys on')
    reader.claim()
    print('reader ready on pid %d: F12 switches it on, up and down step through the window'
          % pid, flush=True)
    print('watching %d toast container(s)' % len(reader.toasts), flush=True)
    print('watching %d layers: %s' % (len(reader.layers), ', '.join(
        '%s %d' % (reader.layers[a], count) for a, count in sorted(
            reader.counted.items(), key=lambda pair: reader.layers[pair[0]]))), flush=True)
    try:
        loop(reader)
    except BaseException as trouble:
        give_back()
        speech.failure('the reader', 'it stopped after %s' % type(trouble).__name__,
                       'the game has its keys back, start the reader again')
        raise
    give_back()


if __name__ == '__main__':
    main()
