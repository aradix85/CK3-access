"""Reads the interface of a running CK3 out of process memory.

Finds the field offsets again at every start instead of writing them down, so that a patch which
shifts the layout gives a clear failure instead of nonsense.
"""
import ctypes, struct, re, os, sys
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

INSTALL = paths.GAME
EXE = paths.EXE
SETTINGS = paths.SETTINGS
ROOT_CLASS = b'.?AVCPdxGuiWidget@@'

_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_k32.OpenProcess.restype = wintypes.HANDLE
_k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
_k32.ReadProcessMemory.restype = wintypes.BOOL


class Region(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', wintypes.DWORD), ('vul1', wintypes.DWORD),
                ('RegionSize', ctypes.c_size_t), ('State', wintypes.DWORD),
                ('Protect', wintypes.DWORD), ('Type', wintypes.DWORD),
                ('vul2', wintypes.DWORD)]


_k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, wintypes.LPCVOID,
                                ctypes.POINTER(Region), ctypes.c_size_t]
_k32.VirtualQueryEx.restype = ctypes.c_size_t


def _sections(data):
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    count = struct.unpack_from('<H', data, pe + 6)[0]
    optional = struct.unpack_from('<H', data, pe + 20)[0]
    base = struct.unpack_from('<Q', data, pe + 24 + 24)[0]
    items = []
    for i in range(count):
        header = pe + 24 + optional + i * 40
        items.append((data[header:header + 8].rstrip(b'\x00').decode(),
                      struct.unpack_from('<I', data, header + 12)[0],
                      struct.unpack_from('<I', data, header + 16)[0],
                      struct.unpack_from('<I', data, header + 20)[0]))
    return base, items


def widget_vtables():
    """Vtable RVAs of every class descending from CPdxGuiWidget, taken from the exe."""
    data = open(EXE, 'rb').read()
    base, sections = _sections(data)
    rdata = [s for s in sections if s[0] == '.rdata'][0]

    def to_offset(rva):
        for _, va, size, raw in sections:
            if va <= rva < va + size:
                return raw + (rva - va)
        return None

    def type_name(td_rva):
        o = to_offset(td_rva) + 16
        return data[o:data.index(b'\x00', o)]

    locators = {}
    for p in range(0, rdata[2] - 24, 4):
        if struct.unpack_from('<I', data, rdata[3] + p)[0] != 1:
            continue
        col = rdata[1] + p
        if struct.unpack_from('<I', data, rdata[3] + p + 20)[0] != col:
            continue
        here = to_offset(struct.unpack_from('<I', data, rdata[3] + p + 16)[0])
        array = to_offset(struct.unpack_from('<I', data, here + 12)[0])
        for i in range(struct.unpack_from('<I', data, here + 8)[0]):
            descriptor = to_offset(struct.unpack_from('<I', data, array + i * 4)[0])
            if type_name(struct.unpack_from('<I', data, descriptor)[0]) == ROOT_CLASS:
                own = struct.unpack_from('<I', data, rdata[3] + p + 12)[0]
                locators[col] = type_name(own).decode()
                break

    vtables = {}
    for p in range(0, rdata[2] - 8, 8):
        value = struct.unpack_from('<Q', data, rdata[3] + p)[0]
        if value > base and (value - base) in locators:
            name = locators[value - base]
            vtables[rdata[1] + p + 8] = name.replace('.?AVCPdxGui', '').replace('@@', '')
    return vtables


def vtables_by_name(part):
    """Vtable RVAs of classes whose RTTI name contains `part` - NOTE: case sensitive.

    The counterpart of `widget_vtables`, which filters on base class. This one filters on name,
    which is what you need once you know a class by name - from an object dump, for instance.

    Wrong casing gives an empty list, and further along an empty filter looks like "there is
    nothing there" rather than "my filter is wrong". The classes are called `Textbox` (not
    `TextBox`), `Window`, `PushButton`, `Icon`, `HBoxLayout`, `VBoxLayout`. So check a filter on
    its count before using it. Measured 30 July 2026: `TextBox` gives zero, `Textbox` gives four.
    """
    data = open(EXE, 'rb').read()
    base, sections = _sections(data)
    rdata = [s for s in sections if s[0] == '.rdata'][0]

    def to_offset(rva):
        for _, va, size, raw in sections:
            if va <= rva < va + size:
                return raw + (rva - va)
        return None

    locators = {}
    for p in range(0, rdata[2] - 24, 4):
        if struct.unpack_from('<I', data, rdata[3] + p)[0] != 1:
            continue
        col = rdata[1] + p
        if struct.unpack_from('<I', data, rdata[3] + p + 20)[0] != col:
            continue
        descriptor = to_offset(struct.unpack_from('<I', data, rdata[3] + p + 12)[0])
        if descriptor is None:
            continue
        start = descriptor + 16
        name = data[start:data.index(b'\x00', start)].decode('latin1')
        if part in name:
            locators[col] = name

    found = {}
    for p in range(0, rdata[2] - 8, 8):
        value = struct.unpack_from('<Q', data, rdata[3] + p)[0]
        if value > base and (value - base) in locators:
            found[rdata[1] + p + 8] = locators[value - base]
    return found


def screen_size():
    text = open(SETTINGS, encoding='utf-8', errors='ignore').read()
    pos = text.index('fullscreen_resolution')
    width, height = re.search(r'value="(\d+)x(\d+)"', text[pos:pos + 200]).groups()
    return float(width), float(height)


def type_name_count():
    """How many RTTI type names the exe contains.

    This tells two very different failures apart. Zero names means a build without type
    information, and then the whole approach falls away - there is nothing left to derive. Many
    names but no widget classes means the base class is called something else, and that is one
    constant to change. Without this distinction the two look alike.
    """
    data = open(EXE, 'rb').read()
    return len(set(re.findall(rb'\.\?A[VU][A-Za-z0-9_@?$]{2,120}@@', data)))
