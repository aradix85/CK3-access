// The target tests/test_channel.py runs channel.dll in. It loads the DLL, builds a small fake
// widget tree that holds every case the walk must report, and asks Windows about the keyboard ten
// times a second through its own import table, so the counter has something it must see.
// It also owns one window, off the screen and never activated, so posted keys have somewhere to
// land: every key message is written to the log named on the command line, with what this
// process's own GetKeyState says about shift, ctrl and alt at that moment - the answer `combo`
// changes.
//
// Fake layout: vtable 0, parent 8, position 0x10, size 0x18, name 0x20, text 0x40, children 0x60,
// count 0x68. Vtable 0x1111 is a widget, 0x2222 is not.
#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef unsigned long long u64;

static FILE* g_log;

static LRESULT CALLBACK host_proc(HWND window, UINT message, WPARAM w, LPARAM l)
{
    const char* kind = message == WM_KEYDOWN ? "down" : message == WM_SYSKEYDOWN ? "sysdown" :
                       message == WM_KEYUP ? "up" : message == WM_SYSKEYUP ? "sysup" : NULL;
    if (!kind) return DefWindowProcA(window, message, w, l);
    fprintf(g_log, "%s %02x %d %d %d %d\n", kind, (unsigned)w, (int)((l >> 29) & 1),
            GetKeyState(VK_LSHIFT) < 0, GetKeyState(VK_CONTROL) < 0, GetKeyState(VK_MENU) < 0);
    fflush(g_log);
    return 0;
}

static void put_string(unsigned char* object, size_t field, const char* text, size_t length, const char* elsewhere)
{
    if (elsewhere) {
        *(const char**)(object + field) = elsewhere;
        *(u64*)(object + field + 24) = length;          // capacity above 15: a pointer
    } else {
        memcpy(object + field, text, length);
        *(u64*)(object + field + 24) = 15;              // text in place
    }
    *(u64*)(object + field + 16) = length;
}

static unsigned char* widget(unsigned char* at, u64 vtable, const char* name, u64 parent)
{
    memset(at, 0, 0x70);
    *(u64*)at = vtable;
    *(u64*)(at + 8) = parent;
    *(float*)(at + 0x10) = 1.0f; *(float*)(at + 0x14) = 2.0f;
    *(float*)(at + 0x18) = 3.0f; *(float*)(at + 0x1C) = 4.0f;
    put_string(at, 0x20, name, strlen(name), NULL);
    return at;
}

static char long_text[9000];

int main(int argc, char** argv)
{
    unsigned char* page = (unsigned char*)VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    unsigned char* gap = (unsigned char*)VirtualAlloc(NULL, 65536, MEM_RESERVE, PAGE_NOACCESS);
    unsigned char* many = (unsigned char*)VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    for (int i = 0; i < 300; i++) memcpy(many + 4 * i, "CK3!", 4);
    memset(long_text, 'x', sizeof(long_text));

    unsigned char* A = widget(page + 0x000, 0x1111, "root", 0);
    unsigned char* B = widget(page + 0x080, 0x1111, "child", (u64)A);
    unsigned char* C = widget(page + 0x100, 0x2222, "stranger", (u64)A);
    unsigned char* D = gap;                                       // reserved, never committed
    unsigned char* E = widget(page + 0x180, 0x1111, "long", (u64)A);
    unsigned char* F = widget(page + 0x200, 0x1111, "absurd", (u64)A);
    unsigned char* G = page + 4096 - 0x20;                        // child fields past the page
    *(u64*)G = 0x1111;
    u64* list_a = (u64*)(page + 0x400);
    list_a[0] = (u64)B; list_a[1] = (u64)C; list_a[2] = (u64)D; list_a[3] = (u64)E; list_a[4] = (u64)F;
    list_a[5] = (u64)G;
    *(u64*)(A + 0x60) = (u64)list_a; *(unsigned*)(A + 0x68) = 6;
    put_string(B, 0x40, "Hello", 5, NULL);
    *(u64*)(B + 0x60) = (u64)(gap + 0x100); *(unsigned*)(B + 0x68) = 2;   // child list unreadable
    put_string(E, 0x40, NULL, sizeof(long_text), long_text);
    *(u64*)(F + 0x60) = (u64)list_a; *(unsigned*)(F + 0x68) = 200000;   // not believable
    *(u64*)(page + 4096 - 8) = 0x1111;                            // a vtable in the last eight bytes

    printf("objects %llx %llx %llx %llx %llx %llx %llx %llx %llx\n", (u64)A, (u64)B, (u64)C, (u64)D,
           (u64)E, (u64)F, (u64)G, (u64)page, (u64)many);
    fflush(stdout);
    g_log = argc > 2 ? fopen(argv[2], "w") : NULL;
    if (!g_log) { printf("no log\n"); return 1; }
    WNDCLASSA kind = {0};
    kind.lpfnWndProc = host_proc;
    kind.hInstance = GetModuleHandleA(NULL);
    kind.lpszClassName = "channel_host";
    RegisterClassA(&kind);
    HWND window = CreateWindowExA(WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, "channel_host", "channel host",
                                  WS_POPUP, -32000, -32000, 10, 10, NULL, NULL, kind.hInstance, NULL);
    ShowWindow(window, SW_SHOWNOACTIVATE);
    if (!LoadLibraryA(argv[1])) { printf("load failed %lu\n", GetLastError()); return 1; }
    printf("loaded\n");
    fflush(stdout);
    BYTE state[256];
    UINT size = 0;
    for (int i = 0; i < 1200; i++) {
        GetKeyState(VK_LSHIFT);
        GetAsyncKeyState(VK_SHIFT);
        GetKeyboardState(state);
        size = 0;
        GetRawInputData((HRAWINPUT)0, RID_INPUT, NULL, &size, sizeof(RAWINPUTHEADER));
        MsgWaitForMultipleObjects(0, NULL, FALSE, 100, QS_ALLINPUT);
        MSG message;
        while (PeekMessageA(&message, NULL, 0, 0, PM_REMOVE)) DispatchMessageA(&message);
    }
    return 0;
}
