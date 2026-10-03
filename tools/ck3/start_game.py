"""Starts CK3 with the channel inside it, in one action.

Then waits until the channel answers, so you know the DLL is really in before you try anything.
The game itself keeps loading for minutes after that; wait for it with
`python -m tools.ck3.states <pid> wait`, which asks the text recogniser, not here.
"""
import os
import sys
import time

from tools import paths
from tools.ck3 import channel, inject

GAME = paths.require('EXE')
WORK_DIR = os.path.dirname(GAME)         # CK3 looks for its files from here
CHANNEL = paths.DLL


def start(timeout: float = 60.0, arguments: str = '') -> tuple[int, str]:
    """Arguments are passed on to the game; `-debug_mode` opens the console. That flag belongs to
    research and never to the product."""
    os.chdir(WORK_DIR)
    number = inject.start_with_dll(GAME, os.path.abspath(CHANNEL), arguments)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            answer = channel.ask('hello', timeout=5.0)
            if 'channel' in answer:
                return number, answer.strip().splitlines()[0]
        except OSError:
            time.sleep(0.5)
    raise OSError(f'the channel did not answer within {timeout:.0f} seconds')


if __name__ == '__main__':
    number, greeting = start(arguments=' '.join(sys.argv[1:]))
    print(f'game started, pid {int(number)}')
    print(greeting)
