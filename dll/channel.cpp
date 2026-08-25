// channel.cpp - the window to the inside.
//
// Runs inside the game process. Everything here falls under the exception: a fault takes the game
// down with it, so every read is checked for readability first. This is not defensive programming
// out of habit but the one place where it belongs.
//
// The DLL knows nothing about CK3. Python derives the field offsets and the widget vtables and
// passes them in; all that lives here is the machinery to walk memory with them.
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

static const wchar_t* PIPE_NAME = L"\\\\.\\pipe\\ck3_access";

// Set by Python with the 'set' command. The initial values are those of build 1.19.0.6,
// only so that a test without 'set' does something sensible.
static SIZE_T f_parent = 0x0E8, f_position = 0x118, f_size = 0x128, f_name = 0x1B8, f_text = 0x390;

static unsigned long long* g_vtables = NULL;   // sorted, for binary search
static int g_vtable_count = 0;

// --- reply buffer -----------------------------------------------------------
// One buffer per thread. That way two connections cannot overwrite each other, and a command
// that waits a long time (waitkey, waitchange) need not hold a lock that freezes every other
// conversation.
static __declspec(thread) char* g_buf = NULL;
static __declspec(thread) size_t g_len = 0;
static __declspec(thread) size_t g_cap = 0;

static void buf_clear(void) { g_len = 0; }

static void buf_add(const char* text, size_t n)
{
    if (g_len + n + 1 > g_cap) {
        size_t fresh = (g_cap ? g_cap : 65536);
        while (fresh < g_len + n + 1) fresh *= 2;
        g_buf = (char*)realloc(g_buf, fresh);
        g_cap = fresh;
    }
    memcpy(g_buf + g_len, text, n);
    g_len += n;
    g_buf[g_len] = 0;
}

static void emit(const char* format, ...)
{
    char line[16384];
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
        part[out++] = digit[p[i] >> 4];
        part[out++] = digit[p[i] & 15];
        if (out >= sizeof(part) - 2) { buf_add(part, out); out = 0; }
    }
    if (out) buf_add(part, out);
}

// --- reading memory safely --------------------------------------------------
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

// scan: walk memory and return every widget object.
// Without bounds it walks everything, and with CK3 that costs tens of seconds because the game
// has eleven gigabytes in use. With bounds it only reads the regions where widgets turned up
// last time; those come from one pool, so that is a handful of regions.
// Every region with hits is followed by a 'region' line, so the other side can remember it.
static void cmd_scan(unsigned long long from_address, unsigned long long to_address)
{
    if (g_vtable_count == 0) { emit("error: no vtables set\n"); return; }

    SYSTEM_INFO base;
    GetSystemInfo(&base);
    const unsigned char* pointer = from_address ? (const unsigned char*)from_address
                                      : (const unsigned char*)base.lpMinimumApplicationAddress;
    const unsigned char* end_at = to_address ? (const unsigned char*)to_address
                                     : (const unsigned char*)base.lpMaximumApplicationAddress;

    char name[512], text[1024];
    int found = 0;
    int skipped = 0;

    while (pointer < end_at) {
        MEMORY_BASIC_INFORMATION info;
        if (!VirtualQuery(pointer, &info, sizeof(info))) break;
        const unsigned char* next_item = (const unsigned char*)info.BaseAddress + info.RegionSize;

        bool usable = info.State == MEM_COMMIT && info.Type == MEM_PRIVATE &&
                         !(info.Protect & PAGE_GUARD) &&
                         (info.Protect & (PAGE_READWRITE | PAGE_WRITECOPY));
        if (usable) {
            const unsigned char* begin = (const unsigned char*)info.BaseAddress;
            const unsigned char* stop = next_item - f_text - 32;
            int here = 0;
            // The game frees memory while we are reading. A violation here may abort the
            // scan, but must never take the game or the channel with it.
            __try {
                for (const unsigned char* p = begin; p < stop; p += 8) {
                    if (!is_widget(*(const unsigned long long*)p)) continue;
                    name[0] = 0; text[0] = 0;
                    read_cstring(name, sizeof(name), p, f_name);
                    read_cstring(text, sizeof(text), p, f_text);
                    emit("w\t%llx\t%llx\t%.1f\t%.1f\t%.1f\t%.1f\t%llx\t%s\t%s\n",
                            (unsigned long long)p, *(const unsigned long long*)p,
                            read_float(p + f_position), read_float(p + f_position + 4),
                            read_float(p + f_size), read_float(p + f_size + 4),
                            read64(p + f_parent), name, text);
                    found++; here++;
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                skipped++;
            }
            if (here)
                emit("region\t%llx\t%llx\t%d\n", (unsigned long long)info.BaseAddress,
                        (unsigned long long)info.RegionSize, here);
        }
        pointer = next_item;
    }
    emit("done\t%d\tskipped\t%d\n", found, skipped);
}

// tree: from a widget, walk the children, and their children, and so on.
// This is what the channel exists for: searching no byte at all, only following pointers.
static SIZE_T f_children = 0x0F0, f_count = 0x0FC;

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
    // If the text does not fit the line, a line of its own follows with the real length. That way
    // the other side can still fetch it with `read` instead of thinking that was all of it.
    if (name_length >= space_name || text_length >= space_text)
        emit("truncated\t%llx\t%zu\t%zu\n", (unsigned long long)p, name_length, text_length);
}

static void cmd_tree(unsigned long long root, unsigned limit)
{
    // No fixed upper bound any more. The old version stopped at 20,000 nodes and silently dropped
    // children after that; every statement of "that is not in the tree" was unreliable as a result.
    // The queue now grows along, and a limit only applies when the caller asks for one - and then
    // it is reported.
    unsigned space = 20000;
    unsigned long long* work = (unsigned long long*)malloc(sizeof(unsigned long long) * space);
    if (!work) { emit("error: out of memory\n"); return; }

    unsigned work_count = 0, done = 0, clipped = 0;
    work[work_count++] = root;
    char name[512], text[8192];

    __try {
        while (done < work_count) {
            const unsigned char* p = (const unsigned char*)work[done++];
            if (!readable(p, f_text + 32)) continue;
            if (!is_widget(*(const unsigned long long*)p)) continue;
            emit_widget(p, name, text, sizeof(name), sizeof(text));

            unsigned long long list_start = read64(p + f_children);
            unsigned how_many = 0;
            if (readable(p + f_count, 4)) how_many = *(const unsigned*)(p + f_count);
            if (!list_start || how_many == 0) continue;
            // An absurd number of children means the field is wrong, not that there is a container
            // of a million. Report it, do not skip it quietly.
            if (how_many > 100000) {
                emit("suspect\t%llx\tchildren\t%u\n", (unsigned long long)p, how_many);
                continue;
            }
            if (!readable((const void*)list_start, (SIZE_T)how_many * 8)) continue;
            const unsigned long long* children = (const unsigned long long*)list_start;
            for (unsigned i = 0; i < how_many; i++) {
                if (!children[i]) continue;
                if (limit && work_count >= limit) { clipped++; continue; }
                if (work_count == space) {
                    space *= 2;
                    unsigned long long* bigger =
                        (unsigned long long*)realloc(work, sizeof(unsigned long long) * space);
                    if (!bigger) { emit("error: out of memory at %u nodes\n", work_count); break; }
                    work = bigger;
                }
                work[work_count++] = children[i];
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        emit("interrupted\t%08x\n", GetExceptionCode());
    }
    if (clipped) emit("limit hit\t%u\tnot visited\n", clipped);
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

// call: call the nth function from an object vtable, with the object as the first
// argument. This is the most dangerous command there is; it exists so that a button can be
// pressed without a mouse.
typedef unsigned long long (*Methode)(void*, unsigned long long, unsigned long long);

static void cmd_call(unsigned long long address, unsigned index, unsigned long long a1, unsigned long long a2)
{
    void* object_address = (void*)address;
    unsigned long long vtable = read64(object_address);
    if (!vtable || !is_widget(vtable)) { emit("error: no widget at that address\n"); return; }
    unsigned long long function = read64((const unsigned char*)vtable + index * 8);
    if (!function) { emit("error: empty slot in the vtable\n"); return; }
    unsigned long long out = 0;
    __try {
        out = ((Methode)function)(object_address, a1, a2);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        emit("error: exception %08x, the game is still alive\n", GetExceptionCode());
        return;
    }
    emit("out\t%llx\n", out);
}

// --- swallowing keys --------------------------------------------------------
static CRITICAL_SECTION g_lock;
static int g_keys[256];
static int g_key_count = 0;
static WNDPROC g_old_proc = NULL;
static HWND g_window = NULL;
static bool g_swallow[256] = {false};   // keys the game must not see

static BOOL CALLBACK visit_window(HWND window, LPARAM)
{
    DWORD from_address = 0;
    GetWindowThreadProcessId(window, &from_address);
    if (from_address == GetCurrentProcessId() && IsWindowVisible(window)) { g_window = window; return FALSE; }
    return TRUE;
}

static LRESULT CALLBACK our_proc(HWND window, UINT message, WPARAM w, LPARAM l)
{
    if (message == WM_KEYDOWN || message == WM_SYSKEYDOWN) {
        EnterCriticalSection(&g_lock);
        if (g_key_count < 256) g_keys[g_key_count++] = (int)w;
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
    DWORD begin = GetTickCount();
    for (;;) {
        EnterCriticalSection(&g_lock);
        int count = g_key_count;
        for (int i = 0; i < count; i++) emit("key\t%d\n", g_keys[i]);
        g_key_count = 0;
        LeaveCriticalSection(&g_lock);
        if (count > 0 || GetTickCount() - begin >= timeout) return;
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

static void cmd_mouse(int x, int y, int button)
{
    if (!ensure_window()) return;
    LPARAM spot = MAKELPARAM(x, y);
    PostMessageW(g_window, WM_MOUSEMOVE, 0, spot);
    if (button) {
        PostMessageW(g_window, WM_LBUTTONDOWN, MK_LBUTTON, spot);
        PostMessageW(g_window, WM_LBUTTONUP, 0, spot);
    }
    emit("mouse\t%d\t%d\t%d\n", x, y, button);
}

// A posted key message with lParam zero cannot come from a real keyboard: it holds no scancode,
// no repeat count and no extended bit. That is why the game ignored these messages while
// swallowing those same keys did work. Here lParam is built up the way Windows would assemble
// it itself.
static LPARAM key_lparam(unsigned code, bool key_up)
{
    UINT scancode = MapVirtualKeyW(code, MAPVK_VK_TO_VSC);
    LPARAM l = 1;                                      // repeat count
    l |= (LPARAM)(scancode & 0xFF) << 16;
    switch (code) {
        case VK_LEFT: case VK_RIGHT: case VK_UP: case VK_DOWN:
        case VK_HOME: case VK_END: case VK_PRIOR: case VK_NEXT:
        case VK_INSERT: case VK_DELETE: case VK_NUMLOCK:
        case VK_RCONTROL: case VK_RMENU:
            l |= 1LL << 24;                            // extended bit
            break;
        default:
            break;
    }
    if (key_up) l |= (1LL << 30) | (1LL << 31);        // previous state and transition
    return l;
}

static void cmd_sendkey(unsigned code)
{
    if (!ensure_window()) return;
    PostMessageW(g_window, WM_KEYDOWN, code, key_lparam(code, false));
    PostMessageW(g_window, WM_KEYUP, code, key_lparam(code, true));
    emit("key sent\t%u\n", code);
}

// A key held down, and released again, as two separate commands. Needed for a binding with a
// modifier: `sendkey` presses and releases in one go, so a shift sent before an F-key is already
// back up by the time the F-key arrives, and shift+F1 cannot be sent at all. Measured 25 August
// 2026 against the game's own bindings: `ledger_window` sits on shift+F1 and was unreachable.
// Whether it works depends on how the game reads the modifier. GetKeyState is fed from the message
// queue and sees these; GetAsyncKeyState reads the physical keyboard and cannot. That is a
// measurement, not a guess - send shift down, F1, and see whether the ledger opens.
static void cmd_keydown(unsigned code)
{
    if (!ensure_window()) return;
    PostMessageW(g_window, WM_KEYDOWN, code, key_lparam(code, false));
    emit("key down\t%u\n", code);
}

static void cmd_keyup(unsigned code)
{
    if (!ensure_window()) return;
    PostMessageW(g_window, WM_KEYUP, code, key_lparam(code, true));
    emit("key up\t%u\n", code);
}


// Entering text does not go through key codes but through WM_CHAR: that is the message an input
// field listens to. Needed in order to type a console command.
static void cmd_sendchar(unsigned ch)
{
    if (!ensure_window()) return;
    PostMessageW(g_window, WM_CHAR, ch, 1);
    emit("char sent\t%u\n", ch);
}

// find: a byte pattern in the full memory of the game, from the inside. From outside, the same
// search costs minutes because every byte has to go through a pipe; here only the answer is left.
// Meant for research: take a sentence that is certainly on screen and see where it lives.
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
            if (sscanf(p, "%2x", &value) != 1) break;
            pattern[length] = (unsigned char)value;
            mask[length] = 0xFF;
            length++;
            p += 2;
        }
        while (*p == ' ') p++;
    }
    if (length == 0) { emit("error: empty search pattern\n"); return; }
    if (*p) { emit("error: pattern longer than %d bytes\n", (int)sizeof(pattern)); return; }
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
                         (info.Protect & (PAGE_READWRITE | PAGE_WRITECOPY |
                                          PAGE_READONLY | PAGE_EXECUTE_READ));
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
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                skipped++;
            }
        }
        pointer = next_item;
    }
    emit("done\t%d\treported\t%d\tskipped\t%d\n", found, reported, skipped);
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
    emit("klaar\t%d\n", done);
}

static void cmd_swallow(const char* rest)
{
    EnterCriticalSection(&g_lock);
    for (int i = 0; i < 256; i++) g_swallow[i] = false;
    const char* p = rest;
    int count = 0;
    for (;;) {
        unsigned code = 0; int n = 0;
        if (sscanf(p, " %u%n", &code, &n) != 1) break;
        if (code < 256) { g_swallow[code] = true; count++; }
        p += n;
    }
    LeaveCriticalSection(&g_lock);
    emit("swallow\t%d\n", count);
}

// --- waiting for a change ---------------------------------------------------
static int count_widgets(void)
{
    SYSTEM_INFO base;
    GetSystemInfo(&base);
    const unsigned char* pointer = (const unsigned char*)base.lpMinimumApplicationAddress;
    const unsigned char* end_at = (const unsigned char*)base.lpMaximumApplicationAddress;
    int tally = 0;
    while (pointer < end_at) {
        MEMORY_BASIC_INFORMATION info;
        if (!VirtualQuery(pointer, &info, sizeof(info))) break;
        const unsigned char* next_item = (const unsigned char*)info.BaseAddress + info.RegionSize;
        if (info.State == MEM_COMMIT && info.Type == MEM_PRIVATE && !(info.Protect & PAGE_GUARD) &&
            (info.Protect & (PAGE_READWRITE | PAGE_WRITECOPY))) {
            __try {
                for (const unsigned char* p = (const unsigned char*)info.BaseAddress; p < next_item - 8; p += 8)
                    if (is_widget(*(const unsigned long long*)p)) tally++;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }
        pointer = next_item;
    }
    return tally;
}

static void cmd_waitchange(DWORD timeout)
{
    int start_tally = count_widgets();
    DWORD begin = GetTickCount();
    for (;;) {
        Sleep(60);
        int now = count_widgets();
        if (now != start_tally) { emit("change\t%d\t%d\n", start_tally, now); return; }
        if (GetTickCount() - begin >= timeout) { emit("same\t%d\n", now); return; }
    }
}

// --- running commands and serving the pipe ----------------------------------
static void cmd_set(const char* rest)
{
    unsigned long long parent, position, size, name, text;
    int bytes_read = sscanf(rest, "%llx %llx %llx %llx %llx", &parent, &position, &size, &name, &text);
    if (bytes_read != 5) { emit("error: set needs five field offsets\n"); return; }
    f_parent = (SIZE_T)parent; f_position = (SIZE_T)position; f_size = (SIZE_T)size;
    f_name = (SIZE_T)name; f_text = (SIZE_T)text;
    emit("fields set\n");
}

static void cmd_vtables(const char* rest)
{
    free(g_vtables);
    g_vtables = (unsigned long long*)malloc(sizeof(unsigned long long) * 256);
    g_vtable_count = 0;
    const char* p = rest;
    while (g_vtable_count < 256) {
        unsigned long long value = 0;
        int n = 0;
        if (sscanf(p, " %llx%n", &value, &n) != 1) break;
        g_vtables[g_vtable_count++] = value;
        p += n;
    }
    for (int i = 1; i < g_vtable_count; i++) {           // insertion sort, the list is small
        unsigned long long key = g_vtables[i];
        int j = i - 1;
        while (j >= 0 && g_vtables[j] > key) { g_vtables[j + 1] = g_vtables[j]; j--; }
        g_vtables[j + 1] = key;
    }
    emit("vtables set\t%d\n", g_vtable_count);
}

static void dispatch(char* command)
{
    buf_clear();
    unsigned long long a = 0, b = 0, c = 0;
    unsigned n = 0;
    int consumed = 0;
    if (strncmp(command, "set ", 4) == 0)                 cmd_set(command + 4);
    else if (strncmp(command, "vtables ", 8) == 0)        cmd_vtables(command + 8);
    else if (sscanf(command, "scan %llx %llx", &a, &b) == 2) cmd_scan(a, b);
    else if (strcmp(command, "scan") == 0)                cmd_scan(0, 0);
    else if (sscanf(command, "tree %llx %u", &a, &n) >= 1)  cmd_tree(a, n);
    else if (sscanf(command, "childfield %llx %llx", &a, &b) == 2) {
        f_children = (SIZE_T)a; f_count = (SIZE_T)b;
        emit("childfield set\t%llx\t%llx\n", a, b);
    }
    else if (sscanf(command, "read %llx %u", &a, &n) == 2) cmd_read(a, n);
    else if (strncmp(command, "readmany ", 9) == 0)       cmd_readmany(command + 9);
    else if (sscanf(command, "findin %llx %llx %n", &a, &b, &consumed) == 2)
                                                           cmd_find(command + consumed, a, b);
    else if (sscanf(command, "call %llx %u %llx %llx", &a, &n, &b, &c) >= 2) cmd_call(a, n, b, c);
    else if (strcmp(command, "keys on") == 0)         keys_enable(true);
    else if (strcmp(command, "keys off") == 0)         keys_enable(false);
    else if (sscanf(command, "waitkey %u", &n) == 1)  cmd_waitkey(n);
    else if (sscanf(command, "waitchange %u", &n) == 1) cmd_waitchange(n);
    else if (strncmp(command, "swallow", 7) == 0)         cmd_swallow(command + 7);
    else if (sscanf(command, "mouse %llu %llu %llu", &a, &b, &c) == 3) cmd_mouse((int)a, (int)b, (int)c);
    else if (sscanf(command, "sendkey %u", &n) == 1)  cmd_sendkey(n);
    else if (sscanf(command, "keydown %u", &n) == 1)  cmd_keydown(n);
    else if (sscanf(command, "keyup %u", &n) == 1)  cmd_keyup(n);
    else if (sscanf(command, "sendchar %u", &n) == 1)  cmd_sendchar(n);
    else if (strncmp(command, "find ", 5) == 0)           cmd_find(command + 5, 0, 0);
    else if (strcmp(command, "hello") == 0)
        emit("channel\t%lu\tbuilt " __DATE__ " " __TIME__ "\n", GetCurrentProcessId());
    else emit("error: unknown command\n");
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
            int header_length = sprintf_s(header, sizeof(header), "reply\t%zu\n", g_len);
            if (!emit_all(pipe, header, (size_t)header_length)) break;
            if (!emit_all(pipe, g_buf, g_len)) break;
            continue;
        }
        while (bytes_read && (command[bytes_read - 1] == '\n' || command[bytes_read - 1] == '\r'))
            command[--bytes_read] = 0;

        dispatch(command);

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
                                       PIPE_UNLIMITED_INSTANCES, 1 << 20, 1 << 16, 0, NULL);
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
