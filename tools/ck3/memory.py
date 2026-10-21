"""What the executable says about the game's classes, and the Windows calls that read its memory.

The class tree comes from the exe's own type information (MSVC RTTI), read off disk, so that a patch
which renames or adds a class is seen at the next start; the field offsets are derived in `derive`.
"""
import ctypes
import pathlib
import re
import struct
from ctypes import wintypes

from tools import paths

ROOT_CLASS = '.?AVCPdxGuiWidget@@'
# One section header: name, virtual address, virtual size, file offset.
Section = tuple[str, int, int, int]

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = wintypes.BOOL


class Region(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', wintypes.DWORD), ('vul1', wintypes.DWORD),
                ('RegionSize', ctypes.c_size_t), ('State', wintypes.DWORD),
                ('Protect', wintypes.DWORD), ('Type', wintypes.DWORD),
                ('vul2', wintypes.DWORD)]


kernel32.VirtualQueryEx.argtypes = [wintypes.HANDLE, wintypes.LPCVOID,
                                ctypes.POINTER(Region), ctypes.c_size_t]
kernel32.VirtualQueryEx.restype = ctypes.c_size_t


def _sections(data: bytes) -> tuple[int, list[Section]]:
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    count = struct.unpack_from('<H', data, pe + 6)[0]
    optional = struct.unpack_from('<H', data, pe + 20)[0]
    base = struct.unpack_from('<Q', data, pe + 24 + 24)[0]
    items: list[Section] = []
    for i in range(count):
        header = pe + 24 + optional + i * 40
        items.append((data[header:header + 8].rstrip(b'\x00').decode(),
                      struct.unpack_from('<I', data, header + 12)[0],
                      struct.unpack_from('<I', data, header + 16)[0],
                      struct.unpack_from('<I', data, header + 20)[0]))
    return base, items


def _offset(sections: list[Section], rva: int) -> int:
    """Where an RVA the exe's own type information points at sits in the file. No section holding it
    is a misread, not an answer."""
    for _, va, size, raw in sections:
        if va <= rva < va + size:
            return raw + (rva - va)
    raise ValueError(f'RVA 0x{rva:X} from the type information lies in no section of ck3.exe')


CLASSES: dict[int, tuple[str, bool]] | None = None


def _classes() -> dict[int, tuple[str, bool]]:
    """Every vtable RVA in the exe's `.rdata`: the RTTI name of its class, and whether that class
    descends from CPdxGuiWidget.

    **Read once and kept.** The executable does not change while the game runs, and this walks
    the whole `.rdata` section: measured 20 September 2026 it cost 7,2 of the 11,3 seconds a live
    read of the character window took, because `class_map` calls it and the reader calls that on
    every window it opens. Nothing here depends on the running game, so a second answer could
    only ever be the same one.
    """
    global CLASSES
    if CLASSES is not None:
        return CLASSES
    data = pathlib.Path(paths.require('EXE')).read_bytes()
    base, sections = _sections(data)
    rdata = next(s for s in sections if s[0] == '.rdata')

    def word(at: int) -> int:
        value: int = struct.unpack_from('<I', data, at)[0]
        return value

    def type_name(td_rva: int) -> str:
        o = _offset(sections, td_rva) + 16
        return data[o:data.index(b'\x00', o)].decode('latin1')

    # A complete object locator: signature 1, the type descriptor at +12, the class hierarchy at
    # +16, and its own RVA at +20. The hierarchy lists every base, the class itself first.
    locators: dict[int, tuple[str, bool]] = {}
    for p in range(0, rdata[2] - 24, 4):
        col = rdata[1] + p
        if word(rdata[3] + p) != 1 or word(rdata[3] + p + 20) != col:
            continue
        hierarchy = _offset(sections, word(rdata[3] + p + 16))
        array = _offset(sections, word(hierarchy + 12))
        bases = {type_name(word(_offset(sections, word(array + i * 4)))) for i in range(word(hierarchy + 8))}
        locators[col] = (type_name(word(rdata[3] + p + 12)), ROOT_CLASS in bases)

    # A vtable is the eight bytes after a pointer to its locator.
    CLASSES = {}
    for p in range(0, rdata[2] - 8, 8):
        value = struct.unpack_from('<Q', data, rdata[3] + p)[0]
        if value > base and (value - base) in locators:
            CLASSES[rdata[1] + p + 8] = locators[value - base]
    return CLASSES


def widget_vtables() -> dict[int, str]:
    """Vtable RVAs of every class descending from CPdxGuiWidget, taken from the exe."""
    return {rva: name.replace('.?AVCPdxGui', '').replace('@@', '')
            for rva, (name, widget) in _classes().items() if widget}


def vtables_by_name(part: str) -> dict[int, str]:
    """Vtable RVAs of classes whose RTTI name contains `part`, case sensitive.

    The counterpart of `widget_vtables`, which filters on base class. A name that matches nothing
    stops here, because further along an empty filter looks like "there is nothing there" rather
    than "my filter is wrong": the classes are called `Textbox` (not `TextBox`), `Window`,
    `PushButton`, `Icon`, `HBoxLayout`, `VBoxLayout`. Measured 30 July 2026: `TextBox` gives zero,
    `Textbox` gives four.
    """
    found = {rva: name for rva, (name, _) in _classes().items() if part in name}
    if not found:
        raise SystemExit(f'no class name in ck3.exe contains {part!r}; the names are case sensitive')
    return found


def type_name_count() -> int:
    """How many RTTI type names the exe contains.

    This tells two very different failures apart. Zero names means a build without type
    information, and then the whole approach falls away - there is nothing left to derive. Many
    names but no widget classes means the base class is called something else, and that is one
    constant to change. Without this distinction the two look alike.
    """
    data = pathlib.Path(paths.require('EXE')).read_bytes()
    return len(set(re.findall(rb'\.\?A[VU][A-Za-z0-9_@?$]{2,120}@@', data)))
