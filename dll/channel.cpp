// channel.cpp - the window to the inside.
//
// Runs inside the game process. Everything here falls under the exception: a fault takes the game
// down with it, so every read is checked for readability first. This is not defensive programming
// out of habit but the one place where it belongs.
//
// The DLL knows nothing about CK3. Python derives the field offsets and the widget vtables and
// passes them in; all that lives here is the machinery to walk memory with them.
#include <windows.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>

static const wchar_t* PIPE_NAME = L"\\\\.\\pipe\\ck3_access";

// Set by Python with `set`. There are no defaults: a walk on offsets nobody passed in is refused.
static SIZE_T f_parent, f_position, f_size, f_name, f_text, f_children, f_count;
static bool g_fields_set = false;

static unsigned long long g_vtables[256];   // sorted, for binary search
static int g_vtable_count = 0;

// Page protections worth reading. Windows defines them as plain ints; these are the bit patterns.
static const DWORD WRITABLE = DWORD{PAGE_READWRITE} | DWORD{PAGE_WRITECOPY};
static const DWORD READABLE = WRITABLE | DWORD{PAGE_READONLY} | DWORD{PAGE_EXECUTE_READ};

// --- reply buffer -----------------------------------------------------------
// One buffer per thread. That way two connections cannot overwrite each other, and a command
// that waits a long time (waitkey) need not hold a lock that freezes every other conversation.
// A reply that does not fit in memory becomes an error, never a crash inside the game.
static __declspec(thread) char* g_buf = NULL;
static __declspec(thread) size_t g_len = 0;
static __declspec(thread) size_t g_cap = 0;
static __declspec(thread) bool g_lost = false;

static void buf_clear(void) { g_len = 0; g_lost = false; }

static void buf_add(const char* text, size_t n)
{
    if (g_lost) return;
    if (g_len + n + 1 > g_cap) {
        size_t fresh = (g_cap ? g_cap : 65536);
        while (fresh < g_len + n + 1) fresh *= 2;
        char* bigger = (char*)realloc(g_buf, fresh);
        if (!bigger) { g_lost = true; return; }
        g_buf = bigger;
        g_cap = fresh;
    }
    memcpy(g_buf + g_len, text, n);
    g_len += n;
    g_buf[g_len] = 0;
}

static void emit(const char* format, ...)
{
    char line[12288];   // the longest line is a widget: a name of 512 and a text of 8192
    va_list list_start;
    va_start(list_start, format);
    int n = vsnprintf(line, sizeof(line), format, list_start);
    va_end(list_start);
    // vsnprintf returns how much was needed. If that is more than the buffer, it was silently
    // truncated, and that must never happen here: better a visible error than half an answer.
    if (n >= (int)sizeof(line)) {
        buf_add("error: line too long\n", 21);
        return;
    }
    if (n > 0) buf_add(line, (size_t)n);
}

// Bytes as hex, straight into the buffer. Going through vsnprintf per byte costs noticeable
// time at thousands of records, and that command exists precisely to read thousands of them.
static void buf_hex(const unsigned char* p, size_t count)
{
    static const char digit[] = "0123456789abcdef";
    char part[512];
    size_t out = 0;
    for (size_t i = 0; i < count; i++) {
        part[out++] = digit[p[i] >> 4U];
        part[out++] = digit[p[i] & 15U];
        if (out >= sizeof(part) - 2) { buf_add(part, out); out = 0; }
    }
    if (out) buf_add(part, out);
}

// Did a parse read the whole command? `consumed` is where it stopped, from the trailing %n, which
// sscanf always fills once every conversion before it matched. A command with text left over is
// refused, never shortened: an argument that is dropped looks exactly like one that arrived.
static bool all_read(const char* command, int consumed)
{
    const char* p = command + consumed;
    while (*p == ' ' || *p == '\t') p++;
    return *p == 0;
}

// --- reading memory safely --------------------------------------------------
// The game frees memory while we read it, which raises an access violation. That, and nothing
// else, is caught: any other exception is a real fault and must not be hidden.
static int access_violation(DWORD code)
{
    return code == EXCEPTION_ACCESS_VIOLATION ? EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH;
}

static bool readable(const void* address, SIZE_T count)
{
    MEMORY_BASIC_INFORMATION info;
    if (!VirtualQuery(address, &info, sizeof(info))) return false;
    if (info.State != MEM_COMMIT) return false;
    if (info.Protect & PAGE_GUARD) return false;
    const DWORD allowed = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
                      PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
    if (!(info.Protect & allowed)) return false;
    const char* end_of = (const char*)info.BaseAddress + info.RegionSize;
    return (const char*)address + count <= end_of;
}

static unsigned long long read64(const void* address)
{
    if (!readable(address, 8)) return 0;
    return *(const unsigned long long*)address;
}

static float read_float(const void* address)
{
    if (!readable(address, 4)) return 0.0f;
    return *(const float*)address;
}

// MSVC string: 16 bytes of buffer or pointer, then length, then capacity.
// If the capacity is 15, the text sits inside the object itself.
// Returns the real length, even when less of it fits in `out`.
static size_t read_cstring(char* out, size_t space, const unsigned char* object_address, SIZE_T field)
{
    out[0] = 0;
    const unsigned char* header = object_address + field;
    if (!readable(header, 32)) return 0;

    unsigned long long length = *(const unsigned long long*)(header + 16);
    unsigned long long capacity = *(const unsigned long long*)(header + 24);
    if (length == 0 || length > 1000000) return 0;

    const char* source = (capacity == 15) ? (const char*)header
                                          : (const char*)(*(const char* const*)header);
    if (!readable(source, (SIZE_T)length)) return 0;

    size_t n = (size_t)length;
    // Truncating is allowed, hiding it is not: the caller gets the real length back and can see
    // that there was more. Silently truncated text leads to "that is not there" while it is,
    // and that is the most expensive mistake this tool can make.
    if (n > space - 1) n = space - 1;
    for (size_t i = 0; i < n; i++) {
        char ch = source[i];
        out[i] = (ch == '\t' || ch == '\r' || ch == '\n') ? ' ' : ch;
    }
    out[n] = 0;
    return (size_t)length;
}

static bool is_widget(unsigned long long vtable)
{
    int low = 0, high = g_vtable_count - 1;
    while (low <= high) {
        int middle = (low + high) / 2;
        if (g_vtables[middle] == vtable) return true;
        if (g_vtables[middle] < vtable) low = middle + 1; else high = middle - 1;
    }
    return false;
}

// --- the commands -----------------------------------------------------------

// scan: every address that holds a widget vtable, with that vtable, and nothing else - it runs
// before the field offsets are known, because the derivation starts here. Every eight bytes up to
// the end of a region are a candidate. Without bounds it walks all eleven gigabytes of the game.
static void cmd_scan(unsigned long long from_address, unsigned long long to_address)
{
    if (g_vtable_count == 0) { emit("error: no vtables set\n"); return; }

    SYSTEM_INFO base;
    GetSystemInfo(&base);
    const unsigned char* pointer = from_address ? (const unsigned char*)from_address
                                      : (const unsigned char*)base.lpMinimumApplicationAddress;
    const unsigned char* end_at = to_address ? (const unsigned char*)to_address
                                     : (const unsigned char*)base.lpMaximumApplicationAddress;
    int found = 0;
    int skipped = 0;

    while (pointer < end_at) {
        MEMORY_BASIC_INFORMATION info;
        if (!VirtualQuery(pointer, &info, sizeof(info))) break;
        const unsigned char* next_item = (const unsigned char*)info.BaseAddress + info.RegionSize;

        bool usable = info.State == MEM_COMMIT && info.Type == MEM_PRIVATE &&
                         !(info.Protect & PAGE_GUARD) &&
                         (info.Protect & WRITABLE);
        if (usable) {
            // The game frees memory while we are reading. A violation here may abort the
            // region, but must never take the game or the channel with it; it is counted.
            __try {
                for (const unsigned char* p = (const unsigned char*)info.BaseAddress; p + 8 <= next_item; p += 8) {
                    unsigned long long vtable = *(const unsigned long long*)p;
                    if (!is_widget(vtable)) continue;
                    emit("w\t%llx\t%llx\n", (unsigned long long)p, vtable);
                    found++;
                }
            } __except (access_violation(GetExceptionCode())) {
                skipped++;
            }
        }
        pointer = next_item;
    }
    emit("done\t%d\tskipped\t%d\n", found, skipped);
}

// tree: from a widget, walk the children, and their children, and so on - following pointers,
// searching nothing. Whatever the walk loses it says on one kind of line, `missing <address> <why>`,
// and derive.widgets speaks every one of them.
static void emit_widget(const unsigned char* p, char* name, char* text, size_t space_name, size_t space_text)
{
    name[0] = 0; text[0] = 0;
    size_t name_length = read_cstring(name, space_name, p, f_name);
    size_t text_length = read_cstring(text, space_text, p, f_text);
    emit("w\t%llx\t%llx\t%.1f\t%.1f\t%.1f\t%.1f\t%llx\t%s\t%s\n",
            (unsigned long long)p, *(const unsigned long long*)p,
            read_float(p + f_position), read_float(p + f_position + 4),
            read_float(p + f_size), read_float(p + f_size + 4),
            read64(p + f_parent), name, text);
    if (name_length >= space_name)
        emit("missing\t%llx\tname of %zu characters cut short\n", (unsigned long long)p, name_length);
    if (text_length >= space_text)
        emit("missing\t%llx\ttext of %zu characters cut short\n", (unsigned long long)p, text_length);
}

static void cmd_tree(unsigned long long root, unsigned limit)
{
    if (!g_fields_set || g_vtable_count == 0) { emit("error: set and vtables come first\n"); return; }
    // The queue grows; a limit applies only when the caller asks for one, and is reported.
    unsigned space = 20000;
    unsigned long long* work = (unsigned long long*)malloc(sizeof(unsigned long long) * space);
    if (!work) { emit("error: out of memory\n"); return; }

    unsigned work_count = 0, done = 0, clipped = 0, foreign = 0;
    work[work_count++] = root;
    char name[512], text[8192];

    __try {
        while (done < work_count) {
            const unsigned char* p = (const unsigned char*)work[done++];
            // Only the vtable has to be readable: every field below is checked on its own, and an
            // object may end right before an uncommitted page.
            if (!readable(p, 8)) { emit("missing\t%llx\tunreadable\n", (unsigned long long)p); continue; }
            // A root that is no widget is how derive.to_root finds the top, so only children count.
            if (!is_widget(*(const unsigned long long*)p)) { if (done > 1) foreign++; continue; }
            emit_widget(p, name, text, sizeof(name), sizeof(text));

            // An object cut off by a page before its child fields would read as "no children".
            if (!readable(p + f_children, 8) || !readable(p + f_count, 4)) {
                emit("missing\t%llx\tchild fields unreadable\n", (unsigned long long)p);
                continue;
            }
            unsigned long long list_start = *(const unsigned long long*)(p + f_children);
            unsigned how_many = *(const unsigned*)(p + f_count);
            if (!list_start || how_many == 0) continue;
            // An absurd number of children means the field is wrong, not a container of a million.
            if (how_many > 100000) {
                emit("missing\t%llx\t%u children is not believable\n", (unsigned long long)p, how_many);
                continue;
            }
            if (!readable((const void*)list_start, (SIZE_T)how_many * 8)) {
                emit("missing\t%llx\tchild list unreadable\n", list_start);
                continue;
            }
            const unsigned long long* children = (const unsigned long long*)list_start;
            for (unsigned i = 0; i < how_many; i++) {
                if (!children[i]) continue;
                if (limit && work_count >= limit) { clipped++; continue; }
                if (work_count == space) {
                    space *= 2;
                    unsigned long long* bigger =
                        (unsigned long long*)realloc(work, sizeof(unsigned long long) * space);
                    if (!bigger) { emit("error: out of memory at %u nodes\n", work_count); free(work); return; }
                    work = bigger;
                }
                work[work_count++] = children[i];
            }
        }
    } __except (access_violation(GetExceptionCode())) {
        emit("missing\t%llx\twalk broken off by exception %08x\n", work[done - 1], GetExceptionCode());
    }
    if (clipped) emit("limit hit\t%u\tnot visited\n", clipped);
    // Children that carry no widget vtable: counted, not spoken, until it is measured whether that
    // is normal in the game.
    if (foreign) emit("not widgets\t%u\n", foreign);
    emit("done\t%u\n", done);
    free(work);
}

// read: raw bytes at an address, as hex.
static void cmd_read(unsigned long long address, unsigned count)
{
    // Quietly returning less than was asked makes the caller think he has everything.
    if (count > 65536) { emit("error: at most 65536 bytes per call\n"); return; }
    const unsigned char* p = (const unsigned char*)address;
    if (!readable(p, count)) { emit("error: unreadable\n"); return; }
    buf_hex(p, count);
    emit("\n");
}

// --- swallowing keys --------------------------------------------------------
static CRITICAL_SECTION g_lock;
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
        EnterCriticalSection(&g_lock);
        if (g_key_count < 256) g_keys[g_key_count++] = (int)w; else g_keys_dropped++;
        bool swallowed = (w < 256) && g_swallow[w];
        LeaveCriticalSection(&g_lock);
        if (swallowed) return 0;   // the game does not see this key
    }
    return CallWindowProcW(g_old_proc, window, message, w, l);
}

static void keys_enable(bool enable)
{
    if (enable && !g_old_proc) {
        g_window = NULL;
        EnumWindows(visit_window, 0);
        if (!g_window) { emit("error: no window found\n"); return; }
        g_old_proc = (WNDPROC)SetWindowLongPtrW(g_window, GWLP_WNDPROC, (LONG_PTR)our_proc);
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

static void cmd_waitkey(DWORD timeout)
{
    ULONGLONG begin = GetTickCount64();
    for (;;) {
        EnterCriticalSection(&g_lock);
        int count = g_key_count;
        for (int i = 0; i < count; i++) emit("key\t%d\n", g_keys[i]);
        if (g_keys_dropped) emit("error: %u keys came in while the list of 256 was full\n", g_keys_dropped);
        g_key_count = 0;
        g_keys_dropped = 0;
        LeaveCriticalSection(&g_lock);
        if (count > 0 || GetTickCount64() - begin >= timeout) return;
        Sleep(15);
    }
}

// --- sending mouse and keys to the game -------------------------------------
// Posted from inside, so the game need not be in the foreground. Coordinates are window
// points; on a fullscreen window those are screen points.
static bool ensure_window(void)
{
    if (!g_window) EnumWindows(visit_window, 0);
    if (!g_window) { emit("error: no window found\n"); return false; }
    return true;
}

// 0 only moves, 1 is left, 2 is right, and anything else is refused. Right was measured on the
// ledger button of the HUD: left toggles the window, right leaves it alone.
#define CLICK_NONE   0
#define CLICK_LEFT   1
#define CLICK_RIGHT  2

static void cmd_mouse(int x, int y, int button)
{
    if (!ensure_window()) return;
    UINT down = 0, up = 0;
    WPARAM held = 0;
    switch (button) {
        case CLICK_NONE:                                                              break;
        case CLICK_LEFT:  down = WM_LBUTTONDOWN; up = WM_LBUTTONUP; held = MK_LBUTTON; break;
        case CLICK_RIGHT: down = WM_RBUTTONDOWN; up = WM_RBUTTONUP; held = MK_RBUTTON; break;
        default:
            emit("error: button %d is not known; 0 only moves, 1 is left, 2 is right\n", button);
            return;
    }
    LPARAM spot = MAKELPARAM(x, y);
    PostMessageW(g_window, WM_MOUSEMOVE, 0, spot);
    if (down) {
        PostMessageW(g_window, down, held, spot);
        PostMessageW(g_window, up, 0, spot);
    }
    emit("mouse\t%d\t%d\t%d\n", x, y, button);
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
static void cmd_sendkey(unsigned code)
{
    if (!ensure_window()) return;
    PostMessageW(g_window, WM_KEYDOWN, code, key_lparam(code, false));
    PostMessageW(g_window, WM_KEYUP, code, key_lparam(code, true));
    emit("key sent\t%u\n", code);
}

// Entering text does not go through key codes but through WM_CHAR: that is the message an input
// field listens to. Needed in order to type a console command.
static void cmd_sendchar(unsigned ch)
{
    if (!ensure_window()) return;
    PostMessageW(g_window, WM_CHAR, ch, 1);
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
enum { C_KEYSTATE, C_ASYNC, C_KEYBOARD, C_RAWDATA, C_TOTAL };
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

// Once per process. The wrappers stay in place for the rest of the session: outside a combination
// they only count, and putting the table back while a game thread is inside a wrapper is the one
// way this could take the game down. The real function is stored before the slot is turned, so a
// call that arrives in between still finds it.
static void count_patch(void)
{
    static void* const ours[C_TOTAL] = {
        (void*)counted_key_state, (void*)counted_async_key_state,
        (void*)counted_keyboard_state, (void*)counted_raw_data
    };
    g_count_patched = true;
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
                g_count_real[i] = (void*)slots->u1.Function;
                MemoryBarrier();
                slots->u1.Function = (ULONGLONG)ours[i];
                VirtualProtect(&slots->u1.Function, sizeof(slots->u1.Function), old, &old);
                g_count_how[i] = "counted";
            }
        }
    }
}

// count: the first time it hangs the counters in; every time it answers with what was counted
// since the previous count and starts again from zero. So an interval is two calls.
static void cmd_count(void)
{
    EnterCriticalSection(&g_lock);
    if (!g_count_patched) count_patch();
    LeaveCriticalSection(&g_lock);
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
static void cmd_combo(const char* rest)
{
    unsigned pause = 0, codes[COMBO_MODIFIERS + 1] = {0};
    int count = 0, n = 0;
    if (sscanf(rest, "%u%n", &pause, &n) != 1) { emit("error: combo needs a pause in ms first\n"); return; }
    const char* p = rest + n;
    for (;;) {
        unsigned code = 0;
        if (sscanf(p, " %u%n", &code, &n) != 1) break;
        if (count == COMBO_MODIFIERS + 1) { emit("error: at most %d modifiers and one key\n", COMBO_MODIFIERS); return; }
        if (code >= 256) { emit("error: key code %u is not a virtual key\n", code); return; }
        codes[count++] = code;
        p += n;
    }
    if (!all_read(p, 0)) { emit("error: not a key code: %.40s\n", p); return; }
    if (pause > COMBO_PAUSE_MOST) { emit("error: a pause of %u ms; at most %d\n", pause, COMBO_PAUSE_MOST); return; }
    if (count < 2) { emit("error: combo needs at least one modifier and a key\n"); return; }
    unsigned key = codes[count - 1];
    if (generic_of(key)) { emit("error: the last code is the key, and %u is a modifier\n", key); return; }
    for (int i = 0; i < count - 1; i++) {
        if (!generic_of(codes[i])) { emit("error: %u is not left or right shift, ctrl or alt\n", codes[i]); return; }
        for (int j = 0; j < i; j++)
            if (generic_of(codes[j]) == generic_of(codes[i])) { emit("error: the same modifier twice\n"); return; }
    }
    if (!ensure_window()) return;
    EnterCriticalSection(&g_lock);
    if (!g_count_patched) count_patch();
    LeaveCriticalSection(&g_lock);
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
    if (!posted) { emit("error: the game window refused a message\n"); return; }
    emit("combo sent");
    for (int i = 0; i < count; i++) emit("\t%u", codes[i]);
    emit("\n");
}

// find: a byte pattern in the full memory of the game, from the inside. From outside, the same
// search costs minutes because every byte has to go through a pipe; here only the answer is left.
// Meant for research: take a sentence that is certainly on screen and see where it lives.
static void cmd_find(const char* rest, unsigned long long from_address, unsigned long long to_address)
{
    unsigned char pattern[128];
    unsigned char mask[128];
    int length = 0;
    const char* p = rest;
    while (*p && length < (int)sizeof(pattern)) {
        if (*p == '?') {
            pattern[length] = 0;
            mask[length] = 0;
            length++;
            while (*p == '?') p++;
        } else {
            unsigned value = 0;
            int used = 0;
            if (sscanf(p, "%2x%n", &value, &used) != 1 || used != 2) break;   // two digits, always
            pattern[length] = (unsigned char)value;
            mask[length] = 0xFF;
            length++;
            p += 2;
        }
        while (*p == ' ') p++;
    }
    if (length == 0) { emit("error: empty search pattern\n"); return; }
    if (*p && length == (int)sizeof(pattern)) { emit("error: pattern longer than %d bytes\n", (int)sizeof(pattern)); return; }
    if (*p) { emit("error: not a hex byte or a wildcard: %.40s\n", p); return; }
    // The first byte carries the jump of memchr. Without that jump this becomes a loop over eleven
    // gigabytes and takes minutes instead of seconds; so a wildcard in front is a mistake and not
    // an edge case to be caught.
    if (mask[0] == 0) { emit("error: first byte cannot be a wildcard\n"); return; }
    const int LIMIT = 200;

    SYSTEM_INFO base;
    GetSystemInfo(&base);
    const unsigned char* pointer = (const unsigned char*)base.lpMinimumApplicationAddress;
    const unsigned char* end_at = (const unsigned char*)base.lpMaximumApplicationAddress;
    if (from_address) pointer = (const unsigned char*)from_address;
    if (to_address && (const unsigned char*)to_address < end_at) end_at = (const unsigned char*)to_address;

    int found = 0, reported = 0, skipped = 0;
    while (pointer < end_at) {
        MEMORY_BASIC_INFORMATION info;
        if (!VirtualQuery(pointer, &info, sizeof(info))) break;
        const unsigned char* next_item = (const unsigned char*)info.BaseAddress + info.RegionSize;

        bool usable = info.State == MEM_COMMIT &&
                         !(info.Protect & PAGE_GUARD) &&
                         (info.Protect & READABLE);
        if (usable) {
            const unsigned char* begin = (const unsigned char*)info.BaseAddress;
            const unsigned char* stop = next_item - length;
            if (begin < pointer) begin = pointer;
            if (stop > end_at - length) stop = end_at - length;
            // memchr jumps in large strides to the next candidate. Comparing byte by byte is ten times
            // slower here: measured 28 July 2026, a naive loop over this memory took longer than
            // five minutes.
            __try {
                const unsigned char* q = begin;
                while (q < stop) {
                    const unsigned char* hit =
                        (const unsigned char*)memchr(q, pattern[0], (size_t)(stop - q));
                    if (!hit) break;
                    int i = 1;
                    while (i < length && (mask[i] == 0 || hit[i] == pattern[i])) i++;
                    if (i == length) {
                        found++;
                        if (reported < LIMIT) {
                            emit("t\t%llx\n", (unsigned long long)hit);
                            reported++;
                        }
                    }
                    q = hit + 1;
                }
            } __except (access_violation(GetExceptionCode())) {
                skipped++;
            }
        }
        pointer = next_item;
    }
    emit("done\t%d\treported\t%d\tskipped\t%d\n", found, reported, skipped);
    // The list stops at LIMIT; more hits than that is an error after the list, so nobody takes the
    // first two hundred for all of them.
    if (found > reported) emit("error: %d hits and only the first %d listed; narrow the search\n", found, reported);
}

// readmany: one command, many addresses. Thousands of characters meant thousands of separate
// reads of about 0.7 ms each; this turns those into one answer.
static void cmd_readmany(const char* rest)
{
    unsigned count = 0;
    int consumed = 0;
    if (sscanf(rest, "%u%n", &count, &consumed) != 1) {
        emit("error: readmany <count> <address> <address> ...\n");
        return;
    }
    if (count > 65536) { emit("error: at most 65536 bytes per address\n"); return; }
    const char* p = rest + consumed;
    int done = 0;
    while (*p) {
        unsigned long long address = 0;
        int n = 0;
        if (sscanf(p, " %llx%n", &address, &n) != 1) break;
        p += n;
        const unsigned char* q = (const unsigned char*)address;
        if (!readable(q, count)) {
            emit("l\t%llx\tunreadable\n", address);
        } else {
            emit("l\t%llx\t", address);
            buf_hex(q, count);
            emit("\n");
        }
        done++;
    }
    if (!all_read(p, 0)) { emit("error: not an address: %.40s\n", p); return; }
    emit("done\t%d\n", done);
}

static void cmd_swallow(const char* rest)
{
    bool wanted[256] = {false};
    const char* p = rest;
    int count = 0;
    for (;;) {
        unsigned code = 0; int n = 0;
        if (sscanf(p, " %u%n", &code, &n) != 1) break;
        if (code >= 256) { emit("error: key code %u is not a virtual key\n", code); return; }
        if (!wanted[code]) { wanted[code] = true; count++; }
        p += n;
    }
    if (!all_read(p, 0)) { emit("error: not a key code: %.40s\n", p); return; }
    EnterCriticalSection(&g_lock);
    for (int i = 0; i < 256; i++) g_swallow[i] = wanted[i];
    LeaveCriticalSection(&g_lock);
    emit("swallow\t%d\n", count);
}

// --- running commands and serving the pipe ----------------------------------
// set: all seven field offsets, in hex, in one go.
static void cmd_set(const char* rest)
{
    unsigned long long v[7];
    int consumed = 0;
    if (sscanf(rest, "%llx %llx %llx %llx %llx %llx %llx%n",
               &v[0], &v[1], &v[2], &v[3], &v[4], &v[5], &v[6], &consumed) != 7 || !all_read(rest, consumed)) {
        emit("error: set needs exactly seven offsets: parent position size name text children count\n");
        return;
    }
    f_parent = (SIZE_T)v[0]; f_position = (SIZE_T)v[1]; f_size = (SIZE_T)v[2]; f_name = (SIZE_T)v[3];
    f_text = (SIZE_T)v[4]; f_children = (SIZE_T)v[5]; f_count = (SIZE_T)v[6];
    g_fields_set = true;
    emit("fields set\n");
}

static void cmd_vtables(const char* rest)
{
    // Read and sort into a list of our own first: a refused command must not leave half a list.
    unsigned long long fresh[256];
    int count = 0;
    const char* p = rest;
    for (;;) {
        unsigned long long value = 0;
        int n = 0;
        if (sscanf(p, " %llx%n", &value, &n) != 1) break;
        if (count == 256) { emit("error: more than 256 vtables; this limit has to grow\n"); return; }
        int j = count++;
        while (j > 0 && fresh[j - 1] > value) { fresh[j] = fresh[j - 1]; j--; }
        fresh[j] = value;
        p += n;
    }
    if (!all_read(p, 0)) { emit("error: not a vtable address: %.40s\n", p); return; }
    memcpy(g_vtables, fresh, sizeof(unsigned long long) * count);
    g_vtable_count = count;
    emit("vtables set\t%d\n", count);
}

// Every form below ends in %n, and `READ_ALL` accepts a form only when it read the whole command;
// see `all_read`. A form with an optional argument is written out once per length, longest first.
#define READ_ALL(fields, parse) ((parse) == (fields) && all_read(command, k))

static void dispatch(char* command)
{
    buf_clear();
    unsigned long long a = 0, b = 0, c = 0;
    unsigned n = 0;
    int consumed = 0, k = 0;
    if (strncmp(command, "set ", 4) == 0)                 cmd_set(command + 4);
    else if (strncmp(command, "vtables ", 8) == 0)        cmd_vtables(command + 8);
    else if (READ_ALL(2, sscanf(command, "scan %llx %llx%n", &a, &b, &k))) cmd_scan(a, b);
    else if (strcmp(command, "scan") == 0)                cmd_scan(0, 0);
    else if (READ_ALL(2, sscanf(command, "tree %llx %u%n", &a, &n, &k))) cmd_tree(a, n);
    else if (READ_ALL(1, sscanf(command, "tree %llx%n", &a, &k)))         cmd_tree(a, 0);
    else if (READ_ALL(2, sscanf(command, "read %llx %u%n", &a, &n, &k))) cmd_read(a, n);
    else if (strncmp(command, "readmany ", 9) == 0)       cmd_readmany(command + 9);
    else if (sscanf(command, "findin %llx %llx %n", &a, &b, &consumed) == 2) cmd_find(command + consumed, a, b);
    else if (strncmp(command, "find ", 5) == 0)           cmd_find(command + 5, 0, 0);
    else if (strcmp(command, "keys on") == 0)             keys_enable(true);
    else if (strcmp(command, "keys off") == 0)            keys_enable(false);
    else if (strncmp(command, "swallow", 7) == 0)         cmd_swallow(command + 7);
    else if (READ_ALL(1, sscanf(command, "waitkey %u%n", &n, &k))) cmd_waitkey(n);
    else if (READ_ALL(3, sscanf(command, "mouse %llu %llu %llu%n", &a, &b, &c, &k))) cmd_mouse((int)a, (int)b, (int)c);
    else if (READ_ALL(1, sscanf(command, "sendkey %u%n", &n, &k))) cmd_sendkey(n);
    else if (READ_ALL(1, sscanf(command, "sendchar %u%n", &n, &k))) cmd_sendchar(n);
    else if (strcmp(command, "count") == 0)               cmd_count();
    else if (strncmp(command, "combo ", 6) == 0)          cmd_combo(command + 6);
    else if (strcmp(command, "hello") == 0)
        emit("channel\t%lu\tbuilt " __DATE__ " " __TIME__ "\n", GetCurrentProcessId());
    else emit("error: unknown command, or more than it reads: %.200s\n", command);
    emit("end\n");
}

// One conversation per thread, and accept connections without limit. Without that, one dead or
// hung counterpart blocks the whole channel, and restarting the game is the only way out.
// That is exactly what we do not want.

static bool emit_all(HANDLE pipe, const char* data, size_t count)
{
    size_t done = 0;
    while (done < count) {
        DWORD now = 0;
        if (!WriteFile(pipe, data + done, (DWORD)(count - done), &now, NULL) || now == 0)
            return false;
        done += now;
    }
    return true;
}

// Every reply is preceded by its length. That way the other side can recognise a half-arrived
// reply instead of quietly computing with it.
static DWORD WINAPI serve_session(LPVOID handle)
{
    HANDLE pipe = (HANDLE)handle;
    char command[8192];
    char header[64];
    for (;;) {
        DWORD bytes_read = 0;
        if (!ReadFile(pipe, command, sizeof(command) - 1, &bytes_read, NULL) || bytes_read == 0) break;
        command[bytes_read] = 0;
        // A command that fills the buffer exactly is almost certainly truncated. Carrying on quietly
        // would yield half an address here and therefore a wrong read; this is a boundary where
        // foreign input arrives, so it is checked.
        if (bytes_read >= sizeof(command) - 1) {
            buf_clear();
            emit("error: command too long\nend\n");
        } else {
            while (bytes_read && (command[bytes_read - 1] == '\n' || command[bytes_read - 1] == '\r'))
                command[--bytes_read] = 0;
            dispatch(command);
        }
        if (g_lost) {                                   // what was built cannot be trusted; say so
            buf_clear();
            emit("error: the game had no memory left for this reply\nend\n");
        }
        int header_length = sprintf_s(header, sizeof(header), "reply\t%zu\n", g_len);
        if (!emit_all(pipe, header, (size_t)header_length)) break;
        if (!emit_all(pipe, g_buf, g_len)) break;
    }
    free(g_buf);
    g_buf = NULL; g_len = 0; g_cap = 0;
    FlushFileBuffers(pipe);
    DisconnectNamedPipe(pipe);
    CloseHandle(pipe);
    return 0;
}

static DWORD WINAPI serve_pipe(LPVOID)
{
    for (;;) {
        HANDLE pipe = CreateNamedPipeW(PIPE_NAME, PIPE_ACCESS_DUPLEX,
                                       PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                                       PIPE_UNLIMITED_INSTANCES, 1U << 20U, 1U << 16U, 0, NULL);
        if (pipe == INVALID_HANDLE_VALUE) { Sleep(500); continue; }
        if (!ConnectNamedPipe(pipe, NULL) && GetLastError() != ERROR_PIPE_CONNECTED) {
            CloseHandle(pipe);
            continue;
        }
        // a thread for this conversation straight away, and back to accepting the next one
        HANDLE worker = CreateThread(NULL, 0, serve_session, pipe, 0, NULL);
        if (worker) CloseHandle(worker); else { DisconnectNamedPipe(pipe); CloseHandle(pipe); }
    }
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        InitializeCriticalSection(&g_lock);
        CreateThread(NULL, 0, serve_pipe, NULL, 0, NULL);
    }
    return TRUE;
}
