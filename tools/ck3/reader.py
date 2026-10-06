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
added to one of them. Reading those counts is a single question, and one of
the layers is called `events` and stands empty until one comes in. Nothing is polled that the
engine does not already keep.

A toast is the other one, and it is cheaper still. The game shows one at a time in one widget that is
always in the tree, `toast_container_widget` in `hud_notification_templates.gui`, whose `visible` is
"the toast handler has a message" - so a toast arrives as 0x08 leaving that widget's state byte, one
question a round. Its text is read from that small subtree only, and said between the lines: a toast
is not a window, so the place you stand on does not move. Decided with the player on 21 September
2026, in place of first finding out whether the message log keeps toasts. It does, with their date:
two toasts called up through the console stood in its log tab afterwards (measured 6 October 2026),
so a toast missed is not a toast lost.
"""
import sys

from tools.ck3 import channel, derive, guimap, memory, reading, windowmap
from tools.nvda import speech

UP, DOWN, TOGGLE, EXPLAIN = 38, 40, 123, 46
POLL = 400          # milliseconds the DLL waits for a key before answering with nothing


def gui_tables() -> guimap.Tables:
    """The templates of every gui file, once. Three seconds, and they do not change while it runs.

    The localisation is warmed here for the same reason: it is over a thousand files, and paid at the first
    keystroke it would be five seconds of silence on the first window rather than on the start.
    The widget classes come out of the executable and cost three seconds the first time, so they
    are warmed here too.
    """
    tables = guimap.tables()
    reading.words_table()
    memory.widget_vtables()
    return tables


def toast_text(pid: int, containers: list[int], above: derive.Nodes) -> str | None:
    """The text of the toast that is showing now, or None when none is.

    **Drawn is what `derive.shown` says, here as everywhere:** no 0x08 on the widget or on any
    ancestor up to the root, and a byte that cannot be read is an object that went away, so not
    drawn. `above` holds the containers and every ancestor of theirs, taken from the tree at the
    start; the subtree below a container is walked only while it shows. The same container holds a
    default, a contest and a contract variant, and only one of them is visible at a time.

    **A text counts only on a text class** (`derive.TEXT_CLASSES`): on any other widget the text
    field is the neighbour's.
    """
    showing = derive.shown(above, containers)
    texts: list[str] = []
    for container in showing:
        below = derive.widgets(container)
        kinds = derive.class_map(pid, {a: n[0] for a, n in below.items()})
        candidates = [a for a, n in below.items()
                      if kinds[a] in derive.TEXT_CLASSES and derive.strip_markup(n[7]).strip()]
        drawn = derive.shown({**above, **below}, candidates)
        for address in candidates:
            text = derive.strip_markup(below[address][7]).strip()
            if address in drawn and text not in texts:
                texts.append(text)
    return ', '.join(texts) or None


class Reader:
    """Where the reader stands: which window, which line, and whether it is listening at all."""

    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.game = windowmap.Game(pid)
        self.tables = gui_tables()
        self.on = False
        self.lines: list[reading.Line] = []
        self.at = 0
        tree = derive.widgets(self.game.root)
        self.layers = {a: (n[6] or '-') for a, n in tree.items() if n[5] == self.game.root}
        self.counted = self.counts()
        self.toasts = [a for a, n in tree.items() if n[6] == 'toast_container_widget']
        # Every toast container with its chain up to the root, so `derive.shown` can walk it.
        self.above: derive.Nodes = {}
        for container in self.toasts:
            walk = container
            while walk in tree:
                self.above[walk] = tree[walk]
                walk = tree[walk][5]
        self.toast_said: str | None = None

    def counts(self) -> dict[int, int]:
        """How many children each layer holds. One question, so it may be asked every round.

        This is what notices an event. An event does not flip a window that is already there, it
        builds a new object, so no list of windows we hold can contain it -
        but whatever it is added to counts its own children, in the very field the tree walk runs
        on. One of these layers is called `events` and stands empty until one arrives.
        """
        return derive.field_for(self.layers, self.game.fields['count'], 4)

    def toast(self) -> str | None:
        """The text of the toast that is showing now, or None when none is."""
        return toast_text(self.pid, self.toasts, self.above)

    def claim(self) -> None:
        """Tell the DLL which keys to keep from the game. The list is replaced, not added to.

        F12 is claimed even when the reader is off, because otherwise there is nothing left to
        switch it back on with. It costs the game nothing: it binds F12 to nothing.
        """
        codes = [TOGGLE] + ([UP, DOWN, EXPLAIN] if self.on else [])
        channel.ask('swallow ' + ' '.join(str(code) for code in codes))

    def refresh(self) -> str | None:
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
            speech.failure('the reader', f'it does not know this window: {trouble}',
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

    def move(self, step: int) -> None:
        """One unit further, or nothing at all at the ends."""
        goal = self.at + step
        if not self.lines or goal < 0 or goal >= len(self.lines):
            return
        self.at = goal
        speech.output(self.lines[goal]['say'])

    def explain(self) -> None:
        """What the game would show on hover here, when it is a sentence and not a sum.

        **A tooltip hangs on the button and not on the text inside it**, so this looks up the
        chain; measured over the harvest on 20 September 2026, one unit in five has one that way
        and two hundred of those sit one single level up. Where the sentence has gaps in it the
        game is adding something up, and rebuilding that sum is work still to do - so it says
        that rather than reading out a skeleton full of holes.
        """
        if not self.lines:
            return
        found = self.lines[self.at]['explain']
        speech.output(found if found else 'no explanation here that is not a sum')

    def toggle(self) -> None:
        self.on = not self.on
        self.claim()
        speech.output('on' if self.on else 'off')
        if self.on:
            self.refresh()


def keys_waiting(answer: str) -> list[int]:
    return [int(line.split('\t')[1]) for line in answer.split('\n') if line.startswith('key\t')]


def loop(reader: Reader) -> None:
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
        pressed = keys_waiting(channel.ask(f'waitkey {int(POLL)}', timeout=POLL / 1000.0 + 30))
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
            print('layer changed: {}'.format(', '.join(moved)), flush=True)
            reader.refresh()


def give_back() -> None:
    """The game gets every key back. This runs before anything is said about why."""
    channel.ask('swallow')
    channel.ask('keys off')


def main() -> None:
    pid = int(sys.argv[1])
    reader = Reader(pid)
    channel.ask('keys on')
    reader.claim()
    print(f'reader ready on pid {int(pid)}: F12 switches it on, up and down step through the window', flush=True)
    print(f'watching {len(reader.toasts)} toast container(s)', flush=True)
    print(f"watching {len(reader.layers)} layers: {', '.join(f'{reader.layers[a]} {count}' for a, count in sorted(reader.counted.items(), key=lambda pair: reader.layers[pair[0]]))}", flush=True)
    try:
        loop(reader)
    except BaseException as trouble:
        give_back()
        speech.failure('the reader', f'it stopped after {type(trouble).__name__}',
                       'the game has its keys back, start the reader again')
        raise
    give_back()


if __name__ == '__main__':
    main()
