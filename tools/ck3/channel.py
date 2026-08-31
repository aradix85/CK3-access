"""Talks to the channel inside the DLL.

Three things keep this conversation on the rails:
  - one connection stays open for the whole session;
  - every reply starts with its length, so a half reply is noticed;
  - leftovers from a previous reply are discarded before anything new is asked.

Reconnecting and waiting for a free instance is allowed here: this is the boundary with another
process, and that is exactly where handling does belong.
"""
import ctypes
import msvcrt
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'nvda'))
import speech

PIPE = r'\\.\pipe\ck3_access'
_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_connection = None


def _queue(file):
    handle = msvcrt.get_osfhandle(file.fileno())
    ready = wintypes.DWORD()
    ok = _k32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(ready), None)
    return ready.value if ok else 0


def _drain(file):
    drained = 0
    while True:
        count = _queue(file)
        if not count:
            return drained
        drained += len(file.read(count))


def _connect(attempts=20):
    """Open the pipe, and say out loud when it stays shut.

    This is the hardest of the four cases that have to speak: with the channel gone there is no
    game information left either, so nothing further down can report it. The speech seam sits
    outside the game process for exactly this reason - it is still alive when the game is not.
    """
    for _ in range(attempts):
        try:
            return open(PIPE, 'r+b', buffering=0)
        except OSError:
            _k32.WaitNamedPipeW(ctypes.c_wchar_p(PIPE), 500)
    raise OSError(speech.failure('the game', 'the link with it is gone',
                                 'start the game again and try what you were doing once more'))


def close():
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def _wait_for_data(file, limit):
    """Wait until something is ready, with the clock running.

    Without this a read hangs forever if the other side sends nothing, and then the timeout is a
    paper promise.

    The wait step grows. An ordinary question is back within a millisecond, and with a fixed step
    of ten milliseconds every question cost ten - measured 27 July 2026: 10.6 ms per question, and
    0.7 ms once the step starts small. But a scan takes two minutes, and it must not be polled for
    two minutes straight. Hence the growing step.
    """
    start = time.time()
    while time.time() < limit:
        if _queue(file):
            return True
        elapsed = time.time() - start
        time.sleep(0.0002 if elapsed < 0.05 else 0.001 if elapsed < 1.0 else 0.01)
    return False


def _read_exact(file, count, limit):
    data = b''
    while len(data) < count:
        if not _wait_for_data(file, limit):
            break
        part = file.read(min(_queue(file), count - len(data)))
        if not part:
            break
        data += part
    if len(data) != count:
        raise OSError('reply arrived half: %d of %d bytes' % (len(data), count))
    return data


def _read_header(file, limit):
    header = b''
    while not header.endswith(b'\n'):
        if not _wait_for_data(file, limit):
            raise OSError('no reply within the time (is the command still running in the DLL?)')
        header += file.read(1)
    parts = header.decode('utf-8', 'replace').strip().split('\t')
    if len(parts) != 2 or parts[0] != 'reply':
        raise OSError('no usable header received: %r' % header[:40])
    return int(parts[1])


def ask(command, timeout=60.0, errors_ok=False):
    """Asks the channel one question and returns the answer as text.

    **An error from the DLL breaks hard.** The DLL answers errors as ordinary text - for a command
    that is too long, for instance, `error: command too long`. Anyone filtering that answer for
    their own kind of line then finds zero lines and concludes "empty result" instead of "failed".
    That cost an hour on 29 July 2026 and led to an invented bug in the DLL. So the message leaves
    here as an exception, not as an empty list.

    `errors_ok=True` is for the single caller that treats an error as a valid answer, such as
    `derive.read` on an unreadable address.
    """
    global _connection
    for attempt in (1, 2):
        if _connection is None:
            _connection = _connect()
        try:
            _drain(_connection)
            _connection.write(command.encode('utf-8'))
            limit = time.time() + timeout
            count = _read_header(_connection, limit)
            answer = _read_exact(_connection, count, limit).decode('utf-8', 'replace')
            if not errors_ok:
                for line in answer.split('\n'):
                    if line.startswith('error:'):
                        raise ValueError('%s (command was %d characters: %.60s...)'
                                         % (line.strip(), len(command), command))
            return answer
        except OSError:
            close()
            if attempt == 2:
                raise


if __name__ == '__main__':
    print(ask(' '.join(sys.argv[1:])), end='')
