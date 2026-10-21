// channel.cpp - the window to the inside.
//
// Runs inside the game process. Everything here falls under the exception: a fault takes the game
// down with it, so every read is checked for readability first. This is not defensive programming
// out of habit but the one place where it belongs.
//
// The DLL knows nothing about CK3. Python derives the field offsets and the widget vtables and
// passes them in; all that lives here is the pipe and the machinery to walk memory with them. Keys
// and clicks are input.cpp.
#include <windows.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>

#include "channel.h"

static const wchar_t* PIPE_NAME = L"\\\\.\\pipe\\ck3_access";

// Set by Python with `set`. There are no defaults: a walk on offsets nobody passed in is refused.
static SIZE_T f_parent, f_position, f_size, f_name, f_text, f_children, f_count;
static bool g_fields_set = false;

static unsigned long long g_vtables[256];   // sorted, for binary search
static int g_vtable_count = 0;

// Page protections. Windows defines them as plain ints; these are the bit patterns. READABLE is the
// one definition of a page that may be read; WRITABLE is where scan looks for objects the game made.
static const DWORD WRITABLE = DWORD{PAGE_READWRITE} | DWORD{PAGE_WRITECOPY};
static const DWORD READABLE = WRITABLE | DWORD{PAGE_READONLY} | DWORD{PAGE_EXECUTE_READ} |
                              DWORD{PAGE_EXECUTE_READWRITE} | DWORD{PAGE_EXECUTE_WRITECOPY};

// --- the DLL's own stacks -----------------------------------------------------
// A search through the game's memory must not find the DLL itself, and every session leaves what it
// handled on its stack. Measured 4 October 2026: the sorted copy of the vtable list that `vtables`
// left there came back from the scan as twenty widgets, and walking each cost seconds - 75 of the 80
// seconds derive.quick_root took. So a session puts its stack on this list while it runs, and scan
// and find skip what lies on it and say how much that was.
struct OwnStack {
    ULONG_PTR low, high;
    OwnStack* next;
};
static OwnStack* g_own_stacks = NULL;
static SRWLOCK g_own_lock = SRWLOCK_INIT;

static bool own_stack(const MEMORY_BASIC_INFORMATION& info)
{
    const ULONG_PTR begin = (ULONG_PTR)info.BaseAddress;
    const ULONG_PTR end = begin + info.RegionSize;
    bool mine = false;
    AcquireSRWLockShared(&g_own_lock);
    for (const OwnStack* s = g_own_stacks; s != NULL && !mine; s = s->next)
        mine = begin < s->high && s->low < end;
    ReleaseSRWLockShared(&g_own_lock);
    return mine;
}

// Write-combined and uncached memory is what the processor hands the graphics card. No object of the
// game lives there - the game would read its own objects past the cache - and reading it is slow:
// measured 4 October 2026, the piece of a scan holding one such region of 128 MB, 144 MB in all, took
// five seconds, where pieces of 70 MB without one took 0.13. Skipped by scan and find, and counted.
static bool uncached(const MEMORY_BASIC_INFORMATION& info)
{
    return (info.Protect & (DWORD{PAGE_WRITECOMBINE} | DWORD{PAGE_NOCACHE})) != 0;
}

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

void emit(const char* format, ...)
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

// --- reading a command ------------------------------------------------------
// Commands come from our own Python, but this is where outside input enters the game process, so a
// number is read strictly: digits only, no sign, nothing too big for its field. A command with text
// left over is refused, never shortened: an argument that is dropped looks exactly like one that
// arrived. A number is one of two kinds, named by a letter: `x` an address in hex, `u` a count or
// a code in decimal that fits 32 bits.

// The value of a hex digit, or -1. A decimal digit is one whose value is under ten.
static int digit_value(char ch)
{
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    return -1;
}

// Nothing but blanks from here to the end of the command.
bool all_read(const char* p)
{
    while (*p == ' ' || *p == '\t') p++;
    return *p == 0;
}

// One number of this kind off the front of *p, past blanks; *p then stands right after it.
// strtoull alone would take a sign - a minus hands back the number counted down from the top - and
// report an overflow only through errno; here both are a refusal.
bool take(const char** p, char kind, unsigned long long* out)
{
    const int base = kind == 'x' ? 16 : 10;
    const unsigned long long most = kind == 'x' ? ULLONG_MAX : UINT_MAX;
    const char* start = *p;
    while (*start == ' ' || *start == '\t') start++;
    const int first = digit_value(*start);
    if (first < 0 || first >= base) return false;
    char* end = NULL;
    errno = 0;
    const unsigned long long value = strtoull(start, &end, base);
    if (errno == ERANGE || value > most) return false;
    *out = value;
    *p = end;
    return true;
}

// The numbers of a command, one letter each in `form`, and nothing after them.
static bool args(const char* p, const char* form, unsigned long long* out)
{
    for (; *form; form++, out++)
        if (!take(&p, *form, out)) return false;
    return all_read(p);
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
    if (!(info.Protect & READABLE)) return false;
    const char* end_of = (const char*)info.BaseAddress + info.RegionSize;
    return (const char*)address + count <= end_of;
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

// A stretch of the game's memory: from, up to but not including to. A null end stands for that end
// of what the process can address. One parameter instead of two, so the ends cannot change places.
struct Span { const unsigned char* from; const unsigned char* to; };

// What a search left out, per kind: how many regions, and how many of their bytes lay inside the
// stretch searched. Said on a line of its own, so the caller can tell "not there" from "not looked at".
struct Skips { int regions; SIZE_T bytes; };

static void skip(Skips& tally, const MEMORY_BASIC_INFORMATION& info, Span searched)
{
    const unsigned char* begin = (const unsigned char*)info.BaseAddress;
    const unsigned char* end = begin + info.RegionSize;
    if (begin < searched.from) begin = searched.from;
    if (end > searched.to) end = searched.to;
    tally.regions++;
    if (end > begin) tally.bytes += (SIZE_T)(end - begin);
}

static void say_skipped(const char* what, const Skips& tally)
{
    if (tally.regions) emit("%s\t%d\t%zu\n", what, tally.regions, tally.bytes);
}

// scan: every address that holds a widget vtable, with that vtable, and nothing else - it runs
// before the field offsets are known, because the derivation starts here. Every eight bytes up to
// the end of a region are a candidate. Without bounds it walks all eleven gigabytes of the game.
static void cmd_scan(Span span)
{
    if (g_vtable_count == 0) { emit("error: no vtables set\n"); return; }

    SYSTEM_INFO base;
    GetSystemInfo(&base);
    const unsigned char* pointer = span.from ? span.from : (const unsigned char*)base.lpMinimumApplicationAddress;
    const unsigned char* end_at = span.to ? span.to : (const unsigned char*)base.lpMaximumApplicationAddress;
    const Span searched = {pointer, end_at};
    int found = 0;
    int skipped = 0;
    Skips own = {0, 0};
    Skips slow = {0, 0};

    while (pointer < end_at) {
        MEMORY_BASIC_INFORMATION info;
        if (!VirtualQuery(pointer, &info, sizeof(info))) break;
        const unsigned char* next_item = (const unsigned char*)info.BaseAddress + info.RegionSize;

        bool usable = info.State == MEM_COMMIT && info.Type == MEM_PRIVATE &&
                         !(info.Protect & PAGE_GUARD) &&
                         (info.Protect & WRITABLE);
        if (usable && own_stack(info)) { skip(own, info, searched); usable = false; }
        if (usable && uncached(info)) { skip(slow, info, searched); usable = false; }
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
    say_skipped("own stack", own);
    say_skipped("uncached", slow);
    emit("done\t%d\tskipped\t%d\n", found, skipped);
}

// tree: from a widget, walk the children, and their children, and so on - following pointers,
// searching nothing. Whatever the walk loses it says on one kind of line, `missing <address> <why>`,
// and widgettree.widgets speaks every one of them.
// A widget whose parent, position or size cannot be read is such a loss, not a widget at 0,0 under
// no parent: a zero read for an unreadable field looks exactly like a measurement.
static bool emit_widget(const unsigned char* p, char* name, char* text, size_t space_name, size_t space_text)
{
    if (!readable(p + f_parent, 8) || !readable(p + f_position, 8) || !readable(p + f_size, 8)) {
        emit("missing\t%llx\tparent, position or size unreadable\n", (unsigned long long)p);
        return false;
    }
    size_t name_length = read_cstring(name, space_name, p, f_name);
    size_t text_length = read_cstring(text, space_text, p, f_text);
    const float* position = (const float*)(p + f_position);
    const float* size = (const float*)(p + f_size);
    emit("w\t%llx\t%llx\t%.1f\t%.1f\t%.1f\t%.1f\t%llx\t%s\t%s\n",
            (unsigned long long)p, *(const unsigned long long*)p,
            position[0], position[1], size[0], size[1],
            *(const unsigned long long*)(p + f_parent), name, text);
    if (name_length >= space_name)
        emit("missing\t%llx\tname of %zu characters cut short\n", (unsigned long long)p, name_length);
    if (text_length >= space_text)
        emit("missing\t%llx\ttext of %zu characters cut short\n", (unsigned long long)p, text_length);
    return true;
}

static void cmd_tree(const unsigned char* root)
{
    if (!g_fields_set || g_vtable_count == 0) { emit("error: set and vtables come first\n"); return; }
    // The queue grows as far as the tree goes.
    unsigned space = 20000;
    unsigned long long* work = (unsigned long long*)malloc(sizeof(unsigned long long) * space);
    if (!work) { emit("error: out of memory\n"); return; }

    unsigned work_count = 0, done = 0, foreign = 0;
    work[work_count++] = (unsigned long long)root;
    char name[512], text[8192];

    __try {
        while (done < work_count) {
            const unsigned char* p = as_pointer<const unsigned char*>(work[done++]);
            // Only the vtable has to be readable: every field below is checked on its own, and an
            // object may end right before an uncommitted page.
            if (!readable(p, 8)) { emit("missing\t%llx\tunreadable\n", (unsigned long long)p); continue; }
            // A root that is no widget is how derive.to_root finds the top, so only children count.
            if (!is_widget(*(const unsigned long long*)p)) { if (done > 1) foreign++; continue; }
            if (!emit_widget(p, name, text, sizeof(name), sizeof(text))) continue;

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
            if (!readable(as_pointer<const void*>(list_start), (SIZE_T)how_many * 8)) {
                emit("missing\t%llx\tchild list unreadable\n", list_start);
                continue;
            }
            const unsigned long long* children = as_pointer<const unsigned long long*>(list_start);
            for (unsigned i = 0; i < how_many; i++) {
                if (!children[i]) continue;
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
    // Children that carry no widget vtable: counted, not spoken, until it is measured whether that
    // is normal in the game.
    if (foreign) emit("not widgets\t%u\n", foreign);
    emit("done\t%u\n", done);
    free(work);
}

// read: raw bytes at an address, as hex.
static void cmd_read(const unsigned char* address, unsigned count)
{
    // Quietly returning less than was asked makes the caller think he has everything.
    if (count > 65536) { emit("error: at most 65536 bytes per call\n"); return; }
    if (!readable(address, count)) { emit("error: unreadable\n"); return; }
    buf_hex(address, count);
    emit("\n");
}

// find: a byte pattern in the full memory of the game, from the inside. From outside, the same
// search costs minutes because every byte has to go through a pipe; here only the answer is left.
// Meant for research: take a sentence that is certainly on screen and see where it lives.
static void cmd_find(const char* rest, Span span)
{
    unsigned char pattern[128];
    int length = 0;
    const char* p = rest;
    while (*p == ' ') p++;
    while (*p && length < (int)sizeof(pattern)) {
        const int high = digit_value(p[0]);
        const int low = high < 0 ? -1 : digit_value(p[1]);
        if (low < 0) break;                                     // two digits, always
        pattern[length++] = static_cast<unsigned char>(high * 16 + low);
        p += 2;
        while (*p == ' ') p++;
    }
    if (*p && length == (int)sizeof(pattern)) { emit("error: pattern longer than %d bytes\n", (int)sizeof(pattern)); return; }
    if (*p) { emit("error: not a hex byte: %.40s\n", p); return; }
    if (length == 0) { emit("error: empty search pattern\n"); return; }
    const int LIMIT = 200;

    SYSTEM_INFO base;
    GetSystemInfo(&base);
    const unsigned char* pointer = (const unsigned char*)base.lpMinimumApplicationAddress;
    const unsigned char* end_at = (const unsigned char*)base.lpMaximumApplicationAddress;
    if (span.from) pointer = span.from;
    if (span.to && span.to < end_at) end_at = span.to;

    const Span searched = {pointer, end_at};
    int found = 0, reported = 0, skipped = 0;
    Skips own = {0, 0};
    Skips slow = {0, 0};
    while (pointer < end_at) {
        MEMORY_BASIC_INFORMATION info;
        if (!VirtualQuery(pointer, &info, sizeof(info))) break;
        const unsigned char* next_item = (const unsigned char*)info.BaseAddress + info.RegionSize;

        bool usable = info.State == MEM_COMMIT &&
                         !(info.Protect & PAGE_GUARD) &&
                         (info.Protect & READABLE);
        if (usable && own_stack(info)) { skip(own, info, searched); usable = false; }
        if (usable && uncached(info)) { skip(slow, info, searched); usable = false; }
        if (usable) {
            // A match may start at every place up to the one where it ends with the region or the
            // stretch, that place included: `stop` stands one past it.
            const unsigned char* begin = (const unsigned char*)info.BaseAddress;
            const unsigned char* stop = next_item - length + 1;
            if (begin < pointer) begin = pointer;
            if (stop > end_at - length + 1) stop = end_at - length + 1;
            // memchr jumps in large strides to the next candidate. Comparing byte by byte is ten times
            // slower here: measured 28 July 2026, a naive loop over this memory took longer than
            // five minutes.
            __try {
                const unsigned char* q = begin;
                while (q < stop) {
                    const unsigned char* hit =
                        (const unsigned char*)memchr(q, pattern[0], (size_t)(stop - q));
                    if (!hit) break;
                    if (memcmp(hit, pattern, (size_t)length) == 0) {
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
    say_skipped("own stack", own);
    say_skipped("uncached", slow);
    emit("done\t%d\treported\t%d\tskipped\t%d\n", found, reported, skipped);
    // The list stops at LIMIT; more hits than that is an error after the list, so nobody takes the
    // first two hundred for all of them.
    if (found > reported) emit("error: %d hits and only the first %d listed; narrow the search\n", found, reported);
}

// readmany: one command, many addresses. Thousands of characters meant thousands of separate
// reads of about 0.7 ms each; this turns those into one answer.
static void cmd_readmany(const char* rest)
{
    unsigned long long count = 0, address = 0;
    const char* p = rest;
    if (!take(&p, 'u', &count)) {
        emit("error: readmany <count> <address> <address> ...\n");
        return;
    }
    if (count > 65536) { emit("error: at most 65536 bytes per address\n"); return; }
    int done = 0;
    while (take(&p, 'x', &address)) {
        const unsigned char* q = as_pointer<const unsigned char*>(address);
        if (!readable(q, count)) {
            emit("l\t%llx\tunreadable\n", address);
        } else {
            emit("l\t%llx\t", address);
            buf_hex(q, count);
            emit("\n");
        }
        done++;
    }
    if (!all_read(p)) { emit("error: not an address: %.40s\n", p); return; }
    emit("done\t%d\n", done);
}

// --- running commands and serving the pipe ----------------------------------
// set: all seven field offsets, in hex, in one go.
static void cmd_set(const char* rest)
{
    unsigned long long v[7];
    if (!args(rest, "xxxxxxx", v)) {
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
    unsigned long long value = 0;
    while (take(&p, 'x', &value)) {
        if (count == 256) { emit("error: more than 256 vtables; this limit has to grow\n"); return; }
        int j = count++;
        while (j > 0 && fresh[j - 1] > value) { fresh[j] = fresh[j - 1]; j--; }
        fresh[j] = value;
    }
    if (!all_read(p)) { emit("error: not a vtable address: %.40s\n", p); return; }
    memcpy(g_vtables, fresh, sizeof(unsigned long long) * count);
    g_vtable_count = count;
    emit("vtables set\t%d\n", count);
}

// The command word picks the handler; a word whose arguments are read here is accepted only when
// `args` read all of them, and a form with an optional argument is tried once per length, longest
// first. A word that needs arguments wants something after it, or it is an unknown command.
static void dispatch(char* command)
{
    buf_clear();
    const char* rest = command + strcspn(command, " ");
    const size_t length = (size_t)(rest - command);
    auto is = [command, length](const char* word) {
        return strlen(word) == length && strncmp(command, word, length) == 0;
    };
    auto at = [](unsigned long long number) { return as_pointer<const unsigned char*>(number); };
    unsigned long long v[3] = {0};
    const char* pattern = rest;   // findin: what follows its two addresses
    if (is("set") && *rest)                                cmd_set(rest);
    else if (is("vtables") && *rest)                       cmd_vtables(rest);
    else if (is("scan") && args(rest, "xx", v))            cmd_scan(Span{at(v[0]), at(v[1])});
    else if (is("scan") && args(rest, "", v))              cmd_scan(Span{});
    else if (is("tree") && args(rest, "x", v))             cmd_tree(at(v[0]));
    else if (is("read") && args(rest, "xu", v))            cmd_read(at(v[0]), static_cast<unsigned>(v[1]));
    else if (is("readmany") && *rest)                      cmd_readmany(rest);
    else if (is("findin") && take(&pattern, 'x', &v[0]) && take(&pattern, 'x', &v[1]))
        cmd_find(pattern, Span{at(v[0]), at(v[1])});
    else if (is("find") && *rest)                          cmd_find(rest, Span{});
    else if (strcmp(command, "keys on") == 0)              keys_enable(true);
    else if (strcmp(command, "keys off") == 0)             keys_enable(false);
    else if (is("swallow"))                                cmd_swallow(rest);
    else if (is("waitkey") && args(rest, "u", v))          cmd_waitkey(static_cast<DWORD>(v[0]));
    else if (is("mouse") && args(rest, "uu", v))
        cmd_mouse(static_cast<unsigned>(v[0]), static_cast<unsigned>(v[1]));
    else if (is("sendkey") && args(rest, "u", v))          cmd_sendkey(static_cast<unsigned>(v[0]));
    else if (is("sendchar") && args(rest, "u", v))         cmd_sendchar(static_cast<unsigned>(v[0]));
    else if (strcmp(command, "count") == 0)                cmd_count();
    else if (is("combo") && *rest)                         cmd_combo(rest);
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
    // On the list of own stacks for as long as this session runs, so no search finds it (own_stack).
    OwnStack mine;
    GetCurrentThreadStackLimits(&mine.low, &mine.high);
    AcquireSRWLockExclusive(&g_own_lock);
    mine.next = g_own_stacks;
    g_own_stacks = &mine;
    ReleaseSRWLockExclusive(&g_own_lock);
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
    AcquireSRWLockExclusive(&g_own_lock);
    for (OwnStack** link = &g_own_stacks; *link != NULL; link = &(*link)->next)
        if (*link == &mine) { *link = mine.next; break; }
    ReleaseSRWLockExclusive(&g_own_lock);
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
        CreateThread(NULL, 0, serve_pipe, NULL, 0, NULL);
    }
    return TRUE;
}
