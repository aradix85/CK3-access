"""The DLL through its real pipe, on a target of its own, without the game.

`channel_host.c` loads `dll\\channel.dll`, builds a fake widget tree that holds every case the walk
must report, and asks Windows about the keyboard ten times a second through its own import table.
Every check below is a prediction that can fail: a command that must be refused, a command that
must reach its handler, a loss the walk must report, and a counter that must move.

**Run it after every change to the DLL, before restarting the game:** building and this test take
seconds, a restart takes minutes. Skipped without a built DLL or a compiler, and while the game
runs, because both answer on the same pipe name.
"""
import os
import re
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'ck3'))
import channel

DLL = os.path.join(ROOT, 'dll', 'channel.dll')
SOURCE = os.path.join(ROOT, 'tests', 'channel_host.c')


def vcvars():
    """The compiler setup that `dll\\build_channel.bat` uses, so its path lives in one place."""
    found = re.search(r'call "([^"]+vcvars64\.bat)"', open(os.path.join(ROOT, 'dll', 'build_channel.bat')).read())
    return found.group(1) if found and os.path.exists(found.group(1)) else None


@pytest.fixture(scope='module')
def host(tmp_path_factory):
    if not os.path.exists(DLL):
        pytest.skip('dll\\channel.dll is not built')
    if not vcvars():
        pytest.skip('no MSVC to build the target with')
    if channel.alive():
        pytest.skip('the game is running, and it answers on the same pipe')
    work = tmp_path_factory.mktemp('channel')
    subprocess.run('call "%s" >nul && cl /nologo /W3 /Od "%s" user32.lib /Fe:host.exe' % (vcvars(), SOURCE),
                   shell=True, check=True, capture_output=True, cwd=work)
    process = subprocess.Popen([str(work / 'host.exe'), DLL], stdout=subprocess.PIPE, text=True)
    objects = [int(value, 16) for value in process.stdout.readline().split()[1:]]
    assert process.stdout.readline().strip() == 'loaded'
    while not channel.alive():
        time.sleep(0.05)
    yield process.pid, objects
    channel.close()
    process.kill()
    process.wait()


def lines_of(command):
    return [line for line in channel.ask(command, errors_ok=True).split('\n') if line and line != 'end']


def kind(lines, prefix):
    return [line.split('\t') for line in lines if line.startswith(prefix + '\t')]


def refused(lines):
    return any(line.startswith('error: unknown command, or more than it reads') for line in lines)


def error(text):
    return lambda lines: any(line.startswith('error: ' + text) for line in lines)


def addresses(lines, prefix):
    return {int(row[1], 16) for row in kind(lines, prefix)}


def counts(lines):
    return {row[1]: row for row in kind(lines, 'count')}


def test_every_command(host):
    pid, (A, B, C, D, E, F, G, PAGE, MANY) = host
    h = '%x'.__mod__
    failed = []

    def check(command, what, test):
        lines = lines_of(command)
        if not test(lines):
            failed.append('%s - %s: %s' % (command[:60], what, ' / '.join(lines)[:300]))

    def wait_then(seconds, *args):
        time.sleep(seconds)
        check(*args)

    check('hello', 'answers from the target', lambda ls: ls[0].startswith('channel\t%d\t' % pid))
    check('hello x', 'refused', refused)
    check('tree ' + h(A), 'no walk before set and vtables', error('set and vtables come first'))
    check('scan %s %s' % (h(PAGE), h(PAGE + 4096)), 'no scan before vtables', error('no vtables set'))
    check('set 8 10 18 20 40 60', 'six offsets refused', error('set needs exactly seven'))
    check('set 8 10 18 20 40 60 68 70', 'eight offsets refused', error('set needs exactly seven'))
    check('set 8 10 18 20 40 60 68', 'seven accepted', lambda ls: ls == ['fields set'])
    check('vtables 1 zz', 'refused at zz', error('not a vtable address'))
    check('vtables ' + ' '.join('%x' % (i + 1) for i in range(257)), '257 refused', error('more than 256 vtables'))
    check('vtables 1111', 'one set', lambda ls: ls == ['vtables set\t1'])

    check('tree ' + h(A), 'five widgets, five losses, one stranger, seven visited',
          lambda ls: addresses(ls, 'w') == {A, B, E, F, G} and addresses(ls, 'missing') == {D, D + 0x100, E, F, G}
          and 'not widgets\t1' in ls and ls[-1] == 'done\t7' and not any(line.startswith('error') for line in ls))
    check('tree ' + h(A), 'the fields of one widget', lambda ls: any(
        row[1:] == [h(B), '1111', '1.0', '2.0', '3.0', '4.0', h(A), 'child', 'Hello'] for row in kind(ls, 'w')))
    check('tree %s 2' % h(A), 'a limit says so', lambda ls: any(line.startswith('limit hit\t') for line in ls))
    check('tree %s 2 x' % h(A), 'refused', refused)
    check('scan %s %s' % (h(PAGE), h(PAGE + 4096)), 'up to the last eight bytes of a region',
          lambda ls: addresses(ls, 'w') == {A, B, E, F, G, PAGE + 4088} and ls[-1] == 'done\t6\tskipped\t0')
    check('scan 1', 'refused', refused)

    check('count', 'hung in, all four counted', lambda ls: [row[2] for row in counts(ls).values()] == ['counted'] * 4)
    wait_then(1.5, 'count', 'every counter moved', lambda ls: all(int(row[3]) >= 10 for row in counts(ls).values()))
    wait_then(1.5, 'count', 'shift asked, per key', lambda ls: ['GetKeyState', 'a0'] in [row[1:3] for row in kind(ls, 'asked')]
              and ['GetAsyncKeyState', '10'] in [row[1:3] for row in kind(ls, 'asked')])
    check('count', 'read again at once: near zero', lambda ls: all(int(row[3]) <= 2 for row in counts(ls).values()))
    check('count x', 'refused', refused)

    check('read %s 8' % h(PAGE), 'the root vtable', lambda ls: ls == ['1111000000000000'])
    check('read %s 8 9' % h(PAGE), 'refused', refused)
    check('readmany 8 %s %s' % (h(A), h(B)), 'two lines', lambda ls: len(kind(ls, 'l')) == 2 and ls[-1] == 'done\t2')
    check('readmany 8 %s zz' % h(A), 'refused at zz', error('not an address'))
    check('findin %s %s 72 6f 6f 74' % (h(PAGE), h(PAGE + 0x80)), 'the name root, once',
          lambda ls: [row[1] for row in kind(ls, 't')] == [h(A + 0x20)])
    check('findin %s %s 43 4b 33 21' % (h(MANY), h(MANY + 4096)), 'more than 200 hits is an error',
          lambda ls: len(kind(ls, 't')) == 200 and error('300 hits and only the first 200')(ls))
    check('findin %s %s 43 4' % (h(PAGE), h(PAGE + 64)), 'one hex digit refused', error('not a hex byte'))
    check('find ?? 4b', 'a wildcard first refused', error('first byte cannot be a wildcard'))

    for command in ('sendkey 112', 'sendchar 65', 'mouse 5 5 0', 'keys on'):
        check(command, 'reaches its handler', error('no window found'))
    for command in ('sendkey 112 4', 'mouse 5 5', 'waitkey 10 5'):
        check(command, 'refused', refused)
    check('swallow 38 40', 'two keys', lambda ls: ls == ['swallow\t2'])
    check('swallow 300', 'not a virtual key', error('key code 300'))
    check('swallow 38 x', 'refused at x', error('not a key code'))
    check('swallow', 'none', lambda ls: ls == ['swallow\t0'])
    check('waitkey 10', 'nothing pressed', lambda ls: ls == [])
    check('keys off', 'unchanged', lambda ls: ls == ['keys unchanged'])
    for command in ('childfield f0 fc', 'call %s 0' % h(A), 'waitchange 1', 'count on'):
        check(command, 'removed, so refused', refused)

    assert not failed, '\n'.join(failed)
