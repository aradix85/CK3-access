"""Talks to the channel inside the DLL.

Three things keep this conversation on the rails:
  - one connection stays open for the whole session;
  - every reply starts with its length, so a half reply is noticed;
  - leftovers from a previous reply are discarded before anything new is asked.

**A question is sent once.** Only a link that breaks is opened again and the question asked anew; a
reply that comes too late or makes no sense is an error, because the command may still be running in
the game, and a click sent twice is two clicks.

Reconnecting and waiting for a free instance is allowed here: this is the boundary with another
process, and that is exactly where handling does belong.
"""
import ctypes
import io
import msvcrt
import sys
import time
from ctypes import wintypes

from tools.nvda import speech

PIPE = r'\\.\pipe\ck3_access'
_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_connection: io.FileIO | None = None


class Gone(OSError):
    """The link broke under a question and does not open again: the game has ended.

    Not spoken. A player who closes the game knows it, and one whose game crashed notices that
    without being told (her decision, 21 October 2026).
    """


def _queue(file: io.FileIO) -> int:
    """Bytes waiting on the pipe. A pipe that cannot be asked is broken, and says so."""
    handle = msvcrt.get_osfhandle(file.fileno())
    ready = wintypes.DWORD()
    if not _k32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(ready), None):
        raise ctypes.WinError(ctypes.get_last_error())
    return ready.value


def _drain(file: io.FileIO) -> None:
    while count := _queue(file):
        file.read(count)


def _connect() -> io.FileIO:
    """Open the pipe, waiting for a free instance. `ask` decides whether a shut pipe is said."""
    for _ in range(20):
        try:
            return open(PIPE, 'r+b', buffering=0)
        except OSError:
            _k32.WaitNamedPipeW(ctypes.c_wchar_p(PIPE), 500)
    raise Gone('the link with the game does not open')


def alive() -> bool:
    """Is the link there? Asked without speaking, for a caller that expects it to be gone.

    `ask` says it out loud when there is no link to begin with, and that is right: for anything that
    needs the game, a missing link is the one failure with nothing left underneath it to report.
    Waiting for the game to go or to come up is the case where the link is expected to be missing.
    """
    try:
        with open(PIPE, 'r+b', buffering=0):
            return True
    except OSError:
        return False


def close() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def _wait_for_data(file: io.FileIO, limit: float) -> bool:
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


def _read_exact(file: io.FileIO, count: int, limit: float) -> bytes:
    data = b''
    while len(data) < count:
        if not _wait_for_data(file, limit):
            raise RuntimeError(f'reply arrived half within the time: {len(data)} of {int(count)} bytes')
        data += file.read(min(_queue(file), count - len(data)))
    return data


def _read_header(file: io.FileIO, limit: float) -> int:
    header = b''
    while not header.endswith(b'\n'):
        if not _wait_for_data(file, limit):
            raise RuntimeError('no reply within the time (is the command still running in the DLL?)')
        header += file.read(1)
    parts = header.decode('utf-8', 'replace').strip().split('\t')
    if len(parts) != 2 or parts[0] != 'reply':
        raise RuntimeError(f'no usable header received: {header[:40]!r}')
    return int(parts[1])


def ask(command: str, timeout: float = 60.0, errors_ok: bool = False) -> str:
    """Asks the channel one question and returns the answer as text.

    **An error from the DLL breaks hard.** The DLL answers errors as ordinary text - for a command
    that is too long, for instance, `error: command too long`. Anyone filtering that answer for
    their own kind of line then finds zero lines and concludes "empty result" instead of "failed".
    That cost an hour on 29 July 2026 and led to an invented bug in the DLL. So the message leaves
    here as an exception, not as an empty list.

    `errors_ok=True` is for the single caller that treats an error as a valid answer, such as
    `derive.read` on an unreadable address.

    **A link that is not there is said out loud; a link that breaks and stays shut is not.** With
    no link to begin with there is no game information either, so nothing further down can report
    it, and the speech seam sits outside the game process for exactly that reason. A link that
    breaks under a question is the game ending, and that raises `Gone` without a word.
    """
    global _connection
    retried = False
    while True:
        if _connection is None:
            try:
                _connection = _connect()
            except Gone:
                if retried:
                    raise
                raise OSError(speech.failure('the game', 'the link with it is gone',
                                             'start the game again and try what you were doing once more')) from None
        try:
            _drain(_connection)
            _connection.write(command.encode('utf-8'))
            limit = time.time() + timeout
            count = _read_header(_connection, limit)
            answer = _read_exact(_connection, count, limit).decode('utf-8', 'replace')
            if not errors_ok:
                for line in answer.split('\n'):
                    if line.startswith('error:'):
                        raise ValueError(f'{line.strip()} (command was {len(command)} characters: {command!s:.60}...)')
            return answer
        except OSError:
            close()
            if retried:
                raise
            retried = True
        except RuntimeError:
            close()             # a late reply must not be read as the answer to the next question
            raise


if __name__ == '__main__':
    print(ask(' '.join(sys.argv[1:])), end='')
