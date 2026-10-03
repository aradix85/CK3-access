"""The DLL through its real pipe, on a target of its own, without the game.

`channel_host.c` loads `dll\\channel.dll`, builds a fake widget tree that holds every case the walk
must report, asks Windows about the keyboard ten times a second through its own import table, and
logs every key message its window receives with what GetKeyState said about shift, ctrl and alt.
Every check below is a prediction that can fail: a command that must be refused, a command that
must reach its handler, a loss the walk must report, a counter that must move, and a key that must
arrive with its modifiers held.

**Run it after every change to the DLL, before restarting the game:** building and this test take
seconds, a restart takes minutes. Skipped without a built DLL or a compiler, and while the game
runs, because both answer on the same pipe name.
"""
import os
import pathlib
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
    with open(os.path.join(ROOT, 'dll', 'build_channel.bat'), encoding='utf-8') as file:
        found = re.search(r'call "([^"]+vcvars64\.bat)"', file.read())
    return found.group(1) if found and os.path.exists(found.group(1)) else None


@pytest.fixture(scope='module', params=['plain', 'asan'])
def host(request, tmp_path_factory):
    """The target running a DLL: `plain` the one the build made, `asan` one built here with
    AddressSanitizer around both, which aborts the target and says so on the first bad access."""
    if not os.path.exists(DLL):
        pytest.skip('dll\\channel.dll is not built')
    if not vcvars():
        pytest.skip('no MSVC to build the target with')
    if channel.alive():
        pytest.skip('the game is running, and it answers on the same pipe')
    work = tmp_path_factory.mktemp(request.param)
    dll = DLL
    lines = ['@echo off', 'call "%s" >nul' % vcvars()]
    sanitize = ''
    if request.param == 'asan':
        dll = str(work / 'channel.dll')
        sanitize = '/Zi /fsanitize=address'
        lines += ['cl /nologo /Od %s /D_CRT_SECURE_NO_WARNINGS /LD "%s" user32.lib /Fe:channel.dll || exit /b 1'
                  % (sanitize, os.path.join(ROOT, 'dll', 'channel.cpp')),
                  'copy /y "%VCToolsInstallDir%bin\\Hostx64\\x64\\clang_rt.asan_dynamic-x86_64.dll" . || exit /b 1']
    lines.append('cl /nologo /Od %s "%s" user32.lib /Fe:host.exe || exit /b 1' % (sanitize, SOURCE))
    (work / 'build.bat').write_text('\r\n'.join(lines) + '\r\n')
    built = subprocess.run(['cmd', '/c', 'build.bat'], capture_output=True, text=True, cwd=work)
    assert built.returncode == 0, built.stdout + built.stderr
    with subprocess.Popen([str(work / 'host.exe'), dll, str(work / 'keys.log')], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as process:      # closes both pipes
        objects = [int(value, 16) for value in process.stdout.readline().split()[1:]]
        assert process.stdout.readline().strip() == 'loaded'
        while not channel.alive():
            time.sleep(0.05)
        yield process.pid, objects, str(work / 'keys.log')
        channel.close()
        process.kill()
        said = process.stderr.read()
    assert 'AddressSanitizer' not in said, said


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
    pid, (A, B, C, D, E, F, G, PAGE, MANY), log = host
    h = '%x'.__mod__
    failed = []

    def check(command, what, test):
        lines = lines_of(command)
        if not test(lines):
            failed.append('%s - %s: %s' % (command[:60], what, ' / '.join(lines)[:300]))

    def wait_then(seconds, *args):
        time.sleep(seconds)
        check(*args)

    def arrives(command, answer, keys):
        """The answer - a list, or a test on it - and the key messages the window logged: kind, key,
        context bit, then shift, ctrl and alt as GetKeyState gave them while the message was
        handled. ? is either."""
        before = len(pathlib.Path(log).read_text().splitlines())
        lines = lines_of(command)
        time.sleep(0.4)
        got = pathlib.Path(log).read_text().splitlines()[before:]
        fits = len(got) == len(keys) and all(
            len(g.split()) == len(k.split()) and all(b in ('?', a) for a, b in zip(g.split(), k.split(), strict=True))
            for g, k in zip(got, keys, strict=True))
        if not (answer(lines) if callable(answer) else lines == answer) or not fits:
            failed.append('%s - %s / keys: %s' % (command, ' / '.join(lines), ' / '.join(got)))

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

    arrives('sendkey 112', ['key sent\t112'], ['down 70 0 0 0 0', 'up 70 0 0 0 0'])
    arrives('combo 50 160 112', ['combo sent\t160\t112'],
            ['down 10 0 1 0 0', 'down 70 0 1 0 0', 'up 70 0 1 0 0', 'up 10 0 ? 0 0'])
    arrives('combo 50 164 82', ['combo sent\t164\t82'],
            ['sysdown 12 1 0 0 1', 'sysdown 52 1 0 0 1', 'sysup 52 1 0 0 1', 'up 12 0 0 0 ?'])
    arrives('combo 50 162 164 82', ['combo sent\t162\t164\t82'],
            ['down 11 0 0 1 0', 'down 12 0 0 1 1', 'down 52 0 0 1 1', 'up 52 0 0 1 1', 'up 12 0 0 1 ?',
             'up 11 0 0 ? 0'])
    arrives('sendkey 112', ['key sent\t112'], ['down 70 0 0 0 0', 'up 70 0 0 0 0'])
    for command, text in (('combo 50 112', 'combo needs at least one modifier'),
                          ('combo 50 160', 'combo needs at least one modifier'),
                          ('combo x', 'combo needs a pause'),
                          ('combo 2000 160 112', 'a pause of 2000'),
                          ('combo 50 300 112', 'key code 300'),
                          ('combo 50 112 160', 'the last code is the key'),
                          ('combo 50 65 112', '65 is not left or right'),
                          ('combo 50 160 161 112', 'the same modifier twice'),
                          ('combo 50 160 162 164 165 112', 'at most 3 modifiers'),
                          ('combo 50 160 112 x', 'not a key code')):
        arrives(command, error(text), [])
    check('combo', 'refused', refused)
    arrives('sendchar 65', ['char sent\t65'], [])
    arrives('mouse 5 5 0', ['mouse\t5\t5\t0'], [])
    check('keys on', 'hooks the window', lambda ls: ls == ['keys on'])
    for command in ('sendkey 112 4', 'mouse 5 5', 'waitkey 10 5'):
        check(command, 'refused', refused)
    check('swallow 38 40', 'two keys', lambda ls: ls == ['swallow\t2'])
    check('swallow 300', 'not a virtual key', error('key code 300'))
    check('swallow 38 x', 'refused at x', error('not a key code'))
    check('swallow', 'none', lambda ls: ls == ['swallow\t0'])
    check('waitkey 10', 'nothing pressed', lambda ls: ls == [])
    check('keys off', 'puts the window back', lambda ls: ls == ['keys off'])
    check('keys off', 'unchanged', lambda ls: ls == ['keys unchanged'])
    for command in ('childfield f0 fc', 'call %s 0' % h(A), 'waitchange 1', 'count on'):
        check(command, 'removed, so refused', refused)

    assert not failed, '\n'.join(failed)


def clang_tidy():
    """Where Windows says LLVM's installer put itself: the InstallLocation of its uninstall entry.

    The NSIS installer of LLVM 22 also wrote `SOFTWARE\\LLVM\\LLVM`; the MSI of LLVM 23 does not,
    measured 3 October 2026, and a lookup on that key turned this check into a quiet skip. Both
    registry views are walked because a 32-bit and a 64-bit installer each write their own.
    """
    import winreg
    uninstall = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uninstall, 0, winreg.KEY_READ | view) as root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                with winreg.OpenKey(root, winreg.EnumKey(root, i)) as entry:
                    try:
                        name = winreg.QueryValueEx(entry, 'DisplayName')[0]
                        where = winreg.QueryValueEx(entry, 'InstallLocation')[0]
                    except OSError:         # most entries lack one of the two
                        continue
                found = os.path.join(where, 'bin', 'clang-tidy.exe')
                if name == 'LLVM' and os.path.exists(found):
                    return found
    return None


def test_clang_tidy_finds_nothing():
    """The checks in `dll\\.clang-tidy`, each finding an error; the MSVC analysis runs in the build."""
    if not clang_tidy() or not vcvars():
        pytest.skip('clang-tidy or MSVC is not installed')
    done = subprocess.run('call "%s" >nul && "%s" channel.cpp --quiet -- --driver-mode=cl /EHsc'
                          % (vcvars(), clang_tidy()), shell=True, capture_output=True, text=True,
                          cwd=os.path.join(ROOT, 'dll'))
    assert done.returncode == 0, done.stdout + done.stderr
