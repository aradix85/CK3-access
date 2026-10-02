"""Starts a program suspended and loads our DLL into it before it runs its first line of code.

Five steps: start suspended, reserve memory inside that process, write the DLL path into it, have
the process call LoadLibraryW itself, and only then let it run.

This runs beside the game, not inside it, so everything breaks hard here: any Windows call that
returns zero is a fault that must be visible.
"""
import ctypes
import ctypes.wintypes as wt

CREATE_SUSPENDED = 0x00000004
STARTF_USESHOWWINDOW = 0x00000001
SW_SHOWNOACTIVATE = 4
MEM_COMMIT_RESERVE = 0x00003000
MEM_RELEASE = 0x00008000
PAGE_READWRITE = 0x04
INFINITE = 0xFFFFFFFF

k32 = ctypes.WinDLL('kernel32', use_last_error=True)


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('lpReserved', wt.LPWSTR), ('lpDesktop', wt.LPWSTR),
                ('lpTitle', wt.LPWSTR), ('dwX', wt.DWORD), ('dwY', wt.DWORD),
                ('dwXSize', wt.DWORD), ('dwYSize', wt.DWORD), ('dwXCountChars', wt.DWORD),
                ('dwYCountChars', wt.DWORD), ('dwFillAttribute', wt.DWORD), ('dwFlags', wt.DWORD),
                ('wShowWindow', wt.WORD), ('cbReserved2', wt.WORD),
                ('lpReserved2', ctypes.POINTER(ctypes.c_byte)), ('hStdInput', wt.HANDLE),
                ('hStdOutput', wt.HANDLE), ('hStdError', wt.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [('hProcess', wt.HANDLE), ('hThread', wt.HANDLE),
                ('dwProcessId', wt.DWORD), ('dwThreadId', wt.DWORD)]

# Without these declarations ctypes truncates 64-bit addresses to 32 bits and everything points nowhere.
k32.VirtualAllocEx.restype = ctypes.c_void_p
k32.VirtualAllocEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD]
k32.VirtualFreeEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD]
k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.GetModuleHandleW.restype = wt.HMODULE
k32.GetProcAddress.restype = ctypes.c_void_p
k32.GetProcAddress.argtypes = [wt.HMODULE, wt.LPCSTR]
k32.CreateRemoteThread.restype = wt.HANDLE
k32.CreateRemoteThread.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                                   ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD)]
k32.GetExitCodeThread.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]


def _require(result, what):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error(), what)
    return result


def start_with_dll(exe_path, dll_path, arguments=''):
    """Starts exe_path suspended, loads dll_path into it, resumes the process. Returns the pid.

    **The game is asked to show its window without taking the foreground**, because the player
    reads along in another window. Measured 2 October 2026: started without this, the game took the
    foreground by itself twenty seconds in, while no script of ours touched its window. Windows uses
    `wShowWindow` instead of what the program asks for on its first ShowWindow call, and the game
    honours it: with this, the player's window stayed in front through a start, a bookmark loading
    and a new game being set up, while the game's window stood visible and not minimised.
    """
    startup = STARTUPINFOW()
    startup.cb = ctypes.sizeof(startup)
    startup.dwFlags = STARTF_USESHOWWINDOW
    startup.wShowWindow = SW_SHOWNOACTIVATE
    pid = PROCESS_INFORMATION()
    command = ctypes.create_unicode_buffer('"%s" %s' % (exe_path, arguments))

    _require(k32.CreateProcessW(exe_path, command, None, None, False, CREATE_SUSPENDED,
                            None, None, ctypes.byref(startup), ctypes.byref(pid)),
         'CreateProcessW')

    pad_bytes = (dll_path + '\0').encode('utf-16-le')
    address = _require(k32.VirtualAllocEx(pid.hProcess, None, len(pad_bytes),
                                    MEM_COMMIT_RESERVE, PAGE_READWRITE), 'VirtualAllocEx')
    written = ctypes.c_size_t()
    _require(k32.WriteProcessMemory(pid.hProcess, address, pad_bytes, len(pad_bytes),
                                ctypes.byref(written)), 'WriteProcessMemory')

    load_function = _require(k32.GetProcAddress(k32.GetModuleHandleW('kernel32.dll'), b'LoadLibraryW'),
                       'GetProcAddress LoadLibraryW')
    thread = _require(k32.CreateRemoteThread(pid.hProcess, None, 0, load_function, address, 0, None),
                 'CreateRemoteThread')

    k32.WaitForSingleObject(thread, INFINITE)
    module = wt.DWORD()
    _require(k32.GetExitCodeThread(thread, ctypes.byref(module)), 'GetExitCodeThread')
    if module.value == 0:
        raise OSError('LoadLibraryW returned zero; the DLL was not loaded')

    k32.VirtualFreeEx(pid.hProcess, address, 0, MEM_RELEASE)
    k32.CloseHandle(thread)
    _require(k32.ResumeThread(pid.hThread) != -1, 'ResumeThread')
    k32.CloseHandle(pid.hThread)
    k32.CloseHandle(pid.hProcess)
    return pid.dwProcessId


if __name__ == '__main__':
    import sys
    print(start_with_dll(sys.argv[1], sys.argv[2], ' '.join(sys.argv[3:])))
