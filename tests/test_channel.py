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
import ctypes
import os
import pathlib
import re
import subprocess
import threading
import time

import pytest

from tools.ck3 import channel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DLL = os.path.join(ROOT, 'dll', 'channel.dll')
SOURCE = os.path.join(ROOT, 'tests', 'channel_host.c')
# On the maintainer's machine a missing tool fails the run instead of skipping it: a green run must not
# hide a check that never ran (her decision, 3 October 2026). The marker `.tools-required` is kept out
# of the repository by .gitignore, so a clone without MSVC or LLVM still skips. A running game stays a
# skip everywhere: it answers on the same pipe, and that is no missing tool.
TOOLS_REQUIRED = os.path.exists(os.path.join(ROOT, '.tools-required'))


def missing(reason):
    """A tool this test needs is not there: a failure where tools are required, a skip elsewhere."""
    if TOOLS_REQUIRED:
        pytest.fail(reason + ' (and .tools-required says this machine has it)')
    pytest.skip(reason)


# Shift, ctrl and alt, either side. The target asks GetKeyState, and that includes the real keyboard:
# a person reading along with NVDA holds ctrl, often without noticing. Measured 3 October 2026: in six
# runs a real modifier was seen around a key five times, and the one failure fell exactly on it.
PHYSICAL = {0x10: 'shift', 0x11: 'ctrl', 0x12: 'alt'}

# Two values nothing in the target holds: one handed over as a vtable, one searched for with `find`.
LISTED = 0x5EEDC0DE0BADF00D
SOUGHT = 0x7E57F00D5EEDBEEF


def physical_modifiers():
    """The modifiers held on the real keyboard right now, by name."""
    return {name for vk, name in PHYSICAL.items() if ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000}


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
        missing('dll\\channel.dll is not built')
    if not vcvars():
        missing('no MSVC to build the target with')
    if channel.alive():
        pytest.skip('the game is running, and it answers on the same pipe')
    work = tmp_path_factory.mktemp(request.param)
    dll = DLL
    lines = ['@echo off', f'call "{vcvars()}" >nul']
    sanitize = ''
    if request.param == 'asan':
        dll = str(work / 'channel.dll')
        sanitize = '/Zi /fsanitize=address'
        lines += ['cl /nologo /Od {} /LD "{}" user32.lib /Fe:channel.dll || exit /b 1'.format(sanitize, os.path.join(ROOT, 'dll', 'channel.cpp')),
                  'copy /y "%VCToolsInstallDir%bin\\Hostx64\\x64\\clang_rt.asan_dynamic-x86_64.dll" . || exit /b 1']
    lines.append(f'cl /nologo /Od {sanitize} "{SOURCE}" user32.lib /Fe:host.exe || exit /b 1')
    (work / 'build.bat').write_text('\r\n'.join(lines) + '\r\n')
    built = subprocess.run(['cmd', '/c', 'build.bat'], capture_output=True, text=True, cwd=work,
                           check=False)                 # the return code is asserted below, with the output
    assert built.returncode == 0, built.stdout + built.stderr
    with subprocess.Popen([str(work / 'host.exe'), dll, str(work / 'keys.log')], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as process:      # closes both pipes
        out, err = process.stdout, process.stderr
        assert out is not None and err is not None    # both asked for as pipes, one line up
        objects = [int(value, 16) for value in out.readline().split()[1:]]
        assert out.readline().strip() == 'loaded'
        while not channel.alive():
            time.sleep(0.05)
        yield process.pid, objects, str(work / 'keys.log'), request.param
        channel.close()
        process.kill()
        said = err.read()
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
    pid, (A, B, _C, D, E, F, G, PAGE, MANY, COMBINED), log, variant = host
    h = '%x'.__mod__
    failed = []

    def check(command, what, test):
        lines = lines_of(command)
        if not test(lines):
            failed.append('{} - {}: {}'.format(command[:60], what, ' / '.join(lines)[:300]))

    def wait_then(seconds, *args):
        time.sleep(seconds)
        check(*args)

    interfered = []
    seen: list[tuple[float, set[str]]] = []     # a real modifier down: when, and which; all test long
    done = threading.Event()

    def watch():
        while not done.is_set():
            names = physical_modifiers()
            if names:
                seen.append((time.monotonic(), names))
            time.sleep(0.005)
    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()

    def arrives(command, answer, keys):
        """The answer - a list, or a test on it - and the key messages the window logged: kind, key,
        context bit, then shift, ctrl and alt as GetKeyState gave them while the message was
        handled. ? is either. A real modifier down at any moment from the send to the reading makes
        the reading worthless - also while the channel is still sending, which a combination takes a
        fifth of a second to do: wait until none is held, at most thirty seconds, send, and send again
        if one came down meanwhile, at most ten times. Every disturbed send is listed with its key."""
        for _ in range(10):
            wait_until = time.monotonic() + 30
            while physical_modifiers() and time.monotonic() < wait_until:
                time.sleep(0.05)
            start = time.monotonic()
            before = len(pathlib.Path(log).read_text().splitlines())
            lines = lines_of(command)
            time.sleep(0.4)
            got = pathlib.Path(log).read_text().splitlines()[before:]
            end = time.monotonic()
            held = {name for moment, names in list(seen) if start <= moment <= end for name in names}
            if not held:
                break
            interfered.append(f"{command} ({'+'.join(sorted(held))})")
        fits = len(got) == len(keys) and all(
            len(g.split()) == len(k.split()) and all(b in ('?', a) for a, b in zip(g.split(), k.split(), strict=True))
            for g, k in zip(got, keys, strict=True))
        if not (answer(lines) if callable(answer) else lines == answer) or not fits:
            failed.append('{} - {} / keys: {}'.format(command, ' / '.join(lines), ' / '.join(got)))

    check('hello', 'answers from the target', lambda ls: ls[0].startswith(f'channel\t{int(pid)}\t'))
    check('hello x', 'refused', refused)
    check('tree ' + h(A), 'no walk before set and vtables', error('set and vtables come first'))
    check(f'scan {h(PAGE)} {h(PAGE + 4096)}', 'no scan before vtables', error('no vtables set'))
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
    check(f'tree {h(A)} 2', 'a limit says so', lambda ls: any(line.startswith('limit hit\t') for line in ls))
    check(f'tree {h(A)} 2 x', 'refused', refused)
    check(f'scan {h(PAGE)} {h(PAGE + 4096)}', 'up to the last eight bytes of a region',
          lambda ls: addresses(ls, 'w') == {A, B, E, F, G, PAGE + 4088} and ls[-1] == 'done\t6\tskipped\t0')
    check('scan 1', 'refused', refused)

    # A search of the game's memory must not find the DLL itself: a session leaves what it handled on
    # its own stack. Measured 4 October 2026 in the game: the sorted copy of the vtable list that
    # `vtables` left there came back from the scan as twenty widgets costing seconds each. LISTED and
    # SOUGHT are in no memory of the target, so wherever a search finds one, it found the DLL.
    # Plain only: a search over the whole target reads the stacks of its other threads, and under
    # AddressSanitizer their redzones abort it - a report on reading foreign memory, which is what a
    # search is for. The ranged scans above run the own-stack test under AddressSanitizer as well.
    check(f'vtables 1111 {h(LISTED)}', 'two set', lambda ls: ls == ['vtables set\t2'])
    if variant == 'plain':
        check('scan', 'not the list it was just given',
              lambda ls: LISTED not in {int(row[2], 16) for row in kind(ls, 'w')})
        check('scan', 'says it skipped its own stack', lambda ls: bool(kind(ls, 'own stack')))
        pattern = SOUGHT.to_bytes(8, 'little').hex(' ')
        check('find ' + pattern, 'not the pattern it searches for', lambda ls: not kind(ls, 't'))
        check('find ' + pattern, 'says it skipped its own stack', lambda ls: bool(kind(ls, 'own stack')))
    check('vtables 1111', 'one set again', lambda ls: ls == ['vtables set\t1'])

    # Write-combined memory is what the processor hands the graphics card: no object of the game lives
    # there, and reading it bypasses the cache. Measured 4 October 2026: the piece of the scan holding
    # one such region of 128 MB, 144 MB in all, took five seconds; pieces of 70 MB without one, 0.13.
    check(f'scan {h(COMBINED)} {h(COMBINED + 4096)}', 'write-combined memory skipped, and said',
          lambda ls: not kind(ls, 'w') and kind(ls, 'uncached') == [['uncached', '1']])
    check(f'findin {h(COMBINED)} {h(COMBINED + 4096)} 57 43 57 43', 'by find as well',
          lambda ls: not kind(ls, 't') and kind(ls, 'uncached') == [['uncached', '1']])

    check('count', 'hung in, all four counted', lambda ls: [row[2] for row in counts(ls).values()] == ['counted'] * 4)
    wait_then(1.5, 'count', 'every counter moved', lambda ls: all(int(row[3]) >= 10 for row in counts(ls).values()))
    wait_then(1.5, 'count', 'shift asked, per key', lambda ls: ['GetKeyState', 'a0'] in [row[1:3] for row in kind(ls, 'asked')]
              and ['GetAsyncKeyState', '10'] in [row[1:3] for row in kind(ls, 'asked')])
    check('count', 'read again at once: near zero', lambda ls: all(int(row[3]) <= 2 for row in counts(ls).values()))
    check('count x', 'refused', refused)

    check(f'read {h(PAGE)} 8', 'the root vtable', lambda ls: ls == ['1111000000000000'])
    check(f'read {h(PAGE)} 8 9', 'refused', refused)
    check(f'readmany 8 {h(A)} {h(B)}', 'two lines', lambda ls: len(kind(ls, 'l')) == 2 and ls[-1] == 'done\t2')
    check(f'readmany 8 {h(A)} zz', 'refused at zz', error('not an address'))
    check(f'findin {h(PAGE)} {h(PAGE + 0x80)} 72 6f 6f 74', 'the name root, once',
          lambda ls: [row[1] for row in kind(ls, 't')] == [h(A + 0x20)])
    check(f'findin {h(MANY)} {h(MANY + 4096)} 43 4b 33 21', 'more than 200 hits is an error',
          lambda ls: len(kind(ls, 't')) == 200 and error('300 hits and only the first 200')(ls))
    check(f'findin {h(PAGE)} {h(PAGE + 64)} 43 4', 'one hex digit refused', error('not a hex byte'))
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
    for command in ('childfield f0 fc', f'call {h(A)} 0', 'waitchange 1', 'count on'):
        check(command, 'removed, so refused', refused)

    # A number is digits only, and fits its field. Measured on the sscanf reader, 3 October 2026: a
    # minus came out as the number counted down from the top (`sendkey -1` sent key 4294967295), and
    # a key code too big for 32 bits wrapped round silently - `combo 50 160 4294967408` sent shift+F1.
    for command in ('sendkey -1', 'sendkey +1', 'sendkey 4294967296', f'read {h(PAGE)} -8',
                    'tree 1' + '0' * 16, 'mouse -5 5 0'):
        check(command, 'refused', refused)
    check('swallow 38 -40', 'a sign refused', error('not a key code'))
    check('vtables 1 -2', 'a sign refused', error('not a vtable address'))
    check('combo 50 160 4294967408', 'too big for 32 bits', error('not a key code'))
    check('find  ?? 4b', 'blanks before the pattern', error('first byte cannot be a wildcard'))

    done.set()
    watcher.join()
    if interfered:
        print('a real modifier was held around: ' + ', '.join(interfered))
    assert not failed, '\n'.join(failed + ['a real modifier was held around: ' + ', '.join(interfered)]
                                 if interfered else failed)


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
        missing('clang-tidy or MSVC is not installed')
    done = subprocess.run(f'call "{vcvars()}" >nul && "{clang_tidy()}" channel.cpp --quiet -- --driver-mode=cl /EHsc', shell=True, capture_output=True, check=False, text=True,
                          cwd=os.path.join(ROOT, 'dll'))
    assert done.returncode == 0, done.stdout + done.stderr
