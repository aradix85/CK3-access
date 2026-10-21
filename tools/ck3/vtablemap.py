"""Hands the vtables of the widget classes to the channel, where the game has loaded them.

That is all this file does: `memory` reads the classes from the exe, `derive` walks the tree. The
list is taken from the exe at every start and never kept on disk, which takes the last
version-bound assumption out of the chain: there is no file with a build number in its name that
can quietly go stale.
"""
import ctypes
import sys

from tools.ck3 import channel, memory

_psapi = ctypes.WinDLL('psapi', use_last_error=True)


def module_base(number: int) -> int:
    """Where ck3.exe is loaded. The vtable addresses from the exe are relative to it."""
    handle = memory.kernel32.OpenProcess(0x0410, False, number)
    if not handle:
        raise OSError(f'cannot open the game process: {int(number)}')
    run = (ctypes.c_void_p * 64)()
    needed = ctypes.c_ulong()
    listed = _psapi.EnumProcessModules(handle, ctypes.byref(run), ctypes.sizeof(run),
                                       ctypes.byref(needed))
    error = ctypes.get_last_error()
    memory.kernel32.CloseHandle(handle)
    # The first module listed is the exe itself.
    base = run[0]
    if not listed or base is None:
        raise ctypes.WinError(error, 'EnumProcessModules')
    return base


def vtables() -> dict[int, str]:
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
            f'{int(names)} type names in the exe, but not a single class descends from {memory.ROOT_CLASS}. '
            'The base class is probably named differently in this build; change ROOT_CLASS in '
            'memory.py.')
    return found


def configure(number: int) -> tuple[int, dict[int, str]]:
    base = module_base(number)
    found = vtables()
    channel.ask('vtables ' + ' '.join('%x' % (base + rva) for rva in found))
    return base, found


if __name__ == '__main__':
    base, found = configure(int(sys.argv[1]))
    print(f'module base 0x{base:x}, {len(found)} vtables of {len(set(found.values()))} classes handed to the channel')
