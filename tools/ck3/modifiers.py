"""Do system-level keys reach the game when it is in front? The first step of the modifier round.

    python tools\\ck3\\modifiers.py <pid>

Start the game first, without -debug_mode: `start_game.py -loadsave=<save>`. This waits until a
game is on screen, says through NVDA that it is about to take the foreground, takes it for a few
seconds, and gives it back. Predictions that can fail: F1 by SendInput draws character_window,
and shift+F1 by SendInput draws ledger_window and not character_window.

Beside them the channel's `count` says what the game asked Windows about the keyboard: idle in
front, during F1, and during shift+F1. With shift held through SendInput, GetKeyState moving is the
positive control the counter of August 2026 never had; a posted shift does not set the key state
that SendInput sets, which is the assumption this is here to settle.

Measured 2 October 2026 on 1.20.0.3, without mods or debug mode: F1 drew character_window alone,
shift+F1 ledger_window alone, and the state and the clock came back. The counter stood at nothing
idle and during F1, and during shift+F1 GetKeyState was asked 44 times, every time for left shift;
raw input was never read. So the game asks about shift only while it believes shift is down, which
is why the counter of August could not move. The channel's `combo` now does the same without the
foreground, by answering that question itself; this stays as the measurement with real keys.

Every key goes in only while the game window is the foreground window, checked right before it,
so nothing can land in the player's own window, and a shift that went down always goes up again.
Windows are closed again with posted keys, which need no foreground, and the state has to come back.

Shift goes in as left shift, the key a keyboard reports, and Windows has to hold it down before F1
is sent. SDL lets go of a shift the moment GetKeyState says left shift is up (assumed from the SDL2
source), so a shift Windows never held would make the game look deaf when the fault is ours.
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'nvda'))

import channel
import speech
import states
import windowgrab
import terminal

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.BringWindowToTop.argtypes = [wt.HWND]
user32.IsWindow.argtypes = [wt.HWND]
user32.GetAsyncKeyState.restype = ctypes.c_short
VK_LSHIFT, VK_F1, VK_ESCAPE = 0xA0, 0x70, 0x1B
# Left shift, left ctrl and left alt, the keys a keyboard reports, each with the generic key
# Windows has to hold down along with it.
MODIFIERS = {'shift': 0xA0, 'ctrl': 0xA2, 'alt': 0xA4}
GENERIC = {0xA0: 0x10, 0xA2: 0x11, 0xA4: 0x12}
KEYEVENTF_KEYUP, INPUT_KEYBOARD = 0x0002, 1


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wt.WORD), ('wScan', wt.WORD), ('dwFlags', wt.DWORD), ('time', wt.DWORD),
                ('dwExtraInfo', ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    """Only here so INPUT has the size Windows expects: SendInput refuses a smaller one."""
    _fields_ = [('dx', wt.LONG), ('dy', wt.LONG), ('mouseData', wt.DWORD), ('dwFlags', wt.DWORD),
                ('time', wt.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class _UNION(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wt.DWORD), ('u', _UNION)]


def bring(hwnd):
    """The foreground, from a process that does not have it: only with the input queues joined."""
    ours = kernel32.GetCurrentThreadId()
    front = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    user32.AttachThreadInput(ours, front, True)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    user32.AttachThreadInput(ours, front, False)
    time.sleep(0.3)
    return user32.GetForegroundWindow() == hwnd


class Keys(object):
    def __init__(self, game_window):
        self.game = game_window
        self.down = []

    def _send(self, vk, up):
        event = INPUT(type=INPUT_KEYBOARD)
        event.u.ki = KEYBDINPUT(vk, user32.MapVirtualKeyW(vk, 0), KEYEVENTF_KEYUP if up else 0, 0, 0)
        if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
            raise OSError('SendInput refused, error %d' % ctypes.get_last_error())

    def send(self, vk, up):
        if user32.GetForegroundWindow() != self.game:
            raise RuntimeError('the game lost the foreground; nothing more is sent')
        self._send(vk, up)
        if vk in GENERIC:
            if up:
                self.down.remove(vk)
            else:
                self.down.append(vk)

    def release(self):
        """A modifier left down would follow the player into her own window. Up is harmless anywhere."""
        for vk in reversed(self.down):
            self._send(vk, True)
        self.down = []

    def combo(self, modifiers, key):
        """Modifiers down, the key once, modifiers up; the key goes in only once Windows holds them."""
        for vk in modifiers:
            self.send(vk, False)
            time.sleep(0.1)
        time.sleep(0.2)
        if not all(held(vk) and held(GENERIC[vk]) for vk in modifiers):
            raise SystemExit('Windows does not hold %s down after SendInput; nothing was pressed with it'
                             % ', '.join('0x%02X' % vk for vk in modifiers if not held(vk)))
        self.send(key, False)
        time.sleep(0.05)
        self.send(key, True)
        time.sleep(0.3)
        for vk in reversed(modifiers):
            self.send(vk, True)


def held(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def counted():
    """What the game asked since the previous `count`, which also starts the next interval."""
    out = {}
    for line in channel.ask('count').split('\n'):
        part = line.split('\t')
        if part[0] == 'count':
            out[part[1]] = int(part[3])
        elif part[0] == 'asked':
            out['%s %s' % (part[1], part[2])] = int(part[3])
    return out


def drawn_after(game, wanted, seconds=6.0):
    deadline = time.time() + seconds
    while True:
        _, _, now = game.state()
        if wanted in now or time.time() > deadline:
            return now
        time.sleep(0.3)


def back_to(game, baseline, first_key):
    """Shut what opened with posted keys, and prove the state is back."""
    channel.ask('sendkey %d' % first_key)
    for _ in range(4):
        time.sleep(1.4)
        _, _, now = game.state()
        if now == baseline:
            return True
        channel.ask('sendkey %d' % VK_ESCAPE)
    return game.state()[2] == baseline


def main(pid):
    import windowmap
    from harvest import paused
    print('state:', states.wait(pid), flush=True)
    game = windowmap.Game(pid)
    _, _, baseline = game.state()
    if baseline:
        raise SystemExit('not starting from an empty screen; still drawn: %s' % ', '.join(sorted(baseline)))
    if not paused(game):
        raise SystemExit('the clock is running; pause the game first')
    print('counter:', ' | '.join(line for line in channel.ask('count').split('\n') if line.startswith('count')))
    hwnd = windowgrab.window_of(pid)[0]
    hers = user32.GetForegroundWindow()
    keys = Keys(hwnd)
    results = {}
    speech.output('the key test takes the game to the front for about ten seconds; please do not type')
    time.sleep(4)
    try:
        if not bring(hwnd):
            raise SystemExit('the game did not come to the front; nothing was sent')
        counted()
        time.sleep(1.0)
        results['idle in front, 1 s'] = counted()

        keys.send(VK_F1, False)
        time.sleep(0.05)
        keys.send(VK_F1, True)
        now = drawn_after(game, 'character_window')
        results['F1'] = counted()
        print('F1 drew:', sorted(now - baseline) or 'nothing', flush=True)
        if now - baseline and not back_to(game, baseline, VK_F1):
            raise SystemExit('after F1 the state did not come back')

        if not bring(hwnd):
            raise SystemExit('the game lost the front before shift+F1')
        counted()
        keys.combo([VK_LSHIFT], VK_F1)
        now = drawn_after(game, 'ledger_window')
        results['shift+F1'] = counted()
        print('shift+F1 drew:', sorted(now - baseline) or 'nothing', flush=True)
        if now - baseline and not back_to(game, baseline, VK_ESCAPE):
            raise SystemExit('after shift+F1 the state did not come back')
    finally:
        keys.release()
        if hers and user32.IsWindow(hers):
            bring(hers)
        speech.output('the key test is done, the foreground is yours again')
    for name, numbers in results.items():
        print('%-20s %s' % (name, ', '.join('%s %d' % pair for pair in numbers.items() if pair[1])
                                  or 'nothing counted'))
    print('clock standing:', paused(game))


if __name__ == '__main__':
    terminal.utf8()
    main(int(sys.argv[1]))
