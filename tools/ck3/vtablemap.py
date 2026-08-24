"""Derives the vtables of the widget classes and hands them to the channel.

That is all this file does. Scanning, walking the tree and deriving the field offsets used to live
here too, but that became `derive.py`; two files both claiming to know how to walk the tree is an
invitation to pick the wrong answer later.

The list is derived from the exe at every start and never read from disk. That costs 1.5 seconds
(measured 27 July 2026) and takes the last version-bound assumption out of the chain: there is no
longer a file with a build number in its name that can quietly go stale.
"""
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory
import channel

_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_psapi = ctypes.WinDLL('psapi', use_last_error=True)


def module_base(number):
    """Where ck3.exe is loaded. The vtable addresses from the exe are relative to it."""
    handle = _k32.OpenProcess(0x0410, False, number)
    if not handle:
        raise OSError('cannot open the game process: %d' % number)
    run = (ctypes.c_void_p * 64)()
    needed = ctypes.c_ulong()
    _psapi.EnumProcessModules(handle, ctypes.byref(run), ctypes.sizeof(run),
                              ctypes.byref(needed))
    _k32.CloseHandle(handle)
    return run[0]


def vtables():
    """Vtable RVAs of the widget classes, from the exe as it is on disk right now.

    If this fails, stop hard and keep the distinction that matters: no type information is the end
    of this approach, a different base class name is one constant.
    """
    found = memory.widget_vtables()
    if not found:
        names = memory.type_name_count()
        if names == 0:
            raise SystemExit(
                'this build ships no RTTI: zero type names in the exe. The whole approach '
                'leans on that, so this is where it stops.')
        raise SystemExit(
            '%d type names in the exe, but not a single class descends from %s. '
            'The base class is probably named differently in this build; change ROOT_CLASS in '
            'memory.py.' % (names, memory.ROOT_CLASS.decode()))
    return found


def configure(number):
    base = module_base(number)
    found = vtables()
    channel.ask('vtables ' + ' '.join('%x' % (base + rva) for rva in found))
    return base, found


if __name__ == '__main__':
    base, found = configure(int(sys.argv[1]))
    print('modulebasis 0x%x, %d vtables over %d klassen doorgegeven'
          % (base, len(found), len(set(found.values()))))
