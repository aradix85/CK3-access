"""Starts CK3 with the channel inside it, in one action.

Then waits until the channel answers, so you know the DLL is really in before you try anything.
The game itself keeps loading for several minutes after that; waiting for it belongs with
`channel.ask('scan')`, not here.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import inject
import channel
import paths

GAME = paths.require('EXE')
WORK_DIR = os.path.dirname(GAME)         # CK3 looks for its files from here
CHANNEL = paths.DLL


def start(timeout=60.0, arguments=''):
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
    raise OSError('the channel did not answer within %.0f seconds' % timeout)


if __name__ == '__main__':
    number, greeting = start(arguments=' '.join(sys.argv[1:]))
    print('game started, pid %d' % number)
    print(greeting)
