"""Starts CK3 with the channel inside it, in one action.

Then waits until the channel answers, so you know the DLL is really in before you try anything.
The game itself keeps loading for minutes after that; wait for it with
`python -m tools.ck3.states <pid> wait`, which asks the text recogniser, not here.

**Waiting for the pipe is silent.** Until 21 October 2026 the wait asked with `channel.ask`, which
says out loud that the link is gone the moment no pipe is there - at once, measured the same day -
so a start that worked told the player it had failed. A pipe that is not there yet is what a start
expects, so it is asked with `channel.alive`, and only the timeout below speaks.
"""
import sys
import time

from tools import paths
from tools.ck3 import channel, inject
from tools.nvda import speech


def start(timeout: float = 60.0, arguments: str = '') -> tuple[int, str]:
    """Arguments are passed on to the game; `-debug_mode` opens the console. That flag belongs to
    research and never to the product."""
    number = inject.start_with_dll(paths.require('EXE'), paths.DLL, arguments)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if channel.alive():
            return number, channel.ask('hello', timeout=5.0).strip().splitlines()[0]
        time.sleep(0.5)
    raise OSError(speech.failure('the game', f'the channel did not answer within {timeout:.0f} seconds',
                                 'close the game and start it again'))


if __name__ == '__main__':
    number, greeting = start(arguments=' '.join(sys.argv[1:]))
    print(f'game started, pid {int(number)}')
    print(greeting)
