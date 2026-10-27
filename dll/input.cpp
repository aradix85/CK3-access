// input.cpp - keys and clicks: the ones the reader takes before the game sees them, and the ones
// posted into the game. Runs inside the game process, under the same exception as channel.cpp.
// Shares nothing with the memory half but the reply and the reading of a command (channel.h).
#include <windows.h>
#include <string.h>

#include "channel.h"

// --- swallowing keys --------------------------------------------------------
static SRWLOCK g_lock = SRWLOCK_INIT;   // never taken twice by one thread
static int g_keys[256];
static int g_key_count = 0;
static unsigned g_keys_dropped = 0;      // keys that found the list full; waitkey says so
static WNDPROC g_old_proc = NULL;
static HWND g_window = NULL;
static bool g_swallow[256] = {false};   // keys the game must not see

static BOOL CALLBACK visit_window(HWND window, LPARAM)
{
    DWORD owner = 0;
    GetWindowThreadProcessId(window, &owner);
    if (owner == GetCurrentProcessId() && IsWindowVisible(window)) { g_window = window; return FALSE; }
    return TRUE;
}

static LRESULT CALLBACK our_proc(HWND window, UINT message, WPARAM w, LPARAM l)
{
    if (message == WM_KEYDOWN || message == WM_SYSKEYDOWN) {
        AcquireSRWLockExclusive(&g_lock);
        if (g_key_count < 256) g_keys[g_key_count++] = (int)w; else g_keys_dropped++;
        bool swallowed = (w < 256) && g_swallow[w];
        ReleaseSRWLockExclusive(&g_lock);
        if (swallowed) return 0;   // the game does not see this key
    }
    return CallWindowProcW(g_old_proc, window, message, w, l);
}

// The game's window, found once and kept. Posting from inside means the game need not be in the
// foreground. Coordinates are window points; on a fullscreen window those are screen points.
static bool ensure_window(void)
{
    if (!g_window) EnumWindows(visit_window, 0);
    if (!g_window) { emit("error: no window found\n"); return false; }
    return true;
}

void keys_enable(bool enable)
{
    if (enable && !g_old_proc) {
        // The window to hook is the one there now. Searched here and not through ensure_window,
        // so the code analysis sees the handle checked before it is used.
        g_window = NULL;
        EnumWindows(visit_window, 0);
        if (!g_window) { emit("error: no window found\n"); return; }
        g_old_proc = as_pointer<WNDPROC>(SetWindowLongPtrW(g_window, GWLP_WNDPROC, (LONG_PTR)our_proc));
        if (!g_old_proc) { emit("error: the window procedure was not replaced: %lu\n", GetLastError()); return; }
        emit("keys on\n");
    } else if (!enable && g_old_proc) {
        SetWindowLongPtrW(g_window, GWLP_WNDPROC, (LONG_PTR)g_old_proc);
        g_old_proc = NULL;
        emit("keys off\n");
    } else {
        emit("keys unchanged\n");
    }
}

void cmd_waitkey(DWORD timeout)
{
    ULONGLONG begin = GetTickCount64();
    for (;;) {
        AcquireSRWLockExclusive(&g_lock);
        int count = g_key_count;
        for (int i = 0; i < count; i++) emit("key\t%d\n", g_keys[i]);
        if (g_keys_dropped) emit("error: %u keys came in while the list of 256 was full\n", g_keys_dropped);
        g_key_count = 0;
        g_keys_dropped = 0;
        ReleaseSRWLockExclusive(&g_lock);
        if (count > 0 || GetTickCount64() - begin >= timeout) return;
        Sleep(15);
    }
}

// --- sending mouse and keys to the game -------------------------------------
// A message the window refuses is said, never answered as sent.
static void refused(void) { emit("error: the game window refused a message\n"); }

// mouse and rmouse: a left or a right click. A window message carries a point in 16 bits a side, so
// a bigger one is refused rather than wrapped round onto another place. Posted mouse messages do not
// move the game's hover point, so a move alone does nothing. The right click is there for what only
// a right click opens, such as the menu of interactions on a portrait.
void cmd_mouse(unsigned x, unsigned y, bool right)
{
    if (x > 0x7FFF || y > 0x7FFF) { emit("error: the point %u %u does not fit a window message\n", x, y); return; }
    if (!ensure_window()) return;
    const LPARAM spot = MAKELPARAM(x, y);
    if (!PostMessageW(g_window, WM_MOUSEMOVE, 0, spot) ||
        !PostMessageW(g_window, right ? WM_RBUTTONDOWN : WM_LBUTTONDOWN, right ? MK_RBUTTON : MK_LBUTTON, spot) ||
        !PostMessageW(g_window, right ? WM_RBUTTONUP : WM_LBUTTONUP, 0, spot)) { refused(); return; }
    emit("%s\t%u\t%u\n", right ? "rmouse" : "mouse", x, y);
}

// The game ignores a posted key whose lParam is zero, so lParam is built the way Windows builds it
// for a real keyboard: repeat count, scancode, extended bit, and the release bits.
// `system` sets the context bit an alt combination carries. Built unsigned, because these are bits.
static LPARAM key_lparam(unsigned code, bool key_up, bool system = false)
{
    UINT scancode = MapVirtualKeyW(code, MAPVK_VK_TO_VSC);
    ULONG_PTR l = 1U;                                  // repeat count
    l |= ULONG_PTR{scancode & 0xFFU} << 16U;
    switch (code) {
        case VK_LEFT: case VK_RIGHT: case VK_UP: case VK_DOWN:
        case VK_HOME: case VK_END: case VK_PRIOR: case VK_NEXT:
        case VK_INSERT: case VK_DELETE: case VK_NUMLOCK:
        case VK_RCONTROL: case VK_RMENU:
            l |= ULONG_PTR{1U} << 24U;                 // extended bit
            break;
        default:
            break;
    }
    if (system) l |= ULONG_PTR{1U} << 29U;             // context: alt is down
    if (key_up) l |= (ULONG_PTR{1U} << 30U) | (ULONG_PTR{1U} << 31U);   // previous state, transition
    return static_cast<LPARAM>(l);
}

// A posted key carries no modifier state; a combination with shift, ctrl or alt goes through
// `combo`, below, which holds the modifier for the game.
void cmd_sendkey(unsigned code)
{
    if (code >= 256) { emit("error: key code %u is not a virtual key\n", code); return; }
    if (!ensure_window()) return;
    if (!PostMessageW(g_window, WM_KEYDOWN, code, key_lparam(code, false)) ||
        !PostMessageW(g_window, WM_KEYUP, code, key_lparam(code, true))) { refused(); return; }
    emit("key sent\t%u\n", code);
}

// Entering text does not go through key codes but through WM_CHAR: that is the message an input
// field listens to. Needed in order to type a console command.
void cmd_sendchar(unsigned ch)
{
    if (!ensure_window()) return;
    if (!PostMessageW(g_window, WM_CHAR, ch, 1)) { refused(); return; }
    emit("char sent\t%u\n", ch);
}

// --- counting what the game asks Windows about the keyboard, and holding a modifier -------
// A measuring instrument first. The game's own import table is pointed, for the four keyboard
// functions ck3.exe imports from user32, at a wrapper that counts and then calls the real one; the
// first two also per virtual key, because which key is asked about tells a modifier check from
// anything else. A function the game finds through GetProcAddress is not seen.
// The wrappers change an answer only while `combo` holds a modifier: that key and its generic twin
// read as down. Measured 2 October 2026: during a shift+F1 from SendInput the game asked
// GetKeyState about left shift and about nothing else - SDL inside the exe checking a shift it
// believes is down, and letting go of one Windows does not hold. Outside a combination every
// answer is the real one.
enum : unsigned char { C_KEYSTATE, C_ASYNC, C_KEYBOARD, C_RAWDATA, C_TOTAL };
static const char* const g_count_names[C_TOTAL] = {
    "GetKeyState", "GetAsyncKeyState", "GetKeyboardState", "GetRawInputData"
};
static const char* g_count_how[C_TOTAL] = { "not imported", "not imported", "not imported", "not imported" };
static void* volatile g_count_real[C_TOTAL];
static volatile LONG g_counts[C_TOTAL];
static volatile LONG g_count_keys[2][256];       // C_KEYSTATE and C_ASYNC, per virtual key
static bool g_count_patched = false;
static volatile LONG g_held[256];                // keys `combo` holds down right now

static void count_key(int which, int key)
{
    InterlockedIncrement(&g_counts[which]);
    InterlockedIncrement(&g_count_keys[which][static_cast<unsigned>(key) & 0xFFU]);
}

static SHORT with_held(SHORT real, int key)
{
    // The high bit of a key state means held; it is set on the unsigned pattern, not on the number.
    return g_held[static_cast<unsigned>(key) & 0xFFU]
               ? static_cast<SHORT>(static_cast<USHORT>(real) | 0x8000U) : real;
}

static SHORT WINAPI counted_key_state(int key)
{
    count_key(C_KEYSTATE, key);
    return with_held(((SHORT (WINAPI*)(int))g_count_real[C_KEYSTATE])(key), key);
}

static SHORT WINAPI counted_async_key_state(int key)
{
    count_key(C_ASYNC, key);
    return with_held(((SHORT (WINAPI*)(int))g_count_real[C_ASYNC])(key), key);
}

static BOOL WINAPI counted_keyboard_state(PBYTE state)
{
    InterlockedIncrement(&g_counts[C_KEYBOARD]);
    BOOL done = ((BOOL (WINAPI*)(PBYTE))g_count_real[C_KEYBOARD])(state);
    if (done)
        for (int key = 0; key < 256; key++)
            if (g_held[key]) state[key] = static_cast<BYTE>(state[key] | 0x80U);
    return done;
}

static UINT WINAPI counted_raw_data(HRAWINPUT input, UINT command, LPVOID data, PUINT size, UINT header)
{
    InterlockedIncrement(&g_counts[C_RAWDATA]);
    return ((UINT (WINAPI*)(HRAWINPUT, UINT, LPVOID, PUINT, UINT))g_count_real[C_RAWDATA])(input, command, data, size, header);
}

// The real function is stored before the slot is turned, so a call that arrives in between still
// finds it.
static void patch_imports(void)
{
    static void* const ours[C_TOTAL] = {
        (void*)counted_key_state, (void*)counted_async_key_state,
        (void*)counted_keyboard_state, (void*)counted_raw_data
    };
    unsigned char* base = (unsigned char*)GetModuleHandleW(NULL);
    IMAGE_NT_HEADERS* nt = (IMAGE_NT_HEADERS*)(base + ((IMAGE_DOS_HEADER*)base)->e_lfanew);
    DWORD imports = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    if (!imports) return;
    for (IMAGE_IMPORT_DESCRIPTOR* d = (IMAGE_IMPORT_DESCRIPTOR*)(base + imports); d->Name; d++) {
        if (_stricmp((const char*)(base + d->Name), "user32.dll") != 0 || !d->OriginalFirstThunk) continue;
        IMAGE_THUNK_DATA* names = (IMAGE_THUNK_DATA*)(base + d->OriginalFirstThunk);
        IMAGE_THUNK_DATA* slots = (IMAGE_THUNK_DATA*)(base + d->FirstThunk);
        for (; names->u1.AddressOfData; names++, slots++) {
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) continue;
            const char* name = (const char*)((IMAGE_IMPORT_BY_NAME*)(base + names->u1.AddressOfData))->Name;
            for (int i = 0; i < C_TOTAL; i++) {
                if (strcmp(name, g_count_names[i]) != 0) continue;
                DWORD old = 0;
                if (!VirtualProtect(&slots->u1.Function, sizeof(slots->u1.Function), PAGE_READWRITE, &old)) {
                    g_count_how[i] = "import slot not writable";
                    continue;
                }
                g_count_real[i] = as_pointer<void*>(slots->u1.Function);
                MemoryBarrier();
                slots->u1.Function = (ULONGLONG)ours[i];
                VirtualProtect(&slots->u1.Function, sizeof(slots->u1.Function), old, &old);
                g_count_how[i] = "counted";
            }
        }
    }
}

// Once per process. The wrappers stay in place for the rest of the session: outside a combination
// they only count, and putting the table back while a game thread is inside a wrapper is the one
// way this could take the game down.
static void count_patch(void)
{
    AcquireSRWLockExclusive(&g_lock);
    if (!g_count_patched) patch_imports();
    g_count_patched = true;
    ReleaseSRWLockExclusive(&g_lock);
}

// count: the first time it hangs the counters in; every time it answers with what was counted
// since the previous count and starts again from zero. So an interval is two calls.
void cmd_count(void)
{
    count_patch();
    for (int i = 0; i < C_TOTAL; i++)
        emit("count\t%s\t%s\t%ld\n", g_count_names[i], g_count_how[i], InterlockedExchange(&g_counts[i], 0));
    for (int which = 0; which < 2; which++)
        for (int key = 0; key < 256; key++) {
            LONG n = InterlockedExchange(&g_count_keys[which][key], 0);
            if (n) emit("asked\t%s\t%02x\t%ld\n", g_count_names[which], key, n);
        }
}

// The modifiers `combo` can hold: left and right shift, ctrl and alt. A message carries the
// generic key and the scancode in lParam says which side, which is how SDL tells them apart.
static UINT generic_of(unsigned code)
{
    switch (code) {
        case VK_LSHIFT:   case VK_RSHIFT:   return VK_SHIFT;
        case VK_LCONTROL: case VK_RCONTROL: return VK_CONTROL;
        case VK_LMENU:    case VK_RMENU:    return VK_MENU;
        default:                            return 0;
    }
}

static void hold(unsigned code, LONG down)
{
    InterlockedExchange(&g_held[code], down);
    InterlockedExchange(&g_held[generic_of(code)], down);
}

// combo <pause ms> <modifier>... <key>: the modifiers down in order, the key down and up, the
// modifiers up in reverse, with the pause after every step so the game takes each in a frame of
// its own. Posted like sendkey, so the game need not be in the foreground; while a modifier is down
// here the keyboard wrappers above say so, which is what a posted shift lacked. With alt down and
// ctrl not, a key goes as a system key with the context bit, as a real keyboard sends it. Once the
// first modifier is down nothing returns early: every key is up again before the answer.
#define COMBO_MODIFIERS 3
#define COMBO_PAUSE_MOST 1000
void cmd_combo(const char* rest)
{
    unsigned long long asked = 0, code = 0;
    unsigned codes[COMBO_MODIFIERS + 1] = {0};
    int count = 0;
    const char* p = rest;
    if (!take(&p, 'u', &asked)) { emit("error: combo needs a pause in ms first\n"); return; }
    while (take(&p, 'u', &code)) {
        if (count == COMBO_MODIFIERS + 1) { emit("error: at most %d modifiers and one key\n", COMBO_MODIFIERS); return; }
        if (code >= 256) { emit("error: key code %llu is not a virtual key\n", code); return; }
        codes[count++] = static_cast<unsigned>(code);
    }
    if (!all_read(p)) { emit("error: not a key code: %.40s\n", p); return; }
    if (asked > COMBO_PAUSE_MOST) { emit("error: a pause of %llu ms; at most %d\n", asked, COMBO_PAUSE_MOST); return; }
    const DWORD pause = static_cast<DWORD>(asked);
    if (count < 2) { emit("error: combo needs at least one modifier and a key\n"); return; }
    unsigned key = codes[count - 1];
    if (generic_of(key)) { emit("error: the last code is the key, and %u is a modifier\n", key); return; }
    for (int i = 0; i < count - 1; i++) {
        if (!generic_of(codes[i])) { emit("error: %u is not left or right shift, ctrl or alt\n", codes[i]); return; }
        for (int j = 0; j < i; j++)
            if (generic_of(codes[j]) == generic_of(codes[i])) { emit("error: the same modifier twice\n"); return; }
    }
    if (!ensure_window()) return;
    count_patch();
    if (strcmp(g_count_how[C_KEYSTATE], "counted") != 0) {
        emit("error: GetKeyState is not hooked (%s), so the game would let go of a held shift\n", g_count_how[C_KEYSTATE]);
        return;
    }
    bool ctrl = false, alt = false, posted = true;
    for (int i = 0; i < count - 1; i++) {
        UINT generic = generic_of(codes[i]);
        hold(codes[i], 1);
        bool system = generic == VK_MENU && !ctrl;
        posted = PostMessageW(g_window, system ? WM_SYSKEYDOWN : WM_KEYDOWN, generic,
                              key_lparam(codes[i], false, system)) && posted;
        ctrl = ctrl || generic == VK_CONTROL;
        alt = alt || generic == VK_MENU;
        Sleep(pause);
    }
    bool system = alt && !ctrl;
    posted = PostMessageW(g_window, system ? WM_SYSKEYDOWN : WM_KEYDOWN, key, key_lparam(key, false, system)) && posted;
    Sleep(pause);
    posted = PostMessageW(g_window, system ? WM_SYSKEYUP : WM_KEYUP, key, key_lparam(key, true, system)) && posted;
    Sleep(pause);
    for (int i = count - 2; i >= 0; i--) {
        posted = PostMessageW(g_window, WM_KEYUP, generic_of(codes[i]), key_lparam(codes[i], true)) && posted;
        Sleep(pause);
        hold(codes[i], 0);
    }
    if (!posted) { refused(); return; }
    emit("combo sent");
    for (int i = 0; i < count; i++) emit("\t%u", codes[i]);
    emit("\n");
}

void cmd_swallow(const char* rest)
{
    bool wanted[256] = {false};
    const char* p = rest;
    int count = 0;
    unsigned long long code = 0;
    while (take(&p, 'u', &code)) {
        if (code >= 256) { emit("error: key code %llu is not a virtual key\n", code); return; }
        if (!wanted[code]) { wanted[code] = true; count++; }
    }
    if (!all_read(p)) { emit("error: not a key code: %.40s\n", p); return; }
    AcquireSRWLockExclusive(&g_lock);
    for (int i = 0; i < 256; i++) g_swallow[i] = wanted[i];
    ReleaseSRWLockExclusive(&g_lock);
    emit("swallow\t%d\n", count);
}
