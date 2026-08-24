"""Grabs an image of the game window without it having to be in the foreground.

A minimised game draws nothing. That also happens in windowed mode once the window has lost the
foreground for long enough, so it is not a property of fullscreen. `window_of` therefore restores
a minimised window itself with SW_SHOWNOACTIVATE, which makes the window draw again without
taking the foreground away from whatever the user is reading.

This is a yardstick, not a product. What the mod reads aloud comes from the widget tree.
"""
import ctypes
import ctypes.wintypes as w

from PIL import Image

PW_RENDERFULLCONTENT = 2
SW_SHOWNOACTIVATE = 4          # restore without taking the foreground; 9 would take it

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32
_user32.SetProcessDPIAware()


class _Header(ctypes.Structure):
    _fields_ = [('biSize', w.DWORD), ('biWidth', ctypes.c_long), ('biHeight', ctypes.c_long),
                ('biPlanes', w.WORD), ('biBitCount', w.WORD), ('biCompression', w.DWORD),
                ('biSizeImage', w.DWORD), ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', w.DWORD),
                ('biClrImportant', w.DWORD)]


def window_of(pid):
    """The largest visible window of that process, with its outer size."""
    found = []

    @ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def collect(hwnd, lparam):
        owner = w.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and _user32.IsWindowVisible(hwnd):
            r = w.RECT()
            _user32.GetWindowRect(hwnd, ctypes.byref(r))
            found.append((hwnd, r.right - r.left, r.bottom - r.top))
        return True

    _user32.EnumWindows(collect, 0)
    hwnd, width, height = max(found, key=lambda v: v[1] * v[2])
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        if _user32.IsIconic(hwnd):
            raise SystemExit('the game window stayed minimised after restoring it')
        r = w.RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(r))
        width, height = r.right - r.left, r.bottom - r.top
    return hwnd, width, height


def client_size(hwnd):
    """The drawing area inside the window, without title bar and border."""
    r = w.RECT()
    _user32.GetClientRect(hwnd, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


def borders(hwnd):
    """Where the drawing area starts inside the window: title bar and border.

    `PrintWindow` draws the whole window, title bar included. Treating that as the drawing area
    gives positions that sit one title bar too high, and clicks then land beside their target.
    """
    point = w.POINT(0, 0)
    _user32.ClientToScreen(hwnd, ctypes.byref(point))
    window = w.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(window))
    return point.x - window.left, point.y - window.top


def grab(pid):
    """Returns (image, width, height) of the game window's drawing area."""
    hwnd, outer_width, outer_height = window_of(pid)
    width, height = client_size(hwnd)
    dx, dy = borders(hwnd)

    hdc_screen = _user32.GetDC(0)
    hdc_memory = _gdi32.CreateCompatibleDC(hdc_screen)
    bitmap = _gdi32.CreateCompatibleBitmap(hdc_screen, outer_width, outer_height)
    _gdi32.SelectObject(hdc_memory, bitmap)
    _user32.PrintWindow(hwnd, hdc_memory, PW_RENDERFULLCONTENT)

    header = _Header()
    header.biSize = ctypes.sizeof(_Header)
    header.biWidth = outer_width
    header.biHeight = -outer_height
    header.biPlanes = 1
    header.biBitCount = 32
    buffer = ctypes.create_string_buffer(outer_width * outer_height * 4)
    _gdi32.GetDIBits(hdc_memory, bitmap, 0, outer_height, buffer, ctypes.byref(header), 0)

    _gdi32.DeleteObject(bitmap)
    _gdi32.DeleteDC(hdc_memory)
    _user32.ReleaseDC(0, hdc_screen)

    whole = Image.frombuffer('RGB', (outer_width, outer_height), buffer, 'raw', 'BGRX', 0, 1)
    return whole.crop((dx, dy, dx + width, dy + height)), width, height


if __name__ == '__main__':
    import sys
    screenshot, b, h = grab(int(sys.argv[1]))
    screenshot.save(sys.argv[2])
    print('capture %dx%d written to %s' % (b, h, sys.argv[2]))
